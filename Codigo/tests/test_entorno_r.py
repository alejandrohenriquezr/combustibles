"""Verifica la selección de R y la detención temprana sin necesitar R en el host."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modulos import entorno


class EntornoR(unittest.TestCase):
    def test_bloqueo_y_guardas_r_conservan_la_misma_version(self):
        # Las guardas de entrada de los scripts R corresponden al bloqueo entregado.
        self.assertEqual(entorno.version_r_requerida(), "4.5.0")
        for archivo in ("02_instalar_paquetes.R", "05_intervalos_calidad.R"):
            self.assertIn('"4.5.0"', (ROOT / archivo).read_text(encoding="utf-8"))

    def test_r_46_se_rechaza_con_versiones_y_ruta(self):
        # El error explica cuál R fue rechazado y no propone actualizar paquetes.
        with patch.object(entorno, "version_rscript", return_value="4.6.2"):
            with self.assertRaisesRegex(RuntimeError, r"4\.6\.2.*4\.5\.0"):
                entorno.comprobar_version_rscript("R-4.6.2/bin/Rscript.exe")

    def test_busqueda_automatica_prefiere_r_del_bloqueo_ante_r_46_en_path(self):
        # Una instalación paralela del usuario se encuentra aunque PATH conserve R 4.6.
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            viejo = base / "PATH/Rscript.exe"
            bueno = base / "Programs/R/R-4.5.0/bin/Rscript.exe"
            for p in (viejo, bueno):
                p.parent.mkdir(parents=True, exist_ok=True); p.touch()
            def version(p):
                return "4.5.0" if Path(p) == bueno else "4.6.2"
            with patch.dict(os.environ, {"LOCALAPPDATA": d}, clear=True), \
                 patch.object(entorno.shutil, "which", return_value=str(viejo)), \
                 patch.object(entorno, "version_rscript", side_effect=version):
                self.assertEqual(entorno.localizar_rscript(), str(bueno.resolve()))

    def test_ruta_explicita_incompatible_no_se_sustituye(self):
        # La selección del usuario prevalece; un error no provoca cambiar de R en silencio.
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "Rscript.exe"; p.touch()
            with patch.object(entorno, "version_rscript", return_value="4.6.2"):
                with self.assertRaisesRegex(RuntimeError, "R incompatible"):
                    entorno.localizar_rscript(p)

    def test_rscript_de_variable_de_sesion_tambien_se_valida(self):
        # Se detecta la variable RSCRIPT que pudo quedar apuntando a R 4.6.2.
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "Rscript.exe"; p.touch()
            with patch.dict(os.environ, {"RSCRIPT": str(p)}), \
                 patch.object(entorno, "version_rscript", return_value="4.6.2"):
                with self.assertRaisesRegex(RuntimeError, "R incompatible"):
                    entorno.localizar_rscript()

    def test_windows_recibe_un_archivo_y_argumentos_separados(self):
        # La llamada no contiene expresiones multilínea ni convierte la ruta en código R.
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.CompletedProcess([], 0, "EPF_R_LIB=" + d + "\n", "")
            with patch.object(entorno.subprocess, "run", return_value=r) as llamada:
                self.assertEqual(entorno.comprobar_dependencias_r("Rscript"), d)
                comando = llamada.call_args.args[0]
                self.assertNotIn("-e", comando)
                self.assertEqual(Path(comando[2]).name, "12_verificar_entorno.R")
                self.assertEqual(Path(comando[3]), ROOT)
                self.assertEqual(len(comando), 4)

    def test_falta_de_paquetes_conserva_el_error_de_r(self):
        # Un fallo de la biblioteca se comunica antes de iniciar las fuentes.
        r = subprocess.CompletedProcess([], 1, "", "Paquetes sin restaurar: survey, calidad")
        with patch.object(entorno.subprocess, "run", return_value=r):
            with self.assertRaisesRegex(RuntimeError, "survey, calidad"):
                entorno.comprobar_dependencias_r("Rscript")

    def test_fallo_sin_texto_conserva_codigo_y_registro(self):
        # Un fallo nativo de Windows no puede convertirse otra vez en un mensaje vacío.
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.CompletedProcess([], -1073741819, "", "")
            with patch.object(entorno.subprocess, "run", return_value=r):
                with self.assertRaisesRegex(RuntimeError, "0xC0000005"):
                    entorno.comprobar_dependencias_r("Rscript", Path(d))
            contenido = (Path(d)/"diagnosticos/verificacion_R.log").read_text(encoding="utf-8")
            self.assertIn("-1073741819", contenido)

    @unittest.skipUnless(os.getenv("EPF_RSCRIPT_PRUEBA"), "Requiere R 4.5.0 preparado")
    def test_verificacion_con_r_real(self):
        # Prueba opcional con el R y el proyecto indicados, sin reinstalar paquetes.
        raiz = Path(os.getenv("EPF_PROYECTO_R_PRUEBA", str(ROOT)))
        biblioteca = entorno.comprobar_dependencias_r(os.environ["EPF_RSCRIPT_PRUEBA"], raiz)
        self.assertTrue(Path(biblioteca).is_dir())
        contenido = (raiz/"diagnosticos/verificacion_R.log").read_text(encoding="utf-8")
        self.assertIn("Cargar survey", contenido)
        self.assertIn("Cargar calidad", contenido)
        self.assertIn("Verificación terminada", contenido)

    def test_flujo_no_descarga_ni_calcula_si_la_biblioteca_falla(self):
        # Se reproduce el fallo del registro y se garantiza que no se lanza 03 ni 04.
        spec = importlib.util.spec_from_file_location("flujo_interno", ROOT / "flujo.py")
        flujo = importlib.util.module_from_spec(spec); spec.loader.exec_module(flujo)
        with patch.object(sys, "argv", ["ejecutar.py"]), \
             patch.dict(os.environ, {}, clear=False), \
             patch.object(flujo, "localizar_rscript", return_value="Rscript45"), \
             patch.object(flujo, "comprobar_dependencias_r", side_effect=RuntimeError("Falta survey")), \
             patch.object(flujo.subprocess, "run") as llamada:
            with self.assertRaisesRegex(RuntimeError, "Falta survey"):
                flujo.ejecutar()
            llamada.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
