# Entorno 012 · Conexión al Portal de Compras

Insumo del runbook de despliegue (plan 012, "Red y conexión"; ADR-0029 y ADR-0031). Lo
escribe T-138; el runbook lo incorpora al desplegar.

## Qué sale a internet y qué no

EVALUON no depende de internet para revisar pliegos ni evaluar ofertas (P4). La única
excepción es leer el Portal de Compras, y la hace **un solo servicio**:

| Servicio | Redes | Salida a internet |
|---|---|---|
| `portal_worker` | `internal` y `egress` | Sí, solo para leer el Portal (ver "Destinos") |
| `worker` (lee pliegos y ofertas, usa IA) | `internal` | No (red sin salida y sin cliente que salga) |
| `app` | `internal` y `web` (bridge común, solo para publicar el puerto en 127.0.0.1) | La red lo permitiría, pero `app` no tiene ningún cliente que salga a internet |
| `db`, `migrate`, `generation`, `generation_batch`, `embeddings`, `reranker` | `internal` | No |

- `internal` es una red de Docker con `internal: true`: sin salida. El aislamiento total de red
  aplica a `worker`, la base y los servicios de IA. `app` está además en `web`, un bridge con
  salida, porque una red `internal: true` no permite publicar el puerto de la pantalla; su
  garantía es otra: en `evaluon/`, fuera de `portal/`, no hay código que abra conexiones
  salientes a internet (lo comprueba `tests/portal/test_no_outbound.py`). Solo `portal_worker`
  tiene un cliente que sale, con la lista de destinos.
- `egress` es una red de Docker común (con salida). La usa solo `portal_worker`, que además
  está en `internal` para llegar a la base.
- `portal_worker` es la misma imagen que `app` y `worker`; corre `manage.py procesar_portal`,
  que atiende solo los pedidos `portal_explore` y `portal_review`. No usa IA ni la GPU y no
  publica puertos. El `worker` ignora esos pedidos y `portal_worker` ignora los demás.

## Destinos permitidos

Docker no filtra por dominio dentro de una red: a nivel de red, `portal_worker` podría salir
a cualquier destino. El filtro está en el código (`evaluon/portal/client.py`) y se aplica
**antes de conectar**, en cada solicitud y en cada redirección (que no se sigue sola):

- solo HTTPS y solo el puerto 443;
- solo los hosts de `PORTAL_ALLOWED_HOSTS` (lista separada por comas; por omisión,
  `afipcompras.afip.gob.ar`); no se aceptan direcciones con usuario ni clave;
- tope de tamaño por respuesta (`PORTAL_MAX_BYTES`, 50 MiB), de espera por solicitud
  (`PORTAL_TIMEOUT_SECONDS`, 30 s) y pausa entre solicitudes (`PORTAL_PAUSE_SECONDS`, 2 s);
- solo lee: GET y el envío de formularios de ASP.NET para pedir documentos; no escribe en
  el Portal.

El enlace que registra una persona se valida con la misma lista. Cambiar la lista es una
decisión de despliegue: se hace en `.env` y se reinicia `portal_worker`.

Variables (en `.env`, todas opcionales; valores por omisión en `evaluon/settings.py` y en
`docker-compose.yml`, que un test mantiene iguales): `PORTAL_ALLOWED_HOSTS`,
`PORTAL_TIMEOUT_SECONDS`, `PORTAL_MAX_BYTES`, `PORTAL_PAUSE_SECONDS`, `PORTAL_REVIEW_HOUR`.

## Cómo comprobarlo

1. **Regla de red (sin red real).** `docker compose run --rm app pytest tests/portal/test_network.py`
   lee `docker-compose.yml` y comprueba que solo `portal_worker` usa `egress`, que
   `internal` sigue siendo interna y que `worker`, la base y la IA están solo en ella; `app` está en `internal` y `web`. Que `app` no tiene cliente saliente lo comprueba `tests/portal/test_no_outbound.py`.
2. **Lista de destinos (sin red real).** `tests/portal/test_client.py` comprueba, con un
   transporte de mentira, que un host fuera de la lista, HTTP, otro puerto, una dirección
   con usuario y una redirección a otro host se rechazan antes de conectar.
3. **En el equipo desplegado.** Con los servicios arriba:
   - `docker compose exec portal_worker python -c "import socket; socket.create_connection(('afipcompras.afip.gob.ar', 443), 5)"`
     conecta (confirma la salida de `portal_worker`);
   - el mismo comando con `worker` en lugar de `portal_worker` falla por no resolver el
     nombre (confirma que el `worker` no tiene salida);
   - `docker network inspect evaluon_egress` lista solo a `portal_worker`.

## Cómo cortar la conexión

```
docker compose stop portal_worker
```

El resto sigue igual: la aplicación, el `worker` y la IA no cambian, y la carga manual de
pliegos y ofertas está disponible (REQ-051). Los pedidos del Portal quedan en espera y se
atienden al volver a levantarlo (`docker compose start portal_worker`); los que estaban en
curso pasan a fallidos "interrumpido" al arrancar. Para quitar la salida de forma
definitiva, sacar `portal_worker` y la red `egress` de `docker-compose.yml`.

## Paso siguiente posible

Un proxy de salida con filtro por dominio (ADR-0031, alternativa B) pasaría el filtro del
código a la red. No está hecho; el cliente no cambiaría.

## Pruebas de esta tarea

Ningún test se conecta al Portal real ni a internet: usan un transporte de mentira con
contenido inventado, y un test falla si el cliente intenta abrir una conexión real.

## Pasos para el runbook del despliegue (T-145)

Orden para dejar la lectura del Portal funcionando en un equipo nuevo. Cada paso dice cómo
saber que salió bien.

1. **Variables en `.env`** (todas opcionales; sin ellas rigen los valores por omisión de
   `.env.example`): `PORTAL_ALLOWED_HOSTS` (hosts separados por comas; por omisión
   `afipcompras.afip.gob.ar`), `PORTAL_TIMEOUT_SECONDS` (30), `PORTAL_MAX_BYTES` (52428800),
   `PORTAL_PAUSE_SECONDS` (2), `PORTAL_REVIEW_HOUR` (7, hora de Buenos Aires),
   `PORTAL_USER_AGENT`. No hay claves ni cuentas del Portal: la lectura es pública. Cambiar la
   lista de hosts es una decisión de despliegue y requiere reiniciar `portal_worker`.
2. **Red.** `docker compose up -d` crea `internal` (sin salida), `web` y `egress` (con salida).
   Solo `portal_worker` está en `egress`. Comprobar: `docker network inspect <proyecto>_egress`
   lista únicamente a `portal_worker`, y `docker compose run --rm app pytest
   tests/portal/test_network.py tests/portal/test_no_outbound.py` pasa. El equipo necesita
   salida HTTPS (443) hacia los hosts de la lista y resolución de nombres; ningún otro puerto ni
   destino.
3. **Servicio.** `docker compose up -d portal_worker` (depende de la base y de la migración).
   Comprobar: `docker compose logs portal_worker` dice «Esperando pedidos del Portal.» y el
   servicio sigue `running`. No usa GPU ni IA: levantarlo no cambia los recursos de la IA.
4. **Salida real, solo desde `portal_worker`.** `docker compose exec portal_worker python -c
   "import socket; socket.create_connection(('afipcompras.afip.gob.ar', 443), 5)"` conecta;
   el mismo comando con `worker` en lugar de `portal_worker` falla (no tiene salida).
5. **Extremo a extremo.** Un operador pega el enlace de un proceso público en la pantalla
   «Importar del Portal»; en segundos aparece la propuesta o el motivo. La revisión diaria
   (lunes a viernes, desde `PORTAL_REVIEW_HOUR`) la encola `portal_worker` solo.
6. **Medición sin conexión (aceptación).** Con las páginas guardadas en `corpus/casos/` (fuera
   del repositorio): `docker compose run --rm --no-deps -v <corpus/casos>:/casos:ro -v
   <carpeta de corridas>:/corridas app python manage.py medir_portal --usuario <evaluador>
   --caso /casos/caso-00 --caso /casos/caso-05 --corridas /corridas --commit <commit>`. No usa
   la red (se puede correr con la red cortada) y deja la base como estaba.
7. **Pasada en vivo (una sola vez, con el Coordinador).** El mismo comando con `portal_worker`
   en lugar de `app` y la opción `--en-vivo`; es el único que sale a internet. Ver
   `verificacion/T-145.md`.

**Cómo cortar la conexión** (en cualquier momento): `docker compose stop portal_worker`. Todo lo
demás sigue funcionando y la carga manual no se ve afectada (REQ-051). Volver a levantarlo:
`docker compose start portal_worker`; los pedidos en espera se atienden y los que estaban en
curso quedan fallidos «interrumpido». Para quitar la salida de forma definitiva: sacar
`portal_worker` y la red `egress` de `docker-compose.yml`.

**Qué mirar si algo falla:** un enlace rechazado muestra su motivo en pantalla; un pedido fallido
deja el motivo en la lista de enlaces y el hecho `portal_explore` o `portal_review` con
`reason`; un host fuera de la lista se rechaza antes de conectar (`DestinationNotAllowed`).
