# ADR-0064 · Instancia del piloto en la misma notebook, con el motor de generación para una instancia a la vez

Estado: propuesto (versión 2) · Fecha: 2026-10-14 · Propuso: planificador (plan 007) · Decidió: —

## Contexto

REQ-117 pide que el proceso en curso y todo lo que el sistema produce sobre él se procese solo en el equipo, con IA local, en una instancia separada de la de construcción. Nada de eso va al repositorio, a las pruebas, a las mediciones ni a los respaldos de construcción. Los agentes no acceden a esa instancia, salvo la lectura que permite el ADR-0060 durante la estabilización.

Condiciones (T-049, integrada en `main`):

- **La GPU.** Una notebook con una GPU de 24.463 MiB. Dos 27B no entran. Con el 27B de una instancia y embeddings y reranker de las dos se midieron 20.940 MiB. El dato es de `nvidia-smi`, que T-049 vio marcar 0 MiB con el 27B cargado.
- **El 27B** tarda de 3 a 10 minutos en cargar. `docker stop` devuelve un error («did not receive an exit event») y el contenedor termina unos 40 s después de la orden, con código 137. Un pedido en curso queda fallido.
- **El nombre del proyecto.** El compose dice `name: evaluon`. Si una copia no tiene `COMPOSE_PROJECT_NAME`, cualquier orden de Compose en ella actúa sobre 8000, y `down -v` borraría su base. La precedencia es `-p`, `COMPOSE_PROJECT_NAME` y `name:` [1]. Las órdenes de la sección T-043 traen `-p evaluon` (O-049-8).
- **La imagen.** Se llama `evaluon-app:local` en todas las copias. Los estáticos (CSS y JS) y las dependencias salen de la imagen; el código se monta.
- **Docker Desktop** corre en la sesión del usuario y en este equipo no arranca solo.
- **Los agentes** corren con el mismo usuario de Windows, que maneja Docker.
- **El repositorio es público.**
- **8000 es la instancia en uso** (construcción y revisión de entregas) y hoy tiene el 27B.

## Alternativas

### A. Motores propios; el 27B para una instancia a la vez; embeddings y reranker en las dos

Cada instancia tiene sus motores. Embeddings y reranker quedan encendidos en las dos. El 27B (`generation_batch`) y el `worker` corren solo en la instancia que tiene el motor. La otra lleva `docker-compose.sin-gpu.yml` en su `COMPOSE_FILE`, que los pone en un perfil que no arranca. La protección es simétrica: ningún `up` ni `run` enciende un segundo 27B, de ningún lado.

`scripts/piloto/gpu.ps1` mueve el motor:

- se niega con pedidos en curso;
- tolera el error de `docker stop` y espera `exited`;
- cambia `COMPOSE_FILE` de los dos `.env` (sin BOM, con comprobación y vuelta atrás) y de otros archivos de entorno que se le indiquen (el del Coordinador);
- enciende el destino con `up -d`, espera `/health` y el alias;
- deja en `motor-gpu.txt` quién tiene el motor.

Los encargos que usan el motor empiezan leyendo ese archivo.

Hay tres variantes de qué pasa con 8000:

- **A1. 8000 sigue como instancia de construcción permanente**, con pantallas y búsqueda, sin evaluaciones, matrices ni Consulta mientras no tenga el motor; los pedidos quedan en espera.
  - **Se gana:** una pantalla de construcción siempre disponible.
  - **Se pierde:** 8000 sin IA casi todo el tiempo, y dos instancias permanentes que cuidar.
- **A2. El piloto es la única instancia permanente.** 8000 se detiene con sus datos guardados, y la construcción mide en instancias temporales con proyecto propio, que se arman y se bajan en cada medición, como hicieron T-268 y T-049.
  - **Se gana:** una sola instancia que cuidar, y nada que proteger en 8000.
  - **Se pierde:** no hay una pantalla de construcción siempre disponible para revisar entregas, y cada medición tarda unos minutos más en armarse.
- **Quién mueve el motor**, en las dos variantes: durante la estabilización, el Coordinador, avisando al responsable; después, solo el responsable.
  - **Se pierde:** cada medición posterior espera al responsable.

En general, con A:

- **Se gana:**
  - REQ-117 al pie de la letra;
  - mediciones sin mezclarse con el uso del piloto;
  - la construcción no cambia el modelo del piloto;
  - el aviso de la Consulta ve la cola correcta.
- **Se pierde:** de 3 a 10 minutos de carga, más unos 40 s, en cada cambio; el piloto sin evaluar mientras presta el motor.

### B. Un solo motor compartido

- **Se gana:** nada que alternar.
- **Se pierde:**
  - el material reservado lo procesa un componente que la construcción también usa;
  - con `--parallel 1`, una medición frena al piloto, y al revés;
  - medir otro modelo cambia el del piloto;
  - el aviso de la Consulta de cada instancia solo ve su propia cola;
  - la caché del motor guarda texto del piloto en un servicio que manejan los agentes.

### C. Otro equipo para el piloto

- **Se gana:** separación total.
- **Se pierde:** un segundo equipo con GPU, que no existe.

## Decisión

Se propone **A con A1**: 8000 sigue como instancia de construcción. Durante la estabilización el motor lo mueve el Coordinador avisando; después, el responsable. A2 queda como alternativa para el responsable (punto 3 del plan). Medidas de separación:

| | Construcción | Piloto |
|---|---|---|
| Carpeta | la de siempre | `C:\EVALUON-piloto\evaluon\`, un clon en el commit desplegado, con la herencia de permisos cortada, fuera del perfil de usuario y de carpetas sincronizadas |
| Proyecto | `evaluon` | `evaluon-piloto`, por tres vías: `COMPOSE_PROJECT_NAME`, `name:` en `docker-compose.piloto.yml` y `scripts/piloto/compose.ps1` |
| Imagen | `evaluon-app:local` | `evaluon-app:piloto`, reconstruida en cada actualización (los estáticos salen de ella) |
| Base y volúmenes | `evaluon_*` | `evaluon-piloto_*` |
| Puerto | `127.0.0.1:8000` | `127.0.0.1:8100`, solo para el intermediario (ADR-0061) |
| Secretos | propios | propios |
| Respaldos | `backups/` | `C:\EVALUON-piloto\respaldos\`, diarios, con retención y copia fuera del equipo |
| Modelos | `models/` | enlaces duros o copia, verificados con `tr -d '\r' < ../scripts/models.sha256 \| sha256sum -c --ignore-missing -`; `scripts/models.sha256` con fin de línea LF por `.gitattributes`, porque con CRLF falla `sha256sum -c` y el `awk` de WSL |
| Repositorio | publica por pull request | el clon no tiene dirección de envío |

`compose.ps1` siempre llama con `--project-directory`, `--env-file` y `-p evaluon-piloto` fijos. Se niega si el `.env` no es del piloto. Rechaza `-p`, `-f`, `--env-file`, `--project-directory`, `down -v`, `rm -v` y `volume rm`. Vaciar la base se hace con `vaciar-base.ps1`, que exige un respaldo reciente y una confirmación escrita.

**Despliegue (P11).** La instancia del piloto es el destino del despliegue de la 007. El proceso reservado se carga solo después de la aceptación, del dictamen de auditoría sin hallazgos bloqueantes y de la aprobación del despliegue. Cada actualización posterior, con `actualizar.ps1`, también la aprueba el responsable.

**Agentes.** Durante la estabilización pueden leer el piloto, sin llevar nada al repositorio ni a las pruebas. Al terminarla, el responsable aplica la lista de cierre:

- reglas de denegación en Claude Code: carpeta, Docker sobre el proyecto y pedidos a la dirección del piloto y a `127.0.0.1:8100`;
- `ALTER ROLE` de la base, porque cambiar el `.env` solo no alcanza;
- una `DJANGO_SECRET_KEY` nueva;
- `clave_inicial` para los usuarios cuya clave pasó por un agente.

T-285 lo verifica con un agente que intenta y es rechazado. Es una separación de procedimiento: con el mismo usuario de Windows y Docker Desktop, un proceso de ese usuario puede entrar a los contenedores. La técnica exige otro usuario de Windows sin Docker para los agentes, u otro equipo (decisión del responsable).

## Consecuencias

Más fácil:

- Probar que la construcción no usa el piloto.
- Mediciones de un modelo y una cola conocidos.
- Ninguna orden de rutina puede encender dos 27B ni borrar la base del piloto.

Más difícil:

- Alternar el motor para medir.
- Los pasos de operación del responsable después de la estabilización.
- Queda el riesgo de una orden de Compose escrita a mano en la carpeta del piloto, sin el script: proteger el volumen de 8000 queda como pendiente fuera de alcance.

Para revertir: el piloto se detiene con sus scripts y sus volúmenes quedan. Pasar a B exige una red compartida y que el responsable acepte la lectura de REQ-117.

## Sin verificar

- Que el 27B cargue con embeddings y reranker de las dos instancias encendidos, en las dos direcciones. T-278 lo comprueba con `/health`, `utilization.gpu` y el registro del motor. Si no carga, el archivo sin GPU suma esos dos servicios al perfil.
- Que `COMPOSE_PROJECT_NAME` del `.env` pese más que `name:`: T-049 lo usó con éxito.
- Que la versión de Compose del equipo (5.5.1, según T-049) acepte `!override` y `!reset`, que usa T-284.

## Fuentes

Consultadas el 2026-10-14.

1. Docker Compose, «Specify a project name»: https://docs.docker.com/compose/how-tos/project-name/
2. `specs/001-normativa/entorno.md`, «Datos para el runbook (T-049)» y «Pendientes del despliegue» (en `main`, b6dec485)
