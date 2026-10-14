# ADR-0060 · Material reservado del piloto visible para los agentes durante la estabilización (enmienda de P4)

Estado: aceptado · Fecha: 2026-10-14 · Propuso: Coordinador, por la decisión del responsable del 2026-10-14 · Decidió: responsable del proyecto (2026-10-14, «todo si.»)

## Contexto

El piloto de evaluación guiada va a cargar también el proceso en curso, cuyas ofertas son reservadas hasta el dictamen (spec 007, decisión del 2026-10-14). P4 de la constitución (versión 1.4) dice:

- **Fase de construcción:** «No se incorpora material reservado al repositorio, a las pruebas ni a las conversaciones con agentes».
- **Fase de operación:** «los pliegos y las ofertas se procesan solo con IA local».

Los agentes que construyen EVALUON, el Coordinador incluido, corren en un servicio de IA en la nube. Si leen las pantallas, la base o los registros de la instancia del piloto, el material reservado sale del equipo.

El responsable decidió el 2026-10-14 que, mientras se estabiliza el piloto, los agentes puedan ver todo: «7 todavia podes ver estamos estabilizando», y ante la advertencia de que eso requiere enmendar P4, eligió «Cargarlo ya y que lo vea todo». Sin agentes que vean lo que pasa con un proceso real, corregir los defectos del piloto queda en manos de una sola persona.

## Decisión

1. **Excepción acotada a P4.** Durante la estabilización del piloto, los agentes de construcción pueden leer el material del proceso en curso cargado en la instancia del piloto (pantallas, base, registros y archivos), para diagnosticar y corregir defectos.
2. **Lo que no cambia:**
   - El material reservado nunca va al repositorio, que es público, ni a las pruebas, a las listas esperadas, al corpus de casos ni a los ejemplos de las instrucciones al modelo.
   - Las mediciones y los registros de verificación que van al repositorio llevan solo cifras, claves y estados, sin textos del proceso (como hoy, P4).
   - Los pliegos y las ofertas siguen procesándose solo con la IA local de EVALUON.
   - Los agentes no copian el material fuera del equipo, salvo lo que la lectura misma envía a su servicio en la nube.
3. **Fin de la excepción.** La estabilización termina cuando el responsable lo dice. Desde ese momento rige REQ-117 completo: los agentes no acceden a la instancia del piloto ni a sus respaldos.
4. **Constitución 1.5.** P4 suma, en la fase de operación: «Excepción (ADR-0060): durante la estabilización del piloto, los agentes de construcción pueden leer el material del proceso en curso en la instancia del piloto. Nunca va al repositorio ni a las pruebas.»

## Alternativas

- **Estabilizar con procesos públicos y cargar el proceso en curso al terminar.** No toca P4. Se pierde que los agentes vean los defectos que solo aparecen con un proceso real en curso.
- **Cargarlo ya y que los agentes vean solo cifras y estados.** No toca P4. Se pierde el diagnóstico con texto: un defecto de lectura o de cita no se entiende sin ver el documento.
- **Cargarlo ya y que lo vean todo (esta).** Se gana el diagnóstico completo. Se pierde la garantía de que el material reservado no sale del equipo: el texto que leen los agentes pasa por el servicio de IA en la nube que los ejecuta.

## Consecuencias

- Conviene que el área legal o de seguridad del organismo esté de acuerdo con que ofertas reservadas pasen por un servicio de IA en la nube durante la estabilización. Esta conformidad no la puede dar el proyecto.
- La spec 007 (REQ-117) se cumple completa desde el fin de la estabilización; antes, valen los puntos 1 y 2 de este ADR.
- La regla de la memoria del Coordinador «los casos de compra nunca se suben a GitHub» sigue vigente sin cambios.
