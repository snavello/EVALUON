# ADR-0011 · Cómo se mide si una respuesta es correcta

Estado: aceptado · Fecha: 2026-10-03 · Decidió: responsable del proyecto

## Contexto

La corrida de calibración de T-045 (`evals/corridas/2026-10-03T132016_8ad46e6_gemma-4-12b-it-qat-q4_0/`) dio 45,8 % de respuesta correcta, contra el 85 % que pide la spec. El sistema citó la unidad esperada en 22 de 24 preguntas con respuesta y aplicó el régimen correcto en todas. La mayoría de las fallas no son del sistema: son de la regla automática que busca cada dato clave como frase textual dentro de la respuesta.

Ejemplos de esa corrida en los que la respuesta dice lo mismo con otras palabras y se cuenta como incorrecta:

- Se esperaba "no" y la respuesta dice "serán desestimadas sin posibilidad de subsanación".
- Se esperaba "30 días" y "acto de apertura", y la respuesta dice "treinta días a partir de la fecha de apertura del acto". Hoy el corrector convierte a cifra solo los números del uno al veinte escritos en letras.
- Se esperaba "por igual término" y la respuesta dice "por un período igual".
- Se esperaba "contratación directa" y la respuesta dice "contrataciones directas".

Ya lo había advertido la verificación de T-039: 16 casos tienen datos clave que son frases compuestas o parafraseadas.

## Alternativas

### A. Datos clave cortos y un corrector tolerante
Reescribir los datos clave como piezas cortas e independientes (el número, la unidad, el término que no puede faltar), con variantes cuando hay más de una forma correcta de decirlo. El corrector acepta números en letras de cualquier tamaño, singular y plural, y un "no" o un "sí" dicho de otra manera, siempre que el caso lo prevea como variante.
Se gana una medida barata, que se puede repetir en cada corrida y que es la misma en cada repetición. Se pierde que siempre se va a escapar alguna forma de decirlo que nadie previó.

### B. La IA local juzga la equivalencia
Un modelo compara la respuesta con la esperada y dice si significan lo mismo.
Mide mejor el sentido. A cambio, suma otro juicio de IA que también hay que validar, ocupa la GPU y puede variar entre corridas.

### C. Revisión humana respuesta por respuesta
El responsable o la Comisión revisan cada respuesta contra la esperada.
Es la medida más confiable, pero no se puede repetir ante cada cambio, que es lo que exige P7.

## Decisión

A para la medida automática de cada corrida, y C solo para la corrida que se presenta para aprobar. Esta última ya estaba prevista en el plan y en T-046: el responsable revisa las respuestas contra la esperada y puede dar por incorrecta cualquiera.

Reglas:

- Un dato clave es una pieza corta: un número con su unidad ("30 días"), un porcentaje, un término que no puede faltar, o "sí" o "no". No es una frase de la norma ni un resumen.
- Un dato clave puede traer variantes. Se cumple si aparece cualquiera de ellas. Las variantes de "sí" y "no" las escribe el caso: el corrector no las deduce.
- El corrector compara de manera tolerante con:
  - los números escritos en letras, de cualquier tamaño ("treinta" vale "30");
  - singular y plural;
  - tildes y mayúsculas, como ya hace hoy.

  No acepta sinónimos que el caso no haya previsto.
- La reescritura no cambia el sentido de ningún caso: la pregunta, la respuesta esperada, las unidades y el régimen quedan como están. El visto bueno provisorio se mantiene. El responsable ve en el pull request la tabla de cada dato clave antes y después.
- El 85 % de la spec no se toca.

## Consecuencias

- La medida automática pasa a reflejar lo que contesta el sistema y no cómo lo redacta. Las fallas que quedan son las que hay que mirar: respuesta incompleta, artículo que no llega a la selección, abstención indebida.
- Cuando el modelo encuentre una forma nueva de decir algo correcto, va a fallar hasta que alguien sume la variante al caso. Esa variante se suma solo con el visto bueno del caso, nunca para hacer pasar una corrida.
- Para revertir la decisión, se vuelve a la comparación textual. Los casos con datos clave cortos siguen siendo válidos con ella.
- Si A no alcanza, B queda como paso siguiente, en una decisión aparte.
