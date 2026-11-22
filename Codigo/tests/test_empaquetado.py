"""El respaldo conserva la entrada, fuentes y web, con manifiesto portable."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('empaquetado', Path(__file__).resolve().parents[1]/'11_empaquetar.py')
modulo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modulo)


class Respaldo(unittest.TestCase):
    def test_zip_reproducible_con_entrada_y_manifiesto_sin_entornos(self):
        with tempfile.TemporaryDirectory() as temporal:
            proyecto = Path(temporal)
            codigo = proyecto/'Codigo'
            resultados = codigo/'resultados'
            datos = codigo/'datos'
            archivos = {
                'ejecutar.py': b'# entrada', 'README.md': b'Instalacion',
                'Codigo/flujo.py': b'# flujo', 'documentacion/instalacion.md': b'Instrucciones',
                'docs/estilos.css': b'body{}', 'Codigo/datos/personas.csv': b'fe\n1\n',
                'Codigo/.venv/paquete.py': b'no distribuir',
                'Codigo/renv/library/paquete/DESCRIPTION': b'no distribuir',
                'Codigo/resultados/resultados.json': b'{}',
                'Codigo/resultados/actualizacion_fuentes.json': b'{}',
                'Codigo/resultados/web/index.html': b'<html lang="es"></html>',
                'Codigo/resultados/web/assets/grafico-1.png': b'grafico',
            }
            for nombre in ['Articulo_LinkedIn_combustibles_Chile_actualizado.docx',
                           'Respaldo_combustibles_EPF_GPP.xlsx', 'IX_EPF_combustibles_hogares_con_gasto.xlsx']:
                archivos['Codigo/resultados/'+nombre] = b'producto de prueba'
            for nombre, contenido in archivos.items():
                p = proyecto/nombre
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(contenido)
            destino = proyecto/'respaldo.zip'
            modulo.empaquetar(codigo, resultados, destino, datos)
            with zipfile.ZipFile(destino) as z:
                for nombre in ['ejecutar.py', 'README.md', 'Codigo/flujo.py', 'Codigo/datos/personas.csv',
                               'documentacion/instalacion.md', 'docs/index.html', 'docs/assets/grafico-1.png', 'docs/estilos.css']:
                    self.assertIn(nombre, z.namelist())
                self.assertFalse(any('/.venv/' in n or '/library/' in n for n in z.namelist()))
                manifiesto = json.loads(z.read('MANIFIESTO_PAQUETE.json'))
                for registro in manifiesto:
                    self.assertNotIn('\\', registro['archivo'])
                    contenido = z.read(registro['archivo'])
                    self.assertEqual(hashlib.sha256(contenido).hexdigest(), registro['sha256'])
                    self.assertEqual(len(contenido), registro['bytes'])
