"""D13 · β efectiva del ABM → data/processed/beta_efectiva.json.

Definición: β de un SEIR SOLO HUMANO equivalente, en 1/día.
Por corrida, mínimos cuadrados SIN intercepto de

    nuevos_infectados_locales(t) ≈ β · S(t−1) · I(t−1) / N

desde el día del primer caso hasta el día del pico. β̂ = Σ x·y / Σ x², con
x = S·I/N e y = infecciones nuevas del día. Se usan S e I del día anterior
porque las infecciones del día t se sortean con el entorno del paso anterior,
y solo las infecciones LOCALES (las de fuera del municipio, R2, no dependen
de I). Las corridas sin brote (menos de 2 días con datos) se descartan.

beta = media de las β por corrida; ic_inf, ic_sup = IC 95 % por bootstrap
(B = abm.bootstrap_B) sobre las corridas.

Uso (desde la raíz):  python src/abm/beta_efectiva.py
"""

import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/abm")
from comun import PROCESSED, parametro  # noqa: E402
from corridas import bootstrap_ci  # noqa: E402
from inicializacion import semilla  # noqa: E402

SALIDA = PROCESSED / "abm"


def beta_de_una_corrida(serie):
    """β̂ por mínimos cuadrados sin intercepto entre el primer caso y el pico."""
    serie = serie.sort_values("dia").reset_index(drop=True)
    N = serie[["S", "E", "I", "H", "R"]].iloc[0].sum()
    y = (serie.nuevos_infectados - serie.nuevos_infectados_fuera).to_numpy(float)[1:]
    x = (serie.S * serie.I / N).to_numpy(float)[:-1]              # S(t−1)·I(t−1)/N
    casos = serie.nuevos_casos.to_numpy()[1:]
    if casos.sum() == 0:
        return np.nan, 0
    t0, tp = int(np.argmax(casos > 0)), int(np.argmax(casos))
    x, y = x[t0: tp + 1], y[t0: tp + 1]
    if len(x) < 2 or np.sum(x**2) == 0:
        return np.nan, len(x)
    return float(np.sum(x * y) / np.sum(x**2)), len(x)


def main():
    series = pd.read_csv(SALIDA / "series.csv")
    filas = []
    for corrida, serie in series.groupby("corrida"):
        beta, n = beta_de_una_corrida(serie)
        filas.append({"corrida": corrida, "beta": beta, "dias_ajuste": n})
    tabla = pd.DataFrame(filas)
    tabla.to_csv(SALIDA / "beta_por_corrida.csv", index=False)
    validas = tabla.beta.dropna().to_numpy()
    ic = bootstrap_ci(validas, parametro("abm", "bootstrap_B"), np.random.default_rng(semilla("abm", "bootstrap")))
    salida = {"beta": round(float(ic["media"]), 5), "ic_inf": round(float(ic["ic_inf"]), 5), "ic_sup": round(float(ic["ic_sup"]), 5)}
    (PROCESSED / "beta_efectiva.json").write_text(json.dumps(salida, indent=2), encoding="utf-8")
    gamma = parametro("transmision", "gamma")
    print(f"{len(validas)} de {len(tabla)} corridas válidas; mediana β = {np.median(validas):.4f}")
    print(json.dumps(salida, indent=2))
    print(f"β/γ = {salida['beta'] / gamma:.3f} (γ = {gamma})")


if __name__ == "__main__":
    main()
