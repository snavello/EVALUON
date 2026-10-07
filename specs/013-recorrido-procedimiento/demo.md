# Instancia de demostración (feature 013)

Segunda copia de la aplicación, con su propia base vacía, para correr un caso desde cero en vivo sin mezclarlo con la base de trabajo. Archivos: `docker-compose.demo.yml` y `scripts/demo.sh`. Sin secretos en el repositorio.

## Qué es

| | Pila real (`evaluon`) | Demostración (`evaluon-demo`) |
|---|---|---|
| Dirección | `http://127.0.0.1:8000/` | `http://127.0.0.1:8001/` (`DEMO_PORT`) |
| Base | `db` / `evaluon`, volumen `pgdata` | `demo_db` / `evaluon_demo`, volumen `demo_pgdata` (mismo Postgres, imagen y huella, pero otro servidor) |
| Aplicación y pedidos | `app`, `worker`, `portal_worker` | `demo_app`, `demo_worker`, `demo_portal_worker` |
| Modelos | `generation`, `generation_batch`, `embeddings`, `reranker` | los mismos: se comparten por la red `evaluon_internal` (no se duplican en la GPU) |

- Los servicios de la demostración llevan prefijo `demo_` para no chocar por nombre con los de la pila real en la red compartida.
- Código: el de la copia de trabajo desde la que se levanta (montado en solo lectura), con la imagen `evaluon-app:local` ya construida (no se reconstruye).
- P4: solo `demo_portal_worker` está en la red con salida a internet (`evaluon-demo_demo_egress`); el código solo conecta a `PORTAL_ALLOWED_HOSTS`. `demo_app` y `demo_worker` no tienen salida. La base de la demostración no publica puertos.
- Límite a tener presente: `demo_app` y `demo_worker` están en `evaluon_internal` para llegar a los modelos, y en esa red también está `db` de la pila real. La demostración no la usa (`POSTGRES_HOST=demo_db`), pero la red no lo impide.
- Los pedidos de IA de las dos pilas comparten GPU y motores de una sola plaza (`--parallel 1`): no correr a la vez una medición o un pedido largo en la pila real y en la demostración.

## Levantar

Requisito: la pila de modelos de `evaluon` levantada (`docker compose up -d` en la raíz).

```
bash scripts/demo.sh subir      # crea secretos si faltan, levanta, migra la base vacía
bash scripts/demo.sh usuarios   # una sola vez: crea demo_evaluador y demo_operador
bash scripts/demo.sh estado
```

Los secretos están fuera del repositorio, en `C:/Users/snave/Documents/dev/evaluon-local/coord/`:
- `demo.env`: `POSTGRES_PASSWORD`, `DJANGO_SECRET_KEY`, `DEMO_PORT` (se genera solo la primera vez).
- `demo-usuarios.txt`: usuarios y claves generadas de la demostración.

(Rutas distintas: variables `DEMO_DIR`, `DEMO_ENV_FILE`, `DEMO_USERS_FILE`.)

## Usar

Entrar a `http://127.0.0.1:8001/` con `demo_evaluador` (incluye operador) o `demo_operador`, ambos con rol de lectura y escritura; las claves están en `demo-usuarios.txt`. La base arranca vacía: sin normativa, procedimientos ni casos. Cargar el caso por la pantalla (o importando desde el Portal) como en la pila real. La normativa no se copia: si la demostración la necesita, se carga en `demo_db` con los mismos comandos de `specs/001-normativa/` (`docker compose -f docker-compose.demo.yml --env-file <demo.env> run --rm demo_app python manage.py ...`).

## Bajar y borrar

```
bash scripts/demo.sh bajar     # detiene; conserva la base de la demostración
bash scripts/demo.sh subir     # vuelve a levantarla con sus datos
bash scripts/demo.sh borrar    # BORRA contenedores, redes propias, volumen demo_pgdata y los dos archivos de secretos
```

`borrar` no toca ningún contenedor, volumen ni red `evaluon-*` / `evaluon_*` de la pila real. Después de `borrar` no queda rastro (salvo la imagen `evaluon-app:local`, que es de la pila real). Para repetir desde cero: `borrar`, `subir`, `usuarios` (genera claves nuevas).

## Comprobaciones al levantar

1. `scripts/demo.sh estado`: `demo_db` y `demo_app` healthy; `demo_worker` y `demo_portal_worker` Up; `demo_migrate` terminó con 0 («la base está vacía; se aplican las migraciones»).
2. `curl -sL http://127.0.0.1:8001/` llega a la pantalla de ingreso.
3. Modelos compartidos: desde `evaluon-demo-demo_app-1`, `http://generation:8080/health`, `generation_batch`, `embeddings` y `reranker` responden 200.
4. `docker network inspect evaluon-demo_demo_egress` lista solo `demo_portal_worker`; desde `demo_worker` no resuelve `afipcompras.afip.gob.ar`, desde `demo_portal_worker` sí.
