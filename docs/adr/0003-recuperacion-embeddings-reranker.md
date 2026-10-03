# ADR-0003 · Recuperación: embeddings, reranker y búsqueda combinada sobre Postgres

Estado: aceptado · Fecha: 2026-10-02 · Decidió: responsable del proyecto

## Contexto

Antes de redactar una respuesta, EVALUON tiene que encontrar, entre todas las unidades citables cargadas, las pocas que tratan lo que la persona preguntó. Si esa búsqueda trae el artículo equivocado, la respuesta cita mal; si no trae nada pertinente, el sistema tiene que darse cuenta y decir "no determinado". Este ADR decide con qué piezas se hace esa búsqueda.

Dos términos que aparecen en todo el documento:

- **Embedding:** una lista de números que representa el significado de un texto, de modo que dos textos que hablan de lo mismo quedan "cerca" aunque usen palabras distintas. Sirve para encontrar el artículo sobre "garantía de mantenimiento de oferta" cuando alguien pregunta "cuánto hay que depositar para presentarse".
- **Reranker:** un segundo modelo que lee la pregunta junto con cada candidato y le pone un puntaje de pertinencia. Es más lento y más preciso que el embedding, por eso se usa solo sobre unas decenas de candidatos.

### Qué requisitos tiene que servir

| Requisito | Qué le pide a la recuperación |
|---|---|
| REQ-008 | Que la unidad correcta llegue al modelo que redacta, para que pueda citarla |
| REQ-009 | Una señal para decidir "no determinado" cuando nada de lo cargado responde |
| REQ-010 | Buscar por norma y número de artículo, y por palabras del texto |
| REQ-005 | Que las normas sin validar no aparezcan en ningún camino de búsqueda |
| REQ-007 | Que la búsqueda se haga respecto de una fecha y traiga las modificaciones registradas |
| REQ-017, REQ-018, REQ-019 | Que cada resultado lleve su categoría, que el orden de presentación respete la prelación y que régimen específico y marco nacional lleguen juntos cuando tratan el mismo punto |
| REQ-012 (P6) | Que quede registrado qué se recuperó, con qué modelo y con qué puntajes |

Además: 30 segundos por consulta en total, funcionamiento sin internet, y exigencias de calidad de la spec (85 % de respuestas correctas con la cita correcta, 90 % de abstención).

### Restricciones

- **Local y sin servicios externos (P4, P5).** Los mismos componentes se reusan en las features 002 a 004 con pliegos y ofertas.
- **Entorno (dato a confirmar por el responsable).** Notebook MSI con Intel Core Ultra 9 (24 núcleos), 32 GB de RAM y GPU NVIDIA RTX 5090 de notebook con 24 GB de memoria de video. Windows con WSL2, Docker Desktop 29, Python 3.12. Ya corre Postgres 17 con pgvector 0.8 (imagen `pgvector/pgvector:pg17`) con una base `evaluon`. Más adelante el sistema se muda a otro equipo.
- **Reparto de la memoria de video acordado entre planificadores.** Generación hasta unos 16 GB; embeddings y reranker juntos hasta unos 4 GB; el resto es margen.
- **Lo que se recibe (ADR-0004).** Unidades citables con documento, categoría, tipo de unidad, número o etiqueta, ubicación, texto literal y marca de reconocimiento sobre imagen.
- **Volumen.** Menos de 10 documentos y pocos usuarios a la vez. Eso da del orden de cientos a pocos miles de unidades (estimación; el número real sale de los informes de lectura).

### Lo que el volumen cambia

Con pocos miles de unidades, varias piezas habituales de un sistema de búsqueda no hacen falta todavía (P10). Este ADR separa lo que se necesita ahora de lo que queda para cuando una medición lo pida.

Hay además un dato propio del dominio: los modelos de embeddings recuperan mal las referencias con número exacto. Para un embedding, "artículo 23" y "artículo 32" son casi el mismo texto. Y en español jurídico la búsqueda por palabras puede rendir más que la búsqueda por significado: en PyLegalIR, un banco de pruebas de recuperación sobre fallos judiciales paraguayos, la búsqueda por palabras (BM25) obtuvo nDCG@10 de 0,710 contra 0,481 de BGE-M3 y 0,389 de jina-embeddings-v3 [F12]. Es un trabajo en revisión y sobre sentencias, no sobre normas, pero apunta en la misma dirección: no conviene depender solo de vectores.

## Alternativas

### 1. Modelo de embeddings

| | A. `BAAI/bge-m3` | B. `Qwen/Qwen3-Embedding-0.6B` |
|---|---|---|
| Licencia | MIT [F1] | Apache-2.0 [F4] |
| Tamaño | 568 a 569 millones de parámetros, 2,27 GB en precisión completa [F3] | 0,6 mil millones de parámetros [F4] |
| Dimensión del vector | 1024 [F1] | 1024, reducible entre 32 y 1024 [F4] |
| Entrada máxima | 8192 tokens [F1] | 32 mil tokens [F4] |
| Idiomas | Más de 100 [F1] | Más de 100 [F4] |
| Resultados publicados | En español (MIRACL, nDCG@10): 56,1 contra 52,9 de mE5-large [F2] | Mejor en la comparación general multilingüe: 64,64 en recuperación contra 54,60 de BGE-M3, según la tabla de sus autores [F5] |
| Cómo se usa | Texto tal cual, sin instrucciones | La pregunta debe llevar una instrucción; sin ella el rendimiento baja entre 1 y 5 % [F4] |
| Arquitectura | Codificador XLM-RoBERTa, la misma familia que el reranker A | Modelo generativo adaptado; requiere `transformers` 4.51 o superior [F4] |

**A. `BAAI/bge-m3`.** Se gana: el modelo más probado en despliegues propios, sin instrucciones que configurar, con resultado publicado en español, misma familia que el reranker recomendado (un solo tipo de servidor para los dos) y con variantes ajustadas a español jurídico que se podrían probar sin cambiar el esquema. Se pierde: en las comparaciones generales multilingües queda unos diez puntos por debajo de la alternativa B.

**B. `Qwen/Qwen3-Embedding-0.6B`.** Se gana: mejor puntaje general y entrada mucho más larga. Se pierde: hay que mantener una instrucción en la pregunta (un parámetro más que registrar y que puede desalinearse), los números son de sus propios autores, y no encontré ningún resultado específico en español ni en texto jurídico.

**Descartadas:**

- `Qwen/Qwen3-Embedding-4B`: mejor calidad (69,60 en la misma tabla [F5]), pero con 4 mil millones de parámetros ocupa del orden de 8 GB a media precisión (estimación por tamaño), el doble del cupo de 4 GB acordado.
- `jinaai/jina-embeddings-v3`: licencia CC BY-NC 4.0, de uso no comercial [F9], que deja en duda su uso en un organismo sin un acuerdo aparte, y fue el más bajo en PyLegalIR [F12].
- `littlejohn-ai/bge-m3-spa-law-qa` (BGE-M3 ajustado con 23.700 preguntas jurídicas en español, Apache-2.0, misma dimensión [F11]): interesante, pero su ficha no publica comparación contra el modelo base ni dice de qué país es el material. En PyLegalIR, ajustar BGE-M3 con datos sintéticos empeoró el resultado (de 0,481 a 0,325) [F12]. Queda como candidato a medir, no como punto de partida.

Las dos alternativas reales tienen la misma dimensión (1024), así que pasar de una a otra no cambia el esquema de la base: solo hay que recalcular los vectores.

### 2. Reranker

| | A. `BAAI/bge-reranker-v2-m3` | B. `Qwen/Qwen3-Reranker-0.6B` |
|---|---|---|
| Licencia | Apache-2.0 [F6] | Apache-2.0 [F8] |
| Tamaño | 0,6 mil millones de parámetros (568 millones) [F6] | 0,6 mil millones [F8] |
| Entrada máxima | 8192 tokens, pero fue entrenado hasta 1024 y sus autores recomiendan ese límite [F7] | 32 mil tokens [F8] |
| Puntaje | Un número que se lleva a escala 0 a 1 [F6] | Probabilidad de "sí" frente a "no", entre 0 y 1 [F8] |
| Resultados publicados | 58,36 multilingüe y 59,51 en documentos largos, según la tabla de Qwen [F8] | 66,36 multilingüe y 67,28 en documentos largos, según sus autores [F8] |
| Cómo se sirve | Misma arquitectura que los rerankers que el servidor propuesto declara soportar [F14] | No figura entre los modelos soportados por ese servidor [F14]; necesita otro |

**A. `BAAI/bge-reranker-v2-m3`.** Se gana: licencia abierta, se sirve con la misma herramienta que el embedding, puntaje directo entre 0 y 1 que sirve como señal de abstención. Se pierde: unos ocho puntos frente a B en las comparaciones generales, y un límite práctico de 1024 tokens por texto.

**B. `Qwen/Qwen3-Reranker-0.6B`.** Se gana: mejor puntaje general y textos más largos. Se pierde: hay que servirlo de otra manera (una pieza más que mantener), y los números son de sus autores.

**Descartadas:**

- `jinaai/jina-reranker-v2-base-multilingual`: licencia CC-BY-NC-4.0, solo para investigación y evaluación [F10].
- `Alibaba-NLP/gte-multilingual-reranker-base` (Apache-2.0, 306 millones de parámetros, 8192 tokens [F17]): más liviano, pero exige ejecutar código propio del repositorio del modelo (`trust_remote_code`), lo que complica reproducir y auditar; no encontré comparación directa con A.

### 3. Búsqueda por palabras

**A. Búsqueda de texto de Postgres, con configuración en español y sin acentos.** Ya está en la base, sin instalar nada. Hay que quitar los acentos antes de reducir las palabras a su raíz: sin eso, la configuración en español falla con palabras como "peluquería" escrita sin tilde [F20], y los usuarios van a escribir "licitacion". Postgres trae `unaccent` para encadenarlo dentro de la configuración de búsqueda [F19]. Se pierde: su orden por relevancia no usa estadísticas del conjunto de documentos (no es BM25) [F21]. No importa en este diseño, porque el orden final lo pone el reranker.

**B. Pesos por palabra que produce el propio BGE-M3, guardados en pgvector (`sparsevec`).** Se gana: una sola herramienta para las dos búsquedas. Se pierde: en español suma poco (58,1 combinado contra 56,1 solo por significado [F2]), obliga a correr el modelo con su librería propia dentro de Python y es opaco: no se puede explicar a un auditor por qué coincidió.

**C. Extensión de Postgres que agregue BM25.** Se gana: mejor orden por palabras. Se pierde: cambiar la imagen de la base ya instalada, sin beneficio medible a este volumen. No la evalué en detalle.

**D. Sin búsqueda por palabras, solo vectores.** Descartada: REQ-010 la exige, y es la que cubre lo que los vectores hacen mal.

### 4. Dónde se guardan y cómo se consultan los vectores

**A. pgvector en el Postgres que ya corre, sin índice aproximado.** Sin índice, pgvector compara contra todas las filas y el resultado es exacto [F23]. Con pocos miles de filas eso tarda milisegundos (estimación a medir). Los filtros por validación y por fecha son un `WHERE` común en la misma consulta.

**B. pgvector con índice HNSW.** HNSW acelera la búsqueda a cambio de resultados aproximados, más memoria y construcción más lenta [F23]. Con filtros, un índice aproximado puede devolver menos resultados de los pedidos; pgvector 0.8 lo mitiga con los recorridos iterativos del índice (`hnsw.iterative_scan`) [F22]. Es la respuesta correcta para cientos de miles de filas, no para este volumen. La dimensión 1024 está dentro del límite de 2000 que pgvector puede indexar [F23], así que agregarlo más adelante es una sentencia SQL.

**C. Un almacén de vectores aparte.** Descartada: un servicio más que levantar y respaldar, y los datos partidos en dos lugares cuando los filtros (validada, vigente, categoría) viven en Postgres.

### 5. Cómo se sirven los modelos

**A. Como servicio dentro de la red de Docker, con Text Embeddings Inference (TEI) de Hugging Face.** Un contenedor para el embedding y otro para el reranker. Expone `/embed` y `/rerank` por HTTP [F13], carga los modelos desde una carpeta local sin conexión [F13][F15], permite fijar la revisión exacta del modelo y la precisión (`--dtype float16`) [F15], y tiene imagen para CPU y para la serie RTX 50 [F13][F14]. Licencia Apache-2.0 [F13]. Se gana: la aplicación web queda liviana y sin dependencia de la GPU, y cambiar de modelo es cambiar una variable. Se pierde: la imagen para la serie RTX 50 figura como experimental [F14], y son dos contenedores más.

**B. Dentro del proceso de Python de la aplicación** (`sentence-transformers` o `FlagEmbedding`). Se gana: menos contenedores y acceso a todo lo que el modelo ofrece. Se pierde: la imagen de la aplicación pasa a incluir PyTorch con CUDA (para la RTX 5090 hace falta una versión compilada con CUDA 12.8 o superior [F18]), la aplicación ocupa memoria de video y no puede correr en varios procesos sin cargar los modelos varias veces.

**C. En el mismo motor que el modelo de generación (ADR-0002).** Depende de qué motor se elija. Ollama ofrece `bge-m3` para embeddings (1,2 GB) [F16], pero no encontré un punto de entrada oficial para rerankers [F24]; el reranker tendría que correr aparte igual. llama.cpp tiene opciones para embeddings y para reranking [F25]. En la integración del plan se verificó lo siguiente: su documentación nombra a `bge-reranker-v2-m3` como ejemplo del endpoint de reranker [F25], que se probó con ese modelo cuando se incorporó [F28]; existen archivos GGUF de los dos modelos, en precisión FP16, de 1,16 GB cada uno [F29][F30]; el endpoint de embeddings devuelve el vector ya normalizado [F25]. Se gana: una sola imagen para los tres modelos, que es la que el ADR-0002 ya obliga a fijar y probar, sin imagen experimental. Se pierde: los archivos GGUF son conversiones de un tercero y no de los autores; solo se obtiene el vector denso de BGE-M3 (es el único que este ADR usa); el puntaje del reranker llega sin escala fija y hay que convertirlo [F32]; y no encontré una medición de que la conversión dé los mismos resultados que el original (ver "Sin verificar").

### 6. Un vector por unidad o unidades subdivididas

**A. Un vector por unidad, siempre.** Lo más simple. Falla con unidades largas: el reranker recomendado pierde calidad por encima de 1024 tokens [F7], y un solo vector para un anexo de varias páginas diluye su contenido.

**B. Pasajes de búsqueda que apuntan a la unidad.** Cada unidad tiene uno o más pasajes. Una unidad corta tiene un único pasaje, que es ella misma. Una unidad larga (un anexo, un artículo con muchos incisos) se parte en pasajes con solape. Se busca y se reordena por pasaje; el resultado se agrupa por unidad, con el mejor puntaje de sus pasajes. La cita, el texto literal y lo que ve el usuario son siempre la unidad.

## Decisión

Se propone una búsqueda en dos etapas sobre el Postgres que ya está, con tres caminos de entrada y un reranker que decide el orden y la abstención.

### Piezas elegidas

| Pieza | Elección | Motivo principal |
|---|---|---|
| Embeddings | `BAAI/bge-m3`, vector de 1024, distancia coseno | Licencia MIT, resultado publicado en español, sin instrucciones, se sirve igual que el reranker |
| Reranker | `BAAI/bge-reranker-v2-m3` | Apache-2.0, puntaje 0 a 1 utilizable como señal de abstención, mismo servidor |
| Búsqueda por palabras | Texto de Postgres, configuración propia derivada de `spanish` con `unaccent` | Ya está instalada, es explicable y cubre REQ-010 |
| Referencias exactas | Consulta directa por norma y número de unidad | Los vectores no distinguen números |
| Almacén | pgvector en el Postgres existente, sin índice aproximado | Resultado exacto y filtros simples; a este volumen el índice no aporta |
| Servicio | Dos contenedores `llama-server` (servicios `embeddings` y `reranker`), con la misma imagen que el motor de generación; TEI queda como plan B | Aplicación liviana, modelos intercambiables y una sola tecnología de IA que fijar y probar (P10) |
| Unidades largas | Pasajes de búsqueda que apuntan a la unidad | El reranker rinde hasta 1024 tokens; los anexos son largos |

`Qwen/Qwen3-Embedding-0.6B` y `Qwen/Qwen3-Reranker-0.6B` quedan como reemplazo designado si la medición no alcanza las metas. No se comparan de entrada: con unas 30 preguntas y un reranker detrás, es improbable que la diferencia se pueda medir, y hacerlo antes de necesitarlo es trabajo que ningún requisito pide (P10).

### Cómo funciona una consulta

1. **Entrada.** La pregunta y una fecha de referencia (por defecto, el día de la consulta).
2. **Unidades consultables.** Los tres caminos leen de una única vista de la base, `consultable_units`, que recibe la fecha de referencia y deja pasar solo unidades de normas validadas (REQ-005) y de versiones que corresponden a esa fecha (REQ-007). Las unidades derogadas a esa fecha salen marcadas y no entran en la consulta en lenguaje natural. Ningún camino consulta las tablas por fuera de esa vista. Es un solo lugar para probar y para auditar.
3. **Tres caminos de candidatos.**
    - *Por significado:* el embedding de la pregunta contra los vectores de los pasajes; los 30 más cercanos.
    - *Por palabras:* búsqueda de texto de Postgres con las palabras de la pregunta unidas por "o" (unidas por "y", una pregunta larga no coincidiría con nada); los 30 mejores.
    - *Por referencia exacta:* si la pregunta menciona "artículo 23", "art. 5 inc. b" o "Disposición 297/03", se detecta con un patrón y se trae esa unidad directamente por sus datos.
4. **Unión.** Se juntan los candidatos sin repetir (como mucho unos 65 pasajes). No hace falta una fórmula de fusión de listas: el orden lo pone el paso siguiente.
5. **Reranker.** Puntúa cada candidato contra la pregunta. La aplicación lleva el valor que devuelve el servidor a un número de 0 a 1 con la función sigmoide, que es la conversión que describen los autores del modelo [F6]. Los pasajes se agrupan por unidad base con su mejor puntaje.
6. **Abstención.** Si ningún candidato supera el umbral, el resultado es "no determinado" y no se llama al modelo de generación (ver abajo).
7. **Selección por categoría.** Pasan las unidades que superan el umbral, hasta 3 por categoría (valor inicial). El cupo por categoría existe para que el régimen específico no deje afuera al marco nacional ni a un dictamen cuando tratan el mismo punto (REQ-018, REQ-019). Los considerandos tienen un cupo aparte, de hasta 2, para que un fundamento no desplace a un artículo.
8. **Modificaciones.** A cada unidad seleccionada se le suman las unidades que la modifican o derogan a la fecha de referencia, tomadas de las relaciones registradas (REQ-006, REQ-007). Esto se hace por relación, no por parecido, para que la modificación acompañe siempre al original.
9. **Orden de entrega.** Régimen específico, otra normativa aplicable, marco nacional, dictamen legal, recomendación de auditoría; dentro de cada categoría, por puntaje; los considerandos, al final. El orden lo fija el código, no el modelo de generación.

La categoría no entra en el puntaje de pertinencia. La pertinencia se mide igual para todos los documentos; la prelación se aplica después, en la selección y en el orden. Mezclar las dos cosas haría que un artículo poco pertinente del régimen específico tape a uno pertinente de otra categoría, y volvería el puntaje imposible de explicar.

### Búsqueda directa (REQ-010)

- *Por norma y número de artículo:* la misma consulta directa del camino por referencia exacta. No usa modelos.
- *Por palabras del texto:* la búsqueda de texto de Postgres, con sintaxis de buscador (comillas para frase exacta) [F21].

Las dos pasan por la vista de unidades consultables.

### Señal para "no determinado" (REQ-009)

La señal propuesta es el **puntaje más alto que el reranker le da a algún candidato**.

- Si ese puntaje queda por debajo de un umbral, el sistema responde "no determinado" sin generar texto. Es una regla fija, reproducible y que queda registrada.
- El umbral se calibra con el conjunto de preguntas: se mira el puntaje máximo en las preguntas con respuesta y en las preguntas sin respuesta, y se elige el valor que mejor las separa.
- El umbral es un parámetro registrado. Cambiarlo exige volver a correr el conjunto (P7).

Límites que conviene conocer antes de aprobar:

- El puntaje del reranker mide si un texto trata el tema de la pregunta, no si la responde. Esta señal frena bien las preguntas ajenas a la normativa cargada. Las preguntas sobre un tema que la normativa menciona pero no resuelve pueden superar el umbral; ahí la segunda barrera es el modelo de generación, que debe poder responder "no determinado", y la comprobación de que cada cita es literal. Esas dos barreras corresponden al ADR-0002 y al plan.
- Con unas 30 preguntas, de las cuales una parte no tiene respuesta, calibrar y medir sobre las mismas preguntas da un resultado optimista. Se propone calibrar dejando cada vez una pregunta afuera y medir sobre ella, e informar el umbral como provisorio.
- El puntaje no es una probabilidad: 0,7 no significa "70 % de certeza". Solo sirve para comparar contra el umbral.

### Qué se necesita ahora y qué no

| Pieza | ¿Ahora? | Motivo |
|---|---|---|
| Búsqueda por palabras y por referencia exacta | Sí | REQ-010 las pide y cubren lo que los vectores hacen mal |
| Embeddings | Sí | Los integrantes de la Comisión preguntan con sus palabras, no con las de la norma |
| Reranker | Sí | De él sale la señal de abstención; además P5 lo da por parte del sistema |
| Pasajes para unidades largas | Sí | REQ-003 incluye anexos |
| Índice aproximado (HNSW) | No | Se agrega cuando la búsqueda exacta medida supere unos 200 ms |
| Fórmula de fusión de listas | No | El reranker ordena la unión |
| Almacén de vectores aparte | No | Nada lo pide |
| Modelos más grandes | No | No entran en el cupo y nada indica que hagan falta |
| Ajuste del modelo al dominio | No | Sin evidencia de mejora; ver PyLegalIR [F12] |

La medición con el conjunto de preguntas incluye correr la búsqueda quitando una pieza por vez. Si el embedding o el reranker no aportan nada medible, se informa al responsable en lugar de sostenerlos por costumbre.

### Qué se guarda

- **Por pasaje:** la unidad a la que pertenece, su orden dentro de ella, el texto, el vector, y el nombre y la revisión del modelo que lo calculó.
- **Texto que se convierte en vector:** el texto literal precedido por un encabezado con la norma y la ubicación (por ejemplo, "Disposición AFIP 297/03, artículo 23"), porque un artículo suelto muchas veces no dice de qué norma es. El texto literal de la unidad se guarda aparte y no se toca.
- **Índice de texto (GIN)** sobre la columna de búsqueda por palabras: una línea, sin costo apreciable. Ningún índice sobre los vectores.
- **Nunca se truncan textos en silencio:** una entrada que exceda el límite se rechaza, en lugar de recortarse. `llama-server` responde con error ante una entrada demasiado larga, según un reporte de su repositorio [F33]; se comprueba en el equipo. TEI, el plan B, recorta por defecto y habría que configurarlo [F15].

### Qué se registra por consulta (P6, REQ-012)

Pregunta, fecha de referencia, usuario y momento; nombre y revisión del modelo de embeddings y del reranker; parámetros (cantidad de candidatos por camino, umbral, cupo por categoría); cada candidato con el camino por el que entró y su puntaje del reranker; las unidades seleccionadas y las agregadas por relación; y la decisión de abstención con el puntaje máximo que la motivó. Con ese registro se explica una consulta pasada sin volver a ejecutarla.

### Memoria de video

| Modelo | Precisión completa | Media precisión (`float16`) |
|---|---|---|
| `bge-m3` | 2,27 GB [F3] | 1,1 GB aprox. |
| `bge-reranker-v2-m3` | 2,3 GB aprox. (mismo tamaño de modelo) | 1,1 GB aprox. |
| Total de pesos | 4,5 GB aprox. | 2,3 GB aprox. |

A media precisión entra en el cupo de 4 GB, con margen para la memoria de trabajo. Los archivos GGUF en FP16 que se van a usar pesan 1,16 GB cada uno [F29][F30], en línea con esa estimación. A precisión completa **no entra**: solo los pesos superan el cupo. Si la media precisión no funcionara en este equipo, el ajuste propuesto es correr el embedding en CPU y dejar solo el reranker en GPU. A este volumen, calcular en CPU el vector de una pregunta y reindexar pocos miles de pasajes es tolerable (estimación a medir). El consumo real se mide en el equipo con los dos modelos cargados junto al de generación.

### Relación con el motor de generación (ADR-0002)

Estos dos modelos corren en contenedores propios (`embeddings` y `reranker`), aparte del contenedor de generación, y no lo necesitan para funcionar. Comparten con él la imagen de `llama-server`, la compilación fijada, la GPU y el cupo de memoria.

La aplicación conoce solo dos operaciones: convertir textos en vectores y puntuar una pregunta contra una lista de textos. Si la comprobación del entorno muestra que alguno de los dos modelos no carga en `llama-server` o no reproduce los valores publicados por sus autores, el plan B es TEI, con su imagen para la serie RTX 50, que figura como experimental [F14]. Si tampoco funcionara, queda un contenedor propio con `sentence-transformers` que ofrezca esas mismas dos operaciones. En los tres casos los servicios se llaman igual y el resto del sistema no cambia.

## Cómo se mide

Cada pregunta del conjunto (`evals/`) lleva, además de su respuesta, la unidad o las unidades que la sostienen. Con eso se mide la recuperación por separado de la redacción, para saber dónde falla cuando falla.

| Medida | Qué responde | Meta propuesta |
|---|---|---|
| Unidad correcta entre los candidatos, por camino y en la unión | ¿La búsqueda la encuentra? | Informativa |
| Unidad correcta entre las seleccionadas | ¿Llega al modelo que redacta? | Al menos 95 % de las preguntas con respuesta |
| Posición de la unidad correcta | ¿Queda arriba o al fondo? | Informativa |
| Preguntas sin respuesta frenadas por el umbral | ¿Cuánto de la abstención resuelve la recuperación sola? | Informativa; el 90 % de la spec se mide sobre el sistema completo |
| Preguntas con respuesta frenadas por error | ¿El umbral es demasiado alto? | A lo sumo 5 % |
| Tiempo de la etapa de recuperación | ¿Deja lugar a la generación dentro de los 30 segundos? | Hasta 3 segundos |

La meta de 95 % se deriva de la spec: si la unidad correcta no llega al modelo que redacta, la respuesta no puede ser correcta, y la spec exige 85 % al final de la cadena. Las metas son una propuesta; las fija el responsable (P7).

Se corre una vez la comparación quitando piezas: solo vectores, solo palabras, combinada sin reranker, completa.

Advertencia sobre el tamaño: con unas 30 preguntas, cada una pesa entre 3 y 5 puntos porcentuales. Una diferencia de una pregunta entre dos configuraciones no demuestra nada.

Para que la medición sea útil, conviene que el conjunto incluya preguntas con referencia exacta ("qué dice el artículo N"), preguntas con palabras distintas a las de la norma, preguntas que tocan dos categorías, preguntas ajenas a la normativa y preguntas sobre un tema cercano que la normativa no resuelve. Es una sugerencia para quien arma el conjunto; no cambia la spec.

## Consecuencias

**Más fácil**

- Una sola base para datos, texto y vectores: un respaldo, un lugar donde aplicar los filtros de validación y vigencia.
- Cada resultado se puede explicar: por qué camino entró, qué puntaje tuvo, por qué quedó o no.
- Las features 002 a 004 reusan los mismos dos servicios y el mismo esquema de pasajes para pliegos y ofertas, sin servicios externos (P4).
- El entorno se levanta con Docker, con los modelos en una carpeta local y la revisión fijada (P5).

**Más difícil**

- Hay tres caminos de búsqueda para probar en lugar de uno; el requisito REQ-005 debe probarse en los tres.
- El umbral de abstención es un valor que hay que calibrar y volver a calibrar si cambia el reranker o el corpus.
- El detector de referencias exactas depende de cómo estén escritos los números ("297/03" y "297/2003", "23 bis"); requiere que la lectura de documentos entregue números normalizados.
- La imagen de la base debe fijarse a una versión concreta en lugar de `pg17` a secas, para que el traslado a otro equipo reproduzca lo mismo.

**Cambiar de modelo de embeddings más adelante**

1. Agregar el modelo nuevo al servicio.
2. Recalcular los vectores de todos los pasajes con el modelo nuevo, guardándolos con su nombre y revisión. A este volumen son minutos. Nunca se buscan juntos vectores de dos modelos.
3. Correr el conjunto de preguntas con el modelo nuevo y comparar (P7). Una baja necesita aprobación del responsable.
4. Recalibrar el umbral de abstención, porque cambian los candidatos que llegan al reranker.
5. Cambiar la configuración y borrar los vectores viejos.

Si el modelo nuevo tiene la misma dimensión (es el caso de `Qwen3-Embedding-0.6B`), el esquema no cambia. Si tiene otra, hay que agregar una columna. Las consultas ya registradas siguen siendo explicables porque el registro guarda lo recuperado y los puntajes, no solo el nombre del modelo.

**Revertir la decisión**

- Cambiar de reranker: reemplazar el contenedor, recalibrar el umbral y correr el conjunto.
- Pasar los modelos a TEI o al proceso de Python: se reemplaza el cliente de las dos operaciones, se recalibra el umbral y se corre el conjunto; los datos no se tocan.
- Dejar pgvector por otro almacén: exportar pasajes y vectores. Es el cambio más caro, porque los filtros dejarían de estar junto a los datos.

## Qué necesita decidir el responsable

1. Aprobar `bge-m3` y `bge-reranker-v2-m3` como par de partida, con los modelos Qwen3 de 0,6B como reemplazo si la medición no alcanza.
2. Aprobar la búsqueda combinada (significado, palabras y referencia exacta) sobre el Postgres existente, sin índice aproximado por ahora.
3. Aprobar que embeddings y reranker corran cada uno en su contenedor, con la misma imagen de `llama-server` que el motor de generación, y con TEI como plan B si la comprobación del entorno lo pide.
4. Aprobar la señal de abstención (umbral sobre el puntaje del reranker) y cómo se calibra con un conjunto de unas 30 preguntas.
5. Fijar las metas de recuperación de la sección "Cómo se mide".
6. Confirmar los datos del entorno.

## Dudas que este ADR no resuelve

No modifican la spec; se informan para que las resuelva quien corresponda. Las tres quedaron resueltas en la sección "Aclaraciones posteriores a la aprobación" de la spec, en el sentido que este ADR suponía.

- **Unidades derogadas.** La spec no dice si una unidad derogada a la fecha de referencia puede sostener una respuesta. Este ADR supone que no entra en las respuestas y que sí aparece en la búsqueda directa, marcada como derogada. *Resuelta: es así.*
- **Fecha de referencia en la pantalla.** REQ-007 habla de "una fecha dada" y REQ-013 no dice si la pantalla permite elegirla. Este ADR supone la fecha del día salvo indicación. *Resuelta: la fecha del día; la pantalla no permite elegirla.*
- **Detalle de las relaciones.** REQ-006 habla de relaciones entre normas y el criterio de REQ-007 de un artículo modificado. Para sumar la modificación a cada unidad recuperada, la relación tiene que estar registrada a nivel de unidad, no solo de norma. *Resuelta: las relaciones se registran entre normas y, cuando corresponde, entre unidades.*

## Dependencias con otros ADR

- **ADR-0002 (motor y modelo de generación).** Comparte la imagen de `llama-server` y su compilación, no el contenedor. Necesita saber: llegan como mucho unas 15 unidades más las agregadas por relación, cada una con su categoría y su estado a la fecha; el modelo debe poder responder "no determinado" como segunda barrera; y el consumo de memoria de video de recuperación es de unos 2,3 GB de pesos a media precisión.
- **ADR-0004 (lectura y partición).** Se necesita: tipo y número de norma y de unidad normalizados; saber si las unidades están anidadas (un artículo y además sus incisos), para no indexar dos veces el mismo texto; y un título o encabezado de contexto por unidad si existe. El plan lo resuelve así: los pasajes se arman solo con las unidades base (todas menos los incisos), y el encabezado de contexto es el nombre de la norma más la ruta (`path`) de la unidad. Las unidades leídas por reconocimiento sobre imagen pueden coincidir peor en la búsqueda por palabras; la marca se registra con cada candidato.
- **Aplicación web y modelo de datos.** La vista de unidades consultables, la tabla de pasajes y el registro por consulta forman parte del esquema. La imagen de Postgres debe incluir `unaccent`.

## Sin verificar

- **Rendimiento en español jurídico argentino.** No encontré ninguna medición de estos modelos sobre normativa administrativa argentina. La evidencia usada es general (multilingüe, español de MIRACL) o de otro tipo de texto jurídico (sentencias paraguayas). La medición propia es la que decide.
- **Números de los modelos Qwen3.** Las comparaciones [F5][F8] son de sus autores; no encontré una réplica independiente.
- **Tiempos.** No medí cuánto tarda el reranker con 65 candidatos, ni la búsqueda exacta en pgvector, ni el embedding en CPU. Las cifras de este documento son estimaciones.
- **Memoria de video real.** Las cifras a media precisión salen de dividir por dos el tamaño publicado. No encontré el tamaño publicado de `bge-reranker-v2-m3` en GB; lo estimé por su cantidad de parámetros. No verifiqué qué precisión usa TEI en GPU cuando no se le indica.
- **`llama-server` con estos modelos y esta GPU.** No se probó en el equipo. Los archivos GGUF son conversiones de un tercero, hechas con versiones viejas de llama.cpp [F29][F30]; una conversión de otro tercero no cargaba por faltarle un dato [F31]. No encontré una medición independiente de que la conversión dé los mismos resultados que el modelo original. Hay un reporte abierto de 2025 sobre BGE-M3 en una compilación de llama.cpp, con otra placa y otro programa cliente [F34]; no sé si aplica a la compilación actual. No verifiqué la escala del puntaje del reranker en la compilación a fijar, ni el tiempo con 65 candidatos. Se cierra en la comprobación del entorno, comparando contra los valores de ejemplo que publican los autores en las fichas de los modelos [F1][F6].
- **TEI con estos modelos y esta GPU (plan B).** La documentación lista la arquitectura XLM-RoBERTa y otros rerankers de la misma familia, pero no nombra a `bge-m3` ni a `bge-reranker-v2-m3` [F14]. La imagen para la serie RTX 50 figura como experimental [F14] y no verifiqué su funcionamiento bajo WSL2 con Docker Desktop. No verifiqué si TEI puede entregar los pesos por palabra de BGE-M3.
- **Configuración `spanish` y `unaccent` en la imagen `pgvector/pgvector:pg17`.** La configuración `spanish` aparece usada en informes de la lista de Postgres [F20], pero no la confirmé en esta imagen ni que la imagen traiga `unaccent`. Se comprueba con `\dF` y `CREATE EXTENSION unaccent`.
- **Versión exacta de pgvector instalada.** El encargo dice 0.8; el registro de cambios muestra correcciones hasta la 0.8.6, del 2026-07-29 [F26]. No verifiqué qué etiqueta de imagen corresponde a cada versión.
- **Cómo trata la búsqueda de texto de Postgres los números con barra ("297/03").** Por eso las referencias exactas van por consulta directa y no por búsqueda de texto.
- **Extensiones BM25 para Postgres.** Mencionadas como alternativa sin evaluación.
- **Modelos más nuevos.** Las guías consultadas, una actualizada en septiembre de 2026 [F27], siguen presentando a BGE-M3 y a la familia Qwen3 como las opciones abiertas principales. Son fuentes secundarias con datos inconsistentes entre sí; no descarto que exista un modelo más reciente que no apareció en la búsqueda.

## Fuentes

Consultadas el 2026-10-02.

- [F1] Ficha de `BAAI/bge-m3`: https://huggingface.co/BAAI/bge-m3
- [F2] Chen y otros, "BGE M3-Embedding", tabla 1 (MIRACL): https://arxiv.org/abs/2402.03216
- [F3] Documentación de BGE-M3 (tamaño del modelo): https://bge-model.com/bge/bge_m3.html
- [F4] Ficha de `Qwen/Qwen3-Embedding-0.6B`: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B
- [F5] Repositorio de Qwen3-Embedding (tablas comparativas): https://github.com/QwenLM/Qwen3-Embedding
- [F6] Ficha de `BAAI/bge-reranker-v2-m3`: https://huggingface.co/BAAI/bge-reranker-v2-m3
- [F7] Respuesta de los autores sobre la longitud máxima del reranker: https://huggingface.co/BAAI/bge-reranker-v2-m3/discussions/9
- [F8] Ficha de `Qwen/Qwen3-Reranker-0.6B`: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B
- [F9] Ficha de `jinaai/jina-embeddings-v3`: https://huggingface.co/jinaai/jina-embeddings-v3
- [F10] Ficha de `jinaai/jina-reranker-v2-base-multilingual`: https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual
- [F11] Ficha de `littlejohn-ai/bge-m3-spa-law-qa`: https://huggingface.co/littlejohn-ai/bge-m3-spa-law-qa
- [F12] "PyLegalIR: A Benchmark for Spanish Legal Information Retrieval" (envío anónimo en revisión): https://openreview.net/pdf?id=v7Plc4IhVs
- [F13] Text Embeddings Inference, repositorio: https://github.com/huggingface/text-embeddings-inference
- [F14] Text Embeddings Inference, modelos y equipos soportados: https://huggingface.co/docs/text-embeddings-inference/supported_models
- [F15] Text Embeddings Inference, opciones de arranque: https://huggingface.co/docs/text-embeddings-inference/cli_arguments
- [F16] `bge-m3` en la biblioteca de Ollama: https://ollama.com/library/bge-m3
- [F17] Ficha de `Alibaba-NLP/gte-multilingual-reranker-base`: https://huggingface.co/Alibaba-NLP/gte-multilingual-reranker-base
- [F18] Foro de PyTorch, soporte de la serie RTX 50: https://discuss.pytorch.org/t/pytorch-support-for-sm-120/222119
- [F19] PostgreSQL 17, `unaccent`: https://www.postgresql.org/docs/17/unaccent.html
- [F20] Lista de PostgreSQL, BUG #14278 (acentos con la configuración `spanish`): https://www.postgresql.org/message-id/20160804102524.1430.90715%40wrigleys.postgresql.org
- [F21] PostgreSQL 17, control de la búsqueda de texto: https://www.postgresql.org/docs/17/textsearch-controls.html
- [F22] Anuncio de pgvector 0.8.0: https://www.postgresql.org/about/news/pgvector-080-released-2952
- [F23] pgvector, documentación del repositorio: https://github.com/pgvector/pgvector
- [F24] Ollama, consulta sobre el punto de entrada de reranking: https://github.com/ollama/ollama/issues/10467
- [F25] llama.cpp, documentación del servidor: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- [F26] pgvector, registro de cambios: https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md
- [F27] Guía de modelos de embeddings para RAG (fuente secundaria): https://www.premai.io/blog/best-embedding-models-for-rag-2026-ranked-by-mteb-score-cost-and-self-hosting/

Agregadas en la integración del plan, consultadas el 2026-10-02:

- [F28] llama.cpp, incorporación del reranking (probado con `BAAI/bge-reranker-v2-m3`): https://github.com/ggml-org/llama.cpp/pull/9510
- [F29] Archivos GGUF de `bge-m3` (licencia MIT, FP16 de 1,16 GB): https://huggingface.co/gpustack/bge-m3-GGUF
- [F30] Archivos GGUF de `bge-reranker-v2-m3` (licencia Apache-2.0, FP16 de 1,16 GB): https://huggingface.co/gpustack/bge-reranker-v2-m3-GGUF
- [F31] Reporte de un archivo GGUF del reranker que no cargaba por faltarle el dato `bert.context_length`: https://github.com/Tanguille/cluster/pull/5232
- [F32] Guía de uso del endpoint de reranker de llama.cpp, con puntajes sin escala fija en el ejemplo (fuente secundaria): https://www.simplified.guide/llama-cpp/server-call-rerank-api
- [F33] llama.cpp, reporte sobre el error ante una entrada demasiado larga: https://github.com/ggml-org/llama.cpp/issues/11105
- [F34] llama.cpp, reporte abierto sobre BGE-M3 en una compilación de 2025: https://github.com/ggml-org/llama.cpp/issues/13494

## Ajustes de integración

Hechos el 2026-10-02 al integrar el plan (`specs/001-normativa/plan.md`). Los modelos elegidos, la búsqueda combinada, el almacén y la señal de abstención no cambian.

- **Cómo se sirven los modelos.** La decisión pasó de dos contenedores TEI a dos contenedores `llama-server` con la misma imagen que el motor de generación (ADR-0002). Motivo: el sistema ya tiene que fijar, probar y mudar esa imagen; sumar TEI agregaba una segunda tecnología cuya imagen para la serie RTX 50 figura como experimental (P10). La evidencia reunida está en la alternativa 5.C, y lo que falta comprobar, en "Sin verificar". Como esa evidencia no alcanza para darlo por seguro, TEI queda como plan B y decide la comprobación del entorno (etapa 0 del plan). Se actualizaron la alternativa 5.C, la fila "Servicio" de la tabla de piezas, "Memoria de video", "Relación con el motor de generación", el punto 3 de "Qué necesita decidir el responsable", "Revertir la decisión", "Dependencias con otros ADR" y "Sin verificar".
- **Nombres de los servicios.** `embeddings` y `reranker`, como en el ADR-0005 y en el plan.
- **Reemplazo designado.** Las tablas de alternativas 1 y 2 comparan cómo se sirve cada modelo pensando en TEI y quedan como estaban. No verifiqué si `Qwen3-Embedding-0.6B` y `Qwen3-Reranker-0.6B` se pueden servir con `llama-server`; se verifica solo si la medición obliga a usarlos.
- **Escala del puntaje.** `llama-server` devuelve el puntaje del reranker sin escala fija. La aplicación lo convierte a un número de 0 a 1 con la función sigmoide, de modo que el umbral y el registro usan siempre la misma escala, con cualquiera de los servidores. Se actualizó el paso 5.
- **Vista de unidades consultables.** Se llama `consultable_units` y se implementa como una función SQL que recibe la fecha, porque una vista común no admite parámetros. Sigue siendo el único lugar por el que pasan los tres caminos. La acompaña `unit_changes`, que devuelve las modificaciones vigentes de cada unidad. Se actualizó el paso 2.
- **Unidades anidadas.** Los pasajes se arman solo con unidades base; los incisos no se indexan por separado. La respuesta cita siempre la unidad base. Con eso el mismo texto no entra dos veces.
- **Considerandos.** La spec los definió como unidades citables, que se citan como contexto. Tienen un cupo propio en la selección y van al final del orden. Se actualizaron los pasos 7 y 9.
- **Relaciones.** El paso 8 se apoya en relaciones registradas por norma y clave de unidad (`key`), con su fecha, como define el plan.
- **Abstención.** El plan deja una sola regla con tres motivos: nada supera el umbral, el modelo se abstiene, o la cita es inválida. El umbral de este ADR es el primero. Se calibra para no frenar preguntas con respuesta (a lo sumo 5 %, la meta que ya estaba en "Cómo se mide"), no para alcanzar por sí solo el 90 % de abstención.
- **Dudas.** Las tres de "Dudas que este ADR no resuelve" quedaron resueltas por la spec; se anotó en cada una.
- **Metas de recuperación.** El plan propone al responsable tratarlas como medidas de diagnóstico; las exigencias son las de la spec.

## Actualización por ADR-0006

- **2026-10-02.** La fecha de referencia ya no es siempre la del día: la indica la persona en la pantalla como fecha de autorización del procedimiento (REQ-020). Lo que este ADR dice sobre "la fecha del día" queda reemplazado por el plan 001 actualizado.

## Adenda 2026-10-02 · Separador de pares en el reranker (etapa 0, T-003)

Decidió: responsable del proyecto, 2026-10-02. La decisión de este ADR no cambia: mismo modelo, mismo archivo, mismo servidor. Esta adenda fija un parámetro de arranque que la decisión original no preveía.

**Qué se comprobó.** El archivo GGUF de `bge-reranker-v2-m3` (conversión de gpustack [F30], huella en `scripts/models.sha256`) no trae el dato `tokenizer.ggml.add_sep_token`. Sin él, `llama-server` arma cada par como `<s> pregunta </s> pasaje </s>`, con 3 tokens especiales, en lugar del formato del modelo original, `<s> pregunta </s></s> pasaje </s>`, con 4 (el `tokenizer.json` oficial de BAAI). Con los dos pares de la ficha [F6]:

| Par de la ficha | Publicado | Archivo tal como viene | Con `add_sep_token=true` |
|---|---|---|---|
| `what is panda?` · `hi` | −8,19 | −7,49 | −8,18 |
| `what is panda?` · pasaje del panda | 5,26 | 5,48 | 5,28 |

Detalle, comandos y salidas: `specs/001-normativa/entorno.md`, T-003, secciones 1, 4 y 8.

**Decisión.** Forzar el dato al cargar el modelo, con `--override-kv tokenizer.ggml.add_sep_token=bool:true` en el servicio `reranker`. Es configuración legítima del mismo modelo, que lo hace armar los pares como su original; no es el plan B (TEI), que sigue reservado para un modelo que no carga o no reproduce los valores publicados.

**Consecuencias.**

- El parámetro es obligatorio en el servicio `reranker`. Sin él, el servicio arranca y responde igual, pero con puntajes distintos: el error no se nota a simple vista.
- El umbral de abstención (REQ-009) se calibra con el parámetro puesto. Quitarlo o cambiarlo exige recalibrar el umbral y correr el conjunto de preguntas (P7).
- Cualquier cambio de compilación de `llama.cpp` o del archivo del reranker repite la prueba de los dos pares de la ficha antes de usarse. Una compilación nueva podría leer el dato de otra manera, y un archivo nuevo podría traerlo o no.
- El parámetro ya está en `docker-compose.yml` (servicio `reranker`), con un comentario que explica el motivo. Para reconstruir una consulta (P6) alcanza con lo que ya se registra (nombre y huella del archivo del reranker, compilación del motor) y el `docker-compose.yml` de ese momento en el repositorio.

## Adenda 2026-10-02 · Búsqueda por palabras sin tildes

La fila "Búsqueda por palabras" de la decisión y la alternativa 3.A dicen que se quitan los acentos antes de reducir las palabras a su raíz. La etapa 0 (T-004, sección 5 de `entorno.md`) mostró que así "licitación" y "licitaciones" dejan de coincidir. La definición que la reemplaza está propuesta en el ADR-0007, pendiente de aprobación del responsable. Hasta que se apruebe, este ADR no cambia.
