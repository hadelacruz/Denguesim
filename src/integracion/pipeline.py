"""G4 · Pipeline de punta a punta de DengueSim GT (desde la raíz):

    python src/integracion/pipeline.py                     # todas las etapas
    python src/integracion/pipeline.py --rapido            # prueba de humo (pocas corridas y muestras)
    python src/integracion/pipeline.py --solo salud        # una sola etapa
    python src/integracion/pipeline.py --desde sd_escenarios
    python src/integracion/pipeline.py --con-datos         # corre antes src/datos/run_all.py
                                                           # (~30 min y ~550 MB de descarga)

Orden de las etapas: el ABM necesita ρ de la calibración de SD, y las intervenciones
de red y la comparación de β necesitan beta_efectiva.json del ABM.

Cada etapa llama al comando de su módulo, registra la hora de inicio y fin, y si falla
detiene el pipeline con un mensaje claro. Al final verifica el contrato: las ocho tablas
de los módulos existen, con columnas exactas y cod_muni como texto de 4 dígitos.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

PROCESSED = Path("data/processed")
ETAPAS = [
    ("redes_base", ["src/redes/run_all.py", "--etapa", "base"]),
    ("sd_calibracion", ["src/sd/run_all.py", "--etapa", "calibracion"]),
    ("abm", ["src/abm/run_all.py"]),
    ("redes_intervenciones", ["src/redes/run_all.py", "--etapa", "intervenciones"]),
    ("sd_escenarios", ["src/sd/run_all.py", "--etapa", "escenarios"]),
    ("salud", ["src/salud/run_all.py"]),
    ("sig", ["src/sig/aplicado_run_all.py"]),
    ("resumenes", ["src/integracion/resumenes.py"]),
]
NOMBRES = [e for e, _ in ETAPAS]
CONTRATO = {
    "centralidad.csv": ["cod_muni", "grado", "intermediacion", "eigenvector"],
    "beta_efectiva.json": ["beta", "ic_inf", "ic_sup"],
    "casos_esperados.csv": ["escenario", "corrida", "cod_muni", "dia", "S", "E", "I", "R", "nuevos"],
    "ocupacion_camas.csv": ["escenario", "id_hosp", "dia", "ocupadas", "en_cola"],
    "inventario.csv": ["escenario", "id_hosp", "dia", "I", "P"],
    "robustez.csv": ["escenario", "metrica", "media", "ic_inf", "ic_sup", "prob_mejor"],
    "unidades_mclp.csv": ["p", "cod_celda", "lat", "lon", "poblacion_cubierta"],
    "ranking_riesgo.csv": ["cod_muni", "riesgo_casos", "centralidad", "puntaje", "posicion"],
}
# Comandos que aceptan --rapido (el de resúmenes no lo necesita).
ACEPTAN_RAPIDO = {"redes_base", "sd_calibracion", "abm", "redes_intervenciones", "sd_escenarios", "salud", "sig"}


def correr_etapa(nombre, comando, rapido):
    argumentos = comando + (["--rapido"] if rapido and nombre in ACEPTAN_RAPIDO else [])
    inicio = time.time()
    print(f"\n[{datetime.now():%H:%M:%S}] ▶ {nombre}: python {' '.join(argumentos)}", flush=True)
    r = subprocess.run([sys.executable] + argumentos)
    duracion = time.time() - inicio
    if r.returncode != 0:
        print(f"\n✖ La etapa «{nombre}» falló (código {r.returncode}) tras {duracion:.0f} s. "
              f"Revisa el error de arriba; para retomar desde aquí: --desde {nombre}")
        sys.exit(r.returncode)
    print(f"[{datetime.now():%H:%M:%S}] ✔ {nombre} terminó en {duracion:.0f} s", flush=True)
    return {"etapa": nombre, "segundos": round(duracion, 1)}


def verificar_contrato():
    """Lista de problemas del contrato (vacía si todo está bien)."""
    problemas = []
    for nombre, columnas in CONTRATO.items():
        ruta = PROCESSED / nombre
        if not ruta.exists():
            problemas.append(f"falta {nombre}")
            continue
        if nombre.endswith(".json"):
            llaves = list(json.loads(ruta.read_text(encoding="utf-8")))
            if sorted(llaves) != sorted(columnas):
                problemas.append(f"{nombre}: llaves {llaves}")
            continue
        df = pd.read_csv(ruta, dtype={"cod_muni": str}, nrows=200_000)
        if list(df.columns) != columnas:
            problemas.append(f"{nombre}: columnas {list(df.columns)}")
        if "cod_muni" in df and not df.cod_muni.str.fullmatch(r"\d{4}").all():
            problemas.append(f"{nombre}: cod_muni no es texto de 4 dígitos")
    return problemas


def main():
    ap = argparse.ArgumentParser(description="Pipeline de DengueSim GT")
    ap.add_argument("--solo", choices=NOMBRES, help="corre solo esta etapa")
    ap.add_argument("--desde", choices=NOMBRES, help="corre desde esta etapa hasta el final")
    ap.add_argument("--rapido", action="store_true", help="pocas corridas y muestras (prueba de humo)")
    ap.add_argument("--con-datos", action="store_true", help="corre antes src/datos/run_all.py (~30 min, ~550 MB)")
    args = ap.parse_args()

    etapas = ETAPAS
    if args.solo:
        etapas = [e for e in ETAPAS if e[0] == args.solo]
    elif args.desde:
        etapas = ETAPAS[NOMBRES.index(args.desde):]
    if args.con_datos:
        etapas = [("datos", ["src/datos/run_all.py"])] + etapas

    registro = [correr_etapa(nombre, comando, args.rapido) for nombre, comando in etapas]
    print("\nTiempos por etapa:\n" + pd.DataFrame(registro).to_string(index=False))
    problemas = verificar_contrato()
    if problemas:
        print("\n✖ Contrato incompleto:\n  - " + "\n  - ".join(problemas))
        sys.exit(1)
    print(f"\n✔ Contrato verificado: las {len(CONTRATO)} tablas de los módulos existen con sus columnas exactas.")


if __name__ == "__main__":
    main()
