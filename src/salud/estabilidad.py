"""R7 · Estabilidad de la política de reabastecimiento → mapa_estabilidad.csv.

El criterio α·τ < π/2 vale para un retardo puro, no para el sistema de dos stocks
de R6. Se implementan los dos modelos y se comparan.

MODELO A · dos stocks (pipeline de primer orden, el de insumos.py). Con u = I − I* y
v = P − P* (D constante):
    du/dt = v/τ,   dv/dt = −α·u − v/τ    →   J = [[0, 1/τ], [−α, −1/τ]]
    ecuación característica: s² + s/τ + α/τ = 0
Como los coeficientes 1/τ y α/τ son positivos, las dos raíces tienen parte real
negativa (Routh–Hurwitz de orden 2): ESTABLE para todo α, τ > 0. Lo que cambia es la
forma: ω_n² = α/τ y 2ζω_n = 1/τ  →  ζ = 1 / (2·√(α·τ)); OSCILA si ζ < 1 ⇔ α·τ > 1/4.

MODELO B · retardo puro: dx/dt = −α·x(t − τ) (las órdenes llegan exactamente τ días
después). Es estable si y solo si α·τ < π/2 ≈ 1.571.

Salidas:
  data/processed/salud/mapa_estabilidad.csv  (alpha, tau, alpha_tau, estable_B, zeta_A, oscila_A)
  data/processed/salud/verificacion_retardo.csv
  data/processed/salud/montecarlo_estabilidad.csv y .json
  figuras/salud/mapa_estabilidad.png
Uso (desde la raíz):  python src/salud/estabilidad.py
"""

import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/salud")
from comun import PROCESSED  # noqa: E402
from comun_salud import parametro, rango, semilla  # noqa: E402

N_MALLA = 60


# ------------------------------------------------------------------ modelo A
def jacobiano_A(alpha, tau):
    """Matriz del sistema linealizado de dos stocks."""
    return np.array([[0.0, 1.0 / tau], [-alpha, -1.0 / tau]])


def raices_A(alpha, tau):
    """Raíces de s² + s/τ + α/τ = 0."""
    return np.roots([1.0, 1.0 / tau, alpha / tau])


def zeta_A(alpha, tau):
    """Razón de amortiguamiento ζ = 1 / (2·√(α·τ))."""
    return 1.0 / (2.0 * np.sqrt(np.asarray(alpha) * np.asarray(tau)))


def verificar_modelo_A(alphas, taus):
    """Comprueba que los valores propios de J coinciden con las raíces de la ecuación
    característica y cuenta las combinaciones inestables (parte real ≥ 0)."""
    inestables, error_max = 0, 0.0
    for a in alphas:
        for t in taus:
            propios = np.sort_complex(np.linalg.eigvals(jacobiano_A(a, t)))
            raices = np.sort_complex(raices_A(a, t))
            error_max = max(error_max, float(np.max(np.abs(propios - raices))))
            inestables += int(np.any(propios.real >= 0))
    return inestables, error_max


# ------------------------------------------------------------------ modelo B
def simular_retardo(alpha, tau, horizonte_tau=150, pasos_por_tau=200):
    """Euler con paso pequeño y un buffer circular para x(t − τ). Historia x(t ≤ 0) = 1."""
    h = tau / pasos_por_tau
    n = int(horizonte_tau * pasos_por_tau)
    x = np.empty(n + pasos_por_tau + 1)
    x[:pasos_por_tau + 1] = 1.0                            # historia constante en [−τ, 0]
    for k in range(pasos_por_tau, n + pasos_por_tau):
        x[k + 1] = x[k] - h * alpha * x[k - pasos_por_tau]  # dx/dt = −α·x(t − τ)
    return x[pasos_por_tau:]


def es_estable_simulado(alpha, tau):
    """Compara la amplitud del último tramo contra la del primero (envolvente)."""
    x = simular_retardo(alpha, tau)
    cuarto = len(x) // 4
    return float(np.abs(x[-cuarto:]).max()) < float(np.abs(x[:cuarto]).max())


def verificar_frontera_B(tau=None, factores=(0.8, 0.9, 0.95, 1.05, 1.1)):
    """Cinco puntos alrededor de α·τ = π/2: simulado contra el criterio teórico."""
    tau = parametro("insumos", "tau") if tau is None else tau
    filas = []
    for f in factores:
        alpha = f * (np.pi / 2) / tau
        filas.append({"alpha": alpha, "tau": tau, "alpha_tau": alpha * tau,
                      "estable_simulado": es_estable_simulado(alpha, tau),
                      "estable_teorico": alpha * tau < np.pi / 2})
    return pd.DataFrame(filas)


# ------------------------------------------------------------------ mapa y Monte Carlo
def mapa_estabilidad(n=N_MALLA):
    a_min, a_max = rango("insumos", "alpha")
    t_min, t_max = rango("insumos", "tau")
    A, T = np.meshgrid(np.linspace(a_min, a_max, n), np.linspace(t_min, t_max, n), indexing="ij")
    at = A * T
    return pd.DataFrame({"alpha": A.ravel().round(5), "tau": T.ravel().round(4), "alpha_tau": at.ravel().round(5),
                         "estable_B": (at < np.pi / 2).ravel(), "zeta_A": zeta_A(A, T).ravel().round(5),
                         "oscila_A": (at > 0.25).ravel()})


def montecarlo(n, rng, factor_alpha=1.0, factor_tau=1.0):
    """τ ~ U(τ_min, τ_max) y α ~ Normal(centro, ancho/4) truncada a α > 0 (rangos del YAML).
    factor_* permite desplazar la política (R8)."""
    a_min, a_max = rango("insumos", "alpha")
    t_min, t_max = rango("insumos", "tau")
    centro, sd = parametro("insumos", "alpha"), (a_max - a_min) / 4
    alpha = np.empty(0)
    while len(alpha) < n:                                  # truncamiento por rechazo
        prop = rng.normal(centro, sd, n)
        alpha = np.concatenate([alpha, prop[prop > 0]])
    alpha, tau = alpha[:n] * factor_alpha, rng.uniform(t_min, t_max, n) * factor_tau
    at = alpha * tau
    return pd.DataFrame({"alpha": alpha, "tau": tau, "alpha_tau": at, "estable_B": at < np.pi / 2, "oscila_A": at > 0.25})


def figura(mapa, mc):
    fig, ejes = plt.subplots(1, 2, figsize=(11, 4.2))
    ax = ejes[0]
    A = mapa.alpha.to_numpy().reshape(N_MALLA, N_MALLA)
    T = mapa.tau.to_numpy().reshape(N_MALLA, N_MALLA)
    at = A * T
    ax.contourf(T, A, at < np.pi / 2, levels=[-0.5, 0.5, 1.5], colors=["#f3d4c4", "#d4e6f6"])
    c1 = ax.contour(T, A, at, levels=[np.pi / 2], colors="#b3261e", linewidths=2)
    c2 = ax.contour(T, A, at, levels=[0.25], colors="#1a1a1a", linewidths=1.5, linestyles="--")
    ax.clabel(c1, fmt={np.pi / 2: "α·τ = π/2 (retardo puro)"}, fontsize=8)
    ax.clabel(c2, fmt={0.25: "α·τ = 1/4 (dos stocks: oscila arriba)"}, fontsize=8)
    ax.plot(parametro("insumos", "tau"), parametro("insumos", "alpha"), "o", color="#1a1a1a")
    ax.set_xlabel("τ, tiempo de entrega (días)")
    ax.set_ylabel("α, fracción de la brecha pedida por día")
    ax.set_title("Azul: estable con retardo puro. Dos stocks: siempre estable", fontsize=9)
    ax = ejes[1]
    ax.hist(mc.alpha_tau, bins=60, color="#2a78d6", alpha=0.6)
    ax.axvline(np.pi / 2, color="#b3261e", linewidth=2, label="π/2")
    ax.axvline(0.25, color="#1a1a1a", linewidth=1.5, linestyle="--", label="1/4")
    ax.set_xlabel("α·τ (Monte Carlo)")
    ax.set_ylabel("Muestras")
    ax.set_title(f"P(estable_B) = {mc.estable_B.mean():.3f} · P(oscila_A) = {mc.oscila_A.mean():.3f}", fontsize=9)
    ax.legend(frameon=False)
    for a in ejes:
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig("figuras/salud/mapa_estabilidad.png", dpi=150)
    plt.close(fig)


def main():
    mapa = mapa_estabilidad()
    inestables, error = verificar_modelo_A(np.unique(mapa.alpha), np.unique(mapa.tau))
    frontera = verificar_frontera_B()
    mc = montecarlo(parametro("salud", "mc_n"), np.random.default_rng(semilla("estabilidad")))
    mapa.to_csv(PROCESSED / "salud" / "mapa_estabilidad.csv", index=False)
    frontera.to_csv(PROCESSED / "salud" / "verificacion_retardo.csv", index=False)
    mc.round(5).to_csv(PROCESSED / "salud" / "montecarlo_estabilidad.csv", index=False)
    resumen = {
        "n": int(len(mc)), "P_estable_B": round(float(mc.estable_B.mean()), 4), "P_oscila_A": round(float(mc.oscila_A.mean()), 4),
        "alpha_tau_media": round(float(mc.alpha_tau.mean()), 4),
        "alpha_tau_p2_5": round(float(np.percentile(mc.alpha_tau, 2.5)), 4),
        "alpha_tau_p97_5": round(float(np.percentile(mc.alpha_tau, 97.5)), 4),
        "modelo_A_inestables": inestables, "modelo_A_combinaciones": int(len(mapa)),
        "modelo_A_error_raices": error,
        "modelo_B_frontera_verificada": bool((frontera.estable_simulado == frontera.estable_teorico).all()),
        "nota": "π/2 es el criterio del retardo puro (modelo B). El modelo de dos stocks de insumos.py (modelo A) "
                "siempre converge; oscila si α·τ > 1/4. α ~ Normal(insumos.alpha, ancho/4) truncada a α > 0, τ ~ U(rango).",
    }
    (PROCESSED / "salud" / "montecarlo_estabilidad.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False),
                                                                     encoding="utf-8")
    figura(mapa, mc)
    print(f"Modelo A: {inestables} inestables de {len(mapa)} (error raíces vs valores propios = {error:.1e})")
    print("Modelo B (frontera π/2):\n" + frontera.round(4).to_string(index=False))
    print(f"Monte Carlo n = {len(mc)}: P(estable_B) = {resumen['P_estable_B']}, P(oscila_A) = {resumen['P_oscila_A']}")


if __name__ == "__main__":
    main()
