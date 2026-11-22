"""Actualiza y almacena fuentes originales ANTES de calcular resultados.

GPP: páginas vigentes y reconstrucción pública histórica, enero 2025 en adelante.
INE: GET condicional a las fuentes oficiales; ninguna omisión de la descarga se
confunde con actualización. WEO: edición oficial configurada para el factor PPA.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import email.utils
import hashlib
import json
from pathlib import Path
import shutil
import urllib.error
from urllib.request import Request,urlopen
from modulos.fuentes_gpp import actualizar,guardar_json
from modulos.ppa import extraer_factores


def huella(archivo):
    """Lee por bloques para verificar también las fuentes de gran tamaño."""
    with Path(archivo).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def descargar(fuente,datos):
    """Consulta el servidor original en cada ejecución y preserva revisiones."""
    destino=datos/fuente['archivo'];headers={'User-Agent':'EPF-GPP-investigacion-reproducible/2.0',
                                           'Accept-Encoding':'identity'}
    anterior=None
    if destino.exists():
        anterior=huella(destino)
        if anterior!=fuente['sha256']:raise ValueError('Fuente local modificada: '+str(destino))
        headers['If-Modified-Since']=email.utils.formatdate(destino.stat().st_mtime,usegmt=True)
    req=Request(fuente['url'],headers=headers)
    consulta=dt.datetime.now(dt.timezone.utc).isoformat();parcial=destino.with_suffix(destino.suffix+'.part')
    try:
        with urlopen(req,timeout=60) as response:
            meta_http={k:response.headers.get(k) for k in ['ETag','Last-Modified','Content-Type']}
            with parcial.open('wb') as f:
                while bloque:=response.read(1024*1024):f.write(bloque)
    except urllib.error.HTTPError as exc:
        if exc.code==304 and anterior:
            return {**fuente,'sha256':anterior,'estado':'Servidor original: HTTP 304, sin cambios',
                    'consulta_utc':consulta}
        raise
    # Se rechazan pantallas HTML de error o de inicio de sesión con HTTP 200.
    with parcial.open('rb') as f:head=f.read(256).lstrip(b'\xef\xbb\xbf')
    if destino.suffix=='.xlsx' and not head.startswith(b'PK'):raise ValueError('Respuesta XLSX inválida: '+fuente['archivo'])
    if destino.suffix=='.csv' and not head.startswith(b'"'):raise ValueError('Respuesta CSV inválida: '+fuente['archivo'])
    digest=huella(parcial)
    if anterior and digest!=anterior:
        carpeta=datos/'originales/revisiones';carpeta.mkdir(parents=True,exist_ok=True)
        shutil.copy2(destino,carpeta/(anterior+destino.suffix))
    parcial.replace(destino)
    return {**fuente,'bytes':destino.stat().st_size,'sha256':digest,'consulta_utc':consulta,
            'estado':'Consultado y descargado del servidor original','cabeceras_http':meta_http,
            'revision':bool(anterior and digest!=anterior)}


def ejecutar(configuracion,datos):
    """Una falla de actualización detiene el flujo antes de crear productos."""
    raiz=configuracion.parent;datos.mkdir(parents=True,exist_ok=True)
    informe=actualizar(raiz,datos)
    cfg=json.loads(configuracion.read_text(encoding='utf-8'))
    entradas=cfg['archivos']+[cfg['ppa']['fuente']]
    with ThreadPoolExecutor(max_workers=3) as pool:registros=list(pool.map(lambda s:descargar(s,datos),entradas))
    cfg['archivos']=[{k:v for k,v in r.items() if k not in ['estado','consulta_utc','cabeceras_http','revision']} for r in registros[:-1]]
    weo=registros[-1];cfg['ppa']['fuente'].update(bytes=weo['bytes'],sha256=weo['sha256'])
    guardar_json(configuracion,cfg)
    # Los factores se extraen de nuevo del WEO descargado; no del CSV incluido.
    extraer_factores(datos/weo['archivo'],raiz)
    cfg['ppa']['sha256']=huella(raiz/cfg['ppa']['archivo'])
    cfg['consulta']=dt.datetime.now(dt.timezone.utc).date().isoformat()
    guardar_json(configuracion,cfg)
    manifiesto={'consulta_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'archivos':registros,'gpp':informe,'actualizacion_completa':True,
        'alcance_weo':'Edición oficial configurada; no se cambia de edición sin registrar URL y metadatos.'}
    guardar_json(datos/'manifiesto_descarga.json',manifiesto)
    guardar_json(raiz/'actualizacion_fuentes.json',manifiesto)
    print('Fuentes actualizadas y almacenadas. Inicio de los cálculos.',flush=True)


if __name__=='__main__':
    raiz=Path(__file__).resolve().parent;p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=raiz/'configuracion.json')
    p.add_argument('--datos',type=Path,default=raiz/'datos');a=p.parse_args()
    ejecutar(a.config.resolve(),a.datos.resolve())
