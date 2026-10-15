# ADR-0061 · Intermediario cifrado en Windows y lista de computadoras por dirección fija

Estado: propuesto (versión 2) · Fecha: 2026-10-14 · Propuso: planificador (plan 007) · Decidió: —

## Contexto

La spec 007 pide:

- **REQ-109:** que la aplicación se use solo desde las computadoras de una lista que el responsable cambia sin tocar el código.
- **REQ-110:** que todo viaje cifrado, con `http` redirigido y sin advertencias.
- **REQ-113:** que cada ingreso quede con la computadora de origen.
- **REQ-116:** que desde la red no se llegue a la base ni a los motores.

Hoy la aplicación se publica solo en `127.0.0.1:8000`, y la base y los motores están en una red interna de Docker sin puertos (ADR-0005).

Un hecho del equipo decide casi todo: Docker Desktop no les pasa a los contenedores la dirección de la computadora que se conecta.

- La documentación dice que el proceso de fondo de Docker Desktop escucha el puerto publicado y encamina la conexión al contenedor [1].
- El pedido «Original ip is not passed to containers» sigue abierto en la hoja de ruta de Docker; un comentario del 19 de junio de 2026 dice que todavía pasa, y otro, que con la red del anfitrión todos los clientes aparecen como `127.0.0.1` [2].

Si el cifrado y la lista se resuelven dentro de un contenedor, la aplicación no sabe desde qué computadora entró cada uno, y la lista solo se podría aplicar en el firewall de Windows. Esto se apoya en esas fuentes, que son de la documentación y de la comunidad; no se probó en este equipo.

Otras condiciones:

- **P4:** sin servicios externos en el camino de pliegos y ofertas.
- **P5:** se levanta con un comando y lo manual queda documentado.
- **P10:** lo mínimo.
- **Quién opera:** lo de Windows y la red lo hace el responsable, que no es técnico.
- **Quién más corre en el equipo:** los agentes de construcción, con el mismo usuario de Windows. Nada que escuche en el equipo puede quedar sin control de acceso, y nada que corra como administrador puede leer código que ese usuario modifique.

Versiones y fechas consultadas el 2026-10-14.

## Alternativas

### A. Caddy en Windows, como servicio sin privilegios, delante de la aplicación; lista por dirección fija en el firewall y en Caddy

Caddy es un servidor web de un solo ejecutable. Versión estable 2.11.7, del 3 de octubre de 2026, con sumas publicadas en SHA-512 [3]. Corre como servicio de Windows [4].

Atiende 80 y 443 en Windows, donde ve la dirección real:

- cifra con el certificado de una carpeta protegida;
- redirige `http`;
- corta las conexiones que no son de la lista (`remote_ip` [6]);
- reenvía a `127.0.0.1:8100`.

Su `reverse_proxy` pone `X-Forwarded-For` y `X-Forwarded-Proto`, ignora esos encabezados si vienen del cliente y pasa el `Host` sin cambios [5]. Se le suma un encabezado con el nombre de la computadora.

El firewall de Windows deja entrar a 80 y 443 solo desde la lista. La lista vive en el `.env` del piloto y un script la aplica.

- **Se gana:**
  - la dirección real para el registro;
  - Docker no publica nada hacia la red;
  - cifrado, redirección, lista y encabezados en una configuración corta, sin código propio de red;
  - cambiar la lista o el certificado no reinicia la aplicación.
- **Se pierde:**
  - una pieza fuera de Docker, que se instala una vez con un script (nota en P5);
  - es propio de Windows;
  - depende de direcciones fijas y de que no haya proxy ni traducción de direcciones en el medio;
  - la dirección no es una identidad fuerte: quien tome la dirección de una computadora de la lista llega al ingreso, igual necesita usuario y clave, y el registro lo anota con el nombre de esa computadora;
  - hay que seguir sus versiones.

### B. nginx en Windows

La misma arquitectura con nginx.

- **Se gana:** es el más difundido.
- **Se pierde:** la versión para Windows «se considera beta», no corre como servicio y solo un proceso trabaja [7]. Descartada frente a A.

### C. Intermediario en un contenedor y un certificado de cliente por computadora

Cada computadora tiene un certificado de cliente emitido por EVALUON, y el intermediario solo acepta conexiones con un certificado de la lista.

- **Se gana:** todo en el compose, y una identidad criptográfica que no depende del área de sistemas.
- **Se pierde:**
  - hay que instalar y elegir un certificado en cada computadora, salvo que el área de sistemas fije una política;
  - la clave se puede copiar a otra computadora;
  - Docker publica 80 y 443 hacia la red.

Es la alternativa si no se pueden fijar direcciones.

### D. Intermediario en un contenedor, lista solo en el firewall de Windows

- **Se pierde:** **no cumple REQ-113**. Con TLS en Gunicorn pasa lo mismo, y además falta la redirección. Descartada.

### E. Docker Engine directo en WSL2, con la red espejada, sin Docker Desktop

- **Se gana:** según informes de la comunidad, los contenedores verían la dirección real [8]. No se probó en este equipo.
- **Se pierde:** cambia la base de todo el entorno, incluido el acceso a la GPU que hoy funciona con Docker Desktop, y arriesga el equipo de uso para ganar lo que A ya da. Descartada por eso, no por falta de informes.

## Decisión

Se propone **A**, así:

1. **Instalación.** `scripts/red/instalar-red.ps1`, como administrador, una vez, desde un clon limpio en el commit aprobado:
   - baja la versión fijada de Caddy y la comprueba con `Get-FileHash -Algorithm SHA512` contra la línea copiada de `caddy_<versión>_checksums.txt`;
   - crea `C:\Program Files\EVALUON-Red\` (ejecutable y scripts de administrador), `C:\ProgramData\EVALUON-Red\` (configuración, certificados, almacenamiento y registro) y `C:\EVALUON-piloto\`, con la herencia de permisos cortada;
   - registra el servicio `EVALUON-Caddy` con la cuenta `NT AUTHORITY\LocalService`, que lee la configuración y los certificados y escribe solo su almacenamiento y su registro.

   Escuchar en 80 y 443 en Windows no exige privilegios.
2. **Configuración de Caddy:**
   - `admin off` (sin API de administración local, que no pide autenticación); se recarga reiniciando el servicio;
   - `auto_https off` (la redirección es explícita), `ocsp_stapling off`, solo HTTP/1.1 y HTTP/2 (sin UDP 443), sin instalar raíces;
   - `default_sni` cuando se entra por IP, porque los navegadores no mandan el nombre del servidor para una dirección IP;
   - registro a archivo con rotación;
   - encabezado HSTS solo cuando se entra por nombre.

   Corta toda conexión que no venga de la lista o del equipo, redirige `http` con 308, cifra con `C:\ProgramData\EVALUON-Red\certificados\` (ADR-0062) y reenvía a `127.0.0.1:8100` con `X-Forwarded-For`, `X-Forwarded-Proto` y `X-Evaluon-Computer`.
3. **La lista:** `EVALUON_COMPUTERS` en el `.env` del piloto (IPv4, 10 como máximo).
   - `scripts/red/caddy.py` corre **sin** administrador y deja el `Caddyfile` y la lista en `C:\EVALUON-piloto\entrada\`.
   - `aplicar-red.ps1` corre como administrador desde `C:\Program Files\EVALUON-Red\`, donde un usuario común no escribe; nunca ejecuta código del clon, ni Python:
     - muestra la lista y pide confirmación;
     - valida con `caddy.exe`;
     - mueve los archivos a `C:\ProgramData\EVALUON-Red\`;
     - crea o actualiza la regla del firewall (TCP 80 y 443, `caddy.exe`, solo esas direcciones, `-Profile Any`, porque una notebook fuera de dominio ve la red del organismo como «Pública»);
     - desactiva otras reglas de entrada de `caddy.exe`;
     - se detiene si el firewall está apagado en la red actual;
     - reinicia el servicio.
   - `desinstalar-red.ps1` deshace el servicio y la regla.
4. **Cómo se reconoce una computadora:** por su IPv4. Supuestos que se piden al área de sistemas:
   - direcciones fijas por computadora;
   - dirección fija del equipo, por cable;
   - EVALUON fuera del proxy;
   - sin traducción de direcciones;
   - si se puede, protección contra quien tome una dirección ajena.

   Si no se cumplen, se pasa a C.
5. **La aplicación toma los encabezados**, porque solo es alcanzable desde el propio equipo. Sin encabezados, el pedido vino directo y se registra como `acceso-directo-local`.

## Relación con el ADR-0005

El ADR-0005 decidió «no se agregan: servidor web intermedio…», y en sus riesgos dejó dicho que antes de abrir la aplicación a la red había que sumar un servicio que termine HTTPS. Este ADR suma ese intermediario. Al aceptarlo, el Coordinador agrega al ADR-0005 una nota «Actualización por ADR-0061 y ADR-0063».

## Consecuencias

Más fácil:

- REQ-116 no depende de reglas nuevas.
- La lista y el certificado cambian sin tocar el código.
- Si el firewall queda mal, Caddy vuelve a controlar la lista.
- Sin API de administración, cambiar la configuración exige administrador.

Más difícil:

- Hay un servicio de Windows que mantener.
- Las pruebas de red necesitan una persona y dos computadoras.
- La dirección como identidad depende del área de sistemas.
- Un proceso del propio usuario puede pedir directo a `127.0.0.1:8100` con encabezados falsos. Es un riesgo aceptado: ese usuario ya puede entrar a los contenedores.

Para revertir: `desinstalar-red.ps1`. La aplicación no cambia. Pasar a C reusa la configuración dentro de un contenedor.

## Sin verificar

- Los nombres exactos de las opciones globales en la 2.11.7 (`admin off`, `auto_https off`, `ocsp_stapling off`, `protocols`, `skip_install_trust`, `default_sni`, `storage`), que `abort` quede en el registro y que `auto_https off` sirva el certificado cargado a mano. Los fija T-270 con `caddy adapt` y los prueba T-271.
- La publicación de Windows amd64 de la 2.11.7: T-270 la confirma.
- Si Windows muestra el aviso del firewall para un programa que corre como servicio.

## Fuentes

Consultadas el 2026-10-14.

1. Docker, «Explore networking features on Docker Desktop»: https://docs.docker.com/desktop/features/networking/
2. docker/roadmap #157, «Original ip is not passed to containers»: https://github.com/docker/roadmap/issues/157
3. Caddy, publicaciones (v2.11.7, 3 de octubre de 2026; sumas SHA-512 en `caddy_2.11.7_checksums.txt`): https://github.com/caddyserver/caddy/releases
4. Caddy, «Keep Caddy Running» (servicio de Windows): https://caddyserver.com/docs/running
5. Caddy, `reverse_proxy`: https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
6. Caddy, filtros de pedidos: https://caddyserver.com/docs/caddyfile/matchers
7. nginx para Windows: https://nginx.org/en/docs/windows.html
8. Foro de Docker, Docker en WSL2 con red espejada: https://forums.docker.com/t/host-networking-not-working-on-docker-desktop-in-wsl2-with-mirrored-mode/147994 (y otros hilos del foro citados en la revisión del plan)
