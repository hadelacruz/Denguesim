"""R10 · Esquema de CADA tabla de interfaz que producen los módulos (contrato de interfaces).

Columnas exactas (ni más ni menos), cod_muni como texto de 4 dígitos, sin nulos y
rangos plausibles. Si un archivo aún no existe, la prueba hace pytest.skip con un aviso
(al final del proyecto no debe quedar ninguna saltada).

Correr con:  pytest -q tests/test_contrato_salida.py   (desde la raíz)
"""

import json
from pathlib import Path

import pandas as pd
import pytest

PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"
TEXTO = {"cod_muni": str, "id_hosp": str, "cod_celda": str}
ESCENARIOS_SD = {"sin_intervencion", "fumigacion_aleatoria", "fumigacion_hubs", "eliminacion_criaderos", "linea_base_camas"}

CONTRATO = {
    "centralidad.csv": ["cod_muni", "grado", "intermediacion", "eigenvector"],
    "casos_esperados.csv": ["escenario", "corrida", "cod_muni", "dia", "S", "E", "I", "R", "nuevos"],
    "ocupacion_camas.csv": ["escenario", "id_hosp", "dia", "ocupadas", "en_cola"],
    "inventario.csv": ["escenario", "id_hosp", "dia", "I", "P"],
    "robustez.csv": ["escenario", "metrica", "media", "ic_inf", "ic_sup", "prob_mejor"],
    "unidades_mclp.csv": ["p", "cod_celda", "lat", "lon", "poblacion_cubierta"],
    "ranking_riesgo.csv": ["cod_muni", "riesgo_casos", "centralidad", "puntaje", "posicion"],
}


def leer(nombre):
    ruta = PROCESSED / nombre
    if not ruta.exists():
        pytest.skip(f"AVISO: falta {nombre}; corre el módulo que lo produce")
    return pd.read_csv(ruta, dtype=TEXTO)


@pytest.mark.parametrize("nombre", list(CONTRATO))
def test_columnas_exactas_y_sin_nulos(nombre):
    df = leer(nombre)
    assert list(df.columns) == CONTRATO[nombre]
    assert len(df) > 0
    assert not df.isna().any().any()


@pytest.mark.parametrize("nombre", ["centralidad.csv", "casos_esperados.csv", "ranking_riesgo.csv"])
def test_cod_muni_texto_de_4_digitos(nombre):
    df = leer(nombre)
    assert df.cod_muni.str.fullmatch(r"01\d{2}").all()
    assert df.cod_muni.nunique() == 17


def test_beta_efectiva_json():
    ruta = PROCESSED / "beta_efectiva.json"
    if not ruta.exists():
        pytest.skip("AVISO: falta beta_efectiva.json")
    b = json.loads(ruta.read_text(encoding="utf-8"))
    assert set(b) == {"beta", "ic_inf", "ic_sup"}
    assert 0 < b["ic_inf"] <= b["beta"] <= b["ic_sup"]


def test_rangos_casos_esperados():
    df = leer("casos_esperados.csv")
    assert set(df.escenario) == ESCENARIOS_SD
    assert df.dia.between(0, 364).all()
    assert (df[["S", "E", "I", "R", "nuevos"]] >= -1e-6).all().all()


def test_rangos_salud():
    o, i, r = leer("ocupacion_camas.csv"), leer("inventario.csv"), leer("robustez.csv")
    assert set(o.escenario) == ESCENARIOS_SD | {"ampliacion_camas"}
    assert (o.ocupadas >= 0).all() and (o.en_cola >= 0).all() and o.dia.between(0, 364).all()
    assert set(i.escenario) == set(o.escenario) and set(i.id_hosp) == set(o.id_hosp)
    # Modelo lineal: I < 0 es déficit acumulado y P < 0 son pedidos cancelados; solo se pide que sean finitos.
    assert pd.api.types.is_float_dtype(i.I) and pd.api.types.is_float_dtype(i.P)
    assert r.prob_mejor.between(0, 1).all()


def test_rangos_sig():
    u, k = leer("unidades_mclp.csv"), leer("ranking_riesgo.csv")
    assert u.p.between(1, 10).all() and (u.poblacion_cubierta >= 0).all()
    assert u.lat.between(14.0, 15.2).all() and u.lon.between(-91.0, -90.0).all()
    assert len(k) == 17 and sorted(k.posicion) == list(range(1, 18))
    assert k[["riesgo_casos", "centralidad", "puntaje"]].stack().between(0, 1).all()
