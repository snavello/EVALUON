# T-120, diagnóstico 4: caso-06 con main 26cb1c0 y consolidado de los casos 01, 05 y 06 (REQ-024, REQ-031)

Solo diagnóstico: no se cambió código, tests, datos, contenedores ni corridas. Sin modelo y sin GPU. Fuentes: la corrida `corpus/casos/caso-06/corridas/20261005-025935-26cb1c0/` (`resumen.md`, `resultados.jsonl`, `parametros.json`, muestras), `esperado/matriz-esperada.yaml` y `para-el-responsable.md`, lecturas de solo lectura de la base (propuesta 17 del procedimiento `caso-06-medicion`, tablas `tenders_run_step`, `tenders_disposition`, `tenders_requirement_quote`, `tenders_requirement_source`, `tenders_segment`), el código a main `26cb1c0` (`git show 26cb1c0:...`; los `archivo:línea` son de ese commit) y los diagnósticos 2 y 3. Sin texto del pliego ni de las circulares: filas por número (`#N` de la corrida, `M-NNN` de la lista, `R-N` = número de requisito de la versión), tramos y fragmentos de pocas palabras.

## Resumen

| Pregunta | Causa | Defecto de | Conocida |
|---|---|---|---|
| 1. M-004, M-005 y M-025 (D2) | La circular entera es un apartado que `is_procedure_data` clasifica como "dato del trámite": **el modelo nunca la vio**. Salió una fuente `modifica` genérica sobre dos citas que nombran el portal | Producto, constantes de `circular_units.py` (T-120) | **Nueva** |
| 1 (después de corregirla) | Con la unidad ya en el modelo reaparece `clave_ambigua` (7.1 tiene dos citas; 12.10, dos) | Producto (`circular_changes.py:249-250`) | Conocida (diag. 3, 1b) |
| 2. M-039 | Descarte del modelo en la pasada de extracción (`dato_procedimiento`) sobre una opción marcada de un cuadro; no es `is_procedure_data` ni el filtro | Prompt de extracción / criterio de la lista | Misma familia que M-033 y M-059 del caso-05 |
| 3. Sobrantes 67 de 114 | Mismos patrones de 01 y 05 (oraciones partidas, deberes generales, anexos), más 15 condiciones reales sin fila en la lista; el filtro casi no actúa | Producto (T-106) y granularidad de la lista | Parcial |

Aclaración sobre la pregunta 2 del encargo: `is_procedure_data` no se usa en `run.py`. Está definida en `circular_units.py:771` y se llama una sola vez, en `resolve` (`circular_units.py:902`), y solo para unidades de **circulares**. El tramo de M-039 es del pliego y no pasa por ahí (ver sección 2).

## 1. Las tres filas de circular (D2, `IF-2026-02677035`)

### Qué hay en la circular

Cinco tramos entre el encabezado y el final (`pre/p-9`, `pre/p-10`, `pre/p-11`, `pre/p-12` y `pagina-2`, vacío): el encabezado "I. RESPUESTAS A LAS CONSULTAS…", una consulta (`Consulta N° 1: …`, 565 caracteres), su respuesta (`Respuesta: Se aclara que…`, 544) y una constancia final (114). Es una sola consulta con una sola respuesta, que dice dos cosas: alcanza la carga electrónica según 7.1 (M-004, M-005) y eso rige sin perjuicio de 12.10 y 21.3 (M-025).

### Qué produjo la pasada

Pedido de la pasada `circulares` (`tenders_run_step` 1918, unidad `apartado`, los cinco tramos). Lo que muestra:
- `request` trae `sin_modelo` y no hay pedido `circulares_cambios` para esa unidad (los 16 pedidos `circulares_cambios` de la propuesta son de `pre/p-1` a `pre/p-8`, todos con `cambios: []`).
- `parsed`: `cambio: dato_del_tramite`, `resultado: dato_del_tramite`, `objetivo: {tipo: anexo, referencia: ["portal de compras"]}`, `fuentes`: dos, ambas `efecto: modifica`, con el texto de `pre/p-10` a `pre/p-12` entero (`char 430 a 1655`) como texto vigente, sobre las citas R-1 (`pre/p-5`, sugerencia) y R-14 (`sec-i/7.1`, primera cita).
- En `tenders_requirement_source` solo existen esas dos fuentes de D2. R-15 (7.1, segunda cita), R-53 y R-54 (12.10) no tienen ninguna.

### Por qué (archivo:línea)

1. **`is_procedure_data` dice que es una lista de datos** (`circular_units.py:771-787`). Para el apartado: `DATA_MIN_LINES = 2` (3 líneas de cuerpo), ninguna línea tiene marcadores de obligación (se verificó: ni `OBLIGATION_MARKERS` ni ninguna forma de "deb-" aparece en `pre/p-9` a `pre/p-12`), y `_LABELED = ^[^\n:]{2,60}:\s*\S` (`circular_units.py:149`) acepta como "rótulo y valor" cualquier línea que tenga dos puntos antes del carácter 60: `Consulta N° 1:` y `Respuesta:` calzan aunque el "valor" sea un párrafo de 500 caracteres. Resultado: etiquetadas 2 de 3 (0,67 contra `DATA_LABELED_SHARE = 0,3`) y etiquetadas más cortas 2 de 3 (0,67 contra `DATA_SHARE = 0,6`). El largo de la línea no pesa para las etiquetadas: `SHORT_LINE_CHARS = 100` solo se aplica a las no etiquetadas. El comentario de `circular_units.py:73` ya dice que esas constantes "se ajustan en T-120".
2. **`resolve` toma el camino de datos antes que el estándar** (`circular_units.py:902-903`): no hay par, y `_resolve_data` (`:841`) corre sin pedirle nada al modelo. La unidad no pasa por la extracción (`circulars.py:833`) y el pedido de respaldo tampoco.
3. **`_resolve_data` fabrica un efecto** (`circular_units.py:841-872`): busca títulos entre comillas en las primeras `HEAD_LINES = 4` líneas (`_titles_in`, `:612`). La consulta cita el servicio entre comillas ("Portal de Compras", dos palabras), así que lo toma como el título de un anexo que "reemplaza" la lista: una fuente `modifica` por cada cita del pliego que lo menciona (R-14 y la sugerida R-1) y el texto vigente es la consulta con su respuesta. No alcanza a R-15, R-53 y R-54 porque no mencionan el portal entre comillas.

### Las tres filas

| Esperado | Qué esperaba la lista | Qué produjo | Puntos en falso | Causa |
|---|---|---|---|---|
| M-004 (7.1, R-14) | D2, `precisa` (se guarda como `aclara`, `evaluation.py:122-124`), tramo `pre/p-11` | fila 14 con fuente de D2 pero efecto `modifica`, texto vigente la consulta con la respuesta | 1 (efecto). Cumplen 2, 3 y 4 por casualidad: la fuente cubre el ancla de la lista | Causa 1-3 de arriba |
| M-005 (7.1, R-15) | D2, `precisa` | fila 15 sin ninguna fuente | 1, 2, 3 y 4 | Causa 1-3; además ni siquiera el camino de datos la alcanza (no nombra el portal entre comillas) |
| M-025 (12.10, R-53) | D2, `aclara` | fila 53 sin ninguna fuente | 1, 2, 3 y 4 | Causa 1-3; en `_resolve_data` no existe la idea de "cláusula nombrada" |

Ruido de REQ-031: 0 fuentes en 0 filas. Es esperable: las dos fuentes caen en R-14 (con esperado) y R-1 (sugerencia, que no cuenta como fila firme).

### Cuál es el siguiente obstáculo

Con la unidad en manos del modelo (corrigiendo la causa 1) la unidad pasaría a `_resolve_standard` (`circular_units.py:699`): encabezado sin verbo → `sin_verbo_reconocible` → extracción, como D2 del caso-05. Lo natural en el modelo es un cambio `aclara` con objetivo `clausula` y referencias "7.1" y "12.10, 21.3". Entonces:
- 7.1 tiene **dos citas** (R-14 y R-15), 12.10 tiene dos (R-53 y la sugerida R-54) y 21.3 tiene dos (R-102 y R-103). En `_pool_for` (`circular_changes.py:249-250`): `aclara` + más de una cita + sin texto anterior = `clave_ambigua`, y el cambio va al respaldo. Es la **misma causa que M-046 del caso-05** (diag. 3, grupo B).
- Si el modelo copia un texto anterior, `match_old_text` (`circular_units.py:367-390`) devuelve una sola cita (o empata), y una sola oración de la respuesta no puede alcanzar a la vez a R-14 y a R-15 como espera la lista.
- El respaldo (v2, `circulars.py`) es por tramo y elige las 8 mejores citas por reranker (`MATRIX_CIRCULAR_CANDIDATES = 8`, `settings.py:274`); las citas de 7.1 compiten con otras del portal. Puede resolver las tres filas o ninguna: no se puede afirmar sin correrlo.

Por eso la estimación de impacto (sección 4) tiene un rango.

### Riesgo lateral que esto revela (afecta a T-120)

La clasificación como datos depende de un accidente: sobre las unidades de consulta y respuesta inspeccionadas, la de D2 del caso-06 no tiene ningún marcador y cae en datos; la D4 del caso-05 (`IF-2026-02188605`, "I.-") tiene dos consultas (`pre/p-10` y `pre/p-14`) que traen un marcador de obligación y por eso **no** caería en datos; D2 del caso-05 se salvó por citar "deberán" (diag. 3). Si se corrige el encabezado "I.-" (diag. 3, corrección 1) sin corregir `is_procedure_data`, D4 del caso-05 se salva solo por esas dos citas, y cualquier circular de consulta y respuesta sin esa palabra se comporta como la de este caso. La corrección de "debe/deben" del diag. 2 no ayuda acá: la unidad no tiene ninguna forma de "deb-".

### Corrección propuesta (entra en T-120: constantes de `circular_units.py`)

1. En `_LABELED` (`circular_units.py:149`) exigir que el valor sea corto (por ejemplo `^[^\n:]{2,60}:\s*\S.{0,100}$`, sobre la línea entera): una línea de 500 caracteres con dos puntos al comienzo no es "rótulo y valor". Con eso la unidad queda con 0 de 3 etiquetadas y deja de ser datos. Una lista real de datos (fecha, hora, lugar, referente) sigue cumpliendo.
2. Excluir de `is_procedure_data` las unidades cuyas líneas empiezan con "Consulta N°" o "Respuesta:" (una constante regex nueva `_QA_LINE`), como segunda red: una respuesta de la convocante es siempre un efecto posible, nunca un dato.
3. No cambiar `_resolve_data` (sigue valiendo para una lista de datos que reemplaza un anexo); con 1 y 2 deja de ver unidades de consulta.
4. Medición: caso-06 (objetivo: el pedido de D2 aparece en `tenders_run_step` con `circulares_cambios`) y caso-05, caso-01 para confirmar que las listas de datos que hoy se reconocen (por ejemplo, los datos del trámite de las circulares del caso-01) siguen siéndolo.
5. Un test sintético con una consulta y respuesta sin marcadores (una "Consulta N° 1:" de varias oraciones y una "Respuesta:" con la aclaración): espera que `is_procedure_data` devuelva falso.

## 2. M-039: `sec-i/18.1/p-1`, "Por Renglón X"

### Qué es y quién lo descartó

- El tramo es un párrafo de 13 caracteres, una de las dos opciones de un cuadro "Tipo de Cotización:" de 18.1; la otra, "Por grupo de Renglones", es un tramo `tabla` (`sec-i/18.1/tabla-2`). La opción marcada con una X es la de este procedimiento (por renglón).
- La disposición es `descartado`, origen `modelo`, motivo `dato_procedimiento` (`tenders_disposition`); no figura en `tenders_discarded_row`, es decir **no lo descartó el filtro** (las 5 descartadas del sistema son de 5.2, 12.3, 17.4, 17.5 y 17.6). En la pasada de extracción (lote `sec-i/18.1` a `sec-i/20.2`, tramo T3) el modelo devolvió `descarte: dato_procedimiento` y `requisitos: []`; hizo lo mismo con el tramo vecino de "Por grupo de Renglones" y con 19.1.
- La completitud no lo reabre: solo reconsidera tramos descartados que tengan marcadores de obligación (`completeness_candidates` en `run.py`; `OBLIGATION_MARKERS`, `run.py:133-144`) y esta línea no tiene ninguno. Además un tramo `tabla` no queda descartado nunca (`keep_tables_pending`), pero `p-1` es un párrafo.

### ¿Es un error de la regla?

No de código. La regla que actuó es el criterio del prompt `matriz-extraccion-v2` ("dato_procedimiento: define algo o da un dato del procedimiento"), y leída al pie de la letra la línea sin verbo es un dato. Hay dos lecturas razonables y la decisión es de criterio, no mía:

- **El contenido no se pierde.** La obligación de cotizar por renglón está en 18.2 (M-040, encontrada: "cotizar la cantidad total de cada renglón") y en 18.3 ("menor precio por renglón", filas sobrantes #89 y #90). La lista del caso-06 y la regla D-02 de `para-el-responsable.md` ("una condición repetida en varios lugares tiene una sola fila") dan pie a tratar M-039 como repetida y no como fila propia.
- **La lista del caso-05 la trata al revés.** Allí la opción hermana ("por grupo de renglones", M-059) sí es fila esperada. Si la convención es "la opción marcada del cuadro es requisito", la lista del caso-06 es coherente con la del caso-05 y el modelo falla en los dos (en el caso-05 la tabla quedó pendiente y no hay fila).

La misma familia de falla que M-033 del caso-05 (línea de formulario "campo: valor" sin verbo, diag. 3, sección 2): una línea de formulario o de opción marcada, sin verbo, que el extractor lee como dato.

### Corrección que propondría

Una sola, y no en T-120: una regla angosta en `matriz-extraccion` (v3) y `matriz-completitud`: "una opción marcada en un cuadro que fija cómo debe cotizar u ofertar el oferente (tipo de cotización, por renglón o por grupo) es un requisito económico, aunque no tenga verbo". Hay que medirla en caso-05, caso-06 y caso-01 porque es el patrón que más sobrantes suma en anexos (ver sección 3). Alternativa que no toca código (decisión del Coordinador con el responsable, que dio el visto bueno a la lista): marcar M-039 como repetida de M-040. Yo no la tocaría para que pase la medición.

Efecto: +1 en encontrados del caso-06 (47 de 48 pasa a 48 de 48, meta 100 %); nada en REQ-031.

## 3. Sobrantes: 67 de 114

Las clases son por criterio mío sobre `resumen.md` (sobrantes por tramo y primeras 80 caracteres de cada cita) y valen unas 3 filas más o menos.

| Patrón | Filas | Filas (`#N`) | Antes se vio en | Corrige |
|---|---|---|---|---|
| 1. Oración partida: la fila es un trozo que empieza en minúscula o es un ítem de una enumeración (incluye "teléfono celular", "correo electrónico", "Para otras formas de garantía,") | 23 de 67 (34 %) | #9, #12, #32, #33, #35, #36, #50, #58, #65, #71, #79, #87, #90, #92, #94, #99, #100, #102, #103, #108, #114, #117, #118 | Caso-05, patrón 2 (33 %) | Regla de partición de la extracción y unificación por contención (apagada: `dedup_containment: false`, `dedup_min_similarity: 1.0`) |
| 2. Anexos: declaraciones juradas de inhabilidades (la lista tiene 0 entradas de anexos) | 14 de 67 (21 %) | #120 a #133 (`anexo-i` 9, `anexo-ii` 5) | Caso-05, patrón 1 (39 %) | Filtro v3 y regla de anexos |
| 3. Aceptación y deberes generales ("la sola presentación implica…", jurisdicción, confidencialidad, canal ético, desconocimiento del pliego) | 11 de 67 (16 %) | #3, #4, #5, #55, #56, #68, #69, #110, #111, #112, #113 | Caso-05, patrón 4; caso-01 (confidencialidad) | Filtro v3 (`norma_aplicable`, `obligacion_organismo`) |
| 4. Etapas posteriores a la oferta (informar contactos de ejecución, observaciones, impugnaciones, vista) | 4 de 67 | #34, #91, #93, #95 | Caso-05, patrón 3 | Filtro v3 (`ejecucion_contrato`, `derecho_posterior`) |
| 5. Condiciones reales que la lista no abre como fila (consecuencias de omitir, descuentos, renovación del mantenimiento, formulario a descargar, domicilio, subcontratación, valor del módulo) | 15 de 67 (22 %) | #2, #17, #21, #26, #28, #30, #38, #40, #43, #75, #76, #77, #82, #89, #119 | Caso-05 (granularidad) | Nada en el código: la diferencia de granularidad entre lista (48) y extractor (114 firmes) |

Total 23 + 14 + 11 + 4 + 15 = 67.

### Lo que es nuevo respecto de los casos 01 y 05

- **El filtro v2 casi no actúa, igual que en 01 y 05**: 5 descartadas y 21 sugerencias; "sin el filtro" serían 72 sobrantes (`resumen.md`). Es el mismo análisis del diag. 2 (prompt v2, "ante la duda, mantener"); no se repite.
- **La unificación funciona con textos iguales**: la pasada de unificación (`tenders_run_step` 1860) unió 6 pares de motivo `igual`: 12.1 con 12.7 y cinco pares de `anexo-i` con `anexo-ii` (p-6 a p-10). No es una causa de sobrantes por sí sola. Lo que falta es la unificación por contención (patrón 1), apagada.
- **Las descartadas "obligacion_organismo" de 17.5 y 17.6 son del tipo de M-058 del caso-01** ("el Organismo verificará… la Resolución General…", caso-01 #128). Acá el filtro las descarta y la condición del lado del oferente (deuda, #87, fila firme) queda como fila: la lista del caso-06 no las pide, así que no hay pérdida. Confirma que la regla angosta del diag. 2 (tercera pregunta C sobre "lo que verifica es del oferente") sería lo correcto para separar los dos lados, y que una regla general de v2 ("mantener todo lo que controle algo") las habría arrastrado.
- **Menor peso de anexos que en el caso-05** (21 % contra 39 %), porque el pliego trae solo dos anexos con texto y 5 de sus 10 ítems se unificaron.
- **Un patrón que casi no se veía antes: 15 filas (22 %) son condiciones reales que la lista no abre.** No son error del sistema.
- **El tope** (hasta 20 % de 114 filas firmes, es decir 22 sobrantes como máximo) no se cierra con el filtro solo: quitando anexos, deberes generales y etapas posteriores (29 filas) quedarían 38. Solo se alcanza si además se cura el patrón 1 (23 filas) y se acepta el patrón 5. Sigue siendo de T-106, no de T-120.

## 4. Tabla consolidada de causas (casos 01, 05 y 06)

Convenciones: "T-120" = constantes y listas de `circular_units.py` o prompt de circulares (v4 o v5). Impacto en REQ-031: filas de circular esperadas que pasarían a cumplir los cuatro puntos; en encontrados: filas que la medición contaría como encontradas. Las estimaciones suponen que la corrección se hace sola salvo que diga lo contrario.

| # | Causa | Filas afectadas | Corrección propuesta | Archivo (26cb1c0) | ¿Entra en T-120? | Impacto REQ-031 | Impacto encontrados |
|---|---|---|---|---|---|---|---|
| A | **Nueva.** Una circular de consulta y respuesta se clasifica como dato del trámite; el modelo no la ve y se fabrica un `modifica` genérico | Caso-06: M-004, M-005, M-025 | `_LABELED` con valor corto, exclusión de líneas "Consulta N°" y "Respuesta:" | `circular_units.py:149, 771-787, 902` | **Sí** (constantes) | Caso-06: de 0 de 3 a entre 0 y 3 de 3 por sí sola; 3 de 3 probable junto con B. Requisito previo de F para no repetir el problema en cualquier circular de consulta sin marcadores | 0 |
| B | `aclara` con varias citas de la cláusula nombrada y sin texto anterior = `clave_ambigua` | Caso-06: M-004, M-005, M-025 (después de A); caso-05: M-046 | Aplicar la aclaración a todas las citas de la cláusula nombrada por la circular, o devolver una sugerencia por cada una | `circular_changes.py:249-250` | No (código y criterio de producto; consultar al responsable) | Caso-06: hasta 3 (con A); caso-05: M-046 con C-bis (hasta 1) | 0 |
| C | Faltan "debe/deben" en los marcadores de obligación que usa `_added_obligations` y `_resolve_addition` | Caso-01: M-015 (D16, `agrega`) | Lista propia de circulares con `\bdeb(e|en|erá|erán|erían)\b` y otras formas; red de seguridad como sugerencia | `circular_units.py:584, :781` (la lista de `run.py:133-144` no se toca) | **Sí** (lista de `circular_units.py`) | Caso-01: de 14 a 15 de 15 | Caso-01: +1 si M-015 hoy figura como faltante (no verificado) |
| D | Filtro v2: guarda casi inerte, balance de ejemplos que empuja a "mantener", sin tercera opinión C | Caso-01: 34 descartadas menos, M-058 en riesgo; casos 05 y 06: sobrantes | Prompt v3, tercera pregunta C solo sobre los descartes, guarda sin cambios | `filter.py`, `matriz-filtro-v3.md` | No (T-106) | 0 | Protege M-058 y M-063 (caso-01) |
| E | Encabezado "I.-" no reconocido: la unidad pierde la consulta | Caso-05: M-066, M-067, M-068 | Ampliar `_ROMAN_HEADING`, `_ROMAN_PREFIX` y `circulars._HEADING` a "I.-", "I -" y "I)" | `circular_units.py:133-134`; `circulars.py:118` | Sí para `circular_units.py`; `circulars.py` pide ampliar la lista de archivos | Caso-05: hasta 3 junto con F; **hacerla junto con A** (ver riesgo lateral) | 0 |
| F | Instrucciones v3 de `circulares_cambios`: "ítem" no vale como renglón; sin un cambio por renglón ni por objeto; una aclaración puede salir con `texto_nuevo` vacío o demasiado corto | Caso-05: M-066 a M-068, M-046 (anexo), M-060 punto 3 | Prompt v4 (diag. 3, corrección 2): "ítem" como renglón; un cambio por renglón con su texto anterior; un cambio por cada objeto nombrado; en `aclara`, copiar las oraciones completas. Para el caso-06 sumar a v4: cuando una oración nombra una cláusula y la respuesta dice varias cosas, un cambio por cláusula | `matriz-circulares-v4.md`, `MATRIX_PROMPT_VERSIONS` (`settings.py:276`) | **Sí** (prompt de circulares) | Caso-05: hasta 5 de 8 (M-060, M-066 a M-068, M-046 con cláusula 6 ya cubierto por B); caso-06: ayuda a A pero no resuelve B | 0 |
| G | Texto de la fuente de una aclaración = encabezado de la unidad cuando `texto_nuevo` viene vacío | Caso-05: M-060 punto 3 (si es este caso) | Usar el tramo de la respuesta o mandar al respaldo | `circular_changes.py:317` | No (código) | Caso-05: +0 si F lo cubre, +1 si no | 0 |
| H | Empate de `match_old_text` entre renglones distintos | Caso-05: M-066 a M-068 (si F no los separa por renglón) | Aceptar una cita por renglón en el empate | `circular_units.py:367-390` | No (código); solo si F no alcanza | Caso-05: hasta 3 | 0 |
| I | Tramo `tabla` pendiente: no hay fila a la que aplicar la circular | Caso-05: M-059 | Crear fila desde la tabla o informar "sin medir"; decisión que cambia la medida | Lectura de tablas; `evaluation.py:1069` | No (otra tarea y decisión del responsable) | Caso-05: +1 posible (8 de 8) | Caso-05: +1 si la tabla da fila |
| J | Línea de formulario u opción marcada sin verbo que el extractor lee como dato | Caso-05: M-033; caso-06: M-039 | Regla angosta en `matriz-extraccion` (v3) y `matriz-completitud` (diag. 3, sección 2; sección 2 de este) | `matriz-extraccion-v2.md`, `matriz-completitud-v2.md` | No (T-106 u otra) | 0 | Caso-06: 47 a 48 de 48 (100 %); caso-05: +1 |
| K | Oraciones partidas: la fila es un trozo | Caso-05: 48 filas; caso-06: 23 filas; caso-01 | Regla de partición en la extracción; unificación por contención | `matriz-extraccion`, `dedup_*` en `parametros.json`, `dedup.py` | No (T-106) | 0 | 0 (baja sobrantes) |
| L | Anexos, deberes generales, etapas posteriores, consecuencias como filas propias | Caso-05: unas 107; caso-06: 29; caso-01 | Filtro v3 con motivos `norma_aplicable`, `ejecucion_contrato`, `derecho_posterior`, `consecuencia_sancion` y regla de anexos | `filter.py`, prompts | No (T-106) | 0 | 0 (baja sobrantes) |
| M | Granularidad de la lista contra la del extractor (48 contra 114 filas firmes en el caso-06) | Caso-05 (69 contra 210); caso-06 | Decisión de producto y de lista, no de código | `matriz-esperada.yaml` (no se toca) | No (responsable) | 0 | 0 |

Notas de la tabla:
- "C-bis" en B es la oración de M-046 que nombra la cláusula 6: sigue siendo dudosa la lista (diag. 3, grupo B).
- Resumen de lo que entra en T-120: **A**, **C**, **E** (solo `circular_units.py`) y **F** (prompt v4). Las dos primeras son constantes y listas, y son las que más rinden en el caso-06 y en el caso-01.

### Estimación acumulada de REQ-031 si T-120 hace A, C, E y F

| Caso | Hoy | Con A, C, E y F | Lo que sigue sin entrar | 
|---|---|---|---|
| Caso-01 | 14 de 15 | 15 de 15 (C) | nada de REQ-031 |
| Caso-05 | 2 de 8 (M-005, M-063) | entre 5 y 7 de 8 (F, E; M-046 y M-066 a M-068 con riesgo de empate H) | M-059 (I); M-046 si no se acepta la lista (B) |
| Caso-06 | 0 de 3 | entre 0 y 3 de 3 (A; B decide cuántas) | B si A solo no basta |

### Orden recomendado para T-120

1. A y C primero: son listas y constantes, sin riesgo de interferencia entre sí, y A es requisito de E.
2. E junto con A (si no, D4 del caso-05 se salva solo por citar "deberán" en dos consultas).
3. F (prompt v4) después, y medir caso-05, caso-06 y caso-01 (que conserve 15 de 15).
4. Pedir al Coordinador que abra tareas para B, G, H, I, J, K y L; B es la que decide si el caso-06 llega a 3 de 3.
5. No pasar de las dos rondas de ajuste que dice `tasks.md`.

## 5. Preguntas abiertas para el Coordinador

- B toca producto y criterio (aplicar una aclaración de cláusula a todas sus citas): conviene consultarla con el responsable antes de abrir la tarea.
- M-039: decidir con el responsable si la opción marcada de un cuadro cuenta como requisito (J) o si se trata como condición repetida de M-040 (cambia la lista, que tiene visto bueno).
- Confirmar que `circulars.py` puede entrar a T-120 para E (`_HEADING`, línea 118); si no, el respaldo sigue sin ver el encabezado de las consultas con "I.-".
