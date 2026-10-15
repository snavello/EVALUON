# Entorno de la 016 · Instancia clonada

Estado: preparado por T-270 (2026-10-15). El clon se levanta con `scripts/clon.sh`; la ventana de GPU (abrir y cerrar) la ejecuta el Coordinador, de noche o en fin de semana, con la cola de 8000 vacía. Decidido por el responsable en la spec (2026-10-14); el plan lo describe en «Instancia clonada y ritmo de trabajo». REQ-125.

Es un segundo entorno de EVALUON con **su propia base**, restaurada de un respaldo nuevo de la de trabajo, y **su propio motor** del Qwen3.8-27B, para medir cada paso de la 016 sin tocar la instancia del piloto (puerto 8000). No lee ni escribe la base de 8000 (solo la respalda) y no toca ningún contenedor ni volumen `evaluon-*` fuera de la ventana de GPU.

## Archivos

| Archivo | Para qué |
|---|---|
| `docker-compose.clon.yml` | Proyecto `evaluon-016`: `clon_db` (volumen `clon_pgdata`), `clon_migrate`, `clon_app` (puerto 8016 solo en `127.0.0.1`), `clon_worker` y `clon_generation_batch` (perfil `motor`: solo lo arranca la ventana) |
| `scripts/clon.sh` | `subir`, `restaurar`, `ventana-abrir`, `ventana-cerrar`, `bajar`, `estado` y `ejecutar` |
| `tools/cerrar.sh` | Variable `BASE`: la rama en la que se integra (por omisión `main`) |
| `.env.example` | Líneas comentadas con las variables del clon |
| `tests/test_clon_compose.py` | Forma del compose, ventana contra un `docker` de mentira, `BASE`, `.env.example` y este documento |

## Qué comparte con 8000 y qué no

| | Clon (`evaluon-016`) | 8000 (`evaluon`) |
|---|---|---|
| Base | `clon_db`, volumen `evaluon-016_clon_pgdata`, base `evaluon_clon` | `db`, volumen `evaluon_pgdata` |
| Aplicación | `clon_app` en `127.0.0.1:8016`, `clon_worker` | `app` en 8000, `worker`, `portal_worker` |
| Motor del 27B | `clon_generation_batch`, solo en las ventanas | `generation_batch`, siempre |
| `embeddings` y `reranker` | **los de 8000**, por la red `evaluon_internal`, en lectura | los suyos |
| Código | `CLON_CODE_DIR` (la copia de trabajo de `016-integracion`, o una copia fija), en solo lectura | `./evaluon` de la carpeta raíz, en `main` |
| Casos | `CLON_CASOS_DIR` (carpeta propia, con escritura) | `corpus/casos` de la raíz |
| Salida a internet | ninguna para la base, el motor y el `worker`; `clon_app` solo tiene la red que publica su puerto (`clon_web`), como `app` con `web`; sin `portal_worker`. El uso externo, si se aprueba, llega con otro archivo (T-289) | `portal_worker` en `egress`, y `app` en `web` |

Los servicios llevan el prefijo `clon_` porque en la red compartida cada servicio se alcanza por su nombre: `db`, `app` o `generation_batch` chocarían con los de 8000 (la lección de `docker-compose.demo.yml`). El motor del clon está solo en la red `clon_internal`; 8000 no lo alcanza, ni el clon al `generation_batch` de 8000.

## Primera vez

Variables, en el entorno o en `clon.env`:

| Variable | Qué es | Ejemplo |
|---|---|---|
| `COORD_DIR` | Carpeta local del Coordinador (fuera del repositorio; la misma de `tools/cerrar.sh`) | `/c/Users/snave/Documents/dev/evaluon-local/coord` |
| `CLON_CODE_DIR` | Código que se monta: la copia de trabajo de `016-integracion` o una copia fija | `C:/Users/snave/Documents/dev/evaluon-wt-016-integracion` |
| `CLON_MODELS_DIR` | Carpeta `models/` con los `.gguf`; por omisión la de la carpeta raíz del repositorio | |
| `CLON_CASOS_DIR` | Casos del clon; por omisión `clon-casos/` junto a `clon.env` | |
| `CLON_PORT` | Puerto en `127.0.0.1` | `8016` |
| `CLON_ENV_FILE` | Otro lugar para `clon.env` | |

La primera vez `scripts/clon.sh` genera `$COORD_DIR/clon.env` (permisos 600) con la contraseña de la base y la clave de Django al azar, el puerto y las tres carpetas. **Ningún secreto ni ruta de un equipo está en el repositorio**: el compose los exige del `--env-file` (`:?`) y el script los toma de `clon.env`. La variable de entorno manda sobre `clon.env`, que es como una medición cambia `CLON_CODE_DIR`. Para ver la configuración resuelta:

```
docker compose -p evaluon-016 -f docker-compose.clon.yml --env-file "$COORD_DIR/clon.env" --profile '*' config
```

Sin `--env-file` Compose protesta por las variables que faltan; es a propósito (sin contraseña, el clon no arranca).

## Levantarlo

```
export COORD_DIR=/c/Users/snave/Documents/dev/evaluon-local/coord
export CLON_CODE_DIR=C:/Users/snave/Documents/dev/evaluon-wt-016-integracion   # solo la primera vez
scripts/clon.sh subir
```

Comprueba que existan la red `evaluon_internal` y la imagen `evaluon-app:local` (las de 8000; no se reconstruye ni se retaga nada), levanta `clon_db`, `clon_migrate`, `clon_app` y `clon_worker` y espera `/ingresar/` 200 en 8016. **No arranca el motor** (perfil `motor`): sin ventana, un pedido que necesite el modelo falla, y lo que no lo necesita (pantallas, lectura de documentos sin visión, consultas a la base) funciona. La base queda recién migrada y vacía; el paso siguiente la carga.

## Restaurar la base

```
scripts/clon.sh restaurar                    # respaldo nuevo de 8000 y restauración
scripts/clon.sh restaurar --archivo RUTA     # restaura un respaldo que ya existe
scripts/clon.sh restaurar --forzar           # vuelve a restaurar (borra lo que el clon tenga)
```

Los pasos, con el procedimiento del runbook de respaldo (`pg_dump -Fc` por el contenedor de la base):

1. **Respaldo nuevo de 8000, solo lectura**: `pg_dump -Fc` dentro del contenedor `db` de 8000, a `$COORD_DIR/respaldos-clon/evaluon-AAAAMMDD-HHMM-clon-016.dump` (fuera del repositorio: el respaldo trae datos de casos, P4). `pg_dump` lee con una instantánea consistente, así que no hace falta detener `app` ni `worker`; si hay pedidos en espera o en curso lo avisa (el respaldo los incluye).
2. Se detienen `clon_app` y `clon_worker`, se recrea la base `evaluon_clon` (`DROP DATABASE … WITH (FORCE)` y `CREATE DATABASE`) y se carga con `pg_restore --no-owner --no-privileges`.
3. **Conteos**: compara, tabla por tabla, las filas que trae el respaldo (cuenta los bloques `COPY` de `pg_restore --data-only`) con las que tiene la base del clon. Si una difiere, sale con error. Con 8000 también se puede comparar a mano contra la misma consulta de conteos sobre su base, mientras nadie escriba.
4. Se aplican las migraciones pendientes sobre la copia (`manage.py migrate`); la base de 8000 no se toca.
5. Se arrancan `clon_app` y, si la copia no trae pedidos en espera o en curso, `clon_worker`; se espera `/ingresar/` 200 en 8016.

Se deja una marca (`$COORD_DIR/clon-restaurado.txt`) con el respaldo y la fecha. **Sin `--forzar`, `restaurar` no pisa una base ya restaurada**: después de cargar casos (T-272) o correr evaluaciones en el clon, esa base es la de las mediciones. Los usuarios y claves son los de 8000, porque es una copia.

## Ventana de GPU

Una sola instancia usa el motor a la vez; el 27B no entra junto con otro motor de generación. La ventana empieza con la cola de 8000 vacía y se hace de noche o en fin de semana. Nunca dos mediciones a la vez.

```
scripts/clon.sh ventana-abrir --simular      # lo que haría y las condiciones; no cambia nada
scripts/clon.sh ventana-abrir
… mediciones …
scripts/clon.sh ventana-cerrar --simular
scripts/clon.sh ventana-cerrar
```

`--simular` (o `DRY_RUN=1`) imprime cada paso con el prefijo `[simular]` y corre solo las comprobaciones de lectura.

**`ventana-abrir`**, condiciones (todas, o no se toca nada): el motor del clon no está en marcha; el motor de 8000 sí lo está; la cola de 8000 está vacía (ningún pedido `queued` ni `running` que no sea del Portal); ningún otro motor `llama.cpp` usa la GPU salvo `embeddings` y `reranker` de 8000; existen los archivos del 27B. Pasos: detiene el `worker` y después `generation_batch` de 8000 (como T-268); espera diez segundos y mide la memoria de video usada (`nvidia-smi`; el tope es `CLON_GPU_MAX_MIB`, 6.000 por omisión); arranca `clon_generation_batch` y espera su salud (hasta `CLON_ESPERA_MOTOR`, 1.500 s; la carga tarda de 4 a 10 minutos); comprueba su `/props`. **Si algo falla después de haber detenido 8000** (la GPU sigue ocupada, el motor del clon no queda sano, un error inesperado, Ctrl-C), el propio script baja el motor del clon y vuelve a arrancar el motor y el `worker` de 8000 y espera su salud.

**`ventana-cerrar`**: baja y quita `clon_generation_batch`; arranca el motor y el `worker` de 8000 (`docker start`: los mismos contenedores, sin recrearlos) y espera su salud; comprueba en 8000: motor sano, `/health` `ok`, `/props` con el alias y el contexto que registra su `app` (`GENERATION_BATCH_MODEL_ALIAS` y `GENERATION_BATCH_CTX_SIZE`), `worker` en marcha, `app` sana, cola vacía y `/ingresar/` 200. Sale con error si una falla. Se puede correr aunque no haya ventana abierta (no hay nada que devolver y solo comprueba).

Mientras la ventana está abierta, la Consulta de 8000 (que usa ese motor) muestra su aviso de «no disponible» y los pedidos nuevos esperan; por eso se hace de noche.

**A mano, si el script no puede**: `docker start evaluon-generation_batch-1`, esperar `healthy`, `docker start evaluon-worker-1`, y comprobar con `scripts/clon.sh estado`. Para bajar el motor del clon: `docker compose -p evaluon-016 -f docker-compose.clon.yml --env-file "$COORD_DIR/clon.env" --profile '*' rm -sf clon_generation_batch`.

El razonamiento es el de la 015: el servidor permite pensar (`--reasoning auto`) y solo el contraste lo enciende, en `low` (`GENERATION_BATCH_REASONING_CONTRAST`). Para una variante de medición, cambiar la variable en `clon.env` y recrear `clon_app` y `clon_worker`.

## Medir sobre una copia fija

Cada medición corre sobre una copia fija del commit, hecha con `git archive`, y el informe nombra el commit; no se integra nada a esa copia durante la medición.

```
COMMIT=$(git -C C:/Users/snave/Documents/dev/evaluon-wt-016-integracion rev-parse --short HEAD)
COPIA=$COORD_DIR/copias-clon/$COMMIT && mkdir -p "$COPIA"
git -C C:/Users/snave/Documents/dev/evaluon-wt-016-integracion archive HEAD | tar -x -C "$COPIA"
CLON_CODE_DIR=$COPIA scripts/clon.sh ejecutar python manage.py medir_evaluacion …
```

`ejecutar` corre la orden en un contenedor nuevo de `clon_worker` (misma configuración, sin dependencias) con el código de `CLON_CODE_DIR` en solo lectura. `clon_app` y `clon_worker` que ya estaban en marcha siguen con la copia de trabajo hasta que se los recrea (`scripts/clon.sh subir` con la variable cambiada). Los casos que la medición lea van en `CLON_CASOS_DIR` (se copian desde `corpus/casos` de la raíz; son locales, P4).

## Integrar en `016-integracion`

Las ramas de tarea `016-T-NNN` se integran en `016-integracion`, no en `main`. `tools/cerrar.sh` acepta `BASE`:

```
BASE=016-integracion COORD_DIR=… tools/cerrar.sh 016-calidad-medible NNN "mensaje" [COMMIT_BASE_VERIFICADO]
```

Sin `BASE` todo es como siempre (`main`). Con `BASE=016-integracion` integra `origin/016-integracion`, comprueba que esté dentro de la rama de la tarea y decide si repite la suite comparando contra esa rama. Cuando un paso pasa su umbral, el Coordinador abre el pull request `016-integracion` → `main` con el registro de la medición.

## Volver atrás

- **Quitar solo los contenedores, conservando la base**: `scripts/clon.sh bajar` (se niega si el motor del clon está en marcha: antes `ventana-cerrar`).
- **Rehacer la base desde cero**: `scripts/clon.sh restaurar --forzar` (respaldo nuevo de 8000).
- **Borrar el clon entero**: `scripts/clon.sh bajar`, después `docker volume rm evaluon-016_clon_pgdata` y borrar `$COORD_DIR/clon.env`, `clon-restaurado.txt`, `respaldos-clon/` y `clon-casos/`. 8000 no depende de nada de esto.
- **Una ventana a medias**: `scripts/clon.sh ventana-cerrar` (ver «A mano»).

## Verificación de T-270

Ver `specs/016-calidad-medible/verificacion/T-270.md` (la deja el testeador evaluador). Lo que hizo el desarrollador está en el informe de entrega.
