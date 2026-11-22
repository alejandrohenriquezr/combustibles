"""Respalda EPF y precios GPP; añade factores FMI como insumo auxiliar para PPA."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd
from modulos.graficos import crear_graficos
from modulos.ppa import leer_factores, calcular_ppa


def leer_gpp(raiz):
    """Verifica la extracción recién actualizada y sus puestos desde el menor."""
    cfg=json.loads((raiz/'configuracion.json').read_text(encoding='utf-8'))
    archivo=raiz/cfg['gpp']['archivo']
    if hashlib.sha256(archivo.read_bytes()).hexdigest()!=cfg['gpp']['sha256']:
        raise ValueError('La extracción GPP no coincide con su huella validada.')
    g=pd.read_csv(archivo)
    if len(g)!=cfg['gpp']['observaciones'] or g.duplicated(['fecha','combustible','iso']).any():
        raise ValueError('El número de registros no coincide con el manifiesto actualizado.')
    paises=None
    for _,f in g.groupby(['fecha','combustible']):
        if len(f)!=17 or (paises is not None and set(f.iso)!=paises):
            raise ValueError('El universo de 17 países cambió entre cortes.')
        paises=set(f.iso)
        puestos=f.usd_litro.rank(method='min',ascending=True).astype(int)
        if not puestos.equals(f.puesto.astype(int)):
            raise ValueError('Los puestos GPP no coinciden con el orden de precios.')
    return g


def preparar_tablas_analisis(payload, config, raiz):
    """Define tablas editables; los estimadores complejos siguen calculándose en R."""
    g=leer_gpp(raiz);src=json.loads((raiz/'gpp_fuentes.json').read_text(encoding='utf-8'))
    spec=importlib.util.spec_from_file_location('exportar_epf',raiz/'07_exportar_excel.py')
    epf=importlib.util.module_from_spec(spec);spec.loader.exec_module(epf)
    t_epf=epf.preparar_tablas(payload,config)
    tablas={};final_gpp=len(g)+5
    filas=[];idx={(r['grupo'],r['indicador']):r for r in payload['precision']
                 if r['segmentacion']=='Quintil' and r['combustible']=='gasolina_diesel'}
    for i in range(1,6):
        s=next(r for r in payload['resumen'] if r['segmentacion']=='Quintil' and r['grupo']==str(i) and r['combustible']=='gasolina_diesel')
        st=idx[(str(i),'relacion_medianas')];r=6+i-1
        row=[i,s['n_gastadores'],s['gasto_mediano'],s['ingreso_mediano'],f'=D{r}/E{r}',
             st['li95'],st['ls95'],st['clasificacion'],st['cv'],s['gasto_mediano_li95'],s['gasto_mediano_ls95'],
             s['ingreso_mediano_li95'],s['ingreso_mediano_ls95'],s['n_ingreso_no_positivo']]
        filas.append(row)
    cab=['Quintil','n con gasto','Gasto mediano CLP','Ingreso mediano CLP','Gasto mediano / ingreso mediano',
         'IC indicador inferior','IC indicador superior','Precisión adaptada','CV indicador',
         'IC gasto inferior','IC gasto superior','IC ingreso inferior','IC ingreso superior','n ingreso <=0']
    tablas['Resumen EPF']={'titulo':'Combustibles e ingreso en hogares gastadores IX EPF',
        'nota':'Mismos hogares con gasto para ambas medianas; ingreso <=0 conservado. †: p Holm ≥0,05 frente al quintil anterior; ‡: No fiable, criterios adaptados.',
        'cabeceras':cab,'filas':filas}
    tablas['Precios GPP']={'titulo':'Precios internacionales de GlobalPetrolPrices',
        'nota':f'{len(g)} registros: {g.iso.nunique()} países × {g.fecha.nunique()} fechas comunes × 2 combustibles. USD/litro; 1=menor precio.',
        'cabeceras':['Fecha','Combustible','ISO','País','USD por litro','Puesto','Captura comprobable','SHA-256 HTML original'],
        'filas':[[r[k] for k in ['fecha','combustible','iso','pais','usd_litro','puesto','url','sha256_html']] for r in g.to_dict('records')]}
    chile=[]
    for i,fecha in enumerate(sorted(g.fecha.unique()),6):
        f=g[(g.fecha==fecha)&(g.iso=='CHL')].set_index('combustible')
        chile.append([fecha,float(f.loc['gasolina','usd_litro']),float(f.loc['diesel','usd_litro']),
                      f'=C{i}/$C$6-1',f'=D{i}/$D$6-1',int(f.loc['gasolina','puesto']),int(f.loc['diesel','puesto'])])
    tablas['Chile GPP']={'titulo':f'Chile: precios y puestos, {g.fecha.min()} a {g.fecha.max()}',
        'nota':'Un corte semanal común por mes. Variaciones en USD: no representan variaciones en pesos ni gasto de hogares de 2026.',
        'cabeceras':['Fecha','Bencina 95 USD/L','Diésel USD/L','Variación bencina USD','Variación diésel USD','Puesto bencina','Puesto diésel'],'filas':chile}
    final=g[g.fecha==g.fecha.max()].sort_values(['combustible','puesto','pais'])
    ranking=[]
    for i,(original,r) in enumerate(final.iterrows(),6):
        # El precio enlaza a la fila original; COUNTIFS reproduce puestos compartidos.
        sr=int(original)+6
        ranking.append([r.combustible,f'=1+COUNTIFS(\'Precios GPP\'!$B$6:$B${final_gpp},F{i},\'Precios GPP\'!$C$6:$C${final_gpp},B{i},\'Precios GPP\'!$F$6:$F${final_gpp},"<"&E{i})',
                        r.pais,f"='Precios GPP'!F{sr}",r.fecha,r.url])
    tablas['Ranking vigente']={'titulo':'Ranking de los 17 países con datos comunes',
        'nota':f'Último corte: {g.fecha.max()}. Menor a mayor precio USD/litro; empates con el mismo puesto. Mes en curso parcial.',
        'cabeceras':['Combustible','Puesto','País','USD por litro','Fecha','Captura comprobable'],'filas':ranking}
    for name in ['Contrastes','Covarianzas']:tablas[name]=t_epf[name]
    tablas['Fuentes GPP']={'titulo':'Capturas comprobables de GlobalPetrolPrices',
        'nota':'Fechas del precio y de captura distintas; el precio corresponde al título de la página original. Sin paginación.',
        'cabeceras':['Fecha del precio','Combustible','Captura UTC','Título original','Enlace archivado','SHA-256 HTML original','URL original'],
        'filas':[[r['date'],r['fuel'],r['timestamp'],r['title'],r['archive_url'],r['sha256'],r['original_url']] for r in src]}
    fuentes=[['INE. Manual IX EPF, R',config['manual']['paginas'],config['manual']['url']]]
    fuentes += [[f['titulo'],'Sin paginación; variables y localizadores en LEEME.md',f['url']] for f in config['archivos']]
    fuentes += [[f['titulo'],f['paginas'],f['url']] for f in config['fuentes_metodo']]
    fuentes += [[config['ppa']['fuente']['titulo'],config['ppa']['localizador'],config['ppa']['fuente']['url']],
                ['FMI. WEO Frequently Asked Questions','Secciones 2 y 4: estimaciones, frecuencia anual, PPA del PIB. Sin paginación.',config['ppa']['metodo_url']]]
    tablas['Fuentes y método']={'titulo':'Fuentes, diseño y marcas estadísticas',
        'nota':f'EPF: hogares; GPP: precios; FMI: factor auxiliar PPA. Consulta {config["consulta"]}.',
        'cabeceras':['Fuente','Páginas o localizador','Enlace comprobable'],'filas':fuentes}
    tablas.update(preparar_tablas_ppa(g,leer_factores(raiz),config))
    if 'escenario_gpp' in payload:tablas.update(preparar_tablas_curva(payload,config))
    return tablas


def preparar_tablas_curva(payload,config):
    """Respaldos completos de precios CLP, IC y pruebas de la curva ciudadana."""
    d=payload['escenario_gpp'];precios=[]
    for i,r in enumerate(d['precios_clp'],6):
        precios.append([r['mes'],r['gasolina_clp'],r['diesel_clp'],f'=C{i}/$C$6',f'=D{i}/$D$6',
            r['fecha_gasolina'] or 'Día no publicado',r['fecha_diesel'] or 'Día no publicado',
            r['origen_gasolina'],r['origen_diesel'],r['publicacion_gasolina'],r['publicacion_diesel'],
            r['url_gasolina'],r['url_diesel'],r['sha256_gasolina'],r['sha256_diesel']])
    serie=[[r[k] for k in ['mes','quintil','estimacion','li95','ls95','ee','cv','n','gl','clasificacion',
                           'marca_no_significativa','marca_no_fiable']] for r in d['serie']]
    pruebas=[[r[k] for k in ['mes','grupo_a','grupo_b','diferencia','ee_diferencia','covarianza','gl',
                             'p_sin_ajuste','p_holm','marca']] for r in d['contrastes']]
    return {
      'Escenario GPP':{'titulo':'Cambio del gasto mediano / ingreso mediano de referencia',
        'nota':'Escenario EPF, base enero 2025; precios GPP CLP. IC 95% conjuntos condicionados a precios. ○ p Holm ≥0,05 con quintil anterior; × No fiable, calidad adaptada.',
        'cabeceras':['Mes','Quintil','Cambio / ingreso mediano','IC 95% inferior','IC 95% superior','EE bootstrap','CV','n gastadores','gl','Precisión adaptada','No significativa','No fiable'],
        'filas':serie},
      'Precios CLP':{'titulo':'Precios chilenos publicados por GlobalPetrolPrices',
        'nota':'Cortes publicados, no promedios mensuales. «Hace un mes» conserva precisión mensual; no se inventa el día. Enero es la base. Mes actual parcial.',
        'cabeceras':['Mes','Bencina 95 CLP/L','Diésel CLP/L','Índice bencina','Índice diésel','Fecha bencina','Fecha diésel',
          'Origen bencina','Origen diésel','Publicación bencina','Publicación diésel','Fuente bencina','Fuente diésel','SHA-256 bencina','SHA-256 diésel'],
        'filas':precios},
      'Contrastes curva':{'titulo':'Comparaciones de quintiles en cada mes de la curva GPP',
        'nota':'Wald t con covarianza conjunta. Holm: 4 pares adyacentes POR MES; no controla simultáneamente todos los meses. Cero inicial: sin prueba.',
        'cabeceras':['Mes','Quintil anterior','Quintil','Diferencia','EE diferencia','Covarianza','gl','p sin ajuste','p Holm, 4 pares','Marca'],
        'filas':pruebas}}


def preparar_tablas_ppa(g, factores, config):
    """Mantiene precios, conversión anual y puestos enlazados mediante fórmulas."""
    d=calcular_ppa(g,factores)
    pos_factor={(r.iso,int(r.ano)):i+6 for i,r in enumerate(factores.itertuples(index=False))}
    pos_gpp={(r.fecha,r.combustible,r.iso):i+6 for i,r in enumerate(g.itertuples(index=False))}
    pos_ppa={(r.fecha,r.combustible,r.iso):i+6 for i,r in enumerate(d.itertuples(index=False))}
    notas='Aproximación con PPA anual del PIB WEO octubre 2026; sin tipo de cambio de cada fecha. 2026 incorpora proyecciones. 1=menor precio.'
    final_ppa=len(d)+5
    tf=[]
    for i,r in enumerate(factores.itertuples(index=False),6):
        tf.append([r.iso,r.pais,int(r.ano),r.ngdpd,r.pppgdp,f'=F{i}/E{i}',r.ngdp,r.pppex,f'=H{i}/E{i}',
                   None if pd.isna(r.ultimo_actual_ngdpd) else int(r.ultimo_actual_ngdpd),r.estado_ngdpd,r.estado_pppgdp,
                   r.celda_ngdpd,r.celda_pppgdp,r.celda_pppex,r.fuente_url,r.sha256_fuente])
    tp=[]
    for i,r in enumerate(d.itertuples(index=False),6):
        origen=pos_gpp[(r.fecha,r.combustible,r.iso)];f=pos_factor[(r.iso,int(r.ano))];fijo=pos_factor[(r.iso,2025)]
        tp.append([r.fecha,r.combustible,r.iso,r.pais,f"='Precios GPP'!F{origen}",int(r.ano),
                   f"='Factores PPA'!G{f}",f'=F{i}*H{i}',
                   f'=1+COUNTIFS($B$6:$B${final_ppa},B{i},$C$6:$C${final_ppa},C{i},$I$6:$I${final_ppa},"<"&I{i})',
                   f"='Factores PPA'!G{fijo}",f'=F{i}*K{i}',
                   f'=1+COUNTIFS($B$6:$B${final_ppa},B{i},$C$6:$C${final_ppa},C{i},$L$6:$L${final_ppa},"<"&L{i})',r.url])
    tc=[]
    for i,fecha in enumerate(sorted(d.fecha.unique()),6):
        a=pos_ppa[(fecha,'gasolina','CHL')];b=pos_ppa[(fecha,'diesel','CHL')]
        tc.append([fecha,f"='Precios PPA'!J{a}",f"='Precios PPA'!J{b}",f"='Chile GPP'!G{i}",f"='Chile GPP'!H{i}"])
    tr=[]
    for i,r in enumerate(d[d.fecha==d.fecha.max()].sort_values(['combustible','puesto_ppa','pais']).itertuples(index=False),6):
        p=pos_ppa[(r.fecha,r.combustible,r.iso)]
        tr.append([r.combustible,f"='Precios PPA'!J{p}",r.pais,f"='Precios PPA'!I{p}",
                   int(r.puesto),f"='Precios PPA'!M{p}",r.fecha])
    return {
      'Chile PPA':{'titulo':'Evolución del ranking de Chile con ajuste PPA anual','nota':notas,
        'cabeceras':['Fecha','Bencina 95 puesto PPA','Diésel puesto PPA','Bencina puesto USD','Diésel puesto USD'],'filas':tc},
      'Precios PPA':{'titulo':'Cálculo del ajuste PPA y del ranking por fecha','nota':notas,
        'cabeceras':['Fecha','Combustible','ISO','País','USD/L original GPP','Año','Factor anual PPA/USD',
                     'PPA aprox./L','Puesto PPA','Factor fijo 2025','PPA aprox./L factor fijo','Puesto factor fijo 2025','Fuente del precio'],'filas':tp},
      'Factores PPA':{'titulo':'Factores anuales auxiliares del WEO octubre 2026',
        'nota':'Factor = PPPGDP/NGDPD; PPA del PIB, extrapolada/estimada. El cambio de año actualiza el factor. No mide ingreso, salario ni consumo de hogares.',
        'cabeceras':['ISO','País','Año','PIB USD miles de millones','PIB PPA miles de millones','Factor PPA/USD',
                     'PIB moneda local miles de millones','PPA moneda local/$ internacional','Cambio implícito anual moneda/USD',
                     'Último año actual PIB USD','Estado PIB USD','Estado PPA','Celda PIB USD','Celda PIB PPA','Celda PPA','Fuente WEO','SHA-256 WEO'],'filas':tf},
      'Ranking PPA vigente':{'titulo':f'Ranking {g.fecha.max()} con ajuste anual por PPA','nota':notas,
        'cabeceras':['Combustible','Puesto PPA','País','PPA aprox./L','Puesto USD','Puesto factor fijo 2025','Fecha'],'filas':tr}}


def exportar(resultados,excel):
    """Exportador portable Python; las fórmulas se recalculan al abrir en Excel."""
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment
    from openpyxl.utils import get_column_letter
    from openpyxl.drawing.image import Image
    raiz=Path(__file__).resolve().parent
    data=json.loads(resultados.read_text(encoding='utf-8'));cfg=json.loads((raiz/'configuracion.json').read_text(encoding='utf-8'))
    tablas=preparar_tablas_analisis(data,cfg,raiz);graficos=crear_graficos(data,resultados.parent/'graficos')
    # El respaldo procesado también se regenera fuera del Excel, para auditar
    # todos los precios ajustados y las dos variantes de factores anuales.
    ppa=calcular_ppa(leer_gpp(raiz),leer_factores(raiz))
    ppa.to_csv(resultados.parent/'precios_ppa.csv',index=False)
    ppa[ppa.iso=='CHL'].to_csv(resultados.parent/'chile_ppa.csv',index=False)
    w=Workbook();w.remove(w.active)
    for name,t in tablas.items():
        s=w.create_sheet(name);s.sheet_view.showGridLines=False
        s['B2']=t['titulo'];s['B3']=t['nota'];s['B2'].font=Font(name='Arial',size=14,bold=True)
        for j,v in enumerate(t['cabeceras'],2):
            c=s.cell(5,j,v);c.fill=PatternFill('solid',fgColor='345469');c.font=Font(name='Arial',color='FFFFFF',bold=True)
            c.alignment=Alignment(wrap_text=True,vertical='center');s.column_dimensions[get_column_letter(j)].width=23
        s.row_dimensions[5].height=60
        for i,row in enumerate(t['filas'],6):
            for j,v in enumerate(row,2):s.cell(i,j,v)
        s.freeze_panes='B6'
    for key,cell in [('indicador','B15'),('gasto','B42'),('ingreso','B69')]:
        im=Image(str(graficos[key]));im.width,im.height=1008,360;w['Resumen EPF'].add_image(im,cell)
    for key,cell in [('precios','L5'),('ranking','L32')]:
        im=Image(str(graficos[key]));im.width,im.height=1008,360;w['Chile GPP'].add_image(im,cell)
    # La nueva figura acompaña la tabla de veinte cortes y la sensibilidad anual.
    im=Image(str(graficos['ranking_ppa']));im.width,im.height=1100,470;w['Chile PPA'].add_image(im,'M5')
    if 'escenario' in graficos:
        im=Image(str(graficos['escenario']));im.width,im.height=1100,465;w['Escenario GPP'].add_image(im,'P5')
        for i in range(6,len(tablas['Escenario GPP']['filas'])+6):
            for c in ['D','E','F','G','H']:w['Escenario GPP'][f'{c}{i}'].number_format='0.00%'
    for i in range(6,len(tablas['Chile GPP']['filas'])+6):
        for c in ['E','F']:w['Chile GPP'][f'{c}{i}'].number_format='0.0%'
        for c in ['C','D']:w['Chile GPP'][f'{c}{i}'].number_format='0.000'
    excel.parent.mkdir(parents=True,exist_ok=True);w.save(excel);print('Respaldo EPF, GPP y ajuste PPA:',excel)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);r=Path(__file__).resolve().parent
    p.add_argument('--resultados',type=Path,default=r/'resultados/resultados.json')
    p.add_argument('--excel',type=Path,default=r/'resultados/Datos_rankings_combustibles_Chile_2025_2026.xlsx')
    a=p.parse_args();exportar(a.resultados.resolve(),a.excel.resolve())
