# Dinámica de Sistemas: resultados de las tareas N2 y N3

Generado el 2026-11-01 con `src/sd/calibracion_anual.py`, `src/sd/poblacion_abierta.py` y `src/sd/orden_llegada.py`.

## A6 (N2) · Calibración 2017–2025 (`calibracion_anual.csv`, `figuras/sd/calibracion_anual.png`)

En cada año se repite el ajuste final de A6: ρ = 0.2 fijo y se calibran βs, I0, la ganancia del loop B y la lluvia mínima. El objetivo es la forma nacional escalada al total departamental observado, que es un **estimado**.

| Año | βs | I0 | Ganancia | RMSE log | Notificados obs. → sim. | Semana pico obs. → sim. |
|---|---|---|---|---|---|---|
| 2017 | 1.07 | 118 | 10 (límite) | 0.72 | 550 → 739 | 41 → 30 |
| 2018 | 1.28 | 112 | 10 (límite) | 0.67 | 578 → 735 | 31 → 29 |
| 2019 | 1.06 | 451 | 0.91 | 0.69 | 6 002 → 5 857 | 33 → 47 |
| 2020 | 0.33 | 1 000 (límite) | 0.001 (límite) | 1.36 | 865 → 529 | 2 → 1 |
| 2021 | 0.73 | 45 | 10 (límite) | 0.77 | 192 → 275 | 32 → 40 |
| 2022 | 0.90 | 55 | 10 (límite) | 0.79 | 390 → 651 | 40 → 30 |
| 2023 | 0.94 | 743 | 0.28 | 0.47 | 14 704 → 14 924 | 38 → 36 |
| 2024 | 1.24 | 1 000 (límite) | 0.51 | 1.13 | 25 075 → 39 754 | 39 → 33 |
| 2025 | 1.36 | 445 | 2.45 | 0.86 | 3 107 → 3 995 | 20 → 31 |

**Conclusiones:**
- **βs es relativamente estable**: mediana 1.06 y CV entre años de 0.32. Si se quita 2020, queda entre 0.73 y 1.36. Es el parámetro más interpretable.
- **2023 da los mismos valores que A6**, lo que confirma que el procedimiento es reproducible.
- **Lluvia mínima queda en su límite superior (0.3) todos los años.** El modelo necesita más criaderos en la época seca de los que permite el rango documentado (0.05–0.3). Es una señal estructural: los casos de enero a abril no se explican solo con la lluvia. No se amplió el rango para no salirse del supuesto documentado.
- **En los años chicos** (2017, 2018, 2021 y 2022), la ganancia del loop B llega a su tope (10). Con un solo mecanismo de balance, el modelo solo puede mantener una epidemia pequeña con una fumigación muy fuerte. La realidad probablemente incluye inmunidad acumulada y cambios de serotipo, que el modelo no tiene.
- **2020 es un caso atípico.** Los casos se concentran en las primeras semanas y después caen, coincidiendo con el subregistro durante la pandemia de COVID-19. Esa explicación es una hipótesis: no está en los datos. El ajuste es malo (RMSE log de 1.36) y dos parámetros quedan en sus límites.
- **2024 no se ajusta bien**: el pico simulado es 3 veces el observado. La curva observada es ancha y plana, y el modelo, con todos susceptibles al inicio, solo produce un pico agudo.
- **Limitación común:** cada año empieza con todos susceptibles. La inmunidad de un año al siguiente se explora en A9.

## A9 (N3) · Población abierta y endemicidad (`poblacion_abierta.csv`, `poblacion_abierta_resumen.json`, `figuras/sd/poblacion_abierta.png`)

Se agregaron nacimientos y muertes con μh = 1/(73 · 365) por día, un supuesto del modelo (`sd.esperanza_vida_humana`). La población se conserva: el error es de 6·10⁻⁸ personas.

- **Ciclo medio de lluvia durante 50 años:** en la población **cerrada**, la fracción susceptible baja de 1.00 a 0.45 y los casos por temporada caen de 18 000 a 1 800, y siguen bajando: no es endémica. En la **abierta**, los nacimientos reponen susceptibles. S se estabiliza en ≈ 0.55 y los casos en ≈ 5 400 por año, con un cambio menor a 2 % entre años al final: **régimen endémico periódico** (S6).
- **Lluvia real 2017–2025 sin reiniciar el estado:** con los parámetros de 2023, el modelo da entre 12 000 y 20 000 notificados todos los años. Los observados van de 192 (2021) a 25 075 (2024), y la correlación es de −0.17. **La lluvia sola no explica la variación entre años.** Cerrada y abierta casi no se distinguen en 9 años, porque la renovación demográfica (1.4 % por año) es lenta frente a la escala de una temporada.
- **Lectura conjunta con la calibración anual:** la magnitud de cada año depende de factores que el modelo no tiene, como la inmunidad por serotipo, la introducción de serotipos nuevos y los cambios en la notificación. Por eso los escenarios (A11) se hacen sobre un solo año calibrado (2023) y se comparan **entre sí**. No deben leerse como pronósticos de otros años.

## A12 (N3) · Orden de llegada por área de salud (`orden_llegada.csv`, `orden_llegada_resumen.csv`, `figuras/sd/orden_llegada.png`)

- **Llegada:** primera semana de una racha de 3 semanas seguidas en zona de brote (`sd.semanas_brote_sostenido`, supuesto del modelo). Lo observado sale del corredor endémico del MSPAS. Para lo simulado se construyó un corredor con la misma regla: Q3 de los años simulados 2017–2025, dejando fuera el año evaluado.
- **Resultados (Spearman, p exacta por permutación):** 2019: ρ = −0.33 (p = 0.83); 2023: ρ = 0.63 (p = 0.50); 2026: ρ = 1.00 (p = 0.083). Con los tres años juntos (12 pares, permutando dentro de cada año): ρ = 0.44 (p = 0.20).
- **Con 4 áreas el resultado es débil por construcción.** Aun una correlación perfecta tiene p = 2/24 = 0.083 y no es significativa al 5 %. Además, en 2026 hay datos de corredor solo hasta la semana 34 y de clima hasta la 40, y el área CENTRAL queda censurada en ambos. No se puede afirmar que el modelo reproduzca el orden de llegada; tampoco se puede descartar.
- **Limitación:** las diferencias entre años simulados vienen solo de la lluvia y de la población, porque todos los años usan los mismos parámetros de 2023. Por eso el corredor simulado es angosto y las llegadas simuladas de 2019 son tardías (semanas 46 a 53).
