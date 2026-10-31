"""Corre todo el módulo de Redes en orden (desde la raíz):  python src/redes/run_all.py"""

import subprocess
import sys

PASOS = [
    "src/redes/construir_red.py",   # D1
    "src/redes/metricas.py",        # D2 → centralidad.csv
    "src/redes/umbral.py",          # D4
    "src/redes/topologias.py",      # D3 (N2)
    "src/redes/intervenciones.py",  # D5 (N2, necesita beta_efectiva.json del ABM)
]

if __name__ == "__main__":
    for paso in PASOS:
        print(f"\n=== {paso}")
        subprocess.run([sys.executable, paso], check=True)
