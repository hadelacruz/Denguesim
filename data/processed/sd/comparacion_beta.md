# Comparación de β (A13)

| Fuente | β (1/día) | β/γ | Qué representa |
|---|---|---|---|
| SD, A5: `β_eq = R0²·γ` | 0.797 | 3.98 | Temporada alta (m = 2.0), μ sin fumigación, βs calibrado = 0.942, todos susceptibles |
| SD, `β_eq(t)` en semanas 18–46 | 0.337 (rango 0.104–0.635) | 1.69 | Igual, pero con m(t) y μ(t) simulados (lluvia + loop B) |
| ABM, `beta_efectiva.json` | 0.227 (IC 95 % 0.195–0.257) | 1.13 | SEIR humano equivalente ajustado a las corridas de Amatitlán (semanas 18–46) |

**Umbral epidémico de la red (D4):** τ_c = 0.0667 (grafo completo, umbral 0) y
0.1109 (umbral 100 personas/día). Con β/γ del ABM = 1.13, la red supera el umbral en
ambos casos (True / True). La red del departamento es tan densa que cualquier
transmisibilidad realista invade: el umbral de red no es la restricción; lo que limita la transmisión
es la estacionalidad (mosquitos) y el control.

## Por qué difieren

1. **Escala espacial:** el ABM es local (Amatitlán, celdas de 500 m) y el SD es departamental de mezcla homogénea.
   En el ABM, los infecciosos solo infectan a los mosquitos de las celdas que visitan y se agotan
   localmente; por eso la β "media" es menor que la de mezcla homogénea.
2. **Qué incluye cada β:** el `β_eq` de A5 supone temporada alta, sin fumigación y todos susceptibles
   (un máximo teórico). `β_eq(t)` ya incluye la lluvia y el loop B, y se acerca más al ABM. La β del ABM es
   un ajuste estadístico (mínimos cuadrados entre el primer caso y el pico) que también absorbe el
   retardo humano → mosquito → humano.
3. **Supuestos distintos:** el ABM no tiene incubación extrínseca y usa la abundancia del autómata
   celular, calibrada con `escala_mosquitos`; el SD tiene incubación extrínseca (σv) y Λ(t) por lluvia
   con retardo de 3er orden, calibrado con βs y la ganancia del loop B.
4. **Lo que sí coincide:** ambos modelos están calibrados para producir la incidencia notificada observada
   de 2023 con ρ = 0.2, y los dos dan una transmisión efectiva **cerca del umbral** (β/γ del ABM ≈ 1.1),
   coherente con brotes de pocos por ciento de la población.
