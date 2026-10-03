# ADR-0008 · El procedimiento como eje y la hoja de ruta reformulada

Estado: aceptado · Fecha: 2026-10-03 · Decidió: responsable del proyecto, 2026-10-03

## Contexto

Al cerrar la etapa 2 de la feature 001, el responsable describió cómo va a funcionar el sistema final:

1. Opcionalmente se sube un pliego borrador para analizarlo contra la normativa. El sistema emite un informe de cumplimiento y le pregunta a la Comisión lo que no puede resolver. También arma una matriz de cumplimiento: las condiciones formales, económicas y técnicas que debe cumplir la oferta.
2. Cuando el pliego se aprueba y se publica, se sube el pliego final, que puede ser distinto del borrador.
3. Con las ofertas presentadas, que pueden ser varios documentos en distintos formatos, se arma una ficha por oferta: una síntesis de lo ofrecido y de los documentos que lo respaldan.
4. La Comisión sube un documento de compliance con lo verificado fuera del sistema. Por ejemplo, la oferta entrega la póliza de garantía que pide el pliego, pero al consultar los sistemas la póliza no está vigente.
5. Con el pliego, la oferta, el compliance y las preguntas que el sistema le haga al evaluador, empieza la evaluación.
6. Un acta de evaluación aportada como ejemplo muestra a qué resultado apunta el proceso. Por ahora el sistema no la redacta.

La hoja de ruta aprobada el 2026-10-02 pone la revisión del pliego borrador (002) como paso previo obligatorio de la matriz (003). Además, no tiene ni el procedimiento ni la ficha por oferta.

Precisiones del responsable:
- No hay una matriz estándar: el sistema la arma al evaluar el pliego.
- Si el pliego final difiere del borrador, la matriz se rehace desde el final.
- Responde la Comisión, que es también quien carga el pliego. Puede no responder en el momento y contestar después.
- Las ofertas son en su mayoría PDF, a veces escaneados, sin archivos firmados digitalmente.
- No hay un formato de ficha por oferta: el sistema propone uno.
- La 001 se limita a la Disposición 297/03 y a la 247/2022.

## Alternativas

### A. Mantener la hoja de ruta y sumar lo que falta dentro de cada feature
Se gana no tocar lo aprobado. Se pierde que la matriz quede atada a un paso opcional y que la ficha por oferta quede escondida dentro de la evaluación, sin spec propia ni criterios de aceptación.

### B. Reordenar en torno al procedimiento (elegida)
El procedimiento se vuelve la entidad central. El pliego final y la matriz se construyen primero, porque todo el camino de evaluación los necesita. La ficha por oferta pasa a ser una feature propia (008). El análisis del pliego borrador queda opcional y se construye después.

Se gana llegar antes a evaluar una oferta real. Se pierde algo de reutilización: la matriz preliminar del borrador (002) se construye después que la del pliego final (003).

## Decisión

B. La hoja de ruta, versión 2, queda en este orden:
1. 001: normativa.
2. 003: procedimiento, pliego final y matriz.
3. 008: ofertas y ficha.
4. 005: compliance.
5. 004: evaluación asistida.
6. 002: análisis del pliego borrador.
7. 006: salidas, sin acta.
8. 007: acceso por red.

Los números se conservan con su sentido más cercano, porque ninguna de esas features había empezado.

## Consecuencias

- **Specs nuevas.** La próxima spec es la 003. Define el procedimiento, con su fecha de autorización, que se conecta con REQ-020 de la 001 para saber qué régimen aplica. Define también el pliego como documento con versiones (borrador y final) y la matriz de cumplimiento.
- **Feature 001.** Reutiliza la lectura de PDF con texto y escaneado de la 001. La lectura de escaneos (T-021) gana prioridad, porque las ofertas la necesitan.
- **Preguntas a la Comisión.** Atraviesan la 002 y la 004. Su lugar como fundamento lo trata el ADR-0009.
- **Corpus de la 001.** Queda en la 297/03 y la 247/2022. Los requisitos de categorías (REQ-018, REQ-019) se prueban con documentos sintéticos. Las modificatorias de la 297/03 se registran como "sin cargar" (REQ-021).
- **Material de referencia.** El caso público completo y el acta de ejemplo van a `corpus/casos/`, porque son públicos (P4).
- **Para revertir.** Volver a la versión 1 de la hoja de ruta. No hay código de esas features.
