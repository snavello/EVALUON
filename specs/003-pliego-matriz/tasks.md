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
| T-085 | Ofrecer solo los niveles que mejoran | REQ-030 | T-084 | terminada |
| T-086 | Imprimir y exportar la matriz a PDF con la leyenda de borrador | REQ-032 | T-082 | terminada |
| T-087 | Comparar en la misma zona horaria la fecha de lectura del informe | REQ-004 | — | terminada |
| T-088 | Cambiar el rol de la Comisión de un usuario existente, con registro | REQ-026 | — | terminada |
| T-089 | Contar bien las páginas en la extrapolación de tiempos | REQ-030 | T-084 | terminada |
| T-090 | Investigar y corregir los reinicios de los servidores de generación | REQ-024, REQ-030 | T-084 | terminada |
| T-091 | Comparar niveles medidos en corridas separadas | REQ-030 | T-084 | terminada |
| T-092 | Aceptar las divisiones de la completitud aunque el original no coincida letra por letra | REQ-024 | T-084 | terminada |
| T-093 | Ajustar las instrucciones con el caso-00 (enumeraciones, tablas, condiciones como efecto) | REQ-024 | T-092 | terminada |
| T-094 | Medir la aceptación con los casos 01 y 02 | REQ-024, REQ-025, REQ-030, REQ-031 | T-085, T-093, T-095 | terminada |
| T-095 | Contar como "a revisión obligatoria" los requisitos en tramos pendientes | REQ-024 | T-093 | terminada |
| T-096 | Corregir la cobertura de tramos de `medir_matriz` cuando hay circulares | REQ-030 | T-095 | terminada |
| T-097 | Corregir la cita literal de las filas técnicas con varios documentos en `medir_matriz` | REQ-025, REQ-030 | T-096 | terminada |
| T-098 | Corregir la pasada de circulares (fuentes, tramos descartados y no ubicados) | REQ-028, REQ-031 | T-094 | terminada |
| T-099 | Crear la tabla de filas descartadas, el estado de sugerencia, el respaldo normativo, las citas repetidas y los parámetros del filtro | REQ-030, REQ-033, REQ-035, REQ-036 | T-096 | terminada |
| T-100 | Quitar el nivel "media" y dejar un solo proceso registrado | REQ-030 | T-099, T-097, T-098 | terminada |
| T-101 | Unificar las filas que repiten la misma condición | REQ-025, REQ-033 | T-100 | terminada |
| T-102 | Filtrar con dos preguntas y repartir cada fila en firme, sugerencia o descartada | REQ-024, REQ-033, REQ-035 | T-101 | terminada |
| T-103 | Medir los sobrantes sobre las filas firmes, con tope e informe de descartadas | REQ-024, REQ-030, REQ-033, REQ-035 | T-099, T-100 | terminada |
| T-104 | Listar y devolver las filas descartadas, y revisar por grupos | REQ-026, REQ-033, REQ-034 | T-099 | terminada |
| T-105 | Mostrar las descartadas, las citas repetidas y la revisión por grupos | REQ-032, REQ-033, REQ-034 | T-100, T-104 | terminada |
| T-106 | Medir el filtro, las sugerencias y el respaldo normativo con el caso-00 y ajustarlos | REQ-024, REQ-033, REQ-035, REQ-036 | T-102, T-103, T-109, T-111 | pendiente |
| T-107 | Decidir con el responsable el tope, la lista y las sugerencias con lo medido en el caso-00 | REQ-033, REQ-035 | T-106 (T-106 diferida, ADR-0024) | terminada |
| T-108 | Medir la aceptación del proceso con filtro y sugerencias con los casos 01 y 02, y REQ-031 con los casos 03 y 04 | REQ-024, REQ-025, REQ-030, REQ-031, REQ-033, REQ-035, REQ-036 | T-094, T-105, T-112, T-107, T-116, T-120 | terminada |
| T-109 | Buscar el respaldo normativo de cada sugerencia, sin que nunca la descarte | REQ-036 | T-099, T-102 | terminada |
| T-110 | Decidir las sugerencias: pasar a requisito o quitar, una por una o por grupo, y bloquear la validación | REQ-035, REQ-034, REQ-026 | T-099, T-104 | terminada |
| T-111 | Medir las sugerencias y el respaldo normativo: a revisión obligatoria e informe | REQ-035, REQ-036, REQ-024 | T-099, T-103 | terminada |
| T-112 | Mostrar la sección de sugerencias con su respaldo en la pantalla y en la impresión | REQ-035, REQ-036, REQ-034, REQ-032 | T-105, T-110 | terminada |
| T-113 | Pasada de circulares, entrega 1: unidades de cambio aplicadas por clave, sin modelo | REQ-028, REQ-031 | T-098 | terminada |
| T-114 | Crear el campo de original en un anexo, el pedido de extracción de cambios y los parámetros de circulares | REQ-031 | T-099, T-100 | terminada |
| T-115 | Pasada de circulares, entrega 2: el modelo extrae la lista de cambios donde no hay clave | REQ-031 | T-113, T-114 | terminada |
| T-116 | Mostrar y imprimir el original en el anexo, el cambio agrupado y el requisito agregado por una circular | REQ-031, REQ-032 | T-113, T-114, T-105, T-112 | terminada |
| T-117 | Medir REQ-031 por fila en `medir_matriz`: documento, fecha, texto original y vigente | REQ-031 | T-103, T-111 | terminada |
| T-118 | Cargar los casos 05 y 06 y preparar sus listas esperadas de circulares | REQ-031 | T-117 | terminada |
| T-119 | Actualizar la lista esperada del caso-01 con las filas que las circulares afectan | REQ-031 | T-117 | terminada |
| T-120 | Medir y ajustar la pasada de circulares con los casos 01, 05 y 06, con estabilidad | REQ-031 | T-113, T-115, T-117, T-118, T-119 | terminada |
| T-121 | Corregir el consumo de memoria de la medición (citas que cargaban cada una su lectura) | REQ-024, REQ-030 | T-117 | terminada |
| T-122 | Mostrar los cambios vigentes de la norma al proponer consecuencias, o no fundar en unidades modificadas | REQ-029 | T-109 | pendiente |
| T-123 | Corregir la medición: citas de otra lectura y filas suprimidas por una circular | REQ-024, REQ-031 | T-117 | terminada |
| T-124 | Pasada de circulares: original en el anexo por título y requisitos que agrega un "Debe decir" | REQ-031 | T-115 | terminada |
| T-125 | Corregir el criterio del filtro que descartó requisitos reales | REQ-024, REQ-033 | T-102 | terminada |
| T-126 | Mostrar la cadena completa de circulares que modifican una misma condición | REQ-031 | T-116, T-124 | terminada |
| T-127 | Impedir que una aclaración termine como supresión y registrar la versión de `circulares_cambios` | REQ-031 | T-115, T-124 | terminada |
| T-128 | Aplicar una aclaración de cláusula a todas sus citas | REQ-031 | T-115, T-124, T-127 | terminada |
| T-129 | Reconocer supresiones dichas con sustantivo y aplicar la aclaración de un renglón a sus citas | REQ-031 | T-127, T-128 | terminada |
| T-137 | Pasada de circulares: revisión obligatoria visible ante un cambio sin resolver y las tres causas de la aceptación a ciegas | REQ-031 | T-108, T-129 | terminada |
| T-147 | Circulares: aviso en la fila que cambia (#183) y medición del criterio de ADR-0034 | REQ-031, REQ-024 | T-137 | terminada |

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

### T-092 · Aceptar las divisiones de la completitud aunque el original no coincida letra por letra

- **Qué hacer:** defecto encontrado al analizar los faltantes de T-084 (consulta de solo lectura del 2026-10-04): la pasada de completitud propuso divisiones correctas (M-044 en alta, M-009 en exigente) y el sistema las rechazó con `completitud_division_no_aplicada` porque el `original` que escribe el modelo no es idéntico al fragmento de la fila existente (por ejemplo, el modelo copia la etiqueta de clase "(formal)" dentro del original, o recorta distinto). Además, esa pasada dejó una fila duplicada. Identificar la fila original por superposición con la cita existente (tolerando la etiqueta de clase, espacios y recortes) en lugar de igualdad exacta; mantener las reglas de T-078 (las partes dentro del original y cubriéndolo; si no, queda el original con la anomalía); no crear duplicados.
- **Archivos:** `evaluon/tenders/proposal/completeness.py`, `tests/tenders/test_completeness.py`.
- **Verificación:** tests con el doble: un original con "(formal)" pegado, uno con espacios o recorte distinto, y uno que no corresponde a ninguna fila (se ignora con anomalía); ninguna división acepta partes que no cubran el original; sin duplicados. Suite en verde.
- **No tocar:** instrucciones, `run.py` salvo lo imprescindible, la lista esperada.
- **Entorno:** cualquier equipo con Docker.

### T-093 · Ajustar las instrucciones con el caso-00 (enumeraciones, tablas, condiciones como efecto)

- **Qué hacer:** decisión del responsable del 2026-10-04 sobre la medición provisoria de T-084 (alta 88,5 %): ajustar con el caso-00, que pasa a uso `ajuste` (decisión 7 del plan). (1) Instrucciones de extracción y de completitud (versiones v2, sin modificar las v1): dividir enumeraciones con comas o "y" en una fila por condición, con ejemplos sintéticos; reconocer como requisito una condición dicha como efecto ("se considerará…", "se entenderá…", "quedará…") y sumar esos marcadores a los de obligación. (2) Regla del sistema: un tramo `tabla` nunca queda `descartado`; o el modelo propone filas o queda pendiente con motivo `tabla`. (3) "Agrupado" sigue contando como faltante (decisión del responsable): no se toca la medición. Volver a medir el caso-00 en los niveles que se ofrecen (media y alta, T-085) y comparar con T-084. No usar los casos 01 y 02.
- **Archivos:** `evaluon/tenders/prompts/matriz-extraccion-v2.md`, `evaluon/tenders/prompts/matriz-completitud-v2.md`, `evaluon/tenders/proposal/` (solo la versión de instrucciones activa, los marcadores y la regla de tablas), `evaluon/settings.py` (`MATRIX_PROMPT_VERSIONS`), tests de `tests/tenders/`; informe en `specs/003-pliego-matriz/verificacion/T-093.md` sin texto del pliego.
- **Verificación:** tests con el doble (división de enumeraciones, tabla nunca descartada, marcadores nuevos); corrida del caso-00 con el modelo real en media y alta, informe comparado con T-084; suite en verde.
- **No tocar:** la lista esperada; la regla de emparejamiento; los casos 01 y 02.
- **Entorno:** MSI con GPU.

### T-094 · Medir la aceptación con los casos 01 y 02

- **Qué hacer:** con las instrucciones fijas después de T-093 y los niveles de T-085, `medir_matriz --verificar-esperada` y la medición de los casos 01 y 02 (reservados, nunca usados para ajustar) en los niveles que se ofrecen. Es la medida de aceptación de la feature: 100 % de encontrados, 100 % de cita literal, REQ-031 con las circulares reales del caso-01, tiempos (el caso-01 tiene 52 páginas) y memoria. Informe sin texto del pliego; un faltante bloquea y se informa con su causa, sin ajustar nada.
- **Archivos:** corridas en `corpus/casos/caso-0N/corridas/` (fuera del repositorio); `specs/003-pliego-matriz/verificacion/T-094.md`.
- **Verificación:** el informe con todas las medidas, su intervalo y el resultado de aceptación; ningún texto del pliego en el repositorio.
- **No tocar:** instrucciones, parámetros, listas esperadas.
- **Entorno:** MSI con GPU.

### T-095 · Contar como "a revisión obligatoria" los requisitos en tramos pendientes

- **Qué hacer:** decisión del responsable del 2026-10-04 (enmienda de la spec, medición): en `medir_matriz`, un esperado sin pareja cuyo tramo quedó pendiente de revisión (causa `tramo_pendiente`) cuenta como "a revisión obligatoria": entra en el numerador de la aceptación y se informa aparte con su cantidad y claves, en `resumen.md` y `resumen-publico.md` (sin texto del pliego). Los demás faltantes no cambian. Recalcular la corrida de T-093 del caso-00 sin el modelo, si el comando lo permite, o dejar el recálculo para la próxima corrida.
- **Archivos:** `evaluon/tenders/evaluation.py`, `tests/tenders/test_evaluation.py`.
- **Verificación:** test: un esperado en un tramo pendiente cuenta como "a revisión obligatoria" y la aceptación lo suma; un esperado en un tramo descartado o con requisitos sigue siendo faltante; el resumen público no lleva texto.
- **No tocar:** la propuesta; la lista esperada.
- **Entorno:** cualquier equipo con Docker.

### T-096 · Corregir la cobertura de tramos de `medir_matriz` cuando hay circulares

- **Qué hacer:** en la medición del caso-01 (T-094, 16 documentos y 2 circulares), `resumen.md` falló con `ValueError: math domain error`: la cobertura dividía los tramos con disposición de la propuesta (1.732, que incluyen los de las circulares) por los tramos de los documentos base (1.632). Medir la cobertura sobre un solo conjunto (tramos de los documentos de la corrida) e informar aparte los tramos de circulares con disposición. Que una proporción fuera de 0 a 100 % no pierda el resumen: `wilson_interval` devuelve `None` y el texto informa la anomalía. Agregar `medir_matriz --regenerar-resumen CARPETA`, que reescribe los dos resúmenes de una corrida hecha, sin el modelo, midiendo de nuevo las propuestas que nombra `parametros.json` (siguen en la base aunque estén descartadas).
- **Archivos:** `evaluon/tenders/evaluation.py`, `evaluon/queries/evaluation.py`, `evaluon/tenders/management/commands/medir_matriz.py`, `tests/tenders/test_evaluation.py`, `tests/queries/test_margin_of_error.py`.
- **Verificación:** tests: con una circular cargada, la cobertura cuenta el mismo conjunto y los tramos de la circular van aparte; una proporción fuera de rango se informa sin romper el resumen; el comando regenera los resúmenes sin llamar al modelo.
- **No tocar:** la propuesta, las instrucciones, la lista esperada.
- **Entorno:** cualquier equipo con Docker.

### T-097 · Corregir la cita literal de las filas técnicas con varios documentos en `medir_matriz`

- **Qué hacer:** en la medición del caso-01 (T-094) la cita literal dio 57,4 % (media) y 54,8 % (alta); todas las citas no literales eran de filas técnicas. Diagnóstico con la base real, en solo lectura: las 10.874 y 10.984 citas de las dos versiones son literales contra la lectura de su propio tramo (texto igual al recorte, dentro del tramo, con página). El defecto es del medidor: `measure_version` comparaba cada cita de una fila contra la lectura de la primera cita de la fila, y una fila técnica cita tramos del pliego y del manual. Medir cada cita contra la lectura de su propio tramo. Regenerar después los resúmenes del caso-01 con `medir_matriz --regenerar-resumen`.
- **Archivos:** `evaluon/tenders/evaluation.py`, `tests/tenders/test_evaluation.py`.
- **Verificación:** test: una fila técnica que cita tramos de dos documentos mide el 100 % de sus citas literales (falla sin el arreglo); suite completa en verde.
- **No tocar:** la propuesta, las instrucciones, la lista esperada.
- **Entorno:** cualquier equipo con Docker.

### T-098 · Corregir la pasada de circulares (fuentes, tramos descartados y no ubicados)

- **Qué hacer:** decisión del responsable del 2026-10-04. En la medición del caso-01 (T-094), REQ-031 no se cumple: M-029 y M-044 sin fuente de circular (tramos de la Circular 1 descartados por título o como líneas de fechas), M-015 sin fila (los tramos de la Circular 2 quedan `no_ubicado`), y fuentes de la Circular 1 pegadas a filas técnicas ajenas. Diagnosticar en la base real en solo lectura y corregir causas generales, no a la medida del texto del caso-01; sin cambiar instrucciones con ejemplos del caso-01.
- **Archivos:** `evaluon/tenders/` (pasada de circulares), tests de `tests/tenders/`.
- **Verificación:** tests con textos inventados que reproducen cada fallo y fallan sin el arreglo; suite completa.
- **No tocar:** `medir_matriz` y `evaluation.py`, la lista esperada, `plan.md`.
- **Entorno:** cualquier equipo con Docker; diagnóstico con la base real en solo lectura.

### Enmienda del 2026-10-04: proceso único, filtro de sobrantes, descartadas, grupos y sugerencias (T-099 a T-112)

Plan: sección "Enmienda del 2026-10-04" de `plan.md` y su subsección "Sugerencias de condición y respaldo normativo" (REQ-035 y REQ-036); ADR-0021 (aceptado) y ADR-0022 (propuesto). Las tareas de sugerencias (T-109 a T-112 y los cambios a T-099, T-102, T-103, T-106, T-107 y T-108) esperan la aprobación de esa subsección. Cadenas: esquema y configuración compartida, solo T-099 y, después, T-100 (`settings.py`); `proposal/run.py`: T-098 → T-100 → T-101 → T-102 → T-109; `evaluation.py` y `medir_matriz`: T-097 → T-100 → T-103 → T-111; servicios de revisión y validación: T-104 → T-110; vistas y plantillas de revisión: T-104 → T-105 → T-112.

**Los tres destinos (T-102).** Cada fila formal o económica que pasa por el filtro termina como **firme** (requisito `propuesto`), **sugerencia** (requisito en estado `sugerido`, con motivo de la duda) o **descartada** (`tenders_discarded_row`), según la tabla del plan: descartada solo con las cuatro condiciones del ADR-0021; firme solo con (mantener, sí), con una única opinión válida que mantiene o sin ninguna opinión válida; todo lo demás, sugerencia.

### T-099 · Crear la tabla de filas descartadas, el estado de sugerencia, el respaldo normativo, las citas repetidas y los parámetros del filtro

- **Qué hacer:** una migración y los parámetros del plan ("Modelo de datos y migración" de la enmienda y "Cómo se guarda" de las sugerencias): tabla `tenders_discarded_row` de solo inserción (con trigger y su reversa); `tenders_requirement_quote.scope` suma `repetida` y la restricción pasa a "una cita con `scope` vacío más las `repetida` que haga falta" en formales y económicos (adaptar la restricción o el trigger de T-067 sin perder las pruebas); `tenders_requirement.origin` suma `devuelto` y el campo `restored_from` (único por versión); `tenders_requirement.state` suma `sugerido`, con los campos `doubt_reason` (`''`, `no_coinciden`, `duda`, `descarte_sin_sustento`, `opinion_incompleta`) y `doubt` (JSON: las dos respuestas, el indicio literal con su ubicación y los pedidos que las produjeron), y la restricción "un requisito en `sugerido` tiene `doubt_reason` y no es técnico"; tabla `tenders_norm_support` de solo inserción (con trigger y su reversa): `requirement`, `unit` (id de `norms_unit`), `unit_label`, `char_start`, `char_end`, `text`, `score`, `regime`, `corpus_version`, `step`, `created_at`; `tenders_requirement_change.action` suma `devolver` y `aceptar_sugerencia`; `tenders_run_step.pass_name` suma `unificacion`, `filtro`, `filtro_2` y `respaldo_normativo`; `tenders_disposition.source` suma `filtro`; `process` en `tenders_matrix_run` y `tenders_matrix_version`, y `level` admite vacío (los datos viejos conservan el suyo). `settings.py`: `FILTER_ENABLED`, `FILTER_BATCH_ROWS`, `FILTER_MOTIVES`, `DEDUP_MIN_SIMILARITY`, `MATRIX_SAMPLE_DISCARDED`, `MATRIX_SOBRANTES_LIMIT`, `MATRIX_PROCESS` (`completo`), `SUGGESTIONS_ENABLED`, `DOUBT_MOTIVES`, `NORM_SUPPORT_ENABLED`, `NORM_SUPPORT_MIN_SCORE` (el umbral del reranker de la 001), `NORM_SUPPORT_MAX_UNITS` (4), `NORM_SUPPORT_QUERY_MAX_CHARS` (800) y las versiones de instrucciones `filtro`, `unificacion` y `respaldo` en `MATRIX_PROMPT_VERSIONS`. No quita ni cambia `MATRIX_LEVELS` (es de T-100).
- **Archivos:** `evaluon/tenders/models.py`, `evaluon/tenders/migrations/` (una nueva), `evaluon/settings.py`, `tests/tenders/test_models.py`.
- **Verificación:** `migrate` sobre base vacía y `migrate --check`; tests: UPDATE y DELETE sobre `tenders_discarded_row` y sobre `tenders_norm_support` rechazados por la base; un formal con una cita principal y dos `repetida` se acepta, con dos principales se rechaza, y un técnico no cambia; dos requisitos de una versión con el mismo `restored_from` se rechazan; un requisito `sugerido` sin `doubt_reason` o técnico se rechaza, y uno con motivo válido se acepta; los valores nuevos de `state`, `origin`, `action`, `pass_name` y `source` se aceptan y uno inventado, no; los datos de una propuesta anterior (con `level` y sin `process`) siguen siendo válidos; suite en verde.
- **No tocar:** `proposal/`, servicios, vistas, `evaluation.py`; las instrucciones.
- **Entorno:** cualquier equipo con Docker.

### T-100 · Quitar el nivel "media" y dejar un solo proceso registrado

- **Qué hacer:** decisión del responsable del 2026-10-04 (REQ-030 enmendado). El proceso único es el de "alta": extracción, completitud, filas técnicas, circulares y consecuencias. Quitar del producto la elección de nivel y los otros dos niveles: el formulario "Proponer matriz" de la pantalla, `MATRIX_LEVELS`, `MATRIX_LEVELS_OFFERED` y el nivel por omisión (en su lugar, `MATRIX_PROCESS`), la validación del nivel en `services/matrix.py`, la rama de media (marcadores que dejan pendiente) y la segunda extracción de exigente en `run.py` y `completeness.py`, la columna "nivel" de la matriz y de la impresión, y `medir_matriz --niveles` (se mide el proceso único; la comparación entre niveles de T-091 y la regla "un nivel se ofrece solo si mejora" dejan de aplicar). La propuesta registra `process` y la versión de cada instrucción en `tenders_matrix_run` y en la versión de matriz. Buscar todas las referencias (`level`, `nivel`, `MATRIX_LEVELS`, `media`, `exigente`) y dejar las propuestas ya guardadas legibles con su nivel como dato histórico. Retirar los tests que solo probaban niveles o la segunda extracción; mantener los de completitud y los demás.
- **Archivos:** `evaluon/settings.py`, `evaluon/tenders/services/matrix.py`, `evaluon/tenders/proposal/run.py`, `evaluon/tenders/proposal/completeness.py`, `evaluon/tenders/evaluation.py`, `evaluon/tenders/management/commands/medir_matriz.py`, `evaluon/tenders/views/` (solo lo que lea el nivel), `evaluon/templates/tenders/procedure.html`, `evaluon/templates/tenders/matrix.html`, `evaluon/templates/tenders/matrix_print.html`, y los tests de `tests/tenders/` que nombran niveles (`test_levels_offered.py`, `test_matrix_request.py`, `test_completeness.py`, `test_evaluation.py`, `test_models.py` y los que la búsqueda encuentre).
- **Verificación:** tests: el pedido de una matriz no recibe nivel y el formulario no lo ofrece; la propuesta registra `process` `completo` y las versiones de instrucciones; la propuesta hace lo mismo que "alta" en T-093 con el doble (mismas pasadas, mismas filas); `medir_matriz` ya no acepta `--niveles`; la matriz y la impresión muestran el proceso y no un nivel; una propuesta vieja con `level` `media` se sigue viendo; búsqueda sin referencias vivas a `MATRIX_LEVELS_OFFERED` o a la segunda extracción; suite completa en verde.
- **No tocar:** las instrucciones; la regla de emparejamiento y la lista esperada; `proposal/circulars.py` (T-098); el esquema (T-099). Esta tarea espera la integración de T-098 (`proposal/`) y de T-097 (`evaluation.py`).
- **Entorno:** cualquier equipo con Docker.

### T-101 · Unificar las filas que repiten la misma condición

- **Qué hacer:** `proposal/dedup.py` (plan, "Unificación de repetidas"): normalización del fragmento, igualdad, contención y similitud de palabras con `DEDUP_MIN_SIMILARITY`; la fila que queda es la primera en el orden del pliego y conserva las citas de las otras como citas `repetida` literales; no junta filas técnicas, de circulares ni de cita amplia, ni dos filas de un mismo tramo con citas sin superposición; registro en `tenders_run_step` (`unificacion`); cuentas en `counts`; la pasada en `run.py` después de la completitud y antes de las filas técnicas.
- **Archivos:** `evaluon/tenders/proposal/dedup.py`, `evaluon/tenders/proposal/run.py`, `tests/tenders/test_dedup.py`.
- **Verificación:** tests con el doble: dos filas con el mismo fragmento en tramos distintos dan una con dos citas, cada una igual a su recorte; una fila contenida en otra se une; dos condiciones distintas de un mismo tramo no se unen; las técnicas y las de circulares quedan como están; el registro lista los pares unidos y el umbral; con `DEDUP_MIN_SIMILARITY` en 1,0 solo se unen las iguales; suite en verde.
- **No tocar:** `extraction.py`, `completeness.py` (salvo importar sus funciones), `circulars.py`; el esquema.
- **Entorno:** cualquier equipo con Docker.

### T-102 · Filtrar con dos preguntas y repartir cada fila en firme, sugerencia o descartada

- **Qué hacer:** `proposal/filter.py` y las instrucciones `prompts/matriz-filtro-v1.md` (plan, "Filtro de precisión" y "Tres destinos en vez de dos"): alcance (formales y económicos propuestos por el modelo, sin técnicos, circulares, tablas, cita amplia ni secciones con clase formal o económica); lotes de `FILTER_BATCH_ROWS`; clasificación con motivo de la lista e indicio, y pregunta inversa, cada una con salida estructurada obligada; **destino de cada fila según la tabla del plan**: descartada solo con las cuatro condiciones; firme con (mantener, `si`), con una única opinión válida que mantiene o `si`, o sin ninguna válida (con la anomalía); sugerencia en todo lo demás, creada como requisito en estado `sugerido` con su `doubt_reason` y `doubt` (las dos respuestas, el indicio literal y los pedidos), con la cita, las citas `repetida`, la clase y los renglones de la fila; con `SUGGESTIONS_ENABLED` en falso, lo que sería sugerencia queda firme; partición de un lote cortado; registro de cada pedido en `tenders_run_step` (`filtro`, `filtro_2`); filas descartadas en `tenders_discarded_row` (con las citas adicionales y los dos votos); disposición `descartado` con origen `filtro` para un tramo cuyas filas se descartaron todas (un tramo con alguna fila firme o sugerencia queda `requisitos`); cuentas por motivo, por pasada, firmes, sugerencias por `doubt_reason` y firmes por falla técnica; la pasada en `run.py` después de la unificación y antes de las reglas de tablas, las filas técnicas, las circulares y las consecuencias; `FILTER_ENABLED` en falso saltea la pasada. Las consecuencias se piden para las filas firmes y para las sugerencias (ajuste mínimo de la selección de filas en `proposal/consequences.py`, solo si hoy filtra por estado). Instrucciones con ejemplos sintéticos de otro objeto y otras cifras que el caso-00.
- **Aviso de tareas anteriores:** T-099: el motivo del filtro se llama `consecuencia_sancion` en `FILTER_MOTIVES` (el plan escribe `consecuencia_o_sancion`); las instrucciones deben usar los valores de `FILTER_MOTIVES`. T-104: `DiscardedRow.extra_quotes` se lee como lista de `{segment (id del tramo), char_start, char_end, text}`; escribir exactamente ese formato.
- **Archivos:** `evaluon/tenders/proposal/filter.py`, `evaluon/tenders/proposal/run.py`, `evaluon/tenders/proposal/consequences.py` (solo qué filas se piden), `evaluon/tenders/prompts/matriz-filtro-v1.md`, `tests/tenders/test_filter.py`.
- **Verificación:** tests con el doble, una fila por cada renglón de la tabla de destinos: (descartar con motivo e indicio literal, `no`) se descarta y queda en la tabla con su cita, motivo, indicio y los dos votos; (mantener, `si`) queda firme; (mantener, `duda`), (mantener, `no`), (descartar válido, `si`), (descartar válido, `duda`), (descartar con indicio que no está o motivo fuera de la lista, cualquiera) y una única opinión válida `descartar`, `no` o `duda` quedan como sugerencia, cada una con la cita, el motivo `doubt_reason` que corresponde y el indicio; dos opiniones inválidas o una única opinión que mantiene dejan la fila firme; una fila técnica, de circular, de tabla o de cita amplia no se manda al modelo; el tramo con todas las filas descartadas queda `descartado` con origen `filtro` y el que tiene una sugerencia, `requisitos`; un lote cortado se parte; con `FILTER_ENABLED` en falso la matriz es la de antes y con `SUGGESTIONS_ENABLED` en falso no hay sugerencias; una prueba busca las anclas de la lista del caso-00 en las instrucciones, los tests y los ejemplos y falla si aparece alguna de 5 palabras; las consecuencias se piden para las firmes y las sugerencias y no para las descartadas; la pasada de circulares alcanza una sugerencia como a cualquier fila no quitada; suite en verde.
- **No tocar:** `extraction.py`, `completeness.py`, `circulars.py`, las instrucciones de extracción y de completitud; la lista esperada; el esquema (T-099).
- **Entorno:** cualquier equipo con Docker.

### T-103 · Medir los sobrantes sobre las filas firmes, con tope e informe de descartadas

- **Qué hacer:** cambios de "Cambios en la medición" del plan: la matriz propuesta es lo que ve la Comisión (sin descartadas **y sin las sugerencias, estado `sugerido`**, que no entran en el tope; el emparejamiento y el informe de sugerencias son de T-111); sobrantes, proporción de sobrantes sobre las filas de la matriz (formales, económicas y técnicas) con su intervalo de Wilson y la proporción solo sobre formales y económicos; veredicto del tope con `MATRIX_SOBRANTES_LIMIT` y el 100 % de encontrados (con "a revisión obligatoria"); esperado descartado por el sistema como faltante con causa `descartado_por_el_sistema`, motivo y clave; esperado en una cita `repetida` como encontrado "unificado"; pareja con cualquiera de las citas de la fila; informe de descartadas por motivo, tramo y pasada, con los sobrantes que habría sin el filtro y la muestra de `MATRIX_SAMPLE_DISCARDED` filas en `resumen.md` y en la plantilla local `muestra-descartadas.md`; `resumen-publico.md` solo con cuentas, claves y motivos; tiempos de `unificacion` y `filtro`; `--verificar-esperada` avisa de dos esperados con el mismo ancla normalizado; `--regenerar-resumen` sigue funcionando con propuestas sin descartadas.
- **Archivos:** `evaluon/tenders/evaluation.py`, `evaluon/tenders/management/commands/medir_matriz.py`, `tests/tenders/test_evaluation.py`, `tests/tenders/fixtures/` (listas y propuestas sintéticas).
- **Verificación:** tests con datos sintéticos insertados en la base: las descartadas y las filas `sugerido` no cuentan como sobrantes ni en el denominador del tope; un esperado cuya cita está en una descartada es faltante con la causa propia y el motivo; uno en una cita `repetida` cuenta como unificado y no como faltante; con 8 sobrantes sobre 40 filas (20 %) el tope cumple y con 9 sobre 40 no; con un faltante el tope no cumple aunque la proporción sí; la muestra sale con el tamaño y el orden previstos; `resumen-publico.md` no contiene texto de ninguna cita ni indicio (se comprueba buscando cada texto); una corrida sin descartadas da las medidas de siempre; suite en verde.
- **No tocar:** la propuesta (`proposal/`); la regla de emparejamiento salvo las citas adicionales; la lista esperada. Espera a T-100 (que ya quitó `--niveles` en el mismo archivo).
- **Entorno:** cualquier equipo con Docker.

### T-104 · Listar y devolver las filas descartadas, y revisar por grupos

- **Qué hacer:** `services/discarded.py` (listar las descartadas de una versión con su estado derivado, por la cadena `based_on`; `restore`, operador o evaluador, que crea el requisito con `origin` `devuelto`, `restored_from`, `proposed`, citas principal y adicionales, estado `propuesto`, fila `devolver` en `tenders_requirement_change` con el motivo y el indicio del descarte, y hecho `requirement_change`; rechazo en una versión validada); en `services/review.py`, `confirm_group` (solo evaluador) y `remove_group` (operador o evaluador) según el plan ("Revisión por grupos"): la clave del grupo se continúa solo en un separador de nivel, actúa solo sobre las filas `propuesto`, en una transacción, llamando a la función de cada fila, con una fila de historial por requisito marcada `via_grupo`; `services/validation.py` suma al hecho `matrix_validation` las cuentas de descartadas totales y devueltas; copiar los requisitos devueltos con su `restored_from` en una versión nueva.
- **Archivos:** `evaluon/tenders/services/discarded.py`, `evaluon/tenders/services/review.py`, `evaluon/tenders/services/validation.py`, `tests/tenders/test_discarded.py`, `tests/tenders/test_review_group.py`.
- **Verificación:** tests: cinco filas propuestas de una cláusula confirmadas como grupo quedan `confirmado` con una fila de historial cada una, con quién y cuándo, igual a una confirmación individual; `sec-i/1` no alcanza a `sec-i/11` y `sec-i/11.3/v-1` es del grupo `sec-i/11.3`; una fila ya confirmada o corregida no se toca, y una fila en `sugerido` tampoco (las sugerencias son de T-110); confirmar una `sugerido` se rechaza; quitar por grupo funciona para un operador y confirmar por grupo lo rechaza (`rejected`); devolver una descartada crea el requisito con sus citas literales y el registro, una segunda devolución en la misma versión se rechaza, y en una versión validada también; la versión nueva copia lo devuelto; el hecho de validación trae las cuentas; suite en verde.
- **No tocar:** `proposal/`, `evaluation.py`, el esquema (T-099), las vistas (T-105).
- **Entorno:** cualquier equipo con Docker.

### T-105 · Mostrar las descartadas, las citas repetidas y la revisión por grupos

- **Qué hacer:** plan, "Pantalla": página "Descartadas por el sistema" de la versión (cita literal, documento, página, cláusula, enlace al original, clase, motivo, indicio, estado; casillas y botón "Devolver a la matriz"); línea en la matriz con las cantidades y el enlace; las citas `repetida` ("también en: …") en cada fila; encabezados por cláusula de primer nivel y por tramo con dos o más propuestas, con "Confirmar las N propuestas" y "Quitar las N propuestas", y la página de confirmación previa con las filas y su texto; el origen `filtro` en la cobertura; en la vista de impresión y el PDF, la línea con la cantidad de descartadas y su reparto por motivo (la leyenda de borrador no cambia); aviso "sin sugerencias de consecuencia" en las filas devueltas.
- **Aviso de tareas anteriores:** T-104: una fila corregida vuelve a `propuesto` y entra en los grupos; la confirmación previa del grupo debe marcar las filas corregidas para que el evaluador las vea antes de confirmar.
- **Archivos:** `evaluon/tenders/views/discarded.py`, `evaluon/tenders/views/review.py`, `evaluon/tenders/urls.py`, `evaluon/templates/tenders/discarded.html`, `evaluon/templates/tenders/group_confirm.html`, `evaluon/templates/tenders/matrix.html`, `evaluon/templates/tenders/matrix_print.html`, `evaluon/templates/tenders/coverage.html`, `evaluon/static/tenders/matrix.css`, `tests/tenders/test_discarded_screen.py`, `tests/tenders/test_group_screen.py`.
- **Verificación:** tests con el cliente de pruebas: la lista muestra cada descartada con su texto igual al recorte, motivo e indicio; devolver una cambia su estado y la fila aparece en la matriz; el botón del grupo muestra primero la página con las N filas y recién "Aceptar" aplica; un operador no ve "Confirmar" del grupo; una fila con citas repetidas muestra todas; el PDF y la impresión de un borrador con descartadas llevan la línea y la leyenda "BORRADOR INCOMPLETO" en cada página; ninguna página referencia direcciones externas; suite en verde.
- **No tocar:** los servicios de T-104; `export.py`; `proposal/`.
- **Entorno:** cualquier equipo con Docker.

### T-106 · Medir el filtro, las sugerencias y el respaldo normativo con el caso-00 y ajustarlos

- **Diferida a la revisión con el primer producto (ADR-0024, 2026-10-05).**
- **Qué hacer:** con T-102, T-103, T-109 y T-111 integradas, corrida real del caso-00 (`uso: ajuste`; el Coordinador pasa la lista de `primera_corrida` a `ajuste` antes, si todavía no lo hizo) con el proceso único, el filtro con sus tres destinos y el respaldo normativo; informe: encontrados (con causas, y en especial esperados descartados por el sistema, que deben ser 0, y esperados "a revisión obligatoria" por sugerencia o por tramo pendiente), sobrantes sobre las filas firmes y su proporción con IC, descartadas por motivo y por tramo, unificadas, sobrantes que habría sin el filtro, **sugerencias (cantidad, por motivo de duda, proporción que eran esperados, sobrantes "si fueran firmes"), cuántas con respaldo normativo y cuántas de esas eran esperados, y la muestra de respaldos revisada (el verificador dice si la norma citada exige de verdad esa condición)**, muestra revisada de las descartadas (el verificador completa `muestra-descartadas.md` fuera del repositorio y el informe trae solo cuentas: correctos e incorrectos), cita literal, tiempos por pasada (incluidas `filtro` y `respaldo_normativo`) y por página, extrapolación a 50 páginas (se informa, sin máximo). Si hace falta, **hasta dos rondas de ajuste** (v2 y v3), solo de las instrucciones del filtro y del respaldo y de sus parámetros (`NORM_SUPPORT_MIN_SCORE` incluido, sin bajarlo para que aparezcan respaldos), con una frase general por ronda que no nombre cláusulas, midiendo cada una; ninguna fila plausible se descarta para ajustarse a la lista y la tabla de destinos no se ajusta.
- **Aviso de tareas anteriores:** T-103: antes de medir, regenerar con `--regenerar-resumen` las corridas guardadas del caso-01 y caso-02 y comprobar que los encontrados no cambian respecto de los resúmenes anteriores. T-101: la unificación por omisión solo une textos idénticos normalizados (`dedup.MIN_SIMILARITY=1.0`, `USE_CONTAINMENT=False`); `settings.DEDUP_MIN_SIMILARITY` (0,9) quedó sin uso: retirarlo o alinearlo. Medir cuántas repetidas legítimas quedan sin unir; si se enciende similitud o contención, repetir la batería adversa de `test_dedup.py`. T-102: `Disposition.discard_reason` registra `obligacion_organismo` para los motivos `consecuencia_sancion` y `derecho_posterior` (la fila descartada conserva el exacto); el mínimo de indicio (`MIN_CLUE_WORDS = 4` palabras con contenido) puede mandar a sugerencia descartes legítimos cortos: medir cuántos con el caso-00. T-109: una unidad de norma con cualquier cambio (`modifica`/`deroga`) vigente a la fecha de autorización no da respaldo (anomalía `respaldo_unidad_modificada`), porque la 001 no arma el texto vigente; medir cuántos respaldos se pierden. `consequences.py::render_norm` muestra el texto original de unidades modificadas (tarea aparte). T-125: contar en la medición las sugerencias con anomalía `filtro_comparte_oracion`; la pantalla muestra "El modelo dudó" para ellas (`duda`) aunque las frenó el código: considerar un motivo propio; comprobar con el caso-01 si M-058 y M-063 quedan firmes o como sugerencia.
- **Archivos:** `evaluon/tenders/prompts/matriz-filtro-v2.md` y `matriz-filtro-v3.md`, `matriz-respaldo-v2.md` y `matriz-respaldo-v3.md` (solo si hay ajuste), `evaluon/settings.py` (versión activa en `MATRIX_PROMPT_VERSIONS`, parámetros del filtro y del respaldo), tests de la versión de instrucciones en `tests/tenders/`; corridas en `corpus/casos/caso-00/corridas/` (fuera del repositorio); informe `specs/003-pliego-matriz/verificacion/T-106.md` sin texto del pliego ni de la norma citada más allá de su identificación.
- **Verificación:** el informe con todas las medidas y el estado del tope; esperados descartados por el sistema: 0, o cada uno con su motivo; cuántas rondas se hicieron y qué movió cada una; ningún texto del pliego en el repositorio; suite en verde si hubo cambios de código. Si el tope no se cumple, se informa con la composición de los sobrantes que quedan (a la vista de la muestra) y se pasa a T-107; no se ajusta más.
- **No tocar:** la lista esperada; la regla de emparejamiento; la tabla de destinos; las instrucciones de extracción y de completitud; los casos 01 y 02.
- **Entorno:** MSI con GPU.

### T-107 · Decidir con el responsable el tope, la lista y las sugerencias con lo medido en el caso-00

- **Resuelta por ADR-0024 (2026-10-05):** el tope de sobrantes pasa a informativo hasta el piloto; las listas no se amplían; las sugerencias quedan como están. Se vuelve a decidir antes del piloto, con lo que la Comisión haya visto en uso.
- **Qué hacer:** el Coordinador lleva al responsable el informe de T-106 (si el tope se cumplió o cuántos sobrantes plausibles quedan y de qué clase, con tabla de ejemplos reales; **cuántas sugerencias hay y qué proporción eran esperados, cuántos esperados quedaron como sugerencia en lugar de firmes, y cuántas sugerencias tuvieron respaldo normativo y cuántas de esas eran esperados, con ejemplos reales sí/no por fila**: la spec no limita cuántos esperados pueden quedar como sugerencia y esta tarea es donde se mira si la sección es útil o un depósito, y si conviene o no la promoción automática por respaldo, que hoy no existe) y registra su decisión: seguir con las listas y el tope como están; revisar con la Comisión si las condiciones plausibles son requisitos y ampliar las listas esperadas de los tres casos (antes de correr 01 y 02, y sin mirar sus sobrantes: la ampliación de 01 y 02 se hace solo desde el texto, como la original); o cambiar el tope. Anota la decisión en `specs/003-pliego-matriz/verificacion/T-107.md` y, si cambia la spec, la enmienda se hace por el camino de la spec, no acá.
- **Archivos:** `specs/003-pliego-matriz/verificacion/T-107.md`; las listas esperadas (fuera del repositorio) solo si el responsable decide ampliarlas.
- **Verificación:** la decisión del responsable anotada con fecha; si se amplían listas, la huella nueva y su visto bueno; sin texto del pliego en el repositorio.
- **No tocar:** el sistema y las instrucciones.
- **Entorno:** datos.

### T-108 · Medir la aceptación del proceso con filtro y sugerencias con los casos 01 y 02, y REQ-031 con los casos 03 y 04

- **ADR-0024 (2026-10-05):** se mide **una sola vez, sin rondas de ajuste**, con las instrucciones actuales (sin esperar a T-106). Los sobrantes se informan y no bloquean. Un faltante o un error de circulares que haga perder un requisito se corrige; lo demás va a la revisión con el primer producto.
- **Qué hacer:** con las instrucciones fijas después de T-106 y T-120 y la decisión de T-107, medir los casos 01 y 02 solo con el proceso único (la medición de T-094 se hizo antes del filtro y con niveles; esta es la medida de aceptación): `medir_matriz --verificar-esperada` y la corrida de cada caso. Medidas: 100 % de encontrados (con "a revisión obligatoria": tramos pendientes y sugerencias, informados aparte), esperados descartados por el sistema (0), sobrantes hasta el tope sobre las filas firmes, cita literal 100 %, las filas descartadas con la muestra revisada de sus motivos, **las sugerencias (cuántas, proporción que eran esperados, cuántas con respaldo normativo y cuántas de esas eran esperados; REQ-035 y REQ-036)**, tiempos por pliego y por página (el caso-01 tiene 52 páginas; se informan, sin máximo) y memoria de video. Informe sin texto del pliego; un faltante o un tope no cumplido bloquea la aceptación y se informa con su causa, sin ajustar nada.
- **Aviso de tareas anteriores:** T-127: la marca de revisión obligatoria de una supresión sin frase se lee de las anomalías de `version.run`; una versión nueva de la matriz sin propuesta propia no la muestra. Resolver antes del piloto (tarea aparte). 6: con la cadena de circulares, observar en el caso-03 (cadena 4 → 5 → 6) que el orden por fecha y el texto vigente sean correctos; en una cadena cerrada por una supresión, la supresión aparece dos veces (como eslabón y en la línea final "Sin efecto desde …"); la modificación posterior a una supresión tiene test solo en pantalla. T-126: con la cadena de circulares, observar en el caso-03 (cadena 4 → 5 → 6) que el orden por fecha y el texto vigente sean correctos; en una cadena cerrada por una supresión, la supresión aparece dos veces (como eslabón y en la línea final "Sin efecto desde …"); la modificación posterior a una supresión tiene test solo en pantalla.
- **Archivos:** corridas en `corpus/casos/caso-0N/corridas/` (fuera del repositorio); `specs/003-pliego-matriz/verificacion/T-108.md`.
- **Verificación:** el informe con todas las medidas, su intervalo y el resultado de aceptación; ningún texto del pliego en el repositorio.
- **REQ-031 (decisión del 2026-10-04):** la aceptación de REQ-031 se mide a ciegas, una sola vez, con los casos 03 y 04 (el caso-01 pasó a ajuste y no cuenta para la aceptación de REQ-031), con la medición automática por fila de T-117: filas de circular esperadas, cumplimiento de los cuatro puntos (efecto, texto original, texto vigente, documento y fecha), fuentes ajenas y tiempos. Sus listas, ya preparadas solo desde el texto, necesitan el bloque `circular`: si no lo tienen, el Coordinador lo agrega solo desde el texto antes de correr, sin mirar ninguna salida del sistema. Un fallo bloquea y se informa con su causa, sin ajustar.
- **No tocar:** instrucciones, parámetros, listas esperadas (salvo lo decidido en T-107 y el bloque `circular` de 03 y 04).
- **Entorno:** MSI con GPU, sin otra carga.

### T-109 · Buscar el respaldo normativo de cada sugerencia, sin que nunca la descarte

- **Qué hacer:** `proposal/norm_support.py` (plan, "Consulta normativa"): para cada requisito en estado `sugerido`, pregunta fija con el fragmento (recortado en límite de oración a `NORM_SUPPORT_QUERY_MAX_CHARS`); `retrieve` y `select_units` de la 001 con la fecha de autorización del procedimiento, solo unidades de normas (no considerandos, dictámenes ni respuestas de la Comisión) y hasta `NORM_SUPPORT_MAX_UNITS`; sin régimen a esa fecha, sin consulta y con la anomalía `sin_regimen`; un pedido corto a `generation_batch` por sugerencia con alias `N1…`, por unidad `exige` (`si` o `no`) y `cita` literal, con salida estructurada obligada; respaldo solo si el puntaje es de al menos `NORM_SUPPORT_MIN_SCORE`, `exige` es `si` y la cita se halla palabra por palabra en el texto de la unidad en la base (`quotes.py`); hasta dos respaldos por sugerencia, en `tenders_norm_support`; registro de cada consulta en `tenders_run_step` (`respaldo_normativo`: pregunta, unidades, puntajes, respuesta, versión de la normativa); cuentas de respaldos y fallas en `counts`; la pasada en `run.py` después del filtro y antes de las reglas de tablas; `NORM_SUPPORT_ENABLED` en falso saltea la pasada. Instrucciones `prompts/matriz-respaldo-v1.md` con ejemplos sintéticos. La pasada solo inserta respaldos: no cambia el estado de ninguna fila.
- **Aviso de tareas anteriores:** T-112: sumar tests fijos de la pantalla con `doubt.evidence` en el formato real de T-102 (`{segment, char_start, char_end, text}`) y en `None`; los de T-112 usan texto plano.
- **Archivos:** `evaluon/tenders/proposal/norm_support.py`, `evaluon/tenders/proposal/run.py`, `evaluon/tenders/prompts/matriz-respaldo-v1.md`, `tests/tenders/test_norm_support.py`.
- **Verificación:** tests con las normas de prueba de la 001 y los dobles de embeddings, reranker y motor: una sugerencia que una norma vigente exige (por ejemplo, una garantía de mantenimiento de oferta sintética) recibe respaldo con la norma, la ruta, el puntaje y la cita literal igual al recorte de la unidad; con fecha de autorización anterior al 2023-01-02 se usa la 297/03 y desde esa fecha la 247/2022; un fragmento que nombra a ARCA recupera una unidad de la norma de AFIP (ADR-0010); una sugerencia que ninguna norma exige queda sin respaldo y **su estado no cambia**; con `exige` `no`, puntaje bajo, alias inexistente o cita que no está en la unidad, no hay respaldo; sin régimen a la fecha no hay consulta y la sugerencia sigue; una falla de la recuperación o del pedido deja la sugerencia sin respaldo con la anomalía; ningún resultado de la consulta cambia el estado de una fila (test sobre todas las salidas posibles); no se consulta para filas firmes, técnicas ni descartadas; la consulta se registra con la versión de la normativa; una prueba busca las anclas de la lista del caso-00 en las instrucciones y los ejemplos y falla si aparece alguna de 5 palabras; suite en verde.
- **No tocar:** `evaluon/queries/` y `evaluon/norms/` (se usan como están); `filter.py`, `extraction.py`, `completeness.py`, `circulars.py`; el esquema (T-099); vistas.
- **Entorno:** cualquier equipo con Docker.

### T-110 · Decidir las sugerencias: pasar a requisito o quitar, una por una o por grupo, y bloquear la validación

- **Qué hacer:** plan, "Qué hace la Comisión con una sugerencia": `services/suggestions.py` con `accept_suggestion` (operador o evaluador: la fila pasa de `sugerido` a `propuesto`, fila `aceptar_sugerencia` en `tenders_requirement_change` con el motivo de la duda y el respaldo como estaban, quién y cuándo, y hecho `requirement_change`) y `accept_suggestions_group` (misma clave de grupo que REQ-034, solo las filas `sugerido` del grupo, en una transacción, una fila de historial por requisito con `via_grupo`); quitar una sugerencia (individual y `remove_group` sobre las `sugerido`) con la función de quitar de `review.py`, extendida para aceptar el estado `sugerido`; restituir una sugerencia quitada la deja `propuesto`; confirmar una fila `sugerido` se rechaza ("pasala primero a requisito"); rechazo en una versión validada; en `services/validation.py`, `validate` se rechaza si queda alguna fila `sugerido`, diciendo cuántas y en qué grupos, y el hecho `matrix_validation` suma las cuentas de sugerencias aceptadas y quitadas; abrir una versión nueva copia el requisito que vino de una sugerencia con su `doubt_reason` y sus respaldos (`tenders_norm_support`).
- **Aviso de tareas anteriores:** T-104 y T-100: `services/validation.py::_copy` copia `doubt_reason`, `doubt` y `restored_from` sin test que lo cubra (agregarlo), y la versión nueva no copia `process` (copiarlo y testearlo).
- **Archivos:** `evaluon/tenders/services/suggestions.py`, `evaluon/tenders/services/review.py`, `evaluon/tenders/services/validation.py`, `tests/tenders/test_suggestions.py`, `tests/tenders/test_validation.py`.
- **Verificación:** tests: pasar a requisito una sugerencia deja `propuesto`, la fila de historial con quién, cuándo, motivo de la duda y respaldo; un grupo de cinco sugerencias de una cláusula pasa a requisito con cinco filas de historial iguales a las de la decisión individual, `sec-i/1` no alcanza a `sec-i/11` y las filas ya decididas no se tocan; quitar un grupo de sugerencias funciona; un operador puede pasar a requisito y quitar; confirmar una sugerencia sin pasarla a requisito se rechaza (también un evaluador); validar con una sola sugerencia sin decidir se rechaza con el mensaje de cuántas quedan, y con todas decididas se valida; descartar un borrador con sugerencias sin decidir se permite; nada de esto se puede en una versión validada, en la función ni en la base; la versión nueva copia el requisito venido de una sugerencia con su motivo y su respaldo; los tests de T-082 y T-104 siguen pasando; suite en verde.
- **No tocar:** `proposal/`, `evaluation.py`, el esquema (T-099), las vistas (T-112); `confirm_group` de T-104 (que ya ignora las `sugerido`).
- **Entorno:** cualquier equipo con Docker.

### T-111 · Medir las sugerencias y el respaldo normativo: a revisión obligatoria e informe

- **Qué hacer:** plan, "Cambios en `medir_matriz`": orden de emparejamiento firmes → sugerencias → descartadas (cualquiera de las citas de la fila, como en T-103); esperado sin pareja firme con pareja en una sugerencia: "a revisión obligatoria" con causa `sugerencia`, en el numerador de la aceptación, informado aparte con su cantidad y sus claves `M-NNN` (misma forma que `tramo_pendiente`, T-095); un esperado con pareja en una descartada y en ninguna sugerencia sigue siendo faltante `descartado_por_el_sistema`; informe de sugerencias: cantidad, por motivo de duda y por tramo, proporción que eran esperados con IC de Wilson, proporción de los esperados que quedaron como sugerencia, cuántas tuvieron respaldo normativo y cuántas de esas eran esperados (con proporción), sobrantes "si las sugerencias fueran firmes" (informativo), y muestra de sugerencias con cita, motivo y respaldo en `resumen.md` y en `muestra-sugerencias.md` locales (con una columna para que el verificador diga si la sugerencia y el respaldo eran correctos); `resumen-publico.md` solo con cuentas, claves, motivos y la identificación de la norma, sin texto del pliego ni de la norma; `timing_summary` suma `respaldo_normativo`; `--regenerar-resumen` sigue funcionando con propuestas sin sugerencias.
- **Archivos:** `evaluon/tenders/evaluation.py`, `evaluon/tenders/management/commands/medir_matriz.py`, `tests/tenders/test_evaluation.py`, `tests/tenders/fixtures/` (propuestas sintéticas con sugerencias y respaldos).
- **Verificación:** tests con datos sintéticos insertados en la base: un esperado cuya cita está en una sugerencia cuenta "a revisión obligatoria" (causa `sugerencia`) y suma a la aceptación, sin ser sobrante ni faltante; uno con pareja firme y otra en una sugerencia empareja con la firme; uno en una descartada sigue siendo faltante con su causa; con 3 sugerencias, 2 con pareja esperada, 1 con respaldo y esa esperada, el informe da 3, 2 de 3, 1 con respaldo y 1 de 1; las sugerencias no cuentan en el tope; el tope informativo "con sugerencias como firmes" las suma; `resumen-publico.md` no contiene el texto de ninguna cita, indicio ni norma (se comprueba buscando cada texto); una corrida sin sugerencias da las medidas de siempre; suite en verde.
- **No tocar:** la propuesta (`proposal/`); la lista esperada; la regla de emparejamiento salvo el orden. Espera a T-103 (mismo archivo).
- **Entorno:** cualquier equipo con Docker.

### T-112 · Mostrar la sección de sugerencias con su respaldo en la pantalla y en la impresión

- **Qué hacer:** plan, "Pantalla e impresión" de las sugerencias: en la página de la matriz, la sección "Sugerencias de condición" después de "Pendiente de revisión" y antes de los requisitos firmes, con la leyenda de que no se valida con sugerencias sin decidir; cada sugerencia con su cita literal, documento, página, cláusula y enlace al original, el motivo de la duda (frase fija por motivo y el indicio literal, si hay), el respaldo normativo (norma, ruta, vigencia, cita literal, enlace a la unidad) o "Sin respaldo normativo encontrado: no es motivo para quitarla", y los botones "Pasar a requisito" y "Quitar"; primero las que tienen respaldo, marcadas "la norma aplicable la exige"; encabezados por cláusula y tramo con "Pasar a requisito las N" y "Quitar las N" y la página de confirmación previa con las filas y su texto (reutiliza `group_confirm.html`); "sugerencias sin decidir" en el resumen; el estado de cada fila en la cobertura; en la vista de impresión y el PDF, la sección "Sugerencias de condición sin decidir" justo antes de los requisitos, con cita, ubicación, motivo y respaldo (la leyenda "BORRADOR INCOMPLETO" no cambia; una versión validada no tiene la sección); en un requisito que viene de una sugerencia, "Pasó de sugerencia el DD/MM/AAAA por <persona>" y su respaldo.
- **Aviso de tareas anteriores:** T-110: la pantalla debe mostrar los mismos grupos que usa `validation._groups`; el test del mensaje de rechazo de validación no fija la cantidad de sugerencias pendientes (reforzarlo si se toca). T-105: `templatetags/review_tags.py` usa privados de `matrix_page` (`_Pages`, `_place`, `_quote_rows`) e importa `views/review`; al tocar esa zona, exponerlos con nombre público y mover `clause_of`, `proposed_entries`, `in_group` a `services/`.
- **Archivos:** `evaluon/tenders/views/suggestions.py`, `evaluon/tenders/views/review.py`, `evaluon/tenders/urls.py`, `evaluon/templates/tenders/matrix.html`, `evaluon/templates/tenders/matrix_print.html`, `evaluon/templates/tenders/coverage.html`, `evaluon/templates/tenders/group_confirm.html`, `evaluon/static/tenders/matrix.css`, `tests/tenders/test_suggestions_screen.py`.
- **Verificación:** tests con el cliente de pruebas y filas sintéticas: la sección muestra cada sugerencia con su texto igual al recorte, su motivo y, si la tiene, el respaldo con la cita literal de la norma y su enlace; las que tienen respaldo van primero; una sin respaldo muestra el aviso de que no es motivo para quitarla; "Pasar a requisito" y "Quitar" cambian el estado y la fila aparece donde corresponde; el botón del grupo muestra primero la página con las N filas y recién "Aceptar" aplica; el botón "Validar" informa cuántas sugerencias faltan decidir; el PDF y la impresión de un borrador con sugerencias llevan la sección y la leyenda "BORRADOR INCOMPLETO" en cada página; una versión validada no tiene la sección y el requisito que vino de una sugerencia muestra su origen; ninguna página referencia direcciones externas; suite en verde.
- **No tocar:** los servicios de T-104 y T-110; `export.py`; `proposal/`.
- **Entorno:** cualquier equipo con Docker.

### Enmienda del 2026-10-04: rediseño de la pasada de circulares (T-113 a T-120)

Plan: sección "Rediseño de la pasada de circulares (2026-10-04)" de `plan.md`; ADR-0023 (aceptado); diagnóstico en `verificacion/T-113-diagnostico.md`. Orden: T-113 (entrega 1) y T-114 (esquema) pueden ir a la vez; T-115 (entrega 2) y T-116 (pantalla) después de las dos; T-117 (medición por fila) en paralelo con ellas; los datos T-118 y T-119 después de T-117; T-120 al final, con la GPU.

**Conflictos de archivo con tareas en curso o pendientes** (el Coordinador integra en secuencia y corre la suite después de cada integración):

- `proposal/run.py` (T-101 → T-102 → T-109): T-113 toca solo `_save_circulars` (persistir la referencia al original). T-115 no lo toca salvo que el cambio de entrada de `Processor.process` lo obligue. Integrar T-113 antes o después de T-101, no a medias; el conflicto es textual y acotado.
- `evaluation.py` y `medir_matriz.py` (T-103 → T-111): T-117 va después de T-111.
- `services/validation.py` y `tests/tenders/test_validation.py` (T-110): T-114 toca solo `_copy` (copiar los tres campos nuevos de la fuente). Preferible integrar T-114 antes que T-110; si T-110 ya está en curso, aviso por `avisos/T-110.md`.
- Vistas y plantillas (`matrix.html`, `matrix_print.html`, `coverage.html`, `matrix.css`) (T-105 → T-112): T-116 va después de las dos.
- `proposal/circulars.py`: T-113 → T-115 (cadena). T-098 ya está integrada.
- `models.py`, `migrations/`, `settings.py`: solo T-114 (un solo agente de esquema).
- GPU: T-120 corre de a una con T-106 y T-108.

### T-113 · Pasada de circulares, entrega 1: unidades de cambio aplicadas por clave, sin modelo

- **Qué hacer:** plan, "Entrega 1, sin modelo". `proposal/circular_units.py`: partir cada circular en unidades de cambio (cláusula numerada con sus tramos, apartado bajo un encabezado romano, par "Donde dice / Debe decir" con los tramos no ubicados que caen entre sus rótulos, tramo suelto); detectar el tipo por la lista de verbos; resolver el objetivo por clave (cláusula con número normalizado y límite de nivel, anexo por número o título con las cláusulas que lo piden, renglón, texto anterior) y aplicar el efecto a **todas** las citas afectadas, una fuente por cita; unidad de datos del trámite (líneas cortas rótulo y valor, sin marcadores de obligación): tramos `descartado` con motivo `dato_procedimiento` y, si reemplaza un anexo sin requisitos que el pliego menciona, una fuente `modifica` por cita que lo menciona con el bloque entero como vigente; clave inexistente con verbo de agregar: requisito nuevo de origen `circular`; todo lo demás, al flujo actual como respaldo, restringido a esos cambios. Corregir `named_annexes` para que "Anexo N de la/del … Disposición/Resolución/Decreto/Ley/Circular/Nota/Acuerdo" no sea un anexo del pliego. Cada unidad deja un pedido en `tenders_run_step` (`circulares`) sin llamada al modelo, con sus tramos, tipo, objetivo, citas resueltas y fuentes. `Source` suma el original opcional (tramo del anexo y posiciones). **Al final**, con T-114 integrada, `_save_circulars` persiste esa referencia; si T-114 no llegó, se entrega todo lo demás y la referencia queda pendiente, informándolo.
- **Archivos:** `evaluon/tenders/proposal/circular_units.py`, `evaluon/tenders/proposal/circulars.py`, `evaluon/tenders/proposal/run.py` (solo `_save_circulars`), `tests/tenders/test_circular_units.py`, `tests/tenders/test_circulars.py`.
- **Verificación:** tests con textos inventados que reproducen cada forma y fallan sin el arreglo: una cláusula con dos citas reemplazada da una fuente en cada una; "el Anexo X no es requisito" da `suprime` en las citas del anexo y en la cláusula que lo pide (y no en una cláusula que lo menciona de pasada); un apartado de líneas de fecha, hora y lugar no crea requisitos, descarta sus tramos con `dato_procedimiento` y, si reemplaza un anexo sin requisitos, da una sola fuente `modifica` por cada cita que lo menciona (con el bloque entero como vigente, no el de la última línea); "Donde dice" y "Debe decir" en tramos separados dan un solo `modifica`, el texto viejo no produce efecto y ningún tramo del par queda `no_ubicado`; "Anexo IV de la Disposición N° …" no agrega citas aludidas; una cita común a varios renglones no recibe efecto si la unidad no nombra la cláusula ni el renglón; el ejemplo de la spec (16 GB a 32 GB) por renglón y por texto anterior; una clave inexistente o un texto anterior ambiguo van al respaldo y no se pierden; todo tramo de circular queda con disposición; una circular sin encabezados se comporta como hoy; una prueba busca las anclas de los casos 00, 01 y 02 en tests y fixtures y falla si aparece alguna de 5 palabras; suite en verde.
- **No tocar:** `medir_matriz` y `evaluation.py`; la lista esperada; `plan.md`; modelos y migraciones (T-114); las instrucciones `matriz-circulares-v2.md`; el resto de `run.py`.
- **Entorno:** cualquier equipo con Docker.

### T-114 · Crear el campo de original en un anexo, el pedido de extracción de cambios y los parámetros de circulares

- **Qué hacer:** plan, "Campo nuevo y migración". Una migración: `tenders_requirement_source` suma `original_segment` (clave al tramo), `original_char_start` y `original_char_end`, opcionales, los tres juntos o ninguno (restricción), y el trigger de inmutabilidad de una versión validada los cubre (adaptar el trigger de T-067 sin perder sus pruebas); `tenders_run_step.pass_name` suma `circulares_cambios`. `settings.py`: `CIRCULAR_EXTRACTION_ENABLED` (verdadero), `CIRCULAR_EXTRACTION_REPEATS` (1) y la versión de instrucciones `circulares_cambios` en `MATRIX_PROMPT_VERSIONS`. `services/validation.py::_copy` copia los tres campos nuevos de la fuente. Una sola tarea de esquema: ninguna otra la toca.
- **Archivos:** `evaluon/tenders/models.py`, `evaluon/tenders/migrations/` (una nueva), `evaluon/settings.py`, `evaluon/tenders/services/validation.py` (solo `_copy`), `tests/tenders/test_models.py`, `tests/tenders/test_validation.py`.
- **Verificación:** `migrate` sobre base vacía y `migrate --check`; tests: una fuente sin los campos nuevos sigue válida (datos de T-083 y T-098); una con solo uno o dos de los tres se rechaza; una con los tres y posiciones coherentes se acepta; UPDATE sobre los campos de una fuente de una versión validada rechazado por la base; `pass_name` `circulares_cambios` se acepta y uno inventado no; una versión nueva copia la referencia al original; los parámetros existen con sus valores por omisión; suite en verde.
- **No tocar:** `proposal/`, vistas, `evaluation.py`; el resto de `validation.py`.
- **Entorno:** cualquier equipo con Docker.

### T-115 · Pasada de circulares, entrega 2: el modelo extrae la lista de cambios donde no hay clave

- **Qué hacer:** plan, "Entrega 2, con modelo". `proposal/circular_changes.py`: pedido por unidad sin citas del pliego, con salida estructurada obligada (`cambios` con `tipo`, `objetivo`, `referencia`, `texto_anterior`, `texto_nuevo`), citas literales de la unidad verificadas con reintento único y registro en `tenders_run_step` (`circulares_cambios`); lo que tiene objetivo resoluble pasa por la aplicación por clave de T-113; lo demás, al flujo actual restringido a esos cambios; repetición según `CIRCULAR_EXTRACTION_REPEATS` con comparación: los cambios iguales se aceptan, los distintos quedan no estables, no se aplican en firme y van al respaldo con la anomalía; `CIRCULAR_EXTRACTION_ENABLED` en falso deja la entrega 1; instrucciones `prompts/matriz-circulares-v3.md` con ejemplos sintéticos de otro objeto y otras cifras.
- **Aviso de tareas anteriores:** T-114: la base no garantiza que `original_segment` sea de la misma lectura/versión que la fuente; el servicio que lo escribe debe comprobarlo (con test). T-113: agregar un test de un par Donde dice/Debe decir aplicado con un tramo `no_ubicado` que sigue pendiente por el motivo de la lectura (REQ-028); los pasos `sin_modelo` de las unidades no llevan `messages` en `RunStep.request`.
- **Archivos:** `evaluon/tenders/proposal/circular_changes.py`, `evaluon/tenders/proposal/circulars.py`, `evaluon/tenders/prompts/matriz-circulares-v3.md`, `tests/tenders/test_circular_changes.py`.
- **Verificación:** tests con el doble del motor: una salida con un cambio de objetivo cláusula se aplica a todas sus citas; un cambio sin objetivo va al respaldo; una cita literal que no está en la unidad se reintenta y, si sigue sin estar, el cambio no se aplica y queda registrado; dos repeticiones iguales se aceptan y dos distintas dejan el cambio sin aplicar con la anomalía; con la extracción apagada, el resultado es el de T-113; el pedido registra modelo, parámetros, versión de instrucciones y la unidad; una prueba busca las anclas de los casos 00, 01 y 02 en las instrucciones y los ejemplos y falla si aparece alguna de 5 palabras; suite en verde.
- **No tocar:** `circular_units.py` salvo importar sus funciones (si hace falta cambiarlas, aviso por `avisos/`); `run.py` salvo lo imprescindible; modelos y migraciones; las instrucciones de las demás pasadas.
- **Entorno:** cualquier equipo con Docker.

### T-116 · Mostrar y imprimir el original en el anexo, el cambio agrupado y el requisito agregado por una circular

- **Qué hacer:** plan, "Pantalla e impresión (T-116)". En la matriz y en la vista de impresión (y el PDF): una fuente con `original_segment` muestra como "Texto original" el tramo del anexo, con documento, página y enlace al original en la página, y como vigente el texto de la circular con documento y fecha; el cambio de una circular sobre varias citas del mismo requisito se muestra una vez; un requisito de origen `circular` muestra "Agregado por <documento> del <fecha>", tomados del tramo de su cita; el historial "modificada por …" no se repite por línea. Sin migración. La leyenda de borrador no cambia.
- **Aviso de tareas anteriores:** T-114: la base no garantiza que `original_segment` sea de la misma lectura/versión que la fuente; validarlo al mostrar o al escribir. T-112: reutilizar los parciales `_support.html` y `_suggestion*.html`; los alias privados de `matrix_page` (`_Pages`, `_place`, `_quote_rows`) siguen vivos: si se tocan esos importadores, pasarlos a los nombres públicos; sumar un test con `enforce_csrf_checks`.
- **Archivos:** `evaluon/tenders/views/matrix.py`, `evaluon/templates/tenders/matrix.html`, `evaluon/templates/tenders/matrix_print.html`, `evaluon/templates/tenders/coverage.html` (solo si hace falta), `evaluon/static/tenders/matrix.css`, `tests/tenders/test_circular_screen.py`.
- **Verificación:** tests con el cliente de pruebas y datos sintéticos: una fuente con el original en un anexo muestra los dos textos iguales a su recorte, con su documento y fecha; dos fuentes del mismo cambio sobre un requisito se muestran una vez; un requisito `circular` muestra documento y fecha de su cita; la vista de impresión y el PDF de un borrador con esos casos llevan la información y la leyenda "BORRADOR INCOMPLETO" en cada página; una versión de antes de esta tarea (sin los campos nuevos) se sigue viendo igual; ninguna página referencia direcciones externas; suite en verde.
- **No tocar:** `proposal/`, servicios, el esquema (T-114), `export.py`.
- **Entorno:** cualquier equipo con Docker.

### T-117 · Medir REQ-031 por fila en `medir_matriz`: documento, fecha, texto original y vigente

- **Qué hacer:** plan, "Cambios en `medir_matriz` (T-117)". En `evaluation.py` y el comando: bloque opcional `circular` en la lista esperada (`documento`, `fecha`, `efecto`, `ancla_original`, `ancla_vigente`) comprobado por `--verificar-esperada`; una lista con `alcance: circulares` mide solo REQ-031 (sin las demás medidas) para los casos de ajuste que no tienen la lista completa; medida por fila de los cuatro puntos (fuente con el efecto esperado; el original mostrado contiene el ancla original; el vigente contiene el ancla vigente; documento y fecha esperados), con la regla de cobertura de la mitad del ancla; `agrega`: fila de origen `circular` con cita en el documento y fecha esperados; ruido de circulares (fuentes en filas sin esperado de circular, por documento y por fila; requisitos `circular` sin esperado); informe en `resumen.md` y `resumen-publico.md` (solo cuentas, claves `M-NNN` y títulos de documentos; sin texto); las corridas sin bloque `circular` dan las medidas de siempre; `--regenerar-resumen` sigue funcionando.
- **Archivos:** `evaluon/tenders/evaluation.py`, `evaluon/tenders/management/commands/medir_matriz.py`, `tests/tenders/test_evaluation.py`, `tests/tenders/fixtures/` (listas y propuestas sintéticas con circulares).
- **Verificación:** tests con datos sintéticos en la base: una fila de circular con los cuatro puntos cumple; con el texto original equivocado falla solo el punto 2; con fecha distinta falla solo el punto 4; una fila sin fuente falla el punto 1; una fuente en una fila sin esperado cuenta como ruido, por documento; una lista con `alcance: circulares` no calcula encontrados ni sobrantes del resto; `--verificar-esperada` rechaza un bloque cuyo ancla no está en la lectura; `resumen-publico.md` no contiene el texto de ninguna ancla ni cita (se comprueba buscando cada una); una lista sin bloques da las medidas de antes; suite en verde.
- **No tocar:** la propuesta (`proposal/`); la regla de emparejamiento; las listas esperadas existentes. Espera a T-111 (mismo archivo).
- **Entorno:** cualquier equipo con Docker.

### T-118 · Cargar los casos 05 y 06 y preparar sus listas esperadas de circulares

- **Qué hacer:** el Coordinador (datos, sin código), con el usuario `desarrollo`: carga los documentos de los casos 05 (A0KJ000000-0008-LPU24, precintos, circulares con respuestas a consultas) y 06 (A0PC000000-0007-LPU26, bases online, circular aclaratoria) en `corpus/casos/caso-05/` y `caso-06/` (fuera del repositorio, material público), con su fecha y tipo de documento; escribe `matriz-esperada.yaml` de cada uno con `alcance: circulares` y `uso: ajuste`, leyendo solo el texto, con una entrada por fila que una circular o respuesta cambia, aclara, suprime o agrega y su bloque `circular`. Los casos 03 y 04 no se tocan ni se miran.
- **Aviso de tareas anteriores:** T-117: cada circular citada en los bloques `circulares` debe estar cargada en el procedimiento, o la lista debe declarar `cargado: false` en ese documento; si no, `--verificar-esperada` y la medición bloquean. Correr `--verificar-esperada` en 01, 05 y 06 antes de T-120.
- **Archivos:** `corpus/casos/caso-05/` y `corpus/casos/caso-06/` (fuera del repositorio); en el repositorio, solo la fila de esta tabla y `specs/003-pliego-matriz/verificacion/T-118.md` con cuentas, sin texto.
- **Verificación:** los archivos se leen como YAML; `medir_matriz --verificar-esperada` los acepta (anclas y documentos existen en la lectura); la verificación anota cuántos documentos, circulares y filas esperadas hay por caso, sin texto del pliego.
- **No tocar:** el sistema; los casos 03 y 04.
- **Entorno:** datos.

### T-119 · Actualizar la lista esperada del caso-01 con las filas que las circulares afectan

- **Qué hacer:** el Coordinador (datos, sin código): actualiza `corpus/casos/caso-01/esperado/matriz-esperada.yaml` (fuera del repositorio) con el bloque `circular` de cada fila afectada por las dos circulares, leyendo solo el texto (no una salida del sistema nueva); las filas de un anexo que una circular suprime (las del Anexo VI) cuentan como afectadas y esperadas junto con la que exige presentarlo (decisión 5 del 2026-10-04); suma la fila de la visita con su cita en el anexo original y las del par "Donde dice / Debe decir" y la fila que agrega la circular 2. Nueva huella y registro del cambio.
- **Archivos:** `corpus/casos/caso-01/esperado/matriz-esperada.yaml` (fuera del repositorio); `specs/003-pliego-matriz/verificacion/T-119.md` con cuentas y claves, sin texto.
- **Verificación:** `medir_matriz --verificar-esperada` acepta la lista; la verificación informa cuántas filas de circular se esperaban por circular y la huella nueva; sin texto del pliego en el repositorio.
- **No tocar:** el sistema; lo que no sea el bloque `circular` y las filas afectadas por una circular.
- **Entorno:** datos.

### T-120 · Medir y ajustar la pasada de circulares con los casos 01, 05 y 06, con estabilidad

- **Qué hacer:** con T-113, T-115, T-117, T-118 y T-119 integradas, corridas reales, de a una, con el modelo, sobre los casos 01, 05 y 06 (`uso: ajuste`; los casos 03 y 04 no se miran). Primero solo la entrega 1 (`CIRCULAR_EXTRACTION_ENABLED` en falso) y después con la entrega 2. Informe con la medición por fila de T-117 (cuatro puntos, por circular y por caso), fuentes ajenas (la meta es 0 en las filas técnicas), requisitos `circular` de más, tramos de circular con disposición, cuántos cambios se resolvieron por clave, cuántos por el modelo y cuántos fueron al respaldo, pedidos, tiempo y tokens de la pasada de circulares frente a los 432 s y 836.000 medidos. **Estabilidad:** la extracción con el modelo se repite 3 veces sobre el caso-01 y se informa si los cambios y las fuentes resultantes son los mismos. Hasta dos rondas de ajuste, solo de las instrucciones `matriz-circulares-v3.md` (v4 y v5) y de las constantes de `circular_units.py` (línea corta de las listas, verbos), con una frase general por ronda que no nombre cláusulas, midiendo cada una.
- **Aviso de tareas anteriores:** T-116: con dos fuentes `modifica` de circulares distintas sobre la misma cita, la pantalla muestra solo la última como vigente y la anterior no aparece; observar con la cadena del caso-01 y consultar al responsable si debe verse la cadena completa. T-124: el umbral `SIMILAR_SENTENCE = 0.7` es sensible (una pasiva reformulada da 0,69 y queda firme; una oración nueva larga con inicio común queda sugerencia); calibrarlo con los casos de ajuste y sumar un test de que una oración nueva con sujeto y verbo en común no es sugerencia. Dos circulares con el mismo par dan un requisito por circular. Un anexo único de título más largo que contiene las palabras se toma como original. T-127: la marca "A revisión obligatoria" de una supresión sin frase explícita (anomalía `circular_supresion_sin_frase`, `review_required`) no cuenta en la medición como "a revisión obligatoria": contarla aparte al medir, en especial el caso-06. T-128: una aclaración de cláusula o de anexo sin texto anterior se aplica a todas sus citas (decisión del responsable del 2026-10-05); un `suprime` por clave sin frase explícita queda `aclara` con la marca de revisión obligatoria. Efecto previo que se mantiene: un `suprime` con frase y sin texto anterior alcanza todas las citas de la cláusula; observarlo al medir. T-129: al medir, comprobar que la supresión del caso-01 ("se dispone la eliminación de la subcláusula…", M-025/M-026) queda firme (esa forma exacta no tiene test) y contar las fuentes ajenas que agrega la aclaración de renglón en filas técnicas. Riesgo acotado: objetos genéricos ("puntos", "ítems") pueden dejar pasar "supresión de puntos de venta"; un `suprime` del modelo con frase nominal queda firme sin revisión.
- **Archivos:** `evaluon/tenders/prompts/matriz-circulares-v4.md` y `v5.md` (solo si hay ajuste), `evaluon/tenders/proposal/circular_units.py` (solo constantes y listas de verbos), `evaluon/settings.py` (versión activa en `MATRIX_PROMPT_VERSIONS`), tests de la versión en `tests/tenders/`; corridas en `corpus/casos/caso-0N/corridas/` (fuera del repositorio); `specs/003-pliego-matriz/verificacion/T-120.md` sin texto del pliego ni de las circulares.
- **Verificación:** el informe con todas las medidas; REQ-031 cumplido en el caso-01 (todas sus filas de circular en los cuatro puntos) y las cuentas de 05 y 06; estabilidad de las 3 repeticiones; cuántas rondas se hicieron y qué movió cada una; ningún texto del pliego en el repositorio; suite en verde si hubo cambios de código. Si no se cumple, se informa con la causa y se pasa al Coordinador; no se ajusta más.
- **No tocar:** las listas esperadas; la regla de emparejamiento; los casos 03 y 04; las instrucciones de las demás pasadas.
- **Entorno:** MSI con GPU, sin otra carga.

### T-121 · Corregir el consumo de memoria de la medición

- **Qué hacer:** la medición real del caso-01 del 2026-10-04 (corrida 14) murió por falta de memoria (14,9 GB): `evaluation.py::_rows` salteaba la precarga y cada cita cargaba su propia lectura. Precargar las citas ordenadas con su tramo y lectura compartida, sin cambiar resultados.
- **Archivos:** `evaluon/tenders/evaluation.py`, `tests/tenders/test_evaluation.py`.
- **Verificación:** test que falla sin el arreglo; pico de memoria de la medición de la corrida 14 y resultados idénticos a los de main sobre una versión que main sí termina.
- **No tocar:** la propuesta; la regla de emparejamiento.
- **Entorno:** cualquier equipo con Docker; copia de la base real en solo lectura.

### T-122 · Mostrar los cambios vigentes de la norma al proponer consecuencias

- **Diferida a la revisión con el primer producto (ADR-0024, 2026-10-05).**
- **Qué hacer:** hallazgo de T-109 (2026-10-04): `consequences.py::render_norm` muestra el texto original de una unidad aunque tenga `modifica` o `deroga` vigente a la fecha de autorización, y el modelo puede fundar una consecuencia en un artículo cambiado. Mostrar los cambios vigentes (`answering.change_block`) o no fundar en unidades con cambios vigentes, con el mismo criterio que T-109.
- **Archivos:** `evaluon/tenders/proposal/consequences.py`, `tests/tenders/test_consequences.py`.
- **Verificación:** test con una unidad modificada a la fecha; ninguna consecuencia fundada en texto no vigente.
- **No tocar:** la 001; las demás pasadas.
- **Entorno:** cualquier equipo con Docker.

### T-123 · Corregir la medición: citas de otra lectura y filas suprimidas por una circular

- **Qué hacer:** diagnóstico 1 de T-120: `_technical_citing` comparaba posiciones de citas de otra lectura; una fila que una circular deja `quitado` con `suprime` debe emparejar con el esperado de bloque `suprime` (encontrado), sin contar como sobrante; sin bloque, causa `suprimido_por_circular`.
- **Archivos:** `evaluon/tenders/evaluation.py`, `tests/tenders/test_evaluation.py`.
- **Verificación:** tests sintéticos que fallan sin el arreglo; regeneración sobre la base real del caso-01 (encontrados 83 → 91 de 93; REQ-031 2 → 13 de 15) y del caso-02 sin cambios.
- **No tocar:** la propuesta; las listas.
- **Entorno:** cualquier equipo con Docker.

### T-124 · Pasada de circulares: original en el anexo por título y requisitos que agrega un "Debe decir"

- **Qué hacer:** diagnóstico 1 de T-120 (M-044, M-015): buscar el anexo por título normalizado por palabras completas y en sus primeros tramos; en un par "Donde dice / Debe decir", cada oración nueva con marcador de obligación es requisito `circular`; las que reformulan el "Dice" van como sugerencia; sin duplicados.
- **Archivos:** `evaluon/tenders/proposal/circular_units.py`, `circulars.py`, `run.py` (estado del requisito nuevo), tests de `tests/tenders/test_circular_units.py`.
- **Verificación:** tests con textos inventados que fallan sin el arreglo; casos adversos de ambigüedad, reformulación y duplicados.
- **No tocar:** `evaluation.py`; modelos.
- **Entorno:** cualquier equipo con Docker.

### T-125 · Corregir el criterio del filtro que descartó requisitos reales

- **Qué hacer:** diagnóstico 1 de T-120 (M-058, M-063); decisión del responsable del 2026-10-04 (el caso-01 pasa a ajuste del filtro): instrucciones `matriz-filtro-v2.md` con dos reglas generales y una guarda en código: una fila que comparte oración con una fila firme del mismo tramo no se descarta (pasa a sugerencia), con un separador de oraciones que respeta abreviaturas.
- **Archivos:** `evaluon/tenders/proposal/filter.py`, `evaluon/tenders/prompts/matriz-filtro-v2.md`, `evaluon/settings.py` (`MATRIX_PROMPT_VERSIONS`), `tests/tenders/test_filter.py`.
- **Verificación:** tests con el doble y textos inventados; nunca convierte firme en descartada ni sugerencia en firme.
- **No tocar:** `evaluation.py`; circulares.
- **Entorno:** cualquier equipo con Docker; el efecto real se mide con el caso-01 (ajuste) y a ciegas con 02, 03 y 04.

### T-126 · Mostrar la cadena completa de circulares que modifican una misma condición

- **Qué hacer:** decisión del responsable del 2026-10-04: cuando varias circulares modifican, reemplazan o rectifican la misma condición (por ejemplo, una cadena 4 → 5 → 6), la pantalla, la impresión y el PDF muestran la cadena completa en orden de fecha: texto original del pliego, cada texto intermedio con su circular y fecha, y el texto vigente al final, marcado como vigente. Hoy se muestra solo el último.
- **Archivos:** `evaluon/tenders/services/matrix_page.py`, `evaluon/templates/tenders/_change.html`, `matrix.html`, `matrix_print.html`, tests de `tests/tenders/test_circular_screen.py`.
- **Verificación:** tests con textos inventados: cadena de tres circulares sobre la misma cita en orden; una circular que anula a otra se muestra como tal; leyenda de borrador intacta; texto literal.
- **No tocar:** la pasada de circulares; la medición.
- **Entorno:** cualquier equipo con Docker.

### T-127 · Impedir que una aclaración termine como supresión y registrar la versión de `circulares_cambios`

- **Qué hacer:** hallazgo bloqueante del diagnóstico 5 de T-120, sección 1 (caso-06, M-005). Una `aclara` decidida en la extracción que no se puede anclar (`clave_ambigua`) va al respaldo; el respaldo no recibe el efecto ya decidido, devuelve `suprime`, `Processor._apply` (`circulars.py:1041-1066`) lo copia sin validar y `run.py:707-709` deja la fila `quitado`. (a) El respaldo recibe el efecto que decidió la extracción para ese cambio y no puede contradecirlo (si lo contradice, se conserva el de la extracción y se registra la anomalía). (b) Un `suprime` solo se acepta como firme si el texto de la circular citado contiene una frase explícita de supresión ("se suprime", "queda sin efecto", "se elimina", "déjase sin efecto", "no será exigible", "derógase" y sus formas); si no la tiene, se guarda como sugerencia de revisión obligatoria, nunca como supresión firme ni como estado `quitado`. (c) `run.py:331-334` (`_begin`): `prompt_versions` incluye `circulares_cambios` y un nombre por instrucción de la pasada de circulares (respaldo y extracción), diagnóstico 5, punto 4.
- **Aviso de tareas anteriores:** T-115 (extracción y respaldo) y T-124 (`circulars.py`, `run.py`, estado del requisito nuevo): mismos archivos, se espera a que estén integradas. T-123: la regla de la medición para una fila `quitado` por `suprime` no cambia. T-120 se mide de nuevo después de esta tarea (caso-06: M-005 deja de ser `suprimido_por_circular`; caso-01 sin cambios) y antes de T-108.
- **Archivos:** `evaluon/tenders/proposal/circulars.py`, `evaluon/tenders/proposal/run.py` (`_begin` y la transición a `quitado`), `evaluon/tenders/proposal/circular_units.py` solo si la lista de frases de supresión va ahí, `tests/tenders/test_circulars.py`, `tests/tenders/test_run_versions.py` (o el test existente de `prompt_versions`).
- **Verificación:** tests con textos inventados que fallan sin el arreglo: (a) cambio `aclara` de la extracción con respaldo que devuelve `suprime` queda `aclara` y se registra; (b) `suprime` con frase explícita queda firme, con cada frase de la lista; `suprime` sin frase queda como sugerencia y la fila no pasa a `quitado`; una circular que dice "sin efecto" en otra oración no relacionada con la cita no habilita la supresión (caso adverso); (c) `prompt_versions` de la corrida trae `circulares_cambios`; suite en verde. Se registra en la auditoría (P6) el efecto original, el devuelto y el resultado.
- **No tocar:** la extracción por clave (`circular_changes.py`: es T-128); `evaluation.py`; instrucciones de las pasadas; esquema.
- **Entorno:** cualquier equipo con Docker.

### T-128 · Aplicar una aclaración de cláusula a todas sus citas

**Decisión del responsable del 2026-10-05: sí. Cuando una circular aclara una cláusula sin decir a qué oración se refiere, la aclaración se aplica a todas las citas de esa cláusula.**

- **Qué hacer:** diagnóstico 4, causa B, y diagnóstico 5, corrección 2. Cuando la circular nombra una cláusula que tiene varias citas y no copia texto anterior, hoy se declara `clave_ambigua` (`circular_changes.py:249-250`) y todo va al respaldo; igual con un anexo nombrado sin texto anterior (`:262-263`). Propuesta: un cambio `aclara` sobre una cláusula (o anexo) nombrado se aplica a todas las citas de esa cláusula, con efecto `aclara` (inocuo: no cambia el texto vigente ni quita la fila). `reemplaza` y `suprime` sin texto anterior siguen sin aplicarse a varias citas. Afirma una aclaración sobre varias citas: por eso necesita la decisión del responsable antes de arrancar; si decide otra cosa, la tarea se reescribe o se retira.
- **Aviso de tareas anteriores:** T-115 (`circular_changes.py`) y T-124 (misma pasada); T-127 va antes (cierra el camino `aclara` a `suprime` por el respaldo, que esta tarea reduce pero no elimina). T-120 se mide de nuevo después de T-127 y de esta tarea, si se aprueba.
- **Archivos:** `evaluon/tenders/proposal/circular_changes.py`, `tests/tenders/test_circular_changes.py`.
- **Verificación:** tests con textos inventados que fallan sin el arreglo: `aclara` sobre cláusula de dos o tres citas sin texto anterior da una fuente por cita; un anexo nombrado igual; `reemplaza` o `suprime` sin texto anterior sobre varias citas siguen en `clave_ambigua`; cláusula inexistente sigue al respaldo; suite en verde. Efecto real: caso-06 (M-004, M-005, M-025) y caso-05 (M-046), medido en T-120.
- **No tocar:** `circulars.py` y `run.py` (T-127); instrucciones; la medición.
- **Entorno:** cualquier equipo con Docker.

### T-129 · Reconocer supresiones dichas con sustantivo y aplicar la aclaración de un renglón a sus citas

- **Qué hacer:** diagnóstico 6 de T-120, correcciones 1 y 2. (1) `_SUPPRESSION_PHRASE` (`evaluon/tenders/proposal/circulars.py`, cerca de las líneas 99-101) reconoce también las formas nominales con objeto de pliego ("se dispone la eliminación de la subcláusula…", "supresión del punto…", "derogación del artículo…") y el infinitivo ("se dispone suprimir/eliminar…"). Un sustantivo sin objeto de pliego no cuenta, para no tomar "eliminación de residuos" como supresión. (2) `_pool_for` (`circular_changes.py`, cerca de las líneas 260-263) acepta una `aclara` con objetivo de renglón y sin texto anterior, y la aplica a las citas de ese renglón, con el mismo criterio que T-128 aplica a cláusula y anexo (decisión del Coordinador: es el criterio que aprobó el responsable el 2026-10-05).
- **Aviso de tareas anteriores:** T-127 (lista de frases de supresión y marca de revisión obligatoria) y T-128 (`_pool_for`): mismos archivos, se espera a que estén integradas. T-120 se mide de nuevo después, con 01, 05 y 06 y estabilidad; meta según el diagnóstico 6: caso-01 15 de 15 y caso-05 7 de 8 (M-059 queda: es de lectura de tablas). Contar aparte las marcas de revisión obligatoria de supresión (aviso de T-127). Riesgo: más fuentes ajenas en filas técnicas (hoy 0 por renglón); medirlo.
- **Archivos:** `evaluon/tenders/proposal/circulars.py`, `evaluon/tenders/proposal/circular_changes.py`, `tests/tenders/test_circulars.py`, `tests/tenders/test_circular_changes.py`.
- **Verificación:** tests con textos inventados que fallan sin el arreglo: cada forma nominal e infinitiva reconocida como supresión; un falso positivo ("eliminación de residuos") que no cuenta; una `aclara` de renglón sin texto anterior da una fuente por cita del renglón; un renglón inexistente no da nada; suite en verde.
- **No tocar:** `circular_units.py`, los prompts, la medición, el esquema.
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

### T-137 · Pasada de circulares: revisión obligatoria visible ante un cambio sin resolver y las tres causas de la aceptación a ciegas

- **Origen:** informe de T-108 (`verificacion/T-108.md`, punto 3): fallos que hacen perder o falsean un requisito sin que la Comisión lo vea (ADR-0024, punto 4: se corrigen). Una sola tarea agrupada (ADR-0025).
- **Qué hacer:** (1) **red de seguridad (P3):** cuando un cambio de una circular queda sin resolver, el pedido al modelo da salida inválida o el reintento pierde cambios, las filas que la circular nombra (cláusula, renglón, anexo) se marcan "A revisión obligatoria" con la circular y su fecha, con el mismo mecanismo de T-127; nunca se pierde un cambio en silencio. (2) Pasar el encabezado del renglón al contexto de la pasada, para que un cambio de un renglón no se aplique a otro (caso-03, D7, renglones 6 y 14). (3) Fecha, hora y lugar de una visita no son dato del trámite cuando el pliego tiene la cláusula que los fija (caso-04, D2), y un título de carátula no es una aclaración. (4) Desempate estable en `_source_points` de la medición (`evaluation.py`).
- **Umbral (escrito antes):** ningún cambio de circular perdido sin marca en los casos 03 y 04; el renglón 14 del caso-03 sin fuentes de D7; M-035 del caso-04 con su fuente. Se mide una vez con 03 y 04 (sin ser ya a ciegas, se informa así) y se comprueba que 01, 05 y 06 no bajan de 15/15, 7/8 y 3/3. Lo que no llegue va a la revisión con el primer producto, con su impacto.
- **Nivel de verificación:** plena (instrucciones al modelo y P3).
- **Archivos:** `evaluon/tenders/proposal/circular_units.py`, `circular_changes.py`, `circulars.py`, `run.py` (solo la marca), `evaluon/tenders/evaluation.py` (solo el desempate), prompts de circulares (versión nueva si cambian), tests de `tests/tenders/`.
- **No tocar:** el esquema; la extracción y el filtro; las listas esperadas.
- **Entorno:** MSI con GPU para la medición, de a una.

### T-147 · Circulares: aviso en la fila que cambia (#183) y medición del criterio de ADR-0034

- **Origen:** dictamen de auditoría de la 003 (rechazado) y ADR-0034. Ronda adicional admitida por ADR-0025 (violación de P3).
- **Nivel de verificación:** plena (P3).
- **Qué hacer:** (1) que un cambio de una circular que no se pudo aplicar deje la marca "A revisión obligatoria" en la fila que ese cambio modifica (caso-03: la cláusula de cotización #183, M-028, que hoy muestra "UN peso" como vigente sin aviso), aunque la fila comparta pocas palabras con el cambio; usar el objetivo del cambio (cláusula o renglón nombrado) antes que la coincidencia de palabras. (2) Medición (`evaluation.py`): informar por fila de circular esperada si cumple P3 (muestra el cambio con su cita o tiene la marca) como medida que bloquea, y los cuatro puntos aparte sin bloquear; contar como encontrado el requisito cuyo contenido está en otra fila e informarlo aparte (ADR-0034). (3) Registrar la memoria de video usada en cada medición (hallazgo menor de la auditoría, P6).
- **Umbral (escrito antes de medir):** casos 03 y 04: P3 en el 100 % de las filas de circular esperadas; encontrados 100 % con la regla de ADR-0034; sin regresión en 01, 05 y 06.
- **No tocar:** el esquema; la extracción y el filtro.
- **Entorno:** MSI con GPU para la medición, de a una.

## Revisión con el primer producto (ADR-0024)

Lo menor de la 003, que se encara con la 008 y la 004 terminadas, con el uso real de la Comisión:

- Ajuste del filtro y de los sobrantes (T-106): oraciones partidas, anexos, deberes generales y etapas posteriores como filas propias (diagnósticos 2 a 4 de T-120).
- Tramos de tabla que quedan pendientes y no dan fila (M-059 de los casos 01 y 05).
- Líneas de formulario u opciones sin verbo que la extracción toma como dato (M-033 del caso-05).
- Cambios vigentes de la norma en las consecuencias (T-122).
- Granularidad de las listas esperadas frente a la del extractor.
- La marca de revisión obligatoria de una supresión sin frase no aparece en una versión nueva de la matriz sin propuesta propia (aviso de T-127); se cuenta aparte en la medición.
- Fuentes ajenas que agrega una aclaración aplicada a todas las citas (T-128, T-129).

- Faltantes de la aceptación a ciegas que no pierden requisito (T-108): M-030, M-032 y M-043 del caso-03 (oración partida, encabezado de lista sin fila, agrupado); su contenido está en otras filas.
- Imprecisiones de REQ-031 en la aceptación a ciegas que no pierden requisito (texto original o vigente parcial, convención de cadena D5 → D6), según `verificacion/T-108.md`.

- Circulares (T-137, medición de la ronda 2): en el caso-03, la cláusula de cotización (#183, M-028) sigue mostrando "UN peso" como vigente sin marca propia (el aviso está en el renglón 6 y en las cláusulas #276 y #279); 20 de 22 filas marcadas por la pérdida de D7 no lo necesitaban (y 3 de 5 en el caso-04): la Comisión las descarta una por una. Ver `verificacion/T-137.md`.

## Cobertura de requisitos

| Requisito | Tareas |
|---|---|
| REQ-022 | T-067, T-069, T-075 |
| REQ-023 | T-067, T-072, T-075 |
| REQ-024 | T-067, T-070, T-071, T-073, T-074, T-075, T-076, T-077, T-078, T-084, T-102, T-103, T-106, T-108, T-111 |
| REQ-025 | T-067, T-070, T-073, T-074, T-075, T-076, T-077, T-084, T-097, T-101, T-108 |
| REQ-026 | T-067, T-068, T-079, T-082, T-104, T-110 |
| REQ-027 | T-067, T-068, T-082 |
| REQ-028 | T-067, T-070, T-072, T-073, T-074, T-075, T-077, T-079, T-082, T-098, T-113 |
| REQ-029 | T-067, T-068, T-080, T-081, T-084 |
| REQ-030 | T-067, T-071, T-073, T-074, T-077, T-078, T-084, T-085, T-096, T-097, T-099, T-100, T-103, T-108 |
| REQ-031 | T-067, T-072, T-074, T-083, T-098, T-108, T-113, T-114, T-115, T-116, T-117, T-118, T-119, T-120, T-127, T-128, T-129 |
| REQ-032 | T-067, T-074, T-082, T-086, T-105, T-112, T-116 |
| REQ-033 | T-099, T-101, T-102, T-103, T-104, T-105, T-106, T-107, T-108 |
| REQ-034 | T-104, T-105, T-110, T-112 |
| REQ-035 | T-099, T-102, T-103, T-106, T-107, T-108, T-110, T-111, T-112 |
| REQ-036 | T-099, T-106, T-108, T-109, T-111, T-112 |

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

**Enmienda del 2026-10-04 (T-099 a T-108).**

| Momento | Pueden ir a la vez | Por qué no chocan |
|---|---|---|
| Terminada T-096 | T-099 (esquema y `settings.py`), sola en esquema | Nadie más toca modelos ni migraciones |
| Terminada T-099 e integradas T-097 y T-098 | T-100, en paralelo con T-104 | `run.py`, `matrix.py`, `evaluation.py` y plantillas del nivel frente a `services/discarded.py`, `review.py` y `validation.py` |
| Terminada T-100 | T-101 → T-102 → T-109 (cadena en `run.py`), en paralelo con T-103 → T-111 (`evaluation.py`) y con T-105 (vistas, tras T-104) | `proposal/` frente a `evaluation.py` frente a vistas y plantillas |
| Terminada T-104 | T-110 (`services/suggestions.py`, `review.py`, `validation.py`), en paralelo con T-105 (vistas y plantillas) y con lo anterior | Servicios frente a vistas; T-110 no necesita `proposal/` (prueba con filas sintéticas) |
| Terminadas T-105 y T-110 | T-112 (vistas y plantillas de sugerencias) | Mismos archivos de vistas y plantillas que T-105, y los servicios de T-110 ya integrados |
| Terminadas T-102, T-103, T-109 y T-111 | T-106 (GPU) | La GPU, de a una |
| Terminada T-106 | T-107 (datos) | Es del Coordinador y el responsable |
| Terminadas T-094, T-105, T-112 y T-107 | T-108 (GPU) | La GPU, de a una |

**Enmienda del 2026-10-04: circulares (T-113 a T-120).**

| Momento | Pueden ir a la vez | Por qué no chocan |
|---|---|---|
| Ahora (T-098 integrada) | T-113 (`proposal/circular_units.py`, `circulars.py`, `_save_circulars` en `run.py`), T-114 (esquema, `settings.py`, `_copy` de `validation.py`) y T-117 una vez que T-111 esté integrada (`evaluation.py`) | Código de circulares frente a esquema y configuración frente a medición. La referencia al original de T-113 espera a T-114 |
| Terminadas T-113 y T-114 | T-115 (`circular_changes.py`, instrucciones v3) y T-116 (vistas y plantillas, además de T-105 y T-112) | Proposal frente a vistas; T-115 no toca plantillas ni T-116 `proposal/` |
| Terminada T-117 | T-118 y T-119 (datos), en paralelo con T-115 y T-116 | Son del Coordinador, fuera del repositorio |
| Terminadas T-113, T-115, T-117, T-118 y T-119 | T-120 (GPU), de a una con T-106 y T-108 | La GPU |
| Terminadas T-116 y T-120 (más lo anterior de T-108) | T-108 | La aceptación final: REQ-031 con 03 y 04 |

Cadenas nuevas: `proposal/circulars.py`: T-098 → T-113 → T-115. `evaluation.py` y `medir_matriz`: T-097 → T-100 → T-103 → T-111 → T-117. Vistas y plantillas: T-105 → T-112 → T-116. Esquema: solo T-114.

T-094 sigue como estaba pensada, antes del filtro, y no se rehace: la aceptación final es T-108. El Coordinador decide si T-094 se cierra con lo ya medido o se retira.

Recursos que no se comparten: la GPU (T-071 en su medición, T-075 y T-084, de a una) y la base de pruebas.

Camino crítico hasta ver una matriz: T-067 → T-068 → T-069 → T-072 → T-073 → T-074 → T-075 (con T-076 lista antes). Hasta la medición: … → T-073 → T-078 → T-080 → T-084.
