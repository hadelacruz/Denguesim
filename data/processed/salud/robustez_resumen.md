# Robustez de las conclusiones (R9) — 100 juegos de parámetros

Cada juego se corrió en todos los escenarios con la misma semilla (números aleatorios comunes).
`prob_mejor` = fracción de juegos en que el escenario tiene el menor valor (menor es mejor).

| Métrica | Mejor escenario | prob_mejor | Media (IC 95 %) del mejor | Segundo | prob_mejor |
|---|---|---|---|---|---|
| pico_casos | eliminacion_criaderos | 0.89 | 285.10 (99.75–1086.77) | fumigacion_hubs | 0.10 |
| casos_totales | eliminacion_criaderos | 0.96 | 33047.82 (7634.69–130823.15) | fumigacion_hubs | 0.04 |
| dias_saturacion | fumigacion_hubs | 0.27 | 0.01 (0.00–0.00) | eliminacion_criaderos | 0.23 |
| espera_media_dias | fumigacion_hubs | 0.27 | 0.00 (0.00–0.00) | eliminacion_criaderos | 0.25 |
| dias_desabasto | sin_intervencion | 0.39 | 931.66 (294.68–2024.72) | ampliacion_camas | 0.36 |

**Lectura:** si `prob_mejor` del mejor escenario es cercana a 1, la conclusión NO cambia con la
incertidumbre de los parámetros. Si se reparte entre varios escenarios (o hay empates, típico de
`dias_saturacion` cuando casi nunca hay cola), la conclusión depende de los parámetros.

**Supuestos:** ρ ~ Uniforme(0.05, 0.5) porque no se calibró; camas por hospital ~ U(10, 60) porque
no hay dato; hospitalizaciones = ρ · nuevos · fraccion_hospitalizada (ver src/salud/comun_salud.py).
