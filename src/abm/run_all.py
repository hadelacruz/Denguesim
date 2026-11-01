"""Corre todo el módulo ABM en orden (desde la raíz):  python src/abm/run_all.py [--rapido]

Requiere data/processed/sd/calibracion.json (ρ de Alex). Si abm.escala_mosquitos
es null en el YAML, corridas.py la calibra primero (o con --recalibrar).
Con --rapido se omite el experimento de scheduler (N2, 60 corridas extra).
validacion_edad.py (N3) es rápido y siempre se corre.
"""

import argparse
import subprocess
import sys

PASOS = [
    ("src/abm/inicializacion.py", True),         # D7: validación de atributos
    ("src/abm/corridas.py", True),               # D12: calibración, corridas y bootstrap
    ("src/abm/beta_efectiva.py", True),          # D13 → beta_efectiva.json
    ("src/abm/experimento_scheduler.py", False), # D11 (N2)
    ("src/abm/validacion_edad.py", True),        # N3: validación por edad (usa edades_infectados.csv)
]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true", help="omite el experimento de scheduler")
    rapido = ap.parse_args().rapido
    for paso, en_rapido in PASOS:
        if rapido and not en_rapido:
            print(f"\n=== {paso} (omitido con --rapido)")
            continue
        print(f"\n=== {paso}")
        subprocess.run([sys.executable, paso], check=True)
