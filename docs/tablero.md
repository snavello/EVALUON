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
  F007["○ 007 · Acceso por red"]:::todo
  F001 --> F002
  F002 --> F003
  F003 --> F004
  F003 --> F005
  F004 --> F006
  F005 --> F006
  F001 --> F007
  classDef done fill:#1a7f37,stroke:#116329,color:#ffffff
  classDef review fill:#0969da,stroke:#0550ae,color:#ffffff
  classDef active fill:#bf8700,stroke:#7d4e00,color:#ffffff
  classDef blocked fill:#cf222e,stroke:#a40e26,color:#ffffff
  classDef todo fill:#eaeef2,stroke:#8c959f,color:#24292f
```

| Feature | Qué entrega | Etapa | Tareas | Avance |
|---|---|---|---|---|
| [001 · Normativa consultable con cita](#001) | Las normas de compras cargadas, versionadas y consultables, con cada respuesta respaldada por el artículo que la sostiene | 4 de 7 · Desarrollo | 0/49 | ░░░░░░░░░░ 0% |
| 002 · Revisión de pliegos | Observaciones a un pliego contra la normativa, antes de publicarlo | No iniciada | — | — |
| 003 · Matriz de requisitos | Los requisitos del pliego ordenados en una matriz que la Comisión valida | No iniciada | — | — |
| 004 · Evaluación de ofertas | Por cada requisito, una propuesta con su cita; la Comisión confirma, corrige o rechaza | No iniciada | — | — |
| 005 · Hojas de compliance | Carga de las validaciones hechas en sistemas no integrados, por oferta | No iniciada | — | — |
| 006 · Salidas de la evaluación | Planilla por oferta, cuadro comparativo y borrador de acta | No iniciada | — | — |
| 007 · Acceso por red | Uso de la pantalla desde otras computadoras, con conexión cifrada y bloqueo tras intentos fallidos de clave | No iniciada | — | — |

<a id="001"></a>

## 001 · Normativa consultable con cita

**Etapa actual:** 4 de 7 · Desarrollo · [carpeta](../specs/001-normativa)

```mermaid
flowchart LR
  E0["✓ 1. Spec"]:::done --> E1["✓ 2. Plan"]:::done --> E2["✓ 3. Tareas"]:::done --> E3["▶ 4. Desarrollo"]:::active --> E4["○ 5. Verificación"]:::todo --> E5["○ 6. Auditoría"]:::todo --> E6["○ 7. Despliegue"]:::todo
  classDef done fill:#1a7f37,stroke:#116329,color:#ffffff
  classDef review fill:#0969da,stroke:#0550ae,color:#ffffff
  classDef active fill:#bf8700,stroke:#7d4e00,color:#ffffff
  classDef blocked fill:#cf222e,stroke:#a40e26,color:#ffffff
  classDef todo fill:#eaeef2,stroke:#8c959f,color:#24292f
```

### Qué falta

- **Próximo paso:** Desarrollar: 49 tareas sin terminar.
- ○ T-001 · Comprobar la GPU dentro de un contenedor (pendiente)
- ○ T-002 · Levantar el motor de generación y medir su velocidad (pendiente)
- ○ T-003 · Levantar embeddings y reranker y medir la memoria de video (pendiente)
- ○ T-004 · Fijar Postgres con sus extensiones y búsqueda en español (pendiente)
- ○ T-005 · Armar el esqueleto de Django con sus librerías (pendiente)
- ○ T-006 · Crear usuarios con rol, ingreso y salida (pendiente)
- ○ T-007 · Crear el registro de auditoría y el alta de usuarios (pendiente)
- ○ T-008 · Crear las tablas de normas, lecturas, unidades y pasajes (pendiente)
- ○ T-009 · Crear las funciones de unidades consultables a una fecha (pendiente)
- ○ T-010 · Crear la tabla del registro detallado de consultas (pendiente)
- ○ T-011 · Crear los clientes de IA, sus dobles y los parámetros (pendiente)
- ○ T-012 · Leer un PDF con texto (pendiente)
- ○ T-013 · Partir en artículos y armar el informe mínimo (pendiente)
- ○ T-014 · Cargar una norma, listarla y ver su informe (pendiente)
- ○ T-015 · Validar una lectura y calcular pasajes y vectores (pendiente)
- ○ T-016 · Armar la pantalla de consulta con sus tres bloques (pendiente)
- ○ T-017 · Recuperar por significado y reordenar con el reranker (pendiente)
- ○ T-018 · Generar la respuesta con esquema e insertar las citas (pendiente)
- ○ T-019 · Unir la consulta de punta a punta con su registro (pendiente)
- ○ T-020 · Probar el hilo mínimo con los servicios reales (pendiente)
- ○ T-021 · Leer un PDF escaneado con reconocimiento de texto (pendiente)
- ○ T-022 · Leer una página web guardada (pendiente)
- ○ T-023 · Partir normas completas con incisos, anexos y considerandos (pendiente)
- ○ T-024 · Partir dictámenes y recomendaciones en puntos y párrafos (pendiente)
- ○ T-025 · Completar el informe de lectura (pendiente)
- ○ T-026 · Avisar duplicados al cargar una norma (pendiente)
- ○ T-027 · Releer un documento y reemplazar la lectura anterior (pendiente)
- ○ T-028 · Integrar los tres formatos en la carga (pendiente)
- ○ T-029 · Registrar relaciones entre normas y mostrar los vínculos (pendiente)
- ○ T-030 · Registrar versiones de una norma (pendiente)
- ○ T-031 · Partir en pasajes las unidades largas (pendiente)
- ○ T-032 · Recuperar por tres caminos y unir los candidatos (pendiente)
- ○ T-033 · Seleccionar por categoría, sumar cambios y ordenar (pendiente)
- ○ T-034 · Completar instrucciones, marca de regímenes y orden (pendiente)
- ○ T-035 · Buscar unidades por artículo y por palabras (pendiente)
- ○ T-036 · Entregar el documento original con sesión (pendiente)
- ○ T-037 · Mostrar las citas con categoría, papel y cambios (pendiente)
- ○ T-038 · Registrar ingresos, ingresos fallidos y rechazos por rol (pendiente)
- ○ T-039 · Correr el conjunto de preguntas y medir las exigencias (pendiente)
- ○ T-040 · Unir recuperación y generación completas con su registro (pendiente)
- ○ T-041 · Mostrar y registrar la búsqueda en la pantalla (pendiente)
- ○ T-042 · Agregar calibración del umbral y comparación de corridas (pendiente)
- ○ T-043 · Cargar y validar el corpus real y ajustar las reglas (pendiente)
- ○ T-044 · Registrar las relaciones y versiones del corpus (pendiente)
- ○ T-045 · Calibrar el umbral con el conjunto de preguntas (pendiente)
- ○ T-046 · Correr las evals y medir tiempo y memoria (pendiente)
- ○ T-047 · Probar una consulta con la red desconectada (pendiente)
- ○ T-048 · Probar el respaldo y la restauración de la base (pendiente)
- ○ T-049 · Levantar todo desde cero y dejar datos para el runbook (pendiente)

### Qué se hizo

- Etapas completas: Spec, Plan, Tareas.

### Mapa de tareas

```mermaid
flowchart TD
  T001["○ T-001 · Comprobar la GPU dentro de un contenedor"]:::todo
  T002["○ T-002 · Levantar el motor de generación y medir su…"]:::todo
  T003["○ T-003 · Levantar embeddings y reranker y medir la m…"]:::todo
  T004["○ T-004 · Fijar Postgres con sus extensiones y búsque…"]:::todo
  T005["○ T-005 · Armar el esqueleto de Django con sus librer…"]:::todo
  T006["○ T-006 · Crear usuarios con rol, ingreso y salida"]:::todo
  T007["○ T-007 · Crear el registro de auditoría y el alta de…"]:::todo
  T008["○ T-008 · Crear las tablas de normas, lecturas, unida…"]:::todo
  T009["○ T-009 · Crear las funciones de unidades consultable…"]:::todo
  T010["○ T-010 · Crear la tabla del registro detallado de co…"]:::todo
  T011["○ T-011 · Crear los clientes de IA, sus dobles y los…"]:::todo
  T012["○ T-012 · Leer un PDF con texto"]:::todo
  T013["○ T-013 · Partir en artículos y armar el informe míni…"]:::todo
  T014["○ T-014 · Cargar una norma, listarla y ver su informe"]:::todo
  T015["○ T-015 · Validar una lectura y calcular pasajes y ve…"]:::todo
  T016["○ T-016 · Armar la pantalla de consulta con sus tres…"]:::todo
  T017["○ T-017 · Recuperar por significado y reordenar con e…"]:::todo
  T018["○ T-018 · Generar la respuesta con esquema e insertar…"]:::todo
  T019["○ T-019 · Unir la consulta de punta a punta con su re…"]:::todo
  T020["○ T-020 · Probar el hilo mínimo con los servicios rea…"]:::todo
  T021["○ T-021 · Leer un PDF escaneado con reconocimiento de…"]:::todo
  T022["○ T-022 · Leer una página web guardada"]:::todo
  T023["○ T-023 · Partir normas completas con incisos, anexos…"]:::todo
  T024["○ T-024 · Partir dictámenes y recomendaciones en punt…"]:::todo
  T025["○ T-025 · Completar el informe de lectura"]:::todo
  T026["○ T-026 · Avisar duplicados al cargar una norma"]:::todo
  T027["○ T-027 · Releer un documento y reemplazar la lectura…"]:::todo
  T028["○ T-028 · Integrar los tres formatos en la carga"]:::todo
  T029["○ T-029 · Registrar relaciones entre normas y mostrar…"]:::todo
  T030["○ T-030 · Registrar versiones de una norma"]:::todo
  T031["○ T-031 · Partir en pasajes las unidades largas"]:::todo
  T032["○ T-032 · Recuperar por tres caminos y unir los candi…"]:::todo
  T033["○ T-033 · Seleccionar por categoría, sumar cambios y…"]:::todo
  T034["○ T-034 · Completar instrucciones, marca de regímenes…"]:::todo
  T035["○ T-035 · Buscar unidades por artículo y por palabras"]:::todo
  T036["○ T-036 · Entregar el documento original con sesión"]:::todo
  T037["○ T-037 · Mostrar las citas con categoría, papel y ca…"]:::todo
  T038["○ T-038 · Registrar ingresos, ingresos fallidos y rec…"]:::todo
  T039["○ T-039 · Correr el conjunto de preguntas y medir las…"]:::todo
  T040["○ T-040 · Unir recuperación y generación completas co…"]:::todo
  T041["○ T-041 · Mostrar y registrar la búsqueda en la panta…"]:::todo
  T042["○ T-042 · Agregar calibración del umbral y comparació…"]:::todo
  T043["○ T-043 · Cargar y validar el corpus real y ajustar l…"]:::todo
  T044["○ T-044 · Registrar las relaciones y versiones del co…"]:::todo
  T045["○ T-045 · Calibrar el umbral con el conjunto de pregu…"]:::todo
  T046["○ T-046 · Correr las evals y medir tiempo y memoria"]:::todo
  T047["○ T-047 · Probar una consulta con la red desconectada"]:::todo
  T048["○ T-048 · Probar el respaldo y la restauración de la…"]:::todo
  T049["○ T-049 · Levantar todo desde cero y dejar datos para…"]:::todo
  T001 --> T002
  T002 --> T003
  T003 --> T004
  T004 --> T005
  T005 --> T006
  T006 --> T007
  T007 --> T008
  T008 --> T009
  T009 --> T010
  T010 --> T011
  T008 --> T012
  T012 --> T013
  T013 --> T014
  T011 --> T015
  T010 --> T016
  T011 --> T017
  T017 --> T018
  T016 --> T019
  T018 --> T019
  T014 --> T020
  T015 --> T020
  T019 --> T020
  T012 --> T021
  T012 --> T022
  T013 --> T023
  T023 --> T024
  T024 --> T025
  T014 --> T026
  T025 --> T026
  T015 --> T027
  T026 --> T027
  T021 --> T028
  T022 --> T028
  T027 --> T028
  T009 --> T029
  T014 --> T029
  T015 --> T030
  T015 --> T031
  T019 --> T032
  T032 --> T033
  T019 --> T034
  T010 --> T035
  T008 --> T036
  T019 --> T037
  T036 --> T037
  T014 --> T038
  T015 --> T038
  T019 --> T039
  T033 --> T040
  T034 --> T040
  T035 --> T041
  T037 --> T041
  T040 --> T041
  T039 --> T042
  T040 --> T042
  T020 --> T043
  T028 --> T043
  T031 --> T043
  T041 --> T043
  T029 --> T044
  T030 --> T044
  T043 --> T044
  T042 --> T045
  T044 --> T045
  T045 --> T046
  T038 --> T047
  T046 --> T047
  T047 --> T048
  T048 --> T049
  classDef done fill:#1a7f37,stroke:#116329,color:#ffffff
  classDef review fill:#0969da,stroke:#0550ae,color:#ffffff
  classDef active fill:#bf8700,stroke:#7d4e00,color:#ffffff
  classDef blocked fill:#cf222e,stroke:#a40e26,color:#ffffff
  classDef todo fill:#eaeef2,stroke:#8c959f,color:#24292f
```

### Requisitos

| Requisito | Descripción | Tareas | Estado |
|---|---|---|---|
| REQ-001 | El sistema debe incorporar una norma a partir de su documento, registrando tipo, número, organismo emisor, título, fecha de publicación, fecha de vigencia y fuente de donde se obtuvo | T-008, T-014 | ○ pendiente |
| REQ-002 | El sistema debe conservar el documento original de cada norma y permitir verlo | T-014, T-036, T-048 | ○ pendiente |
| REQ-003 | El sistema debe dividir cada documento en unidades citables, cada una con su ubicación: considerando, artículo, inciso o anexo en las normas; punto o párrafo en dictámenes y recomendaciones | T-008, T-013, T-023, T-024, T-031, T-043 | ○ pendiente |
| REQ-004 | El sistema debe entregar, por cada norma incorporada, un informe de lectura: cuántas unidades reconoció, cuáles páginas no pudo leer y qué no pudo ubicar | T-012, T-013, T-014, T-021, T-025, T-027, T-028, T-043 | ○ pendiente |
| REQ-005 | Una norma debe quedar disponible para consultas solo después de que una persona valide su informe de lectura | T-009, T-015, T-017, T-027, T-032, T-035, T-043 | ○ pendiente |
| REQ-006 | El sistema debe registrar las relaciones entre normas: cuál modifica, complementa, reglamenta o deroga a cuál. Cuando el cambio alcanza a unidades concretas, la relación se registra entre esas unidades | T-029, T-035, T-041, T-044 | ○ pendiente |
| REQ-007 | El sistema debe mantener las versiones de cada norma y, para una fecha dada, indicar qué unidades estaban vigentes y qué normas las habían modificado o derogado, mostrando el texto literal de cada una | T-009, T-029, T-030, T-033, T-037, T-044 | ○ pendiente |
| REQ-008 | El sistema debe responder consultas en lenguaje natural sobre la normativa, y cada afirmación de la respuesta debe llevar la cita de la unidad que la sostiene, con su texto literal | T-001, T-002, T-003, T-004, T-011, T-017, T-018, T-019, T-020, T-031, T-032, T-034, T-039, T-040, T-042, T-046, T-047 | ○ pendiente |
| REQ-009 | Cuando la normativa cargada no permite responder, el resultado debe ser "no determinado", sin afirmar nada | T-002, T-003, T-011, T-017, T-018, T-019, T-034, T-039, T-040, T-042, T-045, T-046 | ○ pendiente |
| REQ-010 | El sistema debe permitir buscar unidades por norma y número de artículo, y por palabras del texto, desde la pantalla de consulta. Una unidad derogada aparece en la búsqueda marcada como tal | T-004, T-009, T-035, T-041 | ○ pendiente |
| REQ-011 | El sistema debe avisar cuando se intenta cargar una norma que ya está incorporada. Si es el mismo archivo, no lo incorpora; si es la misma norma en otro archivo o formato, pide confirmación expresa | T-008, T-026 | ○ pendiente |
| REQ-012 | El sistema debe registrar cada carga, validación y consulta con lo necesario para reconstruirla: quién, cuándo, sobre qué versión de la normativa, qué se recuperó y qué se respondió | T-007, T-008, T-010, T-014, T-015, T-019, T-020, T-026, T-038, T-040, T-041, T-048, T-049 | ○ pendiente |
| REQ-013 | El sistema debe ofrecer una pantalla de consulta donde una persona escribe su pregunta y ve la respuesta con sus citas; desde cada cita se ve el texto literal de la unidad y se puede abrir la norma original | T-005, T-016, T-019, T-020, T-037, T-047 | ○ pendiente |
| REQ-014 | La pantalla de consulta debe distinguir a simple vista una respuesta con fundamento de un resultado "no determinado" | T-016, T-037 | ○ pendiente |
| REQ-015 | El sistema debe incorporar normas en tres formatos: PDF con texto, PDF escaneado y página web guardada. Cuando el texto de una unidad se obtuvo por reconocimiento sobre una imagen, debe quedar indicado en la unidad y en el informe de lectura | T-012, T-021, T-022, T-025, T-028, T-037, T-043 | ○ pendiente |
| REQ-016 | El sistema debe exigir usuario y clave para ingresar. Cada usuario tiene un rol: lectura, que permite consultar y buscar; o lectura y escritura, que además permite cargar y validar normas y registrar relaciones y versiones | T-005, T-006, T-007, T-038, T-049 | ○ pendiente |
| REQ-017 | El sistema debe registrar la categoría de cada documento: régimen específico, otra normativa aplicable, marco nacional, dictamen legal o recomendación de auditoría | T-008, T-014 | ○ pendiente |
| REQ-018 | Cada cita debe mostrar la categoría de su documento. En una respuesta, las citas del régimen específico van primero; las del marco nacional se presentan como marco; los dictámenes y las recomendaciones se presentan como criterio que acompaña; los considerandos se presentan como contexto, identificados como tales y después del articulado | T-033, T-034, T-037, T-040, T-046 | ○ pendiente |
| REQ-019 | Cuando el régimen específico y el marco nacional tratan el mismo punto de manera distinta, la respuesta debe mostrar ambos textos y señalar el del régimen específico como el aplicable | T-033, T-034, T-037, T-040, T-046 | ○ pendiente |
