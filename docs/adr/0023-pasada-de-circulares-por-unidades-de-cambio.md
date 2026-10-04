# ADR-0023 · Pasada de circulares: unidades de cambio aplicadas por clave, con el modelo solo donde no hay clave

Estado: aceptado · Fecha: 2026-10-04 · Decidió: responsable del proyecto (opción a, en dos entregas, con las seis decisiones de abajo)

## Contexto

REQ-031 pide que las circulares y las respuestas a consultas cambien o precisen los requisitos, mostrando los dos textos y citando el documento. La pasada de T-083 (corregida en T-098) trabaja por tramo: para cada tramo que dejó la lectura arma candidatas del pliego (nombradas por cláusula, aludidas por anexo, las 8 del reranker) y el modelo elige una cita y un efecto.

El diagnóstico de T-113 (`specs/003-pliego-matriz/verificacion/T-113-diagnostico.md`), hecho en solo lectura sobre la corrida del caso-01 con circulares reales, encontró que los fallos no son de parámetros sino de lo que se le hace decidir al modelo:

- La unidad de trabajo es el tramo de la lectura y no el cambio que la circular declara: una lista de 79 líneas son 79 pedidos; "Donde dice" y "Debe decir" son pedidos distintos.
- Lo que la circular dice con precisión (cláusula 7.5.4, Anexo VI, Renglón N) se deja a la elección del modelo; la clave solo ordena candidatas.
- Un efecto por cita elegida no representa "se reemplaza la cláusula" (todas sus citas: M-013) ni "el anexo no es requisito" (el anexo y quien lo exige: M-029).
- Las citas comunes a los 18 renglones multiplican por 18 cada elección dudosa (72 fuentes ajenas); las listas de datos generan 20 requisitos de más; "Anexo IV de la Disposición…" se toma como anexo del pliego (540 aludidas).
- La salida no es estable (mismo texto, mismas candidatas: `modifica` o `titulo`), y 99 pedidos tardan 432 s y 836.000 tokens.

Cada falla de T-094 y T-098 se corrigió con una regla propia del caso y cada corrección abrió otra. Los casos de aceptación (03 y 04) traerán otras formas. Restricciones: P3 (la cita es literal y la comprueba el sistema), P4 (todo local), P7 (cada cambio de instrucciones se mide), P10 (lo mínimo que cumple la spec), y el esquema se cambia solo con aprobación.

## Alternativas

### a. Unidades de cambio aplicadas por clave, el modelo extrae la lista donde no hay clave (elegida)

Se parte cada circular en unidades de cambio (cláusula numerada, apartado completo, par "Donde dice / Debe decir"); el objetivo (cláusula, anexo, renglón, texto anterior) se resuelve con código contra el pliego y el efecto se aplica a **todas** las citas afectadas; las listas de datos del trámite no son requisitos; una norma externa no es un anexo del pliego. En una segunda entrega el modelo extrae la lista estructurada de cambios de cada unidad (sin ver el pliego) donde no hay clave, y el flujo actual queda como respaldo.
- Se gana: lo que la circular nombra por número se resuelve exacto y siempre igual; resuelve M-013, M-029, M-044 completo y el ruido; pocos pedidos cortos, repetibles y comparables (5 a 10 veces menos tokens, estimado); no pide un parche por cada forma de circular nueva; los errores del modelo quedan en una lista corta y revisable.
- Se pierde: un módulo nuevo (unas 300 a 400 líneas por entrega y 30 a 40 % de `circulars.py`); un error de partición se arrastra a las citas de su unidad; la resolución por clave depende de que la circular diga el número y de que el pliego tenga esa clave (si no, respaldo); una migración chica (campo de original en el anexo).

### b. Ajustes incrementales al diseño actual (descartada)

Agrupar el apartado en un tramo; aplicar a toda la cláusula el `modifica` elegido; no tomar como anexo del pliego las normas externas y topar las aludidas; exigir que el tramo nombre la cláusula o el renglón para efectos sobre citas comunes; emparejar "Donde dice" con "Debe decir". Una tarea, 100 a 200 líneas.
- Se gana: costo inicial bajo y riesgo menor al empezar.
- Se pierde: M-029 queda sin resolver salvo una sexta regla; M-044 queda parcial (el original sigue siendo la cláusula 13.2, no el anexo); cada ajuste sale de lo visto en el caso-01, el mismo patrón que ya falló dos veces, sin garantía para 03 y 04; el modelo sigue decidiendo por tramo lo que el código podría decidir; la salida sigue sin ser estable; tiempo y tokens no bajan.

### c. No tocar y aceptar lo medido (no considerada)

REQ-031 no se cumple de manera repetible en el caso-01. No es una alternativa.

## Decisión

Se adopta **a, en dos entregas**, con estas decisiones del responsable (2026-10-04):

1. **Entrega 1, sin modelo (T-113):** partir cada circular en unidades de cambio; aplicar cada cambio por clave de cláusula, renglón o anexo a **todas** las citas afectadas; tratar las listas de datos del trámite (fechas, horas, lugares de visita) como dato del trámite y no como requisito; una referencia a una norma externa no se confunde con un anexo del pliego.
2. **Entrega 2, con modelo (T-115):** el modelo extrae la lista estructurada de cambios de cada circular donde no hay clave; el flujo actual queda como respaldo.
3. **Original en un anexo sin requisitos:** la fuente de circular guarda una referencia al tramo del anexo donde está el texto original: campo nuevo y migración, en una sola tarea de esquema (T-114).
4. **Requisito que agrega una circular:** la pantalla y la impresión toman documento y fecha del tramo de su cita, sin migración (descartada la alternativa de un efecto `agrega`, que habría cambiado el conjunto de efectos de la tabla).
5. **Filas de un anexo que la circular suprime** cuentan como afectadas y esperadas; el Coordinador actualiza la lista del caso-01.
6. **Más casos de ajuste:** caso-05 (A0KJ000000-0008-LPU24, precintos, circulares con respuestas a consultas) y caso-06 (A0PC000000-0007-LPU26, bases online, circular aclaratoria). Los casos 03 y 04 siguen reservados para la aceptación y no se miran. La extracción con modelo se repite 3 veces sobre el caso-01 para medir la estabilidad.

Motivo principal: los fallos son de lo que se le hace decidir al modelo; lo que tiene clave lo resuelve el código y el modelo queda para lo que requiere lectura. Es la única opción que no pide un parche más por cada forma de circular nueva.

## Consecuencias

**Más fácil**
- Una circular se aplica de la misma manera cada vez; los tests de aplicación no necesitan modelo.
- La pasada baja de 99 pedidos a unos pocos; el historial "modificada por …" se muestra una vez por cambio.
- REQ-031 se mide automáticamente por fila (texto original, vigente, documento y fecha) en vez de a ojo.

**Más difícil**
- Dos módulos nuevos (`circular_units.py`, `circular_changes.py`) y un flujo de respaldo que seguir manteniendo.
- Una migración (tres campos opcionales en `tenders_requirement_source`, un valor de `pass_name`, parámetros), con copia al abrir una versión nueva.
- Las constantes de las listas de datos (línea corta, mayoría) y las listas de verbos se calibran con casos reales y se vuelven a medir.
- Cambios de archivo en `proposal/run.py` y `evaluation.py`, que otras tareas de la 003 tocan; se encadenan en `tasks.md`.

**Para revertir**
- `CIRCULAR_EXTRACTION_ENABLED` en falso deja solo la entrega 1 con el respaldo actual. Los campos nuevos nulos son válidos con el flujo anterior; el respaldo conserva el comportamiento de T-098.

## Sin verificar

- Cuántos cambios de las circulares de los casos 05 y 06 tienen clave y cuántos van al respaldo (T-120).
- Si el modelo extrae la lista de cambios de forma estable en tres repeticiones sobre el caso-01 (T-120).
- Si los umbrales de "lista de datos" generalizan a otras listas (listas de precios, de plazos). Se ajustan con los casos 05 y 06, no con 03 ni 04.
- Cuánto tarda y cuántos tokens usa la entrega 2 respecto de los 432 s y 836.000 medidos (estimación del diagnóstico: 5 a 10 veces menos).
