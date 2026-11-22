"""Actualiza precios públicos GPP y conserva cada respuesta original.

Los precios semanales actuales se obtienen directamente del proveedor. El
historial público se reconstruye con copias archivadas de SUS páginas: no es
una descarga de la base comercial completa ni un promedio de todas las semanas.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

from lxml import html
import pandas as pd

PAISES = {
    'Argentina': ('ARG', 'Argentina'), 'Bolivia': ('BOL', 'Bolivia'),
    'Brazil': ('BRA', 'Brasil'), 'Chile': ('CHL', 'Chile'),
    'Colombia': ('COL', 'Colombia'), 'Costa-Rica': ('CRI', 'Costa Rica'),
    'Dominican-Republic': ('DOM', 'República Dominicana'), 'Ecuador': ('ECU', 'Ecuador'),
    'El-Salvador': ('SLV', 'El Salvador'), 'Guatemala': ('GTM', 'Guatemala'),
    'Honduras': ('HND', 'Honduras'), 'Mexico': ('MEX', 'México'),
    'Nicaragua': ('NIC', 'Nicaragua'), 'Panama': ('PAN', 'Panamá'),
    'Paraguay': ('PRY', 'Paraguay'), 'Peru': ('PER', 'Perú'), 'Uruguay': ('URY', 'Uruguay')}


def guardar_json(path, obj):
    """Escribe un archivo completo mediante reemplazo atómico."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.part')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)


class Repositorio:
    """Cachea solo copias históricas inmutables; las páginas vigentes se descargan."""
    def __init__(self, datos):
        self.base=Path(datos)/'originales/gpp';self.base.mkdir(parents=True,exist_ok=True)
        self.indice=self.base/'indice.json'
        self.cache=json.loads(self.indice.read_text()) if self.indice.exists() else {}
        self.consultas=[]

    def obtener(self, url):
        """Almacena bytes, fecha UTC, URL y huella antes de analizarlos."""
        pasado='/web/' in url and 'web.archive.org' in url
        if pasado and url in self.cache:
            meta=self.cache[url];p=self.base/meta['archivo'];raw=p.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=meta['sha256']:
                raise ValueError('La copia histórica almacenada fue modificada.')
            return raw,meta
        req=urllib.request.Request(url,headers={'User-Agent':'EPF-GPP-investigacion-reproducible/2.0',
                                               'Accept-Encoding':'identity'})
        with urllib.request.urlopen(req,timeout=55) as response:raw=response.read()
        digest=hashlib.sha256(raw).hexdigest();p=self.base/(digest+'.html')
        p.write_bytes(raw)
        meta=dict(url=url,archivo=p.name,sha256=digest,bytes=len(raw),
                  consulta_utc=dt.datetime.now(dt.timezone.utc).isoformat())
        self.cache[url]=meta;self.consultas.append(meta)
        return raw,meta

    def terminar(self):
        """El índice permite auditar una copia sin sobrescribir su contenido."""
        guardar_json(self.indice,self.cache)


def arbol(raw):
    """Reconoce la compresión de algunos archivos históricos antes de leer HTML."""
    return html.fromstring(gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw)


def numero(texto):
    """Las tablas de GPP usan punto decimal y coma de miles en los datos."""
    return float(re.sub(r'[^0-9.\-]','',texto.replace(',','')))


def fecha_titulo(tree):
    """Lee la fecha publicada, que puede diferir de la fecha de la captura."""
    # Los metadatos incluyen fechas ISO aunque la página esté traducida.
    contenido=' '.join(tree.xpath('//title/text()')+tree.xpath('//meta/@content'))
    iso=re.findall(r'\b20\d{2}-\d{2}-\d{2}\b',contenido)
    if iso:return max(iso)
    texto=' '.join(tree.xpath('//title/text()'))
    nombres={'ene':'Jan','enero':'Jan','feb':'Feb','marzo':'Mar','mar':'Mar','abr':'Apr',
             'abril':'Apr','mayo':'May','jun':'Jun','jul':'Jul','agosto':'Aug','ago':'Aug',
             'sept':'Sep','sep':'Sep','oct':'Oct','nov':'Nov','dic':'Dec'}
    m=re.search(r'(\d{2})-([A-Za-z]+)-(20\d{2})',texto)
    if not m:raise ValueError('Fecha GPP no identificada: '+texto)
    mes=nombres.get(m[2].lower(),m[2].title())
    return dt.datetime.strptime(f'{m[1]}-{mes}-{m[3]}','%d-%b-%Y').date().isoformat()


def analizar_mundial(raw):
    """Lee etiquetas y valores impresos; nunca digitaliza anchos de barras."""
    tree=arbol(raw);fecha=fecha_titulo(tree)
    unidad=' '.join(tree.xpath('//*[@id="titleGraphic"]//text()'))
    if 'U.S. Dollar' not in unidad or not any(s in unidad for s in ['liter','litro']):
        raise ValueError('La comparación no está expresada en USD/litro.')
    links=tree.xpath('//*[@id="outsideLinks"]//a')
    bars=tree.xpath('//*[@id="graphic"]/div/div[div]')
    if len(links)!=len(bars):raise ValueError('No coinciden países y precios.')
    rows=[]
    for link,bar in zip(links,bars):
        key=urllib.parse.urlsplit(link.get('href')).path.strip('/').split('/')[0]
        if key in PAISES:
            iso,pais=PAISES[key]
            rows.append(dict(fecha=fecha,iso=iso,pais=pais,usd_litro=numero(bar.text_content())))
    if len(rows)!=len(PAISES):raise ValueError('Faltan países del universo fijo LATAM.')
    return fecha,rows


def analizar_chile(raw):
    """Extrae la tabla nacional, con fechas explícitas, CLP y USD simultáneos."""
    tree=arbol(raw);rows=[]
    for fuel,slug in [('gasolina','gasoline'),('diesel','diesel')]:
        trs=tree.xpath(f'//tr[.//a[contains(@href,"/Chile/{slug}_prices")]]')
        for tr in trs:
            cells=[' '.join(' '.join(td.itertext()).split()) for td in tr.xpath('./td')]
            if len(cells)!=3:continue
            try:fecha=dt.datetime.strptime(cells[0],'%d.%m.%Y').date().isoformat()
            except ValueError:continue
            rows.append(dict(fecha=fecha,mes=fecha[:7],combustible=fuel,
                clp_litro=numero(cells[1]),usd_litro=numero(cells[2]),
                precision_fecha='Día publicado',origen='Tabla nacional CLP/USD'))
    if len(rows)!=2:raise ValueError('La tabla nacional debe incluir gasolina y diésel.')
    # La cabecera CLP evita confundir el precio local con otra moneda.
    if 'CLP' not in tree.text_content():raise ValueError('No se identifica la moneda CLP.')
    return rows


def analizar_comparacion_mes(raw, fuel):
    """Conserva una referencia mensual publicada sin inventar su día exacto.

    GPP publica «hace un mes». Se registra el mes anterior y la fecha de la
    publicación de esa comparación; no se presume una fecha semanal exacta.
    """
    tree=arbol(raw);publicacion=fecha_titulo(tree)
    if int(publicacion[8:10])>28:
        raise ValueError('Referencia «hace un mes» a fin de mes: no se asigna un mes ambiguo sin fecha publicada.')
    if 'CLP' not in tree.text_content():raise ValueError('La página no identifica CLP.')
    for tr in tree.xpath('//tr'):
        cells=[' '.join(' '.join(td.itertext()).split()) for td in tr.xpath('./td')]
        if len(cells)>=2 and cells[0] in ('One month ago','Hace un mes'):
            periodo=str(pd.Period(publicacion[:7],freq='M')-1)
            return dict(fecha='',mes=periodo,combustible=fuel,clp_litro=numero(cells[1]),
                usd_litro=None,precision_fecha='Mes de la comparación; día no publicado',
                fecha_publicacion=publicacion,origen='Referencia publicada «hace un mes»')
    raise ValueError('La tabla no publica una comparación mensual reconocida.')


def consultar_cdx(repo, url, inicio, fin):
    """Consulta de nuevo el catálogo público; almacena su respuesta íntegra."""
    params=urllib.parse.urlencode(dict(url=url,output='json',filter='statuscode:200',
        **{'from':inicio.replace('-',''),'to':fin.replace('-',''),'collapse':'timestamp:8'}))
    raw,meta=repo.obtener('https://web.archive.org/cdx/search/cdx?'+params)
    filas=json.loads(raw)
    if not filas:return []
    return [dict(timestamp=r[1],original_url=r[2]) for r in filas[1:]]


def recuperar(repo, registro):
    """Devuelve contenido y trazabilidad de una página histórica seleccionada."""
    ts=registro['timestamp'];original=registro['original_url']
    url=f'https://web.archive.org/web/{ts}id_/{original}'
    raw,meta=repo.obtener(url)
    return raw,{**meta,**registro,'archive_url':f'https://web.archive.org/web/{ts}/{original}'}


def actualizar(raiz, datos):
    """Actualiza primero fuentes y luego publica extracciones normalizadas completas."""
    raiz,datos=Path(raiz),Path(datos);cfg=json.loads((raiz/'configuracion.json').read_text())
    inicio=cfg['gpp'].get('inicio','2025-01-01')
    hoy=dt.datetime.now(dt.timezone.utc).date().isoformat();repo=Repositorio(datos)
    fuentes=[];mundiales=[];locales=[];errores=[]
    try:
        # Las tres páginas vigentes se descargan siempre: ningún error de red
        # permite presentar una extracción vieja como una actualización exitosa.
        for fuel,slug in [('gasolina','gasoline'),('diesel','diesel')]:
            url=f'https://www.globalpetrolprices.com/{slug}_prices/'
            raw,meta=repo.obtener(url);fecha,rows=analizar_mundial(raw)
            fuente={**meta,'date':fecha,'fuel':fuel,'timestamp':meta['consulta_utc'],
                'title':' '.join(arbol(raw).xpath('//title/text()')),
                'original_url':url,'archive_url':url}
            fuentes.append(fuente)
            mundiales.extend({**r,'combustible':fuel,'url':url,'sha256_html':meta['sha256']} for r in rows)
        url='https://www.globalpetrolprices.com/Chile/'
        raw,meta=repo.obtener(url)
        locales.extend({**r,'url':url,'sha256_html':meta['sha256'],
                        'publicacion':r['fecha']} for r in analizar_chile(raw))
        # Las páginas vigentes descargadas en ejecuciones anteriores también
        # son originales almacenados. Se vuelven a analizar, para no perder el
        # último corte de un mes cuando el proveedor pasa al mes siguiente.
        historial_local=datos/'gpp_chile_registros.json'
        if historial_local.exists():
            registros_previos=json.loads(historial_local.read_text())
            versiones={(r['url'],r['sha256_html']) for r in registros_previos
                if r['url'].startswith('https://www.globalpetrolprices.com/Chile/')}
            for url_anterior,sha in versiones:
                raw_anterior=(repo.base/(sha+'.html')).read_bytes()
                if hashlib.sha256(raw_anterior).hexdigest()!=sha:raise ValueError('Original CLP histórico modificado.')
                locales.extend({**r,'url':url_anterior,'sha256_html':sha,
                    'publicacion':r['fecha']} for r in analizar_chile(raw_anterior))
        fin=min(r['fecha'] for r in mundiales)
        meses=list(pd.period_range(inicio[:7],fin[:7],freq='M').astype(str))

        # Las cuarenta páginas del respaldo previo se vuelven a ANALIZAR desde
        # su HTML original. El CSV congelado nunca es la fuente del nuevo cálculo.
        semillas=json.loads((raiz/'gpp_fuentes.json').read_text())
        for f in semillas:
            if 'web.archive.org/web/' in f['archive_url']:
                raw,meta=recuperar(repo,f)
                fecha,rows=analizar_mundial(raw);fuel=f['fuel']
                fuel={'gas':'gasolina'}.get(fuel,fuel)
                fuente={**meta,'date':fecha,'fuel':fuel,'title':' '.join(arbol(raw).xpath('//title/text()'))}
                fuentes.append(fuente)
                mundiales.extend({**r,'combustible':fuel,'url':meta['archive_url'],
                                  'sha256_html':meta['sha256']} for r in rows)
            else:
                # No se confía en el CSV previo: se reabre y verifica el HTML
                # original de la página que entonces estaba vigente.
                sha=f['sha256'];original=repo.base/(sha+'.html')
                if not original.exists():
                    # Un clon nuevo no incluye las bases. El catálogo CDX que se
                    # consulta a continuación puede recuperar ese mes; si no,
                    # el control de cobertura detiene el flujo sin imputar datos.
                    errores.append({'url':f['archive_url'],'error':'Original histórico local ausente; se busca el mes en CDX.'})
                    continue
                raw=original.read_bytes()
                if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('Original mundial histórico modificado.')
                fecha,rows=analizar_mundial(raw);fuel=f['fuel'];fuentes.append(f)
                mundiales.extend({**r,'combustible':fuel,'url':f['archive_url'],
                                  'sha256_html':sha} for r in rows)

        # Los índices se consultan en cada ejecución; se añaden los meses que
        # todavía no tienen un corte internacional común para los dos combustibles.
        for fuel,slug in [('gasolina','gasoline'),('diesel','diesel')]:
            catalogo=consultar_cdx(repo,f'www.globalpetrolprices.com/{slug}_prices/',inicio,hoy)
            existentes={r['fecha'][:7] for r in mundiales if r['combustible']==fuel}
            for r in catalogo:
                if r['timestamp'][:4]+'-'+r['timestamp'][4:6] in existentes:continue
                try:
                    raw,meta=recuperar(repo,r);fecha,rows=analizar_mundial(raw)
                    fuentes.append({**meta,'date':fecha,'fuel':fuel,'title':' '.join(arbol(raw).xpath('//title/text()'))})
                    mundiales.extend({**v,'combustible':fuel,'url':meta['archive_url'],
                                      'sha256_html':meta['sha256']} for v in rows)
                except Exception as exc:errores.append({'url':r['original_url'],'captura':r['timestamp'],'error':str(exc)})

        # El catálogo Chile incluido es un punto de partida trazable. Se consulta
        # nuevamente cada URL de tabla nacional, por idioma, para descubrir novedades.
        catalogo=json.loads((raiz/'catalogo_chile.json').read_text())
        urls=sorted({r['original_url'] for r in catalogo if urllib.parse.urlsplit(r['original_url']).path.lower().rstrip('/')=='/chile'})
        def un_indice(url):
            try:return url,consultar_cdx(repo,url,inicio,hoy),None
            except Exception as exc:return url,[],str(exc)
        with ThreadPoolExecutor(max_workers=4) as pool:
            for url,registros,error in pool.map(un_indice,urls):
                catalogo.extend(registros)
                if error:errores.append({'url':url,'error':error})
        print('GPP: catálogos históricos consultados; verificando tablas CLP.',flush=True)
        unicos={(r['timestamp'],r['original_url']):r for r in catalogo}
        nacionales=[r for r in unicos.values() if urllib.parse.urlsplit(r['original_url']).path.lower().rstrip('/')=='/chile']
        por_mes={}
        for r in nacionales:por_mes.setdefault(r['timestamp'][:6],[]).append(r)
        seleccion=[]
        for rr in por_mes.values():
            rr=sorted(rr,key=lambda r:r['timestamp']);seleccion.extend(rr[-3:]+rr[:1])
        seleccion=list({(r['timestamp'],r['original_url']):r for r in seleccion}.values())
        def una_local(r):
            try:
                raw,meta=recuperar(repo,r)
                return [{**v,'url':meta['archive_url'],'sha256_html':meta['sha256'],
                         'publicacion':v['fecha']} for v in analizar_chile(raw)]
            except Exception as exc:
                return [{'error':str(exc),'url':r['original_url'],'captura':r['timestamp']}]
        with ThreadPoolExecutor(max_workers=4) as pool:
            for registros in pool.map(una_local,seleccion):
                for r in registros:
                    if 'error' in r:errores.append(r)
                    else:locales.append(r)

        # Si falta un mes, se usa únicamente el dato que GPP publica como
        # «hace un mes». La fecha exacta queda vacía y la limitación queda visible.
        conocidos={r['mes'] for r in locales}
        for mes in set(meses)-conocidos:
            siguiente=str(pd.Period(mes,freq='M')+1).replace('-','')
            for fuel,slug in [('gasolina','gasoline'),('diesel','diesel')]:
                rr=[r for r in unicos.values() if slug+'_prices' in r['original_url'] and r['timestamp'].startswith(siguiente)
                    and urllib.parse.urlsplit(r['original_url']).hostname in ['www.globalpetrolprices.com','es.globalpetrolprices.com']]
                for r in sorted(rr,key=lambda r:r['timestamp']):
                    try:
                        raw,meta=recuperar(repo,r);v=analizar_comparacion_mes(raw,fuel)
                        if v['mes']==mes:
                            locales.append({**v,'url':meta['archive_url'],'sha256_html':meta['sha256'],
                                            'publicacion':v['fecha_publicacion']});break
                    except Exception as exc:errores.append({'url':r['original_url'],'error':str(exc)})

        # Un solo corte internacional semanal común por mes, universo fijo. No
        # se promedian capturas ni se rellenan meses con el dato de otro mes.
        g=pd.DataFrame(mundiales);g=g[(g.fecha>=inicio)&(g.fecha<=fin)]
        conflictos=g.groupby(['fecha','combustible','iso']).usd_litro.nunique()
        # El proveedor puede revisar un país durante la semana sin cambiar la
        # fecha del encabezado. Se conserva la última captura COMPLETA del corte,
        # y las versiones anteriores permanecen almacenadas para contrastarlas.
        if (conflictos>1).any():
            claves=set(conflictos[conflictos>1].index)
            guardar_json(datos/'gpp_revisiones_publicadas.json',
              {'regla':'Última captura completa por fecha y combustible, sin mezclar páginas.',
               'registros':g[[tuple(x) in claves for x in g[['fecha','combustible','iso']].to_numpy()]].to_dict('records')})
        ahora=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')
        ordenes={(f['date'],f['fuel'],f['sha256']):re.sub(r'\D','',f['timestamp'])[:14] for f in fuentes}
        g['_orden']=[ordenes.get((r.fecha,r.combustible,r.sha256_html),ahora) for r in g.itertuples(index=False)]
        g=g.sort_values('_orden').drop_duplicates(['fecha','combustible','iso'],keep='last').drop(columns='_orden')
        pares=g.groupby('fecha').agg(n=('usd_litro','size'),fuels=('combustible','nunique'))
        fechas=pares[(pares.n==2*len(PAISES))&(pares.fuels==2)].index
        elegidas=pd.Series(fechas,index=fechas.str[:7]).groupby(level=0).max().to_list()
        if sorted({f[:7] for f in elegidas})!=meses:
            raise ValueError('No hay un corte mundial común por cada mes solicitado; se requiere ampliar las capturas o usar el historial autorizado GPP.')
        g=g[g.fecha.isin(elegidas)].sort_values(['fecha','combustible','iso']).reset_index(drop=True)
        g['puesto']=g.groupby(['fecha','combustible']).usd_litro.rank(method='min').astype(int)

        # La curva doméstica conserva su propia fecha y precisión de fecha por
        # combustible. Los precios en USD nunca sustituyen los precios en CLP.
        loc=pd.DataFrame(locales);sal=[]
        for mes in meses:
            m=loc[loc.mes==mes];exact=m[m.fecha.ne('')]
            comun=exact.groupby('fecha').combustible.nunique()
            fechas_comunes=comun[comun==2].index
            datos_mes=m[m.fecha==max(fechas_comunes)] if len(fechas_comunes) else m
            row={'mes':mes}
            for fuel in ['gasolina','diesel']:
                fuelrows=datos_mes[datos_mes.combustible==fuel]
                if fuelrows.empty:raise ValueError(f'Falta precio GPP CLP {fuel}, {mes}. No se genera un gráfico con valores imputados.')
                r=fuelrows.sort_values(['fecha','publicacion']).iloc[-1]
                for src,dst in [('clp_litro',fuel+'_clp'),('fecha','fecha_'+fuel),('origen','origen_'+fuel),
                                ('url','url_'+fuel),('sha256_html','sha256_'+fuel),('precision_fecha','precision_'+fuel),('publicacion','publicacion_'+fuel)]:row[dst]=r[src]
            sal.append(row)
        local=pd.DataFrame(sal)
        if local[['gasolina_clp','diesel_clp']].isna().any().any():raise ValueError('Precio CLP ausente.')
        if (local[['gasolina_clp','diesel_clp']]<=0).any().any():raise ValueError('Precio CLP no positivo.')

        # Solo después de superar cobertura y unidades se reemplazan los datos
        # normalizados. Un fallo conserva los resultados anteriores identificados.
        g.to_csv(raiz/'gpp_precios.csv',index=False)
        local.to_csv(raiz/'gpp_chile_clp.csv',index=False)
        claves_usadas={(r.fecha,r.combustible,r.sha256_html) for r in g.itertuples(index=False)}
        fuentes=[f for f in fuentes if (f['date'],f['fuel'],f['sha256']) in claves_usadas]
        fuentes.sort(key=lambda f:re.sub(r'\D','',f['timestamp'])[:14])
        fuentes=list({(f['date'],f['fuel'],f['archive_url']):f for f in fuentes}.values())
        guardar_json(raiz/'gpp_fuentes.json',fuentes)
        guardar_json(datos/'gpp_chile_registros.json',locales)
        guardar_json(datos/'gpp_consultas_sin_datos.json',errores)
        cfg['gpp'].update(inicio=inicio,periodo=f'{min(elegidas)}–{max(elegidas)}',
            paises=len(PAISES),observaciones=len(g),cortes=len(elegidas),
            sha256=hashlib.sha256((raiz/'gpp_precios.csv').read_bytes()).hexdigest(),
            consulta_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
            metodo='Un corte semanal común por mes; no promedio mensual. Páginas GPP actuales y copias públicas archivadas; 1=menor precio.')
        cfg['gpp']['clp']={'archivo':'gpp_chile_clp.csv','meses':len(local),
            'sha256':hashlib.sha256((raiz/'gpp_chile_clp.csv').read_bytes()).hexdigest(),
            'referencias_sin_dia':local[local.fecha_gasolina.eq('')|local.fecha_diesel.eq('')].mes.tolist()}
        guardar_json(raiz/'configuracion.json',cfg)
        informe={'consulta_utc':cfg['gpp']['consulta_utc'],'inicio':inicio,'fin':max(elegidas),
            'mes_actual_incompleto':max(elegidas)[:7]==hoy[:7],
            'cortes_internacionales':len(elegidas),'precios_internacionales':len(g),'meses_clp':len(local),
            'actualizacion':'Páginas vigentes descargadas del proveedor; historia reconstruida desde originales archivados, sin interpolación.',
            'comparaciones_sin_dia':cfg['gpp']['clp']['referencias_sin_dia']}
        informe.update(sha256_precios=cfg['gpp']['sha256'],sha256_clp=cfg['gpp']['clp']['sha256'])
        guardar_json(datos/'manifiesto_gpp.json',informe)
        print(json.dumps(informe,ensure_ascii=False),flush=True)
        return informe
    finally:repo.terminar()
