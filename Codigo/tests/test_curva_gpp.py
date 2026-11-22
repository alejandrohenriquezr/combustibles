"""Auditoría independiente de los puntos, IC y respaldo de la nueva curva."""
import hashlib
import json
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
SALIDA=ROOT/'resultados'
if not SALIDA.exists():SALIDA=ROOT.parent/'Resultados'


@unittest.skipUnless((SALIDA/'hogares_procesados.csv').is_file() and
                     (SALIDA/'escenario_gpp_ic.csv').is_file() and
                     (ROOT/'gpp_chile_clp.csv').is_file() and
                     (ROOT/'datos/originales/gpp').is_dir(),
                     'Auditoría de integración: requiere resultados y originales GPP locales')
class CurvaGPP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Se comprueban los productos realmente entregados, no cifras inventadas.
        cls.h=pd.read_csv(SALIDA/'hogares_procesados.csv')
        cls.c=pd.read_csv(SALIDA/'escenario_gpp_ic.csv',keep_default_na=False)
        cls.p=pd.read_csv(ROOT/'gpp_chile_clp.csv',keep_default_na=False)

    def test_puntos_con_mediana_ponderada_independiente(self):
        # El ordenamiento se recalcula aquí, fuera del código R estimador.
        h=self.h
        for q in range(1,6):
            fr=h[f'fraccion_decil_{2*q-1}']+h[f'fraccion_decil_{2*q}']
            dominio=(fr>1e-12)&(h.gasolina_diesel>0)
            x=h[dominio];w=(h.fe*fr)[dominio].to_numpy()
            def med(v):
                v=np.asarray(v);i=np.argsort(v,kind='stable')
                return v[i][np.searchsorted(np.cumsum(w[i]),w.sum()/2)]
            g0=med(x.gasolina_diesel);y=med(x.ing_disp_hog_hd)
            for p in self.p.itertuples(index=False):
                vg=p.gasolina_clp/self.p.gasolina_clp.iloc[0]
                vd=p.diesel_clp/self.p.diesel_clp.iloc[0]
                calculado=(med(x.gasolina*vg+x.diesel*vd)-g0)/y
                punto=self.c[(self.c.quintil==q)&(self.c.mes==p.mes)].estimacion.iloc[0]
                self.assertAlmostEqual(calculado,punto,places=12)

    def test_intervalos_son_percentiles_de_las_replicas(self):
        # Inverted CDF es el tipo 1 de R; no se usa interpolación lineal.
        replicas=pd.read_csv(SALIDA/'replicas_escenario_gpp.csv')
        self.assertEqual(len(replicas),1999)
        for r in self.c.itertuples(index=False):
            v=replicas[f'Q{r.quintil}_{r.mes}'].to_numpy()
            li,ls=np.quantile(v,[.025,.975],method='inverted_cdf')
            self.assertAlmostEqual(li,r.li95,places=12)
            self.assertAlmostEqual(ls,r.ls95,places=12)

    def test_cobertura_mensual_y_fuentes_originales(self):
        # Un hueco mensual no se reemplaza por cero ni por el mes vecino.
        esperado=pd.period_range('2025-01',self.p.mes.max(),freq='M').astype(str).tolist()
        self.assertEqual(self.p.mes.tolist(),esperado)
        base=ROOT/'datos/originales/gpp'
        for r in self.p.itertuples(index=False):
            for fuel in ['gasolina','diesel']:
                sha=getattr(r,'sha256_'+fuel);raw=(base/(sha+'.html')).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(),sha)
                fecha=getattr(r,'fecha_'+fuel)
                if not fecha:self.assertIn('hace un mes',getattr(r,'origen_'+fuel))

    def test_marcas_corresponden_a_pruebas_y_precision(self):
        # Se comprueba la regla declarada, incluida la ausencia de prueba en base.
        t=pd.read_csv(SALIDA/'escenario_gpp_contrastes.csv',keep_default_na=False)
        for r in t.itertuples(index=False):
            punto=self.c[(self.c.mes==r.mes)&(self.c.quintil==r.grupo_b)].iloc[0]
            if r.p_holm=='':self.assertEqual(punto.marca_no_significativa,'')
            else:self.assertEqual(punto.marca_no_significativa=='○',float(r.p_holm)>=.05)
        for r in self.c.itertuples(index=False):
            self.assertEqual(r.marca_no_fiable=='×',r.clasificacion=='No fiable')


if __name__=='__main__':unittest.main(verbosity=2)
