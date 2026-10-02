# Entorno 001 · Comprobación del entorno (etapa 0)

Este archivo registra las comprobaciones de la etapa 0 del plan (`specs/001-normativa/plan.md`, "Etapa 0 · Comprobación del entorno" y "Sin verificar y cómo se cierra"). Lo completan las tareas T-001 a T-005, de a una y en orden: cada tarea agrega sus secciones con qué se probó, el comando, la salida transcripta y el resultado. No se agregan scripts de prueba al repositorio.

Equipo: la notebook MSI del proyecto (Windows 11 Pro 10.0.26200, Docker Desktop con WSL2, motor Docker 29.8.1).

## T-001 · GPU dentro de un contenedor

Fecha: 2026-10-02. Requisito: REQ-008 (habilita la generación local).

### 1. Datos de la placa en Windows

**Qué se probó.** Modelo de placa y memoria de video total, con `nvidia-smi` en Windows.

**Comandos.**

```
nvidia-smi
nvidia-smi --query-gpu=name,memory.used,memory.total,driver_version --format=csv
```

**Salida.**

```
Fri Oct  2 17:44:45 2026
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 591.76                 Driver Version: 591.76         CUDA Version: 13.1     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                  Driver-Model | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA GeForce RTX 5090 ...  WDDM  |   00000000:01:00.0 Off |                  N/A |
| N/A   29C    P0             24W /  150W |       0MiB /  24463MiB |      0%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|  No running processes found                                                             |
+-----------------------------------------------------------------------------------------+
```

```
name, memory.used [MiB], memory.total [MiB], driver_version
NVIDIA GeForce RTX 5090 Laptop GPU, 0 MiB, 24463 MiB, 591.76
```

**Resultado.** Cumple. La placa es "NVIDIA GeForce RTX 5090 Laptop GPU" (así la nombra el controlador), modo de controlador WDDM, controlador 591.76, CUDA 13.1 como máximo soportado. Memoria total: 24.463 MiB, que son los 24 GB nominales (23,9 GiB).

### 2. GPU visible dentro de un contenedor

**Qué se probó.** Que Docker Desktop con WSL2 dé acceso a la GPU: `nvidia-smi` dentro de un contenedor de la imagen oficial de CUDA, con `--gpus all`.

**Imagen usada.** `nvidia/cuda:12.8.1-base-ubuntu24.04` (Docker Hub, imagen oficial de NVIDIA), huella `sha256:133c78a0575303be34164d0b90137a042172bdf60696af01a3c424ab402d86e2`. CUDA 12.8 es la primera versión que soporta la serie RTX 50 (arquitectura Blackwell).

**Comandos.**

```
docker pull nvidia/cuda:12.8.1-base-ubuntu24.04
docker run --rm --gpus all nvidia/cuda:12.8.1-base-ubuntu24.04 nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.8.1-base-ubuntu24.04 nvidia-smi --query-gpu=name,memory.used,memory.total,driver_version --format=csv
```

**Salida.**

```
Digest: sha256:133c78a0575303be34164d0b90137a042172bdf60696af01a3c424ab402d86e2
Status: Downloaded newer image for nvidia/cuda:12.8.1-base-ubuntu24.04
docker.io/nvidia/cuda:12.8.1-base-ubuntu24.04
```

```
Fri Oct  2 20:45:03 2026
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 590.54                 Driver Version: 591.76         CUDA Version: 13.1     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA GeForce RTX 5090 ...    On  |   00000000:01:00.0 Off |                  N/A |
| N/A   30C    P0             24W /  150W |       0MiB /  24463MiB |      0%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|  No running processes found                                                             |
+-----------------------------------------------------------------------------------------+
```

```
name, memory.used [MiB], memory.total [MiB], driver_version
NVIDIA GeForce RTX 5090 Laptop GPU, 0 MiB, 24463 MiB, 591.76
```

**Resultado.** Cumple. El contenedor ve la misma placa (mismo Bus-Id 00000000:01:00.0) con 24.463 MiB. La hora del contenedor está en UTC (20:45) y la de Windows en hora de Buenos Aires (17:44); es la misma corrida del día. El `nvidia-smi` del contenedor es 590.54 y usa el controlador 591.76 de Windows, como corresponde en WSL2.

### 3. Memoria de video que usa Windows

**Qué se probó.** Cuánta memoria de video ocupa Windows con la pantalla activa y los servicios del proyecto detenidos. No hay todavía servicios del proyecto; el único contenedor en marcha es `postgres-dev` (`pgvector/pgvector:pg17`), que no usa GPU. No se usó ningún otro programa con GPU durante la lectura.

**Comandos.**

```
nvidia-smi --query-gpu=display_active,display_mode,memory.used,memory.reserved,memory.free,memory.total --format=csv
powershell -NoProfile -Command "Get-CimInstance Win32_VideoController | Select-Object Name,CurrentHorizontalResolution,CurrentVerticalResolution,DriverVersion"
```

**Salida.**

```
display_active, display_mode, memory.used [MiB], memory.reserved [MiB], memory.free [MiB], memory.total [MiB]
Disabled, [Requested functionality has been deprecated], 0 MiB, 326 MiB, 24137 MiB, 24463 MiB
```

```
Name                               CurrentHorizontalResolution CurrentVerticalResolution DriverVersion
----                               --------------------------- ------------------------- -------------
NVIDIA GeForce RTX 5090 Laptop GPU                                                       32.0.15.9176
Intel(R) Graphics                  2560                        1600                      32.0.101.8509
```

**Resultado.** Windows usa 0 MiB de la placa NVIDIA; el controlador reserva 326 MiB; quedan libres 24.137 MiB (23,6 GiB). La razón: la notebook trabaja con gráficos híbridos y la pantalla (2560 x 1600) la maneja la placa integrada Intel; la RTX 5090 figura con `Disp.A Off` y `display_active Disabled`. En modo WDDM `nvidia-smi` no reporta el uso por proceso ("No running processes found"), por eso la lectura es la de la placa entera.

Para la cuenta de memoria del plan (tope de 20 GB sobre 24): con la configuración actual, Windows no consume memoria de la RTX 5090 y el margen real es de unos 24.137 MiB disponibles. Esta lectura vale mientras la pantalla siga en la placa integrada. Si se cambia el modo de gráficos a solo la placa dedicada, o se conecta un monitor externo a una salida cableada a la NVIDIA, Windows pasa a usar memoria de la RTX 5090 y la lectura hay que repetirla.

## T-002 · Motor de generación

Fecha: 2026-10-02. Requisitos: REQ-008 (respuesta con esquema), REQ-009 (abstención del modelo) y el tiempo de respuesta de la spec.

Resumen: compilación fijada `b11347`; Gemma 4 12B de 4 bits de Google con huella verificada; 20 de 20 salidas válidas; sin razonamiento previo; pedido largo en 15,3 a 15,6 s (menos de 25); 7.818 MiB de memoria de video; la plantilla agrega 18 tokens (margen previsto: 512); el pedido excedido se rechaza con error 400. No se disparó ninguna condición de parada.

### 1. Compilación de llama.cpp fijada

**Qué se probó.** Qué compilación de `llama.cpp` tiene imagen `server-cuda` publicada y sirve para Gemma 4 y la serie RTX 50.

**Elección.** `ghcr.io/ggml-org/llama.cpp:server-cuda-b11347`, huella de la imagen `sha256:d87b02aafa74797a2d599b281c50468704bd0bcdc57bfcf31b570d593f1d285b`, commit `5fc4f3c8c`, compilación publicada el 2026-10-02 (imagen creada 2026-10-02T04:33:53Z). Motivos:

- Es la compilación más nueva con imagen `server-cuda` publicada en el registro al momento de la prueba. Las versiones `b11349` y `b11351` ya figuraban en GitHub, pero sus imágenes todavía no existían en ghcr (respuesta 404); `b11348` y `b11350` no son versiones publicadas.
- La arquitectura `gemma4` está soportada desde abril de 2026, y esta compilación incluye las correcciones posteriores para Gemma 4 (por ejemplo, "chat : fix gemma4 required tool grammar", #29115, 2026-09-16, y la aclaración del token de relleno de gemma4 en #29599, 2026-09-30).
- La imagen está construida sobre CUDA 12.8.1 (`CUDA_VERSION=12.8.1`, `NVIDIA_REQUIRE_CUDA=cuda>=12.8`), la primera versión con soporte de la serie RTX 50 (Blackwell). El controlador de Windows admite hasta CUDA 13.1 (sección T-001).
- Es posterior a la `b11176` citada en el ADR-0002.

**Comandos.**

```
docker pull ghcr.io/ggml-org/llama.cpp:server-cuda-b11347
docker image inspect ghcr.io/ggml-org/llama.cpp:server-cuda-b11347 --format '{{json .Config.Labels}}'
docker run --rm ghcr.io/ggml-org/llama.cpp:server-cuda-b11347 --version
```

**Salida (extracto).**

```
Digest: sha256:d87b02aafa74797a2d599b281c50468704bd0bcdc57bfcf31b570d593f1d285b
Status: Downloaded newer image for ghcr.io/ggml-org/llama.cpp:server-cuda-b11347
"org.opencontainers.image.revision":"5fc4f3c8c7103ffd0b7ff5ee4855bcc78a3ed5cd","org.opencontainers.image.version":"b11347"
CUDA_VERSION=12.8.1
version: 0.5.0-dev (build 11347, commit 5fc4f3c8c)
built with GNU 14.2.0 for Linux x86_64
```

**Resultado.** Fijada en `docker-compose.yml`. T-003 usa la misma imagen y compilación para `embeddings` y `reranker`.

### 2. Archivo del modelo y su huella

**Qué se probó.** Que `scripts/fetch_models.sh` baje el archivo de 4 bits publicado por Google (ADR-0002, fuente [24]) y que su huella coincida con `scripts/models.sha256`.

**Origen.** Repositorio `google/gemma-4-12B-it-qat-q4_0-gguf` de Hugging Face, revisión fijada `29d097773436b69ff9feafd636ab4cf873786537`, archivo `gemma-4-12b-it-qat-q4_0.gguf`, 6.975.879.296 bytes, licencia Apache 2.0, sin registro previo. Huella SHA-256: `93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b` (coincide con la que publica Hugging Face para el archivo). El repositorio trae también `mmproj-gemma-4-12b-it-qat-q4_0.gguf` (visión); no se baja porque la feature no usa imágenes.

**Comandos.**

```
CURL_EXTRA_OPTS="--ssl-no-revoke --silent --show-error" bash scripts/fetch_models.sh
bash scripts/fetch_models.sh
```

**Salida.**

```
Descargando gemma-4-12b-it-qat-q4_0.gguf ...
OK: gemma-4-12b-it-qat-q4_0.gguf  sha256=93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b
real    3m9,802s
```

```
OK (ya estaba): gemma-4-12b-it-qat-q4_0.gguf
exit=0
```

**Resultado.** Cumple: termina sin error y la huella coincide; la segunda corrida no vuelve a bajar el archivo. `models/` queda fuera del repositorio por la regla `models/` que ya tenía `.gitignore`.

Dos observaciones de este equipo, para el runbook:

- El `curl` de Git Bash en Windows (Schannel) falló con `CRYPT_E_NO_REVOCATION_CHECK` al consultar la revocación de certificados. Se resolvió pasando `--ssl-no-revoke` por la variable opcional `CURL_EXTRA_OPTS`; el script no lo trae por defecto.
- La primera corrida falló con `curl: (35) Recv failure: Connection was reset` contra huggingface.co (corte intermitente, ya visto al consultar su API). Se agregó `--retry-all-errors` al script; la segunda corrida terminó bien.

### 3. Servicio `generation` y `/health`

**Configuración** (`docker-compose.yml`). Red `internal` con `internal: true` (sin salida a internet), sin puertos publicados, `models/` montado en `/models` en solo lectura, GPU por `deploy.resources.reservations.devices`. Parámetros de `llama-server`: `--ctx-size 16384`, `--parallel 1` (una sola ranura, para que cada pedido tenga los 16.384 tokens enteros), `--n-gpu-layers all`, `--fit off` (para que el servidor no cambie por su cuenta el contexto ni las capas), `--reasoning off`, `--reasoning-budget 0`, `--no-context-shift`, `--offline`. Temperatura y semilla no se fijan en el servidor: van en cada pedido (temperatura 0 y semilla 42 en estas pruebas). El archivo, el alias y el contexto se leen de variables de entorno con valores por defecto (`.env.example`).

**Comandos.** Los pedidos se hicieron desde un contenedor cliente (la misma imagen, que trae `curl`) conectado a la red interna. Los cuerpos de los pedidos son texto sintético y quedaron fuera del repositorio.

```
docker compose up -d generation
docker inspect -f '{{.State.Health.Status}}' evaluon-generation-1
docker run -d --name t002-client --network evaluon_internal -v <carpeta temporal>:/work --entrypoint sleep ghcr.io/ggml-org/llama.cpp:server-cuda-b11347 infinity
docker exec t002-client curl -sS http://generation:8080/health
docker exec t002-client curl -sS -m 10 https://huggingface.co -o /dev/null -w "%{http_code}\n"
docker exec t002-client curl -sS http://generation:8080/props
```

**Salida.**

```
 Network evaluon_internal Created
 Container evaluon-generation-1 Started
estado=healthy
NAME                   IMAGE                                           SERVICE      STATUS                    PORTS
evaluon-generation-1   ghcr.io/ggml-org/llama.cpp:server-cuda-b11347   generation   Up 39 seconds (healthy)
```

```
srv    load_model: loading model '/models/gemma-4-12b-it-qat-q4_0.gguf'
srv    load_model: initializing, n_slots = 1, n_ctx_slot = 16384, kv_unified = 'false'
srv  llama_server: model loaded
srv  llama_server: listening on http://0.0.0.0:8080
```

```
{"status":"ok"}
curl: (6) Could not resolve host: huggingface.co
{"default_generation_settings": {"n_ctx": 16384}, "total_slots": 1, "model_alias": "gemma-4-12b-it-qat-q4_0", "model_ftype": "Q4_0", "model_path": "/models/gemma-4-12b-it-qat-q4_0.gguf", "modalities": {"vision": false, ...}, "build_info": "b11347-5fc4f3c8c", ...}
```

**Resultado.** Cumple. El modelo carga en unos 31 s y `/health` responde `{"status":"ok"}`. Desde la red interna no se llega a internet. El registro de arranque trae avisos del cargador sobre los tokens `</s>` y `<|tool_response>` ("probably a bug in the model"); el servidor los corrige solo y no afectaron las pruebas.

### 4. Veinte pedidos con esquema de prueba

**Qué se probó.** Que el motor haga cumplir un esquema con lista cerrada de alias, al menos una cita por afirmación y máximo de afirmaciones. Cuatro unidades sintéticas (U1 a U4, de un reglamento ficticio), 10 preguntas que esas unidades responden y 10 que no. `POST /v1/chat/completions` con `response_format` de tipo `json_schema` (`strict: true`), temperatura 0, semilla 42, máximo 800 tokens.

**Esquema de prueba.**

```
{"type": "object", "properties": {"status": {"type": "string", "enum": ["answered", "not_determined"]}, "claims": {"type": "array", "maxItems": 4, "items": {"type": "object", "properties": {"text": {"type": "string"}, "citations": {"type": "array", "minItems": 1, "items": {"type": "string", "enum": ["U1", "U2", "U3", "U4"]}}}, "required": ["text", "citations"], "additionalProperties": false}}}, "required": ["status", "claims"], "additionalProperties": false}
```

**Comando.**

```
docker exec t002-client sh -c 'cd /work && for i in $(seq -w 1 20); do curl -sS -o resp_schema_$i.json -w "$i %{http_code} %{time_total}\n" -H "Content-Type: application/json" --data-binary @req_schema_$i.json http://generation:8080/v1/chat/completions; done'
```

Cada salida se validó fuera del contenedor: JSON válido, solo las claves del esquema, `status` dentro de la lista, a lo sumo 4 afirmaciones, cada una con al menos una cita y solo alias de la lista; además, sin `reasoning_content` y con el contenido empezando en `{`.

**Salida (validación).** Los 20 pedidos respondieron HTTP 200.

```
n | validación | status | afirmaciones | alias citados | finish_reason | prompt_tokens | completion_tokens | s
01 | válida | answered | 1 | ['U1'] | stop | 324 | 71 | 1.19
02 | válida | answered | 1 | ['U2'] | stop | 324 | 71 | 1.07
03 | válida | answered | 1 | ['U2'] | stop | 321 | 63 | 0.97
04 | válida | answered | 2 | ['U3'] | stop | 318 | 111 | 1.57
05 | válida | answered | 1 | ['U3'] | stop | 320 | 64 | 0.97
06 | válida | answered | 1 | ['U4'] | stop | 325 | 69 | 1.03
07 | válida | answered | 1 | ['U1'] | stop | 325 | 67 | 1.00
08 | válida | answered | 2 | ['U1', 'U2'] | stop | 325 | 102 | 1.45
09 | válida | answered | 2 | ['U2', 'U4'] | stop | 329 | 106 | 1.50
10 | válida | answered | 1 | ['U3'] | stop | 320 | 63 | 0.97
11 | válida | not_determined | 0 | [] | stop | 323 | 25 | 0.50
12 | válida | not_determined | 0 | [] | stop | 325 | 25 | 0.48
13 | válida | not_determined | 0 | [] | stop | 321 | 25 | 0.49
14 | válida | not_determined | 0 | [] | stop | 325 | 25 | 0.49
15 | válida | not_determined | 0 | [] | stop | 321 | 25 | 0.48
16 | válida | not_determined | 0 | [] | stop | 323 | 25 | 0.49
17 | válida | not_determined | 0 | [] | stop | 324 | 25 | 0.49
18 | válida | not_determined | 0 | [] | stop | 323 | 25 | 0.48
19 | válida | not_determined | 0 | [] | stop | 323 | 25 | 0.49
20 | válida | not_determined | 0 | [] | stop | 321 | 25 | 0.49
Válidas: 20 de 20
```

Ejemplo de salida (pedido 09, "¿En cuántos días se integra la garantía de cumplimiento y cómo se cuentan esos días?"):

```
{
  "status": "answered",
  "claims": [
    {
      "text": "La garantía de cumplimiento se integra dentro de los cinco días hábiles de notificada la orden de compra.",
      "citations": ["U2"]
    },
    {
      "text": "Los plazos se computan en días hábiles administrativos salvo disposición expresa en contrario.",
      "citations": ["U4"]
    }
  ]
}
```

**Resultado.** Cumple: 20 de 20 salidas válidas. Las 10 preguntas con respuesta citan la unidad que corresponde y las 10 sin respuesta dan `not_determined` sin afirmaciones. Es una prueba del formato, no de calidad (la calidad se mide con las evals de la etapa 4).

Dos datos más:

- **Primera tanda descartada.** Una primera tanda de los mismos 20 pedidos, con una instrucción de prueba que solo nombraba el valor `not_determined` y no describía el formato, dio 20 de 20 salidas válidas pero todas `not_determined`, incluso las que tenían respuesta, con lo que las citas no quedaban ejercitadas. Se corrigió la instrucción de prueba (describe el formato de salida y sus dos valores) y se repitió; la tabla de arriba es la segunda tanda. Para las instrucciones de la etapa 2: el esquema solo no le explica al modelo qué significa cada campo; la instrucción tiene que describirlo.
- **El motor impone el esquema aunque contradiga al modelo.** El pedido 08 se repitió con un esquema de a lo sumo 1 afirmación y solo el alias `U3`. La salida respetó el esquema (1 afirmación, cita `["U3"]`) aunque esa cita es incorrecta para la afirmación ("La garantía de mantenimiento de oferta es del cinco por ciento..."). Confirma que la restricción la aplica el motor, y por qué el esquema de cada consulta debe listar solo los alias de las unidades recuperadas, como prevé el ADR-0002.

### 5. Pensamiento apagado

**Qué se probó.** Que la salida no traiga razonamiento previo.

**Comando.**

```
docker exec t002-client sh -c 'cd /work && curl -sS -H "Content-Type: application/json" --data-binary @req_schema_01.json http://generation:8080/apply-template'
```

**Salida (final de la plantilla aplicada).**

```
...Pregunta: ¿Cuál es el porcentaje de la garantía de mantenimiento de oferta?<turn|>\n<|turn>model\n<|channel>thought\n<channel|>
```

**Resultado.** Cumple. Con `--reasoning off` la plantilla de Gemma 4 abre y cierra un canal de pensamiento vacío antes de la respuesta, que es la forma en que el modelo lo apaga. Ninguna de las 20 respuestas con esquema ni de las 5 largas trae `reasoning_content`, y el contenido empieza directamente con la respuesta. Los tiempos lo confirman: las respuestas con esquema usan entre 25 y 111 tokens de salida.

### 6. Velocidad: pedido de unos 12.000 tokens de entrada y 800 de salida, cinco veces

**Qué se probó.** Cinco pedidos de unos 12.100 tokens de entrada (reglamento sintético de 136 artículos, distinto en cada pedido) y 800 de salida, con `max_tokens: 800` e `ignore_eos: true` para obligar a generar los 800 tokens, y `cache_prompt: false` para que no se reaproveche lo procesado en el pedido anterior. Tiempo medido por `curl` desde el contenedor cliente, de punta a punta.

**Comando.**

```
docker exec t002-client sh -c 'cd /work && for k in 1 2 3 4 5; do curl -sS -o resp_long_$k.json -w "pedido $k: HTTP %{http_code}, time_total %{time_total} s\n" -H "Content-Type: application/json" --data-binary @req_long_$k.json http://generation:8080/v1/chat/completions; done'
```

**Salida.**

```
pedido 1: HTTP 200, time_total 15.328197 s
pedido 2: HTTP 200, time_total 15.546570 s
pedido 3: HTTP 200, time_total 15.629667 s
pedido 4: HTTP 200, time_total 15.642851 s
pedido 5: HTTP 200, time_total 15.561912 s
```

| Pedido | prompt_tokens | completion_tokens | Lectura de la entrada | Generación | Total (curl) |
|---|---|---|---|---|---|
| 1 | 12.140 | 800 | 4,07 s (2.982 t/s) | 10,95 s (73,0 t/s) | 15,33 s |
| 2 | 12.101 | 800 | 3,84 s (3.154 t/s) | 10,81 s (73,9 t/s) | 15,55 s |
| 3 | 12.023 | 800 | 3,86 s (3.113 t/s) | 10,89 s (73,4 t/s) | 15,63 s |
| 4 | 12.115 | 800 | 3,88 s (3.125 t/s) | 10,87 s (73,5 t/s) | 15,64 s |
| 5 | 12.093 | 800 | 3,94 s (3.073 t/s) | 10,79 s (74,1 t/s) | 15,56 s |

En los cinco, `cache_n = 0` (sin caché) y `finish_reason = length`.

**Resultado.** Cumple: entre 15,33 y 15,64 s, por debajo de 25 s. Quedan unos 14 s del presupuesto de 30 para recuperación y armado. Es el peor caso de salida (800 tokens forzados): las respuestas con esquema de la sección 4 usan menos de 120 tokens y tardan entre 0,5 y 1,6 s con entrada corta.

### 7. Memoria de video

**Qué se probó.** Memoria de la placa con `generation` cargado y después de una consulta larga. Solo corría `generation` (y `postgres-dev`, que no usa GPU).

**Comandos.**

```
nvidia-smi --query-gpu=memory.used,memory.reserved,memory.free,memory.total --format=csv
```

Además, durante un sexto pedido largo, se leyó `memory.used` una vez por segundo y se tomó el máximo.

**Salida** (`memory.used, memory.reserved, memory.free, memory.total`).

```
Antes de levantar generation:
0 MiB, 326 MiB, 24137 MiB, 24463 MiB
Con generation cargado, sin pedidos:
7804 MiB, 326 MiB, 16334 MiB, 24463 MiB
Después de los cinco pedidos largos:
7818 MiB, 326 MiB, 16320 MiB, 24463 MiB
Máximo durante un pedido largo:
pico memory.used durante el pedido: 7818 MiB
```

**Resultado.** Cumple. `generation` ocupa 7.818 MiB (7,6 GiB) con contexto de 16.384, estable durante y después de una consulta larga: el contexto se reserva entero al arrancar. Está por debajo del tope de 16 GB del reparto y de la estimación del plan (8,6 GB, medida con contexto de 32.000). Quedan 16.320 MiB libres para `embeddings`, `reranker` y margen.

### 8. Conteo de tokens: `/tokenize` contra `prompt_tokens`

**Qué se probó.** Que `POST /tokenize` responda con la lista de tokens, y cuánto agrega la plantilla de conversación: se cuentan por separado las instrucciones (mensaje de sistema) y el mensaje del usuario, y se compara la suma con `usage.prompt_tokens` de la respuesta al mismo pedido.

**Comando** (uno por parte; el cuerpo es `{"content": "<texto de la parte>"}`).

```
docker exec t002-client sh -c 'cd /work && curl -sS -H "Content-Type: application/json" --data-binary @tok_schema_01_0.json http://generation:8080/tokenize'
```

**Salida.** HTTP 200 con una respuesta de la forma `{"tokens": [209383, 723, 155855, 929, ...]}`. Cuentas:

| Pedido | Sistema (`/tokenize`) | Usuario (`/tokenize`) | Suma | `prompt_tokens` | Diferencia |
|---|---|---|---|---|---|
| Esquema, pregunta 01 | 117 | 189 | 306 | 324 | 18 |
| Largo 1 | 12 | 12.110 | 12.122 | 12.140 | 18 |
| Excedido (sección 9) | 12 | 17.781 | 17.793 | 17.811 | 18 |

**Resultado.** Cumple. `/tokenize` responde en esta compilación. La plantilla agrega 18 tokens por pedido de dos mensajes, sin importar el largo (inicio de texto, marcas de turno y el canal de pensamiento vacío). El margen de 512 del plan alcanza con holgura; si conviene ajustarlo lo decide quien corresponda, no esta tarea. Con `response_format` la gramática no suma tokens a la entrada.

### 9. Pedido que excede el contexto

**Qué se probó.** Un pedido de 17.811 tokens (más de 16.384) a `/v1/chat/completions`.

**Comando.**

```
docker exec t002-client sh -c 'cd /work && curl -sS -o resp_over.json -w "HTTP %{http_code}, time_total %{time_total} s\n" -H "Content-Type: application/json" --data-binary @req_over.json http://generation:8080/v1/chat/completions; cat resp_over.json'
```

**Salida.**

```
HTTP 400, time_total 1.030590 s
{"error":{"code":400,"message":"request (17811 tokens) exceeds the available context size (16384 tokens), try increasing it","type":"exceed_context_size_error","n_prompt_tokens":17811,"n_ctx":16384}}
```

Registro del servidor:

```
E srv    send_error: task id = 6553, error: request (17811 tokens) exceeds the available context size (16384 tokens), try increasing it
```

**Resultado.** Cumple. El servidor rechaza el pedido con HTTP 400 y `type: exceed_context_size_error`, sin recortar ni generar. El cliente de `generation` puede reconocer ese tipo para informar `input_too_long`.

### 10. Cierre

Se detuvo el servicio con `docker compose down` y se borró el contenedor cliente `t002-client`. `postgres-dev` no se tocó.

## T-003 · Embeddings y reranker, y memoria de video

Fecha: 2026-10-02. Requisitos: REQ-008 (búsqueda por significado) y REQ-009 (señal de abstención del reranker).

Resumen: `bge-m3` y `bge-reranker-v2-m3` (GGUF FP16 de gpustack) cargan en `llama-server` con la compilación `b11347` fijada en T-002. Las cuatro similitudes de la ficha de `bge-m3` quedan a menos de 0,0011 de las publicadas. El reranker reproduce los valores publicados (5,279 y −8,181 frente a 5,26 y −8,19) **solo después de forzar** `tokenizer.ggml.add_sep_token=bool:true`, dato que el archivo GGUF no trae (sección 4). Devuelve el valor sin escala (logit), no un número entre 0 y 1. Una entrada más larga que el contexto se rechaza con HTTP 500 en los dos servicios, sin recortar. `/tokenize` responde en los dos y las listas de tokens son idénticas. Memoria de video: 10.344 MiB con los tres modelos cargados después de puntuar 65 pasajes. Reranker con 65 pasajes: 1,10 s (el primer pedido después de arrancar, 3,45 s). No se disparó ninguna condición de parada y no hizo falta el plan B.

### 1. Archivos de los modelos y sus huellas

**Origen** (ADR-0003, [F29] y [F30]). Conversiones GGUF de un tercero (gpustack) en Hugging Face, con revisión fijada en la URL de `scripts/fetch_models.sh`:

| Archivo | Repositorio y revisión | Bytes | SHA-256 |
|---|---|---|---|
| `bge-m3-FP16.gguf` | `gpustack/bge-m3-GGUF`, `2d48f1737679ad900d5c26c5aad5410e9c70fdca` (2024-10-31), licencia MIT | 1.157.671.200 | `daec91ffb5dd0c27411bd71f29932917c49cf529a641d0168496c3a501e3062c` |
| `bge-reranker-v2-m3-FP16.gguf` | `gpustack/bge-reranker-v2-m3-GGUF`, `3093af03b1a635e67b084b1d8c03c5f5e020fd05` (2024-09-29), licencia Apache-2.0 | 1.159.776.896 | `5df93be121c09c43432102ad2b9569d369ccb85c209ca7583e8ccd28f0e41b88` |

Las huellas coinciden con las que publica Hugging Face para cada archivo (`/api/models/<repo>?blobs=true`, campo `lfs.sha256`).

**Comando.**

```
CURL_EXTRA_OPTS="--ssl-no-revoke --silent --show-error" bash scripts/fetch_models.sh
```

**Salida.**

```
OK (ya estaba): gemma-4-12b-it-qat-q4_0.gguf
Descargando bge-m3-FP16.gguf ...
OK: bge-m3-FP16.gguf  sha256=daec91ffb5dd0c27411bd71f29932917c49cf529a641d0168496c3a501e3062c
Descargando bge-reranker-v2-m3-FP16.gguf ...
OK: bge-reranker-v2-m3-FP16.gguf  sha256=5df93be121c09c43432102ad2b9569d369ccb85c209ca7583e8ccd28f0e41b88
real    1m20,184s
exit=0
```

**Metadatos de los archivos** (leídos de la cabecera GGUF). Los dos son arquitectura `bert`, `context_length` 8192, `embedding_length` 1024, 24 capas, tipo de archivo 1 (FP16), tokenizador `t5` (SentencePiece de XLM-RoBERTa) con `bos=0` (`<s>`), `eos=2` y `seperator=2` (`</s>`), `add_bos_token` y `add_eos_token` en verdadero. Diferencias:

- `bge-m3` trae `bert.pooling_type = 2` (CLS), que es la agrupación del vector denso de BGE-M3.
- `bge-reranker-v2-m3` no trae `pooling_type` (el servidor usa `rank` porque se lo pide `--rerank`) ni `tokenizer.ggml.add_sep_token`. Esto último cambia los puntajes (sección 4).

**Resultado.** Cumple. `models/` y `*.gguf` siguen fuera del repositorio.

### 2. Servicios `embeddings` y `reranker`

**Configuración** (`docker-compose.yml`). Misma imagen y compilación que `generation` (`ghcr.io/ggml-org/llama.cpp:server-cuda-b11347`); misma red interna sin salida, sin puertos publicados, `models/` en solo lectura, GPU reservada, `/health` como chequeo de salud, `--offline`, `--n-gpu-layers all`, `--fit off`, `--no-context-shift`, `--parallel 1`. Propios de cada uno:

- `embeddings`: `--embeddings --pooling cls`; contexto 8192 (el del modelo).
- `reranker`: `--rerank --override-kv tokenizer.ggml.add_sep_token=bool:true`; contexto 8192.
- En los dos, `--batch-size` y `--ubatch-size` iguales al contexto. Un modelo no causal procesa cada texto en un solo lote físico; con el valor por defecto (512) cualquier pasaje de más de 512 tokens se rechazaría. Con el lote igual al contexto, todo lo que entra en el contexto se procesa y lo que no entra se rechaza.

Archivo, alias y contexto se leen de variables de entorno con valores por defecto (`.env.example`: `EMBEDDINGS_*` y `RERANKER_*`). El contexto de 8192 es el máximo del modelo; los autores del reranker recomiendan no pasar de 1.024 tokens por par por calidad (ADR-0003), cosa que controla el tamaño de los pasajes (800), no el servidor.

**Comandos.** Los pedidos se hicieron desde un contenedor cliente (`t003-client`, la misma imagen) en la red `evaluon_internal`, con los cuerpos en una carpeta temporal fuera del repositorio.

```
docker compose up -d embeddings
docker inspect -f '{{.State.Health.Status}}' evaluon-embeddings-1
docker run -d --name t003-client --network evaluon_internal -v <carpeta temporal>:/work --entrypoint sleep ghcr.io/ggml-org/llama.cpp:server-cuda-b11347 infinity
docker exec t003-client sh -c 'curl -sS http://embeddings:8080/health; curl -sS -m 10 https://huggingface.co -o /dev/null -w "%{http_code}\n"'
docker compose up -d reranker
docker exec t003-client curl -sS http://reranker:8080/health
```

**Salida.**

```
estado=healthy
embeddings-1  | srv    load_model: loading model '/models/bge-m3-FP16.gguf'
embeddings-1  | srv    load_model: initializing, n_slots = 1, n_ctx_slot = 8192, kv_unified = 'false'
embeddings-1  | srv  llama_server: model loaded
{"status":"ok"}
curl: (6) Could not resolve host: huggingface.co
```

```
estado=healthy
reranker-1  | W load: model vocab missing newline token, using special_pad_id instead
reranker-1  | W llama_init_from_model: model default pooling_type is [-1], but [4] was specified
reranker-1  | W init: embeddings required but some input tokens were not marked as outputs -> overriding
reranker-1  | srv    load_model: initializing, n_slots = 1, n_ctx_slot = 8192, kv_unified = 'false'
reranker-1  | srv  llama_server: model loaded
{"status":"ok"}
```

**Resultado.** Cumple. Los dos cargan en unos 5 a 6 s y `/health` responde `{"status":"ok"}`. Los avisos del reranker son de metadatos que le faltan al archivo (tipo de agrupación, token de salto de línea); el servidor los resuelve solo. Desde la red interna no se llega a internet.

### 3. `bge-m3`: similitudes de la ficha

**Qué se probó.** Las cuatro frases de ejemplo de la ficha de `BAAI/bge-m3` ([F1]): `["What is BGE M3?", "Defination of BM25"]` contra `["BGE M3 is an embedding model supporting dense retrieval, lexical matching and multi-vector interaction.", "BM25 is a bag-of-words retrieval function that ranks a set of documents based on the query terms appearing in each document"]`. Un solo pedido a `POST /v1/embeddings` con las cuatro; producto escalar calculado fuera del contenedor.

**Comando.**

```
docker exec t003-client sh -c 'cd /work && curl -sS -o resp_emb.json -w "HTTP %{http_code} %{time_total}s\n" -H "Content-Type: application/json" --data-binary @req_emb.json http://embeddings:8080/v1/embeddings'
```

**Salida.**

```
HTTP 200 0.307245s
{'model': 'bge-m3', 'object': 'list', 'usage': {'prompt_tokens': 82, 'total_tokens': 82}}
dims [1024, 1024, 1024, 1024] normas [1.0, 1.0, 1.0, 1.0]
```

| Par | Obtenido | Publicado | Diferencia |
|---|---|---|---|
| "What is BGE M3?" · "BGE M3 is..." | 0,6257 | 0,6265 | −0,0008 |
| "What is BGE M3?" · "BM25 is..." | 0,3471 | 0,3477 | −0,0006 |
| "Defination of BM25" · "BGE M3 is..." | 0,3489 | 0,3499 | −0,0010 |
| "Defination of BM25" · "BM25 is..." | 0,6785 | 0,678 | +0,0005 |

**Resultado.** Cumple: las cuatro a menos de 0,0011 (tolerancia: 0,02). Los vectores son de 1024 y llegan normalizados (norma 1), así que el producto escalar es la similitud coseno.

### 4. `bge-reranker-v2-m3`: pares de la ficha y escala

**Qué se probó.** Los dos pares de ejemplo de la ficha de `BAAI/bge-reranker-v2-m3` ([F6]): pregunta `what is panda?` con `hi` y con `The giant panda (Ailuropoda melanoleuca), sometimes called a panda bear or simply panda, is a bear species endemic to China.` Publicado: −8,1875 y 5,26171875 (con sigmoide, 0,000278 y 0,99484).

**Comando.**

```
docker exec t003-client sh -c 'cd /work && curl -sS -H "Content-Type: application/json" --data-binary @req_rr.json http://reranker:8080/v1/rerank'
```

**Primera corrida, con el archivo tal como viene.**

```
{"model":"bge-reranker-v2-m3","object":"list","usage":{"prompt_tokens":51,"total_tokens":51},"results":[{"index":1,"relevance_score":5.47899055480957},{"index":0,"relevance_score":-7.487493991851807}]}
```

Mismo orden, pero −7,487 y 5,479: el par negativo se apartaba 0,70 del publicado (con sigmoide, 0,00056 contra 0,00028). Diagnóstico: la pregunta tiene 5 tokens, `hi` 1 y el pasaje del panda 34 (`/tokenize`), 45 en total; `prompt_tokens` 51 significa 3 tokens especiales por par (`<s> pregunta </s> pasaje </s>`). El modelo original (XLM-RoBERTa) arma los pares con 4: `<s> pregunta </s></s> pasaje </s>`. `llama-server` agrega el separador entre pregunta y pasaje solo si el archivo trae `tokenizer.ggml.add_sep_token`, y la conversión de gpustack no lo trae (sección 1).

**Corrección.** Se fuerza el dato al cargar, sin cambiar de archivo ni de servidor: `--override-kv tokenizer.ggml.add_sep_token=bool:true`. Se probó primero en un contenedor aparte (`t003-rr-test`, borrado después) y luego quedó en `docker-compose.yml`.

**Salida con la corrección** (servicio `reranker` del compose).

```
HTTP 200 0.185420s
{"model":"bge-reranker-v2-m3","object":"list","usage":{"prompt_tokens":53,"total_tokens":53},"results":[{"index":1,"relevance_score":5.279355525970459},{"index":0,"relevance_score":-8.180519104003906}]}
```

| Par | Obtenido | Publicado | Diferencia | Sigmoide obtenida | Sigmoide publicada |
|---|---|---|---|---|---|
| panda · `hi` | −8,1805 | −8,1875 | +0,007 | 0,00028 | 0,000278 |
| panda · pasaje del panda | 5,2794 | 5,2617 | +0,018 | 0,99493 | 0,99484 |

**Resultado.** Cumple con la corrección: valores cercanos a los publicados, mismo orden, y ahora `prompt_tokens` 53 (4 especiales por par, como el original). Sin la corrección no reproduce bien el par negativo; queda anotado en el compose. Es un parámetro elegido en esta tarea: el plan y el ADR-0003 no lo prevén.

**Escala.** `/v1/rerank` devuelve en `relevance_score` el valor sin escala del modelo (logit, positivo y negativo, sin tope), ordenado de mayor a menor y con el `index` del documento en la lista enviada. No lo pasa a 0..1: la aplicación aplica la sigmoide, como prevé el ADR-0003. En la prueba de 65 pasajes (sección 7) los valores fueron de −6,64 a 4,63.

### 5. Entrada más larga que el contexto

**Qué se probó.** Un texto sintético de 11.255 tokens (más de 8192) a `embeddings` y, como pasaje, a `reranker` (junto con un pasaje corto `hola`); y el borde en `embeddings`: un texto de 7.918 tokens y otro de 8.201.

**Comandos.**

```
docker exec t003-client sh -c 'cd /work && curl -sS -w "\nHTTP %{http_code} %{time_total}s\n" -H "Content-Type: application/json" --data-binary @req_emb_long.json http://embeddings:8080/v1/embeddings'
docker exec t003-client sh -c 'cd /work && curl -sS -w "\nHTTP %{http_code} %{time_total}s\n" -H "Content-Type: application/json" --data-binary @req_rr_long.json http://reranker:8080/v1/rerank'
```

**Salida.**

```
{"error":{"code":500,"message":"input (11257 tokens) is too large to process. increase the physical batch size (current batch size: 8192)","type":"server_error"}}
HTTP 500 0.004228s
embeddings-1 | E srv    send_error: task id = 8, error: input (11257 tokens) is too large to process. increase the physical batch size (current batch size: 8192)
embeddings-1 | I slot      release: id  0 | task 8 | stop processing: n_tokens = 34, truncated = 0
```

```
{"error":{"code":500,"message":"input (11269 tokens) is too large to process. increase the physical batch size (current batch size: 8192)","type":"server_error"}}
HTTP 500 0.050709s
reranker-1 | E srv    send_error: task id = 5, error: input (11269 tokens) is too large to process. increase the physical batch size (current batch size: 8192)
```

Borde en `embeddings`:

```
7.918 tokens (/tokenize): HTTP 200 4.889235s, usage.prompt_tokens 7920
8.201 tokens (/tokenize): HTTP 500 0.004911s, "input (8204 tokens) is too large to process. increase the physical batch size (current batch size: 8192)"
```

**Resultado.** Cumple: se rechaza con error, sin recortar ni calcular (`truncated = 0`). Tres datos para los clientes de T-011:

- El código es **HTTP 500** con `type: server_error`, no 400 con `exceed_context_size_error` como en `generation` (T-002, sección 9). El cliente tiene que reconocer el rechazo por el mensaje `is too large to process` para informar `input_too_long`, y no confundirlo con una falla del servicio.
- La cuenta del mensaje incluye los tokens especiales (11.255 + 2 = 11.257 en `embeddings`; en el reranker, pregunta, pasaje y 4 especiales).
- En el reranker, un pasaje demasiado largo hace fallar el pedido entero, también los demás pasajes de la lista.

### 6. Conteo de tokens con `/tokenize` en los dos servicios

**Qué se probó.** Que `POST /tokenize` responda en `embeddings` y en `reranker` y que el mismo texto dé la misma cuenta. Textos: las cuatro frases de la ficha, un artículo sintético en español, el mismo con `add_special: true`, el de 7.918 tokens y el de 11.255.

**Comando** (por texto y por servicio; el cuerpo es `{"content": "<texto>"}`).

```
docker exec t003-client sh -c 'cd /work && curl -sS -H "Content-Type: application/json" --data-binary @tok_es.json http://embeddings:8080/tokenize'
docker exec t003-client sh -c 'cd /work && curl -sS -H "Content-Type: application/json" --data-binary @tok_es.json http://reranker:8080/tokenize'
```

**Salida.** HTTP 200 con `{"tokens": [57161, 11808, 441, 142666, 5035, 9, 164837, 3290, 8, 129826, ...]}`; con `with_pieces: true`, `[{"id":57161,"piece":" ART"},{"id":11808,"piece":"Í"},{"id":441,"piece":"C"},{"id":142666,"piece":"ULO"},...]`.

| Texto | `embeddings` | `reranker` | Listas iguales |
|---|---|---|---|
| Artículo sintético en español | 68 | 68 | sí |
| El mismo, `add_special: true` | 70 (`<s>` ... `</s>`) | 70 | sí |
| Texto de 7.918 tokens | 7.918 | 7.918 | sí |
| Texto de 11.255 tokens | 11.255 | 11.255 | sí |

Contra lo que el modelo procesa: las cuatro frases de la ficha cuentan 7, 6, 29 y 32 (74); `prompt_tokens` del pedido de embeddings fue 82 = 74 + 2 especiales por texto. En el reranker, cada par suma pregunta + pasaje + 4 especiales (sección 4).

**Resultado.** Cumple. `embeddings` responde a `/tokenize` y las dos cuentas son idénticas, token por token (mismo tokenizador). Por defecto `/tokenize` no agrega tokens especiales; lo que el modelo procesa es esa cuenta más 2 (`embeddings`) o, por par, la suma de pregunta y pasaje más 4 (`reranker`).

### 7. Memoria de video y tiempo del reranker con 65 pasajes

**Qué se probó.** Memoria de la placa con cada servicio y con los tres cargados, antes y después de puntuar 65 pasajes; tiempo de `POST /v1/rerank` con 65 pasajes. Los servicios se levantaron de a uno; los pedidos se hicieron de a uno (una sola carga de GPU por vez). Solo corrían los servicios del proyecto y `postgres-dev`, que no usa GPU.

**Pasajes.** 65 pasajes sintéticos en español (artículos de un reglamento ficticio sobre 16 temas de contrataciones), de 674 a 811 tokens según `/tokenize` del reranker (media 747), y la pregunta "¿Cuál es el plazo para integrar la garantía de cumplimiento del contrato?" (14 tokens). Total procesado: 49.706 tokens (pasajes + 65 × (14 + 4)). Es el peor caso del plan: pasajes del tamaño máximo.

**Comandos.**

```
nvidia-smi --query-gpu=memory.used,memory.reserved,memory.free,memory.total --format=csv
docker exec t003-client sh -c 'cd /work && for k in 1 2 3 4 5; do curl -sS -o resp_rr65_$k.json -w "pedido $k: HTTP %{http_code}, time_total %{time_total} s\n" -H "Content-Type: application/json" --data-binary @req_rr65.json http://reranker:8080/v1/rerank; done'
```

Durante los cinco pedidos se leyó `memory.used` cada medio segundo y se tomó el máximo. Al final se detuvieron los servicios de a uno para separar la memoria de cada uno.

**Salida (memoria, `memory.used`).**

```
Ningún servicio:                                         0 MiB
embeddings cargado:                                  1.184 MiB
embeddings después de un texto de 7.918 tokens:      1.304 MiB
embeddings + reranker cargados:                      2.489 MiB
embeddings + reranker + generation cargados:        10.336 MiB  (libres 13.802 MiB)
Pico durante los cinco pedidos de 65 pasajes:       10.344 MiB
Después de los 65 pasajes:                          10.344 MiB, reservada 326 MiB, libres 13.794 MiB, total 24.463 MiB
Detenido reranker:                                   9.107 MiB
Detenido también embeddings (solo generation):       7.804 MiB
Detenidos los tres:                                      0 MiB
```

| Servicio | Memoria de video |
|---|---|
| `generation` | 7.804 MiB |
| `embeddings` | 1.303 MiB (1.184 recién cargado) |
| `reranker` | 1.237 MiB después de los 65 pasajes (1.185 recién cargado) |
| `embeddings` + `reranker` | 2.540 MiB (tope del plan: 4 GB) |
| **Total, los tres** | **10.344 MiB (10,1 GiB)** |

Al levantar los tres juntos para la verificación final (sección 8), recién cargados, la lectura fue 10.172 MiB.

**Salida (tiempo).**

```
pedido 1: HTTP 200, time_total 3.445673 s
pedido 2: HTTP 200, time_total 1.120164 s
pedido 3: HTTP 200, time_total 1.096496 s
pedido 4: HTTP 200, time_total 1.109723 s
pedido 5: HTTP 200, time_total 1.096027 s
```

`usage.prompt_tokens` 49.706 y 65 resultados en cada uno. Los cinco dieron los mismos puntajes. Los cuatro primeros del orden son los pasajes 33, 49, 17 y 1 (4,63; 3,79; 3,64; 3,63), los cuatro que tratan la garantía de cumplimiento; el quinto queda en −1,91.

**Resultado.** Cumple. Total con los tres modelos: 10.344 MiB, dentro de 20 GB, con unos 13,8 GB libres; `embeddings` y `reranker` juntos usan 2,5 GB del cupo de 4. Puntuar no hace crecer la memoria más que unas decenas de MiB. Tiempo del reranker con 65 pasajes: 1,10 a 1,12 s, por debajo de la meta de 3 s del ADR-0003 para la recuperación completa. El primer pedido después de arrancar el servicio tarda 3,45 s (preparación de la GPU para esos tamaños de lote); conviene que el runbook o el arranque de la aplicación hagan un pedido de calentamiento, decisión que no es de esta tarea. Queda sin medir la recuperación completa (vector de la pregunta, búsquedas en Postgres y reranker), que es de la etapa 4.

### 8. Verificación y cierre

**Comando.**

```
docker compose up -d generation embeddings reranker
docker compose ps --format '{{.Service}} {{.Status}}'
docker exec t003-client sh -c 'for h in generation embeddings reranker; do echo "$h $(curl -sS http://$h:8080/health)"; done'
```

**Salida.**

```
embeddings Up 40 seconds (healthy)
generation Up 43 seconds (healthy)
reranker Up 40 seconds (healthy)
generation {"status":"ok"}
embeddings {"status":"ok"}
reranker {"status":"ok"}
```

Los pares de la ficha dieron otra vez 5,279355525970459 y −8,180519104003906.

**Resultado.** Cumple: los tres en estado sano con un solo comando. Después se borró el contenedor cliente `t003-client` y se corrió `docker compose down`. `postgres-dev` no se tocó.

**Parámetros elegidos en esta tarea, que el plan no fija:** contexto 8192 en los dos servicios (el del modelo), `--batch-size` y `--ubatch-size` iguales al contexto, `--parallel 1`, `--pooling cls` explícito en `embeddings` (coincide con el del archivo) y `--override-kv tokenizer.ggml.add_sep_token=bool:true` en `reranker`.
