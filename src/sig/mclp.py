"""G2 · Problema de cobertura máxima (MCLP, Church y ReVelle 1974) con PuLP + CBC → unidades_mclp.csv.

    max Σᵢ dᵢ·yᵢ     sujeto a   yᵢ ≤ Σ_{j ∈ Nᵢ} xⱼ,   Σⱼ xⱼ ≤ p,   xⱼ ∈ {0, 1},   0 ≤ yᵢ ≤ 1

- Zona: grilla piloto de Amatitlán (0114). Candidatos y puntos de demanda = celdas con
  población > 0. Nᵢ = celdas j a ≤ sig.radio_cobertura_m del centro de i (x_utm, y_utm).
- Demanda dᵢ = casos esperados de Amatitlán (sin_intervencion, media de corridas, total
  del año base) × poblacionᵢ / población total × (mosquitos por persona de la celda ÷
  su media), si sig.ponderar_mosquitos. SUPUESTO: se usa mosquitos POR PERSONA
  (densidad del autómata ÷ población, el m_c del ABM) y no la densidad absoluta, porque
  esa ya crece con la población (K ∝ población) y la contaría dos veces.
- Instalaciones existentes: los hospitales con atiende_dengue = True a ≤ radio de alguna
  celda quedan FIJOS; la demanda que ya cubren se descuenta antes de optimizar (cobertura
  "antes"). Se resuelve para p = 1 … sig.p_max y se compara contra el VORAZ del Lab 5.
- poblacion_cubierta de cada unidad = población de las celdas que cubre de forma NUEVA,
  asignando cada celda a la unidad seleccionada más cercana (para no contar doble).

`resolver_mclp(p, radio_m, ponderar_mosquitos)` devuelve el DataFrame del contrato en
menos de 3 s (la matriz de distancias se calcula una vez); la usa el slider del demo.
Este archivo NO importa geopandas (el demo lo importa).

Salidas: data/processed/unidades_mclp.csv, data/processed/sig/mclp_resumen.csv,
         data/processed/sig/demanda_mclp.csv
Uso (desde la raíz):  python src/sig/mclp.py
"""

import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import pulp
from pyproj import Transformer

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src" / "datos"))
from comun import CRS_GEO, CRS_METRICO, PROCESSED, leer_procesado  # noqa: E402
from comun import parametro as _parametro  # noqa: E402

COLUMNAS = ["p", "cod_celda", "lat", "lon", "poblacion_cubierta"]
DEMANDA = PROCESSED / "sig" / "demanda_mclp.csv"


@lru_cache(maxsize=None)
def parametro(seccion, clave):
    """parametro() con caché (el slider del demo llama muchas veces)."""
    return _parametro(seccion, clave)


# ------------------------------------------------------------------ datos
def casos_amatitlan():
    """Casos verdaderos esperados en Amatitlán: sin_intervencion, media entre corridas, año base."""
    resumen = PROCESSED / "sig" / "casos_resumen.csv"
    if resumen.exists():                                   # tabla liviana de resumenes.py
        r = pd.read_csv(resumen, dtype={"cod_muni": str})
        return float(r[(r.escenario == "sin_intervencion") & (r.cod_muni == "0114")].media.sum())
    c = leer_procesado("casos_esperados.csv")
    c = c[(c.escenario == "sin_intervencion") & (c.cod_muni == "0114")]
    return float(c.groupby("corrida").nuevos.sum().mean())


def construir_demanda():
    """Celdas pobladas con población, mosquitos por persona relativos y casos totales."""
    g = pd.read_csv(PROCESSED / "grilla_piloto.csv")
    g = g[g.poblacion > 0].reset_index(drop=True)
    m = pd.read_csv(PROCESSED / "ca_mosquitos.csv")
    m = m[m.anio == parametro("sd", "anio_base")].groupby("cod_celda").densidad.mean()
    g["mosquitos_por_persona"] = m.reindex(g.cod_celda).to_numpy() / g.poblacion
    g["mosquitos_rel"] = g.mosquitos_por_persona / g.mosquitos_por_persona.mean()
    g["casos_amatitlan"] = casos_amatitlan()
    return g[["cod_celda", "lat", "lon", "x_utm", "y_utm", "poblacion", "mosquitos_rel", "casos_amatitlan"]]


@lru_cache(maxsize=1)
def datos_mclp():
    """Celdas (de demanda_mclp.csv si existe), matriz de distancias y distancia a hospitales."""
    celdas = pd.read_csv(DEMANDA) if DEMANDA.exists() else construir_demanda()
    xy = celdas[["x_utm", "y_utm"]].to_numpy()
    dist = np.sqrt(((xy[:, None, :] - xy[None, :, :]) ** 2).sum(axis=-1))   # metros
    h = leer_procesado("hospitales.csv")
    h = h[h.atiende_dengue.astype(bool)]
    hx, hy = Transformer.from_crs(CRS_GEO, CRS_METRICO, always_xy=True).transform(h.lon.to_numpy(), h.lat.to_numpy())
    dist_hosp = np.sqrt((xy[:, 0, None] - hx[None]) ** 2 + (xy[:, 1, None] - hy[None]) ** 2).min(axis=1)
    return celdas, dist, dist_hosp


def demanda(celdas, ponderar_mosquitos):
    peso = celdas.mosquitos_rel.to_numpy() if ponderar_mosquitos else 1.0
    return celdas.casos_amatitlan.to_numpy() * celdas.poblacion.to_numpy() / celdas.poblacion.sum() * peso


# ------------------------------------------------------------------ modelos
def mclp_optimo(d, cubre, p):
    """MCLP con PuLP/CBC. cubre[i, j] = la celda j cubre a la celda i. Devuelve índices elegidos."""
    n = len(d)
    prob = pulp.LpProblem("mclp", pulp.LpMaximize)
    x = [pulp.LpVariable(f"x{j}", cat="Binary") for j in range(n)]
    y = [pulp.LpVariable(f"y{i}", lowBound=0, upBound=1) for i in range(n)]
    prob += pulp.lpSum(float(d[i]) * y[i] for i in range(n) if d[i] > 0)
    for i in np.flatnonzero(d > 0):
        prob += y[i] <= pulp.lpSum(x[j] for j in np.flatnonzero(cubre[i]))
    prob += pulp.lpSum(x) <= p
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    return [j for j in range(n) if x[j].value() is not None and x[j].value() > 0.5]


def mclp_voraz(d, cubre, p):
    """Voraz (Lab 5): en cada paso, la celda que cubre más demanda aún no cubierta."""
    restante, elegidos = d.astype(float).copy(), []
    for _ in range(p):
        ganancia = restante @ cubre                        # demanda nueva que cubriría cada candidato
        j = int(np.argmax(ganancia))
        if ganancia[j] <= 0:
            break
        elegidos.append(j)
        restante[cubre[:, j]] = 0.0
    return elegidos


def cubierta(cubre, elegidos):
    return cubre[:, elegidos].any(axis=1) if elegidos else np.zeros(cubre.shape[0], dtype=bool)


def resolver_mclp(p, radio_m=None, ponderar_mosquitos=None, devolver_detalle=False):
    """Unidades nuevas óptimas para p, con el DataFrame del contrato (p, cod_celda, lat, lon, poblacion_cubierta)."""
    radio_m = parametro("sig", "radio_cobertura_m") if radio_m is None else radio_m
    ponderar_mosquitos = parametro("sig", "ponderar_mosquitos") if ponderar_mosquitos is None else ponderar_mosquitos
    celdas, dist, dist_hosp = datos_mclp()
    cubre = dist <= radio_m
    existente = dist_hosp <= radio_m
    d = demanda(celdas, ponderar_mosquitos)
    residual = np.where(existente, 0.0, d)
    elegidos = mclp_optimo(residual, cubre, p)
    nueva = cubierta(cubre, elegidos) & ~existente
    # Cada celda nueva se asigna a la unidad elegida más cercana.
    cercana = np.array(elegidos)[np.argmin(dist[:, elegidos], axis=1)] if elegidos else np.array([], dtype=int)
    pob = celdas.poblacion.to_numpy()
    unidades = pd.DataFrame({
        "p": p, "cod_celda": celdas.cod_celda.to_numpy()[elegidos], "lat": celdas.lat.to_numpy()[elegidos],
        "lon": celdas.lon.to_numpy()[elegidos],
        "poblacion_cubierta": [int(pob[nueva & (cercana == j)].sum()) for j in elegidos],
    })[COLUMNAS]
    if not devolver_detalle:
        return unidades
    voraz = mclp_voraz(residual, cubre, p)
    total = d.sum()
    detalle = {
        "p": p, "demanda_cubierta_antes_pct": 100 * d[existente].sum() / total,
        "demanda_cubierta_despues_pct": 100 * d[existente | nueva].sum() / total,
        "poblacion_cubierta_antes": int(pob[existente].sum()),
        "poblacion_cubierta_despues": int(pob[existente | nueva].sum()),
        "voraz_demanda_cubierta_despues_pct": 100 * d[existente | (cubierta(cubre, voraz) & ~existente)].sum() / total,
    }
    return unidades, detalle


def main():
    construir_demanda().to_csv(DEMANDA, index=False)
    datos_mclp.cache_clear()
    tablas, resumen = [], []
    for p in range(1, parametro("sig", "p_max") + 1):
        unidades, detalle = resolver_mclp(p, devolver_detalle=True)
        tablas.append(unidades)
        resumen.append(detalle)
    unidades = pd.concat(tablas, ignore_index=True)
    unidades.to_csv(PROCESSED / "unidades_mclp.csv", index=False)
    resumen = pd.DataFrame(resumen).round(3)
    resumen.to_csv(PROCESSED / "sig" / "mclp_resumen.csv", index=False)
    print(f"unidades_mclp.csv: {len(unidades)} filas · radio {parametro('sig', 'radio_cobertura_m')} m · "
          f"ponderar mosquitos = {parametro('sig', 'ponderar_mosquitos')}")
    print(resumen.to_string(index=False))


if __name__ == "__main__":
    main()
