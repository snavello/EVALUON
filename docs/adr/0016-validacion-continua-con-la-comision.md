# ADR-0016 · Validación continua con la Comisión (feature 009)

Estado: aceptado · Fecha: 2026-10-03 · Decidió: responsable del proyecto

## Contexto

El responsable propuso una funcionalidad para que, junto con la Comisión, se puedan responder y validar las preguntas, registrar las respuestas y, cuando haga falta, agregar documentación o normas. La pensó como una forma de "reentrenamiento continuo" para las cuestiones que quedan sin validar o pendientes. Se usaría mucho al principio y después, con menos intensidad, cada vez que surja algo que no se sabe cómo resolver.

Lo que ya estaba decidido:
- las respuestas de la Comisión pueden ser fundamento (ADR-0009);
- el análisis del pliego (002) y la evaluación (004) le hacen preguntas a la Comisión;
- el conjunto de preguntas de evaluación queda pendiente de la revisión de la Comisión antes de usar el sistema fuera del piloto (ADR-0015).

## Alternativas

### A. Feature propia y temprana (elegida)
Un circuito único, inmediatamente después de la 001, que después reutilizan la 002 y la 004. Resuelve desde el principio la revisión pendiente de la Comisión, deja todo registrado y está disponible en el momento de uso más intensivo. A cambio, suma una feature antes de la 003.

### B. Dentro de la 002 y la 004
Es menos trabajo ahora. A cambio, las consultas de normativa quedan sin circuito de validación y cada feature arma el suyo.

### C. Después del piloto
La Comisión validaría fuera del sistema y sin registro, justo cuando más se la necesita.

## Decisión

A. Se agrega a la hoja de ruta la feature 009, "Validación continua con la Comisión", que depende de la 001, va antes de la 003 y forma parte del piloto.

"Reentrenamiento" no quiere decir reentrenar los modelos de IA, que no cambian. Lo que crece es el conocimiento validado. Cada cuestión resuelta puede terminar de tres maneras:
1. como **fundamento**: una respuesta registrada con quién respondió y cuándo (ADR-0009);
2. como **caso para medir** al sistema (conjunto dorado);
3. como **pedido de carga** de una norma o un documento, que se valida como cualquier otra carga (001).

## Consecuencias

- La spec de la 009 se escribe con el responsable al cerrar la 001.
- La spec tiene que separar lo que se usa como fundamento de lo que se usa para medir: un caso de medición no puede ser a la vez material que el sistema consulta para responderlo (ADR-0014).
- La 002 y la 004 usan este circuito para sus preguntas a la Comisión, en lugar de armar uno propio.
- La revisión de la Comisión pendiente por el ADR-0015 se hace con esta feature.
