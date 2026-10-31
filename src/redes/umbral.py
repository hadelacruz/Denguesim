"""D4 · Umbral epidémico de la red (Pastor-Satorras y Vespignani, 2001; S12).

    τ_c = ⟨k⟩ / (⟨k²⟩ − ⟨k⟩)

Si la transmisibilidad β/γ supera τ_c, una infección puede invadir la red.
Cuanto más heterogéneo es el grado (⟨k²⟩ grande), menor es el umbral: los hubs
facilitan la propagación.

  - Versión principal: grado sin pesos k_i de la red NO dirigida.
  - Complemento: misma fórmula con la fuerza s_i (personas/día). Sus unidades
    no son comparables con β/γ; solo sirve para ver el efecto de los pesos.

Prueba: grafo completo de 17 nodos → k = 16 → τ_c = 16 / (256 − 16) = 0.0667.

Salida: data/processed/redes/umbral_epidemico.csv
Uso (desde la raíz):  python src/redes/umbral.py
"""

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/redes")
from comun import PROCESSED, parametro  # noqa: E402
from construir_red import a_no_dirigida, red_censo, red_gravitacional  # noqa: E402


def umbral_epidemico(k):
    """τ_c = ⟨k⟩ / (⟨k²⟩ − ⟨k⟩) para una secuencia de grados k."""
    k = np.asarray(k, dtype=float)
    k_medio, k2_medio = k.mean(), (k**2).mean()
    return k_medio, k2_medio, k_medio / (k2_medio - k_medio)


def tabla_umbrales():
    """τ_c para cada umbral de flujo y ambas redes (sin pesos y con fuerza)."""
    filas = []
    for nombre, constructor in [("gravitacional", red_gravitacional), ("censo", red_censo)]:
        for u in parametro("redes", "umbrales"):
            H = a_no_dirigida(constructor(u))
            for version, k in [("sin_pesos", [d for _, d in H.degree()]),
                               ("fuerza", [d for _, d in H.degree(weight="weight")])]:
                k_medio, k2_medio, tau = umbral_epidemico(k)
                filas.append({"red": nombre, "umbral_flujo": u, "k_medio": round(k_medio, 4),
                              "k2_medio": round(k2_medio, 4), "umbral_epidemico": tau, "version": version})
    return pd.DataFrame(filas)


def comparar_con_beta_gamma(beta, gamma, red="gravitacional", umbral_flujo=0):
    """¿Supera la transmisibilidad β/γ al umbral epidémico τ_c de la red?

    Devuelve un diccionario con β/γ, τ_c (versión sin pesos) y si hay invasión.
    """
    constructor = red_gravitacional if red == "gravitacional" else red_censo
    H = a_no_dirigida(constructor(umbral_flujo))
    _, _, tau = umbral_epidemico([d for _, d in H.degree()])
    return {"beta_sobre_gamma": beta / gamma, "umbral_epidemico": tau, "supera_umbral": bool(beta / gamma > tau)}


if __name__ == "__main__":
    salida = PROCESSED / "redes"
    salida.mkdir(parents=True, exist_ok=True)
    tabla = tabla_umbrales()
    tabla.to_csv(salida / "umbral_epidemico.csv", index=False)
    print(tabla[tabla.version == "sin_pesos"].to_string(index=False))
    gamma = parametro("transmision", "gamma")
    print("\nEjemplo β = 0.3, γ =", gamma, "→", comparar_con_beta_gamma(0.3, gamma))
