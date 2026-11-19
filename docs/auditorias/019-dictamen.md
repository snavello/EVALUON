# Dictamen de auditoría de fallas · Feature 019 (las filas técnicas se deciden solo con el ok del informe técnico)

- **Alcance:** `specs/019-decision-de-filas-tecnicas/`, rango 5a59ef7c^..25ba77ad (`origin/main`), 20 commits, 14 archivos (código: `review.py`, `technical_decisions.py`, `listar_decisiones_tecnicas.py`). Auditoría de fallas según ADR-0036 y ADR-0052. Copia propia `.claude/worktrees/aud019` y proyecto docker propio `evaluon-aud019` (dado de baja con `down -v`).
- **Resultado:** aprobado con observaciones

## Hallazgos

Sin hallazgos bloqueantes. Nada impide funcionar ni expone datos.

1. **Menor, no bloqueante · P3 (hueco conocido, fuera de alcance).** `evaluon/assessment/services/remedy.py` l. 207 y l. 313 siguen creando `Decision` (pedir y registrar subsanación) sobre una fila técnica por renglón, sin el control de `review.py` l. 162-168. El plan (duda 1) lo declara fuera de alcance y razona que esas acciones no fijan el resultado ni el estado del cruce, por lo que no producen un «cumple» sin informe. Está informado en `verificacion/T-366.md`. Queda a decisión del responsable.
2. **Menor, no bloqueante · observación del propio cierre.** La base no impide una decisión insertada sin pasar por el servicio; el control es el listado de REQ-162. Se corrió sobre una copia del piloto (0 de 52), no sobre el piloto: queda repetirlo al desplegar, como anota T-366.

## Para la auditoría de cumplimiento (no bloquea)

- No revisé trazabilidad completa commit a tarea ni la redacción de las verificaciones; T-364 a T-366 figuran terminadas y cada una tiene archivo en `verificacion/`.

## Lo que se controló y está bien

- **Pruebas (P7):** `tests/assessment/test_decision_filas_tecnicas.py`, `test_listar_decisiones_tecnicas.py` y `test_technical_ok.py` sobre origin/main, contenedor y base propios: **55 pasaron, 0 fallaron**, 40 s. Sin `skip` ni `xfail` en los dos archivos nuevos. No corrí la suite completa (encargo; T-366 informa 8505 pasan, 29 salteados, sin verificarlo yo).
- **REQ-159/160:** `review._decide` rechaza con `technical_row` toda fila `sheets.is_item_row`, antes de mirar si el resultado fue reemplazado, sin crear `Decision`; el rechazo se registra por `_refuse_record` con usuario, oferta, requisito, acción y motivo, y el mensaje es llano y nombra el ok del informe técnico. Ambas vías (pantalla y propuesta de acciones) pasan por `review.decide`; no hay otro `Decision.objects.create` de confirmar/corregir/rechazar.
- **REQ-161:** el cambio en el servicio es una rama previa; las pruebas existentes de decidir y del ok técnico pasan sin edición.
- **REQ-162:** el servicio es de solo lectura (2 consultas, filtro por la misma definición `is_item_row`); el comando exige ingreso con rol de operador de la Comisión y no imprime nada sin él.
- **Tablero:** `python tools/tablero.py --check` responde que `docs/tablero.md` está al día.
- **P4:** sin URLs, claves ni clientes externos en el código ni en las pruebas nuevas (las coincidencias de «password» son la clave de prueba sintética); la salida del listado sobre datos reales no se sube (solo la cuenta).
- **P6:** el rechazo deja hecho de auditoría con resultado «rechazado».

## Lo que no pude verificar

- La suite completa y las evals (el encargo lo excluye).
- El listado sobre el piloto real y el comando con clave tipeada (no accedo a datos reservados).
- Historial completo de git en busca de secretos: revisé solo el diff del rango.
