# Plan NNN · Nombre de la feature

Estado: borrador | aprobado · Fecha: AAAA-MM-DD · Aprobó: —

Spec: `specs/NNN-nombre/spec.md`

## Resumen del enfoque

Un párrafo: cómo se resuelve y por qué así.

## Componentes

Qué partes del sistema intervienen, cuáles son nuevas y cómo se comunican.

## Modelo de datos

Tablas nuevas o modificadas, con sus campos. Migraciones necesarias.

## Flujo de IA

Solo si la feature usa IA.

- **Ingesta:** cómo se parte el documento y qué metadatos lleva cada fragmento.
- **Recuperación:** qué se busca, con qué filtros y cuántos candidatos.
- **Reordenamiento:** cómo se eligen los fragmentos finales.
- **Generación:** qué se le pide al modelo y con qué formato de salida.
- **Cita:** cómo se vincula cada afirmación con su fragmento.
- **Abstención:** en qué condiciones el resultado es "no determinado".

## Registro de auditoría

Qué se guarda en cada operación para cumplir el principio P6.

## Cobertura de requisitos

| Requisito | Cómo se resuelve | Cómo se verifica |
|---|---|---|
| REQ-NNN | Sección o componente del plan | Test o eval |

## Verificación contra la constitución

| Principio | Cumple | Nota |
|---|---|---|
| P4 Datos | sí / no | |
| P5 Local y reproducible | sí / no | |
| P6 Auditoría | sí / no | |
| P10 Simplicidad | sí / no | |

Un "no" requiere justificación y aprobación explícita.

## Decisiones

ADR nuevos que este plan propone, con su número.

## Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
