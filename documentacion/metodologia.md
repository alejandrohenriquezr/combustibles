# Metodología e interpretación

## Hogares y dominios

Se identifican gasolina `07.2.2.02.01` y diésel `07.2.2.01.01` de transporte
personal en las bases Personas, Gastos y CCIF de la IX EPF 2021–2022. No se
incluyen pasajes ni combustibles domésticos. La EPF no identifica octanajes.
La cobertura corresponde a capitales regionales y conurbaciones urbanas.

La unidad es un hogar por folio, con persona de referencia `parentesco == 1`.
Los quintiles se construyen sobre todos los hogares antes del filtro de gasto,
por ingreso per cápita sin arriendo imputado, siguiendo las reglas del manual.
Se usan factores fraccionarios en los límites. La sustitución para ordenar
ingresos no positivos no sustituye el ingreso usado en los estimadores.

Dentro de cada dominio se calcula:

```text
indicador (%) = 100 × mediana_ponderada(gasto combustible)
                    / mediana_ponderada(ingreso disponible)
```

Ambas medianas corresponden a los mismos hogares con gasto positivo. Se
conservan los ingresos no positivos y se exige una mediana de ingreso positiva.
El indicador relaciona dos medianas; no representa el porcentaje de cada hogar
ni la mediana de porcentajes individuales.

## Curva con precios posteriores

Para cada hogar se revalora por separado su gasolina y su diésel utilizando
precios nacionales GPP en CLP/litro:

```text
gasto_h(t) = gasolina_h × Pgas_CLP(t) / Pgas_CLP(base)
           + diesel_h × Pdie_CLP(t) / Pdie_CLP(base)
curva(t) = [mediana_ponderada(gasto_h(t)) - mediana_ponderada(gasto_h(base))]
           / mediana_ponderada(ingreso_h)
```

Se conserva la mezcla e ingreso EPF. Es un escenario condicionado a los precios,
no una medición de gasto o ingresos actuales. El cero inicial es una identidad
de la base. Las referencias mensuales son cortes publicados; no promedios
mensuales. Si GPP solo publicó «hace un mes», se conserva la precisión mensual
y su fecha de publicación sin inventar el día del precio.

## Intervalos, calidad y contrastes

- 1.999 réplicas bootstrap conjuntas de pseudo-conglomerados dentro de estratos,
  semilla `20261119`, percentiles tipo 1.
- Medianas y relaciones se recalculan con los mismos ponderadores por réplica.
  Se conserva su dependencia; no se dividen extremos de IC independientes.
- Cortes y factores finales fijos, sin recalibración por réplica: aproximación
  con el diseño público. Las bandas de la curva son puntuales y no incorporan
  incertidumbre en los precios o en cambios de conducta e ingreso.
- `calidad::assess` aplica criterios n/gl/CV del esquema Chile a insumos
  bootstrap. Es una adaptación a medianas y razones, no un estimador nativo ni
  una validación oficial del indicador. `calidad::create_mean` se usa para el
  control de ingreso del manual.
- † en barras y ○ en la curva: diferencia frente al quintil anterior con
  `p` de Holm ≥ 0,05. Cuatro pares por indicador o por mes, respectivamente.
  Se usan covarianzas conjuntas. No significancia no demuestra igualdad.
- ‡ en barras y × en la curva: «No fiable» con los criterios adaptados.

Los controles incluyen veinte celdas oficiales por quintil de los cuadros 4A
y 7B, con tolerancia de $0,02, y el error estándar de ingreso del manual.

## Comparación entre países y PPA

Se utiliza un corte semanal común por mes para gasolina 95 y diésel en un
universo fijo de 17 países. Puesto 1 = menor precio; los empates comparten puesto.
Este universo no equivale a todos los países de Latinoamérica. Los precios y
rankings publicados no llevan IC EPF ni pruebas de significancia muestral.

El ajuste PPA aproxima `precio_USD × (PIB_PPA / PIB_USD)` con factores anuales del
FMI, edición identificada en configuración. No es una canasta específica de
hogares ni una PPA mensual observada. Se conserva una sensibilidad con factores
de 2025 fijos. No se interpreta la variación en USD como variación en CLP.

Las referencias precisas se conservan en el artículo, la configuración base y
los Excel generados. Véase [fuentes](fuentes.md).
