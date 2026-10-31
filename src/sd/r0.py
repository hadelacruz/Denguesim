"""A5 · Número reproductivo básico por matriz de siguiente generación
(van den Driessche y Watmough, 2002).

    R0 = sqrt( a² · (βs·b) · c · m · σv / (γ · μ · (σv + μ)) ),   m = Nv / Nh

La raíz cuadrada aparece porque la matriz de siguiente generación tiene dos
pasos: humano → mosquito → humano. R0 es la media geométrica de los dos pasos;
R0² es el número de casos HUMANOS que produce un caso humano (dos generaciones).

  - Humano → mosquito: a·c·m / γ  (picaduras por día × prob. × duración infecciosa)
  - Mosquito → humano: a·βs·b · σv/(σv+μ) / μ  (sobrevive la incubación y pica mientras vive)

β equivalente de un SEIR solo humano (para comparar con beta_efectiva.json del ABM):
    β_eq = R0² · γ     [1/día]

Salidas: data/processed/sd/r0.csv, data/processed/sd/beta_equivalente.json,
         figuras/sd/r0_m_mu.png
Uso (desde la raíz):  python src/sd/r0.py
"""

import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/sd")
from comun import PROCESSED, parametros  # noqa: E402
from modelo_seir_sei import leer_calibracion, parametros_base  # noqa: E402


def r0(p, m=None, mu=None):
    """R0 por matriz de siguiente generación (acepta arreglos en m y μ)."""
    m = p["m_base"] if m is None else m
    mu = p["mu"] if mu is None else mu
    num = p["a"] ** 2 * p["beta_s"] * p["b"] * p["c"] * m * p["sigma_v"]
    return np.sqrt(num / (p["gamma"] * mu * (p["sigma_v"] + mu)))


def beta_equivalente(p):
    """β de un SEIR humano equivalente: β_eq = R0² · γ (1/día)."""
    return r0(p) ** 2 * p["gamma"]


def mapa_r0(p):
    """R0 en una grilla de m (mosquitos por humano) y μ (mortalidad del mosquito),
    dentro de los rangos de config/parametros.yaml."""
    m_min, m_max = parametros()["transmision"]["m"]["rango"]
    mu_min, mu_max = parametros()["transmision"]["mu"]["rango"]
    ms = np.linspace(m_min, m_max, 46)
    mus = np.linspace(mu_min, mu_max, 41)
    M, MU = np.meshgrid(ms, mus)
    return ms, mus, r0(p, M, MU)


def figura(ms, mus, R, p):
    fig, ax = plt.subplots(figsize=(7, 5))
    malla = ax.pcolormesh(ms, mus, R, cmap="Blues", shading="auto")
    cs = ax.contour(ms, mus, R, levels=[1, 2, 3, 4], colors="#0b0b0b", linewidths=[2.5, 0.8, 0.8, 0.8])
    ax.clabel(cs, fmt=lambda v: f"R0 = {v:.0f}", fontsize=8)
    ax.scatter([p["m_base"]], [p["mu"]], color="#eb6834", s=60, edgecolor="white", zorder=3, label="valores nominales")
    fig.colorbar(malla, ax=ax, label="R0")
    ax.set_xlabel("m = Nv / Nh (mosquitos por humano)")
    ax.set_ylabel("μ (mortalidad diaria del mosquito)")
    ax.set_title(f"R0 al mover m y μ (βs = {p['beta_s']:.2f}); la línea gruesa es R0 = 1", fontsize=10)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig("figuras/sd/r0_m_mu.png", dpi=150)
    plt.close(fig)


def main():
    p = parametros_base()
    cal = leer_calibracion()
    if cal is not None:
        p["beta_s"] = cal["beta_s"]
    ms, mus, R = mapa_r0(p)
    salida = PROCESSED / "sd"
    salida.mkdir(parents=True, exist_ok=True)
    M, MU = np.meshgrid(ms, mus)
    pd.DataFrame({"m": M.ravel().round(4), "mu": MU.ravel().round(5), "R0": R.ravel().round(4)}).to_csv(salida / "r0.csv", index=False)
    figura(ms, mus, R, p)
    R0 = float(r0(p))
    info = {
        "R0": round(R0, 4),
        "R0_cuadrado_humano_a_humano": round(R0**2, 4),
        "gamma": p["gamma"],
        "beta_eq": round(float(beta_equivalente(p)), 4),
        "beta_s": p["beta_s"],
        "m": p["m_base"],
        "mu": p["mu"],
        "fuente_beta_s": "calibracion.json (A6)" if cal is not None else "nominal (βs = 1, sin calibrar)",
        "nota": "β_eq = R0²·γ, en 1/día. R0 en temporada lluviosa (m = m_base); fuera de ella m es menor.",
    }
    (salida / "beta_equivalente.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(info, indent=2, ensure_ascii=False))
    nominal = dict(p, beta_s=1.0)
    print(f"R0 nominal (βs = 1) = {float(r0(nominal)):.3f}")


if __name__ == "__main__":
    main()
