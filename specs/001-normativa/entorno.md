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

## Migración de `audit` (T-007)

Fecha: 2026-10-02. `audit/0001_initial` crea `audit_event` (plan 001, "Modelo de datos"), con restricciones para los valores de `event_type`, `outcome` y `channel`, y la clave hacia `accounts_user` con `PROTECT`. Se generó con el override local, como indica la sección anterior, y `makemigrations --check --dry-run` con el montaje normal dijo `No changes detected`.

**Base `evaluon`, ya con el esquema de T-006 y sin datos que conservar.** El servicio `migrate` se detuvo, como corresponde, y mostró el procedimiento. Como no había nada que respaldar, se aplicó directamente el paso 3; después `migrate` ya no encuentra nada pendiente. También se probó la reversa sobre esa base (`migrate audit zero` y otra vez `migrate`), sin error. El volumen no se vació.

```
docker compose run --rm --no-deps migrate                                     (se detiene: hay migraciones pendientes)
docker compose run --rm --no-deps app python manage.py migrate                Applying audit.0001_initial... OK
docker compose run --rm --no-deps migrate                                     migrate: no hay migraciones pendientes.
```

**Base vacía.** Se comprobó en una base aparte (`t007_prueba`), creada y borrada para la prueba, igual que en T-005: `migrate_on_start.sh` aplicó todo (`accounts.0001_initial`, `audit.0001_initial`, `contenttypes`, `auth`, `sessions`) y en la segunda corrida informó que no hay migraciones pendientes. Tablas resultantes: las siete de T-006 más `audit_event`.

```
docker exec -i evaluon-db-1 sh -c 'psql -U "$POSTGRES_USER" -d evaluon -c "CREATE DATABASE t007_prueba;"'
docker compose run --rm --no-deps -e POSTGRES_DB=t007_prueba migrate          (dos veces)
docker exec -i evaluon-db-1 sh -c 'psql -U "$POSTGRES_USER" -d evaluon -c "DROP DATABASE t007_prueba;"'
```

**Solo inserciones, por trigger (`audit/0002_append_only`).** El registro de auditoría solo admite inserciones: el trigger `audit_event_append_only` (`BEFORE UPDATE OR DELETE ... FOR EACH ROW`, función `audit_event_reject_change`) rechaza cualquier modificación o borrado, venga de Django o de SQL directo. Para limpiar datos de prueba hay que recrear la base (`docker compose down -v`, o borrar y crear la base); los tests no se ven afectados porque cada uno deshace su transacción. Borrar un usuario con hechos registrados tampoco llega a `audit_event`: Django lo impide (`PROTECT`) y la clave foránea no tiene borrado en cascada. Se aplicó con `docker compose run --rm --no-deps app python manage.py migrate`; la reversa (`migrate audit 0001`, que quita trigger y función, y otra vez `migrate`) corrió sin error.

## Migraciones de `norms` (T-008)

Fecha: 2026-10-02. `norms/0001_extensions` crea con SQL propio las extensiones `vector` y `unaccent` (`CREATE EXTENSION IF NOT EXISTS`; reversa `DROP EXTENSION IF EXISTS`). `norms/0002_tables` crea las nueve tablas de "Modelo de datos" con sus restricciones, sin la columna `tsv` ni las funciones SQL (T-009). La segunda se generó con el override local (`makemigrations norms --name tables`); la primera se escribió a mano. Con el montaje normal, `makemigrations --check --dry-run` dijo `No changes detected`.

**Base `evaluon`, sin datos que conservar.** `migrate` se detuvo y mostró el procedimiento, como corresponde; se aplicó el paso 3 y después `migrate` no encontró nada pendiente. Reversa: `migrate norms zero` dejó la base sin tablas `norms_*` y solo con `plpgsql`; otra vez `migrate` las recreó, con `unaccent` 1.1 y `vector` 0.8.7.

```
docker compose run --rm --no-deps app python manage.py migrate              Applying norms.0001_extensions... OK / norms.0002_tables... OK
docker compose run --rm --no-deps app python manage.py migrate norms zero   Unapplying norms.0002_tables... OK / norms.0001_extensions... OK
docker compose run --rm --no-deps app python manage.py migrate              Applying norms.0001_extensions... OK / norms.0002_tables... OK
```

**Base vacía.** En una base aparte (`t008_prueba`), creada y borrada para la prueba como en T-005 y T-007, `migrate_on_start.sh` aplicó todo (`accounts`, `audit` 0001 y 0002, `contenttypes`, `auth`, `norms` 0001 y 0002, `sessions`) y en la segunda corrida informó que no hay migraciones pendientes.

**Versión de la normativa frente al trigger de solo inserción.** `audit_event` no admite UPDATE (T-007), así que un hecho no puede recibir su número de versión después de insertado. `evaluon.audit.services.record(..., creates_corpus_version=True)`, dentro de la transacción de quien hace el cambio: (1) bloquea `norms_corpus_version` en modo `SHARE ROW EXCLUSIVE`, que serializa la creación de versiones sin impedir leerla; (2) reserva el número con `nextval(pg_get_serial_sequence('norms_corpus_version', 'id'))`; (3) inserta el hecho con ese número en `corpus_version` y en `detail.new_corpus_version`; (4) inserta la versión con ese `id`, apuntando al hecho. Solo se admite con resultado `ok`. Los demás hechos llevan la versión vigente, `max(id)` de `norms_corpus_version`, o vacío si no hay ninguna (`current_corpus_version()`). El bloqueo hace que los números se confirmen en el orden en que se reservan: nadie registra como vigente una versión cuyo cambio todavía no se confirmó. Una transacción deshecha deja un hueco en la numeración, que sigue creciente.

## Migraciones de `norms` (T-009)

Fecha: 2026-10-02. Tres migraciones con su reversa:

- `norms/0003_search_functions` (SQL propio): `search_normalize`, `search_document` y `search_query` (ADR-0007), inmutables. Llaman a `public.unaccent('public.unaccent'::regdictionary, ...)` y nombran todo con su esquema. No se crea `spanish_unaccent`.
- `norms/0004_passage_tsv`: columna `tsv` de `norms_passage`, `GENERATED ALWAYS AS (search_document(text)) STORED`, generada con el override local (`makemigrations norms --name passage_tsv`), más el índice GIN `norms_passage_tsv_gin` con SQL propio (`GinIndex` exige `django.contrib.postgres`, que no está instalada). El campo del modelo usa un tipo `tsvector` propio por el mismo motivo.
- `norms/0005_date_functions` (SQL propio): `consultable_units`, `unit_changes` y `applicable_regimes`, estables.

Con el montaje normal, `makemigrations --check --dry-run` dijo `No changes detected`.

**Lexemas en el Postgres fijado (17.11).** Coinciden todos con la tabla "Resultado esperado" del ADR-0007:

```
licitación, licitaciones, licitacion, LICITACIÓN -> 'licit'   (LICITACIÓN se normaliza como LICITAción)
adjudicación, adjudicaciones -> 'adjud'      contratación, contrataciones -> 'contrat'
artículo, artículos, articulo -> 'articul'   garantía, garantías, garantia -> 'garanti'
297/03 -> '297/03'                           247/2022 -> '247/2022'
```

**Base `evaluon`, sin datos que conservar.** Se aplicó con `docker compose run --rm --no-deps app python manage.py migrate` (0003, 0004 y 0005 OK). Reversa: `migrate norms 0002` quitó 0005, 0004 y 0003; quedaron 0 funciones, sin columna `tsv` y sin índice; otra vez `migrate` las aplicó sin error.

**Base vacía.** En una base aparte (`t009_prueba`), creada y borrada, `migrate_on_start.sh` aplicó todo (`norms` 0001 a 0005 incluidas) y en la segunda corrida informó que no hay migraciones pendientes.

**Respaldo y restauración.** En dos bases aparte (`t009_a` y `t009_b`), creadas y borradas: con un pasaje cargado, `pg_dump -Fc` y `pg_restore` sobre una base vacía terminaron sin error, la columna `tsv` restaurada quedó igual (`'licit':2 'public':3`) y `consultable_units` respondió. `pg_restore` corre con `search_path` vacío y recalcula `tsv` al insertar; por eso las funciones nombran todo con su esquema.

**Al actualizar Postgres o la imagen fijada.** Las funciones de búsqueda se declaran inmutables aunque `unaccent` no lo es: la promesa se cumple mientras no cambien las reglas de `unaccent` ni el lematizador de español. Después de una actualización de versión mayor (o de la imagen) hay que recalcular `tsv` de todos los pasajes (por ejemplo `UPDATE norms_passage SET text = text;`, que vuelve a calcular la columna, como se comprobó en una base aparte `t009_c`, creada y borrada, y `REINDEX INDEX norms_passage_tsv_gin;`) y repetir `pytest tests/norms/test_text_search_config.py`. `pg_upgrade` copia los datos sin recalcular.

## Migraciones de `queries` (T-010)

Fecha: 2026-10-02. Dos migraciones:

- `queries/0001_initial`: `queries_query` como en "Modelo de datos", generada con el override local (`makemigrations queries`). Restricciones: `status` en `grounded`, `undetermined` o `error`; `reason` vacío con `grounded`, uno de los cuatro motivos de "no determinado" con `undetermined` y uno de los cuatro de falla técnica con `error`; `max_score` vacío o entre 0 y 1; `event` único (una consulta por hecho), y claves hacia `audit_event` y `accounts_user` con `PROTECT`.
- `queries/0002_insert_only` (SQL propio): trigger `queries_query_insert_only` (función `queries_query_reject_change`) que rechaza todo UPDATE y DELETE, como en `audit_event`.

Con el montaje normal, `makemigrations --check --dry-run` dijo `No changes detected`.

**Base `evaluon`, sin datos que conservar.** Se aplicó con `docker compose run --rm --no-deps app python manage.py migrate` (0001 y 0002 OK). Reversa: `migrate queries zero` quitó 0002 y 0001 (sin tabla `queries_query` ni función del trigger); otra vez `migrate` las aplicó sin error y el trigger quedó en la tabla.

**Base vacía.** En una base aparte (`t010_prueba`), creada y borrada, `migrate_on_start.sh` aplicó todo (`queries` 0001 y 0002 incluidas) y en la segunda corrida informó que no hay migraciones pendientes.

## La eñe en la búsqueda por palabras (T-053)

Fecha: 2026-10-02. `norms/0006_search_normalize_enye` (SQL propio, con reversa) reemplaza `search_normalize` (ADR-0007, adenda "La eñe"): cambia por espacios los `\x01` y `\x02` que traiga el texto, cambia "ñ" y "Ñ" por `\x01` y `\x02`, quita los acentos con `unaccent`, repone "ñ" y "Ñ" y después repone la tilde de "-acion" y "-ucion" con la misma expresión de 0003. La regla de la tilde corre sobre el texto ya repuesto, así no ve los caracteres de control. `search_document` y `search_query` no cambian. La migración y su reversa recalculan `tsv` (`UPDATE public.norms_passage SET text = text;`) y reconstruyen el índice (`REINDEX INDEX public.norms_passage_tsv_gin;`). Con el montaje normal, `makemigrations --check --dry-run` dijo `No changes detected`.

**Lexemas en el Postgres fijado (17.11), antes y después.**

```
palabra       antes (0005)   después (0006)
año           'ano'          'año'
ano           'ano'          'ano'
años          'anos'         'años'
AÑO           'ano'          'año'
señal         'senal'        'señal'
señales       'senal'        'señal'
compañía      'compani'      'compañi'
compañías     'compani'      'compañi'
compania      'compani'      'compani'
Ñandú         'nandu'        'ñandu'
pingüino      'pinguin'      'pinguin'
licitacion    'licit'        'licit'
licitaciones  'licit'        'licit'
297/03        '297/03'       '297/03'
```

Los demás lexemas de la tabla del ADR-0007 no cambian (`tests/norms/test_text_search_config.py`).

**Recálculo con datos, en la base del proyecto `evaluon-t053`.** Con las migraciones aplicadas hasta `norms/0005`, se cargaron por `manage.py shell` dos pasajes sintéticos: "El plazo es de un año calendario." (1) y "La señal de la compañía AÑO Ñandú." (2). Después se aplicó 0006, se revirtió (`migrate norms 0005`) y se volvió a aplicar, sin tocar los pasajes:

```
                       tsv del pasaje 2                            "ano"   "año"   "compania"
0005 (carga)           'ano':6 'compani':5 'nandu':7 'senal':2     {1,2}   {1,2}   {2}
0006                   'año':6 'compañi':5 'señal':2 'ñandu':7     -       {1,2}   -
reversa a 0005         'ano':6 'compani':5 'nandu':7 'senal':2     {1,2}   {1,2}   {2}
0006 otra vez          'año':6 'compañi':5 'señal':2 'ñandu':7     -       {1,2}   -
```

Con `enable_seqscan` apagado, la búsqueda de "año" usa `norms_passage_tsv_gin` y encuentra los dos pasajes. La misma prueba corre en la suite (`test_enye_migration_recalculates_tsv_of_existing_passages`) con el SQL de la migración dentro de la transacción de la prueba.

**Respaldo y restauración.** `pg_dump -Fc` de esa base y `pg_restore` en una base aparte (`t053_b`, creada y borrada) terminaron sin error, con `tsv` igual al de la base de origen.

**Qué se pierde.** Quien escribe sin eñe no encuentra la palabra con eñe ("compania" no encuentra "compañía"), y "año" y "años" no comparten lexema (ADR-0007, adenda).

**Caracteres de control y esquema explícito.** Los `\x01` y `\x02` que traiga el texto se cambian por espacios antes de proteger la eñe. Como el analizador ya los trataba como separadores, el lexema queda igual que antes de T-053: `E'plazo\x01de'` da `'plaz':1`, no `'plazoñd'` (`test_control_characters_used_to_protect_the_enye_are_separators`). Con `SET LOCAL search_path = ''`, `public.search_normalize`, `public.search_document` y `public.search_query` dan los lexemas esperados para "año" y "licitacion" (`test_search_functions_work_with_an_empty_search_path`). Si en la 0006 se llama a `unaccent(...)` sin esquema ni diccionario, ese test falla con `function unaccent(text) does not exist`. Con datos, en la base de `evaluon-t053`, se aplicó la 0006, se revirtió a 0005 y se volvió a aplicar: dio los mismos `tsv` y las mismas coincidencias de la tabla anterior, y `E'plazo\x01de'` dio `'plaz':1` en las tres definiciones.

## T-011 · Clientes de IA contra los servicios reales

Fecha: 2026-10-02. Requisitos: REQ-008 y REQ-009. Además de la suite (que usa un servidor HTTP falso y los dobles), se llamó una vez a cada operación de los clientes de `evaluon/ai/` contra los servicios reales, desde el contenedor `app` y con los valores por defecto de `settings.py` (`http://generation:8080`, `http://embeddings:8080`, `http://reranker:8080`). Los textos son sintéticos o los de las fichas públicas de los modelos; el script quedó fuera del repositorio.

**Comandos.**

```
docker compose up -d generation embeddings reranker
docker compose run --rm --no-deps -T -e DJANGO_SETTINGS_MODULE=evaluon.settings app python - < <script>
docker compose stop reranker      # para la prueba de servicio caído
docker compose stop generation embeddings && docker compose rm -f generation embeddings reranker
```

**Salida.**

```
rerank [0.00028, 0.99493] logit [-8.1805, 5.2794] 0.21s
embed dims [1024, 1024, 1024, 1024] sims [0.6257, 0.3471, 0.3489, 0.6785]
count_tokens embeddings 38 /tokenize 38
count_tokens generation 38 /tokenize 38
count_tokens embeddings 26 /tokenize 26
count_tokens generation 31 /tokenize 31
generate stop 130 81 1.45s
content {"status": "grounded", "statements": [{"text": "El oferente deberá integrar la garantía de mantenimiento de oferta por el cinco por ciento (5 %) del monto total de la oferta.", "citations": ["U1"]}]}
reasoning_content en la respuesta: False
generation InputTooLongError input_too_long 400 ... request (30014 tokens) exceeds the available context size (16384 tokens) ...
embeddings InputTooLongError input_too_long 500 ... input (21002 tokens) is too large to process ...
reranker InputTooLongError input_too_long 500 ... input (21005 tokens) is too large to process ...
reranker detenido: ServiceUnavailableError service_unavailable reranker: no responde (http://reranker:8080/v1/rerank: [Errno -3] Temporary failure in name resolution)
```

**Resultado.** Cumple:

- Las cuatro operaciones responden: `generate` (salida con esquema, `finish_reason` `stop`, sin `reasoning_content`), `embed` (cuatro vectores de 1024, similitudes de la ficha de `bge-m3` iguales a las de T-003), `rerank` y `count_tokens` en los dos clientes.
- Pares de la ficha del reranker, ya con sigmoide: 0,99493 y 0,00028 (valor sin escala 5,2794 y −8,1805, los mismos de T-003).
- `count_tokens` coincide con el largo de la lista de `/tokenize` de cada servidor. Con un segundo texto las cuentas de los dos modelos difieren (26 en `bge-m3`, 31 en Gemma 4): cada cliente cuenta con su propio servidor.
- Una entrada demasiado larga da `InputTooLongError` (motivo `input_too_long`) en los tres servicios, aunque `generation` responde HTTP 400 y `embeddings` y `reranker` HTTP 500.
- Con el servicio detenido, el cliente da `ServiceUnavailableError` (motivo `service_unavailable`).

**Pensamiento apagado por pedido.** Cada pedido de generación lleva `chat_template_kwargs: {"enable_thinking": false}` además del `--reasoning off` del servidor. Se comprobó con `POST /apply-template` que esa es la variable que lee la plantilla de Gemma 4: sin ella y con `false`, la plantilla termina en `<|turn>model\n<|channel>thought\n<channel|>` (canal de pensamiento vacío, como en T-002, sección 5); con `true` agrega `<|think|>` en un turno de sistema y no cierra el canal. Así el pedido registrado dice por sí mismo que el pensamiento estaba apagado.

## T-054 · Variables de los servicios de IA en la aplicación

Fecha: 2026-10-03. Requisitos: REQ-008 y REQ-012. Al verificar T-011 se vio que `x-app` en `docker-compose.yml` solo pasaba a `app` y `migrate` las variables `DJANGO_*` y `POSTGRES_*`: si `.env` cambiaba el modelo, el servidor arrancaba con el valor nuevo y la aplicación seguía con el valor por omisión de `settings.py`, y el registro de una consulta nombraría otro modelo que el que respondió (P6).

**Cambio.**

- `x-app` pasa a `app` y `migrate` `GENERATION_URL`, `EMBEDDINGS_URL`, `RERANKER_URL`, `GENERATION_MODEL_ALIAS`, `GENERATION_MODEL_FILE`, `GENERATION_MODEL_SHA256`, `GENERATION_CTX_SIZE`, `EMBEDDINGS_MODEL_ALIAS`, `EMBEDDINGS_MODEL_FILE`, `EMBEDDINGS_MODEL_SHA256`, `RERANKER_MODEL_ALIAS`, `RERANKER_MODEL_FILE` y `RERANKER_MODEL_SHA256`. Las de modelo se escriben igual que en el `command` de cada servicio (`${NOMBRE:-valor}`), con el mismo valor por omisión: servidor y aplicación leen `.env` y, si falta la variable, caen en el mismo valor. Los servicios de IA y `db` no cambiaron.
- `docker-compose.yml` se monta en solo lectura en `/app/docker-compose.yml` para que la suite lo lea.
- `tests/test_compose_env.py` comprueba, leyendo el compose: que `app` y `migrate` reciben cada variable de modelo con el mismo valor por omisión que el servicio; que, con el entorno que recibió la aplicación, el alias, el archivo y el contexto de `settings.py` son los que resuelve el `command` de cada servicio; que los valores por omisión de `settings.py` son los del compose; y que `GENERATION_ENGINE_BUILD` es la compilación de la etiqueta de la imagen de los tres servicios (`server-cuda-b11347`).
- La dimensión del vector se define una sola vez, en `settings.EMBEDDINGS_DIMENSIONS`; `norms.models.EMBEDDING_DIMENSIONS` y la constante de `tests/conftest.py` la toman de ahí. El esquema no cambia: `makemigrations --check` da `No changes detected`.
- `tests/queries/test_ai_clients.py` suma la espera agotada al conectar, que T-011 no cubría (solo la espera agotada con la conexión ya abierta): `socket.create_connection` lanza `TimeoutError: timed out` y los cuatro pedidos dan `ServiceTimeoutError` (`timeout`), no `ServiceUnavailableError`, con la espera de `AI_TIMEOUT_SECONDS`.

**Prueba con otro alias en `.env`.** Copia temporal de `.env` con `GENERATION_MODEL_ALIAS=gemma-prueba-t054` (el `.env` del equipo no se tocó), servicios reales levantados con ella y el script de comprobación fuera del repositorio:

```
docker compose --env-file <copia> up -d --wait generation embeddings reranker
docker compose --env-file <copia> run --rm --no-deps -T -e DJANGO_SETTINGS_MODULE=evaluon.settings app python -c "..." < <script>
```

```
settings.GENERATION_MODEL: gemma-prueba-t054
generation /v1/models id: ['gemma-prueba-t054'] | build: b11347-5fc4f3c8c | n_ctx: 16384 | model_path: /models/gemma-4-12b-it-qat-q4_0.gguf
embeddings /v1/models id: ['bge-m3'] | build: b11347-5fc4f3c8c | n_ctx: 8192 | model_path: /models/bge-m3-FP16.gguf
reranker /v1/models id: ['bge-reranker-v2-m3'] | build: b11347-5fc4f3c8c | n_ctx: 8192 | model_path: /models/bge-reranker-v2-m3-FP16.gguf
settings: bge-m3 bge-reranker-v2-m3 gemma-4-12b-it-qat-q4_0.gguf bge-m3-FP16.gguf bge-reranker-v2-m3-FP16.gguf 16384 b11347
pedido model: gemma-prueba-t054 | respuesta model: gemma-prueba-t054 | stop
```

Con la misma copia y el `docker-compose.yml` anterior (el de `main` antes de T-054), `docker compose config` da `--alias gemma-prueba-t054` en `generation` y `app` sin `GENERATION_MODEL_ALIAS`: es el desfase que corrige la tarea. Con el `.env` del equipo, `settings.GENERATION_MODEL` y `/v1/models` de `generation` dan los dos `gemma-4-12b-it-qat-q4_0`.

**Suite.** `docker compose run --rm app pytest`, con los seis servicios arriba: 232 pasan, con el `.env` del equipo y con la copia de otro alias. `docker compose run --rm --no-deps app pytest` solo con `db`: 232 pasan.

## T-020 · Hilo mínimo con los servicios reales

Fecha: 2026-10-03. Requisitos: REQ-008, REQ-012, REQ-013 y REQ-020. Cierra la etapa 2 del plan: el anexo de la Disposición 247/2022 cargado y validado, y una pregunta real respondida en la pantalla con los servicios de IA reales.

**Entorno de la prueba.** Una copia de trabajo aislada, con `models/` como enlace a la carpeta de modelos de la copia principal (borrado al terminar). Todo `docker compose` corrió como proyecto propio, `-p evaluon-t020`: su volumen `evaluon-t020_pgdata` es la base aparte de esta prueba, y la base `evaluon` (volumen `evaluon_pgdata`) no se tocó. La imagen se reconstruyó antes de probar la pantalla (`docker compose -p evaluon-t020 build app`), por los estáticos de T-016. GPU en 0 MiB antes de levantar los servicios.

```
docker compose -p evaluon-t020 up -d --wait          # 51 s; migrate aplicó el esquema a la base vacía
```

Con los tres modelos cargados, `nvidia-smi` da 10.172 MiB; después de las consultas, 10.320 MiB.

**Modelo de la aplicación y del servidor (aviso de T-054).** Dentro de `app`, cada valor de `settings.py` contra `GET /v1/models` de su servicio:

```
generation settings: gemma-4-12b-it-qat-q4_0 | /v1/models: ['gemma-4-12b-it-qat-q4_0'] | igual: True
embeddings settings: bge-m3 | /v1/models: ['bge-m3'] | igual: True
reranker settings: bge-reranker-v2-m3 | /v1/models: ['bge-reranker-v2-m3'] | igual: True
```

**Usuarios de prueba.** `crear_usuario prueba-carga --rol lectura-escritura` y `crear_usuario prueba-consulta --rol lectura`, con claves al azar que no se guardaron en el repositorio. Los dos quedaron registrados como hechos `user_created`.

**Carga.** Con los datos del aviso de T-014 (fecha de publicación del Boletín Oficial; vigencia informada por el responsable, ADR-0006):

```
docker compose -p evaluon-t020 exec -T app python manage.py cargar_norma corpus/normativa/disp-afip-247-2022-anexo.pdf \
  --tipo Disposición --numero 247 --anio 2022 --organismo AFIP --nombre "Disposición AFIP 247/2022" \
  --titulo "Régimen General para Contrataciones de Bienes, Servicios y Obras Públicas" \
  --categoria regimen_especifico --parte anexo --regimen-general --fecha-publicacion 2022-11-30 \
  --fecha-vigencia 2023-01-01 --fuente https://servicios.infoleg.gob.ar/infolegInternet/anexos/375000-379999/375829/disp247.pdf \
  --usuario prueba-carga
```

```
Se cargó el documento 1: parte anexo de la Disposición AFIP 247/2022 (norma nueva).
Lectura 1, pendiente de validación: 100 unidades, 45 páginas, páginas no leídas: 45, 16 tramos no ubicados.
```

Tiempo: 3,5 s, medido desde fuera del contenedor (incluye el arranque del comando).

**Informe** (`ver_informe 1 --usuario prueba-carga`), resumido:

```
Páginas: 45. Páginas no leídas: 45.
Unidades reconocidas: 100 (1 anexo, 99 artículos).
  Anexo: 99 artículos, del 1 al 99.
No ubicado: 16 tramos.
  - Página 5: TÍTULO I - DISPOSICIONES GENERALES
  ... (títulos y capítulos de las páginas 12 a 44)
  - Página 44: TÍTULO VII - MÓDULO
  - Página 44: CLÁUSULA TRANSITORIA REGISTRO DE PROVEEDORES Las unidades con
Descartado: 1 tramo.
  - Índice, páginas 1 a 5: ÍNDICE: TÍTULO I - DISPOSICIONES GENERALES ARTÍCULO 1º.-
Uniones de palabras cortadas: 0.
Cobertura: 140925 caracteres: 134730 en unidades, 4801 descartados, 1278 no ubicados y 116 saltos de línea entre tramos; la suma coincide con el total.
```

Es lo esperado para la partición de esta etapa, que reconoce solo artículos: los 99 artículos del índice, de `anexo/art-1` a `anexo/art-99`, en orden. Quedan sin ubicar los títulos y capítulos (que con las reglas de T-023 pasan a la ruta) y la cláusula transitoria (que con T-023 pasa a ser la unidad `anexo/clausula-transitoria`). La página 45, que solo trae la firma digital, figura como no leída. Los incisos no aparecen como no ubicados: quedan dentro del texto de su artículo.

**Validación con el tiempo del pedido de vectores (aviso de T-015).** `validar_informe 1 --usuario prueba-carga`, con un script fuera del repositorio que mide la llamada a `embeddings.embed`:

```
[medida] embeddings.embed: 100 textos en un pedido, 5.43 s; caracteres max 10807, total 139308
[medida] tokens del texto mas largo (bge-m3 /tokenize): 2299; empieza: 'Disposición AFIP 247/2022, Anexo, Artículo 24\nARTÍCULO 24.- MODALIDADES. Los pro'
Se validó la lectura 1, con 100 pasajes. Quedó en uso como versión 1 de su parte. Se creó la versión 1 de la normativa.
[medida] validar_informe total: 5.65 s
```

Un solo pedido a `embeddings` con los 100 pasajes del anexo completo: 5,43 s. El pasaje más largo es el del artículo 24, con 2.299 tokens de `bge-m3` contando el encabezado, debajo del límite de 8.192 por texto (el aviso estimaba unos 3.000).

**Pregunta real en la pantalla.** Sin navegador en esta sesión, la pregunta se envió por HTTP a Gunicorn en `127.0.0.1:8000`, como lo hace el formulario: ingreso con `prueba-consulta` en `/ingresar/`, envío de la pregunta a `/` con su token CSRF y la redirección a la consulta guardada. El script quedó fuera del repositorio. Pregunta: "¿Por cuántos días deben los oferentes mantener sus ofertas?", con el campo de fecha vacío (la fecha del día).

```
URL final: http://127.0.0.1:8000/consultas/1/ | HTTP 200 | 7.00 s
✓ Respuesta con fundamento en la normativa
Pregunta: ¿Por cuántos días deben los oferentes mantener sus ofertas?
Procedimiento autorizado el 03/10/2026 · Régimen aplicado: Disposición AFIP 247/2022
Los oferentes deben mantener sus ofertas por un plazo de sesenta días corridos a partir de la fecha del acto de apertura.
Disposición AFIP 247/2022 · Anexo › Artículo 43
ARTÍCULO 43.- PLAZO DE MANTENIMIENTO DE LA OFERTA. Los oferentes deberán mantener las ofertas por un plazo de SESENTA (60) días corridos, ...
```

La respuesta trae cinco afirmaciones, todas con la cita del artículo 43 (plazo; plazo distinto si lo fija el pliego; el día de apertura no se computa; prórroga automática; aviso de no renovación con cinco días hábiles). El texto citado es igual a `canonical_text[char_start:char_end]` de su lectura (comprobado en la base: `literal igual: True`).

**Registro de la consulta** (`queries_query` 1, hecho `query` 5 en `audit_event`): usuario `prueba-consulta`; pregunta; `reference_date` 2026-10-03; régimen `[{"name": "Disposición AFIP 247/2022", "norm": 1}]`; versión de la normativa 1; estado `grounded`; 30 candidatos con camino, pasaje, distancia y puntaje; 3 unidades seleccionadas (artículo 43 con 0,9995, y otras dos con 0,549 y 0,514); puntaje más alto 0,9995; instrucciones `consulta-v1`; pedido con `model` `gemma-4-12b-it-qat-q4_0`; salida sin tocar (939 caracteres); parámetros con modelo, archivo, huella, compilación `b11347`, temperatura 0, semilla 42 y pensamiento apagado; sin anomalías.

**Tiempos de la consulta** (columna `timings`, en segundos):

| Consulta | Fecha | Resultado | Régimen | Recuperación | Generación | Total |
|---|---|---|---|---|---|---|
| Plazo de mantenimiento (primera después de levantar) | vacía (2026-10-03) | con fundamento, art. 43 | 0,002 | 2,417 | 4,490 | 6,91 |
| La misma | 2023-01-01 | con fundamento, art. 43 | 0,001 | 0,679 | 3,796 | 4,48 |
| La misma | 2021-06-15 | no determinado, `no_regime_at_date` | 0,004 | — | — | 0,004 |
| La misma | 2022-12-31 | no determinado, `no_regime_at_date` | 0,001 | — | — | 0,002 |
| "¿Qué modalidades pueden tener los procedimientos de selección?" | vacía | con fundamento, art. 24 | 0,002 | 0,711 | 7,091 | 7,80 |
| "¿Qué porcentaje es la garantía de cumplimiento del contrato?" | vacía | con fundamento, art. 64 | 0,002 | 0,491 | 2,907 | 3,40 |
| "¿Cuál es la alícuota general del impuesto al valor agregado?" | vacía | no determinado, `below_threshold` (0,019) | 0,001 | 1,511 | — | 1,51 |

Todas debajo de los 30 segundos. Con la fecha de 2021 la página muestra "No determinado" con la línea "Para esa fecha no hay un régimen específico cargado en el sistema", sin buscar ni llamar al modelo; el 2022-12-31 da lo mismo y el 2023-01-01 ya aplica la 247/2022. Una fecha futura vuelve al formulario con "La fecha de autorización no puede ser posterior a hoy" y una inexistente (2021-02-30) con "Escriba una fecha válida, con día, mes y año", sin crear consulta. `GET /static/css/evaluon.css` y `/static/js/consulta.js` dan 200, y las páginas llevan `Content-Security-Policy: default-src 'self'`.

**Diferencias entre los dobles y los servicios reales.** Ninguna que pida corregir `evaluon/ai/`. Se compararon las respuestas reales de `/v1/embeddings` (`data` con `index`, `object` y `embedding` de 1024; `usage`), `/v1/rerank` (`results` ordenados por puntaje, no por índice, con `index` y `relevance_score` sin escala; `usage`) y `/tokenize` (`tokens`) con las del servidor falso de `tests/queries/test_ai_clients.py`, y tienen los mismos campos; la generación respondió con la forma esperada en las cinco consultas que llegaron al modelo. Ninguna consulta dejó anomalías.

**Prueba de espera con Gunicorn** (`tests/queries/test_wait.py`, plan 001, "Sin verificar": "Tiempo de espera de Gunicorn con hilos"). Levanta Gunicorn con el mismo `command` del servicio `app` de `docker-compose.yml` (solo cambia la dirección, a un puerto libre de 127.0.0.1), sobre la base de pruebas, con servidores HTTP falsos de los tres servicios de IA; el del motor tarda 35 s de verdad (el doble `fake_generation` lanza la espera agotada sin esperar y no llega a otro proceso). Ingresa y envía una pregunta como el navegador: la respuesta llega a los 35 s y algo más, redirige a la consulta guardada, y la consulta queda con fundamento, con su régimen y con `timings.generation` de 35 s o más. Otra prueba comprueba que la espera de `app` (120 s) supera los 30 s de una consulta y los 60 s de `AI_TIMEOUT_SECONDS`, con más de un hilo. Para ver que la prueba distingue, se corrió una copia fuera del repositorio con `--threads 1 --timeout 30`: Gunicorn cortó el pedido a los 30 s (`assert 500 == 302`).

**Suite.** `docker compose -p evaluon-t020 run --rm app pytest`, con los seis servicios arriba: 459 pasan. `docker compose -p evaluon-t020 run --rm --no-deps app pytest` solo con `db`: 459 pasan.

**Falta probar en un navegador real** (esta sesión no tuvo navegador): el control de fecha, el script de espera (también al volver con "Atrás"), que la política de contenido no bloquee nada en la consola, el formulario sin JavaScript y que los tres bloques se distingan a simple vista.

**Cierre.** `docker compose -p evaluon-t020 down`, sin `-v`: la base de esta prueba queda cargada en `evaluon-t020_pgdata` para repetir la pregunta. GPU en 0 MiB.

### Cierre de T-020 (Coordinador, 2026-10-03)

- **Qué evita el corte de una consulta larga.** Con `--threads 4`, Gunicorn usa hilos (gthread), y en ese modo `--timeout` no limita cuánto dura un pedido. Lo que impide que una consulta de más de 30 s se corte es que el proceso tenga hilos. La espera de 120 s no es la protección. Lo comprobó la verificación: con `--timeout 30` y 4 hilos, una consulta de 35 s no se corta. Con `--threads 1` sí se corta. `tests/queries/test_wait.py` controla las dos cosas: que haya más de un hilo y que la espera supere 30 s.
- **Navegador real.** El Coordinador probó la pantalla en el navegador integrado de la aplicación de escritorio, sobre esta misma base y con los servicios reales. Ingresó con `prueba-consulta` y preguntó "¿Qué porcentaje de garantía de mantenimiento de oferta se exige?" con la fecha del día. Resultado:
  - La respuesta vino con fundamento y citas del art. 64 de la Disposición AFIP 247/2022: "cinco por ciento (5%)".
  - Cada cita despliega el texto literal.
  - La consola no muestra violaciones de la política de contenido.
  - El control de fecha muestra día/mes/año y rechaza una fecha futura. El script de espera desactiva el botón y muestra el aviso. Esto ya estaba probado en T-016.
  - Queda sin probar que el botón vuelva a habilitarse al volver con "Atrás": se anotó en T-037.

## T-043 · Carga del corpus real (parte del desarrollador)

Fecha: 2026-10-03. Requisitos: REQ-003, REQ-004, REQ-005, REQ-015 y REQ-020. Primera carga en la base real `evaluon` (volumen `evaluon_pgdata`). El desarrollador cargó, revisó los informes, ajustó las reglas y releyó; **no validó ninguna lectura**: la validación la hace el responsable de normativa con su usuario, con los pasos de más abajo.

**Entorno.** Proyecto `evaluon` levantado desde la copia de trabajo de T-043, con los modelos de la copia principal montados por un archivo de sobreescritura fuera del repositorio. GPU en 0 MiB antes de levantar; 10.172 MiB con los tres modelos cargados.

```
docker compose -p evaluon --env-file <.env de la copia principal> -f docker-compose.yml -f <sobreescritura de models> up -d --wait
```

- Antes de escribir se comprobó que la base estaba vacía: 0 normas, 0 documentos, 0 lecturas, 0 unidades, 0 hechos y 0 usuarios.
- `migrate` no arrancó porque la base tenía el esquema creado pero le faltaba `norms.0007_norm_citation` (T-055). Se siguió el procedimiento de `scripts/migrate_on_start.sh`: `stop app`, respaldo con `pg_dump` (guardado fuera del repositorio) y `run --rm --no-deps app python manage.py migrate`, que aplicó solo esa migración. No se escribió ninguna migración nueva.
- Usuario de carga: `crear_usuario desarrollo --rol lectura-escritura`, con una clave al azar que no está en el repositorio. El usuario del responsable no se creó: lo crea él.

**Carga.** Con los datos del manifiesto, el nombre de cita de cada norma, la fecha de publicación del Boletín Oficial (la de la 297/03, de su ficha de Infoleg en `corpus/normativa/referencias/`) y la fecha de vigencia informada por el responsable (ADR-0006):

```
cargar_norma corpus/normativa/disp-afip-297-2003-original.htm --tipo Disposición --numero 297 --anio 2003 \
  --organismo AFIP --nombre "Disposición AFIP 297/03" \
  --titulo "Régimen General para Contrataciones de Bienes, Servicios y Obras Públicas de la AFIP" \
  --categoria regimen_especifico --parte cuerpo --regimen-general --fecha-publicacion 2003-06-13 \
  --fecha-vigencia 2003-06-14 --fuente https://servicios.infoleg.gob.ar/infolegInternet/anexos/85000-89999/86154/norma.htm \
  --usuario desarrollo
cargar_norma corpus/normativa/disp-afip-247-2022-original.htm --tipo Disposición --numero 247 --anio 2022 \
  --organismo AFIP --nombre "Disposición AFIP 247/2022" \
  --titulo "Régimen General para Contrataciones de Bienes, Servicios y Obras Públicas" \
  --categoria regimen_especifico --parte cuerpo --regimen-general --fecha-publicacion 2022-11-30 \
  --fecha-vigencia 2023-01-02 --fuente https://servicios.infoleg.gob.ar/infolegInternet/anexos/375000-379999/375829/norma.htm \
  --usuario desarrollo
cargar_norma corpus/normativa/disp-afip-247-2022-anexo.pdf --tipo Disposición --numero 247 --anio 2022 \
  --organismo AFIP --nombre "Disposición AFIP 247/2022" \
  --titulo "Régimen General para Contrataciones de Bienes, Servicios y Obras Públicas" \
  --categoria regimen_especifico --parte anexo --regimen-general --fecha-publicacion 2022-11-30 \
  --fecha-vigencia 2023-01-02 --fuente https://servicios.infoleg.gob.ar/infolegInternet/anexos/375000-379999/375829/disp247.pdf \
  --usuario desarrollo
```

(cada uno con `docker compose -p evaluon --env-file <.env> exec -T app python manage.py` adelante). El título de la 297/03 se escribió como lo trae el manifiesto: la página de Infoleg dice "Régimen Geeneral", con la errata. El anexo se sumó a la norma 2 como otra parte, sin pedir confirmación ("Se suma como parte anexo de la Disposición AFIP 247/2022, que ya tiene cargado el cuerpo").

**Revisión de los informes y ajuste de reglas.** Con las reglas 7 la carga dio las lecturas 1 (297/03, 403 unidades, 3 tramos no ubicados), 2 (cuerpo de la 247/2022, 13 unidades, 3 tramos no ubicados) y 3 (anexo, 335 unidades, 0 no ubicados). Las tres coinciden con las tablas esperadas de T-023 y T-050, que la suite comprueba contra los mismos archivos. Lo que mostraba "Requiere atención" y lo que se hizo:

- **Tramos no ubicados (297/03 y cuerpo de la 247/2022).** Ninguno es texto normativo, así que no se cambiaron las reglas. En la 297/03: el encabezado (ministerio, organismo, número, título, "Bs. As., 11/6/2003"), la fórmula "Por ello EL ADMINISTRADOR FEDERAL… DISPONE:" y el nombre del régimen que precede al "ANEXO I" ("REGIMEN GENERAL DE CONTRATACIONES / Régimen General para Contrataciones de Bienes, Servicios y Obras Públicas"). En el cuerpo de la 247/2022: el encabezado ("ADMINISTRACIÓN FEDERAL DE INGRESOS PÚBLICOS / Disposición 247/2022 / DI-2022-247-E-AFIP-AFIP / Ciudad de Buenos Aires, 28/11/2022"), la fórmula "Por ello, … DISPONE:" y la firma "Carlos Daniel Castagneto". Mostrarlos aparte como encabezado y fórmulas, en lugar de "no ubicado", es un cambio del informe que no hizo falta para cumplir la tarea y queda como propuesta.
- **Firma dentro del art. 5 de la 297/03.** El texto de `art-5` termina en "… y archívese. — Dr. ALBERTO R. ABAD, Administrador Federal.": la página trae la firma en el mismo párrafo que el artículo. El ADR-0004 admite que el cierre y la firma queden dentro del último artículo. No se cambió.
- **Últimos incisos seguidos de párrafos.** Se revisaron uno por uno contra el documento los 10 de la 297/03 y los 20 del anexo. Dos tenían una marca clara: el último inciso termina en dos puntos y presenta lo que sigue. Son "f) OTRAS OBLIGACIONES DEL CO-CONTRATANTE:" (297/03, Anexo I, art. 14) y el punto 4 del inciso e del art. 33 del anexo ("…a través de los siguientes medios:"), seguido de 4.1 y 4.2 (páginas 24 y 25). Se resolvieron con la regla nueva de las reglas 8 (abajo); desde las reglas 9 el informe los sigue señalando en "Requiere atención" para que quien valida lo compruebe. El resto queda para que lo decida quien valida. El texto del artículo, que es lo que se cita, está completo en todos los casos:
  - **24.h del anexo (página 18).** Los cuatro párrafos que siguen ("La unidad con capacidad de contratación… elaborará un proyecto de acuerdo…", el de la firma, el de la normativa supletoria y el de la difusión) son del inciso h (acuerdo interadministrativo), por paralelo con el inciso g. El PDF no tiene sangrías (todas las líneas empiezan en x0 = 70) ni otra marca que permita una regla razonable: quedan en `anexo/art-24`.
  - **27.b del anexo (página 20).** El párrafo que sigue al punto 3 del inciso b ("En las contrataciones que no tramiten en forma electrónica, en oportunidad de retirar o comprar el pliego…") es del punto b.3 (retiro del pliego); quedó en `anexo/art-27`. El artículo está completo.
  - **Discutibles.** 27.a.2 (cinco párrafos sobre las especificaciones del pliego) del anexo; 23.a (permuta) y 56.b (graduación de sanciones) de la 297/03.
  - **Los demás.** Son párrafos de cierre del artículo y están bien ubicados.
- **Página 45 del anexo.** "Sin texto": trae solo los campos de la firma digital (clasificación `solo_campos`). Es lo esperado.
- **Líneas descartadas.** En las páginas web son los dos scripts de medición de Infoleg, el encabezado HTML y, en la 247/2022, la nota de Infoleg sobre los anexos. Ninguna es texto de la norma.
- **Etiquetas de los arts. 24 y 26 del Anexo I de la 297/03.** Salen como "ARTICULO 24. —" sin epígrafe, porque la página no pone punto después del epígrafe ("CONTRATACIONES EN SOPORTE DIGITAL Las contrataciones…"). El texto está completo y la ruta es "Artículo 24". No se cambió.
- **Avisos 24.h y 33.e.4 de T-023.** 33.e.4 quedó resuelto; 24.h queda como está explicado arriba.
- **Cláusula transitoria.** `anexo/clausula-transitoria`, de tipo `clausula`, con la etiqueta "CLÁUSULA TRANSITORIA REGISTRO DE PROVEEDORES", página 44, después de `anexo/art-99`. Trae sus dos párrafos y nada de la firma.
- **Espaciado (avisos de T-012 y T-013).** El texto canónico del anexo trae "banco, repartición" dos veces y "del presente" 26 veces; ninguna forma pegada ("delpresente"), ningún doble espacio y ninguna unión de palabras cortadas.
- **Umbrales de clasificación de páginas (aviso de T-028).** Ninguna página del anexo se acerca a un umbral. La imagen más grande cubre el 1,2 % de su página (el logo de la página 1), contra el 85 % de `FULL_PAGE_IMAGE`. La proporción de caracteres sin letra es 0 en todas, contra el 10 % de `UNUSABLE_TEXT_SHARE`. 44 páginas salen `con_texto` y la 45, `solo_campos`. El corpus no trae escaneos reales, así que los umbrales de clasificación y de reconocimiento no se pudieron calibrar y quedan como estaban.
- **Dictámenes y recomendaciones (aviso de T-024).** El corpus todavía no tiene ninguno: las reglas de puntos y párrafos siguen probadas solo con documentos sintéticos.

**Reglas 8 (commit `T-043 (REQ-003, REQ-004)`).** Un último inciso sin incisos propios cuyo texto termina en dos puntos se lleva los párrafos que le siguen hasta el final de la unidad que contiene la lista. Comparadas con las unidades guardadas con las reglas 7, cambian dos unidades y ninguna otra:

- `anexo-i/art-14/inc-f` de la 297/03: caracteres 23239–23280 pasan a 23239–23813.
- `anexo/art-33/inc-e/inc-4` del anexo: 72842–73037 pasan a 72842–73686.

El texto canónico, las claves y las unidades base no cambian. "Párrafos después del último inciso" baja de 10 a 9 en la 297/03 y de 20 a 19 en el anexo.

**Relectura.** `releer_norma 1` y `releer_norma 3` con las reglas 8 dieron, en la primera carga, las lecturas 4 (297/03, 403 unidades) y 5 (anexo, 335 unidades), que se borraron con la recarga de abajo. El cuerpo de la 247/2022 no se releyó: con las reglas 8 da las mismas unidades y el mismo texto.

**Recarga con la vigencia 2023-01-02 (decisión del responsable, 2026-10-03).** La vigencia de la Disposición 247/2022 es el 2023-01-02, no el 2023-01-01. Sale de su art. 3: 20 días hábiles administrativos desde la publicación del 30/11/2022, descontando como inhábiles el 8/12, el 9/12 y el 20/12/2022. No había nada validado y no existe comando para corregir fechas, así que se rehizo la carga:

1. Respaldo con `pg_dump`, fuera del repositorio.
2. `down -v` del proyecto `evaluon` y `up -d --wait`: `migrate` aplicó todas las migraciones sobre la base vacía (0 normas, 0 hechos, 0 usuarios, ninguna migración pendiente).
3. Alta de nuevo de `desarrollo` (lectura y escritura, misma clave al azar fuera del repositorio).
4. Carga de los tres documentos con las reglas 8 y los mismos comandos de arriba, con `--fecha-vigencia 2023-01-02` en el cuerpo y en el anexo de la 247/2022. La 297/03 sigue con 2003-06-14.

**Comprobación.** Las unidades de las lecturas nuevas son las mismas que las de las lecturas 4, 2 y 5 de la carga anterior: misma clave y misma posición en las 403, 13 y 335 unidades. Los informes son iguales línea por línea, salvo el número de lectura, la fecha de lectura y la huella del informe. En el cuerpo de la 247/2022 cambia además "versión 7" por "versión 8" de las reglas.

**Reglas 9 y relectura (observaciones del testeador).** Dos cambios:

- **Aviso nuevo en el informe.** Cada último inciso que se llevó párrafos por terminar en dos puntos figura en "Requiere atención", por ejemplo "anexo-i/art-14/inc-f se llevó 1 párrafo que sigue a su presentación".
- **Regla extendida.** Si el inciso que contiene la lista es el último del artículo, su último punto que termina en dos puntos también se lleva lo que le sigue.

En el corpus no cambia ninguna unidad respecto de las reglas 8. Se integró `main`, con la decisión de vigencia del 2023-01-02, y se releyeron los tres documentos con `releer_norma 1`, `2` y `3`. Resultado: las lecturas 4 (297/03), 5 (cuerpo de la 247/2022) y 6 (anexo). Sus unidades son iguales a las de las lecturas 1, 2 y 3 en clave, posición, texto, etiqueta y ruta: 403, 13 y 335 unidades, sin diferencias.

**Estado de la base al terminar.** 2 normas, 3 documentos, 6 lecturas, todas pendientes de validación, y ninguna versión de la normativa. `listar_normas` da "Vigente desde 02/01/2023" en el cuerpo y en el anexo de la 247/2022, y "Vigente desde 14/06/2003" en la 297/03.

| Documento | Norma y parte | Lectura a validar | Lectura anterior (no se valida) |
|---|---|---|---|
| 1 | Disposición AFIP 297/03, cuerpo (con su Anexo I) | 4 | 1 |
| 2 | Disposición AFIP 247/2022, cuerpo | 5 | 2 |
| 3 | Disposición AFIP 247/2022, anexo | 6 | 3 |

Las lecturas 1, 2 y 3 no se pueden validar: su documento tiene una más nueva (`not_latest`).

**No borrar la copia de trabajo de T-043.** Los contenedores del proyecto `evaluon` montan el código de `C:\Users\snave\Documents\dev\EVALUON\.claude\worktrees\t043`. Esa copia no se borra hasta que T-043 esté integrada en `main` y los contenedores se hayan recreado desde la copia principal (`docker compose up -d`).

### Pasos para el responsable de normativa

Todos los comandos van en PowerShell, desde la copia principal, con el proyecto `evaluon` ya levantado:

```
cd C:\Users\snave\Documents\dev\EVALUON
```

Los que piden la clave o una confirmación necesitan una terminal interactiva. En Git Bash hay que anteponer `winpty` (por ejemplo, `winpty docker compose exec app python manage.py listar_normas --usuario SU_USUARIO`). En PowerShell funcionan tal cual. En todos, `SU_USUARIO` es el nombre que elija en el paso 2. No use `docker compose up`, `down` ni `build` hasta que T-043 esté integrada: con `exec` se trabaja sobre los contenedores que ya están corriendo, que montan la copia de trabajo de T-043 (no la borre).

**1. Comprobar que el sistema está arriba.**

```
docker compose ps
```

Tiene que ver `app`, `db`, `embeddings`, `generation` y `reranker` en estado `running`, con `(healthy)`.

**2. Crear su usuario, con rol de lectura y escritura.**

```
docker compose exec app python manage.py crear_usuario SU_USUARIO --rol lectura-escritura
```

Pide la clave dos veces y no la muestra. Tiene que ver "Se dio de alta el usuario SU_USUARIO con rol de lectura y escritura."

**3. Ver qué hay cargado.**

```
docker compose exec app python manage.py listar_normas --usuario SU_USUARIO
```

Pide su clave. Tiene que ver dos normas, las dos con "Categoría: Régimen específico · Régimen general: sí":

- la Disposición AFIP 247/2022, con la parte cuerpo (documento 2, "Lectura 5: pendiente de validación") y la parte anexo (documento 3, "Lectura 6: pendiente de validación"), las dos con "Publicada el 30/11/2022 · Vigente desde 02/01/2023";
- la Disposición AFIP 297/03, con la parte cuerpo (documento 1, "Lectura 4: pendiente de validación"), con "Publicada el 13/06/2003 · Vigente desde 14/06/2003".

**4. Mirar cada informe.**

```
docker compose exec app python manage.py ver_informe 4 --usuario SU_USUARIO
docker compose exec app python manage.py ver_informe 5 --usuario SU_USUARIO
docker compose exec app python manage.py ver_informe 6 --usuario SU_USUARIO
```

Al final de cada informe está la lista de unidades con su clave. Compárela con el original, que puede abrir en `corpus\normativa\`. Qué tiene que ver en cada uno:

- **Lectura 4 (297/03).**
  - "Reglas para dividir el texto: versión 9".
  - "Unidades reconocidas: 403 (visto, 8 considerandos, 69 artículos, 1 anexo, 324 incisos)", con "Cuerpo: … 5 artículos" y "Anexo I: 64 artículos, del 1 al 64", los dos con lo esperado igual a lo reconocido.
  - En "Requiere atención":
    - 3 tramos no ubicados (el encabezado, "Por ello … DISPONE:" y el nombre del régimen antes del Anexo I): ninguno es texto que deba citarse.
    - 9 últimos incisos con párrafos después: los de 23.a y 56.b son los discutibles; los demás son párrafos del artículo.
    - 1 último inciso que termina en dos puntos y se llevó el párrafo que le sigue: anexo-i/art-14/inc-f (el párrafo de confidencialidad, que es suyo).
    - 3 líneas descartadas, que son scripts y el encabezado de la página.
  - Revise también que `art-5` incluye la firma del Administrador Federal.
- **Lectura 5 (cuerpo de la 247/2022).**
  - "Reglas para dividir el texto: versión 9".
  - "Unidades reconocidas: 13 (visto, 7 considerandos, 5 artículos)".
  - En "Requiere atención": 3 tramos no ubicados (el encabezado, "Por ello, … DISPONE:" y la firma "Carlos Daniel Castagneto") y 4 líneas descartadas (scripts, título de la página y la nota de Infoleg).
- **Lectura 6 (anexo de la 247/2022).**
  - "Reglas para dividir el texto: versión 9".
  - "Unidades reconocidas: 335 (1 anexo, 99 artículos, 234 incisos, 1 cláusula)", con "Según el índice se esperaban 99 artículos; se reconocieron 99".
  - "No ubicado: 0 tramos".
  - En "Requiere atención":
    - la página 45 sin texto, que es la de la firma digital;
    - 19 últimos incisos con párrafos después. El de 24.h (página 18) deja en el artículo cuatro párrafos que son del inciso; el de 27.b (página 20) deja en el artículo un párrafo del punto b.3 (retiro del pliego); 27.a.2 es discutible; los demás son párrafos del artículo.
    - 1 último inciso que termina en dos puntos y se llevó los párrafos que le siguen: anexo/art-33/inc-e/inc-4, con sus puntos 4.1 y 4.2 (páginas 24 y 25).
  - Entre las unidades está `anexo/clausula-transitoria`, después de `anexo/art-99`.

Si algo no coincide, no valide esa lectura y avise al Coordinador.

**5. Validar cada lectura.**

```
docker compose exec app python manage.py validar_informe 4 --usuario SU_USUARIO
docker compose exec app python manage.py validar_informe 5 --usuario SU_USUARIO
docker compose exec app python manage.py validar_informe 6 --usuario SU_USUARIO
```

Cada uno pide su clave y muestra el resumen de la lectura: norma, parte, archivo, unidades y huella del informe. La huella es la misma que da `ver_informe`. Después muestra "Al validar, la norma queda disponible para consultas." y pregunta "¿Confirma la validación? Escriba si para confirmar:". Escriba `si`. Tiene que ver "Se validó la lectura N, con … pasajes. Quedó en uso como versión 1 de su parte." Cada validación pide los vectores al servicio de embeddings y tarda unos segundos.

**6. Comprobar el listado.**

```
docker compose exec app python manage.py listar_normas --usuario SU_USUARIO
```

Cada documento tiene que decir "validada · en uso, versión 1": documento 1 con la lectura 4, documento 2 con la lectura 5 y documento 3 con la lectura 6. "Vínculos: ninguno" y "Modificatorias sin cargar: ninguna" son lo esperado hasta T-044.

**7. Consulta en la pantalla con fecha 31/12/2022.**

1. Abra http://127.0.0.1:8000 en el navegador e ingrese con su usuario.
2. Escriba la pregunta "¿Por cuántos días deben los oferentes mantener sus ofertas?".
3. En la fecha de autorización ponga 31/12/2022 (día, mes y año) y envíe.

Tiene que ver:

- la respuesta con fundamento, con la línea "Procedimiento autorizado el 31/12/2022 · Régimen aplicado: Disposición AFIP 297/03";
- citas solo de la Disposición AFIP 297/03. La esperada es la del Anexo I, artículo 39 ("PLAZO DE MANTENIMIENTO DE LA OFERTA"), que fija TREINTA (30) días;
- ninguna cita de la 247/2022.

**8. La misma consulta con fecha 01/01/2023.** Repita la pregunta con la fecha 01/01/2023. Tiene que ver lo mismo que en el paso 7: "Procedimiento autorizado el 01/01/2023 · Régimen aplicado: Disposición AFIP 297/03", y citas solo de la 297/03. El 01/01/2023 la 247/2022 todavía no rige: rige desde el 02/01/2023.

Si repite la pregunta con la fecha del día, la pantalla nombra los dos regímenes y la respuesta puede citar cualquiera de los dos; la 247/2022 da SESENTA (60) días en el artículo 43 del anexo. Es lo esperado hasta que T-044 registre la derogación.

**Falta, fuera de esta parte.** La prueba en el navegador que pide T-043 la hace el Coordinador o el responsable con el corpus validado:

- el visor abre `disp-afip-247-2022-anexo.pdf` en la página citada;
- los originales de las dos páginas web no ejecutan scripts ni cargan recursos externos;
- el campo de fecha se ve y se completa bien.

## T-044 · Relaciones, versiones y modificatorias del corpus real (preparación)

Fecha: 2026-10-03. Requisitos: REQ-006, REQ-007, REQ-020 y REQ-021. El registro lo hace el responsable de normativa con su usuario (`sandro`). El desarrollador comprobó que estuviera todo, preparó el script de registro y el de comprobación, y probó los dos en un proyecto aparte. **Esta sección no registra nada en la base real:** lo registrado se anota cuando el responsable corra el script.

**Comprobación previa sobre la base real (solo lectura, usuario `desarrollo`).** Proyecto `evaluon`, levantado desde la copia principal:

- `listar_normas`: norma 1 = Disposición AFIP 297/03 (documento 1, lectura 4 validada, en uso, versión 1, vigente desde 14/06/2003); norma 2 = Disposición AFIP 247/2022 (cuerpo, documento 2, lectura 5, y anexo, documento 3, lectura 6, las dos validadas, en uso, versión 1, vigentes desde 02/01/2023). "Vínculos: ninguno" y "Modificatorias sin cargar: ninguna" en las dos. No hay relaciones ni modificatorias anotadas.
- `corpus/normativa/referencias/disp-afip-297-2003-modificatorias.csv` está en el corpus y la aplicación lo ve: 33 renglones, el último la Disposición 247/2022.
- La lectura en uso del cuerpo de la 247/2022 tiene la unidad `art-2`: "ARTÍCULO 2°.- Abrogar las Disposiciones Nros. 297 (AFIP) del 11 de junio de 2003, 393 (AFIP) del 6 de julio de 2005, 65 (SDG ADF) del 22 de noviembre de 2005 y su modificatoria, 153 (AFIP) del 11 de abril de 2008 y su modificatoria y 231 (AFIP) del 22 de agosto de 2017. …".
- Fecha: la tarea ya dice 2023-01-02, igual que la vigencia de los dos documentos de la 247/2022. No hubo que corregirla. El ejemplo del docstring de `registrar_relacion` (`evaluon/norms/management/commands/registrar_relacion.py`) todavía dice `--fecha 2023-01-01`: es texto de ayuda del código y no se tocó (queda como observación).

**Tercer paso: lista de las demás relaciones y versiones.** Revisados los tres documentos cargados:

- Relaciones entre normas cargadas: solo la derogación del paso 2. El art. 1 de la 247/2022 aprueba su propio anexo (misma norma, no es relación). Las demás normas que nombran los documentos (Decretos 1.399/01 y 618/97, y las Disposiciones 393/05, 65/05, 153/08 y 231/17 que deroga el art. 2) no están cargadas: no se puede registrar una relación hacia o desde ellas.
- Versiones: ninguna. Cada documento tiene una sola versión (la 1, en uso) y no hay texto nuevo de ninguno.

Por eso el tercer paso no corre ningún comando. REQ-007 con el corpus real (una norma que modifica un artículo de otra) **queda pendiente**: se comprueba cuando se cargue la primera modificatoria, en la tarea que abra el Coordinador para esa carga.

**Script para el responsable.** `registrar_t044.ps1`, en el scratchpad de la tarea (fuera del repositorio). Se abre en una ventana propia de PowerShell (`Start-Process powershell -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-File','<ruta>'`), se posiciona en la copia principal y corre, con `docker compose exec app python manage.py … --usuario sandro`:

1. `registrar_modificatorias --alcanzada 1 --archivo corpus/normativa/referencias/disp-afip-297-2003-modificatorias.csv`
2. `registrar_relacion --tipo deroga --origen 2 --unidad-origen art-2 --alcanzada 1 --fecha 2023-01-02`
3. (sin comando: muestra que no hay otras relaciones ni versiones)
4. `listar_normas`

Solo pide la clave en cada comando; ninguno pide confirmación. Si un paso falla, se detiene y pide avisar al Coordinador. Volver a correrlo es seguro hasta el paso 2: el paso 1 informa "Ya estaban anotadas" y no crea versión, y una segunda derogación igual se rechaza por repetida.

**Prueba en un proyecto aparte.** Proyecto `evaluon-t044s` (con el archivo de variables del Coordinador y sin puerto publicado), con la base vacía: `migrate`, usuarios `desarrollo` y `sandro` con una clave de prueba, carga de los tres documentos con los mismos comandos de T-043 (normas 1 y 2 con los mismos números que en la base real) y validación de las tres lecturas con el doble de embeddings. El script, corrido entero sobre esa base, dio:

```
Se anotaron 33 modificatorias sin cargar de la Disposición AFIP 297/03.
…
Quedan 33 modificatorias sin cargar de la Disposición AFIP 297/03.
Se creó la versión 4 de la normativa.
Se registró la relación 1: la Disposición AFIP 247/2022 (art-2) deroga a la Disposición AFIP 297/03 (la norma entera), desde el 02/01/2023.
Se creó la versión 5 de la normativa.
La Disposición AFIP 247/2022 quedó cargada como modificatoria de la Disposición AFIP 297/03.
Quedan 32 modificatorias sin cargar de la Disposición AFIP 297/03.
```

En `listar_normas`, la 247/2022 muestra "Deroga a Disposición AFIP 297/03 (norma 1) · origen: art-2 · alcanza: la norma entera · desde el 02/01/2023 · relación 1" y "Modificatorias sin cargar: ninguna"; la 297/03, "Derogada por Disposición AFIP 247/2022 (norma 2) · … · desde el 02/01/2023 · relación 1" y "Modificatorias sin cargar: 32". Con una clave equivocada el script se detiene en el paso 1 con "Usuario o clave incorrectos." y el aviso de no seguir.

**Comprobación posterior.** `comprobar_t044.py`, en el mismo scratchpad, se corre después del registro, desde la copia principal:

```
docker compose exec -T app python manage.py shell < comprobar_t044.py
```

Con el usuario `desarrollo` (canal comando) comprueba lo que pide la Verificación de T-044 e imprime OK o FALLA por punto:

1. La relación `deroga` de la 247/2022 (`art-2`) a la 297/03 entera desde el 2023-01-02, vista desde las dos normas, y ninguna otra relación.
2. Modificatorias de la 297/03: las 33 del archivo anotadas, 32 sin cargar y la 247/2022 cargada.
3. `ask` con la pregunta "¿Por cuántos días deben los oferentes mantener sus ofertas?": con 2023-01-01, con fundamento, un solo régimen (la 297/03), citas solo de la 297/03 y aviso de 32 modificatorias sin cargar; con 2023-01-02, un solo régimen (la 247/2022), citas solo de la 247/2022 y sin aviso.
4. Búsqueda del art. 1 de la 297/03 con la fecha del día: sin la casilla de derogados no muestra ninguna unidad vigente y avisa las derogadas ocultas; con la casilla, cada unidad aparece marcada como derogada por la 247/2022 desde el 2023-01-02, con el aviso de modificatorias; el régimen del día es solo la 247/2022.
5. Auditoría: los hechos `pending_amendment` y `relation` con resultado `ok` y usuario `sandro`.

Las dos consultas y las dos búsquedas quedan en el registro de consultas y de auditoría, como cualquier consulta. En el proyecto aparte, con los dobles de los tres clientes de IA (variable `T044_DOBLES=1`, solo para esa prueba), dio 25 de 25 comprobaciones OK: la búsqueda devolvió `Artículo 1` y `Anexo I › Título I › Artículo 1`, las dos derogadas por la 247/2022 desde el 2023-01-02. Con los servicios reales, la respuesta y las citas dependen del modelo: lo esperado es el art. 39 del Anexo I de la 297/03 (TREINTA días) con 2023-01-01 y el art. 43 del anexo de la 247/2022 (SESENTA días) con 2023-01-02.

**En la pantalla, después del registro.** La Verificación pide además la prueba en la pantalla: la misma pregunta con 01/01/2023 tiene que mostrar "Régimen aplicado: Disposición AFIP 297/03", citas solo de la 297/03 y el aviso de modificatorias sin cargar; con 02/01/2023, "Régimen aplicado: Disposición AFIP 247/2022", citas solo de la 247/2022 y sin aviso. En la búsqueda, el artículo 1 de la 297/03 con la fecha del día aparece solo marcando la casilla de derogados, y marcado como derogado por la 247/2022.

**Observaciones.**

- El art. 2 de la 247/2022 abroga también las Disposiciones 393/05, 153/08 y 231/17, que figuran en el listado como modificatorias de la 297/03 (la 231/17 como "Disposición E"). Mientras no se carguen siguen contando entre las 32 sin cargar, y el aviso las cuenta en las respuestas que citan la 297/03. Es lo que pide la Verificación ("las del archivo menos la 247/2022"); si el responsable prefiere otro criterio, es una decisión aparte.
- Las anotaciones del CSV usan el organismo "ADMINISTRACION FEDERAL DE INGRESOS PUBLICOS" y la norma cargada, "AFIP". No afecta a la 247/2022: la coincidencia es por tipo, número y año, y el organismo solo desempata (T-057 trata la equivalencia de organismos).

## T-045 · Calibración del umbral de abstención

**Valor:** `RERANK_THRESHOLD = 0.368` (provisorio), fijado el 2026-10-03 en `evaluon/settings.py`. Reemplaza al 0,5 inicial (punto medio de la sigmoide).

**Corrida de la que sale:** `evals/corridas/2026-10-03T132016_8ad46e6_gemma-4-12b-it-qat-q4_0` (commit `8ad46e6`, normativa versión 5, instrucciones `consulta-v2`, umbral configurado durante la corrida 0,5). Se corrió una sola vez, con los servicios reales del proyecto `evaluon` y el corpus validado:

```
docker compose -p evaluon exec app python manage.py correr_evals --usuario desarrollo
```

Duró de 13:20:16 a 13:22:35. Dejó 31 consultas en el registro (canal `eval`) y 31 hechos `query` de auditoría con el usuario `desarrollo`, más su ingreso por comando.

**Preguntas que entraron.** 31 casos leídos y corridos, todos con visto bueno. En la calibración entraron 24 preguntas con respuesta (todas con puntaje) y 6 sin respuesta con puntaje; EV-031 (sin régimen cargado a la fecha) no llega al reranker y no tiene puntaje.

**Cómo se obtuvo.** Puntajes más altos de las preguntas con respuesta, de menor a mayor: 0,368 (EV-020), 0,508 (EV-004), 0,748 (EV-007) y el resto entre 0,984 y 1,000. Dejando cada vez una afuera, la k más alta que no pasa del 5 % es k = 0 (frena 1 de 24, 4,2 %; el umbral calculado va de 0,368 a 0,507). El umbral es el puntaje de EV-020 redondeado hacia abajo. La regla sin dejar ninguna afuera daría 0,507, que frena EV-020 y, dejando cada vez una afuera, frenaría el 8,3 %. Hay 24 preguntas con respuesta, así que no se aplica el caso de menos de 20.

**Preguntas con respuesta que frena el umbral.** Con 0,368: ninguna en el conjunto completo (la comparación es puntaje igual o mayor). Con el 0,5 de la corrida frenó una: EV-020 (multa con prórroga del plazo de entrega, 297/03, art. 58 del Anexo I, puntaje 0,368). El margen es nulo: EV-020 pasa justo en el umbral, y una variación mínima del puntaje la vuelve a frenar.

**Preguntas sin respuesta por debajo del umbral.** 3 de 6: EV-025 (0,120), EV-026 (0,022) y EV-030 (0,003). Quedan por encima EV-027 (0,775), EV-028 (0,988) y EV-029 (0,743); de esas, el modelo se abstuvo en EV-027 y EV-029 y respondió en EV-028 (art. 50 del anexo de la 247/2022). Ningún umbral que no frene preguntas con respuesta separa a EV-027, 028 y 029: su abstención depende del modelo, no del umbral.

**Resultado de la corrida (con el umbral 0,5, para T-046).** Cita literal 100 % (72 de 72); respuesta correcta 45,8 % (11 de 24); abstención 85,7 % (6 de 7); tiempo mediana 4,54 s y máximo 9,62 s. Las fallas de respuesta correcta son casi todas por datos clave faltantes (aviso de T-039: los datos clave de 16 casos son frases compuestas o parafraseadas). Aviso de REQ-021: falla solo EV-020, porque fue frenada y no hubo respuesta que citara la 297/03. Los tres pares de REQ-020 fallan porque alguno de sus casos no pasa por su cuenta (por datos clave), no por el régimen. La corrida no midió con el umbral nuevo: eso queda para T-046.

**Observaciones de los avisos.**

- (T-031) Los 30 candidatos por significado no se llenan con pocas unidades largas, pero en la 297/03 una unidad larga ocupa varios lugares. Por cada 30 pasajes llegan 25 a 30 unidades distintas en las preguntas con respuesta de la 247/2022, 19 a 27 en las de la 297/03 y 22 a 29 en las sin respuesta. El art. 58 del Anexo I de la 297/03 (17.298 caracteres, 7 pasajes) ocupa los 7 lugares en EV-020 y EV-023, y entre 3 y 6 en otras seis; los arts. 55, 25, 21 y 29 del Anexo I, de 3 a 4 cada uno. En la 247/2022, el máximo es 4 pasajes de una unidad (arts. 24 y 33 del anexo). La unión fue de 37 a 49 pasajes (27 a 44 unidades) y la recuperación tardó mediana 0,62 s y máximo 1,40 s. EV-020 es justamente la del art. 58: su unidad quedó primera, pero con 0,368, muy por debajo de las demás preguntas con respuesta. Puede que el pasaje que contiene la multa por prórroga no sea el que mejor puntúa con el solapamiento de `PASSAGE_OVERLAP_TOKENS = 100`; no se probó otro valor (cambiarlo exige reindexar y correr las evals, P7).
- (T-040) Afirmaciones y citas por respuesta, en las 23 preguntas con respuesta que respondieron: 1 afirmación en 7, 2 en 4, 3 en 5, 4 en 2, 5 en 1 y 6 (el máximo permitido) en 4 (EV-002, EV-008, EV-011, EV-019). Se repite lo de T-040: EV-001 (plazo de mantenimiento de oferta) da 5 afirmaciones con la misma cita (art. 43 del anexo); EV-011 y EV-019 dan 6 con una sola unidad citada. Las respuestas cortas (EV-012, 014, 018, 021, "¿puede…?") dan 1 afirmación y no incluyen el "no" o "sí" que piden sus datos clave. Las 72 citas son literales y ninguna salida tuvo falla de formato ni de cita.
- (T-032) Ninguna pregunta del conjunto nombra un artículo: el camino por referencia exacta no trajo la unidad correcta en ninguna (0 de 24), así que el caso de un artículo nombrado fuera de la selección no se pudo observar. Sí quedó fuera de la selección una unidad esperada por el límite de 3 por categoría: en EV-024 (plazo para observar el acta de evaluación, 297/03) el art. 21 del Anexo I quedó 4.º con 0,894 detrás de los arts. 50 (0,995), 47 (0,958) y 17 (0,924), y la respuesta citó el art. 50. Con el umbral nuevo no cambia: es `SELECTION_UNITS_PER_CATEGORY = 3`.

**Pendiente.** El valor es provisorio y sale de 24 preguntas con respuesta: con k = 0 el umbral es el mínimo observado y no deja margen. Se recalibra cuando el conjunto crezca o cambien los datos clave, el corpus, el reranker o el armado de pasajes.

## T-059 · Datos clave reescritos y corrida de T-045 recalificada

**Carpeta:** `evals/corridas/2026-10-03T145904_30dc41e_gemma-4-12b-it-qat-q4_0_recalificada`, recalificación de `evals/corridas/2026-10-03T132016_8ad46e6_gemma-4-12b-it-qat-q4_0` con los casos del commit `30dc41e` (datos clave reescritos, sección "Reescritura por el ADR-0011 (2026-10-03)" de `evals/casos/INDICE.md`) y el corrector de T-058. No se hicieron consultas ni se usó la GPU; la carpeta original no cambió. Una recalificación no es una corrida nueva para P7.

Se corrió en un proyecto Docker aparte, con una base de prueba vacía y un usuario sintético de lectura creado para esto; no se usó la base `evaluon`:

```
docker compose -p evaluon-t059 --env-file <coord.env> up -d db
docker compose -p evaluon-t059 --env-file <coord.env> run --rm --no-deps app python manage.py migrate
docker compose -p evaluon-t059 --env-file <coord.env> run --rm --no-deps app python manage.py correr_evals --usuario <usuario sintético> --commit 30dc41e --recalificar evals/corridas/2026-10-03T132016_8ad46e6_gemma-4-12b-it-qat-q4_0 --casos evals/casos --corridas evals/corridas
docker compose -p evaluon-t059 down -v
```

Dentro del contenedor no hay `.git`: sin `--commit` la carpeta sale con `sin-commit` en el nombre.

**Respuesta correcta que cita la unidad correcta (24 preguntas con respuesta):**

| Medida | Resultado |
|---|---|
| Corrida original (T-045), datos y corrector anteriores | 45,8 % (11 de 24) |
| Recalificada con el corrector de T-058 y los datos anteriores | 50,0 % (12 de 24) |
| Recalificada con el corrector de T-058 y los datos de T-059 | 79,2 % (19 de 24) |
| Lo mismo, sin las cuatro variantes tomadas de la corrida (punto 1 de `INDICE.md`) | 62,5 % (15 de 24) |

Pasan ahora y antes no: EV-003, EV-005 (por el corrector), EV-011, EV-012, EV-014, EV-016, EV-018 y EV-021. Ningún caso que pasaba dejó de pasar. Pares de REQ-020: pasan EV-001 y EV-016 y EV-014 y EV-018; EV-003 y EV-017 falla por EV-017. Las demás medidas no cambian: cita literal 100 %, abstención 85,7 % (6 de 7), tiempo mediana 4,54 s y máximo 9,62 s, aviso de REQ-021 30 de 31 (falla EV-020).

**Casos que siguen fallando y su causa:**

| Caso | Causa | Detalle |
|---|---|---|
| EV-006 | Respuesta incompleta | Da los 5 días y que no suspende, pero omite la revisión ante la máxima autoridad |
| EV-009 | Respuesta incompleta | Nombra 6 de las 8 modalidades: faltan el acuerdo marco interadministrativo y el acuerdo interadministrativo por imperio normativo |
| EV-017 | Respuesta incompleta | Da los 8 días, pero omite que vencido el plazo se rescinde con pérdida de la garantía de la oferta |
| EV-020 | Abstención indebida | El umbral de la corrida (0,5) la frenó con 0,368 y no hubo respuesta; con el umbral provisorio 0,368 pasaría justo, pero eso lo mide la corrida nueva de T-046 |
| EV-024 | Artículo que no llega a la selección | El art. 21 del Anexo I quedó 4.º por el límite de 3 unidades por categoría; la respuesta solo da los 3 días del art. 50 |

Ningún caso con respuesta falla ya por una forma de decirlo que el caso no prevé, siempre que el responsable acepte las cuatro variantes tomadas de la corrida; si las rechaza, vuelven a fallar por eso EV-003, EV-014, EV-016 y EV-018. Fuera de esta medida, EV-028 (sin respuesta) sigue sin abstenerse: responde con el art. 50 del anexo de la 247/2022.

**Para T-046:** la corrida anterior para comparar es esta carpeta recalificada. El 85 % no se tocó.

## T-062 · Umbral de abstención con la regla del hueco

**Valor:** `RERANK_THRESHOLD = 0.219` (provisorio), fijado el 2026-10-03 en `evaluon/settings.py` con la regla del ADR-0014, punto 2. Reemplaza al 0,368 de T-045, que queda como dato histórico en la sección de T-045.

**Comprobación previa.** Desde la corrida de T-045 (commit `8ad46e6`) no cambió nada que mueva los puntajes del reranker:

- Modelo, compilación y parámetro del reranker: `docker-compose.yml` sin cambios (`bge-reranker-v2-m3-FP16.gguf`, misma huella, compilación `b11347`, `add_sep_token` forzado).
- Recuperación y armado de pasajes: `evaluon/queries/retrieval.py` y `evaluon/norms/indexing.py` sin commits; en `settings.py` el único cambio es `RERANK_THRESHOLD` (T-045), que no interviene en los puntajes guardados.
- Corpus: versión de la normativa 5, sin cargas, validaciones ni registros nuevos (lo confirmó el Coordinador).
- Casos del lote de ajuste: en `evals/casos/` solo cambiaron los `datos_clave` (T-059); la pregunta y la fecha de los 31 casos son las mismas.

**Carpeta de la recalificación:** `evals/corridas/2026-10-03T162823_1728ccc_gemma-4-12b-it-qat-q4_0_recalificada`, de la corrida `evals/corridas/2026-10-03T132016_8ad46e6_gemma-4-12b-it-qat-q4_0`, con el código de T-060 (commit `1728ccc`). No se hicieron consultas ni se usó la GPU. Se corrió en un proyecto Docker aparte, con una base de prueba vacía y un usuario sintético de lectura creado para esto (deja sus hechos `user_created` y `login` en esa base, que se borró al terminar); no se usó la base `evaluon`:

```
docker compose -p evaluon-t062 --env-file <coord.env> up -d db
docker compose -p evaluon-t062 --env-file <coord.env> run --rm --no-deps app python manage.py migrate
docker compose -p evaluon-t062 --env-file <coord.env> run --rm --no-deps app python manage.py crear_usuario <usuario sintético> --rol lectura
docker compose -p evaluon-t062 --env-file <coord.env> run --rm --no-deps app python manage.py correr_evals --usuario <usuario sintético> --commit 1728ccc --recalificar evals/corridas/2026-10-03T132016_8ad46e6_gemma-4-12b-it-qat-q4_0 --casos evals/casos --corridas evals/corridas
docker compose -p evaluon-t062 down -v
```

La corrida de T-045 no tiene lote en sus renglones: sus 31 casos cuentan como de ajuste. El lote de aceptación no está en esa corrida y no se recalifica.

**Cómo se obtuvo:**

| Dato | Caso | Puntaje | Escala anterior a la sigmoide |
|---|---|---|---|
| A: ajena a la normativa más alta | EV-025 | 0,1195 | −1,9967 |
| B: con respuesta más baja | EV-020 | 0,3680 | −0,5407 |
| Punto medio | — | 0,2195 | −1,2687 |

El umbral es el punto medio redondeado hacia abajo a tres decimales: 0,219. Margen 0,728 (la mitad del hueco en la escala anterior a la sigmoide; mínimo 0,5): cumple el margen mínimo. El logit de A es −1,9967 con el puntaje completo; el −1,9972 del plan sale del 0,1195 redondeado.

**Preguntas sin respuesta que frena:** EV-025 (0,1195), EV-026 (0,0218) y EV-030 (0,0032), las tres ajenas a la normativa. Las mismas que frenaban 0,5 y 0,368.

**Preguntas con respuesta que frena:** ninguna de 24. EV-020 queda por encima con margen, no justo en el umbral como con 0,368.

**Preguntas de tema cercano por encima del umbral:** EV-027 (0,7751), EV-028 (0,9881) y EV-029 (0,7430). Por la regla, las tiene que frenar el modelo, no el umbral. En la corrida de T-045 el modelo se abstuvo en EV-027 y EV-029 y respondió en EV-028.

**Aviso del ADR-0015.** T-064 no estaba integrada al recalificar: EV-027, EV-028 y EV-029 siguen siendo de tema cercano. Cuando T-064 se integre pasan a tener respuesta, quedan como no recalificables en una recalificación de esta corrida (cambió la presencia de respuesta) y el resumen deja de listarlas como tema cercano por encima del umbral. El umbral no cambia: sus puntajes (0,743 a 0,988) están por encima del de EV-020, así que A sigue siendo EV-025 y B, EV-020.

**Tests que suponían el umbral por omisión (ampliación de la tarea, decisión del Coordinador, 2026-10-03).** Con 0,219 fallaron 7 tests que usan puntajes sintéticos entre 0,219 y 0,368 (0,3 y 0,25) y esperaban que el umbral por omisión los frenara sin fijarlo: tres de `tests/queries/test_acceptance_lot.py`, tres de `tests/queries/test_evaluation_diagnostics.py` y uno de `tests/queries/test_retrieval_selection.py`. Cada uno fija ahora con el fixture `settings` el umbral que supone (0,368), como `test_retrieval.py`; los puntajes sintéticos no cambiaron. Así no dependen del valor calibrado.

**Efecto del cambio.** El paso de 0,368 a 0,219 no se midió con respuestas nuevas: lo mide la corrida de T-046 (P7). Por su nombre, esta carpeta pasa a ser la corrida anterior con la que se compara T-046, en lugar de la de T-059.

## T-063 · Instrucciones `consulta-v3` (remisión a una norma no cargada)

**Carpeta de la corrida:** `evals/corridas/2026-10-03T165105_d5b96d4_gemma-4-12b-it-qat-q4_0` (commit `d5b96d4`, instrucciones `consulta-v3`, umbral 0,219 de T-062, normativa versión 5, casos EV-001 a EV-033 de T-064; ningún caso del lote de aceptación). Una sola corrida, con los servicios reales del proyecto `evaluon` y su base, desde la copia principal, con el código y las evals de la rama montados encima del contenedor `app`:

```
docker compose -p evaluon run --rm --no-deps -T -v <rama>/evaluon:/app/evaluon:ro -v <rama>/evals:/app/evals app python manage.py correr_evals --usuario desarrollo --commit d5b96d4 --casos evals/casos --corridas evals/corridas < <archivo con la clave>
```

Duró de 16:51:05 a 16:54:13. Dejó 33 consultas (canal `eval`) y sus hechos `query` con el usuario `desarrollo`, más su ingreso por comando. No se tocaron contenedores ni volúmenes del proyecto `evaluon`.

**Qué cambia la v3 respecto de la v2.**

- Regla 10, nueva: si una unidad trata el punto pero remite su contenido a otra norma que no está entre las unidades, responder lo que dice la unidad y a qué norma remite, con sus palabras, y citarla; no dar el contenido de la norma remitida aunque se crea conocerlo; esa respuesta es `grounded`.
- Regla 11, la de abstención reescrita: `undetermined` solo si ninguna unidad trata el punto, ni siquiera para remitirlo.
- La descripción de `status` en el formato, alineada con la regla 11.
- Un ejemplo de la forma con una remisión ilustrativa ("plazo que fije la reglamentación").

Las reglas 1 a 9, el esquema y la validación son los de la v2. No se sumó la línea opcional de "responder solo lo que se pregunta".

**Medidas contra la anterior** (`evals/corridas/2026-10-03T162823_1728ccc_gemma-4-12b-it-qat-q4_0_recalificada`: v2, umbral de la corrida 0,5, casos de T-062). La corrida mide juntos la v3, el umbral 0,219 y los casos de T-064 (EV-027 a EV-029 pasan a tener respuesta; EV-032 y EV-033 son nuevos).

| Medida (lote de ajuste) | Anterior | T-063 |
|---|---|---|
| Cita literal | 100,0 % (72 de 72; IC 95 %: 94,9 % a 100 %) | 100,0 % (74 de 74; IC 95 %: 95,1 % a 100 %) |
| Respuesta correcta | 79,2 % (19 de 24; IC 95 %: 59,5 % a 90,8 %) | 81,5 % (22 de 27; IC 95 %: 63,3 % a 91,8 %) |
| Respuesta correcta, solo los 24 casos comunes | 19 de 24 | 19 de 24 |
| Abstención | 85,7 % (6 de 7; IC 95 %: 48,7 % a 97,4 %) | 100,0 % (6 de 6; IC 95 %: 61,0 % a 100 %) |
| Abstención, solo los 4 casos comunes (EV-025, 026, 030, 031) | 4 de 4 | 4 de 4 |
| Respuesta correcta, 247/2022 (diagnóstico) | 86,7 % (13 de 15; IC 95 %: 62,1 % a 96,3 %) | 82,4 % (14 de 17; IC 95 %: 59,0 % a 93,8 %) |
| Respuesta correcta, 297/03 (diagnóstico) | 66,7 % (6 de 9; IC 95 %: 35,4 % a 87,9 %) | 80,0 % (8 de 10; IC 95 %: 49,0 % a 94,3 %) |
| Unidad correcta entre las enviadas al modelo | 91,7 % (22 de 24) | 96,3 % (26 de 27) |
| Preguntas con respuesta frenadas por el umbral | 1 de 24 (EV-020) | 0 de 27 |
| Pares de REQ-020 | 2 de 3 | 3 de 4 |
| Aviso de REQ-021 | 30 de 31 | 33 de 33 |
| Fallas de formato o de cita | 0 | 0 |
| Tiempo de respuesta | mediana 4,54 s · máximo 9,62 s | mediana 4,79 s · máximo 29,52 s |
| Tiempo de la recuperación | mediana 0,62 s · máximo 1,40 s | mediana 0,60 s · máximo 3,50 s |

Caso por caso, en lo que cambió:

| Caso | Anterior | T-063 | Causa |
|---|---|---|---|
| EV-003 | pasa | falla | Redacción: dice "prorrogado por un término igual"; el dato pide "igual término" o "período igual" y el corrector no acepta el orden cambiado (regla 5). El contenido es correcto y las citas son las mismas (arts. 61 y 66 del anexo) |
| EV-020 | falla (frenada por el umbral 0,5 con 0,368) | pasa | Umbral 0,219: llega al modelo y responde el 1 % por cada 7 días corridos o fracción mayor de 3 días, con el art. 58 del Anexo I |
| EV-027 | abstención (`model_abstained`; entonces sin respuesta) | pasa | v3: responde la remisión al régimen jurisdiccional vigente |
| EV-028 | responde (entonces contaba como falla) | pasa | Ya respondía la remisión con la v2; ahora es una pregunta con respuesta |
| EV-029 | abstención (`model_abstained`; entonces sin respuesta) | pasa | v3: responde la remisión al Régimen Jurisdiccional vigente, con el aviso de modificatorias |
| EV-002 | 6 afirmaciones (arts. 64 y 66) | 5 (art. 64) | Omite la de las excepciones del art. 66; sigue pasando |
| EV-007 | 3 afirmaciones (arts. 88 y 81) | 2 (art. 88) | Omite la multa doble del art. 81; sigue pasando |
| EV-010 | 1 afirmación (art. 24) | 2 (arts. 24 y 64) | Suma la regla general del 5 % del art. 64; sigue pasando |
| EV-004, EV-012 | — | — | Mismas citas en otro orden o una afirmación más; siguen pasando |
| EV-032, EV-033 | no existían | abstención | Frenadas por el umbral (0,0011 y 0,0234), no por el modelo |

Siguen fallando, con la misma causa que en T-059: EV-006 (omite la revisión ante la máxima autoridad), EV-009 (faltan dos modalidades), EV-017 (omite la pérdida de la garantía de la oferta) y EV-024 (el art. 21 del Anexo I no llega a la selección por el límite de 3 unidades por categoría).

**Bajas (P7).** Ninguna medida exigida baja, y el comando informa "Sin bajas respecto de la corrida anterior". Bajan, sin ser exigencias:

1. **EV-003 pasa a fallar.** Por la redacción ("un término igual"), no por la cita ni por el contenido. En los 24 casos comunes la respuesta correcta queda igual (19), porque EV-020 pasa a pasar.
2. **Respuesta correcta de la 247/2022 (diagnóstico):** de 86,7 % a 82,4 %, por EV-003; los casos nuevos de esa norma (EV-027 y EV-028) pasan.
3. **Tiempo máximo:** de 9,62 s a 29,52 s, a 0,48 s del límite de 30 s. Es EV-001, la primera consulta de la corrida: 25,2 s de generación y 3,5 s de recuperación (también el máximo de la recuperación). Las cuatro siguientes tardaron entre 8 y 10 s, y desde EV-006 los tiempos vuelven a los de la anterior. Parece el arranque en frío del motor después de horas sin uso (aviso de T-018), no la v3, que agrega 109 palabras a las instrucciones (de 698 a 807); no se comprobó. Por la regla de T-042 no es una baja (el máximo no supera 30 s y la mediana sube 5,5 %), pero queda sin margen.

Si el responsable no aprueba las bajas 1 y 2, la v3 no se integra activa. La 1 se resolvería con una variante "término igual" en EV-003, que es un cambio de caso y no de esta tarea.

**Pares de REQ-020:** pasan EV-001 y EV-016, EV-014 y EV-018, y EV-022 y EV-028; falla EV-003 y EV-017, por los dos casos (EV-003 por la redacción, EV-017 por la pérdida de la garantía de la oferta). En la anterior fallaba solo por EV-017. En EV-028 la v3 dice "normativa vigente" y no agrega los "tres miembros titulares" del art. 48 de la 297/03, que sí da EV-022 con su fecha.

**Aviso de modificatorias:** 33 de 33 según lo esperado. EV-029 lo trae (297/03, 32 modificatorias sin cargar); EV-020, que antes fallaba por no tener respuesta, también.

**EV-032 y EV-033 (tema cercano).** Se abstienen, pero las frena el umbral (`below_threshold`, puntajes 0,0011 y 0,0234), no el modelo. En esta corrida ninguna pregunta sin respuesta llega al modelo: la regla de abstención reescrita de la v3 no quedó probada con el modelo real en una pregunta de tema cercano. Lo mide el lote de aceptación en T-046.

**Revisión de los casos de remisión** (afirmaciones contra el texto literal de la unidad citada, leído de la base):

| Caso | Respuesta de la v3 | Unidad citada | Revisión |
|---|---|---|---|
| EV-027 (2025-06-30, 247/2022) | "La licitación privada es aplicable cuando el monto estimado no supere el máximo estipulado en el régimen jurisdiccional vigente." "El procedimiento de selección es válido siempre que el monto total a adjudicar no supere el máximo fijado para su encuadre en el régimen jurisdiccional vigente." | Art. 21 del anexo (las dos) y art. 22 (la segunda) | Sin cifra ni monto: todo está en el inc. c) del art. 21; la segunda frase también está en el art. 22. Correcta |
| EV-028 (2024-11-11, 247/2022) | "La integración, las condiciones de funcionamiento y los criterios de designación de los miembros de la comisión evaluadora están sujetos a la normativa vigente." "Los miembros de la comisión evaluadora no pueden ser funcionarios que tengan la competencia para autorizar la convocatoria o aprobar el procedimiento de selección." | Art. 50 del anexo | Sin integración: dice "normativa vigente" y no agrega los "tres miembros titulares" de la 297/03. Correcta |
| EV-029 (2015-10-01, 297/03) | "La contratación directa por monto puede realizarse cuando el monto del contrato no supere el establecido en el Régimen Jurisdiccional vigente para este tipo de contrataciones." | Art. 21 del Anexo I (inc. 4, punto 9) | Sin cifra ni monto; trae el aviso de modificatorias. Correcta |

Respuesta correcta del lote de ajuste: automática 81,5 % (22 de 27); corregida por la revisión, igual, porque la revisión no marcó ningún caso. La revisión la hizo el desarrollador; falta la del testeador evaluador.

**Polaridad (aviso de T-059):** EV-006 ("no tiene carácter suspensivo"), EV-012 ("desestimada sin posibilidad de subsanación"), EV-014 ("no pueden incluir"), EV-018 ("puede prever otras causales", 297/03) y EV-021 ("no es necesario") tienen la polaridad correcta. EV-004 empieza con la regla general y en la segunda afirmación dice que no hace falta hasta M 1.000: es correcta, pero no empieza con "no".

**Afirmaciones por respuesta (aviso de T-040):** en las 27 respuestas con fundamento, mediana 2 y máximo 6. Cinco tienen 5 o más: EV-001 (5), EV-002 (5), EV-011 (6) y EV-019 (5), todas con una sola unidad citada, y EV-008 (6, con tres unidades). Sigue pasando lo de T-040. Ninguna respuesta cita un considerando.

**Tests (con los dobles):** `tests/queries/test_prompt_v3.py`, nuevo. `docker compose -p evaluon-t063 --env-file <coord.env> run --rm --no-deps app pytest`: 1589 pasan.

## T-046 · Corrida de las evals que se presenta para aprobar, tiempo y memoria

**Corrida que se presenta:** `evals/corridas/2026-10-03T171739_14ef270_gemma-4-12b-it-qat-q4_0`.

- Commit `14ef270`, instrucciones `consulta-v3`, umbral 0,219, normativa versión 5.
- 56 casos, todos con visto bueno: 33 del lote de ajuste y 23 del lote de aceptación.
- Comprobado antes de correr:
  - `RERANK_THRESHOLD = 0.219` en `settings.py`;
  - `PROMPT_VERSION_WITH_DATE = "consulta-v3"` en `answering.py`;
  - EV-027, EV-028 y EV-029 con respuesta y con el dato clave de la remisión.

**Dónde y cómo se corrió.** Tres corridas, de a una, con el turno exclusivo de la GPU y de la base:

- servicios reales del proyecto `evaluon` y su base;
- desde la copia principal, en main limpio: el contenedor `app` monta el código y `./evals` de esa copia.

```
docker compose -p evaluon exec -T app python manage.py shell < warmup.py                       # calentamiento, antes de cada corrida
docker compose -p evaluon exec -T app python manage.py correr_evals --usuario desarrollo --commit 14ef270 < <archivo con la clave>
docker compose -p evaluon exec -T app python manage.py correr_evals --usuario desarrollo --commit 14ef270 --quitando-piezas < <archivo con la clave>
```

| Corrida | Carpeta | Horario | Para qué |
|---|---|---|---|
| 1 | `2026-10-03T171739_14ef270_gemma-4-12b-it-qat-q4_0` | 17:17:39 a 17:21:21 | La que se presenta |
| 2 | `2026-10-03T172157_14ef270_gemma-4-12b-it-qat-q4_0` | 17:21:57 a 17:25:33 | Repetición, para la igualdad |
| 3 | `2026-10-03T172609_14ef270_gemma-4-12b-it-qat-q4_0` | 17:26:09 a 17:30:50 | Repetición con `--quitando-piezas` |

Consultas registradas, todas con el usuario `desarrollo`:

- 168 de las tres corridas, con canal `eval`;
- 18 de calentamiento, con canal `command`.

Las carpetas se movieron después a la rama `001-T-046`.

**Calentamiento (decisión del responsable).** `correr_evals` no tiene una opción para calentar. Antes de cada corrida se hicieron 6 consultas:

- con `services.ask`, desde `manage.py shell` en el mismo contenedor `app`;
- canal `command`, usuario `desarrollo`;
- no se cuentan en las medidas.

Las preguntas no son del conjunto ni tratan sus artículos. Su fecha es la 2025-06-30, salvo la cuarta:

1. "¿Qué es una licitación pública?"
2. "¿Qué principios generales rigen las contrataciones?"
3. "¿Quién autoriza la convocatoria de un procedimiento de selección?"
4. "¿Qué es una contratación directa?" (2015-10-01)
5. "¿Qué es el acto de apertura de las ofertas?"
6. "¿Cuál es la capital de Francia?"

| Calentamiento | 1.ª (en frío) | 2.ª | 3.ª | 4.ª | 5.ª | 6.ª (frenada por el umbral) |
|---|---|---|---|---|---|---|
| Antes de la corrida 1 | **7,65 s** | 6,91 s | 2,45 s | 8,71 s | 7,73 s | 0,47 s |
| Antes de la corrida 2 | 5,40 s | 6,36 s | 1,94 s | 7,31 s | 7,10 s | 0,51 s |
| Antes de la corrida 3 | 5,40 s | 6,13 s | 2,01 s | 7,38 s | 7,10 s | 0,40 s |

**Tiempo en frío:** 7,65 s en la primera consulta: 6,63 s de generación y 0,90 s de recuperación. No pasa de 30 s, así que no corresponde abrir la tarea de precalentar.

Límite de la medida:
- Los servicios no se reiniciaron. Su último uso fue la corrida de T-063 (16:54), unos 23 minutos antes.
- No es el arranque después de horas sin uso que dio 29,5 s en T-063: ese caso no se volvió a medir.
- Desde la primera consulta los tiempos ya son los normales: esta vez no se vio un arranque en frío de varias consultas.

**Medidas exigidas (corrida 1).** La respuesta correcta y la abstención se miden sobre el lote de aceptación; la cita literal y el tiempo, sobre toda la corrida.

| Exigencia | Resultado | Umbral | Cumple |
|---|---|---|---|
| Cita literal | 100,0 % (113 de 113; IC 95 %: 96,7 % a 100 %) | 100 % | sí |
| Respuesta correcta que cita la unidad correcta | 94,1 % (16 de 17; IC 95 %: 73,0 % a 99,0 %) | al menos 85 % | sí |
| Abstención | 100,0 % (6 de 6; IC 95 %: 61,0 % a 100 %) | al menos 90 % | sí |
| Tiempo por consulta, sin el calentamiento | mediana 4,03 s · máximo 8,22 s (EV-011) | máximo 30 s | sí |
| Memoria de video total | 10.284 MiB usados + 326 MiB reservados por el controlador (10,4 GiB) | 20 GB | sí |

- **Revisión humana:** no dio por incorrecta ninguna respuesta que el corrector aceptó. La medida corregida es igual a la automática.
- **Margen:** con 17 y 6 casos, ni este resultado permite afirmar con 95 % de confianza que la tasa real supera el 85 % y el 90 %. Las cotas inferiores son 73,0 % y 61,0 %.

**Abstención.** Las 6 preguntas sin respuesta del lote de aceptación las frenó el umbral, no el modelo:

- motivo `below_threshold`, puntajes entre 0,0011 y 0,0074;
- tres ajenas a la normativa: EV-051, EV-052 y EV-053;
- tres de tema cercano: EV-054, EV-055 y EV-056.

La regla 11 de la v3 (abstenerse solo si ninguna unidad trata el punto) sigue sin probarse con el modelo real en una pregunta sin respuesta.

**Caso fallado del lote de aceptación:** EV-044, sobre las muestras no retiradas (art. 28 del anexo de la 247/2022). Este caso no se usa para ajustar.

- Es una abstención indebida por el umbral. El art. 28 quedó 1.º en el orden del reranker, pero con 0,1169, debajo de 0,219.
- 0,1169 está también debajo de la pregunta ajena más alta del lote de ajuste (EV-025, 0,1195). Con la regla del hueco, ningún umbral la deja pasar sin dejar pasar también a EV-025.
- Es una pregunta con "palabras distintas a las de la norma": "nunca pasa a buscar" frente a "no retira las muestras".
- Salió igual en las tres corridas, con el mismo puntaje.
- No hubo contenido inventado: el sistema no afirmó nada (P3).

**Lote de ajuste (diagnóstico):**

- respuesta correcta: 85,2 % (23 de 27; IC 95 %: 67,5 % a 94,1 %);
- abstención: 100 % (6 de 6).

Fallan, con las causas de siempre:
- EV-006: omite la revisión ante la máxima autoridad.
- EV-009: faltan dos modalidades.
- EV-017: omite la pérdida de la garantía de la oferta.
- EV-024: el art. 21 del Anexo I no llega a la selección por el cupo de 3 unidades por categoría.

**Medidas por régimen.** El resumen de la corrida las da para el lote de ajuste. Las del lote de aceptación se calcularon aparte, con la misma función de Wilson.

| Régimen | Ajuste: respuesta correcta | Ajuste: abstención | Aceptación: respuesta correcta | Aceptación: abstención |
|---|---|---|---|---|
| 247/2022 | 88,2 % (15 de 17; IC 65,7 % a 96,7 %) | 100 % (3 de 3) | 90,9 % (10 de 11; IC 62,3 % a 98,4 %) | 100 % (3 de 3; IC 43,8 % a 100 %) |
| 297/03 | 80,0 % (8 de 10; IC 49,0 % a 94,3 %) | 100 % (2 de 2) | 100 % (6 de 6; IC 61,0 % a 100 %) | 100 % (3 de 3; IC 43,8 % a 100 %) |
| Sin régimen a la fecha | — | 100 % (1 de 1) | — | — |

**REQ-018 y REQ-019.** El conjunto no tiene casos de ninguno de los dos y quedan sin medir con la IA:

- ninguno con la etiqueta "dos categorías";
- ninguno con `difieren: true`;
- el resumen dice "ningún caso corrido";
- las 113 citas son del régimen específico y ninguna afirmación trae `regimes_differ`.

**Pares de REQ-020: 7 de 8 pasan.**

- **El que falla:** EV-003 y EV-017, porque EV-017 no pasa por su cuenta. Omite la pérdida de la garantía de la oferta, como en T-045, T-059 y T-063.
- **El régimen:** en los 8 pares, cada caso aplica y cita la norma de su fecha. El par de borde, EV-034 (2023-01-03) y EV-035 (2023-01-01), cita la 247/2022 y la 297/03.

**Aviso de REQ-021:** 56 de 56 según lo esperado.

**Igualdad entre corridas** (estado, motivo, citas y texto de las afirmaciones):

| Comparación | Mismo estado, motivo y citas | Mismo texto | Medidas exigidas |
|---|---|---|---|
| Corrida 2 contra la 1 | 56 de 56 | 47 de 56 | iguales |
| Corrida 3 contra la 2 | 56 de 56 | 56 de 56 | iguales |

Qué cambia entre la 1 y la 2:
- Son 9 textos distintos, todos del lote de ajuste y de las primeras 17 consultas: EV-001, 002, 003, 004, 009, 011, 013, 015 y 017.
- Cambia la redacción, no el contenido.
- El lote de aceptación salió idéntico en las tres corridas.

El caso que cambia de resultado es EV-004:
- La corrida 1 dice "No es necesario presentar la garantía…" y pasa.
- La 2 y la 3 dicen "No será necesario…" y fallan.
- El dato `["no", "no es necesario"]` no acepta "no será necesario", y la primera afirmación no empieza con "no".
- La respuesta es correcta en las tres.

Causa probable, no comprobada: la caché de prompt de `llama-server` (ver el aviso de la decisión del responsable sobre el calentamiento). La corrida 1 llegó con la caché que dejó T-063; la 2 y la 3, con la de una corrida completa de los mismos casos.

**Comparación quitando piezas** (corrida 3, lote de ajuste, sin el modelo de generación):

| Configuración | Unidad correcta entre los candidatos | Entre las enviadas al modelo | Posición (mediana · peor) | Frenadas con respuesta / sin respuesta | Tiempo de la recuperación |
|---|---|---|---|---|---|
| solo vectores | 27 de 27 | 26 de 27 | 1 · 4 | 0 de 27 / 5 de 5 | mediana 0,40 s · máx. 0,49 s |
| solo palabras | 27 de 27 | 26 de 27 | 1 · 4 | 0 de 27 / 5 de 5 | mediana 0,42 s · máx. 0,50 s |
| combinada sin reranker | 27 de 27 | 25 de 27 | 1 · 10 | no aplica | mediana 0,01 s · máx. 0,01 s |
| completa | 27 de 27 | 26 de 27 | 1 · 4 | 0 de 27 / 5 de 5 | mediana 0,58 s · máx. 0,75 s |

- **El reranker es la pieza que aporta.** Sin él, la unidad correcta cae hasta el 10.º lugar y se pierde una más al armar el pedido.
- **Los caminos de búsqueda.** Con este lote, cualquiera de los dos caminos solo, por vectores o por palabras, trae la unidad correcta en los 27 casos.
- **La referencia exacta** sigue en 0 de 27, porque ninguna pregunta nombra un artículo.

**Memoria de video.** Se muestreó con `nvidia-smi --query-gpu=timestamp,memory.used -lms 500`:

- desde el calentamiento de la corrida 1 hasta el final de la medición por vectores, de 17:16:55 a 17:31:11;
- 1.686 lecturas, todas de 10.284 MiB, sin picos;
- al final: `memory.reserved` 326 MiB y `memory.free` 13.854 MiB de 24.463.

Coincide con T-003 (10.336 MiB con los tres modelos cargados después de puntuar 65 pasajes). En modo WDDM, `nvidia-smi` no da el uso por proceso: es la lectura de la placa entera, con la pantalla en la placa integrada.

**Búsqueda exacta por vectores.** Se midió solo la consulta SQL del camino por significado: `retrieval._SEMANTIC_SQL`, con `LIMIT 30` y sin índice.

- Corpus real: 223 pasajes con embedding.
- 24 mediciones: 4 preguntas de calentamiento, para las dos fechas, con 6 repeticiones cada una.
- Resultado: mediana 1,3 ms, máximo 3,8 ms (la primera ejecución) y mínimo 1,0 ms.
- `EXPLAIN ANALYZE`: 0,46 ms de ejecución, con un ordenamiento top-N de 99 pasajes consultables a la fecha.

Está muy por debajo de 200 ms: no hace falta índice.

**Comparación con la corrida anterior** (T-063, `2026-10-03T165105_d5b96d4_…`), lote de ajuste:

| Medida | T-063 | T-046 (corrida 1) |
|---|---|---|
| Cita literal | 100 % (74 de 74) | 100 % (74 de 74) |
| Respuesta correcta | 81,5 % (22 de 27) | 85,2 % (23 de 27) |
| Abstención | 100 % (6 de 6) | 100 % (6 de 6) |
| 247/2022 / 297/03 | 82,4 % / 80,0 % | 88,2 % / 80,0 % |
| Unidad correcta enviada al modelo | 26 de 27 | 26 de 27 |
| Pares / aviso | 3 de 4 / 33 de 33 | 3 de 4 / 56 de 56 (con el lote de aceptación: 7 de 8) |
| Tiempo (toda la corrida) | mediana 4,79 s · máx. 29,52 s | mediana 4,03 s · máx. 8,22 s |

- **Contra T-063:** el comando informa "Sin bajas respecto de la corrida anterior".
- **EV-003** pasa a pasar con las mismas afirmaciones que en T-063, por la variante "término igual" que aprobó el responsable. No es una mejora del sistema.
- **El lote de aceptación** no tiene corrida anterior con la que compararse.
- **Entre repeticiones con el mismo commit** hay una baja: en la corrida 2, el lote de ajuste baja a 81,5 % por EV-004, por redacción (ver "Igualdad entre corridas"). La informa el comando de la corrida 2.

**Huellas** (`parametros.json`, iguales en las tres corridas y a las de T-063):

| Modelo | Archivo | sha256 |
|---|---|---|
| Generación, `gemma-4-12b-it-qat-q4_0`, compilación `b11347`, temperatura 0, semilla 42 | `gemma-4-12b-it-qat-q4_0.gguf` | `93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b` |
| Embeddings, `bge-m3` | `bge-m3-FP16.gguf` | `daec91ffb5dd0c27411bd71f29932917c49cf529a641d0168496c3a501e3062c` |
| Reranker, `bge-reranker-v2-m3` | `bge-reranker-v2-m3-FP16.gguf` | `5df93be121c09c43432102ad2b9569d369ccb85c209ca7583e8ccd28f0e41b88` |

**Decisiones del responsable sobre la corrida de T-046 (2026-10-03).**

1. EV-004: "no será necesario" dice lo mismo que "no es necesario"; se sumó como variante (#87). Con eso la baja entre repeticiones queda resuelta.
2. Par EV-003 / EV-017: el par cumple su objetivo (régimen y norma correctos en los dos casos). La respuesta incompleta de EV-017 (no dice que se pierde la garantía de la oferta), junto con EV-006 y EV-009, queda como mejora pendiente: es un ajuste de instrucciones, con su propia tarea y su medición.
3. REQ-019: se redactan 2 o 3 casos nuevos con visto bueno del responsable y se miden en una corrida corta (T-066). REQ-018: queda pendiente hasta que se cargue una norma de otra categoría; lo puede habilitar la Comisión con la feature 009.
4. EV-044 (lote de aceptación) falla por el umbral con otras palabras que la norma; queda registrado y no se ajusta nada con el lote de aceptación (ADR-0014).
