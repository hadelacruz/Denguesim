"""Red vial (OpenStreetMap) y matriz de distancias/tiempos entre cabeceras.

Se lee el extracto de Geofabrik (``guatemala-latest.osm.pbf``) recortado al
departamento de Guatemala más un margen, se arma la red para vehículos con
pyrosm y se le asignan velocidades y tiempos de viaje con OSMnx (velocidad
``maxspeed`` cuando existe; si no, la media por tipo de vía que imputa OSMnx o
las velocidades por defecto de ``VELOCIDAD_KMH``).

Salidas:
  data/processed/distancias.csv           cod_i, cod_j, dist_km, tiempo_min
  data/processed/red_vial_nodos.csv.gz     osmid, y, x
  data/processed/red_vial_aristas.csv.gz   u, v, key, highway, length (m), speed_kph, travel_time (s)
  (para las isocronas del análisis SIG; los tiempos son de flujo libre, sin congestión)

Para usar la red en otro módulo:
    from src.sig.red_vial import cargar_red
    G = cargar_red()   # networkx.MultiDiGraph de OSMnx con 'length' (m) y 'travel_time' (s)
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import networkx as nx
import osmnx as ox
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "datos"))
from comun import CRS_GEO, PROCESSED, RAW, guardar, municipios  # noqa: E402

PBF = RAW / "geo" / "guatemala-latest.osm.pbf"
GPKG = PROCESSED / "red_vial_guatemala.gpkg"
MARGEN_GRADOS = 0.05  # ~5 km alrededor del departamento

# Velocidades por defecto (km/h) cuando OSM no trae maxspeed. Valores típicos
# urbanos/periurbanos de la región metropolitana con congestión moderada.
VELOCIDAD_KMH = {
    "motorway": 70, "motorway_link": 40, "trunk": 60, "trunk_link": 35,
    "primary": 45, "primary_link": 30, "secondary": 35, "secondary_link": 25,
    "tertiary": 30, "tertiary_link": 20, "unclassified": 25, "residential": 20,
    "living_street": 10, "service": 15, "track": 15, "road": 20,
}


def construir_red() -> nx.MultiDiGraph:
    from pyrosm import OSM

    lim = gpd.read_file(PROCESSED / "limites_municipios.geojson").to_crs(CRS_GEO)
    minx, miny, maxx, maxy = lim.total_bounds
    bbox = [minx - MARGEN_GRADOS, miny - MARGEN_GRADOS, maxx + MARGEN_GRADOS, maxy + MARGEN_GRADOS]
    osm = OSM(str(PBF), bounding_box=bbox)
    nodos, aristas = osm.get_network(network_type="driving", nodes=True)
    G = osm.to_graph(nodos, aristas, graph_type="networkx", osmnx_compatible=True, retain_all=False)
    G = ox.truncate.largest_component(G, strongly=True)
    G = ox.routing.add_edge_speeds(G, hwy_speeds=VELOCIDAD_KMH, fallback=25)
    G = ox.routing.add_edge_travel_times(G)
    return G


NODOS = PROCESSED / "red_vial_nodos.csv.gz"
ARISTAS = PROCESSED / "red_vial_aristas.csv.gz"


def guardar_red(G: nx.MultiDiGraph, gpkg: bool = False) -> None:
    """Guarda la red como dos CSV comprimidos (nodos y aristas, sin geometría
    de las calles) para que pese poco en el repositorio. Con ``gpkg=True``
    también escribe un GeoPackage con la geometría completa (no se versiona)."""
    n, e = ox.convert.graph_to_gdfs(G)
    n = n[["y", "x"]].reset_index()
    e = e.reset_index()
    e["highway"] = e["highway"].astype(str)
    e = e[["u", "v", "key", "highway", "length", "speed_kph", "travel_time"]]
    e[["length", "speed_kph", "travel_time"]] = e[["length", "speed_kph", "travel_time"]].round(2)
    n.to_csv(NODOS, index=False, compression="gzip")
    e.to_csv(ARISTAS, index=False, compression="gzip")
    print(f"  -> {NODOS.name} y {ARISTAS.name}: {len(n)} nodos, {len(e)} aristas")
    if gpkg:
        nn, ee = ox.convert.graph_to_gdfs(G)
        for c in ee.columns:
            if c != "geometry" and ee[c].dtype == object:
                ee[c] = ee[c].astype(str)
        GPKG.unlink(missing_ok=True)
        nn[["y", "x", "geometry"]].to_file(GPKG, layer="nodos", driver="GPKG")
        ee.reset_index().to_file(GPKG, layer="aristas", driver="GPKG")


def cargar_red() -> nx.MultiDiGraph:
    """MultiDiGraph compatible con OSMnx (atributos x, y, length en m, travel_time en s)."""
    n = pd.read_csv(NODOS)
    e = pd.read_csv(ARISTAS)
    G = nx.MultiDiGraph(crs="epsg:4326")
    G.add_nodes_from((int(r.osmid), {"x": r.x, "y": r.y}) for r in n.itertuples())
    G.add_edges_from(
        (int(r.u), int(r.v), int(r.key), {"highway": r.highway, "length": r.length, "speed_kph": r.speed_kph, "travel_time": r.travel_time})
        for r in e.itertuples()
    )
    return G


def matriz_cabeceras(G: nx.MultiDiGraph) -> pd.DataFrame:
    m = municipios()
    nodos = ox.distance.nearest_nodes(G, m.lon_cabecera.values, m.lat_cabecera.values)
    filas = []
    for i, (ci, ni) in enumerate(zip(m.cod_muni, nodos)):
        largo = nx.single_source_dijkstra_path_length(G, ni, weight="length")
        tiempo = nx.single_source_dijkstra_path_length(G, ni, weight="travel_time")
        for cj, nj in zip(m.cod_muni, nodos):
            if ci == cj:
                continue
            filas.append({"cod_i": ci, "cod_j": cj, "dist_km": largo[nj] / 1000, "tiempo_min": tiempo[nj] / 60})
    d = pd.DataFrame(filas)
    d[["dist_km", "tiempo_min"]] = d[["dist_km", "tiempo_min"]].round(3)
    return d


def main() -> None:
    print("[red vial] OSM (Geofabrik) + OSMnx")
    G = construir_red()
    print(f"  red: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")
    guardar_red(G)
    d = matriz_cabeceras(G)
    guardar(d, "distancias.csv", ["cod_i", "cod_j", "dist_km", "tiempo_min"])
    print(f"  distancia media {d.dist_km.mean():.1f} km, tiempo medio {d.tiempo_min.mean():.1f} min")


if __name__ == "__main__":
    main()
