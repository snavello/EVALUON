# ADR-0054 · Matriz: cita de la oración completa, definiciones del responsable en un bloque común y motivos de descarte nuevos

Estado: propuesto · Fecha: 2026-10-10 · Decidió: — (las definiciones de qué entra en la matriz son decisión literal del responsable, 2026-10-10, en la spec 015; el diseño, el Planificador); enmienda al ADR-0019 (decisión 2, lista cerrada de motivos de descarte, y decisión 3, «copia un fragmento corto») y al ADR-0021 (regla «ante la duda se mantiene» y tabla de destinos)

## Contexto

Al rehacer el caso LPU25 (T-229), el sistema propuso una matriz de 122 filas y la Comisión quitó 95 (78 %). El diagnóstico del 2026-10-10 (fuera del repositorio) atribuye las 95 quitas a: instrucciones, 69 (73 %); el modelo, 16 (17 %); tramos que llegan sin su encabezado, 9 (9 %); una dudosa. Las instrucciones mandan «dividí las enumeraciones» y «copiá el fragmento más corto» (32 filas de fragmentos sin sujeto; de las 27 filas que quedaron, la Comisión corrigió 13, todas ampliando la cita a la oración); el filtro dice «ante la duda, la fila se mantiene» (mantuvo 88 de las 95 quitadas y descartó 6, todas bien); y ninguna instrucción distingue las condiciones opcionales ni lo que no es requisito de la oferta.

La revisión exhaustiva de las instrucciones del mismo día (informe local `revision-instrucciones.md`, con seis pedidos de prueba a la GPU, de a uno) agrega evidencia:

- Cinco instrucciones de la matriz (extracción, completitud, filtro, circulares) dicen lo contrario de lo que decidió el responsable el 2026-10-10: que son requisitos el pago, la moneda y la factura, la forma de presentar y los compromisos de presentarse. Con el filtro A tal como está, el lote 1 dio «mantener» en las 15 filas; con **solo las definiciones nuevas**, 13 de 15 salieron «descartar» y quedaron las 2 correctas (la moneda en que se cotiza y el IVA). Pedir el razonamiento antes, con las definiciones viejas, no cambió nada (15 de 15).
- Hay tres capas seguidas de «ante la duda, de más» (extracción, completitud y filtro) y una regla de código: `decide()` (`filter.py`) descarta solo si A dice «descartar» con indicio ubicado y B dice «no»; con las definiciones viejas, B respondió «si» en 14 de 15 filas, así que aun corrigiendo A esas filas habrían ido a sugerencia.
- La lista de motivos de descarte no tiene lugar para la consecuencia (en la extracción), la condición opcional, el pago, la forma de presentar por el Portal ni el compromiso de presentarse: el modelo usa `dato_procedimiento` y `norma_aplicable` de comodín. El motivo es el fundamento que ve la Comisión (P3).
- Con la regla de la oración completa, la extracción devolvió enteras las cláusulas 6.1, 6.2, 7.1, 7.2 y 7.3 del lote 4; las exclusiones le tocan al filtro.
- La regla de «opción» se pasa de rosca: descartó tres condiciones de la forma de garantía (límite del pagaré, no combinable, póliza según la norma) que el oferente **tiene que elegir** entre pagaré y póliza. El responsable lo resolvió el 2026-10-10: «Requisito de la forma elegida».

Lo que dicen hoy los ADR:

- **ADR-0019, decisión 3:** el modelo «copia un fragmento corto». Y el principio de la spec 003: «un requisito que no corresponde lo quita el evaluador, pero uno que falta no lo evalúa nadie» (100 % de encontrados).
- **ADR-0019, decisión 2:** lista cerrada de siete motivos de descarte; la forma y el plazo de pago son un requisito económico aunque lo cumpla el organismo.
- **ADR-0021:** ante la duda la fila se queda.
- **ADR-0024:** los sobrantes no bloquean «hasta el piloto»; el tope se vuelve a decidir con lo que la Comisión haya visto en uso. T-229 es ese uso.

Decisiones literales del responsable (2026-10-10), en la spec 015: «no entran ninguno de los 3» (pago, moneda de pago y factura; forma de presentar por el Portal; compromisos que se cumplen al presentarse), con la salvedad de que **la moneda en que se cotiza la oferta sí es requisito**. REQ-101: la cita es la oración completa, con el encabezado del punto o del inciso cuando la oración sola no se entiende, nunca un pedazo sin sujeto.

Restricciones: la cita sigue siendo literal, un recorte contiguo del texto canónico del pliego (REQ-025, ADR-0004); el modelo no escribe el texto citado; la Comisión decide (P3); lo que el sistema dudó no se pierde en silencio.

## Alternativas

### A. Dejar el diseño y que la Comisión pode
Se gana: nada que cambiar; máximo de recall. Se pierde: la Comisión quita el 78 % de las filas y corrige a mano la cita de otra parte; es la causa de la queja del responsable.

### B. Oración completa por código, un bloque común de definiciones, motivos nuevos y filtro sin sesgo a mantener (propuesta)
Se gana: ataca las tres causas (fragmentos, definiciones, sesgo del filtro) con evidencia medida en la GPU; el límite de la oración lo pone el código, determinista; las definiciones del responsable viven en un solo lugar. Se pierde: una oración que enumera varias condiciones queda en una sola fila; el recall baja del 100 % al 95 % de la lista esperada (criterio de la spec 015); hay que ampliar la lista cerrada de motivos (una migración); hay que revisar las listas esperadas de los casos 00 a 06, que incluyen filas de pago, factura y presentación por el Portal.

### C. Solo mejorar el filtro (más preguntas, razonamiento) sin tocar la cita
Se gana: menos filas de más con un cambio chico. Se pierde: no toca las 32 filas de fragmentos ni las 13 correcciones de cita; y la prueba 2 de la revisión mostró que el razonamiento solo no cambia la decisión.

### D. Revisión humana previa de la propuesta
Descartada: contradice el objetivo (que la Comisión valide confirmando y corrigiendo poco).

## Decisión

Se propone **B**, con estas reglas:

1. **Cita = oración completa.** El modelo sigue señalando un fragmento; el sistema lo ubica (`quotes.locate`) y lo **amplía por código hasta el límite de la oración** (puntuación final, sin cortar tras abreviaturas conocidas) o hasta el límite del inciso o la viñeta. La cita guardada es el recorte contiguo del texto canónico (sigue siendo literal) y el pedido guarda aparte el fragmento que señaló el modelo (P6).
2. **Encabezado.** Un inciso o viñeta cuya oración sola no se entiende (empieza en minúscula, es un inciso de una lista cuyo encabezado termina en «:», o abre con «Esto», «La misma») lleva a la vista el encabezado de su punto, que se toma del tramo padre por la clave del tramo. El modelo lo recibe en el pedido como contexto que no se cita; la fila lo muestra rotulado. No hay cambio de esquema por esto.
3. **Una fila por oración** (o inciso). Las enumeraciones dentro de una oración no se dividen. Se sacan «dividí» y «fragmento más corto» y los ejemplos que enseñaban filas sin sujeto; la completitud ya no divide ni «une» oraciones: solo suma oraciones completas que faltan.
4. **Un bloque común de definiciones**, copiado literal de la tabla de decisiones de la spec 015 y con su propia versión y huella (`matriz-definiciones-v1.md`), que el código incluye en la extracción, la completitud, el filtro (A y B) y las circulares. No entran pago, moneda de pago, factura, forma de presentar por el Portal ni compromisos al presentarse; entra la moneda en que se cotiza; no entran consecuencias ni obligaciones del organismo; una condición que solo vale si el oferente **puede no usar** una opción (alternativa, descuento, MiPyME, subcontratación) entra solo como condición de esa opción; las condiciones de una forma que el oferente **tiene que elegir** (garantía) entran en la matriz y se evalúan solo en la oferta que eligió esa forma (decisión del responsable del 2026-10-10, «Requisito de la forma elegida»).
5. **Motivos de descarte nuevos (enmienda del ADR-0019, decisión 2).** Se suman a `DiscardReason` (tramos) y a `FilterMotive` / `FILTER_MOTIVES` (filas): consecuencia (en la extracción; en el filtro ya existe `consecuencia_sancion`), condición opcional, pago o factura, forma de presentar por el Portal y compromiso al presentarse. Los nombres exactos los fija la tarea de esquema (T-250) con una migración de `tenders` a cargo de un solo agente; las filas descartadas ya guardadas conservan sus motivos.
6. **Filtro sin sesgo.** Se saca «ante la duda, mantené» (tres veces). Una duda real no se pierde: va a **sugerencia** (el destino que ya existe, ADR-0022), visible en su bloque aparte. La pregunta B se rehace con las mismas definiciones y `decide()` se revisa para que un acuerdo de A (con motivo e indicio) sea suficiente cuando B no contradice con su propio razonamiento; la tabla de destinos del ADR-0021 se actualiza en `filter.py` y en su documentación. Se mantiene la guarda en código de oraciones compartidas (`protect_shared_sentences`).
7. **Un sesgo por etapa.** La extracción conserva «ante la duda, proponé de más» (busca recall), limitado a oraciones que le exigen algo a todas las ofertas; la completitud y el filtro no.
8. **Lotes.** Extracción: de 1.500 a 3.000–4.000 tokens de entrada por lote, junto con el encabezado; filtro: de 15 a 5–8 filas por pedido (el lote 1 de 15 filas salía todo igual), con el punto completo de cada fila.
9. **Recall.** El criterio pasa de 100 % de encontrados a **al menos 95 % de la lista esperada** (spec 015). Las entradas de las listas esperadas que las definiciones nuevas excluyen se marcan como excluidas por decisión del 2026-10-10 y no cuentan como faltantes; la lista modificada lleva su huella y el visto bueno del Coordinador antes de medir.

## Pendiente con el responsable

**Condiciones de la forma de garantía que elige el oferente (pagaré o póliza).** La prueba 5 de la revisión muestra que la regla de la opción descarta de más tres condiciones de esa forma (límite del pagaré, no combinable, póliza según la norma). Resuelto el 2026-10-10: «Requisito de la forma elegida». La instrucción distingue «una opción que puede no usar» de «una forma que tiene que elegir» y mantiene las condiciones de la forma elegida como condiciones de esa opción; esas condiciones entran y se evalúan solo en la oferta que eligió esa forma. Además, «Una fila por oración» (2026-10-10): una enumeración queda en una sola fila con la oración completa.

## Consecuencias

Más fácil: la Comisión valida confirmando; cada fila se entiende sola; las definiciones del responsable están en un solo lugar y las instrucciones dejan de contradecirse entre sí.

Más difícil: un requisito dicho dentro de una enumeración ya no tiene su propia fila (el contraste de la evaluación ve toda la oración y la Comisión decide la parte); el filtro puede mandar más filas a sugerencias; hay una migración de `tenders` y un bloque más que versionar; las listas esperadas se tocan una vez.

Para revertir: volver a las versiones `matriz-extraccion-v3`, `matriz-completitud-v3` y `matriz-filtro-v2`, quitar la ampliación (un solo punto de código) y dejar los motivos nuevos sin usar (la migración solo agrega valores). Las matrices ya validadas conservan sus citas.

## Sin verificar

- Que la oración completa baste para el 70 % de filas conservadas en los casos 01 a 06: se mide en T-239. Las pruebas de la revisión son de un solo lote cada una, sin lista esperada, y los ejemplos se parecen a LPU25: hay riesgo de ajuste a este caso.
- Cuántas filas de los casos 00 a 06 son de las clases que ahora salen: se cuenta en T-238 al revisar las listas esperadas.
- Qué hace la pregunta B rehecha con las definiciones nuevas: la revisión no la probó.
