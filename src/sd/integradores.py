"""A4 · Comparación de integradores: Euler y RK4 escritos a mano contra solve_ivp.

  - Euler es de orden 1: el error global baja ~ a la mitad al partir Δt a la mitad.
  - RK4 es de orden 4: el error global baja ~16 veces.

Criterio: con RK4, la altura del pico de casos diarios debe cambiar menos de 1 %
entre Δt y Δt/2; con Euler la diferencia es mayor. solve_ivp (RK45 adaptativo
con tolerancias estrictas) sirve como referencia "exacta".

Salidas: data/processed/sd/comparacion_integradores.csv, figuras/sd/integradores.png
Uso (desde la raíz):  python src/sd/integradores.py
"""

import sys
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.integrate import solve_ivp  # noqa: E402

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/sd")
from comun import PROCESSED, parametro  # noqa: E402
from modelo_seir_sei import (ICA, casos_verdaderos_diarios, condicion_inicial, derivadas, euler_step,  # noqa: E402
                             metricas_epidemia, parametros_departamento, rk4_step, simular_seir_sei)

DIAS = 364


def simular_solve_ivp(p, dias=DIAS):
    """Referencia con scipy (RK45, rtol = 1e-8). max_step = 1 día para respetar los
    saltos semanales de la lluvia."""
    y0 = condicion_inicial(p)
    sol = solve_ivp(lambda t, y: derivadas(t, y, p), (0, dias), y0, method="RK45", rtol=1e-8, atol=1e-6,
                    t_eval=np.arange(dias + 1), max_step=1.0)
    return {"t": sol.t, "Y": sol.y.T}


def pico_relativo(a, b):
    """|pico_a − pico_b| / pico_b."""
    return abs(a - b) / b


def comparar(p, pasos=(1.0, 0.5, 0.25, 0.1, 0.05)):
    """Tabla con pico, día del pico, tamaño final y tiempo de cómputo por método y Δt."""
    filas = []
    ref_t0 = time.perf_counter()
    ref = simular_solve_ivp(p)
    m_ref = metricas_epidemia(ref["t"], casos_verdaderos_diarios(ref))
    filas.append({"metodo": "solve_ivp_RK45", "dt": np.nan, **m_ref, "segundos": time.perf_counter() - ref_t0})
    series = {"solve_ivp": (ref["t"], casos_verdaderos_diarios(ref))}
    for nombre, paso in [("euler", euler_step), ("rk4", rk4_step)]:
        for h in pasos:
            t0 = time.perf_counter()
            res = simular_seir_sei(p, dias=DIAS, h=h, paso=paso)
            nuevos = casos_verdaderos_diarios(res)
            filas.append({"metodo": nombre, "dt": h, **metricas_epidemia(res["t"], nuevos),
                          "segundos": time.perf_counter() - t0})
            series[f"{nombre} Δt={h}"] = (res["t"], nuevos)
    tabla = pd.DataFrame(filas)
    tabla["error_pico_vs_solve_ivp"] = (tabla.pico - m_ref["pico"]).abs() / m_ref["pico"]
    # Δt contra Δt/2 dentro de cada método.
    tabla["cambio_pico_vs_dt_mitad"] = np.nan
    for metodo in ("euler", "rk4"):
        sub = tabla[tabla.metodo == metodo].set_index("dt").pico
        for h in sub.index:
            if h / 2 in sub.index:
                tabla.loc[(tabla.metodo == metodo) & (tabla.dt == h), "cambio_pico_vs_dt_mitad"] = pico_relativo(sub[h], sub[h / 2])
    return tabla, series


def figura(series, tabla):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
    t, y = series["solve_ivp"]
    ax1.plot(t, y, color="#0b0b0b", linewidth=2.5, label="solve_ivp (referencia)")
    ax1.plot(*series["euler Δt=1.0"], color="#eb6834", linewidth=1.5, linestyle="--", label="Euler Δt = 1 día")
    ax1.plot(*series["rk4 Δt=1.0"], color="#2a78d6", linewidth=1.5, linestyle=":", label="RK4 Δt = 1 día")
    ax1.set_xlabel("Día")
    ax1.set_ylabel("Casos verdaderos por día")
    ax1.set_title("Trayectorias", fontsize=10)
    ax1.legend(frameon=False, fontsize=8)
    for metodo, color in [("euler", "#eb6834"), ("rk4", "#2a78d6")]:
        sub = tabla[tabla.metodo == metodo]
        ax2.loglog(sub.dt, sub.error_pico_vs_solve_ivp.clip(lower=1e-12), marker="o", color=color, linewidth=2,
                   label=metodo.upper() if metodo == "rk4" else "Euler")
    ax2.set_xlabel("Δt (días)")
    ax2.set_ylabel("Error relativo del pico vs solve_ivp")
    ax2.set_title("Convergencia: pendiente ≈ 1 (Euler) y ≈ 4 (RK4)", fontsize=10)
    ax2.legend(frameon=False, fontsize=8)
    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(color="#e6e5e0", linewidth=0.6)
    fig.tight_layout()
    fig.savefig("figuras/sd/integradores.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    p = parametros_departamento()
    tabla, series = comparar(p)
    (PROCESSED / "sd").mkdir(parents=True, exist_ok=True)
    tabla.to_csv(PROCESSED / "sd" / "comparacion_integradores.csv", index=False)
    figura(series, tabla)
    print(tabla.round(5).to_string(index=False))
    h, hr = parametro("sd", "paso_rk4"), parametro("sd", "paso_rk4_rapido")
    sub = tabla[tabla.metodo == "rk4"].set_index("dt").pico
    print(f"\nRK4: pico con Δt={hr} vs Δt={h}: diferencia {pico_relativo(sub[hr], sub[h]):.2e} (debe ser < 1 %)")
