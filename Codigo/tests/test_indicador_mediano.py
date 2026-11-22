"""Pruebas de la interpretación solicitada: dos medianas del mismo dominio."""
import unittest
from modulos.epf_calculos import medianas_de_gastadores,cuantiles_ponderados


class IndicadorMediano(unittest.TestCase):
    def test_dos_medianas_no_mediana_de_porcentajes(self):
        # La razón correcta es 50/100; la mediana de porcentajes de estos hogares es 0,1.
        r=medianas_de_gastadores([1,50,100],[100,60,1000],[1,1,1])
        self.assertEqual(r['relacion_medianas'],.5)
        self.assertEqual(cuantiles_ponderados([.01,50/60,.1],[1,1,1],[.5]),[.1])

    def test_no_elimina_ingreso_negativo_del_dominio(self):
        # El ingreso negativo influye en ambas medianas; eliminarlo cambia el indicador.
        r=medianas_de_gastadores([20,30,40,50],[-10,20,100,200],[1.5,1,1,1])
        self.assertEqual((r['gasto_mediano'],r['ingreso_mediano']),(30,20))
        self.assertEqual(r['relacion_medianas'],1.5)
        self.assertEqual(r['n_gastadores'],4)

    def test_hogar_sin_gasto_no_entra_en_ninguna_mediana(self):
        # Un hogar muy expandido pero sin gasto no modifica el numerador ni el denominador.
        r=medianas_de_gastadores([0,10,20,30],[1000000,100,200,300],[1000,1,1,1])
        self.assertEqual((r['gasto_mediano'],r['ingreso_mediano']),(20,200))
        self.assertEqual(r['n_gastadores'],3)

    def test_denominador_mediano_no_positivo_detiene_calculo(self):
        # No se cambia el dominio ni se sustituye el ingreso para obtener una división válida.
        with self.assertRaises(ValueError):medianas_de_gastadores([10,20,30],[-20,-10,100],[1,1,1])


if __name__=='__main__':unittest.main(verbosity=2)
