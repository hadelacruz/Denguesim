"""G1 · Isocronas de 30 y 60 minutos desde los hospitales, cruzadas con la población.

1. Red vial con cargar_red() (OSM, 86 798 nodos). Cada hospital con atiende_dengue = True
   se ubica en su nodo vial más cercano (KD-tree sobre coordenadas UTM 15N, EPSG:32615,
   el mismo sistema de x_utm / y_utm de grilla_piloto.csv).
2. Tiempo de cada nodo al hospital más cercano: Dijkstra de múltiples fuentes
   (scipy.sparse.csgraph.dijkstra con min_only=True) sobre la red INVERTIDA (así se mide
   el viaje nodo → hospital). Con un factor de congestión f todas las aristas se
   multiplican por f, y como el camino más corto no cambia al escalar todos los pesos,
   el tiempo con congestión es f × el tiempo en flujo libre.
3. Isocrona de t minutos = unión de buffers de sig.radio_buffer_m alrededor de los nodos
   con tiempo ≤ t, recortada al límite departamental. Para que la unión sea rápida, los
   nodos se agrupan antes en una malla de 100 m (cambia el borde en < 100 m).
4. Población cubierta. APROXIMACIÓN: el ráster WorldPop no está en el repositorio (es un
   archivo crudo pesado), así que la población de cada municipio (poblacion.csv, 2024) se
   reparte de forma UNIFORME sobre su área: cubierta_i = poblacion_i · área(isocrona ∩ i) / área(i).

Salidas: data/processed/sig/cobertura_isocronas.csv, data/processed/sig/isocronas_30.geojson,
         data/processed/sig/isocronas_60.geojson (factor 1.0) y figuras/sig/isocronas.png
Uso (desde la raíz):  python src/sig/isocronas.py
"""

import sys

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shapely  # noqa: E402
from pyproj import Transformer  # noqa: E402
from scipy.sparse import csr_matrix  # noqa: E402
from scipy.sparse.csgraph import dijkstra  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/sig")
from comun import CRS_GEO, CRS_METRICO, PROCESSED, leer_procesado, parametro  # noqa: E402
from red_vial import cargar_red  # noqa: E402

MALLA_M = 100.0
A_UTM = Transformer.from_crs(CRS_GEO, CRS_METRICO, always_xy=True)


def red_dispersa(G):
    """Matriz dispersa de tiempos (s) entre nodos; con aristas paralelas, la menor."""
    nodos = np.array(list(G.nodes))
    indice = {n: i for i, n in enumerate(nodos)}
    u, v, t = zip(*((indice[a], indice[b], d["travel_time"]) for a, b, d in G.edges(data=True)))
    tabla = pd.DataFrame({"u": u, "v": v, "t": t}).groupby(["u", "v"], as_index=False).t.min()
    M = csr_matrix((tabla.t.to_numpy() + 1e-6, (tabla.u, tabla.v)), shape=(len(nodos), len(nodos)))
    x, y = A_UTM.transform([G.nodes[n]["x"] for n in nodos], [G.nodes[n]["y"] for n in nodos])
    return M, np.column_stack([x, y])


def hospitales_dengue():
    h = leer_procesado("hospitales.csv")
    return h[h.atiende_dengue.astype(bool)].reset_index(drop=True)


def tiempo_al_hospital(M, xy, hospitales):
    """Minutos de cada nodo al hospital más cercano (flujo libre)."""
    hx, hy = A_UTM.transform(hospitales.lon.to_numpy(), hospitales.lat.to_numpy())
    _, nodos_h = cKDTree(xy).query(np.column_stack([hx, hy]))
    segundos = dijkstra(M.T.tocsr(), directed=True, indices=np.unique(nodos_h), min_only=True)
    return segundos / 60.0


def poligono_isocrona(xy, minutos_nodo, minutos, factor, limite, radio=None):
    """Unión de buffers alrededor de los nodos alcanzados, recortada al departamento."""
    radio = parametro("sig", "radio_buffer_m") if radio is None else radio
    alcanzados = xy[factor * minutos_nodo <= minutos]
    if len(alcanzados) == 0:
        return shapely.Polygon()
    malla = np.unique(np.round(alcanzados / MALLA_M) * MALLA_M, axis=0)
    buffers = shapely.buffer(shapely.points(malla), radio, quad_segs=4)
    return shapely.intersection(shapely.union_all(buffers), limite)


def cobertura(poligono, municipios_utm, poblacion, minutos, factor):
    filas = []
    for cod, geom in zip(municipios_utm.cod_muni, municipios_utm.geometry):
        frac = shapely.intersection(geom, poligono).area / geom.area
        pob = float(poblacion[cod])
        filas.append({"cod_muni": cod, "minutos": minutos, "factor_congestion": factor,
                      "pob_total": pob, "pob_cubierta": pob * frac, "pct_cubierta": 100 * frac})
    df = pd.DataFrame(filas)
    total, cub = df.pob_total.sum(), df.pob_cubierta.sum()
    df.loc[len(df)] = {"cod_muni": "departamento", "minutos": minutos, "factor_congestion": factor,
                       "pob_total": total, "pob_cubierta": cub, "pct_cubierta": 100 * cub / total}
    return df


def figura(isocronas, municipios_utm, hospitales):
    fig, ax = plt.subplots(figsize=(7, 7.5))
    municipios_utm.boundary.plot(ax=ax, color="#9a9a96", linewidth=0.6)
    for minutos, color in ((60, "#a9cdf0"), (30, "#2a78d6")):
        gpd.GeoSeries([isocronas[minutos]], crs=CRS_METRICO).plot(ax=ax, color=color, alpha=0.75, linewidth=0)
    hx, hy = A_UTM.transform(hospitales.lon.to_numpy(), hospitales.lat.to_numpy())
    ax.scatter(hx, hy, s=10, color="#b3261e", zorder=3, label="hospitales que atienden dengue")
    ax.set_title("Isocronas de 30 min (azul) y 60 min (celeste) en flujo libre", fontsize=10)
    ax.set_axis_off()
    ax.legend(frameon=False, loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig("figuras/sig/isocronas.png", dpi=150)
    plt.close(fig)


def main():
    G = cargar_red()
    M, xy = red_dispersa(G)
    hospitales = hospitales_dengue()
    minutos_nodo = tiempo_al_hospital(M, xy, hospitales)
    municipios = gpd.read_file(PROCESSED / "limites_municipios.geojson").to_crs(CRS_METRICO)
    limite = shapely.union_all(municipios.geometry.to_numpy())
    poblacion = leer_procesado("poblacion.csv").set_index("cod_muni").poblacion
    tablas, base = [], {}
    for factor in parametro("sig", "factores_congestion"):
        for minutos in parametro("sig", "minutos_isocronas"):
            poligono = poligono_isocrona(xy, minutos_nodo, minutos, factor, limite)
            tablas.append(cobertura(poligono, municipios, poblacion, minutos, factor))
            if factor == 1.0:
                base[minutos] = poligono
    tabla = pd.concat(tablas, ignore_index=True)
    tabla[["pob_total", "pob_cubierta"]] = tabla[["pob_total", "pob_cubierta"]].round(0)
    tabla["pct_cubierta"] = tabla.pct_cubierta.round(2)
    tabla.to_csv(PROCESSED / "sig" / "cobertura_isocronas.csv", index=False)
    for minutos, poligono in base.items():
        g = gpd.GeoDataFrame({"minutos": [minutos], "factor_congestion": [1.0]},
                             geometry=[poligono.simplify(50)], crs=CRS_METRICO).to_crs(CRS_GEO)
        g.to_file(PROCESSED / "sig" / f"isocronas_{minutos}.geojson", driver="GeoJSON")
    figura(base, municipios, hospitales)
    dep = tabla[tabla.cod_muni == "departamento"]
    print(f"{len(hospitales)} hospitales · {M.shape[0]} nodos")
    print(dep[["minutos", "factor_congestion", "pob_cubierta", "pct_cubierta"]].to_string(index=False))


if __name__ == "__main__":
    main()
