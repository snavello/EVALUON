# ADR-0075 · Pase de página entre secciones: transiciones entre documentos declaradas en CSS

Estado: aceptado · Fecha: 2026-10-21 · Propuso: Planificador (plan 017) · Decidió: responsable del proyecto (2026-10-21 21:57, «Apruebo el plan 017 con sus decisiones. Seguí con las tareas.»)

## Contexto

REQ-139: al cambiar de sección, la pantalla pasa con efecto de hoja que gira en 0,5 s o menos; con «reducir movimiento» activado en el equipo, el paso es un fundido de 0,15 s o menos. La maqueta lo hace en una sola página con JavaScript: carga las cinco secciones juntas y anima con la API de animaciones. La aplicación real tiene una página por sección (`expedientes/<id>/<sección>/`), con su tablero calculado por el servidor, un sondeo que reemplaza fragmentos y una política de contenido que solo admite scripts como archivos estáticos. El pedido del responsable: implementable en 8000 «sin mayores complejidades».

Datos actuales (consulta del 2026-10-21, a reconfirmar en caniuse o MDN antes de implementar): las transiciones entre documentos (`@view-transition { navigation: auto }`) funcionan en Chrome y Edge 126 o posterior y en Safari 18.2 o posterior; Firefox no las implementa (la documentación de Chrome lista Firefox como «no soportado» y una guía de 2026 lo da como «en desarrollo»; no se encontró una fuente que confirme que ya se publicó). Chrome cancela la transición si la página tarda más de 4 s en estar lista; los clics en enlaces y los envíos de formularios del propio sitio participan, las navegaciones desde la barra de direcciones y los favoritos no. El navegador con el que el proyecto verifica sus pantallas es Edge (informes de verificación de la 003). Fuentes: https://developer.chrome.com/docs/web-platform/view-transitions/cross-document y búsqueda del 2026-10-21 sobre soporte en Safari y Firefox.

## Alternativas

### A. Transiciones entre documentos en CSS, con una mejora progresiva (propuesta)
`@view-transition { navigation: auto; }` en `pase.css`; el `<main>` con `view-transition-name: hoja`, el encabezado con `cabecera` (queda quieto) y la pestaña activa con `pildora` (el navegador la desliza). Las animaciones de `::view-transition-old(hoja)` y `::view-transition-new(hoja)` giran con `transform` (propiedad que el navegador acelera). Un script de unas 15 líneas (`pagereveal`) decide la dirección. `prefers-reduced-motion` cambia a un fundido. Se gana: sin marco, sin cargar las otras secciones, cada sección sigue siendo una página con su dirección (enlaces, atrás, favoritos); sin el script funciona en una dirección; el sondeo y los formularios no cambian. Se pierde: en Firefox no hay animación (la navegación es la de siempre); el efecto depende de que el destino cargue rápido; la dirección usa un evento que Firefox aún no tiene.

### B. Reemplazo del contenido con JavaScript (como la maqueta)
Interceptar el clic de las pestañas, pedir la página con `fetch`, reemplazar `<main>` y animar con la API de animaciones; actualizar la dirección con la API de historial. Se gana: funciona en cualquier navegador moderno, incluido Firefox. Se pierde: unas 80 líneas de script propio que mantener (foco, historial, scroll, errores de sesión vencida, sondeos que se reinician, scripts de las secciones que dejan de ejecutarse al reemplazar HTML); es la pieza más frágil de las que se proponen; hay que probarla con un navegador real, y la imagen de pruebas del proyecto no tiene uno.

### C. Sin animación, solo fundido
Se gana: cero código. Se pierde: no cumple REQ-139 (efecto de hoja que gira), que el responsable pidió explícitamente.

## Decisión

Se propone **A**. Si la Comisión usa un navegador sin la función (Firefox), el costo es un cambio de sección sin animación, no una falla; si el responsable quiere el efecto en todos los navegadores, se pasa a B sin cambiar el resto (las páginas siguen siendo las mismas). La verificación se hace en Edge; los tests leen `pase.css` (duraciones, `@view-transition`, `view-transition-name`, `prefers-reduced-motion`).

## Consecuencias

- Más fácil: ningún script depende del pase; cada sección es una dirección propia; la animación se ajusta con CSS.
- Más difícil: el efecto no se puede probar con los tests del proyecto (se revisa a mano en Edge); si el tablero tarda más de 4 s no hay animación.
- Para revertir: borrar `pase.css` y `pase.js`; no hay otro cambio. Para pasar a B: agregar el script de intercepción sin tocar las plantillas.
