"""A14 · Corre el módulo de Dinámica de Sistemas en orden (desde la raíz):

    python src/sd/run_all.py                         # las dos etapas
    python src/sd/run_all.py --etapa calibracion     # A6, A1–A5, A7 → calibracion.json y validación
    python src/sd/run_all.py --etapa escenarios      # A10, A11 → casos_esperados.csv (+ A8, A13 N2)
    python src/sd/run_all.py --rapido                # prueba de humo: no recalibra si ya existe la
                                                     # calibración y omite los análisis N2 lentos

Se parte en dos etapas porque el ABM de Daniel necesita ρ de la calibración, y A13 necesita
beta_efectiva.json del ABM (el pipeline de G4 las llama en ese orden).
"""

import argparse
import subprocess
import sys
from pathlib import Path

SD = Path("data/processed/sd")
# (script, se corre con --rapido, archivo que, si ya existe, permite saltarlo con --rapido)
ETAPAS = {
    "calibracion": [
        ("src/sd/calibracion.py", True, SD / "calibracion.json"),        # A6 (~4 min)
        ("src/sd/modelo_seir_sei.py", True, None),                       # A1
        ("src/sd/vector_lluvia.py", True, None),                         # A2
        ("src/sd/fumigacion.py", True, None),                            # A3
        ("src/sd/integradores.py", True, None),                          # A4
        ("src/sd/r0.py", True, None),                                    # A5
        ("src/sd/validacion.py", True, None),                            # A7
        ("src/sd/calibracion_anual.py", False, None),                    # A6 N2: 2017–2025 (~7 min)
    ],
    "escenarios": [
        ("src/sd/metapoblacion.py", True, SD / "calibracion_municipios.csv"),  # A10 (~2 min)
        ("src/sd/escenarios.py", True, None),                            # A11 → casos_esperados.csv
        ("src/sd/sensibilidad.py", False, None),                         # A8 (N2)
        ("src/sd/validacion_municipios.py", False, None),                # A7 N2
        ("src/sd/comparacion_beta.py", True, None),                      # A13 (N2, necesita beta_efectiva.json)
        ("src/sd/poblacion_abierta.py", False, None),                    # A9 (N3, ~1 min)
        ("src/sd/orden_llegada.py", False, None),                        # A12 (N3, ~30 s)
    ],
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--etapa", choices=list(ETAPAS), help="sin --etapa corre las dos")
    ap.add_argument("--rapido", action="store_true")
    args = ap.parse_args()
    for paso, en_rapido, salida in ETAPAS[args.etapa] if args.etapa else sum(ETAPAS.values(), []):
        if args.rapido and (not en_rapido or (salida is not None and salida.exists())):
            print(f"\n=== {paso} (omitido con --rapido)")
            continue
        if paso.endswith("comparacion_beta.py") and not Path("data/processed/beta_efectiva.json").exists():
            print(f"\n=== {paso} (omitido: falta beta_efectiva.json del ABM)")
            continue
        print(f"\n=== {paso}")
        subprocess.run([sys.executable, paso], check=True)
