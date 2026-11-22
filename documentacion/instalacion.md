# Instalación y uso

## Preparar el equipo

Instalar Git, CPython 3.12 de 64 bits y R **4.5.0**. La versión de R está fijada
en `Codigo/renv.lock` y se comprueba antes de descargar datos. No sustituirla por
otra versión sin revisar y validar el bloqueo. Python 3.13/3.15 tampoco se
reutilizan como si fueran 3.12.

- Python: [descargas oficiales](https://www.python.org/downloads/).
- R 4.5.0 para Windows: [archivo oficial CRAN](https://cran.r-project.org/bin/windows/base/old/4.5.0/).
- Compilación de paquetes R en Windows: [Rtools45](https://cran.r-project.org/bin/windows/Rtools/rtools45/rtools.html).
- Linux/macOS: instalar esa versión de R y las herramientas de compilación y
  bibliotecas del sistema que soliciten los paquetes. El instalador del proyecto
  no administra paquetes del sistema operativo.

Se necesitan conexión a Internet, espacio para al menos varios cientos de MB de
fuentes originales, los entornos y sus respaldos, y permisos de escritura sobre
la carpeta del proyecto. En carpetas sincronizadas conviene esperar a que los
archivos estén disponibles localmente. La instalación R puede tardar si compila.

```powershell
git clone https://github.com/alejandrohenriquezr/combustibles.git
cd combustibles
py -3.12 ejecutar.py --solo-instalar
py -3.12 ejecutar.py --verificar
py -3.12 ejecutar.py
```

En Linux/macOS reemplazar `py -3.12` por `python3.12`. Los comandos admiten rutas
con espacios. El programa no requiere activar scripts de PowerShell ni cambiar
su política de ejecución. El entorno Python se crea en `Codigo/.venv`; R usa su
biblioteca `renv` por proyecto. No se incluyen esos binarios en GitHub.

## Seleccionar R o el índice de paquetes

```powershell
py -3.12 ejecutar.py --solo-instalar --rscript "C:\Program Files\R\R-4.5.0\bin\Rscript.exe"
py -3.12 ejecutar.py --rscript "C:\Program Files\R\R-4.5.0\bin\Rscript.exe"
```

También se respeta la variable `RSCRIPT`. Una selección explícita incorrecta
produce un error; no se sustituye silenciosamente. Para quitar una selección
anterior solo de la sesión PowerShell: `Remove-Item Env:RSCRIPT`.

El instalador utiliza wheels Python (`--only-binary=:all:`); no compila NumPy o
SciPy. Conserva el índice configurado en pip. Si se desea PyPI directamente:

```powershell
py -3.12 ejecutar.py --solo-instalar --indice https://pypi.org/simple
```

Las URL de índices de esta opción deben ser HTTPS sin credenciales. Los problemas
de pip quedan en `Codigo/diagnosticos/diagnostico_instalacion.json`. La
verificación R deja stdout, stderr, etapa y código de salida en
`Codigo/diagnosticos/verificacion_R.log`. Ambos archivos quedan excluidos de Git.

Si Python ya está preparado, `python ejecutar.py --solo-instalar --solo-r`
restaura únicamente R, sin repetir la instalación Python.

## Opciones del análisis

```powershell
# Actualización normal; se detiene si falla una fuente requerida.
py -3.12 ejecutar.py

# Reproducción explícita del respaldo local, sin nueva consulta de fuentes.
py -3.12 ejecutar.py --reproducir-sin-actualizar

# Rutas propias; las rutas relativas se interpretan desde el directorio actual.
py -3.12 ejecutar.py --datos "D:\datos\combustibles" --salida "D:\salidas\combustibles"

# Restaurar antes de ejecutar, si cambiaron requisitos o falta algún paquete.
py -3.12 ejecutar.py --instalar
```

Los archivos de una reproducción deben pertenecer a una misma ejecución:
`datos/`, extracciones `gpp_*.csv` y `ppa_factores_anuales.csv`, configuración
local y `actualizacion_fuentes.json`. Se contrastan huellas antes de usarlos.
Un respaldo incoherente o incompleto detiene el flujo.

Las salidas se elaboran en `.resultados_en_proceso_*`. Al completar las etapas,
la salida anterior se conserva en `resultados_anteriores/`. Si falla el
empaquetado se restaura la salida anterior como principal. Los precios o la
configuración local pueden haber sido actualizados aunque falle un paso
posterior; el Word anterior y sus fechas siguen identificando su propia edición.

## Pruebas y comprobación de un clon

```powershell
py -3.12 ejecutar.py --pruebas
```

La suite requiere los paquetes Python. En un clon sin `.venv`, el modo de pruebas
normal prepara los entornos igual que el análisis. Para CI o un entorno Python
ya administrado, instalar `Codigo/requisitos.txt` en ese entorno y usar
`python ejecutar.py --pruebas --sin-instalar`; este modo no necesita R.

Las auditorías de integración de la curva se omiten si faltan sus datos locales.
Para agregar la verificación real de R en PowerShell:

```powershell
$env:EPF_RSCRIPT_PRUEBA = "C:\Program Files\R\R-4.5.0\bin\Rscript.exe"
py -3.12 ejecutar.py --pruebas
```

No se confunde una prueba omitida con una reproducción completa de la estadística.

## Artículo web

```powershell
py -3.12 ejecutar.py --actualizar-web
py -3.12 ejecutar.py --actualizar-web --articulo "ruta\al\articulo.docx"
```

Este modo usa solo la biblioteca estándar: no necesita instalar Python packages,
R ni descargar datos. Conserva el texto, las tablas, los hipervínculos y los
gráficos del Word seleccionado. No recalcula ni inventa cifras. Para publicar,
revisar y subir los cambios de `docs/` según la [guía de Pages](github-pages.md).

## Errores frecuentes

| Mensaje o situación | Acción |
| --- | --- |
| Se requiere CPython 3.12 de 64 bits | Elegir `py -3.12` o `python3.12` y comprobar arquitectura. |
| R incompatible o no encontrado | Instalar R 4.5.0 y seleccionar su `Rscript`. |
| Faltan paquetes R o la biblioteca no existe | Ejecutar `--solo-instalar` con el R correcto. |
| No matching distribution found | Revisar versión, arquitectura, red e índice de pip; no quitar la exigencia de wheels. |
| HTTP 403, timeout o faltan cortes GPP | Revisar disponibilidad del proveedor y de Internet Archive. No interpolar ni usar precios USD en lugar de CLP. |
| Falta comprobante en modo sin actualizar | Recuperar el respaldo completo o ejecutar una actualización normal. |
| Fallo de controles o de huellas | Conservar el error y los originales; investigar la revisión de fuentes antes de continuar. |
