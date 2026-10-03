# Tareas 003 · Procedimiento, pliego final y matriz de cumplimiento

Plan: `specs/003-pliego-matriz/plan.md`

Despliegue: pendiente

> El tablero (`docs/tablero.md`) se genera de este archivo. Al aprobarse el despliegue, la línea de arriba pasa a `Despliegue: aprobado AAAA-MM-DD`.

Estados: pendiente · en curso · en verificación · terminada · bloqueada

Dos tareas que no dependen entre sí y no comparten archivos se pueden hacer en paralelo.

Formato liviano (ADR-0014, punto 6): este archivo tiene solo la tabla y lo que pide cada tarea. Los avisos para una tarea van en `specs/003-pliego-matriz/avisos/T-NNN.md`, que se crea cuando hace falta, y el encargo lo nombra. La verificación de cada tarea queda en `specs/003-pliego-matriz/verificacion/T-NNN.md` (ADR-0014, punto 3).

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-067 | Crear las tablas, los tipos de hecho y los parámetros de la 003 | REQ-022, REQ-023, REQ-024, REQ-025, REQ-026, REQ-027, REQ-028, REQ-029, REQ-030, REQ-031 | — | pendiente |
| T-068 | Sumar el rol de la Comisión a los usuarios | REQ-026, REQ-027, REQ-029 | T-067 | pendiente |
| T-069 | Registrar un procedimiento y mostrar su régimen | REQ-022 | T-068 | pendiente |
| T-070 | Partir un pliego en tramos con control de cobertura | REQ-024, REQ-025, REQ-028 | T-067 | pendiente |
| T-071 | Ejecutar pedidos en segundo plano con su propio motor | REQ-024, REQ-030 | T-067 | pendiente |
| T-072 | Cargar los documentos del pliego y leerlos en segundo plano | REQ-023, REQ-028, REQ-031 | T-069, T-070, T-071 | pendiente |
| T-073 | Proponer la matriz en nivel media | REQ-024, REQ-025, REQ-028, REQ-030 | T-072 | pendiente |
| T-074 | Mostrar la matriz propuesta, la cobertura y el aviso de fin | REQ-024, REQ-025, REQ-028, REQ-030, REQ-031 | T-073 | pendiente |
| T-075 | Probar el hilo mínimo con el caso-00 y los servicios reales | REQ-022, REQ-023, REQ-024, REQ-025, REQ-028 | T-074, T-076 | pendiente |
| T-076 | Preparar la lista esperada del caso-00 | REQ-024, REQ-025 | — | pendiente |
| T-077 | Medir una propuesta contra una lista esperada | REQ-024, REQ-025, REQ-028, REQ-030 | T-073 | pendiente |
| T-078 | Completar los niveles alta y exigente | REQ-024, REQ-030 | T-073 | pendiente |
| T-079 | Revisar la matriz: confirmar, corregir, quitar y agregar | REQ-026, REQ-028 | T-074 | pendiente |
| T-080 | Sugerir consecuencias con fundamento | REQ-029 | T-078 | pendiente |
| T-081 | Elegir la consecuencia en la pantalla | REQ-029 | T-079, T-080 | pendiente |
| T-082 | Validar la matriz y abrir versiones nuevas | REQ-026, REQ-027, REQ-028 | T-081 | pendiente |
| T-083 | Incorporar circulares y respuestas a consultas | REQ-031 | T-080 | pendiente |
| T-084 | Correr la medición del caso-00 | REQ-024, REQ-025, REQ-029, REQ-030 | T-075, T-076, T-077, T-080 | pendiente |
| T-085 | Ofrecer solo los niveles que mejoran | REQ-030 | T-084 | pendiente |

## Para todas las tareas

- **Entorno.** "Cualquier equipo con Docker": tests con los dobles de los clientes de IA y Postgres en contenedor. "MSI con GPU": servicios de IA reales. "Datos": trabajo del Coordinador con el responsable, sin código.
- **Cita literal.** Una sola definición, la del plan 001: el texto mostrado es igual a `canonical_text[char_start:char_end]` de su lectura.
- **Caso de referencia.** `corpus/casos/caso-00/` no se sube al repositorio. Ningún archivo del repositorio (tests, fixtures, informes, avisos, verificaciones) copia texto de sus documentos con datos personales. Los tests usan pliegos sintéticos. Los informes de las tareas que corren el caso-00 llevan identificadores, claves de tramo, cuentas y tiempos, no texto del pliego.
- **Reutilización.** La lectura (`evaluon/norms/reading/`), el texto canónico (`evaluon/norms/splitting/canonical.py`), `applicable_regimes` y la recuperación de la 001 se usan como están. Si una tarea necesita cambiarlos, se detiene y avisa.
- **Suite.** La regla del ADR-0012.

## Detalle

### T-067 · Crear las tablas, los tipos de hecho y los parámetros de la 003

- **Qué hacer:** crear la aplicación `evaluon/tenders/` con todos los modelos de "Modelo de datos" del plan (procedimiento, documento y su archivo, lectura, tramo, pedido, propuesta, pedido al modelo, disposición, versión de matriz, requisito, fuente de circular, consecuencia, pendiente, cambio) con sus restricciones; los triggers de solo inserción (`tenders_run_step`, `tenders_requirement_change`) y de inmutabilidad de una versión validada, con su reversa; sumar los diez tipos de hecho a `audit_event` con su migración; registrar la aplicación y sumar todos los parámetros de "Parámetros" a `settings.py`, incluido `GENERATION_BATCH_URL` (por omisión, `http://generation_batch:8080`).
- **Archivos:** `evaluon/tenders/__init__.py`, `apps.py`, `models.py`, `migrations/`; `evaluon/audit/models.py`, `evaluon/audit/migrations/` (una migración nueva); `evaluon/settings.py`; `tests/tenders/test_models.py`.
- **Verificación:** `migrate` sobre una base vacía y `migrate --check` sin cambios pendientes; tests: restricciones de valores, huella única por procedimiento, número único de procedimiento, un solo borrador por procedimiento, UPDATE sobre un requisito de una versión validada rechazado por la base, UPDATE sobre `tenders_run_step` rechazado; los tipos de hecho nuevos se registran con `audit.record`.
- **No tocar:** `accounts` (T-068), `docker-compose.yml` (T-071), cualquier función de negocio.
- **Entorno:** cualquier equipo con Docker.

### T-068 · Sumar el rol de la Comisión a los usuarios

- **Qué hacer:** campo `commission_role` (`''`, `operator`, `evaluator`) en el usuario, con su migración; `require_commission_role(user, rol)` en `permissions.py`, donde el evaluador incluye al operador y el rechazo se registra como `rejected`; opción `--rol-comision` en `crear_usuario`, registrada en `user_created`; usuarios de prueba de la Comisión en un `conftest.py` propio de `tests/tenders/`.
- **Archivos:** `evaluon/accounts/models.py`, `evaluon/accounts/migrations/` (una nueva), `evaluon/accounts/permissions.py`, `evaluon/accounts/management/commands/crear_usuario.py`, `tests/accounts/test_commission_role.py`, `tests/tenders/conftest.py`.
- **Verificación:** tests: el evaluador pasa donde se exige operador y no al revés; un usuario sin rol de la Comisión es rechazado y queda `rejected`; `crear_usuario --rol-comision evaluador` crea el usuario con ese rol; los tests de `accounts` de la 001 siguen pasando.
- **No tocar:** el campo `role` y sus reglas; `tests/conftest.py`.
- **Entorno:** cualquier equipo con Docker.

### T-069 · Registrar un procedimiento y mostrar su régimen

- **Qué hacer:** `services/procedures.py` (registrar y listar, con rol de operador; fecha futura rechazada; régimen con `applicable_regimes`; hecho `procedure` con régimen y versión de la normativa); página "Procedimientos" con la lista y el formulario, y la línea de régimen con el texto fijo de la 001; enlace en la navegación para usuarios con rol de la Comisión.
- **Archivos:** `evaluon/tenders/services/__init__.py`, `services/procedures.py`, `views/__init__.py`, `views/procedures.py`, `urls.py`; `evaluon/urls.py`; `evaluon/templates/tenders/procedures.html`; `evaluon/templates/base.html`; `tests/tenders/test_procedures.py`.
- **Verificación:** tests con las normas de prueba de la 001: fecha 2022-12-15 muestra la Disposición 297/03; 2023-01-02, la 247/2022; fecha futura rechazada sin registro; número repetido rechazado; el hecho guarda régimen y versión; un usuario sin rol de la Comisión no ve la página.
- **No tocar:** `evaluon/queries/` (se usa `applicable_regimes` como está).
- **Entorno:** cualquier equipo con Docker.

### T-070 · Partir un pliego en tramos con control de cobertura

- **Qué hacer:** `segmenting.py` con las reglas de "Tramos" del plan sobre el texto canónico (`build_canonical_text`): secciones, cláusulas numeradas con control de secuencia, títulos, renglones, viñetas e incisos, anexos y párrafos, tablas (a partir de las zonas que recibe), páginas sin texto legible, tramos largos partidos, claves y rutas, y el control de cobertura; `tables.py` con las zonas de tabla de cada página de un PDF (pdfplumber). Un generador de pliegos sintéticos en PDF para las pruebas, con la forma del caso-00 (secciones, numeración de cuatro niveles con y sin espacio, renglones, viñetas, anexo, tabla, índice, encabezado repetido) y sin datos reales.
- **Archivos:** `evaluon/tenders/segmenting.py`, `evaluon/tenders/tables.py`, `tests/tenders/pdfs.py`, `tests/tenders/test_segmenting.py`, `tests/tenders/test_tables.py`.
- **Verificación:** tests con una tabla de casos escrita a mano: claves esperadas (`sec-i/7.5.2`, `sec-iii/1.1`, `sec-ii/1.2/v-1`, `sec-iv/anexo-i/p-1`, `pagina-7`); "3.972 kcal" y "1.300 mg" al comienzo de una línea no cortan; "10.2.1.Una vez" corta; los renglones pasan a los tramos que cuelgan; el índice no produce tramos; cada texto es igual a su recorte; la cobertura suma el total.
- **No tocar:** `evaluon/norms/` (se importa, no se modifica).
- **Entorno:** cualquier equipo con Docker.

### T-071 · Ejecutar pedidos en segundo plano con su propio motor

- **Qué hacer:** `jobs.py` (encolar, tomar con `FOR UPDATE SKIP LOCKED`, terminar, fallar, pasar a `failed` los interrumpidos al arrancar, tabla de manejadores por tipo de pedido, aviso visto); comando `procesar_pedidos`; servicios `worker` y `generation_batch` en `docker-compose.yml` (ADR-0018), y montaje con escritura de `corpus/casos` en `app` para las corridas de medición; máximo de salida y espera por pedido en el cliente de generación, con su doble. Medir la memoria de video con los cuatro modelos cargados.
- **Archivos:** `evaluon/tenders/jobs.py`, `evaluon/tenders/management/__init__.py`, `management/commands/__init__.py`, `management/commands/procesar_pedidos.py`; `docker-compose.yml`; `.env.example`; `evaluon/ai/generation.py`; `tests/conftest.py`; `tests/tenders/test_jobs.py`; `tests/tenders/test_generation_batch.py` (máximo de salida y espera del cliente); informe en `specs/003-pliego-matriz/verificacion/T-071.md`.
- **Verificación:** tests: dos tomas simultáneas no toman el mismo pedido; un pedido que falla queda `failed` con su motivo; un pedido `running` al arrancar pasa a `failed` "interrumpido"; el cliente manda el máximo de salida pedido. En la MSI: `docker compose up -d` con los ocho servicios sanos y `nvidia-smi` con los cuatro modelos cargados, anotado en la verificación. Si el total supera 20 GB, se informa antes de seguir.
- **No tocar:** la configuración del servicio `generation` y de los demás servicios de la 001; los tipos de pedido concretos (T-072 y T-073).
- **Entorno:** cualquier equipo con Docker para los tests; MSI con GPU para la medición.

### T-072 · Cargar los documentos del pliego y leerlos en segundo plano

- **Qué hacer:** `services/documents.py`: cargar (operador; tipo, título, fecha obligatoria en circulares y respuestas; mismo archivo rechazado; hecho `tender_load`), encolar la lectura, el manejador `read_document` (lectura de la 001, zonas de tabla, tramos, informe, hecho `tender_read`) y la entrega del original con sesión; sección de documentos y formulario de carga en la página del procedimiento.
- **Archivos:** `evaluon/tenders/services/documents.py`, `evaluon/tenders/jobs.py` (registra el manejador), `evaluon/tenders/views/documents.py`, `evaluon/tenders/urls.py`, `evaluon/templates/tenders/procedure.html`, `tests/tenders/test_documents.py`.
- **Verificación:** tests: un pliego sintético en tres documentos; la huella de lo que entrega la vista es igual a la de cada archivo; el mismo archivo dos veces se rechaza y queda registrado; una circular sin fecha se rechaza; un PDF con una página de ruido deja esa página como tramo pendiente (REQ-028); el informe cuenta tramos por tipo.
- **No tocar:** `evaluon/norms/`; `segmenting.py` (si hace falta un cambio, aviso a T-070 por `avisos/`).
- **Entorno:** cualquier equipo con Docker.

### T-073 · Proponer la matriz en nivel media

- **Qué hacer:** `services/matrix.py` (pedir una propuesta con nivel, por omisión alta; rechazos del plan; hecho `matrix_request`); `proposal/run.py` con las pasadas de media; `proposal/extraction.py` (lotes, esquema con una propiedad obligatoria por tramo, validación, reintento único, partición del lote si la salida se corta); `proposal/quotes.py`; instrucciones `prompts/matriz-extraccion-v1.md` con los criterios de las decisiones 4 y 5; el manejador `propose_matrix`: crea la versión borrador con requisitos, disposiciones y pendientes, guarda cada pedido en `tenders_run_step` y deja `matrix_proposal`. Mientras alta y exigente no existan, piden lo mismo que media y quedan registrados con su nombre; T-078 completa sus pasadas.
- **Archivos:** `evaluon/tenders/services/matrix.py`, `evaluon/tenders/proposal/__init__.py`, `proposal/run.py`, `proposal/extraction.py`, `proposal/quotes.py`, `evaluon/tenders/prompts/matriz-extraccion-v1.md`, `evaluon/tenders/jobs.py` (registra el manejador), `tests/tenders/test_extraction.py`, `tests/tenders/test_quotes.py`, `tests/tenders/test_matrix_request.py`.
- **Verificación:** tests con el doble del motor: todo tramo queda con requisitos, descarte o pendiente; un tramo sin disposición se reintenta y queda pendiente; una cita que no está en el tramo se reintenta y queda como cita amplia; dos citas iguales se unen; una salida cortada parte el lote; el renglón sale del tramo; un tramo descartado con marcadores queda pendiente; sin elegir, el nivel es alta; el pedido registra modelos, parámetros, versiones de instrucciones, régimen y versión de la normativa.
- **No tocar:** las vistas y plantillas (T-074); consecuencias y circulares (T-080 y T-083).
- **Entorno:** cualquier equipo con Docker.

### T-074 · Mostrar la matriz propuesta, la cobertura y el aviso de fin

- **Qué hacer:** formulario "Proponer matriz" con el nivel y pedidos en curso en la página del procedimiento; página de la matriz (encabezado, resumen, pendientes primero, requisitos agrupados con clase, texto literal, documento, página, cláusula, enlace al original en la página, textos de circulares y respuestas cuando existan, marca de cita amplia); página de cobertura; aviso de pedidos terminados en todas las páginas.
- **Archivos:** `evaluon/tenders/views/matrix.py`, `evaluon/tenders/urls.py`, `evaluon/templates/tenders/procedure.html`, `evaluon/templates/tenders/matrix.html`, `evaluon/templates/tenders/coverage.html`, `evaluon/templates/base.html`, `evaluon/static/` (hoja de estilos propia), `tests/tenders/test_matrix_screen.py`.
- **Verificación:** tests con el cliente de pruebas: la página muestra cada requisito con su texto igual al recorte, su página y su cláusula; los pendientes aparecen primero con su motivo; la cobertura lista todos los tramos; un requisito con fuente de circular muestra el texto vigente y el original con sus citas; el aviso aparece una vez y desaparece al verlo; ninguna página referencia direcciones externas.
- **No tocar:** las acciones de revisión (T-079) y de consecuencias (T-081).
- **Entorno:** cualquier equipo con Docker.

### T-075 · Probar el hilo mínimo con el caso-00 y los servicios reales

- **Qué hacer:** con la lista esperada ya aprobada (T-076), registrar el procedimiento del caso-00 por pantalla, cargar su pliego, pedir la matriz en nivel media y verla en la pantalla, con los servicios reales. Anotar: tramos por tipo, requisitos, descartes por motivo, pendientes, citas reintentadas y amplias, tiempo por pasada y total, memoria de video. Repetir con la red de Docker sin salida a internet. No se compara con la lista esperada ni se cambian instrucciones a partir de este resultado (decisión 7).
- **Archivos:** ninguno de código; informe en `specs/003-pliego-matriz/verificacion/T-075.md`, sin texto del pliego.
- **Verificación:** el informe muestra 100 % de tramos con disposición y 100 % de citas literales, la matriz visible en la pantalla y el tiempo medido; sin red, el resultado es el mismo.
- **No tocar:** instrucciones y parámetros; la lista esperada.
- **Entorno:** MSI con GPU.

### T-076 · Preparar la lista esperada del caso-00

- **Qué hacer:** el Coordinador escribe `matriz-esperada.yaml` con el formato del plan, leyendo el PDF cláusula por cláusula, sin correr la propuesta de matriz, con los criterios de las decisiones 4 y 5; la contrasta con lo que verificó la evaluación (`en_dictamen`); prepara para el responsable la tabla de ejemplos, las cuentas por sección, clase y renglón, y los casos dudosos. El responsable da el visto bueno, que se anota en el archivo. Sin datos personales.
- **Archivos:** `corpus/casos/caso-00/esperado/matriz-esperada.yaml` (fuera del repositorio). En el repositorio, solo la fila de esta tabla y la verificación con cuentas, sin texto.
- **Verificación:** el archivo existe, se lee como YAML, cada requisito tiene id, documento, tramo, página, ancla, clase y `en_dictamen`; todo lo que la evaluación verificó tiene su requisito; tiene el visto bueno del responsable. La comprobación de las anclas contra la lectura se hace con `medir_matriz --verificar-esperada` antes de T-084.
- **No tocar:** el sistema: no se corre la propuesta sobre el caso-00 antes del visto bueno.
- **Entorno:** datos.

### T-077 · Medir una propuesta contra una lista esperada

- **Qué hacer:** `evaluation.py` y el comando `medir_matriz`: lectura y comprobación de la lista (huella, visto bueno, anclas; opción `--verificar-esperada`), propuesta con el canal `eval` por cada nivel pedido (versiones descartadas al terminar), emparejamiento por cita, causas de faltantes, sobrantes, clase y renglón, cita literal, cobertura, consecuencias sugeridas, tiempos por pasada, extrapolación por página, intervalo de Wilson de la 001, comparación entre niveles y carpeta de corrida con `parametros.json`, `resultados.jsonl`, `resumen.md` y `resumen-publico.md`.
- **Archivos:** `evaluon/tenders/evaluation.py`, `evaluon/tenders/management/commands/medir_matriz.py`, `tests/tenders/test_evaluation.py`, `tests/tenders/fixtures/` (listas esperadas sintéticas).
- **Verificación:** tests con un pliego y una lista sintéticos y el doble del motor: un requisito agrupado cuenta una sola ancla y deja la otra con causa "agrupado"; un tramo descartado deja sus anclas con esa causa; un ancla que no está bloquea; una lista sin visto bueno no se mide; `resumen-publico.md` no contiene ningún texto del pliego (se comprueba buscando cada ancla y cada cita).
- **No tocar:** `proposal/` (se llama, no se modifica); `evaluon/queries/evaluation.py` (se importa la función de Wilson).
- **Entorno:** cualquier equipo con Docker.

### T-078 · Completar los niveles alta y exigente

- **Qué hacer:** `proposal/completeness.py` con la pasada de completitud (faltantes, división de requisitos agrupados, tramos descartados con marcadores) y la segunda extracción con lotes desplazados y su unión; instrucciones `matriz-completitud-v1.md`; orden de pasadas de alta y exigente en `run.py`.
- **Archivos:** `evaluon/tenders/proposal/completeness.py`, `evaluon/tenders/proposal/run.py`, `evaluon/tenders/prompts/matriz-completitud-v1.md`, `tests/tenders/test_completeness.py`.
- **Verificación:** tests con el doble: en alta, un faltante devuelto se suma con su cita verificada y un requisito agrupado se divide; un tramo descartado con marcadores pasa por completitud y no queda pendiente; en exigente, la unión no duplica requisitos que se superponen y conserva requisitos de un tramo descartado en una sola extracción; cada nivel registra sus pasadas.
- **No tocar:** `extraction.py` salvo para reutilizar funciones (si hace falta cambiarla, aviso por `avisos/`); vistas.
- **Entorno:** cualquier equipo con Docker.

### T-079 · Revisar la matriz: confirmar, corregir, quitar y agregar

- **Qué hacer:** `services/review.py` (confirmar uno o varios, solo evaluador; corregir clase, renglones o cita con cita verificada; quitar y restituir; agregar desde un tramo; resolver un pendiente, solo evaluador; historial y hechos `requirement_change` y `segment_review`); acciones en la página de la matriz y página de historial.
- **Archivos:** `evaluon/tenders/services/review.py`, `evaluon/tenders/views/review.py`, `evaluon/tenders/urls.py`, `evaluon/templates/tenders/matrix.html`, `evaluon/templates/tenders/history.html`, `tests/tenders/test_review.py`.
- **Verificación:** tests: una corrección queda con usuario, momento, antes y después, y lo propuesto se consulta en el historial; una cita corregida que no está en el tramo se rechaza; un operador no puede confirmar ni resolver un pendiente y queda `rejected`; nada se puede cambiar en una versión validada.
- **No tocar:** consecuencias (T-081) y validación (T-082).
- **Entorno:** cualquier equipo con Docker.

### T-080 · Sugerir consecuencias con fundamento

- **Qué hacer:** `proposal/consequences.py`: fundamentos del pliego por marcadores (con el reranker si no entran), fundamentos de la norma con `retrieve` y `select_units` de la 001 a la fecha de autorización, pedidos de a 25 requisitos con tipos de la lista cerrada (decisión 8) y alias, validación, "no determinada" sin fundamento; instrucciones `matriz-consecuencias-v1.md` con las preguntas fijas; la pasada en `run.py` para todos los niveles.
- **Archivos:** `evaluon/tenders/proposal/consequences.py`, `evaluon/tenders/proposal/run.py`, `evaluon/tenders/prompts/matriz-consecuencias-v1.md`, `tests/tenders/test_consequences.py`.
- **Verificación:** tests con dobles: una cláusula sintética que sanciona con desestimación produce esa sugerencia con la cita de la cláusula; un alias inexistente invalida la opción; sin fundamentos, "no determinada"; sin régimen a la fecha, solo fundamentos del pliego; el pedido registra unidades de la norma, puntajes y versión de la normativa.
- **No tocar:** `evaluon/queries/` (se usa como está); vistas.
- **Entorno:** cualquier equipo con Docker.

### T-081 · Elegir la consecuencia en la pantalla

- **Qué hacer:** `services/consequences.py` (solo evaluador; elegir una opción sugerida u otro tipo de la lista como decisión de una persona; hecho `consequence_choice`); opciones con su fundamento literal (pliego o norma, con el texto de `norms_unit`) en la página de la matriz.
- **Archivos:** `evaluon/tenders/services/consequences.py`, `evaluon/tenders/views/consequences.py`, `evaluon/tenders/urls.py`, `evaluon/templates/tenders/matrix.html`, `tests/tenders/test_consequence_choice.py`.
- **Verificación:** tests: la página muestra cada opción con el texto literal de su fundamento; la elección queda con quién y cuándo; un operador no puede elegir; una consecuencia "no determinada" se muestra como tal.
- **No tocar:** `proposal/consequences.py`; validación (T-082).
- **Entorno:** cualquier equipo con Docker.

### T-082 · Validar la matriz y abrir versiones nuevas

- **Qué hacer:** `services/validation.py`: validar con las condiciones de la decisión 9 (confirma los requisitos todavía propuestos, cada uno con su historial), descartar un borrador, abrir una versión nueva sobre la última validada copiando requisitos, fuentes, consecuencias elegidas y pendientes resueltos; hechos `matrix_validation` y `matrix_version`; botones y lista de versiones.
- **Archivos:** `evaluon/tenders/services/validation.py`, `evaluon/tenders/views/validation.py`, `evaluon/tenders/urls.py`, `evaluon/templates/tenders/matrix.html`, `evaluon/templates/tenders/procedure.html`, `tests/tenders/test_validation.py`.
- **Verificación:** tests: con un pendiente sin resolver o una consecuencia sin elegir no se valida y se dice por qué; validada, cualquier cambio se rechaza en la función y en la base; la versión nueva copia todo y la anterior sigue igual; el nivel pasa a la versión nueva; solo un evaluador valida.
- **No tocar:** `proposal/`.
- **Entorno:** cualquier equipo con Docker.

### T-083 · Incorporar circulares y respuestas a consultas

- **Qué hacer:** `proposal/circulars.py`: orden por fecha, candidatos por cláusula o renglón nombrados y por el reranker, efectos `modifica`, `aclara` y `suprime`, requisitos nuevos, citas verificadas, disposición de cada tramo de circular; instrucciones `matriz-circulares-v1.md`; la pasada en `run.py`.
- **Archivos:** `evaluon/tenders/proposal/circulars.py`, `evaluon/tenders/proposal/run.py`, `evaluon/tenders/prompts/matriz-circulares-v1.md`, `tests/tenders/test_circulars.py`.
- **Verificación:** test del criterio de la spec con un pliego sintético: "16 GB de RAM" y una circular posterior "32 GB": el requisito exige 32 GB, conserva el texto original y cita la circular; una respuesta a una consulta que precisa un requisito queda como `aclara` con su cita; dos circulares sobre el mismo requisito se aplican por fecha; todo tramo de circular queda con disposición.
- **No tocar:** vistas (los textos de circulares ya se muestran desde T-074).
- **Entorno:** cualquier equipo con Docker.

### T-084 · Correr la medición del caso-00

- **Qué hacer:** fijar las versiones `v1` de las instrucciones; `medir_matriz --verificar-esperada`; primera corrida de los tres niveles, de a uno, sin otra carga en la GPU, que se informa como la medida provisoria independiente (decisión 7); consulta de normativa sola y durante una propuesta, para medir la contención (ADR-0018); informe con encontrados (y causas de cada faltante), sobrantes, cita literal, cobertura, clase y renglón, consecuencias, tiempos por nivel y extrapolación a 50 páginas, memoria de video, y la propuesta de qué niveles ofrecer según la regla de la spec.
- **Archivos:** corridas en `corpus/casos/caso-00/corridas/` (fuera del repositorio); `specs/003-pliego-matriz/verificacion/T-084.md` con el contenido de `resumen-publico.md`.
- **Verificación:** el informe tiene todas las medidas del plan con su intervalo y la marca de provisoria; ningún texto del pliego en el repositorio; el responsable decide los niveles que se ofrecen. Un faltante bloquea la aceptación y se informa con su causa.
- **No tocar:** instrucciones y parámetros durante la corrida. Un ajuste posterior pasa el caso-00 a `uso: ajuste`.
- **Entorno:** MSI con GPU.

### T-085 · Ofrecer solo los niveles que mejoran

- **Qué hacer:** dejar en `MATRIX_LEVELS_OFFERED` los niveles que decidió el responsable con el informe de T-084; si alta no se ofrece, el nivel por omisión pasa al que el responsable indique; el formulario muestra solo los ofrecidos y la función de negocio rechaza los demás.
- **Archivos:** `evaluon/settings.py`, `evaluon/tenders/services/matrix.py`, `evaluon/templates/tenders/procedure.html`, `tests/tenders/test_levels_offered.py`.
- **Verificación:** tests: un nivel no ofrecido no aparece en el formulario y su pedido se rechaza; el nivel por omisión es uno de los ofrecidos.
- **No tocar:** las pasadas de cada nivel.
- **Entorno:** cualquier equipo con Docker.

## Cobertura de requisitos

| Requisito | Tareas |
|---|---|
| REQ-022 | T-067, T-069, T-075 |
| REQ-023 | T-067, T-072, T-075 |
| REQ-024 | T-067, T-070, T-071, T-073, T-074, T-075, T-076, T-077, T-078, T-084 |
| REQ-025 | T-067, T-070, T-073, T-074, T-075, T-076, T-077, T-084 |
| REQ-026 | T-067, T-068, T-079, T-082 |
| REQ-027 | T-067, T-068, T-082 |
| REQ-028 | T-067, T-070, T-072, T-073, T-074, T-075, T-077, T-079, T-082 |
| REQ-029 | T-067, T-068, T-080, T-081, T-084 |
| REQ-030 | T-067, T-071, T-073, T-074, T-077, T-078, T-084, T-085 |
| REQ-031 | T-067, T-072, T-074, T-083 |

## Paralelismo

Esquema y configuración compartida, de a una: T-067 (tablas, `audit_event`, `settings.py`) → T-068 (`accounts`) y T-071 (`docker-compose.yml`, cliente de generación, `tests/conftest.py`). T-085 vuelve a tocar `settings.py`, al final.

| Momento | Pueden ir a la vez | Por qué no chocan |
|---|---|---|
| Desde ya | T-067 y T-076 | T-076 es de datos, fuera del repositorio |
| Terminada T-067 | T-068, T-070 y T-071 | `accounts`; `segmenting.py` y `tables.py`; `jobs.py`, `docker-compose.yml` y el cliente. Los usuarios de prueba de T-068 van en `tests/tenders/conftest.py` y el doble de T-071 en `tests/conftest.py` |
| Terminada T-073 | T-074, T-077 y T-078 | Vistas y plantillas; `evaluation.py` y su comando; `completeness.py` y `run.py` |
| Terminadas T-074 y T-078 | T-079 y T-080 | Revisión en vistas; consecuencias en `proposal/` |
| Terminada T-080 | T-083, en paralelo con T-081 y T-082 | `circulars.py` y `run.py` frente a vistas y servicios de elección y validación |
| Terminada T-074 | T-075, en paralelo con todo lo que no ocupe la GPU | T-075 no escribe código |

Cadenas que se respetan por compartir archivos:

- **Vistas, `urls.py` y plantillas:** T-069 → T-072 → T-074 → T-079 → T-081 → T-082 → T-085.
- **`proposal/run.py`:** T-073 → T-078 → T-080 → T-083.
- **`jobs.py`:** T-071 → T-072 → T-073.
- **`base.html`:** T-069 → T-074.

Recursos que no se comparten: la GPU (T-071 en su medición, T-075 y T-084, de a una) y la base de pruebas.

Camino crítico hasta ver una matriz: T-067 → T-068 → T-069 → T-072 → T-073 → T-074 → T-075 (con T-076 lista antes). Hasta la medición: … → T-073 → T-078 → T-080 → T-084.
