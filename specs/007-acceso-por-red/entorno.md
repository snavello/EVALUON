# Entorno de la 007 · Acceso por red

Estado: preparado por T-269 (2026-10-14). Sin aplicar: lo aplica el responsable en la verificación del corte vertical.

Este documento dice cómo abrir EVALUON a las computadoras de la Comisión, paso por paso, con cada comando y lo que tiene que verse. Sigue el plan 007 («Pasos del responsable») y los ADR-0061 y ADR-0062.

**Cómo queda.** Las computadoras de la lista entran por `https://<dirección>`. En el equipo del sistema, Caddy (un programa chico, instalado como servicio de Windows) recibe la conexión cifrada, corta a toda computadora que no esté en la lista y le pasa el pedido a la aplicación de siempre, en `127.0.0.1:8000`. El firewall de Windows deja entrar a los puertos 80 y 443 solo a la lista. Docker no cambia: la aplicación sigue publicada solo en el propio equipo, y la base y los motores de IA siguen sin puertos hacia afuera.

En este documento `<dirección>` es la dirección con que se entra (`EVALUON_ADDRESS`): un nombre del DNS interno o la IP fija del equipo. Los ejemplos usan direcciones de documentación (`192.0.2.x`); en el `.env` van las de la red del organismo, que no se escriben en el repositorio.

## Qué queda dónde

| Dónde | Qué | Quién lo escribe |
|---|---|---|
| `.env` de la raíz | `EVALUON_ADDRESS`, `EVALUON_SERVER_IP`, `EVALUON_COMPUTERS` y la dirección en `DJANGO_ALLOWED_HOSTS` | el responsable |
| `scripts/red/caddy.py` y `Caddyfile.plantilla` | arman el `Caddyfile` desde el `.env` y validan la lista | repositorio |
| `scripts/red/aplicar-red.ps1` | instala Caddy la primera vez y siempre aplica la lista (Caddy y firewall) | repositorio |
| `scripts/red/caddy.sha512` | la suma publicada del zip de Caddy 2.11.7 para Windows | repositorio |
| `scripts/red/crear-certificados.sh` | crea la autoridad propia y el certificado | repositorio |
| `C:\EVALUON-red\caddy.exe` | Caddy 2.11.7 | `aplicar-red.ps1` |
| `C:\EVALUON-red\Caddyfile` | la configuración de Caddy; no se edita a mano | `aplicar-red.ps1` |
| `C:\EVALUON-red\certificados\evaluon.crt` y `evaluon.key` | el certificado que usa Caddy | `crear-certificados.sh`, o los del área de sistemas |
| `C:\EVALUON-red\autoridad\` | la autoridad propia; se usa solo para renovar | `crear-certificados.sh` |
| `C:\EVALUON-red\ca-evaluon.crt` | la raíz para instalar en las computadoras de la lista | `crear-certificados.sh` |
| Servicio `EVALUON-Caddy` | Caddy, con arranque automático | `aplicar-red.ps1` |
| Regla de firewall «EVALUON» | entrada TCP 80 y 443, solo `caddy.exe`, solo la lista y el equipo | `aplicar-red.ps1` |

`C:\EVALUON-red\` está fuera del repositorio: ninguna clave ni certificado se sube.

## Pedido al área de sistemas

1. Permiso para conectar la notebook a la red del organismo, por cable, y que las computadoras de la Comisión lleguen a ella por TCP 443 y 80.
2. Dirección fija para la notebook y, si se puede, un nombre en el DNS interno.
3. Direcciones fijas para las computadoras de la Comisión (hasta 10).
4. Que la dirección de EVALUON quede fuera del proxy web y de la inspección de conexiones cifradas del antivirus.
5. Que instalen la raíz de EVALUON en esas computadoras (o den permiso), o, si prefieren, un certificado propio del organismo para esa dirección.
6. Qué navegador usa la Comisión, y que no restaure la sesión al reabrir.

## Pasos del responsable (una vez)

### 1. La notebook

- Docker Desktop arranca al iniciar sesión: en Docker Desktop, *Settings* → *General* → *Start Docker Desktop when you sign in to your computer*.
- No se suspende enchufada: *Configuración* → *Sistema* → *Energía* → *Cuando esté enchufado, poner el dispositivo en suspensión después de*: *Nunca*.
- Al dejarla, bloquear la sesión de Windows (tecla Windows + L), no cerrarla: Docker Desktop necesita la sesión abierta. Caddy sí arranca solo, aunque nadie inicie sesión; sin Docker, responde «502» en lugar de la aplicación.

### 2. Completar el `.env`

El `.env` de la raíz del repositorio. Al final hay un bloque comentado «Acceso por red (plan 007)» en `.env.example` con la forma de cada variable. Por ejemplo:

```
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.0.2.10
EVALUON_ADDRESS=192.0.2.10
EVALUON_SERVER_IP=192.0.2.10
EVALUON_COMPUTERS=comision-1=192.0.2.21,comision-2=192.0.2.22
```

- `EVALUON_ADDRESS`: el nombre que dio el área de sistemas (sin `https://`), o la IP fija de la notebook.
- `EVALUON_SERVER_IP`: la IP fija de la notebook. Se ve con `ipconfig`, en «Dirección IPv4» del adaptador de cable.
- `EVALUON_COMPUTERS`: `nombre=IP` de cada computadora, separadas por comas, 10 como máximo. La IP de cada una se ve con `ipconfig` en esa computadora. El nombre (letras sin acentos, números y guiones) es el que va a quedar en el registro de accesos. La notebook no va en la lista: entra siempre, como `equipo-del-sistema`.
- `DJANGO_ALLOWED_HOSTS`: agregar la dirección al final, separada por una coma.

Después, recrear la aplicación para que tome `DJANGO_ALLOWED_HOSTS`, desde la raíz del repositorio:

```
docker compose up -d --no-deps app
```

### 3. Crear el certificado propio

En Git Bash, desde la raíz del repositorio (lee la dirección del `.env`, por eso va después del paso 2):

```
bash scripts/red/crear-certificados.sh
```

Tiene que terminar con `Listo.` y mostrar:

- la «Huella SHA-1» de la raíz: anotarla, para compararla en cada computadora al instalarla;
- el vencimiento de la raíz (10 años) y el del certificado del servidor (397 días).

Si se va a usar el certificado del área de sistemas, este paso se reemplaza por el de la sección «Poner el certificado del área de sistemas».

### 4. Aplicar

En PowerShell **como administrador** (Inicio → escribir `PowerShell` → *Ejecutar como administrador*), desde la raíz del repositorio:

```
cd <carpeta del repositorio>
powershell -ExecutionPolicy Bypass -File scripts\red\aplicar-red.ps1
```

Lo que tiene que verse, en orden:

1. La primera vez: `== Bajando Caddy (solo la primera vez)`, `Suma SHA-512 comprobada: coincide con la publicada.` y `== Registrando el servicio EVALUON-Caddy (arranque automático)`. Es el único paso que usa internet.
2. `Caddyfile escrito en C:\EVALUON-red\Caddyfile.`
3. `Caddy acepta la configuración.`
4. `Entrada por TCP 80 y 443 solo desde:` y la IP de la notebook seguida de las de la lista. Si Windows había creado reglas `Block` para `caddy.exe` (pasa si alguien lo corrió a mano), además una línea amarilla `Se quitó la regla «…» (Inbound, Block)…` por cada una.
5. `== Listo`, la dirección, la lista con nombre e IP, y `Servicio EVALUON-Caddy: Running, atiende en 80 y 443.`

Si el `.env` tiene algo mal, el script lo dice en lenguaje llano (por ejemplo, una IP inválida o repetida, más de 10 computadoras, o la dirección que falta en `DJANGO_ALLOWED_HOSTS`) y no cambia nada: corregir el `.env` y volver a correrlo.

### 5. En cada computadora de la lista: instalar la raíz, una vez

Necesita un usuario administrador de esa computadora, o el área de sistemas.

1. Copiar `C:\EVALUON-red\ca-evaluon.crt` a la computadora (pendrive o carpeta compartida). Es un certificado público: no tiene claves.
2. Doble clic en `ca-evaluon.crt` → pestaña *Detalles* → *Huella digital*: tiene que ser la huella SHA-1 que mostró el paso 3. Si no coincide, no instalarlo.
3. *Instalar certificado...* → *Equipo local* → *Colocar todos los certificados en el siguiente almacén* → *Examinar* → *Entidades de certificación raíz de confianza* → *Siguiente* → *Finalizar*.

   O, en una consola como administrador, en la carpeta donde se copió: `certutil -addstore -f Root ca-evaluon.crt`.
4. Cerrar todas las ventanas del navegador y volver a abrirlo. Edge y Chrome toman la raíz de Windows; Firefox 120 o posterior también, salvo que una política del organismo lo impida.
5. Abrir `https://<dirección>` y guardarlo en favoritos. Tiene que aparecer la pantalla de ingreso sin ninguna advertencia.

La raíz solo sirve para certificados de servidor de la dirección de EVALUON y de la IP de la notebook (ADR-0062): no le permite a nadie hacerse pasar por otro sitio.

## Agregar o quitar una computadora

1. Editar `EVALUON_COMPUTERS` en el `.env`.
2. Repetir el paso 4 (`aplicar-red.ps1` como administrador). No se toca el código ni se reinicia Docker.
3. Una computadora nueva necesita la raíz (paso 5). A una que se quita no hace falta sacarle la raíz: ya no llega.

## Poner el certificado del área de sistemas

Variante A del ADR-0062. Pedirles un certificado de servidor para la dirección de EVALUON (con el nombre o la IP como «nombre alternativo»), en formato PEM: el certificado seguido de los intermedios, y la clave privada sin contraseña.

1. Guardarlos como `C:\EVALUON-red\certificados\evaluon.crt` (el certificado y los intermedios) y `evaluon.key` (la clave), reemplazando los que hay.
2. Repetir el paso 4.
3. Comprobar desde una computadora de la lista que entra sin advertencias. Después se puede quitar la raíz propia de las computadoras: `certutil -delstore Root "EVALUON autoridad propia"` (como administrador).

Con el certificado del organismo, **no volver a correr** `crear-certificados.sh`: pisa esos dos archivos.

Si lo entregan en un solo archivo `.pfx`, en Git Bash: `openssl pkcs12 -in archivo.pfx -clcerts -nokeys -out evaluon.crt`, `openssl pkcs12 -in archivo.pfx -cacerts -nokeys >> evaluon.crt` y `openssl pkcs12 -in archivo.pfx -nocerts -nodes -out evaluon.key` (pide la contraseña del `.pfx`).

## Renovar el certificado cada año

El certificado del servidor dura 397 días; la autoridad, 10 años. Antes de que venza el del servidor:

1. En Git Bash, desde la raíz del repositorio: `bash scripts/red/crear-certificados.sh`. Usa la misma autoridad y muestra el vencimiento nuevo.
2. En PowerShell como administrador: `Restart-Service EVALUON-Caddy` (o repetir el paso 4).

No se toca nada en las computadoras. Para ver cuándo vence el actual: `openssl x509 -in C:/EVALUON-red/certificados/evaluon.crt -noout -enddate`.

**Si cambia la dirección** (otro nombre u otra IP de la notebook), la autoridad no la cubre y el script lo dice. Entonces: borrar `C:\EVALUON-red\autoridad\`, correr el script, instalar la raíz nueva en cada computadora (paso 5) y quitar la vieja (`certutil -delstore Root "EVALUON autoridad propia"` antes de instalar la nueva).

## Comprobaciones del corte vertical (T-269)

Antes: pasos 1 a 5 hechos, con la computadora A en la lista y la B fuera (B puede ser A sacada de la lista). El Coordinador recrea `app` de 8000 y crea un usuario de prueba con rol de la Comisión. Se registra en `verificacion/T-269.md`, sin direcciones de la red del organismo ni claves.

### Desde A

1. En el navegador, `https://<dirección>`: la pantalla de ingreso, con el candado y **sin advertencias**. Ingresar con el usuario de prueba y abrir el caso chico (si no está cargado en 8000, subir su pliego).
2. En PowerShell (sin administrador):

   ```
   curl.exe -si http://<dirección>/ingresar/
   ```

   Muestra la respuesta completa: los encabezados `HTTP/1.1 308 Permanent Redirect`, `Location: https://<dirección>/ingresar/`, `Server: Caddy`, `Date` y `Content-Length: 0`, y nada más después de ellos. La redirección es de Caddy, sin nada de la aplicación. (Con `-sI` en lugar de `-si`, `curl.exe` pide solo los encabezados y `Content-Length` no aparece: no es una falla.)
3. Puertos:

   ```
   5432, 8000, 8080, 2019, 80, 443 | ForEach-Object { "{0,5}  {1}" -f $_, (Test-NetConnection <dirección> -Port $_ -WarningAction SilentlyContinue).TcpTestSucceeded }
   ```

   Tiene que dar `False` en 5432, 8000, 8080 y 2019, y `True` solo en 80 y 443. Cada `False` tarda unos 20 segundos.

Para pedir la página cifrada con `curl.exe` hay que agregar `--ssl-no-revoke`: el `curl.exe` de Windows consulta la revocación del certificado y la autoridad propia no publica una lista de revocados. Los navegadores no la exigen.

### Desde B

1. En el navegador, `https://<dirección>`: no carga (se agota el tiempo o no se puede conectar). Ninguna página.
2. La misma línea de puertos: `False` en los seis, también en 80 y 443.

### La lista

1. Sacar A de `EVALUON_COMPUTERS` y repetir el paso 4: desde A ya no carga, y el puerto 443 da `False`.
2. Volver a ponerla y repetir el paso 4: desde A carga otra vez. No se tocó el código.

### En el equipo: la clave no viaja legible

En PowerShell **como administrador**, en la notebook, mientras alguien ingresa desde A con el usuario de prueba:

```
pktmon filter remove
pktmon filter add EVALUON-443 -t TCP -p 443
pktmon filter add EVALUON-80 -t TCP -p 80
pktmon start --capture --pkt-size 0 --file-name C:\EVALUON-red\captura.etl
```

Desde A: ingresar con el usuario de prueba y, como control, correr una vez `curl.exe -s http://<dirección>/ingresar/` (ese pedido va sin cifrar y tiene que verse en la captura). Después, en la notebook:

```
pktmon stop
pktmon etl2pcap C:\EVALUON-red\captura.etl --out C:\EVALUON-red\captura.pcapng
$texto = [Text.Encoding]::GetEncoding(28591).GetString([IO.File]::ReadAllBytes('C:\EVALUON-red\captura.pcapng'))
"control (GET /ingresar/ sin cifrar): " + ([regex]::Matches($texto, 'GET /ingresar/')).Count
$clave = Read-Host 'Clave del usuario de prueba'
"clave: " + ([regex]::Matches($texto, [regex]::Escape($clave))).Count + ", clave codificada: " + ([regex]::Matches($texto, [regex]::Escape([uri]::EscapeDataString($clave)))).Count
Remove-Item C:\EVALUON-red\captura.*; pktmon filter remove
```

El control tiene que dar 1 o más (la captura funciona y la búsqueda encuentra lo que va sin cifrar), y la clave, **0 y 0**. La captura no ve el tramo de Caddy a la aplicación: va por `127.0.0.1`, dentro de la notebook, y el filtro es solo de 80 y 443.

## Si algo no anda

**No correr `caddy.exe` a mano** (por ejemplo `caddy.exe run`) sin leer el punto «El servicio no arranca»: Windows le crea reglas de firewall propias que pueden dejar afuera a todas las computadoras sin ningún mensaje.

- **Ninguna computadora de la lista llega, y antes llegaban.** Mirar primero si hay reglas del firewall para `caddy.exe` además de «EVALUON», en PowerShell (alcanza sin administrador):

  ```
  Get-NetFirewallApplicationFilter | Where-Object Program -like '*\EVALUON-red\caddy.exe' | Get-NetFirewallRule | Select-Object DisplayName, Direction, Action, Enabled
  ```

  Tiene que aparecer solo «EVALUON», con `Allow`. Una regla con `Block` gana sobre la «EVALUON» y deja afuera a todos: la quita volver a correr el paso 4, que lo avisa («Se quitó la regla…»). Para quitar a mano todas las que no son «EVALUON» (también una `Allow` que abre `caddy.exe` a cualquier computadora), como administrador:

  ```
  Get-NetFirewallApplicationFilter | Where-Object Program -like '*\EVALUON-red\caddy.exe' | Get-NetFirewallRule | Where-Object DisplayName -ne 'EVALUON' | Remove-NetFirewallRule
  ```
- **El navegador advierte que la conexión no es segura.** La raíz no está en *Entidades de certificación raíz de confianza* de *Equipo local* (paso 5), el navegador no se reabrió, o en la barra no está exactamente la dirección de `EVALUON_ADDRESS` (por ejemplo, se entró por IP y el certificado es para el nombre).
- **«Bad Request (400)».** La dirección no está en `DJANGO_ALLOWED_HOSTS`, o no se recreó la aplicación después de agregarla (paso 2).
- **«502».** Docker o la aplicación no están levantados: abrir Docker Desktop y esperar a que `app` quede `healthy`.
- **Desde una computadora de la lista no carga.** Su IP cambió (verla con `ipconfig` en esa computadora y corregir el `.env`), no se corrió el paso 4 después de agregarla, o la red o el proxy del organismo la desvían (pedidos 1 y 4 al área de sistemas).
- **El servicio no arranca.** En este orden:
  1. ¿Otro programa usa el puerto 80 o 443? `Get-NetTCPConnection -State Listen -LocalPort 80, 443 | Select-Object LocalPort, OwningProcess` y `Get-Process -Id <número>`.
  2. ¿Caddy acepta la configuración y el certificado? `& C:\EVALUON-red\caddy.exe validate --config C:\EVALUON-red\Caddyfile --adapter caddyfile`. No abre puertos ni dispara el aviso del firewall; tiene que terminar con «Valid configuration».
  3. Solo si con eso no aparece el motivo: correrlo a mano, como administrador: `Stop-Service EVALUON-Caddy`, `& C:\EVALUON-red\caddy.exe run --config C:\EVALUON-red\Caddyfile` (Ctrl+C para cortar) y `Start-Service EVALUON-Caddy`. **Al correrlo así, Windows muestra un aviso del firewall para `caddy.exe`.** Elija lo que elija, crea reglas propias: con «Cancelar», reglas `Block` que dejan afuera a todas las computadoras; con «Permitir», reglas `Allow` desde cualquier computadora de la red. Después de la prueba, volver a correr el paso 4 (quita las `Block` y lo avisa) y revisar con el primer punto de esta lista que quede solo «EVALUON».
- HTTP/3 (UDP 443) queda cerrado por el firewall a propósito: el navegador usa TCP y no se nota.

## Deshacer

En PowerShell como administrador:

```
Stop-Service EVALUON-Caddy
sc.exe delete EVALUON-Caddy
Remove-NetFirewallRule -DisplayName EVALUON
```

Después, borrar `C:\EVALUON-red\` y, en cada computadora, `certutil -delstore Root "EVALUON autoridad propia"`. La aplicación sigue igual, solo en el equipo; las tres variables del `.env` se pueden dejar o borrar.

## Comprobaciones de T-269 sin el responsable (2026-10-14)

Hechas por el desarrollador en el equipo, sin administrador, sin tocar el firewall, los servicios ni la red, y con direcciones de documentación o de `127.0.0.1`:

- **Caddy 2.11.7.** El zip `caddy_2.11.7_windows_amd64.zip` bajado de la publicación de GitHub coincide con la suma SHA-512 de `caddy_2.11.7_checksums.txt` (la línea copiada en `scripts/red/caddy.sha512`); la SHA-256 de los dos archivos coincide con la que informa la API de GitHub. Se usó desde una carpeta temporal, sin instalarlo.
- **`caddy adapt --validate`** acepta el `Caddyfile` que arma `caddy.py` en las dos formas (por IP, con `default_sni`, y por nombre), con los certificados de `crear-certificados.sh`, sin avisos; `caddy fmt` no tiene nada que corregir. En la configuración resultante la API de administración está apagada, no hay certificados ni redirecciones automáticas, y la conexión sin nombre (entrar por IP) recibe el certificado.
- **Prueba en `127.0.0.1`** con puertos altos y un servidor de prueba en lugar de la aplicación: `http` da `308` a `https` con `Content-Length: 0`; por `https`, con la raíz de prueba, el servidor recibe `X-Evaluon-Computer: equipo-del-sistema` (o el nombre de la lista para `127.0.0.2`), `X-Forwarded-For` con la dirección real y `X-Forwarded-Proto: https`, aunque el cliente mande otros valores; desde una dirección fuera de la lista (`127.0.0.3`) la conexión se corta sin respuesta, por `http` y por `https`; sin la raíz, el certificado no es de confianza; el puerto 2019 no atiende. Se comprobó con el `curl` de Windows (Schannel, que valida como Windows) y con `openssl s_client`.
- **`crear-certificados.sh`.** La autoridad tiene `CA:TRUE` con `pathlen:0`, uso solo de servidor y las restricciones de nombre críticas; `openssl verify` rechaza un certificado firmado por ella para otra IP o para otro nombre, y uno de uso cliente. Volver a correrlo conserva la autoridad y cambia la clave del servidor; con una dirección que la autoridad no cubre, termina con error y deja el certificado anterior. El certificado del servidor no lleva CN: Windows controla el CN contra las restricciones de nombre y lo rechazaba (Schannel, error `0x4000`); sin CN, lo acepta.
- **`aplicar-red.ps1`** no se corrió (necesita administrador). Windows PowerShell 5.1 lo lee sin errores de sintaxis y con los acentos bien (UTF-8 con BOM). Se probaron aparte, sin administrador, la lectura de `caddy.sha512` y la comprobación de la suma (acepta el zip bueno y rechaza otro archivo), la lectura del JSON de `caddy.py` (también con la lista vacía) y `caddy validate`. La búsqueda de reglas `Block` para su `caddy.exe` se probó en modo lectura, sin quitar nada: encontró las dos que Windows había creado para un `caddy.exe` de prueba (Windows guarda la ruta en minúsculas; la comparación no distingue mayúsculas) y ninguna para `C:\EVALUON-red\caddy.exe`.
- Las claves y certificados de estas pruebas se crearon en una carpeta temporal y se borraron.
