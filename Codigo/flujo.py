"""Coordina descarga, cálculo, intervalos reales con calidad y Excel con gráficos e IC."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
from modulos.entorno import localizar_rscript, comprobar_dependencias_r


def ejecutar(argv=None):
    """Usa el mismo intérprete Python en todos los pasos y conserva los errores."""
    raiz = Path(__file__).resolve().parent
    # Cada proceso Python del flujo lee JSON/CSV UTF-8 también en Windows.
    os.environ['PYTHONUTF8']='1'
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reproducir-sin-actualizar", action="store_true", help="Reproducción explícita del respaldo almacenado; NO se presenta como actualización.")
    p.add_argument("--datos", type=Path, default=raiz/"datos")
    p.add_argument("--salida", type=Path, default=raiz/"resultados")
    p.add_argument("--rscript", help="Ruta explícita de Rscript o Rscript.exe.")
    p.add_argument("--instalar", action="store_true", help="Restaurar dependencias R antes del cálculo; Python debe estar preparado.")
    a = p.parse_args(argv)
    datos, destino = a.datos.resolve(), a.salida.resolve()
    sello=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    salida=destino.parent/('.resultados_en_proceso_'+sello)

    # La instalación inicial completa se realiza con 01_instalar_dependencias.py.
    r_opcion = ["--rscript", a.rscript] if a.rscript else []
    if a.instalar:
        subprocess.run([sys.executable, str(raiz/"01_instalar_dependencias.py"), "--solo-r", *r_opcion], check=True)

    # El flujo no consulta fuentes ni recalcula hogares si el R y la biblioteca
    # fijados por renv.lock no están listos. Todos los pasos reciben el mismo R.
    ejecutable_r=localizar_rscript(a.rscript)
    biblioteca=comprobar_dependencias_r(ejecutable_r, raiz)
    os.environ['RSCRIPT']=ejecutable_r
    os.environ['EPF_R_LIB']=biblioteca
    r_opcion=["--rscript", ejecutable_r]
    print('Entorno R verificado:', ejecutable_r, flush=True)

    # La llamada con lista de argumentos conserva correctamente rutas con espacios.
    if not a.reproducir_sin_actualizar:
        subprocess.run([sys.executable, str(raiz/"03_descargar_fuentes.py"), "--datos", str(datos)], check=True)
    comprobante=raiz/'actualizacion_fuentes.json'
    if not comprobante.exists():raise RuntimeError('No existe comprobante de fuentes. Ejecutar 03_descargar_fuentes.py.')
    manifiesto=json.loads(comprobante.read_text())
    if not manifiesto.get('actualizacion_completa'):raise RuntimeError('La actualización de fuentes no terminó correctamente.')
    cfg=json.loads((raiz/'configuracion.json').read_text())
    if (cfg['gpp']['sha256']!=manifiesto['gpp'].get('sha256_precios') or
        cfg['gpp']['clp']['sha256']!=manifiesto['gpp'].get('sha256_clp')):
        raise RuntimeError('Los datos no pertenecen al comprobante completo. Ejecutar de nuevo la actualización de fuentes.')
    salida.mkdir(parents=True,exist_ok=False)
    shutil.copy2(comprobante,salida/'actualizacion_fuentes.json')
    subprocess.run([sys.executable, str(raiz/"04_recalcular_combustibles.py"), "--datos", str(datos), "--salida", str(salida)], check=True)
    subprocess.run([sys.executable, str(raiz/"06_integrar_intervalos.py"), "--salida", str(salida), *r_opcion], check=True)
    subprocess.run([sys.executable, str(raiz/"07_exportar_excel.py"), "--resultados", str(salida/"resultados.json"),
                    "--excel", str(salida/"IX_EPF_combustibles_hogares_con_gasto.xlsx")], check=True)
    # Los dos últimos pasos completan el respaldo GPP y el Word con los mismos datos.
    subprocess.run([sys.executable,str(raiz/"09_respaldo_epf_gpp.py"),"--resultados",str(salida/"resultados.json"),
                    "--excel",str(salida/"Respaldo_combustibles_EPF_GPP.xlsx")],check=True)
    subprocess.run([sys.executable,str(raiz/"10_articulo_linkedin.py"),"--resultados",str(salida/"resultados.json"),
                    "--word",str(salida/"Articulo_LinkedIn_combustibles_Chile_actualizado.docx")],check=True)
    # Se prepara la web en la salida temporal. No se publica automáticamente en GitHub.
    from modulos.web import exportar_articulo, instalar_web
    exportar_articulo(salida/'Articulo_LinkedIn_combustibles_Chile_actualizado.docx',salida/'web')
    # Se publica la carpeta completa solo cuando todos los cálculos y productos
    # finalizaron. La salida anterior se conserva para poder comparar versiones.
    anterior=None
    if destino.exists():
        anterior=destino.parent/'resultados_anteriores'/sello
        anterior.parent.mkdir(parents=True,exist_ok=True);destino.rename(anterior)
    salida.rename(destino)
    try:
        subprocess.run([sys.executable,str(raiz/'11_empaquetar.py'),'--resultados',str(destino),'--datos',str(datos)],check=True)
    except BaseException:
        # Un fallo al empaquetar también conserva la salida anterior como principal.
        destino.rename(salida)
        if anterior is not None:anterior.rename(destino)
        raise
    instalar_web(destino/'web',raiz.parent/'docs')
    print('Word, Excel, gráficos, fuentes y código publicados tras completar el flujo.',flush=True)


# La única entrada del flujo completo es ../ejecutar.py.
