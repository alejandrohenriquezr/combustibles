"""Empaqueta productos, código, configuración y fuentes públicas almacenadas."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import zipfile


def empaquetar(raiz,resultados,destino,datos=None):
    """Incluye los insumos originales; excluye entornos, cachés y salidas viejas."""
    raiz,resultados,destino=map(Path,[raiz,resultados,destino]);datos=Path(datos) if datos else raiz/'datos'
    requeridos=['Articulo_LinkedIn_combustibles_Chile_actualizado.docx','Respaldo_combustibles_EPF_GPP.xlsx',
                'IX_EPF_combustibles_hogares_con_gasto.xlsx','resultados.json','actualizacion_fuentes.json']
    if any(not (resultados/p).exists() for p in requeridos):raise FileNotFoundError('El flujo no terminó: faltan productos finales.')
    items=[]
    for name in requeridos[:3]:items.append((resultados/name,name))
    for p in resultados.rglob('*'):
        if not p.is_file() or p.name in requeridos[:3]:continue
        if p.suffix in ('.csv','.json','.txt','.png','.svg'):items.append((p,'Resultados/'+p.relative_to(resultados).as_posix()))
    # Todo el código entregado se encuentra en una carpeta única reproducible.
    def codigo_publicable():
        # Se podan los entornos antes de recorrerlos; no se inspeccionan miles
        # de paquetes restaurables en una carpeta sincronizada.
        excluir={'datos','resultados','resultados_anteriores','diagnosticos','.venv','.git',
                 '__pycache__','tests_cache','library','bootstrap','staging','cache','.pytest_cache'}
        for carpeta,subcarpetas,archivos in os.walk(raiz):
            subcarpetas[:]=[d for d in subcarpetas if d not in excluir and
                            not d.startswith('.resultados_en_proceso_') and
                            not (Path(carpeta)/d).is_relative_to(resultados) and
                            not (Path(carpeta)/d).is_relative_to(datos)]
            for nombre in archivos:yield Path(carpeta)/nombre

    for p in codigo_publicable():
        rel=p.relative_to(raiz)
        if p.is_relative_to(resultados) or p.is_relative_to(datos):continue
        if rel.parts[0].startswith('.resultados_en_proceso_'):continue
        if rel.parts[0] in ['datos','resultados','resultados_anteriores','diagnosticos','.venv','.git','__pycache__','tests_cache']:continue
        if any(v in rel.parts for v in ['library','bootstrap','staging','cache','__pycache__','.pytest_cache']):continue
        if p.suffix in ['.py','.R','.json','.csv','.txt','.md','.lock','.docx'] or p.name in ['.gitignore','.Rprofile','DESCRIPTION']:
            items.append((p,'Codigo/'+rel.as_posix()))
    # Las fuentes se incluyen también en Codigo/datos: al descomprimir se puede
    # ejecutar una reproducción sin moverlas. El modo normal siempre las consulta.
    for p in datos.rglob('*'):
        if p.is_file() and p.suffix!='.part':items.append((p,'Codigo/datos/'+p.relative_to(datos).as_posix()))
    # La copia clonable conserva también su entrada única y documentación.
    proyecto=raiz.parent
    for nombre in ['ejecutar.py','README.md','CHANGELOG.md','.gitignore','.gitattributes']:
        p=proyecto/nombre
        if p.is_file():items.append((p,nombre))
    for nombre in ['documentacion','.github']:
        for p in (proyecto/nombre).rglob('*'):
            if p.is_file():items.append((p,p.relative_to(proyecto).as_posix()))
    # La web de ESTA ejecución está dentro de resultados/web, no en docs viejo.
    for p in (resultados/'web').rglob('*'):
        if p.is_file():items.append((p,'docs/'+p.relative_to(resultados/'web').as_posix()))
    css=proyecto/'docs/estilos.css'
    if css.is_file():items.append((css,'docs/estilos.css'))
    manifiesto=[]
    for p,nombre in items:
        with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        manifiesto.append({'archivo':nombre,'bytes':p.stat().st_size,'sha256':digest})
    destino.parent.mkdir(parents=True,exist_ok=True);temporal=destino.with_suffix('.zip.part')
    with zipfile.ZipFile(temporal,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p,nombre in items:z.write(p,nombre)
        z.writestr('MANIFIESTO_PAQUETE.json',json.dumps(manifiesto,ensure_ascii=False,indent=2))
    temporal.replace(destino);print('Paquete completo:',destino,flush=True)
    return destino


if __name__=='__main__':
    raiz=Path(__file__).resolve().parent;p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--resultados',type=Path,default=raiz/'resultados')
    p.add_argument('--zip',type=Path,default=raiz.parent/'Paquete_combustibles_EPF_GPP_actualizado.zip')
    p.add_argument('--datos',type=Path,default=raiz/'datos');a=p.parse_args()
    empaquetar(raiz,a.resultados.resolve(),a.zip.resolve(),a.datos.resolve())
