# Plan 018 · El proceso a la vista

Estado: borrador · Fecha: 2026-11-17 (actualizado con las respuestas del responsable a las preguntas del plan y con REQ-157 ampliado) · Aprobó: —

Spec: `specs/018-proceso-a-la-vista/spec.md` (aprobada el 2026-11-17)

ADR de este plan (propuestos): `docs/adr/0078-estado-de-los-siete-pasos-calculado-sobre-las-secciones.md` y `docs/adr/0079-inicio-de-la-aplicacion-lista-de-abiertos-y-presupuesto-de-2-segundos.md`. Se apoya en 0045 (estado calculado, sin guardar fase), 0046 y 0047 (organización por procedimiento y cinco secciones), 0076 (HTML del servidor y poco JavaScript) y 0077 (lo que el sistema no tiene se dice, no se inventa).

## Resumen del enfoque

No se agrega ningún dato ni se cambia ningún cálculo de evaluación. Los siete pasos son **una lectura nueva de lo que el sistema ya calcula**: las seis etapas de la 013 (`journey/stages/`), las cuentas de las cinco secciones de la 014 (`journey/sections/`) y unos pocos datos que ya están en la base. Un módulo nuevo, `evaluon/journey/proceso/`, toma el `Overview` que devuelve `sections_for` y produce, sin tocar la base, el estado de los siete pasos, las acciones de «Qué se puede hacer ahora» y el vencimiento de hoy. Tres pantallas lo muestran: el **inicio** (lista de abiertos, opción E), la **portada** del procedimiento (opción A) y el **cuadro de cumplimiento** con panel lado a lado (opción C, ya reutilizando la página del par requisito-oferta). Todo es HTML del servidor, CSS propio y, como mucho, ningún script nuevo (ADR-0076): el panel del cuadro se elige con un parámetro de la dirección y el colapsar/expandir es `<details>` nativo.

Seis ideas ordenan el plan:

1. **Una sola definición de cada cosa.** Los pasos, sus nombres y su orden viven en una tabla (`proceso/pasos.py`). Las cuentas de pares, preguntas, descartes e informe técnico se toman de las funciones que ya usan las etapas (hoy privadas; se hacen públicas sin cambiar su comportamiento).
2. **El reparto de pendientes en pasos se hace por origen**, no por texto: `Item` y `Missing` suman un campo `origen` (el tema o la etapa que lo produjo), con valor por omisión, y `build_section` lo completa. Así «Qué se puede hacer ahora» y el contador de las pestañas salen de los mismos renglones.
3. **Los casos dudosos se dijeron y el responsable los resolvió el 2026-11-17.** Había cuatro reglas de la spec que los datos actuales no cubrían tal cual (ver «Decisiones del responsable sobre lo que los datos no daban»); sus respuestas están en la spec enmendada y en el plan. Queda una pregunta nueva (N1, al final de esa sección).
4. **Corte vertical primero** (ADR-0025): la tabla de estados escrita a mano, el cálculo, la portada y un cuadro mínimo, con el caso chico y público; recién después el inicio, los filtros y el vocabulario.
5. **El lila de «Vence hoy» (`--hoy`) y el rojo brillante de «Vencido» (`--vencido`) son tokens propios**, distintos de `--ext` y de `--no`, y las pantallas donde se usan no cargan nada que use esos dos.
6. **Sin migraciones.** Ninguna tabla ni columna nueva (REQ-145); un test falla si aparece una migración en `evaluon/*/migrations/` con esta feature.

## Lo que se reutiliza y lo que se cambia

| Hoy | En esta feature |
|---|---|
| `journey/sections/__init__.py` · `sections_for` (l. 32): arma las cinco secciones con `memo.scope` | Se reutiliza tal cual. La entrada del cálculo nuevo es el `Overview` que devuelve. |
| `journey/sections/base.py` · `Item` (l. 46), `Missing` (l. 35), `group_items` (l. 70), `build_section` (l. 212) | Se suma `origen: str = ""` a `Item` y a `Missing`; `build_section` lo completa (`etapa:<clave>` para los renglones genéricos de una etapa; la clave del tema para los de un tema) y `group_items`/`group_missing` lo copian al renglón agrupado. Cambio aditivo. |
| `journey/stages/*.py` (`compute`), `stages/__init__.py` · `stages_for` (l. 50) | Sin cambios. Alimentan los estados. |
| `stages/matriz_evaluacion.py` (l. 38 `_undecided_pairs`, l. 56 `_technical_pending_offers`, l. 61-108 `compute`) | Se extrae `counts(page)` público (pares, preguntas, informes, descartes) que usa `compute`; el resultado de `compute` no cambia (test que compara antes y después). |
| `temas/s4_dictamen.py` · `context` (l. 195-220) calcula `loaded` | Se extrae `dictamen_cargado(procedure)` con las mismas dos funciones (`uploaded_dictamenes`, `portal_dictamen` con `TAKEN`) y `context` la usa. |
| `tablero/ingreso.py` · `plazos` (l. 448), `_plazos` (l. 459), `maintenance` (l. 344), `opening_moment` (l. 324), `today` (l. 215) | Se reutilizan para REQ-131 y REQ-157 (los estados `now`/`past`/`future` ya existen). |
| `temas/s4_propuesta.py` · `_bucket` (l. 609), `figures_of` (l. 638), `pair` (l. 737) y `templates/journey/temas/s4_propuesta_par.html` | `_bucket` pasa a ser la definición única del estado de una celda (la usa el mosaico y el cuadro). El cuerpo de la página del par (l. 8-86) se extrae a `journey/_par.html`; la página y el panel del cuadro lo incluyen. |
| `temas/s4_propuesta_acciones.py` · `decide` (l. 105), `back` (l. 62) | `desde=cuadro` además de `desde=par`: solo cambia a dónde vuelve; `review.decide` (el servicio que registra) no se toca. |
| `views/portada.py` · `lista` (l. 87), `portada` (l. 97: redirige a `procedimiento/`), `seccion` (l. 109: llama a `inicio.remember`) | `lista` pasa a ser el inicio nuevo; `portada` pasa a dibujar la portada; `seccion` deja de recordar el último procedimiento. |
| `views/inicio.py` (redirige al último visto, cookie `evaluon_ultimo_*`) | Se reescribe: el inicio es la lista; se elimina la cookie. |
| `templates/journey/expedientes.html` («Expedientes», tabla de 5 columnas) | Se reemplaza por `inicio.html`. |
| `static/diseno/tokens.css` (`--ext` l. 57 y 95) | Se suman `--hoy`, `--hoy-bg`, `--hoy-ink` en los dos temas. |
| `journey/_ingreso.html` y `tablero/ingreso.py` (primer panel) | Sin cambios de contenido: pasa a ser «Indicadores», a un clic de la portada (REQ-148). |

## Componentes

| Componente | Nuevo | Qué hace | Con quién habla |
|---|---|---|---|
| `evaluon/journey/proceso/pasos.py` | Sí | Tabla de los siete pasos (número, nombre, destino en la sección), `Estado` («Hecho», «En curso», «Todavía no», «Con error») y los tipos `Paso`, `Accion`, `Proceso`. Es la única fuente de nombres y orden (REQ-143). | Plantillas, cálculo |
| `evaluon/journey/proceso/calculo.py` | Sí | `proceso_de(user, procedure, overview=None)`: una función por paso (`_paso1` … `_paso7`) que lee el `Overview`, las etapas y unos pocos datos; devuelve `Proceso` (pasos, acciones, terminado, vencimiento más próximo). Solo lee. | `sections_for`, `memo`, `stages`, `temas` |
| `evaluon/journey/proceso/acciones.py` | Sí | Reparte los `Item` y `Missing` de las secciones 1 a 4 en pasos por `origen`, los agrupa por `(paso, kind)` y suma las pocas acciones «de cierre» derivadas del estado de una etapa (ver tabla). | `calculo.py` |
| `evaluon/journey/proceso/vencimientos.py` | Sí | Traduce `ingreso.plazos()` a «vence hoy» por paso y al «vencimiento más próximo» del inicio. | `tablero/ingreso.py` |
| `evaluon/journey/proceso/lote.py` | Sí | Separa abiertos y terminados con dos consultas para todos los procedimientos y arma las filas del inicio. | `views/inicio.py` |
| `evaluon/journey/views/inicio.py`, `views/portada.py` | Cambian | Inicio (lista de abiertos y terminados) y portada. | `proceso/` |
| `evaluon/journey/views/cuadro.py` | Sí | Página `expedientes/<id>/cuadro/`: filtros, grupos y panel de la celda elegida. | `memo.matrix_page`, `s4_propuesta`, `review` |
| `templates/journey/inicio.html`, `portada.html`, `cuadro.html`, `_foto_pasos.html`, `_acciones.html`, `_par.html` | Sí | Pantallas y piezas compartidas (la foto de los pasos es la misma en el inicio y en la portada). | — |
| `static/journey/proceso.css`, `cuadro.css` | Sí | Foto, acciones, «Vence hoy», «Vencido», cuadro y panel. | `tokens.css` |
| `static/diseno/tokens.css`, `docs/diseno/guia-visual.md` | Cambian | Tokens `--hoy*` y su regla de uso. | — |
| `worker`, `portal_worker`, `app`, IA, `assessment/`, `audit/`, base | No | Sin cambios de arquitectura ni de esquema. | — |

**P4.** El camino de pliegos y ofertas **no depende de servicios externos**: la feature no llama a la IA, al Portal ni a internet; todo se calcula con lo ya guardado. Fuentes y marca ya están alojadas (017).

### Cómo se comunican

La vista del inicio, de la portada o del cuadro llama a `sections_for` (dentro de `memo.scope`, como `seccion` hoy) y pasa el `Overview` a `proceso_de`. Cada paso lee solo lo que su regla nombra; lo que dos pasos comparten (la página de la matriz de evaluación, las ofertas, el dictamen) se pide una vez con `memo.once`/`memo.matrix_page`. La respuesta es HTML completo; no hay endpoints de datos nuevos. El sondeo de `recorrido.js` (cada 5 s) sigue llevando el avance y las pestañas en las pantallas con encabezado de procedimiento; la foto de los pasos **no** se sondea (se recalcula al cargar o volver: ADR-0045).

## Modelo de datos

**Sin cambios.** Ninguna tabla, columna, índice ni migración. El estado de un paso, la lista de acciones y «Terminado» se calculan al mostrar. Un test (`tests/journey/proceso/test_sin_esquema.py`) falla si `makemigrations --check --dry-run` detecta algo o si hay un archivo de migración posterior a la 017 en las aplicaciones.

## Cómo se calcula el estado de cada paso (REQ-143 a REQ-145)

### Reglas comunes (aceptadas por el responsable el 2026-11-17: «En curso» para lo que no empezó pero se puede empezar; «Todavía no» para lo que depende de otro paso)

- **R1. Con error**: alguna de las etapas o datos del paso tiene su último pedido fallido sin resultado posterior (los estados `CON_ERROR` que ya calculan las etapas).
- **R2. Hecho** = las condiciones de la tabla «Está Hecho cuando» de la spec **y** ningún pendiente ni acción de cierre abierta del paso. Un paso hecho que recibe algo nuevo vuelve solo a «En curso» (REQ-145), porque ese algo nuevo es una acción abierta o rompe una condición. Los *faltantes* de la tercera tabla de acciones (datos que completar) no cambian el estado (ver N1).
- **R3. En curso**: el paso ya empezó (algo cargado, un pedido corriendo, un borrador) **o** tiene un pendiente o una acción de cierre disponible ahora.
- **R4. Todavía no**: no empezó **y** no tiene ningún pendiente ni acción de cierre disponible (falta lo que la habilita, es decir, depende de otro paso). El texto dice de qué depende (REQ-147).
- **Dependencias** (solo las que la spec o el código ya establecen): 2 necesita el pliego leído (`stages/matriz.py` l. 62-66); 4 necesita matriz validada y ofertas con documentos (`stages/evaluacion.py` l. 51-58); 5 necesita ofertas; 6 necesita alguna evaluación (`stages/matriz_evaluacion.py` l. 68); 7 «se puede cerrar» con 4 y 6 hechos, salvo que el Portal ya tenga un dictamen por aprobar. Los pasos 1 y 3 no dependen de otro.
- La sección **Normativas no es un paso**. Sus pendientes (`temas/s5_normas.py` `status` l. 212-238) salen de `_pending_readings()` (l. 199), que no recibe procedimiento: son de la normativa general. No entran en las acciones; su contador sigue en la pestaña.

### Tabla paso → regla → datos → función que se reutiliza

Las columnas «Datos» nombran modelo y campo. «Función» es la que ya existe; entre corchetes, lo que se agrega.

| Paso | Hecho cuando (spec + R0) | En curso / Todavía no / Con error | Datos (modelo.campo) | Función que se reutiliza |
|---|---|---|---|---|
| **1 Pliego publicado** | Hay un documento vigente `tenders.Document.kind = pliego`; todos los documentos están leídos; el Portal no lista documentos ni circulares sin tomar; no hay propuesta del Portal sin aprobar (sin contar el dictamen); sin pendientes ni acciones de cierre del paso. | **Con error**: etapa `pliego` o `portal` en `CON_ERROR`. **En curso**: lectura corriendo, documentos sin leer, faltantes del Portal o propuesta sin aprobar. **Todavía no**: ningún documento ni propuesta (etapa `pliego` pendiente con «Faltan los documentos del pliego»). | `tenders.Document.kind`, `readings`; `portal.PortalItem.state/kind` | `stages/pliego.py` `compute` (l. 24-61); `stages/portal.py` `compute` (l. 85-133); `temas/s2_documentos.py` `missing_from_portal` (l. 168); `temas/s3_circulares.py` `missing_from_portal` (l. 187); `temas/s1_portal.py` `_counts` (l. 256) [+ consulta de «hay pliego»] |
| **2 Matriz de requisitos** | La última versión no descartada está `validated` y no queda ninguna circular modificatoria sin entrar a una versión validada; sin pendientes ni acciones de cierre del paso. | **Con error**: etapa `matriz` en `CON_ERROR`. **En curso**: proponiendo, versión en borrador, circular modificatoria pendiente o (pliego leído y sin versión: acción «Proponer la matriz»). **Todavía no**: sin versión y pliego sin leer. Con circular pendiente dice: «hay una circular posterior a la matriz» (REQ-145). | `tenders.MatrixVersion.status`, `Requirement.state`, `PendingItem.resolved_at` | `temas/s2_matriz.py` `latest_version` (l. 107); `stages/matriz.py` `compute` (l. 39-83); `tenders/services/circular_version.py` `states` (l. 155) y `pending` (l. 193) |
| **3 Ofertas recibidas** | Hay ofertas; el acta del Portal no tiene ofertas sin agregar; todas las ofertas tienen documentos; ningún documento sin leer (ver «Lo que la spec pide…», punto 3); sin pendientes ni acciones de cierre del paso. | **Con error**: etapa `ofertas` en `CON_ERROR`. **En curso**: lectura corriendo, documentos sin leer, ofertas del acta sin agregar, borradores de oferta o filas de ficha por confirmar. **Todavía no**: sin ofertas, sin ofertas en el acta y sin borradores. | `offers.Offer`, `offers.Document`, `offers.Reading`, `portal.PortalItem(kind=oferta, state=propuesto)` | `stages/ofertas.py` `compute` (l. 100-163); `temas/s3_ofertas.py` `portal_offers` (l. 288) y `status` (l. 482); `offers/services/offers.py` `offer_ids_with_documents` (l. 599) |
| **4 Cumplimiento de cada oferta** | La etapa `evaluacion` está lista (cada oferta con documentos tiene evaluación de la matriz validada vigente); ninguna evaluación dejó afuera un documento vigente de su oferta (punto 3); ninguna oferta con resultado técnico esperando el informe o su ok; sin pendientes ni acciones de cierre del paso. | **Con error**: etapa `evaluacion` en `CON_ERROR`. **En curso**: evaluando, evaluadas solo algunas, documento no tenido en cuenta, informe técnico por subir o por dar el ok. Con matriz validada y ofertas con documentos sin evaluar: acción «Evaluar las ofertas». **Todavía no**: sin matriz validada u ofertas con documentos (texto: «depende de la matriz de requisitos», REQ-147). | `assessment.Run.matrix_version`, `Run.documents`, `Run.built_at`; `assessment.Result.outcome`; `offers.Document.kind = informe_tecnico` | `stages/evaluacion.py` `compute` (l. 34-69); `stages/matriz_evaluacion.py` `_technical_pending_offer_statuses` (l. 47); `temas/s4_informe.py` `status` (l. 139); `tenders/services/validation.py` `latest_validated` |
| **5 Comparación de ofertas** | Todas las ofertas tienen su total y el paso 4 está «Hecho» con la matriz vigente. | **En curso**: hay ofertas y falta algún total, o están todos y el paso 4 no está hecho (texto: «el orden económico está listo; falta completar el cumplimiento»). **Todavía no**: sin ofertas. No tiene acciones propias: dice qué falta y de qué paso depende. Nunca «Con error». | `portal.PortalOfferData.total` de cada `offers.Offer` | `assessment/ordering.py` `economic_order` (l. 233) para el orden mostrado; para «todas tienen total», una consulta a `PortalOfferData` (no `economic_order`, que deja afuera las ofertas descartadas enteras) |
| **6 Evaluación de la Comisión** | Hay alguna oferta evaluada y no quedan pares por decidir, preguntas abiertas ni descartes por resolver; sin pendientes ni acciones de cierre del paso. (Los resultados que esperan el informe técnico cuentan en el paso 4, no acá.) | **En curso**: queda alguna de las tres. **Todavía no**: ninguna evaluación (`matriz_evaluacion` pendiente, l. 68). Nunca «Con error». | `assessment.Result`, `Decision`, `Question.state`, descartes propuestos | `stages/matriz_evaluacion.py` [`counts(page)` extraído de l. 73-77]; `assessment/services/discards.py` `units` |
| **7 Dictamen** | El dictamen está cargado: subido por la Comisión o tomado del Portal y aprobado. | **Con error**: ítem del Portal en `fallido`. **En curso**: hay un dictamen del Portal sin aprobar; o los pasos 4 y 6 están hechos y falta cargarlo; o el mantenimiento vence hoy o ya venció y falta cargarlo. **Todavía no**: lo demás. Exportar la planilla y el cuadro sigue disponible desde la sección 4 sin importar el estado. | `tenders.Document.kind = dictamen`; `portal.PortalItem(payload.clase = dictamen).state` | `temas/s4_dictamen.py` `uploaded_dictamenes` (l. 107), `portal_dictamen` (l. 94), `TAKEN` (l. 66) [`dictamen_cargado` extraído de `context`, l. 207] |

«Terminado» (REQ-150) = `dictamen_cargado`. Un procedimiento sin dictamen es abierto aunque sus otros pasos estén hechos.

### Decisiones del responsable sobre lo que los datos no daban (2026-11-17)

Los cuatro puntos de abajo son la evidencia que se le mostró; cada uno tiene su respuesta en la spec (tabla «Decisiones del responsable») y en la tabla de decisiones que sigue.

1. **«Qué se puede hacer ahora» contra «los pendientes que el sistema ya calcula»** (criterio numérico 2). Los pendientes que el sistema cuenta (`Overview.pending`, la suma de `Section.pending`) no alcanzan para lo que pide la spec: *validar la matriz* con todo confirmado, *cargar el dictamen* y *evaluar las ofertas* **no son pendientes contados**. Evidencia: `stages/matriz.py` l. 77-83 devuelve `A_DECIDIR` con `pending = 0` y el detalle «falta validarla»; `temas/s4_dictamen.py` `status` (l. 176-182) deja «Dictamen: no se cargó» como `Missing`, no como pendiente; `stages/evaluacion.py` l. 60-66 deja «Se evaluaron N de M» como estado `PENDIENTE` (un `Missing` genérico en `sections/base.py` l. 230). Decisión (opción «3. Todo lo que falta»): la lista es **los pendientes de las secciones 1 a 4 (cuentas exactas) más siete acciones de cierre, cada una disparada por un estado que ya existe, más cada faltante que hoy muestra la línea «Hay / Falta»** (tres tablas siguientes). El criterio se prueba de tres maneras: (a) la suma de las cuentas de las líneas que vienen de pendientes es igual a `Overview.pending` menos el de Normativas, en los tres procedimientos de prueba; (b) cada acción de cierre aparece si y solo si su disparador es verdadero; (c) cada faltante aparece si y solo si está en `Section.tema_missing` de las secciones 1 a 4 (el conjunto que `_hay_falta.html` dibuja) y no está ya cubierto por una línea de pendiente o de cierre.
2. **«A decidir» y «puntos a decidir»** (REQ-152, REQ-153 y paso 6). Hoy el sistema cuenta como pendiente **todo par con propuesta sin decisión de una persona, también los propuestos como «cumple»**. Evidencia: `stages/matriz_evaluacion.py` `_undecided_pairs` (l. 38-44) cuenta `cell.state == PENDING`; `review.state_from` (`assessment/services/review.py` l. 99-101) devuelve «propuesto» cuando no hay decisión; `temas/s4_propuesta.py` `_items` (l. 227-239) lista «… cumple propuesto, sin decidir». En cambio la maqueta y los ejemplos de la spec («50 cumplen, 12 a decidir») tratan «A decidir» como «el sistema no pudo concluir» (resultado «no determinado», `_bucket` l. 609-623). Si el paso 6 se calcula como hoy (sin cambiar cómo se evalúa, regla de la spec), un procedimiento con 81 pares propuestos dirá «Decidir 81 puntos», no 12.
3. **«Documentos nuevos sin revisar» y «circulares sin revisar»** (pasos 1, 3 y 4). No existe una marca de «revisado» (ni en `offers.Document` ni en `tenders.Document`; agregar una sería un dato nuevo, que REQ-145 prohíbe). Se puede derivar así: un documento de oferta está **sin revisar** si (a) todavía no tiene lectura (`offers.Reading`; es lo que ya hace la etapa `ofertas`, l. 109-111) o (b) es vigente y **no está en la lista `assessment.Run.documents`** de la última evaluación de su oferta con la matriz vigente (`assessment/models.py` l. 130; `offers/services/document_history.py` `runs_with_withdrawn` l. 234-247 ya lee esa lista). (a) reabre el paso 3 y (b), el paso 4. Una circular está **sin revisar** si el Portal la lista y no se tomó (`s3_circulares.missing_from_portal`) o no se leyó (cae en la etapa `pliego`); si es modificatoria y no entró a una versión validada, reabre el paso 2 (`circular_version.pending`). Lo que **no** se puede saber es si una persona «miró» un documento ya leído y usado: esa persona no deja registro.
4. **Estados de un paso sin trabajo empezado** (R3 y R4). La spec define «Hecho» y da ejemplos de «En curso» y «Todavía no», pero no qué se llama a un paso que no empezó pero tiene una acción disponible (el paso 2 de un procedimiento recién cargado, con el pliego leído y la matriz sin proponer).

| # | Pregunta del plan | Respuesta del responsable (2026-11-17) | Cómo queda en el plan |
|---|---|---|---|
| P1 | ¿Qué entra en «Qué se puede hacer ahora»? | «3. Todo lo que falta»: pendientes contados + siete acciones de cierre + cada faltante del «Hay / Falta» (REQ-147) | Tres tablas de acciones; criterio numérico (a), (b) y (c) |
| P2 | ¿Qué es «A decidir»? | «1. Solo los no determinados»; leyenda «sin confirmar»; acciones del paso 6 partidas en tres (REQ-152) | `_bucket` (`nd` → «A decidir»); acciones del paso 6 partidas |
| P3 | ¿«Sin revisar» se deduce o se marca? | «1. Lo deduce solo» (sin lectura, o no tenido en cuenta por la última evaluación; sin datos nuevos) | Reglas de los pasos 1, 3 y 4 |
| P4 | ¿«En curso» o «Todavía no» para un paso que no empezó pero se puede empezar? | «1. En curso»; «Todavía no» solo para lo que depende de otro paso; el dictamen espera a 4 y 6 salvo mantenimiento vencido o que vence hoy | R2 a R4 |
| P5 | ¿«No aplica» en el cuadro? | «1. Mostrar “No aplica”» (sexto texto, no cuenta en totales) | `_bucket` (`na`) |

Detalle de las opciones que se le ofrecieron (para trazabilidad):

| # | Opciones ofrecidas |
|---|---|
| P1 | A) solo pendientes contados; B) pendientes más siete acciones de cierre; C) B más cada faltante del «Hay / Falta» (elegida: «3. Todo lo que falta»). |
| P2 | A) «A decidir» = no determinado, con «sin confirmar» y acciones partidas en tres (elegida); B) todo par propuesto sin decisión; C) cambiar la regla de evaluación (fuera de alcance). |
| P3 | A) deducirlo (elegida); B) agregar una marca «revisado por» (dato nuevo, exige enmendar REQ-145). |
| P4 | A) «En curso» si se puede empezar (elegida); B) «Todavía no» para todo lo que no empezó. |
| P5 | A) sexto texto «No aplica», sin contar en totales (elegida); B) ocultar esas celdas. |

**Pregunta nueva (N1) · ¿los faltantes cambian el estado de un paso?** Con la opción «Todo lo que falta» aparecen en la lista datos que completar (por ejemplo «Falta el número de expediente», `temas/s1_datos.py` l. 303-304, o «Oferta N: falta la hoja de compliance», `temas/s3_anexos.py` l. 113-116). Si contaran como acción abierta, el paso 1 de un procedimiento cargado desde un pliego sin Portal nunca llegaría a «Hecho» (contradice la tabla «Está Hecho cuando» de la spec) y el paso 3 sin ofertas no sería «Todavía no».
- Opción A: **los faltantes se listan con su paso pero no cambian el estado** (R2 a R4 miran solo pendientes y acciones de cierre). Un paso puede decir «Hecho» y tener un faltante a la vista.
- Opción B: los faltantes cuentan como acción abierta (el estado cambia; hay que enmendar la tabla «Está Hecho cuando»).
- **Recomiendo A.** Este plan se escribió con A. Con B cambiarían de la tabla de 21 estados los pasos 1 y 3 del procedimiento «recién cargado» (tiene faltantes sueltos: sin cronograma y sin ofertas) y habría que rehacerla antes de firmarla.

### Acciones de «Qué se puede hacer ahora» (REQ-147, REQ-149)

**De pendientes** (cuentas exactas; una línea por `(paso, kind)`, con la cuenta sumada, el paso al que pertenece y un botón al lugar donde se resuelve):

| `origen` del renglón | `kind` | Paso | Línea | Botón lleva a |
|---|---|---|---|---|
| `etapa:portal`, `s1_portal` | — | 1 | «Aprobar lo que leyó el sistema del Portal (N)» | `Item.url` (`procedimiento/#s1-propuesta`) |
| `s3_circulares` | — | 2 | «Abrir la versión nueva de la matriz» / «Validar la versión con la circular» | `Item.url` |
| `etapa:matriz`, `s2_matriz` | `req`, `tramo`, `consec` | 2 | «Validar la matriz: N por resolver» | `group_url` (`pliego/?filtro=falta`) |
| `s3_ofertas` | `oferta_borrador`, `oferta_borrador_fallida` | 3 | «Revisar N ofertas subidas…» | `Item.url`/`group_url` |
| `s3_ficha` | `ficha` | 3 | «Confirmar las filas de la ficha» | `Item.url` |
| `s4_informe` | `informe_falta`, `informe_ok` | 4 | «Cargar el informe técnico del área (falta en N ofertas)» / «Dar el ok al informe» | `evaluacion/#s4-informe` (REQ-149, sin pasos intermedios) |
| `s4_propuesta` | `par` | 6 | partido por estado de la celda (decisión P2): «Decidir N puntos no determinados» / «Revisar N “no cumple”» / «Confirmar N propuestas “cumple”» | cuadro con el filtro y la primera celda abierta (REQ-154) |
| `s4_propuesta` | `pregunta` | 6 | «Contestar N preguntas» | `evaluacion/?preg=abiertas#s4-preguntas` |
| `s4_descartes` | `descarte` | 6 | «Resolver N descartes propuestos» | `group_url` |
| `s4_dictamen` | — | 7 | «Aprobar el dictamen publicado en el Portal» | `Item.post` (el mismo POST de siempre) o su `url` |

**De cierre** (la cuenta es 0: no suman al contador; cada una tiene su disparador):

| Acción | Paso | Se muestra si |
|---|---|---|
| Proponer la matriz | 2 | etapa `pliego` lista, no hay versión y no hay pedido corriendo (`stages/matriz.py` l. 62-67) |
| Validar la matriz | 2 | la última versión es borrador y no quedan renglones de la matriz por resolver (si quedan, la línea «Validar la matriz: N por resolver» ya la cubre) |
| Tomar del Portal lo que lista y no se tomó | 1 | `s2_documentos.missing_from_portal` o `s3_circulares.missing_from_portal` no vacíos |
| Agregar las ofertas del acta | 3 | `s3_ofertas.portal_offers` no vacío |
| Evaluar las ofertas | 4 | matriz validada, ofertas con documentos y alguna sin evaluar o con un documento no tenido en cuenta (`stages/evaluacion.py` l. 60-66 y punto 3) |
| Resolver el error: «<motivo>» | el del paso | el paso está «Con error» (el motivo ya lo guarda `Stage.error`) |
| Cargar el dictamen | 7 | `dictamen_cargado` falso y (pasos 4 y 6 hechos, o el mantenimiento vence hoy o ya venció); si el Portal publicó uno sin aprobar, la línea de pendiente lo cubre |

**De faltantes** (cuenta 0; no cambian el estado del paso, N1). Salen de `Section.tema_missing` de las secciones 1 a 4, el mismo conjunto que dibuja `_hay_falta.html`. Una línea por origen, con la cuenta de ofertas o datos entre paréntesis:

| `Missing` (archivo · función) | Paso | Línea | Botón lleva a |
|---|---|---|---|
| `temas/s1_datos.py` `status` (l. 293-312): sin expediente, sin apertura en el cronograma, sin renglones, sin garantías | 1 | «Tomar del Portal lo que falta de los datos (N)» | la URL `take` que ya arma el tema (`procedimiento/#s1-portal`) |
| `temas/s2_documentos.py` `status` (l. 265-271): documentos del Portal que no se pudieron bajar | 1 | «Subir los documentos que no se pudieron bajar» | `pliego/#s2-subir` |
| `temas/s3_anexos.py` `status` (l. 111-116): oferta sin hoja de compliance | 3 | «Subir la hoja de compliance (N ofertas)» | `ofertas/#s3-anexos-oferta-N` (la primera) |
| `temas/s3_ofertas.py` `status` (l. 513-516): «Todavía no hay ofertas» | 3 | «Subir los archivos de una oferta» | `ofertas/?alta=archivos#s3-alta-archivos` |

Los demás `Missing` de las secciones 1 a 4 ya están cubiertos por una línea de pendiente o de cierre y **no se repiten**: «El Portal lista N … que no se tomaron» (`s2_documentos` l. 262, `s3_circulares` l. 253) y «El acta tiene N ofertas sin agregar» (`s3_ofertas` l. 508) son las acciones de cierre «Tomar del Portal…» y «Agregar las ofertas del acta»; «Falta el informe técnico del área» (`s4_informe` l. 162) es el pendiente `informe_falta`; «Dictamen: no se cargó» y «el Portal publicó uno que no se aprobó» (`s4_dictamen` l. 179-182) son la acción «Cargar el dictamen» y el pendiente del dictamen del Portal. Los de la sección 5 (`s5_normas`, `s5_rigen`) no son de un paso (Normativas). El test (c) del criterio numérico verifica esta lista contra `Section.tema_missing`: cada `Missing` está en una línea o en la lista de «cubiertos», y no hay líneas sin `Missing`.

**Orden de las líneas y cuántas se ven.** Primero lo **vencido** (rojo, «Vencido»), después lo que **vence hoy** (lila), después los pendientes, las acciones de cierre y los faltantes, y dentro de cada grupo por número de paso. Se muestran las primeras 6; si hay más, un `<details>` «ver las N restantes» (sin script) con el resto en el mismo orden. En el inicio, expandido un procedimiento, se muestran todas (REQ-151).

Una acción que depende de otra aún no hecha **no se lista**; el paso lo dice en su resumen («Todavía no: depende de la matriz de requisitos»). Las acciones del usuario de lectura no se dibujan: `without_actions` (`views/portada.py` l. 67) ya quita los formularios, y el botón «Cargar/Subir» se omite igual que hoy (`_UPLOAD_LINK`, l. 64).

## Inicio de la aplicación (REQ-150, REQ-151)

- **Redirección actual.** `views/inicio.py` `inicio` (l. 31-42) lleva al último procedimiento visto (cookie `evaluon_ultimo_<id>`) o al más reciente. Se reemplaza por la lista. Se **elimina** `remember`, `_last_opened` y `COOKIE`, y la llamada de `portada.seccion` (l. 139). El usuario sin rol de la Comisión sigue yendo a `queries:screen` desde `/` (l. 34-35: no es parte de este cambio); el inicio completo lo ve quien tiene rol o es lector que entra a `expedientes/`.
- **Lista «Expedientes».** `expedientes/` (`portada.lista`, l. 87-94, nombre de ruta `expedientes:index`) y `/` muestran la **misma** vista nueva; `expedientes.html` desaparece (sus textos «Expedientes» son los de REQ-155). Ninguna ruta se rompe: `expedientes:index` sigue existiendo y `_cabecera.html` l. 8 sigue enlazando «Procedimientos».
- **Qué muestra cada procedimiento abierto** (`<details open>`): nombre y número (`Procedure.subject`, `number`), cantidad de ofertas, la foto de los siete pasos (`_foto_pasos.html`, la misma de la portada), el texto «En curso: …» (los pasos en curso por nombre), «N acciones», y el vencimiento más próximo. Expandido: sus acciones, cada una con paso, texto y botón. Colapsado: la línea y «N acciones» (REQ-151). Sin «Colapsar todos» (no lo pide ningún requisito, P10).
- **Orden** (coherente con «Vencido» y «Vence hoy», REQ-157): primero los procedimientos con algo **vencido sin resolver** (el que venció hace más días, primero), después los que **vencen hoy**, después los de vencimiento futuro por fecha (apertura futura o mantenimiento futuro) y al final los que no tienen fecha; a igual fecha, por número. La columna «vencimiento más próximo» dice «Vencido hace N días», «Vence hoy» o la fecha con los días que faltan, con el color que corresponde. Es una lectura del plan de «ordenados por el vencimiento más próximo»; se confirma en la compuerta.
- **Terminados.** `?ver=terminados` muestra los que tienen dictamen cargado: número, objeto, fecha del dictamen (`tablero/ingreso.py` `dictamen_day`, l. 431) y enlace a su portada. No calcula los siete pasos de esos (son solo una lista). Un dictamen que se quita vuelve el procedimiento a abiertos sin ninguna acción (se calcula cada vez).
- **Abiertos y terminados sin N consultas pesadas.** `lote.py` hace **dos** consultas para todos los procedimientos: documentos vigentes `kind = dictamen` agrupados por procedimiento (misma definición de «vigente» que `document_history.current_documents`, con una variante por lote y test de equivalencia) y los ítems del Portal `payload.clase = dictamen` en `aprobado`/`cargado`. Sobre los abiertos se calcula `proceso_de` **una vez por procedimiento** (cada uno con su `memo.scope`, como `sections_for`). El presupuesto de 2 s con 20 abiertos y la salida prevista si no alcanza están en el ADR-0079; la medición se hace en el corte vertical con 20 copias del caso chico y, una sola vez, con el procedimiento real del piloto (cifras, no datos, al repositorio).

## Portada del procedimiento (REQ-146, REQ-148, REQ-149, REQ-147)

`expedientes/<id>/` deja de redirigir (`portada.portada`, l. 97-106) y dibuja, en este orden: encabezado con camino (`_camino.html`, ya existe) → título y resumen («N ofertas · X pasos hechos, Y en curso, Z sin empezar») → foto de los siete pasos → «Qué se puede hacer ahora» → los siete pasos con un resumen de una línea y, si están en curso, lo que falta con su botón → columna lateral con «Plazos» (de `ingreso.plazos`, REQ-131) y el botón «Abrir indicadores». «Indicadores» es el primer panel actual (`expedientes/<id>/procedimiento/`, sin cambios de contenido, REQ-148): se le agrega el título visible «Indicadores» y un enlace «Volver al proceso». No se crea una ruta nueva.

El destino de cada paso y de cada acción es el lugar de la sección donde se resuelve (REQ-149), con las anclas que ya existen (`#s1-portal`, `#s2-matriz`, `#s3-circulares`, `#s4-informe`, `#s4-dictamen`, `#dictamen-subir`) y los `Item.url`/`group_url` que los temas ya arman. Un test recorre cada acción de los tres procedimientos de prueba y comprueba que su URL responde 200 y que el ancla existe en la página destino.

**Primera pantalla ≤ 15 piezas (criterio numérico 3).** Antes de construir se fija qué es una pieza: **cada elemento con el atributo `data-pieza`** que la plantilla pone en: encabezado (1), camino (1), título con resumen (1), foto de los siete pasos (1), bloque «Qué se puede hacer ahora» (1) y cada línea de acción (1), cada paso (1), «Plazos» (1) e «Indicadores» (1). Con 6 líneas de acción y 2 pasos visibles son 15. Por eso la lista muestra a lo sumo 6 líneas y, si hay más, un `<details>` «ver las N restantes» (decisión de la spec); ese `<details>` es parte del bloque «Qué se puede hacer ahora» y no lleva `data-pieza`, así que no suma. Las líneas ocultas no cuentan (no están a la vista). Se verifica por (a) un test que cuenta los `data-pieza` que quedan antes del tercer paso (≤ 15 con los tres procedimientos de prueba) y (b) la revisión del Coordinador a 1440 × 900 en Edge, una vez (como en la 017).

## «Vence hoy» en lila y «Vencido» en rojo brillante (REQ-157)

- **De dónde salen los vencimientos (REQ-131).** `tablero/ingreso.py` `plazos()` (l. 448-485) ya devuelve los hitos con su estado `now`/`past`/`future`/`pending` según `today()` (l. 215): apertura (`opening_moment`, cronograma del Portal), mantenimiento (`maintenance`, `mantenimiento_oferta` de la última página del Portal guardada, solo en días corridos desde la apertura) y dictamen (sin fecha prevista: solo existe si hay dictamen, o sea cuando el procedimiento ya está terminado). Sin datos nuevos.
- **A qué paso pertenece cada uno.** Apertura de ofertas → paso 3 y la acción «Agregar las ofertas del acta» si está disponible. Vencimiento del mantenimiento → paso 7 y la acción «Cargar el dictamen» (o «Aprobar el dictamen…»). Excepción a R4, necesaria para el criterio de REQ-157 (que no pide los pasos 4 y 6 hechos): si el mantenimiento vence hoy o ya venció y falta el dictamen, el paso 7 está «En curso» y la acción «Cargar el dictamen» aparece aunque 4 y 6 no estén hechos (hoy el sistema deja subir el dictamen en cualquier momento: `temas/s4_dictamen.py` `can_load`, l. 82). Con el procedimiento terminado no hay nada que marcar.
- **Qué puede quedar «vencido sin resolver» y qué no** (decisión del responsable: «Rojo brillante vencido», hasta que se resuelva).
  - **Sí: el mantenimiento de las ofertas vencido y sin dictamen** (`plazos()` lo da en estado `past` con `maintenance.state = computed`). Marca el paso 7 y la acción «Cargar el dictamen» (o «Aprobar el dictamen…») con «Vencido» y los días. Se resuelve cuando el dictamen está cargado: el procedimiento pasa a «Terminados» y la marca desaparece sola. Mañana el que vencía hoy pasa de lila a rojo (REQ-157, criterio).
  - **No: la apertura ya ocurrida.** Es un hecho, no un plazo que se incumple; pasada, se muestra como fecha normal («apertura 20/03, ya ocurrió»). Una apertura que es hoy sí va en lila (paso 3).
  - **No: el dictamen.** No tiene fecha prevista (`ingreso.dictamen_day`, l. 431, solo existe cuando ya está cargado), así que no puede vencer.
  - **No: un mantenimiento sin fecha calculable** (días hábiles o contado desde otro hecho: `maintenance.state = calendar`, «Falta el calendario»): no se puede decir que venció; se muestra el texto actual.
  - Una acción o paso que «pertenece» a un vencimiento vencido no se marca si ya no tiene qué resolver: el rojo y el lila los decide `vencimientos.py` con una sola función (`marca_de(paso_o_accion)` → `vencido`, `hoy` o nada).
- **Rojo brillante `--vencido`** (+ `--vencido-bg`, `--vencido-ink`), token propio y **distinto del rojo de «No cumple» (`--no`, #BE6A64 en claro y #CC7B75 en negro, desaturado)**: más saturado y más luminoso, y con otra forma. «Vencido» es una etiqueta **rellena** (fondo `--vencido`, texto blanco en claro y casi negro en negro) con el texto «Vencido» y los días; «Con error» y «No cumple» son etiquetas **teñidas** con símbolo. Valores de partida calculados por el planificador: claro, fondo `#D10F2F` con texto `#FFFFFF` (5,5:1); negro, fondo `#FF4D5E` con texto `#1A0508` (6,2:1). Los confirma o ajusta `test_contraste.py` (4,5:1 el texto de la etiqueta; 3:1 la marca lateral de la línea contra el fondo de la pantalla), en los dos temas. En el inicio y la portada `--vencido` no se usa para ninguna otra cosa (mismo test que el lila).
- **Cómo se evita la confusión con el lila del estado «externo»** (`--ext`, `tokens.css` l. 57 y 95; usado en `s4_propuesta.css` l. 55-64, `punto.css` l. 18 y `tablero.css` l. 15). (1) Token propio `--hoy` (+ `--hoy-bg`, `--hoy-ink`) con la misma familia de color que la maqueta pero **otro nombre**: así pueden separarse sin tocar el otro. (2) Separación por pantalla: el inicio, la portada y el cuadro no cargan `s4_propuesta.css`, `punto.css` ni usan `--ext*`/`--ev-externo*`; un test lee `proceso.css`, `cuadro.css` y las plantillas nuevas y falla si aparece `--ext` o `ev-externo`, o si `--hoy` o `--vencido` aparecen fuera de `proceso.css` (REQ-157: «en esas pantallas el lila no se usa para ninguna otra cosa»). (3) Separación por forma: «Vence hoy» es una etiqueta de texto con borde sólido y peso 700 sobre fondo `--hoy-bg`; el «externo» es una franja lateral. (4) En el cuadro («Espera informe» y «Sin resultado») no hay lila: se usa el estilo punteado neutro de la maqueta C.
- **Contraste AA en los dos temas.** Valores de partida de la maqueta `e.html`: claro, texto `#4B3A78` sobre `#E6DFF3` (7,4:1 calculado por el planificador); negro, texto `#DCD2F7` sobre `#2F2745` (9,7:1); marca lateral `#8C7AB0` sobre blanco (3,8:1; 3:1 exigido a los gráficos). El par se declara en `tests/journey/test_contraste.py` (ya existe, calcula la razón desde `tokens.css`) y los valores se ajustan hasta que pasen; la etiqueta lleva siempre el texto «Vence hoy» (REQ-156). Los pares de «Vencido» (arriba) se declaran igual.
- **Los estados de los pasos** (REQ-156): barra con relleno negro (`--ink`) para Hecho, lima con borde `--ink` de 1 px para En curso, gris punteado para Todavía no, y `--no` con símbolo para Con error; **siempre con su nombre escrito** al lado. Lima solo resalta, como manda la 017.

## Cuadro de cumplimiento y panel lado a lado (REQ-152 a REQ-154)

- **Ruta y vista.** `expedientes/<id>/cuadro/` (`journey/views/cuadro.py`), con el encabezado de procedimiento y la pestaña «Evaluación y dictamen» marcada. Se llega desde los pasos 4 y 6 (enlace del paso) y desde las líneas de acción del paso 6.
- **Datos.** `memo.matrix_page(user, procedure.pk, channel=SCREEN)` (la misma página que usan el mosaico «Resultado por oferta» y el pendiente): `page.requirements` (filas, agrupadas por `RequirementClass`: formal, económico, técnico), `page.offers` (columnas, con el total de `PortalOfferData`), `page.cells`. **Estado de cada celda** = `_bucket(cell)` (`s4_propuesta.py` l. 609): `ok` → «Cumple»; `no` → «No cumple»; `nd` → «A decidir»; `pe` con `Doubt.PENDIENTE_INFORME_TECNICO` → «Espera informe»; `pe` sin resultado → «Sin resultado»; `na` → «No aplica» (decisión P5; sexto texto, no cuenta en los totales). Una celda `ok` o `no` cuyo `cell.state` es «propuesto» (nadie la confirmó) lleva debajo del texto la leyenda «sin confirmar» (decisión P2). Por eso **los totales del pie coinciden con el mosaico** (misma función): «cuántos requisitos cumple cada oferta hasta ahora» = `ok` por oferta (`_offer_figures`, l. 626).
- **Filtros** (REQ-153), por parámetro `?filtro=`: `todos`, `pendiente` (filas con alguna celda sin decisión de una persona —las «sin confirmar»— o en «A decidir», «Espera informe» o «Sin resultado»), `a-decidir` (solo las celdas no determinadas, decisión P2), `no-cumple`, `espera-informe`. Cada filtro muestra su cantidad de filas. **Un grupo donde todas las celdas son «Cumple»** (de todas las ofertas) se resume en una línea («Formales · 11 de 18 cumplen en las tres ofertas») y se despliega con `<details>`.
- **Panel lado a lado, sin salir del cuadro (REQ-154).** Cada celda es un enlace `?celda=<oferta>-<requisito>&filtro=…#c-<oferta>-<requisito>`. La página dibuja el cuadro a la izquierda y, a la derecha, el panel de la celda elegida: **es el cuerpo de la página del par** (`s4_propuesta_par.html` l. 8-86 extraído a `_par.html`): texto del pliego con su ubicación (`journey/_punto_pliego.html`), texto de la oferta con documento y página (`page.offer_citations`, `_cita_vision.html`), el motivo de la duda (`explanation`, condiciones), el recorrido de decisiones y los mismos formularios (`confirmar`, `corregir`, `rechazar`), con el campo oculto `desde=cuadro`. Sin JavaScript. Panel `position: sticky`; bajo 1000 px de ancho va debajo. «Siguiente a decidir ›» es un enlace a la próxima celda en estado `nd` (o, si no hay, la próxima sin decisión) según el orden del cuadro y el filtro vigente.
- **Cómo se registran las decisiones exactamente igual que hoy (P3, P6).** El formulario envía a `expedientes:s4_decidir` → `s4_propuesta_acciones.decide` (l. 105) → `review.decide(...)` (`assessment/services/review.py` l. 135), el único servicio que escribe la decisión, valida el rol de evaluador, exige motivo para corregir y rechazar, y deja el hecho `eval_decision` con quién y cuándo. Lo único que cambia es `back(...)` (l. 62), que con `desde=cuadro` vuelve al cuadro con la celda y el aviso (hoy con `desde=par` vuelve al par). El operador y el usuario de lectura ven el panel sin botones, como hoy. Las celdas técnicas conservan «Esta fila se decide con el ok del informe técnico» (`s4_propuesta_par.html` l. 53).
- **Dos clics (criterio numérico 4).** Portada → clic 1 en la línea «Decidir 12 puntos…», cuyo enlace es `cuadro/?filtro=a-decidir&celda=<primera>#c-…` → el cuadro ya abre el panel con pliego y oferta lado a lado. Desde la pestaña «Evaluación y dictamen» el camino sigue siendo el de hoy.
- **Rendimiento.** Una carga del cuadro hace lo que hace hoy la sección 4: una `matrix_page` más, solo para la celda elegida, `evaluate.pair_page` y `review.history` (como en `pair`, l. 745-754). Se mide con 60 requisitos × 10 ofertas (≤ 2 s).

## Vocabulario (REQ-155)

Cambios de texto en pantalla. Un test (`tests/journey/test_vocabulario.py`) busca en `evaluon/templates/` y en las cadenas de `evaluon/journey/` las expresiones prohibidas y falla si aparecen como nombre de la lista o de la matriz.

| Dónde | Hoy | Pasa a |
|---|---|---|
| `templates/journey/expedientes.html` l. 4 y 14 (título y `<h1>`) | «Expedientes» | (archivo reemplazado) «Procedimientos» en `inicio.html` |
| `journey/stages/matriz.py` l. 32 `LABEL` (aparece en el renglón genérico «Matriz de cumplimiento: N por decidir») | «Matriz de cumplimiento» | «Matriz de requisitos» |
| `templates/journey/temas/s2_matriz.html` l. 44 (`<h3>`) | «Matriz de cumplimiento» | «Matriz de requisitos» |
| `templates/tenders/matrix.html` l. 14, `matrix_print.html` l. 43, `tenders/_matrix_panel.html` l. 2 | «Matriz de cumplimiento» | «Matriz de requisitos» |
| `templates/assessment/matrix.html` (2 apariciones; se confirma en la tarea cuáles nombran la lista de requisitos y cuáles el cuadro) | «Matriz de cumplimiento» | «Matriz de requisitos» o «Cuadro de cumplimiento» según lo que muestre |
| `temas/s2_matriz.py` l. 585 y 645, `temas/s4_propuesta.py` l. 680, 695, 712: mosaico «Cumplimiento por tipo y oferta» | «Cumplimiento por tipo y oferta» | «Cuadro de cumplimiento (resumen por tipo)», con enlace al cuadro |
| `templates/journey/temas/s4_propuesta.html` l. 9 (`<h3>`) | «Propuesta por oferta y requisito» | «Propuesta del sistema, requisito por requisito» (para que «Cuadro de cumplimiento» nombre una sola cosa) |
| Los siete pasos, en inicio, portada, cuadro («Paso N · …» en acciones) y mosaicos | — | `proceso/pasos.py` (única fuente) |
| Textos «Vuelve al expediente» / «sale del expediente» (`s2_documentos.html` l. 20, 50, 119; `s4_dictamen.html` l. 42, 68) | «expediente» | «procedimiento» |

«Expediente» como **dato** del Portal (número de expediente: `s1_portal.py` l. 352, `_ingreso.html` l. 9, `portal/items/procedimiento.html` l. 7, `nuevo.html` l. 38) **no se cambia**: es el nombre oficial de ese campo, no el de la lista. La spec no lo pide.

## Flujo de IA

No usa IA. Nada del cálculo lo genera un modelo; no hay recuperación, instrucciones ni modelo que cambiar, así que no aplican evals (P7). Todo lo que se muestra con fundamento (cita del pliego, cita de la oferta, dato del Portal) lo trae el panel de la página del par, con la cita que ya tiene (P3).

## Registro de auditoría

- **Decisiones del cuadro**: el mismo servicio que hoy (`review.decide`), con el mismo hecho `eval_decision` (usuario, momento, acción, resultado antes y después, motivo). La prueba de REQ-154 compara el hecho guardado al decidir desde el cuadro con el que guarda `decidir` desde la página del par: mismos campos.
- **Aprobar el dictamen desde la portada**: el POST de siempre del Portal (`s1_portal_decidir`, `approval.decide`), hecho `portal_decision`, como en la 017.
- **Lectura**: inicio, portada y cuadro solo leen. Los rechazos por rol los sigue registrando `stages_for`/`matrix_page` (`require_commission_role`) como hoy; el usuario de lectura ve las pantallas sin acciones.
- **No se registra** el estado de un paso ni el colapso de un procedimiento: son lectura, no evaluación (P6 pide reconstruir lo que el sistema dijo al evaluar; el estado se reconstruye de los mismos datos).

## Rutas

| Ruta | Cambio |
|---|---|
| `/` (`inicio`) | Lista de procedimientos abiertos (el usuario sin rol de la Comisión sigue yendo a `queries:screen`) |
| `expedientes/` (`expedientes:index`) | La misma vista; `?ver=terminados` |
| `expedientes/<id>/` (`expedientes:portada`) | La portada del procedimiento (antes redirigía a `procedimiento/`) |
| `expedientes/<id>/procedimiento/` | Sin cambios de contenido; pasa a llamarse «Indicadores» en pantalla (REQ-148) |
| `expedientes/<id>/cuadro/` (`expedientes:cuadro`) | Nueva: cuadro de cumplimiento con panel (`?filtro=`, `?celda=`) |
| `expedientes/<id>/evaluacion/resultado/<id>/decidir/` | Igual; acepta `desde=cuadro` |
| Todas las demás | Sin cambios |

## Cobertura de requisitos

| Requisito | Cómo se resuelve | Cómo se verifica |
|---|---|---|
| REQ-143 | `proceso/pasos.py` (nombres y orden únicos); `_foto_pasos.html` compartida por inicio y portada; el cuadro y las acciones citan «Paso N · nombre» de la misma tabla | `tests/journey/proceso/test_pasos.py`: los textos de inicio, portada y cuadro contienen los siete nombres en el mismo orden para los tres procedimientos de prueba |
| REQ-144 | Estado propio por paso (reglas R1 a R4 y tabla); sin «paso actual»: no existe ningún campo ni texto «va por el paso N» | `test_tabla_a_mano.py` (21 de 21); `test_varios_en_curso.py`: oferta con documento nuevo sin leer + evaluación sin informe + 12 puntos → pasos 3, 4 y 6 «En curso» a la vez; el HTML no contiene «paso actual» ni «va por el paso» |
| REQ-145 | `proceso_de` calcula todo al mostrar; `circular_version.pending` y `Run.documents` reabren pasos; `test_sin_esquema.py` | `test_reapertura.py`: matriz validada + circular modificatoria cargada → paso 2 «En curso» con «hay una circular posterior a la matriz»; documento agregado a una oferta → paso 3 (sin leer) y, ya leído, paso 4 (no usado por la evaluación); `makemigrations --check` limpio y sin migraciones nuevas |
| REQ-146 | `portada.html`: foto → «Qué se puede hacer ahora» → siete pasos con resumen de una línea y lo que falta con su botón | `test_portada.py` (orden de los bloques en el HTML; cada paso en curso trae su enlace); criterio de ≤ 15 piezas (cuenta de `data-pieza` y revisión a 1440 × 900) |
| REQ-147 | `acciones.py` (reparto, agrupado y acciones de cierre con disparador); la acción que depende de otra no se lista y el paso lo dice (R4) | `test_acciones.py`: procedimiento sin matriz validada con ofertas → aparece «Validar la matriz», ninguna acción de evaluación y el paso 4 dice «Todavía no: depende de la matriz de requisitos»; criterio numérico: (a) suma de cuentas = `Overview.pending` − Normativas, (b) cada acción de cierre aparece si y solo si su disparador, (c) cada faltante aparece si y solo si está en `Section.tema_missing` y no lo cubre otra línea; `test_acciones_orden.py`: vencido, hoy, pendientes, cierre, faltantes, por paso, y a lo sumo 6 líneas a la vista con «ver las N restantes» |
| REQ-148 | `vencimientos.py` + `plazos()` en la columna lateral; botón «Abrir indicadores» a `procedimiento/`, que conserva sus mosaicos | `test_portada.py`: plazos presentes; el enlace lleva a una página con los mismos mosaicos y cifras que antes (se reutilizan los tests de `test_primer_panel.py` sin cambios) |
| REQ-149 | Cada paso y cada acción llevan a la URL/ancla del tema (los `Item.url`, `group_url` y anclas existentes) | `test_destinos.py`: «Cargar el informe técnico del área» → `evaluacion/#s4-informe`, 200 y el ancla existe; se recorren todas las acciones de los tres procedimientos |
| REQ-150 | `views/inicio.py` + `lote.py`; `dictamen_cargado`; se elimina la cookie del último visto | `test_inicio.py`: usuario con la cookie vieja ve la lista, no el procedimiento; cargar el dictamen pasa el procedimiento a «Terminados»; quitarlo lo devuelve; `test_redirects.py` (l. 78-102) actualizado |
| REQ-151 | `<details open>` por procedimiento con la línea y «N acciones»; acciones agrupadas | `test_inicio.py`: cuatro abiertos con 9 acciones → las 9 bajo su procedimiento; colapsado queda la línea y «N acciones» (atributo `open` ausente/presente en el HTML) |
| REQ-152 | `views/cuadro.py`, `cuadro.html`; estado por `_bucket`; pie con `_offer_figures` | `test_cuadro.py`: 27 requisitos y 3 ofertas → 27 filas en 3 grupos y 3 columnas, estado en texto, totales del pie iguales a `figures_of(...)` (los del mosaico «Resultado por oferta») |
| REQ-153 | Filtros `?filtro=`; grupos resumidos | `test_cuadro_filtros.py`: con 12 puntos a decidir, `a-decidir` deja solo filas con una celda «A decidir»; un grupo todo «Cumple» sale en una línea |
| REQ-154 | Panel con `_par.html` (pliego, oferta, motivo, decisiones) y `desde=cuadro`; «Siguiente a decidir» | `test_cuadro_panel.py`: la celda abierta trae el texto del pliego con ubicación, el de la oferta con ubicación y el motivo; decidir deja el mismo hecho `eval_decision` que desde la página del par, la celda cambia y el enlace «Siguiente» apunta a la próxima; criterio de 2 clics |
| REQ-155 | Tabla de «Vocabulario» | `test_vocabulario.py`: ninguna plantilla ni cadena de pantalla contiene «Expedientes» ni «Matriz de cumplimiento» como nombre de lista; los nombres de los pasos no varían |
| REQ-156 | Etiqueta con texto en cada estado (`.est`), pares declarados en `tokens.css` | `test_contraste.py` ampliado con los pares de estado de los pasos y de las celdas en los dos temas (≥ 4,5:1 el texto); `test_estados_con_texto.py`: ninguna marca de estado sin su nombre |
| REQ-157 | `vencimientos.py` sobre `plazos()` (`marca_de`: `hoy`, `vencido` o nada); tokens `--hoy*` y `--vencido*`; etiquetas «Vence hoy» (lila) y «Vencido» (rojo brillante) en el paso o la acción, con el orden del inicio | `test_vence_hoy.py` (con `today()` fijado): mantenimiento que vence hoy y sin dictamen → paso 7 y «Cargar el dictamen»/«Aprobar el dictamen» en lila con «Vence hoy», en inicio y portada; sin vencimientos, nada en lila. `test_vencido.py`: al día siguiente, si sigue faltando, rojo con «Vencido»; con el dictamen cargado, nada (pasa a Terminados); apertura pasada, dictamen y mantenimiento sin fecha calculable, nunca «Vencido»; el inicio ordena vencidos, luego hoy, luego futuros, luego sin fecha. `test_lila_exclusivo.py`: sin `--ext`/`--no` ajenos en las pantallas nuevas y `--hoy`/`--vencido` solo en `proceso.css`; `test_contraste.py` con los pares de las dos etiquetas en los dos temas |

## Criterio numérico y umbrales (escritos antes de construir, ADR-0024 y ADR-0025)

| Qué | Umbral | Con qué se mide | Bloque |
|---|---|---|---|
| Estado de los siete pasos | 21 de 21 (100 %) contra la tabla escrita a mano de este plan (anexo), firmada en la compuerta **antes** de programar | `tests/journey/proceso/test_tabla_a_mano.py`: tres procedimientos de prueba construidos con los fixtures del caso chico (`tests/journey/conftest.py`: `procedure`, `matrix`, `offer`, `two_offers`, `simulate`); la tabla vive en `tests/journey/proceso/tabla_a_mano.py` y nadie la edita sin la firma | B1 |
| Acciones contra pendientes | 100 %: ninguna de más, ninguna de menos | `test_acciones.py` (suma de cuentas = `Overview.pending` − Normativas; cada acción de cierre ⇔ su disparador; cada faltante ⇔ su condición) en los tres procedimientos | B1 |
| Piezas en la primera pantalla | ≤ 15 a 1440 × 900 | `data-pieza` (cuenta, con hasta 6 líneas a la vista) y revisión del Coordinador en Edge, una vez | B2 |
| Clics a pliego y oferta lado a lado | ≤ 2 | `test_cuadro_panel.py` (la acción del paso 6 lleva a un cuadro con el panel de una celda abierta) | B3 |
| Inicio con 20 abiertos | ≤ 2 s | Test con 20 copias del caso chico (mediana de 5 cargas) y, una vez, el piloto real (solo cifras) | B4 y B6 |
| Portada y cuadro | ≤ 2 s con hasta 60 requisitos y 10 ofertas | Test con un procedimiento sintético de ese tamaño y, una vez, el piloto real | B2, B3 y B6 |
| Contraste | 4,5:1 texto; 3:1 íconos y barras; dos temas; incluye «Vence hoy» (`--hoy*`) y «Vencido» (`--vencido*`) | `tests/journey/test_contraste.py` | B2 |
| Sin servicios externos | 0 direcciones externas en plantillas, hojas y SVG nuevos | `tests/journey/test_no_external.py` y `tests/test_sin_externos.py` (ya existen) | todos |
| Funciones de la 014 y la 017 | siguen en verde | Suite completa sobre la rama combinada con `main` | todos |

Máximo dos rondas de ajuste por medición; lo que no llegue pasa a la lista de revisión con su impacto, como en la 017.

## Corte vertical y orden de trabajo

**Corte vertical (ADR-0025).** Con el **caso chico y público** (los fixtures de `tests/journey/conftest.py`; ningún documento de `corpus/casos/` ni del piloto): B1 (tabla a mano y cálculo) + B2 (portada con los siete pasos, acciones y «Vence hoy») + B3 (cuadro con panel, sin filtros). Se mide una vez: 21 de 21, acciones 100 %, piezas ≤ 15, dos clics, contraste, y la revisión del Coordinador en Edge de la portada y del cuadro en los dos temas. Recién entonces se hacen el inicio, los filtros y el vocabulario, y al final el piloto.

Los bloques no son tareas: `tasks.md` los partirá en tareas de una sesión. «Archivos» es lo que escribe cada bloque; **ningún archivo aparece en dos bloques que puedan correr a la vez**. Nada de esta feature toca el esquema de la base ni la configuración compartida, salvo `tokens.css` (solo B2) y `journey/urls.py` (solo B3).

| Bloque | Qué entrega | Depende de | Archivos que escribe |
|---|---|---|---|
| **B0 Tabla a mano** | La tabla de estados del anexo, revisada y firmada por el responsable; sus tres procedimientos descritos en términos de datos | — (previo a programar) | `specs/018-proceso-a-la-vista/plan.md` (anexo) |
| **B1 Cálculo** | `Item.origen`/`Missing.origen`, `counts(page)`, `dictamen_cargado`, `pasos.py`, `calculo.py`, `acciones.py` (pendientes, siete cierres, faltantes, orden y corte de 6), `vencimientos.py` (`marca_de`: hoy / vencido); tabla de 21 estados, acciones y orden probados con el caso chico | B0 | `evaluon/journey/proceso/{__init__,pasos,calculo,acciones,vencimientos}.py`, `evaluon/journey/sections/base.py`, `evaluon/journey/stages/matriz_evaluacion.py`, `evaluon/journey/temas/s4_dictamen.py`, `tests/journey/proceso/*` |
| **B2 Portada** | `portada.html`, `_foto_pasos.html`, `_acciones.html` (6 líneas y `<details>` «ver las N restantes»), `proceso.css`, tokens `--hoy*` y `--vencido*`, vista `portada`, título «Indicadores», guía visual | B1 | `evaluon/journey/views/portada.py` (solo `portada` y `seccion`), `evaluon/templates/journey/{portada,_foto_pasos,_acciones,_ingreso}.html`, `evaluon/static/journey/proceso.css`, `evaluon/static/diseno/tokens.css`, `docs/diseno/guia-visual.md`, `tests/journey/test_contraste.py`, `tests/journey/proceso/test_portada*.py`, `test_vence_hoy.py`, `test_vencido.py`, `test_lila_exclusivo.py`, `test_acciones_orden.py` |
| **B3 Cuadro y panel** | `cuadro.py`, `cuadro.html`, `_par.html` extraído, `desde=cuadro`, enlaces desde los pasos 4 y 6 | B1 (en paralelo con B2: no comparten archivos) | `evaluon/journey/views/cuadro.py`, `evaluon/journey/urls.py`, `evaluon/templates/journey/{cuadro,_par}.html`, `evaluon/templates/journey/temas/s4_propuesta_par.html`, `evaluon/journey/temas/s4_propuesta_acciones.py`, `evaluon/static/journey/cuadro.css`, `tests/journey/proceso/test_cuadro*.py` |
| **— Corte vertical: medición y revisión del Coordinador —** | | B2, B3 | — |
| **B3b Filtros y grupos** | `?filtro=`, grupos resumidos, «Siguiente a decidir» | B3 | `evaluon/journey/views/cuadro.py`, `cuadro.html`, `cuadro.css`, `tests/journey/proceso/test_cuadro_filtros.py` |
| **B4 Inicio** | `lote.py`, `views/inicio.py`, `inicio.html`, `expedientes.html` retirado, cookie eliminada, `test_redirects.py` actualizado | B2 | `evaluon/journey/proceso/lote.py`, `evaluon/journey/views/inicio.py`, `evaluon/journey/views/portada.py` (solo `lista`), `evaluon/templates/journey/{inicio,expedientes}.html`, `evaluon/urls.py`, `tests/journey/test_redirects.py`, `tests/journey/proceso/test_inicio*.py` |
| **B5 Vocabulario** | Cambios de texto de la tabla y `test_vocabulario.py` | B3b, B4 | `evaluon/journey/stages/matriz.py`, `evaluon/templates/journey/temas/{s2_matriz,s4_propuesta,s2_documentos,s4_dictamen}.html`, `evaluon/templates/{tenders,assessment}/*matrix*.html`, `evaluon/journey/temas/{s2_matriz,s4_propuesta}.py` (solo títulos de mosaico), `tests/journey/temas/test_s2_matriz_actions.py`, `tests/journey/test_vocabulario.py` |
| **B6 Medición con el piloto y cierre** | Tiempos con el procedimiento real, ajustes, glosario y tablero | B5 | `docs/glosario.md`, `docs/tablero.md` |

## Verificación contra la constitución

| Principio | Cumple | Nota |
|---|---|---|
| P1 La spec es la fuente | sí | Cada bloque nombra sus REQ; los vacíos de la spec se le preguntaron al responsable y sus respuestas (2026-11-17) están en «Decisiones del responsable sobre lo que los datos no daban»; queda una pregunta nueva, N1. |
| P2 Trazabilidad | sí | Tabla de cobertura; `tasks.md` asociará REQ a cada tarea. |
| P3 El sistema recomienda, la Comisión decide | sí | La portada, el inicio y el cuadro solo leen. Las decisiones siguen siendo `review.decide` y el POST del Portal, con rol, motivo, quién y cuándo. El cuadro muestra «sin confirmar» en lo que nadie confirmó (decisión P2). Lo que no existe se dice («Falta»), no se inventa. |
| P4 Datos | sí | Sin servicios externos ni IA; sin datos nuevos; las pruebas usan el caso chico público y casos inventados; no se abre `corpus/casos/`. |
| P5 Local y reproducible | sí | Sin dependencias, servicios ni pasos manuales nuevos. |
| P6 Auditoría | sí | Mismo servicio y mismo hecho al decidir desde el cuadro; el estado de un paso se reconstruye de los mismos datos. |
| P7 Evals | sí (no aplica) | No cambia recuperación, instrucciones ni modelo. |
| P8 Normativa versionada | sí (no aplica) | No toca normas. |
| P9 Compliance | sí (no aplica) | No infiere hojas de compliance. |
| P10 Simplicidad | sí | Sin tablas, sin marco de interfaz, sin script nuevo; sin «Colapsar todos», sin ruta de «Indicadores», sin caché; solo las siete acciones de cierre que exigen REQ-147 y REQ-157. |
| P11 Compuertas | sí | Plan, ADR y la tabla a mano esperan la aprobación del responsable; los ADR nacen «propuesto». |

## Decisiones

ADR nuevos, en estado «propuesto»:

- **ADR-0078** · El estado de los siete pasos se calcula sobre las secciones y etapas existentes (alternativas: guardar una fase; calcular aparte con consultas propias).
- **ADR-0079** · Inicio de la aplicación: lista de abiertos calculada en el servidor con presupuesto de 2 s y salida prevista (alternativas: cargar cada procedimiento por separado; caché en memoria).

Decisiones del plan que no llegan a ADR (se revierten cambiando una plantilla o una tabla): token `--hoy` propio; panel del cuadro por parámetro de la dirección en lugar de script; «Indicadores» como título del primer panel en lugar de una ruta nueva.

## Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El inicio con 20 abiertos no llega a 2 s (cada `sections_for` hace decenas de consultas; `ingreso._read_term` parsea una página guardada del Portal por procedimiento) | No se cumple el no funcional del inicio | Medir en el corte vertical con 20 copias del caso chico; si pasa de 2 s, aplicar la salida prevista del ADR-0079 (dibujar la lista al instante y traer cada procedimiento por el sondeo `data-poll-url` que ya existe). Sin tocar el cálculo. |
| N1 se contesta con la opción B (los faltantes cambian el estado) | Hay que enmendar «Está Hecho cuando» y rehacer la tabla de 21 estados | El estado se decide en una función por paso; los faltantes ya están separados de los pendientes y de los cierres en `acciones.py`, así que pasar a B es cambiar una condición y la tabla. |
| La lista de acciones crece (pendientes + cierres + faltantes) y el criterio de 15 piezas se rompe | La primera pantalla supera 15 | Tope de 6 líneas a la vista con «ver las N restantes» (decisión de la spec); el `<details>` no suma piezas. |
| El rojo de «Vencido» se confunde con «Con error» o «No cumple» | Se lee mal el estado | Token propio más saturado, etiqueta rellena con texto «Vencido» y días, `--no` solo en etiquetas teñidas con símbolo; test de exclusividad. |
| La detección de «documento no tenido en cuenta por la última evaluación» (`Run.documents`) cuesta una consulta por lote y puede dar un falso «En curso» tras reemplazar un documento | Un paso 4 que vuelve a «En curso» sin que la Comisión haya hecho nada mal | Es lo que pide REQ-145 («documento agregado»); `stale_warnings` (`s3_ofertas.py` l. 470) ya avisa algo parecido. Se prueba con reemplazo y retiro; si molesta, se limita a documentos agregados (no reemplazos). |
| El reparto por `origen` queda desfasado si un tema nuevo agrega pendientes | Una acción sin paso | Un test recorre todos los temas de las secciones 1 a 4 y falla si un renglón queda sin paso (excepto Normativas). |
| 15 piezas en la primera pantalla con muchas líneas de acción | No se cumple en un procedimiento con más de 6 líneas | El criterio se define sobre el procedimiento de la maqueta y los tres de prueba; las acciones se agrupan por tipo, así que 6 líneas es el techo habitual. Se informa en la medición con el piloto. |
| Se rompen tests de la 014/017 que esperan la redirección de `/` y de la portada | Suite en rojo | Se actualizan en B4 (`test_redirects.py` l. 78-102) y B2 (los que siguen `expedientes/<id>/` con `follow=True`); se corre la suite completa en cada bloque. |
| Confusión entre el lila de «Vence hoy» y el de «externo» | Se lee mal el estado | Token propio, separación por pantalla y por forma, y dos tests (ver «“Vence hoy” en lila y “Vencido” en rojo brillante»). |

## Anexo · Tabla de estados escrita a mano (borrador para la firma del responsable antes de programar)

Los tres procedimientos de prueba se arman con el caso chico público. «Recién cargado» = alta desde el pliego, pliego leído, sin circulares, sin matriz, sin ofertas, sin dictamen. «Varios en curso» = la situación de la maqueta A: pliego y matriz hechos; una oferta con un documento nuevo todavía sin leer; evaluación hecha con 12 puntos no determinados, un «no cumple» y 4 preguntas; falta el informe técnico; todas las ofertas con total; sin dictamen. «Todo hecho» = todo lo anterior resuelto y dictamen cargado. Valores escritos desde la spec y las reglas R1 a R4 (aceptadas por el responsable el 2026-11-17), antes de ver el código. Precisiones que fija la tabla: (i) «Recién cargado» tiene faltantes sueltos (sin cronograma ni expediente, sin ofertas) que figuran en «Qué se puede hacer ahora» pero no cambian ningún estado (N1, opción A); (ii) en «Varios en curso», además de lo dicho, quedan propuestas «cumple» sin confirmar, que cuentan en el paso 6 (el contador de hoy las cuenta); (iii) en «Todo hecho» no queda ningún par sin confirmar, ni pendiente, ni cierre, y el mantenimiento no vence ni venció (sin lila ni rojo); (iv) ninguno de los tres tiene un paso «Con error».

| Paso | Recién cargado | Varios en curso | Todo hecho |
|---|---|---|---|
| 1 Pliego publicado | Hecho | Hecho | Hecho |
| 2 Matriz de requisitos | En curso (acción «Proponer la matriz») | Hecho | Hecho |
| 3 Ofertas recibidas | Todavía no | En curso (1 documento sin leer) | Hecho |
| 4 Cumplimiento de cada oferta | Todavía no (depende de la matriz) | En curso (falta el informe técnico) | Hecho |
| 5 Comparación de ofertas | Todavía no (sin ofertas) | En curso (orden económico listo; falta completar el cumplimiento) | Hecho |
| 6 Evaluación de la Comisión | Todavía no (sin evaluación) | En curso (puntos por decidir, 1 «no cumple», 4 preguntas) | Hecho |
| 7 Dictamen | Todavía no | Todavía no (depende de los pasos 4 y 6) | Hecho |

Pruebas adicionales fuera de las 21 (cada una con su criterio por requisito): matriz validada + circular modificatoria (paso 2 «En curso», REQ-145); matriz sin validar con ofertas (paso 4 «Todavía no: depende de la matriz», acción «Validar la matriz», REQ-147); mantenimiento que vence hoy y sin dictamen (paso 7 y acción en lila), el mismo al día siguiente (rojo «Vencido») y con el dictamen cargado (sin marca), REQ-157; y un procedimiento con un paso «Con error» (R1).
