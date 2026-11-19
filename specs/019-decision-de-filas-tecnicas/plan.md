# Plan 019 · Las filas técnicas se deciden solo con el ok del informe técnico

Estado: borrador · Fecha: 2026-11-18 · Aprobó: —

Spec: `specs/019-decision-de-filas-tecnicas/spec.md` (aprobada el 2026-11-18). Carril completo (ADR-0081); verificación plena en las tareas que tocan la decisión (toca lógica y un principio, P3).

## Resumen del enfoque

El control va en **un solo lugar: el servicio `decide` de `evaluon/assessment/services/review.py`** (función `_decide`). Las dos vistas que reciben decisiones ya llaman a ese servicio y ya muestran el mensaje de cualquier `ReviewRefused`, así que no se toca ninguna vista, ni la pantalla, ni el esquema. Se suma una lectura (comando de solo lectura) para REQ-162. No hay IA, ni datos nuevos, ni migraciones.

## Relevamiento del código (verificado el 2026-11-18)

| Hecho | Dónde |
|---|---|
| `decide` comprueba el rol, abre la transacción, llama a `_decide` y, si lanza `ReviewRefused`, deja el hecho `eval_decision` en resultado `rejected` con `result`, `action`, `reason` y `message` (fuera de la transacción) | `assessment/services/review.py` l. 135-147, `_refuse_record` l. 129 |
| `_decide` valida acción, resultado, resultado reemplazado, resultado correcto y nota; no mira si el requisito es una fila técnica | `review.py` l. 150-185 |
| Vía 1: `decide` de la pantalla del recorrido (`expedientes:s4_decidir`, `evaluacion/resultado/<id>/decidir/`); atrapa `ReviewRefused` y vuelve con el mensaje | `journey/temas/s4_propuesta_acciones.py` l. 120-143 |
| Vía 2: `decide` de la revisión (`assessment:decide`, `resultado/<id>/decidir/`); atrapa `ReviewRefused` y responde 422 con el mensaje | `assessment/views/review.py` l. 23-37, `urls_review.py` l. 8 |
| No hay otra vía que cree decisiones de confirmar, corregir o rechazar: búsqueda de `review.decide/confirm/correct/reject` y de `Decision.objects.create` en todo `evaluon/`. Los formularios del cuadro (`journey/views/cuadro.py` l. 11) envían a la ruta de siempre (vía 1). Ningún comando de gestión ni API decide | búsqueda en `evaluon/` |
| Los otros dos `Decision.objects.create` son pedir y registrar la subsanación (`PEDIR_SUBSANACION`, `SUBSANAR`): no son de las tres acciones | `assessment/services/remedy.py` l. 207 y l. 313 |
| El ok del informe (`give_ok`, `withdraw_ok`) **no pasa por `review.decide`**: crea la fila `TechnicalOk`, el hecho y los `Result` por `_apply`/`_insert_result` | `assessment/services/technical.py` l. 330-459 |
| Definición de «fila técnica por renglón»: `sheets.is_item_row(requirement)` = clase técnica y con renglones. Es la misma que usa `technical.item_rows` | `offers/services/sheets.py` l. 274-276; `technical.py` l. 128-141 |
| La pantalla ya no ofrece decidir filas técnicas (`can_decide = is_evaluator and not view.technical`) | `journey/temas/s4_propuesta.py` |

Diferencias con lo que pidió el encargo: ninguna de fondo. Dos precisiones: (a) el ok no pasa por `review.decide`, así que el control no lo alcanza y REQ-161 queda cubierto por construcción (más tests que lo prueban); (b) `remedy.py` crea decisiones de otras dos acciones, fuera de REQ-159 (ver «Dudas»).

## Componentes y cambios

1. **La regla (una sola fuente).** En `_decide`, justo después de cargar el resultado (con `select_related("requirement")`, que ya está) y **antes** de la comprobación de «resultado reemplazado»: si `sheets.is_item_row(result.requirement)` y la acción es una de `STATE_ACTIONS`, lanza `ReviewRefused`. Va antes del chequeo de reemplazo para que el motivo sea siempre el mismo, aun si el pedido apunta a un resultado viejo de la fila. No agrega ninguna consulta: el requisito ya viene cargado. `unknown_action` y `result_not_found` siguen antes y no cambian. La definición de fila técnica no se copia: se reutiliza `sheets.is_item_row`.
2. **Motivo y mensaje.** `reason = "technical_row"`, `field = "result"`. Mensaje: «Esta fila es técnica y no se decide acá: la resuelve el informe técnico del área. Para cerrarla, dé el ok del informe técnico de la oferta.» Sin términos técnicos y nombra el ok del informe técnico.
3. **Qué queda en el registro (REQ-160).** `decide` ya deja el hecho `rejected` con usuario y fecha (columnas del hecho), `result`, `action`, `reason` y `message`. Para nombrar el cruce sin ambigüedad se suma a `ReviewRefused` un argumento opcional `detail=None` que `_refuse_record` mezcla en el detalle; este rechazo lo llena con `offer` y `requirement`. Cambio aditivo: los demás rechazos quedan idénticos. Como el rechazo ocurre antes de cualquier escritura, no cambia el resultado, el estado ni el historial.
4. **Las vistas no cambian.** Ambas ya traducen `ReviewRefused` en mensaje (vía 1: aviso de error en la pestaña; vía 2: 422 en la página del par).
5. **Listado (REQ-162).** Módulo nuevo `evaluon/assessment/services/technical_decisions.py` con `technical_row_decisions()`: trae con una consulta las `Decision` cuyo `result.requirement` es de clase técnica (`select_related("result__offer__procedure", "result__requirement", "user")`) y filtra en Python con `sheets.is_item_row` (misma definición que el control). Devuelve procedimiento, oferta, requisito, acción, usuario y fecha, ordenado. Todas las acciones, no solo las tres: si hubiera una anomalía, se ve. Comando nuevo `evaluon/assessment/management/commands/listar_decisiones_tecnicas.py` que lo imprime por salida estándar y cierra con «Total: N». Solo lee: no escribe en la base ni deja hecho (es una consulta, no una decisión). Su salida con datos reales no va al repositorio; al repositorio va solo la cuenta N (en el informe de verificación de la tarea del cierre).
6. **Qué no se toca.** Pantalla y plantillas, vistas, `technical.py`, `remedy.py`, modelos, migraciones, tablero, glosario, hoja de ruta, contenedores.

## Modelo de datos

Sin cambios de esquema ni migraciones: no hace falta ninguno (el rechazo usa el hecho `eval_decision` que ya existe y su campo `detail`). Un test falla si aparece una migración nueva en `evaluon/*/migrations/` con esta feature (mismo recurso que la 018).

## Flujo de IA

No usa IA. No cambia recuperación, instrucciones ni modelo (sin evals nuevas, P7).

## Registro de auditoría (P6)

Pedido rechazado: hecho `eval_decision`, resultado `rejected`, con usuario, fecha, `result`, `offer`, `requirement`, `action`, `reason = technical_row` y `message`. Listado: no registra nada porque no decide ni modifica.

## Cobertura de requisitos

Archivo de pruebas nuevo: `tests/assessment/test_decision_filas_tecnicas.py` (control y registro) y `tests/assessment/test_listar_decisiones_tecnicas.py` (listado). Corte vertical: el caso chico y público de `tests/assessment/test_technical_ok.py` (fixture `pending`: `procedure` de `tests/offers/conftest.py`, oferta «Oferente Z» hecha con `make_offer`, filas técnicas de los renglones 1, 2 y 3 pendientes del informe técnico con `requirement(procedure, item=i)` y `add_run`, y la declaración jurada como fila no técnica cumplida). El archivo nuevo arma ese mismo caso; no se inventa otro.

| Requisito | Cómo se resuelve | Cómo se verifica |
|---|---|---|
| REQ-159 | Componente 1 (control en `_decide`) | `test_every_request_on_a_technical_row_is_refused[via-accion-situacion]`: 12 combinaciones (vía 1 y vía 2 × confirmar, corregir, rechazar × oferta sin ok y con ok), todas con respuesta de rechazo y 0 `Decision` nuevas (cuenta antes y después). `test_requests_are_refused_after_the_ok_is_given_and_withdrawn`: ok dado y después retirado con `withdraw_ok`, las 6 combinaciones por vía. `test_a_request_on_a_replaced_technical_result_gives_the_same_reason`: pedido sobre el resultado viejo de la fila, mismo motivo. `test_the_service_refuses_without_going_through_a_view`: llamada directa a `review.decide`, `confirm`, `correct`, `reject`. |
| REQ-160 | Componentes 2 y 3 | `test_a_refused_request_changes_nothing`: resultado, `state_of`, `history` y cuenta de `Decision` iguales antes y después. `test_a_refused_request_leaves_its_fact`: un hecho `eval_decision` con `outcome = rejected`, usuario, fecha, `result`, `offer`, `requirement`, `action` y `reason = technical_row`. `test_the_message_names_the_technical_report_ok`: el texto de ambas vías contiene «ok del informe técnico» y ninguno de `technical_row`, `result`, `reason`, `id`. |
| REQ-161 | Estructura (el ok no pasa por `decide`) y el control solo mira filas técnicas | `test_non_technical_rows_are_decided_as_before` (declaración jurada: confirmar, corregir con motivo y rechazar con motivo guardan decisión y hecho `ok`, por las dos vías). `test_the_ok_still_decides_the_technical_row`: `give_ok` deja el cruce como «cumple» o «no cumple» con `facts["technical_ok"]`, y `withdraw_ok` lo devuelve a pendiente. Además, sin cambios: `tests/assessment/test_review.py`, `test_technical_ok.py`, `test_technical.py`, `test_technical_report.py`, `test_result_actions.py`, `tests/journey/temas/test_s4_propuesta.py` y `tests/journey/proceso/test_par_parcial.py` pasan sin editar una línea. Si alguno falla, es un hallazgo y se informa; no se edita el test. `test_no_new_migration_and_screen_unchanged`: sin migraciones nuevas y plantillas sin cambios. |
| REQ-162 | Componente 5 | `test_the_list_shows_the_technical_decision_and_not_the_others`: una `Decision` puesta a propósito sobre una fila técnica y otras sobre filas no técnicas; el listado trae la primera con procedimiento, oferta, requisito, acción, usuario y fecha, y ninguna otra. `test_the_list_changes_nothing`: cuentas de `Decision`, `Result` y `AuditEvent` iguales antes y después. `test_the_command_prints_the_total`: el comando imprime la fila y «Total: 1». |
| RNF 0,1 s | El control no suma consultas | `test_the_control_adds_no_query_and_takes_less_than_0_1_s`: con el requisito ya cargado, el control hace 0 consultas y tarda menos de 0,1 s. |
| RNF 30 s | Una consulta, filtro en memoria | `test_the_list_uses_a_fixed_number_of_queries` (como mucho 2, sin depender de la cantidad de procedimientos). El tiempo con los 10 procedimientos reales se mide en la corrida del cierre (T-366) y solo se anota. |

**Criterio numérico (ADR-0025).** Umbral escrito antes de medir: **12 de 12 pedidos rechazados y 0 decisiones guardadas** sobre filas técnicas (2 vías × 3 acciones × 2 situaciones), y **0 cambios** en las filas no técnicas (las pruebas existentes pasan sin editarse). Una ronda de ajuste es suficiente; el máximo es dos. El primer paso se prueba con el caso chico antes de mirar los procedimientos reales.

## Verificación contra la constitución

| Principio | Cumple | Nota |
|---|---|---|
| P3 Humano decide | sí | El control cierra el hueco: ningún resultado técnico sin el informe del área |
| P4 Datos | sí | Pruebas con el caso chico y público; el listado real no se sube, solo la cuenta; el camino de pliegos y ofertas no usa servicios externos |
| P5 Local y reproducible | sí | Sin dependencias ni servicios nuevos |
| P6 Auditoría | sí | El rechazo queda como hecho con usuario, fecha, cruce, acción y motivo |
| P10 Simplicidad | sí | Un control, un argumento opcional, un listado de solo lectura; nada que la spec no pida |

## Decisiones

**No hace falta un ADR nuevo.** Ninguna decisión cuesta revertir: sin esquema, sin librería, sin modelo; el control son unas líneas en un servicio y se quita borrándolas. La regla de fondo (nunca por esa vía) ya está decidida por el responsable el 2026-11-18 y queda en la spec; el criterio de la fila técnica reutiliza `sheets.is_item_row` (spec 004 / ADR-0043).

## Tareas estimadas (numeración desde T-364; `tasks.md` va tras la aprobación del plan)

| Tarea | Qué | Requisitos | Archivos | Depende de |
|---|---|---|---|---|
| T-364 | Corte vertical y control: `ReviewRefused` con `detail`, el control en `_decide`, motivo, mensaje y tests de REQ-159, 160 y 161 con el caso chico. Verificación plena | REQ-159, REQ-160, REQ-161 | `assessment/services/review.py`, `tests/assessment/test_decision_filas_tecnicas.py` | — |
| T-365 | Listado de solo lectura y sus tests | REQ-162 | `assessment/services/technical_decisions.py`, `assessment/management/commands/listar_decisiones_tecnicas.py`, `tests/assessment/test_listar_decisiones_tecnicas.py` | — (no comparte archivos con T-364; se puede en paralelo) |
| T-366 | Cierre: correr el listado sobre los procedimientos reales del equipo, anotar solo la cuenta y el tiempo, y la suite completa sobre main | REQ-162 | registro de verificación (solo la cuenta) | T-364, T-365 |

## Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Una prueba existente decide una fila técnica por renglón y deja de pasar | Hallazgo, no un fallo del plan: esa prueba afirmaba lo que la spec prohíbe | Se corre primero, se informa y decide el Coordinador; no se edita sin avisar |
| El control rechaza de más (fila de clase técnica sin renglón) | Una fila no técnica quedaría sin poder decidirse | Se usa la misma definición que el resto (`is_item_row`, que exige renglón); test con una fila técnica sin renglón que sí se decide, si el caso chico la tiene; si no, se prueba con un requisito armado a mano |
| Importar `sheets` en `review.py` crea un ciclo | No levanta el sistema | `technical.py` ya importa `sheets` desde el mismo paquete; `offers` no importa `assessment` salvo una importación local en `document_history.py:238`. Se confirma al correr el test |
| El listado real halla decisiones guardadas | Hay un dictamen con una conclusión sin respaldo | Fuera de alcance corregirlas: se informan al responsable, que decide (spec, «Fuera de alcance») |

## Dudas para el responsable o el Coordinador

1. **Subsanación sobre una fila técnica.** `remedy.py` l. 207 y l. 313 crea decisiones de pedir y registrar la subsanación, y `is_remediable` (l. 83) las acepta si el resultado rige como «sin documento». REQ-159 habla de confirmar, corregir y rechazar, así que este plan no las cubre. Falta saber si una fila técnica por renglón puede llegar a «sin documento»; si puede, queda un hueco parecido. No se agrega control (P10); se informa. **Revisión del Coordinador (2026-11-18):** una fila técnica sí puede quedar en «no se encontró el documento» (`assessment/technical.py` l. 218-223), así que pedir o registrar una subsanación sobre ella es posible. Pero esas dos acciones son recorrido y no fijan el resultado ni el estado del cruce (`review.py`, `STATE_ACTIONS`): no pueden dejar un «cumple» sin informe, que es el problema de esta spec. Queda fuera de alcance y se informa al responsable al pedir la aprobación del plan.
2. **Alcance de «fila técnica».** El control usa «clase técnica y con renglones» (`sheets.py` l. 276). Una fila técnica sin renglones se decide como hoy. Es lo que dice la spec («por renglón»).
3. **Listado de todas las acciones.** REQ-162 pide «acción»; el listado trae también pedir/registrar subsanación sobre filas técnicas, no solo las tres. Es un superconjunto; no contradice la spec.
