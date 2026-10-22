# Plan 017 · Tableros de primer nivel y estética nueva

Estado: borrador · Fecha: 2026-10-21 · Aprobó: —

Spec: `specs/017-tableros-y-estetica/spec.md` (aprobada el 2026-10-21)

ADR de este plan, **propuestos**: `docs/adr/0073-fotos-personales-en-la-base-y-servidas-a-su-dueno.md`, `docs/adr/0074-tema-en-el-perfil-del-usuario-dibujado-por-el-servidor.md`, `docs/adr/0075-pase-de-pagina-con-transiciones-entre-documentos.md`, `docs/adr/0076-tablero-de-mosaicos-con-html-del-servidor-y-poco-javascript.md` y `docs/adr/0077-datos-del-tablero-que-hoy-no-existen.md`. Se apoya en 0045 (estado calculado y sondeo), 0047 (cinco secciones) y 0065 (datos y servicios externos). REQ-133 reemplaza a REQ-100 y REQ-142 enmienda a REQ-108.

## Resumen del enfoque

Las funciones de la 014 ya existen y no cambian: cada tema (`journey/temas/`) calcula su estado y dibuja su detalle en un parcial. Esta feature **cambia la presentación sobre esa misma estructura**: cada sección abre con un tablero de mosaicos y el parcial de cada tema pasa a ser el **detalle** que se despliega debajo del mosaico que se toca. Se hace con lo que ya usa el proyecto: plantillas de Django, CSS propio, gráficos en SVG dibujados por la plantilla y dos scripts chicos (el del detalle desplegable y el de la dirección del pase de página). No se agrega ningún marco de interfaz ni dependencia nueva (Pillow 12.3.0 ya está instalado).

Seis ideas ordenan el plan:

1. **Una base común primero** (tokens de los dos temas, tipografía y marca alojadas, encabezado, selector de tema, pase de página y el componente «mosaico con detalle»), probada de punta a punta con un solo tablero (el de Ofertas) antes de hacer los demás.
2. **El tema vive en el servidor**: una columna en el usuario; la página sale ya dibujada en el tema elegido (sin parpadeo y sin JavaScript).
3. **Las fotos se guardan en la base**, normalizadas al subir, y se sirven por una vista que solo responde a su dueño. No hay carpeta de fotos que pueda llegar al repositorio.
4. **El pase de página es CSS** (`@view-transition`), con fundido corto para «reducir movimiento». En los navegadores que no lo implementan (hoy Firefox) la navegación es la de siempre, sin animación.
5. **Los tableros solo muestran datos que el sistema tiene**. Lo que no existe se muestra como «Falta» o «Pendiente» (REQ-141). Los cuatro datos que la maqueta usa y el sistema no tiene (monto estimado, vencimiento del mantenimiento, avance y denominadores de documentos) se resuelven en el ADR-0077 y en la tabla «Datos que faltan hoy».
6. **Los bloques de trabajo se pueden repartir**: después de la base, cada sección es un bloque con sus archivos y sin archivos compartidos con los demás.

## Lo que se reutiliza y lo que se cambia

| Hoy | En esta feature |
|---|---|
| `journey/temas/*.py` (`status()`, `context()`, `PARTIAL`) y `templates/journey/temas/*.html` | Se conservan. Cada tema suma `tiles()` (qué mosaicos aporta); su parcial se muestra como detalle. |
| `journey/sections/` (`Section`, `Item`, `TemaStatus`, `sections_for`) | Se conservan; `Item` suma `why`, `open` y `post` (ver «Pendientes»). Las cuentas no cambian, salvo el dictamen del Portal (ver «Cambios de comportamiento»). |
| `journey/progress.py` y `journey/window.py` (avance, últimos pasos, `plain_reason`) | Se reutilizan tal cual; `window.py` suma un porcentaje global (ver «Avance»). |
| `recorrido.js` (sondeo cada 5 s de cualquier `[data-poll-url]`, pausa con pestaña oculta, foco conservado) | Se reutiliza sin cambios: el indicador del encabezado es un bloque más con `data-poll-url`. |
| `static/diseno/tokens.css`, `static/journey/secciones.css`, `base.html`, `_cabecera.html`, `_encabezado.html`, `_barra*.html`, `seccion*.html`, `portada.html`, `_paneles.html`, `_window.html` | Se reescriben o se reemplazan (ver «Componentes»). |
| `static/marca/` (T-267, REQ-108) | Se reemplaza por los archivos de `docs/diseno/marca/017/` (REQ-142). |
| `evaluon/accounts/` (User sin preferencias) | Suma `theme` y la tabla de fotos. |

## Criterio de aceptación numérico y umbrales (escritos antes de medir, ADR-0024 y ADR-0025)

| Qué | Umbral | Con qué se mide | Bloque |
|---|---|---|---|
| Contraste AA en los dos temas | 100 % de los pares declarados: texto 4,5:1; íconos y gráficos 3:1; incluido el peor caso del texto sobre la foto del primer panel | `tests/journey/test_contraste.py` (calcula la razón de cada par desde `tokens.css`) | B0.2, B2, B8 |
| Tablero de cada sección | 2 s o menos hasta verse completo: mediana de 5 cargas por sección con un procedimiento real del piloto (al repositorio solo cifras); en los tests, 2 s con el caso chico | Medición local del Coordinador una sola vez al cierre (B8); test con el caso chico en cada bloque | B0.4, B8 |
| Detalle que se despliega | 0,4 s o menos | Test que lee la duración en `tablero.css`; revisión en el navegador | B0.4 |
| Pase de hoja | 0,5 s o menos; con «reducir movimiento», 0,15 s o menos | Test que lee `pase.css`; revisión en el navegador | B0.3 |
| Tono de las fotos | Brillo medio y contraste de dos fotos muy distintas difieren en 10 % o menos (meta de implementación: 5 %) | `tests/accounts/test_fotos.py` con dos imágenes sintéticas generadas en memoria | B1 |
| Fotos | Máximo 10 por usuario y 2 MiB cada una | Restricciones de la base (ranura 0 a 9 única por usuario; tamaño ≤ 2.097.152 bytes) y test | B0.1, B1 |
| Primer panel | Datos principales, pendiente general, orden económico y plazos en dos pantallas o menos a 1440 × 900 | Revisión del Coordinador en el navegador | B2 |
| Avance | Se actualiza cada 10 s o menos | Test del intervalo de `recorrido.js` (hoy 5 s) y del indicador con un pedido en curso | B7 |
| Sin servicios externos | 0 direcciones externas en plantillas, hojas de estilo, scripts y SVG | `tests/test_sin_externos.py` | B0.2 y cada bloque |
| Funciones de la 014 | REQ-075 a REQ-099 siguen en verde | Suite completa sobre la rama combinada con `main` | todos |

Máximo dos rondas de ajuste por medición; lo que no llegue pasa con su impacto a la lista de revisión con el primer producto.

## Componentes

| Componente | Nuevo | Qué hace | Con quién habla |
|---|---|---|---|
| `evaluon/static/diseno/tokens.css` | Cambia | Tokens de los dos temas (`:root` gris y blanco; `[data-theme="negro"]`), `@font-face` de Hanken Grotesk, y alias de los `--ev-*` viejos hasta el cierre (B8) | Todas las hojas de estilo |
| `evaluon/static/diseno/fuentes/` | Cambia | Hanken Grotesk variable (subconjuntos latin y latin-ext, woff2) con su licencia (OFL 1.1) | `tokens.css` |
| `evaluon/static/marca/` | Cambia | Los cuatro SVG de `docs/diseno/marca/017/` (logotipo e isotipo, versión clara y negra) | `base.html`, encabezado |
| `templates/base.html` | Cambia | `<html data-theme>` según `user.theme`; hojas `tokens.css`, `secciones.css`, `tablero.css`, `pase.css`; íconos de pestaña | Todas las páginas |
| `templates/journey/_cabecera.html`, `_encabezado.html`, `_barra.html`, `_barra_nueva.html` | Cambian | Encabezado único: logotipo (versión del tema), pestañas en píldora con el contador de pendientes, indicador de avance, selector de tema, menú de usuario (Mis fotos, Salir) | `sections_for`, vista `avance` |
| `templates/journey/_camino.html`, `_hay_falta.html` | Nuevos | Recorrido «Procedimientos › procedimiento › sección» y línea «Hay: … · Falta: …» | `Section.summary`, `Section.tema_missing` |
| `templates/journey/_selector_tema.html` | Nuevo | Formulario con dos botones (gris y blanco / negro) que hace POST a `accounts:tema` | `accounts.views_perfil` |
| `evaluon/journey/tablero/` | Nuevo | `tiles.py` (`Tile` y su contrato), `charts.py` (los siete tipos de gráfico), `economico.py` (orden económico y diferencias), `ingreso.py` (datos del primer panel) | Los temas, `ordering`, `memo` |
| `templates/journey/_tablero.html`, `_mosaico.html`, `graficos/_*.html` | Nuevos | Cuadrícula de mosaicos, mosaico y los gráficos en SVG con atributos de presentación (sin `style=`) | `Tile` |
| `templates/journey/seccion.html`, `seccion_base.html` | Cambian | Cuerpo común: camino, título, Hay/Falta, pendiente de la sección, tablero y, al final, los detalles (parciales de los temas) | `tablero/`, parciales |
| `templates/journey/_pendientes.html` | Nuevo (reemplaza `_paneles.html`) | Pendiente general o de sección: qué falta, por qué importa, en qué sección está y su acción a mano | `Item` |
| `templates/journey/_ingreso.html` | Nuevo | Primer panel: foto de fondo, datos principales, acciones, Hay/Falta, avance, pendiente general | `tablero/ingreso.py`, `accounts.photos` |
| `templates/journey/_window.html`, `_avance_encabezado.html` | Cambia / Nuevo | Avance de procesos largos: panel (porcentaje, dónde va, últimos 3 pasos) e indicador chico del encabezado | `window_for`, `progress_of` |
| `static/journey/secciones.css` | Cambia | Base: tipografía, encabezado, botones, formularios, tablas, íconos de estado | `tokens.css` |
| `static/journey/tablero.css`, `pase.css`, `ingreso.css`, `avance.css` | Nuevos | Mosaicos y detalle; transiciones entre páginas; primer panel con foto; indicador y panel de avance | Plantillas |
| `static/journey/tablero.js` (~60 líneas), `pase.js` (~15 líneas) | Nuevos | Detalle bajo la fila del mosaico (uno abierto a la vez; abre el de `#d-…`); dirección del pase de hoja | Plantillas |
| `evaluon/accounts/models.py`, `photos.py`, `views_perfil.py`, `views_fotos.py`, `urls.py` | Cambian / Nuevos | `User.theme`; tabla `Photo`; normalización, subida, baja, elección al azar y servido de fotos; vista del tema | Pillow, base |
| `templates/accounts/fotos.html`, `login.html` | Nuevo / Cambia | Página «Mis fotos» y el ingreso con el logotipo claro | `accounts` |
| `journey/views/portada.py`, `journey/views/avance.py`, `journey/urls.py` | Cambian / Nuevo | La portada pasa a ser el primer panel (redirige a `procedimiento/`); vista del indicador; `without_actions` no quita los formularios de preferencias | `window_for` |
| `worker`, `portal_worker`, `app` (servicios), IA | No | Sin cambios de arquitectura | — |

El camino de pliegos y ofertas **no depende de ningún servicio externo** (P4): la feature no llama a la IA ni a internet; tipografía, foto de la casa y marca están en `evaluon/static/` y los gráficos se dibujan en el servidor.

### Cómo se comunican

Una vista de sección arma `Overview` (`sections_for`, ya memoizada por pedido con `memo.scoped`), pide a cada tema de la sección su `tiles(user, procedure, ctx)` y su `context()` (el mismo que hoy), y renderiza: encabezado → camino → título → Hay/Falta → pendiente de la sección → tablero → detalles. Los detalles son los parciales de los temas, ya renderizados y ocultos. El navegador abre uno con `tablero.js`. El sondeo (`recorrido.js`) solo reemplaza tres bloques: las pestañas (`barra/`), el panel de avance (`ventana/`) y el indicador del encabezado (`avance/`); la foto y los mosaicos no se sondean.

### Tablero: mosaicos y detalle (REQ-126, REQ-127)

- **Contrato `Tile`** (`journey/tablero/tiles.py`): `key`, `title`, `detail` (id del detalle que abre, p. ej. `d-s3-ofertas`), `width` (1, 2 o 4 columnas), `tone` (`""` o `dark`), `big` (cifra grande) y `unit`, `sub` (línea de apoyo), `chart` (uno de los gráficos de abajo) y `missing` (texto «Falta …» o «Pendiente»). **Regla de REQ-141:** si el dato de un mosaico es `None`, la plantilla dibuja `missing` en lugar de `big` y `chart`; no existe un valor por omisión. Un test recorre todos los mosaicos con un procedimiento vacío y comprueba que ninguno muestra cifra.
- **Gráficos** (`charts.py` y `templates/journey/graficos/`, todos SVG con atributos de presentación, porque la política de contenido (`default-src 'self'`) y `test_no_external.py` prohíben `style=`): `Bars` (barras horizontales), `Donuts` (cumple / no cumple / no determinado / pendiente por oferta), `Lollipop` (orden económico con el estimado), `Timeline` (plazos), `Stack` (barra apilada por tipo), `Columns` (columnas chicas), `Heat` (tabla de calor por tipo y oferta). El ícono de estado sigue siendo el de la guía (círculo con símbolo y nombre al pasar el mouse o con el foco).
- **Detalle debajo de la fila:** el HTML trae los detalles ya renderizados, en una zona `.detalles`, cada uno `id="d-…"`. Cada mosaico es un `<a href="#d-…">` (sin JavaScript es un ancla a la zona de detalles, que queda visible). `tablero.js` detecta la fila del mosaico (las que comparten `offsetTop`), mueve el detalle después del último mosaico de esa fila y lo abre con una transición de `grid-template-rows` de 0,35 s; un clic en otro mosaico pliega el anterior; un clic en el mismo, lo pliega. Pone `role="button"`, `aria-expanded` y `aria-controls`, y abre el detalle que nombra `location.hash` (así funcionan las anclas que ya usan los enlaces de la 014, como `#s1-portal` o `#dictamen-subir`, y los redirigidos después de un POST: se abre el detalle que contiene el elemento con ese id). Varios mosaicos pueden abrir el mismo detalle (por ejemplo «Requisitos» y «Versiones de la matriz»). Un parámetro que hoy abre un modo del tema (`?oferta=`, `?ficha=`, `?historial=`) abre también su detalle: el tema declara `opens(request)`.
- **Los mosaicos de otra sección en el primer panel** (resultado por oferta, descartes, preguntas) **no repiten el detalle**: son enlaces a la sección con el detalle abierto (`evaluacion/#d-…`), con el pase de hoja. Así el contexto de la sección 4 (el más pesado) no se calcula dos veces. Es una diferencia con la maqueta (punto D-4).
- **Mosaicos agregados a los de la maqueta**, para que ninguna función de la 014 quede sin acceso (la maqueta no los dibuja): sección 1, «Datos del procedimiento», «Portal de Compras» y «Alta desde el pliego»; sección 3, «Circulares» y «Fichas de las ofertas»; sección 4, «Exportar»; sección 5, «Normas cargadas». Cada uno abre el parcial de su tema (punto D-5).

### Pendientes, camino y Hay/Falta (REQ-129, REQ-132)

- `Item` suma tres campos opcionales: `why` (por qué importa, texto que escribe el tema; sin texto no se dibuja la línea, nunca se inventa), `open` (id del detalle que abre la acción, para «subir», «responder», «decidir») y `post` (`(url, campos)` de una acción de un solo clic que ya existe como POST con `next` validado: hoy **aprobar** un ítem del Portal, `s1_portal` con `aprobar=item:<id>`). La acción de cada pendiente es entonces un botón que hace POST, o un enlace que abre el detalle donde está el formulario.
- `_pendientes.html` dibuja el pendiente general (primer panel, todos los ítems con el nombre de su sección) y el de cada sección. Cada fila: ícono, qué falta, por qué importa, sección y acción. Los renglones agrupados (`group_items`, más de 8 del mismo tipo) siguen agrupándose. Las **sugerencias del sistema** siguen en su bloque aparte (REQ-098), con el mismo estilo.
- Al aprobar desde el pendiente general vuelve a la misma pantalla (`next`); el ítem desaparece de las dos listas y baja el contador de la pestaña porque todo se recalcula en el servidor; quién y cuándo ya lo registra `approval.decide` (hecho de auditoría `portal_decision`).
- **Camino** (`_camino.html`): `Procedimientos` (`expedientes:index`) › procedimiento (el menú desplegable que hoy es `sel-proc`, con los otros procedimientos, «+ Nuevo procedimiento» y «Normativas») › sección. **Hay / Falta** (`_hay_falta.html`): «Hay» sale de `Section.summary` y «Falta» de `Section.tema_missing`, con la acción directa de cada faltante; ya se calculan hoy.
- Las pestañas muestran el contador de pendientes (`Section.pending`) y no el de sugerencias; sin pendientes, no se dibuja contador.

### Cambios de comportamiento (mínimos, necesarios para un criterio de la spec)

- **Dictamen del Portal.** El criterio de REQ-129 pide que al aprobar «el dictamen publicado en el Portal» baje el contador de **Evaluación**. Hoy ese ítem se cuenta como propuesta del Portal en la sección 1 y `s4_dictamen` lo lista solo como faltante. Se mueve: el ítem de tipo dictamen se cuenta como pendiente de la sección 4 (`s4_dictamen.status`) y se excluye de la cuenta de la sección 1 (`stages/portal.py` y `s1_portal._counts`). El total de pendientes del procedimiento no cambia. Se hace en un solo bloque (B-P) y se actualizan los tests de la 014 que contaban ese ítem en la sección 1.
- **Portada.** La ruta `expedientes/<id>/` redirige (302, con la consulta) a `expedientes/<id>/procedimiento/`, que pasa a ser el primer panel. Las anclas y los redireccionamientos de la 014 que apuntan a `procedimiento/` siguen funcionando.

## Temas, marca, tipografía y estilo (REQ-133, REQ-134, REQ-142)

- **Tokens.** La maqueta define los dos temas en `estilos.css`; el plan los lleva a `tokens.css` con los nombres de la maqueta (`--bg`, `--tile`, `--ink`, `--ink-2`, `--ink-3`, `--lime`, `--ok/--no/--nd/--pe/--ext`, etc.) y mantiene, hasta el cierre, los `--ev-*` viejos como alias de los nuevos para que las páginas que todavía no se migraron se lean bien en los dos temas. B8 quita los alias y un test prohíbe los `--ev-azul-*`, `--ev-beige-*`, `--ev-rojo*` y los colores en hexadecimal fuera de `tokens.css` (excepto `print.css`, que sigue siempre claro).
- **Contraste: la maqueta no alcanza AA en todos los pares** (cálculo del planificador, a confirmar con el test): `--ink-3` (`#8E8E8E`) da cerca de 3,3:1 sobre blanco y 3,0:1 sobre el mosaico gris (hace falta 4,5:1 para texto); en el tema negro `#6E7076` sobre `#0B0C0E` da cerca de 4,0:1; el ámbar `--nd` (`#C29A4F`) da cerca de 2,4:1 sobre el mosaico gris del tema claro (hace falta 3:1 para el ícono). La tarea B0.2 ajusta esos valores hasta que el test pase (decisión de implementación dentro del criterio numérico, no cambia la estética elegida). El texto secundario (`--ink-2`) sobre la foto del primer panel no alcanza 4,5:1 en el peor píxel: los datos del primer panel se dibujan con `--ink` y el test calcula el peor caso con el píxel más oscuro de la foto de la casa, a máxima opacidad.
- **Tipografía** (REQ-133 usa Hanken Grotesk; la maqueta la pide a `fonts.googleapis.com`, lo que P4 y P5 prohíben): se aloja en `evaluon/static/diseno/fuentes/` el woff2 variable (pesos 300 a 600 en uso) con los subconjuntos `latin` y `latin-ext`, y su `LICENCIA.txt` (SIL OFL 1.1; origen y huella anotados). Una persona la baja una vez (por ejemplo, del paquete Fontsource, que la publica con esa licencia); no se descarga en ejecución. El `@font-face` apunta solo a archivos locales y `test_sin_externos.py` falla si alguna plantilla, hoja de estilo, script o SVG nombra un dominio, `@import url(http…)` o `fonts.googleapis`. Se retira Barlow Condensed al cierre.
- **Marca (REQ-142).** Los cuatro SVG de `docs/diseno/marca/017/` (sus letras ya son formas; ningún `<text>`) se copian a `evaluon/static/marca/`: logotipo claro (placa EVALU negra y ON lima, para el tema gris y blanco), logotipo negro (placa EVALU gris y ON lima, para el tema negro) e isotipos. El encabezado dibuja los dos `<img>` y la hoja de estilo muestra el del tema (`[data-theme="negro"]`); el `<link rel="icon">` apunta al isotipo. `tests/journey/test_marca.py` se actualiza a los nombres nuevos. Los SVG viejos se quitan en B0.3 y el ingreso (`login.html`) usa el logotipo claro.
- **Selector (REQ-134).** `User.theme` (`claro` por omisión, `negro`). `base.html` escribe `data-theme="negro"` en `<html>` si corresponde. El selector son dos botones de un formulario (`POST accounts:tema`, con CSRF y `next` validado con `url_has_allowed_host_and_scheme`); vale desde cualquier equipo porque está en la base y funciona sin JavaScript. La página de ingreso y el usuario de lectura usan el mismo mecanismo; `without_actions` (que hoy quita los formularios de acción del usuario de lectura) deja pasar los formularios con la clase `preferencia`.
- **Estados de cumplimiento.** Los íconos siguen siendo círculo con símbolo y nombre al pasar el mouse o con el foco (`_icono.html`, `_sprite.html`); cambian solo sus colores (tokens `--ok`, `--no`, `--nd`, `--pe` por tema) y se verifican a 3:1.
- **Verde lima solo en resaltados** (REQ-133): pestaña activa, contadores, avance, lo más bajo y la acción principal en el tema negro. Un test busca `--lime` en las hojas de estilo y lo compara con una lista corta de selectores permitidos.

## Fotos (REQ-135 a REQ-138)

- **Modelo** (`accounts_photo`, ADR-0073): `user` (CASCADE), `slot` (0 a 9, única por usuario: es lo que hace valer el máximo de 10 aun con dos subidas a la vez), `content` (bytea), `sha256`, `width`, `height`, `size` (con restricción `size <= 2097152`), `created_at`.
- **Subida** (`photos.upload(user, file)`, un solo servicio llamado por la vista): rechaza lo que no sea JPEG, PNG o WebP según el contenido (no la extensión) y lo mayor de 10 MiB sin procesar (punto D-7); abre con Pillow con un tope de píxeles (rechaza bombas de descompresión); corrige la orientación EXIF; compone sobre blanco lo que tenga transparencia; pasa a luminancia; reduce a 1600 px de lado mayor sin ampliar; **ajusta el histograma al de la foto de la casa** (mapeo de histograma por tabla de 256 niveles, suavizada, en Python puro: así dos fotos distintas quedan con el mismo brillo medio y contraste, en blanco y negro); guarda como JPEG sin metadatos (se pierden los datos EXIF, incluida la ubicación), con calidad descendente hasta quedar por debajo de 2 MiB. Con 10 fotos pide quitar una antes. El histograma de referencia se calcula una vez desde `evaluon/static/diseno/casa/biblioratos-bn.jpg`.
- **Elección** (`photos.pick_for(request)`): al armar el primer panel elige al azar entre las fotos del usuario (o la de la casa si no tiene) y evita repetir la anterior si tiene más de una (la guarda en la sesión). La foto se elige al **servir la página**, no en el navegador: los sondeos no la tocan, así que no cambia mientras se está en la pantalla.
- **Servido** (`accounts:foto`): `get_object_or_404(Photo, pk, user=request.user)`; otro usuario recibe 404, sin sesión va al ingreso (`LoginRequiredMiddleware`). `Cache-Control: private`, ETag con la huella. Las fotos no tienen ninguna otra salida: ninguna etapa externa (ADR-0065, ADR-0067) las lee.
- **Mis fotos** (`/perfil/fotos/`, desde el menú de usuario): hasta 10 ranuras, subir, ver y quitar (borrado real, a pedido de su dueño). La comparación «como la subió / como se ve» de la maqueta **no se hace** (exigiría guardar el original, que además es un dato privado más; punto D-6).
- **Primer panel** (REQ-135): la foto es la capa de fondo del panel (`<img>` en un contenedor absoluto al 60 % del ancho, con máscara de degradado a la izquierda y opacidad baja), con una animación de entrada de 0,9 s (fundido con leve escala); con «reducir movimiento», un fundido de 0,3 s. Un texto «Foto de la casa» o «Foto de su perfil» lo identifica.
- **Qué impide que entren al repositorio o a las pruebas** (ADR-0073): no hay carpeta de fotos; la base vive en el volumen `pgdata` y el respaldo (`backups/`) está en `.gitignore`; B0.1 agrega `*.dump` al `.gitignore`; `tests/test_sin_fotos_en_el_repositorio.py` falla si hay archivos de imagen fuera de la lista permitida (`evaluon/static/diseno/casa/`, `evaluon/static/marca/`) y verifica que `.gitignore` cubra `backups/`, `pgdata/` y `*.dump`; los tests de fotos generan sus imágenes en memoria con Pillow.

## Pase de página (REQ-139)

`@view-transition { navigation: auto; }` en `pase.css`. El `<main>` lleva `view-transition-name: hoja`, el encabezado `cabecera` (queda quieto) y la pestaña activa `pildora` (el navegador la desliza de una pestaña a la otra). `::view-transition-old(hoja)` gira sobre su borde izquierdo (`rotateY` hasta -90° con perspectiva y sombra) en 0,44 s; hacia atrás entra la nueva. La dirección la fija `pase.js` (unas 15 líneas, en el evento `pagereveal`: compara la posición de la pestaña de la página anterior con la actual); sin el script, el pase funciona en una sola dirección. `@media (prefers-reduced-motion: reduce)`: fundido de 0,15 s. Es una mejora progresiva: Chrome y Edge 126 o posterior y Safari 18.2 o posterior la muestran; Firefox no la implementa (consulta del 2026-10-21, ADR-0075) y navega como siempre. El tablero tiene que estar listo en menos de 4 s para que Chrome no cancele la transición.

## Avance de los procesos largos (REQ-140)

- **Lo que ya existe:** `progress_of(job)` (`done`, `total`, `percent`, `detail_done`, `detail_total`, `recent`) y `window_for(procedure)` (estado, tarea, paso, hechos y faltantes, últimos pasos). Los pedidos de evaluar ofertas y fichas reportan el avance fino (oferta x de y; requisito x de y); proponer la matriz, leer un documento y explorar el Portal reportan el paso y el tiempo, no un total.
- **Panel** (`_window.html`, en el primer panel, sondeado por `ventana/`): porcentaje grande, «oferta 2 de 3 · requisito 14 de 23», barra con acento lima y los **últimos 3 pasos** (hoy llegan hasta 8; la plantilla muestra 3), en lenguaje llano. Estados terminado, falló y espera se conservan.
- **Indicador del encabezado** (`_avance_encabezado.html`, vista nueva `journey/views/avance.py`, ruta `expedientes/<id>/avance/`): anillo SVG con el porcentaje, enlazado al primer panel; solo se dibuja con un pedido en espera o en curso; se actualiza con el mismo sondeo (5 s, dentro de los 10 s de REQ-067). Está en todas las páginas de un procedimiento.
- **Porcentaje global.** El de hoy (`main.percent`) cuenta solo ofertas terminadas, así que no se mueve durante toda la primera oferta. `window.py` suma `overall_percent`: `(ofertas hechas + requisitos hechos / requisitos de la oferta en curso) / ofertas`, tope 99 mientras corre. Los pedidos sin total (matriz, lectura, Portal) muestran paso, tiempo y una barra indeterminada, sin porcentaje inventado (punto D-10).

## Rutas

| Ruta | Cambio |
|---|---|
| `expedientes/<id>/` | Redirige a `procedimiento/` conservando la consulta |
| `expedientes/<id>/procedimiento/` | Primer panel (ingreso del procedimiento y tablero de la sección 1) |
| `expedientes/<id>/pliego/`, `ofertas/`, `evaluacion/`, `normativas/` | Igual que hoy, con tablero |
| `expedientes/<id>/barra/`, `ventana/` | Igual (fragmentos del sondeo) |
| `expedientes/<id>/avance/` | Nueva: indicador del encabezado |
| `perfil/fotos/` (GET y POST), `perfil/fotos/<id>/` (GET), `perfil/fotos/<id>/quitar/` (POST) | Nuevas (`accounts:fotos`, `accounts:foto`, `accounts:foto_quitar`) |
| `perfil/tema/` (POST) | Nueva (`accounts:tema`) |

## De dónde sale cada dato

Leyenda: **sí** = existe hoy en el modelo; **calculable** = se deriva de datos que existen, sin guardar nada nuevo; **no** = no existe (ver la tabla siguiente).

### Primer panel (sección Procedimiento)

| Mosaico o dato | Fuente | Existe |
|---|---|---|
| Objeto, tipo y número, fecha de autorización | `tenders.Procedure` (`subject`, `procedure_type`, `number`, `authorization_date`) | sí |
| Expediente | `PortalProcedureData.file_number` (también lo escribe el alta desde el pliego) | sí; «Falta» si no se cargó |
| Monto estimado | — | **no** (ADR-0077) |
| Cantidad de ofertas | `Offer` del procedimiento | sí |
| La más baja | `assessment.ordering.economic_order(...)` sobre `PortalOfferData.total` | sí si el acta del Portal trae los totales; si no, «Falta» |
| Avance | — | **no está definido** (ADR-0077: secciones listas de cinco) |
| Días hasta el vencimiento del mantenimiento | Plazo del Portal (`mantenimiento_oferta`, hoy solo en la página guardada) + apertura del cronograma | **calculable** (ADR-0077) |
| Cantidad de pendientes | `Overview.pending` | sí |
| Pendiente general | `Section.pending_items` de las cinco secciones | sí; «por qué importa» **no** (se agrega `Item.why`) |
| Orden económico (lollipop y detalle) | `economic_order` (de menor a mayor, empates con la misma posición) | sí; diferencia con el estimado **no** hasta tener el estimado; diferencia con la más baja, calculable |
| Plazos importantes | Cronograma del Portal (`PortalProcedureData.schedule`, `s1_datos._schedule`/`_opening`) para la apertura; hoy; vencimiento del mantenimiento (calculable); dictamen (`s4_dictamen`: fecha del documento o del Portal) | apertura sí; vencimiento calculable; dictamen **no tiene fecha prevista** (se muestra «Pendiente» hasta que hay uno) |
| Avance de procesos largos | `window_for` / `progress_of` | sí |
| Resultado por oferta, Descartes propuestos, Preguntas | `memo.matrix_page` (`by_outcome`), `s4_descartes.service.units`, `open_questions` | sí; enlazan a la sección 4 |
| Avance por sección (detalle: Hay/Falta de las cinco) | `Section.summary`, `Section.tema_missing`, estado de la sección | sí |
| Datos del procedimiento (renglones, garantías, cronograma) | `s1_datos.context` | sí |
| Portal de Compras (sin aprobar, novedades) | `s1_portal.status` (`_counts`) | sí |
| Alta desde el pliego (borradores) | `tenders_procedure_draft` (`s1_pliego`) | sí |

### Pliego y matriz

| Mosaico | Fuente | Existe |
|---|---|---|
| Requisitos (cantidad, versión, cambios por revisar) | `s2_matriz.context` (`total`, `summary.changed`, `version`) | sí |
| Documentos del pliego («3 de 4») | `s2_documentos` (cargados) más ítems del Portal sin tomar | calculable; el «de 4» solo existe si el Portal los lista |
| Versiones de la matriz | `s2_matriz._versions` | sí |
| Cumplimiento por tipo y oferta | `memo.matrix_page` (celdas por clase de requisito) | sí si hay evaluación; si no, «Pendiente»; enlaza a la sección 4 |

### Ofertas

| Mosaico | Fuente | Existe |
|---|---|---|
| Ofertas del acta (cantidad, columnas con el total) | `s3_ofertas.offers_of`, `PortalOfferData.total` | sí; sin totales, solo la cantidad |
| La más baja y Orden económico | `tablero/economico.py` sobre `economic_order` | sí (diferencia con el estimado: **no**, ADR-0077) |
| Hojas de compliance («1 de 3») | `s3_anexos.offer_block` (hoja presente) | sí |
| Documentación de las ofertas («23 de 27») | Cantidad de documentos por oferta (`own_current`) | cantidad **sí**; el denominador («de 9») **no existe**: se muestra la cantidad por oferta y los faltantes que el sistema sí conoce (hoja de compliance, anexos) |
| Circulares | `s3_circulares.status/context` | sí |
| Fichas de las ofertas | `s3_ficha.status/context` | sí |

### Evaluación y dictamen

| Mosaico | Fuente | Existe |
|---|---|---|
| Resultado por oferta | `s4_descartes._results` / `s4_propuesta` (`by_outcome`) | sí si hay evaluación |
| Informe técnico | `s4_informe.context` (documentos, estado de lectura, apto o no apto) y `Reading.pages`; durante la lectura, `progress_of` | estado sí; «9 de 16 págs.» solo cuando la lectura terminó o el pedido reporta páginas |
| Dictamen | `s4_dictamen.context` (ítem del Portal o documento `dictamen`) | sí; «Pendiente» si no hay |
| Descartes propuestos, Preguntas | `s4_descartes`, `s4_preguntas` | sí |
| No cumple, No determinado (cifras) | `by_outcome` | sí |
| Exportar | `s4_exportar` | sí |

### Normativas

| Mosaico | Fuente | Existe |
|---|---|---|
| Normas que rigen («4 de 6») | `s5_rigen.rows` (validada / sin validar / falta) | sí |
| Citas del pliego («14 de 15») | `s5_rigen._cited` (normas distintas citadas en el encuadre legal) | **parcial**: normas distintas citadas, no menciones en el texto del pliego |
| Régimen que rige | `applicable_regimes(authorization_date)` | sí |
| Consulta de normativa | `s5_consulta` | sí |
| Normas cargadas | `s5_normas` | sí |

## Datos que faltan hoy y cómo se resuelve cada uno

| Dato que usa la maqueta | Qué hay hoy | Propuesta | Decisión |
|---|---|---|---|
| **Monto estimado** | Nada: ni el Portal (la página no lo trae) ni el modelo lo guardan | Mostrar «Falta» mientras no exista. Para que exista: el evaluador lo carga desde el pliego, con documento y cita literal de respaldo, quién y cuándo (tabla de solo inserción `tenders_procedure_estimate`, un formulario chico en el detalle de «Datos del procedimiento», hecho de auditoría `procedure` con `action=monto_estimado`) | ADR-0077, punto D-1: **necesita respuesta del responsable** |
| **Diferencia de cada oferta con el estimado** | Depende del monto estimado | Se calcula cuando hay estimado; sin él, solo la diferencia con la más baja y «Falta el monto estimado» | ADR-0077 |
| **Vencimiento del mantenimiento y «faltan N días»** | El parser lee `mantenimiento_oferta` («60 Días corridos Acto de apertura») pero el procedimiento no lo guarda; la página del Portal sí queda guardada (`PortalPage.content`, con enlace y fecha) | Se lee al vuelo desde la última página guardada del proceso (`parse_page`), se suma al día de apertura del cronograma si el plazo es en días corridos y se muestra con «Fuente: Portal, tomado el …». En días hábiles (no hay calendario de feriados): «N días hábiles desde la apertura» y «Falta el calendario» | ADR-0077 |
| **Avance (76 %) y avance por sección (barras)** | No hay una medida; hay estado y cuentas por sección | Avance = secciones en estado «lista» de las cinco («2 de 5 secciones listas»). El mosaico «Avance por sección» muestra el estado de cada una (ícono) con sus pendientes y faltantes, sin porcentajes inventados | ADR-0077, punto D-2 |
| **Por qué importa cada pendiente** | `Item` no lo trae | Campo `why`, escrito por cada tema solo donde se sabe el motivo | Plan |
| **Fecha del dictamen de la Comisión (plazos)** | No hay fecha prevista; el dictamen publicado trae fecha cuando existe | «Pendiente» hasta que hay uno; después, su fecha | Plan |
| **Denominador de documentos de cada oferta («de 9»)** | No existe qué documentos debe presentar cada oferta | Cantidad por oferta y faltantes conocidos | ADR-0077 |
| **Páginas del informe técnico («9 de 16»)** | Solo al terminar la lectura, o del pedido en curso | Estado de lectura y páginas cuando se conocen | Plan |
| **Menciones del pliego a normas («15 citas»)** | Normas distintas del encuadre legal | «N normas citadas · M cargadas» | Plan |

## Modelo de datos

Todo el esquema lo toca **una sola tarea, B0.1**, para que ningún otro bloque genere migraciones.

| Cambio | Para qué | REQ |
|---|---|---|
| `accounts_user.theme` (texto, `claro` o `negro`, por omisión `claro`, con restricción de valores) | Tema guardado en el perfil | REQ-134 |
| `accounts_photo` (nueva, descrita en «Fotos») con restricciones: `slot` entre 0 y 9, única `(user, slot)`, `size` ≤ 2.097.152 | Fotos personales | REQ-136, REQ-137 |
| `tenders_procedure_estimate` (nueva, solo inserta, con disparadores contra `UPDATE` y `DELETE` como `tenders_document_change`): procedimiento, importe, moneda, documento y cita de respaldo, usuario, momento. **Solo si el responsable aprueba el punto D-1** | Monto estimado con fundamento | REQ-128, REQ-130 |

Migraciones reversibles (`accounts/0003_tema_y_fotos.py`; `tenders/00NN_monto_estimado.py` si corresponde). Los usuarios existentes quedan con tema `claro` y sin fotos. Sin cambios en el esquema de ofertas, evaluación, Portal ni auditoría.

## Flujo de IA

No usa IA. La normalización de fotos es procesamiento de imagen local con Pillow; ningún dato del tablero lo calcula un modelo, y por lo tanto ninguna eval aplica (P7). Todo lo que el tablero muestra con fundamento (dato del Portal, cita del pliego, respuesta de la Comisión) lo trae del tema que lo produjo, con su cita (REQ-141, P3).

## Registro de auditoría

- **Aprobar desde el pendiente** (REQ-129): `approval.decide` registra quién, cuándo y qué (`portal_decision`), igual que hoy. Es una prueba del test de REQ-129.
- **Monto estimado** (si se aprueba D-1): hecho `procedure` con `action=monto_estimado`, importe, moneda, documento, cita, usuario y momento (P3, P6).
- **Tema y fotos: no se registran** en la auditoría de evaluaciones. Son preferencias de la persona, no intervienen en ninguna evaluación (P6 pide reconstruir por qué el sistema dijo lo que dijo) y registrar sus fotos sería guardar un dato privado más. La base conserva la huella, el tamaño y la fecha de cada foto.
- **Rechazos por rol:** sin cambios; el usuario de lectura puede cambiar su tema y sus fotos, pero ninguna acción de decisión (el botón no se dibuja y el servicio igual lo rechaza).

## Cobertura de requisitos

| Requisito | Cómo se resuelve | Cómo se verifica |
|---|---|---|
| REQ-126 | Contrato `Tile`, `_tablero.html` en las cinco secciones; un `tiles()` por tema (B0.4, B2 a B6); cada tema tiene al menos un mosaico | `tests/journey/test_tablero_secciones.py`: cada sección abre con su tablero y cada mosaico tiene un detalle existente con id único; revisión visual |
| REQ-127 | `tablero.js` y `tablero.css`: detalle bajo la fila, uno abierto, transición de 0,35 s | Test del HTML (mosaico ↔ detalle, `aria-controls`) y de la duración en el CSS (≤ 0,4 s); revisión en el navegador con «Ofertas del acta» |
| REQ-128 | `_ingreso.html`, `tablero/ingreso.py`, foto de fondo, `economico.py`, plazos; sin mosaicos ni datos de normativa | `tests/journey/test_primer_panel.py`: datos, pendiente general, orden y plazos presentes; ningún dato de normativa (régimen, normas); revisión a 1440 × 900 |
| REQ-129 | `Item.why/open/post`, `_pendientes.html`, bloque B-P (dictamen en Evaluación) | `tests/journey/test_pendientes.py`: aprobar el dictamen desde el pendiente general lo quita de las dos listas, baja el contador en uno y deja el hecho de auditoría con usuario y momento |
| REQ-130 | `tablero/economico.py` (ordena, diferencia con el más bajo y con el estimado), mosaico y detalle | Test con tres ofertas: orden, la más baja marcada, porcentajes; sin estimado, «Falta el monto estimado» |
| REQ-131 | `ingreso.py` (`Timeline`: apertura, hoy, vencimiento, dictamen) | Test con apertura del 22/09/2026, 60 días corridos y hoy 21/10/2026: «21/11 · vence el mantenimiento de las ofertas» y «faltan 31 días»; con días hábiles, «Falta el calendario» |
| REQ-132 | `_camino.html`, `_hay_falta.html`, contadores en las pestañas | `test_camino.py`: recorrido y línea «Hay … Falta …» en las cinco secciones y en la portada; contador por pestaña |
| REQ-133 | `tokens.css`, `secciones.css`, `tablero.css`, guía visual nueva | `test_contraste.py` (100 % AA en los dos temas); test del verde lima; revisión visual de las cinco secciones en los dos temas |
| REQ-134 | `User.theme`, `accounts:tema`, `<html data-theme>`, selector | `test_tema.py`: elegir negro, entrar con otro cliente y ver `data-theme="negro"`; inicio en claro; valor inválido rechazado; `next` externo rechazado |
| REQ-135 | Contenedor de foto del primer panel, 60 % del ancho, máscara y opacidad | Test de contraste del peor caso sobre la foto; test de que solo el primer panel trae la foto; revisión visual |
| REQ-136 | Modelo `Photo`, `photos.py`, `views_fotos.py`, «Mis fotos», foto de la casa por omisión | `tests/accounts/test_fotos.py` y `test_fotos_privadas.py`: la 11.ª se rechaza; otro usuario recibe 404; sin fotos propias se usa la de la casa |
| REQ-137 | Normalización por histograma de referencia | Dos imágenes sintéticas (oscura y saturada; clara y fría): blanco y negro, diferencia de brillo medio y de contraste ≤ 10 % |
| REQ-138 | `pick_for` al servir la página; sin repetir la anterior | Test: con 3 fotos, pedidos sucesivos del primer panel eligen distinto; la página no trae script que cambie la foto |
| REQ-139 | `pase.css`, `pase.js` | Test de `@view-transition`, duraciones (≤ 0,5 s; ≤ 0,15 s con reducir movimiento) y de `view-transition-name`; revisión en Edge |
| REQ-140 | `window.py` (`overall_percent`), `_window.html`, `_avance_encabezado.html`, `views/avance.py` | `test_avance_encabezado.py`: con una evaluación en curso, el encabezado de cualquier sección muestra el porcentaje y el primer panel, dónde va y los últimos 3 pasos; intervalo ≤ 10 s |
| REQ-141 | Regla de `Tile` (`None` → «Falta» o «Pendiente») y los tests de cada tema | `test_sin_inventos.py`: procedimiento vacío, sin dictamen, sin estimado, sin ofertas: ninguna cifra inventada; el mosaico de Evaluación dice «Pendiente» |
| REQ-142 | SVG de la marca 017 en `static/marca/`, `<img>` por tema, isotipo en la pestaña | `test_marca.py` actualizado (archivos, sin `<text>`, versión por tema, contraste de las letras sobre su placa); revisión visual de los dos temas |

## Verificación contra la constitución

| Principio | Cumple | Nota |
|---|---|---|
| P1 La spec es la fuente | sí | Cada bloque nombra sus REQ; los vacíos de la spec están en «Puntos donde la spec no alcanza» |
| P2 Trazabilidad | sí | Tabla de cobertura; `tasks.md` asociará REQ a cada tarea |
| P3 El sistema recomienda, la Comisión decide | sí | El tablero solo muestra; lo que no existe se muestra como «Falta»; los datos con fundamento (Portal, cita) lo conservan; el monto estimado, si se carga, lo carga una persona con su cita; aprobar desde el pendiente sigue siendo del evaluador o el operador según el ítem |
| P4 Datos | sí | Fotos solo en la base local, por usuario, nunca en el repositorio, en pruebas ni en un servicio externo; tipografía y foto de la casa en el equipo; test contra direcciones externas |
| P5 Local y reproducible | sí | Sin servicios nuevos ni dependencias nuevas; el entorno se levanta igual; la imagen se reconstruye por los estáticos |
| P6 Auditoría | sí | Lo que decide una persona deja su hecho; tema y fotos no son evaluación (ver «Registro») |
| P7 Evals | sí (no aplica) | No cambia recuperación, instrucciones ni modelo |
| P10 Simplicidad | sí | Sin marco de interfaz; dos scripts chicos; una columna y una tabla de fotos; la tabla del estimado solo si el responsable la aprueba; no se hace la comparación «como la subió», ni mosaicos que ningún requisito pide |
| P11 Compuertas | sí | Plan y ADR esperan la aprobación del responsable; los ADR nacen «propuesto» |

## Decisiones

Cinco ADR, todos «propuesto»: 0073 (dónde y cómo se guardan las fotos), 0074 (cómo se guarda y se aplica el tema), 0075 (cómo se hace el pase de página), 0076 (cómo se construye el tablero sin marco de interfaz) y 0077 (qué hacer con los datos que el sistema no tiene).

## Corte vertical y orden de trabajo

**Corte vertical (ADR-0025):** la base común más **un solo tablero, el de Ofertas**, con el detalle «Ofertas del acta» (el caso del criterio de REQ-127), el orden económico, el selector de tema, el pase de hoja y el logotipo de los dos temas, con el caso chico (público). Se mide una vez: contraste de los pares declarados, el tablero de Ofertas en menos de 2 s con el caso chico, el detalle en 0,4 s, y la revisión visual del Coordinador en Edge en los dos temas. Recién entonces se lanzan los demás tableros.

Los bloques no son tareas: `tasks.md` los partirá en tareas de una sesión. «Archivos» es lo que escribe cada bloque; ningún archivo aparece en dos bloques que puedan correr a la vez.

| Bloque | Qué entrega | Depende de | Archivos que escribe |
|---|---|---|---|
| **B0.1 Esquema y perfil** | `User.theme`, `Photo`, `photos.py` con `pick_for` (por ahora solo la foto de la casa), foto de la casa en estáticos con sus créditos, `.gitignore` | — | `evaluon/accounts/models.py`, `evaluon/accounts/migrations/0003_tema_y_fotos.py`, `evaluon/accounts/photos.py`, `evaluon/static/diseno/casa/*`, `.gitignore`, `tests/accounts/test_models_perfil.py`, `tests/test_sin_fotos_en_el_repositorio.py`; con D-1 aprobado: `evaluon/tenders/models.py`, `evaluon/tenders/migrations/00NN_monto_estimado.py` |
| **B0.2 Tokens, tipografía y marca** | Dos temas en `tokens.css` con los alias viejos, fuente alojada, los cuatro SVG de la marca (sin quitar los viejos), `evaluon.css`, `recorrido.css` y `punto.css` leídos en los dos temas, guía visual, test de contraste y de direcciones externas | — (en paralelo con B0.1) | `evaluon/static/diseno/tokens.css`, `evaluon/static/diseno/fuentes/*`, `evaluon/static/marca/*` (agrega), `evaluon/static/css/evaluon.css`, `evaluon/static/journey/recorrido.css`, `evaluon/static/journey/punto.css`, `docs/diseno/guia-visual.md`, `tests/journey/test_contraste.py`, `tests/test_sin_externos.py` |
| **B0.3 Encabezado, tema y pase** | `base.html` con tema, encabezado nuevo con camino, pestañas en píldora, selector y menú de usuario, vista del tema, portada que redirige, vista `avance` mínima, `pase.css/js`, ingreso con el logotipo nuevo; se quitan los SVG viejos | B0.1, B0.2 | `evaluon/templates/base.html`, `evaluon/templates/journey/_cabecera.html`, `_encabezado.html`, `_barra.html`, `_barra_nueva.html`, `_icono.html`, `_sprite.html`, `_camino.html`, `_hay_falta.html`, `_selector_tema.html`, `_menu_usuario.html`, `_avance_encabezado.html`, `evaluon/templates/accounts/login.html`, `evaluon/static/journey/secciones.css`, `pase.css`, `pase.js`, `evaluon/accounts/urls.py`, `evaluon/accounts/views_perfil.py`, `evaluon/journey/views/portada.py`, `views/avance.py`, `evaluon/journey/urls.py`, `evaluon/journey/context.py`, `tests/journey/test_marca.py`, `test_tema.py`, `test_pase.py`, `test_camino.py` y los tests de la 014 que miran el encabezado (`test_redirects.py`, `test_sections.py`, `test_angosto.py`, `test_normativas_general.py`) |
| **B0.4 Componente de tablero y corte vertical** | `Tile`, gráficos SVG, `_tablero.html`, `_mosaico.html`, `tablero.js/css`, cuerpo común `seccion*.html`, y el tablero de Ofertas con el orden económico | B0.3 | `evaluon/journey/tablero/{__init__,tiles,charts,economico}.py`, `evaluon/templates/journey/_tablero.html`, `_mosaico.html`, `graficos/*`, `_economico.html`, `seccion.html`, `seccion_base.html`, `evaluon/static/journey/tablero.css`, `tablero.js`, `evaluon/journey/sections/base.py` (`Section.tiles`), `evaluon/journey/sections/s3.py`, `evaluon/journey/views/portada.py` (la vista `seccion`), `evaluon/journey/temas/s3_ofertas.py` (`tiles`), `tests/journey/test_tablero_*.py`, `test_sin_inventos.py` |
| **Medición del corte** | Contraste, 2 s, 0,4 s, revisión visual en los dos temas; hallazgos en una sola tarea | B0.4 | `specs/017-tableros-y-estetica/verificacion/*` |
| **B-P Pendientes con acción a mano** | `Item.why/open/post`, `_pendientes.html` (reemplaza `_paneles.html`), ítems del Portal uno por uno con «Aprobar», dictamen en Evaluación | B0.4 | `evaluon/journey/sections/base.py`, `evaluon/templates/journey/_pendientes.html`, `_paneles.html` (se retira), `evaluon/journey/stages/portal.py`, `evaluon/journey/temas/s1_portal.py` (solo `status` y `_counts`), `evaluon/journey/temas/s4_dictamen.py` (solo `status`), `tests/journey/test_pendientes.py` y los tests de la 014 que cuentan el dictamen |
| **B1 Fotos** | Normalización, subida, baja, elección, servido y «Mis fotos» | B0.3 (comparte `accounts/urls.py`) | `evaluon/accounts/photos.py`, `evaluon/accounts/views_fotos.py`, `evaluon/accounts/urls.py`, `evaluon/templates/accounts/fotos.html`, `evaluon/static/accounts/fotos.css`, `tests/accounts/test_fotos.py`, `test_fotos_privadas.py` |
| **B2 Primer panel** | Hero con foto, datos principales, plazos, orden económico, avance por sección, mosaicos de la sección 1, listado de procedimientos y alta | B0.4, B-P | `evaluon/templates/journey/_ingreso.html`, `expedientes.html`, `nuevo.html`, `s1_pliego_borrador.html`, `evaluon/templates/journey/temas/s1_*.html`, `_s1_*.html`, `evaluon/journey/tablero/ingreso.py`, `evaluon/journey/temas/s1_datos.py`, `s1_pliego.py`, `s1_portal.py` (`tiles`), `evaluon/journey/sections/s1.py`, `evaluon/static/journey/ingreso.css`, `s1.css`, `s1_pliego.css`, `tests/journey/test_primer_panel.py`; con D-1 aprobado: `evaluon/tenders/services/estimate.py` |
| **B3 Pliego y matriz** | Tablero de la sección 2 | B0.4 | `evaluon/journey/temas/s2_*.py`, `evaluon/journey/sections/s2.py`, `evaluon/templates/journey/temas/s2_*.html`, `evaluon/static/journey/s2*.css`, `evaluon/static/tenders/matrix.css`, `tests/journey/temas/test_s2_*.py` |
| **B4 Ofertas** | Resto del tablero de la sección 3 | B0.4 | `evaluon/journey/temas/s3_anexos.py`, `s3_circulares.py`, `s3_ficha.py`, `s3_ofertas.py` (resto), `evaluon/templates/journey/temas/s3_*.html`, `_s3_*.html`, `evaluon/static/journey/s3*.css`, `s3_*.js`, `tests/journey/temas/test_s3_*.py` |
| **B5 Evaluación y dictamen** | Tablero de la sección 4 | B0.4, B-P | `evaluon/journey/temas/s4_*.py`, `evaluon/journey/sections/s4.py`, `evaluon/templates/journey/temas/s4_*.html`, `_s4_*.html`, `evaluon/static/journey/s4*.css`, `tests/journey/temas/test_s4_*.py` |
| **B6 Normativas** | Tablero de la sección 5 y página general de normativas | B0.4 | `evaluon/journey/temas/s5_*.py`, `evaluon/journey/sections/s5.py`, `evaluon/templates/journey/temas/s5_*.html`, `evaluon/templates/journey/normativas.html`, `evaluon/static/journey/s5*.css`, `tests/journey/temas/test_s5_*.py`, `test_normativas_general.py` |
| **B7 Avance de procesos largos** | `overall_percent`, panel y encabezado con la estética nueva | B0.4 | `evaluon/journey/window.py`, `evaluon/journey/views/avance.py`, `evaluon/templates/journey/_window.html`, `_avance_encabezado.html`, `evaluon/static/journey/avance.css`, `tests/journey/test_window.py`, `test_avance_encabezado.py` |
| **B8 Cierre** | Quita alias y colores sueltos, retira Barlow y la marca vieja, guía visual final, runbook de despliegue, medición de 2 s con el procedimiento real, revisión visual de las cinco secciones en los dos temas | B1 a B7 | `evaluon/static/diseno/tokens.css`, `evaluon/static/diseno/fuentes/barlow-*`, `evaluon/static/journey/recorrido.css` (resto), `docs/diseno/guia-visual.md`, `specs/017-tableros-y-estetica/entorno.md`, `specs/017-tableros-y-estetica/verificacion/*`, test final de colores y de tokens viejos |

**Paralelismo.** Terminada B0.4 y su medición, pueden correr a la vez B-P, B1, B3, B4, B6 y B7 (archivos disjuntos). B2 y B5 esperan a B-P porque comparten `s1_portal.py` y `s4_dictamen.py`. B1 solo debe ir después de B0.3 por `accounts/urls.py`. B0.1 y B0.2 corren juntas. **Esquema, `tokens.css`, `base.html`, `secciones.css`, `urls.py` y `sections/base.py` los toca un solo bloque por vez** (B0.1, B0.2, B0.3, B0.4/B-P y B8). Los bloques usan solo las fixtures existentes; si necesitan una nueva, la agregan en su propio archivo de tests.

**Cada bloque deja el repositorio funcionando**: los alias de los tokens viejos y la coexistencia de las plantillas viejas hasta que cada sección se migra garantizan que ninguna página queda rota entre bloques.

## Estáticos y despliegue

- WhiteNoise sirve lo que `collectstatic` reunió al construir la imagen: tras cambiar estáticos, 8000 necesita `docker compose build app` y `docker compose up -d`. Lo mismo para los SVG de la marca, la tipografía y la foto de la casa. Los tests leen `evaluon/static` con `finders`, así que no lo necesitan.
- Las migraciones (`accounts` y, si corresponde, `tenders`) exigen el procedimiento de `migrate_on_start.sh` con base con datos: detener `app`, respaldar con `pg_dump` a `backups/` (ya en `.gitignore`), aplicar `migrate` y levantar todo. B8 lo deja en `specs/017-tableros-y-estetica/entorno.md`.
- Raíz de la instancia siempre en `main` (8000 monta `./evaluon`); la integración se hace en un árbol aparte.
- El clon de la 016 (`scripts/clon.sh`) copia la base con las fotos: queda en el equipo y no entra en ningún pedido externo.

## Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Render de las cinco secciones supera 2 s (los contextos de los temas ya se calculan hoy; ahora se suman los mosaicos y los gráficos) | Criterio numérico incumplido | `tiles()` usa los `context()` ya calculados y `memo`; los mosaicos de otra sección solo enlazan; el indicador y las pestañas son fragmentos aparte; se mide con el caso chico en cada bloque y con el real una vez (B8); dos rondas |
| La paleta de la maqueta no alcanza AA en algunos pares | Criterio numérico incumplido | El test de contraste corre en B0.2; se ajustan `--ink-3`, `--nd` y similares; la estética elegida no cambia |
| Texto del primer panel ilegible sobre una foto oscura | Contraste incumplido (REQ-135) | Datos con `--ink`, máscara y opacidad de la foto; el test usa el peor píxel; la normalización ajusta al histograma de la foto de la casa |
| El pase de hoja no funciona en Firefox | REQ-139 solo se ve en Chrome, Edge y Safari | Mejora progresiva (ADR-0075); el navegador de verificación del proyecto es Edge; si la Comisión usa otro, se cambia a transición con JavaScript (ADR-0075, alternativa B) |
| Una transición entre páginas retrasa la navegación hasta que carga el destino | Pantalla lenta al cambiar de sección | Chrome cancela a los 4 s; el tablero se mide a 2 s; el pase usa solo `transform` y `opacity` |
| Los formularios de acción se quitan al usuario de lectura (`without_actions`) y se llevarían el selector de tema | El usuario de lectura no puede cambiar el tema | Clase `preferencia` exceptuada en `without_actions` y test |
| Anclas de la 014 apuntan a elementos dentro de detalles cerrados | Un enlace «Subir archivo» no muestra nada | `tablero.js` abre el detalle que contiene el id del hash; test del HTML (cada ancla usada por un enlace existe dentro de un detalle) |
| Tests de la 014 que miran el HTML del encabezado, las pestañas o el dictamen | Rojo de regresión | Cada bloque actualiza en su propia tarea los tests que su cambio rompe (lista en la tabla de bloques); la suite completa se corre una vez por tanda sobre la rama combinada |
| Una foto personal llega al repositorio | Incumple P4 | No hay carpeta de fotos; `.gitignore` y test de archivos de imagen; los tests generan imágenes en memoria |
| Foto con metadatos (ubicación) | Fuga de datos personales | La normalización re-codifica sin metadatos; test de que el JPEG guardado no trae EXIF |
| Foto muy grande o malformada | Consumo de memoria o falla | Tope de 10 MiB y de píxeles; error claro al usuario; test con imagen corrupta |
| Plazo de mantenimiento «en días hábiles» sin calendario de feriados | No se puede calcular el vencimiento | Se muestra el plazo y «Falta el calendario»; nunca una fecha supuesta (REQ-141) |
| Leer la página guardada del Portal en cada carga para el plazo de mantenimiento es lento | Presiona el criterio de 2 s | `memo` por pedido; se mide en B2; si pasa de unos 150 ms, se guarda el dato en `portal_procedure_data` al explorar (ADR-0077, alternativa B), con su migración en un bloque de esquema aparte |
| Las pantallas viejas de `tenders/` y `queries/` no se migran a mosaicos | Dos estéticas | Se leen bien en los dos temas por los tokens; no son parte de las cinco secciones (spec: REQ-126); B8 las revisa por contraste |

## Puntos donde la spec no alcanza (con recomendación)

| # | Punto | Recomendación |
|---|---|---|
| D-1 | **Monto estimado:** REQ-128 y REQ-130 lo piden, pero no existe en el Portal ni en el modelo, y la spec no dice de dónde sale | Que lo cargue el evaluador desde el pliego con documento y cita, quién y cuándo (tabla chica de solo inserción). Sin esto, el mosaico dice «Falta» y la diferencia con el estimado de REQ-130 no puede mostrarse. Alternativas en el ADR-0077 |
| D-2 | **«Avance»** (primer panel) no está definido | Secciones «listas» de las cinco; el mosaico «Avance por sección» muestra el estado de cada una, sin porcentajes |
| D-3 | REQ-128 dice «ningún dato de normativa» y REQ-129 «el pendiente general trae las cinco secciones» (la maqueta incluye «Subir la norma de montos 2026») | El pendiente general incluye los ítems de Normativas (son tareas); el primer panel no muestra mosaicos ni datos de normativa (régimen, normas, citas) |
| D-4 | La maqueta abre inline en el primer panel los detalles de resultado, descartes y preguntas (de la sección 4) | Que enlacen a la sección 4 con el detalle abierto: evita calcular dos veces el contexto más pesado y mantiene los 2 s |
| D-5 | La maqueta no dibuja mosaicos para ocho temas de la 014 (datos, Portal, alta desde el pliego, circulares, fichas, exportar, normas cargadas) | Agregarlos (mosaicos chicos con cifra y enlace al detalle); sin ellos quedarían funciones sin acceso, y la spec dice que no cambian |
| D-6 | «Mis fotos» de la maqueta compara «como la subió» con «como se ve» | No hacerlo: exige guardar el original (más datos privados) y ningún requisito lo pide |
| D-7 | Tope del archivo antes de ajustarlo (la spec fija 2 MB para la foto ya ajustada) | 10 MiB sin procesar (una foto de celular pesa de 3 a 8 MB), a confirmar |
| D-8 | El dictamen del Portal se mueve a los pendientes de Evaluación (REQ-129), lo que cambia una cuenta de la 014 | Hacerlo; el total del procedimiento no cambia |
| D-9 | La spec habla de actualizar cada 10 s «como REQ-067»; hoy el sondeo es de 5 s (ADR-0045) | Dejar 5 s: cumple «cada 10 s o menos» |
| D-10 | REQ-140 pide porcentaje también para proponer la matriz, leer un documento y explorar el Portal, pedidos que hoy no reportan un total | Para esos, paso actual, tiempo transcurrido y barra indeterminada; el porcentaje queda para evaluar ofertas y armar fichas (que sí reportan total). Calcular totales para los otros excede la spec |
| D-11 | El mosaico «Documentación de las ofertas» de la maqueta usa «23 de 27» | El sistema no sabe cuántos documentos debe presentar cada oferta: se muestra la cantidad y los faltantes conocidos |
| D-12 | El selector de procedimientos del encabezado actual no está en la maqueta | Conservarlo como segmento del camino |

## Control de decisiones literales

| Fecha | Decisión del responsable (resumen literal) | Dónde se aplica en el plan |
|---|---|---|
| 2026-10-21 | «Lo que me muestre debera ser capaz de implementarse sin mayores complejidades en 8000» | Resumen; ADR-0076; sin marco nuevo ni dependencias |
| 2026-10-21 | «El detalle Se despliega debajo del mosaico» | «Tablero: mosaicos y detalle», `tablero.js`; REQ-127 |
| 2026-10-21 | «quisera que este mas chica 40 por ciento menos y que tenga algun dato arriba» | «Fotos», primer panel al 60 % del ancho con los datos encima |
| 2026-10-21 | «Quiero un pendiente de hacer general y despues uno en cada etapa» | «Pendientes, camino y Hay/Falta»; B-P |
| 2026-10-21 | «Un orden economico de las ofertas y plazos importantes» | `economico.py`, `ingreso.py`; REQ-130 y REQ-131 |
| 2026-10-21 | «pequeño selector en pantalla para pasar a Negro … y a gris blanco» | «Temas, marca, tipografía y estilo»; ADR-0074 |
| 2026-10-21 | «se sepa el camino, que hay y que falta hacer o completar» | `_camino.html`, `_hay_falta.html`; REQ-132 |
| 2026-10-21 | «sutil animacion … fotos que tomara al azar y solo cambian al cambiar de pantalla» | «Fotos»: elección al servir la página; animación de entrada |
| 2026-10-21 | «las transformaras para que tengan la misma tonalidad, saturacion, temperatura, brillo contraste» | Normalización por histograma; REQ-137 |
| 2026-10-21 | «opcion del perfil … limite 10 cada uno» | «Mis fotos», ranuras 0 a 9 |
| 2026-10-21 | «procesos ejecutando tareas largas … marque avance acorde con la estetica» | «Avance de los procesos largos» |
| 2026-10-21 | «Marca: mantenemos el logotipo aprobado el 13/10 … recoloreado a negro, gris y lima» | Marca (REQ-142) |
| 2026-10-21 | «blanco y negro para todas las fotos» | Normalización en luminancia |
| 2026-10-21 | «solo en el primer panel … fondo muy suave casi etereo … principales datos de procedimiento. No de normativa» | Primer panel; REQ-128 y REQ-135; D-3 |
| 2026-10-07 | Estados como ícono de color con el nombre al pasar el mouse | «Estados de cumplimiento» |
| Vigente (P4) | Fotos y datos personales solo en el equipo | ADR-0073; test del repositorio |
