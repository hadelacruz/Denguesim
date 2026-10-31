## [2026-10-30] Tarea D2 — Centralidad y métricas de red (Redes)

**Prompt usado:**
> Hola, estoy terminando de armar el script para las redes gravitacionales y del censo, pero me trabé con un detalle de NetworkX. Al calcular la centralidad de intermediación, las aristas que tienen flujo cero me tiran error porque asume distancia infinita. ¿Me ayudas solo con la línea o función específica para ignorar esos pesos cero al sacar esa métrica?

**Qué se esperaba:** `centralidad.csv` (4 columnas, 17 filas), `metricas_red.csv`, centralidad del censo con Spearman y dos figuras.

**Resultado:** satisfactorio. `0101` (Guatemala) es el primero en fuerza (383 582 personas/día), seguido de Mixco y Villa Nueva. Spearman entre la red gravitacional y la del censo: 0.98 (grado), 0.96 (eigenvector), 0.58 (intermediación).

**Por qué creemos que pasó y qué se corrigió:** la intermediación coincide menos porque en el grafo completo casi todos los caminos más "cortos" (1/flujo) pasan por la capital, y la red del censo tiene pares sin arista. Para la intermediación se excluyen las aristas con flujo 0 (su distancia 1/0 sería infinita). El vector propio se reporta en valor absoluto porque su signo es arbitrario.

**Cómo contribuyó la IA:** sugirió cómo filtrar los pesos cero para el cálculo de intermediación en NetworkX y ayudó a generar el mapa de la red sobre los límites municipales.
