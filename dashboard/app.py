"""G5 · Demo de DengueSim GT en Streamlit.

    streamlit run dashboard/app.py

Reglas: el demo SOLO lee data/processed/ (tablas livianas); lo único que se recalcula en
vivo es el MCLP (resolver_mclp de src/sig/mclp.py). No importa geopandas, rasterio, osmnx
ni pyrosm: los GeoJSON se muestran directo con Folium.
"""

import json
import sys
from pathlib import Path

import folium
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "data" / "processed"
sys.path.insert(0, str(RAIZ / "src" / "sig"))
from mclp import resolver_mclp  # noqa: E402

ESCENARIOS = ["sin_intervencion", "fumigacion_aleatoria", "fumigacion_hubs", "eliminacion_criaderos",
              "linea_base_camas", "ampliacion_camas"]
ETIQUETAS = {"sin_intervencion": "Sin intervención", "fumigacion_aleatoria": "Fumigación aleatoria (3 municipios)",
             "fumigacion_hubs": "Fumigación en hubs (top 3 por grado)", "eliminacion_criaderos": "Eliminación de criaderos",
             "linea_base_camas": "Línea base de camas", "ampliacion_camas": "Ampliación de camas (+30 %)"}
AZUL, NARANJA, ROJO, GRIS = "#2a78d6", "#eb6834", "#b3261e", "#9a9a96"
CENTRO = [14.62, -90.53]
TEXTO = {"cod_muni": str, "cod_i": str, "cod_j": str, "id_hosp": str}


# ------------------------------------------------------------------ carga de datos
@st.cache_data
def leer(nombre):
    return pd.read_csv(DATOS / nombre, dtype=TEXTO)


@st.cache_data
def leer_json(nombre):
    return json.loads((DATOS / nombre).read_text(encoding="utf-8"))


@st.cache_data
def municipios():
    m = pd.read_csv(RAIZ / "config" / "municipios.csv", dtype={"cod_muni": str})
    return m.merge(leer("poblacion.csv")[["cod_muni", "poblacion"]], on="cod_muni")


@st.cache_data
def casos_semanales(escenario):
    """Casos verdaderos por semana y municipio (media de corridas) e incidencia por 100 000."""
    c = leer("sig/casos_resumen.csv")
    c = c[c.escenario == escenario].assign(semana=lambda d: d.dia // 7 + 1)
    s = c.groupby(["cod_muni", "semana"]).media.sum().reset_index()
    return s.merge(municipios()[["cod_muni", "nombre", "poblacion"]], on="cod_muni").assign(
        incidencia=lambda d: d.media / d.poblacion * 1e5)


@st.cache_data
def mclp_en_vivo(p, radio, ponderar):
    return resolver_mclp(p, radio, ponderar, devolver_detalle=True)


def escenario_epidemiologico(esc):
    """ampliacion_camas no cambia la epidemia: usa la de linea_base_camas."""
    return "linea_base_camas" if esc == "ampliacion_camas" else esc


def figura_base(titulo, eje_x, eje_y):
    fig = go.Figure()
    fig.update_layout(title=titulo, xaxis_title=eje_x, yaxis_title=eje_y, height=360,
                      margin=dict(l=10, r=10, t=40, b=10), template="plotly_white", legend=dict(orientation="h"))
    return fig


def mapa_folium(m, clave, alto=460):
    st_folium(m, height=alto, use_container_width=True, returned_objects=[], key=clave)


# ------------------------------------------------------------------ vistas
def vista_casos(esc):
    st.subheader("Casos esperados por municipio")
    st.caption("Casos **verdaderos** (sin factor de reporte) del modelo metapoblacional SEIR–SEI, media de 30 corridas. "
               "Para casos notificados, multiplicar por ρ = 0.2. La forma semanal de calibración es un **estimado**.")
    s = casos_semanales(escenario_epidemiologico(esc))
    semana = st.slider("Semana epidemiológica", 1, int(s.semana.max()), 36, key="semana_mapa")
    datos = s[s.semana == semana]
    m = folium.Map(location=CENTRO, zoom_start=10, tiles="OpenStreetMap")
    folium.Choropleth(geo_data=str(DATOS / "limites_municipios.geojson"), data=datos, columns=["cod_muni", "incidencia"],
                      key_on="feature.properties.cod_muni", fill_color="YlOrRd", fill_opacity=0.75, line_opacity=0.5,
                      legend_name=f"Casos por 100 000 hab. en la semana {semana}").add_to(m)
    mapa_folium(m, "mapa_casos")
    nombres = municipios().set_index("nombre").cod_muni
    nombre = st.selectbox("Municipio", list(nombres.index), key="muni_casos")
    c = leer("sig/casos_resumen.csv")
    c = c[(c.escenario == escenario_epidemiologico(esc)) & (c.cod_muni == nombres[nombre])]
    fig = figura_base(f"{nombre}: casos verdaderos por día", "Día del año 2023", "Casos por día")
    fig.add_trace(go.Scatter(x=c.dia, y=c.ic_sup, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=c.dia, y=c.ic_inf, fill="tonexty", fillcolor="rgba(42,120,214,0.2)", line=dict(width=0),
                             name="banda 2.5–97.5 % de las corridas"))
    fig.add_trace(go.Scatter(x=c.dia, y=c.media, line=dict(color=AZUL, width=2), name="media"))
    st.plotly_chart(fig, width="stretch")


def vista_red():
    st.subheader("Red de movilidad (modelo gravitacional calibrado con el Censo 2018)")
    st.caption("Solo flujos ≥ 100 personas/día. Círculo ∝ grado (fuerza total). En rojo, los 3 hubs.")
    f = leer("flujos_od.csv")
    f = f[f.flujo_diario >= 100]
    c = leer("centralidad.csv").merge(municipios(), on="cod_muni")
    hubs = set(c.nlargest(3, "grado").cod_muni)
    pos = c.set_index("cod_muni")[["lat_cabecera", "lon_cabecera"]]
    m = folium.Map(location=CENTRO, zoom_start=10, tiles="OpenStreetMap")
    maximo = f.flujo_diario.max()
    for r in f.itertuples():
        folium.PolyLine([pos.loc[r.cod_i].tolist(), pos.loc[r.cod_j].tolist()], weight=1 + 9 * r.flujo_diario / maximo,
                        color=AZUL, opacity=0.45, tooltip=f"{r.cod_i} → {r.cod_j}: {r.flujo_diario:.0f} personas/día").add_to(m)
    for r in c.itertuples():
        folium.CircleMarker([r.lat_cabecera, r.lon_cabecera], radius=4 + 22 * np.sqrt(r.grado / c.grado.max()),
                            color=ROJO if r.cod_muni in hubs else GRIS, fill=True, fill_opacity=0.8,
                            tooltip=f"{r.nombre}: grado {r.grado:,.0f} personas/día").add_to(m)
    mapa_folium(m, "mapa_red")
    st.dataframe(c[["cod_muni", "nombre", "grado", "intermediacion", "eigenvector"]].sort_values("grado", ascending=False),
                 hide_index=True, width="stretch")


def vista_ranking():
    st.subheader("Ranking de riesgo (riesgo epidemiológico + centralidad en la red)")
    st.caption("puntaje = 0.6 · riesgo_casos + 0.4 · centralidad; riesgo = 0.7 · incidencia esperada + 0.3 · rapidez de "
               "llegada. El orden de llegada por municipio **no está validado** con datos (solo hay 4 áreas de salud).")
    r = leer("ranking_riesgo.csv").merge(municipios()[["cod_muni", "nombre"]], on="cod_muni")
    fig = figura_base("Puntaje por municipio", "Puntaje", "")
    fig.add_trace(go.Bar(y=r.nombre, x=r.riesgo_casos * 0.6, orientation="h", name="0.6 × riesgo de casos", marker_color=AZUL))
    fig.add_trace(go.Bar(y=r.nombre, x=r.centralidad * 0.4, orientation="h", name="0.4 × centralidad", marker_color=NARANJA))
    fig.update_layout(barmode="stack", height=520, yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, width="stretch")
    st.dataframe(r[["posicion", "cod_muni", "nombre", "riesgo_casos", "centralidad", "puntaje"]], hide_index=True, width="stretch")
    st.markdown("**Sensibilidad del ranking** (Spearman contra el ranking base)")
    st.dataframe(leer("sig/ranking_sensibilidad.csv"), hide_index=True, width="stretch")


def vista_salud(esc):
    st.subheader("Camas e insumos por hospital")
    st.caption("DES en SimPy (réplica 0). **No hay dato de camas**: se supone 30 camas de dengue por hospital "
               "(rango 10–60); el resultado principal es la curva de saturación contra capacidad.")
    o, inv = leer("ocupacion_camas.csv"), leer("inventario.csv")
    h = leer("hospitales.csv").set_index("id_hosp").nombre
    ids = sorted(o.id_hosp.unique())
    hosp = st.selectbox("Hospital", ids, format_func=lambda i: f"{i} · {h.get(i, '')}", index=ids.index("H013")
                        if "H013" in ids else 0, key="hospital")
    oo = o[(o.escenario == esc) & (o.id_hosp == hosp)]
    ii = inv[(inv.escenario == esc) & (inv.id_hosp == hosp)]
    col1, col2 = st.columns(2)
    fig = figura_base("Ocupación y cola", "Día", "Pacientes")
    fig.add_trace(go.Scatter(x=oo.dia, y=oo.ocupadas, name="camas ocupadas", line=dict(color=AZUL)))
    fig.add_trace(go.Scatter(x=oo.dia, y=oo.en_cola, name="en cola", line=dict(color=ROJO)))
    col1.plotly_chart(fig, width="stretch")
    fig = figura_base("Insumos (dos stocks)", "Día", "Unidades relativas")
    fig.add_trace(go.Scatter(x=ii.dia, y=ii.I, name="inventario I", line=dict(color=AZUL)))
    fig.add_trace(go.Scatter(x=ii.dia, y=ii.P, name="en tránsito P", line=dict(color=NARANJA)))
    col2.plotly_chart(fig, width="stretch")
    st.caption("I < 0 = déficit acumulado (el modelo es lineal y no se recorta a 0).")
    sat = leer("salud/saturacion_vs_capacidad.csv")
    sat = sat[(sat.id_hosp == "departamento") & (sat.metrica == "dias_saturacion")]
    fig = figura_base("Saturación contra capacidad (línea base)", "Camas de dengue por hospital", "Días-hospital con cola")
    fig.add_trace(go.Scatter(x=sat.camas, y=sat.media, mode="lines+markers", line=dict(color=AZUL),
                             error_y=dict(type="data", symmetric=False, array=sat.ic_sup - sat.media,
                                          arrayminus=sat.media - sat.ic_inf), name="media e IC 95 %"))
    st.plotly_chart(fig, width="stretch")
    st.dataframe(leer("salud/comparacion_ampliacion.csv"), hide_index=True, width="stretch")


def vista_estabilidad():
    st.subheader("Estabilidad de la política de insumos y robustez de las conclusiones")
    st.caption("π/2 es la frontera del **retardo puro** dx/dt = −α·x(t−τ). El modelo de dos stocks siempre converge; "
               "oscila si α·τ > 1/4.")
    mapa = leer("salud/mapa_estabilidad.csv")
    alphas, taus = np.unique(mapa.alpha), np.unique(mapa.tau)
    z = mapa.alpha_tau.to_numpy().reshape(len(alphas), len(taus))
    col1, col2 = st.columns(2)
    fig = figura_base("α·τ en el rango del YAML", "τ (días)", "α (1/día)")
    fig.add_trace(go.Contour(x=taus, y=alphas, z=z, colorscale="Blues", contours=dict(coloring="heatmap"),
                             colorbar=dict(title="α·τ")))
    for nivel, color, nombre in ((np.pi / 2, ROJO, "α·τ = π/2"), (0.25, "#1a1a1a", "α·τ = 1/4")):
        fig.add_trace(go.Scatter(x=taus, y=nivel / taus, mode="lines", line=dict(color=color, width=2), name=nombre))
    fig.update_yaxes(range=[alphas.min(), alphas.max()])
    col1.plotly_chart(fig, width="stretch")
    mc, res = leer("salud/montecarlo_estabilidad.csv"), leer_json("salud/montecarlo_estabilidad.json")
    fig = figura_base(f"Monte Carlo: P(estable_B) = {res['P_estable_B']:.2f} · P(oscila_A) = {res['P_oscila_A']:.2f}",
                      "α·τ", "Muestras")
    fig.add_trace(go.Histogram(x=mc.alpha_tau, nbinsx=60, marker_color=AZUL, name="α·τ"))
    fig.add_vline(x=np.pi / 2, line_color=ROJO)
    fig.add_vline(x=0.25, line_color="#1a1a1a", line_dash="dash")
    col2.plotly_chart(fig, width="stretch")
    st.markdown("**Robustez** (`prob_mejor` = fracción de juegos de parámetros en que el escenario es el mejor)")
    rob = leer("robustez.csv")
    metrica = st.selectbox("Métrica", list(rob.metrica.unique()), key="metrica_robustez")
    st.dataframe(rob[rob.metrica == metrica].sort_values("prob_mejor", ascending=False), hide_index=True, width="stretch")


def vista_sig():
    st.subheader("Isocronas a hospitales y ubicación óptima de unidades (MCLP)")
    cob = leer("sig/cobertura_isocronas.csv")
    st.dataframe(cob[cob.cod_muni == "departamento"].drop(columns="cod_muni"), hide_index=True, width="stretch")
    st.caption("Población repartida de forma uniforme dentro de cada municipio (aproximación: el ráster WorldPop no "
               "está en el repositorio). Tiempos de OSM en flujo libre × factor de congestión.")
    h = leer("hospitales.csv")
    h = h[h.atiende_dengue.astype(bool)]
    m = folium.Map(location=CENTRO, zoom_start=10, tiles="OpenStreetMap")
    for minutos, color in ((60, "#a9cdf0"), (30, AZUL)):
        folium.GeoJson(str(DATOS / "sig" / f"isocronas_{minutos}.geojson"), name=f"{minutos} min",
                       style_function=lambda _, c=color: {"fillColor": c, "color": c, "weight": 0.5, "fillOpacity": 0.45}
                       ).add_to(m)
    for r in h.itertuples():
        folium.CircleMarker([r.lat, r.lon], radius=3, color=ROJO, fill=True, tooltip=r.nombre).add_to(m)
    mapa_folium(m, "mapa_isocronas")

    st.markdown("**MCLP en Amatitlán** (se recalcula en vivo con PuLP + CBC)")
    col1, col2, col3 = st.columns(3)
    p = col1.slider("Unidades nuevas (p)", 1, 10, 3, key="p_mclp")
    radio = col2.slider("Radio de cobertura (m)", 1000, 3000, 2000, step=250, key="radio_mclp")
    ponderar = col3.checkbox("Ponderar por mosquitos por persona", value=True, key="ponderar_mclp")
    unidades, detalle = mclp_en_vivo(p, radio, ponderar)
    a, b, c = st.columns(3)
    a.metric("Demanda cubierta antes", f"{detalle['demanda_cubierta_antes_pct']:.1f} %")
    b.metric("Después (óptimo)", f"{detalle['demanda_cubierta_despues_pct']:.1f} %")
    c.metric("Después (voraz, Lab 5)", f"{detalle['voraz_demanda_cubierta_despues_pct']:.1f} %")
    g = leer("grilla_piloto.csv")
    m = folium.Map(location=[g.lat.mean(), g.lon.mean()], zoom_start=12, tiles="OpenStreetMap")
    for r in unidades.itertuples():
        folium.Circle([r.lat, r.lon], radius=radio, color=AZUL, fill=True, fill_opacity=0.12, weight=1).add_to(m)
        folium.Marker([r.lat, r.lon], tooltip=f"{r.cod_celda}: cubre {r.poblacion_cubierta:,} hab. nuevos").add_to(m)
    for r in h[(h.lat.between(g.lat.min() - 0.05, g.lat.max() + 0.05)) & (h.lon.between(g.lon.min() - 0.05, g.lon.max() + 0.05))].itertuples():
        folium.CircleMarker([r.lat, r.lon], radius=5, color=ROJO, fill=True, tooltip=f"existente: {r.nombre}").add_to(m)
    mapa_folium(m, "mapa_mclp")
    st.dataframe(unidades, hide_index=True, width="stretch")


def vista_automata():
    st.subheader("Autómata celular de mosquitos (zona piloto, Amatitlán)")
    st.caption("Densidad semanal relativa a la capacidad de carga; vecindad de Moore; la lluvia impulsa el crecimiento.")
    st.image(str(DATOS / "ca_mosquitos.gif"))


def vista_abm():
    st.subheader("Modelo basado en agentes (Mesa 2.4.0, zona piloto)")
    r = leer("sig/abm_resumen.csv")
    res = leer_json("abm/resumen_corridas.json")
    pico = res["pico"]
    a, b, c = st.columns(3)
    a.metric("Corridas (criterio de paro)", res["M_final"])
    b.metric("Pico de casos diarios (media)", f"{pico['media']:.1f}", help=f"IC 95 % bootstrap: {pico['ic_inf']}–{pico['ic_sup']}")
    c.metric("Día del pico (media)", f"{res['dia_pico']['media']:.0f}",
             help=f"IC 95 %: {res['dia_pico']['ic_inf']}–{res['dia_pico']['ic_sup']}")
    fig = figura_base("Nuevos casos diarios (agentes; 1 agente = 25 personas)", "Día desde la semana 18 de 2023", "Agentes")
    fig.add_trace(go.Scatter(x=r.dia, y=r.ic_sup, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=r.dia, y=r.ic_inf, fill="tonexty", fillcolor="rgba(42,120,214,0.2)", line=dict(width=0),
                             name="banda 2.5–97.5 % de las corridas"))
    fig.add_trace(go.Scatter(x=r.dia, y=r.media, line=dict(color=AZUL, width=2), name="media"))
    st.plotly_chart(fig, width="stretch")
    st.caption(f"IC 95 % del pico por bootstrap (B = 2000): {pico['ic_inf']} – {pico['ic_sup']} casos/día.")


# ------------------------------------------------------------------ aplicación
def main():
    st.set_page_config(page_title="DengueSim GT", layout="wide")
    st.title("DengueSim GT · Dengue en los 17 municipios del departamento de Guatemala")
    st.sidebar.header("Escenario")
    esc = st.sidebar.selectbox("Escenario", ESCENARIOS, format_func=ETIQUETAS.get, key="escenario")
    if esc == "ampliacion_camas":
        st.sidebar.info("La ampliación de camas no cambia la epidemia: las vistas de casos usan la línea base.")
    st.sidebar.markdown("Redes + ABM · Dinámica de sistemas · Salud · SIG — Modelación y Simulación, UVG 2026")
    pestanas = st.tabs(["Casos por municipio", "Red de movilidad", "Ranking de riesgo", "Camas e insumos",
                        "Estabilidad y robustez", "Isocronas y MCLP", "Autómata de mosquitos", "ABM"])
    vistas = [lambda: vista_casos(esc), vista_red, vista_ranking, lambda: vista_salud(esc), vista_estabilidad,
              vista_sig, vista_automata, vista_abm]
    for pestana, vista in zip(pestanas, vistas):
        with pestana:
            vista()


main()
