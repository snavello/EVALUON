# Tareas 015 · Uso y elección del modelo

Plan: `specs/015-uso-y-eleccion-del-modelo/plan.md`

Despliegue: pendiente

> El tablero (`docs/tablero.md`) se genera de este archivo. Al aprobarse el despliegue, la línea de arriba pasa a `Despliegue: aprobado AAAA-MM-DD`.

Estados: pendiente · en curso · en verificación · terminada · bloqueada

Dos tareas que no dependen entre sí y no comparten archivos se pueden hacer en paralelo.

Ritmo de trabajo (ADR-0024 y ADR-0025): las ramas de tarea no tocan este archivo ni el tablero; el Coordinador los actualiza una vez por lote. La verificación de cada tarea queda en `specs/015-uso-y-eleccion-del-modelo/verificacion/T-NNN.md`. Toda medición escribe antes su umbral (en el plan) y tiene como máximo dos rondas: la medición T-239 y un solo ajuste (T-240 y T-241). Los hallazgos de una medición se corrigen en una sola tarea. **Una sola tarea usa la GPU a la vez.** Al repositorio solo van cifras y resultados; el texto de los casos queda fuera (P4).

**IDs.** T-233 a T-252 son únicos: en `main` (af3dcad) el último ID es T-232 (feature 014). T-250, T-251 y T-252 se sumaron al incorporar el informe de revisión de las instrucciones; van en el orden de la tabla, no en el de su número. El Coordinador confirma contra las ramas abiertas antes de lanzar.

**Condiciones previas.**

- T-231 y T-232 de la 014 (pendientes en `main`) se integran antes de lanzar T-233, T-234, T-235 y T-250: tocan los mismos archivos (`portal_facts.py`, `evaluate.py`, `questions.py`, la matriz de la sección 2 y, quizá, una migración de `tenders`). Si el responsable prefiere no esperar, se mueve ese punto de T-231 o T-232 a la tarea de esta feature que corresponda.
- El informe `revision-instrucciones.md` (fuera del repositorio, en la carpeta local del Coordinador; ya existe, con las 10 correcciones ordenadas) es **entrada obligatoria** de T-236, T-252, T-237 y T-248.
- `descargas-modelos.md` (misma carpeta) tiene que decir que los cuatro archivos de los candidatos están completos antes de T-242. Al escribir este plan no existía; el 2026-10-10 `models/` tenía `Qwen3.8-27B-UD-Q4_K_M.gguf` completo y su proyector en descarga.
- ADR-0053 a ADR-0056 son propuestos: el responsable los acepta junto con este plan. T-233 no arranca sin que el responsable confirme la lectura de P3 del ADR-0053.
- **Pendiente con el responsable:** las condiciones de la forma de garantía que elige el oferente (pagaré o póliza). T-236 y T-252 la tratan con la regla provisoria del ADR-0054 y **no se mide (T-239) sin la respuesta**, que el Coordinador copia literal a la spec.

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-233 | El dato del Portal que coincide con lo que exige el pliego propone «cumple» con la cita del Portal; si difiere, «no cumple» o la diferencia (garantía como porcentaje del total con tolerancia de un centavo, cotización por renglón, total, CUIT); los tests de la decisión literal del ADR-0043 se reescriben. Umbral: 100 % de los casos de prueba con dato que coincide dan «cumple» con cita del Portal; 0 «cumple» con dato que no coincide | REQ-103 | T-231 (014) | pendiente |
| T-234 | Matriz: la cita se amplía por código hasta la oración completa (módulo compartido `sentences.py`), dos fragmentos de la misma oración son una fila, el encabezado del inciso viaja en el pedido y se ve en la fila; el fragmento original del modelo queda registrado | REQ-101 | T-232 (014) | pendiente |
| T-250 | Esquema de los motivos de descarte nuevos (consecuencia en la extracción, condición opcional, pago o factura, forma de presentar por el Portal, compromiso al presentarse): `DiscardReason`, `FilterMotive`, `FILTER_MOTIVES` y una migración de `tenders`, a cargo de un solo agente (enmienda del ADR-0019) | REQ-102 | T-233, T-232 (014) | pendiente |
| T-235 | Evaluación: la cita de la oferta se amplía a la oración completa, el requisito llega con su punto, el Portal le llega al modelo como bloque citable, el contraste recibe la oración y su contexto, y las preguntas a la Comisión se arman por código con requisito, conclusión y texto (sin texto fijo genérico; la pregunta del modelo dirigida al oferente se rechaza) | REQ-103, REQ-104, REQ-105 | T-233, T-234, T-231 (014) | pendiente |
| T-236 | Instrucciones de la matriz, parte 1: bloque común de definiciones (literal de la spec) con versión y huella, extracción, completitud y circulares sin «dividí», «fragmento más corto» ni divisiones, con encabezado del punto, ejemplos balanceados, motivos nuevos, lotes de 3.000 a 4.000 tokens y la versión y la huella registradas en cada pedido; el informe de revisión entra al repositorio con su test de cobertura y de versiones congeladas | REQ-102, REQ-101, REQ-106 | T-234, T-250 | pendiente |
| T-252 | Instrucciones de la matriz, parte 2: filtro A y B con el bloque común, sin «mantené ante la duda» (la duda va a sugerencia), `razonamiento` antes de la decisión, B rehecha, `decide()` revisada, ejemplos 4 y 4 y lotes de 5 a 8 filas | REQ-102, REQ-106 | T-236 | pendiente |
| T-237 | Instrucciones de la evaluación (evaluación, contraste, cláusulas): `razonamiento`, citas y externo antes del veredicto en el esquema, cita de la oración completa en lugar del «fragmento mínimo», «cada condición con su dato», definición de la duda, ejemplos balanceados, pregunta dirigida a la Comisión, reintento con memoria, versión y huella en cada pedido | REQ-104, REQ-105, REQ-106 | T-235, T-252 | pendiente |
| T-251 | Código listo para medir otro modelo: el cuerpo del pedido de lotes dice el modelo que lo atiende y los tokens de los lotes se cuentan con ese motor (hoy con `generation`, que es Gemma) | REQ-107 | T-236, T-252, T-237 | pendiente |
| T-238 | Medidas de la 015 en `medir_matriz` y `medir_evaluacion` (filas conservadas, pedazos sin sujeto, recall sin las entradas excluidas, celdas del Portal, «no determinado» que no espera un documento ausente, forma de las preguntas) y listas esperadas ajustadas con huella y visto bueno del Coordinador | REQ-101, REQ-102, REQ-103, REQ-104, REQ-105 | T-233, T-234, T-235 | pendiente |
| T-239 | Medición del 12B con el uso corregido: caso chico como corte vertical, caso-00 (matriz, revisión como en T-229 y evaluación de las 3 ofertas) y casos 01 a 06 (matriz), contra los umbrales del plan: 70 % de filas conservadas, 0 pedazos sin sujeto, 95 % de la lista esperada, Portal 100 % y 0, 12 de 81 «no determinado» o menos, 0 contradicciones, 100 % literal, 100 % de preguntas conformes, 60 minutos y 22.000 MiB | REQ-101, REQ-102, REQ-103, REQ-104, REQ-105 | T-237, T-238, T-251 | pendiente |
| T-240 | Ronda de ajuste única, solo si T-239 no llega a algún umbral: todos los hallazgos en una sola tarea, un commit por hallazgo; se cierra sin cambios si T-239 cumple todo | REQ-101, REQ-102, REQ-103, REQ-104, REQ-105 | T-239 | pendiente |
| T-241 | Repetición completa de la medición de T-239 sobre el commit ajustado; es la referencia del 12B para la comparación. Solo si hubo T-240; sin una segunda ronda de ajuste | REQ-101, REQ-102, REQ-103, REQ-104, REQ-105 | T-240 | pendiente |
| T-242 | Servicio de los candidatos: un archivo de compose por modelo (Qwen3.8-27B y Qwen3.6-35B-A3B) a la manera del ADR-0042, opciones de descarga con revisión fijada, huellas en `scripts/models.sha256` y tests de coherencia con el compose base | REQ-107 | — | pendiente |
| T-243 | Qwen3.8-27B en servicio: prueba de humo con texto e imagen, memoria máxima (22.000 MiB), reuso de la caché de prefijo (90 % o más del prefijo), razonamiento nativo apagado (0 tokens de pensamiento) y orden del esquema respetado; velocidad medida | REQ-107 | T-242, T-241 | pendiente |
| T-244 | Comparación de Qwen3.8-27B con el 12B, con el protocolo del ADR-0042 y el uso corregido: caso-00 completo primero (compuerta de salida temprana), después los casos 01 a 06; cada par que cambia se revisa y se clasifica | REQ-107 | T-243 | pendiente |
| T-245 | Qwen3.6-35B-A3B en servicio: las mismas comprobaciones que T-243 con los mismos umbrales | REQ-107 | T-244 | pendiente |
| T-246 | Comparación de Qwen3.6-35B-A3B con el 12B, con el mismo protocolo y los mismos umbrales | REQ-107 | T-245 | pendiente |
| T-247 | ADR de resultado (reservado ADR-0057): adopta o descarta cada candidato con las corridas como evidencia; si adopta, deja preparados sin integrar los cambios de compose base y `entorno.md` para la aprobación del responsable | REQ-107 | T-244, T-246 | pendiente |
| T-248 | Resto de las instrucciones (consecuencias, respaldo, ficha, ficha por renglón, reescritura, visión, informe técnico, consulta, nombre del oferente, datos del procedimiento) y hallazgos pendientes del informe de revisión; huella de cada una; el informe queda con todo corregido o justificado | REQ-106 | T-237, T-240, T-246 | pendiente |
| T-249 | Medición de lo que cambió T-248, solo en las áreas que cambió, con el umbral de que ninguna medida empeore (P7): evals de la 001, fichas, lectura con visión, propuestas de datos y matriz con circulares | REQ-106 | T-248 | pendiente |

## Paralelismo y cola de GPU

- **Primer lote, en paralelo:** T-233 y T-234 no comparten archivos (la regla del Portal contra la matriz). **T-242 también**, en cuanto estén las descargas: sus archivos (compose de candidatos, `scripts/`, sus tests) no los toca ninguna otra tarea hasta T-243.
- **Segundo lote:** T-250 (después de T-233 por `settings.py`; es la única que genera migración) y T-235 (después de T-233 y T-234, necesita `sentences.py` y la lectura del Portal) no comparten archivos y van a la vez.
- **Tercer lote:** T-236 (después de T-234 y T-250) va a la vez que T-235 si esta aún no terminó (T-236 toca la matriz y T-235 la evaluación). T-252 espera a T-236 (comparte `settings.py` y el bloque común). T-238 corre a la vez que T-236, T-252 y T-237 (toca solo los dos módulos y los dos comandos de medición) y espera a T-233, T-234 y T-235.
- **Cuarto lote:** T-237 espera a T-235 y T-252 (comparte `prompting.py`, `evaluate.py` y `settings.py`); T-251 espera a T-237 (renombra llamadas a `count_tokens` en archivos que tocan T-234, T-236, T-252 y T-237).
- **Toda tarea que toca `settings.py` va encadenada:** T-233 (versión de reglas), T-250 (`FILTER_MOTIVES`), T-236 (versiones y lotes de la matriz), T-252 (filtro), T-237 (versiones y salida de la evaluación), T-248 (versiones del resto). Si el Coordinador acepta fusionar a mano ese archivo (cada tarea toca un bloque distinto), T-237 corre en paralelo con T-236 y T-252.
- **Esquema:** T-250 es la única tarea que genera una migración y corre sola entre las que tocan el esquema (modelos y migraciones de `tenders`).
- **Cola de GPU, en este orden y encadenada en la columna «Depende de»:** T-239, T-241 (si hubo ajuste), T-243 (humo del 27B), T-244 (comparación del 27B), T-245 (humo del 35B), T-246 (comparación del 35B), T-249. Los candidatos van de a uno, completos, como pidió el responsable. Cada una empieza cuando la anterior terminó y dejó su `verificacion/T-NNN.md`. T-240 y T-241 se cierran sin cambios si T-239 cumple todo (el eslabón de la cadena queda). T-240, T-247 y T-248 no usan la GPU.
- **Código medido.** `docker-compose.yml` monta `./evaluon` en la aplicación: durante una medición no se integra nada a la carpeta que el compose usa. T-239 a T-246 se corren sobre el mismo commit de `main` (T-241 es la referencia si hubo ajuste), y cada informe nombra el commit. Por eso T-251 va antes de T-239 y T-248 se integra recién después de T-246.
- **Máximo sugerido en paralelo:** dos o tres desarrolladores (el Coordinador debe poder revisar cada resultado contra la spec).

## Detalle

### T-233 · El dato del Portal que coincide propone «cumple»

- **Requisitos:** REQ-103
- **Nivel de verificación:** plena (lógica de decisión y un principio de la constitución).
- **No arranca sin:** T-231 (014) integrada y la confirmación del responsable de la lectura de P3 (ADR-0053).
- **Qué hay que hacer:**
  1. Reescribir `portal_facts.rule` según el ADR-0053: qué exige el pliego por clase de dato (garantía como porcentaje del total del Portal, tolerancia de un centavo; cotización por renglón con todos los renglones del procedimiento; total; CUIT de once dígitos) contra el valor del Portal. Coincide: «cumple» con la cita del Portal escrita por el sistema y la explicación «Fuente: Portal», sin contraste del modelo. Difiere y es comparable: «no cumple» con la diferencia y las dos citas. No es comparable: «no determinado» `falta_coincidencia` con la diferencia. El valor de la oferta (`datos`) distinto del Portal sigue dando `falta_coincidencia`.
  2. `facts`: `regla` (`portal_cumple`, `portal_no_cumple`, `portal_falta_coincidencia`), valores comparados, `version_reglas`. `ASSESSMENT_RULES_VERSION` pasa a `reglas-v8`.
  3. Reescribir los tests marcados `decision_literal` que afirmaban `en_portal` donde ahora corresponde «cumple». Un test por clase de dato, con los casos del diagnóstico: garantía exactamente el 5 % del total; con un centavo de diferencia; con una diferencia mayor; renglones todos cotizados y con faltantes; CUIT igual y distinto; Portal sin el dato (no rige la regla); un «cumple» del Portal nunca sale sin cita del Portal.
  4. Si el caso chico no trae un dato del Portal que coincida y otro que no, sumar los dos con datos inventados.
- **Umbral:** 100 % de los casos de prueba con dato que coincide dan «cumple» con la cita del Portal; 0 casos «cumple» con un dato que no coincide.
- **Archivos:** `evaluon/assessment/portal_facts.py`, `evaluon/assessment/rules.py`, `evaluon/settings.py` (solo `ASSESSMENT_RULES_VERSION`), `tests/assessment/test_portal_facts.py`, `tests/assessment/test_rules.py`, `tests/assessment/test_t175.py`, `tests/assessment/test_hallazgos_t172.py`, `tests/assessment/data/caso-chico/` (datos del Portal si faltan).
- **Verificación:** `docker compose run --rm app pytest tests/assessment -m decision_literal` y `pytest tests/assessment`, y la suite completa una vez al final; `manage.py medir_evaluacion --verificar-decisiones` sin fallas; la página del resultado (`tests/assessment/test_result_page.py`) muestra la celda con la cita del Portal.
- **No tocar:** `combine.py`, `externals.py`, `technical.py`, `unreadable.py`, plantillas, el esquema y el resto de `settings.py`.

### T-234 · Matriz: la cita es la oración completa y el inciso lleva su encabezado

- **Requisitos:** REQ-101
- **Nivel de verificación:** plena (lógica de citas y literalidad, REQ-025).
- **No arranca sin:** T-232 (014) integrada (comparte la fila de la matriz de la sección 2).
- **Qué hay que hacer:**
  1. Crear `evaluon/tenders/proposal/sentences.py` con las funciones de oración que hoy están en `filter.py` (`_sentence_ends`, `sentence_range`, `sentence_bounds`, `ABBREVIATIONS`): `filter.py` las importa sin cambiar su comportamiento ni sus nombres públicos. Agregar `expand_to_sentence(text, span)`: amplía el fragmento al comienzo y al fin de su oración (o inciso, o viñeta); si el fragmento cruza varias, abarca las que toca; si la oración supera `ASSESSMENT_CITATION_MAX_CHARS` queda el fragmento original con la marca `cita_amplia` para revisión.
  2. Aplicar la ampliación donde se ubican las citas de la extracción y la completitud (`Found.span`). Dos fragmentos que se amplían a la misma oración dan una sola fila (una fila por oración, ADR-0054). La cita guardada es el recorte contiguo del texto canónico: `run._check_quote` sigue pasando.
  3. Guardar en el `parsed` de cada pedido el fragmento que señaló el modelo y la oración con sus posiciones.
  4. Encabezado del inciso: `heading_of(segment)` toma el texto del tramo padre por la clave cuando la oración sola no se entiende (inciso de una lista cuyo encabezado termina en «:», oración que empieza en minúscula o con «Esto» o «La misma»). `render_block` de la extracción agrega la línea `Encabezado:` al tramo (contexto que no se cita). La fila de la matriz de la sección 2 muestra el encabezado sobre la cita (una línea; sin otros cambios de pantalla).
  5. Verificar sin GPU repitiendo la resolución de citas sobre las salidas del modelo ya guardadas (`tenders_run_step.raw_output`) de la propuesta de T-229, restaurada del respaldo `backups/evaluon-2026-10-10-previo-T229.dump` en una base aparte: ningún fragmento queda sin sujeto y las 13 citas que la Comisión amplió a mano coinciden con la oración que calcula el código.
- **Archivos:** `evaluon/tenders/proposal/sentences.py` (nuevo), `evaluon/tenders/proposal/quotes.py`, `evaluon/tenders/proposal/extraction.py`, `evaluon/tenders/proposal/completeness.py`, `evaluon/tenders/proposal/run.py`, `evaluon/tenders/proposal/filter.py` (solo las importaciones), `evaluon/tenders/services/matrix_page.py`, `evaluon/templates/journey/temas/s2_matriz.html` (una línea), `tests/tenders/test_sentences.py` (nuevo), `tests/tenders/test_extraction.py`, `tests/tenders/test_completeness.py`, `tests/tenders/test_quotes.py`, `tests/tenders/test_filter.py`.
- **Verificación:** `docker compose run --rm app pytest tests/tenders` y la suite completa una vez; tests de `sentences.py` con abreviaturas, incisos, listas con «:» y puntos de cierre; test de que dos fragmentos de una oración dan una fila; test de que la cita guardada es igual al recorte del canónico; la repetición sobre T-229 (punto 5) con sus cifras en `verificacion/T-234.md`.
- **No tocar:** instrucciones (`prompts/`), `settings.py`, el esquema, la lógica del filtro más allá de las importaciones.

### T-250 · Esquema de los motivos de descarte nuevos

- **Requisitos:** REQ-102
- **Nivel de verificación:** plena (esquema, restricciones y migración).
- **No arranca sin:** T-233 integrada (comparte `settings.py`) y T-232 (014) integrada (por si trae su propia migración de `tenders`). Corre sola entre las tareas que tocan el esquema.
- **Qué hay que hacer:**
  1. Sumar a `DiscardReason` (tramos) los motivos nuevos de la extracción: consecuencia, condición opcional, pago o factura, forma de presentar por el Portal y compromiso al presentarse; y a `FilterMotive` y a `FILTER_MOTIVES` (filas) los que el filtro necesita y todavía no tiene (`consecuencia_sancion` ya existe). Los nombres exactos los fija esta tarea (snake_case en español, con etiqueta legible), de acuerdo con el ADR-0054, regla 5.
  2. Una migración de `tenders` que actualiza las restricciones de valores válidos (`tenders_disposition_discard_reason_valid`, `tenders_discarded_row_reason_valid`). Solo agrega valores: las filas existentes no cambian. Se migra desde cero y hacia atrás.
  3. Los esquemas que arman las listas de motivos con `DiscardReason.values` (extracción, circulares) las toman solos; ningún texto de instrucción cambia en esta tarea.
  4. La pantalla de descartadas muestra la etiqueta de cada motivo nuevo (las etiquetas salen del modelo).
- **Archivos:** `evaluon/tenders/models.py`, una migración nueva en `evaluon/tenders/migrations/`, `evaluon/settings.py` (solo `FILTER_MOTIVES`), `tests/tenders/test_models.py`, `tests/tenders/test_schema_014.py` (si lista valores), `tests/tenders/test_discarded.py`.
- **Verificación:** `pytest tests/tenders` y la suite completa una vez; migrar desde cero y hacia atrás; test de que `FILTER_MOTIVES` y `FilterMotive.values` coinciden; test de que cada motivo nuevo es válido en `Disposition` y `DiscardedRow` y uno inexistente es rechazado. `tests/tenders/test_filter.py` (que las instrucciones nombran cada motivo) falla hasta T-252: se marca `xfail` con el motivo y T-252 lo levanta.
- **No tocar:** instrucciones, `filter.py`, `extraction.py`, otras apps.

### T-235 · Evaluación: oración completa de la oferta, Portal para el modelo, contexto en el contraste y preguntas a la Comisión

- **Requisitos:** REQ-103, REQ-104, REQ-105
- **Nivel de verificación:** plena (lógica y datos que ve el modelo).
- **No arranca sin:** T-233 (lee los datos del Portal), T-234 (necesita `sentences.py`) y T-231 (014) integradas.
- **Qué hay que hacer:**
  1. `citations.locate_quote` devuelve la cita ampliada a la oración completa del texto canónico del documento (con el tope de caracteres de las citas); la cita del Portal no se toca.
  2. `grounds.py`: el requisito llega con su punto completo y la oración citada entre `<<< >>>` (hoy solo la cita; el valor por defecto estaba en la oración vecina: requisitos 20 y 62 del caso-00).
  3. **El Portal le llega al modelo:** módulo `portal_block.py` que arma el bloque `[P1]` «Datos del Portal» de la oferta (moneda, total, garantías, precios por renglón) con las lecturas de `portal_facts`, antes del requisito. El alias `P…` es citable: el sistema escribe el texto de la cita desde las columnas (cita de clase Portal, nunca el texto del modelo). Un alias inexistente se descarta como los demás.
  4. El contraste recibe, además de la cita, su contexto: las oraciones vecinas de la misma página y, si la hay, la cita del Portal, con tope (constante del módulo, registrada en el `parsed` del pedido). `build_contrast_messages` y `_contrast_pair` pasan a `(título, página, texto, contexto)`.
  5. Preguntas: reemplazar `combine.fixed_question` por una pregunta armada con requisito (la cita del pliego), conclusión del sistema y motivo, y texto de la oferta (documento y página), dirigida a la Comisión. La pregunta que escribe el modelo se acepta solo si no se dirige al oferente («¿Podría el oferente…?», «solicitamos al oferente…») y se le antepone esa misma información; si no cumple, la arma el código. Ninguna pregunta es un texto fijo sin datos.
  6. Tests con los patrones de las 17 preguntas de T-229 (9 de «no pudo corroborar», 1 de «falta un dato», 3 dirigidas al oferente, 4 propias del modelo) y con el caso del requisito 10 de la oferta 1 (precio en el Portal, no en los PDF).
- **Archivos:** `evaluon/assessment/citations.py`, `evaluon/assessment/grounds.py`, `evaluon/assessment/portal_block.py` (nuevo), `evaluon/assessment/combine.py`, `evaluon/assessment/prompting.py`, `evaluon/assessment/services/evaluate.py`, `evaluon/assessment/services/questions.py`, `tests/assessment/test_citations.py`, `tests/assessment/test_combine.py`, `tests/assessment/test_evaluate.py`, `tests/assessment/test_questions.py`, `tests/assessment/test_portal_block.py` (nuevo).
- **Verificación:** `pytest tests/assessment` y la suite completa una vez; test de que la cita ampliada es un recorte contiguo y literal; test de que la cita de clase Portal la escribe el sistema; test de que ninguna pregunta se genera sin requisito, conclusión y texto; test de que una pregunta dirigida al oferente se rechaza; el contraste recibe el contexto (se inspecciona el pedido guardado).
- **No tocar:** `portal_facts.py` (es de T-233), instrucciones, `settings.py`, el esquema, las plantillas.

### T-236 · Instrucciones de la matriz, parte 1: bloque común, extracción, completitud y circulares

- **Requisitos:** REQ-102, REQ-101, REQ-106
- **Nivel de verificación:** plena (instrucciones al modelo).
- **No arranca sin:** T-234 y T-250 integradas. Entrada: el informe `revision-instrucciones.md`, secciones 4.1, 4.2, 4.6 y 5.
- **Qué hay que hacer:**
  1. **Bloque común** `matriz-definiciones-v1.md`: «qué es un requisito de la oferta», copiado literal de la tabla de decisiones de la spec 015 (no entran pago, moneda de pago, factura, forma de presentar por el Portal ni compromisos que se cumplen al presentarse; sí la moneda en que se cotiza; no consecuencias ni obligaciones del organismo; una condición que solo vale si el oferente **puede no usar** una opción entra solo como condición de esa opción; las condiciones de la forma de garantía que el oferente tiene que elegir, según la regla provisoria del ADR-0054, pendiente con el responsable). El código lo incluye en cada instrucción de la matriz que lo necesita; tiene su versión en `MATRIX_PROMPT_VERSIONS` y su huella.
  2. `matriz-extraccion-v4.md`: usa el bloque; una fila por oración completa, de la mayúscula al punto; la línea `Encabezado:` es contexto que no se cita; fuera «dividí las enumeraciones», «copiá el fragmento más corto» y el ejemplo de pago; las condiciones dichas como efecto son requisito si nombran una condición propia y consecuencia si solo remiten a otra; «ante la duda, proponé de más» se queda solo aquí y limitado a oraciones que exigen algo a todas las ofertas; usa los motivos de descarte nuevos; ejemplos nuevos de otro objeto de contratación, con la forma de los documentos reales (incisos con encabezado, enumeraciones en una oración, condiciones opcionales, consecuencias) y sin ninguno de fragmento sin sujeto.
  3. `matriz-completitud-v4.md`: usa el bloque; sin «divisiones» (instrucción y esquema: solo suma oraciones completas que faltan); sin «ante la duda, proponé de más»; `OBLIGATION_MARKERS` de `run.py` sin «desestim» (va a consecuencias); el ejemplo del descarte recuperado por opcional se corrige; oración completa en lugar de «fragmento más corto».
  4. Circulares: `matriz-circulares-v3.md` (efecto sobre citas) y `matriz-circulares-v6.md` (cambios) con el bloque, la clase económica sin «forma y plazo de pago», el ejemplo de «Donde dice…» con el motivo correcto, y oración completa; `MATRIX_PROMPT_VERSIONS` apunta a las versiones nuevas.
  5. Lotes: `MATRIX_BATCH_INPUT_TOKENS` de 1.500 a un valor entre 3.000 y 4.000, junto con el encabezado; los máximos de salida que hagan falta.
  6. Registro: cada instrucción guarda su versión y su huella SHA-256 en `prompt_versions` y en el `parsed` de cada pedido; un ayudante común carga la instrucción y calcula la huella.
  7. Copiar el informe de revisión al repositorio (`specs/015-uso-y-eleccion-del-modelo/revision-instrucciones.md`) sin texto de casos: instrucción, hallazgo, gravedad, estado. Crear `tests/test_instrucciones_revisadas.py`: arma la lista de instrucciones vigentes (las de `MATRIX_PROMPT_VERSIONS`, `OFFERS_PROMPT_VERSIONS`, `ASSESSMENT_PROMPT_VERSIONS`, `ASSESSMENT_VISION_PROMPT_VERSION`, `consulta`, `informe-tecnico`, `oferente-nombre` y `procedimiento-datos`), comprueba que el informe nombra a todas y que las versiones publicadas están congeladas con su huella (como `scripts/models.sha256`).
- **Archivos:** `evaluon/tenders/prompts/matriz-definiciones-v1.md`, `matriz-extraccion-v4.md`, `matriz-completitud-v4.md`, `matriz-circulares-v3.md`, `matriz-circulares-v6.md`, `evaluon/tenders/proposal/extraction.py`, `completeness.py`, `circulars.py`, `circular_changes.py` (cargadores y registro de versión), `evaluon/tenders/proposal/run.py` (`OBLIGATION_MARKERS` y `prompt_versions`), `evaluon/settings.py`, `specs/015-uso-y-eleccion-del-modelo/revision-instrucciones.md`, `tests/tenders/test_extraction.py`, `test_completeness.py`, `test_circulars.py`, `test_circular_changes.py`, `tests/test_instrucciones_revisadas.py` (nuevo).
- **Verificación:** `pytest tests/tenders tests/test_instrucciones_revisadas.py` y la suite completa una vez. Tests: las instrucciones nuevas no contienen «dividí», «fragmento más corto», «mantené ante la duda» ni «ante la duda, proponé de más» (salvo en la extracción) y sí el bloque común literal; los ejemplos están balanceados; cada pedido guardado trae su versión y su huella; el informe cubre el 100 % de las instrucciones vigentes. Sin GPU (modelo guionado: `tests/tenders/scripted.py`); la prueba con el modelo real es el primer paso de T-239.
- **No tocar:** `assessment/`, `filter.py` y la instrucción del filtro (T-252), el esquema.

### T-252 · Instrucciones de la matriz, parte 2: filtro A y B

- **Requisitos:** REQ-102, REQ-106
- **Nivel de verificación:** plena (instrucciones y lógica de destino).
- **No arranca sin:** T-236 integrada. Entrada: el informe, sección 4.3 y las pruebas 1 a 5.
- **Qué hay que hacer:**
  1. `matriz-filtro-v3.md`: usa el bloque común; fuera «mantené ante la duda» (tres veces); criterios para condición opcional («opción que el oferente puede no usar» contra «forma que tiene que elegir»), forma de presentación por el Portal, compromiso por presentarse y pago, con los motivos nuevos; ejemplos de «mantener» y «descartar» 4 y 4, uno por cada exclusión, sin el de continuación («y conforme a…»), que ahora resuelve la oración completa.
  2. `filter.py`: `razonamiento` (una oración, con tope) como primera propiedad de las preguntas A y B, con su lectura y registro; B rehecha con las mismas definiciones (o quitada, si la medición del diseño muestra que A basta: la decisión queda escrita en el ADR-0054); `decide()` y la tabla de destinos del ADR-0021 revisadas: un acuerdo de A (motivo de la lista e indicio ubicado) alcanza cuando B no contradice, y la duda real va a sugerencia; `RULE_VERSION` nueva.
  3. `FILTER_BATCH_ROWS` de 15 a un valor entre 5 y 8, con el punto completo de cada fila en el pedido.
  4. Versión y huella en el `parsed` de cada pedido del filtro; `settings.py` apunta a `matriz-filtro-v3`.
  5. Levantar el `xfail` de T-250: las instrucciones nombran cada motivo de `FILTER_MOTIVES` y ningún otro.
  6. Condiciones de la forma de garantía (pagaré o póliza): regla provisoria del ADR-0054; si el Coordinador ya trae la respuesta del responsable, se aplica la respuesta.
- **Archivos:** `evaluon/tenders/prompts/matriz-filtro-v3.md`, `evaluon/tenders/proposal/filter.py`, `evaluon/settings.py`, `specs/015-uso-y-eleccion-del-modelo/revision-instrucciones.md`, `tests/tenders/test_filter.py`, `tests/tenders/test_suggestions.py`, `tests/tenders/test_discarded.py`, `tests/test_instrucciones_revisadas.py`.
- **Verificación:** `pytest tests/tenders` y la suite completa una vez. Tests: sin frases prohibidas; los ejemplos de «mantener» y «descartar» están entre el 40 y el 60 %; el esquema pone `razonamiento` primero; la tabla de destinos nueva (acuerdo, desacuerdo, duda, una sola respuesta válida); la guarda de oraciones compartidas sigue; cada pedido guarda su versión y su huella.
- **No tocar:** `extraction.py`, `completeness.py`, el bloque común (salvo un hallazgo de T-239), `assessment/`.

### T-237 · Instrucciones de la evaluación

- **Requisitos:** REQ-104, REQ-105, REQ-106
- **Nivel de verificación:** plena (instrucciones al modelo y esquema de salida).
- **No arranca sin:** T-235 y T-252 integradas. Entrada: el informe, secciones 4.7 a 4.9.
- **Qué hay que hacer:**
  1. `evaluacion-v6.md`: orden del esquema `razonamiento` (2 a 4 oraciones), citas, `externo` e `ilegible`, `datos`, `resultado`, `explicacion`, `pregunta`; la cita es la oración completa (se saca «elegí el fragmento mínimo»); se saca «ante la duda… elegí no_determinado» y la duda se define (qué dato falta o qué texto contradice); «revisá cada condición; si a una le falta el dato no es cumple»; `datos` copia el monto del mismo concepto que pide el requisito; el tipo 5 de externo se alinea con la regla vigente (lo externo es la verificación en el Registro, no la declaración); el bloque `[P…]` del Portal y cómo se cita; la pregunta es para la Comisión: nombra el requisito, la conclusión y el texto, y nunca le pide algo al oferente (eso es subsanación, REQ-060); ejemplos balanceados (3 «cumple», uno con el Portal; 2 «no cumple»; 2 «no consta»; 3 «no determinado»; los externos, a la regla del catálogo); el cierre del mensaje es un recordatorio de tres líneas con el orden de la salida.
  2. `contraste-v3.md`: explica que recibe la oración, su contexto y la cita del Portal; `razonamiento` (el motivo) antes de la respuesta; sumar un «parcial» de un requisito con dos condiciones.
  3. `clausulas-v3.md`: `motivo` antes de `estado`; el ejemplo de la pregunta es a la Comisión, con la cláusula y lo que se leyó.
  4. Código: `razonamiento` como primera propiedad de `evaluation_schema`, `CONTRAST_SCHEMA` y `CLAUSES_SCHEMA`, y los demás campos en el orden nuevo; se lee y se guarda en el `parsed`; los máximos de salida suben lo justo; el reintento le muestra al modelo su respuesta anterior (turno del asistente) y la cita que no se ubicó y le pide la oración completa; `ASSESSMENT_PROMPT_VERSIONS` apunta a las versiones nuevas; versión y huella en cada pedido.
  5. Hallazgos de gravedad alta del informe sobre estas tres instrucciones: corregidos o justificados en `revision-instrucciones.md`.
- **Archivos:** `evaluon/assessment/prompts/evaluacion-v6.md`, `contraste-v3.md`, `clausulas-v3.md`, `evaluon/assessment/prompting.py`, `evaluon/assessment/services/evaluate.py`, `evaluon/settings.py`, `specs/015-uso-y-eleccion-del-modelo/revision-instrucciones.md`, `tests/assessment/test_evaluate.py`, `tests/assessment/test_combine.py`, `tests/assessment/test_evaluation.py`, `tests/assessment/fakes.py`, `tests/test_instrucciones_revisadas.py`.
- **Verificación:** `pytest tests/assessment tests/test_instrucciones_revisadas.py` y la suite completa una vez; tests de forma de las instrucciones (frases prohibidas, definiciones, balance de ejemplos), de los esquemas (`razonamiento` primero y el orden de los demás), de la lectura de la salida con y sin razonamiento, del reintento con memoria y del registro de la versión y la huella en cada pedido. Sin GPU; la prueba con el modelo real es el primer paso de T-239.
- **No tocar:** `combine.py`, `citations.py`, `grounds.py`, `portal_block.py` (son de T-235), `portal_facts.py`, el esquema de la base, las instrucciones de la matriz.

### T-251 · Código listo para medir otro modelo

- **Requisitos:** REQ-107
- **Nivel de verificación:** plena (comportamiento común de todos los pedidos de lotes).
- **No arranca sin:** T-236, T-252 y T-237 integradas (renombra llamadas en archivos que ellas tocan).
- **Qué hay que hacer:**
  1. `generation.py`: el cuerpo registrado de un pedido de lotes dice el alias del modelo del motor que lo atiende (`GENERATION_BATCH_MODEL`), no el de `generation`.
  2. `generation.count_tokens_batch` (misma interfaz, contra `GENERATION_BATCH_URL`): los pedidos de lotes cuentan sus tokens con el tokenizador del motor que los va a responder. Los llamadores de los lotes (`extraction`, `completeness`, `consequences`, `circulars`, `circular_changes`, `norm_support`, `assessment/documents.py`) lo usan; las consultas de normativa (`queries/`) siguen contando con `generation`. Con el 12B los dos coinciden y no cambia ningún número.
  3. El comentario de `settings.py` que presenta `enable_thinking` como propia de Gemma se corrige (la variable es la misma en Qwen3.x).
  4. Los dobles de `tests/conftest.py` que reemplazan `count_tokens` reemplazan también la función nueva.
- **Archivos:** `evaluon/ai/generation.py`, `evaluon/assessment/documents.py`, `evaluon/tenders/proposal/extraction.py`, `completeness.py`, `consequences.py`, `circulars.py`, `circular_changes.py`, `norm_support.py`, `evaluon/settings.py` (solo el comentario), `tests/conftest.py`, `tests/ai/` (tests de `generation`), `tests/tenders/test_generation_batch.py`.
- **Verificación:** `pytest` de `tests/ai`, `tests/tenders` y `tests/assessment` y la suite completa una vez; test de que el cuerpo de un pedido de lotes lleva el alias del lote y el de una consulta, el de `generation`; test de que los llamadores de lotes cuentan con el motor de lotes (con el doble); con el 12B el conteo da lo mismo que antes sobre el caso chico.
- **No tocar:** instrucciones, el compose, `queries/`.

### T-238 · Medidas de la 015 y listas esperadas

- **Requisitos:** REQ-101, REQ-102, REQ-103, REQ-104, REQ-105
- **Nivel de verificación:** plena (lógica de medición).
- **Qué hay que hacer:**
  1. `medir_matriz`: filas conservadas por caso y en total (filas firmes con pareja en la lista esperada); pedazos sin sujeto (comprobación mecánica con `sentences.py`: la cita empieza y termina en límites de oración o de inciso con encabezado); recall sin contar las entradas marcadas `excluida_por_decision`; resumen público con cifras.
  2. `medir_evaluacion`: «no determinado» que no espera un documento ausente (denominador: las celdas del caso, 81 en el caso-00; no cuentan las técnicas ni las externas); celdas del Portal contra la lista `portal` del caso (cumple con cita del Portal; 0 cumple con dato que no coincide); forma de cada pregunta (requisito, conclusión, texto, dirigida a la Comisión) y la plantilla local `muestra-preguntas.md` con todas las preguntas, para leerlas una por una.
  3. Listas esperadas locales (fuera del repositorio): en `matriz-esperada.yaml` de los casos 00 a 06, marcar `excluida_por_decision` las entradas de pago, moneda de pago, factura, forma de presentar por el Portal y compromisos al presentarse; en el caso-00, agregar `portal` por celda (las 21 de T-229: 17 y 4). Los lectores y `--verificar-esperada` aceptan los campos nuevos. Cada lista modificada lleva su huella y el visto bueno del Coordinador antes de medir; se informa cuántas entradas se marcaron.
  4. Caso chico: sumar a `evaluacion-esperada.yaml` los campos nuevos.
- **Archivos:** `evaluon/tenders/evaluation.py`, `evaluon/tenders/management/commands/medir_matriz.py`, `evaluon/assessment/evaluation.py`, `evaluon/assessment/management/commands/medir_evaluacion.py`, `tests/tenders/test_evaluation.py`, `tests/assessment/test_evaluation.py`, `tests/assessment/data/caso-chico/evaluacion-esperada.yaml`.
- **Verificación:** `pytest tests/tenders/test_evaluation.py tests/assessment/test_evaluation.py` y la suite completa una vez; `medir_matriz --verificar-esperada` y `medir_evaluacion --verificar-esperada` sobre cada lista ajustada sin fallas; las medidas nuevas sobre las corridas ya guardadas de T-229 reproducen las cifras del diagnóstico (22 %, 38 de 81).
- **No tocar:** `portal_facts.py`, `combine.py`, `prompting.py`, `evaluate.py`, instrucciones, `settings.py`.

### T-239 · Medición del 12B con el uso corregido

- **Requisitos:** REQ-101, REQ-102, REQ-103, REQ-104, REQ-105
- **Nivel de verificación:** plena. Usa la GPU: ninguna otra tarea a la vez.
- **No arranca sin:** la respuesta del responsable sobre la forma de garantía aplicada a la spec y al ADR-0054.
- **Qué hay que hacer, en este orden:**
  0. Fijar el commit de `main`; `medir_evaluacion --verificar-decisiones`, `--verificar-esperada` y `medir_matriz --verificar-esperada` sin fallas; el servidor con el 12B y el contexto de 32.768.
  1. **Caso chico (corte vertical).** Matriz y evaluación completas con el modelo real. Si falla en forma (salida inválida, `razonamiento` no primero, versión o huella no registradas, tiempo desmedido), se corrige antes de seguir y no cuenta como ronda: es una falla de T-236, T-252 o T-237.
  2. **Caso-00, matriz.** Medición y revisión de la matriz propuesta por el testeador con los criterios y el motivo por fila de T-229 (fila conservada, corregida o quitada).
  3. **Caso-00, evaluación** de las 3 ofertas sobre la matriz validada de T-229 (81 celdas, la misma en todas las corridas). Lectura una por una de todas las preguntas.
  4. **Casos 01 a 06, matriz**, de a uno.
- **Umbral (el del plan):** 70 % de filas conservadas, 0 pedazos sin sujeto, 95 % de la lista esperada, Portal 100 % y 0, 12 de 81 «no determinado» o menos, 0 contradicciones, 100 % de citas literales, 100 % de preguntas conformes, caso-00 completo en 60 minutos y 22.000 MiB.
- **Qué entrega:** `specs/015-uso-y-eleccion-del-modelo/verificacion/T-239.md` con el commit, cada medida contra su umbral, el tiempo de cada paso, la memoria máxima, los hallazgos agrupados por causa y qué pasa a la lista de revisión; la corrida completa queda fuera del repositorio.
- **Archivos:** solo `specs/015-uso-y-eleccion-del-modelo/verificacion/T-239.md`.
- **No tocar:** código, instrucciones, listas esperadas ni umbrales. Un hallazgo es del siguiente paso, no un ajuste.

### T-240 · Ronda de ajuste única

- **Requisitos:** REQ-101, REQ-102, REQ-103, REQ-104, REQ-105
- **Nivel de verificación:** plena (lógica e instrucciones).
- **Qué hay que hacer:** si T-239 no llegó a algún umbral, corregir **todos** los hallazgos en esta sola tarea, con un commit por hallazgo y su test que falla antes y pasa después. Cada corrección es de las causas que T-239 documentó (cita, definiciones, motivos, regla del Portal, preguntas, instrucciones). Si T-239 cumplió todo, se cierra sin cambios y T-241 no se hace.
- **Archivos:** los de T-233 a T-237, T-250 y T-252 que el hallazgo señale, y `specs/015-uso-y-eleccion-del-modelo/revision-instrucciones.md` si cambia una instrucción. Ningún archivo de T-242 en adelante.
- **Verificación:** los tests del área de cada hallazgo y la suite completa una vez.
- **No tocar:** umbrales, lista esperada, instrucciones que ningún hallazgo señale, el servicio de candidatos.

### T-241 · Repetición de la medición sobre el ajuste

- **Requisitos:** REQ-101, REQ-102, REQ-103, REQ-104, REQ-105
- **Nivel de verificación:** plena. Usa la GPU.
- **Qué hay que hacer:** repetir T-239 completo sobre el commit de T-240 (es la referencia del 12B para la comparación: todo lo demás tiene que ser idéntico). Sin una segunda ronda de ajuste: lo que falte pasa con su impacto a la lista de revisión con el primer producto (ADR-0024), salvo que se pierda un requisito o se viole un principio.
- **Archivos:** `specs/015-uso-y-eleccion-del-modelo/verificacion/T-241.md`.
- **No tocar:** código, instrucciones, listas ni umbrales.

### T-242 · Servicio de los candidatos

- **Requisitos:** REQ-107
- **Nivel de verificación:** plena (configuración del entorno y principios P4 y P5).
- **No arranca sin:** `descargas-modelos.md` indicando que los cuatro archivos están completos.
- **Qué hay que hacer:**
  1. `scripts/models.sha256`: cuatro líneas (Qwen3.8-27B-UD-Q4_K_M, su `mmproj-F16`, Qwen3.6-35B-A3B-UD-IQ4_XS, su `mmproj-F16`), con la huella calculada con `sha256sum` sobre el archivo bajado y comparada con la que informó la API de Hugging Face (ADR-0056). Si no coinciden, se frena y se avisa.
  2. `scripts/fetch_models.sh`: las opciones `--qwen38-27b` y `--qwen36-35b`, cada una con su lista aparte y la URL fijada a la revisión completa leída de la API, como `--modelo-grande`.
  3. `docker-compose.qwen38-27b.yml` y `docker-compose.qwen36-35b.yml`: reemplazan solo `generation_batch` (modelo, alias, `--mmproj`, el mismo contexto, `--parallel 1`, `--offline`, `--cache-ram`, sin pensamiento) y las variables `GENERATION_BATCH_*` de `app` y `worker`, a la manera de `docker-compose.modelo-grande.yml`. Las banderas de la caché de prefijo y del tipo de caché quedan comentadas para que las fije T-243 o T-245. El compose base no cambia.
  4. `docker-compose.yml`: montar los dos archivos nuevos en la aplicación, solo para los tests de coherencia (como el del 26B).
  5. Tests de coherencia: cada archivo adicional es igual al compose base salvo modelo, alias, proyector y las banderas declaradas.
  6. `specs/015-uso-y-eleccion-del-modelo/entorno.md`: cómo bajar, levantar y volver al 12B.
- **Archivos:** `scripts/models.sha256`, `scripts/fetch_models.sh`, `docker-compose.qwen38-27b.yml`, `docker-compose.qwen36-35b.yml`, `docker-compose.yml` (solo los montajes), `tests/test_compose_env.py`, `tests/tenders/test_generation_batch.py` (comparte archivo con T-251: la que llegue segunda integra con cuidado), `specs/015-uso-y-eleccion-del-modelo/entorno.md`.
- **Verificación:** `docker compose -f docker-compose.yml -f docker-compose.qwen38-27b.yml config` y el mismo con el otro archivo, sin errores; `scripts/fetch_models.sh --qwen38-27b` y `--qwen36-35b` informan «OK (ya estaba)» con la huella correcta, sin descargar; `pytest tests/test_compose_env.py tests/tenders/test_generation_batch.py` y la suite completa una vez. No usa la GPU.
- **No tocar:** el servicio `generation_batch` del compose base, `settings.py`, el código de la aplicación, `docker-compose.modelo-grande.yml`.

### T-243 · Qwen3.8-27B en servicio

- **Requisitos:** REQ-107
- **Nivel de verificación:** plena. Usa la GPU.
- **No arranca sin:** T-242 integrada y la GPU libre (T-239 o, si hubo ajuste, T-241 terminada).
- **Qué hay que hacer:** levantar `generation_batch` con `docker-compose.qwen38-27b.yml` (`/health`, `n_ctx` de 32.768 en `/props`, plantilla y rol de sistema en `/props`) y comprobar, cada una con su registro:
  1. **Texto:** un pedido con el esquema de la evaluación y otro con el del filtro devuelven JSON válido con `razonamiento` primero y el orden de las demás propiedades respetado.
  2. **Imagen:** una página de `tests/assessment/data/vision/` da una transcripción no vacía.
  3. **Memoria:** máximo observado en reposo y con un pedido de unos 30.000 tokens; **22.000 MiB o menos**. Si pasa, el único ajuste permitido es la caché de claves y valores en `q8_0`; se repite y se registra.
  4. **Caché de prefijo:** dos pedidos con el mismo prefijo de unos 15.000 tokens y requisitos distintos: el segundo reutiliza **90 % o más** de los tokens del prefijo. Si no, probar las banderas de puntos de control de la caché (ADR-0056) y registrar.
  5. **Razonamiento apagado:** 0 tokens de pensamiento en la salida (sin `<think>` ni `reasoning_content`) y `completion_tokens` dentro del tope.
  6. **Velocidad y conteo:** tokens por segundo de generación y de lectura del prompt, para estimar los 60 minutos del caso-00; el conteo de tokens de un lote con el tokenizador del candidato.
- **Umbral:** 3, 4 y 5 se cumplen; si no, el candidato se descarta en esta tarea con esa evidencia, sin pasar a T-244.
- **Archivos:** `docker-compose.qwen38-27b.yml` (solo las banderas que la prueba determine), `specs/015-uso-y-eleccion-del-modelo/verificacion/T-243.md`.
- **No tocar:** código, instrucciones, el compose base.

### T-244 · Comparación de Qwen3.8-27B

- **Requisitos:** REQ-107
- **Nivel de verificación:** plena. Usa la GPU.
- **Qué hay que hacer:** el protocolo del ADR-0056 (todo igual salvo el modelo, sin ajustes al candidato): mismo commit que la referencia del 12B (T-239, o T-241 si hubo ajuste), mismas instrucciones, listas esperadas y parámetros. (1) Caso-00 completo: matriz, revisión como en T-229 y evaluación de las 3 ofertas sobre la matriz validada de T-229; si no entra en 22.000 MiB, tarda más de 60 minutos o da una contradicción con el dictamen, se descarta sin correr los casos 01 a 06. (2) Casos 01 a 06, matriz, de a uno. (3) Cada par o fila que cambia respecto del 12B se revisa y se clasifica (mejora real, empeora, cambia lo que se cuenta); la mejora tiene que venir de pares que el 12B resolvía mal por no ver o no razonar.
- **Umbral (REQ-107):** cumple REQ-101 a REQ-105 al menos tan bien como el 12B; mejora al menos una medida con razones por par; 0 contradicciones; 100 % de citas literales; no empeora tiempo ni memoria; entra en 22.000 MiB; caso-00 completo en 60 minutos o menos.
- **Archivos:** `specs/015-uso-y-eleccion-del-modelo/verificacion/T-244.md` (cifras y conclusiones; la clasificación par por par queda fuera del repositorio).
- **No tocar:** código, instrucciones, listas ni umbrales; sin segunda ronda.

### T-245 · Qwen3.6-35B-A3B en servicio

- **Requisitos:** REQ-107
- **Nivel de verificación:** plena. Usa la GPU.
- **Qué hay que hacer:** las seis comprobaciones de T-243 con `docker-compose.qwen36-35b.yml`, con los mismos umbrales (cuantización IQ4_XS: si la memoria no entra, se descarta y T-246 no se hace).
- **Archivos:** `docker-compose.qwen36-35b.yml` (solo las banderas que la prueba determine), `specs/015-uso-y-eleccion-del-modelo/verificacion/T-245.md`.
- **No tocar:** lo mismo que T-243.

### T-246 · Comparación de Qwen3.6-35B-A3B

- **Requisitos:** REQ-107
- **Nivel de verificación:** plena. Usa la GPU.
- **Qué hay que hacer:** lo mismo que T-244 con el segundo candidato y la misma referencia del 12B. Se mide aunque el primero se adopte, para cerrar la pregunta del responsable (por defecto; ver «Puntos para el responsable» del plan).
- **Archivos:** `specs/015-uso-y-eleccion-del-modelo/verificacion/T-246.md`.
- **No tocar:** lo mismo que T-244.

### T-247 · ADR de resultado de la comparación

- **Requisitos:** REQ-107
- **Nivel de verificación:** liviana (documento): revisión del Coordinador contra los informes de T-243 a T-246.
- **Qué hay que hacer:** redactar el ADR-0057 con `docs/adr/0000-plantilla.md`, en estado «propuesto»: por cada candidato, la decisión (adoptar o descartar), las medidas de T-243 a T-246 contra el umbral de REQ-107 y las razones por par. Si se adopta alguno, el ADR dice qué cambia (el modelo del motor de lotes; el reparto de memoria del ADR-0002 y el ADR-0037; `generation` queda en 12B hasta medir la 001, P7) y se dejan preparados, **sin integrar**, el cambio del compose base y de `specs/004-evaluacion-asistida/entorno.md`. Adoptar y desplegar lo aprueba el responsable (P11).
- **Archivos:** `docs/adr/0057-resultado-de-la-comparacion-de-modelos.md`, `specs/015-uso-y-eleccion-del-modelo/entorno.md`.
- **Verificación:** cada cifra del ADR existe en un `verificacion/T-NNN.md`; las alternativas del ADR-0056 están todas resueltas.
- **No tocar:** el compose base, `settings.py`, `models/`.

### T-248 · Resto de las instrucciones

- **Requisitos:** REQ-106
- **Nivel de verificación:** plena (instrucciones al modelo).
- **No se integra antes de T-246:** puede desarrollarse antes, en una rama que parte del commit medido, pero todas las corridas de T-239 a T-246 usan el mismo código.
- **Qué hay que hacer:** con el informe `revision-instrucciones.md` como entrada, corregir o justificar por escrito cada hallazgo de las instrucciones que todavía no pasaron por T-236, T-252 ni T-237; los de gravedad alta son obligatorios, los de gravedad media y baja se hacen si caben y si no pasan a la lista de revisión con el primer producto. Cada cambio crea una versión nueva, la registra en cada pedido con su huella y se mide en T-249.
  - Consecuencias (`matriz-consecuencias-v2`): alcance de las cláusulas generales por punto, con la ruta de cada fundamento; de 25 a 8–10 requisitos por pedido.
  - Respaldo: oración completa para que la cita se lea sola.
  - Ficha y ficha por renglón: todas las citas del requisito (no solo la primera, `sheets.py`); separar «no aparece» de «sin precio» y «no estoy seguro».
  - Visión (`vision-v4`): medir la penalización de repetición (1,15 contra 1,05 o ninguna) con pagarés y constancias, e imagen antes del texto. Las lecturas con visión ya hechas de los casos no se rehacen.
  - Informe técnico (`informe-tecnico-v2`): tres ejemplos (apto con cita, no apto, no trata) y la cita antes del dictamen.
  - Consulta (`consulta-v4`): repetir la pregunta al final y las afirmaciones antes del estado; retirar `consulta-v1` si ningún camino la usa.
  - Nombre del oferente y datos del procedimiento (en el código): la cita antes del valor; huella de todas las instrucciones.
  - El informe queda con el 100 % de las instrucciones, cada hallazgo alto corregido o justificado.
- **Archivos:** `evaluon/tenders/prompts/matriz-consecuencias-v2.md` y `matriz-respaldo-v2.md`, `evaluon/tenders/proposal/consequences.py`, `evaluon/tenders/proposal/norm_support.py`, `evaluon/offers/prompts/*` (versiones nuevas), `evaluon/offers/services/sheets.py`, `evaluon/assessment/prompts/vision-v4.md` e `informe-tecnico-v2.md`, `evaluon/offers/vision.py`, `evaluon/queries/prompts/consulta-v4.txt`, `evaluon/queries/answering.py`, `evaluon/offers/proposal_fields.py`, `evaluon/tenders/proposal/procedure_fields.py`, `evaluon/assessment/services/technical_report.py`, `evaluon/settings.py`, `specs/015-uso-y-eleccion-del-modelo/revision-instrucciones.md`, los tests de cada área y `tests/test_instrucciones_revisadas.py`.
- **Verificación:** los tests de cada área, `tests/test_instrucciones_revisadas.py` (100 %, todo hallazgo alto con estado, versiones congeladas) y la suite completa una vez. La medición de lo que cambió es T-249.
- **No tocar:** las instrucciones de matriz y evaluación (salvo un hallazgo alto que T-236, T-252 o T-237 haya dejado justificado), el esquema, los compose.

### T-249 · Medición de lo que cambió T-248

- **Requisitos:** REQ-106
- **Nivel de verificación:** plena. Usa la GPU.
- **Qué hay que hacer:** medir solo las áreas que T-248 cambió, de a una, contra el valor registrado antes (P7): consulta con `correr_evals` (85 % de aciertos, 90 % de abstención, 100 % de cita literal, ADR-0002); fichas con `medir_fichas` (90 % de fragmentos esperados, ADR-0027); lectura con visión con `leer_con_vision` sobre el conjunto de T-161; propuestas de datos del procedimiento y del oferente (los umbrales de la 014: 4 de 5 datos y 90 % de renglones; 90 % de CUIT y 80 % de nombres); consecuencias y circulares con `medir_matriz` (casos con circulares: REQ-031). Una baja requiere la aprobación explícita del responsable (P7).
- **Umbral:** ninguna medida empeora; una ronda de ajuste como máximo.
- **Archivos:** `specs/015-uso-y-eleccion-del-modelo/verificacion/T-249.md`.
- **No tocar:** código e instrucciones.
