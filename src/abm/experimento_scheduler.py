"""Experimento de scheduler (D11, N2): ¿cambia el resultado según cómo se activan las personas?

20 corridas por scheduler con las MISMAS semillas:
  - mixto:           RandomActivation (asíncrono aleatorio)  ← el del modelo
  - secuencial_fijo: BaseScheduler (asíncrono, siempre el mismo orden)
  - sincrono:        SimultaneousActivation (step decide, advance aplica)

Se comparan el pico, el día del pico y el tamaño final con IC 95 % por bootstrap,
y la diferencia de medias contra el mixto (bootstrap de dos muestras).

Resultado esperado (S8, comunicación por el entorno): las personas no leen el
estado de otras dentro del mismo paso; solo leen el entorno, que se actualiza
de forma síncrona después de todas. Por eso NO se esperan diferencias
significativas. El modelo no se modifica para forzarlas; se reporta lo que salga.

Salidas: data/processed/abm/experimento_scheduler.csv, figuras/abm/experimento_scheduler.png
Uso (desde la raíz):  python src/abm/experimento_scheduler.py
"""

import sys
from concurrent.futures import ProcessPoolExecutor

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/abm")
from comun import PROCESSED, parametro  # noqa: E402
from corridas import FIGURAS, TRABAJADORES, bootstrap_ci, semillas_corridas  # noqa: E402
from inicializacion import semilla  # noqa: E402
from modelo import ModeloDengue  # noqa: E402

SCHEDULERS = ["mixto", "secuencial_fijo", "sincrono"]
N_CORRIDAS = 20   # lo fija la guía (D11)
METRICAS = ["pico", "dia_pico", "tamano_final"]


def correr(args):
    scheduler, corrida, semilla_m = args
    serie = ModeloDengue(semilla=semilla_m, scheduler=scheduler).correr()
    casos = serie.nuevos_casos.to_numpy()
    i = int(np.argmax(casos))
    return {"scheduler": scheduler, "corrida": corrida, "pico": int(casos[i]),
            "dia_pico": int(serie.dia.iloc[i]), "tamano_final": int(casos.sum())}


def diferencia_bootstrap(x, y, B, rng):
    """IC 95 % de mean(x) − mean(y) remuestreando cada grupo por separado."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    d = [rng.choice(x, len(x)).mean() - rng.choice(y, len(y)).mean() for _ in range(B)]
    return x.mean() - y.mean(), np.percentile(d, 2.5), np.percentile(d, 97.5)


def main():
    semillas = semillas_corridas(semilla("abm", "experimento_scheduler"), N_CORRIDAS)
    tareas = [(s, m, semillas[m]) for s in SCHEDULERS for m in range(N_CORRIDAS)]
    with ProcessPoolExecutor(max_workers=TRABAJADORES) as ex:
        corridas = pd.DataFrame(list(ex.map(correr, tareas)))
    B = parametro("abm", "bootstrap_B")
    rng = np.random.default_rng(semilla("abm", "bootstrap"))
    filas = []
    for s in SCHEDULERS:
        for k in METRICAS:
            x = corridas[corridas.scheduler == s][k]
            ic = bootstrap_ci(x, B, rng)
            d, lo, hi = diferencia_bootstrap(x, corridas[corridas.scheduler == "mixto"][k], B, rng)
            filas.append({"scheduler": s, "metrica": k, "media": round(ic["media"], 3), "ic_inf": round(ic["ic_inf"], 3),
                          "ic_sup": round(ic["ic_sup"], 3), "dif_vs_mixto": round(d, 3), "dif_ic_inf": round(lo, 3),
                          "dif_ic_sup": round(hi, 3), "diferencia_significativa": bool(not (lo <= 0 <= hi))})
    tabla = pd.DataFrame(filas)
    tabla.to_csv(PROCESSED / "abm" / "experimento_scheduler.csv", index=False)
    corridas.to_csv(PROCESSED / "abm" / "experimento_scheduler_corridas.csv", index=False)

    fig, ejes = plt.subplots(1, 3, figsize=(12, 3.8))
    colores = ["#2a78d6", "#eb6834", "#1baf7a"]
    for ax, k in zip(ejes, METRICAS):
        sub = tabla[tabla.metrica == k]
        for i, (fila, color) in enumerate(zip(sub.itertuples(), colores)):
            ax.errorbar(i, fila.media, yerr=[[fila.media - fila.ic_inf], [fila.ic_sup - fila.media]], fmt="o",
                        color=color, capsize=5, markersize=8, linewidth=2)
        ax.set_xticks(range(3), SCHEDULERS, fontsize=8)
        ax.set_title(f"{k}: media e IC 95 % (bootstrap)", fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
    fig.suptitle(f"Experimento de scheduler: {N_CORRIDAS} corridas por scheduler con las mismas semillas", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGURAS / "experimento_scheduler.png", dpi=150)
    plt.close(fig)
    print(tabla.to_string(index=False))


if __name__ == "__main__":
    main()
