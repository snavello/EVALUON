# Tareas 012 · Importación asistida desde el Portal de Compras

Plan: `specs/012-portal-compras/plan.md`

Despliegue: pendiente

> El tablero (`docs/tablero.md`) se genera de este archivo. Al aprobarse el despliegue, la línea de arriba pasa a `Despliegue: aprobado AAAA-MM-DD`.

Estados: pendiente · en curso · en verificación · terminada · bloqueada

Dos tareas que no dependen entre sí y no comparten archivos se pueden hacer en paralelo.

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-138 | Preparar el esquema, la conexión acotada y la cola del Portal: tablas de `portal`, cambios de `tenders_job` y de auditoría, servicio `portal_worker`, cliente HTTP con lista de destinos y `entorno.md` | REQ-045, REQ-049 | — | terminada |
| T-139 | Preparar los casos para probar: páginas reales del caso-00 y de un proceso con circulares (fuera del repositorio), calcos con datos inventados y lista esperada (Coordinador) | REQ-046, REQ-047, REQ-050 | — | terminada |
| T-140 | Leer la página pública del proceso: datos básicos, renglones, cronograma, garantías y lista de documentos, con el texto normalizado | REQ-046 | T-138, T-139 | terminada |
| T-141 | Corte vertical: registrar el enlace, explorar, proponer, aprobar ítem por ítem y cargar el procedimiento y los renglones, con pantalla | REQ-045, REQ-046, REQ-048, REQ-049 | T-138, T-140 | terminada |
| T-142 | Importar los documentos: bajar el pliego, circulares y demás con su huella y cargarlos por `load_document` | REQ-046, REQ-048, REQ-049, REQ-051 | T-141 | terminada |
| T-143 | Importar las ofertas: acta de apertura y cuadro comparativo, ofertas con garantía y cotización por renglón | REQ-047, REQ-048, REQ-049, REQ-051 | T-141 | terminada |
| T-144 | Revisión periódica: una vez por día hábil y a demanda, con novedades y sin repetir lo decidido | REQ-050, REQ-048 | T-142, T-143 | terminada |
| T-145 | Medir con el caso-00 y el proceso con circulares, corregir una ronda y dejar la medición | REQ-045, REQ-046, REQ-047, REQ-048, REQ-049, REQ-050, REQ-051 | T-144 | terminada |

## Paralelismo

- T-138 y T-139 se hacen a la vez: no comparten archivos (T-139 es del Coordinador y no toca el código).
- T-142 y T-143 se hacen a la vez después de T-141: cada una agrega sus propios archivos (lector, `importers/<tipo>.py`, parcial de pantalla, tests y datos); el descubrimiento de tipos de ítem por nombre de archivo (T-141) evita que las dos toquen un registro común. Ninguna toca el esquema: lo dejó completo T-138.
- Todo lo que toca el esquema o la configuración compartida (`settings.py`, `docker-compose.yml`, migraciones, `jobs.py`) está en T-138. Si una tarea posterior necesita cambiarlo, se encadena y no corre en paralelo con otra que lo toque.
- Las mediciones se corren de a una; esta no usa GPU.
- Las ramas de tarea no tocan `tasks.md` ni el tablero (ADR-0025).

## Detalle

### T-138 · Preparar el esquema, la conexión acotada y la cola del Portal

- **Requisitos:** REQ-045, REQ-049
- **Nivel de verificación:** plena (esquema, cola compartida, conexión a internet: P4).
- **Qué hay que hacer:**
  1. Crear `evaluon/portal/` (app, `models.py`, una migración) con todas las tablas del plan: `portal_link`, `portal_page`, `portal_file`, `portal_proposal`, `portal_item`, `portal_procedure_data`, `portal_line`, `portal_offer_data`, `portal_quote`, con sus restricciones y los triggers de solo inserción de página y archivo y de contenido del ítem.
  2. `tenders_job`: tipos `portal_explore` y `portal_review`; `procedure` admite nulo solo para esos dos tipos; esos dos tipos exigen `target_id`.
  3. `audit_event.event_type`: `portal_link`, `portal_explore`, `portal_review`, `portal_decision` (migración de la restricción) y en `audit/models.py`.
  4. `jobs.claim`, `run_next` y `fail_interrupted` con parámetro de tipos a atender (o excluir); `procesar_pedidos` excluye los del Portal; comando `procesar_portal` (bucle con `--hasta-vaciar`, como `procesar_pedidos`; en esta tarea solo atiende pedidos, sin revisión diaria); `HANDLERS` con los dos tipos apuntando a funciones que se crean en T-141.
  5. `settings.py`: `PORTAL_ALLOWED_HOSTS`, `PORTAL_TIMEOUT_SECONDS`, `PORTAL_MAX_BYTES`, `PORTAL_PAUSE_SECONDS`, `PORTAL_REVIEW_HOUR`; `.env.example`.
  6. `docker-compose.yml`: red `egress`, servicio `portal_worker` (ADR-0031); `tests/test_compose_env.py` y un test nuevo que comprueba que solo `portal_worker` usa `egress` y que `internal` sigue interna.
  7. `evaluon/portal/client.py`: GET y envío de formulario de ASP.NET (con los campos ocultos de la página y la misma sesión de cookies), solo HTTPS al puerto 443 de los hosts permitidos, redirecciones verificadas a mano, tope de tamaño y de espera, pausa entre solicitudes. Recibe el transporte por parámetro para probarlo sin red.
  8. `specs/012-portal-compras/entorno.md`: la red, la lista de destinos, cómo comprobarlo y cómo cortar la conexión (insumo del runbook).
- **Archivos:** `evaluon/portal/__init__.py`, `apps.py`, `models.py`, `migrations/0001_initial.py`, `client.py`, `management/commands/procesar_portal.py`; `evaluon/tenders/models.py`, `evaluon/tenders/jobs.py`, `evaluon/tenders/management/commands/procesar_pedidos.py` y su migración; `evaluon/audit/models.py` y su migración; `evaluon/settings.py`; `docker-compose.yml`; `.env.example`; `tests/portal/` (`conftest.py`, `test_schema.py`, `test_client.py`, `test_queue.py`, `test_network.py`); `tests/test_compose_env.py`; `specs/012-portal-compras/entorno.md`.
- **Verificación:** `docker compose run --rm app pytest tests/portal tests/tenders tests/test_compose_env.py` en verde y la suite completa una vez al final. Tests: un host fuera de la lista, HTTP, otro puerto y una redirección a otro host se rechazan antes de conectar; el envío de formulario arma los campos ocultos; `claim` por tipo no toma pedidos del otro consumidor y `fail_interrupted` no toca los del otro; la restricción de `procedure` nulo; solo `portal_worker` en `egress`; triggers.
- **No tocar:** lectura de páginas, pantallas, `offers/`, `register_procedure` y demás servicios.

### T-139 · Preparar los casos para probar (Coordinador)

- **Requisitos:** REQ-046, REQ-047, REQ-050
- **Nivel de verificación:** revisión del Coordinador; sin código de producto.
- **Qué hay que hacer:**
  1. Guardar las páginas reales del caso-00 (A0PC000000-0004-LPU25) en `corpus/casos/caso-00/portal/`, fuera del repositorio: página del proceso, acta, dictamen, cuadro comparativo, las respuestas de los envíos de formulario y los documentos, con su fecha de consulta. Guardar también las de un segundo proceso público con circulares, y el host real del Portal.
  2. Preparar los **calcos** en `tests/portal/data/portal-chico/`: mismas estructura HTML, mismos campos ocultos y mismos problemas de codificación, con CUIT, razones sociales y nombres de personas inventados; 6 renglones, 3 ofertas y 18 pares de cotización; una segunda versión de la página con una circular agregada (para la revisión periódica); documentos de ejemplo inventados con su huella.
  3. Escribir `corpus/casos/caso-00/esperado/portal-esperado.yaml` (datos del procedimiento, renglones, documentos, ofertas con total y garantía, pares oferta y renglón), con huella y visto bueno; y el equivalente para el calco, que sí va al repositorio.
  4. Revisar los calcos y el repositorio para comprobar que no queda ningún dato real (P4).
- **Archivos:** `corpus/casos/caso-00/portal/` y `esperado/` (fuera del repositorio); `tests/portal/data/portal-chico/`.
- **Verificación:** revisión del Coordinador de que el calco no contiene datos reales y reproduce la estructura de la página real.
- **No tocar:** código de `evaluon/`.

### T-140 · Leer la página pública del proceso

- **Requisitos:** REQ-046
- **Nivel de verificación:** plena (lógica de lectura y datos).
- **Qué hay que hacer:**
- **Aviso de tareas anteriores:** T-139: el texto acentuado llega roto en los datos (`¿¿` por letra, `&#191;&#191;`, `è` por `é`) y no se recupera: mostrarlo marcado; desescapar entidades antes de comparar; `&nbsp` sin punto y coma en el expediente; pasar a bs4 texto ya decodificado como UTF-8. Las circulares se abren por GET a VistaPreviaCircularCiudadano.aspx?qs=<id> (onclick VerCircularCiudadano). El Pliego de Bases y Condiciones Generales y su disposición dan pantalla de error.
  1. `parsing/texto.py`: decodificación y normalización (ADR-0032). Primero comprobar con los bytes reales guardados (`corpus/casos/caso-00/portal/`, solo localmente) si el daño es de decodificación (recuperable) o ya viene en los bytes; anotar el hallazgo en `specs/012-portal-compras/plan.md`, sección "Riesgos". Los campos con `¿¿` o `�` se marcan, no se adivinan.
  2. `parsing/pagina.py`: función pura sobre bytes que devuelve datos básicos (número, expediente, objeto, tipo, encuadre legal, fecha de autorización), renglones con cantidad, cronograma, garantías, y la lista de documentos con su nombre, su número GDE si lo trae, su URL directa o los campos del envío de formulario, y la URL del acta y del dictamen. Si falta un dato obligatorio, lo informa en lugar de inventarlo.
  3. Si la fecha de autorización no está en la página, informar de dónde sale y dejar el campo pendiente para quien aprueba (se anota para el responsable).
- **Archivos:** `evaluon/portal/parsing/__init__.py`, `texto.py`, `pagina.py`; `tests/portal/test_parsing_pagina.py`, `test_texto.py`.
- **Verificación:** `docker compose run --rm app pytest tests/portal/test_parsing_pagina.py tests/portal/test_texto.py`: sobre el calco, el 100 % de los datos, los 6 renglones con su cantidad y todos los documentos; el texto dañado queda marcado; pasa una página con una sección faltante sin romper el resto. Corrida local, sin subir nada, contra la página real del caso-00: mismos resultados contra `portal-esperado.yaml`.
- **No tocar:** `client.py`, esquema, servicios.

### T-141 · Corte vertical: del enlace al procedimiento cargado

- **Requisitos:** REQ-045, REQ-046, REQ-048, REQ-049
- **Nivel de verificación:** plena.
- **Qué hay que hacer:**
- **Aviso de tareas anteriores:** T-139: la fecha de autorización no figura en la página; proponer como candidata la fecha de vinculación de "Autorización llamado" y que la apruebe quien carga. T-138: crear `evaluon.portal.services.explore.run_explore` y `run_review` (hoy los pedidos del Portal fallan por falta del módulo); los avisos de fin usan `job.procedure.number` y un pedido del Portal no tiene procedimiento. Aviso menor: no hay test de reversión de las migraciones.
  1. `services/links.py`: `register_link` (rol, validación del enlace contra la lista de destinos, explicación del rechazo, hecho `portal_link`), `stop_following`.
  2. `services/explore.py`: manejador de `portal_explore` (y de `portal_review`, que lo reutiliza): baja la página con el cliente, la guarda, la lee con `parsing/pagina.py` y arma la propuesta y sus ítems; descubre los tipos de ítem por los archivos de `importers/` (`KIND`, `explore`, `load`) y sus anomalías; hecho `portal_explore`.
  3. `importers/procedure.py`: ítems `procedimiento` (crear o asociar al procedimiento ya registrado con ese número) y `renglones`; su carga llama a `register_procedure` y guarda `portal_procedure_data` y `portal_line`.
  4. `services/approval.py`: `decide` (roles por tipo de ítem, orden de dependencias, carga en la misma transacción, `fallido` con motivo, hecho `portal_decision` por ítem) y "aprobar todo".
  5. Pantalla: "Importar desde el Portal" y "Propuesta" (ítems con su origen y su marca de texto dañado, aprobar o rechazar por ítem y todo), con un parcial por tipo de ítem en `templates/portal/items/`; aviso de fin de pedido.
  6. Prueba de punta a punta con el calco y un `FakePortal` (sin red): enlace, exploración, propuesta, aprobar una parte y rechazar otra, procedimiento y renglones cargados, nada cargado sin aprobación.
- **Archivos:** `evaluon/portal/services/links.py`, `explore.py`, `approval.py`; `evaluon/portal/importers/__init__.py`, `procedure.py`; `evaluon/portal/views/`, `urls.py`; `evaluon/urls.py` (una línea); `evaluon/templates/portal/` (incluye `items/procedimiento.html`, `items/renglones.html`); `tests/portal/test_links.py`, `test_explore.py`, `test_approval.py`, `test_flow.py` y `fakeportal.py`.
- **Verificación:** `docker compose run --rm app pytest tests/portal` en verde; suite completa una vez al final. Umbral del caso chico (100 % de datos del procedimiento, 6 de 6 renglones, nada cargado sin aprobación, ambas decisiones con autor y fecha, el operador no aprueba el procedimiento).
- **No tocar:** esquema y configuración compartida (T-138), `parsing/` salvo un error hallado (se informa), `tenders/` y `offers/`.

### T-142 · Importar los documentos

- **Requisitos:** REQ-046, REQ-048, REQ-049, REQ-051
- **Nivel de verificación:** plena.
- **Qué hay que hacer:**
  1. `parsing/documentos.py` (si T-140 no dejó todo en `pagina.py`): lista de documentos y su clasificación (pliego, anexo, circular, acto administrativo, acta, dictamen).
  2. `importers/documents.py`: bajar cada documento (GET de URL directa o envío de formulario de ASP.NET), guardarlo en `portal_file` con su huella, y proponer un ítem `documento` por cada uno con el nombre, el tipo, la fecha y su origen. Pliego, anexo y circulares: la carga llama a `load_document` de la 003 (queda encolada su lectura); acto, acta y dictamen: quedan como archivo del Portal con su origen y son descargables desde la pantalla de importación (decisión del plan, punto 1).
  3. Circulares: el tipo (modificatoria o aclaratoria) y la fecha son obligatorios; si el Portal no lo dice, el ítem pide elegirlo y no se aprueba sin él.
  4. Un documento que no se puede bajar o que no es PDF ni web guardada se informa como anomalía; queda la carga manual.
  5. El operador aprueba solo documentos; el evaluador, todos.
  6. Pantalla de lo importado con su origen (página, fecha) o "carga manual" para lo cargado a mano en el mismo procedimiento.
  7. Si el envío de formulario del pliego no funciona sin JavaScript, informar al Coordinador antes de seguir (ADR-0032).
- **Archivos:** `evaluon/portal/parsing/documentos.py`, `evaluon/portal/importers/documents.py`, `evaluon/templates/portal/items/documento.html`, `evaluon/templates/portal/imported.html`, `evaluon/portal/views/imported.py`; `tests/portal/test_documents.py` y sus datos en `tests/portal/data/portal-chico/`.
- **Verificación:** `docker compose run --rm app pytest tests/portal/test_documents.py` en verde: la huella del documento cargado coincide con el archivo bajado, el origen muestra página y fecha, un duplicado se rechaza con aviso, la lectura queda encolada, un documento cargado a mano figura "carga manual". Suite completa una vez al final.
- **No tocar:** esquema, `settings.py`, `docker-compose.yml`, `importers/offers.py`, `tenders/`.

### T-143 · Importar las ofertas

- **Requisitos:** REQ-047, REQ-048, REQ-049, REQ-051
- **Nivel de verificación:** plena.
- **Qué hay que hacer:**
- **Aviso de tareas anteriores:** T-139: el acta de apertura repite una oferta por cada garantía (mismo proveedor en dos filas con montos distintos o vacío) y tiene filas repetidas; agrupar por CUIT.
  1. `parsing/acta.py`: por oferente, CUIT, fecha de confirmación, moneda, total, tipo, forma y monto de la garantía.
  2. `parsing/cuadro.py`: oferentes, totales y el precio y la cantidad por renglón de cada oferente.
  3. `importers/offers.py`: bajar el acta y el cuadro comparativo (este último por envío de formulario), proponer un ítem `oferta` por oferente con todos sus datos y sus cotizaciones; la carga llama a `register_offer` de la 008 y guarda `portal_offer_data` y `portal_quote`. Si el acta y el cuadro difieren en un total, se informa como anomalía del ítem. Un ítem de oferta exige el procedimiento y los renglones cargados.
  4. Pantalla: parcial `items/oferta.html` con el oferente, el CUIT, el total, la garantía y la tabla de cotización.
  5. La oferta importada convive con la carga manual de sus documentos: el operador carga a mano un documento con `offers.load_document`, que queda junto a lo importado con origen "carga manual".
- **Archivos:** `evaluon/portal/parsing/acta.py`, `cuadro.py`; `evaluon/portal/importers/offers.py`; `evaluon/templates/portal/items/oferta.html`; `tests/portal/test_acta.py`, `test_cuadro.py`, `test_offers.py` y sus datos en `tests/portal/data/portal-chico/`.
- **Verificación:** `docker compose run --rm app pytest tests/portal/test_acta.py tests/portal/test_cuadro.py tests/portal/test_offers.py` en verde: las 3 ofertas con total y garantía y los 18 pares con precio y cantidad iguales a los del calco; el oferente duplicado no se carga dos veces; carga manual de un documento de la oferta importada. Suite completa una vez al final.
- **No tocar:** esquema, configuración compartida, `importers/documents.py`, `offers/`.

### T-144 · Revisión periódica

- **Requisitos:** REQ-050, REQ-048
- **Nivel de verificación:** plena (lógica).
- **Qué hay que hacer:**
- **Aviso de tareas anteriores:** T-141: un ítem que cambió en el Portal no se puede cargar después de aprobar el cambio: el pedido queda `fallido` con `IntegrityError` (`portal_line_number_unique` o `portal_procedure_data_procedure_id_key`). Pasos: aprobar procedimiento y renglones, cambiar la página, correr `portal_review` y aprobar el ítem nuevo. La carga de un cambio tiene que actualizar lo cargado (con registro P6), no crearlo de nuevo. T-142: cada `portal_review` sin novedades crea una propuesta vacía de origen `revision` solo con la anomalía repetida del pliego general (3 revisiones = 3 propuestas con 0 ítems): una anomalía ya informada no crea propuesta nueva; test de tres revisiones iguales sin propuesta nueva. T-143: anomalía cuando precio x cantidad difiere del total del renglón; test del control de CUIT repetido (mismo CUIT con nombres distintos); el esquema guarda una sola garantía por oferta (el ítem muestra todas): decidir si hace falta guardar todas. La ficha de la 008 todavía no usa la cotización del Portal para el estado "cotizado" (tarea aparte antes de la 004).
  1. `services/schedule.py`: `enqueue_due(now)` (día hábil, hora, enlace en curso, `last_review_on` distinto de hoy, sin pedido en espera) y "Revisar ahora"; `procesar_portal` lo llama en cada vuelta (reloj inyectable para los tests).
  2. La revisión reutiliza la exploración: propone solo ítems nuevos o con otra huella que la última decidida; un ítem rechazado con la misma huella no se repite; si no hay novedades no se crea propuesta; un ítem cambiado se muestra "cambiado respecto de lo aprobado".
  3. Fin del seguimiento: al decidirse el ítem del dictamen o con el botón "Dejar de seguir".
  4. Pantalla: novedades pendientes por enlace y el botón "Revisar ahora"; falla de la revisión con su motivo y aviso a quien registró el enlace, sin descartar lo ya propuesto.
  5. Ítems nuevos entran por el mismo circuito de aprobación y por los mismos servicios.
- **Archivos:** `evaluon/portal/services/schedule.py`, `explore.py` (dedupe por huella, ya iniciado en T-141), `evaluon/portal/management/commands/procesar_portal.py`, `evaluon/portal/views/links.py`, `evaluon/templates/portal/links.html`; `tests/portal/test_schedule.py`, `test_review.py` y la segunda versión del calco.
- **Verificación:** `docker compose run --rm app pytest tests/portal` en verde: día hábil, fin de semana y ya revisado hoy (reloj falso); la circular agregada aparece como novedad una sola vez y lo ya aprobado y rechazado no se repite; el botón no apila pedidos; una página ilegible deja el pedido fallido con su motivo. Suite completa una vez al final.
- **No tocar:** esquema, `docker-compose.yml`, `settings.py` (si falta un parámetro, se informa), lectores.

### T-145 · Medir con el caso-00 y el proceso con circulares

- **Requisitos:** REQ-045, REQ-046, REQ-047, REQ-048, REQ-049, REQ-050, REQ-051
- **Nivel de verificación:** plena (medición con umbral escrito en el plan, dos rondas como máximo).
- **Qué hay que hacer:**
- **Aviso de tareas anteriores:** T-140: el test contra las páginas reales solo compara el caso-00 (renglones y faltantes); en la medición comprobar también el caso-05 (4 renglones, 13 documentos, 3 circulares). La marca de daño también marca `è` en nombres propios legítimos. T-144: falta un test de que rechazar el dictamen no termina el seguimiento; un cambio de nombre u objeto del procedimiento en el Portal no llega a `tenders_procedure`: mostrarlo como anomalía visible ("el Portal cambió el nombre u objeto; el procedimiento conserva el anterior") y registrarlo (decisión del Coordinador). La suite completa tarda unos 18 minutos.
  1. `evaluation.py` y el comando `medir_portal`: reproduce la exploración con las páginas guardadas de `corpus/casos/caso-00/portal/` (sin conexión) y compara con `portal-esperado.yaml` según los umbrales del plan; carpeta de corrida (`parametros.json`, `resultados.jsonl`, `resumen.md`, `resumen-publico.md` sin datos reales), como las de la 003 y la 008. Reutiliza `tenders/evaluation.py` (carpeta de corrida, intervalos) sin rehacerlo.
  2. Una corrida base; los hallazgos se corrigen juntos, con un commit por hallazgo, y se mide una vez más (ronda 1). Solo si no llegó al umbral, una ronda más (ronda 2, la última). Lo que falte pasa, con su impacto, a la lista de revisión con el primer producto.
  3. Una pasada "en vivo" (una sola vez, con el Coordinador presente) con el enlace real para comprobar que la lectura coincide con las páginas guardadas; el resultado se anota en `verificacion/T-145.md`.
  4. Dejar en `entorno.md` los pasos para el runbook del despliegue (variables, red, cómo cortar la conexión).
- **Archivos:** `evaluon/portal/evaluation.py`, `evaluon/portal/management/commands/medir_portal.py`; `tests/portal/test_evaluation.py`; correcciones que haga falta en los lectores y servicios de la 012 (un commit por hallazgo); `specs/012-portal-compras/entorno.md`.
- **Verificación:** `medir_portal` con el caso-00 y con el proceso con circulares llega a los umbrales del plan (100 % en todos); el informe de pruebas y el resumen público quedan en la carpeta de la corrida; suite completa una vez sobre la rama combinada con main.
- **No tocar:** `tenders/` y `offers/`; esquema (si hace falta un cambio, se informa y se encadena una tarea nueva).
