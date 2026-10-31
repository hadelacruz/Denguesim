# β efectiva del ABM (`data/processed/beta_efectiva.json`)

**Qué es:** la tasa de transmisión β (en **1/día**) de un modelo SEIR **solo humano** que
produciría, en promedio, las mismas infecciones nuevas que el ABM de Amatitlán. Sirve para
compararla con el β equivalente del modelo de Dinámica de Sistemas (`β_eq = R0²·γ`, A5) y con el
umbral epidémico de la red (D4).

**Cómo se calcula** (`src/abm/beta_efectiva.py`):

1. Para cada corrida del ABM (`data/processed/abm/series.csv`, escala 1 agente = 25 personas):
   - `y(t)` = infecciones nuevas **locales** del día t (S→E dentro de la grilla). Se excluyen las
     infecciones fuera del municipio (regla R2), porque no dependen de los infecciosos locales.
   - `x(t) = S(t−1)·I(t−1)/N`, con el estado del día anterior: las infecciones del día t se
     sortean con el entorno (mosquitos) que dejó el paso anterior.
   - Ventana: desde el día del primer caso (E→I) hasta el día del pico de casos diarios.
   - Mínimos cuadrados **sin intercepto**: `β̂ = Σ x·y / Σ x²`.
2. Se descartan las corridas sin brote (menos de 2 días en la ventana).
3. `beta` = media de las β̂ por corrida; `ic_inf`, `ic_sup` = IC 95 % por **bootstrap no
   paramétrico** (B = `abm.bootstrap_B` = 2000) sobre las corridas.

Las β por corrida están en `data/processed/abm/beta_por_corrida.csv`.

**Limitaciones:**
- El dengue se transmite por mosquitos: las infecciones de hoy dependen de los infecciosos de
  días anteriores (a través de `Y_c`), no solo de `I(t−1)`. β resume ese efecto en un número y
  depende del retardo elegido.
- La ventana "primer caso → pico" tiene pocos días en las corridas con brotes pequeños, y por eso
  la β de esas corridas es ruidosa.
- Es una β **local** (zona piloto, temporada 2023 desde la semana 18), no departamental.
