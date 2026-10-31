"""A11 · Escenarios de intervención sobre la metapoblación → casos_esperados.csv.

| escenario              | qué cambia                                                        |
|------------------------|-------------------------------------------------------------------|
| sin_intervencion       | nada (el loop B endógeno siempre está activo)                     |
| fumigacion_aleatoria   | μ_i·(1 + efecto) en k municipios al azar (distintos por corrida)  |
| fumigacion_hubs        | lo mismo en los top-k por `grado` de centralidad.csv (Daniel, D2) |
| eliminacion_criaderos  | Λ_i·(1 − efecto_criaderos) en todos los municipios                |
| linea_base_camas       | igual que sin_intervencion, etiquetado aparte para Ruiz           |

Corridas: sd.n_corridas por escenario. La corrida k usa un juego de parámetros
muestreado de la calibración (A7: normal multivariada en log), aplicado como
multiplicador relativo sobre la metapoblación. NÚMEROS ALEATORIOS COMUNES (Lab 4):
la corrida k usa el MISMO juego de parámetros y la misma semilla en todos los
escenarios, y por eso se puede comparar con bootstrap PAREADO de
ΔY = Y_sin_intervencion − Y_escenario (se remuestrean los mismos índices).

Las 30 corridas de cada escenario se simulan juntas (estado de forma (30, 17, 13)).

Salidas: data/processed/casos_esperados.csv (contrato), data/processed/sd/resumen_escenarios.csv,
         data/processed/sd/casos_esperados_info.md, figuras/sd/escenarios.png
Uso (desde la raíz):  python src/sd/escenarios.py
"""

import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/sd")
from comun import PROCESSED, leer_procesado, parametro  # noqa: E402
from metapoblacion import cargar_datos, parametros_meta, simular_metapoblacion  # noqa: E402
from modelo_seir_sei import CALIBRACION, ICA, IEH, IIH, IRH, ISH  # noqa: E402
from validacion import muestrear_parametros, semilla  # noqa: E402

ESCENARIOS = ["sin_intervencion", "fumigacion_aleatoria", "fumigacion_hubs", "eliminacion_criaderos", "linea_base_camas"]
COLUMNAS = ["escenario", "corrida", "cod_muni", "dia", "S", "E", "I", "R", "nuevos"]
COLORES = {"sin_intervencion": "#2a78d6", "fumigacion_aleatoria": "#eb6834", "fumigacion_hubs": "#1baf7a",
           "eliminacion_criaderos": "#eda100"}


def muestras_relativas(cal, n, rng):
    """Multiplicadores relativos (muestra / valor calibrado) de cada parámetro calibrado."""
    muestras = muestrear_parametros(cal, n, rng)
    return {nombre: v / cal["valores"][nombre] for nombre, v in muestras.items()}


def municipios_hubs(k):
    c = leer_procesado("centralidad.csv")
    return c.nlargest(k, "grado").cod_muni.tolist()


def factores_escenario(escenario, datos, n, semillas_corrida, efecto_fumigacion=None, efecto_criaderos=None):
    """factor_mu y factor_criaderos de forma (n, 17) para el escenario.

    efecto_fumigacion y efecto_criaderos pueden ser un valor o un arreglo por corrida
    (los usa la robustez de salud, R9); por defecto salen del YAML."""
    k = parametro("sd", "k_fumigacion")
    factor_mu, factor_criaderos = np.ones((n, 17)), np.ones((n, 17))
    efecto_fumigacion = parametro("sd", "efecto_fumigacion_preventiva") if efecto_fumigacion is None else efecto_fumigacion
    efecto_criaderos = parametro("sd", "efecto_criaderos") if efecto_criaderos is None else efecto_criaderos
    efecto_mu = 1 + np.broadcast_to(np.asarray(efecto_fumigacion, dtype=float), (n,))
    if escenario == "fumigacion_aleatoria":
        for r in range(n):
            elegidos = np.random.default_rng(semillas_corrida[r]).choice(17, size=k, replace=False)
            factor_mu[r, elegidos] = efecto_mu[r]
    elif escenario == "fumigacion_hubs":
        idx = [datos["cods"].index(c) for c in municipios_hubs(k)]
        factor_mu[:, idx] = efecto_mu[:, None]
    elif escenario == "eliminacion_criaderos":
        factor_criaderos[:] = 1 - np.broadcast_to(np.asarray(efecto_criaderos, dtype=float), (n,))[:, None]
    return factor_mu, factor_criaderos


def simular_corridas(escenario, datos, cal, relativos, semillas_corrida):
    """Simula las n corridas del escenario a la vez. Devuelve Y (dias+1, n, 17, 13) y p."""
    n = len(semillas_corrida)
    v = cal["valores"]
    cambios = {nombre: (v[nombre] * relativos[nombre]) for nombre in relativos}
    I0 = cambios.pop("I0", np.full(n, v["I0"]))
    cambios = {("expuestos_iniciales" if k == "I0" else k): val[:, None] for k, val in cambios.items()}
    factor_mu, factor_criaderos = factores_escenario(escenario, datos, n, semillas_corrida)
    p = parametros_meta(datos, expuestos_iniciales=I0, factor_mu=factor_mu, factor_criaderos=factor_criaderos, **cambios)
    return simular_metapoblacion(datos, p, dias=364), p


def simular_escenario(escenario, parametros, semilla, datos=None):
    """Función reutilizable (la usa la robustez de salud, R9): UN escenario con un juego de
    parámetros, o con un lote si cada valor es un arreglo de largo n. Devuelve el
    DataFrame del contrato (escenario, corrida, cod_muni, dia, S, E, I, R, nuevos);
    `corrida` es el índice dentro del lote.

    parametros: valores ABSOLUTOS que reemplazan a los calibrados (las claves que falten
      quedan como en calibracion.json o el YAML): beta_s, I0, ganancia_fumigacion,
      lluvia_minima, rho, tau_notificacion, efecto_fumigacion_preventiva, efecto_criaderos.
    semilla: entero; la corrida r sortea los municipios de fumigacion_aleatoria con
      SeedSequence(semilla).spawn(n)[r]. Con la misma semilla y los mismos parámetros,
      todos los escenarios comparten sus números aleatorios (comparación pareada)."""
    datos = cargar_datos() if datos is None else datos
    cal = json.loads(CALIBRACION.read_text(encoding="utf-8"))["valores"]
    v = {**cal, **parametros}
    n = max(np.size(x) for x in v.values())
    columna = lambda x: np.broadcast_to(np.asarray(x, dtype=float), (n,))[:, None]  # noqa: E731
    cambios = {k: columna(v[k]) for k in ("beta_s", "rho", "ganancia_fumigacion", "lluvia_minima", "tau_notificacion")
               if k in v}
    factor_mu, factor_criaderos = factores_escenario(escenario, datos, n, np.random.SeedSequence(semilla).spawn(n),
                                                     v.get("efecto_fumigacion_preventiva"), v.get("efecto_criaderos"))
    p = parametros_meta(datos, expuestos_iniciales=columna(v["I0"])[:, 0], factor_mu=factor_mu,
                        factor_criaderos=factor_criaderos, **cambios)
    res = simular_metapoblacion(datos, p, dias=364)
    return a_tabla(escenario, res["Y"], p, datos["cods"])


def a_tabla(escenario, Y, p, cods):
    """Formato largo del contrato: escenario, corrida, cod_muni, dia, S, E, I, R, nuevos."""
    dias, n = Y.shape[0], Y.shape[1]
    nuevos = p["sigma_h"] * Y[..., IEH]                         # casos verdaderos por día (σh·Eh)
    orden = lambda a: np.transpose(a, (1, 2, 0)).ravel()        # (dia, corrida, muni) → corrida, muni, dia  # noqa: E731
    return pd.DataFrame({
        "escenario": escenario,
        "corrida": np.repeat(np.arange(n), 17 * dias),
        "cod_muni": np.tile(np.repeat(cods, dias), n),
        "dia": np.tile(np.arange(dias), n * 17),
        "S": orden(Y[..., ISH]).round(2), "E": orden(Y[..., IEH]).round(2),
        "I": orden(Y[..., IIH]).round(2), "R": orden(Y[..., IRH]).round(2),
        "nuevos": orden(nuevos).round(3),
    })[COLUMNAS]


def metricas_por_corrida(Y, p):
    """Departamento: total de casos verdaderos, pico diario y día del pico, por corrida."""
    diario = (p["sigma_h"] * Y[..., IEH]).sum(axis=-1)          # (dias, n)
    return pd.DataFrame({
        "total_casos": Y[-1, ..., ICA].sum(axis=-1),
        "total_notificados": p["rho"] * Y[-1, ..., ICA].sum(axis=-1),
        "pico": diario.max(axis=0),
        "dia_pico": diario.argmax(axis=0),
    })


def bootstrap_pareado(base, otro, B, rng):
    """IC 95 % de la media de ΔY = base − otro remuestreando los MISMOS índices."""
    delta = np.asarray(base) - np.asarray(otro)
    idx = rng.integers(0, len(delta), size=(B, len(delta)))
    medias = delta[idx].mean(axis=1)
    return delta.mean(), np.percentile(medias, 2.5), np.percentile(medias, 97.5)


def bootstrap_media(Y, B, rng):
    Y = np.asarray(Y)
    medias = Y[rng.integers(0, len(Y), size=(B, len(Y)))].mean(axis=1)
    return Y.mean(), np.percentile(medias, 2.5), np.percentile(medias, 97.5)


def resumen(metricas, B, rng):
    filas = []
    base = metricas["sin_intervencion"]
    for esc, m in metricas.items():
        for col in m.columns:
            media, lo, hi = bootstrap_media(m[col], B, rng)
            d, dlo, dhi = bootstrap_pareado(base[col], m[col], B, rng)
            filas.append({"escenario": esc, "metrica": col, "media": round(media, 2), "ic_inf": round(lo, 2), "ic_sup": round(hi, 2),
                          "delta_vs_sin_intervencion": round(d, 2), "delta_ic_inf": round(dlo, 2), "delta_ic_sup": round(dhi, 2),
                          "delta_ic_incluye_0": bool(dlo <= 0 <= dhi)})
    return pd.DataFrame(filas)


def figura(series):
    fig, ax = plt.subplots(figsize=(10, 4.2))
    for esc, diario in series.items():
        if esc == "linea_base_camas":
            continue                                             # idéntico a sin_intervencion
        t = np.arange(diario.shape[0])
        ax.fill_between(t, np.percentile(diario, 2.5, axis=1), np.percentile(diario, 97.5, axis=1),
                        color=COLORES[esc], alpha=0.15, linewidth=0)
        ax.plot(t, np.median(diario, axis=1), color=COLORES[esc], linewidth=2, label=esc.replace("_", " "))
    ax.set_xlabel(f"Día del año {parametro('sd', 'anio_base')}")
    ax.set_ylabel("Casos verdaderos por día (departamento)")
    ax.set_title("Escenarios: mediana y banda 2.5–97.5 % de las corridas (línea base de camas = sin intervención)", fontsize=10)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
    fig.tight_layout()
    fig.savefig("figuras/sd/escenarios.png", dpi=150)
    plt.close(fig)


def escribir_info(cal, datos, n):
    texto = f"""# `casos_esperados.csv` — cómo usarlo (Dinámica de Sistemas, A11)

- **Columnas:** `escenario, corrida, cod_muni, dia, S, E, I, R, nuevos` (contrato).
- **Escenarios:** {", ".join(ESCENARIOS)}. `linea_base_camas` es idéntico a `sin_intervencion`
  (etiquetado aparte para el módulo de salud).
- **Corridas:** {n} por escenario (`corrida` = 0 … {n - 1}). La corrida k usa el mismo juego de
  parámetros en todos los escenarios (números aleatorios comunes): comparen escenarios **por corrida**.
- **Año base:** {datos['anio']}. `dia` = 0 … 364 (día 0 = inicio de la semana epidemiológica 1).
- **S, E, I, R:** humanos susceptibles, expuestos, infecciosos y recuperados del municipio (personas).
  Ojo: el acoplamiento por movilidad mueve infecciosos entre municipios, así que S+E+I+R de un
  municipio puede diferir un poco de su población; el total del departamento sí se conserva.
- **`nuevos`:** casos humanos nuevos **VERDADEROS** por día (σh·Eh), **sin** factor de reporte.
  Para pasar a casos **notificados**, multipliquen por ρ = {cal['valores']['rho']}
  (`observacion.factor_reporte`; ρ no es identificable con los datos, ver `calibracion.json`).
  Para hospitalizaciones: notificados × `salud.fraccion_hospitalizada`.
- **Calibración:** βs, I0, ganancia del loop B y lluvia mínima ajustados al departamento (A6);
  multiplicador de mosquitos por municipio ajustado a `casos_anuales_muni.csv` {datos['anio']} (A10).
- **Limitación:** la forma semanal objetivo es un estimado (forma nacional escalada al total
  departamental); los totales anuales por municipio sí son observados.
"""
    (PROCESSED / "sd" / "casos_esperados_info.md").write_text(texto, encoding="utf-8")


def main():
    datos = cargar_datos()
    cal = json.loads(CALIBRACION.read_text(encoding="utf-8"))
    n = parametro("sd", "n_corridas")
    base = semilla("sd", "escenarios")
    relativos = muestras_relativas(cal, n, np.random.default_rng(base))
    semillas_corrida = np.random.SeedSequence(base).spawn(n)
    tablas, metricas, series = [], {}, {}
    for esc in ESCENARIOS:
        res, p = simular_corridas(esc, datos, cal, relativos, semillas_corrida)
        tablas.append(a_tabla(esc, res["Y"], p, datos["cods"]))
        metricas[esc] = metricas_por_corrida(res["Y"], p)
        series[esc] = (p["sigma_h"] * res["Y"][..., IEH]).sum(axis=-1)
        print(f"{esc:24s} total verdadero (mediana) = {metricas[esc].total_casos.median():10.0f}, "
              f"notificados = {metricas[esc].total_notificados.median():8.0f}")
    tabla = pd.concat(tablas, ignore_index=True)
    tabla.to_csv(PROCESSED / "casos_esperados.csv", index=False)
    rng = np.random.default_rng(semilla("sd", "bootstrap"))
    res_tabla = resumen(metricas, parametro("abm", "bootstrap_B"), rng)
    res_tabla.to_csv(PROCESSED / "sd" / "resumen_escenarios.csv", index=False)
    escribir_info(cal, datos, n)
    figura(series)
    print(f"\ncasos_esperados.csv: {len(tabla)} filas")
    print(res_tabla[res_tabla.metrica.isin(["total_casos", "pico"])].to_string(index=False))


if __name__ == "__main__":
    main()
