"""Pruebas del significado de la conversión y de la comparación entre países."""
import unittest
import pandas as pd
from modulos.ppa import calcular_ppa


class PruebasPPA(unittest.TestCase):
    def fuentes(self):
        # Los precios nominales permanecen constantes entre ambos años; cambia
        # solo el factor de una economía para distinguir los dos efectos.
        precios=pd.DataFrame([{'fecha':f,'combustible':'gasolina','iso':i,'pais':i,'usd_litro':v}
                              for f in ['2025-03-10','2026-10-19'] for i,v in [('AAA',1.),('BBB',2.)]])
        factores=pd.DataFrame([{'iso':i,'pais':i,'ano':a,'factor_ppa':v}
                               for i,a,v in [('AAA',2025,3.),('AAA',2026,1.),('BBB',2025,1.),('BBB',2026,1.)]])
        return precios,factores

    def test_la_ppa_puede_invertir_el_orden_nominal(self):
        p,f=self.fuentes();d=calcular_ppa(p,f)
        a=d[(d.iso=='AAA')&(d.ano==2025)].iloc[0]
        self.assertEqual(a.usd_litro,1.)
        self.assertEqual(a.precio_ppa_aprox,3.)
        self.assertEqual(a.puesto_ppa,2)

    def test_se_usa_el_ano_correcto_y_se_conserva_la_sensibilidad(self):
        p,f=self.fuentes();d=calcular_ppa(p,f)
        a=d[(d.iso=='AAA')&(d.ano==2026)].iloc[0]
        self.assertEqual(a.puesto_ppa,1)
        self.assertEqual(a.puesto_ppa_fijo_2025,2)
        self.assertEqual(len(d),len(p))

    def test_no_se_completa_un_factor_faltante(self):
        p,f=self.fuentes();f=f[~((f.iso=='AAA')&(f.ano==2026))]
        with self.assertRaises(ValueError):calcular_ppa(p,f)

    def test_los_empates_comparten_puesto(self):
        p,f=self.fuentes();f.loc[f.iso=='AAA','factor_ppa']=2.
        d=calcular_ppa(p,f)
        self.assertTrue((d.puesto_ppa==1).all())


if __name__=='__main__':
    unittest.main()
