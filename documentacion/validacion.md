# Validación del 22 de noviembre de 2026

## Entorno y ejecución

Se completó una reproducción en Windows con CPython **3.12.10**, R **4.5.0**,
renv **1.3.1**, calidad **0.8.2** y survey **4.4-2**. Se restauraron los 75
paquetes del bloqueo sin modificar sus versiones.

```powershell
py -3.12 ejecutar.py --reproducir-sin-actualizar
```

La ejecución terminó con código de salida 0 y generó ambos Excel, el artículo
Word, gráficos, la web y el ZIP de respaldo. Se utilizaron las fuentes locales
verificadas: consulta registrada del 22 de noviembre de 2026 y último corte GPP
del 16 de noviembre. **Esta validación no hizo una nueva descarga de fuentes.**

## Resultados de las comprobaciones

| Comprobación | Resultado |
| --- | --- |
| Hogares procesados | 15.134 |
| Controles oficiales de estimaciones | 20 coincidentes |
| Error estándar de ingreso de control | 18.082,3858; gl = 3.320 |
| Dominios / intervalos / contrastes principales | 48 / 144 / 30 |
| Curva GPP | 23 meses y cinco quintiles |
| Suite local con las dos pruebas de R real activadas | 43 pruebas aprobadas; ninguna omitida |
| Integridad del ZIP | 321 archivos contrastados con sus SHA-256 |
| Tamaño del ZIP validado | 57.558.692 bytes |

Las auditorías recalcularon los puntos de la curva de forma independiente,
contrastaron sus intervalos contra los percentiles de las réplicas y verificaron
las marcas de precisión y significancia. El respaldo incluye la entrada única,
documentación y fuentes; excluye los entornos instalados. Las rutas del
manifiesto utilizan `/` tanto en Windows como en Linux.

Los registros quedan localmente en `Codigo/diagnosticos/pruebas.log` y
`Codigo/diagnosticos/reproduccion_completa.log`; no se suben a GitHub.

## Compatibilidad de Windows corregida

La ejecución real detectó dos problemas de codificación que las verificaciones
de paquetes por sí solas no detectaban: el BOM del CSV se incorporaba al nombre
del ponderador `fe`, y una locale Unix `C.UTF-8` heredada por R en Windows
alteraba las marcas Unicode al exportarlas. Se declaró la lectura
`UTF-8-BOM` y se omite esa locale incompatible únicamente en los subprocesos R
de Windows. Se conserva la configuración regional válida del usuario.

Se comprobó además con R real el ciclo de escritura y lectura de `†`, `○` y `×`.
Referencia técnica: [R Data Import/Export, codificación y BOM](https://www.stat.ethz.ch/R-manual/R-devel/doc/manual/R-data.html).

## Clon limpio y publicación

El [flujo de pruebas](https://github.com/alejandrohenriquezr/combustibles/actions/workflows/pruebas.yml)
comprueba Windows y Linux con un clon sin bases ni bibliotecas R. Las cuatro
auditorías de datos y las dos pruebas de R real se omiten de forma explícita en
ese entorno; no equivalen a una ejecución completa de R en Linux.

El [flujo de Pages](https://github.com/alejandrohenriquezr/combustibles/actions/workflows/pages.yml)
publica solo `docs/`. Se verificó el sitio público y la correspondencia del HTML,
CSS, metadatos y gráficos consultados con los archivos versionados. Git y los
controles de CI excluyen bases, resultados, ZIP y entornos.

La futura reconstrucción de precios sigue dependiendo de la cobertura pública
de GPP e Internet Archive, como se explica en [fuentes](fuentes.md).
