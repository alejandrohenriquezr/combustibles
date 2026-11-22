"""Exporta el respaldo EPF de gasto mediano / ingreso mediano de hogares gastadores."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from modulos.epf_calculos import COMBUSTIBLES
from modulos.graficos import crear_graficos


def preparar_tablas(payload,fuentes):
    """Conserva las medianas como resultados y deja su relación como fórmula editable."""
    t={};pi={(r['segmentacion'],r['grupo'],r['combustible'],r['indicador']):r for r in payload['precision']}
    componentes=[]
    for r in payload['resumen']:
        st=pi[(r['segmentacion'],r['grupo'],r['combustible'],'relacion_medianas')]
        componentes.append([r['segmentacion'],r['grupo'],COMBUSTIBLES[r['combustible']],r['n_gastadores'],
            r['gasto_mediano'],r['ingreso_mediano'],r['relacion_medianas'],r['relacion_medianas_li95'],
            r['relacion_medianas_ls95'],r['relacion_medianas_calidad'],st['cv'],r['n_ingreso_no_positivo'],
            r['n_todos'],r['participacion'],r['gasto_mediano_li95'],r['gasto_mediano_ls95'],
            r['ingreso_mediano_li95'],r['ingreso_mediano_ls95'],r['gasto_mediano_calidad'],r['ingreso_mediano_calidad']])
    t['Medianas']={'titulo':'Resultados de las dos medianas y su relación','nota':'Mismo dominio con gasto >0 para numerador y denominador; ingresos <=0 incluidos. Datos de 2021–2022.',
        'cabeceras':['Segmentación','Grupo','Combustible','n gastadores','Gasto mediano CLP','Ingreso mediano CLP','Gasto mediano / ingreso mediano',
        'IC relación inferior','IC relación superior','Precisión relación','CV relación','n ingreso <=0','n todos','% hogares con gasto',
        'IC gasto inferior','IC gasto superior','IC ingreso inferior','IC ingreso superior','Precisión gasto mediano','Precisión ingreso mediano'],
        'filas':componentes}
    for hoja,tipo in [('Quintiles','Quintil'),('Deciles','Decil')]:
        filas=[]
        for i,r in enumerate(payload['resumen'],6):
            if r['segmentacion'] not in ['Total',tipo]:continue
            c=lambda x:f"='Medianas'!{x}{i}"
            filas.append([r['grupo'],COMBUSTIBLES[r['combustible']],c('E'),c('F'),c('G'),
                          f"=IF('Medianas'!G{i}>0,'Medianas'!F{i}/'Medianas'!G{i},\"n.a.\")",
                          c('I'),c('J'),c('K'),c('L'),c('M'),c('P'),c('Q'),c('R'),c('S')])
        t[hoja]={'titulo':f'Gasto mediano en combustibles frente al ingreso mediano · {hoja.lower()}',
            'nota':'Porcentaje = gasto mediano / ingreso mediano del mismo conjunto de hogares que declaran gasto. No se promedian porcentajes por hogar.',
            'cabeceras':['Grupo','Combustible','n gastadores','Gasto mediano CLP','Ingreso mediano CLP','Gasto mediano / ingreso mediano',
                'IC 95% inferior','IC 95% superior','Evaluación de precisión','CV del indicador','n ingreso <=0',
                'IC gasto inferior','IC gasto superior','IC ingreso inferior','IC ingreso superior'],'filas':filas}
    t['Precisión']={'titulo':'Intervalos y evaluación de precisión de la nueva métrica',
        'nota':'IC percentiles del bootstrap conjunto. Criterios n/gl/CV de calidad adaptados; no es un estimador nativo de calidad.',
        'cabeceras':['Segmentación','Grupo','Combustible','Indicador','Estimación','EE bootstrap','IC 95% inferior','IC 95% superior','CV','n hogares','Grados de libertad','Evaluación de precisión','Método IC','Alcance de calidad'],
        'filas':[[r[k] for k in ['segmentacion','grupo','combustible','indicador','estimacion','ee','li95','ls95','cv','n','gl','clasificacion','metodo','evaluacion']] for r in payload['precision']]}
    ci={(r['indicador'],int(r['grupo_a']),int(r['grupo_b'])):i for i,r in enumerate(payload['covarianzas'],6)}
    t['Covarianzas']={'titulo':'Covarianzas conjuntas entre quintiles','nota':'Bootstrap de pseudo-conglomerados dentro de estratos; 1999 réplicas, semilla 20261119.',
        'cabeceras':['Indicador','Quintil A','Quintil B','Covarianza'],'filas':[[r[k] for k in ['indicador','grupo_a','grupo_b','covarianza']] for r in payload['covarianzas']]}
    filas=[]
    for i,r in enumerate(payload['contrastes'],6):
        a,b=int(r['grupo_a']),int(r['grupo_b']);ind=r['indicador'];c=lambda x,y:f"='Covarianzas'!E{ci[(ind,x,y)]}"
        filas.append([ind,a,b,r['estimacion_a'],r['estimacion_b'],f'=F{i}-E{i}',f'=SQRT(MAX(0,J{i}+K{i}-2*I{i}))',
            c(a,b),c(a,a),c(b,b),r['gl'],r['p_sin_ajuste'],r['p_holm_adyacentes'],r['p_holm_10'],
            'Sí' if str(r['adyacente']).lower()=='true' else 'No',r['marca_grafico'],r['metodo']])
    t['Contrastes']={'titulo':'Comparaciones entre quintiles con ajuste Holm',
        'nota':'†: p Holm >=0,05 frente al quintil anterior, 4 pares por indicador. Los 10 pares tienen también un ajuste conjunto separado. No significancia no demuestra igualdad.',
        'cabeceras':['Indicador','Quintil A','Quintil B','Estimación A','Estimación B','Diferencia B − A','EE diferencia','Covarianza A,B','Varianza A','Varianza B','gl','p sin ajuste','p Holm 4 adyacentes','p Holm 10 pares','Adyacente','Marca †','Método'],'filas':filas}
    keys=['folio','estrato_muestreo','var_unit','decil','quintil','fe_segmento','ingreso','gasto_total','gasolina','diesel','gasolina_diesel','ingreso_positivo']
    t['Hogares']={'titulo':'Hogares y factores repartidos entre deciles','nota':'Un hogar puede aparecer en dos filas de límite; sumar factores, no interpretar filas como hogares únicos.',
        'cabeceras':['Folio anonimizado','Estrato','Pseudo-conglomerado','Decil','Quintil','Factor segmento','Ingreso disponible CLP','Gasto total CLP','Gasolina CLP','Diésel CLP','Gasolina + diésel CLP','Ingreso positivo'],
        'filas':[[r[k] for k in keys] for r in payload['hogares_segmentados']]}
    fuentes_rows=[['Manual IX EPF',fuentes['manual']['paginas'],fuentes['manual']['url']]]
    fuentes_rows += [[f['titulo'],'Sin paginación; variables en LEEME.md',f['url']] for f in fuentes['archivos']]
    fuentes_rows += [[f['titulo'],f['paginas'],f['url']] for f in fuentes['fuentes_metodo']]
    t['Fuentes y controles']={'titulo':'Fuentes comprobables y controles de replicación','nota':'Datos INE IX EPF. Método bootstrap conjunto, calidad y survey; consulta 19/11/2026.',
        'cabeceras':['Fuente','Páginas o localizador','Enlace comprobable'],'filas':fuentes_rows}
    return t


def exportar(resultados,excel,configuracion):
    """Exportador Python portable; no calcula IC dividiendo extremos independientes."""
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment
    from openpyxl.utils import get_column_letter
    from openpyxl.drawing.image import Image
    d=json.loads(resultados.read_text(encoding='utf-8'));cfg=json.loads(configuracion.read_text(encoding='utf-8'))
    tablas=preparar_tablas(d,cfg);fig=crear_graficos(d,resultados.parent/'graficos');w=Workbook();w.remove(w.active)
    orden=['Quintiles','Deciles','Medianas','Precisión','Contrastes','Covarianzas','Hogares','Fuentes y controles']
    for name in orden:
        s=w.create_sheet(name);t=tablas[name];s.sheet_view.showGridLines=False
        s['B2']=t['titulo'];s['B3']=t['nota'];s['B2'].font=Font(name='Arial',size=14,bold=True)
        for j,v in enumerate(t['cabeceras'],2):
            c=s.cell(5,j,v);c.fill=PatternFill('solid',fgColor='345469');c.font=Font(name='Arial',color='FFFFFF',bold=True)
            c.alignment=Alignment(wrap_text=True,vertical='center');s.column_dimensions[get_column_letter(j)].width=23
        s.row_dimensions[5].height=65
        for i,row in enumerate(t['filas'],6):
            for j,v in enumerate(row,2):s.cell(i,j,v).alignment=Alignment(vertical='center')
            s.row_dimensions[i].height=23
        s.freeze_panes='B6'
    for name in ['Quintiles','Deciles']:
        s=w[name]
        for i in range(6,6+len(tablas[name]['filas'])):
            for c in ['G','H','I','K']:s[f'{c}{i}'].number_format='0.0%'
            for c in ['E','F','M','N','O','P']:s[f'{c}{i}'].number_format='#,##0'
    for i,r in enumerate(d['precision'],6):
        for c in ['F','G','H','I']:w['Precisión'][f'{c}{i}'].number_format='0.00%' if r['indicador']=='relacion_medianas' else '#,##0.00'
        w['Precisión'][f'J{i}'].number_format='0.0%'
    graficos=w.create_sheet('Gráficos EPF');graficos.sheet_view.showGridLines=False
    for key,cell in [('indicador','B5'),('gasto','B30'),('ingreso','B55')]:
        im=Image(str(fig[key]));im.width,im.height=1008,365;graficos.add_image(im,cell)
    s=w['Fuentes y controles'];inicio=20
    for j,v in enumerate(['Quintil','Variable','Calculado','Publicado','Diferencia','Localizador oficial'],2):s.cell(inicio,j,v)
    for i,c in enumerate(d['diagnostico']['controles_oficiales'],inicio+1):
        for j,v in enumerate([c['quintil'],c['variable'],c['calculado'],c['oficial'],f'=D{i}-E{i}',f"{c['hoja']}!{c['celda']}"],2):s.cell(i,j,v)
    s['B44']='EE ingreso, control calidad';s['D44']=d['calidad']['control_ingreso']['se'];s['E44']=18082.39
    s['G44']='Manual IX EPF, p. 82, tabla 5; tolerancia $0,02'
    s['B46']='Versiones ejecutadas';s['D46']=json.dumps(d['calidad']['versiones'])
    excel.parent.mkdir(parents=True,exist_ok=True);w.save(excel);print('Excel EPF:',excel)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);r=Path(__file__).resolve().parent
    p.add_argument('--resultados',type=Path,default=r/'resultados/resultados.json')
    p.add_argument('--excel',type=Path,default=r/'resultados/IX_EPF_combustibles_hogares_con_gasto.xlsx')
    p.add_argument('--config',type=Path,default=r/'configuracion.json');a=p.parse_args()
    exportar(a.resultados.resolve(),a.excel.resolve(),a.config.resolve())
