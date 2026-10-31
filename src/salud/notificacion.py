"""R2 · Retardo de notificación de primer orden entre casos reales y notificados.

    dN/dt = (ρ · nuevos(t) − N) / τ        N = casos notificados por día   [casos/día²]

τ = observacion.retardo_notificacion (= sd.tau_notificacion) y ρ de calibracion.json.
Para τ ∈ {3, 7, 14} se mide cómo distorsiona la curva: retraso del pico (días) y
atenuación del pico (%). Entrada: nuevos del departamento (sin_intervencion, media de
corridas). Integración con el rk4_step de Alex, paso 0.1 día (nuevos constante en el día).

Salidas: data/processed/salud/notificacion.csv y figuras/salud/notificacion.png
Uso (desde la raíz):  python src/salud/notificacion.py
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/sd")
sys.path.insert(0, "src/salud")
from comun import PROCESSED  # noqa: E402
from comun_salud import nuevos_por_escenario, rho_calibrado  # noqa: E402
from integradores import rk4_step  # noqa: E402

TAUS = (3, 7, 14)
PASO = 0.1


def derivada_notificados(t, N, p):
    return (p["rho"] * p["entrada"][p["dia_del_paso"]] - N) / p["tau"]


def notificados(entrada, rho, tau, N0=0.0, h=PASO):
    """N al final de cada día para una entrada diaria (casos verdaderos por día)."""
    p = {"entrada": np.asarray(entrada, dtype=float), "rho": rho, "tau": tau}
    N, salida = float(N0), np.empty(len(entrada))
    for d in range(len(entrada)):
        p["dia_del_paso"] = d
        for s in range(int(round(1 / h))):
            N = rk4_step(derivada_notificados, d + s * h, N, h, p)
        salida[d] = N
    return salida


def main():
    nuevos, _ = nuevos_por_escenario()
    entrada = nuevos["sin_intervencion"].sum(axis=0)          # casos verdaderos / día (departamento)
    rho = rho_calibrado()
    sin_retardo = rho * entrada
    filas, curvas = [], {}
    for tau in TAUS:
        N = notificados(entrada, rho, tau)
        curvas[tau] = N
        filas.append({"tau_dias": tau, "dia_pico_sin_retardo": int(sin_retardo.argmax()), "dia_pico": int(N.argmax()),
                      "retraso_pico_dias": int(N.argmax() - sin_retardo.argmax()),
                      "pico_sin_retardo": round(sin_retardo.max(), 2), "pico": round(N.max(), 2),
                      "atenuacion_pct": round(100 * (1 - N.max() / sin_retardo.max()), 2)})
    tabla = pd.DataFrame(filas)
    tabla.to_csv(PROCESSED / "salud" / "notificacion.csv", index=False)
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.plot(sin_retardo, color="#1a1a1a", linewidth=2, label="ρ · casos verdaderos (sin retardo)")
    for tau, color in zip(TAUS, ("#2a78d6", "#eb6834", "#1baf7a")):
        ax.plot(curvas[tau], color=color, linewidth=1.8, label=f"notificados, τ = {tau} días")
    ax.set_xlabel("Día del año base")
    ax.set_ylabel("Casos por día (departamento)")
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig("figuras/salud/notificacion.png", dpi=150)
    plt.close(fig)
    print(tabla.to_string(index=False))


if __name__ == "__main__":
    main()
