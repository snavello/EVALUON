# ADR-0082 · «Pregúntele a Evi» va por el carril liviano, como función experimental

Estado: aceptado · Fecha: 2026-11-18 · Decidió: responsable del proyecto («dije que lo ponemos por carril rapido y aclaramos que es experimental porque no quiero invertir ahora en ese desarrollo tanto tiempo, en esta instancia no tiene riesgos las equivocaciones»)

## Contexto

La feature 020 (Evi) suma un cuadro de preguntas que responde la IA local. El ADR-0081 dice que lo que toca instrucciones al modelo va por el carril completo, y el principio P7 que ningún cambio en recuperación, instrucciones o modelo se acepta sin correr el conjunto dorado. El Coordinador propuso hacerlo en una segunda entrega por carril completo. El responsable decidió que entre ahora, por el carril liviano y rotulado «Experimental».

## Decisión

1. Las preguntas a Evi se desarrollan por el carril liviano, dentro de la feature 020.
2. Se muestran siempre con el rótulo «Experimental» y cada respuesta avisa que puede equivocarse y no reemplaza al pliego ni a la decisión de la Comisión.
3. Evi explica qué completar y qué opciones hay; nunca decide ni recomienda (P3). Es lo único que se comprueba como condición: tres preguntas trampa, tres respuestas sin decisión.
4. Quedan aisladas de la evaluación: instrucción propia, sin tocar la recuperación, las instrucciones ni el modelo con que se evalúan las ofertas. Un test comprueba que las instrucciones y versiones de la evaluación no cambian. Por eso el conjunto dorado, que mide la evaluación, no se vuelve a correr por esta feature: nada de lo que mide cambia (P7).
5. Solo IA local (P4, P5), un ajuste para apagarlas y registro de cada pregunta y respuesta.
6. Si las preguntas pasan a usarse para decidir, o a leer pliegos, ofertas o normativa, dejan de ser experimentales: ese cambio va por el carril completo, con su conjunto de medición.

## Alternativas

- **Segunda entrega por carril completo** (recomendación del Coordinador): más rigor y una medición propia antes de habilitar; más tiempo. Descartada por el responsable para esta instancia.
- **No hacerlas:** se pierde saber si sirven.

## Consecuencias

- Una respuesta puede ser incorrecta sin que ninguna medición lo haya detectado antes. Es el costo aceptado; el rótulo y el aviso lo dicen.
- La calidad de las respuestas se conoce solo por diez preguntas de prueba, corridas una vez, y por el registro de uso.
- Las preguntas comparten la IA local con la evaluación: mientras se evalúa pueden tardar o no responder.
