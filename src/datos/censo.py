"""Censo 2018 (INE) y proyecciones de población: población, atributos de hogar,
matriz Σ para Cholesky y matriz origen-destino observada de trabajo y estudio.

Variables usadas del Censo 2018 (diccionarios en el ZIP del INE):
  HOGAR    PCH4  fuente principal de agua (1–2 = tubería de red)
           PCH9_F ¿cuenta con tanque o depósito de agua?
           PCH9_A..M bienes del hogar, PCH5 sanitario, PCH8 alumbrado,
           PCH10 basura, PCH12 dormitorios, PCH14 combustible, TOTAL_PERS, Long/Lat del lugar poblado
  VIVIENDA PCV2 material de paredes, PCV5 material del piso
  PERSONA  PCP5 parentesco, PCP6 sexo, PCP7 edad, ANEDUCA años de estudio,
           POCUPA ocupado, TRABAJAGEO municipio de trabajo, PCP18 asiste a estudiar, ESTUDIAGEO municipio de estudio

El Censo no pregunta ingreso. ``ingreso`` es un ÍNDICE DE RIQUEZA (proxy):
primer componente principal de bienes y condiciones de la vivienda más los
años de estudio de la jefatura (Filmer & Pritchett, 2001), estandarizado
(media 0, desviación 1 en el departamento).

``almacena_agua`` = 1 si el hogar declara tanque/depósito de agua (PCH9_F) o
si su fuente de agua obliga a almacenarla (chorro público, lluvia, camión o tonel).

Salidas (data/processed/):
  poblacion.csv            cod_muni, nombre, poblacion, area_km2, densidad (+ censo 2018, año de referencia)
  poblacion_anual.csv      cod_muni, anio, poblacion                 (proyección INE/SIGSA 2015-2026)
  poblacion_edad.csv       cod_muni, anio, grupo_edad, sexo, poblacion
  atributos_hogar.csv      cod_muni, ingreso, agua_entubada, almacena_agua (+ muestra con factor de expansión)
  atributos_municipio.csv  proporciones e índice medio por municipio
  lugares_poblados.csv     coordenadas y atributos medios por lugar poblado (para asignar a celdas)
  sigma_hogar.json         medias, covarianza observada y correlación latente + umbrales para Cholesky
  od_censo.csv             cod_i, cod_j, trabajadores, estudiantes, total  (viajes diarios observados)
"""

from __future__ import annotations

import gzip
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import optimize, stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import (  # noqa: E402
    INTERIM, PROCESSED, RAW, guardar, guardar_json, municipios, parametro, registrar_parametro,
)

ZIP = RAW / "censo" / "censo2018_db_csv.zip"
PROY = RAW / "censo" / "sigsa_proyeccion_poblacion_2015_2026.csv"
DEPTO = 1
SEMILLA_MUESTRA = None  # se lee de config/semillas.yaml (datos.muestra_hogares_censo)
FRACCION_MUESTRA = 0.10

COLS_PERSONA = ["DEPARTAMENTO", "MUNICIPIO", "NUM_VIVIENDA", "NUM_HOGAR", "PCP5", "PCP6", "PCP7",
                "POCUPA", "PCP33", "TRABAJAGEO", "PCP18", "PCP20", "ESTUDIAGEO", "ANEDUCA"]
BIENES = ["PCH9_A", "PCH9_B", "PCH9_C", "PCH9_D", "PCH9_E", "PCH9_G", "PCH9_H", "PCH9_I", "PCH9_K", "PCH9_L", "PCH9_M"]
COLS_HOGAR = ["DEPARTAMENTO", "MUNICIPIO", "LUGAR_POBLADO", "NOMBRE_LUGAR_POBLADO", "NUM_VIVIENDA", "NUM_HOGAR", "AREA",
              "PCH4", "PCH5", "PCH8", "PCH9_F", "PCH10", "PCH12", "PCH14", "TOTAL_PERS", "Long", "Lat"] + BIENES
COLS_VIVIENDA = ["DEPARTAMENTO", "MUNICIPIO", "NUM_VIVIENDA", "PCV2", "PCV5"]


# --------------------------------------------------------------- lectura
def _nombre_en_zip(z: zipfile.ZipFile, base: str) -> str:
    return next(n for n in z.namelist() if Path(n).name.replace(" ", "").upper().startswith(base.replace(" ", "").upper()))


def _leer_filtrado(base: str, cols: list[str], cache: str) -> pd.DataFrame:
    """Lee una tabla del ZIP del Censo en bloques y conserva el departamento 1.
    Guarda una copia filtrada en data/interim/ para no repetir la lectura."""
    ruta_cache = INTERIM / cache
    if ruta_cache.exists():
        return pd.read_csv(ruta_cache, low_memory=False)
    INTERIM.mkdir(parents=True, exist_ok=True)
    partes = []
    with zipfile.ZipFile(ZIP) as z, z.open(_nombre_en_zip(z, base)) as f:
        lector = pd.read_csv(f, usecols=lambda c: c.replace("﻿", "") in cols, chunksize=1_000_000,
                             encoding="utf-8-sig", na_values=[" ", ""], low_memory=False)
        for bloque in lector:
            bloque.columns = [c.replace("﻿", "") for c in bloque.columns]
            partes.append(bloque[bloque["DEPARTAMENTO"] == DEPTO])
    df = pd.concat(partes, ignore_index=True)
    df.to_csv(ruta_cache, index=False, compression="gzip")
    return df


def _cod(x) -> pd.Series:
    return pd.Series(x).astype("Int64").astype(str).str.zfill(4)


# ----------------------------------------------------------- población
def proyecciones() -> pd.DataFrame:
    p = pd.read_csv(PROY, encoding="utf-8-sig")
    p = p[p.cod_depto == DEPTO].copy()
    p["cod_muni"] = (p.cod_depto * 100 + p.cod_mun).astype(str).str.zfill(4)
    return p


def tablas_poblacion(persona: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    m = municipios()
    lim = __import__("geopandas").read_file(PROCESSED / "limites_municipios.geojson")[["cod_muni", "area_km2"]]
    censo = persona.groupby(_cod(persona.MUNICIPIO).values).size().rename("poblacion_censo2018")
    p = proyecciones()
    anual = p.groupby(["cod_muni", "anio"], as_index=False).poblacion.sum()
    edad = p.groupby(["cod_muni", "anio", "grupo_edad", "sexo"], as_index=False).poblacion.sum()
    anio_ref = int(parametro("poblacion", "anio_referencia"))
    ref = anual[anual.anio == anio_ref].set_index("cod_muni").poblacion.rename("poblacion")
    area_salud = p.drop_duplicates("cod_muni").set_index("cod_muni").area_salud
    pob = m[["cod_muni", "nombre"]].set_index("cod_muni").join([ref, censo, area_salud]).reset_index()
    pob = pob.merge(lim, on="cod_muni")
    pob["densidad"] = pob.poblacion / pob.area_km2
    pob["anio_poblacion"] = anio_ref
    pob["area_km2"] = pob.area_km2.round(3)
    pob["densidad"] = pob.densidad.round(1)
    return pob, anual, edad


# ------------------------------------------------------- atributos del hogar
def construir_hogares(persona: pd.DataFrame) -> pd.DataFrame:
    h = _leer_filtrado("HOGAR_BDP", COLS_HOGAR, "censo_hogar_guatemala.csv.gz")
    v = _leer_filtrado("VIVIENDA_BDP", COLS_VIVIENDA, "censo_vivienda_guatemala.csv.gz")
    v = v.drop_duplicates(["MUNICIPIO", "NUM_VIVIENDA"])
    h = h.merge(v[["MUNICIPIO", "NUM_VIVIENDA", "PCV2", "PCV5"]], on=["MUNICIPIO", "NUM_VIVIENDA"], how="left")
    jefe = persona[persona.PCP5 == 1][["MUNICIPIO", "NUM_VIVIENDA", "NUM_HOGAR", "ANEDUCA", "PCP7"]]
    jefe = jefe.drop_duplicates(["MUNICIPIO", "NUM_VIVIENDA", "NUM_HOGAR"])
    h = h.merge(jefe, on=["MUNICIPIO", "NUM_VIVIENDA", "NUM_HOGAR"], how="left")

    h["cod_muni"] = _cod(h.MUNICIPIO).values
    h["agua_entubada"] = h.PCH4.isin([1, 2]).astype(int)
    h["tiene_deposito"] = (h.PCH9_F == 1).astype(int)
    h["almacena_agua"] = ((h.PCH9_F == 1) | h.PCH4.isin([3, 5, 9])).astype(int)

    ind = pd.DataFrame({b: (h[b] == 1).astype(float) for b in BIENES})
    ind["electricidad"] = (h.PCH8 == 1).astype(float)
    ind["inodoro_drenaje"] = (h.PCH5 == 1).astype(float)
    ind["cocina_gas_elec"] = h.PCH14.isin([1, 3]).astype(float)
    ind["basura_servicio"] = h.PCH10.isin([1, 2]).astype(float)
    ind["piso_no_tierra"] = np.where(h.PCV5.isna(), np.nan, (h.PCV5 != 7).astype(float))
    ind["paredes_solidas"] = np.where(h.PCV2.isna(), np.nan, h.PCV2.isin([1, 2, 3]).astype(float))
    ind["personas_por_dormitorio"] = -(h.TOTAL_PERS / h.PCH12.clip(lower=1))  # signo: más hacinamiento = menos riqueza
    anios = pd.to_numeric(h.ANEDUCA, errors="coerce")
    ind["anios_estudio_jefatura"] = anios.where(anios <= 30)
    # Imputación por mediana municipal de los pocos faltantes (se reporta cuántos).
    faltantes = int(ind.isna().any(axis=1).sum())
    ind = ind.groupby(h.cod_muni).transform(lambda s: s.fillna(s.median())).fillna(ind.median())
    z = (ind - ind.mean()) / ind.std(ddof=0)
    valores, vectores = np.linalg.eigh(np.cov(z.T))
    pc1 = vectores[:, -1]
    if pc1[list(z.columns).index("PCH9_H")] < 0:  # orientación: computadora suma riqueza
        pc1 = -pc1
    indice = z.to_numpy() @ pc1
    h["ingreso"] = (indice - indice.mean()) / indice.std()
    h.attrs["varianza_pc1"] = float(valores[-1] / valores.sum())
    h.attrs["cargas_pc1"] = dict(zip(z.columns, np.round(pc1, 3)))
    h.attrs["hogares_imputados"] = faltantes
    return h


# ------------------------------------------- correlación latente (Cholesky)
def _tetracorica(x: np.ndarray, y: np.ndarray) -> float:
    px, py, p11 = x.mean(), y.mean(), (x * y).mean()
    zx, zy = stats.norm.ppf(1 - px), stats.norm.ppf(1 - py)

    def f(r):
        mvn = stats.multivariate_normal([0, 0], [[1, r], [r, 1]])
        # P(X*>zx, Y*>zy) = 1 - Φ(zx) - Φ(zy) + Φ2(zx, zy)
        return 1 - stats.norm.cdf(zx) - stats.norm.cdf(zy) + mvn.cdf([zx, zy]) - p11

    return float(optimize.brentq(f, -0.999, 0.999))


def _poliserial(cont: np.ndarray, binaria: np.ndarray) -> float:
    p = binaria.mean()
    r_pb = np.corrcoef(cont, binaria)[0, 1]
    return float(np.clip(r_pb * np.sqrt(p * (1 - p)) / stats.norm.pdf(stats.norm.ppf(p)), -0.999, 0.999))


def sigma(h: pd.DataFrame) -> dict:
    vars_ = ["ingreso", "agua_entubada", "almacena_agua"]
    X = h[vars_].to_numpy(float)

    def bloque(Xb: np.ndarray) -> dict:
        medias = Xb.mean(axis=0)
        cov = np.cov(Xb.T)
        R = np.eye(3)
        R[0, 1] = R[1, 0] = _poliserial(Xb[:, 0], Xb[:, 1])
        R[0, 2] = R[2, 0] = _poliserial(Xb[:, 0], Xb[:, 2])
        R[1, 2] = R[2, 1] = _tetracorica(Xb[:, 1], Xb[:, 2])
        # Asegura que sea definida positiva (requisito de Cholesky).
        w, V = np.linalg.eigh(R)
        if w.min() <= 1e-6:
            R = V @ np.diag(np.maximum(w, 1e-6)) @ V.T
            d = np.sqrt(np.diag(R))
            R = R / np.outer(d, d)
        return {
            "n_hogares": int(len(Xb)),
            "medias": np.round(medias, 6).tolist(),
            "covarianza": np.round(cov, 6).tolist(),
            "latente": {
                "correlacion": np.round(R, 6).tolist(),
                "umbrales": [None, float(stats.norm.ppf(1 - medias[1])), float(stats.norm.ppf(1 - medias[2]))],
                "cholesky_L": np.round(np.linalg.cholesky(R), 6).tolist(),
            },
        }

    total = bloque(X)
    por_muni = {c: bloque(g[vars_].to_numpy(float)) for c, g in h.groupby("cod_muni")}
    return {
        "descripcion": (
            "Atributos del hogar, Censo 2018, departamento de Guatemala. 'ingreso' es un índice de riqueza "
            "estandarizado (proxy, el Censo no pregunta ingreso). 'medias' y 'covarianza' son los momentos "
            "observados de (ingreso, agua_entubada, almacena_agua). Para generar agentes con Cholesky: "
            "Z ~ N(0, latente.correlacion) con Z = L·u; ingreso = Z0; agua_entubada = 1 si Z1 > umbrales[1]; "
            "almacena_agua = 1 si Z2 > umbrales[2]. Así se reproducen las proporciones y correlaciones observadas."
        ),
        "variables": vars_,
        **total,
        "por_municipio": por_muni,
        "indice_riqueza": {
            "metodo": "PCA (primer componente) de indicadores estandarizados, Filmer & Pritchett (2001)",
            "varianza_explicada_pc1": round(h.attrs["varianza_pc1"], 4),
            "cargas": h.attrs["cargas_pc1"],
            "hogares_con_imputacion": h.attrs["hogares_imputados"],
        },
    }


# ------------------------------------------------ origen-destino observado
def od_censo(persona: pd.DataFrame) -> pd.DataFrame:
    cods = set(municipios().cod_muni)
    origen = _cod(persona.MUNICIPIO).values
    trab = persona.POCUPA.eq(1) & persona.TRABAJAGEO.notna()
    est = persona.PCP18.eq(1) & persona.ESTUDIAGEO.notna()
    filas = []
    for tipo, mask, col in [("trabajadores", trab, "TRABAJAGEO"), ("estudiantes", est, "ESTUDIAGEO")]:
        dest = _cod(persona.loc[mask, col]).values
        t = pd.DataFrame({"cod_i": origen[mask.to_numpy()], "cod_j": dest})
        t["cod_j"] = np.where(pd.Series(t.cod_j).isin(cods), t.cod_j, "FUERA")
        filas.append(t.value_counts().rename(tipo))
    od = pd.concat(filas, axis=1).fillna(0).astype(int).reset_index()
    od["total"] = od.trabajadores + od.estudiantes
    return od.sort_values(["cod_i", "cod_j"]).reset_index(drop=True)


# ----------------------------------------------------------------- main
def main() -> None:
    print("[censo] INE Censo 2018 + proyecciones SIGSA")
    persona = _leer_filtrado("PERSONA", COLS_PERSONA, "censo_persona_guatemala.csv.gz")
    print(f"  personas en el departamento: {len(persona):,}")

    pob, anual, edad = tablas_poblacion(persona)
    guardar(pob, "poblacion.csv", ["cod_muni", "nombre", "poblacion", "area_km2", "densidad"])
    guardar(anual, "poblacion_anual.csv", ["cod_muni", "anio", "poblacion"])
    guardar(edad, "poblacion_edad.csv", ["cod_muni", "anio", "grupo_edad", "sexo", "poblacion"])

    h = construir_hogares(persona)
    print(f"  hogares: {len(h):,}; varianza explicada por el índice de riqueza: {h.attrs['varianza_pc1']:.1%}")
    import yaml

    semilla = yaml.safe_load((PROCESSED.parents[1] / "config" / "semillas.yaml").read_text(encoding="utf-8"))["datos"]["muestra_hogares_censo"]
    muestra = h.groupby("cod_muni", group_keys=False).sample(frac=FRACCION_MUESTRA, random_state=semilla)
    muestra = muestra.assign(factor_expansion=round(1 / FRACCION_MUESTRA, 4), ingreso=muestra.ingreso.round(4),
                             lugar_poblado=muestra.LUGAR_POBLADO.astype("Int64"), personas=muestra.TOTAL_PERS.astype("Int64"))
    cols_hogar = ["cod_muni", "ingreso", "agua_entubada", "almacena_agua", "tiene_deposito",
                  "personas", "lugar_poblado", "factor_expansion"]
    guardar(muestra[cols_hogar], "atributos_hogar.csv", cols_hogar)  # solo las columnas documentadas
    guardar_json(sigma(h), "sigma_hogar.json")

    am = h.groupby("cod_muni").agg(
        hogares=("ingreso", "size"), personas=("TOTAL_PERS", "sum"),
        prop_agua_entubada=("agua_entubada", "mean"), prop_almacena_agua=("almacena_agua", "mean"),
        prop_tiene_deposito=("tiene_deposito", "mean"), indice_riqueza_medio=("ingreso", "mean"),
        prop_urbana=("AREA", lambda s: (s == 1).mean()),
    ).round(4).reset_index()
    guardar(am, "atributos_municipio.csv", ["cod_muni", "hogares", "prop_agua_entubada", "prop_almacena_agua", "indice_riqueza_medio"])

    lp = h.dropna(subset=["Long", "Lat"]).groupby(["cod_muni", "LUGAR_POBLADO"]).agg(
        nombre=("NOMBRE_LUGAR_POBLADO", "first"), lon=("Long", "first"), lat=("Lat", "first"),
        hogares=("ingreso", "size"), personas=("TOTAL_PERS", "sum"),
        prop_agua_entubada=("agua_entubada", "mean"), prop_almacena_agua=("almacena_agua", "mean"),
        indice_riqueza_medio=("ingreso", "mean"),
    ).round(4).reset_index().rename(columns={"LUGAR_POBLADO": "lugar_poblado"})
    guardar(lp, "lugares_poblados.csv", ["lugar_poblado", "nombre", "cod_muni", "lat", "lon", "hogares"])

    od = od_censo(persona)
    guardar(od, "od_censo.csv", ["cod_i", "cod_j", "trabajadores", "estudiantes", "total"])
    internos = od[(od.cod_j != "FUERA") & (od.cod_i != od.cod_j)].total.sum()
    fr = internos / pob.poblacion_censo2018.sum()
    registrar_parametro("gravitacional", "fraccion_viaja", round(float(fr), 5), "fracción de la población por día",
                        "Trabajadores ocupados y estudiantes del Censo 2018 que trabajan o estudian en otro de los 17 municipios.")
    print(f"  O-D censal: {internos:,} viajes diarios entre municipios ({fr:.1%} de la población)")


if __name__ == "__main__":
    main()
