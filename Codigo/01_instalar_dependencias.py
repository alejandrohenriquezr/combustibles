"""Prepara Python y R usando paquetes Python precompilados y el renv.lock.

Windows: py -3.12 01_instalar_dependencias.py
Diagnóstico sin instalar: py -3.12 01_instalar_dependencias.py --diagnostico
Índice explícito opcional: --indice https://pypi.org/simple
R requerido por este bloqueo: 4.5.0. Se valida antes de instalar paquetes.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
import venv

from modulos.entorno import localizar_rscript, comprobar_dependencias_r


def ambiente():
    """UTF-8 se hereda solo en los procesos del proyecto; no cambia Windows."""
    env=os.environ.copy();env['PYTHONUTF8']='1'
    return env


def python_entorno(raiz):
    """Localiza el intérprete del proyecto sin activar scripts de PowerShell."""
    return Path(raiz)/'.venv'/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')


def informacion_python(python):
    """Consulta el intérprete que realmente instalará y ejecutará los paquetes."""
    codigo=("import json,platform,struct,sys,sysconfig; "
      "print(json.dumps({'version':list(sys.version_info[:3]),"
      "'implementacion':platform.python_implementation(),'bits':struct.calcsize('P')*8,"
      "'plataforma':sysconfig.get_platform(),'maquina':platform.machine()}))")
    r=subprocess.run([str(python),'-c',codigo],check=True,capture_output=True,
                     text=True,encoding='utf-8',errors='replace',env=ambiente())
    return json.loads(r.stdout)


def comprobar_python(info, nombre="Python"):
    """Evita reutilizar por error un entorno creado con otra versión de Python."""
    if info['version'][:2]!=[3,12] or info['implementacion']!='CPython' or info['bits']!=64:
        actual='.'.join(map(str, info['version']))
        raise ValueError(f"{nombre} utiliza {info['implementacion']} {actual} de {info['bits']} bits. "
                         'Se requiere CPython 3.12 de 64 bits.')


def opciones_pip_sin_secretos(salida):
    """Conserva preferencias útiles y solo HOSTS de índices, sin claves ni rutas."""
    opciones={};hosts=set()
    permitidas={'no-binary','only-binary','no-index','platform','python-version','implementation','abi'}
    for linea in salida.splitlines():
        if '=' not in linea:continue
        clave,valor=linea.split('=',1);clave=clave.strip();valor=valor.strip().strip("'\"")
        nombre=clave.rsplit('.',1)[-1].lower()
        if nombre in permitidas:opciones[clave]=valor[:200]
        elif nombre in {'index-url','extra-index-url'}:
            for url in valor.split():
                try:
                    host=urlsplit(url).hostname
                    if host:hosts.add(host)
                except ValueError:pass
    return {'preferencias_binarios_y_plataforma':opciones,'hosts_indices':sorted(hosts)}


def diagnosticar(raiz,python,indice=None):
    """Genera un diagnóstico local sin instalar y sin copiar URLs con credenciales."""
    info=informacion_python(python)
    r=subprocess.run([str(python),'-m','pip','config','list'],capture_output=True,
                     text=True,encoding='utf-8',errors='replace',env=ambiente())
    datos={'python':info,**opciones_pip_sin_secretos(r.stdout),
      'indice_explicito_host':urlsplit(indice).hostname if indice else None,
      'modo_instalacion':'Solo wheels; sin compilar paquetes Python',
      'nota':'Si el índice ofrece solo fuentes, se necesita un wheel compatible en un índice accesible y autorizado.'}
    carpeta=Path(raiz)/'diagnosticos';carpeta.mkdir(exist_ok=True)
    destino=carpeta/'diagnostico_instalacion.json'
    destino.write_text(json.dumps(datos,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(datos,ensure_ascii=False,indent=2));print('Diagnóstico guardado:',destino)
    return datos


def comando_instalacion(python,raiz,indice=None):
    """Prohíbe la compilación accidental y conserva el índice configurado por defecto."""
    args=[str(python),'-m','pip','install','--only-binary=:all:','--no-cache-dir']
    if indice:args+=['--index-url',indice]
    return args+['-r',str(Path(raiz)/'requisitos.txt')]


def indice_https(valor):
    """El índice opcional debe ser HTTPS; las credenciales se configuran en pip."""
    p=urlsplit(valor)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment:
        raise argparse.ArgumentTypeError('Usar un índice HTTPS sin usuario, contraseña ni parámetros secretos en la URL.')
    return valor


def instalar(rscript=None,solo_r=False,indice=None,diagnostico=False):
    """Restaura dependencias sin borrar el entorno existente ni modificar pip global."""
    raiz=Path(__file__).resolve().parent;python=python_entorno(raiz)
    if diagnostico:
        return diagnosticar(raiz,python if python.exists() else sys.executable,indice)
    comprobar_python(informacion_python(sys.executable), 'El intérprete que ejecuta el instalador')
    # Se selecciona y valida R antes de instalar paquetes o empezar descargas.
    ejecutable_r=localizar_rscript(rscript)
    print('R seleccionado:', ejecutable_r, flush=True)
    if not solo_r:
        destino=raiz/'.venv'
        if not destino.exists():venv.EnvBuilder(with_pip=True).create(destino)
        if not python.is_file():raise ValueError('El entorno .venv está incompleto; debe contener su ejecutable Python.')
        comprobar_python(informacion_python(python), 'El entorno .venv')
        print('Instalando únicamente paquetes Python precompilados; se conserva la configuración de índice salvo --indice.',flush=True)
        r=subprocess.run(comando_instalacion(python,raiz,indice),env=ambiente())
        if r.returncode:
            diagnosticar(raiz,python,indice)
            raise RuntimeError('La instalación Python no terminó. No se intentó compilar. Revisar el error de pip y diagnosticos/diagnostico_instalacion.json; comprobar acceso a wheels compatibles.')
        # Se comprueban dependencias y carga de módulos, incluidos binarios nativos.
        subprocess.run([str(python),'-m','pip','check'],check=True,env=ambiente())
        prueba=('import numpy,numpy.linalg,pandas,scipy,scipy.linalg,openpyxl,matplotlib,docx,lxml.etree,PIL; '
                'matplotlib.use("Agg"); import matplotlib.pyplot; '
                'print("Paquetes Python importados correctamente.")')
        subprocess.run([str(python),'-c',prueba],check=True,env=ambiente())
    # R usa su restauración propia y sus herramientas; no se mezcla con pip.
    subprocess.run([ejecutable_r,'--vanilla',str(raiz/'02_instalar_paquetes.R'),str(raiz)],check=True,env=ambiente())
    comprobar_dependencias_r(ejecutable_r, raiz)
    print('Dependencias listas. Ejecutar python ejecutar.py desde la raíz del repositorio.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version',action='version',version='Instalador 2026-11-22b: Python 3.12; R 4.5.0; verificación desde archivo R')
    p.add_argument('--rscript',help='Ruta de Rscript.exe si no está en PATH.')
    p.add_argument('--solo-r',action='store_true',help='Restaurar solo paquetes R; Python debe estar preparado.')
    p.add_argument('--indice',type=indice_https,help='Índice explícito opcional. Sin esta opción se conserva el configurado en pip.')
    p.add_argument('--diagnostico',action='store_true',help='Mostrar y guardar diagnóstico sin instalar paquetes ni ejecutar R.')
    a=p.parse_args()
    try:instalar(a.rscript,a.solo_r,a.indice,a.diagnostico)
    except (ValueError,RuntimeError,FileNotFoundError,subprocess.SubprocessError) as exc:
        print('No se completó la preparación:',str(exc),file=sys.stderr);sys.exit(1)
