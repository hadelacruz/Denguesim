"""A7 · Validación con bandas IC 95 % (criterio cuantitativo de S6).

1. Se muestrean n juegos de parámetros de la normal multivariada de la
   calibración en escala logarítmica, θ ~ N(θ̂, Σ), recortados a sus límites.
2. Se simulan TODOS a la vez (el modelo acepta arreglos de parámetros).
3. Dos bandas de percentiles 2.5–97.5 de los casos notificados semanales:
     banda 1: solo incertidumbre de parámetros
     banda 2: parámetros + ruido de observación de Poisson, y ~ Poisson(simulado)
4. Se reporta el % de semanas observadas que cae dentro de cada banda.

Recordatorio: lo "observado" semanal es un estimado (forma nacional escalada al
total departamental), así que la validación semanal mide sobre todo la forma.

Salidas: data/processed/sd/validacion.csv, data/processed/sd/validacion_resumen.json,
         figuras/sd/validacion_ic95.png
Uso (desde la raíz):  python src/sd/validacion.py
"""

import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/sd")
from calibracion import observado_departamento, simular_notificados  # noqa: E402
from comun import CONFIG, PROCESSED, parametro  # noqa: E402
from modelo_seir_sei import CALIBRACION  # noqa: E402


def semilla(seccion, clave):
    """Semilla desde config/semillas.yaml."""
    with open(CONFIG / "semillas.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)[seccion][clave]


def muestrear_parametros(cal, n, rng):
    """n juegos de parámetros de N(θ̂, Σ) en escala log, recortados a los límites."""
    nombres = cal["calibrados"]
    theta = rng.multivariate_normal(cal["theta_log"], cal["covarianza_log"], size=n, method="svd")
    lim = np.log(np.array([cal["limites"][nm] for nm in nombres]))
    theta = np.clip(theta, lim[:, 0], lim[:, 1])
    return {nm: np.exp(theta[:, i]) for i, nm in enumerate(nombres)}


def bandas(cal, n, rng):
    """Simula n juegos y devuelve (simulado sin ruido, con ruido de Poisson), forma (semanas, n)."""
    muestras = muestrear_parametros(cal, n, rng)
    sim, _, _ = simular_notificados(muestras, cal["anio"], cal["n_semanas"])
    con_ruido = rng.poisson(np.clip(sim, 0, None))
    return sim, con_ruido, muestras


def tabla_validacion(obs, sim, con_ruido):
    q = lambda x, a: np.percentile(x, a, axis=1)  # noqa: E731
    df = pd.DataFrame({
        "semana_epi": np.arange(1, len(obs) + 1),
        "observado": obs,
        "mediana": q(sim, 50),
        "ic_inf_parametros": q(sim, 2.5), "ic_sup_parametros": q(sim, 97.5),
        "ic_inf_poisson": q(con_ruido, 2.5), "ic_sup_poisson": q(con_ruido, 97.5),
    })
    df["dentro_parametros"] = df.observado.between(df.ic_inf_parametros, df.ic_sup_parametros)
    df["dentro_poisson"] = df.observado.between(df.ic_inf_poisson, df.ic_sup_poisson)
    return df


def figura(df, anio):
    fig, ax = plt.subplots(figsize=(10, 4.2))
    s = df.semana_epi
    ax.fill_between(s, df.ic_inf_poisson, df.ic_sup_poisson, color="#2a78d6", alpha=0.15, linewidth=0,
                    label=f"IC 95 % parámetros + Poisson ({df.dentro_poisson.mean():.0%} de semanas dentro)")
    ax.fill_between(s, df.ic_inf_parametros, df.ic_sup_parametros, color="#2a78d6", alpha=0.35, linewidth=0,
                    label=f"IC 95 % solo parámetros ({df.dentro_parametros.mean():.0%} de semanas dentro)")
    ax.plot(s, df.mediana, color="#2a78d6", linewidth=2, label="Mediana simulada")
    ax.scatter(s, df.observado, color="#0b0b0b", s=12, zorder=3, label="Objetivo (estimado: forma nacional × total departamental)")
    ax.set_xlabel("Semana epidemiológica")
    ax.set_ylabel("Casos notificados por semana")
    ax.set_title(f"Validación {anio}: bandas IC 95 % de casos notificados (departamento de Guatemala)", fontsize=10)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
    fig.tight_layout()
    fig.savefig("figuras/sd/validacion_ic95.png", dpi=150)
    plt.close(fig)


def main():
    cal = json.loads(CALIBRACION.read_text(encoding="utf-8"))
    rng = np.random.default_rng(semilla("sd", "validacion"))
    obs = observado_departamento(cal["anio"])
    sim, con_ruido, _ = bandas(cal, parametro("sd", "n_muestras_validacion"), rng)
    df = tabla_validacion(obs, sim, con_ruido)
    df.round(2).to_csv(PROCESSED / "sd" / "validacion.csv", index=False)
    total = sim.sum(axis=0)
    resumen = {
        "anio": cal["anio"],
        "n_muestras": int(sim.shape[1]),
        "pct_semanas_dentro_parametros": round(float(df.dentro_parametros.mean()), 4),
        "pct_semanas_dentro_poisson": round(float(df.dentro_poisson.mean()), 4),
        "total_anual_observado": float(obs.sum()),
        "total_anual_simulado_mediana": round(float(np.median(total)), 1),
        "total_anual_simulado_ic95": [round(float(np.percentile(total, 2.5)), 1), round(float(np.percentile(total, 97.5)), 1)],
    }
    (PROCESSED / "sd" / "validacion_resumen.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    figura(df, cal["anio"])
    print(json.dumps(resumen, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
