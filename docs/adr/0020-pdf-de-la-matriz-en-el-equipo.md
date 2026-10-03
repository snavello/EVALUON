# ADR-0020 · PDF de la matriz generado en el equipo con WeasyPrint

Estado: aceptado · Fecha: 2026-10-03 · Decidió: Coordinador (decisión técnica, con aviso al responsable)

## Contexto

La spec 003 suma REQ-032: una matriz que todavía no está validada se puede ver en pantalla, imprimir y exportar a PDF, siempre con la leyenda "BORRADOR INCOMPLETO" bien visible en cada página; una matriz validada sale sin la leyenda, con su versión, la fecha y el evaluador que la validó.

Restricciones:

- **P4.** El PDF se genera dentro del equipo propio. La matriz trae texto del pliego, que puede tener datos personales; no sale a ningún servicio.
- **La imagen de la aplicación** es `python:3.12.15-slim-trixie` con Tesseract (`Dockerfile`). No trae fuentes tipográficas ni bibliotecas de dibujo de texto.
- **El pedido de la pantalla** espera hasta 120 segundos (Gunicorn, ADR-0005). Una matriz tiene del orden de 30 a 40 filas (plan 003, "El pliego del caso de referencia"): unas pocas páginas.
- **Verificación.** El criterio de aceptación dice "cada página muestra la leyenda". Tiene que poder comprobarse con un test, página por página. `pdfplumber` ya está en el proyecto (ADR-0004) y lee el texto de cada página de un PDF.

## Alternativas

### A. WeasyPrint: HTML y CSS a PDF (propuesta)
Una plantilla HTML de la matriz, la misma de la vista de impresión, se convierte en PDF en el servidor. La leyenda va en las cajas de margen de `@page`, que se repiten en cada página.
- Se gana: una sola plantilla para la vista de impresión y el PDF; la leyenda en cada página por definición de la página, no por cómo cae el contenido; WeasyPrint dice soportar "the `@page` rule … the page margin boxes" y los contadores de página [api_reference]. El test lee cada página con `pdfplumber` y busca la leyenda.
- Se pierde: bibliotecas del sistema en la imagen (en Debian ≥ 11, `libpango-1.0-0`, `libpangoft2-1.0-0` y `libharfbuzz-subset0` [first_steps]) y un paquete de fuentes, porque la imagen slim no trae ninguno; una dependencia más que actualizar (la versión 70.0, del 2026-09-08, fue una actualización de seguridad [changelog]). Por omisión WeasyPrint busca recursos por HTTP con una espera de 10 segundos [first_steps]: hay que cerrarlo con un `URLFetcher` propio.

### B. ReportLab: el PDF se dibuja con código
La matriz se arma con las primitivas de la biblioteca; la leyenda se dibuja en una función que corre en cada página.
- Se gana: no necesita la plantilla HTML ni las bibliotecas de texto de Pango.
- Se pierde: un segundo diseño de la matriz, en código, aparte de la plantilla de la pantalla y de la vista de impresión. Los tres pueden divergir, y cada cambio de la matriz se hace dos veces.

### C. Solo la impresión del navegador ("Guardar como PDF")
La vista de impresión tiene su hoja de estilos de impresión y la persona guarda el PDF desde el navegador.
- Se gana: ninguna dependencia nueva.
- Se pierde: el PDF depende del navegador y de su configuración (márgenes, encabezados del navegador, escala). No hay forma de comprobar con un test que cada página lleve la leyenda, ni de registrar qué se exportó (huella del archivo, P6).

### D. Chromium sin cabeza dentro del contenedor
Descartada: un navegador completo dentro de la imagen para generar unas pocas páginas (P10).

## Decisión

Se propone **A**, con estas reglas:

1. `weasyprint==70.0` en `pyproject.toml`, con la versión fija como el resto de las dependencias; las bibliotecas del sistema y el paquete de fuentes en el `Dockerfile`, fijados por versión como Tesseract. Las versiones exactas se anotan en la verificación de la tarea que lo instala.
2. Un `URLFetcher` propio que solo entrega la hoja de estilos de impresión desde el disco de la aplicación y rechaza cualquier otra dirección con error. La plantilla no referencia nada externo. Además, la red de `app` no tiene salida a internet (plan 001).
3. La leyenda "BORRADOR INCOMPLETO" se pone en las cajas de margen superior e inferior de `@page`, en negrita y en tamaño grande, para toda versión que no esté validada. La versión validada lleva en esas cajas su número, la fecha de validación y el evaluador.
4. El PDF se genera en el pedido de la pantalla, sin pasar por la cola de pedidos (ADR-0018): una matriz de decenas de filas no justifica un pedido en segundo plano. Si la medición muestra lo contrario, se revisa.
5. La vista de impresión del navegador usa la misma plantilla con su hoja de estilos de impresión: la leyenda queda fija arriba en cada página impresa. Que el navegador repita en cada página lo fijo se comprueba a mano en la tarea, no se da por sabido.

Motivo principal: la leyenda en cada página es un requisito que se tiene que poder comprobar con un test, y una sola plantilla evita que la pantalla, la impresión y el PDF muestren cosas distintas.

## Consecuencias

**Más fácil**
- Un cambio en la presentación de la matriz se hace en una plantilla.
- El test de REQ-032 es una cuenta: páginas del PDF con la leyenda sobre el total.
- La feature 006 (salidas de la evaluación) puede usar el mismo camino para sus PDF.

**Más difícil**
- La imagen crece por Pango y las fuentes (tamaño sin medir; se anota en la tarea).
- WeasyPrint no ejecuta JavaScript y su soporte de CSS no es el de un navegador: la plantilla de impresión se escribe para él.

**Para revertir**
- Pasar a C es quitar el botón de PDF y la dependencia: la vista de impresión queda igual. Pasar a B es reescribir el armado del PDF; los datos no cambian.

## Sin verificar

- Tamaño de la imagen y tiempo de generación de una matriz de 40 filas: se miden en la tarea que lo instala.
- Que el navegador del equipo repita la leyenda fija en cada página impresa: se comprueba a mano en esa misma tarea.

## Fuentes

- [changelog] WeasyPrint, "Changelog", versión 70.0 del 2026-09-08: https://doc.courtbouillon.org/weasyprint/stable/changelog.html
- [first_steps] WeasyPrint, "First Steps": dependencias en Debian, Python ≥ 3.10, recursos por red y `URLFetcher`: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html
- [api_reference] WeasyPrint, "API Reference", características soportadas de CSS Paged Media: https://doc.courtbouillon.org/weasyprint/stable/api_reference.html
