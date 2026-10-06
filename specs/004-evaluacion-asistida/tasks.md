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
| T-151 | Medir el caso chico: lista esperada, comparación y comando `medir_evaluacion` | REQ-052, REQ-053, REQ-054, REQ-055, REQ-060 | T-149, T-150 | terminada |
| T-152 | Matriz de evaluación de todas las ofertas: descarte propuesto, orden económico con el Portal, estado por oferta y aviso de versión | REQ-057, REQ-058, REQ-059 | T-150 | terminada |
| T-153 | Revisión: confirmar, corregir y rechazar cada propuesta, con historial y fundamentos a la vista | REQ-053, REQ-056 | T-150 | terminada |
| T-154 | Preguntas a la Comisión, respuestas como fundamento y subsanación con su recorrido | REQ-055, REQ-056, REQ-060 | T-153 | terminada |
| T-155 | Medir el caso-00 contra el dictamen (medición base) | REQ-052, REQ-053, REQ-054, REQ-059 | T-149, T-151, T-152 | terminada |
| T-156 | Corregir los hallazgos de T-155 y medir de nuevo (ronda 1) | REQ-052, REQ-053, REQ-054, REQ-059 | T-154, T-155 | terminada |
| T-157 | Solo si T-156 no llegó al umbral: corregir y medir de nuevo (ronda 2, la última) | REQ-052, REQ-053, REQ-054, REQ-059 | T-156 | terminada |
| T-158 | Contraste por cláusula de un cumple técnico: cero contradicciones con el dictamen (tercera ronda por la contradicción M-051, decisión del responsable) | REQ-052, REQ-053 | T-157 | terminada |
| T-164 | Corregir los hallazgos de T-158: el no cumple técnico exige una cita de la oferta que contradiga la cláusula (F-1) y el contraste por cláusula acota cláusulas y tokens (F-2); se mide con T-161 | REQ-052, REQ-053 | T-158 | terminada |
| T-159 | Descarga y verificación de archivos y servicio: proyector del 12B, 26B-A4B con su proyector, variables propias del lote, `--mmproj`, archivo `docker-compose.modelo-grande.yml`, prueba de humo con imagen y memoria medida | REQ-052 | — | pendiente |
| T-160 | Lectura con visión de las páginas dudosas: criterio, imagen, transcripción, lectura nueva con origen `vision`, registro y pantalla rotulada, con tests | REQ-052, REQ-053, REQ-054 | T-159 | terminada |
| T-161 | Medir el caso-00 con el 12B y visión (referencia, y medición de la visión y de T-164) | REQ-052, REQ-053, REQ-054, REQ-059 | T-160, T-164 | pendiente |
| T-162 | Medir el caso-00 con el 26B-A4B y visión, comparar con T-161 y decidir según el umbral (ronda 1) | REQ-052, REQ-053, REQ-054, REQ-059 | T-161 | pendiente |
| T-163 | Solo si T-162 quedó entre 2 y 3 pares de adoptarlo: un cambio igual para los dos modelos y las dos corridas de nuevo (ronda 2, la última) | REQ-052, REQ-053, REQ-054, REQ-059 | T-162 | pendiente |

## Paralelismo

- **T-148 y T-149 a la vez**: T-149 es del Coordinador, sobre `corpus/casos/caso-00/` y `tests/assessment/data/`, sin tocar código.
- **T-148, sola entre las tareas de código.** Toca el esquema, la cola compartida, los tipos de hecho, `settings.py` y `docker-compose.yml`: nadie más trabaja sobre `evaluon/assessment/` ni sobre esos archivos hasta que termine y se integre. Después de T-148 ninguna tarea toca el esquema ni la configuración compartida; si una lo necesita, se detiene, lo informa y se encadena una tarea nueva que corre sola.
- **T-150 va sola** sobre `evaluon/assessment/` hasta integrarse: crea los módulos del núcleo y los archivos que se reparten después.
- **T-151, T-152 y T-153 a la vez** después de T-150, sin compartir archivos: T-151 toca `evaluation.py`, el comando de medición y los datos del caso chico; T-152 toca `services/matrix.py`, `ordering.py`, las vistas y plantillas de la matriz; T-153 toca `services/review.py`, la vista y la plantilla de revisión, y edita `result.html` (de T-150). T-151 usa la GPU; las otras dos no (pruebas con modelo simulado). Si T-151 corrige algo del núcleo (`prompting.py`, `combine.py`, instrucciones), lo informa antes de tocar archivos que otra tarea en curso necesite.
- **T-154 después de T-153**: edita la misma plantilla del par (`result.html`) y usa el servicio de decisiones de T-153. No toca el esquema.
- **T-155 usa la GPU.** Empieza cuando terminaron T-149, T-151 y T-152; puede correr mientras T-153 y T-154 se desarrollan, porque no tocan la construcción de la evaluación. Una medición a la vez; nunca dos.
- **T-156 y T-157 en secuencia.** T-156 espera también a T-154, para corregir sobre el producto completo.
- Las ramas de tarea no tocan `tasks.md` ni el tablero (ADR-0025).

- **Enmienda 2026-10-06 (ADR-0041 y ADR-0042).** T-159 y T-160 no usan la GPU para medir (T-159 solo una prueba de humo y la memoria; coordinar con quien tenga la GPU). T-159 toca configuración compartida (`docker-compose.yml`, `settings.py`, `.env.example`, `scripts/`): va sola entre las tareas que las toquen; antes de lanzarla, el Coordinador confirma que T-156 a T-158 no las tocan (si las tocan, T-159 va después). T-160 toca `evaluon/offers/` (archivo nuevo y una migración de opciones), `evaluate.py`, `documents.py` y `result.html`: no corre a la vez que T-156, T-157 ni T-158, que editan los mismos módulos de `assessment/`; si T-157 se hace, T-160 espera a que se integre.
- **T-161, T-162 y T-163 usan la GPU y van después de T-158**, en secuencia y de a una. Ninguna otra medición ni carga de la GPU mientras corren. T-162 y T-163 cambian el motor de lotes por el 26B: nadie más evalúa en ese lapso.
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
- **Aviso de tareas anteriores:** T-152: la matriz hace unas dos consultas por par (sin carga en lote de decisiones): medir su tiempo con el caso-00; si pesa, que `review` exponga una versión que reciba las decisiones ya cargadas. Medir el orden y el descarte contra el dictamen (un "no cumple" económico descarta la oferta entera). T-151: el caso chico es medición de desarrollo (contraste-v2 se ajustó con sus pares); la medición independiente es la del caso-00. Si una pregunta abierta de una corrida anterior se reutiliza, la evaluación cuenta como sin pregunta: medir sobre una base limpia o con una sola corrida.
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

### T-158 · Contraste por cláusula de un cumple técnico

- **Requisitos:** REQ-052, REQ-053
- **Resultado:** ver `verificacion/T-158.md` (0 contradicciones, 0 conclusiones sin cita; coincidencia 22 de 49).

### T-164 · Hallazgos de T-158 (F-1 y F-2)

- **Requisitos:** REQ-052, REQ-053
- **Nivel de verificación:** plena (lógica e instrucciones al modelo).
- **Qué hay que hacer:**
  1. F-1: un "no cumple" técnico por cláusula exige, además de la cláusula literal del pliego, una cita literal de la oferta que la contradiga (ubicada en el texto canónico, ADR-0038). Sin esa cita, o si el motivo es la calidad de la lectura (escaneo, OCR), el resultado es "no determinado" con pregunta, nunca "no cumple".
  2. F-2: el contraste por cláusula agrupa las cláusulas del renglón (tope de cláusulas por pedido, sin partir fórmulas o tablas en líneas sueltas) y su salida no se corta: tokens suficientes o pedidos en partes. Una salida cortada se reintenta en partes antes de degradar a "sin_corroborar".
  3. El contraste por cláusula ve el documento de la oferta que respalda la cita (no solo la cita), para que una cláusula del encabezado del renglón no quede "no_aparece" cuando está en el documento (caso M-048).
- **Archivos:** `evaluon/assessment/prompts/clausulas-v2.md` (nueva versión; la v1 no se edita), `combine.py`, `services/evaluate.py`, `prompting.py`, `settings.py`, tests del área con datos inventados.
- **Verificación:** tests de cada punto (cita que contradice, motivo de lectura, salida cortada, cláusula en el documento y no en la cita); la suite completa una vez al final. No se mide sola: la medición del caso-00 va en T-161 (ADR-0025, una medición por lote).
- **No tocar:** `evaluon/offers/`, el compose, la visión (T-160).

### T-159 · Descarga, verificación y servicio de los modelos

- **Requisitos:** REQ-052
- **Nivel de verificación:** plena (configuración compartida, memoria de video, archivos).
- **Qué hay que hacer:**
  1. `scripts/fetch_models.sh` y `scripts/models.sha256`: sumar el proyector del 12B (`mmproj-gemma-4-12b-it-qat-q4_0.gguf`, 175.115.616 bytes, SHA-256 `cb018338a7538a9814d994bfe54644c71eb7ed54e31eae2f721e45fd3c260da7`, misma revisión `29d097773436b69ff9feafd636ab4cf873786537`) a la lista normal, y una lista aparte, con la opción `--modelo-grande`, con los dos archivos del 26B-A4B en la revisión `d1c082be9cf3c8a514acf63b8761f4b41935842e`: `gemma-4-26B_q4_0-it.gguf` (14.439.363.584 bytes, SHA-256 `3eca3b8f6d7baf218a7dd6bba5fb59a56ee25fe2d567b6f5f589b4f697eca51d`) y `gemma-4-26B-it-mmproj.gguf` (1.194.828.160 bytes, SHA-256 `a359953a076b877db30c31dbbb4c6d93b4a6e017ee5db5784247e4d4c0dd4f3b`). Antes de fijar, releer tamaños, huellas y revisión en la API de Hugging Face (`/api/models/<repo>/tree/<revisión>`) y corregir el ADR-0042 si algo difiere. Bajar y verificar con el script (es el único paso con internet). Los archivos no van al repositorio.
  2. `docker-compose.yml`: `generation_batch` suma `--mmproj /models/${GENERATION_BATCH_MMPROJ_FILE:-mmproj-gemma-4-12b-it-qat-q4_0.gguf}` y toma modelo, alias y huella de variables propias (`GENERATION_BATCH_MODEL_FILE`, `GENERATION_BATCH_MODEL_ALIAS`, `GENERATION_BATCH_MODEL_SHA256`, por omisión las de `generation`); `app` y `worker` las reciben. `evaluon/settings.py` y `.env.example`: las variables y `GENERATION_BATCH_MODEL_SHA256`, y los registros de las evaluaciones y propuestas (`assessment/services/evaluate.py`, `tenders/proposal/run.py`, `offers/services/sheets.py`: una línea cada uno) leen el modelo del lote. Ajustar `tests/test_compose_env.py` y `tests/tenders/test_generation_batch.py` (los dos motores iguales salvo contexto, modelo, alias y proyector).
  3. `docker-compose.modelo-grande.yml` (nuevo): sobrescribe `generation_batch` con el 26B-A4B y su proyector; no se usa salvo en la comparación.
  4. Prueba de humo, de a una: levantar `generation_batch` con el 12B y el proyector (un pedido con una imagen pública inventada) y con el 26B y su proyector. Medir la memoria de video máxima con embeddings, reranker y `generation` cargados, con contexto 32.768 y con una imagen, y el tiempo de un pedido de unos 20.000 tokens de entrada y el de uno con imagen. Si la compilación `server-cuda-b11347` no carga el 26B o un proyector, informarlo sin cambiar la compilación. Anotar todo en `specs/004-evaluacion-asistida/entorno.md` y, si la espera de 180 s no alcanza, proponer el valor.
- **Archivos:** `scripts/fetch_models.sh`, `scripts/models.sha256`, `docker-compose.yml`, `docker-compose.modelo-grande.yml`, `.env.example`, `evaluon/settings.py`, `evaluon/assessment/services/evaluate.py`, `evaluon/tenders/proposal/run.py`, `evaluon/offers/services/sheets.py` (una línea cada una), `tests/test_compose_env.py`, `tests/tenders/test_generation_batch.py`, `specs/004-evaluacion-asistida/entorno.md`, `docs/adr/0042-…md` (si cambia un dato).
- **Verificación:** `docker compose run --rm app pytest tests/test_compose_env.py tests/tenders tests/assessment` en verde; la suite completa una vez al final; huellas verificadas por el script; memoria y tiempos de la prueba de humo en `entorno.md`.
- **No tocar:** lógica de evaluación, `evaluon/offers/` (salvo la línea indicada), el esquema.
- **Entorno:** descarga de 15,6 GB (15 a 45 minutos); la GPU solo para la prueba de humo, de a una.

### T-160 · Lectura con visión de las páginas dudosas

- **Requisitos:** REQ-052, REQ-053, REQ-054
- **Nivel de verificación:** plena (lógica, datos, instrucciones al modelo, P3 y P6; incluye un cambio de opciones en el esquema de `offers`).
- **Qué hay que hacer:**
  1. `evaluon/offers/vision.py`: criterio de lectura dudosa (páginas `low_confidence`, `unread`, `without_text_unlisted` del informe de la última lectura, y toda página de un documento en formato imagen), tope `ASSESSMENT_VISION_MAX_PAGES`, dibujo de la página con pypdfium2 y su huella, pedido de transcripción al motor de lotes con la imagen, descarte de transcripciones vacías o con más de 30 % de `[ilegible]`, y lectura nueva del documento (`sequence` siguiente) con las páginas legibles de la anterior y las de visión con origen `vision`. Idempotente: no repite páginas ya leídas por visión.
  2. `evaluon/assessment/prompts/vision-v1.md`, parámetros en `settings.py` (`ASSESSMENT_VISION_MAX_PAGES`, resolución, tokens por imagen) y valor `vision` en las opciones del origen del texto del pasaje (una migración de opciones en `offers`).
  3. `assessment/services/evaluate.py`: antes de armar los documentos de una oferta, pedir la lectura por visión de sus páginas dudosas; registrar en `assessment_run.documents` qué lecturas por visión se usaron; marcar el resultado cuando una cita de la oferta cae en una página por visión. `documents.py`: una página por visión cuenta como leída.
  4. Informe de la lectura con el registro de P6 (modelo, huellas, compilación, parámetros, versión de instrucciones, motivo por página, huella de la imagen, pedido, salida cruda, tokens, tiempos).
  5. Pantalla del par (`result.html`): la cita de una página por visión rotulada "leída por visión", con la imagen de la página y el enlace al original.
  6. Comando `leer_con_vision` para correrla a mano sobre una oferta.
- **Archivos:** `evaluon/offers/vision.py`, `evaluon/offers/models.py` y su migración (solo opciones), `evaluon/assessment/prompts/vision-v1.md`, `evaluon/assessment/services/evaluate.py`, `evaluon/assessment/documents.py`, `evaluon/settings.py`, `evaluon/templates/assessment/result.html`, `evaluon/assessment/views/results.py`, `evaluon/offers/management/commands/leer_con_vision.py`, `tests/offers/test_vision.py`, `tests/assessment/test_vision_flow.py`, `tests/assessment/fakes.py` (modelo simulado con imagen), datos inventados en `tests/assessment/data/` (una página de texto inventado dibujada como imagen y una foto de tabla inventada).
- **Verificación:** `docker compose run --rm app pytest tests/offers tests/assessment`; la suite completa una vez al final. Tests de: el criterio (legible no va, dudosa e ilegible sí, formato imagen sí, tope respetado); una transcripción con demasiado `[ilegible]` deja la página sin leer; la lectura nueva conserva las páginas legibles y no toca la anterior; la cita sobre una página por visión es igual al recorte del canónico y una no ubicable degrada a "no determinado"; el registro trae modelo, huellas e imagen; la pantalla rotula; sin `--mmproj` o con el tope en 0 el flujo sigue igual. Una corrida con la página inventada y el motor real.
- **No tocar:** otro esquema que el valor de opciones; `combine.py`, `prompting.py`, las instrucciones de evaluación y el contraste; el compose y la configuración de T-159; la lista esperada.
- **Entorno:** la prueba con el motor real usa la GPU, de a una.

### T-161 · Medir el caso-00 con el 12B y visión (referencia)

- **Requisitos:** REQ-052, REQ-053, REQ-054, REQ-059
- **Nivel de verificación:** plena (medición con umbral escrito).
- **Qué hay que hacer:** con el código que deja T-158 y la visión de T-160, correr `medir_evaluacion` sobre el caso-00 con el 12B del lote, sobre una base limpia, con la misma lista esperada y `fichas-esperadas.yaml`. Registrar las páginas que fueron a visión (cuántas, por qué criterio), el tiempo por oferta y por pedido, los tokens y la memoria de video máxima, y clasificar cada par que cambió de resultado respecto de la última medición de T-158. Es la referencia de T-162. No corrige nada.
- **Aviso de tareas anteriores:** (T-164) Revisar a mano cada no cumple por cláusula: el sistema comprueba que la cita exista en la oferta, no que contradiga la cláusula (H-1). Contar aparte los cumple que bajan por no_legible, por salida cortada o por el filtro de calidad de lectura (H-2); si siguen los cortes, ajustar ASSESSMENT_CLAUSES_MAX_OUTPUT_TOKENS, cláusulas por pedido y caracteres.
- **Umbral (escrito antes de medir):** el del ADR-0041 (0 contradicciones; al menos 3 de los 10 pares de datos que no se leen pasan a coincidir; ningún par que coincidía deja de coincidir por una transcripción inventada; citas sobre páginas por visión 100 % literales) más el de la tabla del plan para el caso-00. Una ronda de ajuste de `vision-v1.md` o de la resolución si no llega (dentro de esta tarea, con commit propio y nueva versión); una segunda solo si la primera acercó.
- **Archivos:** `specs/004-evaluacion-asistida/verificacion/T-161.md` (solo identificadores, cuentas, causas y tiempos); ajustes de `vision-v1.md` y parámetros si hace falta. La corrida completa queda en `corpus/casos/caso-00/corridas/`.
- **Verificación:** el resumen público con proporciones e intervalos y la lista de pares que cambiaron, con su causa.
- **No tocar:** el código de evaluación, la lista esperada, el compose; ningún dato real al repositorio.
- **Entorno:** GPU, de a una; no corre con otra medición.

### T-162 · Medir con el 26B-A4B y decidir (ronda 1)

- **Requisitos:** REQ-052, REQ-053, REQ-054, REQ-059
- **Nivel de verificación:** plena.
- **Qué hay que hacer:** recrear `generation_batch` con `docker-compose.modelo-grande.yml` (el 26B-A4B y su proyector, descargados en T-159), comprobar la huella y la memoria, correr exactamente la misma medición de T-161 (mismo código, instrucciones, lecturas, matriz y lista esperada), y comparar par por par. Informar el tiempo por oferta y por pedido, los tokens, la memoria máxima y el tiempo total del caso-00. Aplicar la tabla de adopción del ADR-0042 y dejar el veredicto: adoptar, quedarse con el 12B, o segunda ronda. Al terminar, restaurar `generation_batch` con el compose base y verificar que arranca con el 12B. Si se adopta, el responsable decide y se redacta el ADR de reemplazo del modelo del lote; esta tarea no cambia el compose base.
- **Umbral (escrito antes de medir, ADR-0042):** 0 contradicciones; 0 conclusiones sin cita y citas 100 % literales; pares que pasan a coincidir menos pares que dejan de coincidir de al menos 4 sobre la referencia y 2 de los 4 desaciertos del modelo recuperados; incumplimientos reales detectados no menos que la referencia; cada par que cambia, explicado; tiempo hasta 30 minutos por oferta (decisión del responsable, 2026-10-06); memoria máxima hasta 22.000 MiB y ningún pedido fallido por memoria o espera.
- **Archivos:** `specs/004-evaluacion-asistida/verificacion/T-162.md` (solo identificadores, cuentas, causas, tiempos y el veredicto); la corrida en `corpus/casos/caso-00/corridas/`.
- **Verificación:** resumen público de las dos corridas lado a lado, la lista de pares que cambian con su causa y la tabla de adopción completa.
- **No tocar:** el compose base, el código, la lista esperada. Nada se ajusta al 26B.
- **Entorno:** GPU, de a una; el 12B del lote apagado durante la corrida.

### T-163 · Ronda 2 de la comparación (condicional)

- **Requisitos:** REQ-052, REQ-053, REQ-054, REQ-059
- **Nivel de verificación:** el de T-162.
- **Qué hay que hacer:** solo si T-162 cumplió los puntos de seguridad, tiempo y memoria y quedó entre 2 y 3 pares de la mejora exigida: un único cambio (presupuesto de grupo o instrucción del contraste), el mismo para los dos modelos, y las dos corridas de nuevo en secuencia, con el 12B primero. Lo que no llegue queda con el 12B y pasa, con su impacto, a la lista de revisión con el primer producto (ADR-0024). No hay tercera ronda salvo que el faltante haga perder un requisito o viole un principio (ADR-0025).
- **Archivos:** como T-162, más `specs/004-evaluacion-asistida/verificacion/T-163.md`.
- **Verificación:** la misma tabla de adopción.
- **No tocar:** lo mismo que T-162.
- **Entorno:** GPU, de a una.

## Revisión con el primer producto

Lo que no llegue al umbral después de la ronda 2 se anota acá, con su impacto (ADR-0024). Vacía por ahora.

- Medición a ciegas con el proceso en curso que reservó el responsable, cuando el producto esté más cerrado (spec).
- Cómo se integran las tablas de preguntas y respuestas con el circuito general de la 009 (ADR-0040).
