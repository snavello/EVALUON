# ADR-0031 · Conexión acotada al Portal: un servicio aparte con salida a internet y una lista de destinos permitidos

Estado: aceptado · Fecha: 2026-10-05 · Decidió: responsable del proyecto

## Contexto

El ADR-0029 permite que EVALUON se conecte a internet solo para leer el Portal de Compras. Hoy todos los servicios están en la red `internal` de Docker (`internal: true`, sin salida) y los pliegos y ofertas se procesan en `worker`. La constitución (P4) exige que el camino de pliegos y ofertas no dependa de un servicio externo, y el ADR-0029 pide que la conexión se limite a ese destino y se documente en el runbook.

Restricciones: Docker no filtra por dominio en una red; una red con salida deja salir a cualquier destino. El `worker` actual lee pliegos y ofertas y usa la GPU; no debería tener salida. La exploración es corta (pocas páginas, unos segundos) y no usa IA.

## Alternativas

### A. Servicio `portal_worker` aparte, con la red `egress`, y lista de destinos en la aplicación (elegida)

Una segunda instancia de la misma imagen que corre `manage.py procesar_portal`: atiende solo los pedidos del Portal y la revisión periódica (ADR-0033). Es el único servicio en la red nueva `egress` (con salida) además de `internal` (para llegar a la base). `worker`, la base y los servicios de IA siguen sin salida de red; `app` está en `web` (bridge con salida, necesario para publicar el puerto) pero no tiene ningún cliente que salga a internet, lo que comprueba un test sobre los imports de `evaluon/`. El código del cliente del Portal solo conecta a los destinos de `PORTAL_ALLOWED_HOSTS` (configuración, por entorno): HTTPS, puerto 443, y los controla en cada solicitud y en cada redirección (no se siguen solos).

- Se gana: el proceso que lee pliegos y ofertas nunca tiene salida (P4 se cumple por construcción de red); una sola imagen y sin software nuevo; la lista y el aislamiento se prueban (un test lee `docker-compose.yml` y comprueba que solo `portal_worker` está en `egress`).
- Se pierde: a nivel de red, `portal_worker` podría salir a cualquier destino si el código se modificara; el filtro por destino es del código, no de la red. Hay un servicio más que levantar y vigilar.

### B. Proxy de salida con filtro por dominio

Un servicio proxy (por ejemplo, un proxy HTTP con lista de dominios permitidos) en `internal` y `egress`; el `worker` o `portal_worker` lo usa y no tiene salida propia.

- Se gana: el filtro es de red y no depende de nuestro código.
- Se pierde: una imagen y un software nuevos que mantener, fijar y documentar; configuración de dominios en un segundo lugar; más piezas para una sola dirección de destino (contra P10). Puede sumarse después sin cambiar el código del cliente (el cliente ya respeta una variable de proxy).

### C. Dar salida al `worker` existente, con la lista de destinos en el código

- Se gana: ningún servicio nuevo.
- Se pierde: el servicio que procesa pliegos y ofertas queda con salida a internet: el riesgo que el ADR-0029 quiere evitar y la base de P4. Además un pedido del Portal competiría con las lecturas y la GPU en una sola cola.

## Decisión

Se adopta **A**. Detalle:

1. `docker-compose.yml`: red nueva `egress` (sin `internal`); servicio `portal_worker` (`<<: *app`, `command: python manage.py procesar_portal`, redes `internal` y `egress`, `depends_on` base y `migrate`; sin dependencia de los servicios de IA ni de la GPU).
2. Configuración: `PORTAL_ALLOWED_HOSTS` (lista; por omisión, el host del Portal), `PORTAL_TIMEOUT_SECONDS`, `PORTAL_MAX_BYTES` por respuesta, `PORTAL_PAUSE_SECONDS` entre solicitudes. El enlace que se registra se rechaza, con explicación, si su host no está en la lista o no es HTTPS.
3. Cola compartida (ADR-0018): `procesar_pedidos` (el `worker`) ignora los pedidos del Portal y `procesar_portal` ignora todos los demás; al arrancar, cada uno pasa a fallidos solo los suyos en curso. Para eso `claim`, `run_next` y `fail_interrupted` reciben qué tipos atender.
4. Documentación: `specs/012-portal-compras/entorno.md` (T-138) describe la red, la lista de destinos, cómo comprobarla y cómo cortar la conexión (`docker compose stop portal_worker`); el runbook del despliegue la incorpora. Con el servicio apagado, todo lo demás funciona y la carga manual sigue disponible (REQ-051).

## Consecuencias

- Más fácil: demostrar que pliegos y ofertas no pasan por un servicio con salida; apagar la conexión con un comando.
- Más difícil: dos consumidores de la misma cola, con filtro por tipo (hay que probar que no se pisan).
- Para revertir: quitar `portal_worker` y la red `egress`; la aplicación sigue con carga manual. Si más adelante se quiere filtro de red, se agrega el proxy de la alternativa B sin tocar el cliente.
