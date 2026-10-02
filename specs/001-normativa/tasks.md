# Tareas 001 · Normativa consultable con cita

Plan: `specs/001-normativa/plan.md`

Despliegue: pendiente

> El tablero (`docs/tablero.md`) se genera de este archivo. Al aprobarse el despliegue, la línea de arriba pasa a `Despliegue: aprobado AAAA-MM-DD`.

Estados: pendiente · en curso · en verificación · terminada · bloqueada

Dos tareas que no dependen entre sí y no comparten archivos se pueden hacer en paralelo.

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-001 | Comprobar la GPU dentro de un contenedor | REQ-008 | — | pendiente |
| T-002 | Levantar el motor de generación y medir su velocidad | REQ-008, REQ-009 | T-001 | pendiente |
| T-003 | Levantar embeddings y reranker y medir la memoria de video | REQ-008, REQ-009 | T-002 | pendiente |
| T-004 | Fijar Postgres con sus extensiones y búsqueda en español | REQ-008, REQ-010 | T-003 | pendiente |
| T-005 | Armar el esqueleto de Django con sus librerías | REQ-013, REQ-016 | T-004 | pendiente |
| T-006 | Crear usuarios con rol, ingreso y salida | REQ-016 | T-005 | pendiente |
| T-007 | Crear el registro de auditoría y el alta de usuarios | REQ-012, REQ-016 | T-006 | pendiente |
| T-008 | Crear las tablas de normas, lecturas, unidades y pasajes | REQ-001, REQ-003, REQ-011, REQ-012, REQ-017 | T-007 | pendiente |
| T-009 | Crear las funciones de unidades consultables a una fecha | REQ-005, REQ-007, REQ-010 | T-008 | pendiente |
| T-010 | Crear la tabla del registro detallado de consultas | REQ-012 | T-009 | pendiente |
| T-011 | Crear los clientes de IA, sus dobles y los parámetros | REQ-008, REQ-009 | T-010 | pendiente |
| T-012 | Leer un PDF con texto | REQ-004, REQ-015 | T-008 | pendiente |
| T-013 | Partir en artículos y armar el informe mínimo | REQ-003, REQ-004 | T-012 | pendiente |
| T-014 | Cargar una norma, listarla y ver su informe | REQ-001, REQ-002, REQ-004, REQ-012, REQ-017 | T-013 | pendiente |
| T-015 | Validar una lectura y calcular pasajes y vectores | REQ-005, REQ-012 | T-011 | pendiente |
| T-016 | Armar la pantalla de consulta con sus tres bloques | REQ-013, REQ-014 | T-010 | pendiente |
| T-017 | Recuperar por significado y reordenar con el reranker | REQ-005, REQ-008, REQ-009 | T-011 | pendiente |
| T-018 | Generar la respuesta con esquema e insertar las citas | REQ-008, REQ-009 | T-017 | pendiente |
| T-019 | Unir la consulta de punta a punta con su registro | REQ-008, REQ-009, REQ-012, REQ-013 | T-016, T-018 | pendiente |
| T-020 | Probar el hilo mínimo con los servicios reales | REQ-008, REQ-012, REQ-013 | T-014, T-015, T-019 | pendiente |
| T-021 | Leer un PDF escaneado con reconocimiento de texto | REQ-004, REQ-015 | T-012 | pendiente |
| T-022 | Leer una página web guardada | REQ-015 | T-012 | pendiente |
| T-023 | Partir normas completas con incisos, anexos y considerandos | REQ-003 | T-013 | pendiente |
| T-024 | Partir dictámenes y recomendaciones en puntos y párrafos | REQ-003 | T-023 | pendiente |
| T-025 | Completar el informe de lectura | REQ-004, REQ-015 | T-024 | pendiente |
| T-026 | Avisar duplicados al cargar una norma | REQ-011, REQ-012 | T-014, T-025 | pendiente |
| T-027 | Releer un documento y reemplazar la lectura anterior | REQ-004, REQ-005 | T-015, T-026 | pendiente |
| T-028 | Integrar los tres formatos en la carga | REQ-004, REQ-015 | T-021, T-022, T-027 | pendiente |
| T-029 | Registrar relaciones entre normas y mostrar los vínculos | REQ-006, REQ-007 | T-009, T-014 | pendiente |
| T-030 | Registrar versiones de una norma | REQ-007 | T-015 | pendiente |
| T-031 | Partir en pasajes las unidades largas | REQ-003, REQ-008 | T-015 | pendiente |
| T-032 | Recuperar por tres caminos y unir los candidatos | REQ-005, REQ-008 | T-019 | pendiente |
| T-033 | Seleccionar por categoría, sumar cambios y ordenar | REQ-007, REQ-018, REQ-019 | T-032 | pendiente |
| T-034 | Completar instrucciones, marca de regímenes y orden | REQ-008, REQ-009, REQ-018, REQ-019 | T-019 | pendiente |
| T-035 | Buscar unidades por artículo y por palabras | REQ-005, REQ-006, REQ-010 | T-010 | pendiente |
| T-036 | Entregar el documento original con sesión | REQ-002 | T-008 | pendiente |
| T-037 | Mostrar las citas con categoría, papel y cambios | REQ-007, REQ-013, REQ-014, REQ-015, REQ-018, REQ-019 | T-019, T-036 | pendiente |
| T-038 | Registrar ingresos, ingresos fallidos y rechazos por rol | REQ-012, REQ-016 | T-014, T-015 | pendiente |
| T-039 | Correr el conjunto de preguntas y medir las exigencias | REQ-008, REQ-009 | T-019 | pendiente |
| T-040 | Unir recuperación y generación completas con su registro | REQ-008, REQ-009, REQ-012, REQ-018, REQ-019 | T-033, T-034 | pendiente |
| T-041 | Mostrar y registrar la búsqueda en la pantalla | REQ-006, REQ-010, REQ-012 | T-035, T-037, T-040 | pendiente |
| T-042 | Agregar calibración del umbral y comparación de corridas | REQ-008, REQ-009 | T-039, T-040 | pendiente |
| T-043 | Cargar y validar el corpus real y ajustar las reglas | REQ-003, REQ-004, REQ-005, REQ-015 | T-020, T-028, T-031, T-041 | pendiente |
| T-044 | Registrar las relaciones y versiones del corpus | REQ-006, REQ-007 | T-029, T-030, T-043 | pendiente |
| T-045 | Calibrar el umbral con el conjunto de preguntas | REQ-009 | T-042, T-044 | pendiente |
| T-046 | Correr las evals y medir tiempo y memoria | REQ-008, REQ-009, REQ-018, REQ-019 | T-045 | pendiente |
| T-047 | Probar una consulta con la red desconectada | REQ-008, REQ-013 | T-038, T-046 | pendiente |
| T-048 | Probar el respaldo y la restauración de la base | REQ-002, REQ-012 | T-047 | pendiente |
| T-049 | Levantar todo desde cero y dejar datos para el runbook | REQ-012, REQ-016 | T-048 | pendiente |

## Detalle

**Reglas comunes a todas las tareas.**

- **Suite.** En la MSI, con los seis servicios arriba: `docker compose run --rm app pytest`. En cualquier equipo con Docker, sin placa de video: `docker compose up -d db` y después `docker compose run --rm --no-deps app pytest`; la suite usa los dobles de los tres clientes de IA y no necesita los servicios `generation`, `embeddings` ni `reranker`. "Suite en verde" significa la suite completa, no solo el test de la tarea.
- **Tests.** Cada tarea escribe primero el test que demuestra el requisito, en un archivo de test propio (el que figura en "Archivos"). Cada test nombra su `REQ-NNN` en el docstring. Los datos de prueba van en `tests/fixtures/`, en archivos con nombre propio de la tarea, y son públicos o sintéticos.
- **Archivos compartidos.** `evaluon/settings.py`, `evaluon/urls.py`, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `.env.example`, `tests/conftest.py`, todo `models.py` y toda carpeta `migrations/` solo los toca la tarea que los lista en "Archivos". Si otra tarea descubre que necesita cambiarlos, se detiene y lo informa.
- **Nunca se tocan:** `specs/001-normativa/spec.md`, `specs/001-normativa/plan.md`, `docs/adr/`, `corpus/` (lo carga el Coordinador; la aplicación lo monta en modo de solo lectura) y `evals/casos/` (lo redacta el Coordinador con el responsable y la Comisión).
- **Entorno.** "MSI con GPU": necesita la placa de video o los servicios de IA reales. "Cualquier equipo con Docker": corre con los dobles y Postgres en contenedor.
- **Texto literal.** Toda comprobación de cita usa una sola definición: el texto mostrado es igual, carácter por carácter, a `canonical_text[char_start:char_end]` de su lectura.

### Etapa 0 · Comprobación del entorno

De a una, en la MSI. No construye funciones: comprueba cada pieza y deja medido lo que hoy es estimación. Las cinco tareas comparten `docker-compose.yml` y `specs/001-normativa/entorno.md`, por eso van encadenadas. Los pedidos de prueba se hacen desde un contenedor de la red interna; los comandos y sus salidas quedan transcriptos en `entorno.md`, sin agregar scripts de prueba al repositorio.

### T-001 · Comprobar la GPU dentro de un contenedor

- **Requisitos:** REQ-008. No implementa un requisito funcional: habilita la generación local de REQ-008 y el tiempo de respuesta de la spec.
- **Qué hay que hacer:** confirmar los datos del equipo con `nvidia-smi` (modelo de placa y 24 GB de memoria de video); comprobar que Docker Desktop con WSL2 da acceso a la GPU con `docker run --rm --gpus all` sobre una imagen de CUDA y `nvidia-smi` adentro; leer cuánta memoria de video usa Windows con la pantalla activa y todos los servicios detenidos. Crear `entorno.md` con una sección por comprobación (qué se probó, comando, salida, resultado). El plan no define plan B: si la placa no se ve dentro del contenedor, la tarea queda bloqueada y se informa al responsable.
- **Archivos:** `specs/001-normativa/entorno.md` (se crea).
- **Verificación:** `docker run --rm --gpus all <imagen de CUDA> nvidia-smi` muestra la RTX 5090 con 24 GB; `entorno.md` trae las tres lecturas con su salida.
- **No tocar:** `docker-compose.yml` (lo crea T-002); cualquier archivo de código.
- **Entorno:** MSI con GPU

### T-002 · Levantar el motor de generación y medir su velocidad

- **Requisitos:** REQ-008, REQ-009. No implementa un requisito funcional: habilita la respuesta con esquema (REQ-008), la abstención del modelo (REQ-009) y el tiempo de 30 segundos.
- **Qué hay que hacer:** elegir y fijar la compilación de `llama.cpp` (`server-cuda-b<compilación>`); crear `docker-compose.yml` con la red interna sin salida a internet y el servicio `generation` (Gemma 4 12B de 4 bits de Google, contexto de 16.384, pensamiento apagado, `--offline`, `models/` montado en solo lectura, `/health`, sin puertos publicados); crear `scripts/fetch_models.sh` y `scripts/models.sha256` con el archivo del modelo y su huella. Probar: veinte pedidos con un esquema de prueba (lista cerrada de alias, al menos una cita por afirmación, máximo de afirmaciones), todas las salidas validan; la salida no trae razonamiento previo; un pedido de unos 12.000 tokens de entrada y 800 de salida, repetido cinco veces; memoria de video con el modelo cargado y después de una consulta larga. Condición: si el pedido largo no termina en menos de 25 segundos, se anota la medición y se informa al responsable antes de seguir con T-003.
- **Archivos:** `docker-compose.yml`, `.env.example`, `scripts/fetch_models.sh`, `scripts/models.sha256`, `specs/001-normativa/entorno.md`.
- **Verificación:** `docker compose up -d generation` y `/health` responde; `entorno.md` registra la compilación fijada, 20 de 20 salidas válidas, los cinco tiempos y la memoria medida. `scripts/fetch_models.sh` termina sin error y la huella coincide.
- **No tocar:** los servicios `embeddings`, `reranker`, `db`, `migrate` y `app` (T-003 a T-005).
- **Entorno:** MSI con GPU

### T-003 · Levantar embeddings y reranker y medir la memoria de video

- **Requisitos:** REQ-008, REQ-009. No implementa un requisito funcional: habilita la búsqueda por significado (REQ-008) y la señal de abstención del reranker (REQ-009).
- **Qué hay que hacer:** sumar a `docker-compose.yml` los servicios `embeddings` (`bge-m3`, GGUF FP16) y `reranker` (`bge-reranker-v2-m3`, GGUF FP16), con la misma imagen y compilación que `generation`; sumar los dos archivos a `scripts/fetch_models.sh` y `scripts/models.sha256`. Probar: los dos levantan y `/health` responde; las cuatro frases de ejemplo de la ficha de `bge-m3` dan similitudes a menos de 0,02 de 0,6265, 0,3477, 0,3499 y 0,678; los dos pares de ejemplo de la ficha del reranker dan valores cercanos a −8,19 y 5,26 (con sigmoide, 0,0003 y 0,995) y en el mismo orden; se anota la escala que devuelve el reranker; un texto más largo que el contexto se rechaza con error en lugar de recortarse; memoria de video de cada servicio y total con los tres modelos cargados y después de puntuar 65 pasajes; tiempo del reranker con 65 pasajes. Condición de plan B: si algún modelo no carga o no reproduce los valores publicados, se repiten las mismas pruebas con Text Embeddings Inference (imagen `120-1.9`), se anota el resultado y la tarea queda bloqueada hasta que el Coordinador haga actualizar el plan y el ADR-0003. Si el total supera 20 GB, no se avanza: se informa para revisar el reparto.
- **Archivos:** `docker-compose.yml`, `.env.example`, `scripts/fetch_models.sh`, `scripts/models.sha256`, `specs/001-normativa/entorno.md`.
- **Verificación:** `docker compose up -d generation embeddings reranker` con los tres en estado sano; `entorno.md` trae las similitudes, los puntajes, el rechazo de la entrada larga, la memoria total (dentro de 20 GB) y el tiempo del reranker.
- **No tocar:** el servicio `generation` y la compilación fijada en T-002; `db`, `migrate` y `app`.
- **Entorno:** MSI con GPU

### T-004 · Fijar Postgres con sus extensiones y búsqueda en español

- **Requisitos:** REQ-008, REQ-010. No implementa un requisito funcional: habilita los vectores (REQ-008) y la búsqueda por palabras sin distinguir acentos (REQ-010).
- **Qué hay que hacer:** sumar el servicio `db` a `docker-compose.yml` con la etiqueta exacta de `pgvector/pgvector` para Postgres 17, dentro de la red interna y sin puerto publicado. Antes de reemplazar el Postgres que ya corre en el equipo, confirmar que la base `evaluon` existente no tiene datos que conservar; si los tiene, detenerse e informar. Probar: `SELECT extversion FROM pg_extension` para `vector`; `CREATE EXTENSION unaccent`; `\dF` muestra `spanish`; una configuración de prueba derivada de `spanish` con `unaccent` encuentra "licitación" buscando "licitacion"; `ts_debug` sobre "297/03" y se anota cómo lo trata. El plan no define plan B: si la imagen no trae `unaccent` o `spanish`, la tarea queda bloqueada y se informa.
- **Archivos:** `docker-compose.yml`, `.env.example`, `specs/001-normativa/entorno.md`.
- **Verificación:** `docker compose up -d db` en estado sano; `entorno.md` registra la etiqueta fijada, la versión de pgvector y la salida de las cuatro pruebas.
- **No tocar:** los tres servicios de IA; no se crean migraciones (la configuración `spanish_unaccent` definitiva es de T-009).
- **Entorno:** MSI con GPU

### T-005 · Armar el esqueleto de Django con sus librerías

- **Requisitos:** REQ-013, REQ-016. No implementa un requisito funcional: habilita la pantalla (REQ-013) y el ingreso (REQ-016), y deja el entorno que se levanta con una orden.
- **Qué hay que hacer:** crear el proyecto Django 6.1 vacío (`manage.py`, `settings.py`, `urls.py`, `wsgi.py`) con psycopg 3 y la configuración por variables de entorno; `pyproject.toml` con todas las dependencias de la feature en versión fija (Django, psycopg, `pgvector`, `argon2-cffi`, Gunicorn, WhiteNoise, pytest, pytest-django, pdfplumber con pypdfium2, pytesseract, BeautifulSoup, lxml, y las de cliente HTTP y lectura de YAML solo si no alcanza la biblioteca estándar) y la configuración de pytest; `Dockerfile` sobre Python 3.12, con Tesseract y `spa.traineddata` de `tessdata_best` verificado por huella, sin PyTorch; servicios `migrate` (corre `scripts/migrate_on_start.sh`: aplica migraciones si la base está vacía, y si tiene datos solo comprueba con `migrate --check`) y `app` (Gunicorn, un proceso con hilos, espera de 120 s, puerto publicado solo en `127.0.0.1`, `corpus/` montado en solo lectura y `evals/` montado, espera a `db` y a los tres servicios de IA); carpetas de `tests/` con un test de humo. El test de humo comprueba: el proyecto arranca, WhiteNoise sirve un archivo estático, y se guarda y se lee un vector con la integración de `pgvector` para Django (con un modelo definido solo dentro del test). Condición de plan B: si WhiteNoise, pytest-django o `pgvector` fallan con Django 6.1, se fija Django 6.0 y se anota.
- **Archivos:** `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `.env.example`, `manage.py`, `evaluon/__init__.py`, `evaluon/settings.py`, `evaluon/urls.py`, `evaluon/wsgi.py`, `evaluon/static/` (hoja de estilos inicial), `scripts/migrate_on_start.sh`, `tests/conftest.py` (se crea vacío), `tests/__init__.py` y las carpetas `tests/accounts/`, `tests/audit/`, `tests/norms/`, `tests/queries/`, `tests/fixtures/`, `tests/test_skeleton.py`, `specs/001-normativa/entorno.md`.
- **Verificación:** `docker compose up -d` deja los seis servicios arriba (`docker compose ps`); `docker compose run --rm app pytest tests/test_skeleton.py` pasa; `docker compose run --rm app tesseract --version` informa la versión; `entorno.md` registra las versiones fijadas y la huella de `spa.traineddata`. También pasa con `--no-deps` y solo `db` arriba.
- **No tocar:** las imágenes y versiones fijadas en T-002 a T-004; no se crean aplicaciones de Django ni modelos (son de la etapa 1).
- **Entorno:** MSI con GPU

### Etapa 1 · Base común

De a una: todas tocan el esquema o la configuración compartida.

### T-006 · Crear usuarios con rol, ingreso y salida

- **Requisitos:** REQ-016
- **Qué hay que hacer:** crear la aplicación `accounts` con el modelo de usuario propio desde la primera migración (`role`: `read` o `read_write`); ingreso y salida con las vistas de Django; Argon2id como primer algoritmo; clave de 15 caracteres como mínimo, sin reglas de composición; sesiones en la base, 8 horas y hasta cerrar el navegador, cookie `HttpOnly` y `SameSite` estricto, identificador nuevo al ingresar, la salida anula la sesión; mensaje de error único ("Usuario o clave incorrectos"); toda página exige sesión salvo la de ingreso; política de contenido que solo permite recursos del propio servidor; plantillas base y de ingreso con tipografías del sistema; `permissions.py` con la comprobación de rol que van a usar las funciones de negocio; usuarios de prueba de los dos roles en `tests/conftest.py`. No se activa el panel de administración ni los grupos de Django. Después del ingreso se redirige a la raíz, que T-016 ocupa con la pantalla de consulta.
- **Archivos:** `evaluon/accounts/__init__.py`, `evaluon/accounts/apps.py`, `evaluon/accounts/models.py`, `evaluon/accounts/migrations/`, `evaluon/accounts/permissions.py`, `evaluon/accounts/views.py`, `evaluon/accounts/urls.py`, `evaluon/templates/` (base e ingreso), `evaluon/static/` (hoja de estilos), `evaluon/settings.py`, `evaluon/urls.py`, `tests/conftest.py`, `tests/accounts/test_login.py`, `tests/accounts/test_password_storage.py`, `tests/accounts/test_session.py`.
- **Verificación:** `pytest tests/accounts`. Cubre del criterio de REQ-016: sin sesión, cualquier página redirige al ingreso. Además: la clave guardada no es legible y lleva el identificador de Argon2id; sus parámetros igualan o superan el mínimo de OWASP (19 MiB, 2 iteraciones, 1 hilo); una clave de 14 caracteres se rechaza; con el reloj adelantado más de 8 horas la sesión venció; la salida anula la sesión en la base.
- **No tocar:** `evaluon/audit/` (T-007); el registro de ingresos y rechazos (T-038).
- **Entorno:** Cualquier equipo con Docker

### T-007 · Crear el registro de auditoría y el alta de usuarios

- **Requisitos:** REQ-012, REQ-016
- **Qué hay que hacer:** crear la aplicación `audit` con `audit_event` como está en "Modelo de datos" (`event_type`, `outcome`, `channel`, `user`, `username`, `corpus_version`, `detail`) y la función de registro de `audit/services.py`, que solo inserta filas; `corpus_version` queda vacío hasta T-008. Crear el comando `crear_usuario` (alta con rol, sin exigir rol de EVALUON, deja el hecho `user_created`). Agregar en `accounts/permissions.py` la autenticación común de los comandos: reciben `--usuario`, piden la clave por teclado sin mostrarla y la verifican contra la misma tabla (el plan no nombra otro archivo para esto). Textos de ayuda y mensajes en español llano.
- **Archivos:** `evaluon/audit/__init__.py`, `evaluon/audit/apps.py`, `evaluon/audit/models.py`, `evaluon/audit/services.py`, `evaluon/audit/migrations/`, `evaluon/accounts/permissions.py`, `evaluon/accounts/management/__init__.py`, `evaluon/accounts/management/commands/__init__.py`, `evaluon/accounts/management/commands/crear_usuario.py`, `evaluon/settings.py`, `tests/audit/test_record.py`, `tests/accounts/test_crear_usuario.py`.
- **Verificación:** `pytest tests/audit tests/accounts`. Un hecho registrado guarda momento, usuario, canal, resultado y detalle; `call_command("crear_usuario", ...)` crea el usuario con su rol, la clave no queda legible y existe el hecho `user_created` sin usuario actuante; la autenticación de comandos acepta la clave correcta y rechaza la incorrecta sin guardar la clave en ningún lado.
- **No tocar:** `evaluon/accounts/models.py` y sus migraciones; `evaluon/accounts/views.py`.
- **Entorno:** Cualquier equipo con Docker

### T-008 · Crear las tablas de normas, lecturas, unidades y pasajes

- **Requisitos:** REQ-001, REQ-003, REQ-011, REQ-012, REQ-017
- **Qué hay que hacer:** crear la aplicación `norms` con las tablas de "Modelo de datos": `norms_norm`, `norms_document`, `norms_document_file`, `norms_reading`, `norms_unit`, `norms_passage` (sin la columna `tsv`, que es de T-009), `norms_relation` y `norms_corpus_version`, con sus valores permitidos y restricciones (categoría obligatoria; tipo, número, año y organismo únicos en conjunto; `file_sha256` única; `key` única dentro de la lectura; a lo sumo un documento `in_use` por norma y versión). Primera migración con SQL propio y su reversa: extensiones `vector` y `unaccent`. Dejar armados los paquetes vacíos que usan las tareas siguientes (`services/`, `management/commands/`, `urls.py` sin rutas, incluido desde la raíz). Completar la función de registro de auditoría para que anote la versión vigente de la normativa.
- **Archivos:** `evaluon/norms/__init__.py`, `evaluon/norms/apps.py`, `evaluon/norms/models.py`, `evaluon/norms/migrations/`, `evaluon/norms/urls.py`, `evaluon/norms/services/__init__.py`, `evaluon/norms/management/__init__.py`, `evaluon/norms/management/commands/__init__.py`, `evaluon/audit/services.py`, `evaluon/settings.py`, `evaluon/urls.py`, `tests/norms/test_schema.py`.
- **Verificación:** `pytest tests/norms/test_schema.py` y `manage.py migrate norms zero` seguido de `manage.py migrate` sin error (reversa probada). Una norma sin categoría no se guarda (base de REQ-017); dos documentos con la misma huella no se guardan (base de REQ-011); dos unidades con la misma clave en una lectura no se guardan (base de REQ-003); un hecho registrado después de crear una versión de la normativa lleva su número (REQ-012).
- **No tocar:** `evaluon/accounts/`; las funciones SQL y la columna `tsv` (T-009); `tests/conftest.py`.
- **Entorno:** Cualquier equipo con Docker

### T-009 · Crear las funciones de unidades consultables a una fecha

- **Requisitos:** REQ-005, REQ-007, REQ-010
- **Qué hay que hacer:** migraciones con SQL propio, cada una con su reversa: configuración de búsqueda `spanish_unaccent` (derivada de `spanish`, quitando acentos antes de reducir las palabras a su raíz); columna `tsv` de `norms_passage` con su índice GIN; función `consultable_units(fecha)` (lectura `validated`, documento `in_use`, fecha dentro de la vigencia, y la marca `repealed` resuelta por norma entera, unidad o prefijo de `key`); función `unit_changes(fecha)` (relaciones `modifica` o `deroga` vigentes que alcanzan a la unidad o a una unidad contenida, con la unidad de origen). Agregar a `tests/conftest.py` el armado de datos de prueba que usan las tareas siguientes: norma, documento, lectura, unidades y pasajes con su vector, en cualquier estado.
- **Archivos:** `evaluon/norms/migrations/`, `evaluon/norms/models.py` (campo `tsv`), `tests/conftest.py`, `tests/norms/test_consultable_units.py`, `tests/norms/test_unit_changes.py`, `tests/norms/test_text_search_config.py`.
- **Verificación:** `pytest tests/norms` y reversa de las migraciones sin error. Cubre la base del criterio de REQ-005 (una lectura sin validar no devuelve unidades) y de REQ-007 (un artículo modificado en una fecha: antes, sin cambios; después, con la unidad que lo modifica; dos versiones de una norma: cada fecha devuelve la suya; una derogación marca `repealed` en la unidad y en las que contiene). Una búsqueda por "licitacion" encuentra un pasaje con "licitación" (base de REQ-010).
- **No tocar:** las tablas creadas en T-008 salvo la columna `tsv`; `evaluon/queries/` (T-010).
- **Entorno:** Cualquier equipo con Docker

### T-010 · Crear la tabla del registro detallado de consultas

- **Requisitos:** REQ-012
- **Qué hay que hacer:** crear la aplicación `queries` con `queries_query` como está en "Modelo de datos" (pregunta, fecha de referencia, versión de la normativa, estado y motivo, parámetros, candidatos, seleccionadas, puntaje más alto, versión de instrucciones, pedido, salida sin tocar, resultado, anomalías, tiempos, y el vínculo con su fila de `audit_event`). Dejar armados los paquetes vacíos (`management/commands/`, `urls.py` sin rutas, incluido desde la raíz).
- **Archivos:** `evaluon/queries/__init__.py`, `evaluon/queries/apps.py`, `evaluon/queries/models.py`, `evaluon/queries/migrations/`, `evaluon/queries/urls.py`, `evaluon/queries/management/__init__.py`, `evaluon/queries/management/commands/__init__.py`, `evaluon/settings.py`, `evaluon/urls.py`, `tests/queries/test_query_model.py`.
- **Verificación:** `pytest tests/queries/test_query_model.py` y reversa de la migración sin error. Una consulta guardada con la forma de "Forma de la respuesta" se lee igual y conserva usuario, fecha y versión de la normativa (base del criterio de REQ-012).
- **No tocar:** `evaluon/norms/`; `tests/conftest.py`.
- **Entorno:** Cualquier equipo con Docker

### T-011 · Crear los clientes de IA, sus dobles y los parámetros

- **Requisitos:** REQ-008, REQ-009
- **Qué hay que hacer:** crear los tres clientes de `evaluon/ai/`: generar con esquema (`/v1/chat/completions`, sin transmisión parcial, temperatura 0, semilla fija, pensamiento apagado), convertir textos en vectores (`/v1/embeddings`) y puntuar una pregunta contra una lista de textos (`/v1/rerank`, llevando el valor a un número entre 0 y 1 con la función sigmoide). Una entrada demasiado larga da error, nunca se recorta; un servicio que no responde y una espera agotada (60 segundos) se distinguen con errores propios. Dejar en `settings.py` las direcciones de los servicios (por variables de entorno), los nombres y huellas de los modelos, y todos los parámetros de búsqueda y generación con los valores iniciales del plan (30 candidatos por camino, umbral, 3 unidades por categoría, 2 considerandos, contexto de 16.384, 800 y 1.500 tokens, hasta 6 afirmaciones, máximo de salida). Agregar a `tests/conftest.py` los dobles de los tres clientes: el de generación devuelve una respuesta con citas, un "no determinado", una salida inválida o una demora; el de embeddings da vectores fijos; el de reranker da puntajes configurables. Si T-003 terminó en plan B, los clientes de embeddings y reranker hablan con Text Embeddings Inference.
- **Archivos:** `evaluon/ai/__init__.py`, `evaluon/ai/generation.py`, `evaluon/ai/embeddings.py`, `evaluon/ai/reranker.py`, `evaluon/settings.py`, `.env.example`, `tests/conftest.py`, `tests/queries/test_ai_clients.py`.
- **Verificación:** `pytest tests/queries/test_ai_clients.py`, contra un servidor HTTP falso dentro del test. El pedido de generación lleva el esquema y los parámetros fijos; un valor del reranker de −8,19 queda en 0,0003 y uno de 5,26 en 0,995; una entrada rechazada por el servidor se propaga como error; la espera agotada y el servicio caído dan errores distintos.
- **No tocar:** `evaluon/queries/` y `evaluon/norms/` (solo se agregan clientes y parámetros).
- **Entorno:** Cualquier equipo con Docker

### Etapa 2 · Hilo mínimo de punta a punta

Objetivo: cargar una norma en PDF con texto, validarla, preguntar en la pantalla y ver una respuesta con su cita y su registro. El documento es la Disposición AFIP 297/03.

### T-012 · Leer un PDF con texto

- **Requisitos:** REQ-004, REQ-015
- **Qué hay que hacer:** definir en `norms/reading/__init__.py` el resultado común a los tres formatos (la lectura: páginas, cada una con sus líneas; cada línea con su texto, su posición, su origen y, si vino de reconocimiento, su confianza; más las versiones de las herramientas) y la entrada única de lectura, que en esta tarea solo acepta PDF con texto. Leer con pdfplumber en `pdf_text.py`. Una página sin capa de texto se informa como no leída. Todo en CPU, sin los servicios de IA. Armar el archivo de prueba: un PDF con texto chico, generado a partir del texto público de la Disp. 297/03 (la página de Infoleg que está en `corpus/normativa/`, solo para leerla), con los cinco artículos de la disposición y el comienzo del Anexo I con su índice y sus primeros artículos.
- **Archivos:** `evaluon/norms/reading/__init__.py`, `evaluon/norms/reading/pdf_text.py`, `tests/norms/test_reading_pdf_text.py`, `tests/fixtures/disp-297-03-extracto.pdf`.
- **Verificación:** `pytest tests/norms/test_reading_pdf_text.py`. La lectura del extracto trae todas sus páginas con sus líneas en orden y con origen `pdf_text`; una página sin texto figura como no leída (base del criterio de REQ-004); la misma entrada da siempre la misma salida.
- **No tocar:** `evaluon/norms/splitting/` (T-013); `evaluon/norms/reading/ocr.py` y `web.py` (T-021 y T-022); `evaluon/norms/models.py`.
- **Entorno:** Cualquier equipo con Docker

### T-013 · Partir en artículos y armar el informe mínimo

- **Requisitos:** REQ-003, REQ-004
- **Qué hay que hacer:** en `norms/splitting/`: el texto canónico con las cinco operaciones del ADR-0004 y ninguna más, contando las uniones de palabras cortadas; la partición solo de artículos, lo que para la Disp. 297/03 exige reconocer las dos formas de encabezado (`ARTICULO 1° —` y `ARTICULO 1.- OBJETO`, con sus variantes), el anexo como contenedor (para que `art-1` y `anexo-i/art-1` sean dos unidades con clave distinta), el índice que repite encabezados (no produce unidades) y el control de secuencia dentro de cada contenedor. Cada unidad sale con `unit_type`, `number`, `label`, `key`, `path`, `order`, páginas, `char_start`, `char_end`, `text` y `text_origin`. Informe mínimo, en datos y en texto: unidades por tipo y por contenedor, páginas no leídas, tramos no ubicados, lista de unidades con su clave y control de cobertura. Incisos, considerandos, títulos en la ruta, cierre, dictámenes y el informe completo son de T-023 a T-025.
- **Archivos:** `evaluon/norms/splitting/` (carpeta completa), `tests/norms/test_canonical_text.py`, `tests/norms/test_splitting_articles.py`.
- **Verificación:** `pytest tests/norms/test_canonical_text.py tests/norms/test_splitting_articles.py`. Cubre el criterio de REQ-003 sobre el extracto: cada artículo es una unidad separada, `art-1` y `anexo-i/art-1` son dos unidades, el índice no produce unidades. Propiedades que se cumplen siempre: `text` es igual a `canonical_text[char_start:char_end]`, el orden es creciente, la cobertura suma el total.
- **No tocar:** `evaluon/norms/reading/`; `evaluon/norms/services/` (T-014 y T-015).
- **Entorno:** Cualquier equipo con Docker

### T-014 · Cargar una norma, listarla y ver su informe

- **Requisitos:** REQ-001, REQ-002, REQ-004, REQ-012, REQ-017
- **Qué hay que hacer:** función de carga en `services/loading.py`: recibe al usuario, comprueba el rol de lectura y escritura, exige los datos de REQ-001 y la categoría (sin categoría no incorpora y pide el dato), lee y parte el documento, guarda el original byte por byte, la lectura en estado `pending`, el texto canónico con su huella, las unidades y el informe, y deja el hecho `load` con su detalle. Función de listado en `services/listing.py` (normas con sus datos, documentos y estado de validación; los vínculos se suman en T-029). Comandos `cargar_norma`, `listar_normas` y `ver_informe` (los dos últimos, para los dos roles), con `--usuario` y clave por teclado; solo traducen y llaman. Mensajes en español llano. El aviso de duplicados es de T-026.
- **Archivos:** `evaluon/norms/services/loading.py`, `evaluon/norms/services/listing.py`, `evaluon/norms/management/commands/cargar_norma.py`, `evaluon/norms/management/commands/listar_normas.py`, `evaluon/norms/management/commands/ver_informe.py`, `tests/norms/test_loading.py`, `tests/norms/test_listing.py`.
- **Verificación:** `pytest tests/norms/test_loading.py tests/norms/test_listing.py`, con `call_command`. Cubre el criterio de REQ-001 (tras cargar con sus datos, el listado muestra la norma con todos ellos), el de REQ-017 (una carga sin categoría no incorpora y pide el dato), la base de REQ-002 (la huella de lo guardado es igual a la del archivo) y la de REQ-012 (el registro de la carga dice quién, cuándo y qué). `ver_informe` muestra las unidades con sus claves.
- **No tocar:** `evaluon/norms/services/validation.py`, `evaluon/norms/indexing.py` y `validar_informe` (T-015); `evaluon/norms/splitting/` y `evaluon/norms/reading/`.
- **Entorno:** Cualquier equipo con Docker

### T-015 · Validar una lectura y calcular pasajes y vectores

- **Requisitos:** REQ-005, REQ-012
- **Qué hay que hacer:** `norms/indexing.py`: un pasaje por unidad base (los incisos no generan pasajes), con su encabezado de contexto (norma y ruta), su texto, su vector y el nombre y la huella del modelo que lo calculó; la partición de unidades largas es de T-031. `services/validation.py`: recibe al usuario, comprueba el rol de lectura y escritura, calcula pasajes y vectores, pasa la lectura a `validated`, deja al primer documento validado de una norma como versión 1 y en uso (un segundo documento de la misma norma queda validado pero no en uso), crea una versión nueva de la normativa y deja el hecho `validation` con su detalle. Si el servicio `embeddings` no responde, no valida, no deja nada a medias y lo dice. Comando `validar_informe`, que pide confirmación antes de validar.
- **Archivos:** `evaluon/norms/indexing.py`, `evaluon/norms/services/validation.py`, `evaluon/norms/management/commands/validar_informe.py`, `tests/norms/test_validation.py`, `tests/norms/test_indexing.py`.
- **Verificación:** `pytest tests/norms/test_validation.py tests/norms/test_indexing.py`, con el doble de embeddings. Cubre la base del criterio de REQ-005: antes de validar, `consultable_units` no devuelve unidades de la norma; después, sí. Con el doble de embeddings caído, la lectura sigue `pending` y no hay pasajes. El registro de la validación trae la lectura, la cantidad de pasajes, el modelo y la versión nueva de la normativa (REQ-012).
- **No tocar:** `evaluon/norms/services/loading.py`, `listing.py` y sus comandos (T-014); `evaluon/norms/models.py`.
- **Entorno:** Cualquier equipo con Docker

### T-016 · Armar la pantalla de consulta con sus tres bloques

- **Requisitos:** REQ-013, REQ-014
- **Qué hay que hacer:** una sola página, armada en el servidor, en la raíz del sitio: nombre del sistema, usuario y botón "Salir"; el formulario de la pregunta; y, para una consulta guardada, uno de tres bloques que se distinguen por título, ícono y color ("Respuesta con fundamento en la normativa", "No determinado" con el texto "La normativa cargada no permite responder esta pregunta", "No se pudo completar la consulta"). La página se arma desde `queries_query.result`, leyendo el texto literal de cada unidad de `norms_unit` por `id`; cada cita muestra norma y ruta y despliega el texto literal con `<details>`. Solo ve el resultado quien hizo la consulta. Script propio para la espera (desactiva el botón y muestra "Buscando en la normativa. Puede tardar hasta medio minuto."); sin el script el formulario funciona igual. Ninguna referencia externa. El envío de la pregunta se conecta en T-019: en esta tarea la página muestra el formulario y el resultado de una consulta ya guardada.
- **Archivos:** `evaluon/queries/views.py`, `evaluon/queries/forms.py`, `evaluon/queries/urls.py`, `evaluon/templates/` (consulta), `evaluon/static/` (hoja de estilos y script), `tests/queries/test_screen.py`.
- **Verificación:** `pytest tests/queries/test_screen.py`, con el cliente de pruebas y consultas guardadas a mano en los tres estados. Cubre la parte de presentación del criterio de REQ-013 (la respuesta con sus citas y el texto literal de cada unidad) y el criterio de REQ-014 (con `undetermined`, aviso propio, distinto del de una respuesta, y ninguna cita). Además: otro usuario no ve la consulta; ninguna página ni archivo estático referencia direcciones externas y la cabecera de política de contenido está presente.
- **No tocar:** `evaluon/queries/services.py`, `retrieval.py` y `answering.py` (T-017 a T-019); `evaluon/accounts/`; la plantilla de ingreso.
- **Entorno:** Cualquier equipo con Docker

### T-017 · Recuperar por significado y reordenar con el reranker

- **Requisitos:** REQ-005, REQ-008, REQ-009
- **Qué hay que hacer:** `queries/retrieval.py`, versión mínima: vector de la pregunta contra los vectores de los pasajes de `consultable_units(fecha)` con `repealed` falso, distancia coseno, búsqueda exacta, 30 pasajes; el reranker puntúa encabezado más texto; los pasajes se agrupan por unidad base con su mejor puntaje; primera barrera de abstención (ninguna unidad alcanza el umbral); pasan las unidades que alcanzan el umbral. Devuelve también cada candidato con su camino y su puntaje, para el registro. Los otros dos caminos, los cupos, los cambios por relación y el espacio son de T-032 y T-033.
- **Archivos:** `evaluon/queries/retrieval.py`, `tests/queries/test_retrieval.py`.
- **Verificación:** `pytest tests/queries/test_retrieval.py`, con los dobles. Una norma cargada y sin validar no aparece entre los candidatos (criterio de REQ-005, por este camino); con todos los puntajes bajo el umbral no hay unidades seleccionadas y el motivo es `below_threshold` (REQ-009); con un pasaje pertinente, su unidad base queda seleccionada (base de REQ-008).
- **No tocar:** `evaluon/queries/answering.py` y `prompts/` (T-018); `evaluon/queries/services.py` (T-019); `evaluon/settings.py`.
- **Entorno:** Cualquier equipo con Docker

### T-018 · Generar la respuesta con esquema e insertar las citas

- **Requisitos:** REQ-008, REQ-009
- **Qué hay que hacer:** `queries/answering.py`, versión mínima, sobre lo que entrega T-017: primera versión de las instrucciones en `queries/prompts/` (un archivo por versión); el pedido con la pregunta y las unidades seleccionadas, cada una con su alias (`U1`, `U2`, …), categoría, norma, ruta, tipo y texto; el esquema armado para cada consulta, que enumera solo los alias mostrados; un solo pedido al motor. Validación de la salida: si no cumple el esquema, falla técnica `invalid_output`; si una afirmación cita un alias no mostrado o no trae citas, "no determinado" con motivo `invalid_citation` y se descarta la respuesta entera; si el estado es `undetermined`, motivo `model_abstained`. Traduce cada alias al `id` de la unidad y arma el resultado con la forma de "Forma de la respuesta"; el texto literal no viaja en el resultado. La marca `regimes_differ`, el orden por categoría y las instrucciones completas son de T-034.
- **Archivos:** `evaluon/queries/answering.py`, `evaluon/queries/prompts/` (primera versión), `tests/queries/test_answering.py`.
- **Verificación:** `pytest tests/queries/test_answering.py`, con el doble del motor. Cubre la base del criterio de REQ-008 (la respuesta cita el artículo por su `id` y el texto de la cita es el de la base) y de REQ-009 (el modelo se abstiene; cita inválida; en los dos el resultado es `undetermined` sin afirmaciones). Una salida cortada da `error` con `invalid_output`, no `undetermined`.
- **No tocar:** `evaluon/queries/retrieval.py` (T-017); `evaluon/queries/services.py` y `views.py` (T-019).
- **Entorno:** Cualquier equipo con Docker

### T-019 · Unir la consulta de punta a punta con su registro

- **Requisitos:** REQ-008, REQ-009, REQ-012, REQ-013
- **Qué hay que hacer:** `queries/services.py`: la función de una consulta de punta a punta. Recibe al usuario, la pregunta y el canal (`screen`, `command` o `eval`); comprueba el rol; usa la fecha del día en hora de Buenos Aires; llama a la recuperación; si nada alcanza el umbral no llama al modelo; llama a la generación; guarda `queries_query` una vez, al terminar, y su hecho `query` en `audit_event`, con pregunta, fecha de referencia, versión de la normativa, parámetros, candidatos, seleccionadas, puntaje más alto, versión de instrucciones, pedido, salida sin tocar, resultado, anomalías y tiempos. Un servicio que no responde, una espera agotada o una salida inválida dan estado `error` con su motivo, nunca `undetermined`. Conectar el envío de la pregunta en la pantalla: la vista llama a esta función y redirige a la página del resultado guardado, de modo que recargar no vuelve a consultar.
- **Archivos:** `evaluon/queries/services.py`, `evaluon/queries/views.py` (solo el envío de la pregunta), `evaluon/queries/urls.py`, `tests/queries/test_services.py`, `tests/queries/test_screen.py`.
- **Verificación:** `pytest tests/queries`, con los dobles. Cubre el criterio de REQ-008 (la respuesta cita el artículo y el texto citado es igual a `canonical_text[char_start:char_end]`), el de REQ-009 (los tres motivos dan `undetermined`; bajo el umbral no se llama al modelo), el de REQ-012 (el registro de la consulta muestra pregunta, unidades recuperadas, respuesta, versión de la normativa, usuario y fecha) y el de REQ-013 de punta a punta (una persona escribe la pregunta y ve la respuesta con sus citas). Recargar la página no crea otra consulta.
- **No tocar:** las plantillas y `static/` (T-016 y T-037); `evaluon/queries/retrieval.py` y `answering.py` (T-032 a T-034); `evaluon/queries/models.py`.
- **Entorno:** Cualquier equipo con Docker

### T-020 · Probar el hilo mínimo con los servicios reales

- **Requisitos:** REQ-008, REQ-012, REQ-013
- **Qué hay que hacer:** en la MSI, con los seis servicios arriba y una base aparte para esta prueba (por variable de entorno, para que la base `evaluon` quede vacía hasta la carga real de T-043): crear dos usuarios con `crear_usuario`, cargar la Disp. 297/03 en PDF con texto, ver su informe, validarla, hacer una pregunta real en la pantalla y revisar su registro. El PDF con texto lo deja el Coordinador en `corpus/normativa/`, anotado en `corpus/manifiesto.csv`: se obtiene del Boletín Oficial o se genera a partir del mismo texto de la página de Infoleg guardada. Corregir en los clientes de `evaluon/ai/` lo que difiera entre los dobles y los servicios reales. Agregar la prueba de espera: Gunicorn con la configuración del proyecto y un doble del motor que tarda más de 30 segundos; la consulta no se corta antes del tiempo configurado. Anotar en `entorno.md` la pregunta, el tiempo total y lo corregido. La validación de esta prueba la hace el desarrollador con un usuario de prueba; la validación del responsable de normativa es la de T-043.
- **Archivos:** `evaluon/ai/generation.py`, `evaluon/ai/embeddings.py`, `evaluon/ai/reranker.py` (solo ajustes), `tests/queries/test_ai_clients.py`, `tests/queries/test_wait.py`, `specs/001-normativa/entorno.md`.
- **Verificación:** en el navegador del equipo (`127.0.0.1`), una pregunta cuya respuesta está en un artículo de la 297/03 muestra la respuesta con su cita y el texto literal; su fila de `queries_query` trae candidatos, puntajes, pedido, salida y tiempos; `docker compose run --rm app pytest` en verde, incluido `tests/queries/test_wait.py`. Cubre, con servicios reales y en versión mínima, los criterios de REQ-008, REQ-012 y REQ-013.
- **No tocar:** `corpus/`; `docker-compose.yml`, `Dockerfile` y `settings.py` (si la prueba pide cambiarlos, se detiene y se informa); la base `evaluon`.
- **Entorno:** MSI con GPU

### Etapa 3 · Bloques completos

Los bloques A a K del plan, partidos en tareas de una sesión. Entre paréntesis, el bloque del plan al que pertenece cada tarea.

### T-021 · Leer un PDF escaneado con reconocimiento de texto

- **Requisitos:** REQ-004, REQ-015
- **Qué hay que hacer:** (bloque A) `norms/reading/ocr.py`: una función que recibe una página de PDF, la dibuja a 300 puntos por pulgada con pypdfium2, la reconoce con Tesseract y el modelo de español de la imagen, y devuelve sus líneas en el resultado común de T-012, con origen `ocr` y la confianza de cada palabra; estado de la página según la confianza promedio (legible desde 80, dudosa entre 50 y 80, ilegible por debajo de 50 o con casi ninguna palabra); una página ilegible no aporta texto. Los umbrales quedan como valores de partida en este archivo. Archivo de prueba: el extracto de T-012 dibujado como imágenes, más una página de ruido. La decisión de qué páginas se reconocen es de T-028.
- **Archivos:** `evaluon/norms/reading/ocr.py`, `tests/norms/test_reading_ocr.py`, `tests/fixtures/disp-297-03-extracto-escaneado.pdf`, `tests/fixtures/pagina-ruido.pdf`.
- **Verificación:** `pytest tests/norms/test_reading_ocr.py`. Las líneas reconocidas del extracto llevan origen `ocr` y confianza (base del criterio de REQ-015); la página de ruido queda en estado ilegible y sin texto (base del criterio de REQ-004).
- **No tocar:** `evaluon/norms/reading/__init__.py` (T-028), `pdf_text.py` y `web.py`; `Dockerfile`.
- **Entorno:** Cualquier equipo con Docker

### T-022 · Leer una página web guardada

- **Requisitos:** REQ-015
- **Qué hay que hacer:** (bloque B) `norms/reading/web.py`: una función que recibe un archivo `.html`, detecta su codificación, descarta scripts, estilos y la navegación del sitio con reglas explícitas por sitio de origen (la de Infoleg, escrita contra la página de la Disp. 297/03 que está en `corpus/normativa/`), y devuelve los bloques de texto en el orden del documento, en el resultado común de T-012, con origen `web` y sin páginas. Lo descartado no se borra de la lectura: queda marcado para el informe. Archivo de prueba: un extracto de esa página con los mismos artículos que el extracto de T-012.
- **Archivos:** `evaluon/norms/reading/web.py`, `tests/norms/test_reading_web.py`, `tests/fixtures/disp-297-03-extracto.html`.
- **Verificación:** `pytest tests/norms/test_reading_web.py`. El extracto se lee con sus tildes correctas, sin texto de navegación ni de scripts, con origen `web` (base del criterio de REQ-015).
- **No tocar:** `evaluon/norms/reading/__init__.py` (T-028), `pdf_text.py` y `ocr.py`.
- **Entorno:** Cualquier equipo con Docker

### T-023 · Partir normas completas con incisos, anexos y considerandos

- **Requisitos:** REQ-003
- **Qué hay que hacer:** (bloque C) completar las reglas de `norms/splitting/` para normas, según la tabla "Cómo se parte" del ADR-0004: todas las formas de artículo (incluido `14 bis`); incisos de dos niveles como unidades hijas, cuyo texto es un recorte del artículo; anexos con y sin artículos y su texto propio; títulos, capítulos y secciones, que no son unidades y pasan a la ruta; visto y considerandos, una unidad por párrafo; cierre y firma; encabezados y pies de página que se descartan en PDF (franja superior o inferior, repetidos ignorando los números, y formas conocidas); controles de secuencia y de saltos y repeticiones; casos trampa (cita a un artículo en medio de un párrafo, artículo transcripto entre comillas, índice). Escribir a mano la tabla esperada de la Disp. 297/03 (contenedor, número, página de inicio) contra el PDF con texto de `corpus/normativa/`, el mismo de T-020.
- **Archivos:** `evaluon/norms/splitting/`, `tests/norms/test_splitting_rules.py`, `tests/norms/test_splitting_disp_297_03.py`.
- **Verificación:** `pytest tests/norms/test_splitting_rules.py tests/norms/test_splitting_disp_297_03.py`. Cubre el criterio de REQ-003 sobre el documento real: cada artículo es una unidad y su ubicación coincide con la tabla esperada; `art-1` y `anexo-i/art-1` son dos unidades; el índice no produce unidades; cada texto es igual a su recorte. La tabla de encabezados y los casos trampa dan el resultado esperado.
- **No tocar:** `evaluon/norms/reading/`; `evaluon/norms/services/`; el informe de lectura más allá de lo que ya entrega T-013 (T-025).
- **Entorno:** Cualquier equipo con Docker

### T-024 · Partir dictámenes y recomendaciones en puntos y párrafos

- **Requisitos:** REQ-003
- **Qué hay que hacer:** (bloque C) sumar a `norms/splitting/` las reglas para dictámenes legales y recomendaciones de auditoría: puntos numerados (`I.`, `1.`, `1.1.`, `2.3`) como unidades `punto`; si no hay numeración, párrafos como unidades `parrafo`, numerados por orden; claves `punto-2.3` y `parrafo-12`. La regla se elige por la categoría del documento. Como todavía no hay dictámenes en el corpus, se prueba con documentos sintéticos; el ajuste contra los reales es de T-043.
- **Archivos:** `evaluon/norms/splitting/`, `tests/norms/test_splitting_opinions.py`, `tests/fixtures/dictamen-sintetico.pdf`.
- **Verificación:** `pytest tests/norms/test_splitting_opinions.py`. Cubre la parte del criterio de REQ-003 que corresponde a dictámenes y recomendaciones: cada punto o párrafo es una unidad con su ubicación; cobertura completa y texto igual a su recorte.
- **No tocar:** las reglas de normas de T-023 salvo lo necesario para elegir la regla por categoría; `evaluon/norms/services/`.
- **Entorno:** Cualquier equipo con Docker

### T-025 · Completar el informe de lectura

- **Requisitos:** REQ-004, REQ-015
- **Qué hay que hacer:** (bloque C) completar el informe en `norms/splitting/` con las diez partes del ADR-0004, en datos y en texto legible, empezando por lo que requiere atención: documento; páginas con su origen, estado y confianza, y las listas de ilegibles y dudosas; unidades por tipo y contenedor, con saltos y repeticiones; no ubicado, con página y primeras palabras; descartado; uniones de palabras cortadas; reconocimiento sobre imagen (cuántas unidades tienen ese origen y las palabras de menor confianza con su página); control de cobertura; y el lugar para los posibles duplicados, que completa T-026. El texto lista las unidades con su `key`. Calcular `text_origin` y la confianza mínima y promedio de cada unidad a partir de sus líneas.
- **Archivos:** `evaluon/norms/splitting/`, `tests/norms/test_reading_report.py`.
- **Verificación:** `pytest tests/norms/test_reading_report.py`, con lecturas armadas en el test. Una lectura con una página ilegible da un informe que señala esa página y ninguna otra (criterio de REQ-004, a nivel del informe); una lectura con líneas de reconocimiento da unidades con origen `ocr` y el informe lo dice (parte del criterio de REQ-015); la cobertura suma el total leído.
- **No tocar:** `evaluon/norms/reading/`; `evaluon/norms/services/loading.py` (T-026).
- **Entorno:** Cualquier equipo con Docker

### T-026 · Avisar duplicados al cargar una norma

- **Requisitos:** REQ-011, REQ-012
- **Qué hay que hacer:** (bloque D) en la carga, las tres comprobaciones en orden: misma huella de archivo, avisa y no incorpora; mismo texto canónico en otro archivo, o mismos tipo, número, año y organismo emisor, avisa "misma norma" y solo incorpora con confirmación expresa, en la que la persona indica si es otro archivo de lo mismo o una versión nueva (`same_norm_confirmation`). El documento así incorporado no queda en uso. El comando `cargar_norma` hace la pregunta de confirmación. Una carga rechazada por duplicado también se registra, con el resultado de las comprobaciones. El informe muestra los posibles duplicados.
- **Archivos:** `evaluon/norms/services/loading.py`, `evaluon/norms/management/commands/cargar_norma.py`, `tests/norms/test_duplicates.py`.
- **Verificación:** `pytest tests/norms/test_duplicates.py`. Cubre el criterio de REQ-011: el mismo archivo dos veces da un aviso y un solo documento; la misma norma desde otro archivo avisa y solo se incorpora con confirmación expresa. El intento rechazado queda en el registro (REQ-012).
- **No tocar:** `evaluon/norms/services/validation.py` y `releer_norma` (T-027); `evaluon/norms/services/listing.py`, `relations.py` y `versions.py` (T-029 y T-030).
- **Entorno:** Cualquier equipo con Docker

### T-027 · Releer un documento y reemplazar la lectura anterior

- **Requisitos:** REQ-004, REQ-005
- **Qué hay que hacer:** (bloque D; el plan no asigna `validation.py` a ningún bloque y esta parte lo necesita) comando `releer_norma` y su función: crea una lectura nueva de un documento ya cargado, a partir del original guardado y sin pedir el archivo, en estado `pending`, con su informe y su hecho `reread`. Al validar la lectura nueva, la anterior pasa a `superseded` y sus unidades no se tocan; mientras no se valide, sigue consultable la anterior. Al validar, el informe avisa si alguna relación registrada quedó apuntando a una clave de unidad que la lectura nueva no tiene.
- **Archivos:** `evaluon/norms/services/loading.py`, `evaluon/norms/services/validation.py`, `evaluon/norms/management/commands/releer_norma.py`, `evaluon/norms/management/commands/validar_informe.py`, `tests/norms/test_reread.py`.
- **Verificación:** `pytest tests/norms/test_reread.py`. La relectura deja una lectura nueva con su informe (REQ-004) que no es consultable hasta validarse; al validarla, `consultable_units` devuelve las unidades de la nueva y ninguna de la anterior (criterio de REQ-005 aplicado a la relectura); las unidades de la lectura anterior conservan su `id` y su texto; el aviso de relación sin unidad aparece cuando corresponde.
- **No tocar:** `evaluon/norms/indexing.py` (T-031); `evaluon/norms/services/versions.py` (T-030); `evaluon/norms/splitting/`.
- **Entorno:** Cualquier equipo con Docker

### T-028 · Integrar los tres formatos en la carga

- **Requisitos:** REQ-004, REQ-015
- **Qué hay que hacer:** (une los bloques A, B y C) completar la entrada única de `norms/reading/__init__.py`: el formato se determina por el contenido del archivo, no por su extensión (`pdf` o `html`); cada página de un PDF se clasifica antes de leerla (con texto, escaneada, con texto inservible, en blanco) y se lee con `pdf_text.py` o con `ocr.py`; una página web se lee con `web.py`; se registran las versiones de las herramientas, la huella del modelo de español y la versión de las reglas. La carga guarda el formato detectado. Probar la misma norma en los tres formatos con los extractos de T-012, T-021 y T-022, y un PDF con una página de ruido insertada.
- **Archivos:** `evaluon/norms/reading/__init__.py`, `evaluon/norms/services/loading.py` (solo el formato detectado y las versiones de herramientas), `tests/norms/test_three_formats.py`, `tests/norms/test_unreadable_page.py`, `tests/fixtures/disp-297-03-extracto-con-ruido.pdf`.
- **Verificación:** `pytest tests/norms/test_three_formats.py tests/norms/test_unreadable_page.py`. Cubre el criterio de REQ-015: la misma norma como PDF con texto, PDF escaneado y página web da la misma lista de unidades (tipo, número y contenedor); entre PDF con texto y web, la misma secuencia de palabras en cada artículo; en el escaneado, todas las unidades con origen `ocr` y el informe lo dice; se informa la proporción de palabras del escaneado que coincide con el PDF con texto. Cubre el criterio de REQ-004: el informe señala la página ilegible y ninguna otra.
- **No tocar:** `pdf_text.py`, `ocr.py` y `web.py` más allá de corregir un defecto que la integración muestre; `evaluon/norms/splitting/`.
- **Entorno:** Cualquier equipo con Docker

### T-029 · Registrar relaciones entre normas y mostrar los vínculos

- **Requisitos:** REQ-006, REQ-007
- **Qué hay que hacer:** (bloque E) `services/relations.py` y el comando `registrar_relacion`: registra que una norma modifica, complementa, reglamenta o deroga a otra, con fecha de vigencia del cambio y, cuando corresponde, las claves de la unidad de origen y de la unidad alcanzada; comprueba el rol de lectura y escritura y que las claves existan; crea una versión nueva de la normativa y deja el hecho `relation`. Sumar los vínculos, en los dos sentidos, a `services/listing.py` y a `listar_normas`.
- **Archivos:** `evaluon/norms/services/relations.py`, `evaluon/norms/services/listing.py`, `evaluon/norms/management/commands/registrar_relacion.py`, `evaluon/norms/management/commands/listar_normas.py`, `tests/norms/test_relations.py`.
- **Verificación:** `pytest tests/norms/test_relations.py`. Cubre el criterio de REQ-006 (registrada la relación, al listar cualquiera de las dos normas aparece el vínculo; una relación entre unidades guarda sus claves; una clave inexistente se rechaza) y la base del de REQ-007 (un artículo modificado en una fecha: antes, `unit_changes` no devuelve nada; después, devuelve la unidad que lo modifica con su texto literal).
- **No tocar:** `evaluon/norms/services/loading.py`, `validation.py` y `versions.py`; `evaluon/norms/models.py` y las funciones SQL.
- **Entorno:** Cualquier equipo con Docker

### T-030 · Registrar versiones de una norma

- **Requisitos:** REQ-007
- **Qué hay que hacer:** (bloque E) `services/versions.py` y el comando `registrar_version`: deja un documento validado como versión siguiente de su norma (asigna `version_number`, lo marca `in_use` y cierra la vigencia de la versión anterior con `effective_to`) o como el archivo en uso de una versión existente (reemplaza al que estaba en uso); comprueba el rol de lectura y escritura; crea una versión nueva de la normativa y deja el hecho `version`.
- **Archivos:** `evaluon/norms/services/versions.py`, `evaluon/norms/management/commands/registrar_version.py`, `tests/norms/test_versions.py`.
- **Verificación:** `pytest tests/norms/test_versions.py`. Cubre la parte de versiones del criterio de REQ-007: con dos versiones de una norma, `consultable_units` devuelve para cada fecha las unidades de la suya. La misma norma validada en tres archivos aparece una sola vez: solo el documento en uso es consultable.
- **No tocar:** `evaluon/norms/services/validation.py`, `relations.py` y `listing.py`; `evaluon/norms/models.py`.
- **Entorno:** Cualquier equipo con Docker

### T-031 · Partir en pasajes las unidades largas

- **Requisitos:** REQ-003, REQ-008
- **Qué hay que hacer:** (completa `norms/indexing.py`; el plan lo describe en "Unidades base, incisos y pasajes" y no lo asigna a ningún bloque) una unidad base larga se parte en pasajes de hasta 800 tokens con solape, cortando en los límites de inciso cuando los hay; cada pasaje guarda el tramo que cubre (`char_start`, `char_end`) y su encabezado; un anexo con artículos aporta solo su texto propio; los incisos no generan pasajes; ningún texto se recorta en silencio. **Pendiente antes de empezar:** el plan mide los pasajes en tokens y no dice cómo se cuentan (los clientes de `evaluon/ai/` ofrecen tres operaciones y ninguna cuenta tokens). El Coordinador lo resuelve antes de asignar esta tarea.
- **Archivos:** `evaluon/norms/indexing.py`, `tests/norms/test_indexing.py`.
- **Verificación:** `pytest tests/norms/test_indexing.py`. Una unidad corta da un pasaje; un anexo sin artículos de varias páginas da varios pasajes que cubren todo su texto, con solape y sin superar el límite; un artículo con muchos incisos se corta en los límites de inciso; ningún texto aparece en pasajes de dos unidades base distintas. Habilita que los anexos (REQ-003) se puedan recuperar y citar como unidad entera (REQ-008).
- **No tocar:** `evaluon/norms/services/validation.py` (T-027); `evaluon/norms/models.py`; `evaluon/settings.py`.
- **Entorno:** Cualquier equipo con Docker

### T-032 · Recuperar por tres caminos y unir los candidatos

- **Requisitos:** REQ-005, REQ-008
- **Qué hay que hacer:** (bloque F) sumar a `queries/retrieval.py` el camino por palabras (búsqueda de texto de Postgres con `spanish_unaccent`, palabras unidas por "o", 30 pasajes) y el camino por referencia exacta (un patrón detecta "artículo 23", "art. 5 inc. b", "14 bis", "Disposición 297/03" o "297/2003" y trae esas unidades por sus datos; si nombra un inciso, entra el artículo que lo contiene); unir los tres sin repetir y sin fórmula de fusión; anotar por qué camino entró cada candidato. Los tres leen de `consultable_units(fecha)` con `repealed` falso. Cada camino y el reranker se pueden apagar por parámetro, para la comparación quitando piezas de las evals.
- **Archivos:** `evaluon/queries/retrieval.py`, `tests/queries/test_retrieval.py`, `tests/queries/test_retrieval_paths.py`.
- **Verificación:** `pytest tests/queries/test_retrieval.py tests/queries/test_retrieval_paths.py`. Cubre el criterio de REQ-005: una norma cargada y sin validar no aparece por ninguno de los tres caminos. Una unidad derogada no entra. "Artículo 1 de la Disposición 297/03" trae `art-1` y `anexo-i/art-1`. Una pregunta sin tildes encuentra el pasaje por palabras.
- **No tocar:** `evaluon/queries/answering.py` (T-034); `evaluon/queries/search.py` (T-035); `evaluon/queries/services.py` (T-040); `evaluon/settings.py`.
- **Entorno:** Cualquier equipo con Docker

### T-033 · Seleccionar por categoría, sumar cambios y ordenar

- **Requisitos:** REQ-007, REQ-018, REQ-019
- **Qué hay que hacer:** (bloque F) completar la selección de `queries/retrieval.py`: unidades con puntaje igual o mayor al umbral, hasta 3 por categoría; cupo propio de hasta 2 considerandos; a cada unidad seleccionada se le suman, por relación y no por parecido, las unidades que la modifican a la fecha (`unit_changes`); si el total no entra en el contexto, primero la mejor de cada categoría, después la segunda, y de una unidad de más de 1.500 tokens solo los pasajes que superaron el umbral; lo que queda afuera se anota; orden de entrega fijado por el código (régimen específico, otra normativa aplicable, marco nacional, dictamen legal, recomendación de auditoría; dentro de cada una, por puntaje; los considerandos al final). **Pendiente antes de empezar:** la misma definición de cómo se cuentan los tokens que necesita T-031.
- **Archivos:** `evaluon/queries/retrieval.py`, `tests/queries/test_retrieval_selection.py`.
- **Verificación:** `pytest tests/queries/test_retrieval_selection.py`. Con cinco unidades pertinentes del régimen específico y una del marco nacional, la del marco nacional entra (base de REQ-019); un artículo y un dictamen salen en ese orden y un considerando al final (base de REQ-018); un artículo modificado a la fecha llega acompañado por la unidad que lo modifica, y antes de esa fecha llega solo (base de REQ-007); lo dejado afuera por espacio queda anotado.
- **No tocar:** `evaluon/queries/answering.py`, `search.py` y `services.py`; `evaluon/settings.py`.
- **Entorno:** Cualquier equipo con Docker

### T-034 · Completar instrucciones, marca de regímenes y orden

- **Requisitos:** REQ-008, REQ-009, REQ-018, REQ-019
- **Qué hay que hacer:** (bloque G) completar `queries/answering.py` y dejar una versión nueva de las instrucciones en `queries/prompts/`: cada unidad se le muestra al modelo con su categoría y su papel; una unidad modificada lleva a continuación el texto de la que la modifica, con la fecha; los considerandos van en un bloque aparte rotulado como contexto; las instrucciones piden todo lo de "Qué se le pide" del plan; el esquema suma `regimes_differ` y el tope de 6 afirmaciones. Validación: `regimes_differ` verdadero sin una cita del régimen específico y otra del marco nacional apaga la marca y anota la anomalía `regimes_flag_dropped`. Orden fijado por el código: las citas de cada afirmación por categoría, con los considerandos al final; las afirmaciones por la categoría de su primera cita. El resultado trae `changes` por unidad.
- **Archivos:** `evaluon/queries/answering.py`, `evaluon/queries/prompts/` (versión nueva; la anterior no se modifica), `tests/queries/test_answering.py`, `tests/queries/test_answering_order.py`.
- **Verificación:** `pytest tests/queries/test_answering.py tests/queries/test_answering_order.py`, con el doble del motor. Cubre a nivel de la respuesta el criterio de REQ-018 (artículo del régimen específico y dictamen: el artículo va primero aunque el modelo los devuelva al revés; un considerando va al final) y el de REQ-019 (con la marca y las dos citas, el resultado conserva `regimes_differ`; sin las dos citas, la marca se apaga y queda la anomalía). Siguen pasando los casos de REQ-008 y REQ-009 de T-018.
- **No tocar:** `evaluon/queries/retrieval.py` (T-032 y T-033); `evaluon/queries/services.py` (T-040); las plantillas.
- **Entorno:** Cualquier equipo con Docker

### T-035 · Buscar unidades por artículo y por palabras

- **Requisitos:** REQ-005, REQ-006, REQ-010
- **Qué hay que hacer:** (bloque H) `queries/search.py`, sin modelos de IA y siempre sobre `consultable_units(fecha)`: por norma y número de artículo, devuelve todas las unidades de tipo `articulo` con ese número en el documento en uso, cada una con su ruta y su texto (y el inciso cuando se lo pide); por palabras, búsqueda de texto sobre los pasajes, sin distinguir acentos, con comillas para frase exacta, agrupada por unidad base. Cada resultado trae la categoría, el texto literal, el documento, los cambios vigentes (`unit_changes`), la marca de derogada con la norma que la derogó y la fecha, y los vínculos de su norma con otras en los dos sentidos. La pantalla y el registro de la búsqueda son de T-041.
- **Archivos:** `evaluon/queries/search.py`, `tests/queries/test_search.py`.
- **Verificación:** `pytest tests/queries/test_search.py`. Cubre a nivel de la función el criterio de REQ-010: dado un número de norma y de artículo se obtiene la unidad con su texto; "artículo 1" de la 297/03 devuelve las dos unidades con su ruta; una búsqueda sin tildes encuentra el texto con tildes; una unidad derogada aparece marcada. Una norma sin validar no aparece (criterio de REQ-005 en la búsqueda directa). Los vínculos de la norma vienen en el resultado (REQ-006).
- **No tocar:** `evaluon/queries/retrieval.py`; `evaluon/queries/services.py`, `views.py` y las plantillas (T-041).
- **Entorno:** Cualquier equipo con Docker

### T-036 · Entregar el documento original con sesión

- **Requisitos:** REQ-002
- **Qué hay que hacer:** (bloque I) vista en `norms/views.py` que exige sesión y entrega el archivo original desde `norms_document_file`, byte por byte. Un PDF se entrega para abrirse en el visor del navegador. Una página web guardada se entrega con una política de contenido que impide ejecutar scripts y cargar recursos de internet; la restricción va en la cabecera y el archivo no se modifica. La ruta lleva nombre, para que las plantillas de T-037 y T-041 la enlacen.
- **Archivos:** `evaluon/norms/views.py`, `evaluon/norms/urls.py`, `tests/norms/test_original.py`.
- **Verificación:** `pytest tests/norms/test_original.py`. Cubre el criterio de REQ-002: la huella de lo que entrega la vista es igual a la del archivo cargado, en PDF y en HTML. Sin sesión redirige al ingreso; la respuesta de un HTML lleva la política de aislamiento.
- **No tocar:** `evaluon/urls.py` de la raíz (la inclusión ya está hecha en T-008); `evaluon/queries/`; las plantillas.
- **Entorno:** Cualquier equipo con Docker

### T-037 · Mostrar las citas con categoría, papel y cambios

- **Requisitos:** REQ-007, REQ-013, REQ-014, REQ-015, REQ-018, REQ-019
- **Qué hay que hacer:** (bloque I) completar el bloque de respuesta de la pantalla: cada cita muestra la categoría con su papel en palabras ("Régimen específico · es lo que se aplica", "Marco nacional · marco de referencia", "Dictamen legal · criterio que acompaña", y así las demás), el documento y la ruta; un considerando se rotula "Considerando · contexto"; el papel se deriva de `category` y `unit_type`; las citas y las afirmaciones se muestran en el orden guardado. Con `regimes_differ`, el aviso de texto fijo ("El régimen específico y el marco nacional tratan este punto de manera distinta. Se aplica el régimen específico."), los dos textos y el rótulo de aplicable en el del régimen específico. Una unidad modificada se muestra junto con el texto literal de la que la modifica, señalando el cambio y su fecha. Al desplegar una cita: texto literal, enlace "Abrir el documento original" (en un PDF, a la página de la unidad) y, si el texto vino de reconocimiento sobre imagen, la leyenda que lo dice. Textos en lenguaje llano.
- **Archivos:** `evaluon/queries/views.py`, `evaluon/templates/` (consulta), `evaluon/static/`, `tests/queries/test_screen_citations.py`.
- **Verificación:** `pytest tests/queries/test_screen_citations.py`, con consultas guardadas. Cubre el criterio de REQ-013 completo (respuesta con citas, texto literal al elegir una cita y enlace al original), el de REQ-018 en la pantalla (artículo primero, dictamen después, cada cita con su categoría; considerando al final, rotulado como contexto), el de REQ-019 (con la marca, la página muestra los dos textos y señala el del régimen específico como aplicable) y la presentación de REQ-007 (el original junto con el texto que lo modifica). Sigue pasando REQ-014. La leyenda de reconocimiento aparece en una unidad `ocr` (REQ-015). La página no muestra nombres internos (`grounded`, `undetermined`, `below_threshold`, `reranker`).
- **No tocar:** `evaluon/queries/services.py` (T-040); `evaluon/queries/forms.py` y el formulario de búsqueda (T-041); `evaluon/norms/views.py`; la plantilla de ingreso.
- **Entorno:** Cualquier equipo con Docker

### T-038 · Registrar ingresos, ingresos fallidos y rechazos por rol

- **Requisitos:** REQ-012, REQ-016
- **Qué hay que hacer:** (bloque J) dejar en el registro de auditoría cada ingreso (`login`), cada ingreso fallido (`login_failed`: nombre intentado y canal, nunca la clave) y cada operación rechazada por rol (`rejected`: usuario, operación intentada y canal), tanto por pantalla como por comando. La comprobación de rol de `permissions.py` registra el rechazo antes de rechazar. El registro no guarda claves ni identificadores de sesión.
- **Archivos:** `evaluon/accounts/views.py`, `evaluon/accounts/permissions.py`, `evaluon/accounts/apps.py` (señales de ingreso), `evaluon/audit/services.py`, `tests/accounts/test_access_log.py`, `tests/accounts/test_role_rejection.py`.
- **Verificación:** `pytest tests/accounts`. Cubre la segunda parte del criterio de REQ-016: un usuario con rol de lectura que corre `cargar_norma` o `validar_informe` (con `call_command`) es rechazado, no se incorpora ni se valida nada, y queda el hecho `rejected` con el usuario, la operación y el canal `command`. Una clave incorrecta en la pantalla y en un comando deja `login_failed` sin la clave; un ingreso correcto deja `login` (REQ-012).
- **No tocar:** `evaluon/accounts/models.py` y sus migraciones; `evaluon/settings.py`; las plantillas; los comandos de `evaluon/norms/` (se usan, no se modifican).
- **Entorno:** Cualquier equipo con Docker

### T-039 · Correr el conjunto de preguntas y medir las exigencias

- **Requisitos:** REQ-008, REQ-009. No implementa un requisito funcional: habilita medir la calidad de REQ-008 y REQ-009 y el tiempo de respuesta (P7).
- **Qué hay que hacer:** (bloque K) `queries/evaluation.py` y el comando `correr_evals` (rol de lectura, `--usuario` y clave por teclado). Formato de los casos: un archivo `EV-NNN.yaml` por pregunta, con los datos de `evals/README.md` más `unidades` (por norma y `key`), `datos_clave`, `difieren`, `etiquetas` y `visto_bueno`; un caso mal formado se informa y un caso sin visto bueno no se corre. La corrida llama a la misma función que la pantalla, con el canal `eval`, una pregunta por vez. Medidas exigidas: cita literal (100 %), respuesta correcta que cita la unidad correcta (si el caso nombra un inciso vale el artículo que lo contiene; contiene los `datos_clave`; con `difieren`, trae la marca y las dos citas), abstención (una falla técnica no cuenta), y tiempo (mediana y máximo). Guarda una carpeta por corrida en `evals/corridas/`, con fecha, commit y modelo en el nombre: `parametros.json`, `resultados.jsonl` y `resumen.md` con las medidas y los casos fallados. Los casos de prueba de esta tarea son sintéticos y van en `tests/fixtures/`.
- **Archivos:** `evaluon/queries/evaluation.py`, `evaluon/queries/management/commands/correr_evals.py`, `tests/queries/test_evaluation.py`, `tests/fixtures/evals/` (casos sintéticos).
- **Verificación:** `pytest tests/queries/test_evaluation.py`, con los dobles y una carpeta temporal de corridas. Con cuatro casos sintéticos (acierto, cita equivocada, abstención correcta, falla técnica) las cuatro medidas dan los valores esperados; el caso sin visto bueno no se corre; la carpeta de la corrida trae los tres archivos; cada consulta de la corrida queda en el registro con el canal `eval`.
- **No tocar:** `evals/casos/` y `evals/README.md`; `evaluon/queries/services.py` (se llama, no se modifica); `evaluon/queries/retrieval.py`.
- **Entorno:** Cualquier equipo con Docker

### T-040 · Unir recuperación y generación completas con su registro

- **Requisitos:** REQ-008, REQ-009, REQ-012, REQ-018, REQ-019
- **Qué hay que hacer:** (unión final del plan, de a una) actualizar `queries/services.py` para usar la recuperación de T-032 y T-033 y la generación de T-034, y completar el registro de la consulta: cada candidato con su camino, su puntaje y el origen de su texto; unidades enviadas, agregadas por relación y dejadas afuera por espacio; puntaje más alto; decisión de abstención y motivo; modelos de generación, embeddings y reranker con nombre y huella, compilación del motor, contexto, temperatura, semilla, pensamiento y máximo de salida; copia de todos los parámetros de búsqueda; versión de las instrucciones y pedido completo; salida sin tocar; anomalías; tiempos por etapa.
- **Archivos:** `evaluon/queries/services.py`, `tests/queries/test_services.py`, `tests/queries/test_services_full.py`.
- **Verificación:** `pytest tests/queries`, con los dobles. Cubre de punta a punta el criterio de REQ-018 (artículo del régimen específico y dictamen: la respuesta cita primero el artículo y cada cita lleva su categoría) y el de REQ-019 (régimen específico y marco nacional distintos: la respuesta trae los dos textos y la marca). El registro de una consulta permite ver todo lo de la fila "Consulta" de "Registro de auditoría" (REQ-012). Siguen pasando los criterios de REQ-008 y REQ-009.
- **No tocar:** `evaluon/queries/views.py`, `forms.py` y las plantillas (T-037 y T-041); `evaluon/queries/retrieval.py` y `answering.py` salvo un defecto de integración; `evaluon/queries/models.py`.
- **Entorno:** Cualquier equipo con Docker

### T-041 · Mostrar y registrar la búsqueda en la pantalla

- **Requisitos:** REQ-006, REQ-010, REQ-012
- **Qué hay que hacer:** (bloques H e I; unión final del plan, de a una) sumar a la pantalla de consulta el formulario de búsqueda directa: por norma (se elige de la lista) y número de artículo, o por palabras. Función de búsqueda en `queries/services.py`: recibe al usuario, comprueba el rol (los dos roles pueden buscar), usa la fecha del día, llama a `queries/search.py` y deja el hecho `search` con el tipo de búsqueda, los términos, la fecha de referencia y las unidades devueltas con su marca de derogada. Cada resultado se muestra con su ruta, su categoría, su texto literal, el enlace al original, los cambios vigentes, la marca de derogada con la norma que la derogó y la fecha, y los vínculos de su norma con otras. Textos en lenguaje llano.
- **Archivos:** `evaluon/queries/services.py`, `evaluon/queries/views.py`, `evaluon/queries/forms.py`, `evaluon/queries/urls.py`, `evaluon/templates/` (consulta), `evaluon/static/`, `tests/queries/test_search_screen.py`.
- **Verificación:** `pytest tests/queries/test_search_screen.py`. Cubre el criterio de REQ-010: una persona con rol de lectura busca norma y artículo en la pantalla de consulta y obtiene la unidad con su texto; si está derogada, se muestra marcada. Cubre el de REQ-006 en la pantalla: al ver una unidad de cualquiera de las dos normas vinculadas se muestra el vínculo. La búsqueda queda en el registro con sus términos y sus resultados (REQ-012).
- **No tocar:** `evaluon/queries/search.py` salvo un defecto de integración; la función de consulta de `services.py`; `evaluon/norms/views.py`; la plantilla de ingreso.
- **Entorno:** Cualquier equipo con Docker

### T-042 · Agregar calibración del umbral y comparación de corridas

- **Requisitos:** REQ-008, REQ-009. No implementa un requisito funcional: habilita calibrar la abstención de REQ-009 y sostener la regla de P7.
- **Qué hay que hacer:** (bloque K) completar `queries/evaluation.py` y `correr_evals`: medidas de diagnóstico de recuperación (unidad correcta entre los candidatos, por camino y en la unión; entre las seleccionadas; su posición; preguntas con respuesta frenadas por el umbral; tiempo de la recuperación); salidas con falla de formato o de cita; los casos de REQ-018 y REQ-019 informados aparte; comparación con la corrida anterior e igualdad al repetir la corrida, en `resumen.md`; la comparación quitando piezas (solo vectores, solo palabras, combinada sin reranker, completa), usando los parámetros de T-032; y la calibración del umbral: puntaje más alto de cada pregunta, el umbral más alto que frena por error a lo sumo el 5 % de las preguntas con respuesta, calculado dejando cada vez una afuera, informado como provisorio. La calibración no cambia `settings.py`: propone el valor.
- **Archivos:** `evaluon/queries/evaluation.py`, `evaluon/queries/management/commands/correr_evals.py`, `tests/queries/test_evaluation_diagnostics.py`, `tests/queries/test_calibration.py`, `tests/fixtures/evals/`.
- **Verificación:** `pytest tests/queries/test_evaluation_diagnostics.py tests/queries/test_calibration.py`, con los dobles. Con puntajes preparados, la calibración propone el umbral esperado; el resumen compara con una corrida anterior y lista las diferencias; la comparación quitando piezas produce las cuatro configuraciones.
- **No tocar:** `evals/casos/`; `evaluon/settings.py`; `evaluon/queries/retrieval.py`, `answering.py` y `services.py`.
- **Entorno:** Cualquier equipo con Docker

### Etapa 4 · Corpus real, calibración y evals

De a una, en la MSI, con los servicios reales. Necesita los documentos en `corpus/normativa/` (hoy, la Disp. 297/03; los demás llegan después) y el conjunto de preguntas con visto bueno en `evals/casos/`. Las dos cosas las prepara el Coordinador con el responsable y la Comisión, en paralelo con las etapas anteriores.

### T-043 · Cargar y validar el corpus real y ajustar las reglas

- **Requisitos:** REQ-003, REQ-004, REQ-005, REQ-015
- **Qué hay que hacer:** con la base `evaluon` vacía, cargar con `cargar_norma` cada documento de `corpus/normativa/` anotado en `corpus/manifiesto.csv`, con sus datos y su categoría; revisar cada informe; ajustar las reglas de partición, las reglas por sitio de las páginas web y, si hay escaneos reales, los umbrales de confianza, cada ajuste con su test, y volver a leer con `releer_norma` hasta que el informe no tenga nada sin ubicar que sea normativo. La validación de cada informe la hace el responsable de normativa con su usuario (`validar_informe`): el desarrollador no valida. Si un documento tiene tramos que no se resuelven con una regla razonable, se deja sin validar y se informa (condición del ADR-0004 para su alternativa L). Con el corpus cargado, probar a mano una vez, en el navegador que usa la Comisión: el visor abre el PDF en la página citada y el original de una página web no ejecuta scripts ni carga recursos externos. Anotar en `entorno.md` los documentos cargados y los comandos usados. Si llegan documentos después de cerrada la tarea, el Coordinador abre una tarea nueva.
- **Archivos:** `evaluon/norms/splitting/`, `evaluon/norms/reading/web.py`, `evaluon/norms/reading/ocr.py`, los tests de `tests/norms/` de esas reglas, `specs/001-normativa/entorno.md`.
- **Verificación:** `listar_normas` muestra cada documento del manifiesto con su lectura validada por el responsable, o la lista de los que quedaron sin validar con su motivo; el informe de la Disp. 297/03 coincide con la tabla esperada de T-023 (criterio de REQ-003 con el documento cargado); una consulta en la pantalla cita solo normas validadas (criterio de REQ-005); suite en verde. Si el corpus trae una norma en más de un formato, se cumple el criterio de REQ-015 con los archivos reales.
- **No tocar:** `corpus/`; `evaluon/norms/models.py`; `evaluon/queries/`; los parámetros de `settings.py` (T-045).
- **Entorno:** MSI con GPU

### T-044 · Registrar las relaciones y versiones del corpus

- **Requisitos:** REQ-006, REQ-007
- **Qué hay que hacer:** preparar, a partir de los documentos cargados, la lista de relaciones (qué norma modifica, complementa, reglamenta o deroga a cuál, con qué unidades y desde qué fecha) y de versiones; el responsable de normativa la revisa y las registra con `registrar_relacion` y `registrar_version`. El cambio lo registra una persona: el desarrollador prepara y asiste, no decide. Anotar en `entorno.md` lo registrado. Necesita en el corpus al menos una norma que modifique o derogue a otra; si todavía no la hay, se deja constancia y la tarea queda bloqueada hasta que llegue.
- **Archivos:** `specs/001-normativa/entorno.md`.
- **Verificación:** `listar_normas` muestra los vínculos en las dos normas de cada relación (criterio de REQ-006 con el corpus real); en la búsqueda de la pantalla, un artículo modificado se muestra con el texto literal de la norma que lo modifica (criterio de REQ-007 a la fecha del día); el registro de auditoría trae cada relación y cada versión con su usuario.
- **No tocar:** cualquier archivo de código (un defecto se informa y se abre una tarea); `corpus/`.
- **Entorno:** MSI con GPU

### T-045 · Calibrar el umbral con el conjunto de preguntas

- **Requisitos:** REQ-009. No implementa un requisito funcional: habilita la abstención de REQ-009 con un umbral medido.
- **Qué hay que hacer:** con el corpus validado y los casos con visto bueno, correr la calibración de T-042 con los servicios reales: puntaje más alto de cada pregunta, umbral más alto que frena por error a lo sumo el 5 % de las preguntas con respuesta, dejando cada vez una afuera. Fijar el valor en `settings.py` como provisorio y anotar en `entorno.md` el valor, la fecha y la corrida de la que sale. Si no hay casos con visto bueno en `evals/casos/`, la tarea queda bloqueada.
- **Archivos:** `evaluon/settings.py` (solo el umbral), `evals/corridas/` (la carpeta de la corrida), `specs/001-normativa/entorno.md`.
- **Verificación:** la carpeta de la corrida de calibración existe con sus tres archivos y el umbral propuesto; `settings.py` tiene ese valor; suite en verde.
- **No tocar:** `evals/casos/`; las instrucciones de `queries/prompts/`; los demás parámetros de `settings.py`.
- **Entorno:** MSI con GPU

### T-046 · Correr las evals y medir tiempo y memoria

- **Requisitos:** REQ-008, REQ-009, REQ-018, REQ-019. No implementa un requisito funcional: mide las exigencias de calidad y de tiempo de la spec.
- **Qué hay que hacer:** correr `correr_evals` completo con los servicios ya cargados, una corrida por vez; repetir la corrida para comprobar la igualdad; correr una vez la comparación quitando piezas; medir con `nvidia-smi` la memoria de video con los tres modelos cargados y medir el tiempo de la búsqueda exacta por vectores con el corpus real (si supera 200 ms se informa: agregar un índice es un cambio de esquema y va en tarea aparte). Anotar el resumen en `entorno.md`. Si no se alcanzan las exigencias, la tarea termina informando qué falló y con qué casos; no ajusta nada: los pasos siguientes (instrucciones, 8 bits, modelo de contraste, reemplazo de embeddings o reranker) los decide el responsable y van en tareas nuevas. La corrida que se presenta para aprobar la revisa además el responsable contra las respuestas esperadas.
- **Archivos:** `evals/corridas/` (las carpetas de las corridas), `specs/001-normativa/entorno.md`.
- **Verificación:** el `resumen.md` de la corrida muestra: cita literal 100 %; respuesta correcta que cita la unidad correcta en al menos 85 % de las preguntas con respuesta; abstención en al menos 90 % de las preguntas sin respuesta; máximo de 30 segundos por consulta; y, aparte, los casos de REQ-018 y REQ-019. La memoria total queda dentro de 20 GB.
- **No tocar:** `evals/casos/`; `evaluon/settings.py`, `queries/prompts/` y todo archivo de código.
- **Entorno:** MSI con GPU

### Etapa 5 · Cierre

De a una, en la MSI.

### T-047 · Probar una consulta con la red desconectada

- **Requisitos:** REQ-008, REQ-013. No implementa un requisito funcional: comprueba el funcionamiento sin conexión que pide la spec para la consulta.
- **Qué hay que hacer:** con el equipo sin acceso a internet, levantar todo con `docker compose up -d`, ingresar, hacer una consulta con respuesta y una búsqueda, y abrir un documento original. Revisar en `docker-compose.yml` que los tres servicios de IA y la base están en la red interna sin puertos publicados, que arrancan con `--offline` y que `app` publica solo en `127.0.0.1`. Correr la lectura de los tres formatos en un contenedor sin red. Anotar el resultado en `entorno.md`. Un defecto se informa; no se corrige en esta tarea.
- **Archivos:** `specs/001-normativa/entorno.md`.
- **Verificación:** con la red desconectada, la consulta devuelve la respuesta con sus citas y el navegador no intenta cargar nada externo; `pytest tests/norms` pasa en un contenedor sin red; `entorno.md` trae la fecha, los pasos y el resultado.
- **No tocar:** `docker-compose.yml` y todo archivo de código.
- **Entorno:** MSI con GPU

### T-048 · Probar el respaldo y la restauración de la base

- **Requisitos:** REQ-002, REQ-012. No implementa un requisito funcional: comprueba que los originales (REQ-002) y el registro (REQ-012) sobreviven a un respaldo y a una restauración.
- **Qué hay que hacer:** seguir el procedimiento del plan para una base con datos: detener `app`, respaldar con `docker compose exec db pg_dump -Fc evaluon` en `backups/` con fecha, restaurar en una base aparte y comparar. Comprobar que el servicio `migrate`, sobre la base con datos, solo comprueba y no migra. No se borra ni se pisa la base cargada. Anotar en `entorno.md` los comandos exactos y los tiempos.
- **Archivos:** `specs/001-normativa/entorno.md`; `scripts/migrate_on_start.sh` solo si la prueba muestra un defecto.
- **Verificación:** en la base restaurada, la huella de cada archivo original es igual a la registrada en su carga, la cantidad de hechos de auditoría y de consultas coincide con la de origen, y una consulta guardada se muestra igual en la pantalla.
- **No tocar:** la base `evaluon` cargada (solo se lee); `docker-compose.yml`.
- **Entorno:** MSI con GPU

### T-049 · Levantar todo desde cero y dejar datos para el runbook

- **Requisitos:** REQ-012, REQ-016. No implementa un requisito funcional: comprueba que el sistema se levanta con una orden en una base vacía (P5) y deja lo que el runbook necesita.
- **Qué hay que hacer:** en una copia limpia del repositorio y sobre una base vacía aparte: `scripts/fetch_models.sh` (o copiar `models/`) con verificación de huellas, `docker compose up -d`, comprobar que `migrate` aplicó el esquema, crear un usuario, cargar y validar una norma y hacer una consulta. Anotar cada paso que no esté automatizado. Dejar en `entorno.md` la sección "Datos para el runbook": descarga de modelos, procedimiento de migración con respaldo previo, respaldo y restauración, limpieza de sesiones vencidas, restablecimiento de clave con `changepassword` (que no pasa por el registro) y fallas conocidas.
- **Archivos:** `specs/001-normativa/entorno.md`; `scripts/fetch_models.sh` y `scripts/migrate_on_start.sh` solo si la prueba muestra un defecto.
- **Verificación:** desde la copia limpia, siguiendo solo lo anotado, los seis servicios quedan arriba, el alta de usuario queda registrada, el ingreso funciona y una consulta devuelve su respuesta con cita; `entorno.md` trae la sección para el runbook.
- **No tocar:** `docs/runbook.md` (lo escribe el implementador en el despliegue); la base `evaluon` cargada; `docker-compose.yml` y todo archivo de código.
- **Entorno:** MSI con GPU

## Paralelismo

Los grupos salen de dos reglas: ninguna tarea del grupo depende de otra del grupo, y ninguna comparte archivos con otra. El Coordinador decide cuántas abre a la vez según lo que pueda revisar.

- **Etapa 0:** de a una, en la MSI: T-001, T-002, T-003, T-004, T-005. Comparten `docker-compose.yml` y `entorno.md`.
- **Etapa 1:** de a una: T-006, T-007, T-008, T-009, T-010, T-011. Comparten el esquema, `settings.py`, `urls.py` y `tests/conftest.py`.
- **Etapa 2:** cuatro líneas en paralelo cuando terminó T-011:
    - línea de datos: T-012, después T-013, después T-014;
    - validación: T-015;
    - pantalla: T-016;
    - consulta: T-017, después T-018.
    - Después, de a una: T-019 (cuando terminaron T-016 y T-018) y T-020 (cuando terminaron T-014, T-015 y T-019; en la MSI).
    - El plan pone T-017 y T-018 después de las dos líneas; por dependencias y archivos se pueden abrir junto con ellas.
- **Adelantos posibles durante la etapa 1** (no comparten archivos con T-009, T-010 ni T-011): T-012, T-013 y T-036 desde que terminó T-008; T-016 y T-035 desde que terminó T-010. T-014 puede seguir a T-013 sin esperar a T-011.
- **Etapa 3, primera tanda** (cada una cuando terminó lo que figura en su fila "Depende de"): T-021, T-022, T-023, T-029, T-030, T-031, T-032, T-034, T-035, T-036, T-038 y T-039 en paralelo. T-037 se suma cuando terminó T-036.
- **Etapa 3, cadenas:**
    - partición: T-023, después T-024, después T-025;
    - carga: T-026 después de T-025; T-027 después de T-026; T-028 después de T-021, T-022 y T-027;
    - recuperación: T-033 después de T-032;
    - unión: T-040 después de T-033 y T-034; T-041 después de T-035, T-037 y T-040; T-042 después de T-039 y T-040.
    - T-041 y T-042 se pueden abrir en paralelo. T-040 y T-037 también.
- **No van juntas aunque no dependan entre sí:** las que comparten carpeta o archivo quedaron encadenadas (T-023 a T-025 en `norms/splitting/`; T-026 a T-028 en `services/loading.py`; T-019, T-040 y T-041 en `queries/services.py`; T-016, T-019, T-037 y T-041 en `queries/views.py` y las plantillas; T-039 y T-042 en `queries/evaluation.py`).
- **Etapa 4:** de a una, en la MSI: T-043, T-044, T-045, T-046. Mientras corre T-043 pueden seguir abiertas T-029, T-030, T-038 y T-042, que no tocan sus archivos.
- **Etapa 5:** de a una, en la MSI: T-047, T-048, T-049.
- **Recursos que no se comparten:** la GPU y la base de la MSI. T-020 y las tareas de las etapas 0, 4 y 5 no se superponen entre sí. Las evals se corren de a una.
- **Solo en la MSI:** T-001 a T-005, T-020 y T-043 a T-049. Las demás corren en cualquier equipo con Docker.
- **Necesitan a una persona además del desarrollador:** T-001 (datos del equipo), T-020 (PDF con texto en el corpus), T-043 y T-044 (valida y registra el responsable de normativa), T-045 y T-046 (casos con visto bueno; revisión del responsable en la corrida que se presenta).

## Cobertura

| Requisito | Tareas |
|---|---|
| REQ-001 | T-008, T-014 |
| REQ-002 | T-014, T-036, T-048 |
| REQ-003 | T-008, T-013, T-023, T-024, T-031, T-043 |
| REQ-004 | T-012, T-013, T-014, T-021, T-025, T-027, T-028, T-043 |
| REQ-005 | T-009, T-015, T-017, T-027, T-032, T-035, T-043 |
| REQ-006 | T-029, T-035, T-041, T-044 |
| REQ-007 | T-009, T-029, T-030, T-033, T-037, T-044 |
| REQ-008 | T-001, T-002, T-003, T-004, T-011, T-017, T-018, T-019, T-020, T-031, T-032, T-034, T-039, T-040, T-042, T-046, T-047 |
| REQ-009 | T-002, T-003, T-011, T-017, T-018, T-019, T-034, T-039, T-040, T-042, T-045, T-046 |
| REQ-010 | T-004, T-009, T-035, T-041 |
| REQ-011 | T-008, T-026 |
| REQ-012 | T-007, T-008, T-010, T-014, T-015, T-019, T-020, T-026, T-038, T-040, T-041, T-048, T-049 |
| REQ-013 | T-005, T-016, T-019, T-020, T-037, T-047 |
| REQ-014 | T-016, T-037 |
| REQ-015 | T-012, T-021, T-022, T-025, T-028, T-037, T-043 |
| REQ-016 | T-005, T-006, T-007, T-038, T-049 |
| REQ-017 | T-008, T-014 |
| REQ-018 | T-033, T-034, T-037, T-040, T-046 |
| REQ-019 | T-033, T-034, T-037, T-040, T-046 |

Los requisitos no funcionales de la spec no tienen identificador. Los atienden: calidad y tiempo, T-039, T-042, T-045 y T-046; funcionamiento sin conexión, T-002, T-003, T-016 y T-047; claves no legibles, T-006; lenguaje llano, T-014, T-037 y T-041; registro del usuario que consulta, T-019.
