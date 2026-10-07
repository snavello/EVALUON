# Dictamen de auditoría · Feature 004 (Evaluación asistida de ofertas)

Fecha: 2026-10-07 · Auditor: agente `auditor` (sin conocer el proceso) · Alcance: `specs/004-evaluacion-asistida/`, commits `1ef794b..eed328d` (incluyen código de la 012 y de ofertas usado por la 004). Auditoría de funcionamiento (ADR-0036).

Texto devuelto por el auditor y registrado por el Coordinador (el auditor trabaja en solo lectura).

## Resultado

**Aprobado con observaciones.** Sin hallazgos que impidan funcionar o expongan datos.

## Hallazgos no bloqueantes

1. **Menor (P3, P7).** REQ-054 (fragmentos de la ficha) midió 81 % (17 de 21) contra el 90 % de su criterio, sin excepción escrita. Atendido por el Coordinador: se difiere a la revisión con el primer producto (ADR-0044, punto 4, y `tasks.md`).
2. **Menor (P3).** En el pagaré manuscrito, la cita es literal contra la transcripción y no contra la imagen (la transcripción del 12B altera dígitos). Ningún par del pagaré quedó en "cumple"; la pantalla rotula el origen y muestra la imagen. Evaluar el 26B para manuscritos con el primer producto (ADR-0044).
3. **Menor (P5).** La base viva no tiene aplicadas las migraciones nuevas de `assessment`; el servicio `migrate` se niega a migrar sin respaldo, como está diseñado. Se aplican con el runbook de despliegue.
4. **Para la auditoría de cumplimiento.** T-159 y T-170 figuraban "pendiente" en `tasks.md` (se perdió el estado en una integración): corregido por el Coordinador. `verificacion/T-176.md` registra el commit medido sin que el medidor recibiera `--commit`.

## Controlado y correcto

- Suite completa en el código del rango: 2896 pasan, sin tests salteados ni fallidos; sin `skip` ni `xfail` agregados en el rango.
- Medición T-176 (leída): 42 de 49 (85,7 %), 0 contradicciones, citas literales de la oferta 38 de 38 y del Portal 45 de 45, descarte 2 de 2.
- P3: sin cita ubicada o sin confirmación del contraste, el resultado baja a "no determinado"; existen los cuatro resultados y las preguntas a la Comisión.
- P4: sin servicios externos en `assessment` ni `offers` (solo el motor interno); datos de prueba sintéticos; `corpus/casos` fuera del repositorio; el registro de T-176 usa solo identificadores y cuentas.
- Matriz, descarte, orden económico, revisión con historial, preguntas y subsanación implementados y con tests.

## No verificado

La medición del caso-00 (necesita el caso local y la GPU); las pantallas con navegador; un barrido de secretos de todo el historial.
