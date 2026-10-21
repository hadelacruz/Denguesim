"""Extracción de datos de las salas situacionales de arbovirosis del MSPAS (PDF).

Los boletines no traen tablas semanales en texto: las curvas semanales y el
mapa de calor por área de salud (DDRISS) están dibujados como gráficos
vectoriales. Aquí se "digitalizan" leyendo directamente la geometría del PDF
con pdfplumber:

1. Curva semanal nacional (página "Corredor endémico semanal"): la línea de
   casos del año es una polilínea; su eje Y se calibra con una regresión
   lineal entre la posición vertical y el valor de las etiquetas del eje.
   Se valida contra un segundo gráfico del mismo boletín y contra OpenDengue.
2. Actividad semanal por DDRISS (página "Actividad semanal ..."): cada celda
   coloreada es la zona del corredor endémico de esa área de salud y semana
   (rojo = brote, naranja = alerta, amarillo = seguridad, verde = éxito,
   gris = sin notificación).

Salidas:
  data/processed/actividad_semanal_area_salud.csv  anio, semana_epi, area_salud, zona, nivel
  data/processed/validacion/digitalizacion_boletines.csv
  (la curva nacional 2025-2026 se agrega a casos_semanales_nacional.csv desde casos.py)
"""

from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import RAW, VALIDACION, guardar, normalizar  # noqa: E402

DIR = RAW / "boletines"
COLOR_ZONA = {  # (R, G, B) redondeado a 2 decimales -> zona del corredor endémico
    (1.0, 0.0, 0.0): ("brote", 4),
    (1.0, 0.8, 0.0): ("alerta", 3),
    (1.0, 1.0, 0.0): ("seguridad", 2),
    (0.0, 0.5, 0.0): ("exito", 1),
    0.75: ("sin_notificacion", 0),
}
NUM = re.compile(r"^\d{1,3}(,\d{3})*$")


def _color(c):
    if isinstance(c, (tuple, list)):
        return tuple(round(float(v), 2) for v in c) if len(c) == 3 else round(float(c[0]), 2)
    return round(float(c), 2) if c is not None else None


def _anio(pdf: Path) -> int:
    return int(re.search(r"(20\d\d)", pdf.stem).group(1))


def _texto(pg) -> str:
    return normalizar(pg.extract_text() or "")


# ------------------------------------------------------------ curva semanal
def _calibrar_y(pg, x_max: float) -> tuple[float, float]:
    """Ajusta valor = a·y + b con las etiquetas numéricas del eje izquierdo."""
    pares = [
        (float(w["text"].replace(",", "")), (w["top"] + w["bottom"]) / 2)
        for w in pg.extract_words()
        if NUM.match(w["text"]) and w["x1"] < x_max
    ]
    if len(pares) < 3:
        raise ValueError("eje Y sin suficientes etiquetas")
    v, y = np.array(pares).T
    a, b = np.polyfit(y, v, 1)
    resid = np.abs(a * y + b - v).max()
    if resid > 0.02 * v.max():
        raise ValueError(f"calibración del eje Y inconsistente (residuo {resid:.0f})")
    return a, b


def curva_corredor(pdf: Path) -> pd.DataFrame | None:
    """Casos semanales del año del boletín, desde el corredor endémico nacional."""
    anio = _anio(pdf)
    with pdfplumber.open(pdf) as p:
        for pg in p.pages:
            t = _texto(pg)
            if "CORREDOR ENDEMICO SEMANAL" in t and "DENGUE" in t and pg.curves and "AREA DE SALUD" not in t:
                abiertas = [c for c in pg.curves if not c.get("fill") and 5 < len(c["pts"]) <= 53]
                if not abiertas:
                    continue
                linea = min(abiertas, key=lambda c: len(c["pts"]))
                x0 = min(pt[0] for pt in linea["pts"])
                a, b = _calibrar_y(pg, x0)
                xs = np.array([pt[0] for pt in linea["pts"]])
                paso = np.diff(xs)
                if paso.std() > 0.05 * paso.mean():
                    raise ValueError(f"{pdf.name}: puntos no equiespaciados")
                ys = np.array([pt[1] for pt in linea["pts"]])
                valores = np.maximum(a * ys + b, 0)
                return pd.DataFrame({
                    "anio": anio, "semana_epi": np.arange(1, len(valores) + 1),
                    "casos": np.round(valores).astype(int),
                    "fuente": f"MSPAS sala situacional {pdf.stem} (digitalizado)", "imputado": False,
                })
    return None


def curvas_comparativas(pdf: Path) -> dict[str, np.ndarray]:
    """Curvas del gráfico 'Casos de dengue hasta SE-xx' (año actual y anterior)."""
    with pdfplumber.open(pdf) as p:
        for pg in p.pages:
            if "CASOS DE DENGUE HASTA SE" in _texto(pg) and pg.curves:
                palabras = pg.extract_words()
                leyenda = {}
                for ln in pg.lines:
                    if ln["x1"] - ln["x0"] < 40 and abs(ln["top"] - ln["bottom"]) < 1:
                        etiqueta = [w["text"] for w in palabras if abs((w["top"] + w["bottom"]) / 2 - ln["top"]) < 6 and ln["x1"] < w["x0"] < ln["x1"] + 20]
                        if etiqueta:
                            leyenda[_color(ln["stroking_color"])] = etiqueta[0]
                x0 = min(min(pt[0] for pt in c["pts"]) for c in pg.curves)
                a, b = _calibrar_y(pg, x0)
                return {
                    leyenda.get(_color(c["stroking_color"]), "?"): np.maximum(a * np.array([pt[1] for pt in c["pts"]]) + b, 0)
                    for c in pg.curves if len(c["pts"]) >= 50
                }
    return {}


def serie_semanal_boletines() -> pd.DataFrame | None:
    """Serie semanal nacional de los años que OpenDengue no cubre (2025-2026)."""
    partes = []
    for pdf in sorted(DIR.glob("arbo_se*_202[5-9].pdf")):
        try:
            c = curva_corredor(pdf)
        except ValueError as e:
            print(f"  ! {pdf.name}: {e}")
            continue
        if c is not None:
            partes.append(c)
    return pd.concat(partes, ignore_index=True) if partes else None


def validar_curvas() -> pd.DataFrame:
    """Compara la digitalización contra fuentes independientes."""
    filas = []
    for pdf in sorted(DIR.glob("arbo_se*_202[5-9].pdf")):
        anio = _anio(pdf)
        corr = curva_corredor(pdf)
        comp = curvas_comparativas(pdf)
        if corr is not None and str(anio) in comp:
            otra = comp[str(anio)][: len(corr)]
            filas.append({"boletin": pdf.stem, "serie": f"{anio} corredor vs gráfico comparativo",
                          "semanas": len(otra), "suma_a": int(corr.casos[: len(otra)].sum()), "suma_b": int(otra.sum()),
                          "correlacion": round(float(np.corrcoef(corr.casos[: len(otra)], otra)[0, 1]), 4)})
        if str(anio - 1) in comp:
            with zipfile.ZipFile(RAW / "casos" / "opendengue_temporal_V1_3.zip") as z:
                od = pd.read_csv(io.BytesIO(z.read(next(n for n in z.namelist() if n.endswith(".csv")))), low_memory=False)
            od = od[(od.adm_0_name == "GUATEMALA") & (od.T_res == "Week") & (od.S_res == "Admin0")]
            od = od[pd.to_datetime(od.calendar_start_date).dt.year.isin([anio - 2, anio - 1])]
            od = od[(pd.to_datetime(od.calendar_start_date) + pd.Timedelta(days=3)).dt.year == anio - 1].dengue_total.to_numpy()
            dig = comp[str(anio - 1)]
            n = min(len(od), len(dig))
            if n:
                filas.append({"boletin": pdf.stem, "serie": f"{anio - 1} boletín vs OpenDengue",
                              "semanas": n, "suma_a": int(dig[:n].sum()), "suma_b": int(od[:n].sum()),
                              "correlacion": round(float(np.corrcoef(dig[:n], od[:n])[0, 1]), 4)})
    return pd.DataFrame(filas)


# ------------------------------------------------- actividad por área de salud
def actividad(pdf: Path) -> pd.DataFrame | None:
    anio = _anio(pdf)
    with pdfplumber.open(pdf) as p:
        pagina = None
        for pg in p.pages:
            t = _texto(pg)
            if ("ACTIVIDAD SEMANAL" in t or "CORREDOR ENDEMICO SEMANAL POR AREA" in t) and len(pg.rects) > 500:
                pagina = pg
                break
        if pagina is None:
            return None
        celdas = [r for r in pagina.rects if 10 < r["width"] < 16 and 8 < r["height"] < 16]
        celdas = [r for r in celdas if _color(r["non_stroking_color"]) in COLOR_ZONA]
        if not celdas:
            return None
        x_min = min(r["x0"] for r in celdas)
        # Columnas: posiciones x distintas, ordenadas → semana 1, 2, ...
        xs = np.sort(np.unique(np.round([r["x0"] for r in celdas], 0)))
        cols = [xs[0]]
        for x in xs[1:]:
            if x - cols[-1] > 4:
                cols.append(x)
        cols = np.array(cols)
        # Filas: etiquetas de texto a la izquierda de la primera columna.
        palabras = [w for w in pagina.extract_words() if w["x1"] <= x_min + 1 and re.match(r"[A-Za-zÁÉÍÓÚáéíóúñ]", w["text"])]
        filas_txt: dict[float, list[str]] = {}
        for w in sorted(palabras, key=lambda w: (round(w["top"]), w["x0"])):
            y = (w["top"] + w["bottom"]) / 2
            llave = next((k for k in filas_txt if abs(k - y) < 3), y)
            filas_txt.setdefault(llave, []).append(w["text"])
        salida = []
        for r in celdas:
            y = (r["top"] + r["bottom"]) / 2
            if not filas_txt:
                break
            llave = min(filas_txt, key=lambda k: abs(k - y))
            if abs(llave - y) > 6:
                continue
            semana = int(np.argmin(np.abs(cols - round(r["x0"])))) + 1
            zona, nivel = COLOR_ZONA[_color(r["non_stroking_color"])]
            salida.append((anio, semana, " ".join(filas_txt[llave]), zona, nivel))
    df = pd.DataFrame(salida, columns=["anio", "semana_epi", "area_salud", "zona", "nivel"])
    df = df[~df.area_salud.map(normalizar).str.contains("DDRISS|AREAS DE SALUD|REPUBLICA")]
    return df.drop_duplicates(["anio", "semana_epi", "area_salud"])


def _area_estandar(nombre: str) -> str:
    n = normalizar(nombre).replace(" ", "")
    for clave, std in [("GUATEMALACENTRAL", "GUATEMALA CENTRAL"), ("GUATEMALANOROCC", "GUATEMALA NOR-OCCIDENTE"),
                       ("GUATEMALANORORI", "GUATEMALA NOR-ORIENTE"), ("GUATEMALASUR", "GUATEMALA SUR")]:
        if clave in n:  # algunas etiquetas traen texto de la nota lateral pegado
            return std
    return normalizar(nombre)


def main() -> None:
    print("[boletines] digitalización de salas situacionales MSPAS")
    partes = []
    for pdf in sorted(DIR.glob("arbo_se*.pdf")):
        try:
            a = actividad(pdf)
        except Exception as e:  # formato distinto en algún año
            print(f"  ! {pdf.name}: {e}")
            continue
        if a is None or a.empty:
            print(f"  - {pdf.name}: sin mapa de actividad semanal")
            continue
        n_sem = a.semana_epi.max()
        print(f"  {pdf.name}: {a.area_salud.nunique()} áreas × {n_sem} semanas")
        partes.append(a)
    act = pd.concat(partes, ignore_index=True)
    act["area_salud"] = act.area_salud.map(_area_estandar)
    act = act[~act.area_salud.str.contains("FUENTE|SEMANA|ZONA")]
    guardar(act.sort_values(["anio", "area_salud", "semana_epi"]), "actividad_semanal_area_salud.csv",
            ["anio", "semana_epi", "area_salud", "zona", "nivel"])
    VALIDACION.mkdir(parents=True, exist_ok=True)
    val = validar_curvas()
    val.to_csv(VALIDACION / "digitalizacion_boletines.csv", index=False)
    if len(val):
        print(val.to_string(index=False))


if __name__ == "__main__":
    main()
