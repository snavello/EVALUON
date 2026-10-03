# ADR-0013 · Asesor de metodología

Estado: aceptado · Fecha: 2026-10-03 · Decidió: responsable del proyecto

## Contexto

El proyecto avanza con un equipo de agentes que coordina el Coordinador. La forma de trabajo se fue ajustando sobre la marcha (por ejemplo, ADR-0011 y ADR-0012). Esos ajustes salieron de problemas que vio el responsable, no de una revisión sistemática. A medida que el proyecto crece, un error en la forma de trabajo o un paso ineficiente se multiplica en cada tarea.

## Decisión

Se suma el agente `asesor-metodologia`, definido en `.claude/agents/asesor-metodologia.md`. Es experto en desarrollo con IA y en equipos de agentes.

- **Qué evalúa:** la forma de trabajo, no el producto.
- **Cuándo recomienda:** solo en dos casos:
  - A: corregir un error grave en la forma de trabajo;
  - B: una mejora muy significativa en tiempo, costo o calidad.
- **A quién reporta:** al Coordinador.
- **Qué puede hacer:** tiene permisos amplios de lectura y medición (repositorio, historia de git, pull requests, búsqueda en la web).
- **Qué no puede hacer:** cambiar archivos, ni lanzar agentes, ni correr tests, evals o servicios.
- **Cómo se aprueba una recomendación:** primero la evalúa el Coordinador. Si la acepta, la lleva al responsable, y solo con la aprobación de los dos se aplica. Lo que afecte la constitución, un plan aprobado o una spec lo decide siempre el responsable.
- **Cuándo se lo convoca:**
  - al cerrar cada etapa del flujo de una feature;
  - cuando algo se repite o se demora;
  - cuando lo pide el responsable.

## Consecuencias

- Una mirada experta y periódica sobre el proceso, separada de quien lo ejecuta.
- Cada consulta cuesta tiempo de un agente y del Coordinador. Por eso solo recomienda con umbrales altos: un informe sin recomendaciones es un resultado válido.
- Para revertirla, se borra la definición del agente y se quita su mención en `CLAUDE.md`.
