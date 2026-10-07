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

Solo agregan tablas, valores y restricciones; no tocan datos existentes. (La tabla es la de T-148; las migraciones posteriores están en "Despliegue", abajo.) Hasta que T-150 cree `evaluon/assessment/services/evaluate.py`, un pedido `evaluate_offers` falla con el motivo «sin manejador para el tipo de pedido».

## Modelos de la enmienda 2026-10-06 (T-159; ADR-0041 y ADR-0042)

### Archivos y huellas

Releídos en la API de Hugging Face (`/api/models/<repo>/tree/<revisión>`) el 2026-10-06 antes de fijarlos: tamaños, SHA-256 y revisiones coinciden con el ADR-0042 (no hubo que corregirlo). `scripts/fetch_models.sh` los baja a `models/` (fuera del repositorio) y verifica la huella contra `scripts/models.sha256`; es el único paso con internet.

| Archivo | Bytes | SHA-256 | Revisión | Lista |
|---|---|---|---|---|
| `mmproj-gemma-4-12b-it-qat-q4_0.gguf` | 175.115.616 | `cb018338…260da7` | `29d09777…786537` | normal (`scripts/fetch_models.sh`) |
| `gemma-4-26B_q4_0-it.gguf` | 14.439.363.584 | `3eca3b8f…eca51d` | `d1c082be…41935842e` | `--modelo-grande` |
| `gemma-4-26B-it-mmproj.gguf` | 1.194.828.160 | `a359953a…4dd3f3b` | `d1c082be…41935842e` | `--modelo-grande` |

`--modelo-grande` baja solo la lista aparte (los dos archivos del 26B-A4B), no repite la normal.

### Variables nuevas del motor de lotes

| Variable | Por omisión | Qué hace |
|---|---|---|
| `GENERATION_BATCH_MODEL_ALIAS` | la de `GENERATION_MODEL_ALIAS` | `--alias` de `generation_batch` y nombre que registran las evaluaciones, propuestas y fichas |
| `GENERATION_BATCH_MODEL_FILE` | la de `GENERATION_MODEL_FILE` | `--model` de `generation_batch` |
| `GENERATION_BATCH_MODEL_SHA256` | la de `GENERATION_MODEL_SHA256` | huella que se registra (P6) |
| `GENERATION_BATCH_MMPROJ_FILE` | `mmproj-gemma-4-12b-it-qat-q4_0.gguf` | `--mmproj` de `generation_batch` |
| `GENERATION_BATCH_MMPROJ_SHA256` | la del proyector del 12B | huella del proyector que se registra (P6; el ADR-0042 pide registrarla) |

`docker-compose.yml` las pasa a `app`, `migrate` y `worker`. Para la comparación, `docker-compose.modelo-grande.yml` (no se usa salvo ahí) sobrescribe `generation_batch` (modelo, alias y proyector del 26B-A4B; el resto de los argumentos igual) y las variables de `app` y `worker`: `docker compose -f docker-compose.yml -f docker-compose.modelo-grande.yml up -d --no-deps generation_batch worker app`. Volver al 12B: el mismo comando solo con el compose base.

### Prueba de humo (T-159, 2026-10-06)

Equipo: RTX 5090 Laptop, 24.463 MiB. Compilación `server-cuda-b11347`, contexto del lote 32.768, `--parallel 1`. Con `generation` (12B, 16.384), `embeddings` y `reranker` cargados todo el tiempo; sin ninguna medición en curso (comprobado con `docker top`). `generation_batch` se reemplazó con `docker compose -f docker-compose.yml [-f docker-compose.modelo-grande.yml] up -d --no-deps generation_batch`. La memoria se muestreó cada segundo con `nvidia-smi` desde el equipo. Pedidos por `curl` dentro del contenedor, con una imagen y un texto inventados (una "factura" dibujada con montos y datos inventados; 50 páginas de palabras sueltas de contrataciones, sin contenido real).

| | 12B + proyector | 26B-A4B + proyector |
|---|---|---|
| Carga de la compilación b11347 | carga el modelo y el proyector («loaded multimodal model») | carga el modelo y el proyector («loaded multimodal model»); sin errores ni avisos |
| Tiempo hasta sano (carga) | menos de 1 min | unos 3 min |
| Memoria de video, sin `generation_batch` (resto del entorno) | 10.425 MiB | 10.425 MiB |
| Memoria de video, con `generation_batch` en reposo | 18.609 MiB | 23.989 MiB |
| **Memoria máxima con pedidos de 20.000 tokens e imagen** | **18.653 MiB** | **24.087 MiB** |
| Pedido de unos 20.000 tokens de entrada, en frío | 7,1 s (lectura del prompt 6,6 s) | 6,2 a 6,6 s (lectura 4,3 a 5,2 s) |
| Pedido con una imagen (215 tokens de entrada, ~100 de salida) | 2,3 a 3,2 s | 0,8 s (la primera vez, 3,3 s) |
| Transcripción de la imagen | correcta | correcta |

Lectura de los números:

- **El 26B-A4B con `generation` cargado deja la memoria al límite: 24.087 MiB de 24.463 (376 libres), por encima del tope de 22.000 del ADR-0042 (punto 7 del umbral).** Lo que ocupa el 26B con proyector y contexto 32.768 es de unos 13.560 MiB sobre el resto del entorno, y el resto del entorno (con `generation` a 16.384) midió hoy 10.425 MiB, más que lo supuesto en la tabla del ADR (2.455 MiB «que no cambia» se había obtenido por diferencia con la medición de T-148). Sin pedidos fallidos en la prueba, pero sin margen para Windows ni para la pantalla. Opciones (decisión del Coordinador, antes de T-162): apagar `generation` durante la comparación (libera unos 8 GB; la 001 no se consulta en ese lapso), o bajar el contexto de las dos corridas a 24.576 con presupuesto de 14.000 (ADR-0037; con el 12B bajar el contexto ahorra solo unos 230 MiB, por lo que probablemente no alcance solo; el 26B no se midió con otro contexto).
- Con el 12B y visión, 18.653 MiB (5.800 libres): entra sin problema.
- La espera de 180 s por pedido (`GENERATION_BATCH_TIMEOUT_SECONDS`) alcanza con holgura: un pedido de 20.000 tokens tarda 7 s con cualquiera de los dos modelos; no se propone cambiarla.
- La velocidad de generación y de lectura del 26B-A4B es igual o mejor que la del 12B en estos pedidos, como esperaba el ADR-0042.
- Al terminar, `generation_batch` quedó con el 12B y el proyector del compose base (`n_ctx` 32.768), respondiendo.

## Despliegue (2026-10-07; `specs/004-evaluacion-asistida/runbook.md`)

Preparado para la aprobación del responsable (P11); nada se aplicó sobre la base real.

- **Migraciones de la 004 completas:** `audit.0007`, `tenders.0007`, `offers.0004_passage_origin_vision` (T-160), `assessment.0001` a `0004` (`0003_resultados_decisiones_literales` y `0004_triggers`, T-165). La tabla de T-148 de arriba solo traía las primeras.
- **Base real, leída el 2026-10-07:** tiene aplicadas todas menos `assessment.0003` y `0004`. El despliegue aplica esas dos, con respaldo previo (`backups/evaluon-AAAA-MM-DD-previo-004.dump`).
- **Entorno en marcha, leído el 2026-10-07:** `generation_batch` con `n_ctx` 32.768, alias del 12B y `vision: true`; `generation` con 16.384; memoria de video usada 17.530 de 24.463 MiB (con la visión cargada y sin carga de evaluación). El compose y `.env.example` ya traen todas las variables de esta feature (`GENERATION_BATCH_*`); no cambia ningún servicio, imagen ni red.
- **Modelos para el uso normal:** el 12B, su proyector (`mmproj-gemma-4-12b-it-qat-q4_0.gguf`), `bge-m3` y el reranker. Los archivos del 26B-A4B no se necesitan (ADR-0044).
- **Salida a internet:** sin cambios (solo `portal_worker`); `tests/portal/test_network.py` pasa.
- **Reversa:** la de `assessment.0003` solo es posible sin resultados nuevos (restricciones anteriores, tablas de solo inserción); si no, se restaura el respaldo (runbook, sección 9).
