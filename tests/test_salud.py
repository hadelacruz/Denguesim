"""Pruebas del módulo de Salud (R1, R4, R6, R7, R9, R2, R3).

Correr con:  pytest -q tests/test_salud.py   (desde la raíz)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

RAIZ = Path(__file__).resolve().parents[1]
for carpeta in ("datos", "sd", "salud"):
    sys.path.insert(0, str(RAIZ / "src" / carpeta))

from comun import PROCESSED  # noqa: E402
from comun_salud import parametro  # noqa: E402
from des_camas import simular_hospital, verificar_conservacion  # noqa: E402
from estabilidad import es_estable_simulado, mapa_estabilidad, verificar_modelo_A  # noqa: E402
from estancia_weibull import comparar  # noqa: E402
from generadores import constante_M, estancia_aceptacion_rechazo, exponencial, parametros_weibull  # noqa: E402
from insumos import simular_insumos  # noqa: E402
from notificacion import notificados  # noqa: E402
from robustez import prob_mejor  # noqa: E402


# ------------------------------------------------------------------ R1 generadores
@pytest.fixture(scope="module")
def muestra_weibull():
    return estancia_aceptacion_rechazo(20_000, np.random.default_rng(1), devolver_tasa=True)


def test_weibull_ks_no_rechaza(muestra_weibull):
    w, _ = muestra_weibull
    k, lam = parametros_weibull()
    assert stats.kstest(w, stats.weibull_min(c=k, scale=lam).cdf).pvalue > 0.01


def test_weibull_media_dentro_de_3_errores(muestra_weibull):
    w, _ = muestra_weibull
    assert abs(w.mean() - parametro("salud", "estancia_media")) < 3 * w.std(ddof=1) / np.sqrt(len(w))


def test_tasa_aceptacion_es_1_entre_M(muestra_weibull):
    _, tasa = muestra_weibull
    k, lam = parametros_weibull()
    M = constante_M(k, lam, 1 / parametro("salud", "estancia_media"))
    assert abs(tasa - 1 / M) / (1 / M) < 0.02


def test_exponencial_transformada_inversa():
    x = exponencial(0.5, 20_000, np.random.default_rng(2))
    assert stats.kstest(x, stats.expon(scale=2.0).cdf).pvalue > 0.01


# ------------------------------------------------------------------ R4 DES
def test_des_sin_llegadas_ocupacion_cero():
    res = simular_hospital(np.zeros(60), 10, np.random.default_rng(0))
    assert res["ocupadas"].max() == 0 and res["llegadas"] == 0


def test_des_capacidad_enorme_sin_cola():
    res = simular_hospital(np.full(60, 20.0), 10_000, np.random.default_rng(0))
    assert res["en_cola"].max() == 0 and res["dias_saturacion"] == 0


def test_des_conservacion():
    res = simular_hospital(np.full(90, 5.0), 8, np.random.default_rng(3))
    assert res["en_cola"].max() > 0                     # hay cola: la prueba no es trivial
    assert verificar_conservacion(res)


def test_des_misma_semilla_mismo_resultado():
    tasas = np.linspace(0, 6, 80)
    a = simular_hospital(tasas, 12, np.random.default_rng(7))
    b = simular_hospital(tasas, 12, np.random.default_rng(7))
    assert np.array_equal(a["ocupadas"], b["ocupadas"]) and np.array_equal(a["en_cola"], b["en_cola"])


# ------------------------------------------------------------------ R6 insumos
def test_insumos_equilibrio_con_demanda_constante():
    I, P, I_obj = simular_insumos(np.full((2, 120), 3.0))
    assert np.allclose(I, I_obj[:, None], atol=1e-9)
    assert np.allclose(P, parametro("insumos", "tau") * 3.0, atol=1e-9)


def test_insumos_vuelven_al_equilibrio_tras_un_choque():
    D = np.full(400, 3.0)
    D[50:60] = 6.0
    I, _, I_obj = simular_insumos(D)
    # Dos stocks: siempre converge. Tras el choque D = 3 pero D̄ = media(D) > 3, así que el
    # equilibrio es I* + (D̄ − 3)/α (de dP/dt = 0 con P = 3τ).
    equilibrio = I_obj + (D.mean() - 3.0) / parametro("insumos", "alpha")
    assert abs(I[-1] - equilibrio) < 1e-3 * I_obj


# ------------------------------------------------------------------ R7 estabilidad
def test_modelo_A_cero_inestables():
    mapa = mapa_estabilidad()
    inestables, error = verificar_modelo_A(np.unique(mapa.alpha), np.unique(mapa.tau))
    assert inestables == 0 and error < 1e-10


def test_modelo_B_frontera_en_pi_medios():
    tau = 7.0
    assert es_estable_simulado(0.9 * (np.pi / 2) / tau, tau)
    assert not es_estable_simulado(1.1 * (np.pi / 2) / tau, tau)


# ------------------------------------------------------------------ R9 robustez
def test_prob_mejor_suma_1_y_reparte_empates():
    v = np.array([[1.0, 2.0, 3.0], [0.0, 0.0, 5.0], [4.0, 1.0, 1.0]])
    pm = prob_mejor(v)
    assert np.isclose(pm.sum(), 1.0)
    assert np.allclose(pm, [(1 + 0.5) / 3, (0.5 + 0.5) / 3, 0.5 / 3])


def test_robustez_esquema_y_suma():
    ruta = PROCESSED / "robustez.csv"
    if not ruta.exists():
        pytest.skip("falta correr src/salud/robustez.py")
    rob = pd.read_csv(ruta)
    assert list(rob.columns) == ["escenario", "metrica", "media", "ic_inf", "ic_sup", "prob_mejor"]
    assert np.allclose(rob.groupby("metrica").prob_mejor.sum(), 1.0, atol=1e-3)
    assert (rob.ic_inf <= rob.ic_sup).all()      # IC por percentiles: la media puede quedar fuera si hay sesgo


# ------------------------------------------------------------------ R2 y R3 (N2)
def test_notificacion_converge_a_rho_por_c():
    N = notificados(np.full(200, 50.0), rho=0.2, tau=7)
    assert abs(N[-1] - 0.2 * 50.0) < 1e-6


def test_estancia_mismos_dias_paciente():
    ingresos = np.exp(-0.5 * ((np.arange(200) - 100) / 15) ** 2) * 10
    tabla, *_ = comparar(ingresos)
    esperados = tabla.dias_paciente_esperados.iloc[0]
    assert np.allclose(tabla.dias_paciente, esperados, rtol=1e-3)
