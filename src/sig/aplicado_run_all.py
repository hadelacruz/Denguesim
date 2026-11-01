"""Corre el SIG aplicado (Gerardo) en orden (desde la raíz):  python src/sig/aplicado_run_all.py

G1 isocronas, G2 MCLP y G3 ranking de riesgo. No toca los scripts de Juan Diego en src/sig/.
Necesita casos_esperados.csv (Alex) y centralidad.csv (Daniel). Acepta --rapido (no cambia nada:
los tres pasos ya tardan pocos segundos; existe para que el pipeline lo pase a todos los módulos).
"""

import subprocess
import sys

PASOS = [
    "src/sig/isocronas.py",        # G1
    "src/sig/mclp.py",             # G2 → unidades_mclp.csv
    "src/sig/ranking_riesgo.py",   # G3 → ranking_riesgo.csv
]

if __name__ == "__main__":
    for paso in PASOS:
        print(f"\n=== {paso}")
        subprocess.run([sys.executable, paso], check=True)
