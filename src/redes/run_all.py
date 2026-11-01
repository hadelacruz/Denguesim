"""Corre el módulo de Redes en orden (desde la raíz):

    python src/redes/run_all.py                          # todo
    python src/redes/run_all.py --etapa base             # D1, D2, D4, D3 → centralidad.csv
    python src/redes/run_all.py --etapa intervenciones   # D5 (necesita beta_efectiva.json del ABM)

El pipeline (src/integracion/pipeline.py) llama las dos etapas por separado porque D5 necesita
la β efectiva del ABM, y el ABM necesita la calibración de Alex. --rapido se acepta y no cambia
nada (estos pasos ya son rápidos).
"""

import argparse
import subprocess
import sys

ETAPAS = {
    "base": [
        "src/redes/construir_red.py",   # D1
        "src/redes/metricas.py",        # D2 → centralidad.csv
        "src/redes/umbral.py",          # D4
        "src/redes/topologias.py",      # D3 (N2)
    ],
    "intervenciones": [
        "src/redes/intervenciones.py",  # D5 (N2, necesita beta_efectiva.json del ABM)
    ],
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--etapa", choices=list(ETAPAS), help="sin --etapa corre las dos")
    ap.add_argument("--rapido", action="store_true")
    etapa = ap.parse_args().etapa
    for paso in ETAPAS[etapa] if etapa else sum(ETAPAS.values(), []):
        print(f"\n=== {paso}")
        subprocess.run([sys.executable, paso], check=True)
