"""Carga CSV oficiales de IX EPF y recalcula combustibles por hogar y dominio.

Ejemplo: python 04_recalcular_combustibles.py --datos datos --salida resultados
El exportador Excel se ejecuta después con 07_exportar_excel.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import unicodedata

import numpy as np
import pandas as pd

from modulos.epf_calculos import CODIGOS, DisenoTaylor, medianas_de_gastadores, segmentar_hogares


# Los identificadores se leen como texto y los decimales con la convención del CSV INE.
PERSONAS = ["folio", "fe", "estrato_muestreo", "var_unit", "parentesco", "macrozona",
            "ing_disp_hog_hd", "ing_disp_hog_hd_pc", "gastot_hd", "gastot_hd_pc"]
IDENTIFICADORES = ["folio", "estrato_muestreo", "var_unit", "macrozona"]


def leer_csv(path, columnas=None, chunksize=None):
    """Lee el formato oficial: UTF-8 con BOM, punto y coma y coma decimal."""
    return pd.read_csv(path, sep=";", decimal=",", encoding="utf-8-sig", usecols=columnas,
                       dtype={k: "string" for k in IDENTIFICADORES + ["ccif", "glosa_ccif"]
                              if columnas is None or k in columnas}, chunksize=chunksize)


def validar_hogares(personas):
    """Exige una persona de referencia por hogar y evita multiplicar gasto por personas."""
    requeridas = set(PERSONAS)
    if requeridas - set(personas):
        raise ValueError(f"Faltan variables: {sorted(requeridas-set(personas))}")
    if personas[PERSONAS].isna().any().any():
        raise ValueError("Hay campos requeridos perdidos en la base de personas.")
    hogar_vars = [c for c in PERSONAS if c not in ("folio", "parentesco")]
    if (personas.groupby("folio")[hogar_vars].nunique(dropna=False) > 1).any().any():
        raise ValueError("Variables del hogar inconsistentes entre sus integrantes.")
    h = personas.loc[personas.parentesco == 1, hogar_vars + ["folio"]].copy()
    if h.folio.duplicated().any() or set(h.folio) != set(personas.folio):
        raise ValueError("No existe exactamente una persona de referencia por hogar.")
    h = h.reset_index(drop=True)
    numericas = [c for c in hogar_vars if c not in IDENTIFICADORES]
    if not np.isfinite(h[numericas].to_numpy(float)).all() or (h.fe <= 0).any():
        raise ValueError("Variables monetarias o factores no válidos.")
    if (h.groupby("var_unit").estrato_muestreo.nunique() > 1).any():
        raise ValueError("Un pseudo-conglomerado pertenece a más de un estrato.")
    return h


def cargar_gastos(path, hogares):
    """Vincula por folio, valida factores y suma solo los dos productos seleccionados."""
    columnas = ["folio", "fe", "estrato_muestreo", "var_unit", "ccif", "gasto", "glosa_ccif"]
    lookup = hogares.set_index("folio")
    trozos, filas, sin_folio = [], 0, 0
    for bloque in leer_csv(path, columnas, chunksize=100_000):
        filas += len(bloque)
        valido = bloque.folio.notna() & bloque.folio.fillna("").str.strip().ne("")
        sin_folio += int((~valido).sum())
        b = bloque.loc[valido].copy()
        # Los registros sin folio son productos sin presencia, no hogares adicionales.
        if not b.folio.isin(lookup.index).all():
            raise ValueError("La base de gastos contiene folios ausentes en personas.")
        ref = lookup.reindex(b.folio)
        if not np.allclose(b.fe.to_numpy(float), ref.fe.to_numpy(float), rtol=1e-11, atol=1e-9):
            raise ValueError("El factor de expansión no coincide entre personas y gastos.")
        for campo in ("estrato_muestreo", "var_unit"):
            if not np.array_equal(b[campo].astype(str).to_numpy(), ref[campo].astype(str).to_numpy()):
                raise ValueError(f"La variable {campo} no coincide entre bases.")
        trozos.append(b.loc[b.ccif.isin(CODIGOS.values())])
    seleccion = pd.concat(trozos, ignore_index=True)
    if seleccion.duplicated(["folio", "ccif"]).any():
        raise ValueError("Más de una fila hogar-producto: revisar la estructura antes de agregar.")
    if not np.isfinite(seleccion.gasto.to_numpy(float)).all() or (seleccion.gasto < 0).any():
        raise ValueError("Gastos de combustible perdidos, negativos o no finitos.")
    tabla = seleccion.pivot(index="folio", columns="ccif", values="gasto")
    for nombre, codigo in CODIGOS.items():
        if codigo not in tabla:
            raise ValueError(f"No se encontró gasto en {codigo}; no se presume un gasto cero general.")
        # Solo la ausencia de un producto en un hogar válido se interpreta como cero registrado.
        hogares[nombre] = tabla[codigo].reindex(hogares.folio).fillna(0).to_numpy(float)
    return hogares, {"filas_gastos": filas, "filas_sin_folio": sin_folio,
                      "filas_combustibles": len(seleccion)}


def verificar_clasificador(path):
    """Comprueba que los códigos sigan correspondiendo a gasolina y diésel."""
    c = leer_csv(path)
    for nombre, codigo in CODIGOS.items():
        fila = c.loc[c.ccif == codigo, "glosa_ccif"]
        if len(fila) != 1:
            raise ValueError(f"Código ausente o duplicado en CCIF: {codigo}")
        texto = "".join(x for x in unicodedata.normalize("NFKD", fila.iloc[0].lower()) if not unicodedata.combining(x))
        if nombre not in texto:
            raise ValueError(f"La glosa del código {codigo} cambió: {fila.iloc[0]}")
    return c.loc[c.ccif.isin(CODIGOS.values())].to_dict("records")


def controles_oficiales(hogares, deciles, path):
    """Replica 20 valores publicados para verificar orden, factores y productos.

    Se contrasta gasto, ingreso, gasolina y diésel de todos los hogares por quintil
    contra los cuadros 4A y 7B. El control no usa hogares filtrados.
    """
    import openpyxl  # Solo lectura de los controles oficiales, sin alterar la fuente.
    libro = openpyxl.load_workbook(path, data_only=True, read_only=True)
    controles = []
    for q in range(5):
        pesos = hogares.fe.to_numpy(float) * deciles[:, q*2:q*2+2].sum(axis=1)
        variables = [("ing_disp_hog_hd", "CUADROS 4A - 4E", f"J{8+q}"),
                     ("gastot_hd", "CUADROS 4A - 4E", f"G{8+q}"),
                     ("gasolina", "CUADRO 7B", f"{chr(68+q)}716"),
                     ("diesel", "CUADRO 7B", f"{chr(68+q)}715")]
        for variable, hoja, celda in variables:
            calculado = float(np.average(hogares[variable].to_numpy(float), weights=pesos))
            oficial = float(libro[hoja][celda].value)
            controles.append({"quintil": q+1, "variable": variable, "calculado": calculado,
                              "oficial": oficial, "diferencia": calculado-oficial,
                              "coincide": bool(abs(calculado-oficial) <= 0.02),
                              "hoja": hoja, "celda": celda})
    libro.close()
    if not all(c["coincide"] for c in controles):
        raise ArithmeticError("No se reprodujeron los tabulados oficiales dentro de $0,02: revisar controles.")
    return controles


def ejecutar(datos: Path, salida: Path, configuracion: Path | None = None):
    """Ejecuta el cálculo, conserva trazabilidad y produce insumos para el Excel."""
    salida.mkdir(parents=True, exist_ok=True)
    # También en modo local se exige la misma versión de las cuatro fuentes validadas.
    configuracion = configuracion or Path(__file__).resolve().parent/"configuracion.json"
    config = json.loads(configuracion.read_text(encoding="utf-8"))
    fuentes = []
    for fuente in config["archivos"]:
        archivo = datos/fuente["archivo"]
        with archivo.open("rb") as f:
            digest = hashlib.file_digest(f, "sha256").hexdigest()
        if archivo.stat().st_size != fuente["bytes"] or digest != fuente["sha256"]:
            raise ValueError(f"Versión de fuente no validada: {archivo.name}. Revisar configuración y publicación INE.")
        fuentes.append({"archivo": archivo.name, "bytes": archivo.stat().st_size, "sha256": digest})
    clasificador = verificar_clasificador(datos / "ccif.csv")
    personas = leer_csv(datos / "personas.csv", PERSONAS)
    hogares = validar_hogares(personas)
    hogares, diagnostico = cargar_gastos(datos / "gastos.csv", hogares)
    deciles = segmentar_hogares(hogares, 10)
    # El indicador ciudadano relaciona dos medianas del mismo conjunto de gastadores.
    # Los ingresos <=0 permanecen en ese conjunto; no se calculan cargas por hogar.
    grupos=[('Total','Total',np.ones(len(hogares)))]
    grupos += [('Quintil',str(q+1),deciles[:,2*q:2*q+2].sum(axis=1)) for q in range(5)]
    grupos += [('Decil',str(q+1),deciles[:,q]) for q in range(10)]
    filas=[]
    for tipo,grupo,fr in grupos:
        for fuel in ['gasolina_diesel','gasolina','diesel']:
            gasto=(hogares.gasolina+hogares.diesel) if fuel=='gasolina_diesel' else hogares[fuel]
            puntos=medianas_de_gastadores(gasto,hogares.ing_disp_hog_hd,hogares.fe.to_numpy()*fr)
            filas.append({'segmentacion':tipo,'grupo':grupo,'combustible':fuel,**puntos})
    resumen=pd.DataFrame(filas);precision=pd.DataFrame()

    # Se conservan todos los hogares y las pertenencias fraccionarias, sin datos personales.
    hogares["gasolina_diesel"] = hogares.gasolina + hogares.diesel
    hogares["gasta_combustible"] = (hogares.gasolina_diesel > 0).astype(int)
    hogares["ingreso_no_positivo"] = (hogares.ing_disp_hog_hd <= 0).astype(int)
    for d in range(10):
        hogares[f"fraccion_decil_{d+1}"] = deciles[:, d]
    largo = []
    for i, h in hogares.iterrows():
        for d in np.flatnonzero(deciles[i] > 1e-12):
            largo.append({"folio": h.folio, "estrato_muestreo": h.estrato_muestreo,
                          "var_unit": h.var_unit, "decil": int(d+1), "quintil": int(d//2+1),
                          "fe_segmento": float(h.fe*deciles[i,d]), "ingreso": float(h.ing_disp_hog_hd),
                          "gasto_total": float(h.gastot_hd), "gasolina": float(h.gasolina),
                          "diesel": float(h.diesel), "gasolina_diesel": float(h.gasolina_diesel),
                          "ingreso_positivo": int(h.ing_disp_hog_hd > 0)})

    # Los controles oficiales son parte obligatoria de esta versión reproducible.
    controles = controles_oficiales(hogares, deciles, datos / "tabulados.xlsx")
    pesos_segmentos = deciles.T @ hogares.fe.to_numpy(float)
    if not np.allclose(pesos_segmentos, hogares.fe.sum()/10, atol=1e-6, rtol=0):
        raise ArithmeticError("Los deciles no reúnen exactamente una décima parte del peso total.")
    ingreso_control = DisenoTaylor(hogares).razon(hogares.ing_disp_hog_hd.to_numpy(float))
    # La tabla 5 del manual publica EE 18.082,39 para el ingreso total sin arriendo.
    if not np.isclose(ingreso_control["ee"], 18082.39, atol=0.02, rtol=0):
        raise ArithmeticError(f"Error estándar no reproduce el manual: {ingreso_control['ee']}")
    diagnostico.update(personas=len(personas), hogares=len(hogares),
                       hogares_expandidos=float(hogares.fe.sum()),
                       estratos=hogares.estrato_muestreo.nunique(),
                       conglomerados=hogares.var_unit.nunique(),
                       control_ingreso=ingreso_control,
                       controles_oficiales=controles,
                       filas_segmentadas=len(largo))
    # Los dominios sin observaciones se conservan como null, nunca como gasto cero.
    r_json = resumen.astype(object).where(pd.notna(resumen), None).to_dict("records")
    p_json = precision.astype(object).where(pd.notna(precision), None).to_dict("records")
    payload = {"resumen": r_json, "precision": p_json,
               "hogares_segmentados": largo, "diagnostico": diagnostico,
               "clasificador": clasificador, "archivos": fuentes}
    (salida/"resultados.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    hogares.to_csv(salida/"hogares_procesados.csv", index=False, encoding="utf-8-sig", float_format="%.15g")
    resumen.to_csv(salida/"resumen.csv", index=False, encoding="utf-8-sig", float_format="%.15g")
    precision.to_csv(salida/"precision.csv", index=False, encoding="utf-8-sig", float_format="%.15g")
    (salida/"validaciones.json").write_text(json.dumps(diagnostico, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Cálculo terminado: {len(hogares):,} hogares; 20 controles oficiales coinciden.")
    print(f"Error estándar de ingreso replicado: {ingreso_control['ee']:.4f}; gl={ingreso_control['gl']}.")
    print(resumen.loc[(resumen.segmentacion == "Quintil") & (resumen.combustible == "gasolina_diesel"),
                      ["grupo", "n_gastadores", "gasto_mediano", "ingreso_mediano", "relacion_medianas"]].to_string(index=False))
    return payload


# La interfaz admite rutas con espacios y no requiere permisos de administrador.
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datos", type=Path, default=Path(__file__).resolve().parent/"datos")
    parser.add_argument("--salida", type=Path, default=Path(__file__).resolve().parent/"resultados")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parent/"configuracion.json")
    args = parser.parse_args()
    try:
        ejecutar(args.datos.resolve(), args.salida.resolve(), args.config.resolve())
    except (ValueError, ArithmeticError, FileNotFoundError) as error:
        print(f"No se generaron resultados válidos: {error}", file=sys.stderr)
        sys.exit(1)
