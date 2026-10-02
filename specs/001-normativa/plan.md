# Plan 001 · Normativa consultable con cita

Estado: aprobado · Fecha: 2026-10-02 · Aprobó: responsable del proyecto

Spec: `specs/001-normativa/spec.md`

ADR en los que se apoya (los cuatro en estado propuesto): `docs/adr/0002-motor-ia-local-y-modelo.md`, `0003-recuperacion-embeddings-reranker.md`, `0004-lectura-y-particion-de-documentos.md`, `0005-aplicacion-web-y-acceso.md`.

## En pocas palabras

Se construye un sistema que corre entero en la notebook del proyecto, sin mandar nada a internet, y que hace tres cosas.

1. **Lee las normas y las separa en partes con nombre.** El responsable de normativa carga cada documento (PDF, PDF escaneado o página web guardada) escribiendo una orden en la terminal. El sistema lo parte en artículos, incisos, anexos y considerandos, y entrega un informe que dice qué reconoció, qué páginas no pudo leer y qué no supo ubicar. Hasta que una persona valida ese informe, la norma no se usa para responder.
2. **Busca y responde con la cita.** Cuando alguien pregunta, el sistema busca los artículos que tratan el tema por tres caminos (por significado, por palabras y por número de artículo), les pone un puntaje de pertinencia y le pasa los mejores a un modelo de lenguaje que redacta la respuesta. El modelo no copia el texto de la norma: solo señala qué artículo sostiene cada afirmación, y el sistema pone el texto tal como está guardado. Así la cita no puede salir distinta del documento.
3. **Dice "no determinado" cuando no hay sustento.** Si nada de lo cargado trata la pregunta, o el modelo no encuentra base suficiente, el resultado es "no determinado", con un aviso propio y sin citas.

**Qué va a ver la Comisión.** Una sola pantalla, a la que se entra con usuario y clave. Tiene un cuadro para escribir la pregunta y, en la misma pantalla, la opción de buscar un artículo por su número o por palabras. La respuesta es una lista corta de afirmaciones; debajo de cada una figuran la norma y el artículo que la respaldan, con el texto literal y un enlace para abrir el documento original. Cada cita dice qué peso tiene: el régimen específico va primero y es el que se aplica; el marco nacional figura como marco; los dictámenes y las recomendaciones, como criterio que acompaña; los considerandos, al final y como contexto. Si el régimen específico y el marco nacional tratan un punto de manera distinta, se muestran los dos textos con un aviso de cuál se aplica. Un artículo modificado se muestra junto con el texto de la norma que lo modificó; uno derogado aparece en la búsqueda marcado como derogado y no sostiene respuestas.

**Con qué piezas.** Todo se levanta con una sola orden: la base de datos, la aplicación que muestra la pantalla y tres copias de un mismo programa de inteligencia artificial, una por tarea (redactar, buscar por significado y puntuar la pertinencia). Las tres usan la placa de video de la notebook; según las estimaciones ocupan alrededor de la mitad de su memoria.

**Qué queda registrado.** Cada carga, validación, consulta, búsqueda e ingreso, con quién lo hizo, cuándo, sobre qué versión de la normativa, qué se encontró y qué se respondió. Con ese registro se puede explicar después por qué el sistema dijo lo que dijo.

**Cómo se sabe si responde bien.** Con unas 30 preguntas de respuesta conocida, aprobadas por un integrante de la Comisión. Se exige: cita literal siempre, respuesta correcta en al menos 85 % de las preguntas que tienen respuesta, "no determinado" en al menos 90 % de las que no la tienen, y hasta 30 segundos por consulta.

**Qué falta comprobar.** Nada de esto se probó todavía en la notebook. Por eso la primera etapa no construye: comprueba que cada pieza funciona en este equipo y mide cuánta memoria usa. Para lo que podría fallar hay un plan B anotado. Los archivos de las normas todavía no están en el repositorio y hacen falta desde el principio.

## Resumen del enfoque

Una aplicación Django con páginas armadas en el servidor (ADR-0005) sobre el Postgres con pgvector que ya existe. La carga lee cada documento con herramientas que transcriben y recortan sin redactar (pdfplumber, Tesseract, BeautifulSoup) y lo parte con reglas deterministas (ADR-0004); cada unidad es un recorte exacto del texto leído. La consulta combina tres caminos de búsqueda sobre Postgres, reordena con un reranker y arma la respuesta con un modelo local que solo señala unidades (ADR-0002 y ADR-0003); el texto de cada cita lo inserta el sistema desde la base. Generación, embeddings y reranker se sirven con la misma imagen de `llama-server`, un contenedor por modelo, de modo que el camino de los documentos no tiene ninguna salida del equipo (P4) y hay una sola tecnología de IA que fijar, probar y mudar (P5, P10). Lo que hoy es estimación se mide en una primera etapa de comprobación del entorno, antes de construir encima.

## Componentes

| Componente | Nuevo | Qué hace | Con quién habla |
|---|---|---|---|
| Aplicación (`app`) | Sí | Pantalla de consulta, ingreso, comandos, lectura y partición de documentos, búsqueda, validación de la respuesta, registro | `db` por SQL; `generation`, `embeddings` y `reranker` por HTTP dentro de la red de Docker |
| Base (`db`) | Existe | Datos, archivos originales, texto para búsqueda por palabras, vectores, sesiones, registro de auditoría | Solo la aplicación |
| Motor de generación (`generation`) | Sí | Redacta la respuesta en formato fijo | Solo la aplicación |
| Embeddings (`embeddings`) | Sí | Convierte textos en vectores | Solo la aplicación |
| Reranker (`reranker`) | Sí | Puntúa cada candidato contra la pregunta | Solo la aplicación |
| Migraciones (`migrate`) | Sí | Prepara el esquema en una base vacía; en una base con datos solo comprueba | `db` |

Reglas de comunicación:

- La aplicación es la única que habla con los demás. Los tres servicios de IA y la base están en una red interna de Docker sin salida a internet y sin puertos publicados. La aplicación publica su puerto solo en `127.0.0.1`.
- Las funciones de negocio (`services`) reciben al usuario que actúa, comprueban su rol y dejan el registro. La pantalla y los comandos solo traducen y llaman (ADR-0005). No hay otra forma de ejecutar una operación.
- Los clientes de `evaluon/ai/` ofrecen tres operaciones: generar con esquema, convertir textos en vectores, y puntuar una pregunta contra una lista de textos. El resto del código no sabe qué servidor hay detrás. Las pruebas los reemplazan por dobles; las evals usan los servicios reales.
- Todo camino de búsqueda lee de `consultable_units` (ver "Modelo de datos"). Nada consulta las tablas de unidades por fuera.

El acceso por red es la feature 007. Este plan no la construye y no la impide: la aplicación escucha dentro del contenedor y la restricción a `127.0.0.1` está solo en la publicación del puerto; las cookies seguras se activan por configuración.

## Estructura del código

```
evaluon/                          raíz del repositorio (existe)
├── docker-compose.yml            los seis servicios
├── Dockerfile                    imagen de la aplicación (Python 3.12, Tesseract y su modelo de español)
├── .env.example                  todas las variables, sin valores reales
├── pyproject.toml                dependencias con versión fija; configuración de pytest
├── manage.py                     entrada de los comandos
├── scripts/
│   ├── fetch_models.sh           descarga los tres modelos y verifica su huella; único paso que usa internet
│   ├── models.sha256             huellas esperadas de los tres archivos
│   └── migrate_on_start.sh       lo que ejecuta el servicio `migrate`
├── evaluon/
│   ├── settings.py  urls.py  wsgi.py      configuración compartida; parámetros de búsqueda y generación
│   ├── accounts/                 usuarios, roles, ingreso y salida (REQ-016)
│   │   ├── models.py  permissions.py  views.py  urls.py  migrations/
│   │   └── management/commands/  crear_usuario
│   ├── audit/                    registro de auditoría (REQ-012, P6)
│   │   ├── models.py  services.py  migrations/
│   ├── norms/                    normas, documentos, lecturas, unidades, pasajes, relaciones, versiones
│   │   ├── models.py  migrations/         tablas y SQL propio (extensiones, configuración de texto, `consultable_units`)
│   │   ├── reading/              un archivo por formato: pdf_text.py, ocr.py, web.py (ADR-0004)
│   │   ├── splitting/            texto canónico, reglas de partición, informe de lectura (ADR-0004)
│   │   ├── indexing.py           pasajes y vectores de una lectura
│   │   ├── services/             un archivo por operación: loading.py, validation.py, relations.py, versions.py, listing.py
│   │   ├── views.py  urls.py     entrega del documento original (REQ-002)
│   │   └── management/commands/  cargar_norma, releer_norma, listar_normas, ver_informe, validar_informe, registrar_relacion, registrar_version
│   ├── queries/                  consulta con cita y búsqueda directa
│   │   ├── models.py  migrations/         registro detallado de cada consulta
│   │   ├── retrieval.py          tres caminos, unión, reranker, selección (ADR-0003)
│   │   ├── answering.py          pedido al modelo, validación, inserción de citas (ADR-0002)
│   │   ├── prompts/              instrucciones versionadas (un archivo por versión)
│   │   ├── search.py             búsqueda por norma y artículo, y por palabras (REQ-010)
│   │   ├── services.py           una consulta o una búsqueda de punta a punta, con su registro
│   │   ├── evaluation.py         corrida del conjunto de preguntas y cálculo de medidas (P7)
│   │   ├── views.py  urls.py  forms.py
│   │   └── management/commands/  correr_evals
│   ├── ai/                       clientes HTTP: generation.py, embeddings.py, reranker.py
│   ├── templates/                base, ingreso, consulta
│   └── static/                   una hoja de estilos y un script propios; nada externo
├── tests/
│   ├── conftest.py               usuarios de prueba; dobles de los tres clientes de IA
│   ├── accounts/  audit/  norms/  queries/
│   └── fixtures/                 documentos públicos chicos o sintéticos
├── evals/
│   ├── casos/                    un archivo por pregunta (EV-NNN.yaml)
│   └── corridas/                 una carpeta por corrida
├── corpus/normativa/             documentos públicos de trabajo (hoy vacío)
├── models/                       archivos de los modelos; fuera del repositorio (`.gitignore`)
├── backups/                      respaldos de la base; fuera del repositorio
└── specs/  docs/  tools/         (existen)
```

`norms/services/` es una carpeta y no un archivo único para que dos desarrolladores puedan trabajar a la vez en carga y en relaciones sin tocar el mismo archivo.

## Servicios

Seis servicios de Docker Compose. Los nombres van en inglés, como el resto de los identificadores.

| Servicio | Imagen | Qué hace | Memoria de video |
|---|---|---|---|
| `db` | `pgvector/pgvector`, Postgres 17, etiqueta exacta a fijar en la etapa 0 | Base `evaluon` | No usa |
| `generation` | `ghcr.io/ggml-org/llama.cpp:server-cuda-b<compilación>`, compilación a fijar en la etapa 0 | Sirve Gemma 4 12B (archivo de 4 bits de Google), contexto de 16.384 tokens, pensamiento apagado. `/v1/chat/completions` | Tope 16 GB. Estimado: hasta 8,6 GB (medición publicada con contexto de 32.000 en una RTX 5090 de escritorio; con 16.384 no está medido) |
| `embeddings` | La misma imagen y compilación | Sirve `bge-m3` (archivo GGUF FP16 de 1,16 GB). `/v1/embeddings` | Tope conjunto con `reranker`: 4 GB. Estimado: entre 1,2 y 2 GB |
| `reranker` | La misma imagen y compilación | Sirve `bge-reranker-v2-m3` (archivo GGUF FP16 de 1,16 GB). `/v1/rerank` | Estimado: entre 1,2 y 2 GB |
| `migrate` | Imagen propia de la aplicación | Corre `scripts/migrate_on_start.sh` y termina | No usa |
| `app` | Imagen propia de la aplicación | Pantalla (Gunicorn, un proceso con hilos, espera de 120 s) y comandos. Lectura de documentos y Tesseract en CPU | No usa |

**Cuenta de memoria de video.** Topes: 16 + 4 = 20 GB de 24, con 4 GB de margen. Con las estimaciones: 8,6 + 2 + 2 = 12,6 GB, con unos 11 GB libres. Ninguna de estas cifras está medida en este equipo, y no se sabe cuánta memoria de video usa Windows con la pantalla activa. La etapa 0 mide el total con los tres modelos cargados; si supera 20 GB, no se avanza sin revisar el reparto. `llama-server` no tiene un tope de memoria que se pueda imponer: los topes son un presupuesto que se controla midiendo.

Detalles comunes:

- Los tres servicios de IA montan `models/` en modo de solo lectura y arrancan con `--offline`. Cada uno expone `/health`; `app` espera a que los tres y `db` estén listos.
- `scripts/fetch_models.sh` descarga los tres archivos y compara su huella SHA-256 con `scripts/models.sha256`. Es el único paso que necesita internet y se hace una vez por equipo; para mudar el sistema también se puede copiar la carpeta `models/`.
- La imagen de la aplicación no lleva PyTorch ni usa la GPU. `app` monta `corpus/` en modo de solo lectura, para cargar documentos desde ahí, y `evals/`, para leer los casos y guardar las corridas.
- No hay servidor web intermedio, cola de tareas ni caché (P10).

**Plan B para embeddings y reranker.** Si la etapa 0 muestra que `bge-m3` o `bge-reranker-v2-m3` no cargan en `llama-server` o no reproducen los valores publicados por sus autores, los servicios `embeddings` y `reranker` pasan a usar Text Embeddings Inference (imagen `120-1.9` para la serie RTX 50, que su documentación marca como experimental). Los nombres de los servicios y el resto del sistema no cambian: solo la imagen y los dos clientes de `evaluon/ai/`. Si tampoco funcionara, queda el contenedor propio con `sentence-transformers` que describe el ADR-0003.

**Migraciones y respaldo.** El servicio `migrate` aplica las migraciones solo cuando la base está vacía; ahí no hay nada que respaldar y un equipo limpio llega al sistema funcionando con una orden (P5). Si la base ya tiene datos, `migrate` solo comprueba (`manage.py migrate --check`): si hay cambios de esquema pendientes termina con error, muestra el procedimiento y `app` no arranca. El procedimiento para una base con datos, que va al runbook, es:

1. Detener `app`.
2. Respaldar: `docker compose exec db pg_dump -Fc evaluon`, guardado en `backups/` con fecha.
3. Aplicar: `docker compose run --rm app python manage.py migrate`.
4. Levantar todo otra vez.

Así nunca se migra una base con datos sin respaldo previo. Cada migración con SQL propio lleva su reversa.

## Modelo de datos

Los nombres de tablas y campos van en inglés. Los valores que nombran un concepto jurídico (tipos de unidad, categorías, tipos de relación) van en español sin tildes, tal como los definió el ADR-0004; los estados propios del sistema van en inglés.

Cuatro niveles: una **norma** tiene uno o más **documentos** (cada archivo cargado), cada documento tiene una o más **lecturas** (cada vez que se leyó y partió), y cada lectura tiene sus **unidades**. Las unidades y las lecturas no se modifican ni se borran: una relectura crea una lectura nueva. Por eso un registro de consulta puede apuntar a una unidad y encontrarla siempre igual (P6, P8).

### accounts

**`accounts_user`** (modelo de usuario propio de Django)

| Campo | Contenido |
|---|---|
| `id`, `username` | Identificación; `username` único |
| `password` | Clave guardada con Argon2id; nunca legible |
| `role` | `read` o `read_write` |
| `is_active`, `date_joined`, `last_login` | Propios de Django |

**`django_session`**: sesiones en la base, tabla propia de Django.

### audit

**`audit_event`**: una fila por hecho registrado. Solo se insertan filas.

| Campo | Contenido |
|---|---|
| `id`, `occurred_at` | Identificación y momento |
| `event_type` | `load`, `reread`, `validation`, `relation`, `version`, `query`, `search`, `login`, `login_failed`, `rejected`, `user_created` |
| `outcome` | `ok`, `rejected` o `failed` |
| `channel` | `screen`, `command` o `eval` |
| `user` | Usuario que actuó; vacío en un ingreso fallido o en un alta hecha por quien administra el equipo |
| `username` | Nombre tal como se escribió; sirve cuando no hay usuario |
| `corpus_version` | Número de versión de la normativa vigente en ese momento |
| `detail` | Datos propios del hecho, en JSON (ver "Registro de auditoría") |

### norms

**`norms_norm`**: una fila por norma (REQ-001, REQ-017).

| Campo | Contenido |
|---|---|
| `id` | Identificación |
| `category` | `regimen_especifico`, `otra_normativa`, `marco_nacional`, `dictamen_legal` o `recomendacion_auditoria`. Obligatorio |
| `norm_type`, `number`, `year`, `issuer` | Tipo, número, año y organismo emisor, normalizados. Únicos en conjunto: es lo que identifica "la misma norma" (REQ-011) |
| `title` | Título |
| `created_at`, `created_by` | Alta |

**`norms_document`**: una fila por archivo cargado.

| Campo | Contenido |
|---|---|
| `id`, `norm` | Identificación y norma a la que pertenece |
| `publication_date`, `effective_from`, `source` | Fecha de publicación, fecha de vigencia y fuente de donde se obtuvo (REQ-001) |
| `effective_to` | Hasta cuándo rigió este texto; vacío mientras rige. Se completa cuando se registra una versión posterior de la misma norma |
| `version_number` | Número de versión dentro de la norma; vacío hasta que el documento se registra como versión |
| `in_use` | Si es el documento que se usa para consultar esa versión. A lo sumo uno por norma y versión |
| `same_norm_confirmation` | Qué confirmó la persona cuando el sistema avisó "misma norma": `other_file` o `new_version`; vacío si fue la primera carga |
| `file_name`, `file_format`, `file_size` | Nombre, formato detectado por contenido (`pdf` o `html`) y tamaño |
| `file_sha256` | Huella del archivo original. Única: es la comprobación de "mismo archivo" (REQ-011) |
| `loaded_at`, `loaded_by` | Carga |

**`norms_document_file`**: el archivo original (REQ-002).

| Campo | Contenido |
|---|---|
| `document` | Documento (clave primaria) |
| `content` | El archivo, byte por byte (`bytea`) |

Va en tabla aparte para que listar documentos no arrastre los archivos.

**`norms_reading`**: una fila por lectura de un documento.

| Campo | Contenido |
|---|---|
| `id`, `document`, `sequence` | Identificación, documento y número de lectura dentro del documento |
| `status` | `pending` (leída, sin validar), `validated`, o `superseded` (estuvo validada y otra lectura del mismo documento la reemplazó) |
| `pages` | La lectura: páginas y líneas con su texto, posición, origen y confianza (JSON) |
| `canonical_text`, `canonical_sha256` | Texto canónico del documento y su huella |
| `tool_versions` | Versiones de las herramientas, huella del modelo de español de Tesseract y versión de las reglas de partición (JSON) |
| `report`, `report_text` | Informe de lectura: datos (JSON) y texto legible (REQ-004) |
| `created_at`, `created_by` | Cuándo y quién leyó |
| `validated_at`, `validated_by`, `superseded_at` | Validación (REQ-005) y reemplazo |

**`norms_unit`**: una fila por unidad citable (REQ-003). No se modifica.

| Campo | Contenido |
|---|---|
| `id` | Identificación interna. Es lo que guarda el registro de consultas |
| `reading` | Lectura a la que pertenece |
| `parent` | Unidad que la contiene; vacío si cuelga de la norma |
| `unit_type` | `articulo`, `inciso`, `anexo`, `considerando`, `punto` o `parrafo` |
| `number` | Número normalizado: `14`, `14 bis`, `b`, `I`. Por orden, si el documento no trae número |
| `label` | Etiqueta como figura en el documento: "ARTICULO 14.- GARANTIAS" |
| `key` | Clave estable, única dentro de la lectura (ver "Identificación de unidades") |
| `path` | Ruta legible: "Anexo I › Título II › Capítulo I › Artículo 14 › Inciso 1" |
| `order` | Posición en el documento, creciente |
| `page_start`, `page_end` | Páginas; vacío en páginas web |
| `char_start`, `char_end` | Posición del recorte dentro de `canonical_text` |
| `text` | Texto literal: igual a `canonical_text[char_start:char_end]` |
| `text_origin` | `pdf_text`, `ocr` o `web` (REQ-015) |
| `ocr_confidence_min`, `ocr_confidence_avg` | Confianza mínima y promedio; vacío si no es `ocr` |

**`norms_passage`**: pasajes de búsqueda. Solo sirven para buscar; nunca se muestran ni se citan.

| Campo | Contenido |
|---|---|
| `id`, `unit`, `order` | Identificación, unidad base a la que pertenece y orden dentro de ella |
| `char_start`, `char_end` | Tramo del texto de la unidad que cubre |
| `header` | Encabezado de contexto: norma y ruta ("Disposición AFIP 297/03, Anexo I, artículo 14") |
| `text` | Texto del tramo |
| `tsv` | Columna para la búsqueda por palabras, con la configuración `spanish_unaccent`; índice GIN |
| `embedding` | Vector de 1024 dimensiones de `header` más `text`; sin índice aproximado |
| `embedding_model`, `embedding_revision` | Nombre del modelo y huella del archivo que calculó el vector |

**`norms_relation`**: relaciones entre normas y, cuando corresponde, entre unidades (REQ-006).

| Campo | Contenido |
|---|---|
| `id` | Identificación |
| `relation_type` | `modifica`, `complementa`, `reglamenta` o `deroga` |
| `source_norm` | La norma que modifica, complementa, reglamenta o deroga |
| `target_norm` | La norma alcanzada |
| `source_unit_key` | Clave de la unidad de la norma de origen que contiene el cambio; vacío si la relación es entre normas enteras |
| `target_unit_key` | Clave de la unidad alcanzada; vacío si alcanza a la norma entera |
| `effective_date` | Desde cuándo rige el cambio |
| `registered_at`, `registered_by` | Quién la registró y cuándo |

Las relaciones guardan la clave de la unidad y no su identificación interna, porque valen para la norma y no para una lectura en particular: si el documento se vuelve a leer, siguen apuntando al mismo artículo. Al registrar una relación se comprueba que la clave exista; al validar una lectura nueva, el informe avisa si alguna relación quedó sin unidad.

**`norms_corpus_version`**: versión de la normativa (REQ-012, P8).

| Campo | Contenido |
|---|---|
| `id` | Número de versión, creciente |
| `created_at`, `event` | Momento y hecho que la originó (`audit_event`) |

Se crea una versión nueva cada vez que cambia lo que se puede consultar: al validar una lectura, al registrar una relación y al registrar una versión de una norma. Cada consulta guarda el número vigente. Como las unidades no cambian y cada cambio tiene fecha, con el número de versión y la fecha de referencia se reconstruye qué era consultable.

### queries

**`queries_query`**: detalle de cada consulta en lenguaje natural. Se inserta una vez, al terminar.

| Campo | Contenido |
|---|---|
| `id`, `event` | Identificación y fila correspondiente en `audit_event` |
| `user`, `asked_at` | Quién y cuándo |
| `question`, `reference_date`, `corpus_version` | Pregunta, fecha de referencia y versión de la normativa |
| `status`, `reason` | Resultado: `grounded`, `undetermined` o `error`, y su motivo |
| `parameters` | Copia de todos los parámetros usados (JSON) |
| `candidates` | Cada candidato con su camino de entrada y su puntaje (JSON) |
| `selected` | Unidades enviadas al modelo, agregadas por relación y dejadas afuera por espacio (JSON) |
| `max_score` | Puntaje más alto del reranker |
| `prompt_version`, `request` | Versión de las instrucciones y pedido completo enviado al motor |
| `raw_output` | Lo que devolvió el modelo, sin tocar |
| `result` | Respuesta validada: afirmaciones, unidades citadas por `id`, marcas (JSON) |
| `anomalies` | Fallas de formato o de cita detectadas al validar (JSON) |
| `timings` | Tiempo de cada etapa y total (JSON) |

### Migraciones con SQL propio

En `norms/migrations/`, cada una con su reversa: extensiones `vector` y `unaccent`; configuración de búsqueda de texto `spanish_unaccent` (derivada de `spanish`, quitando acentos antes de reducir las palabras a su raíz); columna `tsv` con su índice GIN; y las funciones `consultable_units` y `unit_changes`.

### Identificación de unidades

"Artículo 1" no es único dentro de un documento: la Disposición 297/03 tiene uno en el cuerpo y otro en el Anexo I. Cada unidad tiene tres identificadores, con usos distintos.

| Identificador | Ejemplo | Para qué se usa |
|---|---|---|
| `id` | 4812 | Registro de consultas y respuesta guardada. No cambia nunca |
| `key` | `art-1`, `anexo-i/art-1`, `anexo-i/art-14/inc-1/inc-a`, `considerando-3`, `punto-2.3`, `parrafo-12` | Relaciones, comandos y conjunto de preguntas. Se arma con la cadena de unidades que la contienen, en minúsculas y sin tildes. Los títulos y capítulos no entran, porque no son unidades |
| `path` | "Anexo I › Título II › Capítulo I › Artículo 14 › Inciso 1" | Lo que se muestra en la cita y en la búsqueda, precedido por el nombre de la norma. Incluye títulos y capítulos |

La búsqueda por norma y número de artículo (REQ-010) devuelve todas las unidades de tipo `articulo` con ese número en el documento en uso de la norma, cada una con su `path`. Para "Disposición 297/03, artículo 1" son dos resultados, y la ruta dice cuál es cuál. No se elige uno en silencio.

### Unidades base, incisos y pasajes

El ADR-0004 guarda el artículo con el texto completo de sus incisos y además cada inciso como unidad hija. Para que el mismo texto no aparezca dos veces:

- **Unidad base** es toda unidad que no es `inciso`: `articulo`, `considerando`, `punto`, `parrafo` y `anexo`. Un `anexo` que contiene artículos tiene como texto propio solo su encabezado y lo que haya antes del primer artículo; un anexo sin artículos tiene todo su texto.
- **Se indexa para buscar** solo el texto de las unidades base, partido en pasajes. Una unidad corta es un único pasaje; una larga se parte en pasajes de hasta 800 tokens con solape (valor inicial), cortando en los límites de inciso cuando los hay. Los incisos no generan pasajes.
- **Se cita en una respuesta** siempre la unidad base. El modelo recibe unidades base y solo puede señalar unidades base. Una misma unidad base entra una sola vez en una consulta.
- **Los incisos sirven** para registrar relaciones con precisión ("modifica el inciso b del artículo 14") y para la búsqueda directa cuando se pide un inciso. Si una relación alcanza a un inciso, lo que acompaña en la respuesta es el artículo que lo contiene, con la aclaración de qué inciso cambió.
- El control de cobertura del informe de lectura cuenta cada carácter una vez, en su unidad base.

### Unidades consultables a una fecha

`consultable_units(fecha)` es una función SQL: el único lugar por el que pasan la consulta y la búsqueda. Devuelve las unidades que cumplen todo esto:

1. Su lectura está en estado `validated` (REQ-005).
2. Su documento está `in_use` y la fecha cae dentro de su vigencia: `effective_from` ≤ fecha, y `effective_to` vacío o posterior.

Para cada unidad devuelve además `repealed`: verdadero si a esa fecha hay una relación `deroga` que alcanza a la norma entera, a la unidad o a una unidad que la contiene (se resuelve por prefijo de `key`).

`unit_changes(fecha)` devuelve, para cada unidad, las relaciones `modifica` o `deroga` vigentes a esa fecha que alcanzan a la unidad o a una unidad contenida en ella, con la unidad de la norma de origen que trae el cambio.

- La consulta en lenguaje natural usa las unidades con `repealed` falso: una unidad derogada no sostiene una respuesta.
- La búsqueda directa usa todas, y muestra las derogadas marcadas, con la norma que las derogó y desde cuándo.
- La pantalla siempre pasa la fecha del día (hora de Buenos Aires). Las pruebas de REQ-007 llaman a las mismas funciones con otras fechas.

### Versiones de una norma

Una norma cambia de dos maneras, y las dos quedan registradas con fecha:

- **Otra norma la modifica o deroga.** Se registra como relación. El texto original no se toca; a partir de `effective_date`, la unidad se muestra junto con el texto literal de la que la modifica (REQ-007).
- **Se publica otro texto de la misma norma** (por ejemplo, una rectificación). Se carga como documento nuevo de la misma norma y, una vez validado, `registrar_version` lo deja como versión siguiente: le asigna `version_number`, lo marca `in_use` y cierra la vigencia de la versión anterior.

El primer documento validado de una norma queda como versión 1 y en uso sin más pasos. Un segundo documento de la misma norma (otro formato u otra versión) se puede cargar y validar, pero no entra en las consultas hasta que `registrar_version` diga qué es: versión nueva, o reemplazo del archivo en uso de una versión existente. Así la misma norma cargada en tres formatos (prueba de REQ-015) no aparece tres veces en una respuesta.

### Dónde se guarda el archivo original

En la base, en `norms_document_file`. Se comparó con guardarlo en disco en un volumen de Docker:

| | En la base | En un volumen |
|---|---|---|
| Respaldo | Un solo archivo de `pg_dump` contiene datos y originales | Dos cosas para respaldar y restaurar, que pueden quedar desparejas |
| Mudanza a otro equipo | Restaurar el respaldo | Restaurar el respaldo y copiar el volumen |
| Tamaño de la base | Crece con los archivos | No crece |
| Entrega del original | La vista lee de la base | La vista lee del disco |

Con menos de 10 documentos, el tamaño no pesa y gana tener un solo lugar para respaldar. Si en las features 002 a 004 el volumen de ofertas escaneadas vuelve incómodo el respaldo, se revisa ahí.

## Flujo de IA

### Ingesta

1. `cargar_norma` recibe el archivo, los datos de REQ-001 y la categoría. Sin categoría no incorpora y pide el dato (REQ-017).
2. Duplicados (REQ-011), en este orden:
    - Misma huella de archivo: avisa y no incorpora.
    - Mismo texto canónico en otro archivo, o mismos tipo, número, año y organismo emisor: avisa "misma norma" y solo incorpora con confirmación expresa, en la que la persona indica si es otro archivo de lo mismo o una versión nueva.
3. Lectura por formato y partición con reglas (ADR-0004). Todo en CPU, dentro de `app`, sin usar los servicios de IA.
4. Se guardan el original, la lectura, el texto canónico, las unidades y el informe. La lectura queda `pending`.
5. `ver_informe` muestra el informe en texto, con la lista de unidades y sus claves. `validar_informe` pide confirmación; al validar, calcula pasajes y vectores (necesita el servicio `embeddings`; si no responde, no valida y lo dice), pasa la lectura a `validated` y crea una versión nueva de la normativa.
6. `releer_norma` crea una lectura nueva de un documento ya cargado, sin volver a pedir el archivo. Es el camino cuando se corrige una regla de partición: la lectura nueva pasa otra vez por informe y validación, y al validarse deja a la anterior como `superseded`.

Metadatos de cada unidad: los de `norms_unit`. Metadatos de cada pasaje: los de `norms_passage`.

### Recuperación

Entrada: la pregunta y la fecha de referencia. Los tres caminos leen de `consultable_units(fecha)` con `repealed` falso.

| Camino | Qué hace | Cuántos |
|---|---|---|
| Por significado | Vector de la pregunta contra los vectores de los pasajes, distancia coseno, búsqueda exacta | 30 pasajes |
| Por palabras | Búsqueda de texto de Postgres con `spanish_unaccent`, palabras unidas por "o" | 30 pasajes |
| Por referencia exacta | Si la pregunta nombra una norma o un artículo ("art. 5 inc. b", "Disposición 297/03"), trae esas unidades por sus datos. Si nombra un inciso, entra el artículo que lo contiene | Las que coincidan |

Se unen sin repetir (unos 65 pasajes como mucho). No hay fórmula de fusión: el orden lo pone el reranker.

### Reordenamiento

1. El reranker puntúa cada pasaje (encabezado más texto) contra la pregunta. `llama-server` devuelve un valor sin escala fija; la aplicación lo lleva a un número entre 0 y 1 con la función sigmoide, que es la conversión que describen los autores del modelo. Ese número es el que se compara con el umbral y el que se registra.
2. Los pasajes se agrupan por unidad base, con el mejor puntaje de sus pasajes.
3. Primera barrera de abstención (ver "Abstención").
4. Selección: unidades con puntaje igual o mayor al umbral, hasta 3 por categoría. Los considerandos no ocupan ese cupo: tienen uno propio de hasta 2, para que un fundamento no desplace a un artículo. El cupo por categoría existe para que el régimen específico no deje afuera al marco nacional ni a un dictamen (REQ-018, REQ-019).
5. Cambios: a cada unidad seleccionada se le suman, por relación y no por parecido, las unidades que la modifican a la fecha (`unit_changes`).
6. Espacio: si el total no entra en el contexto del modelo (16.384 tokens menos instrucciones, pregunta y respuesta), se incluye primero la mejor unidad de cada categoría, después la segunda de cada una, y así; de una unidad más larga que 1.500 tokens se le muestran al modelo solo los pasajes que superaron el umbral. Lo que queda afuera se registra. La cita muestra siempre la unidad entera.
7. Orden de entrega: régimen específico, otra normativa aplicable, marco nacional, dictamen legal, recomendación de auditoría; dentro de cada categoría, por puntaje; los considerandos, al final. El orden lo fija el código.

Todos los números de esta sección son valores iniciales, guardados como parámetros en `settings.py` y copiados en cada consulta.

### Generación

Un solo pedido a `generation` por consulta, sin transmisión parcial, con temperatura 0, semilla fija y pensamiento apagado.

**Qué recibe el modelo.** Las instrucciones (archivo versionado en `queries/prompts/`), la pregunta y las unidades seleccionadas. Cada unidad lleva un alias corto (`U1`, `U2`, …), su categoría con su papel, la norma, la ruta, el tipo y el texto. Una unidad modificada lleva a continuación el texto de la que la modifica, con la fecha. Los considerandos van en un bloque aparte, rotulado como contexto.

**Qué se le pide.** En resumen: responder solo con lo que dicen las unidades mostradas; escribir afirmaciones cortas, cada una completa por sí misma, y señalar para cada una los alias que la sostienen; no copiar el texto de la norma; aplicar el régimen específico y tratar al marco nacional como marco, y a dictámenes y recomendaciones como criterio que acompaña; no usar un considerando como si estableciera una obligación; ante una unidad modificada, responder según el texto vigente; si el régimen específico y el marco nacional tratan el punto de manera distinta, decir en una misma afirmación qué dispone cada uno, citar los dos y marcarlo; y si las unidades no permiten responder, devolver "no determinado" sin afirmaciones.

**Formato de salida.** Un JSON que el motor obliga a cumplir con un esquema armado para cada consulta:

```json
{
  "status": "grounded",
  "statements": [
    {"text": "…", "citations": ["U1", "U4"], "regimes_differ": false}
  ]
}
```

- `status`: `grounded` o `undetermined`.
- `statements`: hasta 6. Cada una con al menos una cita.
- `citations`: el esquema enumera solo los alias de las unidades mostradas en esa consulta.
- `regimes_differ`: verdadero cuando la afirmación señala una diferencia entre régimen específico y marco nacional (REQ-019).

### Cita

El modelo señala la unidad; el sistema pone el texto.

1. La aplicación valida la salida (ver tabla).
2. Traduce cada alias al `id` de la unidad y toma de la base su texto, categoría, norma, ruta, origen del texto y cambios.
3. Ordena las citas de cada afirmación por categoría, con los considerandos al final, y ordena las afirmaciones por la categoría de su primera cita. Así el régimen específico va primero sin depender del modelo (REQ-018).
4. Guarda la respuesta con los `id` de las unidades. La pantalla arma la página desde lo guardado, leyendo el texto de `norms_unit`.

**"Palabra por palabra"** tiene una sola definición en todo el proyecto, la del ADR-0004: la misma secuencia de palabras, con los mismos signos, después de las cinco operaciones que producen el texto canónico. En la práctica se comprueba así: el texto que se muestra en una cita es igual, carácter por carácter, a `canonical_text[char_start:char_end]` de su lectura. Las pruebas y las evals usan esa comprobación y ninguna otra. Que el texto canónico sea fiel al documento lo sostienen la lectura determinista, la validación de una persona (REQ-005) y la marca de reconocimiento sobre imagen (REQ-015).

Qué pasa cuando la salida del modelo no es la esperada:

| Situación | Resultado | Motivo registrado |
|---|---|---|
| La salida no es un JSON que cumpla el esquema (por ejemplo, quedó cortada) | Falla técnica | `invalid_output` |
| Alguna afirmación cita un alias que no se le mostró, o no trae citas | "No determinado": se descarta la respuesta entera | `invalid_citation` |
| `regimes_differ` verdadero sin una cita del régimen específico y otra del marco nacional | Se apaga la marca; la afirmación queda con sus citas | Anomalía `regimes_flag_dropped` |
| `status` `undetermined` | "No determinado"; si trajo afirmaciones, se descartan | `model_abstained` |

El esquema ya impide que el modelo nombre una unidad que no se le mostró. La validación existe igual, porque de ella depende que nunca se muestre una afirmación sin sustento (P3). Nunca se muestra una respuesta a medias. Cada una de estas situaciones se cuenta en las evals; se espera cero.

### Abstención

Una sola regla. El resultado es "no determinado" si ocurre cualquiera de estas tres cosas, en este orden:

1. **Nada pertinente.** Ninguna unidad alcanza el umbral del reranker. No se llama al modelo. Motivo `below_threshold`.
2. **El modelo se abstiene.** Recibió unidades y devolvió `undetermined`. Motivo `model_abstained`.
3. **Cita inválida.** Motivo `invalid_citation`.

En los tres casos la pantalla muestra lo mismo: el aviso de "no determinado", sin afirmaciones y sin citas. El motivo queda en el registro.

Las dos barreras cumplen papeles distintos. El umbral frena las preguntas ajenas a la normativa, es barato y siempre da lo mismo. El modelo frena las preguntas sobre un tema que la normativa menciona pero no resuelve, que el puntaje no distingue. Por eso el umbral se calibra para no frenar preguntas que sí tienen respuesta, y no para alcanzar por sí solo el 90 %.

Calibración con el conjunto de preguntas:

1. Se corre la recuperación sobre todas las preguntas y se anota el puntaje más alto de cada una.
2. Se elige el umbral más alto que frena por error a lo sumo el 5 % de las preguntas con respuesta. Como son unas 30 preguntas, se calcula dejando cada vez una afuera y midiendo sobre ella, y el valor se informa como provisorio.
3. Con ese umbral se corre el sistema completo y se miden las exigencias de la spec.
4. Si la abstención no llega al 90 %, se ajustan primero las instrucciones (la segunda barrera). Subir el umbral cuesta respuestas correctas y es la última opción.
5. Cualquier cambio de umbral, instrucciones, reranker o corpus obliga a correr todo otra vez (P7).

Una falla técnica (un servicio que no responde, una espera agotada a los 60 segundos, una salida inválida) no es un "no determinado": la pantalla muestra "No se pudo completar la consulta".

### Búsqueda directa (REQ-010)

En la misma pantalla, sin modelos de IA:

- **Por norma y número de artículo:** se elige la norma y se escribe el número. Devuelve las unidades con ese número, cada una con su ruta y su texto.
- **Por palabras:** búsqueda de texto de Postgres sobre los pasajes, sin distinguir acentos, con comillas para frase exacta. Los resultados se agrupan por unidad base.

Cada resultado muestra la categoría, el texto literal, el enlace al original, los cambios vigentes y, si está derogada, la marca con la norma que la derogó y la fecha. También muestra los vínculos de su norma con otras, en los dos sentidos (REQ-006).

### Forma de la respuesta

Lo que `queries/services.py` le entrega a la pantalla y guarda en `queries_query.result`:

```json
{
  "query_id": 318,
  "status": "grounded",
  "reason": null,
  "statements": [
    {"text": "…", "regimes_differ": true, "citations": [4812, 5160]}
  ],
  "units": {
    "4812": {
      "norm": "Disposición AFIP 297/03",
      "category": "regimen_especifico",
      "unit_type": "articulo",
      "path": "Anexo I › Título II › Artículo 14",
      "text_origin": "pdf_text",
      "document": 3,
      "page_start": 12,
      "changes": [
        {"relation_type": "modifica", "unit": 6033, "target_key": "anexo-i/art-14/inc-b", "effective_date": "2010-05-01"}
      ]
    }
  }
}
```

- `status`: `grounded` (con fundamento), `undetermined` (no determinado) o `error` (falla técnica). `reason` lleva el motivo en los dos últimos casos: `below_threshold`, `model_abstained` o `invalid_citation` para `undetermined`; `timeout`, `service_unavailable` o `invalid_output` para `error`.
- `statements` está vacío salvo en `grounded`.
- `units` trae una vez cada unidad citada y cada unidad que la modifica. El texto literal no viaja en la respuesta guardada: la pantalla lo lee de la base por `id`.
- El papel de cada cita ("es lo que se aplica", "marco de referencia", "criterio que acompaña", "contexto") lo deriva la pantalla de `category` y `unit_type`.
- Cuando `regimes_differ` es verdadero, la pantalla agrega un aviso con texto fijo del sistema ("El régimen específico y el marco nacional tratan este punto de manera distinta. Se aplica el régimen específico."), muestra los dos textos y rotula el del régimen específico como aplicable (REQ-019).

## Pantalla, acceso y comandos

**Pantalla.** Una sola página, armada en el servidor, con la disposición del ADR-0005: pregunta, y uno de tres bloques que se distinguen por título, ícono y color ("Respuesta con fundamento en la normativa", "No determinado", "No se pudo completar la consulta"). En la misma página está el formulario de búsqueda directa. Al elegir una cita se despliega el texto literal, con el enlace "Abrir el documento original" y, si corresponde, la leyenda de que el texto proviene de reconocimiento sobre imagen. Tipografías del sistema, una hoja de estilos y un script propios; ninguna referencia externa. Al recargar se muestra lo guardado; no se vuelve a consultar.

**Documento original.** Lo entrega una vista que exige sesión, leyendo de `norms_document_file`. Un PDF se abre con el visor del navegador. Una página web guardada se entrega con una política que impide ejecutar scripts y cargar recursos de internet; el archivo no se modifica.

**Acceso.** Ingreso con usuario y clave de Django; Argon2id; sesiones en la base; mensaje de error único; toda página exige sesión salvo la de ingreso. El rol se comprueba en las funciones de negocio.

**Comandos.** Se corren con `docker compose exec app python manage.py <comando>`. Cada uno pide `--usuario` y la clave por teclado, salvo `crear_usuario`.

| Comando | Qué hace | Requisitos | Rol |
|---|---|---|---|
| `cargar_norma` | Incorpora un documento con sus datos y su categoría; avisa si ya está | REQ-001, 011, 015, 017 | Lectura y escritura |
| `releer_norma` | Vuelve a leer y partir un documento ya cargado; deja una lectura nueva sin validar | REQ-004, 005 | Lectura y escritura |
| `listar_normas` | Lista normas con sus datos, documentos, estado de validación y vínculos | REQ-001, 006 | Los dos |
| `ver_informe` | Muestra el informe de lectura, con las unidades y sus claves | REQ-004 | Los dos |
| `validar_informe` | Valida una lectura, previa confirmación, y calcula sus pasajes y vectores | REQ-005 | Lectura y escritura |
| `registrar_relacion` | Registra que una norma modifica, complementa, reglamenta o deroga a otra, con fecha y, si corresponde, las unidades | REQ-006, 007 | Lectura y escritura |
| `registrar_version` | Deja un documento validado como versión de su norma, o como el archivo en uso de una versión | REQ-007 | Lectura y escritura |
| `crear_usuario` | Da de alta un usuario con su rol. Lo corre quien administra el equipo, sin rol de EVALUON; queda registrado | REQ-016 | — |
| `correr_evals` | Corre el conjunto de preguntas y guarda la corrida | Calidad (P7) | Lectura |

Los nombres de comandos y de sus opciones se proponen en español, como excepción a la convención de identificadores en inglés: es lo que escribe el responsable de normativa, igual que lee los textos de la pantalla. Todo lo demás (servicios, tablas, campos, funciones) va en inglés. Queda para decisión del responsable; si prefiere inglés, es un cambio de nombres de archivos y no de diseño.

`releer_norma` y `correr_evals` no estaban en la tabla del ADR-0005. El primero cubre un hueco: sin él, un documento mal partido no tiene forma de volver a leerse, porque REQ-011 impide cargar otra vez el mismo archivo. El segundo es la herramienta de P7.

## Registro de auditoría

Todo queda en `audit_event`; cada consulta tiene además su detalle en `queries_query`. Datos comunes a todo hecho: momento, usuario, canal (pantalla, comando o eval), resultado y versión de la normativa.

| Hecho | Qué se guarda además |
|---|---|
| Carga (`load`) y relectura (`reread`) | Documento y norma; datos ingresados y categoría; nombre, formato detectado, tamaño y huella del archivo; huella del texto canónico; versiones de las herramientas, huella del modelo de español de Tesseract y versión de las reglas; lectura creada; resumen del informe (unidades por tipo, páginas ilegibles, tramos no ubicados); resultado de las comprobaciones de duplicado y la confirmación expresa, si la hubo. Una carga rechazada por duplicado también se registra |
| Validación (`validation`) | Lectura validada; huella del informe que la persona vio; lectura reemplazada, si había; cantidad de pasajes; nombre y huella del modelo de embeddings; versión nueva de la normativa |
| Relación (`relation`) | Tipo, normas, claves de unidad, fecha de vigencia del cambio; versión nueva de la normativa |
| Versión (`version`) | Documento, número de versión, vigencia, documento que deja de estar en uso; versión nueva de la normativa |
| Consulta (`query`) | Pregunta; fecha de referencia; modelo de generación (nombre, huella del archivo, compilación del motor, contexto, temperatura, semilla, pensamiento, máximo de salida); modelos de embeddings y de reranker (nombre y huella); versión de las instrucciones y pedido completo; parámetros de búsqueda (candidatos por camino, umbral, cupos, espacio); cada candidato con su camino, puntaje y origen del texto; unidades enviadas, agregadas por relación y dejadas afuera; puntaje más alto; decisión de abstención y motivo; salida del modelo sin tocar; anomalías; respuesta final; tiempos por etapa |
| Búsqueda (`search`) | Tipo de búsqueda, términos, fecha de referencia y unidades devueltas, con su marca de derogada |
| Ingreso (`login`) | Usuario y canal |
| Ingreso fallido (`login_failed`) | Nombre intentado y canal. Nunca la clave |
| Operación rechazada por rol (`rejected`) | Usuario, operación intentada y canal |
| Alta de usuario (`user_created`) | Usuario creado y rol; hecho por quien administra el equipo |

Con el registro de una consulta se puede explicar una respuesta pasada sin volver a ejecutarla. El registro no guarda claves ni identificadores de sesión.

Observación: el restablecimiento de una clave olvidada usa el comando `changepassword` de Django (ADR-0005), que no pasa por este registro. Ningún requisito lo pide; se informa para que no sorprenda en la auditoría.

## Evals

**Casos.** Un archivo por pregunta en `evals/casos/EV-NNN.yaml`, con el formato de `evals/README.md` y estos datos adicionales para poder medir sin intervención:

- `unidades`: las unidades que sostienen la respuesta, por norma y `key`. Vacío en las preguntas sin respuesta.
- `datos_clave`: los datos que la respuesta tiene que contener (un plazo, un porcentaje, un sí o un no), cuando los hay.
- `difieren`: verdadero en las preguntas de REQ-019.
- `etiquetas`: referencia exacta, palabras distintas a las de la norma, dos categorías, ajena a la normativa, tema cercano que la normativa no resuelve.
- `visto_bueno`: quién de la Comisión lo aprobó y cuándo. Un caso sin visto bueno no se corre.

**Cómo se corre.** `correr_evals`, dentro de `app`, con los servicios reales y la normativa cargada y validada. Llama a la misma función que la pantalla, con el canal `eval`, una pregunta por vez. Las consultas quedan también en el registro de auditoría.

**Dónde se guarda.** Una carpeta por corrida en `evals/corridas/`, con la fecha, el commit y el modelo en el nombre:

- `parametros.json`: modelos con sus huellas, compilación del motor, versión de las instrucciones, parámetros de búsqueda, umbral y versión de la normativa.
- `resultados.jsonl`: un renglón por caso, con el resultado, las unidades citadas, las medidas y los tiempos.
- `resumen.md`: las medidas de la tabla, la comparación con la corrida anterior y la lista de casos fallados.

**Cómo se mide cada exigencia.**

| Exigencia de la spec | Cómo se mide | Umbral |
|---|---|---|
| Cita literal | Sobre todas las citas de todas las respuestas: el texto mostrado es igual a `canonical_text[char_start:char_end]` | 100 % |
| Respuesta correcta que cita la unidad correcta | Sobre las preguntas con respuesta. Un caso cuenta si el resultado es `grounded`, cita todas las unidades de `unidades` (si el caso nombra un inciso, vale el artículo que lo contiene), contiene los `datos_clave` y, si `difieren` es verdadero, trae la marca `regimes_differ` con las dos citas. En la corrida que se presenta para aprobar, el responsable revisa además las respuestas contra la esperada y puede dar por incorrecta cualquiera | Al menos 85 % |
| Abstención | Sobre las preguntas sin respuesta. Cuenta si el resultado es `undetermined`. Una falla técnica no cuenta como abstención | Al menos 90 % |
| Tiempo de respuesta | Tiempo total de cada consulta, medido en el equipo, con los servicios ya cargados. Se informan la mediana y el máximo | Máximo de 30 segundos |

Se informan además, sin ser exigencias de la spec: las medidas de recuperación del ADR-0003 (unidad correcta entre los candidatos y entre las seleccionadas, preguntas con respuesta frenadas por el umbral, tiempo de la recuperación), las del ADR-0002 (salidas con falla de formato o de cita, memoria de video ocupada, igualdad al repetir la corrida) y, aparte, los casos de REQ-018 y REQ-019. La comparación quitando piezas del ADR-0003 se corre una vez.

Con unas 30 preguntas, cada una pesa entre 3 y 5 puntos: una diferencia de una pregunta entre dos corridas no demuestra nada.

**Regla de P7.** Todo cambio en recuperación, instrucciones, modelo o umbral se acepta solo con una corrida nueva. Una baja respecto de la anterior requiere aprobación del responsable.

## Cobertura de requisitos

| Requisito | Cómo se resuelve | Cómo se verifica |
|---|---|---|
| REQ-001 | `cargar_norma`; `norms_norm` y `norms_document` guardan tipo, número, organismo, título, fechas de publicación y de vigencia, y fuente; `listar_normas` | Test: tras cargar con sus datos, el listado muestra la norma con todos ellos |
| REQ-002 | `norms_document_file`; vista con sesión que entrega el original | Test: la huella de lo que entrega la vista es igual a la del archivo cargado, en PDF y en HTML |
| REQ-003 | Partición con reglas (ADR-0004); `norms_unit` con `unit_type`, `key`, `path`, páginas y posición | Test: tabla esperada de la Disp. 297/03 escrita a mano; `art-1` y `anexo-i/art-1` son dos unidades; el índice no produce unidades; cada texto es igual a su recorte |
| REQ-004 | Informe de lectura en `norms_reading.report`; `ver_informe` | Test: un PDF con una página de ruido; el informe señala esa página y ninguna otra |
| REQ-005 | Estado de la lectura; `consultable_units` como único camino | Test: una norma cargada y sin validar no aparece por ninguno de los tres caminos ni en la búsqueda directa |
| REQ-006 | `norms_relation`, con claves de unidad cuando corresponde; `registrar_relacion`; vínculos en `listar_normas` y en la pantalla | Test: registrada la relación, al ver cualquiera de las dos normas aparece el vínculo; una relación entre unidades guarda sus claves |
| REQ-007 | `effective_date` de las relaciones, versiones de documento con su vigencia, `consultable_units(fecha)` y `unit_changes(fecha)`; `registrar_version` | Test: un artículo modificado en una fecha; antes, solo el original; después, el original con el texto literal de la que lo modifica, señalando el cambio. Test: dos versiones de una norma; cada fecha devuelve la suya |
| REQ-008 | Recuperación, generación con esquema e inserción del texto desde la base | Test con doble del motor: la respuesta cita el artículo y el texto es el de la base. Evals: cita literal 100 %, respuesta correcta al menos 85 % |
| REQ-009 | Regla única de abstención | Tests con dobles: bajo el umbral no se llama al modelo; el modelo se abstiene; cita inválida; en los tres el resultado es `undetermined`. Evals: abstención al menos 90 % |
| REQ-010 | `queries/search.py` y formulario en la pantalla de consulta | Test: un usuario de lectura busca norma y artículo y obtiene la unidad con su texto; "artículo 1" de la 297/03 devuelve las dos unidades con su ruta; busca por palabras sin tildes; una unidad derogada aparece marcada |
| REQ-011 | Huella del archivo, huella del texto canónico y datos de la norma; confirmación expresa en `cargar_norma` | Test: el mismo archivo dos veces da un aviso y un solo documento; la misma norma en otro archivo avisa y solo se incorpora con confirmación |
| REQ-012 | `audit_event`, `queries_query` y `norms_corpus_version` | Test: tras una consulta, su registro muestra pregunta, unidades recuperadas, respuesta, versión de la normativa, usuario y fecha. Tests equivalentes para carga y validación |
| REQ-013 | Pantalla de consulta | Test con el cliente de pruebas: la página muestra la respuesta con sus citas, el texto literal de cada unidad y el enlace al original |
| REQ-014 | Bloque propio de "No determinado" | Test: con resultado `undetermined` la página muestra ese aviso, distinto del de una respuesta, y ninguna cita |
| REQ-015 | Lectura por formato (`reading/`); `text_origin` en la unidad y en el informe | Test: la misma norma en PDF con texto, PDF escaneado y HTML da la misma lista de unidades; en el escaneado, todas con origen `ocr` y el informe lo dice |
| REQ-016 | Ingreso de Django, Argon2id, sesiones en la base; `role` en el usuario; comprobación en las funciones de negocio; `crear_usuario` | Test: sin sesión, la consulta redirige al ingreso; un usuario de lectura que corre `cargar_norma` o `validar_informe` es rechazado y queda el registro; la clave guardada no es legible |
| REQ-017 | `category` obligatorio en `norms_norm`; lo exige `cargar_norma` | Test: una carga sin categoría no incorpora y pide el dato |
| REQ-018 | Cupo por categoría en la selección; orden de citas y de afirmaciones fijado por el código; rótulo de categoría y papel en la pantalla | Test con doble: artículo del régimen específico y dictamen; el artículo va primero y cada cita muestra su categoría; un considerando va al final, rotulado como contexto |
| REQ-019 | Cupo por categoría, marca `regimes_differ` validada por el código y aviso de texto fijo en la pantalla | Test con doble: con la marca, la página muestra los dos textos y señala el del régimen específico como aplicable. Evals: casos con `difieren` |

Los requisitos no funcionales de la spec no tienen identificador `REQ-NNN`. Se atienden así: calidad y tiempo, en "Evals"; funcionamiento sin conexión, con la red interna de Docker, `--offline` y una prueba con la red desconectada; claves no legibles, con REQ-016; lenguaje llano, con la revisión de los textos de la pantalla y de los comandos.

## Verificación contra la constitución

| Principio | Cumple | Nota |
|---|---|---|
| P1 La spec es la fuente de verdad | sí | Cada parte del plan responde a un requisito o a un requisito no funcional. Lo agregado respecto de los ADR (`releer_norma`, `correr_evals`, versión de la normativa) está justificado contra un requisito o un principio |
| P2 Trazabilidad | sí | La tabla de cobertura cruza los 19 requisitos con su test. Las tareas de entorno y las de requisitos no funcionales se anotan contra los requisitos que habilitan, porque esos requisitos no tienen identificador propio (se informa al Coordinador) |
| P3 El sistema recomienda | sí | Toda afirmación lleva su cita con texto literal; sin sustento el resultado es "no determinado"; una falla técnica se muestra como falla. En esta feature no hay decisiones de la Comisión que registrar |
| P4 Datos | sí | Solo material público. Ningún servicio externo en el camino de los documentos: IA local con `--offline` y red interna. Internet se usa una vez, para bajar imágenes y modelos |
| P5 Local y reproducible | sí | Docker Compose, imágenes y modelos con versión y huella fijas, originales dentro de la base, un comando para levantar. La descarga de modelos es un paso único y documentado |
| P6 Auditoría | sí | Ver "Registro de auditoría" |
| P7 Evals | sí | Ver "Evals". Los umbrales son los de la spec |
| P8 Normativa versionada | sí | Fuente y fecha de vigencia por documento, versiones por norma, relaciones con fecha y `norms_corpus_version` en cada consulta. Las unidades no se modifican |
| P9 Hojas de compliance | sí | No aplica en esta feature: no hay ofertas ni validaciones externas. Nada del plan las infiere |
| P10 Simplicidad | sí | Una imagen para los tres servicios de IA; sin índice aproximado, cola, caché ni servidor intermedio; sin pantallas fuera de la de consulta; sin corrección manual de texto |
| P11 Compuertas humanas | sí | El plan y los ADR quedan en borrador y propuesto. Las decisiones del responsable están en la última sección |

## Decisiones

ADR que este plan necesita aprobados, los cuatro en estado propuesto y ajustados en la integración (cada uno termina con una sección "Ajustes de integración"):

| ADR | Decide |
|---|---|
| ADR-0002 | Motor `llama-server` y modelo Gemma 4 12B, con Gemma 4 26B-A4B como contraste |
| ADR-0003 | `bge-m3`, `bge-reranker-v2-m3`, búsqueda combinada sobre Postgres sin índice aproximado, servidos con `llama-server` |
| ADR-0004 | pdfplumber, Tesseract, BeautifulSoup y partición con reglas |
| ADR-0005 | Django, páginas armadas en el servidor, Argon2id, sesiones en la base y comandos |

Decisiones tomadas en este plan al integrar:

1. **Embeddings y reranker se sirven con `llama-server`**, la misma imagen que la generación. Evidencia: la documentación de `llama-server` nombra a `bge-reranker-v2-m3` como ejemplo de su endpoint de reranker, que se probó con ese modelo al incorporarse; hay archivos GGUF de los dos modelos. Lo que no hay: los archivos son conversiones de un tercero y no de los autores; no encontré una medición de que den los mismos resultados que el original; una conversión de otro tercero falló al cargar por faltarle un dato. Por eso es la opción principal y no una certeza: la etapa 0 decide, con Text Embeddings Inference como plan B. Detalle y fuentes en el ADR-0003.
2. **Memoria de video:** 20 GB de tope sobre 24; estimado de 12,6 GB; se mide en la etapa 0.
3. **Unidades anidadas:** se indexan y se citan unidades base; los incisos sirven para relaciones y búsqueda directa.
4. **Identificación:** `id` para el registro, `key` para relaciones y comandos, `path` para mostrar.
5. **Relaciones y versiones:** relaciones por norma y clave de unidad, con fecha; versiones como documentos de la misma norma; `consultable_units(fecha)`.
6. **Archivo original:** en la base.
7. **Nombres:** servicios e identificadores en inglés; comandos en español, a confirmar.
8. **Migraciones:** automáticas solo sobre una base vacía; con datos, respaldo previo.
9. **Forma de la respuesta:** afirmaciones con citas, tres estados, marca `regimes_differ`.
10. **Abstención:** una regla con tres motivos; umbral calibrado para no frenar preguntas con respuesta.
11. **Cita literal:** una definición; cita inválida da "no determinado"; formato inválido da falla técnica.
12. **Registro:** `audit_event` más `queries_query`.
13. **Evals:** `correr_evals`, carpeta por corrida, cuatro medidas exigidas.

## Orden de construcción

Regla para asignar: los bloques marcados "en paralelo" no comparten archivos entre sí y se pueden dar a desarrolladores distintos. Todo lo que toca el esquema (`models.py`, `migrations/`) o la configuración compartida (`settings.py`, `urls.py` de la raíz, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `.env.example`, `tests/conftest.py`) va de a uno, en una sola fila de tareas.

Dos trabajos de personas corren desde el primer día, en paralelo con todo: reunir los archivos de las normas en `corpus/normativa/`, y redactar y validar las preguntas del conjunto (Coordinador, responsable e integrante de la Comisión).

### Etapa 0 · Comprobación del entorno

De a uno. No construye funciones: comprueba que las piezas funcionan en la notebook y deja medido lo que hoy es estimación. Deja el `docker-compose.yml` con los seis servicios, las versiones fijadas y un informe en `specs/001-normativa/entorno.md`. El detalle de cada prueba está en "Sin verificar y cómo se cierra".

1. GPU visible dentro de un contenedor.
2. `generation` responde y cumple un esquema con lista cerrada de valores; se mide su velocidad.
3. `embeddings` y `reranker` cargan en `llama-server`, reproducen los valores publicados y rechazan una entrada demasiado larga; se mide la memoria de video con los tres cargados.
4. Postgres: versión fijada, extensiones `vector` y `unaccent`, configuración `spanish`.
5. Django 6.1 con sus librerías: el esqueleto arranca y corre un test.

Si el punto 3 falla, se pasa al plan B y se actualizan este plan y el ADR-0003 antes de seguir. Si el punto 2 muestra que una consulta no entra en 30 segundos, se informa al responsable antes de seguir.

### Etapa 1 · Base común

De a uno: es esquema y configuración compartida.

1. Esqueleto de Django, usuario propio con rol, ingreso y salida, Argon2id, sesiones, `permissions.py`, `audit_event` y su función de registro, `crear_usuario` (REQ-016, REQ-012).
2. Esquema completo de `norms` y `queries` como está en "Modelo de datos", con las migraciones de SQL propio (`consultable_units`, `unit_changes`, `spanish_unaccent`) y sus reversas (REQ-005, REQ-007, REQ-012).
3. Clientes de `evaluon/ai/` y sus dobles en `tests/conftest.py`.

### Etapa 2 · Hilo mínimo de punta a punta

Objetivo: cargar una norma en PDF con texto, validarla, preguntar en la pantalla y ver una respuesta con su cita y su registro. Todo lo mínimo, para probar el recorrido entero cuanto antes.

Dos líneas en paralelo, que no comparten archivos:

- **Línea de datos:** lectura de PDF con texto y partición solo de artículos (`norms/reading/pdf_text.py`, `norms/splitting/`); `cargar_norma`, `listar_normas`, `ver_informe` y `validar_informe` mínimos (`norms/services/loading.py`, `listing.py`, `validation.py`); pasajes y vectores (`norms/indexing.py`). REQ-001, 003, 004, 005, 017.
- **Línea de consulta:** pantalla con los tres bloques, sobre la forma de la respuesta y con el doble del motor (`queries/views.py`, `forms.py`, `templates/`, `static/`). REQ-013, 014.

Después, de a uno: recuperación mínima por significado con reranker (`queries/retrieval.py`), generación con esquema e inserción de citas (`queries/answering.py`, `queries/prompts/`), y `queries/services.py` que las une y guarda el registro. REQ-008, 009, 012. La etapa termina con una pregunta real respondida en la pantalla con los servicios reales.

### Etapa 3 · Bloques completos

En paralelo. Cada bloque tiene sus archivos:

| Bloque | Archivos | Requisitos |
|---|---|---|
| A · PDF escaneado | `norms/reading/ocr.py` | REQ-015, 004 |
| B · Página web | `norms/reading/web.py` | REQ-015 |
| C · Partición completa e informe | `norms/splitting/` | REQ-003, 004 |
| D · Duplicados y relectura | `norms/services/loading.py`, comandos `cargar_norma` y `releer_norma` | REQ-004, 005, 011 |
| E · Relaciones y versiones | `norms/services/relations.py`, `versions.py`, y los vínculos en `listing.py`, con sus comandos | REQ-006, 007 |
| F · Recuperación completa | `queries/retrieval.py`: tres caminos, cupos, cambios por relación, espacio, umbral | REQ-005, 009, 018, 019 |
| G · Generación completa | `queries/answering.py`, `queries/prompts/`: validación, `regimes_differ`, orden | REQ-008, 009, 018, 019 |
| H · Búsqueda directa | `queries/search.py` | REQ-010 |
| I · Pantalla completa | `queries/views.py`, `templates/`, `static/`, `norms/views.py`: citas con categoría y papel, cambios, aviso de REQ-019, búsqueda, original | REQ-002, 010, 013, 014, 018, 019 |
| J · Acceso y registro | `accounts/`, `audit/services.py`: ingresos fallidos, rechazos por rol, sesión | REQ-012, 016 |
| K · Evals | `queries/evaluation.py`, comando `correr_evals`, `evals/` | Calidad (P7) |

Dependencias dentro de la etapa: C necesita la lectura de la etapa 2; D necesita C; H e I necesitan el esquema y la forma de la respuesta, no a F ni a G; K necesita `queries/services.py` de la etapa 2. I y H comparten la pantalla: H entrega la función de búsqueda e I la muestra.

De a uno: cualquier cambio de esquema que aparezca durante estos bloques, y la unión final en `queries/services.py`.

### Etapa 4 · Corpus real, calibración y evals

De a uno, con los servicios reales. Necesita el corpus en `corpus/normativa/` y el conjunto de preguntas con visto bueno.

1. Cargar y validar el corpus; ajustar las reglas de partición contra los documentos reales.
2. Registrar las relaciones y versiones del corpus.
3. Calibrar el umbral.
4. Correr las evals, la comparación quitando piezas y la medición de tiempo y memoria.
5. Si no se alcanzan las exigencias: seguir la escalera del ADR-0002 (8 bits, instrucciones, modelo de contraste) o el reemplazo del ADR-0003, con decisión del responsable.

### Etapa 5 · Cierre

De a uno: prueba de una consulta con la red desconectada; respaldo y restauración probados; levantar todo desde cero en una base vacía; datos para el runbook (descarga de modelos, procedimiento de migración, respaldo).

## Sin verificar y cómo se cierra

Nada de lo que sigue está comprobado. Cada grupo indica la prueba que lo cierra y cuándo.

### Equipo y placa de video (etapa 0)

| Sin verificar | Prueba que lo cierra |
|---|---|
| Datos del equipo, en especial los 24 GB de memoria de video | El responsable los confirma; `nvidia-smi` en Windows muestra el modelo y la memoria |
| Que Docker Desktop 29 con WSL2 dé acceso a la GPU en esta notebook | `docker run --rm --gpus all` con una imagen de CUDA y `nvidia-smi` dentro del contenedor muestra la placa |
| Memoria de video que usa Windows con la pantalla activa | Lectura de `nvidia-smi` con todos los servicios detenidos |

### Motor de generación (etapa 0; calidad en la etapa 4)

| Sin verificar | Prueba que lo cierra |
|---|---|
| Compilación de `llama.cpp` a fijar | Se elige la etiqueta, se anota en `docker-compose.yml` y se usa en todas las pruebas siguientes |
| Memoria de Gemma 4 12B con contexto de 16.384 | `nvidia-smi` con `generation` cargado y después de una consulta larga |
| Que el motor haga cumplir el esquema con este modelo: lista cerrada de alias, al menos una cita por afirmación, máximo de afirmaciones | Veinte pedidos con un esquema de prueba; todas las salidas validan |
| Que el pensamiento quede apagado | La salida no trae razonamiento previo y el tiempo lo confirma |
| Velocidad en la RTX 5090 de notebook | Un pedido con unos 12.000 tokens de entrada y 800 de salida, repetido cinco veces; tiene que terminar en menos de 25 segundos para dejar lugar a la recuperación |
| Calidad en español jurídico | Evals de la etapa 4 |

### Embeddings y reranker (etapa 0)

| Sin verificar | Prueba que lo cierra |
|---|---|
| Que los archivos GGUF de `bge-m3` y `bge-reranker-v2-m3` carguen en la compilación fijada. Son conversiones de un tercero hechas con versiones viejas de `llama.cpp` | Los dos servicios levantan y `/health` responde |
| Que den los mismos resultados que el modelo original | Embeddings: las cuatro frases de ejemplo de la ficha de `bge-m3` dan similitudes a menos de 0,02 de las publicadas (0,6265; 0,3477; 0,3499; 0,678). Reranker: los dos pares de ejemplo de la ficha de `bge-reranker-v2-m3` dan valores cercanos a los publicados (−8,19 y 5,26; con sigmoide, 0,0003 y 0,995) y en el mismo orden. Si no se cumple, plan B |
| Qué escala devuelve el reranker | Se observa en la prueba anterior; la aplicación guarda siempre el valor entre 0 y 1 |
| Que una entrada más larga que el límite se rechace en lugar de recortarse | Se envía un texto de más tokens que el contexto; el servidor responde con error |
| Memoria de video de cada uno y total | `nvidia-smi` con los tres modelos cargados y después de puntuar 65 pasajes; total dentro de 20 GB |
| Tiempo del reranker con 65 pasajes y de la recuperación completa | Se mide; la meta del ADR-0003 es 3 segundos |
| Plan B: imagen experimental de Text Embeddings Inference para la serie RTX 50, con estos modelos, bajo WSL2 | Solo si hace falta: las mismas pruebas sobre esa imagen |

### Postgres (etapa 0)

| Sin verificar | Prueba que lo cierra |
|---|---|
| Versión exacta de pgvector y etiqueta de imagen | `SELECT extversion FROM pg_extension`; se fija la etiqueta en `docker-compose.yml` |
| Que la imagen traiga `unaccent` y la configuración `spanish` | `CREATE EXTENSION unaccent` y `\dF` |
| Que la configuración propia encuentre palabras sin tilde | Una consulta por "licitacion" encuentra un texto con "licitación" |
| Cómo se tratan los números con barra ("297/03") | Se observa con `ts_debug`; las referencias exactas no dependen de esto |
| Tiempo de la búsqueda exacta por vectores | Se mide en la etapa 4 con el corpus real; se agrega índice solo si supera 200 ms |

### Django y sus librerías (etapa 0 y etapa 1)

| Sin verificar | Prueba que lo cierra |
|---|---|
| Compatibilidad de WhiteNoise, pytest-django y `pgvector` para Python con Django 6.1 | El esqueleto arranca, sirve un archivo estático, corre un test y guarda y lee un vector. Si algo falla: Django 6.0 |
| Parámetros de Argon2 que usa Django | Un test lee una clave guardada y comprueba que igualan o superan el mínimo de OWASP |
| Cómo cuenta Django el vencimiento de la sesión | Un test con el reloj adelantado |
| Tiempo de espera de Gunicorn con hilos | Un test con un doble que tarda más de 30 segundos |

### Lectura de documentos (etapas 2 a 4)

| Sin verificar | Prueba que lo cierra |
|---|---|
| Estructura real de la Disp. 297/03 y de los demás documentos; encabezados y pies; codificación de las páginas de Infoleg | Las reglas y la tabla esperada se escriben contra los archivos de `corpus/normativa/`, que hoy está vacío |
| Calidad de Tesseract en español sobre escaneos de normas; umbrales de confianza (80 y 50) | Prueba de REQ-015: proporción de palabras del escaneado que coincide con el PDF con texto; los umbrales se ajustan con escaneos reales |
| Versión de Tesseract y modelo de español en la imagen | Se incorpora `spa.traineddata` de `tessdata_best` con su huella; la imagen informa su versión |

### Pantalla (etapa 3)

| Sin verificar | Prueba que lo cierra |
|---|---|
| Qué navegador usa la Comisión | Lo informa el responsable |
| Que el visor de PDF abra en la página citada y que el aislamiento de una página web guardada funcione | Prueba a mano en ese navegador, una vez |

## Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El corpus no está en el repositorio | Las reglas de partición, las relaciones y las preguntas no se pueden escribir contra documentos reales; la etapa 4 no arranca | Pedirlo ya. Las etapas 0 a 2 pueden avanzar con una norma |
| Gemma 4 12B no alcanza 85 % o 90 % | No pasa la verificación | Escalera del ADR-0002, con medición en cada paso; hay unos 11 GB libres según las estimaciones |
| Una consulta no entra en 30 segundos | No cumple el tiempo de la spec | Se mide en la etapa 0. Reducir unidades por categoría o el tope de salida; son parámetros |
| `bge-m3` o el reranker no funcionan bien en `llama-server` | La búsqueda trae mal o no arranca | Prueba contra valores publicados en la etapa 0; plan B con Text Embeddings Inference; solo cambian dos clientes |
| La memoria de video real supera el reparto | Los servicios no cargan o se vuelven lentos | Se mide en la etapa 0, antes de construir |
| Las reglas de partición no reconocen un documento, en especial dictámenes y recomendaciones | Ese documento queda sin validar | Se ve en el informe; se agrega una regla y se relee con `releer_norma`. Condición para la alternativa L del ADR-0004 |
| Un escaneo se lee mal | Texto citado distinto del impreso | Marca de reconocimiento en la unidad y en la cita; palabras dudosas en el informe; la persona decide si valida |
| Umbral calibrado con pocas preguntas | Abstención peor que la medida | Calibración dejando una afuera; valor provisorio; recalibrar si cambia el corpus |
| "Respuesta correcta" medida solo de forma automática | Una afirmación errónea junto a la cita correcta pasaría | Revisión del responsable en la corrida que se presenta para aprobar |
| Una relación o una versión mal registrada | Respuestas con un cambio que no corresponde | Las operaciones quedan registradas con su usuario. No hay comando para anularlas porque ningún requisito lo pide; si ocurre, se corrige con una tarea |
| Quien administra el equipo puede entrar a la base | El registro no protege contra esa persona | Límite conocido (ADR-0005); el control de acceso al equipo queda fuera del sistema |

## Qué tiene que decidir el responsable

1. **Aprobar este plan y los ADR 0002 a 0005.** Recomendado: aprobar. Las elecciones de modelo y de servidor de embeddings quedan sujetas a la etapa 0 y a las evals; si alguna no se sostiene, vuelve con una propuesta.
2. **Nombres de los comandos en español**, como excepción a la convención de identificadores en inglés. Recomendado: sí, en español, porque los escribe una persona que no programa.
3. **Cómo se da por correcta una respuesta en las evals.** Recomendado: los criterios automáticos de "Evals" en cada corrida, y además la revisión del responsable en la corrida que se presenta para aprobar la feature.
4. **Valores de partida.** Recomendado: clave de 15 caracteres como mínimo; sesión de 8 horas y hasta cerrar el navegador; las metas de recuperación del ADR-0003 como medidas de diagnóstico y no como exigencias (las exigencias son las cuatro de la spec).
5. **Confirmar los datos del equipo**, en especial los 24 GB de memoria de video, de los que depende el reparto.

No es una decisión, pero hace falta desde ya: los archivos de las normas en `corpus/normativa/`, anotados en `corpus/manifiesto.csv`.

### Decisiones tomadas

El responsable aprobó el plan el 2026-10-02 con las cinco recomendaciones:

1. Plan y ADR 0002 a 0005 aprobados. El modelo y el servidor de embeddings quedan sujetos a la etapa 0 y a las evals.
2. Comandos en español.
3. Evals: criterios automáticos en cada corrida y revisión del responsable en la corrida que se presenta para aprobar.
4. Clave de 15 caracteres como mínimo; sesión de 8 horas y hasta cerrar el navegador; metas de recuperación como diagnóstico.
5. Equipo confirmado: Intel Core Ultra 9, 32 GB de RAM, RTX 5090 de notebook con 24 GB de memoria de video. La etapa 0 lo comprueba igual con `nvidia-smi`.

El corpus inicial es la Disposición AFIP 297/03.

