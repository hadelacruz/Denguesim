"""R9 · Robustez: ¿la conclusión de política se mantiene si los parámetros están mal? → robustez.csv

1. Se muestrean salud.n_muestras_robustez juegos de parámetros inciertos:
   - βs, I0, ganancia_fumigacion y lluvia_minima de la normal multivariada (en log) de
     calibracion.json (Alex, A6), recortada a sus límites;
   - ρ ~ Uniforme(rango) de calibracion.json: ρ se fijó en la calibración porque no es
     identificable con la curva semanal, así que no tiene covarianza (se documenta);
   - uniformes en sus rangos del YAML: tau_notificacion (observacion.retardo_notificacion),
     sd.efecto_fumigacion_preventiva, sd.efecto_criaderos, salud.camas_dengue_por_hospital,
     insumos.alpha e insumos.tau.
2. Para cada muestra se corren TODOS los escenarios con la misma semilla y los mismos
   parámetros (números aleatorios comunes): la epidemia con `simular_escenario` de
   src/sd/escenarios.py (las muestras van juntas en un lote), luego el DES (R4, R5,
   en paralelo con ProcessPoolExecutor) y la cadena de insumos (R6).
3. Métricas (menor es mejor): pico_casos y casos_totales (departamento, casos verdaderos),
   dias_saturacion (días-hospital con cola), espera_media_dias y dias_desabasto (suma de
   hospitales).
4. Comparables: las epidemiológicas entre los 4 escenarios epidemiológicos; las de salud
   entre esos 4 más ampliacion_camas.
5. prob_mejor = fracción de muestras en que el escenario tiene el MENOR valor entre los
   comparables (empates repartidos por igual): suma 1 por métrica.

Salidas: data/processed/robustez.csv (contrato), data/processed/salud/robustez_muestras.csv,
         data/processed/salud/robustez_resumen.md
Uso (desde la raíz):  python src/salud/robustez.py [--rapido]
"""

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/sd")
sys.path.insert(0, "src/salud")
from comun import PROCESSED  # noqa: E402
from comun_salud import DIAS, demanda_hospitalaria, matriz_asignacion, parametro, rango, semilla  # noqa: E402
from des_camas import capacidad, simular_hospital  # noqa: E402
from escenarios import simular_escenario  # noqa: E402
from insumos import dias_desabasto, simular_insumos  # noqa: E402
from metapoblacion import cargar_datos  # noqa: E402
from modelo_seir_sei import CALIBRACION  # noqa: E402
from validacion import muestrear_parametros  # noqa: E402

COLUMNAS = ["escenario", "metrica", "media", "ic_inf", "ic_sup", "prob_mejor"]
EPIDEMIOLOGICOS = ["sin_intervencion", "fumigacion_aleatoria", "fumigacion_hubs", "eliminacion_criaderos"]
SALUD = EPIDEMIOLOGICOS + ["ampliacion_camas"]
METRICAS_EPI = ["pico_casos", "casos_totales"]
METRICAS_SALUD = ["dias_saturacion", "espera_media_dias", "dias_desabasto"]


def muestrear(n, rng):
    """DataFrame con n juegos de parámetros inciertos (uno por fila)."""
    cal = json.loads(CALIBRACION.read_text(encoding="utf-8"))
    m = pd.DataFrame(muestrear_parametros(cal, n, rng))
    uniforme = lambda lo_hi: rng.uniform(lo_hi[0], lo_hi[1], n)  # noqa: E731
    m["rho"] = uniforme(cal["rho_fijo"]["rango"])
    m["tau_notificacion"] = uniforme(rango("observacion", "retardo_notificacion"))
    m["efecto_fumigacion_preventiva"] = uniforme(rango("sd", "efecto_fumigacion_preventiva"))
    m["efecto_criaderos"] = uniforme(rango("sd", "efecto_criaderos"))
    lo, hi = rango("salud", "camas_dengue_por_hospital")
    m["camas"] = rng.integers(lo, hi + 1, n)
    m["alpha"] = uniforme(rango("insumos", "alpha"))
    m["tau_insumos"] = uniforme(rango("insumos", "tau"))
    return m


def epidemia(muestras, semilla_epi, datos):
    """nuevos (escenario → arreglo (n, 17, 365)) con simular_escenario de Alex."""
    claves = ["beta_s", "I0", "ganancia_fumigacion", "lluvia_minima", "rho", "tau_notificacion",
              "efecto_fumigacion_preventiva", "efecto_criaderos"]
    parametros = {k: muestras[k].to_numpy() for k in claves}
    salida = {}
    for esc in EPIDEMIOLOGICOS:
        df = simular_escenario(esc, parametros, semilla_epi, datos)
        salida[esc] = df.nuevos.to_numpy().reshape(len(muestras), len(datos["cods"]), DIAS)
    return salida


def des_muestra(args):
    """DES de todos los hospitales y escenarios de salud para UNA muestra (mismas semillas)."""
    s, demandas, camas, semilla_base = args
    salida = {}
    for esc, D in demandas.items():
        cap = capacidad(esc, camas)
        ocupadas, esperas, saturacion = [], [], 0
        for j in range(D.shape[0]):
            res = simular_hospital(D[j], cap, np.random.default_rng([semilla_base, s, j]))
            ocupadas.append(res["ocupadas"])
            esperas.append(res["esperas"])
            saturacion += res["dias_saturacion"]
        esperas = np.concatenate(esperas)
        salida[esc] = {"ocupadas": np.array(ocupadas), "dias_saturacion": saturacion,
                       "espera_media_dias": float(esperas.mean()) if len(esperas) else 0.0}
    return salida


def prob_mejor(valores):
    """valores (n_muestras, n_escenarios): fracción de muestras en que cada escenario es el
    menor; los empates se reparten por igual."""
    minimo = valores.min(axis=1, keepdims=True)
    ganadores = np.isclose(valores, minimo, rtol=1e-9, atol=1e-9)
    return (ganadores / ganadores.sum(axis=1, keepdims=True)).mean(axis=0)


def tabla_robustez(metricas):
    """metricas: DataFrame largo (muestra, escenario, metrica, valor) → contrato."""
    filas = []
    for m in METRICAS_EPI + METRICAS_SALUD:
        comparables = EPIDEMIOLOGICOS if m in METRICAS_EPI else SALUD
        tabla = metricas[metricas.metrica == m].pivot(index="muestra", columns="escenario", values="valor")[comparables]
        pm = prob_mejor(tabla.to_numpy())
        for esc, p in zip(comparables, pm):
            v = tabla[esc]
            filas.append({"escenario": esc, "metrica": m, "media": round(v.mean(), 4),
                          "ic_inf": round(np.percentile(v, 2.5), 4), "ic_sup": round(np.percentile(v, 97.5), 4),
                          "prob_mejor": round(float(p), 4)})
    return pd.DataFrame(filas)[COLUMNAS]


def escribir_resumen(rob, n):
    lineas = [f"# Robustez de las conclusiones (R9) — {n} juegos de parámetros\n",
              "Cada juego se corrió en todos los escenarios con la misma semilla (números aleatorios comunes).",
              "`prob_mejor` = fracción de juegos en que el escenario tiene el menor valor (menor es mejor).\n",
              "| Métrica | Mejor escenario | prob_mejor | Media (IC 95 %) del mejor | Segundo | prob_mejor |",
              "|---|---|---|---|---|---|"]
    for m, g in rob.groupby("metrica", sort=False):
        g = g.sort_values("prob_mejor", ascending=False)
        a, b = g.iloc[0], g.iloc[1]
        lineas.append(f"| {m} | {a.escenario} | {a.prob_mejor:.2f} | {a.media:.2f} ({a.ic_inf:.2f}–{a.ic_sup:.2f}) "
                      f"| {b.escenario} | {b.prob_mejor:.2f} |")
    lineas += ["", "**Lectura:** si `prob_mejor` del mejor escenario es cercana a 1, la conclusión NO cambia con la",
               "incertidumbre de los parámetros. Si se reparte entre varios escenarios (o hay empates, típico de",
               "`dias_saturacion` cuando casi nunca hay cola), la conclusión depende de los parámetros.",
               "", "**Supuestos:** ρ ~ Uniforme(0.05, 0.5) porque no se calibró; camas por hospital ~ U(10, 60) porque",
               "no hay dato; hospitalizaciones = ρ · nuevos · fraccion_hospitalizada (ver src/salud/comun_salud.py)."]
    (PROCESSED / "salud" / "robustez_resumen.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main(rapido=False):
    n = 10 if rapido else parametro("salud", "n_muestras_robustez")
    base = semilla("robustez")
    muestras = muestrear(n, np.random.default_rng(base))
    datos = cargar_datos()
    nuevos = epidemia(muestras, base, datos)
    nuevos["ampliacion_camas"] = nuevos["sin_intervencion"]          # misma epidemia, más camas
    A, _ = matriz_asignacion(datos["cods"])
    rho = muestras.rho.to_numpy()
    demanda = {esc: demanda_hospitalaria(nuevos[esc], A, rho=rho) for esc in SALUD}    # (n, H, 365)
    tareas = [(s, {esc: demanda[esc][s] for esc in SALUD}, int(muestras.camas[s]), base) for s in range(n)]
    with ProcessPoolExecutor() as ex:
        des = list(ex.map(des_muestra, tareas, chunksize=max(1, n // 32)))

    filas = []
    q = parametro("salud", "insumo_por_paciente_dia")
    for esc in SALUD:
        diario = nuevos[esc].sum(axis=1)                              # (n, 365) departamento
        D = q * np.array([des[s][esc]["ocupadas"] for s in range(n)])  # (n, H, 365)
        I, _, I_obj = simular_insumos(D, alpha=muestras.alpha.to_numpy()[:, None],
                                      tau=muestras.tau_insumos.to_numpy()[:, None])
        desabasto = dias_desabasto(I, I_obj).sum(axis=1)
        for s in range(n):
            valores = {"pico_casos": diario[s].max(), "casos_totales": diario[s].sum(),
                       "dias_saturacion": des[s][esc]["dias_saturacion"],
                       "espera_media_dias": des[s][esc]["espera_media_dias"], "dias_desabasto": desabasto[s]}
            filas += [{"muestra": s, "escenario": esc, "metrica": m, "valor": float(v)} for m, v in valores.items()]
    metricas = pd.DataFrame(filas)
    metricas.merge(muestras.reset_index(names="muestra"), on="muestra").to_csv(
        PROCESSED / "salud" / "robustez_muestras.csv", index=False)
    rob = tabla_robustez(metricas)
    rob.to_csv(PROCESSED / "robustez.csv", index=False)
    escribir_resumen(rob, n)
    print(f"robustez.csv: {len(rob)} filas · {n} muestras")
    print(rob.to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true", help="10 muestras (prueba de humo)")
    main(ap.parse_args().rapido)
