# ADR-0058 · Criterios de la Comisión para la evaluación y la ausencia verificada como fundamento

Estado: aceptado · Fecha: 2026-10-12 · Decidió: responsable del proyecto (decisiones literales en la spec 015)

## Contexto

La mesa de comité del 2026-10-12, que hizo el análisis final de calidad tras adoptar el Qwen3.8-27B, mostró dos cosas:

- 12 de las 18 celdas «no determinado» que cuentan en el caso-00 son cuatro filas que dependen de criterios que la Comisión de prueba aplicó y el sistema no tenía: el IVA incluido en el precio del Portal y los requisitos que se cumplen si la oferta no dice algo en contra.
- La prórroga automática del mantenimiento se perdía en los 4 casos medidos, y la presentación física en Mesa de Entrada se descartaba como forma de presentar por el Portal.

## Decisión

Las decisiones literales están en la spec 015.

1. **IVA.** «Precio del Portal = final con IVA»: salvo que la oferta diga lo contrario, el precio cotizado en el Portal es precio final con IVA incluido. El sistema propone «cumple» citando el Portal y este criterio.
2. **Ausencia verificada.** «Cumple por ausencia, con fundamento»: un requisito negativo o supletorio se propone «cumple» nombrando los documentos leídos y diciendo que ninguno lo contradice. Si alguno lo contradice, se propone «no cumple» con la cita. **Enmienda P3** (constitución 1.4).
3. **Prórroga.** «En la misma fila del plazo»: el mantenimiento y su prórroga automática son una sola fila, porque tratan el mismo asunto. Se evalúa por ausencia, salvo que la oferta limite el plazo o rechace la prórroga.
4. **Presentación física.** Presentar en Mesa de Entrada lo que el Portal marca como «Requiere presentar» es requisito. Si no consta entre los documentos ni en la hoja de compliance, es «no cumple», con un texto que avisa que puede faltar cargarlo. La cláusula de completar la oferta económica por el formulario del Portal no es fila propia.

## Consecuencias

- Las tareas T-257 (evaluación) y T-258 (matriz) aplican estos criterios. T-256 corrige la medida antes de medir, y T-260 mide una sola vez.
- El criterio del IVA y el de la ausencia quedan registrados en cada resultado, con su regla y su versión (P6).

## Aplicación (Coordinador, 2026-10-12, tras la verificación de T-257)

- **Presentación física.** El Portal todavía no importa la marca «Requiere presentar en Mesa de Entrada». Mientras no la traiga, cuando la obligación depende de esa marca el resultado es «no determinado» con pregunta a la Comisión, no «no cumple»; cuando la presentación física no depende de la marca (o está atada a la forma de garantía elegida), rige «no cumple» con «Puede faltar cargarlo». No es «no cumple» si una circular aclara que alcanza con la carga electrónica, ni con frases que no obligan.
- **Ausencia verificada.** Rige solo para prohibiciones sobre lo que dice la oferta y reglas supletorias (lista cerrada de formas), con tres condiciones: nada en contra en las condiciones ni en el grupo, el contraste no rechazó la conclusión y la lectura está completa. Una exigencia de documento dicha en negativo («no se aceptarán ofertas sin…») pide el documento y no se resuelve por ausencia. Ante la duda, «no determinado» con pregunta.
- **IVA.** No rige si la oferta dice algo sobre impuestos o ajustes de precio.
- **Riesgos aceptados (Coordinador, 2026-10-13, tercera verificación de T-257).** Dos casos aislados quedan aceptados con su riesgo, sin regla nueva: (Q8) el modelo marca que la oferta no usa una opción mientras su propio dato dice que sí: la celda puede salir «no aplica (opción no usada)»; se mitiga con la lectura de la Comisión y se mide en T-260; (Q9) una presentación física condicionada («deberán presentar…, si así lo requiere el organismo») puede salir «no cumple» con el texto «Puede faltar cargarlo», que la Comisión resuelve. Costo conocido de la regla estricta del IVA: si otro documento de la oferta nombra el IVA (por ejemplo, la prima de una póliza), el criterio no rige y la celda queda «no determinado».

