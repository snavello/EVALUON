# Entorno 003 · Procedimiento, pliego final y matriz de cumplimiento

Insumo del despliegue de la feature 003 (plan 003, "Componentes"; ADR-0018, ADR-0024, ADR-0034). Complementa `specs/001-normativa/entorno.md` (equipo, GPU, modelos). La instalación y la operación están en `specs/003-pliego-matriz/runbook.md`. La verificación de humo de T-075 (`verificacion/T-075.md`) queda como antecedente: el runbook la completa con un recorrido repetible de punta a punta.

Fecha: 2026-10-05.

## Qué agrega la 003 a la infraestructura

Respecto de la 001: el servicio `generation_batch` (segunda instancia del motor, misma imagen y modelo, solo para los pedidos de la matriz y las mediciones) y el servicio `worker` (`manage.py procesar_pedidos`, de a un pedido). No hay imágenes, modelos ni variables nuevas. Todo está en `docker-compose.yml`.

## Servicios que usa

| Servicio | Para qué | Salida a internet |
|---|---|---|
| `db` | Postgres 17 con pgvector: procedimientos, documentos, lecturas, tramos, matrices, pedidos y registro de auditoría | No |
| `app` | Pantallas de procedimientos y matriz (`/procedimientos/...`) y comandos de `manage.py` (`medir_matriz`, `crear_usuario`) | No tiene cliente que salga (P4) |
| `worker` | Lee los documentos (texto del PDF, tramos) y corre la propuesta de la matriz, de a un pedido | No (solo red `internal`) |
| `generation_batch` | Gemma 4 12B (`gemma-4-12b-it-qat-q4_0`) para cada pasada de la propuesta | No |
| `embeddings`, `reranker` | `bge-m3` y `bge-reranker-v2-m3`: apoyo normativo de cada requisito | No |

`generation` (consulta de normativa) y `portal_worker` no participan del camino de pliegos. Ningún contenedor de ese camino está en la red `egress` (P4); lo comprueba `tests/portal/test_network.py`. En la prueba del 2026-10-05 la red interna del proyecto de prueba resultó `internal: true`.

## Variables de entorno

Ninguna propia de la 003. Cuentan las de `.env.example`, compartidas con la 001: `POSTGRES_*`, `DJANGO_SECRET_KEY`, `APP_PORT`, `GENERATION_CTX_SIZE` (16384) y `GENERATION_CACHE_RAM` (2048). Las URL de los motores (`GENERATION_BATCH_URL`, `EMBEDDINGS_URL`, `RERANKER_URL`) tienen valor por omisión en el compose. Los parámetros de la propuesta (largo de lotes, tope de citas, versiones de instrucciones) son constantes del código; cada corrida guarda con qué valores se hizo (`parametros.json`). `medir_matriz` se configura solo con opciones de línea de comandos.

## Migraciones de la 003

| App | Migración | Qué hace |
|---|---|---|
| `accounts` | `0002_commission_role` | Rol de la Comisión (operador, evaluador) |
| `audit` | `0003_tender_event_types`, `0004_user_role_changed` | Tipos de hecho de procedimientos, pliegos y matriz; cambio de rol |
| `tenders` | `0001_initial`, `0002_triggers` | Procedimientos, documentos, lecturas, tramos, pedidos, matrices, requisitos, citas, consecuencias; triggers de inmutabilidad |
| `tenders` | `0003_sugerencias_descartadas_proceso_unico`, `0004_circulares_original_y_cambios` | Sugerencias, filas descartadas, proceso único, circulares con texto original y cambios |

Las posteriores (`tenders.0005` y `audit.0005`: 008; `tenders.0006`, `audit.0006` y `portal`: 012) se aplican en el mismo `migrate`. Probado el 2026-10-05, en un proyecto aparte, partiendo de una base en el estado previo a la 003 (`norms`, `queries`, `accounts.0001`, `audit.0002`): `migrate` aplicó las 31 migraciones pendientes y `migrate --check` dio 0; la reversa (`offers zero`, `tenders zero`, `audit 0002`, `accounts 0001`) y un nuevo `migrate` funcionaron; la restauración del respaldo previo con `pg_restore` dejó la base en el estado anterior (11 migraciones pendientes otra vez). Ninguna migración borra datos existentes, pero deshacerlas borra las tablas con su contenido: se respalda antes.

## Requisitos del equipo

- Los de la 001: notebook MSI (Windows 11 Pro, Docker Desktop con WSL2), GPU NVIDIA de 24 GB con controlador compatible con CUDA 12.8 o más y `models/` con los tres GGUF (`scripts/fetch_models.sh`, único paso con internet).
- Memoria de video: con los cuatro modelos cargados, 18.099 MiB de 24.463 (T-075), margen de unos 6 GB. El contenedor `app` no tiene `nvidia-smi`: la cifra se anota desde el equipo (`nvidia-smi --query-gpu=memory.used,memory.total --format=csv`). Una fuente automática queda como mejora pendiente (observación 4 del dictamen).
- Memoria del equipo: el núcleo de WSL2 tiene 15,3 GiB; por eso `GENERATION_CACHE_RAM=2048` (T-090).
- Tiempos: lectura de un pliego, segundos; propuesta de la matriz, de menos de un minuto (pliego de dos páginas) a unos 3 minutos (caso-00, 6 renglones) y hasta 40 minutos (caso-01). La medición de un caso real usa la GPU de 30 a 75 minutos.
- Disco: cada documento guarda su PDF original; contar unos MB por pliego más los respaldos de `backups/` (ignorada por git).
- Los casos reales (pliegos, circulares, listas esperadas) quedan solo en el equipo, en `corpus/casos/` (ignorada por git); no se suben (P4).
