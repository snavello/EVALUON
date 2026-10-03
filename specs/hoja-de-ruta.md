# Hoja de ruta de EVALUON

Estado: aprobada · Fecha: 2026-10-03 · Aprobó: responsable del proyecto · Versión 2, reformulada según el ADR-0008 · Ajuste: 2026-10-03, feature 009 (ADR-0016), decisión del responsable · Reordenada: 2026-10-03, el núcleo (003, 008, 004) antes que la 005 y la 009 (ADR-0017), decisión del responsable · 2026-10-03: feature 010, asistente técnico, como mejora futura, decisión del responsable

Las features del proyecto, en el orden en que se construyen. Cada una tiene su carpeta en `specs/` cuando se empieza a trabajar. El tablero (`docs/tablero.md`) lee esta tabla para mostrar el mapa del proyecto.

El eje es el **procedimiento de compra**: su fecha de autorización (que fija el régimen aplicable), su pliego borrador y su pliego final, sus ofertas, sus hojas de compliance y su evaluación. Todo lo que el sistema hace cuelga de un procedimiento.

| N.º | Feature | Qué entrega | Depende de |
|---|---|---|---|
| 001 | Normativa consultable con cita | Las normas de compras cargadas, versionadas y consultables, con cada respuesta respaldada por el artículo que la sostiene | — |
| 003 | Procedimiento, pliego final y matriz de cumplimiento | El procedimiento con su fecha de autorización; la carga del pliego final publicado; la matriz de cumplimiento (requisitos formales, económicos y técnicos que debe cumplir la oferta, cada uno con su cita al pliego) armada desde el pliego final y validada por la Comisión | 001 |
| 008 | Ofertas y ficha por oferta | La carga de cada oferta en varios documentos (PDF con texto o escaneado) y una ficha por oferta: síntesis de lo ofrecido frente a cada requisito de la matriz, con los documentos y fragmentos que lo respaldan | 003 |
| 004 | Evaluación asistida de ofertas | Por cada oferta y cada requisito de la matriz, una propuesta de cumple, no cumple o no determinado con su fundamento (pliego, oferta, compliance, normativa o respuesta de la Comisión) y preguntas a la Comisión sobre lo que no puede resolver; la Comisión confirma, corrige o rechaza | 003, 008 (la 005 suma el compliance como fundamento cuando esté) |
| 005 | Hojas de compliance | La carga, por la Comisión, del documento de compliance de cada oferta: lo verificado en sistemas no integrados (por ejemplo, que la póliza de garantía presentada esté vigente o que no haya deudas) | 008 |
| 009 | Validación continua con la Comisión | Un circuito único para que la Comisión responda y valide preguntas y respuestas del sistema, y registre sus respuestas. Cada cuestión resuelta puede quedar como fundamento (ADR-0009), como caso para medir al sistema o como pedido de cargar una norma o un documento. Lo que queda sin validar se ve como pendiente. Uso intensivo al principio, y después ante cuestiones que no se saben resolver | 001 |
| 002 | Análisis del pliego borrador | Opcional: un informe de cumplimiento de un pliego borrador contra la normativa, con preguntas a la Comisión sobre lo que no puede resolver, y su matriz de cumplimiento preliminar | 001, 003 |
| 006 | Salidas de la evaluación | Planilla por oferta y cuadro comparativo; el borrador de acta queda diferido | 004 |
| 007 | Acceso por red | Uso de la pantalla desde otras computadoras, con conexión cifrada y bloqueo tras intentos fallidos de clave | 001 |
| 010 | Asistente técnico | Un asistente que compara la parte técnica de cada oferta con las especificaciones del pliego, renglón por renglón, para ayudar a la Comisión a revisar el informe técnico del área requirente. No es vinculante: el resultado técnico sigue siendo el del área requirente | 003, 008 |

Los números 002 a 007 se conservan con el sentido más cercano al que tenían; la 008 es nueva. Ninguna de ellas había empezado.

## Preguntas a la Comisión

El análisis del pliego y la evaluación pueden hacerle preguntas a la Comisión sobre lo que no resuelven con la normativa, el pliego, la oferta o el compliance. La Comisión responde cuando tiene el dato; una pregunta puede quedar sin responder, y entonces el punto queda como "no determinado" y la falta de respuesta se informa. Una respuesta registrada, con quién respondió y cuándo, puede servir de fundamento (ADR-0009).

## Alcance del piloto

El piloto de evaluación guiada necesita la 001, la 003, la 008 y la 004, y la 007 para que la Comisión entre desde sus computadoras; la 005 y la 009 lo completan (ADR-0017). Si la 004 necesita registrar respuestas de la Comisión como fundamento (ADR-0009) antes de la 009, se hace una versión mínima de ese registro dentro de la 004. La 002 y la 006 lo completan y pueden entrar después de la primera prueba en paralelo con la evaluación habitual.

Material de referencia para construir: un caso público completo (pliego, ofertas y evaluación terminada) que aporta el responsable, y un acta de evaluación como ejemplo del resultado final del proceso.

## Decisiones diferidas

- **Borrador de acta.** El acta de evaluación aportada es un ejemplo de cómo termina el proceso; por ahora el sistema no la redacta (decisión del responsable del 2026-10-03).
- **Texto ordenado de las normas.** La feature 001 reúne las normas tal como fueron publicadas y registra sus modificaciones. Queda por decidir si más adelante el sistema arma además el texto vigente con las modificaciones aplicadas, y si para eso se usa una IA externa (permitido, por ser normativa pública) con validación de una persona. Se construiría sobre lo que la 001 deja guardado, como una feature nueva.

## Cómo se modifica

Agregar, quitar o reordenar features se hace en esta tabla, con aprobación del responsable. La numeración no se reutiliza.
