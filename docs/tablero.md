# Tablero de avance

> Se genera con `python tools/tablero.py` a partir de `specs/`. No editar a mano.

Leyenda: ✓ hecho · ▶ en curso · ◐ en verificación · ○ pendiente · ✕ bloqueada

## Proyecto

```mermaid
flowchart LR
  F001["▶ 001 · Normativa consultable con cita"]:::active
  F002["○ 002 · Revisión de pliegos"]:::todo
  F003["○ 003 · Matriz de requisitos"]:::todo
  F004["○ 004 · Evaluación de ofertas"]:::todo
  F005["○ 005 · Hojas de compliance"]:::todo
  F006["○ 006 · Salidas de la evaluación"]:::todo
  F001 --> F002
  F002 --> F003
  F003 --> F004
  F003 --> F005
  F004 --> F006
  F005 --> F006
  classDef done fill:#1a7f37,stroke:#116329,color:#ffffff
  classDef review fill:#0969da,stroke:#0550ae,color:#ffffff
  classDef active fill:#bf8700,stroke:#7d4e00,color:#ffffff
  classDef blocked fill:#cf222e,stroke:#a40e26,color:#ffffff
  classDef todo fill:#eaeef2,stroke:#8c959f,color:#24292f
```

| Feature | Qué entrega | Etapa | Tareas | Avance |
|---|---|---|---|---|
| [001 · Normativa consultable con cita](#001) | Las normas de compras cargadas, versionadas y consultables, con cada respuesta respaldada por el artículo que la sostiene | 1 de 7 · Spec | — | — |
| 002 · Revisión de pliegos | Observaciones a un pliego contra la normativa, antes de publicarlo | No iniciada | — | — |
| 003 · Matriz de requisitos | Los requisitos del pliego ordenados en una matriz que la Comisión valida | No iniciada | — | — |
| 004 · Evaluación de ofertas | Por cada requisito, una propuesta con su cita; la Comisión confirma, corrige o rechaza | No iniciada | — | — |
| 005 · Hojas de compliance | Carga de las validaciones hechas en sistemas no integrados, por oferta | No iniciada | — | — |
| 006 · Salidas de la evaluación | Planilla por oferta, cuadro comparativo y borrador de acta | No iniciada | — | — |

<a id="001"></a>

## 001 · Normativa consultable con cita

**Etapa actual:** 1 de 7 · Spec (spec en borrador, 7 dudas abiertas) · [carpeta](../specs/001-normativa)

```mermaid
flowchart LR
  E0["▶ 1. Spec"]:::active --> E1["○ 2. Plan"]:::todo --> E2["○ 3. Tareas"]:::todo --> E3["○ 4. Desarrollo"]:::todo --> E4["○ 5. Verificación"]:::todo --> E5["○ 6. Auditoría"]:::todo --> E6["○ 7. Despliegue"]:::todo
  classDef done fill:#1a7f37,stroke:#116329,color:#ffffff
  classDef review fill:#0969da,stroke:#0550ae,color:#ffffff
  classDef active fill:#bf8700,stroke:#7d4e00,color:#ffffff
  classDef blocked fill:#cf222e,stroke:#a40e26,color:#ffffff
  classDef todo fill:#eaeef2,stroke:#8c959f,color:#24292f
```

### Qué falta

- **Próximo paso:** Resolver 7 dudas marcadas en la spec y aprobar la spec (compuerta del responsable).

### Qué se hizo

- Nada terminado todavía.

### Requisitos

| Requisito | Descripción | Tareas | Estado |
|---|---|---|---|
| REQ-001 | El sistema debe incorporar una norma a partir de su documento, registrando tipo, número, organismo emisor, título, fecha de publicación, fecha de vigencia y fuente de donde se obtuvo | — | — |
| REQ-002 | El sistema debe conservar el documento original de cada norma y permitir verlo | — | — |
| REQ-003 | El sistema debe dividir cada norma en unidades citables (artículo, inciso, anexo), cada una con su ubicación dentro de la norma | — | — |
| REQ-004 | El sistema debe entregar, por cada norma incorporada, un informe de lectura: cuántas unidades reconoció, cuáles páginas no pudo leer y qué no pudo ubicar | — | — |
| REQ-005 | Una norma debe quedar disponible para consultas solo después de que una persona valide su informe de lectura | — | — |
| REQ-006 | El sistema debe registrar las relaciones entre normas: cuál modifica, complementa, reglamenta o deroga a cuál | — | — |
| REQ-007 | El sistema debe mantener las versiones de cada norma y poder indicar qué texto estaba vigente en una fecha dada | — | — |
| REQ-008 | El sistema debe responder consultas en lenguaje natural sobre la normativa, y cada afirmación de la respuesta debe llevar la cita de la unidad que la sostiene, con su texto literal | — | — |
| REQ-009 | Cuando la normativa cargada no permite responder, el resultado debe ser "no determinado", sin afirmar nada | — | — |
| REQ-010 | El sistema debe permitir buscar unidades por norma y número de artículo, y por palabras del texto | — | — |
| REQ-011 | El sistema debe avisar cuando se intenta cargar una norma que ya está incorporada | — | — |
| REQ-012 | El sistema debe registrar cada carga, validación y consulta con lo necesario para reconstruirla: quién, cuándo, sobre qué versión de la normativa, qué se recuperó y qué se respondió | — | — |
