"""D7 · Inicialización de la población de agentes de Amatitlán (0114).

Atributos del hogar con Cholesky sobre la correlación LATENTE (sigma_hogar.json):
    u ~ N(0, I₃),   Z = L·u  ~ N(0, R_latente)
    indice_riqueza = media + sd · Z0
    agua_entubada  = 1 si Z1 > umbral_agua
    almacena_agua  = 1 si Z2 > umbral_almacena
No se usa la covarianza observada directamente: con variables 0/1, una normal
con esa covarianza no reproduce las proporciones. Con el modelo latente
(umbral) sí se reproducen proporciones y correlaciones observadas.

Otros atributos:
  - celda_casa: proporcional a la población de la grilla (celdas con 0 no reciben).
  - edad: grupo según poblacion_edad.csv (Amatitlán, año más cercano a abm.anio)
    y luego uniforme dentro del grupo (supuesto: el grupo "65+" llega a 90 años).
  - destino: proporciones de la fila 0114 de od_censo.csv sobre la población
    del Censo 2018; el resto no trabaja ni estudia (destino None).
  - celda_trabajo: si el destino es 0114, celda ∝ población (supuesto: no hay
    datos de empleo por celda).

Salida: data/processed/abm/validacion_atributos.csv
Uso (desde la raíz):  python src/abm/inicializacion.py
"""

import json
import sys

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, "src/datos")
from comun import CONFIG, PROCESSED, leer_procesado, parametro  # noqa: E402

COD_PILOTO = "0114"
EDAD_MAXIMA = 90  # supuesto del modelo para el grupo abierto "65+"


def semilla(seccion, clave):
    """Semilla desde config/semillas.yaml."""
    with open(CONFIG / "semillas.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)[seccion][clave]


def bloque_hogar(cod=COD_PILOTO):
    """Bloque del municipio en sigma_hogar.json (medias, covarianza y latente)."""
    s = json.loads((PROCESSED / "sigma_hogar.json").read_text(encoding="utf-8"))
    return s["por_municipio"][cod]


def generar_atributos(n, rng, cod=COD_PILOTO):
    """indice_riqueza, agua_entubada y almacena_agua correlacionados (Cholesky latente)."""
    b = bloque_hogar(cod)
    L = np.array(b["latente"]["cholesky_L"])
    _, u_agua, u_alm = b["latente"]["umbrales"]
    media_ing, sd_ing = b["medias"][0], np.sqrt(b["covarianza"][0][0])
    Z = rng.standard_normal((n, 3)) @ L.T          # Z ~ N(0, R)
    return pd.DataFrame({
        "indice_riqueza": media_ing + sd_ing * Z[:, 0],
        "agua_entubada": (Z[:, 1] > u_agua).astype(int),
        "almacena_agua": (Z[:, 2] > u_alm).astype(int),
    })


def cargar_grilla():
    """Grilla piloto en un orden fijo (índice de celda = posición en la tabla)."""
    return pd.read_csv(PROCESSED / "grilla_piloto.csv", dtype={"cod_muni": str}).reset_index(drop=True)


def numero_agentes(grilla=None, escala=None):
    """Agentes = población de la grilla / personas por agente."""
    grilla = cargar_grilla() if grilla is None else grilla
    escala = parametro("abm", "escala_agentes") if escala is None else escala
    return int(round(grilla.poblacion.sum() / escala))


def asignar_celdas(n, grilla, rng):
    """Celdas con probabilidad ∝ población (las de población 0 nunca salen)."""
    w = grilla.poblacion.to_numpy(float)
    return rng.choice(len(grilla), size=n, p=w / w.sum())


def limites_grupo(grupo):
    """'< 1 año' → (0, 1); '1-4' → (1, 5); '65+' → (65, EDAD_MAXIMA)."""
    if grupo.startswith("<"):
        return 0, 1
    if grupo.endswith("+"):
        return int(grupo[:-1]), EDAD_MAXIMA
    a, b = grupo.split("-")
    return int(a), int(b) + 1


def asignar_edades(n, rng, anio=None, cod=COD_PILOTO):
    """Grupo de edad según la proyección del año más cercano y edad uniforme dentro."""
    anio = parametro("abm", "anio") if anio is None else anio
    pe = leer_procesado("poblacion_edad.csv")
    pe = pe[pe.cod_muni == cod]
    anio_usado = pe.anio.unique()[np.argmin(np.abs(pe.anio.unique() - anio))]
    grupos = pe[pe.anio == anio_usado].groupby("grupo_edad").poblacion.sum()
    elegido = rng.choice(len(grupos), size=n, p=(grupos / grupos.sum()).to_numpy())
    lim = np.array([limites_grupo(g) for g in grupos.index])
    return lim[elegido, 0] + rng.random(n) * (lim[elegido, 1] - lim[elegido, 0])


def proporciones_destino(cod=COD_PILOTO):
    """Fracción de residentes que trabaja/estudia en cada destino (Censo 2018)."""
    od = leer_procesado("od_censo.csv")
    od = od[od.cod_i == cod].set_index("cod_j")["total"]
    pob = leer_procesado("poblacion.csv").set_index("cod_muni").loc[cod, "poblacion_censo2018"]
    return od / pob


def asignar_destinos(n, rng, cod=COD_PILOTO):
    """Destino de cada agente (cod_muni, 'FUERA' o None si no trabaja ni estudia)."""
    prop = proporciones_destino(cod)
    opciones = list(prop.index) + [None]
    p = np.append(prop.to_numpy(), 1 - prop.sum())
    return [opciones[i] for i in rng.choice(len(opciones), size=n, p=p)]


def crear_poblacion(n, rng, grilla=None):
    """DataFrame con todos los atributos de los n agentes."""
    grilla = cargar_grilla() if grilla is None else grilla
    df = generar_atributos(n, rng)
    df["celda_casa"] = asignar_celdas(n, grilla, rng)
    df["edad"] = asignar_edades(n, rng)
    df["destino"] = asignar_destinos(n, rng)
    trabajo = asignar_celdas(n, grilla, rng)
    df["celda_trabajo"] = [int(c) if d == COD_PILOTO else None for c, d in zip(trabajo, df.destino)]
    return df


def validar_atributos(df, cod=COD_PILOTO):
    """Proporciones, medias y correlaciones simuladas contra el bloque del municipio."""
    b = bloque_hogar(cod)
    C = np.array(b["covarianza"])
    corr_obs = C / np.sqrt(np.outer(np.diag(C), np.diag(C)))
    variables = ["indice_riqueza", "agua_entubada", "almacena_agua"]
    corr_sim = df[variables].corr().to_numpy()
    filas = [{"medida": f"media_{v}", "observado": b["medias"][i], "simulado": df[v].mean()} for i, v in enumerate(variables)]
    filas.append({"medida": "sd_indice_riqueza", "observado": np.sqrt(C[0, 0]), "simulado": df.indice_riqueza.std()})
    for i, j in [(0, 1), (0, 2), (1, 2)]:
        filas.append({"medida": f"corr_{variables[i]}_{variables[j]}", "observado": corr_obs[i, j], "simulado": corr_sim[i, j]})
    out = pd.DataFrame(filas)
    out["diferencia"] = out.simulado - out.observado
    return out


if __name__ == "__main__":
    rng = np.random.default_rng(semilla("abm", "inicializacion"))
    n = max(numero_agentes(), 20000)  # el criterio de aceptación pide ≥ 10 000 agentes
    df = crear_poblacion(n, rng)
    val = validar_atributos(df)
    (PROCESSED / "abm").mkdir(parents=True, exist_ok=True)
    val.round(5).to_csv(PROCESSED / "abm" / "validacion_atributos.csv", index=False)
    print(f"{n} agentes de prueba (el modelo usa {numero_agentes()} con escala {parametro('abm', 'escala_agentes')})")
    print(val.round(4).to_string(index=False))
    print("\nDestinos:", df.destino.fillna("ninguno").value_counts(normalize=True).round(3).head(6).to_dict())
    print("Edad media:", round(df.edad.mean(), 1), "| celdas con agentes:", df.celda_casa.nunique())
