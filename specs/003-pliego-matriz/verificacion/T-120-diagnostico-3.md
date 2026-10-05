# T-120, diagnóstico 3: caso-05 con main 26cb1c0 (REQ-024, REQ-031)

Solo diagnóstico: no se cambió código, tests, datos ni corridas. Análisis de archivos, sin modelo, sin GPU y sin consultar la base. Fuentes: la corrida `corpus/casos/caso-05/corridas/20261005-024809-26cb1c0/` (`resumen.md`, `resultados.jsonl`, `parametros.json`, muestras), `esperado/matriz-esperada.yaml` y `para-el-responsable.md`, los PDF de las circulares (leídos solo para entender la estructura; no se copia su texto), el código a main `26cb1c0` (`git show 26cb1c0:...`; esta rama está atrás de main, así que **todos los `archivo:línea` son de 26cb1c0**) y los diagnósticos 1 y 2. Sin texto del pliego ni de las circulares: filas por número (`#N` de la corrida, `M-NNN` de la lista), tramos y paráfrasis.

Límite de lo que se puede afirmar: lo que la pasada de circulares hizo con cada tramo (pedido de extracción, cambios devueltos, candidatas mostradas, `sin_efecto`) está en `tenders_run_step` de la base, que no se consultó. Lo que sigue se deduce de `resultados.jsonl` y del ruido del resumen (ver "Qué se ve en los archivos") y se marca **probable** donde no se puede cerrar sin ese registro. Al final hay una consulta de solo lectura para cerrar las dudas.

## Resumen

| Pregunta | Causa | Defecto de | Mismo que diag. 2 |
|---|---|---|---|
| 1a. M-059 (D2, puntos 1 a 4) | No hay fila: el tramo `sec-i/18.1/tabla-1` quedó pendiente (tabla) y la circular no tiene a qué aplicarse | Lectura de tablas y medición, no la pasada de circulares | No |
| 1b. M-046 (D2, puntos 1 a 4) | La oración nombra "cláusula 6" y un anexo; la extracción por clave se rinde con la cláusula (varias citas, sin texto anterior) y el anexo no se separa como cambio propio | Producto (T-115) e instrucciones v3 | No |
| 1c. M-060 (D2, punto 3) | La fuente copia menos de la mitad del ancla vigente (que tiene dos oraciones) | Instrucciones v3 y `circular_changes.py:317` | No |
| 1d. M-066, M-067, M-068 (D4, puntos 1 a 4) | Encabezado "I.-" no se reconoce; cada tramo va suelto; la respuesta no nombra renglón ni cláusula; la extracción no tiene a qué anclar y el respaldo no devuelve efecto | Producto (T-113 y T-115) e instrucciones v3 | No |
| 2. M-033 | La línea del paso del portal no se extrajo; en su tramo solo hay dos filas de otras oraciones, ambas sugerencias | Extracción y completitud (prompts) | No |
| 3. Sobrantes 147 de 210 | Mismo patrón que caso-01 (filtro v2 que casi no descarta) más dos pesos propios: anexos (58 filas) y oraciones partidas (48 filas) | Producto (T-125, extracción, unificación apagada) | Parcial |

Causa de diag. 2 (`OBLIGATION_MARKERS` sin "debe"): **no interviene** acá. Aquel fallo es de la rama `agrega` con par "Donde dice / Debe decir" (`_added_obligations`, `circular_units.py:584`) y las circulares del caso-05 son todas `aclara`: no hay par ni `agrega` (verificado en los PDF y en la lista: sin efecto `agrega`). Lo único que roza el aviso lateral de diag. 2 es `is_procedure_data` (`circular_units.py:771`): la circular D2 evita clasificarse como "datos del trámite" porque su texto cita una oración con "deberán"; una cita con "debe" la habría tratado como lista de datos y sin efectos. Sigue siendo un riesgo para T-106; acá no pasó.

## Qué se ve en los archivos (base de las respuestas 1)

- `resultados.jsonl`, líneas `tipo: circular`: M-005 y M-063 (D4) cumplen; M-046 fila 98 con los cuatro puntos en falso; M-059 `fila: null`; M-060 fila 133 con efecto, original y documento bien y vigente en falso; M-066, M-067 y M-068 filas 221, 222 y 223 con los cuatro puntos en falso.
- Una fila con **todos** los puntos en falso, incluido el 4 (documento y fecha), no tiene ninguna fuente de la circular esperada: `_source_points` (`evaluation.py:1005`) pone el punto 4 en verdadero en cuanto hay una fuente de ese documento y fecha. Entonces las filas 98, 221, 222 y 223 **no recibieron fuente alguna** de D2 o D4 respectivamente.
- Ruido (`resumen.md:57-60`): una sola fuente fuera de filas esperadas, de D4, en la fila #107 (`sec-i/14.2`, conversión del tipo de cambio). **D2 no tiene ninguna fuente fuera de la fila 133.** O sea que el modelo no puso en ningún otro lado lo que no puso en 98.
- Requisitos de origen `circular` sin esperado: 0. Filas de circular sin medir: 0. Las 8 anclas de circular comprobadas (`parametros.json`: `circular_anchors_ok` 8 de 8).
- La estructura de las circulares (PDF): D2 tiene el encabezado "I. RESPUESTA…" y todo el contenido cae bajo él; D4 tiene "I.- RESPUESTAS…" (punto y guion) y cinco consultas con sus respuestas, dos de ellas del tipo "Remítase a la respuesta de la Consulta N° X".

## 1. Las seis filas de circular que fallan

### Grupo A. M-059: no hay fila a la que aplicar (D2)

- **Esperaba la lista** (`matriz-esperada.yaml:575`): fila de `sec-i/18.1/tabla-1` ("por grupo de renglones"), bloque con D2, 2026-07-02, efecto `aclara`, tramo de la circular `pre/p-11`.
- **Qué produjo la pasada:** nada medible. El requisito no existe: `resultados.jsonl` lo da `a_revision_obligatoria` con causa `tramo_pendiente`, detalle `tabla`; en la medición de circulares queda `fila: null` (`evaluation.py:1069`, `row = by_pk.get(matched_pk.get(item.id))`). Las citas candidatas de la pasada salen solo de los requisitos de la versión (`circulars.py:267`, `build_candidates`): un tramo de tabla pendiente no es candidata, así que ni la extracción por clave ni el respaldo pueden ponerle una fuente.
- **Efecto, original, vigente, documento:** los cuatro en falso, por falta de fila y no por lo que dijo la circular.
- **Causa en el código:** la lectura de tablas deja 7 tramos pendientes (`resumen.md:17`: `tabla: 7`). No es de `circular_units.py` ni de las instrucciones de circulares.
- **Decisión que no es de T-120:** mientras la tabla no dé fila, este esperado no puede cumplir REQ-031 por ninguna corrección de circulares. Opciones del responsable: (a) esperar a que la lectura de tablas cree la fila; (b) que la medición lo informe como "sin medir" por tramo pendiente, como ya hace con la circular no cargada (`evaluation.py:1063`, `circular_no_cargada`). La (b) cambia la medida y necesita aprobación; no se propone como ajuste para que pase.

### Grupo B. M-046: la aclaración de cantidades (D2)

- **Esperaba la lista** (`:458`): fila de `sec-i/14.1` ("cotizar el valor unitario"), D2, efecto `precisa`, tramo `pre/p-16`; el ancla dice que las cantidades a cotizar son las de la cláusula 6 y las del Anexo VII.
- **Qué produjo la pasada:** el emparejado existe (fila 98, `encontrado`), pero sin ninguna fuente de D2. Como D2 no tiene ruido, el cambio de ese tramo no llegó a ninguna fila: ni a la 98 ni a las de la cláusula 6.
- **Camino probable.** D2 es un apartado (`I. RESPUESTA…`, `circular_units.py:187`, `_is_heading`) sin verbo en el encabezado (`detect_change` → `sin_verbo_reconocible`, `_resolve_standard`, `circular_units.py:699`), así que va a la extracción (`circulars.py:833`). El modelo ve la unidad entera y devuelve un cambio por cosa. Para la oración de cantidades, lo natural es `aclara`, objetivo `clausula`, referencia "6". En `_pool_for` (`circular_changes.py:231-250`): hay varias citas de la cláusula 6 (6.1 a 6.4, M-001 a M-005) y no hay texto anterior, y la regla es `aclara` + más de una cita = `clave_ambigua` (`:249-250`). Queda sin resolver y va al respaldo, tramo por tramo; el respaldo (v2) no puso efecto (`sin_efecto` o respuesta sin disposición válida; el tramo no deja ruido).
- **Aunque se hubiera resuelto la cláusula 6, no llegaba a la fila 98**: la fila 98 está en la cláusula 14.1. Solo se llega a ella por el anexo ("completar el Anexo VII", el texto de 14.1). Un cambio `aclara` con objetivo `anexo` y referencia "VII" lo resolvería (`circular_changes.py:264-274`, `_asks_for_annex` mira la cláusula entera, `circular_units.py:626`) y alcanzaría 14.1, 14.2, 6.3 y 7.6.11 entre otras. El modelo no separa el anexo porque las instrucciones v3 no se lo piden: el ejemplo del anexo es solo para `suprime`.
- **Efecto / original / vigente / documento:** los cuatro en falso por falta de fuente.
- **Duda sobre la lista (para el Coordinador, no es un ajuste):** M-046 mapea una oración que habla de "cantidades" a una fila que habla de "valor unitario". Si el responsable la da por buena, se resuelve con el anexo; si no, el esperado es discutible.

### Grupo C. M-060: la fuente no cubre el ancla vigente (D2)

- **Esperaba la lista** (`:591`): fila de `sec-i/18.3`, D2, `aclara`, `pre/p-15`; el ancla vigente tiene **dos oraciones** (cotizar todos los renglones del grupo y la causal de desestimación).
- **Qué produjo:** fila 133, efecto `aclara` (punto 1 verdadero), original mostrado verdadero (punto 2: es la cita de 18.3), documento y fecha verdaderos (punto 4); **vigente falso (punto 3)**.
- **Por qué:** `_source_points` (`evaluation.py:1010`) pide que el texto de la fuente cubra al menos la mitad del ancla (`REQUIRED_OVERLAP = 0.5`, `evaluation.py:100`). La primera oración sola ronda un tercio del ancla; la segunda ronda dos tercios. Para que falle, el texto de la fuente es o la primera oración sola o el encabezado del apartado. El segundo caso ocurre si el modelo deja `texto_nuevo` vacío en una aclaración: `span = change.new_span or units._span_of_head(ctx)` (`circular_changes.py:317`), que es el primer tramo de la unidad (el título "I. RESPUESTA…"), un texto sin sentido como "texto vigente". En el primer caso es la regla de las instrucciones v3 "copiá el fragmento más corto que exprese el cambio completo".
- **Cuál de los dos:** no se puede ver en los archivos. Se cierra con `parsed.cambios` del pedido `circulares_cambios` de D2 (consulta al final).

### Grupo D. M-066, M-067 y M-068: "se ratifican los plazos" (D4)

- **Esperaba la lista** (`:658-684`): las tres filas técnicas de los renglones 1 a 3, D4, 2026-07-15, `aclara`, tramo `pre/p-13` (la respuesta a la consulta 3); la consulta 5 remite a ella.
- **Qué produjo:** las tres filas existen y están bien emparejadas (`encontrado`, tramos técnicos sin 10.7.x entre los faltantes), pero **ninguna recibió fuente de D4** (punto 4 en falso). Ninguna otra fila la recibió tampoco (ruido: solo #107). Es decir, la respuesta sobre los plazos no produjo ningún efecto en ningún lado. Las dos respuestas con cláusula nombrada (consultas 2 y 4, 6.4 y 26.2) sí funcionaron (M-005 y M-063 cumplen), lo que acota la causa a lo que no nombra una clave.
- **Causas, en el orden en que actúan:**
  1. **El encabezado "I.-" no se reconoce.** `_ROMAN_HEADING` (`circular_units.py:133`) y `_ROMAN_PREFIX` (`:134`) exigen un espacio después del punto, y `circulars._HEADING` (`circulars.py:118`) igual. D4 no se parte en un apartado; en `partition` (`circular_units.py:203-240`) cada párrafo cae en la rama final y es una unidad `suelto`. `resolve` devuelve respaldo `tramo_suelto` (`:892-895`) y el procesador manda cada tramo suelto a la extracción de a uno (`circulars.py:833`). Resultado: el modelo lee "Respuesta: …ratifican los plazos…" **sin la consulta**, que es la que dice "ítems 1, 2 y 3" y "parcial inicial". Tampoco el respaldo ve el encabezado (`circulars.py:146`, `context`), solo los dos tramos anteriores recortados a 400 caracteres.
  2. **Sin objetivo.** La respuesta no nombra cláusula ni renglón; el modelo da objetivo `ninguno`; `_pool_for` (`circular_changes.py:276`) devuelve `sin_objetivo` si no hay texto anterior, y el cambio va al respaldo.
  3. **Respaldo sin resultado.** El respaldo elige candidatas con el reranker: las 8 mejores entre todas las citas (`MATRIX_CIRCULAR_CANDIDATES = 8`, `settings.py:274`; `circulars.py:664-670`), con la consulta del tramo solo (sin encabezado). Las citas 10.7.x compiten con 9.1, 21.x y otras que también hablan de plazos. Con cualquiera de las dos (no entran las citas de plazo de entrega entre las 8, o el modelo responde sin efecto por tratarse de una ratificación) el resultado es el mismo: ninguna fuente. Cuál de las dos pasó: `parsed.candidatas.mostradas` y `sin_efecto` de ese pedido (consulta al final).
  4. **Aun con el apartado reconocido faltaría un paso.** Si la unidad fuera el apartado entero, la extracción vería consulta y respuesta juntas y podría devolver `aclara`, objetivo `renglon`, referencia "1, 2 y 3". `_pool_for` (`circular_changes.py:252-263`) exige texto anterior para algo que no sea `suprime` (`sin_texto_anterior`). Con texto anterior ("plazos de entrega"), `match_old_text` (`circular_units.py:367-390`) empata entre 10.7.1, 10.7.2 y 10.7.3 (el mismo texto en cada renglón) y devuelve `texto_anterior_ambiguo` (`:388`). La salida que no necesita código: que el modelo devuelva **un cambio por renglón** (referencia "1", otra "2", otra "3", cada uno con el texto anterior), porque entonces el empate se rompe dentro del grupo de un solo renglón (`_item_candidates`, `circular_units.py:486`). Riesgo: "plazos" contra "plazo" no coinciden como palabra; queda la coincidencia de "de entrega", que también puede aparecer en otras citas del renglón (lugar de entrega, cajas). Hay que medirlo.
- **Efecto / original / vigente / documento:** los cuatro en falso por falta de fuente.

### Agrupado por causa

| Causa | Filas | Archivo:línea (26cb1c0) |
|---|---|---|
| Sin fila por tabla pendiente | M-059 | `evaluation.py:1069`; lectura de tablas |
| La extracción por clave no resuelve (varias citas sin texto anterior; sin objetivo) y el respaldo no devuelve efecto | M-046, M-066, M-067, M-068 | `circular_changes.py:249-250, 252-263, 276`; `circulars.py:664-670` |
| Encabezado "I.-" no reconocido (la unidad pierde su consulta) | M-066, M-067, M-068 | `circular_units.py:133-134`; `circulars.py:118` |
| El anexo no se separa como cambio propio | M-046 | instrucciones `matriz-circulares-v3.md` (ejemplo de anexo solo para `suprime`) |
| Texto de la fuente de una aclaración demasiado corto o igual al encabezado | M-060 punto 3 | instrucciones v3 ("fragmento más corto"); `circular_changes.py:317` |

## 2. M-033 (`sec-i/12.1/v-1`, `tramo_con_requisitos_sin_este`)

- **Qué es:** un renglón de una lista de pasos del portal (el paso de ingreso de garantía, con el valor "exceptuado"), en una viñeta (`v-1`) de la cláusula 12.1, página 10; clase económica.
- **Por qué falta:** el resumen lo da `tramo_con_requisitos_sin_este`: el tramo tiene filas, pero ninguna cubre el ancla. Las filas del tramo son #77 y #78, ambas **sugerencias** `no_coinciden` (`resumen.md:35, 83-84`), y citan otras oraciones del mismo bloque (el valor del módulo y su posible variación). La oración vecina de 12.1 que dice que el oferente queda exceptuado de integrar la garantía y debe consignarlo en el portal sí está: son #75 y #76, sobrantes firmes de `sec-i/12.1`. No hay descartadas en ese tramo (`resumen.md:29`), de modo que **no es un descarte del filtro**: la línea del paso no llegó a ser fila en la extracción ni en la completitud. El extractor tomó las oraciones con verbo ("se establece", "podrá variar") y no la línea de formulario "paso N, campo: valor".
- **Corrección que lo resolvería:** una regla en las instrucciones de extracción (y de completitud): "una instrucción de carga con valor a consignar en un formulario o portal ('Paso N, campo: valor') es requisito si el pliego la exige, aunque no tenga verbo". Es un cambio de prompt de `matriz-extraccion` y `matriz-completitud`, no de circulares: otra tarea (T-106 o la que el Coordinador abra), y hay que medirlo en caso-01 y caso-06 para no sumar sobrantes, porque es el mismo tipo de línea que se ve en los anexos (ver 3).
- **Alternativa de lista (decisión del Coordinador, no mía):** el propio esperado D-02 de `para-el-responsable.md` ya dice que una condición repetida en varios lugares tiene una sola fila; la exención de garantía figura en #75, firme. Si la Comisión considera M-033 una repetición de esa condición, correspondería marcarla repetida o quitarla; no se toca la lista.

## 3. Sobrantes: 147 de 210

**Mismo patrón que caso-01 en lo principal.** El filtro v2 descartó 11 filas y mandó 14 a sugerencia; "sin el filtro" serían 158 sobrantes (`resumen.md:32`). Los descartes que el v1 hacía y v2 deja pasar están acá con las mismas formas que en diag. 2: presentación de facturas tras la recepción (#9, igual que #8 del caso-01), envío por correo a una casilla (#10, #11; igual que #10), deber de confidencialidad (#152; igual que #183), cola de oración (#103; igual que #103). El análisis de diag. 2 (prompt v2, A "mantener", ejemplos desbalanceados, "ante la duda, mantener") aplica sin cambios; no se repite.

**Pesos propios de este caso** (por tramo, a partir de `resumen.md:26` y las citas de `resumen.md:94-243`; las clases son por criterio mío y valen ±3 filas):

| Patrón | Filas | Ejemplos (fila, tramo) | Corrige |
|---|---|---|---|
| 1. Anexos: ítems de listas, preguntas de formulario y filas de tabla (la lista dice 0 entradas propias para los anexos) | 58 de 147 (39 %): anexo-iii 24, anexo-vi 9, anexo-i 7, anexo-vii 6, anexo-v 5, anexo-ii 4, anexo-iv 3 | #172, `anexo-iii/p-2`; #182, `anexo-iii/p-3`; #161, `anexo-i/p-5`; #207, `anexo-vi/p-5`; #217, `anexo-vii/tabla-1` | Filtro v3 y regla de anexos (otra tarea) |
| 2. Oración partida: la fila es un trozo que empieza en minúscula | 48 de 147 (33 %), repartidas por todo el pliego | #51 y #52, `7.6.8`; #83 y #84, `12.4`; #103 y #106, `14.1` y `14.2`; #137 y #139, `19.2` y `19.3` | Unificación apagada (`dedup_containment: false`, `dedup_min_similarity: 1.0`, `parametros.json`) y regla de partición de la extracción |
| 3. Etapas posteriores a la oferta (ejecución, facturación, entrega, impugnación, garantía de cumplimiento) | unas 25 en `sec-i` | #9, `4.12`; #67, `10.3`; #138, `19.3`; #142, `21.2`; #146, `21.4` | Filtro v3 (`ejecucion_contrato`, `derecho_posterior`) |
| 4. Aceptación y deberes generales (jurisdicción, "la presentación implica…", confidencialidad, canal ético) | unas 16: `3.3` 2, `3.4` 3, `13.4` 2, `27.1` 3, `28.1`, `28.2`, `4.7` 2, `5.1`, `9.1` | #2, `3.3`; #4, `3.4`; #95, `13.4`; #152, `27.1`; #154, `28.2` | Filtro v3 (`norma_aplicable`, `obligacion_organismo`) |
| 5. Consecuencias y sanciones como filas propias | unas 8 | #25, `7.3`; #27, `7.4`; #60, `8.3`; #63, `8.5`; #134, `18.3` | Pasada de consecuencias y filtro (`consecuencia_sancion`) |

Los patrones 1 y 2 se superponen en parte (hay trozos dentro de anexos) y el resto del conteo son las condiciones repetidas del D-02 (traducción: #46, #50 a #52; tipo de cambio: #86, #107, #220; Anexo VII: #102, #106, #215), que cuentan en 2 o en 3.

**Lo que sigue sin cerrarse con el filtro solo.** El tope es 20 % de 210 filas firmes = 42 sobrantes como máximo, y hay 147. Aun recuperando las descartadas como en diag. 2 (hasta unas 34), quedarían más de 100. El patrón 2 (48 filas) no lo toca el filtro: es de la extracción y de la unificación; y el patrón 1 (58 filas) pide una regla para anexos. Con 69 entradas esperadas contra 210 filas firmes, la granularidad de la lista (una fila por condición) frente a la del extractor (varias por cláusula) es la diferencia de fondo.

## 4. Correcciones propuestas, ordenadas por impacto

Entran en T-120 los cambios que caben en "constantes y listas de verbos de `circular_units.py` y prompt de circulares" (`tasks.md`, T-120). El resto necesita otra tarea.

| Orden | Corrección | Dónde | Filas / efecto esperado | Entra en T-120 |
|---|---|---|---|---|
| 1 | Reconocer encabezados "I.-", "I -" y "I)": ampliar `_ROMAN_HEADING` y `_ROMAN_PREFIX` (y, para el contexto del respaldo, `circulars._HEADING`) | `circular_units.py:133-134` (constantes); `circulars.py:118` | M-066 a M-068 (paso 1 de la causa D); D4 pasa a ser un apartado y el modelo ve cada consulta con su respuesta. Riesgo: cambia la partición de los casos 01 y 06, hay que re-medirlos | Sí para `circular_units.py`; `circulars.py` no está en la lista de archivos de T-120: pedirlo al Coordinador o dejarlo para otra tarea (sin él, el respaldo sigue sin encabezado en D4, pero la extracción ya ve el apartado) |
| 2 | Instrucciones de `circulares_cambios` v4: (a) "ítem" vale como renglón; (b) si la respuesta alcanza a varios renglones, un cambio por renglón con el texto anterior copiado de la unidad; (c) si una oración nombra una cláusula y un anexo, un cambio por cada objeto; (d) en `aclara`, copiar las oraciones completas que aclaran, nunca dejar `texto_nuevo` vacío | `matriz-circulares-v4.md`, `MATRIX_PROMPT_VERSIONS` | M-066 a M-068 (con 1), M-046 (anexo), M-060 punto 3. Hasta 7 de 8 en REQ-031; la octava (M-059) no depende de esto. Riesgo: más fuentes de D2 sin esperado (ruido informativo, no bloquea) | Sí |
| 3 | Dejar de usar el encabezado del apartado como texto de una aclaración sin `texto_nuevo`: usar el tramo de la respuesta, o mandar el cambio al respaldo | `circular_changes.py:317` | M-060 punto 3 si el caso es el del encabezado; calidad de la pantalla | No (código): otra tarea |
| 4 | Aclaración con varias citas sin texto anterior (`clave_ambigua`): aplicar a todas las citas de una cláusula nombrada o dar una sugerencia | `circular_changes.py:249-250` | M-046 (si la lista se mantiene con la cláusula 6) | No (código y criterio de producto): otra tarea y consulta al responsable |
| 5 | Empate de `match_old_text` entre renglones distintos: aceptar una cita por renglón | `circular_units.py:367-390` | M-066 a M-068 sin pedir un cambio por renglón | No (código): otra tarea; solo si 2(b) no alcanza |
| 6 | Crear fila para tramos de tabla pendientes, o informar "sin medir" | lectura de tablas; `evaluation.py:1069` | M-059; 8 de 8 posible | No: otra tarea y decisión del responsable (cambia la medida) |
| 7 | Regla de extracción y de completitud para líneas de formulario "campo: valor" | `matriz-extraccion`, `matriz-completitud` | M-033; riesgo de sumar sobrantes en anexos | No: T-106 u otra |
| 8 | Filtro v3, tercera pregunta C, regla de anexos y revisión de la unificación apagada | `filter.py`, prompts, `dedup_*` | Sobrantes, patrones 1 a 5; ver diag. 2, sección 3 | No: T-106 |

**Medición que corresponde después (T-120, ronda 1):** caso-05 y caso-01 con 1 y 2; contar M-060, M-066, M-067, M-068 y M-046; mirar que las fuentes de D2 sin esperado no suban demasiado y que el caso-01 conserve sus 15 de 15 (diag. 2). No ajustar más de las dos rondas que dice `tasks.md`.

**Consulta de solo lectura para cerrar las dudas** (cuando la base y la GPU estén libres; no se hizo): sobre la corrida 16 del caso-05, `tenders_run_step` de la pasada `circulares_cambios` con `segment_keys` que incluya `pre/p-11`, `pre/p-15`, `pre/p-16` (D2) y `pre/p-13` (D4): `parsed.cambios` (tipo, objetivo, referencia, `texto_nuevo`, motivo de no resolución) y, para los pedidos de respaldo (`circulares`) de esos tramos, `parsed.candidatas.mostradas` y `sin_efecto`. Con eso se confirma: qué texto copió el modelo en M-060, si M-046 salió como cláusula 6, y si en D4 las citas 10.7.x estaban entre las 8 candidatas.
