# ADR-0076 · Tablero de mosaicos: HTML dibujado por el servidor, gráficos en SVG y un script de unas 60 líneas

Estado: aceptado · Fecha: 2026-10-21 · Propuso: Planificador (plan 017) · Decidió: responsable del proyecto (2026-10-21 21:57, «Apruebo el plan 017 con sus decisiones. Seguí con las tareas.»)

## Contexto

REQ-126 y REQ-127: cada sección abre con mosaicos de información agregada (cifras grandes y gráficos); al tocar un mosaico, su detalle se despliega debajo de la fila del mosaico, de a uno, en 0,4 s o menos. El pedido del responsable: implementable en 8000 «sin mayores complejidades»; el requisito no funcional: sin agregar un marco de interfaz nuevo.

Lo que hay: plantillas de Django; un parcial por tema que ya dibuja lo que será el detalle (con sus formularios, anclas y modos por parámetro de la dirección); un sondeo propio de unas 100 líneas (`recorrido.js`) que reemplaza fragmentos; política de contenido `default-src 'self'` (sin `style=` ni `<script>` en línea, que `tests/journey/test_no_external.py` también prohíbe); WhiteNoise sirve los estáticos que `collectstatic` reunió al construir la imagen. La maqueta arma todo con JavaScript (las plantillas literales construyen el HTML en el navegador) y usa estilos en línea para el ancho de las barras, lo que la política de contenido no permite.

## Alternativas

### A. Servidor + CSS + un script de ~60 líneas, gráficos en SVG de plantilla (propuesta)
El servidor dibuja los mosaicos y los gráficos (SVG con atributos de presentación, que la política de contenido admite), y deja los detalles ya renderizados y ocultos. `tablero.js` mueve el detalle del mosaico tocado debajo de su fila y lo abre con una transición de CSS. Sin el script, los mosaicos son anclas a la zona de detalles, que queda visible. Se gana: cero dependencias; la mayor parte se prueba con tests de Django (el HTML contiene lo que debe); los parciales de la 014 se reutilizan sin reescribirlos; el sondeo no cambia. Se pierde: los detalles de toda la sección se calculan al abrirla, aunque no se abran (hoy ya se calculan); la lógica de «debajo de la fila» necesita medir la posición de los mosaicos, lo único que solo se prueba con un navegador.

### B. HTMX (o similar) para cargar cada detalle al tocar
Se gana: se calcula solo el detalle que se abre; se escribe menos script propio. Se pierde: una dependencia nueva que fijar, descargar y alojar en `static/` (P5); el detalle sale de una vista nueva por tema con su contexto (se duplica el que hoy arma la página); los formularios del detalle tienen que volver a la sección con el detalle abierto; el responsable pidió explícitamente evitar marcos nuevos.

### C. Una aplicación de página única (React o similar)
Se gana: la experiencia de la maqueta tal cual. Se pierde: una cadena de construcción, un servidor de datos (API) y reescribir cada tema; contradice el pedido «sin mayores complejidades» y P10.

### D. `<details>` nativo sin script
Se gana: cero JavaScript. Se pierde: el detalle se abre dentro de la celda del mosaico, no debajo de la fila completa (REQ-127), y no cierra los otros.

## Decisión

Se propone **A**. El contrato del servidor es `Tile` (título, cifra, gráfico, detalle que abre, texto de «falta»): si un dato es `None`, la plantilla dibuja «Falta» o «Pendiente» y no hay valor por omisión (REQ-141). El detalle abre con una transición de `grid-template-rows` de 0,35 s. El script también abre el detalle que contiene el elemento del `#hash` (anclas de la 014) y respeta `prefers-reduced-motion`. Los gráficos se dibujan con SVG de plantilla; si un gráfico necesitara más de lo que SVG hace con los datos agregados (por ejemplo, ejes interactivos), se vuelve a plantear con la medición.

## Consecuencias

- Más fácil: cada bloque de sección escribe un `tiles()` por tema y no toca scripts; cambiar un gráfico es cambiar una plantilla.
- Más difícil: la posición «debajo de la fila» y la animación se verifican a mano en Edge; con pantallas muy angostas (menos de 640 px) la cuadrícula cae a una columna y el detalle va debajo del mosaico.
- Para revertir: quitar `tablero.js` deja los detalles como una lista de secciones al final de la página (el comportamiento sin script); pasar a B es cambiar la carga del detalle sin tocar los mosaicos.
