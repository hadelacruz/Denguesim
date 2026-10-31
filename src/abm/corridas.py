"""D12 · Corridas del ABM: calibración de escala_mosquitos, corridas en paralelo,
bootstrap y criterio de paro ("una corrida es una anécdota", S8).

1. Calibración rápida de abm.escala_mosquitos: grilla logarítmica (8 valores ×
   3 corridas, mismas semillas en cada valor) para que la incidencia NOTIFICADA
   simulada (casos × ρ por 100 000 hab.) se acerque a la observada en Amatitlán
   en abm.anio. Como el ABM solo simula semanas 18 a 46, el objetivo es la
   incidencia anual × la fracción de casos que cae en esas semanas según la curva
   semanal nacional observada. El valor se interpola en escala log-log y se
   escribe en config/parametros.yaml (marcado como calibrado).
2. Corridas en paralelo (ProcessPoolExecutor). La corrida m siempre usa la
   semilla int(SeedSequence(abm.base).spawn(max_corridas)[m].generate_state(1)[0]).
3. Por corrida: pico (máximo de casos nuevos diarios), día del pico y tamaño final.
4. Bootstrap no paramétrico (bootstrap_ci, como analysis.py del Laboratorio 4).
5. Criterio de paro: 20 corridas y luego de 10 en 10 hasta que los extremos de
   AMBOS IC (pico y día del pico) cambien < 5 %, o hasta 100. Además M* =
   (z·CV/0.05)² y la curva del error estándar bootstrap contra M.

Salidas (data/processed/abm/): calibracion_escala.csv, corridas.csv, series.csv,
edades_infectados.csv, convergencia_ic.csv, resumen_corridas.json;
figuras/abm/convergencia_ic.png
Uso (desde la raíz):  python src/abm/corridas.py
       (en segundo plano: nohup python src/abm/corridas.py > data/processed/abm/corridas.log 2>&1 &)
"""

import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/abm")
from comun import CONFIG, PROCESSED, leer_procesado, parametro  # noqa: E402
from inicializacion import semilla  # noqa: E402
from modelo import ModeloDengue, factor_reporte  # noqa: E402

SALIDA = PROCESSED / "abm"
FIGURAS = PROCESSED.parents[1] / "figuras" / "abm"
Z = 1.96
TRABAJADORES = min(8, os.cpu_count() or 1)


# ---------------------------------------------------------------- semillas
def semillas_corridas(base, n):
    """Semilla entera de cada corrida, derivada con SeedSequence (siempre la misma para m)."""
    return [int(s.generate_state(1)[0]) for s in np.random.SeedSequence(base).spawn(n)]


# ---------------------------------------------------------------- una corrida
def correr_una(args):
    """Corre el modelo y devuelve (métricas, serie diaria, edades de infectados)."""
    corrida, semilla_m, escala_mosquitos = args
    modelo = ModeloDengue(semilla=semilla_m, escala_mosquitos=escala_mosquitos)
    serie = modelo.correr()
    n = len(modelo.agentes)
    casos = serie.nuevos_casos.to_numpy()
    i = int(np.argmax(casos))
    metricas = {
        "corrida": corrida, "semilla": semilla_m, "escala_mosquitos": escala_mosquitos, "n_agentes": n,
        "pico": int(casos[i]), "dia_pico": int(serie.dia.iloc[i]), "tamano_final": int(casos.sum()),
        "incidencia_notificada_100k": float(casos.sum() / n * modelo.rho * 1e5),
    }
    serie.insert(0, "corrida", corrida)
    edades = pd.DataFrame({"corrida": corrida, "edad": np.round(modelo.edades_infectados, 1)})
    return metricas, serie, edades


def correr_varias(corridas, semillas, escala_mosquitos):
    with ProcessPoolExecutor(max_workers=TRABAJADORES) as ex:
        return list(ex.map(correr_una, [(m, semillas[m], escala_mosquitos) for m in corridas]))


# ---------------------------------------------------------------- bootstrap (Laboratorio 4)
def bootstrap_ci(Y, B, rng, alpha=0.05):
    """Bootstrap no paramétrico de la media: B remuestreos con reemplazo,
    IC por percentiles (2.5, 97.5) y error estándar bootstrap. No asume normalidad."""
    Y = np.asarray(Y, dtype=float)
    medias = np.array([rng.choice(Y, size=len(Y), replace=True).mean() for _ in range(B)])
    return {"media": Y.mean(), "ic_inf": np.percentile(medias, 100 * alpha / 2),
            "ic_sup": np.percentile(medias, 100 * (1 - alpha / 2)), "se": medias.std(ddof=1)}


def bootstrap_se_convergence(Y, B, rng, paso=5):
    """Error estándar bootstrap de la media usando las primeras M corridas, para M creciente."""
    return [(M, bootstrap_ci(Y[:M], B, rng)["se"]) for M in range(paso, len(Y) + 1, paso)]


def corridas_necesarias(Y, error_relativo=0.05):
    """M* = (z·CV / e)²: corridas para que el IC de la media tenga ±5 % de ancho relativo."""
    Y = np.asarray(Y, dtype=float)
    cv = Y.std(ddof=1) / Y.mean()
    return int(np.ceil((Z * cv / error_relativo) ** 2)), float(cv)


# ---------------------------------------------------------------- 1. calibración de escala_mosquitos
def incidencia_objetivo():
    """Incidencia notificada observada de Amatitlán en abm.anio, en la ventana simulada."""
    anio, cod = parametro("abm", "anio"), "0114"
    casos = leer_procesado("casos_anuales_muni.csv").query("anio == @anio and cod_muni == @cod").casos.iloc[0]
    pob = leer_procesado("poblacion_anual.csv").query("anio == @anio and cod_muni == @cod").poblacion.iloc[0]
    nac = leer_procesado("casos_semanales_nacional.csv").query("anio == @anio").set_index("semana_epi").casos
    s0 = parametro("abm", "semana_inicio")
    s1 = s0 + (parametro("abm", "dias_simulacion") - 1) // 7
    fraccion = nac.loc[s0:s1].sum() / nac.sum()
    anual = casos / pob * 1e5
    return anual * fraccion, anual, fraccion


def calibrar_escala_mosquitos():
    objetivo, anual, fraccion = incidencia_objetivo()
    escalas = np.geomspace(0.5, 5.0, 8)
    semillas = semillas_corridas(semilla("abm", "calibracion"), 3)
    filas = []
    for e in escalas:
        for metricas, _, _ in correr_varias(range(3), semillas, float(e)):
            filas.append(metricas)
    tabla = pd.DataFrame(filas)
    medias = tabla.groupby("escala_mosquitos").incidencia_notificada_100k.mean()
    # Interpolación log-log entre los dos valores que encierran al objetivo.
    x, y = np.log(medias.index.to_numpy()), np.log(np.maximum(medias.to_numpy(), 1e-3))
    arriba = np.nonzero(y >= np.log(objetivo))[0]
    if len(arriba) and arriba[0] > 0:
        k = arriba[0]
        elegido = float(np.exp(np.interp(np.log(objetivo), [y[k - 1], y[k]], [x[k - 1], x[k]])))
    else:
        elegido = float(medias.index[np.argmin(np.abs(y - np.log(objetivo)))])
    tabla["objetivo_100k"] = objetivo
    tabla.to_csv(SALIDA / "calibracion_escala.csv", index=False)
    print(f"Objetivo: {objetivo:.0f} notificados por 100 000 en la ventana ({anual:.0f} anual × {fraccion:.3f})")
    print(medias.round(1).to_string())
    print(f"escala_mosquitos elegida = {elegido:.4f}")
    return round(elegido, 4)


def escribir_escala_en_yaml(valor):
    """Escribe abm.escala_mosquitos en config/parametros.yaml (solo esa clave)."""
    ruta = CONFIG / "parametros.yaml"
    texto = ruta.read_text(encoding="utf-8")
    patron = re.compile(r"(  escala_mosquitos:\n    valor: )[^\n]*")
    texto, n = patron.subn(rf"\g<1>{valor}   # calibrado en src/abm/corridas.py (D12)", texto, count=1)
    if n != 1:
        raise RuntimeError("no se encontró abm.escala_mosquitos en parametros.yaml")
    ruta.write_text(texto, encoding="utf-8")


# ---------------------------------------------------------------- 2–5. corridas con criterio de paro
def correr_con_criterio_de_paro(escala_mosquitos):
    B, tol = parametro("abm", "bootstrap_B"), parametro("abm", "tolerancia_ic")
    m0, dm, m_max = (parametro("abm", k) for k in ("corridas_iniciales", "corridas_incremento", "max_corridas"))
    semillas = semillas_corridas(semilla("abm", "base"), m_max)
    rng = np.random.default_rng(semilla("abm", "bootstrap"))
    resultados, convergencia, previo = [], [], None
    M = m0
    while True:
        resultados += correr_varias(range(len(resultados), M), semillas, escala_mosquitos)
        met = pd.DataFrame([r[0] for r in resultados])
        actual = {k: bootstrap_ci(met[k], B, rng) for k in ("pico", "dia_pico")}
        cambios = {}
        for k, ic in actual.items():
            cambio = np.nan if previo is None else max(abs(ic[e] - previo[k][e]) / abs(previo[k][e]) for e in ("ic_inf", "ic_sup"))
            cambios[k] = cambio
            convergencia.append({"M": M, "metrica": k, **{c: round(v, 4) for c, v in ic.items()}, "cambio_relativo_extremos": cambio})
        print(f"M = {M:3d}: pico IC [{actual['pico']['ic_inf']:.1f}, {actual['pico']['ic_sup']:.1f}], "
              f"día pico IC [{actual['dia_pico']['ic_inf']:.1f}, {actual['dia_pico']['ic_sup']:.1f}], cambios {cambios}")
        convergio = previo is not None and all(c < tol for c in cambios.values())
        if convergio or M >= m_max:
            break
        previo, M = actual, min(M + dm, m_max)
    return resultados, pd.DataFrame(convergencia), convergio


def figura_convergencia(met, rng, B):
    fig, ejes = plt.subplots(1, 2, figsize=(10, 3.8))
    for ax, k, unidad in zip(ejes, ("pico", "dia_pico"), ("casos/día (agentes)", "días")):
        curva = bootstrap_se_convergence(met[k].to_numpy(), B, rng)
        ax.plot(*zip(*curva), marker="o", markersize=4, color="#2a78d6", linewidth=2)
        ax.set_xlabel("Número de corridas M")
        ax.set_ylabel(f"Error estándar bootstrap ({unidad})")
        ax.set_title(f"{'Pico' if k == 'pico' else 'Día del pico'}: error estándar bootstrap de la media contra M", fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(color="#e6e5e0", linewidth=0.6)
    fig.tight_layout()
    fig.savefig(FIGURAS / "convergencia_ic.png", dpi=150)
    plt.close(fig)


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    FIGURAS.mkdir(parents=True, exist_ok=True)
    escala = parametro("abm", "escala_mosquitos")
    if escala is None or "--recalibrar" in sys.argv:
        escala = calibrar_escala_mosquitos()
        escribir_escala_en_yaml(escala)
    print(f"Corridas con escala_mosquitos = {escala} y ρ = {factor_reporte()}")
    resultados, convergencia, convergio = correr_con_criterio_de_paro(escala)
    met = pd.DataFrame([r[0] for r in resultados])
    met.to_csv(SALIDA / "corridas.csv", index=False)
    pd.concat([r[1] for r in resultados]).to_csv(SALIDA / "series.csv", index=False)
    pd.concat([r[2] for r in resultados]).to_csv(SALIDA / "edades_infectados.csv", index=False)
    convergencia.to_csv(SALIDA / "convergencia_ic.csv", index=False)
    B = parametro("abm", "bootstrap_B")
    rng = np.random.default_rng(semilla("abm", "bootstrap"))
    figura_convergencia(met, rng, B)
    resumen = {"escala_mosquitos": escala, "rho": factor_reporte(), "M_final": int(len(met)), "convergio": bool(convergio)}
    for k in ("pico", "dia_pico", "tamano_final", "incidencia_notificada_100k"):
        ic = bootstrap_ci(met[k], B, rng)
        m_estrella, cv = corridas_necesarias(met[k])
        resumen[k] = {**{c: round(float(v), 3) for c, v in ic.items()}, "cv": round(cv, 4), "M_estrella": m_estrella}
    resumen["incidencia_objetivo_100k"] = round(float(incidencia_objetivo()[0]), 1)
    resumen["corridas_con_brote"] = int((met.tamano_final > parametro("abm", "infectados_iniciales")).sum())
    (SALIDA / "resumen_corridas.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(resumen, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
