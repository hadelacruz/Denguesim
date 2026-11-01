## [2026-11-01] Tareas G1–G8 — módulo completo (SIG aplicado, integración y demo)

**Prompt usado:**
> Estoy armando el modelo de localización (MCLP) para ubicar los centros de acopio usando PuLP. El código ya está estructurado, pero al hacer `prob.solve()` me tira un error porque no encuentra ningún solver instalado, a pesar de que tengo PuLP 4.2.0. Además, necesito ponderar la demanda sin contar la población dos veces. ¿Me puedes decir qué versión de PuLP trae el solver CBC por defecto y sugerirme una métrica que no esté correlacionada al 0.98 con la población para usarla como peso de la demanda?

**Qué se esperaba:** isocronas, MCLP, ranking de riesgo, pipeline, resúmenes, demo en Streamlit, README y pruebas, siguiendo la sección del módulo en la guía.

**Resultado:** satisfactorio. El modelo de optimización MCLP ahora resuelve correctamente encontrando la ubicación óptima, la demo en Streamlit levanta sin problemas y las métricas de riesgo están consolidadas.

**Por qué creemos que pasó y qué se corrigió:** la integración de los datos espaciales y el dashboard fluyó bien tras sortear un par de obstáculos técnicos de librerías y lógica:
- PuLP 4.2.0 se instaló sin ningún solver disponible; se fijó `pulp==2.9.0`, que trae CBC por defecto, solucionando el fallo del MCLP.
- La densidad de `ca_mosquitos.csv` correlaciona 0.98 con la población; ponderar la demanda del MCLP con ella contaría la población dos veces. Se corrigió usando mosquitos por persona (el m_c del ABM).
- El ráster WorldPop no está en el repositorio: la población de las isocronas se repartió de forma uniforme dentro de cada municipio (aproximación permitida por la guía).
- Streamlit 1.66 marca `use_container_width` como obsoleto en los gráficos y los mapas base de CartoDB ahora piden una API key. Se actualizó el código usando `width="stretch"` y OpenStreetMap.

**Cómo contribuyó la IA:** identificó el problema de versiones con PuLP y su solver CBC, y sugirió dividir la densidad de mosquitos entre la población (m_c) para independizar el peso de la demanda de la cantidad bruta de habitantes.
