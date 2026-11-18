# Tareas 018 · El proceso a la vista

Plan: `specs/018-proceso-a-la-vista/plan.md` (aprobado el 2026-11-17 por el responsable, con la tabla de 21 estados firmada y los ADR 0078, 0079 y 0080 aceptados)

Despliegue: pendiente

> El tablero (`docs/tablero.md`) se genera de este archivo. Al aprobarse el despliegue, la línea de arriba pasa a `Despliegue: aprobado AAAA-MM-DD`.

Estados: pendiente · en curso · en verificación · terminada · bloqueada

Dos tareas que no dependen entre sí y no comparten archivos se pueden hacer en paralelo.

**Ritmo de trabajo (ADR-0024 y ADR-0025).** Las ramas de tarea no tocan este archivo ni el tablero: el Coordinador los actualiza una vez por lote. La verificación de cada tarea queda en `specs/018-proceso-a-la-vista/verificacion/T-NNN.md`. Cada tarea declara su nivel: **plena** (lógica, datos, decisiones registradas o principios de la constitución) o **liviana** (cambio acotado con un test que falla antes y pasa después). Toda medición escribe antes su umbral y tiene dos rondas como máximo; los hallazgos se corrigen en una sola tarea y se mide una vez por lote; lo que no llegue pasa, con su impacto, a la lista de revisión. Con tareas en paralelo, cada desarrollador corre solo los tests de su área; la suite completa la corre el Coordinador una vez por oleada, sobre la rama combinada con `main` (ADR-0012). Commits de código: `T-NNN (REQ-NNN): qué cambia`. Ninguna tarea toca el esquema de la base (no hay migraciones en esta feature: lo vigila T-342). La auditoría y el despliegue son etapas del flujo, no tareas.

**IDs.** T-340 a T-361. En `main` el último ID usado es T-339. El Coordinador confirma contra las ramas abiertas antes de lanzar.

**Nombres de los siete pasos** (REQ-143, decisión del responsable): 1 Carga de pliego, 2 Matriz de requisitos de pliego, 3 Recepción de ofertas, 4 Cumplimiento de ofertas (matriz), 5 Comparación de ofertas, 6 Evaluación Comisión, 7 Dictamen. Salen de `proceso/pasos.py` (T-343); ninguna otra tarea escribe esos textos a mano.

## Oleadas de paralelismo

Dentro de una oleada las tareas no dependen entre sí ni comparten archivos. Una oleada empieza cuando terminaron (verificadas e integradas) las tareas de las que depende. Máximo sugerido en paralelo: tres desarrolladores.

| Oleada | Tareas | Qué habilita |
|---|---|---|
| 1 | T-340 (fixtures de los tres procedimientos), T-342 (refactors sin cambio de comportamiento), T-343 (pasos y vencimientos) | Base de B1. T-340 responde la duda de si el caso chico alcanza |
| 2 | T-341 (la tabla de 21 estados como test, antes del cálculo), T-344 (acciones), T-347 (tokens y hoja `proceso.css`) | T-341 y T-344 esperan a la oleada 1; T-347 no depende de nada |
| 3 | T-345 (pasos 1 a 3), T-349 (geometría del mapa), T-351 (panel del par reutilizable) | T-345 espera a T-344; T-349 y T-351 no dependen de nada anterior |
| 4 | T-346 (pasos 4 a 7: pasa 21 de 21), T-352 (cuadro con panel) | T-346 espera a T-345; T-352 a T-351 y T-343 |
| 5 | T-348 (portada) | Espera a T-346 y T-347 |
| 6 | T-350 (mapa del proceso), T-353 (enlaces al cuadro y destinos) | T-350 espera a T-348, T-349 y T-347; T-353 a T-348 y T-352 |
| 7 | T-354 (medición del corte vertical, sin código) | Umbrales escritos antes |
| 8 | T-355 (filtros del cuadro), T-356 (abiertos y terminados por lote) | Archivos disjuntos |
| 9 | T-357 (inicio) | Espera a T-356 y a T-348 |
| 10 | T-358 (vocabulario) | Espera a T-355 y T-357 |
| 11 | T-359 (cierre técnico: guía visual y glosario) | Un solo escritor de la guía |
| 12 | T-360 (medición final con el piloto, sin código) | Una sola vez |
| 13 | T-361 (correcciones de la medición; condicional) | Cierre |

**Cadenas** (nunca dos a la vez): `calculo.py`, T-345 y después T-346; `acciones.py` y `pasos.py`, T-344 y T-343, y después T-353; `tokens.css`, `test_contraste.py`, T-347 y después T-350; `portada.html`, T-348 y después T-350; `portada.py`, T-348 y después T-357; `cuadro.py`, `cuadro.html`, `cuadro.css`, T-352 y después T-355; `docs/diseno/guia-visual.md`, T-347, T-350 y T-359; `tests/journey/test_redirects.py`, `test_sections.py` y `test_roles.py`, T-348 y después T-357; `journey/urls.py`, solo T-352; `sections/base.py`, solo T-342.

## Definiciones compartidas (escritas antes de lanzar)

Lo que varias tareas necesitan igual. Si una tarea necesita cambiarlas, lo informa; no lo decide sola.

1. **Contrato de `proceso/pasos.py`** (lo escribe T-343): `Estado` con los cuatro valores y sus textos «Hecho», «En curso», «Todavía no», «Con error»; `PASOS`, una tupla de siete con `numero`, `clave` (`pliego`, `matriz`, `ofertas`, `cumplimiento`, `comparacion`, `evaluacion`, `dictamen`) y `nombre`; `Accion` (`id` estable `"<paso>-<tipo>-<kind>"`, `paso`, `tipo` = `pendiente` | `cierre` | `faltante`, `texto`, `cuenta`, `boton`, `url`, `post`, `marca`); `Paso` (`numero`, `nombre`, `estado`, `dato`, `resumen`, `espera`, `advertencias`, `tareas`, `marca`, `destino`); `Proceso` (`procedure`, `pasos`, `acciones`, `terminado`, `vencimiento`). `Paso.tareas` contiene los mismos objetos `Accion` que `Proceso.acciones` (REQ-158).
2. **Entrada del cálculo.** `proceso_de(user, procedure, overview=None) -> Proceso` (T-345 lo crea, T-346 lo completa). Se llama una sola vez por pedido; las plantillas solo recorren `Proceso` y no calculan estados, conteos ni tareas.
3. **Atributos de plantilla.** `data-pieza` marca las piezas que cuenta el criterio de 15 piezas (encabezado, camino, título, mapa con su línea de plazos como una sola, bloque «Qué se puede hacer ahora», cada línea de acción, cada paso de la lista). `data-accion="<id de Accion>"` va en cada tarea, en el mapa, en la lista y en las acciones.
4. **Tokens.** `--hoy`, `--hoy-bg`, `--hoy-ink` (lila, «Vence hoy») y `--vencido`, `--vencido-bg`, `--vencido-ink` (rojo brillante, «Vencido») los define T-347; `--mapa-nodo`, `--mapa-nodo-n`, `--mapa-punto` los define T-350. Ninguna otra hoja nombra `--hoy` ni `--vencido` (lo vigila `test_lila_exclusivo.py`). Las pantallas nuevas no usan `--ext*` ni `ev-externo`.
5. **Geometría del mapa** (T-349): `LIENZO = (1130, 740)`, `ANCHO = 172`, `ALTO = 240`, `POSICIONES = {1: (10, 140), 2: (245, 140), 3: (245, 490), 4: (480, 250), 5: (715, 490), 6: (715, 10), 7: (950, 250)}`, `CONECTORES = ((1,2), (2,4), (3,4), (3,5), (4,5), (4,6), (4,7), (6,7))`. Posiciones por clases `pos-1` … `pos-7` (sin `style=`).
6. **Fixtures.** Solo las existentes (`tests/conftest.py`, `tests/journey/conftest.py`, `tests/assessment/conftest.py`, `tests/offers/conftest.py`) más las que agrega T-340 en `tests/journey/proceso/conftest.py` (`caso_recien_cargado`, `caso_varios_en_curso`, `caso_todo_hecho`). Solo datos públicos o inventados; no se abre `corpus/casos/` (P4).
7. **Reparto por `origen`.** `Item.origen` y `Missing.origen` (T-342): `etapa:<clave>` para los renglones genéricos de una etapa y la clave del tema para los de un tema. Un renglón sin paso hace fallar el test de T-344.
8. **Los bloques no renombran ni quitan** `status()`, `context()`, `PARTIAL` ni funciones públicas de los temas existentes. `s4_propuesta._bucket` es la definición única del estado de una celda; no se duplica.
9. **Tests existentes.** La portada deja de redirigir a `procedimiento/` (T-348) y la lista «Expedientes» pasa a ser el inicio (T-357): esas dos tareas actualizan los tests de la 014/017 que cambian, y solo las líneas que fallan por ese motivo.

## Umbrales de las mediciones (escritos antes de medir)

Los del plan, «Criterio numérico y umbrales». T-354, T-360 y T-361 se miden contra esta lista.

| Qué | Umbral | Con qué se mide |
|---|---|---|
| Estado de los siete pasos | 21 de 21 contra la tabla firmada del anexo del plan | `test_tabla_a_mano.py` (T-341, se pone en verde en T-346) |
| Acciones contra lo que el sistema calcula | 100 %: suma de líneas de pendientes = contador menos Normativas; cierres y faltantes si y solo si su condición | `test_acciones.py` (T-344) |
| Piezas en la primera pantalla | 15 o menos a 1440 × 900 (el mapa cuenta como una) | Cuenta de `data-pieza` y revisión del Coordinador en Edge, una vez |
| Clics de la portada a pliego y oferta lado a lado | 2 o menos | `test_destinos.py` (T-353) |
| Mapa | 0 conectores tapados; alto de tarjeta dentro del presupuesto; misma fuente que la lista | `test_mapa_geometria.py`, `test_mapa_misma_fuente.py` |
| Inicio con 20 abiertos | 2 s o menos | Test con 20 copias del caso chico (mediana de 5 cargas) y, una vez, el piloto real |
| Portada y cuadro | 2 s o menos con hasta 60 requisitos y 10 ofertas | Test con un procedimiento sintético de ese tamaño y, una vez, el piloto real |
| Contraste | 4,5:1 texto; 3:1 íconos, barras y conectores; dos temas; incluye `--hoy*`, `--vencido*` y los tokens del mapa | `tests/journey/test_contraste.py` |
| Sin servicios externos | 0 direcciones externas | `tests/journey/test_no_external.py` y `tests/test_sin_externos.py` |
| Funciones de la 014 y la 017 | siguen en verde | Suite completa sobre la rama combinada con `main` |

## Resumen

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-340 | Armar los fixtures de los tres procedimientos de la tabla con el caso chico | REQ-144, REQ-145 | — | terminada |
| T-341 | Escribir la tabla de 21 estados como test, antes del cálculo | REQ-143, REQ-144 | T-340 | terminada |
| T-342 | Preparar el cálculo sin cambiar comportamiento (origen de renglones, cuentas públicas, dictamen cargado, guarda de esquema) | REQ-145, REQ-147 | — | terminada |
| T-343 | Crear los tipos y nombres de los siete pasos y la marca de vencimientos | REQ-143, REQ-157 | — | terminada |
| T-344 | Calcular las acciones: pendientes, cierres, faltantes, orden y corte de 6 | REQ-146, REQ-147, REQ-157 | T-340, T-342, T-343 | terminada |
| T-345 | Calcular el estado de los pasos 1 a 3 y armar `proceso_de` | REQ-144, REQ-145 | T-342, T-343, T-344 | terminada |
| T-346 | Calcular los pasos 4 a 7, datos, resúmenes y advertencias; pasar 21 de 21 | REQ-143, REQ-144, REQ-145, REQ-146, REQ-147 | T-341, T-345 | terminada |
| T-347 | Definir los tokens de «Vence hoy» y «Vencido» y la hoja `proceso.css` | REQ-156, REQ-157 | — | terminada |
| T-348 | Dibujar la portada: acciones, lista de pasos, advertencias e «Indicadores» | REQ-143, REQ-144, REQ-146, REQ-147, REQ-148, REQ-157 | T-346, T-347 | terminada |
| T-349 | Escribir la geometría constante del mapa y los hitos de la línea de plazos | REQ-158 | — | terminada |
| T-350 | Dibujar el mapa del proceso, la línea de plazos y el selector Mapa / Lista | REQ-146, REQ-148, REQ-156, REQ-157, REQ-158 | T-347, T-348, T-349 | terminada |
| T-351 | Extraer el panel del par para reutilizarlo y aceptar `desde=cuadro` | REQ-154 | — | terminada |
| T-352 | Dibujar el cuadro de cumplimiento con el panel lado a lado | REQ-143, REQ-152, REQ-154, REQ-156 | T-343, T-351 | terminada |
| T-353 | Llevar pasos y acciones al lugar donde se resuelven (cuadro incluido) | REQ-149, REQ-154 | T-348, T-352 | terminada |
| T-354 | Medir el corte vertical con el caso chico y revisar con el Coordinador | REQ-144, REQ-146, REQ-152, REQ-154, REQ-158 | T-350, T-353 | terminada |
| T-355 | Agregar filtros, grupos resumidos y «Siguiente a decidir» al cuadro | REQ-153, REQ-154 | T-354 | pendiente |
| T-356 | Separar abiertos y terminados con dos consultas | REQ-150 | T-354 | pendiente |
| T-357 | Reemplazar la entrada y la lista «Expedientes» por el inicio | REQ-143, REQ-150, REQ-151, REQ-157 | T-348, T-356 | pendiente |
| T-358 | Unificar el vocabulario en pantalla | REQ-155 | T-355, T-357 | pendiente |
| T-359 | Cierre técnico: guía visual y glosario | REQ-156, REQ-157, REQ-158 | T-358 | pendiente |
| T-360 | Medición final con el procedimiento del piloto y revisión visual | REQ-143 a REQ-158 | T-359 | pendiente |
| T-361 | Corregir los hallazgos de la medición final (condicional) | los que correspondan | T-360 | pendiente |
| T-362 | Corregir los hallazgos del corte vertical en el cuadro y en Indicadores | REQ-149, REQ-152, REQ-154, REQ-156 | T-354 | terminada |
| T-363 | Rehacer las tarjetas del mapa: más anchas, tareas sin recorte y alto según el contenido | REQ-146, REQ-158 | T-354 | pendiente |

## Detalle

### T-340 · Armar los fixtures de los tres procedimientos de la tabla con el caso chico

- **Requisitos:** REQ-144, REQ-145 (la prueba de los 21 estados).
- **Nivel:** liviana (solo tests; deja el repositorio verde).
- **Qué hay que hacer:** con los fixtures existentes (`procedure`, `matrix`, `offer`, `two_offers`, `simulate`, `make_run`, `make_offer`) construir `caso_recien_cargado`, `caso_varios_en_curso` y `caso_todo_hecho` tal como los describe el anexo del plan (pliego leído; matriz validada; una oferta con un documento sin leer; evaluación hecha con puntos no determinados, un «no cumple», preguntas, propuestas «cumple» sin confirmar y sin informe técnico; totales del acta de todas las ofertas; dictamen cargado en el último). Para cada uno, una prueba comprueba **con las etapas y temas que ya existen** (`stages_for`, `s4_dictamen.uploaded_dictamenes`, `memo.matrix_page`) que las condiciones de datos de la tabla se dan. **Si el caso chico no alcanza** (por ejemplo, no hay filas técnicas para «falta el informe técnico», no hay datos del acta para «todas las ofertas con total», o no hay forma de dejar un documento sin leer), la tarea lo informa con lo que falta y propone el arreglo mínimo en el propio `conftest.py`; no cambia el plan.
- **Archivos:** `tests/journey/proceso/__init__.py`, `tests/journey/proceso/conftest.py`, `tests/journey/proceso/test_fixtures_tres_casos.py`.
- **Verificación:** `pytest tests/journey/proceso/test_fixtures_tres_casos.py` (los tres casos arman y cumplen sus condiciones de datos); `verificacion/T-340.md` dice si el caso chico alcanzó.
- **No tocar:** código de producto, `tests/journey/conftest.py` y los demás fixtures.

### T-341 · Escribir la tabla de 21 estados como test, antes del cálculo

- **Requisitos:** REQ-143, REQ-144.
- **Nivel:** plena (es el criterio numérico de la feature).
- **Qué hay que hacer:** copiar la tabla firmada del anexo del plan como datos (`TABLA` con los nombres nuevos de los pasos) y escribir el test que arma cada caso con T-340, llama a `proceso_de` y compara los 21 estados. El test usa `pytest.importorskip("evaluon.journey.proceso.calculo")` para no romper el repositorio hasta que exista el cálculo; **T-346 no cierra hasta que este test corre y pasa 21 de 21** (no puede quedar saltado). La tabla no se edita sin la firma del responsable.
- **Aviso de tareas anteriores:** De T-340: los tres fixtures (`caso_recien_cargado`, `caso_varios_en_curso`, `caso_todo_hecho`) crean el mismo procedimiento, así que un test no puede pedir dos a la vez ni combinarlos con `procedure` o `matrix`. «Varios en curso» usa dos ofertas: de sus 12 no determinados, 6 son filas técnicas que esperan el informe (paso 4) y 6 son dudas para la Comisión (paso 6). El caso chico no tiene mantenimiento cargado: la precisión «no vence ni venció» y la cuenta «1 de 3 documentos sin leer» se fijan en T-341.
- **Archivos:** `tests/journey/proceso/tabla_a_mano.py`, `tests/journey/proceso/test_tabla_a_mano.py`.
- **Verificación:** `pytest tests/journey/proceso/test_tabla_a_mano.py` queda saltado antes de T-345 y debe dar 21 pasadas en T-346; un chequeo propio verifica que la tabla tiene 7 filas × 3 casos y los siete nombres de `pasos.py`.
- **No tocar:** el cálculo y el plan.

### T-342 · Preparar el cálculo sin cambiar comportamiento

- **Requisitos:** REQ-145, REQ-147.
- **Nivel:** plena (toca el cálculo de pendientes de la 013/014).
- **Qué hay que hacer:** (1) `Item.origen` y `Missing.origen` con valor por omisión; `build_section` los completa (`etapa:<clave>` para los renglones de una etapa, la clave del tema para los de un tema) y `group_items`/`group_missing` los copian al renglón agrupado. (2) `matriz_evaluacion.counts(page)` público (pares, preguntas, informes técnicos, descartes) que usa `compute`. (3) `s4_dictamen.dictamen_cargado(procedure)` con las funciones que ya usa `context`, y `context` la usa. (4) Guarda de esquema: test que falla si `makemigrations --check --dry-run` detecta algo o si hay una migración nueva en las apps.
- **Archivos:** `evaluon/journey/sections/base.py`, `evaluon/journey/stages/matriz_evaluacion.py`, `evaluon/journey/temas/s4_dictamen.py`, `tests/journey/proceso/test_origen.py`, `tests/journey/proceso/test_counts_sin_cambio.py`, `tests/journey/proceso/test_dictamen_cargado.py`, `tests/journey/proceso/test_sin_esquema.py`.
- **Verificación:** `pytest tests/journey/proceso/test_origen.py test_counts_sin_cambio.py test_dictamen_cargado.py test_sin_esquema.py` más los tests de la 013/014/017 de sus áreas (`tests/journey/test_stage_*.py`, `tests/journey/test_sections.py`, `tests/journey/temas/test_s4_*.py`) sin cambios en su resultado; el estado y los textos de `matriz_evaluacion.compute` son iguales antes y después (test que compara).
- **No tocar:** el resto de `stages/`, los demás temas, plantillas.

### T-343 · Crear los tipos y nombres de los siete pasos y la marca de vencimientos

- **Requisitos:** REQ-143, REQ-157.
- **Nivel:** plena.
- **Qué hay que hacer:** crear el paquete `evaluon/journey/proceso/` con `pasos.py` (contrato de las Definiciones, con los siete nombres nuevos y su sección destino por omisión) y `vencimientos.py` (`marca_de(paso_o_accion, plazos, hoy)` → `"hoy"`, `"vencido"` o `""`; apertura → paso 3; mantenimiento → paso 7 y su acción de dictamen; el vencido solo para el mantenimiento con fecha calculable sin dictamen; apertura pasada, dictamen y mantenimiento sin fecha nunca «Vencido»; `proximo(plazos)` para el inicio). Reutiliza `tablero/ingreso.py` `plazos()` y `today()`.
- **Archivos:** `evaluon/journey/proceso/__init__.py`, `evaluon/journey/proceso/pasos.py`, `evaluon/journey/proceso/vencimientos.py`, `tests/journey/proceso/test_pasos.py`, `tests/journey/proceso/test_vencimientos.py`.
- **Verificación:** `pytest tests/journey/proceso/test_pasos.py test_vencimientos.py`: siete nombres exactos y en orden; con `today()` fijado, mantenimiento hoy → `hoy`, ayer → `vencido`, con el dictamen cargado → nada, apertura pasada → nada, estado `calendar` → nada.
- **No tocar:** `tablero/ingreso.py`, plantillas.

### T-344 · Calcular las acciones

- **Requisitos:** REQ-146, REQ-147, REQ-157.
- **Nivel:** plena.
- **Qué hay que hacer:** `acciones.py` arma, desde el `Overview` y el `memo.matrix_page`, las líneas de «Qué se puede hacer ahora»: (a) **pendientes** de las secciones 1 a 4 repartidos por `origen` y agrupados por `(paso, kind)` con la cuenta sumada, y el `par` partido por `_bucket` en «Decidir N puntos no determinados» / «Revisar N “no cumple”» / «Confirmar N propuestas “cumple”»; (b) las **siete acciones de cierre** con su disparador; (c) los **faltantes** de `Section.tema_missing` (s1_datos, s2_documentos, s3_anexos, s3_ofertas), sin repetir los cubiertos por pendiente o cierre, cada `Missing` como una advertencia del paso; (d) el **orden** (vencido, vence hoy, pendientes, cierre, faltantes; por paso) y el corte de 6 con «ver las N restantes». Normativas queda fuera. El estado de «pasos 4 y 6 hechos» llega como parámetro. Los enlaces de las líneas del paso 6 usan por ahora el `group_url` existente (T-353 los lleva al cuadro).
- **Aviso de tareas anteriores:** De T-340: en «Varios en curso» el paso 6 tiene 6 puntos no determinados (no 12): los otros 6 son filas técnicas que esperan el informe y cuentan en el paso 4. Las filas técnicas resueltas siguen figurando como `propuesto`; hay que excluirlas igual que `_undecided_pairs`. De T-342: `Item.origen` y `Missing.origen` valen `etapa:<clave>` para los renglones de una etapa y la clave del tema para los de un tema; `matriz_evaluacion.counts(page)` devuelve `Counts(pairs, questions, reports, discards)` con `.pending` (`reports` cuenta ofertas con el ok técnico pendiente, no informes). De T-343: el id de una acción es `"<número de paso>-<tipo>-<kind>"`; usar las constantes `KIND_DICTAMEN` y `KIND_ACTA` de `pasos.py`, que `marca_de` reconoce. Pasar a `marca_de` y a `proximo` el valor real `dictamen_cargado=` del procedimiento (`s4_dictamen.dictamen_cargado`): si se deduce de los plazos, un dictamen del Portal sin aprobar se lee como cargado y se pierde la marca. Falta un test con `ingreso.plazos()` real (hoy los plazos se arman a mano con las claves `apertura` y `dictamen`).
- **Archivos:** `evaluon/journey/proceso/acciones.py`, `tests/journey/proceso/test_acciones.py`, `tests/journey/proceso/test_acciones_orden.py`.
- **Verificación:** `pytest tests/journey/proceso/test_acciones.py test_acciones_orden.py`: (a) suma de cuentas = `Overview.pending` − Normativas en los tres casos; (b) cada cierre ⇔ su disparador; (c) cada faltante ⇔ su condición y está en `Section.tema_missing`; ningún renglón de las secciones 1 a 4 queda sin paso; «Validar la matriz» y ninguna acción de evaluación con matriz sin validar y ofertas cargadas; orden y corte de 6.
- **No tocar:** `calculo.py`, plantillas, `sections/base.py` (solo lo lee).

### T-345 · Calcular el estado de los pasos 1 a 3 y armar `proceso_de`

- **Requisitos:** REQ-144, REQ-145.
- **Nivel:** plena.
- **Qué hay que hacer:** `calculo.py` con `proceso_de(user, procedure, overview=None)` (llama a `sections_for` si no recibe el `Overview`, una vez; llama a `acciones.py`) y las reglas R1 a R4 de los pasos 1, 2 y 3 según la tabla del plan: paso 1 (documento `pliego` vigente, lectura, faltantes del Portal, propuesta del Portal); paso 2 (`latest_version`, `circular_version.pending`, texto «hay una circular posterior a la matriz»); paso 3 (ofertas, ofertas del acta sin agregar, documentos sin leer, borradores, fichas). Cada paso trae `estado`, `dato`, `resumen`, `espera` y sus `tareas`. Los pasos 4 a 7 devuelven por ahora «Todavía no» con `espera` vacío (los completa T-346).
- **Aviso de tareas anteriores:** De T-343: `Estado.value` es una clave (`hecho`, `en_curso`, `todavia_no`, `con_error`) y `Estado.texto` es lo que se muestra («Hecho», «En curso», «Todavía no», «Con error»). Decisión del Coordinador: la clave queda para clases de CSS y el texto para pantalla; el test de la tabla de 21 estados compara por `texto`. `DefPaso.seccion` da el destino por omisión de cada paso (1 y 2 pliego; 3 ofertas; 4, 6 y 7 evaluación; 5 procedimiento). De T-344: usar `acciones.armar(user, procedure, overview, *, pasos_4_y_6_hechos=False, plazos=None, hoy=None, dictamen_cargado=None)` (devuelve las acciones ordenadas y con `marca`), `acciones.lista(...)` (`Lista(todas, visibles, restantes)`, corte de 6) y `acciones.advertencias(overview)` (`{paso: [textos]}`) para llenar `Paso.tareas` y `Paso.advertencias`. Las advertencias no incluyen los faltantes que ya cubre un pendiente o un cierre. Sin pliego leído no hay ninguna línea «cargar el pliego»: el resumen del paso 1 tiene que decirlo. Un `Missing` de etapa (origen `etapa:*`) no genera línea ni advertencia.
- **Archivos:** `evaluon/journey/proceso/calculo.py`, `tests/journey/proceso/test_pasos_1_a_3.py`, `tests/journey/proceso/test_reapertura.py`.
- **Verificación:** `pytest tests/journey/proceso/test_pasos_1_a_3.py test_reapertura.py`: matriz validada + circular modificatoria → paso 2 «En curso» con el texto; documento agregado a una oferta → paso 3; los estados de los pasos 1 a 3 de `test_tabla_a_mano.py` pasan.
- **No tocar:** pasos 4 a 7, `acciones.py`, plantillas.

### T-346 · Calcular los pasos 4 a 7, datos, resúmenes y advertencias

- **Requisitos:** REQ-143, REQ-144, REQ-145, REQ-146, REQ-147.
- **Nivel:** plena.
- **Qué hay que hacer:** completar `calculo.py`: paso 4 (etapa `evaluacion`, resultados que esperan informe o su ok, documento vigente no usado por la última evaluación comparando con `Run.documents`, reutilizando `current_documents_by_offer` por tipo), paso 5 (`PortalOfferData.total` de cada oferta y paso 4 «Hecho»), paso 6 (`matriz_evaluacion.counts`; «D de T puntos decididos» desde las celdas no técnicas), paso 7 (`dictamen_cargado`, excepción de REQ-157 con el mantenimiento vencido o que vence hoy). Completa `dato`, `resumen`, `espera` y `advertencias` de los siete pasos y `Proceso.terminado`/`vencimiento`. Sin porcentajes ni «N de M tareas».
- **Aviso de tareas anteriores:** De T-340: un «no cumple» formal saca la oferta de `ordering.economic_order` (`page.order.totals` trae 1 de 2). «Todas las ofertas tienen su total» se cuenta con `PortalOfferData`, nunca con `len(order.totals)`. De T-342: `s4_dictamen.dictamen_cargado(procedure, uploaded=None, portal=...)` es la única fuente de «dictamen cargado». `tests/journey/proceso/test_sin_esquema.py` tiene una tabla fija de la última migración por aplicación: si entra a main una migración legítima de otra feature, hay que actualizarla a propósito. De T-341: `tests/journey/proceso/test_tabla_a_mano.py` queda saltado mientras no exista `evaluon/journey/proceso/calculo.py` con `proceso_de(user, procedure)`; debe devolver un objeto con `.pasos` (siete, con `numero`, `nombre` y `estado`) y SIN atributo `paso_actual`. El test compara por `estado.texto`. T-346 no cierra hasta que los 21 estados corran y pasen, no saltados. La tabla solo compara estados: los detalles («1 documento sin leer») son documentación; `test_mantenimiento_no_vence_ni_vencio` solo comprueba que el mantenimiento no es calculable en el caso chico. De T-344: para «documento no tenido en cuenta por la última evaluación» usar la misma regla que `acciones._sin_usar`: con `Run.documents` registrado (formato de `evaluate.py`, clave `document`), falta el documento vigente que no figura, sin contar el informe técnico; con la lista vacía (fixtures), se compara `loaded_at` con `built_at`. «Evaluar las ofertas» no se ofrece con una evaluación corriendo. El cierre «Cargar el dictamen» necesita `pasos_4_y_6_hechos` real.
- **Archivos:** `evaluon/journey/proceso/calculo.py`, `tests/journey/proceso/test_pasos_4_a_7.py`, `tests/journey/proceso/test_varios_en_curso.py`.
- **Verificación:** `pytest tests/journey/proceso/` completo: `test_tabla_a_mano.py` pasa **21 de 21**, no saltado; `test_varios_en_curso.py` (pasos 3, 4 y 6 «En curso» a la vez, ninguna cadena «paso actual»); REQ-147: matriz sin validar con ofertas → paso 4 «Todavía no: depende de la matriz de requisitos»; las 4 y 5 de paso 5 («orden económico listo; falta completar el cumplimiento»).
- **No tocar:** pasos 1 a 3 (salvo un error), `acciones.py`, plantillas.

### T-347 · Definir los tokens de «Vence hoy» y «Vencido» y la hoja `proceso.css`

- **Requisitos:** REQ-156, REQ-157.
- **Nivel:** liviana.
- **Qué hay que hacer:** en `tokens.css`, `--hoy`, `--hoy-bg`, `--hoy-ink` y `--vencido`, `--vencido-bg`, `--vencido-ink` en los dos temas (valores de partida del plan; el test de contraste los confirma o ajusta). `proceso.css` con las etiquetas de estado (Hecho, En curso, Todavía no, Con error, con el texto siempre escrito), «Vence hoy» (lila), «Vencido» (rojo relleno, distinto de `--no`), advertencias y las líneas de acción. Documentar los tokens en la guía visual.
- **Archivos:** `evaluon/static/diseno/tokens.css`, `evaluon/static/journey/proceso.css`, `docs/diseno/guia-visual.md`, `tests/journey/test_contraste.py`, `tests/journey/proceso/test_lila_exclusivo.py`.
- **Verificación:** `pytest tests/journey/test_contraste.py tests/journey/proceso/test_lila_exclusivo.py tests/test_sin_externos.py`: pares `--hoy*` y `--vencido*` ≥ 4,5:1 (texto) y 3:1 (marcas) en claro y negro; `--hoy` y `--vencido` solo aparecen en `proceso.css` (y `mapa.css` cuando exista); sin `--ext*` ni `ev-externo` en las hojas y plantillas nuevas.
- **No tocar:** otros tokens, hojas de otras pantallas.

### T-348 · Dibujar la portada: acciones, lista de pasos, advertencias e «Indicadores»

- **Requisitos:** REQ-143, REQ-144, REQ-146, REQ-147, REQ-148, REQ-157.
- **Nivel:** plena.
- **Qué hay que hacer:** `portada.portada` deja de redirigir y dibuja encabezado, camino, título con resumen y «Abrir indicadores», «Qué se puede hacer ahora» (6 líneas, `<details>` «ver las N restantes», `data-pieza`), la lista de los siete pasos con resumen, «N advertencias» con su detalle, lo que falta con su botón y las marcas «Vence hoy» / «Vencido». `seccion` deja de llamar a `inicio.remember` (la cookie se elimina en T-357). `_foto_pasos.html` (la barra) se crea para el inicio. El primer panel recibe el título visible «Indicadores» y un enlace «Volver al proceso» sin cambiar su contenido. El espacio del mapa queda reservado para T-350. Actualizar los tests de la 014/017 que esperan que la portada redirija, solo en las líneas que fallan por eso.
- **Aviso de tareas anteriores:** De T-347: `evaluon/static/journey/proceso.css` ya tiene las clases `pr-estado` (hecho, en-curso, todavia-no, con-error), `pr-hoy`, `pr-vencido`, `pr-advertencia`, `pr-accion` (con `.hoy` y `.vencido`) y `pr-restantes`: usalas tal cual. La hoja no puede obligar a que la etiqueta diga «Vence hoy» o «Vencido»: eso lo comprueba un test de plantilla acá (REQ-156). `test_lila_exclusivo.py` empieza a vigilar `portada.html`, `_acciones.html` y `_foto_pasos.html` cuando existan. De T-345 y T-346: `calculo.proceso_de(user, procedure, overview=None)` devuelve `Proceso(procedure, pasos, acciones, terminado, vencimiento)`; cada `Paso` trae `estado`, `dato`, `resumen`, `espera`, `tareas` (los mismos objetos de `Proceso.acciones`), `advertencias` y `marca`. Si la portada ya calculó el `Overview`, pasalo para no repetir `sections_for` y medí las consultas (con el `Overview` dado eran 15 / 45 / 21 antes de sumar los pasos 4 a 7). El dato del paso 6 es «D de T puntos decididos» y T incluye los «cumple» y «no cumple» sin confirmar (en «varios en curso»: «0 de 12», mientras las acciones dicen decidir 6, revisar 1 y confirmar 5): mostrá el desglose para que se entienda. El dato del paso 4 suma las cifras de todas las ofertas e incluye las filas técnicas (18 contra 12): revisá que no confunda. Los textos de `dato` y `resumen` no están fijados por ningún test: fijá con un test los que muestres. Paso 7 «Con error» por un dictamen del Portal fallido no tiene acción cuando los pasos 4 o 6 no están hechos: mostrá el motivo igual. Con un dictamen subido y otro del Portal sin aprobar, `terminado` es verdadero y el paso 7 queda «En curso».
- **Archivos:** `evaluon/journey/views/portada.py` (solo `portada` y `seccion`), `evaluon/templates/journey/portada.html`, `evaluon/templates/journey/_acciones.html`, `evaluon/templates/journey/_foto_pasos.html`, `evaluon/templates/journey/_ingreso.html`, `tests/journey/proceso/test_portada.py`, `tests/journey/proceso/test_portada_acciones.py`, `tests/journey/proceso/test_vence_hoy.py`, `tests/journey/proceso/test_vencido.py`, `tests/journey/proceso/test_advertencias.py`, y, solo las líneas que dependen de la portada, `tests/journey/test_camino.py`, `test_moments.py`, `test_redirects.py`, `test_roles.py`, `test_sections.py`, `test_window.py`, `tests/journey/temas/test_s1_portal.py`.
- **Verificación:** `pytest tests/journey/proceso/test_portada*.py test_vence_hoy.py test_vencido.py test_advertencias.py` y los tests actualizados: orden de bloques; los pasos en curso traen su enlace; pliego leído sin número de expediente → «Hecho» y «1 advertencia» con «Falta el número de expediente» y la misma línea en las acciones; mantenimiento que vence hoy → paso 7 y «Cargar el dictamen» en lila, mañana en rojo con «Vencido», con el dictamen nada; más de 6 líneas muestran 6 y «ver las N restantes»; «Abrir indicadores» lleva a los mismos mosaicos; el usuario de lectura no ve botones de acción.
- **No tocar:** `lista` de `portada.py` (T-357), el mapa, `inicio.py`.

### T-349 · Escribir la geometría constante del mapa y los hitos de la línea de plazos

- **Requisitos:** REQ-158.
- **Nivel:** liviana (Python puro, con test que falla antes).
- **Qué hay que hacer:** `mapa.py` con las constantes de la Definición 5, el presupuesto de alto de una tarjeta (relleno 22 + encabezado 36 + dato 34 + pie 30 + 3 tareas × 30 + «+ N más» 26), `trazo(origen, destino)` (borde derecho a `y + 28`, codo de radio 12 en el hueco entre columnas, entrada por el borde izquierdo, punta de flecha) calculado una vez al importar, y `hitos_en_eje(events)` (posición proporcional a la fecha, segundo nivel si dos hitos quedan a menos de 12 %, los hitos sin fecha como texto aparte).
- **Archivos:** `evaluon/journey/proceso/mapa.py`, `tests/journey/proceso/test_mapa_geometria.py`, `tests/journey/proceso/test_mapa_hitos.py`.
- **Verificación:** `pytest tests/journey/proceso/test_mapa_geometria.py test_mapa_hitos.py`: las siete tarjetas caben en el lienzo y no se superponen; ningún tramo de conector corta una tarjeta (12 px de margen) salvo en el borde de su origen o destino; los conectores son exactamente los ocho; el presupuesto de alto ≤ `ALTO`; hitos con y sin fecha, solapados y `hoy` fuera de rango.
- **No tocar:** plantillas, hojas de estilo.

### T-350 · Dibujar el mapa del proceso, la línea de plazos y el selector Mapa / Lista

- **Requisitos:** REQ-146, REQ-148, REQ-156, REQ-157, REQ-158.
- **Nivel:** plena.
- **Qué hay que hacer:** `_mapa.html` (una `<ol>` de siete tarjetas con número, nombre, dato, estado escrito, hasta 3 tareas y «+ N más», advertencias y «espera» distinguidas, texto oculto «Depende de …»; SVG de conectores `aria-hidden`, lleno si el paso de origen está «Hecho» y punteado si no), `_plazos.html` (apertura, hoy, mantenimiento y dictamen si tiene fecha; el motivo en texto cuando falta una fecha), `mapa.css` (clases `pos-1` … `pos-7` iguales a las constantes, una línea por tarea con puntos suspensivos, regla de menos de 900 px que oculta mapa y selector, foco visible), los tokens `--mapa-*` en los dos temas, el selector `?vista=mapa|lista` sin estado guardado, y la inclusión en `portada.html`. Sin barra de avance ni porcentaje. Todo lo lee de `Proceso`.
- **Aviso de tareas anteriores:** De T-349: `mapa.TRAZOS` trae los ocho conectores con su `d`; el test de la plantilla debe comparar el `d` dibujado con `mapa.TRAZOS` (hoy ningún test valida el `d` completo). 4→5, 4→6 y 4→7 comparten los primeros 31 px y 4→7 y 6→7 confluyen en la entrada de la 7: si con tarjetas llenas se lee confuso, diferenciar el trazo. El presupuesto de alto es 238 de 240 px (2 de holgura): comprobar en el navegador que el texto real no desborda. `mapa.css` debe declarar las mismas posiciones que `mapa.POSICIONES`, con test. De T-347: tokens `--hoy` (#7A4FD0 claro, #A98BFF negro) y `--vencido` (#D10F2F claro, #FF4D5E negro) con sus `-bg` e `-ink`; `--hoy` está a ΔE ≥ 20 de `--ext` por test. Los tokens `--mapa-*` todavía no existen: los define esta tarea con su par de contraste. `mapa.css`, `_mapa.html` y `_plazos.html` quedan vigilados por `test_lila_exclusivo.py` al crearse; la etiqueta con texto se prueba en la plantilla. De T-348: la portada (`views/portada.py`, `portada.html`) dibuja «Qué se puede hacer ahora» (`_acciones.html`, 6 líneas y `<details>`) y los siete pasos; el lugar del mapa es un comentario de plantilla arriba de las acciones. `proceso_de` se llama UNA vez por pedido con el `overview` de la vista (un test cuenta 1 / 0 / 1 llamadas): el mapa tiene que usar ese mismo `Proceso`, sin calcular de nuevo. La hoja de la disposición es `portada.css` (solo `var(--…)`); los rótulos de botón son el verbo de la línea y las comillas son « » en toda la pantalla (hay tests). La primera pantalla tiene 11 piezas sin el mapa. `_foto_pasos.html` existe para el inicio y la portada no lo usa.
- **Archivos:** `evaluon/templates/journey/_mapa.html`, `evaluon/templates/journey/_plazos.html`, `evaluon/templates/journey/portada.html`, `evaluon/static/journey/mapa.css`, `evaluon/static/diseno/tokens.css`, `docs/diseno/guia-visual.md`, `tests/journey/test_contraste.py`, `tests/journey/proceso/test_mapa.py`, `tests/journey/proceso/test_mapa_misma_fuente.py`, `tests/journey/proceso/test_mapa_vista.py`.
- **Verificación:** `pytest tests/journey/proceso/test_mapa*.py tests/journey/test_contraste.py tests/journey/test_no_external.py`: siete tarjetas con el estado de su fila de la lista; líneas llenas las que salen de un paso «Hecho»; hasta 3 tareas y «+ N más»; ni «%» ni barra de avance en el HTML; plazos con apertura, hoy y vencimiento, y el motivo si falta una fecha; una sola llamada a `sections_for` y a `proceso_de` por pedido y los `data-accion` de mapa, lista y acciones coinciden; `?vista=lista` no trae mapa, ni cookies ni escrituras; `mapa.css` contiene la regla de 900 px y las posiciones iguales a las constantes; contraste de los tokens del mapa en los dos temas.
- **No tocar:** `mapa.py` (T-349), `calculo.py`, `acciones.py`.

### T-351 · Extraer el panel del par para reutilizarlo y aceptar `desde=cuadro`

- **Requisitos:** REQ-154.
- **Nivel:** plena (toca la ruta que registra las decisiones; el servicio no cambia).
- **Qué hay que hacer:** extraer el cuerpo de `s4_propuesta_par.html` (el bloque `cuerpo`) a `_par.html` con la variable `desde` («par» por omisión) y hacer que la página lo incluya sin cambiar nada visible. `s4_propuesta_acciones.decide` y `back` aceptan `desde=cuadro` y vuelven a `cuadro/?celda=<oferta>-<requisito>&filtro=…` con el aviso; `review.decide` no se toca.
- **Archivos:** `evaluon/templates/journey/_par.html`, `evaluon/templates/journey/temas/s4_propuesta_par.html`, `evaluon/journey/temas/s4_propuesta_acciones.py`, `tests/journey/proceso/test_par_parcial.py`.
- **Verificación:** `pytest tests/journey/proceso/test_par_parcial.py tests/journey/temas/test_s4_propuesta.py tests/assessment/`: la página del par produce el mismo HTML de antes; una decisión con `desde=cuadro` deja el mismo hecho `eval_decision` (usuario, momento, acción, resultado, motivo) que con `desde=par`; sin rol de evaluador se rechaza igual y queda el hecho.
- **No tocar:** `assessment/services/review.py`, `s4_propuesta.py`.

### T-352 · Dibujar el cuadro de cumplimiento con el panel lado a lado

- **Requisitos:** REQ-143, REQ-152, REQ-154, REQ-156.
- **Nivel:** plena.
- **Qué hay que hacer:** `views/cuadro.py` y la ruta `expedientes/<id>/cuadro/` (`expedientes:cuadro`); requisitos en filas agrupados por tipo, ofertas en columnas con su total, estado de cada celda por `_bucket` («Cumple», «No cumple», «A decidir», «Espera informe», «Sin resultado», «No aplica»; «sin confirmar» debajo de «Cumple» y «No cumple» que nadie confirmó), pie con los cumplidos por oferta (los mismos de `figures_of`), celdas como enlaces `?celda=`, panel con `_par.html` (`desde=cuadro`) a la derecha, debajo bajo 1000 px. Los nombres de los pasos vienen de `pasos.py`. Sin lila en el cuadro.
- **Aviso de tareas anteriores:** De T-351: el contexto del panel sale de `s4_propuesta.par_context(request, procedure, offer_id, requirement_id, *, desde='par', filtro=None)` (ids, no objetos; devuelve el dict del panel sin `shell` ni `section`; valida `filtro` contra `s4_propuesta_acciones.FILTROS_CUADRO`: importala, no la redefinas; levanta `Http404` si el requisito no está evaluado para la oferta o la oferta es de otro procedimiento). Llamala con `desde='cuadro'` y el filtro vigente e incluí `journey/_par.html`. Registrá la ruta `<int:procedure_id>/cuadro/` con nombre `cuadro` y agregá un test que compare `reverse('expedientes:cuadro')` con la dirección que arma `s4_propuesta_acciones.cuadro_url` (hoy la arma con la portada más `cuadro/`). El regreso tras decidir termina en `?celda=<oferta>-<requisito>[&filtro=…]&aviso=…#s4-aviso`: el cuadro tiene que dibujar el panel siempre que haya `?celda=` y deserializar `aviso` con `acciones.unpack`. Validá que `celda` sean dos números separados por un guion y que oferta y requisito sean del procedimiento (404 si no); si la celda ya no existe tras una evaluación nueva, mostrá el cuadro sin panel. El rol de lectura puro recibe 403 en la página del par hoy: en el cuadro, el panel sin botones lo ve el operador.
- **Archivos:** `evaluon/journey/views/cuadro.py`, `evaluon/journey/urls.py`, `evaluon/templates/journey/cuadro.html`, `evaluon/static/journey/cuadro.css`, `tests/journey/proceso/test_cuadro.py`, `tests/journey/proceso/test_cuadro_panel.py`.
- **Verificación:** `pytest tests/journey/proceso/test_cuadro.py test_cuadro_panel.py`: 27 requisitos y 3 ofertas → 27 filas en 3 grupos y 3 columnas, estado en texto, totales del pie iguales a los del mosaico «Resultado por oferta»; la celda abierta trae el texto del pliego con su ubicación, el de la oferta con su ubicación y el motivo; decidir deja el hecho de siempre y la celda cambia; el usuario de lectura ve el panel sin botones; tiempo ≤ 2 s con 60 requisitos y 10 ofertas sintéticos.
- **No tocar:** filtros y «Siguiente a decidir» (T-355), `pasos.py`, `acciones.py`.

### T-353 · Llevar pasos y acciones al lugar donde se resuelven (cuadro incluido)

- **Requisitos:** REQ-149, REQ-154.
- **Nivel:** liviana.
- **Qué hay que hacer:** que los pasos 4 y 6 enlacen al cuadro y las líneas `par` del paso 6 lleven a `cuadro/?filtro=a-decidir&celda=<primera>#c-…`; ajustar `destino` de los siete pasos a las anclas existentes. Se cierra la lista de destinos de la portada.
- **Aviso de tareas anteriores:** De T-344: las tres líneas del paso 6 (decidir, revisar «no cumple», confirmar «cumple») apuntan hoy al `group_url` de siempre, que no filtra por tipo de celda: llevarlas al cuadro con su filtro. «Tomar del Portal lo que falta de los datos» apunta a `/expedientes/nuevo/`; el plan decía `procedimiento/#s1-portal`. Un par pendiente con celda `pe` o `na` se cuenta en «Decidir N puntos no determinados»: revisar el texto. De T-346: `acciones.py` solo ofrece «Resolver el error» para etapas, no para el ítem del Portal con el dictamen fallido (l. 322-325): el paso 7 «Con error» queda sin acción. Faltan dos tests de `calculo.py`: que las filas técnicas quedan fuera de «D de T» y el caso «dictamen subido + Portal sin aprobar» → paso 7 «En curso». `calculo.py` usa `s3_circulares._states` (privado). De T-348: «Tomar del Portal lo que falta de los datos» lleva a `/expedientes/nuevo/` (alta de un procedimiento nuevo), que no es el lugar del procedimiento que se mira. El paso 5 lleva a `procedimiento/` (Indicadores) y los pasos 1 y 2 a `pliego/` sin ancla. La línea «Falta leer N documento de la Oferta X» enlaza a `ofertas/#s3-anexos-oferta-N`. En «Indicadores» el `<h2>` queda antes del `<h1>` del primer panel. De T-350: los destinos de las tarjetas del mapa son los de las acciones; «+ N más» lleva a `#paso-N` de la lista. La advertencia de una tarjeta («2 advertencias») no es enfocable ni lleva a donde se resuelve: revisar junto con la del paso «Hecho» de la lista. Falta comprobar que exista cada ancla de destino (`#s4-informe` y demás): hasta ahora solo se verificó que la página responde 200. De T-352: la ruta es `expedientes:cuadro` (`<id>/cuadro/`); cada celda tiene el ancla `c-<oferta>-<requisito>` (enlace si hay resultado, `span` si no) y se abre con `?celda=<oferta>-<requisito>[&filtro=…]`. Llevá las tres líneas del paso 6 al cuadro con su filtro y la primera celda abierta. `s4_propuesta_acciones.cuadro_url` puede pasar a `reverse('expedientes:cuadro')`. `_money` (de `s4_descartes`) y `_bucket` (de `s4_propuesta`) son privados importados por la vista del cuadro: conviene exponerlos con nombre público.
- **Archivos:** `evaluon/journey/proceso/pasos.py`, `evaluon/journey/proceso/acciones.py`, `tests/journey/proceso/test_destinos.py`.
- **Verificación:** `pytest tests/journey/proceso/test_destinos.py tests/journey/proceso/test_acciones.py`: cada acción y cada paso de los tres casos responde 200 y el ancla existe; «Cargar el informe técnico del área» llega a `evaluacion/#s4-informe`; de la portada al panel de una celda a decidir con pliego y oferta lado a lado hay un solo clic (criterio de 2 o menos).
- **No tocar:** `calculo.py`, plantillas.

### T-354 · Medir el corte vertical con el caso chico y revisar con el Coordinador

- **Requisitos:** REQ-144, REQ-146, REQ-152, REQ-154, REQ-158.
- **Nivel:** plena (sin código).
- **Qué hay que hacer:** medir contra los umbrales de este archivo: 21 de 21, acciones 100 %, piezas ≤ 15 con el mapa como una, mapa sin conectores tapados, dos clics, contraste, tiempos de portada y cuadro con el caso chico, y la revisión visual del Coordinador en Edge de portada (mapa y lista), cuadro y panel en los dos temas, con el caso de la maqueta A y uno de 3 tareas más advertencias. Máximo dos rondas. Los hallazgos se corrigen en una sola tarea previa a la oleada 8.
- **Aviso de tareas anteriores:** De T-350: medir también a 1000, 1024 × 768 y 1100 px (entre 900 y 1241 px el mapa se desplaza dentro de su caja con una pista escrita; por debajo de 900 se ve la lista). El mapa con sus plazos mide unos 1.000 px de alto y «Qué se puede hacer ahora» empieza a unos 1.430 px del tope a 1440 × 900. Revisar en Edge: desplazamiento con flechas del teclado dentro de la caja, anillo de foco, táctil, y el rango 1242 a 1258 px, donde la tarjeta 7 asoma hasta 7 px sin pista. Pendiente de decisión del responsable (H3): las tareas largas se recortan con puntos suspensivos y el texto completo solo está en `title` y en la lista; las tarjetas tienen 41 a 53 % de blanco por el alto fijo. La leyenda dice «punteada» y el trazo es de rayas. De T-353: de la portada al panel lado a lado hay 1 clic («Decidir N puntos no determinados» abre el cuadro con la primera celda «A decidir»). Recorridos 51 destinos con los tres roles: todos 200 y con su ancla. Falta reverificar el enlace al documento original dentro del panel para el rol de solo lectura (en T-352 se reemplazó por texto).
- **Archivos:** `specs/018-proceso-a-la-vista/verificacion/T-354.md`.
- **Verificación:** el informe con cada umbral, su medida y su resultado.
- **No tocar:** código.

### T-355 · Agregar filtros, grupos resumidos y «Siguiente a decidir» al cuadro

- **Requisitos:** REQ-153, REQ-154.
- **Nivel:** plena.
- **Qué hay que hacer:** `?filtro=` con `todos`, `pendiente`, `a-decidir` (solo no determinados), `no-cumple`, `espera-informe`, cada uno con su cantidad de filas; los grupos donde todas las celdas son «Cumple» se resumen en una línea con `<details>`; enlace «Siguiente a decidir ›» a la próxima celda no determinada (o, si no hay, la próxima sin decisión) según el filtro.
- **Aviso de tareas anteriores:** De T-352: hoy `?filtro=` solo se conserva en los enlaces y en el regreso; todavía no filtra las filas. «Siguiente a decidir» tiene que seguir el orden del cuadro (grupo y fila), no el número de requisito. Con «A decidir» solo para lo no determinado, el caso «varios en curso» tiene 6 celdas «A decidir» y 6 «Espera informe» (no 12 a decidir). La leyenda «sin confirmar» está en 11 px: subila a 12. El panel de una celda «No aplica» dice «Falta su decisión» (texto de `_par.html`). El hilo de siete pasos del cuadro muestra solo nombres; con `calculo.proceso_de` ya en main podría mostrar estados. De T-353: «Decidir N puntos no determinados» cuenta también pares «sin resultado» y «No aplica», pero el filtro `a-decidir` mostrará solo lo no determinado: la cuenta de la línea y las filas del filtro pueden no coincidir; alinear la cuenta, el texto o el filtro. «Confirmar N propuestas «cumple»» usa `filtro=pendiente`, que también mostrará los no determinados. Si no hay celdas «A decidir», la línea usa `filtro=pendiente`. De T-362: en el cuadro con muchas ofertas la tabla se desplaza dentro de su caja, pero la columna del requisito NO queda fija (a 1280 px con 10 ofertas sale de vista) y la caja no da ninguna pista de que se desplaza (la barra queda al pie de 60 filas): fijar la primera columna y dar la pista. `_par.html` y `_cita_vision.html` aceptan `sin_original` (por omisión no cambia nada); falta un test de la rama `sin_original` de `_cita_vision.html` con una cita leída por visión. Los tests de CSS del cuadro leen el texto del archivo, no un renderizado.
- **Archivos:** `evaluon/journey/views/cuadro.py`, `evaluon/templates/journey/cuadro.html`, `evaluon/static/journey/cuadro.css`, `tests/journey/proceso/test_cuadro_filtros.py`.
- **Verificación:** `pytest tests/journey/proceso/test_cuadro_filtros.py tests/journey/proceso/test_cuadro.py tests/journey/proceso/test_cuadro_panel.py`: con 12 puntos a decidir, «A decidir» deja solo las filas con una celda «A decidir»; un grupo todo «Cumple» sale en una línea; «Siguiente» avanza al próximo punto y conserva el filtro.
- **No tocar:** `urls.py`, `_par.html`.

### T-356 · Separar abiertos y terminados con dos consultas

- **Requisitos:** REQ-150.
- **Nivel:** plena.
- **Qué hay que hacer:** `lote.py` con `abiertos_y_terminados()` que usa dos consultas para todos los procedimientos (documentos vigentes de tipo dictamen agrupados por procedimiento y dictámenes del Portal aprobados o cargados) y devuelve los identificadores; la definición de «vigente» es la de `document_history.current_documents` (test de equivalencia con `dictamen_cargado` de T-342).
- **Aviso de tareas anteriores:** De T-346: un procedimiento con dictamen subido y otro del Portal sin aprobar tiene `terminado` verdadero y el paso 7 «En curso»: decidir en qué lista va (por REQ-150, en «Terminados»). `proceso_de` cuesta 71 / 110 / 111 consultas por procedimiento incluyendo `sections_for` (60 / 91 / 93): con 20 abiertos el presupuesto de 2 s está en riesgo (ADR-0079).
- **Archivos:** `evaluon/journey/proceso/lote.py`, `tests/journey/proceso/test_lote.py`.
- **Verificación:** `pytest tests/journey/proceso/test_lote.py`: coincide con `dictamen_cargado` procedimiento por procedimiento (subido, del Portal aprobado, del Portal sin aprobar, retirado, restituido); número de consultas constante con 20 procedimientos.
- **No tocar:** vistas y plantillas.

### T-357 · Reemplazar la entrada y la lista «Expedientes» por el inicio

- **Requisitos:** REQ-143, REQ-150, REQ-151, REQ-157.
- **Nivel:** plena.
- **Qué hay que hacer:** `/` y `expedientes/` muestran la misma vista: procedimientos abiertos, cada uno en un `<details open>` con nombre y número, ofertas, la barra de siete pasos (`_foto_pasos.html`), los pasos en curso por nombre, «N acciones» y su vencimiento más próximo («Vencido hace N días», «Vence hoy» o la fecha); expandido, sus acciones con paso, texto y botón. Orden: vencidos, vencen hoy, futuros por fecha, sin fecha. `?ver=terminados` lista los terminados sin calcular sus pasos. Se elimina la cookie del último visto (`remember`, `_last_opened`, `COOKIE`); el usuario sin rol sigue a `queries:screen` desde `/`. Se retira `expedientes.html`. Actualizar los tests de la 014/017 que cambian, solo las líneas que fallan por eso.
- **Aviso de tareas anteriores:** De T-348: la sección ya no llama a `inicio.remember` (nadie escribe la cookie del último procedimiento) pero `inicio.py` todavía la lee; `tests/journey/test_redirects.py::test_entering_opens_the_last_procedure_the_user_opened` afirma hoy que `/` lee la cookie y que no se fija: retirá esa aserción junto con la cookie. De T-350: `views/portada.py` ahora trae `_Tarjeta`, `_Mapa`, `_vista`, `_mapa_de` y `TARJETA_TAREAS`, y suma `mapa` al contexto; la sección «Los siete pasos» tiene `id="pasos"` y cada paso `id="paso-N"` en su `<h3>`. No los quites al tocar `lista`.
- **Archivos:** `evaluon/journey/views/inicio.py`, `evaluon/journey/views/portada.py` (solo `lista`), `evaluon/templates/journey/inicio.html`, `evaluon/templates/journey/expedientes.html`, `evaluon/urls.py`, `tests/journey/proceso/test_inicio.py`, `tests/journey/proceso/test_inicio_orden.py`, `tests/journey/proceso/test_inicio_rendimiento.py`, y, solo las líneas que dependen del inicio, `tests/journey/test_redirects.py`, `test_sections.py`, `test_roles.py`, `test_tema.py`, `test_pase.py`, `test_procedimientos_estetica.py`, `tests/journey/temas/test_s1_pliego.py`.
- **Verificación:** `pytest tests/journey/proceso/test_inicio*.py` y los tests actualizados: quien dejó abierto un procedimiento ve la lista, no ese procedimiento; cargar el dictamen lo pasa a «Terminados» y quitarlo lo devuelve; cuatro abiertos con 9 acciones muestran las 9 agrupadas, colapsado queda la línea y «N acciones»; vencidos primero, luego hoy; 20 abiertos (copias del caso chico) en ≤ 2 s (mediana de 5); sin cookie `evaluon_ultimo_*`.
- **No tocar:** `portada` y `seccion` de `portada.py`, `lote.py`.

### T-358 · Unificar el vocabulario en pantalla

- **Requisitos:** REQ-155.
- **Nivel:** liviana.
- **Qué hay que hacer:** aplicar la tabla «Vocabulario» del plan: «Matriz de cumplimiento» → «Matriz de requisitos» (etiqueta de la etapa y títulos de las plantillas), el mosaico «Cumplimiento por tipo y oferta» → «Cuadro de cumplimiento (resumen por tipo)» con enlace al cuadro, «Propuesta por oferta y requisito» → «Propuesta del sistema, requisito por requisito», «expediente» → «procedimiento» en los textos de ayuda. «Expediente» como dato del Portal no cambia. Confirmar cuáles apariciones de `assessment/matrix.html` nombran la lista de requisitos y cuáles el cuadro. El test acepta «Matriz de requisitos de pliego» como el nombre del paso 2.
- **Archivos:** `evaluon/journey/stages/matriz.py`, `evaluon/templates/journey/temas/s2_matriz.html`, `evaluon/templates/journey/temas/s4_propuesta.html`, `evaluon/templates/journey/temas/s2_documentos.html`, `evaluon/templates/journey/temas/s4_dictamen.html`, `evaluon/templates/tenders/matrix.html`, `evaluon/templates/tenders/matrix_print.html`, `evaluon/templates/tenders/_matrix_panel.html`, `evaluon/templates/assessment/matrix.html`, `evaluon/journey/temas/s2_matriz.py`, `evaluon/journey/temas/s4_propuesta.py`, `tests/journey/test_vocabulario.py`, y los tests que miran esos textos: `tests/journey/temas/test_s2_matriz_actions.py`, `tests/journey/temas/test_s4_propuesta.py`, `tests/journey/temas/test_s2_t338.py`, `tests/journey/temas/test_s2_tiles.py`.
- **Verificación:** `pytest tests/journey/test_vocabulario.py tests/journey/temas/` sin fallos nuevos: ninguna plantilla ni cadena de pantalla contiene «Expedientes» ni «Matriz de cumplimiento» como nombre de la lista; los siete nombres de los pasos son los mismos en inicio, portada y cuadro.
- **No tocar:** nombres de rutas, de claves de temas y `pasos.py`.

### T-359 · Cierre técnico: guía visual y glosario

- **Requisitos:** REQ-156, REQ-157, REQ-158.
- **Nivel:** liviana.
- **Qué hay que hacer:** consolidar en la guía visual los tokens y las reglas de la feature (estados de los pasos con texto, `--hoy`, `--vencido`, tokens del mapa, la regla de exclusividad de los colores) y actualizar el glosario con los siete pasos, «Mapa del proceso», «Cuadro de cumplimiento», «Indicadores» y las definiciones (advertencia, tarea, acción de cierre, faltante). No hay runbook de entorno: la feature no agrega servicios, dependencias ni migraciones (lo vigila T-342).
- **Aviso de tareas anteriores:** De T-350: la guía visual (§3.2) no dice nada del rango 900 a 1241 px (mapa desplazable en su caja) ni del umbral de 900 px para pasar a lista: documentarlo. De T-352: `cuadro.html` carga `s4_propuesta.css` y `punto.css`, que contienen `--ev-externo*` (lila de «externo») aunque el panel hoy no use esas reglas; el plan decía que el cuadro no las cargaría y `test_lila_exclusivo.py` no lo detecta: documentarlo o ajustar el test. De T-353: `pasos.DefPaso.seccion` ya no lo lee nadie y contradice a `pasos.DESTINOS` (su docstring quedó viejo): quitarlo o alinearlo. «Proponer la matriz» y «Evaluar las ofertas» no llevan ancla. `s4_propuesta_acciones.cuadro_url` arma la ruta a mano (puede usar `reverse('expedientes:cuadro')`). Faltan dos tests de `calculo.py` (filas técnicas fuera de «D de T»; dictamen subido + Portal sin aprobar ⇒ paso 7 «En curso»). `_money`, `_bucket` y `s3_circulares._states` son privados usados entre módulos. La advertencia de la tarjeta y de la lista no lleva a ningún lado. El `<h2>` «Indicadores» queda antes del `<h1>` del primer panel. De T-362 (anterior a la feature 018, para la lista de revisión): el rol sin Comisión ve enlaces que le dan 403 fuera de Indicadores, en páginas alcanzables desde la portada: en la pestaña Evaluación, 4 de exportación, los de la página del par y el documento original; en la pestaña Pliego, los de historial de requisitos, matrices descartadas, imprimir y PDF, y el original. En el panel del cuadro, ese rol ve rota la imagen de la página leída por visión (da 403), igual que en main.
- **Archivos:** `docs/diseno/guia-visual.md`, `docs/glosario.md`.
- **Verificación:** revisión del Coordinador; `pytest tests/journey/test_contraste.py tests/test_sin_externos.py` en verde.
- **No tocar:** código y hojas de estilo.

### T-360 · Medición final con el procedimiento del piloto y revisión visual

- **Requisitos:** REQ-143 a REQ-158.
- **Nivel:** plena (sin código).
- **Qué hay que hacer:** una sola vez, con el procedimiento real del piloto en su instancia (ADR-0060; al repositorio solo cifras): tiempos de inicio (20 abiertos), portada y cuadro (hasta 60 requisitos y 10 ofertas), 21 de 21 y acciones 100 % en un procedimiento real, piezas en la primera pantalla, mapa y cuadro leídos en los dos temas y en pantalla angosta, y la revisión visual del Coordinador. Máximo dos rondas.
- **Archivos:** `specs/018-proceso-a-la-vista/verificacion/T-360.md`.
- **Verificación:** informe con cada umbral y su resultado; lo que no llegue pasa con su impacto a la lista de revisión.
- **No tocar:** código.

### T-361 · Corregir los hallazgos de la medición final (condicional)

- **Requisitos:** los de cada hallazgo.
- **Nivel:** según el hallazgo.
- **Qué hay que hacer:** corregir lo que T-360 haya marcado; si no hay hallazgos, se cierra sin cambios. Si el inicio supera 2 s, aplicar la salida prevista del ADR-0079 (fila al instante y cada procedimiento por el sondeo existente).
- **Archivos:** los que indique `verificacion/T-360.md` (el Coordinador los declara al lanzar la tarea).
- **Verificación:** los tests de las áreas tocadas y una nueva medición de lo corregido.
- **No tocar:** nada fuera de los hallazgos.

## Cobertura de requisitos

| Requisito | Tareas |
|---|---|
| REQ-143 | T-341, T-343, T-346, T-348, T-352, T-357, T-358 |
| REQ-144 | T-340, T-341, T-345, T-346, T-348, T-354 |
| REQ-145 | T-340, T-342, T-345, T-346 |
| REQ-146 | T-344, T-346, T-348, T-350, T-354 |
| REQ-147 | T-342, T-344, T-346, T-348 |
| REQ-148 | T-348, T-350 |
| REQ-149 | T-353 |
| REQ-150 | T-356, T-357 |
| REQ-151 | T-357 |
| REQ-152 | T-352, T-354 |
| REQ-153 | T-355 |
| REQ-154 | T-351, T-352, T-353, T-355, T-354 |
| REQ-155 | T-358 |
| REQ-156 | T-347, T-350, T-352, T-359 |
| REQ-157 | T-343, T-344, T-347, T-348, T-350, T-357 |
| REQ-158 | T-349, T-350, T-354 |
| REQ-143 a REQ-158 | T-360 (medición final), T-361 |

### T-362 · Corregir los hallazgos del corte vertical en el cuadro y en Indicadores

- **Requisitos:** REQ-149, REQ-152, REQ-154, REQ-156.
- **Nivel:** plena.
- **Qué hay que hacer:** corregir los hallazgos H-A1, H-A2, H-A3 y H-A5 de `verificacion/T-354.md`. H-A1: para un usuario sin rol de la Comisión, el panel del cuadro muestra el HTML escrito en pantalla (`views/cuadro.py`, `_panel`: el reemplazo del enlace al documento original devuelve texto sin marcar como seguro); el panel tiene que verse igual que para el operador, sin el enlace, y sin abrir ninguna puerta de inyección (no marcar como seguro nada que no haya salido de la plantilla). H-A2: en Indicadores, solo lectura ve dos enlaces «Tomar del Portal» que dan 403: no ofrecer a un rol un enlace que no puede abrir. H-A3: el cuadro con 10 ofertas desplaza la página de costado; la tabla se desplaza dentro de su caja, con foco por teclado, y la página nunca. H-A5: nombre y total de cada oferta en el encabezado del cuadro, y la leyenda «sin confirmar», a 12 px o más. Cada corrección con un test que falla antes y pasa después.
- **Aviso de tareas anteriores:** De T-354: H-A1, H-A2, H-A3 y H-A5 están descritos con su reproducción en `verificacion/T-354.md`. H-A1 lo introdujo la corrección de T-352 que reemplaza el enlace al documento original con `re.sub` sobre el HTML ya renderizado: ningún test lo cubría porque no se renderizó el panel con ese rol. H-A3: `section.cu-tabla` mide 1.709 px con 10 ofertas y `.cu-scroll` no recorta; `min-width: 0` solo no alcanza (baja a 1.626). No se comprobó si H-A2 ya existía antes de la 018: comprobalo contra `main` anterior a la feature (commit 2272895d) y decilo.
- **Archivos:** `evaluon/journey/views/cuadro.py`, `evaluon/templates/journey/cuadro.html`, `evaluon/static/journey/cuadro.css`, la plantilla o el tema que dibuja «Tomar del Portal» en el primer panel (el que corresponda, uno solo), `tests/journey/proceso/test_cuadro.py`, `tests/journey/proceso/test_cuadro_panel.py`, `tests/journey/proceso/test_corte_correcciones.py` (nuevo).
- **Verificación:** `pytest tests/journey/proceso -q -rs` y `pytest tests/journey tests/assessment -n 2 --dist worksteal -q`; medición con Chrome sin cabeza del cuadro de 60 × 10 en 1000, 1280 y 1440 px (el ancho del documento igual al de la ventana).
- **No tocar:** `views/portada.py`, `mapa.py`, `mapa.css`, `_mapa.html` (son de T-363), `_par.html`, `tasks.md`, el tablero, la spec, el plan.

### T-363 · Rehacer las tarjetas del mapa: más anchas, tareas sin recorte y alto según el contenido

- **Requisitos:** REQ-146, REQ-158.
- **Nivel:** plena.
- **Qué hay que hacer:** decisión del responsable del 2026-11-18 («Tarjetas más anchas y a medida»): las tarjetas del mapa pasan a ser más anchas, las tareas se leen enteras en hasta dos líneas (sin puntos suspensivos) y cada tarjeta mide lo que ocupa su contenido (sin espacio en blanco por alto fijo). El mapa queda más compacto para que «Qué se puede hacer ahora» suba. Rehacer la geometría constante de `mapa.py` (posiciones, lienzo, conectores con sus codos) y sus tests, manteniendo: los ocho conectores 1→2, 2→4, 3→4, 3→5, 4→5, 4→6, 4→7, 6→7 que entran y salen por un punto fijo cerca del borde superior de la tarjeta; ningún conector tapado ni sobre texto con el alto MÁXIMO posible de cada tarjeta (3 tareas a dos líneas, «+ N más», advertencias, «Vence hoy» o «Vencido»); letra de 12 px o más; lienzo que entra entero a 1280 px de ventana; entre 900 px y el ancho en que entra, se desplaza dentro de su caja con la pista; por debajo de 900 px, la lista. Además: H-A4 de `verificacion/T-354.md` (el resumen del título dice «1 hechos»: concordar singular y plural), la leyenda dice «punteada» y el trazo es de rayas (que el texto diga lo que se ve), la línea de plazos sin cronograma no ocupa 150 px para decir casi nada (H-B6), y la advertencia de la tarjeta lleva a la lista de su paso (`#paso-N`). Comprobar en Chrome sin cabeza, en los tres fixtures, «Vence hoy», «Vencido» y las siete tarjetas llenas, en los dos temas, y dejar capturas.
- **Aviso de tareas anteriores:** De T-354: en el caso de la maqueta A hay 6 textos recortados (20 con las siete tarjetas llenas) y las tarjetas 1, 2 y 5 tienen 42 a 53 % de blanco; «Qué se puede hacer ahora» empieza a 1.457 px del tope a 1440 × 900 (612 px en `?vista=lista`); la página completa mide 3.596 px. Las mismas tareas aparecen en el mapa, en «Qué se puede hacer ahora» y en «Lo que falta» de cada paso, con las mismas cifras. Sin cronograma, la línea de plazos ocupa unos 150 px. No se pudo medir en Edge, con flechas del teclado ni en táctil.
- **Archivos:** `evaluon/journey/proceso/mapa.py`, `evaluon/static/journey/mapa.css`, `evaluon/templates/journey/_mapa.html`, `evaluon/templates/journey/_plazos.html`, `evaluon/journey/views/portada.py` (solo lo del mapa y el resumen del título), `docs/diseno/guia-visual.md` (§3.2), `tests/journey/proceso/test_mapa_geometria.py`, `tests/journey/proceso/test_mapa.py`, `tests/journey/proceso/test_mapa_vista.py`, `tests/journey/proceso/test_portada.py` (solo si una aserción cambia por el título).
- **Verificación:** `pytest tests/journey/proceso tests/journey/test_contraste.py -q -rs` y `pytest tests/journey tests/assessment -n 2 --dist worksteal -q`; medición propia en Chrome sin cabeza: ningún texto recortado ni fuera de su tarjeta, ningún conector tapado, y a qué distancia del tope empieza «Qué se puede hacer ahora» a 1440 × 900 (antes: 1.457 px en el caso de la maqueta A).
- **No tocar:** `views/cuadro.py`, `cuadro.html`, `cuadro.css` (son de T-362), `acciones.py`, `calculo.py`, `tasks.md`, el tablero, la spec, el plan.
