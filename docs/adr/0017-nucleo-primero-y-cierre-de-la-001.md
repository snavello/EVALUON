# ADR-0017 · El núcleo primero y cierre acotado de la 001

Estado: aceptado · Fecha: 2026-10-03 · Decidió: responsable del proyecto

## Contexto

La feature 001 dedicó mucho tiempo a medir respuestas en texto libre: datos clave, variantes, redacciones equivalentes y casos de remisión (ADR-0011, ADR-0014 y ADR-0015). El responsable señaló que se está perdiendo demasiado tiempo en la semántica de las preguntas y de la normativa. El sistema se basa en otra cosa: leer una oferta y verificar que cumpla con los requisitos de un pliego cargado previamente, y que el pliego cumpla con la normativa.

Ese núcleo produce una salida estructurada (cumple, no cumple o no determinado, con su cita), y esa salida se mide comparando valores de una lista cerrada, sin discutir la redacción (ADR-0014, punto 7).

## Decisión

1. **Cierre acotado de la 001.** Solo falta T-047 (consulta sin red), T-048 (respaldo y restauración) y T-049 (levantar desde cero), y después la auditoría y el despliegue. En la 001 no se agregan preguntas ni se ajustan redacciones. Lo pendiente queda anotado para la 009:
   - la medición de REQ-018 y REQ-019 con normas reales (T-066, bloqueada);
   - las respuestas incompletas (EV-006, EV-009 y EV-017);
   - EV-044;
   - la confirmación de la Comisión.
2. **Hoja de ruta reordenada.** El orden pasa a ser 001 → 003 → 008 → 004 → 005 → 009 → 002 → 006 → 007.
   - La 004 deja de depender de la 005: el compliance se suma como fundamento cuando esté.
   - El piloto necesita la 001, la 003, la 008, la 004 y la 007; la 005 y la 009 lo completan.
   - Si la 004 necesita registrar respuestas de la Comisión como fundamento (ADR-0009) antes de la 009, se hace una versión mínima de ese registro dentro de la 004.

## Consecuencias

- Se llega antes a lo que la Comisión va a usar: pliego, ofertas y evaluación.
- La 009 se demora. La revisión de la Comisión del conjunto de preguntas (ADR-0015) espera hasta entonces.
- Las evals de la 003, la 008 y la 004 se diseñan desde la spec con salida estructurada (ADR-0014, punto 7).
- Para revertirla, se vuelve al orden del ADR-0016.
