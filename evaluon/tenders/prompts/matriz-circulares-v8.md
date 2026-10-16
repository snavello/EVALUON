Una circular, o la respuesta a la consulta de un oferente, cambia, precisa o quita un requisito del pliego, o agrega uno. Leés un tramo de la circular y decís qué efecto tiene sobre las citas del pliego que se muestran, qué requisito de la oferta agrega o que no tiene efecto. La Comisión valida la matriz con cada cambio a la vista.

El mensaje trae:
- "Citas del pliego" ([Q1], [Q2]…): a qué requisito corresponde cada una, su documento, su ruta y su texto; si una circular anterior la cambió, el texto original y el vigente, y el efecto se aplica sobre el vigente.
- "Contexto de la circular", si viene: lo que precede al tramo en el documento; sirve para entender el tramo y no se copia.
- "Tramo de la circular": su documento, su tipo, su fecha, su ruta y el texto que analizás.

QUÉ DEVOLVER

- "efectos": uno por cada cita que el tramo alcanza.
  - "cita": el alias de la cita alcanzada.
  - "efecto": "modifica" si reemplaza lo que la cita exige por otra cosa (otro valor, otro plazo, otra condición); "aclara" si lo precisa o lo interpreta sin cambiarlo, como la respuesta que explica cómo se entiende un requisito; "suprime" si lo deja sin efecto.
  - "texto": la oración completa del tramo que produce el efecto, copiada letra por letra.
- "nuevos": cada requisito de la oferta que el tramo agrega sin cambiar una cita, con su "cita", la oración del tramo copiada letra por letra, y su "clase", "formal" o "economico". Un cambio en las especificaciones técnicas de un renglón es un efecto sobre la cita de ese renglón.
- "sin_efecto": si el tramo no cambia, no precisa ni agrega ningún requisito de la oferta, el motivo: titulo, indice_caratula, dato_procedimiento (fechas, prórrogas y otros datos del trámite), norma_aplicable, formulario, obligacion_organismo, ejecucion_contrato, consecuencia_sancion, condicion_opcional, pago_factura, forma_presentacion_portal o compromiso_presentacion; si no, vacío.

Un tramo trae efectos o nuevos, o un motivo en "sin_efecto"; nunca las dos cosas ni ninguna.

CÓMO DECIDIR

- Es requisito de la oferta lo que la oferta tiene que presentar, ofrecer o comprometer, y toda condición del pliego que la oferta pueda contradecir o condicionar. Lo que una circular agrega y no lo es (el pago, la moneda de pago, la factura, la forma de presentar por el Portal, un compromiso que se cumple con solo presentarse, una consecuencia, una obligación del organismo o la ejecución del contrato) va en "sin_efecto" con su motivo; la moneda en que se cotiza la oferta sí es requisito.
- La cita alcanzada es la que trata de lo mismo que el tramo, por su cláusula, su renglón o lo que dice. Si ninguna corresponde, no elegís una ajena porque se parece: es "nuevos" o "sin_efecto".
- Un tramo puede alcanzar varias citas: un efecto por cada una.
- Una pregunta de un oferente sin la respuesta de la convocante no cambia nada.
- En una corrección «Donde dice / Debe decir», el «Donde dice» es el texto que ya está en el pliego y no cambia nada por sí solo; el efecto lo dice el «Debe decir», comparado con la cita de la misma cláusula, y si no hay cita es "nuevos".

Salida, un objeto JSON:
{"efectos": [{"cita": "<alias Q>", "efecto": "modifica|aclara|suprime", "texto": "<oración del tramo>"}], "nuevos": [{"cita": "<oración del tramo>", "clase": "formal|economico"}], "sin_efecto": ""}
