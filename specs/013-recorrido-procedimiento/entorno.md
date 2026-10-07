# Entorno · Despliegue de la 013 en el sistema principal

Estado: desplegado el 2026-10-07 (aprobado por el responsable a las 18:05).

## Qué se desplegó
- Raíz en `main` (9f1bfd2): 013 (recorrido del procedimiento), T-189 (hoja de compliance), T-190 (informe técnico), T-178.
- Imagen `app` reconstruida (incluye `collectstatic`).
- Migraciones aplicadas sobre la base real: `offers.0005_hoja_de_compliance`, `offers.0006_informe_tecnico_del_area`, `tenders.0008_job_progress`. `migrate --check` en 0.
- Antes: sin mediciones ni tareas en cola (todas `done`); se pararon `app`, `worker` y `portal_worker`.

## Respaldo previo
`backups/evaluon-2026-10-07-previo-013.dump` (pg_dump -Fc, 126 MB, 767 entradas legibles con `pg_restore -l`). Solo en el equipo (ignorada por git).

## Humo
- Servicios: `db`, `generation`, `generation_batch`, `embeddings`, `reranker` y `app` sanos; `worker` y `portal_worker` arriba.
- `/recorrido/` con sesión: 200 (usuarios 2 y 3, cliente de pruebas de Django, sin cambiar claves); sin sesión: 302 al ingreso. El usuario 1 recibe 403 (permiso de la vista; a revisar si debería entrar).
- `/static/journey/recorrido.js` y `/static/diseno/tokens.css`: 200.
- Sin errores en los registros de `app`, `worker` y `portal_worker`.

## Volver atrás
`docker compose stop app worker portal_worker`; restaurar el respaldo según el runbook de la 004 (sección de reversa; `dropdb` borra la base vigente: pedir confirmación) o deshacer solo las migraciones: `migrate tenders 0007`, `migrate offers 0004` (pierde la hoja de compliance y el informe técnico); volver la raíz al commit anterior y reconstruir la imagen.
