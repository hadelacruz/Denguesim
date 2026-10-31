"""A7 (N2) · Validación anual por municipio de la metapoblación.

Casos NOTIFICADOS anuales simulados (ρ · casos verdaderos) contra
casos_anuales_muni.csv, con un IC 95 % que combina la incertidumbre de
parámetros (sd.n_corridas juegos de la calibración) y ruido de Poisson.
Se reporta el % de municipios cuyo valor observado cae dentro del IC.

  - 2023 (año base): DENTRO de la muestra, porque los m_i se calibraron con
    esos totales. Solo verifica que la incertidumbre de parámetros no los aleje.
  - 2024: FUERA de la muestra. Mismos m_i y parámetros, con la lluvia y la
    población de 2024 y condiciones iniciales nuevas (sin inmunidad del año
    anterior: limitación).

Salidas: data/processed/sd/validacion_municipios.csv, figuras/sd/validacion_municipios.png
Uso (desde la raíz):  python src/sd/validacion_municipios.py
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
from escenarios import muestras_relativas, simular_corridas  # noqa: E402
from metapoblacion import cargar_datos, observados_anuales  # noqa: E402
from modelo_seir_sei import CALIBRACION, ICA  # noqa: E402
from validacion import semilla  # noqa: E402


def validar_anio(anio, cal, relativos, semillas_corrida, rng):
    datos = cargar_datos(anio)
    res, p = simular_corridas("sin_intervencion", datos, cal, relativos, semillas_corrida)
    notificados = p["rho"] * res["Y"][-1, ..., ICA]                 # (corridas, 17)
    con_ruido = rng.poisson(notificados)
    obs = observados_anuales(datos)
    tabla = pd.DataFrame({"anio": anio, "cod_muni": datos["cods"], "observado": obs,
                          "mediana_simulada": np.median(notificados, axis=0).round(1),
                          "ic_inf": np.percentile(con_ruido, 2.5, axis=0), "ic_sup": np.percentile(con_ruido, 97.5, axis=0)})
    tabla["dentro_ic"] = tabla.observado.between(tabla.ic_inf, tabla.ic_sup)
    tabla["tipo"] = "dentro de muestra" if anio == cal["anio"] else "fuera de muestra"
    return tabla


def figura(tabla):
    nombres = leer_procesado("poblacion.csv").set_index("cod_muni").nombre
    anios = sorted(tabla.anio.unique())
    fig, ejes = plt.subplots(1, len(anios), figsize=(6 * len(anios), 5))
    for ax, anio in zip(np.atleast_1d(ejes), anios):
        sub = tabla[tabla.anio == anio].sort_values("observado")
        y = np.arange(len(sub))
        ax.hlines(y, sub.ic_inf, sub.ic_sup, color="#2a78d6", linewidth=3, alpha=0.5, label="IC 95 % simulado")
        ax.scatter(sub.mediana_simulada, y, color="#2a78d6", s=20, label="mediana simulada")
        ax.scatter(sub.observado, y, color="#0b0b0b", marker="x", s=30, zorder=3, label="observado")
        ax.set_xscale("log")
        ax.set_yticks(y, [nombres[c] for c in sub.cod_muni], fontsize=7)
        ax.set_xlabel("Casos notificados en el año (escala log)")
        ax.set_title(f"{anio} ({sub.tipo.iloc[0]}): {sub.dentro_ic.mean():.0%} de municipios dentro del IC", fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", color="#e6e5e0", linewidth=0.6)
    np.atleast_1d(ejes)[0].legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig("figuras/sd/validacion_municipios.png", dpi=150)
    plt.close(fig)


def main():
    cal = json.loads(CALIBRACION.read_text(encoding="utf-8"))
    n = parametro("sd", "n_corridas")
    base = semilla("sd", "validacion")
    relativos = muestras_relativas(cal, n, np.random.default_rng(base))
    semillas_corrida = np.random.SeedSequence(base).spawn(n)
    rng = np.random.default_rng(base + 1)
    tabla = pd.concat([validar_anio(a, cal, relativos, semillas_corrida, rng) for a in (cal["anio"], cal["anio"] + 1)],
                      ignore_index=True)
    tabla.to_csv(PROCESSED / "sd" / "validacion_municipios.csv", index=False)
    figura(tabla)
    for anio, sub in tabla.groupby("anio"):
        print(f"{anio} ({sub.tipo.iloc[0]}): {sub.dentro_ic.mean():.1%} de municipios dentro del IC; "
              f"total observado {sub.observado.sum():.0f}, mediana simulada {sub.mediana_simulada.sum():.0f}; "
              f"Spearman = {sub[['observado', 'mediana_simulada']].corr('spearman').iloc[0, 1]:.3f}")


if __name__ == "__main__":
    main()
