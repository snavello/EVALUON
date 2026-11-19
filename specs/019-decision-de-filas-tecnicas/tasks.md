# Tareas 019 · Las filas técnicas se deciden solo con el ok del informe técnico

Plan: `specs/019-decision-de-filas-tecnicas/plan.md` (aprobado el 2026-11-18 por el responsable, «Sí, apruebo»; sin ADR nuevo)

Despliegue: pendiente

> El tablero (`docs/tablero.md`) se genera de este archivo. Al aprobarse el despliegue, la línea de arriba pasa a `Despliegue: aprobado AAAA-MM-DD`.

Estados: pendiente · en curso · en verificación · terminada · bloqueada

Dos tareas que no dependen entre sí y no comparten archivos se pueden hacer en paralelo.

**Ritmo de trabajo (ADR-0024 y ADR-0025).** Las ramas de tarea no tocan este archivo ni el tablero: el Coordinador los actualiza una vez por lote. La verificación de cada tarea queda en `specs/019-decision-de-filas-tecnicas/verificacion/T-NNN.md`. Toda medición escribe antes su umbral y tiene dos rondas como máximo; lo que no llegue pasa, con su impacto, a la lista de revisión. Con tareas en paralelo, cada desarrollador corre solo los tests de su área (`pytest tests/assessment -q`, con un proyecto de Compose propio); la suite completa se corre una sola vez, en T-366, sobre la rama combinada con `main` (ADR-0012). Commits de código: `T-NNN (REQ-NNN): qué cambia`. Ninguna tarea toca el esquema de la base ni genera migraciones. La auditoría y el despliegue son etapas del flujo, no tareas.

**IDs.** T-364 a T-366. En `main` el último ID usado es T-363. El Coordinador confirma contra las ramas abiertas antes de lanzar.

## Oleadas de paralelismo

| Oleada | Tareas | Qué habilita |
|---|---|---|
| 1 | T-364 (control en el servicio de decisión y corte vertical), T-365 (listado de solo lectura) | No comparten archivos ni dependen entre sí |
| 2 | T-366 (cierre sobre los procedimientos reales y suite completa) | Espera a T-364 y T-365 integradas en `main` |

## Definiciones compartidas (escritas antes de lanzar)

1. **Qué es una fila técnica por renglón.** `sheets.is_item_row(requirement)` (`evaluon/offers/services/sheets.py`): clase técnica y con renglones. T-364 (control) y T-365 (listado) la reutilizan; ninguna la copia.
2. **Caso chico y público.** El de `tests/assessment/test_technical_ok.py` (fixture `pending`: `procedure` de `tests/offers/conftest.py`, oferta «Oferente Z» con `make_offer`, filas técnicas de los renglones 1, 2 y 3 con `requirement(procedure, item=i)` y `add_run`, y la declaración jurada como fila no técnica cumplida). Los archivos de pruebas nuevos lo arman igual; no se inventa otro ni se abre `corpus/casos/` (P4).
3. **Motivo y mensaje del rechazo** (T-364): `reason = "technical_row"`, `field = "result"`; mensaje «Esta fila es técnica y no se decide acá: la resuelve el informe técnico del área. Para cerrarla, dé el ok del informe técnico de la oferta.»
4. **Regla sobre pruebas existentes.** Si una prueba existente deja de pasar, se informa al Coordinador y no se edita.

## Umbrales de las mediciones (escritos antes de medir)

| Qué | Umbral | Con qué se mide |
|---|---|---|
| Pedidos sobre filas técnicas | 12 de 12 rechazados y 0 decisiones guardadas (2 vías × 3 acciones × 2 situaciones) | `test_every_request_on_a_technical_row_is_refused` (T-364) |
| Filas no técnicas | 0 cambios: las pruebas existentes pasan sin editarse | `tests/assessment/` y `tests/journey/` indicados en T-364, y suite completa en T-366 |
| Costo del control | menos de 0,1 s y 0 consultas nuevas | `test_the_control_adds_no_query_and_takes_less_than_0_1_s` (T-364) |
| Listado | como mucho 2 consultas; menos de 30 s con los 10 procedimientos reales | `test_the_list_uses_a_fixed_number_of_queries` (T-365); tiempo real anotado en T-366 |

## Resumen

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-364 | Rechazar en el servicio de decisión todo pedido sobre una fila técnica por renglón, con el caso chico | REQ-159, REQ-160, REQ-161 | — | en curso |
| T-365 | Listar las decisiones guardadas sobre filas técnicas (solo lectura) | REQ-162 | — | en curso |
| T-366 | Cierre: listado sobre los procedimientos reales (solo la cuenta y el tiempo) y suite completa | REQ-162 | T-364, T-365 | pendiente |

## Detalle

### T-364 · Rechazar en el servicio de decisión todo pedido sobre una fila técnica por renglón, con el caso chico

- **Requisitos:** REQ-159, REQ-160, REQ-161.
- **Nivel:** plena (toca lógica de decisión y un principio, P3).
- **Qué hay que hacer:** (1) Sumar a `ReviewRefused` un argumento opcional `detail=None` que `_refuse_record` mezcla en el detalle del hecho; los demás rechazos quedan idénticos. (2) En `_decide`, justo después de cargar el resultado y **antes** de la comprobación de «resultado reemplazado»: si `sheets.is_item_row(result.requirement)` y la acción está en `STATE_ACTIONS`, lanzar `ReviewRefused` con `reason = "technical_row"`, `field = "result"`, el mensaje de la Definición 3 y `detail` con `offer` y `requirement`. `unknown_action` y `result_not_found` siguen antes y no cambian. No agrega consultas (el requisito ya viene con `select_related`). Reutiliza `sheets.is_item_row`; si la importación crea un ciclo, se informa. (3) Escribir primero los tests con el caso chico (corte vertical, ADR-0025) y comprobar que fallan antes del control y pasan después. Tests, todos en `tests/assessment/test_decision_filas_tecnicas.py`:
  - `test_every_request_on_a_technical_row_is_refused[via-accion-situacion]`: 12 combinaciones (vía 1 `expedientes:s4_decidir` y vía 2 `assessment:decide` × confirmar, corregir, rechazar × oferta sin ok y con ok), todas rechazadas y con 0 `Decision` nuevas (cuenta antes y después).
  - `test_requests_are_refused_after_the_ok_is_given_and_withdrawn`: ok dado y retirado con `withdraw_ok`; las 6 combinaciones por vía.
  - `test_a_request_on_a_replaced_technical_result_gives_the_same_reason`.
  - `test_the_service_refuses_without_going_through_a_view`: llamada directa a `review.decide`, `confirm`, `correct` y `reject`.
  - `test_a_refused_request_changes_nothing`: resultado, `state_of`, `history` y cuenta de `Decision` iguales antes y después.
  - `test_a_refused_request_leaves_its_fact`: un hecho `eval_decision` con `outcome = rejected`, usuario, fecha, `result`, `offer`, `requirement`, `action` y `reason = technical_row`.
  - `test_the_message_names_the_technical_report_ok`: el texto de ambas vías contiene «ok del informe técnico» y ninguno de `technical_row`, `result`, `reason`, `id`.
  - `test_non_technical_rows_are_decided_as_before`: declaración jurada, confirmar, corregir con motivo y rechazar con motivo guardan decisión y hecho `ok`, por las dos vías; incluye, si el caso chico lo permite (si no, con un requisito armado a mano), una fila de clase técnica sin renglón que sí se decide.
  - `test_the_ok_still_decides_the_technical_row`: `give_ok` deja el cruce como «cumple» o «no cumple» con `facts["technical_ok"]` y `withdraw_ok` lo devuelve a pendiente.
  - `test_the_control_adds_no_query_and_takes_less_than_0_1_s`.
  - `test_no_new_migration_and_screen_unchanged`: sin migraciones nuevas en `evaluon/*/migrations/` y plantillas sin cambios.
- **Aviso de tareas anteriores:** (vacío)
- **Archivos:** `evaluon/assessment/services/review.py`, `tests/assessment/test_decision_filas_tecnicas.py`.
- **Verificación:** `pytest tests/assessment -q` con un proyecto de Compose propio (sin suite completa: va una sola vez, en T-366). Además, sin editar una línea y en verde: `tests/assessment/test_review.py`, `test_technical_ok.py`, `test_technical.py`, `test_technical_report.py`, `test_result_actions.py`, `tests/journey/temas/test_s4_propuesta.py` y `tests/journey/proceso/test_par_parcial.py`. Si alguna de estas deja de pasar, se informa y no se edita. El 12 de 12 y el 0 decisiones guardadas se anotan en `verificacion/T-364.md`.
- **No tocar:** vistas, pantalla y plantillas, `technical.py`, `remedy.py`, modelos, migraciones, `tasks.md` y el tablero.

### T-365 · Listar las decisiones guardadas sobre filas técnicas (solo lectura)

- **Requisitos:** REQ-162.
- **Nivel:** plena (consulta sobre decisiones registradas; el resultado es material reservado con datos reales).
- **Qué hay que hacer:** (1) `technical_decisions.py` con `technical_row_decisions()`: trae con una consulta las `Decision` cuyo `result.requirement` es de clase técnica (`select_related("result__offer__procedure", "result__requirement", "user")`) y filtra en Python con `sheets.is_item_row` (misma definición que el control de T-364; no se copia). Devuelve procedimiento, oferta, requisito, acción, usuario y fecha, ordenados; incluye todas las acciones, no solo las tres. (2) Comando `listar_decisiones_tecnicas` que lo imprime por salida estándar y cierra con «Total: N». Solo lee: no escribe en la base ni deja hecho. Tests, en `tests/assessment/test_listar_decisiones_tecnicas.py`, con el caso chico y datos inventados:
  - `test_the_list_shows_the_technical_decision_and_not_the_others`: una `Decision` puesta a propósito sobre una fila técnica y otras sobre filas no técnicas; el listado trae la primera con procedimiento, oferta, requisito, acción, usuario y fecha, y ninguna otra.
  - `test_the_list_changes_nothing`: cuentas de `Decision`, `Result` y `AuditEvent` iguales antes y después.
  - `test_the_command_prints_the_total`: el comando imprime la fila y «Total: 1».
  - `test_the_list_uses_a_fixed_number_of_queries`: como mucho 2 consultas, sin depender de la cantidad de procedimientos.
- **Aviso de tareas anteriores:** (vacío)
- **Archivos:** `evaluon/assessment/services/technical_decisions.py`, `evaluon/assessment/management/commands/listar_decisiones_tecnicas.py`, `tests/assessment/test_listar_decisiones_tecnicas.py`.
- **Verificación:** `pytest tests/assessment -q` con un proyecto de Compose propio (sin suite completa: va una sola vez, en T-366). Si una prueba existente deja de pasar, se informa y no se edita. No se corre el comando sobre datos reales en esta tarea (eso es T-366).
- **No tocar:** `review.py` (T-364), modelos, migraciones, vistas, plantillas, `tasks.md` y el tablero.

### T-366 · Cierre: listado sobre los procedimientos reales y suite completa

- **Requisitos:** REQ-162.
- **Nivel:** plena (sin código de producto).
- **Qué hay que hacer:** con T-364 y T-365 integradas en `main`, la hace el Coordinador con el testeador evaluador: (1) correr `listar_decisiones_tecnicas` sobre los procedimientos reales del equipo propio (10 hoy), medir el tiempo (umbral: menos de 30 s) y anotar solo la cuenta N y el tiempo. La salida con nombres o contenidos no va al repositorio (P4). Si N es mayor que 0, no se borra ni se corrige nada: se informa al responsable, que decide. (2) Correr la suite completa una vez sobre `main` e informar con qué commit se corrió (ADR-0012). (3) Comprobar el criterio numérico: 12 de 12 rechazados, 0 decisiones guardadas y 0 cambios en filas no técnicas.
- **Aviso de tareas anteriores:** (vacío)
- **Archivos:** `specs/019-decision-de-filas-tecnicas/verificacion/T-366.md` (solo la cuenta, el tiempo y el commit de la suite; sin código).
- **Verificación:** el registro dice N, el tiempo del listado, el commit de `main` y el resultado de la suite completa; sin ese archivo la tarea no pasa a terminada.
- **No tocar:** código de producto y tests; corrección de decisiones ya guardadas, si las hubiera (fuera de alcance).
