# EVALUON

Sistema con IA local para consolidar normativa de compras, revisar pliegos de bases y condiciones y asistir a la Comisión Evaluadora en la evaluación de ofertas.

El proyecto se construye con Spec Driven Development (SDD): cada cambio nace de una especificación aprobada y se puede rastrear hasta ella.

## Cómo se trabaja

Se usa Claude Code en la raíz del repositorio. Al abrirlo, Claude actúa como **Coordinador Consultor** (definido en `CLAUDE.md`) y trabaja en dos modos:

- **Consulta:** preguntas de arquitectura, infraestructura o funcionales. Las decisiones quedan como ADR.
- **Construcción:** se le delega una tarea y coordina a los agentes.

| Agente | Función | Entrega |
|---|---|---|
| `planificador` | Diseño técnico y tareas a partir de la spec | `plan.md`, `tasks.md`, ADR |
| `desarrollador` | Implementa una tarea por vez | Código y tests unitarios |
| `testeador-evaluador` | Verifica contra la spec y mide la IA | Informe de pruebas y evals |
| `auditor` | Revisión independiente, solo lectura | Dictamen |
| `implementador` | Docker, migraciones y runbook | Entorno funcionando |

Flujo: spec → plan → tareas → desarrollo y verificación → auditoría → despliegue. El responsable aprueba la spec, el plan y el despliegue.

El Coordinador puede lanzar varios agentes a la vez, incluso del mismo tipo, cuando las partes son independientes y se mantiene la coherencia.

## Cómo va el proyecto

**[Tablero de avance](docs/tablero.md):** qué se hizo y qué falta, con diagramas. Se genera desde las specs y las tareas con `python tools/tablero.py`; no se edita a mano.

## Estructura

```
CLAUDE.md                 Coordinador Consultor
.claude/agents/           Definición de los cinco agentes
specs/constitution.md     Principios no negociables
specs/hoja-de-ruta.md     Features del proyecto y su orden
specs/_plantillas/        Plantillas de spec, plan y tareas
specs/NNN-nombre/         Una carpeta por feature
docs/adr/                 Decisiones de arquitectura
docs/tablero.md           Tablero de avance (generado)
docs/auditorias/          Dictámenes del auditor
docs/runbook.md           Instalación y operación (lo crea el implementador)
tools/tablero.py          Generador del tablero
evals/                    Conjunto dorado para medir la IA
corpus/                   Documentos públicos de trabajo
```

## Para empezar

1. Clonar el repositorio y abrir Claude Code en la carpeta.
2. Mirar el [tablero](docs/tablero.md) para ver en qué etapa está cada feature.
3. Pedirle al Coordinador el próximo paso que indica el tablero.

## Decisiones abiertas

Se resuelven como ADR cuando el primer plan las requiera:

- Motor de IA local y modelo de generación.
- Modelo de embeddings y reranker.
- Estrategia para partir normativa y pliegos en fragmentos citables.
- Framework de la aplicación web.
- Extracción de texto de documentos escaneados.

## Entorno de desarrollo

Equipo con Windows y WSL2, Git, Python 3.12, Docker Desktop y Postgres 17 con pgvector en contenedor (base `evaluon`). Falta instalar el motor de IA local, que depende de la primera decisión abierta.

## Datos

En la fase de construcción solo se usa material público. No subir documentos reservados a este repositorio. Ver principio P4 de la constitución.
