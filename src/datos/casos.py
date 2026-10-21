"""Casos de dengue: observados (SIGSA, OpenDengue, boletines MSPAS) y la serie
semanal por municipio del contrato.

No existe una fuente pública con casos *semanales por municipio*. Se publican:
  * SIGSA/MSPAS: casos ANUALES por municipio, edad y sexo (2012-2025).
  * OpenDengue (origen OPS/PLISA): casos SEMANALES nacionales (2013-2024).
  * Boletines MSPAS (PDF): curva semanal nacional y casos por área de salud.

Salidas (data/processed/):
  casos_anuales_muni.csv      cod_muni, anio, casos, casos_graves          (observado)
  casos_anuales_edad_sexo.csv cod_muni, anio, grupo_etario, sexo, casos   (observado)
  casos_semanales_nacional.csv anio, semana_epi, fecha_inicio, casos, fuente, imputado (observado)
  casos_semanales.csv         cod_muni, anio, semana_epi, casos, tipo, metodo  (ESTIMADO)

``casos_semanales.csv`` reparte el total anual observado de cada municipio
según la forma de la curva semanal nacional de ese año (desagregación
proporcional). Conserva exactamente el total anual municipal, pero la forma
semanal es la nacional: no sirve para validar el orden de llegada del brote
entre municipios.
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import RAW, VALIDACION, a_codigo, guardar, inicio_semana, normalizar, registrar_parametro  # noqa: E402

DIR = RAW / "casos"
DEPARTAMENTO = "GUATEMALA"


# ------------------------------------------------------------------ SIGSA
def _leer_sigsa(ruta: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(ruta, sep=";", encoding=enc, dtype=str)
            break
        except UnicodeDecodeError:
            continue
    df.columns = [normalizar(c).lower().replace(" ", "_") for c in df.columns]
    df = df.rename(columns={"ano": "anio"})
    df = df.dropna(subset=["anio", "municipio"])  # SIGSA agrega filas vacías al final
    df["casos"] = pd.to_numeric(df["casos"], errors="coerce").fillna(0).astype(int)
    df["anio"] = df["anio"].astype(int)
    df["grupo_etario"] = df["grupo_etario"].str.replace(r"\s+", " ", regex=True).str.strip()
    return df


def sigsa(patron: str) -> pd.DataFrame:
    archivos = sorted(DIR.glob(patron))
    if not archivos:
        raise FileNotFoundError(f"No hay archivos {patron} en {DIR}. Corre src/datos/descargar.py")
    df = pd.concat([_leer_sigsa(a) for a in archivos], ignore_index=True)
    df = df[df["departamento"].map(normalizar) == DEPARTAMENTO].copy()
    df["cod_muni"] = df["municipio"].map(a_codigo)
    sin = df[df["cod_muni"].isna()]["municipio"].unique()
    if len(sin):
        raise RuntimeError(f"Municipios SIGSA sin código INE: {sin}")
    return df


def casos_anuales() -> tuple[pd.DataFrame, pd.DataFrame]:
    d = sigsa("sigsa_dengue_2*.csv")
    g = sigsa("sigsa_dengue_grave_*.csv")
    anual = d.groupby(["cod_muni", "anio"], as_index=False)["casos"].sum()
    graves = g.groupby(["cod_muni", "anio"], as_index=False)["casos"].sum().rename(columns={"casos": "casos_graves"})
    anual = anual.merge(graves, on=["cod_muni", "anio"], how="left")
    # Completar municipio-año sin registros con 0 (SIGSA omite filas sin casos).
    malla = pd.MultiIndex.from_product(
        [sorted(anual.cod_muni.unique()), range(anual.anio.min(), anual.anio.max() + 1)], names=["cod_muni", "anio"]
    ).to_frame(index=False)
    anual = malla.merge(anual, how="left").fillna({"casos": 0, "casos_graves": 0})
    anual[["casos", "casos_graves"]] = anual[["casos", "casos_graves"]].astype(int)
    edad = (
        d.groupby(["cod_muni", "anio", "grupo_etario", "sexo"], as_index=False)["casos"].sum()
        .sort_values(["cod_muni", "anio", "grupo_etario", "sexo"])
    )
    return anual, edad


# --------------------------------------------------------------- OpenDengue
def opendengue_nacional() -> pd.DataFrame:
    with zipfile.ZipFile(DIR / "opendengue_temporal_V1_3.zip") as z:
        nombre = next(n for n in z.namelist() if n.endswith(".csv"))
        df = pd.read_csv(io.BytesIO(z.read(nombre)), low_memory=False)
    df = df[(df["adm_0_name"] == "GUATEMALA") & (df["T_res"] == "Week") & (df["S_res"] == "Admin0")].copy()
    fecha = pd.to_datetime(df["calendar_start_date"])
    fin = fecha + pd.Timedelta(days=3)  # el miércoles cae siempre en la semana epi correcta
    from epiweeks import Week

    semanas = [Week.fromdate(f.date(), system="CDC") for f in fin]
    out = pd.DataFrame({
        "anio": [w.year for w in semanas],
        "semana_epi": [w.week for w in semanas],
        "fecha_inicio": fecha.dt.date.astype(str),
        "casos": df["dengue_total"].round().astype(int).values,
        "fuente": "OpenDengue V1.3 / OPS-PLISA",
        "imputado": df["UUID"].str.contains("Imputed").values,
    })
    return out.sort_values(["anio", "semana_epi"]).drop_duplicates(["anio", "semana_epi"]).reset_index(drop=True)


# ---------------------------------------------------- desagregación semanal
def _reparto_entero(total: int, pesos: np.ndarray) -> np.ndarray:
    """Reparte un entero según pesos conservando la suma (mayores restos)."""
    if total == 0 or pesos.sum() == 0:
        return np.zeros(len(pesos), dtype=int)
    cuota = total * pesos / pesos.sum()
    base = np.floor(cuota).astype(int)
    resto = total - base.sum()
    base[np.argsort(-(cuota - base))[:resto]] += 1
    return base


def semanas_del_anio(anio: int) -> int:
    from epiweeks import Year

    return Year(anio, system="CDC").totalweeks()


def desagregar(anual: pd.DataFrame, nacional: pd.DataFrame) -> pd.DataFrame:
    filas = []
    anios = sorted(set(anual.anio) & set(nacional.anio))
    for anio in anios:
        n_sem = semanas_del_anio(anio)
        perfil = nacional[nacional.anio == anio].set_index("semana_epi")["casos"].reindex(range(1, n_sem + 1))
        # Semanas faltantes en la serie nacional: interpolación lineal (se documenta).
        faltantes = perfil.isna().sum()
        perfil = perfil.interpolate(limit_direction="both").fillna(0).to_numpy(float)
        for _, r in anual[anual.anio == anio].iterrows():
            casos = _reparto_entero(int(r.casos), perfil)
            for s, c in enumerate(casos, start=1):
                filas.append((r.cod_muni, anio, s, int(c), faltantes))
    out = pd.DataFrame(filas, columns=["cod_muni", "anio", "semana_epi", "casos", "_faltantes"])
    out["tipo"] = "estimado"
    out["metodo"] = "total_anual_SIGSA_x_perfil_semanal_nacional"
    return out.drop(columns="_faltantes")


def main() -> None:
    print("[casos] SIGSA, OpenDengue y desagregación semanal")
    anual, edad = casos_anuales()
    guardar(anual, "casos_anuales_muni.csv", ["cod_muni", "anio", "casos", "casos_graves"])
    guardar(edad, "casos_anuales_edad_sexo.csv", ["cod_muni", "anio", "grupo_etario", "sexo", "casos"])
    fg = anual.casos_graves.sum() / anual.casos.sum()
    registrar_parametro("salud", "fraccion_grave", round(float(fg), 5), "casos graves / casos registrados",
                        f"Departamento de Guatemala, SIGSA {anual.anio.min()}-{anual.anio.max()}.")

    nacional = opendengue_nacional()
    try:  # 2025-2026 desde los boletines del MSPAS, si se pudieron extraer
        from boletines import serie_semanal_boletines

        extra = serie_semanal_boletines()
        if extra is not None and len(extra):
            extra = extra[~extra.set_index(["anio", "semana_epi"]).index.isin(nacional.set_index(["anio", "semana_epi"]).index)]
            nacional = pd.concat([nacional, extra], ignore_index=True).sort_values(["anio", "semana_epi"])
    except ImportError:
        pass
    nacional["fecha_inicio"] = [str(inicio_semana(a, s)) for a, s in zip(nacional.anio, nacional.semana_epi)]
    guardar(nacional, "casos_semanales_nacional.csv", ["anio", "semana_epi", "fecha_inicio", "casos", "fuente", "imputado"])

    semanal = desagregar(anual, nacional)
    guardar(semanal, "casos_semanales.csv", ["cod_muni", "anio", "semana_epi", "casos"])

    # Control: el total anual se conserva exactamente.
    chequeo = semanal.groupby(["cod_muni", "anio"]).casos.sum().reset_index().merge(anual, on=["cod_muni", "anio"], suffixes=("_sem", "_anual"))
    assert (chequeo.casos_sem == chequeo.casos_anual).all(), "la desagregación no conserva el total anual"
    VALIDACION.mkdir(parents=True, exist_ok=True)
    dep = anual.groupby("anio").casos.sum().rename("dep_guatemala_sigsa")
    nac = nacional.groupby("anio").casos.sum().rename("nacional_semanal")
    pd.concat([dep, nac], axis=1).assign(fraccion_dep=lambda x: x.dep_guatemala_sigsa / x.nacional_semanal).round(3).to_csv(
        VALIDACION / "casos_departamento_vs_nacional.csv"
    )
    print(f"  años con serie semanal estimada: {sorted(semanal.anio.unique())}")


if __name__ == "__main__":
    main()
