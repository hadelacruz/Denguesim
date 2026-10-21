# DengueSim GT

Gemelo digital de la propagación del dengue y de la respuesta del sistema de
salud en el departamento de Guatemala (17 municipios). Modelo híbrido
SD + ABM + Redes + SIG con análisis de estabilidad y Monte Carlo.

Proyecto Final · Modelación y Simulación · UVG 2026
Equipo: Juan Diego · Daniel Juárez · Alex · Ruiz · Gerardo

> Demo: *(link de Streamlit Community Cloud — pendiente)*

## Estructura

```
data/raw/          datos originales (se bajan con src/datos/descargar.py)
data/processed/    tablas limpias = interfaces entre módulos
config/            parametros.yaml (fuente única de parámetros), municipios.csv, semillas.yaml
src/datos/         descarga y limpieza de datos
src/sig/           límites, ráster, red vial, modelo gravitacional, autómata celular y análisis SIG
src/redes/         red de movilidad, métricas y topologías
src/abm/           modelo basado en agentes (zona piloto)
src/sd/            dinámica de sistemas (SEIR–SEI)
src/salud/         demanda hospitalaria, camas e insumos
src/integracion/   pipeline integrado
dashboard/         demo en Streamlit
tests/             pruebas (pytest)
prompts/           historial de prompts de IA
```

## Datos

```bash
pip install -r requirements.txt
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

## Fuentes de datos

| Fuente | Qué aporta | Licencia / acceso |
|---|---|---|
| [SIGSA / MSPAS](https://sigsa.mspas.gob.gt/datos-de-salud/morbilidad/enfermedades-transmitidas-por-vectores) | Casos de dengue por municipio, año, edad y sexo; proyecciones de población | Datos públicos |
| [Salas situacionales de arbovirosis, MSPAS](https://epidemiologia.mspas.gob.gt/informacion/vigilancia-epidemiologica/salas-situacionales/5-arbovirosis) | Curva semanal nacional y actividad por área de salud (PDF digitalizado) | Datos públicos |
| [OpenDengue V1.3](https://opendengue.org/data.html) | Serie semanal nacional 2014–2024 (origen OPS/PLISA) | CC BY 4.0 |
| [INE, Censo 2018](https://censo2018.ine.gob.gt/descarga) | Población, hogares, viviendas y matriz origen-destino de trabajo/estudio | Datos públicos |
| [WorldPop](https://hub.worldpop.org/) | Población en ráster de ~100 m (2020) | CC BY 4.0 |
| [geoBoundaries](https://www.geoboundaries.org/) | Límites municipales | CC BY 4.0 |
| [OpenStreetMap / Geofabrik](https://download.geofabrik.de/central-america/guatemala.html) | Red vial y hospitales | ODbL |
| [Open-Meteo (ERA5, ERA5-Land)](https://open-meteo.com/) · [NASA POWER](https://power.larc.nasa.gov/) | Lluvia y temperatura diaria por cabecera | CC BY 4.0 / público |
| [INSIVUMEH](https://insivumeh.gob.gt/datos-mensuales-usuario-final/) | Datos diarios recientes de estaciones (validación del reanálisis) | Datos públicos |
