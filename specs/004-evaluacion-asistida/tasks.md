# Tareas 004 · Evaluación asistida de ofertas

Plan: `specs/004-evaluacion-asistida/plan.md`

Despliegue: pendiente

> El tablero (`docs/tablero.md`) se genera de este archivo. Al aprobarse el despliegue, la línea de arriba pasa a `Despliegue: aprobado AAAA-MM-DD`.

Estados: pendiente · en curso · en verificación · terminada · bloqueada

Dos tareas que no dependen entre sí y no comparten archivos se pueden hacer en paralelo.

Ritmo de trabajo (ADR-0024 y ADR-0025): las ramas de tarea no tocan este archivo ni el tablero; el Coordinador los actualiza una vez por lote. La verificación de cada tarea queda en `specs/004-evaluacion-asistida/verificacion/T-NNN.md`. Pocas tareas, grandes, agrupadas por corte; toda medición escribe antes su umbral y tiene como máximo dos rondas.

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-148 | Esquema, configuración compartida y tamaños: módulo `assessment` con todas sus tablas y triggers, tipo de pedido y de hecho, contexto del motor de lotes, `medir_tamanos` y `entorno.md` | REQ-052, REQ-053, REQ-054, REQ-056, REQ-057 | — | terminada |
| T-149 | Preparar los casos para medir (Coordinador): caso chico calcado de ofertas reales y lista esperada del dictamen del caso-00, con la lista de fichas completada | REQ-052, REQ-053, REQ-054, REQ-059, REQ-060 | — | terminada |
| T-150 | Corte vertical: evaluar una oferta de punta a punta (lectura completa por grupos, cita ubicada, contraste, cuatro resultados, preguntas formuladas) con pantalla mínima del par | REQ-052, REQ-053, REQ-054, REQ-055, REQ-059, REQ-060 | T-148 | terminada |
| T-151 | Medir el caso chico: lista esperada, comparación y comando `medir_evaluacion` | REQ-052, REQ-053, REQ-054, REQ-055, REQ-060 | T-149, T-150 | pendiente |
| T-152 | Matriz de evaluación de todas las ofertas: descarte propuesto, orden económico con el Portal, estado por oferta y aviso de versión | REQ-057, REQ-058, REQ-059 | T-150 | pendiente |
| T-153 | Revisión: confirmar, corregir y rechazar cada propuesta, con historial y fundamentos a la vista | REQ-053, REQ-056 | T-150 | terminada |
| T-154 | Preguntas a la Comisión, respuestas como fundamento y subsanación con su recorrido | REQ-055, REQ-056, REQ-060 | T-153 | pendiente |
| T-155 | Medir el caso-00 contra el dictamen (medición base) | REQ-052, REQ-053, REQ-054, REQ-059 | T-149, T-151, T-152 | pendiente |
| T-156 | Corregir los hallazgos de T-155 y medir de nuevo (ronda 1) | REQ-052, REQ-053, REQ-054, REQ-059 | T-154, T-155 | pendiente |
| T-157 | Solo si T-156 no llegó al umbral: corregir y medir de nuevo (ronda 2, la última) | REQ-052, REQ-053, REQ-054, REQ-059 | T-156 | pendiente |

## Paralelismo

- **T-148 y T-149 a la vez**: T-149 es del Coordinador, sobre `corpus/casos/caso-00/` y `tests/assessment/data/`, sin tocar código.
- **T-148, sola entre las tareas de código.** Toca el esquema, la cola compartida, los tipos de hecho, `settings.py` y `docker-compose.yml`: nadie más trabaja sobre `evaluon/assessment/` ni sobre esos archivos hasta que termine y se integre. Después de T-148 ninguna tarea toca el esquema ni la configuración compartida; si una lo necesita, se detiene, lo informa y se encadena una tarea nueva que corre sola.
- **T-150 va sola** sobre `evaluon/assessment/` hasta integrarse: crea los módulos del núcleo y los archivos que se reparten después.
- **T-151, T-152 y T-153 a la vez** después de T-150, sin compartir archivos: T-151 toca `evaluation.py`, el comando de medición y los datos del caso chico; T-152 toca `services/matrix.py`, `ordering.py`, las vistas y plantillas de la matriz; T-153 toca `services/review.py`, la vista y la plantilla de revisión, y edita `result.html` (de T-150). T-151 usa la GPU; las otras dos no (pruebas con modelo simulado). Si T-151 corrige algo del núcleo (`prompting.py`, `combine.py`, instrucciones), lo informa antes de tocar archivos que otra tarea en curso necesite.
- **T-154 después de T-153**: edita la misma plantilla del par (`result.html`) y usa el servicio de decisiones de T-153. No toca el esquema.
- **T-155 usa la GPU.** Empieza cuando terminaron T-149, T-151 y T-152; puede correr mientras T-153 y T-154 se desarrollan, porque no tocan la construcción de la evaluación. Una medición a la vez; nunca dos.
- **T-156 y T-157 en secuencia.** T-156 espera también a T-154, para corregir sobre el producto completo.
- Las ramas de tarea no tocan `tasks.md` ni el tablero (ADR-0025).

## Detalle

### T-148 · Esquema, configuración compartida y tamaños

- **Requisitos:** REQ-052, REQ-053, REQ-054, REQ-056, REQ-057
- **Nivel de verificación:** plena (esquema, configuración compartida, memoria de video).
- **Qué hay que hacer:**
  1. Crear `evaluon/assessment/` (app, `models.py`, migración inicial y migración de triggers) con las ocho tablas del plan: `assessment_request`, `assessment_run`, `assessment_result`, `assessment_citation`, `assessment_step`, `assessment_decision`, `assessment_question`, `assessment_answer`, con sus restricciones (valores válidos, único por evaluación y requisito, una restricción por clase de cita, `note` obligatoria en `corregir`, `rechazar` y `pedir_subsanacion`) y los triggers de solo inserción (UPDATE y DELETE rechazados) en todas.
  2. `tenders_job`: tipo `evaluate_offers` (migración de la restricción) y su manejador en `HANDLERS`, apuntando a `evaluon.assessment.services.evaluate.run_evaluate_offers` (lo crea T-150; hasta entonces el pedido falla con un motivo, como pasó con el Portal).
  3. `audit_event.event_type`: `eval_request`, `eval_build`, `eval_decision`, `eval_answer` (migración de la restricción y `audit/models.py`).
  4. `settings.py` y `.env.example`: `GENERATION_BATCH_CONTEXT_TOKENS` (variable `GENERATION_BATCH_CTX_SIZE`, 32.768) y los parámetros `ASSESSMENT_*` del plan, y `INSTALLED_APPS`. `docker-compose.yml`: `generation_batch` usa `GENERATION_BATCH_CTX_SIZE`; se pasa también a `app` y `worker` como se hace con `GENERATION_CTX_SIZE`. Ajustar `tests/test_compose_env.py` y `tests/tenders/test_generation_batch.py` (los dos motores siguen iguales salvo el contexto).
  5. Registrar el contexto real del motor de lotes en las propuestas de la 003 (`tenders/proposal/run.py`) y las fichas de la 008 (`offers/services/sheets.py`): una línea en cada archivo, con su test. `consequences.py` y `circulars.py` siguen con el presupuesto del contexto de 16.384 (más conservador, sin cambio de resultados).
  6. `sizing.py` y comando `medir_tamanos`: por oferta (las tres del caso-00 cargadas con `cargar_oferta`, o el caso chico), páginas, tokens por documento y por página con `generation.count_tokens`, documentos de texto idéntico, y cuántos grupos salen con `ASSESSMENT_GROUP_TOKENS` en orden de carga. Mide además la memoria de video con los tres modelos cargados y `generation_batch` a 32.768 (`tenders.evaluation.video_memory`). Los números por documento quedan fuera del repositorio (`corpus/casos/caso-00/corridas-tamanos/`); al repositorio van solo las cuentas por oferta.
  7. `specs/004-evaluacion-asistida/entorno.md`: la variable nueva, cómo comprobar el contexto y la memoria de video, lo medido y, si el contexto de 32.768 no entra en el reparto, la alternativa elegida del ADR-0037 (24.576 con presupuesto de 14.000, o apagar `generation` durante la evaluación), registrada en el ADR.
- **Archivos:** `evaluon/assessment/__init__.py`, `apps.py`, `models.py`, `migrations/0001_initial.py`, `migrations/0002_triggers.py`, `sizing.py`, `management/commands/medir_tamanos.py`; `evaluon/tenders/models.py` y su migración, `evaluon/tenders/jobs.py`, `evaluon/tenders/proposal/run.py` (una línea); `evaluon/offers/services/sheets.py` (una línea); `evaluon/audit/models.py` y su migración; `evaluon/settings.py`; `docker-compose.yml`; `.env.example`; `tests/assessment/` (`conftest.py`, `test_schema.py`, `test_sizing.py`); `tests/test_compose_env.py`; `tests/tenders/test_generation_batch.py`; `specs/004-evaluacion-asistida/entorno.md`; `docs/adr/0037-…md` (si cambia el contexto elegido).
- **Verificación:** `docker compose run --rm app pytest tests/assessment tests/tenders tests/offers tests/test_compose_env.py` en verde y la suite completa una vez al final. Tests: triggers de las ocho tablas, restricciones de cita por clase y de nota obligatoria, el pedido sin manejador falla con motivo, los dos motores con el mismo comando salvo el contexto, el contexto registrado en la 003 y la 008. Corrida local de `medir_tamanos` con las tres ofertas del caso-00 y la memoria de video medida, en `entorno.md`.
- **No tocar:** la lógica de evaluación, las pantallas, las instrucciones, la lectura de `evaluon/norms/`, `offers/` y `tenders/` fuera de lo indicado.
- **Entorno:** la medición de memoria usa la GPU: de a una.

### T-149 · Preparar los casos para medir (Coordinador)

- **Requisitos:** REQ-052, REQ-053, REQ-054, REQ-059, REQ-060
- **Nivel de verificación:** revisión del Coordinador, sin código de producto; `medir_evaluacion --verificar-esperada` (T-151) comprueba huellas, páginas y citas contra las lecturas sin usar el modelo.
- **Qué hay que hacer:**
  1. **Caso chico** en `tests/assessment/data/caso-chico/`: partir del pliego y de la matriz validada del caso chico de la 008 y sumar 3 ofertas calcadas de las reales (misma estructura de archivos: formularios, una póliza, un escaneo con una página ilegible, una hoja técnica; nombres, CUIT y montos inventados), con 8 a 10 requisitos que incluyan: un "cumple" y un "no cumple" con cita, un documento exigido que falta (par "no se encontró el documento"), un requisito que se verifica fuera de la oferta ("no determinado" con pregunta), una página ilegible y un requisito técnico por renglón. Datos de cotización del Portal inventados para el orden. `evaluacion-esperada.yaml` con el resultado esperado de cada par y el orden económico. Revisar que no queda ningún dato real (P4).
  2. **Lista esperada del dictamen del caso-00** en `corpus/casos/caso-00/esperado/dictamen-esperado.yaml`, con el formato del plan: por oferta y requisito que el dictamen trata, su resultado, su `base` (`oferta`, `externa`, `tecnica`), si la oferta queda descartada, y el orden económico del cuadro comparativo del Portal. Con huella del dictamen y visto bueno. Dejar anotados los pares de `base: externa` para que el responsable decida cómo se cuentan (punto 1 del plan).
  3. **Completar `fichas-esperadas.yaml`** con lo que el ADR-0035 dejó pendiente: los cuadros del Portal (fotos de las ofertas 1 y 3) y la copia deduplicada (`copy_of`) del documento esperado, porque REQ-054 se mide contra esa lista.
- **Archivos:** `tests/assessment/data/caso-chico/**` (en el repositorio, solo contenido inventado); `corpus/casos/caso-00/esperado/` (fuera del repositorio).
- **Verificación:** revisión del Coordinador; `medir_evaluacion --verificar-esperada` sobre las dos listas cuando exista (T-151).
- **No tocar:** código de `evaluon/`; ningún dato de las ofertas ni del dictamen se copia al repositorio.

### T-150 · Corte vertical: evaluar una oferta de punta a punta

- **Requisitos:** REQ-052, REQ-053, REQ-054, REQ-055, REQ-059, REQ-060
- **Nivel de verificación:** plena (lógica, datos, instrucciones al modelo y principios P3 y P6).
- **Qué hay que hacer:** entregar de punta a punta lo mínimo, con un caso inventado y público (una matriz validada chica y una oferta con documentos de texto y un escaneo, generados desde texto inventado):
- **Aviso de tareas anteriores:** T-148: la oferta 2 del caso-00 queda a 471 tokens del presupuesto de grupo (20.000): prever el paso a dos grupos. `jobs._handler` captura cualquier `ImportError` y lo informa como "sin manejador": limitarlo a `ModuleNotFoundError` del propio módulo o registrar la causa. El despliegue de la 004 recrea `generation_batch`, `worker` y `app` (contexto 32.768).
  1. `documents.py`: documentos de la oferta como texto por página (con los pasajes de la lectura; página ilegible marcada), copias de texto idéntico, tokens por documento y por página (`generation.count_tokens`, reutilizando `sizing.py`), empaquetado en grupos hasta `ASSESSMENT_GROUP_TOKENS` con relevancia por requisito (`offers.retrieval.retrieve` con la reescritura de `sheets.rewrite_requirement`, calculada una vez por requisito) solo cuando la oferta no entra en un grupo, ventanas de un documento mayor que el presupuesto, tope de grupos.
  2. `grounds.py`: texto vigente de la cita del requisito (el de la circular que la modifica y el original), unidades de norma que la matriz ya asocia al requisito, y las respuestas de la Comisión vigentes que aplican (`applicable_answers`, hasta 20; con el reranker si hay más).
  3. `citations.py`, `prompting.py`, `combine.py` y `prompts/evaluacion-v1.md` y `contraste-v1.md`: pedido con documentos primero y requisito al final, esquema JSON, ubicación de cada cita con `tenders.proposal.quotes.locate` y página con `pages_at`, reintento, unión de grupos, contraste, "no se encontró el documento", "no determinado" con su motivo y pregunta, según el plan y los ADR-0037 y ADR-0038.
  4. `services/evaluate.py`: `request_evaluation` (rol, rechazos con su motivo, un pedido en curso por procedimiento), `run_evaluate_offers` (de a una oferta, cada una guardada en una transacción con su `assessment_run`, resultados, citas y pedidos al modelo), creación de la pregunta abierta del par, hechos `eval_request` y `eval_build`, y la función única del resultado vigente de un par.
  5. Comando `evaluar_ofertas` (pide y corre la evaluación de un procedimiento, con `--oferta` y `--requisito`, en el canal `eval`).
  6. Pantalla mínima: la página de un par en solo lectura (requisito, citas de la oferta con documento, página y texto, explicación rotulada, motivo, pregunta), con el enlace al original en la página citada; `views/results.py`, `urls.py`, `evaluon/urls.py` (una línea) y `templates/assessment/result.html`.
- **Umbral del corte:** el de la columna "Caso chico" de la tabla del plan, medido con T-151; en esta tarea, tests con modelo simulado y una corrida del caso inventado.
- **Archivos:** `evaluon/assessment/documents.py`, `grounds.py`, `citations.py`, `prompting.py`, `combine.py`, `services/__init__.py`, `services/evaluate.py`, `prompts/`, `views/__init__.py`, `views/results.py`, `urls.py`, `management/commands/evaluar_ofertas.py`; `evaluon/urls.py`; `evaluon/templates/assessment/result.html`; `tests/assessment/test_documents.py`, `test_citations.py`, `test_combine.py`, `test_evaluate.py`, `test_result_page.py` y `fakes.py` (modelo simulado), con datos en `tests/assessment/data/`.
- **Verificación:** `docker compose run --rm app pytest tests/assessment`; suite completa una vez al final. Tests de: oferta chica en un grupo, oferta grande en varios y un documento mayor que el presupuesto en ventanas; una cita no ubicable que baja un "cumple" a "no determinado"; "cumple" y "no cumple" en grupos distintos; "no consta" en todos los grupos con y sin páginas sin leer; un contraste que no corrobora; la respuesta de la Comisión que aplica y la que no; el requisito técnico por renglón; rechazo por rol y registro de cada pedido al modelo; el texto de toda cita es igual al recorte del texto canónico.
- **No tocar:** el esquema y las migraciones, `settings.py`, `docker-compose.yml`, `offers/`, `tenders/`, `portal/` (solo lectura), `services/matrix.py`, `review.py`, `questions.py`, `remedy.py`.

### T-151 · Medir el caso chico

- **Requisitos:** REQ-052, REQ-053, REQ-054, REQ-055, REQ-060
- **Nivel de verificación:** plena (medición con umbral escrito en el plan).
- **Qué hay que hacer:**
- **Aviso de tareas anteriores:** T-149: el formato de `evaluacion-esperada.yaml` lo definió T-149; el lector de la medición se ajusta a él. `fichas-esperadas.yaml` trae un campo nuevo `equivalentes` (copias deduplicadas) que el lector de la 008 ignora: leerlo para REQ-054. Las anclas de las fotos del Portal y de los escaneos del caso chico se comprueban con `--verificar-esperada`. T-150: el caso chico pasa a medición de desarrollo (contraste-v1 se ajustó mirándolo); la medición independiente es T-155 con el caso-00. Corregir en la lista del caso chico M-003 de la oferta B a "lectura incompleta" con pregunta (ADR-0038, regla 3; decisión del Coordinador) y sumar un par con lectura completa y documento ausente; ajustar `test_the_whole_small_case...`. `offers/evaluation.py::_create_matrix` arma las filas técnicas solo con el encabezado "RENGLÓN N" sin las cláusulas del renglón: corregirlo o armar la matriz propia.
  1. `evaluation.py` y comando `medir_evaluacion`: carga la lista esperada (`evaluacion-esperada.yaml` del caso chico y `dictamen-esperado.yaml` del caso-00, con huella y visto bueno, reutilizando `tenders/evaluation.py`), arma el caso chico en la base (`--caso-chico`), corre la evaluación en el canal `eval`, cuenta según "Cómo se cuenta" del plan (coincidencia, contradicciones, citas, fragmentos de la ficha, matriz, tiempos y tokens) y guarda la corrida (`parametros.json`, `resultados.jsonl`, `resumen.md`, `resumen-publico.md`). `--verificar-esperada` comprueba las listas contra las lecturas sin usar el modelo.
  2. Una medición del caso chico. Si no llega al umbral, se corrige dentro de esta tarea antes de cerrarla; no cuenta como ronda del caso-00. Cada cambio de instrucciones sube la versión.
- **Umbral (escrito antes de medir):** el de la columna "Caso chico" de la tabla del plan: coincidencia 100 %, 0 contradicciones, 0 "cumple" o "no cumple" sin cita, citas 100 % literales, "no se encontró el documento" y pregunta 100 % donde corresponde.
- **Archivos:** `evaluon/assessment/evaluation.py`, `management/commands/medir_evaluacion.py`; `tests/assessment/test_evaluation.py`; correcciones que haga falta en `prompting.py`, `combine.py` y `prompts/` (un commit por hallazgo); `specs/004-evaluacion-asistida/verificacion/T-151.md` (solo identificadores, cuentas y tiempos).
- **Verificación:** `medir_evaluacion --caso-chico` en el umbral, con el resumen público; `pytest tests/assessment`; suite completa una vez sobre la rama combinada con main.
- **No tocar:** el esquema, `services/matrix.py`, `review.py`, `questions.py`, `remedy.py`, la lista esperada (no se ajusta a lo que el sistema encuentra).
- **Entorno:** GPU, de a una.

### T-152 · Matriz de evaluación de todas las ofertas

- **Requisitos:** REQ-057, REQ-058, REQ-059
- **Nivel de verificación:** plena (lógica y datos).
- **Qué hay que hacer:**
- **Aviso de tareas anteriores:** T-149: el dictamen del caso-00 descarta una oferta **por renglón** (Lombardozzi, renglones 5 y 6, art. 55 inc. h): la matriz de evaluación tiene que admitir el descarte parcial por renglón, además del descarte de la oferta entera (decisión del Coordinador, dentro de REQ-059). T-150: "Evaluar todas" debe avisar antes si una oferta no tiene documentos (hoy el pedido entero se rechaza).
  1. `services/matrix.py`: la grilla de requisitos por ofertas con el resultado vigente y el estado de cada par, el estado por oferta (requisitos por estado y por resultado, preguntas abiertas), el aviso de versión posterior de la matriz, y el pedido "Evaluar todas las ofertas" (llama a `request_evaluation` con todas las ofertas) con el aviso de fin de la 003.
  2. `ordering.py`: descarte propuesto (algún requisito formal o técnico con resultado efectivo "no cumple", con requisito, fundamento y la consecuencia prevista de la matriz; "no se encontró el documento" y "no determinado" no descartan) y orden económico: total y por renglón con `portal_offer_data` y `portal_quote` de la 012; oferta sin datos del Portal al final y sin posición; monedas distintas sin orden y con aviso. El alcance del descarte a requisitos económicos queda detrás de una sola constante, según la respuesta del responsable al punto 3 del plan.
  3. Pantalla: la matriz de evaluación (ofertas por requisitos), estado por oferta, descartes propuestos con su motivo, orden económico, preguntas abiertas y aviso de versión, todo rotulado como propuesta; `views/matrix.py`, `templates/assessment/matrix.html`.
- **Archivos:** `evaluon/assessment/services/matrix.py`, `ordering.py`, `views/matrix.py`, `urls_matrix.py`, `evaluon/templates/assessment/matrix.html`, `tests/assessment/test_matrix.py`, `test_ordering.py`.
- **Verificación:** `docker compose run --rm app pytest tests/assessment/test_matrix.py tests/assessment/test_ordering.py`; suite completa una vez al final. Tests de: tres ofertas con resultados y descarte por un "no cumple" con su motivo; un "no se encontró el documento" que no descarta; orden por total igual al de los datos del Portal y por renglón; oferta sin datos del Portal; monedas distintas; evaluación armada con la versión 1 y versión 2 validada (aviso); cuentas por estado y preguntas abiertas; el estado de un par con y sin decisión.
- **No tocar:** el esquema, `settings.py`, `services/evaluate.py` (se usa, no se cambia), `result.html`, `portal/` (solo lectura).

### T-153 · Revisión de cada propuesta

- **Requisitos:** REQ-053, REQ-056
- **Nivel de verificación:** plena (principios P3 y P6).
- **Qué hay que hacer:** `services/review.py`: confirmar, corregir (elige otro resultado y escribe el motivo) y rechazar (con motivo), solo el evaluador; cada decisión inserta su fila en `assessment_decision` con la propuesta original a la vista, y deja el hecho `eval_decision`. El historial del par lista todo el recorrido (propuestas, decisiones, autor, fecha). Pantalla del par con las acciones, el historial y los fundamentos a la vista: el requisito (vigente y original), las citas de la oferta con enlace al original en la página citada, la norma con su artículo o la respuesta de la Comisión rotulada con quién y cuándo.
- **Aviso de tareas anteriores:** T-150: un "cumple" que el contraste baja a `sin_corroborar` queda sin pregunta a la Comisión: decidir si la lleva.
- **Archivos:** `evaluon/assessment/services/review.py`, `views/review.py`, `urls_review.py`, `evaluon/templates/assessment/result.html` (de T-150) y `history.html`, `tests/assessment/test_review.py`, `test_result_actions.py`.
- **Verificación:** `docker compose run --rm app pytest tests/assessment/test_review.py tests/assessment/test_result_actions.py`; suite completa una vez al final. Tests de: corregir deja la propuesta original, la corrección, el autor y la fecha; rol (el operador no decide); nota obligatoria; una decisión sobre un resultado reemplazado por uno nuevo no cambia la nueva propuesta; el historial muestra el recorrido; ningún fundamento aparece como cita de la oferta si no lo es.
- **No tocar:** el esquema, `settings.py`, `services/evaluate.py`, `services/matrix.py`, `questions.py`, `remedy.py`.

### T-154 · Preguntas a la Comisión, respuestas como fundamento y subsanación

- **Requisitos:** REQ-055, REQ-056, REQ-060
- **Nivel de verificación:** plena (P3, P6 y recorrido registrado).
- **Qué hay que hacer:**
- **Aviso de tareas anteriores:** T-153: un resultado rechazado deja `effective_outcome` en `None`; la matriz y los conteos deben tratarlo. El estado de un par se define en `review.state_of` / `effective_outcome` (única definición; T-152 la reutiliza).
  1. `services/questions.py`: listar preguntas abiertas y respondidas; responder (solo el evaluador) con alcance `par`, `requisito` (por omisión) o `procedimiento`, o dejar sin responder; hecho `eval_answer`; una respuesta nueva reemplaza a la anterior como vigente y la anterior queda. Al responder, ofrecer "evaluar de nuevo" los pares afectados (causa `respuesta`), sin cambiar lo ya evaluado.
  2. `services/remedy.py`: `pedir_subsanacion` (evaluador, con nota) cuando el resultado es "no se encontró el documento"; agregar el documento a la oferta con `offers.services.offers.load_document` y vincularlo (`subsanar`); pedir evaluar de nuevo ese requisito (causa `subsanacion`), que lee todos los documentos, incluido el agregado, y crea un resultado nuevo con `previous` al anterior. La evaluación nueva espera a que la lectura del documento termine.
  3. Pantalla: la lista de preguntas con el formulario de respuesta, la marca "subsanación pedida" y el recorrido completo en el historial del par (resultado con la cita del pliego, pedido, documento agregado con su huella y quién lo cargó, evaluación nueva, decisión sobre ella); `views/questions.py`, `views/remedy.py`, `templates/assessment/questions.html` y `_remedy.html` (incluido desde `result.html`).
- **Archivos:** `evaluon/assessment/services/questions.py`, `remedy.py`, `views/questions.py`, `views/remedy.py`, `urls_questions.py`, `evaluon/templates/assessment/questions.html`, `_remedy.html`, `result.html` (una inclusión), `tests/assessment/test_questions.py`, `test_remedy.py`, `test_flow_remedy.py`.
- **Verificación:** `docker compose run --rm app pytest tests/assessment/test_questions.py tests/assessment/test_remedy.py tests/assessment/test_flow_remedy.py`; suite completa una vez al final. Tests de: un requisito que depende de un dato que no está en la oferta ni en la normativa queda "no determinado" con una pregunta, y una pregunta sin respuesta no entra como fundamento; una respuesta de alcance `requisito` se usa en otra oferta del mismo requisito y se muestra con quién y cuándo; una respuesta sola no produce "cumple"; una respuesta nueva reemplaza a la anterior y la anterior queda; recorrido completo de una subsanación con las dos evaluaciones registradas y el documento agregado leído; rol (el operador no pide la subsanación ni responde).
- **No tocar:** el esquema, `settings.py`, `services/evaluate.py` (se llama, no se cambia), `services/matrix.py`, `services/review.py`, `offers/` (se usa su servicio de carga sin cambios).

### T-155 · Medir el caso-00 contra el dictamen (medición base)

- **Requisitos:** REQ-052, REQ-053, REQ-054, REQ-059
- **Nivel de verificación:** plena.
- **Qué hay que hacer:** con las tres ofertas del caso-00 cargadas y leídas y la matriz validada de la 008, correr `medir_evaluacion` contra `dictamen-esperado.yaml` y `fichas-esperadas.yaml` y guardar la corrida fuera del repositorio. Informar por oferta y por pedido el tiempo, los tokens por grupo, las páginas sin leer y los pares por resultado y por motivo de "no determinado". Clasificar cada hallazgo por causa: lectura, agrupamiento, elección del modelo, cita, contraste, unión de grupos, requisito externo, requisito técnico, orden. No corrige nada. Antes de medir, el responsable responde los puntos 1 a 3 del plan; la tarea los toma como regla de conteo.
- **Umbral (escrito antes de medir):** el de la columna "Caso-00" de la tabla del plan: coincidencia de más del 80 % (con la regla de la `base: externa` según la respuesta al punto 1), 0 contradicciones, 0 conclusiones sin cita de la oferta, citas 100 % literales, 90 % de fragmentos de la ficha, tres ofertas evaluadas y orden igual al del Portal.
- **Archivos:** `specs/004-evaluacion-asistida/verificacion/T-155.md` (solo identificadores, cuentas, causas y tiempos; sin datos personales). La corrida completa queda en `corpus/casos/caso-00/corridas/`.
- **Verificación:** el resumen público con las proporciones y sus intervalos, y la lista de hallazgos por causa.
- **No tocar:** el código; ningún dato real al repositorio.
- **Entorno:** GPU, de a una; no se lanza otra medición ni otra carga de la GPU.

### T-156 · Corregir los hallazgos de T-155 y medir de nuevo (ronda 1)

- **Requisitos:** REQ-052, REQ-053, REQ-054, REQ-059
- **Nivel de verificación:** plena si cambia lógica o instrucciones al modelo; liviana por hallazgo si es un cambio acotado con test que falla antes y pasa después. El encargo lo dice hallazgo por hallazgo.
- **Qué hay que hacer:** corregir todos los hallazgos de T-155 que bajan alguna medida del umbral, un commit por hallazgo, y medir una vez, al final del lote. Ajustes permitidos, en este orden: presupuesto por grupo (de 20.000 a 14.000 o 8.000 tokens), orden de los documentos y tope de grupos, redacción de las instrucciones y del contraste, motivo de "no determinado" mal asignado, ubicación de citas. Cada cambio de instrucciones sube la versión. Si un hallazgo exige cambiar la forma de tratar un requisito externo o técnico, se informa al responsable antes de seguir.
- **Archivos:** los de `evaluon/assessment/` que cada hallazgo exija, `prompts/`, `tests/assessment/`, `specs/004-evaluacion-asistida/verificacion/T-156.md`.
- **Verificación:** la medición con el mismo umbral que T-155. Si llega, T-157 no se hace. Si no, se anota qué falta y con qué impacto.
- **No tocar:** el esquema (si un hallazgo lo exige, se informa y se hace en una tarea aparte), la lista esperada (no se ajusta a lo que el sistema encuentra), la 003, la 008 y la 012.
- **Entorno:** GPU, de a una.

### T-157 · Ronda 2 (condicional)

- **Requisitos:** REQ-052, REQ-053, REQ-054, REQ-059
- **Nivel de verificación:** el de T-156.
- **Qué hay que hacer:** solo si T-156 no llegó al umbral: corregir lo que queda con el mismo método y medir por última vez. Lo que siga sin llegar pasa, con su impacto, a la lista de revisión con el primer producto (ADR-0024) y no se hace otra ronda, salvo que el faltante haga perder un requisito o viole un principio (ADR-0025). Una contradicción con el dictamen abierta después de esta ronda no se acepta: se informa al responsable.
- **Archivos:** como T-156, más `specs/004-evaluacion-asistida/verificacion/T-157.md`.
- **Verificación:** la medición con el mismo umbral.
- **No tocar:** lo mismo que T-156.
- **Entorno:** GPU, de a una.

## Revisión con el primer producto

Lo que no llegue al umbral después de la ronda 2 se anota acá, con su impacto (ADR-0024). Vacía por ahora.

- Medición a ciegas con el proceso en curso que reservó el responsable, cuando el producto esté más cerrado (spec).
- Cómo se integran las tablas de preguntas y respuestas con el circuito general de la 009 (ADR-0040).
