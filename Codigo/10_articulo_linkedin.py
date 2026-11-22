"""Actualiza la plantilla editada por el autor y solo sus dependencias numéricas.

La plantilla conserva párrafos, estilos, tablas, encabezados y estructura.
Se sustituyen las figuras GPP, las fechas, cifras y referencias que cambian.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
import zipfile
from copy import deepcopy
from lxml import etree
import pandas as pd
from modulos.graficos import crear_graficos,es
from modulos.ppa import calcular_ppa,leer_factores

NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
    'wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'rel':'http://schemas.openxmlformats.org/package/2006/relationships'}
MESES=['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']


def fecha_es(valor):
    """Escribe únicamente la fecha efectivamente publicada en la fuente."""
    f=dt.date.fromisoformat(valor);return f'{f.day} de {MESES[f.month-1]} de {f.year}'


def crear_articulo(resultados,destino):
    """Aplica cambios acotados al OOXML para preservar la edición del autor."""
    raiz=Path(__file__).resolve().parent
    payload=json.loads(resultados.read_text(encoding='utf-8'))
    cfg=json.loads((raiz/'configuracion.json').read_text(encoding='utf-8'))
    fig=crear_graficos(payload,resultados.parent/'graficos')
    g=pd.read_csv(raiz/'gpp_precios.csv');chi=g[g.iso=='CHL']
    a=chi[chi.fecha==chi.fecha.min()].set_index('combustible')
    b=chi[chi.fecha==chi.fecha.max()].set_index('combustible')
    ppa=calcular_ppa(g,leer_factores(raiz));pc=ppa[ppa.iso=='CHL']
    pa=pc[pc.fecha==pc.fecha.min()].set_index('combustible');pb=pc[pc.fecha==pc.fecha.max()].set_index('combustible')
    f0,f1=g.fecha.min(),g.fecha.max();n=g.fecha.nunique();npaises=g.iso.nunique()
    principio=fecha_es(f0);final=fecha_es(f1)
    mes_final=MESES[int(f1[5:7])-1]+' de '+f1[:4]
    plantilla=raiz/'plantillas/articulo_base.docx'
    with zipfile.ZipFile(plantilla) as z:partes={i.filename:z.read(i.filename) for i in z.infolist()}
    doc=etree.fromstring(partes['word/document.xml']);body=doc.find('w:body',NS)
    paras=body.findall('w:p',NS)
    def texto(p):return ''.join(p.xpath('.//w:t/text()',namespaces=NS))
    def poner(p,t):
        # Se mantienen las propiedades del párrafo y la primera tipografía.
        nodos=p.xpath('.//w:t',namespaces=NS)
        if not nodos:raise ValueError('El párrafo de la plantilla no tiene texto.')
        nodos[0].text=t
        for x in nodos[1:]:x.text=''
    def cambiar(indice,inicio,nuevo):
        if not texto(paras[indice]).startswith(inicio):
            raise ValueError('Cambió la estructura de la plantilla; revisar el anclaje '+inicio)
        poner(paras[indice],nuevo)

    # Estos son los únicos párrafos analíticos que dependen de la ventana GPP.
    cambiar(1,'IX EPF','IX EPF 2021–2022 y GlobalPetrolPrices de enero de 2025 a '+mes_final)
    cambiar(19,'Según la información',
        f'Según la información de GlobalPetrolPrices, entre el {principio} y el {final}, en Chile la bencina de referencia 95 pasó '
        f'de USD {es(a.loc["gasolina","usd_litro"],3)} a USD {es(b.loc["gasolina","usd_litro"],3)} por litro '
        f'({es((b.loc["gasolina","usd_litro"]/a.loc["gasolina","usd_litro"]-1)*100)}%); el diésel, '
        f'de USD {es(a.loc["diesel","usd_litro"],3)} a USD {es(b.loc["diesel","usd_litro"],3)} '
        f'({es((b.loc["diesel","usd_litro"]/a.loc["diesel","usd_litro"]-1)*100)}%).')
    cambiar(21,'Gráfico 3',
        f'Gráfico 3  Precios GPP publicados para Chile en USD/litro. {n} cortes semanales seleccionados, uno por mes; no promedios mensuales. '
        f'Último corte: {f1}. Sin IC ni marcas de significancia muestral para estos registros de precios. Fuente [4]; cálculo propio.')
    cambiar(24,'En marzo de 2025',
        f'En {mes_final}, Chile ocupa el puesto {int(b.loc["gasolina","puesto"])} en bencina 95 y el '
        f'{int(b.loc["diesel","puesto"])} en diésel, entre {npaises} países (1 = menor precio).')
    cambiar(26,'Gráfico 4',
        f'Gráfico 5  Puesto de Chile (1 = menor precio en USD/litro), en {n} cortes comunes y un universo fijo de '
        f'{npaises} países. Sin IC ni pruebas de significancia muestral para estos puestos. Fuente [4]; cálculo propio.')
    poner(paras[29],texto(paras[29]).replace('veinte cortes',str(n)+' cortes'))
    cambiar(30,'Bajo ese ajuste',
        f'Bajo ese ajuste, Chile pasa del puesto {int(pa.loc["gasolina","puesto_ppa"])} al {int(pb.loc["gasolina","puesto_ppa"])} '
        f'en bencina 95 y del {int(pa.loc["diesel","puesto_ppa"])} al {int(pb.loc["diesel","puesto_ppa"])} en diésel. '
        f'El puesto 1 corresponde al precio ajustado más bajo entre los mismos {npaises} países. Los puestos en USD se muestran en gris para facilitar la comparación.')
    poner(paras[32],texto(paras[32]).replace('Gráfico 5','Gráfico 6'))
    cambiar(34,'La actualización anual',
        f'Al mantener los factores de 2025 durante toda la ventana, Chile termina '
        f'{mes_final} en el puesto {int(pb.loc["gasolina","puesto_ppa_fijo_2025"])} en bencina y '
        f'{int(pb.loc["diesel","puesto_ppa_fijo_2025"])} en diésel. El Excel conserva ambas variantes, los factores originales, sus celdas y las fórmulas. [4, 8]')
    cambiar(42,'Los Excel respaldan',
        'Los Excel respaldan ambas medianas, el indicador, sus IC, covarianzas, pruebas, precios y fuentes de la curva GPP. '
        'Los scripts 01–11 incluyen instalación y renv.lock; actualizan y almacenan las fuentes antes de generar los productos. '
        'Se reproducen veinte celdas oficiales y el error estándar de ingreso del manual. '
        f'Actualización de fuentes: {fecha_es(cfg["consulta"])}; último precio publicado: {final}. [2, 3]')

    # La nueva figura usa la misma ubicación y dimensiones de la figura CNE.
    # Su pie explicita que no se observa el presupuesto de los hogares actuales.
    cap=deepcopy(paras[21]);captext=(
        'Gráfico 4  Cambio simulado del gasto mediano / ingreso mediano de los mismos hogares gastadores. '
        'Base: enero 2025, con mezcla de gastos e ingresos IX EPF; precios GPP en CLP. IC 95% puntuales, condicionados a precios. '
        '○: p Holm ≥0,05 frente al quintil anterior (4 pares por mes); ×: «No fiable», criterios adaptados. ')
    sin_dia=cfg['gpp']['clp']['referencias_sin_dia']
    if sin_dia:
        nombres=', '.join(MESES[int(m[5:7])-1]+' de '+m[:4] for m in sin_dia)
        captext+=nombres.capitalize()+' usa referencias GPP «hace un mes», sin día publicado. '
    captext+='No mide gasto actual. Fuentes [1, 2, 4–7].'
    poner(cap,captext);paras[23].addnext(cap)
    # Se reduce únicamente un párrafo vacío junto a la nueva figura para
    # mantener el pie completo en la misma página que el gráfico.
    for indice in [17,27]:
        if texto(paras[indice]).strip():continue
        pr=paras[indice].find('w:pPr',NS)
        if pr is None:pr=etree.SubElement(paras[indice],'{'+NS['w']+'}pPr')
        spacing=pr.find('w:spacing',NS)
        if spacing is None:spacing=etree.SubElement(pr,'{'+NS['w']+'}spacing')
        for key,value in [('before','0'),('after','0'),('line','20'),('lineRule','exact')]:spacing.set('{'+NS['w']+'}'+key,value)
    pr=cap.find('w:pPr',NS)
    if pr is None:pr=etree.SubElement(cap,'{'+NS['w']+'}pPr')
    keep=pr.find('w:keepLines',NS)
    if keep is None:keep=etree.SubElement(pr,'{'+NS['w']+'}keepLines')
    keep.set('{'+NS['w']+'}val','1')
    # Una reducción de altura acotada deja espacio para el nuevo pie sin
    # separarlo del gráfico. Se conserva el ancho original de la ilustración.
    for ex in paras[23].xpath('.//wp:extent | .//a:xfrm/a:ext',namespaces=NS):
        if ex.get('cy'):ex.set('cy',str(round(int(ex.get('cy'))*.86)))
    for ex in paras[31].xpath('.//wp:extent | .//a:xfrm/a:ext',namespaces=NS):
        if ex.get('cy') and ex.get('cx'):ex.set('cy',str(round(int(ex.get('cx'))*3.8/11)))
    # El salto en un párrafo vacío de la plantilla producía una página en
    # blanco. Se ancla al encabezado siguiente y se conserva la separación.
    if not texto(paras[36]).strip() and paras[36].xpath('.//w:br[@w:type="page"]',namespaces=NS):
        body.remove(paras[36])
        pr=paras[37].find('w:pPr',NS)
        if pr is None:pr=etree.SubElement(paras[37],'{'+NS['w']+'}pPr')
        br=pr.find('w:pageBreakBefore',NS)
        if br is None:br=etree.SubElement(pr,'{'+NS['w']+'}pageBreakBefore')
        br.set('{'+NS['w']+'}val','1')

    # Los hipervínculos ya existentes se mantienen; sus destinos finales se
    # actualizan a las páginas usadas y se añaden las dos fuentes CLP nacionales.
    rel=etree.fromstring(partes['word/_rels/document.xml.rels'])
    fuentes=json.loads((raiz/'gpp_fuentes.json').read_text())
    source={(f['date'],f['fuel']):f['archive_url'] for f in fuentes}
    mapping={'Gasolina inicial':source[(f0,'gasolina')],
             'Gasolina final':source[(f1,'gasolina')],'Diésel final':source[(f1,'diesel')]}
    links=paras[46].xpath('.//w:hyperlink',namespaces=NS)
    for h in links:
        label=''.join(h.xpath('.//w:t/text()',namespaces=NS));rid=h.get('{'+NS['r']+'}id')
        if label in mapping:
            for r in rel:
                if r.get('Id')==rid:r.set('Target',mapping[label])
    # Se modifica solo el texto bibliográfico inicial, preservando los links.
    primer=paras[46].find('.//w:t',NS)
    primer.text=(f'[4] GlobalPetrolPrices. Bencina 95 y diésel: {n} cortes internacionales comunes, {f0}–{f1}; '
        f'{npaises} países y {len(g)} precios. Precios CLP: {len(payload["escenario_gpp"]["precios_clp"])} referencias mensuales publicadas, '
        'con fecha y origen en Precios CLP del Excel. Historia: copias públicas archivadas; último corte: páginas vigentes del proveedor. '
        'Sin paginación. ')
    for label,url in [(' Precios nacionales CLP','https://www.globalpetrolprices.com/Chile/'),
                      (' Acceso y cobertura','https://www.globalpetrolprices.com/data_access.php')]:
        rid='rIdGPP'+str(len(rel)+1)
        rr=etree.SubElement(rel,'{'+NS['rel']+'}Relationship',Id=rid,
            Type=NS['r']+'/hyperlink',Target=url,TargetMode='External')
        h=etree.SubElement(paras[46],'{'+NS['w']+'}hyperlink');h.set('{'+NS['r']+'}id',rid)
        run=etree.SubElement(h,'{'+NS['w']+'}r');props=etree.SubElement(run,'{'+NS['w']+'}rPr')
        color=etree.SubElement(props,'{'+NS['w']+'}color');color.set('{'+NS['w']+'}val','245B7A')
        t=etree.SubElement(run,'{'+NS['w']+'}t');t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=label

    # Se reemplazan solamente las cuatro imágenes cuyo origen o período cambió.
    imagenes={'word/media/image6.png':fig.get('escenario_word',fig['escenario']),
              'word/media/image5.png':fig['precios'],'word/media/image4.png':fig['ranking'],
              'word/media/image2.png':fig.get('ranking_ppa_word',fig['ranking_ppa'])}
    for name,path in imagenes.items():partes[name]=Path(path).read_bytes()
    partes['word/document.xml']=etree.tostring(doc,xml_declaration=True,encoding='UTF-8',standalone=True)
    partes['word/_rels/document.xml.rels']=etree.tostring(rel,xml_declaration=True,encoding='UTF-8',standalone=True)
    destino.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destino,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in partes.items():z.writestr(name,data)
    print('Artículo actualizado preservando la plantilla del autor:',destino)


if __name__=='__main__':
    raiz=Path(__file__).resolve().parent;p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--resultados',type=Path,default=raiz/'resultados/resultados.json')
    p.add_argument('--word',type=Path,default=raiz/'resultados/Articulo_LinkedIn_combustibles_Chile_actualizado.docx')
    a=p.parse_args();crear_articulo(a.resultados.resolve(),a.word.resolve())
