"""Verifica binarios obligatorios y diagnósticos que no expongan credenciales."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('instalador_01',ROOT/'01_instalar_dependencias.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class Instalador(unittest.TestCase):
    def test_paquetes_no_se_compilan_y_se_conserva_indice_configurado(self):
        # La instalación normal no sustituye el repositorio configurado del equipo.
        c=m.comando_instalacion('python.exe',ROOT)
        self.assertIn('--only-binary=:all:',c)
        self.assertIn('--no-cache-dir',c)
        self.assertNotIn('--index-url',c)

    def test_indice_publico_solo_se_selecciona_explicitamente(self):
        # La selección de PyPI queda visible en una opción del usuario.
        c=m.comando_instalacion('python.exe',ROOT,'https://pypi.org/simple')
        self.assertEqual(c[c.index('--index-url')+1],'https://pypi.org/simple')

    def test_no_se_filtran_credenciales_al_diagnostico(self):
        # Un índice con autenticación conserva solo el host en el informe.
        salida="global.index-url='https://usuario:secreto@repo.ejemplo.cl/simple?token=oculto'\nglobal.no-binary=':all:'"
        r=m.opciones_pip_sin_secretos(salida)
        self.assertEqual(r['hosts_indices'],['repo.ejemplo.cl'])
        for secreto in ['usuario','secreto','oculto','token']:self.assertNotIn(secreto,str(r))
        self.assertEqual(r['preferencias_binarios_y_plataforma']['global.no-binary'],':all:')

    def test_version_erronea_de_entorno_se_detecta_antes_de_instalar(self):
        # Un .venv de otra versión no se borra ni se reutiliza silenciosamente.
        with self.assertRaises(ValueError):
            m.comprobar_python({'version':[3,11,9],'implementacion':'CPython','bits':64})
        m.comprobar_python({'version':[3,12,8],'implementacion':'CPython','bits':64})


if __name__=='__main__':unittest.main(verbosity=2)
