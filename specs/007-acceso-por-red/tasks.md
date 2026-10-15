# Tareas 007 · Acceso por red

Plan: `specs/007-acceso-por-red/plan.md` (versión 2)

Despliegue: pendiente

> El tablero (`docs/tablero.md`) se genera de este archivo. Al aprobarse el despliegue, la línea de arriba pasa a `Despliegue: aprobado AAAA-MM-DD`.

Estados: pendiente · en curso · en verificación · terminada · bloqueada

Dos tareas que no dependen entre sí y no comparten archivos se pueden hacer en paralelo. El paralelismo se decide por archivos: la lista de cada tarea es la que vale.

**Ritmo de trabajo (ADR-0024 y ADR-0025).**

- Las ramas de tarea no tocan este archivo ni el tablero: el Coordinador los actualiza una vez por lote.
- La verificación de cada tarea queda en `specs/007-acceso-por-red/verificacion/T-NNN.md`. Lleva solo cifras, identificadores (REQ, T, ADR) y estados: nunca contraseñas, direcciones o nombres de la red del organismo, ni textos de procesos.
- Los umbrales están en el plan, escritos antes de medir. Como máximo dos rondas por medición: T-271 y su corrección T-281; T-278, su corrección T-279 y la repetición T-280.
- **Lo que toca Windows como administrador, las computadoras de la Comisión o una decisión lo hace el responsable**, siguiendo `entorno.md` e `instancia-piloto.md`. Lo demás (Docker, el clon, el `.env`, las pruebas) lo hace un agente, siempre por `scripts/piloto/compose.ps1` en el piloto.

**IDs.** T-269 a T-285 son de esta feature. El último ID usado antes era T-268 (015). T-280 a T-285 se sumaron en la versión 2: el Coordinador confirma que están libres antes de lanzar. La tabla va en el orden de ejecución, no en el de los números.

**Condiciones previas.**

- Los ADR-0061 a ADR-0064 son propuestos: el responsable los acepta con este plan, junto con los «Puntos para el responsable».
- T-282 se hace solo si el responsable aprueba el punto 1; T-283 y T-284, solo si aprueba el punto 4. Si no, se cierran sin cambios para que la cadena siga, y cambia lo que dice cada tarea afectada. Lo mismo para los puntos 2, 6, 19 y 20 dentro de T-272 a T-275.
- Las maquetas de la pantalla de cambio de clave (T-275) y del registro de accesos (T-282) las presenta el Coordinador junto con la aprobación de este plan. La tarea no arranca sin su maqueta aprobada.
- Los pedidos al área de sistemas no frenan T-269 a T-280: el corte vertical y la aceptación se pueden hacer en cualquier red, con una segunda computadora y el certificado propio. Sí frenan cargar el proceso reservado (punto 7 del plan).
- **P11.** El proceso reservado se carga en el piloto solo después de la aceptación (T-278, o T-280), del dictamen de auditoría sin hallazgos bloqueantes y de la línea `Despliegue: aprobado` de arriba. Antes, el piloto tiene solo material público.

**Órdenes de verificación.** Todas las tareas corren sus pruebas con un proyecto de Docker propio y la base de ese proyecto ya levantada. Nunca con `evaluon` (8000) ni `evaluon-piloto`:

```
docker compose -p <proyecto del encargo> --env-file <archivo del encargo> up -d db
docker compose -p <proyecto del encargo> --env-file <archivo del encargo> run --rm --no-deps app pytest <área de la tarea>
```

Las tareas que corren en paralelo corren solo su área. La suite completa la corre el Coordinador una vez por lote, sobre la rama combinada (ADR-0012). Lo que se prueba en Docker más allá de pytest usa también un proyecto propio (`evaluon-t269`, etc.) y se baja con `down -v` al terminar.

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-269 | Modo HTTPS detrás del intermediario (cookies seguras, protocolo del intermediario, sin arrancar con depuración), esqueleto de la instancia del piloto (`docker-compose.piloto.yml` con nombre e imagen propios, bloque del piloto en `.env.example`) y `scripts/piloto/compose.ps1`, que fija el proyecto y rechaza las órdenes peligrosas | REQ-110, REQ-116, REQ-117, REQ-109 | — | pendiente |
| T-270 | Intermediario en Windows: generador del `Caddyfile` y de la lista (hasta 10), plantilla endurecida, instalación con permisos y servicio `LocalService`, aplicación de la lista al firewall y al intermediario, desinstalación, autoridad propia limitada y pedido de firma, y pasos del responsable en `entorno.md` | REQ-109, REQ-110, REQ-116 | — | pendiente |
| T-271 | Prueba del corte vertical en la red, con el responsable: ingreso cifrado a una computadora de la lista con un usuario de prueba, el pliego del caso chico subido desde ella, sin advertencias, `http` redirigido, la clave ilegible en el tráfico, 0 páginas desde fuera de la lista, 0 servicios internos, inventario de puertos y la restricción de la autoridad | REQ-109, REQ-110, REQ-116 | T-269, T-270 | pendiente |
| T-281 | Corrección única del corte vertical, solo si T-271 no llega: todos los hallazgos en una tarea, un commit por hallazgo, y T-271 repetida completa una vez como verificación. Se cierra sin cambios si T-271 cumple todo | REQ-109, REQ-110, REQ-116 | T-271 | pendiente |
| T-272 | Esquema de acceso (una sola tarea) y bloqueo: 5 fallidos seguidos bloquean 15 minutos con el mismo mensaje y el mismo tiempo de respuesta, decidido dentro de una transacción con la fila bloqueada, con el backend propio como único backend, igual por comando | REQ-111 | T-281 | pendiente |
| T-273 | Computadora de origen en cada hecho de acceso, registro de la salida, comandos de administración en el equipo (`desbloquear_usuario`, `ver_accesos`, `responsable_sistema`) y claves de formulario prohibidas en el registro | REQ-112, REQ-113 | T-272 | pendiente |
| T-274 | Cierre de la sesión a los 30 minutos sin uso y a las 8 horas; el sondeo y las tres recargas automáticas no cuentan como uso (un test por pantalla); salidas de las sesiones vencidas (punto 6) | REQ-115, REQ-113 | T-273 | pendiente |
| T-275 | Cambio de clave que respeta el bloqueo y rechaza claves cortas, comunes o iguales a la actual; clave inicial obligatoria, también para los comandos; `clave_inicial`; `changepassword` y `createsuperuser` reemplazados | REQ-114, REQ-111 | T-274 | pendiente |
| T-282 | Pantalla «Registro de accesos» con el botón de desbloquear, solo para el responsable del sistema (punto 1) | REQ-112, REQ-113 | T-275 | pendiente |
| T-276 | Instancia separada del piloto: motor para una instancia a la vez con protección simétrica y `gpu.ps1` seguro, respaldos programados, vaciado con respaldo, actualización como despliegue, `scripts/models.sha256` en LF, instalación, reinicio, clave olvidada y cierre de la estabilización en `instancia-piloto.md` | REQ-117, REQ-116 | T-281 | pendiente |
| T-283 | Usuario de la base de la aplicación del piloto sin propiedad de las tablas, que en el registro solo lee y agrega (punto 4) | REQ-117, REQ-113 | T-272, T-276 | pendiente |
| T-284 | Aplicación del piloto en una red sin salida a internet, con una puerta que solo la une con el intermediario (punto 4) | REQ-117, REQ-116 | T-283 | pendiente |
| T-277 | Herramienta de medición: carga con 10 sesiones a la vez y el sondeo, línea de base de una sesión medida dos veces, tiempos de respuesta del ingreso, preparación de los usuarios de carga | REQ-109, REQ-111 | T-281 | pendiente |
| T-278 | Prueba de aceptación en la red, con el responsable: el caso chico en 5 de 5 secciones desde una computadora de la lista y todos los umbrales del plan, incluido el cierre del navegador real y la separación durante la estabilización | REQ-109, REQ-110, REQ-111, REQ-112, REQ-113, REQ-114, REQ-115, REQ-116, REQ-117 | T-275, T-276, T-277, T-282, T-284 | pendiente |
| T-279 | Corrección única de la aceptación, solo si T-278 no llega: todos los hallazgos en una tarea, un commit por hallazgo, verificada por el testeador. Se cierra sin cambios si T-278 cumple todo | REQ-109, REQ-110, REQ-111, REQ-112, REQ-113, REQ-114, REQ-115, REQ-116, REQ-117 | T-278 | pendiente |
| T-280 | Repetición completa de T-278 sobre el commit corregido, solo si hubo T-279 | REQ-109, REQ-110, REQ-111, REQ-112, REQ-113, REQ-114, REQ-115, REQ-116, REQ-117 | T-279 | pendiente |
| T-285 | Verificación del cierre de la estabilización, cuando el responsable la dé por terminada: lista de cierre aplicada y un agente que intenta entrar al piloto y es rechazado | REQ-117 | T-278 | pendiente |

## Paralelismo y recursos

- **Primer lote, en paralelo:** T-269 y T-270. No comparten archivos. Lo que comparten (nombres de variables, carpetas, encabezados) está fijado en el plan, «Definiciones compartidas».
- **Corte vertical:** T-271, y T-281 si hace falta. Nada más arranca hasta que T-281 se cierra (con o sin cambios), para no construir sobre un corte que no funciona.
- **Segundo lote, en paralelo:** T-272, T-276 y T-277. Sus archivos no se cruzan:
  - T-272: modelo, migraciones y backend de `accounts`, `audit/models.py` y su migración, `settings.py`, tests de bloqueo;
  - T-276: `docker-compose.sin-gpu.yml`, montajes de `docker-compose.yml`, el bloque del piloto en `.env.example`, `.gitattributes`, `scripts/piloto/` (salvo `compose.ps1`), `instancia-piloto.md`, `tests/test_instancia_piloto.py`;
  - T-277: `scripts/red/medir_carga.py` y su test.
- **Cadena del acceso:** T-272, T-273, T-274, T-275 y T-282, de a una. Comparten `settings.py` (T-272, T-274, T-275), `backends.py` (T-272, T-273), `permissions.py` (T-273, T-275), `apps.py` (T-273), `views.py`, `urls.py` y `_cabecera.html` (T-275, T-282).
- **Cadena del piloto:** T-276, T-283 y T-284, de a una (comparten `docker-compose.piloto.yml`, `actualizar.ps1`, `instancia-piloto.md` y `tests/test_instancia_piloto.py`). T-283 corre en paralelo con T-273 y T-274.
- **Esquema:** solo T-272 genera migraciones de Django (`accounts` y `audit`, juntas). T-283 cambia permisos de la base del piloto con un script, no el esquema.
- **GPU:** solo T-278 y T-280 usan el 27B, el del piloto, y una sola tarea a la vez. El motor se mueve con `gpu.ps1` según el punto 3 del plan: durante la estabilización, el Coordinador avisando al responsable. T-271 levanta solo la base, la migración y la aplicación del piloto.
- **Proyectos de Docker:** el proyecto `evaluon-piloto` lo crea el agente de T-271, por `compose.ps1`, dentro de `C:\EVALUON-piloto\` que creó el responsable. Ningún otro agente lo crea ni lo baja.
- **Necesitan a una persona:** T-271, T-278, T-280 y la repetición de T-281 (Windows, red y las computadoras A y B); las maquetas de T-275 y T-282; T-285 (la lista de cierre).
- **Máximo sugerido en paralelo:** tres desarrolladores (por ejemplo T-272, T-276 y T-277).

## Revisión con el primer producto (ADR-0024)

Lo que T-271 a T-280 no alcancen sin perder un requisito ni violar un principio se anota aquí, con su impacto, para revisarlo con el primer producto. Vacío por ahora.

| Qué | Medida y umbral | Impacto | De qué tarea |
|---|---|---|---|

## Detalle

### T-269 · Modo HTTPS detrás del intermediario, esqueleto del piloto y `compose.ps1`

- **Requisitos:** REQ-110, REQ-116, REQ-117, REQ-109
- **Nivel de verificación:** plena (configuración compartida y principios P4 y P5).
- **Qué hay que hacer:**
  1. **`settings.py`**, bloque «Acceso por red (plan 007)», con una función que lee el entorno, como `reasoning_levels`.
     - `EVALUON_HTTPS` (`env_bool`, falso por omisión). Con verdadero: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` y `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`.
     - Con `EVALUON_HTTPS` y `DJANGO_DEBUG` verdaderos a la vez, `ImproperlyConfigured`.
     - Sin `SECURE_SSL_REDIRECT`: redirige el intermediario, y el chequeo de salud del contenedor pide por `http` adentro. El HSTS lo pone el intermediario (punto 18).
     - Corregir el comentario de sesiones que dice que la cookie segura es «de la feature 007».
  2. **`docker-compose.yml`**: `EVALUON_HTTPS: ${EVALUON_HTTPS:-false}` en el entorno de `x-app`; montar `./docker-compose.piloto.yml` en `x-app` y en `app`, solo para los tests (regla de T-264).
  3. **`docker-compose.piloto.yml`** (nuevo): `name: evaluon-piloto` e `image: evaluon-app:piloto` en `migrate`, `app`, `worker` y `portal_worker`. Sin puertos ni redes nuevos. Para levantar la aplicación sin motores se usa `up -d --no-deps`.
  4. **`.env.example`**, bloque **comentado** «Instancia del piloto (plan 007, ADR-0064)»:
     - empieza por `COMPOSE_PROJECT_NAME=evaluon-piloto`, con el aviso de lo que pasa si falta (actuaría sobre 8000);
     - sigue con las variables del plan, una línea cada una sobre qué poner;
     - las direcciones de ejemplo son solo del rango de documentación (`192.0.2.0/24`);
     - ninguna línea sin comentar cambia.
  5. **`scripts/piloto/compose.ps1`** (nuevo), según el plan («Scripts del piloto»):
     - siempre llama con `--project-directory`, `--env-file` y `-p evaluon-piloto` fijos;
     - se niega si el `.env` no lo identifica como piloto o si `APP_PORT` es 8000;
     - rechaza `-p`, `--project-name`, `-f`, `--file`, `--env-file`, `--project-directory`, `down -v`, `down --volumes`, `rm -v` y `volume rm`, con un mensaje en lenguaje llano;
     - guardado en UTF-8 con BOM, para que Windows PowerShell 5.1 lea bien los acentos.
  6. **Tests.**
     - `tests/accounts/test_https_mode.py`:
       - con el modo HTTPS y `X-Forwarded-Proto: https`, las cookies de sesión y CSRF salen con `Secure`;
       - un POST con `Origin: https://<dirección>` pasa el control CSRF;
       - sin el modo, nada cambia;
       - con el modo y depuración a la vez, la configuración no arranca.
     - `tests/test_instancia_piloto.py` (nuevo):
       - el archivo del piloto nombra el proyecto y una imagen distinta de `evaluon-app:local`, y no agrega puertos ni redes;
       - `EVALUON_HTTPS` llega con el mismo valor por omisión que `settings.py`;
       - el bloque de `.env.example` trae `COMPOSE_PROJECT_NAME` y el archivo del piloto;
       - `compose.ps1` tiene BOM, fija los tres parámetros y nombra cada orden rechazada (revisión del texto: PowerShell no corre en el contenedor).
- **Archivos:** `evaluon/settings.py`, `docker-compose.yml`, `docker-compose.piloto.yml` (nuevo), `.env.example`, `scripts/piloto/compose.ps1` (nuevo), `tests/accounts/test_https_mode.py` (nuevo), `tests/test_instancia_piloto.py` (nuevo), `tests/test_compose_env.py` (si el test de montajes lista los archivos).
- **Verificación:**
  - Pruebas de `tests/accounts`, `tests/test_instancia_piloto.py` y `tests/test_compose_env.py` con la orden de «Órdenes de verificación».
  - `docker compose config` con la combinación de uso más `docker-compose.piloto.yml`, sin errores y con el proyecto `evaluon-piloto`.
  - En Windows, `compose.ps1` en una carpeta temporal: con un `.env` sin `COMPOSE_PROJECT_NAME`, se niega; con `down -v` y con `-p`, también. Con el `.env` correcto, solo `config`: nunca `up` con el nombre `evaluon-piloto`.
  - Con el proyecto `evaluon-t269`, `APP_PORT` libre, `EVALUON_HTTPS=true` y sin motores: `curl.exe -H "X-Forwarded-Proto: https" -H "Host: <dirección de ejemplo>"` al ingreso devuelve 200 con `csrftoken` `Secure`. Al terminar, `down -v` y borrar la imagen que haya creado.
- **No tocar:** `accounts` salvo sus tests de modo HTTPS, `audit`, `scripts/red/`, 8000, el nombre `evaluon-piloto` en Docker.

### T-270 · Intermediario en Windows, lista, firewall y certificados

- **Requisitos:** REQ-109, REQ-110, REQ-116
- **Nivel de verificación:** plena (seguridad de la red, P4 y P5).
- **Qué hay que hacer** (carpetas y permisos, según el plan, «Definiciones compartidas»):
  1. **`scripts/red/caddy.py`** (Python 3.12, solo la biblioteca estándar). Corre **sin** administrador. Lee el `.env` del piloto y se niega, con mensajes en lenguaje llano, si:
     - falta `COMPOSE_PROJECT_NAME=evaluon-piloto`;
     - `APP_PORT` es 8000;
     - `EVALUON_ADDRESS` no es un nombre ni una IPv4;
     - `EVALUON_SERVER_IP` no es una IPv4;
     - `EVALUON_COMPUTERS` no cumple su formato (minúsculas, IPv4, sin repetidos, ninguna igual a la del equipo, 10 como máximo).

     Escribe en `C:\EVALUON-piloto\entrada\` el `Caddyfile` y `computadoras.txt` (nombre y dirección, para el firewall y para que el responsable los vea).
  2. **`scripts/red/Caddyfile.plantilla`.**
     - Opciones globales: `admin off`, `auto_https off`, `ocsp_stapling off`, `servers { protocols h1 h2 }`, `skip_install_trust`, almacenamiento en `C:\ProgramData\EVALUON-Red\datos\`, `log` a archivo con rotación en `registros\` y, si se entra por IP, `default_sni` con esa IP.
     - Sitio `http://<dirección>`: corta (`abort`) lo que no viene de la lista ni del equipo, y redirige el resto a `https` con 308.
     - Sitio `https://<dirección>`:
       - `tls` con `C:\ProgramData\EVALUON-Red\certificados\evaluon.crt` y `evaluon.key`;
       - el mismo corte;
       - `map` de la dirección al nombre (la del equipo da `equipo-del-sistema`);
       - `reverse_proxy 127.0.0.1:<APP_PORT>` con `header_up X-Evaluon-Computer`;
       - `Strict-Transport-Security "max-age=31536000"` solo si la dirección es un nombre (punto 18);
       - registro de acceso al mismo archivo.

     Los nombres exactos de las opciones se fijan con la documentación de la versión.
  3. **`scripts/red/instalar-red.ps1`** (como administrador, una vez; con `-SoloMostrar`). Corre desde un clon recién hecho.
     - Comprueba que el clon esté limpio y en el commit que escribe el responsable.
     - Baja el zip de Windows amd64 de la versión fijada de la publicación oficial y lo comprueba con `Get-FileHash -Algorithm SHA512` contra `scripts/red/caddy.sha512`, copiado literal de `caddy_<versión>_checksums.txt`. Verificar la firma de las sumas es opcional y se anota.
     - Crea las tres carpetas con la herencia cortada y los permisos del plan (`icacls`).
     - Copia `caddy.exe`, `aplicar-red.ps1` y `desinstalar-red.ps1` a `C:\Program Files\EVALUON-Red\`.
     - Registra el servicio `EVALUON-Caddy` con `obj= "NT AUTHORITY\LocalService"`, arranque automático y reinicio ante fallas.
     - No lo arranca: lo arranca `aplicar-red.ps1`.
  4. **`scripts/red/aplicar-red.ps1`** (como administrador, desde `C:\Program Files\EVALUON-Red\`; con `-SoloMostrar`). No corre Python ni código del clon: solo lee `entrada\`.
     - Muestra la lista de computadoras y el nombre y el vencimiento del certificado, y pide confirmación.
     - Valida el `Caddyfile` con `caddy.exe validate`.
     - Mueve el `Caddyfile` y los certificados nuevos de `entrada\` a `C:\ProgramData\EVALUON-Red\` (la clave no queda en `entrada\`).
     - Crea o actualiza la regla «EVALUON piloto»: TCP 80 y 443, programa `caddy.exe`, direcciones de la lista más la del equipo, `-Profile Any`. Desactiva toda otra regla de entrada de `caddy.exe`.
     - Se detiene si el firewall está apagado en el perfil de la red actual.
     - Activa el registro de conexiones descartadas del firewall de Windows (`Set-NetFirewallProfile -LogBlocked True`), para que también queden anotados los intentos desde fuera de la lista.
     - Reinicia el servicio (`Restart-Service`) y avisa si al certificado le quedan menos de 30 días.
  5. **`scripts/red/desinstalar-red.ps1`** (como administrador): detiene y borra el servicio y la regla. Las carpetas quedan. Es el «Volver atrás» de `entorno.md`.
  6. **`scripts/red/crear-certificados.sh`** (Git Bash, con el `openssl` de Git para Windows y `MSYS_NO_PATHCONV=1`). Tres modos:
     - **Autoridad y certificado del servidor:**
       - Si no existe, crea la autoridad en la carpeta de la unidad extraíble que se le indica; se niega si está bajo `C:\EVALUON-piloto\` o en el disco del sistema. La clave va cifrada con AES-256 y una frase de paso que escribe el responsable.
       - La autoridad dura 3 años: `CA:TRUE` con `pathlen:0`, `extendedKeyUsage=serverAuth` y restricciones de nombre críticas de los dos tipos. `iPAddress`: solo las /32 de EVALUON y del equipo, con IPv6 excluido. `dNSName`: solo el nombre de EVALUON, o `.invalid` si no hay nombre.
       - Después crea `evaluon.key` y `evaluon.crt` (397 días, nombres alternativos con la dirección y la del equipo, `serverAuth`, con la cadena) en `entrada\certificados\`.
       - Muestra el vencimiento y la huella SHA-256 de la raíz. Con la autoridad ya creada, solo renueva el del servidor.
     - **`--pedido`:** genera `evaluon.key` y `evaluon.csr` en `entrada\` para que el área de sistemas los firme, sin comodín.
     - **`--prueba-otro-nombre`:** un certificado para `127.0.0.2`, fuera de la restricción, para probarla en T-271.
  7. **`specs/007-acceso-por-red/entorno.md`**, para una persona no técnica: cada comando, lo que tiene que verse y cómo volver atrás. Secciones:
     - Instalar la red del piloto, incluido dejar en cada computadora de la lista un acceso directo o favorito con la dirección `https://`.
     - Dónde mirar los registros: el de Caddy y el de conexiones descartadas del firewall.
     - Cambiar la lista.
     - Pasar al certificado del organismo: el pedido de firma; un PFX se convierte con `openssl pkcs12` y su frase llega aparte.
     - Renovar.
     - Comprobar, con las líneas de `Test-NetConnection <dirección> -Port N` para pegar en A y en B y `curl.exe -sI`.
     - Captura con `pktmon`: como administrador, `pktmon start --capture`, `pktmon stop`, `pktmon etl2pcap` y la búsqueda de la clave con `findstr`; borrar la captura después.
     - Inventario de puertos.
     - Volver atrás.
     - Qué pedir al área de sistemas.

     Solo direcciones de ejemplo de documentación.
  8. **Tests.**
     - `tests/red/test_caddy_config.py`:
       - una lista válida genera el `Caddyfile` esperado;
       - 11 computadoras, repetidos, direcciones inválidas, falta de `COMPOSE_PROJECT_NAME` o `APP_PORT` 8000 se rechazan con su mensaje;
       - el equipo siempre entra como `equipo-del-sistema`;
       - el sitio `http` corta y redirige;
       - el sitio `https` tiene `tls` con los dos archivos, el corte, el `map`, el reenvío a `127.0.0.1` y HSTS solo con nombre;
       - las opciones globales están todas;
       - no hay ACME, correo ni hosts externos.
     - `tests/red/test_scripts_red.py`:
       - los `.ps1` tienen BOM;
       - `aplicar-red.ps1` no llama a Python ni lee el clon;
       - `instalar-red.ps1` usa `LocalService` y `SHA512`;
       - ningún archivo de `scripts/red/` tiene direcciones fuera de los rangos de documentación y de `127.0.0.0/8`.
- **Archivos:** `scripts/red/caddy.py`, `Caddyfile.plantilla`, `instalar-red.ps1`, `aplicar-red.ps1`, `desinstalar-red.ps1`, `caddy.sha512`, `crear-certificados.sh` (todos nuevos en `scripts/red/`), `tests/red/__init__.py`, `tests/red/test_caddy_config.py`, `tests/red/test_scripts_red.py` (nuevos), `specs/007-acceso-por-red/entorno.md` (nuevo).
- **Verificación:**
  - Pruebas de `tests/red`.
  - En Windows, sin administrador:
    - el `Caddyfile` que genera `caddy.py` con un `.env` de ejemplo lo acepta `caddy.exe adapt` (binario bajado a una carpeta temporal y verificado con SHA-512);
    - `instalar-red.ps1 -SoloMostrar` y `aplicar-red.ps1 -SoloMostrar` listan lo que harían. Si Windows pide administrador para leer las reglas, lo corre el responsable en T-271.
  - En Git Bash en Windows (no en el contenedor), sobre carpetas temporales:
    - los tres modos de `crear-certificados.sh` funcionan;
    - `openssl x509 -text` muestra EKU, restricciones de los dos tipos y nombres alternativos;
    - `openssl verify -CAfile` pasa con el certificado del servidor y falla con el de otro nombre.
  - Los scripts de administrador, en modo real, los corre el responsable en T-271: hasta ahí, su verificación es revisión estática y `-SoloMostrar`.
- **No tocar:** el firewall, los servicios y la red de Windows (solo el responsable), `settings.py`, los compose, 8000.

### T-271 · Prueba del corte vertical en la red

- **Requisitos:** REQ-109, REQ-110, REQ-116
- **Nivel de verificación:** plena (criterio de la feature y P4).
- **Necesita:** al responsable, una computadora de la lista (A) y una de fuera (B; puede ser A sacada de la lista). No usa la GPU.
- **No arranca sin:** T-269 y T-270 integradas.
- **Qué hay que hacer:** el testeador arma la lista de pasos con `entorno.md` y la planilla de resultados; el responsable ejecuta lo suyo y pasa salidas y capturas.
  1. **Responsable:**
     - `instalar-red.ps1` como administrador, desde un clon recién hecho en el commit de `main`; antes, `-SoloMostrar`.
     - Activa «Start Docker Desktop when you sign in».
  2. **Agente, por `compose.ps1`:**
     - clona `C:\EVALUON-piloto\evaluon\` en el commit de `main`, con el push desactivado;
     - arma el `.env` con el bloque del piloto y claves generadas;
     - `compose.ps1 config` nombra `evaluon-piloto`; `compose.ps1 down -v` y `compose.ps1 -p evaluon ps` se rechazan;
     - `compose.ps1 up -d db migrate`, después `compose.ps1 up -d --no-deps app`;
     - `crear_usuario` de un usuario de prueba con rol de la Comisión;
     - `docker compose ls` muestra 8000 sin cambios.
     - No se carga nada reservado.
  3. **Responsable:**
     - `crear-certificados.sh` con la autoridad en su unidad extraíble;
     - completa la lista con A;
     - `caddy.py` y `aplicar-red.ps1`, como administrador;
     - instala la raíz en A.
  4. **Desde A:**
     - la dirección cifrada muestra el ingreso sin advertencias (captura), y el certificado que ve el navegador es el de EVALUON (se anota el emisor);
     - el usuario ingresa y **sube el pliego del caso chico** (público) en «Nuevo procedimiento». La lectura queda en espera: no hay motor ni `worker`;
     - `curl.exe -sI http://<dirección>/ingresar/` da 308 del intermediario hacia `https`, sin cuerpo de la aplicación;
     - con una captura de `pktmon` en el equipo durante un ingreso, la clave aparece 0 veces.
  5. **Puertos:**
     - desde B, `http` y `https` no conectan y las líneas de `Test-NetConnection` dan 0 puertos abiertos;
     - desde A, solo 80 y 443;
     - en el equipo, el inventario (`Get-NetTCPConnection -State Listen` y `Get-NetUDPEndpoint` con su proceso) muestra fuera del propio equipo solo `caddy.exe` en TCP 80 y 443 y servicios de Windows que se anotan, sin UDP 443.
  6. **La lista:** sacar A y aplicar: A no llega. Volver a ponerla: llega. `git status` del clon sigue limpio.
  7. **La restricción de la autoridad:**
     - el responsable instala la raíz también en el equipo, solo para esta prueba;
     - el agente sirve un rato con Caddy, fuera del servicio, el certificado de `--prueba-otro-nombre` en `https://127.0.0.2:8443`;
     - en Edge (y Chrome, si lo usa la Comisión), el navegador lo rechaza por la restricción y no solo por el nombre;
     - `certutil -verify` en A queda como prueba complementaria;
     - después, la raíz se quita del equipo.
- **Umbral:** el del corte vertical en el plan: 0 advertencias, 0 páginas por `http`, 0 apariciones de la clave, 0 páginas desde B, solo 80 y 443 desde A, inventario conforme, la lista cambia sin tocar el código, el pliego se sube por la conexión cifrada y la restricción se cumple en el navegador.
- **Qué entrega:** `verificacion/T-271.md` con el commit, cada punto contra su umbral y los hallazgos. Computadoras «A» y «B», sin datos del organismo. La instancia mínima queda para las tareas siguientes.
- **Archivos:** solo `specs/007-acceso-por-red/verificacion/T-271.md`.
- **No tocar:** código, scripts, 8000. Un hallazgo es de T-281.

### T-281 · Corrección única del corte vertical

- **Requisitos:** REQ-109, REQ-110, REQ-116
- **Nivel de verificación:** plena.
- **No arranca sin:** T-271 terminada, con su verificación registrada.
- **Qué hay que hacer:** si T-271 no llegó a algún umbral, corregir **todos** sus hallazgos en esta sola tarea, con un commit por hallazgo y su test que falla antes y pasa después cuando el hallazgo es de código. Si el hallazgo obliga a pasar a la alternativa C del ADR-0061 (certificado de cliente), se frena y lo decide el responsable. Si T-271 cumplió todo, se cierra sin cambios.
- **Archivos:** los de T-269 y T-270 que el hallazgo señale, y `specs/007-acceso-por-red/verificacion/T-281.md`.
- **Verificación:** las pruebas del área de cada hallazgo y, con el responsable, **T-271 repetida completa una vez** sobre el commit corregido. Lo que siga sin llegar pasa a «Revisión con el primer producto». Si se pierde un requisito o se viola un principio, el responsable decide si hay otra ronda.
- **No tocar:** umbrales; archivos que ningún hallazgo señale.

### T-272 · Esquema de acceso y bloqueo tras 5 intentos

- **Requisitos:** REQ-111
- **Nivel de verificación:** plena (esquema y seguridad).
- **No arranca sin:** T-281 cerrada. Corre sola entre las tareas que tocan el esquema.
- **Qué hay que hacer:**
  1. `accounts/models.py`: `failed_logins`, `locked_until`, `must_change_password` y, con el punto 2, `is_system_manager`, con su migración (desde cero y hacia atrás).
  2. `audit/models.py`: los cinco tipos de hecho, con una migración que reemplaza la restricción, como la `0008`.
  3. `accounts/backends.py` (nuevo): `LockoutBackend`, sobre el `ModelBackend` de Django.
     - Primero calcula la clave, siempre. Si el usuario no existe, contra un usuario vacío, como Django.
     - Después, dentro de una transacción con `select_for_update` del usuario, decide con el estado de ese momento:
       - bloqueado: rechaza sin contar, aunque la clave sea correcta (`PermissionDenied`: mismo mensaje y señal de ingreso fallido);
       - clave equivocada: `register_failed_attempt`, que al quinto bloquea `LOGIN_LOCKOUT_MINUTES`, vuelve la cuenta a 0 y deja `lockout`;
       - clave correcta y usuario activo: vuelve la cuenta a 0 si no lo estaba.
     - `register_failed_attempt` y `is_locked` según el plan («Funciones compartidas»).
     - Los intentos durante el bloqueo no cuentan ni lo alargan (punto 15).
  4. `settings.py`: `AUTHENTICATION_BACKENDS = ["evaluon.accounts.backends.LockoutBackend"]`, sin `ModelBackend`; `LOGIN_FAILURE_LIMIT = 5` y `LOGIN_LOCKOUT_MINUTES = 15`.
  5. Tests, `tests/accounts/test_lockout.py`, con el reloj controlado, por pantalla y por comando:
     - 5 fallidos y la clave correcta, rechazada con el mismo mensaje; a los 14 min 59 s, rechazada; a los 15 min, ingresa;
     - 4 fallidos y uno correcto: ingresa y la cuenta queda en 0;
     - 3 mensajes idénticos (inexistente, clave equivocada, bloqueado), en la pantalla y en el comando;
     - con un usuario bloqueado, el cálculo de la clave corre;
     - `lockout` una sola vez;
     - `AUTHENTICATION_BACKENDS` comparado literal;
     - con transacciones reales y dos hilos: si el quinto fallido bloquea mientras otro pedido con la clave correcta espera la fila, ese pedido se rechaza.
- **Archivos:** `evaluon/accounts/models.py`, una migración nueva en `evaluon/accounts/migrations/`, `evaluon/accounts/backends.py` (nuevo), `evaluon/audit/models.py`, una migración nueva en `evaluon/audit/migrations/`, `evaluon/settings.py`, `tests/accounts/test_lockout.py` (nuevo), los tests de `audit` que listen tipos de hecho.
- **Verificación:** pruebas de `tests/accounts` y `tests/audit`; migrar desde cero y volver a la migración anterior de cada app; los tests de ingreso existentes pasan.
- **No tocar:** `apps.py`, `permissions.py`, vistas, plantillas y comandos.

### T-273 · Computadora de origen, registro de accesos y comandos de administración

- **Requisitos:** REQ-112, REQ-113
- **Nivel de verificación:** plena (registro de auditoría, P6).
- **No arranca sin:** T-272 integrada.
- **Qué hay que hacer:**
  1. **`accounts/origin.py`** (nuevo): `request_origin(request)`.
     - Con `X-Evaluon-Computer` y `X-Forwarded-For`: el nombre y la última dirección.
     - Sin ellos: `acceso-directo-local`, sin dirección.
     - `COMMAND_ORIGIN` = `equipo-del-sistema`.
     - Valores acotados en largo.
  2. **`apps.py`:**
     - `login` y `login_failed` llevan `origin`; el del ingreso se guarda también en la sesión;
     - receptor de `user_logged_out`: `logout` con `origin` y `reason`;
     - con el punto 20, el nombre escrito se guarda tal cual solo si tiene forma de usuario (caracteres permitidos, hasta 150); si no, «texto que no es un usuario, N caracteres».
  3. **`backends.py`:** `lockout` con el origen. **`permissions.authenticate_command`:** `login` con `COMMAND_ORIGIN`.
  4. **Comandos de administración**, con el punto 2: los corre quien administra el equipo, sin usuario de EVALUON, como `crear_usuario`. Cada uno deja su hecho con «administración del equipo» como actor y `COMMAND_ORIGIN`.
     - `desbloquear_usuario <usuario>`: usuario inexistente, error; no bloqueado, lo dice y no cambia nada; bloqueado, vacía el bloqueo y la cuenta y deja `unlock`.
     - `ver_accesos [--desde] [--hasta] [--de]`: los hechos de acceso en orden de fecha, con hora de Buenos Aires, hecho, usuario o nombre, «computadora (según su dirección)» y canal.
     - `responsable_sistema <usuario> {si,no}`: pone o quita la marca y deja `user_role_changed`.

     Con la alternativa del punto 2, los comandos piden `--usuario` y el rol de lectura y escritura, como `rol_comision`, y no existe `responsable_sistema`.
  5. **`audit/services.py`:** `FORBIDDEN_DETAIL_KEYS` suma `old_password`, `new_password1` y `new_password2`.
  6. **Tests:**
     - origen con encabezados, directo y por comando;
     - REQ-113: ingreso, fallido, bloqueo y desbloqueo con encabezados de una computadora de la lista, y `ver_accesos` muestra los 4 con usuario o nombre, computadora, fecha y hora;
     - el desbloqueo deja ingresar enseguida (REQ-112);
     - «Salir» deja `logout`;
     - las claves nuevas de `FORBIDDEN_DETAIL_KEYS` se rechazan;
     - con el punto 20, el nombre con forma de clave se reemplaza.
- **Archivos:** `evaluon/accounts/origin.py` (nuevo), `evaluon/accounts/apps.py`, `evaluon/accounts/backends.py`, `evaluon/accounts/permissions.py`, `evaluon/accounts/management/commands/desbloquear_usuario.py`, `ver_accesos.py` y `responsable_sistema.py` (nuevos), `evaluon/audit/services.py`, `tests/accounts/test_origin.py`, `test_unlock.py` y `test_ver_accesos.py` (nuevos), `tests/accounts/test_access_log.py`, `tests/audit/` (test de las claves prohibidas).
- **Verificación:** pruebas de `tests/accounts` y `tests/audit`.
- **No tocar:** modelos y migraciones, `settings.py`, vistas y plantillas, middleware.

### T-274 · Cierre de la sesión por inactividad y a las 8 horas

- **Requisitos:** REQ-115, REQ-113
- **Nivel de verificación:** plena (lógica de sesión).
- **No arranca sin:** T-273 integrada.
- **Qué hay que hacer:**
  1. **`accounts/session_policy.py`** (nuevo): middleware después de `AuthenticationMiddleware` y antes de `LoginRequiredMiddleware`.
     - Guarda en la sesión el ingreso y el último uso.
     - Si pasaron `SESSION_MAX_HOURS` desde el ingreso, o `SESSION_IDLE_MINUTES` sin uso: pone el motivo, llama a `logout` y manda al ingreso con `next`.
     - Si no, y el pedido no trae `X-Evaluon-Poll` ni `auto=1`, actualiza el último uso.
  2. **Salidas de las sesiones vencidas** (punto 6). A lo sumo cada 5 minutos, en algún pedido, recorre las sesiones de la base:
     - las vencidas por inactividad o por las 8 horas dejan `logout` con `reason`, `expired_at` y el origen guardado, y se borran;
     - un `clearsessions` posterior no encuentra nada que registrar.

     Con la alternativa del punto 6, este paso no se hace.
  3. **`settings.py`:** la línea de `MIDDLEWARE`, `SESSION_IDLE_MINUTES = 30` y `SESSION_MAX_HOURS = 8`, y el comentario de sesiones. Sin cambios en `SESSION_COOKIE_AGE`, `SESSION_EXPIRE_AT_BROWSER_CLOSE` ni `SESSION_SAVE_EVERY_REQUEST`.
  4. **Recargas y sondeo** (nada cambia a la vista):
     - `static/journey/recorrido.js` manda `X-Evaluon-Poll: 1`;
     - `journey/nuevo.html` y `journey/s1_pliego_borrador.html` recargan con `auto=1` en la dirección (`meta refresh` con `url`);
     - `static/journey/s3_ofertas.js` recarga con `auto=1`.
  5. **Tests:**
     - a los 29 minutos sin uso sigue y a los 31 lleva al ingreso;
     - el sondeo durante 40 minutos no mantiene la sesión;
     - **una prueba por cada una de las tres pantallas que se recargan solas**: 40 minutos de recargas no la mantienen;
     - con uso cada 20 minutos, a las 8 horas lleva al ingreso;
     - lo guardado antes sigue después de volver a ingresar;
     - `logout` con `idle` o `max_age` y su origen;
     - con el punto 6, la sesión vencida que nadie retomó deja su `logout` con `expired_at`;
     - la cookie sigue sin fecha de vencimiento.

     El test de 8 horas de `test_session.py` se ajusta a usos cada menos de 30 minutos.
- **Archivos:** `evaluon/accounts/session_policy.py` (nuevo), `evaluon/settings.py`, `evaluon/static/journey/recorrido.js`, `evaluon/static/journey/s3_ofertas.js`, `evaluon/templates/journey/nuevo.html`, `evaluon/templates/journey/s1_pliego_borrador.html`, y si hace falta para armar la dirección, `evaluon/journey/views/nuevo.py` y `evaluon/journey/temas/s1_pliego.py`; `tests/accounts/test_session.py`, `tests/accounts/test_session_policy.py` (nuevo), los tests de `tests/journey/` de esas pantallas.
- **Verificación:** pruebas de `tests/accounts` y `tests/journey`.
- **No tocar:** `apps.py`, modelos, el resto de las pantallas.

### T-275 · Cambio de clave, clave inicial y comandos reemplazados

- **Requisitos:** REQ-114, REQ-111
- **Nivel de verificación:** plena (seguridad y una pantalla nueva).
- **No arranca sin:** T-274 integrada y la maqueta de la pantalla de cambio de clave y de su enlace aprobada por el responsable.
- **Qué hay que hacer:**
  1. **Vista `cambiar-clave/`** (`accounts:password_change`) sobre la de Django. Rótulos «Clave actual», «Clave nueva», «Repita la clave nueva»; mensajes con «clave».
     - Con el usuario bloqueado (`is_locked`): rechaza sin mirar la clave, sin contar y sin renovar el bloqueo.
     - Clave actual equivocada: `register_failed_attempt`, y `login_failed` con el usuario de la sesión y `form: password_change`. Si con eso queda bloqueado, cierra esa sesión (`locked_in_form`).
     - La nueva, distinta de la actual (`check_password`): «La clave nueva tiene que ser distinta de la actual».
     - Cambio correcto: vuelve `must_change_password` a falso, deja `password_change`, conserva la sesión y lleva al inicio.
  2. **`templates/accounts/cambiar_clave.html`** según la maqueta, y el enlace «Cambiar clave» junto a «Salir» en `_cabecera.html`.
  3. **`accounts/password_policy.py`** (nuevo): un usuario con `must_change_password` solo puede pedir el cambio de clave, la salida y el ingreso. Todo lo demás va al cambio de clave, incluidos el sondeo y las recargas.
  4. **`settings.py`:**
     - la línea de `MIDDLEWARE`;
     - `CommonPasswordValidator` y, con el punto 19, `UserAttributeSimilarityValidator` y una lista corta propia en castellano (`evaluon/accounts/claves-comunes.txt`);
     - `evaluon.accounts` antes de `django.contrib.auth` en `INSTALLED_APPS`, para que sus comandos reemplacen a los de Django.
  5. **Comandos:**
     - `crear_usuario` deja la clave inicial marcada, y la ayuda lo dice;
     - `clave_inicial <usuario>` (como dice el punto 2) pide la clave dos veces, la valida, la guarda con la marca y vuelve la cuenta a 0. Si estaba bloqueado, lo desbloquea con su `unlock` (punto 14). Deja `initial_password`;
     - `changepassword` y `createsuperuser` se reemplazan por comandos propios con el mismo nombre, que no cambian nada y explican que se usa `clave_inicial` o `crear_usuario`.
  6. **`permissions.authenticate_command`:** un usuario con clave inicial no pasa (punto 13). Mensaje: «Tiene que cambiar su clave inicial: ingrese por la pantalla y cámbiela antes de usar los comandos.». No deja `login`; deja `rejected` con el motivo `must_change_password`.
  7. Revisar los scripts de evals y de medición que dan de alta usuarios y después usan comandos (los de los tests usan el ORM y no cambian); si alguno usa `crear_usuario`, se ajusta.
  8. **Tests:**
     - REQ-114: con clave inicial, ninguna sección; clave corta, común, parecida al usuario (punto 19) e igual a la actual, rechazadas con su motivo; sin la clave actual correcta, rechazada y contada;
     - con el usuario bloqueado, el formulario no acepta la clave ni renueva el bloqueo;
     - el quinto error en el formulario cierra esa sesión;
     - el cambio correcto quita la marca y queda registrado;
     - `crear_usuario` marca;
     - `clave_inicial`: marca, desbloqueo y hechos;
     - un comando con clave inicial se rechaza;
     - `changepassword` y `createsuperuser` no cambian nada;
     - el enlace está en el encabezado.
- **Archivos:** `evaluon/accounts/views.py`, `evaluon/accounts/urls.py`, `evaluon/accounts/password_policy.py` (nuevo), `evaluon/accounts/permissions.py`, `evaluon/accounts/management/commands/crear_usuario.py`, `clave_inicial.py`, `changepassword.py` y `createsuperuser.py` (los tres nuevos), `evaluon/accounts/claves-comunes.txt` (nuevo, con el punto 19), `evaluon/templates/accounts/cambiar_clave.html` (nuevo), `evaluon/templates/journey/_cabecera.html`, `evaluon/static/css/` (solo si la maqueta lo pide), `evaluon/settings.py`, `tests/accounts/test_password_change.py` y `test_clave_inicial.py` (nuevos), `tests/accounts/test_crear_usuario.py`.
- **Verificación:** pruebas de `tests/accounts` y `tests/journey`. El Coordinador abre la pantalla y la compara con la maqueta.
- **No tocar:** `backends.py` (usa sus funciones sin cambiarlas), modelos y migraciones, `session_policy.py`, las secciones.

### T-282 · Pantalla «Registro de accesos» con desbloqueo

- **Requisitos:** REQ-112, REQ-113
- **Nivel de verificación:** plena (pantalla con permiso y registro).
- **No arranca sin:** T-275 integrada, el punto 1 aprobado y su maqueta aprobada. Si el responsable elige la alternativa del punto 1, se cierra sin cambios.
- **Qué hay que hacer:**
  1. Página `accesos/`, solo para usuarios con `is_system_manager`. Cualquier otro recibe 403 y deja `rejected`.
  2. Arriba, los usuarios bloqueados ahora, cada uno con «Desbloquear» (formulario POST con CSRF). Al usarlo deja `unlock` con el responsable como actor y su origen.
  3. Debajo, los hechos de acceso más recientes primero, con fecha y hora, hecho, usuario o nombre, «computadora (según su dirección)» y canal, con filtro por fecha y por usuario.
  4. El enlace «Registro de accesos» en el encabezado, solo para el responsable.
  5. **Tests:**
     - permiso y rechazo registrado;
     - el desbloqueo por pantalla con encabezados de otra computadora deja ingresar enseguida y queda con quién, cuándo y desde dónde;
     - REQ-113: los 4 hechos se ven en la pantalla;
     - el enlace solo aparece para el responsable.
- **Archivos:** `evaluon/accounts/views.py` (o un módulo nuevo `access_log.py`), `evaluon/accounts/urls.py`, `evaluon/templates/accounts/registro_accesos.html` (nuevo), `evaluon/templates/journey/_cabecera.html`, `tests/accounts/test_registro_accesos.py` (nuevo).
- **Verificación:** pruebas de `tests/accounts`. El Coordinador compara con la maqueta.
- **No tocar:** modelos, `backends.py`, middleware, las secciones.

### T-276 · Instancia separada del piloto

- **Requisitos:** REQ-117, REQ-116
- **Nivel de verificación:** plena (P4 en fase de operación, P5 y P11).
- **No arranca sin:** T-281 cerrada.
- **Qué hay que hacer:**
  1. **`docker-compose.sin-gpu.yml`** (nuevo): `generation_batch` y `worker` en el perfil `gpu`. Ningún servicio sin perfil los espera. Embeddings y reranker no cambian. Va en el `COMPOSE_FILE` de la instancia que no tiene el motor. Montarlo en `x-app` y `app` para los tests. Sumar al bloque del piloto de `.env.example` que el piloto empieza con este archivo.
  2. **`scripts/piloto/gpu.ps1 -Para piloto|construccion [-OtrosEnv <archivos>] [-SoloMostrar]`**, según el plan:
     - del lado del piloto, por `compose.ps1`; del de construcción, comprobando el proyecto `evaluon`;
     - se niega si la instancia que cede el motor tiene pedidos `running` en `tenders_job`, y lo explica;
     - detiene `generation_batch` y `worker` con espera, tolera el error de `docker stop` y espera `exited` en `docker inspect` (hasta 2 minutos);
     - cambia solo la línea `COMPOSE_FILE` de los dos `.env` y de los `-OtrosEnv`, con `[IO.File]::WriteAllText(..., [Text.UTF8Encoding]::new($false))` y los fines de línea originales, después de guardar una copia. Comprueba con `docker compose config -q` y, si falla, restaura y se detiene;
     - enciende el destino con `up -d` y espera `/health` y el alias en `/props`, hasta 15 minutos;
     - escribe `motor-gpu.txt`.
  3. **`scripts/piloto/respaldar.ps1 [-Conservar N]`**, por `compose.ps1`:
     - `pg_dump` a un temporal dentro del contenedor, copiado con `docker compose cp` a `C:\EVALUON-piloto\respaldos\` (sin redirección de PowerShell);
     - lo comprueba con `pg_restore -l` y borra el temporal;
     - conserva los N más nuevos (14 por omisión);
     - rechaza destinos dentro de una copia de Git, del perfil de usuario o de carpetas sincronizadas.
  4. **`scripts/piloto/vaciar-base.ps1`** (punto 8):
     - exige un respaldo de menos de una hora, comprobado con `pg_restore -l`, y una confirmación escrita;
     - detiene `app`, `worker` y `portal_worker`, vuelve a crear la base vacía con el dueño y deja que `migrate` aplique el esquema.
  5. **`scripts/piloto/actualizar.ps1 -Commit <commit> [-SoloMostrar]`**, según el plan («Actualizar el piloto»): se niega con pedidos en curso, respalda, lleva el clon al commit, `build` de la imagen, `showmigrations`, la migración con respaldo de T-049 si hay pendientes, `up -d --no-deps` de los servicios de la imagen propia, y comprueba el ingreso.
  6. **`.gitattributes`:** `scripts/models.sha256 text eol=lf`.
  7. **`specs/007-acceso-por-red/instancia-piloto.md`**, para una persona no técnica. Toda orden de Docker por `compose.ps1`; no se copian las órdenes de T-043 que traen `-p evaluon` (O-049-8). Secciones:
     - **Instalación, por un agente:** el procedimiento de T-049 más el clon con el push desactivado, el `.env`, los modelos por enlace duro o copia verificados con `tr -d '\r' < ../scripts/models.sha256 | sha256sum -c --ignore-missing -`, y el arranque sin motor. Después de `crear_usuario`, cambiar la clave por pantalla antes de usar comandos.
     - **Actualizar:** es un despliegue y lo aprueba el responsable.
     - **Después de un reinicio de Windows:** Docker Desktop, sesión bloqueada y no cerrada, tapa, Windows Update; `compose.ps1 ps` y repetir `up -d` si algo no arrancó.
     - **Mover el motor.**
     - **Respaldos:** el Programador de tareas, cada día fuera de horario, y una copia periódica a un medio que custodia el responsable, sin pasar por carpetas sincronizadas.
     - **Vaciar la base.**
     - **Clave olvidada:** con `clave_inicial`, en lugar del `changepassword` de T-049.
     - **Qué pueden hacer los agentes,** durante y después de la estabilización.
     - **Lista de cierre de la estabilización:**
       - el texto de las reglas de denegación para la configuración de permisos de Claude Code, que aplica el responsable: lectura de `C:\EVALUON-piloto\`, Docker sobre `evaluon-piloto`, pedidos a la dirección del piloto y a `127.0.0.1:8100`;
       - `ALTER ROLE` del usuario o los usuarios de la base y el `.env` actualizado;
       - una `DJANGO_SECRET_KEY` nueva;
       - `clave_inicial` para los usuarios cuya clave pasó por un agente;
       - el aviso al Coordinador.
     - **Lista de comprobación de REQ-117** para T-278 y T-285.
  8. **Tests** en `tests/test_instancia_piloto.py`:
     - el archivo sin GPU;
     - en el piloto, los motores corren con `--offline` y las direcciones de IA son internas;
     - qué servicios tienen salida a internet: `portal_worker` y, hasta T-284, `app` por `web`, anotado;
     - los nombres del piloto no aparecen en scripts ni comandos de construcción, salvo en `scripts/piloto/` y `scripts/red/`;
     - el destino por omisión de `respaldar.ps1` está fuera del repositorio;
     - los `.ps1` tienen BOM y `gpu.ps1` escribe sin BOM;
     - `.gitattributes` fija el archivo de huellas.
- **Archivos:** `docker-compose.sin-gpu.yml` (nuevo), `docker-compose.yml` (montajes), `.env.example` (bloque del piloto), `.gitattributes`, `scripts/piloto/gpu.ps1`, `respaldar.ps1`, `vaciar-base.ps1` y `actualizar.ps1` (nuevos), `specs/007-acceso-por-red/instancia-piloto.md` (nuevo), `tests/test_instancia_piloto.py`, `tests/test_compose_env.py` (si lista los montajes).
- **Verificación:**
  - Pruebas de `tests/test_instancia_piloto.py` y `tests/test_compose_env.py`.
  - `docker compose config` con la combinación de uso más `docker-compose.sin-gpu.yml` no lista `generation_batch` ni `worker` sin el perfil.
  - `gpu.ps1 -SoloMostrar` en las dos direcciones y `actualizar.ps1 -SoloMostrar` muestran lo esperado.
  - `docker build --no-cache -t evaluon-app:t276 .` termina sin errores de certificado; después se borra la etiqueta.
  - En un clon nuevo en Windows, `sha256sum -c` del archivo de huellas ya no falla por el fin de línea.
  - Las corridas reales de `gpu.ps1`, `respaldar.ps1` y `actualizar.ps1` son de T-278: esta tarea no mueve motores ni toca la instancia del piloto.
- **No tocar:** `docker-compose.piloto.yml` y `compose.ps1` (salvo hallazgo), `settings.py`, `accounts`, 8000.

### T-283 · Usuario de la base del piloto sin propiedad de las tablas

- **Requisitos:** REQ-117, REQ-113
- **Nivel de verificación:** plena (permisos de la base y P6).
- **No arranca sin:** T-272 y T-276 integradas y el punto 4 aprobado. Si el responsable elige la alternativa, se cierra sin cambios y el riesgo queda escrito en el plan.
- **Qué hay que hacer:**
  1. `scripts/piloto/permisos-base.sql`, idempotente, que corre el dueño del esquema:
     - crea el usuario `evaluon_app` (sin superusuario, sin crear bases);
     - le da lectura y escritura sobre las tablas y secuencias de la aplicación;
     - en `audit_event`, solo `SELECT` e `INSERT` (sin `UPDATE`, `DELETE` ni `TRUNCATE`);
     - `ALTER DEFAULT PRIVILEGES` para las tablas que creen migraciones futuras.
  2. `docker-compose.piloto.yml`: `app`, `worker` y `portal_worker` se conectan como `evaluon_app` con `EVALUON_APP_DB_PASSWORD`; `migrate` sigue con el dueño. `.env.example`: la variable en el bloque del piloto.
  3. `actualizar.ps1` y la instalación de `instancia-piloto.md` aplican el script después de cada `migrate`. La restauración de respaldos sigue con el dueño (T-049).
  4. Tests: el compose del piloto usa usuarios distintos para `migrate` y para la aplicación; el script no da a `evaluon_app` más que lectura e inserción en `audit_event`.
- **Archivos:** `scripts/piloto/permisos-base.sql` (nuevo), `docker-compose.piloto.yml`, `.env.example`, `scripts/piloto/actualizar.ps1`, `specs/007-acceso-por-red/instancia-piloto.md`, `tests/test_instancia_piloto.py`.
- **Verificación:**
  - Pruebas de `tests/test_instancia_piloto.py`.
  - Con el proyecto `evaluon-t283` y la combinación del piloto: se aplica el script, la aplicación ingresa y sube un archivo como `evaluon_app`, y `TRUNCATE`, `DELETE` y `UPDATE` sobre `audit_event` con ese usuario fallan. `down -v` al terminar.
- **No tocar:** el compose base, `settings.py`, `migrate_on_start.sh`, 8000.

### T-284 · Aplicación del piloto sin salida a internet

- **Requisitos:** REQ-117, REQ-116
- **Nivel de verificación:** plena (P4 en fase de operación).
- **No arranca sin:** T-283 cerrada (con o sin cambios) y el punto 4 aprobado. Si el responsable elige la alternativa, se cierra sin cambios.
- **Qué hay que hacer:**
  1. `docker-compose.piloto.yml`:
     - `app` solo en la red interna y sin puertos (`!override` y `!reset`; si la versión de Compose no los acepta, se informa);
     - un servicio `puerta`, en `web` y en la red interna, es el único con `127.0.0.1:${APP_PORT}:8000`. Reenvía la conexión TCP a `app:8000` sin tocar los encabezados. Su imagen es oficial o mantenida y está fijada por huella; la elige la tarea con esos criterios.
  2. `instancia-piloto.md`: la puerta en la comprobación y en el reinicio.
  3. Tests: en el piloto, `app` no está en `web` ni publica puertos; `puerta` es el único servicio con puerto; solo `portal_worker` y `puerta` tienen salida.
- **Archivos:** `docker-compose.piloto.yml`, `specs/007-acceso-por-red/instancia-piloto.md`, `tests/test_instancia_piloto.py`.
- **Verificación:**
  - Pruebas de `tests/test_instancia_piloto.py`.
  - Con el proyecto `evaluon-t284`: el ingreso funciona por `127.0.0.1:<puerto>`, y los encabezados `X-Forwarded-For` y `X-Evaluon-Computer` llegan intactos a la aplicación.
  - Desde `app`, un nombre de internet no resuelve. `down -v` al terminar.
- **No tocar:** el compose base, 8000.

### T-277 · Herramienta de medición de carga y del ingreso

- **Requisitos:** REQ-109 (requisito no funcional de carga) y REQ-111 (tiempos del ingreso)
- **Nivel de verificación:** plena (lógica de medición).
- **No arranca sin:** T-281 cerrada.
- **Qué hay que hacer:** `scripts/red/medir_carga.py` (biblioteca estándar), que nunca muestra claves y guarda el resultado fuera del repositorio.
  1. **`--preparar`:** con los usuarios y claves iniciales de un archivo fuera del repositorio, ingresa con cada uno y le cambia la clave por pantalla. Deja las claves nuevas en el mismo archivo.
  2. **Carga:**
     - N sesiones (10 por omisión) que ingresan con CSRF y durante T minutos recorren las páginas de las cinco secciones de un procedimiento, con pausas, y piden la barra cada 5 s con `X-Evaluon-Poll`;
     - por página: mediana, p95, máximo y errores;
     - se niega a medir si una sesión recibe la redirección al cambio de clave.
  3. **Línea de base:** una sesión desde el equipo por la misma dirección cifrada (por el puerto local no viajan las cookies seguras), corrida dos veces para el ruido (punto 5).
  4. **`--tiempos-ingreso`:** 20 intentos de cada caso (usuario inexistente, clave equivocada, usuario bloqueado con un usuario de prueba propio) y las medianas.
  5. **`--ca`:** verifica el certificado con la raíz de EVALUON o la del organismo.
  6. **Tests**, `tests/red/test_medir_carga.py`:
     - mediana y p95;
     - 2 sesiones por pocos segundos contra el `live_server` de pytest-django;
     - un usuario con clave inicial hace que se niegue;
     - `--preparar` cambia la clave;
     - `--tiempos-ingreso` arma los tres casos.
- **Archivos:** `scripts/red/medir_carga.py` (nuevo), `tests/red/test_medir_carga.py` (nuevo).
- **Verificación:** pruebas de `tests/red`.
- **No tocar:** el código de la aplicación, los demás archivos de `scripts/red/`.

### T-278 · Prueba de aceptación en la red

- **Requisitos:** REQ-109 a REQ-117
- **Nivel de verificación:** plena. **Usa la GPU** (el 27B del piloto). Necesita al responsable, A y B.
- **No arranca sin:**
  - T-275, T-276, T-277, T-282 y T-284 cerradas;
  - la instancia del piloto actualizada con `actualizar.ps1` por un agente, solo con material público;
  - la decisión del punto 5 copiada literal a la spec por el Coordinador;
  - el momento elegido con el responsable: el 27B de 8000 se apaga durante la prueba.
- **Qué hay que hacer, en este orden:**
  0. **Preparación.**
     - Fijar el commit.
     - `gpu.ps1 -Para piloto`, primera corrida real (según el punto 3, la corre el Coordinador avisando al responsable): el motor responde `/health` con el alias esperado, y se anota el tiempo. Se confirma la memoria por `utilization.gpu` y el registro del motor, no solo por la memoria usada.
     - Alta de los usuarios de carga y del evaluador de prueba, y `medir_carga.py --preparar`.
  1. **Caso chico (REQ-109, REQ-114).**
     - Desde A, con un evaluador recién creado: cambio obligatorio de clave; una clave corta, una común, una igual a la actual y la actual equivocada, rechazadas con su motivo.
     - El recorrido del caso chico en las cinco secciones, retomando el pliego que se subió en T-271. Umbral: 5 de 5.
  2. **Cifrado (REQ-110).** `curl.exe -sI` por `http` al ingreso, a una página de cada sección y a un estático: todas terminan en `https` sin cuerpo de la aplicación. 0 advertencias en A.
  3. **Bloqueo, registro y desbloqueo (REQ-111 a REQ-113).**
     - Desde A, 5 claves equivocadas y después la correcta: rechazada con el mismo mensaje que un usuario inexistente y una clave equivocada.
     - Desbloqueo por la pantalla del responsable, desde otra computadora de la lista (punto 1); A ingresa enseguida.
     - La pantalla y `ver_accesos` muestran los 4 hechos con la computadora, su dirección, fecha y hora.
     - Lo mismo por comando en el equipo.
     - `medir_carga.py --tiempos-ingreso`: diferencia de medianas menor que 25 ms.
  4. **Sesión (REQ-115).**
     - Una pantalla con sondeo abierta 31 minutos sin tocarla: el siguiente clic lleva al ingreso, y lo guardado sigue.
     - Cerrar todas las ventanas del navegador en A y volver a abrirlo: lleva al ingreso. Se anotan el navegador y su configuración de restauración y de arranque rápido.
     - Con el punto 6, la salida de una sesión abandonada aparece en el registro.
  5. **Servicios internos y lista (REQ-116, REQ-109).**
     - `Test-NetConnection` desde A y desde B, e inventario de puertos en el equipo;
     - 0 páginas desde B;
     - sacar A de la lista y volver a ponerla.
  6. **Carga.** `medir_carga.py` con 10 sesiones y la línea de base según el punto 5, más la carga de cada sección en A con las herramientas del navegador.
  7. **Separación durante la estabilización (REQ-117)**, con la lista de `instancia-piloto.md`:
     - con el motor en el piloto, la construcción no enciende su 27B (`docker compose ps` y un `run --rm` de un test);
     - con el motor en construcción, el piloto tampoco;
     - `compose.ps1` rechaza `down -v` y `-p`;
     - `respaldar.ps1` deja el respaldo en la carpeta del piloto;
     - `git push --dry-run` del clon falla;
     - motores con `--offline`;
     - quién tiene salida a internet: con el punto 4, solo `portal_worker` y la puerta; sin él, también `app`, anotado como riesgo aceptado;
     - con el punto 4, el usuario de la aplicación no puede borrar el registro;
     - `manage.py check --deploy`: los avisos se anotan, cada uno con su motivo.
  8. **Mover el motor.** `gpu.ps1 -Para construccion` y de vuelta, con el tiempo de cada cambio y una negativa con un pedido en curso. El motor queda donde decidan el responsable y el punto 3.
- **Umbral:** el de la tabla del plan, punto por punto.
- **Qué entrega:** `verificacion/T-278.md` con:
  - el commit;
  - cada medida contra su umbral;
  - los tiempos de los cambios de motor;
  - los hallazgos agrupados por causa;
  - lo que pasa a «Revisión con el primer producto»;
  - qué parte de REQ-117 queda verificada (los mecanismos, durante la estabilización y con material público). El resto es de T-285.

  Sin datos del organismo ni claves. Las salidas de `medir_carga.py`, fuera del repositorio.
- **Archivos:** solo `specs/007-acceso-por-red/verificacion/T-278.md`.
- **No tocar:** código, scripts, umbrales. Un hallazgo es de T-279.

### T-279 · Corrección única de la aceptación

- **Requisitos:** REQ-109 a REQ-117
- **Nivel de verificación:** plena.
- **No arranca sin:** T-278 terminada, con su verificación registrada.
- **Qué hay que hacer:** si T-278 no llegó a algún umbral, corregir **todos** sus hallazgos en esta sola tarea. Un commit por hallazgo y su test que falla antes y pasa después; por ejemplo, los hilos de Gunicorn en `docker-compose.piloto.yml` si la carga no llega. Si T-278 cumplió todo, se cierra sin cambios y T-280 también.
- **Archivos:** los de T-269 a T-277 y T-282 a T-284 que el hallazgo señale, y `specs/007-acceso-por-red/verificacion/T-279.md`.
- **Verificación:** el testeador verifica cada corrección con las pruebas de su área. La repetición de la medición es T-280.
- **No tocar:** umbrales; archivos que ningún hallazgo señale.

### T-280 · Repetición de la aceptación

- **Requisitos:** REQ-109 a REQ-117
- **Nivel de verificación:** plena. Usa la GPU. Necesita al responsable, A y B.
- **No arranca sin:** T-279 terminada con cambios, y el piloto actualizado a su commit con `actualizar.ps1`.
- **Qué hay que hacer:** repetir T-278 **completa**, no solo lo que falló, para ver también las regresiones. Lo que siga sin llegar pasa con su impacto a «Revisión con el primer producto». Si se sigue perdiendo un requisito o se viola un principio, el responsable decide si se abre otra ronda (ADR-0025).
- **Archivos:** solo `specs/007-acceso-por-red/verificacion/T-280.md`.
- **No tocar:** código, scripts, umbrales.

### T-285 · Verificación del cierre de la estabilización

- **Requisitos:** REQ-117
- **Nivel de verificación:** plena.
- **No arranca sin:** que el responsable dé por terminada la estabilización y aplique la lista de cierre de `instancia-piloto.md`. Según el punto 12, esta tarea no reabre la feature.
- **Qué hay que hacer:**
  1. Con los registros del responsable, comprobar que se aplicó cada paso de la lista de cierre (reglas, claves de la base y de Django, claves de usuarios).
  2. Un agente intenta leer `C:\EVALUON-piloto\`, correr `docker` sobre `evaluon-piloto` y pedir la página de ingreso del piloto, y es rechazado en los tres. Anota el rechazo, sin ver contenido.
  3. Comprobar que ninguna tarea, script ni encargo de construcción vigente nombra el proyecto, la base, los volúmenes, los respaldos ni la carpeta del piloto.
- **Qué entrega:** `verificacion/T-285.md`, sin nada del proceso. Si algo falla, un hallazgo para el responsable.
- **Archivos:** solo `specs/007-acceso-por-red/verificacion/T-285.md`.
- **No tocar:** la instancia del piloto (no se accede: se prueba que no se puede).
