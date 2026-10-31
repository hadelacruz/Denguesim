"""Pruebas del módulo de Redes (D1, D2, D4 y D5).

Correr con:  pytest -q tests/test_redes.py   (desde la raíz)
"""

import sys
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src" / "datos"))
sys.path.insert(0, str(RAIZ / "src" / "redes"))

from comun import PROCESSED, leer_procesado  # noqa: E402
from construir_red import red_censo, red_gravitacional  # noqa: E402
from umbral import umbral_epidemico  # noqa: E402


def test_red_gravitacional_completa_y_con_umbral():
    assert red_gravitacional(0).number_of_nodes() == 17
    assert red_gravitacional(0).number_of_edges() == 272
    assert red_gravitacional(100).number_of_edges() == 76


def test_red_censo_sin_diagonal_ni_fuera():
    G = red_censo(0)
    assert nx.number_of_selfloops(G) == 0
    assert "FUERA" not in G
    assert G.number_of_nodes() == 17


def test_esquema_centralidad():
    ruta = PROCESSED / "centralidad.csv"
    if not ruta.exists():
        pytest.skip("falta correr src/redes/metricas.py")
    c = leer_procesado("centralidad.csv")
    assert list(c.columns) == ["cod_muni", "grado", "intermediacion", "eigenvector"]
    assert len(c) == 17
    assert not c.isna().any().any()
    assert c.cod_muni.str.fullmatch(r"\d{4}").all()
    assert "0101" in c.nlargest(3, "grado").cod_muni.tolist()


def test_umbral_grafo_completo():
    k = [d for _, d in nx.complete_graph(17).degree()]
    _, _, tau = umbral_epidemico(k)
    assert tau == pytest.approx(16 / 240)


def test_intervenciones_conserva_poblacion_y_k0():
    import intervenciones as iv

    datos = iv.cargar_datos()
    nodos_sin = np.zeros(17, dtype=bool)
    res = iv.simular_metapoblacion(datos, nodos_sin, inicio=0, dias=60, devolver_estado=True)
    total = res["estado"].sum(axis=(1, 2))
    assert np.max(np.abs(total - total[0])) < 1e-6
    # Con k = 0 no se fumiga nada: todas las estrategias dan lo mismo.
    tabla = iv.evaluar_estrategias(datos, ks=[0], sorteos=3, inicios=[0, 13], dias=60)
    assert tabla.groupby("k").tamano_final.nunique().iloc[0] == 1
    assert isinstance(tabla, pd.DataFrame)
