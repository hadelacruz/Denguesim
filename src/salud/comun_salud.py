"""Utilidades comunes del módulo de Salud: semillas, bootstrap y demanda hospitalaria
por hospital (insumo de R4, R6 y R9).

Supuestos:
- Solo reciben demanda los hospitales MSPAS e IGSS con `atiende_dengue = True`
  (los privados y ONG no reciben la demanda pública).
- Cada municipio manda su demanda a los hospitales elegibles de su propio municipio;
  si no tiene, a los del municipio con hospital elegible más cercano por `tiempo_min`
  (distancias.csv). Si un municipio tiene varios hospitales elegibles, la demanda se
  reparte por igual entre ellos (la Ciudad de Guatemala tiene 13: mandar todo a uno
  solo dejaría 12 hospitales vacíos). Es una simplificación.
- Todos los hospitales tienen la misma capacidad base (no hay dato de camas).
- Hospitalizaciones esperadas por día = ρ · nuevos · salud.fraccion_hospitalizada.
  `nuevos` son casos VERDADEROS; se multiplican por ρ porque `fraccion_hospitalizada`
  está definida en el YAML como "hospitalizados / casos notificados" (y así lo indica
  data/processed/sd/casos_esperados_info.md).
"""

import json
import sys
from functools import lru_cache

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, "src/datos")
from comun import CONFIG, PROCESSED, leer_procesado, parametros  # noqa: E402
from comun import parametro as _parametro  # noqa: E402

ESCENARIOS_SD = ["sin_intervencion", "fumigacion_aleatoria", "fumigacion_hubs", "eliminacion_criaderos", "linea_base_camas"]
ESCENARIOS_DES = ESCENARIOS_SD + ["ampliacion_camas"]
DIAS = 365


@lru_cache(maxsize=None)
def parametro(seccion, clave):
    """parametro() de src/datos/comun.py con caché: leer el YAML cuesta ~0.1 s y el DES
    lo consulta miles de veces. Mismo valor (primero parametros_datos.json, luego el YAML)."""
    return _parametro(seccion, clave)


def semilla(clave, seccion="salud"):
    """Semilla desde config/semillas.yaml."""
    with open(CONFIG / "semillas.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)[seccion][clave]


def rango(seccion, clave):
    """[mínimo, máximo] de un parámetro de config/parametros.yaml."""
    return parametros()[seccion][clave]["rango"]


def rho_calibrado():
    """Factor de reporte ρ de calibracion.json (Alex, A6)."""
    cal = json.loads((PROCESSED / "sd" / "calibracion.json").read_text(encoding="utf-8"))
    return float(cal["valores"]["rho"])


def hospitales_elegibles():
    """MSPAS e IGSS que atienden dengue, en orden de id_hosp."""
    h = leer_procesado("hospitales.csv")
    elegibles = h[h.sector.isin(["MSPAS", "IGSS"]) & h.atiende_dengue.astype(bool)]
    return elegibles.sort_values("id_hosp").reset_index(drop=True)


def municipio_destino(cods):
    """Municipio cuyos hospitales atienden a cada municipio (el propio o el más cercano)."""
    con_hospital = set(hospitales_elegibles().cod_muni)
    d = leer_procesado("distancias.csv")
    destino = {}
    for c in cods:
        if c in con_hospital:
            destino[c] = c
        else:
            cand = d[(d.cod_i == c) & d.cod_j.isin(con_hospital)]
            destino[c] = cand.loc[cand.tiempo_min.idxmin(), "cod_j"]
    return destino


def matriz_asignacion(cods):
    """A (17 × H): fracción de la demanda del municipio i que va al hospital h."""
    h = hospitales_elegibles()
    destino = municipio_destino(cods)
    A = np.zeros((len(cods), len(h)))
    for i, c in enumerate(cods):
        mios = np.flatnonzero(h.cod_muni.to_numpy() == destino[c])
        A[i, mios] = 1.0 / len(mios)
    return A, h


def tabla_asignacion(cods):
    """Municipio → municipio de destino y hospitales que lo atienden (para documentar)."""
    A, h = matriz_asignacion(cods)
    destino = municipio_destino(cods)
    return pd.DataFrame({"cod_muni": cods, "cod_muni_destino": [destino[c] for c in cods],
                         "hospitales": [";".join(h.id_hosp[A[i] > 0]) for i in range(len(cods))]})


def nuevos_por_escenario(corridas=False):
    """nuevos de casos_esperados.csv: {escenario: arreglo (17, 365)} con la media entre
    corridas, o (n_corridas, 17, 365) si corridas=True. Devuelve también los cods."""
    df = leer_procesado("casos_esperados.csv")
    cods = sorted(df.cod_muni.unique())
    salida = {}
    for esc, g in df.groupby("escenario"):
        cubo = g.pivot_table(index=["corrida", "cod_muni"], columns="dia", values="nuevos").sort_index()
        arr = cubo.to_numpy().reshape(g.corrida.nunique(), len(cods), -1)
        salida[esc] = arr if corridas else arr.mean(axis=0)
    return salida, cods


def demanda_hospitalaria(nuevos, A, rho=None, fraccion=None):
    """Hospitalizaciones esperadas por hospital y día: (…, 17, dias) → (…, H, dias)."""
    rho = rho_calibrado() if rho is None else rho
    fraccion = parametro("salud", "fraccion_hospitalizada") if fraccion is None else fraccion
    hosp_muni = np.asarray(rho)[..., None, None] * fraccion * np.asarray(nuevos)   # personas/día
    return np.einsum("...id,ih->...hd", hosp_muni, A)


def bootstrap_ci(Y, B, rng):
    """Media, IC 95 % por percentiles 2.5 y 97.5 y error estándar bootstrap (Lab 4)."""
    Y = np.asarray(Y, dtype=float)
    medias = Y[rng.integers(0, len(Y), size=(B, len(Y)))].mean(axis=1)
    return Y.mean(), np.percentile(medias, 2.5), np.percentile(medias, 97.5), medias.std(ddof=1)


def bootstrap_pareado(base, otro, B, rng):
    """IC 95 % de la media de ΔY = base − otro remuestreando los MISMOS índices (Lab 4)."""
    delta = np.asarray(base, dtype=float) - np.asarray(otro, dtype=float)
    idx = rng.integers(0, len(delta), size=(B, len(delta)))
    medias = delta[idx].mean(axis=1)
    return delta.mean(), np.percentile(medias, 2.5), np.percentile(medias, 97.5)
