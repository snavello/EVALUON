# ADR-0015 · Remisión a una norma no cargada y visto bueno del conjunto en el piloto

Estado: aceptado · Fecha: 2026-10-03 · Decidió: responsable del proyecto

## Contexto

Antes de T-046 quedaban dos decisiones pendientes, abiertas por el ADR-0014: la decisión 7 y la decisión 8 del plan.

**A. Remisión a una norma no cargada.** Tres casos del conjunto (EV-027, EV-028 y EV-029) preguntan por algo que la norma cargada trata, pero cuyo contenido remite a otra norma que no está cargada:
- el monto de la contratación directa o de la licitación privada remite al "Régimen Jurisdiccional vigente";
- la integración de la Comisión Evaluadora queda "sujeta a la normativa vigente".

Hasta ahora se esperaba "no determinado". En la corrida de T-045 el sistema se abstuvo en EV-027 y EV-029. En EV-028 respondió lo que dice el art. 50 del anexo de la 247/2022, con su cita, y eso se contó como falla.

**B. Visto bueno del conjunto de preguntas.** La spec pide el visto bueno de un integrante de la Comisión para que una pregunta entre al conjunto. Hoy los casos tienen el visto bueno provisorio del responsable, y el lote de aceptación de T-061 necesita uno.

## Decisión

**A.** El responsable decidió que, cuando la norma cargada trata el tema y remite a otra norma no cargada, la respuesta dice lo que establece la norma cargada, con su cita, e indica a qué norma remite. Nunca afirma el contenido de la norma no cargada: no da cifras ni la integración que no están cargadas. "No determinado" queda para los temas que ninguna norma cargada trata. Se enmienda REQ-009.

Al mostrarle los ejemplos, el responsable aprobó como válida la respuesta de EV-028, y pidió el mismo comportamiento para las preguntas de monto: decir que la norma remite al régimen jurisdiccional vigente, con su cita.

**B.** Para el piloto alcanza el visto bueno del responsable del proyecto. La revisión de la Comisión queda pendiente y se hace antes de usar el sistema fuera del piloto. Se enmienda "Validación del conjunto de preguntas" en la spec.

## Consecuencias

- EV-027, EV-028 y EV-029 pasan a ser preguntas con respuesta. Su respuesta esperada es lo que dice la norma cargada más la remisión, con la cita. Un dato clave controla la remisión. Una respuesta que dé la cifra o la integración no cargada es incorrecta.
- Las instrucciones del modelo pueden necesitar un ajuste para que responda la remisión en lugar de abstenerse. Ese ajuste es un cambio de instrucciones y se mide con el conjunto dorado (P7).
- En el lote de aceptación de T-061, las preguntas sin respuesta son de temas que ninguna norma cargada trata, y se suman preguntas de remisión como preguntas con respuesta.
- La Comisión tiene pendiente revisar el conjunto antes de que el sistema se use fuera del piloto.
