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
