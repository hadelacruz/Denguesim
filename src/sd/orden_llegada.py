"""A12 (N3) · Orden de llegada de la temporada por área de salud: observado contra simulado.

Observado: actividad_semanal_area_salud.csv trae la zona del corredor endémico
del MSPAS por área de salud y semana (4 = brote: casos por encima del
cuartil 3 histórico). Se toman las 4 áreas del departamento de Guatemala.

Simulado: la metapoblación (A10) con la lluvia y la población de cada año y los
m_i del año base. Los casos notificados semanales de los municipios se suman por
area_salud (poblacion.csv) y se arma un corredor endémico SIMULADO con la misma
regla del MSPAS: para cada área y semana, el cuartil 3 de los años simulados
2017–2025 (dejando fuera el año evaluado). "Brote" = semana por encima de ese Q3.

Llegada = primera semana de una racha de sd.semanas_brote_sostenido semanas
seguidas en brote (supuesto: con 1 sola semana, el corredor observado marca
llegadas espurias en la época seca, cuando los casos son pocos y ruidosos).
Si un área nunca llega, queda CENSURADA en (última semana + 1).

Comparación: Spearman entre el orden observado y el simulado (p exacta por
permutación, no la aproximación t, que con n = 4 no vale) en 2019, 2023 y
2026 (los años de la tabla con clima disponible; 2026 solo hasta la semana 40
de clima y la 34 de corredor). Con 4 áreas el resultado es débil: aun una
correlación perfecta tiene p exacta bilateral = 2/24 ≈ 0.083 (no significativa al 5 %).

Salidas: data/processed/sd/orden_llegada.csv, data/processed/sd/orden_llegada_resumen.csv,
figuras/sd/orden_llegada.png
Uso (desde la raíz):  python src/sd/orden_llegada.py
"""

import itertools
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/sd")
from comun import PROCESSED, leer_procesado, parametro  # noqa: E402
from metapoblacion import cargar_datos, simular_metapoblacion  # noqa: E402
from modelo_seir_sei import ICA  # noqa: E402

SALIDA = PROCESSED / "sd"
FIGURA = "figuras/sd/orden_llegada.png"
ANIOS_EVALUADOS = [2019, 2023, 2026]
ANIOS_CORREDOR = list(range(2017, 2026))
NIVEL_BROTE = 4
MAX_SEMANAS = 52
P_EXACTA_N4 = 2 / 24          # P(|ρ| = 1) con 4 unidades, bilateral, bajo H0


# ------------------------------------------------------------------ regla de llegada
def primera_racha(en_brote, largo):
    """Semana (1, 2, ...) en que empieza la primera racha de `largo` semanas seguidas en True; None si no hay."""
    seguidas = 0
    for i, b in enumerate(en_brote):
        seguidas = seguidas + 1 if b else 0
        if seguidas == largo:
            return i - largo + 2
    return None


def llegadas(en_brote_por_area, largo, n_semanas):
    """Semana de llegada por área; las que no llegan quedan censuradas en n_semanas + 1."""
    filas = []
    for area, serie in en_brote_por_area.items():
        semana = primera_racha(list(serie), largo)
        filas.append({"area_salud": area, "semana_llegada": semana if semana is not None else n_semanas + 1,
                      "censurado": semana is None})
    return pd.DataFrame(filas)


# ------------------------------------------------------------------ observado
def areas_departamento():
    """area_salud de cada cod_muni (las 4 áreas del departamento de Guatemala)."""
    return leer_procesado("poblacion.csv").set_index("cod_muni").area_salud


def brote_observado(anio, areas):
    a = leer_procesado("actividad_semanal_area_salud.csv")
    a = a[(a.anio == anio) & a.area_salud.isin(areas)]
    tabla = a.pivot(index="semana_epi", columns="area_salud", values="nivel").sort_index()
    return {area: tabla[area] == NIVEL_BROTE for area in areas}, len(tabla)


# ------------------------------------------------------------------ simulado
def notificados_semanales_por_area(anio, area_de):
    """Casos notificados semanales simulados, sumados por área de salud: DataFrame (semanas × áreas)."""
    datos = cargar_datos(anio)
    n_semanas = min(len(datos["lluvia"]), MAX_SEMANAS)
    datos["lluvia"] = datos["lluvia"][:n_semanas]
    res = simular_metapoblacion(datos, dias=7 * n_semanas)
    acum = res["Y"][::7, :, ICA]                                     # (semanas+1, 17)
    semanal = res["p"]["rho"] * np.diff(acum, axis=0)
    df = pd.DataFrame(semanal, columns=datos["cods"], index=np.arange(1, n_semanas + 1))
    return df.T.groupby(area_de.loc[datos["cods"]].to_numpy()).sum().T


def brote_simulado(anio, simulados):
    """Brote simulado: semana por encima del Q3 de los demás años simulados (corredor endémico simulado)."""
    otros = [simulados[a] for a in ANIOS_CORREDOR if a != anio]
    q3 = pd.concat(otros).groupby(level=0).quantile(0.75)
    actual = simulados[anio]
    q3 = q3.loc[actual.index]
    return {area: actual[area] > q3[area] for area in actual.columns}, len(actual)


# ------------------------------------------------------------------ comparación
def comparar(anio, simulados, areas, largo):
    obs_brote, n_obs = brote_observado(anio, areas)
    sim_brote, n_sim = brote_simulado(anio, simulados)
    obs = llegadas(obs_brote, largo, n_obs).add_suffix("_obs").rename(columns={"area_salud_obs": "area_salud"})
    sim = llegadas(sim_brote, largo, n_sim).add_suffix("_sim").rename(columns={"area_salud_sim": "area_salud"})
    tabla = obs.merge(sim, on="area_salud")
    tabla.insert(0, "anio", anio)
    tabla["orden_obs"] = tabla.semana_llegada_obs.rank(method="average")
    tabla["orden_sim"] = tabla.semana_llegada_sim.rank(method="average")
    return tabla


def spearman(tabla):
    """ρ de Spearman y p EXACTA por permutación; NaN si una serie no tiene variación."""
    if tabla.semana_llegada_obs.nunique() < 2 or tabla.semana_llegada_sim.nunique() < 2:
        return np.nan, np.nan
    obs, sim = tabla.semana_llegada_obs.to_numpy(), tabla.semana_llegada_sim.to_numpy()
    r = float(spearmanr(obs, sim).statistic)
    return r, p_permutacion([obs], [sim], r)


def p_permutacion(obs_por_anio, sim_por_anio, r_obs):
    """p exacta bilateral: fracción de permutaciones (dentro de cada año) con |ρ| ≥ |ρ observado|.
    Con 4 áreas hay 24 permutaciones por año; con 3 años juntos, 24³ = 13 824."""
    obs = np.concatenate([pd.Series(o).rank().to_numpy() for o in obs_por_anio])
    perms = [list(itertools.permutations(pd.Series(s).rank().to_numpy())) for s in sim_por_anio]
    extremos = total = 0
    for combinacion in itertools.product(*perms):
        r = spearmanr(obs, np.concatenate(combinacion)).statistic
        extremos += abs(r) >= abs(r_obs) - 1e-12
        total += 1
    return extremos / total


def figura(tabla):
    anios = sorted(tabla.anio.unique())
    fig, ejes = plt.subplots(1, len(anios), figsize=(5 * len(anios), 4), sharey=True)
    for ax, anio in zip(ejes, anios):
        sub = tabla[tabla.anio == anio]
        for _, f in sub.iterrows():
            marca = "o" if not (f.censurado_obs or f.censurado_sim) else "s"
            ax.scatter(f.semana_llegada_obs, f.semana_llegada_sim, s=60, marker=marca, color="#2a78d6")
            ax.annotate(f.area_salud.replace("GUATEMALA ", ""), (f.semana_llegada_obs, f.semana_llegada_sim),
                        fontsize=8, xytext=(4, 4), textcoords="offset points")
        lim = [0, 54]
        ax.plot(lim, lim, color="#c9c8c2", linewidth=1, linestyle="--")
        r, _ = spearman(sub)
        ax.set_title(f"{anio}: Spearman ρ = {r:.2f}" if np.isfinite(r) else f"{anio}: ρ indefinida", fontsize=10)
        ax.set_xlabel("Semana de llegada observada")
        ax.spines[["top", "right"]].set_visible(False)
    ejes[0].set_ylabel("Semana de llegada simulada")
    fig.suptitle("Llegada de la temporada (racha de brote) por área de salud · cuadrado = censurado", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGURA, dpi=150)
    plt.close(fig)


def main():
    largo = int(parametro("sd", "semanas_brote_sostenido"))
    area_de = areas_departamento()
    areas = sorted(area_de.unique())
    simulados = {anio: notificados_semanales_por_area(anio, area_de) for anio in sorted(set(ANIOS_CORREDOR) | set(ANIOS_EVALUADOS))}
    tabla = pd.concat([comparar(anio, simulados, areas, largo) for anio in ANIOS_EVALUADOS], ignore_index=True)
    tabla.to_csv(SALIDA / "orden_llegada.csv", index=False)
    resumen = []
    for anio in ANIOS_EVALUADOS:
        r, p = spearman(tabla[tabla.anio == anio])
        resumen.append({"anio": anio, "spearman": r, "p_exacta": p, "n_areas": len(areas),
                        "p_minima_posible": round(P_EXACTA_N4, 4)})
    # Todos los años juntos: orden dentro de cada año (12 pares), permutando dentro de cada año.
    r_all = float(spearmanr(tabla.orden_obs, tabla.orden_sim).statistic)
    grupos = [g for _, g in tabla.groupby("anio")]
    p_all = p_permutacion([g.orden_obs for g in grupos], [g.orden_sim for g in grupos], r_all)
    resumen.append({"anio": "todos", "spearman": r_all, "p_exacta": p_all, "n_areas": len(tabla),
                    "p_minima_posible": round(2 / 24 ** 3, 6)})
    resumen = pd.DataFrame(resumen).round(4)
    resumen.to_csv(SALIDA / "orden_llegada_resumen.csv", index=False)
    figura(tabla)
    print(tabla.to_string(index=False))
    print(resumen.to_string(index=False))


if __name__ == "__main__":
    main()
