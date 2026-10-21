"""Contrato de interfaces del módulo de datos y su verificación automática.

Cada tabla de interfaz que produce el módulo de datos se valida contra las columnas
acordadas para cada tabla y contra reglas básicas de consistencia. Lo usa
``run_all.py`` (último paso) y ``tests/test_contrato_datos.py``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import PROCESSED, leer_procesado, municipios  # noqa: E402

CONTRATO = {
    "casos_semanales.csv": ["cod_muni", "anio", "semana_epi", "casos"],
    "poblacion.csv": ["cod_muni", "nombre", "poblacion", "area_km2", "densidad"],
    "clima_semanal.csv": ["cod_muni", "anio", "semana_epi", "lluvia_mm", "temp_c"],
    "atributos_hogar.csv": ["cod_muni", "ingreso", "agua_entubada", "almacena_agua"],
    "hospitales.csv": ["id_hosp", "nombre", "cod_muni", "lat", "lon", "camas"],
    "distancias.csv": ["cod_i", "cod_j", "dist_km", "tiempo_min"],
    "flujos_od.csv": ["cod_i", "cod_j", "flujo_diario"],
}
JSON = {"sigma_hogar.json": ["variables", "medias", "covarianza"]}


def verificar() -> list[str]:
    errores: list[str] = []
    cods = set(municipios().cod_muni)
    for nombre, cols in CONTRATO.items():
        ruta = PROCESSED / nombre
        if not ruta.exists():
            errores.append(f"{nombre}: no existe")
            continue
        df = leer_procesado(nombre)
        faltan = [c for c in cols if c not in df.columns]
        if faltan:
            errores.append(f"{nombre}: faltan columnas {faltan}")
            continue
        if list(df.columns[: len(cols)]) != cols:
            errores.append(f"{nombre}: las columnas del contrato no van primero y en orden")
        for c in ("cod_muni", "cod_i", "cod_j"):
            if c in df.columns:
                malos = set(df[c].dropna()) - cods
                if malos:
                    errores.append(f"{nombre}: códigos INE desconocidos en {c}: {sorted(malos)[:5]}")
        if "semana_epi" in df.columns and not df.semana_epi.between(1, 53).all():
            errores.append(f"{nombre}: semana_epi fuera de 1..53")
        llave = {"casos_semanales.csv": ["cod_muni", "anio", "semana_epi"], "clima_semanal.csv": ["cod_muni", "anio", "semana_epi"],
                 "poblacion.csv": ["cod_muni"], "distancias.csv": ["cod_i", "cod_j"], "flujos_od.csv": ["cod_i", "cod_j"]}.get(nombre)
        if llave and df.duplicated(llave).any():
            errores.append(f"{nombre}: filas duplicadas en la llave {llave}")
        numericas = [c for c in cols if c not in ("cod_muni", "cod_i", "cod_j", "nombre", "id_hosp", "camas")]
        for c in numericas:
            if not pd.api.types.is_numeric_dtype(df[c]):
                errores.append(f"{nombre}: {c} no es numérica")
            elif (df[c].dropna() < 0).any() and c not in ("lat", "lon", "ingreso"):
                errores.append(f"{nombre}: {c} tiene valores negativos")
    for nombre, llaves in JSON.items():
        ruta = PROCESSED / nombre
        if not ruta.exists():
            errores.append(f"{nombre}: no existe")
            continue
        obj = json.loads(ruta.read_text(encoding="utf-8"))
        faltan = [k for k in llaves if k not in obj]
        if faltan:
            errores.append(f"{nombre}: faltan llaves {faltan}")
            continue
        n = len(obj["variables"])
        if len(obj["medias"]) != n or len(obj["covarianza"]) != n or any(len(f) != n for f in obj["covarianza"]):
            errores.append(f"{nombre}: dimensiones inconsistentes")
    return errores


def main() -> None:
    errores = verificar()
    if errores:
        print("  CONTRATO CON ERRORES:")
        for e in errores:
            print("   -", e)
        raise SystemExit(1)
    print(f"  contrato OK: {len(CONTRATO) + len(JSON)} tablas de interfaz verificadas")


if __name__ == "__main__":
    main()
