"""R1 · Generadores de variables aleatorias para el DES de camas.

1. Exponencial por TRANSFORMADA INVERSA:
       F(x) = 1 − e^(−λx)  →  X = F⁻¹(U) = −ln(1 − U) / λ,   U ~ Uniforme(0, 1)

2. Estancia hospitalaria Weibull(k, λ) por ACEPTACIÓN–RECHAZO:
       f(x) = (k/λ)(x/λ)^(k−1) · exp(−(x/λ)^k),   λ = estancia_media / Γ(1 + 1/k)
   Propuesta: exponencial g(x) = θ·e^(−θx) con la misma media (θ = 1/estancia_media).
   M = max f(x)/g(x) (en una malla fina). Existe porque con k > 1 la Weibull decae
   como e^(−x^k), más rápido que la exponencial. Se acepta X ~ g si U ≤ f(X) / (M·g(X)).
   La probabilidad de aceptar en cada intento es 1/M.

Salida: figuras/salud/generadores.png
Uso (desde la raíz):  python src/salud/generadores.py
"""

import sys
from functools import lru_cache

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy import stats  # noqa: E402
from scipy.special import gamma as funcion_gamma  # noqa: E402

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/salud")
from comun_salud import parametro, semilla  # noqa: E402


# ------------------------------------------------------------------ exponencial
def exponencial(lam, n, rng):
    """n valores Exponencial(λ) por transformada inversa: X = −ln(1 − U)/λ."""
    U = rng.random(n)
    return -np.log(1.0 - U) / lam


# ------------------------------------------------------------------ Weibull
def parametros_weibull(estancia_media=None, k=None):
    """(k, λ) de la Weibull con la media pedida: λ = media / Γ(1 + 1/k)."""
    media = parametro("salud", "estancia_media") if estancia_media is None else estancia_media
    k = parametro("salud", "weibull_k") if k is None else k
    return k, media / funcion_gamma(1.0 + 1.0 / k)


def densidad_weibull(x, k, lam):
    """f(x) = (k/λ)(x/λ)^(k−1) · exp(−(x/λ)^k)."""
    return (k / lam) * (x / lam) ** (k - 1) * np.exp(-((x / lam) ** k))


def densidad_exponencial(x, theta):
    """g(x) = θ·e^(−θx)."""
    return theta * np.exp(-theta * x)


@lru_cache(maxsize=32)
def constante_M(k, lam, theta, n_malla=200_000):
    """M = max f(x)/g(x) en una malla fina de (0, 20·λ]."""
    x = np.linspace(1e-6, 20 * lam, n_malla)
    return float(np.max(densidad_weibull(x, k, lam) / densidad_exponencial(x, theta)))


def estancia_aceptacion_rechazo(n, rng, estancia_media=None, k=None, devolver_tasa=False):
    """n estancias (días) Weibull(k, λ) por aceptación–rechazo con propuesta exponencial.

    Se proponen lotes y se guardan los aceptados hasta tener n. Con devolver_tasa=True
    también devuelve la tasa de aceptación observada (debe ser ≈ 1/M)."""
    k, lam = parametros_weibull(estancia_media, k)
    media = lam * funcion_gamma(1.0 + 1.0 / k)
    theta = 1.0 / media
    M = constante_M(k, lam, theta)
    aceptados, propuestos, total = [], 0, 0
    while total < n:
        lote = int((n - total) * M * 1.1) + 16
        X = exponencial(theta, lote, rng)                              # X ~ g
        U = rng.random(lote)
        ok = U <= densidad_weibull(X, k, lam) / (M * densidad_exponencial(X, theta))
        aceptados.append(X[ok])
        propuestos += lote
        total += int(ok.sum())
    muestra = np.concatenate(aceptados)[:n]
    if devolver_tasa:
        return muestra, total / propuestos
    return muestra


# ------------------------------------------------------------------ verificación
def verificar_generadores(n=20_000, rng=None):
    """KS contra scipy.stats, media contra la teórica (en errores estándar) y tasa contra 1/M."""
    rng = np.random.default_rng(semilla("generadores")) if rng is None else rng
    k, lam = parametros_weibull()
    media = parametro("salud", "estancia_media")
    M = constante_M(k, lam, 1.0 / media)
    w, tasa = estancia_aceptacion_rechazo(n, rng, devolver_tasa=True)
    e = exponencial(1.0 / media, n, rng)
    sd_teorica = lam * np.sqrt(funcion_gamma(1 + 2 / k) - funcion_gamma(1 + 1 / k) ** 2)
    return {
        "k": k, "lambda": lam, "M": M, "tasa_aceptacion": tasa, "tasa_esperada": 1.0 / M,
        "ks_p_weibull": stats.kstest(w, stats.weibull_min(c=k, scale=lam).cdf).pvalue,
        "ks_p_exponencial": stats.kstest(e, stats.expon(scale=media).cdf).pvalue,
        "media_weibull": w.mean(), "media_teorica": media,
        "z_media": (w.mean() - media) / (sd_teorica / np.sqrt(n)),
        "muestras": (w, e),
    }


def figura(v):
    w, e = v["muestras"]
    x = np.linspace(0.01, 15, 400)
    fig, ejes = plt.subplots(1, 2, figsize=(10, 3.8))
    for ax, datos, dens, titulo in (
        (ejes[0], e, densidad_exponencial(x, 1 / v["media_teorica"]), "Exponencial (transformada inversa)"),
        (ejes[1], w, densidad_weibull(x, v["k"], v["lambda"]),
         f"Weibull k={v['k']:.1f} (aceptación–rechazo, tasa {v['tasa_aceptacion']:.3f} ≈ 1/M = {v['tasa_esperada']:.3f})"),
    ):
        ax.hist(datos, bins=80, range=(0, 15), density=True, color="#2a78d6", alpha=0.45, label="muestra (n = 20 000)")
        ax.plot(x, dens, color="#1a1a1a", linewidth=1.8, label="densidad teórica")
        ax.set_title(titulo, fontsize=9)
        ax.set_xlabel("Estancia (días)")
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False, fontsize=8)
    ejes[0].set_ylabel("Densidad")
    fig.tight_layout()
    fig.savefig("figuras/salud/generadores.png", dpi=150)
    plt.close(fig)


def main():
    v = verificar_generadores()
    figura(v)
    print(f"Weibull k = {v['k']}, λ = {v['lambda']:.3f} días, M = {v['M']:.4f}")
    print(f"tasa de aceptación = {v['tasa_aceptacion']:.4f} (1/M = {v['tasa_esperada']:.4f})")
    print(f"KS Weibull p = {v['ks_p_weibull']:.3f} · KS exponencial p = {v['ks_p_exponencial']:.3f}")
    print(f"media Weibull = {v['media_weibull']:.3f} (teórica {v['media_teorica']}), z = {v['z_media']:.2f}")
    print("  -> figuras/salud/generadores.png")


if __name__ == "__main__":
    main()
