"""Pruebas de la unidad hogar, dominios, razones y partición de factores."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
from modulos.epf_calculos import DisenoTaylor, calcular_resultados, cuantiles_ponderados, segmentar_hogares


# Se carga el ejecutable numérico para probar sus validaciones sin ejecutar la CLI.
spec = importlib.util.spec_from_file_location("recalculo", Path(__file__).resolve().parents[1]/"04_recalcular_combustibles.py")
recalculo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recalculo)


def ejemplo():
    """Diseño pequeño con dos estratos y dos conglomerados por estrato."""
    return pd.DataFrame({"folio": [str(i) for i in range(8)], "fe": np.ones(8),
                         "estrato_muestreo": ["1"]*4+["2"]*4,
                         "var_unit": ["A", "A", "B", "B", "C", "C", "D", "D"],
                         "ing_disp_hog_hd": np.arange(1,9)*100., "ing_disp_hog_hd_pc": np.arange(1,9)*50.,
                         "gastot_hd": np.arange(1,9)*80., "gastot_hd_pc": np.arange(1,9)*40.,
                         "gasolina": [10.,20.,0.,0.,30.,40.,0.,0.], "diesel": np.zeros(8),
                         "parentesco": np.ones(8), "macrozona": ["1"]*8})


class CalculosEPF(unittest.TestCase):
    # Este resultado analítico detecta la pérdida incorrecta de conglomerados sin gastadores.
    def test_varianza_dominio_conserva_conglomerados_cero(self):
        h = ejemplo()
        s = DisenoTaylor(h).razon(h.gasolina, pertenencia=(h.gasolina > 0).astype(float))
        self.assertAlmostEqual(s["estimacion"],25.)
        self.assertAlmostEqual(s["ee"]**2,50.)
        self.assertEqual(s["n"],4)

    # Un promedio de proporciones no debe confundirse con una razón de totales.
    def test_razon_distinta_de_promedio_individual(self):
        h = ejemplo()
        h["gasolina"] = [1,9,0,0,0,0,0,0]
        h["ing_disp_hog_hd"] = [1,99,100,100,100,100,100,100]
        d = DisenoTaylor(h)
        a = (h.gasolina > 0).to_numpy(float)
        self.assertAlmostEqual(d.razon(h.gasolina,h.ing_disp_hog_hd,a)["estimacion"],0.1)
        self.assertAlmostEqual(d.razon(h.gasolina/h.ing_disp_hog_hd,pertenencia=a)["estimacion"],(1+9/99)/2)

    # La partición conserva el peso incluso si un hogar atraviesa varios cortes.
    def test_particion_pesos_y_quintiles(self):
        h=ejemplo()
        h.loc[0,"fe"]=40
        d=segmentar_hogares(h,10)
        q=segmentar_hogares(h,5)
        np.testing.assert_allclose(d.sum(axis=1),1,atol=1e-12)
        np.testing.assert_allclose(d.T@h.fe.to_numpy(),h.fe.sum()/10,atol=1e-12)
        np.testing.assert_allclose(d.reshape(len(h),5,2).sum(axis=2),q,atol=1e-12)

    # El reemplazo para ordenar no altera el ingreso que entra al denominador de carga.
    def test_ingreso_no_positivo_solo_reemplaza_orden(self):
        h=ejemplo();h.loc[0,"ing_disp_hog_hd"]=0;h.loc[0,"gastot_hd_pc"]=10000
        d=segmentar_hogares(h,10)
        self.assertGreater(d[0,-1],0)
        self.assertEqual(h.loc[0,"ing_disp_hog_hd"],0)
        r,_=calcular_resultados(h,d)
        t=r[(r.segmentacion=="Total")&(r.combustible=="gasolina_diesel")].iloc[0]
        self.assertEqual(t.n_gastadores,4)
        self.assertEqual(t.n_ingreso_positivo,3)
        self.assertEqual(t.n_ingreso_no_positivo,1)

    # Un dominio vacío no representa un promedio cero.
    def test_dominio_vacio_y_mediana_ponderada(self):
        h=ejemplo();d=DisenoTaylor(h)
        s=d.razon(h.gasolina,pertenencia=np.zeros(len(h)))
        self.assertIsNone(s["estimacion"])
        self.assertEqual(cuantiles_ponderados([1,9,10],[8,1,1],[0.5]),[1.])

    # Duplicados e inconsistencias deben detener el cálculo, sin correcciones silenciosas.
    def test_control_un_hogar_una_fila(self):
        h=ejemplo()
        self.assertEqual(len(recalculo.validar_hogares(h)),8)
        with self.assertRaises(ValueError):
            recalculo.validar_hogares(pd.concat([h,h.iloc[[0]]],ignore_index=True))
        h2=h.iloc[[0]].copy();h2["parentesco"]=2;h2["fe"]=99
        with self.assertRaises(ValueError):
            recalculo.validar_hogares(pd.concat([h,h2],ignore_index=True))

    # El diseño completo no permite inventar una corrección para estratos solitarios.
    def test_estrato_invalido(self):
        h=ejemplo();h["var_unit"]=["A"]*4+["B"]*4
        with self.assertRaises(ValueError):DisenoTaylor(h)


if __name__=="__main__":
    unittest.main(verbosity=2)
