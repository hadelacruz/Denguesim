"""Regenera todas las tablas del módulo de datos desde data/raw/.

Uso (desde la raíz del repo):
    python src/datos/descargar.py      # 1) una vez, baja los datos crudos
    python src/datos/run_all.py        # 2) procesa todo → data/processed/
    python src/datos/run_all.py --sin-red   # omite la red vial (paso más lento)

Orden de los pasos (cada uno usa salidas del anterior):
    limites → censo → boletines → casos → clima → hospitales → raster → red vial →
    gravitacional → autómata → diccionario y verificación del contrato
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / "sig"))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sin-red", action="store_true", help="no recalcula la red vial (usa distancias.csv existente)")
    a = p.parse_args()

    import automata_mosquitos
    import boletines
    import casos
    import censo
    import clima
    import contrato
    import diccionario
    import gravitacional
    import hospitales
    import limites
    import raster_poblacion
    import red_vial

    pasos = [
        ("límites municipales", limites.main),
        ("censo 2018 y población", censo.main),
        ("boletines MSPAS (digitalización)", boletines.main),
        ("casos de dengue", casos.main),
        ("clima", clima.main),
        ("hospitales", hospitales.main),
        ("ráster WorldPop y grilla piloto", raster_poblacion.main),
    ]
    if not a.sin_red:
        pasos.append(("red vial y distancias", red_vial.main))
    pasos += [
        ("modelo gravitacional", gravitacional.main),
        ("autómata celular", automata_mosquitos.main),
        ("diccionario de datos", diccionario.main),
        ("verificación del contrato", contrato.main),
    ]
    t0 = time.time()
    for nombre, fn in pasos:
        t = time.time()
        print(f"\n=== {nombre} ===")
        fn()
        print(f"    ({time.time() - t:.1f} s)")
    print(f"\nTodo listo en {time.time() - t0:.0f} s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
