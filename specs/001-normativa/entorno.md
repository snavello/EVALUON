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
