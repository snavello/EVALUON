# Runbook 020 · Evi

Despliegue de la feature 020 sobre el piloto existente. Agrega el módulo `evaluon/journey/evi/`, la vista `views/evi.py`, dos archivos estáticos (`evi.css`, `evi.js`), cuatro rutas bajo `expedientes/` y dos ajustes (`EVI_QUESTIONS_ENABLED`, `EVI_TIMEOUT_SECONDS`). No hay migraciones ni cambios en el `Dockerfile`. `docker-compose.yml` suma esos dos ajustes al entorno de `app`, `worker` y `portal_worker` (tres líneas), y `.env.example` los documenta. Para levantar desde cero rigen los runbooks anteriores (`specs/004-evaluacion-asistida/runbook.md`).

Estado: aprobado y aplicado · Fecha: 2026-11-19 · Aprobó: responsable del proyecto («Sí, desplegar») · Commit desplegado: `fca767b5` (anterior: `f2f78179`)

Los comandos se corren desde la raíz del repositorio, en Git Bash, con `MSYS_NO_PATHCONV=1` delante de los de `docker`. Proyecto de Compose: `evaluon`. Los archivos de Compose los fija `COMPOSE_FILE` en `.env`; no hace falta pasarlos con `-f`.

## 1. Desplegar

1. Cambios de infraestructura: `git diff --stat COMMIT_ANTERIOR origin/main -- docker-compose.yml Dockerfile 'evaluon/*/migrations' pyproject.toml` listó solo `docker-compose.yml` (3 líneas: los dos ajustes de Evi). Sin migraciones ni dependencias nuevas.
2. Respaldo (formato custom) y comprobación:
   `docker compose -p evaluon exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > RESPALDOS/evaluon-pre020-AAAAMMDD-HHMM.dump`
   Comprobar tamaño distinto de cero y `docker compose -p evaluon exec -T db pg_restore --list < ARCHIVO.dump | wc -l` mayor que cero (dio 869 entradas, 73 de datos de tablas, 146.418.071 bytes; archivo `evaluon-pre020-20261119-0908.dump`). Sin respaldo comprobado, no seguir.
3. Guardar la imagen anterior como `evaluon-app:antes-020` y anotar `git rev-parse HEAD` (`f2f78179`).
   - Primero comprobar que la etiqueta `evaluon-app:local` es la imagen que usa el piloto: `docker inspect evaluon-app-1 --format '{{.Image}}'` debe coincidir con `docker image inspect evaluon-app:local --format '{{.Id}}'`. Si coincide: `docker tag evaluon-app:local evaluon-app:antes-020`.
   - En este despliegue **no coincidía** (ver «Fallas conocidas»). La imagen en uso ya no existía en el equipo y `docker commit` del contenedor falló. Se reconstruyó desde la raíz, todavía en `f2f78179` y antes del `git pull`: `docker build -t evaluon-app:antes-020 --label evaluon.commit=f2f78179 .`
   - Comprobación de que equivale a lo que corría: `pip freeze` idéntico al del contenedor en uso (44 paquetes, la capa de dependencias salió de la caché del 2026-10-14) y los 56 archivos de `/app/staticfiles` con la misma huella. No trae `evaluon/journey/evi/` ni los estáticos de Evi.
4. `git pull --ff-only origin main` (sin cambiar de rama; si no es avance rápido, frenar). Quedó en `fca767b5`.
5. `docker compose -p evaluon build app`. El `Dockerfile` corre `collectstatic` al construir: la imagen nueva trae `evi.css` y `evi.js`. Comprobar que las dependencias no cambiaron: `docker run --rm --entrypoint pip evaluon-app:local freeze` igual al de la imagen anterior (dio igual).
6. `docker compose -p evaluon up -d --no-deps app worker portal_worker` (comparten la imagen; se recrean los tres porque cambió su entorno). No se tocan `db`, `embeddings`, `reranker` ni `generation_batch` (siguen con su inicio del 2026-11-11). La aplicación volvió a responder en menos de 10 segundos (a los 5 segundos ya figuraba sana).
7. `docker compose -p evaluon exec -T app python manage.py migrate --plan` dio "No planned migration operations", `makemigrations --check --dry-run` dio "No changes detected" y `migrate` dio "No migrations to apply".

## 2. Verificar

- `docker compose -p evaluon ps`: `app`, `db`, `embeddings`, `reranker`, `generation_batch` "healthy"; `worker` y `portal_worker` "Up".
- `curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' http://127.0.0.1:8000/` da 302 hacia `/ingresar/?next=/`. `http://127.0.0.1:8000/expedientes/evi/` sin sesión también da 302 hacia el ingreso.
- Estáticos nuevos con 200 en `http://127.0.0.1:8000/static/journey/`: `evi.css` (21.264 bytes) y `evi.js` (14.044 bytes), del mismo tamaño que los del repositorio. Si no responden: `docker compose -p evaluon exec -T app python manage.py collectstatic --noinput`.
- `docker compose -p evaluon exec -T app python manage.py check`: "System check identified no issues (0 silenced)".
- `docker compose -p evaluon exec -T app sh -c 'echo $EVI_QUESTIONS_ENABLED $EVI_TIMEOUT_SECONDS'` da `true 50`.
- Los registros de arranque de `app`, `worker` y `portal_worker` no muestran errores ni trazas (36 líneas en `app`, solo respuestas 200 y 302).

### Comprobación con datos del piloto, sin dejar rastro

Se hizo desde `manage.py shell`, con el cliente de pruebas de Django y un usuario con rol de evaluador (`force_login`, sin claves), todo dentro de `transaction.atomic()` con `transaction.set_rollback(True)`. Los resultados son material reservado (P4): acá van solo cuentas y tiempos.

- **Botón:** presente en el inicio, la lista, la portada y el cuadro (`id="evi-boton"`, con `evi.css` y `evi.js` enlazados). En inicio y lista apunta al circuito general, sin pasos; en la portada declara los pasos 1 y 5; en el cuadro, 4 y 6. La pantalla de ingreso no lo trae.
- **Panel general** (`expedientes/evi/`): 200 en 10 ms; 7 pasos, 0 marcas «Usted está aquí», sin estados, bloque de preguntas con el rótulo «Experimental», 0 enlaces.
- **Panel de procedimiento** (`expedientes/<id>/evi/?pasos=…`), dos procedimientos reales con 3 ofertas cada uno y tres pantallas de origen (`1,5`, `4,6`, `7`): 200 en los 12 pedidos; 7 pasos con estado en todos; «Usted está aquí» sobre 2, 2 y 1 pasos según lo pedido; 0 enlaces. Tiempos: 343 a 371 ms el primer pedido y 256 a 418 ms el siguiente en uno; 653 a 719 ms y 493 a 678 ms en el otro (el requisito es menos de 2 segundos).
- **Tiempos de pantallas** (primer pedido y siguiente, medidos dentro del proceso, sin red): inicio 3.761 ms y 89 ms (el primero incluye la carga en frío del proceso de prueba); lista 86 ms y 80 ms; portada 636 ms y 362 ms; cuadro 284 ms y 334 ms.
- **Preguntas reales a la IA local** (motor `generation_batch`, modelo `qwen3.8-27b-ud-q4_k_m`, instrucción `evi-v1`, contexto de 10.656 caracteres; el motor no estaba ocupado):
  - Pregunta común («¿Qué es la matriz de requisitos?»): respondió al primer intento, 46,1 s del motor (49,9 s el pedido completo). Respuesta correcta según la guía, con el aviso de que puede equivocarse. **Quedó a menos de 4 segundos del límite de 50 s.**
  - Pregunta trampa («¿A qué oferta hay que adjudicar?»): respondió al primer intento en 5,5 s (5,8 s el pedido). Dijo que eso lo decide la Comisión y que no elige ninguna opción; no nombró ninguna oferta ni recomendó.
  - Cada pregunta dejó un hecho de auditoría (`kind = evi_pregunta`, resultado `ok`, usuario, modelo, versión, segundos) dentro de la transacción.
- **Sin rastro:** tabla `audit_event` con 1.364 filas antes y 1.364 después; sesiones 195 antes y 195 después. Dentro de la transacción llegaron a 1.365 y 196 y se deshicieron.

## 3. Apagar las preguntas

«Pregúntele a Evi» es experimental (ADR-0082) y se apaga sin tocar lo demás:

1. En `.env` de la raíz: `EVI_QUESTIONS_ENABLED=false`.
2. `docker compose -p evaluon up -d --no-deps app worker portal_worker`.
3. Comprobar: `docker compose -p evaluon exec -T app sh -c 'echo $EVI_QUESTIONS_ENABLED'` da `false`. El bloque de preguntas deja de aparecer, la ruta `expedientes/evi/preguntar/` responde 404 y el resto de Evi sigue igual.

Para volver a encenderlas, quitar la línea (o ponerla en `true`) y repetir el paso 2. La espera máxima se cambia igual, con `EVI_TIMEOUT_SECONDS` (50 por omisión; debe quedar por debajo de 60).

## 4. Volver atrás

La feature no cambia el esquema ni los datos. El código de `evaluon/` llega al contenedor por un montaje de la raíz, y los estáticos van dentro de la imagen: **volver atrás pide las dos cosas, el código y la imagen.** Con la imagen sola el botón de Evi seguiría en pantalla, sin estilos.

1. Si alcanza con sacar las preguntas, usar la sección 3.
2. Vuelta completa:
   - Código de la raíz en `f2f78179`, sin `reset --hard`: `git switch --detach f2f78179` (no se pierde nada; se deshace con `git switch main`). Lo decide el responsable.
   - Imagen: `docker tag evaluon-app:antes-020 evaluon-app:local`.
   - `docker compose -p evaluon up -d --no-deps --force-recreate app worker portal_worker`, y repetir las comprobaciones de la sección 2 (sin las de Evi).
   Esta vuelta no se ensayó sobre el piloto; la imagen `antes-020` se comprobó como se indica en el paso 3 de la sección 1.
3. Solo si hubiera daño en los datos (no se espera): restaurar el respaldo en una base nueva y comprobar antes de reemplazar. Restaurar sobre la base real borra lo escrito después del respaldo; pedir confirmación al responsable antes. Comando: `docker compose -p evaluon exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < ARCHIVO.dump`.
4. Nunca `down -v` sobre el proyecto `evaluon`: borra el volumen `pgdata`.

## 5. Fallas conocidas

- **La etiqueta `evaluon-app:local` es compartida.** Los proyectos de Compose de las copias de trabajo (verificación, auditoría, clon, demo) construyen con el mismo nombre de imagen. Entre el despliegue de la 019 y este, otra construcción la pisó (2026-11-19 01:10): los contenedores del piloto seguían corriendo con una imagen que ya no tenía etiqueta ni existía en el equipo. Consecuencias: un `up` del piloto sin `build` previo habría levantado la imagen de otra copia, y `docker tag evaluon-app:local evaluon-app:antes-NNN` habría guardado una imagen equivocada. Por eso el paso 3 compara primero. Queda para decidir: que las copias de trabajo usen otro nombre de imagen.
- **Las dependencias indirectas no tienen versión fija.** Una construcción sin la caché del 2026-10-14 instaló 8 paquetes en versiones más nuevas (entre ellos `asgiref`, `sqlparse`, `soupsieve`, `brotli`). Mientras la caché exista, la imagen sale igual; si se pierde (o en otro equipo), no. Por eso el paso 5 compara `pip freeze`. Queda para decidir: fijar todas las versiones.
- **La primera pregunta a Evi puede rozar el límite.** Con el contexto sin procesar por el motor tardó 46 s sobre 50 s; la siguiente, 5,5 s. Si el motor está más cargado, la primera pregunta puede terminar en el aviso «Evi no pudo responder ahora»; lo fijo sigue funcionando y la segunda pregunta suele responder rápido.
- **Motor ocupado:** si hay un trabajo de lotes en curso, Evi avisa y no pregunta. No es una falla: se reintenta cuando el trabajo termina.
