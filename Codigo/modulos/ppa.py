"""Ajuste PPA anual aproximado para precios GPP; no estima ingresos de hogares."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def extraer_factores(archivo_weo, raiz):
    """Extrae países y años de los precios actualizados y conserva sus celdas."""
    import openpyxl
    from openpyxl.utils import get_column_letter

    raiz = Path(raiz)
    cfg = json.loads((raiz / "configuracion.json").read_text(encoding="utf-8"))
    fuente = cfg["ppa"]["fuente"]
    digest = hashlib.sha256(Path(archivo_weo).read_bytes()).hexdigest()
    if digest != fuente["sha256"]:
        raise ValueError("El WEO no coincide con la edición y huella documentadas.")
    precios = pd.read_csv(raiz / "gpp_precios.csv")
    paises = precios.set_index("iso").pais.to_dict()
    anos = sorted(set(pd.to_datetime(precios.fecha).dt.year))
    w = openpyxl.load_workbook(archivo_weo, read_only=True, data_only=True)
    s = w["Countries"]
    cab = list(next(s.values))
    pos = {v: i for i, v in enumerate(cab)}
    series = {}
    for numero, fila in enumerate(s.values, 1):
        iso, indicador = fila[pos["COUNTRY.ID"]], fila[pos["INDICATOR.ID"]]
        if iso in paises and indicador in ("NGDP", "NGDPD", "PPPGDP", "PPPEX"):
            if (iso, indicador) in series:
                raise ValueError("Serie WEO duplicada.")
            series[(iso, indicador)] = (numero, fila)
    registros = []
    for iso in sorted(paises):
        for ano in anos:
            registro = {"iso": iso, "pais": paises[iso], "ano": ano}
            for indicador in ("NGDP", "NGDPD", "PPPGDP", "PPPEX"):
                numero, fila = series[(iso, indicador)]
                valor = fila[pos[ano]]
                if not isinstance(valor, (int, float)) or valor <= 0:
                    raise ValueError(f"Falta un valor WEO positivo: {iso}, {ano}, {indicador}.")
                registro[indicador.lower()] = float(valor)
                registro["celda_" + indicador.lower()] = f"Countries!{get_column_letter(pos[ano]+1)}{numero}"
                ultimo = fila[pos["LATEST_ACTUAL_ANNUAL_DATA"]]
                registro["ultimo_actual_" + indicador.lower()] = ultimo
                registro["estado_" + indicador.lower()] = (
                    "Estimación/proyección" if isinstance(ultimo, (int, float)) and ano > ultimo
                    else "Actual revisable" if isinstance(ultimo, (int, float)) and ultimo > 0
                    else "PPA estimada; sin año actual especificado")
            # PIB en PPA / PIB en USD convierte dólares a dólares internacionales
            # con un factor anual. No recupera el precio local de cada fecha.
            registro["factor_ppa"] = registro["pppgdp"] / registro["ngdpd"]
            registro["fx_implicito_anual"] = registro["ngdp"] / registro["ngdpd"]
            registro["edicion"] = fuente["titulo"]
            registro["fuente_url"] = fuente["url"]
            registro["sha256_fuente"] = digest
            registros.append(registro)
    salida = pd.DataFrame(registros)
    destino = raiz / cfg["ppa"]["archivo"]
    salida.to_csv(destino, index=False, encoding="utf-8")
    return salida


def leer_factores(raiz):
    """Falla si cambian la extracción congelada, el universo o las claves de año."""
    raiz = Path(raiz)
    cfg = json.loads((raiz / "configuracion.json").read_text(encoding="utf-8"))["ppa"]
    archivo = raiz / cfg["archivo"]
    if hashlib.sha256(archivo.read_bytes()).hexdigest() != cfg["sha256"]:
        raise ValueError("La extracción PPA cambió; revisar fuente, años y huellas.")
    f = pd.read_csv(archivo)
    paises = set(pd.read_csv(raiz / "gpp_precios.csv").iso)
    anos=set(pd.to_datetime(pd.read_csv(raiz / 'gpp_precios.csv').fecha).dt.year)
    if len(f) != len(paises)*len(anos) or f.duplicated(["iso", "ano"]).any():
        raise ValueError("Faltan factores PPA anuales únicos.")
    if set(f.iso) != paises or set(f.ano) != anos:
        raise ValueError("PPA y GPP no comparten países y años.")
    for c in ("ngdp", "ngdpd", "pppgdp", "pppex", "factor_ppa"):
        if not np.isfinite(f[c]).all() or (f[c] <= 0).any():
            raise ValueError(f"Factor PPA inválido en {c}.")
    if not np.allclose(f.factor_ppa, f.pppgdp/f.ngdpd, rtol=1e-13):
        raise ValueError("El factor no corresponde a PIB PPA / PIB USD.")
    return f


def calcular_ppa(gpp, factores):
    """Une por país y año, conserva fechas GPP y ordena desde el menor precio."""
    g = gpp.copy()
    g["ano"] = pd.to_datetime(g.fecha).dt.year
    d = g.merge(factores, on=["iso", "pais", "ano"], how="left", validate="many_to_one")
    if len(d) != len(gpp) or d.factor_ppa.isna().any():
        raise ValueError("No se puede completar la PPA para todos los precios GPP.")
    d["precio_ppa_aprox"] = d.usd_litro * d.factor_ppa
    d["puesto_ppa"] = d.groupby(["fecha", "combustible"]).precio_ppa_aprox.rank(method="min").astype(int)
    # La sensibilidad conserva los factores de 2025 en toda la ventana; permite
    # observar cuánto cambia el puesto por actualizar el factor anual en 2026.
    fijo = factores[factores.ano == 2025].set_index("iso").factor_ppa
    d["factor_fijo_2025"] = d.iso.map(fijo)
    d["precio_ppa_fijo_2025"] = d.usd_litro * d.factor_fijo_2025
    d["puesto_ppa_fijo_2025"] = d.groupby(["fecha", "combustible"]).precio_ppa_fijo_2025.rank(method="min").astype(int)
    return d.sort_values(["fecha", "combustible", "iso"]).reset_index(drop=True)


# Se puede regenerar la extracción a partir del libro WEO completo y verificado.
if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fuente-weo", type=Path, required=True)
    a = p.parse_args()
    tabla = extraer_factores(a.fuente_weo, Path(__file__).resolve().parents[1])
    print(f"Factores PPA extraídos: {len(tabla)}. Verificar y registrar su SHA-256 antes del uso.")
