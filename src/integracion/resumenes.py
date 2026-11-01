"""G4 · Tablas LIVIANAS que lee el demo (el demo no debe leer casos_esperados.csv completo).

- data/processed/sig/casos_resumen.csv: escenario, cod_muni, dia, media, ic_inf, ic_sup de
  `nuevos` (casos verdaderos por día); ic = percentiles 2.5 y 97.5 entre corridas.
- data/processed/sig/abm_resumen.csv: dia, media, ic_inf, ic_sup de los nuevos casos diarios
  del ABM (zona piloto) entre corridas.

Uso (desde la raíz):  python src/integracion/resumenes.py
"""

import sys

import pandas as pd

sys.path.insert(0, "src/datos")
from comun import PROCESSED, leer_procesado  # noqa: E402


def banda(grupo, columna):
    g = grupo[columna]
    return pd.DataFrame({"media": g.mean(), "ic_inf": g.quantile(0.025), "ic_sup": g.quantile(0.975)})


def casos_resumen():
    c = leer_procesado("casos_esperados.csv")
    r = banda(c.groupby(["escenario", "cod_muni", "dia"]), "nuevos").round(3).reset_index()
    r.to_csv(PROCESSED / "sig" / "casos_resumen.csv", index=False)
    return r


def abm_resumen():
    s = pd.read_csv(PROCESSED / "abm" / "series.csv")
    r = banda(s.groupby("dia"), "nuevos_casos").round(3).reset_index()
    r.to_csv(PROCESSED / "sig" / "abm_resumen.csv", index=False)
    return r


def main():
    c = casos_resumen()
    print(f"  -> data/processed/sig/casos_resumen.csv ({len(c)} filas)")
    a = abm_resumen()
    print(f"  -> data/processed/sig/abm_resumen.csv ({len(a)} filas)")


if __name__ == "__main__":
    main()
