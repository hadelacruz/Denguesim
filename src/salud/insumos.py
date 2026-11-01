"""R6 · Cadena de insumos de dos stocks por hospital y escenario → inventario.csv.

    dI/dt = P/τ − D(t)               inventario   [unidades/día]
    dP/dt = D̄ + α·(I* − I) − P/τ    pedidos en tránsito (pipeline de primer orden)

    D(t) = salud.insumo_por_paciente_dia × ocupadas(t)     (ocupadas del DES, R4)
    I*   = insumos.cobertura_objetivo × media(D)            (días de cobertura deseados)
    α, τ = insumos.alpha, insumos.tau (valor central del YAML)

Pedidos: con dP/dt = α·(I* − I) − P/τ el equilibrio queda en I* − D̄/α, no en I*.
Por eso se agrega la reposición de la demanda media D̄: el equilibrio es I = I*,
P = τ·D̄, y la ecuación característica s² + s/τ + α/τ = 0 (R7) no cambia.

Condición inicial de equilibrio: I(0) = I*, P(0) = τ·media(D). Integración con el
rk4_step escrito a mano de Alex (src/sd/integradores.py), paso 0.1 día, registro diario.
D(t) es constante dentro de cada día y, como 1/h es entero, ningún paso cruza un día.

El modelo es lineal: I PUEDE SALIR NEGATIVO. Se interpreta como déficit acumulado
(demanda que no se pudo atender con inventario) y se reporta así; no se recorta a 0.

Salidas: data/processed/inventario.csv (contrato) y data/processed/salud/metricas_insumos.csv
Uso (desde la raíz):  python src/salud/insumos.py
"""

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/sd")
sys.path.insert(0, "src/salud")
from comun import PROCESSED, leer_procesado  # noqa: E402
from comun_salud import parametro  # noqa: E402
from integradores import rk4_step  # noqa: E402

COLUMNAS = ["escenario", "id_hosp", "dia", "I", "P"]
PASO = 0.1


def derivadas_insumos(t, y, p):
    """y[..., 0] = I, y[..., 1] = P. D se toma del día del paso."""
    I, P = y[..., 0], y[..., 1]
    D = p["D"][..., p["dia_del_paso"]]
    dI = P / p["tau"] - D                                  # llegan pedidos − consumo  [unidades/día]
    dP = p["D_media"] + p["alpha"] * (p["I_obj"] - I) - P / p["tau"]  # se pide − se entrega  [unidades/día]
    return np.stack([dI, dP], axis=-1)


def simular_insumos(D, alpha=None, tau=None, cobertura=None, h=PASO):
    """D: consumo diario (…, dias). Devuelve I, P (…, dias) al final de cada día e I*."""
    alpha = parametro("insumos", "alpha") if alpha is None else alpha
    tau = parametro("insumos", "tau") if tau is None else tau
    cobertura = parametro("insumos", "cobertura_objetivo") if cobertura is None else cobertura
    D = np.asarray(D, dtype=float)
    media = D.mean(axis=-1)
    p = {"D": D, "alpha": np.asarray(alpha, dtype=float), "tau": np.asarray(tau, dtype=float),
         "I_obj": np.asarray(cobertura) * media, "D_media": media}
    y = np.stack(np.broadcast_arrays(p["I_obj"], p["tau"] * media), axis=-1).astype(float)  # equilibrio
    dias = D.shape[-1]
    I, P = np.empty(D.shape), np.empty(D.shape)
    pasos = int(round(1 / h))
    for d in range(dias):
        p["dia_del_paso"] = d
        for s in range(pasos):
            y = rk4_step(derivadas_insumos, d + s * h, y, h, p)
        I[..., d], P[..., d] = y[..., 0], y[..., 1]
    return I, P, p["I_obj"]


def dias_desabasto(I, I_obj, umbral=None):
    """Días con I < umbral · I* (si I* = 0 no hay consumo y no se cuenta desabasto)."""
    umbral = parametro("salud", "umbral_desabasto") if umbral is None else umbral
    I_obj = np.asarray(I_obj)[..., None]
    return np.where(I_obj > 0, I < umbral * I_obj, False).sum(axis=-1)


def consumo_desde_ocupacion(ocupacion):
    """{(escenario, id_hosp): D diario} desde ocupacion_camas.csv."""
    q = parametro("salud", "insumo_por_paciente_dia")
    tabla = ocupacion.pivot_table(index=["escenario", "id_hosp"], columns="dia", values="ocupadas").sort_index()
    return tabla.index, q * tabla.to_numpy(float)


def main():
    ocupacion = leer_procesado("ocupacion_camas.csv")
    indice, D = consumo_desde_ocupacion(ocupacion)
    I, P, I_obj = simular_insumos(D)
    dias = np.arange(D.shape[1])
    inventario = pd.DataFrame({
        "escenario": np.repeat(indice.get_level_values(0), len(dias)),
        "id_hosp": np.repeat(indice.get_level_values(1), len(dias)),
        "dia": np.tile(dias, len(indice)),
        "I": I.ravel().round(3), "P": P.ravel().round(3),
    })[COLUMNAS]
    inventario.to_csv(PROCESSED / "inventario.csv", index=False)
    metricas = pd.DataFrame({
        "escenario": indice.get_level_values(0), "id_hosp": indice.get_level_values(1),
        "demanda_media": D.mean(axis=1).round(3), "I_objetivo": I_obj.round(3),
        "I_min": I.min(axis=1).round(3), "amplitud_max": np.abs(I - I_obj[:, None]).max(axis=1).round(3),
        "dias_deficit": (I < 0).sum(axis=1), "dias_desabasto": dias_desabasto(I, I_obj),
    })
    metricas.to_csv(PROCESSED / "salud" / "metricas_insumos.csv", index=False)
    print(f"inventario.csv: {len(inventario)} filas · α = {parametro('insumos', 'alpha')}, τ = {parametro('insumos', 'tau')}, "
          f"α·τ = {parametro('insumos', 'alpha') * parametro('insumos', 'tau'):.2f}")
    print(metricas.groupby("escenario")[["dias_desabasto", "dias_deficit", "amplitud_max"]].agg(["sum", "max"]).to_string())


if __name__ == "__main__":
    main()
