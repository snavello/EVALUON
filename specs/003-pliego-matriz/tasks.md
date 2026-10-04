# Tareas 003 · Procedimiento, pliego final y matriz de cumplimiento

Plan: `specs/003-pliego-matriz/plan.md`

Despliegue: pendiente

> El tablero (`docs/tablero.md`) se genera de este archivo. Al aprobarse el despliegue, la línea de arriba pasa a `Despliegue: aprobado AAAA-MM-DD`.

Estados: pendiente · en curso · en verificación · terminada · bloqueada

Dos tareas que no dependen entre sí y no comparten archivos se pueden hacer en paralelo.

Formato liviano (ADR-0014, punto 6): este archivo tiene solo la tabla y lo que pide cada tarea. Los avisos para una tarea van en `specs/003-pliego-matriz/avisos/T-NNN.md`, que se crea cuando hace falta, y el encargo lo nombra. La verificación de cada tarea queda en `specs/003-pliego-matriz/verificacion/T-NNN.md` (ADR-0014, punto 3).

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-067 | Crear las tablas, los tipos de hecho y los parámetros de la 003 | REQ-022, REQ-023, REQ-024, REQ-025, REQ-026, REQ-027, REQ-028, REQ-029, REQ-030, REQ-031, REQ-032 | — | terminada |
| T-068 | Sumar el rol de la Comisión a los usuarios | REQ-026, REQ-027, REQ-029 | T-067 | terminada |
| T-069 | Registrar un procedimiento y mostrar su régimen | REQ-022 | T-068 | terminada |
| T-070 | Partir un pliego en tramos con renglones, clase por sección y control de cobertura | REQ-024, REQ-025, REQ-028 | T-067 | terminada |
| T-071 | Ejecutar pedidos en segundo plano con su propio motor | REQ-024, REQ-030 | T-067 | terminada |
| T-072 | Cargar los documentos del pliego y leerlos en segundo plano | REQ-023, REQ-028, REQ-031 | T-069, T-070, T-071 | terminada |
| T-073 | Proponer la matriz en nivel media, con filas técnicas por renglón | REQ-024, REQ-025, REQ-028, REQ-030 | T-072 | terminada |
| T-074 | Mostrar la matriz propuesta con la leyenda de borrador, la cobertura y el aviso de fin | REQ-024, REQ-025, REQ-028, REQ-030, REQ-031, REQ-032 | T-073 | terminada |
| T-075 | Probar el hilo mínimo con el caso-00 y los servicios reales | REQ-022, REQ-023, REQ-024, REQ-025, REQ-028 | T-074, T-076 | terminada |
| T-076 | Preparar la lista esperada del caso-00 | REQ-024, REQ-025 | — | terminada |
| T-077 | Medir una propuesta contra una lista esperada | REQ-024, REQ-025, REQ-028, REQ-030 | T-073 | terminada |
| T-078 | Completar los niveles alta y exigente | REQ-024, REQ-030 | T-073 | terminada |
| T-079 | Revisar la matriz: confirmar, corregir, quitar y agregar | REQ-026, REQ-028 | T-074 | terminada |
| T-080 | Sugerir consecuencias con fundamento | REQ-029 | T-078 | terminada |
| T-081 | Elegir la consecuencia en la pantalla, con su motivo | REQ-029 | T-079, T-080 | terminada |
| T-082 | Validar la matriz y abrir versiones nuevas | REQ-026, REQ-027, REQ-028, REQ-032 | T-081 | terminada |
| T-083 | Incorporar circulares y respuestas a consultas | REQ-031 | T-080 | terminada |
| T-084 | Correr la medición del caso-00 | REQ-024, REQ-025, REQ-029, REQ-030 | T-075, T-076, T-077, T-080 | terminada |
| T-085 | Ofrecer solo los niveles que mejoran | REQ-030 | T-084 | pendiente |
| T-086 | Imprimir y exportar la matriz a PDF con la leyenda de borrador | REQ-032 | T-082 | pendiente |
| T-087 | Comparar en la misma zona horaria la fecha de lectura del informe | REQ-004 | — | terminada |
| T-088 | Cambiar el rol de la Comisión de un usuario existente, con registro | REQ-026 | — | terminada |
| T-089 | Contar bien las páginas en la extrapolación de tiempos | REQ-030 | T-084 | pendiente |
| T-090 | Investigar y corregir los reinicios de los servidores de generación | REQ-024, REQ-030 | T-084 | pendiente |
| T-091 | Comparar niveles medidos en corridas separadas | REQ-030 | T-084 | terminada |

## Para todas las tareas

- **Entorno.** "Cualquier equipo con Docker": tests con los dobles de los clientes de IA y Postgres en contenedor. "MSI con GPU": servicios de IA reales. "Datos": trabajo del Coordinador con el responsable, sin código.
- **Cita literal.** Una sola definición, la del plan 001: el texto mostrado es igual a `canonical_text[char_start:char_end]` de su lectura, en cada cita.
- **Requisito y clase.** Los criterios son los de la spec ("Qué es un requisito") y la sección "Qué es un requisito y su clase" del plan: formales y económicos, una fila por condición; técnicos, una fila por renglón.
- **Caso de referencia.** `corpus/casos/caso-00/` no se sube al repositorio. Ningún archivo del repositorio (tests, fixtures, informes, avisos, verificaciones) copia texto de sus documentos con datos personales. Los tests usan pliegos sintéticos. Los informes de las tareas que corren el caso-00 llevan identificadores, claves de tramo, cuentas y tiempos, no texto del pliego.
- **Reutilización.** La lectura (`evaluon/norms/reading/`), el texto canónico (`evaluon/norms/splitting/canonical.py`), `applicable_regimes` y la recuperación de la 001 se usan como están. Si una tarea necesita cambiarlos, se detiene y avisa.
- **Suite.** La regla del ADR-0012.

## Detalle

### T-067 · Crear las tablas, los tipos de hecho y los parámetros de la 003

- **Qué hacer:** crear la aplicación `evaluon/tenders/` con todos los modelos de "Modelo de datos" del plan (procedimiento, documento y su archivo, lectura con sus renglones, tramo con su clase de sección, pedido, propuesta, pedido al modelo, disposición con su origen, versión de matriz, requisito, cita de requisito, fuente de circular por cita, consecuencia con el motivo de la elección y los siete tipos, pendiente, cambio) con sus restricciones (un formal o económico con exactamente una cita; un técnico con un renglón como máximo); los triggers de solo inserción (`tenders_run_step`, `tenders_requirement_change`) y de inmutabilidad de una versión validada (requisitos, citas, fuentes, consecuencias, pendientes), con su reversa; sumar los once tipos de hecho a `audit_event`, incluido `matrix_export`, con su migración; registrar la aplicación y sumar todos los parámetros de "Parámetros" a `settings.py`, incluido `GENERATION_BATCH_URL` (por omisión, `http://generation_batch:8080`).
- **Archivos:** `evaluon/tenders/__init__.py`, `apps.py`, `models.py`, `migrations/`; `evaluon/audit/models.py`, `evaluon/audit/migrations/` (una migración nueva); `evaluon/settings.py`; `tests/tenders/test_models.py`.
- **Verificación:** `migrate` sobre una base vacía y `migrate --check` sin cambios pendientes; tests: restricciones de valores, huella única por procedimiento, número único de procedimiento, un solo borrador por procedimiento, un formal con dos citas rechazado, UPDATE sobre una cita de una versión validada rechazado por la base, UPDATE sobre `tenders_run_step` rechazado; los tipos de hecho nuevos se registran con `audit.record`.
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

### T-070 · Partir un pliego en tramos con renglones, clase por sección y control de cobertura

- **Qué hacer:** `segmenting.py` con las reglas de "Tramos" del plan sobre el texto canónico (`build_canonical_text`): secciones y su clase cuando el título la nombra ("especificaciones técnicas", "requisitos económicos", "requisitos formales"), cláusulas numeradas con control de secuencia, títulos, renglones (también "RENGLONES NROS. j A k") y la lista de renglones de la lectura, viñetas e incisos, anexos y párrafos, tablas (a partir de las zonas que recibe), páginas sin texto legible, tramos largos partidos, claves y rutas, y el control de cobertura; `tables.py` con las zonas de tabla de cada página de un PDF (pdfplumber). Un generador de pliegos sintéticos en PDF para las pruebas, con la forma del caso-00 (secciones con y sin clase en el título, numeración de cuatro niveles con y sin espacio, renglones, viñetas, anexo, tabla, índice, encabezado repetido) y sin datos reales.
- **Archivos:** `evaluon/tenders/segmenting.py`, `evaluon/tenders/tables.py`, `tests/tenders/pdfs.py`, `tests/tenders/test_segmenting.py`, `tests/tenders/test_tables.py`.
- **Verificación:** tests con una tabla de casos escrita a mano: claves esperadas (`sec-i/7.5.2`, `sec-iii/1.1`, `sec-ii/1.2/v-1`, `sec-iv/anexo-i/p-1`, `pagina-7`); "3.972 kcal" y "1.300 mg" al comienzo de una línea no cortan; "10.2.1.Una vez" corta; los renglones pasan a los tramos que cuelgan y a la lista de la lectura, y "RENGLONES NROS. 2 A 4" da los renglones 2, 3 y 4; los tramos de una sección "Especificaciones técnicas" tienen clase técnica y los de "Condiciones particulares", ninguna; el índice no produce tramos; cada texto es igual a su recorte; la cobertura suma el total.
- **No tocar:** `evaluon/norms/` (se importa, no se modifica).
- **Entorno:** cualquier equipo con Docker.

### T-071 · Ejecutar pedidos en segundo plano con su propio motor

- **Qué hacer:** `jobs.py` (encolar, tomar con `FOR UPDATE SKIP LOCKED`, terminar, fallar, pasar a `failed` los interrumpidos al arrancar, tabla de manejadores por tipo de pedido, aviso visto); comando `procesar_pedidos`; servicios `worker` y `generation_batch` en `docker-compose.yml` (ADR-0018), y montaje con escritura de `corpus/casos` en `app` para las corridas de medición; máximo de salida y espera por pedido en el cliente de generación, con su doble. Medir la memoria de video con los cuatro modelos cargados.
- **Archivos:** `evaluon/tenders/jobs.py`, `evaluon/tenders/management/__init__.py`, `management/commands/__init__.py`, `management/commands/procesar_pedidos.py`; `docker-compose.yml`; `.env.example`; `evaluon/ai/generation.py`; `tests/conftest.py`; `tests/tenders/test_jobs.py`; `tests/tenders/test_generation_batch.py` (máximo de salida y espera del cliente); informe en `specs/003-pliego-matriz/verificacion/T-071.md`.
- **Verificación:** tests: dos tomas simultáneas no toman el mismo pedido; un pedido que falla queda `failed` con su motivo; un pedido `running` al arrancar pasa a `failed` "interrumpido"; el cliente manda el máximo de salida pedido. En la MSI: `docker compose up -d` con los ocho servicios sanos y `nvidia-smi` con los cuatro modelos cargados, anotado en la verificación. Si el total supera 20 GB, se informa antes de seguir.
- **No tocar:** la configuración del servicio `generation` y de los demás servicios de la 001; los tipos de pedido concretos (T-072 y T-073); el `Dockerfile` (T-086).
- **Entorno:** cualquier equipo con Docker para los tests; MSI con GPU para la medición.

### T-072 · Cargar los documentos del pliego y leerlos en segundo plano

- **Qué hacer:** `services/documents.py`: cargar (operador; tipo, título, fecha obligatoria en circulares y respuestas; mismo archivo rechazado; hecho `tender_load`), encolar la lectura, el manejador `read_document` (lectura de la 001, zonas de tabla, tramos, renglones, informe, hecho `tender_read`) y la entrega del original con sesión; sección de documentos y formulario de carga en la página del procedimiento.
- **Archivos:** `evaluon/tenders/services/documents.py`, `evaluon/tenders/jobs.py` (registra el manejador), `evaluon/tenders/views/documents.py`, `evaluon/tenders/urls.py`, `evaluon/templates/tenders/procedure.html`, `tests/tenders/test_documents.py`.
- **Verificación:** tests: un pliego sintético en tres documentos; la huella de lo que entrega la vista es igual a la de cada archivo; el mismo archivo dos veces se rechaza y queda registrado; una circular sin fecha se rechaza; un PDF con una página de ruido deja esa página como tramo pendiente (REQ-028); el informe cuenta tramos por tipo y lista los renglones.
- **No tocar:** `evaluon/norms/`; `segmenting.py` (si hace falta un cambio, aviso a T-070 por `avisos/`).
- **Entorno:** cualquier equipo con Docker.

### T-073 · Proponer la matriz en nivel media, con filas técnicas por renglón

- **Qué hacer:** `services/matrix.py` (pedir una propuesta con nivel, por omisión alta; rechazos del plan; hecho `matrix_request`); `proposal/run.py` con las pasadas de media; disposición por regla (títulos, páginas, no ubicados y tramos de secciones técnicas, que no pasan por el modelo); `proposal/extraction.py` (lotes de los tramos restantes, esquema con una propiedad obligatoria por tramo con `requisitos` formales o económicos, `tecnico` y `descarte`, validación, reintento único, partición del lote si la salida se corta); `proposal/quotes.py`; `proposal/technical.py` (una fila técnica por renglón con citas `propia` y `general`, renglón sin especificaciones como pendiente, tramo de un renglón descartado por el modelo que entra igual en su fila); instrucciones `prompts/matriz-extraccion-v1.md` con los criterios de requisito y de clase de la spec y ejemplos sintéticos (incluido el de la forma de pago); el manejador `propose_matrix`: crea la versión borrador con requisitos, citas, disposiciones y pendientes, guarda cada pedido en `tenders_run_step` y deja `matrix_proposal`. Mientras alta y exigente no existan, piden lo mismo que media y quedan registrados con su nombre; T-078 completa sus pasadas.
- **Archivos:** `evaluon/tenders/services/matrix.py`, `evaluon/tenders/proposal/__init__.py`, `proposal/run.py`, `proposal/extraction.py`, `proposal/quotes.py`, `proposal/technical.py`, `evaluon/tenders/prompts/matriz-extraccion-v1.md`, `evaluon/tenders/jobs.py` (registra el manejador), `tests/tenders/test_extraction.py`, `tests/tenders/test_quotes.py`, `tests/tenders/test_technical.py`, `tests/tenders/test_matrix_request.py`.
- **Verificación:** tests con el doble del motor: todo tramo queda con requisitos, fila técnica, descarte o pendiente; los tramos de una sección técnica no se mandan al modelo y quedan con origen "regla"; un pliego sintético de tres renglones da tres filas técnicas, cada una con sus tramos propios y los generales; un tramo marcado `todos` entra en las tres; un renglón sin especificaciones deja su fila y un pendiente; un tramo sin disposición se reintenta y queda pendiente; una cita que no está en el tramo se reintenta y queda como cita amplia; dos citas iguales se unen; una salida cortada parte el lote; un tramo descartado con marcadores queda pendiente; sin elegir, el nivel es alta; el pedido registra modelos, parámetros, versiones de instrucciones, régimen y versión de la normativa.
- **No tocar:** las vistas y plantillas (T-074); consecuencias y circulares (T-080 y T-083).
- **Entorno:** cualquier equipo con Docker.

### T-074 · Mostrar la matriz propuesta con la leyenda de borrador, la cobertura y el aviso de fin

- **Qué hacer:** formulario "Proponer matriz" con el nivel y pedidos en curso en la página del procedimiento; página de la matriz (franja "BORRADOR INCOMPLETO" fija arriba en toda versión no validada, encabezado, resumen por clase, pendientes primero, formales y económicos agrupados con clase, texto literal, documento, página, cláusula, enlace al original en la página, textos de circulares y respuestas cuando existan, marca de cita amplia; después, las filas técnicas por renglón con la lista de tramos citados y su texto desplegable); página de cobertura con disposición, origen y motivo; aviso de pedidos terminados en todas las páginas.
- **Archivos:** `evaluon/tenders/views/matrix.py`, `evaluon/tenders/urls.py`, `evaluon/templates/tenders/procedure.html`, `evaluon/templates/tenders/matrix.html`, `evaluon/templates/tenders/coverage.html`, `evaluon/templates/base.html`, `evaluon/static/tenders/matrix.css`, `tests/tenders/test_matrix_screen.py`.
- **Verificación:** tests con el cliente de pruebas: un borrador muestra "BORRADOR INCOMPLETO"; la página muestra cada requisito con su texto igual al recorte, su página y su cláusula; una fila técnica muestra su renglón y todos sus tramos; los pendientes aparecen primero con su motivo; la cobertura lista todos los tramos; un requisito con fuente de circular muestra el texto vigente y el original con sus citas; el aviso aparece una vez y desaparece al verlo; ninguna página referencia direcciones externas.
- **No tocar:** las acciones de revisión (T-079) y de consecuencias (T-081).
- **Entorno:** cualquier equipo con Docker.

### T-075 · Probar el hilo mínimo con el caso-00 y los servicios reales

- **Qué hacer:** con la lista esperada ya aprobada (T-076), registrar el procedimiento del caso-00 por pantalla, cargar su pliego, pedir la matriz en nivel media y verla en la pantalla, con los servicios reales. Anotar: tramos por tipo y por origen, renglones reconocidos, requisitos por clase, filas técnicas con su cantidad de citas, descartes por motivo, pendientes, citas reintentadas y amplias, tiempo por pasada y total, memoria de video. Repetir con la red de Docker sin salida a internet. No se compara con la lista esperada ni se cambian instrucciones a partir de este resultado (uso del caso-00 decidido por el responsable).
- **Archivos:** ninguno de código; informe en `specs/003-pliego-matriz/verificacion/T-075.md`, sin texto del pliego.
- **Verificación:** el informe muestra 100 % de tramos con disposición, 100 % de citas literales, seis filas técnicas, la matriz visible en la pantalla con la leyenda de borrador y el tiempo medido; sin red, el resultado es el mismo.
- **No tocar:** instrucciones y parámetros; la lista esperada.
- **Entorno:** MSI con GPU.

### T-076 · Preparar la lista esperada del caso-00

- **Qué hacer:** el Coordinador escribe `matriz-esperada.yaml` con el formato del plan, leyendo el PDF cláusula por cláusula, sin correr la propuesta de matriz, con los criterios de la spec ("Qué es un requisito"): formales y económicos, una entrada por condición con su ancla; técnicos, una entrada por renglón con sus tramos propios, y los tramos técnicos generales en `tecnico_general`. Se esperan unas 30 a 40 entradas. La contrasta con lo que verificó la evaluación (`en_dictamen`); prepara para el responsable la tabla de ejemplos (unos 12, de clases y secciones distintas, incluida la forma de pago), las cuentas por clase y por sección, los renglones con sus tramos y los casos dudosos. El responsable da el visto bueno, que se anota en el archivo. Sin datos personales.
- **Archivos:** `corpus/casos/caso-00/esperado/matriz-esperada.yaml` (fuera del repositorio). En el repositorio, solo la fila de esta tabla y la verificación con cuentas, sin texto.
- **Verificación:** el archivo existe, se lee como YAML; cada formal o económico tiene id, documento, tramo, página, ancla, clase y `en_dictamen`; cada técnico, id, renglón, tramos y `en_dictamen`; hay una entrada técnica por cada renglón del pliego; todo lo que la evaluación verificó tiene su requisito; tiene el visto bueno del responsable. La comprobación de anclas y tramos contra la lectura se hace con `medir_matriz --verificar-esperada` antes de T-084.
- **No tocar:** el sistema: no se corre la propuesta sobre el caso-00 antes del visto bueno.
- **Entorno:** datos.

### T-077 · Medir una propuesta contra una lista esperada

- **Qué hacer:** `evaluation.py` y el comando `medir_matriz`: lectura y comprobación de la lista (huella, visto bueno, anclas y tramos; opción `--verificar-esperada`), propuesta con el canal `eval` por cada nivel pedido (versiones descartadas al terminar), emparejamiento por cita uno a uno para formales y económicos y por renglón para técnicos, encontrado con clase equivocada cuando el ancla está dentro de un tramo de una fila técnica, causas de faltantes (incluida "renglón sin fila"), sobrantes, clase (informada, no bloquea), tramos técnicos citados por renglón (informados, no bloquean), cita literal, cobertura por origen, consecuencias sugeridas, tiempos por pasada, extrapolación por página, intervalo de Wilson de la 001, comparación entre niveles y carpeta de corrida con `parametros.json`, `resultados.jsonl`, `resumen.md` y `resumen-publico.md`.
- **Archivos:** `evaluon/tenders/evaluation.py`, `evaluon/tenders/management/commands/medir_matriz.py`, `tests/tenders/test_evaluation.py`, `tests/tenders/fixtures/` (listas esperadas sintéticas).
- **Verificación:** tests con un pliego y una lista sintéticos y el doble del motor: una fila formal que junta dos condiciones cuenta una sola ancla y deja la otra con causa "agrupado"; un tramo descartado deja sus anclas con esa causa; una fila técnica del renglón 2 empareja con el esperado del renglón 2 aunque le falte un tramo, y el tramo faltante se informa; un renglón sin fila es faltante; una garantía propuesta como formal cuenta como encontrada con clase equivocada; un ancla que no está bloquea; una lista sin visto bueno no se mide; `resumen-publico.md` no contiene ningún texto del pliego (se comprueba buscando cada ancla y cada cita).
- **No tocar:** `proposal/` (se llama, no se modifica); `evaluon/queries/evaluation.py` (se importa la función de Wilson).
- **Entorno:** cualquier equipo con Docker.

### T-078 · Completar los niveles alta y exigente

- **Qué hacer:** `proposal/completeness.py` con la pasada de completitud solo para formales y económicos (faltantes, división de requisitos agrupados, tramos descartados con marcadores) y la segunda extracción con lotes desplazados sobre los tramos que pasan por el modelo, y su unión (fragmentos por superposición de cita; marca técnica si aparece en cualquiera de las dos); instrucciones `matriz-completitud-v1.md`; orden de pasadas de alta y exigente en `run.py`, con las filas técnicas después de la unión.
- **Archivos:** `evaluon/tenders/proposal/completeness.py`, `evaluon/tenders/proposal/run.py`, `evaluon/tenders/prompts/matriz-completitud-v1.md`, `tests/tenders/test_completeness.py`.
- **Verificación:** tests con el doble: en alta, un faltante devuelto se suma con su cita verificada y un requisito agrupado se divide; un tramo descartado con marcadores pasa por completitud y no queda pendiente; los tramos de secciones técnicas no se mandan a la completitud; en exigente, la unión no duplica requisitos que se superponen y conserva requisitos de un tramo descartado en una sola extracción; las filas técnicas son las mismas en los tres niveles para el mismo pliego; cada nivel registra sus pasadas.
- **No tocar:** `extraction.py` y `technical.py` salvo para reutilizar funciones (si hace falta cambiarlas, aviso por `avisos/`); vistas.
- **Entorno:** cualquier equipo con Docker.

### T-079 · Revisar la matriz: confirmar, corregir, quitar y agregar

- **Qué hacer:** `services/review.py` (confirmar uno o varios, solo evaluador; corregir en un formal o económico la clase, los renglones o la cita con cita verificada, y en un técnico sumar o quitar tramos; pasar un formal o económico a técnico lo une a la fila de su renglón; quitar y restituir; agregar un formal o económico desde un tramo, o una fila técnica para un renglón que no la tenga; resolver un pendiente, solo evaluador; historial y hechos `requirement_change` y `segment_review`); acciones en la página de la matriz y página de historial.
- **Archivos:** `evaluon/tenders/services/review.py`, `evaluon/tenders/views/review.py`, `evaluon/tenders/urls.py`, `evaluon/templates/tenders/matrix.html`, `evaluon/templates/tenders/history.html`, `tests/tenders/test_review.py`.
- **Verificación:** tests: una corrección queda con usuario, momento, antes y después, y lo propuesto se consulta en el historial; una cita corregida que no está en el tramo se rechaza; sumar un tramo a una fila técnica queda registrado; una segunda fila técnica para el mismo renglón se rechaza; un operador no puede confirmar ni resolver un pendiente y queda `rejected`; nada se puede cambiar en una versión validada.
- **No tocar:** consecuencias (T-081) y validación (T-082).
- **Entorno:** cualquier equipo con Docker.

### T-080 · Sugerir consecuencias con fundamento

- **Qué hacer:** `proposal/consequences.py`: fundamentos del pliego por marcadores (con el reranker si no entran), fundamentos de la norma con `retrieve` y `select_units` de la 001 a la fecha de autorización, pedidos de a 25 requisitos (los técnicos como "Renglón k, especificaciones técnicas"), con los tipos que el sistema puede sugerir (`desestimacion`, `intimacion_subsanar`, `consultar_oferente`, `otra_pliego`) y alias; validación (`consultar_oferente` y `otra_pliego` con al menos un fundamento del pliego); "no determinada" sin fundamento; instrucciones `matriz-consecuencias-v1.md` con las preguntas fijas; la pasada en `run.py` para todos los niveles.
- **Archivos:** `evaluon/tenders/proposal/consequences.py`, `evaluon/tenders/proposal/run.py`, `evaluon/tenders/prompts/matriz-consecuencias-v1.md`, `tests/tenders/test_consequences.py`.
- **Verificación:** tests con dobles: una cláusula sintética que sanciona con desestimación produce esa sugerencia con la cita de la cláusula; una cláusula que permite pedir aclaraciones al oferente produce `consultar_oferente` con su cita; una salida del modelo con `aprobacion_condicionada` o `aprobar_igual` se descarta; un alias inexistente invalida la opción; sin fundamentos, "no determinada"; sin régimen a la fecha, solo fundamentos del pliego; el pedido registra unidades de la norma, puntajes y versión de la normativa.
- **No tocar:** `evaluon/queries/` (se usa como está); vistas.
- **Entorno:** cualquier equipo con Docker.

### T-081 · Elegir la consecuencia en la pantalla, con su motivo

- **Qué hacer:** `services/consequences.py` (solo evaluador; elegir una opción sugerida u otro tipo de la lista salvo "no determinada", con motivo obligatorio; en `aprobacion_condicionada`, la condición; en `consultar_oferente` u `otra_pliego` sin sugerencia, el tramo del pliego con cita verificada; hecho `consequence_choice`); opciones con su fundamento literal (pliego o norma, con el texto de `norms_unit`) y formulario de elección en la página de la matriz.
- **Archivos:** `evaluon/tenders/services/consequences.py`, `evaluon/tenders/views/consequences.py`, `evaluon/tenders/urls.py`, `evaluon/templates/tenders/matrix.html`, `tests/tenders/test_consequence_choice.py`.
- **Verificación:** tests: la página muestra cada opción con el texto literal de su fundamento; la elección queda con quién, cuándo y motivo; sin motivo se rechaza; una aprobación condicionada sin condición se rechaza; "no determinada" no se puede elegir y se muestra como tal; `otra_pliego` elegida por una persona sin tramo se rechaza; un operador no puede elegir.
- **No tocar:** `proposal/consequences.py`; validación (T-082).
- **Entorno:** cualquier equipo con Docker.

### T-082 · Validar la matriz y abrir versiones nuevas

- **Qué hacer:** `services/validation.py`: validar con las condiciones del plan (ningún pendiente sin resolver, cada requisito no quitado con su consecuencia elegida; confirma los requisitos todavía propuestos, cada uno con su historial), descartar un borrador, abrir una versión nueva sobre la última validada copiando requisitos, citas, fuentes, consecuencias elegidas y pendientes resueltos; hechos `matrix_validation` y `matrix_version`; botones y lista de versiones; en la página de una versión validada, sin la franja de borrador, su número, la fecha de validación y el evaluador.
- **Archivos:** `evaluon/tenders/services/validation.py`, `evaluon/tenders/views/validation.py`, `evaluon/tenders/urls.py`, `evaluon/templates/tenders/matrix.html`, `evaluon/templates/tenders/procedure.html`, `tests/tenders/test_validation.py`.
- **Verificación:** tests: con un pendiente sin resolver o una consecuencia sin elegir no se valida y se dice por qué; validada, cualquier cambio se rechaza en la función y en la base; la página de la validada no muestra "BORRADOR INCOMPLETO" y muestra versión, fecha y evaluador; la versión nueva copia todo, incluidas las citas técnicas, y la anterior sigue igual; el nivel pasa a la versión nueva; solo un evaluador valida.
- **No tocar:** `proposal/`.
- **Entorno:** cualquier equipo con Docker.

### T-083 · Incorporar circulares y respuestas a consultas

- **Qué hacer:** `proposal/circulars.py`: orden por fecha, citas candidatas por cláusula o renglón nombrados y por el reranker (en un técnico, cada tramo citado por separado), efectos `modifica`, `aclara` y `suprime` sobre una cita, requisitos nuevos, citas verificadas, disposición de cada tramo de circular; instrucciones `matriz-circulares-v1.md`; la pasada en `run.py`, después de las filas técnicas.
- **Archivos:** `evaluon/tenders/proposal/circulars.py`, `evaluon/tenders/proposal/run.py`, `evaluon/tenders/prompts/matriz-circulares-v1.md`, `tests/tenders/test_circulars.py`.
- **Verificación:** test del criterio de la spec con un pliego sintético: "16 GB de RAM" en las especificaciones de un renglón y una circular posterior "32 GB": la fila del renglón exige 32 GB en esa cita, conserva el texto original y cita la circular; una respuesta a una consulta que precisa un requisito queda como `aclara` con su cita; dos circulares sobre la misma cita se aplican por fecha; todo tramo de circular queda con disposición.
- **No tocar:** vistas (los textos de circulares ya se muestran desde T-074).
- **Entorno:** cualquier equipo con Docker.

### T-084 · Correr la medición del caso-00

- **Qué hacer:** fijar las versiones `v1` de las instrucciones; `medir_matriz --verificar-esperada`; primera corrida de los tres niveles, de a uno, sin otra carga en la GPU, que se informa como la medida provisoria independiente; consulta de normativa sola y durante una propuesta, para medir la contención (ADR-0018); informe con encontrados (y causas de cada faltante), sobrantes, cita literal, cobertura, clase, tramos técnicos citados por renglón, consecuencias, tiempos por nivel y extrapolación a 50 páginas, memoria de video, y la propuesta de qué niveles ofrecer según la regla de la spec, con la advertencia de que con unas 30 filas la diferencia entre niveles es de pocas filas.
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

### T-086 · Imprimir y exportar la matriz a PDF con la leyenda de borrador

- **Qué hacer:** con el ADR-0020 aceptado, sumar `weasyprint` con versión fija a `pyproject.toml` y sus bibliotecas del sistema y un paquete de fuentes, fijados por versión, al `Dockerfile`; plantilla `matrix_print.html` y hoja `print.css` (cajas de margen de `@page` con "BORRADOR INCOMPLETO" en toda versión no validada, o versión, fecha de validación y evaluador en la validada, y "Página N de M"; elemento fijo con la leyenda para la impresión del navegador); `export.py` (HTML a PDF con un `URLFetcher` que solo entrega `print.css` desde el disco y rechaza el resto; hecho `matrix_export` con versión, estado, leyenda, páginas y huella); vista de impresión con su botón "Imprimir" y descarga del PDF; botones "Vista de impresión" y "Exportar PDF" en la página de la matriz.
- **Archivos:** `pyproject.toml`, `Dockerfile`, `evaluon/tenders/export.py`, `evaluon/tenders/views/export.py`, `evaluon/tenders/urls.py`, `evaluon/templates/tenders/matrix_print.html`, `evaluon/templates/tenders/matrix.html`, `evaluon/static/tenders/print.css`, `tests/tenders/test_export.py`; informe en `specs/003-pliego-matriz/verificacion/T-086.md`.
- **Verificación:** tests con una matriz sintética de varias páginas, leyendo el PDF con pdfplumber: cada página de un borrador tiene "BORRADOR INCOMPLETO"; ninguna página de la versión validada la tiene, y todas muestran versión, fecha y evaluador; una versión descartada lleva la leyenda; la vista de impresión de un borrador tiene la leyenda; una plantilla con una dirección externa hace fallar la generación en lugar de buscarla; la exportación queda registrada con la huella del archivo entregado. En la imagen: `docker compose build app` y la suite completa en verde; el informe anota las versiones instaladas, el aumento de tamaño de la imagen, el tiempo de generación de una matriz de 40 filas y la comprobación a mano de que la impresión del navegador repite la leyenda en cada hoja.
- **No tocar:** `docker-compose.yml`; `proposal/`; los servicios de revisión, consecuencias y validación.
- **Entorno:** cualquier equipo con Docker.

### T-089 · Contar bien las páginas en la extrapolación de tiempos

- **Qué hacer:** defecto F1 de T-084: `timing_summary` en `evaluon/tenders/evaluation.py` usa `len(r.pages)` (claves del diccionario, da 4) en lugar de la cantidad real de páginas (`len(r.pages["pages"])`, 20 en el caso-00), y la extrapolación a 50 páginas sale mal en `resumen-publico.md`. Corregir y sumar un test con una lectura sintética de N páginas.
- **Archivos:** `evaluon/tenders/evaluation.py`, `tests/tenders/test_evaluation.py`.
- **Verificación:** test con lectura de 20 páginas: la extrapolación a 50 es tiempo × 2,5; suite en verde.
- **No tocar:** la propuesta.
- **Entorno:** cualquier equipo con Docker.

### T-090 · Investigar y corregir los reinicios de los servidores de generación

- **Qué hacer:** defecto F2 de T-084: `generation` y `generation_batch` (llama-server) terminaron solos con código 0 durante la medición (02:14 y 02:21 del 2026-10-04) y Docker los reinició; cada reinicio deja unos 80 s de HTTP 503 y hace fallar consultas. No hay error en los registros ni falta de memoria de video. Investigar la causa (parámetros del servidor, healthcheck, límites del contenedor, versión de la imagen) y corregirla, o, si no se encuentra, mitigar (reintentos en el cliente ante 503 durante la recarga) y documentarlo en el runbook. Sin tocar la base real.
- **Archivos:** `docker-compose.yml` y `evaluon/ai/__init__.py` solo si la corrección lo requiere; informe en `specs/003-pliego-matriz/verificacion/T-090.md`.
- **Verificación:** una corrida de varias horas (o la reproducción de la causa) sin reinicios no previstos, o el reintento probado con un servidor que devuelve 503; la consulta de la 001 sigue haciendo el mismo pedido.
- **No tocar:** instrucciones, umbral, parámetros de búsqueda.
- **Entorno:** MSI con GPU.

### T-091 · Comparar niveles medidos en corridas separadas

- **Qué hacer:** observación F3 de T-084: cuando `medir_matriz` mide los niveles en corridas separadas, la sección "Comparación entre niveles" de cada resumen dice "base". Permitir pasar las corridas anteriores (por ejemplo `--comparar-con <carpeta>`) o comparar automáticamente con la última corrida de cada nivel en la misma carpeta, y aplicar la regla de la spec (un nivel se ofrece solo si mejora al anterior).
- **Archivos:** `evaluon/tenders/evaluation.py`, `evaluon/tenders/management/commands/medir_matriz.py`, `tests/tenders/test_evaluation.py`.
- **Verificación:** con corridas sintéticas de media, alta y exigente en carpetas separadas, el resumen compara y dice qué niveles mejoran; nada de texto del pliego en el resumen público.
- **No tocar:** la propuesta.
- **Entorno:** cualquier equipo con Docker.

### T-088 · Cambiar el rol de la Comisión de un usuario existente, con registro

- **Qué hacer:** hoy `crear_usuario --rol-comision` solo sirve para usuarios nuevos. El 2026-10-04 el Coordinador le dio rol de evaluador al usuario `sandro` en la base real con una actualización directa del campo `commission_role` (pedido del responsable), sin hecho de auditoría porque no hay tipo de hecho ni comando para eso. Agregar un comando `rol_comision <usuario> {operador,evaluador,ninguno}` que cambie el rol y deje un hecho (un tipo nuevo `user_role_changed`, con su migración de `audit`, o el que corresponda), y anotar en el registro el cambio manual del 2026-10-04 corriendo el comando sobre `sandro` con el mismo valor o registrando el hecho de regularización.
- **Archivos:** `evaluon/accounts/management/commands/rol_comision.py`, `evaluon/audit/models.py` y su migración, `tests/accounts/test_commission_role_change.py`.
- **Verificación:** tests: el cambio deja el hecho con quién, antes y después; un usuario inexistente o un valor inválido se rechazan sin cambiar nada.
- **No tocar:** `crear_usuario` salvo para compartir validaciones; `evaluon/tenders/`.
- **Entorno:** cualquier equipo con Docker.

### T-087 · Comparar en la misma zona horaria la fecha de lectura del informe

- **Qué hacer:** defecto encontrado en la suite al desarrollar T-068 (decisión del Coordinador, 2026-10-03): `tests/norms/test_duplicates.py::test_report_document_part_has_file_name_hash_and_read_date` compara `read_at` del informe (hora local) con `created_at.date()` (UTC) y falla entre las 21 y las 24 hora argentina. Determinar si el defecto es del test o del informe (la fecha que ve la persona tiene que ser la local, `America/Argentina/Buenos_Aires`) y corregirlo donde corresponda, sin cambiar lo que el test comprueba. Buscar otros tests con la misma comparación.
- **Archivos:** `tests/norms/test_duplicates.py`; el código del informe de lectura en `evaluon/norms/` solo si el defecto es del producto.
- **Verificación:** el test pasa con el reloj fijado a las 23:30 hora argentina y a las 10:00 (por ejemplo, con `time_machine` o fijando `timezone.now`); suite completa en verde.
- **No tocar:** `evaluon/tenders/`, `accounts`.
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
| REQ-032 | T-067, T-074, T-082, T-086 |

## Paralelismo

Esquema y configuración compartida, de a una: T-067 (tablas, `audit_event`, `settings.py`) → T-068 (`accounts`) y T-071 (`docker-compose.yml`, cliente de generación, `tests/conftest.py`). T-086 toca `pyproject.toml` y el `Dockerfile`, que ninguna otra tarea de la 003 toca. T-085 vuelve a tocar `settings.py`, al final.

| Momento | Pueden ir a la vez | Por qué no chocan |
|---|---|---|
| Desde ya | T-067 y T-076 | T-076 es de datos, fuera del repositorio |
| Terminada T-067 | T-068, T-070 y T-071 | `accounts`; `segmenting.py` y `tables.py`; `jobs.py`, `docker-compose.yml` y el cliente. Los usuarios de prueba de T-068 van en `tests/tenders/conftest.py` y el doble de T-071 en `tests/conftest.py` |
| Terminada T-073 | T-074, T-077 y T-078 | Vistas y plantillas; `evaluation.py` y su comando; `completeness.py` y `run.py` |
| Terminadas T-074 y T-078 | T-079 y T-080 | Revisión en vistas; consecuencias en `proposal/` |
| Terminada T-080 | T-083, en paralelo con T-081 y T-082 | `circulars.py` y `run.py` frente a vistas y servicios de elección y validación |
| Terminada T-082 | T-086, en paralelo con T-083, T-084 y T-085 | `export.py`, plantilla de impresión, `pyproject.toml` y `Dockerfile` frente a `proposal/`, la corrida y `settings.py` con `procedure.html` |
| Terminada T-074 | T-075, en paralelo con todo lo que no ocupe la GPU | T-075 no escribe código |

Cadenas que se respetan por compartir archivos:

- **Vistas, `urls.py` y plantillas:** T-069 → T-072 → T-074 → T-079 → T-081 → T-082 → T-086; T-082 → T-085 (`procedure.html`).
- **`proposal/run.py`:** T-073 → T-078 → T-080 → T-083.
- **`jobs.py`:** T-071 → T-072 → T-073.
- **`base.html`:** T-069 → T-074.

Recursos que no se comparten: la GPU (T-071 en su medición, T-075 y T-084, de a una) y la base de pruebas.

Camino crítico hasta ver una matriz: T-067 → T-068 → T-069 → T-072 → T-073 → T-074 → T-075 (con T-076 lista antes). Hasta la medición: … → T-073 → T-078 → T-080 → T-084.
