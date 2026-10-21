"""Modelo gravitacional de movilidad diaria entre municipios.

    F_ij = G · P_i^α · P_j^β / d_ij^γ      (i ≠ j)

P = población (poblacion.csv), d = tiempo (min) o distancia (km) por la red
vial (distancias.csv, según ``gravitacional.variable_distancia``).
Los exponentes α, β, γ se CALIBRAN con la matriz origen-destino observada del
Censo 2018 (personas que trabajan o estudian en otro municipio, od_censo.csv)
mediante una regresión de Poisson; los valores quedan en parametros_datos.json
y reemplazan a los de literatura de parametros.yaml. La constante G se fija
para que el total de viajes diarios entre municipios sea ``fraccion_viaja`` ×
población total (también estimada con el Censo).

Salidas:
  data/processed/flujos_od.csv                 cod_i, cod_j, flujo_diario
  data/processed/validacion/sensibilidad_gravitacional.csv
      índices resumen de la red O-D para una grilla de (α, β, γ)

Uso para sensibilidad desde otros módulos:
    from src.sig.gravitacional import flujos
    F = flujos(alpha=0.46, beta=0.64, gamma=2.5)
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "datos"))
from comun import PROCESSED, VALIDACION, guardar, leer_procesado, parametro, registrar_parametro  # noqa: E402


def _param(nombre: str):
    """Valor de gravitacional.<nombre>: primero datos estimados, luego YAML."""
    return parametro("gravitacional", nombre)


def flujos(
    alpha: float | None = None,
    beta: float | None = None,
    gamma: float | None = None,
    fraccion_viaja: float | None = None,
    variable_distancia: str | None = None,
) -> pd.DataFrame:
    """Matriz O-D (formato largo). Parámetros None → valores de configuración."""
    alpha = _param("alpha") if alpha is None else alpha
    beta = _param("beta") if beta is None else beta
    gamma = _param("gamma") if gamma is None else gamma
    fraccion_viaja = _param("fraccion_viaja") if fraccion_viaja is None else fraccion_viaja
    variable_distancia = _param("variable_distancia") if variable_distancia is None else variable_distancia
    if fraccion_viaja is None:
        raise ValueError("fraccion_viaja no está definida (ni en parametros_datos.json ni en parametros.yaml)")

    pob = leer_procesado("poblacion.csv").set_index("cod_muni")["poblacion"].astype(float)
    d = leer_procesado("distancias.csv")
    d = d[d.cod_i != d.cod_j].copy()
    pi = d.cod_i.map(pob).to_numpy()
    pj = d.cod_j.map(pob).to_numpy()
    dij = np.maximum(d[variable_distancia].to_numpy(float), 1e-6)
    sin_g = pi**alpha * pj**beta / dij**gamma
    G = fraccion_viaja * pob.sum() / sin_g.sum()
    out = d[["cod_i", "cod_j"]].copy().reset_index(drop=True)
    out["flujo_diario"] = np.round(G * sin_g, 2)
    out.attrs.update(G=G, alpha=alpha, beta=beta, gamma=gamma, fraccion_viaja=fraccion_viaja, variable_distancia=variable_distancia)
    return out


def resumen_red(F: pd.DataFrame) -> dict:
    """Indicadores simples para comparar configuraciones (sensibilidad)."""
    pob = leer_procesado("poblacion.csv").set_index("cod_muni")["poblacion"]
    salida = F.groupby("cod_i").flujo_diario.sum()
    entrada = F.groupby("cod_j").flujo_diario.sum()
    top = entrada.idxmax()
    w = F.flujo_diario / F.flujo_diario.sum()
    return {
        "destino_principal": top,
        "fraccion_entradas_destino_principal": round(float(entrada.max() / entrada.sum()), 3),
        "max_fraccion_salida": round(float((salida / pob).max()), 3),
        "entropia_flujos": round(float(-(w * np.log(w)).sum()), 3),
    }


def sensibilidad(
    alphas=(0.46, 0.75, 1.0), betas=(0.64, 0.8, 1.0), gammas=(1.0, 1.5, 2.0, 2.5, 3.0)
) -> pd.DataFrame:
    base = flujos()
    filas = []
    for a, b, g in itertools.product(alphas, betas, gammas):
        F = flujos(alpha=a, beta=b, gamma=g)
        corr = np.corrcoef(np.log1p(base.flujo_diario), np.log1p(F.flujo_diario))[0, 1]
        filas.append({"alpha": a, "beta": b, "gamma": g, "corr_log_vs_base": round(corr, 3), **resumen_red(F)})
    return pd.DataFrame(filas)


def _poisson_irls(X: np.ndarray, y: np.ndarray, iter_max: int = 100) -> np.ndarray:
    """Regresión de Poisson (enlace log) por mínimos cuadrados reponderados."""
    b = np.linalg.lstsq(X, np.log(y + 1), rcond=None)[0]
    for _ in range(iter_max):
        mu = np.exp(X @ b)
        z = X @ b + (y - mu) / mu
        W = mu
        b_new = np.linalg.solve(X.T @ (W[:, None] * X), X.T @ (W * z))
        if np.max(np.abs(b_new - b)) < 1e-10:
            return b_new
        b = b_new
    return b


def calibrar_con_censo() -> dict | None:
    """Ajusta α, β, γ con la matriz O-D observada del Censo 2018 (trabajo + estudio).

    log E[T_ij] = log G + α log P_i + β log P_j − γ log d_ij,  T_ij ~ Poisson.
    P = población del Censo 2018 (mismo año que la O-D), d = variable_distancia.
    """
    ruta = PROCESSED / "od_censo.csv"
    if not ruta.exists():
        return None
    var = parametro("gravitacional", "variable_distancia")
    od = leer_procesado("od_censo.csv")
    od = od[(od.cod_j != "FUERA") & (od.cod_i != od.cod_j)]
    d = leer_procesado("distancias.csv").merge(od[["cod_i", "cod_j", "total"]], on=["cod_i", "cod_j"], how="left").fillna({"total": 0})
    pob = leer_procesado("poblacion.csv").set_index("cod_muni")["poblacion_censo2018"].astype(float)
    X = np.column_stack([np.ones(len(d)), np.log(d.cod_i.map(pob)), np.log(d.cod_j.map(pob)), -np.log(d[var].astype(float))])
    y = d.total.to_numpy(float)
    b = _poisson_irls(X, y)
    mu = np.exp(X @ b)
    dev = 2 * np.sum(np.where(y > 0, y * np.log(np.where(y > 0, y, 1) / mu), 0) - (y - mu))
    dev0 = 2 * np.sum(np.where(y > 0, y * np.log(np.where(y > 0, y, 1) / y.mean()), 0) - (y - y.mean()))
    res = {
        "alpha": round(float(b[1]), 4), "beta": round(float(b[2]), 4), "gamma": round(float(b[3]), 4),
        "pseudo_r2_deviance": round(float(1 - dev / dev0), 4),
        "corr_log_flujos": round(float(np.corrcoef(np.log1p(y), np.log1p(mu))[0, 1]), 4),
        "pares": int(len(y)), "variable_distancia": var,
    }
    VALIDACION.mkdir(parents=True, exist_ok=True)
    d.assign(observado=y, ajustado=np.round(mu, 1))[["cod_i", "cod_j", var, "observado", "ajustado"]].to_csv(
        VALIDACION / "gravitacional_vs_censo.csv", index=False)
    pd.DataFrame([res]).to_csv(VALIDACION / "gravitacional_calibracion.csv", index=False)
    nota = f"Calibrado con la O-D del Censo 2018 (regresión de Poisson, pseudo-R² = {res['pseudo_r2_deviance']})."
    registrar_parametro("gravitacional", "alpha", res["alpha"], "adimensional", nota)
    registrar_parametro("gravitacional", "beta", res["beta"], "adimensional", nota)
    registrar_parametro("gravitacional", "gamma", res["gamma"], "adimensional", nota)
    return res


def main() -> None:
    print("[gravitacional] F_ij = G P_i^a P_j^b / d_ij^g")
    cal = calibrar_con_censo()
    if cal:
        print(f"  calibración con O-D del Censo: α={cal['alpha']}, β={cal['beta']}, γ={cal['gamma']}, "
              f"pseudo-R²={cal['pseudo_r2_deviance']}, corr(log)={cal['corr_log_flujos']}")
    F = flujos()
    guardar(F, "flujos_od.csv", ["cod_i", "cod_j", "flujo_diario"])
    print(f"  G={F.attrs['G']:.3g}, α={F.attrs['alpha']}, β={F.attrs['beta']}, γ={F.attrs['gamma']}, "
          f"d={F.attrs['variable_distancia']}, viajes/día={F.flujo_diario.sum():,.0f}")
    VALIDACION.mkdir(parents=True, exist_ok=True)
    sensibilidad().to_csv(VALIDACION / "sensibilidad_gravitacional.csv", index=False)


if __name__ == "__main__":
    main()
