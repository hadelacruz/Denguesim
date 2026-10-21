"""Extensión: autómata celular de densidad de mosquitos en la grilla piloto.

Estado: D_i(t) = mosquitos adultos en la celda i en la semana t.
Cada celda depende de SU lluvia (lluvia_rel de clima_semanal.csv interpolada por
distancia inversa desde las 17 cabeceras, con rezago) y de su vecindad de Moore:

  K_i      = capacidad_por_hab · población_i · (1 + peso_almacena_agua · p_almacena_i)
             (p_almacena_i = proporción de hogares que almacena agua en la celda, Censo 2018)
  L_i(t)   = lluvia_rel_i(t − rezago)   (lluvia relativa a la temporada lluviosa; ≥ 0, tope 2)
  nac_i    = r · L_i · D_i · (1 − D_i / K_i) + ε · K_i · L_i         (eclosión de huevos latentes)
  D*_i     = (1 − m) · D_i + nac_i                                   (muerte semanal m)
  D_i(t+1) = (1 − δ) · D*_i + δ · promedio_Moore(D*)                 (dispersión a 8 vecinas)

Salidas (data/processed/):
  ca_mosquitos.csv   cod_celda, anio, semana_epi, densidad, densidad_rel
  ca_mosquitos.npz   arreglos (semanas × filas × columnas) para el demo
  ca_mosquitos.gif   animación de la densidad relativa (últimas 104 semanas)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "datos"))
from comun import PROCESSED, guardar, leer_procesado, municipios, parametro, registrar_parametro  # noqa: E402

EPS_ECLOSION = 0.02  # fracción de K que eclosiona de huevos latentes con lluvia de referencia


def lluvia_por_celda(grilla: pd.DataFrame, clima: pd.DataFrame, potencia: float = 2.0) -> tuple[np.ndarray, pd.DataFrame]:
    """Interpolación IDW de la lluvia semanal de las cabeceras a cada celda."""
    m = municipios().set_index("cod_muni")
    tabla = clima.pivot_table(index=["anio", "semana_epi"], columns="cod_muni", values="lluvia_rel").dropna(axis=1, how="all")
    tabla = tabla.dropna()
    cods = list(tabla.columns)
    lat0 = np.deg2rad(grilla.lat.mean())
    dx = (grilla.lon.to_numpy()[:, None] - m.loc[cods, "lon_cabecera"].to_numpy()[None, :]) * np.cos(lat0)
    dy = grilla.lat.to_numpy()[:, None] - m.loc[cods, "lat_cabecera"].to_numpy()[None, :]
    dist = np.hypot(dx, dy) * 111.0 + 0.5  # km; +0.5 evita división entre cero
    w = 1.0 / dist**potencia
    w /= w.sum(axis=1, keepdims=True)
    return tabla.to_numpy() @ w.T, tabla.index.to_frame(index=False)  # (semanas × celdas)


def simular(grilla: pd.DataFrame, lluvia: np.ndarray, p_almacena) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    r = parametro("automata", "r_crecimiento")
    mort = parametro("automata", "muerte_semanal")
    delta = parametro("automata", "difusion_moore")
    k_hab = parametro("automata", "capacidad_por_hab")
    peso = parametro("automata", "peso_almacena_agua")
    rezago = int(parametro("ciclo_vector", "rezago_lluvia_semanas"))

    nf, nc = grilla.fila.max() + 1, grilla.col.max() + 1
    mascara = np.zeros((nf, nc), bool)
    mascara[grilla.fila, grilla.col] = True
    K = np.zeros((nf, nc))
    K[grilla.fila, grilla.col] = k_hab * grilla.poblacion.to_numpy() * (1 + peso * np.asarray(p_almacena))
    K = np.maximum(K, 1e-9)
    L = np.zeros((lluvia.shape[0], nf, nc))
    L[:, grilla.fila, grilla.col] = np.clip(lluvia, 0, 2)  # lluvia ya es relativa (lluvia_rel)

    D = np.where(mascara, 0.1 * K, 0.0)
    salida = np.zeros_like(L)
    vecinos = np.zeros((nf, nc))
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            if di or dj:
                vecinos += np.roll(np.roll(np.pad(mascara, 1), di, 0), dj, 1)[1:-1, 1:-1]
    for t in range(L.shape[0]):
        lt = L[max(t - rezago, 0)]
        nac = r * lt * D * (1 - D / K) + EPS_ECLOSION * K * lt
        Dx = np.where(mascara, np.maximum((1 - mort) * D + nac, 0), 0)
        suma = np.zeros_like(Dx)
        Dp = np.pad(Dx, 1)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if di or dj:
                    suma += np.roll(np.roll(Dp, di, 0), dj, 1)[1:-1, 1:-1]
        prom = np.divide(suma, vecinos, out=np.zeros_like(suma), where=vecinos > 0)
        D = np.where(mascara, (1 - delta) * Dx + delta * prom, 0)
        salida[t] = D
    return salida, K, mascara


def animar(rel: np.ndarray, mascara: np.ndarray, semanas: pd.DataFrame, ruta: Path, n: int = 104) -> None:
    import imageio.v2 as imageio
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cuadros = []
    for t in range(max(0, len(rel) - n), len(rel)):
        fig, ax = plt.subplots(figsize=(4.2, 4.2), dpi=80)
        img = np.where(mascara, rel[t], np.nan)
        ax.imshow(img, vmin=0, vmax=max(0.05, np.nanpercentile(rel, 99)), cmap="YlOrRd")
        ax.set_title(f"Densidad relativa D/K · {semanas.anio[t]}-SE{semanas.semana_epi[t]:02d}", fontsize=9)
        ax.axis("off")
        fig.canvas.draw()
        cuadros.append(np.asarray(fig.canvas.buffer_rgba())[..., :3].copy())
        plt.close(fig)
    imageio.mimsave(ruta, cuadros, duration=0.12, loop=0)


def main() -> None:
    print("[autómata] densidad de mosquitos en la grilla piloto")
    grilla = leer_procesado("grilla_piloto.csv")
    grilla = grilla[grilla.poblacion > 0].reset_index(drop=True)
    clima = leer_procesado("clima_semanal.csv")
    lluvia, semanas = lluvia_por_celda(grilla, clima)
    registrar_parametro("automata", "semanas", int(len(semanas)), "semanas", "semanas con clima completo en las 17 cabeceras")
    p_alm = grilla["prop_almacena_agua"].to_numpy()  # proporción de hogares que almacenan agua en cada celda (Censo)

    D, K, mascara = simular(grilla, lluvia, p_alm)
    rel = np.divide(D, K, out=np.zeros_like(D), where=mascara[None])
    idx = (slice(None), grilla.fila.to_numpy(), grilla.col.to_numpy())
    largo = pd.DataFrame({
        "cod_celda": np.tile(grilla.cod_celda.to_numpy(), len(semanas)),
        "anio": np.repeat(semanas.anio.to_numpy(), len(grilla)),
        "semana_epi": np.repeat(semanas.semana_epi.to_numpy(), len(grilla)),
        "densidad": D[idx].ravel().round(1),
        "densidad_rel": rel[idx].ravel().round(4),
    })
    guardar(largo, "ca_mosquitos.csv", ["cod_celda", "anio", "semana_epi", "densidad", "densidad_rel"])
    np.savez_compressed(PROCESSED / "ca_mosquitos.npz", densidad=D.astype(np.float32), densidad_rel=rel.astype(np.float32),
                        mascara=mascara, anio=semanas.anio.to_numpy(), semana_epi=semanas.semana_epi.to_numpy())
    animar(rel, mascara, semanas, PROCESSED / "ca_mosquitos.gif")
    print(f"  {len(semanas)} semanas × {len(grilla)} celdas; animación ca_mosquitos.gif")


if __name__ == "__main__":
    main()
