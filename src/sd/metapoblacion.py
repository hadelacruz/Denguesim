"""A10 · Metapoblación: los 17 municipios con el modelo completo (A1–A3), acoplados
por la movilidad diaria (S13; Balcan et al., 2009).

Cada municipio i tiene su propia lluvia_rel y su Nh (año base). Acoplamiento
sobre los humanos infecciosos, con F_ij = flujo diario de i a j (flujos_od.csv):

    dIh_i/dt += Σ_j ( F_ji · Ih_j / N_j  −  F_ij · Ih_i / N_i )
                 entran infecciosos de j    salen infecciosos de i

Sumado sobre todos los municipios, el acoplamiento es cero: la población total
se conserva (prueba). Se calcula de una vez para los 17 municipios con un
producto de matrices: entradas = (Ih/N) @ F, salidas = (Ih/N) · F.sum(1).

El estado tiene forma (..., 17, 13): la última dimensión son las variables y la
penúltima los municipios; adelante puede ir un lote de corridas o de juegos de
parámetros (se simulan todos a la vez).

Magnitud por municipio: multiplicador de abundancia de mosquitos m_i (sobre
m_base), ajustado con least_squares (17 parámetros, residuos en log) para que
los casos NOTIFICADOS anuales simulados (ρ de A6) se acerquen a
casos_anuales_muni.csv en el año base.

Salida: data/processed/sd/calibracion_municipios.csv
Uso (desde la raíz):  python src/sd/metapoblacion.py
"""

import json
import sys

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/sd")
from comun import PROCESSED, leer_procesado, parametro  # noqa: E402
from modelo_seir_sei import (IIH, ICA, IEH, IRH, ISH, condicion_inicial, derivadas, integrar,  # noqa: E402
                             leer_calibracion, parametros_base)
from vector_lluvia import escala_k, lluvia_semanal, poblacion_anio  # noqa: E402

CALIB_MUNI = PROCESSED / "sd" / "calibracion_municipios.csv"
LIMITES_M = (0.02, 50.0)


def cargar_datos(anio=None):
    """Población, lluvia y matriz de flujos de los 17 municipios en un orden fijo."""
    anio = parametro("sd", "anio_base") if anio is None else anio
    lluvia, cods = lluvia_semanal(anio)
    flujos = leer_procesado("flujos_od.csv").pivot(index="cod_i", columns="cod_j", values="flujo_diario")
    F = flujos.reindex(index=cods, columns=cods).fillna(0.0).to_numpy(float).copy()
    np.fill_diagonal(F, 0.0)
    return {"anio": anio, "cods": cods, "Nh": poblacion_anio(anio, cods), "lluvia": lluvia, "F": F}


def leer_multiplicadores(datos):
    """m_i calibrados (o 1 si aún no se calibra), en el orden de datos['cods']."""
    if not CALIB_MUNI.exists():
        return np.ones(len(datos["cods"]))
    c = pd.read_csv(CALIB_MUNI, dtype={"cod_muni": str}).set_index("cod_muni")
    return c.loc[datos["cods"], "m_multiplicador"].to_numpy(float)


def parametros_meta(datos, m_mult=None, **cambios):
    """Parámetros del modelo para los 17 municipios (valores calibrados de A6)."""
    p = parametros_base()
    cal = leer_calibracion()
    if cal is not None:
        p.update(rho=cal["rho"], beta_s=cal["beta_s"], expuestos_iniciales=cal["I0"],
                 ganancia_fumigacion=cal.get("ganancia_fumigacion", p["ganancia_fumigacion"]),
                 lluvia_minima=cal.get("lluvia_minima", p["lluvia_minima"]))
    m_mult = leer_multiplicadores(datos) if m_mult is None else np.asarray(m_mult, dtype=float)
    p.update(Nh=datos["Nh"], lluvia=datos["lluvia"], F=datos["F"], anio=datos["anio"])
    p.update(cambios)
    p["m_base"] = p["m_base"] * m_mult                          # abundancia propia de cada municipio
    p["k"] = escala_k(p)
    # I0 del departamento repartido en proporción a la población.
    p["expuestos_iniciales"] = np.multiply.outer(np.asarray(p["expuestos_iniciales"]), datos["Nh"] / datos["Nh"].sum())
    return p


def acoplamiento(Ih, p):
    """Σ_j (F_ji·Ih_j/N_j − F_ij·Ih_i/N_i) para todos los municipios a la vez."""
    prevalencia_viajera = Ih / p["Nh"]                          # Ih_j / N_j
    entradas = prevalencia_viajera @ p["F"]                     # Σ_j F_ji · Ih_j/N_j  (personas/día)
    salidas = prevalencia_viajera * p["F"].sum(axis=1)          # Ih_i/N_i · Σ_j F_ij   (personas/día)
    return entradas - salidas


def derivadas_meta(t, y, p):
    """Modelo completo de cada municipio + acoplamiento por movilidad en Ih."""
    dy = derivadas(t, y, p)
    dy[..., IIH] += acoplamiento(y[..., IIH], p)
    return dy


def simular_metapoblacion(datos, p=None, dias=364, h=None):
    """Integra la metapoblación con RK4. Y tiene forma (dias+1, ..., 17, 13)."""
    p = parametros_meta(datos) if p is None else p
    h = parametro("sd", "paso_rk4_rapido") if h is None else h
    y0 = condicion_inicial(p)
    t, Y = integrar(derivadas_meta, y0, p, dias, h)
    return {"t": t, "Y": Y, "p": p}


def verificar_conservacion_total(Y, Nh):
    """Error máximo de Σ_i (Sh+Eh+Ih+Rh) respecto a Σ_i Nh."""
    total = (Y[..., ISH] + Y[..., IEH] + Y[..., IIH] + Y[..., IRH]).sum(axis=-1)
    return float(np.max(np.abs(total - np.sum(Nh))))


def notificados_anuales(datos, log_m):
    """Casos notificados anuales por municipio para uno o varios juegos de log m_i."""
    p = parametros_meta(datos, m_mult=np.exp(log_m))
    res = simular_metapoblacion(datos, p)
    return p["rho"] * res["Y"][-1][..., ICA]


def observados_anuales(datos):
    c = leer_procesado("casos_anuales_muni.csv")
    return c[c.anio == datos["anio"]].set_index("cod_muni").casos.loc[datos["cods"]].to_numpy(float)


def calibrar_multiplicadores(datos, paso_fd=1e-3):
    """least_squares sobre log m_i. El Jacobiano por diferencias finitas se calcula
    simulando los 17 juegos perturbados a la vez (un solo lote)."""
    obs = observados_anuales(datos)
    residuo = lambda x: np.log(notificados_anuales(datos, x)) - np.log(obs)  # noqa: E731

    def jacobiano(x):
        lote = x + paso_fd * np.eye(len(x))
        return ((np.log(notificados_anuales(datos, lote)) - np.log(obs)) - residuo(x)) / paso_fd

    lim = np.log(LIMITES_M)
    r = least_squares(residuo, np.zeros(len(obs)), jac=jacobiano, bounds=(lim[0], lim[1]), max_nfev=60)
    sim = np.exp(r.fun) * obs
    return pd.DataFrame({"cod_muni": datos["cods"], "m_multiplicador": np.exp(r.x).round(5),
                         "casos_observados": obs, "notificados_simulados": sim.round(1),
                         "error_relativo": (sim / obs - 1).round(4)}), r


if __name__ == "__main__":
    datos = cargar_datos()
    tabla, r = calibrar_multiplicadores(datos)
    tabla["nombre"] = tabla.cod_muni.map(leer_procesado("poblacion.csv").set_index("cod_muni").nombre)
    tabla.to_csv(CALIB_MUNI, index=False)
    print(tabla.to_string(index=False))
    print(f"\nRMSE log = {np.sqrt(np.mean(r.fun ** 2)):.4f}; total simulado {tabla.notificados_simulados.sum():.0f} "
          f"vs observado {tabla.casos_observados.sum():.0f}; evaluaciones = {r.nfev}")
    res = simular_metapoblacion(datos, h=0.5, dias=120)
    print("Conservación total:", verificar_conservacion_total(res["Y"], datos["Nh"]))
