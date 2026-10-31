"""A8 · Sensibilidad local ±20 % (criterio de S6) del modelo departamental calibrado.

Se mueve cada parámetro ±20 % (a, b, c, σh, σv, γ, μ, βs, m_base, τ) dejando los
demás en su valor calibrado, y se mide el efecto sobre la altura y el día del
pico de casos verdaderos diarios. Todas las variantes se simulan en un solo lote.

Detalle: k (la escala del reclutamiento Λ) se calcula con μ NOMINAL, así un μ
mayor significa más mortalidad y menos mosquitos (como fumigar), en lugar de
reescalar Λ para mantener Nv/Nh.

Criterio de clase: si el pico cambia más de 50 % ante ±20 % en un parámetro,
el modelo es SENSIBLE a él y las conclusiones que dependen de ese parámetro
son inciertas. Se reportan rangos, no valores únicos.

Salidas: data/processed/sd/sensibilidad.csv, figuras/sd/tornado.png
Uso (desde la raíz):  python src/sd/sensibilidad.py
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/sd")
from comun import PROCESSED  # noqa: E402
from modelo_seir_sei import casos_verdaderos_diarios, parametros_departamento, simular_seir_sei  # noqa: E402
from vector_lluvia import escala_k  # noqa: E402

PARAMETROS = ["a", "b", "c", "sigma_h", "sigma_v", "gamma", "mu", "beta_s", "m_base", "tau_desarrollo"]
VARIACION = 0.20
UMBRAL_SENSIBLE = 0.50


def correr_sensibilidad():
    base = parametros_departamento()
    variantes = [("base", 0.0)] + [(nombre, s * VARIACION) for nombre in PARAMETROS for s in (-1, 1)]
    p = dict(base)
    for nombre in PARAMETROS:
        p[nombre] = np.array([base[nombre] * (1 + d) if n == nombre else base[nombre] for n, d in variantes])
    p["k"] = escala_k({**p, "mu": base["mu"]})                    # Λ con μ nominal (ver docstring)
    res = simular_seir_sei(p, dias=364)
    nuevos = casos_verdaderos_diarios(res)                         # (dias+1, variantes)
    pico, dia = nuevos.max(axis=0), nuevos.argmax(axis=0)
    tabla = pd.DataFrame({"parametro": [n for n, _ in variantes], "variacion": [d for _, d in variantes],
                          "pico": pico.round(2), "dia_pico": dia})
    tabla["cambio_pico_relativo"] = (tabla.pico / pico[0] - 1).round(4)
    tabla["cambio_dia_pico"] = tabla.dia_pico - dia[0]
    return tabla


def clasificar(tabla):
    var = tabla[tabla.parametro != "base"]
    max_cambio = var.groupby("parametro").cambio_pico_relativo.apply(lambda x: x.abs().max())
    tabla["clasificacion"] = tabla.parametro.map(lambda n: "base" if n == "base" else
                                                 ("sensible" if max_cambio[n] > UMBRAL_SENSIBLE else "robusto"))
    return tabla


def tornado(tabla):
    var = tabla[tabla.parametro != "base"].pivot(index="parametro", columns="variacion", values="cambio_pico_relativo")
    var = var.loc[var.abs().max(axis=1).sort_values().index]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    y = np.arange(len(var))
    ax.barh(y, var[-VARIACION] * 100, color="#eb6834", height=0.6, label="−20 %")
    ax.barh(y, var[VARIACION] * 100, color="#2a78d6", height=0.6, label="+20 %")
    ax.axvline(0, color="#0b0b0b", linewidth=0.8)
    for lim in (-50, 50):
        ax.axvline(lim, color="#8a8984", linewidth=1, linestyle="--")
    ax.set_yticks(y, var.index)
    ax.set_xlabel("Cambio en la altura del pico (%)")
    ax.set_title("Sensibilidad ±20 % del pico de casos (líneas punteadas: umbral de 50 % de S6)", fontsize=10)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig("figuras/sd/tornado.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    tabla = clasificar(correr_sensibilidad())
    tabla.to_csv(PROCESSED / "sd" / "sensibilidad.csv", index=False)
    tornado(tabla)
    print(tabla.to_string(index=False))
