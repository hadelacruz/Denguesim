"""Validación por edad del ABM (N3): ¿se enferma la misma gente que en los datos? (S8: validación de distribución).

Compara la distribución por grupo de edad de los agentes que se infectaron
(S → E) en las corridas de D12 (edades_infectados.csv) con:
  1. los casos OBSERVADOS de Amatitlán (casos_anuales_edad_sexo.csv) en abm.anio;
  2. los casos observados de Amatitlán sumados 2014–2024 (más estables);
  3. la población de Amatitlán por edad (poblacion_edad.csv, año más cercano a abm.anio).

Grupos comunes a las tres fuentes: <1, 1-4, 5-9, 10-14, 15-19, 20-24, 25-39,
40-49, 50-59, 60+.

IC 95 % de la proporción simulada: bootstrap sobre CORRIDAS (se remuestrean
corridas completas con reemplazo y se recalcula la proporción combinada),
B = abm.bootstrap_B. Métricas:
  - índice de disimilitud D = ½·Σ|p_sim − p_obs| (fracción de casos que habría
    que mover de grupo para que coincidan; 0 = idénticas);
  - riesgo relativo por edad = proporción de casos / proporción de población
    (> 1: el grupo se enferma más de lo que pesa en la población);
  - si la proporción observada cae dentro del IC 95 % simulado.

Hallazgo esperado (y no se fuerza): en el ABM la edad no cambia ninguna regla
y el destino (trabajo/estudio) se asigna sin mirar la edad, así que los
infectados deberían repetir la pirámide de población. Si los observados se
concentran en otros grupos, es una limitación del modelo, no de la validación.

Salidas: data/processed/abm/validacion_edad.csv, data/processed/abm/validacion_edad_resumen.json,
figuras/abm/validacion_edad.png
Uso (desde la raíz):  python src/abm/validacion_edad.py   (después de corridas.py)
"""

import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/abm")
from comun import PROCESSED, leer_procesado, parametro  # noqa: E402
from inicializacion import COD_PILOTO, semilla  # noqa: E402

SALIDA = PROCESSED / "abm"
FIGURA = "figuras/abm/validacion_edad.png"
GRUPOS = ["<1", "1-4", "5-9", "10-14", "15-19", "20-24", "25-39", "40-49", "50-59", "60+"]
CORTES = [0, 1, 5, 10, 15, 20, 25, 40, 50, 60, np.inf]
ANIOS_HISTORICOS = (2014, 2024)

# grupo_etario de casos_anuales_edad_sexo.csv → grupo común
GRUPO_CASOS = {"< 1 mes": "<1", "1m a < 2m": "<1", "2m a < 1 año": "<1", "1a a 4 años": "1-4",
               "5a a 9 años": "5-9", "10a a 14 años": "10-14", "15a a 19 años": "15-19",
               "20a a 24 años": "20-24", "25a a 39 años": "25-39", "40a a 49 años": "40-49",
               "50a a 59 años": "50-59", "60a a 64 años": "60+", "65a a 69 años": "60+", "70a+": "60+"}
# grupo_edad de poblacion_edad.csv → grupo común
GRUPO_POBLACION = {"< 1 año": "<1", "1-4": "1-4", "5-9": "5-9", "10-14": "10-14", "15-19": "15-19",
                   "20-24": "20-24", "25-29": "25-39", "30-34": "25-39", "35-39": "25-39",
                   "40-44": "40-49", "45-49": "40-49", "50-54": "50-59", "55-59": "50-59",
                   "60-64": "60+", "65+": "60+"}


def grupo_de_edad(edades):
    """Grupo común de cada edad en años (intervalos [a, b))."""
    return pd.cut(np.asarray(edades, dtype=float), CORTES, right=False, labels=GRUPOS)


def proporciones(conteos):
    """Serie de conteos por grupo → proporciones en el orden de GRUPOS."""
    c = pd.Series(conteos).reindex(GRUPOS, fill_value=0).astype(float)
    return c / c.sum()


def simulado_por_corrida(edades):
    """Matriz (corridas × grupos) con el número de infectados de cada grupo."""
    edades = edades.assign(grupo=grupo_de_edad(edades.edad))
    return edades.groupby(["corrida", "grupo"], observed=False).size().unstack(fill_value=0).reindex(columns=GRUPOS, fill_value=0)


def bootstrap_proporciones(por_corrida, B, rng):
    """IC 95 % de la proporción combinada, remuestreando corridas completas."""
    M = por_corrida.to_numpy(float)
    idx = rng.integers(0, len(M), size=(B, len(M)))
    sumas = M[idx].sum(axis=1)                         # (B, grupos)
    props = sumas / sumas.sum(axis=1, keepdims=True)
    return np.percentile(props, 2.5, axis=0), np.percentile(props, 97.5, axis=0)


def observados(cod, anios):
    c = leer_procesado("casos_anuales_edad_sexo.csv")
    c = c[(c.cod_muni == cod) & c.anio.between(*anios)]
    return c.groupby(c.grupo_etario.map(GRUPO_CASOS)).casos.sum()


def poblacion(cod, anio):
    pe = leer_procesado("poblacion_edad.csv")
    pe = pe[pe.cod_muni == cod]
    anio_usado = pe.anio.unique()[np.argmin(np.abs(pe.anio.unique() - anio))]
    pe = pe[pe.anio == anio_usado]
    return pe.groupby(pe.grupo_edad.map(GRUPO_POBLACION)).poblacion.sum()


def disimilitud(p, q):
    """Índice de disimilitud D = ½·Σ|p − q|."""
    return float(0.5 * np.abs(np.asarray(p) - np.asarray(q)).sum())


def figura(tabla, anio):
    x = np.arange(len(GRUPOS))
    fig, ejes = plt.subplots(1, 2, figsize=(13, 4.3))
    ax = ejes[0]
    ax.bar(x - 0.3, tabla.prop_poblacion, width=0.2, color="#c9c8c2", label="población Amatitlán")
    ax.bar(x - 0.1, tabla.prop_simulada, width=0.2, color="#2a78d6", label="ABM (infectados)")
    ax.errorbar(x - 0.1, tabla.prop_simulada, yerr=[tabla.prop_simulada - tabla.ic_inf, tabla.ic_sup - tabla.prop_simulada],
                fmt="none", ecolor="#0b0b0b", linewidth=1, capsize=2)
    ax.bar(x + 0.1, tabla.prop_observada_anio, width=0.2, color="#eb6834", label=f"casos observados {anio}")
    ax.bar(x + 0.3, tabla.prop_observada_historica, width=0.2, color="#9b5de5",
           label=f"casos observados {ANIOS_HISTORICOS[0]}–{ANIOS_HISTORICOS[1]}")
    ax.set_ylabel("Proporción")
    ax.set_title("Distribución por edad de los infectados (Amatitlán)", fontsize=10)
    ax.legend(frameon=False, fontsize=8)
    ax = ejes[1]
    ax.axhline(1, color="#c9c8c2", linewidth=1)
    ax.plot(x, tabla.riesgo_relativo_simulado, marker="o", color="#2a78d6", label="ABM")
    ax.plot(x, tabla.riesgo_relativo_observado_historico, marker="s", color="#9b5de5",
            label=f"observado {ANIOS_HISTORICOS[0]}–{ANIOS_HISTORICOS[1]}")
    ax.set_ylabel("Riesgo relativo (proporción de casos / de población)")
    ax.set_title("Riesgo relativo por edad", fontsize=10)
    ax.legend(frameon=False, fontsize=8)
    for ax in ejes:
        ax.set_xticks(x, GRUPOS)
        ax.set_xlabel("Grupo de edad (años)")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
        ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(FIGURA, dpi=150)
    plt.close(fig)


def main():
    anio = parametro("abm", "anio")
    edades = pd.read_csv(SALIDA / "edades_infectados.csv")
    por_corrida = simulado_por_corrida(edades)
    rng = np.random.default_rng(semilla("abm", "validacion_edad"))
    ic_inf, ic_sup = bootstrap_proporciones(por_corrida, parametro("abm", "bootstrap_B"), rng)
    tabla = pd.DataFrame({"grupo_edad": GRUPOS,
                          "prop_simulada": proporciones(por_corrida.sum()).to_numpy(),
                          "ic_inf": ic_inf, "ic_sup": ic_sup,
                          "prop_observada_anio": proporciones(observados(COD_PILOTO, (anio, anio))).to_numpy(),
                          "prop_observada_historica": proporciones(observados(COD_PILOTO, ANIOS_HISTORICOS)).to_numpy(),
                          "prop_poblacion": proporciones(poblacion(COD_PILOTO, anio)).to_numpy()})
    tabla["dentro_ic_anio"] = tabla.prop_observada_anio.between(tabla.ic_inf, tabla.ic_sup)
    tabla["dentro_ic_historica"] = tabla.prop_observada_historica.between(tabla.ic_inf, tabla.ic_sup)
    tabla["riesgo_relativo_simulado"] = tabla.prop_simulada / tabla.prop_poblacion
    tabla["riesgo_relativo_observado_historico"] = tabla.prop_observada_historica / tabla.prop_poblacion
    tabla = tabla.round(4)
    tabla.to_csv(SALIDA / "validacion_edad.csv", index=False)
    resumen = {
        "infectados_simulados": int(por_corrida.to_numpy().sum()), "corridas": int(len(por_corrida)),
        "casos_observados_anio": int(observados(COD_PILOTO, (anio, anio)).sum()),
        "casos_observados_historicos": int(observados(COD_PILOTO, ANIOS_HISTORICOS).sum()),
        "D_simulado_vs_observado_anio": round(disimilitud(tabla.prop_simulada, tabla.prop_observada_anio), 4),
        "D_simulado_vs_observado_historico": round(disimilitud(tabla.prop_simulada, tabla.prop_observada_historica), 4),
        "D_simulado_vs_poblacion": round(disimilitud(tabla.prop_simulada, tabla.prop_poblacion), 4),
        "D_observado_historico_vs_poblacion": round(disimilitud(tabla.prop_observada_historica, tabla.prop_poblacion), 4),
        "grupos_dentro_ic_anio": int(tabla.dentro_ic_anio.sum()),
        "grupos_dentro_ic_historica": int(tabla.dentro_ic_historica.sum()),
        "n_grupos": len(GRUPOS),
        "nota": "La edad no entra en ninguna regla del ABM y el destino se asigna sin mirar la edad.",
    }
    (SALIDA / "validacion_edad_resumen.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    figura(tabla, anio)
    print(tabla.to_string(index=False))
    print(json.dumps(resumen, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
