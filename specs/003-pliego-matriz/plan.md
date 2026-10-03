# Plan 003 · Procedimiento, pliego final y matriz de cumplimiento

Estado: borrador · Fecha: 2026-10-03 · Aprobó: —

Spec: `specs/003-pliego-matriz/spec.md` (aprobada el 2026-10-03).

ADR que propone este plan, en estado "propuesto":

- `docs/adr/0018-pedidos-largos-en-segundo-plano.md`: pedidos largos en una tabla de la base con un servicio `worker`, y una segunda instancia del motor de generación para esos pedidos.
- `docs/adr/0019-matriz-por-tramos-con-disposicion-obligatoria.md`: la matriz se propone recorriendo el pliego por tramos, cada tramo con su disposición obligatoria, y cada requisito con un fragmento literal verificado.

ADR en los que se apoya: 0002 (motor y modelo), 0003 (recuperación), 0004 (lectura y cita literal), 0005 (aplicación web), 0006 (dos regímenes), 0009 (respuestas de la Comisión), 0011 (medición), 0012 (suite), 0014 (puntos 6 y 7), 0015, 0017.

## En pocas palabras

1. **Procedimiento.** Un integrante de la Comisión registra el procedimiento con su número, tipo, objeto y fecha de autorización. La pantalla muestra el régimen que corresponde a esa fecha, calculado con la misma función de la 001: hasta el 2023-01-01, la Disposición 297/03; desde el 2023-01-02, la 247/2022.
2. **Pliego.** Se cargan por pantalla los documentos del pliego final: el pliego particular, sus anexos, las especificaciones técnicas y, si las hay, las circulares y las respuestas a consultas, cada una con su fecha. El sistema guarda cada original sin cambios y lo lee en segundo plano, con las mismas herramientas de la 001 (PDF con texto o escaneado).
3. **Tramos.** Reglas fijas parten el pliego en tramos: cada cláusula y subcláusula numerada, cada viñeta, cada párrafo de un anexo, cada tabla. Nada queda afuera: lo que no se pudo leer queda como tramo pendiente de revisión.
4. **Matriz propuesta.** Se elige el nivel de revisión (media, alta o exigente; por omisión, alta) y el sistema trabaja en segundo plano. El modelo recorre todos los tramos y, para cada uno, propone sus requisitos (una fila por condición, con su clase y su renglón) o dice por qué no tiene ninguno. Cada requisito es un fragmento literal del pliego: el sistema comprueba que esté, palabra por palabra, en el tramo, y muestra el documento, la página y la cláusula. Para cada requisito sugiere además las consecuencias de no cumplirlo, cada una con la cláusula del pliego o el artículo de la norma que la sostiene. Si una circular cambia un requisito, la matriz muestra el texto nuevo y el anterior, con la cita de la circular. Cuando termina, avisa.
5. **Revisión y validación.** El operador y el evaluador corrigen, quitan o agregan requisitos; el evaluador confirma, elige la consecuencia de cada requisito y valida la matriz. Todo cambio queda registrado con quién y cuándo. Una matriz validada no cambia: modificarla crea una versión nueva.
6. **Medición.** Con la lista de requisitos esperada del caso de referencia, que vive fuera del repositorio, un comando mide qué requisitos se encontraron, cuáles sobran, si las citas son literales y cuánto tarda cada nivel.

## Resumen del enfoque

Un módulo nuevo de Django, `evaluon/tenders/`, con el mismo esquema de capas de la 001: las funciones de negocio reciben al usuario, comprueban su rol y dejan el registro; la pantalla y los comandos solo traducen y llaman (ADR-0005). La lectura de documentos y el texto canónico se reutilizan de `evaluon/norms/reading/` y `evaluon/norms/splitting/canonical.py` sin cambios. Los trabajos largos (leer un documento, proponer una matriz) van a una tabla de pedidos que atiende un servicio `worker`, con su propia instancia del motor de generación (ADR-0018). La propuesta recorre el pliego por tramos con disposición obligatoria y cita verificada (ADR-0019). Para las consecuencias con fundamento normativo se reutilizan la recuperación y la selección de la 001 (`evaluon/queries/retrieval.py`) a la fecha de autorización del procedimiento. El camino del pliego no usa ningún servicio externo (P4).

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
| Requisitos | Del orden de 200 a 250 con "una fila por condición", la mayoría técnicos (estimación; la cifra la da la lista esperada) |
| Qué verificó la evaluación | Garantía de mantenimiento de oferta; habilidad de los oferentes (registro de proveedores, deuda, REPSAL, sanciones); ajuste de lo ofrecido a cada renglón (por ejemplo, alimento para cachorros y no para adultos, tamaño de bolsa); razonabilidad de precios. Dos renglones de una oferta se declararon inadmisibles por el art. 55 inc. h) del anexo de la 247/2022 |

Sin circulares ni respuestas a consultas: REQ-031 se prueba con un pliego sintético.

## Componentes

| Componente | Nuevo | Qué hace | Con quién habla |
|---|---|---|---|
| `app` | Cambia | Suma las páginas de procedimientos, documentos y matrices, y el comando `medir_matriz` | `db`; `generation`, `embeddings`, `reranker` como en la 001 |
| `worker` | Sí (ADR-0018) | Misma imagen que `app`. Corre `procesar_pedidos`: lee documentos y propone matrices, un pedido por vez | `db`; `generation_batch`; `embeddings` y `reranker` para consecuencias y circulares |
| `generation_batch` | Sí (ADR-0018) | Segunda instancia de `llama-server` con el mismo modelo, compilación y contexto que `generation`, `--parallel 1`, `--offline` | Solo `worker` y `app` (el comando de medición) |
| `db`, `generation`, `embeddings`, `reranker`, `migrate` | No | Los de la 001, sin cambios de configuración | — |

Reglas de comunicación, las de la 001: red interna sin salida a internet, sin puertos publicados salvo `app` en `127.0.0.1`. Las funciones de `tenders/services/` son el único camino para operar. `GENERATION_BATCH_URL` decide qué motor usa el `worker`; si apunta a `generation`, se vuelve a un solo motor sin cambiar código.

## Estructura del código

```
evaluon/tenders/
├── models.py  migrations/          tablas de este plan
├── segmenting.py                   tramos de un pliego y su cobertura (ADR-0019)
├── tables.py                       zonas de tabla de cada página de un PDF (pdfplumber)
├── jobs.py                         cola de pedidos: encolar, tomar, terminar, interrumpidos (ADR-0018)
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
│   ├── completeness.py             pasada de completitud y segunda extracción (alta y exigente)
│   ├── consequences.py             sugerencia de consecuencias con fundamento
│   └── circulars.py                efecto de circulares y respuestas a consultas (REQ-031)
├── prompts/                        instrucciones versionadas, un archivo por versión
├── evaluation.py                   medición contra una lista esperada
├── views/  urls.py                 un archivo de vistas por tema
└── management/commands/            procesar_pedidos, medir_matriz
evaluon/templates/tenders/          procedimientos, procedimiento, matriz, cobertura, historial
tests/tenders/                      pruebas; conftest.py propio con usuarios de la Comisión; pliegos sintéticos
```

## Modelo de datos

Nombres en inglés; los valores que nombran un concepto del dominio, en español sin tildes, como en la 001. Todas las tablas son nuevas salvo dos cambios: el rol de la Comisión en `accounts_user` y los tipos de hecho en `audit_event`.

### accounts y audit

- **`accounts_user.commission_role`**: `''` (ninguno), `operator` o `evaluator`. Independiente de `role`, que sigue siendo el de la normativa (`read`, `read_write`). Ver "Roles" y la decisión 3.
- **`audit_event.event_type`** suma: `procedure`, `tender_load`, `tender_read`, `matrix_request`, `matrix_proposal`, `requirement_change`, `consequence_choice`, `segment_review`, `matrix_validation`, `matrix_version`. Todos caben en los 20 caracteres del campo. La migración cambia la restricción de valores válidos.

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

**`tenders_reading`**: una lectura de un documento. `document`, `sequence`, `pages` (la lectura de la 001, en JSON), `tables` (zonas de tabla por página), `canonical_text`, `canonical_sha256`, `tool_versions` (las de la 001 más la versión de las reglas de tramos), `report` (páginas por estado, tramos por tipo, cobertura, pendientes), `created_at`, `job`. No se modifica.

**`tenders_segment`**: un tramo. No se modifica.

| Campo | Contenido |
|---|---|
| `id`, `reading`, `order` | Identificación, lectura y posición |
| `key` | Clave estable dentro de la lectura (ver "Tramos") |
| `label`, `path` | Encabezado tal como figura y ruta legible ("Sección I › 11. Garantía de mantenimiento de la oferta › 11.3") |
| `segment_type` | `titulo`, `clausula`, `vineta`, `parrafo`, `tabla`, `pagina` (página sin texto legible) o `no_ubicado` |
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
| `counts`, `timings`, `anomalies` | Tramos, requisitos, descartes, pendientes, citas reintentadas y amplias; tiempo por pasada y total; fallas |
| `version` | Versión de matriz que creó; vacío hasta terminar |

**`tenders_run_step`**: un pedido al modelo dentro de una propuesta. `run`, `pass_name` (`extraccion`, `extraccion_2`, `completitud`, `consecuencias`, `circulares`), `batch`, `segment_keys`, `request` (el pedido completo), `raw_output`, `parsed`, `anomalies`, `retry_of`, `timings`. Solo se insertan filas. Con esta tabla se reconstruye por qué el sistema propuso cada requisito (P6).

**`tenders_disposition`**: qué pasó con cada tramo en una propuesta. `run`, `segment`, `outcome` (`requisitos`, `descartado`, `pendiente`), `discard_reason` (lista cerrada del ADR-0019), `step`. Una por tramo y propuesta: es el control de cobertura.

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
| `id`, `version`, `number` | Número dentro de la versión, en el orden del pliego |
| `category` | `formal`, `economico` o `tecnico` |
| `items` | Renglones (lista; vacía si es general) |
| `segment`, `char_start`, `char_end`, `text` | La cita original: tramo y posiciones en el texto canónico de su lectura. `text` es igual al recorte (REQ-025) |
| `quote_flag` | Vacío o `cita_amplia` (el fragmento no se pudo ubicar y se cita el tramo entero) |
| `origin` | `propuesto`, `agregado` (por una persona) o `circular` (lo agrega una circular) |
| `state` | `propuesto`, `confirmado` o `quitado` |
| `proposed` | Copia de lo propuesto por el sistema, que no cambia (REQ-026) |
| `previous` | El mismo requisito en la versión anterior, si se copió |
| `step`, `passes` | Pedido que lo produjo y pasadas que lo encontraron |

**`tenders_requirement_source`**: textos que una circular o una respuesta suman a un requisito (REQ-031). `requirement`, `effect` (`modifica`, `aclara`, `suprime`), `segment`, `char_start`, `char_end`, `text`, `issued_on`, `step`. El texto vigente de un requisito es el del último `modifica` por fecha; si no hay, el original. Un `suprime` deja el requisito como quitado por la circular, visible y con su cita.

**`tenders_consequence`**: una consecuencia posible de un requisito (REQ-029). `requirement`, `consequence_type` (lista cerrada, decisión 8), `grounds` (lista de fundamentos: tramo del pliego con sus posiciones, o unidad de la norma por su `id` de `norms_unit`), `origin` (`sistema` o `persona`), `step`, `chosen`, `chosen_by`, `chosen_at`. Un requisito sin opciones del sistema tiene su consecuencia "no determinada".

**`tenders_pending_item`**: un tramo pendiente de revisión dentro de una versión (REQ-028). `version`, `segment`, `reason`, `resolved_by`, `resolved_at`, `resolution` (`sin_requisitos` o `requisito_agregado`).

**`tenders_requirement_change`**: historial (REQ-026). `requirement`, `action` (`confirmar`, `corregir`, `quitar`, `restituir`, `agregar`, `elegir_consecuencia`), `before`, `after`, `user`, `at`, `event`. Solo se insertan filas.

**Inmutabilidad.** Las funciones de negocio rechazan cualquier cambio sobre una versión validada, y un trigger de la base rechaza UPDATE y DELETE sobre sus requisitos, fuentes, consecuencias y pendientes, igual que con `audit_event` en la 001 (REQ-027).

### Parámetros

En `settings.py`, valores iniciales, copiados en cada propuesta: niveles disponibles (`MATRIX_LEVELS`), nivel por omisión (`alta`), niveles ofrecidos (los tres hasta la medición; después, los que decida el responsable), tokens de entrada por lote (1.500), máximo de salida por pedido (4.096), largo máximo de un tramo antes de partirlo (4.000 caracteres), requisitos por pedido de consecuencias (25), candidatos por tramo de circular (8), versiones de instrucciones, `GENERATION_BATCH_URL`, espera máxima de un pedido del `worker` (180 s) y segundos entre consultas a la cola (5).

## Roles

| Operación | Operador | Evaluador |
|---|---|---|
| Registrar un procedimiento, cargar documentos, pedir una propuesta de matriz | sí | sí |
| Ver procedimientos, documentos, matrices, cobertura e historial | sí | sí |
| Corregir, quitar o agregar requisitos en un borrador; abrir una versión nueva sobre una validada | sí | sí |
| Confirmar requisitos, elegir la consecuencia, dar por revisado un tramo pendiente | no | sí |
| Validar la matriz o descartar un borrador | no | sí |

Interpretación de la spec: el operador "propone correcciones" porque todo el borrador es una propuesta hasta que un evaluador lo valida; lo que cuenta como decisión (confirmar, elegir la consecuencia, validar) queda en manos de un evaluador (P3). Un usuario sin rol de la Comisión no ve estas páginas. El rechazo por rol se registra como en la 001 (`rejected`). `crear_usuario` suma la opción `--rol-comision`.

## Carga y lectura (REQ-023, REQ-028)

1. La persona elige el archivo, el tipo, el título y, si es una circular o una respuesta, la fecha. Se guarda el original y se encola su lectura. Hecho `tender_load`.
2. El `worker` lee con `evaluon.norms.reading.read_document` (PDF con texto o escaneado, página por página) y arma el texto canónico con `build_canonical_text` (encabezados y pies repetidos descartados, ADR-0004). Sobre los PDF busca además zonas de tabla con pdfplumber (`tables.py`), sin tocar la lectura de la 001.
3. Parte en tramos (`segmenting.py`) y guarda lectura, tramos e informe. Hecho `tender_read`.
4. La página del procedimiento muestra el estado de cada documento y, si hay, las páginas ilegibles o dudosas y las tablas, que ya figuran como pendientes de revisión.

El original se entrega con la misma vista de la 001 (sesión obligatoria; un PDF se abre en el visor del navegador en la página citada).

## Tramos (ADR-0019)

Reglas sobre las líneas del texto canónico. Un encabezado solo se reconoce al comienzo de una línea.

| Elemento | Forma | Qué produce |
|---|---|---|
| Sección | Línea en mayúsculas `SECCIÓN I - …` | Contenedor `sec-i`; su encabezado es un tramo `titulo` |
| Cláusula numerada | `7.`, `7.5.`, `7.5.2.`, `10.2.1.Una vez` (con o sin espacio) | Tramo `clausula` con clave `sec-i/7.5.2`. Control de secuencia: se acepta si continúa la numeración de su sección (hermano siguiente, primer hijo o vuelta a un nivel superior); así "3.972 kcal" o "1.300 mg" al comienzo de una línea no cortan |
| Título de cláusula sin texto | "8. VIGENCIA DE LA ORDEN DE COMPRA…" solo | Tramo `titulo` |
| Renglón | Cláusula cuyo encabezado dice "RENGLÓN N° k"; o "RENGLONES NROS. j A k" | `items` del tramo y de los que cuelgan de él |
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

## Propuesta de la matriz (REQ-024, REQ-025, REQ-028, REQ-029, REQ-030, REQ-031)

### Pedido

La persona elige el nivel entre los ofrecidos (por omisión, alta) y pide la propuesta. Se rechaza si hay un borrador abierto, si algún documento base está en lectura o si no hay ningún documento base. Hecho `matrix_request`. El `worker` toma el pedido, fija fecha, régimen y versión de la normativa, y corre las pasadas del nivel. Los pedidos al modelo van a `generation_batch`, con temperatura 0, semilla fija y pensamiento apagado, como en la 001; el cliente de generación suma un máximo de salida por pedido.

### Pasadas

| Pasada | Media | Alta | Exigente | Qué hace |
|---|---|---|---|---|
| Disposición determinista | sí | sí | sí | Tramos `titulo` → descartado ("título"); tramos `pagina` y `no_ubicado` → pendiente |
| Extracción | sí | sí | sí | Lotes de tramos consecutivos (hasta 1.500 tokens). Por cada tramo: requisitos o motivo de descarte |
| Segunda extracción | — | — | sí | La misma extracción con los lotes desplazados medio lote; se une con la primera: un requisito nuevo entra si su cita no se superpone en más de la mitad con otro del mismo tramo; un tramo descartado en una y con requisitos en la otra queda con requisitos |
| Completitud | — | sí | sí | Cada tramo con sus requisitos ya encontrados: devuelve los que faltan y divide los que juntan dos condiciones. Recibe además los tramos descartados que tienen marcadores de obligación ("deberá", "deberán", "será requisito", "mín.", "máx.", "no se aceptarán", "bajo apercibimiento", "desestim") |
| Marcadores en media | sí | — | — | En media no hay completitud: los tramos descartados con marcadores de obligación quedan pendientes de revisión |
| Circulares | si hay | si hay | si hay | Ver "Circulares y respuestas" |
| Consecuencias | sí | sí | sí | Ver "Consecuencias" |

Cada nivel se ofrece solo si la medición demuestra que mejora al anterior: más requisitos encontrados, o menos sobrantes con los mismos encontrados (spec). Los tres se construyen; la corrida de T-084 decide cuáles se ofrecen (T-085).

### Extracción: qué recibe y qué devuelve el modelo

- **Recibe.** Las instrucciones (`prompts/matriz-extraccion-v1.md`): qué es un requisito (una condición que la oferta debe cumplir y que se verifica por separado; una fila por condición), los criterios de clase (decisión 5) y de requisito de la oferta (decisión 4), la lista cerrada de motivos de descarte y la regla de copiar el fragmento exacto. Después, cada tramo del lote con un alias (`T1`, `T2`, …), su ruta, sus renglones y su texto.
- **Devuelve** un JSON que el motor obliga a cumplir. El esquema tiene una propiedad obligatoria por alias del lote; cada una trae `requisitos` (lista de `{cita, clase, renglon}`, con `clase` y `renglon` de listas cerradas) y `descarte` (motivo de la lista o vacío).
- **El sistema valida**, tramo por tramo:
  - Sin requisitos ni descarte, o con los dos: tramo sin disposición.
  - Cada `cita` se busca exacta dentro del texto del tramo (`quotes.py`). Si aparece más de una vez, se toma la primera aparición no usada. Si no aparece, el requisito se marca para reintento.
  - Dos requisitos del mismo tramo con la misma cita se unen.
  - Los tramos sin disposición y los requisitos con cita no encontrada se vuelven a pedir una vez, solos. Si siguen igual: el tramo queda **pendiente**, y el requisito queda con el tramo entero como cita y la marca `cita_amplia`.
  - Si la salida se cortó por el máximo de salida, el lote se parte en dos y se repite cada mitad.
  - El renglón: si el tramo cuelga de un renglón, vale el del tramo; si es general, el que eligió el modelo.
- El requisito **no lleva texto redactado por el modelo**: se muestra el fragmento literal, su clase y su renglón. Así toda la matriz es texto del pliego (P3) y la medición no depende de redacciones (ADR-0014, punto 7).

### Cita (REQ-025)

La definición de "palabra por palabra" es la del ADR-0004 y la comprobación, la del plan 001: el texto mostrado es igual a `canonical_text[char_start:char_end]` de la lectura. La página sale de las líneas del texto canónico (`pages_at`); la cláusula, de la ruta del tramo. La pantalla muestra documento, página, cláusula y el enlace al original en esa página.

### Consecuencias (REQ-029)

1. **Fundamentos del pliego.** Los tramos de los documentos base con marcadores de consecuencia ("desestim", "inadmisib", "subsan", "intim", "apercibimiento", "causal suficiente", "rechaz"), más el tramo del propio requisito. En el caso-00 son unos diez. Si superan el espacio, el reranker elige los más pertinentes a una pregunta fija.
2. **Fundamentos de la norma.** Las preguntas fijas de las instrucciones (por ejemplo, "¿Qué deficiencias de una oferta no son subsanables y causan su desestimación?" y "¿Qué errores u omisiones de una oferta se pueden subsanar y cómo se intima al oferente?") pasan por la recuperación y la selección de la 001 (`retrieve` y `select_units`) con la fecha de autorización del procedimiento. Sin régimen a esa fecha, no hay fundamentos de la norma.
3. **Pedido.** De a 25 requisitos. El modelo recibe los fundamentos con alias (`P1…` del pliego, `N1…` de la norma, con norma y ruta) y los requisitos (`R1…`). Devuelve, por requisito, hasta tres opciones `{tipo, fundamentos}`; `tipo` de la lista cerrada y `fundamentos` solo entre los alias mostrados, al menos uno.
4. **Validación**, como en la 001: un alias inexistente invalida la opción; un requisito sin opciones válidas queda con la consecuencia **"no determinada"** (P3). El sistema pone el texto de cada fundamento desde la base.
5. **Elección.** Un evaluador elige una opción; queda registrado con quién y cuándo (`consequence_choice`). Si ninguna sirve, puede elegir otro tipo de la lista, que queda como decisión de una persona sin fundamento del sistema.

Ejemplo del criterio de aceptación con el caso-00: el requisito de la cláusula 11.3 ("La garantía de mantenimiento de la oferta deberá ser individualizada en ocasión de presentarse la oferta") recibe "desestimación sin posibilidad de subsanación" con la cita de esa misma cláusula, y queda confirmada solo cuando un evaluador la elige.

### Circulares y respuestas (REQ-031)

- Se leen y se parten como cualquier documento. Se procesan después de la extracción, por fecha y, a igual fecha, por orden de carga.
- Para cada tramo de una circular o de una respuesta, los requisitos candidatos son los de los tramos cuya cláusula o renglón el tramo nombra ("cláusula 1.1", "Renglón N° 2") más los 8 que el reranker puntúa más alto contra el texto del tramo.
- El modelo devuelve, por tramo, sus efectos (`modifica`, `aclara` o `suprime`, el requisito alcanzado y la cita literal de la circular), requisitos nuevos que la circular agrega, o un motivo de "sin efecto". Las citas se verifican igual que en la extracción. Todo tramo de circular queda con disposición.
- En la pantalla, un requisito modificado muestra el texto vigente (el de la circular, con su cita y su fecha) y el original (con la suya). Una aclaración o una respuesta figura junto al requisito con su cita.
- Ejemplo del criterio de aceptación, con un pliego sintético: el pliego exige "16 GB de RAM" y una circular posterior dice "32 GB". La matriz muestra "32 GB" como vigente, "16 GB" como original y cita la circular.

### Abstención y fallas

- Un tramo nunca desaparece: tiene requisitos, un descarte con motivo o queda pendiente.
- Una consecuencia sin fundamento es "no determinada".
- Una falla técnica (servicio caído, espera agotada) deja el pedido en `failed` con su motivo; no se crea una matriz a medias. Lo ya registrado en `tenders_run_step` queda.

## Revisión, validación y versiones (REQ-026, REQ-027, REQ-028)

- **Confirmar** (evaluador): uno o varios requisitos seleccionados.
- **Corregir** (operador o evaluador): clase, renglones o cita. La cita corregida se elige dentro de un tramo y se comprueba literal, igual que la del modelo.
- **Quitar** y **restituir**: el requisito queda `quitado`, visible y con su historia.
- **Agregar**: desde un tramo, con un fragmento literal, clase y renglón; origen `agregado`.
- **Resolver un pendiente** (evaluador): "revisado, sin requisitos", o agregando requisitos desde ese tramo.
- Cada cambio deja una fila en `tenders_requirement_change` y el hecho `requirement_change`, con lo de antes y lo de después. Lo propuesto originalmente queda en `proposed` y se consulta en el historial del requisito.
- **Validar** (evaluador): pasa la versión a `validated`. Las condiciones que propone este plan están en la decisión 9: ningún pendiente sin resolver, cada requisito no quitado con su consecuencia elegida, y los requisitos todavía propuestos quedan confirmados por la validación, cada uno con su fila de historial.
- **Versión nueva**: sobre la última validada se abre un borrador con número siguiente que copia requisitos, fuentes, consecuencias elegidas y pendientes resueltos, cada uno con `previous`. La anterior no cambia (REQ-027).
- **Descartar un borrador** (evaluador): queda `discarded`, visible. Permite pedir una propuesta nueva.

## Pantalla

Páginas armadas en el servidor, sin htmx (ADR-0005), con la hoja de estilos y el script propios.

- **Procedimientos**: lista con número, objeto, fecha de autorización, régimen y estado de la matriz; formulario para registrar. Al registrar se muestra la línea "Procedimiento autorizado el 15/12/2022 · Régimen aplicable: Disposición AFIP 297/03", con el mismo texto fijo de la 001.
- **Procedimiento**: datos y régimen; documentos con su tipo, fecha, estado de lectura y enlace al original; formulario de carga; versiones de la matriz; formulario "Proponer matriz" con el nivel (alta marcado) y los pedidos en curso.
- **Matriz**: encabezado con versión, estado, nivel, régimen y fecha; resumen (requisitos por clase, pendientes, consecuencias sin elegir); "Pendiente de revisión" primero; requisitos agrupados por documento, sección y renglón, cada uno con su clase, su texto literal, su ubicación, los textos de circulares y respuestas, sus consecuencias con fundamento y sus acciones; casillas para confirmar varios; botón "Validar".
- **Cobertura**: todos los tramos con su disposición y su motivo.
- **Historial** de un requisito.
- **Aviso de fin**: en cualquier página, un recuadro con los pedidos de la persona que terminaron y todavía no vio, con enlace (ADR-0018).

## Registro de auditoría (P6)

| Hecho | Qué guarda además de los datos comunes |
|---|---|
| `procedure` | Número, tipo, objeto, fecha de autorización, régimen mostrado y versión de la normativa |
| `tender_load` | Procedimiento, tipo, título, fecha, nombre, formato, tamaño y huella del archivo; también las cargas rechazadas |
| `tender_read` | Lectura, versiones de las herramientas y de las reglas de tramos, páginas por estado, tramos por tipo, cobertura, pendientes |
| `matrix_request` | Procedimiento, nivel, documentos y lecturas incluidos |
| `matrix_proposal` | Propuesta, versión creada o motivo de la falla, nivel, fecha, régimen, versión de la normativa, modelos con huella, parámetros, versiones de instrucciones, cuentas, tiempos y anomalías. El detalle de cada pedido al modelo está en `tenders_run_step` |
| `requirement_change` | Versión, requisito, acción, antes y después |
| `consequence_choice` | Requisito, opción elegida con sus fundamentos, si era sugerida por el sistema |
| `segment_review` | Versión, tramo, motivo del pendiente, resolución |
| `matrix_validation` | Versión, cuentas por estado y por clase, requisitos confirmados por la validación |
| `matrix_version` | Versión nueva, versión de la que sale; o borrador descartado |
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
criterios: "plan 003, decisiones 4 y 5"       # definición de requisito y de clase usadas
preparo: "Coordinador, AAAA-MM-DD"
visto_bueno: "responsable, AAAA-MM-DD"        # sin esto, la lista no se usa
confirmacion_comision: pendiente              # feature 009
uso: primera_corrida                          # primera_corrida o ajuste (decisión 7)
requisitos:
  - id: M-001
    documento: PLIEG-2025-04092776-ARCA-DVGDCO#SDGADM.pdf
    tramo: sec-i/11.3
    pagina: 8
    ancla: "La garantía de mantenimiento de la oferta deberá ser individualizada en ocasión de presentarse la oferta"
    clase: formal
    renglones: []
    consecuencia: desestimacion_sin_subsanacion   # optativa; informativa
    en_dictamen: si                               # si, no
  - id: M-150
    documento: PLIEG-2025-04092776-ARCA-DVGDCO#SDGADM.pdf
    tramo: sec-iii/1.1
    pagina: 16
    ancla: "Proteína bruta (mín.): 24%"
    clase: tecnico
    renglones: [1]
    en_dictamen: no
```

  `ancla` es el fragmento literal más corto que identifica la condición, copiado del pliego. Si aparece más de una vez dentro del tramo, se agrega `ocurrencia: 2`.
- **Cómo se prepara, sin correr el sistema.** La prepara el Coordinador leyendo el PDF, cláusula por cláusula, con los criterios de las decisiones 4 y 5 y las claves de "Tramos", que se derivan de la numeración impresa. Después la contrasta con lo que verificó la evaluación del caso (columna `en_dictamen`): todo lo que la evaluación verificó tiene que estar en la lista. Nadie corre la propuesta de matriz sobre el caso-00 hasta que la lista tenga el visto bueno; por eso T-075 (hilo mínimo) depende de T-076.
- **Cómo la aprueba el responsable.** Con una tabla de ejemplos (unos 15 requisitos de clases y secciones distintas, más los casos dudosos), las cuentas por sección, clase y renglón, y la lista de lo que verificó la evaluación con su requisito. El responsable anota el visto bueno en el archivo. La confirma después la Comisión (feature 009).
- **Antes de medir**, `medir_matriz --verificar-esperada` comprueba que la huella del archivo coincida con la del documento cargado y que cada ancla esté, exacta, en el tramo indicado. No usa el modelo.

### Cómo se cuenta

1. **Ubicación del ancla.** Cada ancla se busca exacta en el tramo indicado, en el texto canónico de la lectura usada. Un ancla que no aparece es una falla de la lectura o de la lista: se informa y bloquea.
2. **Emparejamiento por cita, no por redacción.** Un requisito propuesto empareja con uno esperado si están en el mismo documento y la cita propuesta cubre al menos la mitad de los caracteres del ancla. El emparejamiento es uno a uno: se ordenan los pares por superposición y se asignan de mayor a menor. Un requisito propuesto que cubre dos anclas empareja con una sola.
3. **Encontrado**: requisito esperado emparejado. **Faltante**: no emparejado, con su causa: tramo descartado (y el motivo), tramo pendiente, agrupado con otro requisito (decisión 6), tramo con requisitos pero no este, ancla no encontrada.
4. **Sobrante**: requisito propuesto sin emparejar. Se informan la cantidad y su reparto por tramo y por clase; no tienen límite.
5. **Clase y renglón**: entre los encontrados, la proporción con la clase y los renglones esperados (decisión 6).
6. **Cita literal**: sobre todos los requisitos propuestos, el texto es igual al recorte del texto canónico, cae dentro de su tramo y la página informada es la del recorte. Las citas amplias se cuentan aparte.
7. **Cobertura**: tramos con disposición sobre el total, y pendientes por motivo. Se espera 100 % con disposición.
8. **Consecuencias** (informativo): donde la lista trae `consecuencia`, si está entre las sugeridas.

| Medida | Meta |
|---|---|
| Requisitos encontrados | 100 %. Cada faltante se informa con su causa y bloquea la aceptación |
| Cita literal | 100 % |
| Tramos con disposición | 100 % |
| Sobrantes | Sin límite; se informan |
| Clase y renglón correctos | Decisión 6 |
| Tiempo por nivel | El de la spec, para unas 50 páginas (ver "Tiempos") |

### La corrida

- `medir_matriz --procedimiento <número> --esperada <archivo> --niveles media,alta,exigente`, dentro de `app`. Corre la propuesta con la misma función que el `worker`, con el canal `eval`; no exige que el procedimiento esté sin borrador, y las versiones que crea quedan descartadas al terminar, para no interferir con el trabajo real. Se corre de a una, sin otra carga en la GPU, salvo la prueba de contención (ver "Tiempos").
- Guarda una carpeta por corrida en `corpus/casos/caso-00/corridas/` (fuera del repositorio): `parametros.json`, `resultados.jsonl` (un renglón por requisito esperado y por propuesto), `resumen.md` (puede tener texto del pliego) y `resumen-publico.md`, que solo tiene identificadores `M-NNN`, claves de tramo, cuentas, causas y tiempos. Solo este último se copia al repositorio, en `specs/003-pliego-matriz/verificacion/T-084.md`.
- Cada proporción lleva su intervalo de Wilson al 95 %, con la función de la 001.

### Por qué la medida es provisoria

- Un solo pliego. Los requisitos de un mismo pliego no son independientes entre sí: el intervalo sobre unos 250 requisitos (con 250 de 250, de 98,5 % a 100 %) sobreestima la confianza. La unidad que importa es el pliego.
- ADR-0014, punto 7, pide una parte de los casos que nunca se use para ajustar. Con un pliego no hay cómo separarla. Se propone (decisión 7): las instrucciones `v1` quedan fijas antes de la primera corrida; esa primera corrida se informa como la medida independiente provisoria; si después se ajusta algo, el caso-00 pasa a ser de ajuste (`uso: ajuste`) y la aceptación espera al próximo pliego que aporte la Comisión, que se mide primero sin ajustes.
- La spec ya lo prevé: la medición se informa como provisoria y se repite cuando haya más casos.

## Tiempos y GPU

Estimación con lo medido en la 001 (unos 3.000 tokens por segundo al leer y 73 al escribir) y lo que se vio del caso-00 (unos 11.000 tokens de texto, unos 200 tramos, unos 250 requisitos). La salida domina: cada requisito ocupa unos 40 tokens y cada disposición unos 12.

| Pasada | Caso-00 (20 páginas) | 50 páginas (×2,5) |
|---|---|---|
| Extracción | 3 a 4 min | 8 a 10 min |
| Completitud | 1 a 2 min | 3 a 5 min |
| Segunda extracción y unión | 3 a 4 min | 8 a 10 min |
| Consecuencias | 1 a 2 min | 3 a 4 min |
| **Media** | **5 a 6 min** (límite 15) | **11 a 14 min** |
| **Alta** | **6 a 8 min** (límite 30) | **14 a 19 min** |
| **Exigente** | **9 a 12 min** (límite 60) | **22 a 29 min** |

Media es la que queda más cerca de su límite. Los números son estimaciones: T-075 da la primera medición y T-084 la de todos los niveles. Como no hay un pliego de 50 páginas, el tiempo de 50 páginas se informa por página y por tramo, extrapolado y provisorio, hasta que la Comisión aporte uno.

| Memoria de video | MiB |
|---|---|
| `generation` + `embeddings` + `reranker` (medido en la 001) | 10.344 |
| `generation_batch` (mismo modelo y contexto que `generation`) | unos 7.818 |
| Total estimado | unos 18.162 de 24.137 libres |

T-071 mide la memoria con los cuatro modelos cargados. T-084 mide además una consulta de normativa sola y durante una propuesta de matriz; la exigencia de la 001 es de hasta 30 segundos.

## Qué no se hace en esta feature

- La revisión del pliego borrador contra la normativa (002), las ofertas (008) y la evaluación (004). Redactar o modificar el pliego.
- Texto redactado por el modelo en los requisitos: el requisito es el fragmento literal.
- Búsqueda por significado o por palabras sobre el pliego: no se calculan vectores de los tramos.
- Reconocer la estructura de las tablas (por ejemplo, con Docling): las tablas se leen como texto y quedan pendientes de revisión.
- Volver a proponer solo lo que cambió una circular que llega después de validar: se pide una propuesta nueva, que crea una versión nueva.
- Corregir los datos de un procedimiento registrado o quitar un documento cargado: ningún requisito lo pide.
- Preguntas a la Comisión (ADR-0009): son de la 002 y la 004.
- Actualización automática de la página o avisos fuera de la aplicación.
- Exportar la matriz (feature 006).

## Cobertura de requisitos

| Requisito | Cómo se resuelve | Cómo se verifica |
|---|---|---|
| REQ-022 | `tenders_procedure`; `services/procedures.py`; `applicable_regimes(fecha)` de la 001; línea de régimen en la pantalla; hecho `procedure` | Test con normas de prueba: fecha 2022-12-15 muestra la Disposición 297/03; 2023-01-02, la 247/2022; fecha futura rechazada; el registro guarda régimen y versión de la normativa |
| REQ-023 | `tenders_document` y `tenders_document_file`; carga por pantalla; vista del original | Test: un pliego en tres documentos; la huella de lo que entrega la vista es igual a la de cada archivo cargado; el mismo archivo dos veces se rechaza |
| REQ-024 | Tramos con cobertura; extracción con disposición obligatoria; completitud y segunda extracción según nivel; clase de lista cerrada | Tests con dobles: todo tramo queda con requisitos, descarte o pendiente; un tramo sin disposición se reintenta y queda pendiente; cada requisito con clase válida. Medición: 100 % de encontrados sobre el caso-00, provisoria |
| REQ-025 | Fragmento literal ubicado en el tramo; posiciones en el texto canónico; documento, página y cláusula en la pantalla | Tests: cita no encontrada se reintenta y queda como cita amplia; el texto mostrado es igual al recorte; página y cláusula correctas. Medición: 100 % de cita literal |
| REQ-026 | `services/review.py`; `tenders_requirement_change`; `proposed`; roles | Tests: una corrección queda con usuario, momento, antes y después, y lo propuesto se consulta; quitar y agregar quedan registrados; un operador no puede confirmar |
| REQ-027 | `services/validation.py`; versiones; trigger de inmutabilidad | Tests: cambiar una versión validada se rechaza en la función y en la base; abrir una versión nueva la copia y la anterior sigue igual |
| REQ-028 | Páginas ilegibles o dudosas, tablas, tramos no ubicados y tramos sin disposición como pendientes; marcadores en media | Test: un pliego sintético con una página de ruido; esa página figura como pendiente de revisión en la matriz propuesta y ninguna otra |
| REQ-029 | Pasada de consecuencias con fundamentos del pliego y de la norma a la fecha; lista cerrada de tipos; elección por un evaluador | Tests con dobles: una cláusula que sanciona con desestimación produce la sugerencia con su cita; sin fundamento, "no determinada"; la elección queda con quién y cuándo |
| REQ-030 | Nivel en el pedido, por omisión alta; guardado en la propuesta y en la versión; niveles ofrecidos por configuración | Tests: sin elegir, alta; con media o exigente, el elegido; cada nivel corre sus pasadas. Medición por nivel en T-084 |
| REQ-031 | Tipos de documento con fecha; pasada de circulares; `tenders_requirement_source`; pantalla con los dos textos | Test con un pliego sintético: "16 GB de RAM" y una circular "32 GB": el requisito exige 32 GB, muestra los dos textos y cita la circular; una respuesta que precisa un requisito figura junto a él con su cita |

Requisitos no funcionales: la medición, en "Medición"; tiempo y nivel, en "Tiempos y GPU" y T-084; sin conexión, con la red interna y una prueba con la red cortada en T-075.

## Verificación contra la constitución

| Principio | Cumple | Nota |
|---|---|---|
| P1 Spec | sí | Cada pieza responde a un REQ. Lo que se suma sin REQ propio está justificado: rechazar el mismo archivo dos veces (evita tramos duplicados), la tabla de pedidos (la exige el tiempo de la spec) |
| P2 Trazabilidad | sí | Tabla de cobertura; cada tarea nombra sus REQ |
| P3 Recomienda, la Comisión decide | sí | Requisitos como texto literal; consecuencias con fundamento o "no determinada"; confirmar, elegir y validar, solo un evaluador |
| P4 Datos | sí | El camino del pliego no usa servicios externos: lectura en CPU, modelos locales sin red. El caso y su lista esperada quedan fuera del repositorio; al repositorio solo llegan resúmenes sin texto del pliego |
| P5 Local y reproducible | sí | Dos servicios nuevos en `docker-compose.yml`, misma imagen y modelo fijados |
| P6 Auditoría | sí | Ver "Registro de auditoría" y `tenders_run_step` |
| P7 Evals | sí | `medir_matriz` con salida estructurada; todo cambio de instrucciones o modelo de la matriz se vuelve a medir |
| P8 Normativa versionada | sí | Cada propuesta guarda régimen y versión de la normativa |
| P9 Compliance | sí | No se infiere nada de sistemas externos; los requisitos que se verifican afuera (registro de proveedores, deuda) entran a la matriz como requisitos, y su verificación queda para la 005 |
| P10 Simplicidad | sí | Sin cola de terceros, sin vectores del pliego, sin estructura de tablas, sin texto redactado. Los niveles alta y exigente se construyen porque la spec los pide; se ofrecen solo si mejoran |
| P11 Compuertas | sí | Plan y ADR 0018 y 0019 en estado propuesto |

## Qué tiene que decidir el responsable

1. **Pedidos largos y segundo motor (ADR-0018).** Los trabajos largos van a un servicio `worker` y usan una segunda copia del modelo, para no frenar las consultas de normativa.

   | Opción | Memoria de video | Consulta de normativa durante una matriz |
   |---|---|---|
   | Un solo motor | unos 10 GB | Espera hasta que termine el pedido en curso: unos 15 s + hasta 20 s |
   | Dos motores (propuesta) | unos 18 GB de 24 | No espera; comparte la placa (se mide en T-084) |

   ¿Aprobás el ADR-0018 con dos motores? Recomendado: sí.

2. **Matriz por tramos (ADR-0019).** Todo tramo del pliego queda con requisitos, con un motivo de descarte o pendiente de revisión.

   | Tramo del caso-00 | Resultado esperado |
   |---|---|
   | 7.5.2 (declaración jurada de habilidad) | Requisito formal |
   | 3.1, viñeta "Ley de Procedimiento Administrativo N° 19.549…" | Descartado: norma aplicable |
   | Página que no se pudo leer | Pendiente de revisión |

   ¿Aprobás el ADR-0019? Recomendado: sí.

3. **Rol de la Comisión aparte del rol de normativa.** Un campo nuevo en el usuario, independiente del que ya existe.

   | Usuario | Normativa | Comisión |
   |---|---|---|
   | Responsable de normativa | lectura y escritura | ninguno |
   | Personal de apoyo | lectura | operador |
   | Integrante de la Comisión | lectura | evaluador |

   ¿Aprobás el rol de la Comisión como un campo aparte? Recomendado: sí.

4. **Qué cuenta como requisito de la oferta.** Dentro: lo que la oferta tiene que presentar, ofrecer o comprometer, incluidas las condiciones del bien y los plazos que la oferta asume. Fuera: cómo se ejecuta y se controla el contrato (multas, recepción, pagos, confidencialidad) y lo que hace el organismo.

   | Cláusula del caso-00 | ¿En la lista esperada? |
   |---|---|
   | 7.5.2 Presentar la declaración jurada de habilidad | sí, formal |
   | Sección II, 1.3 Vencimiento mayor a 11 meses desde la entrega | sí, técnico |
   | 9.2.1 Entrega en 15 días hábiles | sí, técnico |
   | 24.3 Multas por atraso | no: ejecución del contrato |
   | 25.1 Forma y moneda de pago | no: obligación del organismo |

   ¿Aprobás este criterio? Recomendado: sí.

5. **Criterio de clase.**

   | Condición | Clase |
   |---|---|
   | Garantía de mantenimiento del 5 % | formal |
   | Inscripción en el registro de proveedores | formal |
   | Cotizar en pesos con IVA, precio unitario por renglón | económico |
   | Mantener la oferta 60 días corridos | formal |
   | Proteína bruta mínima 24 % | técnico |

   ¿Aprobás estos criterios? Recomendado: sí.

6. **Cómo se cuenta un requisito encontrado.** Un requisito propuesto que junta dos condiciones encuentra una sola; la clase equivocada se informa pero no bloquea.

   | Propuesto | Esperado | Resultado |
   |---|---|---|
   | "Proteína bruta (mín.): 24%; Extracto etéreo (mín.): 15%" | dos condiciones | 1 encontrada, 1 faltante (agrupada) |
   | Garantía clasificada como económica | formal | encontrada; clase incorrecta informada |

   ¿Aprobás que el agrupamiento cuente como faltante y que la clase no bloquee? Recomendado: sí.

7. **Primera corrida sin ajustes.** Las instrucciones quedan fijas antes de la primera corrida sobre el caso-00; esa corrida es la medida provisoria; si después se ajusta, el caso-00 pasa a ajuste y la aceptación espera otro pliego.

   | Corrida | Uso |
   |---|---|
   | Hilo mínimo (T-075) | Solo comprueba que funciona; no se compara con la lista ni se ajusta |
   | Primera corrida de T-084 | Medida provisoria independiente |
   | Siguientes | Ajuste |

   ¿Aprobás este uso del caso-00? Recomendado: sí.

8. **Tipos de consecuencia.** Lista cerrada de la que el sistema sugiere y el evaluador elige.

   | Tipo | Ejemplo en el caso-00 |
   |---|---|
   | Desestimación sin posibilidad de subsanación | 11.3, garantía no individualizada |
   | Intimación a subsanar; si no se subsana, desestimación | 7.3, documentación omitida |
   | Otra consecuencia prevista en el pliego (con su cita) | 13.4, oferta condicionada |
   | No determinada (sin fundamento) | — |

   ¿Aprobás esta lista? Recomendado: sí.

9. **Condiciones para validar.** No quedan pendientes sin resolver, cada requisito tiene su consecuencia elegida, y la validación confirma los requisitos que seguían propuestos.

   | Situación | ¿Se puede validar? |
   |---|---|
   | Una tabla pendiente sin revisar | no |
   | Un requisito con la consecuencia sin elegir | no |
   | 30 requisitos propuestos sin confirmar uno por uno | sí: quedan confirmados por la validación, con su registro |

   ¿Aprobás estas condiciones? Recomendado: sí.

10. **Tiempo de 50 páginas, provisorio.** Sin un pliego de 50 páginas, el tiempo se mide con el caso-00 (20 páginas) y se extrapola.

    | Nivel | Caso-00 medido | 50 páginas extrapolado | Límite |
    |---|---|---|---|
    | Media | (T-084) | por página × 50 | 15 min |

    ¿Aceptás la extrapolación como medida provisoria hasta tener un pliego de 50 páginas? Recomendado: sí.

## Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Un solo pliego para ajustar y medir | El 100 % medido no garantiza el próximo pliego | Medida provisoria; primera corrida sin ajustes; cada pliego nuevo se mide primero sin ajustar (decisión 7) |
| El modelo descarta un tramo que tiene requisitos | Faltante | Descarte con motivo visible; marcadores de obligación (pendiente en media, completitud en alta); la medición informa la causa |
| El modelo junta varias condiciones en una fila | Faltante por agrupamiento | Instrucciones con ejemplos de "una fila por condición"; completitud divide; se mide (decisión 6) |
| El modelo copia mal la cita | Requisito con cita amplia | Reintento; cita amplia marcada para revisar; nunca una cita que no esté en el pliego |
| Reglas de tramos que no reconocen otro pliego | Tramos grandes o no ubicados | Siguen pasando por el modelo o quedan pendientes; nunca afuera; se ajustan las reglas con una tarea y una relectura |
| Tablas mal leídas | Condiciones de una tabla mezcladas | Toda tabla queda pendiente de revisión con enlace a la página |
| Media se pasa de 15 minutos en un pliego de 50 páginas | No cumple el tiempo | Se mide; tamaño de lote y máximo de salida son parámetros; si media no cumple, no se ofrece |
| Una consulta de normativa tarda más de 30 s mientras corre una matriz | No cumple la 001 en ese momento | Segundo motor (ADR-0018); se mide en T-084; si no alcanza, se informa al responsable |
| Memoria de video con cuatro modelos | Un servicio no carga | Se mide en T-071; el margen estimado es de unos 6 GB |
| Un pedido se interrumpe | Matriz a medias | El pedido queda `failed`; nunca una versión parcial; al arrancar, `procesar_pedidos` cierra los interrumpidos |
| La lista esperada tiene un error | Faltante o sobrante falso | Visto bueno del responsable con tabla de ejemplos; ancla verificada antes de medir; confirmación de la Comisión en la 009 |
| Datos personales en el repositorio | Incumple P4 y la decisión del responsable | Lista y corridas en `corpus/casos/`; al repositorio solo `resumen-publico.md`, sin texto del pliego |
| Un documento cargado por error | Requisitos de otro pliego | Fuera de alcance quitarlo; el evaluador quita los requisitos o descarta el borrador; si hace falta, se registra de nuevo el procedimiento |
| Circulares sin un caso real | REQ-031 medido solo con un ejemplo sintético | Tests con el ejemplo de la spec; se mide cuando la Comisión aporte un pliego con circulares |

## Vacíos de la spec, para el Coordinador

No se modificó la spec. Estos puntos los resuelve este plan con una propuesta, o una decisión del responsable:

1. La spec no dice qué es "requisito de la oferta" frente a una obligación de la ejecución del contrato (decisión 4) ni define las clases (decisión 5).
2. El criterio de medición pide "la clasificación y la cita correctas" pero solo fija metas para encontrados y cita literal (decisión 6).
3. No dice si se puede validar con pendientes o consecuencias sin elegir (decisión 9), ni la lista de tipos de consecuencia (decisión 8).
4. "El operador propone correcciones": el plan lo interpreta como edición del borrador, que valida un evaluador (ver "Roles").
5. Los tiempos son para 50 páginas y el único pliego tiene 20 (decisión 10).
6. ADR-0014, punto 7, pedía armar el conjunto con la Comisión antes del plan; la spec aprobada lo cambió por la lista del Coordinador con visto bueno del responsable y confirmación posterior de la Comisión. El plan sigue la spec.
7. REQ-031 no se puede medir con el caso-00, que no tiene circulares.

## Orden de construcción

Detalle en `specs/003-pliego-matriz/tasks.md`.

1. **Base** (T-067 a T-071): tablas, roles, procedimiento, tramos, pedidos en segundo plano y segundo motor.
2. **Hilo mínimo** (T-072 a T-075): cargar el pliego del caso-00, proponer la matriz en nivel media y verla en la pantalla, con los servicios reales. Requiere la lista esperada aprobada (T-076), para que nadie la escriba después de ver la salida.
3. **Completar** (T-077 a T-083): medición, niveles alta y exigente, revisión, consecuencias, validación y versiones, circulares.
4. **Medir y decidir** (T-084 y T-085): corrida del caso-00 en los tres niveles, tiempos y GPU; ofrecer solo los niveles que mejoran.
