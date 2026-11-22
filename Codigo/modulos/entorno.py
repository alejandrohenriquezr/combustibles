"""Selecciona el R de renv.lock y verifica su biblioteca antes de calcular."""
import json
import datetime as dt
import os
from pathlib import Path
import re
import shutil
import subprocess


def version_r_requerida(raiz=None):
    """La versión de referencia se lee del bloqueo, sin cambiar sus paquetes."""
    raiz = Path(raiz) if raiz else Path(__file__).resolve().parents[1]
    return json.loads((raiz / "renv.lock").read_text(encoding="utf-8"))["R"]["Version"]


def version_rscript(ejecutable):
    """Consulta R sin perfiles del usuario ni activación de otros proyectos."""
    r = subprocess.run([str(ejecutable), "--vanilla", "-e", "cat(as.character(getRversion()))"],
                       check=True, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=30)
    version = r.stdout.strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise RuntimeError(f"No se pudo identificar la versión de R en {ejecutable}.")
    return version


def comprobar_version_rscript(ejecutable, requerida=None):
    """Explica qué ejecutable es incompatible antes de descargar o compilar."""
    requerida = requerida or version_r_requerida()
    actual = version_rscript(ejecutable)
    if actual != requerida:
        raise RuntimeError(
            f"R incompatible: {ejecutable} utiliza R {actual}; renv.lock requiere R {requerida}. "
            f"Instalar R {requerida} desde https://cran.r-project.org/bin/windows/base/old/{requerida}/ "
            "y seleccionar su Rscript con --rscript o RSCRIPT. No se cambió el archivo de bloqueo.")
    return actual


def localizar_rscript(explicito=None):
    """Respeta una selección explícita; en modo automático busca la versión fijada."""
    requerida = version_r_requerida()
    elegido = explicito or os.getenv("RSCRIPT")
    if elegido:
        # Una ruta indicada por el usuario se valida, nunca se sustituye en silencio.
        p = Path(elegido)
        if not p.is_file():
            raise FileNotFoundError(f"Rscript no encontrado en la ruta indicada: {p}")
        comprobar_version_rscript(p, requerida)
        return str(p.resolve())
    opciones = [Path(p)] if (p := shutil.which("Rscript")) else []
    # Se incluyen instalaciones paralelas del sistema y del usuario de Windows.
    for base in (os.getenv("ProgramFiles"), os.getenv("LOCALAPPDATA")):
        if base:
            opciones.extend(Path(base).glob("R/R-*/bin/Rscript.exe"))
            opciones.extend(Path(base).glob("Programs/R/R-*/bin/Rscript.exe"))
    vistos = set(); encontrados = []
    for p in opciones:
        if not p.is_file() or p.resolve() in vistos:
            continue
        vistos.add(p.resolve())
        try:
            actual = version_rscript(p)
        except (OSError, RuntimeError, subprocess.SubprocessError):
            encontrados.append(f"{p}: no se pudo consultar")
            continue
        if actual == requerida:
            return str(p.resolve())
        encontrados.append(f"{p}: R {actual}")
    detalle = "; ".join(encontrados) or "no se encontró Rscript"
    raise FileNotFoundError(
        f"No se encontró R {requerida}, requerido por renv.lock ({detalle}). "
        f"Descarga: https://cran.r-project.org/bin/windows/base/old/{requerida}/. "
        "Instalarlo en paralelo y usar --rscript o RSCRIPT si está en otra carpeta.")


def comprobar_dependencias_r(ejecutable, raiz=None):
    """Ejecuta un archivo R y conserva salida, errores y código de terminación."""
    raiz = Path(raiz) if raiz else Path(__file__).resolve().parents[1]
    script = Path(__file__).resolve().parents[1] / "12_verificar_entorno.R"
    comando = [str(ejecutable), "--vanilla", str(script), str(raiz)]
    carpeta = raiz / "diagnosticos"
    carpeta.mkdir(parents=True, exist_ok=True)
    registro = carpeta / "verificacion_R.log"

    def guardar(codigo, salida="", errores=""):
        # El registro local no contiene URLs autenticadas y se excluye de los ZIP.
        contenido = ("Verificación R: " + dt.datetime.now(dt.timezone.utc).isoformat() + "\n"
                     + "Ejecutable: " + str(ejecutable) + "\n"
                     + "Código de salida: " + str(codigo) + "\n"
                     + "SALIDA ESTÁNDAR\n" + salida + "\nERRORES\n" + errores + "\n")
        registro.write_text(contenido, encoding="utf-8")

    # Un archivo evita pasar expresiones multilínea como argumentos de Windows.
    # Se conserva el mismo R y todos los controles de versiones y carga.
    try:
        r = subprocess.run(comando, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        guardar("proceso no completado", errores=str(exc))
        raise RuntimeError(f"No se pudo completar la verificación R. Detalle: {registro}") from exc
    guardar(r.returncode, r.stdout or "", r.stderr or "")
    if r.returncode:
        # Incluso un fallo nativo sin texto conserva el código y la última etapa.
        partes = [s.strip() for s in [r.stdout, r.stderr] if s and s.strip()]
        detalle = "\n".join(partes)[-3000:] or "R terminó sin emitir salida ni errores."
        hexadecimal = f"0x{r.returncode & 0xffffffff:08X}"
        raise RuntimeError(f"Falló la verificación R (salida {r.returncode}; {hexadecimal}). "
                           f"{detalle}\nRegistro completo: {registro}")
    lineas = [s[len("EPF_R_LIB="):].strip() for s in (r.stdout or "").splitlines()
              if s.startswith("EPF_R_LIB=")]
    if len(lineas) != 1 or not Path(lineas[0]).is_dir():
        raise RuntimeError(f"R no devolvió una biblioteca válida para el proyecto. Detalle: {registro}")
    return lineas[0]
