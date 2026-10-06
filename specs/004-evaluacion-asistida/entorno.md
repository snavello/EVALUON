# Entorno 004 · Evaluación asistida de ofertas

Insumo del despliegue de la feature 004 (plan 004, "Componentes", "Qué se lee y cómo se agrupa" y "Tiempos y GPU"; ADR-0037). Complementa `specs/001-normativa/entorno.md` (equipo, GPU, modelos), `specs/008-ofertas-ficha/entorno.md` (ofertas) y `specs/012-portal-compras/entorno.md` (red).

Fecha: 2026-10-06 (T-148). Lo medido está al final; lo que cambia el despliegue, aquí abajo.

## Qué agrega la 004 a la infraestructura

Un solo cambio de entorno: **el motor de lotes (`generation_batch`) arranca con un contexto propio de 32.768 tokens** (ADR-0037). Ningún servicio, imagen ni modelo nuevo. `generation` (consulta de normativa) sigue en 16.384.

## Variable nueva

| Variable | Por omisión | Qué hace |
|---|---|---|
| `GENERATION_BATCH_CTX_SIZE` | `32768` | `--ctx-size` de `generation_batch`. `docker-compose.yml` la pasa también a `app`, `migrate` y `worker`, donde `settings.GENERATION_BATCH_CONTEXT_TOKENS` la lee y la registra con cada propuesta de la 003, cada ficha de la 008 y cada evaluación de la 004 (P6) |

`GENERATION_CTX_SIZE` (16384) no cambia y sigue siendo el contexto de `generation`, de las consultas de normativa y de los presupuestos de `consequences.py` y `circulars.py`. Los parámetros `ASSESSMENT_*` (`ASSESSMENT_GROUP_TOKENS = 20000`, `ASSESSMENT_MAX_GROUPS`, `ASSESSMENT_MAX_OUTPUT_TOKENS`, etc.) no son variables de entorno: son constantes de `evaluon/settings.py`, como las `OFFERS_*`; cada evaluación guarda los valores con que se hizo y cambiarlos exige volver a medir (P7).

Para **volver al contexto anterior** (ADR-0037, "Para revertir"): `GENERATION_BATCH_CTX_SIZE=16384` en `.env`, recrear `generation_batch` y bajar `ASSESSMENT_GROUP_TOKENS` a 8.000.

## Cómo comprobar el contexto y la memoria de video

- Contexto con que arrancó el servidor (el real, el que cuenta): `docker compose exec generation_batch curl -s localhost:8080/props` y buscar `"n_ctx":32768`. `generation` debe mostrar `16384`.
- Contexto que la aplicación registra: `GENERATION_BATCH_CONTEXT_TOKENS` en `evaluon/settings.py`; `tests/test_compose_env.py` comprueba que coincida con el `--ctx-size` del compose.
- Memoria de video: `nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits` en el equipo. `medir_tamanos` la informa con `tenders.evaluation.video_memory`; dentro del contenedor no hay `nvidia-smi`, así que se indica otro comando con `MEASURE_VIDEO_MEMORY_COMMAND` (debe escribir "usada, total").
- Aplicar el cambio sobre el entorno de uso: `docker compose up -d generation_batch worker app` recrea esos servicios con el contexto nuevo (lo hace el despliegue, no T-148).

## Lo medido (T-148, 2026-10-06)

Equipo: notebook con RTX 5090 Laptop, 24.463 MiB. Se midió en un proyecto de compose aparte (`t148`, con su base, su `embeddings` y su `generation_batch`), sin tocar los contenedores del entorno principal, que ocupaban 10.302 MiB con sus cuatro modelos (generation y generation_batch a 16.384, embeddings, reranker).

### Memoria de video

| Medida | MiB |
|---|---|
| Entorno principal (cuatro modelos, motor de lotes a 16.384) | 10.302 |
| `generation_batch` aparte con contexto 16.384, en reposo | +7.847 |
| `generation_batch` aparte con contexto 32.768, en reposo | +8.075 |
| Diferencia de subir el contexto a 32.768 | **+228** |
| Mismo motor a 32.768 respondiendo un pedido de 30.147 tokens (11,5 s), máximo observado | +14 sobre el reposo |
| **Entorno de uso con el motor de lotes a 32.768** (10.302 − 7.847 + 8.075) | **10.530 de 24.463 (libres 13.933)** |

El contexto de 32.768 entra con holgura: el caché de contexto de este modelo crece poco (228 MiB por duplicar el contexto), porque la mayor parte de lo que ocupa el motor son los pesos. **No hace falta la alternativa del ADR-0037** (24.576 con presupuesto de 14.000, o apagar `generation` durante la evaluación) y el ADR no cambia. El motor aceptó y respondió un pedido de 30.147 tokens de entrada con el contexto de 32.768.

### Tamaños de las ofertas del caso-00 (con el tokenizador de Gemma 4)

Cuentas por oferta, en el orden de las ofertas del procedimiento; los documentos de texto idéntico se cuentan una vez; el texto es el de la lectura, página por página, con el encabezado `--- página k ---` (así lo lee el modelo; ver `evaluon/assessment/sizing.py`). El detalle por documento y por página está fuera del repositorio, en `corpus/casos/caso-00/corridas-tamanos/`.

| Oferta | Documentos | Copias de texto idéntico | Páginas | Páginas sin leer | Tokens | Tokens con las copias | Documento mayor | Grupos con 20.000 |
|---|---|---|---|---|---|---|---|---|
| 1 | 11 | 0 | 16 | 1 | 9.494 | 9.494 | 4.512 | 1 (9.494) |
| 2 | 10 | 1 | 38 (45 con la copia) | 0 | 19.529 | 24.901 | 5.377 | 1 (19.529) |
| 3 | 5 | 0 | 9 | 0 | 8.819 | 8.819 | 4.489 | 1 (8.819) |

- Las tres entran en **un solo grupo** con `ASSESSMENT_GROUP_TOKENS = 20000`. La estimación del plan para la oferta grande (18.000 a 40.000 tokens, uno o dos grupos) resultó en el extremo bajo: con las copias deduplicadas, 19.529.
- **La oferta 2 queda a 471 tokens del presupuesto.** Con instrucciones, requisito, fundamentos y salida, el pedido llega a unos 22.000 tokens de 32.768. Con el contexto de 24.576 y 14.000 de presupuesto, esa oferta se habría partido en dos grupos: el contexto de 32.768 evita que la oferta más grande se lea en dos pasadas.
- Tokens por página: 593 (oferta 1), 514 (oferta 2) y 980 (oferta 3, escaneos fotografiados). La oferta de 9 páginas pesa más que la de 16: el rango del plan para la «oferta chica» (3.500 a 8.000) quedó corto; la «mediana» (6.000 a 14.000) está dentro.
- El caso-00 tiene además dos fotos del cuadro del Portal (en las ofertas 1 y 3) que el sistema carga como documentos; se cuentan aquí como uno más.

## Servicios que usa la 004 y salida a internet

`db`, `app`, `worker`, `generation_batch`, `embeddings` y `reranker`, como la 008. Ninguno sale a internet (P4); `tests/portal/test_network.py` sigue comprobando que solo `portal_worker` está en `egress`.

## Migraciones que trae T-148

| App | Migración | Qué hace |
|---|---|---|
| `assessment` | `0001_initial` | Crea las ocho tablas de la evaluación, con sus restricciones |
| `assessment` | `0002_triggers` | Triggers de solo inserción (UPDATE y DELETE rechazados) en las ocho |
| `tenders` | `0007_evaluacion` | `tenders_job`: tipo de pedido `evaluate_offers` |
| `audit` | `0007_evaluacion` | Restricción de tipos de hecho: `eval_request`, `eval_build`, `eval_decision`, `eval_answer` |

Solo agregan tablas, valores y restricciones; no tocan datos existentes. Hasta que T-150 cree `evaluon/assessment/services/evaluate.py`, un pedido `evaluate_offers` falla con el motivo «sin manejador para el tipo de pedido».
