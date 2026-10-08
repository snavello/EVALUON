# Tareas 014 · Aplicación por secciones

Plan: `specs/014-aplicacion-por-secciones/plan.md`

Despliegue: pendiente

> El tablero (`docs/tablero.md`) se genera de este archivo. Al aprobarse el despliegue, la línea de arriba pasa a `Despliegue: aprobado AAAA-MM-DD`.

Estados: pendiente · en curso · en verificación · terminada · bloqueada

Dos tareas que no dependen entre sí y no comparten archivos se pueden hacer en paralelo.

Ritmo de trabajo (ADR-0024 y ADR-0025): las ramas de tarea no tocan este archivo ni el tablero; el Coordinador los actualiza una vez por lote. La verificación de cada tarea queda en `specs/014-aplicacion-por-secciones/verificacion/T-NNN.md`. Corte vertical primero; toda medición escribe antes su umbral (en el plan) y tiene como máximo dos rondas.

**Compuerta de maqueta.** Ninguna tarea de interfaz arranca antes de que el responsable apruebe la maqueta corregida (`docs/diseno/mockup/index.html`). Son tareas de interfaz: T-192, T-194, T-195, T-197, T-198, T-200 a T-212 y T-214 a T-219. Pueden empezar antes (con el plan aprobado y los ADR aceptados): T-193, T-196, T-199, T-213 y T-220.

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-192 | Corte vertical: esqueleto de las cinco secciones (barra, portada con pendientes y sugerencias separados, jerarquía común, guía visual) y sección 2 con la matriz de cumplimiento en tabla agrupada, filtros, filas con cita y lista de versiones, con el caso chico | REQ-075, REQ-081, REQ-082, REQ-097, REQ-098, REQ-100 | — | terminada |
| T-193 | Esquema de la feature (una sola tarea): cambios de historial de documentos, tipos nuevos, borrador de procedimiento y de oferta, pedidos nuevos, renglones y CUIT con documento de origen, decisión de descartes, subida de normas y hechos de auditoría | REQ-077, REQ-083, REQ-087, REQ-091, REQ-092, REQ-094, REQ-099 | — | terminada |
| T-194 | Sección 1: datos del procedimiento con origen de cada dato, régimen por fecha de autorización, renglones, apertura, garantías y ofertas del Portal | REQ-078, REQ-097 | T-192 | pendiente |
| T-195 | Sección 1: explorador y cargador del Portal (pegar enlace, propuesta agrupada, aprobar ítem por ítem o todo) y novedades de la revisión periódica | REQ-076, REQ-079, REQ-097 | T-194 | pendiente |
| T-196 | Propuesta de datos y renglones desde el pliego subido: servicio, pedido en segundo plano, citas y aprobación que crea el procedimiento (sin pantalla) | REQ-077 | T-193 | pendiente |
| T-197 | Sección 1: alta subiendo el pliego (propuesta con citas; el evaluador aprueba, descarta o corrige escribiendo valor y motivo; sin alta en blanco) | REQ-077, REQ-076, REQ-097 | T-195, T-196 | pendiente |
| T-198 | Sección 2: documentos del pliego, anexos y especificaciones (lista por tipo con origen, subida de varios a la vez, tomar del Portal, faltantes) | REQ-080, REQ-097 | T-192 | pendiente |
| T-199 | Servicio de historial de documentos del pliego y de las ofertas: reemplazar, retirar, restituir, con auditoría y estado calculado (sin pantalla) | REQ-099 | T-193 | terminada |
| T-200 | Sección 2: reemplazar, retirar y restituir documentos del pliego, historial de versiones y «retirados» | REQ-099, REQ-097 | T-198, T-199 | pendiente |
| T-201 | Sección 2: acciones de la Comisión en la tabla de la matriz (confirmar, corregir, quitar, agregar, validar), versión nueva, imprimir y exportar | REQ-081, REQ-082 | T-192 | terminada |
| T-202 | Sección 3: lista de ofertas con alta a la vista (desde el Portal o subiendo archivos, con nombre y CUIT propuestos para aprobar o corregir) y documentos de cada oferta, subida múltiple | REQ-083, REQ-084, REQ-097 | T-192, T-220 | pendiente |
| T-203 | Sección 3: ficha de cada oferta (qué presentó frente a cada requisito, con el fragmento o «no se encontró en la oferta») | REQ-086 | T-192 | pendiente |
| T-204 | Sección 3: anexos técnicos dentro de la oferta y hoja de compliance por oferta con el faltante a la vista (absorbe la parte de compliance de T-191) | REQ-087, REQ-088, REQ-097 | T-192, T-193 | pendiente |
| T-205 | Sección 3: circulares y aclaraciones (Portal o subidas); una circular modificatoria abre una versión nueva de la matriz con lo cambiado marcado | REQ-085, REQ-097 | T-201 | pendiente |
| T-206 | Sección 3: reemplazar, retirar y restituir documentos de la oferta, con historial y «retirados» | REQ-099 | T-202, T-199 | pendiente |
| T-207 | Sección 4: propuesta de evaluación por oferta y requisito (cumple, no cumple, no determinado, con fundamento) y decisión de la Comisión | REQ-089, REQ-097 | T-192 | pendiente |
| T-208 | Sección 4: preguntas a la Comisión y pedidos de subsanación con su respuesta registrada | REQ-090 | T-192 | pendiente |
| T-209 | Sección 4: informe técnico del área (por procedimiento o por oferta) y ok de la Comisión (absorbe la parte de informe técnico de T-191) | REQ-089, REQ-097 | T-192 | pendiente |
| T-210 | Sección 4: descartes propuestos y orden económico; el evaluador confirma o rechaza cada descarte con quién y cuándo | REQ-091 | T-192, T-193 | pendiente |
| T-211 | Sección 4: dictamen del Portal o subido (sin borrador) | REQ-092, REQ-097 | T-192, T-193 | pendiente |
| T-212 | Sección 4: exportar la planilla por oferta (Excel) y el cuadro comparativo (Excel y PDF); suma la dependencia XlsxWriter (ADR-0050) | REQ-093 | T-192 | pendiente |
| T-213 | Propuesta de los datos de una norma desde su archivo y staging de la subida (sin pantalla) | REQ-094 | T-193 | terminada |
| T-214 | Sección 5: subir una norma, ver el informe de lectura y validarla desde la pantalla | REQ-094, REQ-097 | T-192, T-213 | pendiente |
| T-215 | Sección 5: normas que rigen al procedimiento según su fecha de autorización y cuáles faltan cargar | REQ-095, REQ-097 | T-192 | pendiente |
| T-216 | Sección 5: consulta de normativa con citas literales | REQ-096 | T-192 | pendiente |
| T-217 | Los cinco momentos y los roles con el caso chico: estados y cuentas de las cinco secciones, 25 de 25 celdas (reemplaza a T-185 de la 013) | REQ-075, REQ-097, REQ-098 | T-194, T-195, T-197, T-198, T-200, T-201, T-202, T-203, T-204, T-205, T-206, T-207, T-208, T-209, T-210, T-211, T-212, T-214, T-215, T-216, T-219 | pendiente |
| T-218 | Comprobación final con el caso chico y el caso-00 (Coordinador y testeador): 26 de 26 requisitos en pantalla, 0 datos tipeados, carga menor a 2 s y guía visual (reemplaza a T-186 de la 013) | REQ-075, REQ-076, REQ-077, REQ-078, REQ-079, REQ-080, REQ-081, REQ-082, REQ-083, REQ-084, REQ-085, REQ-086, REQ-087, REQ-088, REQ-089, REQ-090, REQ-091, REQ-092, REQ-093, REQ-094, REQ-095, REQ-096, REQ-097, REQ-098, REQ-099, REQ-100 | T-217 | pendiente |
| T-219 | Las pantallas anteriores redirigen a su sección y el menú queda con la entrada nueva | REQ-075, REQ-100 | T-195, T-197, T-198, T-201, T-202, T-207, T-208, T-214 | pendiente |
| T-220 | Propuesta de nombre y CUIT del oferente desde los archivos de una oferta: borrador, pedido en segundo plano, citas, corrección con valor y motivo y aprobación que crea la oferta (sin pantalla) | REQ-083 | T-193, T-196 | pendiente |

## Tareas de la 013 que se absorben

| Tarea de la 013 | Qué la reemplaza |
|---|---|
| T-185 | T-217 (con sus avisos: pausa del sondeo con la pestaña oculta, `Stage.suggestions`, motivo de falla con `plain_reason`, foco del ícono tras el sondeo) |
| T-186 | T-218 (con la nota de runbook: reconstruir la imagen con `docker compose build app` para servir los estáticos) |
| T-188 | T-192 (base de la guía visual) y la aplicación en cada tarea de interfaz; revisión final en T-218 |
| T-191 | T-204 (hoja de compliance que falta) y T-209 (informe técnico que falta) |

El Coordinador marca T-185, T-186, T-188 y T-191 de la 013 como «reemplazada por T-NNN de la 014» en el tablero de la 013 al aprobarse este plan.

## Paralelismo

- **T-192 va primero y casi sola.** Es el corte vertical y fija lo que todas comparten: crea `evaluon/journey/sections/` y `evaluon/journey/temas/` con **los 18 temas como módulos mínimos** (cada uno con `status()` que devuelve ceros, sus rutas vacías y su parcial vacío), los CSS por sección, la plantilla común, la portada, la barra y el registro de rutas. Es la única tarea de interfaz que toca `evaluon/urls.py`, `evaluon/templates/base.html` y `evaluon/journey/urls.py`; después de T-192 nadie los toca (salvo T-219 para redirecciones y menú).
- **T-193 puede ir a la vez que T-192** (no comparten archivos) y es **la única que toca modelos y migraciones**. Ninguna otra tarea genera migraciones. Si T-193 falta, las tareas que dependen de ella esperan.
- **Después de T-192 y T-193, cinco carriles independientes**, uno por sección; dentro de un carril, cada tarea toca solo su tema:
  - Sección 1: T-194 → T-195 → T-197 (comparten el parcial y las rutas de la sección); T-196 corre aparte, en cuanto termina T-193, y T-197 espera a las dos.
  - Sección 2: T-198 y T-201 a la vez (documentos y matriz son temas distintos, con parciales y rutas separados); T-199 aparte; T-200 espera a T-198 y T-199.
  - Sección 3: T-220 (servicio, sin pantalla, después de T-193 y T-196) antes de T-202; T-202, T-203, T-204 a la vez (temas distintos); T-205 espera a T-201 porque marca cambios en la tabla de la matriz; T-206 espera a T-202 y T-199.
  - Sección 4: T-207, T-208, T-209, T-210, T-211 y T-212 a la vez (un tema cada una).
  - Sección 5: T-213 aparte; T-214 espera a T-213; T-215 y T-216 a la vez.
- **Archivos compartidos entre tareas de distintos carriles:** `evaluon/tenders/services/documents.py` (solo T-211), `evaluon/tenders/services/matrix.py` y `evaluon/assessment/documents.py` (solo T-199), `evaluon/offers/services/offers.py` (solo T-204), `evaluon/tenders/jobs.py` (T-196 y después T-220, encadenadas), `pyproject.toml` (solo T-212). Ningún par de tareas listadas en paralelo comparte archivo.
- **Máximo sugerido en paralelo:** cinco a seis desarrolladores, uno por carril, porque el Coordinador debe revisar cada resultado contra la spec (CLAUDE.md, "Trabajo en paralelo").
- **T-219 va antes de T-217:** redirige las pantallas viejas para que la comprobación vea una sola organización.
- **T-217 y T-218 van solas, en ese orden**, después de integrar todo. T-218 usa el equipo y, si se corre una evaluación con modelo real, la GPU: nunca dos mediciones a la vez. Al repositorio solo van cifras y resultados (P4).
- Las ramas de tarea no tocan `tasks.md` ni el tablero (ADR-0025).

## Estructura común (la fija T-192)

- Secciones: `evaluon/journey/sections/__init__.py`, `base.py`, `s1.py` a `s5.py`.
- Temas (uno por tarea; cada módulo trae `status()`, vistas y `urlpatterns`): `evaluon/journey/temas/` con `s1_datos`, `s1_portal`, `s1_pliego`, `s2_documentos`, `s2_matriz`, `s3_ofertas`, `s3_ficha`, `s3_anexos`, `s3_circulares`, `s4_propuesta`, `s4_preguntas`, `s4_informe`, `s4_descartes`, `s4_dictamen`, `s4_exportar`, `s5_normas`, `s5_rigen`, `s5_consulta`.
- Parciales: `evaluon/templates/journey/temas/<tema>.html`. CSS por sección: `evaluon/static/journey/secciones.css` y `s1.css` a `s5.css`.
- Tests: `tests/journey/temas/test_<tema>.py`.
- Al nombrar «sus archivos», cada tarea de tema se refiere a su módulo, su parcial y su test, más los servicios que el detalle indica.

## Detalle

### T-192 · Corte vertical: esqueleto de las cinco secciones y matriz de la sección 2

- **Requisitos:** REQ-075, REQ-081, REQ-082, REQ-097, REQ-098, REQ-100
- **Nivel de verificación:** plena (menú de todas las pantallas, módulo nuevo, tabla de la matriz).
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:**
  1. Crear `sections` y `temas` como en "Estructura común". Los 18 temas existen desde el primer día con `status()` en cero, rutas vacías y parcial vacío, salvo `s2_matriz`, que se hace completo hasta el punto 5.
  2. Rutas bajo `expedientes/` (plan, "Rutas"); `recorrido/` redirige. Tipo `Section`/`TemaStatus` y `sections_for(user, procedure)` con `require_commission_role` (operador como mínimo) y estados con las reglas comunes de la 013 (reutilizando `journey/stages/`).
  3. Plantilla común `seccion_base.html`: título, resumen (qué hay, qué falta, de dónde vino), pendientes, sugerencias en bloque aparte, detalle y acciones al pie; barra de las cinco secciones en toda pantalla del procedimiento con estado y dos cuentas; «Subir archivo» y «Tomar del Portal» como componente reutilizable (se muestran según lo que el Portal publica).
  4. Portada `expedientes/<id>/` con las cinco secciones y los dos bloques separados (pendientes y sugerencias), la ventana del proceso de la 013 y el sondeo cada 5 s sobre la barra (`recorrido.js` reutilizado, con el foco del ícono conservado y el motivo de falla por `plain_reason`). `expedientes/` lista los procedimientos.
  5. Tema `s2_matriz`: la última versión de la matriz en **tabla agrupada por tipo** (formales, económicos, técnicos) con cabecera fija, cebra e íconos de estado con nombre al pasar el mouse; filtros («solo lo que falta decidir», por tipo, por estado); cada fila se abre con la cita del pliego; **lista de versiones** con fecha y quién validó cada una. Solo lectura en este corte: las acciones son T-201.
  6. `secciones.css` con la guía visual (`tokens.css`), sin direcciones externas; entrada «Expedientes» en el menú de `base.html`.
  7. Datos de prueba: el caso chico de la 013 con matriz de dos versiones.
- **Umbral:** el del plan (carga de la portada y de la sección 2 con el caso chico por debajo de 2 s; 0 direcciones externas). Máximo dos rondas.
- **Archivos:** `evaluon/journey/sections/*`, `evaluon/journey/temas/*` (18 módulos mínimos), `evaluon/journey/urls.py`, `evaluon/journey/views/portada.py`, `evaluon/templates/journey/seccion_base.html`, `portada.html`, `temas/*.html`, `evaluon/static/journey/secciones.css`, `s1.css` a `s5.css`, `recorrido.js` (ajustes), `evaluon/urls.py`, `evaluon/templates/base.html`, `tests/journey/test_sections.py`, `tests/journey/temas/test_s2_matriz.py`, `tests/journey/test_no_external.py` (ampliado).
- **Verificación:** `docker compose run --rm app pytest tests/journey` y la suite completa una vez al final. Tests: las cinco secciones con estado y cuentas; cualquiera se abre sin pasar por otra; sin rol de la Comisión, 403 con rechazo registrado; el filtro muestra solo esas filas, agrupadas por tipo, y cada fila abre su cita; la lista muestra las dos versiones con fecha y quién validó; pendientes y sugerencias en dos bloques; ninguna dirección externa. Revisión del Coordinador en el navegador (1280 px y 1366 × 768).
- **No tocar:** servicios y modelos de las otras apps, las pantallas viejas (siguen funcionando), el esquema.

### T-193 · Esquema de la feature

- **Requisitos:** REQ-077, REQ-087, REQ-091, REQ-092, REQ-094, REQ-099
- **Nivel de verificación:** plena (esquema, disparadores, restricciones).
- **Qué hay que hacer:** crear, en este orden y con una migración por app, lo que fija el plan en «Modelo de datos»: `tenders_document_change`, `offers_document_change`; tipos `dictamen` y `anexo_tecnico`; `tenders_procedure_draft`; `offers_offer_draft` y `offers_offer_draft_file`; tipos de pedido `propose_procedure` y `propose_offer` y ajuste de `tenders_job_procedure_required`; `portal_line`, `portal_procedure_data` y `portal_offer_data` con `item` nulo y `document`, con la restricción de «exactamente uno»; `assessment_discard_decision`; `norms_upload`; tipos de hecho de auditoría nuevos. Las tablas de hechos llevan disparador de solo inserción. Solo modelos y migraciones: ninguna lógica.
- **Archivos:** `evaluon/tenders/models.py`, `evaluon/offers/models.py`, `evaluon/portal/models.py`, `evaluon/assessment/models.py`, `evaluon/norms/models.py`, `evaluon/audit/models.py` y una migración en cada app; `tests/tenders/test_schema_014.py`, `tests/offers/test_schema_014.py`, `tests/portal/test_schema_014.py`, `tests/assessment/test_schema_014.py`, `tests/norms/test_schema_014.py`.
- **Verificación:** `pytest` de esas carpetas y la suite completa una vez; migrar desde cero y hacia atrás; tests de cada restricción y disparador (inserción permitida, `UPDATE` y `DELETE` rechazados, «exactamente uno» en renglones); los tests existentes de las apps siguen en verde.
- **No tocar:** servicios, vistas y plantillas. Corre sola entre las tareas que generan migraciones.

### T-194 · Sección 1: datos del procedimiento con origen

- **Requisitos:** REQ-078, REQ-097
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** tema `s1_datos`: número, expediente, tipo, objeto, fecha de autorización con el régimen que fija (`regime_for`, Disp. 247/2022 o 297/03), renglones con cantidad, apertura, cronograma, garantías y ofertas, y para cada dato su origen (el Portal, con el enlace, o tal archivo). `status()` con lo que falta. Lee `Procedure`, `PortalProcedureData`, `PortalLine`, `PortalGuarantee`, `PortalOfferData`; muestra el origen por documento cuando el dato venga de un pliego (T-196 lo escribe).
- **Archivos:** `evaluon/journey/temas/s1_datos.py`, `evaluon/templates/journey/temas/s1_datos.html`, `evaluon/journey/sections/s1.py`, `tests/journey/temas/test_s1_datos.py`.
- **Verificación:** `pytest tests/journey`; test con un procedimiento del Portal y con uno cargado a mano (origen distinto); la fecha del caso-00 muestra el régimen 247/2022; procedimiento sin renglones muestra lo que falta.
- **No tocar:** `portal`, `tenders` y los demás temas.

### T-195 · Sección 1: explorador y cargador del Portal

- **Requisitos:** REQ-076, REQ-079, REQ-097
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** tema `s1_portal`: pegar el enlace del proceso (usa `portal.services.links`), ver lo que encontró el sistema (datos, renglones, cronograma, garantías, documentos y ofertas) agrupado, aprobar ítem por ítem o todo (`approve_all`, con las confirmaciones de fecha y de tipo de circular que ya pide) y ver a qué sección va cada cosa (pliego a la 2, ofertas a la 3, dictamen a la 4); después de aprobar, volver a la sección de destino. Las novedades de la revisión periódica (`origin = revision`) aparecen como pendientes de la sección 1 y de la portada y no se cargan sin aprobación. «Revisar ahora» y «dejar de seguir» a la vista. El alta sin procedimiento (`expedientes/nuevo/`) muestra este mismo tema.
- **Archivos:** `evaluon/journey/temas/s1_portal.py`, `evaluon/templates/journey/temas/s1_portal.html`, `evaluon/journey/views/nuevo.py`, `evaluon/templates/journey/nuevo.html`, `evaluon/journey/sections/s1.py`, `tests/journey/temas/test_s1_portal.py`.
- **Verificación:** `pytest tests/journey tests/portal`; test del caso chico simulado: pegar el enlace, ver la propuesta agrupada, aprobar todo y encontrar datos, pliego y ofertas en su sección; novedad detectada aparece como pendiente y nada se carga; datos, renglones y ofertas los aprueba solo el evaluador; el operador aprueba solo la carga de documentos (REQ-048 de la 012); lectura no aprueba nada.
- **No tocar:** `evaluon/portal/` (se reutiliza tal cual), el tema `s1_datos`.

### T-196 · Propuesta de datos y renglones desde el pliego subido

- **Requisitos:** REQ-077
- **Nivel de verificación:** plena (lógica nueva, datos, instrucciones al modelo, auditoría). Puede empezar antes de la maqueta.
- **Qué hay que hacer:** según ADR-0049. (1) Servicio `tenders/services/procedure_proposal.py`: `upload_tender(user, data, file_name)` crea el borrador y el pedido `propose_procedure`; `run_propose_procedure(job)` lee el pliego con la lectura local, propone número, expediente, tipo, objeto y fecha de autorización con su cita (página y texto) y candidatos, y los renglones (número, descripción, cantidad) de la tabla de renglones; sin cita verificable el dato queda «no determinado» y no se propone. (2) `correct(user, draft_id, field, value, reason)`: corrige un dato o renglón propuesto con motivo obligatorio y guarda propuesto, corregido, motivo, quién y cuándo. `approve(user, draft_id, decisions)` (solo evaluador): crea el procedimiento con las funciones existentes (`register_procedure`, `load_document` como pliego) y escribe renglones y expediente en `portal_line` y `portal_procedure_data` con su documento de origen; dedupe por número y huella; deja los hechos de auditoría. (3) Registro del manejador en `tenders/jobs.py`. Umbral escrito en el plan; una medición por lote.
- **Archivos:** `evaluon/tenders/services/procedure_proposal.py`, `evaluon/tenders/proposal/procedure_fields.py`, `evaluon/tenders/jobs.py`, `tests/tenders/test_procedure_proposal.py`, `tests/tenders/data/caso-chico/` (si hace falta el pliego sintético).
- **Verificación:** `pytest tests/tenders`; el pliego del caso chico: 5 de 5 datos y renglones completos; un dato sin cita queda «no determinado»; un duplicado se rechaza; la corrección sin motivo se rechaza y con motivo conserva el valor propuesto; el operador puede subir pero no aprobar ni corregir, solo el evaluador; lectura no; el modelo simulado y el real no cambian los resultados de los tests existentes. Medición del pliego público del caso-00 (cifras al repositorio).
- **No tocar:** `register_procedure` y `load_document` más allá de llamarlos; la matriz; las pantallas.

### T-197 · Sección 1: alta subiendo el pliego

- **Requisitos:** REQ-077, REQ-076, REQ-097
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** tema `s1_pliego`: «Subir el pliego» (en `expedientes/nuevo/` y en la sección 1); mientras se lee, muestra el avance; al terminar, la propuesta con cada dato, su cita y su estado, y los renglones; el evaluador aprueba todo o ítem por ítem, descarta un renglón o **corrige un dato o renglón propuesto escribiendo el valor y el motivo (obligatorio)**; el operador sube el pliego y ve la propuesta sin botones de aprobar ni corregir. **No hay alta en blanco: sin propuesta no hay nada que escribir.** Al aprobar, abre el procedimiento recién creado en la sección 1.
- **Archivos:** `evaluon/journey/temas/s1_pliego.py`, `evaluon/templates/journey/temas/s1_pliego.html`, `evaluon/journey/sections/s1.py`, `tests/journey/temas/test_s1_pliego.py`.
- **Verificación:** `pytest tests/journey`; test de que no existe ruta ni formulario de alta en blanco y de que corregir exige motivo y registra quién y cuándo; flujo con el pliego del caso chico: subir, ver la propuesta con citas, aprobar y ver el procedimiento con su origen; pliego sin datos reconocibles muestra «no determinado» y no crea nada.
- **No tocar:** el servicio de T-196; los temas `s1_datos` y `s1_portal` (solo se enlazan).

### T-198 · Sección 2: documentos del pliego

- **Requisitos:** REQ-080, REQ-097
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** tema `s2_documentos`: lista de pliego, anexos, especificaciones técnicas y circulares vigentes por tipo, con su origen y estado de lectura; **subir varios archivos a la vez** (cada uno con su tipo y fecha cuando el tipo la exige; se reutiliza `load_document` por archivo, con el resultado por archivo); «Tomar del Portal» lleva a los ítems de documentos del Portal. Procedimiento sin pliego muestra los dos accesos y lo que falta.
- **Archivos:** `evaluon/journey/temas/s2_documentos.py`, `evaluon/templates/journey/temas/s2_documentos.html`, `evaluon/journey/sections/s2.py`, `tests/journey/temas/test_s2_documentos.py`.
- **Verificación:** `pytest tests/journey`; sin pliego aparecen «Subir archivo» y «Tomar del Portal»; subir tres documentos juntos deja los tres (y el repetido se rechaza con su motivo sin frenar a los otros).
- **No tocar:** `tenders/services/documents.py`, las pantallas viejas.

### T-199 · Servicio de historial de documentos

- **Requisitos:** REQ-099
- **Nivel de verificación:** plena (lógica, datos, auditoría). Puede empezar antes de la maqueta.
- **Qué hay que hacer:** según ADR-0048, para pliego y ofertas: `replace(user, document, data, file_name, note)`, `withdraw(user, document, note)`, `restore(user, document)`, `history(document)`, `current_documents(owner)` y `withdrawn_documents(owner)`. Reemplazar crea el documento nuevo (con la carga existente) y el cambio; retirar y restituir solo agregan un cambio; nada se modifica ni se borra. Los documentos retirados o reemplazados dejan de usarse en la propuesta de la matriz (`base_documents`) y en la evaluación (`assessment/documents.py`). Una versión de matriz validada no cambia: se deja la marca «armada con un documento retirado» para que la sección 2 la muestre. Cada operación deja el hecho `document_change`.
- **Archivos:** `evaluon/tenders/services/document_history.py`, `evaluon/offers/services/document_history.py`, `evaluon/tenders/services/matrix.py`, `evaluon/assessment/documents.py`, `tests/tenders/test_document_history.py`, `tests/offers/test_document_history.py`.
- **Verificación:** `pytest tests/tenders tests/offers tests/assessment`; reemplazo deja anterior y nueva con quién y cuándo; retirado sale de lo vigente y aparece en retirados; restituir lo devuelve; la matriz validada no cambia; los tests existentes siguen en verde.
- **No tocar:** modelos y migraciones (T-193), vistas y plantillas.

### T-200 · Sección 2: historial de documentos del pliego

- **Requisitos:** REQ-099, REQ-097
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** en el tema `s2_documentos`, acciones «Reemplazar», «Retirar» (con nota) y «Restituir» por documento; historial de versiones de cada documento; bloque «retirados»; aviso de matriz armada con un documento retirado.
- **Archivos:** `evaluon/journey/temas/s2_documentos.py`, `evaluon/templates/journey/temas/s2_documentos.html`, `tests/journey/temas/test_s2_documentos_history.py`.
- **Verificación:** `pytest tests/journey`; un documento reemplazado muestra la versión anterior y la nueva; uno retirado aparece en «retirados»; restituirlo lo devuelve; operador puede, lectura no.
- **No tocar:** `document_history.py`.

### T-201 · Sección 2: acciones de la matriz

- **Requisitos:** REQ-081, REQ-082
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** en el tema `s2_matriz`, desde cada fila: confirmar, corregir, quitar, agregar (formal, económico y fila técnica) y validar la versión (solo el evaluador), con las rutas POST existentes de `tenders` y regreso a la sección; abrir versión nueva; imprimir y exportar PDF (reutiliza `export`); filas descartadas y cobertura enlazadas. Sugerencias en bloque aparte.
- **Archivos:** `evaluon/journey/temas/s2_matriz.py`, `evaluon/templates/journey/temas/s2_matriz.html`, `tests/journey/temas/test_s2_matriz_actions.py`.
- **Verificación:** `pytest tests/journey tests/tenders`; cada acción desde la fila deja el mismo hecho y el mismo cambio que la pantalla vieja; el operador no ve «validar»; imprimir y PDF responden 200.
- **No tocar:** `evaluon/tenders/` (se reutiliza).

### T-202 · Sección 3: ofertas

- **Requisitos:** REQ-083, REQ-084, REQ-097
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** tema `s3_ofertas`: cuadro de ofertas con oferente, estado de lectura, ficha y faltantes; **botón de alta visible sin abrir nada**: desde el Portal (acta de apertura con oferente, CUIT, total, garantía y precio por renglón, ítems de oferta) o subiendo los archivos de la oferta: el sistema propone nombre y CUIT con su cita (servicio de T-220) y el evaluador los aprueba o corrige escribiendo valor y motivo; el operador sube y ve la propuesta sin botones de aprobar ni corregir; documentos de cada oferta con subida de varios a la vez (`load_document` por archivo).
- **Archivos:** `evaluon/journey/temas/s3_ofertas.py`, `evaluon/templates/journey/temas/s3_ofertas.html`, `evaluon/journey/sections/s3.py`, `tests/journey/temas/test_s3_ofertas.py`.
- **Verificación:** `pytest tests/journey tests/offers`; el botón de alta está en la página; tres archivos juntos quedan en la oferta; oferta importada del acta muestra su origen; subir los archivos de una oferta muestra nombre y CUIT propuestos con su cita; el evaluador corrige con motivo y el operador no ve el botón.
- **No tocar:** `evaluon/offers/` (se reutiliza).

### T-203 · Sección 3: ficha de la oferta

- **Requisitos:** REQ-086
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** tema `s3_ficha`: por oferta, qué presentó frente a cada requisito de la matriz con el fragmento que lo respalda, o «no se encontró en la oferta»; armar la ficha, confirmar filas y agregar o quitar fragmentos con las rutas existentes de `offers:*`. La ficha es opcional: no cuenta como faltante, sus filas propuestas cuentan como pendientes.
- **Archivos:** `evaluon/journey/temas/s3_ficha.py`, `evaluon/templates/journey/temas/s3_ficha.html`, `tests/journey/temas/test_s3_ficha.py`.
- **Verificación:** `pytest tests/journey tests/offers`; con una oferta leída cada requisito muestra lo presentado y el fragmento o «no se encontró»; las filas propuestas suman a los pendientes.
- **No tocar:** `evaluon/offers/`.

### T-204 · Sección 3: anexos técnicos y hoja de compliance

- **Requisitos:** REQ-087, REQ-088, REQ-097
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** tema `s3_anexos`: dentro de cada oferta, «Subir anexo técnico» (fichas y folletos del oferente; documento de tipo `anexo_tecnico`, fijado por la acción, como la hoja de compliance) y «Subir hoja de compliance» una vez por oferta (usa `assessment.services.compliance`); una oferta sin hoja figura como faltante con su botón y suma a las cuentas de la sección y de la portada (absorbe la parte de compliance de T-191). Se agrega el parámetro de tipo a `load_document`.
- **Archivos:** `evaluon/journey/temas/s3_anexos.py`, `evaluon/templates/journey/temas/s3_anexos.html`, `evaluon/offers/services/offers.py`, `tests/journey/temas/test_s3_anexos.py`, `tests/offers/test_anexo_tecnico.py`.
- **Verificación:** `pytest tests/journey tests/offers tests/assessment`; la ficha técnica subida figura como anexo técnico de esa oferta; la oferta sin hoja figura como faltante y la sube desde el botón; la clasificación por reglas no pisa el tipo fijado.
- **No tocar:** el resto de `offers/services` y `assessment/services/compliance.py`.

### T-205 · Sección 3: circulares y aclaraciones

- **Requisitos:** REQ-085, REQ-097
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** tema `s3_circulares`: lista de circulares modificatorias, aclaratorias y respuestas a consultas, tomadas del Portal o subidas (con fecha y tipo). Primero relevar cómo `tenders/proposal/circulars.py` y `circular_changes.py` aplican una circular y dejarlo escrito en la verificación. Al cargar una modificatoria se abre una versión nueva de la matriz de la sección 2 (`open_new_version` más el pedido que incorpora la circular, según el relevamiento) con lo cambiado marcado, que la Comisión valida de nuevo. La circular sin matriz nueva validada cuenta como pendiente. En la tabla de la sección 2 se marca lo cambiado.
- **Archivos:** `evaluon/journey/temas/s3_circulares.py`, `evaluon/templates/journey/temas/s3_circulares.html`, `evaluon/tenders/services/circular_version.py`, `evaluon/journey/temas/s2_matriz.py` (solo la marca de cambiado), `evaluon/templates/journey/temas/s2_matriz.html` (ídem), `tests/journey/temas/test_s3_circulares.py`, `tests/tenders/test_circular_version.py`.
- **Verificación:** `pytest tests/journey tests/tenders`; una circular que cambia un requisito produce una versión nueva en borrador con ese requisito marcado como cambiado; la versión anterior no cambia; no se valida sola; una aclaratoria no abre versión.
- **No tocar:** `tenders/proposal/`; las acciones de la matriz (T-201).

### T-206 · Sección 3: historial de documentos de la oferta

- **Requisitos:** REQ-099
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** en el tema `s3_ofertas`, «Reemplazar», «Retirar» (con nota) y «Restituir» por documento de la oferta, historial y «retirados»; aviso de evaluación hecha con un documento retirado (se pide evaluar de nuevo; no se recalcula sola).
- **Archivos:** `evaluon/journey/temas/s3_ofertas.py`, `evaluon/templates/journey/temas/s3_ofertas.html`, `tests/journey/temas/test_s3_ofertas_history.py`.
- **Verificación:** `pytest tests/journey`; documento reemplazado muestra la anterior y la nueva; retirado figura en «retirados»; el aviso de evaluación aparece.
- **No tocar:** `offers/services/document_history.py`.

### T-207 · Sección 4: propuesta de evaluación

- **Requisitos:** REQ-089, REQ-097
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** tema `s4_propuesta`: «Evaluar todas las ofertas», avance, y la matriz de evaluación por oferta y requisito (cumple, no cumple, no determinado) con su fundamento; confirmar, corregir o rechazar un resultado (evaluador) con las rutas existentes de `assessment:*`; historial del par. Reutiliza `matrix_page`; no redefine «vigente» ni el estado de un par.
- **Archivos:** `evaluon/journey/temas/s4_propuesta.py`, `evaluon/templates/journey/temas/s4_propuesta.html`, `evaluon/journey/sections/s4.py`, `tests/journey/temas/test_s4_propuesta.py`.
- **Verificación:** `pytest tests/journey tests/assessment`; con el caso evaluado se ve la propuesta por oferta y requisito; el operador no ve las acciones de decisión; el tiempo de la sección con el caso chico queda anotado.
- **No tocar:** `evaluon/assessment/`.

### T-208 · Sección 4: preguntas y subsanación

- **Requisitos:** REQ-090
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** tema `s4_preguntas`: preguntas a la Comisión abiertas (entre los pendientes, con acceso para responder) y respondidas, con quién y cuándo; pedidos de subsanación y documento agregado, con las rutas existentes.
- **Archivos:** `evaluon/journey/temas/s4_preguntas.py`, `evaluon/templates/journey/temas/s4_preguntas.html`, `tests/journey/temas/test_s4_preguntas.py`.
- **Verificación:** `pytest tests/journey tests/assessment`; pregunta abierta figura entre los pendientes con su acceso; la respuesta queda con quién y cuándo.
- **No tocar:** `evaluon/assessment/`.

### T-209 · Sección 4: informe técnico del área

- **Requisitos:** REQ-089, REQ-097
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** tema `s4_informe`: subir el informe técnico por procedimiento o por oferta (`technical_report`), pedir que el sistema proponga apto o no apto con cita del informe y dar el ok (evaluador); ofertas con filas técnicas sin informe figuran como faltante con su botón (absorbe la parte de informe técnico de T-191).
- **Archivos:** `evaluon/journey/temas/s4_informe.py`, `evaluon/templates/journey/temas/s4_informe.html`, `tests/journey/temas/test_s4_informe.py`.
- **Verificación:** `pytest tests/journey tests/assessment`; el informe se sube desde la sección; la oferta sin informe figura como faltante; el ok exige evaluador.
- **No tocar:** `evaluon/assessment/`.

### T-210 · Sección 4: descartes y orden económico

- **Requisitos:** REQ-091
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** tema `s4_descartes`: descartes propuestos (`propose_discards`) con sus motivos y fundamentos, y el orden económico total y por renglón (`economic_order`); el evaluador confirma o rechaza cada descarte (nota opcional) y queda `assessment_discard_decision` con quién y cuándo y el hecho `discard_decision`; si se evalúa de nuevo, el descarte vuelve a quedar sin decidir. El operador ve el estado y no el botón. Servicio nuevo en `assessment/services/discards.py`. Los descartes sin decisión son pendientes de la sección.
- **Archivos:** `evaluon/assessment/services/discards.py`, `evaluon/journey/temas/s4_descartes.py`, `evaluon/templates/journey/temas/s4_descartes.html`, `tests/assessment/test_discard_decisions.py`, `tests/journey/temas/test_s4_descartes.py`.
- **Verificación:** `pytest tests/assessment tests/journey`; el evaluador confirma y queda registrado con quién y cuándo; rechazar también; el operador no ve el botón y la ruta lo rechaza con registro; una evaluación nueva reinicia el estado; `propose_discards` y `economic_order` no cambian.
- **No tocar:** `assessment/ordering.py` y el resto de servicios de evaluación.

### T-211 · Sección 4: dictamen

- **Requisitos:** REQ-092, REQ-097
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** tema `s4_dictamen`: dictamen del Portal (archivo importado de clase dictamen) o subido (documento de tipo `dictamen`, que no se lee); «Tomar del Portal» y «Subir archivo»; **sin acción «generar borrador»**. Ajuste en `load_document` para que un documento de tipo dictamen no encole lectura.
- **Archivos:** `evaluon/journey/temas/s4_dictamen.py`, `evaluon/templates/journey/temas/s4_dictamen.html`, `evaluon/tenders/services/documents.py`, `tests/journey/temas/test_s4_dictamen.py`, `tests/tenders/test_dictamen_document.py`.
- **Verificación:** `pytest tests/journey tests/tenders`; un dictamen publicado en el Portal aparece al aprobar su carga; uno subido no encola lectura; no existe ruta ni botón de borrador; la matriz no lo toma como documento base.
- **No tocar:** el resto de `documents.py`.

### T-212 · Sección 4: exportaciones

- **Requisitos:** REQ-093
- **No arranca sin la maqueta aprobada.** ADR-0050 aceptado antes de empezar (incluida la dependencia nueva).
- **Qué hay que hacer:** tema `s4_exportar`: la planilla por oferta en Excel (un libro con una hoja por oferta: cada requisito con resultado, fundamento, decisión de la Comisión, descartes y su decisión) y el cuadro comparativo (ofertas por requisito, orden económico) en Excel y en PDF; Excel con XlsxWriter (agregar a `pyproject.toml` con versión exacta, verificando antes versión actual, licencia y compatibilidad con la versión de Python de la imagen, y reconstruir la imagen) y PDF con `weasyprint`; el hecho `eval_export` con qué se exportó y de qué evaluación; rotulado como propuesta de evaluación donde corresponda.
- **Archivos:** `pyproject.toml` (y el archivo de versiones fijadas si existe), `evaluon/assessment/services/export.py`, `evaluon/journey/temas/s4_exportar.py`, `evaluon/templates/journey/temas/s4_exportar.html`, `tests/assessment/test_export.py`, `tests/journey/temas/test_s4_exportar.py`.
- **Verificación:** `pytest tests/assessment tests/journey`; con el caso evaluado se obtienen el Excel de la planilla y del cuadro con el 100 % de ofertas y requisitos (se reabre el `.xlsx` en el test) y el PDF del cuadro; queda el hecho de auditoría; la imagen se reconstruye sin internet en uso.
- **No tocar:** `assessment/ordering.py`.

### T-213 · Propuesta de los datos de una norma desde su archivo

- **Requisitos:** REQ-094
- **Nivel de verificación:** plena (lógica nueva, datos, cita normativa). Puede empezar antes de la maqueta.
- **Qué hay que hacer:** según ADR-0051. `norms/services/upload.py`: `stage(user, data, file_name)` guarda el archivo en `norms_upload`, lo lee con la lectura existente y propone categoría, tipo, número, año, emisor, título, cita, fecha de publicación y vigencia, cada uno con su evidencia (página y texto); lo no reconocido queda marcado. `correct(user, upload_id, field, value, reason)` corrige o completa un dato con motivo obligatorio (queda el valor propuesto, el corregido, el motivo, quién y cuándo). `confirm(user, upload_id)` llama a `load_norm` con los datos confirmados y deja `norm_upload`. Sin IA.
- **Archivos:** `evaluon/norms/services/upload.py`, `evaluon/norms/splitting/header_fields.py`, `tests/norms/test_upload_proposal.py`.
- **Verificación:** `pytest tests/norms`; umbral del plan (8 de 10 datos en 5 normas públicas del corpus); lo no reconocido queda marcado; confirmar crea la norma igual que el comando; archivo repetido se rechaza como hoy.
- **No tocar:** `loading.py` más allá de llamarlo; `validation.py`.

### T-214 · Sección 5: subir, leer y validar normas

- **Requisitos:** REQ-094, REQ-097
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** tema `s5_normas`: lista de normas cargadas con su estado y versión (`list_norms`); «Subir norma» (archivo); datos propuestos con su evidencia, para confirmar; informe de lectura (`reading_report`, `reading_summary`) y «Validar» (evaluador, `validate_reading`) sin comandos; modificatorias sin cargar (`PendingAmendment`) como faltantes. Corregir un dato propuesto se hace escribiendo el valor y el motivo. Comprueba el rol de la Comisión (evaluador) y el de normativa y, si falta uno, dice cuál. No se cambia el modelo de permisos; el runbook de la tarea (`specs/014-aplicacion-por-secciones/runbook-normas.md`) documenta que los evaluadores se crean con los dos roles (`crear_usuario` y `rol_comision`).
- **Archivos:** `evaluon/journey/temas/s5_normas.py`, `evaluon/templates/journey/temas/s5_normas.html`, `evaluon/journey/sections/s5.py`, `tests/journey/temas/test_s5_normas.py`, `specs/014-aplicacion-por-secciones/runbook-normas.md`.
- **Verificación:** `pytest tests/journey tests/norms`; subir el archivo de una norma muestra su informe de lectura y el evaluador la valida; el operador no ve «Validar»; el resultado es el mismo que con los comandos.
- **No tocar:** `evaluon/norms/services/` (se reutiliza), los comandos.

### T-215 · Sección 5: normas que rigen

- **Requisitos:** REQ-095, REQ-097
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** tema `s5_rigen`: según la fecha de autorización, las normas que rigen al procedimiento (`applicable_regimes`) con su versión, y cuáles faltan cargar: la norma del régimen que fija la fecha si no está, el marco nacional, las modificatorias registradas sin cargar y las normas que cita el pliego y no están cargadas; cada faltante con «Subir norma».
- **Archivos:** `evaluon/journey/temas/s5_rigen.py`, `evaluon/templates/journey/temas/s5_rigen.html`, `tests/journey/temas/test_s5_rigen.py`.
- **Verificación:** `pytest tests/journey tests/queries`; el caso-00 (Disp. 247/2022) muestra las normas que lo rigen y las que faltan; un procedimiento anterior muestra la 297/03.
- **No tocar:** `queries/services.py` (solo se llama `applicable_regimes`).

### T-216 · Sección 5: consulta con citas

- **Requisitos:** REQ-096
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** tema `s5_consulta`: la consulta de normativa existente dentro de la sección, con la fecha de autorización del procedimiento ya cargada, respuesta con citas literales y su parte, y el historial de consultas. La consulta global (`queries:screen`) sigue disponible.
- **Archivos:** `evaluon/journey/temas/s5_consulta.py`, `evaluon/templates/journey/temas/s5_consulta.html`, `tests/journey/temas/test_s5_consulta.py`.
- **Verificación:** `pytest tests/journey tests/queries`; la consulta responde con citas literales y su parte; el modelo simulado no cambia los resultados de los tests de `queries`.
- **No tocar:** `evaluon/queries/`.

### T-220 · Propuesta de nombre y CUIT del oferente desde los archivos de una oferta

- **Requisitos:** REQ-083
- **Nivel de verificación:** plena (lógica nueva, datos, instrucciones al modelo, auditoría). Puede empezar antes de la maqueta.
- **Qué hay que hacer:** (1) Servicio `offers/services/offer_proposal.py`: `upload_offer_files(user, procedure, files)` crea el borrador de oferta con sus archivos y el pedido `propose_offer`; `run_propose_offer(job)` lee los archivos con la lectura local de ofertas y propone nombre y CUIT, cada uno con su cita (documento, página y texto): el CUIT por regla (formato y dígito verificador), el nombre por regla y, si no alcanza, con el modelo local pidiendo cita literal verificada contra el texto; sin cita verificable queda «no determinado». (2) `correct(user, draft_id, field, value, reason)`: corrige lo propuesto con motivo obligatorio y guarda propuesto, corregido, motivo, quién y cuándo. (3) `approve(user, draft_id)` (solo evaluador): crea la oferta con `register_offer`, carga los archivos con `load_document`, guarda el CUIT en `portal_offer_data` con su documento de origen y deja `offer_proposal` y `offer_register`; rechaza oferente repetido. (4) Registro del manejador en `tenders/jobs.py`.
- **Umbral:** el del plan (caso chico 2 de 2 datos por oferta con cita; ofertas públicas del caso-00: 90 % de CUIT y 80 % de nombre correctos). Una medición por lote; máximo dos rondas.
- **Archivos:** `evaluon/offers/services/offer_proposal.py`, `evaluon/offers/proposal_fields.py`, `evaluon/tenders/jobs.py` (solo el registro del manejador; T-196 toca el mismo archivo, por eso T-220 depende de T-196), `tests/offers/test_offer_proposal.py`.
- **Verificación:** `pytest tests/offers`; ofertas del caso chico con nombre y CUIT propuestos y citados; dato sin cita queda «no determinado»; corrección sin motivo rechazada y con motivo conserva el valor propuesto; operador sube pero no aprueba ni corrige; oferente repetido rechazado; los tests existentes de `offers` siguen en verde.
- **No tocar:** `register_offer` y `load_document` más allá de llamarlos; las pantallas.

### T-217 · Los cinco momentos y los roles con el caso chico

- **Requisitos:** REQ-075, REQ-097, REQ-098
- **Nivel de verificación:** plena (criterio de aceptación).
- **Umbral (escrito antes):** 25 de 25 celdas (5 momentos por 5 secciones), cada sección con su estado y sus cuentas correctas, 0 acciones de decisión del operador, y los accesos «Subir archivo» o «Tomar del Portal» presentes donde corresponde. Máximo dos rondas.
- **Qué hay que hacer:** con el caso chico inventado y los servicios reales (modelo simulado, sin GPU), recorrer los cinco momentos: antes de importar, importado, matriz propuesta, matriz validada, evaluación terminada con pares propuestos. En cada uno comprobar estado y cuentas de las cinco secciones contra una tabla escrita en el test. Traer los avisos de la 013: pausa del sondeo con la pestaña oculta, `Stage.suggestions`, motivo de falla con `plain_reason`, foco del ícono tras el sondeo.
- **Archivos:** `tests/journey/test_moments.py`, `tests/journey/test_roles.py`, `tests/journey/data/momentos-esperados.yaml`, `specs/014-aplicacion-por-secciones/verificacion/T-217.md` (lo deja el testeador).
- **Verificación:** `pytest tests/journey` en verde y la tabla con los 25 valores correctos. Cualquier diferencia es un hallazgo del tema correspondiente: una sola tarea de ajuste y se vuelve a correr.
- **No tocar:** el código del módulo salvo en una tarea de ajuste aparte; el caso-00.

### T-218 · Comprobación final con el caso chico y el caso-00 (Coordinador y testeador)

- **Requisitos:** REQ-075 a REQ-100
- **Nivel de verificación:** plena; sin cambios de código salvo los hallazgos.
- **Umbral (escrito antes):** 26 de 26 requisitos comprobados en pantalla con el caso chico y con el caso-00; 0 datos o renglones tipeados en el alta (Portal y pliego subido); cada pantalla carga en menos de 2 s (mediana de 5 cargas, portada y cinco secciones); la guía visual y la jerarquía común en el 100 % de las pantallas revisadas en el navegador (1280 px y 1366 × 768). Máximo dos rondas.
- **Qué hay que hacer:** cargar el caso-00 desde cero en una instancia de demostración siguiendo los escenarios de la spec; recorrer cada criterio de aceptación con un usuario evaluador y uno operador; medir cinco cargas de cada pantalla; el Coordinador revisa cada pantalla en el navegador contra la guía visual. Contrastar las decisiones literales del plan («Control de decisiones») contra el código. Al repositorio solo van cifras y resultado (P4). El runbook de la 013 debe decir que hay que reconstruir la imagen (`docker compose build app`) para servir los estáticos.
- **Archivos:** `specs/014-aplicacion-por-secciones/verificacion/T-218.md`.
- **Verificación:** el informe con los 26 requisitos, los tiempos de carga y el resultado frente al umbral. Lo que no llegue pasa con su impacto a «Revisión con el primer producto».
- **No tocar:** código de producto (los hallazgos van a una tarea aparte).
- **Entorno:** usa la GPU si se corre una evaluación con el modelo real: de a una.

### T-219 · Las pantallas anteriores redirigen a su sección

- **Requisitos:** REQ-075, REQ-100
- **No arranca sin la maqueta aprobada.**
- **Qué hay que hacer:** las páginas de lectura `tenders:procedures`, `tenders:procedure`, `tenders:matrix`, `offers:procedure_offers`, `offers:offer`, `assessment:matrix`, `assessment:questions`, `portal:links`, `portal:proposal`, `journey:index` y `journey:procedure` redirigen a la sección que corresponde; las rutas de acción (POST) y de descarga de originales se conservan. El menú queda con «Consulta» (global), «Expedientes» y «Normas». Sin pantallas duplicadas.
- **Archivos:** `evaluon/tenders/views/documents.py`, `evaluon/tenders/views/procedures.py`, `evaluon/tenders/views/matrix.py`, `evaluon/offers/views/documents.py`, `evaluon/assessment/views/matrix.py`, `evaluon/assessment/views/questions.py`, `evaluon/portal/views/links.py`, `evaluon/portal/views/proposal.py`, `evaluon/journey/views/index.py`, `evaluon/journey/views/procedure.py`, `evaluon/templates/base.html`, `tests/journey/test_redirects.py` y los tests existentes de esas vistas que cambien a propósito.
- **Verificación:** `pytest` de las apps tocadas y la suite completa una vez; cada página vieja redirige y cada acción POST sigue funcionando y vuelve a su sección; los tests de servicios no cambian.
- **No tocar:** servicios, modelos y los temas.
