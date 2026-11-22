"""Estimadores de dominio y segmentación ponderada para la IX EPF.

La unidad analítica es el hogar. Los importes son mensuales, en pesos de
2021–2022. La selección de hogares con gasto no elimina conglomerados del
diseño completo: sus contribuciones fuera del dominio se dejan en cero.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import t as student_t


# Se usan productos específicos de transporte personal, sin lubricantes ni gas doméstico.
CODIGOS = {"gasolina": "07.2.2.02.01", "diesel": "07.2.2.01.01"}
COMBUSTIBLES = {"gasolina_diesel": "Gasolina + diésel", "gasolina": "Gasolina", "diesel": "Diésel"}


def segmentar_hogares(hogares: pd.DataFrame, grupos: int = 10) -> np.ndarray:
    """Aplica el orden del manual, pp. 72–75, y divide pesos en los límites.

    El gasto per cápita sustituye al ingreso SOLO para ordenar hogares cuyo
    ingreso disponible total es <= 0. Su ingreso original no se reemplaza.
    Se devuelve una fracción por hogar y grupo, con suma por hogar igual a 1.
    """
    if not isinstance(grupos, int) or grupos < 2:
        raise ValueError("El número de grupos debe ser un entero >= 2.")
    h = hogares.copy()
    h["_posicion"] = np.arange(len(h))
    h["_orden"] = np.where(h.ing_disp_hog_hd <= 0, h.gastot_hd_pc, h.ing_disp_hog_hd_pc)
    h = h.sort_values(["_orden", "ing_disp_hog_hd_pc", "gastot_hd_pc", "folio"], kind="mergesort")
    fe = h.fe.to_numpy(float)
    if not np.isfinite(fe).all() or (fe <= 0).any():
        raise ValueError("Los factores de expansión deben ser positivos y finitos.")

    # La intersección de intervalos acumulados reproduce la partición de factores.
    superior = np.cumsum(fe)
    inferior = superior - fe
    cortes = np.linspace(0, superior[-1], grupos + 1)
    partes = np.maximum(0, np.minimum(superior[:, None], cortes[None, 1:])
                        - np.maximum(inferior[:, None], cortes[None, :-1]))
    fracciones = np.zeros_like(partes)
    fracciones[h._posicion.to_numpy()] = partes / fe[:, None]
    if not np.allclose(fracciones.sum(axis=1), 1, atol=1e-10, rtol=0):
        raise ArithmeticError("La segmentación no conserva los factores por hogar.")
    return fracciones


def cuantiles_ponderados(valores, pesos, probabilidades=(0.25, 0.5, 0.75)):
    """Cuantiles de la distribución empírica ponderada, sin interpolación."""
    v, w = np.asarray(valores, float), np.asarray(pesos, float)
    usar = np.isfinite(v) & np.isfinite(w) & (w > 0)
    if not usar.any():
        return [None] * len(probabilidades)
    orden = np.argsort(v[usar], kind="mergesort")
    v, w = v[usar][orden], w[usar][orden]
    acumulado = np.cumsum(w)
    return [float(v[min(np.searchsorted(acumulado, p * acumulado[-1], side="left"), len(v)-1)])
            for p in probabilidades]


def medianas_de_gastadores(gasto, ingreso, pesos):
    """Relaciona dos medianas del mismo dominio; conserva ingreso cero o negativo."""
    g,y,w=np.asarray(gasto,float),np.asarray(ingreso,float),np.asarray(pesos,float)
    if not (g.shape==y.shape==w.shape) or not np.isfinite(np.c_[g,y,w]).all():
        raise ValueError('Variables o pesos no válidos para las medianas.')
    if (g<0).any() or (w<0).any():raise ValueError('Gastos y ponderadores no pueden ser negativos.')
    dominio=(g>0)&(w>1e-12)
    if not dominio.any():raise ValueError('No existen hogares con gasto en el dominio.')
    gm=cuantiles_ponderados(g[dominio],w[dominio],[.5])[0]
    ym=cuantiles_ponderados(y[dominio],w[dominio],[.5])[0]
    if ym<=0:raise ValueError('El ingreso mediano del dominio debe ser positivo.')
    return {'n_gastadores':int(dominio.sum()),'gasto_mediano':gm,'ingreso_mediano':ym,
            'relacion_medianas':gm/ym,'n_ingreso_no_positivo':int((y[dominio]<=0).sum())}


class DisenoTaylor:
    """Linealización de razones con estratos y pseudo-conglomerados completos.

    Var(R) = sum_h [m_h/(m_h-1) * sum_j (u_hj - media_h(u))**2],
    donde u_hj suma fe_i*a_i*(y_i-R*x_i)/sum(fe*a*x) dentro del conglomerado.
    a_i combina pertenencia fraccionaria al grupo y el indicador de dominio.
    No se aplica corrección de población finita, como en la Programación 1
    del manual. Los grados de libertad se calculan dentro del dominio (p. 84).
    """
    def __init__(self, hogares: pd.DataFrame):
        self.pesos = hogares.fe.to_numpy(float)
        if not np.isfinite(self.pesos).all() or (self.pesos <= 0).any():
            raise ValueError("Factores de expansión no válidos.")
        ids = pd.MultiIndex.from_frame(hogares[["estrato_muestreo", "var_unit"]])
        self.cluster, self.ids = pd.factorize(ids, sort=True)
        self.estrato, self.estratos = pd.factorize(self.ids.get_level_values(0), sort=True)
        self.m = np.bincount(self.estrato)
        if (self.m < 2).any():
            raise ValueError("Hay un estrato con menos de dos conglomerados en el diseño completo.")
        self.n = len(hogares)

    def razon(self, y, x=None, pertenencia=None):
        """Estima medias, participaciones o razones; conserva ceros fuera del dominio."""
        y = np.asarray(y, float)
        x = np.ones(self.n) if x is None else np.asarray(x, float)
        a = np.ones(self.n) if pertenencia is None else np.asarray(pertenencia, float)
        if any(len(v) != self.n for v in (y, x, a)):
            raise ValueError("Las variables no coinciden con el número de hogares del diseño.")
        if not np.isfinite(a).all() or (a < 0).any() or (a > 1 + 1e-9).any():
            raise ValueError("Pertenencia de dominio fuera de [0,1].")
        activo = a > 1e-12
        if not np.isfinite(y[activo]).all() or not np.isfinite(x[activo]).all():
            raise ValueError("Hay valores no finitos dentro del dominio analizado.")
        c_activos = np.unique(self.cluster[activo])
        df = int(len(c_activos) - len(np.unique(self.estrato[c_activos])))
        salida = {"n": int(activo.sum()), "gl": df, "conglomerados": int(len(c_activos)),
                  "estimacion": None, "ee": None, "li95": None, "ls95": None, "cv": None,
                  "numerador": 0.0, "denominador": 0.0, "peso_dominio": float(np.sum(self.pesos * a))}
        if not activo.any():
            return salida

        # Los valores ajenos al dominio se anulan sin eliminar sus conglomerados.
        yy, xx = np.where(activo, y, 0), np.where(activo, x, 0)
        wa = self.pesos * a
        numerador, denominador = float(wa @ yy), float(wa @ xx)
        salida.update(numerador=numerador, denominador=denominador)
        if denominador <= 0:
            return salida
        estimacion = numerador / denominador
        u = wa * (yy - estimacion * xx) / denominador
        uj = np.bincount(self.cluster, weights=u, minlength=len(self.ids))
        medias = np.bincount(self.estrato, weights=uj) / self.m
        residuos2 = (uj - medias[self.estrato]) ** 2
        varianza = float(np.sum(np.bincount(self.estrato, weights=residuos2) * self.m / (self.m - 1)))
        ee = float(np.sqrt(max(varianza, 0)))
        critico = float(student_t.ppf(0.975, df)) if df > 0 else None
        salida.update(estimacion=estimacion, ee=ee,
                      li95=estimacion-critico*ee if critico is not None else None,
                      ls95=estimacion+critico*ee if critico is not None else None,
                      cv=ee/abs(estimacion) if estimacion != 0 else None)
        return salida


def calidad_media(estadistico):
    """Criterios del texto del manual, p. 80, para medias monetarias.

    No se aplica esta clasificación a participaciones ni a razones de carga:
    estas requieren evaluar el criterio correspondiente a su tipo de estimador.
    """
    if estadistico["estimacion"] is None:
        return "Sin estimación"
    if estadistico["n"] < 60:
        return "No fiable: n < 60"
    if estadistico["gl"] < 9:
        return "No fiable: gl < 9"
    cv = estadistico["cv"]
    if cv is None:
        return "Sin clasificación: CV no definido"
    if cv <= 0.15:
        return "Fiable"
    if cv <= 0.30:
        return "Poco fiable: CV > 15%"
    return "No fiable: CV > 30%"


def calcular_resultados(hogares: pd.DataFrame, deciles: np.ndarray):
    """Calcula resultados para todos los hogares y para gastadores, sin requintilizar."""
    d = DisenoTaylor(hogares)
    ingreso = hogares.ing_disp_hog_hd.to_numpy(float)
    gas = hogares.gasolina.to_numpy(float)
    diesel = hogares.diesel.to_numpy(float)
    vectores = {"gasolina_diesel": gas + diesel, "gasolina": gas, "diesel": diesel}
    grupos = [("Total", "Total", np.ones(len(hogares)))]
    grupos += [("Quintil", str(i+1), deciles[:, i*2:i*2+2].sum(axis=1)) for i in range(5)]
    grupos += [("Decil", str(i+1), deciles[:, i]) for i in range(10)]
    resumen, precision = [], []
    for tipo, grupo, a in grupos:
        for combustible, gasto in vectores.items():
            # Cada combustible tiene su propio dominio; la unión se aplica una sola vez.
            gastador = gasto > 0
            b = a * gastador
            bp = b * (ingreso > 0)
            carga = np.divide(gasto, ingreso, out=np.zeros(len(ingreso)), where=ingreso > 0)
            medidas = {
                "participacion": d.razon(gastador.astype(float), pertenencia=a),
                "gasto_todos": d.razon(gasto, pertenencia=a),
                "gasto_gastadores": d.razon(gasto, pertenencia=b),
                "ingreso_gastadores": d.razon(ingreso, pertenencia=b),
                "carga_razon": d.razon(gasto, x=ingreso, pertenencia=bp),
                "carga_media": d.razon(carga, pertenencia=bp),
            }
            p25, p50, p75 = cuantiles_ponderados(carga, d.pesos * bp)
            registro = {"segmentacion": tipo, "grupo": grupo, "combustible": combustible,
                        "n_todos": int((a > 1e-12).sum()), "peso_todos": float(d.pesos @ a),
                        "n_gastadores": medidas["gasto_gastadores"]["n"],
                        "peso_gastadores": float(d.pesos @ b),
                        "n_ingreso_positivo": medidas["carga_media"]["n"],
                        "peso_ingreso_positivo": float(d.pesos @ bp),
                        "n_ingreso_no_positivo": int(((b > 1e-12) & (ingreso <= 0)).sum()),
                        "peso_ingreso_no_positivo": float(d.pesos @ (b * (ingreso <= 0))),
                        "p25_carga": p25, "mediana_carga": p50, "p75_carga": p75,
                        "calidad_gasto": calidad_media(medidas["gasto_gastadores"])}
            for nombre, stat in medidas.items():
                registro[nombre] = stat["estimacion"]
                registro[nombre+"_numerador"] = stat["numerador"]
                registro[nombre+"_denominador"] = stat["denominador"]
                precision.append({"segmentacion": tipo, "grupo": grupo, "combustible": combustible,
                                  "indicador": nombre, **stat,
                                  "clasificacion": calidad_media(stat) if nombre in ("gasto_todos", "gasto_gastadores", "ingreso_gastadores")
                                  else "Sin clasificación integral del estándar"})
            resumen.append(registro)
    return pd.DataFrame(resumen), pd.DataFrame(precision)
