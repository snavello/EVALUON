# Plan 013 · Recorrido del procedimiento (aplicación mínima)

Estado: borrador · Fecha: 2026-10-07 · Aprobó: —

Spec: `specs/013-recorrido-procedimiento/spec.md` (aprobada el 2026-10-07)

ADR de este plan, **propuesto**: `docs/adr/0045-recorrido-estado-calculado-sondeo-y-avance-de-pedidos.md` (estado calculado al mostrar, sondeo local, avance de los pedidos). Se apoya en 0018 (cola), 0025 (ritmo de trabajo), 0026 (cola compartida), 0031 (Portal), 0039 (módulo de evaluación).

## Resumen del enfoque

Un módulo nuevo y chico, `evaluon/journey/`, **sin tablas**: solo lee lo que ya registran el Portal, el pliego, la matriz, las ofertas y la evaluación, y arma una página por procedimiento con seis etapas en orden. Cada etapa es una función de solo lectura que devuelve su estado, cuántas decisiones esperan, el pedido en segundo plano si lo hay y los enlaces a las pantallas existentes. El recorrido no tiene formularios de decisión: enlaza.

Para ver el avance sin recargar, la página pide cada 5 segundos al servidor el bloque de las etapas (un script propio de unas 30 líneas, sin librerías ni CDN) y lo reemplaza. El avance de un pedido sale de lo que la cola y cada servicio ya guardan (tiempo, oferta k de N, última pasada de la matriz); si falta granularidad, una tarea aparte y chica suma una columna `progress` a la cola (ADR-0045).

Orden de trabajo (ADR-0025): primero un **corte vertical** con la página de recorrido de un procedimiento chico y la etapa Evaluación en vivo (T-179); después, en paralelo, las demás etapas y la entrada; al final, la comprobación de los cinco momentos con el caso chico y con el caso-00.

## Criterio de aceptación numérico y umbrales (escritos antes de medir)

| Qué | Umbral | Con qué se mide | Quién |
|---|---|---|---|
| REQ-066, los cinco momentos | 30 de 30 celdas correctas (5 momentos por 6 etapas) | `tests/journey/test_moments.py` con el caso chico inventado, y la misma tabla a mano con el caso-00 | T-185 y T-186 |
| REQ-067, frecuencia | El script pide cada 5 s (no más de 10 s); 0 recargas completas de la página; el cambio de "en curso" a "a decidir" o "lista" se ve en 10 s o menos después de terminar el pedido | Test de la constante y del bloque; prueba manual con un pedido simulado | T-179 y T-186 |
| REQ-067, aviso | Terminar y fallar muestran el mensaje; el motivo de una falla se ve en el 100 % de los casos probados | Test del bloque con pedido terminado y fallido | T-179 |
| REQ-068 | Cada etapa con pendientes mayores que 0 tiene su enlace y el enlace responde 200 al evaluador (6 de 6 etapas) | `test_moments.py` | T-185 |
| REQ-069 | Operador: 0 acciones de decisión en las 6 etapas. Evaluador: las 6 que correspondan | `test_moments.py` | T-185 |
| REQ-065 | La entrada lista el 100 % de los procedimientos con su etapa actual y sus pendientes; alta de enlace del Portal desde la entrada | Tests de la vista | T-183 |
| No funcional: tiempo | La página de recorrido del caso-00 carga en menos de 2 s (mediana de 5 cargas, en el equipo) | Medición local, solo las cifras al repositorio | T-186 |
| No funcional: sin internet | 0 pedidos a direcciones externas: ningún `http://` ni `https://` en las plantillas ni en el script | Test que lo busca | T-179 |

Máximo dos rondas de ajuste (ADR-0025); lo que no llegue pasa con su impacto a "Revisión con el primer producto".

## Componentes

| Componente | Nuevo | Qué hace | Con quién habla |
|---|---|---|---|
| `evaluon/journey/` | Sí | Etapas, vistas, plantillas y script del recorrido. Sin modelos ni migraciones | `tenders`, `portal`, `offers`, `assessment` (solo lectura) |
| `evaluon/journey/stages/` | Sí | Un archivo por etapa con `compute(user, procedure) -> Stage`, más `base.py` (el tipo `Stage` y los ayudantes de pedidos) y `__init__.py` (la lista ordenada) | Tablas existentes y funciones de lectura ya hechas (`matrix_page`, `evaluate.current_result`, `review.state_of`) |
| `evaluon/journey/progress.py` | Sí | `progress_of(job)`: tarea, paso, cuenta y tiempo transcurrido de un pedido en curso | La cola y lo que cada servicio registra |
| `evaluon/static/journey/recorrido.js` y `.css` | Sí | Sondeo cada 5 s y reemplazo del bloque; aviso al terminar o fallar | La vista del bloque |
| `base.html`, `evaluon/urls.py`, `settings.py` | Cambian una línea cada uno | Enlace "Recorrido" en el menú, ruta `recorrido/`, `INSTALLED_APPS` | — |
| `app`, `worker`, `portal_worker`, base de datos, servicios de IA | No | Sin cambios | — |

La IA no interviene. El camino de pliegos y ofertas sigue sin depender de ningún servicio externo (P4): la página lee la base y el script habla solo con el mismo servidor.

### Rutas

| Ruta | Vista | Para qué |
|---|---|---|
| `recorrido/` | `journey:index` | Entrada: lista de procedimientos con etapa actual y pendientes; formulario del enlace del Portal; enlace a "cargar a mano" |
| `recorrido/<procedure_id>/` | `journey:procedure` | Página de recorrido |
| `recorrido/<procedure_id>/etapas/` | `journey:stages` | Solo el bloque de las etapas (lo que el script pide); sin el aviso de fin de `base.html`, para no marcar avisos como vistos |

El formulario de la entrada envía el enlace a la vista existente `portal:links` (que ya valida, registra y redirige a la propuesta); cargar a mano lleva a `tenders:procedures`. No se duplica ninguno.

## Las etapas y cómo se calcula cada estado

Las seis etapas, en el orden de la spec. Un pedido "activo" es uno de la cola en `queued` o `running`; el "último pedido" de una etapa es el más reciente de sus tipos. Reglas comunes, en este orden:

1. Hay un pedido activo de la etapa: **en curso**.
2. El último pedido de la etapa falló y no hay un resultado posterior que lo supere: **con error**, con el motivo (`job.error`).
3. La etapa no tiene lo que necesita para empezar o no se hizo todavía: **pendiente**.
4. Hay decisiones que esperan a la Comisión: **a decidir**, con la cuenta.
5. Si no: **lista**.

| Etapa | Pedidos de la cola | Pendiente cuando | A decidir (cuenta) | Enlace "ver" y "decidir" |
|---|---|---|---|---|
| 1. Datos del Portal | `portal_explore`, `portal_review` (por `target_id` = enlace; el procedimiento puede faltar al empezar) | No hay enlace del Portal para el procedimiento. Es **opcional**: no cuenta como etapa actual (el procedimiento puede cargarse a mano) | Ítems de la propuesta del Portal en estado `propuesto` | `portal:proposal` (ver y decidir); `portal:imported` si ya se cargó |
| 2. Pliego y circulares | `read_document` | No hay documentos del pliego | Ninguna (la lectura es automática) | `tenders:procedure` |
| 3. Matriz | `propose_matrix` | No hay pliego listo o no hay versión ni pedido | Con versión **borrador**: requisitos en estado `propuesto` más tramos pendientes sin resolver | `tenders:matrix` de la versión (ver); validar y confirmar solo el evaluador |
| 4. Ofertas | `read_offer_document`, `build_sheet` | No hay ofertas | Filas de la última ficha de cada oferta en estado `propuesto` | `offers:procedure_offers`; `offers:sheet` de cada ficha con pendientes |
| 5. Evaluación | `evaluate_offers` | No hay matriz validada, ofertas con documentos o ninguna evaluación | Ninguna (la evaluación solo propone) | `assessment:matrix` (pide "Evaluar todas las ofertas") |
| 6. Matriz de evaluación | — (las decisiones son de personas) | No hay ninguna evaluación | Pares con estado `propuesto`, preguntas sin respuesta y ofertas con filas técnicas pendientes del ok del informe técnico (los tres salen de `assessment.services.matrix.matrix_page`, que ya los calcula) | `assessment:matrix`, `assessment:questions` |

**Lista** en cada caso: la etapa tiene lo que necesita y no tiene pendientes (matriz: versión validada; ofertas: todas con documentos leídos; evaluación: toda oferta con documentos tiene una evaluación de la versión validada vigente; matriz de evaluación: ningún par `propuesto` y ninguna pregunta abierta).

**Etapa actual** del procedimiento: la primera etapa que no está lista, salvo la del Portal cuando es opcional. **Pendientes del procedimiento**: la suma de las cuentas de "a decidir".

Supuestos que el plan toma (ver "Dudas abiertas" al final): la ficha de una oferta no es condición para evaluar, así que sus filas pendientes ponen la etapa Ofertas "a decidir" pero no frenan la etapa Evaluación; los tramos "sugeridos" de la matriz no se cuentan como decisión pendiente.

### El tipo `Stage`

`Stage(key, label, state, pending, detail, view_url, decide_url, job, progress, error, optional)`. `decide_url` es `None` para quien no es evaluador (REQ-069); el operador recibe solo `view_url`. La plantilla muestra "Ir a decidir" únicamente si `decide_url` existe.

## Avance en vivo (REQ-067)

- `progress_of(job)` devuelve `{task, step, done, total, elapsed_seconds}`:
  - `evaluate_offers`: tarea "Evaluando las ofertas"; paso "oferta k de N" con `k` = evaluaciones (`assessment_run`) del pedido y `N` = `len(request.offers)`.
  - `propose_matrix`: tarea "Proponiendo la matriz"; paso = nombre de la última pasada (`RunStep.pass_name`); cuenta = pedidos al modelo hechos.
  - Demás tipos: tarea por tipo y solo tiempo transcurrido (`now - started_at`; si está en espera, "en espera desde").
- Si la tarea de granularidad fina (T-184) está hecha, `progress_of` usa la columna `progress` del pedido para mostrar "requisito x de y" dentro de la oferta o de la ficha, y cae a lo anterior si está vacía.
- El bloque HTML de las etapas es el que vuelve el sondeo. El script lo reemplaza y compara el estado de cada etapa con el anterior: si una etapa pasó de "en curso" a otra, escribe en una región de aviso (`role="status"`) "La etapa X terminó" o "La etapa X falló: motivo". La falla además queda visible en la propia etapa mientras siga siendo el último pedido.
- El script se detiene mientras la pestaña está oculta y reintenta si una respuesta falla (muestra "sin conexión con el servidor" y sigue). Una sesión vencida (redirección al ingreso) se muestra como aviso con enlace al ingreso.

## Roles (REQ-069, P3)

Todas las vistas y el cálculo exigen rol de la Comisión (`require_commission_role`, operador como mínimo, como el resto de las pantallas); sin él, 403 y el rechazo queda registrado. El operador ve todo el recorrido, las cuentas y los enlaces "ver". Solo el evaluador (`commission_role == evaluator`) recibe `decide_url` y ve "Ir a decidir". El recorrido no ejecuta ninguna decisión y no tiene botones que cambien datos; las decisiones siguen en sus pantallas, que comprueban el rol por su cuenta.

## Modelo de datos

Sin tablas ni cambios de esquema en el corte ni en las etapas. Única excepción, **opcional y aparte** (T-184, ADR-0045, alternativa 3.B): una columna `progress` (JSON, por omisión vacío) en `tenders_job`, con su migración.

## Flujo de IA

No usa IA.

## Registro de auditoría

La página no decide ni modifica nada, así que no agrega hechos de auditoría (P6). Lo que sí queda: el rechazo por rol (`rejected`) lo registra la comprobación de rol existente. Cada decisión que se tome desde un enlace queda registrada por su pantalla, como hoy. `progress` (T-184) no es registro de auditoría: es un dato de seguimiento descartable; la auditoría de cada pedido sigue siendo la de su servicio (`matrix_proposal`, `sheet_build`, `eval_build`).

## Cobertura de requisitos

| Requisito | Cómo se resuelve | Cómo se verifica |
|---|---|---|
| REQ-065 | Vista `journey:index` con la etapa actual y los pendientes de cada procedimiento y el formulario del enlace del Portal (envía a `portal:links`) más el enlace a cargar a mano; corte mínimo en T-179, completa en T-183 | `tests/journey/test_index.py`: lista todos con etapa y pendientes; el alta con el enlace llega a la propuesta del Portal |
| REQ-066 | Funciones de etapa y regla de estado de "Las etapas y cómo se calcula cada estado"; Evaluación en T-179, Portal, Pliego y Matriz en T-180, Ofertas en T-181, Matriz de evaluación en T-182 | `tests/journey/test_stage_*.py` por etapa y `test_moments.py` con 5 momentos por 6 etapas (30 de 30); T-186 con el caso-00 |
| REQ-067 | Vista del bloque `journey:stages`, `progress.py`, script de sondeo cada 5 s y región de aviso; T-179 y, para el detalle fino, T-184 | Tests del bloque con pedido en curso, terminado y fallido; constante de 5 s y ausencia de recarga; prueba manual con pedido simulado (T-186) |
| REQ-068 | Cada etapa con `view_url` y, para el evaluador, `decide_url` hacia la pantalla existente; cuenta de pendientes visible | `test_moments.py`: enlaces de las 6 etapas con pendientes responden 200 |
| REQ-069 | `decide_url` solo con `commission_role == evaluator`; 403 sin rol | `test_moments.py` y `test_roles.py`: operador 0 acciones de decisión, evaluador las que corresponden |
| No funcional: 2 s | Consultas acotadas por etapa; el bloque del sondeo reutiliza el mismo cálculo | Medición del caso-00 en T-186 |
| No funcional: sin internet | Script y estilos propios en `static/`; ninguna dirección externa | Test que busca `http://` y `https://` en plantillas y script |

## Verificación contra la constitución

| Principio | Cumple | Nota |
|---|---|---|
| P1 Spec fuente de verdad | sí | Cada tarea nombra su REQ; las dudas del plan están abajo |
| P3 El sistema recomienda, la Comisión decide | sí | El recorrido solo enlaza; el operador no ve acciones de decisión (REQ-069) |
| P4 Datos | sí | Sin servicios externos; casos de prueba inventados; el caso-00 se mide solo en el equipo y al repositorio van cifras |
| P5 Local y reproducible | sí | Sin dependencias nuevas, sin CDN; se levanta con el `app` actual |
| P6 Auditoría | sí | No agrega hechos porque no decide; el rechazo por rol queda registrado |
| P10 Simplicidad | sí | Sin tablas, sin librerías, un script de unas 30 líneas; la columna `progress` es opcional y aparte |

## Decisiones

- ADR-0045 (propuesto): estado calculado, sondeo local y avance de los pedidos.

## Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El cálculo repetido cada 5 s por pestaña se vuelve lento con muchos pares (la etapa 6 recorre todos los pares) | La página supera 2 s | Medir en T-186; la etapa 6 reutiliza `matrix_page`, que ya soporta el caso-00; si no alcanza, el bloque del sondeo calcula primero los pedidos activos y reutiliza el último resultado de la etapa 6 mientras no haya cambios (una sola ronda de ajuste) |
| Un pedido de evaluación muestra solo "oferta k de N" y parece detenido durante minutos | REQ-067 cumplido a medias | T-184 agrega "requisito x de y"; el tiempo transcurrido siempre se actualiza |
| Una feature futura cambia cómo registra sus estados y el recorrido miente | Estado incorrecto | `test_moments.py` recorre los cinco momentos con los servicios reales; se actualiza con cada cambio |
| El estado "lista" de una etapa depende de un supuesto de la spec (la ficha no frena la evaluación) | Se muestra un estado distinto del que esperan las personas | Dudas abiertas; el responsable confirma antes de aprobar el plan |
| El pedido del Portal anterior al procedimiento no tiene `procedure` | La etapa 1 no ve el pedido | Se busca por el enlace (`PortalLink.procedure`, `target_id`), como ya hace el Portal |
| Dos pestañas, dos usuarios: las dos consultan cada 5 s | Carga extra | Aceptable con el número de usuarios del piloto; el script se detiene con la pestaña oculta |

## Dudas abiertas (para el responsable)

1. **Ficha de la oferta.** El plan supone que la ficha (008) no es obligatoria para evaluar. Si lo fuera, la etapa Evaluación quedaría "pendiente" hasta que las ofertas tengan ficha confirmada.
2. **Sugeridos de la matriz.** El plan no cuenta los tramos "sugeridos" como decisión pendiente (no frenan la validación). Si se quiere, se suman a la cuenta de la etapa Matriz.
3. **Columna `progress` (T-184).** Toca la cola compartida. Si el responsable prefiere no tocarla, se omite y la evaluación muestra "oferta k de N" y el tiempo.
4. **Etapa Portal opcional.** El plan la trata como opcional (un procedimiento cargado a mano nunca tiene datos del Portal). Confirmar.
