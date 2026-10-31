"""D5 · Intervenciones según la topología: fumigación aleatoria contra dirigida a hubs (S12).

SEIR metapoblacional SOLO humano, paso de 1 día, en los 17 municipios:

    λ_i = β_i · ( I_i + Σ_j (F_ji / N_j) · I_j ) / N_i
          (infecciosos locales + infecciosos que llegan de j a i cada día)
    nuevas infecciones_i = S_i · (1 − exp(−λ_i))
    E → I con prob. 1 − exp(−σh);  I → R con prob. 1 − exp(−γ)

β = beta_efectiva.json (ABM, D13); σh y γ del YAML; F = flujos_od.csv.
Fumigar el municipio i: β_i · (1 − redes.efecto_fumigacion).

Estrategias para k = 1 … redes.k_max municipios fumigados:
  - aleatoria: redes.sorteos_aleatorios sorteos de k municipios
  - dirigida: top-k por grado (fuerza), por intermediación y por eigenvector
Inicio: 10 expuestos en un municipio; se repite con cada uno de los 17 como
inicio y se promedia. 365 días. Todo se simula en lote (arreglos (lote, 17)).

Salidas: data/processed/redes/intervenciones.csv, figuras/redes/intervenciones.png
Uso (desde la raíz):  python src/redes/intervenciones.py
"""

import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

sys.path.insert(0, "src/datos")
from comun import CONFIG, PROCESSED, leer_procesado, parametro  # noqa: E402

EXPUESTOS_INICIALES = 10   # lo fija la guía (D5)
COLORES = {"aleatoria": "#8a8984", "grado": "#2a78d6", "intermediacion": "#eb6834", "eigenvector": "#1baf7a"}


def semilla(seccion, clave):
    with open(CONFIG / "semillas.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)[seccion][clave]


def cargar_datos():
    """N, F (matriz 17×17), β, σh, γ y centralidades en el orden de poblacion.csv."""
    pob = leer_procesado("poblacion.csv")
    cods = pob.cod_muni.tolist()
    F = (leer_procesado("flujos_od.csv").pivot(index="cod_i", columns="cod_j", values="flujo_diario")
         .reindex(index=cods, columns=cods).fillna(0.0).to_numpy(float).copy())
    np.fill_diagonal(F, 0.0)
    beta = json.loads((PROCESSED / "beta_efectiva.json").read_text(encoding="utf-8"))["beta"]
    cent = leer_procesado("centralidad.csv").set_index("cod_muni").loc[cods]
    return {"cods": cods, "N": pob.poblacion.to_numpy(float), "F": F, "beta": beta,
            "sigma_h": parametro("transmision", "sigma_h"), "gamma": parametro("transmision", "gamma"),
            "centralidad": cent}


def simular_lote(datos, fumigados, inicios, dias=365):
    """Simula un lote: fumigados (B, 17) booleano, inicios (B,) índice del municipio inicial.

    Devuelve el estado (dias+1, B, 17, 4) con S, E, I, R y las infecciones diarias (dias, B, 17)."""
    B, n = fumigados.shape
    beta = datos["beta"] * np.where(fumigados, 1 - parametro("redes", "efecto_fumigacion"), 1.0)
    p_inc, p_rec = 1 - np.exp(-datos["sigma_h"]), 1 - np.exp(-datos["gamma"])
    N, F = datos["N"], datos["F"]
    X = np.zeros((dias + 1, B, n, 4))
    X[0, ..., 0] = N
    X[0, np.arange(B), inicios, 0] -= EXPUESTOS_INICIALES
    X[0, np.arange(B), inicios, 1] += EXPUESTOS_INICIALES
    nuevas = np.zeros((dias, B, n))
    for t in range(dias):
        S, E, I, R = (X[t, ..., k] for k in range(4))
        visitantes = (I / N) @ F                                  # Σ_j (F_ji/N_j)·I_j
        lam = beta * (I + visitantes) / N
        inf, inc, rec = S * (1 - np.exp(-lam)), E * p_inc, I * p_rec
        X[t + 1] = np.stack([S - inf, E + inf - inc, I + inc - rec, R + rec], axis=-1)
        nuevas[t] = inf
    return X, nuevas


def simular_metapoblacion(datos, nodos_fumigados, inicio=0, dias=365, devolver_estado=False):
    """Una simulación: nodos_fumigados (17,) booleano e inicio = índice del municipio inicial."""
    X, nuevas = simular_lote(datos, np.atleast_2d(nodos_fumigados), np.array([inicio]), dias)
    salida = {"nuevas": nuevas[:, 0]}
    if devolver_estado:
        salida["estado"] = X[:, 0]
    return salida


def metricas(nuevas):
    """Tamaño final, pico y día del pico del total departamental, para cada elemento del lote."""
    total = nuevas.sum(axis=-1)                                   # (dias, B)
    return total.sum(axis=0), total.max(axis=0), total.argmax(axis=0) + 1


def fumigados_por_estrategia(datos, estrategia, k, sorteos, rng):
    """Matriz (n_conjuntos, 17) de municipios fumigados."""
    n = len(datos["cods"])
    if estrategia == "aleatoria":
        conjuntos = np.zeros((sorteos, n), dtype=bool)
        for s in range(sorteos):
            conjuntos[s, rng.choice(n, size=k, replace=False)] = True
        return conjuntos
    orden = np.argsort(-datos["centralidad"][estrategia].to_numpy(), kind="stable")
    conjunto = np.zeros((1, n), dtype=bool)
    conjunto[0, orden[:k]] = True
    return conjunto


def evaluar_estrategias(datos, ks=None, sorteos=None, inicios=None, dias=365):
    """Promedia tamaño final, pico y día del pico sobre sorteos e inicios."""
    ks = range(0, parametro("redes", "k_max") + 1) if ks is None else ks
    sorteos = parametro("redes", "sorteos_aleatorios") if sorteos is None else sorteos
    inicios = np.arange(len(datos["cods"])) if inicios is None else np.asarray(inicios)
    rng = np.random.default_rng(semilla("redes", "intervenciones"))
    filas = []
    for k in ks:
        for estrategia in ("aleatoria", "grado", "intermediacion", "eigenvector"):
            conjuntos = fumigados_por_estrategia(datos, estrategia, k, sorteos, rng)
            fumigados = np.repeat(conjuntos, len(inicios), axis=0)
            lote_inicios = np.tile(inicios, len(conjuntos))
            _, nuevas = simular_lote(datos, fumigados, lote_inicios, dias)
            tam, pico, dia = metricas(nuevas)
            filas.append({"estrategia": estrategia, "k": k, "tamano_final": round(float(tam.mean()), 2),
                          "pico": round(float(pico.mean()), 2), "dia_pico": round(float(dia.mean()), 2)})
    return pd.DataFrame(filas)


def figura(tabla):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
    for estrategia, sub in tabla.groupby("estrategia"):
        etiqueta = "aleatoria (media de sorteos)" if estrategia == "aleatoria" else f"dirigida por {estrategia}"
        estilo = dict(color=COLORES[estrategia], marker="o", markersize=5, linewidth=2, label=etiqueta)
        ax1.plot(sub.k, sub.tamano_final / 1e3, **estilo)
        ax2.plot(sub.k, sub.pico / 1e3, **estilo)
    ax1.set_ylabel("Tamaño final (miles de infecciones)")
    ax2.set_ylabel("Pico (miles de infecciones/día)")
    for ax in (ax1, ax2):
        ax.set_xlabel("k = municipios fumigados")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
    ax1.legend(frameon=False, fontsize=8)
    fig.suptitle("Fumigación aleatoria contra dirigida a hubs (SEIR metapoblacional, β del ABM; media de 17 inicios)", fontsize=10)
    fig.tight_layout()
    fig.savefig("figuras/redes/intervenciones.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    datos = cargar_datos()
    tabla = evaluar_estrategias(datos)
    tabla.to_csv(PROCESSED / "redes" / "intervenciones.csv", index=False)
    figura(tabla)
    print(f"β = {datos['beta']}, γ = {datos['gamma']}, β/γ = {datos['beta'] / datos['gamma']:.3f}")
    print(tabla.pivot(index="k", columns="estrategia", values="tamano_final").round(0).to_string())
