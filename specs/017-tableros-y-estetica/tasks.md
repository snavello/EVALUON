# Tareas 017 · Tableros de primer nivel y estética nueva

Plan: `specs/017-tableros-y-estetica/plan.md` (aprobado el 2026-10-21 por el responsable)

Despliegue: pendiente

> El tablero (`docs/tablero.md`) se genera de este archivo. Al aprobarse el despliegue, la línea de arriba pasa a `Despliegue: aprobado AAAA-MM-DD`.

Estados: pendiente · en curso · en verificación · terminada · bloqueada

Dos tareas que no dependen entre sí y no comparten archivos se pueden hacer en paralelo.

**Ritmo de trabajo (ADR-0024 y ADR-0025).** Las ramas de tarea no tocan este archivo ni el tablero: el Coordinador los actualiza una vez por lote. La verificación de cada tarea queda en `specs/017-tableros-y-estetica/verificacion/T-NNN.md`. Cada tarea declara su nivel: **plena** (lógica, datos, esquema, instrucciones o principios de la constitución) o **liviana** (cambio acotado con un test que falla antes y pasa después). Toda medición escribe antes su umbral y tiene dos rondas como máximo; los hallazgos se corrigen en una sola tarea y se mide una vez por lote; lo que no llegue pasa, con su impacto, a la lista de revisión. Con tareas en paralelo, cada desarrollador corre solo los tests de su área; la suite completa la corre el Coordinador una vez por oleada, sobre la rama combinada con `main` (ADR-0012). Commits de código: `T-NNN (REQ-NNN): qué cambia`.

**IDs.** T-308 a T-334. En `main` el último ID usado es T-307 (feature 016). El Coordinador confirma contra las ramas abiertas antes de lanzar.

**Oleadas de paralelismo.** Dentro de una oleada las tareas no dependen entre sí ni comparten archivos. Una oleada empieza cuando terminaron (verificadas e integradas) las tareas de las que depende. Máximo sugerido en paralelo: tres desarrolladores (el Coordinador tiene que poder revisar cada resultado contra la spec); las oleadas 2 y 8 admiten más, se lanzan en tandas.

| Oleada | Tareas | Qué habilita |
|---|---|---|
| 1 | T-308 (esquema y perfil), T-309 (tokens y contraste), T-310 (tipografía y marca) | Base: B0.1 y B0.2 |
| 2 | T-311 (tema, encabezado y pase), T-314 (gráficos y orden económico), T-319 (normalización de fotos) | T-311 espera a la oleada 1; T-314 solo a T-309; T-319 solo a T-308 |
| 3 | T-312 (Hay/Falta, portada y avance mínimo), T-320 (Mis fotos) | Cierra B0.3 y B1 |
| 4 | T-313 (componente de tablero) | B0.4 |
| 5 | T-315 (tablero de Ofertas) | Corte vertical probable de punta a punta |
| 6 | T-316 (medición del corte vertical, sin código) | Umbrales escritos antes |
| 7 | T-317 (correcciones de la medición; se cierra sin cambios si no hay hallazgos) | Habilita los demás tableros |
| 8 | T-318 (pendientes), T-324 (listado y alta), T-325 (Pliego), T-326 (Ofertas, resto), T-329 (Normativas), T-330 (avance) | Archivos disjuntos |
| 9 | T-321 (primer panel), T-323 (mosaicos de Procedimiento), T-327 y T-328 (Evaluación) | Esperan a T-318 (`s1_portal.py`, `s4_dictamen.py`, `Item`) |
| 10 | T-322 (primer panel: orden económico y plazos) | Comparte `ingreso.py` con T-321 |
| 11 | T-331 (cierre técnico) y T-332 (runbook) | B8 |
| 12 | T-333 (medición final y revisión visual, sin código) | Una sola vez |
| 13 | T-334 (correcciones de la medición final; condicional) | Cierre |

**Archivos de uso compartido y quién los toca** (nunca dos tareas a la vez): esquema y migraciones, solo T-308; `tokens.css`, T-309 y T-331; `base.html`, `secciones.css`, T-311; `accounts/urls.py`, T-311 y después T-320; `journey/urls.py`, T-312; `sections/base.py`, T-313 y después T-318; `journey/views/portada.py`, T-311, T-312 y T-313 en ese orden; `ingreso.py`, T-321 y después T-322; `test_contraste.py`, T-309, T-321 y T-331.

## Definiciones compartidas (escritas antes de lanzar)

Lo que varias tareas necesitan igual. Si una tarea necesita cambiarlas, lo informa; no lo decide sola.

1. **Ids de los detalles.** `d-` más la clave del tema con el guion bajo cambiado por guion. Claves de los temas: sección 1 `s1_datos`, `s1_pliego`, `s1_portal`; sección 2 `s2_documentos`, `s2_matriz`; sección 3 `s3_ofertas`, `s3_anexos`, `s3_circulares`, `s3_ficha`; sección 4 `s4_propuesta`, `s4_descartes`, `s4_preguntas`, `s4_dictamen`, `s4_informe`, `s4_exportar`; sección 5 `s5_rigen`, `s5_consulta`, `s5_normas`. Ejemplos: `d-s3-ofertas`, `d-s4-dictamen`. Los enlaces de otra sección usan `evaluacion/#d-s4-propuesta` y las rutas del plan.
2. **Contrato `Tile`** (`journey/tablero/tiles.py`, lo escribe T-313): campos `key`, `title`, `detail`, `width` (1, 2 o 4), `tone` (`""` o `dark`), `big`, `unit`, `sub`, `chart` y `missing`, tal como los define el plan, «Tablero: mosaicos y detalle». Regla de REQ-141: si `big` es `None` se dibuja `missing` («Falta …» o «Pendiente») y no se dibuja ni la cifra ni el gráfico. Cada tema suma `tiles(user, procedure, ctx) -> list[Tile]` y, si un parámetro de la consulta abre un modo (`?oferta=`, `?ficha=`, `?historial=`), `opens(request) -> str | None` con el id del detalle. `Section.tiles(...)` junta los de sus temas y `Section.ingreso_template` (por omisión `None`) y `Section.ingreso_context(...)` dejan un gancho para el primer panel.
3. **Protocolo de gráficos.** Cada gráfico de `charts.py` es una dataclass con el atributo de clase `template` (por ejemplo `journey/graficos/_bars.html`); el mosaico lo dibuja con `{% include chart.template %}` y la variable `chart`. Los siete tipos: `Bars`, `Donuts`, `Lollipop`, `Timeline`, `Stack`, `Columns`, `Heat`. Todo SVG usa atributos de presentación y `fill`/`stroke="currentColor"`; el color sale de una clase `g-ok`, `g-no`, `g-nd`, `g-pe`, `g-ext`, `g-lime`, `g-ink`, `g-mute`, que en `tablero.css` solo declara `color: var(--…)` (la escribe T-313). Nunca `style=`.
4. **Tipografía.** Familia `"Hanken Grotesk"`; archivos `evaluon/static/diseno/fuentes/hanken-grotesk-latin.woff2` y `hanken-grotesk-latin-ext.woff2`. Los nombres de los tokens son los de `docs/diseno/mockup-017/comun/estilos.css`.
5. **Hojas enlazadas por `base.html`** (lo escribe T-311): `evaluon.css`, `tokens.css`, `secciones.css`, `tablero.css`, `pase.css`, `avance.css`. Como esas hojas no existen todas cuando T-311 se integra, T-311 crea `tablero.css` y `avance.css` con un solo comentario; las llenan T-313 y T-330. Las demás (`ingreso.css`, `s1.css`, etc.) las enlaza cada plantilla con `{% block head %}`.
6. **Fotos.** `photos.pick_for(request)` devuelve un objeto con `photo_id` (`None` si es la foto de la casa), `label` («Foto de la casa» o «Foto de su perfil») y `url` (propiedad calculada al dibujar: la estática de la casa, o `reverse("accounts:foto", args=[photo_id])`). T-308 deja la versión que solo devuelve la casa; T-319 la completa sin cambiar la forma.
7. **Pendientes.** `Item` suma `why`, `open` y `post` (T-318). Los temas que escriben `why` lo hacen en sus propias tareas (T-323, T-327, T-328, T-325, T-326, T-329) sin tocar `sections/base.py`.
8. **Los bloques no renombran ni quitan** `status()`, `context()`, `PARTIAL` ni las funciones públicas de los temas existentes: otras tareas las leen en paralelo (el primer panel lee `memo.matrix_page`, `s4_descartes.service.units`, `open_questions`).
9. **Tests que recorren todo.** `test_tablero_secciones.py` y `test_sin_inventos.py` (T-313) recorren los temas que declaran `tiles()`; cada bloque nuevo queda cubierto sin editarlos. Cada bloque agrega su propio archivo de test con el caso chico y la medida de 2 s.
10. **Fixtures.** Solo las existentes (`tests/conftest.py`, `tests/journey/conftest.py`). Si una tarea necesita una nueva, la agrega en su propio archivo de tests.

## Umbrales de las mediciones (escritos antes de medir)

Los del plan, «Criterio de aceptación numérico y umbrales». Se repiten acá porque T-316, T-317, T-333 y T-334 se miden contra esta lista.

| Qué | Umbral | Con qué se mide |
|---|---|---|
| Contraste AA en los dos temas | 100 % de los pares declarados (texto 4,5:1; íconos y gráficos 3:1; texto sobre la foto en el peor píxel) | `tests/journey/test_contraste.py` |
| Tablero de Ofertas (corte vertical) | 2 s o menos hasta verse completo con el caso chico | Test con el caso chico y medición en Edge |
| Detalle que se despliega | 0,4 s o menos | Duración en `tablero.css` y revisión en Edge |
| Pase de hoja | 0,5 s o menos; con «reducir movimiento», 0,15 s o menos | Duración en `pase.css` y revisión en Edge |
| Revisión visual del Coordinador | Dos temas, sin hallazgos que impidan usar la pantalla | Edge, 1440 × 900 |
| Tablero de cada sección (cierre) | 2 s o menos, mediana de 5 cargas por sección con un procedimiento real del piloto | Medición local del Coordinador, una sola vez; al repositorio solo cifras |
| Funciones de la 014 | REQ-075 a REQ-099 en verde | Suite completa sobre la rama combinada con `main` |

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-308 | Esquema y perfil: `User.theme`, tabla `Photo` con sus restricciones, migración reversible, `photos.py` con `pick_for` (por ahora solo la foto de la casa), foto de la casa con sus créditos y `.gitignore` | REQ-134, REQ-136, REQ-138 | — | terminada |
| T-309 | Tokens de los dos temas con alias de los viejos, estilos de `evaluon.css`, `recorrido.css` y `punto.css` en los dos temas, guía visual, test de contraste y test de direcciones externas | REQ-133 | — | terminada |
| T-310 | Tipografía Hanken Grotesk alojada con su licencia y los cuatro SVG de la marca 017 en `static/marca/` | REQ-133, REQ-142 | — | terminada |
| T-311 | Tema en `base.html`, encabezado único (logotipo por tema, camino, pestañas en píldora con contador, selector, menú de usuario), vista del tema, pase de hoja, ingreso con el logotipo nuevo y retiro de los SVG viejos | REQ-132, REQ-133, REQ-134, REQ-139, REQ-142 | T-308, T-309, T-310 | en curso |
| T-312 | Línea «Hay · Falta», portada que redirige al primer panel y vista mínima del indicador de avance | REQ-128, REQ-132, REQ-140 | T-311 | pendiente |
| T-313 | Componente de tablero: contrato `Tile`, mosaico, cuadrícula, detalle desplegable (`tablero.js` y `tablero.css`) y cuerpo común de las secciones | REQ-126, REQ-127, REQ-141 | T-312 | pendiente |
| T-314 | Siete gráficos SVG y orden económico (`charts.py`, `economico.py`, plantillas de gráficos) | REQ-126, REQ-130, REQ-141 | T-309 | en verificación |
| T-315 | Tablero de Ofertas con el detalle «Ofertas del acta» y el orden económico (corte vertical) | REQ-126, REQ-127, REQ-130, REQ-141 | T-313, T-314 | pendiente |
| T-316 | Medición del corte vertical: contraste, 2 s, 0,4 s y revisión visual en Edge, sin código | REQ-126, REQ-127, REQ-133, REQ-139 | T-315 | pendiente |
| T-317 | Correcciones de la medición del corte vertical, en una sola tarea y con re-medición de lo que cambió (se cierra sin cambios si no hay hallazgos) | REQ-126, REQ-127, REQ-133 | T-316 | pendiente |
| T-318 | Pendientes con acción a mano: `Item.why/open/post`, `_pendientes.html` y dictamen del Portal en Evaluación | REQ-129, REQ-141 | T-317 | pendiente |
| T-319 | Fotos: normalización por histograma, subida con sus límites y elección al azar sin repetir | REQ-136, REQ-137, REQ-138 | T-308 | en verificación |
| T-320 | Mis fotos: página del perfil, quitar, servido privado y enlace en el menú de usuario | REQ-136 | T-311, T-319 | pendiente |
| T-321 | Primer panel: foto de fondo, datos principales, pendiente general, avance y mosaicos que enlazan a Evaluación | REQ-128, REQ-129, REQ-132, REQ-135, REQ-138 | T-317, T-318, T-320 | pendiente |
| T-322 | Primer panel: orden económico, plazos importantes y vencimiento del mantenimiento | REQ-128, REQ-130, REQ-131, REQ-141 | T-321 | pendiente |
| T-323 | Mosaicos de la sección Procedimiento: Datos, Portal de Compras y Alta desde el pliego | REQ-126, REQ-129, REQ-141 | T-317, T-318 | pendiente |
| T-324 | Listado de procedimientos, alta y borrador del pliego con la estética nueva | REQ-132, REQ-133 | T-317 | pendiente |
| T-325 | Tablero de Pliego y matriz | REQ-126, REQ-129, REQ-141 | T-317 | pendiente |
| T-326 | Resto del tablero de Ofertas: hojas de compliance, documentación, circulares y fichas | REQ-126, REQ-129, REQ-141 | T-317 | pendiente |
| T-327 | Tablero de Evaluación, parte 1: resultado por oferta, no cumple, no determinado y cumplimiento por tipo | REQ-126, REQ-141 | T-317, T-318 | pendiente |
| T-328 | Tablero de Evaluación, parte 2: informe técnico, dictamen, descartes, preguntas y exportar | REQ-126, REQ-129, REQ-141 | T-317, T-318 | pendiente |
| T-329 | Tablero de Normativas y página general de normativas | REQ-126, REQ-129, REQ-141 | T-317 | pendiente |
| T-330 | Avance de procesos largos: porcentaje global, panel de avance e indicador del encabezado con la estética nueva | REQ-140 | T-317 | pendiente |
| T-331 | Cierre técnico: quitar alias y colores sueltos, retirar Barlow y la marca vieja, guía visual final y test final de tokens y de anclas | REQ-133, REQ-142 | T-320, T-322, T-323, T-324, T-325, T-326, T-327, T-328, T-329, T-330 | pendiente |
| T-332 | Runbook de despliegue `entorno.md`: reconstrucción de la imagen y migración con respaldo | REQ-134, REQ-136 | T-320, T-322, T-323, T-324, T-325, T-326, T-327, T-328, T-329, T-330 | pendiente |
| T-333 | Medición final: 2 s con el procedimiento real del piloto y revisión visual de las cinco secciones en los dos temas, sin código | REQ-126, REQ-133, REQ-139 | T-331, T-332 | pendiente |
| T-334 | Correcciones de la medición final, en una sola tarea (se cierra sin cambios si no hay hallazgos) | REQ-126, REQ-133 | T-333 | pendiente |

## Detalle

### T-308 · Esquema y perfil

- **Requisitos:** REQ-134, REQ-136, REQ-138
- **Nivel de verificación:** plena (esquema, datos personales, principio P4).
- **Qué hay que hacer:**
  1. `User.theme` en `evaluon/accounts/models.py`: texto, valores `claro` y `negro`, por omisión `claro`, con restricción de valores (ADR-0074).
  2. Modelo `Photo` (ADR-0073), tabla `accounts_photo`: `user` (CASCADE), `slot` (0 a 9), `content` (bytea), `sha256`, `width`, `height`, `size`, `created_at`; restricciones `slot` entre 0 y 9, única `(user, slot)` y `size <= 2097152`.
  3. Migración reversible `evaluon/accounts/migrations/0003_tema_y_fotos.py`. Es la única migración de la feature. Los usuarios existentes quedan en `claro` y sin fotos.
  4. `evaluon/accounts/photos.py` con `pick_for(request)` según la definición compartida 6: por ahora devuelve siempre la foto de la casa. Calcula el histograma de referencia una sola vez desde la foto de la casa (función `reference_histogram()`, con caché en memoria) para que T-319 lo use.
  5. Foto de la casa: copiar `docs/diseno/mockup-017/img/biblioratos-bn.jpg` y `CREDITOS.txt` a `evaluon/static/diseno/casa/`.
  6. `.gitignore`: agregar `*.dump` (ya cubre `backups/` y `pgdata/`).
  7. `tests/test_sin_fotos_en_el_repositorio.py`: falla si hay archivos de imagen fuera de `evaluon/static/diseno/casa/`, `evaluon/static/marca/` y `docs/` (la carpeta de diseño ya versionada); verifica que `.gitignore` cubra `backups/`, `pgdata/` y `*.dump`.
- **Archivos:** `evaluon/accounts/models.py`, `evaluon/accounts/migrations/0003_tema_y_fotos.py`, `evaluon/accounts/photos.py`, `evaluon/static/diseno/casa/*`, `.gitignore`, `tests/accounts/test_models_perfil.py`, `tests/test_sin_fotos_en_el_repositorio.py`.
- **Verificación:** `pytest tests/accounts/test_models_perfil.py tests/test_sin_fotos_en_el_repositorio.py` y los tests de `tests/accounts/`. Casos: tema por omisión `claro`; valor `otro` rechazado por la base; `slot` 10 y -1 rechazados; dos fotos del mismo usuario en la misma ranura rechazadas; `size` mayor a 2 MiB rechazado; borrar el usuario borra sus fotos; `migrate` hacia delante y hacia atrás sobre una base con usuarios; `pick_for` devuelve la casa con `label` «Foto de la casa»; el histograma de referencia se calcula una vez. Criterios: máximo 10 fotos y 2 MiB (umbral «Fotos» del plan).
- **No tocar:** ninguna otra migración, vistas, URLs ni plantillas. Nada fuera de `accounts/` y los estáticos de la casa.

### T-309 · Tokens, estilos en los dos temas, guía visual y tests de contraste y de externos

- **Requisitos:** REQ-133
- **Nivel de verificación:** plena (criterio numérico de la feature, principios P4 y P5).
- **Qué hay que hacer:**
  1. Reescribir `evaluon/static/diseno/tokens.css` con los dos temas: `:root` gris y blanco y `[data-theme="negro"]`, con los nombres de la maqueta (`--bg`, `--tile`, `--ink`, `--ink-2`, `--ink-3`, `--lime`, `--ok`, `--no`, `--nd`, `--pe`, `--ext`, etc.) y los `--ev-*` viejos como alias de los nuevos hasta T-331. Incluir los `@font-face` de Hanken Grotesk apuntando a los dos archivos de la definición compartida 4 (los escribe T-310).
  2. Ajustar `--ink-3`, `--nd` y similares hasta que el test pase (el plan calcula `--ink-3` cerca de 3,3:1, `#6E7076` sobre `#0B0C0E` cerca de 4,0:1 y `--nd` cerca de 2,4:1): decisión de implementación dentro del criterio, sin cambiar la estética elegida. Los datos del primer panel se dibujan con `--ink`.
  3. Hacer que `evaluon/static/css/evaluon.css`, `evaluon/static/journey/recorrido.css` y `evaluon/static/journey/punto.css` se lean en los dos temas usando los tokens (sin quitar sus reglas todavía; el resto de `recorrido.css` lo cierra T-331).
  4. `tests/journey/test_contraste.py`: lista declarada de pares texto/fondo, ícono/fondo y gráfico/fondo por tema; calcula la razón desde `tokens.css`; falla si algún par no llega a 4,5:1 (texto) o 3:1 (íconos y gráficos). Deja un lugar para el par «texto sobre la foto» que agrega T-321.
  5. `tests/test_sin_externos.py`: falla si alguna plantilla, hoja de estilo, script o SVG nombra un dominio, `@import url(http…)` o `fonts.googleapis`.
  6. `docs/diseno/guia-visual.md`: guía nueva (temas, tipografía, estados de cumplimiento, regla del verde lima, gráficos). La versión final la cierra T-331.
- **Archivos:** `evaluon/static/diseno/tokens.css`, `evaluon/static/css/evaluon.css`, `evaluon/static/journey/recorrido.css`, `evaluon/static/journey/punto.css`, `docs/diseno/guia-visual.md`, `tests/journey/test_contraste.py`, `tests/test_sin_externos.py`.
- **Verificación:** `pytest tests/journey/test_contraste.py tests/test_sin_externos.py tests/journey/test_no_external.py`. Criterio: contraste AA al 100 % en los dos temas y 0 direcciones externas (criterio numérico de la spec). Pruebas de alteración: bajar `--ink-3` a un gris más claro hace fallar el test.
- **No tocar:** `base.html`, `secciones.css`, plantillas, `evaluon/static/diseno/fuentes/*` y `evaluon/static/marca/*` (T-310), cualquier hoja `sN*.css`.

### T-310 · Tipografía alojada y archivos de la marca 017

- **Requisitos:** REQ-133, REQ-142
- **Nivel de verificación:** liviana (archivos estáticos con un test que falla antes y pasa después). Origen y licencia de la fuente: revisión del Coordinador.
- **Qué hay que hacer:**
  1. Alojar Hanken Grotesk variable (pesos 300 a 600), subconjuntos `latin` y `latin-ext`, en woff2, con los nombres de la definición compartida 4. Se baja una vez de un paquete que la publique con licencia SIL OFL 1.1 (por ejemplo Fontsource); no se descarga en ejecución. Agregar `LICENCIA.txt` con el texto de la licencia, el origen (URL, versión y fecha de consulta) y la huella SHA-256 de cada archivo.
  2. Copiar los cuatro SVG de `docs/diseno/marca/017/` (`logotipo-claro`, `logotipo-negro`, `isotipo-claro`, `isotipo-negro`) a `evaluon/static/marca/` **sin quitar** los viejos (los retira T-311).
  3. `tests/test_archivos_estaticos_017.py`: los dos woff2 existen y no están vacíos; `LICENCIA.txt` nombra OFL 1.1 y las huellas coinciden; si `tokens.css` declara `@font-face`, cada `url()` apunta a un archivo local que existe (vale en cualquier orden de integración con T-309); los cuatro SVG existen, no contienen `<text>` ni direcciones externas.
- **Archivos:** `evaluon/static/diseno/fuentes/*`, `evaluon/static/marca/` (solo agrega los cuatro SVG nuevos), `tests/test_archivos_estaticos_017.py`.
- **Verificación:** `pytest tests/test_archivos_estaticos_017.py tests/test_sin_externos.py`. Si no hay red para bajar la fuente, la tarea queda bloqueada y se pide el archivo al Coordinador.
- **No tocar:** `tokens.css`, plantillas, los SVG viejos de `static/marca/`, `tests/journey/test_marca.py`.

### T-311 · Tema, encabezado único, selector, pase de hoja e ingreso

- **Requisitos:** REQ-132, REQ-133, REQ-134, REQ-139, REQ-142
- **Nivel de verificación:** plena (preferencia del usuario guardada, redirección con `next`, rol de lectura).
- **Qué hay que hacer:**
- **Aviso de tareas anteriores:** (oleada 1) Retirar los SVG viejos de static/marca; el encabezado nuevo no usa blanco fijo. El selector de tema valida el valor y guarda con update_fields=["theme"]. Toda imagen nueva va en casa/, marca/ o docs/ (test de T-308).
  1. `accounts:tema` (POST, `perfil/tema/`) en `evaluon/accounts/views_perfil.py` y `urls.py`: valida el valor (`claro` o `negro`), guarda en `User.theme`, exige CSRF y redirige a `next` validado con `url_has_allowed_host_and_scheme` (ADR-0074). Vale para el usuario de lectura.
  2. `base.html`: `<html data-theme="negro">` si corresponde; enlaza las hojas de la definición compartida 5 y crea `tablero.css` y `avance.css` con un comentario; `<link rel="icon">` al isotipo nuevo.
  3. Encabezado único en `_cabecera.html`, `_encabezado.html`, `_barra.html`, `_barra_nueva.html`: los dos `<img>` del logotipo (la hoja muestra el del tema), recorrido «Procedimientos › procedimiento (menú que hoy es `sel-proc`, con «+ Nuevo procedimiento» y «Normativas») › sección», pestañas en píldora con el contador de `Section.pending` (sin contador si es 0), `_selector_tema.html` (dos botones de un formulario) y `_menu_usuario.html` (Salir; el enlace a «Mis fotos» lo agrega T-320). El recorrido va aquí; la línea Hay/Falta es de T-312.
  4. `_icono.html` y `_sprite.html` leen los tokens de estado nuevos sin cambiar la forma ni el nombre al pasar el mouse.
  5. `secciones.css`: tipografía, encabezado, botones, formularios, tablas e íconos de estado con los tokens.
  6. `pase.css` y `pase.js` (ADR-0075): `@view-transition { navigation: auto; }`, `view-transition-name` `hoja` (el `<main>`), `cabecera` y `pildora`; rotación sobre el borde izquierdo en 0,44 s; con `prefers-reduced-motion: reduce`, fundido de 0,15 s; `pase.js` fija la dirección en `pagereveal` (unas 15 líneas).
  7. `login.html` con el logotipo claro; quitar los SVG viejos de `static/marca/` y actualizar `tests/journey/test_marca.py` a los nombres nuevos (archivos, sin `<text>`, versión por tema, contraste de las letras sobre su placa a 4,5:1).
  8. `without_actions` (en `journey/views/portada.py`) deja pasar los formularios con la clase `preferencia`; el selector la lleva.
  9. `context.py`: lo que el recorrido y las pestañas necesiten del procedimiento y de `sections_for`.
  10. Actualizar los tests de la 014 que miran el encabezado y las pestañas: `test_sections.py` y `test_angosto.py` (los otros dos de la lista del plan, `test_redirects.py` y `test_normativas_general.py`, los toca T-312).
- **Archivos:** `evaluon/templates/base.html`, `evaluon/templates/journey/_cabecera.html`, `_encabezado.html`, `_barra.html`, `_barra_nueva.html`, `_icono.html`, `_sprite.html`, `_selector_tema.html`, `_menu_usuario.html`, `evaluon/templates/accounts/login.html`, `evaluon/static/journey/secciones.css`, `evaluon/static/journey/pase.css`, `pase.js`, `tablero.css` y `avance.css` (solo el comentario), `evaluon/static/marca/` (quita los viejos), `evaluon/accounts/urls.py`, `evaluon/accounts/views_perfil.py`, `evaluon/journey/views/portada.py` (solo `without_actions`), `evaluon/journey/context.py`, `tests/journey/test_marca.py`, `tests/journey/test_tema.py`, `tests/journey/test_pase.py`, `tests/journey/test_sections.py`, `tests/journey/test_angosto.py`.
- **Verificación:** `pytest tests/journey/test_tema.py tests/journey/test_pase.py tests/journey/test_marca.py tests/journey/test_sections.py tests/journey/test_angosto.py tests/journey/test_roles.py tests/journey/test_no_external.py tests/test_sin_externos.py tests/journey/test_contraste.py`. Casos de REQ-134: elegir negro, entrar con otro cliente y ver `data-theme="negro"`; inicio en claro; valor inválido rechazado; `next` externo rechazado; el usuario de lectura puede cambiar el tema. REQ-139: `@view-transition`, duración ≤ 0,5 s, ≤ 0,15 s con reducir movimiento, `view-transition-name`. REQ-142: letras sobre la placa a 4,5:1, versión por tema. REQ-132: contador por pestaña, ninguno si no hay pendientes. Revisión en Edge queda para T-316.
- **No tocar:** el esquema, `tokens.css`, `journey/urls.py`, `sections/base.py`, `seccion*.html`, las plantillas de los temas.

### T-312 · Hay/Falta, portada que redirige y vista mínima del avance

- **Requisitos:** REQ-128, REQ-132, REQ-140
- **Nivel de verificación:** plena (rutas y redirecciones que usan los enlaces de la 014).
- **Qué hay que hacer:**
  1. `_hay_falta.html`: línea «Hay: … · Falta: …» con «Hay» desde `Section.summary` y «Falta» desde `Section.tema_missing`, con la acción directa de cada faltante. Queda como parcial que T-313 incluye en el cuerpo común.
  2. `expedientes/<id>/` redirige (302, con la consulta) a `expedientes/<id>/procedimiento/`, que pasa a ser el primer panel (por ahora sigue mostrando el cuerpo de la sección 1 de hoy). Las anclas y los redireccionamientos de la 014 a `procedimiento/` siguen andando. Si `portada.html` queda sin referencias, se retira.
  3. Ruta `expedientes/<id>/avance/` y `journey/views/avance.py` mínima: devuelve el fragmento `_avance_encabezado.html` (anillo SVG con el porcentaje de `window_for(...).main.percent`, enlazado a `procedimiento/`), solo si hay un pedido en espera o en curso; con `data-poll-url` para que `recorrido.js` lo sondee. Se incluye en `_encabezado.html`. La estética final y `overall_percent` son de T-330.
  4. Actualizar `test_redirects.py` y `test_normativas_general.py`.
- **Archivos:** `evaluon/templates/journey/_hay_falta.html`, `_avance_encabezado.html`, `_encabezado.html` (solo el `include` del indicador), `portada.html` (se retira si no se usa), `evaluon/journey/views/portada.py` (solo la redirección), `evaluon/journey/views/avance.py`, `evaluon/journey/urls.py`, `evaluon/journey/context.py` (si falta algún dato), `tests/journey/test_camino.py`, `tests/journey/test_avance_minimo.py`, `tests/journey/test_redirects.py`, `tests/journey/test_normativas_general.py`.
- **Verificación:** `pytest tests/journey/test_camino.py tests/journey/test_avance_minimo.py tests/journey/test_redirects.py tests/journey/test_normativas_general.py tests/journey/test_sections.py tests/journey/test_live_block.py`. REQ-132 (criterio): recorrido y línea «Hay … Falta …» en las cinco secciones y en la portada. Redirección 302 con la consulta. Sin pedido en curso, el indicador no se dibuja.
- **No tocar:** `base.html`, `secciones.css`, el esquema, `tokens.css`, `sections/base.py`, `seccion*.html`, `window.py`.

### T-313 · Componente de tablero

- **Requisitos:** REQ-126, REQ-127, REQ-141
- **Nivel de verificación:** plena (lógica de presentación que cumple REQ-141 y un criterio numérico).
- **Qué hay que hacer:** (ADR-0076; plan, «Tablero: mosaicos y detalle»)
- **Aviso de tareas anteriores:** (oleada 1) En el tema claro toda marca lima lleva contorno --ink (guía visual, sección 4); no aplicar opacidad al texto secundario (.todo li.done de la maqueta baja --ink-2 a 2,4:1); --ink-3 no va sobre --tile-h.
  1. `evaluon/journey/tablero/tiles.py`: `Tile` con los campos de la definición compartida 2; la regla de REQ-141 (si `big` es `None`, la plantilla dibuja `missing`; no hay valor por omisión).
  2. `Section.tiles(...)`, `Section.ingreso_template` e `ingreso_context(...)` en `sections/base.py`; la vista `seccion` de `portada.py` arma el tablero: pide `tiles()` y `context()` a cada tema y renderiza encabezado → camino → título → Hay/Falta → pendiente de la sección (hueco que llena T-318) → tablero → detalles. Mientras un tema no declare `tiles()`, la sección sigue mostrando sus parciales como hoy.
  3. `_tablero.html` (cuadrícula) y `_mosaico.html`: cada mosaico es un `<a href="#d-…">` (sin JavaScript es un ancla a la zona de detalles); dibuja el gráfico con `{% include chart.template %}`; `seccion.html` y `seccion_base.html` con el cuerpo común; zona `.detalles` con cada detalle `id="d-…"` ya renderizado.
  4. `tablero.js` (~60 líneas): detecta la fila del mosaico (los que comparten `offsetTop`), mueve el detalle después del último mosaico de esa fila y lo abre con una transición de `grid-template-rows` de 0,35 s; uno abierto a la vez; el mismo mosaico lo pliega; pone `role="button"`, `aria-expanded` y `aria-controls`; abre el detalle que nombra `location.hash` (o que contiene el elemento con ese id, para `#s1-portal`, `#dictamen-subir` y los redirigidos después de un POST); varios mosaicos pueden abrir el mismo detalle; el tema declara `opens(request)` para `?oferta=`, `?ficha=`, `?historial=`.
  5. `tablero.css`: cuadrícula, mosaicos de 1, 2 y 4 columnas, tono `dark`, detalle, foco visible, las clases `g-*` de la definición compartida 3 y la transición del detalle de 0,35 s.
  6. Tests: `test_tablero_secciones.py` (cada sección que declara `tiles()` abre con su tablero; cada mosaico tiene un detalle existente con id único; `aria-controls` coincide; cada ancla usada por un enlace existe dentro de un detalle), `test_sin_inventos.py` (procedimiento vacío: ningún mosaico muestra cifra, todos muestran `missing`), `test_tablero_componente.py` (con un gráfico de prueba; duración ≤ 0,4 s leída de `tablero.css`).
- **Archivos:** `evaluon/journey/tablero/tiles.py`, `evaluon/templates/journey/_tablero.html`, `_mosaico.html`, `seccion.html`, `seccion_base.html`, `evaluon/static/journey/tablero.css`, `tablero.js`, `evaluon/journey/sections/base.py`, `evaluon/journey/views/portada.py` (la vista `seccion`), `tests/journey/test_tablero_secciones.py`, `test_sin_inventos.py`, `test_tablero_componente.py`.
- **Verificación:** `pytest tests/journey/test_tablero_*.py tests/journey/test_sin_inventos.py tests/journey/test_sections.py tests/journey/test_redirects.py tests/journey/test_live_block.py tests/test_sin_externos.py tests/journey/test_no_external.py`. Criterio REQ-127: el detalle se despliega en 0,4 s o menos (duración en el CSS); uno solo abierto (se prueba la lógica con el HTML; el comportamiento en el navegador se revisa en T-316). Sin `style=` en ninguna plantilla nueva.
- **No tocar:** `charts.py`, `economico.py`, `graficos/*` (T-314), `s3.py` y `s3_ofertas.py` (T-315), `base.html`, `secciones.css`, `tokens.css`, el esquema, `journey/urls.py`.

### T-314 · Gráficos SVG y orden económico

- **Requisitos:** REQ-126, REQ-130, REQ-141
- **Nivel de verificación:** plena (cálculo del orden económico).
- **Qué hay que hacer:**
- **Aviso de tareas anteriores:** (oleada 1) En el tema claro el lima de los gráficos lleva contorno --ink; las series --s2 y --s3 del tema negro quedan a 1,54:1 entre sí (mirarlo en la medición T-316).
  1. `evaluon/journey/tablero/__init__.py` (vacío) y `charts.py` con las siete dataclasses del protocolo (definición compartida 3): `Bars`, `Donuts` (cumple, no cumple, no determinado, pendiente por oferta), `Lollipop` (orden económico de menor a mayor con la más baja y la más alta como indicadores), `Timeline`, `Stack`, `Columns`, `Heat`. Valores `None` o series vacías no dibujan marcas.
  2. `templates/journey/graficos/_bars.html`, `_donuts.html`, `_lollipop.html`, `_timeline.html`, `_stack.html`, `_columns.html`, `_heat.html`: SVG con atributos de presentación, `currentColor` y las clases `g-*`; título y descripción accesibles; sin `style=`.
  3. `economico.py`: ordena las ofertas de menor a mayor total con `assessment.ordering.economic_order(...)` sobre `PortalOfferData.total` (empates con la misma posición), marca la más alta y la más baja y calcula la diferencia porcentual de cada una con la más baja. Sin ofertas, devuelve el día de la apertura (del cronograma) y el estado «Pendiente», sin cifras. Con ofertas sin totales, devuelve solo la cantidad y «Falta el total».
  4. `_economico.html`: cuadro del orden económico (detalle) reutilizable por el primer panel (T-322).
  5. Tests: `test_tablero_graficos.py` (cada gráfico se dibuja con datos mínimos y sin datos; ninguna plantilla de gráfico contiene `style=`, `<text>` con dominios ni direcciones externas) y `test_economico.py`.
- **Archivos:** `evaluon/journey/tablero/__init__.py`, `charts.py`, `economico.py`, `evaluon/templates/journey/graficos/*`, `evaluon/templates/journey/_economico.html`, `tests/journey/test_tablero_graficos.py`, `tests/journey/test_economico.py`.
- **Verificación:** `pytest tests/journey/test_tablero_graficos.py tests/journey/test_economico.py tests/test_sin_externos.py`. Criterio REQ-130: con tres ofertas, orden de menor a mayor, la más baja y la más alta marcadas y la diferencia porcentual de cada una con la más baja; con un empate, la misma posición; sin ofertas, el día de la apertura y «Pendiente» y ninguna cifra; ofertas sin total, sin cifra inventada (REQ-141).
- **No tocar:** `tiles.py`, `tablero.css`, `tablero.js`, `seccion*.html` (T-313), `sections/*`, los temas, `tokens.css`.

### T-315 · Tablero de Ofertas (corte vertical)

- **Requisitos:** REQ-126, REQ-127, REQ-130, REQ-141
- **Nivel de verificación:** plena (es el corte vertical de la feature).
- **Qué hay que hacer:**
  1. `s3_ofertas.tiles()` (en `evaluon/journey/temas/s3_ofertas.py`): mosaicos «Ofertas del acta» (cantidad, columnas con el total; sin totales, solo la cantidad), «La más baja», «La más alta» y «Orden económico» (con `economico.py` y el `Lollipop`), cada uno con su detalle (`d-s3-ofertas` para el primero; el orden económico usa `_economico.html`). `opens(request)` para `?oferta=`, `?ficha=`, `?historial=`. Todo dato que no existe se muestra como `missing` (REQ-141).
  2. `sections/s3.py`: orden de los mosaicos de la sección 3 con el contador de pendientes y `tema_missing`.
  3. Tests con el caso chico (público): el tablero abre con sus mosaicos; «Ofertas del acta» abre el detalle con la comparación de las ofertas; el orden económico con tres ofertas y sin ofertas; el tablero se arma en 2 s o menos con el caso chico; los parciales de los temas de la sección 3 que aún no tienen mosaicos siguen accesibles.
  4. Revisar a mano en el navegador (sin cifras al repositorio): selector de tema, pase de hoja y logotipo en los dos temas con este tablero. La medición formal es T-316.
- **Archivos:** `evaluon/journey/temas/s3_ofertas.py` (`tiles` y `opens`), `evaluon/journey/sections/s3.py`, `tests/journey/test_tablero_ofertas.py`.
- **Verificación:** `pytest tests/journey/test_tablero_ofertas.py tests/journey/temas/test_s3_ofertas.py tests/journey/temas/test_s3_ofertas_history.py tests/journey/test_tablero_secciones.py tests/journey/test_sin_inventos.py`. Criterios de la spec: REQ-127 («Ofertas del acta» despliega la comparación de las tres ofertas), REQ-130, REQ-141.
- **No tocar:** `s3_anexos.py`, `s3_circulares.py`, `s3_ficha.py` (T-326), `tiles.py`, `charts.py`, `tablero.js`, `tablero.css`, `base.html`, `sections/base.py`.

### T-316 · Medición del corte vertical (sin código)

- **Requisitos:** REQ-126, REQ-127, REQ-133, REQ-139
- **Nivel de verificación:** plena. No escribe código de producto.
- **Quién:** el testeador evaluador (cifras) y el Coordinador (revisión visual en Edge). Una sola medición, sin GPU, sobre la rama combinada con `main` y con el caso chico.
- **Umbrales, escritos antes de medir** (de la tabla «Umbrales de las mediciones»): contraste AA al 100 % de los pares declarados en los dos temas; tablero de Ofertas en 2 s o menos con el caso chico; detalle en 0,4 s o menos; pase de hoja en 0,5 s o menos (0,15 s con reducir movimiento); revisión visual del Coordinador en Edge, 1440 × 900, en los dos temas, con el tablero de Ofertas, el selector, el pase de hoja y el logotipo.
- **Qué hay que hacer:** correr los tests de contraste, de externos y de tablero; medir cinco cargas del tablero de Ofertas con el caso chico (mediana) y el despliegue del detalle en Edge; el Coordinador revisa en Edge y deja sus hallazgos. Registrar con qué commit de `main` se corrió. Cada hallazgo con su evidencia y su impacto.
- **Archivos:** `specs/017-tableros-y-estetica/verificacion/T-316.md` (solo cifras y hallazgos).
- **Verificación:** el informe tiene cada umbral con su cifra y el veredicto; los hallazgos pasan todos a T-317.
- **No tocar:** código, tests, plantillas, `tasks.md`.

### T-317 · Correcciones de la medición del corte vertical

- **Requisitos:** REQ-126, REQ-127, REQ-133
- **Nivel de verificación:** plena (corrige lo que la medición encontró).
- **Qué hay que hacer:** corregir todos los hallazgos de T-316 en esta sola tarea, con un commit por hallazgo, y re-medir una vez lo que cambió (segunda y última ronda). Se cierra sin cambios si T-316 cumple todos los umbrales. Lo que no llegue en la segunda ronda pasa, con su impacto, a la lista de revisión con el primer producto. Si un hallazgo exige cambiar una definición compartida, se informa antes de lanzar los bloques de la oleada 8.
- **Archivos:** los de T-311, T-313, T-314 y T-315 que los hallazgos señalen (la lista exacta la fija el Coordinador al lanzar, según el informe) y `specs/017-tableros-y-estetica/verificacion/T-317.md`.
- **Verificación:** los tests que fallaban antes pasan; la re-medición de lo que cambió contra el mismo umbral.
- **No tocar:** archivos de otros bloques; el esquema; lo que ningún hallazgo señale.

### T-318 · Pendientes con acción a mano

- **Requisitos:** REQ-129, REQ-141
- **Nivel de verificación:** plena (cambia una cuenta de la 014 y registra decisiones de personas, P6).
- **Qué hay que hacer:**
  1. `Item` suma `why` (texto que escribe el tema; sin texto no se dibuja la línea), `open` (id del detalle que abre la acción) y `post` (`(url, campos)` de una acción de un solo clic que ya existe como POST con `next` validado: hoy aprobar un ítem del Portal, `s1_portal` con `aprobar=item:<id>`).
  2. `_pendientes.html` reemplaza a `_paneles.html`: pendiente general (todos los ítems de las cinco secciones con el nombre de su sección) y pendiente de cada sección; cada fila con ícono, qué falta, por qué importa, sección y acción (botón que hace POST o enlace que abre el detalle). Los renglones agrupados (`group_items`) siguen agrupándose; las sugerencias del sistema siguen en su bloque aparte (REQ-098). Se incluye en el hueco que dejó T-313. Retirar `_paneles.html`.
  3. Dictamen del Portal (plan, «Cambios de comportamiento»): el ítem de tipo dictamen pasa a contarse como pendiente de la sección 4 (`s4_dictamen.status`) y se excluye de la cuenta de la sección 1 (`stages/portal.py` y `s1_portal._counts`). El total de pendientes del procedimiento no cambia.
  4. Al aprobar desde el pendiente general vuelve a la misma pantalla (`next`); el ítem desaparece de las dos listas y baja el contador; `approval.decide` sigue registrando quién y cuándo (`portal_decision`).
  5. Actualizar los tests de la 014 que contaban el dictamen en la sección 1.
- **Archivos:** `evaluon/journey/sections/base.py`, `evaluon/templates/journey/_pendientes.html`, `evaluon/templates/journey/_paneles.html` (se retira), `evaluon/journey/stages/portal.py`, `evaluon/journey/temas/s1_portal.py` (solo `status` y `_counts`), `evaluon/journey/temas/s4_dictamen.py` (solo `status`), `tests/journey/test_pendientes.py` y los tests de la 014 que cuentan el dictamen (`tests/journey/test_stage_portal.py`, `tests/journey/temas/test_s1_portal.py`, `tests/journey/temas/test_s4_dictamen.py`, `tests/journey/test_sections.py` en lo que cuente el dictamen).
- **Verificación:** `pytest tests/journey/test_pendientes.py tests/journey/test_stage_portal.py tests/journey/temas/test_s1_portal.py tests/journey/temas/test_s4_dictamen.py tests/journey/test_sections.py tests/journey/test_grouped_items.py tests/journey/test_roles.py`. Criterio REQ-129: aprobar «el dictamen publicado en el Portal» desde el pendiente general lo quita de las dos listas, baja en uno el contador de Evaluación y deja el hecho de auditoría con usuario y momento; el total del procedimiento no cambia; el usuario de lectura no ve el botón y el servicio igual lo rechaza.
- **No tocar:** el esquema, `tiles()` de los temas, `base.html`, `tokens.css`, el resto de `s1_portal.py` y `s4_dictamen.py` (los toman T-323 y T-328 después).

### T-319 · Fotos: normalización, subida y elección

- **Requisitos:** REQ-136, REQ-137, REQ-138
- **Nivel de verificación:** plena (datos personales, P4, y medida de un criterio numérico).
- **Qué hay que hacer:** (ADR-0073; plan, «Fotos»)
- **Aviso de tareas anteriores:** (oleada 1) Picked ya tiene su forma final; la ruta accounts:foto la agrega T-320; la subida maneja IntegrityError por ranura repetida y llena size y sha256.
  1. `photos.upload(user, file)`: acepta solo JPEG, PNG o WebP según el contenido (no la extensión); rechaza lo mayor de 10 MiB sin procesar; abre con Pillow con tope de píxeles (rechaza bombas de descompresión); corrige la orientación EXIF; compone sobre blanco lo que tenga transparencia; pasa a luminancia; reduce a 1600 px de lado mayor sin ampliar; ajusta el histograma al de la foto de la casa (tabla de 256 niveles suavizada, en Python puro); guarda como JPEG sin metadatos, con calidad descendente hasta quedar por debajo de 2 MiB; con 10 fotos pide quitar una antes; busca la primera ranura libre (la restricción única de la base cubre la subida simultánea).
  2. `photos.remove(user, photo_id)` (borrado real, solo del dueño) y `photos.pick_for(request)` completo: al azar entre las fotos del usuario (o la de la casa si no tiene), sin repetir la anterior si tiene más de una (la guarda en la sesión); misma forma de la definición compartida 6.
  3. Tests con imágenes generadas en memoria con Pillow (ninguna foto en el repositorio).
- **Archivos:** `evaluon/accounts/photos.py`, `tests/accounts/test_fotos.py`.
- **Verificación:** `pytest tests/accounts/test_fotos.py tests/accounts/test_models_perfil.py tests/test_sin_fotos_en_el_repositorio.py`. Criterios: REQ-137 con dos imágenes sintéticas (oscura y saturada; clara y fría): blanco y negro, diferencia de brillo medio y de contraste de 10 % o menos (meta 5 %); el JPEG guardado no trae EXIF; imagen corrupta, formato no permitido y bomba de píxeles rechazados con mensaje claro; la 11.ª foto se rechaza; tamaño guardado menor a 2 MiB; REQ-138: con 3 fotos, pedidos sucesivos de `pick_for` eligen distinto del anterior.
- **No tocar:** `models.py` y migraciones (T-308), vistas, URLs, plantillas.

### T-320 · Mis fotos

- **Requisitos:** REQ-136
- **Nivel de verificación:** plena (privacidad de datos personales).
- **Qué hay que hacer:**
  1. `views_fotos.py` y rutas de `accounts/urls.py`: `perfil/fotos/` (GET y POST, `accounts:fotos`), `perfil/fotos/<id>/` (GET, `accounts:foto`) y `perfil/fotos/<id>/quitar/` (POST, `accounts:foto_quitar`). El servido usa `get_object_or_404(Photo, pk, user=request.user)`: otro usuario recibe 404 y sin sesión va al ingreso; `Cache-Control: private` y ETag con la huella.
  2. `accounts/fotos.html` y `fotos.css`: hasta 10 ranuras, subir, ver y quitar, con el mensaje claro cuando hay 10 («quitá una antes»); sin la comparación «como la subió» (decisión D-6 del plan).
  3. Agregar «Mis fotos» a `_menu_usuario.html` (archivo de T-311; ajuste respecto del plan, que no lo lista).
  4. El usuario de lectura puede subir y quitar sus fotos; ninguna acción de decisión.
- **Archivos:** `evaluon/accounts/views_fotos.py`, `evaluon/accounts/urls.py`, `evaluon/templates/accounts/fotos.html`, `evaluon/static/accounts/fotos.css`, `evaluon/templates/journey/_menu_usuario.html`, `tests/accounts/test_fotos_privadas.py`.
- **Verificación:** `pytest tests/accounts/test_fotos_privadas.py tests/accounts/test_fotos.py tests/accounts/ tests/journey/test_tema.py`. Criterios REQ-136: dado un usuario con 10 fotos, la 11.ª se rechaza pidiendo quitar una; otro usuario recibe 404 en la foto ajena; sin sesión redirige al ingreso; quitar deja la ranura libre; el enlace del menú aparece.
- **No tocar:** `photos.py`, `models.py`, migraciones, `base.html`, `secciones.css`.

### T-321 · Primer panel: foto, datos principales, pendiente general y avance

- **Requisitos:** REQ-128, REQ-129, REQ-132, REQ-135, REQ-138
- **Nivel de verificación:** plena (datos del procedimiento, criterio de contraste, privacidad).
- **Qué hay que hacer:** (plan, «Primer panel» y «De dónde sale cada dato»)
- **Aviso de tareas anteriores:** (oleada 1) Completar PARES_FOTO en tests/journey/test_contraste.py con el par de la foto.
  1. `evaluon/journey/tablero/ingreso.py`: datos principales del procedimiento (objeto, tipo y número, expediente —«Falta» si no se cargó—, fecha de autorización, cantidad de ofertas, cantidad de pendientes) y el avance como «N de 5 secciones listas» (ADR-0077, D-2); el mosaico «Avance por sección» con el estado de cada sección (ícono, pendientes y faltantes, sin porcentajes). La oferta más alta y la más baja, el orden económico, los plazos y el mantenimiento los agrega T-322 en el mismo archivo.
  2. `_ingreso.html` e `ingreso.css`: foto de fondo en un contenedor absoluto al 60 % del ancho con máscara de degradado y opacidad baja, animación de entrada de 0,9 s (fundido con leve escala; con «reducir movimiento», fundido de 0,3 s), texto «Foto de la casa» o «Foto de su perfil», datos principales con `--ink`, acciones, Hay/Falta, `_window.html` (como está; lo cambia T-330) y el pendiente general con `_pendientes.html`. Foto solo en este panel; la elige `photos.pick_for(request)` al servir la página, sin script que la cambie.
  3. Mosaicos de otra sección (resultado por oferta, descartes propuestos, preguntas): enlaces a `evaluacion/#d-s4-…` con el pase de hoja, sin repetir el detalle (D-4 del plan).
  4. `sections/s1.py`: fija `ingreso_template` e `ingreso_context(...)`, y suma los mosaicos propios del primer panel a los de los temas de la sección 1.
  5. Sin mosaicos ni datos de normativa (régimen, normas, citas) en este panel (D-3 del plan; el pendiente general sí incluye los ítems de Normativas).
  6. Agregar a `test_contraste.py` el par «texto sobre la foto» con el peor caso (píxel más oscuro de la foto de la casa, máxima opacidad) en los dos temas.
- **Archivos:** `evaluon/templates/journey/_ingreso.html`, `evaluon/journey/tablero/ingreso.py`, `evaluon/journey/sections/s1.py`, `evaluon/static/journey/ingreso.css`, `tests/journey/test_primer_panel.py`, `tests/journey/test_contraste.py` (solo el par de la foto).
- **Verificación:** `pytest tests/journey/test_primer_panel.py tests/journey/test_contraste.py tests/journey/test_sections.py tests/journey/test_redirects.py tests/accounts/test_fotos.py`. Criterios: REQ-128 (datos, pendiente general presentes; ningún dato de normativa; revisión a 1440 × 900 en dos pantallas o menos, que revisa el Coordinador); REQ-135 (la foto ocupa a lo sumo el 60 % del ancho, contraste de 4,5:1 o más sobre ella en los dos temas, foto solo en el primer panel); REQ-138 (con 3 fotos, pedidos sucesivos eligen distinto y la página no trae script que cambie la foto); tablero del primer panel en 2 s o menos con el caso chico.
- **No tocar:** el esquema, `photos.py`, `economico.py`, `charts.py`, `s1_datos.py`, `s1_pliego.py`, `s1_portal.py`, `temas/s1_*.html` (T-323), `expedientes.html`, `nuevo.html` (T-324), `window.py`, `_window.html` (T-330).

### T-322 · Primer panel: orden económico, plazos y mantenimiento

- **Requisitos:** REQ-128, REQ-130, REQ-131, REQ-141
- **Nivel de verificación:** plena (cálculo de fechas; no se inventa ningún dato).
- **Qué hay que hacer:** (plan, «Datos que faltan hoy»; ADR-0077)
  1. En `ingreso.py`: indicadores «La más alta» y «La más baja» y el mosaico «Orden económico» con `economico.py` y `_economico.html` (sin ofertas: día de la apertura y «Pendiente»; sin total: «Falta»).
  2. Vencimiento del mantenimiento: leer `mantenimiento_oferta` de la última página guardada del Portal (`parse_page`), sumarlo a la apertura del cronograma si es en días corridos y mostrar «Fuente: Portal, tomado el …». En días hábiles: «N días hábiles desde la apertura» y «Falta el calendario». Memoizado por pedido. Si la lectura pasa de unos 150 ms, se informa para decidir guardar el dato (ADR-0077, alternativa B, con migración en un bloque aparte); no se hace en esta tarea.
  3. `Timeline` de plazos: apertura (cronograma), hoy, vencimiento del mantenimiento y dictamen (fecha del documento o del Portal si existe; «Pendiente» si no), con lo que ya pasó, lo de hoy y lo que viene; días hasta el vencimiento.
  4. Incluir ambos mosaicos y el panel de plazos en `_ingreso.html`.
- **Archivos:** `evaluon/journey/tablero/ingreso.py`, `evaluon/templates/journey/_ingreso.html`, `evaluon/static/journey/ingreso.css`, `tests/journey/test_primer_panel_plazos.py`.
- **Verificación:** `pytest tests/journey/test_primer_panel_plazos.py tests/journey/test_primer_panel.py tests/journey/test_economico.py`. Criterios: REQ-131 con apertura del 22/09/2026, 60 días corridos y hoy 21/10/2026: «21/11 · vence el mantenimiento de las ofertas» y «faltan 31 días»; con días hábiles, «Falta el calendario»; REQ-130 con tres ofertas y sin ofertas; REQ-141 sin dictamen: «Pendiente»; sin cronograma: «Falta». Medida de 2 s con el caso chico incluyendo la lectura del plazo.
- **No tocar:** `economico.py` y `charts.py` (se usan, no se cambian), el esquema, `s1.py`, los temas.

### T-323 · Mosaicos de la sección Procedimiento

- **Requisitos:** REQ-126, REQ-129, REQ-141
- **Nivel de verificación:** plena (datos de la 014 que pasan a mosaicos, `why` de los pendientes).
- **Qué hay que hacer:** `tiles()` y `opens()` de `s1_datos`, `s1_pliego` y `s1_portal`: «Datos del procedimiento» (renglones, garantías, cronograma), «Portal de Compras» (sin aprobar, novedades) y «Alta desde el pliego» (borradores), mosaicos agregados a los de la maqueta para que ninguna función de la 014 quede sin acceso (D-5 del plan). Cada mosaico abre el parcial de su tema (`d-s1-datos`, `d-s1-portal`, `d-s1-pliego`) con las anclas de la 014 (`#s1-portal`) funcionando. Escribir `why` en los ítems donde el tema sabe el motivo. Ajustar los estilos de los parciales a los tokens. Un dato ausente es `missing`.
- **Archivos:** `evaluon/journey/temas/s1_datos.py`, `s1_pliego.py`, `s1_portal.py` (`tiles`, `opens` y `why`), `evaluon/templates/journey/temas/s1_*.html`, `evaluon/templates/journey/temas/_s1_*.html`, `evaluon/static/journey/s1.css`, `s1_pliego.css`, `tests/journey/temas/test_s1_tiles.py`.
- **Verificación:** `pytest tests/journey/temas/test_s1_tiles.py tests/journey/temas/test_s1_datos.py tests/journey/temas/test_s1_pliego.py tests/journey/temas/test_s1_portal.py tests/journey/test_tablero_secciones.py tests/journey/test_sin_inventos.py tests/journey/test_pendientes.py`. Criterios: cada mosaico tiene su detalle y su ancla; procedimiento vacío sin cifras; las funciones de la 014 (REQ-075 a REQ-099) siguen en verde en estos temas; sección en 2 s o menos con el caso chico.
- **No tocar:** `status` y `_counts` de `s1_portal.py` (T-318), `sections/s1.py`, `_ingreso.html`, `ingreso.py` (T-321), `expedientes.html`, `nuevo.html`, `s1_pliego_borrador.html` (T-324), `tiles.py`.

### T-324 · Listado de procedimientos, alta y borrador con la estética nueva

- **Requisitos:** REQ-132, REQ-133
- **Nivel de verificación:** liviana (solo presentación; los tests de la 014 que ya existen siguen en verde).
- **Qué hay que hacer:** pasar `expedientes.html`, `nuevo.html` y `s1_pliego_borrador.html` a los tokens y componentes nuevos (tablas, formularios, botones, camino) sin cambiar su comportamiento. Si necesitan reglas propias, van en `evaluon/static/journey/procedimientos.css` (archivo nuevo, enlazado con `{% block head %}`).
- **Archivos:** `evaluon/templates/journey/expedientes.html`, `nuevo.html`, `s1_pliego_borrador.html`, `evaluon/static/journey/procedimientos.css` (si hace falta), `tests/journey/test_procedimientos_estetica.py`.
- **Verificación:** `pytest tests/journey/test_procedimientos_estetica.py tests/journey/test_queries.py tests/journey/temas/test_s1_pliego.py tests/journey/test_no_external.py tests/test_sin_externos.py`. Un test que falla antes y pasa después: las tres páginas cargan en los dos temas, sin `style=`, sin colores en hexadecimal y con el recorrido.
- **No tocar:** `temas/s1_*.html`, `s1.css`, `s1_pliego.css` (T-323), `secciones.css`, `base.html`.

### T-325 · Tablero de Pliego y matriz

- **Requisitos:** REQ-126, REQ-129, REQ-141
- **Nivel de verificación:** plena.
- **Qué hay que hacer:** `tiles()` y `opens()` de `s2_documentos` y `s2_matriz`: «Requisitos» (cantidad, versión, cambios por revisar), «Versiones de la matriz», «Documentos del pliego» (cargados; el «de N» solo si el Portal lista los documentos) y «Cumplimiento por tipo y oferta» (`Heat` con `memo.matrix_page`; sin evaluación: «Pendiente»; enlaza a `evaluacion/#d-s4-propuesta`). «Requisitos» y «Versiones» pueden abrir el mismo detalle (`d-s2-matriz`). Escribir `why` donde el tema sabe el motivo. Ajustar los parciales a los tokens y respetar las anclas de la 014.
- **Archivos:** `evaluon/journey/temas/s2_*.py`, `evaluon/journey/sections/s2.py`, `evaluon/templates/journey/temas/s2_*.html`, `evaluon/static/journey/s2*.css`, `evaluon/static/tenders/matrix.css`, `evaluon/static/journey/s2_documentos.js` (solo si cambia el detalle), `tests/journey/temas/test_s2_tiles.py`.
- **Verificación:** `pytest tests/journey/temas/test_s2_tiles.py tests/journey/temas/test_s2_documentos.py tests/journey/temas/test_s2_matriz.py tests/journey/temas/test_s2_matriz_actions.py tests/journey/test_stage_matriz.py tests/journey/test_tablero_secciones.py tests/journey/test_sin_inventos.py`. Criterios: sin evaluación el mosaico de cumplimiento dice «Pendiente» y no muestra cifra; sin pliego, «Falta»; funciones de la 014 en verde; sección en 2 s o menos con el caso chico.
- **No tocar:** `sections/base.py`, `tiles.py`, `charts.py`, los temas de otras secciones, `tokens.css`.

### T-326 · Resto del tablero de Ofertas

- **Requisitos:** REQ-126, REQ-129, REQ-141
- **Nivel de verificación:** plena.
- **Qué hay que hacer:** `tiles()` y `opens()` de `s3_anexos`, `s3_circulares`, `s3_ficha` y el resto de `s3_ofertas`: «Hojas de compliance» («N de M» con la hoja presente por oferta), «Documentación de las ofertas» (cantidad por oferta y faltantes que el sistema conoce, sin «de 9»; D-11 del plan), «Circulares» y «Fichas de las ofertas». Cada uno abre su parcial (`d-s3-anexos`, `d-s3-circulares`, `d-s3-ficha`, `d-s3-ofertas`) y respeta `opens()` y las anclas de la 014. Escribir `why` donde corresponda. No se vuelve a tocar lo que T-315 entregó (mosaicos de orden económico y «Ofertas del acta»).
- **Archivos:** `evaluon/journey/temas/s3_anexos.py`, `s3_circulares.py`, `s3_ficha.py`, `s3_ofertas.py` (resto), `evaluon/templates/journey/temas/s3_*.html`, `_s3_*.html`, `evaluon/static/journey/s3*.css`, `s3_circulares.js`, `s3_ofertas.js`, `tests/journey/temas/test_s3_tiles.py`.
- **Verificación:** `pytest tests/journey/temas/test_s3_tiles.py tests/journey/temas/test_s3_anexos.py tests/journey/temas/test_s3_circulares.py tests/journey/temas/test_s3_ficha.py tests/journey/temas/test_s3_ofertas.py tests/journey/test_tablero_ofertas.py tests/journey/test_sin_inventos.py`. Criterios: ningún «de N» inventado; funciones de la 014 en verde; sección en 2 s o menos con el caso chico.
- **No tocar:** `sections/s3.py`, `sections/base.py`, `tiles()` de «Ofertas del acta» y orden económico, `tiles.py`, `charts.py`.

### T-327 · Tablero de Evaluación, parte 1

- **Requisitos:** REQ-126, REQ-141
- **Nivel de verificación:** plena (resultados de la evaluación; un número equivocado aquí engaña a la Comisión, P3).
- **Qué hay que hacer:** `tiles()` y `opens()` de `s4_propuesta`: «Resultado por oferta» (`Donuts`: cumple, no cumple, no determinado, pendiente), «No cumple» y «No determinado» (cifras desde `by_outcome`) y «Cumplimiento por tipo» (`Heat`), abriendo `d-s4-propuesta`. Sin evaluación, cada mosaico dice «Pendiente» y no muestra valor. Orden y composición de la sección 4 en `sections/s4.py`. Escribir `why` en los ítems de la propuesta. Los parciales conservan el fundamento y la cita de cada propuesta (P3).
- **Archivos:** `evaluon/journey/temas/s4_propuesta.py`, `s4_propuesta_acciones.py`, `evaluon/journey/sections/s4.py`, `evaluon/templates/journey/temas/s4_propuesta.html`, `s4_propuesta_par.html`, `evaluon/static/journey/s4.css`, `s4_propuesta.css`, `tests/journey/temas/test_s4_tiles_propuesta.py`.
- **Verificación:** `pytest tests/journey/temas/test_s4_tiles_propuesta.py tests/journey/temas/test_s4_propuesta.py tests/journey/temas/test_s4_fundamento.py tests/journey/temas/test_s4_fundamento_pantallas.py tests/journey/test_evaluation_stage.py tests/journey/test_sin_inventos.py`. Criterios: REQ-141 (sin evaluación, «Pendiente»); las cifras coinciden con las celdas guardadas; el fundamento se sigue mostrando; sección en 2 s o menos con el caso chico (el contexto más pesado se calcula una vez).
- **No tocar:** `s4_dictamen.py`, `s4_informe.py`, `s4_descartes.py`, `s4_preguntas.py`, `s4_exportar.py` (T-328), `sections/base.py`, instrucciones o evaluación (`assessment/`).

### T-328 · Tablero de Evaluación, parte 2

- **Requisitos:** REQ-126, REQ-129, REQ-141
- **Nivel de verificación:** plena (dictamen y descartes tocan decisiones de personas).
- **Qué hay que hacer:** `tiles()` y `opens()` de `s4_informe` (estado de lectura, apto o no apto; «N págs.» solo cuando se conocen), `s4_dictamen` («Dictamen»: «Pendiente» si no hay; el contador de Evaluación ya lo cuenta T-318), `s4_descartes`, `s4_preguntas` y `s4_exportar`. Cada uno abre su parcial (`d-s4-informe`, `d-s4-dictamen`, `d-s4-descartes`, `d-s4-preguntas`, `d-s4-exportar`) con las anclas de la 014 (`#dictamen-subir`). Escribir `why` en los ítems de dictamen, descartes y preguntas. Sin tocar `status` de `s4_dictamen.py`, que dejó T-318.
- **Archivos:** `evaluon/journey/temas/s4_informe.py`, `s4_dictamen.py` (`tiles`, `opens` y `why`), `s4_descartes.py`, `s4_preguntas.py`, `s4_preguntas_acciones.py`, `s4_exportar.py`, `evaluon/templates/journey/temas/s4_informe.html`, `s4_dictamen.html`, `s4_descartes.html`, `s4_preguntas.html`, `s4_exportar.html`, `_s4_*.html`, `evaluon/static/journey/s4_descartes.css`, `s4_dictamen.css`, `s4_informe.css`, `s4_preguntas.css`, `tests/journey/temas/test_s4_tiles_resto.py`.
- **Verificación:** `pytest tests/journey/temas/test_s4_tiles_resto.py tests/journey/temas/test_s4_dictamen.py tests/journey/temas/test_s4_dictamen_historial.py tests/journey/temas/test_s4_informe.py tests/journey/temas/test_s4_descartes.py tests/journey/temas/test_s4_preguntas.py tests/journey/temas/test_s4_exportar.py tests/journey/test_pendientes.py tests/journey/test_sin_inventos.py`. Criterios: REQ-141 (un procedimiento sin dictamen: el mosaico de Evaluación dice «Pendiente» y no muestra un valor); REQ-129 (las acciones de dictamen, descartes y preguntas siguen a mano); funciones de la 014 en verde; sección en 2 s o menos.
- **No tocar:** `s4_propuesta*.py`, `sections/s4.py`, `s4.css`, `s4_propuesta.css` (T-327), `sections/base.py`, `status` de `s4_dictamen.py`.

### T-329 · Tablero de Normativas

- **Requisitos:** REQ-126, REQ-129, REQ-141
- **Nivel de verificación:** plena.
- **Qué hay que hacer:** `tiles()` y `opens()` de `s5_rigen`, `s5_consulta` y `s5_normas`: «Normas que rigen» («N de M»: validada, sin validar, falta), «Citas del pliego» («N normas citadas · M cargadas», no menciones en el texto; D del plan), «Régimen que rige» (`applicable_regimes(authorization_date)`), «Consulta de normativa» y «Normas cargadas». Cada uno abre su parcial (`d-s5-rigen`, `d-s5-consulta`, `d-s5-normas`) con las anclas de la 014. Adaptar la página general de normativas (`normativas.html`) a los tokens. Escribir `why` donde corresponda.
- **Archivos:** `evaluon/journey/temas/s5_*.py`, `evaluon/journey/sections/s5.py`, `evaluon/templates/journey/temas/s5_*.html`, `evaluon/templates/journey/normativas.html`, `evaluon/static/journey/s5*.css`, `s5_consulta.js`, `tests/journey/temas/test_s5_tiles.py`, `tests/journey/test_normativas_general.py`.
- **Verificación:** `pytest tests/journey/temas/test_s5_tiles.py tests/journey/temas/test_s5_rigen.py tests/journey/temas/test_s5_consulta.py tests/journey/temas/test_s5_normas.py tests/journey/test_normativas_general.py tests/journey/test_tablero_secciones.py tests/journey/test_sin_inventos.py`. Criterios: sin normas cargadas, «Falta» y ninguna cifra; la consulta apagada se sigue comportando como en la 014; sección en 2 s o menos con el caso chico.
- **No tocar:** `sections/base.py`, `tiles.py`, `charts.py`, otros temas, `tokens.css`.

### T-330 · Avance de procesos largos

- **Requisitos:** REQ-140
- **Nivel de verificación:** plena (cálculo de un porcentaje que se muestra a la Comisión; no se inventa uno).
- **Qué hay que hacer:** (plan, «Avance de los procesos largos»; D-9 y D-10)
  1. `window.py` suma `overall_percent`: `(ofertas hechas + requisitos hechos / requisitos de la oferta en curso) / ofertas`, con tope 99 mientras corre. Evaluar ofertas y fichas dan porcentaje; matriz, lectura y Portal muestran paso, tiempo transcurrido y barra indeterminada, sin porcentaje inventado.
  2. `_window.html`: porcentaje grande, «oferta 2 de 3 · requisito 14 de 23», barra con acento lima y los últimos 3 pasos en lenguaje llano; se conservan los estados terminado, falló y espera. Sondeado por `ventana/`.
  3. `_avance_encabezado.html` y `views/avance.py`: anillo SVG con el porcentaje (o el giro indeterminado), solo con un pedido en espera o en curso, enlazado al primer panel, en todas las páginas del procedimiento, sondeado con el mismo `recorrido.js` (5 s, dentro de los 10 s de REQ-067).
  4. `avance.css` (el archivo que dejó T-311 con un comentario): panel e indicador.
- **Archivos:** `evaluon/journey/window.py`, `evaluon/journey/views/avance.py`, `evaluon/templates/journey/_window.html`, `_avance_encabezado.html`, `evaluon/static/journey/avance.css`, `tests/journey/test_window.py`, `tests/journey/test_avance_encabezado.py`.
- **Verificación:** `pytest tests/journey/test_window.py tests/journey/test_avance_encabezado.py tests/journey/test_avance_minimo.py tests/journey/test_progress.py tests/journey/test_live_block.py`. Criterios REQ-140: con una evaluación en curso, el encabezado de cualquier sección muestra el porcentaje y el primer panel muestra dónde va y los últimos 3 pasos; el intervalo de `recorrido.js` es de 10 s o menos (hoy 5 s); porcentaje del caso de dos ofertas de tres con 14 de 23 requisitos; matriz y lectura sin porcentaje; contraste de los colores del avance en los dos temas.
- **No tocar:** `recorrido.js`, `progress.py`, `_ingreso.html`, `base.html`, `journey/urls.py`.

### T-331 · Cierre técnico

- **Requisitos:** REQ-133, REQ-142
- **Nivel de verificación:** plena (principio de la guía visual y retiro de lo viejo).
- **Qué hay que hacer:**
- **Aviso de tareas anteriores:** (oleada 1) Quedan con hexadecimales _sprite.html, _window.html, tenders/matrix.css y tenders/print.css; el test de var() sin definir ya existe en test_contraste.py; Barlow se retira acá. Retirar los tokens transitorios --hdr*, los alias --ev-azul-200/800 y los pares «encabezado viejo» de test_contraste.py.
  1. Quitar los alias `--ev-*` de `tokens.css` y los restos del azul, el beige y el rojo viejos en `recorrido.css` y en cualquier hoja que quede; retirar Barlow Condensed (`evaluon/static/diseno/fuentes/barlow-*`) y cualquier referencia.
  2. Test final: prohíbe los `--ev-azul-*`, `--ev-beige-*`, `--ev-rojo*` y los colores en hexadecimal fuera de `tokens.css` (excepto `print.css`, que sigue siempre claro).
  3. Test del verde lima: compara los usos de `--lime` con una lista corta de selectores permitidos (pestaña activa, contadores, avance, lo más bajo, acción principal en el tema negro).
  4. Test de anclas: en las cinco secciones, todo enlace `#…` de las plantillas apunta a un elemento que existe dentro de un detalle.
  5. Revisar por contraste las pantallas viejas de `tenders/` y `queries/` (no se migran, plan).
  6. Cerrar `docs/diseno/guia-visual.md` con la versión final.
- **Archivos:** `evaluon/static/diseno/tokens.css`, `evaluon/static/diseno/fuentes/barlow-*`, `evaluon/static/journey/recorrido.css` (resto), `docs/diseno/guia-visual.md`, `tests/journey/test_tokens_viejos.py`, `tests/journey/test_verde_lima.py`, `tests/journey/test_anclas_detalles.py`, `tests/journey/test_contraste.py` (revisión final de pares).
- **Verificación:** `pytest tests/journey/test_tokens_viejos.py tests/journey/test_verde_lima.py tests/journey/test_anclas_detalles.py tests/journey/test_contraste.py tests/test_sin_externos.py tests/journey/test_no_external.py tests/journey/test_marca.py`. Criterio: contraste AA al 100 % en los dos temas con todos los pares finales; 0 colores sueltos; 0 direcciones externas. Suite completa del área `tests/journey`.
- **No tocar:** el esquema, plantillas de los temas, `base.html`, funciones de la 014.

### T-332 · Runbook de despliegue

- **Requisitos:** REQ-134, REQ-136
- **Nivel de verificación:** liviana (documento; el Coordinador ejecuta cada paso en una copia antes de darlo por bueno).
- **Qué hay que hacer:** `specs/017-tableros-y-estetica/entorno.md` con el procedimiento reproducible desde cero: (1) reconstruir la imagen (`docker compose build app` y `docker compose up -d`) porque WhiteNoise sirve lo que `collectstatic` reunió (tipografía, marca, foto de la casa); (2) migración de `accounts` (`0003_tema_y_fotos`) con base con datos, según `migrate_on_start.sh`: detener `app`, respaldar con `pg_dump` a `backups/`, aplicar `migrate` y levantar todo; (3) cómo volver atrás (migración reversible y respaldo); (4) comprobaciones posteriores (ingreso 200, tema, una foto de prueba, tablero de cada sección); (5) la raíz de la instancia siempre en `main` (8000 monta `./evaluon`); (6) que el clon de la 016 copia la base con las fotos y queda en el equipo.
- **Aviso de tareas anteriores:** (oleada 1) La migración accounts 0003 hacia atrás borra accounts_photo y theme: respaldo antes. El CASCADE de fotos es solo del ORM (FK NO ACTION en la base): un DELETE crudo de usuario falla.
- **Archivos:** `specs/017-tableros-y-estetica/entorno.md`.
- **Verificación:** los comandos se corrieron en el clon (`scripts/clon.sh`) o en una copia con una base de prueba, y el documento anota el resultado de cada paso; la migración hacia atrás se probó.
- **No tocar:** código, compose, scripts.

### T-333 · Medición final y revisión visual (sin código)

- **Requisitos:** REQ-126, REQ-133, REQ-139
- **Nivel de verificación:** plena. No escribe código de producto.
- **Quién:** el Coordinador, una sola vez, con el procedimiento real del piloto en una instancia local con la rama combinada con `main` (el clon `scripts/clon.sh` o una copia de la base según `entorno.md`). Sin GPU. Al repositorio solo van cifras; ningún dato del procedimiento real.
- **Umbrales, escritos antes de medir:** tablero de cada una de las cinco secciones en 2 s o menos (mediana de 5 cargas por sección); contraste AA al 100 % en los dos temas (test); detalle en 0,4 s o menos; revisión visual de las cinco secciones en los dos temas sin hallazgos que impidan usar la pantalla; el primer panel entra en dos pantallas a 1440 × 900; el pase de hoja y «reducir movimiento» en Edge. Suite completa sobre la rama combinada con `main`, informando con qué commit se corrió.
- **Qué hay que hacer:** correr la medición, anotar las cifras por sección, revisar cada sección en claro y en negro y dejar los hallazgos con su evidencia y su impacto.
- **Archivos:** `specs/017-tableros-y-estetica/verificacion/T-333.md`.
- **Verificación:** cada umbral con su cifra y su veredicto; los hallazgos pasan todos a T-334.
- **No tocar:** código, tests, `tasks.md`.

### T-334 · Correcciones de la medición final

- **Requisitos:** REQ-126, REQ-133
- **Nivel de verificación:** plena.
- **Qué hay que hacer:** corregir los hallazgos de T-333 en una sola tarea, con un commit por hallazgo, y re-medir una vez lo que cambió (segunda y última ronda). Se cierra sin cambios si T-333 cumple todo. Lo que no llegue pasa, con su impacto, a la lista de revisión del primer producto.
- **Archivos:** los que los hallazgos señalen (la lista exacta la fija el Coordinador al lanzar) y `specs/017-tableros-y-estetica/verificacion/T-334.md`.
- **Verificación:** los tests que fallaban antes pasan; la re-medición de lo que cambió contra el mismo umbral.
- **No tocar:** el esquema ni nada que ningún hallazgo señale.

## Suites completas por oleada (ADR-0012)

| Fecha | Oleada | Commit de `main` | Resultado |
|---|---|---|---|
| — | — | — | — |

## Lista de revisión (hallazgos que no impiden integrar; se corrigen en una sola tarea por lote, ADR-0025)

| Clave | De | Qué | Dónde se corrige | Estado |
|---|---|---|---|---|
| — | — | — | — | — |
