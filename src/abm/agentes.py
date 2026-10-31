"""D6 · Agente Persona (Mesa 2.4.0, mismo patrón que agents.py del Laboratorio 4).

Estados: S (susceptible), E (expuesto), I (infeccioso), H (hospitalizado), R (recuperado).
Transiciones válidas: S→E, E→I, I→R, I→H, H→R. Cualquier otra lanza ValueError.

Las personas NO leen el estado de otras personas: se comunican a través del
entorno (los mosquitos de cada celda), que el modelo actualiza de forma síncrona
después de activar a todos. Por eso step() solo consulta las probabilidades de
exposición que el modelo ya calculó al inicio del paso.

  - RandomActivation / BaseScheduler: step() decide y aplica.
  - SimultaneousActivation: step() decide y advance() aplica.
"""

import sys

import mesa

sys.path.insert(0, "src/abm")
from reglas import ocurre, prob_busca_atencion  # noqa: E402

ESTADOS = ["S", "E", "I", "H", "R"]
CODIGO = {e: i for i, e in enumerate(ESTADOS)}
TRANSICIONES_VALIDAS = {("S", "E"), ("E", "I"), ("I", "R"), ("I", "H"), ("H", "R")}


class Persona(mesa.Agent):
    """Una persona de Amatitlán (representa a abm.escala_agentes personas)."""

    def __init__(self, unique_id, model, edad, indice_riqueza, agua_entubada, almacena_agua,
                 celda_casa, celda_trabajo, destino):
        super().__init__(unique_id, model)   # Mesa 2: unique_id y model son obligatorios
        self.edad = edad
        self.indice_riqueza = indice_riqueza
        self.agua_entubada = agua_entubada
        self.almacena_agua = almacena_agua
        self.celda_casa = celda_casa
        self.celda_trabajo = celda_trabajo
        self.destino = destino               # "0114", otro cod_muni, "FUERA" o None
        self.estado = "S"
        self.dias_en_estado = 0
        self.busco_atencion = False
        self.evaluo_hospital = False
        self.activaciones = 0                # contador para la prueba del scheduler
        self.nuevo_estado = None             # decisión pendiente (modo síncrono)

    # ------------------------------------------------------------ transiciones
    def cambiar_estado(self, nuevo):
        """Aplica una transición validándola y avisa al modelo."""
        if (self.estado, nuevo) not in TRANSICIONES_VALIDAS:
            raise ValueError(f"Transición inválida {self.estado} → {nuevo} (agente {self.unique_id})")
        viejo, self.estado = self.estado, nuevo
        self.dias_en_estado = 0
        self.model.registrar_transicion(self, viejo, nuevo)

    # ------------------------------------------------------------ decisión
    def decidir(self):
        """Evalúa las reglas del día y devuelve el nuevo estado (o None si no cambia)."""
        m = self.model
        if self.estado == "S":
            return "E" if m.sorteo_exposicion(self) else None
        if self.estado == "E":
            return "I" if ocurre(m.p_incubacion, m.rng) else None                         # R3
        if self.estado == "I":
            if self.busco_atencion and not self.evaluo_hospital:
                self.evaluo_hospital = True
                if ocurre(m.p_hospitalizacion, m.rng):                                      # R5
                    return "H"
            return "R" if ocurre(m.p_recuperacion, m.rng) else None                       # R6
        if self.estado == "H":
            return "R" if ocurre(m.p_alta, m.rng) else None                               # R7
        return None

    def aplicar(self, nuevo):
        self.dias_en_estado += 1
        if nuevo is None:
            return
        self.cambiar_estado(nuevo)
        if nuevo == "I":                                                                    # R4
            p = prob_busca_atencion(self.model.p_busca_base, self.model.efecto_riqueza, self.indice_riqueza)
            self.busco_atencion = ocurre(p, self.model.rng)

    # ------------------------------------------------------------ Mesa
    def step(self):
        self.activaciones += 1
        decision = self.decidir()
        if self.model.sincrono:
            self.nuevo_estado = decision     # se aplica en advance()
        else:
            self.aplicar(decision)

    def advance(self):
        """Solo SimultaneousActivation: aplica lo decidido en step()."""
        self.aplicar(self.nuevo_estado)
        self.nuevo_estado = None
