"""Corre todo el módulo ABM en orden (desde la raíz):  python src/abm/run_all.py

Requiere data/processed/sd/calibracion.json (ρ de Alex). Si abm.escala_mosquitos
es null en el YAML, corridas.py la calibra primero (o con --recalibrar).
"""

import subprocess
import sys

PASOS = [
    "src/abm/inicializacion.py",        # D7: validación de atributos
    "src/abm/corridas.py",              # D12: calibración, corridas y bootstrap
    "src/abm/beta_efectiva.py",         # D13 → beta_efectiva.json
    "src/abm/experimento_scheduler.py", # D11 (N2)
]

if __name__ == "__main__":
    for paso in PASOS:
        print(f"\n=== {paso}")
        subprocess.run([sys.executable, paso], check=True)
