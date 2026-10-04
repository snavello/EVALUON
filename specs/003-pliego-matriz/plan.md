# Plan 003 · Procedimiento, pliego final y matriz de cumplimiento

Estado: aprobado · Fecha: 2026-10-03 · Aprobó: responsable del proyecto · Enmienda: 2026-10-04, tope de sobrantes, REQ-033, REQ-034 y proceso único sin niveles (sección "Enmienda del 2026-10-04"), pendiente de aprobación del responsable

Spec: `specs/003-pliego-matriz/spec.md` (aprobada el 2026-10-03, enmendada el mismo día: requisitos técnicos por renglón, criterio de requisito y de clase, tipos de consecuencia y REQ-032; enmendada el 2026-10-04: requisitos en tramos pendientes, tope de sobrantes, REQ-033 y REQ-034).

ADR de este plan:

- `docs/adr/0018-pedidos-largos-en-segundo-plano.md`, **aceptado**: pedidos largos en una tabla de la base con un servicio `worker`, y una segunda instancia del motor de generación para esos pedidos.
- `docs/adr/0019-matriz-por-tramos-con-disposicion-obligatoria.md`, **aceptado**: la matriz se propone recorriendo el pliego por tramos, cada tramo con su disposición obligatoria; los requisitos formales y económicos con un fragmento literal verificado y los técnicos en una fila por renglón.
- `docs/adr/0020-pdf-de-la-matriz-en-el-equipo.md`, **propuesto**: el PDF de la matriz se genera en el equipo con WeasyPrint (REQ-032, agregado después de aprobadas las decisiones de este plan).

- `docs/adr/0021-filtro-de-precision-de-la-matriz.md`, **propuesto**: el filtro de sobrantes como pasada separada, con dos preguntas distintas, descarte visible y recuperable, y unificación por regla (REQ-033; enmienda del 2026-10-04).

ADR en los que se apoya: 0002 (motor y modelo), 0003 (recuperación), 0004 (lectura y cita literal), 0005 (aplicación web), 0006 (dos regímenes), 0009 (respuestas de la Comisión), 0011 (medición), 0012 (suite), 0014 (puntos 6 y 7), 0015, 0017.

## En pocas palabras

1. **Procedimiento.** Un integrante de la Comisión registra el procedimiento con su número, tipo, objeto y fecha de autorización. La pantalla muestra el régimen que corresponde a esa fecha, calculado con la misma función de la 001: hasta el 2023-01-01, la Disposición 297/03; desde el 2023-01-02, la 247/2022.
2. **Pliego.** Se cargan por pantalla los documentos del pliego final: el pliego particular, sus anexos, las especificaciones técnicas y, si las hay, las circulares y las respuestas a consultas, cada una con su fecha. El sistema guarda cada original sin cambios y lo lee en segundo plano, con las mismas herramientas de la 001 (PDF con texto o escaneado).
3. **Tramos.** Reglas fijas parten el pliego en tramos: cada cláusula y subcláusula numerada, cada viñeta, cada párrafo de un anexo, cada tabla. Nada queda afuera: lo que no se pudo leer queda como tramo pendiente de revisión. Las reglas reconocen también los renglones y las secciones que el pliego dedica a una clase de requisitos (por ejemplo, "Especificaciones técnicas").
4. **Matriz propuesta.** Se elige el nivel de revisión (media, alta o exigente; por omisión, alta) y el sistema trabaja en segundo plano.
   - **Formales y económicos:** una fila por condición. El modelo recorre los tramos y, para cada uno, propone sus requisitos o dice por qué no tiene ninguno. Cada requisito es un fragmento literal del pliego que el sistema comprueba palabra por palabra.
   - **Técnicos:** una fila por renglón, que cita los tramos de sus especificaciones técnicas. La Comisión no evalúa ese detalle: se apoya en el informe técnico del área requirente (feature 004).
   - Para cada requisito sugiere las consecuencias de no cumplirlo, cada una con la cláusula del pliego o el artículo de la norma que la sostiene. Si una circular cambia un requisito, la matriz muestra el texto nuevo y el anterior, con la cita de la circular. Cuando termina, avisa.
5. **Revisión y validación.** El operador y el evaluador corrigen, quitan o agregan requisitos; el evaluador confirma, elige la consecuencia de cada requisito con su motivo y valida la matriz. Todo cambio queda registrado con quién y cuándo. Una matriz validada no cambia: modificarla crea una versión nueva.
6. **Salidas.** La matriz se ve en pantalla, se imprime y se exporta a PDF dentro del equipo. Mientras no está validada, cada página dice "BORRADOR INCOMPLETO"; validada, lleva su versión, la fecha y el evaluador que la validó.
7. **Medición.** Con la lista de requisitos esperada del caso de referencia, que vive fuera del repositorio, un comando mide qué requisitos se encontraron, cuáles sobran, si las citas son literales y cuánto tarda cada nivel.

## Resumen del enfoque

Un módulo nuevo de Django, `evaluon/tenders/`, con el mismo esquema de capas de la 001: las funciones de negocio reciben al usuario, comprueban su rol y dejan el registro; la pantalla y los comandos solo traducen y llaman (ADR-0005). La lectura de documentos y el texto canónico se reutilizan de `evaluon/norms/reading/` y `evaluon/norms/splitting/canonical.py` sin cambios. Los trabajos largos (leer un documento, proponer una matriz) van a una tabla de pedidos que atiende un servicio `worker`, con su propia instancia del motor de generación (ADR-0018). La propuesta recorre el pliego por tramos con disposición obligatoria y cita verificada (ADR-0019). Para las consecuencias con fundamento normativo se reutilizan la recuperación y la selección de la 001 (`evaluon/queries/retrieval.py`) a la fecha de autorización del procedimiento. El PDF se genera en `app` con WeasyPrint (ADR-0020). El camino del pliego no usa ningún servicio externo (P4).

## El pliego del caso de referencia

Lo que se leyó de `corpus/casos/caso-00/` para dimensionar el plan. No se transcriben datos personales.

| Dato | Valor |
|---|---|
| Documento | Un PDF de 20 páginas, todas con capa de texto: 19 de pliego y una hoja adicional de firma digital |
| Encabezados y pies | El lema del año arriba, número de página abajo, y el número del documento y "Página N de 19" como campos de formulario |
| Estructura | Sección I, condiciones particulares (cláusulas 1 a 28); Sección II, especificaciones técnicas generales; Sección III, especificaciones técnicas particulares (renglones 1 a 6); Sección IV, anexos I y II (declaraciones juradas). Índice en la página 2 |
| Numeración | Hasta cuatro niveles ("11.6.1.", "17.3.2."); a veces sin espacio después del número ("10.2.1.Una vez…"); vuelve a empezar en cada sección (hay una "1.1" en las secciones I, II y III) |
| Renglones | Seis, de alimento balanceado. Cada uno con una cláusula de composición de unas 30 condiciones ("Proteína bruta (mín.): 24%; …"), el desvío admitido y el tamaño de bolsa |
| Tablas | Detalle de renglones y cantidades (p. 5), nómina de funcionarios con documento de identidad (pp. 6 y 7), tipo de cotización (p. 11), multas (p. 13) |
| Consecuencias en el pliego | Regla general de la documentación (7.3), falsedad (7.4), garantía no individualizada (11.3), copia del pagaré (11.7), ofertas condicionadas (13.4), inscripción en el registro (16.2), requerimientos de la Comisión (16.3), remisión al art. 55 del régimen (16.4), REPSAL y deuda subsanables (16.5 y 16.6) |
| Fecha de autorización | 14 de noviembre de 2025, según la evaluación: régimen de la Disposición 247/2022 |
| Clase por sección | Las secciones II y III se titulan "especificaciones técnicas": sus tramos son técnicos por la sección. La I y la IV no nombran una clase: se clasifican por naturaleza |
| Tramos | Unos 200, de los que unos 130 están fuera de las secciones técnicas y pasan por el modelo |
| Requisitos | **Unos 30 a 40**: de 16 a 22 formales, de 8 a 12 económicos (garantía, cotización, moneda, forma y plazo de pago) y 6 técnicos, uno por renglón. Estimación; la cifra la da la lista esperada (T-076) |
| Qué verificó la evaluación | Garantía de mantenimiento de oferta; habilidad de los oferentes (registro de proveedores, deuda, REPSAL, sanciones); ajuste de lo ofrecido a cada renglón (por ejemplo, alimento para cachorros y no para adultos, tamaño de bolsa); razonabilidad de precios. Dos renglones de una oferta se declararon inadmisibles por el art. 55 inc. h) del anexo de la 247/2022 |

Sin circulares ni respuestas a consultas: REQ-031 se prueba con un pliego sintético.

## Componentes

| Componente | Nuevo | Qué hace | Con quién habla |
|---|---|---|---|
| `app` | Cambia | Suma las páginas de procedimientos, documentos y matrices, la vista de impresión y el PDF (WeasyPrint, ADR-0020), y el comando `medir_matriz` | `db`; `generation`, `embeddings`, `reranker` como en la 001 |
| `worker` | Sí (ADR-0018) | Misma imagen que `app`. Corre `procesar_pedidos`: lee documentos y propone matrices, un pedido por vez | `db`; `generation_batch`; `embeddings` y `reranker` para consecuencias y circulares |
| `generation_batch` | Sí (ADR-0018) | Segunda instancia de `llama-server` con el mismo modelo, compilación y contexto que `generation`, `--parallel 1`, `--offline` | Solo `worker` y `app` (el comando de medición) |
| `db`, `generation`, `embeddings`, `reranker`, `migrate` | No | Los de la 001, sin cambios de configuración | — |

Reglas de comunicación, las de la 001: red interna sin salida a internet, sin puertos publicados salvo `app` en `127.0.0.1`. Las funciones de `tenders/services/` son el único camino para operar. `GENERATION_BATCH_URL` decide qué motor usa el `worker`; si apunta a `generation`, se vuelve a un solo motor sin cambiar código. WeasyPrint no busca nada por red: un `URLFetcher` propio solo entrega la hoja de estilos de impresión desde el disco (ADR-0020).

## Estructura del código

```
evaluon/tenders/
├── models.py  migrations/          tablas de este plan
├── segmenting.py                   tramos, renglones y clase por sección; cobertura (ADR-0019)
├── tables.py                       zonas de tabla de cada página de un PDF (pdfplumber)
├── jobs.py                         cola de pedidos: encolar, tomar, terminar, interrumpidos (ADR-0018)
├── export.py                       PDF de una versión de la matriz (ADR-0020, REQ-032)
├── services/
│   ├── procedures.py               registrar y listar procedimientos (REQ-022)
│   ├── documents.py                cargar documentos, leerlos, entregar el original (REQ-023, REQ-028)
│   ├── matrix.py                   pedir una propuesta, ver una matriz (REQ-024, REQ-030)
│   ├── review.py                   confirmar, corregir, quitar, agregar, resolver pendientes (REQ-026, REQ-028)
│   ├── consequences.py             elegir la consecuencia (REQ-029)
│   └── validation.py               validar, descartar borrador, abrir versión nueva (REQ-027)
├── proposal/
│   ├── run.py                      orden de las pasadas según el nivel; crea la versión propuesta
│   ├── quotes.py                   ubicar un fragmento literal dentro de un tramo
│   ├── extraction.py               extracción por lotes con disposición obligatoria
│   ├── technical.py                filas técnicas por renglón y sus controles
│   ├── completeness.py             pasada de completitud y segunda extracción (alta y exigente)
│   ├── consequences.py             sugerencia de consecuencias con fundamento
│   └── circulars.py                efecto de circulares y respuestas a consultas (REQ-031)
├── prompts/                        instrucciones versionadas, un archivo por versión
├── evaluation.py                   medición contra una lista esperada
├── views/  urls.py                 un archivo de vistas por tema
└── management/commands/            procesar_pedidos, medir_matriz
evaluon/templates/tenders/          procedimientos, procedimiento, matriz, impresión, cobertura, historial
evaluon/static/tenders/             hoja de estilos de la matriz y de impresión
tests/tenders/                      pruebas; conftest.py propio con usuarios de la Comisión; pliegos sintéticos
```

## Modelo de datos

Nombres en inglés; los valores que nombran un concepto del dominio, en español sin tildes, como en la 001. Todas las tablas son nuevas salvo dos cambios: el rol de la Comisión en `accounts_user` y los tipos de hecho en `audit_event`.

### accounts y audit

- **`accounts_user.commission_role`**: `''` (ninguno), `operator` o `evaluator`. Independiente de `role`, que sigue siendo el de la normativa (`read`, `read_write`). Ver "Roles".
- **`audit_event.event_type`** suma: `procedure`, `tender_load`, `tender_read`, `matrix_request`, `matrix_proposal`, `requirement_change`, `consequence_choice`, `segment_review`, `matrix_validation`, `matrix_version`, `matrix_export`. Todos caben en los 20 caracteres del campo. La migración cambia la restricción de valores válidos.

### Procedimiento y documentos

**`tenders_procedure`**

| Campo | Contenido |
|---|---|
| `id` | Identificación |
| `number` | Número del procedimiento tal como lo escribe la persona ("A0PC000000-0004-LPU25"). Único |
| `procedure_type` | Tipo, texto que escribe la persona ("Licitación pública"). Ninguna regla depende de él |
| `subject` | Objeto |
| `authorization_date` | Fecha de autorización. No puede ser posterior al día, como en la 001 |
| `created_at`, `created_by` | Alta |

El régimen no se guarda en el procedimiento: se calcula con `applicable_regimes(fecha)` de la 001 cada vez que se muestra, y queda fijado en el registro del alta y en cada propuesta de matriz, con la versión de la normativa (P8).

**`tenders_document`**: un archivo cargado.

| Campo | Contenido |
|---|---|
| `id`, `procedure` | Identificación y procedimiento |
| `kind` | `pliego`, `anexo`, `especificaciones`, `circular_modificatoria`, `circular_aclaratoria` o `respuesta_consulta` |
| `title` | Nombre con que se lo muestra ("Pliego de bases y condiciones particulares", "Circular N.º 1") |
| `issued_on` | Fecha del documento. Obligatoria en circulares y respuestas (REQ-031); opcional en los demás |
| `file_name`, `file_format`, `file_size`, `file_sha256` | Como en la 001. La huella es única dentro del procedimiento: el mismo archivo dos veces se rechaza con aviso |
| `loaded_at`, `loaded_by` | Carga |

**`tenders_document_file`**: el original byte por byte (`bytea`), en tabla aparte, como en la 001 (REQ-023).

**`tenders_reading`**: una lectura de un documento. `document`, `sequence`, `pages` (la lectura de la 001, en JSON), `tables` (zonas de tabla por página), `canonical_text`, `canonical_sha256`, `items` (renglones reconocidos: número y clave del tramo de su encabezado), `tool_versions` (las de la 001 más la versión de las reglas de tramos), `report` (páginas por estado, tramos por tipo, cobertura, pendientes), `created_at`, `job`. No se modifica.

**`tenders_segment`**: un tramo. No se modifica.

| Campo | Contenido |
|---|---|
| `id`, `reading`, `order` | Identificación, lectura y posición |
| `key` | Clave estable dentro de la lectura (ver "Tramos") |
| `label`, `path` | Encabezado tal como figura y ruta legible ("Sección I › 11. Garantía de mantenimiento de la oferta › 11.3") |
| `segment_type` | `titulo`, `clausula`, `vineta`, `parrafo`, `tabla`, `pagina` (página sin texto legible) o `no_ubicado` |
| `section_class` | `''`, `formal`, `economico` o `tecnico`: la clase que nombra el título de su sección, si la nombra (ver "Clase") |
| `items` | Renglones a los que pertenece (lista; vacía si es general) |
| `page_start`, `page_end`, `char_start`, `char_end`, `text` | Ubicación y texto literal: `text` es igual a `canonical_text[char_start:char_end]` |
| `text_origin`, `ocr_confidence_min`, `ocr_confidence_avg` | Como en la 001 |
| `review_reason` | Vacío, o `pagina_ilegible`, `pagina_dudosa`, `tabla`, `no_ubicado` (REQ-028) |

### Pedidos y propuestas

**`tenders_job`**: un pedido en segundo plano (ADR-0018). `kind` (`read_document`, `propose_matrix`), `status` (`queued`, `running`, `done`, `failed`), `procedure`, `document`, `requested_by`, `requested_at`, `started_at`, `finished_at`, `error`, `seen_at` (cuándo vio el aviso quien lo pidió).

**`tenders_matrix_run`**: una propuesta de matriz.

| Campo | Contenido |
|---|---|
| `id`, `procedure`, `job` | Identificación |
| `level` | `media`, `alta` o `exigente` (REQ-030) |
| `channel` | `screen` o `eval` |
| `documents` | Cada documento usado con su lectura y su huella |
| `authorization_date`, `regime`, `corpus_version` | Fecha, régimen aplicado y versión de la normativa tomados al empezar (P8) |
| `models` | Nombre, huella del archivo y compilación del motor de `generation_batch`; nombre y huella de `embeddings` y `reranker` |
| `parameters`, `prompt_versions` | Copia de los parámetros y versión de cada instrucción |
| `counts`, `timings`, `anomalies` | Tramos, requisitos por clase, descartes, pendientes, citas reintentadas y amplias; tiempo por pasada y total; fallas |
| `version` | Versión de matriz que creó; vacío hasta terminar |

**`tenders_run_step`**: un pedido al modelo dentro de una propuesta. `run`, `pass_name` (`extraccion`, `extraccion_2`, `completitud`, `consecuencias`, `circulares`), `batch`, `segment_keys`, `request` (el pedido completo), `raw_output`, `parsed`, `anomalies`, `retry_of`, `timings`. Solo se insertan filas. Con esta tabla se reconstruye por qué el sistema propuso cada requisito (P6).

**`tenders_disposition`**: qué pasó con cada tramo en una propuesta. `run`, `segment`, `outcome` (`requisitos`, `tecnico`, `descartado`, `pendiente`), `discard_reason` (lista cerrada del ADR-0019), `source` (`modelo` o `regla`: por ejemplo, un tramo de una sección técnica lo dispone la regla), `step`. Una por tramo y propuesta: es el control de cobertura. Un tramo con fragmentos formales o económicos y además citado por una fila técnica queda `requisitos`.

### Matriz

**`tenders_matrix_version`**

| Campo | Contenido |
|---|---|
| `id`, `procedure`, `number` | Número correlativo dentro del procedimiento |
| `status` | `draft`, `validated` o `discarded` |
| `level` | Nivel de la propuesta de la que sale; una versión abierta sobre otra conserva el de su origen (REQ-030) |
| `run` | Propuesta que la creó; vacío si se abrió sobre una validada |
| `based_on` | Versión validada de la que se copió, si corresponde |
| `created_at`, `created_by`, `validated_at`, `validated_by`, `discarded_at`, `discarded_by` | Momentos y personas |

Un procedimiento tiene a lo sumo un borrador a la vez. La matriz vigente para la 008 y la 004 es la última validada.

**`tenders_requirement`**

| Campo | Contenido |
|---|---|
| `id`, `version`, `number` | Número dentro de la versión: primero los formales y económicos en el orden del pliego, después los técnicos por renglón |
| `category` | `formal`, `economico` o `tecnico` |
| `items` | Renglones. Un técnico tiene exactamente uno (o ninguno si el pliego no tiene renglones). Un formal o económico, los del tramo del que sale, o ninguno si es general |
| `origin` | `propuesto`, `agregado` (por una persona) o `circular` (lo agrega una circular) |
| `state` | `propuesto`, `confirmado` o `quitado` |
| `proposed` | Copia de lo propuesto por el sistema (clase, renglones y citas), que no cambia (REQ-026) |
| `previous` | El mismo requisito en la versión anterior, si se copió |
| `step`, `passes` | Pedido que lo produjo y pasadas que lo encontraron (vacío en las filas técnicas, que arma una regla) |

**`tenders_requirement_quote`**: las citas de un requisito (REQ-025). `requirement`, `order`, `segment`, `char_start`, `char_end`, `text`, `scope`, `quote_flag`. `text` es igual al recorte del texto canónico.

- Un formal o económico tiene **una** cita: el fragmento literal de la condición. `scope` vacío.
- Un técnico tiene **una cita por tramo** de sus especificaciones, con el tramo entero: `scope` `propia` (tramos del renglón) o `general` (especificaciones técnicas comunes a todos los renglones, por ejemplo, la Sección II del caso-00 o el plazo de entrega).
- `quote_flag`: vacío o `cita_amplia` (en un formal o económico, el fragmento no se pudo ubicar y se cita el tramo entero).

**`tenders_requirement_source`**: textos que una circular o una respuesta suman a un requisito (REQ-031). `requirement`, `quote` (la cita alcanzada; en un técnico, el tramo de la especificación que cambia), `effect` (`modifica`, `aclara`, `suprime`), `segment`, `char_start`, `char_end`, `text`, `issued_on`, `step`. El texto vigente de una cita es el del último `modifica` por fecha; si no hay, el original. Un `suprime` deja el requisito (o, en un técnico, esa cita) como quitado por la circular, visible y con su cita.

**`tenders_consequence`**: una consecuencia posible de un requisito (REQ-029). `requirement`, `consequence_type` (lista cerrada, ver "Consecuencias"), `grounds` (lista de fundamentos: tramo del pliego con sus posiciones, o unidad de la norma por su `id` de `norms_unit`), `origin` (`sistema` o `persona`), `step`, `chosen`, `chosen_by`, `chosen_at`, `chosen_note` (el motivo del evaluador; en una aprobación condicionada, la condición). Un requisito sin opciones del sistema queda con la consecuencia "no determinada".

**`tenders_pending_item`**: un tramo pendiente de revisión dentro de una versión (REQ-028). `version`, `segment`, `reason` (los de la lectura, `sin_disposicion`, `marcadores`, `renglon_sin_especificaciones`), `resolved_by`, `resolved_at`, `resolution` (`sin_requisitos` o `requisito_agregado`).

**`tenders_requirement_change`**: historial (REQ-026). `requirement`, `action` (`confirmar`, `corregir`, `quitar`, `restituir`, `agregar`, `elegir_consecuencia`), `before`, `after`, `user`, `at`, `event`. Solo se insertan filas.

**Inmutabilidad.** Las funciones de negocio rechazan cualquier cambio sobre una versión validada, y un trigger de la base rechaza UPDATE y DELETE sobre sus requisitos, citas, fuentes, consecuencias y pendientes, igual que con `audit_event` en la 001 (REQ-027).

### Parámetros

En `settings.py`, valores iniciales, copiados en cada propuesta: niveles disponibles (`MATRIX_LEVELS`), nivel por omisión (`alta`), niveles ofrecidos (`MATRIX_LEVELS_OFFERED`: los tres hasta la medición; después, los que decida el responsable), tokens de entrada por lote (1.500), máximo de salida por pedido (4.096), largo máximo de un tramo antes de partirlo (4.000 caracteres), requisitos por pedido de consecuencias (25), candidatos por tramo de circular (8), versiones de instrucciones, `GENERATION_BATCH_URL`, espera máxima de un pedido del `worker` (180 s) y segundos entre consultas a la cola (5).

## Roles

| Operación | Operador | Evaluador |
|---|---|---|
| Registrar un procedimiento, cargar documentos, pedir una propuesta de matriz | sí | sí |
| Ver procedimientos, documentos, matrices, cobertura e historial; imprimir y exportar a PDF | sí | sí |
| Corregir, quitar o agregar requisitos en un borrador; abrir una versión nueva sobre una validada | sí | sí |
| Confirmar requisitos, elegir la consecuencia, dar por revisado un tramo pendiente | no | sí |
| Validar la matriz o descartar un borrador | no | sí |

El operador "propone correcciones" porque todo el borrador es una propuesta hasta que un evaluador lo valida; lo que cuenta como decisión (confirmar, elegir la consecuencia, validar) queda en manos de un evaluador (P3). Un usuario sin rol de la Comisión no ve estas páginas. El rechazo por rol se registra como en la 001 (`rejected`). `crear_usuario` suma la opción `--rol-comision`.

## Carga y lectura (REQ-023, REQ-028)

1. La persona elige el archivo, el tipo, el título y, si es una circular o una respuesta, la fecha. Se guarda el original y se encola su lectura. Hecho `tender_load`.
2. El `worker` lee con `evaluon.norms.reading.read_document` (PDF con texto o escaneado, página por página) y arma el texto canónico con `build_canonical_text` (encabezados y pies repetidos descartados, ADR-0004). Sobre los PDF busca además zonas de tabla con pdfplumber (`tables.py`), sin tocar la lectura de la 001.
3. Parte en tramos (`segmenting.py`) y guarda lectura, tramos, renglones e informe. Hecho `tender_read`.
4. La página del procedimiento muestra el estado de cada documento y, si hay, las páginas ilegibles o dudosas y las tablas, que ya figuran como pendientes de revisión.

El original se entrega con la misma vista de la 001 (sesión obligatoria; un PDF se abre en el visor del navegador en la página citada).

## Tramos (ADR-0019)

Reglas sobre las líneas del texto canónico. Un encabezado solo se reconoce al comienzo de una línea.

| Elemento | Forma | Qué produce |
|---|---|---|
| Sección | Línea en mayúsculas `SECCIÓN I - …` | Contenedor `sec-i`; su encabezado es un tramo `titulo`. Si el título nombra una clase, la pasa a sus tramos (ver "Clase") |
| Cláusula numerada | `7.`, `7.5.`, `7.5.2.`, `10.2.1.Una vez` (con o sin espacio) | Tramo `clausula` con clave `sec-i/7.5.2`. Control de secuencia: se acepta si continúa la numeración de su sección (hermano siguiente, primer hijo o vuelta a un nivel superior); así "3.972 kcal" o "1.300 mg" al comienzo de una línea no cortan |
| Título de cláusula sin texto | "8. VIGENCIA DE LA ORDEN DE COMPRA…" solo | Tramo `titulo` |
| Renglón | Cláusula cuyo encabezado dice "RENGLÓN N° k"; o "RENGLONES NROS. j A k" | `items` del tramo y de los que cuelgan de él; el renglón entra en `items` de la lectura |
| Viñeta o inciso | `•`, `−`, `–`, `-` o `a)` al comienzo de línea, dentro de una cláusula | Tramo `vineta` con clave `sec-ii/1.2/v-1` o `…/inc-b` |
| Anexo | Línea en mayúsculas `ANEXO I - …` | Contenedor `sec-iv/anexo-i`; cada párrafo es un tramo `parrafo` (`sec-iv/anexo-i/p-3`) |
| Tabla | Líneas dentro de una zona de tabla | Un tramo `tabla` por zona (`sec-i/6/tabla-1`), con `review_reason` `tabla` |
| Índice | Líneas con puntos guía y número de página | Descartadas en la lectura, como el índice de la 001 |
| Antes de la primera sección | Carátula | Tramos `parrafo` con clave `pre/p-1` |
| Página sin texto legible | Página ilegible o no leída | Tramo `pagina` (`pagina-7`) sin texto, pendiente de revisión |
| Tramo largo | Más de 4.000 caracteres | Se parte en límites de oración: `sec-iii/1.1#2` |

- Un pliego sin secciones usa las claves sin prefijo (`7.5.2`). Una clave repetida suma `~2`.
- **Cobertura.** Todo carácter del texto canónico está en un solo tramo; lo descartado por la lectura se cuenta aparte; la suma da el total. Un tramo que no encaja en ninguna regla queda `no_ubicado`, pendiente de revisión.
- Las claves son públicas en este plan porque la lista esperada las usa (ver "Medición").

## Qué es un requisito y su clase (spec, decisiones del responsable)

**Requisito de la oferta.** Lo que la oferta tiene que presentar, ofrecer o comprometer, y toda condición del pliego que la oferta pueda contradecir o condicionar, aunque la cumpla el organismo. En el caso-00:

| Cláusula del caso-00 | ¿Es requisito? | Clase | Por qué |
|---|---|---|---|
| 7.5.2 Presentar la declaración jurada de habilidad | sí | formal | documento de la presentación |
| 11 Garantía de mantenimiento del 5 % | sí | económico | garantía, por naturaleza |
| Cotizar en pesos con IVA, precio unitario por renglón | sí | económico | precio y moneda |
| 25.1 Forma, moneda y plazo de pago | sí | económico | la oferta puede contradecirla (por ejemplo, pedir pago a los 3 días de la entrega cuando el pliego dice 90) |
| Mantener la oferta 60 días corridos | sí | formal | compromiso de la presentación |
| Inscripción en el registro de proveedores | sí | formal | condición de la presentación |
| 9.2.1 Entrega en 15 días hábiles | sí | técnico | el bien y su entrega; entra como cita `general` en la fila de cada renglón |
| Sección II, 1.3 Vencimiento mayor a 11 meses | sí | técnico | por la sección; cita `general` en cada renglón |
| Sección III, renglón 1 (composición, desvío, bolsa) | sí | técnico | por la sección; **una fila**, la del renglón 1 |
| 24.3 Multas por atraso | no | — | ejecución y control del contrato |

**Clase.** Si el título de la sección nombra una clase ("especificaciones técnicas", "requisitos económicos", "requisitos formales"), la clase de sus tramos es la de la sección (`section_class`, la pone la regla, no el modelo). Si no, se clasifica por naturaleza: la garantía, el precio, la moneda y el pago son económicos; los documentos y compromisos de la presentación, formales; el bien y su entrega, técnicos.

**Granularidad.**

- Formales y económicos: una fila por condición que se pueda verificar por separado, para que un "no cumple" señale la condición exacta.
- Técnicos: una fila por renglón del pliego, con la cita de los tramos de sus especificaciones técnicas (`propia`) y de las especificaciones técnicas comunes a todos los renglones (`general`). Una oferta puede cotizar o cumplir solo algunos renglones. La Comisión no evalúa el detalle técnico: se apoya en el informe técnico del área requirente, que es el fundamento de esas filas en la evaluación (feature 004).

## Propuesta de la matriz (REQ-024, REQ-025, REQ-028, REQ-029, REQ-030, REQ-031)

### Pedido

La persona elige el nivel entre los ofrecidos (por omisión, alta) y pide la propuesta. Se rechaza si hay un borrador abierto, si algún documento base está en lectura o si no hay ningún documento base. Hecho `matrix_request`. El `worker` toma el pedido, fija fecha, régimen y versión de la normativa, y corre las pasadas del nivel. Los pedidos al modelo van a `generation_batch`, con temperatura 0, semilla fija y pensamiento apagado, como en la 001; el cliente de generación suma un máximo de salida por pedido.

### Pasadas

| Pasada | Media | Alta | Exigente | Qué hace |
|---|---|---|---|---|
| Disposición por regla | sí | sí | sí | Tramos `titulo` → descartado ("título"); `pagina` y `no_ubicado` → pendiente; tramos de una sección técnica → `tecnico`, de su renglón o, sin renglón, `general`. Estos tramos no pasan por el modelo |
| Extracción | sí | sí | sí | Lotes de tramos consecutivos de los restantes (hasta 1.500 tokens). Por cada tramo: requisitos formales o económicos, marca técnica, o motivo de descarte |
| Segunda extracción | — | — | sí | La misma extracción, sobre los mismos tramos, con los lotes desplazados medio lote; se une con la primera: un requisito nuevo entra si su cita no se superpone en más de la mitad con otro del mismo tramo; un tramo descartado en una y con requisitos o marca técnica en la otra queda con lo encontrado |
| Completitud | — | sí | sí | Solo formales y económicos. Cada tramo con sus requisitos ya encontrados: devuelve los que faltan y divide los que juntan dos condiciones. Recibe además los tramos descartados que tienen marcadores de obligación ("deberá", "deberán", "será requisito", "mín.", "máx.", "no se aceptarán", "bajo apercibimiento", "desestim") |
| Marcadores en media | sí | — | — | En media no hay completitud: los tramos descartados con marcadores de obligación quedan pendientes de revisión |
| Filas técnicas | sí | sí | sí | Por regla (`technical.py`, ver abajo) |
| Circulares | si hay | si hay | si hay | Ver "Circulares y respuestas" |
| Consecuencias | sí | sí | sí | Ver "Consecuencias" |

**Los niveles con menos filas.** Con requisitos técnicos por renglón y las secciones técnicas dispuestas por regla, lo técnico es igual en los tres niveles: los niveles solo cambian cómo se buscan los formales y los económicos (unos 30 en el caso-00, sobre unos 130 tramos). Se simplifican así:

- **Alta** conserva la completitud, que ataca las dos causas de faltante que quedan: un tramo descartado que tenía una condición y dos condiciones juntas en una fila.
- **Exigente** conserva la segunda extracción, ahora solo sobre los tramos que pasan por el modelo, y una unión más simple, porque no une filas técnicas.
- Con unas 30 filas, la diferencia entre niveles puede ser de una o dos filas, o ninguna. Si media ya encuentra todo en el caso-00, por la regla de la spec alta y exigente no se ofrecen; y como alta es el nivel por omisión, el responsable indica cuál lo reemplaza (T-085). Los tres se construyen porque REQ-030 los pide; la corrida de T-084 decide cuáles se ofrecen.

### Extracción: qué recibe y qué devuelve el modelo

- **Recibe.** Las instrucciones (`prompts/matriz-extraccion-v1.md`): qué es un requisito de la oferta y qué no (sección "Qué es un requisito y su clase", con ejemplos sintéticos, incluido el de la forma de pago), los criterios de clase por naturaleza, "una fila por condición" para formales y económicos, cuándo marcar un tramo como técnico, la lista cerrada de motivos de descarte y la regla de copiar el fragmento exacto. Después, cada tramo del lote con un alias (`T1`, `T2`, …), su ruta, sus renglones y su texto.
- **Devuelve** un JSON que el motor obliga a cumplir. El esquema tiene una propiedad obligatoria por alias del lote; cada una trae `requisitos` (lista de `{cita, clase}`, con `clase` entre `formal` y `economico`), `tecnico` (vacío, o los renglones a los que se aplica, o `todos`) y `descarte` (motivo de la lista o vacío).
- **El sistema valida**, tramo por tramo:
  - Sin requisitos, sin marca técnica y sin descarte, o con descarte y algo más: tramo sin disposición.
  - Cada `cita` se busca exacta dentro del texto del tramo (`quotes.py`). Si aparece más de una vez, se toma la primera aparición no usada. Si no aparece, el requisito se marca para reintento.
  - Dos requisitos del mismo tramo con la misma cita se unen.
  - Los tramos sin disposición y los requisitos con cita no encontrada se vuelven a pedir una vez, solos. Si siguen igual: el tramo queda **pendiente**, y el requisito queda con el tramo entero como cita y la marca `cita_amplia`.
  - Si la salida se cortó por el máximo de salida, el lote se parte en dos y se repite cada mitad.
  - Si el tramo cuelga de un renglón, sus renglones son los del tramo, no los del modelo.
- El requisito **no lleva texto redactado por el modelo**: se muestra el fragmento literal o los tramos citados, la clase y el renglón. Así toda la matriz es texto del pliego (P3) y la medición no depende de redacciones (ADR-0014, punto 7).

### Filas técnicas por renglón (`technical.py`)

1. **Renglones del pliego:** los de `items` de las lecturas de los documentos base. Si no hay ninguno, el pliego tiene una sola fila técnica, sin renglón.
2. **Una fila por renglón**, clase técnica, con una cita por tramo: los tramos `tecnico` de ese renglón (`propia`) y los tramos `tecnico` generales o marcados `todos` (`general`). Un tramo marcado por el modelo para algunos renglones va como `propia` en cada uno de ellos.
3. **Controles**, en todos los niveles: un renglón sin ningún tramo `propia` queda con su fila (con las citas generales) y un pendiente `renglon_sin_especificaciones` en el tramo de su encabezado; un tramo que cuelga de un renglón y que el modelo descartó entra igual en la fila del renglón (ante la duda, de más), con la anomalía registrada.
4. La pantalla muestra la fila como "Renglón k · Técnico · se evalúa con el informe técnico del área requirente", con la lista de tramos citados (ruta, página, enlace al original) y su texto literal desplegable.

### Cita (REQ-025)

La definición de "palabra por palabra" es la del ADR-0004 y la comprobación, la del plan 001: el texto mostrado es igual a `canonical_text[char_start:char_end]` de la lectura, en cada cita. La página sale de las líneas del texto canónico (`pages_at`); la cláusula, de la ruta del tramo. La pantalla muestra documento, página, cláusula y el enlace al original en esa página.

### Consecuencias (REQ-029)

**Tipos**, la lista cerrada de la spec:

| Código | Tipo | Quién lo puede proponer | Qué exige |
|---|---|---|---|
| `desestimacion` | Desestimación sin posibilidad de subsanar | sistema o evaluador | del sistema: fundamento del pliego o de la norma |
| `intimacion_subsanar` | Intimación a subsanar; si no se subsana, desestimación | sistema o evaluador | del sistema: fundamento del pliego o de la norma |
| `consultar_oferente` | Consultar al oferente | sistema o evaluador | la cita del pliego que lo permite (del sistema, o un tramo que elige el evaluador) |
| `aprobacion_condicionada` | Aprobación condicionada | solo el evaluador | la condición escrita |
| `aprobar_igual` | Aprobar de todas maneras | solo el evaluador | el motivo escrito |
| `otra_pliego` | Otra consecuencia prevista en el pliego | sistema o evaluador | la cita del pliego |
| `no_determinada` | No determinada | solo el sistema | es el estado de un requisito sin sugerencia con fundamento; no se elige |

El sistema solo sugiere; nunca decide si un requisito es subsanable ni si una oferta cumple. La consecuencia la elige siempre un evaluador, con su nombre y su motivo registrados (spec). El "cumple o no cumple" de cada oferta es de la evaluación (feature 004), no de esta feature.

**Cómo sugiere el sistema:**

1. **Fundamentos del pliego.** Los tramos de los documentos base con marcadores de consecuencia ("desestim", "inadmisib", "subsan", "intim", "apercibimiento", "causal suficiente", "rechaz", "requerir", "solicitar aclaraciones"), más los tramos del propio requisito. En el caso-00 son unos diez. Si superan el espacio, el reranker elige los más pertinentes a una pregunta fija.
2. **Fundamentos de la norma.** Las preguntas fijas de las instrucciones (por ejemplo, "¿Qué deficiencias de una oferta no son subsanables y causan su desestimación?", "¿Qué errores u omisiones de una oferta se pueden subsanar y cómo se intima al oferente?" y "¿Cuándo un renglón de una oferta es inadmisible?") pasan por la recuperación y la selección de la 001 (`retrieve` y `select_units`) con la fecha de autorización del procedimiento. Sin régimen a esa fecha, no hay fundamentos de la norma.
3. **Pedido.** De a 25 requisitos (en el caso-00, dos pedidos). El modelo recibe los fundamentos con alias (`P1…` del pliego, `N1…` de la norma, con norma y ruta) y los requisitos (`R1…`: un formal o económico con su fragmento; un técnico como "Renglón k, especificaciones técnicas" con la ruta de su encabezado). Devuelve, por requisito, hasta tres opciones `{tipo, fundamentos}`; `tipo` entre `desestimacion`, `intimacion_subsanar`, `consultar_oferente` y `otra_pliego`, y `fundamentos` solo entre los alias mostrados, al menos uno; `consultar_oferente` y `otra_pliego`, al menos uno del pliego.
4. **Validación**, como en la 001: un alias inexistente invalida la opción; un requisito sin opciones válidas queda **"no determinada"** (P3). El sistema pone el texto de cada fundamento desde la base.
5. **Elección.** Un evaluador elige una opción sugerida u otro tipo de la lista (salvo "no determinada"). Si acepta una sugerencia del sistema, el fundamento de la sugerencia es el motivo registrado y no tiene que escribir nada (aclaración del Coordinador, 2026-10-03, para no sumar trabajo en las 30 o 40 filas); si elige otra cosa, escribe su motivo, y en una aprobación condicionada, la condición. Si elige `consultar_oferente` u `otra_pliego` sin sugerencia del sistema, indica el tramo del pliego que la sostiene, con cita verificada. Queda registrado con quién, cuándo y el motivo (`consequence_choice`).

Ejemplo del criterio de aceptación con el caso-00: el requisito de la cláusula 11.3 ("La garantía de mantenimiento de la oferta deberá ser individualizada en ocasión de presentarse la oferta"), económico, recibe "desestimación sin posibilidad de subsanar" con la cita de esa misma cláusula, y queda confirmada solo cuando un evaluador la elige.

### Circulares y respuestas (REQ-031)

- Se leen y se parten como cualquier documento. Se procesan después de la extracción y de las filas técnicas, por fecha y, a igual fecha, por orden de carga.
- Para cada tramo de una circular o de una respuesta, las citas candidatas son las de los requisitos cuya cláusula o renglón el tramo nombra ("cláusula 1.1", "Renglón N° 2") más las 8 que el reranker puntúa más alto contra el texto del tramo. En un técnico, cada tramo citado es una candidata aparte.
- El modelo devuelve, por tramo, sus efectos (`modifica`, `aclara` o `suprime`, la cita alcanzada y la cita literal de la circular), requisitos nuevos que la circular agrega, o un motivo de "sin efecto". Las citas se verifican igual que en la extracción. Todo tramo de circular queda con disposición.
- En la pantalla, una cita modificada muestra el texto vigente (el de la circular, con su cita y su fecha) y el original (con la suya). Una aclaración o una respuesta figura junto al requisito con su cita.
- Ejemplo del criterio de aceptación, con un pliego sintético: el pliego exige "16 GB de RAM" en las especificaciones de un renglón y una circular posterior dice "32 GB". La fila del renglón muestra "32 GB" como vigente, "16 GB" como original y cita la circular.

### Abstención y fallas

- Un tramo nunca desaparece: tiene requisitos, va a una fila técnica, tiene un descarte con motivo o queda pendiente.
- Una consecuencia sin fundamento es "no determinada".
- Una falla técnica (servicio caído, espera agotada) deja el pedido en `failed` con su motivo; no se crea una matriz a medias. Lo ya registrado en `tenders_run_step` queda.

## Revisión, validación y versiones (REQ-026, REQ-027, REQ-028)

- **Confirmar** (evaluador): uno o varios requisitos seleccionados.
- **Corregir** (operador o evaluador): en un formal o económico, la clase, los renglones o la cita, elegida dentro de un tramo y comprobada literal, igual que la del modelo. En un técnico, sumar o quitar tramos citados. Un formal o económico pasado a técnico se une a la fila de su renglón.
- **Quitar** y **restituir**: el requisito queda `quitado`, visible y con su historia.
- **Agregar**: un formal o económico desde un tramo, con un fragmento literal, clase y renglón; una fila técnica para un renglón que no la tenga, con sus tramos. Origen `agregado`.
- **Resolver un pendiente** (evaluador): "revisado, sin requisitos", o agregando requisitos desde ese tramo.
- Cada cambio deja una fila en `tenders_requirement_change` y el hecho `requirement_change`, con lo de antes y lo de después. Lo propuesto originalmente queda en `proposed` y se consulta en el historial del requisito.
- **Validar** (evaluador): pasa la versión a `validated`. Condiciones (decisión del responsable): ningún pendiente sin resolver; cada requisito no quitado con su consecuencia elegida por un evaluador; los requisitos todavía propuestos quedan confirmados por la validación, cada uno con su fila de historial.
- **Versión nueva**: sobre la última validada se abre un borrador con número siguiente que copia requisitos, citas, fuentes, consecuencias elegidas y pendientes resueltos, cada uno con `previous`. La anterior no cambia (REQ-027).
- **Descartar un borrador** (evaluador): queda `discarded`, visible. Permite pedir una propuesta nueva.

## Pantalla

Páginas armadas en el servidor, sin htmx (ADR-0005), con la hoja de estilos y el script propios.

- **Procedimientos**: lista con número, objeto, fecha de autorización, régimen y estado de la matriz; formulario para registrar. Al registrar se muestra la línea "Procedimiento autorizado el 15/12/2022 · Régimen aplicable: Disposición AFIP 297/03", con el mismo texto fijo de la 001.
- **Procedimiento**: datos y régimen; documentos con su tipo, fecha, estado de lectura y enlace al original; formulario de carga; versiones de la matriz; formulario "Proponer matriz" con el nivel (alta marcado) y los pedidos en curso.
- **Matriz**: si la versión no está validada, la franja "BORRADOR INCOMPLETO" arriba, fija al desplazarse (REQ-032); si está validada, su número, la fecha de validación y el evaluador. Encabezado con versión, estado, nivel, régimen y fecha; resumen (requisitos por clase, pendientes, consecuencias sin elegir); "Pendiente de revisión" primero; formales y económicos agrupados por documento y sección, cada uno con su clase, su texto literal, su ubicación, los textos de circulares y respuestas, sus consecuencias con fundamento y sus acciones; después, las filas técnicas por renglón; casillas para confirmar varios; botones "Validar", "Vista de impresión" y "Exportar PDF".
- **Cobertura**: todos los tramos con su disposición, su origen (modelo o regla) y su motivo.
- **Historial** de un requisito.
- **Aviso de fin**: en cualquier página, un recuadro con los pedidos de la persona que terminaron y todavía no vio, con enlace (ADR-0018).

## Salidas: impresión y PDF (REQ-032, ADR-0020)

- **Una plantilla**, `tenders/matrix_print.html`, para la vista de impresión y para el PDF. Tiene lo mismo que la página de la matriz sin las acciones: encabezado del procedimiento, régimen, versión, estado y nivel; pendientes; requisitos con clase, texto literal, ubicación, textos de circulares; consecuencias (la elegida con su motivo, o las sugeridas si no hay elegida); filas técnicas por renglón con la lista de tramos citados. El texto completo de los tramos técnicos no se repite: se cita su ruta y su página.
- **Leyenda.** Toda versión que no esté validada (borrador o descartada) lleva "BORRADOR INCOMPLETO":
  - en el PDF, en las cajas de margen superior e inferior de `@page`, en negrita y tamaño grande, en cada página, con "Página N de M";
  - en la vista de impresión del navegador, en un elemento fijo arriba de la página, que la hoja de estilos de impresión repite en cada hoja impresa.
- **Validada.** Sin leyenda; en las cajas de margen, "Matriz validada · versión N · validada el DD/MM/AAAA por <evaluador>" y la página.
- **PDF.** `export.py` arma el HTML de la plantilla y lo convierte con WeasyPrint dentro de `app`, en el mismo pedido de la pantalla (una matriz de decenas de filas son pocas páginas). Un `URLFetcher` propio solo entrega `tenders/print.css` desde el disco y rechaza cualquier otra dirección; la plantilla no tiene recursos externos. El archivo se descarga con nombre `matriz-<procedimiento>-v<N>[-borrador].pdf`.
- **Imprimir.** La vista de impresión tiene un botón que llama a la impresión del navegador; para una copia en papel con la leyenda asegurada en cada hoja, se imprime el PDF.
- **Registro.** Cada exportación deja el hecho `matrix_export` con la versión, su estado, si llevó la leyenda, la cantidad de páginas y la huella del PDF. La vista de impresión no se registra: no produce un archivo.

## Registro de auditoría (P6)

| Hecho | Qué guarda además de los datos comunes |
|---|---|
| `procedure` | Número, tipo, objeto, fecha de autorización, régimen mostrado y versión de la normativa |
| `tender_load` | Procedimiento, tipo, título, fecha, nombre, formato, tamaño y huella del archivo; también las cargas rechazadas |
| `tender_read` | Lectura, versiones de las herramientas y de las reglas de tramos, páginas por estado, tramos por tipo, renglones reconocidos, cobertura, pendientes |
| `matrix_request` | Procedimiento, nivel, documentos y lecturas incluidos |
| `matrix_proposal` | Propuesta, versión creada o motivo de la falla, nivel, fecha, régimen, versión de la normativa, modelos con huella, parámetros, versiones de instrucciones, cuentas por clase, tiempos y anomalías. El detalle de cada pedido al modelo está en `tenders_run_step` |
| `requirement_change` | Versión, requisito, acción, antes y después |
| `consequence_choice` | Requisito, tipo elegido con sus fundamentos, si era sugerido por el sistema, y el motivo o la condición |
| `segment_review` | Versión, tramo, motivo del pendiente, resolución |
| `matrix_validation` | Versión, cuentas por estado y por clase, requisitos confirmados por la validación |
| `matrix_version` | Versión nueva, versión de la que sale; o borrador descartado |
| `matrix_export` | Versión, estado, leyenda sí o no, páginas, huella del PDF |
| `rejected` | Como en la 001 |

## Medición (ADR-0014, punto 7)

### Lista esperada

- **Dónde.** `corpus/casos/caso-00/esperado/matriz-esperada.yaml`, en el equipo propio, fuera del repositorio (`corpus/casos/` está en `.gitignore`), porque deriva de un documento con datos personales. La lista no transcribe ningún dato personal: nombres, documentos de identidad ni CUIT de personas.
- **Formato.**

```yaml
caso: caso-00
documentos:
  - archivo: PLIEG-2025-04092776-ARCA-DVGDCO#SDGADM.pdf
    sha256: <huella del archivo>
criterios: "spec 003, 'Qué es un requisito' (enmienda del 2026-10-03)"
preparo: "Coordinador, AAAA-MM-DD"
visto_bueno: "responsable, AAAA-MM-DD"        # sin esto, la lista no se usa
confirmacion_comision: pendiente              # feature 009
uso: primera_corrida                          # primera_corrida o ajuste
tecnico_general:                              # tramos técnicos comunes a todos los renglones
  - {documento: PLIEG-2025-04092776-ARCA-DVGDCO#SDGADM.pdf, tramo: sec-ii/1.3}
  - {documento: PLIEG-2025-04092776-ARCA-DVGDCO#SDGADM.pdf, tramo: sec-i/9.2.1}
requisitos:
  - id: M-001
    documento: PLIEG-2025-04092776-ARCA-DVGDCO#SDGADM.pdf
    tramo: sec-i/11.3
    pagina: 8
    ancla: "La garantía de mantenimiento de la oferta deberá ser individualizada en ocasión de presentarse la oferta"
    clase: economico
    renglones: []
    consecuencia: desestimacion                 # optativa; informativa
    en_dictamen: si                             # si, no
  - id: M-031
    clase: tecnico
    renglon: 1
    tramos: [sec-iii/1, sec-iii/1.1, sec-iii/1.2]   # tramos propios del renglón
    en_dictamen: si
```

  En formales y económicos, `ancla` es el fragmento literal más corto que identifica la condición, copiado del pliego; si aparece más de una vez dentro del tramo, se agrega `ocurrencia: 2`. En técnicos, una entrada por renglón con sus tramos propios; los generales van una sola vez en `tecnico_general`.
- **Cómo se prepara, sin correr el sistema.** La prepara el Coordinador leyendo el PDF, cláusula por cláusula, con los criterios de la spec ("Qué es un requisito") y las claves de "Tramos", que se derivan de la numeración impresa. Después la contrasta con lo que verificó la evaluación del caso (columna `en_dictamen`): todo lo que la evaluación verificó tiene que estar en la lista. Nadie corre la propuesta de matriz sobre el caso-00 hasta que la lista tenga el visto bueno; por eso T-075 (hilo mínimo) depende de T-076.
- **Cómo la aprueba el responsable.** Con una tabla de ejemplos (unos 12 requisitos de clases y secciones distintas, más los casos dudosos), las cuentas por clase y por sección, los renglones con sus tramos, y la lista de lo que verificó la evaluación con su requisito. El responsable anota el visto bueno en el archivo. La confirma después la Comisión (feature 009).
- **Antes de medir**, `medir_matriz --verificar-esperada` comprueba que la huella del archivo coincida con la del documento cargado, que cada ancla esté, exacta, en el tramo indicado, y que cada tramo técnico exista. No usa el modelo.

### Cómo se cuenta

1. **Ubicación.** Cada ancla se busca exacta en el tramo indicado, en el texto canónico de la lectura usada; cada tramo técnico, por su clave. Un ancla o un tramo que no aparece es una falla de la lectura o de la lista: se informa y bloquea.
2. **Formales y económicos: emparejamiento por cita, no por redacción.** Un requisito propuesto formal o económico empareja con uno esperado si están en el mismo documento y la cita propuesta cubre al menos la mitad de los caracteres del ancla. El emparejamiento es uno a uno: se ordenan los pares por superposición y se asignan de mayor a menor. Una fila que junta dos condiciones empareja con una sola: la otra cuenta como faltante, con causa "agrupado".
3. **Técnicos: emparejamiento por renglón.** Un esperado técnico empareja con la fila técnica propuesta del mismo renglón. Además se informa, por renglón, qué tramos esperados (propios y generales) no están entre sus citas.
4. **Encontrado**: requisito esperado emparejado. Un formal o económico esperado que ninguna fila formal o económica empareja, pero cuya ancla está dentro de un tramo citado por una fila técnica, cuenta como encontrado con clase equivocada. **Faltante**: no emparejado, con su causa: tramo descartado (y el motivo), tramo pendiente, agrupado con otro requisito, tramo con requisitos pero no este, renglón sin fila, ancla no encontrada.
5. **Sobrante**: requisito propuesto sin emparejar. Se informan la cantidad y su reparto por tramo y por clase. *Enmendado el 2026-10-04: tienen un tope, y se miden sobre la matriz sin las filas descartadas por el sistema; ver "Enmienda del 2026-10-04".*
6. **Clase**: entre los encontrados, los que tienen la clase esperada. La clase equivocada se informa y no bloquea (decisión del responsable).
7. **Cita literal**: sobre todas las citas propuestas, el texto es igual al recorte del texto canónico, cae dentro de su tramo y la página informada es la del recorte. Las citas amplias se cuentan aparte.
8. **Cobertura**: tramos con disposición sobre el total, por origen (modelo o regla), y pendientes por motivo. Se espera 100 % con disposición.
9. **Consecuencias** (informativo): donde la lista trae `consecuencia`, si está entre las sugeridas.

| Medida | Meta |
|---|---|
| Requisitos encontrados | 100 %. Cada faltante se informa con su causa y bloquea la aceptación |
| Cita literal | 100 % |
| Tramos con disposición | 100 % |
| Sobrantes | Hasta el 20 % de la matriz propuesta en el nivel por omisión, con el 100 % de encontrados (enmienda del 2026-10-04); ver "Enmienda del 2026-10-04" |
| Clase correcta | Se informa; no bloquea |
| Tramos técnicos citados por renglón | Se informa cada tramo que falta; no bloquea (la fila del renglón existe y el detalle lo evalúa el área requirente) |
| Tiempo por nivel | El de la spec, para unas 50 páginas (ver "Tiempos") |

### La corrida

- `medir_matriz --procedimiento <número> --esperada <archivo> --niveles media,alta,exigente`, dentro de `app`. Corre la propuesta con la misma función que el `worker`, con el canal `eval`; no exige que el procedimiento esté sin borrador, y las versiones que crea quedan descartadas al terminar, para no interferir con el trabajo real. Se corre de a una, sin otra carga en la GPU, salvo la prueba de contención (ver "Tiempos").
- Guarda una carpeta por corrida en `corpus/casos/caso-00/corridas/` (fuera del repositorio): `parametros.json`, `resultados.jsonl` (un renglón por requisito esperado y por propuesto), `resumen.md` (puede tener texto del pliego) y `resumen-publico.md`, que solo tiene identificadores `M-NNN`, claves de tramo, cuentas, causas y tiempos. Solo este último se copia al repositorio, en `specs/003-pliego-matriz/verificacion/T-084.md`.
- Cada proporción lleva su intervalo de Wilson al 95 %, con la función de la 001.

### Por qué la medida es provisoria

- Un solo pliego, y ahora con pocas filas: con 35 de 35 encontrados, el intervalo de Wilson va de 90 % a 100 %. Además, los requisitos de un mismo pliego no son independientes entre sí: la unidad que importa es el pliego.
- Con unas 30 filas formales y económicas, comparar niveles discrimina poco: una diferencia de una fila decide si un nivel se ofrece.
- ADR-0014, punto 7, pide una parte de los casos que nunca se use para ajustar. Con un pliego no hay cómo separarla. Decisión del responsable: las instrucciones `v1` quedan fijas antes de la primera corrida; esa primera corrida se informa como la medida independiente provisoria; si después se ajusta algo, el caso-00 pasa a ser de ajuste (`uso: ajuste`) y la aceptación espera al próximo pliego que aporte la Comisión, que se mide primero sin ajustes.
- La spec ya lo prevé: la medición se informa como provisoria y se repite cuando haya más casos.

## Tiempos y GPU

Estimación con lo medido en la 001 (unos 3.000 tokens por segundo al leer y 73 al escribir) y lo que se vio del caso-00: unos 200 tramos, de los que unos 130 pasan por el modelo (unos 7.000 tokens de texto), y unos 30 a 40 requisitos. La salida domina: cada disposición ocupa unos 15 tokens y cada fragmento formal o económico unos 40; las filas técnicas las arma una regla y no cuestan salida del modelo.

| Pasada | Caso-00 (20 páginas) | 50 páginas (×2,5) |
|---|---|---|
| Extracción (unos 3.200 tokens de salida) | 1 a 2 min | 3 a 5 min |
| Completitud | 0,5 a 1 min | 1 a 3 min |
| Segunda extracción y unión | 1 a 2 min | 3 a 5 min |
| Consecuencias (dos pedidos de hasta 25) | 0,5 a 1 min | 1 a 3 min |
| **Media** | **1,5 a 3 min** (límite 15) | **4 a 8 min** |
| **Alta** | **2 a 4 min** (límite 30) | **5 a 10 min** |
| **Exigente** | **3 a 6 min** (límite 60) | **8 a 15 min** |

Antes, con 200 a 250 filas, media era la que quedaba más cerca de su límite; ahora los tres niveles quedan con margen amplio, y lo que decide qué niveles se ofrecen es la mejora medida, no el tiempo. Los números son estimaciones: T-075 da la primera medición y T-084 la de todos los niveles. Como no hay un pliego de 50 páginas, el tiempo de 50 páginas se informa por página y por tramo, extrapolado y provisorio, hasta que la Comisión aporte uno (decisión del responsable).

| Memoria de video | MiB |
|---|---|
| `generation` + `embeddings` + `reranker` (medido en la 001) | 10.344 |
| `generation_batch` (mismo modelo y contexto que `generation`) | unos 7.818 |
| Total estimado | unos 18.162 de 24.137 libres |

T-071 mide la memoria con los cuatro modelos cargados. T-084 mide además una consulta de normativa sola y durante una propuesta de matriz; la exigencia de la 001 es de hasta 30 segundos. El PDF no usa la GPU.

## Enmienda del 2026-10-04: tope de sobrantes, filas descartadas y revisión por grupos (REQ-033, REQ-034)

La spec se enmendó el 2026-10-04 (decisión del responsable): descartar a mano cientos de filas empeora el trabajo de la Comisión. Esta sección agrega al plan un filtro de precisión, una lista de filas descartadas por el sistema, la revisión por grupos y los cambios de la medición. No cambia nada de lo aprobado antes: la extracción, la completitud y las filas técnicas siguen proponiendo como hasta ahora. ADR propuesto: `docs/adr/0021-filtro-de-precision-de-la-matriz.md`.

### Lo que dicen los números

Medidas de T-093 y T-094; la muestra del caso-00 es de 30 de 95 sobrantes y la clasificó quien verificó (`corpus/casos/caso-00/corridas/analisis-sobrantes.md`, local).

| Caso (proceso completo, el de "alta") | Esperados | Sobrantes | Sobrantes sobre la matriz propuesta |
|---|---|---|---|
| caso-00 | 52 | 95 | 65 % (95 de 146 filas; el 100 % de encontrados no se alcanza todavía: 51 de 52) |
| caso-01 | 85 | 327 | 79 % |
| caso-02 | 108 | 133 | 55 % |

| Muestra de 30 sobrantes del caso-00 | Filas | Qué haría el filtro |
|---|---|---|
| No son requisitos de la oferta (ejecución del contrato, obligaciones del organismo, texto de normas o de formularios, datos) | 18 | Descartar |
| Repetidas | 2 | Unificar |
| Plausibles: condiciones que la oferta puede condicionar y la lista esperada no tiene | 9 | **Mantener** (ante la duda) |
| División legítima de una oración | 1 | Mantener |

**El tope probablemente no se alcanza con el filtro solo.** Si el filtro quita todo lo que no es requisito y lo repetido (unos dos tercios de los sobrantes en la muestra, con un intervalo amplio por ser 30 filas), en el caso-00 quedarían unos 30 sobrantes sobre unas 80 filas: alrededor del 38 %, no el 20 %. Quedan sobre todo las condiciones plausibles, que son compromisos que la oferta puede condicionar ("la mera presentación implica…", la confidencialidad, el código de ética). El filtro no las descarta para ajustarse a la lista: llevarse una fila real es un faltante que bloquea la aceptación. Si la medición del caso-00 lo confirma, la salida es una decisión del responsable (T-106), no un ajuste del filtro. Ver "Riesgos de la enmienda" y "Decisiones que necesita el responsable".

### Orden de las pasadas

**Un solo proceso (spec enmendada el 2026-10-04, REQ-030).** El responsable eliminó el nivel "media" y, con él, la elección de nivel: la matriz se propone siempre con un único proceso, el más completo, que es el que hoy se llama "alta" (extracción, completitud, filas técnicas, circulares, consecuencias). Se le suman pasadas cuando la medición muestra que mejoran la matriz. El tiempo se mide y se informa por pliego y por página, sin máximo y sin bloquear la aceptación. Donde este plan y las tareas ya terminadas hablan de niveles (media, alta, exigente; `MATRIX_LEVELS`, `MATRIX_LEVELS_OFFERED`, T-078 y T-085), rige lo de esta sección; la tarea T-100 saca la elección de nivel del producto. El proceso queda registrado con la matriz con un nombre fijo (`completo`) y la versión de cada instrucción (`matrix_run.process`, `prompt_versions`).

Se suman dos pasadas al proceso, después de las que buscan requisitos y antes de lo que depende de ellos:

| Pasada | Qué hace |
|---|---|
| Disposición por regla, extracción, completitud | Sin cambios. Proponen de más, como pide REQ-024 |
| **Unificación** (`pass_name` `unificacion`) | Regla, sin modelo: junta las filas formales y económicas que repiten la misma condición |
| **Filtro de precisión** (`filtro` y `filtro_2`) | Dos preguntas distintas por fila al modelo; descarta solo si coinciden |
| Reglas de tablas (T-093), filas técnicas, circulares | Sin cambios. Las circulares se aplican después del filtro y a lo que quedó |
| Consecuencias | Solo para las filas que quedaron en la matriz: menos pedidos |

La segunda extracción (la que sumaba "exigente") no forma parte del proceso: T-100 deja de llamarla. Si la medición demuestra que una pasada así mejora la matriz, se vuelve a sumar con una tarea nueva.

### Unificación de repetidas (`proposal/dedup.py`)

- **Qué junta.** Dos filas formales o económicas, de cualquier tramo, cuyo fragmento normalizado (sin tildes, en minúsculas, espacios y signos de puntuación colapsados) es igual, o uno contiene al otro, o cuya similitud de palabras (conjunto de palabras sin las de uso común) es de al menos `DEDUP_MIN_SIMILARITY` (valor inicial 0,9). No usa el modelo: la coincidencia del texto es objetiva (en la muestra, 2 de 30 sobrantes eran el mismo texto en otro tramo o en el otro anexo).
- **Cómo queda.** Una fila: la primera en el orden del pliego, con su cita como cita principal. Las citas de las otras filas quedan como citas adicionales de esa fila (`scope` `repetida`), cada una con su texto literal y su ubicación. La matriz muestra una fila con "también en: …" y las citas de cada una.
- **No junta** filas técnicas, filas de circulares ni filas con `cita_amplia`; tampoco dos filas de un mismo tramo con citas distintas que no se superponen (son condiciones distintas, aunque se parezcan).
- Se registra en `tenders_run_step` (`unificacion`, con la versión de la regla, el umbral y los pares unidos). Si dos filas distintas que debían quedar separadas se unieron, la Comisión lo ve en la fila y puede agregar la otra (REQ-026).

### Filtro de precisión (`proposal/filter.py`)

**Qué filas.** Las formales y económicas que propuso el modelo (después de la unificación). No pasan por el filtro, y quedan siempre en la matriz: las filas técnicas (las arma una regla), las que agrega una circular, las de tramos `tabla` (ya quedan pendientes de revisión) y las de cita amplia. Tampoco las filas de un tramo cuya sección el pliego titula como de clase formal o económica (`section_class`): por la sección, son requisitos.

**Qué recibe el modelo.** Las instrucciones `prompts/matriz-filtro-v1.md`, con la definición de requisito de la spec y ejemplos sintéticos de otro objeto y otras cifras que el caso-00 (incluidos los que se mantienen aunque cumpla el organismo, como la forma y el plazo de pago, y los compromisos que la oferta asume al presentarse). Después, un lote de hasta `FILTER_BATCH_ROWS` filas (15), cada una con un alias (`F1`, `F2`, …), la ruta del tramo, el texto del tramo con el fragmento marcado y el título de su sección.

**Dos preguntas distintas, cada una en su pedido** (`filtro` y `filtro_2`, temperatura 0, salida estructurada con una propiedad obligatoria por alias):

1. **Clasificación.** Por fila: `mantener` o `descartar`; si descarta, un motivo de una lista cerrada (la del ADR-0019: título, definición o dato del procedimiento, norma aplicable, obligación del organismo que la oferta no puede contradecir ni condicionar, obligación de la ejecución del contrato, formulario a completar; más `consecuencia_o_sancion` y `derecho_posterior`) y un `indicio`: un fragmento literal del tramo que sostiene el motivo.
2. **Pregunta inversa.** Por fila: si la oferta puede presentar, ofrecer, comprometer, contradecir o condicionar lo que dice el fragmento: `si`, `no` o `duda`. No ve la respuesta de la primera.

**Cuándo se descarta.** Solo si se cumplen las cuatro condiciones: (1) la clasificación dice `descartar`; (2) el motivo está en la lista; (3) el indicio se encuentra, palabra por palabra, en el tramo (`quotes.py`); (4) la pregunta inversa dice `no`. Cualquier otra cosa mantiene la fila: salida inválida o cortada, alias faltante, motivo fuera de la lista, indicio que no está, `duda`, pedidos que fallan. Un lote que se corta por el máximo de salida se parte en dos, como en la extracción. Una fila nunca se pierde por una falla técnica.

**Cuidado con los requisitos reales.**

- Ante la duda, se mantiene. La asimetría es a propósito: un sobrante cuesta una fila a la Comisión; un faltante bloquea la aceptación.
- Dos preguntas distintas, indicio verificable y coincidencia obligatoria, para que un error del modelo no alcance para perder una fila.
- Lo descartado no desaparece: la lista de descartadas muestra cada fila con su cita, motivo e indicio, y se puede devolver (ver abajo).
- La medición cuenta como **faltante, con causa propia**, a todo esperado que el filtro descartó; ese faltante bloquea la aceptación.
- La disposición del tramo cuyas filas se descartaron todas queda `descartado` con origen `filtro` y el motivo, visible en la cobertura. Un tramo con alguna fila mantenida sigue `requisitos`.

### Modelo de datos y migración

Una migración nueva en `evaluon/tenders/migrations/`, a cargo de una sola tarea (T-099), que cambia varias cosas de la 003 y agrega una tabla:

- **`tenders_discarded_row`** (nueva, solo inserción, trigger como `tenders_run_step`): una fila descartada por el sistema.

| Campo | Contenido |
|---|---|
| `id`, `run`, `version`, `order` | Identificación; la propuesta, la versión que creó y el orden del pliego |
| `segment`, `char_start`, `char_end`, `text` | La cita literal de la fila descartada y su ubicación, igual al recorte del texto canónico (P3) |
| `extra_quotes` | Citas adicionales, si la fila había unificado repetidas (lista de tramo, posiciones y texto) |
| `category`, `items` | Clase (`formal` o `economico`) y renglones que había propuesto el modelo |
| `reason` | Motivo de la lista cerrada |
| `evidence_segment`, `evidence_start`, `evidence_end`, `evidence_text` | El indicio, literal |
| `vote_a`, `vote_b`, `step_a`, `step_b` | Las dos respuestas validadas y los pedidos de `tenders_run_step` que las produjeron |
| `source_pass`, `passes` | Pasada que propuso la fila (`extraccion`, `extraccion_2`, `completitud`) y pasadas que la encontraron |
| `created_at` | Momento |

- **`tenders_requirement_quote.scope`** suma `repetida` (una cita adicional de la misma condición). La restricción de T-067 pasa a ser: un formal o económico tiene exactamente una cita con `scope` vacío y puede tener las `repetida` que haga falta; un técnico no cambia.
- **`tenders_requirement.origin`** suma `devuelto` (devuelta desde la lista de descartadas) y la tabla suma `restored_from` (la descartada de la que sale; única por versión). Una fila devuelta nace `propuesto`.
- **`tenders_requirement_change.action`** suma `devolver`.
- **`tenders_matrix_run.process`** (texto, `completo`) y `tenders_matrix_version.process` para registrar el proceso único (REQ-030 enmendado). `level` queda como dato histórico de las propuestas ya hechas: acepta vacío y las propuestas nuevas lo dejan vacío.
- **`tenders_run_step.pass_name`** suma `unificacion`, `filtro` y `filtro_2`; **`tenders_disposition.source`** suma `filtro`.
- **Inmutabilidad.** `tenders_discarded_row` es de solo inserción. "Devolver" no la modifica: crea un requisito con `restored_from`. El estado de una descartada (descartada o devuelta) se deriva de la existencia de ese requisito en la versión que se mira. Las versiones que se abren sobre una validada muestran las descartadas de la propuesta original (por la cadena `based_on`) y copian, como el resto, los requisitos devueltos con su `restored_from`.
- **Parámetros** (`settings.py`, copiados en cada propuesta): `FILTER_ENABLED` (verdadero), `FILTER_BATCH_ROWS` (15), `FILTER_MOTIVES` (la lista cerrada), `DEDUP_MIN_SIMILARITY` (0,9), `MATRIX_SAMPLE_DISCARDED` (uno de cada tres, mínimo 20), `MATRIX_SOBRANTES_LIMIT` (0,20) y la versión de las instrucciones del filtro en `MATRIX_PROMPT_VERSIONS`. `FILTER_ENABLED` en falso devuelve la propuesta de T-093 sin la pasada (ADR-0021, "Para revertir").
- **`tenders_matrix_run.counts`** suma: filas unificadas, filas descartadas por motivo y por pasada, filas mantenidas por duda (la clasificación pidió descartar y no se cumplió alguna de las otras tres condiciones).

### La lista de descartadas y cómo se devuelve (REQ-033)

- **Servicio** `services/discarded.py`: listar las descartadas de una versión (con su estado derivado) y `restore(user, version, [descartada])`. Roles: operador o evaluador, porque devolver equivale a agregar un requisito (REQ-026). En una versión validada se rechaza; la lista se puede ver.
- **Qué hace devolver.** Crea el requisito con la clase, los renglones y las citas de la descartada (la principal y las adicionales), `origin` `devuelto`, `restored_from`, `proposed` con copia de lo propuesto, estado `propuesto`; lo confirma después un evaluador, como cualquier otro. Deja una fila de `tenders_requirement_change` con acción `devolver`, quién, cuándo, y el motivo y el indicio del descarte, y el hecho `requirement_change`. Una devuelta que se quita después queda `quitado` con su historia.
- **Sin sugerencias de consecuencia.** Una fila devuelta no pasa por la pasada de consecuencias: llega sin sugerencias y el evaluador elige el tipo y escribe su motivo, como con cualquier fila sin sugerencia (REQ-029). Se informa en pantalla.
- **Pantalla.** Página "Descartadas por el sistema" de la versión: cada fila con su cita literal, el documento, la página y la cláusula, el enlace al original, la clase propuesta, el motivo y el indicio; casillas y botón "Devolver a la matriz" (una o varias); las ya devueltas figuran como tales. En la página de la matriz, una línea "El sistema descartó N filas y unificó M repetidas: ver" con el enlace, y en la cobertura, el origen `filtro`.
- **Impresión y PDF (REQ-032).** La plantilla de impresión suma una línea con la cantidad de filas descartadas por el sistema y su reparto por motivo, para que quien lee el papel sepa que existe esa lista; el detalle se ve en pantalla.

### Revisión por grupos (REQ-034)

- **Qué es un grupo.** Las filas `propuesto` de la versión cuyo tramo cuelga de una misma cláusula o es un mismo tramo. El grupo se nombra por una clave de tramo: una cláusula (`sec-i/11`, `sec-i/11.3`) o un tramo (`sec-i/11.3/v-1`). Una fila es del grupo si la clave de su tramo es igual a la del grupo o la continúa con un separador de nivel (`/`, `.` o `#`), de modo que `sec-i/1` no alcanza a `sec-i/11`.
- **Servicios** (`services/review.py`): `confirm_group(user, version, clave)` (solo evaluador) y `remove_group(user, version, clave)` (operador o evaluador). Actúan solo sobre las filas `propuesto` del grupo, dentro de una transacción, y para cada una llaman a la misma función que la revisión fila por fila. Cada fila deja su propia fila de `tenders_requirement_change` y su hecho `requirement_change`, con quién y cuándo, y una marca `via_grupo` con la clave. Una fila ya confirmada, corregida o quitada no se toca. Un grupo vacío no hace nada y lo dice.
- **Pantalla.** En la matriz, encabezados por cláusula de primer nivel y, dentro de cada una, por tramo con dos o más filas propuestas, con los botones "Confirmar las N propuestas" y "Quitar las N propuestas". Primero se muestra una página de confirmación con las N filas que se van a tocar y su texto literal; solo con "Aceptar" se aplica. Las casillas de confirmar varias (T-079) siguen.
- Los grupos no cambian lo que cuenta como decisión: confirmar sigue siendo del evaluador y queda registrado fila por fila. La validación sigue confirmando lo que haya quedado `propuesto`.

### Cambios en la medición (`medir_matriz`)

Se aplican a `evaluation.py` y al comando; la lista esperada y la regla de emparejamiento por cita no cambian.

1. **Matriz propuesta = lo que ve la Comisión**: las filas formales, económicas y técnicas de la versión, sin las descartadas por el sistema.
2. **Sobrantes** = filas de esa matriz sin pareja. **Proporción de sobrantes** = sobrantes ÷ filas de la matriz propuesta (formales, económicas y técnicas), con su intervalo de Wilson al 95 %. Se informa también la proporción solo sobre formales y económicos.
3. **Tope.** Se evalúa sobre el proceso único: cumple si la proporción es de hasta 20 % (`MATRIX_SOBRANTES_LIMIT`) y los encontrados son el 100 % (contando "a revisión obligatoria", T-095). El intervalo se informa y no decide.
4. **Esperados descartados.** Un esperado sin pareja entre las filas de la matriz que sí tiene pareja (misma regla de cobertura de la mitad del ancla) entre las filas descartadas pasa a faltante con causa propia `descartado_por_el_sistema`, con el motivo y la clave de la descartada. Bloquea la aceptación y se informa con su motivo.
5. **Unificadas.** Un esperado cuyo ancla está en una cita `repetida` de una fila ya emparejada cuenta como encontrado "unificado", informado aparte. Así la unificación no crea faltantes. `--verificar-esperada` avisa además si dos esperados tienen un ancla con el mismo texto normalizado (se unificarían).
6. **Pareja con varias citas.** Una fila empareja con un esperado si cualquiera de sus citas (la principal o una adicional) cubre al menos la mitad del ancla.
7. **Informe de descartadas.** Cantidad, reparto por motivo, por tramo y por pasada; sobrantes que habría sin el filtro (sobrantes más descartadas sin pareja, para ver cuánto quita); y una **muestra** de `MATRIX_SAMPLE_DISCARDED` filas, en orden de la corrida, con su cita, motivo e indicio, en `resumen.md` (con texto, fuera del repositorio) y en una plantilla local `muestra-descartadas.md` con una columna para que quien verifica diga si el descarte era correcto. `resumen-publico.md` solo lleva cuentas, claves de tramo y motivos, sin texto del pliego.
8. **Corridas anteriores.** `--regenerar-resumen` sigue funcionando con propuestas sin descartadas (sin filtro, todas las medidas anteriores).
9. **Tiempos.** `timing_summary` suma las pasadas `unificacion` y `filtro`.

| Medida | Meta |
|---|---|
| Requisitos encontrados | 100 % (sin cambios); un esperado descartado por el sistema es un faltante |
| Sobrantes | Hasta 20 % de la matriz propuesta sin descartadas |
| Filas descartadas | Se informan, por motivo, con una muestra revisada de sus motivos |
| Esperados descartados por el sistema | 0 |

### Cómo se evita el sobreajuste

El caso-00 es de ajuste (`uso: ajuste`, decisión del 2026-10-04); los casos 01 y 02 son de aceptación y no se miran antes.

1. **Qué se ajusta y cuánto.** Solo las instrucciones del filtro (`matriz-filtro-v1.md`) y los parámetros del filtro y de la unificación, con el caso-00, en a lo sumo **tres rondas** (v1, v2, v3). Cada ronda se mide en el caso-00 y se anota en `verificacion/T-106.md`: qué cambió, con una frase general que no nombra cláusulas del pliego, y qué movió (esperados descartados, sobrantes, descartadas).
2. **Qué no se toca.** La lista esperada, el emparejamiento, las instrucciones de extracción y de completitud, los motivos de la lista cerrada ni los criterios de requisito de la spec. No se descarta ninguna fila para que coincida con la lista: una fila plausible que la lista no tiene sigue siendo un sobrante legítimo; el camino para esos casos es decidir sobre la lista o el tope con el responsable (T-107).
3. **Independencia de lo que se escribe.** Las instrucciones nuevas usan ejemplos de otro objeto y otras cifras; una prueba busca las anclas de la lista del caso-00 (frases de 3 a 5 palabras) y falla si aparecen en las instrucciones, los tests o los ejemplos, como se hizo en T-093.
4. **La parte a ciegas.** Los casos 01 y 02 no se corren con el filtro hasta T-108, con las instrucciones fijas. Lo que se vio de ellos en T-094 (cantidades) no se usa para ajustar. T-108 no ajusta nada: informa, y un faltante o un tope no cumplido se informan con su causa.
5. **Sin ajustar en la aceptación.** Si en T-108 el filtro se lleva un esperado de 01 o 02 o no cumple el tope, no se corrige ahí: se informa al responsable y, si decide ajustar, el caso afectado pasa a ser de ajuste, como ya prevé este plan.

### Tiempos de la enmienda

Estimación, por lo medido en T-093 (caso-00, 20 páginas): alta 412 s, media 333 s; el filtro lee unos 147 tramos de contexto y escribe unos 30 tokens por fila en la clasificación y 5 en la pregunta inversa. Sumaría en el caso-00 alrededor de 1 a 2 minutos; las consecuencias, que se piden por fila (126 s en alta), correrían sobre menos filas y recuperan una parte. Para 50 páginas (×2,5), alta pasaría de unos 17 minutos a unos 20: la spec ya no fija un máximo, y el tiempo se mide e informa por pliego y por página (T-106 y T-108) sin bloquear. El responsable indicó que en la matriz manda la calidad y el tiempo es secundario.

### Riesgos de la enmienda

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El filtro descarta un requisito real | Faltante: bloquea la aceptación | Ante la duda se mantiene; dos preguntas distintas, indicio literal y coincidencia obligatoria; la lista de descartadas permite devolverla; la medición lo cuenta como faltante con causa propia |
| **El tope del 20 % no se alcanza aunque el filtro funcione** (quedan condiciones plausibles que la lista no tiene) | La aceptación no se cumple por la lista, no por el sistema | T-106 lo mide en el caso-00 y T-107 lleva los números al responsable antes de la aceptación; no se descartan filas plausibles para llegar al tope |
| Sobreajuste del filtro al caso-00 | Buen resultado en el caso-00 y malo en 01 y 02 | Ver "Cómo se evita el sobreajuste": tres rondas como máximo, ajustes generales, ejemplos independientes, 01 y 02 a ciegas |
| La unificación junta dos condiciones distintas | Una condición real queda dentro de otra fila | Umbral alto, citas adicionales visibles en la fila, el evaluador puede agregar la otra; mide como "unificado" |
| Una descartada devuelta no tiene sugerencias de consecuencia | Más trabajo del evaluador en esas filas | Son pocas (las que la Comisión cree que el sistema descartó mal); el evaluador elige el tipo, como con cualquier fila sin sugerencia |
| Quitar el nivel "media" deja referencias sueltas (pantalla, `MATRIX_LEVELS`, `--niveles`, tests, corridas guardadas) | Un pedido o una medición que todavía nombra un nivel | T-100 lo quita en una sola tarea, con búsqueda de todas las referencias; las propuestas ya guardadas conservan su nivel como dato histórico |
| La medición provisoria con un solo pliego de ajuste | El filtro puede no generalizar | T-108 mide con 01 y 02 sin ajustar; cada pliego nuevo se mide primero sin ajustes |

### Cobertura de REQ-033 y REQ-034

| Requisito | Cómo se resuelve | Cómo se verifica |
|---|---|---|
| REQ-033 | Unificación por regla (`dedup.py`); pasada de filtro con dos preguntas, motivo e indicio (`filter.py`); `tenders_discarded_row` y la lista de descartadas; devolver con registro; tope y causa propia en la medición | Tests con el doble: una fila de ejecución del contrato se descarta con cita y motivo y figura en la lista; una duda, un indicio ausente o una respuesta distinta mantienen la fila; dos filas con la misma condición dan una con las dos citas; devolver crea el requisito y deja el registro. Medición del caso-00 (ajuste) y de 01 y 02 (aceptación): sobrantes hasta 20 %, esperados descartados 0 |
| REQ-030 (enmendado) | Sin elección de nivel; proceso único `completo` registrado con la matriz junto con la versión de instrucciones (T-099 y T-100) | Tests: el pedido no ofrece niveles; la propuesta registra proceso y versiones; la medición no tiene `--niveles` |
| REQ-034 | `confirm_group` y `remove_group`; pantalla de grupos con confirmación previa | Tests: cinco filas propuestas de una cláusula se confirman como grupo y cada una tiene su fila de historial con quién y cuándo; `sec-i/1` no alcanza a `sec-i/11`; un operador no puede confirmar el grupo y queda `rejected` |

### Decisiones que necesita el responsable

1. **Aprobar esta enmienda del plan y el ADR-0021** (compuerta).
2. **El tope y la lista, después de T-106.** Si el caso-00 confirma que quedan unas decenas de sobrantes plausibles y la proporción no baja del 20 %, hay que elegir entre: (a) revisar con la Comisión si esas condiciones son requisitos y ampliar las listas esperadas de los tres casos; (b) subir el tope; (c) otra forma de contar las filas que son un solo requisito. El sistema no debe descartar esas filas para llegar al tope.
3. Nada más por el tiempo: la spec ya no lo limita.

### Puntos de interpretación, para el Coordinador

1. **Denominador del tope.** El plan toma como "matriz propuesta" todas las filas (formales, económicas y técnicas, sin descartadas); informa también la proporción solo sobre formales y económicos. Las técnicas suman unas 6 filas por pliego y favorecen levemente el tope.
2. **El tope se evalúa con el valor observado**, no con el límite superior del intervalo; el intervalo se informa.
3. **Grupo de revisión.** "Misma cláusula" se resuelve por la clave del tramo (cláusula de cualquier nivel o tramo). La spec no dice si el grupo es solo de primer nivel.
4. **Quitar por grupo** puede hacerlo un operador, como quitar una fila (REQ-026); confirmar, solo un evaluador.
5. **Devolver** lo hace un operador o un evaluador, como agregar; la fila nace `propuesto`.
6. **Las filas devueltas no tienen sugerencias de consecuencia.**
7. **T-094** (medición de aceptación con 01 y 02) se hizo antes del filtro y con niveles: la matriz cambia con T-102 y el producto con T-100, por lo que T-108 repite la aceptación completa, solo con el proceso único.
8. **REQ-030 y los niveles.** El texto de REQ-030 de la spec enmendada ya no pide nivel; el resto del plan aprobado y las tareas T-073, T-078, T-084 y T-085 los mencionan como historia. Este plan no los reescribe: T-100 deja el producto y la medición sin niveles.

## Qué no se hace en esta feature

- La revisión del pliego borrador contra la normativa (002), las ofertas (008) y la evaluación (004). Redactar o modificar el pliego.
- **El asistente técnico (feature 010)**: comparar la parte técnica de cada oferta con las especificaciones del pliego, renglón por renglón. En la 003, las filas técnicas solo citan las especificaciones de cada renglón; el resultado técnico es el del informe del área requirente.
- Decidir si una oferta cumple, o si un requisito es subsanable: el sistema solo sugiere consecuencias.
- Texto redactado por el modelo en los requisitos: el requisito es el fragmento literal o los tramos citados.
- Búsqueda por significado o por palabras sobre el pliego: no se calculan vectores de los tramos.
- Reconocer la estructura de las tablas (por ejemplo, con Docling): las tablas se leen como texto y quedan pendientes de revisión.
- Volver a proponer solo lo que cambió una circular que llega después de validar: se pide una propuesta nueva, que crea una versión nueva.
- Corregir los datos de un procedimiento registrado o quitar un documento cargado: ningún requisito lo pide.
- Preguntas a la Comisión (ADR-0009): son de la 002 y la 004.
- Actualización automática de la página o avisos fuera de la aplicación.
- Otros formatos de la matriz (planilla) y las salidas de la evaluación: feature 006. Esta feature solo da la vista de impresión y el PDF que pide REQ-032.

## Cobertura de requisitos

| Requisito | Cómo se resuelve | Cómo se verifica |
|---|---|---|
| REQ-022 | `tenders_procedure`; `services/procedures.py`; `applicable_regimes(fecha)` de la 001; línea de régimen en la pantalla; hecho `procedure` | Test con normas de prueba: fecha 2022-12-15 muestra la Disposición 297/03; 2023-01-02, la 247/2022; fecha futura rechazada; el registro guarda régimen y versión de la normativa |
| REQ-023 | `tenders_document` y `tenders_document_file`; carga por pantalla; vista del original | Test: un pliego en tres documentos; la huella de lo que entrega la vista es igual a la de cada archivo cargado; el mismo archivo dos veces se rechaza |
| REQ-024 | Tramos con cobertura y clase por sección; extracción con disposición obligatoria para formales y económicos; filas técnicas por renglón; completitud y segunda extracción según nivel | Tests con dobles: todo tramo queda con requisitos, fila técnica, descarte o pendiente; un tramo sin disposición se reintenta y queda pendiente; una fila técnica por renglón con sus tramos; la clase de la sección manda. Medición: 100 % de encontrados sobre el caso-00, provisoria |
| REQ-025 | Fragmento literal ubicado en el tramo; tramos enteros en las filas técnicas; posiciones en el texto canónico; documento, página y cláusula en la pantalla | Tests: cita no encontrada se reintenta y queda como cita amplia; el texto mostrado es igual al recorte en cada cita; página y cláusula correctas. Medición: 100 % de cita literal |
| REQ-026 | `services/review.py`; `tenders_requirement_change`; `proposed`; roles | Tests: una corrección queda con usuario, momento, antes y después, y lo propuesto se consulta; quitar y agregar quedan registrados; un operador no puede confirmar |
| REQ-027 | `services/validation.py`; versiones; trigger de inmutabilidad | Tests: cambiar una versión validada se rechaza en la función y en la base; abrir una versión nueva la copia y la anterior sigue igual |
| REQ-028 | Páginas ilegibles o dudosas, tablas, tramos no ubicados, tramos sin disposición y renglones sin especificaciones como pendientes; marcadores en media | Test: un pliego sintético con una página de ruido; esa página figura como pendiente de revisión en la matriz propuesta y ninguna otra |
| REQ-029 | Pasada de consecuencias con fundamentos del pliego y de la norma a la fecha; lista cerrada de siete tipos; elección con motivo por un evaluador | Tests con dobles: una cláusula que sanciona con desestimación produce la sugerencia con su cita; sin fundamento, "no determinada"; el sistema no sugiere aprobación condicionada ni aprobar de todas maneras; la elección queda con quién, cuándo y motivo |
| REQ-030 | Nivel en el pedido, por omisión alta; guardado en la propuesta y en la versión; niveles ofrecidos por configuración | Tests: sin elegir, alta; con media o exigente, el elegido; cada nivel corre sus pasadas. Medición por nivel en T-084 |
| REQ-031 | Tipos de documento con fecha; pasada de circulares; `tenders_requirement_source` por cita; pantalla con los dos textos | Test con un pliego sintético: "16 GB de RAM" y una circular "32 GB": el requisito exige 32 GB, muestra los dos textos y cita la circular; una respuesta que precisa un requisito figura junto a él con su cita |
| REQ-032 | Franja en la página de la matriz; plantilla de impresión; `export.py` con WeasyPrint (ADR-0020); leyenda en las cajas de margen de cada página; datos de validación; hecho `matrix_export` | Tests: un PDF de un borrador de varias páginas, leído con pdfplumber, tiene "BORRADOR INCOMPLETO" en cada página; el de una versión validada no la tiene y muestra versión, fecha y evaluador; la página y la vista de impresión de un borrador muestran la leyenda; el PDF no pide ningún recurso externo. A mano: la impresión del navegador repite la leyenda en cada hoja |

Requisitos no funcionales: la medición, en "Medición"; tiempo y nivel, en "Tiempos y GPU" y T-084; sin conexión, con la red interna, el `URLFetcher` cerrado y una prueba con la red cortada en T-075.

## Verificación contra la constitución

| Principio | Cumple | Nota |
|---|---|---|
| P1 Spec | sí | Cada pieza responde a un REQ. Lo que se suma sin REQ propio está justificado: rechazar el mismo archivo dos veces (evita tramos duplicados), la tabla de pedidos (la exige el tiempo de la spec), el hecho `matrix_export` (P6) |
| P2 Trazabilidad | sí | Tabla de cobertura; cada tarea nombra sus REQ |
| P3 Recomienda, la Comisión decide | sí | Requisitos como texto literal; consecuencias con fundamento o "no determinada"; confirmar, elegir con motivo y validar, solo un evaluador; el cumple o no cumple, en la 004 |
| P4 Datos | sí | El camino del pliego no usa servicios externos: lectura en CPU, modelos locales sin red, PDF generado en `app` sin recursos externos. El caso y su lista esperada quedan fuera del repositorio; al repositorio solo llegan resúmenes sin texto del pliego |
| P5 Local y reproducible | sí | Dos servicios nuevos en `docker-compose.yml`, misma imagen y modelo fijados; WeasyPrint y sus bibliotecas con versión fija |
| P6 Auditoría | sí | Ver "Registro de auditoría" y `tenders_run_step` |
| P7 Evals | sí | `medir_matriz` con salida estructurada; todo cambio de instrucciones o modelo de la matriz se vuelve a medir |
| P8 Normativa versionada | sí | Cada propuesta guarda régimen y versión de la normativa |
| P9 Compliance | sí | No se infiere nada de sistemas externos; los requisitos que se verifican afuera (registro de proveedores, deuda) entran a la matriz como requisitos, y su verificación queda para la 005 |
| P10 Simplicidad | sí | Sin cola de terceros, sin vectores del pliego, sin estructura de tablas, sin texto redactado; lo técnico por regla; el PDF en el pedido, sin cola. Los niveles alta y exigente se construyen porque la spec los pide; se ofrecen solo si mejoran |
| P11 Compuertas | sí | Plan aprobado; ADR-0018, 0019 y 0020 aceptados |

## Decisiones del responsable (2026-10-03)

Todas resueltas.

| N.º | Tema | Decisión |
|---|---|---|
| 1 | Pedidos largos y segundo motor | Aprobado el ADR-0018 con dos motores |
| 2 | Matriz por tramos | Aprobado el ADR-0019 |
| 3 | Rol de la Comisión | Campo aparte del rol de normativa |
| 4 | Qué es requisito | Con cambio: también toda condición del pliego que la oferta pueda contradecir o condicionar, aunque la cumpla el organismo. La forma, moneda y plazo de pago (25.1) entran como económicos. Las multas (24.3) siguen afuera |
| 5 | Clase | Con cambio: sigue la sección del pliego cuando el pliego ordena sus requisitos por secciones; si no, por naturaleza (garantía, precio, moneda y pago, económicos) |
| 6 | Granularidad y medición | Con cambio: técnicos en una fila por renglón, con la cita a sus especificaciones; formales y económicos, una fila por condición. Medición: técnico por renglón; en formal y económico, una fila que junta dos condiciones cuenta una faltante; la clase equivocada se informa y no bloquea |
| 7 | Uso del caso-00 | Primera corrida sin ajustes como medida provisoria; después, ajuste |
| 8 | Tipos de consecuencia | Con cambio: la lista de la spec, que suma consultar al oferente, aprobación condicionada y aprobar de todas maneras. El sistema solo sugiere; el evaluador decide |
| 9 | Condiciones para validar | Aprobadas como se propusieron |
| 10 | Tiempo de 50 páginas | Extrapolado y provisorio hasta tener un pliego de ese tamaño |
| — | Feature 010, asistente técnico | Fuera de la 003 |

Queda por decidir, por REQ-032, agregado después: el ADR-0020 (PDF con WeasyPrint). Lo necesita solo T-086.

## Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Un solo pliego para ajustar y medir | El 100 % medido no garantiza el próximo pliego | Medida provisoria; primera corrida sin ajustes; cada pliego nuevo se mide primero sin ajustar |
| Pocas filas para comparar niveles | Un nivel se ofrece o no por una fila de diferencia | Se informa como provisorio; se vuelve a medir con cada pliego nuevo |
| El modelo descarta un tramo que tiene requisitos | Faltante | Descarte con motivo visible; marcadores de obligación (pendiente en media, completitud en alta); la medición informa la causa |
| El modelo junta varias condiciones formales o económicas en una fila | Faltante por agrupamiento | Instrucciones con ejemplos de "una fila por condición"; completitud divide; se mide |
| Una condición técnica fuera de una sección técnica (por ejemplo, la entrega en la Sección I) no se marca como técnica | Falta una cita general en las filas de los renglones | Se mide como "tramos técnicos citados por renglón"; el evaluador la suma al corregir la fila |
| Un pliego que no titula sus secciones por clase | Lo técnico pasa por el modelo | Las instrucciones explican cuándo marcar un tramo como técnico; los tramos que cuelgan de un renglón entran igual en su fila |
| El modelo copia mal la cita | Requisito con cita amplia | Reintento; cita amplia marcada para revisar; nunca una cita que no esté en el pliego |
| Reglas de tramos que no reconocen otro pliego | Tramos grandes, no ubicados o renglones no reconocidos | Siguen pasando por el modelo o quedan pendientes; nunca afuera; se ajustan las reglas con una tarea y una relectura |
| Tablas mal leídas | Condiciones de una tabla mezcladas | Toda tabla queda pendiente de revisión con enlace a la página |
| Una consulta de normativa tarda más de 30 s mientras corre una matriz | No cumple la 001 en ese momento | Segundo motor (ADR-0018); se mide en T-084; si no alcanza, se informa al responsable |
| Memoria de video con cuatro modelos | Un servicio no carga | Se mide en T-071; el margen estimado es de unos 6 GB |
| Un pedido se interrumpe | Matriz a medias | El pedido queda `failed`; nunca una versión parcial; al arrancar, `procesar_pedidos` cierra los interrumpidos |
| La lista esperada tiene un error | Faltante o sobrante falso | Visto bueno del responsable con tabla de ejemplos; anclas y tramos verificados antes de medir; confirmación de la Comisión en la 009 |
| Datos personales en el repositorio | Incumple P4 y la decisión del responsable | Lista y corridas en `corpus/casos/`; al repositorio solo `resumen-publico.md`, sin texto del pliego |
| Un borrador impreso circula como si fuera la matriz final | Se evalúa con una lista sin validar | Leyenda en cada página del PDF por las cajas de margen; test página por página; la impresión segura es la del PDF |
| WeasyPrint pide un recurso por red | Fuga de datos o espera | `URLFetcher` que rechaza todo salvo la hoja de estilos local; red sin salida; test |
| Un documento cargado por error | Requisitos de otro pliego | Fuera de alcance quitarlo; el evaluador quita los requisitos o descarta el borrador; si hace falta, se registra de nuevo el procedimiento |
| Circulares sin un caso real | REQ-031 medido solo con un ejemplo sintético | Tests con el ejemplo de la spec; se mide cuando la Comisión aporte un pliego con circulares |

## Puntos de interpretación, para el Coordinador

No se modificó la spec. Estos puntos los resuelve el plan con una lectura de la spec que conviene confirmar:

1. **Condiciones técnicas generales.** Las especificaciones comunes a todos los renglones (Sección II del caso-00) y las condiciones técnicas por naturaleza fuera de una sección técnica (la entrega en 15 días, 9.2.1) se citan en la fila de cada renglón como citas `general`, no en filas propias, para respetar "una fila por renglón".
2. **Aprobación condicionada y aprobar de todas maneras** se ofrecen en la matriz como tipos que solo elige un evaluador. Es probable que se usen sobre todo al evaluar cada oferta (004); la 003 no los restringe.
3. **Motivo obligatorio** en toda elección de consecuencia, incluida la de una sugerencia del sistema, por "con su nombre y su motivo registrados".
4. **"No determinada" no se elige**: es el estado de un requisito sin sugerencia; para validar, el evaluador elige uno de los otros seis tipos.
5. **Tramos técnicos citados por renglón**: se miden y se informan, pero no bloquean; lo que bloquea es que falte la fila del renglón.
6. ADR-0014, punto 7, pedía armar el conjunto con la Comisión antes del plan; la spec aprobada lo cambió por la lista del Coordinador con visto bueno del responsable y confirmación posterior de la Comisión. El plan sigue la spec.
7. REQ-031 no se puede medir con el caso-00, que no tiene circulares.

## Orden de construcción

Detalle en `specs/003-pliego-matriz/tasks.md`.

1. **Base** (T-067 a T-071): tablas, roles, procedimiento, tramos, pedidos en segundo plano y segundo motor.
2. **Hilo mínimo** (T-072 a T-075): cargar el pliego del caso-00, proponer la matriz en nivel media y verla en la pantalla con la leyenda de borrador, con los servicios reales. Requiere la lista esperada aprobada (T-076), para que nadie la escriba después de ver la salida.
3. **Completar** (T-077 a T-083, T-086): medición, niveles alta y exigente, revisión, consecuencias, validación y versiones, circulares, impresión y PDF.
4. **Medir y decidir** (T-084 y T-085): corrida del caso-00 en los tres niveles, tiempos y GPU; ofrecer solo los niveles que mejoran.
