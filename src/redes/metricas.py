"""D2 · Métricas de red y centralidad de los municipios → centralidad.csv.

Centralidades (red gravitacional con umbral 0, que es un grafo completo):
  grado          fuerza total s_i = Σ_j w_ij + Σ_j w_ji (personas/día). En un
                 grafo completo el grado sin pesos es 16 para todos y no distingue.
  intermediacion betweenness dirigida y normalizada, con distancia d_ij = 1 / w_ij:
                 un flujo grande equivale a un camino "corto" (S12).
  eigenvector    centralidad de vector propio del grafo NO dirigido, ponderado
                 por flujo (x = (1/λ)·A·x): importa estar unido a nodos importantes.

Métricas globales (S12): densidad, ⟨k⟩, ⟨k²⟩, clustering, distancia media y
diámetro (sin pesos, en la componente gigante si la red no es conexa).

Salidas:
  data/processed/centralidad.csv                    (contrato: 4 columnas)
  data/processed/redes/metricas_red.csv
  data/processed/redes/centralidad_censo.csv
  data/processed/redes/spearman_gravitacional_censo.csv
  figuras/redes/red_od.png, figuras/redes/distribucion_grado.png

Uso (desde la raíz):  python src/redes/metricas.py
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/redes")
from comun import PROCESSED, parametro  # noqa: E402
from construir_red import a_no_dirigida, red_censo, red_gravitacional  # noqa: E402

COLUMNAS_CENTRALIDAD = ["cod_muni", "grado", "intermediacion", "eigenvector"]
SALIDA_REDES = PROCESSED / "redes"
FIGURAS = PROCESSED.parents[1] / "figuras" / "redes"
AZUL, NARANJA, GRIS = "#2a78d6", "#eb6834", "#8a8984"


def centralidades(G):
    """DataFrame con grado (fuerza), intermediación y eigenvector de cada nodo."""
    fuerza = {n: G.out_degree(n, weight="weight") + G.in_degree(n, weight="weight") for n in G}
    # Distancia = 1 / flujo; las aristas con flujo 0 no son caminos.
    D = nx.DiGraph()
    D.add_nodes_from(G)
    D.add_edges_from((i, j, {"distancia": 1.0 / d["weight"]}) for i, j, d in G.edges(data=True) if d["weight"] > 0)
    inter = nx.betweenness_centrality(D, weight="distancia", normalized=True)
    eig = nx.eigenvector_centrality_numpy(a_no_dirigida(G), weight="weight")
    df = pd.DataFrame({"cod_muni": list(G.nodes)})
    df["grado"] = df.cod_muni.map(fuerza).round(2)
    df["intermediacion"] = df.cod_muni.map(inter).round(6)
    # El signo del vector propio es arbitrario: se reporta en valor absoluto.
    df["eigenvector"] = df.cod_muni.map(eig).abs().round(6)
    return df


def metricas_globales(G):
    """Métricas de S12 para una red dirigida G (estructura sin pesos)."""
    H = a_no_dirigida(G)
    k = np.array([d for _, d in H.degree()], dtype=float)
    conexa = nx.is_connected(H)
    gigante = H if conexa else H.subgraph(max(nx.connected_components(H), key=len))
    return {
        "red": G.graph["nombre"],
        "umbral": G.graph["umbral"],
        "n_nodos": G.number_of_nodes(),
        "n_aristas": G.number_of_edges(),
        "densidad": round(nx.density(G), 4),
        "grado_medio": round(k.mean(), 4),
        "grado2_medio": round((k**2).mean(), 4),
        "clustering_medio": round(nx.average_clustering(H), 4),
        "distancia_media": round(nx.average_shortest_path_length(gigante), 4) if len(gigante) > 1 else np.nan,
        "diametro": nx.diameter(gigante) if len(gigante) > 1 else 0,
        "conexa": conexa,
    }


def comparar_rankings(c_grav, c_censo):
    """Spearman entre los rankings de ambas redes para cada centralidad."""
    m = c_grav.merge(c_censo, on="cod_muni", suffixes=("_grav", "_censo"))
    filas = []
    for col in COLUMNAS_CENTRALIDAD[1:]:
        rho, p = spearmanr(m[f"{col}_grav"], m[f"{col}_censo"])
        filas.append({"centralidad": col, "spearman": round(rho, 4), "p_valor": round(p, 6)})
    return pd.DataFrame(filas)


def _posiciones():
    """Centroides (lon, lat) de los municipios para dibujar la red sobre el mapa."""
    import geopandas as gpd

    lim = gpd.read_file(PROCESSED / "limites_municipios.geojson")
    cent = lim.to_crs("EPSG:32615").geometry.centroid.to_crs("EPSG:4326")
    return lim, {c: (p.x, p.y) for c, p in zip(lim.cod_muni.astype(str).str.zfill(4), cent)}


def figura_red(G, cent):
    """Mapa de la red O-D: tamaño del nodo ∝ grado (fuerza); top 3 en naranja."""
    lim, pos = _posiciones()
    top3 = cent.nlargest(3, "grado").cod_muni.tolist()
    fig, ax = plt.subplots(figsize=(7.5, 8))
    lim.plot(ax=ax, color="#f3f2ef", edgecolor="#c9c8c2", linewidth=0.6)
    umbral = parametro("redes", "umbral_comparacion")
    H = a_no_dirigida(G)
    w_max = max(d["weight"] for *_, d in H.edges(data=True))
    for i, j, d in H.edges(data=True):
        if d["weight"] >= umbral:
            (x1, y1), (x2, y2) = pos[i], pos[j]
            ax.plot([x1, x2], [y1, y2], color=GRIS, alpha=0.55, linewidth=0.4 + 5 * d["weight"] / w_max, zorder=1)
    s = cent.set_index("cod_muni").grado
    for n in G.nodes:
        x, y = pos[n]
        color = NARANJA if n in top3 else AZUL
        ax.scatter(x, y, s=30 + 1400 * s[n] / s.max(), color=color, edgecolor="white", linewidth=1.5, zorder=3)
        if n in top3 or s[n] > s.quantile(0.6):
            ax.annotate(G.nodes[n]["nombre"], (x, y), xytext=(6, 6), textcoords="offset points", fontsize=8, color="#0b0b0b")
    ax.set_title(f"Red O-D gravitacional (aristas con flujo ≥ {umbral} personas/día)\n"
                 "Tamaño del nodo ∝ fuerza (personas/día); naranja = 3 municipios con mayor fuerza", fontsize=10)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(FIGURAS / "red_od.png", dpi=150)
    plt.close(fig)


def figura_distribucion(cent):
    """Distribución de la fuerza (grado ponderado) y del grado sin pesos por umbral."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
    orden = cent.sort_values("grado", ascending=False)
    ax1.bar(range(len(orden)), orden.grado / 1000, color=AZUL, width=0.75)
    ax1.set_xticks(range(len(orden)), orden.cod_muni, rotation=90, fontsize=7)
    ax1.set_ylabel("Fuerza (miles de personas/día)")
    ax1.set_title("Fuerza total por municipio (umbral 0)", fontsize=10)
    for u, color in zip(parametro("redes", "umbrales"), ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]):
        k = sorted((d for _, d in a_no_dirigida(red_gravitacional(u)).degree()), reverse=True)
        ax2.plot(range(1, len(k) + 1), k, marker="o", markersize=4, linewidth=2, color=color, label=f"umbral {u}")
    ax2.set_xlabel("Rango del municipio")
    ax2.set_ylabel("Grado k (sin pesos, red no dirigida)")
    ax2.set_title("Grado ordenado según el umbral de flujo", fontsize=10)
    ax2.legend(frameon=False, fontsize=8)
    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
        ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(FIGURAS / "distribucion_grado.png", dpi=150)
    plt.close(fig)


def main():
    SALIDA_REDES.mkdir(parents=True, exist_ok=True)
    FIGURAS.mkdir(parents=True, exist_ok=True)
    G = red_gravitacional(0)
    cent = centralidades(G)[COLUMNAS_CENTRALIDAD]
    cent.to_csv(PROCESSED / "centralidad.csv", index=False)

    filas = [metricas_globales(f(u)) for f in (red_gravitacional, red_censo) for u in parametro("redes", "umbrales")]
    pd.DataFrame(filas).to_csv(SALIDA_REDES / "metricas_red.csv", index=False)

    cent_censo = centralidades(red_censo(0))[COLUMNAS_CENTRALIDAD]
    cent_censo.to_csv(SALIDA_REDES / "centralidad_censo.csv", index=False)
    spearman = comparar_rankings(cent, cent_censo)
    spearman.to_csv(SALIDA_REDES / "spearman_gravitacional_censo.csv", index=False)

    figura_red(G, cent)
    figura_distribucion(cent)

    print("Top 5 por grado (fuerza):")
    print(cent.sort_values("grado", ascending=False).head(5).to_string(index=False))
    print("\nMétricas globales:")
    print(pd.DataFrame(filas).to_string(index=False))
    print("\nSpearman gravitacional vs censo:")
    print(spearman.to_string(index=False))


if __name__ == "__main__":
    main()
