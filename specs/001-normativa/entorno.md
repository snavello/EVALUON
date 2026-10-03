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

## T-004 · Postgres con sus extensiones y búsqueda en español

Fecha: 2026-10-02. Requisitos: REQ-008 (vectores) y REQ-010 (búsqueda por palabras sin distinguir acentos).

Resumen: la base `evaluon` que existía en el Postgres anterior del equipo (`postgres-dev`) está vacía: no hay nada que conservar. El servicio `db` queda fijado en `pgvector/pgvector:0.8.7-pg17-bookworm` con su huella: Postgres 17.11 y pgvector 0.8.7. La imagen trae `vector`, `unaccent` y la configuración `spanish`. Una configuración de prueba derivada de `spanish` con `unaccent` encuentra "licitación" buscando "licitacion". `ts_debug` trata "297/03" y "247/2022" como una sola palabra de tipo `file`, sin separar los números. No se disparó la condición de parada. Hay una observación para T-009 sobre el orden "quitar acentos y después reducir a la raíz" (sección 5).

### 1. Postgres anterior del equipo y la base `evaluon`

**Qué se probó.** El contenedor `postgres-dev` (`pgvector/pgvector:pg17`, Postgres 17.11, pgvector 0.8.7) es de otro entorno (`C:\Users\snave\Documents\dev\entorno`, volumen `entorno-dev_pgdata`, puerto `127.0.0.1:5432`). Se consultó, solo con lecturas y con la sesión en modo de solo lectura, si tiene una base `evaluon` y qué contiene. No se detuvo, borró ni modificó nada.

**Comandos.**

```
docker exec postgres-dev psql -U dev -d desarrollo -c "SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database ORDER BY 1;"
docker exec postgres-dev psql -U dev -d evaluon -c "SET default_transaction_read_only = on;" \
  -c "SELECT nspname, nspowner::regrole FROM pg_namespace ORDER BY 1;" \
  -c "SELECT n.nspname, c.relname, c.relkind, c.reltuples::bigint, s.n_live_tup FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_stat_user_tables s ON s.relid=c.oid WHERE n.nspname NOT IN ('pg_catalog','information_schema','pg_toast') AND c.relkind IN ('r','p','v','m','S','f') ORDER BY 1,2;" \
  -c "SELECT extname, extversion FROM pg_extension;" \
  -c "SELECT cfgname FROM pg_ts_config WHERE cfgnamespace <> 'pg_catalog'::regnamespace;"
# Objetos que no pertenecen a una extensión (tablas, secuencias, vistas; funciones; tipos),
# contados con pg_depend (deptype 'e'), también en modo de solo lectura.
```

**Salida.**

```
  datname   | pg_size_pretty
------------+----------------
 desarrollo | 7478 kB
 evaluon    | 7694 kB
 mitrabajo  | 7321 kB
 postgres   | 7478 kB
 template0  | 7321 kB
 template1  | 7550 kB

Esquemas de evaluon: information_schema, pg_catalog, pg_toast, public (sin esquemas propios)
Tablas, vistas, secuencias:          (0 rows)
Extensiones:                         plpgsql 1.0, vector 0.8.7
Configuraciones de búsqueda propias: (0 rows)
objetos_fuera_de_extensiones: 0
funciones_propias:            0
tipos_propios:                0
dueño de la base evaluon:     dev
```

**Resultado.** La base `evaluon` de `postgres-dev` existe pero está vacía: no tiene esquemas, tablas, filas, funciones ni tipos propios. Solo tiene instalada la extensión `vector`, cuyas funciones son las que se ven en `public`. No hay datos que conservar, así que se sigue con la tarea. El servicio `db` del proyecto es independiente: tiene su propio volumen y no publica puertos, por lo que no choca con el puerto 5432 de `postgres-dev`. `postgres-dev` sigue funcionando y en estado sano. Si se retira o no, lo decide el responsable.

### 2. Imagen fijada y servicio `db`

**Etiqueta.** En Docker Hub, para Postgres 17 y pgvector 0.8.x, la más reciente es `0.8.7-pg17`, publicada el 2026-10-01. Se publica en dos variantes de Debian: `bookworm` (12) y `trixie` (13). Hoy `0.8.7-pg17` y `pg17` apuntan a la misma huella que `0.8.7-pg17-bookworm`. Las etiquetas con versión **se vuelven a publicar**: por ejemplo, `0.8.0-pg17` tiene fecha de 2025-08-15, aunque pgvector 0.8.0 es de 2024. Esto pasa cada vez que sale una versión menor de Postgres. Por eso, en `docker-compose.yml` la imagen queda fijada por etiqueta y por huella:

```
pgvector/pgvector:0.8.7-pg17-bookworm@sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d
```

| Dato | Valor |
|---|---|
| Etiqueta | `0.8.7-pg17-bookworm` (se nombra la variante de Debian para que no cambie si la etiqueta sin variante pasa a `trixie`) |
| Huella (índice de la imagen, `RepoDigests`) | `sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d` |
| Creada | 2026-10-01T17:35:53Z |
| Postgres | 17.11 (Debian 17.11-1.pgdg12+2), Debian 12.15 |
| pgvector | 0.8.7 |
| `unaccent` | 1.1 (contrib) |

**Comandos.**

```
curl -s "https://hub.docker.com/v2/repositories/pgvector/pgvector/tags?page_size=100&name=pg17"
docker pull pgvector/pgvector:0.8.7-pg17-bookworm
docker image inspect pgvector/pgvector:0.8.7-pg17-bookworm --format '{{json .RepoDigests}} {{.Id}} {{.Created}}'
docker run --rm --entrypoint sh pgvector/pgvector:0.8.7-pg17-bookworm -c 'echo $PG_VERSION; postgres --version; cat /etc/debian_version; ls /usr/share/postgresql/17/extension | grep -E "^(vector|unaccent)\.control"; ls /usr/share/postgresql/17/tsearch_data | grep -i spanish'
```

**Salida.**

```
0.8.7-pg17          2026-10-01T17:36:12Z sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d
0.8.7-pg17-bookworm 2026-10-01T17:36:15Z sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d
0.8.7-pg17-trixie   2026-10-01T17:46:55Z sha256:7a7e9f22015b67edb4bef5c59daeebcd7e74bfa570df6ce60ae01237c8648a84
pg17                2026-10-01T17:36:06Z sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d

["pgvector/pgvector@sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d"] sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d 2026-10-01T17:35:53.866963013Z
17.11-1.pgdg12+2
postgres (PostgreSQL) 17.11 (Debian 17.11-1.pgdg12+2)
12.15
unaccent.control
vector.control
spanish.stop
```

**Configuración** (`docker-compose.yml`, servicio `db`):

- Red `internal`, la misma red sin salida a internet de los servicios de IA. No publica puertos.
- Volumen con nombre `pgdata`, que Docker crea como `evaluon_pgdata` (proyecto `evaluon`), montado en `/var/lib/postgresql/data`.
- Credenciales por variables de entorno (`.env.example`): `POSTGRES_DB` y `POSTGRES_USER`, las dos `evaluon` por defecto, y `POSTGRES_PASSWORD` **sin valor por defecto**. Si falta la clave, `docker compose` se detiene con el mensaje "Falta POSTGRES_PASSWORD (copiar .env.example a .env y completarla)". Docker Compose resuelve las variables de todo el archivo, así que desde esta tarea **cualquier** orden de `docker compose` necesita la clave, aunque se levanten solo los servicios de IA. Esto incluye las órdenes que figuran en las secciones de T-002 y T-003.
- Chequeo de salud: `pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"`, cada 10 s, con 5 reintentos y 30 s de arranque. `restart: unless-stopped`, como los demás servicios.
- La clave solo se lee al crear el volumen por primera vez. Si se cambia en `.env` después, la base sigue con la clave anterior.

**Comandos.** La clave de la prueba se generó al azar en el shell y no se guardó en ningún archivo.

```
export POSTGRES_PASSWORD=$(py -3 -c "import secrets;print(secrets.token_urlsafe(32))")
docker compose up -d db
docker inspect -f '{{.State.Health.Status}}' evaluon-db-1
docker compose ps --format '{{.Service}} {{.Status}} {{.Ports}}'
docker inspect -f '{{.Config.Image}} {{.Image}}' evaluon-db-1
echo "puertos=[$(docker port evaluon-db-1)]"
docker network inspect -f '{{.Internal}}' evaluon_internal
docker exec -i evaluon-db-1 psql -U evaluon -X -d evaluon -c "SELECT version();" -c "SHOW server_encoding;" -c "SHOW default_text_search_config;" -c "SELECT name, default_version FROM pg_available_extensions WHERE name IN ('vector','unaccent');"
```

**Salida.**

```
Container evaluon-db-1 Started
estado=healthy
db Up 7 seconds (healthy) 5432/tcp
pgvector/pgvector:0.8.7-pg17-bookworm@sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d
puertos=[]
true
 PostgreSQL 17.11 (Debian 17.11-1.pgdg12+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 12.2.0-14+deb12u1) 12.2.0, 64-bit
 server_encoding: UTF8
 default_text_search_config: pg_catalog.english
 unaccent | 1.1
 vector   | 0.8.7
```

La base `evaluon` se crea con codificación UTF8 y orden `en_US.utf8` (proveedor `libc`). La configuración de búsqueda por omisión del servidor es `english`. Esto no afecta al sistema si las consultas y la columna `tsv` nombran siempre la configuración, como indica el plan (`spanish_unaccent`).

**Resultado.** Cumple: el servicio queda sano en unos 7 s, no publica puertos y está solo en la red interna.

### 3. Pruebas 1 a 3: `vector`, `unaccent` y `\dF`

Las pruebas se hicieron dentro del contenedor (`psql` por el socket local), en una base de prueba `t004_prueba` que se borró al terminar (sección 7).

**Comandos.**

```
docker exec -i evaluon-db-1 psql -U evaluon -X -d evaluon -c "CREATE DATABASE t004_prueba;"
docker exec -i evaluon-db-1 psql -U evaluon -X -d t004_prueba   # con estas órdenes por la entrada estándar:
CREATE EXTENSION vector;
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
SELECT '[1,2,3]'::vector <=> '[1,2,4]'::vector AS distancia_coseno;
CREATE EXTENSION unaccent;
SELECT extname, extversion FROM pg_extension WHERE extname = 'unaccent';
SELECT unaccent('licitación pública, adjudicación, órgano, cesión, pingüino, Ñandú');
\dF
\dF+ spanish
```

**Salida.**

```
CREATE EXTENSION
 extname | extversion
---------+------------
 vector  | 0.8.7

  distancia_coseno
---------------------
 0.00853986601633272

CREATE EXTENSION
 extname  | extversion
----------+------------
 unaccent | 1.1

                             unaccent
-------------------------------------------------------------------
 licitacion publica, adjudicacion, organo, cesion, pinguino, Nandu

               List of text search configurations
   Schema   |    Name    |              Description
------------+------------+---------------------------------------
 pg_catalog | arabic     | configuration for arabic language
 ...        (se omiten las de otros idiomas)
 pg_catalog | simple     | simple configuration
 pg_catalog | spanish    | configuration for spanish language
 ...
(29 rows)

Text search configuration "pg_catalog.spanish"
Parser: "pg_catalog.default"
      Token      | Dictionaries
-----------------+--------------
 asciihword      | spanish_stem
 asciiword       | spanish_stem
 email           | simple
 file            | simple
 float           | simple
 host            | simple
 hword           | spanish_stem
 hword_asciipart | spanish_stem
 hword_numpart   | simple
 hword_part      | spanish_stem
 int             | simple
 numhword        | simple
 numword         | simple
 sfloat          | simple
 uint            | simple
 url             | simple
 url_path        | simple
 version         | simple
 word            | spanish_stem
```

**Resultado.** Cumple. `SELECT extversion FROM pg_extension` da `vector` 0.8.7 y la distancia de coseno funciona. `CREATE EXTENSION unaccent` funciona (versión 1.1) y quita tildes, diéresis y la tilde de la ñ (`Ñandú` queda como `Nandu`). `\dF` muestra `pg_catalog.spanish`, con el diccionario `spanish_stem` (Snowball y su lista de palabras vacías `spanish.stop`).

### 4. Prueba 4: configuración de prueba derivada de `spanish` con `unaccent`

**Qué se probó.** Se creó una configuración de prueba, `t004.spanish_unaccent_prueba`, en un esquema de prueba dentro de la base de prueba. No es la configuración definitiva `spanish_unaccent`, que crea T-009. Es una copia de `spanish` que primero quita acentos y después reduce a la raíz, como pide el plan. Se probó contra tres pasajes sintéticos.

**Comandos.**

```
CREATE SCHEMA t004;
CREATE TEXT SEARCH CONFIGURATION t004.spanish_unaccent_prueba (COPY = pg_catalog.spanish);
ALTER TEXT SEARCH CONFIGURATION t004.spanish_unaccent_prueba
  ALTER MAPPING FOR hword, hword_part, word WITH unaccent, spanish_stem;
CREATE TABLE t004.pasaje (id int, texto text);
INSERT INTO t004.pasaje VALUES
  (1, 'La licitación pública se adjudicará a la oferta más conveniente.'),
  (2, 'Las licitaciones privadas se rigen por el artículo 25.'),
  (3, 'La contratación directa procede por exclusividad.');
SELECT id, texto FROM t004.pasaje
 WHERE to_tsvector('t004.spanish_unaccent_prueba', texto)
    @@ websearch_to_tsquery('t004.spanish_unaccent_prueba', 'licitacion');
-- Comparación con spanish sin unaccent, búsqueda de "articulo" y palabras vacías con tilde.
```

**Salida.**

```
Búsqueda "licitacion" con la configuración de prueba:
 id |                              texto
----+------------------------------------------------------------------
  1 | La licitación pública se adjudicará a la oferta más conveniente.
(1 row)

Misma búsqueda con spanish sin unaccent:
(0 rows)

Búsqueda "articulo" (sin tilde) con la configuración de prueba:  id 2

       tsv_unaccent        |     tsv_spanish
---------------------------+----------------------
 'licitacion':2 'public':3 | 'licit':2 'public':3

Palabras vacías con tilde ("él está aquí"):  spanish 'aqu':3 | prueba 'aqui':3
```

**Resultado.** Cumple. Buscando "licitacion" se encuentra el pasaje con "licitación"; con `spanish` sola no se encuentra. "articulo" encuentra "artículo". Las palabras vacías con tilde ("él", "está") se siguen descartando después de quitar los acentos.

### 5. Observación para T-009: quitar acentos antes de reducir a la raíz pierde la raíz de "-ación"

Esta observación no es parte de las cuatro pruebas, pero apareció al hacerlas. El lematizador Snowball de español reconoce sufijos con tilde, como "-ación", "-ición" o "-ía". Si los acentos se quitan **antes**, como pide el plan para `spanish_unaccent`, el singular de esas palabras deja de reducirse a la raíz. El plural sí se reduce, porque "-aciones" no lleva tilde. Resultado: singular y plural dejan de coincidir.

**Comando** (en la base de prueba).

```
SELECT w, to_tsvector('spanish', w), to_tsvector('t004.spanish_unaccent_prueba', w)
FROM unnest(ARRAY['licitación','licitacion','licitaciones','licitar','adjudicación','adjudicaciones',
  'contratación','contrataciones','garantía','garantías','artículo','artículos','órgano','pública','públicas']) AS w;
```

**Salida.**

```
    palabra     |    spanish     | unaccent_y_raiz
----------------+----------------+------------------
 licitación     | 'licit':1      | 'licitacion':1
 licitacion     | 'licitacion':1 | 'licitacion':1
 licitaciones   | 'licit':1      | 'licit':1
 licitar        | 'licit':1      | 'licit':1
 adjudicación   | 'adjud':1      | 'adjudicacion':1
 adjudicaciones | 'adjud':1      | 'adjud':1
 contratación   | 'contrat':1    | 'contratacion':1
 contrataciones | 'contrat':1    | 'contrat':1
 garantía       | 'garant':1     | 'garanti':1
 garantías      | 'garant':1     | 'garanti':1
 artículo       | 'articul':1    | 'articul':1
 artículos      | 'articul':1    | 'articul':1
 órgano         | 'organ':1      | 'organ':1
 pública        | 'public':1     | 'public':1
 públicas       | 'public':1     | 'public':1

Búsqueda "licitacion" contra el pasaje 2 ("Las licitaciones privadas..."):
 unaccent_licitacion = f   |   spanish con "licitación" = t
```

**Lectura.** Con la configuración del plan, buscar "licitacion" o "licitación" no encuentra un pasaje que solo dice "licitaciones", y viceversa. Lo mismo pasa con "adjudicación" y "adjudicaciones", y con "contratación" y "contrataciones". Con `spanish` sola, en cambio, singular y plural coinciden siempre que la búsqueda lleve la tilde. La prueba de REQ-010 ("licitacion" encuentra "licitación") pasa igual, y "garantía" y "garantías" siguen coincidiendo entre sí. Esta tarea no cambia nada al respecto: la configuración definitiva es de T-009 y su definición está en el plan. Se informa al Coordinador para que decida si la definición de `spanish_unaccent` se mantiene.

### 6. Prueba 5: `ts_debug` sobre "297/03" y "247/2022"

**Comandos.**

```
SELECT alias, token, dictionaries, lexemes FROM ts_debug('t004.spanish_unaccent_prueba', 'Disposición 297/03');
SELECT alias, token, dictionaries, lexemes FROM ts_debug('t004.spanish_unaccent_prueba', 'Disposición 247/2022');
SELECT alias, token, dictionaries, lexemes FROM ts_debug('spanish', 'Disposición 297/03 y 247/2022');
SELECT to_tsvector('t004.spanish_unaccent_prueba', 'Disposición AFIP N° 297/03 y Disposición 247/2022');
-- ¿Coincide la búsqueda por el número entero, por una parte o con el año en cuatro cifras?
```

**Salida.**

```
 alias |    token    |      dictionaries       |    lexemes
-------+-------------+-------------------------+---------------
 word  | Disposición | {unaccent,spanish_stem} | {Disposicion}
 blank |             | {}                      |
 file  | 297/03      | {simple}                | {297/03}

 word  | Disposición | {unaccent,spanish_stem} | {Disposicion}
 blank |             | {}                      |
 file  | 247/2022    | {simple}                | {247/2022}

   alias   |    token    |  dictionaries  |    lexemes
-----------+-------------+----------------+---------------
 word      | Disposición | {spanish_stem} | {disposicion}
 file      | 297/03      | {simple}       | {297/03}
 asciiword | y           | {spanish_stem} | {}
 file      | 247/2022    | {simple}       | {247/2022}

                           tsv
----------------------------------------------------------
 '247/2022':7 '297/03':4 'afip':2 'disposicion':1,6 'n':3

 coincide_297_03 | coincide_297 | coincide_297_2003 | coincide_247_2022 | coincide_247
-----------------+--------------+-------------------+-------------------+--------------
 t               | f            | f                 | t                 | f

websearch_to_tsquery('297/03') = '297/03'   websearch_to_tsquery('247/2022') = '247/2022'
```

**Resultado.** El analizador por omisión toma "297/03" y "247/2022" como un único elemento de tipo `file` (ruta de archivo). El diccionario `simple` lo guarda entero, con la barra, y no lo separa en números. Por eso:

- buscar "297/03" encuentra "297/03", y buscar "247/2022" encuentra "247/2022";
- buscar solo "297" o solo "247" **no** los encuentra;
- buscar "297/2003" **no** encuentra "297/03": cada forma de escribir el año es un elemento distinto.

Además, "N°" deja un elemento suelto `n`, y en `ts_debug` el lexema intermedio de `unaccent` conserva la mayúscula (`Disposicion`), aunque `to_tsvector` lo guarda en minúsculas (`disposicion`). Como dice el plan, las referencias exactas no dependen de esto. Para que la búsqueda por palabras encuentre una norma por número hace falta escribirlo tal como figura en el texto.

### 7. Cómo quedó la base y cierre

**Comandos.**

```
docker exec -i evaluon-db-1 psql -U evaluon -X -d evaluon -c "DROP DATABASE t004_prueba;" \
  -c "SELECT datname FROM pg_database ORDER BY 1;" -c "SELECT extname, extversion FROM pg_extension;" \
  -c "SELECT count(*) AS tablas FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema');" \
  -c "SELECT count(*) AS configs_propias FROM pg_ts_config WHERE cfgnamespace <> 'pg_catalog'::regnamespace;"
docker ps --format '{{.Names}} {{.Status}}'
docker compose down -v
```

**Salida.**

```
DROP DATABASE
 evaluon, postgres, template0, template1
 extensiones en evaluon: plpgsql 1.0 (vector y unaccent no están instaladas en evaluon)
 tablas: 0
 configs_propias: 0
evaluon-db-1 Up About a minute (healthy)
postgres-dev Up 7 hours (healthy)
```

**Resultado.** Todo lo que crearon las pruebas (extensiones, esquema `t004`, configuración `spanish_unaccent_prueba`, tabla de pasajes) quedó dentro de `t004_prueba`, y esa base se borró. En `evaluon` no quedó ningún objeto que choque con las migraciones de T-008 (extensiones) ni de T-009 (`spanish_unaccent`). Al final se corrió `docker compose down -v`, que borró también el volumen `evaluon_pgdata`. Ese volumen solo tenía la base vacía, y además había quedado iniciado con la clave al azar de la prueba, que no se guardó. Como la clave solo se lee al crear el volumen, conservarlo habría dejado la base con una clave desconocida. La próxima vez que se levante, `docker compose up -d db` crea la base desde cero con la clave de `.env`. `postgres-dev` no se tocó.

**Decisiones de esta tarea que el plan no fija:** fijar la imagen por etiqueta y huella, con la variante `bookworm` nombrada en la etiqueta; usuario y base `evaluon` por defecto; `POSTGRES_PASSWORD` obligatoria y sin valor por defecto; chequeo de salud con `pg_isready`; volumen `pgdata` (`evaluon_pgdata`).

## T-005 · Esqueleto de Django con sus librerías

Fecha: 2026-10-02. Requisitos: REQ-013 (habilita la pantalla) y REQ-016 (habilita el ingreso). Cierra "Django y sus librerías" de "Sin verificar y cómo se cierra" en lo que toca a la etapa 0: compatibilidad de WhiteNoise, pytest-django y `pgvector` con Django 6.1.

Resumen: Django 6.1.1 con todas sus librerías funciona; **no hizo falta el plan B** (Django 6.0). Imagen propia sobre Python 3.12.15 (Debian 13), Tesseract 5.5.0 y `spa.traineddata` de `tessdata_best` con huella verificada; sin PyTorch. Los seis servicios levantan con `docker compose up -d`; el test de humo pasa con todo arriba y con solo `db`.

### 1. Versiones fijadas

**Imagen base.** `python:3.12.15-slim-trixie@sha256:29113dcae7aad06daa8e95260fa09f27d62be33b9687ea3774f771d601a02256` (índice de la etiqueta; imagen `linux/amd64` `sha256:6b1f85a08c199d29d5b6d71ab9c27bd5b3b393492e01216a15758ff69c4be8b8`, creada 2026-10-01T21:49:55Z). Python 3.12.15 sobre Debian 13.

- Se fija por etiqueta con la versión completa de Python y por huella, como `db` en T-004. La etiqueta `3.12-slim-trixie` apunta hoy a la misma imagen `amd64` pero a otro índice (`sha256:dddfd7e0…`); por eso la huella anotada es la de la etiqueta que figura en el `Dockerfile`.
- Se eligió Debian 13 (`trixie`) y no Debian 12 (`bookworm`) por la versión de Tesseract que trae cada una: 5.5.0 contra 5.3.0. El ADR-0004 habla de Tesseract 5.5.3; ninguna de las dos la trae, y la 5.5.0 es la más cercana.

**Paquetes de Debian.** `tesseract-ocr` fijado en `5.5.0-1+b1`; quedan instalados `libtesseract5 5.5.0-1+b1`, `libleptonica6 1.84.1-4`, `tesseract-ocr-eng` y `tesseract-ocr-osd` `1:4.1.0-2` (dependencias del paquete; no se usan para español). No se instala `tesseract-ocr-spa`: el modelo de español es el de `tessdata_best` (punto 2). Si Debian publica una revisión nueva del paquete y retira la anterior, la construcción falla en lugar de cambiar de versión sin aviso; en ese caso se actualiza la línea del `Dockerfile` y esta sección.

**Dependencias de Python** (`pyproject.toml`, versión fija; son las últimas publicadas al 2026-10-02 según `pip index versions`):

| Biblioteca | Versión | Para qué |
|---|---|---|
| Django | 6.1.1 | Aplicación (ADR-0005) |
| psycopg (con `psycopg-binary`) | 3.3.6 | Postgres; la variante binaria trae su propia `libpq` |
| pgvector | 0.5.0 | Campo de vector y distancias para Django |
| argon2-cffi | 25.1.0 | Claves con Argon2id (T-006) |
| gunicorn | 26.2.0 | Servidor de la aplicación |
| whitenoise | 6.12.0 | Archivos estáticos |
| pdfplumber | 0.11.10 | PDF con texto (ADR-0004) |
| pypdfium2 | 5.13.0 | Dibujar páginas para el reconocimiento de texto |
| pytesseract | 0.3.13 | Llamar a Tesseract |
| beautifulsoup4 | 4.15.0 | Página web guardada |
| lxml | 6.1.3 | Analizador de HTML para BeautifulSoup |
| PyYAML | 6.0.3 | Casos de las evals (`evals/casos/EV-NNN.yaml`); la biblioteca estándar no lee YAML |
| pytest | 9.1.1 | Pruebas (dependencia opcional `test`, instalada en la imagen) |
| pytest-django | 4.14.0 | Pruebas con Django |
| setuptools | 84.0.0 | Solo para instalar las dependencias al construir la imagen |

No se agregó biblioteca de cliente HTTP: los clientes de `evaluon/ai/` (T-011) pueden usar `urllib.request` de la biblioteca estándar, que alcanza para pedidos JSON con tiempo de espera. Si T-011 encuentra que no alcanza, se informa y se agrega en una tarea que liste `pyproject.toml`.

**Dependencias indirectas** que resolvió `pip` al construir (no están fijadas en `pyproject.toml`; se anotan para poder reproducir la imagen): argon2-cffi-bindings 26.1.0, asgiref 3.12.1, cffi 2.1.1, charset-normalizer 3.5.2, cryptography 50.0.2, iniconfig 2.3.0, packaging 26.3, pdfminer.six 20260107 (fijada por pdfplumber), pillow 12.3.0, pluggy 1.6.0, pycparser 3.0, Pygments 2.21.0, soupsieve 2.10, sqlparse 0.6.0, typing_extensions 4.16.0. No hay `torch` ni `numpy` en la imagen.

**Comandos.**

```
docker pull python:3.12.15-slim-trixie
docker buildx imagetools inspect python:3.12.15-slim-trixie
docker run --rm python:3.12-slim-<bookworm|trixie> sh -c 'apt-get update -qq; apt-cache policy tesseract-ocr'
docker run --rm python:3.12-slim-trixie sh -c 'for p in django psycopg pgvector ...; do pip index versions $p | head -1; done'
docker compose run --rm --no-deps app pip freeze
```

**Salida (extracto).**

```
Name:      docker.io/library/python:3.12.15-slim-trixie
Digest:    sha256:29113dcae7aad06daa8e95260fa09f27d62be33b9687ea3774f771d601a02256
  Name:        docker.io/library/python:3.12.15-slim-trixie@sha256:6b1f85a08c199d29d5b6d71ab9c27bd5b3b393492e01216a15758ff69c4be8b8
  Platform:    linux/amd64
== bookworm   tesseract-ocr  Candidate: 5.3.0-2
== trixie     tesseract-ocr  Candidate: 5.5.0-1+b1
django (6.1.1)  psycopg (3.3.6)  pgvector (0.5.0)  argon2-cffi (25.1.0)  gunicorn (26.2.0)
whitenoise (6.12.0)  pytest (9.1.1)  pytest-django (4.14.0)  pdfplumber (0.11.10)  pypdfium2 (5.13.0)
pytesseract (0.3.13)  beautifulsoup4 (4.15.0)  lxml (6.1.3)  pyyaml (6.0.3)
Django==6.1.1 ... whitenoise==6.12.0   (pip freeze dentro de la imagen; la lista completa está arriba)
```

### 2. Tesseract y `spa.traineddata` de `tessdata_best`

**Qué se probó.** Que la imagen traiga Tesseract, informe su versión y tenga el modelo de español de `tessdata_best` con la huella esperada.

**Origen del modelo.** Repositorio `tesseract-ocr/tessdata_best`, etiqueta `4.1.0` (commit `e2aad9b983032bb1beff9133104a67cdbb87ca4d`, la última etiqueta publicada). El archivo `spa.traineddata` no cambió desde su incorporación al repositorio (2017-09-14). Se bajó desde dos direcciones (`raw.githubusercontent.com/.../e2aad9b9.../spa.traineddata` y `github.com/.../raw/e2aad9b9.../spa.traineddata`) y las dos dieron la misma huella. El `Dockerfile` lo incorpora con `ADD --checksum=sha256:...`: si la huella no coincide, la construcción falla. Queda en la carpeta de modelos por omisión de Tesseract, así que no hace falta `TESSDATA_PREFIX`.

| Dato | Valor |
|---|---|
| Archivo | `/usr/share/tesseract-ocr/5/tessdata/spa.traineddata` |
| Tamaño | 13.570.187 bytes |
| Huella SHA-256 | `e2c1ffdad8b30f26c45d4017a9183d3a7f9aa69e59918be4f88b126fac99ab2c` |

**Comandos.**

```
docker compose run --rm app tesseract --version
docker compose run --rm app tesseract --list-langs
docker compose run --rm --no-deps app sha256sum /usr/share/tesseract-ocr/5/tessdata/spa.traineddata
```

**Salida.**

```
tesseract 5.5.0
 leptonica-1.84.1
  libgif 5.2.2 : libjpeg 6b (libjpeg-turbo 2.1.5) : libpng 1.6.48 : libtiff 4.7.0 : zlib 1.3.1 : libwebp 1.5.0 : libopenjp2 2.5.3
 Found AVX2
 Found AVX
 Found FMA
 Found SSE4.1
 Found OpenMP 201511
 Found libarchive 3.7.4 zlib/1.3.1 liblzma/5.8.1 bz2lib/1.0.8 liblz4/1.10.0 libzstd/1.5.7
 Found libcurl/8.14.1 OpenSSL/3.5.7 zlib/1.3.1 brotli/1.1.0 zstd/1.5.7 libidn2/2.3.8 libpsl/0.21.2 libssh2/1.11.1 nghttp2/1.64.0 nghttp3/1.8.0 librtmp/2.3 OpenLDAP/2.6.10

List of available languages in "/usr/share/tesseract-ocr/5/tessdata/" (3):
eng
osd
spa

e2c1ffdad8b30f26c45d4017a9183d3a7f9aa69e59918be4f88b126fac99ab2c  /usr/share/tesseract-ocr/5/tessdata/spa.traineddata
```

**Resultado.** Cumple. La huella del modelo de español es la que el registro de auditoría de cada carga tiene que anotar (plan, "Registro de auditoría").

### 3. Proyecto Django, servicios `migrate` y `app`

**Qué se armó.** Proyecto vacío (`manage.py`, `evaluon/settings.py`, `urls.py` sin rutas, `wsgi.py`), sin aplicaciones propias ni modelos. En `INSTALLED_APPS` solo está `django.contrib.staticfiles`: `auth` y `sessions` los suma T-006 junto con el usuario propio, porque Django pide definir el modelo de usuario antes de la primera migración. Configuración por variables de entorno: `DJANGO_SECRET_KEY` (obligatoria, sin valor por defecto: sin ella Django no arranca y lo dice), `DJANGO_DEBUG` (falso por omisión), `DJANGO_ALLOWED_HOSTS`, `POSTGRES_*` (las mismas que `db`), `APP_PORT` y `DJANGO_STATIC_ROOT`; todas documentadas en `.env.example`. Idioma `es-ar` y hora de Buenos Aires.

- **Imagen** (`Dockerfile`): la comparten `migrate` y `app` (`evaluon-app:local`). Corre con un usuario sin privilegios (`evaluon`, uid 1000). Al construir reúne los archivos estáticos con `collectstatic`, que sirve WhiteNoise. Tamaño: 609 MB.
- **Código montado.** `evaluon/`, `tests/`, `scripts/`, `manage.py` y `pyproject.toml` se montan en solo lectura sobre la imagen, para que `docker compose run --rm app pytest` pruebe siempre el código de la copia de trabajo y no el que quedó en la imagen. Un cambio en `pyproject.toml`, en el `Dockerfile` o en los archivos estáticos que sirve Gunicorn necesita reconstruir: `docker compose build app` (o `docker compose up -d --build`).
- **`migrate`** corre `scripts/migrate_on_start.sh` y termina. "Base vacía" quiere decir: ninguna tabla fuera de los esquemas del sistema, salvo `django_migrations` sin migraciones aplicadas.
- **`app`**: Gunicorn 26.2.0, un proceso con cuatro hilos (`gthread`), espera de 120 s; puerto publicado solo en `127.0.0.1:${APP_PORT:-8000}`; `corpus/` en solo lectura y `evals/` con escritura; espera a `db` y a los tres servicios de IA en estado sano y a que `migrate` termine bien. Está en la red `internal` y además en una red `web`, que existe solo para publicar el puerto: una red interna de Docker no publica puertos (comprobado: un contenedor solo en una red `--internal`, con `-p 127.0.0.1:18765:8000`, no muestra puertos en `docker port` y no responde en ese puerto). Chequeo de salud: pide la hoja de estilos con `urllib` (la imagen no trae `curl`).
- **`.gitattributes`** fija fin de línea LF para `*.sh` y el `Dockerfile` (el repositorio usa `core.autocrlf=true`). **`.dockerignore`** deja fuera de la imagen `.git`, `.env`, `models/`, `corpus/`, `evals/`, `backups/`, `docs/`, `specs/` y `tools/`.

**Comandos.**

```
docker compose build
docker compose up -d
docker compose ps -a
docker compose logs migrate app
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://127.0.0.1:8000/static/css/evaluon.css
```

**Salida.**

```
SERVICE      STATUS                        PORTS
app          Up 7 seconds (healthy)        127.0.0.1:8000->8000/tcp
db           Up About a minute (healthy)   5432/tcp
embeddings   Up 49 seconds (healthy)
generation   Up 48 seconds (healthy)
migrate      Exited (0) 47 seconds ago
reranker     Up 53 seconds (healthy)

migrate-1  | migrate: la base está vacía; se aplican las migraciones.
migrate-1  | Operations to perform:
migrate-1  |   Apply all migrations: (none)
migrate-1  | Running migrations:
migrate-1  |   No migrations to apply.
app-1      | [INFO] Starting gunicorn 26.2.0
app-1      | [INFO] Listening at: http://0.0.0.0:8000 (1)
app-1      | [INFO] Using worker: gthread
app-1      | "GET /static/css/evaluon.css HTTP/1.1" 200 0 "-" "Python-urllib/3.12"

200 text/css; charset="utf-8"
```

**Resultado.** Cumple: los seis servicios levantan con una orden; `migrate` es de una sola corrida y queda terminado con código 0, los otros cinco quedan arriba y sanos. Sin migraciones, `migrate` no crea ninguna tabla: la base `evaluon` sigue vacía (sin `django_migrations`), así que la primera migración de T-006 se aplica sola al levantar.

### 4. Las tres ramas de `migrate_on_start.sh`

**Qué se probó.** En una base aparte (`t005_prueba`), borrada al terminar: base vacía, base con datos sin migraciones pendientes, y base con datos con migraciones pendientes. Para la tercera se usó una configuración de prueba fuera del repositorio que solo suma `django.contrib.contenttypes` a `INSTALLED_APPS`, montada en el contenedor para esa corrida.

**Comandos.**

```
docker exec -i evaluon-db-1 sh -c 'psql -U "$POSTGRES_USER" -d evaluon -c "CREATE DATABASE t005_prueba;"'
docker compose run --rm --no-deps -e POSTGRES_DB=t005_prueba migrate
docker exec -i evaluon-db-1 sh -c 'psql ... -d t005_prueba -c "CREATE TABLE datos (id int); INSERT INTO datos VALUES (1);"'
docker compose run --rm --no-deps -e POSTGRES_DB=t005_prueba migrate
docker compose run --rm --no-deps -e POSTGRES_DB=t005_prueba -e DJANGO_SETTINGS_MODULE=t005_settings \
  -v <carpeta temporal>/t005_settings.py:/app/t005_settings.py:ro migrate
docker exec -i evaluon-db-1 sh -c 'psql ... -d evaluon -c "DROP DATABASE t005_prueba;"'
```

**Salida.**

```
migrate: la base está vacía; se aplican las migraciones.
...  No migrations to apply.                                         código 0

migrate: la base tiene datos; solo se comprueba que no haya migraciones pendientes.
migrate: no hay migraciones pendientes.                              código 0

migrate: la base tiene datos; solo se comprueba que no haya migraciones pendientes.
migrate: hay migraciones pendientes y la base tiene datos. No se migra sin respaldo previo,
y la aplicación no arranca. Procedimiento:
  1. Detener app:   docker compose stop app
  2. Respaldar:     docker compose exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > backups/evaluon-AAAA-MM-DD.dump
  3. Aplicar:       docker compose run --rm --no-deps app python manage.py migrate
  4. Levantar todo: docker compose up -d
                                                                     código 1
```

**Resultado.** Cumple. El procedimiento que muestra difiere en dos detalles del texto del plan ("Migraciones y respaldo"), por motivos prácticos: el respaldo lleva `-T` y el usuario de la base (sin ellos `pg_dump` corre como `root` y la salida binaria pasa por una terminal), y el paso 3 lleva `--no-deps` (sin él, `docker compose run app` vuelve a correr `migrate`, que falla, y no llega a migrar). Se informa al Coordinador para el runbook.

### 5. Test de humo y suite

**Qué se probó.** `tests/test_skeleton.py`, con tres pruebas: el proyecto pasa `manage.py check` sin advertencias y la aplicación WSGI se carga; WhiteNoise sirve la hoja de estilos (`evaluon/static/css/evaluon.css`) reunida con `collectstatic`, con `DEBUG` apagado y el mismo contenido byte a byte; y la integración de `pgvector` para Django guarda un vector de tres dimensiones, lo lee igual y ordena por distancia `L2Distance`, con un modelo definido solo dentro de la prueba (`isolate_apps`). La extensión `vector` y la tabla de esa prueba se crean dentro de la transacción de la prueba, en la base que pytest-django crea y borra (`test_evaluon`). Antes de agregar la hoja de estilos y el middleware de WhiteNoise, las dos primeras pruebas fallaban (directorio de estáticos inexistente y respuesta 404); la de `pgvector` pasó desde la primera corrida.

**Comandos.**

```
docker compose run --rm app pytest tests/test_skeleton.py -v       (los seis servicios arriba)
docker compose run --rm app pytest                                 (los seis servicios arriba)
docker compose down
docker compose up -d db
docker compose run --rm --no-deps app pytest -v                    (solo db arriba)
```

**Salida.**

```
tests/test_skeleton.py::test_pgvector_stores_and_reads_vector PASSED     [ 33%]
tests/test_skeleton.py::test_project_starts PASSED                       [ 66%]
tests/test_skeleton.py::test_whitenoise_serves_static_file PASSED        [100%]
============================== 3 passed in 0.23s ===============================

tests/test_skeleton.py ...                                               [100%]
============================== 3 passed in 0.24s ===============================

db Up 7 seconds (healthy)
tests/test_skeleton.py::test_pgvector_stores_and_reads_vector PASSED     [ 33%]
tests/test_skeleton.py::test_project_starts PASSED                       [ 66%]
tests/test_skeleton.py::test_whitenoise_serves_static_file PASSED        [100%]
============================== 3 passed in 0.25s ===============================
```

**Resultado.** Cumple. WhiteNoise 6.12.0, pytest-django 4.14.0 y `pgvector` 0.5.0 funcionan con Django 6.1.1, aunque los dos primeros no declaran todavía la 6.1 (ADR-0005, "Sin verificar"). No hace falta el plan B. Queda abierto lo que el plan asigna a la etapa 1: parámetros de Argon2, vencimiento de la sesión y espera de Gunicorn con hilos ante una consulta larga.

### 6. Cierre

Al terminar se corrió `docker compose down`, sin `-v`: el volumen `evaluon_pgdata` se conserva, con la base `evaluon` vacía. La clave de la base y la de Django de estas pruebas están solo en el `.env` local, que no se sube. `postgres-dev` y el volumen `entorno-dev_pgdata` no se tocaron.

**Decisiones de esta tarea que el plan no fija:** Debian 13 en la imagen base, por la versión de Tesseract; `tesseract-ocr` fijado por versión de paquete; `spa.traineddata` de la etiqueta 4.1.0 de `tessdata_best`; `psycopg` en su variante binaria; PyYAML sí y biblioteca de cliente HTTP no; dependencias de prueba como opcionales `test`, instaladas en la imagen; solo `staticfiles` en `INSTALLED_APPS`; `DJANGO_SECRET_KEY` obligatoria; usuario sin privilegios en la imagen; código montado en solo lectura en `app` y `migrate`; red `web` para publicar el puerto; cuatro hilos de Gunicorn; chequeo de salud de `app`; definición de "base vacía"; `.gitattributes` y `.dockerignore`.

## Procedimiento de migraciones (T-006)

Fecha: 2026-10-02. Para el runbook.

**Por qué hace falta.** En `app` y `migrate` el código está montado en solo lectura (T-005, punto 3), así que `makemigrations` no puede escribir el archivo de migración dentro del contenedor. Para generarlas se usa un override local, fuera del repositorio, que monta solo `evaluon/` con escritura: `../evaluon-local/compose.migraciones.yml`. No forma parte de la configuración compartida: el montaje en solo lectura sigue siendo la regla para correr la aplicación y la suite.

**Generar una migración** (desde la raíz del repositorio, con `db` arriba):

```
docker compose -f docker-compose.yml -f ../evaluon-local/compose.migraciones.yml --project-directory . run --rm --no-deps app python manage.py makemigrations <aplicación>
docker compose run --rm --no-deps app python manage.py makemigrations --check --dry-run
```

La segunda orden, ya con el montaje normal, tiene que decir `No changes detected`.

**Aplicarla.** Al levantar, el servicio `migrate` corre `scripts/migrate_on_start.sh`: sobre una base vacía aplica todo; sobre una base con datos solo comprueba, y si hay migraciones pendientes se detiene y muestra el procedimiento de respaldo (T-005, punto 4).

**Primera migración del proyecto.** `accounts/0001_initial` crea `accounts_user`, el usuario propio (`AUTH_USER_MODEL = "accounts.User"`), antes que cualquier otra tabla que lo referencie. Se comprobó sobre la base `evaluon`, que no tenía ninguna tabla:

```
docker compose up -d db migrate
docker compose logs --no-log-prefix migrate
docker compose run --rm --no-deps migrate
```

```
migrate: la base está vacía; se aplican las migraciones.
Operations to perform:
  Apply all migrations: accounts, auth, contenttypes, sessions
Running migrations:
  Applying accounts.0001_initial... OK
  Applying contenttypes.0001_initial... OK
  ...
  Applying auth.0012_alter_user_first_name_max_length... OK
  Applying sessions.0001_initial... OK
migrate Exited (0)

migrate: la base tiene datos; solo se comprueba que no haya migraciones pendientes.
migrate: no hay migraciones pendientes.                              código 0
```

Tablas resultantes: `accounts_user`, `auth_group`, `auth_group_permissions`, `auth_permission`, `django_content_type`, `django_migrations`, `django_session`. Las de grupos y permisos las crea `django.contrib.auth`, que se instala por el ingreso y por `changepassword`; no se usan (ADR-0005).

**Consecuencia.** Desde ahora la base `evaluon` del volumen `evaluon_pgdata` tiene tablas y cuenta como "con datos". La próxima tarea que agregue una migración no la verá aplicada sola al levantar: `migrate` se detiene y hay que seguir el procedimiento (respaldar y aplicar a mano), o bien, mientras la base no tenga datos que conservar, vaciarla a propósito.
