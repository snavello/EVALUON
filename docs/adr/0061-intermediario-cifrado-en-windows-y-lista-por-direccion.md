# ADR-0061 · Intermediario cifrado en Windows y lista de computadoras por dirección fija

Estado: aceptado (versión 3, mínima) · Fecha: 2026-10-14 · Propuso: planificador (plan 007) · Decidió: responsable del proyecto (2026-10-14, «Ok», con el plan 007)

## Contexto

La spec 007 pide:

- que solo lleguen las computadoras de una lista que se cambia sin tocar el código (REQ-109);
- que todo viaje cifrado, sin advertencias (REQ-110);
- que cada ingreso quede con la computadora de origen (REQ-113);
- que los servicios internos no acepten conexiones de fuera (REQ-116).

Es una sola instancia, la de siempre (8000), publicada solo en `127.0.0.1` (versión mínima, decisión del responsable del 2026-10-14).

El hecho que decide: Docker Desktop no les pasa a los contenedores la dirección de quien se conecta. Su documentación dice que su proceso de fondo atiende el puerto publicado [1]. El pedido «Original ip is not passed to containers» sigue abierto, con comentarios de junio de 2026 [2]. Si el cifrado se hace dentro de Docker, no hay computadora de origen.

## Alternativas

### A. Caddy en Windows, como servicio, delante de 8000; lista por dirección

Caddy es un ejecutable único: 2.11.7, del 3 de octubre de 2026, con sumas SHA-512 publicadas [3]. Corre como servicio de Windows [4].

- Ve la dirección real.
- Corta lo que no está en la lista (`remote_ip` [6]).
- Redirige `http`.
- Reenvía a `127.0.0.1:8000` con `X-Forwarded-For` (ignora el que mande el cliente) y el nombre de la computadora [5].
- El firewall de Windows abre 80 y 443 solo para la lista.

- **Se gana:** la dirección real para el registro; Docker no cambia; sin código propio de red.
- **Se pierde:** una pieza fuera de Docker, que se instala una vez con un script, y la dependencia de direcciones fijas.

### B. Caddy en un contenedor y un certificado de cliente por computadora

- **Se gana:** todo en el compose, y una identidad que no depende de direcciones.
- **Se pierde:** instalar y elegir un certificado en cada computadora, pasos difíciles para personas no técnicas.

Es el camino si el área de sistemas no puede fijar direcciones.

### C. Caddy en un contenedor y la lista solo en el firewall

- **Se pierde:** no cumple REQ-113: dentro del contenedor todas llegan con la misma dirección. Descartada.

### D. Docker Engine directo en WSL2 con red espejada

- **Se gana:** según la comunidad, conservaría la dirección [7].
- **Se pierde:** cambia la base del entorno y el acceso a la GPU que hoy funciona. Descartada.

## Decisión

Se propone **A**, con lo indispensable para que funcione y no exponga:

- **`admin off`:** sin la API de administración local, que no pide clave. Se recarga reiniciando el servicio.
- **`auto_https off`, con el sitio `http` escrito a mano:** corta lo que no está en la lista y redirige el resto.
- **El sitio `https`:** el certificado de `C:\EVALUON-red\certificados\` (ADR-0062), el mismo corte, el nombre de la computadora en un encabezado y el reenvío a `127.0.0.1:8000`.
- **`default_sni` si se entra por IP.**
- **El firewall:** una regla de entrada TCP 80 y 443 para `caddy.exe`, solo desde la lista y el equipo, en todos los perfiles.

Un solo script de administrador (`aplicar-red.ps1`) instala Caddy la primera vez, comprobando la suma, y siempre arma el `Caddyfile` desde el `.env`, aplica la regla y reinicia el servicio. La aplicación toma los encabezados del intermediario, porque solo es alcanzable desde el propio equipo.

Los endurecimientos que la versión 2 sumaba (cuenta `LocalService`, permisos de carpetas, registro a archivo, solo HTTP/1.1 y HTTP/2, desinstalación) están en la lista de revisión con el primer producto.

**Relación con el ADR-0005:** suma el servicio que termina HTTPS que ese ADR dejó previsto en sus riesgos para abrir la aplicación a la red.

## Consecuencias

- **Más fácil:** Docker no cambia; la lista y el certificado cambian sin tocar el código.
- **Más difícil:** un servicio de Windows que mantener; las pruebas de red necesitan una persona y dos computadoras.
- **Riesgo aceptado:** un proceso del propio equipo puede falsear el origen pidiendo directo a `127.0.0.1:8000`.
- **Para revertir:** detener y borrar el servicio y la regla; la aplicación sigue igual.

## Fuentes

Consultadas el 2026-10-14.

1. Docker, «Explore networking features on Docker Desktop»: https://docs.docker.com/desktop/features/networking/
2. docker/roadmap #157: https://github.com/docker/roadmap/issues/157
3. Caddy, publicaciones: https://github.com/caddyserver/caddy/releases
4. Caddy, «Keep Caddy Running»: https://caddyserver.com/docs/running
5. Caddy, `reverse_proxy`: https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
6. Caddy, filtros de pedidos: https://caddyserver.com/docs/caddyfile/matchers
7. Foro de Docker, WSL2 con red espejada: https://forums.docker.com/t/host-networking-not-working-on-docker-desktop-in-wsl2-with-mirrored-mode/147994
