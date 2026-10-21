# Historial de prompts — Juan Diego (módulo de datos)

Herramienta: Claude.
Formato por entrada: prompt reformulado · qué se esperaba · resultado · por qué creemos que pasó y qué se corrigió.

---

## 1. Revisar el acceso programático a las fuentes investigadas

**Prompt**
> Para nuestro proyecto DengueSim GT ya investigué varias fuentes que podrían servirnos: SIGSA, salas situacionales del MSPAS, OpenDengue, Censo 2018, WorldPop, Geofabrik/OSM, GADM, NASA POWER e INSIVUMEH. Te adjunto la propuesta para que tengas contexto sobre los datos que necesitamos.
>
> Quiero que revises cuáles de estas fuentes permiten obtener los datos mediante una API, enlaces de descarga directa o código. Verifica los enlaces y, cuando sea posible, prueba una consulta o descarga para confirmar que funcionan y que contienen las variables y la cobertura que necesitamos.
>
> Si alguna fuente no permite el acceso programático, tiene restricciones o no ofrece suficiente detalle temporal o geográfico, explícame la limitación y busca alternativas. Distingue entre poder consultar una página y poder descargar sus datos de manera reproducible. Incluye las URLs verificadas, el método de acceso y las limitaciones de cada fuente. *(adjunto: Propuesta_Proyecto_DengueSim_GT.pdf)*

**Qué se esperaba:** evaluación técnica de las fuentes previamente investigadas, con URLs verificadas, métodos de acceso mediante código y alternativas para los datos que no pudieran obtenerse.

**Resultado: satisfactorio, con dos hallazgos importantes.**
- Se revisaron las fuentes propuestas y sus posibilidades de acceso mediante API, descarga directa o extracción.
- Se detectó que `censopoblacion.gt`, citado en muchas referencias, era un dominio en venta; los microdatos estaban disponibles en `censo2018.ine.gob.gt/descarga`.
- No se encontraron casos semanales por municipio publicados en las fuentes revisadas, y las páginas consultadas de INSIVUMEH solo mostraban aproximadamente 30 días por estación.

**Por qué pasó / qué se corrigió:** algunas páginas gubernamentales restringen las consultas automatizadas y requieren inspección desde un navegador para identificar cómo obtener los archivos. Además, una URL citada en publicaciones puede dejar de funcionar. Se corrigieron los enlaces y se distinguió entre acceso a la página, descarga del archivo y disponibilidad del nivel de detalle requerido.

---

## 2. Revisar y corregir el módulo de datos desarrollado

**Prompt**
> Estoy trabajando en el módulo de datos de nuestro proyecto de modelado y simulación, DengueSim GT. Soy el encargado de recopilar, limpiar y preparar los datos para el resto del equipo. Ya desarrollé una primera versión de los scripts de descarga y procesamiento, y he obtenido parte de los archivos, pero algunas descargas, variables y transformaciones no me están dando resultados correctos.
>
> Revisa el código y los datos que ya tengo en la carpeta del repositorio. Usa como guía las instrucciones del proyecto y la “Guía de validación y entrega de datos”, donde se especifican las tablas esperadas, sus columnas, la cobertura temporal y geográfica y los controles de calidad.
>
> Identifica los problemas, explica sus causas y realiza los ajustes necesarios sobre mi implementación para obtener y procesar correctamente los datos. Ejecuta los scripts cuando el entorno lo permita y comprueba los resultados: formatos, unidades, valores faltantes, duplicados, cobertura y coherencia entre fuentes. Si alguna descarga no puede ejecutarse desde tu entorno, deja el procedimiento preparado para que pueda correrlo en mi computadora.
>
> También ayúdame a completar y corregir `estado_de_datos.md` y `diccionario_datos.md`. En el primero, documenta qué logré recolectar, qué está validado, qué sigue pendiente y qué limitaciones o aproximaciones debe considerar el equipo. En el segundo, describe las tablas y sus variables, incluyendo significado, tipo, unidad, fuente, transformaciones y tratamiento de valores faltantes.
>
> El objetivo es que los siguientes integrantes puedan identificar con claridad qué datos están disponibles y con cuáles pueden trabajar. Si un dato no se consigue o se sustituye por un proxy, déjalo explícitamente documentado. *(adjuntos: Proyecto_Final.pdf, guía de validación y archivos del repositorio)*

**Qué se esperaba:** revisión de la implementación existente, corrección de los problemas de descarga y procesamiento, validación de las tablas obtenidas y documentación clara para entregar los datos al resto del equipo.

**Resultado: satisfactorio en general, con errores que se detectaron y corrigieron durante la revisión.**

| Paso | Resultado | Qué pasó y cómo se corrigió |
|---|---|---|
| Descargar datos desde el entorno de la IA | No respondió a lo pedido | El entorno de la IA solo tiene red hacia GitHub y gestores de paquetes. Se cambió la estrategia: la IA escribió `descargar.py` (solo biblioteca estándar) y Juan Diego lo corrió en su computadora; luego la IA procesó los archivos. Ventaja: quedó probado que la descarga es reproducible en otra máquina. |
| Lectura de los CSV del SIGSA | Con errores | El primer intento falló porque el CSV de dengue grave trae una fila vacía al final (`;;;;;`). Se agregó limpieza de filas vacías y normalización de espacios en los grupos de edad. |
| Clima con ERA5-Land (Open-Meteo) | Con errores | La IA supuso que ERA5-Land traía lluvia; la respuesta llegó con la precipitación vacía (solo temperatura). Se agregó una segunda consulta a ERA5 para la lluvia y hubo que volver a descargar el clima. |
| Clima con NASA POWER (respaldo) | Lluvia inutilizable | La lluvia llegó con valores imposibles (20 000–50 000 mm/año, idénticos en los 17 puntos) aunque la API dice "mm/day". La IA primero supuso un factor de conversión; al comparar año por año con ERA5 se vio que no había un factor constante, así que se descartó la lluvia de POWER y se dejó solo su temperatura. |
| Sesgo de ERA5 | Detectado en la validación | Comparando con 25 días de las estaciones de INSIVUMEH, ERA5 da ~55 % de la lluvia en la celda de la capital y ~97 % en otra. Se agregó `lluvia_rel` (lluvia relativa a la temporada de cada municipio) para que el modelo use la estacionalidad y no el nivel. |
| INSIVUMEH | Con errores | Se descargó el HTML de cada estación, pero la tabla se arma con JavaScript. Revisando el código de la página se encontró el CSV directo que usa y se agregó al script. |
| Archivo `La_Aurora.csv` suelto | Efecto no previsto | Al inspeccionar el CSV de una estación de INSIVUMEH en el navegador integrado de la app, el navegador lo descargó en vez de mostrarlo. No lo usa el pipeline (el script baja el mismo dato como `INS010102CV.csv`). |
| Boletines del MSPAS (PDF) | Satisfactorio tras iterar | Las tablas semanales no existen como texto: son gráficos vectoriales. Se "digitalizaron" leyendo la geometría del PDF (posición de cada punto de la curva y de cada celda del mapa de calor). Primer intento: algunas etiquetas de área de salud salían mezcladas con notas al margen; se corrigió con búsqueda por contenido. Validación: la curva 2024 digitalizada correlaciona 0.99 con OpenDengue y los totales coinciden con los que el boletín reporta en texto. |
| Censo 2018 | Satisfactorio | El archivo de personas pesa 3.5 GB; se leyó por bloques filtrando el departamento. Hallazgo útil: el Censo trae municipio de trabajo y de estudio, lo que permitió construir una matriz origen-destino **observada** y calibrar el modelo gravitacional. |
| Ingreso del hogar | No existe en la fuente | El Censo no pregunta ingreso. Se construyó un índice de riqueza (PCA de bienes y vivienda, Filmer & Pritchett 2001) y se documentó como proxy. |
| Matriz Σ | Satisfactorio | Además de la covarianza observada (lo pedido), se calcularon la correlación latente (poliserial/tetracórica) y los umbrales, porque con variables binarias la Cholesky directa sobre la covarianza observada no reproduce las proporciones. |
| Camas por hospital | No disponible | No hay datos abiertos de camas (ni MSPAS, IGSS, ni OSM). Se dejó la columna vacía y se documentó la recomendación. |

**Cómo contribuyó la IA:** apoyó la revisión del código y de los datos que ya había preparado, ayudó a identificar problemas de acceso, lectura, unidades y transformaciones, y propuso y ejecutó correcciones cuando el entorno lo permitió. También ayudó a organizar `estado_de_datos.md` y `diccionario_datos.md` para distinguir los datos disponibles, las aproximaciones utilizadas y los faltantes. Las tablas de control en `data/processed/validacion/` permiten revisar la evidencia de las comprobaciones realizadas.