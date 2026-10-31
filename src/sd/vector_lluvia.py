"""A2 · Reclutamiento de mosquitos Λ(t) con retardo de tercer orden (Sterman, 2000).

La lluvia crea criaderos; los adultos aparecen después del desarrollo
huevo → larva → pupa → adulto. Cada etapa es un stock con tiempo de residencia τ/3:

    entrada(t) = k · (lluvia_minima + lluvia_rel(t))          [mosquitos/día]
    dX1/dt = entrada(t) − X1/(τ/3)                            [mosquitos/día]
    dX2/dt = X1/(τ/3)   − X2/(τ/3)
    dX3/dt = X2/(τ/3)   − X3/(τ/3)
    Λ(t)   = X3/(τ/3)                                         [mosquitos/día]

Escala: k = m_base · μ · Nh / (1 + lluvia_minima). En temporada lluviosa la
media de lluvia_rel es ≈ 1, así que en equilibrio Nv = Λ/μ ≈ m_base · Nh.

lluvia_rel (lluvia ÷ media de mayo–octubre del municipio) se usa en lugar de
lluvia_mm por el sesgo de nivel del reanálisis ERA5. Es semanal y se toma
constante dentro de cada semana.

Uso (desde la raíz):  python src/sd/vector_lluvia.py   → figuras/sd/lluvia_vs_lambda.png
"""

import sys

import numpy as np

sys.path.insert(0, "src/datos")
from comun import leer_procesado, parametro  # noqa: E402


def lluvia_semanal(anio, cods=None):
    """Matriz (semanas, municipios) de lluvia_rel del año y la lista de cod_muni."""
    c = leer_procesado("clima_semanal.csv")
    c = c[c.anio == anio].pivot(index="semana_epi", columns="cod_muni", values="lluvia_rel").sort_index()
    if cods is not None:
        c = c[list(cods)]
    return c.to_numpy(float), list(c.columns)


def poblacion_anio(anio, cods=None):
    """Población por municipio del año (poblacion_anual.csv), en el orden de cods."""
    p = leer_procesado("poblacion_anual.csv")
    p = p[p.anio == anio].set_index("cod_muni")["poblacion"]
    return p.loc[list(cods)].to_numpy(float) if cods is not None else p


def lluvia_departamento(anio):
    """lluvia_rel del departamento: promedio de los 17 municipios ponderado por población."""
    lluvia, cods = lluvia_semanal(anio)
    pob = poblacion_anio(anio, cods)
    return lluvia @ pob / pob.sum()


def lluvia_en(t, p):
    """lluvia_rel en el día t (constante dentro de la semana epidemiológica).

    Si el integrador fijó "semana_del_paso", se usa esa semana en las cuatro etapas
    de RK4: así el forzamiento es suave dentro de cada paso (ver integrar())."""
    semana = p.get("semana_del_paso")
    semana = int(t // 7) if semana is None else semana
    semana = min(semana, len(p["lluvia"]) - 1)
    return p["lluvia"][semana]


def escala_k(p):
    """k = m_base · μ · Nh / (1 + lluvia_minima)   [mosquitos/día por unidad de lluvia_rel]."""
    return p["m_base"] * p["mu"] * p["Nh"] / (1.0 + p["lluvia_minima"])


def entrada_huevos(t, p):
    """entrada(t) = k · (lluvia_minima + lluvia_rel(t)), con el factor de criaderos del escenario."""
    return p["k"] * p.get("factor_criaderos", 1.0) * (p["lluvia_minima"] + lluvia_en(t, p))


def derivadas_criaderos(t, X1, X2, X3, p):
    """Retardo de tercer orden. Devuelve (dX1, dX2, dX3, Λ)."""
    r = p["tau_desarrollo"] / 3.0                      # días en cada etapa
    entrada = entrada_huevos(t, p)
    dX1 = entrada - X1 / r                             # huevos/día
    dX2 = X1 / r - X2 / r                              # larvas/día
    dX3 = X2 / r - X3 / r                              # pupas/día
    return dX1, dX2, dX3, X3 / r                       # Λ = adultos que emergen/día


def criaderos_en_equilibrio(p):
    """Condición inicial: cada etapa en equilibrio con la lluvia de la primera semana."""
    x = p["tau_desarrollo"] / 3.0 * entrada_huevos(0.0, p)
    return x, x, x


def figura_lluvia_vs_lambda():
    """Dibuja lluvia_rel contra Λ(t)/k para ver el retardo de desarrollo."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sys.path.insert(0, "src/sd")
    from modelo_seir_sei import IX3, parametros_departamento, simular_seir_sei

    p = parametros_departamento()
    res = simular_seir_sei(p, dias=364, expuestos_iniciales=0.0)
    t = res["t"]
    lam = res["Y"][:, IX3] / (p["tau_desarrollo"] / 3.0)
    entrada = np.array([p["lluvia_minima"] + lluvia_en(ti, p) for ti in t])
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.step(t, entrada, where="post", color="#8a8984", linewidth=1.2, label="lluvia_minima + lluvia_rel(t) (entrada)")
    ax.plot(t, lam / p["k"], color="#2a78d6", linewidth=2, label="Λ(t) / k (adultos que emergen, retardo de 3er orden)")
    ax.set_xlabel(f"Día del año {parametro('sd', 'anio_base')}")
    ax.set_ylabel("Relativo a la temporada lluviosa")
    ax.set_title(f"Lluvia y reclutamiento de mosquitos: τ = {p['tau_desarrollo']:.0f} días suaviza y retrasa la señal", fontsize=10)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
    fig.tight_layout()
    fig.savefig("figuras/sd/lluvia_vs_lambda.png", dpi=150)
    plt.close(fig)
    desfase = np.argmax(np.correlate(lam / lam.mean() - 1, entrada / entrada.mean() - 1, "full")) - (len(t) - 1)
    print(f"Retardo que maximiza la correlación entre entrada y Λ: {desfase} días (τ = {p['tau_desarrollo']} días)")


if __name__ == "__main__":
    figura_lluvia_vs_lambda()
