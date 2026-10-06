# Tareas 008 · Ofertas y ficha por oferta

Plan: `specs/008-ofertas-ficha/plan.md`

Despliegue: pendiente

> El tablero (`docs/tablero.md`) se genera de este archivo. Al aprobarse el despliegue, la línea de arriba pasa a `Despliegue: aprobado AAAA-MM-DD`.

Estados: pendiente · en curso · en verificación · terminada · bloqueada

Dos tareas que no dependen entre sí y no comparten archivos se pueden hacer en paralelo.

Ritmo de trabajo (ADR-0024 y ADR-0025): las ramas de tarea no tocan este archivo ni el tablero; el Coordinador los actualiza una vez por lote. La verificación de cada tarea queda en `specs/008-ofertas-ficha/verificacion/T-NNN.md`. Pocas tareas, grandes, agrupadas por corte.

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-130 | Corte vertical con el caso chico: esquema, carga, lectura (texto y escaneo), ficha, pantalla mínima y medición | REQ-037, REQ-038, REQ-039, REQ-040, REQ-041, REQ-043, REQ-044 | — | terminada |
| T-131 | Completar la carga y la lectura de ofertas: pantalla, fotos sueltas, segundo intento de lectura y lista de páginas no leídas | REQ-037, REQ-038 | T-130 | terminada |
| T-132 | Corregir la ficha: confirmar, corregir, quitar y agregar fragmentos, historial y aviso de versión de la matriz | REQ-042, REQ-043 | T-130 | terminada |
| T-133 | Preparar el caso-00 para medir: lista esperada de fichas de las tres ofertas y matriz validada (Coordinador) | REQ-039, REQ-040, REQ-044 | — | terminada |
| T-134 | Medir la ficha con las tres ofertas del caso-00 (medición base) | REQ-038, REQ-039, REQ-040, REQ-041, REQ-044 | T-131, T-133 | terminada |
| T-135 | Corregir los hallazgos de T-134 y medir de nuevo (ronda 1) | REQ-038, REQ-039, REQ-040, REQ-041, REQ-044 | T-134 | terminada |
| T-136 | Solo si T-135 no llegó al umbral: corregir y medir de nuevo (ronda 2, la última) | REQ-038, REQ-039, REQ-040, REQ-041, REQ-044 | T-135 | terminada |
| T-146 | Búsqueda de la ficha con el requisito reescrito como lo diría una oferta | REQ-039, REQ-040 | T-136 | terminada |

## Paralelismo

- **Primero T-130, sola.** Toca el esquema, la cola compartida, los tipos de hecho y los archivos que después se reparten: nadie más trabaja sobre `evaluon/offers/` ni sobre `evaluon/tenders/jobs.py` hasta que termine y se integre.
- **T-131 y T-132 pueden ir a la vez** después de T-130: no dependen entre sí y no comparten archivos (T-131 toca lectura, carga y la pantalla de ofertas; T-132 toca revisión y la pantalla de la ficha; ver sus listas). Ninguna toca el esquema ni `settings.py`. Si una de las dos necesita un cambio de esquema, se detiene y lo informa: el cambio se hace en una tarea aparte, que depende de T-130 y corre sola.
- **T-133 puede ir a la vez que cualquier otra**: la hace el Coordinador sobre `corpus/casos/caso-00/` (fuera del repositorio), sin tocar código.
- **T-134 usa la GPU.** Empieza cuando terminaron T-131 y T-133. Puede correr mientras T-132 se desarrolla si la medición se hace sobre una rama que no la incluye (T-132 no toca la construcción de la ficha); si el Coordinador prefiere medir el producto completo, T-134 espera a T-132.
- **T-135 y T-136 en secuencia.** Una medición a la vez; nunca dos.
- Las mediciones (T-130, T-134, T-135, T-136) no se lanzan a la vez que otra medición ni que otra carga de la GPU.

## Detalle

### T-130 · Corte vertical con el caso chico

- **Requisitos:** REQ-037, REQ-038, REQ-039, REQ-040, REQ-041, REQ-043, REQ-044
- **Nivel de verificación:** plena (esquema, datos, instrucciones al modelo y principios P3, P4 y P6).
- **Qué hay que hacer:** entregar de punta a punta lo mínimo, con un caso inventado y público: un procedimiento con una matriz validada de unos 5 requisitos formales y económicos y 3 renglones técnicos, una oferta con dos documentos (uno con texto y otro escaneado, generado desde texto inventado), y lo que sigue:
  1. **Esquema completo** del plan, en una sola migración de `offers`: todas las tablas y triggers de "Modelo de datos"; más los dos tipos de pedido y `target_id` en `tenders_job`, y los seis tipos de hecho de auditoría. Ninguna tarea posterior toca el esquema.
  2. **Carga y lectura** mínimas: `services/offers.py` (registrar oferta, cargar documento con su huella, sin que la persona elija tipo; clasificación automática del tipo por reglas, vacía si no puede; la búsqueda siempre recorre todos los documentos, rechazo de duplicado), lectura con la 001 y OCR existente, pasajes con vectores y página, lista de páginas no leídas y de baja confianza. Comando `cargar_oferta`. Dos manejadores en `tenders/jobs.py`.
  3. **Ficha**: `retrieval.py` (embeddings, palabras, reranker) y `services/sheets.py` (pedido al modelo con `prompts/ficha-v1.md` y `ficha-renglon-v1.md`, validación de alias, texto del pasaje, "no se encontró", control de palabras de juicio, `cotizado` con el estado "no se pudo leer" cuando el renglón cae en una página o tabla ilegible (nunca "no cotizado"), documentación técnica, versión de la matriz, registro `offers_sheet_step`).
  4. **Pantalla mínima**: lista de ofertas del procedimiento, página de la oferta (documentos, estado, páginas no leídas, "Armar ficha") y página de la ficha en solo lectura. Dos archivos de URLs separados (`urls_documents.py` y `urls_sheet.py`) y dos archivos de vistas, para que T-131 y T-132 no choquen.
  5. **Medición del caso chico**: `offers/evaluation.py` y `medir_fichas` (reutiliza `tenders/evaluation.py`; no lo reescribe), con `tests/offers/data/caso-chico/` (documentos inventados, generador del escaneado, lista esperada en YAML) y la opción `--caso-chico` que arma el caso en la base.
- **Umbral (escrito antes de medir):** el de la columna "Caso chico" de la tabla del plan: 90 % de fragmentos encontrados o más, 100 % de texto literal, 100 % de "no se encontró" en los sin respuesta, 100 % de síntesis sin juicio, 100 % de renglones y de documentación técnica, 0 páginas sin texto ni lista. Si no llega, se corrige dentro de esta tarea.
- **Archivos:** `evaluon/offers/**` (nuevo), `evaluon/templates/offers/**`, `evaluon/tenders/models.py` y su migración (solo `JobKind` y `target_id`), `evaluon/tenders/jobs.py`, `evaluon/audit/models.py` y su migración, `evaluon/settings.py` (parámetros de ofertas e `INSTALLED_APPS`), `evaluon/urls.py` (incluir `offers`), `tests/offers/**`.
- **Verificación:** `docker compose run --rm app pytest tests/offers`, suite completa una vez al final, y `medir_fichas --caso-chico` con el resumen público en `specs/008-ofertas-ficha/verificacion/T-130.md`. El levantar de punta a punta: cargar, leer, armar la ficha y verla en pantalla. Tests de: duplicado rechazado, ficha solo contra matriz validada, alias inexistente, requisito sin respuesta, palabras de juicio, literalidad y de los triggers de inmutabilidad.
- **No tocar:** el código de la 003 fuera de lo indicado, `docker-compose.yml`, la lectura de `evaluon/norms/`, la pantalla de revisión de la ficha (T-132), la lista y la medición del caso-00.

### T-131 · Completar la carga y la lectura de ofertas

- **Requisitos:** REQ-037, REQ-038
- **Nivel de verificación:** plena (lectura de datos y umbrales de OCR).
- **Qué hay que hacer:** pantalla completa de ofertas: registrar oferente, cargar varios documentos a la vez (sin elegir tipo), ver estado y tipo clasificado, descargar el original, aviso de fin de la 003. Aceptar fotos JPG y PNG (guardar el original y convertirlas a un PDF de una página en el equipo). Segundo intento de lectura para páginas con confianza por debajo del umbral de dudosa (enderezado y umbral adaptativo; se conserva la lectura de mayor confianza y el informe dice cuál). Verificar antes de agregar cualquier dependencia de imagen si ya está en la imagen. Lista de páginas no leídas y de baja confianza con documento, página y confianza, en la oferta.
- **Aviso de tareas anteriores:** T-130: la clasificación de documentación técnica debe contar un documento técnico (especificaciones firmadas, folletos, hojas técnicas), no solo una tabla de renglones (decisión del Coordinador, T-133); leer también .docx (hojas técnicas de oferente 1 en el caso-00), convertidos dentro del equipo; falta el enlace desde la pantalla del procedimiento a las ofertas.
- **Archivos:** `evaluon/offers/services/offers.py`, `evaluon/offers/passages.py` (solo si hace falta), `evaluon/offers/reading.py` (nuevo: conversión y segundo intento), `evaluon/offers/views/documents.py`, `evaluon/offers/urls_documents.py`, `evaluon/templates/offers/offers.html` y `offer.html`, `pyproject.toml` y `Dockerfile` solo si falta una dependencia, `tests/offers/test_documents.py`, `tests/offers/test_reading.py`.
- **Verificación:** tests con un escaneo sintético torcido y una foto sintética: la página queda leída o en la lista; las páginas buenas no cambian de texto. `pytest tests/offers`; suite completa una vez al final.
- **No tocar:** el esquema y las migraciones, `settings.py`, `evaluon/offers/services/sheets.py`, `evaluon/offers/services/review.py`, `views/sheet*.py`, plantillas de la ficha, `evaluon/norms/`.

### T-132 · Corregir la ficha

- **Requisitos:** REQ-042, REQ-043
- **Nivel de verificación:** plena (lógica, datos y registro P6).
- **Qué hay que hacer:** `services/review.py`: confirmar (evaluador), corregir, quitar, restituir y agregar fragmentos (elegir un pasaje y, si se quiere, un recorte literal comprobado contra el texto canónico). Cada cambio deja su fila en `offers_change` y el hecho `sheet_change`; el fragmento anterior queda visible en el historial. Pantalla de la ficha con las acciones, el historial de una fila, la sección "Lo que no se encontró", y el aviso de versión ("Armada con la versión 1; la versión vigente es la 2") con el botón para armar una ficha nueva.
- **Archivos:** `evaluon/offers/services/review.py`, `evaluon/offers/views/sheet.py`, `evaluon/offers/urls_sheet.py`, `evaluon/templates/offers/sheet.html` y `sheet_history.html`, `tests/offers/test_review.py`, `tests/offers/test_sheet_page.py`.
- **Verificación:** tests de corregir con historial y autor, rol (operador no confirma), literalidad del recorte, aviso de versión con matriz v1 y v2. `pytest tests/offers`; suite completa una vez al final.
- **No tocar:** el esquema y las migraciones, `settings.py`, `evaluon/offers/services/offers.py`, `evaluon/offers/services/sheets.py` (la construcción), `views/documents.py`, plantillas de ofertas, `evaluon/tenders/`.

### T-133 · Preparar el caso-00 para medir (Coordinador)

- **Requisitos:** REQ-039, REQ-040, REQ-044
- **Nivel de verificación:** liviana (sin código: se comprueba con `medir_fichas --verificar-esperada`, sin usar el modelo).
- **Qué hay que hacer:** leyendo las tres ofertas sin correr el sistema, armar `corpus/casos/caso-00/esperado/fichas-esperadas.yaml` con el formato del plan: fragmentos esperados por requisito (documento, página, ancla), requisitos sin respuesta, estado de cada renglón por oferta, documentación técnica y páginas no legibles. Dejar una matriz validada del caso-00 (con el usuario de desarrollo, desde la propuesta medida en la 003). El visto bueno de la lista queda anotado en el archivo. Nada de esto va al repositorio.
- **Archivos:** solo `corpus/casos/caso-00/` (fuera del repositorio).
- **Verificación:** `medir_fichas --verificar-esperada` (T-130 lo trae): huellas, páginas y anclas ubicadas en las lecturas.
- **No tocar:** el repositorio. Ningún dato de las ofertas se copia a él.

### T-134 · Medir la ficha con las tres ofertas del caso-00

- **Requisitos:** REQ-038, REQ-039, REQ-040, REQ-041, REQ-044
- **Nivel de verificación:** plena.
- **Qué hay que hacer:** cargar las tres ofertas (29 documentos) con `cargar_oferta`, leerlas, medir con `medir_fichas` y guardar la corrida fuera del repositorio. Informar por oferta y por página el tiempo y el reparto de páginas por estado. Clasificar cada hallazgo por causa: lectura, recuperación, elección del modelo, síntesis, renglones. No corrige nada.
- **Aviso de tareas anteriores:** T-130: la regla "renglón sin oferta = no se pudo leer si la oferta tiene cualquier página no leída" es demasiado amplia y la medición cuenta esos renglones aparte (el 2/2 del caso chico está inflado): informar la proporción de renglones "aparte" y acotar la regla a las páginas relevantes en la ronda 1 si pesa. Las anclas se escriben como las ve una persona, no como sale de la lectura de una tabla. T-132: se puede confirmar una fila "no se encontró" (queda confirmada la ausencia); tenerlo en cuenta al contar filas confirmadas. T-131: el segundo intento de lectura no se probó con documentos reales que lo necesiten (los CamScanner de oferente 3 leen con 84,8 a 90,6 de confianza): informar en la medición cuántas páginas lo usaron; falta un test de la descarga (`?descargar`).
- **Umbral (escrito antes de medir):** el de la columna "Caso-00" de la tabla del plan: 90 % de fragmentos o más, 100 % de texto literal, 100 % de síntesis sin juicio, 90 % de renglones (17 de 18), 100 % de documentación técnica, 0 páginas sin texto ni lista.
- **Archivos:** `specs/008-ofertas-ficha/verificacion/T-134.md` (solo identificadores, cuentas, causas y tiempos; sin datos personales). La corrida completa queda en `corpus/casos/caso-00/corridas/`.
- **Verificación:** el resumen público con las proporciones y sus intervalos, y la lista de hallazgos por causa.
- **No tocar:** el código; ningún dato real al repositorio.

### T-135 · Corregir los hallazgos de T-134 y medir de nuevo (ronda 1)

- **Requisitos:** REQ-038, REQ-039, REQ-040, REQ-041, REQ-044
- **Nivel de verificación:** plena si cambia lógica o instrucciones al modelo; liviana por hallazgo si es un cambio acotado con test que falla antes y pasa después. El encargo lo dice hallazgo por hallazgo.
- **Qué hay que hacer:** corregir todos los hallazgos de T-134 que bajan alguna medida del umbral, un commit por hallazgo, y medir una vez, al final del lote. Ajustes permitidos, en este orden: candidatos de 8 a 12, consulta con el encabezado del renglón, zona de tabla para renglones, umbrales de OCR de la página dudosa, redacción de las instrucciones. Cada cambio de instrucciones sube la versión de la instrucción.
- **Archivos:** los de `evaluon/offers/` que cada hallazgo exija, `evaluon/offers/prompts/`, `tests/offers/`, `specs/008-ofertas-ficha/verificacion/T-135.md`.
- **Verificación:** la medición con el mismo umbral que T-134. Si llega al umbral, T-136 no se hace. Si no, se anota qué falta y con qué impacto.
- **No tocar:** el esquema (si un hallazgo lo exige, se informa y se hace en una tarea aparte), la 003, la lista esperada (no se ajusta la lista a lo que el sistema encuentra).

### T-136 · Ronda 2 (condicional)

- **Requisitos:** REQ-038, REQ-039, REQ-040, REQ-041, REQ-044
- **Nivel de verificación:** el de T-135.
- **Qué hay que hacer:** solo si T-135 no llegó al umbral: corregir lo que queda con el mismo método y medir por última vez. Lo que siga sin llegar pasa, con su impacto, a la lista de revisión con el primer producto (ADR-0024) y no se hace otra ronda, salvo que el faltante haga perder un requisito o viole un principio (ADR-0025).
- **Archivos:** como T-135, más `specs/008-ofertas-ficha/verificacion/T-136.md`.
- **Verificación:** la medición con el mismo umbral.
- **No tocar:** lo mismo que T-135.

### T-146 · Búsqueda de la ficha con el requisito reescrito como lo diría una oferta

- **Requisitos:** REQ-039, REQ-040
- **Origen:** calibración de T-136 (`verificacion/T-136.md`): 32 de 55 pasajes correctos reciben puntaje casi nulo del reranker porque la consulta usa el texto del pliego y la oferta responde con otras palabras; ningún umbral pasa de 25 de 55. Decisión del responsable del 2026-10-05: tarea nueva (cambio de diseño de la búsqueda, no una tercera ronda; ADR-0025).
- **Nivel de verificación:** plena (instrucciones al modelo).
- **Qué hay que hacer:** antes de recuperar, el modelo reescribe cada requisito como lo diría una oferta (por ejemplo, "garantía de mantenimiento de oferta del 5 %" como "póliza de caución, suma asegurada, mantenimiento de oferta"); se recupera y se reordena con la consulta original y la reescrita, y el pasaje queda con el mejor puntaje de las dos. La reescritura se guarda en el registro de la ficha (P6). Instrucciones nuevas con su versión. El umbral de 0,4 se recalibra con los puntajes nuevos.
- **Umbral (escrito antes de medir):** fragmentos encontrados 90 % (REQ-039), con falsos hallazgos no mayores que en T-136 (1) más 5, texto literal y síntesis sin juicio 100 %. Una medición con el caso-00; lo que no llegue va a la revisión con el primer producto.
- **No tocar:** el esquema; la lectura; la medición.
- **Entorno:** MSI con GPU para la medición, de a una.

## Revisión con el primer producto

- Ficha (T-146, ADR-0035): fragmentos encontrados en torno al 55 % con el método de búsqueda de pasajes; la lectura completa de los documentos por requisito se encara en la 004.
- Medición de la ficha: reconocer como encontrada la copia deduplicada (`copy_of`) del documento esperado.
- Lista esperada del caso-00: sumar los cuadros del Portal (fotos de oferente 1 y oferente 3) y los renglones de esas ofertas; releer las fotos con la lectura de tablas de T-136 (hoy no hay forma de releer un documento cargado).

Lo que no llegue al umbral después de la ronda 2 se anota acá, con su impacto (ADR-0024). Vacía por ahora.
