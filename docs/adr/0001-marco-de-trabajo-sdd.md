# ADR-0001 · Marco de trabajo: SDD con Coordinador y cinco agentes

Estado: aceptado · Fecha: 2026-10-02 · Decidió: responsable del proyecto

## Contexto

EVALUON lo construye una persona con asistencia de agentes de IA. El sistema asiste decisiones de compras públicas, por lo que cada comportamiento debe poder rastrearse hasta un requisito y, cuando corresponde, hasta una norma. Los agentes no conservan memoria entre sesiones, de modo que la continuidad del proyecto tiene que estar en documentos.

## Alternativas

### A. Desarrollo conversacional, sin especificación formal
Rápido al inicio. No deja trazabilidad, las decisiones se pierden entre conversaciones y no hay contra qué auditar.

### B. SDD con un único agente que hace todo
Mantiene la spec como fuente de verdad. El mismo agente que escribe el código lo verifica y lo audita, así que tiende a confirmar su propio trabajo.

### C. SDD con Coordinador y agentes especializados
Un Coordinador Consultor atiende consultas y coordina a Planificador, Desarrollador, Testeador evaluador, Implementador y Auditor. Cada agente tiene un entregable, límites y herramientas acotadas. Cuesta más coordinación y más consumo por feature.

## Decisión

Se adopta la alternativa C, con dos ajustes para que no frene un piloto corto:

- El ciclo por tarea usa solo Planificador, Desarrollador y Testeador evaluador.
- Auditor e Implementador intervienen una vez por feature, en sus compuertas.

El Coordinador se define en `CLAUDE.md`, los agentes en `.claude/agents/` y los principios en `specs/constitution.md`. El responsable aprueba spec, plan y despliegue.

## Consecuencias

- Toda feature empieza por una spec; no hay código sin requisito.
- El Auditor trabaja con acceso de solo lectura y sin recibir el resumen del trabajo previo, para que su dictamen sea independiente.
- El avance se sigue en `docs/tablero.md`, generado desde las specs y las tareas, sin registros paralelos.
- El marco vive en el repositorio y se versiona igual que el código: cambiarlo es un commit revisable.
- Si la coordinación resulta pesada, se puede volver a la alternativa B fusionando roles sin perder specs, ADR ni tests.
