# ADR-0002 · Motor de IA local y modelo de generación

Estado: propuesto · Fecha: 2026-10-02 · Decidió: —

## Contexto

EVALUON necesita dos piezas para responder preguntas sobre la normativa: un programa que mantenga cargado el modelo de lenguaje en el equipo y lo atienda cuando el sistema le manda una pregunta (el "motor"), y el modelo en sí, que es un archivo de varios gigabytes. Las dos cosas corren dentro del equipo propio, sin mandar nada afuera. Hay que elegirlas ahora porque el resto del plan se apoya en ellas, y porque las mismas piezas se van a reusar con pliegos y ofertas en las features 002 a 004.

Qué se le pide al conjunto:

- **Citar sin inventar (REQ-008, P3).** El diseño previsto es que el modelo no copie el texto de la norma: solo indica QUÉ unidad sostiene cada afirmación, en un formato fijo, y el sistema inserta el texto literal desde la base. Así la exigencia de "palabra por palabra, sin tolerancia" no depende de la buena memoria del modelo. Para eso el motor tiene que poder obligar al modelo a responder en un formato estructurado.
- **Abstenerse (REQ-009, P3).** Cuando las unidades recuperadas no alcanzan, el resultado es "no determinado".
- **Español jurídico.** Normas, dictámenes y recomendaciones de auditoría argentinas.
- **Hasta 30 segundos por consulta**, sin conexión a internet (requisitos no funcionales de la spec 001).
- **Nada externo en el camino de los documentos (P4)**, levantar todo con un comando y poder mudarlo de equipo (P5), y dejar registrado qué modelo y con qué parámetros respondió (P6, REQ-012).
- **Lo mínimo que cumple (P10).** Menos de 10 documentos y pocos usuarios a la vez.

Entorno (dato a confirmar por el responsable): notebook MSI con Intel Core Ultra 9 (24 núcleos), 32 GB de RAM y GPU NVIDIA RTX 5090 de notebook con 24 GB de memoria de video [15]; Windows con WSL2, Docker Desktop 29, Python 3.12. Más adelante el sistema se muda a otro equipo.

Definiciones compartidas con los otros ADR de la feature:

- Reparto de los 24 GB de memoria de video: modelo de generación cargado y con su contexto, hasta unos 16 GB; embeddings y reranker juntos, hasta unos 4 GB; el resto es margen.
- El motor se expone como servicio HTTP dentro de la red de Docker Compose, con interfaz compatible con la API de OpenAI, para que el código no quede atado a un proveedor.
- Embeddings y reranker los decide el ADR-0003.

La constitución permitiría usar una API externa para la normativa, por ser pública (P4, fase de operación). No se evalúa esa vía: la spec exige que la consulta funcione sin conexión, y el mismo componente va a procesar pliegos y ofertas.

Todos los datos de versiones, tamaños y licencias de este documento se consultaron el 2026-10-02; las fuentes están numeradas al final. Lo que no se pudo confirmar está en "Sin verificar".

## Alternativas

### Motor

Los tres candidatos tienen imagen oficial de Docker con soporte de GPU NVIDIA, y los tres ofrecen una interfaz compatible con la API de OpenAI. Docker Desktop en Windows da acceso a la GPU a los contenedores solo con el backend WSL2, con Windows, drivers de NVIDIA y kernel de WSL2 al día [14].

#### A. Ollama

Programa que administra modelos por nombre (`ollama pull gemma4:12b`) y los sirve. Licencia MIT [1]. Imagen `ollama/ollama`; requiere NVIDIA Container Toolkit y `--gpus=all` [2]. La serie RTX 50 figura en su lista de GPU soportadas [3].

Qué se gana:

- Es el más simple de operar: catálogo propio de modelos, descarga por nombre, carga y descarga de memoria automáticas.
- Interfaz compatible con OpenAI para chat y para embeddings (`/v1/chat/completions`, `/v1/embeddings`), con salida estructurada vía `response_format` [4][5].
- Cambiar de modelo es cambiar un nombre.

Qué se pierde:

- **Trae funciones de nube** (modelos con etiqueta `:cloud`, búsqueda web). Se desactivan con `OLLAMA_NO_CLOUD=1` [6], pero cumplir P4 pasa a depender de que esa variable esté bien puesta: un modelo con etiqueta de nube mandaría el contenido afuera.
- **No tiene endpoint de reranker**: el pedido de agregarlo se cerró sin integrarse [7]. Si se elige Ollama, el reranker del ADR-0003 necesita otra tecnología.
- **Antecedentes de fallas en la salida estructurada** justo con los modelos candidatos: hay un reporte abierto de que el esquema no se respeta con Qwen 3.5 y Gemma 4 [8], y la combinación con modelos que "piensan" necesitó varias correcciones [9].
- **Valores por defecto que hay que pisar**: con menos de 24 GiB de memoria de video usa un contexto de 4.000 tokens, insuficiente para una consulta con varias unidades [10]; descarga el modelo de memoria a los 5 minutos sin uso, y la primera consulta siguiente paga la recarga [6].
- Los nombres del catálogo son etiquetas que se actualizan (la de `gemma4` se había modificado dos días antes de la consulta [16]). Para reproducir (P5, P6) hay que registrar la huella del modelo, no el nombre.

#### B. llama.cpp (`llama-server`)

El servidor del proyecto llama.cpp, que es además el motor que Ollama usa por debajo [9]. Licencia MIT [11]. Imagen `ghcr.io/ggml-org/llama.cpp:server-cuda`, con etiquetas por número de compilación (por ejemplo `server-cuda-b11176`) que permiten fijar una versión exacta [12][13].

Qué se gana:

- **No tiene ninguna función de nube.** Se le indica un archivo de modelo y lo sirve; con `--offline` no accede a la red [17]. P4 se cumple por construcción, no por configuración.
- **Salida estructurada nativa**: acepta un esquema JSON en `response_format` y restringe la generación para que la respuesta lo cumpla [17]. Es el mecanismo original, sin capa intermedia.
- **Reproducible**: el modelo es un archivo `.gguf` con huella verificable; el contexto, el uso de GPU y el "pensamiento" son parámetros explícitos del arranque (`--ctx-size`, `--reasoning-budget`) [17]. El modelo queda cargado mientras el servicio esté arriba: la memoria que ocupa es fija y previsible, lo que sirve para respetar el reparto.
- **La misma imagen puede servir embeddings y reranker** (`--embeddings`, `--rerank`, endpoint `/v1/rerank`) [17]. Le deja al ADR-0003 la opción de no sumar otra tecnología.
- Tiene endpoint `/health` para que Docker Compose sepa cuándo está listo [17].

Qué se pierde:

- No hay catálogo: hay que indicar de qué repositorio se baja el archivo (`-hf organización/modelo:cuantización`) [17] y documentarlo en el runbook.
- No publica versiones "estables": salen varias compilaciones por día [12]. Hay que fijar una y actualizarla a propósito.
- Un proceso sirve un modelo. Servir generación, embeddings y reranker son tres contenedores de la misma imagen (o el modo "router", más nuevo) [17].
- Menos material introductorio que Ollama.

#### C. vLLM

Servidor orientado a muchos usuarios simultáneos. Imagen `vllm/vllm-openai` [18].

Qué se gana: el mejor rendimiento cuando hay muchas consultas a la vez; salida estructurada con esquema JSON [19].

Qué se pierde: resuelve un problema que EVALUON no tiene (pocos usuarios; P10). Reserva de entrada un porcentaje de la memoria de video [20], lo que complica compartir la GPU con embeddings y reranker. Solo soporta Linux; en Windows funciona a través de WSL, y su guía de Docker no cubre ese caso [18][21]. Trabaja con modelos en formato sin comprimir o con otras cuantizaciones, que ocupan más que los archivos `.gguf`.

#### Descartado sin análisis detallado: Docker Model Runner

Función de Docker Desktop que sirve modelos usando llama.cpp o vLLM por debajo [22]. Ataría el entorno a Docker Desktop; el equipo de destino de la mudanza podría no tenerlo (P5).

### Modelo de generación

Se compararon los modelos abiertos vigentes que entran, o casi, en 24 GB. Todos tienen licencia Apache 2.0, que permite el uso en un organismo público sin pago ni restricciones de uso.

| Modelo | Publicación | Archivo (4 bits) | Memoria de video medida con contexto de 32.000 tokens | Contexto máximo | ¿Entra en 16 GB? |
|---|---|---|---|---|---|
| Gemma 4 12B (Google) | julio 2026 [23] | 6,98 GB, publicado por Google [24] | 8,6 GB (8.758 MiB) [25] | 256.000 [23] | Sí, con margen |
| Mistral Small 3.2 24B (Mistral) | junio 2025 [26] | 15 GB [27] | sin medición | 128.000 [27] | En el límite |
| gpt-oss 20B (OpenAI) | sin dato verificado | 14 GB [28] | sin medición | 128.000 [28] | Sí, justo |
| Gemma 4 26B-A4B (Google) | abril 2026 [29] | 15,64 GiB [25] | 17,3 GB (17.702 MiB) [25] | 256.000 [29] | No: se pasa unos 1,3 GB |
| Qwen3.8-27B (Alibaba) | agosto 2026 [30] | 18 GB [31] | 17,6 GB (18.048 MiB) [25] | 262.144 [30] | No: se pasa unos 1,6 GB |

Las mediciones de [25] son sobre una RTX 5090 de escritorio (32 GB), no de notebook; sirven para el tamaño en memoria, no para la velocidad de este equipo.

#### M1. Gemma 4 12B

Qué se gana:

- Entra con mucho margen: menos de 9 GB de los 16 reservados. Deja lugar para usar la versión de 8 bits (archivo de 12,7 GB [32]) si la de 4 bits no alcanza, sin tocar el reparto.
- Google publica el archivo ya comprimido a 4 bits, entrenado para esa compresión (QAT), sin registro previo para descargarlo [24]. El archivo viene del autor del modelo y no de un tercero, lo que simplifica justificar su origen.
- Google declara soporte para más de 35 idiomas y preentrenamiento en más de 140 [23], salida JSON estructurada e instrucciones de sistema [29].
- El "pensamiento" viene apagado salvo que se lo pida explícitamente [16], lo que ayuda con los 30 segundos.
- Es el más rápido de los densos: 145 tokens por segundo en la 5090 de escritorio [25].

Qué se pierde: es el modelo más chico de la comparación. Puede quedar corto en los casos que piden razonar sobre dos textos (REQ-019) o en decidir cuándo abstenerse (REQ-009). No hay medición pública de su desempeño en español jurídico.

#### M2. Qwen3.8-27B (o Gemma 4 26B-A4B)

Modelos del doble de tamaño, los más capaces que se pueden cargar en este equipo.

Qué se gana: más capacidad de razonamiento y de seguir instrucciones largas. Qwen declara soporte de 201 idiomas y dialectos en la serie [33]. Gemma 4 26B-A4B es además muy rápido (248 tokens por segundo en escritorio) [25].

Qué se pierde: **no entran en el reparto acordado.** Con unos 17,5 GB para generación y 4 GB para embeddings y reranker quedan unos 2,5 GB de margen, en un equipo donde Windows también usa memoria de video. Qwen "piensa" por defecto y hay que desactivarlo en cada pedido [30]; si se lo deja, gasta tiempo del presupuesto de 30 segundos. La tarjeta de Qwen3.6 informa resultados en inglés y chino, no en español [34].

#### M3. Mistral Small 3.2 24B

Qué se gana: fabricante europeo, licencia Apache 2.0 [26], sin modo de pensamiento (respuesta directa), buen seguimiento de instrucciones según su fabricante [26].

Qué se pierde: es de junio de 2025, una generación anterior a los demás. Con 15 GB de archivo más el contexto queda en el borde de los 16 GB. Su sucesor abierto, Mistral Small 4, es un modelo de 119.000 millones de parámetros y no entra en este equipo [35].

#### M4. gpt-oss 20B

Qué se gana: entra (14 GB), Apache 2.0 [28].

Qué se pierde: siempre razona antes de responder (se regula en bajo, medio o alto, no se apaga) y exige un formato de conversación propio ("harmony") [36], lo que suma una particularidad al motor. Su tarjeta no informa idiomas soportados [36].

## Decisión

Se propone:

1. **Motor: llama.cpp (`llama-server`), alternativa B**, con la imagen oficial `server-cuda` fijada a un número de compilación, expuesto solo dentro de la red de Docker Compose y consumido por su interfaz compatible con OpenAI.
2. **Modelo inicial: Gemma 4 12B, alternativa M1**, con el archivo de 4 bits publicado por Google, contexto de 16.384 tokens, pensamiento apagado, temperatura 0 y semilla fija.
3. **Modelo de contraste: Gemma 4 26B-A4B.** Se mide con el mismo conjunto de preguntas solo si M1 no alcanza las exigencias de la spec. Pasar a él requiere ajustar el reparto (ver abajo) y es una decisión del responsable. Se lo prefiere a Qwen3.8-27B como contraste porque es el que menos se pasa del reparto y, al ser de la misma familia que el modelo inicial, usa la misma configuración.

Motivo principal del motor: es el único de los tres en el que no existe un camino hacia afuera (P4), y el que deja más a la vista qué archivo y qué parámetros produjeron cada respuesta (P5, P6). Ollama es más cómodo, pero esa comodidad se paga con funciones de nube que hay que desactivar, valores por defecto que hay que corregir y fallas reportadas en la salida estructurada, que es la pieza de la que depende la cita literal. La decisión es poco costosa de revertir: como el código habla la interfaz de OpenAI, cambiar a Ollama es reemplazar un servicio en Docker Compose.

Motivo principal del modelo: es el más capaz que cumple el reparto de memoria con holgura y con archivo de origen oficial. No hay evidencia pública de cuál rinde mejor en español jurídico argentino, así que la elección no se puede cerrar por referencias: se cierra midiendo (P7). Conviene empezar por el que entra sin forzar nada y subir de tamaño solo si los números lo piden.

**Ajuste del reparto si se pasa al modelo de contraste.** Gemma 4 26B-A4B ocuparía unos 17 GB con contexto de 16.384 tokens (estimado a partir de las dos mediciones de [25], a 32.000 y a 128.000 tokens). El reparto pasaría a ser: generación hasta 18 GB, embeddings y reranker hasta 3 GB, margen 3 GB. Solo es viable si el ADR-0003 se mantiene en 3 GB.

## Consecuencias

Más fácil:

- Cumplir P4 sin depender de una opción de configuración.
- Registrar para auditoría (P6, REQ-012): nombre y huella SHA-256 del archivo del modelo, número de compilación del motor, contexto, temperatura, semilla y versión de las instrucciones. Con temperatura 0 y semilla fija, la misma consulta sobre la misma normativa debería dar la misma respuesta.
- Limitar las citas a lo recuperado: el esquema que se le pasa al motor en cada consulta puede enumerar los identificadores de las unidades recuperadas, de modo que el modelo no pueda nombrar una unidad que no se le mostró. El sistema valida igual la respuesta antes de insertar el texto literal: si una afirmación cita una unidad que no se le mostró o no trae cita, la respuesta entera se trata como "no determinado"; si la salida no cumple el formato (por ejemplo, quedó cortada), se trata como falla técnica y no como "no determinado".
- Prever la memoria: el modelo se carga al arrancar y queda fijo.

Más difícil:

- La primera puesta en marcha necesita internet una vez, para bajar la imagen y el archivo del modelo (unos 7 GB). Después funciona sin conexión. El runbook debe indicar el repositorio y la huella esperada.
- Hay que elegir y fijar una compilación de llama.cpp, y actualizarla a propósito corriendo el conjunto de preguntas (P7).
- El arranque del servicio tarda lo que tarde en cargar el modelo; la aplicación debe esperar a `/health`.
- Los parámetros propios de cada modelo (cómo se apaga el pensamiento, temperatura recomendada) deben vivir en la configuración, no en el código, para que cambiar de modelo no obligue a programar.

Riesgos y mitigación:

- **El modelo de 12B no alcanza 85 % de aciertos o 90 % de abstención.** Mitigación en orden de costo: versión de 8 bits del mismo modelo; ajustar instrucciones; modelo de contraste con ajuste del reparto. Cada paso se mide con el conjunto de preguntas.
- **La GPU no queda visible dentro del contenedor en este equipo.** La serie RTX 50 necesita CUDA 12.8 o posterior [21]; la imagen oficial se compila con CUDA 12.8.1 [13]. Primera tarea técnica: validar la GPU en Docker con el comando de prueba de Docker [14] y levantar el motor con una consulta de prueba, antes de construir nada encima.
- **Windows usa parte de los 24 GB.** Medir la memoria de video libre real con los tres modelos cargados antes de dar por bueno el reparto.

Para revertir: reemplazar el servicio del motor en Docker Compose por otro con interfaz compatible con OpenAI (Ollama con `OLLAMA_NO_CLOUD=1`, contexto y permanencia en memoria configurados), volver a correr el conjunto de preguntas y registrar el cambio en un ADR nuevo.

## Cómo se comprueba la elección

Con el conjunto de unas 30 preguntas de `evals/`, ya validado por la Comisión, y la normativa cargada. Por cada modelo candidato se mide:

| Qué se mide | Exigencia | Origen |
|---|---|---|
| Respuesta correcta que cita la unidad correcta, sobre las preguntas con respuesta | Al menos 85 % | Spec 001, calidad |
| Resultado "no determinado" sobre las preguntas sin respuesta | Al menos 90 % | Spec 001, calidad; REQ-009 |
| Texto citado idéntico al de la base | 100 % | Spec 001, calidad; REQ-008 |
| Respuestas del modelo que no cumplen el formato o nombran una unidad no recuperada (antes de la validación del sistema) | Se informa; se espera 0 | Diseño de la cita |
| Tiempo de punta a punta por consulta: mediana y máximo | Máximo de 30 segundos | Spec 001, tiempo de respuesta |
| Memoria de video ocupada con generación, embeddings y reranker cargados | Dentro del reparto | Definición compartida |
| Misma respuesta al repetir la corrida | Se informa | P6 |

Las preguntas del conjunto que tocan REQ-018 y REQ-019 (orden por categoría, régimen específico frente a marco nacional) se informan aparte: son las que más exigen al modelo.

El modelo inicial queda confirmado si cumple las tres exigencias de calidad y el tiempo. Si no, se sigue la escalera de mitigación de arriba y el responsable decide (P7).

## Qué hay que hacer para cambiar de modelo

1. Descargar el archivo `.gguf` del modelo nuevo y anotar su huella.
2. Cambiar en la configuración del servicio la referencia al archivo y sus parámetros propios (contexto, pensamiento, temperatura).
3. Reiniciar el servicio del motor.
4. Correr el conjunto de preguntas completo y comparar con la corrida anterior (P7). Una baja en las métricas requiere aprobación del responsable.
5. Registrar el cambio como actualización de este ADR.

No se toca código: la aplicación habla la interfaz de OpenAI y lee el nombre del modelo de la configuración. Las consultas ya registradas conservan el modelo con que se respondieron (REQ-012).

## Impacto en los otros ADR

- **ADR-0003 (embeddings y reranker).** `llama-server` puede servir embeddings (`/v1/embeddings`) y reranker (`/v1/rerank`) con la misma imagen, un contenedor por modelo, siempre que el modelo elegido exista en formato `.gguf`. Ollama sirve embeddings pero no reranker. La decisión de qué modelos usar y si se sirven así es del ADR-0003, que en la integración del plan adoptó esta vía: servicios `embeddings` y `reranker`, con la misma imagen y compilación que el servicio `generation`. Presupuesto: hasta 4 GB con el modelo inicial; hasta 3 GB si se pasa al modelo de contraste.
- **Lectura de documentos.** Todos los modelos comparados aceptan imágenes, pero este ADR no propone usar el modelo de generación para leer PDF escaneados. Si el ADR de lectura quiere un modelo de visión en GPU, tiene que entrar en el margen del reparto.
- **Aplicación web.** Consume un único endpoint (`/v1/chat/completions`) sin transmisión parcial de la respuesta: el sistema necesita la respuesta completa para validarla e insertar las citas antes de mostrar nada. La pantalla debe prever una espera de hasta 30 segundos. El puerto del motor no se publica fuera de la red de Docker Compose.

## Sin verificar

- **Versión vigente exacta de cada motor.** Las fuentes dieron datos distintos el mismo día: para Ollama, v0.35.0 (28-09-2026) en la página de versiones [37] y v0.33.2 (27-08-2026) en la API de GitHub [38]; para vLLM, v0.30.0 [39] y v0.29.0 (09-09-2026) [40]. Para llama.cpp, la etiqueta más reciente vista en el registro de imágenes fue `b11176` [12]. La compilación a fijar se confirma al implementar.
- **Velocidad en la RTX 5090 de notebook.** No se encontró medición para este equipo. Las cifras de [25] son de la 5090 de escritorio, que es más potente. Que la consulta entre en 30 segundos es una expectativa razonable, no un dato.
- **Calidad en español jurídico.** No se encontró ninguna comparación pública de estos modelos sobre textos jurídicos en español. Las afirmaciones de idiomas soportados son de los fabricantes.
- **Memoria de Gemma 4 12B con contexto de 16.384 tokens** y de su versión de 8 bits cargada: estimadas a partir de los tamaños de archivo y de la medición a 32.000 tokens.
- **Memoria de Mistral Small 3.2 y gpt-oss 20B cargados**: solo se verificó el tamaño de archivo. Tampoco se verificó la fecha de publicación de gpt-oss.
- **Tamaño de Mistral Small 4**: los 119.000 millones de parámetros surgen del nombre de los repositorios que lo publican en `.gguf` [35]; no se leyó la ficha del fabricante.
- **Memoria del modelo de contraste con contexto de 16.384 tokens**: estimada, no medida.
- **Estado actual del reporte [8]** sobre salida estructurada en Ollama: figura abierto, pero se abrió con una versión vieja y no consta si las versiones recientes lo corrigen.
- **Licencia de vLLM y valor por defecto de la reserva de memoria**: no se confirmaron en esta consulta.
- **Memoria de video que usa Windows** en este equipo con la pantalla activa.
- **Funcionamiento de la GPU en Docker Desktop 29 con esta notebook**: la documentación lo da por soportado [14]; hay que probarlo.
- Las páginas se leyeron mediante una herramienta que las resume; las cifras deben volver a mirarse en la fuente al fijar versiones.
- **Datos del equipo**: informados en el encargo, a confirmar por el responsable.

## Fuentes

Consultadas el 2026-10-02.

1. Ollama, repositorio y licencia: https://github.com/ollama/ollama
2. Ollama en Docker: https://docs.ollama.com/docker
3. Ollama, GPU soportadas: https://docs.ollama.com/gpu
4. Ollama, compatibilidad con la API de OpenAI: https://docs.ollama.com/api/openai-compatibility
5. Ollama, salida estructurada: https://docs.ollama.com/capabilities/structured-outputs
6. Ollama, preguntas frecuentes (funciones de nube, permanencia en memoria): https://docs.ollama.com/faq
7. Ollama, pedido de soporte de reranker, cerrado sin integrar: https://github.com/ollama/ollama/pull/7219
8. Ollama, reporte "structured output not enforced on qwen 3.5 / gemma 4": https://github.com/ollama/ollama/issues/15540
9. Ollama, salida estructurada con modelos que piensan: https://github.com/ollama/ollama/issues/10538 y https://github.com/ollama/ollama/pull/18479
10. Ollama, tamaño de contexto por defecto: https://docs.ollama.com/context-length
11. llama.cpp, repositorio y licencia: https://github.com/ggml-org/llama.cpp
12. llama.cpp, registro de imágenes de Docker: https://github.com/ggml-org/llama.cpp/pkgs/container/llama.cpp
13. llama.cpp, guía de Docker: https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md
14. Docker Desktop, soporte de GPU en Windows con WSL2: https://docs.docker.com/desktop/features/gpu/
15. NVIDIA, GeForce RTX serie 50 para notebooks: https://www.nvidia.com/en-us/geforce/laptops/50-series/
16. Ollama, catálogo y ficha de Gemma 4: https://ollama.com/library y https://ollama.com/library/gemma4
17. llama.cpp, documentación de `llama-server`: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
18. vLLM, despliegue con Docker: https://docs.vllm.ai/en/latest/deployment/docker.html
19. vLLM, salida estructurada: https://docs.vllm.ai/en/latest/features/structured_outputs.html
20. vLLM, optimización y reserva de memoria: https://docs.vllm.ai/en/latest/configuration/optimization.html
21. vLLM, instalación con GPU: https://docs.vllm.ai/en/latest/getting_started/installation/gpu.html
22. Docker Model Runner: https://docs.docker.com/ai/model-runner/
23. Google, ficha de Gemma 4 12B: https://huggingface.co/google/gemma-4-12b-it
24. Google, Gemma 4 12B en 4 bits (QAT): https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf
25. Atomic Chat, mediciones en RTX 5090 de escritorio (18-09-2026): https://atomic.chat/blog/guides/best-local-llms-for-rtx-5090
26. Mistral AI, ficha de Mistral Small 3.2: https://huggingface.co/mistralai/Mistral-Small-3.2-24B-Instruct-2506
27. Ollama, etiquetas de Mistral Small 3.2: https://ollama.com/library/mistral-small3.2/tags
28. Ollama, ficha de gpt-oss: https://ollama.com/library/gpt-oss
29. Google, anuncio de Gemma 4 (02-04-2026): https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/
30. Alibaba, ficha de Qwen3.8-27B: https://huggingface.co/Qwen/Qwen3.8-27B
31. Ollama, ficha de Qwen3.8: https://ollama.com/library/qwen3.8
32. ggml-org, Gemma 4 12B en `.gguf`: https://huggingface.co/ggml-org/gemma-4-12B-it-GGUF
33. Alibaba, ficha de Qwen3.5-27B: https://huggingface.co/Qwen/Qwen3.5-27B
34. Alibaba, ficha de Qwen3.6-27B: https://huggingface.co/Qwen/Qwen3.6-27B
35. Mistral AI, modelos disponibles: https://docs.mistral.ai/getting-started/models/models_overview/ y https://huggingface.co/unsloth/Mistral-Small-4-119B-2603-GGUF
36. OpenAI, ficha de gpt-oss-20b: https://huggingface.co/openai/gpt-oss-20b
37. Ollama, página de versiones: https://github.com/ollama/ollama/releases
38. Ollama, versiones por la API de GitHub: https://api.github.com/repos/ollama/ollama/releases
39. vLLM, página de versiones: https://github.com/vllm-project/vllm/releases
40. vLLM, versiones por la API de GitHub: https://api.github.com/repos/vllm-project/vllm/releases

## Ajustes de integración

Hechos el 2026-10-02 al integrar el plan (`specs/001-normativa/plan.md`). La decisión de motor y de modelo no cambia.

- **Nombre del servicio.** En Docker Compose el motor de generación es el servicio `generation`, el mismo nombre que usan el ADR-0005 y el plan.
- **Embeddings y reranker.** El ADR-0003 pasó a servirlos con `llama-server`, como este ADR dejaba abierto: tres contenedores de la misma imagen y compilación (`generation`, `embeddings`, `reranker`). Se actualizó el punto correspondiente de "Impacto en los otros ADR". Fijar una compilación pasa a valer para los tres servicios, y actualizarla exige correr el conjunto de preguntas completo.
- **Respuesta que no valida.** En "Consecuencias" decía que una respuesta que no valida se trata como "no determinado". Se separó en dos casos para coincidir con el ADR-0005, que distingue una falla técnica de un "no determinado": una cita inválida da "no determinado"; una salida que no cumple el formato da falla técnica. Motivo: decir "la normativa no permite responder" cuando en realidad falló el sistema sería una afirmación sin sustento (P3).
- **Marca para REQ-019.** El esquema de salida suma, por afirmación, el campo `regimes_differ`, con el que el modelo señala que el régimen específico y el marco nacional tratan el punto de manera distinta. No cambia ningún requisito sobre el motor: es un campo más del mismo esquema.
- **Comprobación de la elección.** Las medidas de "Cómo se comprueba la elección" se corren con el comando `correr_evals` y quedan en `evals/corridas/`, como define el plan. La validación de la GPU y la consulta de prueba que este ADR pide como primera tarea técnica son la etapa 0 del plan.
