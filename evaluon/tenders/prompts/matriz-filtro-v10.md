# COMÚN

Una primera lectura de un pliego propuso las filas formales y económicas de la matriz, buscando que no falte ninguna. Por cada fila decidís, con las definiciones de abajo y solo con lo que ves, si es un requisito de la oferta. Lo que descartás o dudás no se pierde: la Comisión lo ve con su motivo.

Cada fila va entre [Fn] y [/Fn], con su documento, su ruta, a veces un «Encabezado:» que es solo contexto, su clase propuesta, el fragmento y el texto del tramo con el fragmento entre <<< y >>>.

{{DEFINICIONES}}

EN ESTE CONTROL

- Una fila se evalúa entera: si alguna de sus condiciones es un requisito de la oferta, la fila lo es.
- La duda de las definiciones se resuelve acá: si con lo que ves no podés saber si la fila es un requisito de la oferta, respondé "duda" y la fila va como sugerencia, para que la Comisión la resuelva. No la mantengas ni la descartes por las dudas.
- Cada respuesta empieza por "razonamiento": una oración, de hasta 400 caracteres, que dice qué pide la fila y qué definición le corresponde.

# PREGUNTA A

Por cada fila:
- "decision": "mantener" si la definición la deja adentro, "descartar" si la deja afuera con seguridad, "duda" si con lo que ves no podés saberlo.
- "motivo": si descartás, el que corresponde según las definiciones; si no, vacío.
  - "titulo": un título.
  - "indice_caratula": un índice o una carátula.
  - "dato_procedimiento": una definición o un dato del procedimiento.
  - "norma_aplicable": la cita o la transcripción de una norma.
  - "formulario": una planilla o un modelo en blanco.
  - "obligacion_organismo": una obligación del organismo que la oferta no puede contradecir ni condicionar.
  - "derecho_posterior": un derecho del organismo posterior a la oferta, que la oferta no puede condicionar.
  - "ejecucion_contrato": la ejecución o el control del contrato después de adjudicar.
  - "consecuencia_sancion": una consecuencia de no cumplir.
  - "condicion_opcional": una oración que solo permite o describe una opción y no le exige nada a quien la usa.
  - "pago_factura": el pago, la moneda de pago o la factura.
  - "forma_presentacion_portal": la forma de presentar la oferta por el Portal.
  - "compromiso_presentacion": un compromiso que se cumple con solo presentarse.
- "indicio": si descartás, una frase del texto del tramo, de al menos cuatro palabras con contenido, copiada letra por letra y sin las marcas <<< ni >>>, que muestra por qué corresponde ese motivo; si no, vacío.

Salida, un objeto JSON con una propiedad por alias:
{"F1": {"razonamiento": "<qué pide la fila y qué definición le corresponde>", "decision": "mantener|descartar|duda", "motivo": "", "indicio": ""}}

# PREGUNTA B

Por cada fila, "respuesta": "si" si según las definiciones es un requisito de la oferta, "no" si queda afuera con claridad, "duda" si con lo que ves no podés saberlo. No elegís un motivo.

Salida, un objeto JSON con una propiedad por alias:
{"F1": {"razonamiento": "<qué pide la fila y qué definición le corresponde>", "respuesta": "si|no|duda"}}
