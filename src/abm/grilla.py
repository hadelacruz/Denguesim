"""D8 · Entorno: celdas de 500 m con mosquitos (arreglos de NumPy, NO agentes de Mesa).

Para cada celda c y día t:
    m_c(t) = escala_mosquitos · densidad_c(semana) / poblacion_c   [mosquitos por persona]
             (densidad = salida del autómata celular ca_mosquitos para esa semana)
    Y_c(t) = fracción de mosquitos infectados (empieza en 0)
    f_c(t) = w_dia · I_dia/N_dia + (1 − w_dia) · I_noche/N_noche
             (fracción de personas infecciosas presentes, ponderada por fase)

Actualización SÍNCRONA con doble buffer (todas las celdas leen el estado viejo
y escriben uno nuevo):
    Y_c(t+1) = clip( Y_c + a·c·f_c·(1 − Y_c) − μ·Y_c , 0, 1 )
    (nuevas infecciones de mosquitos − muerte de mosquitos infectados, por día)
Simplificación: no hay periodo de incubación extrínseco en el mosquito.
"""

import sys

import numpy as np

sys.path.insert(0, "src/datos")
from comun import PROCESSED  # noqa: E402


def cargar_densidad(grilla, anio):
    """Densidad de mosquitos (semanas del año, celdas) en el orden de la grilla."""
    ca = np.load(PROCESSED / "ca_mosquitos.npz")
    filas = ca["anio"] == anio
    semanas = ca["semana_epi"][filas]
    dens = ca["densidad"][filas][:, grilla.fila.to_numpy(), grilla.col.to_numpy()]
    return dens[np.argsort(semanas)].astype(float)


def mosquitos_por_persona(densidad, poblacion, escala):
    """m_c = escala · densidad_c / poblacion_c (0 donde no vive nadie)."""
    poblacion = np.asarray(poblacion, dtype=float)
    return np.divide(escala * densidad, poblacion, out=np.zeros_like(densidad, dtype=float), where=poblacion > 0)


def fraccion_infecciosa(I_dia, N_dia, I_noche, N_noche, w_dia):
    """f_c: fracción de personas infecciosas presentes, ponderada por fase."""
    f_dia = np.divide(I_dia, N_dia, out=np.zeros(len(N_dia)), where=N_dia > 0)
    f_noche = np.divide(I_noche, N_noche, out=np.zeros(len(N_noche)), where=N_noche > 0)
    return w_dia * f_dia + (1 - w_dia) * f_noche


def actualizar_Y(Y, f, a, c, mu):
    """Paso síncrono: devuelve un arreglo NUEVO (doble buffer), no modifica Y."""
    return np.clip(Y + a * c * f * (1 - Y) - mu * Y, 0.0, 1.0)
