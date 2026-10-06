# Runbook 003 · Procedimiento, pliego final y matriz de cumplimiento

Para llegar al sistema funcionando desde un equipo limpio y operar la feature 003 (P5). Servicios, variables, migraciones y requisitos: `specs/003-pliego-matriz/entorno.md`. Los comandos se corren desde la raíz del repositorio (Git Bash o PowerShell). `docker compose` usa el proyecto `evaluon` del archivo; para pruebas se agrega `-p nombre`. En Git Bash, un argumento que empiece con `/` se convierte a una ruta de Windows: usar rutas relativas o anteponer `MSYS_NO_PATHCONV=1`.

## 1. Levantar desde cero

1. Requisitos: Docker Desktop con WSL2, GPU NVIDIA (ver `specs/001-normativa/entorno.md`) y Git.
2. Clonar el repositorio y entrar a la carpeta.
3. Modelos (único paso con internet; una vez por equipo, o copiar `models/` de otro equipo): `bash scripts/fetch_models.sh`. Verifica la huella de cada archivo contra `scripts/models.sha256`.
4. Configuración: `cp .env.example .env` y completar `POSTGRES_PASSWORD` y `DJANGO_SECRET_KEY` con valores propios, largos y al azar (`openssl rand -hex 32`). `.env` no se sube.
5. Construir y levantar: `docker compose build app` y `docker compose up -d`. Con la base vacía, `migrate` aplica todas las migraciones; después arrancan `app` y `worker`. Los motores de IA tardan hasta dos minutos en quedar sanos.
6. Comprobar: `docker compose ps` (todos "healthy"; `worker` y `portal_worker` no tienen estado de salud y `migrate` termina solo) y abrir `http://127.0.0.1:8000/` (o el `APP_PORT` del `.env`).
7. Crear un usuario de la Comisión (la clave se pide dos veces):
   `docker compose run --rm app python manage.py crear_usuario NOMBRE --rol lectura-escritura --rol-comision evaluador`
   El rol `evaluador` incluye al de `operador`. Solo el evaluador valida la matriz y elige las consecuencias.

Parar: `docker compose stop`. Volver a arrancar: `docker compose up -d`. Los datos viven en el volumen `pgdata`: no usar `down -v` salvo en un proyecto de pruebas, porque borra la base.

## 2. Migraciones de `tenders` y `audit` sobre una base existente (con respaldo)

Con datos en la base, `migrate` no migra solo: comprueba y, si hay pendientes, falla y `app` no arranca. Es lo esperado.

1. Confirmar que no hay una medición ni un pedido en curso: `docker top evaluon-app-1 | grep medir` no debe devolver nada, y la pantalla no debe mostrar pedidos "en curso".
2. Detener lo que escribe: `docker compose stop app worker portal_worker`.
3. Respaldar (`mkdir backups` si no existe; la carpeta está ignorada por git):
   `docker compose exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > backups/evaluon-AAAA-MM-DD-previo-003.dump`
   Comprobar con `ls -l backups` que el archivo no esté vacío. Contiene datos de casos: queda solo en el equipo.
4. Ver qué se aplicará: `docker compose run --rm --no-deps app python manage.py showmigrations accounts audit tenders`. Las pendientes no llevan `[X]`.
5. Aplicar: `docker compose run --rm --no-deps app python manage.py migrate`. Desde el estado previo a la 003 se aplican `accounts.0002`, `audit.0003` a `0006` y `tenders.0001` a `0006` (más `offers` y `portal` si el código ya los trae).
6. Comprobar: `docker compose run --rm --no-deps app python manage.py migrate --check` (salida 0).
7. Levantar todo: `docker compose up -d`.

Nota: `crear_usuario` no anda sobre una base sin `accounts.0002`: dar de alta los usuarios después de migrar.

## 3. Registrar un procedimiento, cargar pliego y circulares, proponer la matriz, revisarla y validarla

Todo se hace en la pantalla `http://127.0.0.1:8000/procedimientos/` con un usuario de la Comisión (evaluador para validar). Los archivos de los casos van en `corpus/casos/`, la única carpeta de casos que ve el contenedor; no se sube a GitHub.

1. **Registrar.** Formulario "Procedimientos": número, tipo, objeto y fecha de autorización (no futura). La pantalla muestra el régimen que corresponde a esa fecha (Disposición 247/2022 o 297/03). Un número repetido se rechaza.
2. **Cargar el pliego.** Dentro del procedimiento: archivo PDF, tipo "Pliego" (también "Anexo" o "Especificaciones técnicas") y título. El `worker` lo lee (segundos) y deja el estado "Leído"; las páginas dudosas o sin texto figuran con su motivo.
3. **Cargar las circulares y respuestas a consultas**, antes de proponer la matriz: tipo "Circular modificatoria", "Circular aclaratoria" o "Respuesta a consulta", con su fecha (obligatoria) y su título. Esperar a que quede leída.
4. **Proponer la matriz.** Botón "Proponer matriz" (proceso único, no se elige nivel). Queda como pedido para el `worker`: menos de un minuto para un pliego de dos páginas, unos 3 minutos para el caso-00 y hasta 40 para uno grande, con la GPU libre. Al terminar aparece la versión 1, borrador, con la leyenda "BORRADOR INCOMPLETO" mientras haya pendientes, y el enlace a la cobertura.
5. **Revisar.** En la página de la matriz: confirmar requisitos (uno por uno o por grupo), corregirlos, quitarlos y restituirlos, agregar los que falten, resolver los pendientes (tramos con tabla o marcadores) y decidir las sugerencias. Los requisitos afectados por una circular muestran el texto original, el vigente y la circular que lo cambia, con su fecha. Las filas descartadas por el sistema están en "Descartadas" y se pueden devolver.
6. **Elegir la consecuencia** de cada requisito (solo el evaluador). Una sugerida del sistema se acepta con su fundamento; las demás exigen escribir el motivo.
7. **Validar** (solo el evaluador). No deja validar con pendientes sin resolver, sugerencias sin decidir o requisitos sin consecuencia elegida. La versión validada queda fija; para cambiarla, "Abrir una versión nueva" copia la validada como borrador.
8. **Imprimir o exportar** la matriz: pantalla de impresión y PDF de la versión.

## 4. Medir (`medir_matriz`)

Usa la GPU: de a una, sin otra medición ni pedido del `worker` (ADR-0025). Antes: `docker top evaluon-app-1 | grep medir`; si devuelve algo, esperar. Rol de operador o evaluador; la clave se pide por teclado. `--commit` hace falta dentro del contenedor (no tiene `.git`). `--corridas` indica dónde guardar si la carpeta por omisión (`corridas/` junto a la carpeta `esperado/` de la lista) no admite escritura.

- Solo comprobar la lista contra la lectura (huellas, anclas, tramos y bloques de circulares), sin modelo de generación:
  `docker compose run --rm app python manage.py medir_matriz --usuario NOMBRE --procedimiento NUMERO --esperada corpus/casos/CASO/esperado/matriz-esperada.yaml --verificar-esperada`
- Medir (corre la propuesta con el canal `eval`; la versión que crea queda descartada y no toca la validada):
  `docker compose run --rm app python manage.py medir_matriz --usuario NOMBRE --procedimiento NUMERO --esperada corpus/casos/CASO/esperado/matriz-esperada.yaml --commit HASH`
  Informa encontrados, cita literal, sobrantes, REQ-031 por fila y qué bloquea la aceptación. Guarda `parametros.json`, `resultados.jsonl`, `resumen.md` (privado) y `resumen-publico.md` en `corridas/AAAAMMDD-HHMMSS-HASH`.
- Reescribir los resúmenes de una corrida ya hecha, sin modelo (vuelve a medir las propuestas que nombra `parametros.json`, que siguen en la base):
  `docker compose run --rm app python manage.py medir_matriz --usuario NOMBRE --procedimiento NUMERO --esperada LISTA --regenerar-resumen corpus/casos/CASO/corridas/AAAAMMDD-HHMMSS-HASH`
- Memoria de video: anotarla desde el equipo, no desde el contenedor (no tiene `nvidia-smi`): `nvidia-smi --query-gpu=memory.used,memory.total --format=csv`, antes y durante la corrida.

### Caso chico inventado (prueba rápida, sin datos de casos)

Pliego de dos páginas y una circular que cambia 16 GB de RAM por 32 GB, todo inventado: `specs/003-pliego-matriz/caso-chico/`.

1. Generar los PDF en `corpus/casos/caso-chico/` (la carpeta debe existir):
   `MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps -e PYTHONPATH=/app -v "$(pwd)/specs/003-pliego-matriz/caso-chico:/app/caso-chico:ro" app python caso-chico/generar.py`
2. Cargarlos como en la sección 3 (procedimiento `CHICO-001`; pliego tipo "Pliego"; circular tipo "Circular modificatoria", fecha 2026-09-10) y proponer la matriz.
3. Preparar la lista con las huellas de los PDF generados (cada generación da archivos con huella distinta):
   `sed "s/__SHA_PLIEGO__/$(sha256sum corpus/casos/caso-chico/pliego-sintetico.pdf | cut -d' ' -f1)/; s/__SHA_CIRCULAR__/$(sha256sum corpus/casos/caso-chico/circular-sintetica-1.pdf | cut -d' ' -f1)/" specs/003-pliego-matriz/caso-chico/matriz-esperada.yaml > corpus/casos/caso-chico/esperado-matriz.yaml`
   Si se generan de nuevo los PDF después de cargarlos, `--verificar-esperada` falla por la huella: es lo esperado.
4. `medir_matriz --usuario NOMBRE --procedimiento CHICO-001 --esperada corpus/casos/caso-chico/esperado-matriz.yaml --corridas corpus/casos/caso-chico/corridas --commit HASH`, antes con `--verificar-esperada`.
5. Resultado de referencia (2026-10-05): 5 requisitos; encontrados 5 de 5; cita literal 10 de 10; sobrantes 0 de 5; REQ-031 con el cambio y su cita 1 de 1 (bloqueante, P3); "Bloquea la aceptación: nada". La propuesta tardó 27 s en la medición y 55 s con la lectura de la circular desde la pantalla.

## 5. Volver atrás

Según el caso:

1. **Dejar de usar la feature, conservando los datos**: volver el código a la versión anterior (`git checkout` del commit previo), `docker compose build app` y `docker compose up -d`. Si el código anterior no arranca por las migraciones ya aplicadas, usar la opción 2.
2. **Restaurar la base al estado previo a la migración.** Se pierde todo lo hecho desde el respaldo (procedimientos, matrices y registro posterior). Pedir confirmación antes: `dropdb` borra la base vigente.
   ```
   docker compose stop app worker portal_worker
   docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --force "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
   docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --exit-on-error' < backups/evaluon-AAAA-MM-DD-previo-003.dump
   docker compose up -d
   ```
3. **Deshacer solo las migraciones.** Borra las tablas de procedimientos y matrices con su contenido (y las de ofertas y Portal, que dependen de ellas). Solo con respaldo hecho y confirmación, en este orden:
   `docker compose run --rm --no-deps app python manage.py migrate offers zero`, luego `migrate tenders zero`, `migrate audit 0002` y `migrate accounts 0001`.
4. **Dejar de usar una matriz**: un borrador se descarta desde su pantalla (queda visible y fijo); una versión validada no se borra: se abre una versión nueva.

## 6. Problemas conocidos

- **Sobrantes informativos (ADR-0024).** La propuesta trae de 60 a 70 % de filas de más en los casos reales (firmes sin pareja en las listas esperadas; el tope del 20 % no se alcanzó). Se decidió cerrar la 003 así y revisarlo con el primer producto: la Comisión descarta a mano lo que no sea requisito (la fila queda en "Descartadas"). Los sobrantes se informan; no bloquean la aceptación.
- **Circulares: marca "A revisión obligatoria" y marcas de más.** Cuando una circular suprime o cambia algo sin una frase explícita, la fila no se da por modificada: queda con la marca "A revisión obligatoria" (P3) y la Comisión decide leyendo ambos textos. La regla de una raíz común (T-147) puede marcar de más; esas marcas se resuelven a mano y son lo previsto, no una falla.
- **No lanzar dos suites o dos mediciones contra la misma base, ni a la vez en la GPU.** Dos corridas simultáneas dan errores de bloqueo de la base (observado por el auditor) o compiten por la memoria de video. Antes de cualquiera: `docker top evaluon-app-1 | grep medir`. Para probar en paralelo, usar otro proyecto (`-p nombre`) con base propia.
- **La memoria de video se anota desde el equipo.** El contenedor `app` no tiene `nvidia-smi` (sección 4). Mejora pendiente: una fuente automática.
- **`migrate` falla al arrancar con "hay migraciones pendientes".** Es lo esperado con datos en la base: seguir la sección 2.
- **`embeddings: no responde ... name resolution`:** los motores de IA no están arriba (`docker compose ps`). Con `--no-deps` no se levantan.
- **Un motor de generación desaparece sin error en el registro:** falta de memoria de WSL2; verificar `GENERATION_CACHE_RAM=2048` (T-090).
- **Pedidos "en curso" tras reiniciar:** el `worker` los pasa a fallidos "interrumpido" al arrancar; se vuelven a pedir desde la pantalla.
- **Guardar la corrida falla por carpeta de solo lectura:** agregar `--corridas` con una carpeta con escritura.
- **Clave por teclado en scripts:** sin terminal (`-T`), `getpass` lee la clave de la entrada estándar y avisa que puede mostrarse; solo para pruebas.

## 7. Prueba del runbook (2026-10-05)

Proyecto de pruebas `evaluon-dep003` (imagen `evaluon-app:dep003`, puerto 18003, claves propias en `.env`, base propia). Para no duplicar la GPU, `app` y `worker` se sumaron a la red `evaluon_internal` del proyecto principal (archivo de compose adicional, fuera del repositorio, sin dependencias de los motores) y `GENERATION_BATCH_URL`, `EMBEDDINGS_URL`, `RERANKER_URL` y `POSTGRES_HOST` se apuntaron a los contenedores correspondientes. No se reinició nada del proyecto principal. Antes de usar la GPU se comprobó que no hubiera una medición en curso. Al final, `down -v`.

Probado, con resultado correcto:

- construir la imagen; levantar `db` y llevarla al estado previo a la 003; respaldo con `pg_dump`; `migrate` (31 migraciones) y `migrate --check`; reversa completa y nuevo `migrate`; restauración desde el respaldo (`dropdb`, `createdb`, `pg_restore`) y nuevo `migrate`;
- `app` sana y respondiendo en el puerto de prueba (302 a la entrada, 200 en la pantalla de ingreso) y `worker` en marcha; red interna del proyecto con `internal: true`;
- alta de usuario con rol de evaluador;
- caso chico: registrar el procedimiento, cargar el pliego y la circular (lectura por el `worker`), proponer la matriz (5 requisitos; el de 16 GB de RAM con la fuente "modifica" de la circular), confirmar, elegir consecuencias, validar (versión validada), pantallas de cobertura e impresión (200);
- `medir_matriz --verificar-esperada` (anclas 3 de 3, tramos técnicos 6 de 6, circulares 1 de 1), `medir_matriz` (cifras en la sección 4) y `--regenerar-resumen`; `--verificar-esperada` con huellas que no coinciden falla, como debe.

Hechos con un script de la prueba y no por la pantalla (usa las mismas rutas y formularios de la aplicación con el cliente de pruebas de Django): registro, cargas, pedido de la matriz, confirmación, consecuencias y validación. El recorrido con navegador no se repitió; lo cubren las pruebas de la feature y la verificación de T-075.

Observación: en el caso chico, el punto 3 de REQ-031 (texto vigente) dio 0 de 1; en ADR-0034 ese punto solo se informa y no bloquea. No se investigó la causa.

No probado: un caso real completo (caso-01, 40 minutos), la suite de tests, la descarga del PDF de la matriz (solo la pantalla de impresión), `fetch_models.sh` ni la construcción en un clon sin `models/`, y `migrate` en base vacía (lo cubrió la 008: 43 migraciones).
