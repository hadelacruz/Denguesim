"""R8 · Política de insumos: reducir el tiempo de entrega τ contra reducir la agresividad α.

Se comparan tres políticas: base, τ × 0.8 y α × 0.8. OJO: como α y τ aparecen
multiplicados en los criterios de estabilidad, una misma reducción porcentual da el
mismo α·τ; por eso P(estable_B) y P(oscila_A) salen iguales en las dos reducciones y
las diferencias hay que buscarlas en otras métricas:
- amplitud máxima de I − I* y dias_desabasto (R6 con la demanda de linea_base_camas),
- tamaño de la línea de tránsito P* = τ · media(D) (inventario "en camino"),
- razón de amortiguamiento ζ_A = 1/(2√(α·τ)) con los valores centrales.

Salidas: data/processed/salud/politicas_insumos.csv y data/processed/salud/recomendacion_insumos.md
Uso (desde la raíz):  python src/salud/politicas_insumos.py
"""

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/sd")
sys.path.insert(0, "src/salud")
from comun import PROCESSED, leer_procesado  # noqa: E402
from comun_salud import parametro, semilla  # noqa: E402
from estabilidad import montecarlo, zeta_A  # noqa: E402
from insumos import consumo_desde_ocupacion, dias_desabasto, simular_insumos  # noqa: E402

POLITICAS = {"base": (1.0, 1.0), "reducir_tau_20pct": (1.0, 0.8), "reducir_alpha_20pct": (0.8, 1.0)}


def evaluar_politicas():
    ocupacion = leer_procesado("ocupacion_camas.csv")
    indice, D = consumo_desde_ocupacion(ocupacion[ocupacion.escenario == "linea_base_camas"])
    alpha0, tau0 = parametro("insumos", "alpha"), parametro("insumos", "tau")
    filas = []
    for nombre, (fa, ft) in POLITICAS.items():
        alpha, tau = alpha0 * fa, tau0 * ft
        mc = montecarlo(parametro("salud", "mc_n"), np.random.default_rng(semilla("estabilidad")), fa, ft)
        I, P, I_obj = simular_insumos(D, alpha=alpha, tau=tau)
        filas.append({
            "politica": nombre, "alpha": round(alpha, 4), "tau": round(tau, 3), "alpha_tau": round(alpha * tau, 4),
            "zeta_A": round(float(zeta_A(alpha, tau)), 4),
            "P_estable_B": round(float(mc.estable_B.mean()), 4), "P_oscila_A": round(float(mc.oscila_A.mean()), 4),
            "amplitud_max": round(float(np.abs(I - I_obj[:, None]).max()), 3),
            "amplitud_media_hospitales": round(float(np.abs(I - I_obj[:, None]).max(axis=1).mean()), 3),
            "dias_desabasto": int(dias_desabasto(I, I_obj).sum()),
            "inventario_en_transito_P_estrella": round(float((tau * D.mean(axis=1)).sum()), 3),
        })
    return pd.DataFrame(filas)


def recomendacion(t):
    base = t.set_index("politica").loc["base"]
    tau, alpha = t.set_index("politica").loc["reducir_tau_20pct"], t.set_index("politica").loc["reducir_alpha_20pct"]
    mejor = "reducir_tau_20pct" if (tau.dias_desabasto, tau.amplitud_max) <= (alpha.dias_desabasto, alpha.amplitud_max) \
        else "reducir_alpha_20pct"
    texto = f"""# Recomendación de política de insumos (R8)

Datos: demanda de `linea_base_camas` (ocupación del DES, réplica 0), 21 hospitales, α y τ
centrales del YAML (α = {base.alpha}, τ = {base.tau} días).

| Política | α·τ | ζ_A | P(estable_B) | P(oscila_A) | Amplitud máx. de I − I* | Días de desabasto | Inventario en tránsito P* |
|---|---|---|---|---|---|---|---|
""" + "\n".join(f"| {r.politica} | {r.alpha_tau} | {r.zeta_A} | {r.P_estable_B} | {r.P_oscila_A} | {r.amplitud_max} | "
                f"{r.dias_desabasto} | {r.inventario_en_transito_P_estrella} |" for r in t.itertuples()) + f"""

**Estabilidad:** las dos reducciones dan el mismo α·τ = {tau.alpha_tau}, así que P(estable_B) y
P(oscila_A) son iguales en ambas ({tau.P_estable_B} y {tau.P_oscila_A}). Según estos criterios, ninguna de las dos es mejor.

**Otras métricas:** reducir τ deja {tau.dias_desabasto} días de desabasto y una amplitud de {tau.amplitud_max};
reducir α deja {alpha.dias_desabasto} días y una amplitud de {alpha.amplitud_max} (base: {base.dias_desabasto} días, amplitud de {base.amplitud_max}).
Reducir τ además baja el inventario en tránsito P* de {base.inventario_en_transito_P_estrella} a {tau.inventario_en_transito_P_estrella}
(capital inmovilizado en pedidos).

**Recomendación (según estos números):** `{mejor}`. Con τ más corto, los pedidos llegan antes y el
inventario se recupera más rápido de los picos de demanda. Con α más bajo, en cambio, se
pide menos de la brecha cada día y el inventario tarda más en recuperarse. Limitación: el desabasto
depende sobre todo de I* = días de cobertura × demanda MEDIA anual, que se queda corto en
la temporada alta; subir la cobertura objetivo o hacerla estacional pesa más que α o τ.
"""
    (PROCESSED / "salud" / "recomendacion_insumos.md").write_text(texto, encoding="utf-8")
    return mejor


def main():
    t = evaluar_politicas()
    t.to_csv(PROCESSED / "salud" / "politicas_insumos.csv", index=False)
    mejor = recomendacion(t)
    print(t.to_string(index=False))
    print(f"Recomendación: {mejor}  -> data/processed/salud/recomendacion_insumos.md")


if __name__ == "__main__":
    main()
