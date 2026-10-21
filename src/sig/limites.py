"""Límites municipales del departamento de Guatemala unidos por código INE.

Fuente principal: geoBoundaries gbOpen ADM2 (CC BY 4.0).
Cada polígono se asigna a un ``cod_muni`` buscando el polígono que contiene la
cabecera municipal de ``config/municipios.csv`` (evita confundir municipios
homónimos, p. ej. San Pedro Sacatepéquez de Guatemala y de San Marcos).

Salida: data/processed/limites_municipios.geojson (cod_muni, nombre, area_km2)
"""

from __future__ import annotations

import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "datos"))
from comun import CRS_GEO, CRS_METRICO, PROCESSED, RAW, VALIDACION, municipios, normalizar  # noqa: E402

ARCHIVO = RAW / "geo" / "geoBoundaries-GTM-ADM2.geojson"
OSM = RAW / "osm" / "municipios.json"


def cabeceras() -> gpd.GeoDataFrame:
    m = municipios()
    return gpd.GeoDataFrame(m, geometry=gpd.points_from_xy(m.lon_cabecera, m.lat_cabecera), crs=CRS_GEO)


def cargar_limites() -> gpd.GeoDataFrame:
    gb = gpd.read_file(ARCHIVO).to_crs(CRS_GEO)
    unidos = gpd.sjoin(cabeceras(), gb, predicate="within", how="left")
    if unidos["shapeID"].isna().any():
        faltan = unidos.loc[unidos["shapeID"].isna(), "nombre"].tolist()
        raise RuntimeError(f"Cabeceras sin polígono en geoBoundaries: {faltan}")
    # Control de calidad: el nombre del polígono debe parecerse al oficial.
    unidos["similitud_nombre"] = [
        SequenceMatcher(None, normalizar(a), normalizar(b)).ratio()
        for a, b in zip(unidos["nombre"], unidos["shapeName"])
    ]
    sospechosos = unidos[unidos["similitud_nombre"] < 0.8]
    if len(sospechosos):
        print("  ! nombres distintos entre INE y geoBoundaries:")
        print(sospechosos[["cod_muni", "nombre", "shapeName"]].to_string(index=False))
    geo = gb.set_index("shapeID").loc[unidos["shapeID"], "geometry"].values
    lim = gpd.GeoDataFrame(
        {
            "cod_muni": unidos["cod_muni"].values,
            "nombre": unidos["nombre"].values,
            "nombre_fuente": unidos["shapeName"].values,
            "shape_id": unidos["shapeID"].values,
        },
        geometry=list(geo),
        crs=CRS_GEO,
    )
    lim["area_km2"] = lim.to_crs(CRS_METRICO).area / 1e6
    return lim.sort_values("cod_muni").reset_index(drop=True)


def comparar_con_osm(lim: gpd.GeoDataFrame) -> pd.DataFrame | None:
    """Compara áreas con los polígonos de OpenStreetMap (validación cruzada)."""
    if not OSM.exists():
        return None
    datos = json.loads(OSM.read_text(encoding="utf-8"))
    filas = []
    for e in datos.get("elements", []):
        if e.get("type") != "relation":
            continue
        try:
            geom = _poligono_osm(e)
        except Exception:
            continue
        filas.append({"osm_rel": e["id"], "geometry": geom})
    if not filas:
        return None
    osm = gpd.GeoDataFrame(filas, crs=CRS_GEO)
    ref = municipios()[["cod_muni", "osm_rel_municipio"]]
    osm = osm.merge(ref, left_on="osm_rel", right_on="osm_rel_municipio")
    osm["area_osm_km2"] = osm.to_crs(CRS_METRICO).area / 1e6
    comp = lim[["cod_muni", "nombre", "area_km2"]].merge(osm[["cod_muni", "area_osm_km2"]], on="cod_muni", how="left")
    comp["dif_pct"] = 100 * (comp["area_osm_km2"] - comp["area_km2"]) / comp["area_km2"]
    return comp


def _poligono_osm(rel: dict):
    """Arma el polígono de una relación OSM (salida 'out geom' de Overpass)."""
    from shapely.ops import linemerge, polygonize, unary_union
    from shapely.geometry import LineString

    lineas = [
        LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
        for m in rel.get("members", [])
        if m.get("type") == "way" and m.get("role") in ("outer", "") and m.get("geometry")
    ]
    return unary_union(list(polygonize(linemerge(lineas))))


def main() -> gpd.GeoDataFrame:
    print("[limites] geoBoundaries ADM2")
    lim = cargar_limites()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    ruta = PROCESSED / "limites_municipios.geojson"
    lim.to_file(ruta, driver="GeoJSON")
    print(f"  -> {ruta.relative_to(PROCESSED.parents[1])} ({len(lim)} municipios, {lim.area_km2.sum():.0f} km2)")
    comp = comparar_con_osm(lim)
    if comp is not None:
        VALIDACION.mkdir(parents=True, exist_ok=True)
        comp.round(2).to_csv(VALIDACION / "limites_vs_osm.csv", index=False)
        print(f"  diferencia media de área vs OSM: {comp['dif_pct'].abs().mean():.1f} %")
    return lim


if __name__ == "__main__":
    main()
