"""Pruebas del módulo de datos: contrato de interfaces y consistencia básica.

Correr con:  pytest -q tests/test_contrato_datos.py
Requiere haber generado data/processed/ (python src/datos/run_all.py).
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src" / "datos"))

from comun import PROCESSED, leer_procesado  # noqa: E402
from contrato import verificar  # noqa: E402

pytestmark = pytest.mark.skipif(not (PROCESSED / "poblacion.csv").exists(), reason="faltan datos procesados")


def test_contrato_sin_errores():
    assert verificar() == []


def test_17_municipios_en_tablas_municipales():
    for nombre in ["poblacion.csv", "casos_semanales.csv", "clima_semanal.csv"]:
        assert leer_procesado(nombre).cod_muni.nunique() == 17, nombre


def test_desagregacion_conserva_total_anual():
    sem = leer_procesado("casos_semanales.csv").groupby(["cod_muni", "anio"]).casos.sum()
    anual = leer_procesado("casos_anuales_muni.csv").set_index(["cod_muni", "anio"]).casos
    comun = sem.index.intersection(anual.index)
    assert len(comun) > 0
    assert (sem.loc[comun] == anual.loc[comun]).all()


def test_matriz_distancias_completa_y_positiva():
    d = leer_procesado("distancias.csv")
    assert len(d) == 17 * 16
    assert (d.dist_km > 0).all() and (d.tiempo_min > 0).all()


def test_flujos_suman_fraccion_viaja():
    f = leer_procesado("flujos_od.csv")
    pob = leer_procesado("poblacion.csv").poblacion.sum()
    params = json.loads((PROCESSED / "parametros_datos.json").read_text(encoding="utf-8"))
    fr = params.get("gravitacional", {}).get("fraccion_viaja", {}).get("valor")
    if fr is not None:
        assert abs(f.flujo_diario.sum() / pob - fr) < 1e-3


def test_sigma_es_simetrica_y_semidefinida():
    s = json.loads((PROCESSED / "sigma_hogar.json").read_text(encoding="utf-8"))
    C = np.array(s["covarianza"])
    assert np.allclose(C, C.T)
    assert np.linalg.eigvalsh(C).min() > -1e-10
    # Cholesky debe existir para generar agentes correlacionados en el ABM.
    np.linalg.cholesky(C + 1e-12 * np.eye(len(C)))


def test_atributos_binarios():
    a = leer_procesado("atributos_hogar.csv")
    assert set(a.agua_entubada.unique()) <= {0, 1}
    assert set(a.almacena_agua.unique()) <= {0, 1}
