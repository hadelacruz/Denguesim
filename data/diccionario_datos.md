# Diccionario de datos — DengueSim GT (módulo de datos)

Generado automáticamente por `src/datos/diccionario.py` el 2026-10-20. Leer las tablas con `dtype={'cod_muni': str, 'cod_i': str, 'cod_j': str}` para conservar los ceros iniciales (o usar `leer_procesado()` de `src/datos/comun.py`).

La procedencia de cada archivo crudo (URL, tamaño, SHA-256, fecha) está en `data/raw/manifest.json`.

## `casos_semanales.csv`

ESTIMADO. Casos semanales por municipio = total anual SIGSA repartido con la curva semanal nacional del mismo año.

- **Filas:** 10,659 · **Módulos que la usan:** Dinámica de sistemas
- **Fuente:** SIGSA/MSPAS + OpenDengue/OPS + salas situacionales MSPAS
- **Fecha de descarga:** 2026-10-20

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `cod_muni` | Código INE del municipio (4 dígitos, depto 01 + municipio) | texto | 17 valores |
| `anio` | Año epidemiológico | año | 2014 – 2025 |
| `semana_epi` | Semana epidemiológica (domingo a sábado, calendario OPS/CDC) | 1-53 | 1 – 53 |
| `casos` | Casos de dengue registrados | casos | 0 – 277 |
| `tipo` | 'estimado' = desagregación, no observación directa | texto | 1 valores |
| `metodo` | Método con que se construyó la fila | texto | 1 valores |

## `casos_anuales_muni.csv`

OBSERVADO. Casos y casos graves por municipio y año.

- **Filas:** 238 · **Módulos que la usan:** Dinámica de sistemas, SIG y demo
- **Fuente:** SIGSA/MSPAS
- **Fecha de descarga:** 2026-10-20

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `cod_muni` | Código INE del municipio (4 dígitos, depto 01 + municipio) | texto | 17 valores |
| `anio` | Año epidemiológico | año | 2012 – 2025 |
| `casos` | Casos de dengue registrados | casos | 0 – 6,902 |
| `casos_graves` | Casos de dengue grave registrados | casos | 0 – 73 |

## `casos_anuales_edad_sexo.csv`

OBSERVADO. Casos por municipio, año, grupo de edad y sexo.

- **Filas:** 3,013 · **Módulos que la usan:** ABM, dinámica de sistemas
- **Fuente:** SIGSA/MSPAS
- **Fecha de descarga:** 2026-10-20

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `cod_muni` | Código INE del municipio (4 dígitos, depto 01 + municipio) | texto | 17 valores |
| `anio` | Año epidemiológico | año | 2012 – 2025 |
| `grupo_etario` | Grupo de edad según SIGSA | texto | 14 valores |
| `sexo` | Sexo | texto | 2 valores |
| `casos` | Casos de dengue registrados | casos | 1 – 1,049 |

## `casos_semanales_nacional.csv`

OBSERVADO. Casos semanales de todo el país (2014-2024 OpenDengue; 2025-2026 digitalizado de boletines MSPAS).

- **Filas:** 660 · **Módulos que la usan:** Dinámica de sistemas
- **Fuente:** OpenDengue V1.3 (OPS/PLISA); MSPAS
- **Fecha de descarga:** 2026-10-20

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `anio` | Año epidemiológico | año | 2014 – 2026 |
| `semana_epi` | Semana epidemiológica (domingo a sábado, calendario OPS/CDC) | 1-53 | 1 – 53 |
| `fecha_inicio` | Domingo con que inicia la semana epidemiológica | fecha | 660 valores |
| `casos` | Casos de dengue registrados | casos | 0 – 7,560 |
| `fuente` | Fuente de la fila | texto | 3 valores |
| `imputado` | La fuente marca el valor como imputado | booleano | 8% verdadero |

## `actividad_semanal_area_salud.csv`

OBSERVADO (categórico). Zona del corredor endémico por área de salud y semana, digitalizado de los boletines.

- **Filas:** 6,989 · **Módulos que la usan:** Dinámica de sistemas (orden de llegada)
- **Fuente:** MSPAS salas situacionales
- **Fecha de descarga:** 2026-10-20

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `anio` | Año epidemiológico | año | 2019 – 2026 |
| `semana_epi` | Semana epidemiológica (domingo a sábado, calendario OPS/CDC) | 1-53 | 1 – 52 |
| `area_salud` | Área de salud / DDRISS del MSPAS | texto | 29 valores |
| `zona` | Zona del corredor endémico del MSPAS: brote, alerta, seguridad, exito, sin_notificacion | texto | 5 valores |
| `nivel` | Zona codificada: 4 brote, 3 alerta, 2 seguridad, 1 éxito, 0 sin notificación | 0-4 | 0 – 4 |

## `poblacion.csv`

Población, área y densidad por municipio.

- **Filas:** 17 · **Módulos que la usan:** Todos los módulos
- **Fuente:** INE/SIGSA proyecciones; INE Censo 2018; geoBoundaries; WorldPop
- **Fecha de descarga:** 2026-10-20

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `cod_muni` | Código INE del municipio (4 dígitos, depto 01 + municipio) | texto | 17 valores |
| `nombre` | Nombre oficial INE | texto | 17 valores |
| `poblacion` | Población (proyección INE/SIGSA del año de referencia, salvo que se indique) | personas | 8,545 – 1.229e+06 |
| `area_km2` | Área del polígono municipal (UTM 15N) | km² | 23.8 – 280 |
| `densidad` | poblacion / area_km2 | hab/km² | 111.7 – 6,503 |
| `poblacion_censo2018` | Personas censadas en 2018 (sin ajuste de omisión) | personas | 7,229 – 9.234e+05 |
| `area_salud` | Área de salud / DDRISS del MSPAS | texto | 4 valores |
| `anio_poblacion` | Año de la proyección usada en 'poblacion' | año | 2024 – 2024 |

## `poblacion_anual.csv`

Proyección de población por municipio y año 2015-2026.

- **Filas:** 204 · **Módulos que la usan:** Dinámica de sistemas
- **Fuente:** INE/SIGSA
- **Fecha de descarga:** 2026-10-20

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `cod_muni` | Código INE del municipio (4 dígitos, depto 01 + municipio) | texto | 17 valores |
| `anio` | Año epidemiológico | año | 2015 – 2026 |
| `poblacion` | Población (proyección INE/SIGSA del año de referencia, salvo que se indique) | personas | 8,078 – 1.242e+06 |

## `poblacion_edad.csv`

Proyección por municipio, año, grupo de edad y sexo.

- **Filas:** 6,120 · **Módulos que la usan:** ABM
- **Fuente:** INE/SIGSA
- **Fecha de descarga:** 2026-10-20

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `cod_muni` | Código INE del municipio (4 dígitos, depto 01 + municipio) | texto | 17 valores |
| `anio` | Año epidemiológico | año | 2015 – 2026 |
| `grupo_edad` | Grupo de edad de la proyección | texto | 15 valores |
| `sexo` | Sexo | texto | 2 valores |
| `poblacion` | Población (proyección INE/SIGSA del año de referencia, salvo que se indique) | personas | 81 – 7.216e+04 |

## `clima_semanal.csv`

Lluvia y temperatura semanal en la cabecera de cada municipio.

- **Filas:** 8,670 · **Módulos que la usan:** Dinámica de sistemas, autómata celular
- **Fuente:** Open-Meteo (ERA5 / ERA5-Land) o NASA POWER (ver columna fuente)
- **Fecha de descarga:** 2026-10-20

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `cod_muni` | Código INE del municipio (4 dígitos, depto 01 + municipio) | texto | 17 valores |
| `anio` | Año epidemiológico | año | 2017 – 2026 |
| `semana_epi` | Semana epidemiológica (domingo a sábado, calendario OPS/CDC) | 1-53 | 1 – 53 |
| `lluvia_mm` | Lluvia acumulada en la semana en la cabecera municipal | mm/semana | 0 – 354.8 |
| `temp_c` | Temperatura media diaria a 2 m, promedio de la semana | °C | 10.81 – 28.09 |
| `temp_max_c` | Máxima de la temperatura máxima diaria en la semana | °C | 18.9 – 36.9 |
| `temp_min_c` | Mínima de la temperatura mínima diaria en la semana | °C | 2.9 – 20.8 |
| `fecha_inicio` | Domingo con que inicia la semana epidemiológica | fecha | 510 valores |
| `fuente` | Fuente de la fila | texto | 1 valores |
| `lluvia_rel` | — | — | 0 – 11.84 |

## `clima_semanal_power.csv`

Respaldo de clima desde 2012 con NASA POWER.

- **Filas:** 13,107 · **Módulos que la usan:** Dinámica de sistemas
- **Fuente:** NASA POWER
- **Fecha de descarga:** 2026-10-20

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `cod_muni` | Código INE del municipio (4 dígitos, depto 01 + municipio) | texto | 17 valores |
| `anio` | Año epidemiológico | año | 2012 – 2026 |
| `semana_epi` | Semana epidemiológica (domingo a sábado, calendario OPS/CDC) | 1-53 | 1 – 53 |
| `lluvia_mm` | Lluvia acumulada en la semana en la cabecera municipal | mm/semana | vacío |
| `temp_c` | Temperatura media diaria a 2 m, promedio de la semana | °C | 11.95 – 25.58 |
| `temp_max_c` | Máxima de la temperatura máxima diaria en la semana | °C | 20.32 – 35.74 |
| `temp_min_c` | Mínima de la temperatura mínima diaria en la semana | °C | 4.97 – 20.39 |
| `fecha_inicio` | Domingo con que inicia la semana epidemiológica | fecha | 771 valores |
| `fuente` | Fuente de la fila | texto | 1 valores |

## `atributos_hogar.csv`

Muestra aleatoria del 10 % de los hogares del departamento (Censo 2018) con atributos para el ABM.

- **Filas:** 75,285 · **Módulos que la usan:** ABM
- **Fuente:** INE Censo 2018
- **Fecha de descarga:** 2026-10-20

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `cod_muni` | Código INE del municipio (4 dígitos, depto 01 + municipio) | texto | 17 valores |
| `ingreso` | Índice de riqueza del hogar (PCA, estandarizado). Proxy de ingreso: el Censo no pregunta ingreso | desv. estándar | -3.894 – 1.517 |
| `agua_entubada` | 1 = agua por tubería de red dentro o fuera de la vivienda (PCH4 = 1, 2) | 0/1 | 0 – 1 |
| `almacena_agua` | 1 = tiene tanque/depósito (PCH9_F) o su fuente obliga a almacenar (chorro público, lluvia, camión) | 0/1 | 0 – 1 |
| `tiene_deposito` | 1 = declara tanque o depósito de agua (PCH9_F) | 0/1 | 0 – 1 |
| `personas` | Personas en el hogar / lugar poblado | personas | 1 – 29 |
| `lugar_poblado` | Código INE del lugar poblado | texto | 101001 – 117999 |
| `factor_expansion` | Hogares que representa cada fila de la muestra | hogares | 10 – 10 |

## `atributos_municipio.csv`

Atributos medios de los hogares por municipio.

- **Filas:** 17 · **Módulos que la usan:** ABM, SIG y demo
- **Fuente:** INE Censo 2018
- **Fecha de descarga:** 2026-10-20

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `cod_muni` | Código INE del municipio (4 dígitos, depto 01 + municipio) | texto | 17 valores |
| `hogares` | Número de hogares | hogares | 1,913 – 2.43e+05 |
| `prop_agua_entubada` | Proporción de hogares con agua entubada | 0-1 | 0.612 – 0.9611 |
| `prop_almacena_agua` | Proporción de hogares que almacenan agua | 0-1 | 0.2247 – 0.5471 |
| `indice_riqueza_medio` | Media del índice de riqueza | desv. estándar | -1.514 – 0.3136 |
| `personas` | Personas en el hogar / lugar poblado | personas | 7,229 – 9.108e+05 |
| `prop_tiene_deposito` | Proporción de hogares con tanque o depósito | 0-1 | 0.2108 – 0.5331 |
| `prop_urbana` | Proporción de hogares en área urbana | 0-1 | 0.3231 – 1 |

## `lugares_poblados.csv`

Lugares poblados del Censo con coordenadas y atributos medios de sus hogares.

- **Filas:** 2,057 · **Módulos que la usan:** ABM, SIG y demo
- **Fuente:** INE Censo 2018
- **Fecha de descarga:** 2026-10-20

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `lugar_poblado` | Código INE del lugar poblado | texto | 101001 – 117128 |
| `nombre` | Nombre oficial INE | texto | 1802 valores |
| `cod_muni` | Código INE del municipio (4 dígitos, depto 01 + municipio) | texto | 17 valores |
| `lat` | Latitud WGS84 | grados | 14.28 – 14.9 |
| `lon` | Longitud WGS84 | grados | -90.72 – -90.22 |
| `hogares` | Número de hogares | hogares | 2 – 5.036e+04 |
| `personas` | Personas en el hogar / lugar poblado | personas | 9 – 1.98e+05 |
| `prop_agua_entubada` | Proporción de hogares con agua entubada | 0-1 | 0 – 1 |
| `prop_almacena_agua` | Proporción de hogares que almacenan agua | 0-1 | 0 – 1 |
| `indice_riqueza_medio` | Media del índice de riqueza | desv. estándar | -3.305 – 1.351 |

## `hospitales.csv`

Hospitales y establecimientos de OSM en el departamento.

- **Filas:** 108 · **Módulos que la usan:** Sistema de salud, SIG y demo
- **Fuente:** OpenStreetMap
- **Fecha de descarga:** 2026-10-20

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `id_hosp` | Identificador del establecimiento | texto | 108 valores |
| `nombre` | Nombre oficial INE | texto | 98 valores |
| `cod_muni` | Código INE del municipio (4 dígitos, depto 01 + municipio) | texto | 10 valores |
| `lat` | Latitud WGS84 | grados | 14.46 – 14.72 |
| `lon` | Longitud WGS84 | grados | -90.65 – -90.41 |
| `camas` | Camas (solo si OSM trae la etiqueta 'beds'; vacío = no publicado) | camas | vacío |
| `osm_id` | Elemento de OpenStreetMap | texto | 108 valores |
| `camas_fuente` | Origen del dato de camas | texto | vacío |
| `sector` | MSPAS, IGSS, militar o privado_u_ong (inferido del nombre/operador) | texto | 3 valores |
| `es_hospital` | El nombre indica hospital o sanatorio (no centro de salud, clínica, laboratorio) | booleano | 59% verdadero |
| `atiende_dengue` | Hospital general (excluye salud mental, rehabilitación, oncología, etc.) | booleano | 52% verdadero |

## `distancias.csv`

Distancia y tiempo por carretera entre cabeceras municipales.

- **Filas:** 272 · **Módulos que la usan:** Redes
- **Fuente:** OpenStreetMap (Geofabrik) + OSMnx
- **Fecha de descarga:** 2026-10-20

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `cod_i` | Código INE del municipio de origen | texto | 17 valores |
| `cod_j` | Código INE del municipio de destino ('FUERA' = fuera del departamento) | texto | 17 valores |
| `dist_km` | Distancia por la red vial entre cabeceras (ruta más corta) | km | 3.215 – 57.92 |
| `tiempo_min` | Tiempo de viaje en flujo libre entre cabeceras (ruta más rápida) | min | 4.795 – 74.35 |

## `flujos_od.csv`

Flujos diarios entre municipios del modelo gravitacional calibrado con el Censo.

- **Filas:** 272 · **Módulos que la usan:** Redes, dinámica de sistemas
- **Fuente:** Modelo propio; Censo 2018
- **Fecha de descarga:** 2026-10-20

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `cod_i` | Código INE del municipio de origen | texto | 17 valores |
| `cod_j` | Código INE del municipio de destino ('FUERA' = fuera del departamento) | texto | 17 valores |
| `flujo_diario` | Personas que viajan de i a j en un día típico (modelo gravitacional calibrado) | personas/día | 0 – 8.337e+04 |

## `od_censo.csv`

OBSERVADO. Matriz origen-destino de trabajo y estudio del Censo 2018.

- **Filas:** 283 · **Módulos que la usan:** Redes, dinámica de sistemas
- **Fuente:** INE Censo 2018
- **Fecha de descarga:** 2026-10-20

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `cod_i` | Código INE del municipio de origen | texto | 17 valores |
| `cod_j` | Código INE del municipio de destino ('FUERA' = fuera del departamento) | texto | 18 valores |
| `trabajadores` | Ocupados que residen en i y trabajan en j (Censo 2018) | personas | 0 – 3.966e+05 |
| `estudiantes` | Personas que residen en i y estudian en j (Censo 2018) | personas | 0 – 2.732e+05 |
| `total` | trabajadores + estudiantes | personas | 1 – 6.698e+05 |

## `grilla_piloto.csv`

Grilla de la zona piloto del ABM con población y atributos de hogar por celda.

- **Filas:** 470 · **Módulos que la usan:** ABM
- **Fuente:** WorldPop 2020; INE Censo 2018
- **Fecha de descarga:** 2026-10-20

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `cod_celda` | Identificador de celda de la grilla piloto (fila_columna) | texto | 470 valores |
| `fila` | Fila de la grilla (0 = norte) | índice | 0 – 32 |
| `col` | Columna de la grilla (0 = oeste) | índice | 0 – 28 |
| `x_utm` | Centro de la celda, este UTM 15N | m | 7.508e+05 – 7.648e+05 |
| `y_utm` | Centro de la celda, norte UTM 15N | m | 1.591e+06 – 1.607e+06 |
| `lat` | Latitud WGS84 | grados | 14.38 – 14.53 |
| `lon` | Longitud WGS84 | grados | -90.67 – -90.54 |
| `poblacion` | Población (proyección INE/SIGSA del año de referencia, salvo que se indique) | personas | 0 – 1,787 |
| `fraccion_en_municipio` | Fracción del área de la celda dentro del municipio piloto | 0-1 | 0.002 – 1 |
| `cod_muni` | Código INE del municipio (4 dígitos, depto 01 + municipio) | texto | 1 valores |
| `prop_agua_entubada` | Proporción de hogares con agua entubada | 0-1 | 0.007 – 1 |
| `prop_almacena_agua` | Proporción de hogares que almacenan agua | 0-1 | 0 – 0.8333 |
| `indice_riqueza_medio` | Media del índice de riqueza | desv. estándar | -2.239 – 0.9736 |
| `lugar_poblado_ref` | Lugar poblado del Censo del que se tomaron los atributos de la celda | texto | 114001 – 114178 |

## `ca_mosquitos.csv`

Densidad semanal de mosquitos por celda del autómata celular.

- **Filas:** 234,600 · **Módulos que la usan:** Demo
- **Fuente:** Modelo propio con clima_semanal.csv
- **Fecha de descarga:** —

| Columna | Significado | Unidad | Rango observado |
|---|---|---|---|
| `cod_celda` | Identificador de celda de la grilla piloto (fila_columna) | texto | 460 valores |
| `anio` | Año epidemiológico | año | 2017 – 2026 |
| `semana_epi` | Semana epidemiológica (domingo a sábado, calendario OPS/CDC) | 1-53 | 1 – 53 |
| `densidad` | poblacion / area_km2 | hab/km² | 0 – 2,386 |
| `densidad_rel` | Densidad de mosquitos relativa a la capacidad de carga (D/K) | 0-1 | 0.0001 – 3.312 |

## Otros archivos

| Archivo | Contenido |
|---|---|
| `sigma_hogar.json` | Medias y covarianza observadas de (ingreso, agua_entubada, almacena_agua); correlación latente, umbrales y factor de Cholesky para generar agentes. Incluye un bloque por municipio. Lo usa el ABM. |
| `parametros_datos.json` | Parámetros estimados con los datos (fracción que viaja, exponentes gravitacionales calibrados, lluvia de referencia, etc.). Tienen prioridad sobre los de config/parametros.yaml. |
| `limites_municipios.geojson` | Polígonos de los 17 municipios con cod_muni (geoBoundaries). |
| `grilla_piloto.geojson` | Polígonos de las celdas de la grilla piloto (mismas columnas que grilla_piloto.csv). |
| `red_vial_nodos.csv.gz / red_vial_aristas.csv.gz` | Red vial para isocronas; cargar con `cargar_red()` de src/sig/red_vial.py. |
| `ca_mosquitos.npz / ca_mosquitos.gif` | Arreglos (semanas × filas × columnas) y animación del autómata celular. |
| `validacion/` | Tablas de control de calidad: comparaciones entre fuentes y calibraciones. |
