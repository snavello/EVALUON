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
