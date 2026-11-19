# Dictamen de auditoría de fallas · Feature 021 (una imagen por proyecto de trabajo)

- **Alcance:** `specs/021-imagen-por-proyecto/`, rango eb3c9e6b..bcfc554f (`origin/main`), 4 commits (uno de código, 26038390; dos de gestión; el merge del PR #508), 5 archivos (código: `docker-compose.yml`, una línea de `image:` y seis de comentario; `tests/test_compose_imagen.py`, nuevo, 14 casos). Auditoría de fallas según ADR-0036 y ADR-0052, carril liviano (ADR-0081). Lectura sobre la copia `.claude/worktrees/t369`; para construir y correr la suite se usó una exportación de `origin/main` (`git archive`) en una carpeta temporal y un proyecto docker propio, `evaluon-aud021`, dado de baja con `down -v` y con su imagen borrada. Sobre el proyecto `evaluon` (piloto) solo se corrió `config`, `ps`, `ls` e `inspect`.
- **Resultado:** aprobado

## Hallazgos

Sin hallazgos bloqueantes. Nada impide funcionar ni expone datos.

1. **Menor, no bloqueante · P5 (operación).** `tools/cerrar.sh` l. 40-46 corre la suite con el proyecto `evaluon-t$N-cierre` y termina con `down -v`, que no borra imágenes. Desde este cambio cada cierre construye su propia imagen `evaluon-tN-cierre-app:local` y la deja en el equipo. No afecta al piloto ni al resultado; ocupa disco con el tiempo. Borrar imágenes viejas está fuera de alcance en la spec, así que queda como aviso: convendría agregar `--rmi local` a ese `down` o una limpieza periódica.
2. **Menor, no bloqueante · REQ-174 (límite del arreglo).** Un `docker compose build` desde una copia de trabajo sin `-p` y sin `COMPOSE_PROJECT_NAME` sigue resolviendo `evaluon-app:local` (comprobado: `docker compose -f docker-compose.yml config --images` sin `-p` da `evaluon-app:local`, porque el archivo declara `name: evaluon`) y pisaría la imagen del piloto. Está dentro de la letra de REQ-174 («con un proyecto distinto del piloto»), pero la protección depende de que toda copia use su `-p`. No hay test ni control que lo impida.

## Para la auditoría de cumplimiento (no bloquea)

- No se revisó trazabilidad completa ni redacción. A la vista: el único commit de código nombra T-369 y REQ-174/175; el test nombra ambos requisitos; T-369 figura terminada y tiene `verificacion/T-369.md`; `Despliegue: pendiente` en `tasks.md`.
- La feature no tiene `plan.md` propio (el plan corto está en la spec, carril liviano) ni runbook; la spec dice que no requiere despliegue.
- La resolución real de `${COMPOSE_PROJECT_NAME:-evaluon}` no queda automatizada: el test la interpola con una expresión propia (`_resolve`), no con Compose. El propio registro de verificación lo avisa.

## Lo que se controló y está bien

- **Criterios 1 y 2 (REQ-174), con Compose real (v5.5.1), `config --images` sobre `origin/main`:** sin `-p` y con `-p evaluon`, los cuatro servicios de la aplicación (`app`, `migrate`, `worker`, `portal_worker`) resuelven `evaluon-app:local`; con `-p evaluon-aud021`, `evaluon-aud021-app:local`; con `COMPOSE_PROJECT_NAME=evaluon-x` sin `-p`, `evaluon-x-app:local`; con la variable vacía, `evaluon-app:local`. El `.env` de la raíz no define `COMPOSE_PROJECT_NAME`.
- **Criterio 3:** con una copia temporal de `docker-compose.yml` con `image: evaluon-app:local` montada sobre `/app/docker-compose.yml`, `tests/test_compose_imagen.py` da 7 fallan, 7 pasan; sin la alteración, los 14 pasan. El test detecta la regresión.
- **Criterio 4:** huella de `evaluon-app:local` antes de construir: `sha256:4f5db476…6d9b45`. Después de `docker compose -p evaluon-aud021 build app` (que creó `evaluon-aud021-app:local`), después de la suite y después de la baja: la misma, e igual a la del contenedor `evaluon-app-1`, que siguió corriendo sin reinicio.
- **Criterio 5 (REQ-175):** `docker-compose.clon.yml` (l. 35-36) y `docker-compose.demo.yml` (l. 19-20) conservan `image: evaluon-app:local` literal con `pull_policy: never`, sin `build`, y no están en el diff. `scripts/clon.sh` l. 139 sigue exigiendo esa imagen. `test_compose_imagen.py`, `test_compose_env.py`, `test_clon_compose.py` y `test_compose_razonamiento.py`, en contenedor suelto con los archivos del clon y la demo montados: 95 pasaron, 0 fallaron, 0 salteados.
- **Suite completa (P7), corrida por el auditor** sobre `origin/main` bcfc554f, proyecto `evaluon-aud021`, base propia: 8.612 pasaron, 31 salteados, 0 fallaron, 717 s. El registro del cierre dice 8.614 y 29: el total coincide (8.643) y la diferencia de dos está en saltos por archivos que la exportación no trae o Compose no monta, no en fallas.
- **Tests de la feature:** sin `skip` ni `xfail` incondicionales; el único salto es condicional (clon y demo no montados) y cada caso afirma algo concreto.
- **Efecto en el resto del entorno:** los demás archivos de superposición no definen `image`, `build` ni `name`; el piloto corre con tres de ellos y sigue en `evaluon-app:local`. `tools/cerrar.sh` usa `-p` propio y `build: .` sigue en `x-app`, así que un proyecto nuevo construye su imagen al primer `run`.
- **P4:** el diff no agrega URLs, claves, clientes de API ni datos; el test lee solo configuración. Ningún servicio cambia de red.
- **Entorno que se levanta:** construcción, base, migraciones y suite arrancaron desde cero en el proyecto propio sin intervención.
- **Tablero:** `python tools/tablero.py --check` responde que `docs/tablero.md` está al día.

## Lo que no se pudo verificar

- Evals contra la IA local: no se corrieron; el cambio no toca aplicación, instrucciones ni modelos.
- `docker compose config` de la demo y del clon con Compose real: piden variables de archivos de entorno que están fuera del repositorio. El nombre de imagen en ambos es literal y lo cubre el test.
- Los dos tests de `test_clon_compose.py` que necesitan `cerrar.sh` montado y los que piden `corpus/casos/` y `docs/`: salteados en la corrida completa por el montaje.
- Que los proyectos ya levantados desde copias anteriores (`evaluon-t236`, `evaluon-t248`, `evaluon-ver256`) dejen de usar el nombre viejo: depende de que tomen main.
- Historial completo de git en busca de secretos: se revisó solo el diff del rango.
