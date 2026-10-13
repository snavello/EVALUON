# T-256 · Verificación: medición honesta (recálculo sin GPU)

Nivel: plena (lógica de la medida, sin GPU) · Fecha: 2026-10-12 · Verificó: testeador evaluador · Requisitos: REQ-101 a REQ-105 y REQ-107
Rama: `015-T-256` en `3a3b0ad` (tres commits sobre `main` fd72210). Entradas leídas: la constitución 1.4, la fila T-256 de `tasks.md`, el informe del comité `4-medicion.md` (§1, §2, §5 y §7, fuera de git), el ADR-0059 y `verificacion/T-256.md`.
Solo cifras, filas y nombres de pruebas (P4): ningún texto de las ofertas ni del pliego. Las pruebas corrieron en un Postgres propio (`evaluon-ver256`), con el código de la rama montado de solo lectura y el corpus montado. La base de 8000 se usó una sola vez, para leer (`default_transaction_read_only=on`). No se usó la GPU ni se corrió la suite completa (el encargo la reserva al Coordinador). Los guiones propios y las alteraciones se hicieron en la carpeta temporal de la sesión; se commitea solo este registro.

## Veredicto

**Pasa.** Los siete defectos (D1, D2, D3, D5, D7, D8 y D9) y «la fila de una circular no es sobrante» están corregidos. Cada uno tiene un test que falla cuando se revierte el cambio, y las pruebas de las tres áreas pasan. La exactitud por celda, recalculada con un guion propio, da lo esperado: V1 27/21/3 y el 12B 24/24/3. El recálculo de la rama reproduce la tabla de `T-256.md` en V1 y en el 12B, en evaluación y en matriz. Quedan **4 hallazgos menores** (H-256-1 a H-256-4) y **8 observaciones** (O-256-1 a O-256-8; siete son sobre el ADR-0059). Ninguno impide integrar, pero H-256-4 conviene resolverlo antes de T-260. Con R39 excluida, las cifras de la tabla de `T-256.md` cambian: ver «Cifras con R39 excluida».

## Criterios de verificación

| # | Criterio | Resultado | Evidencia |
|---|---|---|---|
| 1.1 | D1: el par del Portal coincide solo si el resultado es el esperado | **Cumple** | `_match` y su copia en el recálculo (`_figures`). Al revertir cualquiera de las dos, falla un test (alteraciones D1 y R-D1). V1: coincidencia de 47/49 a 40/44 (con R123 y R124 fuera), igual que la cuenta del comité (44/49 menos los 5 pares excluidos, de los que 4 coincidían) |
| 1.2 | D2: «no se encontró el documento» contra «cumple» es conclusión errada | **Cumple** | `_contradiction` y `_figures` (alteraciones D2 y R-D2). V1: de 0 a 1 en el dictamen (M-008 de la oferta 3), como dice el comité. El lado «no aplica» se cuenta en la exactitud por celda (O1 R80 y O2 R80 son erradas). La lista del dictamen no tiene pares «no aplica», así que en la coincidencia no hace falta |
| 1.3 | D3: el «externo» del modelo no se descuenta; se informa sobre todas las celdas y sobre las decidibles | **Cumple** | `waits_for_document`, `cell_counts` y `_figures` (alteraciones D3 y R-D3). Cuenta propia desde `celdas-todas.txt`: V1 21 de 75 y 21 de 45 decidibles; 12B 24 de 74 y 24 de 44. Son las mismas que da la rama. «Externo» del modelo que ahora cuenta: V1 4, 12B 3 |
| 1.4 | D5: la lista presente principal va sin lo que está a revisión, y la otra cifra al lado | **Cumple** | `"recall": found_without_review` (alteración D5). V1 caso-00: 39/42, con la revisión 40/42 |
| 1.5 | D7: la suprimida por una circular que está en otra fila cuenta como encontrada | **Cumple** | `suppressed_elsewhere` en la medida y en el recálculo (alteraciones D7 y R-D7). Caso-01 V1: 2 en otra fila, 76/80 (77/80 con la revisión). El test que pedía lo contrario se reescribió según la decisión de la mesa, no para que pase |
| 1.6 | D8: el «cumple» citado al Portal no es «sin cita» | **Cumple** | `measure_pair` y `_figures` (alteraciones D8 y R-D8). V1: de 3 a 0 «sin cita». Los 3 de antes son pares del Portal con 1 a 4 citas del Portal: M-020 de la oferta 3 es de la regla del Portal, y M-039 de las ofertas 1 y 2 es un «cumple» del modelo (regla vacía) con 3 citas del Portal (O-256-8). Los 5 del 12B (M-012 ×3 y M-020 ×2) son «cumple» de la regla del Portal, que nunca sale sin la cita del Portal (`portal_facts.py`) |
| 1.7 | D9: las cifras sin las filas técnicas se informan aparte | **Cumple** | `found_without_technical` y `kept_without_technical` (alteraciones D9 y D9b). V1 caso-00: 33/36 y 24/27 |
| 1.8 | La fila que agrega una circular no es sobrante | **Cumple** (solo en la medición nueva) | `ORIGIN_CIRCULAR` → `agregada_por_circular` (alteración CIRC). El recálculo no la ve porque `resultados.jsonl` no guarda el origen; `T-256.md` lo dice |
| 1.9 | Ninguna corrección rompe otra medida | **Cumple** | Las «antes» del recálculo reproducen los `resumen.md` de V1 y del 12B: coincidencia 47/49 y 46/49; 0 contradicciones; «sin cita» 3 y 5; Portal 16/21 y 12/20; «no determinado» 18/81 y 24/80. En la matriz: conservadas 30/33 y 31/48. Las tres áreas pasan (criterio 6) |
| 2 | Exactitud por celda, con un guion propio | **Cumple** | Guion propio (`exact_ver.py`, expresiones regulares, sin el analizador de la rama) sobre `celdas-comision-2026-10-10.yaml` y `celdas-todas.txt`. **V1 (160553): 27 / 21 / 3.** Erradas: O1 R80 y O2 R80 «no se encontró» (Comisión: «no aplica»), O3 R22 «no se encontró» (Comisión: «cumple»). **12B (011105): 24 / 24 / 3.** Erradas: O3 R16, O3 R22 y O3 R80. Las discordantes son 4 a favor de V1 (O1 R22, O1 R32, O2 R32, O3 R24) y 1 a favor del 12B (O2 R41). Las 8 corridas dan lo mismo que la tabla §5.2 del comité. Además: la huella declarada es la de las 51 celdas, y las 51 son iguales, una por una, a las decisiones de la base de 8000 (consulta de §5.1, solo lectura): 39 «cumple», 11 «no aplica», 1 «no se encontró» |
| 3 | Exclusiones de celdas (R123, R124 y R39): salen de la evaluación y se informan aparte | **Cumple** (con H-256-3 y H-256-4) | El archivo trae las tres filas, con su motivo y el visto bueno del Coordinador que suma R39. Recálculo de V1: «Filas excluidas: 9 celdas y 7 pares» (M-020 ×2, M-039 ×3, M-021 ×2); exactitud «excluidas 3» (las tres celdas de R39 de la Comisión). Salen de las celdas, del «no determinado», del Portal, de las preguntas, de los pares y de la exactitud. En el recálculo y en `cell_counts` lo cuida un test (alteraciones EXCL y X-CELDAS). En la medición en vivo, la exclusión de pares y de preguntas no tiene test (X-PARES y X-PREG: H-256-4). En la medición nueva, `parametros.json` guarda las filas con su motivo |
| 4 | `--recalcular` coincide con la tabla de `T-256.md` | **Cumple** (con H-256-1 y H-256-2) | Con el archivo de dos filas, el método `_recompute` de la rama da, en V1 y en el 12B, las nueve columnas de la tabla. En la matriz: V1 y 12B del caso-00 y V1 del caso-01, las ocho columnas. Con el archivo actual de tres filas, ver «Cifras con R39 excluida». La regla de las 3 citas del Portal no esconde un «cumple» sin cita (H-256-1) |
| 5 | ADR-0059: criterios claros, medibles y escritos antes de medir | **Cumple en lo principal, con faltas** | Está escrito antes de T-260 y en estado «propuesto». Las medidas, los tamaños mínimos, los conjuntos y la corrida alterada son medibles. Faltas en O-256-1 a O-256-7: lo más importante es que V1 hoy no pasa su propio P3 bloqueante (3 «no se encontró» contra «cumple» o «no aplica») y que no dice qué pasa con los umbrales del plan 015 |
| 6 | Tests de `tests/assessment`, `tests/tenders` y `tests/journey` con `-n 2` y el corpus montado | **Cumple** | `tests/assessment tests/tenders tests/journey` con `-n 2`, sobre la rama combinada con `main` e6432b6: **3046 pasaron, 0 fallaron, 0 se saltearon** (708,6 s). El corpus estaba montado, así que corrieron también las pruebas que lo necesitan (`test_ronda_t254.py`) |

## Cifras con R39 excluida

Las da el recálculo de la rama con `exclusiones-celdas-2026-10-12.yaml` tal como está (R123, R124 y R39), comparado con la tabla de `T-256.md` (solo R123 y R124). Las cifras de exactitud y de «no determinado» las rehice con guiones propios y dan lo mismo.

| Medida | V1, `T-256.md` | **V1 con R39 fuera** | 12B, `T-256.md` | 12B con R39 fuera |
|---|---|---|---|---|
| Exactitud: exactas / abstenciones / erradas | 27 / 21 / 3 de 51 | **24 / 21 / 3 de 48** (50,0 % / 43,8 % / 6,2 %) | 24 / 24 / 3 de 51 | 21 / 24 / 3 de 48 |
| Exactas con cita / sin cita | 26 / 1 | **23 / 1** | 23 / 1 | 20 / 1 |
| «No determinado», todas | 21/75 | **21/73 (28,8 %)** | 24/74 | 24/72 (33,3 %) |
| «No determinado», decidibles | 21/45 | **21/43 (48,8 %)** | 24/44 | 24/42 (57,1 %) |
| Portal «cumple» con su cita | 12/16 | **11/15 (73,3 %)** | 10/15 | 9/14 (64,3 %) |
| Coincidencia con el dictamen | 40/44 | **38/42 (90,5 %)** | 37/44 | 35/42 (83,3 %) |
| Erradas en el dictamen | 1 | **1** | 1 | 1 |
| «Cumple» sin cita | 0 | **0** | 0 | 0 |
| Excluidas | 6 celdas y 5 pares | **9 celdas y 7 pares; 3 celdas de la Comisión** | 6 y 5 | 9 y 7; 3 |

- Los dos modelos aciertan R39 en las tres ofertas, así que la diferencia entre V1 y el 12B no cambia: +3 exactas, con las mismas 4 a 1 discordantes.
- En las 8 corridas, sobre 48 celdas, las exactas son 21, 25, 24, 22, 24 (V1), 22, 22 y 26. El rango pasa de 24–28 a 21–26. La V4 (180648) tiene O2 R39 como abstención: le quita 2 exactas y 1 abstención.
- La matriz no cambia: R39 es una exclusión de celdas de la evaluación, y `exclusiones-2026-10-10.yaml` ya excluía M-021 de la lista de la matriz.

## Suite

Corrida **de las áreas**, no la completa (por encargo), sobre la rama combinada con `main` **e6432b6** en una copia aparte (fusión sin conflictos, sin publicar). Resultado: **3046 pasaron, 0 fallaron, 0 se saltearon** (`-n 2`, 708,6 s, de 20:20 a 20:32). La suite completa la corre el Coordinador una vez por tanda.

## Alteraciones del código

Cada una cambia una sola cadena en una copia del código. Después corre solo los tests de la parte alterada, con `-x`, y se restaura.

| # | Alteración | Tests | Lo detecta |
|---|---|---|---|
| D1 | `_match`: el par del Portal vuelve a coincidir solo con la cita | `tests/assessment/test_medicion_t256.py` | `test_a_portal_pair_matches_only_when_the_result_is_the_expected_one` |
| D2 | `_contradiction`: sin «no se encontró» contra «cumple» | ídem | `test_missing_document_against_a_cumple_of_the_dictamen_is_a_wrong_conclusion` |
| D3 | `waits_for_document`: todo «externo» espera, como antes | ídem | `test_the_external_that_the_model_marks_is_not_discounted_and_both_figures_are_reported` |
| D8 | `measure_pair`: «sin cita» sin mirar las citas del Portal | ídem | `test_a_cumple_cited_to_the_portal_is_not_without_citation` |
| EXCL | `cell_accuracy`: no saca las filas excluidas | ídem | `test_cell_accuracy_counts_exact_abstained_and_wrong_and_lists_the_exact_to_read` |
| X-CELDAS | `cell_counts`: vuelve a contar las celdas de filas excluidas | ídem | `test_an_excluded_row_leaves_the_cells_counts` |
| X-PARES | `measure_offer`: vuelve a medir los pares de filas excluidas | `tests/assessment/test_medicion_t256.py` | **Ninguno** (pasan los 10). La corrida con `tests/assessment/test_evaluation.py` se cortó por tiempo, y ningún test de `tests/` pasa filas excluidas a `measure_offer` (`grep`): H-256-4 |
| X-PREG | `question_records`: vuelve a contar las preguntas de filas excluidas | ídem | **Ninguno** (pasan los 10). Ningún test pasa filas excluidas a `question_records`: H-256-4 |
| R-D1 | recálculo (`_figures`): sin D1 | `tests/assessment/test_medicion_t256.py` | `test_a_saved_run_is_recomputed_without_the_model_before_and_after` |
| R-D2 | recálculo: sin D2 | ídem | ídem |
| R-D3 | recálculo: sin D3 | ídem | `test_the_command_recomputes_a_saved_run_without_the_model` |
| R-D8 | recálculo: sin D8 | ídem | `test_a_saved_run_is_recomputed_without_the_model_before_and_after` |
| R-3CITAS | recálculo (`_offline_portal_record`): sin la regla de las 3 citas del Portal | ídem | **Ninguno** (pasan los 10): H-256-1 |
| D5 | `measure_version`: `recall` vuelve a sumar lo que está a revisión | `tests/tenders/test_medicion_t256.py` y `tests/tenders/test_evaluation.py` | `test_what_is_in_mandatory_review_is_not_found_and_is_reported_apart` |
| D7 | `measure_version`: sin «suprimido por circular, en otra fila» | ídem | `test_two_expected_over_one_suppressed_row_are_both_found_one_in_another_row` (101 corrieron) |
| D9 | `found_without_technical` vuelve a contar las técnicas | `tests/tenders/test_medicion_t256.py` | `test_technical_rows_built_by_a_rule_are_reported_apart` |
| D9b | `kept_without_technical` igual a las conservadas con las técnicas | ídem | ídem. El primer intento usaba una variable que todavía no existía y daba error de ejecución: no cuenta |
| CIRC | la fila agregada por una circular vuelve a ser sobrante | `tests/tenders/test_medicion_t256.py` y `tests/tenders/test_evaluation.py` | `test_a_row_added_by_a_circular_is_not_a_leftover` |
| R-D7 | recálculo de la matriz (`_matrix_figures`): sin D7 | `tests/tenders/test_medicion_t256.py` | `test_a_saved_matrix_run_is_recomputed_without_the_model_before_and_after` |

## Hallazgos

**H-256-1 (menor): la regla de las 3 citas del Portal no tiene test, y depende de un archivo que no escribe el repositorio.**
- **Qué hace.** En `_offline_portal_record`, si la celda muestra 3 citas del Portal, ninguna trae el valor y la regla es `portal_cumple`, se da por citada.
- **Qué decide.** En V1 decide 2 celdas (O1 R46 y O2 R46, el total del Portal: las 3 citas que se ven son renglones). En el 12B decide 1 (O1 R46).
- **Si se quita.** Al revertirla (alteración R-3CITAS) pasan los 10 tests. Sin la regla, el Portal de V1 bajaría de 12/16 a 10/16 y aparecerían 2 «cumple con un dato que no coincide», que bloquean. Además, las «antes» ya no reproducirían el resumen en vivo: darían 14/21 en vez de 16/21 (recalculado con la regla quitada).
- **Por qué no esconde un «cumple» sin cita.**
  - La cifra «sin cita» sale de `resultados.jsonl` (`citas_portal`), no de `celdas-todas.txt`.
  - La regla del Portal nunca da «cumple» sin la cita del Portal (`portal_facts.py`).
  - Con la regla, las «antes» reproducen el Portal de los resúmenes en vivo (16/21 y 12/20), que se midieron con todas las citas.
- **El riesgo.** Ningún código de `evaluon/` escribe `celdas-todas.txt`, así que el tope de 3 citas es un supuesto sobre un guion externo. Si cambia, el recálculo cambia sin que falle ningún test.
- **Reproducir.** En `evaluon/assessment/evaluation.py`, cambiar `with_value = True` por `with_value = False` dentro de `_offline_portal_record` y correr `pytest tests/assessment/test_medicion_t256.py`: pasan 10.

**H-256-2 (menor): `--recalcular` pide usuario y clave, y por eso usa la base.**
- En `medir_evaluacion` y en `medir_matriz`, `handle` autentica antes de mirar `--recalcular` (`permissions.authenticate_command`). El docstring de `medir_matriz` dice «No usa el modelo, la GPU ni la base».
- **Reproducir.** `python manage.py medir_evaluacion --recalcular CARPETA --celdas-comision …` da «the following arguments are required: --usuario». Con `--usuario x`, pide «Clave de EVALUON:» y sin terminal termina con `EOFError`. Lo mismo con `medir_matriz`.
- **Cómo se verificó.** Llamando al mismo `Command()._recompute(options)` de la rama.
- **Arreglo posible.** Recalcular antes de autenticar, o corregir el docstring.

**H-256-3 (menor, texto): el resumen dice que todas las filas excluidas son «agregadas solo para la medida».**
- La línea del resumen nuevo es «Filas excluidas de la evaluación (agregadas solo para la medida): N…».
- R39 no se agregó para la medida: está en la versión 1 y sale por ser forma de presentar por el Portal. Su motivo queda bien en `parametros.json`, pero el resumen lo dice mal.
- El encabezado de `exclusiones-celdas-2026-10-12.yaml` (fuera de git) también dice «Son las dos filas…».
- **Arreglo posible.** «Filas excluidas de la evaluación (con su motivo en `parametros.json`)».

**H-256-4 (menor, antes de T-260): la exclusión de pares y de preguntas en la medición en vivo no tiene test.**
- `measure_offer` saca las filas de `exclusiones-celdas` de los pares, de las celdas del Portal, de las preguntas y de las celdas observadas. Es el camino que va a usar T-260 con GPU.
- Al revertir la exclusión de pares (X-PARES) o la de preguntas (X-PREG), pasan los 10 tests de `test_medicion_t256.py`. Ningún test de `tests/` llama a `measure_offer`, `question_records` u `observed_cells` con filas excluidas. Solo están cubiertos `cell_counts` (X-CELDAS) y el recálculo (EXCL y R-D1 a R-D8).
- **Reproducir.** En `evaluon/assessment/evaluation.py`, `measure_offer`, cambiar `if requirement is not None and requirement.number in excluded_rows:` por `if False:` y correr `pytest tests/assessment/test_medicion_t256.py`: pasan 10.
- **Diferencia entre los dos caminos.** El recálculo excluye los pares por el `requisito` (M-NNN) del archivo; la medición en vivo, por el número de fila. Una exclusión sin `requisito` sacaría las celdas pero no los pares del recálculo. Hoy las tres filas lo traen.

**O-256-8 (observación, hoy sin efecto en las cifras): D8 acepta cualquier cita del Portal, también en un «cumple» que concluyó el modelo.**
- En V1, R124 de las ofertas 1 y 2 es un «cumple» con regla vacía, sin citas de la oferta y con 3 del Portal (renglones), y deja de contar como «sin cita».
- Es fundamento válido según P3 1.3 si la cita es el dato de esa fila: el texto lo escribe el sistema desde el Portal, nunca el modelo. Pero la medida 004 no comprueba que la cita del Portal sea del dato que pide el requisito.
- Hoy no cambia nada, porque R124 está excluida. Conviene que la lectura de «cumple sin respaldo» del ADR-0059 (O-256-3) incluya estos casos.

## Observaciones al ADR-0059

- **O-256-1.** V1 no pasa hoy el P3 bloqueante del propio ADR: tiene 3 «no se encontró el documento» donde la Comisión dijo «no aplica» (O1 R80 y O2 R80) o «cumple» (O3 R22). El ADR no da la línea de base de cada criterio, ni dice si T-260 parte bloqueada hasta que T-257 resuelva el «no aplica» de MiPyME.
- **O-256-2.** No dice qué pasa con los umbrales del plan 015 (conservadas ≥ 70 %, lista presente ≥ 95 %, Portal 100 %, «no determinado» ≤ 15 %, preguntas 100 %, 0 «sin cita»): si siguen, si se reemplazan o si quedan de referencia. Tampoco dice cuál de las dos cifras de «no determinado» se compara con el 15 %.
- **O-256-3.** «Exactas con fundamento» es la medida principal, pero no dice quién lee `muestra-exactas.md` ni cuándo. Tampoco dice si el «+6 celdas netas» se cuenta sobre las exactas o sobre las exactas con fundamento. La falla «cumple sin respaldo» se lee celda por celda, pero la muestra lista solo las exactas: un «cumple» errado o fuera de las 48 celdas no se lee. Conviene decir qué celdas se leen (por ejemplo, todos los «cumple»).
- **O-256-4.** Sigue escrito «con 51 celdas». Con R39 fuera son 48, y las 8 corridas dan de 21 a 26 exactas, no de 24 a 28. «+6 netas» equivale a p < 0,05 solo si las 6 discordancias van en un solo sentido: con 7 a 1, McNemar exacto da p ≈ 0,07.
- **O-256-5.** La corrida alterada dice «por ejemplo» (orden invertido, semilla 43, `group_tokens` +5 %). Como el tamaño mínimo es el doble de lo que cambie con ella, la alteración debería quedar fija antes de medir, no elegida después.
- **O-256-6.** La constitución 1.4 (ADR-0058) acepta como fundamento la ausencia verificada en la lectura completa de la oferta. El ADR nombra solo la cita del Portal (1.3). La medida 004 contaría un «cumple por ausencia» como «sin cita» (`sin_cita = concluded and not cites and not portal_cites`).
- **O-256-7.** Los casos 03, 04 y 05 quedan «congelados con huella y fecha» desde la aprobación, pero el ADR no da esas huellas. Las exclusiones del 04 y del 05 se ampliaron después de mirar sus faltantes (comité, H8), y el ADR no dice si se congela esa versión o se revisa antes en forma simétrica.

## Avisos para tareas siguientes

- **Para el Coordinador.**
  - La tabla y la nota «Exactitud: no cambia entre antes y después» de `T-256.md` son con dos filas excluidas. Con el archivo actual, de tres, rigen las cifras de «Cifras con R39 excluida».
  - El ADR-0059 sigue «propuesto»: T-260 lo necesita aprobado, con O-256-1 a O-256-7 resueltas o descartadas.
- **T-257.**
  - Las 3 erradas de V1 (R80 ×2 y O3 R22) son las que bloquean el P3 del ADR.
  - El «cumple por ausencia» necesita que la medida 004 lo reconozca como fundamento (O-256-6).
- **T-260.**
  - Medir con `exclusiones-celdas-2026-10-12.yaml` (48 celdas de la Comisión).
  - `--recalcular` pide usuario y clave (H-256-2).
  - Antes de medir, un test de la exclusión en vivo de pares y preguntas (H-256-4).
  - Las exactas con fundamento siguen sin leer en `muestra-exactas.md`.
- **Medición de la matriz.** `resultados.jsonl` no guarda el origen de las filas, así que el recálculo no ve las agregadas por una circular. Solo una medición nueva las aparta.
