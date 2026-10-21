"""Catálogo de fuentes externas del módulo de datos.

Cada entrada describe un archivo crudo que se guarda en ``data/raw/``.
Este módulo solo usa la biblioteca estándar para que ``descargar.py``
funcione en cualquier computadora con Python 3.9+ sin instalar nada.

Campos de cada fuente:
    id       identificador corto (se usa con --solo)
    grupo    agrupación lógica (casos, censo, clima, ...)
    url      URL de descarga
    destino  ruta relativa dentro de data/raw/
    metodo   GET (por defecto) o POST
    nota     qué contiene y por qué se usa
    git      True si el archivo es pequeño y puede versionarse en GitHub
"""

from __future__ import annotations

import csv
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
RAW = RAIZ / "data" / "raw"
CONFIG = RAIZ / "config"

SIGSA = "https://sigsa.mspas.gob.gt/descargas/datos-salud"
MSPAS_ARBO = "https://epidemiologia.mspas.gob.gt/phocadownload/userupload/arbovirosis"
INSIVUMEH_EST = "https://insivumeh.gob.gt/img/Estaciones_Met/output_csv_page"

# Inicio de la serie climática diaria. ERA5-Land (Open-Meteo) cobra por días
# pedidos; desde 2017 son ~10 temporadas y caben en el límite gratuito por hora.
CLIMA_INICIO_OPENMETEO = "2017-01-01"
CLIMA_INICIO_POWER = "20120101"

FUENTES: list[dict] = [
    # ------------------------------------------------------------------ casos
    {
        "id": "sigsa_dengue_2012_2024",
        "grupo": "casos",
        "url": f"{SIGSA}/2024/enfermedades-transmitidas-por-vectores/enfermedades-transmitidas-por-vectores-2012-al-2024-dengue.csv",
        "destino": "casos/sigsa_dengue_2012_2024.csv",
        "nota": "SIGSA/MSPAS. Casos de dengue por año, departamento, municipio, grupo etario y sexo (2012-2024).",
        "git": True,
    },
    {
        "id": "sigsa_dengue_2025",
        "grupo": "casos",
        "url": f"{SIGSA}/2025/enfermedades-transmitidas-por-vectores/enfermedades-transmitidas-por-vectores-2025-dengue.csv",
        "destino": "casos/sigsa_dengue_2025.csv",
        "nota": "SIGSA/MSPAS. Casos de dengue 2025 por municipio, grupo etario y sexo.",
        "git": True,
    },
    {
        "id": "sigsa_dengue_grave_2012_2024",
        "grupo": "casos",
        "url": f"{SIGSA}/2024/enfermedades-transmitidas-por-vectores/enfermedades-transmitidas-por-vectores-2012-al-2024-dengue-grave.csv",
        "destino": "casos/sigsa_dengue_grave_2012_2024.csv",
        "nota": "SIGSA/MSPAS. Casos de dengue grave 2012-2024 por municipio.",
        "git": True,
    },
    {
        "id": "sigsa_dengue_grave_2025",
        "grupo": "casos",
        "url": f"{SIGSA}/2025/enfermedades-transmitidas-por-vectores/enfermedades-transmitidas-por-vectores-2025-dengue-grave.csv",
        "destino": "casos/sigsa_dengue_grave_2025.csv",
        "nota": "SIGSA/MSPAS. Casos de dengue grave 2025 por municipio.",
        "git": True,
    },
    {
        "id": "opendengue_temporal",
        "grupo": "casos",
        "url": "https://raw.githubusercontent.com/OpenDengue/master-repo/main/data/releases/V1.3/Temporal_extract_V1_3.zip",
        "destino": "casos/opendengue_temporal_V1_3.zip",
        "nota": "OpenDengue V1.3 (LSHTM, CC BY 4.0). Serie semanal nacional de Guatemala 2013-2024 (origen OPS/PLISA).",
        "git": False,
    },
    # Salas situacionales de arbovirosis (cierre de cada año). PDF.
    *[
        {
            "id": f"mspas_arbo_{etiqueta}",
            "grupo": "boletines",
            "url": f"{MSPAS_ARBO}/{ruta}",
            "destino": f"boletines/{etiqueta}.pdf",
            "nota": "MSPAS, Dirección de Epidemiología. Sala situacional de arbovirosis (PDF).",
            "git": True,
        }
        for etiqueta, ruta in [
            ("arbo_se35_2026", "2026/arbovirosis-semana-35-2026.pdf"),
            ("arbo_se53_2025", "2025/arbovirosis-semana-53-2025.pdf"),
            ("arbo_se52_2024", "arbovirosis-sem-52%202024.pdf"),
            ("arbo_se52_2023", "arbovirosis-sem-52-2023.pdf"),
            ("arbo_se52_2022", "arbo-sem-52-2022.pdf"),
            ("arbo_se52_2021", "ARBO-SEM-52-2021.pdf"),
            ("arbo_se53_2020", "ARB-SE-53-2020.pdf"),
            ("arbo_se51_2019", "ARBO-SE-51-2019.pdf"),
            ("arbo_se52_2018", "arbovirosis-Sem52-2018.pdf"),
        ]
    ],
    # --------------------------------------------------------------- población
    {
        "id": "ine_censo2018_csv",
        "grupo": "censo",
        "url": "https://censo2018.ine.gob.gt/archivos/bdd/db_csv_.zip",
        "metodo": "POST",
        "destino": "censo/censo2018_db_csv.zip",
        "nota": "INE, XII Censo de Población y VII de Vivienda 2018. Microdatos (personas, hogares, viviendas). ~323 MB.",
        "git": False,
    },
    {
        "id": "sigsa_proyecciones",
        "grupo": "censo",
        "url": f"{SIGSA}/2026/proyecciones-de-poblacion/reporte-proyeccion-poblacion-2015-2026.csv",
        "destino": "censo/sigsa_proyeccion_poblacion_2015_2026.csv",
        "nota": "SIGSA/MSPAS (con base en INE). Proyección de población por municipio 2015-2026.",
        "git": True,
    },
    {
        "id": "worldpop_2020",
        "grupo": "geo",
        "url": "https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/GTM/gtm_ppp_2020.tif",
        "destino": "geo/gtm_ppp_2020.tif",
        "nota": "WorldPop (CC BY 4.0). Personas por celda de ~100 m, 2020, no restringido.",
        "git": False,
    },
    # ----------------------------------------------------------------- geo
    {
        "id": "geoboundaries_adm2",
        "grupo": "geo",
        "url": "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/gbOpen/GTM/ADM2/geoBoundaries-GTM-ADM2.geojson",
        "destino": "geo/geoBoundaries-GTM-ADM2.geojson",
        "nota": "geoBoundaries gbOpen (CC BY 4.0). Límites municipales de Guatemala.",
        "git": True,
    },
    {
        "id": "geofabrik_osm",
        "grupo": "geo",
        "url": "https://download.geofabrik.de/central-america/guatemala-latest.osm.pbf",
        "destino": "geo/guatemala-latest.osm.pbf",
        "nota": "OpenStreetMap vía Geofabrik (ODbL). Red vial completa del país. ~130 MB.",
        "git": False,
    },
    # --------------------------------------------------------------- clima
    # INSIVUMEH publica solo los últimos ~30 días por estación; se guarda una
    # foto para validar el reanálisis.
    *[
        {
            "id": f"insivumeh_{cod}",
            "grupo": "clima",
            "url": f"{INSIVUMEH_EST}/{cod}.html",
            "destino": f"clima/insivumeh/{cod}.html",
            "nota": f"INSIVUMEH. Datos diarios recientes de la estación {nombre} (últimos ~30 días).",
            "git": True,
        }
        for cod, nombre in [
            ("INS010101CV", "INSIVUMEH"),
            ("INS010102CV", "La Aurora"),
            ("INS010301AT", "San José Pinula"),
            ("INS010302AT", "Las Nubes"),
            ("INS010701AT", "San Pedro Ayampuc"),
            ("INS010801AT", "Lo de Coy"),
            ("INS011402CV", "Amatitlán dos"),
        ]
    ],
]

# Consultas Overpass (OpenStreetMap) para hospitales y límites de respaldo.
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSM_REL_DEPARTAMENTO = 214704  # Departamento de Guatemala
OVERPASS_CONSULTAS = {
    "osm/hospitales.json": f"""[out:json][timeout:120];
area({3600000000 + OSM_REL_DEPARTAMENTO})->.d;
(nwr(area.d)["amenity"="hospital"]; nwr(area.d)["healthcare"="hospital"];);
out tags center;""",
    "osm/municipios.json": f"""[out:json][timeout:180];
area({3600000000 + OSM_REL_DEPARTAMENTO})->.d;
rel(area.d)["boundary"="administrative"]["admin_level"="6"];
out geom;""",
}


def municipios() -> list[dict]:
    """Lee config/municipios.csv (17 municipios con cabecera)."""
    with open(CONFIG / "municipios.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fuentes_clima() -> list[dict]:
    """Una consulta Open-Meteo (ERA5-Land) y una NASA POWER por cabecera."""
    from datetime import date, timedelta

    ayer = date.today() - timedelta(days=6)  # ERA5 tiene ~5 días de rezago
    salida = []
    for m in municipios():
        lat, lon = m["lat_cabecera"], m["lon_cabecera"]
        salida.append({
            "id": f"openmeteo_{m['cod_muni']}",
            "grupo": "clima",
            "url": (
                "https://archive-api.open-meteo.com/v1/archive"
                f"?latitude={lat}&longitude={lon}"
                f"&start_date={CLIMA_INICIO_OPENMETEO}&end_date={ayer.isoformat()}"
                "&daily=precipitation_sum,temperature_2m_mean,temperature_2m_max,temperature_2m_min"
                "&models=era5_land&timezone=America%2FGuatemala"
            ),
            "destino": f"clima/openmeteo/{m['cod_muni']}.json",
            "nota": "Open-Meteo, reanálisis ERA5-Land (~9 km). Temperatura diaria en la cabecera (la lluvia viene vacía en este modelo).",
            "git": True,
            "pausa": 35,  # respeta el límite gratuito (600 llamadas/min, 5000/h)
        })
        # ERA5-Land no trae precipitación en Open-Meteo: la lluvia se pide a ERA5 (0.25°).
        salida.append({
            "id": f"openmeteo_lluvia_{m['cod_muni']}",
            "grupo": "clima",
            "url": (
                "https://archive-api.open-meteo.com/v1/archive"
                f"?latitude={lat}&longitude={lon}"
                f"&start_date={CLIMA_INICIO_OPENMETEO}&end_date={ayer.isoformat()}"
                "&daily=precipitation_sum&models=era5&timezone=America%2FGuatemala"
            ),
            "destino": f"clima/openmeteo_lluvia/{m['cod_muni']}.json",
            "nota": "Open-Meteo, reanálisis ERA5 (~25 km). Lluvia diaria en la cabecera.",
            "git": True,
            "pausa": 30,
        })
        salida.append({
            "id": f"power_{m['cod_muni']}",
            "grupo": "clima",
            "url": (
                "https://power.larc.nasa.gov/api/temporal/daily/point"
                "?parameters=PRECTOTCORR,T2M,T2M_MAX,T2M_MIN&community=AG"
                f"&longitude={lon}&latitude={lat}"
                f"&start={CLIMA_INICIO_POWER}&end={ayer.strftime('%Y%m%d')}&format=JSON"
            ),
            "destino": f"clima/power/{m['cod_muni']}.json",
            "nota": "NASA POWER (MERRA-2, ~50 km). Respaldo y serie desde 2012.",
            "git": True,
        })
    return salida


def todas() -> list[dict]:
    return FUENTES + fuentes_clima()
