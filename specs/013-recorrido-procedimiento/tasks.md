# Tareas 013 · Recorrido del procedimiento

Plan: `specs/013-recorrido-procedimiento/plan.md`

Despliegue: pendiente

> El tablero (`docs/tablero.md`) se genera de este archivo. Al aprobarse el despliegue, la línea de arriba pasa a `Despliegue: aprobado AAAA-MM-DD`.

Estados: pendiente · en curso · en verificación · terminada · bloqueada

Dos tareas que no dependen entre sí y no comparten archivos se pueden hacer en paralelo.

Ritmo de trabajo (ADR-0024 y ADR-0025): las ramas de tarea no tocan este archivo ni el tablero; el Coordinador los actualiza una vez por lote. La verificación de cada tarea queda en `specs/013-recorrido-procedimiento/verificacion/T-NNN.md`. Corte vertical primero; toda medición escribe antes su umbral (en el plan) y tiene como máximo dos rondas.

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-179 | Corte vertical: módulo `journey`, página de recorrido del caso chico con la etapa Evaluación en vivo (sondeo cada 5 s), roles, entrada mínima y las otras cinco etapas como lugares reservados | REQ-065, REQ-066, REQ-067, REQ-068, REQ-069 | — | pendiente |
| T-180 | Etapas Portal, Pliego y circulares, y Matriz: estado, pendientes y enlaces | REQ-066, REQ-068, REQ-069 | T-179 | pendiente |
| T-181 | Etapa Ofertas: documentos, fichas, estado, pendientes y enlaces | REQ-066, REQ-068, REQ-069 | T-179 | pendiente |
| T-182 | Etapa Matriz de evaluación: pares por decidir, preguntas abiertas, ok del informe técnico y enlaces | REQ-066, REQ-068, REQ-069 | T-179 | pendiente |
| T-183 | Entrada completa: procedimientos con etapa actual y pendientes; alta explorando primero el Portal y la carga a mano como complemento (REQ-071) | REQ-065 | T-179 | pendiente |
| T-184 | Avance fino de los pedidos: columna `progress` en la cola y aviso desde la evaluación y la ficha (aprobada por el responsable, ADR-0045) | REQ-067 | T-179 | pendiente |
| T-187 | Ventana del proceso: panel en vivo con los pasos del pedido en curso, en lenguaje llano (REQ-070) | REQ-070, REQ-067 | T-184 | pendiente |
| T-188 | Aplicar la guía visual aprobada (docs/diseno/guia-visual.md, tokens.css): encabezado, recorrido, tablas y estados con íconos de color y nombre al pasar el mouse | REQ-066, REQ-068 | T-179 | pendiente |
| T-189 | Hoja de compliance por oferta: subirla una vez, rige para todos los requisitos externos de la oferta (reevaluación automática citándola), acceso en la matriz de evaluación (REQ-073) | REQ-073, REQ-063 | T-179 | pendiente |
| T-190 | Informe técnico del área: subirlo (por procedimiento u oferta), el sistema propone apto/no apto por oferta y renglón con cita del informe y la Comisión da el ok (REQ-074) | REQ-074, REQ-061 | T-189 | pendiente |
| T-191 | Recorrido: cuentas y accesos de hojas de compliance e informes técnicos que faltan en la etapa de evaluación (REQ-073, REQ-074) | REQ-073, REQ-074 | T-182, T-189, T-190 | pendiente |
| T-185 | Los cinco momentos y los roles con el caso chico: 30 de 30 celdas y enlaces de las seis etapas | REQ-066, REQ-068, REQ-069 | T-180, T-181, T-182 | pendiente |
| T-186 | Comprobación con el caso-00 desde cero (Coordinador y testeador): cinco momentos, avance en vivo y carga en menos de 2 s | REQ-065, REQ-066, REQ-067, REQ-068, REQ-069 | T-183, T-184, T-185 | pendiente |

## Paralelismo

- **T-179 va sola.** Es el corte vertical y fija lo que las demás comparten: crea el módulo `evaluon/journey/`, el tipo `Stage`, la lista de etapas con **seis archivos de etapa** (Evaluación completa, las otras cinco como lugares reservados que devuelven "pendiente"), `progress.py`, las vistas, la plantilla, el script y las rutas. También es la única que toca `settings.py` (`INSTALLED_APPS`), `evaluon/urls.py` y `base.html`. Después de T-179 ninguna tarea toca esos archivos.
- **T-180, T-181, T-182, T-183 y T-184 a la vez**, después de T-179, porque no comparten archivos: T-180 reemplaza `stages/portal.py`, `stages/pliego.py` y `stages/matriz.py`; T-181, `stages/ofertas.py`; T-182, `stages/matriz_evaluacion.py`; T-183, `views/index.py` y `templates/journey/index.html`; T-184, la cola y los dos manejadores largos, más `progress.py`. Cada una trae su propio archivo de tests en `tests/journey/`.
- **T-184 toca el esquema** (la columna de `tenders_job`) y `jobs.py`, `evaluate.py` y `sheets.py`: ninguna otra tarea de esta feature los toca, y no corre a la vez que otra feature que los modifique. Es la única de la 013 que toca el esquema. Es opcional: si el responsable decide omitirla, T-186 se mide con el avance "oferta k de N".
- **T-185 espera a T-180, T-181 y T-182**: prueba las seis etapas juntas con los servicios reales. Solo agrega tests y los datos del caso chico.
- **T-186 usa el equipo y, si se hace con modelo real, la GPU**: va sola, después de integrar todo. Nunca dos mediciones a la vez.
- Las ramas de tarea no tocan `tasks.md` ni el tablero (ADR-0025).

## Detalle

### T-187 · Ventana del proceso

- **Requisitos:** REQ-070, REQ-067
- **Nivel de verificación:** plena.
- **Qué hay que hacer:** ver plan, "Enmienda 2026-10-07". Panel en la página de recorrido con los últimos pasos del pedido en curso (qué documento lee, qué requisito evalúa, qué decidió una regla), lo hecho y lo que falta; se actualiza con el sondeo de T-179. En lenguaje llano, sin datos técnicos. Tests con un pedido simulado.
- **No tocar:** la lógica de las etapas.


### T-179 · Corte vertical: página de recorrido con la etapa Evaluación en vivo

- **Requisitos:** REQ-065, REQ-066, REQ-067, REQ-068, REQ-069
- **Nivel de verificación:** plena (lo nuevo es el módulo entero; toca roles y el menú de todas las pantallas).
- **Qué hay que hacer:**
  1. Crear la app `evaluon/journey/` (sin modelos ni migraciones) y registrarla en `INSTALLED_APPS`. Rutas bajo `recorrido/` (`journey:index`, `journey:procedure`, `journey:stages`; ver el plan, "Rutas") y una entrada "Recorrido" en el menú de `base.html`, delante de "Procedimientos". La raíz (consulta) no cambia.
  2. `stages/base.py`: el tipo `Stage` (campos del plan), las constantes de estado (`pendiente`, `en_curso`, `a_decidir`, `lista`, `con_error`) con sus etiquetas, y los ayudantes de pedidos: el pedido activo de unos tipos, el último pedido de unos tipos y si lo superó un resultado posterior. `stages/__init__.py`: `STAGES` (las seis, en orden) y `stages_for(user, procedure)`, que exige el rol de la Comisión (`require_commission_role`, operador como mínimo, con el nombre de la operación para el registro del rechazo) y devuelve las seis etapas más la etapa actual y la suma de pendientes.
  3. `stages/evaluacion.py` **completa** con las reglas del plan (pendiente sin matriz validada, ofertas con documentos o evaluación; en curso con el pedido `evaluate_offers`; con error con su motivo; lista cuando cada oferta con documentos tiene una evaluación de la versión validada vigente). Los otros cinco archivos (`portal.py`, `pliego.py`, `matriz.py`, `ofertas.py`, `matriz_evaluacion.py`) existen con `compute()` que devuelve la etapa con estado "pendiente" y una nota "todavía no calculada", para que T-180, T-181 y T-182 los reemplacen sin tocar nada más.
  4. `progress.py`: `progress_of(job)` según el plan, "Avance en vivo" (oferta k de N para `evaluate_offers`, última pasada para `propose_matrix`, tiempo transcurrido para los demás). Sin columna nueva.
  5. Vistas `views/procedure.py` (página con las seis etapas, cuenta de pendientes y el aviso) y `views/stages.py` (solo el bloque, que devuelve el HTML de las etapas sin pasar por el aviso de fin de `base.html`). Plantillas `templates/journey/procedure.html` y `_stages.html`. El rol: `decide_url` solo si `commission_role` es evaluador; "Ir a decidir" solo se muestra con `decide_url`.
  6. `static/journey/recorrido.js` y `recorrido.css`: sondeo cada 5000 ms con `fetch` al bloque, reemplazo del contenido, pausa con la pestaña oculta, mensaje si falla la respuesta, y la región `role="status"` que avisa "La etapa X terminó" o "falló: motivo" cuando una etapa deja de estar en curso. Sin librerías ni direcciones externas.
  7. `views/index.py` mínimo: lista de procedimientos con enlace a su recorrido (T-183 lo completa).
  8. Datos de prueba: un procedimiento chico inventado con matriz validada y dos ofertas (partir de `tests/assessment/data/caso-chico/`), y un pedido de evaluación simulado: en espera, en curso con 1 de 2 ofertas hechas, terminado y fallido.
- **Umbral:** el del plan: REQ-067 (cada 5 s, 0 recargas, cambio visible en 10 s o menos, motivo de la falla visible, 100 % de los casos probados) y sin direcciones externas; REQ-069 (operador 0 acciones de decisión). Máximo dos rondas.
- **Archivos:** `evaluon/journey/__init__.py`, `apps.py`, `urls.py`, `progress.py`, `stages/__init__.py`, `stages/base.py`, `stages/portal.py`, `stages/pliego.py`, `stages/matriz.py`, `stages/ofertas.py`, `stages/evaluacion.py`, `stages/matriz_evaluacion.py`, `views/__init__.py`, `views/index.py`, `views/procedure.py`, `views/stages.py`; `evaluon/templates/journey/procedure.html`, `_stages.html`; `evaluon/static/journey/recorrido.js`, `recorrido.css`; `evaluon/settings.py` (una línea); `evaluon/urls.py` (una línea); `evaluon/templates/base.html` (una línea); `tests/journey/__init__.py`, `conftest.py`, `test_evaluation_stage.py`, `test_live_block.py`, `test_roles_cut.py`, `test_no_external.py`.
- **Verificación:** `docker compose run --rm app pytest tests/journey` y la suite completa una vez al final. Tests de: estado de la etapa Evaluación en cuatro situaciones (sin matriz validada, en espera, en curso con 1 de 2, terminada, fallida con motivo); el bloque cambia de "en curso" a "lista" cuando el pedido termina, sin recargar la página completa (se prueba la vista del bloque y que el script tiene intervalo de 5000 ms y no recarga la página); el operador no recibe `decide_url` y el evaluador sí; 403 sin rol de la Comisión con su rechazo registrado; el bloque no marca avisos como vistos; el script y las plantillas no contienen `http://` ni `https://`. Prueba manual con el caso chico en el navegador (mirar y anotar en la verificación).
- **No tocar:** las pantallas y servicios de `tenders`, `portal`, `offers` y `assessment` (solo se leen), la cola, el esquema, los otros cinco archivos de etapa más allá del lugar reservado.

### T-180 · Etapas Portal, Pliego y circulares, y Matriz

- **Requisitos:** REQ-066, REQ-068, REQ-069
- **Nivel de verificación:** plena (lógica del estado de tres etapas).
- **Qué hacer:** reemplazar `compute()` de `stages/portal.py`, `stages/pliego.py` y `stages/matriz.py` con las reglas del plan ("Las etapas y cómo se calcula cada estado").
  1. **Portal:** enlaces del procedimiento (`PortalLink.procedure`), pedidos `portal_explore` y `portal_review` por `target_id` de esos enlaces, ítems `propuesto` de la última propuesta como pendientes; opcional si no hay enlace. Enlaces a `portal:proposal` o `portal:imported`.
  2. **Pliego y circulares:** documentos del pliego y su lectura (`read_document`); pendiente sin documentos; lista cuando todos tienen lectura; con error si el último pedido de un documento falló. Enlace a `tenders:procedure`.
  3. **Matriz:** pedido `propose_matrix`, última versión no descartada; borrador con requisitos `propuesto` y tramos pendientes sin resolver como cuenta; validada es lista. Enlace a `tenders:matrix`; `decide_url` solo para el evaluador.
- **Archivos:** `evaluon/journey/stages/portal.py`, `pliego.py`, `matriz.py`; `tests/journey/test_stage_portal.py`, `test_stage_pliego.py`, `test_stage_matriz.py`.
- **Verificación:** `pytest tests/journey` en verde. Un test por regla de estado y por etapa (pendiente, en curso, con error con motivo, a decidir con su cuenta, lista, y Portal opcional sin enlace); el enlace de cada etapa resuelve; el operador no recibe `decide_url`.
- **No tocar:** `stages/base.py`, `stages/__init__.py`, las demás etapas, las vistas, las plantillas, el script, las pantallas de las otras features. Si falta un ayudante en `base.py`, se detiene y lo informa.

### T-181 · Etapa Ofertas

- **Requisitos:** REQ-066, REQ-068, REQ-069
- **Nivel de verificación:** plena (lógica del estado).
- **Qué hacer:** reemplazar `compute()` de `stages/ofertas.py`: pedidos `read_offer_document` y `build_sheet` (por `target_id` = documento u oferta del procedimiento), pendiente sin ofertas, en curso, con error y su motivo, a decidir con las filas de la última ficha de cada oferta en estado `propuesto`, lista con todos los documentos leídos y ninguna fila propuesta. La ficha no frena la etapa Evaluación (plan, supuestos). Enlaces a `offers:procedure_offers` y, para las fichas con pendientes, a `offers:sheet`.
- **Archivos:** `evaluon/journey/stages/ofertas.py`; `tests/journey/test_stage_ofertas.py`.
- **Verificación:** `pytest tests/journey` en verde; tests de cada estado, de la cuenta de filas por oferta y de los enlaces; operador sin `decide_url`.
- **No tocar:** `stages/base.py`, `stages/__init__.py`, las demás etapas, vistas, plantillas, script, pantallas de `offers`.

### T-182 · Etapa Matriz de evaluación

- **Requisitos:** REQ-066, REQ-068, REQ-069
- **Nivel de verificación:** plena (lógica del estado y de los roles).
- **Qué hacer:** reemplazar `compute()` de `stages/matriz_evaluacion.py` reutilizando `assessment.services.matrix.matrix_page` (pares `propuesto`, preguntas sin respuesta, `technical` pendiente del ok del informe técnico; no se redefine "vigente" ni el estado de un par). Pendiente sin evaluaciones; a decidir con la suma de los tres conteos y el detalle de cada uno; lista sin pendientes. Enlaces a `assessment:matrix` y `assessment:questions`; `decide_url` solo para el evaluador (y de ahí el ok del informe técnico, que ya exige evaluador en su servicio).
- **Archivos:** `evaluon/journey/stages/matriz_evaluacion.py`; `tests/journey/test_stage_matriz_evaluacion.py`.
- **Verificación:** `pytest tests/journey` en verde; tests de los tres tipos de pendiente por separado y juntos, de "lista" cuando todos están decididos, de que la etapa no cambia el estado de ningún par, y de roles. Anotar el tiempo de la etapa con el caso chico en la verificación.
- **No tocar:** `stages/base.py`, `stages/__init__.py`, las demás etapas, vistas, plantillas, script, `evaluon/assessment/`.

### T-183 · Entrada completa

- **Requisitos:** REQ-065
- **Nivel de verificación:** plena (pantalla nueva con alta que escribe vía otras vistas).
- **Qué hacer:** completar `views/index.py` y `templates/journey/index.html`: una fila por procedimiento (número, objeto, etapa actual con su estado, pendientes del procedimiento y enlace al recorrido), los más recientes primero; formulario "Pegar enlace del Portal" que envía por POST a `portal:links` (campo `url`) y, al lado, el enlace "Cargar a mano" a `tenders:procedures`. Un procedimiento sin etapas calculadas todavía se muestra como "pendiente".
- **Archivos:** `evaluon/journey/views/index.py`; `evaluon/templates/journey/index.html`; `tests/journey/test_index.py`.
- **Verificación:** `pytest tests/journey` en verde. Tests: con tres procedimientos en etapas distintas, la entrada muestra cada etapa actual y su cuenta; el formulario apunta a `portal:links`; un enlace inválido vuelve con el motivo del Portal; sin rol de la Comisión, 403.
- **No tocar:** `portal`, `tenders`, `stages/`, `views/procedure.py`, `views/stages.py`, el script.

### T-184 · Avance fino de los pedidos (opcional, ADR-0045)

- **Requisitos:** REQ-067
- **Nivel de verificación:** plena (esquema de la cola compartida y manejadores largos).
- **Qué hacer:** sumar a `tenders_job` la columna `progress` (JSON, por omisión `{}`) con su migración; en `jobs.py`, `report(job, step, done, total)`, que la actualiza con una escritura aparte (`update`, fuera de la transacción del manejador) y nunca hace fallar al pedido; llamarla desde `assessment/services/evaluate.py` por requisito leído y por contraste (`_read_pair`, `_contrast_pair`) y desde `offers/services/sheets.py` por requisito de la ficha. `progress_of` usa la columna cuando tiene datos y, si está vacía, el cálculo del corte. La columna no se registra como hecho de auditoría.
- **Archivos:** `evaluon/tenders/models.py`; `evaluon/tenders/migrations/NNNN_job_progress.py`; `evaluon/tenders/jobs.py`; `evaluon/assessment/services/evaluate.py`; `evaluon/offers/services/sheets.py`; `evaluon/journey/progress.py`; `tests/tenders/test_jobs_progress.py`; `tests/journey/test_progress.py`.
- **Verificación:** `pytest tests/tenders tests/assessment tests/offers tests/journey` y la suite completa una vez al final. Tests: `report` escribe y sobrevive a una falla posterior del pedido; una falla al escribir el avance no hace fallar el pedido; la evaluación con modelo simulado informa requisito x de y; los resultados de la evaluación y de la ficha no cambian (los tests existentes siguen en verde); `progress_of` cae al cálculo del corte con la columna vacía.
- **No tocar:** la lógica de evaluación y de la ficha (solo se agrega la llamada), las pantallas, las demás etapas, `settings.py`.
- **Entorno:** corre sola entre las tareas que tocan `tenders/models.py` o la cola.

### T-185 · Los cinco momentos y los roles con el caso chico

- **Requisitos:** REQ-066, REQ-068, REQ-069
- **Nivel de verificación:** plena (verificación del criterio de aceptación).
- **Umbral (escrito antes):** 30 de 30 celdas (5 momentos por 6 etapas), seis enlaces que responden 200 al evaluador, 0 acciones de decisión del operador. Máximo dos rondas.
- **Qué hacer:** con el caso chico inventado y los servicios reales (modelo simulado donde haga falta, sin GPU), recorrer los cinco momentos de REQ-066 en este orden: antes de importar (procedimiento vacío), importado (procedimiento, pliego y ofertas cargados), matriz propuesta (borrador con propuestos), matriz validada, evaluación terminada (con pares propuestos). En cada momento comprobar el estado y la cuenta de las seis etapas contra una tabla esperada escrita en el test. Comprobar los enlaces de las seis etapas con pendientes (evaluador) y que el operador no recibe ninguna acción de decisión.
- **Archivos:** `tests/journey/test_moments.py`, `tests/journey/test_roles.py`, `tests/journey/data/momentos-esperados.yaml`; `specs/013-recorrido-procedimiento/verificacion/T-185.md` (lo deja el testeador).
- **Verificación:** `pytest tests/journey` en verde y la tabla esperada con los 30 valores correctos. Cualquier diferencia es un hallazgo de la etapa correspondiente: se corrige en una sola tarea de ajuste y se vuelve a correr (una ronda).
- **No tocar:** el código del módulo salvo en una tarea de ajuste aparte; el caso-00.

### T-186 · Comprobación con el caso-00 desde cero (Coordinador y testeador)

- **Requisitos:** REQ-065, REQ-066, REQ-067, REQ-068, REQ-069
- **Nivel de verificación:** plena; sin cambios de código salvo los hallazgos.
- **Umbral (escrito antes):** los cinco momentos con el estado correcto en las seis etapas (30 de 30); carga de la página de recorrido en menos de 2 s (mediana de 5 cargas); el avance se actualiza solo cada 5 s y, al terminar la evaluación, la etapa pasa a "a decidir" en 10 s o menos sin recargar; operador sin acciones de decisión. Máximo dos rondas.
- **Qué hacer:** cargar el caso-00 desde cero en una instancia de demostración (instancia aparte o la real: decisión de operación del Coordinador) siguiendo el orden de los cinco momentos; mirar la página en cada uno con un usuario evaluador y uno operador; correr la evaluación de una oferta y mirar el avance en el navegador, anotando los tiempos; medir cinco cargas de la página. Al repositorio solo van cifras y el resultado (`specs/013-recorrido-procedimiento/verificacion/T-186.md`); ningún dato del caso-00 (P4).
- **Archivos:** `specs/013-recorrido-procedimiento/verificacion/T-186.md`.
- **Verificación:** el informe con la tabla de los cinco momentos, los tiempos de carga y de actualización y el resultado frente al umbral. Lo que no llegue pasa con su impacto a "Revisión con el primer producto".
- **No tocar:** código de producto (los hallazgos van a una tarea aparte).
- **Entorno:** usa la GPU si la evaluación se corre con el modelo real: de a una.
