# Datos de DengueSim GT

```
data/
├── raw/          datos originales tal como se descargaron (python src/datos/descargar.py)
│   └── manifest.json   URL, tamaño, SHA-256 y fecha de cada archivo crudo
├── processed/    tablas limpias = interfaces entre módulos (python src/datos/run_all.py)
│   └── validacion/     controles de calidad y comparaciones entre fuentes
├── diccionario_datos.md   columnas, unidades, fuentes y rangos (se genera solo)
```

Los archivos crudos pesados (Censo, ráster WorldPop, extracto OSM, OpenDengue)
no se suben a GitHub (ver `.gitignore`); se regeneran con el script de descarga.

## Cómo leer las tablas

Todo municipio se identifica con su **código INE de 4 dígitos** (`0101` … `0117`).
Para no perder el cero inicial:

```python
import pandas as pd
df = pd.read_csv("data/processed/poblacion.csv", dtype={"cod_muni": str})
# o bien
from src.datos.comun import leer_procesado
df = leer_procesado("flujos_od.csv")          # conserva cod_i / cod_j como texto
```

Tiempo: `anio` + `semana_epi` (semana epidemiológica domingo–sábado, calendario
OPS/CDC) en datos observados; `dia` en simulaciones.

## Contrato de interfaces

Las columnas del contrato van **primero y en este orden**; algunas tablas traen
columnas extra a la derecha (documentadas en el diccionario). `src/datos/contrato.py`
lo verifica automáticamente al final de `run_all.py`.

| Archivo | Columnas | Produce (módulo) | Usa (módulo) | Estado |
|---|---|---|---|---|
| `casos_semanales.csv` | cod_muni, anio, semana_epi, casos | Datos | Dinámica de sistemas | **Estimado** |
| `poblacion.csv` | cod_muni, nombre, poblacion, area_km2, densidad | Datos | Todos los módulos | Disponible |
| `clima_semanal.csv` | cod_muni, anio, semana_epi, lluvia_mm, temp_c | Datos | Dinámica de sistemas, autómata celular | Disponible (reanálisis) |
| `atributos_hogar.csv` | cod_muni, ingreso, agua_entubada, almacena_agua | Datos | ABM | Disponible (ingreso = índice proxy) |
| `sigma_hogar.json` | medias, matriz de covarianza | Datos | ABM | Disponible (+ correlación latente) |
| `hospitales.csv` | id_hosp, nombre, cod_muni, lat, lon, camas | Datos | Sistema de salud, SIG y demo | Parcial (`camas` vacío) |
| `distancias.csv` | cod_i, cod_j, dist_km, tiempo_min | Datos | Redes | Disponible |
| `flujos_od.csv` | cod_i, cod_j, flujo_diario | Datos | Redes, dinámica de sistemas | Disponible (calibrado con el Censo) |
| `centralidad.csv` | cod_muni, grado, intermediacion, eigenvector | Redes | Dinámica de sistemas, SIG y demo | — |
| `beta_efectiva.json` | beta, ic_inf, ic_sup | ABM | Dinámica de sistemas | — |
| `casos_esperados.csv` | escenario, corrida, cod_muni, dia, S, E, I, R, nuevos | Dinámica de sistemas | Sistema de salud, SIG y demo | — |
| `ocupacion_camas.csv` | escenario, id_hosp, dia, ocupadas, en_cola | Sistema de salud | SIG y demo | — |
| `inventario.csv` | escenario, id_hosp, dia, I, P | Sistema de salud | SIG y demo | — |
| `robustez.csv` | escenario, metrica, media, ic_inf, ic_sup, prob_mejor | Sistema de salud | SIG y demo | — |
| `unidades_mclp.csv` | p, cod_celda, lat, lon, poblacion_cubierta | SIG y demo | Demo | — |
| `ranking_riesgo.csv` | cod_muni, riesgo_casos, centralidad, puntaje, posicion | SIG y demo | Demo | — |

### Tablas adicionales del módulo de datos

| Archivo | Para qué sirve | Lo puede usar |
|---|---|---|
| `casos_anuales_muni.csv` | Casos **observados** por municipio y año (2012–2025), con dengue grave | Dinámica de sistemas (magnitudes), SIG y demo (ranking) |
| `casos_anuales_edad_sexo.csv` | Casos por grupo de edad y sexo | ABM (validar quién se enferma) |
| `casos_semanales_nacional.csv` | Curva semanal **observada** del país 2014–2026 | Dinámica de sistemas (forma de la temporada, calibración) |
| `actividad_semanal_area_salud.csv` | Zona del corredor endémico por área de salud y semana | Dinámica de sistemas (orden de llegada por área de salud) |
| `od_censo.csv` | Matriz origen-destino **observada** (trabajo + estudio, Censo 2018) | Redes (red real), dinámica de sistemas (metapoblación) |
| `poblacion_anual.csv`, `poblacion_edad.csv` | N por año y estructura por edad | Dinámica de sistemas, ABM |
| `atributos_municipio.csv`, `lugares_poblados.csv` | Atributos de hogar agregados y georreferenciados | ABM, SIG y demo |
| `grilla_piloto.csv` / `.geojson` | Grilla de 500 m de la zona piloto con población y atributos | ABM |
| `red_vial_nodos.csv.gz`, `red_vial_aristas.csv.gz` | Red vial para isocronas (`cargar_red()`) | SIG y demo |
| `limites_municipios.geojson` | Polígonos municipales con `cod_muni` | Todos (mapas) |
| `ca_mosquitos.csv` / `.npz` / `.gif` | Salida del autómata celular de mosquitos | Demo |
| `parametros_datos.json` | Parámetros estimados con datos (prioridad sobre el YAML) | Todos los módulos |
