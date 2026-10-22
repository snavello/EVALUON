# Entorno · Despliegue de la 017 en el sistema principal (8000) para la demo

Estado: desplegado el 2026-10-22 01:48 por el Coordinador. Versión provisoria para la demo del mediodía: el runbook completo (T-332) y la auditoría (etapa 6) quedan para después.

## Decisiones del responsable (literales)
- 2026-10-21 23:25: «no me sirve ese recorte, necesito mostrarlo completo, puedo resignar auditoria y controles finos, solo voy a mostrar el caso cero cargado y necesito pasear por todo el sistema. miralo otra vez, puedo extender hasta las 9 am». De ahí la verificación liviana por tarea, sin T-316/T-317 formales, sin T-333/T-334 (reemplazadas por el recorrido del Coordinador) y con T-331 diferida.
- 2026-10-22 01:01: «Sí, instalá en 8000 todo lo que hay en main, con la 016 incluida (uso externo apagado).» Cumple el punto 6 de ADR-0071: 8000 toma también la 016 y la migración `audit.0009_externo`.

## Qué se desplegó
- Raíz en `main` 18e6e34c (PR 464). Imagen `app` reconstruida: `evaluon-app:local` = ac2a6a9df3a6.
- Migraciones aplicadas sobre la base real: `accounts.0003_tema_y_fotos` y `audit.0009_externo`. `migrate --check` en 0.
- Servicios recreados: `app`, `worker`, `portal_worker`. Uso externo apagado (`EXTERNAL_ENABLED=false` por omisión; sin `docker-compose.externo.yml`).
- Suite completa sobre la rama integrada (8d9c6b61): 7904 pasaron, 45 omitidas (carpetas solo locales), 0 fallaron.

## Segundo paso (02:25): correcciones del recorrido
- Raíz en `main` b1bd308c (PR 465, T-336: anillo sin pedido, «Venció» en plazos, «Falta:» siempre, documentos propios en Ofertas). Sin migraciones. Imagen reconstruida (`evaluon-app:local` = 9bf8feb504bc) y servicios recreados. Suite completa sobre la rama: 7925 pasaron, 0 fallaron.
- Comprobado en las cinco secciones del procedimiento 10: sin anillo (no hay pedidos en curso), «Falta:» siempre, «Venció · hace 263 días» en plazos.

## Respaldo previo
`backups/evaluon-2026-10-22-previo-017.dump` (pg_dump -Fc, 146.412.724 bytes, 861 líneas con `pg_restore -l`). Solo en el equipo (ignorada por git). Imagen anterior: `evaluon-app:previo-017` (fc1ac35bc2eb).

Las copias sin seguimiento de `docs/diseno/exploracion-ui/` que había en la raíz se movieron a `evaluon-local/coord/raiz-exploracion-ui-previo/` antes del `pull`: su contenido es igual al de `main` salvo el fin de línea.

## Humo
- Sin sesión: `/` da 302; `/ingresar/` 200; `/static/diseno/tokens.css`, `/static/journey/tablero.js`, `/static/marca/logotipo-claro.svg` y la fuente Hanken Grotesk dan 200.
- Con sesión del usuario `desarrollo-comision` (sesión creada con el cliente de pruebas de Django, sin tocar claves), procedimiento 10 (alimento balanceado para canes, 3 ofertas): las cinco secciones, el listado y «Mis fotos» se ven en los dos temas; el selector de tema cambia y vuelve a la misma pantalla; los mosaicos abren un detalle por vez.
- Fotos de punta a punta: subir una foto sintética, verla en el primer panel como «Foto de su perfil» y quitarla. Quedó sin fotos.

## Vuelta atrás
Las dos migraciones agregan tablas y columnas; la vuelta atrás segura es restaurar el respaldo:
1. `docker compose stop app worker portal_worker`.
2. Restaurar según el runbook de la 004 (sección de reversa, punto 2; `dropdb` borra la base vigente: pedir confirmación; se pierde todo lo hecho desde el respaldo) con `backups/evaluon-2026-10-22-previo-017.dump`.
3. Llevar la raíz a 595c503d (pedir confirmación, cambia el árbol de trabajo), `docker tag evaluon-app:previo-017 evaluon-app:local` y `docker compose up -d --no-build --force-recreate app worker portal_worker`.
