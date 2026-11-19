# Runbook 019 · Decisión de filas técnicas

Despliegue de la feature 019 sobre el piloto existente. Cambia un servicio (`evaluon/assessment/services/review.py`) y agrega un servicio (`technical_decisions.py`) y un comando de solo lectura (`listar_decisiones_tecnicas`). No hay migraciones ni cambios en `docker-compose.yml` ni en el `Dockerfile`. Para levantar desde cero rigen los runbooks anteriores (`specs/004-evaluacion-asistida/runbook.md`).

Estado: aprobado y aplicado · Fecha: 2026-11-18 · Aprobó: responsable del proyecto · Commit desplegado: `f2f78179` (anterior: `bf2270f9`)

Los comandos se corren desde la raíz del repositorio, en Git Bash, con `MSYS_NO_PATHCONV=1` delante de los de `docker`. Proyecto de Compose: `evaluon`.

## 1. Desplegar

1. Sin cambios de infraestructura: `git diff --stat COMMIT_ANTERIOR origin/main -- docker-compose.yml Dockerfile 'evaluon/*/migrations'` no debe listar nada.
2. Respaldo (formato custom) y comprobación:
   `docker compose -p evaluon exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > RESPALDOS/evaluon-pre019-AAAAMMDD-HHMM.dump`
   Comprobar tamaño distinto de cero y `docker compose -p evaluon exec -T db pg_restore --list < ARCHIVO.dump | wc -l` mayor que cero (dio 869 entradas, 146 MB). Sin respaldo comprobado, no seguir.
3. Etiquetar la imagen actual: `docker tag evaluon-app:local evaluon-app:antes-019` y anotar `git rev-parse HEAD` (`bf2270f9`).
4. `git pull --ff-only origin main` (sin cambiar de rama; si no es avance rápido, frenar).
5. `docker compose -p evaluon build app`.
6. `docker compose -p evaluon up -d --no-deps app worker portal_worker`. No se tocan `db`, `embeddings`, `reranker` ni `generation_batch`. Tiempo hasta que la aplicación vuelve a responder: unos 7 segundos.
7. `docker compose -p evaluon exec -T app python manage.py migrate` debe decir "No migrations to apply".

## 2. Verificar

- `docker compose -p evaluon ps`: `app`, `db`, `embeddings`, `reranker`, `generation_batch` "healthy"; `worker` y `portal_worker` "Up".
- `curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' http://127.0.0.1:8000/` da 302 hacia `/ingresar/?next=/`.
- `docker compose -p evaluon exec -T app python manage.py check`: "no issues".
- `docker compose -p evaluon exec -T app python manage.py shell -c "from evaluon.assessment.services.technical_decisions import technical_row_decisions as t; print(t)"` imprime la función.
- `docker compose -p evaluon exec -T app python manage.py listar_decisiones_tecnicas --help` muestra la ayuda (no correr el comando con usuario en esta verificación: su salida es material reservado).
- Los registros de arranque de `app`, `worker` y `portal_worker` no muestran errores ni trazas.

## 3. Después de desplegar

El responsable corre, desde la raíz del repositorio:

`docker compose -p evaluon exec app python manage.py listar_decisiones_tecnicas --usuario <usuario con rol de la Comisión>`

El comando pide la clave del usuario y es de solo lectura. Su salida es material reservado (P4): no se copia al repositorio. Al repositorio solo va la cuenta final.

## 4. Volver atrás

La feature no cambia el esquema, así que normalmente alcanza con la imagen.

1. `docker tag evaluon-app:antes-019 evaluon-app:local` y `docker compose -p evaluon up -d --no-deps --force-recreate app worker portal_worker`. Dejar el código de la raíz como está o, si hace falta, volver a `bf2270f9` en una copia aparte (no con `reset --hard` sobre la raíz).
2. Solo si hubiera daño en los datos (no se espera): restaurar el respaldo en una base nueva y comprobar antes de reemplazar. Restaurar sobre la base real borra lo escrito después del respaldo; pedir confirmación al responsable antes. Comando: `docker compose -p evaluon exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < ARCHIVO.dump`.
3. Nunca `down -v` sobre el proyecto `evaluon`: borra el volumen `pgdata`.
