## [2026-10-30] Tarea A8 — Sensibilidad y gráfica de tornado (Dinámica de Sistemas)

**Prompt usado:**
> Ya terminé de correr las simulaciones variando los parámetros ±20 % y tengo los resultados en un DataFrame. Solo necesito ayuda con la visualización: ¿me pasas el código exacto de matplotlib para armar la gráfica de tornado? Necesito que las barras se ordenen automáticamente por el impacto absoluto en el pico y que el eje X esté centrado en el valor del caso base. Solo pasame el bloque de la gráfica, yo lo integro al script.

**Qué se esperaba:** `sensibilidad.csv` con los límites de cada parámetro evaluado y la figura de tornado con el impacto en el pico epidémico y el día del pico.

**Resultado:** satisfactorio. El pico es **sensible** a `a` (+61 % / −54 %) y a `μ` (+109 % / −51 %); los demás son robustos según el criterio del 50 %. El día del pico salta ~80–90 días porque la curva tiene dos jorobas.

**Por qué creemos que pasó y qué se corrigió:** la visualización requería alinear dos sets de barras (los incrementos y decrementos) restando el valor base para que el centro fuera el 0 del impacto relativo. Las gráficas muestran claramente que la mortalidad del vector y la tasa de picadura dominan la dinámica del pico.

**Cómo contribuyó la IA:** generó la sintaxis de matplotlib para el diagrama de tornado, incluyendo la lógica para ordenar los parámetros de mayor a menor sensibilidad absoluta.
