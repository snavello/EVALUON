# ADR-0070 · Instrucciones y reglas simples: largo máximo, sin ejemplos de casos, desempate a la corta y tres salidas por celda

Estado: aceptado · Fecha: 2026-10-15 · Propuso: planificador (plan 016) · Decidió: responsable del proyecto (2026-10-15, «Apruebo el plan 016 y los ADR 0066 a 0070»)

## Contexto

Las instrucciones al modelo local crecieron por acumulación: `evaluacion-v12` tiene 161 líneas y unos 36.000 caracteres (alrededor de 9.000 tokens de un contexto de 32.768), `matriz-extraccion-v12` 207 líneas, `matriz-filtro-v9` 194; las 19 instrucciones vigentes medidas (matriz, evaluación, ficha, visión y las auxiliares, sin la consulta) suman 1.622 líneas. Cada ronda de la 015 agregó una regla por un fallo del caso-00 y parte de las mejoras viene de formas que enseñan los ejemplos (T-263, «Formas de la plantilla que enseñan los ejemplos»: la presentación física, recuperada en 7 de 7 casos, es una forma enseñada y no evidencia independiente, P7). El ADR-0065, punto 6, levantó la exigencia de la 015 de instrucciones idénticas para todos los modelos: cada modelo lleva la instrucción más corta que cumple la spec.

Además, una parte de los «no determinado» no los produce el modelo sino el código que convierte su respuesta: en `combine.py`, `done()` descarta la pregunta que el modelo escribió cuando el resultado es «no se encontró el documento» y `compose_question` devuelve vacío para un «no determinado» sin pregunta del modelo salvo en cuatro motivos; es el mecanismo de los pares O2 R16 (T-263) y O3 R22 (T-268), convertidos en «no se encontró el documento» sin la pregunta. La spec 016 (REQ-119 y REQ-120) pide instrucciones con solo definiciones y decisiones vigentes, sin ejemplos de casos y con un largo máximo escrito en el plan, y que toda celda termine en cumple, no cumple o no determinado con la pregunta o el documento nombrado.

## Alternativas

### A. Tope de caracteres y líneas por tipo de instrucción, sin ejemplos, tabla de decisiones aparte, y las tres salidas garantizadas por una invariante sin tocar el esquema (propuesta)

Se gana: un tope que se comprueba con un test sin modelo; una instrucción que se controla contra la tabla de decisiones; las celdas se corrigen en el código que las convierte, sin migración ni cambio de exportaciones. Se pierde: el rótulo «no se encontró el documento» sigue existiendo como forma de un «no determinado» con el documento nombrado, que es una lectura de las «tres salidas» de la spec (ver plan, «Puntos para el Coordinador»).

### B. Tope en tokens (con el tokenizador del motor)

Se gana: mide lo que importa al contexto. Se pierde: el tokenizador vive en el motor, así que el test necesitaría el motor encendido y no correría en la suite sin GPU. Los caracteres y las líneas son una buena aproximación estable.

### C. Acortar solo las instrucciones y dejar las reglas del código como están

Se gana: menos cambios. Se pierde: queda la causa de los «no determinado» sin pregunta, que REQ-120 pide eliminar.

### D. Colapsar «no se encontró el documento» y «no aplica» en «no determinado» con migración

Se gana: tres salidas literales. Se pierde: cambia la enumeración de resultados (ADR-0038, regla 3; ADR-0043), el esquema, las exportaciones, el historial de decisiones de la Comisión y la verdad de T-229, que ya usa esos rótulos; es una decisión de fondo del responsable que la spec no pide.

## Decisión

Se propone **A**.

1. **Largo máximo.** Instrucciones decisoras (extracción, filtro, evaluación y la de la matriz externa): **90 líneas y 9.000 caracteres**, con el bloque de definiciones ya incluido. Las demás (contraste, cláusulas, completitud, unión, consecuencias, circulares, respaldo, visión, ficha, ficha por renglón, reescritura, informe técnico, nombre del oferente, datos del procedimiento, consulta, verificador): **50 líneas y 5.000 caracteres**. El bloque común de definiciones: **5.000 caracteres**. Cada descripción de campo del esquema de salida: **80 caracteres**, para que el texto no se mude al esquema. Razón: 9.000 caracteres son un cuarto de `evaluacion-v12` y dejan a la instrucción unos 2.500 tokens, con lo que cada pedido de lectura recupera más de 6.000 tokens de documentos de la oferta; las demás vigentes van de 31 a 130 líneas y 5.000 caracteres obligan a las más largas (ficha por renglón, 130; ficha, 107; respaldo, 92) a quedarse con lo decidido.
2. **Qué lleva y qué no.** Lleva las definiciones y decisiones vigentes de las specs y los ADR, en términos generales, y el esqueleto de la salida con marcadores. No lleva ejemplos con contenido de licitación, reglas nacidas de un fallo de un caso ni texto que el código ya garantiza. Cada instrucción tiene su tabla de decisiones en `specs/016-calidad-medible/revision-instrucciones.md` (oración por oración).
3. **Sin calco.** Una prueba compara cada instrucción con el cuerpo de los pliegos, las circulares, las ofertas y los dictámenes de los casos 00 a 06 y del caso chico: 0 secuencias de 6 palabras seguidas en común. Se salta si `corpus/` no está montado.
4. **Desempate a la corta (REQ-119).** Si las medidas graves no empeoran y las demás empatan (los tamaños del ADR-0059), queda la instrucción corta. Es una excepción acotada a la regla 4 del ADR-0059 («en empate queda lo que ya está»), por decisión de la spec.
5. **Tres salidas por celda.** Cada resultado guardado es: «cumple» con fundamento (cita de la oferta, dato del Portal, ausencia verificada con los documentos nombrados, criterio de la Comisión); «no cumple» con cita; o «no determinado» —o «no se encontró el documento», que es su forma cuando el pliego exige un documento y se leyeron todos— con la pregunta a la Comisión o el documento o consulta que falta nombrados. «No aplica» sigue siendo la forma de un «no determinado» decidido por regla (forma de garantía no elegida, opción no usada) con su motivo nombrado. Una invariante comprueba la forma de cada celda para todas las combinaciones de resultados de grupo, contraste y reglas; una conversión del código que no la cumpla deja una anomalía.
6. **Qué se conserva.** La cita literal verificada (ADR-0038), el dato del Portal (ADR-0053), el cumple por ausencia y el criterio del IVA (ADR-0058) y la presentación física (decisión del 2026-10-12). Los tests `decision_literal` siguen verdes; si uno exigiera cambiar, se frena y se consulta al responsable.
7. **Las versiones publicadas no se editan.** Las instrucciones nuevas son versiones nuevas y sus huellas se suman a `tests/fixtures/instrucciones.sha256`.

## Consecuencias

- Más fácil: controlar una instrucción contra la tabla de decisiones; que un pedido de lectura recupere más texto de la oferta; encontrar de dónde sale cada «no determinado» sin pregunta.
- Más difícil: reescribir las instrucciones vigentes sin usar los casos como ejemplo; la lista presente de la matriz tiene que ser igual o mejor en cada caso de ajuste (REQ-119), que es más estricto que la regla 2 del ADR-0059; las medidas se pueden mover por el cambio de formas enseñadas (la presentación física), y se explican fila por fila.
- Para revertir: volver las versiones de `MATRIX_PROMPT_VERSIONS`, `ASSESSMENT_PROMPT_VERSIONS`, `OFFERS_PROMPT_VERSIONS`, `ASSESSMENT_VISION_PROMPT_VERSION`, `consulta` y `ASSESSMENT_RULES_VERSION` a las de la 015 (las huellas siguen congeladas) y revertir los cambios de `combine.py` y de las reglas del Portal. No hay migración.
