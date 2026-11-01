# Prueba de instalación limpia (D15, N3)

**Fecha:** 2026-11-01 · **Sistema:** Ubuntu 24.04, Python 3.12.3.

## Procedimiento

1. Se copiaron a una carpeta nueva **solo** los archivos que van al repositorio (`git ls-files -co --exclude-standard`): rastreados y sin rastrear no ignorados, sin `.venv/` ni archivos ignorados. Se usó una copia y no `git clone` porque parte del trabajo aún no tenía commit. **Después de los commits, repetir con `git clone`.**
2. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` → 1 min 7 s, sin errores; Mesa quedó en **2.4.0**.
3. `pytest -q` → **72 pruebas pasan en 24.6 s**, incluidas las 7 del contrato de datos de Juan Diego. `pytest -q -m "not lento"`, lo mismo que corre la integración continua, también da 72.
4. `python src/integracion/pipeline.py --rapido` → las 8 etapas terminan sin error en unos 2.5 minutos, y el contrato se verifica: las 8 tablas de los módulos tienen sus columnas exactas.

| Etapa | Segundos |
|---|---|
| redes_base | 6.7 |
| sd_calibracion | 17.6 |
| abm | 60.1 |
| redes_intervenciones | 11.1 |
| sd_escenarios | 17.2 |
| salud | 25.5 |
| sig | 20.5 |
| resumenes | 1.3 |

## Qué no cubre `--rapido`

Con `--rapido` no se recalibra si la calibración ya existe y se omiten los análisis lentos de N2 y N3: `calibracion.py`, `calibracion_anual.py`, `metapoblacion.py`, `sensibilidad.py`, `validacion_municipios.py`, `poblacion_abierta.py`, `orden_llegada.py` y `experimento_scheduler.py`. Esos scripts se corrieron completos en el entorno de trabajo, con las mismas versiones de `requirements.txt`. La corrida completa, `python src/integracion/pipeline.py`, tarda bastante más: la calibración de SD ~4 min, la calibración anual ~7 min y las corridas del ABM varios minutos.
