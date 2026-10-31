"""Pruebas del módulo de Dinámica de Sistemas (A1, A4, A9, A10, A11 y A12).

Correr con:  pytest -q tests/test_sd.py   (desde la raíz)
"""

import sys
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src" / "datos"))
sys.path.insert(0, str(RAIZ / "src" / "sd"))

from comun import PROCESSED, leer_procesado  # noqa: E402
from modelo_seir_sei import (casos_verdaderos_diarios, metricas_epidemia, parametros_departamento,  # noqa: E402
                             simular_seir_sei, verificar_conservacion)


@pytest.fixture(scope="module")
def p():
    return parametros_departamento()


def test_conservacion_humanos(p):
    res = simular_seir_sei(p, dias=120, h=0.25)
    assert verificar_conservacion(res["Y"], p["Nh"]) < 1e-6


def test_sin_infectados_nada_cambia_en_humanos(p):
    res = simular_seir_sei(p, dias=60, h=0.25, expuestos_iniciales=0.0)
    assert np.abs(res["Y"][:, :4] - res["Y"][0, :4]).max() == 0.0


def test_rk4_dt_contra_dt_mitad(p):
    picos = [metricas_epidemia(r["t"], casos_verdaderos_diarios(r))["pico"]
             for r in (simular_seir_sei(p, dias=364, h=h) for h in (0.5, 0.25))]
    assert abs(picos[0] - picos[1]) / picos[1] < 0.01


def test_metapoblacion_conserva_total():
    import metapoblacion as mp

    datos = mp.cargar_datos()
    res = mp.simular_metapoblacion(datos, dias=60, h=0.5)
    assert mp.verificar_conservacion_total(res["Y"], datos["Nh"]) < 1e-6
    # El acoplamiento suma cero entre municipios.
    Ih = np.random.default_rng(0).uniform(0, 100, 17)
    assert abs(mp.acoplamiento(Ih, datos).sum()) < 1e-6


def test_esquema_casos_esperados():
    ruta = PROCESSED / "casos_esperados.csv"
    if not ruta.exists():
        pytest.skip("falta correr src/sd/escenarios.py")
    df = leer_procesado("casos_esperados.csv")
    assert list(df.columns) == ["escenario", "corrida", "cod_muni", "dia", "S", "E", "I", "R", "nuevos"]
    assert set(df.escenario) == {"sin_intervencion", "fumigacion_aleatoria", "fumigacion_hubs",
                                 "eliminacion_criaderos", "linea_base_camas"}
    assert df.cod_muni.str.fullmatch(r"\d{4}").all() and df.cod_muni.nunique() == 17
    assert df.dia.min() == 0 and df.dia.max() == 364
    assert not df.isna().any().any()
    assert (df[["S", "E", "I", "R", "nuevos"]] >= -1e-6).all().all()


# ---------------------------------------------------------------- A9 y A12 (N3)
def test_poblacion_abierta_conserva_y_repone_susceptibles():
    import poblacion_abierta as pa
    from modelo_seir_sei import ISH
    from vector_lluvia import lluvia_departamento

    t, Y, p = pa.simular(np.tile(lluvia_departamento(2023)[:52], 2), h=1.0)
    assert verificar_conservacion(Y, p["Nh"]) < 1e-6
    # Lote [cerrada, abierta]: con nacimientos quedan más susceptibles al final.
    assert Y[-1, 1, ISH] > Y[-1, 0, ISH]


def test_primera_racha_de_brote():
    from orden_llegada import llegadas, primera_racha

    assert primera_racha([False, True, True, False, True, True, True], 3) == 5
    assert primera_racha([True, True, False], 3) is None
    tabla = llegadas({"A": [False, True, True, True], "B": [False] * 4}, 3, 4)
    assert tabla.semana_llegada.tolist() == [2, 5] and tabla.censurado.tolist() == [False, True]
