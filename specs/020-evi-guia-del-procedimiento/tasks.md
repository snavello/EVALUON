# Tareas 020 · Evi

Plan: `specs/020-evi-guia-del-procedimiento/spec.md`, sección «Plan corto» (aprobado el 2026-11-18 por el responsable, «Cambia esto y da por aprobado todo»; ADR-0082)

Despliegue: pendiente

> El tablero (`docs/tablero.md`) se genera de este archivo. Al aprobarse el despliegue, la línea de arriba pasa a `Despliegue: aprobado AAAA-MM-DD`.

Estados: pendiente · en curso · en verificación · terminada · bloqueada

**Ritmo (carril liviano, ADR-0081).** Tareas grandes; cada desarrollador corre los tests de su área; una sola verificación y una sola suite completa, al cierre del lote. Las ramas de tarea no tocan este archivo ni el tablero. Prototipo de referencia: `docs/diseno/evi/index.html`.

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-367 | Evi fija: botón en todas las pantallas, circuito con «Usted está aquí», recorrido guiado, textos de los siete pasos y «Qué hacer acá» | REQ-163, REQ-164, REQ-165, REQ-166, REQ-167, REQ-168, REQ-169, REQ-170 | — | terminada |
| T-368 | «Pregúntele a Evi», experimental: preguntas respondidas por la IA local | REQ-171, REQ-172, REQ-173 | T-367 | terminada |

### T-367 · Evi fija

- **Requisitos:** REQ-163 a REQ-170.
- **Nivel:** liviana.
- **Qué hay que hacer:** llevar a la aplicación el prototipo `docs/diseno/evi/index.html` sin el bloque de preguntas: botón chico con el logo animado en toda pantalla con sesión; panel titulado «Evi», sin subtítulos ni pies; gráfico del circuito completo en cualquier ancho desde 360 px, con estados si hay procedimiento abierto; «Usted está aquí» sobre el o los pasos de la pantalla abierta; recorrido guiado y «Ver el circuito completo»; textos de los siete pasos y de los términos en un solo archivo; «Qué hacer acá» armado con el cálculo del proceso de la feature 018, con los mismos números que la portada. Solo lectura. Sin cambios de esquema.
- **Aviso de tareas anteriores:**
- **Verificación:** tests del área (`tests/journey`), con los tres procedimientos de prueba de la 018; medición en Chrome sin cabeza a 360, 1280 y 1440 px en los dos temas.
- **No tocar:** las reglas de estado y de acciones de la 018, la lógica de evaluación, `tasks.md`, el tablero, la spec.

### T-368 · «Pregúntele a Evi», experimental

- **Requisitos:** REQ-171, REQ-172, REQ-173.
- **Nivel:** liviana (excepción del responsable, ADR-0082).
- **Qué hay que hacer:** el bloque de preguntas al pie del panel, con el rótulo «Experimental» y el aviso en cada respuesta; un pedido a la IA local con instrucción propia de Evi, la guía y el estado del procedimiento como único contexto; ajuste para apagarlas; aviso si la IA no responde en 60 segundos o está ocupada; registro de usuario, fecha, pregunta y respuesta; test de que las instrucciones y versiones de la evaluación no cambian; diez preguntas de prueba (tres trampa) para correr una vez contra la IA local.
- **Aviso de tareas anteriores:**
- **Verificación:** tests del área con la IA simulada; las diez preguntas reales las corre el Coordinador al cierre, de a una, sin otra medición en curso.
- **No tocar:** instrucciones, recuperación y modelo de la evaluación; servicios externos; `tasks.md`, el tablero, la spec.
