# ADR-0018 · Pedidos largos en segundo plano y motor de generación para lotes

Estado: propuesto · Fecha: 2026-10-03 · Decidió: —

## Contexto

La feature 003 (`specs/003-pliego-matriz/spec.md`) pide dos cosas que la 001 no tenía:

- **Trabajos largos.** Proponer la matriz de un pliego de unas 50 páginas puede llevar hasta 15, 30 o 60 minutos según el nivel de revisión, y "mientras tanto se puede seguir trabajando, y el sistema avisa cuando termina". Leer un pliego escaneado con reconocimiento de texto también lleva minutos. La 001 resuelve todo dentro del pedido de la pantalla: Gunicorn espera 120 segundos y el plan 001 dice "No hay servidor web intermedio, cola de tareas ni caché (P10)".
- **Uso prolongado del motor de generación.** La propuesta de la matriz hace decenas de pedidos seguidos al modelo. El servicio `generation` de la 001 corre con `--parallel 1` (`docker-compose.yml`): atiende un pedido por vez. Una consulta de normativa que llega mientras corre la matriz espera a que termine el pedido en curso, y la spec 001 pide hasta 30 segundos por consulta.

Datos medidos en este equipo (`specs/001-normativa/entorno.md`, T-001 a T-003):

| Dato | Valor |
|---|---|
| Memoria de video total y libre con la pantalla en la placa integrada | 24.463 MiB; 24.137 MiB libres |
| `generation` (Gemma 4 12B, contexto 16.384) | 7.818 MiB |
| `embeddings` + `reranker` | 2.540 MiB |
| Los tres servicios de la 001 | 10.344 MiB |
| Velocidad de `generation` | unos 3.000 tokens por segundo al leer y unos 73 al escribir; 15,5 s para 12.000 de entrada y 800 de salida |

Restricciones: todo local y sin servicios externos en el camino del pliego (P4); un comando para levantar todo (P5); lo mínimo que pide la spec (P10).

Este ADR decide dos cosas: **cómo se ejecuta un trabajo largo** y **con qué motor lo hace**.

## Alternativas

### Parte 1 · Cómo se ejecuta un trabajo largo

#### A. Tabla de pedidos en Postgres y un servicio `worker` propio
Un pedido (leer un documento, proponer una matriz) es una fila en una tabla de la base con su estado (`queued`, `running`, `done`, `failed`). Un servicio nuevo de Docker, `worker`, con la misma imagen que `app`, corre el comando `procesar_pedidos`: toma el pedido más antiguo con `SELECT … FOR UPDATE SKIP LOCKED`, lo ejecuta y deja el resultado. Si no hay pedidos, espera unos segundos y vuelve a mirar.
- Se gana: ninguna librería ni servicio de terceros; los pedidos quedan en la base, con el respaldo de siempre; el estado se ve desde la pantalla leyendo una tabla; el pedido es auditable como cualquier otra fila.
- Se pierde: código propio para tomar pedidos, reintentar y marcar como fallido un pedido que quedó a medias si el servicio se cae. Es poco código, pero hay que probarlo.

#### B. El marco de tareas de Django con un backend de base de datos de terceros
Django 6 trae un marco de tareas (`django.tasks`), pero solo con backends de desarrollo y pruebas: "Django does not provide a worker mechanism to run Tasks" y "Production systems should rely on backends that supply a worker process and a durable queue implementation" [F1]. El backend de base de datos es un paquete aparte, `django-tasks-db` 0.13.0 (28 de agosto de 2026, BSD-3-Clause), con su comando `db_worker` [F3]; el paquete base `django-tasks` es la adaptación del marco a versiones anteriores [F2].
- Se gana: una interfaz estándar de Django; si el backend madura, se cambia sin tocar el código de las tareas.
- Se pierde: `django-tasks-db` figura como "4 - Beta" y declara soporte para Django 5.2 y 6.0, no para la 6.1.1 que usa el proyecto [F3]. Una pieza central en estado beta y fuera de la versión declarada.

#### C. Celery o RQ con Redis
- Se gana: la solución más conocida, con reintentos y monitoreo.
- Se pierde: dos servicios más (cola y Redis) que levantar, respaldar y mudar, para un volumen de unos pocos pedidos por día (P10).

#### D. Un hilo dentro del proceso de la pantalla
- Se gana: nada nuevo que levantar.
- Se pierde: el trabajo muere si Gunicorn reinicia el proceso; dos trabajos compiten dentro del mismo proceso que atiende la pantalla; no hay forma limpia de saber que un trabajo quedó a medias.

### Parte 2 · Con qué motor de generación

#### 1. El mismo servicio `generation` de la 001
- Se gana: no se suma memoria de video.
- Se pierde: con `--parallel 1`, una consulta de normativa espera al pedido de la matriz en curso. Si ese pedido escribe 1.500 tokens, son unos 20 segundos de espera más los 15 de la consulta: se pasa de los 30 segundos de la spec 001 mientras haya una matriz en preparación.

#### 2. Una segunda instancia, `generation_batch`, con la misma imagen y el mismo modelo
Mismo archivo de Gemma 4 12B, misma compilación fijada (`b11347`), mismo contexto, `--parallel 1`. La usan solo los pedidos del `worker`.
- Se gana: la consulta de normativa no queda en fila detrás de la matriz; el servicio `generation` de la 001 no cambia, así que sus mediciones y su umbral siguen valiendo (P7).
- Se pierde: unos 7,8 GB más de memoria de video. La cuenta con lo medido da 10.344 + 7.818 = 18.162 MiB de 24.137 libres, unos 6 GB de margen. Cuando las dos escriben a la vez se reparten la placa: la consulta puede tardar más que sola. Cuánto, no está medido.

#### 3. `--parallel 2` en el servicio `generation`
- Se gana: una sola instancia.
- Se pierde: cambia la configuración del servicio con el que se midió y calibró la 001 (P7 obliga a volver a correr el conjunto); la documentación de `llama-server` no aclara cómo se reparte el contexto entre las ranuras [F4], y con varios pedidos a la vez el resultado puede dejar de ser idéntico entre corridas. Es el cambio con más efectos sobre lo ya aprobado.

## Decisión

Se propone **A + 2**:

- Pedidos largos en una tabla de la base y un servicio `worker` con la misma imagen que `app`, que corre `procesar_pedidos`. Procesa un pedido por vez.
- Un servicio `generation_batch` con la misma imagen, compilación y modelo que `generation`, que usan solo los pedidos del `worker`. La aplicación lo conoce por la variable `GENERATION_BATCH_URL`; si se la deja apuntando a `generation`, se vuelve a la alternativa 1 sin tocar código.
- Si `embeddings` o `reranker` hacen falta dentro de un pedido (consecuencias y circulares, plan 003), se usan los servicios existentes: sus pedidos duran alrededor de un segundo.

Motivo principal: no tocar nada de lo que la 001 midió y aprobó, y no sumar dependencias en estado beta ni servicios que no hacen falta a este volumen.

### Cómo funciona

- **Estados.** `queued` → `running` → `done` o `failed`. Un pedido fallido guarda el motivo y lo que alcanzó a registrar; no se reintenta solo. La persona lo puede volver a pedir.
- **Caída a mitad de camino.** Al arrancar, `procesar_pedidos` pasa a `failed` los pedidos que quedaron en `running`, con el motivo "interrumpido". Nunca queda una matriz a medias marcada como lista.
- **Aviso al terminar.** La pantalla muestra, en cualquier página, un aviso con los pedidos de la persona que terminaron y todavía no vio. No hay actualización automática de la página (ADR-0005: sin htmx hasta que un requisito lo pida); el aviso aparece en la próxima página que abre.
- **Sin red.** `worker` y `generation_batch` están en la misma red interna sin salida a internet; `generation_batch` arranca con `--offline` (P4).
- **Un comando para levantar todo.** Los dos servicios entran en `docker-compose.yml` (P5).

## Consecuencias

**Más fácil**
- Un trabajo de una hora no depende de la pantalla ni del navegador.
- La 008 (ofertas escaneadas) y la 004 (evaluación de varias ofertas) pueden usar el mismo `worker`.
- La 001 queda como está.

**Más difícil**
- Dos servicios más. La memoria de video pasa de unos 10 a unos 18 GB, con unos 6 GB de margen.
- Si se usa la placa dedicada para la pantalla o se conecta un monitor a ella, Windows ocupa memoria de video (entorno.md, T-001) y el margen baja: hay que volver a medir.
- Mientras la matriz escribe, una consulta de normativa comparte la placa. Se mide en la corrida de la 003 (plan 003, T-084): consulta sola y consulta durante una matriz.

**Para revertir**
- Parte 2: apuntar `GENERATION_BATCH_URL` a `generation` y quitar el servicio. Sin cambios de código ni de datos.
- Parte 1: reemplazar `procesar_pedidos` por el `db_worker` de un backend de `django.tasks` cuando haya uno estable para la versión de Django en uso. La tabla de pedidos y su historia quedan como registro.

## Sin verificar

- Cuánto tarda una consulta de normativa mientras `generation_batch` escribe. Se mide en T-084.
- Memoria de video real con los cuatro modelos cargados. La cifra de 18.162 MiB suma mediciones separadas. Se mide en T-071.
- Cómo reparte `llama-server` el contexto con `--parallel` mayor que 1 [F4]: no se usa, pero sería el dato para revisar la alternativa 3.

## Fuentes

Consultadas el 2026-10-03.

- [F1] Documentación de Django 6.1, marco de tareas: https://docs.djangoproject.com/en/6.1/topics/tasks/
- [F2] `django-tasks` en PyPI (0.12.0, 6 de febrero de 2026): https://pypi.org/project/django-tasks/
- [F3] `django-tasks-db` en PyPI (0.13.0, 28 de agosto de 2026; "4 - Beta"; Django 5.2 y 6.0): https://pypi.org/project/django-tasks-db/
- [F4] Documentación del servidor de llama.cpp (`--parallel`, `--kv-unified-per-slot`, procesamiento continuo): https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- Fuentes secundarias sobre el marco de tareas de Django 6: https://realpython.com/django-tasks/ y https://lincolnloop.com/blog/django-6-tasks-background-processing-without-the-infrastructure/
- Mediciones del equipo: `specs/001-normativa/entorno.md`, T-001 a T-003.
