"""Pruebas del ABM (D6–D13), al estilo de lab4_tests.py del Laboratorio 4.

Correr con:  pytest -q tests/test_abm.py   (desde la raíz)
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src" / "datos"))
sys.path.insert(0, str(RAIZ / "src" / "abm"))

import agentes  # noqa: E402
import reglas  # noqa: E402
from comun import PROCESSED  # noqa: E402
from grilla import actualizar_Y  # noqa: E402
from inicializacion import crear_poblacion, validar_atributos  # noqa: E402
from modelo import ModeloDengue  # noqa: E402
from movilidad import ocupacion  # noqa: E402

# Corridas cortas y con pocos agentes para que las pruebas tarden segundos.
CHICO = dict(escala_agentes=100, dias=25, escala_mosquitos=4.0)


# ---------------------------------------------------------------- inicialización
def test_atributos_reproducen_proporciones_y_correlaciones():
    df = crear_poblacion(12000, np.random.default_rng(123))
    val = validar_atributos(df).set_index("medida")
    for v in ("media_agua_entubada", "media_almacena_agua"):
        assert abs(val.loc[v, "diferencia"]) < 0.01, v            # ±1 punto porcentual
    for m in val.index[val.index.str.startswith("corr_")]:
        assert abs(val.loc[m, "diferencia"]) < 0.05, m            # ±0.05


# ---------------------------------------------------------------- scheduler
def test_cada_agente_se_activa_una_vez_por_paso(monkeypatch):
    orden = []
    original = agentes.Persona.step

    def step_registrado(self):
        orden.append(self.unique_id)
        original(self)

    monkeypatch.setattr(agentes.Persona, "step", step_registrado)
    modelo = ModeloDengue(semilla=5, **CHICO)
    n = len(modelo.agentes)
    ordenes = []
    for _ in range(3):
        orden.clear()
        modelo.step()
        assert sorted(orden) == list(range(n))   # todos, una sola vez
        ordenes.append(list(orden))
    assert ordenes[0] != ordenes[1]               # RandomActivation baraja cada paso
    assert all(ag.activaciones == 3 for ag in modelo.agentes)


@pytest.mark.parametrize("scheduler", ["secuencial_fijo", "sincrono"])
def test_otros_schedulers_activan_a_todos(scheduler):
    modelo = ModeloDengue(semilla=5, scheduler=scheduler, **CHICO)
    modelo.step()
    assert all(ag.activaciones == 1 for ag in modelo.agentes)


# ---------------------------------------------------------------- reproducibilidad y conservación
def test_misma_semilla_mismo_resultado():
    a = ModeloDengue(semilla=11, **CHICO).correr()
    b = ModeloDengue(semilla=11, **CHICO).correr()
    assert a.equals(b)


def test_conservacion_de_agentes():
    modelo = ModeloDengue(semilla=3, **CHICO)
    serie = modelo.correr()
    total = serie[["S", "E", "I", "H", "R"]].sum(axis=1)
    assert (total == len(modelo.agentes)).all()


def test_transicion_invalida_lanza_error():
    modelo = ModeloDengue(semilla=3, **CHICO)
    ag = next(a for a in modelo.agentes if a.estado == "S")
    with pytest.raises(ValueError):
        ag.cambiar_estado("R")
    with pytest.raises(ValueError):
        ag.cambiar_estado("I")


# ---------------------------------------------------------------- grilla y movilidad
def test_grilla_sin_infectados_queda_en_cero():
    Y = np.zeros(10)
    for _ in range(20):
        Y = actualizar_Y(Y, np.zeros(10), 0.5, 0.5, 0.07)
    assert np.all(Y == 0)


def test_grilla_sube_con_infectados_y_decae_con_mu():
    Y = actualizar_Y(np.zeros(5), np.full(5, 0.2), 0.5, 0.5, 0.07)
    assert np.all(Y > 0)
    sin = actualizar_Y(Y, np.zeros(5), 0.5, 0.5, 0.07)
    assert np.allclose(sin, Y * (1 - 0.07))       # decae a la tasa μ


def test_ocupacion_noche_suma_no_hospitalizados():
    modelo = ModeloDengue(semilla=2, **CHICO)
    for _ in range(10):
        modelo.step()
    personas, _ = ocupacion(modelo.celdas_noche, modelo.estados, modelo.n_celdas, agentes.CODIGO["I"], agentes.CODIGO["H"])
    assert personas.sum() == np.sum(modelo.estados != agentes.CODIGO["H"])


# ---------------------------------------------------------------- reglas con probabilidad 0 y 1
def test_reglas_probabilidad_cero_y_uno():
    rng = np.random.default_rng(0)
    assert reglas.prob_picadura(0.5, 0.5, 2.0, 0.0, 0.5) == 0           # R1: sin mosquitos infectados
    assert reglas.prob_picadura(0.5, 0.5, 1e6, 1.0, 0.5) == pytest.approx(1)
    assert reglas.prob_infeccion_fuera(0.0, 0.2) == 0                   # R2
    assert reglas.prob_infeccion_fuera(1e6, 0.2) == 1
    assert reglas.prob_incubacion(0.0) == 0 and reglas.prob_incubacion(1e6) == 1   # R3
    assert reglas.prob_busca_atencion(0.0, 0.0, 1.0) == 0                # R4
    assert reglas.prob_busca_atencion(1.0, 0.0, 1.0) == 1
    assert reglas.prob_hospitalizacion(0.0, 0.5) == 0                    # R5
    assert reglas.prob_hospitalizacion(0.9, 0.5) == 1
    assert reglas.prob_recuperacion(0.0) == 0 and reglas.prob_recuperacion(1e6) == 1   # R6
    assert reglas.prob_alta(1.0) == 1 and reglas.prob_alta(1e12) == pytest.approx(0)   # R7
    assert not any(reglas.ocurre(0.0, rng) for _ in range(1000))
    assert all(reglas.ocurre(1.0, rng) for _ in range(1000))


# ---------------------------------------------------------------- salida para Alex
def test_esquema_beta_efectiva():
    ruta = PROCESSED / "beta_efectiva.json"
    if not ruta.exists():
        pytest.skip("falta correr src/abm/beta_efectiva.py")
    b = json.loads(ruta.read_text(encoding="utf-8"))
    assert set(b) == {"beta", "ic_inf", "ic_sup"}
    assert b["ic_inf"] <= b["beta"] <= b["ic_sup"]
