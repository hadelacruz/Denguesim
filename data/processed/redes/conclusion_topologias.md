# Conclusión: topología de la red de movilidad (D3)

Red no dirigida con umbral de 100 personas/día. Medias de 100 repeticiones por tipo.

| red_base | tipo | clustering | distancia_media | k_medio | k2_medio | heterogeneidad | sigma_mundo_pequeno |
|---|---|---|---|---|---|---|---|
| gravitacional | real | 0.856 | 1.588 | 6.588 | 66.000 | 1.521 | 2.128 |
| gravitacional | ER | 0.409 | 1.616 | 6.588 | 46.942 | 1.082 | 1.000 |
| gravitacional | BA | 0.426 | 1.791 | 4.941 | 30.460 | 1.248 | 0.941 |
| gravitacional | WS | 0.507 | 1.764 | 6.000 | 36.567 | 1.016 | 1.133 |
| censo | real | 0.786 | 1.640 | 5.765 | 46.235 | 1.391 | 2.280 |
| censo | ER | 0.359 | 1.708 | 5.765 | 36.666 | 1.103 | 0.999 |
| censo | BA | 0.426 | 1.791 | 4.941 | 30.460 | 1.248 | 1.133 |
| censo | WS | 0.507 | 1.764 | 6.000 | 36.567 | 1.016 | 1.365 |

- **gravitacional:** C = 0.86 contra 0.41 en ER; L = 1.59 contra 1.62; σ = 2.13 (> 1: rasgos de mundo pequeño). Heterogeneidad ⟨k²⟩/⟨k⟩² = 1.52 (ER 1.08, BA 1.25): pocos municipios (la capital, Mixco, Villa Nueva) concentran las conexiones.
- **censo:** C = 0.79 contra 0.36 en ER; L = 1.64 contra 1.71; σ = 2.28 (> 1: rasgos de mundo pequeño). Heterogeneidad ⟨k²⟩/⟨k⟩² = 1.39 (ER 1.10, BA 1.25): pocos municipios (la capital, Mixco, Villa Nueva) concentran las conexiones.

**Limitación (obligatoria):** con solo 17 nodos **no se puede afirmar que la red sea "libre de escala"**: no hay suficientes nodos para estimar la cola de la distribución de grado ni para distinguir una ley de potencia de otras distribuciones. Lo que sí se puede decir es que la red es más heterogénea que una ER con el mismo número de aristas y que tiene una estructura de hub (estrella alrededor de la capital), lo que baja el umbral epidémico (D4) y favorece las intervenciones dirigidas a los hubs (D5).
