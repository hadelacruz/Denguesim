"""Hospitales y establecimientos con encamamiento del departamento de Guatemala.

Fuente: OpenStreetMap (amenity=hospital / healthcare=hospital) vía Overpass.
El número de camas por hospital NO está publicado en datos abiertos (MSPAS,
IGSS ni OSM lo traen); la columna ``camas`` queda vacía salvo que OSM tenga la
etiqueta ``beds``.

Salida: data/processed/hospitales.csv
  id_hosp, nombre, cod_muni, lat, lon, camas, sector, es_hospital, atiende_dengue, osm_id, camas_fuente
  atiende_dengue = hospital general (excluye salud mental, rehabilitación, oncología, etc.)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import CRS_GEO, PROCESSED, RAW, guardar, normalizar  # noqa: E402

ARCHIVO = RAW / "osm" / "hospitales.json"

# Palabras que indican un establecimiento con encamamiento.
HOSPITAL = re.compile(r"HOSPITAL|SANATORIO|IGSS|MATERNIDAD|CENTRO MEDICO|CENTRO HOSPITALARIO|MULTIMEDICA|CLINICA.*24|EMERGENCIA")
# Hospitales especializados que no reciben dengue (salud mental, rehabilitación, cáncer, etc.).
ESPECIALIZADO = re.compile(r"SALUD MENTAL|REHABILITACION|ONCOLOG|CANCER|DIABETES|JUBILADOS|BIOPSIA|OFTALM|OCULAR|CONSULTA EXTERNA|VETERINAR|HOSPICIO")
NO_HOSPITAL = re.compile(r"CENTRO DE SALUD|PUESTO DE SALUD|LABORATORIO|FARMACIA|DENTAL|ODONTO|OPTICA|VETERINARI")
MSPAS = re.compile(r"NACIONAL|ROOSEVELT|SAN JUAN DE DIOS|INFECTOLOGIA|FEDERICO MORA|SAN VICENTE|AMATITLAN|VILLA NUEVA|ANTIGUO HOSPITAL|ELISA MARTINEZ|MINISTERIO|MSPAS")


def sector(nombre: str, operador: str, tipo_op: str) -> str:
    t = normalizar(f"{nombre} {operador}")
    if "IGSS" in t or "SEGURIDAD SOCIAL" in t:
        return "IGSS"
    if "MILITAR" in t:
        return "militar"
    if MSPAS.search(t) or tipo_op == "government":
        return "MSPAS"
    return "privado_u_ong"


def cargar() -> pd.DataFrame:
    datos = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    filas = []
    for e in datos["elements"]:
        tags = e.get("tags", {})
        lat = e.get("lat") or e.get("center", {}).get("lat")
        lon = e.get("lon") or e.get("center", {}).get("lon")
        if lat is None:
            continue
        nombre = tags.get("name") or tags.get("official_name") or ""
        beds = pd.to_numeric(tags.get("beds"), errors="coerce")
        n = normalizar(nombre)
        filas.append({
            "osm_id": f"{e['type']}/{e['id']}",
            "nombre": nombre.strip() or "(sin nombre en OSM)",
            "lat": lat, "lon": lon,
            "camas": beds,
            "camas_fuente": "OSM beds" if pd.notna(beds) else "",
            "sector": sector(nombre, tags.get("operator", ""), tags.get("operator:type", "")),
            "es_hospital": bool(n) and bool(HOSPITAL.search(n)) and not NO_HOSPITAL.search(n),
            "general": not ESPECIALIZADO.search(n),
        })
    return pd.DataFrame(filas).drop_duplicates("osm_id")


def main() -> pd.DataFrame:
    print("[hospitales] OpenStreetMap")
    h = cargar()
    lim = gpd.read_file(PROCESSED / "limites_municipios.geojson")
    pts = gpd.GeoDataFrame(h, geometry=gpd.points_from_xy(h.lon, h.lat), crs=CRS_GEO)
    h = gpd.sjoin(pts, lim[["cod_muni", "geometry"]], predicate="within", how="inner").drop(columns=["geometry", "index_right"])
    h["atiende_dengue"] = h.es_hospital & h.general
    h = h.drop(columns="general").sort_values(["es_hospital", "sector", "cod_muni", "nombre"], ascending=[False, True, True, True]).reset_index(drop=True)
    h.insert(0, "id_hosp", [f"H{i + 1:03d}" for i in range(len(h))])
    h["camas"] = h["camas"].astype("Int64")
    guardar(h, "hospitales.csv", ["id_hosp", "nombre", "cod_muni", "lat", "lon", "camas"])
    print(f"  {int(h.es_hospital.sum())} hospitales/sanatorios de {len(h)} puntos OSM; con camas: {int(h.camas.notna().sum())}")
    print("  por sector:", h[h.es_hospital].sector.value_counts().to_dict())
    return h


if __name__ == "__main__":
    main()
