# `casos_esperados.csv` — cómo usarlo (Dinámica de Sistemas, A11)

- **Columnas:** `escenario, corrida, cod_muni, dia, S, E, I, R, nuevos` (contrato).
- **Escenarios:** sin_intervencion, fumigacion_aleatoria, fumigacion_hubs, eliminacion_criaderos, linea_base_camas. `linea_base_camas` es idéntico a `sin_intervencion`
  (etiquetado aparte para el módulo de salud).
- **Corridas:** 30 por escenario (`corrida` = 0 … 29). La corrida k usa el mismo juego de
  parámetros en todos los escenarios (números aleatorios comunes): comparen escenarios **por corrida**.
- **Año base:** 2023. `dia` = 0 … 364 (día 0 = inicio de la semana epidemiológica 1).
- **S, E, I, R:** humanos susceptibles, expuestos, infecciosos y recuperados del municipio (personas).
  Ojo: el acoplamiento por movilidad mueve infecciosos entre municipios, así que S+E+I+R de un
  municipio puede diferir un poco de su población; el total del departamento sí se conserva.
- **`nuevos`:** casos humanos nuevos **VERDADEROS** por día (σh·Eh), **sin** factor de reporte.
  Para pasar a casos **notificados**, multipliquen por ρ = 0.2
  (`observacion.factor_reporte`; ρ no es identificable con los datos, ver `calibracion.json`).
  Para hospitalizaciones: notificados × `salud.fraccion_hospitalizada`.
- **Calibración:** βs, I0, ganancia del loop B y lluvia mínima ajustados al departamento (A6);
  multiplicador de mosquitos por municipio ajustado a `casos_anuales_muni.csv` 2023 (A10).
- **Limitación:** la forma semanal objetivo es un estimado (forma nacional escalada al total
  departamental); los totales anuales por municipio sí son observados.
