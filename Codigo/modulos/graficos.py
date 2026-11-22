"""Gráficos reproducibles con los IC 95% calculados por calidad y survey."""
from pathlib import Path
import datetime as dt

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd
from modulos.ppa import leer_factores, calcular_ppa


def es(v, n=1):
    """El formato español solo se aplica a las etiquetas, sin alterar los datos."""
    return f"{v:,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def crear_graficos(payload, carpeta):
    """El porcentaje principal relaciona las dos medianas del mismo grupo gastador."""
    carpeta=Path(carpeta);carpeta.mkdir(parents=True,exist_ok=True)
    colores=["#D96B25","#B68C30","#39848F","#858894","#34566D"]
    roman=["I","II","III","IV","V"]
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10.5,
                         "axes.spines.top":False,"axes.spines.right":False})
    stats={(r["grupo"],r["indicador"]):r for r in payload["precision"]
           if r["segmentacion"]=="Quintil" and r["combustible"]=="gasolina_diesel"}
    def ejes(ax):
        ax.grid(axis="y",color="#E5E8EB",lw=.7);ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False);ax.spines["bottom"].set_color("#BAC4CC")
        ax.tick_params(length=0,pad=7)
    def marca(q,indicador):
        # La marca pertenece a la comparación con el quintil anterior, del mismo indicador.
        test=next((r for r in payload['contrastes'] if r['indicador']==indicador and
                   int(r['grupo_a'])==q-1 and int(r['grupo_b'])==q),None)
        ns='†' if test and test['marca_grafico']=='†' else ''
        nf='‡' if stats[(str(q),indicador)]['clasificacion']=='No fiable' else ''
        return ns+nf
    def guardar(fig,nombre):
        # Dos formatos exportables; ambos conservan IC y notas completos.
        archivo=carpeta/nombre
        fig.savefig(archivo.with_suffix('.png'),dpi=250,facecolor='white')
        fig.savefig(archivo.with_suffix('.svg'),facecolor='white');plt.close(fig)
        return archivo.with_suffix('.png')
    salidas={};x=np.arange(5)
    meses_es=['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic']
    def etiquetas_temporales(ax,fechas,cantidad=7):
        # Los extremos y el número de meses se derivan de los datos actualizados.
        ix=np.unique(np.linspace(0,len(fechas)-1,min(cantidad,len(fechas)),dtype=int))
        ax.set_xticks([fechas[i] for i in ix],
          [meses_es[fechas[i].month-1]+' '+str(fechas[i].year)[2:] for i in ix])
    for ind,clave,nombre,ylabel in [
      ('relacion_medianas','indicador','indicador_mediano_ic95','Gasto mediano / ingreso mediano'),
      ('gasto_mediano','gasto','gasto_mediano_ic95','Gasto mediano en combustibles (CLP)'),
      ('ingreso_mediano','ingreso','ingreso_mediano_ic95','Ingreso mediano de gastadores (CLP)')]:
        fig,ax=plt.subplots(figsize=(10.5,3.9))
        datos=[stats[(str(i+1),ind)] for i in range(5)]
        escala=100 if clave=='indicador' else 1
        v=np.array([r['estimacion'] for r in datos])*escala
        lo=np.array([r['li95'] for r in datos])*escala;hi=np.array([r['ls95'] for r in datos])*escala
        ax.bar(x,v,width=.55,color=colores[4],yerr=np.vstack([np.maximum(0,v-lo),np.maximum(0,hi-v)]),
               error_kw={'ecolor':'#26343E','capsize':4,'elinewidth':1.2})
        margen=max(hi)*.025
        for i in range(5):
            label=es(v[i],1)+'%' if escala==100 else '$'+es(v[i],0)
            ax.text(i,hi[i]+margen,label+marca(i+1,ind),ha='center',va='bottom',weight='bold',fontsize=10)
        ax.set_ylim(0,max(hi)*1.15);ax.set_xticks(x,['Quintil '+q for q in roman]);ax.set_ylabel(ylabel)
        ax.yaxis.set_major_formatter(FuncFormatter((lambda v,p:es(v,1)+'%') if escala==100 else (lambda v,p:'$'+es(v,0))))
        ejes(ax)
        fig.text(.045,.068,'† Diferencia con el quintil anterior no significativa: p de Holm ≥ 0,05 (4 pares por indicador). No prueba igualdad.',fontsize=8)
        fig.text(.045,.030,'‡ Baja precisión: «No fiable» con criterios n/gl/CV de calidad adaptados. IC 95% bootstrap conjunto; mismos hogares.',fontsize=8)
        fig.tight_layout(rect=(0,.13,1,1),pad=1)
        salidas[clave]=guardar(fig,nombre)

    # La curva usa precios GPP en CLP y la misma relación de medianas del
    # artículo. Sus bandas son IC puntuales, condicionados a los precios.
    if 'escenario_gpp' in payload:
        serie=pd.DataFrame(payload['escenario_gpp']['serie'])
        fig,ax=plt.subplots(figsize=(11,4.65))
        for q,color,estilo in zip(range(1,6),colores,['-','-','--','--','-']):
            s=serie[serie.quintil==q].sort_values('mes')
            f=[dt.date.fromisoformat(v+'-01') for v in s.mes]
            y=s.estimacion.to_numpy(float)*100
            ax.fill_between(f,s.li95.to_numpy(float)*100,s.ls95.to_numpy(float)*100,color=color,alpha=.11,lw=0)
            ax.plot(f,y,color=color,lw=2.1,ls=estilo,label='Quintil '+roman[q-1])
            ns=s.marca_no_significativa.eq('○').to_numpy();nf=s.marca_no_fiable.eq('×').to_numpy()
            if ns.any():ax.scatter(np.asarray(f)[ns],y[ns],s=19,facecolors='white',edgecolors=color,linewidths=.85,zorder=5)
            if nf.any():ax.scatter(np.asarray(f)[nf],y[nf],s=28,color=color,marker='x',linewidths=1.3,zorder=6)
            if q in (1,5):
                label=es(y[-1],2)+'%'
                if s.clasificacion.iloc[-1] in ['Poco fiable','No fiable']:label+='\n'+s.clasificacion.iloc[-1]
                ax.annotate(label,(f[-1],y[-1]),xytext=(8,0),textcoords='offset points',
                    color=color,weight='bold',va='center',fontsize=9)
        ax.axhline(0,color='#9CA9B4',lw=.9);ejes(ax)
        ax.set_ylabel('Cambio del gasto mediano / ingreso mediano\nde referencia')
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:es(v,1)+'%'))
        etiquetas_temporales(ax,f);ax.margins(x=.045)
        ax.set_xlim(f[0]-dt.timedelta(days=12),f[-1]+dt.timedelta(days=52))
        ax.legend(loc='upper center',bbox_to_anchor=(.5,1.17),frameon=False,ncol=5,fontsize=9.5)
        fig.text(.045,.151,'Bandas: IC 95% puntuales del bootstrap EPF, condicionados a precios GPP. Base: enero 2025. No mide gasto actual.',fontsize=7.8)
        fig.text(.045,.109,'○ Diferencia con el quintil anterior no significativa: p Holm ≥ 0,05 (4 pares por mes); no demuestra igualdad.',fontsize=7.8)
        fig.text(.045,.067,'× «No fiable»: criterios n/gl/CV de calidad adaptados. El cero inicial es la base, sin prueba de comparación.',fontsize=7.8)
        fig.text(.045,.025,'Fuente de precios: GlobalPetrolPrices, CLP/litro; cortes publicados, no promedios mensuales. Fechas y referencias en Excel.',fontsize=7.8)
        fig.tight_layout(rect=(0,.21,1,1),pad=1)
        # En Word las notas se escriben en un pie de figura legible y editable;
        # se conserva además el PNG/SVG completo para uso independiente.
        completo=carpeta/'escenario_gpp_ic95'
        fig.savefig(completo.with_suffix('.png'),dpi=250,facecolor='white')
        fig.savefig(completo.with_suffix('.svg'),facecolor='white')
        salidas['escenario']=completo.with_suffix('.png')
        for t in fig.texts:t.set_visible(False)
        fig.set_size_inches(11,3.9);fig.tight_layout(rect=(0,0,1,1),pad=1)
        word=carpeta/'escenario_gpp_word.png';fig.savefig(word,dpi=250,facecolor='white')
        salidas['escenario_word']=word
        plt.close(fig)

    # GlobalPetrolPrices es la única fuente de precios. Sus registros publicados
    # no tienen IC EPF ni contrastes muestrales atribuibles a este análisis.
    gpp=pd.read_csv(Path(__file__).resolve().parents[1]/'gpp_precios.csv')
    chile=gpp[gpp.iso=='CHL'];fechas=sorted(chile.fecha.unique());fechas_dt=[dt.date.fromisoformat(f) for f in fechas]
    n_paises=gpp.iso.nunique()
    for clave,columna,ylabel in [('ranking','puesto','Puesto de Chile · 1 = menor precio'),('precios','usd_litro','USD por litro')]:
        fig,ax=plt.subplots(figsize=(10.5,3.75))
        for fuel,label,color in [('gasolina','Bencina 95',colores[4]),('diesel','Diésel',colores[0])]:
            df=chile[chile.combustible==fuel].set_index('fecha').loc[fechas]
            vals=df[columna].to_numpy(float)
            ax.plot(fechas_dt,vals,color=color,label=label,lw=2.2,marker='o',markersize=3.5)
            for i,offset in [(0,(0,11)),(len(vals)-1,(0,-16 if fuel=='diesel' else 10))]:
                ax.annotate(es(vals[i],0 if clave=='ranking' else 3),(fechas_dt[i],vals[i]),xytext=offset,
                            textcoords='offset points',ha='center',color=color,weight='bold',fontsize=10)
        ejes(ax);ax.set_ylabel(ylabel)
        if clave=='ranking':ax.set_ylim(.5,n_paises+.8);ax.set_yticks(range(1,n_paises+1,2));ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:es(v,0)))
        else:ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:es(v,2)))
        etiquetas_temporales(ax,fechas_dt)
        ax.legend(loc='upper center',bbox_to_anchor=(.5,1.16),frameon=False,ncol=2)
        fig.text(.045,.045,f'Fuente: GlobalPetrolPrices. {len(fechas)} cortes semanales comunes; {n_paises} países. No son promedios mensuales.',fontsize=8)
        fig.text(.045,.009,'IC y marcas de significancia o fiabilidad no aplican: son registros de precios y puestos, sin diseño muestral declarado.',fontsize=8)
        fig.tight_layout(rect=(0,.10,1,1),pad=1)
        salidas[clave]=guardar(fig,'gpp_'+clave)
    # Un segundo ranking usa los mismos precios GPP y un factor auxiliar anual
    # del FMI. La PPA del PIB no se interpreta como salario ni como gasto EPF.
    raiz=Path(__file__).resolve().parents[1]
    ppa=calcular_ppa(gpp,leer_factores(raiz));chi=ppa[ppa.iso=='CHL']
    fig,axes=plt.subplots(1,2,figsize=(11,4.7),sharey=True)
    for ax,(fuel,titulo,color) in zip(axes,[('gasolina','Bencina 95',colores[4]),('diesel','Diésel',colores[0])]):
        serie=chi[chi.combustible==fuel].set_index('fecha').loc[fechas]
        ax.plot(fechas_dt,serie.puesto,color='#8A929A',linestyle='--',lw=1.7,marker='o',markersize=3,label='Precio en USD')
        ax.plot(fechas_dt,serie.puesto_ppa,color=color,lw=2.3,marker='o',markersize=3.8,label='Ajuste PPA anual')
        for col,c in [('puesto','#747C84'),('puesto_ppa',color)]:
            for i in [0,len(fechas)-1]:
                ax.annotate(str(int(serie[col].iloc[i])),(fechas_dt[i],serie[col].iloc[i]),xytext=(0,8),
                            textcoords='offset points',ha='center',color=c,weight='bold',fontsize=10)
        ejes(ax);ax.set_title(titulo,fontsize=12,weight='bold',pad=12)
        ax.set_ylim(.5,n_paises+.8);ax.set_yticks([1,5,9,13,17]);ax.tick_params(labelleft=True)
        etiquetas_temporales(ax,fechas_dt,5)
        ax.axvline(dt.date(2026,1,1),color='#BAC4CC',lw=.9,zorder=0)
        ax.legend(loc='lower center',bbox_to_anchor=(.5,1.13),frameon=False,ncol=2,fontsize=9)
    axes[0].set_ylabel('Puesto de Chile · 1 = menor precio')
    fig.text(.035,.125,f'Fuentes: precios GlobalPetrolPrices; factor auxiliar FMI, WEO octubre 2026. {n_paises} países y {len(fechas)} cortes comunes.',fontsize=8)
    fig.text(.035,.080,'Aproximación con PPA anual del PIB, fija dentro del año; 2026 incorpora proyecciones. Línea vertical: cambio de factor anual.',fontsize=8)
    fig.text(.035,.035,'No usa el tipo de cambio de cada fecha ni mide ingreso de hogares. Sin IC muestral; †/‡ corresponden a las estimaciones EPF.',fontsize=8)
    fig.tight_layout(rect=(0,.19,1,.96),pad=1.1,w_pad=2)
    full=carpeta/'gpp_ranking_ppa'
    fig.savefig(full.with_suffix('.png'),dpi=250,facecolor='white')
    fig.savefig(full.with_suffix('.svg'),facecolor='white')
    salidas['ranking_ppa']=full.with_suffix('.png')
    # Word ya incluye estas notas como texto editable debajo de la figura.
    # La versión sin notas repetidas evita desplazar un párrafo a una página sola.
    for t in fig.texts:t.set_visible(False)
    fig.set_size_inches(11,3.8);fig.tight_layout(rect=(0,0,1,.96),pad=1.1,w_pad=2)
    word=carpeta/'gpp_ranking_ppa_word.png';fig.savefig(word,dpi=250,facecolor='white')
    salidas['ranking_ppa_word']=word;plt.close(fig)
    return salidas
