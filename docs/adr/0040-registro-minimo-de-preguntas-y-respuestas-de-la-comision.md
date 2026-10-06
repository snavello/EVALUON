# ADR-0040 · Registro mínimo de preguntas y respuestas de la Comisión dentro de la 004

Estado: aceptado · Fecha: 2026-10-06 · Decidió: responsable del proyecto

## Contexto

El ADR-0009 deja que una respuesta de la Comisión, registrada con quién respondió y cuándo, sea fundamento de una conclusión; una pregunta sin responder no lo es. La hoja de ruta ("Alcance del piloto") dice que si la 004 necesita ese registro antes de la 009, se hace una versión mínima dentro de la 004. La spec (REQ-055, REQ-056) pide que el sistema formule preguntas concretas, que el evaluador las responda o las deje sin responder, y que una respuesta pueda servir de fundamento en otros requisitos. El circuito general de validación con la Comisión (009) está fuera de alcance (ADR-0016).

Un dato que hay que decidir: a qué se aplica una respuesta. "La garantía es una póliza validada por la SSN" vale para una oferta; "el art. 55 inc. h se aplica así en esta licitación" vale para todas.

## Alternativas

### A. Esperar a la 009

Se gana: un solo diseño. Se pierde: REQ-055 y REQ-056 no se cumplen en la 004; el piloto necesita la 004 antes.

### B. Dos tablas mínimas propias de la 004, con alcance elegido por quien responde (elegida)

`assessment_question` (procedimiento, requisito, oferta, texto, motivo, resultado de origen) y `assessment_answer` (pregunta, texto, alcance, quién, cuándo), de solo inserción. Alcance: `par` (solo esa oferta y ese requisito), `requisito` (todas las ofertas de ese requisito) o `procedimiento` (cualquier requisito del procedimiento). Una respuesta nueva a la misma pregunta reemplaza a la anterior como vigente; la anterior queda. Una pregunta sin respuesta no se manda al modelo como fundamento. Al evaluar un par, el sistema le da al modelo las respuestas vigentes que le aplican (hasta 20; si hay más, el reranker elige) y las muestra como fundamento "respuesta de la Comisión" con quién y cuándo. Responder no cambia lo ya evaluado: ofrece "evaluar de nuevo" ese par (ADR-0009, "una respuesta posterior genera una conclusión nueva").

Se gana: REQ-055 y REQ-056 sin esperar; el modelo no necesita nada de la 009. Se pierde: la 009 tendrá que absorber estas tablas (migración de datos, no de comportamiento) cuando defina el circuito general.

### C. Un módulo común `commission` pensado ya para la 002, la 004 y la 009

Se gana: una sola vez. Se pierde: diseñar para requisitos que todavía no existen (002 y 009 sin spec); contra P10.

## Decisión

Se propone B. Se agrega el alcance porque la spec pide que una respuesta sirva de fundamento en otros requisitos; el alcance por omisión es `requisito`. Solo un evaluador responde (decide la Comisión, P3). Las preguntas que el sistema formula las crea la evaluación cuando el resultado es "no determinado" por falta de un dato que no está en la oferta, la normativa ni lo ya respondido.

## Consecuencias

- Más fácil: la respuesta de la Comisión entra como fundamento sin tocar la constitución (ya enmendada por el ADR-0009).
- Más difícil: el sistema no sabe si una respuesta de alcance amplio es pertinente a un requisito en el que nadie pensó; lo decide el modelo con la respuesta a la vista, y el resultado siempre muestra qué respuesta usó.
- Para revertir: quitar las dos tablas y el bloque "respuestas" del pedido al modelo; las preguntas pasarían a leerse del texto de la explicación.
- Al hacerse la 009, se decide si estas tablas pasan a ser las del circuito general o se migran.
