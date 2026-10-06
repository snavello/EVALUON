# Spec 004 · Evaluación asistida de ofertas

Estado: aprobada · Fecha: 2026-10-06 · Aprobó: responsable del proyecto (2026-10-06, con las respuestas de "Preguntas abiertas")

> La spec dice qué se necesita y por qué. No menciona tecnología, librerías ni estructura de código: eso va en el plan.
> Cada duda se marca `[A ACLARAR: pregunta concreta]`. Una spec con marcas pendientes no pasa la compuerta.

## Problema

Con la matriz validada (003), las ofertas cargadas (008) y los datos del Portal (012), la Comisión todavía tiene que decidir, por cada oferta y cada requisito, si cumple, no cumple o no se puede determinar, y escribir el fundamento. Es el trabajo central de la evaluación y el más largo: hay que ir de cada requisito a los documentos de cada oferente, a la normativa y a las respuestas de las consultas, y dejar asentado por qué.

El sistema puede preparar ese trabajo: proponer para cada par oferta y requisito un resultado con su fundamento citado, y preguntarle a la Comisión lo que no puede resolver solo. La decisión sigue siendo de la Comisión (P3): confirma, corrige o rechaza cada propuesta.

La ficha por oferta (008) mostró que buscar pasajes parecidos no alcanza con ofertas reales (ADR-0035). La 004 lee completos los documentos de la oferta para cada requisito: las ofertas son cortas (de 8 a 45 páginas en el caso-00).

## Usuarios y escenarios

Roles de la 003: el operador prepara; el evaluador decide (P3).

**Escenario 1 · Proponer la evaluación.** Como integrante de la Comisión, cuando la matriz está validada y las ofertas cargadas, necesito pedir la evaluación de una oferta, para recibir por cada requisito una propuesta de cumple, no cumple o no determinado, con su fundamento.

**Escenario 2 · Revisar y decidir.** Como evaluador, necesito ver cada propuesta con el texto del pliego, el de la oferta (con documento y página) y, si corresponde, la norma o la respuesta de la Comisión, para confirmarla, corregirla o rechazarla, y que quede registrado.

**Escenario 3 · Preguntas a la Comisión.** Como evaluador, cuando el sistema no puede resolver un requisito con lo que tiene, necesito ver la pregunta concreta que me hace, responderla o dejarla sin responder, y que mi respuesta sirva de fundamento (ADR-0009).

**Escenario 4 · Ver el estado de la evaluación.** Como integrante de la Comisión, necesito ver por oferta cuántos requisitos están propuestos, confirmados, corregidos, rechazados o no determinados, y cuáles preguntas siguen abiertas.

## Requisitos funcionales

| ID | Requisito | Origen normativo |
|---|---|---|
| REQ-052 | Para cada oferta y cada requisito de la matriz validada, el sistema debe proponer un resultado: cumple, no cumple, no se encontró el documento, o no determinado (con duda o sin corroborar, citando lo que tiene). | — |
| REQ-053 | Cada propuesta debe traer su fundamento citado: el texto del requisito (pliego o circular), el texto de la oferta que lo sostiene (documento y página, texto literal) y, si lo usa, la norma con su artículo o la respuesta registrada de la Comisión. Sin fundamento citado, el resultado es "no determinado". | P3 |
| REQ-054 | Para proponer, el sistema debe leer completos los documentos de la oferta que pueden responder el requisito, no solo los pasajes que encuentra una búsqueda. | ADR-0035 |
| REQ-055 | Cuando no puede resolver un requisito con el pliego, la oferta, la normativa o lo ya respondido, el sistema debe formular una pregunta concreta a la Comisión. Una pregunta sin respuesta deja el requisito en "no determinado" y se informa. | Hoja de ruta, "Preguntas a la Comisión" |
| REQ-056 | El evaluador debe poder confirmar, corregir o rechazar cada propuesta, y responder las preguntas. Cada decisión y cada respuesta quedan registradas con quién y cuándo (P6). Una respuesta puede servir de fundamento en otros requisitos (ADR-0009). | P3, P6 |
| REQ-057 | La evaluación de una oferta se arma contra una versión de la matriz validada y lo indica; si la matriz cambia, se avisa. | — |
| REQ-058 | El sistema debe mostrar, por oferta, el estado de la evaluación: requisitos por estado y preguntas abiertas. | — |
| REQ-059 | La evaluación se pide para todas las ofertas del procedimiento a la vez y se presenta como una **matriz de evaluación** (ofertas por requisitos). Las ofertas que no cumplen requisitos formales o técnicos quedan señaladas como descartadas, con el requisito y su fundamento, y las demás se **ordenan por lo económico** (precio total y por renglón, con la cotización del Portal cuando la hay). El descarte y el orden son propuestas: decide la Comisión. | — |
| REQ-060 | Cuando el pliego exige un documento que no está en la oferta, el resultado es "no se encontró el documento", con la cita del pliego; no es "no cumple". La Comisión decide: puede pedir que se subsane y, si el oferente lo presenta, el documento se agrega a la oferta y ese requisito se vuelve a evaluar, con registro de todo el recorrido. | Subsanación prevista en el régimen; P3, P6 |

## Criterios de aceptación

- **REQ-052 y REQ-053.** Dado el caso-00 (tres ofertas con evaluación terminada por la Comisión), cuando el sistema propone, entonces su resultado coincide con el dictamen de la Comisión en **más del 80 %** de los requisitos que el dictamen trata, y **no lo contradice en ninguno** (0 casos de "cumple" donde la Comisión dijo "no cumple" o al revés): donde duda o no puede corroborar, propone "no determinado" citando lo que tiene. Ninguna propuesta de "cumple" o "no cumple" carece de cita literal de la oferta (100 %). Decisión del responsable, 2026-10-06.
- **REQ-054.** Dado el caso-00, el texto de la oferta que respalda cada propuesta está entre los fragmentos esperados de la ficha (lista de la 008) en al menos el 90 %.
- **REQ-055.** Dado un requisito que depende de un dato que no está en la oferta ni en la normativa, entonces el sistema formula una pregunta y el requisito queda "no determinado" hasta la respuesta.
- **REQ-056.** Dada una propuesta, cuando el evaluador la corrige, entonces queda la propuesta original, la corrección, el autor y la fecha.
- **REQ-059.** Dado el caso-00, cuando se pide la evaluación, entonces se evalúan las tres ofertas, la matriz de evaluación muestra el resultado de cada requisito por oferta, las descartadas aparecen con su motivo y las demás ordenadas por precio total, igual al orden del cuadro comparativo del Portal.
- **REQ-060.** Dada una oferta sin un documento exigido, entonces el resultado es "no se encontró el documento" con la cita del pliego; cuando se agrega el documento por subsanación, ese requisito se vuelve a evaluar y quedan registradas las dos evaluaciones.
- **REQ-057 y REQ-058.** Dada una evaluación armada con la versión 1 de la matriz, cuando se valida la versión 2, entonces se avisa; la pantalla de estado muestra las cuentas por estado y las preguntas abiertas.

## Requisitos no funcionales

- **Medición:** primero con un caso chico calcado de ofertas reales (ADR-0025) y después con el caso-00 contra el dictamen de la Comisión (`corpus/casos/caso-00/evaluacion/`). Umbral escrito en el plan; como máximo dos rondas.
- **Prueba a ciegas:** con el proceso en curso que reservó el responsable (hoja de ruta), cuando el producto esté más cerrado.
- **Tiempo:** se mide y se informa por oferta; sin máximo.
- **Funcionamiento:** todo el procesamiento en el equipo propio (P4).

## Fuera de alcance

- El compliance (005) como fundamento: se suma cuando exista.
- El circuito general de validación con la Comisión (009): la 004 trae solo el registro mínimo de preguntas y respuestas que necesita (hoja de ruta, "Alcance del piloto").
- La planilla por oferta, el cuadro comparativo y el acta (006).
- La comparación técnica renglón por renglón (010).

## Datos involucrados

Pliegos, ofertas y dictámenes de casos públicos, fuera del repositorio (P4); al repositorio solo identificadores y medidas.

## Preguntas abiertas

Ninguna. Respuestas del responsable (2026-10-06):

1. Coincidencia con el dictamen: más del 80 %, sin contradecirlo en ningún requisito; puede quedar en duda o sin corroborar, citando lo que tiene.
2. Evaluación de todas las ofertas a la vez, en una matriz de evaluación, descartando las que no cumplen requisitos formales o técnicos y ordenando lo económico (REQ-059).
3. Documento faltante: se informa "no se encontró el documento" y la Comisión decide; la evaluación admite la subsanación, por ejemplo adjuntando el documento (REQ-060).
