# ADR-0025 · Rondas de ajuste con umbral previo, verificación proporcional al riesgo y estado por lote

Estado: aceptado · Fecha: 2026-10-05 · Decidió: responsable del proyecto (puntos 1 y 2); Coordinador (puntos 3 a 5), a propuesta del asesor de metodología (ADR-0013)

## Contexto

La feature 003 encadenó, solo entre el 2026-10-04 y el 2026-10-05, cinco diagnósticos, tres rondas de ajuste y cuatro tareas nuevas (T-126 a T-129) sobre un mismo requisito (REQ-031). Cada medición real cuesta de 30 a 75 minutos de GPU. En los últimos 150 commits, 83 son de gestión y 32 son merges, con conflictos repetidos en `tasks.md` y `docs/tablero.md`, porque cada rama los edita. Una vez se lanzaron dos mediciones a la vez y hubo que repetir una. La verificación independiente encontró defectos reales: tres tareas volvieron a desarrollo.

## Decisión

1. **Umbral previo y dos rondas como máximo (responsable).** Toda tarea de medición escribe antes su umbral de aceptación y tiene como máximo dos rondas de ajuste. Lo que no llegue al umbral se registra con su impacto y pasa a la lista de revisión con el primer producto (ADR-0024). Una ronda más solo procede si el faltante hace perder un requisito o viola un principio de la constitución.
2. **Verificación en dos niveles (responsable).** Enmienda al ADR-0014:
   - **Plena:** cambios de lógica, de datos, de esquema, de instrucciones al modelo, y todo lo que toque un principio de la constitución. Se mantiene igual.
   - **Liviana:** cambios acotados, con un test que falla antes y pasa después, sin tocar esos ámbitos. El testeador revisa el diff y los tests del área y deja un registro corto en `verificacion/T-NNN.md`. La suite completa corre una vez, al cierre del lote.
   - El Coordinador indica el nivel en el encargo. Ante la duda, se usa el nivel pleno.
3. **Correcciones agrupadas (Coordinador).** Los hallazgos de una misma medición van en una sola tarea de corrección, con un commit por hallazgo, y se mide una vez al cerrar el lote. Las mediciones largas van en cola, de a una, y la medición tiene un bloqueo que impide lanzar dos a la vez (tarea aparte).
4. **Estado fuera de las ramas de tarea (Coordinador).** Las ramas de tarea no tocan `tasks.md` ni el tablero. El Coordinador actualiza los estados y regenera el tablero una vez por lote, en su propia rama de gestión. La trazabilidad por tarea queda en el commit de código y en `verificacion/T-NNN.md`. `tools/cerrar.sh` se ajusta en consecuencia (tarea aparte).
5. **Features nuevas desde un caso chico (Coordinador).** La spec trae su criterio de aceptación con número y con el caso que lo mide. El plan empieza por un corte vertical completo con un caso chico y público (por ejemplo, una oferta y tres requisitos). Los casos reales se miden después de que pase el chico.

## Alternativas

- **Seguir igual:** se conserva toda la trazabilidad por tarea, pero se pierden 6 a 10 horas de GPU y agentes por feature, y siguen los conflictos de gestión.
- **Bajar la verificación para todo:** más rápido, pero se pierden los defectos que hoy se encuentran en la lógica. Por eso la verificación liviana es solo para cambios acotados.

## Consecuencias

- `CLAUDE.md` se actualiza en la sección de registro y cierre.
- Hacen falta dos tareas de herramientas: el bloqueo de mediciones simultáneas y el ajuste de `cerrar.sh` al estado por lote.
- Se pierde algo de trazabilidad por tarea en `tasks.md` entre lotes. El tablero se actualiza por lote, no por tarea.
