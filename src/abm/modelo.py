"""D11 · ModeloDengue (Mesa 2.4.0) con scheduler MIXTO.

Regla de clase (S8): síncrono para procesos físicos, asíncrono aleatorio para
comportamiento social.
  - Personas (comportamiento)      → RandomActivation (orden barajado cada paso).
  - Celdas y mosquitos (proceso físico) → arreglos de NumPy actualizados de forma
    síncrona (doble buffer), una vez por paso y DESPUÉS de las personas.

Cada paso = 1 día:
  1. Antes de activar a nadie se calcula con NumPy, una sola vez, la
     probabilidad de exposición de cada celda en la fase día y en la noche,
     a partir de Y_c (estado del paso anterior) y m_c(t). Cada agente hace una
     sola consulta y un solo sorteo.
  2. schedule.step(): cada persona combina la exposición de ambas fases (R1 y R2)
     y aplica R3–R7.
  3. Con la ocupación de ambas fases se actualizan las celdas (grilla.py).
  4. datacollector.collect(self).

Schedulers para el experimento de D11: "mixto" (RandomActivation),
"secuencial_fijo" (BaseScheduler) y "sincrono" (SimultaneousActivation).
"""

import json
import sys

import mesa
import numpy as np
from mesa.time import BaseScheduler, RandomActivation, SimultaneousActivation

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/abm")
from agentes import CODIGO, ESTADOS, Persona  # noqa: E402
from comun import PROCESSED, leer_procesado, parametro  # noqa: E402
from grilla import actualizar_Y, cargar_densidad, fraccion_infecciosa, mosquitos_por_persona  # noqa: E402
from inicializacion import cargar_grilla, crear_poblacion, numero_agentes  # noqa: E402
from movilidad import FUERA, celda_dia, celda_noche, ocupacion  # noqa: E402
from reglas import (factor_hogar, prob_alta, prob_busca_atencion, prob_hospitalizacion,  # noqa: E402
                    prob_incubacion, prob_infeccion_fuera, prob_picadura, prob_recuperacion)

SCHEDULERS = {"mixto": RandomActivation, "secuencial_fijo": BaseScheduler, "sincrono": SimultaneousActivation}


def factor_reporte():
    """ρ de la calibración de Alex (A6); si no existe, el valor nominal del YAML."""
    ruta = PROCESSED / "sd" / "calibracion.json"
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))["valores"]["rho"]
    return parametro("observacion", "factor_reporte")


def incidencia_destinos(anio):
    """Casos notificados por persona en el año, por municipio y para 'FUERA' (departamento)."""
    casos = leer_procesado("casos_anuales_muni.csv")
    casos = casos[casos.anio == anio].set_index("cod_muni").casos
    pob = leer_procesado("poblacion_anual.csv")
    pob = pob[pob.anio == anio].set_index("cod_muni").poblacion
    inc = (casos / pob).to_dict()
    inc["FUERA"] = casos.sum() / pob.sum()
    return inc


class ModeloDengue(mesa.Model):
    """ABM de dengue en la grilla de Amatitlán."""

    def __init__(self, semilla=None, escala_agentes=None, dias=None, scheduler="mixto", escala_mosquitos=None):
        super().__init__()
        if semilla is not None:
            self.reset_randomizer(semilla)            # self.random: orden del scheduler
        self.rng = np.random.default_rng(semilla)     # NumPy: atributos y sorteos
        self.dias = parametro("abm", "dias_simulacion") if dias is None else dias
        self.escala_agentes = parametro("abm", "escala_agentes") if escala_agentes is None else escala_agentes
        self.sincrono = scheduler == "sincrono"
        self.dia = 0

        # --- parámetros (todos del YAML)
        self.a, self.b, self.c = (parametro("transmision", k) for k in ("a", "b", "c"))
        self.mu = parametro("transmision", "mu")
        self.w_dia = parametro("abm", "fraccion_picaduras_dia")
        self.efecto_almacena = parametro("abm", "efecto_almacena_agua")
        self.p_busca_base = parametro("abm", "prob_busca_atencion_base")
        self.efecto_riqueza = parametro("abm", "efecto_riqueza_atencion")
        self.p_incubacion = prob_incubacion(parametro("transmision", "sigma_h"))
        self.p_recuperacion = prob_recuperacion(parametro("transmision", "gamma"))
        self.p_alta = prob_alta(parametro("salud", "estancia_media"))
        self.rho = factor_reporte()
        anio = parametro("abm", "anio")
        escala_m = parametro("abm", "escala_mosquitos") if escala_mosquitos is None else escala_mosquitos
        if escala_m is None:
            raise ValueError("abm.escala_mosquitos no está calibrada: corre src/abm/corridas.py o pásala al modelo")

        # --- entorno (celdas = arreglos de NumPy)
        self.grilla = cargar_grilla()
        self.n_celdas = len(self.grilla)
        densidad = cargar_densidad(self.grilla, anio)
        self.m_semanal = mosquitos_por_persona(densidad, self.grilla.poblacion.to_numpy(), escala_m)
        self.semana_inicio = parametro("abm", "semana_inicio")
        self.Y = np.zeros(self.n_celdas)

        # --- agentes
        n = numero_agentes(self.grilla, self.escala_agentes)
        pob = crear_poblacion(n, self.rng, self.grilla)
        self.schedule = SCHEDULERS[scheduler](self)
        self.estados = np.zeros(n, dtype=int)
        self.celdas_dia = np.empty(n, dtype=int)
        self.celdas_noche = np.empty(n, dtype=int)
        for i, fila in enumerate(pob.itertuples()):
            # pandas guarda los None como NaN: se normalizan aquí.
            destino = fila.destino if isinstance(fila.destino, str) else None
            trabajo = int(fila.celda_trabajo) if destino == "0114" else None
            persona = Persona(i, self, fila.edad, fila.indice_riqueza, fila.agua_entubada, fila.almacena_agua,
                              int(fila.celda_casa), trabajo, destino)
            self.schedule.add(persona)
            self.celdas_dia[i] = celda_dia(persona.destino, persona.celda_casa, persona.celda_trabajo)
            self.celdas_noche[i] = celda_noche(persona.celda_casa)
        self.agentes = list(self.schedule.agents)

        # R5: P(H | buscó) para que P(busca)·P(H | busca) = fraccion_hospitalizada
        p_media = np.mean([prob_busca_atencion(self.p_busca_base, self.efecto_riqueza, ag.indice_riqueza) for ag in self.agentes])
        self.p_hospitalizacion = prob_hospitalizacion(parametro("salud", "fraccion_hospitalizada"), p_media)
        # R2: probabilidad diaria de infección en el destino externo
        inc = incidencia_destinos(anio)
        self.p_fuera = {d: prob_infeccion_fuera(inc[d], self.rho, self.w_dia) for d in inc}

        # --- infección inicial: agentes en E
        for ag in self.rng.choice(self.agentes, size=parametro("abm", "infectados_iniciales"), replace=False):
            ag.cambiar_estado("E")

        self.edades_infectados = []
        self._reiniciar_contadores()
        self.datacollector = mesa.DataCollector(model_reporters={
            "dia": lambda m: m.dia,
            **{e: (lambda m, k=CODIGO[e]: int(np.sum(m.estados == k))) for e in ESTADOS},
            "nuevos_infectados": lambda m: m.nuevos_infectados,
            "nuevos_infectados_fuera": lambda m: m.nuevos_infectados_fuera,
            "nuevos_casos": lambda m: m.nuevos_casos,
            "Y_medio": lambda m: float(m.Y.mean()),
        })
        self.datacollector.collect(self)

    # ------------------------------------------------------------ apoyo a los agentes
    def _reiniciar_contadores(self):
        self.nuevos_infectados = 0
        self.nuevos_infectados_fuera = 0
        self.nuevos_casos = 0

    def registrar_transicion(self, agente, viejo, nuevo):
        """Lo llama Persona.cambiar_estado: mantiene el arreglo de estados y los contadores."""
        self.estados[agente.unique_id] = CODIGO[nuevo]
        if nuevo == "E" and self.dia > 0:
            self.nuevos_infectados += 1
            self.edades_infectados.append(agente.edad)
        elif nuevo == "I":
            self.nuevos_casos += 1

    def sorteo_exposicion(self, agente):
        """R1 + R2 con un solo sorteo. Probabilidad total de las dos fases:
        p = 1 − (1 − p_dia)(1 − p_noche). Si la infección ocurre se distingue si fue
        local (grilla) o fuera del municipio (R2), para estimar β (D13)."""
        cd = self.celdas_dia[agente.unique_id]
        p_noche = self.P_noche_alm[agente.celda_casa] if agente.almacena_agua else self.P_noche[agente.celda_casa]
        if cd == FUERA:
            p_local, p_fuera = p_noche, self.p_fuera[agente.destino]
        else:
            p_local, p_fuera = 1 - (1 - self.P_dia[cd]) * (1 - p_noche), 0.0
        u = self.rng.random()
        if u < p_local:
            return True
        if u < p_local + (1 - p_local) * p_fuera:
            self.nuevos_infectados_fuera += 1
            return True
        return False

    # ------------------------------------------------------------ paso del modelo
    def _probabilidades_de_celda(self):
        """Paso 1: exposición por celda y fase con Y del paso anterior (NumPy, una vez)."""
        semana = min(self.semana_inicio - 1 + self.dia // 7, len(self.m_semanal) - 1)
        m = self.m_semanal[semana]
        self.P_dia = prob_picadura(self.a, self.b, m, self.Y, self.w_dia)
        self.P_noche = prob_picadura(self.a, self.b, m, self.Y, 1 - self.w_dia)
        self.P_noche_alm = prob_picadura(self.a, self.b, m, self.Y, 1 - self.w_dia, factor_hogar(1, self.efecto_almacena))

    def _actualizar_celdas(self):
        """Paso 3: ocupación de ambas fases y actualización síncrona de Y."""
        codigo_I, codigo_H = CODIGO["I"], CODIGO["H"]
        N_dia, I_dia = ocupacion(self.celdas_dia, self.estados, self.n_celdas, codigo_I, codigo_H)
        N_noche, I_noche = ocupacion(self.celdas_noche, self.estados, self.n_celdas, codigo_I, codigo_H)
        f = fraccion_infecciosa(I_dia, N_dia, I_noche, N_noche, self.w_dia)
        self.Y = actualizar_Y(self.Y, f, self.a, self.c, self.mu)

    def step(self):
        self.dia += 1
        self._reiniciar_contadores()
        self._probabilidades_de_celda()   # 1. entorno → probabilidades (síncrono)
        self.schedule.step()              # 2. personas (asíncrono aleatorio)
        self._actualizar_celdas()         # 3. personas → entorno (síncrono, doble buffer)
        self.datacollector.collect(self)  # 4. registro

    def correr(self):
        for _ in range(self.dias):
            self.step()
        return self.datacollector.get_model_vars_dataframe()


if __name__ == "__main__":
    import time

    t0 = time.perf_counter()
    modelo = ModeloDengue(semilla=1, escala_agentes=100, dias=30, escala_mosquitos=1.0)
    serie = modelo.correr()
    print(f"{len(modelo.agentes)} agentes, 30 días en {time.perf_counter() - t0:.2f} s")
    print(serie.tail(3).to_string(index=False))
