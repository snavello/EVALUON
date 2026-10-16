# Tareas 016 · Calidad medible: verdad ampliada, instrucciones simples y modelos externos por clase de dato

Plan: `specs/016-calidad-medible/plan.md` (aprobado el 2026-10-15 por el responsable, pull request 342)

Despliegue: pendiente

> El tablero (`docs/tablero.md`) se genera de este archivo. Al aprobarse el despliegue, la línea de arriba pasa a `Despliegue: aprobado AAAA-MM-DD`.

Estados: pendiente · en curso · en verificación · terminada · bloqueada

Dos tareas que no dependen entre sí y no comparten archivos se pueden hacer en paralelo.

Ritmo de trabajo (ADR-0024 y ADR-0025): las ramas de tarea no tocan este archivo ni el tablero; el Coordinador los actualiza una vez por lote. La verificación de cada tarea queda en `specs/016-calidad-medible/verificacion/T-NNN.md`. Toda medición escribe antes su umbral (la tabla de umbrales del plan, con su número) y tiene como máximo dos rondas: la medición de la ronda 1, un solo ajuste y la re-medición de lo que cambió. Los hallazgos de una medición se corrigen en una sola tarea, con un commit por hallazgo. **Una sola tarea usa la GPU a la vez** y nunca dos mediciones a la vez. Al repositorio solo van cifras y resultados; el texto de los casos y la verdad celda por celda quedan fuera (P4, ADR-0060). Las tareas de esta feature se integran en la rama `016-integracion` (no en `main`) y cierran con `BASE=016-integracion tools/cerrar.sh …`; el Coordinador abre el pull request `016-integracion` → `main` al cerrar cada paso (T-287, T-298, T-306), con la suite completa corrida sobre la combinación (ADR-0012).

**IDs.** T-270 a T-307 son únicos: en `main` el último ID es T-269 (feature 007). El Coordinador confirma contra las ramas abiertas antes de lanzar.

**Condiciones previas.**

- El plan 016 y los ADR 0066 a 0070 (propuestos) los aprueba el responsable antes de lanzar T-270. T-289 y T-290 no arrancan sin los ADR 0066, 0067 y 0068 aceptados.
- **Datos del paso 1 (bloqueo con el responsable).** En el corpus solo el caso-00 tiene ofertas y dictamen; los casos 01 a 06 tienen pliego, circulares y autorización. T-272 no arranca hasta que el responsable aporte, o autorice bajar del Portal, las ofertas y el dictamen de 3 procesos públicos terminados. Mientras tanto avanzan sin esperar T-270, T-271, T-277 a T-282, T-283 y el desarrollo de los pasos 3 y 4; las que necesitan verdad celda por celda (T-284, T-304) y el cierre del paso 1 esperan. Las mediciones del paso 3 (T-293 a T-297) usan solo matrices y no esperan la verdad; el cierre del paso 3 (T-298) espera a T-287 para que el pull request a `main` lleve primero los pasos 1 y 2 aprobados.
- **Clave de la API (bloqueo con el responsable).** T-292 no arranca sin la clave del proveedor, el límite mensual de 10 USD en la consola, la confirmación de la política de retención de datos (ADR-0066, «Sin verificar») y el `.env` del clon con la clave, todo fuera del repositorio.
- Las referencias de T-263, T-266 y T-268 valen mientras el diff de `evaluon/` entre su commit y el commit de arranque del clon no toque la ruta medida; si la toca, la medición del paso mide la referencia de nuevo una vez (B0).

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-270 | Entorno del clon: `docker-compose.clon.yml` y `scripts/clon.sh` (proyecto `evaluon-016`, servicios `clon_*`, base restaurada de un respaldo nuevo, motor propio del 27B, `embeddings` y `reranker` de 8000 por red compartida, ventana de GPU con el cierre y la reapertura de 8000 comprobados), líneas del clon en `.env.example`, variable `BASE` (por omisión `main`) en `tools/cerrar.sh` y `entorno.md`; la rama `016-integracion` | REQ-125 | — | terminada |
| T-271 | Formato de la verdad celda por celda y su cargador: `no_determinado`, fundamento, revisión, huella, congelado, clave por requisito `M-NNN`; `medir_evaluacion --verificar-verdad` (casos, celdas decididas, quién y cuándo, citas ubicadas, 0 corridas en aceptación); verdad del caso chico en el repositorio. Umbral: el caso chico da los conteos esperados y una cita inventada que no está se rechaza | REQ-118 | — | terminada |
| T-272 | Cargar al clon las ofertas, los datos del Portal y el dictamen de los 3 procesos públicos terminados que aporte o autorice el responsable (1 de ajuste y 2 de aceptación), con su lista de requisitos y su lectura; sin correr ninguna evaluación | REQ-118 | T-270, T-271 | pendiente |
| T-273 | Verdad celda por celda del caso de ajuste: un agente lo rehace como la Comisión, sin ver nada del sistema, con fundamento por celda. Umbral 1 a 4 del plan: al menos 40 celdas decididas y 100 % con cita ubicada | REQ-118 | T-271, T-272 | pendiente |
| T-274 | Verdad celda por celda del primer caso de aceptación, con el mismo método y el mismo umbral | REQ-118 | T-271, T-272 | pendiente |
| T-275 | Verdad celda por celda del segundo caso de aceptación, con el mismo método y el mismo umbral | REQ-118 | T-271, T-272 | pendiente |
| T-276 | Cierre del paso 1: documento de revisión por caso, revisión y firma celda por celda del responsable (quién y cuándo en cada celda), congelado de los casos de aceptación y verificación de REQ-118. Umbral 1 a 4: al menos 3 casos (2 de aceptación), 40 celdas decididas por caso y 150 en total, 100 % con quién y cuándo, 0 corridas de evaluación en aceptación | REQ-118, REQ-125 | T-273, T-274, T-275 | pendiente |
| T-277 | Reglas a tres salidas: toda celda lleva su pregunta o su documento nombrado (`combine.py`, conversiones de `evaluate.py`, reglas del Portal), `reglas-v13`, invariante probada sobre todas las combinaciones y conteo en `medir_evaluacion`. Umbral 9: 0 «no se encontró el documento» sin pregunta y 100 % de los «no determinado» con pregunta o documento nombrado; los 245 tests `decision_literal` siguen verdes | REQ-120 | T-271 | terminada |
| T-278 | Pruebas de las instrucciones y tabla de decisiones: tope de largo (decisoras 90 líneas y 9.000 caracteres; demás 50 y 5.000; definiciones 5.000; descripción de campo 80), prueba de no calco contra el corpus (6 palabras seguidas), `revision-instrucciones.md` de la 016 con la tabla decisión → fuente, y adaptación de `test_instrucciones_revisadas.py`. Umbral 5 y 6, aplicados a las versiones nuevas | REQ-119 | — | terminada |
| T-279 | Instrucciones de la matriz, parte 1: bloque común de definiciones, extracción, completitud y unión, nuevas y cortas, sin ejemplos de casos, con versión y huella; `matriz-definiciones-v9`, `matriz-extraccion-v13`, `matriz-completitud-v7`, `matriz-union-v2` | REQ-119 | T-277, T-278 | terminada |
| T-280 | Instrucciones de la matriz, parte 2: filtro, consecuencias, circulares, cambios de circulares y respaldo normativo, nuevas y cortas | REQ-119 | T-279 | terminada |
| T-281 | Instrucciones de la evaluación: evaluación, contraste, cláusulas y reescritura, nuevas y cortas, con las descripciones del esquema de salida de hasta 80 caracteres | REQ-119 | T-280 | terminada |
| T-282 | Instrucciones auxiliares: visión, ficha, ficha por renglón, informe técnico, nombre del oferente, datos del procedimiento y consulta; versión y huella registradas en cada pedido; informe de revisión completo y prueba de que toda instrucción vigente es de la 016 | REQ-119 | T-281 | terminada |
| T-283 | Medición del paso 2, ronda 1 (matrices y caso-00): matrices de 00, 01, 02 y 06; caso-00 completo (matriz y evaluación de las 3 ofertas); evals de la 001, fichas y visión. Umbrales 7 a 12: 0 «cumple» sin fundamento, 0 contradicciones, 100 % literal, lista presente igual o mejor (00 41/42, 01 79/80, 02 95/97, 06 35/35), tres salidas, no empeora, caso-00 completo ≤ 112,6 min y ≤ 22.000 MiB, auxiliares no peor que T-266 | REQ-119, REQ-120, REQ-125 | T-282 | terminada |
| T-284 | Medición del paso 2, ronda 1 (evaluación con verdad): evaluación del caso de ajuste con verdad con el commit de arranque (B0) y con el candidato, celda por celda. Umbrales 7, 9 y 10: 0 «cumple» sin fundamento, 0 contradicciones, tres salidas, exactitud por celda sin llegar a 6 filas en contra con 0 a favor ni a 8 contra 1 | REQ-119, REQ-120, REQ-125 | T-276, T-283 | pendiente |
| T-285 | Ajuste único del paso 2: todos los hallazgos de T-283 y T-284 en una sola tarea, un commit por hallazgo, corregidos como definiciones y nunca como ejemplos de un caso; se cierra sin cambios si T-283 y T-284 cumplen todo | REQ-119, REQ-120 | T-284 | terminada |
| T-286 | Re-medición del paso 2, ronda 2: solo lo que cambió T-285 (más el caso-00 completo, para el tiempo y la comparación con T-307); es la referencia local simplificada de los pasos 3 y 4. Mismos umbrales que T-283 y T-284 | REQ-119, REQ-120, REQ-125 | T-285 | terminada |
| T-287 | Cierre de los pasos 1 y 2: ADR-0071 (resultado: instrucciones y reglas simples que quedan locales) con las cifras como evidencia, registro del paso y pull request `016-integracion` → `main` | REQ-125 | T-276, T-286 | terminada |
| T-288 | Esquema y configuración del uso externo: tipo de hecho `external_request` y su migración (la única de la feature), variables `EXTERNAL_*` apagadas por omisión con la tabla de precios versionada, pasaje al compose base y `.env.example`. Umbral 20 (parte): con los valores por omisión nada cambia | REQ-122 | T-270, T-282 | terminada |
| T-289 | Cliente de la API externa, su doble y la salida a internet: `evaluon/ai/external/client.py` (mensajes directos y lotes, host fijo, `ExternalDisabled`), `ExternalPayload`, `FakeExternal` y el fixture que impide toda llamada real, `docker-compose.externo.yml`, `test_no_outbound` y `test_network` ajustados | REQ-122 | T-288 | terminada |
| T-290 | Puerta de filtrado, libro de gasto y registro: `guard.py` (lista permitida, exclusiones, huellas), `ledger.py` (hecho por pedido, tope por caso y por mes, reuso por huella, freno al doble) y `gasto_externo` con `--verificar-filtro`; hoja de compliance inventada para las pruebas. Umbral 19 y 21 con el doble: 0 pedidos con texto de la hoja; el lote que pasa el tope no sale | REQ-121, REQ-122 | T-289 | terminada |
| T-291 | Matriz con modelo externo: `matriz-externa-v1`, `proposal/external.py` con el contrato de la etapa local, enchufe en `run.py` con vuelta a lo local si falla, clave `externo` en el registro de la propuesta y `medir_matriz --externo matriz`; probada con el doble y el caso chico | REQ-122, REQ-123 | T-290, T-280 | terminada |
| T-292 | Prueba de humo con el proveedor real (caso chico): matriz externa en modo directo con la hoja de compliance inventada cargada; registro completo, `gasto_externo --verificar-filtro` en 0 y gasto ≤ 0,10 USD | REQ-121, REQ-122, REQ-123 | T-291 | terminada |
| T-293 | Medición del paso 3, ronda 1 (ajuste): propuesta externa de 00, 01, 02 y 06 contra la local simplificada de T-286. Umbral 16 (puerta): lista presente y firmes con pareja no peores en cada caso y 0 pedazos; gasto ≈ 1,20 USD | REQ-123, REQ-125 | T-292, T-286 | pendiente |
| T-294 | Ajuste único de la matriz externa (`matriz-externa-v2` y parámetros) con todos los hallazgos de T-293; se cierra sin cambios si T-293 cumple todo | REQ-123 | T-293 | pendiente |
| T-295 | Re-medición del paso 3, ronda 2 (ajuste): lo que cambió T-294. Mismo umbral 16; si no lo pasa, el externo no pasa a aceptación y queda local | REQ-123, REQ-125 | T-294 | pendiente |
| T-296 | Medición final del paso 3 (aceptación, una sola corrida): matriz local simplificada y externa de 03, 04 y 05, mismo commit y listas congeladas. Umbrales 13 a 15: el externo sube al menos 5 puntos en lista presente en al menos 2 de 3 sin bajar en ninguno, firmes con pareja no bajan, 0 pedazos; si no, queda local. Se cierra sin correr si T-295 no pasó la puerta | REQ-123, REQ-125 | T-295 | pendiente |
| T-297 | Segunda comparación con `claude-opus-5-5`, solo si Sonnet no pasó el umbral 13 o 14 y la etapa pasó la puerta 16: misma instrucción, solo la etapa que falló, una vez; se cierra sin correr si no corresponde | REQ-123 | T-296 | pendiente |
| T-298 | Cierre del paso 3: ADR-0072 (matriz: local o externa, y por qué) con las cifras, gasto real por etapa, registro del paso y pull request `016-integracion` → `main` | REQ-125 | T-296, T-297, T-287 | pendiente |
| T-299 | Verificador externo de citas: `verifier.py`, `verificador-v1`, enchufe en `evaluate_offer` después del contraste y de las reglas y antes de la pregunta, solo sobre «cumple» o «no cumple» con cita, nunca de «no determinado» a «cumple», clave `externo` y `facts["verificador"]`, y la pasada sobre una evaluación guardada para medir; probado con el doble y el caso chico | REQ-121, REQ-122, REQ-124 | T-290, T-291, T-277 | terminada |
| T-300 | Línea «Etapas fuera del equipo» en la pantalla de la evaluación y en su exportación, leída de la clave `externo` de la corrida (o «Ninguna: todo corrió en el equipo»). Umbral 20 (parte): la pantalla y la exportación la muestran | REQ-122 | T-288 | en verificación |
| T-301 | Medición del paso 4, ronda 1 (ajuste, sin GPU): humo del verificador con el caso chico y después el verificador sobre las evaluaciones guardadas de T-286 del caso-00 y del caso de ajuste con verdad. Umbral 17 como puerta: 0 «cumple» sin fundamento, preguntas conformes 100 %, exactas no bajan, erradas no suben, todo «no determinado» nuevo viene de una celda errada; gasto ≈ 0,60 USD | REQ-124, REQ-125 | T-299, T-298, T-287 | pendiente |
| T-302 | Ajuste único del verificador (`verificador-v2` y parámetros) con todos los hallazgos de T-301; se cierra sin cambios si cumple todo | REQ-124 | T-301 | pendiente |
| T-303 | Re-medición del paso 4, ronda 2 (ajuste, sin GPU): lo que cambió T-302. Mismo umbral 17 como puerta | REQ-124, REQ-125 | T-302 | pendiente |
| T-304 | Medición final del paso 4 (aceptación, una sola corrida): evaluación local de los casos de aceptación con verdad y verificador una vez; el «sin» sale de `antes` y el «con» de `después`. Umbrales 17 a 21: 0 «cumple» sin fundamento, preguntas conformes 100 %, exactas no bajan, «no determinado» nuevo solo de erradas, 0 pedidos con texto de la hoja, gasto ≤ 2 USD por caso y ≤ 10 USD por mes; si empata, queda sin verificador | REQ-121, REQ-122, REQ-124, REQ-125 | T-303, T-297, T-276 | pendiente |
| T-305 | Segunda comparación del verificador con `claude-opus-5-5`, solo si Sonnet no pasó el umbral 17 y la etapa pasó la puerta de ajuste: misma instrucción, una vez, sobre las mismas evaluaciones guardadas; se cierra sin correr si no corresponde | REQ-124 | T-304 | pendiente |
| T-306 | Cierre del paso 4: ADR-0073 (verificador: con o sin, y por qué) con las cifras, gasto real por etapa, registro del paso y pull request `016-integracion` → `main` | REQ-125 | T-304, T-305 | pendiente |
| T-307 | Verificación transversal con el uso externo apagado y encendido: suite completa sobre la combinación; caso-00 completo con el uso externo apagado, mismas celdas que la corrida final del paso 2 (0 diferencias) y dentro de los tiempos; `gasto_externo --verificar-filtro` sobre todo el registro (0) y el gasto total de la feature contra los topes; 100 % de los pedidos con sus campos. Umbrales 19 a 21 | REQ-121, REQ-122, REQ-125 | T-306, T-300 | pendiente |

## Paralelismo y cola de GPU

- **Primer lote, en paralelo:** T-270, T-271 y T-278 no comparten archivos (compose, `tools/` y `.env.example`; el cargador de la verdad y los datos del caso chico; las pruebas de instrucciones y el informe). T-277 puede ir a la vez que T-270 y T-278 una vez que T-271 terminó (comparten `evaluation.py` y `medir_evaluacion.py` con T-271).
- **Datos del paso 1:** T-273, T-274 y T-275 van a la vez, un agente por caso (carpetas distintas del corpus), cuando T-272 terminó. Ninguna toca código.
- **Cadena de `settings.py`, de los compose y de la huella de instrucciones (nunca en paralelo):** T-277 → T-279 → T-280 → T-281 → T-282 → T-288 → T-291 → T-299 → T-285 → T-294 → T-302. Cada tarea toca su propio bloque, pero la integran de a una. Los compose los tocan T-270 y T-288 (variables al compose base) y T-289 (`docker-compose.externo.yml`, archivo nuevo): encadenados T-270 → T-288 → T-289. **Esquema:** T-288 es la única tarea que genera una migración.
- **Desarrollo mientras la GPU y los datos esperan:** T-288 a T-291, T-299 y T-300 no dependen de la verdad ni de las mediciones; avanzan mientras corren T-283 y T-284, porque cada medición corre sobre una copia fija del commit (`git archive`), nombrada en el informe. T-300 va a la vez que T-289 a T-299 (toca solo vistas, plantilla y exportación; lee la clave `externo` fijada en el plan, «Modelo de datos»).
- **Las tareas de ajuste (T-285, T-294, T-302) dependen solo de su medición** (corrección del Coordinador, 2026-10-15: el orden de pasos de la spec manda; el paso 2 no espera al desarrollo del paso 4). Si un ajuste y una tarea de desarrollo tocan `settings.py` a la vez, se integran de a una en `016-integracion` y la segunda resuelve el conflicto antes de cerrar, como en toda integración (CLAUDE.md, «Trabajo en paralelo»). T-307 verifica al final que, con el uso externo apagado, el caso-00 da las mismas celdas que la corrida final del paso 2.
- **Cola de GPU, encadenada en la columna «Depende de»:** T-283 → T-284 → T-286 (paso 2); T-292 (humo, minutos) → T-293 → T-295 → T-296 → T-297 (parte local del paso 3); T-304 (evaluación local de aceptación); T-307 (caso-00 completo). T-272 (lectura de ofertas, 1 a 2 h) usa la GPU: el Coordinador la programa en su propia ventana, sin encadenarla para no retrasar a T-283 si los datos tardan. T-285, T-294, T-301 a T-303 y T-305 no usan la GPU.
- **Ventanas:** cada medición con GPU detiene el motor de lotes y el `worker` de 8000 (cola vacía, de noche o fin de semana) con `scripts/clon.sh` y vuelve a arrancar y a comprobar 8000 al terminar. Estimado de GPU: T-283 de 4 a 6 h; T-284 de 2 a 4 h; T-286 de 2 a 5 h según lo que cambie; T-293 y T-295 0,75 h cada una; T-296 unas 3 h; T-304 de 2 a 4 h; T-307 unas 2 h.
- **Gasto externo (plan, «Costo y tope»):** T-292 ≤ 0,10 USD; T-293 y T-295 ≈ 1,20 USD cada una (hasta 2,40 y 3,20 en total con el caso-01); T-296 ≈ 0,90; T-301 y T-303 ≈ 0,60 cada una; T-304 ≈ 0,60 a 0,90; las segundas comparaciones, solo si corresponde, hasta 3,90 en total. Cada informe pega la salida de `gasto_externo`.
- **Máximo sugerido en paralelo:** dos o tres desarrolladores (el Coordinador debe poder revisar cada resultado contra la spec).

## Suites completas por lote (ADR-0012)

| Fecha | Lote | Commit de `016-integracion` | Resultado |
|---|---|---|---|
| 2026-10-15 12:23 | 1: T-270, T-271, T-278 | e5724b1d | 6187 pasaron, 1 omitida, 0 fallaron (22 min 46 s, `-n 2`, con `corpus/casos` montado) |
| 2026-10-15 22:54 | 2: T-277, T-279, T-280, T-281, T-282 | e489985f | 6418 pasaron, 1 omitida, 0 fallaron (25 min 21 s, `-n 2`, con `corpus/casos` montado) |
| 2026-10-16 07:08 | 3: T-285, T-288, T-289, T-290, T-300 | c93b33bd | 6760 pasaron, 1 omitida, 0 fallaron (25 min 31 s, `-n 2`, con `corpus/casos` y los compose del clon montados) |
| 2026-10-16 16:06 | 4 (cierre del paso 2, T-287): T-291, T-299, T-286, T-292 combinados con `main` 595c503d | 202f473c | 6843 pasaron, 1 omitida, 0 fallaron (27 min 0 s, `-n 2`, con `corpus/casos`, los compose del clon y `tools/` montados) |

## Lista de revisión (hallazgos que no impiden integrar; se corrigen en una sola tarea por lote, ADR-0025)

| Clave | De | Qué | Dónde se corrige | Estado |
|---|---|---|---|---|
| D-278-1, D-278-2, D-278-3 | T-278 (verificación, pasa) | Huecos de cobertura de las pruebas de instrucciones: nada fija las 6 palabras; no se detecta quitar el paso a minúsculas, leer solo parte del corpus ni medir sin el bloque de definiciones; una sección sin filas del informe no tiene prueba | T-279 (toca los mismos archivos) | abierto |
| D-270-1 | T-270 (verificación, pasa con la ventana real pendiente) | `clon_app` y `clon_worker` alcanzan por nombre a `db`, `generation_batch` y `app` de 8000 en `evaluon_internal`; `entorno.md` dice lo contrario (sin daño hoy: contraseñas distintas y ninguna variable apunta ahí) | T-288 (toca los compose) o la tarea de la ventana real | cerrado el 2026-10-16: `entorno.md` ya dice que la red `evaluon_internal` es compartida y se alcanza por nombre, y T-292 usa el motor de 8000 por nombre a propósito |
| D-270-2 | T-270 | **Resuelto en la ventana real del 2026-10-15:** `nvidia-smi` fallaba solo para el motor de 8000 arrancado antes del reinicio; con el motor reiniciado informa 18.458 MiB. La medida del umbral 11 vale si el motor se arrancó después del último reinicio | Cerrado (anexo de `verificacion/T-270.md` en `016-integracion`) | cerrado (T-270) |
| D-270-3 | T-270 | `restaurar` no tiene test de la condición `--forzar` | T-288 · 2026-10-16: no entró en T-288 (sigue sin test de `restaurar` con `--forzar`); pasa al primer producto | abierto |
| D-271-1 a D-271-4 | T-271 (verificación, pasa) | D-271-1: `cargar_oferta` guarda el nombre sin carpeta, así que la verdad nombra los documentos sin carpeta y únicos por oferta (condición para T-273 a T-275; dos archivos con el mismo nombre en carpetas distintas chocan). D-271-2: el «cumple» por ausencia no exige nombrar todos los documentos de la oferta (sugerencia: informar «N de M»). D-271-3: dos alteraciones sin test (nombre base no único; informe que imprima citas). D-271-4: `armada_por` no se exige | T-273 a T-275 (nombres); T-276 (la revisión controla la cobertura de la ausencia); los tests, en la tarea de ajuste del paso 2 (T-285) · 2026-10-16: D-271-3 y D-271-4 no entraron en T-285; pasan a T-276 (cierre del paso 1, con la verdad nueva) | abierto |
| H-277-1 a H-277-5 | T-277 (verificación, pasa sobre 699da5c4) | H-277-1: `--recalcular` de corridas viejas no calcula las tres salidas ni lo dice. H-277-2: cuatro alteraciones sin test (pregunta fija de `no_cumple_sin_clausula`, dato del Portal en `portal_cubre_parte`, primera fila de `thresholds_016`). H-277-3: «no aplica» se guarda como «cumple» con `aplica = False` (informativo; el plan lo describe como forma de «no determinado»). H-277-4: cada «no determinado» abre una pregunta y la etapa queda «lista» solo con 0 abiertas: tenerlo presente para el piloto y T-284. H-277-5: aserción negativa residual en `test_tres_salidas.py` | T-285 (tests y aviso de `--recalcular`); H-277-3 y H-277-4 al cierre del paso 2 (ADR-0071) · 2026-10-16: H-277-3 (forma guardada de «no aplica») queda como está, documentada en ADR-0070 punto 5, y se mira en la auditoría; H-277-4 (cada «no determinado» abre una pregunta) se absorbe en D-286-3 (primer producto) | abierto |
| H-279-1 a H-279-7 | T-279 (verificación, pasa) | H-279-1 (media): la cláusula de la garantía de cumplimiento de contrato en el bloque v9 no la sostiene D-01 literal (definición derivada, pendiente de confirmación del responsable: D-32). H-279-2 (media): «la duda va a sugerencia» solo aplica al filtro. H-279-3: tres citas a decisiones que no las sostienen. H-279-4: tres bordes de «ejemplo». H-279-5: ninguna prueba exige una fila por oración ni liga el esqueleto con `build_schema`. H-279-6: la clase de la sección repite `_category`. H-279-7: una prueba de opciones ya no puede fallar | T-280 (H-279-1, 2, 3 y 5); H-279-4, 6 y 7 en T-285 · 2026-10-16: H-279-4, 6 y 7 no entraron en T-285 (baja); pasan al primer producto junto con D-286 | abierto |
| H-280-1 a H-280-6 | T-280 (verificación, pasa) | H-280-1 (media): dos reglas sin decisión literal nacidas de mediciones de la 015 (alcance por la ruta; «no elegís una ajena porque se parece»): pasan a definiciones derivadas D-35 y D-36 pendientes de confirmación. H-280-2: citas incompletas. H-280-3: la oración «duda va a sugerencia» del bloque v9 (congelado) la leen etapas sin ese destino. H-280-4: cuatro huecos de cobertura. H-280-5: las circulares omiten parte de D-01 por el tope. H-280-6: la v10 ya no manda las excepciones a `condicion_opcional` (venía de T-240, sin decisión literal) | T-281 (H-280-1, 2 y 4a/4d); el resto se mide en T-283 y, si pesa, T-285. Las definiciones derivadas D-33 a D-36 se presentan al responsable en una tabla de sí o no antes de T-283 | abierto |
| H-281-1 a H-281-4 | T-281 (verificación, pasa con reparos) | H-281-1 (media): «con otras palabras equivalentes, alcanza» (contraste) citaba D-08 que no la sostiene; con la regla de tabla/listado y la forma de la reescritura pasan a derivadas D-43 a D-45 pendientes de confirmación. H-281-2: lo externo nombra tres tipos, REQ-063 cuatro. H-281-3: el test del tope de razonamiento admite 100 caracteres de deriva. H-281-4: quitar el rótulo de una derivada no falla ningún test | T-282 (H-281-1, 3 y 4); H-281-2 se mide en T-283 | abierto |
| H-282-1 a H-282-3 | T-282 (verificación, pasa con reparos) | H-282-1 (media, resuelto en 3179f0b4): seis reglas de contenido sin decisión literal pasan a derivadas D-55 a D-60 pendientes de confirmación. H-282-2: las dos líneas de registro de la consulta se cubren entre sí. H-282-3: la forma del registro P6 difiere entre puntos de llamada (cumple en sustancia). `consulta-v1` queda fuera de `SIMPLIFIED` (camino sin fecha que la aplicación no usa) | D-55 a D-60 al responsable con D-33 a D-45; H-282-2 y 3 en T-285 si pesa | abierto |
| O-288-1 a O-288-5 | T-288 (verificación, pasa) | O-288-1: pensamiento de la matriz `adaptive`, a confirmar con la medición. O-288-2: se aceptan tope negativo, NaN e intervalo 0 (T-290 los rechaza). O-288-3: una etapa en `externo` con el interruptor apagado carga sin error (T-289 decide con ambos). O-288-4: `portal_worker` recibe las variables (T-289 impide importar el cliente desde el Portal). O-288-5: ninguna prueba obliga a subir la versión de la tabla de precios al cambiar un precio | T-289 y T-290 | abierto |
| O-300-1 y contrato de la clave `externo` | T-300 (verificación liviana, cumple; falta la lectura de la pantalla por el Coordinador) | O-300-1: `external_stages.line` falla si `proveedor` o `modo` llegan como lista (arreglo de una línea). Contrato: `models_used["externo"]` con `etapas`, `proveedor`, `modelo`; `parameters["externo"]["modo"]`; `counts["externo"]["pedidos"]`, con entrada propia por etapa (obligatoria si hay dos etapas externas). La línea lee solo `assessment_run`: la etapa externa de la matriz (T-291, `tenders_run`) necesita su propia línea en la pantalla y la exportación de la matriz | T-291 (línea de la matriz y O-300-1) y T-299 (clave por etapa); T-307 comprueba pedidos contra hechos `external_request` | abierto |
| H-289-1, H-289-2, O-289-1 a O-289-6 | T-289 (verificación: no pasa por pruebas; reverificación de 5f8bad29: pasa) | H-289-1 y 2 (huecos de pruebas del anfitrión fijo y de la clave) y O-289-1 a 3 (tapar la clave en errores, cancelar el lote ante cualquier falla, acotar Retry-After) corregidos. Quedan: O-289-4 (`dataclasses.replace` o `copy` saltean la puerta: lo cierra T-290), O-289-5 (`MAX_RETRIES` sin fijar) y `on_created` fuera del `try` de `run_batch` (quien lo pase captura sus errores) | T-290 (O-289-4); T-291/T-292 (`on_created`) | abierto |
| D-283-1 a D-283-9 | T-283 (medición del paso 2, ronda 1: no pasa; umbrales 9 y 11 cumplen, 7, 8, 10 y 12 no) | Matriz: la presentación física descartada como forma de presentar por el Portal (D-283-1), la condición de una opción descartada (D-283-2), sobrantes de anexos y notas (D-283-3), dos entradas (D-283-4). Evaluación del caso-00: 30→21 exactas, 1 contradicción con el dictamen (D-283-5), 9 exactas que pasan a no determinado por conversiones del código, la regla del Portal y la ausencia que no corre (D-283-6), preguntas no conformes (D-283-7). Consulta v5 se abstiene de más y REQ-021 54/56 (D-283-8). Visión v5 omite la fecha del DNI (D-283-9) | T-285 (ajuste único) y T-286 (remedición, última ronda). Decisión del responsable (P7) si T-286 no recupera la Consulta: vuelve consulta-v4 | abierto |
| H-290-1 a H-290-6, O-290-1 a O-290-10 | T-290 (verificación: dos rondas de corrección; final: pasa) | Fugas corregidas: huellas por mensaje, caracteres invisibles, sugerencia de compliance pendiente (enmienda del ADR-0067), ocho controles sin prueba, precios validados tarde, invisibles como separador. Quedan como límites del cotejo exacto (no bloquean): 7 palabras seguidas, cirílico, corte con guion, invisibles en las dos formas en un mismo párrafo (O-290-10); la puerta compara solo con las hojas del procedimiento (O-290-5); `--verificar-filtro` sin opciones mira el mes en curso (usar `--procedimiento N`); `dictamen` bloqueado (O-290-1). Residual: `_record_in_flight` dentro de `on_created` (T-291) | T-291 y T-299 (origen declarado, `on_created`); auditoría completa (límites del cotejo) | abierto |
| H-285-1 a H-285-7, O-285-7, O-285-8 | T-285 (verificación: no pasa; reverificación de 9f45ae49: pasa) | Corregidos: «no aplica» solo desde la `opcion` de la fila (H-285-1), causas reales de las citas no ubicadas y repetidas (H-285-2), la ausencia no corre ante un dato negativo parafraseado (H-285-3), preguntas (H-285-5), derivadas D-65 a D-67 (H-285-6), tests (H-285-7). Límite: una condición con cita ubicada y `no_consta` frena la ausencia (H-285-4). O-285-7: `marked_rule` reemplaza la pregunta específica de la fila. O-285-8: dos citas de O1 siguen sin ubicarse (letra cambiada por el OCR; frase completada de memoria). **Decisión del Coordinador para T-286:** la versión 3 del caso-00 se rearma con `opcion = mipyme` en las filas de la opción MiPyME (versión 3b, documentada en el registro), porque una matriz propuesta las traería así | T-286 (3b); O-285-7 en T-299 o el cierre del paso 2 | abierto |
| H-291-1, O-291-1 a O-291-13 | T-291 (verificación: no pasa por pruebas; reverificación de 893d8e63: pasa) | H-291-1 (cinco controles sin prueba) corregido; el freno de etapa conserva las respuestas pagadas si llega tras el último pedido (O-291-1); `medir_matriz --medicion` reutiliza respuestas a costo 0 (O-291-3). Abiertos: O-291-12 (con 3 o 4 pedidos de extracción el freno de 0,60 USD puede saltar antes de la completitud y perder lo pagado: revisar el estimado de 0,30 USD con la prueba de humo T-292), O-291-13 (`--medicion` sin `--externo` se ignora), la línea dice «Ninguna» aunque se hayan pagado pedidos antes de volver a local, el razonamiento va último y vacío en filas firmes | T-292 (estimado); T-293; cierre del paso 3 | abierto |
| H-299-1, H-299-2, O-299-1 a O-299-9 | T-299 (verificación: no pasa; reverificación de da3d49d7: pasa) | Corregidos: la segunda pasada de `--verificador-sobre` mide la pregunta de la celda cambiada (H-299-1), 17 controles con prueba (H-299-2), la pregunta nombra al verificador (O-299-1), razonamiento ≤ 400 (O-299-4). Abiertos: O-299-2 (la línea dice «Ninguna» si la etapa volvió a local tras pagar pedidos; igual que O-291-4: decidir antes de T-307), O-299-6 (una derivada reabre una pregunta respondida del origen; solo en el clon), O-299-5 (una oferta con la hoja de compliance en el grupo de todas sus celdas no manda ninguna: falla cerrada) | Cierre del paso 4 (ADR-0073); T-307 | abierto |
| D-286-1 a D-286-8 | T-286 (medición del paso 2, ronda 2 y última: 7 con reparo, 9, 10 y 11 cumplen; 8 y 12 no) | D-286-1 (alta): la presentación física queda como sugerencia (00, 02, 06) o descartada (01): lista presente a 1 de la referencia en los 4 casos. D-286-2: M-007 del 00 baja a sugerencia. D-286-3: 7 celdas exactas en T-263 siguen en pregunta; «no determinado» 33,3 % (T-263 25,4 %; meta 15 %), con 0 erradas (T-263: 1). D-286-4: O1 R62 «cumple» con fundamento débil (cita del Portal que no dice el plazo). D-286-5: `consulta-v6` se abstiene en EV-010 y EV-012 (15/17 por corrector, 16/17 por lectura; REQ-021 56/56 recuperado). D-286-6: visión DNI 15/18 (falta la fecha de vencimiento), pagaré 10 u 11/18. D-286-7 y 8: preguntas de R87 y REQ-031 del 06 en 0 de 3 | **Decidido el 2026-10-16 (ADR-0071):** el paso 2 cierra con las instrucciones cortas; D-286-1 a 8 quedan para el primer producto, en una sola tarea por lote con una medición | abierto (primer producto, ADR-0071) |
| O-292-1 a O-292-8 | T-292 (prueba de humo con el proveedor real: pasa; 2 pedidos, 0,0597 USD, 0 pedidos con texto de la hoja, 100 % registrados; red, clave inválida y tope se comportan) | O-292-1: `EXTERNAL_CASE_CAP_USD=0` aborta la propuesta (`ImproperlyConfigured`, O-288-2) en vez de volver a local; con tope positivo mínimo sí bloquea por `tope`. O-292-2: 0 aciertos de caché entre los 2 pedidos (texto de sistema idéntico; hipótesis: esquemas de salida distintos cambian el prefijo); la escritura de caché fue el 82 % del gasto. O-292-3: el estimado de 0,30 USD (O-291-12) vale solo si la caché acierta (0,12–0,32 USD por pliego de 30–70 k tokens); sin aciertos 0,23–0,85 y el freno de 0,60 se pasa en pliegos grandes. O-292-4: `clon_app` sí tiene ruta a internet por `clon_web` (diseño documentado; barrera por código). O-292-5: no se probó el modo de lotes ni el verificador; el filtro solo vio texto del pliego. O-292-6: el libro suma por base. O-292-7: `gasto_externo --por-etapa` no separa por medición. O-292-8: el hecho del 401 deja `duracion_s` y `modelo_respuesta` vacíos | Antes de T-293 mirar `lectura_cache` en los primeros pedidos de extracción; si es 0, decidir caché y estimado (O-292-2/3). O-292-1: decidir si tope en 0 vuelve a local (runbook) · Lectura del Coordinador (2026-10-16, sin gasto): el esquema de salida va en `output_config.format` y es el mismo entre los pedidos de extracción de un caso (depende solo de los números técnicos) y distinto en completitud, así que se esperan aciertos de caché desde el 2.º pedido de extracción; T-293 lo comprueba en su primer caso | abierto |
| Ventana real | T-270 | **Hecha el 2026-10-15 (19:28 a 19:37):** apertura en 5 min, pedido al 27B del clon en 3,8 s, cierre con las 7 comprobaciones de 8000 en OK en 3 min. Anexo en `verificacion/T-270.md` | Cerrado | cerrado (T-283) |

## Detalle

### T-270 · Entorno del clon

- **Requisitos:** REQ-125
- **Nivel de verificación:** plena (configuración compartida y entorno de las mediciones).
- **Qué hay que hacer:**
  1. `docker-compose.clon.yml` y `scripts/clon.sh` a la manera de `docker-compose.demo.yml` y `scripts/demo.sh`: proyecto `evaluon-016`, servicios `clon_db`, `clon_migrate`, `clon_app`, `clon_worker` y `clon_generation_batch` (27B con `docker-compose.qwen38-27b.yml` y `docker-compose.razonamiento.yml`; razonamiento `low` solo en el contraste), volumen `clon_pgdata`, puerto 8016 solo en `127.0.0.1`, `embeddings` y `reranker` de 8000 por `evaluon_internal`, código de la copia de trabajo de `016-integracion`, secretos en un `--env-file` fuera del repositorio.
  2. `scripts/clon.sh`: `subir`, `restaurar` (respaldo nuevo de 8000 con el procedimiento del runbook y `pg_restore` en `clon_db`), `ventana-abrir` (detiene `generation_batch` y `worker` de 8000, comprueba la GPU y la cola vacía, arranca `clon_generation_batch`), `ventana-cerrar` (baja el motor del clon, arranca y comprueba 8000: `/health`, `/props`, cola vacía, `/ingresar/` 200), `bajar` y `estado`.
  3. `tools/cerrar.sh`: variable `BASE` (por omisión `main`, comportamiento actual intacto); con `BASE=016-integracion` integra en esa rama.
  4. `.env.example`: líneas comentadas del clon. `specs/016-calidad-medible/entorno.md`: cómo se levanta, se restaura, se abre y cierra una ventana, se mide sobre una copia fija (`git archive`) y se vuelve atrás.
  5. El Coordinador crea la rama `016-integracion` desde `main` y su copia de trabajo antes de lanzar esta tarea.
- **Archivos:** `docker-compose.clon.yml`, `scripts/clon.sh`, `.env.example`, `tools/cerrar.sh`, `specs/016-calidad-medible/entorno.md`, `tests/test_clon_compose.py` (nuevo; lee los archivos de la raíz y se salta si no están montados, como `test_instrucciones_revisadas.py`).
- **Verificación:** `docker compose -p evaluon-016 -f docker-compose.clon.yml config` sin errores; `restaurar` deja la base del clon con los mismos conteos de tablas que el respaldo; `clon_app` responde `/ingresar/` 200 en 8016; los contenedores y volúmenes `evaluon-*` de 8000 no cambian (se compara la lista y las huellas de imagen antes y después); `ventana-abrir` y `ventana-cerrar` dejan a 8000 sano; `BASE=main tools/cerrar.sh` sigue funcionando igual (prueba en seco).
- **No tocar:** `docker-compose.yml` y los compose existentes, `evaluon/`, la base de 8000 (solo se la respalda), ningún contenedor de 8000 fuera de la ventana.

### T-271 · Formato de la verdad y su cargador

- **Requisitos:** REQ-118
- **Nivel de verificación:** plena (datos y medida).
- **Qué hay que hacer:**
  1. Extender el cargador de `evaluation.py` (que hoy lee `celdas-comision-*.yaml`) con el formato `verdad-celdas.yaml` del plan, «Paso 1» y ADR-0069: `procedimiento`, `caso`, `lote` (`ajuste` o `aceptacion`), `huella`, `armada_por`, `visto_bueno`, y por celda `oferta`, `requisito` (`M-NNN`, traducido a la fila de la matriz armada con `build_case`), `resultado` (agrega `no_determinado`), `fundamento` (`tipo`, documento, página, texto, nota), `pregunta` y `revision` (`por`, `fecha`, `estado`). El archivo `celdas-comision-*.yaml` de hoy sigue cargando sin cambios.
  2. `medir_evaluacion --verificar-verdad`: por caso y en total, cantidad de celdas decididas (cumple, no cumple, no aplica, no se encontró el documento), celdas con revisión (quién y cuándo), citas ubicadas en la lectura de la oferta (`quotes.locate`) o ítem del Portal, «no determinado» con pregunta o documento nombrado, `congelado-016.txt` coincidente en los de aceptación y 0 corridas de evaluación guardadas del procedimiento. Una celda sin revisión no se cuenta.
  3. `--celdas-comision` acepta el archivo de verdad; `cell_accuracy` trata «no determinado» contra «no determinado» como exacta.
  4. La verdad del caso chico (público e inventado) en el repositorio, con 3 requisitos, para el corte vertical.
- **Umbral:** el caso chico da los conteos esperados; una cita que no está palabra por palabra en la lectura se rechaza; una celda sin revisión no cuenta; un caso de aceptación con una corrida guardada se señala.
- **Archivos:** `evaluon/assessment/evaluation.py`, `evaluon/assessment/management/commands/medir_evaluacion.py`, `tests/assessment/data/caso-chico/verdad-celdas.yaml`, `tests/assessment/test_verdad.py` (nuevo).
- **Verificación:** `docker compose run --rm app pytest tests/assessment/test_verdad.py tests/assessment/test_evaluation.py`; `manage.py medir_evaluacion --caso-chico --verificar-verdad`; la suite del área.
- **No tocar:** el flujo de evaluación, las instrucciones, `settings.py` y los archivos de verdad de los casos reales (fuera de git).

### T-272 · Cargar los 3 procesos de la verdad

- **Requisitos:** REQ-118
- **Nivel de verificación:** plena (datos).
- **No arranca sin:** que el responsable aporte, o autorice bajar del Portal, las ofertas y el dictamen de 3 procesos públicos terminados, con al menos 2 ofertas legibles cada uno y suficientes requisitos para 40 celdas decididas; T-270 y T-271 integradas. Si el proceso es uno de los casos 01 a 06, usa su lista esperada y su lectura vigentes (preferir 03, 04 y 05 para aceptación); si es otro, se le arma la lista esperada con el mismo método (huella y visto bueno del Coordinador).
- **Qué hay que hacer:** poner los documentos en `corpus/casos/` (fuera de git); cargarlos en el clon con `cargar_oferta` y el importador del Portal (acta, cuadro comparativo, dictamen); `releer_pliego` si hace falta; fijar el lote de cada caso (1 de ajuste, 2 de aceptación); hasta 3 ofertas por caso; comprobar que las ofertas se leyeron (páginas dudosas con visión del 27B) y que **ninguna evaluación corrió**.
- **Archivos:** solo `corpus/casos/` (fuera de git) y `specs/016-calidad-medible/verificacion/T-272.md` (cifras: casos, ofertas, páginas leídas, páginas con visión, corridas de evaluación = 0).
- **Verificación:** `medir_evaluacion --verificar-esperada` de cada caso; consulta a las corridas del clon (0 de evaluación en los de aceptación).
- **No tocar:** código, instrucciones, la base de 8000.
- **GPU:** de 1 a 2 h para la lectura con visión; ventana propia.

### T-273, T-274 y T-275 · Verdad celda por celda de cada caso

- **Requisitos:** REQ-118
- **Nivel de verificación:** plena (datos). T-273 es el caso de ajuste; T-274 y T-275 son los de aceptación.
- **Qué hay que hacer:** un agente por caso rehace la evaluación como la Comisión (ADR-0069): con el pliego y sus circulares, la lista de requisitos, la lectura de cada oferta, los datos del Portal y el dictamen publicado, **sin ver ninguna corrida, propuesta ni evaluación del sistema**. Decide cada celda decidible (hasta 3 ofertas y de 40 a 120 celdas decididas por caso) con su fundamento: cita literal de la oferta con documento y página, ítem del Portal, ausencia con los documentos leídos, o la pregunta o el documento que falta si es «no determinado». Las filas técnicas sin informe y los requisitos externos sin hoja quedan «no determinado» con su motivo.
- **Archivos:** `corpus/casos/<caso>/esperado/verdad-celdas.yaml` (fuera de git; sin visto bueno todavía) y `specs/016-calidad-medible/verificacion/T-NNN.md` (solo cifras).
- **Verificación:** `medir_evaluacion --verificar-verdad` del caso: al menos 40 celdas decididas, 100 % de los «cumple» y «no cumple» con cita ubicada o dato del Portal, 100 % de los «no determinado» con pregunta o documento nombrado, 0 corridas de evaluación.
- **No tocar:** código, instrucciones, la base más allá de leer, los archivos de otro caso.

### T-276 · Cierre del paso 1: revisión y firma del responsable

- **Requisitos:** REQ-118, REQ-125
- **Nivel de verificación:** plena (datos y compuerta humana).
- **No arranca sin:** que el responsable tenga tiempo para revisar de 150 a 360 celdas.
- **Qué hay que hacer:** el Coordinador arma por caso el documento de revisión (fuera de git, tabla de ejemplos reales con una pregunta de sí o no por fila, de lo más dudoso a lo más seguro); el responsable confirma o corrige cada celda; en cada una queda `revision` (`por`, `fecha`, `estado`, resultado anterior si la corrigió); el archivo lleva `visto_bueno` y `huella`. Para los casos de aceptación se escribe `congelado-016.txt` (huella de la verdad y de la lista, commit y fecha). Registro del paso con las cifras.
- **Archivos:** `corpus/casos/*/esperado/verdad-celdas.yaml` y `congelado-016.txt` (fuera de git), `specs/016-calidad-medible/verificacion/T-276.md`.
- **Verificación:** `medir_evaluacion --verificar-verdad` en los 3 casos: al menos 3 casos (2 de aceptación), 40 celdas decididas por caso y 150 en total, 100 % con quién y cuándo, congelado coincidente, 0 corridas de evaluación en aceptación. Cumple los umbrales 1 a 4.
- **No tocar:** código; ninguna celda sin revisar del responsable.

### T-277 · Reglas a tres salidas

- **Requisitos:** REQ-120
- **Nivel de verificación:** plena (lógica de decisión, un principio de la constitución).
- **Qué hay que hacer:** según el plan, «Paso 2», y el ADR-0070 (punto 5):
  1. `combine.py`: `done()` conserva la pregunta del modelo para «no se encontró el documento» y el documento exigido queda nombrado; `compose_question` arma una pregunta para todo «no determinado» que no nombre ya un documento faltante (`externo`, `pendiente_informe_tecnico`, `no_se_pudo_leer`), con texto por motivo (`duda`, `contradiccion`, `sin_cita`) en `_default_ask`.
  2. `services/evaluate.py` y `services/questions.py`: inventario de las conversiones (`condicion_sin_cita`, `condicion_sin_dato`, `condicion_no_aplica`, `resultado_derivado`, `resultado_no_sostenido`, `no_cumple_sin_clausula`, `requisito_sin_cita`, `contraste_invalido`, `pedido_fuera_de_contexto`, cláusulas): cada una deja el motivo en la explicación y la pregunta o el documento en la celda.
  3. `rules.py` y `portal_facts.py`: las reglas del Portal que dejan condiciones abiertas (`portal_cubre_parte`, `portal_falta_coincidencia`, `en_portal`, `falta_coincidencia`) deciden «cumple» o «no cumple» con la cita del Portal cuando el dato alcanza, o «no determinado» con la pregunta que nombra la condición y el dato que sí hay. Se conservan la cita literal, el dato del Portal, el cumple por ausencia, el criterio del IVA y la presentación física.
  4. `ASSESSMENT_RULES_VERSION` pasa a `reglas-v13`.
  5. `medir_evaluacion` cuenta las celdas «no se encontró el documento» sin pregunta y los «no determinado» sin pregunta ni documento nombrado.
  6. Los 245 tests `decision_literal` siguen verdes; si uno exigiera cambiar, se frena y se consulta (P1, P11).
- **Umbral 9:** 0 «no se encontró el documento» sin pregunta; 100 % de los «no determinado» con pregunta o documento nombrado, en los casos de prueba y en las combinaciones.
- **Archivos:** `evaluon/assessment/combine.py`, `rules.py`, `portal_facts.py`, `services/evaluate.py`, `services/questions.py`, `evaluation.py`, `management/commands/medir_evaluacion.py`, `evaluon/settings.py` (solo `ASSESSMENT_RULES_VERSION`), `tests/assessment/test_tres_salidas.py` (nuevo) y los tests que cambien de forma.
- **Verificación:** `pytest tests/assessment -m decision_literal`, `pytest tests/assessment`, `medir_evaluacion --verificar-decisiones`; `test_tres_salidas.py` recorre todas las combinaciones de resultados de grupo, contraste y reglas y exige que cada celda cumpla una de las tres formas; alteraciones del código (las dos conversiones de T-263 y T-268 reproducidas); suite completa una vez al final.
- **No tocar:** instrucciones, `prompting.py`, el esquema, las demás líneas de `settings.py`.

### T-278 · Pruebas de las instrucciones y tabla de decisiones

- **Requisitos:** REQ-119
- **Nivel de verificación:** plena (instrucciones al modelo y pruebas).
- **Qué hay que hacer:**
  1. `tests/test_instrucciones_largo.py`: tope por instrucción, con el bloque de definiciones ya incluido: decisoras (extracción, filtro, evaluación, matriz externa) 90 líneas y 9.000 caracteres; las demás 50 y 5.000; bloque de definiciones 5.000; descripción de campo de un esquema 80. Se aplica a las versiones listadas en una tabla `SIMPLIFIED` que cada tarea de instrucciones agranda; T-282 agrega la prueba de que toda instrucción vigente está en la tabla.
  2. `tests/test_instrucciones_sin_casos.py`: ninguna secuencia de 6 palabras seguidas (sin tildes ni mayúsculas) de una instrucción de `SIMPLIFIED` aparece en el cuerpo de los pliegos, circulares, ofertas y dictámenes de los casos 00 a 06 ni del caso chico; sin ejemplos con contenido de licitación. Se salta si `corpus/` no está montado.
  3. `specs/016-calidad-medible/revision-instrucciones.md`: tabla decisión → fuente (spec o ADR) con las decisiones literales del responsable de las specs 003, 004, 014 y 015 y de los ADR 0043, 0053, 0054 y 0058, sin texto de casos; y, por cada instrucción nueva, sus oraciones con la decisión de la que salen (se completa en T-279 a T-282).
  4. `tests/test_instrucciones_revisadas.py`: lee el informe de la 016 y comprueba que toda versión de `SIMPLIFIED` tiene su tabla.
- **Umbral 5 y 6:** las pruebas existen y fallan con una instrucción de 100 líneas y con una oración copiada de un caso inventado.
- **Archivos:** `tests/test_instrucciones_largo.py`, `tests/test_instrucciones_sin_casos.py`, `tests/test_instrucciones_revisadas.py`, `specs/016-calidad-medible/revision-instrucciones.md`.
- **Verificación:** las tres pruebas con una versión de prueba que cumple y otra que no; la suite del área.
- **No tocar:** las instrucciones vigentes, `settings.py`, `tests/fixtures/instrucciones.sha256`.

### T-279 · Instrucciones de la matriz, parte 1

- **Requisitos:** REQ-119
- **Nivel de verificación:** plena (instrucciones al modelo).
- **Qué hay que hacer:** escribir `matriz-definiciones-v9` (≤ 5.000 caracteres), `matriz-extraccion-v13`, `matriz-completitud-v7` y `matriz-union-v2` a partir de la tabla de decisiones de T-278, **sin leer textos de casos**: definiciones y decisiones vigentes en términos generales (las «formas» de T-263 como definiciones del responsable, sin ejemplo), esqueleto de la salida con marcadores, nada que el código ya garantice. Actualizar `MATRIX_PROMPT_VERSIONS`, los cargadores y `OBLIGATION_MARKERS` de `run.py` si hace falta, la huella en `tests/fixtures/instrucciones.sha256` y `SIMPLIFIED`; completar la tabla de decisiones.
- **Archivos:** `evaluon/tenders/prompts/matriz-definiciones-v9.md`, `matriz-extraccion-v13.md`, `matriz-completitud-v7.md`, `matriz-union-v2.md`, `evaluon/settings.py` (`MATRIX_PROMPT_VERSIONS`), `evaluon/tenders/proposal/extraction.py`, `completeness.py`, `joining.py`, `run.py` (solo cargadores y marcadores), `tests/fixtures/instrucciones.sha256`, `specs/016-calidad-medible/revision-instrucciones.md`.
- **Verificación:** `test_instrucciones_largo.py`, `test_instrucciones_sin_casos.py` y `test_instrucciones_revisadas.py` en verde; `pytest tests/tenders`; el caso chico con el doble de generación. La medición es de T-283.
- **No tocar:** filtro, consecuencias, circulares, respaldo, evaluación, las versiones publicadas.

### T-280 · Instrucciones de la matriz, parte 2

- **Requisitos:** REQ-119
- **Nivel de verificación:** plena (instrucciones al modelo).
- **Qué hay que hacer:** `matriz-filtro-v10` (con el bloque común; la duda va a sugerencia), `matriz-consecuencias-v3`, `matriz-circulares-v8`, `matriz-circulares-cambios-v7` y `matriz-respaldo-v3`, con las mismas reglas de T-279; `decide()` y los lotes de `filter.py` se mantienen salvo lo que el cambio de formato exija.
- **Archivos:** `evaluon/tenders/prompts/matriz-filtro-v10.md`, `matriz-consecuencias-v3.md`, `matriz-circulares-v8.md`, `matriz-circulares-cambios-v7.md` (cambios; el vigente de cambios es `matriz-circulares-v6.md` y el de circulares `matriz-circulares-v7.md`, congelados: O-278-2) y `matriz-respaldo-v3.md` según corresponda a las versiones vigentes, `evaluon/settings.py` (`MATRIX_PROMPT_VERSIONS`), `evaluon/tenders/proposal/filter.py`, `consequences.py`, `circulars.py`, `circular_changes.py`, `norm_support.py`, `tests/fixtures/instrucciones.sha256`, `specs/016-calidad-medible/revision-instrucciones.md`.
- **Verificación:** las tres pruebas de instrucciones; `pytest tests/tenders`.
- **No tocar:** definiciones, extracción, completitud, unión, evaluación.

### T-281 · Instrucciones de la evaluación

- **Requisitos:** REQ-119
- **Nivel de verificación:** plena (instrucciones al modelo y lógica del pedido).
- **Qué hay que hacer:** `evaluacion-v13`, `contraste-v5`, `clausulas-v6` y `reescritura-v3` con las reglas de T-279; sacar de la instrucción lo que el código ya garantiza (ubicar las citas, derivar el resultado de las condiciones, esquema); `prompting.py`: descripciones del esquema de salida de hasta 80 caracteres y el mismo orden de campos (razonamiento, citas, externo e ilegible, datos, resultado, explicación, pregunta); versiones y huellas.
- **Archivos:** `evaluon/assessment/prompts/evaluacion-v13.md`, `contraste-v5.md`, `clausulas-v6.md`, `evaluon/offers/prompts/reescritura-v3.md`, `evaluon/assessment/prompting.py`, `evaluon/settings.py` (`ASSESSMENT_PROMPT_VERSIONS`, `OFFERS_PROMPT_VERSIONS`), `tests/assessment/test_instrucciones_evaluacion.py`, `tests/fixtures/instrucciones.sha256`, `specs/016-calidad-medible/revision-instrucciones.md`.
- **Verificación:** las tres pruebas de instrucciones; `pytest tests/assessment`; `medir_evaluacion --verificar-decisiones`; el caso chico con el doble.
- **No tocar:** `evaluate.py`, `combine.py`, reglas, instrucciones de la matriz.

### T-282 · Instrucciones auxiliares

- **Requisitos:** REQ-119
- **Nivel de verificación:** plena (instrucciones al modelo).
- **Qué hay que hacer:** `vision-v5`, `ficha-v4`, `ficha-renglon-v6`, `informe-tecnico-v3`, `oferente-nombre-v3`, `procedimiento-datos-v3` y `consulta-v5`, con las reglas de T-279; las versiones publicadas (incluida `consulta-v1`) no se editan. Inventariar y, donde falte, registrar nombre, versión y huella en cada pedido (P6). Completar el informe de revisión (cada instrucción vigente con su tabla) y activar la prueba de que toda instrucción vigente está en `SIMPLIFIED`.
- **Archivos:** `evaluon/assessment/prompts/vision-v5.md`, `informe-tecnico-v3.md`, `evaluon/offers/prompts/ficha-v4.md`, `ficha-renglon-v6.md`, `oferente-nombre-v3.md`, `evaluon/tenders/prompts/procedimiento-datos-v3.md`, `evaluon/queries/prompts/` (consulta), `evaluon/queries/answering.py`, `evaluon/assessment/services/technical_report.py`, `evaluon/offers/proposal_fields.py`, `evaluon/tenders/proposal/procedure_fields.py`, `evaluon/offers/vision.py` y los módulos de ficha (solo constantes y registro de la instrucción), `evaluon/settings.py`, `tests/test_instrucciones_revisadas.py`, `tests/fixtures/instrucciones.sha256`, `specs/016-calidad-medible/revision-instrucciones.md`.
- **Verificación:** las tres pruebas de instrucciones (ahora sobre todas las vigentes); `pytest tests/queries tests/offers tests/assessment`; cada pedido de estas instrucciones registra su versión y su huella.
- **No tocar:** el resto de las instrucciones, la lógica de lectura y de la consulta.

### T-283 · Medición del paso 2, ronda 1 (matrices y caso-00)

- **Requisitos:** REQ-119, REQ-120, REQ-125
- **Nivel de verificación:** plena (medición).
- **Antes de medir:** copia fija del commit (`git archive`), tests `decision_literal` (`--verificar-decisiones`), pruebas de largo y de no calco en verde, comprobación del diff de `evaluon/` contra las referencias (si toca la ruta medida, B0 de las matrices, unas 1,9 h más), caso chico como corte vertical (si falla en forma, no se mide lo demás).
- **Qué hay que hacer:** en una sola ventana por tanda, una corrida a la vez: `releer_pliego` si cambió la lectura, `medir_matriz` de 00, 01, 02 y 06 con sus listas y exclusiones; caso-00 completo (matriz y evaluación de las 3 ofertas, revisión como Comisión de la matriz); `correr_evals`, `medir_fichas` y `leer_con_vision` para las auxiliares. `nvidia-smi` cada 5 s. Cada «cumple» leído uno por uno.
- **Umbral (plan, 7 a 12):** 0 «cumple» sin fundamento; 0 contradicciones; 100 % de citas literales; lista presente igual o mejor que la referencia en cada caso (00 41/42, 01 79/80, 02 95/97, 06 35/35); 0 «no se encontró el documento» sin pregunta y 100 % de los «no determinado» con pregunta o documento; filas firmes con pareja ≥ 70 % y sin bajar 10 puntos; caso-00 completo ≤ 112,6 min y ≤ 22.000 MiB; auxiliares no peor que T-266 (16/17, 6/6, 100 % de cita literal, máximo ≤ 30 s). Si todas las demás empatan, queda la instrucción corta.
- **Archivos:** `specs/016-calidad-medible/verificacion/T-283.md` (solo cifras, claves y `M-NNN`); las corridas y el detalle con texto, fuera del repositorio.
- **Verificación:** el registro nombra el commit, las instrucciones con su huella, el motor, los umbrales escritos antes y el resultado de cada uno.
- **No tocar:** código, instrucciones, listas, exclusiones, umbrales, este archivo, ni integrar nada durante la corrida.
- **GPU:** de 4 a 6 h.

### T-284 · Medición del paso 2, ronda 1 (evaluación con verdad)

- **Requisitos:** REQ-119, REQ-120, REQ-125
- **Nivel de verificación:** plena (medición).
- **No arranca sin:** la verdad del caso de ajuste revisada y firmada (T-276).
- **Qué hay que hacer:** evaluar el caso de ajuste con verdad dos veces, de a una: con el commit de arranque del clon (B0, instrucciones y reglas de la 015) y con el candidato; `medir_evaluacion --celdas-comision verdad-celdas.yaml` en las dos; comparación fila por fila (regla 3 del ADR-0059) y celda por celda de lo que cambia; lectura de todos los «cumple».
- **Umbral (plan, 7, 9 y 10):** 0 «cumple» sin fundamento; 0 contradicciones con la Comisión; tres salidas; exactitud por celda sin llegar a 6 filas en contra con 0 a favor ni a 8 contra 1; erradas nuevas explicadas una por una.
- **Archivos:** `specs/016-calidad-medible/verificacion/T-284.md`.
- **Verificación:** igual que T-283.
- **No tocar:** igual que T-283.
- **GPU:** de 2 a 4 h.

### T-285 · Ajuste único del paso 2

- **Requisitos:** REQ-119, REQ-120
- **Nivel de verificación:** plena (instrucciones y lógica).
- **Qué hay que hacer:** corregir en una sola tarea todos los hallazgos de T-283 y T-284, un commit por hallazgo, **como definiciones y nunca como ejemplos de un caso** (los casos de ajuste no se calcan); nuevas versiones de las instrucciones que cambien, con sus huellas; lo que no se pueda corregir pasa con su impacto a la lista de revisión (ADR-0024). Se cierra sin cambios si T-283 y T-284 cumplen todo.
- **Archivos:** las instrucciones y módulos que corresponda a cada hallazgo, `evaluon/settings.py` (versiones), `tests/fixtures/instrucciones.sha256`, `specs/016-calidad-medible/revision-instrucciones.md`.
- **Verificación:** pruebas de instrucciones, `pytest` del área tocada, tests `decision_literal`; la medición es de T-286.
- **No tocar:** umbrales, listas, la verdad, los casos de aceptación.

### T-286 · Re-medición del paso 2, ronda 2

- **Requisitos:** REQ-119, REQ-120, REQ-125
- **Nivel de verificación:** plena (medición).
- **Qué hay que hacer:** medir de nuevo solo lo que cambió T-285 (matrices y evaluaciones afectadas) más el caso-00 completo con el commit final, que es la referencia local simplificada de los pasos 3 y 4 y de T-307; mismos umbrales que T-283 y T-284. Es la última ronda: lo que no llegue pasa con su impacto a la lista de revisión y la decisión es del responsable (P7). Se cierra sin correr si T-285 no cambió nada y se usan los resultados de T-283 y T-284.
- **Archivos:** `specs/016-calidad-medible/verificacion/T-286.md`.
- **Verificación, no tocar:** igual que T-283.
- **GPU:** de 2 a 5 h.

### T-287 · Cierre de los pasos 1 y 2

- **Requisitos:** REQ-125
- **Nivel de verificación:** liviana (documentos).
- **Qué hay que hacer:** ADR-0071 (resultado de los pasos 1 y 2: la verdad ampliada y las instrucciones y reglas simples quedan, con sus cifras, o qué parte no pasó y por qué), `specs/016-calidad-medible/verificacion/T-287.md` con el umbral escrito antes, el resultado y la decisión de cada paso, y la suite completa sobre la combinación con `main`. El Coordinador abre el pull request `016-integracion` → `main`; lo aprueba el responsable.
- **Archivos:** `docs/adr/0071-*.md`, `specs/016-calidad-medible/verificacion/T-287.md`.
- **Verificación:** suite completa en verde sobre la combinación (ADR-0012).
- **No tocar:** código.

### T-288 · Esquema y configuración del uso externo

- **Requisitos:** REQ-122
- **Nivel de verificación:** plena (esquema y configuración compartida).
- **Qué hay que hacer:**
  1. `EventType.EXTERNAL_REQUEST = "external_request"` en `audit/models.py` y su migración `0009_*` (la única de la feature; `audit_event` conserva su disparador de solo inserción).
  2. `settings.py`: `EXTERNAL_ENABLED=false`, `EXTERNAL_STAGES` (`matriz` y `verificador`, ambas `local`), modelo por etapa (`claude-sonnet-5-5`), esfuerzo y pensamiento por etapa, `EXTERNAL_MODE` (`lotes`), `EXTERNAL_BATCH_POLL_SECONDS=30`, `EXTERNAL_BATCH_MAX_WAIT_SECONDS=7200`, `EXTERNAL_CASE_CAP_USD=2.00`, `EXTERNAL_MONTH_CAP_USD=10.00`, `EXTERNAL_STAGE_ESTIMATE_USD` (0,30 y 0,30), `EXTERNAL_STAGE_STOP_FACTOR=2`, `EXTERNAL_PRICES` con versión, fecha (2026-10-15) y fuente. La clave `ANTHROPIC_API_KEY` no se lee de `settings` por omisión ni va en el compose base.
  3. Pasar las variables al compose base y a `.env.example`, con `tests/test_compose_env.py` comprobando que coincidan.
- **Umbral 20 (parte):** con los valores por omisión el sistema funciona como hoy.
- **Archivos:** `evaluon/audit/models.py`, `evaluon/audit/migrations/0009_*.py`, `evaluon/settings.py`, `docker-compose.yml`, `.env.example`, `tests/test_compose_env.py`, `tests/audit/test_external_event.py` (nuevo).
- **Verificación:** `manage.py makemigrations --check`; `migrate` sobre una base vacía y sobre la del clon; el disparador impide editar un hecho; `pytest tests/test_compose_env.py tests/audit`; suite completa una vez al final.
- **No tocar:** el resto de `settings.py`, las instrucciones, ningún otro modelo.

### T-289 · Cliente de la API externa, su doble y la salida a internet

- **Requisitos:** REQ-122
- **Nivel de verificación:** plena (código de red y un principio de la constitución).
- **No arranca sin:** ADR-0066 aceptado.
- **Qué hay que hacer:** ADR-0066: `evaluon/ai/external/client.py` con `urllib`, host `api.anthropic.com` fijo en el código y HTTPS, cabeceras `x-api-key` y `anthropic-version`, crear un mensaje, crear y consultar un lote, bajar sus resultados, errores propios (tiempo agotado, servicio no disponible, entrada demasiado larga, vencido), `ExternalDisabled` antes de abrir un socket si no está habilitado o falta la clave; la clase `ExternalPayload` (única entrada que acepta el cliente, que construirá `guard.py`); `FakeExternal` en `tests/conftest.py` con respuestas guiadas, errores y vencimientos, y un fixture automático que hace fallar toda llamada real en la suite; `docker-compose.externo.yml` (red `egress` y clave para `clon_worker` y `clon_app`); `tests/portal/test_no_outbound.py` permite exactamente `evaluon/ai/external/client.py` además de lo de hoy; `tests/portal/test_network.py` sigue exigiendo que el compose base solo dé `egress` a `portal_worker`.
- **Archivos:** `evaluon/ai/external/__init__.py`, `evaluon/ai/external/client.py`, `evaluon/ai/external/payload.py`, `tests/conftest.py`, `tests/ai/test_external_client.py` (nuevo), `docker-compose.externo.yml`, `tests/portal/test_no_outbound.py`, `tests/portal/test_network.py`.
- **Verificación:** `pytest tests/ai tests/portal`; una llamada real dentro de la suite falla; sin habilitar, `ExternalDisabled` y ningún socket abierto; el compose base no cambia y `docker compose -f docker-compose.clon.yml -f docker-compose.externo.yml config` muestra `egress` solo en los servicios del clon; suite completa una vez al final.
- **No tocar:** el compose base, el flujo de matriz y de evaluación, la lectura.

### T-290 · Puerta de filtrado, libro de gasto y registro

- **Requisitos:** REQ-121, REQ-122
- **Nivel de verificación:** plena (principio P4 y P9, y registro P6).
- **No arranca sin:** ADR-0067 y ADR-0068 aceptados.
- **Qué hay que hacer:** ADR-0067 y ADR-0068:
  1. `guard.py`: único lugar que construye un `ExternalPayload`; lista permitida por tipo de documento (pliego, anexos, circulares y respuestas a consultas; oferta de tipo económico, técnico, garantía, anexo técnico, otro o sin clasificar; nunca `compliance`); exclusiones por contenido (respuestas de la Comisión, informe técnico del área, requisitos externos por catálogo o por marca del modelo, celdas con grupo o cita de un documento `compliance`); comprobación por huellas de párrafos de 8 palabras contra los documentos `compliance` del procedimiento; un pedido bloqueado queda con resultado `bloqueado` y vuelve al camino local con la anomalía `externo_bloqueado`.
  2. `ledger.py`: escribe el hecho `external_request` por pedido (campos del plan, «Modelo de datos»); suma el costo del mes y del procedimiento antes de cada lote con la estimación conservadora (caracteres entre 2,5); el lote que haría pasar los 2 USD por caso o los 10 por mes no sale; frena una etapa al doble de su estimado; reuso por huella con resultado `reutilizado` y costo 0.
  3. `gasto_externo` (`--mes`, `--procedimiento`, `--por-etapa`, `--verificar-filtro`): gasto real; el escaneo del filtro con una implementación propia, independiente de `guard.py`.
  4. Una hoja de compliance inventada, marcada con una palabra clave improbable en cada párrafo, en los datos de pruebas.
- **Umbral 19 y 21 (con el doble):** 0 pedidos con texto de la hoja ni la palabra clave; los requisitos externos quedan en local; un tipo desconocido, un documento sin clasificar con un párrafo de la hoja, una respuesta de la Comisión y un informe técnico no salen; el lote que pasa el tope no sale.
- **Archivos:** `evaluon/ai/external/guard.py`, `evaluon/ai/external/ledger.py`, `evaluon/assessment/management/commands/gasto_externo.py`, `tests/ai/test_external_guard.py`, `tests/ai/test_external_ledger.py`, `tests/ai/data/compliance-inventada/` (nuevos).
- **Verificación:** `pytest tests/ai`; alteraciones del código (quitar una exclusión debe hacer fallar una prueba); `gasto_externo --verificar-filtro` sobre un registro de prueba con un pedido que sí contiene la hoja lo detecta; suite del área.
- **No tocar:** el cliente, el flujo de matriz y de evaluación, `settings.py`.

### T-291 · Matriz con modelo externo

- **Requisitos:** REQ-122, REQ-123
- **Nivel de verificación:** plena (lógica, instrucciones al modelo y un principio de la constitución).
- **Qué hay que hacer:** según el plan, «Paso 3»:
  1. `matriz-externa-v1` (decisora: ≤ 9.000 caracteres con el bloque `matriz-definiciones-v9` incluido, sin ejemplos de casos) y su entrada en `EXTERNAL_PROMPT_VERSIONS`.
  2. `tenders/proposal/external.py`: con el pliego completo como prefijo común (texto canónico de todos los tramos con ruta, encabezado y clase, caché de una hora) manda 3 a 5 pedidos (extracción en varios, completitud y filtro en uno) por `guard.py` y `client.py` en lotes; devuelve el mismo contrato que `extraction.Extractor` y `filter.Filter`; la cita la ubica `quotes.locate` y la amplía `sentences.py`; un fragmento que no se ubica se descarta con la anomalía `fragmento_externo_no_ubicado`.
  3. `run.py::propose`: con `EXTERNAL_STAGES["matriz"] = "externo"` reemplaza extracción, completitud, unión, unificación y filtro; deja intactas las reglas por tramo, las tablas pendientes, las filas técnicas, las circulares, las consecuencias, el respaldo y el guardado; si el pedido falla, se agota el tope o la puerta bloquea, sigue con la cadena local y lo registra (`externo_no_disponible`); clave `externo` en `models`, `parameters` y `prompt_versions` de la propuesta.
  4. `medir_matriz --externo matriz`: dos propuestas sobre la misma lectura en la misma base, una local y otra externa, con el gasto en el resumen.
- **Archivos:** `evaluon/tenders/proposal/external.py`, `evaluon/tenders/proposal/run.py`, `evaluon/tenders/prompts/matriz-externa-v1.md`, `evaluon/tenders/management/commands/medir_matriz.py`, `evaluon/settings.py` (`EXTERNAL_PROMPT_VERSIONS`), `tests/fixtures/instrucciones.sha256`, `specs/016-calidad-medible/revision-instrucciones.md`, `tests/tenders/test_external_matrix.py` (nuevo).
- **Verificación:** `pytest tests/tenders tests/ai` con `FakeExternal` y el caso chico; con el uso externo apagado, la propuesta es idéntica a la local; el pedido que falla vuelve a lo local; una propuesta externa no contiene texto de una hoja de compliance; pruebas de largo y de no calco de la nueva instrucción; suite del área.
- **No tocar:** el cliente y la puerta, las instrucciones locales, la evaluación.

### T-292 · Prueba de humo con el proveedor real

- **Requisitos:** REQ-121, REQ-122, REQ-123
- **Nivel de verificación:** plena (primera salida real a internet).
- **No arranca sin:** la clave, el límite de 10 USD en la consola, la política de retención confirmada y el `.env` del clon (ver «Condiciones previas»).
- **Qué hay que hacer:** con el caso chico y la hoja de compliance inventada cargada en una oferta, correr la matriz externa en modo directo (unos 3 pedidos); comprobar el registro de cada pedido (proveedor, modelo, versión de la instrucción, texto enviado, respuesta, tokens, costo), que ningún pedido tenga el texto ni la palabra clave de la hoja, `gasto_externo --verificar-filtro` en 0, que sin `docker-compose.externo.yml` no haya ruta a internet y que con la clave inválida o el tope en cero la propuesta siga por lo local. Anotar el límite de la consola en `entorno.md`.
- **Umbral:** gasto ≤ 0,10 USD; 100 % de los pedidos registrados; 0 pedidos con texto de la hoja.
- **Archivos:** `specs/016-calidad-medible/verificacion/T-292.md`, `specs/016-calidad-medible/entorno.md`.
- **Verificación:** `gasto_externo --por-etapa` y `--verificar-filtro`.
- **No tocar:** código; casos reales.

### T-293 · Medición del paso 3, ronda 1 (ajuste)

- **Requisitos:** REQ-123, REQ-125
- **Nivel de verificación:** plena (medición).
- **Qué hay que hacer:** propuesta externa de 00, 01, 02 y 06 en la misma lectura y la misma base, comparada con la local simplificada de T-286 (no se repite); la parte local que queda después de la etapa externa (circulares, consecuencias, respaldo, filas técnicas) usa la GPU; revisión como Comisión del caso-00; gasto real por etapa con `gasto_externo`.
- **Umbral 16 (puerta de ajuste):** en 00, 01, 02 y 06 el externo no es peor que la local simplificada en lista presente ni en firmes con pareja, y 0 pedazos sin sujeto; informativos 14 y 15. Gasto ≈ 1,20 USD (frena a 0,60 USD por etapa). Si no lo pasa tras las dos rondas, el externo no pasa a aceptación y queda local.
- **Archivos:** `specs/016-calidad-medible/verificacion/T-293.md`.
- **Verificación, no tocar:** igual que T-283.
- **GPU:** unas 0,75 h.

### T-294 · Ajuste único de la matriz externa

- **Requisitos:** REQ-123
- **Nivel de verificación:** plena (instrucciones al modelo).
- **Qué hay que hacer:** todos los hallazgos de T-293 en una sola tarea: `matriz-externa-v2` y parámetros (esfuerzo, `max_tokens`, cantidad de pedidos de extracción), como definiciones y nunca como ejemplos de un caso; se cierra sin cambios si T-293 cumple todo.
- **Archivos:** `evaluon/tenders/prompts/matriz-externa-v2.md`, `evaluon/tenders/proposal/external.py`, `evaluon/settings.py`, `tests/fixtures/instrucciones.sha256`, `specs/016-calidad-medible/revision-instrucciones.md`.
- **Verificación:** pruebas de instrucciones y `pytest tests/tenders tests/ai`.
- **No tocar:** umbrales, los casos de aceptación.

### T-295 · Re-medición del paso 3, ronda 2 (ajuste)

- **Requisitos:** REQ-123, REQ-125
- **Nivel de verificación:** plena (medición).
- **Qué hay que hacer:** medir de nuevo lo que cambió T-294 con el mismo método y el mismo umbral 16. Es la última ronda de ajuste. Se cierra sin correr si T-294 no cambió nada.
- **Archivos:** `specs/016-calidad-medible/verificacion/T-295.md`. **Verificación, no tocar:** igual que T-293. **GPU:** unas 0,75 h; gasto ≈ 1,20 USD.

### T-296 · Medición final del paso 3 (aceptación)

- **Requisitos:** REQ-123, REQ-125
- **Nivel de verificación:** plena (medición).
- **Qué hay que hacer:** una sola corrida, sin ajuste posterior, de 03, 04 y 05: matriz local simplificada y matriz externa sobre el mismo commit, con las listas y las exclusiones congeladas (huella y fecha); `medir_matriz --externo matriz`; revisión como Comisión de lo que cambia. Se cierra sin correr si T-295 no pasó la puerta.
- **Umbral 13 y 14 (informativo 15):** lista presente del externo sube al menos 5 puntos porcentuales en al menos 2 de los 3 casos sin bajar en ninguno, firmes con pareja no bajan en ninguno, pedazos sin sujeto = 0; si no, queda local. Una diferencia de una entrada es empate y en empate queda lo local (ADR-0065). Referencias de T-266 (local de entonces): 83,6 %, 91,8 % y 96,6 %. Gasto ≈ 0,90 USD.
- **Archivos:** `specs/016-calidad-medible/verificacion/T-296.md`. **Verificación, no tocar:** igual que T-283. **GPU:** unas 3 h.

### T-297 · Segunda comparación de la matriz con Opus 5.5

- **Requisitos:** REQ-123
- **Nivel de verificación:** plena (medición).
- **Qué hay que hacer:** solo si Sonnet no pasó el umbral 13 o 14 en T-296 y la etapa pasó la puerta de T-295: la misma instrucción con `claude-opus-5-5`, una vez, en la etapa que falló, en los casos de aceptación; se registra que se miró dos veces la misma aceptación; si el tope del mes no alcanza, espera al mes siguiente. Se cierra sin correr si no corresponde.
- **Umbral:** el mismo (13 y 14) más la puerta 16 en el ajuste; gasto hasta 2,10 USD. **Archivos, verificación, no tocar:** igual que T-296; `specs/016-calidad-medible/verificacion/T-297.md`.

### T-298 · Cierre del paso 3

- **Requisitos:** REQ-125
- **Nivel de verificación:** liviana (documentos).
- **Qué hay que hacer:** ADR-0072 (matriz: local o externa, y por qué) con las cifras de T-293 a T-297 y el gasto real por etapa; `specs/016-calidad-medible/verificacion/T-298.md` con el umbral escrito antes, el resultado y la decisión; pull request `016-integracion` → `main` con la suite completa. Adoptar una etapa externa en el piloto es decisión del responsable (P11).
- **Archivos:** `docs/adr/0072-*.md`, `specs/016-calidad-medible/verificacion/T-298.md`. **Verificación:** suite completa sobre la combinación. **No tocar:** código.

### T-299 · Verificador externo de citas

- **Requisitos:** REQ-121, REQ-122, REQ-124
- **Nivel de verificación:** plena (lógica, instrucciones al modelo y principios de la constitución).
- **Qué hay que hacer:** según el plan, «Paso 4»:
  1. `verificador-v1` (≤ 5.000 caracteres): `razonamiento` (≤ 400 caracteres), `sostiene` (`si`, `no`, `parcial`) y, si no es `si`, `pregunta` a la Comisión; esfuerzo `low` y pensamiento `between_tools`; entrada en `EXTERNAL_PROMPT_VERSIONS`.
  2. `assessment/verifier.py`: una función que verifica una lista de celdas (requisito con su punto y la oración marcada, conclusión, oración citada con documento, página y contexto de la misma página, dato del Portal citado; sin el razonamiento del modelo local, sin respuestas de la Comisión), por `guard.py` y `client.py` en un lote por oferta; la usan `evaluate_offer` con los pares en armado y la medición con resultados guardados.
  3. `services/evaluate.py`: el verificador corre después del contraste y de las reglas y antes de armar la pregunta; solo sobre «cumple» o «no cumple» con una oración citada o un dato del Portal (no las decididas por ausencia, IVA, presentación física o forma de garantía, ni «no determinado», ni requisitos externos, ni celdas con documentos `compliance`); `no` o `parcial` pasa la celda a «no determinado» `sin_corroborar` con las mismas citas y la pregunta (la del verificador si cumple `question_form` y no se dirige al oferente; si no, la arma el código); nunca de «no determinado» a «cumple»; una respuesta inválida, un vencimiento, un bloqueo o el tope agotado dejan la celda como estaba con la anomalía `verificador_sin_respuesta`.
  4. `facts["verificador"]` (`antes`, `despues`, `respuesta`, `razonamiento`, `pregunta`, `hecho`) y clave `externo` en `models_used`, `parameters` y `counts` de la corrida; comando de medición que aplica el verificador a una evaluación guardada (`medir_evaluacion --verificador-sobre`).
- **Archivos:** `evaluon/assessment/verifier.py`, `evaluon/assessment/prompts/verificador-v1.md`, `evaluon/assessment/services/evaluate.py`, `evaluon/assessment/management/commands/medir_evaluacion.py`, `evaluon/assessment/evaluation.py`, `evaluon/settings.py`, `tests/fixtures/instrucciones.sha256`, `specs/016-calidad-medible/revision-instrucciones.md`, `tests/assessment/test_verifier.py` (nuevo).
- **Verificación:** `pytest tests/assessment tests/ai` con `FakeExternal` y el caso chico (incluida la hoja inventada: 0 pedidos con su texto); alteraciones del código (permitir «no determinado» → «cumple» debe fallar una prueba); con el uso externo apagado la evaluación es idéntica; pruebas de largo y de no calco; suite del área.
- **No tocar:** el cliente, la puerta, la matriz, las instrucciones locales.

### T-300 · Línea «Etapas fuera del equipo» en pantalla y exportación

- **Requisitos:** REQ-122
- **Nivel de verificación:** liviana (cambio acotado con test que falla antes y pasa después; se acompaña con la lectura del Coordinador de la pantalla, que la abre antes de darla por buena).
- **Qué hay que hacer:** en la pantalla de la evaluación y en su exportación, una línea «Etapas fuera del equipo» con proveedor, modelo, modo y cantidad de pedidos de cada etapa externa, leída de la clave `externo` de la corrida (`models_used` y `parameters`), o «Ninguna: todo corrió en el equipo». Ningún otro cambio de pantalla.
- **Archivos:** `evaluon/assessment/views/results.py`, la plantilla de resultados de la evaluación, `evaluon/assessment/services/export.py`, `tests/assessment/test_result_page.py`, `tests/assessment/test_export.py`.
- **Verificación:** los tests de la pantalla y de la exportación con una corrida con `externo` y otra sin él; la pantalla abierta por el Coordinador.
- **No tocar:** `evaluate.py`, el esquema, otras pantallas.

### T-301 · Medición del paso 4, ronda 1 (ajuste, sin GPU)

- **Requisitos:** REQ-124, REQ-125
- **Nivel de verificación:** plena (medición).
- **Qué hay que hacer:** primero el humo del verificador con el caso chico y el proveedor real (centavos; si falla en forma, no sigue); después el verificador sobre las evaluaciones guardadas de T-286 del caso-00 y del caso de ajuste con verdad, en lotes; cada celda que cambia se lee una por una (¿era errada o exacta?); gasto real con `gasto_externo`.
- **Umbral 17 como puerta:** 0 «cumple» sin fundamento; preguntas conformes 100 %; exactas no bajan; erradas no suben; todo «no determinado» nuevo viene de una celda que era errada. Gasto ≈ 0,60 USD (frena a 0,60 por etapa).
- **Archivos:** `specs/016-calidad-medible/verificacion/T-301.md`. **Verificación, no tocar:** igual que T-283. **GPU:** ninguna.

### T-302 · Ajuste único del verificador

- **Requisitos:** REQ-124
- **Nivel de verificación:** plena (instrucciones al modelo).
- **Qué hay que hacer:** todos los hallazgos de T-301 en una sola tarea: `verificador-v2` y parámetros, como definiciones; se cierra sin cambios si T-301 cumple todo.
- **Archivos:** `evaluon/assessment/prompts/verificador-v2.md`, `evaluon/assessment/verifier.py`, `evaluon/settings.py`, `tests/fixtures/instrucciones.sha256`, `specs/016-calidad-medible/revision-instrucciones.md`.
- **Verificación:** pruebas de instrucciones y `pytest tests/assessment tests/ai`. **No tocar:** umbrales, casos de aceptación.

### T-303 · Re-medición del paso 4, ronda 2 (ajuste, sin GPU)

- **Requisitos:** REQ-124, REQ-125
- **Nivel de verificación:** plena (medición).
- **Qué hay que hacer:** medir de nuevo lo que cambió T-302, con el mismo método y el mismo umbral 17 como puerta. Es la última ronda de ajuste. Se cierra sin correr si T-302 no cambió nada.
- **Archivos:** `specs/016-calidad-medible/verificacion/T-303.md`. **Verificación, no tocar:** igual que T-283. **Gasto:** ≈ 0,60 USD.

### T-304 · Medición final del paso 4 (aceptación)

- **Requisitos:** REQ-121, REQ-122, REQ-124, REQ-125
- **Nivel de verificación:** plena (medición).
- **No arranca sin:** la verdad de los casos de aceptación revisada, firmada y congelada (T-276).
- **Qué hay que hacer:** una sola corrida: evaluación local de los casos de aceptación con verdad (al menos 2) con el commit final y el verificador una vez; el «sin verificador» sale de `facts["verificador"]["antes"]` y el «con» de `despues`; `medir_evaluacion --celdas-comision verdad-celdas.yaml`; lectura de todos los «cumple» y de todas las preguntas; `gasto_externo --verificar-filtro` y gasto por etapa y por caso.
- **Umbral 17 a 21:** con el verificador 0 «cumple» sin fundamento; 100 % de preguntas conformes (dirigidas a la Comisión, con requisito, conclusión y texto); celdas exactas no bajan; todo «no determinado» nuevo viene de una celda errada; 0 pedidos con texto de la hoja; gasto ≤ 2 USD por caso y ≤ 10 USD por mes; si empata, queda sin verificador. Informativo 18: Portal «cumple» con su cita 100 %, «no determinado» que cuenta ≤ 15 %, preguntas conformes 100 %. Gasto ≈ 0,60 a 0,90 USD.
- **Archivos:** `specs/016-calidad-medible/verificacion/T-304.md`. **Verificación, no tocar:** igual que T-283. **GPU:** de 2 a 4 h.

### T-305 · Segunda comparación del verificador con Opus 5.5

- **Requisitos:** REQ-124
- **Nivel de verificación:** plena (medición).
- **Qué hay que hacer:** solo si Sonnet no pasó el umbral 17 en T-304 y la etapa pasó la puerta de ajuste: la misma instrucción con `claude-opus-5-5`, una vez, sobre las mismas evaluaciones guardadas; se registra que se miró dos veces la misma aceptación. Se cierra sin correr si no corresponde.
- **Umbral:** el 17; gasto hasta 1,80 USD. **Archivos, verificación, no tocar:** igual que T-304; `specs/016-calidad-medible/verificacion/T-305.md`.

### T-306 · Cierre del paso 4

- **Requisitos:** REQ-125
- **Nivel de verificación:** liviana (documentos).
- **Qué hay que hacer:** ADR-0073 (verificador: con o sin, y por qué) con las cifras de T-301 a T-305 y el gasto real por etapa; `specs/016-calidad-medible/verificacion/T-306.md`; pull request `016-integracion` → `main` con la suite completa. Adoptarlo en el piloto es decisión del responsable (P11).
- **Archivos:** `docs/adr/0073-*.md`, `specs/016-calidad-medible/verificacion/T-306.md`. **Verificación:** suite completa sobre la combinación. **No tocar:** código.

### T-307 · Verificación transversal

- **Requisitos:** REQ-121, REQ-122, REQ-125
- **Nivel de verificación:** plena (principios de la constitución y regresión).
- **Qué hay que hacer:**
  1. Suite completa sobre la combinación de `016-integracion` con `main` (ADR-0012).
  2. Con el uso externo apagado: el caso-00 completo en el clon da las mismas celdas que la corrida final del paso 2 (T-286), 0 diferencias, dentro del tiempo (≤ 112,6 min) y de la memoria (≤ 22.000 MiB).
  3. `gasto_externo --verificar-filtro` sobre todo el registro de la feature: 0 pedidos con texto de una hoja de compliance; todos los requisitos que dependen de consultas externas en local.
  4. 100 % de los pedidos externos con proveedor, modelo, versión de la instrucción, texto enviado y respuesta; gasto total por etapa, por caso y por mes contra los topes (2 USD y 10 USD).
  5. Que sin `docker-compose.externo.yml` ningún contenedor del clon tenga ruta a internet.
- **Umbral 19 a 21 (plan).**
- **Archivos:** `specs/016-calidad-medible/verificacion/T-307.md`.
- **Verificación:** los comandos de arriba; el registro nombra el commit y las cifras.
- **No tocar:** código. **GPU:** unas 2 h.
