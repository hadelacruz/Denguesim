"""Pruebas del SIG aplicado, la integración y el demo (G1, G2, G3, G5).

Correr con:  pytest -q tests/test_sig.py   (desde la raíz)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src" / "datos"))
sys.path.insert(0, str(RAIZ / "src" / "sig"))

from comun import PROCESSED  # noqa: E402


def leer(nombre):
    ruta = PROCESSED / nombre
    if not ruta.exists():
        pytest.skip(f"AVISO: falta {nombre}; corre src/sig/aplicado_run_all.py")
    return pd.read_csv(ruta, dtype={"cod_muni": str, "cod_celda": str})


# ------------------------------------------------------------------ G1 isocronas
def test_isocronas_60_cubre_al_menos_lo_de_30():
    c = leer("sig/cobertura_isocronas.csv")
    t = c.pivot_table(index=["cod_muni", "factor_congestion"], columns="minutos", values="pob_cubierta")
    assert (t[60] >= t[30] - 1e-6).all()


def test_isocronas_mas_congestion_menos_cobertura():
    c = leer("sig/cobertura_isocronas.csv")
    for _, g in c.groupby(["cod_muni", "minutos"]):
        cub = g.sort_values("factor_congestion").pob_cubierta.to_numpy()
        assert (np.diff(cub) <= 1e-6).all()


def test_isocronas_porcentajes_validos():
    c = leer("sig/cobertura_isocronas.csv")
    assert c.pct_cubierta.between(0, 100).all()


# ------------------------------------------------------------------ G2 MCLP
@pytest.fixture(scope="module")
def mclp_por_p():
    from mclp import resolver_mclp
    return [resolver_mclp(p, devolver_detalle=True) for p in range(1, 11)]


def test_mclp_cobertura_no_decrece_con_p(mclp_por_p):
    cobertura = [d["demanda_cubierta_despues_pct"] for _, d in mclp_por_p]
    assert all(b >= a - 1e-9 for a, b in zip(cobertura, cobertura[1:]))


def test_mclp_optimo_al_menos_voraz(mclp_por_p):
    assert all(d["demanda_cubierta_despues_pct"] >= d["voraz_demanda_cubierta_despues_pct"] - 1e-6 for _, d in mclp_por_p)


def test_mclp_unidades_en_celdas_pobladas(mclp_por_p):
    g = pd.read_csv(PROCESSED / "grilla_piloto.csv").set_index("cod_celda").poblacion
    for unidades, d in mclp_por_p:
        assert len(unidades) == d["p"]
        assert (g.loc[unidades.cod_celda] > 0).all()


def test_resolver_mclp_rapido():
    import time
    from mclp import resolver_mclp
    resolver_mclp(5)                                     # precalcula la matriz de distancias
    inicio = time.time()
    resolver_mclp(10, 3000, False)
    assert time.time() - inicio < 3.0


# ------------------------------------------------------------------ G3 ranking
def test_ranking_esquema_y_posiciones():
    r = leer("ranking_riesgo.csv")
    assert list(r.columns) == ["cod_muni", "riesgo_casos", "centralidad", "puntaje", "posicion"]
    assert len(r) == 17 and sorted(r.posicion) == list(range(1, 18))
    assert r.cod_muni.str.fullmatch(r"\d{4}").all()
    assert (r.puntaje.diff().dropna() <= 1e-12).all()   # ordenado por posición = puntaje descendente


def test_ranking_sensibilidad_calculada():
    s = leer("sig/ranking_sensibilidad.csv")
    assert len(s) == 6 and s.spearman_vs_base.between(-1, 1).all()


# ------------------------------------------------------------------ G5 demo
def test_demo_sin_excepciones():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(RAIZ / "dashboard" / "app.py"), default_timeout=120).run()
    assert not at.exception
    for escenario in ("fumigacion_hubs", "ampliacion_camas"):
        at.selectbox(key="escenario").select(escenario).run()
        assert not at.exception
