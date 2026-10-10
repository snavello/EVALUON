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

# Lote 2 · 2026-10-08

Estado: desplegado con una observación abierta (autorizado: «desplega 8000 también es un piloto»). Los tiempos de carga no cumplen el umbral; decide el responsable si se queda o se vuelve atrás.

## Qué
- Raíz en `main` b233a04 (suma T-194, T-195, T-196, T-198, T-199, T-200, T-203, T-207, T-208, T-209, T-213). Imagen `app` reconstruida; `migrate`: sin migraciones nuevas; `migrate --check` en 0.
- Antes: cola sin pedidos en curso (70 `done`); se pararon `app`, `worker` y `portal_worker`. No se tocó nada más.
- Estado final de las etiquetas: `evaluon-app:local` apunta hoy a la imagen ANTERIOR (674573a2aeb9, igual a `previo-014-lote2`) y la nueva está como `evaluon-app:lote2-lento` (13c43bf91da8). El código en ejecución es el de la raíz (main b233a04) porque `app` lo monta desde la carpeta. Para dejar imagen y código coherentes: `docker tag evaluon-app:lote2-lento evaluon-app:local` y recrear los tres servicios.

## Respaldo previo
`backups/evaluon-2026-10-08-previo-014-lote2.dump` (pg_dump -Fc, 126.115.327 bytes, 846 entradas con `pg_restore -l`).

## Humo
- Sin sesión `/expedientes/` 302; con sesión (usuario 3, procedimiento 9): `/expedientes/`, `/nuevo/`, `procedimiento`, `pliego`, `ofertas`, `evaluacion`, `normativas` dan 200 con las cinco pestañas. Estáticos de `journey/` 200. Sin errores en los registros.
- FALLA el umbral de tiempo (< 2 s): mediana de 5 cargas de `/pliego/` 3,4 s, `/evaluacion/` 6,5 s, `/ofertas/` 2,7 s (lote 1: pliego 1,5 s). En un contenedor aparte con la imagen previa y su propio código, evaluación y ofertas dan 1,0 s. Sin migraciones: la causa es código del lote 2. Se devuelve a desarrollo.
- No probado: caso de punta a punta con la GPU.

## Volver atrás
El contenedor `app` monta `evaluon/`, `tests/`, `scripts/` y `manage.py` desde la raíz: cambiar solo la imagen NO revierte el código (comprobado). Para volver al lote 1:
1. Llevar la raíz al commit del lote 1 (c1d8b87 o el vigente antes de b233a04; cambia el árbol de trabajo: pedir confirmación).
2. `docker tag evaluon-app:previo-014-lote2 evaluon-app:local` y `docker compose up -d --no-build --force-recreate app worker portal_worker`.
3. Sin migraciones nuevas: no hace falta restaurar la base; el respaldo queda por si acaso.

# Lote 3 · 2026-10-08

Estado: desplegado (autorizado: «desplega 8000 también es un piloto»). Cumple el umbral de tiempo (< 2 s).

## Qué
- Raíz en `main` 27e641f (suma T-197 alta subiendo el pliego, T-214 normas, T-221 rendimiento). Imagen `app` reconstruida con `docker compose build app`: `evaluon-app:local` = 1c6460c88b76, coherente con el código. `migrate`: sin migraciones nuevas; `migrate --check` en 0.
- Antes: cola sin pedidos en curso (70 trabajos `done`, 5 pedidos de evaluación `done`); se pararon `app`, `worker` y `portal_worker`. No se tocó nada más.
- Etiquetas de imagen: `previo-014-lote1` (4bc7f409df7b) y `previo-014-lote2` (674573a2aeb9) siguen; `lote2-lento` (13c43bf91da8) ya no se usa.

## Respaldo previo
`backups/evaluon-2026-10-08-previo-014-lote3.dump` (pg_dump -Fc, 126.116.321 bytes, 861 líneas con `pg_restore -l`).

## Humo
- Sin sesión `/expedientes/` 302 a `/ingresar/?next=/expedientes/`.
- Con sesión (cliente de pruebas, usuario 3, procedimiento 9): `/expedientes/nuevo/`, `/expedientes/9/`, `procedimiento`, `pliego`, `ofertas`, `evaluacion`, `normativas` dan 200; la barra enlaza procedimiento, pliego, ofertas, evaluación y normativas.
- Mediana de 5 cargas (umbral < 2 s): procedimiento 0,80 s; pliego 1,11 s (1,08 a 1,19); ofertas 0,78 s (0,75 a 0,83); evaluación 1,33 s (1,28 a 1,45); normativas 0,80 s (0,77 a 0,84). Lote 2 era pliego 3,4 / ofertas 2,7 / evaluación 6,5.
- Sin errores en los registros de `app`, `worker` y `portal_worker` (5 minutos tras el arranque).
- No probado: caso de punta a punta con la GPU.

## Volver atrás
Sin migraciones nuevas: no hace falta restaurar la base. Llevar la raíz al commit del lote anterior (b233a04; pedir confirmación, cambia el árbol de trabajo), `docker tag evaluon-app:previo-014-lote2 evaluon-app:local` y `docker compose up -d --no-build --force-recreate app worker portal_worker`. El respaldo del lote 3 queda por si acaso.

# Lote 4 · 2026-10-09

Estado: desplegado (autorizado: «desplega 8000 también es un piloto»). Cumple el umbral de tiempo (< 2 s).

## Qué
- Raíz en `main` bf8c4a2 (suma lote 1 de la 014: circulares, normas que rigen, pendientes agrupados; T-210, T-211, T-204; lote 2: ingreso con la guía visual y un solo encabezado, exportar Excel y PDF, consulta en la pestaña, huecos funcionales, suite en paralelo). Dependencias nuevas: XlsxWriter y pytest-xdist (verificadas dentro de la imagen). Imagen `app` reconstruida: `evaluon-app:local` nueva; la anterior quedó como `evaluon-app:previo-014-lote4`.
- `migrate`: sin migraciones nuevas; `migrate --check` en 0.
- Antes: cola sin pedidos en curso (70 trabajos `done`); se pararon `app`, `worker` y `portal_worker`. No se tocó nada más.

## Respaldo previo
`backups/evaluon-2026-10-09-previo-014-lote4.dump` (pg_dump -Fc, 126.116.984 bytes, 861 líneas con `pg_restore -l`).

## Humo (cliente de pruebas, usuario 3, sin cambiar claves)
- `/ingresar/`: 200, carga `tokens.css`, sin «Recorrido» ni «Importar del Portal».
- `/` con sesión: 302 a `/expedientes/9/procedimiento/`. El encabezado no contiene «Recorrido» ni «Importar del Portal». `/recorrido/` y `/procedimientos/` dan 302 a `/`, que lleva a la pestaña.
- Medianas de 5 cargas (umbral < 2 s), 200 en todas: procedimiento 0,87 s; pliego 1,14 s; ofertas 0,82 s; evaluación 1,34 s; normativas 0,87 s; `/expedientes/normativas/` 0,02 s. `/expedientes/9/matriz/` da 404 (no es una pestaña: son cinco).
- Exportaciones de la pestaña Evaluación (planilla y cuadro, xlsx y pdf): 200; los .xlsx son zip válidos y los .pdf empiezan con %PDF.
- Sin errores en los registros de `app`, `worker` y `portal_worker` (5 minutos).
- No probado: caso de punta a punta con la GPU.

## Volver atrás
Sin migraciones nuevas: no hace falta restaurar la base. Llevar la raíz al commit del lote anterior (27e641f; pedir confirmación, cambia el árbol de trabajo), `docker tag evaluon-app:previo-014-lote4 evaluon-app:local` y `docker compose up -d --no-build --force-recreate app worker portal_worker`. El respaldo del lote 4 queda por si acaso.
