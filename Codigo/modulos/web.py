"""Exportación estática del artículo Word, sin bases de datos ni servicios externos."""
from __future__ import annotations

import hashlib
from html import escape
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}
REPOSITORIO = "https://github.com/alejandrohenriquezr/combustibles"
SITIO = "https://alejandrohenriquezr.github.io/combustibles/"
SECCIONES = (
    "Cuánto representa el gasto mediano frente al ingreso mediano",
    "La evolución del precio y del puesto de Chile",
    "Cómo cambia el ranking al ajustar por PPA",
    "Cómo leer los intervalos y las marcas",
)


def texto(nodo):
    return "".join(n.text or "" for n in nodo.iter("{" + NS["w"] + "}t"))


def identificador(titulo):
    normal = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", normal).strip("-")


def inline(nodo, relaciones):
    """Conserva enlaces y énfasis; escapa siempre el texto del documento."""
    tag = nodo.tag.rsplit("}", 1)[-1]
    if tag == "t":
        return escape(nodo.text or "")
    if tag == "br":
        return "<br>"
    if tag == "tab":
        return " "
    if tag in ("pPr", "rPr", "drawing", "pict"):
        return ""
    contenido = "".join(inline(n, relaciones) for n in nodo)
    if tag == "r":
        if nodo.find("w:rPr/w:b", NS) is not None:
            contenido = "<strong>" + contenido + "</strong>"
        if nodo.find("w:rPr/w:i", NS) is not None:
            contenido = "<em>" + contenido + "</em>"
    if tag == "hyperlink":
        enlace = relaciones.get(nodo.get("{" + NS["r"] + "}id"), "")
        if enlace.startswith(("https://", "http://")):
            contenido = '<a href="' + escape(enlace, quote=True) + '">' + contenido + "</a>"
    return contenido


def exportar_articulo(articulo, destino):
    """Genera HTML, tablas, imágenes y metadatos desde un Word final existente.

    La generación usa un directorio temporal; un Word inválido conserva la web anterior.
    No copia microdatos, Excel, CSV ni el Word al sitio público.
    """
    articulo, destino = Path(articulo), Path(destino)
    if not articulo.is_file():
        raise FileNotFoundError("Falta el artículo final: " + str(articulo))
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".web_", dir=destino.parent) as temporal:
        carpeta = Path(temporal)
        assets = carpeta / "assets"
        assets.mkdir()
        with zipfile.ZipFile(articulo) as z:
            doc = ET.fromstring(z.read("word/document.xml"))
            rels = ET.fromstring(z.read("word/_rels/document.xml.rels"))
            relaciones = {r.get("Id"): r.get("Target", "") for r in rels}
            body = doc.find("w:body", NS)
            parrafos = body.findall("w:p", NS)
            if len(parrafos) < 3:
                raise ValueError("El artículo debe tener título, subtítulo y contenido.")
            titulo, subtitulo = texto(parrafos[0]), texto(parrafos[1])
            partes, enlaces, imagenes = [], [], {}
            fuentes = False
            contenido_texto = []
            nodos = list(body)
            for indice, nodo in enumerate(nodos):
                if nodo in parrafos[:2]:
                    continue
                if nodo.tag == "{" + NS["w"] + "}tbl":
                    filas = []
                    for i, fila in enumerate(nodo.findall("w:tr", NS)):
                        celdas = []
                        for celda in fila.findall("w:tc", NS):
                            etiqueta = "th" if i == 0 else "td"
                            alcance = ' scope="col"' if i == 0 else ""
                            valor = "<br>".join(inline(p, relaciones) for p in celda.findall("w:p", NS))
                            celdas.append(f"<{etiqueta}{alcance}>{valor}</{etiqueta}>")
                            contenido_texto.append(texto(celda))
                        filas.append("<tr>" + "".join(celdas) + "</tr>")
                    partes.append('<div class="tabla" role="region" aria-label="Medianas por quintil" tabindex="0"><table><caption>Gasto e ingreso de los mismos hogares gastadores</caption>' + "".join(filas) + "</table></div>")
                    continue
                if nodo.tag != "{" + NS["w"] + "}p":
                    continue
                valor = texto(nodo).strip()
                for dibujo in nodo.findall(".//a:blip", NS):
                    rid = dibujo.get("{" + NS["r"] + "}embed")
                    target = relaciones.get(rid, "")
                    ruta = PurePosixPath("word") / target
                    if ".." in ruta.parts or not target.startswith("media/"):
                        raise ValueError("Relación de imagen inesperada en Word.")
                    extension = ruta.suffix.lower()
                    if extension not in (".png", ".jpg", ".jpeg", ".gif"):
                        raise ValueError("Formato de imagen no soportado: " + extension)
                    if rid not in imagenes:
                        nombre = "grafico-" + str(len(imagenes) + 1) + extension
                        (assets / nombre).write_bytes(z.read(str(ruta)))
                        imagenes[rid] = "assets/" + nombre
                    cercanos = nodos[max(0, indice - 1):indice] + nodos[indice + 1:indice + 3]
                    pie = next((texto(p) for p in cercanos if texto(p).startswith("Gráfico")), "Gráfico del artículo sobre combustibles")
                    alt = re.split(r"\. |Fuentes? ", pie)[0].strip()
                    url = imagenes[rid]
                    partes.append(f'<figure><a href="{url}" aria-label="Ampliar: {escape(alt, quote=True)}"><img src="{url}" alt="{escape(alt, quote=True)}" loading="lazy" decoding="async"></a></figure>')
                if not valor:
                    continue
                contenido_texto.append(valor)
                contenido = inline(nodo, relaciones)
                if valor in SECCIONES:
                    ancla = identificador(valor)
                    enlaces.append((ancla, valor))
                    partes.append(f'<h2 id="{ancla}">{escape(valor)}</h2>')
                elif re.match(r"^\[\d+\]", valor):
                    if not fuentes:
                        partes.append('<h2 id="fuentes">Fuentes y referencias</h2>')
                        enlaces.append(("fuentes", "Fuentes y referencias"))
                        fuentes = True
                    numero = re.match(r"^\[(\d+)\]", valor).group(1)
                    partes.append(f'<p class="referencia" id="fuente-{numero}">{contenido}</p>')
                else:
                    clase = "entrada" if nodo is parrafos[2] else "pie" if valor.startswith(("Gráfico", "IC 95%", "Pesos mensuales", "*:")) else ""
                    partes.append(f'<p class="{clase}">{contenido}</p>')
            if not imagenes:
                raise ValueError("El artículo no contiene gráficos para la web.")
        navegacion = "".join(f'<a href="#{ancla}">{escape(titulo_enlace)}</a>' for ancla, titulo_enlace in enlaces)
        html = f'''<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(titulo)} · Combustibles</title>
  <meta name="description" content="Gasto en combustibles e ingresos de los hogares en Chile: evidencia de la IX EPF, precios GlobalPetrolPrices, intervalos y ajuste PPA.">
  <meta name="theme-color" content="#102d40">
  <meta property="og:title" content="{escape(titulo, quote=True)}">
  <meta property="og:description" content="{escape(subtitulo, quote=True)}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{SITIO}">
  <meta property="og:image" content="{SITIO}{next(iter(imagenes.values()))}">
  <link rel="canonical" href="{SITIO}">
  <link rel="stylesheet" href="estilos.css">
</head>
<body>
<a class="saltar" href="#articulo">Saltar al artículo</a>
<header class="cabecera">
  <nav class="barra" aria-label="Principal"><a class="marca" href="./">Combustibles<span>Chile</span></a><a href="{REPOSITORIO}">Código y documentación</a></nav>
  <div class="hero"><p class="etiqueta">HOGARES · PRECIOS · EVIDENCIA</p><h1>{escape(titulo)}</h1><p class="subtitulo">{escape(subtitulo)}</p><p class="edicion">Análisis reproducible · Fuentes y método abiertos a revisión</p></div>
</header>
<div class="lectura">
  <aside class="indice"><p>En este artículo</p><nav aria-label="Contenido">{navegacion}</nav><a class="reproducir" href="{REPOSITORIO}#instalación-y-ejecución">Reproducir el análisis</a></aside>
  <main id="articulo">
    <div class="metodo"><strong>Qué se mide</strong><p>El gasto mediano en combustible dividido por el ingreso mediano de los mismos hogares que declaran gasto. Los montos EPF corresponden a 2021–2022. La curva con precios posteriores es un escenario; no mide el presupuesto observado de hogares actuales.</p></div>
    <article>{''.join(partes)}</article>
    <section class="replicar" aria-labelledby="replicar"><p class="etiqueta">ANÁLISIS REPRODUCIBLE</p><h2 id="replicar">Del artículo al código</h2><p>Una entrada coordina la instalación, la descarga de fuentes, los controles estadísticos y la generación de Word, Excel, gráficos y esta página.</p><pre><code>git clone {REPOSITORIO}.git
cd combustibles
python ejecutar.py</code></pre><p>Requiere CPython 3.12 de 64 bits y R 4.5.0. Los datos se descargan de sus proveedores; la disponibilidad de las capturas públicas condiciona la reconstrucción histórica.</p><a href="{REPOSITORIO}">Ver instalación, metodología y fuentes</a></section>
  </main>
</div>
<footer><div><strong>Combustibles · Chile</strong><p>IX EPF · GlobalPetrolPrices · FMI</p></div><p>Esta página conserva el artículo y sus gráficos.<br>Los microdatos y archivos de trabajo quedan fuera del sitio.</p><a href="{REPOSITORIO}">Repositorio en GitHub</a></footer>
</body></html>'''
        (carpeta / "index.html").write_text(html, encoding="utf-8")
        (carpeta / ".nojekyll").touch()
        (carpeta / "articulo.json").write_text(json.dumps({
            "titulo": titulo, "subtitulo": subtitulo,
            "sha256_word": hashlib.sha256(articulo.read_bytes()).hexdigest(),
            "sha256_contenido": hashlib.sha256("\n".join(contenido_texto).encode()).hexdigest(),
            "graficos": len(imagenes), "origen": "Artículo Word final; no se actualizan cifras al convertir a HTML",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        instalar_web(carpeta, destino)
    return destino / "index.html"


def instalar_web(origen, destino):
    """Sustituye solo archivos generados; conserva CSS y otros archivos del sitio."""
    origen, destino = Path(origen), Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    for nombre in ("index.html", ".nojekyll", "articulo.json"):
        src = origen / nombre
        if src.exists():
            tmp = destino / (nombre + ".part")
            shutil.copy2(src, tmp)
            os.replace(tmp, destino / nombre)
    (destino / "assets").mkdir(exist_ok=True)
    for src in (origen / "assets").glob("grafico-*.*"):
        shutil.copy2(src, destino / "assets" / src.name)
