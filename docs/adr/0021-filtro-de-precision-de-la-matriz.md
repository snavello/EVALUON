# ADR-0021 · Filtro de precisión de la matriz: una pasada separada, con descarte visible y recuperable

Estado: aceptado · Fecha: 2026-10-04 · Decidió: responsable del proyecto (al aprobar la enmienda del plan 003)

## Contexto

La spec 003, enmendada el 2026-10-04 (REQ-033), pide que antes de mostrar la matriz el sistema descarte las filas que no son requisitos de la oferta y unifique las que repiten la misma condición, dejando lo descartado en una lista aparte, con su cita y su motivo, que la Comisión puede abrir y devolver. La medición pone un tope: los sobrantes no pueden superar el 20 % de la matriz propuesta en el nivel por omisión, con el 100 % de encontrados; un esperado descartado por el sistema cuenta como faltante.

Lo medido en T-093 (caso-00, alta): 52 esperados, 51 encontrados y 95 sobrantes, es decir, el 65 % de la matriz propuesta. En una muestra de 30 de esos 95 sobrantes (análisis local, fuera del repositorio): 18 no eran requisitos de la oferta (ejecución del contrato, obligaciones del organismo, texto de normas o de formularios, datos), 9 eran condiciones plausibles de la oferta que la lista no tiene, 2 eran repetidas y 1 era una división legítima. En T-094, el caso-01 dio 85 esperados y 327 sobrantes, y el caso-02, 108 y 133.

El responsable fijó que en la matriz manda la calidad y que el tiempo es secundario: una pasada más del modelo es aceptable. Lo que no es negociable es el 100 % de encontrados: una fila real que el filtro se lleve es un faltante que bloquea la aceptación. Además, los casos 01 y 02 se miden a ciegas, de modo que el filtro no se puede corregir mirando sus resultados.

Restricciones: Gemma 4 12B con contexto de 16.384 tokens (ADR-0002); salida estructurada obligada por el motor; cita literal comprobada por el sistema (ADR-0004, ADR-0019); lo que el modelo escribe no se muestra como texto propio (P3).

## Alternativas

### A. Endurecer la extracción (el filtro dentro de la misma pasada)
Las instrucciones de extracción y completitud piden no proponer cláusulas de ejecución, obligaciones del organismo, texto de normas ni formularios.
- Se gana: ninguna pasada más, ningún tiempo más.
- Se pierde: va contra "ante la duda, proponer de más" (spec, REQ-024) en la misma decisión que protege el 100 %; el modelo decide en un solo paso qué es un requisito y si descartarlo, y no queda registro de lo que descartó (un requisito que no se propone no figura en ningún lado, no hay lista que abrir ni devolver, y REQ-033 pide esa lista). T-093 mostró que cambiar las instrucciones de extracción mueve los encontrados en las dos direcciones (media perdió M-034 y M-035 al ajustar): tocar la extracción para bajar sobrantes arriesga el 100 %. Tampoco resuelve las filas repetidas.

### B. Pasada de filtro separada, después de la extracción (propuesta)
La extracción y la completitud siguen proponiendo de más. Una pasada posterior revisa cada fila formal o económica con su tramo y decide mantener o descartar. Para descartar, hacen falta dos opiniones que coincidan y un indicio literal verificable; ante cualquier duda, la fila se mantiene. Las repetidas se unifican por una regla. Lo descartado se guarda en una tabla propia, con su cita, motivo, indicio y las dos opiniones, y la Comisión lo puede devolver.
- Se gana: la extracción conserva su cobertura y su medición; el filtro se ajusta y se mide por separado; cada descarte queda registrado y es recuperable (P3, P6); el costo de equivocarse está acotado (una fila devuelta a mano); la pasada de consecuencias, que se paga por fila, corre sobre menos filas.
- Se pierde: una o dos pasadas más del modelo (minutos, no decenas); instrucciones nuevas que mantener y medir; una tabla y una pantalla nuevas.

### C. Solo reglas, sin modelo
Descartar por marcadores: sujeto distinto de la oferta ("el adjudicatario", "el organismo", "la Agencia"), secciones de ejecución, texto entre comillas de normas, anexos que repiten la norma.
- Se gana: determinista, sin tiempo de GPU, reproducible a la letra.
- Se pierde: el sujeto gramatical no alcanza ("la mera presentación de la oferta implica…" es del oferente; "la oferta deberá ser mantenida…" es un requisito); las reglas se escriben mirando un pliego y no se sostienen en el siguiente, que es el riesgo de sobreajuste que se quiere evitar. Se usa solo para unificar repetidas, donde la coincidencia del texto es objetiva.

### D. Dos opiniones iguales (un solo tipo de pedido repetido)
El filtro de B pero con la misma pregunta hecha dos veces.
- Se gana: más simple.
- Se pierde: dos respuestas del mismo modelo a la misma pregunta con temperatura 0 son casi la misma respuesta; no frenan un error sistemático. Por eso B usa dos preguntas distintas.

## Decisión

Se propone **B**, con estas reglas:

1. **Pasada separada**, después de la extracción (y la completitud y la segunda extracción, según el nivel) y antes de las filas técnicas, las circulares y las consecuencias. Alcanza a las filas formales y económicas propuestas por el modelo. No alcanza a las filas técnicas (las arma una regla), a las filas que agrega una circular, a las de tramos de tabla (ya quedan pendientes de revisión) ni a las de cita amplia.
2. **Dos preguntas distintas por fila.** La primera pide mantener o descartar, con un motivo de una lista cerrada (la del ADR-0019 para los descartes de tramos, más "consecuencia o sanción" y "derecho posterior a la oferta") y un indicio: un fragmento literal del tramo que sostiene ese motivo. La segunda pregunta lo contrario: si la oferta puede presentar, ofrecer, comprometer, contradecir o condicionar lo que dice la fila (sí, no o duda).
3. **Se descarta solo si** la primera pide descartar con motivo válido y con indicio hallado, palabra por palabra, en el tramo, y la segunda responde que no. Todo lo demás (respuesta inválida, indicio ausente, duda, salida cortada) mantiene la fila.
4. **Unificación por regla**, no por modelo: dos filas cuyo fragmento es igual (normalizado) o una contiene a la otra, o cuya similitud de palabras supera un umbral fijo, se unifican en la primera en el orden del pliego, que conserva las citas de las otras como citas adicionales. Se aplica antes del filtro.
5. **Lo descartado queda en una tabla de solo inserción** con su cita literal, su motivo, su indicio y las dos respuestas, y se muestra en una lista aparte. Devolver una fila crea el requisito con su cita y registra el cambio con quién y cuándo.
6. **Pasadas, parámetros e instrucciones versionados y registrados** como las demás (P6).

Motivo principal: es la única alternativa que protege a la vez el 100 % de encontrados (la extracción no se toca), la transparencia que pide REQ-033 (todo descarte visible y recuperable) y la independencia del ajuste (el filtro se ajusta con una pasada propia sobre el caso-00, y los casos 01 y 02 miden sin haberlo mirado).

## Consecuencias

**Más fácil**
- El tope de sobrantes se mide sobre la matriz propuesta sin descartadas; los descartes se miden aparte, con una muestra revisada de sus motivos.
- Si el filtro se lleva un esperado, la causa es propia (`descartado_por_el_sistema`) y se ve en la lista de descartadas cuál fue el motivo y el indicio.
- La pasada de consecuencias corre sobre menos filas, con lo que compensa parte del tiempo.

**Más difícil**
- Una o dos pasadas más: estimadas en 1 a 2 minutos en el caso-00, de los que consecuencias recupera parte. La spec enmendada el 2026-10-04 eliminó el nivel "media" y el máximo de tiempo: hay un solo proceso, el más completo, y el tiempo se informa sin bloquear.
- **El tope puede no alcanzarse con el filtro solo.** Si el filtro quita todo lo que no es requisito y lo repetido (unos 20 de cada 30 sobrantes en la muestra), quedan las condiciones plausibles que la lista esperada no tiene (unos 9 de cada 30): con el caso-00 serían del orden de 30 sobrantes sobre unas 80 filas (unos 38 %), no 20 %. El filtro no debe descartar esas filas para llegar al tope: son condiciones que la oferta puede condicionar y descartarlas pone en riesgo el 100 %. Si la medición del caso-00 lo confirma, la salida es una decisión del responsable (revisar con la Comisión si esas condiciones son requisitos y ampliar la lista, o revisar el tope), no un ajuste del filtro.
- Dos instrucciones nuevas y su medición; la unificación por regla puede juntar de más dos filas parecidas que son condiciones distintas (se mitiga conservando las dos citas, y porque lo unificado se ve).

**Para revertir**
- Desactivar la pasada con un parámetro (`FILTER_ENABLED`) vuelve a la matriz de T-093; la tabla de descartadas y los datos guardados siguen siendo válidos. Pasar a A es dejar de llamar a la pasada y tocar las instrucciones de extracción.

## Sin verificar

- Cuántos sobrantes reales (no requisitos y repetidos) quita el filtro en el caso-00, y cuántos requisitos esperados se lleva. Se mide en la tarea de medición del caso-00.
- Que la segunda pregunta ("¿la oferta puede condicionarlo?") sea lo bastante distinta de la primera para frenar un error. Se verifica con la medición, no con tests con dobles.
- Cuánto aporta la unificación por texto: en la muestra, 2 de 30 sobrantes eran repetidas con texto idéntico.
- El tiempo del proceso completo extrapolado a 50 páginas con la pasada nueva (se informa, no bloquea).
