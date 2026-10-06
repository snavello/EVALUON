# ADR-0038 · Resultados con cita literal verificada por el sistema y contraste antes de concluir

Estado: propuesto · Fecha: 2026-10-06 · Decidió: —

## Contexto

La meta de la 004 (decisión del responsable, 2026-10-06) es más del 80 % de coincidencia con el dictamen del caso-00 y cero contradicciones (ningún "cumple" donde la Comisión dijo "no cumple", ni al revés). Ante la duda, "no determinado". Sin cita literal de la oferta no hay "cumple" ni "no cumple" (REQ-053; P3). El modelo (Gemma 4 12B, temperatura 0, semilla fija) puede citar de memoria, parafrasear o concluir de más. En la 003 y la 008 el sistema nunca acepta texto del modelo como cita: la busca en el texto canónico (`tenders/proposal/quotes.py`) o la copia de la base.

Cuatro resultados posibles (spec): cumple, no cumple, no se encontró el documento, no determinado.

## Alternativas

### A. Una pasada: el modelo concluye y cita; el sistema verifica la cita

Se gana: un pedido por grupo; sencillo. Se pierde: una cita que existe y está en la oferta puede no respaldar la conclusión (el modelo cita algo del tema y concluye "cumple"). La verificación literal prueba que el texto está, no que alcanza. Es el camino más probable a una contradicción.

### B. Una pasada más un contraste (elegida)

Después de la pasada, por cada conclusión "cumple" o "no cumple" con cita verificada, un segundo pedido corto recibe solo el requisito, el texto literal citado y los fundamentos, y contesta si ese texto, por sí solo, demuestra la conclusión (sí, no, parcial). Si no contesta "sí", el resultado es "no determinado" con lo citado. Se gana: el criterio "donde duda o no puede corroborar, no determinado" tiene un mecanismo; el pedido es corto (unos 1.000 tokens). Se pierde: un pedido más por cada conclusión; el contraste del mismo modelo puede coincidir con su error; algunos "cumple" correctos pasarán a "no determinado" (baja la coincidencia).

### C. Dos corridas completas independientes y acuerdo

Se gana: más robusto al azar del modelo. Se pierde: duplica el tiempo de todo el pedido; con temperatura 0 y semilla fija las dos corridas repiten lo mismo, así que habría que variar las instrucciones, y entonces es un contraste caro.

## Decisión

Se propone B, con estas reglas (detalle en el plan, "Flujo de IA"):

1. El modelo devuelve el resultado, la exigencia (documento o condición), las citas (documento y texto) y una explicación breve. **La página y las posiciones las pone el sistema** al ubicar el texto en el texto canónico del documento; el texto que se muestra es el recorte del canónico, nunca el que escribió el modelo. Una cita no ubicable se descarta; un "cumple" o "no cumple" sin ninguna cita ubicada se reintenta una vez y, si sigue igual, queda "no determinado" (REQ-053).
2. Si distintos grupos de documentos dan resultados distintos, rige: "cumple" y "no cumple" juntos son "no determinado" por contradicción entre documentos, con las citas de ambos; una conclusión con cita más "no consta" en los demás grupos queda la conclusión.
3. "No se encontró el documento" solo si el pliego exige un documento, todos los grupos de la oferta se leyeron y dijeron "no consta", y la oferta no tiene páginas sin leer. Si tiene páginas sin leer, es "no determinado" (no se supone que la respuesta no estaba). Nunca es "no cumple" (REQ-060).
4. Una respuesta de la Comisión puede ser fundamento, pero no sustituye la cita de la oferta: con una respuesta como único apoyo el resultado propuesto sigue "no determinado" y la persona decide (corrige) con la respuesta a la vista (ADR-0009; coherente con "sin cita literal de la oferta no hay cumple ni no cumple").

## Consecuencias

- Más fácil: el 100 % de citas literales es una propiedad del sistema, no del modelo; se prueba con un test.
- Más difícil: la coincidencia del 80 % depende de cuántos "cumple" correctos sobreviven al contraste; se mide y es el primer ajuste posible (instrucciones del contraste, versión nueva y medición).
- Para revertir el contraste: quitar el segundo pedido; cada "cumple" pasaría sin corroborar y habría que reabrir la meta de cero contradicciones con el responsable.
- Los pedidos del contraste quedan en `assessment_step` (P6).
