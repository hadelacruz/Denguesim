"""Genera data/diccionario_datos.md a partir de las tablas de data/processed/.

Para cada tabla: qué contiene, quién la usa, fuente, fecha de descarga (del
manifiesto de data/raw/) y, por columna, significado, unidad y rango observado.
Se regenera en cada corrida para que nunca quede desactualizado.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import PROCESSED, RAIZ, RAW, leer_procesado  # noqa: E402

# columna -> (significado, unidad)
COL = {
    "cod_muni": ("Código INE del municipio (4 dígitos, depto 01 + municipio)", "texto"),
    "cod_i": ("Código INE del municipio de origen", "texto"),
    "cod_j": ("Código INE del municipio de destino ('FUERA' = fuera del departamento)", "texto"),
    "nombre": ("Nombre oficial INE", "texto"),
    "anio": ("Año epidemiológico", "año"),
    "semana_epi": ("Semana epidemiológica (domingo a sábado, calendario OPS/CDC)", "1-53"),
    "fecha_inicio": ("Domingo con que inicia la semana epidemiológica", "fecha"),
    "casos": ("Casos de dengue registrados", "casos"),
    "casos_graves": ("Casos de dengue grave registrados", "casos"),
    "tipo": ("'estimado' = desagregación, no observación directa", "texto"),
    "metodo": ("Método con que se construyó la fila", "texto"),
    "fuente": ("Fuente de la fila", "texto"),
    "imputado": ("La fuente marca el valor como imputado", "booleano"),
    "grupo_etario": ("Grupo de edad según SIGSA", "texto"),
    "sexo": ("Sexo", "texto"),
    "poblacion": ("Población (proyección INE/SIGSA del año de referencia, salvo que se indique)", "personas"),
    "poblacion_censo2018": ("Personas censadas en 2018 (sin ajuste de omisión)", "personas"),
    "poblacion_worldpop": ("Suma del ráster WorldPop 2020 dentro del municipio", "personas"),
    "anio_poblacion": ("Año de la proyección usada en 'poblacion'", "año"),
    "area_salud": ("Área de salud / DDRISS del MSPAS", "texto"),
    "area_km2": ("Área del polígono municipal (UTM 15N)", "km²"),
    "densidad": ("poblacion / area_km2", "hab/km²"),
    "grupo_edad": ("Grupo de edad de la proyección", "texto"),
    "lluvia_mm": ("Lluvia acumulada en la semana en la cabecera municipal", "mm/semana"),
    "temp_c": ("Temperatura media diaria a 2 m, promedio de la semana", "°C"),
    "temp_max_c": ("Máxima de la temperatura máxima diaria en la semana", "°C"),
    "temp_min_c": ("Mínima de la temperatura mínima diaria en la semana", "°C"),
    "ingreso": ("Índice de riqueza del hogar (PCA, estandarizado). Proxy de ingreso: el Censo no pregunta ingreso", "desv. estándar"),
    "agua_entubada": ("1 = agua por tubería de red dentro o fuera de la vivienda (PCH4 = 1, 2)", "0/1"),
    "almacena_agua": ("1 = tiene tanque/depósito (PCH9_F) o su fuente obliga a almacenar (chorro público, lluvia, camión)", "0/1"),
    "tiene_deposito": ("1 = declara tanque o depósito de agua (PCH9_F)", "0/1"),
    "personas": ("Personas en el hogar / lugar poblado", "personas"),
    "lugar_poblado": ("Código INE del lugar poblado", "texto"),
    "factor_expansion": ("Hogares que representa cada fila de la muestra", "hogares"),
    "hogares": ("Número de hogares", "hogares"),
    "prop_agua_entubada": ("Proporción de hogares con agua entubada", "0-1"),
    "prop_almacena_agua": ("Proporción de hogares que almacenan agua", "0-1"),
    "prop_tiene_deposito": ("Proporción de hogares con tanque o depósito", "0-1"),
    "indice_riqueza_medio": ("Media del índice de riqueza", "desv. estándar"),
    "prop_urbana": ("Proporción de hogares en área urbana", "0-1"),
    "lat": ("Latitud WGS84", "grados"),
    "lon": ("Longitud WGS84", "grados"),
    "id_hosp": ("Identificador del establecimiento", "texto"),
    "camas": ("Camas (solo si OSM trae la etiqueta 'beds'; vacío = no publicado)", "camas"),
    "camas_fuente": ("Origen del dato de camas", "texto"),
    "sector": ("MSPAS, IGSS, militar o privado_u_ong (inferido del nombre/operador)", "texto"),
    "es_hospital": ("El nombre indica hospital o sanatorio (no centro de salud, clínica, laboratorio)", "booleano"),
    "atiende_dengue": ("Hospital general (excluye salud mental, rehabilitación, oncología, etc.)", "booleano"),
    "osm_id": ("Elemento de OpenStreetMap", "texto"),
    "dist_km": ("Distancia por la red vial entre cabeceras (ruta más corta)", "km"),
    "tiempo_min": ("Tiempo de viaje en flujo libre entre cabeceras (ruta más rápida)", "min"),
    "flujo_diario": ("Personas que viajan de i a j en un día típico (modelo gravitacional calibrado)", "personas/día"),
    "trabajadores": ("Ocupados que residen en i y trabajan en j (Censo 2018)", "personas"),
    "estudiantes": ("Personas que residen en i y estudian en j (Censo 2018)", "personas"),
    "total": ("trabajadores + estudiantes", "personas"),
    "cod_celda": ("Identificador de celda de la grilla piloto (fila_columna)", "texto"),
    "fila": ("Fila de la grilla (0 = norte)", "índice"),
    "col": ("Columna de la grilla (0 = oeste)", "índice"),
    "x_utm": ("Centro de la celda, este UTM 15N", "m"),
    "y_utm": ("Centro de la celda, norte UTM 15N", "m"),
    "fraccion_en_municipio": ("Fracción del área de la celda dentro del municipio piloto", "0-1"),
    "lugar_poblado_ref": ("Lugar poblado del Censo del que se tomaron los atributos de la celda", "texto"),
    "densidad_rel": ("Densidad de mosquitos relativa a la capacidad de carga (D/K)", "0-1"),
    "zona": ("Zona del corredor endémico del MSPAS: brote, alerta, seguridad, exito, sin_notificacion", "texto"),
    "nivel": ("Zona codificada: 4 brote, 3 alerta, 2 seguridad, 1 éxito, 0 sin notificación", "0-4"),
}

TABLAS = {
    "casos_semanales.csv": ("ESTIMADO. Casos semanales por municipio = total anual SIGSA repartido con la curva semanal nacional del mismo año.", "Dinámica de sistemas", "SIGSA/MSPAS + OpenDengue/OPS + salas situacionales MSPAS", ["sigsa_dengue_2012_2024", "opendengue_temporal"]),
    "casos_anuales_muni.csv": ("OBSERVADO. Casos y casos graves por municipio y año.", "Dinámica de sistemas, SIG y demo", "SIGSA/MSPAS", ["sigsa_dengue_2012_2024", "sigsa_dengue_grave_2012_2024"]),
    "casos_anuales_edad_sexo.csv": ("OBSERVADO. Casos por municipio, año, grupo de edad y sexo.", "ABM, dinámica de sistemas", "SIGSA/MSPAS", ["sigsa_dengue_2012_2024"]),
    "casos_semanales_nacional.csv": ("OBSERVADO. Casos semanales de todo el país (2014-2024 OpenDengue; 2025-2026 digitalizado de boletines MSPAS).", "Dinámica de sistemas", "OpenDengue V1.3 (OPS/PLISA); MSPAS", ["opendengue_temporal", "mspas_arbo_arbo_se53_2025"]),
    "actividad_semanal_area_salud.csv": ("OBSERVADO (categórico). Zona del corredor endémico por área de salud y semana, digitalizado de los boletines.", "Dinámica de sistemas (orden de llegada)", "MSPAS salas situacionales", ["mspas_arbo_arbo_se53_2025"]),
    "poblacion.csv": ("Población, área y densidad por municipio.", "Todos los módulos", "INE/SIGSA proyecciones; INE Censo 2018; geoBoundaries; WorldPop", ["sigsa_proyecciones", "ine_censo2018_csv"]),
    "poblacion_anual.csv": ("Proyección de población por municipio y año 2015-2026.", "Dinámica de sistemas", "INE/SIGSA", ["sigsa_proyecciones"]),
    "poblacion_edad.csv": ("Proyección por municipio, año, grupo de edad y sexo.", "ABM", "INE/SIGSA", ["sigsa_proyecciones"]),
    "clima_semanal.csv": ("Lluvia y temperatura semanal en la cabecera de cada municipio.", "Dinámica de sistemas, autómata celular", "Open-Meteo (ERA5 / ERA5-Land) o NASA POWER (ver columna fuente)", ["openmeteo_0101", "power_0101"]),
    "clima_semanal_power.csv": ("Respaldo de clima desde 2012 con NASA POWER.", "Dinámica de sistemas", "NASA POWER", ["power_0101"]),
    "atributos_hogar.csv": ("Muestra aleatoria del 10 % de los hogares del departamento (Censo 2018) con atributos para el ABM.", "ABM", "INE Censo 2018", ["ine_censo2018_csv"]),
    "atributos_municipio.csv": ("Atributos medios de los hogares por municipio.", "ABM, SIG y demo", "INE Censo 2018", ["ine_censo2018_csv"]),
    "lugares_poblados.csv": ("Lugares poblados del Censo con coordenadas y atributos medios de sus hogares.", "ABM, SIG y demo", "INE Censo 2018", ["ine_censo2018_csv"]),
    "hospitales.csv": ("Hospitales y establecimientos de OSM en el departamento.", "Sistema de salud, SIG y demo", "OpenStreetMap", ["osm_hospitales"]),
    "distancias.csv": ("Distancia y tiempo por carretera entre cabeceras municipales.", "Redes", "OpenStreetMap (Geofabrik) + OSMnx", ["geofabrik_osm"]),
    "flujos_od.csv": ("Flujos diarios entre municipios del modelo gravitacional calibrado con el Censo.", "Redes, dinámica de sistemas", "Modelo propio; Censo 2018", ["ine_censo2018_csv"]),
    "od_censo.csv": ("OBSERVADO. Matriz origen-destino de trabajo y estudio del Censo 2018.", "Redes, dinámica de sistemas", "INE Censo 2018", ["ine_censo2018_csv"]),
    "grilla_piloto.csv": ("Grilla de la zona piloto del ABM con población y atributos de hogar por celda.", "ABM", "WorldPop 2020; INE Censo 2018", ["worldpop_2020"]),
    "ca_mosquitos.csv": ("Densidad semanal de mosquitos por celda del autómata celular.", "Demo", "Modelo propio con clima_semanal.csv", []),
}


def _fecha(manifest: dict, ids: list[str]) -> str:
    fechas = sorted({manifest[i].get("fecha_descarga", "")[:10] for i in ids if i in manifest and manifest[i].get("fecha_descarga")})
    return ", ".join(fechas) or "—"


def _rango(s: pd.Series) -> str:
    if s.name in ("anio", "semana_epi", "fila", "col", "anio_poblacion", "lugar_poblado", "lugar_poblado_ref"):
        v = s.dropna()
        return f"{int(v.min())} – {int(v.max())}" if len(v) and pd.api.types.is_numeric_dtype(v) else f"{s.nunique()} valores"
    if pd.api.types.is_bool_dtype(s):
        return f"{s.mean():.0%} verdadero"
    if pd.api.types.is_numeric_dtype(s):
        v = s.dropna()
        if v.empty:
            return "vacío"
        return f"{v.min():,.4g} – {v.max():,.4g}" + (f" ({s.isna().sum()} vacíos)" if s.isna().any() else "")
    n = s.nunique()
    return f"{n} valores" + (f" ({s.isna().sum()} vacíos)" if s.isna().any() else "")


def main() -> None:
    manifest = {}
    if (RAW / "manifest.json").exists():
        manifest = {r["id"]: r for r in json.loads((RAW / "manifest.json").read_text(encoding="utf-8"))}
    lineas = [
        "# Diccionario de datos — DengueSim GT (módulo de datos)",
        "",
        f"Generado automáticamente por `src/datos/diccionario.py` el {date.today().isoformat()}. "
        "Leer las tablas con `dtype={'cod_muni': str, 'cod_i': str, 'cod_j': str}` para conservar los ceros iniciales "
        "(o usar `leer_procesado()` de `src/datos/comun.py`).",
        "",
        "La procedencia de cada archivo crudo (URL, tamaño, SHA-256, fecha) está en `data/raw/manifest.json`.",
        "",
    ]
    for nombre, (desc, usa, fuente, ids) in TABLAS.items():
        ruta = PROCESSED / nombre
        if not ruta.exists():
            continue
        df = leer_procesado(nombre)
        lineas += [
            f"## `{nombre}`",
            "",
            f"{desc}",
            "",
            f"- **Filas:** {len(df):,} · **Módulos que la usan:** {usa}",
            f"- **Fuente:** {fuente}",
            f"- **Fecha de descarga:** {_fecha(manifest, ids)}",
            "",
            "| Columna | Significado | Unidad | Rango observado |",
            "|---|---|---|---|",
        ]
        for c in df.columns:
            sig, uni = COL.get(c, ("—", "—"))
            lineas.append(f"| `{c}` | {sig} | {uni} | {_rango(df[c])} |")
        lineas.append("")
    extras = [
        ("sigma_hogar.json", "Medias y covarianza observadas de (ingreso, agua_entubada, almacena_agua); correlación latente, umbrales y factor de Cholesky para generar agentes. Incluye un bloque por municipio. Lo usa el ABM."),
        ("parametros_datos.json", "Parámetros estimados con los datos (fracción que viaja, exponentes gravitacionales calibrados, lluvia de referencia, etc.). Tienen prioridad sobre los de config/parametros.yaml."),
        ("limites_municipios.geojson", "Polígonos de los 17 municipios con cod_muni (geoBoundaries)."),
        ("grilla_piloto.geojson", "Polígonos de las celdas de la grilla piloto (mismas columnas que grilla_piloto.csv)."),
        ("red_vial_nodos.csv.gz / red_vial_aristas.csv.gz", "Red vial para isocronas; cargar con `cargar_red()` de src/sig/red_vial.py."),
        ("ca_mosquitos.npz / ca_mosquitos.gif", "Arreglos (semanas × filas × columnas) y animación del autómata celular."),
        ("validacion/", "Tablas de control de calidad: comparaciones entre fuentes y calibraciones."),
    ]
    lineas += ["## Otros archivos", "", "| Archivo | Contenido |", "|---|---|"]
    lineas += [f"| `{a}` | {b} |" for a, b in extras]
    (RAIZ / "data" / "diccionario_datos.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("  -> data/diccionario_datos.md")


if __name__ == "__main__":
    main()
