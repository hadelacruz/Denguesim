"""A13 · Comparación de β entre Dinámica de Sistemas (A5), el ABM (D13) y la red (D4).

  - β_eq = R0²·γ del modelo SEIR–SEI (A5): temporada alta, sin control, todos susceptibles.
  - β_eq(t) = R0(t)²·γ con m(t) = Nv(t)/Nh y μ(t) simulados (incluye la lluvia y el
    loop B), promediado en la ventana del ABM (semanas 18 a 46). Es la comparación justa.
  - β del ABM (beta_efectiva.json): SEIR humano equivalente ajustado a las corridas.
  - β/γ contra el umbral epidémico de la red τ_c (umbral.py).

Salida: data/processed/sd/comparacion_beta.md
Uso (desde la raíz):  python src/sd/comparacion_beta.py
"""

import json
import sys

import numpy as np

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/sd")
sys.path.insert(0, "src/redes")
from comun import PROCESSED, parametro  # noqa: E402
from fumigacion import mortalidad_vector  # noqa: E402
from modelo_seir_sei import IEV, IFU, IIV, ISV, parametros_departamento, simular_seir_sei  # noqa: E402
from r0 import r0  # noqa: E402
from umbral import comparar_con_beta_gamma  # noqa: E402


def beta_eq_en_el_tiempo():
    """β_eq(t) = R0(t)²·γ con la abundancia y la mortalidad simuladas, en la ventana del ABM."""
    p = parametros_departamento()
    res = simular_seir_sei(p, dias=364)
    Y = res["Y"]
    m_t = (Y[:, ISV] + Y[:, IEV] + Y[:, IIV]) / p["Nh"]
    mu_t = mortalidad_vector(Y[:, IFU], p)
    beta_t = r0(p, m=m_t, mu=mu_t) ** 2 * p["gamma"]
    s0 = parametro("abm", "semana_inicio")
    ventana = slice(7 * (s0 - 1), 7 * (s0 - 1) + parametro("abm", "dias_simulacion"))
    return float(beta_t[ventana].mean()), float(beta_t[ventana].min()), float(beta_t[ventana].max())


def main():
    sd = json.loads((PROCESSED / "sd" / "beta_equivalente.json").read_text(encoding="utf-8"))
    abm = json.loads((PROCESSED / "beta_efectiva.json").read_text(encoding="utf-8"))
    gamma = parametro("transmision", "gamma")
    media_t, min_t, max_t = beta_eq_en_el_tiempo()
    red0 = comparar_con_beta_gamma(abm["beta"], gamma, "gravitacional", 0)
    red100 = comparar_con_beta_gamma(abm["beta"], gamma, "gravitacional", parametro("redes", "umbral_comparacion"))
    texto = f"""# Comparación de β (A13)

| Fuente | β (1/día) | β/γ | Qué representa |
|---|---|---|---|
| SD, A5: `β_eq = R0²·γ` | {sd['beta_eq']:.3f} | {sd['beta_eq'] / gamma:.2f} | Temporada alta (m = {sd['m']}), μ sin fumigación, βs calibrado = {sd['beta_s']:.3f}, todos susceptibles |
| SD, `β_eq(t)` en semanas 18–46 | {media_t:.3f} (rango {min_t:.3f}–{max_t:.3f}) | {media_t / gamma:.2f} | Igual, pero con m(t) y μ(t) simulados (lluvia + loop B) |
| ABM, `beta_efectiva.json` | {abm['beta']:.3f} (IC 95 % {abm['ic_inf']:.3f}–{abm['ic_sup']:.3f}) | {abm['beta'] / gamma:.2f} | SEIR humano equivalente ajustado a las corridas de Amatitlán (semanas 18–46) |

**Umbral epidémico de la red (D4):** τ_c = {red0['umbral_epidemico']:.4f} (grafo completo, umbral 0) y
{red100['umbral_epidemico']:.4f} (umbral {parametro('redes', 'umbral_comparacion')} personas/día). Con β/γ del ABM = {abm['beta'] / gamma:.2f}, la red supera el umbral en
ambos casos ({red0['supera_umbral']} / {red100['supera_umbral']}). La red del departamento es tan densa que cualquier
transmisibilidad realista invade: el umbral de red no es la restricción; lo que limita la transmisión
es la estacionalidad (mosquitos) y el control.

## Por qué difieren

1. **Escala espacial:** el ABM es local (Amatitlán, celdas de 500 m) y el SD es departamental de mezcla homogénea.
   En el ABM, los infecciosos solo infectan a los mosquitos de las celdas que visitan y se agotan
   localmente; por eso la β "media" es menor que la de mezcla homogénea.
2. **Qué incluye cada β:** el `β_eq` de A5 supone temporada alta, sin fumigación y todos susceptibles
   (un máximo teórico). `β_eq(t)` ya incluye la lluvia y el loop B, y se acerca más al ABM. La β del ABM es
   un ajuste estadístico (mínimos cuadrados entre el primer caso y el pico) que también absorbe el
   retardo humano → mosquito → humano.
3. **Supuestos distintos:** el ABM no tiene incubación extrínseca y usa la abundancia del autómata
   celular, calibrada con `escala_mosquitos`; el SD tiene incubación extrínseca (σv) y Λ(t) por lluvia
   con retardo de 3er orden, calibrado con βs y la ganancia del loop B.
4. **Lo que sí coincide:** ambos modelos están calibrados para producir la incidencia notificada observada
   de 2023 con ρ = 0.2, y los dos dan una transmisión efectiva **cerca del umbral** (β/γ del ABM ≈ 1.1),
   coherente con brotes de pocos por ciento de la población.
"""
    (PROCESSED / "sd" / "comparacion_beta.md").write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
