"""A3 · Fumigación endógena: loop de balance B (Sterman, 2000).

La fumigación responde a los casos NOTIFICADOS, con dos retardos de primer orden:

    dCn/dt = (ρ · σh · Eh − Cn) / tau_notificacion           [casos/día por día]
    dF/dt  = (ganancia · Cn / Nh · 1e5 − F) / tau_respuesta   [1/día]
    μ(t)   = μ · (1 + min(F, fumigacion_max))                 [1/día]

Más casos → más notificados → más fumigación → más mortalidad de mosquitos →
menos casos: el loop es de BALANCE (B). Los retardos hacen que la respuesta
llegue tarde, cuando el pico ya pasó en parte.

tau_notificacion usa la clave existente observacion.retardo_notificacion.

Uso (desde la raíz):  python src/sd/fumigacion.py   → figuras/sd/loop_fumigacion.png
"""

import sys

import numpy as np

sys.path.insert(0, "src/datos")
from comun import parametro  # noqa: E402


def mortalidad_vector(F, p):
    """μ(t) = μ · factor_mu · (1 + min(F, fumigacion_max)) si el loop está activo."""
    mu = p["mu"] * p.get("factor_mu", 1.0)            # factor_mu: fumigación preventiva del escenario
    if not p.get("fumigacion_endogena", True):
        return mu
    return mu * (1.0 + np.minimum(F, p["fumigacion_max"]))


def derivadas_fumigacion(Eh, Cn, F, p):
    """Devuelve (dCn/dt, dF/dt) del loop B."""
    notificados = p["rho"] * p["sigma_h"] * Eh                          # casos notificados/día
    dCn = (notificados - Cn) / p["tau_notificacion"]
    objetivo = p["ganancia_fumigacion"] * Cn / p["Nh"] * 1e5            # intensidad deseada
    dF = (objetivo - F) / p["tau_respuesta"]
    return dCn, dF


def figura_loop():
    """Corre el modelo con y sin el loop B y guarda la comparación."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sys.path.insert(0, "src/sd")
    from modelo_seir_sei import IFU, casos_notificados_diarios, metricas_epidemia, parametros_departamento, simular_seir_sei

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
    for endogena, color, etiqueta in [(False, "#8a8984", "sin loop B"), (True, "#2a78d6", "con loop B (fumigación endógena)")]:
        p = parametros_departamento(fumigacion_endogena=endogena)
        res = simular_seir_sei(p)
        notif = casos_notificados_diarios(res, p)
        m = metricas_epidemia(res["t"], notif)
        ax1.plot(res["t"], notif, color=color, linewidth=2, label=f"{etiqueta}: pico {m['pico']:.0f}/día")
        F = np.minimum(res["Y"][:, IFU], p["fumigacion_max"])
        ax2.plot(res["t"], 1 + (F if endogena else 0 * F), color=color, linewidth=2, label=etiqueta)
        print(f"{etiqueta:35s} pico notificado = {m['pico']:8.1f}/día, día {m['dia_pico']:3d}, "
              f"total notificado = {np.sum(notif):9.0f}, F máx = {res['Y'][:, IFU].max():.3f}")
    ax1.set_ylabel("Casos notificados por día")
    ax2.set_ylabel("μ(t) / μ")
    ax1.set_title("Casos notificados (departamento)", fontsize=10)
    ax2.set_title("Mortalidad relativa del mosquito", fontsize=10)
    for ax in (ax1, ax2):
        ax.set_xlabel(f"Día del año {parametro('sd', 'anio_base')}")
        ax.legend(frameon=False, fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
    fig.tight_layout()
    fig.savefig("figuras/sd/loop_fumigacion.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    figura_loop()
