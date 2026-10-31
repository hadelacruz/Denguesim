# ODD del ABM de dengue — DengueSim GT (zona piloto Amatitlán)

Protocolo ODD (*Overview, Design concepts, Details*) según Grimm et al. (2020).
**Versión inicial (N1, 2026-10-30).** Pendiente para N3: ampliar los conceptos de diseño y agregar los resultados.

- **Implementación:** Python 3.12, **Mesa 2.4.0** (API clásica `mesa.time`, igual que el Laboratorio 4), NumPy y pandas.
- **Código:** `src/abm/` (`agentes.py`, `modelo.py`, `inicializacion.py`, `grilla.py`, `reglas.py`, `movilidad.py`, `corridas.py`, `beta_efectiva.py`).
- **Pruebas:** `tests/test_abm.py`.

---

## 1. Propósito y patrones

**Propósito.** Representar cómo la heterogeneidad individual (hogar, nivel socioeconómico, edad, movilidad diaria) y la distribución espacial de los mosquitos en una grilla de 500 m generan la transmisión local de dengue en Amatitlán (código INE 0114) durante la temporada de lluvias de 2023. El modelo produce:
1. Una **β efectiva** (1/día) para comparar con el modelo de Dinámica de Sistemas (`beta_efectiva.json`).
2. Distribuciones del pico, del día del pico y del tamaño del brote, con su incertidumbre (bootstrap).

**Patrones con los que se evalúa:**
- Incidencia **notificada** de Amatitlán en 2023 (`casos_anuales_muni.csv`: 1 826 casos), en la ventana simulada.
- Curva de la temporada: crecimiento con las lluvias (semanas 18–46).
- (N3) Distribución por edad de los casos (`casos_anuales_edad_sexo.csv`).

## 2. Entidades, variables de estado y escalas

| Entidad | Variables | Implementación |
|---|---|---|
| **Persona** (agente de Mesa) | `estado` ∈ {S, E, I, H, R}; `edad`; `indice_riqueza` (índice de riqueza, **no** es dinero); `agua_entubada`, `almacena_agua` (0/1); `celda_casa`; `celda_trabajo` (o `None`); `destino` (`"0114"`, otro `cod_muni`, `"FUERA"` o `None`); `dias_en_estado`; `busco_atencion`; `activaciones` | `agentes.Persona(mesa.Agent)` |
| **Celda** de 500 m (470, de las cuales 10 tienen población 0) | `m_c(t)` mosquitos por persona; `Y_c(t)` fracción de mosquitos infectados | Arreglos de NumPy (**no** son agentes de Mesa) |
| **Modelo** | día t, probabilidades de exposición por celda y fase, contadores | `modelo.ModeloDengue(mesa.Model)` |

**Escalas:**
- Temporal: paso de **1 día**, con fase día y fase noche; 200 días desde la semana epidemiológica 18 de 2023.
- Espacial: grilla de 500 m (`grilla_piloto.csv`), con 126 548 habitantes.
- Agregación: 1 agente = `abm.escala_agentes` = 25 personas → 5 062 agentes.

## 3. Visión general del proceso y scheduling

**Scheduler mixto**, justificado por la regla de clase (S8): *síncrono para procesos físicos, asíncrono aleatorio para comportamiento social*.

Cada paso (día):
1. **Entorno → probabilidades (síncrono, NumPy, una vez):** con `Y_c` del paso anterior y `m_c(t)` se calcula la probabilidad de exposición de cada celda en la fase día, en la fase noche y en la fase noche para hogares que almacenan agua.
2. **Personas (`RandomActivation`, orden barajado):** cada persona hace una sola consulta y un solo sorteo para combinar la exposición de ambas fases (R1, R2); después aplica R3–R7. Las personas **no leen el estado de otras personas**: se comunican a través del entorno.
3. **Personas → entorno (síncrono, doble buffer):** con la ocupación de ambas fases se calcula `f_c` y se actualiza `Y` de todas las celdas a la vez.
4. **Registro:** `DataCollector` guarda S, E, I, H, R, `nuevos_infectados`, `nuevos_infectados_fuera`, `nuevos_casos` e `Y_medio`.

Para el experimento de D11 también están `BaseScheduler` (`"secuencial_fijo"`) y `SimultaneousActivation` (`"sincrono"`: `step()` decide y `advance()` aplica).

## 4. Conceptos de diseño

- **Principios básicos:** transmisión Ross–Macdonald (picadura → infección) resuelta en el espacio; los humanos se mueven entre su casa y su lugar de trabajo o estudio, y los mosquitos se quedan en su celda.
- **Emergencia:** el tamaño, la fecha y la variabilidad del brote emergen de dónde viven y se mueven las personas, de la abundancia de mosquitos por celda y del azar en la cadena humano–mosquito–humano.
- **Adaptación y objetivos:** no hay; las personas siguen reglas fijas.
- **Percepción:** ninguna persona percibe a otras; solo "perciben" el riesgo de su celda (comunicación por el entorno).
- **Interacción:** indirecta, a través de `Y_c` (proceso físico síncrono).
- **Estocasticidad:** atributos iniciales, orden de activación (`self.random`) y todas las transiciones (`self.rng`, NumPy). Las dos fuentes salen de la misma semilla (`config/semillas.yaml`); misma semilla → misma corrida (probado).
- **Colectivos:** hogares implícitos (la celda de la casa).
- **Observación:** series diarias por corrida, métricas por corrida (pico, día del pico, tamaño final) y la edad de cada infectado; IC 95 % por bootstrap sobre las corridas (S8: *una corrida es una anécdota*).
- *(N3: ampliar con aprendizaje, predicción y sensibilidad.)*

## 5. Inicialización

- **Atributos del hogar:** Cholesky sobre la correlación **latente** del bloque `0114` de `sigma_hogar.json`. Con `Z = L·u` y `u ~ N(0, I)`: el índice de riqueza es `media + sd·Z0`, y las variables binarias salen de umbrales sobre `Z1` y `Z2`. Validado con 20 000 agentes: proporciones a < 0.5 pp y correlaciones a < 0.002 (`data/processed/abm/validacion_atributos.csv`).
- **Casa:** celda con probabilidad ∝ población (las celdas con 0 no reciben agentes).
- **Edad:** grupo según `poblacion_edad.csv` (Amatitlán, 2023) y edad uniforme dentro del grupo; el grupo abierto "65+" llega hasta 90 años (supuesto).
- **Destino:** proporciones de la fila 0114 de `od_censo.csv` sobre la población del Censo 2018: 53.0 % se queda en Amatitlán, 6.6 % va a Guatemala, 2.7 % a Villa Nueva, 2.4 % sale del departamento, el resto a otros municipios, y 34.5 % no trabaja ni estudia.
- **Trabajo en Amatitlán:** celda ∝ población (supuesto: no hay datos de empleo por celda).
- **Infección inicial:** `abm.infectados_iniciales` = 5 agentes en E; `Y_c = 0` en todas las celdas.

## 6. Datos de entrada

| Archivo | Uso |
|---|---|
| `ca_mosquitos.npz` | Densidad semanal de mosquitos por celda (autómata celular, 2023) → `m_c(t)` |
| `grilla_piloto.csv` | Celdas, población y posición |
| `sigma_hogar.json` | Correlación latente, umbrales y Cholesky del bloque 0114 |
| `poblacion_edad.csv`, `od_censo.csv`, `poblacion.csv` | Edad, destinos y población del Censo 2018 |
| `casos_anuales_muni.csv`, `poblacion_anual.csv` | Incidencia de los destinos (R2) y objetivo de calibración |
| `data/processed/sd/calibracion.json` | Factor de reporte ρ (módulo de Alex) |

## 7. Submodelos

| # | SI | ENTONCES | CON probabilidad (por día) |
|---|---|---|---|
| R1 | S en la celda c durante una fase | E | `1 − exp(−a·b·m_c·Y_c·w_fase·factor_hogar)`; `factor_hogar = 1 + efecto_almacena_agua` solo de noche y si almacena agua |
| R2 | S con destino en otro municipio (fase día) | E | incidencia notificada anual del destino (o del departamento para `FUERA`) ÷ 365 ÷ ρ × `w_dia` |
| R3 | E | I | `1 − exp(−σh)` |
| R4 | recién pasó a I | busca atención (una vez) | `clip(prob_busca_atencion_base + efecto_riqueza_atencion · indice_riqueza, 0, 1)` |
| R5 | I y buscó atención (se evalúa una vez) | H | `clip(fraccion_hospitalizada / prob_media_busca_atencion, 0, 1)` |
| R6 | I | R | `1 − exp(−γ)` |
| R7 | H | R | `1 / estancia_media` |

Las dos fases se combinan con un solo sorteo: `p = 1 − (1 − p_dia)(1 − p_noche)`. Los agentes en H no están en ninguna celda.

**Grilla (síncrona, doble buffer):**
- `m_c(t) = escala_mosquitos · densidad_c(semana) / poblacion_c`
- `f_c = w_dia · I_dia/N_dia + (1 − w_dia) · I_noche/N_noche`
- `Y_c(t+1) = clip(Y_c + a·c·f_c·(1 − Y_c) − μ·Y_c, 0, 1)`

**Movilidad:**
- De día: casa (sin destino), celda de trabajo (destino 0114) o fuera (otro destino).
- De noche: todos en casa.

### Tabla de parámetros

| Parámetro | Valor | Rango | Unidad | Fuente |
|---|---|---|---|---|
| a | 0.5 | 0.3–1.0 | picaduras/mosquito/día | scott2000; andraud2012 |
| b | 0.5 | 0.1–0.75 | probabilidad | newton_reiter1992; andraud2012 |
| c | 0.5 | 0.25–0.9 | probabilidad | newton_reiter1992; andraud2012 |
| σh | 0.1695 | 0.10–0.333 | 1/día | chan_johansson2012 |
| γ | 0.2 | 0.143–0.25 | 1/día | gubler1998; nishiura_halstead2007 |
| μ | 0.0714 | 0.024–0.125 | 1/día | brady2013; focks1993 |
| fraccion_hospitalizada | 0.10 | 0.05–0.25 | fracción | who2009; shepard2011 |
| estancia_media | 4 | 3–6 | días | suaya2009; who2009 |
| ρ (factor de reporte) | 0.2 | 0.05–0.5 | fracción | shepard2011; stanaway2016 (fijado en A6: no identificable) |
| escala_agentes | 25 | 1–100 | personas/agente | supuesto del modelo |
| escala_mosquitos | 1.2542 | — | multiplicador | **calibrado** (D12) contra la incidencia de Amatitlán 2023 |
| fraccion_picaduras_dia (w_dia) | 0.5 | 0.3–0.7 | fracción | supuesto del modelo |
| efecto_almacena_agua | 0.3 | 0–0.6 | fracción | supuesto del modelo |
| prob_busca_atencion_base | 0.5 | 0.3–0.7 | probabilidad | supuesto del modelo |
| efecto_riqueza_atencion | 0.1 | 0–0.2 | probabilidad/sd | supuesto del modelo |
| infectados_iniciales | 5 | 1–20 | agentes | supuesto del modelo |
| anio, semana_inicio, dias_simulacion | 2023, 18, 200 | — | — | decisión del equipo |

## Supuestos y limitaciones

- **Sin incubación extrínseca** en el mosquito: un mosquito infectado transmite de inmediato, lo que acelera la cadena de transmisión. `escala_mosquitos` absorbe parte de ese efecto al calibrar.
- **Mosquitos sin movimiento entre celdas** en el ABM; su distribución espacial y estacional viene del autómata celular.
- **Celda de trabajo ∝ población**, no por empleo (no hay datos).
- **R2 usa la incidencia notificada ÷ ρ** del destino: supone el mismo subregistro en todos los municipios.
- **ρ no es identificable** con la curva semanal (ver A6); se usa el valor de literatura, 0.2. La incidencia notificada simulada depende de esa decisión.
- **Escala 1:25:** reduce el ruido demográfico real; bajarla después.
- El brote calibrado está **cerca del umbral**: CV alto entre corridas (0.94 en el pico) y M* grande (≈ 1 300 corridas para ±5 % en el pico).
- Una sola temporada (2023) y una sola zona piloto.
