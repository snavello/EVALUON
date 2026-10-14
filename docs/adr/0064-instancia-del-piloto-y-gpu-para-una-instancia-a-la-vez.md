# ADR-0064 · Instancia del piloto en la misma notebook, con el motor de generación para una instancia a la vez

Estado: propuesto · Fecha: 2026-10-14 · Propuso: planificador (plan 007) · Decidió: —

## Contexto

REQ-117 pide que el proceso en curso, reservado hasta el dictamen, y todo lo que el sistema produce sobre él se procesen solo en el equipo del sistema, con IA local, **en una instancia separada de la que usa la construcción**. Nada de eso se copia al repositorio, a las pruebas, a las mediciones ni a los respaldos de construcción. Los agentes no acceden a esa instancia ni a sus respaldos, salvo la lectura que permite el ADR-0060 mientras dura la estabilización. El criterio de aceptación agrega que, terminada la estabilización, ninguna tarea de construcción (tests, mediciones, respaldos, verificaciones) usa la instancia, su base ni sus respaldos.

Condiciones del equipo:

- **Una notebook** con Windows 11, Docker Desktop y una GPU de 24.463 MiB.
- **Memoria de la GPU.** El 27B con embeddings y reranker usa 20.956 MiB (entorno de la 015, T-244d). T-049 midió 20.940 MiB con el 27B de una instancia y embeddings y reranker de las dos. Dos 27B no entran.
- **El 27B tarda de 3 a 10 minutos en cargar.** Detenerlo lleva unos 20 s y puede avisar «did not receive an exit event» (T-049). `nvidia-smi` puede marcar 0 MiB con el modelo cargado (T-049): no sirve como prueba de GPU libre.
- **El compose dice `name: evaluon`.** Si en otra carpeta falta `COMPOSE_PROJECT_NAME`, cualquier orden de Compose actúa sobre 8000; un `down -v` borraría su base (T-049). La precedencia del nombre es: `-p`, después `COMPOSE_PROJECT_NAME`, después `name:` [1].
- **La imagen se llama `evaluon-app:local` en todas las copias:** construir en una cambia la de la otra (T-049).
- **Los agentes** corren con el mismo usuario de Windows, que tiene acceso a Docker.
- **El repositorio es público.** La carpeta de construcción está en `Documentos`, que en Windows suele sincronizarse con la nube.
- **La configuración de uso** es la del ADR-0057: el 27B en `generation_batch`, con la Consulta en el mismo motor.

## Alternativas

### A. Motores propios; el 27B para una instancia a la vez; embeddings y reranker en las dos

Cada instancia tiene sus motores. Embeddings y reranker quedan siempre encendidos en las dos (entran, según T-049). El motor de generación (`generation_batch`, el 27B) y el `worker` solo corren en una instancia a la vez.

Mientras el piloto lo tiene, la construcción usa un archivo de compose que pone su `generation_batch` y su `worker` en un perfil que no arranca: ni `up` ni `run --rm app pytest` encienden un segundo 27B. Para medir, el responsable pasa el motor con un script que:

- detiene el de una instancia y enciende el de la otra;
- comprueba el de destino por `/health` y `/props`, no por `nvidia-smi`.

- **Se gana:**
  - REQ-117 al pie de la letra: ningún componente que procese el material reservado lo usa la construcción.
  - Las mediciones no se mezclan con el uso del piloto.
  - La construcción no puede cambiar el modelo del piloto por medir otro.
  - El aviso de la Consulta («el sistema está evaluando») sigue viendo la cola correcta.
- **Se pierde:**
  - La construcción mide solo cuando el piloto le presta el motor.
  - Cada cambio tarda de 3 a 10 minutos.
  - Mientras tanto el piloto no evalúa ni arma matrices.
  - Terminada la estabilización, el cambio lo hace el responsable.

### B. Un solo motor compartido

Un `generation_batch` en un proyecto aparte, o del piloto, al que llegan las dos instancias por una red de Docker compartida.

- **Se gana:** no hay que alternar; las dos instancias tienen IA siempre.
- **Se pierde:**
  - El material reservado lo procesa un componente que también usa la construcción: choca con «instancia separada» y con «ninguna usa esa instancia».
  - El motor atiende de a un pedido (`--parallel 1`): una medición de una hora frena al piloto, y al revés.
  - Medir otro modelo cambia el del piloto.
  - El aviso de la Consulta de cada instancia solo ve su propia cola.
  - La caché de pedidos del motor guarda texto del piloto en un servicio que los agentes de construcción manejan.

Necesitaría que el responsable lea REQ-117 como «separada salvo la IA».

### C. Otro equipo para el piloto

- **Se gana:** separación total, también de los agentes, y nada que alternar.
- **Se pierde:** un segundo equipo con GPU, que hoy no existe, y la decisión de correr «en el equipo del sistema».

## Decisión

Se propone **A**, con estas medidas de separación:

| | Construcción | Piloto |
|---|---|---|
| Carpeta | la de siempre | `C:\EVALUON-piloto\evaluon\`, un clon en el commit desplegado, fuera del perfil de usuario y de toda carpeta sincronizada |
| Proyecto | `evaluon` | `evaluon-piloto`, por tres vías: `COMPOSE_PROJECT_NAME` en su `.env`, `name:` en `docker-compose.piloto.yml`, y `scripts/piloto/compose.ps1`, que comprueba las dos y llama a Docker con `-p evaluon-piloto`. El runbook del piloto no usa `docker compose` directo |
| Imagen | `evaluon-app:local` | `evaluon-app:piloto` |
| Base y volúmenes | `evaluon_*` | `evaluon-piloto_*` |
| Puerto | `127.0.0.1:8000` | `127.0.0.1:8100`, solo para el intermediario (ADR-0061) |
| Secretos | propios | otros `POSTGRES_PASSWORD` y `DJANGO_SECRET_KEY` |
| Respaldos | `backups/` | `C:\EVALUON-piloto\respaldos\`, con un script que rechaza destinos dentro de una copia de Git o del perfil |
| Modelos | `models/` | copia propia, verificada con las huellas de `scripts/models.sha256` (con fin de línea LF) |
| Repositorio | publica por pull request | el clon no tiene dirección de envío |

**Agentes.** Durante la estabilización pueden leer la instancia del piloto (ADR-0060), sin llevar nada al repositorio ni a las pruebas.

Al terminar, el responsable aplica el procedimiento de cierre que deja T-276:

- reglas de denegación en la configuración de permisos de Claude Code del equipo (leer la carpeta del piloto, Docker sobre su proyecto);
- cambio de la clave de la base y de la clave secreta del piloto;
- aviso al Coordinador para que no dé encargos sobre el piloto.

Es una separación **de procedimiento**: con el mismo usuario de Windows y Docker Desktop, un proceso de ese usuario puede entrar a los contenedores. La separación técnica exige que los agentes usen otro usuario de Windows sin acceso a Docker, u otro equipo. Lo decide el responsable.

## Consecuencias

Más fácil:

- Probar que la construcción no usa el piloto: otro nombre de proyecto, otra carpeta y otros volúmenes, que los tests y la revisión pueden buscar.
- Las mediciones siguen siendo de un modelo y una cola conocidos.

Más difícil:

- Hay que alternar el motor para medir.
- El responsable carga con pasos de operación: el cambio de motor, los respaldos del piloto y el cierre de la estabilización.
- Queda el riesgo de una orden de Compose escrita a mano en la carpeta del piloto sin el script. Proteger la base de 8000 contra `down -v` queda como pendiente fuera del alcance de esta feature.

Para revertir: el piloto se apaga con su script y sus volúmenes quedan. Pasar a B exige una red compartida y que el responsable acepte la lectura de REQ-117.

## Sin verificar

- La cifra de 20.940 MiB de T-049 se tomó con `nvidia-smi`, que el mismo T-049 vio fallar con el 27B cargado. T-278 comprueba en las dos direcciones que el 27B carga con embeddings y reranker de las dos instancias encendidos. Si no carga, el archivo de construcción suma embeddings y reranker a su perfil.
- Que `COMPOSE_PROJECT_NAME` tomado del `.env` pese más que el `name:` del archivo. La documentación [1] lo pone como variable de entorno, sin nombrar el `.env`; T-049 lo usó con éxito.

## Fuentes

Consultadas el 2026-10-14.

1. Docker Compose, «Specify a project name»: https://docs.docker.com/compose/how-tos/project-name/
