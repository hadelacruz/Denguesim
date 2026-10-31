"""A6 (N2) · Calibración del modelo de una población para cada año 2017–2025.

Repite el ajuste FINAL de calibracion.py (ρ fijo en observacion.factor_reporte;
se calibran βs, I0, ganancia del loop B y lluvia mínima) con la lluvia, la
población y el objetivo semanal de cada año. Sirve para ver si los parámetros
son estables entre años o si absorben diferencias que el modelo no explica
(por ejemplo, la inmunidad que deja la epidemia grande de 2019 o el
subregistro de 2020 por la pandemia).

El rango de años lo fija el clima: clima_semanal.csv empieza en 2017, y 2026
está incompleto (solo hasta la semana 40), así que no se calibra.

Mismo objetivo que A6: casos_semanales.csv sumado por semana = forma nacional
escalada al total departamental observado (ESTIMADO, no observación semanal).
Cada año se simula desde la semana 1 con todos susceptibles (sin la inmunidad
de años anteriores: limitación; ver poblacion_abierta.py).

Los años se calibran en paralelo (ProcessPoolExecutor), uno por proceso.

Salidas: data/processed/sd/calibracion_anual.csv, figuras/sd/calibracion_anual.png
Uso (desde la raíz):  python src/sd/calibracion_anual.py
"""

import os
import sys
from concurrent.futures import ProcessPoolExecutor

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/sd")
from calibracion import FINAL, PARAMETROS, calibrar  # noqa: E402
from comun import PROCESSED, parametro  # noqa: E402

SALIDA = PROCESSED / "sd" / "calibracion_anual.csv"
FIGURA = "figuras/sd/calibracion_anual.png"
ANIOS = list(range(2017, 2026))
TOLERANCIA_LIMITE = 0.01      # un parámetro "toca el límite" si queda a menos de 1 % (en log) del borde


def en_limite(nombre, valor):
    """True si el valor calibrado quedó pegado a uno de sus límites."""
    lo, hi = np.log(PARAMETROS[nombre][0])
    v = np.log(valor)
    return bool(v - lo < TOLERANCIA_LIMITE * (hi - lo) or hi - v < TOLERANCIA_LIMITE * (hi - lo))


def calibrar_anio(anio):
    """Ajuste final (ρ fijo) de un año. Devuelve (fila de la tabla, observado, simulado)."""
    rho = parametro("observacion", "factor_reporte")
    cal, obs, sim = calibrar(FINAL, anio, fijos={"rho": rho})
    fila = {"anio": anio, "rho_fijo": rho}
    for nombre, ee in zip(FINAL, cal["error_estandar_log"]):
        fila[nombre] = cal["valores"][nombre]
        fila[f"ee_log_{nombre}"] = ee
    fila["en_limite"] = ";".join(n for n in FINAL if en_limite(n, cal["valores"][n])) or "ninguno"
    for clave in ("rmse_log1p", "rmse_casos", "total_observado", "total_simulado", "pico_observado",
                  "pico_simulado", "semana_pico_observado", "semana_pico_simulado", "tasa_ataque"):
        fila[clave] = cal[clave]
    fila["error_total_relativo"] = round(cal["total_simulado"] / cal["total_observado"] - 1, 4)
    return fila, obs, sim


def figura(resultados):
    """Observado contra simulado por año (3 × 3)."""
    fig, ejes = plt.subplots(3, 3, figsize=(13, 9), sharex=True)
    for ax, (fila, obs, sim) in zip(ejes.ravel(), resultados):
        semanas = np.arange(1, len(obs) + 1)
        ax.bar(semanas, obs, color="#c9c8c2", width=0.8, label="objetivo (estimado)")
        ax.plot(semanas, sim, color="#2a78d6", linewidth=2, label="simulado")
        ax.set_title(f"{fila['anio']}: βs = {fila['beta_s']:.2f}, I0 = {fila['I0']:.0f}, "
                     f"RMSE = {fila['rmse_casos']:.0f}", fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
        ax.set_axisbelow(True)
    ejes[0, 0].legend(frameon=False, fontsize=8)
    for ax in ejes[-1]:
        ax.set_xlabel("Semana epidemiológica")
    for ax in ejes[:, 0]:
        ax.set_ylabel("Notificados por semana")
    fig.suptitle("Calibración por año (ρ fijo): forma nacional escalada al total departamental observado", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIGURA, dpi=150)
    plt.close(fig)


def main():
    with ProcessPoolExecutor(max_workers=min(len(ANIOS), os.cpu_count() or 1)) as ex:
        resultados = list(ex.map(calibrar_anio, ANIOS))
    tabla = pd.DataFrame([r[0] for r in resultados])
    tabla.to_csv(SALIDA, index=False)
    figura(resultados)
    columnas = ["anio", "beta_s", "I0", "ganancia_fumigacion", "lluvia_minima", "en_limite",
                "rmse_log1p", "total_observado", "total_simulado", "semana_pico_observado", "semana_pico_simulado"]
    print(tabla[columnas].to_string(index=False))
    for nombre in FINAL:
        v = tabla[nombre]
        print(f"{nombre}: mediana {v.median():.4g}, rango [{v.min():.4g}, {v.max():.4g}], CV entre años {v.std() / v.mean():.2f}")
    print(f"\n{SALIDA}\n{FIGURA}")


if __name__ == "__main__":
    main()
