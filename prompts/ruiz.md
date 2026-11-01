## [2026-11-01] Tareas R1–R12 — módulo completo (Salud + verificación)

**Prompt usado:**
> Estoy armando las pruebas unitarias para la política de insumos del hospital. Mi regla de pedidos actual es `dP/dt = α(I* − I) − P/τ`, pero la prueba de estabilidad me falla porque con demanda constante el inventario no se queda en `I*`, sino que se asienta en `I* − D̄/α`. ¿Me ayudas a ajustar la ecuación diferencial sumando la reposición de demanda esperada `D̄` para que el equilibrio quede exactamente en `I*` sin alterar la ecuación característica del sistema?

**Qué se esperaba:** generadores, DES de camas con ampliación, insumos, estabilidad (dos modelos), robustez, notificación, estancia Weibull, política de insumos, pruebas, contrato y CI, siguiendo la sección del módulo en la guía.

**Resultado:** satisfactorio. Los modelos lineal y de simulación están completos. Tras el ajuste algebraico, el inventario converge exactamente a I* y las pruebas del contrato pasan sin errores. 

**Por qué creemos que pasó y qué se corrigió:** se iteró sobre la estructura base corrigiendo lo siguiente:
- La regla de pedidos del plan, `dP/dt = α(I* − I) − P/τ`, fallaba la prueba "con D constante el inventario se queda en I*". Se agregó la reposición de la demanda esperada D̄ sugerida.
- El DES tardaba 4.5 min porque `parametro()` releía el YAML en cada llamada; se agregó una versión con caché en `src/salud/comun_salud.py` (bajó a ~20 s).
- Con 30 camas no hay saturación y la comparación de R5 daba Δ = 0; se agregó la misma comparación con la capacidad mínima del rango (10 camas), donde sí hay efecto.
- Dos pruebas estaban mal planteadas estadísticamente (la media dentro del IC por percentiles y P ≥ 0 en un modelo lineal que permite negativos); se reescribieron los asserts de las pruebas.
- Se ajustó la demanda: `fraccion_hospitalizada` está definida como hospitalizados / casos **notificados**, así que la fórmula pasó a ser ρ · nuevos · fracción.

**Cómo contribuyó la IA:** dedujo la modificación algebraica (`+ D̄/τ`) necesaria en la ecuación diferencial de pedidos para desplazar el punto de equilibrio de vuelta a I*, resolviendo el fallo de la prueba.
