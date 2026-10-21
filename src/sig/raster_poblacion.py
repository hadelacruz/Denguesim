"""Ráster de población WorldPop: agregación por municipio y grilla piloto del ABM.

1. Zonal statistics (suma de personas por píxel de ~100 m) dentro de cada
   polígono municipal → validacion/poblacion_worldpop_vs_censo.csv y la
   columna ``poblacion_worldpop`` de poblacion.csv.
2. Grilla piloto: celdas cuadradas de ``zona_piloto.celda_m`` metros (UTM 15N)
   sobre el municipio piloto, con la población WorldPop de cada celda.
   A cada celda se le asignan los atributos de hogar del Censo 2018 del lugar
   poblado correspondiente (lugares_poblados.csv). Si ``zona_piloto.cod_muni`` es null en parametros.yaml se elige el
   municipio con mayor incidencia media de dengue (casos / 100 000 hab.)
   entre los de densidad > 1 000 hab/km².

Salidas: data/processed/grilla_piloto.csv y grilla_piloto.geojson
  cod_celda, fila, col, x_utm, y_utm, lat, lon, poblacion, cod_muni
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterstats import zonal_stats
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "datos"))
from comun import CRS_GEO, CRS_METRICO, PROCESSED, RAW, VALIDACION, guardar, leer_procesado, parametros, registrar_parametro  # noqa: E402

RASTER = RAW / "geo" / "gtm_ppp_2020.tif"


def poblacion_por_municipio(lim: gpd.GeoDataFrame) -> pd.DataFrame:
    with rasterio.open(RASTER) as src:
        lim_r = lim.to_crs(src.crs)
        nodata = src.nodata
    stats = zonal_stats(lim_r, str(RASTER), stats=["sum", "count"], nodata=nodata, all_touched=False)
    return pd.DataFrame({
        "cod_muni": lim["cod_muni"].values,
        "poblacion_worldpop": [round(s["sum"] or 0) for s in stats],
        "pixeles": [s["count"] for s in stats],
    })


def elegir_piloto() -> tuple[str, pd.DataFrame]:
    p = parametros()["zona_piloto"]["cod_muni"]["valor"]
    pob = leer_procesado("poblacion.csv")
    casos = leer_procesado("casos_anuales_muni.csv")
    casos = casos[casos.anio.between(2014, 2024)].groupby("cod_muni").casos.mean().rename("casos_medios")
    t = pob.set_index("cod_muni").join(casos)
    t["incidencia_100k"] = 1e5 * t["casos_medios"] / t["poblacion"]
    candidatos = t[t["densidad"] > 1000].sort_values("incidencia_100k", ascending=False)
    elegido = str(p) if p else candidatos.index[0]
    return elegido.zfill(4), t.reset_index()


def grilla(poligono_utm, celda: float) -> gpd.GeoDataFrame:
    minx, miny, maxx, maxy = poligono_utm.bounds
    minx, miny = np.floor(minx / celda) * celda, np.floor(miny / celda) * celda
    xs = np.arange(minx, maxx, celda)
    ys = np.arange(maxy, miny, -celda)  # fila 0 = norte
    filas = []
    for i, y in enumerate(ys):
        for j, x in enumerate(xs):
            c = box(x, y - celda, x + celda, y)
            if c.intersects(poligono_utm):
                filas.append({"fila": i, "col": j, "x_utm": x + celda / 2, "y_utm": y - celda / 2, "geometry": c})
    return gpd.GeoDataFrame(filas, crs=CRS_METRICO)


def atributos_por_celda(g: gpd.GeoDataFrame, cod: str) -> gpd.GeoDataFrame:
    """Asigna a cada celda los atributos de hogar del Censo 2018 de los lugares
    poblados (puntos del INE) que caen en ella, ponderados por hogares; si la
    celda no contiene ninguno, toma el lugar poblado más cercano del municipio."""
    lp = leer_procesado("lugares_poblados.csv")
    lp = lp[lp.cod_muni == cod]
    pts = gpd.GeoDataFrame(lp, geometry=gpd.points_from_xy(lp.lon, lp.lat), crs=CRS_GEO).to_crs(CRS_METRICO)
    cols = ["prop_agua_entubada", "prop_almacena_agua", "indice_riqueza_medio"]
    dentro = gpd.sjoin(pts, g[["geometry"]], predicate="within", how="inner")
    pond = dentro.groupby("index_right").apply(
        lambda d: pd.Series({c: np.average(d[c], weights=d.hogares) for c in cols} | {"lugar_poblado_ref": int(d.sort_values("hogares").lugar_poblado.iloc[-1])}),
        include_groups=False,
    )
    cerca = gpd.sjoin_nearest(g[["geometry"]].assign(geometry=g.centroid), pts[cols + ["lugar_poblado", "geometry"]], how="left")
    cerca = cerca[~cerca.index.duplicated()].rename(columns={"lugar_poblado": "lugar_poblado_ref"})
    out = cerca[cols + ["lugar_poblado_ref"]].copy()
    out.loc[pond.index, cols + ["lugar_poblado_ref"]] = pond[cols + ["lugar_poblado_ref"]].values
    for c in cols:
        g[c] = out[c].astype(float).round(4)
    g["lugar_poblado_ref"] = out["lugar_poblado_ref"].astype(int)
    return g


def main() -> None:
    print("[raster] WorldPop 2020")
    lim = gpd.read_file(PROCESSED / "limites_municipios.geojson")
    zon = poblacion_por_municipio(lim)

    pob = leer_procesado("poblacion.csv")
    pob = pob.drop(columns=[c for c in ["poblacion_worldpop"] if c in pob.columns]).merge(zon[["cod_muni", "poblacion_worldpop"]], on="cod_muni", how="left")
    guardar(pob, "poblacion.csv", ["cod_muni", "nombre", "poblacion", "area_km2", "densidad"])
    VALIDACION.mkdir(parents=True, exist_ok=True)
    comp = pob[["cod_muni", "nombre", "poblacion", "poblacion_worldpop"]].copy()
    comp["razon_worldpop_censo"] = (comp.poblacion_worldpop / comp.poblacion).round(3)
    comp.to_csv(VALIDACION / "poblacion_worldpop_vs_censo.csv", index=False)

    cod, tabla = elegir_piloto()
    tabla.round(2).to_csv(VALIDACION / "seleccion_zona_piloto.csv", index=False)
    registrar_parametro("zona_piloto", "cod_muni", cod, "código INE",
                        "Mayor incidencia media 2014-2024 entre municipios con densidad > 1 000 hab/km² (ver validacion/seleccion_zona_piloto.csv).")
    celda = float(parametros()["zona_piloto"]["celda_m"]["valor"])
    poligono = lim.to_crs(CRS_METRICO).set_index("cod_muni").loc[cod, "geometry"]
    g = grilla(poligono, celda)
    with rasterio.open(RASTER) as src:
        g_r = g.to_crs(src.crs)
        nodata = src.nodata
    # Población de la parte de cada celda dentro del municipio.
    recortada = g_r.copy()
    recortada["geometry"] = g.intersection(poligono).to_crs(g_r.crs)
    stats = zonal_stats(recortada, str(RASTER), stats=["sum"], nodata=nodata, all_touched=False)
    g["poblacion"] = [round(s["sum"] or 0) for s in stats]
    g["fraccion_en_municipio"] = (g.intersection(poligono).area / g.area).round(3)
    centros = gpd.GeoSeries(gpd.points_from_xy(g.x_utm, g.y_utm), crs=CRS_METRICO).to_crs(CRS_GEO)
    g["lat"], g["lon"] = centros.y.round(6), centros.x.round(6)
    g["cod_muni"] = cod
    g = atributos_por_celda(g, cod)
    g.insert(0, "cod_celda", [f"C{r:03d}_{c:03d}" for r, c in zip(g.fila, g.col)])
    cols = ["cod_celda", "fila", "col", "x_utm", "y_utm", "lat", "lon", "poblacion", "fraccion_en_municipio", "cod_muni",
            "prop_agua_entubada", "prop_almacena_agua", "indice_riqueza_medio", "lugar_poblado_ref"]
    guardar(pd.DataFrame(g[cols]), "grilla_piloto.csv", cols)
    g.to_crs(CRS_GEO)[cols + ["geometry"]].to_file(PROCESSED / "grilla_piloto.geojson", driver="GeoJSON")
    print(f"  zona piloto {cod}: {len(g)} celdas de {celda:.0f} m, {g.poblacion.sum():,.0f} hab. (WorldPop)")


if __name__ == "__main__":
    main()
