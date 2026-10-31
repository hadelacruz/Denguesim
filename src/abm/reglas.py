"""D9 · Reglas SI – ENTONCES – CON probabilidad (por día), como funciones puras.

| #  | SI                                  | ENTONCES   | CON probabilidad                                     |
|----|-------------------------------------|------------|------------------------------------------------------|
| R1 | S en la celda c durante una fase    | E          | 1 − exp(−a·b·m_c·Y_c·w_fase·factor_hogar)            |
| R2 | S con destino en otro municipio     | E          | incidencia anual del destino ÷ 365 ÷ ρ  (· w_dia)    |
| R3 | E                                   | I          | 1 − exp(−σh)                                         |
| R4 | recién pasó a I                     | busca at.  | clip(base + efecto · indice_riqueza, 0, 1)           |
| R5 | I y buscó atención                  | H          | clip(fraccion_hospitalizada / prob_media_busca, 0, 1) |
| R6 | I                                   | R          | 1 − exp(−γ)                                          |
| R7 | H                                   | R          | 1 / estancia_media                                   |

Las tasas (σh, γ) se convierten a probabilidad diaria con 1 − exp(−tasa·1 día).
R2 se multiplica por w_dia porque la persona solo pasa la fase día en el
destino (la noche está en su casa y ahí aplica R1); queda anotado en el ODD.
R5 se evalúa UNA vez por caso, así la fracción total hospitalizada es
P(busca) · P(H | busca) = fraccion_hospitalizada.
"""

import numpy as np


def prob_picadura(a, b, m, Y, w_fase, factor_hogar=1.0):
    """R1: probabilidad de infección en una fase dentro de la grilla."""
    return 1.0 - np.exp(-a * b * m * Y * w_fase * factor_hogar)


def factor_hogar(almacena_agua, efecto_almacena):
    """R1: 1 + efecto si el hogar almacena agua (solo se usa en la fase noche)."""
    return 1.0 + efecto_almacena * almacena_agua


def prob_infeccion_fuera(incidencia_anual, rho, w_dia=1.0):
    """R2: incidencia anual notificada (casos/persona/año) ÷ 365 ÷ ρ, por la fracción del día."""
    return float(np.clip(incidencia_anual / 365.0 / rho * w_dia, 0.0, 1.0))


def prob_incubacion(sigma_h):
    """R3: E → I."""
    return 1.0 - np.exp(-sigma_h)


def prob_busca_atencion(base, efecto_riqueza, indice_riqueza):
    """R4: buscar atención depende del nivel socioeconómico (índice de riqueza)."""
    return float(np.clip(base + efecto_riqueza * indice_riqueza, 0.0, 1.0))


def prob_hospitalizacion(fraccion_hospitalizada, prob_media_busca):
    """R5: I → H para quien buscó atención."""
    return float(np.clip(fraccion_hospitalizada / prob_media_busca, 0.0, 1.0))


def prob_recuperacion(gamma):
    """R6: I → R."""
    return 1.0 - np.exp(-gamma)


def prob_alta(estancia_media):
    """R7: H → R."""
    return float(np.clip(1.0 / estancia_media, 0.0, 1.0))


def ocurre(p, rng):
    """Sorteo de Bernoulli: True con probabilidad p."""
    return rng.random() < p
