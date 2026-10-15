Una lectura de un pliego ya propuso las filas de la matriz, cada una con la oración que la exige. Por cada par de filas, decís si son un mismo requisito (una fila) o dos requisitos (dos filas).

Cada par va entre [Pn] y [/Pn], con su documento, su ruta, a veces un «Encabezado:» que es solo contexto, la «Fila A» y la «Fila B». Hay dos clases de pares: dos filas seguidas del mismo punto, con lo que el pliego dice entre ellas si dice algo; o una fila del punto y una nota de una tabla que cuelga de ese punto, con el texto de la tabla que está antes de la nota.

{{DEFINICIONES}}

Es «una» cuando la fila B continúa o precisa lo que pide la fila A (el mismo documento, la misma declaración, la misma verificación o el mismo plazo) y sola no se entiende o no se evalúa por separado. También es «una» la nota de una tabla que agrega algo que se cumple con la misma declaración de la fila A.

Es «dos» cuando cada fila pide algo que se puede cumplir sin la otra. Que las dos traten del mismo tema general no alcanza para unirlas.

Por cada par:
- "razonamiento": una o dos oraciones, primero: qué pide cada fila y si es lo mismo.
- "filas": "una" o "dos".

Salida, un objeto JSON con una propiedad por alias:
{"P1": {"razonamiento": "<qué pide cada fila y si es lo mismo>", "filas": "una|dos"}}
