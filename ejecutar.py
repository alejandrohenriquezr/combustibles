"""Entrada única: instala, verifica, prueba y ejecuta el análisis de combustibles."""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys

RAIZ = Path(__file__).resolve().parent
CODIGO = RAIZ / "Codigo"
sys.path.insert(0, str(CODIGO))


def cargar_instalador():
    spec = importlib.util.spec_from_file_location("instalador", CODIGO / "01_instalar_dependencias.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def preparar_configuracion():
    """Separa las referencias versionadas del estado que cambia al descargar."""
    for base, local in (("configuracion.base.json", "configuracion.json"),
                        ("gpp_fuentes.base.json", "gpp_fuentes.json")):
        destino = CODIGO / local
        if not destino.exists():
            shutil.copy2(CODIGO / base, destino)


def argumentos(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    modo = p.add_mutually_exclusive_group()
    modo.add_argument("--solo-instalar", action="store_true", help="Preparar Python y R, sin descargar datos ni calcular.")
    modo.add_argument("--verificar", action="store_true", help="Comprobar Python, paquetes y R; no instala ni descarga fuentes.")
    modo.add_argument("--pruebas", action="store_true", help="Ejecutar las pruebas; las auditorías de datos se omiten si no hay respaldo local.")
    modo.add_argument("--actualizar-web", action="store_true", help="Exportar un artículo Word ya generado a docs/; no publica en Internet.")
    p.add_argument("--instalar", action="store_true", help="Restaurar dependencias antes del modo elegido.")
    p.add_argument("--solo-r", action="store_true", help="Con --solo-instalar, restaurar solo los paquetes R.")
    p.add_argument("--sin-instalar", action="store_true", help="Usar el entorno disponible sin instalación automática.")
    p.add_argument("--rscript", help="Ruta explícita de Rscript 4.5.0.")
    p.add_argument("--indice", help="Índice HTTPS de pip opcional, sin credenciales.")
    p.add_argument("--reproducir-sin-actualizar", action="store_true", help="Recalcular con fuentes locales verificadas, sin actualizar precios.")
    p.add_argument("--datos", type=Path, default=CODIGO / "datos")
    p.add_argument("--salida", type=Path, default=CODIGO / "resultados")
    p.add_argument("--articulo", type=Path, help="Word que se exporta con --actualizar-web.")
    a = p.parse_args(argv)
    if a.instalar and a.sin_instalar:
        p.error("--instalar y --sin-instalar son excluyentes")
    if a.solo_r and not a.solo_instalar:
        p.error("--solo-r requiere --solo-instalar")
    if a.articulo and not a.actualizar_web:
        p.error("--articulo requiere --actualizar-web")
    if a.indice and not (a.instalar or a.solo_instalar):
        p.error("--indice requiere --instalar o --solo-instalar")
    if a.verificar and a.instalar:
        p.error("--verificar no instala; usar antes --solo-instalar")
    return a


def ejecutar(argv=None):
    a = argumentos(argv)
    os.environ["PYTHONUTF8"] = "1"
    if a.actualizar_web:
        from modulos.web import exportar_articulo
        articulo = a.articulo or a.salida / "Articulo_LinkedIn_combustibles_Chile_actualizado.docx"
        exportar_articulo(articulo.resolve(), RAIZ / "docs")
        print("Artículo web preparado en docs/index.html. Publicar los cambios con Git.")
        return 0

    instalador = cargar_instalador()
    instalador.comprobar_python(instalador.informacion_python(sys.executable))
    python = instalador.python_entorno(CODIGO)
    instalar = a.solo_instalar or a.instalar or (
        not python.is_file() and not a.sin_instalar and not a.verificar)
    if instalar:
        indice = instalador.indice_https(a.indice) if a.indice else None
        instalador.instalar(rscript=a.rscript, indice=indice, solo_r=a.solo_r)
    if a.solo_instalar:
        return 0
    # CI y entornos administrados pueden usar sus paquetes con --sin-instalar.
    if not python.is_file():
        if a.sin_instalar:
            python = Path(sys.executable)
        else:
            raise RuntimeError("Falta .venv. Ejecutar: python ejecutar.py --solo-instalar")
    instalador.comprobar_python(instalador.informacion_python(python), "El entorno de ejecución")
    env = os.environ.copy()
    # Cambiar de directorio no altera rutas: todos los argumentos son absolutos.
    if a.pruebas:
        prueba = [str(python), "-m", "unittest", "discover", "-s", "tests", "-v"]
        return subprocess.run(prueba, cwd=CODIGO, env=env).returncode

    prueba = ("import numpy,numpy.linalg,pandas,scipy,scipy.linalg,openpyxl,matplotlib,docx,lxml.etree,PIL; "
              "matplotlib.use('Agg'); import matplotlib.pyplot")
    subprocess.run([str(python), "-c", prueba], check=True, cwd=CODIGO, env=env)
    subprocess.run([str(python), "-m", "pip", "check"], check=True, cwd=CODIGO, env=env)
    if a.verificar:
        from modulos.entorno import localizar_rscript, comprobar_dependencias_r
        rscript = localizar_rscript(a.rscript)
        comprobar_dependencias_r(rscript, CODIGO)
        print("Python, paquetes y R verificados. No se descargaron fuentes ni se calcularon resultados.")
        return 0

    preparar_configuracion()
    opciones = ["--datos", str(a.datos.resolve()), "--salida", str(a.salida.resolve())]
    if a.rscript:
        opciones += ["--rscript", a.rscript]
    if a.reproducir_sin_actualizar:
        opciones += ["--reproducir-sin-actualizar"]
    # El flujo interno se importa desde el intérprete preparado, sin otra CLI pública.
    codigo = "import flujo; flujo.ejecutar(__import__('sys').argv[1:])"
    return subprocess.run([str(python), "-c", codigo, *opciones], cwd=CODIGO, env=env).returncode


if __name__ == "__main__":
    try:
        sys.exit(ejecutar())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, argparse.ArgumentTypeError) as exc:
        print("No se completó la operación:", exc, file=sys.stderr)
        sys.exit(1)
