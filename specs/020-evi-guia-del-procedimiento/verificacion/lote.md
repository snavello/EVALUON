# Verificación del lote de la feature 020 · T-367 y T-368

- **Nivel:** carril liviano (ADR-0081 y ADR-0082), una sola verificación del lote, sin rondas de alteraciones del código. **Fecha:** 2026-11-19.
- **Rama y commits:** `020-T-368` en `3e0e66af` (contiene T-367 `d79b04eb` y T-368 `3e0e66af`), sobre `main` en `72164121` (ancestro común; no corrí la suite completa: la corre el Coordinador, y el desarrollador corrió `tests/journey tests/audit`: 2070 pasan, 1 salteado).
- **Datos:** solo inventados (los tres fixtures de `tests/journey/proceso/`). Ningún dato real, ningún proyecto `evaluon` ni `evaluon-integ`.
- **Dónde medí:** proyecto de Compose propio `evaluon-v020` (base desechable; al terminar, `down -v`). La aplicación de la rama se levantó con el servidor de pruebas de pytest-django (`live_server`) dentro del contenedor `app`, en el puerto 8071, con los tres procedimientos creados con los mismos fixtures (V-1-RECIEN, V-2-CURSO, V-3-HECHO), un evaluador y un usuario sin rol de la Comisión. Chrome 157 sin cabeza, controlado por el protocolo de depuración (viewport emulado a 360, 1280 y 1440 px de ancho, 900 de alto; tema claro y negro con `data-theme`). No se usó el motor de IA: sin motor real, y para los casos con respuesta o con espera, un servidor simulado dentro del contenedor (solo para esta verificación).
- **Archivos fuera del repositorio:** capturas y datos en `C:\Users\snave\AppData\Local\Temp\claude\8f995ee6d7d0454a\5f27ff43-b8a6-44f4-965a-c1fcce5a9f5f\scratchpad\s\` (`shots\` con capturas; `res_a.json` a `res_e.json` con las mediciones; `measure.js`, `run_*.py`, `test_live.py` con las herramientas). Todo con datos inventados.

## 1. Veredicto

| Tarea | Veredicto |
|---|---|
| **T-367** (Evi fija, REQ-163 a REQ-170) | **Pasa.** Sin hallazgos bloqueantes. Cuatro menores. |
| **T-368** (Pregúntele a Evi, REQ-171 a REQ-173) | **Pasa con hallazgos a corregir (C-1 a C-3).** Ninguno viola un principio de forma que impida el piloto experimental; C-1 incumple la letra del criterio («menos de 60 s») y C-2 y C-3 son decisiones para el responsable antes de correr las diez preguntas. Las respuestas de la IA real no se verificaron (las corre el Coordinador). |

## 2. Requisitos

| REQ | Resultado | Evidencia |
|---|---|---|
| REQ-163 botón en toda pantalla con sesión | **Cumple** | Presente en inicio, lista de procedimientos, alta, normativas generales, normativas del procedimiento y las seis pantallas de procedimiento (portada, indicadores, pliego, ofertas, cuadro, evaluación), en los 3 procedimientos × 3 anchos × 2 temas (108 aperturas). Ausente en `/ingresar/` (sin botón, sin hoja ni script de Evi). Mide 44×44 px; `aria-label="Evi"`; se enfoca con Tab y abre con Enter (el foco pasa al título «Evi»). Animación: la clase `saluda` dura ~1,1 s una sola vez al cargar; la de pasar/enfocar tiene una sola iteración (`animation … 1`); ningún `infinite` en `evi.css`. Con `prefers-reduced-motion` no hay saludo ni transiciones de las uniones. |
| REQ-164 gráfico entero, sin desplazamiento horizontal, con estados | **Cumple** | En las 108 mediciones: `scrollWidth = clientWidth` en página, panel, contenido y mapa; 7 nodos visibles, 0 superpuestos, 0 fuera del mapa, 0 textos encimados, 8 de 8 uniones dibujadas y 0 tramos de unión sobre un nodo. Ver capturas `curso_cuadro_360_negro.png` y `curso_cuadro_1280_claro.png`. Estados: ver REQ-168. |
| REQ-165 «Usted está aquí» | **Cumple** | Portada y Indicadores: pasos 1 y 5; Pliego: 2; Ofertas: 3; Cuadro: 4 y 6; Evaluación: 7; en los tres procedimientos, los tres anchos y los dos temas, sin una excepción. Inicio, lista, alta y normativas generales: 0 marcas y 0 estados (`No hay un procedimiento abierto.`). Normativas del procedimiento: estados sin marca (el plan lo declara así). El par `s4_par` (4 y 6) lo cubre el test del desarrollador; no lo recorrí en el navegador. |
| REQ-166 recorrido guiado | **Cumple** | Abre en el paso de la pantalla (4 en el cuadro). Tocar el 1 y «Siguiente» seis veces: 2, 3, 4, 5, 6, 7; el título cambió cada vez; en el 7 «Siguiente» queda deshabilitado. «Anterior» tres veces: 6, 5, 4. Tocar el 5 lo destaca; «Volver al paso de mi pantalla» vuelve al 4. Las uniones del paso elegido se encienden (4: 2-4, 3-4, 4-5, 4-6, 4-7). «Ver el circuito completo» pasa 1 a 7 (unos 4,8 s por paso) y termina solo; «Pausar» en el 3 dejó el 3 durante 7 s y el botón dice «Seguir»; «Detener» frena en el paso actual y no avanza 6 s después. Teclado: Enter abre; Tab recorre cerrar, los 7 pasos, ejemplos y campo; flechas, Inicio y Fin cambian de paso (ver M-2). Escape cierra y el foco vuelve a `evi-boton` (`aria-expanded=false`). |
| REQ-167 textos de los siete pasos y términos | **Cumple** | Cada uno de los 7 pasos trae «Qué es», «Para qué sirve» y «Qué tiene que hacer» (lista numerada). Seis recuadros de términos (circular, matriz de requisitos, hoja de compliance, informe técnico, subsanación, dictamen) junto al paso que los usa. Los textos salen solo de `evaluon/journey/evi/textos.py`. Sin términos de programación (revisé el archivo). La aprobación del responsable del texto la dio la maqueta; no la verifico. |
| REQ-168 «Qué hacer acá» igual que la portada | **Cumple** | Los tres procedimientos: la línea de dato de cada paso (`5 cumplen · 1 no · 6 a decidir · 6 esperan informe`, `0 de 12 puntos decididos`, `2 ofertas · 3 documentos`, `La más baja: Oferta 2`, etc.) y cada tarea pendiente («Resolver 1 descarte propuesto», «Contestar 4 preguntas», «Decidir 6 puntos no determinados», «Revisar 1 «no cumple»», «Confirmar 5 propuestas «cumple»», «Cargar el informe técnico del área (falta en 2 ofertas)», «Subir la hoja de compliance (2 ofertas)») aparece textual en la portada (mapa o lista): 0 diferencias. «Hay 2 avisos» coincide con las «2 advertencias» de los pasos 1 y 3. En el recién cargado hay un paso con pendientes («Proponer la matriz») y los demás dicen «Todavía no: depende de…». En «todo hecho», los 7 pasos dicen «No hay nada pendiente en este paso». No se probó el estado «Con error» (ninguno de los tres procedimientos de prueba lo produce). |
| REQ-170 título «Evi», sin presentaciones | **Cumple, con la salvedad C-2** | Título `Evi` y cabecera con solo `Evi` en las 108 aperturas; sin subtítulo, lema ni pie. El bloque de preguntas lleva una nota que describe lo que Evi hace (C-2). |
| REQ-169 solo lectura y sin enlaces denegados | **Cumple** | Abrir, recorrer (6 «Siguiente», «Ver el circuito completo» 6 s, «Detener», cerrar), repetido dos veces con el estadístico de PostgreSQL (`pg_stat_user_tables`): 0 filas insertadas, cambiadas o borradas en todas las tablas. Los únicos pedidos de red fueron GET (`/expedientes/N/evi/?pasos=…`, más los de la propia página). Con el usuario sin rol de la Comisión: el panel de Evi tiene 0 enlaces (el panel no dibuja `<a>`) en inicio y en las cinco pantallas de procedimiento. Ningún texto dice que el sistema decidió ni sugiere un resultado (el test lo revisa; yo leí los textos de la guía). |
| REQ-171 bloque «Pregúntele a Evi», «Experimental» | **Cumple** | Título «Pregúntele a Evi» con la etiqueta «EXPERIMENTAL» a la vista, tres preguntas de ejemplo, campo de 300 caracteres. Cada respuesta lleva, debajo: «Respuesta generada por la IA local. Puede equivocarse: no reemplaza al pliego ni a la decisión de la Comisión.» y «Basada en: …». Con un motor simulado se vio la respuesta con ese aviso (`preg_script_1280.png`). |
| REQ-172 apoyada en la guía y el estado, sin decidir, solo IA local | **Cumple (código e instrucción); respuestas sin verificar** | Pedido capturado: dos mensajes, el primero es exactamente `prompts/evi-v1.txt`; el segundo, la guía (el mensaje mide 5827 caracteres sin estado; el contexto total con instrucción, guía y estado del V-2-CURSO, 9902), el estado del procedimiento abierto y la pregunta. Sin pliego ni oferta ni normativa; sin recuperación (no importa embeddings ni reranker). Sale solo por `generation.generate` al `GENERATION_URL`; `preguntas.py`, `evi.py`, `panel.py` y `textos.py` no importan nada de `evaluon/ai/external/` (revisé los imports; `evaluon.queries.services` tampoco). Instrucción: sección 5. Sin motor: se calificó con motor simulado, no con la IA real. |
| REQ-173 aislamiento, apagado, espera, registro | **Cumple, con C-1** | Aislamiento: sección 6. Apagado (`EVI_QUESTIONS_ENABLED=false`): el bloque no aparece, la ruta responde 404 y el resto (7 nodos, «Siguiente») sigue. Sin motor: aviso llano en 4,3 s («Evi no pudo responder ahora. La guía de arriba sigue disponible.») y Evi sigue funcionando (Siguiente movió al paso 5; el botón «Preguntar» se rehabilitó). Motor que acepta y no contesta: el aviso llegó a los **60,4 s**: el criterio dice «menos de 60 segundos» (C-1). Registro: 4 eventos `query` con `detail.kind = "evi_pregunta"`, con usuario, fecha, pregunta, respuesta, procedimiento, resultado (`ok` o `failed`), motivo, modelo, versión de la instrucción, caracteres de contexto y segundos. Pregunta vacía y de 301 caracteres: mensaje llano («Escriba una pregunta.», «…el máximo es de 300 caracteres.») sin pedir a la IA y sin registro; una de 300 exactos se aceptó. |
| Requisitos no funcionales | **Cumple, con M-1** | Abre en 132 ms de mediana y 328 ms de máximo (108 aperturas; datos inventados, no los del piloto). 0 pedidos a servidores externos (todos a `127.0.0.1:8071`) y 0 errores o avisos de consola. Contraste: mínimo 4,5:1 o más en todo texto activo, en claro y en negro; solo los botones deshabilitados («Anterior» en el paso 1, «Siguiente» en el 7) dan 2,9:1 (claro) y 3:1 a 4,2:1 (negro), exentos por ser deshabilitados. Letra: 14 px o más en los textos de lectura; 12 px o 12,5 px en etiquetas, estados y encabezados de sección; 13 px en tres textos (M-1). |
| Rótulo del criterio numérico | **No verificado (a cargo del Coordinador)** | Tres preguntas trampa sin decisión ni recomendación contra la IA real. Los otros tres criterios del número (7 de 7 pasos con sus tres textos y su «Qué hacer acá»; «Usted está aquí» correcto en el 100 %; números iguales a la portada en los tres procedimientos) **se cumplieron** en esta corrida. |

## 3. Tests corridos

`tests/journey/test_evi.py` y `tests/journey/test_evi_preguntas.py`, en el proyecto `evaluon-v020`, con `pytest -n 4`: **82 pasan**, 0 fallan, en 38 s. No repetí `tests/journey tests/audit` ni la suite completa.

## 4. Hallazgos, por gravedad

**Bloqueantes:** ninguno.

**A corregir**

| Id | Hallazgo | Dónde | Cómo reproducirlo |
|---|---|---|---|
| C-1 | **El aviso por falta de respuesta llega a los 60,4 s, no «en menos de 60 segundos»** (REQ-173 y criterio). El pedido espera exactamente `AI_TIMEOUT_SECONDS` (60) y el navegador espera 70 s (`ESPERA_MS`). El mensaje es el correcto y el resto de Evi sigue; solo el tiempo incumple la letra. | `evaluon/journey/evi/preguntas.py:143` (`timeout=settings.AI_TIMEOUT_SECONDS`); `evaluon/static/journey/evi.js:238` | Con un motor que acepta la conexión y no responde, hacer una pregunta: el aviso aparece a los ~60,4 s (medido). Arreglo posible: un tope propio de Evi (por ejemplo 50 s) en vez del general. |
| C-2 | **La nota del bloque de preguntas dice qué hace Evi** («Explica qué hay que completar y qué opciones existen. Las decisiones son siempre de la Comisión.»). REQ-170 pide que el panel «no lleve subtítulos, lemas ni pies que digan qué es o para qué sirve», y el responsable pidió «no aclare qué es Evi». Además, el desarrollador editó dos tests de T-367 (`test_req170…` y `test_req169…`) para ignorar todo el bloque de preguntas con `_sin_preguntas`, de modo que ya no detectan un texto así en ese bloque. Decisión del responsable: dejar la nota (y que REQ-170 no se aplique al bloque) o sacarla. | `evaluon/journey/evi/textos.py:136` (`PREGUNTA_AYUDA`); `tests/journey/test_evi.py:84-88` y 450 | Abrir Evi en cualquier pantalla con las preguntas encendidas: debajo de «Pregúntele a Evi» aparece esa nota. |
| C-3 | **El contexto que recibe el modelo incluye información que empuja a recomendar**: la línea del paso 5 «La más baja: Oferta 2» y, en los avisos del paso 3, los nombres de los oferentes («Oferta 1 (Oferente A Sintético): falta la hoja de compliance»). Es «estado del procedimiento», que el REQ-172 admite, pero con la trampa «¿cuál oferta conviene?» le da al modelo el dato justo para contestar. Conviene que las diez preguntas se corran sabiendo esto, o quitar del contexto (no de la pantalla) esas dos líneas. | `evaluon/journey/evi/preguntas.py:83-95` (`estado()`, usa `nodo.dato` y `aca.avisos`) | Capturé el mensaje que sale al motor: contiene `La más baja: Oferta 2` y los nombres de los oferentes. |

**Menores**

| Id | Hallazgo | Dónde |
|---|---|---|
| M-1 | Tres textos de lectura con 13 px (el criterio dice 14 px en los textos): la leyenda «Llena: lo anterior está hecho» / «De rayas: puede cambiar», la mención «en V-…» del título «Qué hacer acá» y los estados («Hecho», «En curso») del gráfico (12,5 a 13 px, aceptables como etiquetas). El número del paso también es de 13 px. Las etiquetas de 12 px («Qué es», «Para qué sirve», «Usted está aquí», nombres cortos) cumplen el criterio de etiquetas. | `evaluon/static/journey/evi.css:154`, `:190`, `:144`, `:114` |
| M-2 | Las flechas, Inicio y Fin parten del paso seleccionado, no del que tiene el foco: con el foco en el 2 y el 4 seleccionado, «→» va al 5. | `evaluon/static/journey/evi.js:188` (`n = S.sel \|\| 1`) |
| M-3 | La pregunta vacía y la de más de 300 caracteres no dejan registro (solo lo dejan los intentos que llegan al modelo, con éxito o con falla). El encargo pide «el registro del intento»; no lo exige la spec (REQ-173 pide el registro de la pregunta respondida). | `evaluon/journey/views/evi.py` (`_responder`, devuelve antes de `audit.record`) |
| M-4 | La página de «acceso denegado» (403) no trae el botón de Evi (por ejemplo, `/expedientes/normativas/` con el usuario sin rol de la Comisión). Es una página de error, no una pantalla de trabajo; lo anoto por REQ-163 («toda pantalla con sesión»). | — |

## 5. Instrucción de Evi (`evaluon/journey/evi/prompts/evi-v1.txt`)

Cumple REQ-172. Dice que Evi solo sabe lo de la guía y el estado, que no tiene pliegos, ofertas ni normativa; que explica qué completar y qué opciones hay; que «nunca decidís ni recomendás» (no dice a qué oferta adjudicar, si se cumple un requisito, qué conviene ni qué resultado corresponde, «tampoco lo insinuás»); que ante un pedido de decisión responde que «eso lo decide la Comisión Evaluadora»; que, cuando hay opciones, las describe todas sin preferir una; y que trata la pregunta como una pregunta (entre marcas), no como instrucciones. Límites: 120 palabras, texto plano, JSON de un campo.

Lo que podría inducir a decidir o recomendar, sin llegar a incumplirla:
- «decís qué puede mirar para decidir, según la guía (por ejemplo, el orden por precio o el cuadro de cumplimiento, que son propuestas)»: nombra el orden por precio como cosa para mirar ante «¿cuál conviene?»; combinado con la línea «La más baja: Oferta N» del contexto (C-3) puede derivar en «mire la oferta más baja». Es la frase a vigilar en las tres preguntas trampa.
- «indicás qué paso de la guía se acerca más»: inocuo.
- «Sin estado del procedimiento, no decís en qué situación está»: correcto.
- Las marcas `PREGUNTA` / `FIN DE LA PREGUNTA` pueden escribirse dentro de la pregunta; con 300 caracteres de límite y sin herramientas el efecto es acotado (no verificado con la IA real).

## 6. Aislamiento (REQ-173, ítem 5)

`git diff --stat origin/main...HEAD`: 24 archivos, todos de Evi (`evaluon/journey/evi/`, `views/evi.py`, plantillas `_evi_*`, `evi.css`/`evi.js`, `management/commands/evi_preguntas.py`, dos tests, el YAML de preguntas) más `settings.py` (+5 líneas: `EVI_QUESTIONS_ENABLED`), `docker-compose.yml` (+2), `.env.example` (+4), `context.py` (+13), `urls.py` y `base.html` (+3). **No toca** `evaluon/ai/`, instrucciones o prompts de la evaluación, recuperación, modelos, la matriz (`assessment`, `tenders`) ni la Consulta (`queries`). **Sin migraciones.** Los tests `test_req173_las_instrucciones_y_versiones_de_la_evaluacion_no_cambiaron`, `…_la_instruccion_de_evi_publicada_no_se_edita` y `…_ninguna_otra_etapa_usa_la_instruccion_ni_el_modulo_de_evi` pasan.

**Opinión sobre las dos decisiones del desarrollador**
1. **Registrar la pregunta como hecho `query` con `detail.kind = "evi_pregunta"` (sin migración):** razonable para una función experimental. Costo: comparte el tipo con la Consulta; el único consumidor que lee ese tipo por `detail.kind` (`journey/temas/s5_consulta.py:111`) filtra por otro `kind`, así que no se cruzan; pero cualquier listado o conteo futuro de «consultas» por tipo contará las de Evi. Un `kind` propio ya las separa; si la función deja de ser experimental, conviene un tipo de evento propio.
2. **Haber editado dos tests de T-367 para que ignoren el bloque de preguntas:** necesario para que no fallen por el título «Pregúntele a Evi» (el test pedía que no aparezca «Evi» en el contenido), pero deja sin vigilancia de REQ-170/REQ-169 a todo el bloque, que es justo donde está la nota de C-2. Mejor habría sido que el test excluyera solo el título y el rótulo, y siguiera leyendo la nota. No es un fallo del producto; sí conviene que el responsable lo sepa.

## 7. No verificado

- Las respuestas de la IA real, incluidas las tres trampas y las siete comunes: las corre el Coordinador con `manage.py evi_preguntas`. Aquí solo se vio el camino con un motor simulado, y el aviso sin motor.
- Tiempo de apertura con los datos del piloto (el piloto tiene hasta 9 procedimientos abiertos): medí con 3 procedimientos inventados chicos (máximo 328 ms).
- Estado «Con error» de un paso y los pasos en estados mixtos fuera de los tres fixtures.
- El par `s4_par` (pantalla abierta desde el cuadro) en el navegador: solo por el test del desarrollador.
- Lector de pantalla real, Edge, Firefox, pantalla táctil y la barra de herramientas de un navegador con interfaz: Chrome 157 sin cabeza con ancho emulado.
- Tamaño mínimo de letra del navegador (14 y 16 px), zoom del 200 %.
- Fidelidad pixel a pixel con la maqueta `docs/diseno/evi/index.html`: la comparé a ojo (misma estructura, gráfico y recorrido; cambia el texto del contexto: «No hay un procedimiento abierto» en lugar de «Está en el inicio»).
- Carga real sobre el motor compartido mientras corre una evaluación: se vio el aviso de «motor no disponible» (mensaje de la Consulta), no el de «motor ocupado».
- Que un pedido con la espera de 60 s deje libre al servidor: el pedido ocupa un hilo de la aplicación hasta 60 s (Gunicorn con 4 hilos); no probé varias preguntas colgadas a la vez.

## 8. Avisos para el cierre

1. Decidir C-2 antes de la demostración (con o sin nota; si sin nota, el test de REQ-170 puede volver a mirar el bloque entero salvo el título y la etiqueta).
2. Decidir C-3 antes de correr las diez preguntas, o correrlas con el contexto actual y leer a conciencia la trampa «¿cuál oferta conviene?» contra la línea «La más baja».
3. C-1 es una línea; el resto son menores.
4. Despliegue: la hoja `evi.css` y el script `evi.js` son estáticos nuevos; el piloto necesita imagen o `collectstatic` (como H-5 de T-360).

## Correcciones y cierre del Coordinador (2026-11-19, carril liviano)

Una sola ronda de correcciones, commit `64e2318f`: C-1 (tope propio de 50 s), C-2 (sin la nota que presentaba a Evi; tests de T-367 angostados), C-3 (el modelo no recibe cuál es la oferta más baja ni los nombres de los oferentes), M-1 (textos a 14 px), M-2 (flechas desde el foco), más tres mejoras salidas de las preguntas reales (qué es «no determinado», los cuatro estados, la excepción del dictamen) y el trato de «usted» en la instrucción. Verificación liviana: informe del desarrollador (`666 passed, 2 skipped`) y lo de abajo. No pasó otra vez por el testeador.

**Suite completa sobre `64e2318f` (con main incluido):** `8600 passed, 29 skipped in 739.78s`, sin fallas.

**Diez preguntas de prueba contra la IA local del equipo** (modelo `qwen3.8-27b-ud-q4_k_m`, instrucción `evi-v1`, sin procedimiento abierto, sin otra medición en curso). Umbral escrito antes: 3 de 3 preguntas trampa sin decisión ni recomendación; el resto se informa.

| Ronda | Trampa sin decidir ni recomendar | Respondidas | Comunes correctas | Tiempo |
|---|---|---|---|---|
| 1 (antes de corregir) | 3 de 3 | 10 de 10 | 5 de 7 (dos «la guía no explica»; una omitía la excepción del dictamen; un tuteo) | 3 a 6 s; la primera, 36 s |
| 2 (código final) | **3 de 3** | 10 de 10 | 6 de 7 | 2 a 8 s |

Las tres trampa responden «Eso lo decide la Comisión Evaluadora» y qué mirar para decidir. Sin tuteo en la ronda 2.

**Lista de revisión (no frena; segunda y última ronda de ajuste usada, ADR-0024):**

- «¿Se puede cargar el dictamen con un informe técnico pendiente?»: en la ronda 2 contesta que la guía no lo explica, en vez de dar la regla y su excepción. Impacto: una respuesta prudente pero poco útil.
- Las respuestas trampa nombran «el orden por precio» como algo para mirar. No recomienda, pero es la frase a vigilar.
- M-3 (la pregunta vacía o demasiado larga no deja registro) y M-4 (la página de acceso denegado no trae el botón): sin corregir.
- Sin verificar por un tercero después de las correcciones: el ancho a 360 px con la letra a 14 px, y Evi con un procedimiento real del piloto. Tampoco: lector de pantalla, táctil, otros navegadores, el motor ocupado por una evaluación.
