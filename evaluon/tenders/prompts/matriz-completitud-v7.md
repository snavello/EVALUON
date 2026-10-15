Una primera lectura de un pliego ya propuso los requisitos de cada tramo. Tu tarea es decir qué requisito formal o económico de la oferta quedó afuera.

Cada tramo va entre [Tn] y [/Tn], con sus «Requisitos ya encontrados» («ninguno» si la primera lectura lo descartó) y su texto. La línea «Encabezado:» es contexto y nunca se cita.

{{DEFINICIONES}}

Por cada tramo, "faltantes" lista las oraciones del texto que son requisitos según estas definiciones y no están entre los ya encontrados, cada una con su "cita", copiada letra por letra del texto, y su "clase" ("formal" o "economico").
- Un requisito ya encontrado está completo aunque junte varias condiciones: no lo repitas ni lo partas.
- Si una oración seguida del mismo asunto quedó fuera de un requisito ya encontrado, como la prórroga automática de un plazo, devolvela como faltante.
- Lo técnico no lo buscás.
- Si no falta nada, la lista va vacía.

Salida, un objeto JSON con una propiedad por alias:
{"T1": {"faltantes": [{"cita": "<oración del tramo>", "clase": "formal|economico"}]}}
