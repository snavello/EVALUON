# ADR-0068 · Registro de los pedidos externos en la auditoría y tope de gasto hecho cumplir en código

Estado: propuesto · Fecha: 2026-10-15 · Propuso: planificador (plan 016) · Decidió: —

## Contexto

El ADR-0065 (punto 4) pide que cada pedido a una API externa quede en el registro de auditoría con proveedor, modelo, versión de la instrucción, fragmentos enviados y respuesta, y que el registro de la evaluación diga qué etapas corrieron fuera del equipo (P6). La spec 016 (REQ-122) lo concreta y suma el tope de gasto del responsable (2026-10-15): **2 USD por caso completo y 10 USD por mes**, con la obligación de registrar el gasto real por etapa y de frenar una etapa que pase el doble de su estimación.

Lo que ya existe: `audit_event` es una tabla de solo inserción (disparador de la migración 0002) con tipo, resultado, canal, usuario y un campo JSON `detail`, que ya guarda las corridas de matriz y de evaluación con sus modelos, parámetros e instrucciones (`MATRIX_PROPOSAL`, `EVAL_BUILD`). Cada corrida local además guarda cada pedido en `tenders_run_step` y `assessment_step`. El externo no es determinista (sin semilla), así que lo único que permite reconstruir qué dijo es guardar el pedido y la respuesta completos.

## Alternativas

### A. Un tipo de hecho nuevo, `external_request`, en `audit_event`, y el libro de gasto como suma de esos hechos (propuesta)

Un hecho por pedido, con el texto enviado, la respuesta, los tokens y el costo en `detail`. El tope se calcula sumando `detail.costo_usd` del mes y del procedimiento. Se gana: una sola migración de una línea, solo inserción (nadie puede editar un pedido), y el mismo lugar que los demás hechos de P6. Se pierde: `detail` es JSON, así que la suma se hace con una consulta sobre el JSON; los pedidos son grandes (hasta unos 250 KB de pliego por pedido).

### B. Una tabla propia `audit_external_request` con columnas tipadas

Se gana: consultas simples, índices por mes y procedimiento, tamaño controlado. Se pierde: una migración mayor, otro disparador de solo inserción y un modelo más, para algo que `audit_event` ya hace.

### C. Guardar los pedidos solo en archivos de la corrida, fuera de la base

Se gana: nada pesado en la base. Se pierde: no está en el registro de auditoría de P6, no es de solo inserción y el tope no podría contar lo gastado por otras corridas.

### D. Confiar solo en el límite de gasto de la consola del proveedor

Se gana: no hay código. Se pierde: no frena por etapa ni por caso, no sabe cuánto es de cada medición, y avisa tarde.

## Decisión

Se propone **A**, con el límite de la consola como segundo freno.

1. **Un hecho por pedido** (`external_request`): proveedor; modelo pedido y modelo devuelto; etapa; nombre, versión y huella de la instrucción (y del bloque de definiciones); modo (`lotes` o `directo`), identificador del lote y del pedido; parámetros (esfuerzo, pensamiento, `max_tokens`, formato de salida); procedimiento, oferta y requisito; corrida; el texto enviado tal como salió; la huella del pedido; la respuesta completa; el uso (entrada, salida, escritura y lectura de caché); el costo en USD; la versión, la fecha y la fuente de la tabla de precios; la duración; el resultado (`ok`, `error`, `vencido`, `bloqueado` o `reutilizado`); y lo que comprobó la puerta de filtrado (ADR-0067). Un pedido bloqueado no lleva texto.
2. **En las corridas**, la clave `externo` de `models`, `parameters` o `models_used` y de `counts` dice qué etapas fueron `externo` o `local`, con modelo, modo, cantidad de pedidos y gasto; de ahí sale la línea «Etapas fuera del equipo» de la pantalla y de la exportación de la evaluación.
3. **Tabla de precios versionada** (`EXTERNAL_PRICES` en la configuración, con versión, fecha y fuente). El costo se calcula con el uso que informa el proveedor, no con una estimación.
4. **El libro** (`ledger.py`) suma el costo del mes calendario y del procedimiento antes de cada lote, con una estimación conservadora de tokens (caracteres entre 2,5). Si el pedido haría pasar el caso de 2 USD o el mes de 10 USD, no sale: queda `bloqueado` con el motivo «tope» y la etapa sigue en local. Una etapa que supera el doble de su estimado (0,60 USD para la matriz y para el verificador) se frena y se informa antes de seguir.
5. **Reuso por huella.** Un pedido con la misma huella (pedido, modelo, parámetros, versión) que uno ya respondido en la misma medición se contesta con la respuesta guardada y queda como `reutilizado`, con costo 0. Es un control de gasto ligado al tope.
6. **Comando** `manage.py gasto_externo [--mes] [--procedimiento] [--por-etapa] [--verificar-filtro]`: el gasto real por etapa que cada medición pega en su registro, y el escaneo independiente del filtro (ADR-0067).
7. **Segundo freno**: el límite mensual de 10 USD del espacio de trabajo de la clave en la consola del proveedor.

## Consecuencias

- Más fácil: reconstruir por qué el sistema dijo lo que dijo aunque el externo no se repita; saber el gasto por etapa; recalcular las cifras de una medición sin pagar de nuevo.
- Más difícil: la base del clon crece con los pedidos (unos MB por caso); la suma sobre JSON se hace con una consulta menos directa que una columna. Si el uso externo pasara a ser de producción y diario, convendría la alternativa B.
- Una migración: `evaluon/audit/migrations/0009_*.py`, que agrega un valor permitido a `EventType`.
- Para revertir: dejar de usar las etapas externas; los hechos ya guardados quedan como registro. La migración no necesita deshacerse.
