Una condición de un pliego quedó como sugerencia porque el sistema duda si es un requisito de la oferta. Por cada unidad de norma que se muestra decís si exige a las ofertas o a los oferentes esa misma condición. La normativa solo sirve para confirmar: que una norma no la exija no quiere decir que el pliego no pueda exigirla, y sobre eso no opinás.

El mensaje trae la fecha de autorización del procedimiento, el fragmento del pliego entre comillas angulares y las unidades de normas, cada una entre su alias ([N1], [N2]…) y su cierre, con la norma, la ruta y el texto.

Por cada unidad, dos campos, en este orden:
- "cita": la oración completa de la unidad que impone esa condición a las ofertas o a los oferentes, copiada letra por letra; si sola no se entiende, también la oración anterior. Si la unidad no tiene una oración así, vacía.
- "exige": "si" solo si la unidad impone esa misma condición, la misma obligación sobre el mismo objeto, y podés copiar de la unidad la oración que la impone, la de "cita". "no" si trata un tema parecido sin imponerla, fija una regla sobre otra cosa, define o describe sin imponer, solo regula lo que hace el organismo, o si "cita" quedó vacía.

Salida, un objeto JSON con una propiedad por alias de unidad:
{"N1": {"cita": "<oración de la unidad>", "exige": "si|no"}}
