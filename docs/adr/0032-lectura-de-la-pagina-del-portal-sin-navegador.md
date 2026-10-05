# ADR-0032 · Lectura de la página del Portal: HTML con las librerías existentes, formularios de ASP.NET con la biblioteca estándar, y texto mal codificado sin adivinar

Estado: propuesto · Fecha: 2026-10-05 · Decidió: —

## Contexto

La exploración del 2026-10-05 (proceso A0PC000000-0004-LPU25) mostró que la página pública del proceso se lee sin CAPTCHA y trae casi todo el contenido en HTML; los botones "Ver" y "Ver cuadro comparativo" son envíos de formulario de ASP.NET (`__doPostBack`, con `__VIEWSTATE`); el acta de apertura y el dictamen tienen URL directa; y el texto llega con caracteres mal codificados ("Log¿¿stica"). La búsqueda exige CAPTCHA y queda fuera.

El proyecto ya depende de `beautifulsoup4` y `lxml` (lectura de páginas web guardadas en `evaluon/norms/reading/web.py`) y sus clientes HTTP usan `urllib` de la biblioteca estándar. No hay biblioteca de cliente HTTP ni navegador.

## Alternativas

### A. `urllib` con sesión de cookies, `lxml` y `beautifulsoup4`; los envíos de ASP.NET se arman leyendo los campos ocultos (elegida)

Un cliente chico (`evaluon/portal/client.py`): GET, y POST del formulario con `__EVENTTARGET`, `__EVENTARGUMENT`, `__VIEWSTATE`, `__EVENTVALIDATION` y los demás campos ocultos que trae la página, con la misma sesión. Los lectores de cada parte de la página son funciones puras sobre bytes (`evaluon/portal/parsing/`), por eso se prueban con páginas guardadas y sin red.

- Se gana: ninguna dependencia nueva; lectura reproducible y probada sin conexión; todos los accesos pasan por un solo punto, donde se aplica la lista de destinos (ADR-0031).
- Se pierde: si el Portal exige ejecutar JavaScript en alguna parte, no se llega. El postback depende de que el formulario no cambie.

### B. Navegador automatizado (Playwright o Selenium)

- Se gana: ejecuta JavaScript y se comporta como una persona.
- Se pierde: un navegador entero en la imagen (cientos de MB), más superficie de seguridad con salida a internet, tests lentos y frágiles. No hace falta mientras los postbacks se puedan armar a mano.

### C. Biblioteca `requests` o `httpx`

- Se gana: sesión y cookies listos.
- Se pierde: dependencia nueva para lo que `urllib` hace con 40 líneas; pierde el control de redirecciones que la lista de destinos necesita.

## Decisión

Se adopta **A**. Si en T-142 o T-143 se comprueba que un documento o el cuadro comparativo no se pueden obtener sin JavaScript, la parte se marca "no se pudo importar" (REQ-051: queda la carga manual) y se vuelve a este ADR antes de considerar la alternativa B.

**Texto mal codificado** (regla del lector, no del modelo):

1. Se decodifica según lo que declara la página y se prueba con `detect_encoding` de la 001. Si una decodificación alternativa devuelve texto válido para toda la página, se usa esa.
2. Si el daño ya viene en los bytes (los acentos llegan reemplazados por `¿¿` o `�`, sin forma de saber cuál era la letra), **no se adivina** (P3): el texto se guarda y se muestra tal como el Portal lo entrega, y el ítem lleva la marca "texto con caracteres dañados en el Portal" con el campo afectado. Los números, fechas, CUIT y montos no dependen de esto y se leen por su formato.
3. La normalización solo cubre lo recuperable: espacios y saltos de línea duplicados, caracteres de control y la forma Unicode NFC.

La primera tarea del lector (T-140) comprueba con los bytes reales guardados cuál de los dos casos es y lo anota en el plan antes de seguir.

## Consecuencias

- Más fácil: probar el lector con archivos; cambiar el cliente en un solo lugar.
- Más difícil: un cambio en el formulario del Portal rompe el postback; el sistema lo informa (el ítem queda "no se pudo importar") y se sigue con la carga manual.
- Si el daño de codificación no se puede recuperar, el objeto o el título de un procedimiento pueden quedar con `¿¿` en el sistema hasta que alguien lo corrija a mano, y el 100 % de coincidencia se mide contra lo que el Portal muestra, no contra el texto correcto.
- Para revertir: reemplazar `client.py` por otro cliente; los lectores no cambian.
