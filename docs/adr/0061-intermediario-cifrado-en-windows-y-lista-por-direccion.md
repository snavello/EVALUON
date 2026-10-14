# ADR-0061 · Intermediario cifrado en Windows y lista de computadoras por dirección fija

Estado: propuesto · Fecha: 2026-10-14 · Propuso: planificador (plan 007) · Decidió: —

## Contexto

La spec 007 pide cuatro cosas de la red:

- que la aplicación se use solo desde las computadoras de una lista que el responsable cambia sin tocar el código (REQ-109);
- que todo viaje cifrado, con `http` redirigido y sin advertencias del navegador (REQ-110);
- que cada ingreso quede con la computadora de origen (REQ-113);
- que desde la red no se llegue a la base ni a los motores (REQ-116).

Hoy la aplicación se publica solo en `127.0.0.1:8000` y la base y los motores están en una red interna de Docker sin puertos (ADR-0005). Hay que elegir quién atiende la red, quién cifra y cómo se reconoce cada computadora.

Un hecho del equipo decide casi todo. El equipo es una notebook con Windows 11 y Docker Desktop sobre WSL2, y **Docker Desktop no les pasa a los contenedores la dirección de la computadora que se conecta**:

- La documentación dice que, para un puerto publicado, «el proceso de fondo de Docker Desktop escucha en el puerto» y la conexión se encamina al contenedor [1]. El contenedor ve la conexión que abre ese proceso, no la del cliente.
- El pedido «Original ip is not passed to containers» sigue abierto en la hoja de ruta de Docker [2]. El último comentario es del 19 de junio de 2026: «Three years later, this is still relevant». Otro informa que con la red del anfitrión (`host`) todos los clientes aparecen como `127.0.0.1`.
- En los foros, Docker Desktop no usa la red espejada de WSL [3].

Consecuencia: si el cifrado y la lista se resuelven dentro de un contenedor, la aplicación no puede saber desde qué computadora entró cada uno. REQ-113 no se cumpliría, y la lista por dirección solo se podría aplicar en el firewall de Windows.

Otras condiciones:

- P4: el camino de pliegos y ofertas no depende de servicios externos (sin certificados pedidos a internet).
- P5: todo se levanta con un comando y lo que se configura a mano queda documentado.
- P10: lo mínimo.
- Lo de Windows y de la red lo hace el responsable, que no es técnico, siguiendo el runbook.
- El área de sistemas del organismo puede dar direcciones fijas y un nombre en su DNS (a confirmar).

Las versiones y fechas se consultaron el 2026-10-14.

## Alternativas

### A. Caddy en Windows, como servicio, delante de la aplicación; lista por dirección fija en el firewall y en Caddy

Caddy es un servidor web de un solo ejecutable. La versión estable vigente es la 2.11.7, del 3 de octubre de 2026, y publica sumas de verificación [4]. Corre como servicio de Windows con `sc.exe create … binPath= "…\caddy.exe run"` y se recarga con `caddy reload` [5].

Caddy atiende 80 y 443 en Windows, donde ve la dirección real de cada computadora:

- cifra con el certificado de una carpeta (ADR-0062);
- redirige `http` a `https`;
- corta (`abort`) toda conexión cuya dirección no esté en la lista (`remote_ip` es la dirección de quien se conecta [7]);
- reenvía a `127.0.0.1:8100`, el puerto que Docker publica solo en el propio equipo.

Por omisión, su `reverse_proxy` pone `X-Forwarded-For` y `X-Forwarded-Proto`, ignora esos encabezados si vienen del cliente («to prevent spoofing») y pasa el `Host` sin cambios [6]. A eso se suma un encabezado con el nombre de la computadora en la lista.

El firewall de Windows deja entrar a 80 y 443 solo desde las direcciones de la lista. La lista vive en el `.env` del piloto y un script la aplica al firewall y a Caddy.

- **Se gana:**
  - La dirección real de cada computadora, para el registro.
  - Docker no publica nada hacia la red: REQ-116 se cumple como hoy, sin depender de reglas.
  - Cifrado, redirección, lista y encabezados en una pieza con una configuración de unas 20 líneas, sin código propio de red.
  - Cambiar la lista o el certificado no reinicia la aplicación.
- **Se pierde:**
  - Una pieza fuera de Docker. Se instala una vez con un script (versión y huella fijas) y arranca sola como servicio, pero `docker compose up` no la levanta (nota en P5).
  - Es propio de Windows: en otro sistema habría que instalarla de otra forma.
  - Depende de que cada computadora tenga una dirección fija y de que no haya un proxy ni una traducción de direcciones en el medio (pedidos al área de sistemas).
  - La dirección no es una identidad fuerte: otro aparato que tome la dirección de una computadora apagada llega al ingreso (igual necesita usuario y clave).
  - Hay que seguir las versiones de Caddy.

### B. nginx en Windows, como servicio, en lugar de Caddy

La misma arquitectura que A, con nginx.

- **Se gana:** es el intermediario más difundido.
- **Se pierde:** la versión para Windows «se considera beta». Usa solo `select()` y `poll()` («no se debe esperar alto rendimiento»), solo un proceso trabaja aunque se arranquen varios, y no corre como servicio: es «una aplicación de consola estándar» [8]. Habría que sumar un programa que lo envuelva como servicio y escribir a mano la redirección y la configuración de cifrado, que Caddy trae resueltas. Descartada frente a A.

### C. Intermediario en un contenedor y un certificado de cliente por computadora (TLS mutuo)

Caddy en un contenedor del compose, publicado en 80 y 443. Cada computadora de la lista tiene un certificado de cliente emitido por EVALUON, y el intermediario solo acepta conexiones con un certificado de la lista y le pasa su nombre a la aplicación. La identidad no depende de la dirección.

- **Se gana:**
  - Todo dentro del compose (P5 sin nota).
  - Identidad criptográfica de cada computadora, que no depende del área de sistemas.
- **Se pierde:**
  - Hay que emitir e instalar un certificado de cliente en cada computadora y elegirlo en el navegador cada vez, salvo que el área de sistemas fije una política de selección automática. Son pasos difíciles para personas no técnicas.
  - La clave del certificado se puede copiar a otra computadora: identifica a quien lo tiene, no a la computadora.
  - Quitar una computadora es sacar su certificado de la lista y recargar.
  - Docker publica 80 y 443 hacia la red, y lo demás depende del firewall.

Es la alternativa si el área de sistemas no puede fijar direcciones.

### D. Intermediario en un contenedor, lista solo en el firewall de Windows

Lo mismo que C sin certificados de cliente. El firewall filtra por dirección, porque él sí la ve.

- **Se gana:** lo más simple y todo en el compose.
- **Se pierde:** **no cumple REQ-113**: dentro del contenedor todas las computadoras llegan con la misma dirección interna. Con TLS en Gunicorn en lugar de Caddy pasa lo mismo, y además no hay redirección de `http` sin un segundo proceso. Descartada.

### E. Docker Engine directo en WSL2 con red espejada, sin Docker Desktop

- **Se gana:** quizá los contenedores vean la dirección real. Alguien lo preguntó en [2] el 19 de junio de 2026 y no hay respuesta.
- **Se pierde:**
  - No está verificado.
  - Cambia la base de todo el entorno, incluido el acceso a la GPU que hoy funciona con Docker Desktop.
  - Arriesga el equipo de uso para ganar algo que A ya da.

Descartada.

## Decisión

Se propone **A**.

1. **Caddy 2.11.x en Windows**, como servicio que arranca solo, instalado con `scripts/red/instalar-caddy.ps1`: versión fijada, huella comprobada contra la suma publicada, carpeta `C:\EVALUON-piloto\caddy\`.
2. **Escucha 80 y 443 hacia la red.** Corta toda conexión que no venga de la lista o del propio equipo. Redirige `http` a `https` con 308. Cifra con `certificados\evaluon.crt` y `evaluon.key` (ADR-0062). Reenvía a `127.0.0.1:8100` con `X-Forwarded-For`, `X-Forwarded-Proto` y `X-Evaluon-Computer`. Sin certificados automáticos ni consultas a internet; la administración, solo en `localhost`.
3. **La lista:** `EVALUON_COMPUTERS` en el `.env` de la instancia del piloto (`nombre=dirección`, IPv4, 10 como máximo). `scripts/red/aplicar-red.ps1`, que corre el responsable como administrador:
   - genera el `Caddyfile` con `scripts/red/caddy.py`;
   - crea o actualiza la regla de entrada del firewall (TCP 80 y 443, programa `caddy.exe`, solo esas direcciones, perfiles de dominio y privado) y desactiva otras reglas de entrada de `caddy.exe`;
   - recarga Caddy.

   Agregar o quitar una computadora es editar una línea y correr el script.
4. **Cómo se reconoce una computadora:** por su dirección IPv4. Supuestos, que se le piden al área de sistemas:
   - dirección fija por computadora (reserva de DHCP);
   - dirección fija del equipo del sistema;
   - EVALUON fuera del proxy web;
   - sin traducción de direcciones entre la Comisión y el equipo.

   Si alguno no se cumple, se pasa a C.
5. **La aplicación confía en los encabezados**, porque solo es alcanzable desde el propio equipo. Sin encabezados, el pedido vino directo por el puerto local y se registra como «equipo del sistema».

## Consecuencias

Más fácil:

- REQ-116 no depende de reglas nuevas: Docker no publica nada hacia la red.
- La lista y el certificado cambian sin tocar el código ni reiniciar la aplicación.
- Si el firewall queda mal (por ejemplo, porque alguien aceptó el aviso de Windows que abre Caddy a todos), Caddy vuelve a controlar la lista.

Más difícil:

- Hay un servicio de Windows que mantener y actualizar (versión y huella en el repositorio).
- Las pruebas de red necesitan una persona y dos computadoras (T-271, T-278).
- La dirección como identidad depende del área de sistemas.

Para revertir: desinstalar el servicio y borrar la regla del firewall; la aplicación no cambia (solo lee encabezados). Pasar a C reusa casi toda la configuración de Caddy dentro de un contenedor y suma los certificados de cliente.

## Sin verificar

- El comportamiento de Docker Desktop sale de su documentación y de [2] y [3]; no se probó en este equipo. T-271 lo ve: el registro de acceso de Gunicorn muestra la dirección interna.
- Los nombres exactos de las opciones globales de Caddy 2.11.7 para no pedir certificados ni consultar a internet, y la forma de `abort` y de `map`, se fijan en T-270 con la documentación de la versión. Las páginas de [7] muestran `abort` con `remote_ip` en sus ejemplos, pero no lo definen.
- No se verificó la publicación de Windows amd64 de la 2.11.7: la lista de archivos de [4] estaba cortada. T-270 lo confirma.
- No se verificó si Windows muestra el aviso del firewall para un programa que corre como servicio.

## Fuentes

Consultadas el 2026-10-14.

1. Docker, «Explore networking features on Docker Desktop»: https://docs.docker.com/desktop/features/networking/
2. docker/roadmap #157, «Original ip is not passed to containers»: https://github.com/docker/roadmap/issues/157
3. Foro de Docker, «Host networking not working on Docker Desktop in WSL2 with mirrored mode»: https://forums.docker.com/t/host-networking-not-working-on-docker-desktop-in-wsl2-with-mirrored-mode/147994
4. Caddy, publicaciones (v2.11.7, 3 de octubre de 2026; v2.11.6, 1 de octubre de 2026): https://github.com/caddyserver/caddy/releases
5. Caddy, «Keep Caddy Running» (servicio de Windows): https://caddyserver.com/docs/running
6. Caddy, `reverse_proxy`: https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
7. Caddy, filtros de pedidos (`remote_ip`, `client_ip`, `not`): https://caddyserver.com/docs/caddyfile/matchers
8. nginx para Windows: https://nginx.org/en/docs/windows.html
