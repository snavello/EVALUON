# Entorno 008 · Ofertas y ficha por oferta

Insumo del despliegue de la feature 008 (plan 008, "Componentes" y "Tiempos y GPU"; ADR-0025, ADR-0026, ADR-0028, ADR-0035). Complementa `specs/001-normativa/entorno.md` (equipo, GPU, modelos) y `specs/012-portal-compras/entorno.md` (red). La instalación y la operación están en `specs/008-ofertas-ficha/runbook.md`.

Fecha: 2026-10-05.

## Qué agrega la 008 a la infraestructura

Nada nuevo en `docker-compose.yml`: ni servicios, ni imágenes, ni variables, ni modelos. La 008 usa lo que ya hay.

## Servicios que usa

| Servicio | Para qué | Salida a internet |
|---|---|---|
| `db` | Postgres 17 con pgvector: ofertas, documentos, lecturas, pasajes (con vector), fichas, pedidos al modelo y registro de auditoría | No |
| `app` | Pantalla de ofertas y de la ficha (`/ofertas/...`) y comandos de `manage.py` | No tiene cliente que salga (P4) |
| `worker` | Lee los documentos de cada oferta (OCR, pasajes, vectores) y arma la ficha, de a un pedido | No (solo red `internal`) |
| `generation_batch` | Modelo de generación (Gemma 4 12B, `gemma-4-12b-it-qat-q4_0`) para cada fila de la ficha y para reescribir el requisito | No |
| `embeddings` | `bge-m3`: vectores de los pasajes y de la consulta | No |
| `reranker` | `bge-reranker-v2-m3`: reordena los candidatos de cada fila | No |
| OCR | Tesseract 5.5 con `spa.traineddata` (tessdata_best), dentro de la imagen de `app` y `worker`; corre en CPU. Las fotos dudosas pasan por una preparación de imagen (ADR-0028) | No |

`generation` (consulta de normativa) y `portal_worker` no participan. Ningún contenedor del camino de ofertas está en la red `egress` (P4); lo comprueba `tests/portal/test_network.py`.

## Variables de entorno

- **`OFFERS_*` no son variables de entorno.** Son constantes de `evaluon/settings.py` (largo de pasajes, cantidad de candidatos, `OFFERS_MIN_RERANK_SCORE = 0.35`, tope de tokens de salida, versiones de instrucciones). No están en `.env.example` ni en `docker-compose.yml` y no se cambian en el despliegue. Cada ficha guarda los valores con que se armó (`offers_sheet.parameters`); cambiarlos es un cambio de código y exige volver a medir (P7).
- **`MEASURE_*` no existen.** `medir_fichas` se configura solo con opciones de línea de comandos (`--caso-chico`, `--procedimiento`, `--esperada`, `--corridas`, `--commit`, `--verificar-esperada`).
- Las que sí cuentan ya están en `.env.example` y se comparten con la 001 y la 003: `POSTGRES_*`, `DJANGO_SECRET_KEY`, `APP_PORT`, `GENERATION_BATCH_URL`, `EMBEDDINGS_URL`, `RERANKER_URL`, `GENERATION_CTX_SIZE` (16384) y `GENERATION_CACHE_RAM`. La espera de cada pedido de la ficha es `GENERATION_BATCH_TIMEOUT_SECONDS` (180 s, constante).

## Migraciones que trae la 008

| App | Migración | Qué hace |
|---|---|---|
| `offers` | `0001_initial` | Crea ofertas, documentos, lecturas, páginas, pasajes, fichas, filas, fragmentos, pedidos al modelo e historial |
| `offers` | `0002_triggers` | Triggers de inmutabilidad (UPDATE y DELETE rechazados en lecturas, pasajes, pedidos al modelo e historial) |
| `offers` | `0003_docx_format` | Formato de documento Word |
| `tenders` | `0005_ofertas` | `tenders_job`: tipos de pedido de ofertas y `target_id` |
| `audit` | `0005_ofertas` | Restricción de tipos de hecho: `offer_register`, `offer_load`, `offer_read`, `sheet_request`, `sheet_build`, `sheet_change` |

Sobre una base al día de la 003 se aplican también `audit/0006_portal`, `tenders/0006_portal` y `portal/0001-0002` (feature 012). Ninguna migración borra datos existentes: solo agregan tablas, columnas y restricciones. Las reversas existen y se probaron el 2026-10-05 en un proyecto aparte: `migrate offers zero` (arrastra `portal`), `migrate tenders 0004`, `migrate audit 0004`; un `migrate` posterior vuelve a dejar todo aplicado. Deshacer `offers` borra las tablas de ofertas y fichas con todo lo cargado: se respalda antes (runbook, sección 2).

## Requisitos del equipo

- Los de la 001: notebook MSI (Windows 11 Pro, Docker Desktop con WSL2), GPU NVIDIA con 24 GB (RTX 5090 Laptop) con controlador compatible con CUDA 12.8 o más, y la carpeta `models/` con los tres GGUF verificados por huella (`scripts/fetch_models.sh`; es el único paso con internet).
- Memoria de video: sin cambio respecto de la 003 (no hay modelo nuevo); unos 7,8 GB por motor de generación, más embeddings y reranker.
- Memoria del equipo: el núcleo de WSL2 tiene 15,3 GiB; por eso `GENERATION_CACHE_RAM=2048` (T-090).
- Disco: cada oferta guarda sus PDF originales, las lecturas con huella y los pasajes con vector; contar decenas de MB por oferta, más los respaldos de `backups/`.
- Tiempos (plan, "Tiempos y GPU"): de 2 a 5 minutos de modelo por oferta (35 a 45 filas). El OCR corre en CPU y se mide por página. Armar fichas y medir usan la GPU: una sola corrida a la vez (ADR-0025).
- Probado el 2026-10-05 con `app` y `worker` unidos a la red de los motores de otro proyecto: sirve para probar sin duplicar la GPU (ver runbook, sección 8).
- Los casos reales (pliegos y ofertas) quedan solo en el equipo, en `corpus/casos/` (ignorada por git); no se suben (P4).
