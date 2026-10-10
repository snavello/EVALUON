# ADR-0036 · Auditoría de funcionamiento por feature y de cumplimiento al final

Estado: aceptado, reemplazado en parte por ADR-0052 · Fecha: 2026-10-05 · Decidió: responsable del proyecto

## Contexto

La auditoría completa de cada feature (trazabilidad, cumplimiento de la constitución, registro de tareas, datos, seguridad) toma mucho tiempo: la de la 003 necesitó dos vueltas, y buena parte de los hallazgos eran formales (estados de tareas, registros faltantes, redacción de criterios) y no de funcionamiento. El responsable prioriza llegar al primer producto completo (ADR-0024, ADR-0025).

## Decisión

1. **Auditoría por feature (etapa 6), solo de buen funcionamiento:** el auditor revisa si la feature hace lo que la spec pide y lo hace bien: requisitos cumplidos según sus criterios de aceptación y las mediciones, que nada se presente como hecho sin respaldo (P3), defectos de lógica o de datos, la suite en verde, el entorno que se levanta, y riesgos de seguridad o de datos reales en el repositorio (P4), que no pueden esperar. Bloquea solo lo que impide funcionar o expone datos.
2. **Auditoría de cumplimiento, una sola vez, antes del piloto:** trazabilidad completa (P2), registro de tareas y de verificaciones, cumplimiento formal de la constitución, ADR, historial de secretos, coherencia de la documentación, para todas las features juntas.
3. Los hallazgos formales que aparezcan antes se anotan en la lista de revisión con el primer producto y no bloquean.

## Alternativas

- Seguir con la auditoría completa por feature: más trazabilidad en cada paso, a costa de tiempo y de vueltas por cuestiones formales.

## Consecuencias

- `CLAUDE.md` y la definición del agente `auditor` cambian en ese sentido.
- La hoja de ruta suma, antes del piloto, la auditoría de cumplimiento.
