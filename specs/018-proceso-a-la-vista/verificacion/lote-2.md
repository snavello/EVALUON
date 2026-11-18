# Verificación del lote 2 de la 018 · T-355, T-356, T-357, T-358, T-359 y T-363 (segunda vez)

- **Nivel:** carril liviano (ADR-0081): una sola verificación al cierre del lote, sin rondas de alteraciones a propósito. **Fecha:** 2026-11-18.
- **Rama / commit:** `018-lote2` en `511be83d` (`main` + las cinco tareas + el commit de gestión del tope de 3 segundos). No se tocó código, `tasks.md`, la spec ni el tablero.
- **Entorno:** copia `.claude/worktrees/lote2`; proyecto de Compose `evaluon-v018l2` (tests del encargo) y `evaluon-v018l2m` (mediciones propias, sobre una copia del código extraída con `git archive` más archivos de medición que no están en el repositorio); `--env-file` de la raíz en solo lectura, `MSYS_NO_PATHCONV=1`. No se tocaron la raíz, `evaluon` ni `evaluon-integ`. Chrome 157 sin cabeza (`--headless=new`, ventana = ancho pedido + 22 px, barra vertical de 15 px). Los dos proyectos se bajan con `down -v` al terminar.
- **Material propio** (fuera del repositorio): `C:\Users\snave\AppData\Local\Temp\claude\8f995ee6d7d0454a\5f27ff43-b8a6-44f4-965a-c1fcce5a9f5f\scratchpad\lote2\verificacion\` (`capturas\` PNG, `html\` páginas autocontenidas, `out\` mediciones en JSON, `h\` herramientas, `m\tests\journey\proceso\test_zz_*.py` pruebas de medición, `suite.txt` salida de los tests).
- **Cómo medí el mapa:** una prueba pide la portada con el cliente de Django (los tres fixtures, «Vence hoy» y «Vencido» con cronograma, siete tarjetas llenas con 5 y con 3 tareas y 2 advertencias, y 14 textos de estrés por 4 variantes: letras anchas, símbolos, dígitos, palabra de 73 letras, tildes, emojis, chino, el texto del fixture, el texto de H-A1 de la verificación anterior, errores de 150, 220 y 330 caracteres, 120 «Z» y mayúsculas) y guarda el HTML que sirvió la aplicación y, con un espía sobre `portada._geometria_de`, el alto estimado de cada tarjeta. Con hojas, fuentes y logo incrustados, Chrome mide cada tarjeta (alto real, solapes, fuera del lienzo, conectores contra tarjetas y textos, tareas ocultas por la red de seguridad). 72 páginas con la tipografía del sitio y 64 con cada una de Verdana, Courier New, Arial, `system-ui` y con tamaño mínimo de letra emulado de 14 y 16 px (`font-size` forzado dentro de las tarjetas), en total 456 mediciones. Un primer pase contó como «texto fuera de la tarjeta» y «conector sobre texto» las tareas cortadas por la red de seguridad (siguen en el DOM, fuera de la caja y recortadas); corregí el medidor para ignorarlas (es un falso positivo del medidor, no del producto) y repetí todo.

## 1. Veredicto por bloque

| Bloque | Resultado | Resumen |
|---|---|---|
| A · Mapa (segunda verificación de T-363) | **Pasa, con avisos** | 0 tarjetas superpuestas, 0 fuera del lienzo, 0 conectores sobre tarjeta ajena o texto en 456 mediciones (7 tipografías, mínimos de 14 y 16 px, claro y negro). Con la tipografía del sitio el real nunca supera al estimado (holgura mínima 14 px). Avisos A-1 a A-4 sobre la red de seguridad con otras tipografías |
| B · Recorrido con los tres roles | **Pasa, con avisos** | 9 recorridos (3 roles × varios, «Vence hoy», «Vencido»), 140 páginas cada uno: ningún 404 ni 500, ningún marcado escapado. Evaluador y operador: 140 de 140 en 200. Sin rol: 39 de 140 dan 403 (todos anteriores a la feature). Cifras coherentes entre inicio, portada, mapa, lista, cuadro y filtros |
| C · Cuadro (T-355) | **Pasa, con un aviso** | Cada filtro deja exactamente las filas que corresponden y su contador coincide; grupo resumido; columna fija y pista con 10 ofertas; misma `Decision` y mismo hecho de auditoría desde el panel con filtro que desde el par. Aviso C-1 sobre «Siguiente a decidir» |
| D · Inicio (T-356 y T-357) | **Pasa** | REQ-150 y REQ-151 con sus criterios; lila y rojo con texto; sin cookie del último procedimiento; 20 abiertos en 1,71 s y 21 «varios en curso» en 2,51 s y 2,29 s (mediana de 5), con tope 3 s |
| E · Vocabulario y cierre (T-358 y T-359) | **No pasa por un punto** | Los siete nombres coinciden en inicio, portada, mapa, lista y cuadro, y no aparece «Expedientes» como nombre de la lista. «matriz de cumplimiento» (en minúscula) sigue nombrando la lista de requisitos en tres textos de pantalla (H-1) |
| F · Higiene | **Pasa** | Sin `style=` ni scripts ni direcciones externas nuevas; sin texto bajo 12 px en lo nuevo; AA en los dos temas (mínimo 5,02:1 claro y 5,09:1 negro); sin `id` duplicados; la página nunca se desplaza de costado en 112 mediciones; `makemigrations --check`: «No changes detected» |
| G · Tests | **1 fallo, por carga** | Parte 1: 751 passed. Parte 2: 3594 passed, 1 failed, 2 skipped; el que falla es el tope de tiempo del inicio con 20 abiertos (5,39 s con la máquina cargada; aislado pasa con 1,88 s y 1,45 s). Ver 3 |

## 2. Veredicto por tarea

| Tarea | Resultado | Por qué |
|---|---|---|
| T-363 (mapa rehecho) | **Pasa** | Cierra H-A1 a H-A4 de la verificación anterior en lo que se puede medir con la tipografía del sitio (holgura de 14 px por tarjeta, `acortar`, red de seguridad por `max-height`, «Ver todo en la lista»). H-B1 resuelto: 4→5 y 4→7 tienen troncos separados y se siguen. Quedan los avisos A-1 a A-4 con otras tipografías |
| T-355 (filtros, grupos, «Siguiente») | **Pasa** | Bloque C. Aviso C-1 |
| T-356 (abiertos y terminados) | **Pasa** | Terminados por dictamen cargado y de vuelta a abiertos al quitarlo (probado con el flujo real de carga y `withdraw`); tests de `test_lote.py` en verde; dos consultas |
| T-357 (inicio) | **Pasa** | Bloque D. Avisos D-1 y D-2 |
| T-358 (vocabulario) | **No pasa** | H-1: REQ-155 queda incompleto en tres textos de estados vacíos; el test no lo detecta |
| T-359 (cierre técnico) | **Pasa, con un aviso** | `DefPaso.seccion` retirado, `cuadro_url` por `reverse`, el `<h2>` Indicadores ya no precede al `<h1>`, guía visual al día (§3.2 a §3.4). El glosario (`docs/glosario.md`) no cambió: es un glosario de códigos generado (`tools/glosario.py`) y no tiene los términos que pide la tarea (aviso E-2) |

## 3. Tests (salida literal)

Parte 1 (`pytest tests/journey/proceso tests/journey/test_contraste.py tests/journey/test_no_external.py tests/journey/test_vocabulario.py -q -rs`):

```
...............................                                          [100%]
751 passed in 261.01s (0:04:21)
```

(`-rs` no listó ningún omitido.) Parte 2 (`pytest tests/journey tests/assessment tests/offers -n 2 --dist worksteal -q`):

```
FAILED tests/journey/proceso/test_inicio_rendimiento.py::test_req150_veinte_abiertos_en_dos_segundos
1 failed, 3594 passed, 2 skipped in 1844.41s (0:30:44)
E       assert 5.390823233989067 <= 3.0
E        +  where 5.390823233989067 = <function median at 0x73b8423936a0>([4.9740919610485435, 5.7948312980588526, 5.390823233989067, 5.693932059919462, 5.3732940120389685])
tests/journey/proceso/test_inicio_rendimiento.py:35: AssertionError
```

Los 2 omitidos no se identificaron (la parte 2 se corre sin `-rs`, como pide el encargo). La corrida duró 30 min 44 s porque corrí Chrome y otro proyecto de Compose a la vez; por eso los tiempos de esa corrida están inflados. El mismo test, solo y sin otra carga, dos veces:

```
[inicio, 20 abiertos] mediana 1.88 s (tiempos [1.88, 1.88, 2.07, 1.66, 2.24]), 1448 consultas
[inicio, 1 varios en curso] 0.11 s, 120 consultas
2 passed in 28.15s
[inicio, 20 abiertos] mediana 1.45 s (tiempos [1.42, 1.72, 1.35, 1.45, 1.99]), 1448 consultas
2 passed in 26.46s
```

Y en la parte 1 (con Chrome corriendo al lado): `[inicio, 20 abiertos] mediana 2.38 s (tiempos [2.23, 2.17, 2.38, 2.67, 2.76]), 1448 consultas`. El fallo de la parte 2 es de carga, no de la aplicación, pero indica que ese test es frágil bajo `-n 2` en una máquina ocupada (aviso G-1). No corrí la suite completa (la corre el Coordinador). `makemigrations --check --dry-run`: `No changes detected`.

## 4. Bloque A en detalle (mapa)

### Tabla A-1 · Resultados por tipografía (portada, 1440 px; páginas = fixtures + textos de estrés; «nombre» = el nombre del paso reemplazado por el texto de estrés, que en el producto es constante)

| Tipografía | páginas | solapadas | fuera del lienzo | conector sobre tarjeta ajena | conector sobre texto | tarjetas con real > estimado | tareas ocultas por la red | de ellas sin «+ N más» ni «Ver todo» |
|---|---|---|---|---|---|---|---|---|
| Sitio (Hanken Grotesk) | 72 | 0 | 0 | 0 | 0 | **0** (holgura mínima +14 px) | 21 (solo con el nombre de 330 o 120 letras) | 0 |
| system-ui | 64 | 0 | 0 | 0 | 0 | 0 | 21 | 0 |
| Arial | 64 | 0 | 0 | 0 | 0 | 0 | 21 | 0 |
| Verdana | 64 | 0 | 0 | 0 | 0 | 42 (hasta 9 px: textos de dígitos y letras anchas) | 50 (8 con 120 «Z») | 0 |
| Courier New | 64 | 0 | 0 | 0 | 0 | 4 (+9 px en la tarjeta 2 del caso A: 128 contra 119) | 42 | 0 |
| Mínimo 14 px | 64 | 0 | 0 | 0 | 0 | 42 (1 px) | 36 | 0 |
| Mínimo 16 px | 64 | 0 | 0 | 0 | 0 | 47 (hasta 18 px) | 163 (5 son solo el relleno inferior de un renglón recortado, con el texto entero) | **42** |

Las 14 familias de texto de la verificación anterior (incluido el de H-A1, «Falta la hoja de compliance de CERRAJERIA … JORGE Trescientas José», y los errores de 150 a 330 caracteres) quedan con holgura de 14 px o más con la tipografía del sitio. Con Verdana y Courier el real supera al estimado en algunas tarjetas, pero la fila de abajo no se pisa (la separación de 12 px más el redondeo al escalón alcanzan) y la red recorta lo que sobra.

### Lo que hace la red de seguridad y cuándo no avisa

- Cuando recorta, **corta entre tarea y tarea**, nunca a media línea: las que no entran pasan a una segunda columna fuera de la caja (`overflow: hidden`). No encontré una tarea cortada a media línea con textos que el sistema genera; el único caso de corte a media tarea es con el nombre del paso de 330 letras, que no existe en el producto (los nombres son constantes de `pasos.py`). Los textos de una tarea están acotados por `LIMITE_TAREA = 110` (con «…» y el completo en `title` y en la lista), así que **un texto único no puede ser más alto que una tarjeta** (110 caracteres a 16 px ocupan unas 6 líneas, 120 px; el último escalón es de 432 px). Las 5 marcas «parcial» de mi medidor con mínimo de 16 px y una sola tarea de mayúsculas eran el relleno inferior del renglón recortado: el texto estaba entero (capturas `corte_min16_mayus_sintexto.png`).
- **«Ver todo en la lista» solo sale si la estimación pasa del último escalón (`t.excede`) y no hay «+ N más»** (`_mapa.html:38`, `portada._geometria_de`). **No se ofrece cuando la estimación queda corta y no hay «+ N más»**: con tamaño mínimo de 16 px, 42 tarjetas (las siete, en cada una de las 6 páginas con 3 tareas largas, p. ej. errores de 150 caracteres) esconden la tercera tarea y no dicen nada (`corte_min16_err150_tres.png`). Con la tipografía del sitio no ocurre en ningún caso medido (el único «Ver todo» aparece donde corresponde: 120 «Z» seguidas en la tarjeta 4).
- Cuando sí hay «+ N más», **N no cuenta la tarea oculta**: con 16 px el caso A muestra «+ 2 más» en la tarjeta 6 y esconde 3 (`corte_min16_A_varios.png`).
- **Teclado:** las tareas ocultas siguen siendo enlaces enfocables. Con Tab sobre una oculta, la caja de tareas se desplaza 234 px de costado, aparece la oculta y desaparecen las visibles (medido en la tarjeta 6 con 16 px: `scrollLeft` 0 a 234, primera tarea fuera de la caja). Es un salto visual dentro de la tarjeta, no una pérdida de contenido.

### Conectores 4→5 y 4→7

Con los troncos a 12 px del borde de la 4 (4→5) y de la 7 (4→7), cada flecha se sigue de punta a punta sin cruces, a 1× y a 2× (capturas `zoom1x_A_varios.png` y `zoomcrop_A_varios__portada__claro.png`): la que baja más cerca de la 5 entra a su borde derecho con la punta a la izquierda, la otra entra a la 7 por su borde izquierdo con la punta a la derecha. Reservas menores: las dos comparten con 4→6 el tramo horizontal de salida, las puntas miden 8 px y los dos troncos quedan a 25 px uno del otro, de modo que a tamaño normal y con una mirada rápida se leen como una franja de dos rayas verticales con dos puntas enfrentadas (se entiende con un segundo vistazo, sin duda de destino).

### «Qué se puede hacer ahora» a 1440 × 900 (caso de la maqueta A)

951 px desde el tope en el tema claro y 896 px en el negro (declarado: 951). Los 55 px de diferencia son el aviso «La lectura de … terminó» que muestra la primera carga de la página (el mensaje se consume y en la segunda carga no está): sin el aviso son 896. Con cronograma real: 1110 px con «Vence hoy» y 1038 con «Vencido» (la línea de plazos con eje); recién cargado 851 px; todo hecho 839 px; `?vista=lista` no se midió en este pase. 1280 × 800 da lo mismo que 1440 × 900. Los 951 px quedan por debajo de los 1.457 de antes del rehacer y por encima de los 919 de la primera versión (más ancho de tarjeta y holgura).

### Lo que se ve desparejo (capturas)

Las filas de arriba tienen tarjetas de alturas distintas (las 4 y 6 con tres tareas son 40 a 60 px más altas que la 1 y la 2) y, entre las dos filas, queda un espacio de 60 a 100 px bajo las tarjetas más bajas (consecuencia de «a la medida», ya señalada como H-B2). En «Vence hoy» con cronograma el eje de plazos ocupa unos 200 px para dos hitos del mismo día. La leyenda «Advertencia» es un anillo y en la tarjeta un círculo con «!» (H-B3, sin cambios).

## 5. Bloque B en detalle (recorrido y cifras)

- **Recorrido:** por rol y escenario, a partir de `/`, `/expedientes/`, la portada (mapa y lista), el cuadro con y sin filtro, la lista de terminados, y siguiendo cada enlace interno visible hasta 140 páginas (portada, pestañas, cuadro con cada celda y cada filtro, páginas del par, exportaciones, etc.; el recorrido es por ancho y no agotó todo el sitio). Evaluador y operador: 140 de 140 con 200 en los tres escenarios. Rol sin Comisión: `/` redirige (302) a `/consulta/` (anterior a la feature y pedido por T-357); `/expedientes/` y la portada abren; 100 de 140 con 200 y 39 con 403.
- **Los 403 del rol sin Comisión, todos anteriores a la feature** (el botón de «+ Nuevo procedimiento» del inicio ya existía en `expedientes.html` de `main`; el resto son de la pestaña Pliego y de la pestaña Evaluación, ya listados por T-359): `/expedientes/nuevo/` (desde el inicio), `/procedimientos/documentos/N/original/`, `/procedimientos/requisitos/N/historial/` (9), `/procedimientos/matrices/N/imprimir/`, `.../pdf/` y `.../descartadas/`, `/expedientes/N/evaluacion/par/N/M/` (9), las 4 exportaciones de la evaluación y `/ofertas/documentos/N/original/` (3). Ninguna pantalla nueva del lote da 403 a ese rol: inicio, portada, mapa, lista, cuadro con filtros y panel dan 200.
- **Marcado escapado:** 0 páginas en los 9 recorridos (se buscó `&lt;` seguido de etiquetas conocidas en el texto de cada página; el panel del cuadro sin rol de la Comisión se ve igual que con rol, sin el enlace al original).
- **Cifras (caso «varios en curso», evaluador):** inicio «1 abierto · 9 acciones para hacer» y la fila «9 acciones»; portada «2 hechos, 4 en curso, 1 sin empezar» = estados de los siete pasos del mapa y de la lista (Hecho, Hecho, En curso ×4, Todavía no); «Qué se puede hacer ahora» 9 líneas (6 y «ver las 3 restantes»); mapa 6 tareas visibles (paso 3: 1, paso 4: 2, paso 6: 3) + «+ 2 más» (paso 6) + el renglón «2 advertencias» del paso 1, que remite a la línea «Tomar del Portal lo que falta de los datos (2)»: 9; lista de pasos: «Lo que falta» de los pasos 3, 4 y 6 (1 + 2 + 5) y las advertencias del paso 1; «2 advertencias» en los pasos 1 y 3 en mapa y lista; «Revisar 1 «no cumple»» = filtro «No cumple 1» = «No cumple 1» al pie; «Cargar el informe técnico del área (falta en 2 ofertas)» = «Esperan informe técnico 3» filas = «Espera informe 3» por oferta al pie; «Decidir 6 puntos no determinados» = 2 + 4 «A decidir» al pie y 4 filas en el filtro. En cuatro procedimientos con «Vencido hace 3 días», «Vence hoy», 20/11 y 27/11: «10 acciones» en el título = 3 + 3 + 2 + 2.
- **Una diferencia que no es error pero confunde (C-2):** el filtro cuenta **filas** («A decidir 4») y la acción cuenta **celdas** («Decidir 6 puntos»); al pie del cuadro dice «A decidir 2» y «A decidir 4» (por oferta). Ningún texto lo explica.
- **«Con algo pendiente 3» en el caso todo hecho:** las tres filas técnicas figuran «Cumple sin confirmar» con el informe técnico cargado y el dictamen cargado, y el filtro «Con algo pendiente» las cuenta mientras la portada dice «No hay nada para hacer ahora» (aviso para la lista de revisión: por diseño «sin confirmar» es propuesta del sistema, pero el inicio y el cuadro dicen cosas distintas del mismo procedimiento).

## 6. Bloque C en detalle (cuadro)

- **Filtros** (caso en curso; regla propia escrita desde la spec, no desde el código): `A decidir` deja las filas 1, 2, 3 y 4 (las que tienen una celda «A decidir»), contador 4; `No cumple` la fila 9, contador 1; `Esperan informe técnico` las filas 6, 7 y 8, contador 3; `Con algo pendiente` las 9 filas (cualquier «A decidir», «Espera informe», «Sin resultado» o «sin confirmar»), contador 9; `Todos` 9. Coinciden fila por fila con mi regla y con los contadores. En el caso todo hecho: `Con algo pendiente` 3 filas, los demás 0 y el cuadro dice «Ninguna fila cumple este filtro» con el enlace «Ver todos los requisitos».
- **Grupo resumido:** en el caso todo hecho 2 de los 3 grupos salen en una línea con `<details>` («· todas las ofertas cumplen todo») y el grupo con celdas «sin confirmar» (técnicas) no; el caso en curso no resume ninguno.
- **«Siguiente a decidir ›»:** con `a-decidir` recorre las 6 celdas a decidir en el orden del cuadro (grupo y fila, no número de requisito: la fila 9 está en el grupo de Económicos y se visita antes de la 4); con `pendiente`, `no-cumple` y `espera-informe` recorre exactamente las celdas del filtro en el orden del cuadro (18, 2 y 6). **En la última:** dice «No hay otro punto para decidir.» y no ofrece enlace. Con `a-decidir`, al acabar las celdas a decidir **sigue con las «sin decisión» posteriores** (8 más) antes de llegar a ese texto (diseño de la tarea). **C-1:** esa celda de reemplazo **no está en la tabla filtrada** (`?celda=3-14&filtro=a-decidir`: el panel abre «Oferta 1 × requisito 5» y la tabla, con 8 celdas, no la muestra ni la marca): el botón dice «Siguiente a decidir» y lleva a algo que el filtro vigente oculta. Repro: `/expedientes/<id>/cuadro/?filtro=a-decidir&celda=<última celda A decidir>`; el cálculo está en `views/cuadro.py:186-200` (`_siguiente`).
- **Columna del requisito fija y pista:** con 10 ofertas la tabla mide 1584 px dentro de una caja de 924 px (1000 px de ventana) y de 1175 px (1280 y 1440 px), `th.cu-req` es `position: sticky` y con la caja desplazada 500 px sigue en el borde izquierdo de la caja; la pista aparece con más de 3 ofertas y no con 3; la caja es una región con `tabindex="0"`. La página no se desplaza de costado en ningún ancho (ver bloque F).
- **Decidir desde el panel con un filtro activo:** `corregir` a «Cumple» con nota «prueba lote2» en la celda 1 de la oferta 1 (panel con `desde=cuadro&filtro=a-decidir`) y en la misma fila de la oferta 2 (página del par con `desde=par`): ambas dejan una `Decision` con la misma acción, el mismo usuario, la misma nota, `outcome_after = cumple`, el mismo evento de auditoría (`eval_decision`, resultado `ok`, canal `screen`) con el mismo detalle (`outcome_before = no_determinado`), y solo difiere la dirección a la que vuelve (cuadro con la celda y el aviso, o la página del par). Sin rol de evaluador la decisión da 403 y no deja nada (test del lote, en verde). P3 y P6 se cumplen.
- **Panel de «No aplica»:** dice «Falta su decisión: confirmar, corregir o rechazar la propuesta» (aviso heredado de T-352 que T-355 no podía arreglar sin tocar `_par.html`).

## 7. Bloque D en detalle (inicio)

- **Orden y vencimientos** (5 procedimientos: sin fecha, +9 días, +2 días, hoy, hace 3 días): `[hace 3 días, hoy, +2, +9, sin fecha]`; «Vencido hace 3 días» en rojo con relleno, «Vence hoy» en lila, «20/11/2026 · faltan 2 días» y «27/11/2026 · faltan 9 días» sin color, «Sin fecha de vencimiento». El lila aparece solo en el procedimiento que vence hoy (0 apariciones en los demás); las acciones «Cargar el dictamen» salen con «Vence hoy» y «Vencido» en texto; la portada de «Vence hoy» dice «Próximo vencimiento: Vence hoy · paso 7, Dictamen» y la acción está primera.
- **Todas las acciones agrupadas, colapsar y expandir:** con 5 abiertos el título dice «12 acciones» = 3 + 3 + 2 + 2 + 2 listadas; cada `<details>` arranca abierto; plegado en Chrome el alto baja de 410 a 198 px, la lista deja de verse, la línea (nombre, «3 acciones», vencimiento y barra de pasos) queda y el `summary` se enfoca; al reabrir vuelve. Sin JavaScript.
- **Terminados:** al cargar un dictamen el procedimiento sale de la lista de abiertos y `Terminados (1)` lo lleva a `?ver=terminados`; al retirar el documento (`document_history.withdraw`) vuelve a la lista y a su lugar por vencimiento.
- **Sin cookie del último procedimiento:** la única cookie de la respuesta de `/` es `csrftoken`. Sin rol de la Comisión `/` redirige a `/consulta/`; operador y evaluador ven el inicio.
- **Tiempo** (mediana de 5 cargas, `client.get('/')`, mi base propia): 20 abiertos del caso chico: **1,71 s** (tiempos 1,71, 1,62, 1,72, 1,75, 1,55; 1448 consultas); 21 abiertos «varios en curso» (20 copias con dos ofertas, resultados y total del acta, más el procedimiento del fixture): **2,51 s** en la primera medición (tiempos 2,51, 2,57, 2,40, 2,55, 2,38) y **2,29 s** en la segunda (2,26, 2,52, 2,67, 2,29, 2,29; 2380 consultas, 113 por procedimiento). El tope es 3 s y quedan 0,3 a 0,7 s; con procedimientos reales mayores el margen es chico (D-1).

## 8. Bloque E en detalle (vocabulario y cierre)

- **Nombres de los pasos:** los siete están en el texto del inicio, de la portada, del mapa (tarjetas), de la lista de pasos, de `?vista=lista` y del cuadro (hilo «Paso N · nombre»), con las mismas palabras y el mismo orden. `test_vocabulario` dice cubrir el cuadro en su docstring pero solo verifica inicio y portada (E-1).
- **Vocabulario en las pantallas:** en inicio, terminados, portada (mapa y lista), pestañas Procedimiento, Pliego, Ofertas, Evaluación y Normativas, cuadro, «Nuevo procedimiento» y la impresión de la matriz no aparece «Expedientes» como nombre de la lista ni «Cumplimiento por tipo y oferta» ni «Propuesta por oferta y requisito» (los únicos «Expediente» son el dato del Portal en Indicadores). **H-1:** «matriz de cumplimiento» en minúscula sigue nombrando la lista de requisitos en: `evaluon/templates/journey/temas/s2_matriz.html:50` («Todavía no hay una matriz de cumplimiento», se ve en la pestaña Pliego de un procedimiento sin matriz: reproducido con el caso recién cargado, `/expedientes/<id>/pliego/`), `evaluon/templates/journey/temas/s2_documentos.html:90` («sin ellos no hay matriz de cumplimiento», sin pliego cargado) y `evaluon/journey/temas/s4_propuesta.py:509` (devuelve «Falta una matriz de cumplimiento validada.» como motivo de por qué no se puede pedir la evaluación). `PROHIBIDAS` del test solo busca la forma con mayúscula y las pantallas del caso con matriz no llegan a esos estados vacíos.
- **Tests existentes que los desarrolladores modificaron** (`git diff origin/main...HEAD -- tests/`, archivos que ya existían: 12). Ninguno debilitó una comprobación que siguiera valiendo, con dos matices:
  - `test_cuadro_panel.py` (`test_los_enlaces_de_las_celdas_no_arrastran…`): `filtro=no-cumple` pasó a `filtro=pendiente` porque ahora el filtro quita filas. Sigue comprobando que el filtro viaja en los 18 enlaces, pero con un filtro que en ese caso no quita ninguna celda con resultado (no prueba que el enlace conserve un filtro restrictivo).
  - `test_sections.py` (`test_the_index_lists_procedures_with_their_counts`): `"pend." in html` pasó a `"acci" in html`, una subcadena que aparece en cualquier texto con «acción», «acciones» o «Acciones de …»; ya no prueba que el listado traiga **su cuenta**. Conviene volver a una aserción con el número («N acciones») (E-3).
  - Los otros diez son cambios de nombre o de destino decididos por las tareas: `test_portada.py` (`>Indicadores</h2>` a `>Indicadores</p>`: la pantalla ya no tiene un encabezado «Indicadores»; el `<h1>` del procedimiento va primero), `test_s2_matriz_actions.py` (`Matriz de requisitos:` en vez de `Matriz de cumplimiento:`), `test_s2_tiles.py` (el mosaico enlaza al cuadro, tres aserciones), `test_s4_propuesta.py` (título renombrado), `test_procedimientos_estetica.py` (`inicio.html` y `lista-abiertos` en vez de `expedientes.html` y la tabla), `test_redirects.py` (sin cookie; la entrada muestra la lista; también cubre «no hay cookie del último visto», lo que la versión vieja afirmaba al revés), `test_mapa.py`, `test_mapa_geometria.py` y `test_mapa_vista.py` (reescritos para la geometría nueva; mantienen sin colores fijos, sin letra bajo 12 px, los 196 pares de escalones, las ocho conexiones y la hoja contra `mapa.py`), y `test_pasos_4_a_7.py` (solo agrega dos tests).
- **T-359:** `docs/glosario.md` no cambió (E-2). `docs/diseno/guia-visual.md` suma §3.3 (inicio) y §3.4 (cuadro, filtros y el aviso del lila de `--ev-externo*`) y actualiza §3.2 (tarjetas de 252 px, alto variable).

## 9. Bloque F en detalle (higiene)

- **`style=`, `<script>` y direcciones externas:** `git diff -U0 origin/main...HEAD -- evaluon` no agrega ninguno (la única coincidencia es un comentario que dice «ni `style=`»). Las 28 páginas medidas (inicio, portada claro y negro, cuadro, panel, terminados) no tienen atributos `style`, ni enlaces a otro origen, y no tienen `id` repetidos (0 en 28).
- **Letra:** 0 textos bajo 12 px en inicio y terminados; 1 en portada y cuadro: el contador de la pestaña «Evaluación y dictamen» (11 px, anterior a la 018; en la portada solo con el caso A, en el cuadro siempre).
- **Contraste:** 0 pares de texto bajo 4,5:1 y 0 de no texto bajo 3:1 en las 28 páginas y los dos temas (mínimos 5,02:1 en claro y 5,09:1 en negro; «Vence hoy» lila y «Vencido» rojo incluidos).
- **Desplazamiento lateral de la página:** 112 mediciones (inicio de 4, de 1 y de varios procedimientos, terminados, portada A, «Vence hoy», «Vencido», recién cargado, todo hecho, cuadro con 3 y con 10 ofertas, cuadro con filtro y con panel; 800, 1000, 1280 y 1440 px; claro y negro): `scrollWidth` = `clientWidth` en todas.
- **Migraciones y datos nuevos:** ninguno (`git diff --name-only` no trae archivos de migraciones; `makemigrations --check --dry-run` sin cambios).
- **Otros:** el cuadro no tiene `<h1>` (como las demás pestañas); Indicadores ya no tiene encabezado propio (`<p class="encab-titulo">`).

## 10. Hallazgos

### Bloqueantes

Ninguno.

### A corregir antes de integrar

- **H-1 (T-358, REQ-155): «matriz de cumplimiento» sigue nombrando la lista de requisitos** en tres textos de pantalla: `evaluon/templates/journey/temas/s2_matriz.html:50`, `evaluon/templates/journey/temas/s2_documentos.html:90` y `evaluon/journey/temas/s4_propuesta.py:509`. Repro: caso recién cargado, pestaña Pliego (`/expedientes/<id>/pliego/`): «Todavía no hay una matriz de cumplimiento». El test `tests/journey/test_vocabulario.py` busca solo «Matriz de cumplimiento» con mayúscula y no renderiza los estados vacíos. Cambiar los tres textos a «matriz de requisitos» y ampliar el test (sin distinguir mayúsculas, con un procedimiento sin matriz y otro sin pliego).

### Avisos para la medición final (T-360) o para el Coordinador

- **A-1 (T-363) la red de seguridad no avisa cuando la estimación queda corta:** con otra tipografía o con tamaño mínimo de letra de 16 px, tarjetas con tres tareas de dos líneas esconden la tercera sin «+ N más» ni «Ver todo» (42 tarjetas en 6 páginas de las que probé). Sin cambios con la tipografía del sitio. `views/portada.py:_geometria_de` y `_mapa.html:38`.
- **A-2 (T-363) «+ N más» no cuenta lo que la red oculta** (muestra 2, esconde 3). `_mapa.html:38`.
- **A-3 (T-363) salto de contenido con el teclado:** Tab sobre una tarea oculta desplaza 234 px la caja de tareas de esa tarjeta. Sin teclado no se ve. Solo ocurre cuando la red recorta.
- **A-4 (T-363) holgura de la estimación con Verdana y Courier:** el real supera al estimado hasta 9 px en el caso A con Courier New y en textos de dígitos con Verdana; la red evita el solape.
- **C-1 (T-355) «Siguiente a decidir ›» sale del filtro:** con `a-decidir`, después de la última celda a decidir lleva a una celda «sin decisión» que la tabla filtrada no muestra (`views/cuadro.py:186-200`). Está en lo pedido por la tarea («o, si no hay, la próxima sin decisión»), pero la pantalla queda incoherente con el filtro activo.
- **C-2 (T-355/T-353)** el filtro cuenta filas y la acción «Decidir N puntos» cuenta celdas (4 contra 6 en el caso en curso). Ningún texto lo explica.
- **C-3** el filtro «Con algo pendiente» cuenta 3 filas «Cumple sin confirmar» en el procedimiento todo hecho, mientras el inicio y la portada dicen que no hay nada para hacer.
- **D-1 (T-357) margen del tope de 3 s:** 1,71 s con 20 abiertos chicos y 2,29 a 2,51 s con 21 «varios en curso» de este caso inventado (113 consultas por procedimiento); un procedimiento real del piloto cuesta más. La salida prevista del ADR-0079 sigue disponible.
- **D-2 (T-357)** el encabezado de «Procedimientos» muestra «Elegir procedimiento» como ubicación; las seis tarjetas de la barra de pasos del inicio dejan 2 a 4 px entre «5 Comparación de ofertas» y «6 Evaluación Comisión» a 1440 px (cuesta leerlas).
- **E-1** `test_vocabulario.py` dice cubrir el cuadro y solo verifica inicio y portada.
- **E-2 (T-359)** `docs/glosario.md` no se actualizó: es el glosario de códigos generado y no tiene los términos que pide la tarea (siete pasos, «Mapa del proceso», «Cuadro de cumplimiento», «Indicadores», advertencia, tarea, acción de cierre, faltante). Hay que decidir dónde viven esas definiciones.
- **E-3** `test_sections.py`: `"acci" in html` es una aserción muy débil donde antes se verificaba la cuenta.
- **G-1** `test_req150_veinte_abiertos_en_dos_segundos` falló bajo `-n 2` con la máquina ocupada (5,39 s contra 3 s) y pasa solo (1,45 y 1,88 s). Riesgo de falso rojo en la suite del Coordinador.

### Lista de revisión (anteriores a la feature o decisiones)

- Los 39 enlaces del rol sin Comisión que dan 403 (listados en el bloque B), todos anteriores a la 018; incluye «+ Nuevo procedimiento» en el inicio, que ya estaba en `expedientes.html` de `main`.
- «No aplica» en el panel dice «Falta su decisión» (`_par.html`).
- El contador «19» de la pestaña (11 px).
- Filas de arriba del mapa con alturas distintas y espacio entre filas (H-B2 anterior), leyenda «Advertencia» con otra forma que en la tarjeta (H-B3).
- Indicadores sin encabezado semántico (p en lugar de h2) y el cuadro sin `<h1>`.

## 11. Alteraciones del código

No hubo rondas de alteraciones (carril liviano, ADR-0081). La única comprobación sobre el código fue la lectura de los tests existentes modificados (bloque E).

## 12. Capturas propias

Carpeta `C:\Users\snave\AppData\Local\Temp\claude\8f995ee6d7d0454a\5f27ff43-b8a6-44f4-965a-c1fcce5a9f5f\scratchpad\lote2\verificacion\capturas\`, claro y negro (`__claro` y `__negro`): `INICIO__cuatro`, `INICIO__varios`, `INICIO__terminados`; `A_varios__portada`, `A_hoy__portada`, `A_vencido__portada`, `C_lleno5__portada` (siete tarjetas llenas con «Vence hoy») y `A_varios__lista`; `CUADRO__tres`, `CUADRO__diez`, `CUADRO__filtro` y `CUADRO__panel`. Zooms y casos de corte: `zoom1x_A_varios.png`, `zoomcrop_A_varios__portada__claro.png`, `corte_min16_A_varios.png`, `corte_min16_err150_tres.png`, `corte_min16_mayus_sintexto.png`. Las miré una por una: lo desparejo está en el bloque A.

## 13. No verificado

- Edge, táctil, impresión del PDF de la matriz con navegador (solo se comprobó el texto de la página de impresión) y las flechas del teclado dentro de la caja del mapa (solo se verificó que es una región enfocable y que Tab sobre una tarea oculta mueve su caja).
- Tamaño mínimo de letra de 14 y 16 px del navegador: emulado con `font-size` forzado dentro de las tarjetas (no con el ajuste real de Chrome).
- Procedimientos reales del piloto (tiempos y cifras con datos reales: es T-360).
- Las 2 pruebas omitidas de la parte 2 de G (se corre sin `-rs`).
- El recorrido por enlaces se detuvo en 140 páginas por escenario.
