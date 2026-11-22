# Combustibles y presupuesto de los hogares en Chile

Análisis reproducible del gasto en gasolina y diésel para transporte personal,
basado en la **IX Encuesta de Presupuestos Familiares (EPF 2021–2022)** del INE.
Relaciona el gasto mediano con el ingreso mediano de los mismos hogares que
declaran gasto y lo complementa con precios de **GlobalPetrolPrices (GPP)**,
rankings entre 17 países y un ajuste anual aproximado por PPA del PIB del FMI.

[Leer el artículo](https://alejandrohenriquezr.github.io/combustibles/) ·
[Metodología](documentacion/metodologia.md) ·
[Instalación detallada](documentacion/instalacion.md) ·
[Fuentes y datos](documentacion/fuentes.md)

## Qué hace

1. Prepara un entorno Python local y restaura los paquetes R fijados en `renv.lock`.
2. Consulta fuentes oficiales y reconstruye los cortes públicos disponibles de GPP.
3. Calcula dominios de hogares gastadores, medianas y controles contra tabulados INE.
4. Estima IC del 95%, precisión y contrastes con bootstrap conjunto en R.
5. Genera dos Excel, gráficos, el artículo Word, su versión HTML y un ZIP de respaldo.

La relación de medianas **no es la mediana del porcentaje individual de gasto**.
La EPF describe hogares urbanos de 2021–2022. La curva con precios posteriores
es un escenario con ingresos y consumo de referencia; no mide el gasto observado
de los hogares en 2025–2026. El artículo publicado indica su propia fecha de corte.

## Instalación y ejecución

Requisitos previos: **Git, CPython 3.12 de 64 bits y R 4.5.0**. Instalar R
desde [CRAN](https://cran.r-project.org/bin/windows/base/old/4.5.0/).
En Windows, las versiones archivadas de algunos paquetes R pueden requerir
[Rtools45](https://cran.r-project.org/bin/windows/Rtools/rtools45/rtools.html).
El programa instala paquetes; no instala el lenguaje Python, R ni Rtools.

```bash
git clone https://github.com/alejandrohenriquezr/combustibles.git
cd combustibles
python ejecutar.py
```

En Windows, si `python` apunta a otra versión:

```powershell
py -3.12 ejecutar.py
```

En Linux/macOS, usar `python3.12 ejecutar.py`. No es necesario activar `.venv`:
la entrada selecciona su intérprete y lo utiliza en los subprocesos. La primera
ejecución crea `Codigo/.venv` y restaura R. Después reutiliza ambos entornos.
Si existe un entorno incompleto, restaurarlo con `--solo-instalar`.

**El único archivo que se usa para ejecutar el proyecto completo es
[`ejecutar.py`](ejecutar.py).** Los scripts de `Codigo/` son etapas internas.

| Operación | Comando desde la raíz |
| --- | --- |
| Instalar/restaurar dependencias sin analizar datos | `python ejecutar.py --solo-instalar` |
| Verificar dependencias sin descargar fuentes | `python ejecutar.py --verificar` |
| Ejecutar pruebas | `python ejecutar.py --pruebas` |
| Actualizar fuentes y generar todos los productos | `python ejecutar.py` |
| Reproducir un respaldo local sin actualizar fuentes | `python ejecutar.py --reproducir-sin-actualizar` |
| Reconstruir la web desde el Word existente | `python ejecutar.py --actualizar-web` |
| Mostrar opciones | `python ejecutar.py --help` |

El modo sin actualizar requiere originales, extracciones y comprobante locales
coherentes. **Un clon de GitHub no contiene esos datos.** El modo normal los
descarga; la reconstrucción pública de GPP depende de las capturas disponibles y
puede requerir historial autorizado del proveedor si hay meses sin cobertura.
Nunca se presentan datos antiguos como una actualización de fuentes fallida.

## Dónde queda cada archivo

```text
ejecutar.py                    Entrada única
Codigo/
  configuracion.base.json      URLs, controles y parámetros de referencia
  gpp_fuentes.base.json        Metadatos de páginas de partida, no precios
  modulos/                    Cálculo, fuentes, entorno, gráficos y web
  flujo.py                    Coordinación interna de las etapas
  tests/                      Pruebas y auditorías de resultados
  plantillas/articulo_base.docx  Plantilla editorial necesaria
  requisitos.txt              Versiones directas de Python
  renv.lock                   Versiones de R y sus paquetes
  datos/                      Originales descargados (solo local)
  resultados/                 Excel, Word, CSV y gráficos (solo local)
  diagnosticos/               Registros de instalación y R (solo local)
documentacion/                Instalación, método, fuentes y mantenimiento
docs/                         Artículo estático para GitHub Pages
.github/workflows/            Pruebas y publicación de Pages
```

`Codigo/configuracion.json`, las extracciones CSV, los manifiestos y los entornos
se crean o actualizan localmente. `.gitignore` excluye bases, hojas de cálculo,
salidas, cachés, registros, respaldos y secretos. La plantilla Word y los gráficos
del artículo en `docs/assets/` sí se versionan porque son necesarios para el
proyecto y la publicación. La ejecución puede modificar `docs/`: se revisan y
publican esos cambios deliberadamente con Git; el análisis no hace `git push`.

El ZIP de respaldo es un producto **local** que incluye fuentes de datos para
reproducir la ejecución. No debe añadirse al repositorio ni a GitHub Pages.

## Documentación

- [Instalación, opciones y resolución de problemas](documentacion/instalacion.md).
- [Método estadístico e interpretación](documentacion/metodologia.md).
- [Fuentes, trazabilidad y límites de reconstrucción](documentacion/fuentes.md).
- [Arquitectura y productos](documentacion/arquitectura.md).
- [Publicar y mantener GitHub Pages](documentacion/github-pages.md).
- [Validación completa y correcciones de Windows](documentacion/validacion.md).
- [Cambios de la preparación del repositorio](CHANGELOG.md).

## Pruebas

Las pruebas unitarias usan ejemplos pequeños y no necesitan descargar las bases
INE. Las auditorías de la curva requieren productos y originales locales; si no
existen, se informan como omitidas. La prueba real de R es opcional y está
documentada en la guía de instalación. GitHub Actions ejecuta las pruebas en un
clon limpio, comprueba enlaces locales y evita que se incorporen bases a Git.

Las fuentes conservan sus propias condiciones de uso. La disponibilidad pública
del código no cambia las licencias de INE, GPP, FMI ni de los paquetes utilizados.
Este repositorio no declara una licencia abierta adicional sobre el código.
