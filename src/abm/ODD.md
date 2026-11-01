# ODD del ABM de dengue — DengueSim GT (zona piloto Amatitlán)

Protocolo ODD (*Overview, Design concepts, Details*) según Grimm et al. (2020).
**Versión completa (N3, 2026-11-01).** La versión inicial (N1) es del 2026-10-30; en N3 se ampliaron los conceptos de diseño (sección 4) y se agregaron la verificación, la calibración, los resultados y la validación por edad (sección 8).

- **Implementación:** Python 3.12, **Mesa 2.4.0** (API clásica `mesa.time`, igual que el Laboratorio 4), NumPy y pandas.
- **Código:** `src/abm/` (`agentes.py`, `modelo.py`, `inicializacion.py`, `grilla.py`, `reglas.py`, `movilidad.py`, `corridas.py`, `beta_efectiva.py`, `experimento_scheduler.py`, `validacion_edad.py`).
- **Pruebas:** `tests/test_abm.py`.

---

## 1. Propósito y patrones

**Propósito.** Representar cómo la heterogeneidad individual (hogar, nivel socioeconómico, edad, movilidad diaria) y la distribución espacial de los mosquitos en una grilla de 500 m generan la transmisión local de dengue en Amatitlán (código INE 0114) durante la temporada de lluvias de 2023. El modelo produce:
1. Una **β efectiva** (1/día) para comparar con el modelo de Dinámica de Sistemas (`beta_efectiva.json`).
2. Distribuciones del pico, del día del pico y del tamaño del brote, con su incertidumbre (bootstrap).

**Patrones con los que se evalúa:**
- Incidencia **notificada** de Amatitlán en 2023 (`casos_anuales_muni.csv`: 1 826 casos), en la ventana simulada.
- Curva de la temporada: crecimiento con las lluvias (semanas 18–46).
- Distribución por edad de los casos (`casos_anuales_edad_sexo.csv`): validación de distribución (S8), resultado en la sección 8.4.

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

Los once elementos de Grimm et al. (2020):

1. **Principios básicos.** Transmisión de Ross–Macdonald (picadura → infección) resuelta en el espacio y en el tiempo: la fuerza de infección sobre una persona depende de los mosquitos por persona (`m_c`) y de la fracción de mosquitos infectados (`Y_c`) en la celda donde está en cada fase del día. Los humanos se mueven entre su casa y su lugar de trabajo o estudio (movilidad pendular del Censo 2018); los mosquitos no se mueven entre celdas. Es la versión individual y espacial del mismo mecanismo que usa el modelo de Dinámica de Sistemas (SEIR–SEI), lo que permite comparar las dos a través de la β efectiva (D13).
2. **Emergencia.** No se programan el tamaño ni la fecha del brote: emergen de dónde viven y adónde viajan las personas, de la abundancia de mosquitos de cada celda y semana, del almacenamiento de agua en el hogar y del azar de la cadena humano → mosquito → humano. El resultado emergente más claro es la **bimodalidad cerca del umbral**: con la misma `escala_mosquitos`, unas corridas se apagan con menos de 20 infectados y otras producen un brote de cientos (`calibracion_escala.csv`), lo que explica el CV alto entre corridas. También emerge la relación entre la red de movilidad y el riesgo: los agentes que trabajan en Guatemala o Villa Nueva se infectan fuera (R2) y siembran su celda de casa.
3. **Adaptación.** No hay. Las personas no cambian su conducta según el riesgo (no evitan picaduras ni dejan de viajar al enfermar, salvo la hospitalización). Es un supuesto deliberado: el curso pide reglas SI–ENTONCES simples y no hay datos para calibrar conductas adaptativas.
4. **Objetivos.** Los agentes no maximizan nada: siguen reglas fijas.
5. **Aprendizaje.** No hay. La única "memoria" individual es `busco_atencion` (R4 se evalúa una sola vez por infección) y `dias_en_estado`.
6. **Predicción.** Los agentes no predicen. El modelo, en cambio, sí sirve para predecir distribuciones (pico y día del pico con IC 95 %), nunca una trayectoria única.
7. **Percepción (sensing).** Ninguna persona percibe a otras. Cada una "percibe" solo la probabilidad de exposición de la celda en la que está en cada fase, que el modelo calcula una vez por paso (comunicación por el entorno). La incidencia del municipio de destino (R2) también es una variable del entorno, no de otros agentes.
8. **Interacción.** Indirecta, mediada por los mosquitos: una persona infecciosa sube `Y_c` de la celda donde está, y eso aumenta el riesgo de quienes pasan por esa celda en el paso siguiente. Como la interacción pasa por un entorno que se actualiza de forma síncrona, el orden en que se activan las personas no debería importar (S8). El experimento de D11 lo confirma (sección 8.3).
9. **Estocasticidad.** Hay azar en los atributos iniciales (Cholesky, casa, edad, destino, celda de trabajo), en el orden de activación (`self.random`, barajado por `RandomActivation`) y en todas las transiciones R1–R7 (`self.rng`, NumPy). Las dos fuentes salen de la misma semilla de `config/semillas.yaml`, así que la misma semilla da la misma corrida (probado). La corrida m usa siempre la semilla `SeedSequence(abm.base).spawn(...)[m]`.
10. **Colectivos.** Hogares implícitos: los agentes que comparten `celda_casa` comparten la exposición nocturna; no hay una entidad hogar con variables propias. Los municipios de destino son colectivos externos que solo aportan su incidencia (R2).
11. **Observación.** Por corrida: series diarias de S, E, I, H, R, nuevos infectados (dentro y fuera de la grilla), nuevos casos y `Y` medio; métricas de pico, día del pico y tamaño final; edad de cada infectado. Entre corridas: media e IC 95 % por bootstrap no paramétrico (B = 2 000), con criterio de paro por estabilidad del IC, `M* = (z·CV/0.05)²` y curva del error estándar contra M (S8: *una corrida es una anécdota*).

**Sensibilidad.** El ABM no tiene un análisis ±20 % propio (el de SD está en `src/sd/sensibilidad.py`); la sensibilidad más fuerte que se ve aquí es a `escala_mosquitos`: entre 0.97 y 1.34 la incidencia pasa de unas decenas a miles por 100 000 hab. (`calibracion_escala.csv`), señal de que el sistema opera cerca de su umbral.

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

## 8. Verificación, calibración y resultados

### 8.1 Verificación (S8)

Pruebas en `tests/test_abm.py`, todas pasan:
- El scheduler activa a **cada agente exactamente una vez por paso** (se parchea `Persona.step` y se registra el orden, como `test_scheduler` del Laboratorio 4), y los otros dos schedulers también activan a todos.
- **Misma semilla → misma corrida**; S + E + I + H + R = número de agentes en todo paso; las transiciones inválidas lanzan error.
- Grilla: sin infectados `Y = 0`; con infectados `Y` sube y, al quitarlos, decae a la tasa μ.
- Reglas R1–R7 con probabilidad 0 y 1; en la fase noche la ocupación suma los agentes no hospitalizados.
- Inicialización con 20 000 agentes (`validacion_atributos.csv`): proporciones a menos de 0.5 pp y correlaciones a menos de 0.002 de las del bloque 0114.

### 8.2 Calibración de `escala_mosquitos` (D12)

Grilla logarítmica de 8 valores entre 0.5 y 5, con 3 corridas cada uno y las mismas semillas. El objetivo es la incidencia **notificada** de Amatitlán en 2023 dentro de la ventana simulada: 962 por 100 000 hab. Se interpoló en escala log-log: `escala_mosquitos = 1.2542`. Con ese valor, 60 corridas dan 920 por 100 000 hab. (IC 95 % 665–1 197), que contiene el objetivo.

### 8.3 Resultados (60 corridas, criterio de paro cumplido)

| Métrica | Media | IC 95 % bootstrap | CV | M* para ±5 % |
|---|---|---|---|---|
| Pico de casos diarios (agentes) | 10.0 | 7.8–12.6 | 0.94 | 1 349 |
| Día del pico | 132.6 | 109–153 | 0.68 | 708 |
| Tamaño final (agentes infectados) | 232.9 | 168–304 | 1.17 | 2 110 |
| Incidencia notificada (por 100 000) | 920 | 665–1 197 | 1.17 | 2 110 |

- **Criterio de paro:** los extremos de los dos IC cambiaron menos de 5 % al pasar de 50 a 60 corridas, y la curva del error estándar se aplana (`figuras/abm/convergencia_ic.png`). Sin embargo, `M*` pide entre 700 y 2 100 corridas para que la **media** tenga un error relativo de ±5 %: los dos criterios responden a preguntas distintas (estabilidad del IC contra precisión relativa de la media). Con un CV cercano a 1, propio de un brote cerca del umbral, los IC son estables pero anchos. Hay que reportarlos así, como distribuciones.
- **β efectiva** (D13): 0.227 1/día (IC 95 % 0.195–0.257), a partir del ajuste `nuevos_infectados ≈ β·S·I/N` hasta el pico (`beta_efectiva_metodo.md`).
- **Experimento de scheduler** (D11, 20 corridas por scheduler con las mismas semillas): ninguna diferencia significativa con el mixto en pico, día del pico ni tamaño final; todos los IC de la diferencia incluyen 0 (`experimento_scheduler.csv`). Era lo esperado porque las personas se comunican a través del entorno, que se actualiza de forma síncrona.

### 8.4 Validación por edad (N3)

`src/abm/validacion_edad.py` compara la edad de los 16 575 agentes infectados de las 59 corridas con brote contra los casos observados de Amatitlán (1 826 en 2023 y 6 546 en 2014–2024) y contra la población por edad (`validacion_edad.csv`, `figuras/abm/validacion_edad.png`).

- Los infectados del ABM **repiten la pirámide de población**: índice de disimilitud D = 0.007 contra la población y riesgo relativo ≈ 1 en todos los grupos.
- Los casos observados **no**: D = 0.25 contra la población. Los grupos de 5–9 años (riesgo relativo 2.2) y de 10–14 (2.0) se enferman de más, y los de 25–49 y 60+ de menos (0.3–0.5). Contra los observados de 2014–2024, el ABM tiene D = 0.25 y solo 1 de 10 grupos queda dentro de su IC 95 %.
- **Interpretación:** es un fallo de validación **de distribución** que se reporta tal cual. En el modelo la edad no entra en ninguna regla y el destino se asigna sin mirar la edad. Las explicaciones posibles, sin evidencia aquí para separarlas, son: exposición escolar diurna (los niños pasan el día en escuelas con criaderos), inmunidad acumulada en los adultos por infecciones previas (el ABM empieza con todos susceptibles) y diferencias por edad en la búsqueda de atención y en la notificación.
- **Mejora propuesta:** asignar el destino según la edad (estudiantes de 5 a 19 años y trabajadores de 15 a 64) y una fracción inicial inmune que crezca con la edad. Ninguna de las dos se implementó, para no ajustar el modelo a posteriori sin datos que respalden los valores.

## 9. Supuestos y limitaciones

- **Sin incubación extrínseca** en el mosquito: un mosquito infectado transmite de inmediato, lo que acelera la cadena de transmisión. `escala_mosquitos` absorbe parte de ese efecto al calibrar.
- **Mosquitos sin movimiento entre celdas** en el ABM; su distribución espacial y estacional viene del autómata celular.
- **Celda de trabajo ∝ población**, no por empleo (no hay datos).
- **R2 usa la incidencia notificada ÷ ρ** del destino: supone el mismo subregistro en todos los municipios.
- **ρ no es identificable** con la curva semanal (ver A6); se usa el valor de literatura, 0.2. La incidencia notificada simulada depende de esa decisión.
- **Escala 1:25:** reduce el ruido demográfico real; bajarla después.
- El brote calibrado está **cerca del umbral**: CV alto entre corridas (0.94 en el pico) y M* grande (≈ 1 300 corridas para ±5 % en el pico).
- Una sola temporada (2023) y una sola zona piloto.
- **Todos empiezan susceptibles y la edad no modifica el riesgo**: el ABM no reproduce la distribución por edad observada (sección 8.4).
