# ADR-0074 · Tema claro u oscuro: se guarda en el usuario y lo dibuja el servidor

Estado: aceptado · Fecha: 2026-10-21 · Propuso: Planificador (plan 017) · Decidió: responsable del proyecto (2026-10-21 21:57, «Apruebo el plan 017 con sus decisiones. Seguí con las tareas.»)

## Contexto

REQ-134: un selector chico en el encabezado pasa la pantalla a negro o a gris y blanco; la elección queda guardada en el perfil del usuario y vale en cualquier equipo; el tema de inicio es gris y blanco. Hoy el usuario propio (`accounts.User`) no tiene preferencias ni perfil. La política de contenido de la aplicación (`default-src 'self'`) prohíbe scripts y estilos en línea; todo `<script>` es un archivo estático. La maqueta guarda la elección en el almacenamiento local del navegador, lo que no cumple «cualquier equipo». Los usuarios de lectura (sin rol de la Comisión) también deben poder elegir; hoy `journey/views/portada.py` (`without_actions`) quita de la respuesta todo formulario de acción que no sea el de salir.

## Alternativas

### A. Columna `theme` en `accounts_user`, dibujada por el servidor (propuesta)
`User.theme` (`claro` o `negro`, por omisión `claro`, con restricción de valores). `base.html` escribe `<html data-theme="negro">` según `user.theme`. El selector son dos botones de un formulario con POST a una vista que valida el valor y la dirección de vuelta. Se gana: una sola migración chica; la página sale ya en el tema correcto (sin parpadeo ni script); funciona sin JavaScript; vale en cualquier equipo. Se pierde: cada cambio recarga la página (menos de un segundo); el usuario anónimo (página de ingreso) siempre ve el tema de inicio.

### B. Tabla de perfil aparte (`accounts_profile`, uno a uno con el usuario)
Se gana: un lugar donde sumar más preferencias después. Se pierde: una tabla, una relación y un acceso más por cada pedido para una sola columna; la spec no pide más preferencias (P10).

### C. Almacenamiento local del navegador o una cookie, con un script que aplica el tema
Se gana: cambia el tema sin recargar. Se pierde: no cumple «vale en cualquier equipo»; con almacenamiento local o con una cookie leída por script hay un parpadeo del tema equivocado antes de que cargue el script; exige JavaScript para algo que el servidor puede dibujar.

## Decisión

Se propone **A**. El selector envía `tema` (`claro` o `negro`) y `next`; la vista rechaza otro valor, acepta `next` solo si es del mismo sitio (`url_has_allowed_host_and_scheme`) y guarda con `update_fields`. El formulario lleva la clase `preferencia`, que `without_actions` deja pasar, porque cambiar de tema no es una acción de decisión de la Comisión. No se registra en la auditoría: no interviene en ninguna evaluación (P6).

## Consecuencias

- Más fácil: la prueba es un test de vista (elegir negro, entrar con otro cliente y ver `data-theme="negro"`); las hojas de estilo solo conocen `[data-theme="negro"]`.
- Más difícil: un tercer tema o un tema por procedimiento (fuera de alcance) exigirían cambiar el campo a una lista de valores y sumar tokens.
- Para revertir: quitar la columna y cambiar `base.html`; la migración es reversible. Pasar a B si aparece una segunda preferencia.
