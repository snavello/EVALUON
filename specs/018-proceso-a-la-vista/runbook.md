# Runbook 018 · El proceso a la vista

Despliegue de la feature 018 sobre el piloto existente. La feature solo cambia la exposición: no hay migraciones, ni cambios en `docker-compose.yml` ni en el `Dockerfile`. Para levantar desde cero rigen los runbooks anteriores (`specs/004-evaluacion-asistida/runbook.md`).

Estado: aprobado y aplicado · Fecha: 2026-11-18 · Aprobó: responsable del proyecto · Commit desplegado: `bf2270f9` (anterior: `2272895d`)

Los comandos se corren desde la raíz del repositorio, en Git Bash, con `MSYS_NO_PATHCONV=1` delante de los de `docker`. Proyecto de Compose: `evaluon`.

## 1. Desplegar

1. Comprobar que no hay cambios de infraestructura: `git diff --stat COMMIT_ANTERIOR origin/main -- docker-compose.yml Dockerfile '*migrations*'` no debe listar nada.
2. Respaldo (formato custom) y comprobación:
   `docker compose -p evaluon exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > RESPALDOS/evaluon-pre018-AAAAMMDD-HHMM.dump`
   Comprobar tamaño distinto de cero y `docker compose -p evaluon exec -T db pg_restore --list < ARCHIVO.dump | wc -l` mayor que cero (dio 869 entradas, 146 MB). Sin respaldo comprobado, no seguir.
3. Etiquetar la imagen actual: `docker tag evaluon-app:local evaluon-app:antes-018` y anotar `git rev-parse HEAD` (`2272895d`).
4. `git pull --ff-only origin main` (sin cambiar de rama; si no es avance rápido, frenar).
5. `docker compose -p evaluon build app`. El `Dockerfile` corre `collectstatic` al construir, así que la imagen nueva trae los estáticos nuevos. Si se omite este paso, las pantallas salen sin estilos.
6. `docker compose -p evaluon up -d --no-deps app worker portal_worker` (comparten la imagen). No se tocan `db`, `embeddings`, `reranker` ni `generation_batch`. Corte de la aplicación: unos 13 segundos.
7. `docker compose -p evaluon exec -T app python manage.py migrate` debe decir "No migrations to apply".

## 2. Verificar

- `docker compose -p evaluon ps`: `app`, `db`, `embeddings`, `reranker`, `generation_batch` "healthy"; `worker` y `portal_worker` "Up".
- `curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' http://127.0.0.1:8000/` da 302 hacia `/ingresar/?next=/`.
- Estáticos nuevos con 200 en `http://127.0.0.1:8000/static/journey/` para `proceso.css`, `portada.css`, `mapa.css`, `cuadro.css`, `inicio.css` y `recorrido.js`.
- `docker compose -p evaluon exec -T app python manage.py check`: "no issues".
- `docker compose -p evaluon exec -T app python manage.py shell -c "from evaluon.journey.proceso.calculo import proceso_de; print(proceso_de)"` imprime la función.
- Si los estáticos no responden: `docker compose -p evaluon exec -T app python manage.py collectstatic --noinput`.

## 3. Volver atrás

La feature no cambia el esquema, así que normalmente alcanza con la imagen.

1. Imagen anterior: `docker tag evaluon-app:antes-018 evaluon-app:local` y `docker compose -p evaluon up -d --no-deps --force-recreate app worker portal_worker`. Dejar el código de la raíz como está o, si hace falta, volver a `2272895d` en una copia aparte (no con `reset --hard` sobre la raíz).
2. Solo si hubiera daño en los datos (no se espera): restaurar el respaldo en una base nueva y comprobar antes de reemplazar. Restaurar sobre la base real borra lo escrito después del respaldo; pedir confirmación al responsable antes. Comando: `docker compose -p evaluon exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < ARCHIVO.dump`.
3. Nunca `down -v` sobre el proyecto `evaluon`: borra el volumen `pgdata`.
