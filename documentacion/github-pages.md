# GitHub Pages

Dirección del artículo:
<https://alejandrohenriquezr.github.io/combustibles/>

El sitio estático vive en `docs/`. El flujo `.github/workflows/pages.yml` sube
solo esa carpeta y publica con GitHub Pages. Las bases y productos locales no
se incluyen en el artefacto web.

## Configuración inicial

En el repositorio, abrir **Settings → Pages → Build and deployment → Source**
y seleccionar **GitHub Actions**. GitHub Pages es compatible con repositorios
públicos en GitHub Free; la disponibilidad para repositorios privados depende
del plan. El flujo necesita los permisos `contents: read`, `pages: write` e
`id-token: write` y usa el entorno `github-pages`.

Referencia oficial: [flujos personalizados con GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## Actualizar el artículo

```powershell
# Ejecutar el análisis completo o convertir un Word final ya generado.
py -3.12 ejecutar.py --actualizar-web

# Revisar los cambios antes de publicarlos.
git status --short
git diff
git add docs
git commit -m "Actualiza el artículo de combustibles"
git push origin main
```

El push a `main` inicia la publicación. Ver su estado en **Actions → Publicar
artículo**. El flujo también puede iniciarse desde **Run workflow**. La ejecución
local del análisis no dispara una publicación sin un push posterior.

`docs/index.html`, `docs/assets/grafico-*`, `docs/articulo.json` y `.nojekyll`
se regeneran desde el Word. `docs/estilos.css` define el diseño. El modo web
conserva todo el texto, la tabla y los enlaces del artículo; no modifica cifras.

## Vista previa local

```powershell
py -3.12 -m http.server 8000 --directory docs
```

Abrir <http://localhost:8000> y terminar el servidor con Ctrl+C. Revisar gráficos,
tabla, navegación por teclado y ancho móvil antes de publicar. El HTML también
puede abrirse directamente, ya que usa enlaces relativos y no tiene JavaScript.

Si la URL da 404, comprobar primero el estado del flujo, la fuente de Pages y
que `index.html` esté en la raíz del artefacto. El despliegue puede tardar después
del push. No publicar carpetas de datos para resolver errores de cobertura.
