"""R3 · Pacientes presentes con estancia exponencial contra estancia Weibull (misma media).

1. Tasa de alta constante (estancia exponencial):  dX/dt = ingresos(t) − X / estancia_media
2. Estancia Weibull(k > 1): las altas son la convolución de los ingresos con la densidad
   Weibull. Equivale a X(t) = ∫ ingresos(s) · S(t − s) ds con S(u) = exp(−(u/λ)^k), cuyo
   riesgo de alta h(u) = (k/λ)(u/λ)^(k−1) crece con los días de estancia.

Ingresos: hospitalizaciones diarias del departamento (linea_base_camas, media de corridas,
ρ · nuevos · fraccion_hospitalizada). Se integra con paso fino y un horizonte con 60 días
extra para que todos los pacientes salgan; así los días-paciente totales deben coincidir
(= ingresos totales × estancia media). No se asume el resultado: se reporta lo medido.

Salidas: data/processed/salud/estancia_comparacion.csv y figuras/salud/estancia_weibull.png
Uso (desde la raíz):  python src/salud/estancia_weibull.py
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
from comun_salud import demanda_hospitalaria, matriz_asignacion, nuevos_por_escenario, parametro  # noqa: E402
from generadores import parametros_weibull  # noqa: E402

PASO = 0.05
DIAS_EXTRA = 60


def ingresos_finos(ingresos_diarios, h=PASO):
    """Ingresos por unidad de tiempo en la malla fina (constantes dentro del día) + cola en 0."""
    por_dia = int(round(1 / h))
    a = np.repeat(np.asarray(ingresos_diarios, dtype=float), por_dia)
    return np.concatenate([a, np.zeros(DIAS_EXTRA * por_dia)])


def presentes_exponencial(a, media, h=PASO):
    """dX/dt = a(t) − X/media, con la solución exacta de cada paso (a constante en el paso)."""
    X, x, decae = np.empty(len(a)), 0.0, np.exp(-h / media)
    for i, ai in enumerate(a):
        x = x * decae + ai * media * (1 - decae)
        X[i] = x
    return X


def presentes_weibull(a, k, lam, h=PASO):
    """X(t) = Σ_s a(s)·h·S(t − s) con S de la Weibull, evaluada en el punto medio del paso."""
    u = (np.arange(len(a)) + 0.5) * h
    S = np.exp(-((u / lam) ** k))
    return np.convolve(a * h, S)[:len(a)]


def comparar(ingresos_diarios, media=None, k=None, h=PASO):
    media = parametro("salud", "estancia_media") if media is None else media
    k, lam = parametros_weibull(media, k)
    a = ingresos_finos(ingresos_diarios, h)
    X_exp, X_w = presentes_exponencial(a, media, h), presentes_weibull(a, k, lam, h)
    t = np.arange(len(a)) * h
    filas = []
    for nombre, X in (("exponencial", X_exp), (f"weibull_k{k:g}", X_w)):
        filas.append({"modelo": nombre, "pico_ocupacion": round(X.max(), 3), "dia_pico": round(t[X.argmax()], 2),
                      "dias_paciente": round(X.sum() * h, 2)})
    tabla = pd.DataFrame(filas)
    tabla["dias_paciente_esperados"] = round(a.sum() * h * media, 2)
    return tabla, t, X_exp, X_w


def main():
    nuevos, cods = nuevos_por_escenario()
    A, _ = matriz_asignacion(cods)
    ingresos = demanda_hospitalaria(nuevos["linea_base_camas"], A).sum(axis=0)   # departamento
    tabla, t, X_exp, X_w = comparar(ingresos)
    e, w = tabla.iloc[0], tabla.iloc[1]
    tabla["diferencia_pico_pct"] = [0.0, round(100 * (w.pico_ocupacion / e.pico_ocupacion - 1), 3)]
    tabla["diferencia_dia_pico"] = [0.0, round(w.dia_pico - e.dia_pico, 2)]
    tabla.to_csv(PROCESSED / "salud" / "estancia_comparacion.csv", index=False)
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.plot(t, X_exp, color="#2a78d6", linewidth=2, label="estancia exponencial (alta a tasa constante)")
    ax.plot(t, X_w, color="#eb6834", linewidth=2, label=f"estancia Weibull ({w.modelo})")
    ax.set_xlabel("Día del año base")
    ax.set_ylabel("Pacientes presentes (departamento)")
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig("figuras/salud/estancia_weibull.png", dpi=150)
    plt.close(fig)
    print(tabla.to_string(index=False))


if __name__ == "__main__":
    main()
