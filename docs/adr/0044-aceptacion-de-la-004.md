# ADR-0044 · Aceptación de la 004 (evaluación asistida) con la medición de T-176

Estado: aceptado · Fecha: 2026-10-07 · Decidió: responsable del proyecto

## Contexto

La spec 004 fija, con la regla de medición de la enmienda del 2026-10-06 (decisiones literales, ADR-0043): más del 80 % de coincidencia con el dictamen de la Comisión en el caso-00, ninguna contradicción y el 100 % de las citas literales. La medición final (T-176, `specs/004-evaluacion-asistida/verificacion/T-176.md`) dio 42 de 49 (85,7 %), 0 contradicciones, 38 de 38 citas literales de la oferta y 45 de 45 del Portal.

## Decisión

1. La 004 cumple su criterio de aceptación y pasa a la auditoría de funcionamiento (ADR-0036) y al despliegue.
2. Siguen el modelo de generación de 12B y la lectura con visión con ese modelo (T-177). La lectura de manuscritos con el modelo de 26B (que en la prueba del 2026-10-07 leyó el pagaré casi sin errores) queda para la revisión con el primer producto: hoy no entra junto con el 12B en la memoria de video.
3. Lo que no llegó pasa, con su impacto, a "Revisión con el primer producto" de `specs/004-evaluacion-asistida/tasks.md`.
4. REQ-054 (fragmentos de la ficha) midió 81 % contra el 90 % de su criterio: se difiere a la revisión con el primer producto, con su impacto anotado (señalado por la auditoría de funcionamiento, 2026-10-07).

## Consecuencias

- Una página manuscrita leída por visión puede traer datos distintos del original; el sistema no concluye "cumple" sobre esos datos sin respaldo y la Comisión ve la imagen junto a la cita (P3).
- La prueba a ciegas con el proceso reservado mide la 004 con un caso que nadie ajustó.
