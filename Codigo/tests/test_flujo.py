"""Un fallo al crear el ZIP no debe sustituir los productos anteriores."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import flujo
from modulos import web


class Publicacion(unittest.TestCase):
    def test_error_de_empaquetado_restaura_la_salida_anterior(self):
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            salida = raiz / 'resultados'
            salida.mkdir()
            (salida / 'anterior.txt').write_text('resultado válido anterior')
            (raiz / 'actualizacion_fuentes.json').write_text(json.dumps({
                'actualizacion_completa': True, 'gpp': {'sha256_precios':'a', 'sha256_clp':'b'}}))
            (raiz / 'configuracion.json').write_text(json.dumps({
                'gpp': {'sha256':'a', 'clp':{'sha256':'b'}}}))

            def proceso(comando, **kwargs):
                if Path(comando[1]).name == '11_empaquetar.py':
                    raise subprocess.CalledProcessError(1, comando)
                return subprocess.CompletedProcess(comando, 0)

            with patch.object(flujo, '__file__', str(raiz/'flujo.py')), \
                 patch.object(flujo, 'localizar_rscript', return_value='Rscript'), \
                 patch.object(flujo, 'comprobar_dependencias_r', return_value='biblioteca'), \
                 patch.object(flujo.subprocess, 'run', side_effect=proceso), \
                 patch.object(web, 'exportar_articulo'), \
                 patch.object(web, 'instalar_web') as publicar:
                with self.assertRaises(subprocess.CalledProcessError):
                    flujo.ejecutar(['--reproducir-sin-actualizar', '--salida', str(salida)])
                publicar.assert_not_called()
            self.assertEqual((salida/'anterior.txt').read_text(), 'resultado válido anterior')
            self.assertEqual(len(list(raiz.glob('.resultados_en_proceso_*'))), 1)
