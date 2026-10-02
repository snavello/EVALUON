# Evals · conjunto dorado

Casos públicos ya resueltos contra los que se mide cada versión del sistema (principio P7).

## Qué es un caso

Un caso tiene una pregunta o una tarea de evaluación, los documentos sobre los que se hace, la respuesta esperada y la cita que la sostiene. También hay casos sin respuesta posible, donde lo correcto es "no determinado".

El formato vigente de cada feature lo fija su plan (para la 001, `specs/001-normativa/plan.md`, sección "Evals"). Como punto de partida, un archivo por caso en `evals/casos/`:

```yaml
id: EV-001
tipo: normativa | pliego | oferta
documentos: [ruta en corpus/]
pregunta: "..."
esperado: "..."            # o "no determinado"
cita: {documento: "...", ubicacion: "artículo o página"}
origen: "de dónde sale la respuesta esperada"
```

## Reglas

- Solo material público.
- La respuesta esperada la valida una persona que conoce la materia, no un modelo.
- Los casos existentes no se modifican ni se eliminan sin aprobación del responsable. Se pueden agregar.
- Cada corrida guarda sus resultados en `evals/corridas/` con fecha, commit y modelo, para poder comparar.

## Métricas

Recuperación, respuesta, cita y abstención, medidas por separado. Los umbrales de aceptación se fijan en la spec de cada feature.
