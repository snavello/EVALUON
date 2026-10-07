# Runbook 004 · Evaluación asistida de ofertas

Para llegar al sistema funcionando desde un equipo limpio y operar la evaluación asistida (P5). Insumos: `specs/004-evaluacion-asistida/entorno.md` (memoria, contexto, tamaños), ADR-0037 a ADR-0044. Para lo anterior rigen `specs/003-pliego-matriz/runbook.md`, `specs/008-ofertas-ficha/runbook.md` y `specs/012-portal-compras/runbook.md`.

Los comandos se corren desde la raíz del repositorio (Git Bash o PowerShell). `docker compose` usa el proyecto `evaluon`; para pruebas se agrega `-p nombre`. En Git Bash, anteponer `MSYS_NO_PATHCONV=1` a los comandos con rutas que empiezan con `/`.

Estado: aprobado y aplicado · Fecha: 2026-10-07 · Aprobó: responsable del proyecto

## 1. Requisitos

**Equipo.** Docker Desktop con WSL2, GPU NVIDIA (RTX 5090 Laptop, 24.463 MiB; ver `specs/001-normativa/entorno.md`) y Git. Solo `portal_worker` sale a internet (P4); la 004 no agrega ningún servicio, imagen ni salida.

**Modelos** (`models/`, fuera del repositorio; `bash scripts/fetch_models.sh` los baja y verifica contra `scripts/models.sha256`; es el único paso con internet). La lista normal trae cuatro archivos más el proyector de visión:

| Archivo | Para qué | SHA-256 (inicio) |
|---|---|---|
| `gemma-4-12b-it-qat-q4_0.gguf` | `generation` y `generation_batch` (consultas, matriz, ficha, evaluación) | `93567e57…8b` |
| `mmproj-gemma-4-12b-it-qat-q4_0.gguf` (175.115.616 bytes) | proyector de imagen del 12B: lectura con visión (ADR-0041); `--mmproj` de `generation_batch` | `cb018338…260da7` |
| `bge-m3-FP16.gguf` | `embeddings` | `daec91ff…062c` |
| `bge-reranker-v2-m3-FP16.gguf` | `reranker` | `5df93be1…1b88` |

Las huellas completas están en `scripts/models.sha256` y en `docker-compose.yml`; la aplicación registra la del modelo y la del proyector con cada evaluación (P6). Los dos archivos del 26B-A4B (`gemma-4-26B_q4_0-it.gguf`, `gemma-4-26B-it-mmproj.gguf`) **no se necesitan**: el ADR-0044 mantiene el 12B; solo se bajan con `bash scripts/fetch_models.sh --modelo-grande` para la comparación (ADR-0042), que hoy no entra junto con `generation` en la memoria de video.

**Memoria de video** (medida en `entorno.md`): el entorno de uso, con el motor de lotes a 32.768 y el proyector, ocupa unos 18.600 MiB de 24.463 (5.800 libres; T-159). Con pedidos de unos 20.000 tokens e imagen, máximo 18.653 MiB. Hace falta que no haya otra carga en la GPU mientras se evalúa o se mide (de a una; ADR-0025).

**Contexto del motor de lotes: 32.768** (`GENERATION_BATCH_CTX_SIZE`, ADR-0037). `generation` sigue en 16.384. `GENERATION_CACHE_RAM=2048` (por omisión) evita que WSL2 mate un motor por falta de memoria. Los parámetros `ASSESSMENT_*` son constantes de `evaluon/settings.py` (no variables de entorno); cambiarlos exige volver a medir (P7).

Comprobar el contexto real con el que arrancó cada motor:

```
docker compose exec -T generation_batch curl -s localhost:8080/props    # buscar "n_ctx":32768 y "vision":true
docker compose exec -T generation curl -s localhost:8080/props          # "n_ctx":16384
```

Memoria: `nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits` en el equipo (el contenedor `app` no trae `nvidia-smi`).

## 2. Levantar desde cero

1. Clonar el repositorio. `bash scripts/fetch_models.sh` (una vez por equipo, o copiar `models/` de otro equipo; después correr el mismo script para verificar huellas).
2. `cp .env.example .env` y completar `POSTGRES_PASSWORD` y `DJANGO_SECRET_KEY` con valores propios, largos y al azar (`openssl rand -hex 32`). `.env` no se sube. Las demás claves tienen valor por omisión en `.env.example`.
3. `docker compose build app` y `docker compose up -d`. Con la base vacía, `migrate` aplica todas las migraciones (incluidas las de la 004); después arrancan `app`, `worker` y `portal_worker`. Los motores de IA tardan hasta dos minutos en quedar sanos.
4. Comprobar:
   - `docker compose ps`: `db`, `generation`, `generation_batch`, `embeddings`, `reranker` y `app` "healthy"; `worker` y `portal_worker` "Up" (sin estado de salud); `migrate` termina solo.
   - `n_ctx` de los dos motores (sección 1).
   - `docker network inspect evaluon_egress --format '{{range .Containers}}{{.Name}} {{end}}'` lista solo a `portal_worker` (P4).
   - `docker compose run --rm app pytest tests/portal/test_network.py tests/test_compose_env.py tests/tenders/test_generation_batch.py` pasa.
5. Usuario de la Comisión (clave pedida dos veces): `docker compose run --rm app python manage.py crear_usuario NOMBRE --rol lectura-escritura --rol-comision evaluador`.
6. Pantalla: `http://127.0.0.1:8000/` (o `APP_PORT`).

Parar: `docker compose stop`. Los datos viven en el volumen `pgdata`: no usar `down -v` salvo en un proyecto de pruebas, porque borra la base.

## 3. Migrar la base real (con respaldo previo)

Migraciones de la 004:

| App | Migración | Qué hace |
|---|---|---|
| `audit` | `0007_evaluacion` | Tipos de hecho `eval_request`, `eval_build`, `eval_decision`, `eval_answer` |
| `tenders` | `0007_evaluacion` | Tipo de pedido `evaluate_offers` |
| `assessment` | `0001_initial` | Las ocho tablas de la evaluación |
| `assessment` | `0002_triggers` | Solo inserción (UPDATE y DELETE rechazados) en las ocho |
| `offers` | `0004_passage_origin_vision` | El origen de un pasaje suma `vision` (cambia una restricción; no toca datos) |
| `assessment` | `0003_resultados_decisiones_literales` | Tabla `assessment_technical_ok`; columnas `opinion` y `facts` en resultados, `portal_item` y `portal_kind` en citas; motivos y tipo de cita nuevos (reemplaza restricciones) |
| `assessment` | `0004_triggers` | Solo inserción en `assessment_technical_ok` |

**Estado de la base real el 2026-10-07** (leído, sin tocar): ya tiene aplicadas `audit.0007`, `tenders.0007`, `offers.0004` y `assessment.0001` y `0002` (se usaron en las mediciones de T-148 a T-173). Lo **pendiente** es `assessment.0003` y `assessment.0004`. Las demás tablas solo se agregan o se relajan restricciones: no se tocan datos existentes.

Pasos (con datos en la base, `migrate` del arranque no migra: comprueba y, si hay pendientes, falla y `app` no arranca; es lo esperado):

1. Que no haya medición ni pedido en curso: `docker top evaluon-app-1 | grep medir` y `docker top evaluon-worker-1 | grep medir` vacíos; la pantalla sin pedidos "en curso".
2. `docker compose stop app worker portal_worker`. Dejar `db` arriba.
3. Respaldo (`backups/` está ignorada por git; si no existe, `mkdir backups`):
   `docker compose exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > backups/evaluon-AAAA-MM-DD-previo-004.dump`
   Comprobar con `ls -l backups` que no esté vacío. Contiene datos de casos: queda solo en el equipo. El respaldo es de la base `evaluon`; las bases de medición `evaluon_t161` a `evaluon_t176` y `test_evaluon` del mismo servidor no entran y no se necesitan.
4. Ver qué se aplicará: `docker compose run --rm --no-deps app python manage.py showmigrations audit tenders offers portal assessment`. Las pendientes no llevan `[X]`.
5. Aplicar: `docker compose run --rm --no-deps app python manage.py migrate`.
6. Comprobar: `docker compose run --rm --no-deps app python manage.py migrate --check` (salida 0) y que `showmigrations assessment` muestre las cuatro con `[X]`.
7. Si el contexto o el proyector del motor de lotes no son los de la sección 1: `docker compose up -d generation_batch`. Después `docker compose up -d` (recrea `app` y `worker` si cambió la configuración).

## 4. Evaluar un procedimiento

Requisitos: el procedimiento con su pliego leído y su matriz **validada** (003), y sus ofertas leídas (008). La evaluación usa el motor de lotes, el proyector de imagen y `embeddings`/`reranker`; de a una por vez.

1. (Opcional) tamaños y grupos de lectura antes de pedir: `docker compose run --rm app python manage.py medir_tamanos --usuario NOMBRE --procedimiento NUMERO --corridas evals/corridas-tamanos`.
2. Si la matriz validada es anterior a T-156 (sin las cláusulas completas de cada renglón técnico), crear una versión nueva: `docker compose run --rm app python manage.py rehacer_matriz --usuario NOMBRE --procedimiento NUMERO`. La versión anterior no se toca.
3. Evaluar:
   - Por pantalla: `/evaluacion/procedimiento/ID/`, botón «Evaluar todas las ofertas». Queda como pedido `evaluate_offers` para el `worker`, que lo corre.
   - Por línea de comandos (corre acá mismo, sin esperar al `worker`; con el `worker` ocioso): `docker compose run --rm app python manage.py evaluar_ofertas --usuario NOMBRE --procedimiento NUMERO [--oferta N]... [--requisito N]...`
   La evaluación lee con visión las páginas dudosas antes de armar los documentos (ADR-0041). Por oferta, hasta unos 30 minutos (plan, enmienda). Cada resultado guarda sus citas, el modelo, la huella y las versiones de reglas e instrucciones (P6).
4. Ver resultados: matriz de la pantalla; cada par muestra su cita literal ubicada y, si vino de una página leída por visión, la imagen junto a la cita. Un resultado "cumple" o "no cumple" sin cita no existe: queda "no determinado" con su motivo. La Comisión decide aparte; las decisiones no cambian los resultados (inmutables, ADR-0039).
5. Preguntas a la Comisión, respuestas y subsanación: por pantalla (`/evaluacion/procedimiento/ID/preguntas/`, y desde cada resultado).
6. (Manual) lectura con visión de una oferta: `docker compose run --rm app python manage.py leer_con_vision --usuario NOMBRE --procedimiento NUMERO --oferta N`. Una página ya intentada no se repite.

## 5. Ok del informe técnico

Rol evaluador, por pantalla, en la matriz del procedimiento (REQ-061): en cada oferta, «Dar el ok del informe técnico» (todo el informe o los renglones marcados) y «Retirar el ok» (pide nota). Cada ok queda como hecho `eval_decision` y fila de solo inserción en `assessment_technical_ok`; no se edita. El sistema no da el ok por la Comisión (P3).

## 6. Cargar el Portal

Es la fuente de cotización, garantías, total y CUIT (REQ-062). Rige la sección 4 de `specs/012-portal-compras/runbook.md`: en `/importar/` pegar el enlace público del proceso, «Explorar», abrir el proceso, elegir lo que se acepta y «Aprobar lo elegido». `portal_worker` debe estar arriba (única salida a internet). Para emparejar los ítems de la propuesta con las ofertas ya cargadas (por nombre del oferente) se aprueba sin crear ofertas nuevas; los documentos del Portal quedan como archivo, no entran a la lectura de la oferta. Cortar la conexión: `docker compose stop portal_worker` (la evaluación sigue funcionando; las filas que necesitan el Portal quedan "en el Portal" o "falta coincidencia" sin cita inventada).

## 7. Medir (`medir_evaluacion`)

Usa la GPU: de a una, sin otra medición ni pedido en curso (`docker top evaluon-app-1 | grep medir` y lo mismo en `worker`; si devuelve algo, esperar). Rol evaluador; la clave se pide por teclado. Las listas esperadas están en `corpus/casos/` (fuera del repositorio; `app` ve esa carpeta con escritura).

1. **Sin GPU, antes de medir:**
   - `... medir_evaluacion --usuario NOMBRE --procedimiento NUMERO --esperada /app/corpus/casos/caso-00/esperado/dictamen-esperado.yaml --verificar-esperada`: comprueba la huella de cada documento, que cada ancla esté en su página y que cada página no legible lo sea. Debe decir «sin fallas». Usa la lectura de la base, sin el modelo de generación.
   - `... medir_evaluacion --usuario NOMBRE --esperada /app/corpus/casos/caso-00/esperado/dictamen-esperado.yaml --verificar-decisiones`: corre los tests `decision_literal` (uno por decisión del responsable, ADR-0043; 115 en T-176) y comprueba los campos nuevos de la lista. Si un test falla o falta un campo, la medición se rechaza.
   (cada `...` es `docker compose run --rm app python manage.py`.)
2. **Caso chico y público** (arma el caso en la base y lo mide): `docker compose run --rm app python manage.py medir_evaluacion --usuario NOMBRE --caso-chico`. Con `--verificar-esperada` solo comprueba la lista.
3. **Caso real ya cargado** (el umbral de la spec, ADR-0044: más del 80 % de coincidencia, 0 contradicciones, 100 % de citas literales): `... medir_evaluacion --usuario NOMBRE --procedimiento NUMERO --esperada /app/corpus/casos/caso-00/esperado/dictamen-esperado.yaml --fichas /app/corpus/casos/caso-00/esperado/fichas-esperadas.yaml --corridas /app/corpus/casos/caso-00/esperado/corridas --commit HASH` (`--commit` hace falta: el contenedor no tiene `.git`). En T-176 la corrida completa tardó 970 s.
4. Si se mide una base que ya intentó la visión, usar una base nueva para comparar con T-176 (la visión no repite páginas intentadas).

La salida informa coincidencias por tipo de par, contradicciones, citas literales y qué bloquea la aceptación; la corrida queda en la carpeta indicada, con solo identificadores y cuentas en lo que se publica (P4).

## 8. Comprobaciones de funcionamiento después del despliegue (humo)

Sin GPU y sin tocar datos de casos, salvo el último punto:

1. `docker compose ps` como en la sección 2; `n_ctx` 32.768 en `generation_batch`, 16.384 en `generation`, `"vision":true` en el primero.
2. `migrate --check` en 0 y `showmigrations assessment` con `0001` a `0004` aplicadas.
3. `docker compose run --rm app pytest tests/portal/test_network.py tests/test_compose_env.py tests/tenders/test_generation_batch.py`.
4. `medir_evaluacion --verificar-decisiones` (sección 7) en verde.
5. Abrir `/evaluacion/procedimiento/ID/` de un procedimiento ya evaluado: se ven los resultados anteriores con sus citas, sin errores.
6. Caso de punta a punta (con la GPU libre, antes de usar el sistema con un caso nuevo): `medir_evaluacion --usuario NOMBRE --caso-chico`; pasa si informa «Bloquea la aceptación: nada».

## 9. Volver atrás

1. **Dejar de usar la feature, conservando los datos:** `git checkout` del commit previo, `docker compose build app`, `docker compose up -d`. Las tablas de la evaluación quedan sin uso. Si el código anterior no arranca por las migraciones ya aplicadas, usar la 2 o la 3.
2. **Restaurar el respaldo.** Se pierde todo lo hecho desde él (evaluaciones, oks, decisiones, registro). Pedir confirmación: `dropdb` borra la base vigente.
   ```
   docker compose stop app worker portal_worker
   docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --force "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
   docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --exit-on-error' < backups/evaluon-AAAA-MM-DD-previo-004.dump
   docker compose up -d
   ```
   (Probado en el runbook 008: mismo procedimiento.)
3. **Deshacer solo las migraciones nuevas** (`assessment.0003` y `0004`): `docker compose run --rm --no-deps app python manage.py migrate assessment 0002`. Solo es posible mientras la base no tenga resultados con motivos, citas del Portal u oks nuevos: la reversa de `0003` vuelve a poner las restricciones anteriores y falla si hay filas que no las cumplen; y como las tablas son de solo inserción, esas filas no se pueden borrar. Si falla, usar la 2. Borra la tabla `assessment_technical_ok` con sus oks.
   Más atrás (borra tablas con su contenido; solo con respaldo y confirmación): `migrate assessment zero`, `migrate tenders 0006`, `migrate audit 0006`; `offers.0004` se deshace con `migrate offers 0003` y falla si hay pasajes leídos por visión.
4. **Volver al contexto anterior del motor de lotes** (ADR-0037): `GENERATION_BATCH_CTX_SIZE=16384` en `.env`, `docker compose up -d generation_batch worker app` y bajar `ASSESSMENT_GROUP_TOKENS` a 8.000 (cambio de código: exige medir).
5. **Cortar el Portal:** `docker compose stop portal_worker`.

## 10. Problemas conocidos

Los de "Revisión con el primer producto" de `tasks.md` y la aceptación (ADR-0044: 42 de 49, 85,7 %; 0 contradicciones):

- **Manuscritos (el pagaré).** La lectura con visión del 12B transcribe lo manuscrito con valores plausibles y distintos del original (monto en letras, fecha, beneficiario, concepto) sin marcar `[ilegible]`. Impacto: los pares del pagaré no pueden quedar en "cumple" sin respaldo. Qué hacer: la Comisión mira la imagen junto a la cita (P3) y el original; no confiar en cifras de páginas leídas por visión sin revisarlas a mano. El 26B-A4B lo lee casi sin errores, pero hoy no entra en la memoria junto con `generation` (requiere apagar la consulta de normativa o rehacer el reparto; ADR-0002, ADR-0044).
- **Tablas por visión.** Transcriptas como «celda | celda»: las citas de encabezado y valor pueden no ubicarse (V-2 de T-161); el par queda "no determinado" o con cita de fila completa.
- **Resultado que cambia entre corridas.** M-051 de la oferta 1 puede salir "cumple" o "no cumple" (V-3 de T-161): seguirlo; la evaluación no se promedia, cada corrida es un registro distinto.
- **Transcripción por visión cortada por repetición.** Se descarta entera (V-1, mitigado en T-177 con texto plano y marcador de fin): la página queda sin leer y el par "no se pudo leer".
- **M-039 (cotización por renglón genérica)** sin cita del Portal en las tres ofertas del caso-00: falta la regla para esa forma de requisito. **M-041 (cantidad por renglón):** `falta_coincidencia` falso y citas de cotización de más; no afecta la coincidencia ni crea contradicciones.
- **`generation` es necesario para la evaluación.** Cuenta tokens con `generation` aunque use el motor de lotes (T-162): si `generation` está apagado, la evaluación falla. No apagarlo.
- **Falta un test** de que `assessment:vision_page` se niegue a servir una página citada que no fue leída por visión (T-160). Impacto bajo (mismo par y mismo rol).
- **Fragmentos de la ficha:** 17 de 21 (81 %) contra el 90 % informativo del plan; fuera del umbral de aceptación.
- **Oferta grande:** la del caso-00 con más páginas queda a 471 tokens del presupuesto de grupo (20.000): una oferta más grande se lee en dos pasadas (hasta `ASSESSMENT_MAX_GROUPS = 4`).
- **`migrate` falla al arrancar con "hay migraciones pendientes":** esperado con datos en la base; seguir la sección 3.
- **Un motor desaparece sin error en el registro:** falta de memoria de WSL2; verificar `GENERATION_CACHE_RAM=2048` (T-090).
- **Pedidos "en curso" tras reiniciar:** el `worker` los pasa a fallidos "interrumpido" al arrancar; se vuelven a pedir desde la pantalla.
- **Una evaluación falla con "sin manejador para el tipo de pedido":** el `worker` corre una imagen o un código anterior a T-150; `docker compose up -d --force-recreate worker` tras actualizar el código.
- **Dos mediciones o una medición y un pedido a la vez:** distorsionan tiempos y pueden agotar la memoria de video; esperar a que termine la anterior.
- **Bases de medición en el servidor** (`evaluon_t161` a `evaluon_t176`, `test_evaluon`): ocupan espacio; quitarlas es una decisión del responsable (se pierden los resultados de esas mediciones; la corrida de cada una está en `corpus/casos/`).

## 11. Prueba del runbook (2026-10-07)

Proyecto aparte `evaluon-dep004` (imagen `evaluon-app:dep004` con un archivo de compose adicional, fuera del repositorio, que solo cambia la etiqueta de la imagen y el puerto; base y claves propias; solo `db` y `app --no-deps`, sin motores de IA ni GPU). No se tocó el proyecto `evaluon` ni su base; los contenedores `evaluon-*` no se reiniciaron. Al final, `down -v` y se borró la imagen de prueba. El código fue el de `main` (`eed328d`).

Probado, con resultado correcto:

- construir la imagen y `migrate` en base vacía (todas las migraciones);
- reproducir el estado de la base real (`migrate assessment 0002`: `0003` y `0004` sin aplicar) y comprobar que `migrate` del arranque se niega y muestra el procedimiento;
- `pg_dump -Fc` (343 KB), `showmigrations` (solo `assessment.0003` y `0004` pendientes), `migrate` (se aplican esas dos) y `migrate --check` en 0;
- reversa de `assessment.0003` y `0004` (`migrate assessment 0002`) sobre base sin evaluaciones;
- `pytest`: 115 tests `decision_literal`; `tests/test_compose_env.py`, `tests/portal/test_network.py` y `tests/tenders/test_generation_batch.py`: 30 pasan;
- solo lectura sobre el entorno real: `generation_batch` con `n_ctx` 32.768, `vision: true` y alias del 12B; `generation` con 16.384; todos los contenedores sanos; migraciones de la base real como en la sección 3.

No probado: la restauración con `pg_restore` (la prueba con `dropdb` fue bloqueada por la herramienta de seguridad del entorno; es el mismo procedimiento probado en el runbook 008); evaluar y medir con la GPU (no se la usó a pedido; los números de T-176 y T-159 respaldan los de este documento); la reversa de `assessment.0003` con datos (por diseño no es posible, ver 9.3); el ok del informe técnico y la carga del Portal por pantalla (las cubren T-168, T-172 y T-176).
