"""A9 (N3) · Población abierta: nacimientos y muertes humanas → endemicidad (S6).

Al modelo de una población (A1–A3) se le agregan nacimientos y muertes con la
misma tasa μh = 1 / (esperanza de vida · 365), así Nh se mantiene constante:

    dSh/dt += μh·Nh − μh·Sh       nacen susceptibles          [personas/día]
    dEh/dt −= μh·Eh               mueren por otras causas     [personas/día]
    dIh/dt −= μh·Ih
    dRh/dt −= μh·Rh

Sumado: d(Sh+Eh+Ih+Rh)/dt = μh·(Nh − total) = 0, la población se conserva.

Población cerrada (μh = 0) y abierta (μh > 0) se simulan a la vez como un lote
de 2 (el modelo acepta arreglos de parámetros), con los mismos parámetros de A6.

Dos experimentos:
  1. Lluvia real 2017–2025 seguida (9 temporadas, cada año = 52 semanas), sin
     reiniciar el estado: la inmunidad de un año pasa al siguiente. Los casos
     notificados anuales se comparan con el total departamental observado.
  2. sd.anios_endemicidad años con el ciclo MEDIO de lluvia 2017–2025: en la
     población cerrada los susceptibles se agotan poco a poco y las
     temporadas se apagan; en la abierta los nacimientos los reponen y el
     sistema llega a un régimen endémico periódico (una epidemia por año).

Criterio de endemicidad: en el último tercio de la simulación los casos anuales
cambian menos de 5 % entre años y Ih no baja de 1 persona (no hay extinción
práctica entre temporadas).

Salidas: data/processed/sd/poblacion_abierta.csv, data/processed/sd/poblacion_abierta_resumen.json,
figuras/sd/poblacion_abierta.png
Uso (desde la raíz):  python src/sd/poblacion_abierta.py
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
from comun import PROCESSED, leer_procesado, parametro  # noqa: E402
from modelo_seir_sei import (ICA, IEH, IIH, IRH, ISH, condicion_inicial, derivadas, integrar,  # noqa: E402
                             parametros_departamento, verificar_conservacion)
from vector_lluvia import escala_k, lluvia_departamento, poblacion_anio  # noqa: E402

SALIDA = PROCESSED / "sd"
FIGURA = "figuras/sd/poblacion_abierta.png"
ANIOS_REALES = list(range(2017, 2026))
ANIO_POBLACION = 2021                 # Nh constante: año central de 2017–2025
SEMANAS = 52
DIAS_ANIO = 7 * SEMANAS
TOLERANCIA_ENDEMICA = 0.05
POBLACIONES = ["cerrada", "abierta"]


def tasa_demografica():
    """μh = 1 / (esperanza de vida · 365)   [1/día]."""
    return 1.0 / (parametro("sd", "esperanza_vida_humana") * 365.0)


def derivadas_abierta(t, y, p):
    """Modelo SEIR–SEI (A1–A3) + nacimientos y muertes humanas con tasa p['mu_h']."""
    dy = derivadas(t, y, p)
    mu_h = p["mu_h"]
    dy[..., ISH] += mu_h * p["Nh"] - mu_h * y[..., ISH]   # nacimientos − muertes   personas/día
    dy[..., IEH] -= mu_h * y[..., IEH]                     # muertes                  personas/día
    dy[..., IIH] -= mu_h * y[..., IIH]
    dy[..., IRH] -= mu_h * y[..., IRH]
    return dy


def parametros_lote(lluvia):
    """Parámetros calibrados (A6) con la lluvia dada; lote de 2: cerrada (μh = 0) y abierta."""
    p = parametros_departamento(parametro("sd", "anio_base"))
    p["Nh"] = float(poblacion_anio(ANIO_POBLACION).sum())
    p["lluvia"] = lluvia
    p["k"] = escala_k(p)
    p["mu_h"] = np.array([0.0, tasa_demografica()])
    p["expuestos_iniciales"] = np.full(2, p["expuestos_iniciales"])
    return p


def simular(lluvia, h=None):
    """Integra con RK4 a mano todos los años de `lluvia` sin reiniciar el estado."""
    p = parametros_lote(lluvia)
    h = parametro("sd", "paso_rk4_rapido") if h is None else h
    dias = len(lluvia) // SEMANAS * DIAS_ANIO
    t, Y = integrar(derivadas_abierta, condicion_inicial(p), p, dias, h)
    return t, Y, p


def resumen_anual(Y, p, etiquetas):
    """Por año y población: casos verdaderos y notificados, fracción susceptible al final y mínimo de Ih."""
    filas = []
    for k, anio in enumerate(etiquetas):
        a, b = k * DIAS_ANIO, (k + 1) * DIAS_ANIO
        for j, pob in enumerate(POBLACIONES):
            verdaderos = Y[b, j, ICA] - Y[a, j, ICA]
            filas.append({"anio": anio, "poblacion": pob, "casos_verdaderos": round(float(verdaderos), 1),
                          "casos_notificados": round(float(p["rho"] * verdaderos), 1),
                          "fraccion_susceptible_fin": round(float(Y[b, j, ISH] / p["Nh"]), 5),
                          "ih_minimo": round(float(Y[a:b + 1, j, IIH].min()), 3)})
    return pd.DataFrame(filas)


def es_endemica(tabla, pob):
    """Último tercio: casos anuales con cambio < 5 % entre años e Ih mínimo ≥ 1."""
    sub = tabla[tabla.poblacion == pob]
    cola = sub.iloc[-max(3, len(sub) // 3):]
    cambio = cola.casos_verdaderos.pct_change().abs().max()
    return {"cambio_max_entre_anios": round(float(cambio), 4), "ih_minimo": float(cola.ih_minimo.min()),
            "endemica": bool(cambio < TOLERANCIA_ENDEMICA and cola.ih_minimo.min() >= 1.0)}


def observados_departamento():
    c = leer_procesado("casos_anuales_muni.csv")
    return c[c.anio.isin(ANIOS_REALES)].groupby("anio").casos.sum()


def experimento_real():
    lluvia = np.concatenate([lluvia_departamento(a)[:SEMANAS] for a in ANIOS_REALES])
    t, Y, p = simular(lluvia)
    tabla = resumen_anual(Y, p, ANIOS_REALES)
    tabla.insert(0, "experimento", "lluvia_real_2017_2025")
    tabla["casos_observados"] = tabla.anio.map(observados_departamento())
    return tabla, t, Y, p


def experimento_endemicidad():
    n = int(parametro("sd", "anios_endemicidad"))
    ciclo = np.mean([lluvia_departamento(a)[:SEMANAS] for a in ANIOS_REALES], axis=0)
    t, Y, p = simular(np.tile(ciclo, n))
    tabla = resumen_anual(Y, p, list(range(1, n + 1)))
    tabla.insert(0, "experimento", "ciclo_medio")
    tabla["casos_observados"] = np.nan
    return tabla, t, Y, p


def figura(real, end, t_end, Y_end, p_end):
    fig, ejes = plt.subplots(1, 3, figsize=(15, 4.3))
    colores = {"cerrada": "#eb6834", "abierta": "#2a78d6"}
    ax = ejes[0]
    obs = real[real.poblacion == "abierta"]
    ax.bar(obs.anio, obs.casos_observados, color="#c9c8c2", label="observado (departamento)")
    for pob in POBLACIONES:
        s = real[real.poblacion == pob]
        ax.plot(s.anio, s.casos_notificados, marker="o", color=colores[pob], label=f"simulado, población {pob}")
    ax.set_title("Lluvia real 2017–2025 sin reiniciar el estado", fontsize=10)
    ax.set_ylabel("Casos notificados por año")
    ax.legend(frameon=False, fontsize=8)
    ax = ejes[1]
    for pob in POBLACIONES:
        s = end[end.poblacion == pob]
        ax.plot(s.anio, s.casos_notificados, color=colores[pob], linewidth=2, label=f"población {pob}")
    ax.set_title("Ciclo medio de lluvia: casos por temporada", fontsize=10)
    ax.set_xlabel("Año simulado")
    ax.set_ylabel("Casos notificados por año")
    ax.legend(frameon=False, fontsize=8)
    ax = ejes[2]
    for j, pob in enumerate(POBLACIONES):
        ax.plot(t_end / 365.0, Y_end[:, j, ISH] / p_end["Nh"], color=colores[pob], label=f"población {pob}")
    ax.set_title("Fracción susceptible", fontsize=10)
    ax.set_xlabel("Años")
    ax.legend(frameon=False, fontsize=8)
    for ax in ejes:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
        ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(FIGURA, dpi=150)
    plt.close(fig)


def main():
    real, _, Y_real, p_real = experimento_real()
    end, t_end, Y_end, p_end = experimento_endemicidad()
    tabla = pd.concat([real, end], ignore_index=True)
    tabla.to_csv(SALIDA / "poblacion_abierta.csv", index=False)
    figura(real, end, t_end, Y_end, p_end)
    abierta = real[real.poblacion == "abierta"]
    resumen = {
        "mu_h_por_dia": tasa_demografica(),
        "esperanza_vida_anios": parametro("sd", "esperanza_vida_humana"),
        "Nh": p_real["Nh"],
        "error_conservacion": max(verificar_conservacion(Y_real, p_real["Nh"]), verificar_conservacion(Y_end, p_end["Nh"])),
        "lluvia_real": {
            "correlacion_simulado_observado": round(float(np.corrcoef(abierta.casos_notificados, abierta.casos_observados)[0, 1]), 3),
            "total_simulado": round(float(abierta.casos_notificados.sum()), 0),
            "total_observado": float(abierta.casos_observados.sum()),
        },
        "ciclo_medio": {pob: es_endemica(end, pob) for pob in POBLACIONES},
        "nota": ("Parámetros de la calibración 2023 (A6) para todos los años; Nh constante (población "
                 f"{ANIO_POBLACION}). Cada año = 52 semanas."),
    }
    (SALIDA / "poblacion_abierta_resumen.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    print(real.pivot(index="anio", columns="poblacion", values="casos_notificados").join(
        real.groupby("anio").casos_observados.first()).round(0).to_string())
    print(json.dumps(resumen, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
