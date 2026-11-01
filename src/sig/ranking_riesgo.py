"""G3 · Ranking de riesgo por municipio: riesgo epidemiológico + centralidad en la red → ranking_riesgo.csv

    incidencia_esperada = casos esperados ÷ poblacion × 100 000   (sin_intervencion, media de corridas)
    dia_llegada         = primer día con nuevos acumulados ≥ sig.umbral_llegada_casos (365 si nunca)
    riesgo_casos        = peso_incidencia · minmax(incidencia) + peso_llegada · minmax(−dia_llegada)
    centralidad         = promedio de minmax(grado), minmax(intermediacion), minmax(eigenvector)
    puntaje             = peso_riesgo · riesgo_casos + (1 − peso_riesgo) · centralidad
    posicion            = 1 … 17 por puntaje descendente

LIMITACIÓN: el orden de llegada por municipio no está validado con datos (solo existe a
nivel de 4 áreas de salud, actividad_semanal_area_salud.csv).

Sensibilidad: Spearman entre el ranking base y los rankings con peso_riesgo ∈ {0.4 … 0.8},
y contra una variante con la incidencia OBSERVADA (casos_anuales_muni.csv, media 2014–2024).

Salidas: data/processed/ranking_riesgo.csv y data/processed/sig/ranking_sensibilidad.csv
Uso (desde la raíz):  python src/sig/ranking_riesgo.py
"""

import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, "src/datos")
from comun import PROCESSED, leer_procesado, parametro  # noqa: E402

COLUMNAS = ["cod_muni", "riesgo_casos", "centralidad", "puntaje", "posicion"]
PESOS_RIESGO = [0.4, 0.5, 0.6, 0.7, 0.8]


def minmax(x):
    x = np.asarray(x, dtype=float)
    rango = x.max() - x.min()
    return (x - x.min()) / rango if rango > 0 else np.zeros_like(x)


def indicadores_esperados():
    """Incidencia esperada y día de llegada por municipio (sin_intervencion, media de corridas)."""
    c = leer_procesado("casos_esperados.csv")
    c = c[c.escenario == "sin_intervencion"]
    diario = c.groupby(["cod_muni", "dia"]).nuevos.mean().unstack("dia")       # media entre corridas
    pob = leer_procesado("poblacion.csv").set_index("cod_muni").poblacion.loc[diario.index]
    acumulado = diario.cumsum(axis=1).to_numpy()
    llego = acumulado >= parametro("sig", "umbral_llegada_casos")
    dia_llegada = np.where(llego.any(axis=1), llego.argmax(axis=1), 365)
    return pd.DataFrame({"cod_muni": diario.index, "incidencia": diario.sum(axis=1).to_numpy() / pob.to_numpy() * 1e5,
                         "dia_llegada": dia_llegada})


def incidencia_observada():
    c = leer_procesado("casos_anuales_muni.csv")
    c = c[c.anio.between(2014, 2024)].groupby("cod_muni").casos.mean()
    pob = leer_procesado("poblacion.csv").set_index("cod_muni").poblacion
    return (c / pob.loc[c.index] * 1e5).rename("incidencia")


def centralidad_red(cods):
    c = leer_procesado("centralidad.csv").set_index("cod_muni").loc[cods]
    return np.mean([minmax(c[k]) for k in ("grado", "intermediacion", "eigenvector")], axis=0)


def ranking(ind, peso_riesgo=None):
    peso_riesgo = parametro("sig", "peso_riesgo") if peso_riesgo is None else peso_riesgo
    riesgo = (parametro("sig", "peso_incidencia") * minmax(ind.incidencia)
              + parametro("sig", "peso_llegada") * minmax(-ind.dia_llegada))
    cen = centralidad_red(ind.cod_muni.tolist())
    r = pd.DataFrame({"cod_muni": ind.cod_muni.to_numpy(), "riesgo_casos": riesgo, "centralidad": cen,
                      "puntaje": peso_riesgo * riesgo + (1 - peso_riesgo) * cen})
    r["posicion"] = r.puntaje.rank(ascending=False, method="first").astype(int)
    return r.sort_values("posicion").reset_index(drop=True)[COLUMNAS]


def sensibilidad(ind, base):
    orden_base = base.set_index("cod_muni").posicion
    filas = []
    variantes = [("incidencia_esperada", w, ind) for w in PESOS_RIESGO]
    obs = ind.drop(columns="incidencia").merge(incidencia_observada(), left_on="cod_muni", right_index=True)
    variantes.append(("incidencia_observada_2014_2024", parametro("sig", "peso_riesgo"), obs))
    for nombre, w, datos in variantes:
        r = ranking(datos, w).set_index("cod_muni").posicion.loc[orden_base.index]
        filas.append({"variante": nombre, "peso_riesgo": w, "spearman_vs_base": round(spearmanr(orden_base, r)[0], 4),
                      "top3": ";".join(r.sort_values().index[:3])})
    return pd.DataFrame(filas)


def main():
    ind = indicadores_esperados()
    base = ranking(ind)
    base.round(4).to_csv(PROCESSED / "ranking_riesgo.csv", index=False)
    sens = sensibilidad(ind, base)
    sens.to_csv(PROCESSED / "sig" / "ranking_sensibilidad.csv", index=False)
    nombres = leer_procesado("poblacion.csv").set_index("cod_muni").nombre
    print(base.assign(nombre=base.cod_muni.map(nombres)).round(3).to_string(index=False))
    print("\n" + sens.to_string(index=False))


if __name__ == "__main__":
    main()
