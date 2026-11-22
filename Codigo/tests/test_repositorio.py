"""Controles de publicación: enlaces locales, archivos rastreados e ignore."""
from html.parser import HTMLParser
from pathlib import Path
import os
import subprocess
import unittest
from urllib.parse import unquote, urlsplit

RAIZ = Path(__file__).resolve().parents[2]


def ambiente_git():
    # Los tests del entorno R simulan variables de Windows. No dependemos de
    # configuraciones Git inyectadas por el proceso que ejecuta la suite.
    return {k:v for k,v in os.environ.items() if k != 'GIT_CONFIG_COUNT' and
            not k.startswith(('GIT_CONFIG_KEY_', 'GIT_CONFIG_VALUE_'))}


class Enlaces(HTMLParser):
    def __init__(self):
        super().__init__()
        self.enlaces, self.ids, self.imagenes = [], set(), []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        for nombre in ("href", "src"):
            if nombre in a:
                self.enlaces.append(a[nombre])
        if tag == "img":
            self.imagenes.append(a)


class Repositorio(unittest.TestCase):
    def test_web_tiene_todos_los_enlaces_y_graficos_locales(self):
        p = Enlaces()
        p.feed((RAIZ / "docs/index.html").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(p.imagenes), 6)
        for imagen in p.imagenes:
            self.assertTrue(imagen.get("alt"), "Cada gráfico necesita descripción")
        for url in p.enlaces:
            r = urlsplit(url)
            if r.scheme or r.netloc:
                continue
            if r.path:
                archivo = (RAIZ / "docs" / unquote(r.path)).resolve()
                self.assertTrue(archivo.is_relative_to(RAIZ / "docs"))
                self.assertTrue(archivo.exists(), url)
            elif r.fragment:
                self.assertIn(r.fragment, p.ids)

    @unittest.skipUnless((RAIZ / ".git").exists(), "Requiere repositorio Git inicializado")
    def test_no_se_versionan_bases_salidas_o_entornos(self):
        archivos = subprocess.check_output(["git", "ls-files", "-z"], cwd=RAIZ, env=ambiente_git()).decode().split("\0")
        prohibidas = {".csv", ".tsv", ".xlsx", ".xls", ".parquet", ".feather", ".db", ".sqlite", ".sqlite3", ".duckdb", ".rds", ".rda", ".rdata", ".zip", ".dta", ".sav", ".sas7bdat", ".fst", ".h5", ".hdf5"}
        carpetas = {"datos", "data", "resultados", "resultados_anteriores", ".venv", ".archivo_local", "diagnosticos", "__pycache__", "library", "bootstrap", "staging", "cache"}
        for archivo in filter(None, archivos):
            p = Path(archivo)
            self.assertNotIn(p.suffix.lower(), prohibidas, archivo)
            self.assertFalse(carpetas.intersection(s.lower() for s in p.parts), archivo)
            if p.suffix == ".docx":
                self.assertEqual(p.as_posix(), "Codigo/plantillas/articulo_base.docx")

    @unittest.skipUnless((RAIZ / ".git").exists(), "Requiere repositorio Git inicializado")
    def test_ignore_cubre_bases_y_temporales_pero_permite_la_web(self):
        excluir = ["personas.csv", "otra/base.sqlite3", "Codigo/datos/originales/a.html",
                   "Codigo/gpp_precios.csv", "Codigo/configuracion.json", "Codigo/gpp_fuentes.json",
                   "Codigo/actualizacion_fuentes.json", "Codigo/resultados/resultados.json",
                   "Codigo/.venv/Scripts/python.exe", "Codigo/renv/library/survey/DESCRIPTION",
                   "Codigo/.resultados_en_proceso_123/a.json", "Codigo/diagnosticos/error.log",
                   "salida.xlsx", "respaldo.zip", ".archivo_local/archivo.txt"]
        for archivo in excluir:
            resultado = subprocess.run(["git", "check-ignore", "--no-index", "-q", archivo], cwd=RAIZ, env=ambiente_git())
            self.assertEqual(resultado.returncode, 0, archivo)
        for archivo in ["ejecutar.py", "Codigo/configuracion.base.json", "Codigo/gpp_fuentes.base.json",
                        "Codigo/plantillas/articulo_base.docx", "Codigo/renv.lock", "Codigo/renv/activate.R",
                        "docs/index.html", "docs/assets/grafico-1.png"]:
            resultado = subprocess.run(["git", "check-ignore", "--no-index", "-q", archivo], cwd=RAIZ, env=ambiente_git())
            self.assertEqual(resultado.returncode, 1, archivo)
