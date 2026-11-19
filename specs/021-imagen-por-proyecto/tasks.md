# Tareas 021 · Una imagen por proyecto de trabajo

Plan: `specs/021-imagen-por-proyecto/spec.md`, sección «Plan corto» (aprobado el 2026-11-19 por el responsable, «Sí, corregir»)

Despliegue: pendiente

> El tablero (`docs/tablero.md`) se genera de este archivo. Al aprobarse el despliegue, la línea de arriba pasa a `Despliegue: aprobado AAAA-MM-DD`.

Estados: pendiente · en curso · en verificación · terminada · bloqueada

**Ritmo (carril liviano, ADR-0081).** Una tarea; el desarrollador corre los tests de su área; una sola verificación y una sola suite completa al cierre. La rama de tarea no toca este archivo ni el tablero.

| ID | Tarea | Requisitos | Depende de | Estado |
|---|---|---|---|---|
| T-369 | El nombre de la imagen de la aplicación sale del proyecto de Compose; el piloto conserva el suyo | REQ-174, REQ-175 | — | en curso |

### T-369 · Imagen por proyecto

- **Requisitos:** REQ-174, REQ-175.
- **Nivel:** liviana.
- **Qué hay que hacer:** en `docker-compose.yml`, el nombre de la imagen de la configuración común de la aplicación se arma con el nombre del proyecto de Compose, con `evaluon` por omisión, de modo que el piloto siga resolviendo `evaluon-app:local`. Test que lo fije. Sin cambios en `docker-compose.clon.yml` ni `docker-compose.demo.yml`.
- **Aviso de tareas anteriores:**
- **Verificación:** tests de Compose (`tests/test_compose_env.py`, `tests/test_clon_compose.py`, `tests/test_compose_razonamiento.py`); `docker compose config` con y sin `-p`.
- **No tocar:** el clon, la demo, el `Dockerfile`, la aplicación, `tasks.md`, el tablero, la spec.
