# ADR-0039 · Módulo de evaluación propio: resultados inmutables, decisiones aparte y recorrido por par

Estado: aceptado · Fecha: 2026-10-06 · Decidió: responsable del proyecto

## Contexto

La 004 guarda, por cada oferta y cada requisito, lo que el sistema propone (resultado, citas, fundamentos), lo que la Comisión decide (confirmar, corregir, rechazar), las preguntas y sus respuestas, y el recorrido de una subsanación (documento faltante, pedido, documento agregado, nueva evaluación). Es esquema nuevo y difícil de revertir con datos cargados. Debe poder reconstruirse por qué el sistema dijo lo que dijo (P6) y qué decidió una persona sobre cada propuesta; una respuesta posterior o un documento agregado generan una evaluación nueva sin alterar la anterior (ADR-0009, REQ-060).

La ficha de la 008 (`offers_sheet_entry`) ya tiene una fila por requisito de una oferta, pero por contrato no emite juicio (REQ-041: ni "cumple" ni "no cumple") y sus estados (propuesto, confirmado) son los de un fragmento hallado, no los de una decisión de evaluación.

## Alternativas

### A. Extender la ficha de la 008 con campos de resultado y decisión

Se gana: una sola fila por par. Se pierde: la ficha y la evaluación quedarían mezcladas; habría que aflojar restricciones y pruebas de la 008 (síntesis sin juicio, estados) ya verificadas, y una re-evaluación de un requisito no tendría dónde vivir sin pisar la ficha.

### B. Módulo `evaluon/assessment/` con tablas propias (elegida)

Tablas `assessment_*`: pedido, evaluación (una por oferta y pedido, con modelos, parámetros e instrucciones), resultado (uno por par y evaluación), cita, pedido al modelo, decisión, pregunta y respuesta. Los resultados, las citas, los pedidos al modelo, las decisiones, las preguntas y las respuestas son de solo inserción (triggers de la base, como en la 003 y la 008). El resultado vigente de un par es el más reciente; la decisión vigente es la última sobre ese resultado. `assessment` usa `tenders` (matriz, requisito, cola) y `offers` (oferta, documento, lectura) y `portal` (cotización, solo lectura); nunca al revés. La cola de la 003 se comparte (un tipo de pedido nuevo con `target_id`, como en ADR-0026).

Se gana: la 003 y la 008 no se tocan salvo un valor de tipo de pedido y los tipos de hecho de auditoría; re-evaluar un par es insertar un resultado nuevo y el recorrido queda completo. Se pierde: ocho tablas; `target_id` sin clave foránea (se controla en la función de negocio, como ADR-0026); el estado actual de un par se calcula (último resultado, última decisión) en lugar de leerse de un campo.

### C. Guardar toda la evaluación como un documento JSON por oferta

Se gana: una tabla. Se pierde: no se puede consultar la matriz ni el estado por oferta sin leer todos los documentos, ni hacer valer integridad (FK a requisito, documento y usuario), ni proteger con triggers cada decisión.

## Decisión

Se propone B. Todo el esquema, los triggers, el tipo de pedido `evaluate_offers` y los tipos de hecho de auditoría los crea una sola tarea (T-148); ninguna otra lo toca. Un cambio posterior de esquema se encadena después de la tarea que lo tocó.

## Consecuencias

- Más fácil: P6 y P3 por construcción (nada se pisa; cada decisión tiene autor y fecha); subsanación, respuesta de la Comisión y nueva versión de la matriz usan la misma operación: evaluar de nuevo un par.
- Más difícil: la pantalla y la medición calculan el "vigente"; hay que cuidar que sea siempre el mismo cálculo (una función única).
- Para revertir: quitar la aplicación `assessment`, su migración y el valor de `JobKind`. Las demás features no dependen de ella.
