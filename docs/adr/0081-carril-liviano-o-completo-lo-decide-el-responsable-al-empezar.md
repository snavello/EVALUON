# ADR-0081 · Carril liviano o completo: lo decide el responsable al empezar cada desarrollo

Estado: aceptado · Fecha: 2026-11-18 · Decidió: responsable del proyecto («Y que quede por adr preguntarme con opciones y opinión si se hace en próximos desarrollo carril liviano o full.»)

## Contexto

La feature 018 («El proceso a la vista») solo cambia cómo se muestra el procedimiento: no toca la matriz, la evaluación ni los datos. Aun así se hizo con el flujo completo: 16 requisitos, un plan de más de 400 líneas, 3 ADR, 24 tareas y unos 20 pull requests para unos seis archivos de código nuevos. Cada tarea tuvo un desarrollador y un verificador con verificación plena, alteraciones a propósito del código para buscar tests faltantes, y dos corridas de unos 17 minutos. El mapa del proceso se rehízo tres veces porque se especificó en píxeles antes de verlo en pantalla.

El 2026-11-18 el responsable dijo: «Este proyecto hecho con driven spec devs me está resultando excesivamente más lento incluso en desarrollos menores, que otros proyectos hecho con planificación y desarrollo común. Estamos haciendo algo mal? No lo voy a cambiar ahora, Pero creo que no se justifica, evalúa y opina.» La evaluación del Coordinador fue que el rigor completo se justifica donde un error produce un dictamen equivocado, y no en la exposición ni en los cambios menores; estimó, sin medición, que la 018 fue entre 3 y 5 veces más lenta que con planificación común. El responsable respondió «Si pasemos a nivel liviano» para lo que faltaba de la 018 y pidió dejar la regla por ADR.

El ADR-0025 ya permitía verificación liviana por tarea, pero la elegía el Coordinador y, ante la duda, mandaba la plena. No había una decisión por desarrollo ni un carril liviano para el flujo entero.

## Decisión

1. **La pregunta.** Antes de empezar cada desarrollo nuevo (una feature, una enmienda o un cambio pedido por el responsable), el Coordinador le pregunta al responsable por cuál carril va. La pregunta trae las dos opciones, qué se gana y qué se pierde con cada una en ese desarrollo concreto, y la recomendación del Coordinador con su motivo. Es una sola pregunta, con un ejemplo real y en lenguaje llano. El Coordinador no elige el carril por su cuenta.
2. **Carril completo.** El flujo de siempre: spec, plan, tareas, desarrollo, verificación por tarea, auditoría y despliegue, con sus compuertas. Verificación plena en lo que toque lógica, datos, esquema, instrucciones al modelo o un principio de la constitución.
3. **Carril liviano.** Para exposición, interfaz y cambios menores que no tocan esos ámbitos:
   - Spec corta (una página): qué se necesita, para quién y cómo se sabe que está. Los requisitos siguen teniendo su `REQ-NNN` y su test (P1 y P2 no cambian).
   - En interfaz, primero un prototipo que se ve en pantalla; las medidas y la disposición se fijan después de que el responsable lo vio.
   - Plan corto dentro de la misma spec, sin ADR salvo que haya una decisión que cueste revertir.
   - Tareas grandes: una por pantalla o por cambio, no por archivo.
   - Los desarrolladores corren los tests de su área. Una sola verificación y una sola suite completa, al cierre del lote. Sin rondas de alteraciones a propósito.
   - Un pull request por lote.
4. **Lo que no cambia en ningún carril.** Las compuertas del responsable (spec, plan y despliegue, P11), el registro de sus decisiones literales, que no se sube material reservado (P4) y que las evals corren ante cualquier cambio de recuperación, instrucciones o modelo (P7).
5. **Cambio de carril a mitad de camino.** Si un desarrollo que iba por el carril liviano termina tocando lógica de evaluación, datos, esquema, instrucciones al modelo o seguridad, el Coordinador frena, lo dice y vuelve a preguntar. Esa parte va por el carril completo.
6. **Recomendación por defecto del Coordinador.** Liviano para exposición y cambios menores; completo para el núcleo de evaluación. Es una recomendación: decide el responsable.

## Alternativas

- **Seguir con el flujo completo para todo.** Se conserva la trazabilidad fina en todos lados, al costo que mostró la 018.
- **Que el Coordinador elija el carril.** Es más rápido, pero es justo lo que falló: con «ante la duda, plena» se eligió el nivel pesado hasta para definir colores.
- **Carril liviano para todo.** Más rápido, pero se pierde la red donde un error termina en un dictamen equivocado.

## Consecuencias

- `CLAUDE.md` suma la pregunta al modo construcción y la descripción de los dos carriles.
- Enmienda al ADR-0025, punto 2: el nivel de verificación de un desarrollo sale del carril que eligió el responsable; dentro del carril completo, el Coordinador sigue indicando plena o liviana por tarea.
- En el carril liviano un defecto puede aparecer recién al cierre del lote y no tarea por tarea. Es el costo aceptado para exposición y cambios menores.
- Se pierde trazabilidad fina por tarea en la interfaz; el tablero muestra el lote.
- Lo que falta de la 018 (filtros del cuadro, inicio, vocabulario y cierre) ya va por el carril liviano, por decisión del responsable del 2026-11-18.
