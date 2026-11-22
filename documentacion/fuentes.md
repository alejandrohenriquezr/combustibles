# Fuentes y trazabilidad

`Codigo/configuracion.base.json` contiene URLs oficiales, controles estadísticos,
edición WEO y huellas de referencia. La primera ejecución copia ese archivo a
`Codigo/configuracion.json`; las actualizaciones se escriben en la copia local,
que está excluida de Git. Para cambiar parámetros permanentes, editar la base y
revisar también la copia local existente: no se sobreescribe automáticamente.

## INE: IX EPF 2021–2022

Se descargan Personas, Gastos, CCIF y tabulados desde las URL oficiales de la
configuración. El [manual de uso en R](https://www.ine.gob.cl/docs/default-source/encuesta-de-presupuestos-familiares/manuales/ix-epf-(octubre-2021---septiembre-2022)/manual-de-uso-de-bases-de-datos-ix-epf-(lenguaje-r).pdf)
explica cobertura (p. 10), mensualización (pp. 13–14), diseño (pp. 19–21), grupos
(pp. 72–79) y calidad (pp. 80–84).

Cada actualización consulta el servidor original. Si responde HTTP 304, se
comprueba la huella local; una respuesta 304 no significa omitir la consulta.
Las revisiones se conservan y deben superar de nuevo los controles.

## GlobalPetrolPrices

- [Gasolina](https://www.globalpetrolprices.com/gasoline_prices/).
- [Diésel](https://www.globalpetrolprices.com/diesel_prices/).
- [Precios nacionales de Chile](https://www.globalpetrolprices.com/Chile/).
- [Acceso y cobertura](https://www.globalpetrolprices.com/data_access.php).

La historia comercial completa requiere autorización del proveedor. El proyecto
reconstruye la alternativa pública mediante capturas de las páginas originales
en Internet Archive y páginas vigentes GPP. Registra URL, fecha de consulta,
fecha publicada, precisión temporal y SHA-256; no obtiene precios desde imágenes.

`gpp_fuentes.base.json` y `catalogo_chile.json` contienen metadatos para localizar
páginas de partida. No contienen la base de precios ni sustituyen las descargas.
La ejecución vuelve a consultar catálogos públicos. Si una página antigua que
antes era vigente no está en un clon local, se busca el mes en el catálogo CDX.
Si no hay cobertura, el proceso se detiene. **Clonar el repositorio no garantiza
recuperar todo el historial que estuvo disponible cuando se escribió el artículo.**

El universo fijo comprende Argentina, Bolivia, Brasil, Chile, Colombia, Costa
Rica, Ecuador, El Salvador, Guatemala, Honduras, México, Nicaragua, Panamá,
Paraguay, Perú, República Dominicana y Uruguay.

## FMI

Se usa el [WEO de octubre de 2026](https://data.imf.org/-/media/iData/External-Storage/Documents/0FA3DC49A04D446E9D69DBEB29979E1C/en/WEOOct2026all.xlsx),
hoja `Countries`, para factores anuales del PIB. Las celdas, series y estados de
estimación/proyección quedan en la extracción local y en los Excel. El FMI no
es la fuente de precios de combustibles. Cambiar de edición exige registrar URL,
título y metadatos, y validar los nuevos resultados.

## Datos fuera de Git

Se excluyen originales, microdatos procesados, extracciones de precios y PPA,
réplicas bootstrap, Excel y respaldos. Permanecen en `Codigo/datos/`,
`Codigo/resultados/` y los archivos locales de extracción. El ZIP final contiene
esos insumos para reproducir una ejecución y debe conservarse fuera de GitHub.
La publicación solo utiliza texto y gráficos del artículo en `docs/`.

Las condiciones de uso de los proveedores siguen aplicando a cada fuente.
