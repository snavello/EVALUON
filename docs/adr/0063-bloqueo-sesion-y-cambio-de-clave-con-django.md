# ADR-0063 · Bloqueo, sesión y cambio de clave con lo que trae Django

Estado: propuesto · Fecha: 2026-10-14 · Propuso: planificador (plan 007) · Decidió: —

## Contexto

La spec 007 pide, además del acceso por red:

- **REQ-111:** bloquear 15 minutos a un usuario tras 5 claves equivocadas seguidas, aunque después escriba la correcta, con el mismo mensaje para usuario inexistente, clave equivocada y usuario bloqueado, también en los comandos.
- **REQ-112:** que el responsable del sistema desbloquee, con registro.
- **REQ-113:** registrar ingresos, salidas, fallidos, bloqueos y desbloqueos con la computadora de origen, y poder consultarlos.
- **REQ-114:** cambio de clave con la actual, 8 caracteres como mínimo, sin claves comunes, y cambio obligatorio de la clave inicial.
- **REQ-115:** cierre a los 30 minutos sin uso, a las 8 horas y al cerrar el navegador, sin perder lo guardado.

Lo que ya existe (ADR-0005, plan 001):

- Django 6.1 con el usuario propio de `accounts`, claves en Argon2id y sesiones en la base, que vencen a las 8 horas del ingreso y al cerrar el navegador.
- Un único mensaje de error, «Usuario o clave incorrectos».
- El registro de `login` y `login_failed` en `audit_event` por las señales de Django.
- Los comandos, que piden la clave por teclado y la verifican con el mismo `authenticate` de Django, sin pedido web (`permissions.authenticate_command`).
- La pantalla, que pide su avance cada 5 segundos (`recorrido.js`, ADR-0045).

Lo que Django 6.1 trae y lo que no:

- **No trae bloqueo por intentos fallidos.** La página de claves no lo menciona; solo habla de la defensa contra la enumeración por tiempo [1].
- **Trae** el validador de largo mínimo y uno de claves comunes, con una lista de 20.000 de Royce Williams [1], y la vista y el formulario de cambio de clave, que piden la actual.
- **La sesión** vence según la última vez que se modificó: leerla no cuenta como actividad [2]. Con `SESSION_SAVE_EVERY_REQUEST` se guarda en cada pedido; con `set_expiry(n)` vence a los `n` segundos sin actividad [2]. Algunos navegadores, como Chrome, restauran la sesión al reabrir, y entonces no vence al cerrar el navegador [2].

## Alternativas

### Parte 1 · Bloqueo

**A. Backend propio sobre el `ModelBackend` de Django.** Tres campos en el usuario (intentos seguidos, bloqueado hasta, clave inicial) y un backend que, antes de comprobar la clave, mira si el usuario está bloqueado. Si lo está, lanza `PermissionDenied`: Django devuelve que no, emite la señal de ingreso fallido y el formulario muestra el mismo mensaje. Para no delatar el bloqueo por el tiempo de respuesta, igual calcula la clave. Al quinto fallido pone el bloqueo y deja el hecho `lockout`; un ingreso correcto vuelve la cuenta a cero.

- **Se gana:**
  - Los comandos quedan cubiertos sin cambios, porque ya pasan por `authenticate`.
  - Todo queda en `audit_event`, con la computadora de origen.
  - El desbloqueo registra quién lo hizo.
  - «Seguidos» significa exactamente eso, sin ventana de tiempo.
  - Sin bibliotecas nuevas.
- **Se pierde:** es código de seguridad propio (unas decenas de líneas), que se cubre con tests de cada criterio de la spec.

**B. django-axes.** Biblioteca de Jazzband. Versión 8.3.1, del 11 de febrero de 2026; las anteriores son del 9 y el 6 de febrero de 2026 y del 19 de diciembre de 2025: se mantiene. Declara Django 4.2, 5.2 y 6.0, pero no la 6.1 [3]. Exige que cada autenticación reciba el pedido web [4].

- **Se gana:** una pieza mantenida y conocida.
- **Se pierde:**
  - Los comandos no tienen pedido web: habría que fabricarles uno para pasarlo.
  - Guarda los intentos y bloqueos en sus propias tablas, aparte de `audit_event`. El desbloqueo con su comando no deja quién lo hizo en nuestro registro.
  - La respuesta de bloqueo por omisión hay que reemplazarla para que el mensaje sea el mismo.
  - No declara la versión de Django que usa el proyecto.
  - Cómo cuenta «seguidos» frente a su tiempo de enfriamiento no lo verifiqué.

**C. Limitar en el intermediario, por computadora.**

- **Se pierde:** no cumple «para un mismo usuario» ni cubre los comandos. Descartada.

### Parte 2 · Cierre por inactividad

**A. Middleware propio con marcas de tiempo en la sesión.** Guarda el momento del ingreso y el del último uso. Si pasaron 30 minutos sin uso o 8 horas desde el ingreso, cierra la sesión (la salida queda registrada con su motivo) y lleva al ingreso. Los pedidos del sondeo traen un encabezado y no cuentan como uso. La cookie sigue siendo de sesión del navegador, y la base la sigue venciendo a las 8 horas.

- **Se gana:** cumple los tres cierres, no cuenta el sondeo y deja registro.
- **Se pierde:** unas decenas de líneas propias, y una escritura de la sesión por pedido (10 usuarios).

**B. Sesión deslizante de Django** (`SESSION_SAVE_EVERY_REQUEST`, o `set_expiry(1800)`).

- **Se gana:** casi sin código.
- **Se pierde:**
  - El sondeo cada 5 segundos la mantiene viva para siempre mientras la pestaña esté abierta.
  - Con `set_expiry` de un número, la cookie deja de ser de sesión del navegador: sobrevive al cierre y rompe REQ-115.
  - El tope de 8 horas igual necesita código.
  - El cierre no queda registrado.

### Parte 3 · Cambio de clave y clave inicial

**Única alternativa razonable:** la vista y el formulario de cambio de clave de Django (piden la actual y validan con `AUTH_PASSWORD_VALIDATORS`), con el largo mínimo de 8 que ya existe y el validador de claves comunes, más la marca de clave inicial en el usuario y un middleware que, mientras esté puesta, solo deja pedir el cambio de clave y la salida. `crear_usuario` y un comando nuevo, `clave_inicial`, ponen la marca. La clave actual equivocada en el formulario cuenta para el bloqueo: si no, sería una forma de probar claves sin bloqueo desde una sesión abierta.

La lista de claves comunes de Django es casi toda en inglés. Una lista propia en castellano es un cambio de configuración (`password_list_path` [1]) si el responsable lo pide; no se agrega ahora (P10).

### Parte 4 · Quién es el «responsable del sistema» y por dónde actúa

**A. El usuario con rol de lectura y escritura, por comandos** (`desbloquear_usuario`, `ver_accesos`, `clave_inicial`), como ya hace `rol_comision` para cambiar roles.

- **Se gana:** sin roles nuevos ni pantallas nuevas, con el mismo control y registro que los demás comandos.
- **Se pierde:** el responsable tiene que estar en el equipo y escribir comandos.

**B. Una pantalla del registro de accesos**, que la spec permite.

- **Se gana:** consultar desde cualquier computadora de la lista.
- **Se pierde:** una pantalla más, con su maqueta, sus pruebas y un control de rol en la vista.

## Decisión

Se propone **A en las cuatro partes**:

- backend de bloqueo propio;
- middleware de sesión propio;
- cambio de clave de Django con el validador de claves comunes y la marca de clave inicial;
- responsable del sistema = rol de lectura y escritura, por comandos.

Sin bibliotecas nuevas. Los valores de la spec son constantes de `settings.py`: 5 intentos, 15 minutos, 30 minutos, 8 horas, 8 caracteres. El esquema cambia una sola vez: tres campos del usuario y cinco tipos de hecho (`logout`, `lockout`, `unlock`, `password_change`, `initial_password`).

## Consecuencias

Más fácil:

- Pantalla y comandos comparten bloqueo, mensaje y registro.
- El registro de accesos es el mismo `audit_event` de siempre, con la computadora en `detail`.

Más difícil:

- El bloqueo y el cierre por inactividad son código propio que hay que mantener con sus tests.
- La lista de claves comunes no cubre bien el castellano.
- Si el navegador restaura la sesión al reabrir, el cierre «al cerrar el navegador» no ocurre. Queda el de 30 minutos, y se le pide al área de sistemas que lo desactive por política.

Para revertir: el backend y los middleware se sacan de `settings.py`; los campos y los tipos de hecho quedan sin uso. Pasar a django-axes exige resolver los comandos y llevar sus registros a `audit_event`.

## Sin verificar

- Cómo cuenta django-axes 8.3 los intentos «seguidos» frente a su tiempo de enfriamiento.
- Que calcular la clave también para un usuario bloqueado iguale los tiempos en la práctica. Los tests comprueban que el cálculo corre, no los milisegundos.

## Fuentes

Consultadas el 2026-10-14.

1. Django 6.1, manejo de claves (validadores, lista de claves comunes): https://docs.djangoproject.com/en/6.1/topics/auth/passwords/
2. Django 6.1, sesiones: https://docs.djangoproject.com/en/6.1/topics/http/sessions/
3. django-axes en PyPI (versión, clasificadores) y su registro de cambios: https://pypi.org/pypi/django-axes/json
4. django-axes, uso (el pedido como argumento de la autenticación): https://django-axes.readthedocs.io/en/stable/3_usage.html
