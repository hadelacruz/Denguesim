"""A1 · Modelo Ross–Macdonald SEIR (humanos) – SEI (mosquitos) con RK4 a mano.

Mismo estilo y nombres que sir_model.py del Laboratorio 3: derivadas, rk4_step,
simular_*, valores_en, metricas_epidemia, sce y verificar_conservacion. No se usa
PySD; solve_ivp solo se usa para comparar en integradores.py (A4).

    λh = βs · a · b · Iv / Nh        fuerza de infección sobre humanos  [1/día]
    λv = a · c · Ih / Nh             fuerza de infección sobre mosquitos [1/día]

    dSh/dt = −λh·Sh                     dSv/dt = Λ(t) − λv·Sv − μ(t)·Sv
    dEh/dt =  λh·Sh − σh·Eh             dEv/dt = λv·Sv − (σv + μ(t))·Ev
    dIh/dt =  σh·Eh − γ·Ih              dIv/dt = σv·Ev − μ(t)·Iv
    dRh/dt =  γ·Ih

Λ(t) viene del retardo de tercer orden con la lluvia (A2, vector_lluvia.py) y
μ(t) del loop B de fumigación (A3, fumigacion.py). Casos nuevos verdaderos:
σh·Eh por día; notificados: ρ·σh·Eh.

El estado es un arreglo cuya ÚLTIMA dimensión son las 13 variables (y[..., k]).
Así la misma función sirve para una población (13,), para muchos juegos de
parámetros a la vez (n, 13) o para los 17 municipios (17, 13).

Uso (desde la raíz):  python src/sd/modelo_seir_sei.py
"""

import json
import sys

import numpy as np

sys.path.insert(0, "src/datos")
sys.path.insert(0, "src/sd")
from comun import PROCESSED, parametro  # noqa: E402
from fumigacion import derivadas_fumigacion, mortalidad_vector  # noqa: E402
from vector_lluvia import criaderos_en_equilibrio, derivadas_criaderos, escala_k, lluvia_departamento, poblacion_anio  # noqa: E402

# Índices de las variables de estado.
ISH, IEH, IIH, IRH, ISV, IEV, IIV, IX1, IX2, IX3, ICN, IFU, ICA = range(13)
NOMBRES = ["Sh", "Eh", "Ih", "Rh", "Sv", "Ev", "Iv", "X1", "X2", "X3", "Cn", "F", "casos_acum"]
CALIBRACION = PROCESSED / "sd" / "calibracion.json"


# ------------------------------------------------------------------ parámetros
def parametros_base(**cambios):
    """Parámetros biológicos y de control desde config/parametros.yaml."""
    p = {
        "a": parametro("transmision", "a"),
        "b": parametro("transmision", "b"),
        "c": parametro("transmision", "c"),
        "sigma_h": parametro("transmision", "sigma_h"),
        "sigma_v": parametro("transmision", "sigma_v"),
        "gamma": parametro("transmision", "gamma"),
        "mu": parametro("transmision", "mu"),
        "m_base": parametro("transmision", "m"),                       # = sd.m_base
        "beta_s": 1.0,                                                 # multiplicador a calibrar (A6)
        "rho": parametro("observacion", "factor_reporte"),             # a calibrar (A6)
        "expuestos_iniciales": parametro("sd", "expuestos_iniciales"), # a calibrar (A6)
        "lluvia_minima": parametro("sd", "lluvia_minima"),
        "tau_desarrollo": parametro("ciclo_vector", "tau_desarrollo"), # = sd.tau_desarrollo
        "tau_notificacion": parametro("observacion", "retardo_notificacion"),  # = sd.tau_notificacion
        "tau_respuesta": parametro("sd", "tau_respuesta"),
        "ganancia_fumigacion": parametro("sd", "ganancia_fumigacion"),
        "fumigacion_max": parametro("sd", "fumigacion_max"),
        "fumigacion_endogena": True,
    }
    p.update(cambios)
    return p


def leer_calibracion():
    """Valores calibrados de A6 (ρ, βs, I0, ganancia_fumigacion, lluvia_minima) o None."""
    if not CALIBRACION.exists():
        return None
    return json.loads(CALIBRACION.read_text(encoding="utf-8"))["valores"]


def parametros_departamento(anio=None, calibrado=True, **cambios):
    """Modelo de una sola población: todo el departamento en el año dado."""
    anio = parametro("sd", "anio_base") if anio is None else anio
    p = parametros_base()
    cal = leer_calibracion() if calibrado else None
    if cal is not None:
        p.update(rho=cal["rho"], beta_s=cal["beta_s"], expuestos_iniciales=cal["I0"])
        for clave in ("ganancia_fumigacion", "lluvia_minima"):
            if clave in cal:
                p[clave] = cal[clave]
    p["anio"] = anio
    p["Nh"] = float(poblacion_anio(anio).sum())
    p["lluvia"] = lluvia_departamento(anio)
    p.update(cambios)
    p["k"] = escala_k(p)
    return p


# ------------------------------------------------------------------ ecuaciones
def derivadas(t, y, p):
    """dy/dt del modelo SEIR–SEI con lluvia (A2) y fumigación endógena (A3)."""
    Sh, Eh, Ih = y[..., ISH], y[..., IEH], y[..., IIH]
    Sv, Ev, Iv = y[..., ISV], y[..., IEV], y[..., IIV]
    X1, X2, X3, Cn, F = y[..., IX1], y[..., IX2], y[..., IX3], y[..., ICN], y[..., IFU]
    Nh = p["Nh"]

    lam_h = p["beta_s"] * p["a"] * p["b"] * Iv / Nh        # 1/día
    lam_v = p["a"] * p["c"] * Ih / Nh                      # 1/día
    dX1, dX2, dX3, Lam = derivadas_criaderos(t, X1, X2, X3, p)
    mu_t = mortalidad_vector(F, p)                         # 1/día
    dCn, dF = derivadas_fumigacion(Eh, Cn, F, p)

    infeccion_h = lam_h * Sh                               # personas/día  S → E
    nuevos_casos = p["sigma_h"] * Eh                       # personas/día  E → I
    recuperados = p["gamma"] * Ih                          # personas/día  I → R
    infeccion_v = lam_v * Sv                               # mosquitos/día S → E
    incubados_v = p["sigma_v"] * Ev                        # mosquitos/día E → I

    dy = [
        -infeccion_h,                                      # dSh  personas/día
        infeccion_h - nuevos_casos,                        # dEh  personas/día
        nuevos_casos - recuperados,                        # dIh  personas/día
        recuperados,                                       # dRh  personas/día
        Lam - infeccion_v - mu_t * Sv,                     # dSv  mosquitos/día
        infeccion_v - incubados_v - mu_t * Ev,             # dEv  mosquitos/día
        incubados_v - mu_t * Iv,                           # dIv  mosquitos/día
        dX1, dX2, dX3,                                     # criaderos (huevo, larva, pupa)
        dCn, dF,                                           # loop B
        nuevos_casos,                                      # casos verdaderos acumulados
    ]
    return np.stack(np.broadcast_arrays(*dy), axis=-1)


def condicion_inicial(p, expuestos_iniciales=None):
    """Humanos: Eh = I0 y el resto susceptibles. Vector y criaderos en equilibrio
    con la lluvia de la primera semana: X_k = (τ/3)·entrada(0), Sv = Λ(0)/μ."""
    E0 = p["expuestos_iniciales"] if expuestos_iniciales is None else expuestos_iniciales
    E0 = np.asarray(E0, dtype=float)
    X1, X2, X3 = criaderos_en_equilibrio(p)
    Sv = X3 / (p["tau_desarrollo"] / 3.0) / mortalidad_vector(0.0, p)
    cero = np.zeros(np.broadcast(E0, p["Nh"], X1).shape)
    y0 = [p["Nh"] - E0, E0, cero, cero, Sv, cero, cero, X1, X2, X3, cero, cero, cero]
    return np.stack(np.broadcast_arrays(*y0), axis=-1).astype(float)


# ------------------------------------------------------------------ integración
def rk4_step(f, t, y, h, p):
    """Un paso de RK4: y_{n+1} = y_n + (h/6)(k1 + 2k2 + 2k3 + k4). Evalúa en t, t+h/2 y t+h
    porque el sistema depende del tiempo (lluvia)."""
    k1 = f(t, y, p)
    k2 = f(t + h / 2, y + h / 2 * k1, p)
    k3 = f(t + h / 2, y + h / 2 * k2, p)
    k4 = f(t + h, y + h * k3, p)
    return y + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


def euler_step(f, t, y, h, p):
    """Un paso de Euler explícito: y_{n+1} = y_n + h·f(t_n, y_n)."""
    return y + h * f(t, y, p)


def integrar(f, y0, p, dias, h, paso=rk4_step):
    """Integra de 0 a `dias` con paso h y guarda el estado al final de cada día.

    La lluvia es escalonada por semana. Si la etapa k4 de RK4 cae justo en el borde
    de una semana, toma la lluvia de la semana siguiente y el método baja a orden 1.
    Como 1/h es entero, ningún paso cruza un borde: se fija la semana del paso
    (la de su punto medio) y RK4 conserva su orden 4."""
    pasos_por_dia = int(round(1.0 / h))
    if abs(pasos_por_dia * h - 1.0) > 1e-9:
        raise ValueError("1/h debe ser entero para guardar un valor por día")
    Y = np.empty((dias + 1,) + y0.shape)
    Y[0] = y = y0
    for d in range(dias):
        p["semana_del_paso"] = d // 7
        for s in range(pasos_por_dia):
            y = paso(f, d + s * h, y, h, p)
        Y[d + 1] = y
    p["semana_del_paso"] = None
    return np.arange(dias + 1, dtype=float), Y


def simular_seir_sei(p, dias=364, h=None, expuestos_iniciales=None, paso=rk4_step):
    """Simula el modelo de una población. Devuelve {'t': días, 'Y': estados por día}."""
    h = parametro("sd", "paso_rk4") if h is None else h
    y0 = condicion_inicial(p, expuestos_iniciales)
    t, Y = integrar(derivadas, y0, p, dias, h, paso)
    return {"t": t, "Y": Y}


# ------------------------------------------------------------------ salidas
def casos_verdaderos_diarios(res):
    """Casos nuevos verdaderos por día = incremento diario de casos_acum (∫ σh·Eh dt)."""
    return np.diff(res["Y"][..., ICA], axis=0, prepend=res["Y"][:1, ..., ICA])


def casos_notificados_diarios(res, p):
    """Casos notificados por día = ρ · casos verdaderos."""
    return p["rho"] * casos_verdaderos_diarios(res)


def casos_notificados_semanales(res, p, n_semanas=None):
    """Casos notificados por semana epidemiológica (semana w = días 7(w−1) a 7w)."""
    acum = res["Y"][..., ICA]
    n_semanas = (len(acum) - 1) // 7 if n_semanas is None else n_semanas
    return p["rho"] * np.diff(acum[: 7 * n_semanas + 1: 7], axis=0)


def valores_en(t, Y, tiempos):
    """Interpola una trayectoria (t, Y) en otros tiempos (por ejemplo, semanas)."""
    return np.interp(tiempos, t, Y)


def metricas_epidemia(t, nuevos):
    """Pico (máximo de casos por día), día del pico y tamaño final (suma)."""
    i = int(np.argmax(nuevos))
    return {"pico": float(nuevos[i]), "dia_pico": int(t[i]), "tamano_final": float(np.sum(nuevos))}


def sce(observado, simulado):
    """Suma de cuadrados del error."""
    return float(np.sum((np.asarray(observado) - np.asarray(simulado)) ** 2))


def verificar_conservacion(Y, Nh):
    """Error máximo de Sh + Eh + Ih + Rh respecto a Nh (debe ser < 1e-6)."""
    total = Y[..., ISH] + Y[..., IEH] + Y[..., IIH] + Y[..., IRH]
    return float(np.max(np.abs(total - Nh)))


if __name__ == "__main__":
    p = parametros_departamento()
    res = simular_seir_sei(p)
    notif = casos_notificados_diarios(res, p)
    m = metricas_epidemia(res["t"], casos_verdaderos_diarios(res))
    print(f"Nh = {p['Nh']:.0f}, βs = {p['beta_s']:.3f}, ρ = {p['rho']:.4f}, I0 = {p['expuestos_iniciales']:.1f}")
    print(f"Pico de casos verdaderos = {m['pico']:.1f}/día el día {m['dia_pico']}; tamaño final = {m['tamano_final']:.0f}")
    print(f"Notificados en el año = {notif.sum():.0f}; error de conservación = {verificar_conservacion(res['Y'], p['Nh']):.2e}")
    sin = simular_seir_sei(p, expuestos_iniciales=0.0)
    print("Sin infectados iniciales, cambio máximo en humanos:",
          float(np.abs(sin["Y"][:, :4] - sin["Y"][0, :4]).max()))
