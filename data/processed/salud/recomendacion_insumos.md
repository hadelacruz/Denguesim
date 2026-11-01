# Recomendación de política de insumos (R8)

Datos: demanda de `linea_base_camas` (ocupación del DES, réplica 0), 21 hospitales, α y τ
centrales del YAML (α = 0.15, τ = 7.0 días).

| Política | α·τ | ζ_A | P(estable_B) | P(oscila_A) | Amplitud máx. de I − I* | Días de desabasto | Inventario en tránsito P* |
|---|---|---|---|---|---|---|---|
| base | 1.05 | 0.488 | 0.4844 | 0.9496 | 76.558 | 1048 | 110.619 |
| reducir_tau_20pct | 0.84 | 0.5455 | 0.5782 | 0.9308 | 73.421 | 989 | 88.495 |
| reducir_alpha_20pct | 0.84 | 0.5455 | 0.5782 | 0.9308 | 88.483 | 1257 | 110.619 |

**Estabilidad:** las dos reducciones dan el mismo α·τ = 0.84, así que P(estable_B) y
P(oscila_A) son iguales en ambas (0.5782 y 0.9308). Según estos criterios, ninguna de las dos es mejor.

**Otras métricas:** reducir τ deja 989.0 días de desabasto y una amplitud de 73.421;
reducir α deja 1257.0 días y una amplitud de 88.483 (base: 1048.0 días, amplitud de 76.558).
Reducir τ además baja el inventario en tránsito P* de 110.619 a 88.495
(capital inmovilizado en pedidos).

**Recomendación (según estos números):** `reducir_tau_20pct`. Con τ más corto, los pedidos llegan antes y el
inventario se recupera más rápido de los picos de demanda. Con α más bajo, en cambio, se
pide menos de la brecha cada día y el inventario tarda más en recuperarse. Limitación: el desabasto
depende sobre todo de I* = días de cobertura × demanda MEDIA anual, que se queda corto en
la temporada alta; subir la cobertura objetivo o hacerla estacional pesa más que α o τ.
