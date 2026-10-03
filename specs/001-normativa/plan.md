# Plan 001 · Normativa consultable con cita

Estado: aprobado · Fecha: 2026-10-02 · Aprobó: responsable del proyecto

Actualización: 2026-10-02, por ADR-0006 y REQ-020 y REQ-021; aprobada por el responsable el 2026-10-02 (pull request 5).

Ajustes por la etapa 0: 2026-10-02. El parámetro del reranker lo decidió el responsable (ADR-0003, adenda). La nueva definición de la búsqueda por palabras (ADR-0007) la aprobó el responsable el 2026-10-02. Resumen en "Ajustes por la etapa 0", al final.

Spec: `specs/001-normativa/spec.md`

ADR en los que se apoya (los cinco aceptados): `docs/adr/0002-motor-ia-local-y-modelo.md`, `0003-recuperacion-embeddings-reranker.md`, `0004-lectura-y-particion-de-documentos.md`, `0005-aplicacion-web-y-acceso.md`, `0006-dos-regimenes-segun-fecha-de-autorizacion.md`.

Qué cambió con la actualización está resumido al final, en "Actualización por ADR-0006".

## En pocas palabras

Se construye un sistema que corre entero en la notebook del proyecto, sin mandar nada a internet, y que hace tres cosas.

1. **Lee las normas y las separa en partes con nombre.** El responsable de normativa carga cada documento (PDF, PDF escaneado o página web guardada) escribiendo una orden en la terminal. Una norma puede venir en más de un archivo: la Disposición 247/2022 son dos, el cuerpo y el anexo, y quedan bajo la misma norma. El sistema parte cada documento en artículos, incisos, anexos y considerandos; el texto con título propio y sin número, como una cláusula transitoria, queda como una parte más, con el nombre que le da el documento. Después entrega un informe que dice qué reconoció, qué páginas no pudo leer y qué no supo ubicar. Hasta que una persona valida ese informe, la norma no se usa para responder.
2. **Busca y responde con la cita, para una fecha.** Hay dos regímenes de contrataciones: la Disposición 247/2022 y la 297/03 que esta abrogó. Cuál se aplica depende de cuándo se autorizó el procedimiento. Por eso cada pregunta se hace para una fecha de autorización, y el sistema trabaja solo con lo que regía ese día. Busca los artículos que tratan el tema por tres caminos (por significado, por palabras y por número de artículo), les pone un puntaje de pertinencia y le pasa los mejores a un modelo de lenguaje que redacta la respuesta. El modelo no copia el texto de la norma: solo señala qué artículo sostiene cada afirmación, y el sistema pone el texto tal como está guardado. Así la cita no puede salir distinta del documento.
3. **Dice "no determinado" cuando no hay sustento.** Si nada de lo cargado trata la pregunta, si el modelo no encuentra base suficiente o si para esa fecha no hay un régimen cargado, el resultado es "no determinado", con un aviso propio y sin citas.

**Qué va a ver la Comisión.** Una sola pantalla, a la que se entra con usuario y clave. Tiene un cuadro para escribir la pregunta, un campo con la fecha de autorización del procedimiento (viene con la del día y se puede cambiar) y, en la misma pantalla, la opción de buscar un artículo por su número o por palabras. Toda respuesta y toda búsqueda dicen para qué fecha se hicieron y qué régimen se aplicó. La respuesta es una lista corta de afirmaciones; debajo de cada una figuran la norma y el artículo que la respaldan, con el texto literal y un enlace para abrir el documento original. Cada cita dice qué peso tiene: el régimen específico va primero y es el que se aplica; el marco nacional figura como marco; los dictámenes y las recomendaciones, como criterio que acompaña; los considerandos, al final y como contexto. Si el régimen específico y el marco nacional tratan un punto de manera distinta, se muestran los dos textos con un aviso de cuál se aplica. Un artículo modificado se muestra junto con el texto de la norma que lo modificó; uno derogado a la fecha consultada aparece en la búsqueda marcado como derogado y no sostiene respuestas.

**Aviso cuando faltan modificatorias.** La Disposición 297/03 se carga con su texto de 2003, y las normas que la modificaron después se van sumando de a poco. Mientras falte alguna, toda respuesta o búsqueda que muestre un artículo de la 297/03 lleva un aviso que dice cuántas modificatorias faltan cargar y que puede haber cambios que el sistema no conoce. El aviso es un texto fijo del sistema; no lo redacta el modelo.

**Con qué piezas.** Todo se levanta con una sola orden: la base de datos, la aplicación que muestra la pantalla y tres copias de un mismo programa de inteligencia artificial, una por tarea (redactar, buscar por significado y puntuar la pertinencia). Las tres usan la placa de video de la notebook; según las estimaciones ocupan alrededor de la mitad de su memoria.

**Qué queda registrado.** Cada carga, validación, consulta, búsqueda e ingreso, con quién lo hizo, cuándo, para qué fecha de autorización, qué régimen se aplicó, sobre qué versión de la normativa, qué se encontró, qué se respondió y qué aviso se mostró. Con ese registro se puede explicar después por qué el sistema dijo lo que dijo.

**Cómo se sabe si responde bien.** Con unas 30 preguntas de respuesta conocida, aprobadas por un integrante de la Comisión. Cada pregunta lleva su fecha de autorización: hay preguntas para cada uno de los dos regímenes y al menos una que se repite con dos fechas, para comprobar que la respuesta cambia de régimen. Se exige: cita literal siempre, respuesta correcta en al menos 85 % de las preguntas que tienen respuesta, "no determinado" en al menos 90 % de las que no la tienen, y hasta 30 segundos por consulta.

**Qué falta comprobar.** Nada de esto se probó todavía en la notebook. Por eso la primera etapa no construye: comprueba que cada pieza funciona en este equipo y mide cuánta memoria usa. Para lo que podría fallar hay un plan B anotado. Los dos regímenes ya están en el repositorio (`corpus/normativa/`). Las fechas de entrada en vigencia ya no faltan: 1 de enero de 2023 para la Disposición 247/2022, informada por el responsable, y 14 de junio de 2003 para la 297/03. Las sigue escribiendo una persona al cargar cada norma; el sistema no las calcula. Faltan dos cosas que dependen de personas: las modificatorias de la 297/03, que se cargan de a poco; y los documentos de las otras categorías.

## Resumen del enfoque

Una aplicación Django con páginas armadas en el servidor (ADR-0005) sobre el Postgres con pgvector que ya existe. La carga lee cada documento con herramientas que transcriben y recortan sin redactar (pdfplumber, Tesseract, BeautifulSoup) y lo parte con reglas deterministas (ADR-0004); cada unidad es un recorte exacto del texto leído. La consulta combina tres caminos de búsqueda sobre Postgres, reordena con un reranker y arma la respuesta con un modelo local que solo señala unidades (ADR-0002 y ADR-0003); el texto de cada cita lo inserta el sistema desde la base. Cada consulta y cada búsqueda llevan una fecha de autorización del procedimiento; una función de la base devuelve lo que regía a esa fecha, y con eso se resuelve cuál de los dos regímenes se aplica (ADR-0006). Generación, embeddings y reranker se sirven con la misma imagen de `llama-server`, un contenedor por modelo, de modo que el camino de los documentos no tiene ninguna salida del equipo (P4) y hay una sola tecnología de IA que fijar, probar y mudar (P5, P10). Lo que hoy es estimación se mide en una primera etapa de comprobación del entorno, antes de construir encima.

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
- Los clientes de `evaluon/ai/` ofrecen cuatro operaciones: generar con esquema, convertir textos en vectores, puntuar una pregunta contra una lista de textos, y contar los tokens de un texto (ver "Conteo de tokens"). El resto del código no sabe qué servidor hay detrás. Las pruebas los reemplazan por dobles; las evals usan los servicios reales.
- Todo camino de búsqueda lee de `consultable_units(fecha)` (ver "Modelo de datos"), con la fecha de autorización que recibió la consulta. Nada consulta las tablas de unidades por fuera.

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
│   ├── norms/                    normas, documentos, lecturas, unidades, pasajes, relaciones, versiones, modificatorias sin cargar
│   │   ├── models.py  migrations/         tablas y SQL propio (extensiones, configuración de texto, `consultable_units`, `unit_changes`, `applicable_regimes`)
│   │   ├── reading/              un archivo por formato: pdf_text.py, ocr.py, web.py (ADR-0004)
│   │   ├── splitting/            texto canónico, reglas de partición, informe de lectura (ADR-0004)
│   │   ├── indexing.py           pasajes y vectores de una lectura
│   │   ├── services/             un archivo por operación: loading.py, validation.py, relations.py, versions.py, amendments.py, listing.py
│   │   ├── views.py  urls.py     entrega del documento original (REQ-002)
│   │   └── management/commands/  cargar_norma, releer_norma, listar_normas, ver_informe, validar_informe, registrar_relacion, registrar_version, registrar_modificatorias
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
│   ├── ai/                       clientes HTTP: generation.py, embeddings.py, reranker.py (los dos primeros también cuentan tokens)
│   ├── templates/                base, ingreso, consulta
│   └── static/                   una hoja de estilos y un script propios; nada externo
├── tests/
│   ├── conftest.py               usuarios de prueba; dobles de los tres clientes de IA
│   ├── accounts/  audit/  norms/  queries/
│   └── fixtures/                 documentos públicos chicos o sintéticos
├── evals/
│   ├── casos/                    un archivo por pregunta (EV-NNN.yaml)
│   └── corridas/                 una carpeta por corrida
├── corpus/normativa/             documentos públicos de trabajo: hoy, la Disp. 297/03 (página web) y la Disp. 247/2022 (cuerpo en página web y anexo en PDF)
├── corpus/normativa/referencias/ fichas y listados de la fuente; no son normas y no se cargan
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
| `reranker` | La misma imagen y compilación | Sirve `bge-reranker-v2-m3` (archivo GGUF FP16 de 1,16 GB). `/v1/rerank`. Arranca obligatoriamente con `--override-kv tokenizer.ggml.add_sep_token=bool:true`, que el archivo no trae (ADR-0003, adenda del 2026-10-02) | Estimado: entre 1,2 y 2 GB |
| `migrate` | Imagen propia de la aplicación | Corre `scripts/migrate_on_start.sh` y termina | No usa |
| `app` | Imagen propia de la aplicación | Pantalla (Gunicorn, un proceso con hilos, espera de 120 s) y comandos. Lectura de documentos y Tesseract en CPU | No usa |

**Cuenta de memoria de video.** Topes: 16 + 4 = 20 GB de 24, con 4 GB de margen. Con las estimaciones: 8,6 + 2 + 2 = 12,6 GB, con unos 11 GB libres. Ninguna de estas cifras está medida en este equipo, y no se sabe cuánta memoria de video usa Windows con la pantalla activa. La etapa 0 mide el total con los tres modelos cargados; si supera 20 GB, no se avanza sin revisar el reparto. `llama-server` no tiene un tope de memoria que se pueda imponer: los topes son un presupuesto que se controla midiendo.

Detalles comunes:

- Los tres servicios de IA montan `models/` en modo de solo lectura y arrancan con `--offline`. Cada uno expone `/health`; `app` espera a que los tres y `db` estén listos.
- `scripts/fetch_models.sh` descarga los tres archivos y compara su huella SHA-256 con `scripts/models.sha256`. Es el único paso que necesita internet y se hace una vez por equipo; para mudar el sistema también se puede copiar la carpeta `models/`.
- La imagen de la aplicación no lleva PyTorch ni usa la GPU. `app` monta `corpus/` en modo de solo lectura, para cargar documentos desde ahí, y `evals/`, para leer los casos y guardar las corridas.
- No hay servidor web intermedio, cola de tareas ni caché (P10).

**Plan B para embeddings y reranker.** Si la etapa 0 muestra que `bge-m3` o `bge-reranker-v2-m3` no cargan en `llama-server` o no reproducen los valores publicados por sus autores, los servicios `embeddings` y `reranker` pasan a usar Text Embeddings Inference (imagen `120-1.9` para la serie RTX 50, que su documentación marca como experimental). Los nombres de los servicios y el resto del sistema no cambian: solo la imagen y los dos clientes de `evaluon/ai/`. Si tampoco funcionara, queda el contenedor propio con `sentence-transformers` que describe el ADR-0003.

La etapa 0 no necesitó el plan B (`entorno.md`, T-003). El reranker reprodujo los valores de su ficha (5,28 y −8,18 frente a 5,26 y −8,19) solo después de forzar `tokenizer.ggml.add_sep_token`, un dato que el archivo GGUF no trae y sin el cual los pares se arman con un separador de menos. El responsable decidió que es configuración del mismo modelo, no el plan B. Consecuencias, en la adenda del ADR-0003: el parámetro es obligatorio; el umbral de abstención se calibra con él y quitarlo exige recalibrar; un cambio de compilación o de archivo del reranker repite la prueba de los pares de la ficha.

**Migraciones y respaldo.** El servicio `migrate` aplica las migraciones solo cuando la base está vacía; ahí no hay nada que respaldar y un equipo limpio llega al sistema funcionando con una orden (P5). Si la base ya tiene datos, `migrate` solo comprueba (`manage.py migrate --check`): si hay cambios de esquema pendientes termina con error, muestra el procedimiento y `app` no arranca. El procedimiento para una base con datos, que va al runbook, es:

1. Detener `app`.
2. Respaldar: `docker compose exec db pg_dump -Fc evaluon`, guardado en `backups/` con fecha.
3. Aplicar: `docker compose run --rm app python manage.py migrate`.
4. Levantar todo otra vez.

Así nunca se migra una base con datos sin respaldo previo. Cada migración con SQL propio lleva su reversa.

## Modelo de datos

Los nombres de tablas y campos van en inglés. Los valores que nombran un concepto jurídico (tipos de unidad, categorías, tipos de relación) van en español sin tildes, tal como los definió el ADR-0004; el tipo de unidad `clausula` lo suma este plan (ver "Texto normativo sin número de artículo"). Los estados propios del sistema van en inglés.

Cuatro niveles: una **norma** tiene uno o más **documentos** (cada archivo cargado), cada documento tiene una o más **lecturas** (cada vez que se leyó y partió), y cada lectura tiene sus **unidades**. Cada documento es una parte de la norma: el cuerpo o un anexo (ver "Una norma en más de un archivo"). Las unidades y las lecturas no se modifican ni se borran: una relectura crea una lectura nueva. Por eso un registro de consulta puede apuntar a una unidad y encontrarla siempre igual (P6, P8).

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
| `event_type` | `load`, `reread`, `validation`, `relation`, `version`, `pending_amendment`, `query`, `search`, `login`, `login_failed`, `rejected`, `user_created` |
| `outcome` | `ok`, `rejected` o `failed` |
| `channel` | `screen`, `command` o `eval` |
| `user` | Usuario que actuó; vacío en un ingreso fallido o en un alta hecha por quien administra el equipo |
| `username` | Nombre tal como se escribió; sirve cuando no hay usuario |
| `corpus_version` | Número de versión de la normativa vigente en ese momento. En el hecho `query`, la versión con que se hizo la búsqueda, tomada en el mismo momento que la recuperación, aunque se cree otra versión mientras la consulta sigue (decisión del responsable del 2026-10-03, P6 y P8) |
| `detail` | Datos propios del hecho, en JSON (ver "Registro de auditoría") |

### norms

**`norms_norm`**: una fila por norma (REQ-001, REQ-017).

| Campo | Contenido |
|---|---|
| `id` | Identificación |
| `category` | `regimen_especifico`, `otra_normativa`, `marco_nacional`, `dictamen_legal` o `recomendacion_auditoria`. Obligatorio |
| `norm_type`, `number`, `year`, `issuer` | Tipo, número, año y organismo emisor, normalizados. Únicos en conjunto: es lo que identifica "la misma norma" (REQ-011) |
| `title` | Título |
| `citation` | Nombre con que se cita la norma, tal como lo escribe la persona al cargarla: "Disposición AFIP 297/03", "Disposición AFIP 247/2022". Obligatorio. Lo usan la pantalla, el encabezado de los pasajes, el régimen aplicado, los avisos de modificatorias y las evals. Decisión del responsable del 2026-10-03: ninguna regla automática acierta siempre con la forma del año (T-055) |
| `general_regime` | Verdadero en la norma que aprueba un régimen general de contrataciones: hoy, la Disposición 297/03 y la 247/2022. Falso en sus modificatorias y en todo lo demás. Solo puede ser verdadero con categoría `regimen_especifico`. De acá sale "qué régimen aplicó" (REQ-020) |
| `created_at`, `created_by` | Alta |

**`norms_document`**: una fila por archivo cargado.

| Campo | Contenido |
|---|---|
| `id`, `norm` | Identificación y norma a la que pertenece |
| `part` | Qué parte de la norma es este archivo: `cuerpo` (valor por omisión) o la clave de un anexo (`anexo`, `anexo-i`, `anexo-ii`). Lo indica la persona al cargar |
| `publication_date`, `effective_from`, `source` | Fecha de publicación, fecha de vigencia y fuente de donde se obtuvo (REQ-001). `effective_from` es desde cuándo rige el texto y lo escribe la persona: el sistema no lo calcula. Para la Disposición 247/2022 es su entrada en vigencia, el 2023-01-01, en sus dos documentos; para la 297/03, el 2003-06-14 (ADR-0006, "Datos registrados") |
| `effective_to` | Hasta cuándo rigió este texto; vacío mientras rige. Se completa cuando se registra una versión posterior de la misma parte de la norma. Una derogación no lo completa: queda como relación |
| `version_number` | Número de versión de esa parte de la norma; vacío hasta que el documento se registra como versión |
| `in_use` | Si es el documento que se usa para consultar esa versión. A lo sumo uno por norma, parte y versión |
| `same_norm_confirmation` | Qué confirmó la persona cuando el sistema avisó "misma norma": `other_file` o `new_version`; vacío si fue la primera carga de esa parte |
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
| `unit_type` | `articulo`, `inciso`, `anexo`, `considerando`, `clausula`, `punto` o `parrafo` |
| `number` | Número normalizado: `14`, `14 bis`, `b`, `I`. Por orden, si el documento no trae número. Vacío en una unidad `clausula`: no se le inventa un número |
| `label` | Etiqueta como figura en el documento: "ARTICULO 14.- GARANTIAS" |
| `key` | Clave estable, única dentro de la lectura y, entre los documentos en uso, única dentro de la norma (ver "Identificación de unidades") |
| `path` | Ruta legible: "Anexo › Título II › Capítulo V › Artículo 50 › Inciso a" |
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
| `header` | Encabezado de contexto: norma y ruta ("Disposición AFIP 247/2022, Anexo, artículo 50") |
| `text` | Texto del tramo |
| `tsv` | Columna para la búsqueda por palabras, calculada por la base con `search_document` (ver "Búsqueda por palabras: tildes, singular y plural"); índice GIN |
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

Las relaciones guardan la clave de la unidad y no su identificación interna, porque valen para la norma y no para una lectura en particular: si el documento se vuelve a leer, siguen apuntando al mismo artículo. Al registrar una relación se comprueba que la clave exista en los documentos en uso de la norma, en cualquiera de sus partes; al validar una lectura nueva, la validación avisa (antes de confirmar y en el hecho `validation`, no en el informe guardado, cuya huella no cambia; aclaración al implementar T-027) si alguna relación quedó sin unidad.

`effective_date` es la fecha desde la que rige el cambio y la escribe la persona. La abrogación de la Disposición 297/03 se registra así: tipo `deroga`, norma de origen la 247/2022 con `source_unit_key` `art-2`, norma alcanzada la 297/03 entera, y `effective_date` igual a la fecha de entrada en vigencia de la 247/2022, que es el 2023-01-01.

**`norms_pending_amendment`**: modificatorias de una norma que todavía no están cargadas (REQ-021). Una fila por modificatoria.

| Campo | Contenido |
|---|---|
| `id` | Identificación |
| `target_norm` | La norma que tiene la modificatoria sin cargar (hoy, la Disposición 297/03) |
| `norm_type`, `number`, `year`, `issuer` | Tipo, número, año y organismo emisor de la modificatoria, normalizados igual que en `norms_norm`. Únicos en conjunto dentro de `target_norm` |
| `source_ref` | Referencia en la fuente: la dirección de la ficha de la modificatoria en Infoleg |
| `registered_at`, `registered_by` | Quién la anotó y cuándo |
| `loaded_norm` | La norma cargada que le corresponde; vacío mientras la modificatoria está sin cargar |

No guarda fecha, tipo de relación ni artículos alcanzados: eso se sabe recién al leer la modificatoria, y entonces se registra como relación. Cómo se anota y cómo pasa a cargada está en "Modificatorias sin cargar".

**`norms_corpus_version`**: versión de la normativa (REQ-012, P8).

| Campo | Contenido |
|---|---|
| `id` | Número de versión, creciente |
| `created_at`, `event` | Momento y hecho que la originó (`audit_event`) |

Se crea una versión nueva cada vez que cambia lo que se puede consultar o lo que se avisa: al validar una lectura, al registrar una relación, al registrar una versión de una norma y al anotar modificatorias sin cargar. Cada consulta guarda el número vigente. Como las unidades no cambian y cada cambio tiene fecha, con el número de versión y la fecha de autorización se reconstruye qué era consultable.

### queries

**`queries_query`**: detalle de cada consulta en lenguaje natural. Se inserta una vez, al terminar.

| Campo | Contenido |
|---|---|
| `id`, `event` | Identificación y fila correspondiente en `audit_event` |
| `user`, `asked_at` | Quién y cuándo |
| `question`, `reference_date`, `corpus_version` | Pregunta, fecha de autorización del procedimiento para la que se consultó (REQ-020) y versión de la normativa con que se hizo la búsqueda, igual a la de su hecho |
| `status`, `reason` | Resultado: `grounded`, `undetermined` o `error`, y su motivo |
| `parameters` | Copia de todos los parámetros usados (JSON) |
| `candidates` | Cada candidato con su camino de entrada y su puntaje (JSON) |
| `selected` | Unidades enviadas al modelo, agregadas por relación y dejadas afuera por espacio (JSON) |
| `max_score` | Puntaje más alto del reranker |
| `prompt_version`, `request` | Versión de las instrucciones y pedido completo enviado al motor |
| `raw_output` | Lo que devolvió el modelo, sin tocar |
| `result` | Respuesta validada: fecha, régimen aplicado, afirmaciones, unidades citadas por `id`, marcas y avisos (JSON; ver "Forma de la respuesta") |
| `anomalies` | Fallas de formato o de cita detectadas al validar (JSON) |
| `timings` | Tiempo de cada etapa y total (JSON) |

### Migraciones con SQL propio

En `norms/migrations/`, cada una con su reversa: extensiones `vector` y `unaccent`; funciones de búsqueda por palabras `search_normalize`, `search_document` y `search_query` (ver la sección siguiente); columna `tsv` con su índice GIN; y las funciones `consultable_units`, `unit_changes` y `applicable_regimes`.

### Búsqueda por palabras: tildes, singular y plural

Aprobada por el responsable el 2026-10-02 (ADR-0007). Reemplaza la configuración `spanish_unaccent` del plan aprobado, que quitaba los acentos antes de reducir las palabras a su raíz.

**Por qué cambia.** La etapa 0 midió que, quitando los acentos primero, "licitación" queda como `licitacion` y "licitaciones" como `licit`: buscar "licitacion" o "licitación" no encuentra un pasaje que solo dice "licitaciones". Pasa con todas las palabras terminadas en "-ación" y "-ución" (adjudicación, contratación, resolución). El lematizador de español de Postgres 17 reconoce "-ación" con tilde y no sin ella (`entorno.md`, T-004, sección 5; ADR-0007).

**Definición.** El texto del pasaje y el de la consulta pasan por la misma normalización y después por la configuración `spanish` de Postgres. Tres funciones SQL, en la migración de T-009:

| Función | Qué hace |
|---|---|
| `search_normalize(texto)` | Quita los acentos con `unaccent`, salvo la "ñ", que se conserva (ADR-0007, adenda "La eñe"), y vuelve a poner la tilde en las palabras terminadas en "acion" o "ucion", sin distinguir mayúsculas. En español esas terminaciones siempre llevan tilde |
| `search_document(texto)` | `to_tsvector('spanish', search_normalize(texto))`. Calcula `tsv` |
| `search_query(texto)` | `websearch_to_tsquery('spanish', search_normalize(texto))`. La usan el camino por palabras y la búsqueda directa |

Se declaran inmutables, con `unaccent` llamado con su diccionario nombrado con esquema, para que `tsv` pueda ser una columna calculada por la base. Nada fuera de ellas arma `tsv` ni una consulta de texto.

**Qué se espera.** Con o sin tilde y en mayúsculas o minúsculas, "licitación", "licitacion", "LICITACIÓN" y "licitaciones" quedan como `licit`; "adjudicación" y "adjudicaciones", como `adjud`; "contratación" y "contrataciones", como `contrat`; "artículo", "artículos" y "articulo", como `articul`; "garantía", "garantías" y "garantia", como `garanti`. "297/03" y "247/2022" quedan enteros, como en T-004. Es una deducción de lo medido en T-004, no una medición: la comprueba T-009.

**Qué se pierde.** Una regla propia de dos terminaciones que mantener; las palabras que solo se distinguen por la tilde se confunden ("público" y "publico"), igual que con la definición anterior. Al actualizar Postgres de versión mayor hay que recalcular `tsv` y repetir la prueba, porque el lematizador puede cambiar. Alternativas y costos: ADR-0007.

### Identificación de unidades

"Artículo 1" no es único dentro de una norma: la Disposición 297/03 tiene uno en la disposición y otro en el Anexo I, en el mismo archivo; la 247/2022 tiene uno en el cuerpo y otro en el anexo, en archivos distintos. Cada unidad tiene tres identificadores, con usos distintos.

| Identificador | Ejemplo | Para qué se usa |
|---|---|---|
| `id` | 4812 | Registro de consultas y respuesta guardada. No cambia nunca |
| `key` | `art-1`, `anexo-i/art-1`, `anexo/art-50`, `anexo-i/art-14/inc-1/inc-a`, `considerando-3`, `anexo/clausula-transitoria`, `punto-2.3`, `parrafo-12` | Relaciones, comandos y conjunto de preguntas. Se arma con la cadena de unidades que la contienen, en minúsculas y sin tildes. Los títulos y capítulos no entran, porque no son unidades |
| `path` | "Anexo › Título II › Capítulo V › Artículo 50 › Inciso a" | Lo que se muestra en la cita y en la búsqueda, precedido por el nombre de la norma. Incluye títulos y capítulos |

La búsqueda por norma y número de artículo (REQ-010) devuelve todas las unidades de tipo `articulo` con ese número en los documentos en uso de la norma, en todas sus partes, cada una con su `path`. Para "Disposición 297/03, artículo 1" son dos resultados, y para "Disposición 247/2022, artículo 1" también; la ruta dice cuál es cuál. No se elige uno en silencio.

### Una norma en más de un archivo

La Disposición 247/2022 está publicada en dos archivos: el cuerpo, con el visto, los considerandos y sus cinco artículos (`disp-afip-247-2022-original.htm`), y el anexo, con el régimen completo (`disp-afip-247-2022-anexo.pdf`). Los dos se cargan bajo la misma norma, cada uno como una parte:

- **Al cargar se indica la parte** con `--parte`: `cuerpo`, que es el valor por omisión, o la clave del anexo (`anexo`, `anexo-i`). El dato queda en `norms_document.part`.
- **Las claves no chocan.** En un documento cargado como anexo, todas las unidades cuelgan de una unidad raíz de tipo `anexo` cuya clave es la parte. El artículo 1 del anexo queda como `anexo/art-1` y el del cuerpo como `art-1`: las mismas claves que tendría la norma si viniera en un solo archivo, como pasa con la 297/03. Un encabezado "ANEXO" dentro de un documento cargado como esa misma parte no abre otro contenedor.
- **Cada parte tiene su documento en uso.** El primer documento validado de cada parte queda como versión 1 y en uso. Las unidades consultables de una norma son las de todas sus partes en uso.
- **Control al validar.** Si una clave de la lectura nueva ya existe en otra parte en uso de la misma norma, no se valida y se informa cuál. Puede pasar si el archivo del cuerpo trae adentro un anexo con la misma clave que una parte cargada aparte.
- **Los datos de la norma se escriben una vez.** Categoría, título y `general_regime` quedan con la primera parte. Al cargar otra parte, si los datos indicados difieren de los registrados, el comando la rechaza y muestra los registrados. Si la fecha de vigencia difiere de la de otra parte en uso, el comando lo avisa.
- **Duplicados (REQ-011).** "Misma norma" pasa a significar mismo tipo, número, año, organismo emisor y parte. Cargar el anexo de una norma que ya tiene cargado el cuerpo es sumar una parte: el comando lo informa y no pide confirmación, porque la persona ya declaró con `--parte` qué está cargando. Cargar un segundo archivo de una parte ya cargada sigue siendo "misma norma en otro archivo" y pide confirmación expresa. La comprobación de mismo texto en otro archivo se hace contra todos los documentos, sin mirar la parte.

Se descartaron otras dos formas. Cargar el anexo como una norma aparte, vinculada con una relación, mostraría las citas del régimen bajo otro nombre de norma. Unir los dos archivos en uno antes de cargar dejaría guardado un original que nadie publicó (REQ-002).

### Texto normativo sin número de artículo

Una norma puede traer texto dispositivo con título propio y sin número. El anexo de la Disposición 247/2022 termina con una cláusula transitoria, después del artículo 99. Ese texto se guarda como unidad citable propia, con el nombre que le da el documento (REQ-003; decisión del responsable del 2026-10-02). No se le asigna un número, porque el documento no lo trae, y no se usa el tipo `parrafo`, que queda para dictámenes y recomendaciones.

| Dato | Regla | En el anexo de la 247/2022 |
|---|---|---|
| `unit_type` | `clausula` | `clausula` |
| Nombre | La forma reconocida en el encabezado, con mayúscula inicial. Lo que sigue en la misma línea es su epígrafe, como en un artículo | "Cláusula transitoria" |
| `number` | Vacío | Vacío |
| `label` | El encabezado completo, como figura en el documento | "CLÁUSULA TRANSITORIA REGISTRO DE PROVEEDORES" |
| `key` | La clave de su contenedor y el nombre en minúsculas, sin tildes y con guiones en lugar de espacios. Si el mismo contenedor trae otra con el mismo nombre, desde la segunda se agrega su número de orden (`clausula-transitoria-2`) | `anexo/clausula-transitoria` |
| `path` | El contenedor y el nombre. No lleva título ni capítulo: el encabezado cierra los que estaban abiertos | "Anexo › Cláusula transitoria" |
| `order` | El del documento | Después de `anexo/art-99` |
| `header` de sus pasajes | Norma y ruta, como en las demás unidades | "Disposición AFIP 247/2022, Anexo, Cláusula transitoria" |

- **Cómo la reconoce la partición.** Por su encabezado: una línea propia, escrita en mayúsculas, que empieza con una de las formas de una lista de nombres de texto sin número. La lista arranca con la única forma que trae el corpus, `CLÁUSULA TRANSITORIA`, con o sin tilde y con o sin epígrafe a continuación. El encabezado cierra el artículo anterior y los títulos y capítulos abiertos. La unidad va desde su encabezado hasta el siguiente encabezado de unidad, de título o de anexo, o hasta el cierre y la firma, que no se le suman. No entra en el control de secuencia de los artículos: si después viene un artículo, sigue la numeración de su contenedor. Las mismas palabras en medio de un párrafo no abren una unidad.
- **Otras normas.** El tipo, la clave, la etiqueta y la ruta valen para cualquier texto normativo con título propio y sin número, por ejemplo una disposición transitoria. Cada forma nueva se suma a la lista como una regla más, con su caso de prueba. Un párrafo propio que coincide con un encabezado reconocido (título, capítulo, cláusula u otra forma de la lista) cierra el artículo abierto, y lo que sigue hasta la próxima unidad queda sin ubicar y a la vista en el informe: así un título nunca termina dentro de la cita de un artículo (decisión del responsable del 2026-10-03, que reemplaza el límite anterior). Un párrafo en mayúsculas que no es un encabezado reconocido no corta: queda dentro del artículo, y el informe lo señala para que lo revise la persona que valida (REQ-005); si es una forma nueva, se agrega a la lista y se relee con `releer_norma`.
- **Cómo se usa.** Es una unidad base: se indexa, se recupera y sostiene respuestas igual que un artículo, con la categoría de su norma y dentro del mismo cupo. Admite relaciones por su clave. Como no tiene número, la búsqueda por norma y número de artículo no la devuelve; se la encuentra por palabras.
- **Cómo se muestra en la cita.** Con la norma y su ruta, "Disposición AFIP 247/2022" y "Anexo › Cláusula transitoria", y con el mismo papel que un artículo de su categoría. Al desplegarla se ve su texto literal, que empieza con el encabezado tal como figura en el documento.

La tabla "Cómo se parte" del ADR-0004 no tiene esta fila ni su lista de tipos tiene `clausula`. Este plan no modifica ese ADR; se informa al Coordinador (ver "Actualización por ADR-0006").

### Unidades base, incisos y pasajes

El ADR-0004 guarda el artículo con el texto completo de sus incisos y además cada inciso como unidad hija. Para que el mismo texto no aparezca dos veces:

- **Unidad base** es toda unidad que no es `inciso`: `articulo`, `considerando`, `clausula`, `punto`, `parrafo` y `anexo`. Un `anexo` que contiene artículos tiene como texto propio solo su encabezado y lo que haya antes del primer artículo; un anexo sin artículos tiene todo su texto.
- **Se indexa para buscar** solo el texto de las unidades base, partido en pasajes. Una unidad corta es un único pasaje; una larga se parte en pasajes de hasta 800 tokens con solape (valor inicial), cortando en los límites de inciso cuando los hay. Los incisos no generan pasajes.
- **Se cita en una respuesta** siempre la unidad base. El modelo recibe unidades base y solo puede señalar unidades base. Una misma unidad base entra una sola vez en una consulta.
- **Los incisos sirven** para registrar relaciones con precisión ("modifica el inciso b del artículo 14") y para la búsqueda directa cuando se pide un inciso. Si una relación alcanza a un inciso, lo que acompaña en la respuesta es el artículo que lo contiene, con la aclaración de qué inciso cambió.
- El control de cobertura del informe de lectura cuenta cada carácter una vez, en su unidad base.
- Estados de página en el informe (aclaración al implementar T-025, decisión del Coordinador, 2026-10-03): además de legible, dudosa, ilegible y en blanco del ADR-0004, el informe distingue "sin texto" (página sin capa de texto ni reconocimiento, por ejemplo la que solo trae la firma digital) y "casi sin texto" (reconocida con muy pocas palabras legibles), para que quien valida no confunda una página vacía con una que no se pudo leer. Los dos van a "Requiere atención".

### Unidades consultables a una fecha

La fecha es la de autorización del procedimiento que indicó la persona (REQ-020; ver "Fecha de autorización y régimen aplicado"). Todo lo que sigue se evalúa contra esa fecha, nunca contra la del día.

`consultable_units(fecha)` es una función SQL: el único lugar por el que pasan la consulta y la búsqueda. Devuelve las unidades que cumplen todo esto:

1. Su lectura está en estado `validated` (REQ-005).
2. Su documento está `in_use` y la fecha cae dentro de su vigencia: `effective_from` ≤ fecha, y `effective_to` vacío o posterior. Vale para cada parte de la norma por separado.

Para cada unidad devuelve además `repealed`: verdadero si hay una relación `deroga` con `effective_date` ≤ fecha que alcanza a la norma entera, a la unidad o a una unidad que la contiene (se resuelve por prefijo de `key`). Una derogación con fecha posterior a la consultada no cuenta.

`unit_changes(fecha)` devuelve, para cada unidad, las relaciones `modifica` o `deroga` con `effective_date` ≤ fecha que alcanzan a la unidad o a una unidad contenida en ella, con la unidad de la norma de origen que trae el cambio.

`applicable_regimes(fecha)` devuelve las normas con `general_regime` verdadero que tienen al menos una unidad en `consultable_units(fecha)` con `repealed` falso. Es el régimen que se aplica a esa fecha y lo que la pantalla muestra como "Régimen aplicado".

- La consulta en lenguaje natural usa las unidades con `repealed` falso: una unidad derogada a la fecha consultada no sostiene una respuesta.
- La búsqueda directa usa todas, y muestra las derogadas a esa fecha marcadas, con la norma que las derogó y desde cuándo.
- Las pruebas de REQ-007 y de REQ-020 llaman a estas funciones con distintas fechas.

**Cómo quedan los dos regímenes.** Con los datos que registra el responsable de normativa (la fecha de vigencia de cada documento al cargarlo y la fecha de la relación `deroga`), y llamando V a la fecha de entrada en vigencia de la 247/2022, que es el 2023-01-01 (la 297/03 rige desde el 2003-06-14):

| Fecha consultada | Disposición 297/03 | Disposición 247/2022 | `applicable_regimes` |
|---|---|---|---|
| Anterior a V | Consultable y con `repealed` falso: sostiene respuestas, aunque hoy esté abrogada | No aparece: `effective_from` es posterior a la fecha | 297/03 |
| V o posterior | Consultable y con `repealed` verdadero: no sostiene respuestas; en la búsqueda sale marcada como derogada desde V por la 247/2022 | Consultable: sostiene respuestas | 247/2022 |
| Anterior a la vigencia de la 297/03 | No aparece | No aparece | Ninguno |

La regla "una unidad derogada no sostiene respuestas" no cambia: lo que se precisa es que derogada quiere decir derogada a la fecha consultada. Así la 297/03 responde para un procedimiento autorizado antes de V, que es lo que disponen los artículos 3 y 4 de la 247/2022.

V se escribe en tres lugares: `effective_from` del cuerpo de la 247/2022, `effective_from` de su anexo y `effective_date` de la relación `deroga`. Los tres tienen que llevar la misma fecha. Si la relación tuviera una fecha anterior, habría días sin régimen; si tuviera una posterior, días con dos. El sistema no lo corrige solo: muestra lo que encuentra (ningún régimen, o los dos) y la carga del corpus lo comprueba consultando el día anterior a V y el día V (ver "Riesgos").

### Versiones de una norma

Una norma cambia de dos maneras, y las dos quedan registradas con fecha:

- **Otra norma la modifica o deroga.** Se registra como relación. El texto original no se toca; a partir de `effective_date`, la unidad se muestra junto con el texto literal de la que la modifica (REQ-007).
- **Se publica otro texto de la misma norma** (por ejemplo, una rectificación). Se carga como documento nuevo de la misma norma y de la misma parte y, una vez validado, `registrar_version` lo deja como versión siguiente de esa parte: le asigna `version_number`, lo marca `in_use` y cierra la vigencia de la versión anterior.

El primer documento validado de cada parte de una norma queda como versión 1 y en uso sin más pasos. Un segundo documento de la misma norma y la misma parte (otro formato u otra versión) se puede cargar y validar, pero no entra en las consultas hasta que `registrar_version` diga qué es: versión nueva, o reemplazo del archivo en uso de una versión existente. Así la misma norma cargada en tres formatos (prueba de REQ-015) no aparece tres veces en una respuesta. El cuerpo y el anexo de una norma no son versiones una de la otra: son partes, y las dos están en uso a la vez.

### Modificatorias sin cargar

La Disposición 297/03 se carga con su texto de 2003. Infoleg lista 33 normas que la modificaron o complementaron; hasta que estén cargadas, el sistema no conoce esos cambios y tiene que avisarlo (REQ-021).

**Qué se anota.** De cada modificatoria, lo mínimo para identificarla: tipo, número, año, organismo emisor y su referencia en la fuente (`norms_pending_amendment`). El organismo hace falta porque en el listado hay disposiciones de diez dependencias distintas de la AFIP, y dos dependencias pueden tener una disposición con el mismo número y año.

**Cómo se anota.** Con el comando `registrar_modificatorias`, que indica la norma alcanzada y recibe la lista de dos maneras:

- En lote, con `--archivo`: un CSV con las columnas `tipo`, `numero`, `anio`, `organismo` y `referencia`, un renglón por modificatoria. Para la 297/03 el archivo se prepara a partir de `corpus/normativa/referencias/disp-afip-297-2003-modificada-por-infoleg.htm` y se guarda como `corpus/normativa/referencias/disp-afip-297-2003-modificatorias.csv`, anotado en el manifiesto. Lo preparan el Coordinador y el responsable; el sistema no lee la página de Infoleg.
- De a una, con `--tipo`, `--numero`, `--anio`, `--organismo` y `--referencia`.

Una modificatoria ya anotada no se anota otra vez: el comando lo informa y sigue con las demás. Un renglón incompleto se rechaza sin anotar ninguno del archivo. Al terminar muestra cuántas anotó, cuántas ya estaban y cuántas quedan sin cargar.

**Cómo pasa de sin cargar a cargada.** No hay un paso aparte: ocurre al hacer el trabajo normal. Una modificatoria queda cargada cuando se cumplen las tres cosas: la norma está cargada, su lectura está validada y en uso, y una persona registró con `registrar_relacion` al menos una relación de esa norma hacia la norma alcanzada. En ese momento el sistema completa `loaded_norm` y lo informa, junto con cuántas quedan. Corresponde con el criterio de la spec: "cuando todas quedan cargadas y registradas".

La comprobación la hace una sola función, en `norms/services/amendments.py`, que se llama al final de `registrar_relacion` y al final de `registrar_modificatorias`; así el orden en que se hagan las cosas no importa. La coincidencia entre la norma cargada y la modificatoria anotada se busca por tipo, número y año; el organismo solo desempata si hay más de una con esos tres datos. Si una relación viene de una norma que no figura entre las anotadas, el comando lo dice y no cambia nada.

La Disposición 247/2022 figura en el listado de Infoleg. Se anota como las demás y queda cargada cuando se registra su relación `deroga`. Para la 297/03, entonces, quedan 32 sin cargar.

**Qué cuenta el aviso.** La cantidad de filas de `norms_pending_amendment` de esa norma con `loaded_norm` vacío. No se filtra por la fecha consultada: de una modificatoria sin cargar no se conoce desde cuándo rige. Cómo llega el aviso a la respuesta, a la búsqueda y a la pantalla está en "Aviso de modificatorias sin cargar".

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

1. `cargar_norma` recibe el archivo, los datos de REQ-001, la categoría, la parte (`--parte`; por omisión, `cuerpo`) y, si la norma aprueba un régimen general, `--regimen-general`. Sin categoría no incorpora y pide el dato (REQ-017). La fecha de vigencia la escribe la persona.
2. Duplicados (REQ-011), en este orden:
    - Misma huella de archivo: avisa y no incorpora.
    - Mismo texto canónico en otro archivo, o mismos tipo, número, año, organismo emisor y parte: avisa "misma norma" y solo incorpora con confirmación expresa, en la que la persona indica si es otro archivo de lo mismo o una versión nueva.
    - Mismos tipo, número, año y organismo emisor, y una parte que la norma todavía no tiene: informa que se suma como parte de la norma ya incorporada, y la incorpora (ver "Una norma en más de un archivo").
3. Lectura por formato y partición con reglas (ADR-0004). Todo en CPU, dentro de `app`, sin usar los servicios de IA. La partición recibe la parte, para colgar las unidades de un anexo bajo su unidad raíz.
4. Se guardan el original, la lectura, el texto canónico, las unidades y el informe. La lectura queda `pending`.
5. `ver_informe` muestra el informe en texto, con la lista de unidades y sus claves. `validar_informe` pide confirmación; al validar, calcula pasajes y vectores (necesita el servicio `embeddings`; si no responde, no valida y lo dice), pasa la lectura a `validated` y crea una versión nueva de la normativa.
6. `releer_norma` crea una lectura nueva de un documento ya cargado, sin volver a pedir el archivo. Es el camino cuando se corrige una regla de partición: la lectura nueva pasa otra vez por informe y validación, y al validarse deja a la anterior como `superseded`.
7. `registrar_modificatorias` anota las modificatorias de una norma que todavía no están cargadas (ver "Modificatorias sin cargar"). No lee ni parte ningún documento.

Metadatos de cada unidad: los de `norms_unit`. Metadatos de cada pasaje: los de `norms_passage`.

### Fecha de autorización y régimen aplicado (REQ-020)

**De dónde sale la fecha.** La indica la persona en la pantalla, en el campo "Fecha de autorización del procedimiento", que está en el formulario de la pregunta y en el de búsqueda. El campo viene con la fecha del día (hora de Buenos Aires). Cuando la página muestra un resultado guardado, los dos campos traen la fecha de ese resultado, para no tener que escribirla de nuevo. En las evals, la fecha viene en cada caso y no tiene valor por omisión.

**Cómo se valida.** En el formulario y otra vez en la función de negocio, porque es el único camino para ejecutar una consulta:

| Situación | Qué pasa |
|---|---|
| El campo llega vacío | Se usa la fecha del día |
| No es una fecha | El formulario lo marca y no se consulta |
| Fecha posterior al día | El formulario la rechaza con el texto "La fecha de autorización no puede ser posterior a hoy" y no se consulta. El sistema no puede saber qué normas van a regir |
| Fecha anterior a todo régimen cargado | Se acepta. `applicable_regimes(fecha)` no devuelve nada: la consulta termina en "no determinado" con el motivo `no_regime_at_date`, sin buscar ni llamar al modelo. La búsqueda directa se ejecuta igual y muestra lo que haya a esa fecha |

Un formulario rechazado no es una consulta y no deja registro.

**Qué régimen aplicó.** Antes de buscar, la función de negocio llama a `applicable_regimes(fecha)`. El resultado lo calcula el código, no el modelo, y se muestra como una línea de texto fijo en los tres bloques de la pantalla y arriba de los resultados de una búsqueda:

- Con un régimen: "Procedimiento autorizado el 15/03/2021 · Régimen aplicado: Disposición AFIP 297/03".
- Sin régimen: "Procedimiento autorizado el 10/01/2001 · Para esa fecha no hay un régimen específico cargado en el sistema".
- Con más de uno, que solo puede pasar si las fechas del corpus están mal registradas: se nombran todos.

**Qué se guarda.** La fecha en `queries_query.reference_date`; la fecha y el régimen aplicado, dentro de `result`. En una búsqueda, la fecha y el régimen van en el detalle del hecho `search`. Como la página se arma desde lo guardado, una consulta vieja se sigue mostrando con la fecha y el régimen con que se hizo.

### Recuperación

Entrada: la pregunta y la fecha de autorización. Los tres caminos leen de `consultable_units(fecha)` con `repealed` falso.

| Camino | Qué hace | Cuántos |
|---|---|---|
| Por significado | Vector de la pregunta contra los vectores de los pasajes, distancia coseno, búsqueda exacta | 30 pasajes |
| Por palabras | Búsqueda de texto de Postgres: `tsv` contra `search_query`, palabras unidas por "o" | 30 pasajes |
| Por referencia exacta | Si la pregunta nombra una norma o un artículo ("art. 5 inc. b", "Disposición 297/03", "Disposición 247/2022"), trae esas unidades por sus datos, siempre dentro de lo consultable a la fecha. Si nombra un inciso, entra el artículo que lo contiene | Las que coincidan |

Se unen sin repetir (unos 65 pasajes como mucho). No hay fórmula de fusión: el orden lo pone el reranker.

Aclaraciones al implementar T-032 (decisión del Coordinador, 2026-10-03):

- Una norma nombrada sin artículo no trae unidades por este camino: traer la norma entera superaría el tope de unos 65 pasajes. La norma nombrada filtra los artículos nombrados (por número y año; el año de dos cifras se compara con los dos últimos dígitos; el tipo de norma no filtra). Si se nombran varias normas y varios artículos, se combinan todos con todos.
- "Artículo N" sin norma trae el artículo N de todo lo consultable y no derogado a la fecha, no solo del régimen aplicado.
- Sin reranker (configuración "combinada sin reranker" de la comparación quitando piezas) no hay puntajes ni umbral: todas las unidades de la unión pasan, en el orden de la unión. En esa configuración la medida "unidad correcta entre las seleccionadas" coincide con "entre los candidatos".

Aclaraciones al implementar T-033 (decisión del Coordinador, 2026-10-03):

- Si una unidad no entra en el espacio, se anota como fuera por espacio y se prueba con la siguiente en el orden de prioridad, que puede ser más chica: no se corta en la primera que no entra.
- El espacio se cuenta sobre el bloque de cada unidad tal como lo arma `answering` (encabezado, texto o tramos, y líneas de cambio), con el alias del ancho máximo. El margen de la plantilla cubre solo la plantilla de conversación.
- Los cambios se siguen a un solo nivel: si una unidad se muestra anidada como modificatoria de otra, no se muestran sus propias modificatorias. Límite conocido: el modelo puede ver el texto de una modificatoria sin el aviso de que a su vez fue modificada.

### Reordenamiento

1. El reranker puntúa cada pasaje (encabezado más texto) contra la pregunta. `llama-server` devuelve un valor sin escala fija; la aplicación lo lleva a un número entre 0 y 1 con la función sigmoide, que es la conversión que describen los autores del modelo. Ese número es el que se compara con el umbral y el que se registra.
2. Los pasajes se agrupan por unidad base, con el mejor puntaje de sus pasajes.
3. Primera barrera de abstención (ver "Abstención").
4. Selección: unidades con puntaje igual o mayor al umbral, hasta 3 por categoría. Los considerandos no ocupan ese cupo: tienen uno propio de hasta 2, para que un fundamento no desplace a un artículo. El cupo por categoría existe para que el régimen específico no deje afuera al marco nacional ni a un dictamen (REQ-018, REQ-019).
5. Cambios: a cada unidad seleccionada se le suman, por relación y no por parecido, las unidades que la modifican a la fecha (`unit_changes`).
6. Espacio: si el total no entra en el contexto del modelo (16.384 tokens menos instrucciones, pregunta, respuesta y margen), se incluye primero la mejor unidad de cada categoría, después la segunda de cada una, y así; de una unidad más larga que 1.500 tokens se le muestran al modelo solo los pasajes que superaron el umbral. Lo que queda afuera se registra. La cita muestra siempre la unidad entera. Los tokens se cuentan como dice "Conteo de tokens".
7. Orden de entrega: régimen específico, otra normativa aplicable, marco nacional, dictamen legal, recomendación de auditoría; dentro de cada categoría, por puntaje; los considerandos, al final. El orden lo fija el código.

Todos los números de esta sección son valores iniciales, guardados como parámetros en `settings.py` y copiados en cada consulta.

### Conteo de tokens

El plan mide en tokens tres cosas: el largo de un pasaje (800), el largo a partir del cual una unidad se le muestra al modelo por pasajes (1.500) y el espacio del contexto (16.384). Cada modelo corta el texto en tokens a su manera, así que la cuenta se le pide al mismo servidor que tiene cargado el modelo. `llama-server` ofrece para eso `POST /tokenize`: recibe un texto y devuelve la lista de tokens; la cantidad es el largo de la lista. No hace falta sumar una librería ni archivos de tokenizador a la aplicación.

| Qué se mide | Quién cuenta | Motivo |
|---|---|---|
| Pasajes de hasta 800 tokens (encabezado más texto) | `count_tokens` del cliente de `embeddings` | El pasaje es lo que recibe `bge-m3`. El reranker recibe el mismo pasaje junto con la pregunta y rinde hasta 1.024 tokens (ADR-0003); que su cuenta no difiera de la de `bge-m3` se comprueba en la etapa 0 |
| Unidad de más de 1.500 tokens y espacio del contexto | `count_tokens` del cliente de `generation` | Es el modelo que recibe el pedido |

- **Al partir en pasajes** se cuenta el texto por tramos que terminan en un límite de inciso, de párrafo o de oración, y se acumulan tramos hasta llegar a 800. Nunca se corta en medio de una palabra.
- **Al armar el pedido** se cuentan una vez las instrucciones con la pregunta, y una vez cada unidad tal como se le va a mostrar al modelo. El espacio disponible para unidades es 16.384 menos lo contado para instrucciones y pregunta, menos el máximo de salida, menos un margen de 512 tokens (valor inicial, parámetro en `settings.py`) por lo que agrega la plantilla de conversación del modelo, que `/tokenize` no ve.
- **Si igual no entra**, el motor rechaza el pedido en lugar de recortarlo. El cliente lo informa como error propio y la consulta termina en falla técnica con el motivo `input_too_long`. No es un "no determinado".
- **En las pruebas**, los dobles cuentan de una forma fija y simple (palabras), para que el resultado no dependa del modelo.

La alternativa de estimar por cantidad de caracteres se descartó: puede dejar un pasaje por encima del límite, y una entrada demasiado larga se rechaza. La de cargar los tokenizadores dentro de la aplicación se descartó por sumar una librería y dos archivos que fijar y mantener iguales a los de los modelos (P10).

`llama-server` tiene además un punto de acceso que cuenta los tokens de un pedido de conversación completo, con la plantilla incluida (`POST /v1/chat/completions/input_tokens`). Su documentación aclara que no es parte de la interfaz oficial de OpenAI; no se usa para no depender de él. Si la etapa 0 muestra que el margen de 512 no alcanza o sobra, se ajusta el parámetro.

**Medido en la etapa 0** (`entorno.md`, T-002, sección 8, y T-003, secciones 5 y 6):

- La plantilla de conversación agregó 18 tokens en todos los pedidos de dos mensajes medidos, sin importar el largo. El margen queda en 512: lo que sobra son unos 490 tokens de 16.384 (3 %), y cubre formas de pedido que no se midieron, como un cambio de las instrucciones o de la compilación. Se revisa si la medición de tiempo o de espacio de la etapa 4 lo pide.
- `/tokenize` no cuenta los tokens especiales que agrega el modelo: en `embeddings` son 2 por texto y en `reranker` 4 por par (pregunta más pasaje). Con pasajes de hasta 800 tokens, el límite de 8.192 no se alcanza.
- Una entrada más larga que el contexto se rechaza sin recortar en los tres servicios, pero con códigos distintos: `generation` responde HTTP 400 con `type` `exceed_context_size_error`; `embeddings` y `reranker` responden **HTTP 500** con `type` `server_error` y un mensaje que contiene `is too large to process`. Los clientes de T-011 reconocen el rechazo por ese mensaje para informarlo como `input_too_long` y no como servicio caído. En el reranker, un solo pasaje demasiado largo hace fallar el pedido entero.

Fuentes, consultadas el 2026-10-02: documentación de `llama-server` (https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md), para `/tokenize`, `/apply-template`, el campo `usage` y el conteo de un pedido completo; reporte en su repositorio de que un pedido que excede el contexto se rechaza con error 400 (https://github.com/ggml-org/llama.cpp/issues/17284). Queda por comprobar en el equipo, en la etapa 0, lo que figura en "Sin verificar".

### Generación

Un solo pedido a `generation` por consulta, sin transmisión parcial, con temperatura 0, semilla fija y pensamiento apagado.

**Qué recibe el modelo.** Las instrucciones (archivo versionado en `queries/prompts/`), la pregunta, la fecha de autorización del procedimiento y las unidades seleccionadas, que ya son solo las que regían a esa fecha. El modelo no elige el régimen ni redacta la línea de régimen aplicado ni los avisos: eso lo pone el código. Cada unidad lleva un alias corto (`U1`, `U2`, …), su categoría con su papel, la norma, la ruta, el tipo y el texto. Una unidad modificada lleva a continuación el texto de la que la modifica, con la fecha. Los considerandos van en un bloque aparte, rotulado como contexto.

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

Una sola regla. El resultado es "no determinado" si ocurre cualquiera de estas cuatro cosas, en este orden:

1. **Sin régimen a la fecha.** `applicable_regimes(fecha)` no devuelve ninguno. No se busca ni se llama al modelo. Motivo `no_regime_at_date`. Se aplica el régimen específico y el marco nacional es marco: sin régimen cargado para esa fecha, una respuesta apoyada solo en el marco daría por aplicable lo que no lo es.
2. **Nada pertinente.** Ninguna unidad alcanza el umbral del reranker. No se llama al modelo. Motivo `below_threshold`.
3. **El modelo se abstiene.** Recibió unidades y devolvió `undetermined`. Motivo `model_abstained`.
4. **Cita inválida.** Motivo `invalid_citation`.

En los cuatro casos la pantalla muestra lo mismo: el aviso de "no determinado", sin afirmaciones y sin citas, con la línea de fecha y régimen. El motivo queda en el registro.

Las dos barreras de pertinencia cumplen papeles distintos. El umbral frena las preguntas ajenas a la normativa, es barato y siempre da lo mismo. El modelo frena las preguntas sobre un tema que la normativa menciona pero no resuelve, que el puntaje no distingue. Por eso el umbral se calibra para no frenar preguntas que sí tienen respuesta, y no para alcanzar por sí solo el 90 %.

Calibración con el conjunto de preguntas:

1. Se corre la recuperación sobre todas las preguntas y se anota el puntaje más alto de cada una.
2. Se elige el umbral más alto que frena por error a lo sumo el 5 % de las preguntas con respuesta. Como son unas 30 preguntas, se calcula dejando cada vez una afuera y midiendo sobre ella, y el valor se informa como provisorio.
3. Con ese umbral se corre el sistema completo y se miden las exigencias de la spec.
4. Si la abstención no llega al 90 %, se ajustan primero las instrucciones (la segunda barrera). Subir el umbral cuesta respuestas correctas y es la última opción.
5. Cualquier cambio de umbral, instrucciones, reranker o corpus obliga a correr todo otra vez (P7).

**Valores iniciales provisorios** (confirmados por el responsable el 2026-10-03, a evaluar con T-045 y T-046): umbral del reranker 0,5 sobre la escala de la sigmoide, que equivale a un valor 0 antes de convertirlo; máximo de salida del modelo de generación 800 tokens, que en la etapa 0 alcanzó para 6 afirmaciones de 60 a 110 tokens cada una. Los dos son parámetros de `settings.py` (T-011) y entran en el registro de cada consulta.

Una falla técnica (un servicio que no responde, una espera agotada a los 60 segundos, una salida inválida, un pedido que no entra en el contexto) no es un "no determinado": la pantalla muestra "No se pudo completar la consulta".

### Búsqueda directa (REQ-010)

En la misma pantalla, sin modelos de IA, y siempre para la fecha de autorización indicada en el formulario de búsqueda:

- **Por norma y número de artículo:** se elige la norma y se escribe el número. Devuelve las unidades con ese número que eran consultables a la fecha, en todas las partes de la norma, cada una con su ruta y su texto.
- **Por palabras:** búsqueda de texto de Postgres sobre los pasajes (`tsv` contra `search_query`), sin distinguir acentos ni singular y plural, con comillas para frase exacta. Los resultados se agrupan por unidad base.

Arriba de los resultados va la línea de fecha y régimen aplicado, y debajo los avisos de modificatorias sin cargar que correspondan. Cada resultado muestra la categoría, el texto literal, el enlace al original, los cambios vigentes a la fecha y, si a esa fecha está derogada, la marca con la norma que la derogó y desde cuándo. También muestra los vínculos de su norma con otras, en los dos sentidos (REQ-006). Si no hay resultados para esa fecha, la pantalla lo dice.

Ejemplo: buscar el artículo 1 de la Disposición 297/03 con la fecha del día devuelve sus dos unidades marcadas como derogadas por la 247/2022; con una fecha de 2021 las devuelve sin la marca.

### Aviso de modificatorias sin cargar (REQ-021)

El aviso lo arma el código y es un texto fijo; el modelo no lo redacta ni lo recibe.

1. **Cuándo corresponde.** Cuando una respuesta o una búsqueda muestra al menos una unidad de una norma que tiene modificatorias sin cargar. En una respuesta cuentan las unidades citadas y las que se muestran por haberlas modificado. Un "no determinado" y una falla técnica no muestran unidades y no llevan aviso.
2. **Cómo llega a la respuesta.** `queries/services.py`, después de validar la salida del modelo, mira las normas de las unidades que se van a mostrar, cuenta las modificatorias sin cargar de cada una y agrega a la respuesta un aviso por norma, en `notices` (ver "Forma de la respuesta"). Queda guardado en `queries_query.result`.
3. **Cómo llega a la búsqueda.** La función de búsqueda de `queries/services.py` hace lo mismo con las normas de las unidades devueltas. Los avisos van en el detalle del hecho `search`.
4. **Cómo se muestra.** Un recuadro propio, arriba de las afirmaciones o de los resultados, uno por norma: "La Disposición AFIP 297/03 tiene 32 modificatorias que todavía no están cargadas en el sistema. Puede haber cambios en este texto que el sistema no conoce." El nombre de la norma y la cantidad salen del aviso guardado; el resto es texto de la plantilla.
5. **Cuándo deja de aparecer.** Cuando la cuenta de esa norma llega a cero no se agrega el aviso. Una consulta guardada sigue mostrando el aviso con el que se respondió.

`listar_normas` muestra, para cada norma, cuántas modificatorias tiene sin cargar y cuáles son.

### Forma de la respuesta

Lo que `queries/services.py` le entrega a la pantalla y guarda en `queries_query.result`:

```json
{
  "query_id": 318,
  "status": "grounded",
  "reason": null,
  "reference_date": "2021-03-15",
  "regime": [
    {"norm": 1, "name": "Disposición AFIP 297/03"}
  ],
  "notices": [
    {"type": "pending_amendments", "norm": 1, "name": "Disposición AFIP 297/03", "pending": 32}
  ],
  "statements": [
    {"text": "…", "regimes_differ": true, "citations": [4812, 5160]}
  ],
  "units": {
    "4812": {
      "norm": "Disposición AFIP 297/03",
      "category": "regimen_especifico",
      "unit_type": "articulo",
      "path": "Anexo I › Título I › Artículo 14",
      "text_origin": "web",
      "document": 3,
      "page_start": null,
      "changes": [
        {"relation_type": "modifica", "unit": 6033, "target_unit_key": "anexo-i/art-14/inc-b", "effective_date": "2010-05-01"}
      ]
    }
  }
}
```

Las identificaciones, la fecha y el cambio del ejemplo son ilustrativos.

- `status`: `grounded` (con fundamento), `undetermined` (no determinado) o `error` (falla técnica). `reason` lleva el motivo en los dos últimos casos: `no_regime_at_date`, `below_threshold`, `model_abstained` o `invalid_citation` para `undetermined`; `timeout`, `service_unavailable`, `invalid_output` o `input_too_long` para `error`.
- `reference_date`: la fecha de autorización del procedimiento para la que se consultó. Está en los tres estados.
- `regime`: lo que devolvió `applicable_regimes(fecha)`: una norma, ninguna o, con fechas mal registradas, más de una. Está en los tres estados. La pantalla arma con esto y con la fecha la línea de régimen aplicado (REQ-020).
- `notices`: un aviso por cada norma mostrada que tiene modificatorias sin cargar, con la cantidad (REQ-021). Vacío si no corresponde ninguno y siempre vacío fuera de `grounded`.
- `statements` está vacío salvo en `grounded`.
- `units` trae una vez cada unidad citada y cada unidad que la modifica. El texto literal no viaja en la respuesta guardada: la pantalla lo lee de la base por `id`.
- El papel de cada cita ("es lo que se aplica", "marco de referencia", "criterio que acompaña", "contexto") lo deriva la pantalla de `category` y `unit_type`.
- Cuando `regimes_differ` es verdadero, la pantalla agrega un aviso con texto fijo del sistema ("El régimen específico y el marco nacional tratan este punto de manera distinta. Se aplica el régimen específico."), muestra los dos textos y rotula el del régimen específico como aplicable (REQ-019).

## Pantalla, acceso y comandos

**Pantalla.** Una sola página, armada en el servidor, con la disposición del ADR-0005: pregunta con su campo "Fecha de autorización del procedimiento", y uno de tres bloques que se distinguen por título, ícono y color ("Respuesta con fundamento en la normativa", "No determinado", "No se pudo completar la consulta"). Los tres bloques llevan la línea de fecha y régimen aplicado (REQ-020); el de respuesta lleva además, cuando corresponde, el recuadro de modificatorias sin cargar (REQ-021). En la misma página está el formulario de búsqueda directa, con su propio campo de fecha; sus resultados llevan la misma línea y el mismo recuadro. El campo de fecha es el control de fecha del navegador, viene con la del día y las fechas se muestran como día/mes/año. Al elegir una cita se despliega el texto literal, con el enlace "Abrir el documento original" y, si corresponde, la leyenda de que el texto proviene de reconocimiento sobre imagen. Tipografías del sistema, una hoja de estilos y un script propios; ninguna referencia externa. Al recargar se muestra lo guardado; no se vuelve a consultar.

**Documento original.** Lo entrega una vista que exige sesión, leyendo de `norms_document_file`. Un PDF se abre con el visor del navegador. Una página web guardada se entrega con una política que impide ejecutar scripts y cargar recursos de internet; el archivo no se modifica.

**Acceso.** Ingreso con usuario y clave de Django; Argon2id; sesiones en la base; mensaje de error único; toda página exige sesión salvo la de ingreso. El rol se comprueba en las funciones de negocio.

**Comandos.** Se corren con `docker compose exec app python manage.py <comando>`. Cada uno pide `--usuario` y la clave por teclado, salvo `crear_usuario`.

| Comando | Qué hace | Requisitos | Rol |
|---|---|---|---|
| `cargar_norma` | Incorpora un documento con sus datos, su categoría y su parte (`--parte`); marca la norma como régimen general si se indica `--regimen-general`; avisa si ya está | REQ-001, 011, 015, 017, 020 | Lectura y escritura |
| `releer_norma` | Vuelve a leer y partir un documento ya cargado; deja una lectura nueva sin validar | REQ-004, 005 | Lectura y escritura |
| `listar_normas` | Lista normas con sus datos, documentos por parte, estado de validación, vínculos y modificatorias sin cargar | REQ-001, 006, 021 | Los dos |
| `ver_informe` | Muestra el informe de lectura, con las unidades y sus claves | REQ-004 | Los dos |
| `validar_informe` | Valida una lectura, previa confirmación, y calcula sus pasajes y vectores | REQ-005 | Lectura y escritura |
| `registrar_relacion` | Registra que una norma modifica, complementa, reglamenta o deroga a otra, con fecha y, si corresponde, las unidades. Si la norma de origen figuraba como modificatoria sin cargar, la deja como cargada e informa cuántas quedan | REQ-006, 007, 020, 021 | Lectura y escritura |
| `registrar_version` | Deja un documento validado como versión de su parte de la norma, o como el archivo en uso de una versión | REQ-007 | Lectura y escritura |
| `registrar_modificatorias` | Anota las modificatorias de una norma que todavía no están cargadas, en lote desde un archivo CSV o de a una | REQ-021 | Lectura y escritura |
| `crear_usuario` | Da de alta un usuario con su rol. Lo corre quien administra el equipo, sin rol de EVALUON; queda registrado | REQ-016 | — |
| `correr_evals` | Corre el conjunto de preguntas y guarda la corrida | Calidad (P7) | Lectura |

Los nombres de comandos y de sus opciones van en español, como excepción a la convención de identificadores en inglés: es lo que escribe el responsable de normativa, igual que lee los textos de la pantalla. Lo decidió el responsable al aprobar el plan. Todo lo demás (servicios, tablas, campos, funciones) va en inglés.

`releer_norma`, `correr_evals` y `registrar_modificatorias` no están en la tabla del ADR-0005. El primero cubre un hueco: sin él, un documento mal partido no tiene forma de volver a leerse, porque REQ-011 impide cargar otra vez el mismo archivo. El segundo es la herramienta de P7. El tercero es el camino de REQ-021, que se sumó a la spec después de ese ADR; lo mismo vale para las opciones `--parte` y `--regimen-general` de `cargar_norma`.

## Registro de auditoría

Todo queda en `audit_event`; cada consulta tiene además su detalle en `queries_query`. Datos comunes a todo hecho: momento, usuario, canal (pantalla, comando o eval), resultado y versión de la normativa.

| Hecho | Qué se guarda además |
|---|---|
| Carga (`load`) y relectura (`reread`) | Documento y norma; datos ingresados, categoría, parte y marca de régimen general; nombre, formato detectado, tamaño y huella del archivo; huella del texto canónico; versiones de las herramientas, huella del modelo de español de Tesseract y versión de las reglas; lectura creada; resumen del informe (unidades por tipo, páginas ilegibles, tramos no ubicados); resultado de las comprobaciones de duplicado y la confirmación expresa, si la hubo. Una carga rechazada por duplicado también se registra |
| Validación (`validation`) | Lectura validada; huella del informe que la persona vio; lectura reemplazada, si había; cantidad de pasajes; nombre y huella del modelo de embeddings; versión nueva de la normativa |
| Relación (`relation`) | Tipo, normas, claves de unidad, fecha de vigencia del cambio; la modificatoria que quedó como cargada, si la hubo, y cuántas quedan sin cargar; versión nueva de la normativa |
| Versión (`version`) | Documento, parte, número de versión, vigencia, documento que deja de estar en uso; versión nueva de la normativa |
| Modificatorias sin cargar (`pending_amendment`) | Norma alcanzada; cada modificatoria anotada con su tipo, número, año, organismo y referencia; las que ya estaban; las que quedaron como cargadas en el acto; archivo de origen con su huella, si fue en lote; cuántas quedan sin cargar; versión nueva de la normativa |
| Consulta (`query`) | Pregunta; fecha de autorización del procedimiento; régimen aplicado; avisos de modificatorias sin cargar mostrados, con su cantidad; modelo de generación (nombre, huella del archivo, compilación del motor, contexto, temperatura, semilla, pensamiento, máximo de salida); modelos de embeddings y de reranker (nombre y huella); versión de las instrucciones y pedido completo; parámetros de búsqueda (candidatos por camino, umbral, cupos, espacio); cada candidato con su camino, puntaje y origen del texto; unidades enviadas, agregadas por relación y dejadas afuera; puntaje más alto; decisión de abstención y motivo; salida del modelo sin tocar; anomalías; respuesta final; tiempos por etapa |
| Búsqueda (`search`) | Tipo de búsqueda, términos, fecha de autorización del procedimiento, régimen aplicado, unidades devueltas con su marca de derogada, y avisos de modificatorias sin cargar mostrados, con su cantidad |
| Ingreso (`login`) | Usuario y canal |
| Ingreso fallido (`login_failed`) | Nombre intentado y canal. Nunca la clave |
| Operación rechazada por rol (`rejected`) | Usuario, operación intentada y canal |
| Alta de usuario (`user_created`) | Usuario creado y rol; hecho por quien administra el equipo |

Con el registro de una consulta se puede explicar una respuesta pasada sin volver a ejecutarla. El registro no guarda claves ni identificadores de sesión.

Observación: el restablecimiento de una clave olvidada usa el comando `changepassword` de Django (ADR-0005), que no pasa por este registro. Ningún requisito lo pide; se informa para que no sorprenda en la auditoría.

## Evals

**Casos.** Un archivo por pregunta en `evals/casos/EV-NNN.yaml`, con el formato de `evals/README.md` y estos datos adicionales para poder medir sin intervención:

- `fecha_autorizacion`: la fecha de autorización del procedimiento para la que se pregunta. Obligatoria en todos los casos, también en los que no tienen respuesta. No tiene valor por omisión: si fuera la del día, el mismo caso daría otro resultado con el paso del tiempo.
- `regimen`: la norma que tiene que figurar como régimen aplicado a esa fecha ("Disposición AFIP 297/03" o "Disposición AFIP 247/2022"). Vacío solo en un caso que pregunte para una fecha sin régimen cargado.
- `unidades`: las unidades que sostienen la respuesta, por norma y `key`. Vacío en las preguntas sin respuesta.
- `datos_clave`: los datos que la respuesta tiene que contener (un plazo, un porcentaje, un sí o un no), cuando los hay.
- `difieren`: verdadero en las preguntas de REQ-019.
- `pareja`: en los casos que repiten una pregunta con otra fecha, el identificador del otro caso del par. Vacío en los demás.
- `aviso_modificatorias`: verdadero si la respuesta tiene que llevar el aviso de modificatorias sin cargar; falso si no tiene que llevarlo.
- `etiquetas`: referencia exacta, palabras distintas a las de la norma, dos categorías, ajena a la normativa, tema cercano que la normativa no resuelve, dos fechas.
- `visto_bueno`: quién de la Comisión lo aprobó y cuándo. Un caso sin visto bueno no se corre.

**Composición del conjunto por la fecha (REQ-020 y REQ-021).** El conjunto de unas 30 preguntas tiene que incluir:

- Casos con fecha anterior a la entrada en vigencia de la Disposición 247/2022, que se responden con la 297/03, y casos con fecha posterior, que se responden con la 247/2022. De los dos grupos, con y sin respuesta.
- Al menos un par: la misma pregunta en dos casos, uno con fecha anterior y otro con fecha posterior, vinculados por `pareja`. Es el criterio de aceptación de REQ-020: el primero cita la 297/03, el segundo la 247/2022, y cada uno indica su régimen y su fecha.
- Al menos un caso con `aviso_modificatorias` verdadero (una respuesta que cita la 297/03 mientras tenga modificatorias sin cargar) y al menos uno con falso (una respuesta que cita solo la 247/2022). Es el criterio de REQ-021.

Cuántas preguntas van a cada régimen lo decide el responsable (ver "Qué tiene que decidir el responsable"). Los casos cercanos al cambio de régimen se redactan con la fecha de entrada en vigencia de la 247/2022, el 2023-01-01: hasta el 2022-12-31 corresponde la 297/03.

**Cómo se corre.** `correr_evals`, dentro de `app`, con los servicios reales y la normativa cargada y validada. Llama a la misma función que la pantalla, con el canal `eval` y la `fecha_autorizacion` del caso, una pregunta por vez. Las consultas quedan también en el registro de auditoría.

**Dónde se guarda.** Una carpeta por corrida en `evals/corridas/`, con la fecha, el commit y el modelo en el nombre:

- `parametros.json`: modelos con sus huellas, compilación del motor, versión de las instrucciones, parámetros de búsqueda, umbral y versión de la normativa.
- `resultados.jsonl`: un renglón por caso, con el resultado, las unidades citadas, las medidas y los tiempos.
- `resumen.md`: las medidas de la tabla, la comparación con la corrida anterior y la lista de casos fallados.

**Cómo se mide cada exigencia.**

| Exigencia de la spec | Cómo se mide | Umbral |
|---|---|---|
| Cita literal | Sobre todas las citas de todas las respuestas: el texto mostrado es igual a `canonical_text[char_start:char_end]` | 100 % |
| Respuesta correcta que cita la unidad correcta | Sobre las preguntas con respuesta. Un caso cuenta si el resultado es `grounded`, el régimen aplicado es el de `regimen`, cita todas las unidades de `unidades` (si el caso nombra un inciso, vale el artículo que lo contiene), contiene los `datos_clave` y, si `difieren` es verdadero, trae la marca `regimes_differ` con las dos citas. En la corrida que se presenta para aprobar, el responsable revisa además las respuestas contra la esperada y puede dar por incorrecta cualquiera | Al menos 85 % |
| Abstención | Sobre las preguntas sin respuesta. Cuenta si el resultado es `undetermined`. Una falla técnica no cuenta como abstención | Al menos 90 % |
| Tiempo de respuesta | Tiempo total de cada consulta, medido en el equipo, con los servicios ya cargados. Se informan la mediana y el máximo | Máximo de 30 segundos |

Se informan además, sin ser exigencias de la spec: las medidas de recuperación del ADR-0003 (unidad correcta entre los candidatos y entre las seleccionadas, preguntas con respuesta frenadas por el umbral, tiempo de la recuperación), las del ADR-0002 (salidas con falla de formato o de cita, memoria de video ocupada, igualdad al repetir la corrida) y, aparte, los casos de REQ-018 y REQ-019. La comparación quitando piezas del ADR-0003 se corre una vez.

También se informan aparte, y se espera que no falle ninguno:

- **Pares de REQ-020.** Un par pasa si sus dos casos tienen la misma pregunta, cada uno pasa por su cuenta y las normas citadas son distintas.
- **Aviso de REQ-021.** En cada caso, que la respuesta lleve o no lleve el aviso según `aviso_modificatorias`. Como el aviso lo pone el código, una diferencia acá es un defecto o un caso desactualizado, no una baja de calidad del modelo.
- **Medidas por régimen.** Respuesta correcta y abstención, separadas para los casos de la 297/03 y los de la 247/2022. Son de diagnóstico: las exigencias de la spec se miden sobre el conjunto entero.

Con unas 30 preguntas, cada una pesa entre 3 y 5 puntos: una diferencia de una pregunta entre dos corridas no demuestra nada. Repartidas entre dos regímenes, las medidas por régimen salen de menos casos todavía y sirven solo para orientar.

Cuando se carga una modificatoria de la 297/03 cambian el corpus y, tal vez, la cantidad del aviso: como con cualquier cambio del corpus, se corre todo otra vez y se revisan los casos que esa modificatoria alcanza.

**Regla de P7.** Todo cambio en recuperación, instrucciones, modelo o umbral se acepta solo con una corrida nueva. Una baja respecto de la anterior requiere aprobación del responsable.

## Cobertura de requisitos

| Requisito | Cómo se resuelve | Cómo se verifica |
|---|---|---|
| REQ-001 | `cargar_norma`; `norms_norm` y `norms_document` guardan tipo, número, organismo, título, fechas de publicación y de vigencia, y fuente; `listar_normas` | Test: tras cargar con sus datos, el listado muestra la norma con todos ellos |
| REQ-002 | `norms_document_file`; vista con sesión que entrega el original de cada parte | Test: la huella de lo que entrega la vista es igual a la del archivo cargado, en PDF y en HTML |
| REQ-003 | Partición con reglas (ADR-0004), más la regla del texto normativo sin número, que da unidades `clausula`; `norms_unit` con `unit_type`, `key`, `path`, páginas y posición; parte del documento como unidad raíz cuando es un anexo | Test: tablas esperadas escritas a mano del anexo de la Disp. 247/2022 (`disp-afip-247-2022-anexo.pdf`), de su cuerpo (`disp-afip-247-2022-original.htm`) y de la Disp. 297/03 (`disp-afip-297-2003-original.htm`); `art-1` y `anexo/art-1`, y `art-1` y `anexo-i/art-1`, son unidades distintas; la cláusula transitoria del anexo de la 247/2022 es la unidad `anexo/clausula-transitoria`, después de `anexo/art-99`; los índices no producen unidades; cada texto es igual a su recorte |
| REQ-004 | Informe de lectura en `norms_reading.report`; `ver_informe` | Test: un PDF con una página de ruido; el informe señala esa página y ninguna otra |
| REQ-005 | Estado de la lectura; `consultable_units` como único camino | Test: una norma cargada y sin validar no aparece por ninguno de los tres caminos ni en la búsqueda directa |
| REQ-006 | `norms_relation`, con claves de unidad cuando corresponde; `registrar_relacion`; vínculos en `listar_normas` y en la pantalla | Test: registrada la relación, al ver cualquiera de las dos normas aparece el vínculo; una relación entre unidades guarda sus claves |
| REQ-007 | `effective_date` de las relaciones, versiones de documento con su vigencia, `consultable_units(fecha)` y `unit_changes(fecha)`; `registrar_version` | Test: un artículo modificado en una fecha; antes, solo el original; después, el original con el texto literal de la que lo modifica, señalando el cambio. Test: dos versiones de una norma; cada fecha devuelve la suya. Test: una norma derogada en una fecha; antes sostiene respuestas, después no |
| REQ-008 | Recuperación, generación con esquema e inserción del texto desde la base | Test con doble del motor: la respuesta cita el artículo y el texto es el de la base. Evals: cita literal 100 %, respuesta correcta al menos 85 % |
| REQ-009 | Regla única de abstención | Tests con dobles: bajo el umbral no se llama al modelo; el modelo se abstiene; cita inválida; en los tres el resultado es `undetermined`. Evals: abstención al menos 90 % |
| REQ-010 | `queries/search.py` y formulario en la pantalla de consulta, con su fecha de autorización | Test: un usuario de lectura busca norma y artículo y obtiene la unidad con su texto; "artículo 1" de la 297/03 devuelve las dos unidades con su ruta; busca por palabras sin tildes; una unidad derogada a la fecha consultada aparece marcada, y con una fecha anterior a la derogación aparece sin la marca |
| REQ-011 | Huella del archivo, huella del texto canónico y datos de la norma con su parte; confirmación expresa en `cargar_norma` | Test: el mismo archivo dos veces da un aviso y un solo documento; la misma norma y la misma parte en otro archivo avisa y solo se incorpora con confirmación; el anexo de una norma que ya tiene su cuerpo se incorpora como otra parte, con aviso informativo y sin duplicar la norma |
| REQ-012 | `audit_event`, `queries_query` y `norms_corpus_version` | Test: tras una consulta, su registro muestra pregunta, fecha de autorización, régimen aplicado, unidades recuperadas, respuesta, avisos, versión de la normativa, usuario y fecha. Tests equivalentes para carga, validación, búsqueda y modificatorias sin cargar |
| REQ-013 | Pantalla de consulta | Test con el cliente de pruebas: la página muestra la respuesta con sus citas, el texto literal de cada unidad y el enlace al original |
| REQ-014 | Bloque propio de "No determinado" | Test: con resultado `undetermined` la página muestra ese aviso, distinto del de una respuesta, y ninguna cita |
| REQ-015 | Lectura por formato (`reading/`); `text_origin` en la unidad y en el informe | Test: un mismo extracto del anexo de la Disp. 247/2022 en PDF con texto, PDF escaneado y HTML da la misma lista de unidades; en el escaneado, todas con origen `ocr` y el informe lo dice |
| REQ-016 | Ingreso de Django, Argon2id, sesiones en la base; `role` en el usuario; comprobación en las funciones de negocio; `crear_usuario` | Test: sin sesión, la consulta redirige al ingreso; un usuario de lectura que corre `cargar_norma` o `validar_informe` es rechazado y queda el registro; la clave guardada no es legible |
| REQ-017 | `category` obligatorio en `norms_norm`; lo exige `cargar_norma` | Test: una carga sin categoría no incorpora y pide el dato |
| REQ-018 | Cupo por categoría en la selección; orden de citas y de afirmaciones fijado por el código; rótulo de categoría y papel en la pantalla | Test con doble: artículo del régimen específico y dictamen; el artículo va primero y cada cita muestra su categoría; un considerando va al final, rotulado como contexto |
| REQ-019 | Cupo por categoría, marca `regimes_differ` validada por el código y aviso de texto fijo en la pantalla | Test con doble: con la marca, la página muestra los dos textos y señala el del régimen específico como aplicable. Evals: casos con `difieren` |
| REQ-020 | Campo de fecha en los formularios de pregunta y de búsqueda, con la del día por omisión; `consultable_units(fecha)`, `unit_changes(fecha)` y `applicable_regimes(fecha)`; `effective_from` de cada documento, `effective_date` de la relación `deroga` y `general_regime` en la norma; línea de fecha y régimen aplicado en la pantalla; fecha y régimen en el registro | Test con dobles: dos regímenes y una derogación con fecha; la misma pregunta con una fecha anterior cita el primero y con una posterior cita el segundo, y cada respuesta muestra su régimen y su fecha. Tests: campo vacío usa la del día; fecha futura rechazada; fecha sin régimen da "no determinado" con `no_regime_at_date`; la búsqueda respeta la fecha. Evals: par de casos con `pareja` |
| REQ-021 | `norms_pending_amendment`; `registrar_modificatorias` (en lote o de a una); paso a cargada al registrar la relación; `notices` en la respuesta y en la búsqueda; recuadro de texto fijo en la pantalla; `listar_normas` | Test: una norma con dos modificatorias anotadas; una respuesta que cita una unidad suya muestra el aviso con "2", y una búsqueda también; cargada, validada y relacionada una, muestra "1"; con las dos, el aviso no aparece. Una respuesta que no muestra unidades de esa norma no lleva aviso. Evals: casos con `aviso_modificatorias` |

Los requisitos no funcionales de la spec no tienen identificador `REQ-NNN`. Se atienden así: calidad y tiempo, en "Evals"; funcionamiento sin conexión, con la red interna de Docker, `--offline` y una prueba con la red desconectada; claves no legibles, con REQ-016; lenguaje llano, con la revisión de los textos de la pantalla y de los comandos.

## Verificación contra la constitución

| Principio | Cumple | Nota |
|---|---|---|
| P1 La spec es la fuente de verdad | sí | Cada parte del plan responde a un requisito o a un requisito no funcional. Lo agregado respecto de los ADR (`releer_norma`, `correr_evals`, `registrar_modificatorias`, parte del documento, marca de régimen general, versión de la normativa) está justificado contra un requisito o un principio |
| P2 Trazabilidad | sí | La tabla de cobertura cruza los 21 requisitos con su test. REQ-020 es de origen normativo y cita la Disp. AFIP 247/2022, arts. 2 a 4. Las tareas de entorno y las de requisitos no funcionales se anotan contra los requisitos que habilitan, porque esos requisitos no tienen identificador propio (se informa al Coordinador) |
| P3 El sistema recomienda | sí | Toda afirmación lleva su cita con texto literal; sin sustento el resultado es "no determinado", y también cuando para la fecha no hay un régimen cargado; una falla técnica se muestra como falla. El régimen aplicado y el aviso de modificatorias sin cargar son textos del sistema que dicen con qué se respondió y qué puede faltar. En esta feature no hay decisiones de la Comisión que registrar |
| P4 Datos | sí | Solo material público. Ningún servicio externo en el camino de los documentos: IA local con `--offline` y red interna. Internet se usa una vez, para bajar imágenes y modelos |
| P5 Local y reproducible | sí | Docker Compose, imágenes y modelos con versión y huella fijas, originales dentro de la base, un comando para levantar. La descarga de modelos es un paso único y documentado |
| P6 Auditoría | sí | Ver "Registro de auditoría" |
| P7 Evals | sí | Ver "Evals". Los umbrales son los de la spec |
| P8 Normativa versionada | sí | Fuente y fecha de vigencia por documento, versiones por parte de cada norma, relaciones con fecha y `norms_corpus_version` en cada consulta. Las unidades no se modifican. La 297/03 abrogada se conserva y se sigue pudiendo consultar para las fechas en que regía |
| P9 Hojas de compliance | sí | No aplica en esta feature: no hay ofertas ni validaciones externas. Nada del plan las infiere |
| P10 Simplicidad | sí | Una imagen para los tres servicios de IA; sin índice aproximado, cola, caché ni servidor intermedio; sin pantallas fuera de la de consulta; sin corrección manual de texto. Los dos regímenes se resuelven con la función de fecha que ya existía, un campo en la norma y uno en el documento; las modificatorias sin cargar, con una tabla y un comando; los tokens los cuenta el mismo servidor de IA |
| P11 Compuertas humanas | sí | El plan está aprobado y los ADR 0002 a 0007 están aceptados. La actualización por el ADR-0006 la aprobó el responsable el 2026-10-02 (pull request 5), y los ajustes por la etapa 0 también, el mismo día |

## Decisiones

ADR en los que se apoya este plan, los cinco aceptados. Los ADR 0002 a 0005 se ajustaron en la integración (cada uno termina con una sección "Ajustes de integración"); el ADR-0006 lo decidió el responsable el 2026-10-02.

| ADR | Decide |
|---|---|
| ADR-0002 | Motor `llama-server` y modelo Gemma 4 12B, con Gemma 4 26B-A4B como contraste |
| ADR-0003 | `bge-m3`, `bge-reranker-v2-m3`, búsqueda combinada sobre Postgres sin índice aproximado, servidos con `llama-server` |
| ADR-0004 | pdfplumber, Tesseract, BeautifulSoup y partición con reglas |
| ADR-0005 | Django, páginas armadas en el servidor, Argon2id, sesiones en la base y comandos |
| ADR-0006 | Dos regímenes específicos, la Disposición 247/2022 y la 297/03, aplicados según la fecha de autorización del procedimiento |
| ADR-0007 | Búsqueda por palabras: normalizar texto y consulta (quitar acentos y reponer la tilde de "-ación" y "-ución") y reducir a la raíz con `spanish` |

Esta actualización no necesita un ADR nuevo: ninguna de sus decisiones es difícil de revertir. Los campos y la tabla que suma entran en el esquema antes de que exista una base con datos, y para volver a un solo régimen alcanza con fijar la fecha y ocultar el campo, como dice el ADR-0006.

Los ADR 0003, 0004 y 0005 tienen frases que quedaron atrás del ADR-0006 (la fecha del día fija, el corpus vacío, la tabla de comandos), y al ADR-0004 le falta el tipo de unidad `clausula`. Este plan no los modifica; el detalle está en "Actualización por ADR-0006".

Decisiones tomadas en este plan al integrar:

1. **Embeddings y reranker se sirven con `llama-server`**, la misma imagen que la generación. Evidencia: la documentación de `llama-server` nombra a `bge-reranker-v2-m3` como ejemplo de su endpoint de reranker, que se probó con ese modelo al incorporarse; hay archivos GGUF de los dos modelos. Lo que no hay: los archivos son conversiones de un tercero y no de los autores; no encontré una medición de que den los mismos resultados que el original; una conversión de otro tercero falló al cargar por faltarle un dato. Por eso es la opción principal y no una certeza: la etapa 0 decide, con Text Embeddings Inference como plan B. Detalle y fuentes en el ADR-0003.
2. **Memoria de video:** 20 GB de tope sobre 24; estimado de 12,6 GB; se mide en la etapa 0.
3. **Unidades anidadas:** se indexan y se citan unidades base; los incisos sirven para relaciones y búsqueda directa.
4. **Identificación:** `id` para el registro, `key` para relaciones y comandos, `path` para mostrar.
5. **Relaciones y versiones:** relaciones por norma y clave de unidad, con fecha; versiones como documentos de la misma norma; `consultable_units(fecha)`.
6. **Archivo original:** en la base.
7. **Nombres:** servicios e identificadores en inglés; comandos en español.
8. **Migraciones:** automáticas solo sobre una base vacía; con datos, respaldo previo.
9. **Forma de la respuesta:** afirmaciones con citas, tres estados, marca `regimes_differ`.
10. **Abstención:** una regla con tres motivos; umbral calibrado para no frenar preguntas con respuesta.
11. **Cita literal:** una definición; cita inválida da "no determinado"; formato inválido da falla técnica.
12. **Registro:** `audit_event` más `queries_query`.
13. **Evals:** `correr_evals`, carpeta por corrida, cuatro medidas exigidas.

Decisiones tomadas en la actualización por el ADR-0006, pendientes de aprobación:

14. **Fecha de autorización:** campo en los dos formularios, con la del día por omisión; fecha futura rechazada; fecha sin régimen cargado da "no determinado" con motivo propio.
15. **Régimen aplicado:** lo calcula el código con `applicable_regimes(fecha)`, a partir de la marca `general_regime` de la norma; se muestra como línea de texto fijo y se guarda.
16. **Transición entre regímenes:** la fecha de entrada en vigencia de la 247/2022, que es el 2023-01-01, la escribe una persona, en `effective_from` de sus dos documentos y en `effective_date` de la relación `deroga`. Derogada quiere decir derogada a la fecha consultada.
17. **Norma en más de un archivo:** cada documento es una parte (`cuerpo` o un anexo); las unidades de un anexo cuelgan de una unidad raíz con la clave de la parte; un documento en uso por norma, parte y versión.
18. **Modificatorias sin cargar:** tabla `norms_pending_amendment`, comando `registrar_modificatorias` con carga en lote, paso a cargada al registrar la relación, aviso de texto fijo con la cantidad.
19. **Conteo de tokens:** `POST /tokenize` del servidor que tiene cargado cada modelo, como cuarta operación de los clientes de `evaluon/ai/`; margen de 512 tokens para la plantilla de conversación.
20. **Hilo mínimo:** se hace con `disp-afip-247-2022-anexo.pdf`, que es un PDF con texto real y es el régimen que responde con la fecha del día.
21. **Texto normativo sin número de artículo:** unidad de tipo `clausula`, sin número, con el nombre que le da el documento en la clave y en la ruta. La cláusula transitoria del anexo de la 247/2022 es `anexo/clausula-transitoria`. Que sea unidad propia, sin número y sin usar `parrafo`, lo decidió el responsable el 2026-10-02; el tipo, la clave y la regla de partición los define este plan.

Ajustes por la etapa 0:

22. **Separador de pares del reranker:** `--override-kv tokenizer.ggml.add_sep_token=bool:true`, obligatorio. Decidido por el responsable el 2026-10-02 (ADR-0003, adenda).
23. **Búsqueda por palabras:** `search_normalize`, `search_document` y `search_query` en lugar de la configuración `spanish_unaccent`. Aprobada (ADR-0007).

## Orden de construcción

Regla para asignar: los bloques marcados "en paralelo" no comparten archivos entre sí y se pueden dar a desarrolladores distintos. Todo lo que toca el esquema (`models.py`, `migrations/`) o la configuración compartida (`settings.py`, `urls.py` de la raíz, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `.env.example`, `tests/conftest.py`) va de a uno, en una sola fila de tareas.

Tres trabajos de personas corren desde el primer día, en paralelo con todo (Coordinador, responsable e integrante de la Comisión). Las fechas de entrada en vigencia, que eran el cuarto, ya están establecidas (2026-10-02): 2023-01-01 para la Disposición 247/2022, informada por el responsable, y 2003-06-14 para la 297/03. Se escriben al cargar cada documento y al registrar la derogación.

- Corpus de la feature: decisión del responsable del 2026-10-03 (ADR-0008), solo la Disposición 297/03 y la 247/2022 con su anexo. Las modificatorias de la 297/03 se registran como sin cargar (REQ-021); los requisitos de categorías (REQ-018, REQ-019) y la partición de dictámenes y recomendaciones se prueban con documentos sintéticos.
- Redactar y validar las preguntas del conjunto, cada una con su fecha de autorización.

### Etapa 0 · Comprobación del entorno

De a uno. No construye funciones: comprueba que las piezas funcionan en la notebook y deja medido lo que hoy es estimación. Deja el `docker-compose.yml` con los seis servicios, las versiones fijadas y un informe en `specs/001-normativa/entorno.md`. El detalle de cada prueba está en "Sin verificar y cómo se cierra".

1. GPU visible dentro de un contenedor.
2. `generation` responde y cumple un esquema con lista cerrada de valores; se mide su velocidad; cuenta tokens con `/tokenize`, se mide cuánto agrega la plantilla de conversación y se comprueba que rechaza un pedido que no entra en el contexto.
3. `embeddings` y `reranker` cargan en `llama-server`, reproducen los valores publicados y rechazan una entrada demasiado larga; `embeddings` cuenta tokens con `/tokenize`; se mide la memoria de video con los tres cargados.
4. Postgres: versión fijada, extensiones `vector` y `unaccent`, configuración `spanish`.
5. Django 6.1 con sus librerías: el esqueleto arranca y corre un test.

Si el punto 3 falla, se pasa al plan B y se actualizan este plan y el ADR-0003 antes de seguir. Si el punto 2 muestra que una consulta no entra en 30 segundos, se informa al responsable antes de seguir.

### Etapa 1 · Base común

De a uno: es esquema y configuración compartida.

1. Esqueleto de Django, usuario propio con rol, ingreso y salida, Argon2id, sesiones, `permissions.py`, `audit_event` y su función de registro, `crear_usuario` (REQ-016, REQ-012).
2. Esquema completo de `norms` y `queries` como está en "Modelo de datos", incluidos `general_regime`, `part` y `norms_pending_amendment`, con las migraciones de SQL propio (`consultable_units`, `unit_changes`, `applicable_regimes`, y `search_normalize`, `search_document` y `search_query` para la búsqueda por palabras) y sus reversas (REQ-005, REQ-007, REQ-012, REQ-020, REQ-021).
3. Clientes de `evaluon/ai/`, con el conteo de tokens, y sus dobles en `tests/conftest.py`.

### Etapa 2 · Hilo mínimo de punta a punta

Objetivo: cargar una norma en PDF con texto, validarla, preguntar en la pantalla para una fecha de autorización y ver una respuesta con su cita, su régimen aplicado y su registro. Todo lo mínimo, para probar el recorrido entero cuanto antes.

**Con qué documento.** Con el anexo de la Disposición 247/2022, `corpus/normativa/disp-afip-247-2022-anexo.pdf`, cargado como parte `anexo` de esa norma. Se eligió por tres motivos:

- Es un PDF con texto real, de 45 páginas, que ya está en el corpus. No hay que conseguir ni generar ningún PDF, como preveía la versión anterior de este plan para la 297/03.
- Es el régimen que rige hoy: con la fecha del día, que es la que trae el campo, la pregunta se responde con este documento. Con la 297/03 sola, una pregunta con la fecha del día se respondería con un régimen abrogado o, una vez registrada la derogación, no tendría respuesta.
- La 297/03 está en el corpus solo como página web, y la lectura de páginas web es de la etapa 3.

Para las pruebas automáticas se usa un extracto del mismo archivo: sus primeras seis páginas, que traen el índice completo y los primeros artículos. El cuerpo de la 247/2022 y la 297/03 se cargan en la etapa 4, cuando la lectura de páginas web está hecha.

Dos líneas en paralelo, que no comparten archivos:

- **Línea de datos:** lectura de PDF con texto y partición solo de artículos, con el anexo como unidad raíz (`norms/reading/pdf_text.py`, `norms/splitting/`); `cargar_norma` con `--parte` y `--regimen-general`, `listar_normas`, `ver_informe` y `validar_informe` mínimos (`norms/services/loading.py`, `listing.py`, `validation.py`); pasajes y vectores (`norms/indexing.py`). REQ-001, 003, 004, 005, 017, 020.
- **Línea de consulta:** pantalla con el campo de fecha y los tres bloques con su línea de régimen aplicado, sobre la forma de la respuesta y con el doble del motor (`queries/views.py`, `forms.py`, `templates/`, `static/`). REQ-013, 014, 020.

Después, de a uno: recuperación mínima por significado con reranker (`queries/retrieval.py`), generación con esquema e inserción de citas (`queries/answering.py`, `queries/prompts/`), y `queries/services.py` que las une, valida la fecha, resuelve el régimen y guarda el registro. REQ-008, 009, 012, 020. La etapa termina con una pregunta real respondida en la pantalla con los servicios reales, con la fecha del día y la Disposición 247/2022 como régimen aplicado.

### Etapa 3 · Bloques completos

En paralelo. Cada bloque tiene sus archivos:

| Bloque | Archivos | Requisitos |
|---|---|---|
| A · PDF escaneado | `norms/reading/ocr.py` | REQ-015, 004 |
| B · Página web | `norms/reading/web.py` | REQ-015 |
| C · Partición completa e informe | `norms/splitting/`: reglas completas contra el anexo de la 247/2022 y, con la lectura de páginas web, contra su cuerpo y contra la 297/03 | REQ-003, 004 |
| D · Duplicados y relectura | `norms/services/loading.py`, comandos `cargar_norma` y `releer_norma`: duplicados que distinguen la parte | REQ-004, 005, 011 |
| E · Relaciones y versiones | `norms/services/relations.py`, `versions.py`, y los vínculos en `listing.py`, con sus comandos; versiones por parte | REQ-006, 007 |
| F · Recuperación completa | `queries/retrieval.py`: tres caminos, cupos, cambios por relación, espacio, umbral, siempre para la fecha de autorización | REQ-005, 009, 018, 019, 020 |
| G · Generación completa | `queries/answering.py`, `queries/prompts/`: validación, `regimes_differ`, orden | REQ-008, 009, 018, 019 |
| H · Búsqueda directa | `queries/search.py`, para la fecha de autorización | REQ-010, 020 |
| I · Pantalla completa | `queries/views.py`, `templates/`, `static/`, `norms/views.py`: citas con categoría y papel, cambios, aviso de REQ-019, búsqueda con su fecha y su línea de régimen, original | REQ-002, 010, 013, 014, 018, 019, 020 |
| J · Acceso y registro | `accounts/`, `audit/services.py`: ingresos fallidos, rechazos por rol, sesión | REQ-012, 016 |
| K · Evals | `queries/evaluation.py`, comando `correr_evals`, `evals/`: casos con fecha, pares y aviso | Calidad (P7), REQ-020, 021 |
| L · Modificatorias sin cargar | `norms/services/amendments.py`, comando `registrar_modificatorias`, paso a cargada desde `relations.py`, cuenta en `listing.py`; después, avisos en `queries/services.py` y en la pantalla | REQ-021, 012 |

Dependencias dentro de la etapa: C necesita la lectura de la etapa 2 y, para los documentos que son páginas web, a B; D necesita C; H e I necesitan el esquema y la forma de la respuesta, no a F ni a G; K necesita `queries/services.py` de la etapa 2. I y H comparten la pantalla: H entrega la función de búsqueda e I la muestra. L toca `relations.py` y `listing.py`, por eso su primera parte va después de E; su segunda parte toca `queries/services.py` y la pantalla, por eso va después de la unión final y de I.

De a uno: cualquier cambio de esquema que aparezca durante estos bloques, y la unión final en `queries/services.py`.

### Etapa 4 · Corpus real, calibración y evals

De a uno, con los servicios reales. Necesita el corpus en `corpus/normativa/`, las fechas de vigencia informadas (2003-06-14 para la 297/03 y 2023-01-01 para la 247/2022), que escribe una persona al cargar, el archivo de modificatorias y el conjunto de preguntas con visto bueno.

1. Cargar y validar el corpus: `disp-afip-297-2003-original.htm` como cuerpo de la 297/03; `disp-afip-247-2022-original.htm` como cuerpo y `disp-afip-247-2022-anexo.pdf` como anexo de la 247/2022; las dos normas, con la marca de régimen general. Ajustar las reglas de partición contra los documentos reales.
2. Anotar las modificatorias sin cargar de la 297/03 con `registrar_modificatorias`; registrar la relación `deroga` de la 247/2022 sobre la 297/03 con su fecha (2023-01-01), y las demás relaciones y versiones del corpus. Comprobar el cambio de régimen consultando el día anterior a la entrada en vigencia (2022-12-31) y ese mismo día (2023-01-01).
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
| Que `POST /tokenize` responda en la compilación fijada y cuánto agrega la plantilla de conversación | Se cuentan con `/tokenize` las partes de un pedido de prueba y se compara la suma con `prompt_tokens` del campo `usage` de la respuesta. La diferencia tiene que quedar por debajo del margen de 512; si no, se ajusta el parámetro |
| Que un pedido que no entra en el contexto se rechace en lugar de recortarse | Se envía un pedido de más de 16.384 tokens; el servidor responde con error. La documentación dice que el corrimiento de contexto viene apagado y hay un reporte de rechazo con error 400; no está probado en esta compilación |
| Calidad en español jurídico | Evals de la etapa 4 |

### Embeddings y reranker (etapa 0)

| Sin verificar | Prueba que lo cierra |
|---|---|
| Que los archivos GGUF de `bge-m3` y `bge-reranker-v2-m3` carguen en la compilación fijada. Son conversiones de un tercero hechas con versiones viejas de `llama.cpp` | Los dos servicios levantan y `/health` responde |
| Que den los mismos resultados que el modelo original | Embeddings: las cuatro frases de ejemplo de la ficha de `bge-m3` dan similitudes a menos de 0,02 de las publicadas (0,6265; 0,3477; 0,3499; 0,678). Reranker: los dos pares de ejemplo de la ficha de `bge-reranker-v2-m3` dan valores cercanos a los publicados (−8,19 y 5,26; con sigmoide, 0,0003 y 0,995) y en el mismo orden. Si no se cumple, plan B |
| Qué escala devuelve el reranker | Se observa en la prueba anterior; la aplicación guarda siempre el valor entre 0 y 1 |
| Que una entrada más larga que el límite se rechace en lugar de recortarse | Se envía un texto de más tokens que el contexto; el servidor responde con error |
| Que `POST /tokenize` responda en un servidor levantado para embeddings, y que el reranker cuente igual. La documentación no lo dice | Se cuenta el mismo texto en `embeddings` y en `reranker`; las dos cuentas coinciden, salvo los tokens especiales. Si `embeddings` no responde a `/tokenize`, se informa antes de seguir: el conteo de pasajes depende de esto |
| Plan B: cómo cuenta tokens Text Embeddings Inference | Solo si hace falta el plan B. No lo pude comprobar en su documentación; se prueba sobre esa imagen |
| Memoria de video de cada uno y total | `nvidia-smi` con los tres modelos cargados y después de puntuar 65 pasajes; total dentro de 20 GB |
| Tiempo del reranker con 65 pasajes y de la recuperación completa | Se mide; la meta del ADR-0003 es 3 segundos |
| Plan B: imagen experimental de Text Embeddings Inference para la serie RTX 50, con estos modelos, bajo WSL2 | Solo si hace falta: las mismas pruebas sobre esa imagen |

Cerrado en la etapa 0 (`entorno.md`, T-003), sin plan B: los dos modelos cargan; `bge-m3` reproduce la ficha a menos de 0,0011; el reranker la reproduce con el parámetro de la adenda del ADR-0003; el reranker devuelve el valor sin escala; entrada larga rechazada con HTTP 500 (ver "Conteo de tokens"); `/tokenize` da listas idénticas en los dos; 10.344 MiB con los tres modelos cargados; 1,1 s para 65 pasajes (3,45 s el primer pedido después de arrancar).

### Postgres (etapa 0)

| Sin verificar | Prueba que lo cierra |
|---|---|
| Versión exacta de pgvector y etiqueta de imagen | `SELECT extversion FROM pg_extension`; se fija la etiqueta en `docker-compose.yml` |
| Que la imagen traiga `unaccent` y la configuración `spanish` | `CREATE EXTENSION unaccent` y `\dF` |
| Que la configuración propia encuentre palabras sin tilde | Cerrado en T-004 para la definición anterior, que además rompía singular y plural en "-ación" y "-ución". La definición del ADR-0007 la comprueba T-009: cada forma de "licitación", "adjudicación", "contratación", "artículo" y "garantía", con y sin tilde, en mayúsculas y en plural, encuentra las demás de su familia, y "297/03" y "247/2022" se encuentran a sí mismos |
| Cómo se tratan los números con barra ("297/03", "247/2022") | Se observa con `ts_debug`; las referencias exactas no dependen de esto |
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
| Estructura real de los tres archivos del corpus. Lo que vi al preparar esta actualización está debajo de la tabla; no leí los tres archivos completos | Las reglas y las tablas esperadas se escriben contra los archivos de `corpus/normativa/` |
| Cuántos artículos tiene cada documento. Vi 99 en el índice del anexo de la 247/2022 y 5 en su cuerpo; de la 297/03, 5 en la disposición y un índice del Anexo I que llega al 64 | Las tablas esperadas escritas a mano y el control de secuencia del informe de lectura |
| Qué unidad le corresponde a la cláusula transitoria del anexo de la 247/2022: resuelto el 2026-10-02, es una unidad `clausula` (ver "Texto normativo sin número de artículo"). Queda por comprobar que la regla la reconozca en el archivo real, con sus dos párrafos y sin la firma | La tabla esperada del anexo la incluye como `anexo/clausula-transitoria`, después de `anexo/art-99`; el informe de lectura la cuenta entre las unidades y no la da como no ubicada |
| Que la página 45 del anexo, que solo tiene la firma digital, se lea como cierre y firma | Informe de lectura del documento real |
| Documentos de las otras categorías (marco nacional, dictámenes, recomendaciones) | Todavía no están en el corpus; sus reglas se prueban con documentos sintéticos hasta que lleguen |
| Calidad de Tesseract en español sobre escaneos de normas; umbrales de confianza (80 y 50) | Prueba de REQ-015: proporción de palabras del escaneado que coincide con el PDF con texto; los umbrales se ajustan con escaneos reales |
| Versión de Tesseract y modelo de español en la imagen | Se incorpora `spa.traineddata` de `tessdata_best` con su huella; la imagen informa su versión |

Lo que vi en los archivos del corpus, para quien escriba las reglas:

- **`disp-afip-297-2003-original.htm`.** Página de Infoleg con párrafos `<P>` y bloques `<DIR>`, letras acentuadas escritas como entidades (`&oacute;`) y el signo de grado como carácter suelto; el manifiesto indica codificación windows-1252. La disposición tiene cinco artículos con la forma `ARTICULO 1° —`. Sigue "ANEXO I - DISPOSICION N° 297/03 (AFIP)", un índice con las formas `ARTICULO 1.- OBJETO`, `ARTICULO 20 -`, `ARTICULO 27.` y `ARTICULO 29-`, y después el articulado con `ARTICULO 2° —`, `ARTICULO 11. —`, `ARTICULO 12.—` y `ARTICULO 13 —`. Los títulos y capítulos van en líneas propias.
- **`disp-afip-247-2022-original.htm`.** Página de Infoleg que declara ISO-8859-1, con el texto en un solo bloque separado por `<br>` y comillas como entidades numéricas. Trae visto, siete considerandos, cinco artículos con la forma `ARTÍCULO 1°.-`, la firma, la nota del Boletín Oficial sobre los anexos y una nota de Infoleg al pie. Tiene scripts de medición en el encabezado.
- **`disp-afip-247-2022-anexo.pdf`.** 45 páginas con texto. Empieza con una carátula ("ANEXO", número de documento, referencia) y la línea "ANEXO (artículo 1°)". El índice ocupa de la página 1 a la 5 y escribe los artículos como `ARTÍCULO 1º.- OBJETO`; el articulado empieza en la página 5 y los escribe `ARTÍCULO 1°.- OBJETO.` con el texto a continuación, y `ARTÍCULO 10.-` sin signo. Títulos de I a VII, con capítulos. Incisos con letra y paréntesis. Después del artículo 99, en la página 44, hay una "CLÁUSULA TRANSITORIA REGISTRO DE PROVEEDORES" de dos párrafos; el encabezado va en una línea propia, en mayúsculas y en negrita, como los títulos, y el índice no la lista. La página 45 trae solo la firma digital. No vi encabezados ni pies repetidos en las páginas que abrí (1 a 6, 44 y 45).

### Dos regímenes y modificatorias (etapa 4)

| Sin verificar | Prueba que lo cierra |
|---|---|
| Fecha de entrada en vigencia de la Disposición 247/2022: resuelto el 2026-10-02. Es el 2023-01-01, informada por el responsable (ADR-0006, "Datos registrados"). El sistema no la calcula y este plan tampoco | Se escribe al cargar los dos documentos y al registrar la relación `deroga` |
| Fecha de vigencia de la Disposición 297/03: resuelto el 2026-10-02. Es el 2003-06-14, el día siguiente a su publicación del 13/6/2003, según su propio texto (ADR-0006, "Datos registrados") | Se escribe al cargarla |
| Que las tres fechas de la 247/2022 queden iguales | Consulta en la pantalla con el día anterior a la entrada en vigencia (2022-12-31) y con ese día (2023-01-01): en cada una, un régimen aplicado y solo uno |
| Contenido del archivo de modificatorias de la 297/03 | Lo preparan el Coordinador y el responsable a partir del listado de Infoleg guardado. El listado trae 33 normas; una es la propia 247/2022. El nombre de algunas dependencias aparece cortado en el listado y hay que completarlo |
| Qué son las 33 normas del listado. Por sus descripciones, varias no modifican el régimen: aprueban una licitación, designan una comisión o delegan una competencia | Se sabe al cargar cada una. Mientras tanto cuentan todas en el aviso, como pide la spec |

### Pantalla (etapa 3)

| Sin verificar | Prueba que lo cierra |
|---|---|
| Qué navegador usa la Comisión | Lo informa el responsable |
| Que el visor de PDF abra en la página citada y que el aislamiento de una página web guardada funcione | Prueba a mano en ese navegador, una vez |
| Que el campo de fecha se vea y se complete bien en ese navegador, con día, mes y año en el orden habitual | La misma prueba a mano |

## Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El corpus de la feature se limita a la 297/03 y la 247/2022 (decisión del 2026-10-03) | Las reglas para dictámenes y recomendaciones y las preguntas de REQ-018 y REQ-019 no se escriben contra documentos reales | Se prueban con documentos sintéticos; las evals de esos requisitos quedan con casos sintéticos hasta que se cargue material real |
| La fecha de entrada en vigencia de la 247/2022 se registra mal, o distinta en alguno de sus tres lugares | Consultas respondidas con el régimen equivocado, o días sin régimen o con dos | La escribe el responsable de normativa, no el sistema. La pantalla muestra siempre qué régimen aplicó, y nombra los dos o ninguno si eso encuentra. La carga del corpus consulta el día anterior y el día de entrada en vigencia. Cada registro queda con su usuario |
| Se responde con el texto de 2003 de la 297/03 un punto que una modificatoria sin cargar cambió | Respuesta desactualizada para procedimientos anteriores a la 247/2022 | Aviso con la cantidad de modificatorias sin cargar en toda respuesta o búsqueda que muestre la 297/03 (REQ-021). La profundidad con que se cargan la decide el responsable (ADR-0006) |
| El aviso deja de contar una modificatoria cuando se registra su primera relación, aunque traiga más cambios | Por un rato el aviso muestra una menos de las que faltan registrar | La persona registra todas las relaciones de una modificatoria en la misma sesión; cada relación queda en el registro. Si se quiere un cierre expreso por modificatoria, es un requisito nuevo |
| La persona elige una fecha que no es la de autorización del procedimiento | Respuesta correcta para otra fecha | La línea de fecha y régimen figura en toda respuesta y en el registro; el campo trae la del día y el texto del campo dice qué fecha se pide |
| El margen para la plantilla de conversación no alcanza | El motor rechaza el pedido y la consulta termina en falla técnica | Se mide en la etapa 0; el margen es un parámetro; el rechazo se registra con su motivo |
| Gemma 4 12B no alcanza 85 % o 90 % | No pasa la verificación | Escalera del ADR-0002, con medición en cada paso; hay unos 11 GB libres según las estimaciones |
| Una consulta no entra en 30 segundos | No cumple el tiempo de la spec | Se mide en la etapa 0. Reducir unidades por categoría o el tope de salida; son parámetros |
| `bge-m3` o el reranker no funcionan bien en `llama-server` | La búsqueda trae mal o no arranca | Prueba contra valores publicados en la etapa 0; plan B con Text Embeddings Inference; solo cambian dos clientes |
| La memoria de video real supera el reparto | Los servicios no cargan o se vuelven lentos | Se mide en la etapa 0, antes de construir |
| Las reglas de partición no reconocen un documento, en especial dictámenes y recomendaciones | Ese documento queda sin validar | Se ve en el informe; se agrega una regla y se relee con `releer_norma`. Condición para la alternativa L del ADR-0004 |
| Un escaneo se lee mal | Texto citado distinto del impreso | Marca de reconocimiento en la unidad y en la cita; palabras dudosas en el informe; la persona decide si valida |
| Umbral calibrado con pocas preguntas, repartidas además entre dos regímenes | Abstención peor que la medida; un régimen puede quedar medido con muy pocos casos | Calibración dejando una afuera; un solo umbral para los dos regímenes; valor provisorio; medidas por régimen como diagnóstico; recalibrar si cambia el corpus |
| "Respuesta correcta" medida solo de forma automática | Una afirmación errónea junto a la cita correcta pasaría | Revisión del responsable en la corrida que se presenta para aprobar |
| Una relación o una versión mal registrada | Respuestas con un cambio que no corresponde | Las operaciones quedan registradas con su usuario. No hay comando para anularlas porque ningún requisito lo pide; si ocurre, se corrige con una tarea |
| Quien administra el equipo puede entrar a la base | El registro no protege contra esa persona | Límite conocido (ADR-0005); el control de acceso al equipo queda fuera del sistema |

## Qué tiene que decidir el responsable

Las decisiones del plan original ya están tomadas y figuran más abajo. Por la actualización del ADR-0006 quedan estas:

1. **Aprobar esta actualización del plan.** Recomendado: aprobar. El detalle de lo que cambió está en "Actualización por ADR-0006".
2. **Fecha de autorización posterior al día.** Recomendado: rechazarla en el formulario. El sistema no puede saber qué normas van a regir, y responder sería afirmar sin sustento. Se pierde poder consultar para un procedimiento que se va a autorizar en los próximos días; para eso alcanza con usar la fecha del día.
3. **Fecha sin régimen específico cargado** (por ejemplo, anterior a la 297/03). Recomendado: "no determinado", sin buscar. La alternativa es responder con lo que haya del marco nacional y avisar que falta el régimen; se descartó porque daría por aplicable un marco que no desplaza al régimen específico.
4. **Reparto de las preguntas de las evals entre los dos regímenes.** Recomendado: la mayoría con fecha bajo la 247/2022, que es lo que la Comisión usa hoy, y no menos de ocho con fecha bajo la 297/03, incluido el par que repite una pregunta con dos fechas. Hay que tener presente que las respuestas bajo la 297/03 se miden contra el texto de 2003, sin sus modificatorias.
5. **Las modificatorias que no modifican.** El listado de Infoleg junta las normas que modifican la 297/03 con las que solo la complementan o la citan, como la aprobación de una licitación. Según la spec, el aviso desaparece cuando están cargadas las 33. Recomendado: dejarlo así por ahora y revisarlo cuando se decida con qué profundidad se cargan (ADR-0006). Sacar una norma del listado sin cargarla sería un requisito nuevo.
6. **Búsqueda por palabras (ADR-0007).** Decidido: el responsable aprobó la alternativa D el 2026-10-02: normalizar texto y consulta quitando acentos y reponiendo la tilde de "-ación" y "-ución", y reducir a la raíz con `spanish`. Se pierde: una regla propia de dos terminaciones que mantener, y recalcular `tsv` al cambiar de versión mayor de Postgres.

La cláusula transitoria del anexo de la 247/2022 y las fechas de entrada en vigencia, que figuraban en esta sección, quedaron resueltas el 2026-10-02 y pasaron a "Decisiones tomadas".

No son decisiones, pero hacen falta:

- Los documentos de las otras categorías y las modificatorias de la 297/03, a medida que se decida cargarlas.

### Decisiones tomadas

El responsable aprobó el plan el 2026-10-02 con las cinco recomendaciones que traía:

1. Plan y ADR 0002 a 0005 aprobados. El modelo y el servidor de embeddings quedan sujetos a la etapa 0 y a las evals.
2. Comandos en español.
3. Evals: criterios automáticos en cada corrida y revisión del responsable en la corrida que se presenta para aprobar.
4. Clave de 15 caracteres como mínimo; sesión de 8 horas y hasta cerrar el navegador; metas de recuperación como diagnóstico.
5. Equipo confirmado: Intel Core Ultra 9, 32 GB de RAM, RTX 5090 de notebook con 24 GB de memoria de video. La etapa 0 lo comprueba igual con `nvidia-smi`.

El corpus inicial era la Disposición AFIP 297/03. El mismo día, por el ADR-0006, el responsable decidió trabajar con los dos regímenes: el corpus inicial pasa a ser la Disposición 297/03 con su texto de 2003 y la Disposición 247/2022 con su anexo. Las modificatorias de la 297/03 se anotan como no cargadas y se cargan de a poco.

Resueltas el 2026-10-02, después de presentada la actualización por el ADR-0006:

- **Fechas de entrada en vigencia.** Disposición 247/2022: 2023-01-01, informada por el responsable. Disposición 297/03: 2003-06-14, el día siguiente a su publicación del 13/6/2003. Las escribe una persona al cargar cada norma y al registrar la relación `deroga`; el sistema no las calcula.
- **Cláusula transitoria del anexo de la 247/2022.** Es una unidad citable propia, con el nombre que le da el documento, ubicada después del artículo 99: tipo `clausula`, clave `anexo/clausula-transitoria`, ruta "Anexo › Cláusula transitoria". Sin número y sin usar el tipo `parrafo`. Vale para todo texto normativo con título propio y sin número (REQ-003).

## Actualización por ADR-0006

Fecha: 2026-10-02. Aprobada por el responsable el 2026-10-02. Esta sección lista qué cambió en el plan aprobado y por qué, para poder revisar solo el cambio.

**Motivo.** Al cargar el corpus se comprobó que la Disposición 247/2022 abrogó la 297/03. El responsable decidió trabajar con los dos regímenes según la fecha de autorización del procedimiento (ADR-0006). La spec sumó REQ-020 y REQ-021, y la fecha de referencia dejó de ser siempre la del día.

**Qué no cambió.** Los servicios, los modelos, la memoria de video, la forma de leer y partir documentos, los tres caminos de búsqueda, el reranker, la regla de cita literal, el acceso, las migraciones y el respaldo. Las funciones de fecha ya existían: cambia de dónde sale la fecha.

| Sección | Qué cambió | Por qué |
|---|---|---|
| Encabezado | Línea de actualización; los cinco ADR figuran como aceptados | Texto desactualizado; ADR-0006 |
| En pocas palabras | La pantalla pide la fecha de autorización, muestra el régimen aplicado y avisa cuando faltan modificatorias; una norma puede venir en dos archivos; el corpus ya tiene los dos regímenes | REQ-020, REQ-021 |
| Resumen del enfoque; Componentes | La fecha de autorización llega a `consultable_units(fecha)`; los clientes de IA suman contar tokens | REQ-020; conteo de tokens |
| Estructura del código | `amendments.py`, `registrar_modificatorias`, `applicable_regimes`; el corpus ya no está vacío | REQ-021, REQ-020 |
| Modelo de datos · `audit_event` | Hecho nuevo `pending_amendment` | REQ-021, REQ-012 |
| Modelo de datos · `norms_norm` | Campo `general_regime` | REQ-020: saber qué norma es "el régimen" |
| Modelo de datos · `norms_document` | Campo `part`; un documento en uso por norma, parte y versión; se precisa que `effective_from` lo escribe la persona | Norma en dos archivos; ADR-0006 |
| Modelo de datos · `norms_relation` | Cómo se registra la abrogación de la 297/03; las claves se comprueban en todas las partes | ADR-0006 |
| Modelo de datos · `norms_pending_amendment` | Tabla nueva | REQ-021 |
| Modelo de datos · `norms_corpus_version`, `queries_query` | Versión nueva al anotar modificatorias; `reference_date` es la fecha de autorización; `result` suma fecha, régimen y avisos | REQ-020, REQ-021 |
| Identificación de unidades | Ejemplos con la 247/2022; la búsqueda por artículo recorre todas las partes | Norma en dos archivos |
| Una norma en más de un archivo (nueva) | Parte del documento, unidad raíz del anexo, control de claves, duplicados | La 247/2022 son dos archivos; REQ-011 |
| Unidades consultables a una fecha | La fecha es la de autorización; derogada quiere decir derogada a esa fecha; función `applicable_regimes`; tabla de los dos regímenes; se quitó que la pantalla pasa siempre la fecha del día | REQ-020, ADR-0006 |
| Versiones de una norma | Las versiones son por parte | Norma en dos archivos |
| Modificatorias sin cargar (nueva) | Qué se anota, cómo se carga en lote, cómo pasa a cargada, qué cuenta el aviso | REQ-021 |
| Flujo de IA · Ingesta | `--parte` y `--regimen-general`; tercer caso en duplicados | Norma en dos archivos; REQ-020 |
| Flujo de IA · Fecha de autorización y régimen aplicado (nueva) | De dónde sale la fecha, validación, fecha futura, fecha sin régimen, línea de régimen, qué se guarda | REQ-020 |
| Flujo de IA · Recuperación, Reordenamiento, Generación | La entrada es la fecha de autorización; el espacio descuenta un margen; el modelo recibe la fecha | REQ-020; conteo de tokens |
| Flujo de IA · Conteo de tokens (nueva) | `POST /tokenize` de cada servidor; margen de 512; motivo `input_too_long` | Definición que faltaba para T-031 y T-033 |
| Flujo de IA · Abstención | Cuarta causa: sin régimen a la fecha (`no_regime_at_date`) | REQ-020, REQ-009 |
| Flujo de IA · Búsqueda directa | Se hace para la fecha del formulario; línea de régimen y avisos | REQ-020, REQ-021 |
| Flujo de IA · Aviso de modificatorias sin cargar (nueva) | Cómo llega el aviso a la respuesta, a la búsqueda y a la pantalla | REQ-021 |
| Flujo de IA · Forma de la respuesta | `reference_date`, `regime`, `notices`; motivos nuevos; ejemplo con la 297/03 como página web | REQ-020, REQ-021 |
| Pantalla, acceso y comandos | Campo de fecha en los dos formularios; línea de régimen; recuadro de aviso; comando `registrar_modificatorias`; opciones nuevas de `cargar_norma`; los comandos en español ya están decididos | REQ-020, REQ-021; texto desactualizado |
| Registro de auditoría | Fecha de autorización, régimen y avisos en consulta y búsqueda; hecho de modificatorias; parte en carga y versión | REQ-012 con REQ-020 y REQ-021 |
| Evals | Campos `fecha_autorizacion`, `regimen`, `pareja` y `aviso_modificatorias`; composición por régimen; pares y aviso informados aparte; el régimen entra en "respuesta correcta" | REQ-020, REQ-021 |
| Cobertura de requisitos | Filas de REQ-020 y REQ-021; ajustes en REQ-002, 003, 007, 010, 011, 012 y 015 | 21 requisitos |
| Verificación contra la constitución | P1, P2, P3, P8, P10 y P11 | Constitución 1.1; texto desactualizado |
| Decisiones | ADR-0006 en la tabla; los cinco ADR aceptados; decisiones 14 a 21 | ADR-0006; texto desactualizado; REQ-003 |
| Orden de construcción | Trabajos de personas; etapa 2 con el anexo de la 247/2022; bloques C, D, E, F, H, I y K ajustados y bloque L nuevo; etapa 4 con los tres archivos, las modificatorias y la derogación | Corpus real; REQ-020, REQ-021 |
| Sin verificar y cómo se cierra | Conteo de tokens en la etapa 0; lo visto en los tres archivos; grupo nuevo de regímenes y modificatorias; campo de fecha en el navegador | Corpus real; ADR-0006 |
| Riesgos | Corpus incompleto en lugar de ausente; fecha de vigencia mal registrada; texto de 2003 sin modificatorias; cierre del aviso; fecha mal elegida; margen del contexto | ADR-0006, REQ-020, REQ-021 |
| Qué tiene que decidir el responsable | Cinco decisiones de esta actualización y dos datos que hacen falta; la cláusula transitoria y las fechas de vigencia pasaron a "Decisiones tomadas" | Compuerta de la actualización |

**Hilo mínimo.** Antes se hacía con la Disposición 297/03 en un PDF que había que conseguir o generar. Ahora se hace con `disp-afip-247-2022-anexo.pdf`, que ya está en el corpus.

**Ajustes del 2026-10-02 por dos definiciones del responsable.** Primero, las fechas de entrada en vigencia ya están informadas (247/2022: 2023-01-01; 297/03: 2003-06-14) y dejaron de figurar como faltantes en "En pocas palabras", "Modelo de datos", "Unidades consultables a una fecha", "Evals", "Orden de construcción", "Sin verificar y cómo se cierra" y "Qué tiene que decidir el responsable". Segundo, la cláusula transitoria del anexo de la 247/2022 es una unidad de tipo `clausula`, con clave `anexo/clausula-transitoria`: tipo nuevo en `norms_unit.unit_type`, sección nueva "Texto normativo sin número de artículo", fila de REQ-003 en "Cobertura de requisitos" y decisión 21.

**Frases de otros documentos que quedaron atrás.** Este plan no los modifica; se informan al Coordinador:

- ADR-0003, "Fecha de referencia en la pantalla": dice que es la del día y que la pantalla no permite elegirla.
- ADR-0004: dice que `corpus/normativa/` está vacío, describe la estructura de la 297/03 a partir de una lectura incompleta de la página y prevé su tabla esperada con página de inicio; el archivo del corpus es una página web y no tiene páginas. Además, su tabla "Cómo se parte" no tiene la fila del texto normativo sin número de artículo, la lista de `unit_type` de "Qué lleva cada unidad" no tiene `clausula`, y su cita de REQ-003 es la anterior al cambio de la spec.
- ADR-0005: su tabla de comandos no tiene `registrar_modificatorias` ni las opciones `--parte` y `--regimen-general`.
- Spec, "Volumen" y aclaración sobre modificatorias: hablan de 33 modificatorias sin cargar. El listado de Infoleg tiene 33 normas, pero una es la Disposición 247/2022, que se carga; quedan 32.
- `evals/README.md`: su formato de partida no tiene la fecha de autorización. El formato vigente para esta feature es el de la sección "Evals" de este plan, como ese mismo archivo indica.

## Ajustes por la etapa 0

Fecha: 2026-10-02. Lo medido en `entorno.md` (T-001 a T-005) que cambia el diseño. Lo que solo afecta al runbook no figura acá.

| Sección | Qué cambió | Estado |
|---|---|---|
| Servicios (tabla y plan B) | El reranker arranca con `--override-kv tokenizer.ggml.add_sep_token=bool:true`; no fue el plan B | Decidido por el responsable (ADR-0003, adenda) |
| Modelo de datos (`tsv`, migraciones) y sección nueva "Búsqueda por palabras: tildes, singular y plural" | `spanish_unaccent` reemplazada por `search_normalize`, `search_document` y `search_query` | Aprobado (ADR-0007) |
| Recuperación; Búsqueda directa; Etapa 1 | Usan `search_query` | Aprobado (ADR-0007) |
| Conteo de tokens | Plantilla medida en 18 tokens; el margen sigue en 512. Rechazo de entrada larga con HTTP 500 en `embeddings` y `reranker`, a reconocer por el mensaje en T-011 | Anotación |
| Sin verificar | Cierre de embeddings y reranker; la prueba de búsqueda sin tilde pasa a T-009 | Anotación |
| Decisiones; Qué tiene que decidir el responsable | Decisiones 22 y 23; decisión 6 | — |

