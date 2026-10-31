"""R4 + R5 · Simulación de eventos discretos (SimPy) de las camas de dengue → ocupacion_camas.csv.

Un hospital a la vez:
- LLEGADAS: proceso de Poisson no homogéneo con tasa constante por día (la suma de las
  hospitalizaciones esperadas de los municipios que le tocan, comun_salud.py). Los
  tiempos entre llegadas salen de `exponencial` (R1). Por la falta de memoria de la
  exponencial, al terminar un día se vuelve a sortear con la tasa del día siguiente;
  si la tasa del día es 0, se salta al día siguiente.
- ESTANCIA: `estancia_aceptacion_rechazo` (R1), Weibull con k = salud.weibull_k.
- CAMAS: simpy.Resource(capacity=camas). Cada paciente es un proceso:
      with cama.request() as req: yield req; yield env.timeout(estancia)
  La espera es el tiempo entre llegar y obtener cama.
- MONITOR: al final de cada día registra ocupadas = cama.count y en_cola = len(cama.queue).

Escenarios: los cinco de Alex más `ampliacion_camas` (R5): la demanda de
`linea_base_camas` con capacidad × (1 + salud.ampliacion_camas_pct/100).
Números aleatorios comunes: la réplica r del hospital j usa default_rng([semilla, r, j])
en TODOS los escenarios y capacidades, así las comparaciones son pareadas.

Salidas:
  data/processed/ocupacion_camas.csv              (contrato; réplica 0)
  data/processed/salud/metricas_des.csv           (media e IC 95 % entre réplicas)
  data/processed/salud/comparacion_ampliacion.csv (R5, bootstrap pareado)
  data/processed/salud/saturacion_vs_capacidad.csv y figuras/salud/saturacion_vs_capacidad.png
  data/processed/salud/asignacion_hospitales.csv
Uso (desde la raíz):  python src/salud/des_camas.py [--rapido]
"""

import argparse
import sys
from concurrent.futures import ProcessPoolExecutor

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import simpy  # noqa: E402

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/salud")
from comun import PROCESSED  # noqa: E402
from comun_salud import (DIAS, ESCENARIOS_DES, bootstrap_ci, bootstrap_pareado, demanda_hospitalaria,  # noqa: E402
                         matriz_asignacion, nuevos_por_escenario, parametro, rango, semilla,
                         tabla_asignacion)
from generadores import estancia_aceptacion_rechazo, exponencial  # noqa: E402

COLUMNAS = ["escenario", "id_hosp", "dia", "ocupadas", "en_cola"]
METRICAS = ["ocupacion_max", "espera_media_dias", "espera_p95_dias", "dias_saturacion"]


class FuenteEstancias:
    """Entrega estancias Weibull de una en una, generándolas por lotes (más rápido)."""

    def __init__(self, rng, lote=256):
        self.rng, self.lote, self.buffer = rng, lote, np.empty(0)
        # Se leen una sola vez (parametro() abre el YAML en cada llamada).
        self.media, self.k = parametro("salud", "estancia_media"), parametro("salud", "weibull_k")

    def siguiente(self):
        if len(self.buffer) == 0:
            self.buffer = estancia_aceptacion_rechazo(self.lote, self.rng, self.media, self.k)
        valor, self.buffer = self.buffer[0], self.buffer[1:]
        return float(valor)


def simular_hospital(tasas, camas, rng):
    """DES de un hospital. tasas: llegadas esperadas por día (largo = días simulados)."""
    dias = len(tasas)
    env = simpy.Environment()
    cama = simpy.Resource(env, capacity=int(camas))
    estancias = FuenteEstancias(rng)
    reg = {"llegadas": 0, "altas": 0, "esperas": []}
    ocupadas, en_cola = np.zeros(dias, dtype=int), np.zeros(dias, dtype=int)

    def paciente(env):
        llegada = env.now
        with cama.request() as req:
            yield req
            reg["esperas"].append(env.now - llegada)           # días esperando cama
            yield env.timeout(estancias.siguiente())
        reg["altas"] += 1

    def llegadas(env):
        for d in range(dias):
            lam = tasas[d]                                     # pacientes / día
            t = float(d)
            while lam > 0:
                t += exponencial(lam, 1, rng)[0]               # tiempo entre llegadas (R1)
                if t >= d + 1:
                    break
                yield env.timeout(t - env.now)
                reg["llegadas"] += 1
                env.process(paciente(env))
            yield env.timeout(d + 1 - env.now)

    def monitor(env):
        for d in range(dias):
            yield env.timeout(1)                               # fin del día d
            ocupadas[d], en_cola[d] = cama.count, len(cama.queue)

    env.process(llegadas(env))
    env.process(monitor(env))
    env.run(until=dias)
    esperas = np.array(reg["esperas"])
    return {
        "ocupadas": ocupadas, "en_cola": en_cola, "llegadas": reg["llegadas"], "altas": reg["altas"],
        "presentes": cama.count + len(cama.queue), "esperas": esperas,
        "ocupacion_max": int(ocupadas.max()),
        "espera_media_dias": float(esperas.mean()) if len(esperas) else 0.0,
        "espera_p95_dias": float(np.percentile(esperas, 95)) if len(esperas) else 0.0,
        "dias_saturacion": int((en_cola > 0).sum()),
    }


def verificar_conservacion(res):
    """llegadas = altas + pacientes presentes al final (en cama o en cola)."""
    return res["llegadas"] == res["altas"] + res["presentes"]


def correr_escenario(tasas_H, camas, replicas, semilla_base):
    """Todas las réplicas de todos los hospitales de un escenario.

    Devuelve (serie de la réplica 0 por hospital, métricas por réplica y hospital,
    totales del departamento por réplica)."""
    H = tasas_H.shape[0]
    serie0, filas, totales = [], [], []
    for r in range(replicas):
        esperas_dep, sat_dep = [], 0
        for j in range(H):
            res = simular_hospital(tasas_H[j], camas, np.random.default_rng([semilla_base, r, j]))
            if r == 0:
                serie0.append((res["ocupadas"], res["en_cola"]))
            filas.append({"replica": r, "hosp": j, **{m: res[m] for m in METRICAS}})
            esperas_dep.append(res["esperas"])
            sat_dep += res["dias_saturacion"]
        esperas_dep = np.concatenate(esperas_dep)
        totales.append({"replica": r, "dias_saturacion": sat_dep,
                        "espera_media_dias": float(esperas_dep.mean()) if len(esperas_dep) else 0.0})
    return serie0, pd.DataFrame(filas), pd.DataFrame(totales)


def _tarea(args):
    return correr_escenario(*args)


def demanda_des(D, escenario):
    """El escenario ampliacion_camas usa la demanda de linea_base_camas."""
    return D["linea_base_camas"] if escenario == "ampliacion_camas" else D[escenario]


def capacidad(escenario, camas_base):
    if escenario == "ampliacion_camas":
        return int(round(camas_base * (1 + parametro("salud", "ampliacion_camas_pct") / 100)))
    return int(camas_base)


def tabla_metricas(por_escenario, ids, B, rng):
    filas = []
    for esc, df in por_escenario.items():
        for j, g in df.groupby("hosp"):
            for m in METRICAS:
                media, lo, hi, _ = bootstrap_ci(g[m], B, rng)
                filas.append({"escenario": esc, "id_hosp": ids[j], "metrica": m,
                              "media": round(media, 3), "ic_inf": round(lo, 3), "ic_sup": round(hi, 3)})
    return pd.DataFrame(filas)


def comparar_ampliacion(totales, B, rng, camas):
    """R5: Δ = linea_base_camas − ampliacion_camas (positivo = la ampliación mejora)."""
    filas = []
    for m in ("dias_saturacion", "espera_media_dias"):
        base, amp = totales["linea_base_camas"][m], totales["ampliacion_camas"][m]
        d, lo, hi = bootstrap_pareado(base, amp, B, rng)
        filas.append({"camas_base": camas, "camas_ampliadas": capacidad("ampliacion_camas", camas), "metrica": m,
                      "media_linea_base": round(base.mean(), 3), "media_ampliacion": round(amp.mean(), 3),
                      "delta": round(d, 3), "delta_ic_inf": round(lo, 3), "delta_ic_sup": round(hi, 3),
                      "ic_incluye_0": bool(lo <= 0 <= hi)})
    return pd.DataFrame(filas)


def figura_saturacion(sat):
    dep = sat[sat.id_hosp == "departamento"]
    fig, ejes = plt.subplots(1, 2, figsize=(10, 3.8))
    for ax, m, etiqueta in ((ejes[0], "dias_saturacion", "Días-hospital con cola (suma)"),
                            (ejes[1], "espera_media_dias", "Espera media por cama (días)")):
        g = dep[dep.metrica == m]
        ax.fill_between(g.camas, g.ic_inf, g.ic_sup, color="#2a78d6", alpha=0.2, linewidth=0)
        ax.plot(g.camas, g.media, color="#2a78d6", marker="o", linewidth=2)
        ax.set_xlabel("Camas de dengue por hospital (supuesto, sin dato)")
        ax.set_ylabel(etiqueta)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
    fig.suptitle("Saturación contra capacidad (linea_base_camas, media e IC 95 % entre réplicas)", fontsize=10)
    fig.tight_layout()
    fig.savefig("figuras/salud/saturacion_vs_capacidad.png", dpi=150)
    plt.close(fig)


def main(rapido=False):
    replicas = 3 if rapido else parametro("salud", "n_replicas_des")
    B = parametro("abm", "bootstrap_B")
    base = semilla("des")
    camas_base = parametro("salud", "camas_dengue_por_hospital")
    nuevos, cods = nuevos_por_escenario()
    A, hosp = matriz_asignacion(cods)
    ids = hosp.id_hosp.tolist()
    D = {esc: demanda_hospitalaria(n, A) for esc, n in nuevos.items()}
    tabla_asignacion(cods).to_csv(PROCESSED / "salud" / "asignacion_hospitales.csv", index=False)

    minimo, maximo = rango("salud", "camas_dengue_por_hospital")
    capacidades = np.unique(np.round(np.linspace(minimo, maximo, 8)).astype(int))
    tareas = [(demanda_des(D, e), capacidad(e, camas_base), replicas, base) for e in ESCENARIOS_DES]
    tareas += [(D["linea_base_camas"], c, replicas, base) for c in capacidades]
    # R5 también con la capacidad mínima del rango (con la base puede no haber saturación).
    tareas.append((D["linea_base_camas"], capacidad("ampliacion_camas", minimo), replicas, base))
    with ProcessPoolExecutor() as ex:
        resultados = list(ex.map(_tarea, tareas))
    n_esc = len(ESCENARIOS_DES)
    res_esc = dict(zip(ESCENARIOS_DES, resultados[:n_esc]))
    res_cap = dict(zip(capacidades, resultados[n_esc:n_esc + len(capacidades)]))
    ampliado_min = resultados[-1]

    # Contrato: réplica 0 de cada escenario y hospital.
    filas = []
    for esc, (serie0, _, _) in res_esc.items():
        for j, (ocu, cola) in enumerate(serie0):
            filas.append(pd.DataFrame({"escenario": esc, "id_hosp": ids[j], "dia": np.arange(DIAS),
                                       "ocupadas": ocu, "en_cola": cola}))
    ocupacion = pd.concat(filas, ignore_index=True)[COLUMNAS]
    ocupacion.to_csv(PROCESSED / "ocupacion_camas.csv", index=False)

    rng = np.random.default_rng(base)
    metricas = tabla_metricas({e: r[1] for e, r in res_esc.items()}, ids, B, rng)
    metricas.to_csv(PROCESSED / "salud" / "metricas_des.csv", index=False)
    comp = comparar_ampliacion({e: r[2] for e, r in res_esc.items()}, B, rng, camas_base)
    if minimo in res_cap:
        comp_min = comparar_ampliacion({"linea_base_camas": res_cap[minimo][2], "ampliacion_camas": ampliado_min[2]},
                                       B, rng, minimo)
        comp = pd.concat([comp, comp_min], ignore_index=True)
    comp.to_csv(PROCESSED / "salud" / "comparacion_ampliacion.csv", index=False)

    filas = []
    for c, (_, por_hosp, totales) in res_cap.items():
        for m in ("dias_saturacion", "espera_media_dias"):
            media, lo, hi, _ = bootstrap_ci(totales[m], B, rng)
            filas.append({"camas": c, "id_hosp": "departamento", "metrica": m, "media": media, "ic_inf": lo, "ic_sup": hi})
        for j, g in por_hosp.groupby("hosp"):
            for m in ("ocupacion_max", "dias_saturacion"):
                filas.append({"camas": c, "id_hosp": ids[j], "metrica": m, "media": g[m].mean(),
                              "ic_inf": np.percentile(g[m], 2.5), "ic_sup": np.percentile(g[m], 97.5)})
    sat = pd.DataFrame(filas).round(3)
    sat.to_csv(PROCESSED / "salud" / "saturacion_vs_capacidad.csv", index=False)
    figura_saturacion(sat)

    print(f"ocupacion_camas.csv: {len(ocupacion)} filas · {len(ids)} hospitales · {replicas} réplicas · {camas_base} camas base")
    resumen = metricas[metricas.metrica.isin(["ocupacion_max", "dias_saturacion"])].groupby(["escenario", "metrica"]).media.max()
    print("Máximo entre hospitales (media de réplicas):\n" + resumen.unstack().round(2).to_string())
    print("\nR5 · linea_base_camas − ampliacion_camas (pareado):\n" + comp.to_string(index=False))
    dep = sat[(sat.id_hosp == "departamento") & (sat.metrica == "dias_saturacion")]
    print("\nSaturación (días-hospital con cola) contra camas:\n" + dep[["camas", "media", "ic_inf", "ic_sup"]].to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true", help="pocas réplicas (prueba de humo)")
    main(ap.parse_args().rapido)
