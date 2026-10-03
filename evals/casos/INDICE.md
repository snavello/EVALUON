# Conjunto dorado de la feature 001 · borrador

Borrador para validar. Ningún caso tiene visto bueno: todos llevan `validado_por: pendiente` y `redactado_por: borrador asistido`. La respuesta esperada la valida una persona que conoce la materia (`evals/README.md`).

Fuentes: solo el anexo de la Disposición AFIP 247/2022 (`corpus/normativa/disp-afip-247-2022-anexo.pdf`), su cuerpo (`disp-afip-247-2022-original.htm`) y la Disposición AFIP 297/03 con su Anexo I (`disp-afip-297-2003-original.htm`). Cada `origen` transcribe el texto de la norma y se comprobó por programa que aparece tal cual en el texto extraído (salvo espacios y saltos de línea). En los casos sin respuesta, `origen` explica por qué no hay respuesta; en los de tema cercano EV-032 y EV-033, además, anota la búsqueda por palabras que comprueba que ninguna norma cargada trata el tema.

## Composición

Todos los casos son del lote de ajuste (ninguno lleva el campo `lote`).

| Grupo | Casos | Cantidad |
|---|---|---|
| Con respuesta en la 247/2022 (fecha desde 2023-01-02) | EV-001 a EV-015; EV-027 y EV-028 (remisión a norma no cargada) | 17 |
| Con respuesta en la 297/03 (fecha entre 2003-06-14 y 2023-01-01) | EV-016 a EV-024; EV-029 (remisión a norma no cargada) | 10 |
| Sin respuesta, fecha bajo la 247/2022 | EV-025, EV-026 (ajenas); EV-033 (tema cercano) | 3 |
| Sin respuesta, fecha bajo la 297/03 | EV-030 (ajena); EV-032 (tema cercano) | 2 |
| Sin respuesta, fecha sin régimen (anterior a 2003-06-14) | EV-031 | 1 |
| **Total** | | **33** |

- Pares (REQ-020): EV-001 y EV-016; EV-003 y EV-017; EV-014 y EV-018; EV-022 y EV-028 (desde T-064).
- `aviso_modificatorias` verdadero: los 10 casos con respuesta en la 297/03. Falso: todos los demás.
- REQ-018 y REQ-019 (categorías y marco nacional): sin casos. No hay documentos de esas categorías en el corpus; quedan pendientes, a cubrir con casos sintéticos cuando se decida. `difieren` es falso en todos.

## Casos

| Id | Pregunta (resumida) | Régimen | Fecha | Esperado (resumido) | Cita | Pareja |
|---|---|---|---|---|---|---|
| EV-001 | Plazo de mantenimiento de oferta si el pliego no lo fija | 247/2022 | 2023-01-02 | 60 días corridos desde la apertura; prórroga automática | Anexo, art. 43 | EV-016 |
| EV-002 | Clases de garantías y porcentajes | 247/2022 | 2024-04-08 | Mantenimiento 5 %, cumplimiento 10 %, contragarantía por el adelanto | Anexo, art. 64 a) b) c) | |
| EV-003 | Plazo para integrar la garantía de cumplimiento | 247/2022 | 2024-03-15 | 10 días desde el perfeccionamiento, prorrogable | Anexo, art. 61 | EV-017 |
| EV-004 | ¿Garantía de oferta si se cotiza poco? | 247/2022 | 2025-07-21 | No, si la oferta no supera M 1.000 | Anexo, art. 66 f) | |
| EV-005 | Plazo para observar el dictamen de evaluación | 247/2022 | 2023-05-02 | 3 días; 1 día en contratación directa | Anexo, art. 57 | |
| EV-006 | Impugnación del acto de aprobación y efecto | 247/2022 | 2024-09-30 | 5 días; revisión en 5 días; no suspensiva | Anexo, art. 59 | |
| EV-007 | Multa por mora si el pliego no la prevé | 247/2022 | 2025-03-12 | 0,1 % por día hábil; tope 100 % | Anexo, art. 88 c) | |
| EV-008 | Sanciones aplicables | 247/2022 | 2023-08-14 | Apercibimiento, suspensión, inhabilitación | Anexo, art. 92 | |
| EV-009 | Modalidades de los procedimientos | 247/2022 | 2026-02-03 | Las ocho del art. 24 | Anexo, art. 24 a) a h) | |
| EV-010 | Garantía en orden de compra abierta | 247/2022 | 2024-06-17 | 5 % sobre máximo de unidades × precio unitario | Anexo, art. 24 b) | |
| EV-011 | Publicidad de la licitación pública | 247/2022 | 2023-10-09 | BO 2 días hábiles, 7 días corridos de antelación, más comunicaciones, invitaciones y difusión | Anexo, art. 33 a) | |
| EV-012 | ¿Se subsana la oferta económica sin firma? | 247/2022 | 2025-11-24 | No; desestimación sin subsanación | Anexo, art. 55 j) | |
| EV-013 | Orden de prelación de los documentos | 247/2022 | 2024-01-22 | Régimen, normas, pliego y circulares, oferta, muestras, adjudicación, orden de compra | Anexo, art. 7 | |
| EV-014 | ¿El pliego puede agregar causales de desestimación? | 247/2022 | 2025-02-10 | No (no subsanables) | Anexo, art. 55, anteúltimo párrafo | EV-018 |
| EV-015 | Aumento o disminución del contrato | 247/2022 | 2026-05-04 | Hasta 20 % sin conformidad; nunca más de 35 % | Anexo, art. 79 | |
| EV-016 | Plazo de mantenimiento de oferta si el pliego no lo fija | 297/03 | 2022-12-31 | 30 días desde la apertura; prórroga automática | Anexo I, art. 39 | EV-001 |
| EV-017 | Plazo para integrar la garantía de cumplimiento | 297/03 | 2019-08-20 | 8 días; si no, rescisión y pérdida de la garantía de oferta | Anexo I, art. 55 inc. 6) | EV-003 |
| EV-018 | ¿El pliego puede agregar causales de desestimación? | 297/03 | 2010-04-05 | Sí, expresa y fundadamente (inadmisibilidad) | Anexo I, art. 43 i) | EV-014 |
| EV-019 | Requisitos y plazo para impugnar la adjudicación | 297/03 | 2003-06-14 | 5 días y depósito del "cinco por mil (0,5 ‰)" de la oferta | Anexo I, art. 53 | |
| EV-020 | Multa por prórroga del plazo de entrega | 297/03 | 2012-09-10 | 1 % cada 7 días corridos o fracción mayor de 3 | Anexo I, art. 58 inc. 10) | |
| EV-021 | ¿Garantía de oferta en contratación directa? | 297/03 | 2016-03-01 | No | Anexo I, art. 55 inc. 3) d) | |
| EV-022 | Integración de la Comisión Evaluadora | 297/03 | 2008-11-17 | Mínimo 3 titulares: presidente y 2 vocales, de planta permanente | Anexo I, art. 48 | EV-028 |
| EV-023 | Garantía en orden de compra abierta | 297/03 | 2014-05-26 | Garantía de adjudicación del 10 % sobre máximo × precio unitario | Anexo I, art. 25 inc. 3) b) | |
| EV-024 | Plazo para observar el acta de evaluación | 297/03 | 2021-07-05 | 3 días; 2 días en privadas y directas | Anexo I, arts. 50 y 21 f) | |
| EV-025 | Licencia por maternidad de una agente | 247/2022 | 2024-05-02 | No determinado (ajena) | — | |
| EV-026 | Alícuota general del IVA | 247/2022 | 2023-09-01 | No determinado (ajena) | — | |
| EV-027 | Monto máximo de la licitación privada | 247/2022 | 2025-06-30 | Remisión: el monto es el que estipula el régimen jurisdiccional vigente (no cargado); sin cifra | Anexo, art. 21 c) | |
| EV-028 | Integración de la Comisión Evaluadora | 247/2022 | 2024-11-11 | Remisión: integración sujeta a la normativa vigente (no cargada); los integrantes no pueden ser funcionarios con competencia para autorizar o aprobar | Anexo, art. 50 | EV-022 |
| EV-029 | Monto máximo de la contratación directa por monto | 297/03 | 2015-10-01 | Remisión: el monto es el que establece el Régimen Jurisdiccional vigente (no cargado); sin cifra | Anexo I, art. 21 inc. 4) punto 9 | |
| EV-030 | Vencimiento de la DDJJ de ganancias | 297/03 | 2018-04-16 | No determinado (ajena) | — | |
| EV-031 | Plazo de mantenimiento de oferta | sin régimen | 2003-06-13 | No determinado (`no_regime_at_date`) | — | |
| EV-032 | Horas anuales de capacitación del personal de compras | 297/03 | 2011-05-16 | No determinado (tema cercano que ninguna norma cargada trata ni remite) | — | |
| EV-033 | Cada cuánto rota el personal de compras | 247/2022 | 2025-09-15 | No determinado (tema cercano que ninguna norma cargada trata ni remite) | — | |

## Para mirar con atención

1. **EV-019, el depósito para impugnar.** La 297/03 dice "CINCO POR MIL (0,5 ‰)". Cinco por mil es 5 ‰ (0,5 %), así que la cifra en palabras y la cifra en número no coinciden. El esperado repite el texto. Hay que decidir qué dato exigir en `datos_clave`; quizás alguna de las modificatorias sin cargar lo corrigió.
2. **EV-024, el plazo para observar el acta de evaluación bajo la 297/03.** El art. 50 da 3 días, la pauta f) del art. 21 da 2 días en licitaciones privadas y contrataciones directas, y la pauta g) dice que en las contrataciones directas el acta puede no notificarse y "no será impugnable". El esperado toma el art. 50 y la pauta f). Conviene acotar la pregunta a la licitación pública, o aceptar la respuesta con los dos plazos.
3. **Resuelto por el ADR-0015 (2026-10-03): EV-027, EV-028 y EV-029 pasaron a ser preguntas con respuesta de remisión a una norma no cargada (T-064; ver "Remisión a una norma no cargada (ADR-0015)", más abajo).** Texto original del punto: **EV-027, EV-028 y EV-029: preguntas cercanas sin respuesta.** La norma no da la cifra ni la integración, pero sí remite a otra normativa (el régimen jurisdiccional o la "normativa vigente"). Un sistema que responda "lo fija el régimen jurisdiccional vigente" citando el artículo no inventa nada. Hay que decidir si eso cuenta como abstención correcta o como respuesta correcta. Se marcaron "no determinado" porque la pregunta pide una cifra o una integración que el corpus no tiene. En EV-028 el art. 50 sí dice quiénes no pueden integrar la Comisión; si se quiere un caso sin ambigüedad, se puede cambiar la pregunta a "¿Cuántos miembros tiene...?".
4. **EV-014 y EV-018, el par con respuestas opuestas.** La 247/2022 prohíbe agregar causales "no subsanables"; no dice nada de causales subsanables. La 297/03 habla de "inadmisibilidad", no de "desestimación". La pregunta usa "desestimar" en los dos casos para que sea la misma; verificar que la equivalencia sea aceptable.
5. **EV-016, el cómputo de los 30 días.** El art. 39 de la 297/03 no dice si los días son corridos o hábiles. Por su art. 8, los plazos se computan en días hábiles administrativos salvo disposición en contrario. El esperado dice "30 días" sin calificarlos; si se exige "hábiles", habría que sumar el art. 8 a `unidades`.
6. **Todos los casos de la 297/03 (EV-016 a EV-024).** Se responden con el texto original de 2003. Infoleg registra 32 modificatorias sin cargar; cualquiera puede haber cambiado un plazo o un porcentaje. Para la medición está bien, porque el sistema solo conoce ese texto; y el aviso de modificatorias existe por eso mismo. Lo que sí hay que revisar es cada caso cuando se cargue una modificatoria.
7. **`aviso_modificatorias` en los casos sin respuesta con fecha bajo la 297/03 (EV-030, EV-032; hasta T-064 también EV-029, que ahora cita la 297/03 y lleva el aviso en verdadero).** Se marcó falso, porque una respuesta "no determinado" no muestra unidades de la 297/03 y la spec pide el aviso solo cuando se muestra una unidad. Confirmar que la pantalla no muestra unidades recuperadas cuando se abstiene.
8. **EV-026, una trampa.** El art. 41 de la 247/2022 menciona el IVA (la AFIP es consumidor final), pero no fija ninguna alícuota. Una respuesta que cite el art. 41 para dar una alícuota es incorrecta.
9. **EV-004, el valor del módulo.** El esperado se queda en "M 1.000". El valor en pesos del módulo lo fija la máxima autoridad (art. 99) y no está cargado.
10. **EV-012.** Solo exige el art. 55. El art. 38 remite al 55 para la oferta económica sin firma; si se quiere exigir también, hay que agregarlo a `unidades`.
11. **EV-031.** Es la misma pregunta que el par EV-001 y EV-016, pero no tiene `pareja`: el plan exige que los dos casos de un par citen normas distintas, y este no cita ninguna. Lo mismo pasaba con EV-022 y EV-028; desde T-064, EV-028 cita la 247/2022 y el responsable aprobó el par EV-022 / EV-028 (2026-10-03).
12. **Las claves de `unidades`.** Están a nivel de artículo (`anexo/art-43`, `anexo-i/art-55`), y el inciso va en `cita.ubicacion`. Según el plan, cuando un caso nombra un inciso vale el artículo que lo contiene. No se usaron claves de inciso porque la forma de los puntos numerados dentro de incisos (por ejemplo, art. 33 a) 1.) no está fijada en el plan.

## Reescritura de datos clave (2026-10-03)

**Propuesta pendiente del visto bueno del responsable.** Solo cambia `datos_clave`; `pregunta`, `esperado`, `unidades`, `regimen`, `fecha_autorizacion` y `visto_bueno` quedan como estaban.

Motivo: 21 datos clave de 16 casos no aparecían ni en su `esperado` ni en el texto de la norma (por ejemplo, "desde el acto de apertura" cuando la norma dice "contados a partir de la fecha del acto de apertura"), así que ninguna respuesta podía cumplirlos tal como los compara `key_data_missing` (`evaluon/queries/evaluation.py`). Cada dato nuevo es un fragmento corto que una respuesta correcta tiene que contener, que aparece en el `esperado` y que aparece o se deduce literalmente del `origen`. Los datos compuestos se partieron en varios. Los datos que ya se cumplían se dejaron igual.

Comprobado en el contenedor: los 24 casos con respuesta cumplen sus datos clave contra su propio `esperado`, y una respuesta contraria plausible armada a mano para cada uno (otro plazo, otro porcentaje u otra polaridad) no los cumple.

| Caso | Datos anteriores | Datos nuevos |
|---|---|---|
| EV-001 | "60 días corridos", "desde el acto de apertura", "prórroga automática", "5 días hábiles" | "60 días corridos", "acto de apertura", "se prorroga automáticamente", "5 días hábiles" |
| EV-002 | "mantenimiento de la oferta 5 %", "cumplimiento del contrato 10 %", "contragarantía" | "5 %", "mantenimiento", "10 %", "cumplimiento", "contragarantía" |
| EV-003 | "10 días", "prorrogable por igual término" | "10 días", "por igual término" |
| EV-004 | "M 1.000", "no es necesaria" | "no", "M 1.000" |
| EV-005 | "3 días", "1 día en contratación directa" | "3 días", "1 día", "contratación directa" |
| EV-006 | "5 días", "revisión ante la máxima autoridad", "no suspensivo" | "5 días", "revisión", "máxima autoridad", "suspensivo" |
| EV-007 | "0,1 %", "por cada día hábil de atraso", "tope 100 %" | "0,1 %", "por cada día hábil de atraso", "100 %" |
| EV-010 | "5 %", "máximo de unidades por precio unitario" | "5 %", "máximo", "unidades", "precio unitario" |
| EV-011 | "Boletín Oficial 2 días hábiles", "7 días corridos de antelación" | "Boletín Oficial", "2 días hábiles", "7 días corridos de antelación" |
| EV-012 | "no", "desestimación sin subsanación" | "no", "sin posibilidad de subsanación" |
| EV-013 | "régimen", "normas que se dicten en consecuencia", "pliego con circulares", "oferta", "muestras", "adjudicación", "orden de compra o contrato" | "régimen", "normas que se dicten en consecuencia", "pliego", "circulares", "oferta", "muestras", "adjudicación", "orden de compra" |
| EV-015 | "20 %", "35 %", "conformidad previa por encima del 20 %" | "20 %", "35 %", "conformidad" |
| EV-016 | "30 días", "desde el acto de apertura", "prórroga automática" | "30 días", "acto de apertura", "se prorroga automáticamente" |
| EV-019 | "5 días", "depósito 0,5 ‰ del valor de la oferta" | "5 días", "5 por mil" |
| EV-023 | "10 %", "máximo de unidades por precio unitario" | "10 %", "máximo de unidades", "precio unitario" |
| EV-024 | "3 días", "2 días en licitaciones privadas y contrataciones directas" | "3 días", "2 días", "licitaciones privadas", "contrataciones directas" |

Puntos para decidir al dar el visto bueno:

1. **EV-006, "suspensivo".** Lo que el caso quiere medir es que la impugnación *no* suspende. El `esperado` dice "no tienen efecto suspensivo" y la norma "En ningún caso ... tendrá carácter suspensivo": no hay un fragmento negativo común y corto que una respuesta correcta deba traer. "suspensivo" solo comprueba que la respuesta trate el punto, no su sentido; una respuesta que diga "tiene efecto suspensivo" con los plazos correctos lo cumpliría. Si se quiere medir la polaridad, la alternativa es "no tienen efecto suspensivo", a costa de rechazar respuestas correctas redactadas de otra forma ("no suspende el trámite").
2. **EV-001 y EV-016, "se prorroga automáticamente".** Aparece en el `esperado`; la norma dice "prorrogado automáticamente" (247/2022) y "prorrogada automáticamente" (297/03), así que se deduce pero no es literal. Una respuesta correcta que diga "prórroga automática" no lo cumple. La alternativa más tolerante es "automáticamente" solo.
3. **EV-019, "5 por mil".** Se exige la cifra en palabras de la norma ("CINCO POR MIL"), no el "(0,5 ‰)", porque las dos no coinciden (ver el punto 1 de "Para mirar con atención"). Una respuesta que diga solo "0,5 ‰" no lo cumple. Se sacó "depósito" porque la norma y el `esperado` dicen "depositado" y "depositar".
4. **EV-013, el orden.** Los datos clave comprueban que estén los siete documentos, no el orden de prelación; una respuesta con los siete en otro orden los cumple. "oferta", "pliego" y "régimen" son palabras comunes, pero son los nombres de los documentos y no hay forma más corta de exigirlos.
5. **EV-010, "máximo" y "unidades" por separado.** El `esperado` dice "máximo de unidades" y la norma "máximo de las unidades": se partieron para que valgan las dos redacciones. En EV-023 la norma sí dice "máximo de unidades" y se dejó junto.
6. **EV-015, "conformidad".** Comprueba que la respuesta trate la conformidad del contratista, no que la ubique por encima del 20 %; esa relación no se puede exigir con un fragmento corto común al `esperado` y a la norma.

## Visto bueno provisorio (2026-10-03)

El responsable autorizó el 2026-10-03 un visto bueno provisorio para los 31 casos, para poder calibrar (T-045) y correr el conjunto (T-046). Los casos se revisan con la Comisión y se corrigen a medida que aparezcan errores. Decisiones del responsable sobre los datos clave dudosos: más tolerantes. EV-001 y EV-016 piden "automáticamente"; EV-006 queda con "suspensivo" (los plazos frenan las respuestas equivocadas); EV-019 queda con "5 por mil", porque "0,5 ‰" es otra cantidad (la duda sobre la cifra sigue marcada). EV-004 pasa de "no" a "no es necesario": la regla del sí y del no exige un signo después de la palabra y la respuesta esperada no lo tiene.

## Reescritura por el ADR-0011 (2026-10-03)

**Propuesta de T-059, para el visto bueno del responsable en el pull request.** Aplica el ADR-0011 y el plan ("Datos clave y corrector"): cada dato es una pieza corta, las frases compuestas se parten y un dato puede traer variantes, sostenidas en el `esperado` o en el `origen` del caso. Solo cambia `datos_clave`, en 11 casos; `pregunta`, `esperado`, `unidades`, `regimen`, `fecha_autorizacion`, `visto_bueno` y los demás campos quedan como estaban, y el visto bueno provisorio se mantiene. Una lista entre corchetes es un dato con sus variantes: se cumple con cualquiera.

Sin cambios: EV-001, EV-002, EV-005, EV-006, EV-008, EV-009, EV-010, EV-013, EV-015, EV-017, EV-019, EV-023, EV-024 (ya cumplen las reglas) y los 7 casos sin respuesta. Se mantienen las decisiones del responsable del 2026-10-03 sobre EV-001 y EV-016 ("automáticamente"), EV-006 ("suspensivo") y EV-019 ("5 por mil"); la de EV-004 se propone cambiar (punto 2). EV-017 no se tocó: la respuesta de la corrida omite la pérdida de la garantía y eso es una respuesta incompleta, no una forma de decirlo.

| Caso | Dato antes | Dato después | Motivo |
|---|---|---|---|
| EV-003 | "por igual término" | ["igual término", "período igual"] | Pieza más corta, sin "por" (esperado y origen). "período igual": **tomada de la corrida** (punto 1) |
| EV-004 | "no es necesario" | ["no", "no es necesario"] | Un "no" con su variante escrita, la forma que da el ADR-0011. Cambia una decisión del responsable (punto 2) |
| EV-004 | "M 1.000" | ["M 1.000", "1.000 módulos"] | El esperado dice "mil módulos" y el origen "UN MIL MÓDULOS" |
| EV-007 | "por cada día hábil de atraso" | "día hábil" | Frase de la norma: queda la unidad |
| EV-011 | "7 días corridos de antelación" | "7 días corridos", "antelación" | Frase compuesta, partida en dos datos |
| EV-012 | "no" y "sin posibilidad de subsanación" (dos datos) | ["no", "sin posibilidad de subsanación"] (un dato) | El "no" con la forma que usan el esperado y el origen, como el ejemplo del plan (punto 3) |
| EV-014 | "no" | ["no", "no pueden prever", "no se podrán prever", "no pueden incluir"] | "no pueden prever" del esperado, "no se podrán prever" del origen. "no pueden incluir": **tomada de la corrida** (punto 1) |
| EV-016 | "acto de apertura" | ["acto de apertura", "fecha de apertura"] | "fecha de apertura": **tomada de la corrida** (la respuesta dice "fecha de apertura del acto"; es también el ejemplo del plan) (punto 1) |
| EV-018 | "sí" | ["sí", "otras causales de inadmisibilidad"] | El "sí" con la forma que usan el esperado y el origen (punto 4) |
| EV-018 | "expresa y fundadamente" | ["expresa y fundadamente", "expresarse y fundamentarse"] | "expresarse y fundamentarse": **tomada de la corrida** (punto 1) |
| EV-020 | "cada 7 días corridos" | "7 días corridos" | Cifra con su unidad |
| EV-020 | "fracción mayor de 3 días" | "fracción", "3 días" | Frase compuesta, partida en dos datos |
| EV-021 | "no" | ["no", "no es necesario", "no será necesario"] | "no es necesario" del esperado, "no será necesario" del origen |
| EV-022 | "presidente y 2 vocales" | "presidente", "2 vocales" | Frase compuesta, partida en dos datos |

**Comprobado** en un contenedor aparte (proyecto `evaluon-t059`): `load_cases` lee los 31 casos y ninguno queda mal formado; los 24 casos con respuesta cumplen sus datos clave con su propio `esperado` como única afirmación; y para cada uno, una respuesta contraria plausible armada a mano (otro plazo, otro porcentaje u otra polaridad: por ejemplo "Sí. El pliego puede prever otras causales…" en EV-014, o "No. El pliego no puede agregar otras causales de inadmisibilidad" en EV-018) no los cumple.

**Efecto en la corrida de T-045, recalificada** (`evals/corridas/2026-10-03T145904_30dc41e_gemma-4-12b-it-qat-q4_0_recalificada`): respuesta correcta 79,2 % (19 de 24), contra 45,8 % original y 50,0 % con el corrector nuevo y los datos anteriores. Sin las cuatro variantes tomadas de la corrida, 62,5 % (15 de 24). Siguen fallando EV-006, EV-009 y EV-017 (respuestas incompletas), EV-020 (frenada por el umbral) y EV-024 (artículo fuera de la selección); detalle en `specs/001-normativa/entorno.md`, sección T-059.

### Para decidir

1. **Cuatro formas de decirlo que salen de las respuestas del sistema, no del caso.** "período igual" en EV-003 (por "por igual término"), "no pueden incluir" en EV-014, "fecha de apertura" en EV-016 (por "acto de apertura") y "expresarse y fundamentarse" en EV-018 (por "expresa y fundadamente"). Si son formas correctas de decir el dato, quedan; si no, se sacan. Con las cuatro, la corrida recalificada da 79,2 %; sin ellas, 62,5 %. En EV-014 la respuesta dice que el pliego no puede incluir causales "que no estén expresamente enumeradas en la normativa", sin la palabra "no subsanables" del esperado.
2. **EV-004: aceptar también una respuesta que empiece con "No."** El 2026-10-03 se eligió "no es necesario" porque el "no" solo exigía un signo después de la palabra. Ahora el caso puede llevar las dos formas y valer cualquiera. EV-021 se escribió de la misma manera, con las formas de su esperado y su origen.
3. **EV-012: basta una de las dos formas.** Antes la respuesta tenía que traer el "No" y además "sin posibilidad de subsanación". Ahora basta con cualquiera de las dos: una respuesta que diga solo "No." pasa, y la que dice "serán desestimadas sin posibilidad de subsanación" también.
4. **EV-018: el "sí" se acepta si la respuesta dice que el pliego puede prever "otras causales de inadmisibilidad".** Esa frase podría aparecer también en una respuesta que diga que no; lo que frena esa respuesta es el segundo dato, "expresa y fundadamente", que una respuesta negativa no trae.

### Decisiones del responsable (2026-10-03)

1. Las cuatro formas que salieron de las respuestas del sistema **quedan**: el responsable las reconoce como formas correctas de decir el dato. Son "período igual" (EV-003), "fecha de apertura" (EV-016), "expresarse y fundamentarse" (EV-018) y "no pueden incluir" (EV-014). Se le mostraron con la tabla norma / respuesta del sistema. Criterio general del responsable: una forma que dice lo mismo que la norma se acepta. Igual se le consulta cada vez, con ejemplos (ADR-0011).
2. EV-004 acepta "no" o "no es necesario": aceptado.
3. EV-012 se cumple con cualquiera de las dos formas: aceptado.
4. EV-018 acepta el "sí" con "otras causales de inadmisibilidad": aceptado.

La medida que vale para aprobar la feature sale del lote de aceptación de T-061, que no se usa para ajustar (ADR-0014).

## Remisión a una norma no cargada (ADR-0015)

**Propuesta de T-064, para el visto bueno del responsable en el pull request.** Aplica el ADR-0015 y REQ-009 enmendado: cuando una norma cargada trata el tema y remite su contenido a otra norma que no está cargada, la respuesta dice lo que establece la norma cargada, con su cita, e indica a qué norma remite, sin dar el contenido de la norma no cargada. EV-027, EV-028 y EV-029 pasan a ser preguntas con respuesta del lote de ajuste. En los tres cambian solo `esperado`, `cita`, `origen`, `unidades`, `datos_clave`, `etiquetas`, `notas` y, en EV-029, `aviso_modificatorias`; `pregunta`, `fecha_autorizacion`, `regimen` y `visto_bueno` quedan como estaban; por el par aprobado, EV-028 y EV-022 suman además `pareja` y la etiqueta "dos fechas". El `origen` transcribe el texto de la unidad que remite y se comprobó por programa contra el texto extraído de `corpus/normativa/`; coincide con lo que citaba el `origen` anterior.

| Caso | Campo | Antes | Después |
|---|---|---|---|
| EV-027 | `esperado` | "no determinado" | La licitación privada es aplicable cuando el monto estimado no supere el estipulado en el régimen jurisdiccional vigente, y es válida cuando el monto a adjudicar no supere el máximo fijado en ese régimen; el anexo no fija el monto: remite al régimen jurisdiccional vigente |
| EV-027 | `cita` / `unidades` | vacías | Anexo de la 247/2022, art. 21, inciso c) / `anexo/art-21` |
| EV-027 | `origen` | Explicación de por qué no había respuesta | Texto del inciso c) del art. 21 del anexo |
| EV-027 | `datos_clave` | vacío | "régimen jurisdiccional" |
| EV-027 | `etiquetas` | "tema cercano que la normativa no resuelve" | "remisión a norma no cargada" |
| EV-027 | `aviso_modificatorias` | falso | falso (sin cambio: cita la 247/2022) |
| EV-028 | `esperado` | "no determinado" | En cada unidad con capacidad de contratación funciona una comisión evaluadora; su integración, funcionamiento y criterios de designación quedan sujetos a la normativa vigente; sus integrantes no pueden ser funcionarios con competencia para autorizar la convocatoria o aprobar el procedimiento |
| EV-028 | `cita` / `unidades` | vacías | Anexo de la 247/2022, art. 50 / `anexo/art-50` |
| EV-028 | `origen` | Explicación de por qué no había respuesta | Texto del art. 50 del anexo |
| EV-028 | `datos_clave` | vacío | "normativa vigente" |
| EV-028 | `etiquetas` | "tema cercano que la normativa no resuelve" | "remisión a norma no cargada" |
| EV-028 | `aviso_modificatorias` | falso | falso (sin cambio: cita la 247/2022) |
| EV-029 | `esperado` | "no determinado" | La contratación directa por monto procede cuando el monto del contrato no supere el establecido en el Régimen Jurisdiccional vigente; el Anexo I no fija el monto: remite al Régimen Jurisdiccional vigente |
| EV-029 | `cita` / `unidades` | vacías | Anexo I de la 297/03, art. 21, inciso 4), punto 9 / `anexo-i/art-21` |
| EV-029 | `origen` | Explicación de por qué no había respuesta | Encabezado del inciso 4) y texto del punto 9 del art. 21 del Anexo I |
| EV-029 | `datos_clave` | vacío | "régimen jurisdiccional" |
| EV-029 | `etiquetas` | "tema cercano que la normativa no resuelve" | "remisión a norma no cargada" |
| EV-029 | `aviso_modificatorias` | falso | verdadero (la respuesta cita la 297/03) |

En los tres casos, `notas` reemplaza la duda por la decisión del ADR-0015 y por las decisiones del responsable de más abajo.

Cada caso lleva un solo dato clave, el de la remisión, con las palabras de la norma. No lleva variantes: la norma nombra la remisión de una sola forma en cada unidad. En EV-028 no se exige el impedimento ("competencia para autorizar"): está en el `esperado`, pero no en `datos_clave` (decisión 3, más abajo).

**Casos nuevos de tema cercano: EV-032 y EV-033.** Dos preguntas de control "fuera de tema", una por régimen, del lote de ajuste y sin campo `lote` (decisión 1, más abajo). Son temas de compras que ninguna norma cargada trata ni remite a otra norma: la capacitación (EV-032, 297/03, 2011-05-16) y la rotación (EV-033, 247/2022, 2025-09-15) del personal que gestiona las compras. Se comprobó con una búsqueda por palabras, sin tildes ni mayúsculas, sobre el texto canónico de las dos disposiciones y sus anexos ("capacit", "horas", "entrenamiento", "rota", "personal de compras", "area de compras", "unidad de compras", "agentes del"): ninguna aparece. El detalle está en el `origen` de cada caso.

No se usó el ejemplo de referencia ("¿Qué plazo tiene la AFIP para pagar una factura de servicios públicos?"): las dos normas cargadas fijan el plazo de pago de las facturas en 30 días corridos (anexo de la 247/2022, art. 77; Anexo I de la 297/03, art. 58, inciso 7). El sistema podría responder ese plazo con su cita, así que la pregunta no es de un tema que ninguna norma trata.

**Comprobado** en un contenedor aparte (proyecto `evaluon-t064`), sin consultar al sistema:

- `load_cases` lee los 33 casos y ninguno queda mal formado ni sin visto bueno: 27 con respuesta y 6 sin respuesta, todos del lote de ajuste. EV-032 y EV-033 salen sin respuesta y con `lot == "ajuste"`.
- El `origen` de EV-027, EV-028 y EV-029 aparece tal cual en el texto extraído (salvo espacios y saltos de línea).
- Con su propio `esperado` como única afirmación, cada uno de los tres cumple su dato clave. Los 27 casos con respuesta también cumplen los suyos.
- Una respuesta "no determinado" no los cumple, y una que no nombra la norma a la que remite ("El monto máximo no está establecido.") tampoco.
- Límite del corrector: una respuesta con la remisión y una cifra inventada sí los cumple (por ejemplo, "… el régimen jurisdiccional vigente, que lo fija en 1.300 módulos"; cifra inventada para la prueba). El corrector solo comprueba que algo esté, no que algo falte. Ese caso lo controla la revisión humana de la decisión 2.

### Para decidir

1. **¿Se vinculan EV-022 y EV-028 como par de REQ-020?** Tienen la misma pregunta, y desde T-064 cada una cita una norma distinta, que es lo que el plan pide para un par. Para vincularlas hay que cambiar el campo `pareja` de los dos casos, y T-064 no toca ese campo. **Resuelto:** el responsable aprobó el par el 2026-10-03; los dos casos llevan `pareja` y la etiqueta "dos fechas".

| Pregunta | Fecha | Respuesta del sistema (ejemplo) | ¿Sí o no? |
|---|---|---|---|
| ¿Cómo se integra la Comisión Evaluadora? | 2008-11-17 (297/03, EV-022) | "Como mínimo por tres miembros titulares, un presidente y dos vocales, funcionarios de planta permanente…" (Anexo I, art. 48) | ¿Se vinculan las dos respuestas como un par de la misma pregunta con distinto régimen? |
| ¿Cómo se integra la Comisión Evaluadora? | 2024-11-11 (247/2022, EV-028) | "La integración … está sujeta a la normativa vigente. Los miembros no pueden ser funcionarios que tengan competencia para autorizar la convocatoria o aprobar el procedimiento" (anexo, art. 50; respuesta de la corrida de T-045) | |

## Decisiones del responsable sobre la remisión (2026-10-03)

1. **Dos preguntas de control "fuera de tema" nuevas, una por régimen.** Son temas de compras que ninguna norma cargada trata ni remite a otra norma. Van al lote de ajuste, sin campo `lote`, con la respuesta esperada "no determinado", la etiqueta "tema cercano que la normativa no resuelve" y el visto bueno "provisorio, autorizado por el responsable el 2026-10-03 (ADR-0015)". Cada una tiene su `fecha_autorizacion`: una antes del 2023-01-02 (297/03) y otra después (247/2022). Llevan los números EV-032 y EV-033. El lote de aceptación de T-061 usa los números siguientes.
2. **Una persona controla a mano, en cada corrida, que la respuesta de remisión no dé la cifra ni la integración no cargada.** No hay control automático. Está anotado en `notas` de EV-027, EV-028 y EV-029.
3. **EV-028: alcanza con que la respuesta diga que la integración está sujeta a la normativa vigente, con la cita del art. 50.** Por ahora no se exige que diga quiénes no pueden integrarla. Está anotado en `notas` de EV-028.

### Decisiones del responsable sobre T-064 (2026-10-03)

- Aprueba las dos preguntas de control nuevas, EV-032 (capacitación del área de compras, 297/03) y EV-033 (rotación de puestos, 247/2022), que esperan "no determinado".
- Aprueba vincular EV-022 (297/03, 2008) y EV-028 (247/2022, 2024) como par de REQ-020: la misma pregunta, "¿Cómo se integra la Comisión Evaluadora?", con un régimen distinto en cada fecha. Los dos casos llevan `pareja` y la etiqueta "dos fechas".

## Lote de aceptación (ADR-0014, T-061)

**Propuesta de T-061, para el visto bueno del responsable en el pull request.** Casos EV-034 a EV-056, todos con `lote: aceptacion`. De este lote salen la respuesta correcta y la abstención que se exigen para aceptar (el 85 % y el 90 % de T-046). No se usa nunca para ajustar: sus datos clave y variantes quedan fijos antes de su primera corrida (plan, "Evals", "Lote de aceptación").

- **Redacción:** 2026-10-03, en nombre del Coordinador.
- **Escrito sin correr el sistema.** Nadie hizo estas preguntas, ni otras parecidas, en la pantalla, con `ask` ni con `correr_evals`. No se abrió `evals/corridas/` ni las secciones de resultados de `specs/001-normativa/entorno.md`. Cada pregunta y su respuesta esperada salen solo del texto de las normas en `corpus/normativa/`, y cada `origen` lo transcribe.
- **Visto bueno:** los 23 casos llevan `visto_bueno: "pendiente"`, y un caso pendiente no se corre. Al aprobar cada caso, el campo pasa a "responsable del proyecto, AAAA-MM-DD (piloto, ADR-0015)". La revisión de la Comisión queda pendiente para antes de usar el sistema fuera del piloto.

### Composición

| Grupo | Casos | Cantidad |
|---|---|---|
| Con respuesta en la 247/2022 (fecha desde 2023-01-02) | EV-034, EV-036, EV-038, EV-040 a EV-045 | 9 |
| Con respuesta en la 297/03 (fecha hasta 2023-01-01) | EV-035, EV-037, EV-039, EV-046, EV-047 | 5 |
| Remisión a una norma no cargada, con respuesta (ADR-0015) | EV-048 y EV-049 (247/2022); EV-050 (297/03) | 3 |
| Sin respuesta, ajena a la normativa | EV-051 y EV-053 (247/2022); EV-052 (297/03) | 3 |
| Sin respuesta, tema cercano que la normativa no resuelve | EV-054 (247/2022); EV-055 y EV-056 (297/03) | 3 |
| **Total** | | **23** |

- Pares de REQ-020: EV-034 y EV-035; EV-036 y EV-037; EV-038 y EV-039; EV-049 y EV-050 (un par de remisión). En los dos primeros y en el tercero la respuesta cambia con el régimen; en el de remisión las dos normas remiten al régimen jurisdiccional, cada una con su cita.
- `aviso_modificatorias` verdadero: los 6 casos con respuesta en la 297/03 (EV-035, EV-037, EV-039, EV-046, EV-047, EV-050). Falso: todos los demás, también los sin respuesta con fecha bajo la 297/03.
- Medida: 17 preguntas con respuesta (14 sin remisión y 3 de remisión) y 6 sin respuesta. Con ese tamaño, 17 de 17 da un intervalo de Wilson al 95 % de 81,6 % a 100 %, y 6 de 6, de 61,0 % a 100 % (plan, "Margen de error").

### Casos

| Id | Pregunta (resumida) | Régimen | Fecha | Esperado (resumido) | Cita | Pareja | Tipo sin respuesta |
|---|---|---|---|---|---|---|---|
| EV-034 | Plazo mínimo para observar el proyecto de pliego | 247/2022 | 2023-01-03 | 10 días corridos desde la última publicación en el Boletín Oficial | Anexo, art. 30 | EV-035 | |
| EV-035 | Plazo mínimo para observar el proyecto de pliego | 297/03 | 2023-01-01 | No inferior a 5 días | Anexo I, art. 27 | EV-034 | |
| EV-036 | Qué se hace si dos ofertas empatan | 247/2022 | 2025-04-14 | Preferencias de la normativa vigente; mejora de precios; sorteo público | Anexo, art. 56 | EV-037 | |
| EV-037 | Qué se hace si dos ofertas empatan | 297/03 | 2013-10-21 | Mejora de precios; sorteo público | Anexo I, art. 51 | EV-036 | |
| EV-038 | Cuánto se puede cobrar por el pliego | 247/2022 | 2024-05-20 | Costo de reproducción; no se devuelve | Anexo, art. 27 b) 2 | EV-039 | |
| EV-039 | Cuánto se puede cobrar por el pliego | 297/03 | 2020-02-17 | Hasta el uno por mil (1 ‰) del monto presunto | Anexo I, art. 28 inc. 1) | EV-038 | |
| EV-040 | Cuándo ya no se puede penalizar a un proveedor | 247/2022 | 2024-08-05 | 5 años desde la causal (prescripción) | Anexo, art. 91 | | |
| EV-041 | Cuándo se presume que se partió una compra | 247/2022 | 2023-06-20 | Desdoblamiento: otra convocatoria por lo mismo dentro de 3 meses | Anexo, art. 29 | | |
| EV-042 | Plazo de responsabilidad por vicios ocultos | 247/2022 | 2026-01-19 | 1 año desde la conformidad definitiva (inmuebles, 3 años) | Anexo, art. 78 | | |
| EV-043 | ¿Se puede rechazar la orden de compra? | 247/2022 | 2025-10-06 | Sí, dentro de 3 días, con pérdida de la garantía de oferta | Anexo, art. 60 | | |
| EV-044 | Muestras que el oferente no retira | 247/2022 | 2024-02-26 | 60 días corridos; renuncia tácita a favor de la AFIP | Anexo, art. 28 | | |
| EV-045 | ¿Garantía con pagaré? | 247/2022 | 2023-11-13 | Sí, pagaré a la vista si la garantía no supera M 260 | Anexo, art. 65 g) | | |
| EV-046 | Duración de la suspensión como sanción | 297/03 | 2017-06-05 | Hasta 6 meses | Anexo I, art. 56 b) 2 | | |
| EV-047 | ¿Se puede adjudicar al actual locador si no es el más barato? | 297/03 | 2006-09-11 | Sí, si no supera en más de 10 % a la menor y hay razones de funcionamiento | Anexo I, art. 61 inc. 2) | | |
| EV-048 | Integración de la comisión de recepción | 247/2022 | 2024-07-01 | Remisión: sujeta a la reglamentación que se dicte (no cargada); sin integración | Anexo, art. 73 | | |
| EV-049 | Monto máximo del trámite simplificado | 247/2022 | 2025-12-01 | Remisión: el del régimen jurisdiccional vigente (no cargado); sin cifra | Anexo, art. 22 | EV-050 | |
| EV-050 | Monto máximo del trámite simplificado | 297/03 | 2011-03-14 | Remisión: el del Régimen Jurisdiccional vigente (no cargado); sin cifra | Anexo I, art. 22 | EV-049 | |
| EV-051 | Monto del salario mínimo, vital y móvil | 247/2022 | 2024-10-15 | No determinado | — | | Ajena a la normativa |
| EV-052 | Documentación para tramitar el pasaporte | 297/03 | 2009-07-06 | No determinado | — | | Ajena a la normativa |
| EV-053 | Velocidad máxima en autopista | 247/2022 | 2026-03-09 | No determinado | — | | Ajena a la normativa |
| EV-054 | Viáticos diarios de un agente de compras que viaja | 247/2022 | 2023-09-25 | No determinado | — | | Tema cercano que la normativa no resuelve |
| EV-055 | Frecuencia de encuestas de satisfacción a las áreas requirentes | 297/03 | 2016-11-28 | No determinado | — | | Tema cercano que la normativa no resuelve |
| EV-056 | Días de teletrabajo del personal de compras | 297/03 | 2020-08-10 | No determinado | — | | Tema cercano que la normativa no resuelve |

### Artículos del lote de ajuste que se evitaron

Se tomaron de `unidades`, `cita`, `origen` y `notas` de EV-001 a EV-033 y de este índice:

- Anexo de la 247/2022: arts. 5, 7, 21, 24, 33, 38, 41, 43, 50, 55, 57, 59, 61, 64, 66, 77, 79, 88, 92 y 99. Cuerpo: arts. 2 a 4 (los cita REQ-020).
- Disposición 297/03: art. 3 de la disposición; Anexo I, arts. 8, 21, 25, 39, 43, 48, 50, 53, 55, 58 y 64.

Los casos nuevos usan otros: anexo de la 247/2022, arts. 22, 27, 28, 29, 30, 56, 60, 65, 73, 78 y 91; Anexo I de la 297/03, arts. 22, 27, 28, 51, 56 y 61. Por eso no se armaron pares con temas que en la 297/03 están en el art. 58 (comisión de recepción, vicios ocultos, plazo de entrega).

### Remisiones

Además de las del lote de ajuste (arts. 21 y 50 del anexo de la 247/2022 y art. 21 del Anexo I de la 297/03), el corpus tiene estas, y el lote usa tres:

- **Anexo de la 247/2022, art. 73 (EV-048):** la integración de la comisión de recepción queda "sujeta a la reglamentación que se dicte". Es la remisión que señalaba el aviso de T-064.
- **Art. 22 de las dos normas (EV-049 y EV-050):** el monto del trámite simplificado es el del régimen jurisdiccional vigente.
- **No usadas:** art. 62 del anexo de la 247/2022 (autoridades competentes según el régimen jurisdiccional vigente; el art. 58 dice lo mismo para la adjudicación y un caso con una sola unidad sería ambiguo); art. 52, inciso 1) b) del Anexo I de la 297/03 (licitación privada con menos de 3 ofertas y monto del Régimen Jurisdiccional vigente); otras menciones de "la reglamentación" o "la normativa vigente" (preferencias, garantías, registro de sancionados) que acompañan una regla que sí está en el texto.

En EV-036 (desempate bajo la 247/2022), las preferencias remiten a la normativa vigente, que no está cargada; el resto de la respuesta sí está en el artículo. Una respuesta que diga en qué consisten las preferencias es incorrecta y lo controla la revisión humana, como en los casos de remisión.

### Preguntas sin respuesta: búsquedas

Búsqueda por palabras, sin tildes ni mayúsculas, sobre el texto canónico de la lectura (2026-10-03) del anexo y el cuerpo de la 247/2022 y de la 297/03 con su Anexo I, considerandos incluidos. El detalle de cada búsqueda está en el `origen` del caso.

| Caso | No aparecen | Aparecen con otro sentido |
|---|---|---|
| EV-051 | "salario", "minimo vital", "sueldo", "remuneraci", "ingreso minimo", "smvm", "consejo del salario" | — |
| EV-052 | "pasaporte", "migraci", "documento nacional" | "identidad" (del personal del contratista y de los usuarios), "cedula" (medio de notificación) |
| EV-053 | "velocidad", "autopista", "kilometr", "km/h", "ruta", "conducir" | "transito" (dentro de "transitorio"), "vehicul" (reparación de vehículos) |
| EV-054 | "viatic", "pasaje", "alojamiento", "gastos de viaje", "movilidad" | "traslado" (de maquinarias o bienes rechazados), "gastos" (del contratista, caja chica, iniciativa privada), "inspecci" (facultad de inspeccionar al contratista) |
| EV-055 | "encuesta", "sondeo", "areas requirentes", "evaluacion de desempe", "calidad de la gestion" | "satisfacci" ("a satisfacción de la AFIP"), "area requirente" (acuerdos marco), "opinion" (opinión técnica sobre ofertas y opiniones sobre el proyecto de pliego) |
| EV-056 | "teletrabajo", "trabajo a distancia", "a distancia", "remoto", "home office", "presencial", "jornada" | "licencia" (contratos de licencias), "horario" (consulta del pliego), "oficina" (del contratista o de pagos) |

Se descartaron por zona gris (la norma menciona el tema sin resolverlo): caja chica (excluida del régimen), preferencias a pymes (remite a la normativa vigente), conservación de expedientes (remite a la normativa vigente), sustentabilidad y género (art. 98 del anexo), anticipos financieros (solo la contragarantía), designación del titular de la unidad de compras, plantel mínimo de la unidad con capacidad de contratación.

### Comprobado

En un contenedor aparte (proyecto `evaluon-t061`), sin consultar al sistema, solo con la lectura de casos, el corrector y la lectura y partición de las normas:

- `load_cases` sobre `evals/casos/`: los 33 casos del lote de ajuste corren; los 23 nuevos quedan sin correr por visto bueno pendiente; ninguno mal formado.
- Con visto bueno provisorio en una copia temporal: `load_cases` lee los 56 casos sin ninguno mal formado; los 23 nuevos salen con `lot == "aceptacion"` y los 33 anteriores con `lot == "ajuste"`. El régimen de cada caso es el de su fecha, `aviso_modificatorias` es verdadero solo en los casos con respuesta de la 297/03, y cada par tiene la misma pregunta, `pareja` recíproca y normas distintas.
- Cada clave de `unidades` de los casos nuevos existe en la partición de su norma, y ninguna figura en los casos del lote de ajuste (intersección vacía).
- Con su propio `esperado` como única afirmación, los 17 casos con respuesta cumplen sus datos clave. Una respuesta contraria plausible (otro plazo, otro porcentaje, otra polaridad; en los de remisión, "El monto máximo no está establecido." o una integración inventada) no los cumple, y "no determinado" tampoco.
- El `origen` de los 17 casos con respuesta aparece tal cual en el texto extraído de su norma (salvo espacios y saltos de línea).

### Para el visto bueno del responsable

Una fila por caso. Al aprobar, el caso pasa de `visto_bueno: "pendiente"` a "responsable del proyecto, AAAA-MM-DD (piloto, ADR-0015)".

| Caso | Pregunta | Respuesta esperada (resumida) | Cita | ¿La aprobás? sí/no |
|---|---|---|---|---|
| EV-034 | ¿Cuál es el plazo mínimo para que los interesados formulen observaciones al proyecto de pliego de bases y condiciones particulares? (2023-01-03) | 10 días corridos como mínimo, desde la última publicación en el Boletín Oficial | 247/2022, anexo, art. 30 | |
| EV-035 | La misma (2023-01-01) | No inferior a 5 días | 297/03, Anexo I, art. 27 | |
| EV-036 | ¿Qué se hace cuando dos ofertas quedan empatadas? (2025) | Preferencias de la normativa vigente; si sigue, mejora de precios; si sigue, sorteo público | 247/2022, anexo, art. 56 | |
| EV-037 | La misma (2013) | Mejora de precios; si sigue, sorteo público | 297/03, Anexo I, art. 51 | |
| EV-038 | ¿Cuánto puede cobrar la AFIP por el pliego de una licitación? (2024) | Una suma equivalente al costo de reproducción, que no se devuelve | 247/2022, anexo, art. 27 b) 2 | |
| EV-039 | La misma (2020) | Hasta el uno por mil (1 ‰) del monto presunto del contrato | 297/03, Anexo I, art. 28 inc. 1) | |
| EV-040 | ¿Pasado cuánto tiempo la AFIP ya no puede aplicarle una penalidad a un proveedor? | 5 años desde la causal | 247/2022, anexo, art. 91 | |
| EV-041 | ¿Cuándo se presume que una unidad partió la compra de manera indebida? | Si en 3 meses desde la autorización hace otra convocatoria por los mismos bienes sin justificación (desdoblamiento) | 247/2022, anexo, art. 29 | |
| EV-042 | ¿Durante cuánto tiempo responde el contratista por los vicios ocultos? | 1 año desde la conformidad definitiva (el pliego puede fijar otro, no menor a 6 meses; inmuebles, 3 años) | 247/2022, anexo, art. 78 | |
| EV-043 | ¿El adjudicatario puede rechazar la orden de compra después de que se la notifican? | Sí, dentro de 3 días, con pérdida de la garantía de mantenimiento de oferta | 247/2022, anexo, art. 60 | |
| EV-044 | ¿Qué pasa con las muestras que un oferente nunca pasa a buscar? | A los 60 días corridos de notificado, renuncia tácita a favor de la AFIP | 247/2022, anexo, art. 28 | |
| EV-045 | ¿Un oferente puede constituir la garantía con un pagaré? | Sí, pagaré a la vista, si la garantía no supera M 260; no combinable | 247/2022, anexo, art. 65 g) | |
| EV-046 | ¿Por cuánto tiempo puede la AFIP suspender a un proveedor como sanción? | Hasta 6 meses | 297/03, Anexo I, art. 56 b) 2 | |
| EV-047 | ¿Se puede adjudicar al actual locador aunque su oferta no sea la más baja? | Sí, si no supera en más de 10 % a la menor admisible y hay razones de funcionamiento fundadas | 297/03, Anexo I, art. 61 inc. 2) | |
| EV-048 | ¿Cómo se integra la comisión de recepción? | Remisión: queda sujeta a la reglamentación que se dicte; no pueden integrarla quienes intervinieron en el procedimiento | 247/2022, anexo, art. 73 | |
| EV-049 | ¿Hasta qué monto se puede usar el trámite simplificado? (2025) | Remisión: el que fije el régimen jurisdiccional vigente, sin cifra | 247/2022, anexo, art. 22 | |
| EV-050 | La misma (2011) | Remisión: el que fije el Régimen Jurisdiccional vigente, sin cifra | 297/03, Anexo I, art. 22 | |
| EV-051 | ¿Cuál es el monto del salario mínimo, vital y móvil? | No determinado (ajena) | — | |
| EV-052 | ¿Qué documentación hay que presentar para tramitar el pasaporte? | No determinado (ajena) | — | |
| EV-053 | ¿Cuál es la velocidad máxima permitida en una autopista? | No determinado (ajena) | — | |
| EV-054 | ¿Qué monto diario de viáticos le corresponde a un agente de compras que viaja por una contratación? | No determinado (tema cercano) | — | |
| EV-055 | ¿Cada cuánto tiene que hacer la unidad de compras una encuesta de satisfacción a las áreas requirentes? | No determinado (tema cercano) | — | |
| EV-056 | ¿Cuántos días por semana pueden teletrabajar los agentes del área de compras? | No determinado (tema cercano) | — | |

### Visto bueno del responsable sobre el lote de aceptación (2026-10-03)

- El responsable aprobó los 23 casos (EV-034 a EV-056), en tres grupos: 14 con respuesta, 3 de remisión y 6 sin respuesta. Se le mostraron con la tabla pregunta / respuesta esperada / cita.
- Todas las preguntas del conjunto (lote de ajuste y lote de aceptación) quedan acumuladas para que la Comisión Evaluadora las confirme en la feature 009 (ADR-0015, ADR-0016). Hasta entonces, el visto bueno es el del responsable para el piloto.
