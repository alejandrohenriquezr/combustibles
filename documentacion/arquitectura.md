# Arquitectura y productos

`ejecutar.py` resuelve rutas, prepara dependencias y selecciona el modo de trabajo.
`Codigo/flujo.py` coordina las etapas internas utilizando el mismo intérprete
Python y la misma instalación R en todos los subprocesos.

| Etapa interna | Responsabilidad |
| --- | --- |
| `01_instalar_dependencias.py` | CPython 3.12, entorno local, wheels y diagnóstico. |
| `02_instalar_paquetes.R` | Arranque de renv y restauración del bloqueo con R 4.5.0. |
| `12_verificar_entorno.R` y `modulos/entorno.py` | Versiones y carga real de paquetes antes del cálculo. |
| `03_descargar_fuentes.py` | Descarga, revisiones, huellas y comprobante completo. |
| `modulos/fuentes_gpp.py` | Páginas vigentes, capturas históricas y controles de cobertura. |
| `04_recalcular_combustibles.py` y `modulos/epf_calculos.py` | Hogares, factores, dominios, puntos y controles INE. |
| `05_intervalos_calidad.R` y `06_integrar_intervalos.py` | Bootstrap, IC, covarianzas, precisión y validación de puntos. |
| `07_exportar_excel.py` y `09_respaldo_epf_gpp.py` | Excel, gráficos y respaldo de fuentes y fórmulas. |
| `modulos/ppa.py` | Extracción anual WEO, ajuste y sensibilidad PPA. |
| `10_articulo_linkedin.py` | Actualiza dependencias numéricas de la plantilla editorial Word. |
| `modulos/web.py` | Exporta el Word final a HTML estático con tablas, enlaces e imágenes. |
| `11_empaquetar.py` | ZIP local, manifiesto SHA-256 y fuentes para reproducción. |

La plantilla Word tiene anclajes editoriales comprobados. Cambiar la estructura
de sus párrafos requiere revisar el generador; un anclaje cambiado debe detener
el proceso en lugar de sustituir texto equivocado.

## Productos locales

- `IX_EPF_combustibles_hogares_con_gasto.xlsx`: estimaciones, controles y precisión.
- `Respaldo_combustibles_EPF_GPP.xlsx`: medianas, IC, precios, PPA y fuentes.
- `Articulo_LinkedIn_combustibles_Chile_actualizado.docx`: artículo actualizado.
- CSV, JSON, réplicas, `sessionInfo_R.txt` y gráficos para auditoría.
- `Paquete_combustibles_EPF_GPP_actualizado.zip`: respaldo completo local.

El sitio `docs/` se deriva del Word final: no consulta bases en el navegador,
no calcula estadísticas y no requiere Node, servidor de aplicación o claves.
`docs/articulo.json` registra la huella del Word convertido y del contenido.
El CSS permanece separado de la exportación para conservar el diseño al actualizar.

## Seguridad de publicación

`.gitignore` se aplica desde la raíz e impide agregar los formatos de bases y las
carpetas de ejecución. No usar `git add -f` con datos ni respaldos. Git no aplica
un ignore a archivos ya versionados; CI comprueba también la lista de archivos
rastreada y rechaza las bases. La comprobación web revisa enlaces locales para
detectar imágenes o estilos faltantes.

Los cambios de `docs/` se revisan y publican con Git. Ningún modo de `ejecutar.py`
cambia la visibilidad del repositorio, hace push o publica por su cuenta.
