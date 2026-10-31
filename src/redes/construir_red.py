"""D1 · Construcción de las redes de movilidad entre los 17 municipios.

Dos redes dirigidas con los mismos nodos (cod_muni):
  - red_gravitacional: flujos diarios del modelo gravitacional calibrado
    (flujos_od.csv). Con umbral 0 es un grafo completo: 17 × 16 = 272 aristas.
  - red_censo: matriz O-D observada del Censo 2018 (od_censo.csv, columna
    total = trabajadores + estudiantes), sin la diagonal (i == j) ni el destino
    FUERA (fuera del departamento).

Peso de cada arista: w_ij = personas/día que van de i a j. Para métricas que
no admiten grafos dirigidos se usa a_no_dirigida(G), con peso w_ij + w_ji.

Uso (desde la raíz):  python src/redes/construir_red.py
"""

import sys

import networkx as nx

sys.path.insert(0, "src/datos")
from comun import leer_procesado  # noqa: E402


def _agregar_nodos(G):
    """Los 17 municipios como nodos, con nombre y población (N de 2024)."""
    pob = leer_procesado("poblacion.csv")
    for fila in pob.itertuples():
        G.add_node(fila.cod_muni, nombre=fila.nombre, poblacion=int(fila.poblacion))
    return G


def red_gravitacional(umbral=0):
    """Red dirigida desde flujos_od.csv: arista i→j si flujo_diario >= umbral.

    Atributos de arista: weight = flujo_diario (personas/día) y tiempo_min
    (tiempo de viaje en flujo libre, de distancias.csv).
    """
    flujos = leer_procesado("flujos_od.csv")
    tiempos = leer_procesado("distancias.csv").set_index(["cod_i", "cod_j"])["tiempo_min"]
    G = _agregar_nodos(nx.DiGraph(nombre="gravitacional", umbral=umbral))
    for fila in flujos.itertuples():
        if fila.cod_i != fila.cod_j and fila.flujo_diario >= umbral:
            G.add_edge(fila.cod_i, fila.cod_j, weight=float(fila.flujo_diario),
                       tiempo_min=float(tiempos.loc[(fila.cod_i, fila.cod_j)]))
    return G


def red_censo(umbral=0):
    """Red dirigida desde od_censo.csv (total), sin diagonal ni destino FUERA."""
    od = leer_procesado("od_censo.csv")
    od = od[(od.cod_i != od.cod_j) & (od.cod_j != "FUERA") & (od.cod_i != "FUERA")]
    G = _agregar_nodos(nx.DiGraph(nombre="censo", umbral=umbral))
    for fila in od.itertuples():
        if fila.total >= umbral:
            G.add_edge(fila.cod_i, fila.cod_j, weight=float(fila.total))
    return G


def a_no_dirigida(G):
    """Grafo no dirigido con peso w_ij + w_ji (flujo total entre i y j)."""
    H = nx.Graph(**G.graph)
    H.add_nodes_from(G.nodes(data=True))
    for i, j, d in G.edges(data=True):
        if H.has_edge(i, j):
            H[i][j]["weight"] += d["weight"]
        else:
            H.add_edge(i, j, weight=d["weight"])
    return H


if __name__ == "__main__":
    for nombre, constructor in [("gravitacional", red_gravitacional), ("censo", red_censo)]:
        for u in (0, 100):
            G = constructor(u)
            print(f"{nombre:13s} umbral={u:3d}: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas, "
                  f"autoaristas={nx.number_of_selfloops(G)}, FUERA en nodos={'FUERA' in G}")
