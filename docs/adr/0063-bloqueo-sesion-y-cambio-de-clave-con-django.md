# ADR-0063 · Bloqueo, sesión, cambio de clave y administración de usuarios con lo que trae Django

Estado: propuesto (versión 2) · Fecha: 2026-10-14 · Propuso: planificador (plan 007) · Decidió: —

Enmienda al ADR-0005 en dos puntos: la clave olvidada y los comandos de administración de usuarios (ver «Enmienda al ADR-0005»).

## Contexto

La spec 007 pide:

- **REQ-111:** bloqueo de 15 minutos tras 5 claves equivocadas seguidas, con el mismo mensaje para usuario inexistente, clave equivocada y usuario bloqueado, también en los comandos.
- **REQ-112:** que el responsable del sistema desbloquee, con registro.
- **REQ-113:** registrar ingresos, salidas, fallidos, bloqueos y desbloqueos con la computadora de origen, y consultarlos.
- **REQ-114:** cambio de clave con la actual, 8 caracteres como mínimo, sin comunes, y cambio obligatorio de la clave inicial.
- **REQ-115:** cierre a los 30 minutos sin uso, a las 8 horas y al cerrar el navegador.

Lo que existe (ADR-0005, plan 001):

- Django 6.1 con usuario propio, Argon2id y sesiones en la base.
- Un mensaje único de error.
- Registro de `login` y `login_failed` en `audit_event`.
- Comandos que verifican la clave con `authenticate`, sin pedido web.
- `changepassword` para la clave olvidada, que no deja registro (T-049 lo confirmó: 8 hechos antes y 8 después).
- Una pantalla que pide su avance cada 5 segundos.
- Tres pantallas que se recargan solas cada 5 segundos mientras hay una lectura en curso: el alta desde el Portal, el borrador del pliego y la lectura de ofertas.

Lo que Django 6.1 trae y lo que no:

- No trae bloqueo [1].
- Trae los validadores de largo, de claves comunes (lista de 20.000), de similitud con el usuario y de lista propia [1], y la vista de cambio de clave. Esa vista valida la clave actual con `check_password`, no con `authenticate`: no pasa por un backend.
- La sesión vence según su última modificación, y algunos navegadores la restauran al reabrir [2].

## Alternativas

### Parte 1 · Bloqueo

**A. Backend propio sobre el `ModelBackend` de Django, como único backend.**

- Calcula la clave siempre, para no delatar el bloqueo por el tiempo.
- Después decide dentro de una transacción con la fila del usuario bloqueada (`select_for_update`): con 4 hilos de Gunicorn, decidir fuera dejaría pasar una clave correcta que llegó junto con el quinto error.
- Bloqueado: rechaza con `PermissionDenied`, sin contar. Clave equivocada: suma y, al quinto, bloquea y deja `lockout`. Clave correcta: vuelve la cuenta a 0.
- Con `ModelBackend` también en la lista, una clave correcta entraría aunque el usuario esté bloqueado.

- **Se gana:**
  - los comandos quedan cubiertos;
  - todo en `audit_event` con origen;
  - el desbloqueo registra quién;
  - «seguidos» sin ventana de tiempo;
  - sin bibliotecas nuevas.
- **Se pierde:** código de seguridad propio, que se cubre con tests (incluido uno con pedidos simultáneos).

**B. django-axes.**

- Versión 8.3.1, del 11 de febrero de 2026. Declara Django 4.2, 5.2 y 6.0, pero no la 6.1 [3].
- Según la revisión del plan, la etiqueta 8.3.2 del 30 de agosto de 2026 está en GitHub pero no en PyPI.
- Su organización, Jazzband, anunció en marzo de 2026 su cierre: los proyectos se transfieren entre junio y diciembre de 2026 y la organización se archiva a principios de 2027 [5]. La continuidad de django-axes no está confirmada.
- Exige el pedido web en cada autenticación [4], que los comandos no tienen. Guarda sus registros aparte de `audit_event`.

- **Se gana:** una pieza conocida.
- **Se pierde:** adaptarla a los comandos y al registro, con continuidad incierta.

**C. Limitar en el intermediario, por computadora.**

- **Se pierde:** no es «para un mismo usuario» y no cubre comandos. Descartada.

### Parte 2 · Cierre por inactividad

**A. Middleware propio con marcas de tiempo en la sesión.**

- Guarda el ingreso, el último uso y el origen.
- Cierra a los 30 minutos sin uso o a las 8 horas, con la salida registrada y su motivo.
- No cuentan como uso los pedidos del sondeo (encabezado) ni las tres recargas automáticas (parámetro `auto=1` en la dirección).
- La cookie sigue siendo de sesión del navegador.
- Si el responsable lo aprueba (punto 6 del plan), cada 5 minutos, con uso, registra las salidas de las sesiones que vencieron sin que nadie volviera y las borra.

- **Se gana:** los tres cierres, sin que el sondeo ni las recargas mantengan viva la sesión, y con registro.
- **Se pierde:** algo de código propio y una escritura de sesión por pedido.

**B. Sesión deslizante de Django.**

- **Se pierde:**
  - el sondeo y las recargas la mantienen viva;
  - con `set_expiry` de un número, la cookie sobrevive al cierre del navegador;
  - el tope de 8 horas igual necesita código;
  - no hay registro.

### Parte 3 · Cambio de clave y clave inicial

La vista y el formulario de Django, ajustados:

- con el usuario bloqueado, el formulario no acepta la clave ni renueva el bloqueo;
- la clave actual equivocada cuenta para el bloqueo y deja `login_failed` con el usuario de la sesión;
- si el quinto error ocurre ahí, esa sesión se cierra;
- la clave nueva tiene que ser distinta de la actual (si no, la inicial se podría «cambiar» por la misma, que conoce el responsable);
- mínimo de 8 y claves comunes. Con el punto 19 del plan, también la similitud con el usuario y una lista corta propia en castellano.

Una marca de clave inicial, que ponen `crear_usuario` y `clave_inicial`, obliga a cambiarla antes de usar cualquier sección y cualquier comando.

### Parte 4 · El responsable del sistema y la administración de usuarios

**A. Una marca solo en el usuario del responsable, más comandos de quien administra el equipo.**

- La marca habilita la pantalla del registro de accesos con el botón de desbloquear (punto 1 del plan).
- En el equipo, desbloquear, asignar una clave inicial, ver el registro y poner o quitar la marca son comandos que corre quien administra el equipo, sin usuario de EVALUON, como `crear_usuario` desde la 001. Cada uno deja su hecho.
- Si alguien bloquea a propósito al responsable desde la red, él se desbloquea en el equipo.

- **Se gana:** pocas personas con poder sobre otros usuarios, y una salida si el responsable queda bloqueado.
- **Se pierde:** quien administra el equipo usa esos comandos sin clave de EVALUON. Ya hoy puede dar de alta usuarios y entrar a la base.

**B. Todo el rol de lectura y escritura, con su clave en cada comando (como `rol_comision`).**

- **Se pierde:**
  - todo usuario con ese rol puede ponerle una clave a otro y entrar en su nombre;
  - si bloquean al responsable desde la red, durante 15 minutos nadie desbloquea.

## Decisión

Se propone **A en las cuatro partes**, sin bibliotecas nuevas:

- `AUTHENTICATION_BACKENDS` con solo el backend propio;
- los valores de la spec como constantes;
- una sola vez de esquema: cuatro campos del usuario (el cuarto, la marca, con el punto 2) y cinco tipos de hecho.

`changepassword` y `createsuperuser` se reemplazan por comandos propios con el mismo nombre, que no hacen nada y remiten a `clave_inicial` o `crear_usuario`. Para eso `evaluon.accounts` va antes de `django.contrib.auth` en `INSTALLED_APPS`.

## Enmienda al ADR-0005

- **Clave olvidada.** El ADR-0005 decía: «El restablecimiento de una clave olvidada usa el comando `changepassword` que Django ya trae». Pasa a ser `clave_inicial`, que obliga a cambiarla en el primer ingreso (REQ-114) y deja registro (P6). `changepassword` deja de cambiar claves.
- **Comandos de administración de usuarios.** Además de `crear_usuario`, los comandos `desbloquear_usuario`, `clave_inicial`, `ver_accesos` y `responsable_sistema` los corre quien administra el equipo, sin rol de EVALUON, y quedan registrados. Esto vale si se aprueba la parte 4 A; con la B, piden usuario y el rol de lectura y escritura.

Al aceptar este ADR, el Coordinador agrega al ADR-0005 una nota «Actualización por ADR-0061 y ADR-0063».

## Consecuencias

Más fácil:

- Pantalla, comandos y formulario comparten bloqueo, mensaje y registro.
- Ningún camino cambia claves sin registro.
- El responsable bloqueado tiene salida.

Más difícil:

- Código propio de bloqueo y de sesión, con sus tests.
- La lista de claves comunes de Django no cubre bien el castellano (punto 19).
- Si el navegador restaura la sesión o sigue en segundo plano, el cierre al cerrar el navegador no ocurre. Queda el de 30 minutos, y se le pide al área de sistemas que lo desactive.

Para revertir: el backend y los middleware se sacan de `settings.py`, y los comandos propios se borran para volver a los de Django.

## Sin verificar

- Que calcular la clave siempre iguale los tiempos en la práctica. T-278 lo mide con un umbral escrito antes.
- La etiqueta 8.3.2 de django-axes sin publicar en PyPI: dato de la revisión del plan.

## Fuentes

Consultadas el 2026-10-14.

1. Django 6.1, manejo de claves: https://docs.djangoproject.com/en/6.1/topics/auth/passwords/
2. Django 6.1, sesiones: https://docs.djangoproject.com/en/6.1/topics/http/sessions/
3. django-axes en PyPI (versión, clasificadores, registro de cambios): https://pypi.org/pypi/django-axes/json
4. django-axes, uso: https://django-axes.readthedocs.io/en/stable/3_usage.html
5. Jazzband, «Wind-Down Plan» (14 de marzo de 2026): https://jazzband.co/news/2026/03/14/wind-down-plan
