# DengueSim GT

Gemelo digital de la propagación del dengue y de la respuesta del sistema de
salud en el departamento de Guatemala (17 municipios). Modelo híbrido
SD + ABM + Redes + SIG con análisis de estabilidad y Monte Carlo.

Proyecto Final · Modelación y Simulación · UVG 2026
Equipo: Juan Diego (datos) · Daniel Juárez (redes + ABM) · Alex (dinámica de sistemas) ·
Ruiz (salud + verificación) · Gerardo (SIG aplicado, integración y demo)

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q -m "not lento"          # todas las pruebas rápidas (< 1 min)
```

## Cómo correrlo

```bash
python src/integracion/pipeline.py              # todo el modelo, de punta a punta
python src/integracion/pipeline.py --rapido     # prueba de humo (pocas corridas y muestras)
python src/integracion/pipeline.py --solo salud # una etapa (o --desde sd_escenarios)
streamlit run dashboard/app.py                  # demo
```

El pipeline corre las etapas en este orden y al final verifica el contrato de interfaces:

| # | Etapa | Comando | Produce |
|---|---|---|---|
| 1 | `redes_base` | `python src/redes/run_all.py --etapa base` | `centralidad.csv`, métricas, topologías, umbral |
| 2 | `sd_calibracion` | `python src/sd/run_all.py --etapa calibracion` | `sd/calibracion.json` (ρ, βs, I0), validación |
| 3 | `abm` | `python src/abm/run_all.py` | `beta_efectiva.json`, corridas con IC bootstrap |
| 4 | `redes_intervenciones` | `python src/redes/run_all.py --etapa intervenciones` | `redes/intervenciones.csv` |
| 5 | `sd_escenarios` | `python src/sd/run_all.py --etapa escenarios` | `casos_esperados.csv` |
| 6 | `salud` | `python src/salud/run_all.py` | `ocupacion_camas.csv`, `inventario.csv`, `robustez.csv` |
| 7 | `sig` | `python src/sig/aplicado_run_all.py` | isocronas, `unidades_mclp.csv`, `ranking_riesgo.csv` |
| 8 | `resumenes` | `python src/integracion/resumenes.py` | tablas livianas para el demo |

Con `--con-datos` el pipeline corre antes `src/datos/run_all.py` (unos 30 min y ~550 MB de descarga).

## Módulos

| Módulo | Carpeta | Qué hace |
|---|---|---|
| Datos | `src/datos/`, `src/sig/` (archivos de Juan Diego) | Descarga y limpia casos, censo, clima, red vial y hospitales; modelo gravitacional y autómata celular de mosquitos |
| Redes | `src/redes/` | Red O-D gravitacional y del censo, centralidades, umbral epidémico, comparación con ER/BA/WS, fumigación aleatoria contra dirigida |
| ABM | `src/abm/` | Agentes en Mesa 2.4.0 sobre la grilla de Amatitlán (Cholesky para los atributos, scheduler mixto, bootstrap con criterio de paro, β efectiva). Protocolo en `src/abm/ODD.md` |
| Dinámica de sistemas | `src/sd/` | SEIR–SEI de Ross–Macdonald con RK4 a mano, lluvia con retardo de tercer orden, loop B de fumigación, R₀, calibración, metapoblación y escenarios |
| Salud | `src/salud/` | Generadores (transformada inversa y aceptación–rechazo), DES de camas en SimPy, cadena de insumos, estabilidad (α·τ), robustez con Monte Carlo |
| SIG aplicado | `src/sig/isocronas.py`, `mclp.py`, `ranking_riesgo.py` | Isocronas a hospitales con congestión, MCLP con PuLP/CBC contra el voraz, ranking de riesgo |
| Integración y demo | `src/integracion/`, `dashboard/` | Pipeline, tablas livianas y demo en Streamlit |

## Estructura

```
data/raw/          datos originales (se bajan con src/datos/descargar.py)
data/processed/    tablas limpias = interfaces entre módulos (+ redes/ abm/ sd/ salud/ sig/)
config/            parametros.yaml (fuente única de parámetros), municipios.csv, semillas.yaml
figuras/           figuras de cada módulo (redes/ abm/ sd/ salud/ sig/)
src/datos/         descarga y limpieza de datos
src/sig/           límites, ráster, red vial, gravitacional, autómata (datos) + isocronas, MCLP, ranking
src/redes/         red de movilidad, métricas, topologías e intervenciones
src/abm/           modelo basado en agentes (zona piloto)
src/sd/            dinámica de sistemas (SEIR–SEI)
src/salud/         demanda hospitalaria, camas, insumos, estabilidad y robustez
src/integracion/   pipeline integrado y resúmenes para el demo
dashboard/         demo en Streamlit (app.py y sus requirements.txt)
tests/             pruebas (pytest); fixtures/ para datos de prueba
prompts/           historial de prompts de IA, uno por integrante
.github/workflows/ integración continua (pytest -m "not lento")
```

## Datos

```bash
python src/datos/descargar.py      # ~25 min la primera vez (~550 MB); solo biblioteca estándar
python src/datos/run_all.py        # regenera data/processed/ (~5 min; el Censo es lo más lento)
pytest -q tests/test_contrato_datos.py
```

Las tablas de `data/processed/` ya están en el repo: los demás módulos **no** necesitan
correr la descarga. Si `pyrosm` no instala en Windows, `run_all.py --sin-red` reutiliza
`distancias.csv` y la red ya guardada.

- Contrato de interfaces y tablas extra: [`data/README.md`](data/README.md)
- Diccionario de datos: [`data/diccionario_datos.md`](data/diccionario_datos.md)
- Parámetros con referencias: [`config/parametros.yaml`](config/parametros.yaml); los estimados con datos están en `data/processed/parametros_datos.json`

## Limitaciones de los datos

- **Casos semanales por municipio estimados:** no se publican. `casos_semanales.csv` reparte el total
  anual observado de cada municipio con la forma semanal nacional, así que todos los municipios tienen el
  mismo perfil semanal. Se valida contra datos observados: la forma nacional y los totales anuales.
- **Camas sin dato:** `hospitales.csv` no trae camas (no se publican en datos abiertos). La capacidad es un
  supuesto con rango (10–60 camas de dengue por hospital) y el resultado principal es la curva de
  saturación contra capacidad.
- **Clima por reanálisis (ERA5):** se usa la lluvia relativa (`lluvia_rel`) por el sesgo del reanálisis.
- **Orden de llegada:** solo se puede validar a nivel de las 4 áreas de salud.
- **Población en isocronas:** el ráster WorldPop no está en el repo; la población se reparte de forma
  uniforme dentro de cada municipio (aproximación).
- **Factor de reporte ρ:** no es identificable con la curva semanal; se fija en 0.2 (rango 0.05–0.5).


| Fuente | Qué aporta | Licencia / acceso |
|---|---|---|
| [SIGSA / MSPAS](https://sigsa.mspas.gob.gt/datos-de-salud/morbilidad/enfermedades-transmitidas-por-vectores) | Casos de dengue por municipio, año, edad y sexo; proyecciones de población | Datos públicos |
| [Salas situacionales de arbovirosis, MSPAS](https://epidemiologia.mspas.gob.gt/informacion/vigilancia-epidemiologica/salas-situacionales/5-arbovirosis) | Curva semanal nacional y actividad por área de salud (PDF digitalizado) | Datos públicos |
| [OpenDengue V1.3](https://opendengue.org/data.html) | Serie semanal nacional 2014–2024 (origen OPS/PLISA) | CC BY 4.0 |

