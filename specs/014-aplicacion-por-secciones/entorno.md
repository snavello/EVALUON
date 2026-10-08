# Entorno · Despliegue del primer lote de la 014 en el sistema principal

Estado: desplegado el 2026-10-08 (autorizado por el responsable: «desplega 8000 también es un piloto. si está mal corregimos»).

## Qué se desplegó
- Raíz en `main` (c1d8b87): 014 primer lote (T-192, T-193 con migraciones, T-201).
- Imagen `app` reconstruida (incluye `collectstatic`). La imagen anterior quedó etiquetada `evaluon-app:previo-014-lote1`.
- Migraciones aplicadas sobre la base real: `audit.0008_hechos_de_la_014`, `tenders.0009_historial_y_alta_desde_el_pliego`, `offers.0007_historial_y_alta_desde_los_archivos`, `assessment.0005_decisiones_de_descarte`, `norms.0008_normas_subidas`, `portal.0004_origen_en_documento`. `migrate --check` en 0.
- Antes: cola sin pedidos en curso (70 `done`); se pararon `app`, `worker` y `portal_worker`. No se tocaron `db`, `generation`, `generation_batch`, `embeddings`, `reranker`, el proyecto demo ni postgres-dev.

## Respaldo previo
`backups/evaluon-2026-10-08-previo-014-lote1.dump` (pg_dump -Fc, 126.069.681 bytes, 752 entradas legibles con `pg_restore -l`). Solo en el equipo (ignorada por git).

## Humo
- Servicios: `db`, `generation`, `generation_batch`, `embeddings`, `reranker` y `app` sanos; `worker` y `portal_worker` arriba.
- Sin sesión: `/expedientes/` responde 302 a `/ingresar/?next=/expedientes/`.
- Con sesión (cliente de pruebas de Django, usuario 3, sin cambiar claves), procedimiento 9: `/expedientes/`, `/expedientes/9/`, `/expedientes/9/pliego/` y `/recorrido/` dan 200. La barra de pestañas enlaza a pliego, ofertas, matriz, evaluación y normativas (más el enlace al procedimiento).
- `/static/journey/secciones.css` y `/static/journey/secciones.js`: 200.
- Tiempo de carga de la pestaña pliego, 5 mediciones: mediana 1,52 s (1,46 a 1,64 s), umbral < 2 s.
- Sin errores en los registros de `app`, `worker` y `portal_worker` (3 minutos tras el arranque).
- No probado: un caso de punta a punta con la GPU (no se lanzó ningún pedido).

## Volver atrás
Varias migraciones de la 014 no se deshacen con datos nuevos (ver `specs/014-aplicacion-por-secciones/verificacion/T-193.md`); la vuelta atrás es restaurar el respaldo:
1. `docker compose stop app worker portal_worker`.
2. Restaurar según el runbook de la 004 (sección de reversa, punto 2; `dropdb` borra la base vigente: pedir confirmación; se pierde todo lo hecho desde el respaldo) con `backups/evaluon-2026-10-08-previo-014-lote1.dump`.
3. Volver la raíz al commit anterior a c1d8b87 y reconstruir la imagen, o usar la etiqueta `evaluon-app:previo-014-lote1` (hay que retaguearla como `evaluon-app:local`), y `docker compose up -d app worker portal_worker`.
