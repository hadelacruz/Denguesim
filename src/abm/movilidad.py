"""D10 · Movilidad diaria en dos fases.

  - Fase día:   destino 0114 → celda_trabajo; destino externo → "fuera" (aplica R2);
                sin destino → celda_casa.
  - Fase noche: todos en celda_casa.
Los hospitalizados (H) no están presentes en ninguna celda.

FUERA = −1 marca a quien está fuera de la grilla durante el día.
"""

import numpy as np

FUERA = -1
COD_PILOTO = "0114"


def celda_dia(destino, celda_casa, celda_trabajo):
    """Celda donde pasa la fase día (FUERA si trabaja/estudia en otro municipio)."""
    if destino is None:
        return celda_casa
    if destino == COD_PILOTO:
        return celda_trabajo
    return FUERA


def celda_noche(celda_casa):
    """En la noche todos están en su casa."""
    return celda_casa


def ocupacion(celdas, estados, n_celdas, codigo_I, codigo_H):
    """Personas e infecciosos presentes por celda en una fase.

    celdas: celda de cada agente en la fase (FUERA = −1); estados: código de estado.
    """
    presente = (celdas >= 0) & (estados != codigo_H)
    personas = np.bincount(celdas[presente], minlength=n_celdas).astype(float)
    infecciosos = np.bincount(celdas[presente & (estados == codigo_I)], minlength=n_celdas).astype(float)
    return personas, infecciosos
