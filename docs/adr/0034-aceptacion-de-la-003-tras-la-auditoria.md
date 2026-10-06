# ADR-0034 · Criterios de aceptación de la 003 después de la auditoría

Estado: aceptado · Fecha: 2026-10-05 · Decidió: responsable del proyecto

## Contexto

La auditoría de la 003 (`docs/auditorias/003-dictamen.md`, rama `003-auditoria`) rechazó la feature: el ADR-0024 aflojó solo el tope de sobrantes, pero la spec seguía exigiendo que cada fila de circular cumpla los cuatro puntos (a ciegas: 3 de 10 en el caso-03, 1 de 4 en el caso-04) y el 100 % de requisitos encontrados (62 de 65 en el caso-03, con los tres faltantes presentes en otras filas). Además, la fila #183 del caso-03 muestra "UN peso" como vigente sin aviso, un hecho falso (P3).

## Decisión

1. La fila #183 se corrige en una tarea puntual (T-147). Es la ronda adicional que el ADR-0025 admite cuando se viola un principio.
2. Criterio de aceptación de REQ-031: lo que bloquea es que ningún cambio de una circular llegue como hecho sin aviso en la fila que cambia (muestra el cambio con su cita o queda "A revisión obligatoria"). Los cuatro puntos exactos se miden e informan sin bloquear; sus imprecisiones van a la revisión con el primer producto.
3. Requisitos encontrados: cuenta como encontrado el requisito cuyo contenido está en otra fila de la matriz; la medición lo informa aparte.

## Alternativas

- Seguir con rondas hasta cumplir los cuatro puntos: contradice el ADR-0025 y demora la 008, la 012 y la 004.
- Desplegar sin cambiar la spec: no pasa la auditoría.

## Consecuencias

- La spec de la 003 se enmienda en REQ-031 y en "Requisitos encontrados".
- La medición (`evaluation.py`) debe informar el cumplimiento de P3 por fila de circular y los encontrados en otra fila (T-147).
- Después de T-147 se repite la auditoría.
