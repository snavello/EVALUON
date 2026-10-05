# Plan 008 · Ofertas y ficha por oferta

Estado: borrador · Fecha: 2026-10-05 · Aprobó: —

Spec: `specs/008-ofertas-ficha/spec.md` (aprobada el 2026-10-05)

ADR de este plan, todos **propuestos**:

- `docs/adr/0026-ofertas-modulo-propio-y-cola-compartida.md`: las ofertas viven en un módulo `evaluon/offers/` con tablas propias; la cola de pedidos de la 003 se comparte.
- `docs/adr/0027-fragmentos-por-recuperacion-y-eleccion-del-modelo.md`: los fragmentos se encuentran por recuperación en pasajes y el modelo elige entre candidatos; el texto es siempre el del pasaje.
- `docs/adr/0028-lectura-de-escaneos-de-ofertas.md`: OCR existente, con preparación de imagen solo para las páginas dudosas.

ADR en los que se apoya: 0002 (motor), 0003 (recuperación), 0004 (lectura y cita literal), 0007 (palabras), 0009 (respuestas de la Comisión), 0012, 0018 (cola), 0024 y 0025 (ritmo de trabajo).

## Resumen del enfoque

Un módulo nuevo `evaluon/offers/` con el mismo esquema de capas que `tenders/` (funciones de negocio que comprueban el rol y dejan el registro; pantalla y comandos solo traducen). Reutiliza sin cambios la lectura de PDF y el OCR de `evaluon/norms/reading/`, el texto canónico de `evaluon/norms/splitting/canonical.py`, los clientes de `evaluon/ai/` (embeddings, reranker, generación), la cola, el `worker` y el aviso de fin de la 003, la matriz validada (`tenders.services.validation.latest_validated`) y la infraestructura de medición de la 003 (`evaluation.py`: lista esperada en YAML fuera del repositorio con huella y visto bueno, carpeta de corrida, resumen público, intervalos de Wilson).

Una oferta se lee en segundo plano: cada documento pasa por la lectura de la 001, se parte en pasajes por página y cada pasaje recibe su vector. La ficha se arma contra la última matriz validada: para cada requisito se buscan candidatos en la oferta (embeddings y palabras), el reranker los ordena, y un pedido al modelo elige cuáles responden y escribe una síntesis sin juicio. El fragmento mostrado es el texto del pasaje, copiado de la base. Todo corre en el equipo, sin servicios externos (P4).

El trabajo empieza por un **corte vertical** (ADR-0025): T-130 entrega, con un caso chico inventado, carga, lectura (un documento con texto y uno escaneado), ficha, pantalla mínima y medición. Recién después se amplía (T-131 y T-132, en paralelo) y se mide con las tres ofertas del caso-00.

## Componentes

| Componente | Nuevo | Qué hace | Con quién habla |
|---|---|---|---|
| `app` | Cambia | Suma las páginas de ofertas y fichas y los comandos `cargar_oferta` y `medir_fichas` | `db`; `embeddings`, `reranker` |
| `worker` | Cambia | Atiende dos tipos de pedido nuevos: `read_offer_document` y `build_sheet` | `db`; `generation_batch`, `embeddings`, `reranker` |
| `generation_batch`, `embeddings`, `reranker`, `db`, `migrate` | No | Sin cambios de configuración ni de `docker-compose.yml` | — |

La lectura de escaneos (Tesseract) corre en CPU dentro de `worker`, como en la 001. Ningún servicio nuevo, ninguna dependencia de internet.

## Estructura del código

```
evaluon/offers/
├── models.py  migrations/          tablas de este plan (ADR-0026)
├── passages.py                     partir una lectura en pasajes por página
├── retrieval.py                    candidatos (embeddings y palabras) y reranker
├── services/
│   ├── offers.py                   registrar oferentes, cargar documentos, original, lectura (REQ-037, REQ-038)
│   ├── sheets.py                   pedir y armar la ficha, pedido al modelo (REQ-039 a REQ-041, REQ-043, REQ-044)
│   └── review.py                   confirmar, corregir, quitar, agregar, historial (REQ-042)
├── prompts/                        instrucciones versionadas (ficha-v1.md, ficha-renglon-v1.md)
├── evaluation.py                   medición contra la lista esperada de fichas
├── views/  urls.py                 un archivo de vistas por tema; urls_documents.py y urls_sheet.py separados
└── management/commands/            cargar_oferta, medir_fichas
evaluon/templates/offers/           ofertas, oferta, ficha, historial
tests/offers/                       pruebas, conftest.py propio, textos inventados y el caso chico
```

`evaluon/tenders/` cambia en tres lugares: una migración de `tenders_job` (dos tipos de pedido y `target_id`), `jobs.py` (dos manejadores) y la lista de tipos de hecho de `evaluon/audit/`. Todo en T-130.

## Modelo de datos

Nombres en inglés; valores de dominio en español sin tildes, como en la 003. Todo el esquema lo crea T-130, en una sola migración de `offers`, para que ninguna otra tarea necesite tocarlo (ADR-0026).

**`offers_offer`**: una oferta. `procedure` (FK a `tenders_procedure`), `number` (correlativo dentro del procedimiento), `bidder` (nombre del oferente, texto que escribe la persona; único dentro del procedimiento), `created_at`, `created_by`. Los datos personales del oferente solo existen en la base; no van al repositorio ni a los registros públicos (P4).

**`offers_document`**: un archivo de la oferta. `offer`, `kind` (`propuesta_economica`, `declaracion_jurada`, `garantia`, `constancia`, `tecnica`, `otro`; lo elige quien carga), `title`, `file_name`, `file_format` (`pdf`, `jpg`, `png`), `file_size`, `file_sha256` (única dentro de la oferta: el mismo archivo dos veces se rechaza con aviso), `loaded_at`, `loaded_by`.

**`offers_document_file`**: el original byte por byte, en tabla aparte, como en la 003.

**`offers_reading`**: una lectura de un documento. `document`, `sequence`, `pages` (la lectura de la 001, JSON), `canonical_text`, `canonical_sha256`, `tool_versions`, `report` (páginas por estado y origen, lista de páginas no leídas y de baja confianza, con documento, número y confianza), `created_at`, `job`. No se modifica.

**`offers_passage`**: un pasaje. `reading`, `order`, `key` (`p{página}/b{n}`, única en la lectura), `page`, `char_start`, `char_end`, `text` (igual a `canonical_text[char_start:char_end]`), `text_origin`, `ocr_confidence_min`, `ocr_confidence_avg`, `embedding` (vector de 1.024 dimensiones, bge-m3) y `tsv` (palabras, con la normalización de la 001). No se modifica. Búsqueda exacta dentro de una oferta, sin índice aproximado: una oferta tiene a lo sumo unos cientos de pasajes.

**`offers_sheet`**: una ficha. `offer`, `matrix_version` (FK a `tenders_matrix_version`, validada), `number` (correlativo por oferta), `channel` (`screen` o `eval`), `readings` (cada lectura usada con su huella), `models` (motor, embeddings y reranker, con huella y compilación), `parameters`, `prompt_versions`, `counts`, `timings`, `anomalies`, `technical_documents` (si la oferta trae documentación técnica y de qué documentos, REQ-044), `built_at`, `requested_by`, `job`. Armar de nuevo crea una ficha nueva; la anterior queda visible. Una ficha solo se arma contra una matriz validada (REQ-043).

**`offers_sheet_entry`**: una fila por requisito de la matriz no quitado. `sheet`, `requirement` (FK a `tenders_requirement`), `outcome` (`encontrado` o `no_encontrado`), `synthesis` (puede estar vacía), `quoted` (solo en filas técnicas por renglón: `cotizado`, `no_cotizado` o vacío), `unread_pages_warning` (hay páginas sin leer en la oferta), `state` (`propuesto` o `confirmado`).

**`offers_fragment`**: un fragmento de una fila. `entry`, `order`, `passage`, `char_start`, `char_end`, `text` (igual al recorte del texto canónico), `origin` (`sistema` o `persona`), `state` (`propuesto`, `confirmado` o `quitado`), `proposed` (copia de lo propuesto por el sistema, que no cambia).

**`offers_sheet_step`**: un pedido al modelo (P6). `sheet`, `entry`, `candidates` (pasajes, puntaje de cada fuente y del reranker), `request`, `raw_output`, `parsed`, `anomalies`, `retry_of`, `timings`. Solo se insertan filas.

**`offers_change`**: historial de la ficha (REQ-042). `entry`, `fragment`, `action` (`confirmar`, `corregir`, `quitar`, `restituir`, `agregar`), `before`, `after`, `user`, `at`, `event`. Solo se insertan filas.

**Inmutabilidad.** Triggers de la base rechazan UPDATE y DELETE sobre lecturas, pasajes, pedidos al modelo e historial, como en la 003 (`tenders/migrations/0002_triggers.py`).

**Cambios fuera del módulo** (T-130):

- `tenders_job.kind` suma `read_offer_document` y `build_sheet`; campo `target_id` (entero, nulo) con el id del documento de oferta o de la oferta. La restricción "leer un documento exige documento" no cambia.
- `audit_event.event_type` suma `offer_register`, `offer_load`, `offer_read`, `sheet_request`, `sheet_build`, `sheet_change` (caben en 20 caracteres). La migración cambia la restricción de valores válidos.

**Parámetros** (`settings.py`, copiados en cada ficha): largo máximo de un pasaje (1.200 caracteres), candidatos por embeddings (20) y por palabras (20), candidatos al modelo (8), máximo de salida por pedido, versiones de instrucciones, espera máxima de un pedido.

## Roles

Los de la 003, sin cambios:

| Operación | Operador | Evaluador |
|---|---|---|
| Registrar una oferta, cargar documentos, pedir la ficha, ver ficha y original | sí | sí |
| Corregir, quitar, restituir, agregar fragmentos | sí | sí |
| Confirmar fragmentos y filas | no | sí |

Un usuario sin rol de la Comisión no ve estas páginas; el rechazo se registra como `rejected`.

## Carga y lectura (REQ-037, REQ-038)

1. Se registra la oferta (oferente) y se cargan sus documentos, cada uno con su tipo. Se guarda el original y la huella; el mismo archivo dos veces en la oferta se rechaza. Se encola `read_offer_document`. Hecho `offer_load`.
2. El `worker` lee con `evaluon.norms.reading.read_document` (PDF con texto o escaneado, página por página; ADR-0028), arma el texto canónico, parte cada página en pasajes y calcula sus vectores con `evaluon.ai.embeddings`. Hecho `offer_read`.
3. Cada página queda con texto o en la lista de **páginas no leídas** (ilegibles, no leídas) o de **baja confianza** (dudosas), con documento, número y confianza (REQ-038). La pantalla de la oferta muestra esa lista y el estado de cada documento.
4. Fotos JPG o PNG (T-131): se guardan tal cual y se convierten a un PDF de una página, en el equipo, para leerlas.

**Pasajes** (`passages.py`). Sobre las líneas del texto canónico de cada página: se agrupan en bloques separados por línea en blanco o por un salto vertical mayor a 1,5 veces el interlineado típico de la página; un bloque de menos de 200 caracteres se une al siguiente de su página; un bloque de más de 1.200 caracteres se parte en límite de oración. Un pasaje nunca cruza una página, así su página es la suya. Una página ilegible no genera pasajes.

## Flujo de IA: armar la ficha (REQ-039 a REQ-044)

**Pedido.** `sheet_request` (hecho) encola `build_sheet` para una oferta. Se rechaza si no hay matriz validada, si la oferta no tiene ningún documento leído o si algún documento sigue en lectura. La matriz es `latest_validated(procedure)`.

**Por cada requisito no quitado de la matriz (formales, económicos y técnicos):**

- **Consulta.** El texto literal de la cita del requisito (con su ruta, para las filas técnicas: "Renglón k" y el texto de su encabezado).
- **Recuperación.** Los 20 pasajes más cercanos por embeddings y los 20 mejores por palabras, solo de la oferta, unidos (ADR-0007, ADR-0003).
- **Reordenamiento.** El reranker ordena los candidatos; pasan los 8 mejores.
- **Generación.** Un pedido a `generation_batch` (temperatura 0, semilla fija, salida con esquema JSON, como la 003). Recibe las instrucciones (`prompts/ficha-v1.md`: qué es "responde a un requisito", síntesis breve y neutra, "ninguno" es una respuesta válida), el requisito y los candidatos con alias `P1…P8` (documento, página, texto). Devuelve `{pasajes: [alias], sintesis}`.
- **Cita.** El sistema valida las alias y arma cada fragmento con el texto del pasaje elegido, copiado de la base (100 % literal por construcción). El modelo no escribe texto citado.
- **Síntesis sin juicio (REQ-041).** Se controla con una lista de palabras de juicio ("cumple", "no cumple", "incumple", "satisface", "adecuado", "conforme" y sus formas). Si falla, un reintento con el aviso; si vuelve a fallar, la fila queda sin síntesis y la anomalía en el registro.
- **Abstención (REQ-040).** Sin alias válida: `no_encontrado`, con el texto "no se encontró en la oferta", sin síntesis. Si la oferta tiene páginas sin leer, la fila lo avisa; el sistema no supone que la respuesta estaba ahí.

**Filas técnicas por renglón (REQ-044).** El pedido pide además `cotizado` (sí o no) para el renglón: sí si algún candidato elegido ofrece ese renglón con precio o cantidad. Un renglón con fragmento elegido figura "cotizado" con su cita; sin fragmento, "no cotizado" (con el aviso de páginas sin leer si las hay). Si el pliego no tiene renglones, no hay estado de cotización. La ficha indica además `technical_documents`: sí, si la oferta tiene un documento de tipo `tecnica` o alguna fila técnica tiene fragmentos. No se compara el contenido técnico con las especificaciones (feature 010).

**Versión de la matriz (REQ-043).** La ficha guarda la versión con que se armó. En la pantalla, si la matriz tiene una versión validada posterior, la ficha lo avisa ("Armada con la versión 1; la versión vigente es la 2") y ofrece armar una nueva.

**Revisión (REQ-042).** Confirmar (evaluador), corregir, quitar, restituir y agregar fragmentos. Agregar o corregir se hace eligiendo un pasaje de la oferta y, opcionalmente, un recorte literal dentro de él, comprobado contra el texto canónico. Cada cambio deja una fila en `offers_change` y el hecho `sheet_change`; el fragmento anterior queda visible en el historial.

## Pantalla

Páginas armadas en el servidor, sin htmx (ADR-0005), con la hoja de estilos de la 003.

- **Ofertas** de un procedimiento: lista de oferentes con estado de lectura y de ficha; registrar una oferta.
- **Oferta**: documentos con tipo, estado, enlace al original y botón de carga (varios a la vez); páginas no leídas y de baja confianza; "Armar ficha".
- **Ficha**: encabezado con la oferta, la versión de la matriz y el aviso de versión; "Lo que no se encontró" y "Páginas sin leer" primero; una fila por requisito con su síntesis, sus fragmentos (documento, página, texto literal, enlace al original en esa página) y sus acciones; filas técnicas con "cotizado" o "no cotizado" y la indicación de documentación técnica. Sin palabras de juicio en ninguna parte.
- **Historial** de una fila.
- Aviso de fin de pedido, el de la 003.

## Registro de auditoría (P6)

| Hecho | Qué guarda además de los datos comunes |
|---|---|
| `offer_register` | Procedimiento, oferta, oferente (id, no nombre en el detalle público) |
| `offer_load` | Oferta, tipo, título, nombre, formato, tamaño y huella; también las cargas rechazadas |
| `offer_read` | Documento, lectura, versiones de las herramientas, páginas por estado, páginas no leídas y de baja confianza, pasajes, tiempo |
| `sheet_request` | Oferta, versión de la matriz, lecturas incluidas |
| `sheet_build` | Ficha, versión de la matriz, modelos con huella, parámetros, versiones de instrucciones, cuentas por resultado, anomalías, tiempos. El detalle de cada pedido (candidatos con puntajes, pedido, salida) está en `offers_sheet_step` |
| `sheet_change` | Ficha, fila, acción, antes y después |
| `rejected` | Como en la 001 |

Con eso se reconstruye por qué el sistema mostró cada fragmento: documentos analizados, versión de la matriz, modelo y parámetros, instrucciones, candidatos recuperados, resultado, usuario y fecha.

## Medición (ADR-0025)

Reutiliza `evaluon/tenders/evaluation.py` sin rehacerlo: la lista esperada en YAML fuera del repositorio con huellas y visto bueno (`load_expected`), la carpeta de corrida (`parametros.json`, `resultados.jsonl`, `resumen.md`, `resumen-publico.md`), `proportion_text` (Wilson al 95 %) y `quotes.locate`. Lo nuevo es `offers/evaluation.py` y el comando `medir_fichas`, que corre la ficha con el canal `eval` en la base y la compara. Se corre de a una (GPU).

### Lista esperada de fichas

Un archivo por caso (`fichas-esperadas.yaml`). El caso chico, inventado, vive en el repositorio (`tests/offers/data/caso-chico/`); la del caso-00, en `corpus/casos/caso-00/esperado/`, fuera del repositorio, y la prepara el Coordinador leyendo las ofertas, sin correr el sistema.

```yaml
caso: caso-chico
matriz: {procedimiento: CASO-CHICO-SINTETICO}
ofertas:
  - oferente: "Oferente A"
    documentos: [{archivo: dj.pdf, sha256: …}, {archivo: constancia-escaneada.pdf, sha256: …}]
    fragmentos:
      - {id: F-001, requisito: M-003, documento: dj.pdf, pagina: 1, ancla: "Declaro bajo juramento…"}
    sin_respuesta: [M-007]
    renglones: {1: cotizado, 2: cotizado, 3: no_cotizado}
    documentacion_tecnica: si
    paginas_no_legibles: [{documento: constancia-escaneada.pdf, pagina: 2}]
visto_bueno: "responsable, AAAA-MM-DD"
```

`requisito` es el id de la lista de requisitos esperada de la 003 (`M-NNN`); la medición lo traduce a la fila de la matriz validada con el emparejamiento por cita que la 003 ya hace. `ancla` es el texto del pasaje tal como lo lee una persona; puede no coincidir palabra por palabra con el OCR.

### Cómo se cuenta

1. **Fragmento encontrado.** Un fragmento esperado se ubica en el texto canónico de la lectura por búsqueda aproximada dentro de su página (similitud de al menos 0,8 sobre ventanas del largo del ancla). Un fragmento propuesto de la fila del mismo requisito lo encuentra si está en el **mismo documento y la misma página** y su texto cubre al menos la mitad de los caracteres del pasaje ubicado, o si ambos caen en el mismo pasaje. No se exige igualdad de palabras (decisión del responsable, 2026-10-05).
2. **Texto literal.** Todo fragmento mostrado es igual al recorte del texto canónico y cae dentro de su pasaje y su página (100 %).
3. **Sin respuesta.** Todo requisito listado en `sin_respuesta` figura "no se encontró"; un fragmento propuesto ahí es un falso hallazgo.
4. **Fragmentos de más.** Los fragmentos propuestos sin pareja se cuentan y se informan; no bloquean (como los sobrantes de la 003).
5. **Renglones (REQ-044).** Cada renglón con el estado esperado (`cotizado` o `no_cotizado`) y la indicación de documentación técnica.
6. **Páginas no legibles (REQ-038).** Toda página de `paginas_no_legibles` está en la lista de no leídas o de baja confianza; toda página sin texto ni figura en esa lista es una falla.
7. **Síntesis (REQ-041).** Ninguna contiene palabras de juicio.
8. **Tiempo.** Por oferta y por página, informado, sin máximo.

### Umbrales, escritos antes de medir

| Medida | Caso chico (T-130) | Caso-00, tres ofertas (T-134 en adelante) |
|---|---|---|
| Fragmentos esperados encontrados (REQ-039) | 90 % o más | 90 % o más, con intervalo de Wilson informado |
| Texto literal (REQ-039) | 100 % | 100 % |
| Requisitos sin respuesta con "no se encontró" (REQ-040) | 100 % | informado, sin tope (los falsos hallazgos no bloquean) |
| Síntesis sin palabras de juicio (REQ-041) | 100 % | 100 % |
| Renglones con el estado correcto (REQ-044) | 100 % | 90 % o más (17 de 18) |
| Documentación técnica indicada (REQ-044) | 100 % | 100 % |
| Páginas sin texto ni figura en la lista de no leídas (REQ-038) | 0 | 0 |

Lo que bloquea la aceptación: fragmentos encontrados, texto literal, síntesis sin juicio, renglones, documentación técnica y páginas sin texto ni lista. Lo que se informa: falsos hallazgos, tiempo, páginas dudosas y su proporción.

### Rondas

- **Caso chico** (T-130): una medición, para comprobar que el corte funciona. Si no llega, se corrige dentro de T-130 antes de cerrarla; no cuenta como ronda del caso-00.
- **Caso-00:** T-134 mide la base y registra los hallazgos. T-135 corrige todos los hallazgos juntos, con un commit por hallazgo, y mide una vez (ronda 1). Solo si no llegó al umbral, T-136 repite (ronda 2). Después de la ronda 2 no hay más: lo que falta pasa, con su impacto, a la lista de revisión con el primer producto (ADR-0024). Una ronda más solo si el faltante hace perder un requisito o viola un principio.
- La medición a ciegas con otro caso queda diferida (spec, ADR-0024).
- La medición de caso-00 usa una matriz validada de ese caso: la prepara el Coordinador con el usuario de desarrollo a partir de la propuesta ya medida en la 003, sin tocar la 003.

## Tiempos y GPU

Estimación a confirmar con T-130 y T-134. Unas 35 a 45 filas por oferta, un pedido al modelo por fila (unos 3.000 tokens de entrada, unos 80 de salida): de 3 a 6 segundos cada uno, de 2 a 5 minutos por oferta. Embeddings y reranker son los de la 001. El OCR corre en CPU: se mide por página (segundos). La memoria de video no cambia: no hay modelo nuevo. Se informa por oferta y por página; no hay máximo (spec).

## Cobertura de requisitos

| Requisito | Cómo se resuelve | Cómo se verifica |
|---|---|---|
| REQ-037 | "Modelo de datos" (oferta, documento, original con huella) y "Carga y lectura", T-130 y T-131 | Test de carga con huella y rechazo de duplicado; pantalla completa en T-131 |
| REQ-038 | "Carga y lectura" y ADR-0028: lectura de la 001, lista de páginas no leídas y de baja confianza, fotos y segundo intento (T-131) | Test con PDF escaneado sintético; medición (umbral de páginas) |
| REQ-039 | "Flujo de IA": recuperación, reranker, elección del modelo, texto del pasaje (ADR-0027) | Medición: 90 % de fragmentos, 100 % literal, caso chico y caso-00 |
| REQ-040 | "Abstención" y fila `no_encontrado` con el aviso de páginas sin leer; lista "Lo que no se encontró" en la pantalla | Test con requisito sin respuesta; medición de `sin_respuesta` |
| REQ-041 | Instrucciones, control de palabras de juicio y reintento | Test del control; medición (100 % sin juicio) |
| REQ-042 | `services/review.py`, `offers_change`, hecho `sheet_change`, historial en pantalla (T-132) | Test de corregir y ver el fragmento anterior en el historial |
| REQ-043 | `offers_sheet.matrix_version`, ficha solo contra matriz validada, aviso de versión (T-130 y T-132) | Test con versión 1 y 2 de la matriz |
| REQ-044 | Pedido con `cotizado`, `technical_documents`, tipo de documento `tecnica` | Test de renglones; medición de renglones y documentación técnica |

## Verificación contra la constitución

| Principio | Cumple | Nota |
|---|---|---|
| P1 Spec fuente de verdad | sí | Cada tarea nombra sus REQ |
| P2 Trazabilidad | sí | Tabla de cobertura; tareas con REQ |
| P3 El sistema recomienda | sí | La ficha no dice cumple ni no cumple; "no se encontró" es un resultado válido; texto del pasaje, nunca del modelo |
| P4 Datos | sí | Ofertas reales solo en la base y en `corpus/casos/` (fuera del repositorio); los tests y el caso chico usan textos inventados; todo el camino con IA local, sin servicios externos |
| P5 Local y reproducible | sí | Sin servicios nuevos; mismo `docker compose` |
| P6 Auditoría | sí | Ver "Registro de auditoría" |
| P7 Evals | sí | Medición con lista esperada; baja de métricas requiere aprobación |
| P10 Simplicidad | sí | Sin servicio nuevo, sin índice aproximado, sin modelo de visión, sin comparación entre ofertas ni contenido técnico |
| P11 Compuertas | sí | El plan queda en borrador hasta que lo apruebe el responsable |

## Qué no se hace

Decir si cumple o no cumple (004); hojas de compliance (005); preguntas a la Comisión (009); comparar ofertas (006); comparar el contenido técnico con las especificaciones (010); medir a ciegas con otro caso (diferido, ADR-0024).

## Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Fotos de celular con OCR de baja calidad | Páginas ilegibles o dudosas, fragmentos faltantes | Lista visible de páginas no leídas; segundo intento con preparación de imagen (ADR-0028); el faltante por lectura se informa aparte del faltante por búsqueda |
| El requisito no está entre los 8 candidatos | Fragmento esperado no encontrado | Palabras y embeddings juntos; si la medición lo muestra, subir candidatos a 12 o sumar consultas por renglón (ronda de ajuste) |
| Un pasaje de 1.200 caracteres trae de más | Fragmento poco preciso | Aceptado: lo que cuenta es el mismo lugar (spec); la Comisión puede corregir |
| Tablas de precios mal leídas (renglones) | Renglón mal clasificado | Se mide aparte; la fila avisa cuando hay páginas sin leer; el ajuste puede sumar la zona de tabla (`tenders/tables.py`) |
| El modelo escribe una síntesis con juicio | Violación de P3 | Control por lista, reintento, y fila sin síntesis |
| Medición de GPU que se pisa con otra | Corridas repetidas | De a una; usar el bloqueo de mediciones del ADR-0025 si ya existe |
| `target_id` sin clave foránea | Referencia rota | Control en la función de negocio y prueba (ADR-0026) |
| Una oferta de otro caso se comporta distinto al caso-00 | Resultados provisorios | La medición a ciegas queda en la revisión con el primer producto |

## Decisiones

ADR 0026, 0027 y 0028, propuestos (ver arriba).

## Puntos para el responsable

1. **Tipo de documento al cargar.** El operador elige el tipo (propuesta económica, declaración jurada, garantía, constancia, técnica, otro). Propuesta: sí, con "otro" como valor por omisión; alimenta la indicación de documentación técnica (REQ-044).
2. **Fotos sueltas (JPG o PNG).** Propuesta: aceptarlas, convertidas a PDF dentro del equipo (T-131). Si el responsable las descarta, T-131 se achica.
3. **Matriz validada del caso-00.** La prepara el Coordinador con el usuario de desarrollo desde la propuesta medida en la 003, sin pedir aprobaciones operativas al responsable.
4. **Umbral de renglones en caso-00:** 90 % (17 de 18) y no 100 %, porque las tablas de precios escaneadas pueden perder un renglón. Propuesta: 90 %.
