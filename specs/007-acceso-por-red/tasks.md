# Tareas 007 · Acceso por red

Plan: `specs/007-acceso-por-red/plan.md`

Despliegue: pendiente

> El tablero (`docs/tablero.md`) se genera de este archivo. Al aprobarse el despliegue, la línea de arriba pasa a `Despliegue: aprobado AAAA-MM-DD`.

Estados: pendiente · en curso · en verificación · terminada · bloqueada

Dos tareas que no dependen entre sí y no comparten archivos se pueden hacer en paralelo.

Ritmo de trabajo (ADR-0024 y ADR-0025): las ramas de tarea no tocan este archivo ni el tablero; el Coordinador los actualiza una vez por lote. La verificación de cada tarea queda en `specs/007-acceso-por-red/verificacion/T-NNN.md`, sin direcciones ni nombres de la red del organismo, sin claves y sin nada del proceso en curso. Los umbrales están escritos en el plan antes de medir; como máximo dos rondas: la prueba T-278 y un solo ajuste (T-279). **Lo que toca Windows o la red lo hace el responsable**, siguiendo `entorno.md`; el agente prepara los pasos y registra los resultados.

**IDs.** T-269 a T-279 son únicos: el último ID usado en el proyecto es T-268 (015). El Coordinador lo confirma contra las ramas abiertas antes de lanzar.

**Condiciones previas.**

- Los ADR-0061 a ADR-0064 son propuestos: el responsable los acepta con este plan.
- Los pedidos al área de sistemas (plan, «Pedido al área de sistemas») no frenan T-269 a T-277: el corte vertical se puede probar en cualquier red, con una segunda computadora y el certificado propio. Sí frenan abrir el piloto en la red del organismo.
- T-276 necesita T-049 de la 001 terminada: la instancia del piloto se instala con su procedimiento.
- T-275 necesita la maqueta de la pantalla de cambio de clave y del enlace del encabezado, aprobada por el responsable antes de desarrollar.
- T-278 necesita que el Coordinador confirme la lectura del umbral de carga (plan, «Criterio de aceptación numérico») y que el responsable elija el momento: pasa el motor al piloto y el 27B de 8000 se apaga durante la prueba.
- Construir la imagen del piloto sin caché hoy falla en este equipo porque Norton intercepta las conexiones de `pip` (hallazgo de T-049). Con el mismo `Dockerfile` y `pyproject.toml`, Docker reutiliza las capas que ya tiene. Si hace falta construir sin caché, la salida la decide el responsable (pendiente fuera del alcance de esta feature).

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-269 | Modo HTTPS detrás del intermediario (cookies seguras, protocolo que informa el intermediario) y esqueleto de la instancia del piloto: `docker-compose.piloto.yml` con nombre de proyecto e imagen propios, bloque del piloto en `.env.example` con `COMPOSE_PROJECT_NAME`, y `scripts/piloto/compose.ps1`, que no deja correr Compose en la carpeta del piloto sin su nombre de proyecto (hallazgo de T-049) | REQ-110, REQ-116, REQ-117, REQ-109 | — | pendiente |
| T-270 | Intermediario cifrado en Windows: generador del `Caddyfile` desde el `.env` (lista de hasta 10 computadoras, corte de las demás, redirección, encabezados de origen), script que aplica la lista al firewall y al intermediario, instalación de Caddy con versión y huella fijas, certificados propios con restricción de nombre, revisión de puertos y pasos del responsable en `entorno.md` | REQ-109, REQ-110, REQ-116 | — | pendiente |
| T-271 | Prueba del corte vertical en la red, con el responsable: el ingreso servido cifrado a una computadora de la lista con un usuario de prueba, sin advertencias, `http` redirigido sin contenido, la clave ilegible en el tráfico, 0 páginas para una computadora de fuera, 0 servicios internos abiertos, una computadora que se saca y se vuelve a poner sin tocar el código | REQ-109, REQ-110, REQ-116 | T-269, T-270 | pendiente |
| T-272 | Esquema de acceso (campos del usuario y cinco tipos de hecho, una sola tarea) y bloqueo: 5 fallidos seguidos bloquean 15 minutos aunque después se escriba la clave correcta, mismo mensaje para inexistente, clave equivocada y bloqueado, igual por comando | REQ-111 | T-269 | pendiente |
| T-273 | Computadora de origen en cada hecho de acceso (pantalla, intermediario y comando), registro de la salida, comandos `desbloquear_usuario` y `ver_accesos` para el responsable del sistema | REQ-112, REQ-113 | T-272 | pendiente |
| T-274 | Cierre de la sesión a los 30 minutos sin uso y a las 8 horas, sin contar el sondeo de la pantalla; la cookie sigue venciendo al cerrar el navegador; el cierre queda registrado con su motivo | REQ-115, REQ-113 | T-273 | pendiente |
| T-275 | Cambio de clave por pantalla con la clave actual, 8 caracteres como mínimo y sin claves comunes; clave inicial obligatoria de cambiar en el primer ingreso (también frena los comandos); comando `clave_inicial`; la clave actual equivocada cuenta para el bloqueo | REQ-114, REQ-111 | T-274 | pendiente |
| T-276 | Instancia separada del piloto: compose de construcción sin el 27B mientras el piloto lo tiene, script para pasar el motor de una instancia a la otra, respaldo del piloto en su carpeta, clon sin publicación, `scripts/models.sha256` con fin de línea LF, procedimiento de instalación y de cierre de la estabilización | REQ-117, REQ-116 | T-269, T-049 (001) | pendiente |
| T-277 | Herramienta de medición de carga: 10 sesiones a la vez por el intermediario, con el sondeo de la pantalla, y la línea de base con una sola sesión en el equipo; mediana, p95 y máximo por página | REQ-109 | T-270 | pendiente |
| T-278 | Prueba de aceptación en la red, con el responsable: el caso chico en 5 de 5 secciones desde una computadora de la lista, todos los umbrales del plan (cifrado, lista, servicios internos, bloqueo, registro, clave, inactividad, carga) y la separación de la instancia del piloto | REQ-109, REQ-110, REQ-111, REQ-112, REQ-113, REQ-114, REQ-115, REQ-116, REQ-117 | T-271, T-275, T-276, T-277 | pendiente |
| T-279 | Ronda de ajuste única, solo si T-278 no llega a algún umbral: todos los hallazgos en una sola tarea, un commit por hallazgo, y repetición de lo que falló; se cierra sin cambios si T-278 cumple todo | REQ-109, REQ-110, REQ-111, REQ-112, REQ-113, REQ-114, REQ-115, REQ-116, REQ-117 | T-278 | pendiente |

## Paralelismo y recursos

- **Primer lote, en paralelo:** T-269 y T-270. No comparten archivos: T-269 toca `settings.py`, compose, `.env.example` y sus tests; T-270, `scripts/red/`, `tests/red/` y `entorno.md`. Lo que comparten (nombres de variables y encabezados) está fijado en el plan, «Definiciones compartidas».
- **Segundo lote, en paralelo:** T-271 (el responsable y el testeador; solo escribe su verificación), T-272, T-277 y, si T-049 de la 001 terminó, T-276. Sus archivos no se cruzan:
  - T-272: `accounts` (modelo, backend, migración), `audit` y `settings.py`;
  - T-276: `docker-compose.sin-gpu.yml`, los montajes de `docker-compose.yml`, `.gitattributes`, `scripts/piloto/gpu.ps1` y `respaldar.ps1`, `instancia-piloto.md` y `tests/test_instancia_piloto.py`;
  - T-277: `scripts/red/medir_carga.py` y su test.
- **Cadena del acceso:** T-272, después T-273, después T-274, después T-275. Comparten `settings.py` (T-272, T-274, T-275), `backends.py` (T-272, T-273), `permissions.py` (T-273, T-275) y el receptor de salida de `apps.py` (lo crea T-273 y lo usa T-274).
- **Esquema:** T-272 es la única tarea que genera migraciones (`accounts` y `audit`, juntas) y corre sola entre las que tocan el esquema.
- **Configuración compartida:** `settings.py` en el orden T-269, T-272, T-274, T-275; `docker-compose.yml` en el orden T-269, T-276. `.env.example` lo toca solo T-269 y `.gitattributes` solo T-276. En `scripts/piloto/`, T-269 crea `compose.ps1` y T-276, que depende de ella, los otros dos.
- **GPU:** solo T-278 (y la repetición de T-279, si incluye el caso chico) usa el 27B, el del piloto. El responsable pasa el motor con `scripts/piloto/gpu.ps1`: el 27B de 8000 se apaga mientras tanto. Ninguna otra tarea enciende motores. T-271 levanta solo la base, la migración y la aplicación.
- **Proyectos de Docker:** solo el responsable crea el proyecto `evaluon-piloto` (en T-271), y siempre por `compose.ps1`. Los agentes que prueban algo en Docker usan un nombre propio (`-p evaluon-t269`, por ejemplo) y lo bajan con `down -v` al terminar. Nunca usan `evaluon-piloto`, que compartiría la base con la instancia real, ni tocan los contenedores de 8000.
- **Necesitan a una persona:** T-271, T-278 y T-279 (pasos de Windows y de red, una computadora de la lista y una de fuera); la maqueta de T-275 (aprobación del responsable).
- **Máximo sugerido en paralelo:** tres desarrolladores (T-272, T-276, T-277) mientras el responsable hace T-271.

## Detalle

### T-269 · Modo HTTPS detrás del intermediario y esqueleto de la instancia del piloto

- **Requisitos:** REQ-110, REQ-116, REQ-117, REQ-109
- **Nivel de verificación:** plena (configuración compartida y principios P4 y P5).
- **Qué hay que hacer:**
  1. `settings.py`, bloque nuevo «Acceso por red (plan 007)», con una función que lee el entorno, a la manera de `reasoning_levels`: `EVALUON_HTTPS` (`env_bool`, por omisión falso). Con verdadero: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` y `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`. Sin `SECURE_SSL_REDIRECT`: redirige el intermediario, y con esa opción el chequeo de salud del contenedor, que pide la hoja de estilos por `http` adentro, recibiría una redirección. Sin HSTS: ningún requisito lo pide y los navegadores lo ignoran en una dirección IP. Corregir el comentario del bloque de sesiones que dice que la cookie segura es «de la feature 007».
  2. `docker-compose.yml`: `EVALUON_HTTPS: ${EVALUON_HTTPS:-false}` en el entorno de `x-app`; montar `./docker-compose.piloto.yml` en `x-app` y en `app`, solo para los tests (regla de T-264).
  3. `docker-compose.piloto.yml` (nuevo): `name: evaluon-piloto` e `image: evaluon-app:piloto` en `migrate`, `app`, `worker` y `portal_worker`, para que construir en una instancia no cambie la imagen de la otra (hallazgo de T-049). Nada más: sin puertos ni redes nuevos, porque el puerto sale de `APP_PORT`. Para levantar la aplicación con los motores apagados se usa `up -d --no-deps app`, no un cambio de dependencias.
  4. `.env.example`: bloque **comentado** «Instancia del piloto (plan 007, ADR-0064)» con las variables del plan («Definiciones compartidas»), empezando por `COMPOSE_PROJECT_NAME=evaluon-piloto` y con el aviso de lo que pasa si falta, y una línea por variable sobre qué poner. Para las direcciones, solo ejemplos del rango de documentación (`192.0.2.0/24`). Ninguna línea sin comentar cambia.
  5. `scripts/piloto/compose.ps1` (nuevo; es la única forma de correr Compose en la carpeta del piloto). Lee el `.env` de la carpeta en la que corre. Si no tiene `COMPOSE_PROJECT_NAME=evaluon-piloto`, o su `COMPOSE_FILE` no incluye `docker-compose.piloto.yml`, se detiene con un mensaje en lenguaje llano y no llama a Docker. Si los tiene, llama a `docker compose -p evaluon-piloto` con los argumentos que recibió.
  6. Tests: `tests/accounts/test_https_mode.py`. Con el modo HTTPS, un ingreso con `X-Forwarded-Proto: https` y el `Host` de la dirección fija deja las cookies de sesión y CSRF con `Secure`; un POST con `Origin: https://<dirección>` pasa el control CSRF; sin el modo, nada cambia respecto de hoy. `tests/test_instancia_piloto.py` (nuevo):
     - el archivo del piloto nombra el proyecto `evaluon-piloto`;
     - las imágenes de los cuatro servicios no son `evaluon-app:local`;
     - el archivo no agrega puertos ni redes;
     - el puerto de `app` sigue publicado solo en `127.0.0.1`;
     - `EVALUON_HTTPS` llega a la aplicación con el mismo valor por omisión que `settings.py`;
     - el bloque del piloto de `.env.example` trae `COMPOSE_PROJECT_NAME=evaluon-piloto` y `docker-compose.piloto.yml` en `COMPOSE_FILE`;
     - `compose.ps1` comprueba las dos líneas y pasa `-p evaluon-piloto` (revisión del texto: PowerShell no corre en el contenedor).
- **Archivos:** `evaluon/settings.py`, `docker-compose.yml` (entorno de `x-app` y montajes), `docker-compose.piloto.yml` (nuevo), `.env.example`, `scripts/piloto/compose.ps1` (nuevo), `tests/accounts/test_https_mode.py` (nuevo), `tests/test_instancia_piloto.py` (nuevo), `tests/test_compose_env.py` (si el test de montajes lista los archivos).
- **Verificación:**
  - `docker compose run --rm app pytest tests/accounts tests/test_instancia_piloto.py tests/test_compose_env.py` y la suite completa una vez al final.
  - `docker compose -f docker-compose.yml -f docker-compose.qwen38-27b.yml -f docker-compose.razonamiento.yml -f docker-compose.consulta-27b.yml -f docker-compose.piloto.yml config`, sin errores y con el proyecto `evaluon-piloto`.
  - `compose.ps1 config` en una carpeta temporal: con un `.env` sin `COMPOSE_PROJECT_NAME` se niega; con él, muestra la configuración del piloto. Solo `config`: nunca `up` con el nombre `evaluon-piloto`.
  - Prueba local con otro nombre de proyecto (`-p evaluon-t269`, `APP_PORT` libre, `EVALUON_HTTPS=true`, sin motores: `up -d db migrate` y `up -d --no-deps app`): `curl -H "X-Forwarded-Proto: https" -H "Host: <dirección de ejemplo>"` al ingreso devuelve 200 con `csrftoken` `Secure`. Al terminar, `down -v` de ese proyecto y borrado de la imagen que haya creado.
- **No tocar:** modelos, backend, vistas y plantillas de `accounts`; `audit`; `scripts/red/` (T-270); el `.env` de 8000 y sus contenedores; el nombre de proyecto `evaluon-piloto` en Docker.

### T-270 · Intermediario cifrado en Windows, lista de computadoras, firewall y certificados

- **Requisitos:** REQ-109, REQ-110, REQ-116
- **Nivel de verificación:** plena (seguridad de la red y principios P4 y P5).
- **Qué hay que hacer:**
  1. `scripts/red/caddy.py` (Python 3.12, solo la biblioteca estándar: corre en Windows con `py -3` y en el contenedor para los tests). Lee el `.env` del piloto y valida, con mensajes en lenguaje llano:
     - `EVALUON_ADDRESS`: un nombre o una IPv4;
     - `EVALUON_SERVER_IP`: una IPv4;
     - `EVALUON_COMPUTERS`: formato `nombre=dirección`; nombres con minúsculas, números y guiones; IPv4; sin nombres ni direcciones repetidos; ninguna igual a la del equipo; **10 como máximo**;
     - `APP_PORT`.
     Escribe el `Caddyfile` en la ruta que se le indica, a partir de la plantilla.
  2. `scripts/red/Caddyfile.plantilla`:
     - Opciones globales sin certificados automáticos ni consultas a internet; la administración solo en `localhost`.
     - Sitio `http://<dirección>`: corta (`abort`) lo que no viene de la lista ni del equipo, y redirige el resto a `https` con 308.
     - Sitio `https://<dirección>`: `tls` con `evaluon.crt` y `evaluon.key` de la carpeta de certificados; el mismo corte; `map` de la dirección de origen al nombre de la computadora (la del equipo da `equipo-del-sistema`); `reverse_proxy 127.0.0.1:<APP_PORT>` con `header_up X-Evaluon-Computer`.
     Los nombres exactos de las opciones se fijan con la documentación de la versión fijada.
  3. `scripts/red/aplicar-red.ps1` (como administrador). Comprueba que corre como administrador. Corre `caddy.py` y `caddy validate`. Crea o actualiza la regla de entrada «EVALUON piloto»: TCP 80 y 443, programa `caddy.exe`, direcciones remotas solo las de la lista y la del equipo, perfiles de dominio y privado. Desactiva toda otra regla de entrada de `caddy.exe` y recarga el intermediario (lo arranca si estaba detenido). Al final muestra la regla, la lista y el perfil de la red (avisa si es «Pública»).
  4. `scripts/red/instalar-caddy.ps1` (como administrador): baja el zip de Windows amd64 de la versión fijada desde la publicación oficial de GitHub, comprueba su SHA-256 contra `scripts/red/caddy.sha256` (copiado del archivo de sumas de la publicación; si no coincide, se detiene), lo deja en `C:\EVALUON-piloto\caddy\` y registra el servicio `EVALUON-Caddy` con arranque automático y reinicio ante fallas (`sc.exe`, `caddy.exe run --config`). La versión es la estable vigente (2.11.7 el 2026-10-14, ADR-0061); esta tarea confirma el archivo de Windows y su suma.
  5. `scripts/red/crear-certificados.sh` (Git Bash, con el `openssl` de Git para Windows):
     - Si no hay autoridad en su carpeta, crea `ca-evaluon.key` y `ca-evaluon.crt`: 10 años, `CA:TRUE` con `pathlen:0`, solo firma de certificados y listas, y restricción de nombre crítica que permite solo la dirección de EVALUON y la del equipo.
     - Crea `evaluon.key` y `evaluon.crt` (397 días, con la dirección y la del equipo como nombres alternativos y uso de servidor), firmados por la autoridad, con la cadena.
     - Muestra el vencimiento y la huella SHA-256 de la raíz, para cotejarla en cada computadora.
     - Las claves nunca quedan en el repositorio: las carpetas por omisión están bajo `C:\EVALUON-piloto\`. Con la autoridad ya creada, solo renueva el del servidor.
  6. `scripts/red/revisar-puertos.ps1` (en una computadora de la red, sin administrador): con la dirección, prueba TCP 80, 443, 5432, 8000, 8080, 8100, 2019 y 2375 y muestra cuáles aceptan conexión.
  7. `specs/007-acceso-por-red/entorno.md`, para una persona no técnica: cada comando y lo que tiene que verse. Secciones:
     - «Red del piloto: pasos del responsable» (el plan, ampliado);
     - «Cambiar la lista»;
     - «Pasar al certificado del organismo» (incluida la conversión de un PFX);
     - «Renovar el certificado propio»;
     - «Comprobar» (la lista de T-271);
     - «Qué pedir al área de sistemas».
     Solo direcciones de ejemplo de documentación.
  8. Tests, `tests/red/test_caddy_config.py`:
     - una lista válida genera el `Caddyfile` esperado;
     - 11 computadoras, un nombre o una dirección repetidos o una dirección inválida se rechazan con su mensaje;
     - la dirección del equipo siempre entra y se nombra `equipo-del-sistema`;
     - el sitio `http` corta lo que no está en la lista y redirige el resto;
     - el sitio `https` tiene `tls` con los dos archivos, el corte, el `map` y el reenvío a `127.0.0.1:<APP_PORT>`;
     - no hay ACME, correo ni ningún host externo;
     - ningún archivo de `scripts/red/` tiene direcciones fuera de los rangos de documentación y de `127.0.0.1`.
- **Archivos:** `scripts/red/caddy.py`, `scripts/red/Caddyfile.plantilla`, `scripts/red/aplicar-red.ps1`, `scripts/red/instalar-caddy.ps1`, `scripts/red/caddy.sha256`, `scripts/red/crear-certificados.sh`, `scripts/red/revisar-puertos.ps1` (todos nuevos), `tests/red/__init__.py`, `tests/red/test_caddy_config.py` (nuevos), `specs/007-acceso-por-red/entorno.md` (nuevo).
- **Verificación:**
  - `docker compose run --rm app pytest tests/red` y la suite completa una vez al final.
  - Con un `.env` de ejemplo, el `Caddyfile` que produce `py -3 scripts\red\caddy.py` lo acepta `caddy adapt`, con el binario fijado bajado a una carpeta temporal y su huella verificada, sin registrar el servicio.
  - `crear-certificados.sh` sobre una carpeta temporal: `openssl x509 -text` muestra la restricción de nombre y los nombres alternativos, y `openssl verify -CAfile` pasa.
  - Los dos scripts de administrador no los corre el agente: los prueba el responsable en T-271.
- **No tocar:** el firewall, los servicios y la red de Windows (los cambia solo el responsable); `settings.py`; los compose; los contenedores de 8000.

### T-271 · Prueba del corte vertical en la red

- **Requisitos:** REQ-109, REQ-110, REQ-116
- **Nivel de verificación:** plena (criterio de la feature y principio P4).
- **Necesita:** al responsable (pasos de Windows y de red), una computadora de la lista (A) y una de fuera (B; puede ser A sacada de la lista). No usa la GPU.
- **No arranca sin:** T-269 y T-270 integradas.
- **Qué hay que hacer:** el testeador arma la lista de pasos con `entorno.md` y la planilla de resultados; el responsable ejecuta y le pasa las salidas y las capturas.
  1. **Instancia mínima del piloto.** `C:\EVALUON-piloto\evaluon\`, clonada en el commit de `main`, con el push desactivado y un `.env` con el bloque del piloto y claves propias.
     - Primero `.\scripts\piloto\compose.ps1 config`, que tiene que nombrar el proyecto `evaluon-piloto`.
     - Después `compose.ps1 up -d db migrate` y `compose.ps1 up -d --no-deps app`: la base, la migración y la aplicación, sin motores.
     - Al final, `crear_usuario` de un usuario de prueba evaluador.
     - `docker compose ls` muestra los dos proyectos y el de 8000 sin cambios.
     - No se carga nada reservado.
     Si la imagen no se construye porque Norton intercepta `pip` (hallazgo de T-049), se anota y se sigue con la salida que elija el Coordinador; no es parte de esta prueba.
  2. Caddy instalado (`instalar-caddy.ps1`), certificado propio (`crear-certificados.sh`), lista con A y `aplicar-red.ps1`. La raíz, instalada en A.
  3. **Desde A:**
     - la dirección cifrada muestra el ingreso sin advertencias (captura);
     - el certificado que muestra el navegador es el de EVALUON y no el de un antivirus o un proxy (se anota el emisor);
     - el usuario de prueba ingresa y llega a la primera pantalla;
     - `curl -sI http://<dirección>/ingresar/` da 308 del intermediario hacia `https`, sin cuerpo de la aplicación;
     - con una captura con `pktmon` en el equipo durante un ingreso, la clave aparece 0 veces.
  4. **Desde B:** `http` y `https` no conectan; `revisar-puertos.ps1` da 0 puertos abiertos.
  5. **Desde A:** `revisar-puertos.ps1` da solo 80 y 443.
  6. Sacar A de la lista y correr `aplicar-red.ps1`: A no llega. Volver a ponerla: llega. `git status` del clon sigue limpio (no se tocó el código).
  7. **Restricción de nombre:** un certificado de prueba para otro nombre, firmado por la misma autoridad, es rechazado en A (`certutil -verify`).
- **Umbral:** el del corte vertical en el plan. 0 advertencias, 0 páginas por `http`, 0 apariciones de la clave, 0 páginas desde B, solo 80 y 443 desde A, y el cambio de la lista sin tocar el código.
- **Qué entrega:** `verificacion/T-271.md` con el commit, cada punto contra su umbral y los hallazgos. Las computadoras se nombran «A» y «B», sin direcciones ni nombres del organismo. Un defecto vuelve a T-269 o T-270 como hallazgo. La instancia mínima queda para T-278.
- **Archivos:** solo `specs/007-acceso-por-red/verificacion/T-271.md`.
- **No tocar:** código, scripts, 8000.

### T-272 · Esquema de acceso y bloqueo tras 5 intentos

- **Requisitos:** REQ-111
- **Nivel de verificación:** plena (esquema y lógica de seguridad).
- **No arranca sin:** T-269 integrada (comparte `settings.py`). Corre sola entre las tareas que tocan el esquema.
- **Qué hay que hacer:**
  1. `accounts/models.py`: `failed_logins`, `locked_until` y `must_change_password` (plan, «Modelo de datos»), con su migración, que se aplica desde cero y hacia atrás.
  2. `audit/models.py`: los cinco tipos de hecho, con una migración que reemplaza la restricción de valores válidos, como la `0008`.
  3. `accounts/backends.py` (nuevo): `LockoutBackend`, sobre el `ModelBackend` de Django.
     - Usuario inexistente: corre el cálculo de la clave, como hace Django, y devuelve nada.
     - Usuario con `locked_until` futuro: corre el mismo cálculo de la clave, para tardar lo mismo, y lanza `PermissionDenied`. Django devuelve nada, emite la señal de ingreso fallido y el formulario muestra el mismo mensaje.
     - Clave equivocada: `register_failed_attempt(user, origin)`. Suma uno de forma atómica (`select_for_update` en una transacción) y, al llegar a `LOGIN_FAILURE_LIMIT`, pone `locked_until = ahora + LOGIN_LOCKOUT_MINUTES`, vuelve la cuenta a 0 y deja `lockout`.
     - Clave correcta de un usuario activo: vuelve la cuenta a 0 si no lo estaba.
     - Los intentos durante el bloqueo no cuentan ni lo alargan. Un usuario dado de baja sigue con el mismo mensaje.
  4. `settings.py`: `AUTHENTICATION_BACKENDS` con el backend nuevo; `LOGIN_FAILURE_LIMIT = 5` y `LOGIN_LOCKOUT_MINUTES = 15`.
  5. Tests, `tests/accounts/test_lockout.py`, con el reloj controlado, por pantalla y por comando (`call_command` con la clave simulada):
     - 5 fallidos seguidos, y la clave correcta se rechaza con el mismo mensaje;
     - a los 14 min 59 s sigue rechazada; a los 15 min ingresa;
     - 4 fallidos y uno correcto ingresa y deja la cuenta en 0;
     - los tres mensajes son idénticos (inexistente, clave equivocada y bloqueado), en la pantalla y en el comando;
     - con un usuario bloqueado, el cálculo de la clave igual corre;
     - `lockout` se registra una sola vez, con `locked_until`.
- **Archivos:** `evaluon/accounts/models.py`, una migración nueva en `evaluon/accounts/migrations/`, `evaluon/accounts/backends.py` (nuevo), `evaluon/audit/models.py`, una migración nueva en `evaluon/audit/migrations/`, `evaluon/settings.py` (backend y dos constantes), `tests/accounts/test_lockout.py` (nuevo), y los tests de `audit` que listen los tipos de hecho.
- **Verificación:** `docker compose run --rm app pytest tests/accounts tests/audit` y la suite completa una vez al final; migrar desde cero y volver a la migración anterior de cada app; los tests de ingreso existentes pasan sin cambios.
- **No tocar:** `apps.py`, `permissions.py`, vistas, plantillas y comandos de `accounts` (T-273 y T-275); el compose.

### T-273 · Computadora de origen, registro de accesos y desbloqueo

- **Requisitos:** REQ-112, REQ-113
- **Nivel de verificación:** plena (registro de auditoría, P6).
- **No arranca sin:** T-272 integrada.
- **Qué hay que hacer:**
  1. `accounts/origin.py` (nuevo): `request_origin(request)`. Con `X-Evaluon-Computer` y `X-Forwarded-For` devuelve el nombre y la última dirección; sin ellos, `equipo-del-sistema` sin dirección (pedido directo por el puerto local). `COMMAND_ORIGIN` es el origen de un comando. Valores acotados en largo.
  2. `apps.py`:
     - `login` y `login_failed` llevan `origin` (sin pedido, el del comando);
     - receptor nuevo de `user_logged_out`: deja `logout` con `origin` y `reason` (el de `request.evaluon_logout_reason` si existe; si no, `user`).
  3. `backends.py`: el hecho `lockout` lleva el origen del pedido, o el del comando.
  4. `permissions.authenticate_command`: el hecho `login` lleva `COMMAND_ORIGIN`.
  5. `desbloquear_usuario <usuario> --usuario <responsable>` (nuevo): `authenticate_command` y rol de lectura y escritura, como `rol_comision`. Usuario inexistente: error sin cambios. No bloqueado: lo dice y no cambia nada. Bloqueado: vacía `locked_until` y la cuenta, y deja `unlock` con quién, a quién y el `locked_until` que tenía.
  6. `ver_accesos [--desde] [--hasta] [--de <usuario>] --usuario <responsable>` (nuevo): mismo control. Lista los siete hechos de acceso en orden de fecha: fecha y hora de Buenos Aires, hecho, usuario o nombre escrito, computadora con su dirección y canal. Sin filtros, todo.
  7. Tests:
     - origen por el intermediario (con encabezados), directo y por comando;
     - criterio de REQ-113: ingreso, fallido, bloqueo y desbloqueo con los encabezados de una computadora de la lista, y `ver_accesos` muestra los 4 con usuario o nombre, computadora, fecha y hora;
     - el desbloqueo deja ingresar enseguida (REQ-112);
     - un usuario sin rol de lectura y escritura es rechazado, con su hecho `rejected`;
     - «Salir» deja `logout` con su origen.
- **Archivos:** `evaluon/accounts/origin.py` (nuevo), `evaluon/accounts/apps.py`, `evaluon/accounts/backends.py`, `evaluon/accounts/permissions.py`, `evaluon/accounts/management/commands/desbloquear_usuario.py` (nuevo), `evaluon/accounts/management/commands/ver_accesos.py` (nuevo), `tests/accounts/test_origin.py` (nuevo), `tests/accounts/test_access_log.py`, `tests/accounts/test_unlock.py` (nuevo), `tests/accounts/test_ver_accesos.py` (nuevo).
- **Verificación:** `docker compose run --rm app pytest tests/accounts tests/audit` y la suite completa una vez al final; ningún detalle de los hechos lleva claves (`FORBIDDEN_DETAIL_KEYS`).
- **No tocar:** modelos y migraciones (T-272), `settings.py`, vistas y plantillas, middleware.

### T-274 · Cierre de la sesión por inactividad y a las 8 horas

- **Requisitos:** REQ-115, REQ-113
- **Nivel de verificación:** plena (lógica de sesión).
- **No arranca sin:** T-273 integrada (receptor de la salida).
- **Qué hay que hacer:**
  1. `accounts/session_policy.py` (nuevo): middleware después de `AuthenticationMiddleware` y antes de `LoginRequiredMiddleware`. Para un usuario con sesión:
     - guarda en la sesión el momento del ingreso (en la respuesta del ingreso) y el del último uso;
     - si pasaron `SESSION_MAX_HOURS` desde el ingreso, o `SESSION_IDLE_MINUTES` desde el último uso, pone el motivo (`max_age` o `idle`) en `request.evaluon_logout_reason`, llama a `logout` y manda al ingreso con `next`;
     - si no, y el pedido no trae `X-Evaluon-Poll`, actualiza el último uso.
  2. `settings.py`: la línea de `MIDDLEWARE`, `SESSION_IDLE_MINUTES = 30` y `SESSION_MAX_HOURS = 8`, y el comentario del bloque de sesiones. `SESSION_COOKIE_AGE` (8 horas), `SESSION_EXPIRE_AT_BROWSER_CLOSE` (verdadero) y `SESSION_SAVE_EVERY_REQUEST` (falso) no cambian.
  3. `static/journey/recorrido.js`: el sondeo manda `X-Evaluon-Poll: 1`. Su aviso de sesión vencida ya existe y no cambia.
  4. Tests:
     - a los 29 minutos sin uso sigue la sesión y a los 31 lleva al ingreso;
     - el sondeo durante 40 minutos no la mantiene;
     - con uso cada 20 minutos, a las 8 horas lleva al ingreso;
     - después de volver a ingresar, lo guardado antes sigue (un procedimiento creado por la función de negocio);
     - `logout` con `idle` o `max_age` y su origen;
     - la cookie sigue sin fecha de vencimiento;
     - `recorrido.js` manda el encabezado.
     El test de las 8 horas de `test_session.py` se ajusta: usa la sesión cada menos de 30 minutos.
- **Archivos:** `evaluon/accounts/session_policy.py` (nuevo), `evaluon/settings.py`, `evaluon/static/journey/recorrido.js`, `tests/accounts/test_session.py`, `tests/accounts/test_session_policy.py` (nuevo), y el test de `tests/journey/` que revise `recorrido.js`, si lo hay.
- **Verificación:** `docker compose run --rm app pytest tests/accounts tests/journey` y la suite completa una vez al final.
- **No tocar:** `apps.py` (el receptor es de T-273), `s3_ofertas.js`, plantillas, modelos.

### T-275 · Cambio de clave y clave inicial

- **Requisitos:** REQ-114, REQ-111
- **Nivel de verificación:** plena (seguridad y una pantalla nueva).
- **No arranca sin:** T-274 integrada (comparte `settings.py`), y la maqueta de la pantalla de cambio de clave y del enlace del encabezado aprobada por el responsable.
- **Qué hay que hacer:**
  1. Vista `cambiar-clave/` (`accounts:password_change`) sobre la de Django.
     - Rótulos: «Clave actual», «Clave nueva», «Repita la clave nueva». Los mensajes dicen «clave», no «contraseña», como `crear_usuario.password_problems`.
     - Clave actual equivocada: se rechaza, cuenta con `register_failed_attempt` y deja `login_failed` con `form: password_change`.
     - Cambio correcto: vuelve `must_change_password` a falso, deja `password_change` con su origen e `initial`, conserva la sesión y lleva al inicio con «Su clave se cambió.».
  2. `templates/accounts/cambiar_clave.html` según la maqueta aprobada, y el enlace «Cambiar clave» junto a «Salir» en `_cabecera.html`.
  3. `accounts/password_policy.py` (nuevo): middleware. Un usuario con `must_change_password` que pide cualquier cosa salvo el cambio de clave, la salida y el ingreso va al cambio de clave. El sondeo también: su aviso ya lo muestra la pantalla.
  4. `settings.py`: la línea de `MIDDLEWARE` (después de la de sesión) y `CommonPasswordValidator` en `AUTH_PASSWORD_VALIDATORS`. El mínimo de 8 no cambia.
  5. `crear_usuario`: el usuario nuevo queda con `must_change_password`, y la ayuda lo dice.
  6. `clave_inicial <usuario> --usuario <responsable>` (nuevo): `authenticate_command` y rol de lectura y escritura. Pide la clave dos veces, la valida y la guarda con `must_change_password`, y vuelve la cuenta a 0. Si el usuario estaba bloqueado, lo desbloquea y deja `unlock`. Siempre deja `initial_password`.
  7. `permissions.authenticate_command`: un usuario con `must_change_password` no pasa. Mensaje: «Tiene que cambiar su clave inicial: ingrese por la pantalla y cámbiela antes de usar los comandos.». No deja `login`; deja `rejected` con el motivo `must_change_password`.
  8. Tests:
     - REQ-114: con clave inicial, ninguna sección hasta cambiarla;
     - clave corta y clave común rechazadas, cada una con su motivo en castellano;
     - sin la clave actual correcta, se rechaza y cuenta para el bloqueo;
     - el cambio correcto quita la marca y queda registrado;
     - `crear_usuario` marca la clave inicial;
     - `clave_inicial`: rol, marca, desbloqueo y hechos;
     - un comando con clave inicial se rechaza;
     - el enlace está en el encabezado.
- **Archivos:** `evaluon/accounts/views.py`, `evaluon/accounts/urls.py`, `evaluon/accounts/password_policy.py` (nuevo), `evaluon/accounts/permissions.py`, `evaluon/accounts/management/commands/crear_usuario.py`, `evaluon/accounts/management/commands/clave_inicial.py` (nuevo), `evaluon/templates/accounts/cambiar_clave.html` (nuevo), `evaluon/templates/journey/_cabecera.html`, `evaluon/static/css/` (solo si la maqueta lo pide), `evaluon/settings.py`, `tests/accounts/test_password_change.py` (nuevo), `tests/accounts/test_clave_inicial.py` (nuevo), `tests/accounts/test_crear_usuario.py`.
- **Verificación:** `docker compose run --rm app pytest tests/accounts tests/journey` y la suite completa una vez al final. El Coordinador abre la pantalla y la compara con la maqueta antes de mostrarla.
- **No tocar:** `backends.py` (usa `register_failed_attempt` sin cambiarla), modelos y migraciones, `session_policy.py`, las pantallas de las secciones.

### T-276 · Instancia separada del piloto

- **Requisitos:** REQ-117, REQ-116
- **Nivel de verificación:** plena (principio P4, fase de operación, y P5).
- **No arranca sin:** T-269 integrada y T-049 de la 001 terminada (procedimiento de instalación y «Datos para el runbook»).
- **Qué hay que hacer:**
  1. `docker-compose.sin-gpu.yml` (nuevo; para la construcción mientras el piloto tiene el 27B): `generation_batch` y `worker` en el perfil `gpu`. `generation` ya está en un perfil en la configuración de uso, y nadie más espera a `generation_batch`. Embeddings y reranker de las dos instancias siguen encendidos: T-049 midió 20.940 MiB de 24.463 con el 27B y las dos parejas. Así `docker compose up -d` y `docker compose run --rm app pytest` en construcción no encienden un segundo 27B. Se suma a la combinación de uso, al final. Montarlo en `x-app` y en `app` para los tests.
  2. `scripts/piloto/gpu.ps1 -Para piloto|construccion [-SoloMostrar]` (lo corre el responsable), con las carpetas de las dos instancias como parámetros.
     - Del lado del piloto actúa por `compose.ps1`; del lado de construcción comprueba que el proyecto sea `evaluon`.
     - **Al piloto:** detiene `generation_batch` y `worker` de construcción (`stop -t 60`: el 27B tarda unos 20 s y puede avisar «did not receive an exit event»), suma `docker-compose.sin-gpu.yml` al `COMPOSE_FILE` del `.env` de construcción (guarda una copia del `.env`) y levanta `generation_batch` y `worker` del piloto.
     - **A la construcción:** lo mismo al revés: quita ese archivo del `COMPOSE_FILE`.
     - Espera hasta 15 minutos a que el motor de destino responda `/health` y su `/props` tenga el alias esperado. No usa `nvidia-smi` como prueba (T-049 lo vio marcar 0 MiB con el 27B cargado).
     - Con `-SoloMostrar` solo muestra lo que haría.
  3. `scripts/piloto/respaldar.ps1`:
     - actúa por `compose.ps1`;
     - hace el `pg_dump` dentro del contenedor a un archivo temporal y lo copia con `docker compose cp` a `C:\EVALUON-piloto\respaldos\`, con fecha y hora en el nombre (sin redirección de PowerShell, que daña el binario);
     - comprueba el respaldo con `pg_restore -l` y borra el temporal;
     - rechaza un destino dentro de una copia de Git o del perfil de usuario.
  4. `.gitattributes`: `scripts/models.sha256 text eol=lf`. En un clon de Windows hoy queda con CRLF y la verificación de las huellas falla (hallazgo de T-049).
  5. `specs/007-acceso-por-red/instancia-piloto.md`, para una persona no técnica. Todas las órdenes de Docker van por `compose.ps1`.
     - **Instalación:** el procedimiento de T-049 más:
       - la carpeta y el clon con el push desactivado;
       - el `.env`;
       - la copia de los modelos desde la construcción y su verificación con `bash scripts/fetch_models.sh` y `--qwen38-27b`, que con los archivos presentes solo comprueban la huella;
       - `compose.ps1 up -d`;
       - qué hacer si la imagen no se construye por Norton (remite al pendiente).
     - **Uso diario:** pasar el motor, respaldos, vaciar la base del piloto después de la aceptación (si el responsable lo aprueba, punto 7 del plan).
     - **Agentes:** qué pueden y qué no durante y después de la estabilización.
     - **Cierre de la estabilización:** texto propuesto de las reglas de denegación para la configuración de permisos de Claude Code, que aplica el responsable, cambio de la clave de la base y de la clave secreta, aviso al Coordinador.
     - **Lista de comprobación de REQ-117** para T-278.
  6. `tests/test_instancia_piloto.py`:
     - con `docker-compose.sin-gpu.yml`, `generation_batch` y `worker` quedan en el perfil y ningún servicio sin perfil los espera; embeddings y reranker no cambian;
     - `.gitattributes` fija `scripts/models.sha256` en LF;
     - en el piloto, solo `portal_worker` está en `egress`, los motores corren con `--offline` y las direcciones de IA son internas;
     - los nombres `evaluon-piloto` y `EVALUON-piloto` no aparecen en los scripts ni en los comandos de construcción (mediciones, respaldos, evals), salvo en `scripts/piloto/` y `scripts/red/`;
     - el destino por omisión de `respaldar.ps1` está fuera del repositorio.
- **Archivos:** `docker-compose.sin-gpu.yml` (nuevo), `docker-compose.yml` (solo montajes), `.gitattributes`, `scripts/piloto/gpu.ps1` (nuevo), `scripts/piloto/respaldar.ps1` (nuevo), `specs/007-acceso-por-red/instancia-piloto.md` (nuevo), `tests/test_instancia_piloto.py`, `tests/test_compose_env.py` (si el test de montajes lista los archivos).
- **Verificación:**
  - `docker compose run --rm app pytest tests/test_instancia_piloto.py tests/test_compose_env.py` y la suite completa una vez al final.
  - `docker compose config` con la combinación de uso más `docker-compose.sin-gpu.yml` no tiene `generation_batch` ni `worker` fuera del perfil, y `docker compose config --services` sin el perfil no los lista.
  - En un clon nuevo en Windows, `sha256sum -c` sobre `scripts/models.sha256` ya no falla por el fin de línea.
  - `gpu.ps1 -SoloMostrar` en las dos direcciones muestra los comandos esperados.
  - La corrida real de `gpu.ps1` y de `respaldar.ps1` es de T-278, con el responsable: esta tarea no apaga motores ni crea el proyecto `evaluon-piloto`.
- **No tocar:** `docker-compose.piloto.yml` (salvo hallazgo), `settings.py`, `accounts`, los contenedores y el `.env` de 8000.

### T-277 · Herramienta de medición de carga

- **Requisitos:** REQ-109 (requisito no funcional de carga de la spec)
- **Nivel de verificación:** plena (lógica de medición).
- **No arranca sin:** T-270 integrada (paquete `tests/red/`).
- **Qué hay que hacer:**
  1. `scripts/red/medir_carga.py` (biblioteca estándar).
     - **Sesiones:** N sesiones (10 por omisión) con usuarios de prueba que lee de un archivo fuera del repositorio. Cada una ingresa (con CSRF) y durante T minutos recorre las páginas de las cinco secciones de un procedimiento que se indica, con una pausa entre páginas, y pide la barra de secciones cada 5 s con `X-Evaluon-Poll`, como la pantalla.
     - **Resultado:** por página, mediana, p95, máximo y errores.
     - **Línea de base:** `--sesiones 1` desde el propio equipo, por la misma dirección cifrada. Por el puerto local sin cifrar no sirve: las cookies seguras no viajan.
     - **Cifrado:** verifica el certificado con `--ca`, que acepta más de un archivo. Si Norton intercepta en el equipo, se suma su raíz o se pausa su revisión durante la medición, y se anota cuál de las dos (hallazgo de T-049).
     - Guarda el resultado fuera del repositorio y nunca muestra claves.
  2. Tests, `tests/red/test_medir_carga.py`: el cálculo de mediana y p95, y una corrida de 2 sesiones por pocos segundos contra el `live_server` de pytest-django, que ingresa, recorre y resume.
- **Archivos:** `scripts/red/medir_carga.py` (nuevo), `tests/red/test_medir_carga.py` (nuevo).
- **Verificación:** `docker compose run --rm app pytest tests/red` y la suite completa una vez al final.
- **No tocar:** el código de la aplicación, los demás archivos de `scripts/red/`.

### T-278 · Prueba de aceptación en la red

- **Requisitos:** REQ-109 a REQ-117
- **Nivel de verificación:** plena. **Usa la GPU** (el 27B del piloto). Necesita al responsable, una computadora de la lista (A) y una de fuera (B).
- **No arranca sin:**
  - T-271, T-275, T-276 y T-277 integradas;
  - la instancia del piloto actualizada al commit de `main` según `instancia-piloto.md`, con solo material público;
  - la lectura del umbral de carga confirmada por el Coordinador;
  - el momento elegido por el responsable (el 27B de 8000 se apaga).
- **Qué hay que hacer, en este orden:**
  0. Fijar el commit. `gpu.ps1 -Para piloto` (primera corrida real): el 27B del piloto responde `/health` y su `/props` tiene el alias esperado, con el tiempo del cambio. No se usa `nvidia-smi` como prueba.
  1. **Caso chico (REQ-109, REQ-114).** Desde A, con un usuario evaluador recién creado: primer ingreso con cambio obligatorio de clave; con una clave corta, una común y la actual equivocada, rechazos con su motivo. Después, el recorrido del caso chico (los archivos públicos copiados a A) en las cinco secciones. Umbral: 5 de 5.
  2. **Cifrado (REQ-110).** `curl -sI` por `http` al ingreso, a una página de cada sección y a un estático: todas terminan en `https` sin cuerpo de la aplicación. 0 advertencias en A.
  3. **Bloqueo, registro y desbloqueo (REQ-111, REQ-112, REQ-113).** Desde A, 5 claves equivocadas y después la correcta: rechazada con el mismo mensaje. El mensaje se compara con el de un usuario inexistente y el de una clave equivocada. `desbloquear_usuario` en el equipo, y A ingresa enseguida. `ver_accesos` muestra los 4 hechos con la computadora A, su dirección, fecha y hora. Lo mismo por comando en el equipo.
  4. **Inactividad (REQ-115).** Desde A, una pantalla con sondeo abierta 31 minutos sin tocarla: el siguiente clic lleva al ingreso. Al volver a ingresar, lo guardado sigue.
  5. **Servicios internos y lista (REQ-116, REQ-109).** `revisar-puertos.ps1` desde A y desde B; 0 páginas desde B.
  6. **Carga.** `medir_carga.py` con 10 sesiones por el intermediario y la línea de base con una sola en el equipo, más la carga de cada sección en A con las herramientas del navegador.
  7. **Separación (REQ-117).** La lista de `instancia-piloto.md`:
     - la construcción con `docker-compose.sin-gpu.yml` no enciende su 27B (`docker compose ps`, y un `run --rm app pytest` de un solo test);
     - `compose.ps1` se niega con un `.env` de prueba sin `COMPOSE_PROJECT_NAME`;
     - `respaldar.ps1` deja el respaldo en la carpeta del piloto;
     - `git push --dry-run` del clon falla;
     - los servicios del piloto: motores con `--offline` y solo `portal_worker` en `egress`.
  8. `gpu.ps1 -Para construccion` y de vuelta, con el tiempo de cada cambio. El motor queda donde diga el responsable.
- **Umbral:** el de la tabla del plan, punto por punto.
- **Qué entrega:** `verificacion/T-278.md` con el commit, cada medida contra su umbral, los tiempos de los cambios de GPU, los hallazgos agrupados por causa y lo que pasa a la lista de revisión. Sin direcciones ni nombres del organismo y sin claves. Las salidas de `medir_carga.py` quedan fuera del repositorio. Si el responsable lo aprueba (punto 7 del plan), después se vacía la base del piloto según `instancia-piloto.md`.
- **Archivos:** solo `specs/007-acceso-por-red/verificacion/T-278.md`.
- **No tocar:** código, scripts, umbrales. Un hallazgo es de T-279, no un ajuste.

### T-279 · Ronda de ajuste única

- **Requisitos:** REQ-109 a REQ-117
- **Nivel de verificación:** plena.
- **Qué hay que hacer:** si T-278 no llegó a algún umbral, corregir **todos** los hallazgos en esta sola tarea, con un commit por hallazgo y su test que falla antes y pasa después. Por ejemplo, los hilos de Gunicorn en `docker-compose.piloto.yml` si la carga no llega. Después, repetir sobre el commit ajustado solo los puntos de T-278 que fallaron, con el responsable si son de red. Lo que siga sin llegar pasa con su impacto a la lista de revisión con el primer producto, salvo que se pierda un requisito o se viole un principio. Si T-278 cumplió todo, se cierra sin cambios.
- **Archivos:** los de T-269 a T-277 que el hallazgo señale, y `specs/007-acceso-por-red/verificacion/T-279.md`.
- **Verificación:** los tests del área de cada hallazgo y la suite completa una vez; la repetición de lo que falló, registrada en `verificacion/T-279.md`.
- **No tocar:** umbrales, y archivos que ningún hallazgo señale.
