"""Lluvia y temperatura semanales por municipio.

INSIVUMEH solo publica los últimos ~30 días por estación (no hay serie
histórica descargable), así que la serie se arma con reanálisis en la
cabecera de cada municipio:

  * Open-Meteo: temperatura ERA5-Land (~9 km) y lluvia ERA5 (~25 km), 2017 → hoy → clima_semanal.csv (contrato)
  * NASA POWER, MERRA-2 (~50 km), 2012 → hoy          → clima_semanal_power.csv (respaldo, SOLO temperatura:
    su precipitación llegó con valores imposibles y se descarta)
  * INSIVUMEH, estaciones del departamento (~30 días) → validacion/clima_vs_insivumeh.csv

Semana epidemiológica domingo–sábado. Solo se conservan semanas completas.
lluvia_mm = suma de la semana; temp_c = promedio de la temperatura media diaria.
lluvia_rel = lluvia_mm / lluvia semanal media de mayo-octubre del mismo municipio
(1 = semana típica de temporada lluviosa). Se recomienda alimentar Λ(t) con
lluvia_rel porque elimina el sesgo de nivel del reanálisis.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import RAW, VALIDACION, agregar_semana_epi, guardar, municipios, normalizar, registrar_parametro  # noqa: E402

DIR = RAW / "clima"


# ----------------------------------------------------------------- lectores
def diario_openmeteo(cod: str) -> pd.DataFrame | None:
    """Temperatura de ERA5-Land (~9 km) + lluvia de ERA5 (~25 km), ambas vía Open-Meteo.
    ERA5-Land no publica precipitación en Open-Meteo, por eso la lluvia es otra consulta."""
    ruta_t = DIR / "openmeteo" / f"{cod}.json"
    ruta_ll = DIR / "openmeteo_lluvia" / f"{cod}.json"
    if not ruta_t.exists() or not ruta_ll.exists():
        return None
    t = json.loads(ruta_t.read_text(encoding="utf-8"))["daily"]
    ll = json.loads(ruta_ll.read_text(encoding="utf-8"))["daily"]
    temp = pd.DataFrame({
        "fecha": pd.to_datetime(t["time"]),
        "temp_c": t["temperature_2m_mean"],
        "temp_max_c": t["temperature_2m_max"],
        "temp_min_c": t["temperature_2m_min"],
    })
    lluvia = pd.DataFrame({"fecha": pd.to_datetime(ll["time"]), "lluvia_mm": ll["precipitation_sum"]})
    return lluvia.merge(temp, on="fecha", how="inner")


def diario_power(cod: str) -> pd.DataFrame | None:
    ruta = DIR / "power" / f"{cod}.json"
    if not ruta.exists():
        return None
    p = json.loads(ruta.read_text(encoding="utf-8"))["properties"]["parameter"]
    df = pd.DataFrame({
        "lluvia_mm": p["PRECTOTCORR"], "temp_c": p["T2M"], "temp_max_c": p["T2M_MAX"], "temp_min_c": p["T2M_MIN"],
    })
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df = df.replace(-999.0, np.nan).rename_axis("fecha").reset_index()
    # La precipitación de POWER (PRECTOTCORR) llegó con valores físicamente
    # imposibles (20 000-50 000 mm/año, idénticos en los 17 puntos): se descarta
    # y POWER se usa solo como respaldo de temperatura.
    df["lluvia_mm"] = np.nan
    return df


def semanal(diario: pd.DataFrame) -> pd.DataFrame:
    requeridas = ["temp_c"] if diario["lluvia_mm"].isna().all() else ["lluvia_mm", "temp_c"]
    d = agregar_semana_epi(diario.dropna(subset=requeridas))
    g = d.groupby(["anio", "semana_epi"]).agg(
        lluvia_mm=("lluvia_mm", lambda x: x.sum(min_count=1)),
        temp_c=("temp_c", "mean"),
        temp_max_c=("temp_max_c", "max"),
        temp_min_c=("temp_min_c", "min"),
        dias=("fecha", "count"),
        fecha_inicio=("fecha", "min"),
    ).reset_index()
    g = g[g.dias == 7].drop(columns="dias")
    g["fecha_inicio"] = g["fecha_inicio"].dt.date.astype(str)
    return g


def construir(lector, fuente: str) -> pd.DataFrame:
    partes = []
    for cod in municipios()["cod_muni"]:
        d = lector(cod)
        if d is None:
            print(f"  ! sin datos {fuente} para {cod}")
            continue
        s = semanal(d)
        s.insert(0, "cod_muni", cod)
        partes.append(s)
    if not partes:
        return pd.DataFrame()
    out = pd.concat(partes, ignore_index=True)
    out["fuente"] = fuente
    num = ["lluvia_mm", "temp_c", "temp_max_c", "temp_min_c"]
    out[num] = out[num].round(2)
    return out.sort_values(["cod_muni", "anio", "semana_epi"]).reset_index(drop=True)


# --------------------------------------------------------------- INSIVUMEH
ESTACION_MUNI = {  # el código INSIVUMEH incluye depto y municipio: INS01MM..
    "INS010101CV": "0101", "INS010102CV": "0101", "INS010301AT": "0103", "INS010302AT": "0103",
    "INS010701AT": "0107", "INS010801AT": "0108", "INS011402CV": "0114",
}


def insivumeh() -> pd.DataFrame:
    filas = []
    for est, cod in ESTACION_MUNI.items():
        ruta = DIR / "insivumeh" / f"{est}.csv"
        if not ruta.exists():
            continue
        try:
            tabla = pd.read_csv(ruta, encoding="utf-8-sig")
        except Exception as e:  # CSV vacío o con otro formato
            print(f"  ! INSIVUMEH {est}: {e}")
            continue
        tabla.columns = [normalizar(c).lower() for c in tabla.columns]
        col_f = next(c for c in tabla.columns if "fecha" in c)
        col_ll = next(c for c in tabla.columns if "lluvia" in c)
        col_t = next((c for c in tabla.columns if "media" in c and "temp" in c), None)  # varias estaciones solo miden lluvia
        filas.append(pd.DataFrame({
            "estacion": est, "cod_muni": cod, "fecha": pd.to_datetime(tabla[col_f], errors="coerce"),
            "lluvia_obs_mm": pd.to_numeric(tabla[col_ll], errors="coerce"),
            "temp_obs_c": pd.to_numeric(tabla[col_t], errors="coerce") if col_t else np.nan,
        }))
    return pd.concat(filas, ignore_index=True).dropna(subset=["fecha"]) if filas else pd.DataFrame()


def validar_contra_estaciones(obs: pd.DataFrame) -> pd.DataFrame | None:
    """Compara ERA5-Land diario (cabecera) con lo observado en las estaciones."""
    if obs.empty:
        return None
    comparas = []
    for cod, g in obs.groupby("cod_muni"):
        rea = diario_openmeteo(cod)
        if rea is None:
            continue
        comparas.append(g.merge(rea[["fecha", "lluvia_mm", "temp_c"]], on="fecha", how="inner"))
    if not comparas:
        return None
    c = pd.concat(comparas)
    if c.empty:
        return None
    res = c.groupby("estacion").apply(lambda g: pd.Series({
        "cod_muni": g.cod_muni.iloc[0],
        "dias_comparados": len(g),
        "lluvia_obs_total_mm": g.dropna(subset=["lluvia_obs_mm"]).lluvia_obs_mm.sum(),
        "lluvia_era5_total_mm": g.dropna(subset=["lluvia_obs_mm"]).lluvia_mm.sum(),
        "sesgo_temp_c": (g.temp_c - g.temp_obs_c).mean(),
        "corr_temp": g[["temp_c", "temp_obs_c"]].corr().iloc[0, 1] if g.temp_obs_c.notna().sum() > 2 else np.nan,
        "corr_lluvia": g[["lluvia_mm", "lluvia_obs_mm"]].corr().iloc[0, 1] if len(g) > 2 else np.nan,
    }), include_groups=False).reset_index()
    return res.round(3)


def main() -> None:
    print("[clima] reanálisis por cabecera municipal")
    om = construir(diario_openmeteo, "Open-Meteo (lluvia ERA5, temperatura ERA5-Land)")
    pw = construir(diario_power, "NASA POWER MERRA-2")
    contrato = ["cod_muni", "anio", "semana_epi", "lluvia_mm", "temp_c"]
    if not om.empty:
        # Índice de lluvia relativo a la temporada lluviosa (mayo-octubre) de cada municipio.
        # Quita el sesgo de nivel del reanálisis (ERA5 subestima ~45 % en la celda de la
        # Ciudad de Guatemala frente a INSIVUMEH) y conserva la estacionalidad.
        mes = pd.to_datetime(om.fecha_inicio).dt.month
        ref = om[mes.between(5, 10)].groupby("cod_muni").lluvia_mm.mean()
        om["lluvia_rel"] = (om.lluvia_mm / om.cod_muni.map(ref)).round(4)
    if not om.empty:
        guardar(om, "clima_semanal.csv", contrato)
    elif not pw.empty:
        print("  ! Open-Meteo no disponible: clima_semanal.csv se arma con NASA POWER")
        guardar(pw, "clima_semanal.csv", contrato)
    if not pw.empty:
        guardar(pw, "clima_semanal_power.csv", contrato)

    base = om if not om.empty else pw
    if not base.empty:
        lluviosa = base[pd.to_datetime(base.fecha_inicio).dt.month.between(5, 10)]
        registrar_parametro("ciclo_vector", "lluvia_referencia_mm_semana", round(float(lluviosa.lluvia_mm.mean()), 2), "mm / semana",
                            f"Lluvia semanal media de mayo a octubre en las 17 cabeceras ({base.fuente.iloc[0]}).")
    VALIDACION.mkdir(parents=True, exist_ok=True)
    obs = insivumeh()
    if not obs.empty:
        obs.to_csv(VALIDACION / "insivumeh_diario_reciente.csv", index=False)
        val = validar_contra_estaciones(obs)
        if val is not None:
            val.to_csv(VALIDACION / "clima_vs_insivumeh.csv", index=False)
            print(f"  validación INSIVUMEH: {len(val)} estaciones, sesgo medio temp {val.sesgo_temp_c.mean():+.2f} °C")
    if not om.empty and not pw.empty:
        j = om.merge(pw, on=["cod_muni", "anio", "semana_epi"], suffixes=("_om", "_pw"))
        r = pd.DataFrame({
            "corr_temp_diaria_nota": ["la lluvia de POWER se descartó"],
            "corr_temp_semanal": [j.temp_c_om.corr(j.temp_c_pw)],
            "sesgo_temp_pw_menos_om": [(j.temp_c_pw - j.temp_c_om).mean()],
            "temp_media_om": [j.temp_c_om.mean()], "temp_media_pw": [j.temp_c_pw.mean()],
        }).round(3)
        r.to_csv(VALIDACION / "clima_openmeteo_vs_power.csv", index=False)


if __name__ == "__main__":
    main()
