# Runbook 012 · Importación asistida desde el Portal de Compras

Para llegar al sistema funcionando desde un equipo limpio y operar la lectura del Portal (P5). Red y destinos: `specs/012-portal-compras/entorno.md`. Para las demás features rigen los runbooks de `specs/003-pliego-matriz/runbook.md` y `specs/008-ofertas-ficha/runbook.md`. Los comandos se corren desde la raíz del repositorio (Git Bash o PowerShell); `docker compose` usa el proyecto `evaluon`, y para pruebas se agrega `-p nombre`. En Git Bash, anteponer `MSYS_NO_PATHCONV=1` a los comandos con rutas que empiezan con `/`.

## 1. Levantar desde cero

1. Requisitos: Docker Desktop con WSL2, GPU NVIDIA (ver `specs/001-normativa/entorno.md`) y Git. Para leer el Portal, salida HTTPS (443) y resolución de nombres hacia los hosts de `PORTAL_ALLOWED_HOSTS`; ningún otro puerto ni destino.
2. Clonar el repositorio. Modelos (único otro paso con internet): `bash scripts/fetch_models.sh`.
3. `cp .env.example .env` y completar `POSTGRES_PASSWORD` y `DJANGO_SECRET_KEY` (valores propios, largos y al azar: `openssl rand -hex 32`). `.env` no se sube. No hay claves ni cuentas del Portal: la lectura es pública.
4. `docker compose build app` y `docker compose up -d`. Con la base vacía, `migrate` aplica todo; después arrancan `app`, `worker` y `portal_worker` (este depende solo de la base y de `migrate`; no usa GPU ni IA).
5. Comprobar:
   - `docker compose ps`: `app` y la IA "healthy"; `worker` y `portal_worker` "Up" (sin estado de salud); `migrate` termina solo.
   - `docker compose logs portal_worker` dice «Esperando pedidos del Portal.».
   - `docker network inspect evaluon_egress --format '{{range .Containers}}{{.Name}} {{end}}'` lista solo a `portal_worker`.
   - `docker compose run --rm app pytest tests/portal/test_network.py tests/portal/test_no_outbound.py` pasa (sin red real).
6. Usuario de la Comisión (clave pedida dos veces): `docker compose run --rm app python manage.py crear_usuario NOMBRE --rol lectura-escritura --rol-comision operador` (el rol `evaluador` incluye al de operador).
7. Pantalla: `http://127.0.0.1:8000/` (o `APP_PORT`); la importación está en `/importar/` («Importar desde el Portal»).

Salida de `portal_worker` (opcional; toca el Portal real): `docker compose exec portal_worker python -c "import socket; socket.create_connection(('afipcompras.afip.gob.ar', 443), 5)"` conecta. El mismo comando con `worker` falla por no resolver el nombre. `app` está además en la red `web` (solo para publicar el puerto), pero no tiene ningún cliente que salga a internet (lo comprueba `tests/portal/test_no_outbound.py`).

Parar: `docker compose stop`. Los datos viven en el volumen `pgdata`: no usar `down -v` salvo en un proyecto de pruebas, porque borra la base.

## 2. Variables `PORTAL_*`

Todas opcionales, en `.env` (valores por omisión en `.env.example`, `docker-compose.yml` y `evaluon/settings.py`; un test los mantiene iguales). Cambiar una requiere `docker compose up -d` para recrear los servicios. Cambiar la lista de hosts es una decisión de despliegue.

| Variable | Omisión | Qué hace |
|---|---|---|
| `PORTAL_ALLOWED_HOSTS` | `afipcompras.afip.gob.ar` | Hosts permitidos, separados por comas. Valida los enlaces que se registran y cada solicitud y redirección del cliente (solo HTTPS, puerto 443) |
| `PORTAL_TIMEOUT_SECONDS` | 30 | Espera máxima por solicitud |
| `PORTAL_MAX_BYTES` | 52428800 | Tamaño máximo por respuesta (50 MiB) |
| `PORTAL_PAUSE_SECONDS` | 2 | Pausa entre solicitudes |
| `PORTAL_REVIEW_HOUR` | 7 | Hora (Buenos Aires) desde la que corre la revisión diaria, lunes a viernes |
| `PORTAL_USER_AGENT` | `EVALUON/1.0 (lectura de procesos publicos)` | Identificación ante el Portal |

## 3. Migraciones sobre una base existente (con respaldo previo)

Con datos en la base, `migrate` no migra solo: comprueba y, si hay pendientes, falla y `app` no arranca. Es lo esperado. Esta feature trae `audit.0006`, `tenders.0006` y `portal.0001` a `0003` (las migraciones de features posteriores van en el mismo `migrate`).

1. Que no haya medición ni pedido en curso (pantalla sin pedidos "en curso"; `docker top evaluon-app-1 | grep medir` vacío).
2. `docker compose stop app worker portal_worker`.
3. Respaldo (`backups/` está ignorada por git; si no existe, `mkdir backups`):
   `docker compose exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > backups/evaluon-AAAA-MM-DD-previo-012.dump`
   Comprobar con `ls -l backups` que no esté vacío. Contiene datos de casos: queda solo en el equipo.
4. Ver qué se aplicará: `docker compose run --rm --no-deps app python manage.py showmigrations audit tenders portal`.
5. Aplicar: `docker compose run --rm --no-deps app python manage.py migrate`.
6. Comprobar: `docker compose run --rm --no-deps app python manage.py migrate --check` (salida 0).
7. `docker compose up -d`.

## 4. Registrar un enlace, explorar, aprobar y cargar

Rol de operador. Todo en la pantalla `/importar/`.

1. **Registrar y explorar.** Pegar el enlace público del proceso en «Registrar un enlace» y pulsar «Explorar». Un enlace de un host fuera de la lista se rechaza en pantalla, con su motivo. La exploración queda como pedido `portal_explore` para `portal_worker`; en segundos aparece la propuesta (datos del procedimiento, renglones, documentos, ofertas) o el motivo del fallo en la lista.
2. **Aprobar.** Abrir el proceso (columna «Proceso»). Elegir lo que se acepta y pulsar «Aprobar lo elegido» (o «Aprobar todo»; o rechazar). Nada se carga sin esa decisión (REQ-048). Una circular pide tipo y fecha si el Portal no los dice. Los campos con caracteres dañados vienen marcados (sección 9).
3. **Cargar.** Lo aprobado se carga: el procedimiento, sus renglones, los documentos (pliego, anexos y circulares van a la lectura del `worker`, como la carga manual) y las ofertas. Acta, dictamen y actos quedan como archivo del Portal, descargables desde la pantalla de lo importado, con su origen y su huella.
4. La carga manual de pliegos y ofertas sigue disponible siempre (REQ-051).

## 5. Revisión diaria y «Revisar ahora»

- Cada enlace con seguimiento activo se revisa solo, de lunes a viernes, desde `PORTAL_REVIEW_HOUR` (hora de Buenos Aires), por `portal_worker` (pedido `portal_review`). Propone solo lo nuevo o cambiado; lo ya decidido no se repite.
- «Revisar ahora» (en la lista, por proceso) encola una revisión inmediata. «Dejar de seguir» saca el proceso de la revisión diaria; lo ya cargado no cambia.
- La columna «Novedades por decidir» cuenta lo propuesto sin resolver. Una revisión fallida muestra su motivo («La revisión falló: ...») y lo ya propuesto sigue disponible.

## 6. Medir con `medir_portal`

No usa GPU ni IA. Rol de evaluador; pide la clave por teclado. Las páginas guardadas están en `corpus/casos/` (fuera del repositorio, no se sube).

- **Sin conexión (aceptación):** no usa la red (se puede correr con la red cortada) y deja la base como estaba:
  `docker compose run --rm --no-deps -v <ruta-absoluta>/corpus/casos:/casos:ro -v <carpeta-de-corridas>:/corridas app python manage.py medir_portal --usuario NOMBRE --caso /casos/caso-00 --caso /casos/caso-05 --corridas /corridas --commit HASH`
  (`--commit` hace falta: el contenedor no tiene `.git`). Informa 8 medidas por caso y «Bloquea la aceptación: nada» cuando todas están en 100 %. La corrida queda en la carpeta indicada.
- **En vivo:** solo con el Coordinador presente y una sola vez: el mismo comando con `portal_worker` en lugar de `app` y la opción `--en-vivo`. Es el único que sale a internet y compara lo que sirve el Portal ahora. No repetirlo sin necesidad.

## 7. Cortar la conexión al Portal

```
docker compose stop portal_worker
```

Sin `portal_worker`, nada sale a internet. La aplicación, el `worker` y la IA siguen igual y la carga manual funciona. Los pedidos del Portal quedan en espera; al volver (`docker compose start portal_worker`) se atienden, y los que estaban en curso pasan a fallidos «interrumpido» (se vuelven a pedir desde la pantalla). Para quitar la salida de forma definitiva: sacar `portal_worker` y la red `egress` de `docker-compose.yml`. Comprobar el corte: `docker compose ps` no lista `portal_worker` en ejecución.

## 8. Volver atrás

1. **Dejar de usar la importación, conservando los datos:** cortar la conexión (sección 7). Las tablas del Portal quedan sin uso; lo cargado sigue siendo parte de los procedimientos y ofertas.
2. **Volver el código a la versión anterior:** `git checkout` del commit previo, `docker compose build app`, `docker compose up -d`. Si no arranca por las migraciones ya aplicadas, usar la 3 o la 4.
3. **Deshacer solo las migraciones.** Borra las tablas del Portal con su contenido (enlaces, propuestas, archivos bajados). Con respaldo hecho y confirmación:
   `docker compose run --rm --no-deps app python manage.py migrate portal zero`, luego `migrate tenders 0005` y `migrate audit 0005`.
   Atención: `tenders 0005` y `audit 0005` también deshacen las migraciones posteriores que dependen de ellas (`tenders.0007`, `audit.0007` y `assessment.0001` y `0002`, de la feature 004): se pierde lo que hayan guardado. Para volver a avanzar: `migrate`.
4. **Restaurar el respaldo.** Se pierde todo lo hecho desde él. Pedir confirmación: `dropdb` borra la base vigente.
   ```
   docker compose stop app worker portal_worker
   docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --force "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
   docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --exit-on-error' < backups/evaluon-AAAA-MM-DD-previo-012.dump
   docker compose up -d
   ```

## 9. Problemas conocidos

- **La búsqueda del Portal pide CAPTCHA.** El sistema no busca procesos: lee el enlace directo de un proceso que una persona pega (no resuelve ni evita el CAPTCHA). Qué hacer: encontrar el proceso en el Portal a mano y pegar su enlace.
- **El Pliego de Bases y Condiciones Generales da error en el Portal** (una pantalla de error en lugar del PDF). No frena la importación: queda como anomalía en la propuesta y el resto se importa. Qué hacer: cargar ese pliego a mano (REQ-051).
- **Acentos rotos (`¿`, `�`, `è`).** Si el daño ya viene en los datos del Portal, se guarda tal cual (no se adivinan letras, P3) y el campo queda marcado como dañado en la propuesta. «Igual al Portal» incluye esos caracteres. Qué hacer: revisar el original y corregir a mano al aprobar si corresponde.
- **Enlace rechazado:** host fuera de `PORTAL_ALLOWED_HOSTS`, HTTP, otro puerto o dirección con usuario. El motivo se ve en pantalla.
- **Pedido fallido:** el motivo queda en la lista de enlaces y en el hecho `portal_explore` o `portal_review` (`reason`). Un host fuera de la lista se rechaza antes de conectar (`DestinationNotAllowed`).
- **Pedido que no avanza:** `docker compose ps portal_worker` y `docker compose logs portal_worker`; si está detenido, `docker compose start portal_worker`.
- **`migrate` falla al arrancar con "hay migraciones pendientes":** es lo esperado con datos en la base; seguir la sección 3.
- **`app` no arranca con "port is already allocated":** otro proyecto usa el puerto; cambiar `APP_PORT` en `.env` (en pruebas con un proyecto aparte, siempre).
- **Las páginas HTML del Portal cambian de huella en cada visita:** se comparan por identidad; los PDF, por huella.

## 10. Prueba del runbook (2026-10-06)

Proyecto `evaluon-dep012` (imagen `evaluon-app:dep012`, con un archivo de compose adicional fuera del repositorio que solo cambia la etiqueta de la imagen para no pisar la del proyecto principal; puerto 18012; claves propias; base propia). No se levantaron los motores de IA (esta feature no los usa; `app` se levantó con `--no-deps`). No se tocó el proyecto `evaluon` ni su base. Al final, `down -v`.

Probado, con resultado correcto:

- construir, `db` sana, `migrate` en base vacía (incluidas `portal.0001` a `0003`), `portal_worker` arriba («Esperando pedidos del Portal.») y `app` sana;
- red: `evaluon-dep012_egress` lista solo a `portal_worker`;
- alta de usuario, respaldo `pg_dump` (343 KB), `migrate --check` en 0;
- `medir_portal` sin conexión, casos 00 y 05: 8 de 8 medidas en 100 % en cada caso, «Bloquea la aceptación: nada»;
- corte: con `portal_worker` detenido, `app` sigue respondiendo; al volver a arrancarlo, «Esperando pedidos del Portal.»;
- reversa de migraciones (`portal zero`, `tenders 0005`, `audit 0005`) y reaplicación con `migrate` (después, `--check` en 0).

No probado: registrar un enlace, explorar, aprobar y cargar por la pantalla, la revisión diaria y «Revisar ahora» (necesitan el Portal real); la restauración con `pg_restore` (probada en el runbook 008, mismo procedimiento); la pasada en vivo (la hizo el Coordinador el 2026-10-06, 100 % en ambos casos). Nota: la comprobación opcional de salida de la sección 1 abre una conexión TCP al Portal real; en esta prueba se hizo una vez desde `portal_worker`, solo el saludo de conexión, sin pedir contenido.
