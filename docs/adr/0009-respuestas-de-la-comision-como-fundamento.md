# ADR-0009 · Las respuestas de la Comisión como fundamento

Estado: propuesto · Fecha: 2026-10-03 · Decidió: —

Enmienda de la constitución: P3, versión 1.1 → 1.2.

## Contexto

El sistema final le hace preguntas a la Comisión en dos momentos: al analizar el pliego (feature 002) y al evaluar las ofertas (feature 004). Pregunta lo que no puede resolver con la normativa, el pliego, la oferta o el compliance. Según el responsable, la Comisión responde cuando tiene el dato. Una pregunta puede quedar sin respuesta, aunque eso perjudique el resultado, y puede contestarse después.

P3 dice hoy: "Toda conclusión del sistema muestra su fundamento: el fragmento del pliego o de la oferta y la cita normativa que la sostiene. Si no hay fundamento recuperable, el resultado es 'no determinado'". Una respuesta de la Comisión no es un fragmento de documento ni una cita normativa, así que con el texto actual no podría sostener una conclusión.

## Alternativas

### A. No usar las respuestas como fundamento
Las respuestas solo orientan a la Comisión, y la conclusión queda "no determinado". Se gana no tocar P3. Se pierde el sentido de preguntar: el sistema no podría cerrar ningún punto con lo que la Comisión le contesta.

### B. Una respuesta registrada es un fundamento más, identificado como tal (recomendada)
Una respuesta de la Comisión puede sostener una conclusión si queda registrada con la pregunta, el texto de la respuesta, quién respondió y cuándo. La conclusión la muestra como fundamento de ese tipo, distinto de una cita a un documento.

Se gana usar lo que la Comisión sabe y que no está en los documentos. Se pierde la garantía de que todo fundamento sea un texto verificable en un documento: una respuesta es una afirmación de una persona.

### C. La respuesta tiene que adjuntar un documento
Toda respuesta trae un documento que la respalde, y el fundamento es ese documento. Se gana trazabilidad documental. Se pierde agilidad: muchas respuestas son datos que la Comisión conoce y no tiene escritos.

## Decisión

Propuesta: B. P3 quedaría así:

> **P3. El sistema recomienda, la Comisión decide.** Toda conclusión del sistema muestra su fundamento. El fundamento puede ser el fragmento del pliego o de la oferta y la cita normativa que la sostiene, o la respuesta de la Comisión a una pregunta del sistema, registrada con quién respondió y cuándo, y mostrada como tal. Si no hay fundamento recuperable, el resultado es "no determinado", nunca una afirmación. Una pregunta sin responder no es fundamento. La decisión final es siempre de una persona y queda registrada como tal.

## Consecuencias

- **Registro.** Las preguntas y las respuestas, con su autor y su momento, entran en el registro de auditoría (P6). Una respuesta posterior no altera una conclusión ya registrada: genera una nueva.
- **Interfaz.** La pantalla distingue el fundamento documental del fundamento por respuesta de la Comisión.
- **Specs 002 y 004.** Las dos lo usan. La feature 001 no cambia.
- **Para revertir.** Volver a P3 versión 1.1. Las conclusiones apoyadas en respuestas pasarían a "no determinado".
