"""R12 · Corre todo el módulo de Salud en orden (desde la raíz):

    python src/salud/run_all.py            # completo (~1 min)
    python src/salud/run_all.py --rapido   # pocas réplicas y muestras (prueba de humo)

Necesita data/processed/casos_esperados.csv y data/processed/sd/calibracion.json (Alex).
"""

import argparse
import subprocess
import sys

PASOS = [
    ("src/salud/generadores.py", False),        # R1
    ("src/salud/des_camas.py", True),           # R4 + R5 → ocupacion_camas.csv
    ("src/salud/insumos.py", False),            # R6 → inventario.csv
    ("src/salud/estabilidad.py", False),        # R7 → mapa_estabilidad.csv
    ("src/salud/robustez.py", True),            # R9 → robustez.csv
    ("src/salud/notificacion.py", False),       # R2 (N2)
    ("src/salud/estancia_weibull.py", False),   # R3 (N2)
    ("src/salud/politicas_insumos.py", False),  # R8 (N2)
]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true", help="pocas réplicas y muestras")
    rapido = ap.parse_args().rapido
    for paso, acepta_rapido in PASOS:
        print(f"\n=== {paso}")
        subprocess.run([sys.executable, paso] + (["--rapido"] if rapido and acepta_rapido else []), check=True)
