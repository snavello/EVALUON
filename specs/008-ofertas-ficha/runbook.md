# Runbook 008 · Ofertas y ficha por oferta

Para llegar al sistema funcionando desde un equipo limpio y operar la feature 008 (P5). Servicios, variables, migraciones y requisitos: `specs/008-ofertas-ficha/entorno.md`. Los comandos se corren desde la raíz del repositorio (Git Bash o PowerShell). `docker compose` usa el proyecto `evaluon` del archivo; para pruebas se agrega `-p nombre`.

## 1. Levantar desde cero

1. Requisitos: Docker Desktop con WSL2, GPU NVIDIA (ver `specs/001-normativa/entorno.md`) y Git.
2. Clonar el repositorio y entrar a la carpeta.
3. Modelos (único paso con internet; una vez por equipo, o copiar `models/` de otro equipo): `bash scripts/fetch_models.sh`. Verifica la huella de cada archivo contra `scripts/models.sha256`.
4. Configuración: `cp .env.example .env` y completar `POSTGRES_PASSWORD` y `DJANGO_SECRET_KEY` con valores propios, largos y al azar (por ejemplo, `openssl rand -hex 32`). `.env` no se sube.
5. Construir y levantar: `docker compose build app` y `docker compose up -d`. Con la base vacía, el servicio `migrate` aplica todas las migraciones; después arrancan `app` y `worker`. Los motores de IA tardan hasta dos minutos en quedar sanos.
6. Comprobar: `docker compose ps` (todos "healthy"; `worker` y `portal_worker` no tienen estado de salud y `migrate` termina solo) y abrir `http://127.0.0.1:8000/` (o el `APP_PORT` del `.env`).
7. Crear un usuario de la Comisión (la clave se pide dos veces, sin mostrarla):
   `docker compose run --rm app python manage.py crear_usuario NOMBRE --rol lectura-escritura --rol-comision operador`
   (el rol `evaluador` incluye al de operador).

Parar: `docker compose stop`. Volver a arrancar: `docker compose up -d`. Los datos viven en el volumen `pgdata`: no usar `down -v` salvo en un proyecto de pruebas, porque borra la base.

## 2. Aplicar las migraciones sobre una base existente (con respaldo)

Con datos en la base, `migrate` no migra solo: comprueba y, si hay pendientes, falla y `app` no arranca. Es lo esperado.

1. Confirmar que no hay una medición ni un pedido en curso: `docker top evaluon-app-1 | grep medir` no debe devolver nada, y la pantalla no debe mostrar pedidos "en curso".
2. Detener lo que escribe: `docker compose stop app worker portal_worker`.
3. Respaldar (`backups/` está ignorada por git; si no existe, `mkdir backups`):
   `docker compose exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > backups/evaluon-AAAA-MM-DD-previo-008.dump`
   Comprobar con `ls -l backups` que el archivo no esté vacío. El respaldo contiene datos de casos: queda solo en el equipo.
4. Ver qué se aplicará: `docker compose run --rm --no-deps app python manage.py showmigrations audit tenders offers portal`. Las pendientes no llevan `[X]`.
5. Aplicar: `docker compose run --rm --no-deps app python manage.py migrate`. Desde una base al día de la 003 se aplican `audit.0005`, `audit.0006`, `tenders.0005`, `offers.0001` a `0003`, `tenders.0006` y `portal.0001` y `0002` (las de `audit.0006`, `tenders.0006` y `portal` son de la 012).
6. Comprobar: `docker compose run --rm --no-deps app python manage.py migrate --check` (salida 0).
7. Levantar todo: `docker compose up -d`.

## 3. Cargar una oferta, armar la ficha y verla

Requisito: el procedimiento existe, con su pliego leído y su matriz validada (feature 003). Los archivos de la oferta tienen que estar en `corpus/casos/`, la única carpeta de casos que ve el contenedor; no se sube a GitHub.

1. Cargar (la clave se pide por teclado):
   `docker compose run --rm app python manage.py cargar_oferta --usuario NOMBRE --procedimiento NUMERO --oferente "Nombre del oferente" corpus/casos/CASO/oferta1/doc1.pdf corpus/casos/CASO/oferta1/doc2.pdf`
   Imprime el número y el id de la oferta. Si el oferente ya tiene oferta en el procedimiento, se le suman los documentos; un archivo repetido se avisa y se omite. Cada documento queda en espera de lectura para el `worker`.
2. Esperar la lectura (OCR, pasajes, vectores): `docker compose logs -f worker` o la pantalla de la oferta.
3. Ver la oferta en `http://127.0.0.1:8000/ofertas/ID/` (o desde la pantalla del procedimiento). Muestra los documentos, su tipo, el estado de lectura y las listas de páginas no leídas y de baja confianza.
4. Armar la ficha: botón "Armar ficha" de esa pantalla. Queda como pedido para el `worker`, de a uno; de 2 a 5 minutos por oferta con la GPU libre. Al terminar aparece el aviso de fin.
5. Ver la ficha (`/ofertas/fichas/ID/`). Cada fila del pliego muestra los fragmentos hallados (texto literal, documento y página) o "no se encontró" o "no se pudo leer". La ficha no dice si la oferta cumple: lo decide la Comisión (P3). Para armar otra con los mismos datos, "Armar una ficha nueva" (las fichas anteriores no se alteran).

## 4. Mantenimiento

Los comandos exigen rol de operador y piden la clave. Respaldar antes (sección 2, paso 3).

- Volver a clasificar el tipo de los documentos ya cargados:
  `docker compose run --rm app python manage.py reclasificar_documentos --usuario NOMBRE --procedimiento NUMERO`
- Rearmar los pasajes de los documentos ya leídos, sin repetir el OCR:
  `docker compose run --rm app python manage.py rearmar_pasajes --usuario NOMBRE --procedimiento NUMERO`
  Las fichas ya armadas no cambian (son inmutables); para una ficha con los pasajes nuevos, armar otra.

## 5. Medir (`medir_fichas`)

Usa la GPU: de a una, sin otra medición ni pedido del `worker` (ADR-0025). Antes: `docker top evaluon-app-1 | grep medir`; si devuelve algo, esperar.

- Caso chico y público (arma el caso en la base y lo mide):
  `docker compose run --rm app python manage.py medir_fichas --usuario NOMBRE --caso-chico`
- Si falla al guardar la corrida (carpeta de solo lectura), agregar `--corridas evals/corridas-fichas`.
- Solo comprobar la lista de fragmentos esperados contra la lectura, sin usar el modelo de generación (la lectura del caso sí usa embeddings):
  `docker compose run --rm app python manage.py medir_fichas --usuario NOMBRE --caso-chico --verificar-esperada`
- Un caso real ya cargado: `--procedimiento NUMERO --esperada corpus/casos/CASO/esperado/fichas-esperadas.yaml --commit HASH` (`--commit` hace falta: el contenedor no tiene `.git`).
- La corrida se guarda en `corridas/`, junto a la lista (o en `--corridas`). La salida informa fragmentos encontrados, falsos hallazgos, páginas sin texto ni lista, renglones "no se pudo leer" y qué bloquea la aceptación.

## 6. Volver atrás

Según el caso:

1. **Dejar de usar la feature, conservando los datos**: volver el código a la versión anterior (`git checkout` del commit previo), `docker compose build app` y `docker compose up -d`. Las tablas de ofertas quedan sin uso. Si el código anterior no arranca por las migraciones ya aplicadas, usar la opción 2.
2. **Restaurar la base al estado previo a la migración.** Se pierde todo lo hecho desde el respaldo (ofertas, fichas y registro posterior). Pedir confirmación antes: `dropdb` borra la base vigente.
   ```
   docker compose stop app worker portal_worker
   docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --force "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
   docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --exit-on-error' < backups/evaluon-AAAA-MM-DD-previo-008.dump
   docker compose up -d
   ```
3. **Deshacer solo las migraciones.** Borra las tablas de ofertas y fichas con su contenido y arrastra las del Portal. Solo con respaldo hecho y confirmación:
   `docker compose run --rm --no-deps app python manage.py migrate offers zero`, luego `migrate tenders 0004` y `migrate audit 0004`.

## 7. Problemas conocidos

- **Fotos de tablas dudosas.** Una foto de celular con una tabla puede dar OCR de baja calidad: las páginas figuran como "baja confianza" o "no leídas" en la pantalla de la oferta y las filas de renglón dicen "no se pudo leer" (nunca "no cotizado"). No es una falla del sistema. La Comisión mira el documento original (enlace "original" de la pantalla); se reintenta con preparación de imagen solo en páginas dudosas (ADR-0028). Qué hacer: pedir el PDF digital al oferente o revisar esas páginas a mano.
- **La ficha encuentra en torno al 55 % de los fragmentos esperados** (25 de 55 en la última medición, 45,5 % bruto; en torno al 55 % descontando defectos de la lista), no el 90 % de la meta original. Está decidido (ADR-0035, responsable): bloquean el texto literal y que ningún hallazgo se presente sin respaldo; el 90 % pasa a ser meta de la feature 004. Se informan además los falsos hallazgos (10 en la última medición). "No se encontró" no significa que la oferta no lo tenga: la Comisión revisa el documento.
- **`migrate` falla al arrancar con "hay migraciones pendientes".** Es lo esperado con datos en la base: seguir la sección 2.
- **`embeddings: no responde ... name resolution`** al cargar o leer una oferta: los motores de IA no están arriba (`docker compose ps`). Con `--no-deps` no se levantan.
- **Un motor de generación desaparece sin error en el registro:** falta de memoria de WSL2; verificar `GENERATION_CACHE_RAM=2048` (T-090).
- **Pedidos "en curso" tras reiniciar:** el `worker` los pasa a fallidos "interrumpido" al arrancar; se vuelven a pedir desde la pantalla.
- **Clave por teclado en scripts:** los comandos leen la clave con `getpass`; sin terminal (`-T`) la leen de la entrada estándar y avisan que puede mostrarse. En el equipo real, usar terminal interactiva.

## 8. Prueba del runbook (2026-10-05)

Proyecto de pruebas `evaluon-dep008` (imagen `evaluon-app:dep008`, puerto 18008, claves propias en `.env`, base propia). Para no cargar la GPU con otros motores, `app` y `worker` se sumaron a la red `evaluon_internal` del proyecto principal (archivo de compose adicional, fuera del repositorio) y se apuntaron `GENERATION_BATCH_URL`, `EMBEDDINGS_URL` y `RERANKER_URL` a esos contenedores, con `POSTGRES_HOST` apuntando a la base de prueba. No se reinició nada del proyecto principal. Antes de cada corrida se comprobó que no hubiera una medición en curso. Al final, `down -v`.

Probado, todo con resultado correcto:

- construir la imagen, levantar `db`, `migrate` (43 migraciones en base vacía), alta de usuario y `app` sana;
- sección 2 completa: `migrate` se niega con datos, `pg_dump`, `migrate`, `migrate --check`, y la reversa y la restauración de la sección 6 (opciones 2 y 3);
- `medir_fichas --caso-chico --verificar-esperada`: "Documentos 5, anclas 7, páginas no legibles 1: sin fallas";
- `medir_fichas --caso-chico`: 7 de 7 fragmentos, texto literal 9 de 9, síntesis sin juicio 8 de 8, renglones 3 de 3, falsos hallazgos 0, "Bloquea la aceptación: nada";
- `cargar_oferta` con dos PDF del caso chico (oferente B), lectura por el `worker`, botón "Armar ficha" (pedido `build_sheet` terminado) y ficha en `/ofertas/fichas/ID/` con sus filas "no se encontró" y los hallazgos;
- `reclasificar_documentos` (0 cambios) y `rearmar_pasajes` (0 documentos con lectura nueva) sobre el caso chico.

Hallazgos de la prueba, a devolver al desarrollo (no se tocó código):

- `medir_fichas --caso-chico` sin `--corridas` falla al guardar la corrida: la carpeta por omisión (`tests/offers/data/caso-chico/corridas`) está en un montaje de solo lectura. Con `--corridas evals/corridas-fichas` (carpeta con escritura) funciona. En Git Bash, una ruta que empiece con `/` se convierte a una de Windows: usar la ruta relativa, o anteponer `MSYS_NO_PATHCONV=1`.
- Con `-T` y la clave por la entrada estándar la medición anda, pero escribe la clave en pantalla; solo para pruebas.
