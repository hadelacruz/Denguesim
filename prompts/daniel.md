## [2026-11-01] Tareas pendientes N2/N3 — calibración 2017–2025 (A6), población abierta (A9), orden de llegada (A12), validación por edad del ABM, ODD completo e instalación limpia (Redes + ABM y Dinámica de Sistemas)

**Prompt usado:**
> Ya estoy analizando el orden de llegada (A12) para las 4 áreas usando Spearman, pero me tira un `p-value = 0` con `rho = 1` y `n = 4`, que obviamente está mal porque la distribución t de scipy asume muestras grandes. ¿Me pasas el código para cambiarlo a una prueba de permutación exacta? De paso, mientras yo termino de cuadrar el `conclusiones_n2_n3.md` y pulir el documento ODD, dame una sugerencia de qué commits (unos 5-7 por persona) deberíamos armar para subir todo este bloque final de SD y ABM; recuerda que los haré yo a mano, no vayas a commitear nada.

**Qué se esperaba:** terminar lo pendiente de la guía: calibración por año 2017–2025 (N2), A9, A12, validación por edad del ABM, ODD completo y prueba de instalación limpia, con pruebas y sin hacer commits.

**Resultado:** satisfactorio. Se completaron los últimos experimentos estructurales (dinámica abierta, validación temporal larga y distribución demográfica). El repositorio se probó desde cero con éxito y el ODD está finalizado.

**Por qué creemos que pasó y qué se corrigió:** los modelos corrieron bien, pero hubo algunos ajustes técnicos que depurar en el proceso:
- **Intento fallido:** al agregar `sd.esperanza_vida_humana` al YAML para la población abierta, una descripción con "(A9): " rompió el archivo, porque YAML interpreta los dos puntos como clave de un nuevo nivel. Eso hizo fallar la lectura de la calibración anual. Se corrigió poniéndole comillas a todo el string.
- **Corregido:** el error estadístico esperado en A12: la p de `scipy.stats.spearmanr` daba 0 con n=4. Se implementó la prueba de permutación exacta (24 combinaciones) para calcular el p-value real sin la aproximación t.

**Resultados que hay que discutir (no se forzaron):** 
1. La lluvia mínima queda empujada hacia su límite superior todos los años. 
2. Con los parámetros del 2023 constantes, la lluvia por sí sola no logra explicar la variabilidad interanual (correlación −0.17), sugiriendo factores de inmunidad plurianual u otras variables. 
3. El ABM sigue la pirámide de población demográfica y no captura el sesgo observado en los datos reales hacia ciertas edades (D = 0.25). 
4. El análisis del orden de llegada (A12) con solo 4 macro-áreas no tiene suficiente poder estadístico para ser concluyente.

**Cómo contribuyó la IA:** corrigió el error sintáctico de YAML, implementó la prueba de permutación en Python para el análisis del orden de llegada, y listó las agrupaciones sugeridas para los commits finales del equipo.
