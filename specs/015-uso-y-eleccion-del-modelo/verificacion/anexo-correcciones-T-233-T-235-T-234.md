# Anexo de la tanda 2 · Verificación de las correcciones de la tanda 1 (T-233, T-235 y T-234)

Tanda 2 de la 015 · Nivel: liviano (diff, contraejemplos del registro, tests del área y alteraciones) · Fecha: 2026-10-11 · Verificó: testeador evaluador
Rama verificada: `origin/015-integracion-2` (12a87b8) = `main` (58f9f00) más las tandas 1 y 2. Correcciones: `015-T-233b` (c917785 y a5b854e) y `015-T-234b` (d3db860, con el ajuste de 12a87b8).
Defectos de origen: D-233-1, D-235-1 y D-234-2, del registro de la tanda 1 (rama `015-ver1`, `T-233.md`, `T-235.md`, `T-234.md`). Este anexo se suma a esos registros; no los reemplaza.

## Veredictos

| Tarea | Defecto | Corrección | Veredicto |
|---|---|---|---|
| T-233 | D-233-1 · «cumple» con un dato del Portal que no coincide con lo que el pliego fija | c917785 | **PASA**: corregido, con 0 falsos «cumple» en las sondas |
| T-235 | D-235-1 · preguntas dirigidas al oferente que llegan a la Comisión | a5b854e | **PASA** con la observación O-235-2: sigue siendo una lista de patrones; los 21 contraejemplos del registro se rechazan y la medida y el producto usan una sola definición |
| T-234 | D-234-2 · la letra de un inciso en línea se tomaba como continuación; O-234-1 y las unidades largas | d3db860 y 12a87b8 | **PASA** con las observaciones O-234-3 y O-234-4: la regla es más estricta y las unidades largas se informan aparte, pero «Deberá/Deberán» ya no se une por código aunque la spec y el ADR-0054 lo dicen |

## D-233-1 · Portal contra pliego (T-233, `portal_facts.py`)

Cambio: `compare` devuelve «no comparable» (nunca «cumple») si el requisito fija un tope o un mínimo (`_LIMIT`), un monto o un porcentaje para el total o la cotización, un CUIT distinto del del Portal, o un porcentaje de garantía sobre una base que no es el total cotizado de la oferta (`_percent_base`, `_OTHER_BASE`) o que no se puede leer.

| Contraejemplo del registro de la tanda 1 | Resultado ahora | Test |
|---|---|---|
| total 5.000.000 contra «no podrá superar $ 1.000.000» | no comparable (`falta_coincidencia`) | `test_a_total_over_the_ceiling_the_pliego_fixes_is_not_a_cumple` |
| precio del renglón 2 = 900 contra un tope de 500 | no comparable | `test_a_line_price_over_the_ceiling_the_pliego_fixes_is_not_a_cumple` |
| CUIT 30-11111111-1 contra «deberá ser 20-22222222-2» | «no cumple» con la diferencia | `test_a_cuit_that_is_not_the_one_the_pliego_fixes_is_not_a_cumple` |
| garantía 5 % del total cotizado contra «5 % del presupuesto oficial» | no comparable | `test_five_percent_of_another_base_is_not_five_percent_of_the_total` |

Sondas propias (17 requisitos y datos inventados, fuera del repositorio): ningún «cumple» con un dato que no coincide. «Cumple» queda para el 5 % del total cotizado, del monto total ofertado, del valor total o del importe total cotizado (con o sin cláusulas aparte), el CUIT o el total sin valor fijado; «no cumple» para 21.749 contra 21.750; no comparable para «presupuesto oficial», «oferta de mayor monto», «como mínimo», «al menos», «no podrá superar» y «hasta $ …».

Observación (baja): `_LIMIT` incluye «hasta», «mayor», «menor» y «no deberá», que aparecen en cláusulas que no fijan un tope («deberá mantenerse hasta la adjudicación»): esas filas quedan en «no comparable» en lugar de «cumple». Es el lado seguro; se paga en recall del REQ-103 (100 % de las celdas del Portal que coinciden), que mide T-239. Los requisitos de garantía individualizada en el Portal siguen en «cumple» (rama `_INDIVIDUALIZED`).

Alteraciones probadas:

| # | Alteración | Test que la detectó |
|---|---|---|
| 1 | Sin el filtro `_LIMIT` | `test_a_guarantee_whose_base_cannot_be_read_is_not_compared[…]` (caso «como mínimo») |
| 2 | La base del porcentaje es siempre el total cotizado | 4 tests: `test_five_percent_of_another_base_is_not_five_percent_of_the_total`, `test_a_guarantee_whose_base_cannot_be_read_is_not_compared[…]` (3) |
| 3 | El CUIT que fija el pliego no se compara | `test_a_cuit_that_is_not_the_one_the_pliego_fixes_is_not_a_cumple` |

## D-235-1 · Preguntas dirigidas al oferente (T-235, `combine.py` y `assessment/evaluation.py`)

Cambio: `combine.addresses_offeror` pasa a ser la única definición (`evaluation.question_form` ya no tiene su lista): un destinatario nombrado («a/al/para» más un rol, con más roles: cotizante, postor, adjudicatario, contratista…), un rol junto a un verbo de pedido u obligación, el pedido impersonal («se requiere», «solicitamos», «favor de», «agradeceremos»), la segunda persona y la cortesía («usted», «por favor», «sírvase», «podés») y una orden o un verbo que le habla a alguien al empezar la oración. Ante la duda rechaza y la pregunta la arma el código.

| Contraejemplo del registro de la tanda 1 | Ahora |
|---|---|
| «Se requiere al oferente que presente el certificado fiscal.»; «¿Puede aclarar si cuenta con el certificado fiscal vigente?»; «Aclare si el monto de la garantía es el 5 %.»; «Se solicita aclarar la garantía presentada.»; «¿Podría confirmar si la garantía fue constituida en pagaré?»; «¿Podría el cotizante aclarar el monto?»; «El adjudicatario deberá presentar el certificado.»; «Favor de indicar el monto de la garantía.»; «Agradeceremos nos informe el monto de la garantía.» | rechazadas las 9 (más las 5 que ya rechazaba: 14 de 14), y 21 en `TO_THE_OFFEROR` de `test_a_question_addressed_to_the_offeror_is_rejected` |
| Las dos listas podían divergir | una sola: `test_the_measure_of_the_form_uses_the_same_definition_as_the_product` |

Sondas propias (40 preguntas inventadas, fuera del repositorio):

- Dirigidas a la Comisión o de hecho (12): 10 se aceptan, entre ellas la del ejemplo de `evaluacion-v6` («…¿la Comisión da por cumplida la condición del IVA?»). Dos se rechazan de más («¿corresponde pedir la subsanación al oferente?» y «¿la Comisión solicita al oferente la subsanación?»): es el lado seguro, el código arma la pregunta.
- Dirigidas al oferente con otras formas (28): **16 pasan el control**. Ejemplos: «¿Presentará el certificado de habilitación?», «¿La empresa oferente confirma el plazo?», «¿El interesado presentará la garantía?», «¿Tu oferta incluye IVA?», «¿Nos podría indicar si incluye IVA?», «¿Me puede decir si incluye IVA?», «Informar si el precio incluye IVA.», «Adjuntar la planilla de cotización.», «Es necesario que adjunte la nota firmada.».

**O-235-2 (media-baja):** la corrección amplía la lista, que era lo que el registro pedía como mínimo, pero la defensa sigue siendo una lista: el registro de la tanda 1 sugería aceptar la pregunta libre del modelo solo si nombra a la Comisión y no tiene imperativo ni segunda persona, o no aceptarla nunca. Como la medida de T-239 usa la misma definición, lo que el producto deja pasar la medida lo da por conforme: el 100 % de REQ-105 lo sostiene en T-239 la lectura una por una, no la comprobación mecánica. Con `evaluacion-v6` el modelo tiene ejemplos de preguntas a la Comisión, de modo que la frecuencia esperada es baja; las preguntas que arma el código (`compose_question`, `missing_question`) nunca se dirigen al oferente (`test_the_questions_the_code_writes_are_never_addressed_to_the_offeror`).

Alteraciones probadas:

| # | Alteración | Test que la detectó |
|---|---|---|
| 1 | La orden o el verbo al empezar la oración dejan de rechazarse | 6 tests de `test_a_question_addressed_to_the_offeror_is_rejected` («¿Puede aclarar…», «Aclare…», «¿Podría confirmar…», «Presente…», «¿Cuenta con…»…) |
| 2 | «adjudicatario» fuera de los roles | `test_a_question_addressed_to_the_offeror_is_rejected[El adjudicatario deberá…]` y `test_the_measure_of_the_form_uses_the_same_definition_as_the_product` |
| 3 | `question_form` deja de usar la definición del producto (`directed = True`) | 4 tests de `test_evaluation.py` (`test_a_composed_question_closed_with_a_request_to_the_bidder_is_not_conforming`, `test_a_question_that_lacks_a_part_or_addresses_the_bidder_is_not_conforming[…]` ×3) |
| 4 | «cotizante» fuera de los roles | **ninguno**: los otros patrones rechazan igual «¿Podría el cotizante aclarar el monto?»; los roles agregados (cotizante, postor, concursante, vendedor, presentante) no tienen un test propio |

## D-234-2 · Unidad de sentido (T-234, `sentences.py` y `tenders/evaluation.py`)

Cambio: `is_continuation` une solo una anáfora explícita («La misma», «Los mismos», «Dicho», «Este», «Esto», «Ello») o una minúscula que no sea la letra de un inciso en línea («b)», «c.», «ii)»). «Deberá/Deberán» sin anáfora ya no se une por código (`lacks_subject` lo sigue tratando como oración sin sujeto para el encabezado y para la medida). La medida de T-238 (`pieces_of`) devuelve aparte las unidades largas que quedaron como fragmento (`cita_amplia`), que no cuentan contra el umbral de 0 pedazos, y marca «sin_sujeto» la cita que empieza con una oración sin sujeto que tiene la anterior en el tramo.

| Contraejemplo del registro de la tanda 1 | Antes | Ahora |
|---|---|---|
| CE2: «a) Constituir garantía de oferta del 5 %… b) Acompañar el certificado fiscal…» | las dos incisos en una fila | solo el inciso a) (`test_the_letter_of_an_inline_item_does_not_join_the_previous_one`, `test_which_sentences_continue_the_previous_one[b)…]`) |
| CE1: «…presentarse en pesos argentinos. Deberá acompañarse el certificado de visita…» | las dos oraciones | solo la primera |
| CE3: «La apertura de ofertas se realizará… El mismo día se labrará el acta…» | las dos | solo la primera («El mismo día» no es una de las anáforas de la lista) |
| Ejemplo del perro: «…cuatro patas, dos ojos y de color marrón. Deberá ser de raza chica.» | las dos | solo la primera; que la segunda vaya en la misma fila depende de que el modelo las cite juntas (la instrucción de extracción se lo pide) |
| Unidades largas (2,2 % en el caso-00) contadas como pedazos | 25 de 1.126 citas | informadas aparte: `test_a_complete_unit_is_not_a_piece_and_a_long_unit_is_reported_apart`, `test_a_real_piece_is_still_counted_when_the_flagged_quotes_are_set_apart` |

Sondas propias (12 textos inventados): CE1, CE2, CE3, «Deberán renovarla…» y los incisos con letras minúsculas o romanos no se unen; «La misma se renueva…» sí. Siguen uniéndose dos oraciones de asuntos distintos cuando la segunda empieza con «Este» o «Dicho» («…presentarse en pesos argentinos. Este pliego se rige por la Disposición…»; «…certificado fiscal. Dicho organismo es el encargado de emitirlo.»).

**O-234-3 (media): la corrección se aparta de la spec y del ADR-0054 sin enmendarlos.** La decisión literal de la spec (y la regla 3 del ADR-0054, «el sistema las une por código») cita como ejemplo la oración que «empieza con “Deberán…” o “La misma…” y continúa la anterior». El código une solo «La misma…» y las demás anáforas; «Deberá/Deberán» queda a cargo del modelo (la docstring dice «decisión del Coordinador, verificación de T-234»). Si el modelo no cita las dos oraciones juntas, quedan dos filas y la segunda es un pedazo sin sujeto, que ahora la medida cuenta como «sin_sujeto». Falta dejarlo por escrito en el ADR-0054 (P1: la diferencia entre código y spec se corrige de forma explícita).

**O-234-4 (baja):** «Este» y «Dicho» unen oraciones de otro asunto (ver las sondas). En las 1.126 citas reales de T-229 la regla anterior unió 12 (1,1 %) y todas las leídas seguían el mismo asunto; no se midió la nueva.

Alteraciones probadas:

| # | Alteración | Test que la detectó |
|---|---|---|
| 1 | «Deberá/Deberán» vuelve a unirse por código | 6 tests de `test_sentences.py` (`test_the_dog_is_one_row_and_a_different_matter_is_not_joined`, `test_a_sentence_without_an_explicit_anaphora_is_another_matter_and_does_not_join[…]` ×2, `test_which_sentences_continue_the_previous_one[Deberá…]` ×2…) |
| 2 | La letra de un inciso vuelve a ser continuación | 6 tests de `test_sentences.py` (`test_which_sentences_continue_the_previous_one[b)…c.…ii)…iv.]`, `test_which_sentences_lack_their_own_subject[b)…]`) |
| 3 | Las unidades largas vuelven a contar como pedazos | `test_a_complete_unit_is_not_a_piece_and_a_long_unit_is_reported_apart`, `test_a_real_piece_is_still_counted_when_the_flagged_quotes_are_set_apart` |

## Tests y regresión

Tests del área sobre `12a87b8`, en una copia aparte, con una base Postgres propia y sin GPU: `pytest tests/tenders tests/assessment tests/journey tests/test_instrucciones_revisadas.py -n 4 --dist worksteal` → **2750 pasan, 0 fallan, 0 xfail** (367 s); en la tanda 1 eran 2526 pasan y 1 xfail. Suite completa no corrida (la corre el Coordinador). `main` en 58f9f00.

## Avisos para tareas siguientes

- T-239: para REQ-103, informar cuántas de las 21 celdas del Portal del caso-00 siguen en «cumple» con la regla más estricta; para REQ-105, leer las preguntas una por una (la comprobación mecánica es la misma lista que el producto).
- Anotar en el ADR-0054 (regla 3) la decisión sobre «Deberá/Deberán» y, si se mantiene, la de «Este/Dicho».
- ADR-0053, el plan y las fichas siguen diciendo `reglas-v8`; la versión vigente es `reglas-v9` (aviso de la tanda 1, sin cambio).
