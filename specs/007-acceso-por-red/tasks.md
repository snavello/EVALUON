# Tareas 007 · Acceso por red

Plan: `specs/007-acceso-por-red/plan.md` (versión 3, mínima)

Despliegue: pendiente

> El tablero (`docs/tablero.md`) se genera de este archivo. Al aprobarse el despliegue, la línea de arriba pasa a `Despliegue: aprobado AAAA-MM-DD`.

Estados: pendiente · en curso · en verificación · terminada · bloqueada

Dos tareas que no dependen entre sí y no comparten archivos se pueden hacer en paralelo. Estas cuatro van en cadena: comparten `settings.py` y `accounts`, y la última prueba todo.

Ritmo de trabajo (ADR-0024 y ADR-0025):

- Las ramas de tarea no tocan este archivo ni el tablero.
- La verificación de cada tarea queda en `specs/007-acceso-por-red/verificacion/T-NNN.md`, con cifras, identificadores y estados. Nunca claves, direcciones de la red del organismo ni textos de procesos.
- Si T-269 o T-272 no llegan a un umbral: una sola tarea de corrección (ID nuevo) y una sola repetición. Lo que siga sin llegar va a «Revisión con el primer producto».

**IDs.** T-269 a T-272. El último ID usado antes era T-268. Los IDs T-273 a T-285 de la versión 2 quedan sin usar.

**Condiciones previas.**

- Los ADR-0061 a ADR-0063 son propuestos y los acepta el responsable con este plan. El ADR-0064 está rechazado.
- T-271 necesita la maqueta de la pantalla de cambio de clave aprobada por el responsable. La presenta el Coordinador.
- P11: el proceso reservado se carga en 8000 solo después de dos cosas: el dictamen de auditoría (solo fallas, ADR-0052) sin hallazgos bloqueantes, y la aprobación del despliegue (`Despliegue: aprobado`).

**Órdenes de verificación.** Las pruebas corren con un proyecto de Docker propio, nunca sobre los contenedores de 8000:

```
docker compose -p <proyecto del encargo> --env-file <archivo del encargo> up -d db
docker compose -p <proyecto del encargo> --env-file <archivo del encargo> run --rm --no-deps app pytest <área>
```

La suite completa la corre el Coordinador una vez por lote.

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-269 | Corte vertical: Caddy en Windows con certificado, lista y firewall, los pasos del responsable en `entorno.md`, y Django detrás del intermediario. Se verifica con el ingreso cifrado desde una computadora de la lista, con un usuario de prueba y el caso chico | REQ-109, REQ-110, REQ-116 | — | en curso |
| T-270 | Bloqueo de 5 intentos y 15 minutos con mensaje genérico también en comandos, registro con la computadora de origen y la salida, `desbloquear_usuario` y `ver_accesos` en el equipo; el esquema de la feature | REQ-111, REQ-112, REQ-113 | T-269 | pendiente |
| T-271 | Cambio de clave (mínimo 8, comunes, distinta de la actual), clave inicial obligatoria y `clave_inicial`; cierre de sesión a los 30 minutos y a las 8 horas, sin contar el sondeo ni las tres recargas automáticas | REQ-114, REQ-115 | T-270 | pendiente |
| T-272 | Prueba en la red con el caso chico, con el responsable: 5 de 5 secciones desde una computadora de la lista y los umbrales del plan, con la GPU de 8000 | REQ-109, REQ-110, REQ-111, REQ-112, REQ-113, REQ-114, REQ-115, REQ-116, REQ-117 | T-271 | pendiente |

## Detalle

### T-269 · Corte vertical: intermediario cifrado, lista y firewall

- **Requisitos:** REQ-109, REQ-110, REQ-116
- **Nivel de verificación:** plena. Necesita al responsable (administrador de Windows), una computadora de la lista (A) y una de fuera (B; puede ser A sacada de la lista).
- **Qué hay que hacer:**
  1. **`scripts/red/caddy.py`** (Python, solo la biblioteca estándar). Lee el `.env`. Valida `EVALUON_ADDRESS`, `EVALUON_SERVER_IP` y `EVALUON_COMPUTERS` (IPv4, sin repetidos, 10 como máximo) y `APP_PORT`, con mensajes en lenguaje llano. Escribe `C:\EVALUON-red\Caddyfile` desde `scripts/red/Caddyfile.plantilla`:
     - opciones globales `admin off` y `auto_https off`, y `default_sni` si se entra por IP;
     - sitio `http://<dirección>`: `abort` de lo que no viene de la lista ni del equipo, y redirección 308 a `https` para el resto;
     - sitio `https://<dirección>`: `tls` con los dos archivos de `C:\EVALUON-red\certificados\`, el mismo corte, `map` de la dirección al nombre (el equipo da `equipo-del-sistema`), `reverse_proxy 127.0.0.1:<APP_PORT>` con `header_up X-Evaluon-Computer`.

     Los nombres exactos de las opciones se fijan con la documentación de la versión.
  2. **`scripts/red/aplicar-red.ps1`** (PowerShell como administrador; guardado en UTF-8 con BOM).
     - La primera vez: baja el zip de Windows de la versión fijada de Caddy, lo comprueba con `Get-FileHash -Algorithm SHA512` contra `scripts/red/caddy.sha512` (copiado literal de las sumas publicadas), lo deja en `C:\EVALUON-red\` y registra el servicio `EVALUON-Caddy` con arranque automático.
     - Siempre:
       - corre `caddy.py`;
       - valida con `caddy.exe validate`;
       - crea o actualiza la regla de entrada «EVALUON» (TCP 80 y 443, programa `caddy.exe`, solo las direcciones de la lista y la del equipo, `-Profile Any`);
       - reinicia el servicio;
       - muestra la lista y el resultado.
  3. **`scripts/red/crear-certificados.sh`** (Git Bash, con el `openssl` de Git para Windows y `MSYS_NO_PATHCONV=1`).
     - Si falta, crea la autoridad en `C:\EVALUON-red\autoridad\`: 10 años, `CA:TRUE` con `pathlen:0`, `extendedKeyUsage=serverAuth`, y restricciones de nombre críticas de los dos tipos (las IP de EVALUON y del equipo; el nombre de EVALUON, o `.invalid` si no hay nombre).
     - Crea `evaluon.crt` (397 días, con la cadena) y `evaluon.key` en `certificados\`.
     - Deja `ca-evaluon.crt` para instalar en las computadoras y muestra su huella y el vencimiento.
  4. **Django detrás del intermediario:**
     - `settings.py`: `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`.
     - Un middleware chico (`evaluon/accounts/secure_cookies.py`), después de `ContentSecurityPolicyMiddleware` y antes de `SessionMiddleware`, para que actúe después de que se escriban las cookies: si el pedido llegó cifrado, marca `Secure` las cookies de sesión y CSRF de la respuesta. El uso local por `http://127.0.0.1:8000` no cambia.
  5. **`.env.example`:** bloque comentado «Acceso por red (plan 007)» con las tres variables y la dirección en `DJANGO_ALLOWED_HOSTS`. Solo direcciones de ejemplo de documentación (`192.0.2.0/24`).
  6. **`specs/007-acceso-por-red/entorno.md`:** los pasos del responsable del plan, con cada comando y lo que tiene que verse. También:
     - agregar y quitar una computadora;
     - poner el certificado del organismo (reemplazar los dos archivos y volver a aplicar);
     - renovar el certificado cada año;
     - las comprobaciones de este corte: las líneas de `Test-NetConnection` y `curl.exe` para pegar, y la captura con `pktmon` como administrador.
  7. **Tests:**
     - `tests/red/test_caddy_config.py`:
       - una lista válida da el `Caddyfile` esperado;
       - 11 computadoras, repetidos o direcciones inválidas se rechazan;
       - el equipo entra como `equipo-del-sistema`;
       - están `admin off` y `auto_https off`;
       - el sitio `http` corta y redirige;
       - el `https` reenvía a `127.0.0.1`;
       - no hay hosts externos.
     - `tests/accounts/test_secure_cookies.py`: con `X-Forwarded-Proto: https` las cookies salen `Secure`; sin él, no; un POST con `Origin: https://<dirección>` pasa el control CSRF.
- **Archivos:** `scripts/red/caddy.py`, `Caddyfile.plantilla`, `aplicar-red.ps1`, `caddy.sha512` y `crear-certificados.sh` (nuevos), `evaluon/accounts/secure_cookies.py` (nuevo), `evaluon/settings.py`, `.env.example`, `specs/007-acceso-por-red/entorno.md` (nuevo), `tests/red/__init__.py`, `tests/red/test_caddy_config.py` y `tests/accounts/test_secure_cookies.py` (nuevos).
- **Verificación:**
  1. Las pruebas de `tests/red` y `tests/accounts`. El `Caddyfile` de ejemplo lo acepta `caddy.exe adapt` (binario bajado a una carpeta temporal y verificado).
  2. Después, el corte vertical en 8000, con el código integrado:
     - **Responsable:** `crear-certificados.sh`; el `.env` con A en la lista y la dirección en `DJANGO_ALLOWED_HOSTS`; `aplicar-red.ps1`; la raíz en A.
     - **Coordinador:** recrea `app` de 8000 y crea un usuario de prueba con rol de la Comisión.
     - **Desde A:**
       - `https://<dirección>` muestra el ingreso sin advertencias;
       - el usuario ingresa y abre el caso chico (si no está cargado en 8000, sube su pliego);
       - `curl.exe -si http://<dirección>/ingresar/` da 308 de Caddy, sin contenido de la aplicación.
     - **En el equipo:** con una captura de `pktmon` durante un ingreso, la clave aparece 0 veces.
     - **Desde B:** 0 páginas, y `Test-NetConnection` a 5432, 8000, 8080 y 2019 da 0 conexiones; desde A, también 0 (solo responden 80 y 443).
     - **La lista:** sacar A, aplicar: no llega; volver a ponerla: llega, sin tocar el código.

     Se registra en `verificacion/T-269.md`.
- **No tocar:** `docker-compose*.yml`, los contenedores de 8000 salvo recrear `app` en la verificación, modelos.

### T-270 · Bloqueo, registro de origen y comandos

- **Requisitos:** REQ-111, REQ-112, REQ-113
- **Nivel de verificación:** plena (esquema y seguridad).
- **No arranca sin:** T-269 integrada. Es la única tarea con migraciones.
- **Qué hay que hacer:**
  1. **Esquema:** los tres campos del usuario y los cinco tipos de hecho (plan, «Modelo de datos»), con sus migraciones, desde cero y hacia atrás.
  2. **`accounts/backends.py`:** `LockoutBackend`, el único de `AUTHENTICATION_BACKENDS`.
     - Calcula la clave y después decide dentro de una transacción con `select_for_update` del usuario:
       - bloqueado: rechaza sin contar, aunque la clave sea correcta (`PermissionDenied`: mismo mensaje y señal de ingreso fallido);
       - clave equivocada: suma uno, y al quinto pone `locked_until` a 15 minutos, vuelve la cuenta a 0 y deja `lockout`;
       - clave correcta: vuelve la cuenta a 0.
     - Las constantes van en `settings.py`.
  3. **`accounts/origin.py`:** el origen del pedido desde `X-Evaluon-Computer` y `X-Forwarded-For` (sin ellos, `equipo-del-sistema`); el de un comando, `equipo-del-sistema`. Valores acotados en largo.
  4. **`apps.py`:**
     - `login` y `login_failed` con `origin`, que se guarda en la sesión al ingresar;
     - receptor de `user_logged_out`: `logout` con `origin` y `reason` (`request.evaluon_logout_reason`, o `user`).
  5. **`permissions.authenticate_command`:** `login` con el origen del comando.
  6. **Comandos `desbloquear_usuario <usuario> --usuario <responsable>` y `ver_accesos [--desde] [--hasta] [--de] --usuario <responsable>`,** con `authenticate_command` y el rol de lectura y escritura, como `rol_comision`.
     - Desbloquear vacía el bloqueo y la cuenta y deja `unlock` con quién, a quién y cuándo.
     - `ver_accesos` lista los hechos de acceso con fecha y hora de Buenos Aires, hecho, usuario o nombre, computadora con su dirección, y canal.
  7. **`audit/services.py`:** `FORBIDDEN_DETAIL_KEYS` suma `old_password`, `new_password1` y `new_password2`.
  8. **Tests, con el reloj controlado:**
     - los criterios de REQ-111, por pantalla y por comando;
     - `AUTHENTICATION_BACKENDS` comparado literal;
     - REQ-112: tras el desbloqueo, ingresa enseguida;
     - REQ-113: ingreso, fallido y bloqueo con los encabezados de una computadora de la lista, desbloqueo por comando, y `ver_accesos` muestra los 4 con usuario o nombre, computadora, fecha y hora;
     - «Salir» deja `logout`.
- **Archivos:** `evaluon/accounts/models.py` y una migración nueva, `evaluon/audit/models.py` y una migración nueva, `evaluon/accounts/backends.py` y `origin.py` (nuevos), `evaluon/accounts/apps.py`, `evaluon/accounts/permissions.py`, `evaluon/accounts/management/commands/desbloquear_usuario.py` y `ver_accesos.py` (nuevos), `evaluon/audit/services.py`, `evaluon/settings.py`, `tests/accounts/test_lockout.py`, `test_origin.py` y `test_ver_accesos.py` (nuevos), `tests/accounts/test_access_log.py`, y los tests de `audit` que listen tipos de hecho.
- **Verificación:** las pruebas de `tests/accounts` y `tests/audit`; migrar desde cero y hacia atrás.
- **No tocar:** vistas, plantillas, `scripts/red/`.

### T-271 · Clave, clave inicial e inactividad

- **Requisitos:** REQ-114, REQ-115
- **Nivel de verificación:** plena (una pantalla nueva y lógica de sesión).
- **No arranca sin:** T-270 integrada y la maqueta de la pantalla de cambio de clave aprobada.
- **Qué hay que hacer:**
  1. **Pantalla `cambiar-clave/`** sobre la vista de cambio de clave de Django. Rótulos «Clave actual», «Clave nueva», «Repita la clave nueva»; mensajes con «clave».
     - La clave nueva tiene que ser distinta de la actual.
     - Al cambiarla: quita `must_change_password`, deja `password_change` y lleva al inicio.
     - Enlace «Cambiar clave» junto a «Salir» en `_cabecera.html`, según la maqueta.
  2. **`settings.py`:** `CommonPasswordValidator` junto al mínimo de 8 que ya existe; las líneas de `MIDDLEWARE`; `SESSION_IDLE_MINUTES = 30` y `SESSION_MAX_HOURS = 8`.
  3. **`accounts/password_policy.py`:** con `must_change_password`, solo se pueden pedir el cambio de clave, la salida y el ingreso; todo lo demás va al cambio de clave.
  4. **Comandos:**
     - `crear_usuario` marca la clave inicial;
     - `clave_inicial <usuario> --usuario <responsable>` (lectura y escritura) pide la clave dos veces, la valida y la guarda con la marca. Si el usuario estaba bloqueado, lo desbloquea con su `unlock`. Deja `initial_password`;
     - `permissions.authenticate_command` rechaza a un usuario con clave inicial, con el mensaje de que la cambie por pantalla.
  5. **`accounts/session_policy.py`:** middleware después de `AuthenticationMiddleware`.
     - Guarda el ingreso y el último uso.
     - A las 8 horas del ingreso, o a los 30 minutos sin uso: pone el motivo, llama a `logout` y lleva al ingreso con `next`.
     - Solo cuenta como uso un pedido sin `X-Evaluon-Poll` ni `auto=1`.
  6. **Recargas:**
     - `recorrido.js` manda `X-Evaluon-Poll: 1`;
     - `journey/nuevo.html` y `journey/s1_pliego_borrador.html` recargan con `auto=1` en la dirección;
     - `s3_ofertas.js` recarga con `auto=1`.
  7. **Tests:**
     - REQ-114: con clave inicial, ninguna sección; clave corta, común e igual a la actual, rechazadas con su motivo; sin la clave actual correcta, rechazada;
     - `crear_usuario` y `clave_inicial` marcan;
     - un comando con clave inicial se rechaza;
     - REQ-115: 29 minutos sigue, 31 lleva al ingreso; con uso cada 20 minutos, a las 8 horas lleva al ingreso; lo guardado sigue;
     - el sondeo no mantiene la sesión, y **una prueba por cada una de las tres pantallas que se recargan solas**;
     - la cookie sigue sin fecha de vencimiento;
     - `logout` con `idle` o `max_age`.

     El test de 8 horas de `test_session.py` se ajusta a usos cada menos de 30 minutos.
- **Archivos:** `evaluon/accounts/views.py`, `urls.py`, `password_policy.py` y `session_policy.py` (los dos nuevos), `evaluon/accounts/permissions.py`, `evaluon/accounts/management/commands/crear_usuario.py` y `clave_inicial.py` (nuevo), `evaluon/templates/accounts/cambiar_clave.html` (nuevo), `evaluon/templates/journey/_cabecera.html`, `nuevo.html` y `s1_pliego_borrador.html`, `evaluon/static/journey/recorrido.js` y `s3_ofertas.js`, si hace falta `evaluon/journey/views/nuevo.py` y `evaluon/journey/temas/s1_pliego.py`, `evaluon/settings.py`, `tests/accounts/test_password_change.py`, `test_clave_inicial.py` y `test_session_policy.py` (nuevos), `tests/accounts/test_session.py`, `tests/accounts/test_crear_usuario.py`, y los tests de `tests/journey/` de esas pantallas.
- **Verificación:** las pruebas de `tests/accounts` y `tests/journey`. El Coordinador compara la pantalla con la maqueta.
- **No tocar:** modelos y migraciones, `backends.py`, `scripts/red/`.

### T-272 · Prueba en la red con el caso chico

- **Requisitos:** REQ-109 a REQ-117
- **Nivel de verificación:** plena. Usa la GPU de 8000, como siempre: no se presta nada. Necesita al responsable, A y B.
- **No arranca sin:** T-271 integrada y desplegada en 8000 por el Coordinador.
- **Qué hay que hacer**, el testeador con el responsable, sobre 8000 y con material público:
  1. **REQ-109 y REQ-114.** Un evaluador nuevo (`crear_usuario`) ingresa desde A y cambia la clave inicial. Antes, prueba una clave corta, una común, una igual a la actual y la actual equivocada. Después recorre el caso chico en las cinco secciones. Umbral: 5 de 5.
  2. **REQ-110.** `curl.exe -si` por `http` al ingreso, a una página de cada sección y a un estático: todas terminan en `https` sin contenido de la aplicación. 0 advertencias en A.
  3. **REQ-111 a REQ-113.**
     - Desde A, 5 claves equivocadas y la correcta: rechazada con el mismo mensaje que un usuario inexistente y una clave equivocada.
     - `desbloquear_usuario` en el equipo: A ingresa enseguida.
     - `ver_accesos` muestra los 4 hechos con la computadora A (y «equipo del sistema» para el desbloqueo), fecha y hora.
     - Por comando: las mismas reglas.
  4. **REQ-115.**
     - Una pantalla con sondeo abierta 31 minutos sin tocarla: el siguiente clic lleva al ingreso, y lo guardado sigue.
     - Cerrar todas las ventanas del navegador en A y reabrirlo: lleva al ingreso. Se anota el navegador.
  5. **REQ-116 y REQ-109.** `Test-NetConnection` desde A y desde B: 0 conexiones a servicios internos; 0 páginas desde B.
  6. **Tiempo de carga.** Cada sección desde A en menos de 2 s y no más lenta que en el equipo, con las herramientas del navegador.
  7. **REQ-117, lo que rige ahora.**
     - `git status` de la raíz no tiene nada del caso fuera de lo ignorado;
     - los motores corren con `--offline`;
     - solo `portal_worker` y `app` tienen salida a internet, como hasta hoy; se anota.
- **Umbral:** el del plan, punto por punto.
- **Qué entrega:** `verificacion/T-272.md`, sin datos del organismo ni claves.
- **Archivos:** solo ese.
- **No tocar:** código y scripts. Un hallazgo va a la tarea de corrección.

## Revisión con el primer producto (ADR-0024)

Lo que la versión 2 agregaba y la spec no pide. Se revisa cuando el sistema esté probado (decisión del responsable del 2026-10-14). Una línea por ítem.

- Pantalla del registro de accesos con botón de desbloquear (L1-01).
- Marca de «responsable del sistema» propia, distinta del rol de lectura y escritura, y salida si ese usuario queda bloqueado (SEG-11, PC-13).
- Que `clave_inicial` no permita a cualquier usuario de lectura y escritura tomar cuentas ajenas (L1, SEG).
- Reemplazar `changepassword` y `createsuperuser` por comandos que remiten a `clave_inicial` (SEG-09, PC-12).
- Que el formulario de cambio de clave respete el bloqueo y cuente la clave actual equivocada (L1).
- Cerrar la sesión si el bloqueo se produce desde el formulario de cambio de clave (L1-12).
- Registrar la salida de las sesiones que vencen sin que el usuario vuelva (L1-05).
- No guardar en el registro un nombre escrito que parezca una clave (SEG-16).
- Usuario de la base sin propiedad de las tablas, para que el registro no se pueda vaciar desde la aplicación (SEG-13).
- Cortar la salida a internet de `app` (red `web`), con una puerta (T-047, PC-10).
- HSTS si se entra por nombre (SEG-07).
- Lista de claves comunes en castellano y validador de similitud con el usuario (SEG-15).
- Igualdad de tiempos del ingreso, medida (SEG-18).
- Medición de carga con 10 sesiones a la vez y p95 (PC-03).
- Permisos endurecidos: carpetas con herencia cortada, scripts de administrador en Program Files, sin Python como administrador, Caddy con `LocalService` (SEG-01, F-01).
- Caddy: OCSP apagado, solo HTTP/1.1 y HTTP/2, registro a archivo con rotación; firewall con registro de conexiones descartadas (SEG-17, SEG-19, F10, F-16).
- Clave de la autoridad propia cifrada y fuera del equipo; pedido de firma (CSR) para el certificado del organismo (SEG-05, SEG-14).
- Prueba de la restricción de nombre de la autoridad en el navegador (F3).
- Encabezado secreto entre el intermediario y la aplicación (SEG-04).
- `DEBUG` prohibido con acceso por red y `check --deploy` (SEG).
- Respaldos programados con retención y copia fuera del equipo (F-17).
- Modo `-SoloMostrar` y script de desinstalación del intermediario (F-10).
- Proteger el volumen de la base contra `down -v` (F-04).
- Repetir la prueba de red en el organismo con una computadora real de la Comisión, si T-272 se hizo en otra red (L1-10).
