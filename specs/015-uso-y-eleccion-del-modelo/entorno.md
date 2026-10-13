# Entorno de la 015 · Servicio de los modelos candidatos

Estado: preparado por T-242 (2026-10-10). Sin desplegar: el servicio de un candidato se levanta solo en las mediciones de T-243 a T-246, de a una y con la GPU libre.

Este documento dice cómo bajar, levantar y volver atrás de cada candidato del ADR-0056: Qwen3.8-27B (denso) y Qwen3.6-35B-A3B (mezcla de expertos). El compose base (`docker-compose.yml`) no cambia de modelo: sigue con el 12B.

## Archivos

Revisiones fijadas completas en `scripts/fetch_models.sh`; las huellas están en `scripts/models.sha256` y las verificó T-242 con `sha256sum` sobre los archivos bajados y contra las que informó la API de Hugging Face (coinciden las cuatro).

| Candidato | Archivo local | Bytes | SHA-256 | Repositorio y revisión | Opción de descarga |
|---|---|---|---|---|---|
| Qwen3.8-27B | `Qwen3.8-27B-UD-Q4_K_M.gguf` | 16.464.440.224 | `322e194f…9123482` | `unsloth/Qwen3.8-27B-GGUF` `4ca72078…2e502` | `--qwen38-27b` |
| Qwen3.8-27B (proyector) | `mmproj-Qwen3.8-27B-F16.gguf` (`mmproj-F16.gguf` en el repositorio) | 927.607.488 | `cbb841a9…b4e43e` | igual | igual |
| Qwen3.6-35B-A3B | `Qwen3.6-35B-A3B-UD-IQ4_XS.gguf` | 17.730.509.792 | `649d7508…7ebbb3` | `unsloth/Qwen3.6-35B-A3B-GGUF` `a483e9e6…1118c` | `--qwen36-35b` |
| Qwen3.6-35B-A3B (proyector) | `mmproj-Qwen3.6-35B-A3B-F16.gguf` (`mmproj-F16.gguf` en el repositorio) | 899.283.680 | `8971ee4f…e887f` | igual | igual |

Licencia Apache 2.0 los dos. Los archivos son de un tercero (Unsloth), no del autor del modelo; la revisión fijada y la huella compensan el origen (ADR-0056).

## Bajarlos (una vez por equipo)

Es el único paso con internet, como el resto de los modelos (P4: los motores corren con `--offline`).

```
bash scripts/fetch_models.sh --qwen38-27b    # 17,4 GB
bash scripts/fetch_models.sh --qwen36-35b    # 18,6 GB
```

Cada opción baja solo su lista, no combina con las otras y verifica la huella de cada archivo contra `scripts/models.sha256`; si ya está y coincide imprime `OK (ya estaba)` y no baja nada (con los 4 archivos ya en `models/`, tarda un minuto por la verificación). Los 4 archivos están en `models/` de este equipo desde el 2026-10-10. Para mudarlos a otro equipo también se puede copiar la carpeta `models/` y correr la opción para verificar.

## Levantar un candidato

De a una medición, sin otra carga de la GPU. El archivo reemplaza solo `generation_batch` y las variables `GENERATION_BATCH_*` de `app` y `worker` (para registrar el modelo, P6); `generation`, `embeddings` y `reranker` siguen.

```
docker compose -f docker-compose.yml -f docker-compose.qwen38-27b.yml up -d --no-deps generation_batch worker app
docker compose -f docker-compose.yml -f docker-compose.qwen36-35b.yml up -d --no-deps generation_batch worker app
```

Con el candidato, `/props` de `generation_batch` tiene que mostrar `model_alias` `qwen3.8-27b-ud-q4_k_m` o `qwen3.6-35b-a3b-ud-iq4_xs`, `n_ctx` 32.768 y `modalities.vision` verdadero.

**La carga es lenta.** El 27B tardó unos 6 minutos en cargar y quedar listo en CPU desde el disco compartido (el 12B tarda de 1 a 3 minutos), así que durante la carga Docker puede mostrar el contenedor como `unhealthy` (el `start_period` del compose base es de 120 s; el archivo del 27B lo sube a 900 s desde T-247, el del 35B-A3B no) y pasa a `healthy` al terminar. Con `--no-deps` el `up` no espera la salud; esperar a `/health` antes de pedir nada: `docker compose ... exec generation_batch curl -s localhost:8080/health` devuelve `{"status":"ok"}`.

**No entra junto con el 12B de lotes.** Con el entorno de uso levantado (los cuatro motores) la GPU ocupa 10.968 MiB de 24.463 (medido el 2026-10-10 a las 19:45, sin pedidos en curso). El motor de lotes del 12B ocupa unos 8.075 MiB (ADR-0042); el candidato lo reemplaza, no se suma. El tope de la comparación es 22.000 MiB (ADR-0042 y ADR-0056).

## Qué cambia respecto del compose base

El `command` de cada archivo es el de `generation_batch` del compose base con estas diferencias, y nada más (lo comprueban `tests/test_compose_env.py` y `tests/tenders/test_generation_batch.py`):

| Qué | Base (12B) | Candidato |
|---|---|---|
| `--model`, `--alias`, `--mmproj` | Gemma 4 12B y su proyector | el modelo, el alias y el proyector del candidato |
| `--ctx-checkpoints` | no figura (por omisión del motor, 32) | `32`, declarado |
| `--checkpoint-min-step` | no figura (por omisión del motor, 8192) | `1024` |

Igual que el base: contexto 32.768 (`GENERATION_BATCH_CTX_SIZE`), `--parallel 1`, sin pensamiento (`--reasoning off`, `--reasoning-budget 0`), `--cache-ram 2048`, `--no-context-shift`, `--offline`, `--fit off`, imagen `server-cuda-b11347` (CUDA 12.8.1: la salida corrupta de CUDA 13.2 con Qwen3.6 que cita Unsloth no aplica; no pasar a una imagen CUDA 13 sin medir), red interna sin puertos publicados ni salida a internet. Los archivos de candidato no definen redes, puertos ni imagen (un test lo comprueba): el camino de pliegos y ofertas sigue sin salida a servicios externos de IA (P4).

### Caché de prefijo en la compilación b11347 (para T-243 y T-245)

El informe de candidatos recomendaba `--checkpoint-every-n-tokens 1024 --ctx-checkpoints 256` (paliativo de los usuarios de llama.cpp para los modelos híbridos). **Con la compilación fijada no se puede copiar tal cual:**

- `--checkpoint-every-n-tokens` no existe en `b11347` (el servidor no arrancaría); la bandera de esa compilación es `--checkpoint-min-step N` (separación mínima entre puntos de control; por omisión 8192). Se declara con 1024.
- `--ctx-checkpoints 256` guardaría en la memoria del equipo hasta 256 estados recurrentes del modelo (del orden de cientos de MiB cada uno para el 27B): decenas de GiB contra los 20 GB de WSL2. Se declara con 32, el valor por omisión del motor, explícito para que quede en el compose y en el registro. T-243 mide el tamaño real de un punto de control (el servidor lo imprime) y decide si sube.
- Lectura del código del servidor de `b11347` (`tools/server/server-context.cpp`): un modelo híbrido no puede recortar su memoria hasta el final de un prefijo común; al llegar un pedido se vuelve al último punto de control cuya posición no pasa del prefijo común, y si no hay ninguno se reprocesa todo el prompt. Los puntos de control se crean al empezar un mensaje de usuario y **4 y 4 + `--ubatch-size` tokens antes del final del prompt** (no cada N tokens). En la evaluación, los documentos y el requisito van en un solo mensaje de usuario (`build_evaluation_messages`): el punto de control útil es el de 516 tokens antes del final (`--ubatch-size` 512), y alcanza solo si lo que varía entre dos pedidos (normas, respuestas, requisito y la línea final) mide 516 tokens o menos. Si el reuso queda por debajo del 90 % del prefijo, la palanca de T-243 es `--ubatch-size` (mueve ese punto de control más atrás, a costa de memoria de video), igual en la prueba y la comparación y registrada. Es una lectura del código, no una medición.

### Tipo de la caché de claves y valores

Por omisión f16. Está comentado en cada archivo (`--cache-type-k q8_0 --cache-type-v q8_0`) y se activa solo si el candidato no entra en 22.000 MiB (único ajuste de servicio que permite el ADR-0056); en ese caso, igual en la prueba y la comparación, y registrado.

## Volver atrás

Volver al 12B es no usar el archivo adicional: recrear los mismos servicios solo con el compose base.

```
docker compose -f docker-compose.yml up -d --no-deps generation_batch worker app
```

Cambia solo el motor de lotes y el registro del modelo de `app` y `worker`; la base y los datos no se tocan. Los archivos de `models/` quedan donde están; borrarlos (36 GB) es la reversa de la descarga y requiere la confirmación del responsable cuando se decida descartar un candidato (ADR-0056, «Para revertir»).

## Prueba de arranque de T-242 (2026-10-10)

La prueba de humo completa con la GPU (memoria, caché de prefijo, velocidad, imagen) es de T-243 y T-245. T-242 solo comprobó que lo que declara el compose arranca:

- `docker compose -f docker-compose.yml -f docker-compose.qwen38-27b.yml config` y el mismo con `docker-compose.qwen36-35b.yml`: sin errores; `generation_batch` queda en la red interna, sin puertos, con la imagen `server-cuda-b11347` y las variables del candidato en `app` y `worker`.
- Con la GPU ocupada por el entorno de uso (10.968 MiB de 24.463, quedan 13.495 MiB) y los motores de ese proyecto en marcha, el candidato no se cargó en la GPU: el 27B necesita unos 19.000 MiB solo con el motor de lotes (estimación del ADR-0056, sin medir). No se detuvo ni se tocó ningún contenedor del proyecto `evaluon`.
- Arranque en CPU, sin GPU ni red (`docker run --network none --memory 5g`/`6g`, contexto 4.096, `--no-warmup`, con las mismas banderas del compose), para saber si la compilación `b11347` reconoce las dos arquitecturas, los proyectores y las banderas nuevas antes de gastar horas de GPU:

| | Qwen3.8-27B | Qwen3.6-35B-A3B |
|---|---|---|
| Carga del modelo y del proyector | sí | sí |
| Servidor escuchando y `/health` | `ok` a los 5 min 59 s | `ok` a los 4 min 20 s |
| `/props` | alias `qwen3.8-27b-ud-q4_k_m`, `Q4_K - Medium`, visión verdadera, `b11347-5fc4f3c8c` | alias `qwen3.6-35b-a3b-ud-iq4_xs`, `IQ4_XS - 4.25 bpw`, visión verdadera, `b11347-5fc4f3c8c` |
| Banderas `--ctx-checkpoints 32 --checkpoint-min-step 1024 --reasoning off --reasoning-budget 0 --offline` | aceptadas | aceptadas |

  Avisos del motor que T-243 y T-245 deben mirar, sin que sean fallas: la plantilla soporta conservar el razonamiento y lo activa por omisión («may use more tokens»; el pensamiento está apagado con `--reasoning off`, a verificar con 0 tokens de pensamiento); «Qwen-VL models require at minimum 1024 image tokens» (`--image-min-tokens 1024` si la lectura de imágenes pierde precisión; no se cambia sin medir); el 27B ignora sus tensores `blk.64.*` (la cabeza de predicción adicional `nextn`, que EVALUON no usa).
- Un pedido de texto en CPU no se completó: el 27B procesó 88 tokens de prompt en 90 s (menos de 1 token por segundo, limitado por leer los 16 GB del disco compartido) y se detuvo la prueba. Esa cifra **no** sirve para estimar nada de la GPU. El pedido de texto, el de imagen, la memoria, los tokens por segundo y la caché de prefijo quedan para T-243 y T-245, con la GPU libre.
- No se detuvo, recreó ni tocó ningún contenedor del proyecto `evaluon`; las dos pruebas usaron un contenedor propio (`evaluon-cand-cpu`), ya borrado.

## Razonamiento propio del modelo (T-253, 2026-10-11)

Decisión del responsable (spec 015, 2026-10-11): la comparación suma variantes con el razonamiento propio del modelo encendido en los pasos que deciden. T-253 lo hace posible y no cambia lo que corre hoy. Se enciende de a un paso (extracción, completitud, filtro, evaluación y contraste), solo en el motor de lotes (`generation_batch`); con todo apagado el pedido es el de siempre.

### Cómo se enciende

Se suma `docker-compose.razonamiento.yml` al final de cualquier otra combinación y se pone la variable de cada paso (`low`, `medium` o `high`; sin la variable o con `off`, el paso no piensa):

```
GENERATION_BATCH_REASONING_FILTER=low GENERATION_BATCH_REASONING_EVALUATION=low \
  docker compose -f docker-compose.yml -f docker-compose.razonamiento.yml up -d --no-deps generation_batch worker app
GENERATION_BATCH_REASONING_FILTER=low \
  docker compose -f docker-compose.yml -f docker-compose.qwen38-27b.yml -f docker-compose.razonamiento.yml up -d --no-deps generation_batch worker app
```

Variables (`settings.py`; llegan a `app` y `worker` solo con este archivo): `GENERATION_BATCH_REASONING_EXTRACTION`, `_COMPLETENESS`, `_FILTER`, `_EVALUATION`, `_CONTRAST`; `GENERATION_BATCH_REASONING_BUDGET_LOW|MEDIUM|HIGH` (tope de tokens de razonamiento por nivel; por omisión 1.024, 2.048 y 4.096); `GENERATION_BATCH_REASONING_EXTRA_TIMEOUT_SECONDS` (espera que se suma a un pedido que piensa; por omisión 900). Volver es recrear los mismos servicios sin el archivo. El compose base y los de los candidatos no cambian: arrancan con `--reasoning off --reasoning-budget 0`, y con eso el servidor ignora cualquier pedido de pensar (ADR-0055, punto 9).

El archivo no repite el `command` (el `command` de un archivo de Compose reemplaza al del otro): cambia el `entrypoint` de `generation_batch` para que `llama-server` reciba, al final de las banderas del otro archivo, `--reasoning auto --reasoning-budget -1`. Con una bandera repetida el servidor usa la última y lo avisa en el registro (`argument '--reasoning' specified multiple times ... only last value will be used`; b11347, verificado el 2026-10-11 arrancando el 12B en CPU con las banderas de hoy y el entrypoint del archivo). `tests/test_compose_razonamiento.py` comprueba, para el base, el 26B-A4B y los dos Qwen, que el `command` llega entero y termina en esas dos banderas. Con el servidor permitido, un paso apagado no piensa: su pedido manda `enable_thinking: false` (medido con el 12B: 68 tokens de salida contra 282 con `true`, mismo pedido).

### Qué pide el pedido de un paso encendido

`chat_template_kwargs {"enable_thinking": true}`; `reasoning_effort` con el nivel; `thinking_budget_tokens` con el tope del nivel; `max_tokens` sube en ese tope; la espera sube en `GENERATION_BATCH_REASONING_EXTRA_TIMEOUT_SECONDS`. El esquema JSON, la temperatura 0 y la semilla no cambian.

- **`enable_thinking`**: lo entienden el 12B (Gemma 4) y las plantillas Qwen3.x.
- **`reasoning_effort`**: va en el cuerpo del pedido, no en `chat_template_kwargs` (medido con `/apply-template` del Qwen3.8-27B: en `chat_template_kwargs` no llega a la plantilla). La plantilla del Qwen3.8-27B acepta `xhigh` (por omisión), `medium` y `low`, y convierte `high` en `xhigh`; agrega una línea al mensaje de sistema («Reasoning effort is set to low. Keep your thinking brief…»). El 12B lo ignora (mismo razonamiento con y sin él). Los niveles `low`, `medium` y `high` de EVALUON se corresponden.
- **`thinking_budget_tokens`**: llama.cpp b11347 lo respeta por pedido. Cortó el razonamiento en el tope (1.023 de 1.024 y 2.047 de 2.048 tokens en el 12B; 2.048 de 2.048 en el 27B) y siguió con la respuesta. El tope es lo que acota el costo; el servidor queda con el presupuesto ilimitado.

### Cómo se combinan el esquema y el razonamiento

La gramática del esquema se aplica al **contenido**, después del bloque de razonamiento, no al razonamiento. Evidencia (12B con `--reasoning auto`): con un esquema cuyo `resultado` solo admitía `alfa` o `beta`, el razonamiento salió en texto libre (habló de claves `cumple` y `razonamiento` que el esquema no tiene) y el contenido salió `{"razonamiento": …, "resultado": "beta"}`, válido. Con los pedidos reproducidos del filtro y de la evaluación del caso-00, y con el 27B, el contenido también validó (`json.loads` y las claves del esquema). El razonamiento vuelve aparte, en `choices[0].message.reasoning_content`, y el contenido sigue siendo el JSON; los esquemas no cambian. Una condición: si el máximo de salida se agota pensando, el contenido llega vacío con `finish_reason: length` (medido con `max_tokens` 100); por eso el pedido suma el tope de razonamiento al máximo de salida, y un contenido vacío cae en las anomalías de salida inválida de siempre.

### ¿El Gemma 4 12B admite razonamiento?

Sí, en esta compilación (b11347): con `--reasoning auto --reasoning-budget -1` en el servidor, el pedido con `enable_thinking: true` devuelve `reasoning_content`; con `false`, no. Con las banderas de hoy (`--reasoning off --reasoning-budget 0`) lo ignora. El razonamiento del 12B salió en inglés y empezó repitiendo las instrucciones del pedido (en el filtro) o listando los documentos (en la evaluación) antes de llegar al requisito; si eso agrega calidad, lo dirá la medición de T-244.

### Registro (P6)

Cada pedido de un paso encendido guarda en su `parsed` `razonamiento_propio` = `{nivel, texto, tokens}` (los tokens, por `/tokenize` del servidor que lo generó; sin dato si el servidor no puede contarlos). Un modelo que no devuelve razonamiento queda con texto vacío y 0 tokens, para no confundirlo con un paso apagado. La corrida guarda en `parameters` `reasoning` (el nivel de cada paso), `reasoning_budget_tokens` y `reasoning_extra_timeout_seconds`; el pedido registrado lleva `enable_thinking`, `reasoning_effort`, `thinking_budget_tokens` y el máximo de salida con que salió.

### Mediciones (T-253, 2026-10-11; un pedido por caso, sin repetir)

Pedidos reales del caso-00 (LPU25) reproducidos desde la base con el razonamiento encendido. El pedido guardado es de una versión anterior de las instrucciones y de los esquemas (previa a T-236 y T-237), así que miden el costo del razonamiento y no la calidad. «Base» es el mismo pedido guardado, sin razonamiento.

| Pedido | Modelo | Tope pedido | Base: tokens de salida y tiempo | Con razonamiento: tokens de salida (de razonamiento) y tiempo | Cortado por el tope |
|---|---|---|---|---|---|
| Filtro de 11 filas, 3.514 tokens de entrada (matriz 54, paso 9469) | Gemma 4 12B | 1.024 | 374, 11,9 s | 1.412 (1.023), 25,3 s | sí |
| Evaluación de un grupo, 13.483 tokens de entrada (evaluación 51, paso 1296) | Gemma 4 12B | 2.048 | 133, 8,7 s | 2.165 (2.047), 51,1 s | sí |
| El mismo, nivel `low` | Qwen3.8-27B | 2.048 | sin base | 2.187 (2.048), 91,7 s a 24 tokens por segundo | sí |

Lecturas: en los tres el modelo quiso pensar más que el tope, así que el costo observado es el tope (con el 12B, 13 s más por pedido de filtro y 42 s más por pedido de evaluación; el 27B tardó 91,7 s en la evaluación, contra 8,7 s del 12B sin razonamiento). El tiempo del 27B no incluye leer el prompt de 13.600 tokens, que ya estaba en la caché de prefijo por un intento previo del mismo pedido que se cortó. Extrapolación de una sola muestra, a confirmar en T-244: con el 12B y un tope de 2.048, unos 243 pedidos de lectura de evaluación suman cerca de 2,8 horas más, casi todo el tope de 180 minutos del caso-00 completo; conviene medir la evaluación con tope de 1.024 o encender solo el contraste y el filtro. La GPU marcó 20.948 MiB en total con el 27B generando el primer intento de ese pedido (contexto 32.768, caché f16, con embeddings y reranker y sin los otros dos motores de generación), dentro de 22.000.

## Configuración candidata: Qwen3.8-27B con razonamiento solo en el contraste (T-254, 2026-10-12)

Decisión del responsable del 2026-10-12 («1 y luego 3 para no dejarlo sin probar», spec 015): el candidato es el Qwen3.8-27B con el razonamiento propio encendido **solo en el contraste** de la evaluación. Es la parte de la variante 3 de T-244b que frena el único «cumple» sin respaldo del 27B sin cambiar nada más; el razonamiento en el filtro (que dejaba pasar incisos de formularios) y en la extracción y la evaluación (que dio una contradicción con el dictamen, T-244c) quedan apagados. Esta configuración todavía no se midió entera: se mide una vez, junto con el 12B, con el código de T-254.

### Cómo se levanta

El 27B no entra con el motor de la Consulta (`generation`) encendido: se apaga antes. La propuesta de la matriz ya no lo necesita para contar tokens (H-244-1, T-254).

```
docker compose stop generation
GENERATION_BATCH_REASONING_CONTRAST=low docker compose -f docker-compose.yml -f docker-compose.qwen38-27b.yml -f docker-compose.razonamiento.yml up -d --no-deps generation_batch worker app
```

- **Los tres archivos, en ese orden.** El del 27B cambia el modelo, el alias y el proyector de `generation_batch`; el de razonamiento va **al final** y agrega al servidor `--reasoning auto --reasoning-budget -1` (si no, el servidor ignora el pedido de pensar) y pasa a `app` y `worker` las variables de cada paso.
- **Solo el contraste piensa.** `GENERATION_BATCH_REASONING_CONTRAST=low` y ninguna otra variable de razonamiento: la extracción, la completitud, el filtro y la evaluación quedan apagados (cada pedido manda `enable_thinking: false`). El tope del nivel `low` es de 1.024 tokens de razonamiento por pedido (`GENERATION_BATCH_REASONING_BUDGET_LOW`); en T-244b el contraste usó 905 en promedio. Un test (`tests/test_compose_razonamiento.py`) comprueba que esa variable deja solo ese paso encendido.
- **Esperar a `/health`** antes de pedir nada: la carga tarda de 4 a 10 minutos (10 en T-244, 7,5 en T-244b; en T-254, 4,5 minutos la primera vez y 5 la segunda, de `up` a `/health` `ok`) (`docker compose exec generation_batch curl -s localhost:8080/health` devuelve `{"status":"ok"}`). Con `--no-deps` el `up` no espera.
- **Qué comprobar:** `/props` de `generation_batch` con el alias `qwen3.8-27b-ud-q4_k_m`, `n_ctx` 32.768 y visión verdadera; en cada corrida, `parameters.reasoning` con `contrast: low` y los demás pasos en `off`, y `razonamiento_propio` (nivel, texto y tokens) en cada pedido del contraste y en ningún otro (P6).
- **Memoria:** unos 20.960 MiB de 24.463 con `embeddings` y `reranker` encendidos y `generation` apagado (T-244, T-244b); el tope es 22.000 MiB. Con `generation` encendido no entra.
- **La propuesta de datos del procedimiento** (`procedure_fields`, el alta desde el pliego) usaba `generation` y con el 27B levantado no corría; desde T-247 pide al motor de lotes y funciona con el 27B (ADR-0057). La propuesta de la matriz y el respaldo normativo también cuentan y piden al motor de lotes (T-254, H-244-1).
- **Mientras esté levantado**, la Consulta de normativa no responde (el motor `generation` está apagado; desde T-247 su pantalla lo dice en lugar de fallar) y la propuesta de datos del oferente (`offers/proposal_fields.py`, el nombre) tampoco, sin fallar: el dato queda «no determinado». Fichas, lectura con visión, informe técnico, matriz y evaluación piden al motor de lotes y funcionan.

### Cómo se vuelve al 12B

```
docker compose -f docker-compose.yml up -d --no-deps generation_batch worker app
docker compose start generation
```

Recrea `generation_batch`, `worker` y `app` solo con el compose base (12B, sin razonamiento: `--reasoning off --reasoning-budget 0`) y enciende de nuevo la Consulta. Comprobar: `/health` `ok` en los dos motores, el alias del 12B en `/props` de cada uno, `n_ctx` 32.768 en el de lotes y 16.384 en el de la Consulta, y un pedido de prueba a cada uno sin razonamiento.

## Uso por omisión: el Qwen3.8-27B con razonamiento solo en el contraste (T-247, ADR-0057)

Preparado por T-247 (2026-10-12), **sin desplegar**: el responsable adoptó el modelo el mismo día («Sí; Consulta con el 27B») y el despliegue en el equipo de uso (8000) lo hace el Coordinador después de verificar (P11).

### Qué cambia respecto del compose base

Un `.env` copiado de `.env.example` trae tres líneas nuevas y `docker compose up -d` (sin `-f`) arma el proyecto con cuatro archivos:

| Línea de `.env.example` | Efecto |
|---|---|
| `COMPOSE_FILE=docker-compose.yml:docker-compose.qwen38-27b.yml:docker-compose.razonamiento.yml:docker-compose.sin-consulta.yml` y `COMPOSE_PATH_SEPARATOR=:` | `generation_batch` es el Qwen3.8-27B, el servidor permite pensar (`--reasoning auto --reasoning-budget -1`) y `generation` no arranca (perfil `consulta-12b`; `app` no lo espera). El separador `:` es explícito porque el de Compose en Windows es `;` |
| `GENERATION_BATCH_REASONING_CONTRAST=low` | Solo el contraste piensa, con tope de 1.024 tokens de razonamiento por pedido; extracción, completitud, filtro y evaluación no (T-244b y T-244c: con razonamiento empeoran) |

Los archivos del 12B, de razonamiento y del 35B no cambian de contenido; el del 27B suma la espera de la carga (`start_period` de 900 s en el chequeo de `generation_batch`). Los comandos con `-f archivo` explícito (las secciones de arriba, las mediciones y los runbooks anteriores) no leen `COMPOSE_FILE` y siguen valiendo tal cual.

### Instalación desde cero (P5)

```
cp .env.example .env            # completar POSTGRES_PASSWORD y DJANGO_SECRET_KEY (ver .env.example)
bash scripts/fetch_models.sh               # 12B, bge-m3 y reranker (el 12B es el camino de vuelta)
bash scripts/fetch_models.sh --qwen38-27b  # 27B y su proyector, 17,4 GB; verifica la huella
docker compose up -d
```

La carga del 27B tarda de 3 a 10 minutos (3 min 4 s en T-244d; 4,5 a 10 min en otras corridas). Con `docker compose up -d` (con dependencias), el `worker` espera la salud de `generation_batch`: el archivo del 27B sube el `start_period` del chequeo a 900 s (el del compose base es de 120 s), así que el servicio no pasa a «unhealthy» mientras carga y el `up` termina con todo arriba, unos minutos después. Si pasan más de 15 minutos sin salud, mirar `docker compose logs generation_batch` (archivo o huella del modelo, memoria de video ocupada por otro proceso). Comprobar: `/props` de `generation_batch` con el alias `qwen3.8-27b-ud-q4_k_m`, `n_ctx` 32.768 y visión verdadera; `docker compose ps` sin `generation`; en cada corrida, `parameters.reasoning` con `contrast: low` y los demás pasos en `off`.

### Memoria, tiempos y carga

| | Medido | Registro |
|---|---|---|
| Memoria de video máxima, con `embeddings` y `reranker` y sin `generation` | 20.956 MiB de 24.463 (tope 22.000; margen 1.044) | T-244d |
| Caso-00 completo (matriz y evaluación de 3 ofertas) | 72,9 min (12,3 + 60,6); el 12B, 31,6 min | T-244d, T-241 |
| Carga del modelo hasta `/health` | 3 min 4 s a 10 min | T-244d, T-244 |
| Con `generation` encendido | no entra (unos 7.800 MiB más) | T-243, T-244 |

Mientras una evaluación o una matriz corre, el motor de lotes está ocupado: los pedidos del `worker` van de a uno. La GPU no admite otra carga.

### La Consulta y las propuestas de datos

- La Consulta de normativa queda **apagada** hasta T-255: su pantalla (`/consulta/`) y la pestaña de Normativas dicen «La consulta de normativa no está disponible por ahora…», con el botón desactivado, y no ejecutan ni guardan la pregunta. Lo decide `generation.is_available()` (`GET /health` de `generation`, 2 s de espera; cualquier falla, incluso una respuesta que no es HTTP, es «no disponible»): si el motor se enciende, la Consulta vuelve sola. La búsqueda directa sigue.
- El alta del procedimiento desde el pliego usa el motor de lotes (T-247) y su traza de auditoría nombra el motor y el modelo que atendieron el pedido (`models.generation_batch`: alias, archivo y huella del modelo, proyector, compilación y contexto), como la matriz y la evaluación (P6).
- La propuesta de datos del oferente (`offers/proposal_fields.py`) sigue pidiendo a `generation`: sin ese motor, el nombre queda «no determinado» sin fallar (pendiente para T-248).

### Cómo se vuelve al 12B (con la Consulta)

```
# 1. en .env: borrar o comentar COMPOSE_FILE, COMPOSE_PATH_SEPARATOR y GENERATION_BATCH_REASONING_CONTRAST
docker compose up -d --no-deps generation_batch worker app generation
```

Recrea `generation_batch`, `worker` y `app` con el compose base (12B, sin razonamiento) y enciende `generation`. Comprobar: `/health` `ok` en los dos motores, el alias del 12B en `/props` de cada uno, `n_ctx` 32.768 en el de lotes y 16.384 en el de la Consulta, y la pantalla de la Consulta sin el aviso. No cambia ningún dato ni la base. Los archivos del 27B quedan en `models/`; borrarlos (17,4 GB) lo decide el responsable. Una vuelta puntual, sin tocar `.env`: `docker compose -f docker-compose.yml up -d --no-deps generation_batch worker app generation`.

## Despliegue del 27B en 8000 · 2026-10-12

Estado: desplegado (decisión del responsable del 2026-10-12, «Sí; Consulta con el 27B»; ADR-0057).

- Raíz en `main` e6432b6. Respaldo previo `backups/evaluon-2026-10-12-previo-015-27b.dump` (861 entradas con `pg_restore -l`); `.env` anterior guardado fuera del repositorio; imagen anterior `evaluon-app:previo-015-27b`.
- Se detuvieron `generation` y `generation_batch`, se sumaron al `.env` las tres líneas de «Uso por omisión» (`COMPOSE_FILE`, `COMPOSE_PATH_SEPARATOR`, `GENERATION_BATCH_REASONING_CONTRAST=low`) y se levantó con `docker compose up -d`.
- Comprobado: `generation_batch` sano con `Qwen3.8-27B-UD-Q4_K_M.gguf`, su proyector y `--reasoning auto`; `app` con `GENERATION_BATCH_MODEL_ALIAS=qwen3.8-27b-ud-q4_k_m` y el razonamiento solo en el contraste; `generation` fuera; GPU en 18.458 MiB en reposo; `/ingresar/` 200; cola sin pedidos en curso.
- Volver al 12B: «Cómo se vuelve al 12B» de este archivo (borrar las tres líneas del `.env` y recrear).

