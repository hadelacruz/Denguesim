"""D3 · La red real contra redes aleatorias ER, BA y WS (S12).

Red real: NO dirigida, con umbral redes.umbral_comparacion (100 personas/día),
n = 17 nodos y m = número de aristas resultante. Se repite con la red del censo.

  - ER: nx.gnm_random_graph(n, m)                         (mismo n y m)
  - BA: nx.barabasi_albert_graph(n, max(1, round(m/n)))   (enlace preferencial)
  - WS: nx.watts_strogatz_graph(n, k, p), k = par más cercano a 2m/n

redes.n_repeticiones redes de cada tipo, con semillas derivadas de
semillas.yaml. Se comparan clustering C, distancia media L, ⟨k⟩, ⟨k²⟩ y la
heterogeneidad ⟨k²⟩/⟨k⟩². Mundo pequeño (Humphries y Gurney, 2008):
σ = (C/C_ER) / (L/L_ER); σ > 1 indica mundo pequeño.

Salidas: data/processed/redes/topologias.csv, data/processed/redes/conclusion_topologias.md,
         figuras/redes/comparacion_topologias.png
Uso (desde la raíz):  python src/redes/topologias.py
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/redes")
from comun import CONFIG, PROCESSED, parametro  # noqa: E402
from construir_red import a_no_dirigida, red_censo, red_gravitacional  # noqa: E402

COLORES = {"real": "#0b0b0b", "ER": "#2a78d6", "BA": "#eb6834", "WS": "#1baf7a"}


def semilla(seccion, clave):
    with open(CONFIG / "semillas.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)[seccion][clave]


def medidas(H):
    """C, L (en la componente gigante), ⟨k⟩, ⟨k²⟩ y ⟨k²⟩/⟨k⟩² de un grafo no dirigido."""
    k = np.array([d for _, d in H.degree()], dtype=float)
    gigante = H.subgraph(max(nx.connected_components(H), key=len))
    return {"clustering": nx.average_clustering(H), "distancia_media": nx.average_shortest_path_length(gigante),
            "k_medio": k.mean(), "k2_medio": (k**2).mean(), "heterogeneidad": (k**2).mean() / k.mean() ** 2,
            "conexa": nx.is_connected(H)}


def redes_aleatorias(n, m, semillas):
    """Genera ER, BA y WS con las semillas dadas (una por repetición)."""
    k_ws = max(2, int(2 * round(m / n)))                    # entero par más cercano a 2m/n
    m_ba = max(1, round(m / n))
    p_ws = parametro("redes", "ws_p")
    for s in semillas:
        yield "ER", nx.gnm_random_graph(n, m, seed=s)
        yield "BA", nx.barabasi_albert_graph(n, m_ba, seed=s)
        yield "WS", nx.watts_strogatz_graph(n, k_ws, p_ws, seed=s)


def comparar(nombre, G):
    """Tabla de medidas de la red real y de las repeticiones aleatorias."""
    H = a_no_dirigida(G)
    n, m = H.number_of_nodes(), H.number_of_edges()
    reps = parametro("redes", "n_repeticiones")
    semillas = [int(s.generate_state(1)[0]) for s in np.random.SeedSequence(semilla("redes", "topologias")).spawn(reps)]
    filas = [{"red_base": nombre, "tipo": "real", "repeticion": 0, "n": n, "m": m, **medidas(H)}]
    for i, (tipo, R) in enumerate(redes_aleatorias(n, m, semillas)):
        filas.append({"red_base": nombre, "tipo": tipo, "repeticion": i // 3, "n": n, "m": R.number_of_edges(), **medidas(R)})
    df = pd.DataFrame(filas)
    er = df[df.tipo == "ER"]
    C_er, L_er = er.clustering.mean(), er.distancia_media.mean()
    df["sigma_mundo_pequeno"] = (df.clustering / C_er) / (df.distancia_media / L_er)
    return df


def figura(tabla):
    metricas = [("clustering", "Clustering C"), ("distancia_media", "Distancia media L"),
                ("heterogeneidad", "⟨k²⟩ / ⟨k⟩²"), ("sigma_mundo_pequeno", "σ mundo pequeño")]
    fig, ejes = plt.subplots(2, 4, figsize=(13, 6), sharex=True)
    for fila, red in enumerate(["gravitacional", "censo"]):
        sub = tabla[tabla.red_base == red]
        for ax, (col, titulo) in zip(ejes[fila], metricas):
            datos = [sub[sub.tipo == t][col].to_numpy() for t in ("ER", "BA", "WS")]
            ax.boxplot(datos, tick_labels=["ER", "BA", "WS"], widths=0.5, medianprops={"color": "#0b0b0b"})
            real = sub[sub.tipo == "real"][col].iloc[0]
            ax.axhline(real, color="#eb6834", linewidth=2, label="red real")
            ax.set_title(f"{titulo} — {red}", fontsize=9)
            ax.spines[["top", "right"]].set_visible(False)
            ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
    ejes[0, 0].legend(frameon=False, fontsize=8)
    fig.suptitle(f"Red real (umbral {parametro('redes', 'umbral_comparacion')} personas/día) contra "
                 f"{parametro('redes', 'n_repeticiones')} redes ER, BA y WS con el mismo n y m", fontsize=10)
    fig.tight_layout()
    fig.savefig("figuras/redes/comparacion_topologias.png", dpi=150)
    plt.close(fig)


def tabla_markdown(df):
    """Tabla Markdown simple (sin depender de tabulate)."""
    fmt = lambda v: f"{v:.3f}" if isinstance(v, float) else str(v)  # noqa: E731
    filas = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    filas += ["| " + " | ".join(fmt(v) for v in fila) + " |" for fila in df.itertuples(index=False)]
    return "\n".join(filas)


def conclusion(resumen):
    lineas = ["# Conclusión: topología de la red de movilidad (D3)", "",
              f"Red no dirigida con umbral de {parametro('redes', 'umbral_comparacion')} personas/día. "
              f"Medias de {parametro('redes', 'n_repeticiones')} repeticiones por tipo.", "",
              tabla_markdown(resumen), ""]
    for red in ("gravitacional", "censo"):
        r = resumen[(resumen.red_base == red) & (resumen.tipo == "real")].iloc[0]
        er = resumen[(resumen.red_base == red) & (resumen.tipo == "ER")].iloc[0]
        ba = resumen[(resumen.red_base == red) & (resumen.tipo == "BA")].iloc[0]
        lineas.append(f"- **{red}:** C = {r.clustering:.2f} contra {er.clustering:.2f} en ER; "
                      f"L = {r.distancia_media:.2f} contra {er.distancia_media:.2f}; σ = {r.sigma_mundo_pequeno:.2f} "
                      f"({'> 1: rasgos de mundo pequeño' if r.sigma_mundo_pequeno > 1 else '≤ 1: sin evidencia de mundo pequeño'}). "
                      f"Heterogeneidad ⟨k²⟩/⟨k⟩² = {r.heterogeneidad:.2f} (ER {er.heterogeneidad:.2f}, BA {ba.heterogeneidad:.2f}): "
                      "pocos municipios (la capital, Mixco, Villa Nueva) concentran las conexiones.")
    lineas += ["",
               "**Limitación (obligatoria):** con solo 17 nodos **no se puede afirmar que la red sea \"libre de escala\"**: "
               "no hay suficientes nodos para estimar la cola de la distribución de grado ni para distinguir una ley de "
               "potencia de otras distribuciones. Lo que sí se puede decir es que la red es más heterogénea que una ER con "
               "el mismo número de aristas y que tiene una estructura de hub (estrella alrededor de la capital), lo que "
               "baja el umbral epidémico (D4) y favorece las intervenciones dirigidas a los hubs (D5)."]
    (PROCESSED / "redes" / "conclusion_topologias.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main():
    u = parametro("redes", "umbral_comparacion")
    tabla = pd.concat([comparar("gravitacional", red_gravitacional(u)), comparar("censo", red_censo(u))], ignore_index=True)
    tabla.round(5).to_csv(PROCESSED / "redes" / "topologias.csv", index=False)
    cols = ["clustering", "distancia_media", "k_medio", "k2_medio", "heterogeneidad", "sigma_mundo_pequeno"]
    resumen = tabla.groupby(["red_base", "tipo"], sort=False)[cols].mean().reset_index()
    figura(tabla)
    conclusion(resumen)
    print(resumen.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
