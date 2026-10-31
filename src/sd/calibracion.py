"""A6 · Calibración del modelo de una población (departamento de Guatemala).

Objetivo: casos NOTIFICADOS semanales del departamento en el año base =
suma por semana de casos_semanales.csv. Ojo: esa tabla es un ESTIMADO (la
forma nacional escalada al total departamental observado), no una
observación semanal directa; el total anual sí es observado.

Parámetros base (los tres desafíos de calibración de S6):
    ρ   ∈ [0.01, 1]    factor de reporte (subregistro)
    βs  ∈ [0.1, 10]    multiplicador de transmisión ("β estacional")
    I0  ∈ [1, 1000]    expuestos iniciales (condición inicial desconocida)
Parámetros agregados (ambos son "supuesto del modelo, a ajustar"):
    g   ∈ [0.001, 10]  ganancia del loop B de fumigación (sd.ganancia_fumigacion)
    ℓ   ∈ [0.05, 0.3]  lluvia mínima: criaderos que no dependen de la lluvia
                       (sd.lluvia_minima, dentro de su rango documentado)

Se hicieron tres ajustes (los dos primeros quedan en el JSON como comparación):
  1. Solo (ρ, βs, I0) → FALLA: infecta al 97 % de la población
     con un pico 12 veces mayor que el observado. Para que haya casos en la época
     seca el modelo necesita R ≈ 1 con pocos mosquitos, y eso obliga a R0 ≈ 3 en
     temporada. La curva observada baja desde la semana 41 aunque la lluvia sigue
     alta hasta la 45: eso es un mecanismo de balance (loop B), no agotamiento de
     susceptibles.
  2. Los 5 parámetros → buen ajuste, pero corr(log ρ, log I0) = −1: ρ NO es
     identificable. Con el loop B respondiendo a los NOTIFICADOS, un ρ mayor
     produce más fumigación por caso verdadero y la curva notificada casi no
     cambia; solo el producto ρ·I0 (primeras semanas) queda fijado.
  3. FINAL: ρ fijo en su valor de literatura (observacion.factor_reporte = 0.2,
     rango 0.05–0.5) y se calibran βs, I0, g y ℓ.

Método: θ = log(parámetros). Primero una grilla gruesa (simulada de forma
vectorizada, todos los juegos a la vez) y luego scipy.optimize.least_squares
desde los mejores puntos, con residuos r_w = log1p(simulado_w) − log1p(observado_w).
Covarianza aproximada de θ: (JᵀJ)⁻¹·s², con s² = SCE / (n − p).

Salidas: data/processed/sd/calibracion.json, figuras/sd/calibracion.png
Uso (desde la raíz):  python src/sd/calibracion.py
"""

import itertools
import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.optimize import least_squares  # noqa: E402

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/sd")
from comun import leer_procesado, parametro  # noqa: E402
from modelo_seir_sei import CALIBRACION, ICA, casos_notificados_semanales, parametros_departamento, sce, simular_seir_sei  # noqa: E402

# nombre → (límites, clave en el diccionario de parámetros del modelo)
PARAMETROS = {
    "rho": ([0.01, 1.0], "rho"),
    "beta_s": ([0.1, 10.0], "beta_s"),
    "I0": ([1.0, 1000.0], "expuestos_iniciales"),
    "ganancia_fumigacion": ([0.001, 10.0], "ganancia_fumigacion"),
    "lluvia_minima": ([0.05, 0.3], "lluvia_minima"),
}
BASE = ["rho", "beta_s", "I0"]                       # ajuste 1 (comparación)
FINAL = ["beta_s", "I0", "ganancia_fumigacion", "lluvia_minima"]  # ajuste 3 (ρ fijo)
N_PUNTOS_GRILLA = {"rho": 9, "beta_s": 13, "I0": 4, "ganancia_fumigacion": 6, "lluvia_minima": 3}


def observado_departamento(anio):
    """Casos semanales del departamento (suma de los 17 municipios), semanas 1..52."""
    s = leer_procesado("casos_semanales.csv")
    s = s[s.anio == anio].groupby("semana_epi").casos.sum().sort_index()
    return s.to_numpy(float)[:52]


def parametros_modelo(valores, anio):
    """Diccionario de parámetros del modelo con los valores dados (escalares o arreglos)."""
    cambios = {PARAMETROS[n][1]: v for n, v in valores.items()}
    return parametros_departamento(anio, calibrado=False, **cambios)


def simular_notificados(valores, anio, n_semanas, h=None):
    """Casos notificados semanales simulados, forma (n_semanas, ...)."""
    p = parametros_modelo(valores, anio)
    h = parametro("sd", "paso_rk4_rapido") if h is None else h
    res = simular_seir_sei(p, dias=7 * n_semanas, h=h)
    return casos_notificados_semanales(res, p, n_semanas), res, p


def _valores(theta, nombres, fijos):
    return {**fijos, **dict(zip(nombres, np.exp(theta)))}


def residuos(theta, nombres, fijos, obs, anio):
    sim, _, _ = simular_notificados(_valores(theta, nombres, fijos), anio, len(obs))
    return np.log1p(sim) - np.log1p(obs)


def busqueda_en_grilla(nombres, fijos, obs, anio, n_mejores=2):
    """Grilla logarítmica gruesa, simulada de forma vectorizada (h = 1 día)."""
    ejes = [np.geomspace(*PARAMETROS[n][0], N_PUNTOS_GRILLA[n]) for n in nombres]
    malla = np.array(list(itertools.product(*ejes)))
    sim, _, _ = simular_notificados({**fijos, **{n: malla[:, i] for i, n in enumerate(nombres)}}, anio, len(obs), h=1.0)
    costo = 0.5 * ((np.log1p(sim) - np.log1p(obs)[:, None]) ** 2).sum(axis=0)
    return malla[np.argsort(costo)[:n_mejores]]


def calibrar(nombres, anio, fijos=None):
    """Grilla + least_squares desde los mejores puntos; devuelve el resultado completo."""
    fijos = {} if fijos is None else fijos
    obs = observado_departamento(anio)
    lim = np.log(np.array([PARAMETROS[n][0] for n in nombres]))
    mejor = None
    for x0 in busqueda_en_grilla(nombres, fijos, obs, anio):
        r = least_squares(residuos, np.log(x0), bounds=(lim[:, 0], lim[:, 1]), args=(nombres, fijos, obs, anio),
                          diff_step=1e-3, max_nfev=150)
        print(f"  partida {np.round(x0, 4)} → costo {r.cost:.3f}, valores {np.round(np.exp(r.x), 4)}")
        if mejor is None or r.cost < mejor.cost:
            mejor = r
    n, k = len(obs), len(mejor.x)
    s2 = 2 * mejor.cost / (n - k)
    cov = np.linalg.pinv(mejor.jac.T @ mejor.jac) * s2
    valores = _valores(mejor.x, nombres, fijos)
    sim, res, p = simular_notificados(valores, anio, n)
    return {
        "anio": int(anio),
        "valores": {n: round(float(v), 6) for n, v in valores.items()},
        "calibrados": nombres,
        "theta_log": mejor.x.round(6).tolist(),
        "covarianza_log": cov.round(8).tolist(),
        "error_estandar_log": np.sqrt(np.diag(cov)).round(6).tolist(),
        "limites": {nm: PARAMETROS[nm][0] for nm in nombres},
        "rmse_log1p": round(float(np.sqrt(np.mean(mejor.fun**2))), 4),
        "rmse_casos": round(float(np.sqrt(sce(obs, sim) / n)), 2),
        "total_observado": float(obs.sum()),
        "total_simulado": round(float(sim.sum()), 1),
        "pico_observado": float(obs.max()), "semana_pico_observado": int(np.argmax(obs) + 1),
        "pico_simulado": round(float(sim.max()), 1), "semana_pico_simulado": int(np.argmax(sim) + 1),
        "tasa_ataque": round(float(res["Y"][-1, ICA] / p["Nh"]), 5),
        "n_semanas": int(n),
    }, obs, sim


def figura(obs, sim, sim3, cal):
    semanas = np.arange(1, len(obs) + 1)
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.bar(semanas, obs, color="#c9c8c2", width=0.8, label="Objetivo: forma nacional escalada al total departamental (estimado)")
    ax.plot(semanas, sim3, color="#eb6834", linewidth=1.5, linestyle="--",
            label=f"Solo ρ, βs, I0 (intento fallido): pico {sim3.max():.0f}, ataque {cal['comparacion_3_parametros']['tasa_ataque']:.0%}")
    ax.plot(semanas, sim, color="#2a78d6", linewidth=2.5,
            label=f"Final: ρ fijo, calibrados βs, I0, ganancia del loop B y lluvia mínima: pico {sim.max():.0f}")
    v = cal["valores"]
    ax.set_title(f"Calibración {cal['anio']}: ρ = {v['rho']:.3f}, βs = {v['beta_s']:.3f}, I0 = {v['I0']:.0f}, "
                 f"g = {v['ganancia_fumigacion']:.3f}, ℓ = {v['lluvia_minima']:.3f}  (RMSE = {cal['rmse_casos']:.0f} casos/semana)",
                 fontsize=9)
    ax.set_xlabel("Semana epidemiológica")
    ax.set_ylabel("Casos notificados por semana")
    ax.set_ylim(0, max(obs.max(), sim.max()) * 1.6)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig("figuras/sd/calibracion.png", dpi=150)
    plt.close(fig)


def correlacion(cov):
    s = np.sqrt(np.diag(cov))
    return (cov / np.outer(s, s)).round(3).tolist()


def main():
    anio = parametro("sd", "anio_base")
    print("Ajuste 1: los 3 parámetros base (ρ, βs, I0):")
    cal3, obs, sim3 = calibrar(BASE, anio)
    print("Ajuste 2: 5 parámetros (+ ganancia_fumigacion, lluvia_minima):")
    cal5, _, _ = calibrar(list(PARAMETROS), anio)
    rho = parametro("observacion", "factor_reporte")
    print(f"Ajuste 3 (final): ρ fijo = {rho} y se calibran {FINAL}:")
    cal, obs, sim = calibrar(FINAL, anio, fijos={"rho": rho})
    cal["rho_fijo"] = {"valor": rho, "fuente": "config/parametros.yaml observacion.factor_reporte (shepard2011; stanaway2016)",
                       "rango": [0.05, 0.5], "motivo": "no identificable con la curva semanal (ver comparacion_5_parametros)"}
    cal["objetivo"] = "casos_semanales.csv sumado por semana: forma nacional escalada al total departamental observado (ESTIMADO)"
    cal["nota"] = ("covarianza_log = (JᵀJ)⁻¹·s² en escala logarítmica de los parámetros, en el orden de 'calibrados'. "
                   "ganancia_fumigacion y lluvia_minima se agregaron porque con solo (ρ, βs, I0) el ajuste es absurdo "
                   "(comparacion_3_parametros); ρ se fija porque no es identificable (comparacion_5_parametros).")
    cal["correlacion_log"] = correlacion(np.array(cal["covarianza_log"]))
    campos = ("valores", "rmse_log1p", "rmse_casos", "total_simulado", "pico_simulado", "semana_pico_simulado", "tasa_ataque")
    cal["comparacion_3_parametros"] = {k: cal3[k] for k in campos}
    cal["comparacion_5_parametros"] = {**{k: cal5[k] for k in campos}, "calibrados": cal5["calibrados"],
                                       "error_estandar_log": cal5["error_estandar_log"],
                                       "correlacion_log": correlacion(np.array(cal5["covarianza_log"]))}
    CALIBRACION.parent.mkdir(parents=True, exist_ok=True)
    CALIBRACION.write_text(json.dumps(cal, indent=2, ensure_ascii=False), encoding="utf-8")
    figura(obs, sim, sim3, cal)
    for nombre, c in [("3 parámetros", cal3), ("5 parámetros", cal5), ("final (ρ fijo)", cal)]:
        print(f"{nombre}: {c['valores']}\n   RMSE = {c['rmse_casos']} casos/semana, total = {c['total_simulado']} "
              f"(obs {c['total_observado']}), pico = {c['pico_simulado']} sem {c['semana_pico_simulado']} "
              f"(obs {c['pico_observado']} sem {c['semana_pico_observado']}), ataque = {c['tasa_ataque']:.3%}, "
              f"EE log = {c['error_estandar_log']}")


if __name__ == "__main__":
    main()
