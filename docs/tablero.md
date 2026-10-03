# Tablero de avance

> Se genera con `python tools/tablero.py` a partir de `specs/`. No editar a mano.

Leyenda: ✓ hecho · ▶ en curso · ◐ en verificación · ○ pendiente · ✕ bloqueada

## Proyecto

```mermaid
flowchart LR
  F001["▶ 001 · Normativa consultable con cita"]:::active
  F002["○ 002 · Análisis del pliego borrador"]:::todo
  F003["○ 003 · Procedimiento, pliego final y…"]:::todo
  F004["○ 004 · Evaluación asistida de ofertas"]:::todo
  F005["○ 005 · Hojas de compliance"]:::todo
  F006["○ 006 · Salidas de la evaluación"]:::todo
  F007["○ 007 · Acceso por red"]:::todo
  F008["○ 008 · Ofertas y ficha por oferta"]:::todo
  F001 --> F002
  F003 --> F002
  F001 --> F003
  F003 --> F004
  F008 --> F004
  F005 --> F004
  F008 --> F005
  F004 --> F006
  F001 --> F007
  F003 --> F008
  classDef done fill:#1a7f37,stroke:#116329,color:#ffffff
  classDef review fill:#0969da,stroke:#0550ae,color:#ffffff
  classDef active fill:#bf8700,stroke:#7d4e00,color:#ffffff
  classDef blocked fill:#cf222e,stroke:#a40e26,color:#ffffff
  classDef todo fill:#eaeef2,stroke:#8c959f,color:#24292f
```

| Feature | Qué entrega | Etapa | Tareas | Avance |
|---|---|---|---|---|
| [001 · Normativa consultable con cita](#001) | Las normas de compras cargadas, versionadas y consultables, con cada respuesta respaldada por el artículo que la sostiene | 4 de 7 · Desarrollo | 26/55 | █████░░░░░ 47% |
| 002 · Análisis del pliego borrador | Opcional: un informe de cumplimiento de un pliego borrador contra la normativa, con preguntas a la Comisión sobre lo que no puede resolver, y su matriz de cumplimiento preliminar | No iniciada | — | — |
| 003 · Procedimiento, pliego final y matriz de cumplimiento | El procedimiento con su fecha de autorización; la carga del pliego final publicado; la matriz de cumplimiento (requisitos formales, económicos y técnicos que debe cumplir la oferta, cada uno con su cita al pliego) armada desde el pliego final y validada por la Comisión | No iniciada | — | — |
| 004 · Evaluación asistida de ofertas | Por cada oferta y cada requisito de la matriz, una propuesta de cumple, no cumple o no determinado con su fundamento (pliego, oferta, compliance, normativa o respuesta de la Comisión) y preguntas a la Comisión sobre lo que no puede resolver; la Comisión confirma, corrige o rechaza | No iniciada | — | — |
| 005 · Hojas de compliance | La carga, por la Comisión, del documento de compliance de cada oferta: lo verificado en sistemas no integrados (por ejemplo, que la póliza de garantía presentada esté vigente o que no haya deudas) | No iniciada | — | — |
| 006 · Salidas de la evaluación | Planilla por oferta y cuadro comparativo; el borrador de acta queda diferido | No iniciada | — | — |
| 007 · Acceso por red | Uso de la pantalla desde otras computadoras, con conexión cifrada y bloqueo tras intentos fallidos de clave | No iniciada | — | — |
| 008 · Ofertas y ficha por oferta | La carga de cada oferta en varios documentos (PDF con texto o escaneado) y una ficha por oferta: síntesis de lo ofrecido frente a cada requisito de la matriz, con los documentos y fragmentos que lo respaldan | No iniciada | — | — |

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

- **Próximo paso:** Desarrollar: 29 tareas sin terminar.
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
- ○ T-037 · Mostrar las citas con categoría, papel y cambios (pendiente)
- ○ T-038 · Registrar ingresos, ingresos fallidos y rechazos por rol (pendiente)
- ○ T-039 · Correr el conjunto de preguntas y medir las exigencias (pendiente)
- ○ T-040 · Unir recuperación y generación completas con su registro (pendiente)
- ○ T-041 · Mostrar y registrar la búsqueda en la pantalla (pendiente)
- ○ T-042 · Agregar calibración del umbral y comparación de corridas (pendiente)
- ○ T-043 · Cargar y validar el corpus real y ajustar las reglas (pendiente)
- ○ T-044 · Registrar relaciones, versiones y modificatorias del corpus (pendiente)
- ○ T-045 · Calibrar el umbral con el conjunto de preguntas (pendiente)
- ○ T-046 · Correr las evals y medir tiempo y memoria (pendiente)
- ○ T-047 · Probar una consulta con la red desconectada (pendiente)
- ○ T-048 · Probar el respaldo y la restauración de la base (pendiente)
- ○ T-049 · Levantar todo desde cero y dejar datos para el runbook (pendiente)
- ○ T-050 · Partir la 297/03 y el cuerpo de la 247/2022 desde la web (pendiente)
- ○ T-051 · Registrar las modificatorias sin cargar de una norma (pendiente)
- ○ T-052 · Avisar modificatorias sin cargar en respuesta y búsqueda (pendiente)

### Qué se hizo

- Etapas completas: Spec, Plan, Tareas.
- ✓ T-001 · Comprobar la GPU dentro de un contenedor (`3b7a8a7` 2026-10-02)
- ✓ T-002 · Levantar el motor de generación y medir su velocidad (`5fdf016` 2026-10-02)
- ✓ T-003 · Levantar embeddings y reranker y medir la memoria de video (`d1eaa07` 2026-10-02)
- ✓ T-004 · Fijar Postgres con sus extensiones y búsqueda en español (`1a9d113` 2026-10-02)
- ✓ T-005 · Armar el esqueleto de Django con sus librerías (`d771da6` 2026-10-02)
- ✓ T-006 · Crear usuarios con rol, ingreso y salida (`4ceae34` 2026-10-02, `f76f0a2` 2026-10-02)
- ✓ T-007 · Crear el registro de auditoría y el alta de usuarios (`960121e` 2026-10-02, `04d537d` 2026-10-02)
- ✓ T-008 · Crear las tablas de normas, lecturas, unidades y pasajes (`210e12f` 2026-10-02)
- ✓ T-009 · Crear las funciones de unidades consultables a una fecha (`9f1886e` 2026-10-02, `b9ca5d3` 2026-10-02)
- ✓ T-010 · Crear la tabla del registro detallado de consultas (`cc485fc` 2026-10-02)
- ✓ T-011 · Crear los clientes de IA, sus dobles y los parámetros (`fb2f640` 2026-10-02)
- ✓ T-012 · Leer un PDF con texto (`977f834` 2026-10-02, `ef7d903` 2026-10-02)
- ✓ T-013 · Partir en artículos y armar el informe mínimo (`a4e0391` 2026-10-03)
- ✓ T-014 · Cargar una norma, listarla y ver su informe (`e53cc24` 2026-10-03, `d115ccf` 2026-10-03)
- ✓ T-015 · Validar una lectura y calcular pasajes y vectores (`420eae6` 2026-10-03, `845bdae` 2026-10-03)
- ✓ T-016 · Armar la pantalla de consulta con sus tres bloques (`ceff61d` 2026-10-03, `bb49b8c` 2026-10-03)
- ✓ T-017 · Recuperar por significado y reordenar con el reranker (`f31dab6` 2026-10-03)
- ✓ T-018 · Generar la respuesta con esquema e insertar las citas (`33f0f08` 2026-10-03, `9830fe5` 2026-10-03)
- ✓ T-019 · Unir la consulta de punta a punta con su registro (`2685761` 2026-10-03, `71fd67b` 2026-10-03)
- ✓ T-020 · Probar el hilo mínimo con los servicios reales (`b520afe` 2026-10-03)
- ✓ T-021 · Leer un PDF escaneado con reconocimiento de texto (`223295e` 2026-10-03, `197dada` 2026-10-03)
- ✓ T-022 · Leer una página web guardada (`3d9224f` 2026-10-03, `c12d12c` 2026-10-03)
- ✓ T-036 · Entregar el documento original con sesión (`07ea00d` 2026-10-03)
- ✓ T-053 · Conservar la eñe en la búsqueda por palabras (`18a8d59` 2026-10-02, `122f9c7` 2026-10-02)
- ✓ T-054 · Pasar a la aplicación las variables de los servicios de IA (`4f4fea7` 2026-10-03)
- ✓ T-055 · Agregar el nombre de cita de la norma (`ff230c8` 2026-10-03, `88796e6` 2026-10-03)

### Mapa de tareas

```mermaid
flowchart TD
  T001["✓ T-001 · Comprobar la GPU dentro de un contenedor"]:::done
  T002["✓ T-002 · Levantar el motor de generación y medir su…"]:::done
  T003["✓ T-003 · Levantar embeddings y reranker y medir la m…"]:::done
  T004["✓ T-004 · Fijar Postgres con sus extensiones y búsque…"]:::done
  T005["✓ T-005 · Armar el esqueleto de Django con sus librer…"]:::done
  T006["✓ T-006 · Crear usuarios con rol, ingreso y salida"]:::done
  T007["✓ T-007 · Crear el registro de auditoría y el alta de…"]:::done
  T008["✓ T-008 · Crear las tablas de normas, lecturas, unida…"]:::done
  T009["✓ T-009 · Crear las funciones de unidades consultable…"]:::done
  T010["✓ T-010 · Crear la tabla del registro detallado de co…"]:::done
  T011["✓ T-011 · Crear los clientes de IA, sus dobles y los…"]:::done
  T012["✓ T-012 · Leer un PDF con texto"]:::done
  T013["✓ T-013 · Partir en artículos y armar el informe míni…"]:::done
  T014["✓ T-014 · Cargar una norma, listarla y ver su informe"]:::done
  T015["✓ T-015 · Validar una lectura y calcular pasajes y ve…"]:::done
  T016["✓ T-016 · Armar la pantalla de consulta con sus tres…"]:::done
  T017["✓ T-017 · Recuperar por significado y reordenar con e…"]:::done
  T018["✓ T-018 · Generar la respuesta con esquema e insertar…"]:::done
  T019["✓ T-019 · Unir la consulta de punta a punta con su re…"]:::done
  T020["✓ T-020 · Probar el hilo mínimo con los servicios rea…"]:::done
  T021["✓ T-021 · Leer un PDF escaneado con reconocimiento de…"]:::done
  T022["✓ T-022 · Leer una página web guardada"]:::done
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
  T036["✓ T-036 · Entregar el documento original con sesión"]:::done
  T037["○ T-037 · Mostrar las citas con categoría, papel y ca…"]:::todo
  T038["○ T-038 · Registrar ingresos, ingresos fallidos y rec…"]:::todo
  T039["○ T-039 · Correr el conjunto de preguntas y medir las…"]:::todo
  T040["○ T-040 · Unir recuperación y generación completas co…"]:::todo
  T041["○ T-041 · Mostrar y registrar la búsqueda en la panta…"]:::todo
  T042["○ T-042 · Agregar calibración del umbral y comparació…"]:::todo
  T043["○ T-043 · Cargar y validar el corpus real y ajustar l…"]:::todo
  T044["○ T-044 · Registrar relaciones, versiones y modificat…"]:::todo
  T045["○ T-045 · Calibrar el umbral con el conjunto de pregu…"]:::todo
  T046["○ T-046 · Correr las evals y medir tiempo y memoria"]:::todo
  T047["○ T-047 · Probar una consulta con la red desconectada"]:::todo
  T048["○ T-048 · Probar el respaldo y la restauración de la…"]:::todo
  T049["○ T-049 · Levantar todo desde cero y dejar datos para…"]:::todo
  T050["○ T-050 · Partir la 297/03 y el cuerpo de la 247/2022…"]:::todo
  T051["○ T-051 · Registrar las modificatorias sin cargar de…"]:::todo
  T052["○ T-052 · Avisar modificatorias sin cargar en respues…"]:::todo
  T053["✓ T-053 · Conservar la eñe en la búsqueda por palabras"]:::done
  T054["✓ T-054 · Pasar a la aplicación las variables de los…"]:::done
  T055["✓ T-055 · Agregar el nombre de cita de la norma"]:::done
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
  T055 --> T014
  T011 --> T015
  T010 --> T016
  T011 --> T017
  T017 --> T018
  T016 --> T019
  T018 --> T019
  T014 --> T020
  T015 --> T020
  T019 --> T020
  T054 --> T020
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
  T050 --> T043
  T029 --> T044
  T030 --> T044
  T043 --> T044
  T051 --> T044
  T052 --> T044
  T042 --> T045
  T044 --> T045
  T045 --> T046
  T038 --> T047
  T046 --> T047
  T047 --> T048
  T048 --> T049
  T022 --> T050
  T025 --> T050
  T029 --> T051
  T041 --> T052
  T051 --> T052
  T009 --> T053
  T011 --> T054
  T015 --> T055
  classDef done fill:#1a7f37,stroke:#116329,color:#ffffff
  classDef review fill:#0969da,stroke:#0550ae,color:#ffffff
  classDef active fill:#bf8700,stroke:#7d4e00,color:#ffffff
  classDef blocked fill:#cf222e,stroke:#a40e26,color:#ffffff
  classDef todo fill:#eaeef2,stroke:#8c959f,color:#24292f
```

### Requisitos

| Requisito | Descripción | Tareas | Estado |
|---|---|---|---|
| REQ-001 | El sistema debe incorporar una norma a partir de su documento, registrando tipo, número, organismo emisor, título, fecha de publicación, fecha de vigencia y fuente de donde se obtuvo | T-008, T-014, T-055 | ✓ cubierto |
| REQ-002 | El sistema debe conservar el documento original de cada norma y permitir verlo | T-014, T-036, T-048 | ▶ en proceso |
| REQ-003 | El sistema debe dividir cada documento en unidades citables, cada una con su ubicación: considerando, artículo, inciso o anexo en las normas, y también el texto normativo que no lleva número de artículo, como una cláusula transitoria, con el nombre que le da el documento; punto o párrafo en dictámenes y recomendaciones | T-008, T-013, T-023, T-024, T-031, T-043, T-050 | ▶ en proceso |
| REQ-004 | El sistema debe entregar, por cada norma incorporada, un informe de lectura: cuántas unidades reconoció, cuáles páginas no pudo leer y qué no pudo ubicar | T-012, T-013, T-014, T-021, T-025, T-027, T-028, T-043 | ▶ en proceso |
| REQ-005 | Una norma debe quedar disponible para consultas solo después de que una persona valide su informe de lectura | T-009, T-015, T-017, T-027, T-032, T-035, T-043 | ▶ en proceso |
| REQ-006 | El sistema debe registrar las relaciones entre normas: cuál modifica, complementa, reglamenta o deroga a cuál. Cuando el cambio alcanza a unidades concretas, la relación se registra entre esas unidades | T-029, T-035, T-041, T-044 | ○ pendiente |
| REQ-007 | El sistema debe mantener las versiones de cada norma y, para una fecha dada, indicar qué unidades estaban vigentes y qué normas las habían modificado o derogado, mostrando el texto literal de cada una | T-009, T-029, T-030, T-033, T-037, T-044 | ▶ en proceso |
| REQ-008 | El sistema debe responder consultas en lenguaje natural sobre la normativa, y cada afirmación de la respuesta debe llevar la cita de la unidad que la sostiene, con su texto literal | T-001, T-002, T-003, T-004, T-011, T-017, T-018, T-019, T-020, T-031, T-032, T-034, T-039, T-040, T-042, T-046, T-047, T-054 | ▶ en proceso |
| REQ-009 | Cuando la normativa cargada no permite responder, el resultado debe ser "no determinado", sin afirmar nada | T-002, T-003, T-011, T-017, T-018, T-019, T-034, T-039, T-040, T-042, T-045, T-046 | ▶ en proceso |
| REQ-010 | El sistema debe permitir buscar unidades por norma y número de artículo, y por palabras del texto, desde la pantalla de consulta. Una unidad derogada aparece en la búsqueda marcada como tal | T-004, T-009, T-035, T-041, T-053 | ▶ en proceso |
| REQ-011 | El sistema debe avisar cuando se intenta cargar una norma que ya está incorporada. Si es el mismo archivo, no lo incorpora; si es la misma norma en otro archivo o formato, pide confirmación expresa | T-008, T-026 | ▶ en proceso |
| REQ-012 | El sistema debe registrar cada carga, validación y consulta con lo necesario para reconstruirla: quién, cuándo, sobre qué versión de la normativa, qué se recuperó y qué se respondió | T-007, T-008, T-010, T-014, T-015, T-019, T-020, T-026, T-038, T-040, T-041, T-048, T-049, T-051, T-052, T-054 | ▶ en proceso |
| REQ-013 | El sistema debe ofrecer una pantalla de consulta donde una persona escribe su pregunta y ve la respuesta con sus citas; desde cada cita se ve el texto literal de la unidad y se puede abrir la norma original | T-005, T-016, T-019, T-020, T-037, T-047, T-055 | ▶ en proceso |
| REQ-014 | La pantalla de consulta debe distinguir a simple vista una respuesta con fundamento de un resultado "no determinado" | T-016, T-037 | ▶ en proceso |
| REQ-015 | El sistema debe incorporar normas en tres formatos: PDF con texto, PDF escaneado y página web guardada. Cuando el texto de una unidad se obtuvo por reconocimiento sobre una imagen, debe quedar indicado en la unidad y en el informe de lectura | T-012, T-021, T-022, T-025, T-028, T-037, T-043 | ▶ en proceso |
| REQ-016 | El sistema debe exigir usuario y clave para ingresar. Cada usuario tiene un rol: lectura, que permite consultar y buscar; o lectura y escritura, que además permite cargar y validar normas y registrar relaciones y versiones | T-005, T-006, T-007, T-038, T-049 | ▶ en proceso |
| REQ-017 | El sistema debe registrar la categoría de cada documento: régimen específico, otra normativa aplicable, marco nacional, dictamen legal o recomendación de auditoría | T-008, T-014 | ✓ cubierto |
| REQ-018 | Cada cita debe mostrar la categoría de su documento. En una respuesta, las citas del régimen específico van primero; las del marco nacional se presentan como marco; los dictámenes y las recomendaciones se presentan como criterio que acompaña; los considerandos se presentan como contexto, identificados como tales y después del articulado | T-033, T-034, T-037, T-040, T-046 | ○ pendiente |
| REQ-019 | Cuando el régimen específico y el marco nacional tratan el mismo punto de manera distinta, la respuesta debe mostrar ambos textos y señalar el del régimen específico como el aplicable | T-033, T-034, T-037, T-040, T-046 | ○ pendiente |
| REQ-020 | Cada consulta y cada búsqueda se hacen para una fecha de autorización del procedimiento, que la persona indica en la pantalla; por defecto es la del día. El sistema responde con lo que regía a esa fecha y muestra qué régimen aplicó | T-008, T-009, T-014, T-016, T-019, T-020, T-032, T-035, T-039, T-041, T-042, T-043, T-044, T-046, T-055 | ▶ en proceso |
| REQ-021 | El sistema debe permitir registrar que una norma tiene modificatorias todavía no cargadas, identificando cada una. Mientras queden, toda respuesta o búsqueda que muestre una unidad de esa norma avisa que puede haber cambios que el sistema no conoce e indica cuántas modificatorias faltan cargar | T-008, T-039, T-042, T-044, T-046, T-051, T-052 | ▶ en proceso |
