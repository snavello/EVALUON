# Plan 014 · Aplicación por secciones

Estado: aprobado · Fecha: 2026-10-07 · Aprobó: responsable del proyecto (2026-10-07 21:20, «ok avanza», junto con la maqueta)

Spec: `specs/014-aplicacion-por-secciones/spec.md` (aprobada el 2026-10-07)

ADR de este plan, **propuestos**: `docs/adr/0048-historial-de-documentos-sin-borrar.md`, `docs/adr/0049-alta-del-procedimiento-desde-el-pliego-subido.md`, `docs/adr/0050-formato-de-las-exportaciones-de-la-evaluacion.md` y `docs/adr/0051-carga-de-normas-subiendo-solo-el-archivo.md`. Se apoya en 0045 (estado calculado y sondeo), 0046 (jerarquía común, guía visual, íconos) y 0047 (cinco secciones).

## Resumen del enfoque

Las funciones ya existen de punta a punta; esta feature es sobre todo **reorganizar la interfaz** en las cinco secciones del ADR-0047 y sumar las pocas acciones que faltan. Lo que se reutiliza sin cambios de lógica: el Portal (explorar, proponer, aprobar, revisar), la lectura de pliegos y ofertas, la matriz de cumplimiento (versiones, revisión, validación), la ficha de la oferta, la hoja de compliance, el informe técnico, la evaluación asistida, las preguntas, el descarte propuesto y el orden económico, la carga y validación de normas (servicios) y la consulta con citas.

El módulo `evaluon/journey/` (feature 013) pasa de "seis etapas en orden" a "cinco secciones sin orden". No se crea otra aplicación: se reutilizan los cálculos de estado de las seis etapas (`journey/stages/`) como insumo de las secciones y se agrega una capa de **temas**: cada tema es una pieza chica de una sección (por ejemplo, "matriz" dentro de la sección 2) con su vista, sus rutas, su parcial de plantilla y su función `status()` (pendientes, sugerencias y qué falta). Las secciones suman los `status()` de sus temas. Así cada tarea posterior a la primera toca solo los archivos de su tema, y varias pueden hacerse a la vez.

Las pantallas viejas (`tenders:procedure`, `offers:procedure_offers`, `assessment:matrix`, `journey:procedure`, `portal:proposal`) dejan de ser el camino principal: sus acciones (POST) se conservan como puntos de entrada y vuelven a la sección; sus páginas de lectura redirigen a la sección que corresponde al final (T-219), para no duplicar pantallas.

Lo nuevo de verdad, según el relevamiento verificado en el código:

| Falta hoy | Dónde se resuelve |
|---|---|
| Alta del procedimiento desde el pliego subido, con datos y renglones propuestos (`register_procedure` pide los cuatro datos tipeados; los renglones solo existen si vienen del Portal) | T-193 (modelo), T-196 (servicio), T-197 (pantalla); ADR-0049 |
| Subir varios documentos del pliego a la vez (hoy `DocumentForm` sube uno; las ofertas ya suben varios) | T-198 |
| Alta de una oferta sin Portal con nombre y CUIT del oferente propuestos leyendo sus archivos (hoy `register_offer` pide el nombre tipeado y el CUIT solo existe si viene del acta) | T-193 (modelo), T-220 (servicio), T-202 (pantalla) |
| Corregir un dato propuesto escribiendo el valor y el motivo, con registro de quién y cuándo (hoy no existe en el alta de procedimiento, de oferta ni de norma) | T-196, T-197, T-213, T-214, T-220, T-202 |
| Reemplazar, retirar y restituir documentos con historial (hoy no hay ninguna de las tres) | T-193, T-199, T-200, T-206; ADR-0048 |
| Matriz como tabla agrupada con filtros y lista de versiones (hoy es una página de tarjetas con `<details>`, sin tabla ni filtros ni lista de versiones) | T-192 |
| Confirmar o rechazar descartes (hoy el descarte solo se propone y se muestra) | T-193, T-210 |
| Carga, informe de lectura y validación de normas por pantalla (hoy solo comandos de `norms/management/commands/`; la única vista de `norms/` entrega el original) | T-193, T-213, T-214; ADR-0051 |
| Exportar la planilla por oferta y el cuadro comparativo (hoy solo la matriz de cumplimiento se imprime y baja en PDF) | T-212; ADR-0050 |
| Pantalla de normas que rigen al procedimiento (hoy `applicable_regimes` solo se usa dentro de la consulta) | T-215 |
| Anexos técnicos de la oferta como tipo propio, y dictamen subido como documento | T-193, T-204, T-211 |

## Condición previa: maqueta aprobada

**Ninguna tarea de interfaz arranca antes de que el responsable apruebe la maqueta corregida** (`docs/diseno/mockup/index.html`, que se rehace con las cinco secciones en otra rama). Es una compuerta humana (P11) y se cumple así:

- Las tareas de interfaz llevan en su detalle la línea "No arranca sin la maqueta aprobada". Son: T-192, T-194, T-195, T-197, T-198, T-200 a T-212, T-214 a T-219.
- Pueden empezar antes, una vez aprobado este plan y aceptados los ADR, las tareas sin pantalla: T-193 (esquema), T-196 (servicio de propuesta desde el pliego), T-199 (servicio de historial), T-213 (propuesta de datos de una norma) y T-220 (propuesta de nombre y CUIT desde los archivos de una oferta).
- Si la maqueta aprobada cambia la estructura de una sección, el Coordinador ajusta antes de lanzar la tarea de esa sección; este plan no define la disposición visual, solo qué contiene cada sección.

## Criterio de aceptación numérico y umbrales (escritos antes de medir)

| Qué | Umbral | Con qué se mide | Tarea |
|---|---|---|---|
| Requisitos comprobados en pantalla | 26 de 26 (REQ-075 a REQ-100) con el caso chico y con el caso-00 | Lista de comprobación en `verificacion/T-218.md` | T-218 |
| Datos o renglones tipeados desde cero en el alta | 0, desde el Portal, desde el pliego subido y desde los archivos de una oferta (solo se corrige lo propuesto, con motivo obligatorio) | Revisión de los formularios de alta (test: ningún campo en blanco de datos ni renglones; la corrección sin motivo se rechaza) y prueba en el navegador | T-197, T-202, T-218 |
| Propuesta de nombre y CUIT desde los archivos de una oferta | caso chico: 2 de 2 datos por oferta, con cita; pliego/ofertas públicos del caso-00: al menos 90 % de ofertas con CUIT correcto y 80 % con nombre correcto; sin cita verificable queda «no determinado» | `tests/offers/test_offer_proposal.py` y medición local | T-220 |
| Carga de cada pantalla | menos de 2 s, mediana de 5 cargas con el caso-00, en el equipo, para portada y las cinco secciones | Medición local; al repositorio solo cifras | T-218 |
| Propuesta de datos desde el pliego (ADR-0049) | caso chico: 5 de 5 datos y 100 % de renglones con número, descripción y cantidad; pliego público del caso-00: al menos 4 de 5 datos y 90 % de renglones | `tests/tenders/test_procedure_proposal.py` y medición local | T-196 |
| Propuesta de datos de una norma (ADR-0051) | al menos 8 de 10 datos correctos en 5 normas públicas del corpus; lo que no reconoce queda marcado para confirmar | `tests/norms/test_upload_proposal.py` | T-213 |
| Estados y cuentas | 25 de 25 celdas (5 momentos por 5 secciones) y operador con 0 acciones de decisión | `tests/journey/test_moments.py` con el caso chico | T-217 |
| Historial de documentos | 100 % de los reemplazos y retiros dejan versión anterior, quién y cuándo; 0 borrados | `tests/tenders/test_document_history.py`, `tests/offers/test_document_history.py` | T-199 |
| Exportaciones | la planilla y el cuadro del caso chico contienen el 100 % de ofertas y requisitos en el Excel; el PDF del cuadro se genera | `tests/assessment/test_export.py` | T-212 |
| Sin internet | 0 direcciones externas en plantillas y scripts nuevos | Test que busca `http://` y `https://` | T-192 y cada tarea de interfaz |

Máximo dos rondas de ajuste (ADR-0025); lo que no llegue pasa con su impacto a "Revisión con el primer producto". Los umbrales de propuesta (T-196, T-213, T-220) se miden una sola vez por lote.

## Componentes

| Componente | Nuevo | Qué hace | Con quién habla |
|---|---|---|---|
| `evaluon/journey/sections/` | Sí | `base.py` (tipo `Section`, `TemaStatus`, estados y cuentas), `__init__.py` (`SECTIONS`, `sections_for(user, procedure)`) y un archivo por sección que suma los `status()` de sus temas | `journey/stages/` (insumo), los temas |
| `evaluon/journey/temas/` | Sí | Un módulo por tema, con `status()`, vistas, `urlpatterns` y el nombre de su parcial. `__init__.py` los registra y suma sus rutas | Servicios existentes de `tenders`, `offers`, `portal`, `assessment`, `norms`, `queries` |
| `evaluon/templates/journey/` | Cambia | `seccion_base.html` (encabezado, barra de las cinco secciones, resumen, pendientes, sugerencias, detalle, acciones al pie), `portada.html` y un parcial por tema | Guía visual y `tokens.css` |
| `evaluon/static/journey/` | Cambia | `secciones.css` (jerarquía común, tabla densa, íconos de estado con nombre al pasar el mouse) y un CSS por sección; `recorrido.js` se reutiliza para el sondeo de la portada y la barra | Mismo servidor, sin CDN |
| `evaluon/tenders/` | Cambia poco | Modelos y servicios de historial, borrador de procedimiento, pedido nuevo | T-193, T-196, T-199 |
| `evaluon/offers/`, `evaluon/assessment/`, `evaluon/portal/`, `evaluon/norms/`, `evaluon/audit/` | Cambian poco | Un modelo o un servicio cada una (ver "Modelo de datos") | T-193 y tareas de servicio |
| `app`, `worker`, `portal_worker`, base, servicios de IA | No | Sin cambios de arquitectura. El pedido nuevo lo atiende `worker` | — |

El camino de pliegos y ofertas sigue sin depender de ningún servicio externo (P4): la lectura del pliego para proponer los datos usa la lectura local ya existente y, si hace falta, el modelo local. La normativa, por ser pública, solo se sube como archivo; no se trae de fuentes externas.

### Rutas

El prefijo `recorrido/` pasa a `expedientes/` y `recorrido/` redirige. Todo lo demás cuelga del procedimiento. Los nombres exactos los fija T-192 con la maqueta aprobada.

| Ruta | Para qué |
|---|---|
| `expedientes/` | Lista de procedimientos con sus cuentas |
| `expedientes/nuevo/` | Sección 1 antes de que exista el procedimiento: pegar el enlace del Portal o subir el pliego |
| `expedientes/<id>/` | Portada del procedimiento: las cinco secciones con estado, pendientes y sugerencias en dos bloques separados; ventana del proceso |
| `expedientes/<id>/procedimiento/`, `pliego/`, `ofertas/`, `evaluacion/`, `normativas/` | Las cinco secciones; se entra a cualquiera, sin pasar por las anteriores |
| `expedientes/<id>/barra/` | Solo el bloque de la barra de secciones y las cuentas (sondeo cada 5 s, ADR-0045) |
| Rutas de acción de cada tema | En su propio `urlpatterns` (por ejemplo, `.../pliego/documentos/subir/`) |

Las rutas POST de las otras apps (confirmar un requisito, validar la matriz, decidir un resultado, aprobar ítems del Portal) se conservan y se invocan desde las secciones; después de actuar vuelven a la sección de origen (parámetro `next` validado, solo rutas del mismo sitio).

## Las cinco secciones: qué contiene cada una

Todas usan la misma jerarquía (REQ-100): título, resumen (qué hay, qué falta, de dónde vino cada cosa), lo pendiente de decidir, las sugerencias del sistema (bloque aparte, visible), el detalle y las acciones al pie. En todas, «Subir archivo» y, cuando el Portal lo publica, «Tomar del Portal» están siempre a la vista (REQ-097).

| Sección | Temas (cada uno, una tarea) | Se reutiliza | Se mueve | Se agrega |
|---|---|---|---|---|
| 1 · Procedimiento de compra | `s1_datos` (T-194), `s1_portal` (T-195), `s1_pliego` (T-197) | `portal` completo (`links`, `proposal`, `approval`, `imported`, revisión periódica); `PortalProcedureData`, `PortalLine`, `PortalGuarantee`; `applicable_regimes` | La propuesta del Portal deja de ser pantalla suelta: se muestra dentro de la sección, agrupada | Origen de cada dato; alta desde el pliego |
| 2 · Pliego y matriz | `s2_documentos` (T-198, T-200), `s2_matriz` (T-192, T-201) | `tenders.services.documents`, `matrix_page`, `review`, `validation`, `export` (imprimir y PDF), `open_new_version`, cobertura y descartadas | Los formularios de carga y de revisión pasan de `tenders:procedure` y `tenders:matrix` a la sección | Subida múltiple, historial de documentos, tabla agrupada con filtros, lista de versiones |
| 3 · Ofertas | `s3_ofertas` (T-202, T-206), `s3_ficha` (T-203), `s3_anexos` (T-204), `s3_circulares` (T-205) | `offers.services` (alta, carga múltiple, lectura), fichas, `assessment.services.compliance`, circulares del pliego (documentos de tipo circular) | Alta de oferta y carga de documentos pasan de `offers:*` a la sección | Alta desde el acta (ya viene del Portal) a la vista; anexos técnicos como tipo; circular modificatoria que abre versión nueva de la matriz |
| 4 · Evaluación y dictamen | `s4_propuesta` (T-207), `s4_preguntas` (T-208), `s4_informe` (T-209), `s4_descartes` (T-210), `s4_dictamen` (T-211), `s4_exportar` (T-212) | `assessment.services` (`matrix_page`, `evaluate`, `review`, `questions`, `remedy`, `technical_report`), `ordering.propose_discards` y `economic_order` | Matriz de evaluación, preguntas, subsanación e informe técnico pasan de `assessment:*` a la sección | Decisión sobre descartes; dictamen subido; exportaciones |
| 5 · Normativas | `s5_normas` (T-214), `s5_rigen` (T-215), `s5_consulta` (T-216) | `norms.services` (`load_norm`, `reading_summary`, `validate_reading`, `list_norms`, `reading_report`), `queries` (consulta con citas) | La consulta (hoy raíz del sitio) se muestra dentro de la sección 5 con la fecha de autorización del procedimiento | Carga, informe de lectura y validación por pantalla; normas que rigen y que faltan |

### Cómo se calcula el estado y las cuentas de cada sección

Cada tema devuelve `TemaStatus(pending, suggestions, missing, sources)`: `missing` es la lista de lo que falta, cada ítem con su acción directa; `sources` dice de dónde vino lo que hay (el Portal o tal archivo). La sección suma. Estado de la sección, con las mismas reglas comunes de la 013 (en curso, con error, pendiente, a decidir, lista): sale de las etapas que ya calcula `journey/stages/` más los temas nuevos.

| Sección | Insumo existente (etapas de la 013) | Suma de los temas nuevos |
|---|---|---|
| 1 | `portal` (propuesta del Portal, ítems `propuesto`) | Borradores de procedimiento desde el pliego pendientes de aprobar |
| 2 | `pliego`, `matriz` | Documentos del pliego faltantes |
| 3 | `ofertas` (documentos leídos, filas de ficha `propuesto`) | Ofertas sin hoja de compliance (faltante, REQ-088); circulares modificatorias sin matriz nueva validada |
| 4 | `evaluacion`, `matriz_evaluacion` (pares `propuesto`, preguntas abiertas, ok del informe técnico) | Descartes propuestos sin decisión; ofertas sin informe técnico (sugerencia o faltante según la fila técnica); dictamen sin cargar |
| 5 | — | Normas que rigen y no están cargadas; lecturas de norma pendientes de validar |

La barra de las cinco secciones aparece en toda pantalla del procedimiento (REQ-075) y usa el mismo cálculo que la portada. El sondeo de la 013 (cada 5 s, ADR-0045) se reutiliza para la portada y la barra.

## Modelo de datos

Todo el esquema lo toca **una sola tarea, T-193**, para que ninguna otra tarea genere migraciones en paralelo. Las tablas nuevas siguen la costumbre del proyecto: sin borrado, con disparadores que impiden `UPDATE` y `DELETE` cuando son registros de hechos.

| Tabla o cambio | Para qué | REQ |
|---|---|---|
| `tenders_document_change` y `offers_document_change` (nuevas, solo se insertan filas): documento, acción (`reemplazar`, `retirar`, `restituir`), documento nuevo (en `reemplazar`), nota, usuario, momento, hecho de auditoría | Historial de versiones. "Vigente", "reemplazado" y "retirado" se calculan del último cambio; el documento y su archivo original nunca se modifican ni se borran (ADR-0048) | REQ-099 |
| `tenders_document.kind` suma `dictamen`; `offers_document.kind` suma `anexo_tecnico` | Dictamen subido (4.4) y anexo técnico como tipo fijado por la acción de la Comisión, igual que la hoja de compliance (T-189) | REQ-092, REQ-087 |
| `tenders_procedure_draft` (nueva): archivo (bytes y huella), propuesta (JSON con cada dato, sus candidatos y su cita), estado (`leyendo`, `propuesto`, `aprobado`, `rechazado`, `fallido`), pedido, usuario, momento, procedimiento resultante | Alta desde el pliego: el procedimiento no puede existir antes de aprobarse (sus datos son obligatorios), así que el pliego espera aquí (ADR-0049) | REQ-077 |
| `tenders_job.kind` suma `propose_procedure` (`target_id` = borrador) y la restricción `tenders_job_procedure_required` lo admite sin procedimiento | Pedido en segundo plano que lee el pliego y propone | REQ-077 |
| `portal_line.item` y `portal_procedure_data.item` pasan a admitir nulo y ambas suman `document` (documento del pliego de origen); una restricción exige exactamente uno de los dos | Los renglones y el expediente propuestos desde el pliego se guardan en las mismas tablas que los del Portal, así `assessment` y las pantallas siguen leyendo un solo lugar. El origen sale de cuál de los dos está presente (ADR-0049) | REQ-077, REQ-078 |
| `assessment_discard_decision` (nueva, solo inserta): procedimiento, oferta, renglón (nulo si es toda la oferta), pedido de evaluación sobre el que se decidió, acción (`confirmar`, `rechazar`), nota, usuario, momento, hecho | Decisión de la Comisión sobre cada descarte propuesto. El estado del descarte es la última decisión sobre la evaluación vigente: si se evalúa de nuevo, vuelve a quedar sin decidir | REQ-091 |
| `norms_upload` (nueva): archivo, huella, nombre, datos propuestos con la evidencia de cada uno, estado, usuario, momento, documento de norma resultante | Una norma subida espera aquí hasta que la Comisión confirma los datos propuestos; recién entonces se llama a `load_norm` (ADR-0051) | REQ-094 |
| `offers_offer_draft` y `offers_offer_draft_file` (nuevas): procedimiento, archivos de la oferta (bytes y huella), propuesta (JSON con nombre y CUIT, cada uno con su cita), estado (`leyendo`, `propuesto`, `aprobado`, `rechazado`, `fallido`), pedido, usuario, momento, oferta resultante | Alta de oferta sin Portal: la oferta no puede existir sin oferente, así que los archivos esperan aquí hasta que la Comisión aprueba o corrige el nombre y el CUIT | REQ-083 |
| `tenders_job.kind` suma también `propose_offer` (`target_id` = borrador de oferta), mismo ajuste de restricción | Pedido en segundo plano que lee los archivos de la oferta y propone | REQ-083 |
| `portal_offer_data.item` pasa a admitir nulo y suma `document` (documento de la oferta de origen), con la restricción de «exactamente uno» | El CUIT propuesto desde los archivos se guarda donde ya se guarda el del acta | REQ-083 |
| Corrección de un dato propuesto: no es una tabla aparte. Cada propuesta guarda, por dato, `{propuesto, corregido, motivo, quién, cuándo}` dentro de su JSON (`tenders_procedure_draft`, `offers_offer_draft`, `norms_upload`) y la aprobación lo copia al hecho de auditoría | «Escribe el valor y motivo»: corrige lo propuesto, el motivo es obligatorio; el valor propuesto original no se pierde | REQ-077, REQ-083, REQ-094 |
| `audit.EventType` suma `document_change`, `procedure_proposal`, `offer_proposal`, `discard_decision`, `norm_upload`, `eval_export`, con su restricción | Registro de auditoría (P6) | REQ-091, REQ-093, REQ-094, REQ-099 |

Los parciales de las plantillas no tienen modelos. El borrador del dictamen no existe (fuera de alcance). No hay cambios en `tenders_job.progress` ni en la cola más allá del tipo nuevo.

### Roles

| Acción | Quién | Cómo se comprueba |
|---|---|---|
| Ver cualquier sección, subir archivos (incluidos el pliego y los archivos de una oferta para que el sistema proponga), aprobar la carga de documentos del Portal, reemplazar, retirar, restituir, exportar | Operador o evaluador | `require_commission_role(OPERATOR)` en cada servicio nuevo, con su rechazo registrado |
| Aprobar o corregir datos, renglones y ofertas importados del Portal, el alta del procedimiento desde el pliego y el alta de una oferta desde sus archivos (REQ-048 de la 012) | Solo evaluador | `require_commission_role(EVALUATOR)`; el operador sube y ve la propuesta pero no ve los botones de aprobar ni corregir |
| Decidir descartes, validar la matriz, decidir resultados, dar el ok del informe técnico, validar una norma | Evaluador | `require_commission_role(EVALUATOR)`; el botón no se dibuja para el operador (REQ-091) |
| Usuario de lectura sin rol de la Comisión | Rechazado (403) en todo el procedimiento | Como hoy |

Dos cosas que hoy no coinciden y se resuelven en T-214: las operaciones de normas exigen el rol de normativa de lectura y escritura (`Role.READ_WRITE`), no el rol de la Comisión. La pantalla exige además evaluador de la Comisión para validar (REQ-094); el servicio sigue exigiendo su rol de normativa. Decisión operativa del Coordinador (punto 4 de «Decisiones operativas»): no se cambia el modelo de permisos; los evaluadores se crean con los dos roles, y el runbook de T-214 lo documenta (`crear_usuario` y `rol_comision`).

## Flujo de IA

La feature **no cambia ningún flujo de IA existente** (evaluación, matriz, ficha). Dos usos nuevos de lectura, ambos locales:

- **Propuesta de datos desde el pliego (T-196, ADR-0049).** Se lee el pliego con la lectura local ya existente (`tenders.reading`) sobre los bytes del borrador. Número, expediente y fecha de autorización se buscan por reglas sobre las primeras páginas; tipo y objeto, por reglas y, si no alcanzan, con el modelo local pidiéndole la cita literal que se verifica contra el texto (mismo patrón que la matriz: sin cita verificable, el dato queda "no determinado" y no se propone). Los renglones salen de la tabla de renglones de la lectura (número, descripción, cantidad). Cada dato propuesto lleva su cita (página y texto). El evaluador aprueba, descarta o corrige cada dato escribiendo el valor y el motivo (obligatorio; queda quién y cuándo; P3). Se registra modelo, parámetros, instrucciones y fragmentos (P6).
- **Nombre y CUIT del oferente desde los archivos de la oferta (T-220).** Se leen los archivos de la oferta con la lectura local de ofertas sobre los bytes del borrador; el CUIT se busca por regla (formato y dígito verificador) y el nombre por regla y, si no alcanza, con el modelo local pidiendo la cita literal que se verifica contra el texto; sin cita verificable el dato queda «no determinado». El evaluador aprueba o corrige escribiendo el valor y el motivo. Se registra modelo, parámetros, instrucciones y fragmentos (P6).
- **Datos de una norma subida (T-213, ADR-0051).** Solo reglas sobre el encabezado del PDF; sin IA. Los datos que no reconoce quedan marcados para que la Comisión los confirme o corrija con valor y motivo.

Evals (P7): como no cambia recuperación ni instrucciones existentes, no se vuelve a correr el conjunto dorado de la evaluación. Las instrucciones nuevas de la propuesta desde el pliego se miden con los umbrales de la tabla (una vez por lote).

## Registro de auditoría

Cada operación nueva deja un hecho (P6), con usuario, momento y canal pantalla:

- Reemplazar, retirar, restituir: `document_change` con documento, acción, documento nuevo, nota y huellas.
- Propuesta desde el pliego: `procedure_proposal` con la huella del archivo, la lectura usada, modelo y parámetros (si se usó), instrucciones, las citas, y luego la decisión de la Comisión ítem por ítem. Al aprobar, el alta del procedimiento deja además el hecho `procedure` de siempre.
- Decisión de un descarte: `discard_decision` con oferta, renglón, motivos (los requisitos con "no cumple" y sus fundamentos), evaluación, acción y nota.
- Alta de oferta desde sus archivos: `offer_proposal` con las huellas, la lectura usada, modelo y parámetros (si se usó), instrucciones, las citas y la decisión o corrección (valor propuesto, valor corregido, motivo) con quién y cuándo; al aprobar, además el hecho `offer_register` de siempre.
- Toda corrección de un dato propuesto guarda el valor original, el corregido, el motivo, quién y cuándo, en el hecho de su propuesta.
- Norma subida: `norm_upload` con la huella y los datos propuestos y confirmados; la carga, la lectura y la validación siguen dejando `load`, `reread` y `validation`.
- Exportaciones: `eval_export` con qué se exportó (planilla o cuadro), de qué evaluación y en qué formato.
- Pedidos de rol rechazados: `rejected`, como hoy.

## Cobertura de requisitos

| Requisito | Cómo se resuelve | Cómo se verifica |
|---|---|---|
| REQ-075 | Registro de secciones y barra en toda pantalla del procedimiento (T-192); redirección de las pantallas viejas (T-219) | `tests/journey/test_sections.py`: cinco secciones con estado y cuentas, cualquiera se abre sin pasar por otra; T-217 y T-218 |
| REQ-076 | Tema `s1_portal`: pegar enlace, propuesta agrupada, aprobar ítem por ítem o todo (`approve_all`), destino por sección (T-195, T-197) | Test del flujo con el caso chico simulado; T-218 con el caso-00: datos en la 1, pliego en la 2, ofertas en la 3 |
| REQ-077 | Borrador, pedido `propose_procedure`, servicio de propuesta y aprobación (T-193, T-196); pantalla que solo permite aprobar, descartar o corregir lo propuesto con valor y motivo obligatorio, sin formulario de alta en blanco; aprueba solo el evaluador (T-197) | `test_procedure_proposal.py` (umbral de la tabla), test de que no existe alta en blanco y de que la corrección exige motivo; T-218 |
| REQ-078 | Tema `s1_datos`: número, expediente, tipo, objeto, fecha con régimen (`regime_for`), renglones con cantidad, apertura, garantías y origen de cada dato (T-194) | Test con caso del Portal y con caso desde pliego; régimen 247/2022 con el caso-00 |
| REQ-079 | Se reutiliza la revisión periódica (`portal_review`, `following`); sus novedades se cuentan como pendientes de la sección 1 y de la portada y no se cargan sin aprobar (T-195) | Test: novedad detectada aparece como `propuesto` y nada se carga |
| REQ-080 | Tema `s2_documentos`: lista por tipo con origen, «Subir archivo» múltiple, «Tomar del Portal» (T-198) | Test: procedimiento sin pliego muestra los dos accesos; subir tres documentos |
| REQ-081 | Tema `s2_matriz`: tabla agrupada por tipo, filtros, fila que abre la cita, acciones de la Comisión (T-192, T-201) | Test del filtro "solo lo que falta decidir"; acciones confirmar, corregir, quitar, agregar, validar desde la fila |
| REQ-082 | Lista de versiones con fecha y quién validó (T-192); imprimir y exportar PDF (T-201, reutiliza `export`) | Test con matriz de dos versiones; PDF responde 200 |
| REQ-083 | Tema `s3_ofertas`: botón de alta visible; alta desde el acta del Portal o subiendo los archivos de la oferta, con nombre y CUIT propuestos por el sistema con su cita y aprobados o corregidos (valor y motivo) por el evaluador (T-193, T-220, T-202) | Test: el botón está en la página sin abrir nada; `test_offer_proposal.py` (umbral de la tabla); el operador sube pero no aprueba |
| REQ-084 | Subida múltiple en la oferta (ya existe en `offers.views.documents.offer`), integrada en la sección (T-202) | Test: tres archivos juntos quedan en la oferta |
| REQ-085 | Tema `s3_circulares`: lista y subida; al aprobar o subir una circular modificatoria se abre una versión nueva de la matriz con lo cambiado marcado (T-205) | Test: circular que cambia un requisito produce versión nueva con ese requisito marcado |
| REQ-086 | Tema `s3_ficha`: la ficha de la oferta dentro de la sección, con lo presentado y el fragmento o "no se encontró en la oferta" (T-203) | Test con oferta leída |
| REQ-087 | Tipo `anexo_tecnico` y subida dentro de la oferta (T-193, T-204) | Test: la ficha técnica subida figura como anexo técnico |
| REQ-088 | Tema `s3_anexos`: hoja de compliance una vez por oferta; faltante con su botón (T-204) | Test: oferta sin hoja figura como faltante |
| REQ-089 | Temas `s4_propuesta` y `s4_informe` (T-207, T-209) | Test con el caso evaluado; el informe técnico se sube desde la sección |
| REQ-090 | Tema `s4_preguntas` (T-208) | Test: pregunta abierta figura entre los pendientes con su acceso |
| REQ-091 | Tema `s4_descartes`: tabla de decisión, servicio, auditoría y orden económico (T-193, T-210) | Test: el evaluador confirma y queda quién y cuándo; el operador no ve el botón |
| REQ-092 | Tema `s4_dictamen`: dictamen del Portal (archivo ya importado) o subido (tipo `dictamen`); ninguna acción de borrador (T-211) | Test: dictamen del Portal aparece; no existe la ruta "generar borrador" |
| REQ-093 | Tema `s4_exportar`: planilla por oferta en Excel y cuadro comparativo en Excel y PDF (T-212, ADR-0050) | `test_export.py` con el caso evaluado: el `.xlsx` se abre y trae el 100 % de ofertas y requisitos; el PDF responde 200 |
| REQ-094 | Staging `norms_upload`, propuesta de datos, informe de lectura y validación (T-193, T-213, T-214) | Test del flujo completo sin comandos |
| REQ-095 | Tema `s5_rigen`: `applicable_regimes` por fecha de autorización, normas cargadas y normas faltantes (T-215) | Test con el caso-00 (247/2022) |
| REQ-096 | Tema `s5_consulta`: la consulta existente dentro de la sección (T-216) | Test: respuesta con citas literales y su parte |
| REQ-097 | Cada tema declara `missing` con su acción directa; la sección los lista (T-192 y cada tema) | Test del procedimiento recién creado en cada sección; T-217 |
| REQ-098 | Dos bloques separados (pendientes y sugerencias) en cada sección y en la portada (T-192) | Test del caso con pendientes y sugerencias |
| REQ-099 | Esquema (T-193), servicios (T-199), pantallas (T-200 en la 2, T-206 en la 3; dictamen en T-211) | Tests: reemplazado muestra anterior y nueva; retirado aparece en "retirados" |
| REQ-100 | Plantilla común y CSS de la guía visual (T-192); cada tarea de interfaz la aplica; revisión del Coordinador en el navegador (T-218) | Revisión visual de cada pantalla; test de que ninguna plantilla define colores fuera de los tokens |
| No funcional: 2 s | Estado calculado con consultas acotadas; la barra reutiliza el cálculo de la portada | Medición en T-218 |
| No funcional: 1280 px | Diseño desde 1280 px, usable a 1366 × 768 | Revisión en el navegador (T-218) |

## Control de decisiones

Cada decisión literal de la spec y de los ADR, y dónde se aplica. Antes de medir (T-218) se contrastan contra el código.

| Fecha | Decisión del responsable (resumen literal) | Dónde se aplica en el plan |
|---|---|---|
| 2026-10-07 | «es alta desde el portal o subir el pliego en un file»; no se tipean renglones | Resumen; "Lo nuevo de verdad", fila 1; modelo `tenders_procedure_draft` y `portal_line` con documento de origen; T-196 y T-197; umbral de 0 datos tipeados |
| 2026-10-07 | «Donde esta el alta de ofertas?» | Sección 3, tema `s3_ofertas` (T-202): el botón de alta visible sin abrir nada |
| 2026-10-07 | Organización en cinco secciones, sin orden, «cada uno con su posibilidad de subir files o tomarlos del portal», explorador y cargador inicial del Portal en el uno | Sección "Las cinco secciones"; rutas sin orden obligatorio; REQ-097 (acciones siempre a la vista); tema `s1_portal` |
| 2026-10-07 | Circular modificatoria: «Versión nueva de la matriz» con lo cambiado marcado, que la Comisión valida de nuevo | Tema `s3_circulares` (T-205); la versión nueva queda en borrador y se valida con la acción existente (evaluador) |
| 2026-10-07 | «Matrices» de la oferta: «Lo que presentó cada oferta», con el fragmento (la ficha) | Tema `s3_ficha` (T-203) |
| 2026-10-07 | Anexos técnicos: «Solo los de la oferta»; el informe técnico del área va en la 4 | Tema `s3_anexos` (tipo `anexo_tecnico`, solo dentro de la oferta); tema `s4_informe` |
| 2026-10-07 | Borrador del dictamen: «Sigue diferido» | Tema `s4_dictamen`: sin ruta ni botón de borrador; test de que no existe |
| 2026-10-07 | Normas: «Solo subir el archivo» | Tema `s5_normas`; `norms_upload`; ADR-0051 (datos propuestos desde el archivo, sin formulario de diez campos tipeados desde cero) |
| 2026-10-07 | «Todo sí» al resto de la hoja (1.1 a 1.4, 2.1 a 2.3, 3.1, 3.2, 3.6, 4.1 a 4.3, 4.5, 5.2, 5.3, T.1 a T.6) | Tabla "Cobertura de requisitos", una fila por requisito |
| 2026-10-07 | Alta de oferta sin Portal, nombre y CUIT: «El sistema lo propone» (lee los archivos y propone con su cita; la Comisión aprueba o corrige) | Modelo `offers_offer_draft`; Flujo de IA, nombre y CUIT; T-220 (servicio) y T-202 (pantalla); REQ-083 |
| 2026-10-07 | Corregir un dato propuesto (pliego, oferta, norma): «Escribe el valor y motivo» | Modelo, fila «Corrección de un dato propuesto»; Registro de auditoría; T-196, T-197, T-213, T-214, T-220, T-202; ADR-0049 y ADR-0051 |
| 2026-10-07 | Exportación de la planilla y el cuadro: «Excel y PDF» | ADR-0050 (XlsxWriter y `weasyprint`); T-212; REQ-093 |
| 2026-10-07 | «usa el diseño que acordamos» | Plantilla común y `secciones.css` con `tokens.css` (T-192); REQ-100; revisión del Coordinador |
| Vigente | El Portal es la primera fuente; lo que no publica se sube (REQ-071) | Cada sección muestra primero «Tomar del Portal» cuando hay algo publicado y «Subir archivo» siempre |
| Vigente | Pendientes y sugerencias separados y los dos visibles (REQ-072) | `TemaStatus.pending` y `.suggestions` en dos bloques (REQ-098) |
| Vigente | La ficha de la oferta es opcional | La ficha no frena la evaluación; en el tema `s3_ficha` no cuenta como faltante, solo sus filas propuestas como pendiente |
| Vigente | Los cuatro íconos de estado con el nombre propio de cada pantalla al pasar el mouse (ADR-0046, punto 7) | `secciones.css` y el parcial de íconos (T-192); cada tema pasa su nombre |
| Vigente | Guía visual: ícono de color sin pastillas, tabla densa con cabecera fija y cebra, barra oscura con filete rojo | T-192; verificación en T-218 |
| 2026-10-07 | Maqueta rehecha y aprobada antes de programar cualquier pantalla | "Condición previa: maqueta aprobada" |

## Verificación contra la constitución

| Principio | Cumple | Nota |
|---|---|---|
| P1 Spec fuente de verdad | sí | Cada tarea nombra sus REQ; las dudas están abajo |
| P2 Trazabilidad | sí | Tabla de cobertura y `tasks.md` con REQ por tarea |
| P3 El sistema recomienda, la Comisión decide | sí | Todo lo propuesto (datos del pliego, nombre y CUIT de la oferta, datos de la norma, descartes, versión nueva por circular) queda en estado propuesto hasta que una persona decide; el operador no ve acciones de decisión |
| P4 Datos | sí | Material público; el camino de pliegos y ofertas es local; normas solo por archivo subido; casos reales no suben al repositorio |
| P5 Local y reproducible | sí | Sin servicios nuevos; una sola dependencia nueva, XlsxWriter (ADR-0050), local y con versión fijada |
| P6 Auditoría | sí | Hechos nuevos para cada operación (ver sección); nada se borra |
| P7 Evals | sí | No cambia recuperación ni instrucciones existentes; lo nuevo se mide con los umbrales de la tabla |
| P8 Normativa versionada | sí | La carga de normas usa `load_norm` y sus versiones sin cambios |
| P9 Compliance | sí | La hoja la sube una persona identificada; el sistema no la completa |
| P10 Simplicidad | sí | Se reutilizan servicios y modelos; las tablas nuevas existen porque un requisito las pide (REQ-077, 083, 091, 094, 099); no se agrega nada más |
| P11 Compuertas humanas | sí | Maqueta, plan y despliegue requieren aprobación del responsable |

## Decisiones

- ADR-0048 (propuesto): historial de documentos sin borrar (tabla de cambios solo-inserción y estado calculado).
- ADR-0049 (propuesto): alta del procedimiento desde el pliego subido (borrador previo, renglones en las tablas del Portal, reglas más modelo local con cita verificada).
- ADR-0050 (propuesto): formato de las exportaciones de la evaluación (Excel con XlsxWriter, dependencia nueva a aceptar, y PDF con `weasyprint`).
- ADR-0051 (propuesto): carga de normas subiendo solo el archivo (datos propuestos por reglas, confirmación y staging).

## Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El cálculo de las cinco secciones en cada pantalla (la barra) supera 2 s con el caso-00; el recorrido de la 013 nunca se midió con el caso-00 (T-186 quedó pendiente) | REQ de rendimiento incumplido | Medir en T-192 con el caso chico y en T-218 con el caso-00; la barra usa solo conteos; si no alcanza, una ronda: memoria de 5 s por procedimiento en el cálculo de la matriz de evaluación |
| La propuesta de datos desde el pliego no reconoce bien un pliego real | Alta con muchas correcciones | Cita verificada y estado "no determinado"; corrección con valor y motivo; umbral escrito y dos rondas; lo que no llegue pasa a la lista de revisión |
| Circular modificatoria: hoy la incorporan los pedidos de propuesta de la matriz, no hay un camino documentado para aplicarla sobre una versión validada | REQ-085 más caro de lo previsto | T-205 empieza relevando `tenders/proposal/circulars.py` y `circular_changes.py`; si hace falta, la versión nueva se obtiene con un pedido de propuesta que incluya la circular, con lo cambiado marcado por `previous` y `RequirementSource` |
| Reemplazar o retirar un documento del pliego deja una matriz validada apoyada en un documento ya no vigente | Matriz inconsistente | El retiro no modifica versiones validadas (no cambian); se avisa en la sección 2 "la matriz vigente se armó con un documento retirado" y se ofrece abrir versión nueva; el retiro no dispara ninguna propuesta sola |
| Retirar una oferta o documento ya evaluado deja evaluaciones sobre un documento retirado | Resultado sin respaldo vigente | Las evaluaciones guardan los documentos usados (P6); se marca la evaluación como "con documentos retirados" y se pide evaluar de nuevo; no se recalcula sola |
| Dos tareas de sección con parciales o rutas en común | Conflictos al integrar | Un tema por archivo y rutas por tema; la plantilla de sección solo incluye los parciales (T-192); las tareas no tocan `base.html`, `urls.py`, `settings.py` |
| Duplicar el pliego al leerlo dos veces (para proponer y al cargarlo ya aprobado) | Tiempo extra | Aceptado en la primera versión; el costo es una lectura local |
| Las pantallas viejas siguen accesibles y confunden | El responsable ve dos organizaciones | T-219 las redirige antes de la comprobación final |
| Rol de normativa y rol de la Comisión no coinciden para validar normas | El evaluador no puede validar | T-214 comprueba ambos y muestra el motivo; los evaluadores se crean con los dos roles (decisión operativa 4) |
| Cambiar la maqueta después de empezar a programar | Retrabajo | Compuerta previa explícita; las tareas con pantalla no arrancan sin ella |

## Tareas de la 013 que se absorben

| Tarea de la 013 | Qué la reemplaza |
|---|---|
| T-185 · Los cinco momentos y los roles con el caso chico (30 celdas) | T-217 (5 momentos por 5 secciones, 25 celdas, y roles). Se traen sus avisos: pausa del sondeo con la pestaña oculta, `Stage.suggestions`, motivo de falla con `plain_reason`, foco del ícono tras el sondeo |
| T-186 · Comprobación con el caso-00 desde cero | T-218 (26 de 26 requisitos, carga menor a 2 s, sin datos tipeados). Se trae la nota del runbook: reconstruir la imagen (`docker compose build app`) para servir los archivos estáticos |
| T-188 · Aplicar la guía visual | T-192 (jerarquía común, `secciones.css`, íconos y tabla densa) y la aplicación en cada tarea de interfaz; revisión final en T-218 |
| T-191 · Cuentas y accesos de hojas de compliance e informes técnicos que faltan | T-204 (hoja de compliance faltante, sección 3) y T-209 (informe técnico faltante, sección 4), con sus cuentas en la portada (T-192) |

## Dudas abiertas

Ninguna. Las seis dudas de la primera versión quedaron resueltas el 2026-10-07: las tres primeras por el responsable (filas nuevas de «Control de decisiones» y de la spec) y las otras cuatro, más una, como decisiones operativas del Coordinador.

## Decisiones operativas del Coordinador (2026-10-07)

Son decisiones de operación, no del responsable sobre el producto.

4. **Validar normas por pantalla.** Lo hace el evaluador de la Comisión; quien tenga ese rol necesita además el rol de normativa de lectura y escritura. No se cambia el modelo de permisos. El runbook de T-214 documenta que los evaluadores se crean con los dos roles.
5. **«Normas que faltan cargar» (REQ-095).** Son: la norma del régimen que fija la fecha de autorización, el marco nacional, las modificatorias registradas sin cargar (`PendingAmendment`) y las normas que cita el pliego y no están cargadas. Se aplica en T-215.
6. **Pantalla «Nuevo procedimiento» previa** (`expedientes/nuevo/`, o el nombre que fije la maqueta, que ya la muestra como `#nuevo`). Se aplica en T-192 y T-195.
7. **Roles de aprobación de lo importado.** Según REQ-048 de la 012: datos, renglones y ofertas los aprueba solo un evaluador; el operador puede aprobar solo la carga de documentos. Se aplica también al alta desde el pliego (T-196, T-197) y al alta de una oferta desde sus archivos (T-220, T-202); ver «Roles».
