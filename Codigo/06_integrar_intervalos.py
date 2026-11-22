"""Integra la razón de medianas estimada en R y verifica sus puntos en Python."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd
from modulos.entorno import localizar_rscript, comprobar_dependencias_r
from modulos.epf_calculos import medianas_de_gastadores


def integrar(salida,rscript=None):
    """Las dos medianas usan el mismo dominio con gasto positivo, incluido ingreso <=0."""
    raiz=Path(__file__).resolve().parent;env=os.environ.copy()
    # renv consulta la biblioteca del R seleccionado; no se elige el primer
    # directorio calidad encontrado entre instalaciones de distintas versiones.
    ejecutable=localizar_rscript(rscript)
    env['EPF_R_LIB']=comprobar_dependencias_r(ejecutable, raiz)
    subprocess.run([ejecutable,'--vanilla',str(raiz/'05_intervalos_calidad.R'),
                    str(salida/'hogares_procesados.csv'),str(salida)],check=True,env=env)
    archivo=salida/'resultados.json';anterior=json.loads(archivo.read_text(encoding='utf-8'))
    h=pd.read_csv(salida/'hogares_procesados.csv',dtype={'folio':str})
    resumen=pd.read_csv(salida/'medianas_resumen.csv',dtype={'grupo':str})
    precision=pd.read_csv(salida/'medianas_precision.csv',dtype={'grupo':str})
    contrastes=pd.read_csv(salida/'contrastes.csv',keep_default_na=False)
    covs=pd.read_csv(salida/'covarianzas.csv')
    # Recalcula ambas medianas de forma independiente; no usa cargas por hogar.
    for r in resumen.to_dict('records'):
        if r['segmentacion']=='Total':fr=np.ones(len(h))
        elif r['segmentacion']=='Quintil':
            q=int(r['grupo']);fr=(h[f'fraccion_decil_{2*q-1}']+h[f'fraccion_decil_{2*q}']).to_numpy()
        else:fr=h[f"fraccion_decil_{int(r['grupo'])}"].to_numpy()
        puntos=medianas_de_gastadores(h[r['combustible']],h.ing_disp_hog_hd,h.fe.to_numpy()*fr)
        for campo in ['gasto_mediano','ingreso_mediano','relacion_medianas']:
            a,b=puntos[campo],r[campo]
            if not np.isclose(a,b,rtol=1e-10,atol=1e-8):raise ArithmeticError('Las medianas R/Python no coinciden.')
        if puntos['n_gastadores']!=int(r['n_gastadores']):raise ArithmeticError('Dominio diferente en R y Python.')
    if len(resumen)!=48 or len(precision)!=144 or len(contrastes)!=30:raise ArithmeticError('Número inesperado de estimaciones o contrastes.')
    ady=contrastes[contrastes.adyacente.astype(str).str.lower().eq('true')]
    if len(ady)!=12:raise ArithmeticError('Se requieren cuatro pares adyacentes por cada uno de los tres indicadores.')
    for r in ady.to_dict('records'):
        if (r['marca_grafico']=='†')!=(float(r['p_holm_adyacentes'])>=.05):raise ArithmeticError('Marca de significancia incorrecta.')
    # Los IC son percentiles de las réplicas de la función completa; se conservan asimétricos.
    for r in precision.to_dict('records'):
        if any(not np.isfinite(r[k]) for k in ['estimacion','ee','li95','ls95']):raise ArithmeticError('IC no finito.')
        if r['li95']>r['ls95']:raise ArithmeticError('IC invertido.')
    def registros(df):return df.astype(object).where(pd.notna(df),None).to_dict('records')
    control=pd.read_csv(salida/'control_calidad.csv').iloc[0].to_dict()
    versiones=dict(pd.read_csv(salida/'versiones_R.csv').astype(str).itertuples(index=False,name=None))
    payload={k:anterior[k] for k in ['hogares_segmentados','diagnostico','clasificador','archivos']}
    payload.update(resumen=registros(resumen),precision=registros(precision),contrastes=registros(contrastes),
        covarianzas=registros(covs),calidad={'versiones':versiones,'nivel_confianza':.95,
        'control_ingreso':control,'indicador':'Gasto mediano / ingreso mediano de los mismos hogares con gasto positivo',
        'intervalos':'Bootstrap percentil conjunto, 1999 réplicas; cuantiles tipo 1; semilla 20261119',
        'evaluacion':'Criterios n/gl/CV de calidad, adaptación explícita a medianas y razón de medianas; no estimador nativo',
        'contrastes':'Wald t con covarianza bootstrap; Holm de 4 pares adyacentes por indicador',
        'cortes':'Cortes y factores finales fijos; no se recalibran ponderadores en cada réplica'})
    # Curva y contrastes conjuntos: el cero inicial es una identidad; no se
    # decide significancia a partir del solapamiento de sus bandas.
    curva=pd.read_csv(salida/'escenario_gpp_ic.csv',keep_default_na=False)
    pruebas=pd.read_csv(salida/'escenario_gpp_contrastes.csv',keep_default_na=False)
    local=pd.read_csv(raiz/'gpp_chile_clp.csv',keep_default_na=False)
    if len(curva)!=5*len(local) or len(pruebas)!=4*len(local):raise ArithmeticError('Cobertura incorrecta de la curva GPP.')
    if not np.isfinite(curva[['estimacion','ee','li95','ls95']].to_numpy(float)).all():raise ArithmeticError('IC GPP no finito.')
    if (curva.li95>curva.ls95).any():raise ArithmeticError('IC GPP invertido.')
    base=curva[curva.mes==local.mes.iloc[0]]
    if not (base[['estimacion','li95','ls95']]==0).all().all():raise ArithmeticError('La base debe ser exactamente cero.')
    payload['escenario_gpp']={'serie':registros(curva),'contrastes':registros(pruebas),
        'precios_clp':registros(local),'base':local.mes.iloc[0],
        'formula':'[mediana(gasolina_h * Pgas_t/Pgas_0 + diesel_h * Pdie_t/Pdie_0) - mediana(gasolina_h + diesel_h)] / mediana(ingreso_h)',
        'alcance':'Escenario EPF de referencia; no gasto ni ingreso observado en 2025–2026. IC condicionados a precios publicados; no incluyen error de precios.',
        'metodo':'Mismos hogares gastadores, ingresos <=0 conservados; mismo bootstrap conjunto; Holm de cuatro pares por mes.'}
    archivo.write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    resumen.to_csv(salida/'resumen.csv',index=False,encoding='utf-8-sig');precision.to_csv(salida/'precision.csv',index=False,encoding='utf-8-sig')
    print('Verificados 48 dominios: gasto e ingreso medianos del mismo conjunto; 144 IC y 30 contrastes.')
    return payload


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);raiz=Path(__file__).resolve().parent
    p.add_argument('--salida',type=Path,default=raiz/'resultados');p.add_argument('--rscript')
    a=p.parse_args();integrar(a.salida.resolve(),a.rscript)
