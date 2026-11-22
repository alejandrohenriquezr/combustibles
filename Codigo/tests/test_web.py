"""La conversión debe conservar contenido y enlaces sin publicar los datos."""
from pathlib import Path
import tempfile
import unittest
import zipfile

from modulos.web import exportar_articulo


class Web(unittest.TestCase):
    def test_exportacion_conserva_tabla_enlace_imagen_y_escapa_texto(self):
        doc = '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
          xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><w:body>
          <w:p><w:r><w:t>Artículo &amp; evidencia</w:t></w:r></w:p>
          <w:p><w:r><w:t>EPF</w:t></w:r></w:p>
          <w:p><w:r><w:t>Texto &lt;seguro&gt;</w:t></w:r><w:hyperlink r:id="link"><w:r><w:t>Fuente</w:t></w:r></w:hyperlink></w:p>
          <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Quintil</w:t></w:r></w:p></w:tc></w:tr>
          <w:tr><w:tc><w:p><w:r><w:t>I</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
          <w:p><w:r><w:drawing><a:blip r:embed="image"/></w:drawing></w:r></w:p>
          <w:p><w:r><w:t>Gráfico 1: Indicador. Fuente INE.</w:t></w:r></w:p>
          </w:body></w:document>'''
        relaciones = '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="link" Target="https://www.ine.gob.cl/"/>
          <Relationship Id="image" Target="media/image1.png"/></Relationships>'''
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            word = raiz / "articulo.docx"
            with zipfile.ZipFile(word, "w") as z:
                z.writestr("word/document.xml", doc)
                z.writestr("word/_rels/document.xml.rels", relaciones)
                z.writestr("word/media/image1.png", b"imagen-de-prueba")
            destino = raiz / "docs"
            destino.mkdir()
            (destino / "estilos.css").write_text("body{}")
            exportar_articulo(word, destino)
            html = (destino / "index.html").read_text(encoding="utf-8")
            self.assertIn("Texto &lt;seguro&gt;", html)
            self.assertIn('href="https://www.ine.gob.cl/"', html)
            self.assertIn('<th scope="col">Quintil</th>', html)
            self.assertIn("<td>I</td>", html)
            self.assertEqual((destino / "assets/grafico-1.png").read_bytes(), b"imagen-de-prueba")
            self.assertEqual((destino / "estilos.css").read_text(), "body{}")
            self.assertFalse((destino / "articulo.docx").exists())

    def test_word_invalido_no_reemplaza_la_pagina_anterior(self):
        with tempfile.TemporaryDirectory() as temporal:
            raiz = Path(temporal)
            destino = raiz / "docs"
            destino.mkdir()
            (destino / "index.html").write_text("edición anterior")
            word = raiz / "invalido.docx"
            word.write_bytes(b"no es un Word")
            with self.assertRaises(zipfile.BadZipFile):
                exportar_articulo(word, destino)
            self.assertEqual((destino / "index.html").read_text(), "edición anterior")
