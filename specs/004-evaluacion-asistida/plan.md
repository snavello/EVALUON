# Plan 004 · Evaluación asistida de ofertas

Estado: aprobado · Fecha: 2026-10-06 · Aprobó: responsable del proyecto (2026-10-06, con las decisiones de abajo)

Spec: `specs/004-evaluacion-asistida/spec.md` (aprobada el 2026-10-06)

ADR de este plan, todos **propuestos**:

- `docs/adr/0037-lectura-completa-por-grupos-de-documentos-y-contexto-del-motor-de-lotes.md`: documentos completos empaquetados en grupos de hasta 20.000 tokens; el motor de lotes pasa a 32.768 tokens de contexto.
- `docs/adr/0038-resultados-con-cita-literal-verificada-y-contraste.md`: la cita la ubica el sistema, un contraste corto antes de concluir y reglas para unir grupos y para "no se encontró el documento".
- `docs/adr/0039-modulo-de-evaluacion-resultados-inmutables-y-decisiones-aparte.md`: módulo `evaluon/assessment/`, resultados y decisiones de solo inserción.
- `docs/adr/0040-registro-minimo-de-preguntas-y-respuestas-de-la-comision.md`: dos tablas mínimas con alcance de la respuesta.

ADR en los que se apoya: 0002 (motor y reparto de memoria), 0003 (recuperación), 0004 (lectura y cita literal), 0009 (respuestas de la Comisión), 0012 (suite), 0018 (cola), 0024, 0025 y 0036 (ritmo de trabajo y auditoría), 0026 (módulo propio y cola compartida), 0035 (lectura completa en la 004).

## Resumen del enfoque

Un módulo nuevo `evaluon/assessment/`, con las capas de `tenders/` y `offers/` (funciones de negocio que comprueban el rol y dejan el registro; pantalla y comandos solo traducen). Para cada par oferta y requisito de la última matriz validada, el `worker` arma el texto completo de los documentos de la oferta, página por página, y lo agrupa hasta el presupuesto del contexto (ADR-0037). Un pedido al modelo por grupo devuelve resultado, exigencia y citas; el sistema ubica cada cita en el texto canónico del documento (la página sale de ahí, el texto mostrado es el recorte del canónico), descarta lo que no encuentra, une los grupos con reglas fijas y contrasta con un segundo pedido corto antes de concluir "cumple" o "no cumple" (ADR-0038). Donde duda o no puede corroborar, el resultado es "no determinado" citando lo que tiene, con una pregunta concreta a la Comisión si falta un dato.

Lo que el modelo no hace: no escribe texto citado, no decide la página, no decide "no se encontró el documento" (lo decide una regla sobre lo leído), no ordena ofertas ni descarta (eso es aritmética sobre resultados y datos del Portal). La Comisión confirma, corrige o rechaza cada propuesta (P3); cada paso queda en tablas de solo inserción.

La evaluación se pide para todas las ofertas a la vez y se presenta como **matriz de evaluación** (ofertas por requisitos) con descartes propuestos y orden económico. Volver a evaluar un requisito de una oferta (por una subsanación, por una respuesta de la Comisión o a mano) es la misma operación: un resultado nuevo que no pisa el anterior.

El trabajo empieza por un **corte vertical** (ADR-0025): T-150 evalúa una oferta de punta a punta con un modelo simulado y T-151 lo mide con un caso chico calcado de ofertas reales; recién después se arman la matriz, la revisión y las preguntas, y se mide el caso-00 contra el dictamen.

## Componentes

| Componente | Nuevo | Qué hace | Con quién habla |
|---|---|---|---|
| `app` | Cambia | Páginas de la matriz de evaluación, del resultado de un par y de las preguntas; comandos `evaluar_ofertas`, `medir_evaluacion`, `medir_tamanos` | `db`; `embeddings`, `reranker` |
| `worker` | Cambia | Atiende el pedido nuevo `evaluate_offers` | `db`; `generation_batch`, `embeddings`, `reranker` |
| `generation_batch` | Cambia | Contexto de 32.768 tokens (variable propia); mismo modelo, compilación y argumentos | Solo `worker` y `app` (comandos de medición) |
| `generation`, `embeddings`, `reranker`, `db`, `migrate`, `portal_worker` | No | Sin cambios | — |

Todo el camino de pliegos y ofertas corre en el equipo, sin internet (P4): `worker` no tiene red de salida y `generation_batch` arranca con `--offline`. La cotización del Portal se lee de las tablas que la 012 ya cargó, sin conectarse a nada.

## Estructura del código

```
evaluon/assessment/
├── models.py  migrations/          tablas de este plan y triggers (ADR-0039)
├── documents.py                    documentos de una oferta como texto por página, copias, tokens, grupos y ventanas
├── grounds.py                      fundamentos de un requisito: texto vigente del pliego, normas, respuestas aplicables
├── citations.py                    ubicar la cita del modelo en el texto canónico y sacar la página
├── prompting.py                    mensajes, esquemas JSON y análisis de la salida del modelo
├── combine.py                      unir los grupos y el contraste en un resultado (ADR-0038)
├── ordering.py                     descarte propuesto y orden económico con datos del Portal
├── services/
│   ├── evaluate.py                 pedir, manejador del pedido, armar una evaluación por oferta (REQ-052 a REQ-054, REQ-057)
│   ├── matrix.py                   matriz de evaluación, estado por oferta, aviso de versión (REQ-057 a REQ-059)
│   ├── review.py                   confirmar, corregir, rechazar, historial (REQ-056)
│   ├── questions.py                preguntas y respuestas (REQ-055, REQ-056)
│   └── remedy.py                   pedir subsanación, agregar el documento y evaluar de nuevo (REQ-060)
├── prompts/                        instrucciones versionadas (evaluacion-v1.md, contraste-v1.md)
├── sizing.py                       medida de tamaños de las ofertas (T-148)
├── evaluation.py                   medición contra la lista esperada del dictamen
├── views/  urls.py                 un archivo de vistas por tema
└── management/commands/            evaluar_ofertas, medir_evaluacion, medir_tamanos
evaluon/templates/assessment/       matriz, resultado, preguntas, historial
tests/assessment/                   pruebas, conftest.py propio, textos inventados y el caso chico
```

Cambios fuera del módulo, todos en T-148: `docker-compose.yml`, `.env.example`, `evaluon/settings.py`, `JobKind` y `HANDLERS` de `evaluon/tenders/`, tipos de hecho de `evaluon/audit/`, los tests de compose y del motor de lotes, y el contexto registrado en `tenders/proposal/run.py` y `offers/services/sheets.py`.

## Modelo de datos

Nombres en inglés; valores de dominio en español sin tildes, como en la 003 y la 008. **Todo el esquema lo crea T-148**, en una sola migración de `assessment` más un archivo de triggers, para que ninguna otra tarea lo toque (ADR-0039). Todas las tablas son de solo inserción: triggers rechazan UPDATE y DELETE.

**`assessment_request`**: un pedido de evaluación. `procedure`, `matrix_version` (FK, validada), `offers` (lista de ids de oferta), `requirements` (lista de ids o nula si son todos), `cause` (`matriz`, `subsanacion`, `respuesta`, `nueva_version`, `manual`), `decision` (FK, nula; la decisión o respuesta que lo originó, ver abajo), `answer` (FK, nula), `requested_by`, `requested_at`, `job` (FK a `tenders_job`; el pedido de cola lleva el id de esta fila en `target_id`, sin clave foránea, como en ADR-0026).

**`assessment_run`**: una evaluación de una oferta. `request`, `offer`, `matrix_version`, `number` (correlativo por oferta), `channel` (`screen` o `eval`), `documents` (cada documento usado con su lectura, huella del texto canónico, páginas, tokens, copias omitidas y ventanas), `norms` (régimen, fecha de autorización y versión de la normativa tomados de la propuesta de matriz, P8), `models` (motor de lotes con su contexto real, embeddings y reranker, con huellas y compilación), `parameters`, `prompt_versions`, `counts`, `timings`, `anomalies`, `built_at`. Una evaluación se guarda entera, en una transacción, al terminar la oferta: un pedido cortado conserva las ofertas ya evaluadas y no deja una a medias.

**`assessment_result`**: lo que se propone para un par. `run`, `offer`, `requirement`, `outcome` (`cumple`, `no_cumple`, `sin_documento`, `no_determinado`), `doubt` (vacío, o el motivo de un "no determinado": `duda`, `sin_corroborar`, `contradiccion`, `lectura_incompleta`, `externo`, `sin_cita`, `sin_dato`), `exigence` (`documento`, `condicion` o vacío), `explanation` (texto breve del modelo; la pantalla lo rotula "explicación del sistema" y nunca lo presenta como cita), `unread_pages_warning` (la oferta tiene páginas sin leer), `previous` (FK a sí mismo: el resultado anterior del mismo par, para el recorrido). Único por evaluación y requisito. El resultado vigente de un par es el de la evaluación más reciente.

**`assessment_citation`**: los fundamentos de un resultado. `result`, `order`, `kind` (`oferta`, `pliego`, `norma`, `respuesta`) y los campos de su clase, con una restricción por clase:
- `oferta`: `document`, `reading`, `page`, `char_start`, `char_end`, `text` (igual al recorte del texto canónico de la lectura). Solo estas citas habilitan "cumple" o "no cumple".
- `pliego`: `requirement_quote` (FK a la cita del requisito, de la 003), `text` (el texto vigente, y `original_text` si una circular lo modificó).
- `norma`: `norm_unit` (FK a la unidad de la normativa), `label` (norma y artículo), `text`.
- `respuesta`: `answer` (FK), con quién y cuándo se leen de la respuesta.

**`assessment_step`**: un pedido al modelo (P6). `run`, `offer`, `requirement` (nulo en la reescritura), `purpose` (`grupo`, `contraste`, `reescritura`), `group_index`, `documents` (qué documentos o ventanas entraron, con sus tokens), `request`, `raw_output`, `parsed`, `anomalies`, `retry_of`, `prompt_tokens`, `completion_tokens`, `timings`.

**`assessment_decision`**: lo que una persona hace con un resultado. `result`, `action` (`confirmar`, `corregir`, `rechazar`, `pedir_subsanacion`, `subsanar`), `outcome_after` (en `corregir`: uno de los cuatro resultados), `note` (obligatoria en `corregir`, `rechazar` y `pedir_subsanacion`), `document` (FK a `offers_document`, en `subsanar`), `user`, `at`, `event` (FK a `audit_event`). El estado de un par se calcula: sin decisión, "propuesto"; con la última entre `confirmar`, `corregir` y `rechazar`, ese estado. `pedir_subsanacion` y `subsanar` no cambian el estado: son el recorrido.

**`assessment_question`**: `procedure`, `requirement`, `offer`, `result` (el resultado que la originó), `text` (la pregunta concreta), `reason`, `created_at`. **`assessment_answer`**: `question`, `text`, `scope` (`par`, `requisito`, `procedimiento`), `answered_by`, `answered_at`, `event`. La respuesta vigente de una pregunta es la última. Una pregunta sin respuesta no es fundamento (P3).

**Cambios fuera del módulo** (T-148): `tenders_job.kind` suma `evaluate_offers`; `audit_event.event_type` suma `eval_request`, `eval_build`, `eval_decision`, `eval_answer` (caben en 20 caracteres; la migración cambia la restricción de valores válidos).

**Parámetros** (`settings.py`, copiados en cada evaluación): `GENERATION_BATCH_CONTEXT_TOKENS` (32.768; variable `GENERATION_BATCH_CTX_SIZE`), `ASSESSMENT_GROUP_TOKENS` (20.000), `ASSESSMENT_MAX_GROUPS` (4), `ASSESSMENT_MAX_OUTPUT_TOKENS` (700), `ASSESSMENT_MAX_CITATIONS` (4), `ASSESSMENT_CITATION_MAX_CHARS` (600), `ASSESSMENT_REQUEST_TIMEOUT_SECONDS` (300), `ASSESSMENT_NORM_UNITS_MAX` (4), `ASSESSMENT_ANSWERS_MAX` (20), versiones de instrucciones.

## Roles

Los de la 003: el operador prepara, el evaluador decide (P3).

| Operación | Operador | Evaluador |
|---|---|---|
| Pedir la evaluación (todas las ofertas o un requisito), ver la matriz, el estado, los resultados, las preguntas | sí | sí |
| Agregar un documento a una oferta presentado por subsanación y pedir volver a evaluar | sí | sí |
| Confirmar, corregir o rechazar una propuesta; pedir una subsanación | no | sí |
| Responder o dejar sin responder una pregunta | no | sí |

Un usuario sin rol de la Comisión no ve estas páginas; el rechazo se registra como `rejected`.

## Flujo de IA

### Pedido

`request_evaluation(user, procedure, offers=None, requirements=None, cause="matriz")` se rechaza, sin encolar nada y con el hecho en resultado `rejected` y su motivo, si no hay matriz validada, si el procedimiento no tiene ofertas, si algún documento de una oferta pedida está en lectura o falló, o si ya hay un pedido de evaluación en espera o en curso del procedimiento. Encola un solo pedido `evaluate_offers`. El `worker` evalúa las ofertas de a una; cada una se guarda al terminar.

### Qué se lee y cómo se agrupa (REQ-054, ADR-0037)

1. **Documentos.** Los documentos de la oferta con su última lectura. Los de texto canónico idéntico se cuentan una vez (el resto figura como copia, con su documento, y la cita se hace sobre el que quedó). Cada documento se arma como texto por página con los pasajes de la lectura (`offers_passage`, que nunca cruzan una página): `--- página k ---` y el texto; una página ilegible figura `--- página k: no se pudo leer ---`. No se filtra por tipo de documento (decisión de la 008: el tipo es un dato, nunca excluye).
2. **Tokens.** Se cuentan con el tokenizador del modelo (`generation.count_tokens`) una vez por documento y por página, y se guardan en el registro de la evaluación.
3. **Grupos.** Se empaquetan documentos enteros hasta `ASSESSMENT_GROUP_TOKENS`. Si toda la oferta entra, es un solo grupo y no hace falta ordenar nada: así son las ofertas chicas y medianas. Si no entra:
   - el orden de los documentos para ese requisito es por relevancia: el mayor puntaje del reranker entre sus pasajes recuperados (`offers.retrieval.retrieve`, con el requisito y su reescritura como lo diría una oferta, `sheets.rewrite_requirement`, calculada una vez por requisito y no por oferta); los documentos sin pasaje recuperado van al final, por orden de carga;
   - se arman grupos con ese orden; un documento que por sí solo supera el presupuesto se parte por páginas en ventanas con una página de solape;
   - **se pregunta por todos los grupos**, hasta `ASSESSMENT_MAX_GROUPS`. La relevancia ordena, no descarta. Si hay más grupos que el tope, los últimos no se leen y el par no puede ser "no se encontró el documento" (queda `lectura_incompleta`).
4. **Orden de los pedidos.** Para cada oferta y grupo, se piden seguidos todos los requisitos que le tocan: las instrucciones y los documentos van primero y el requisito al final del mensaje, de modo que el servidor reutilice el prefijo ya procesado. Los contrastes se piden después, todos juntos, para no desalojar ese prefijo. Es un ordenamiento de pedidos, sin lógica propia: si el servidor no reutiliza, los resultados son los mismos y cambia el tiempo.

Estimación, a confirmar con T-148 (`medir_tamanos`, con el tokenizador y las lecturas reales del caso-00):

| Oferta | Páginas | Tokens estimados | Grupos con 20.000 |
|---|---|---|---|
| Oferta chica | 9 | 3.500 a 8.000 | 1 |
| Oferta mediana | 16 | 6.000 a 14.000 | 1 |
| Oferta grande | 45 | 18.000 a 40.000 (menos con las copias deduplicadas) | 1 a 2 |

### Qué recibe y qué devuelve el modelo

- **Recibe** (`prompts/evaluacion-v1.md` como sistema; como usuario, en este orden): los documentos del grupo con alias `D1…` (título, archivo, páginas y el texto por página); las respuestas de la Comisión que aplican (`R1…`, con quién y cuándo); las unidades de norma que respaldan el requisito (`N1…`, con norma y artículo); y el requisito. El requisito es el texto vigente de la cita del pliego (el de la circular si la modificó, con el original al lado), su ruta y su renglón. Las normas son las que la matriz ya trae para ese requisito (respaldo normativo y fundamentos de la consecuencia elegida o sugerida, 003): no hay búsqueda normativa nueva. Las instrucciones definen los cuatro resultados, piden citar solo texto de los documentos, tratan "no se encontró" como una falta de documento (nunca "no cumple") y mandan "no determinado" con una pregunta cuando verificar el requisito exige una base externa o un dato que solo tiene la Comisión.
- **Devuelve** un JSON obligado por esquema: `resultado` (`cumple`, `no_cumple`, `no_consta`, `no_determinado`), `exigencia` (`documento`, `condicion`), `citas` (hasta 4: `documento` entre los alias del grupo y `texto` literal de hasta 600 caracteres), `fundamentos` (alias `N`/`R` usados), `explicacion` (hasta 300 caracteres) y `pregunta` (vacía si no hace falta).
- **Filas técnicas por renglón.** Se tratan igual, con el renglón y las citas propias y generales del pliego como requisito. El sistema propone sobre el ajuste de lo ofrecido al renglón (por ejemplo, el producto o la presentación que la oferta declara contra los del pliego); la comparación valor por valor de las especificaciones es de la 010 y no se hace aquí. Es el punto 2 de "Puntos para el responsable".

### Cita (REQ-053)

Por cada cita, el sistema busca el texto del modelo dentro del texto canónico de ese documento con `evaluon.tenders.proposal.quotes.locate` (igual con cualquier cantidad de espacios, como en la 003). Si lo ubica, la cita guarda las posiciones, el recorte del texto canónico y la página de esas líneas (`pages_at`); la página que diga el modelo no se usa. Si no lo ubica, se descarta y queda la anomalía. Un "cumple" o "no cumple" sin una cita de la oferta ubicada se reintenta una vez con el aviso; si vuelve a fallar, queda "no determinado" (`sin_cita`) con lo que haya. El requisito del pliego se agrega siempre como fundamento `pliego`, por el sistema.

### Unir grupos y contrastar (ADR-0038)

1. Cada grupo da su resultado con sus citas ubicadas. Se unen así:
   - "cumple" y "no cumple" en grupos distintos: "no determinado", `contradiccion`, con las citas de ambos;
   - una conclusión con cita y "no consta" en los demás grupos: queda la conclusión;
   - todos los grupos "no consta": "no se encontró el documento" si la exigencia es `documento` en todos los grupos, la oferta no tiene páginas sin leer y se leyeron todos los grupos; si la exigencia es `condicion`, "no determinado" (`sin_dato`); si hay páginas sin leer o grupos sin leer, "no determinado" (`lectura_incompleta`).
2. **Contraste.** Por cada "cumple" o "no cumple" con cita ubicada, un pedido corto (`prompts/contraste-v1.md`): recibe solo el requisito, el texto literal citado y los fundamentos, y contesta `si`, `no` o `parcial` a si ese texto, por sí solo, demuestra la conclusión. Si no contesta `si`, el resultado pasa a "no determinado" (`sin_corroborar`) y se conservan las citas.
3. **Externos.** Si el requisito se verifica con una consulta fuera de la oferta (por ejemplo, el Registro de Proveedores, REPSAL o la deuda) el modelo lo señala y el resultado es "no determinado" (`externo`): el sistema no infiere hojas de compliance (P9, 005).
4. **Pregunta.** Un "no determinado" con una pregunta del modelo crea una `assessment_question` (una por oferta y requisito mientras esté abierta; una evaluación nueva del mismo par reutiliza la abierta). Con respuesta aplicable, el modelo la recibe como `R`; una respuesta sola no basta para "cumple" (queda "no determinado" y la persona decide con ella a la vista, ADR-0038).

### Abstención

Resultado "no determinado": duda, falta de corroboración, contradicción entre documentos, lectura incompleta, requisito externo, falta de cita ubicada, falta de dato. En todos los casos se muestran las citas que haya y el motivo, y nada se presenta como hecho (P3).

## Matriz de evaluación (REQ-057, REQ-058, REQ-059)

`services/matrix.py` arma, para la última matriz validada de un procedimiento, la grilla de requisitos por ofertas con el resultado vigente de cada par y su estado (propuesto, confirmado, corregido, rechazado). Cada celda enlaza a la página del par.

- **Versión de la matriz (REQ-057).** Cada evaluación guarda la versión; la matriz muestra con cuál se evaluó cada oferta y, si hay una versión validada posterior, avisa ("Evaluada con la versión 1; la versión vigente es la 2") y ofrece evaluar de nuevo.
- **Estado (REQ-058).** Por oferta: requisitos por estado y por resultado, y preguntas abiertas.
- **Descarte propuesto (REQ-059).** Una oferta se señala descartada si algún requisito formal o técnico tiene resultado efectivo "no cumple" (el propuesto, o el corregido por la Comisión; un "rechazado" no cuenta como "no cumple"). Se muestra el requisito, su fundamento (pliego y cita de la oferta) y la consecuencia prevista que la matriz validada eligió para ese requisito. "No se encontró el documento" y "no determinado" **no descartan**: se muestran aparte como "a resolver por la Comisión". El punto 3 de "Puntos para el responsable" trata los requisitos económicos.
- **Orden económico (REQ-059).** Entre las no descartadas, por precio total ascendente (`portal_offer_data.total`, de la 012) y, por renglón, por precio unitario ascendente (`portal_quote`). Si una oferta no tiene datos del Portal, figura "sin cotización del Portal" al final y sin posición; si las monedas difieren, no se ordena y se avisa. No se leen precios de los documentos de la oferta.
- Todo es una propuesta: la pantalla lo rotula así; la Comisión decide.

## Preguntas a la Comisión (REQ-055, REQ-056, ADR-0040)

Lista de preguntas abiertas del procedimiento (con requisito, oferta y motivo). El evaluador responde con un texto y elige el alcance (`par`, `requisito` —por omisión— o `procedimiento`), o la deja sin responder. Al responder, el sistema ofrece "evaluar de nuevo" los pares afectados (pedido con causa `respuesta`); no cambia las evaluaciones ya hechas. Una pregunta sin respuesta deja el requisito en "no determinado" y la matriz y el estado la informan.

## Subsanación (REQ-060)

Cuando un resultado es "no se encontró el documento", la Comisión decide: el evaluador puede **pedir la subsanación** (decisión `pedir_subsanacion`, con su nota, y la matriz marca el par "subsanación pedida"). Si el oferente presenta el documento, el operador o el evaluador lo agrega a la oferta con el servicio de carga existente de la 008 (`offers.services.offers.load_document`: original, huella y lectura en segundo plano, con su hecho `offer_load`), lo vincula (decisión `subsanar` con el documento) y pide evaluar de nuevo ese requisito (causa `subsanacion`). La evaluación nueva lee **todos** los documentos de la oferta, incluido el agregado, y crea un resultado nuevo con `previous` apuntando al anterior. El historial del par muestra, en orden: resultado "no se encontró el documento" con la cita del pliego, el pedido de subsanación, el documento agregado (con su huella y quién lo cargó), la evaluación nueva, y la decisión de la Comisión sobre ella. Nada se pisa.

## Revisión y decisión (REQ-056)

La página de un par muestra: el requisito (texto vigente y, si cambió, el original), las citas de la oferta con documento, página, texto literal y enlace al original en esa página, la norma con su artículo o la respuesta de la Comisión (rotulada como tal, con quién y cuándo), la explicación del sistema (rotulada), el motivo de un "no determinado" y la pregunta abierta si hay. El evaluador **confirma**, **corrige** (elige otro resultado y escribe el motivo) o **rechaza** (con motivo); queda la propuesta original, la decisión, el autor y la fecha, y el hecho `eval_decision`. El historial lista todo el recorrido del par.

## Pantalla

Páginas armadas en el servidor, sin htmx (ADR-0005), con la hoja de estilos de la 003.

- **Evaluación del procedimiento**: la matriz de evaluación, el estado por oferta, los descartes propuestos y el orden económico, las preguntas abiertas, el aviso de versión; botón "Evaluar todas las ofertas" y estado del pedido con el aviso de fin de la 003.
- **Par (oferta y requisito)**: lo descrito en "Revisión y decisión", con las acciones de decisión, subsanación y "evaluar de nuevo este requisito", y su historial.
- **Preguntas**: abiertas y respondidas, con el formulario de respuesta.

## Registro de auditoría (P6)

| Hecho | Qué guarda además de los datos comunes |
|---|---|
| `eval_request` | Procedimiento, versión de la matriz, ofertas y requisitos pedidos, causa, decisión o respuesta de origen; también los pedidos rechazados con su motivo |
| `eval_build` | Evaluación, oferta, versión de la matriz, documentos analizados (lectura, huella del texto canónico, páginas, tokens, copias omitidas, ventanas), régimen y versión de la normativa, motor con su contexto real y huellas, parámetros, versiones de instrucciones, cuentas por resultado y por motivo de "no determinado", preguntas creadas, anomalías (citas no ubicadas, salidas inválidas, reintentos), tiempos por oferta y por pedido; con resultado `failed` y motivo si no se pudo |
| `eval_decision` | Resultado, acción, antes y después, nota, documento si es una subsanación, usuario |
| `eval_answer` | Pregunta, respuesta, alcance, usuario |
| `rejected` | Como en la 001 |

El detalle de cada pedido (documentos que entraron, pedido completo, salida cruda, lo interpretado) está en `assessment_step`. Con eso se reconstruye por qué el sistema propuso cada resultado: documentos analizados, versión de la normativa, modelo y parámetros, instrucciones, texto leído, resultado, usuario y fecha.

## Medición (ADR-0025)

Reutiliza `evaluon/tenders/evaluation.py` (lista esperada con huellas y visto bueno, carpeta de corrida, resumen público, intervalos de Wilson) y la regla de ubicación de fragmentos de `evaluon/offers/evaluation.py`. Lo nuevo es `assessment/evaluation.py` y el comando `medir_evaluacion`, que corre la evaluación con el canal `eval` y la compara. Se corre de a una (GPU).

### Listas esperadas

- **Caso chico** (T-149, en el repositorio, `tests/assessment/data/caso-chico/`): calcado de ofertas reales (misma estructura de archivos, páginas escaneadas, formularios y pólizas; nombres, CUIT y montos inventados), con 3 ofertas, 8 a 10 requisitos y un resultado esperado por par, que incluye: un "cumple" y un "no cumple" con cita, un documento exigido que falta ("no se encontró el documento"), un requisito externo ("no determinado" con pregunta), una página ilegible, y un requisito técnico por renglón. Un archivo nuevo, `evaluacion-esperada.yaml`.
- **Caso-00** (T-149, fuera del repositorio, `corpus/casos/caso-00/esperado/dictamen-esperado.yaml`): la prepara el Coordinador leyendo el dictamen (`corpus/casos/caso-00/evaluacion/`), sin correr el sistema, con visto bueno y huella:

```yaml
caso: caso-00
dictamen: {archivo: "../evaluacion/…FINAL.pdf", sha256: …}
matriz: {procedimiento: A0PC000000-0004-LPU25}
ofertas:
  - oferente: "Lombardozzi"
    requisitos:
      - {requisito: M-008, dictamen: cumple, base: oferta}
      - {requisito: M-033, dictamen: cumple, base: externa}
      - {requisito: M-051, dictamen: no_cumple, base: tecnica}
    descartada: no
orden_economico: [oferente, oferente, oferente]   # el del cuadro comparativo del Portal
visto_bueno: "responsable, AAAA-MM-DD"
```

`requisito` es el id de `matriz-esperada.yaml`; `base` dice dónde está el fundamento del dictamen: `oferta` (los documentos de la oferta), `externa` (consulta a una base externa: Registro de Proveedores, REPSAL, deuda, SSN, Portal) o `tecnica` (informe del área requirente). Esa misma tarea completa `fichas-esperadas.yaml` con lo que el ADR-0035 dejó pendiente (los cuadros del Portal y las copias deduplicadas), porque REQ-054 se mide contra esa lista.

### Cómo se cuenta

1. **Coincidencia (REQ-052).** Entre los pares que el dictamen trata, el resultado vigente propuesto (sin decisión humana) coincide si es igual al del dictamen (`cumple` o `no_cumple`). En los pares de `base: externa`, "no determinado" con lo citado también coincide (es la abstención correcta: P3, P9); es el punto 1 de "Puntos para el responsable".
2. **Contradicción.** "Cumple" donde el dictamen dice "no cumple", o al revés. Se informa además, sin bloquear, "no se encontró el documento" donde el dictamen dice "cumple" (discrepancia fuerte).
3. **Cita literal (REQ-053).** Toda propuesta "cumple" o "no cumple" tiene al menos una cita de la oferta, igual al recorte del texto canónico de su documento y dentro de su página.
4. **Fragmentos de la ficha (REQ-054).** De las propuestas con cita de pares cuyo requisito tiene fragmentos en la lista de fichas, la parte cuya cita cae en el mismo documento y página que un fragmento esperado (regla 1 de la 008).
5. **Matriz (REQ-059).** Las tres ofertas evaluadas; un resultado vigente por cada par; descartes propuestos con requisito y fundamento; las no descartadas ordenadas por total como el cuadro comparativo.
6. **Tiempo.** Por oferta y por pedido, informado, sin máximo; más los tokens por grupo y las páginas sin leer.

### Umbrales, escritos antes de medir

| Medida | Caso chico (T-151) | Caso-00 (T-155 en adelante) |
|---|---|---|
| Coincidencia con el esperado (REQ-052) | 100 % | más del 80 % de los pares del dictamen, con intervalo de Wilson informado |
| Contradicciones (REQ-052) | 0 | 0 |
| "Cumple" o "no cumple" sin cita literal de la oferta (REQ-053) | 0 | 0 |
| Citas de la oferta iguales al recorte del texto canónico (REQ-053) | 100 % | 100 % |
| "No se encontró el documento" con la cita del pliego donde el esperado lo dice (REQ-060) | 100 % | informado |
| Pregunta formulada donde falta un dato (REQ-055) | 100 % | informado (cuántas y cuáles) |
| Fragmentos de la ficha (REQ-054) | informado | 90 % o más |
| Tres ofertas evaluadas, un resultado por par, orden igual al del Portal (REQ-059) | 100 % | 100 % |
| "No se encontró el documento" donde el dictamen dice "cumple" | informado | informado |
| Tiempo y tokens | informado | informado |

Bloquean: coincidencia, contradicciones, cita, fragmentos de la ficha y matriz. Se informan: lo demás.

### Rondas

- **Caso chico (T-151):** una medición para comprobar que el corte funciona; se corrige dentro de la misma tarea antes de cerrarla, y no cuenta como ronda del caso-00.
- **Caso-00:** T-155 mide la base y registra los hallazgos. T-156 los corrige todos juntos, con un commit por hallazgo, y mide una vez (ronda 1). Solo si no llegó al umbral, T-157 repite (ronda 2). Después no hay más: lo que falta pasa, con su impacto, a la lista de revisión con el primer producto (ADR-0024). Una ronda más solo si el faltante hace perder un requisito o viola un principio (ADR-0025). Una contradicción abierta después de la ronda 2 viola P3 y no se acepta: se pasa al responsable.
- La medición a ciegas, con el proceso en curso que reservó el responsable, es posterior (spec).
- La matriz validada del caso-00 es la de la 008 (T-133).

## Tiempos y GPU

Estimación a confirmar con T-148 y T-155. Caso-00: 52 requisitos por 3 ofertas, 156 pares; un pedido por par y grupo (unos 200 pedidos de lectura, más unos 60 contrastes), con el prefijo de documentos reutilizado dentro de cada grupo. Cada grupo se procesa una vez por oferta (de 5.000 a 25.000 tokens) y cada requisito sobre él cuesta una consulta corta de 2 a 6 segundos. Orden de magnitud: de 20 a 45 minutos para las tres ofertas. Memoria de video: sube con el contexto del motor de lotes (ADR-0037); se mide en T-148 con los tres modelos cargados. Se informa por oferta y por pedido; no hay máximo (spec).

## Cobertura de requisitos

| Requisito | Cómo se resuelve | Cómo se verifica |
|---|---|---|
| REQ-052 | "Flujo de IA": cuatro resultados, unión de grupos y abstención (ADR-0038); matriz validada como entrada; T-150 | Test con modelo simulado de cada resultado; medición T-151 y T-155 a T-157 (más del 80 %, 0 contradicciones) |
| REQ-053 | "Cita": cita ubicada por el sistema, pliego, norma y respuesta como fundamentos; sin cita no hay conclusión; T-150 y T-153 (pantalla) | Test de una cita no ubicable que degrada a "no determinado"; medición: 100 % de citas literales |
| REQ-054 | "Qué se lee y cómo se agrupa": documentos completos por página, grupos y ventanas, ADR-0037; T-148 (tamaños) y T-150 | Test de agrupamiento (oferta chica en un grupo, grande en varios, documento mayor que el presupuesto en ventanas); medición: 90 % de fragmentos de la ficha |
| REQ-055 | "Unir grupos y contrastar", punto 4, y "Preguntas a la Comisión" (ADR-0040); T-150 (formular) y T-154 (responder) | Test: requisito con un dato que no está en la oferta ni en la normativa queda "no determinado" con una pregunta; medición del caso chico |
| REQ-056 | "Revisión y decisión" y "Preguntas a la Comisión"; tablas de solo inserción; T-153 y T-154 | Test de corrección que conserva original, nueva, autor y fecha; test de respuesta usada como fundamento |
| REQ-057 | `assessment_run.matrix_version` y aviso en la matriz; T-148 (esquema) y T-152 | Test con la versión 1 evaluada y la 2 validada: aviso |
| REQ-058 | "Matriz de evaluación", estado por oferta; T-152 | Test de cuentas por estado y de preguntas abiertas |
| REQ-059 | "Matriz de evaluación": todas las ofertas en un pedido, descarte propuesto y orden con la cotización del Portal; T-150 (pedido) y T-152 | Test de descarte y orden con y sin datos del Portal; medición T-155: tres ofertas, orden igual al del Portal |
| REQ-060 | "Subsanación": "no se encontró el documento" con la cita del pliego, pedido, documento agregado y evaluación nueva con `previous`; T-150 (resultado) y T-154 (recorrido) | Test del recorrido completo con dos evaluaciones registradas |

## Verificación contra la constitución

| Principio | Cumple | Nota |
|---|---|---|
| P1 Spec fuente de verdad | sí | Cada tarea nombra sus REQ; las dos interpretaciones de la spec están en "Puntos para el responsable" |
| P2 Trazabilidad | sí | Tabla de cobertura; tareas con REQ |
| P3 El sistema recomienda | sí | Todo es una propuesta; sin cita literal de la oferta no hay "cumple" ni "no cumple"; "no se encontró el documento" no es "no cumple"; una pregunta sin respuesta no es fundamento; la decisión es de una persona con autor y fecha |
| P4 Datos | sí | Ofertas reales solo en la base y en `corpus/casos/` (fuera del repositorio); tests y caso chico con textos calcados e inventados; todo el camino con IA local y sin red |
| P5 Local y reproducible | sí | Sin servicios nuevos; el único cambio de entorno es el contexto del motor de lotes, con variable y documentado en `entorno.md` |
| P6 Auditoría | sí | Ver "Registro de auditoría"; el registro incluye el contexto real del motor |
| P7 Evals | sí | Medición con lista esperada, umbrales escritos y dos rondas; una baja de métricas requiere aprobación |
| P8 Normativa versionada | sí | Cada evaluación guarda régimen y versión de la normativa de la propuesta de matriz |
| P9 Compliance | sí | El sistema no infiere consultas externas: "no determinado" y pregunta |
| P10 Simplicidad | sí | Sin servicio nuevo, sin búsqueda normativa nueva, sin leer precios de las ofertas, sin ficha obligatoria, sin circuito general de la 009 |
| P11 Compuertas | sí | El plan queda en borrador hasta que lo apruebe el responsable |

## Qué no se hace

El compliance (005) como fundamento; el circuito general de validación con la Comisión (009); la planilla por oferta, el cuadro comparativo y el acta (006); la comparación valor por valor de las especificaciones técnicas (010); leer precios de los documentos de la oferta; usar los datos del Portal (garantía, CUIT) como fundamento de un requisito; búsqueda normativa nueva (se usa la que la matriz ya trae); la medición a ciegas.

## Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El modelo pierde precisión con 20.000 tokens de documentos | "No determinado" de más; coincidencia baja | Presupuesto por grupo configurable; la primera ronda de ajuste puede bajarlo (14.000, 8.000); el contraste y la abstención evitan que se convierta en contradicción |
| Contradicción con el dictamen | Viola la meta y P3 | Cita ubicada por el sistema, contraste, unión de grupos que degrada a "no determinado"; se mide en cada ronda; no se acepta una abierta |
| La mayor parte de lo que el dictamen verifica es externo (Registro, REPSAL, deuda, SSN) | La coincidencia del 80 % no se alcanza si "no determinado" no cuenta | Punto 1 para el responsable; la lista esperada marca la `base` de cada par |
| Páginas ilegibles (el pagaré manuscrito y girado) | "No determinado" de más | La lista de páginas sin leer es visible; el par dice `lectura_incompleta`; el evaluador decide con el original |
| Dos instancias del modelo con 32.768 de contexto no entran en la memoria de video | No arranca el motor | T-148 mide; alternativas en el ADR-0037 (24.576 de contexto, o apagar `generation` durante la evaluación) |
| Una oferta grande necesita más grupos que el tope | Pares sin lectura completa | El par queda `lectura_incompleta`, nunca "no se encontró el documento"; el tope es un parámetro |
| El servidor no reutiliza el prefijo de los pedidos seguidos | Más tiempo, mismo resultado | El orden de pedidos es solo una optimización; se mide el tiempo y se informa |
| La evaluación técnica del renglón es de la 010 | Las filas técnicas quedan muy en "no determinado" | Punto 2 para el responsable; la medición las separa para ver su efecto |
| Una evaluación de varios minutos se corta | Trabajo perdido | Se guarda una oferta por vez en una transacción; el pedido interrumpido conserva lo ya guardado y se vuelve a pedir lo que falta |
| Se pisa la medición con otra | Corridas repetidas | De a una; el bloqueo de mediciones del ADR-0025 |
| Cambios de esquema a destiempo | Conflictos de migraciones | Todo el esquema en T-148; ninguna otra tarea lo toca |

## Decisiones

ADR 0037, 0038, 0039 y 0040, propuestos.

## Puntos de interpretación, para el Coordinador

- **La ficha de la 008 no es entrada de la evaluación.** ADR-0035 la deja como apoyo; aquí solo sirve como lista esperada para medir REQ-054. La evaluación no la necesita armada.
- **Una respuesta de la Comisión no sustituye la cita de la oferta.** La spec pide cita literal de la oferta para "cumple" y "no cumple" y el ADR-0009 admite una respuesta como fundamento: se conjugan así (ADR-0038, punto 4): la respuesta se muestra y se pasa al modelo, y si es el único apoyo el resultado propuesto queda "no determinado" y la persona decide.
- **Una respuesta nueva o un documento agregado no cambian lo ya evaluado**: generan una evaluación nueva del par (ADR-0009, REQ-060).
- **El contexto del motor de lotes cambia** y con él el registro de la 003 y la 008, que hoy toma el del motor interactivo (T-148 lo corrige).

## Puntos para el responsable

1. **Cómo se cuenta la coincidencia en lo externo.** El dictamen verifica requisitos que no se pueden resolver con los documentos de la oferta (Registro de Proveedores, REPSAL, deuda, pólizas validadas por la SSN). Propuesta: en esos pares cuenta como coincidencia "no determinado" citando lo que hay y con la pregunta; si no, el 80 % no se alcanza porque unos 5 de los 18 requisitos que el dictamen trata por oferta son de ese tipo.
2. **Filas técnicas por renglón.** La spec deja la comparación técnica renglón por renglón a la 010, pero 6 de los 18 requisitos del dictamen son el ajuste técnico (por ejemplo, la oferta de alimento para adultos en un renglón de cachorros). Propuesta: la 004 propone sobre el ajuste de lo ofrecido al renglón con cita de la oferta y del pliego, y deja a la 010 la comparación valor por valor.
3. **Descarte por requisitos económicos.** La spec descarta por requisitos formales o técnicos; la garantía no individualizada es económica y el pliego manda desestimarla. Propuesta: el descarte propuesto alcanza también a un "no cumple" económico, mostrando la consecuencia prevista en la matriz.
4. **Contexto del motor de lotes** de 16.384 a 32.768 tokens (ADR-0037, puede cambiar la memoria de video).


## Decisiones del responsable (2026-10-06)

1. **Requisitos externos** (Registro de Proveedores, REPSAL, deuda, Superintendencia de Seguros): los integra la **hoja de compliance**. La evaluación los deja como "falta la hoja de compliance"; la Comisión puede subir la hoja (o una que diga que no cumple) y el requisito se vuelve a evaluar con el mismo circuito de la subsanación. En la medición contra el dictamen, ese resultado cuenta como coincidencia.
2. **Filas técnicas por renglón:** la 004 opina por renglón (cumple, no cumple, no determinado) con cita de la especificación del pliego y de la hoja técnica de la oferta; la comparación valor por valor, con su tabla para el informe técnico, queda para la 010.
3. **Descarte:** también por un "no cumple" económico (por ejemplo, la garantía que el pliego manda desestimar si falta).
4. **Contexto del motor de lotes:** se amplía a 32.768 tokens (ADR-0037), midiendo antes la memoria de video.

## Enmienda 2026-10-06: lectura con visión y comparación de modelos

Estado: aprobada · Fecha: 2026-10-06 · Aprobó: responsable del proyecto (2026-10-06; tiempo por oferta hasta 30 minutos)

Motivo: la medición base del caso-00 dio 26 de 49 coincidencias; de los 23 desaciertos, 10 son datos que no se leen, 4 del modelo, 6 de diseño y 3 de medida. El responsable aprobó probar (1) la lectura con visión de las páginas que el reconocimiento de texto no lee bien y (2) una comparación controlada con un modelo más grande. Las correcciones de diseño y de medida siguen en T-156 a T-158 y no se tocan aquí.

ADR propuestos: `docs/adr/0041-lectura-con-vision-de-paginas-dudosas.md` y `docs/adr/0042-comparacion-controlada-con-gemma-4-26b-a4b.md`.

### Componentes

| Componente | Cambio |
|---|---|
| `generation_batch` | Suma `--mmproj` (proyector de imagen del 12B, 175 MB). Modelo, proyector y huella pasan a variables propias del lote (`GENERATION_BATCH_MODEL_FILE`, `_MODEL_ALIAS`, `_MODEL_SHA256`, `_MMPROJ_FILE`, por omisión las del 12B). `generation`, `embeddings` y `reranker`, sin cambios |
| `docker-compose.modelo-grande.yml` (nuevo) | Archivo adicional que reemplaza solo a `generation_batch` por el 26B-A4B con su proyector, para la comparación; no es parte del entorno de uso |
| `worker` | Antes de evaluar una oferta, pide la lectura por visión de sus páginas dudosas |
| `scripts/fetch_models.sh`, `scripts/models.sha256` | Suman el proyector del 12B y, aparte (opción `--modelo-grande`), el 26B-A4B y su proyector, con revisión y huella fijadas |

Todo sigue en el equipo y sin red de salida del camino de pliegos y ofertas (P4): la descarga es el único paso con internet, como hoy, y se hace con el script, una vez.

### Lectura con visión (ADR-0041)

- **Criterio** (objetivo, ya existente en el informe de la lectura): páginas `dudosa` (`low_confidence`), ilegibles y casi sin texto (`unread`), `without_text_unlisted`, y toda página de un documento en formato imagen. Hasta `ASSESSMENT_VISION_MAX_PAGES` por oferta.
- **Qué se hace**: una página por pedido a `generation_batch` con la imagen dibujada con pypdfium2; el modelo transcribe literalmente, con `[ilegible]` donde no lee. La transcripción se guarda como lectura nueva del documento (`sequence` siguiente, solo inserción) con las páginas legibles de la anterior tal cual y origen `vision` en los pasajes de las páginas por visión.
- **Dónde va el código**: `evaluon/offers/vision.py` (criterio, imagen, pedido, lectura nueva), `evaluon/assessment/prompts/vision-v1.md`, y un llamado desde `assessment/services/evaluate.py` antes de armar los documentos de la oferta. El único cambio de esquema es el valor `vision` del origen del texto de un pasaje.
- **Cita**: igual que hoy (ADR-0038): el modelo copia, el sistema ubica en el texto canónico de la lectura por visión y muestra el recorte del canónico. La pantalla rotula "leída por visión", muestra la imagen de la página y marca el resultado; la persona compara con el original antes de confirmar (P3).
- **Auditoría (P6, P8)**: el informe de la lectura guarda modelo y huella, huella del proyector, compilación, parámetros de imagen, versión de las instrucciones, página y motivo de cada transcripción, huella de cada imagen, pedido, salida cruda, tokens y tiempos; `assessment_run.documents` dice qué lecturas por visión usó cada evaluación.
- **Memoria**: +0,3 a 0,6 GB sobre los 10.530 MiB medidos en T-148; T-159 lo mide.

### Comparación de modelos (ADR-0042)

- **Candidato**: `google/gemma-4-26B-A4B-it-qat-q4_0-gguf`, revisión `d1c082be9cf3c8a514acf63b8761f4b41935842e`, `gemma-4-26B_q4_0-it.gguf`, 14.439.363.584 bytes, SHA-256 `3eca3b8f6d7baf218a7dd6bba5fb59a56ee25fe2d567b6f5f589b4f697eca51d`; proyector `gemma-4-26B-it-mmproj.gguf`, 1.194.828.160 bytes, SHA-256 `a359953a076b877db30c31dbbb4c6d93b4a6e017ee5db5784247e4d4c0dd4f3b`.
- **Memoria**: no entra junto al 12B del lote (27.000 MiB o más). Reemplaza temporalmente a `generation_batch`: unos 19.400 a 20.500 MiB con visión, de 24.463; aceptable hasta 22.000.
- **Corridas**: T-161 (12B con visión, referencia) y T-162 (26B con visión), de a una, con el mismo código, instrucciones, lecturas, matriz y lista esperada. T-163 solo si falta poco.
- **Umbral y rondas**: los de la tabla del ADR-0042, escritos antes de medir: 0 contradicciones, 0 conclusiones sin cita, coincidencia con al menos 4 pares netos más que la referencia y 2 de los 4 desaciertos del modelo recuperados, incumplimientos reales no peores, mejora explicada par por par, hasta 30 minutos por oferta, memoria hasta 22.000 MiB. Dos rondas como máximo.
- **Tiempo**: 3 a 5 horas de reloj para una ronda (1 a 1,5 de GPU); descarga de 15,6 GB entre 15 y 45 minutos.

### Medición de la lectura con visión (umbral del ADR-0041)

En T-161, sobre el caso-00: 0 contradicciones; al menos 3 de los 10 pares de datos que no se leen pasan a coincidir; ningún par que coincidía deja de hacerlo por una transcripción inventada; citas sobre páginas de visión 100 % literales contra su canónico; tiempo informado. Una ronda de ajuste de la instrucción o de la resolución, y una segunda solo si acerca.

### Cobertura de requisitos

| Requisito | Cómo se resuelve | Cómo se verifica |
|---|---|---|
| REQ-052 | Lectura con visión de las páginas dudosas (ADR-0041) y comparación de modelos (ADR-0042) para subir la coincidencia sin contradicciones; T-159 a T-163 | Mediciones T-161 y T-162 con los umbrales de arriba |
| REQ-053 | La cita de una página por visión se ubica en el texto canónico de su lectura y se muestra rotulada con la imagen; T-160 | Test: la cita de una página de visión es igual al recorte del canónico; una transcripción no ubicable degrada a "no determinado"; medición: 100 % literales |
| REQ-054 | Las páginas ilegibles pasan a ser texto para la lectura completa; T-160 | Test: la página dudosa se reemplaza por su transcripción en el texto por página y en los grupos; medición de fragmentos de la ficha |

### Verificación contra la constitución

| Principio | Cumple | Nota |
|---|---|---|
| P3 | sí | La visión transcribe, no decide; el resultado sobre una página de visión va marcado y la persona confirma con el original a la vista; ante `[ilegible]` en exceso la página sigue "no se pudo leer" |
| P4 | sí | Modelos y proyectores en el equipo, sin red; solo se bajan una vez con el script y se verifican por huella |
| P5 | sí | Las variables nuevas con valores por omisión; el 26B es un archivo adicional, no el entorno de uso |
| P6 y P8 | sí | Ver "Auditoría" arriba: modelo, proyector, imagen, instrucciones y lecturas usadas |
| P7 | sí | Umbrales escritos antes, dos rondas, regla de adopción |
| P10 | sí | Sin servicio nuevo ni modelo nuevo para leer; la comparación es temporal y se desmonta |

### Qué no se hace

Aplicar visión a una página legible; un modelo de lectura aparte; leer el cuadro de precios con confianza alta pero equivocado (sin criterio objetivo para detectarlo); cambiar `generation` (consulta de normativa) de modelo; medir el 31B; mantener instalado el 26B si no se adopta.

### Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El modelo inventa texto donde no se lee | Un "cumple" sobre texto falso | Marca visible y original al lado; `[ilegible]` obligatorio; transcripción con más de 30 % de `[ilegible]` no cuenta; se revisan contra la imagen las de los pares que cambian |
| La compilación fijada no carga el 26B o su proyector | La comparación no corre | T-159 hace la prueba de humo antes de cualquier medición; si falla, se informa y no se cambia la compilación sin ADR |
| La memoria del 26B no cabe o deja menos de 2,4 GB | Pedidos fallidos | Medición en T-159; baja el contexto a 24.576 en las dos corridas |
| La espera de 180 s por pedido no alcanza con el 26B | Pedidos fallidos que parecen del modelo | T-159 la mide; se sube para las dos corridas |
| La mejora medida viene de azar o de otra causa | Se adopta algo que no ayuda | Regla de "razón de la mejora" par por par, mismas condiciones, 0 contradicciones |
| Dos mediciones a la vez en una GPU | Resultados corruptos | T-161 a T-163 después de T-158, de a una; ninguna otra tarea usa la GPU en ese lapso |

### Puntos para el responsable

1. **Un "cumple" o "no cumple" apoyado solo en una página leída por visión.** Propuesta: se permite como propuesta rotulada, porque la Comisión confirma con el original a la vista. Alternativa más cauta: queda "no determinado" hasta que una persona lo confirme (baja la coincidencia).
2. **Cuadros mal leídos con confianza alta** no tienen criterio objetivo: no entran en la visión. Alternativa: mandar a visión toda página reconocida por OCR de las ofertas (más tiempo, y riesgo de empeorar texto que estaba bien). Propuesta: no, y evaluar con la medición cuántos pares quedan.
3. **Umbrales de adopción del 26B** (mejora neta de al menos 4 pares, hasta 30 minutos por oferta, memoria hasta 22.000 MiB): confirmar o ajustar antes de medir.
