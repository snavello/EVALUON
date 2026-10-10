# ADR-0055 · Cómo se pide al modelo: razonamiento en el JSON antes del veredicto, ejemplos balanceados, contexto en lugar de volumen y registro de cada instrucción

Estado: propuesto · Fecha: 2026-10-10 · Decidió: — (el responsable pidió revisar «exhaustivamente» cómo se promptea, 2026-10-10; el diseño, el Planificador)

## Contexto

El diagnóstico del 2026-10-10 y la revisión exhaustiva de las instrucciones (informe local `revision-instrucciones.md`, con seis pedidos de prueba a la GPU, de a uno) encontraron, con el modelo y el caso LPU25:

- **El veredicto sale antes que lo que lo sostiene.** llama.cpp genera los campos en el orden del esquema: en la evaluación `resultado` sale primero y `externo` e `ilegible`, que la instrucción dice que «ganan», salen después; lo mismo en el filtro, el contraste, el informe técnico y la consulta. El pensamiento nativo del motor está apagado en todo (`--reasoning off`, `enable_thinking: false`, ADR-0002), con temperatura 0, semilla 42 y JSON estricto.
- **Razonar antes no basta por sí solo.** Con las definiciones viejas, pedir `razon` antes no cambió el filtro (15 de 15 «mantener»); con las definiciones nuevas, la decisión la cambian las definiciones (13 de 15 «descartar») y el razonamiento mejora el motivo elegido y deja fundamento visible. Cuesta entre 40 y 50 % más de tokens de salida en el filtro (unos 15 s por lote de 15 filas). En la evaluación, con el bloque del Portal y el razonamiento primero, la propuesta pasó a «cumple» citando el dato y la pregunta fue a la Comisión; el razonamiento supuso una condición que no tenía dato (el IVA), lo que pide una regla de «cada condición con su dato».
- **«Fragmento mínimo» y contraste sin contexto.** La instrucción pide el fragmento mínimo, en la misma línea que pide hasta 1.000 caracteres; el contraste lo juzga «por sí solo»: de ahí las 9 celdas «sin corroborar» con la pregunta fija genérica.
- **Ejemplos desbalanceados.** En el filtro, 5 de 7 son «mantener»; en la evaluación, 6 de 11 terminan en «no determinado» y ninguno es «cumple» con el Portal ni con un requisito de dos condiciones.
- **Contexto ocioso.** La matriz usa de 4.000 a 5.000 tokens de un contexto de 32.768 (lote de extracción de 1.500 tokens, filtro de 15 filas); el requisito llega a la evaluación sin su punto ni su encabezado; el Portal no le llega al modelo.
- **Registro.** Cada pedido guarda su cuerpo completo (con la instrucción literal) y cada corrida el nombre de la versión, pero no la huella del archivo de instrucción; el cuerpo registra el modelo de `generation` también en los pedidos de lotes; los tokens se cuentan con el servidor de `generation`, que es Gemma, aunque el motor de lotes cambie.
- Los candidatos Qwen (ADR-0056) «piensan» por defecto y el pensamiento se apaga por pedido con la misma variable de plantilla, `enable_thinking`; los benchmarks de sus fichas son con pensamiento.

Restricciones: la salida sigue siendo un JSON con esquema que el sistema valida (ADR-0002, ADR-0038); la comparación de modelos usa las **mismas** instrucciones (spec 015, fuera de alcance); todo pedido registra la versión de su instrucción (P6, REQ-106); el caso-00 completo debe entrar en 60 minutos de GPU (hoy 13,5 + 23).

## Alternativas

### A. Encender el pensamiento nativo del motor
Se gana: razonamiento más largo, el que los modelos traen entrenado. Se pierde: tokens y tiempo sin tope fino (en 243 evaluaciones largas se pasaría de los 60 minutos); el ADR-0002 documentó fallas de la salida estructurada con modelos que piensan; cada modelo lo prende distinto, lo que ensucia la comparación; el texto pensado no queda dentro del JSON validado; cambiarlo exige reiniciar el servidor.

### B. Una propiedad `razonamiento` (texto breve, con tope) antes del veredicto, con el pensamiento nativo apagado (propuesta)
Se gana: como el modelo escribe en orden de esquema, razona (y cita) antes de decidir; el esquema lo obliga, no hace falta confiar en la instrucción; queda guardado en el pedido (P6) y se puede mostrar (P3); funciona igual en todos los modelos; el costo está acotado. Se pierde: entre 40 y 50 % más de tokens de salida donde se usa; un razonamiento corto no equivale a pensar largo; hay que ajustar los esquemas, las lecturas de la salida y los máximos de tokens.

### C. Dos pedidos por decisión: razonar y después decidir
Se gana: separación limpia. Se pierde: duplica los pedidos (los 23 minutos de la evaluación pasarían a unos 45); más superficie de fallas.

## Decisión

Se propone **B**, con estas reglas:

1. **Dónde.** `razonamiento` va primero en el filtro (preguntas A y B), la evaluación, el contraste y el contraste por cláusula. En la evaluación el orden del esquema es: `razonamiento` (de 2 a 4 oraciones), citas, `externo` e `ilegible`, `datos`, `resultado`, `explicacion`, `pregunta`. En el informe técnico y la consulta, las citas o las afirmaciones van antes del veredicto o del estado, y se mide (T-248, T-249). En la extracción y la completitud no se agrega razonamiento: el costo es por tramo.
2. **Tope.** El razonamiento tiene un máximo de caracteres en el esquema y en la instrucción (se fija en T-252 y T-237, de partida unos 400); los máximos de salida suben lo justo y se registran con la corrida.
3. **Qué se le pide razonar.** La cita primero (la oración completa), después qué exige el requisito, qué dice la cita y qué dato tiene cada condición, y recién ahí el veredicto. Se sacan «fragmento mínimo» y «ante la duda, no determinado»: la duda real se declara con su razón (qué dato falta o qué texto contradice). Un requisito de varias condiciones no es «cumple» si a una le falta el dato.
4. **Ejemplos balanceados.** Cada instrucción lleva ejemplos de cada salida posible en proporciones parecidas (ninguna sale del 40 al 60 % en el filtro; en la evaluación 3 «cumple», uno de ellos con el Portal, 2 «no cumple», 2 «no consta», 3 «no determinado»), de otro objeto de contratación, con la forma y la variedad de los documentos reales, y nunca con lo que hay que dejar de hacer.
5. **Contexto en lugar de volumen.** El encabezado del punto para cada fila de la matriz; el requisito con su punto completo y la oración citada entre `<<< >>>`; la página o el contexto de la cita para el contraste; los datos del Portal como bloque citable `[P…]` antes del requisito. Lotes: extracción de 3.000 a 4.000 tokens, filtro de 5 a 8 filas. Son parámetros de `settings.py` que se registran en cada propuesta (P6); cambiarlos exige volver a medir (P7).
6. **Las preguntas van a la Comisión.** Las instrucciones lo dicen y los ejemplos que preguntaban un dato que solo tiene el oferente se corrigen; el código arma el resto (ver T-235).
7. **Reintento con memoria.** El reintento le muestra al modelo su respuesta anterior (como turno del asistente) y la cita que no se ubicó, y le pide la oración completa, en lugar de sugerirle «no_determinado».
8. **Registro.** Cada instrucción guarda su huella SHA-256 junto a su versión en `prompt_versions`, y un test congela las versiones publicadas (como `scripts/models.sha256` con los modelos); cada pedido de lotes registra en su cuerpo el alias del modelo que lo atiende y cuenta los tokens con ese motor (T-251), para que cambiar de modelo no deje datos de otro. Cada pedido guarda además la versión de su instrucción en su `parsed`.
9. **Lo que no se hace.** No se deja el pensamiento nativo decidible por pedido (sacar el presupuesto 0 del servidor): ningún requisito lo pide (P10); si una medición futura lo necesita, se decide con su ADR. Tampoco se cambia la temperatura 0 ni la semilla: valen para citas literales y reproducibilidad (P6); con Qwen y sin pensamiento sigue siendo aceptable, y no se usa `presence_penalty`.

## Consecuencias

Más fácil: se puede leer por qué el modelo concluyó lo que concluyó; los errores de uso se distinguen de los del modelo (el diagnóstico lo necesitó y no pudo hacerlo por falta de este dato); la comparación de modelos es más justa.

Más difícil: más tokens de salida (tiempo de GPU hacia arriba; se mide); el razonamiento puede contener texto del caso: el registro es de la base, no del repositorio (P4); hay que mantener las instrucciones y los esquemas juntos (una versión de instrucción va con una versión de esquema); el bloque del Portal le agrega al modelo una fuente que hay que citar bien.

Para revertir: volver a las versiones anteriores de las instrucciones (`evaluacion-v5`, `contraste-v2`, `clausulas-v2`, `matriz-filtro-v2`) y a los parámetros de lote anteriores. El campo `razonamiento` ya guardado queda como historia.

## Sin verificar

- Cuántos tokens suma el razonamiento en el caso-00 completo y cuánto sube el tiempo: se mide en T-239; si con el 12B el caso-00 completo supera los 60 minutos, el hallazgo vuelve a este ADR antes de medir candidatos.
- Que un razonamiento de unas pocas oraciones alcance en español jurídico, y que el bloque del Portal no lleve al modelo a suponer condiciones sin dato: se mide en T-239.
- Que `llama-server` respete el orden de las propiedades del esquema con los modelos Qwen y con la compilación fijada: con el 12B lo mostraron las pruebas de la revisión; con los candidatos lo comprueba T-243 (y T-245).
- Que llama.cpp aplique la gramática JSON después del bloque de pensamiento si alguna vez se enciende: no se usa en este plan.
