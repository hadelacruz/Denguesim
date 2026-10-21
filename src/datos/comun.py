"""Utilidades compartidas del módulo de datos: rutas, códigos INE, semanas
epidemiológicas, lectura de parámetros y escritura de tablas de interfaz."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd
import yaml
from epiweeks import Week

RAIZ = Path(__file__).resolve().parents[2]
RAW = RAIZ / "data" / "raw"
PROCESSED = RAIZ / "data" / "processed"
INTERIM = RAIZ / "data" / "interim"
VALIDACION = PROCESSED / "validacion"  # tablas de control de calidad
CONFIG = RAIZ / "config"

COLUMNAS_COD = ["cod_muni", "cod_i", "cod_j"]
CRS_GEO = "EPSG:4326"
# UTM 15N: proyección métrica adecuada para Guatemala central (áreas y distancias).
CRS_METRICO = "EPSG:32615"


# ---------------------------------------------------------------- parámetros
def parametros() -> dict:
    with open(CONFIG / "parametros.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def valor(seccion: str, nombre: str):
    """Devuelve el valor nominal de un parámetro de config/parametros.yaml."""
    p = parametros()[seccion][nombre]
    return p["valor"] if isinstance(p, dict) and "valor" in p else p


# ---------------------------------------------------------------- municipios
def municipios() -> pd.DataFrame:
    return pd.read_csv(CONFIG / "municipios.csv", dtype={"cod_muni": str})


def normalizar(texto: str) -> str:
    """MAYÚSCULAS sin tildes ni signos, espacios simples. Para cruzar nombres."""
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return ""
    t = str(texto)
    # Corrige UTF-8 leído como latin-1 (p. ej. 'CAHABÃ“N').
    if "Ã" in t or "Â" in t:
        try:
            t = t.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^A-Za-z0-9 ]", " ", t).upper()
    return re.sub(r"\s+", " ", t).strip()


# Variantes de nombre que aparecen en las fuentes -> nombre normalizado INE.
ALIAS = {
    "CIUDAD DE GUATEMALA": "GUATEMALA",
    "SAN MIGUEL PETAPA": "PETAPA",
    "VILLA NUEVA GUATEMALA": "VILLA NUEVA",
}


def codigo_por_nombre() -> dict[str, str]:
    m = municipios()
    mapa = {normalizar(n): c for n, c in zip(m["nombre"], m["cod_muni"])}
    mapa.update({normalizar(n): c for n, c in zip(m["nombre_osm"], m["cod_muni"])})
    for alias, oficial in ALIAS.items():
        mapa[alias] = mapa[oficial]
    return mapa


def a_codigo(nombre: str) -> str | None:
    return codigo_por_nombre().get(ALIAS.get(normalizar(nombre), normalizar(nombre)))


# ---------------------------------------------------- semanas epidemiológicas
def semana_epi(fecha) -> tuple[int, int]:
    """(año, semana) epidemiológica, semanas domingo-sábado (OPS/CDC)."""
    d = pd.Timestamp(fecha).date()
    w = Week.fromdate(d, system="CDC")
    return w.year, w.week


def agregar_semana_epi(df: pd.DataFrame, col_fecha: str = "fecha") -> pd.DataFrame:
    fechas = pd.to_datetime(df[col_fecha])
    unicas = pd.Series(fechas.dt.date.unique())
    tabla = {d: Week.fromdate(d, system="CDC") for d in unicas}
    df = df.copy()
    df["anio"] = [tabla[d].year for d in fechas.dt.date]
    df["semana_epi"] = [tabla[d].week for d in fechas.dt.date]
    return df


def inicio_semana(anio: int, semana: int) -> date:
    return Week(int(anio), int(semana), system="CDC").startdate()


# ----------------------------------------------------------------- escritura
def guardar(df: pd.DataFrame, nombre: str, columnas: list[str] | None = None) -> Path:
    """Escribe una tabla de interfaz en data/processed/ con columnas fijas."""
    PROCESSED.mkdir(parents=True, exist_ok=True)
    if columnas is not None:
        faltan = [c for c in columnas if c not in df.columns]
        if faltan:
            raise ValueError(f"{nombre}: faltan columnas del contrato {faltan}")
        df = df[columnas + [c for c in df.columns if c not in columnas]]
    ruta = PROCESSED / nombre
    df.to_csv(ruta, index=False, encoding="utf-8")
    print(f"  -> {ruta.relative_to(RAIZ)} ({len(df)} filas)")
    return ruta


def guardar_json(obj, nombre: str) -> Path:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    ruta = PROCESSED / nombre
    ruta.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  -> {ruta.relative_to(RAIZ)}")
    return ruta


def leer_procesado(nombre: str) -> pd.DataFrame:
    """Lee una tabla de data/processed/ conservando los ceros de cod_muni."""
    return pd.read_csv(PROCESSED / nombre, dtype={c: str for c in COLUMNAS_COD})


# ------------------------------------------------- parámetros derivados de datos
PARAM_DATOS = PROCESSED / "parametros_datos.json"


def registrar_parametro(seccion: str, nombre: str, valor, unidad: str = "", nota: str = "") -> None:
    """Guarda en data/processed/parametros_datos.json un parámetro estimado con
    los datos (los de parametros.yaml con `fuente: datos`)."""
    PROCESSED.mkdir(parents=True, exist_ok=True)
    datos = json.loads(PARAM_DATOS.read_text(encoding="utf-8")) if PARAM_DATOS.exists() else {}
    if hasattr(valor, "item"):
        valor = valor.item()
    datos.setdefault(seccion, {})[nombre] = {"valor": valor, "unidad": unidad, "nota": nota}
    PARAM_DATOS.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")


def parametro(seccion: str, nombre: str):
    """Valor de un parámetro: primero el estimado con datos, si no el de YAML."""
    if PARAM_DATOS.exists():
        d = json.loads(PARAM_DATOS.read_text(encoding="utf-8")).get(seccion, {}).get(nombre)
        if d is not None and d.get("valor") is not None:
            return d["valor"]
    return valor(seccion, nombre)
