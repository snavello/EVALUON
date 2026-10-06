# ADR-0041 · Lectura con visión de las páginas de lectura dudosa

Estado: propuesto · Fecha: 2026-10-06 · Decidió: —

## Contexto

La medición base de la 004 con el caso-00 dio 26 de 49 coincidencias. De los 23 desaciertos que la revisión del 2026-10-06 atribuyó a los datos, 10 son datos que el sistema no lee: un pagaré escaneado ilegible (confianza del reconocimiento de 44 %, dos intentos, `verificacion/T-155.md`), el cuadro de precios de una oferta mal leído por el reconocimiento de texto y fotos de tablas. Hoy toda página escaneada se lee con Tesseract (ADR-0004, alternativa D), en CPU y sin entender la imagen. El responsable aprobó (2026-10-06) probar la lectura con visión: que el modelo mire la imagen de la página.

Lo que ya existe y se reutiliza:

- **Criterio objetivo de lectura dudosa.** La lectura de cada documento guarda en su informe, por página, el estado que sale de la confianza promedio de las palabras (`evaluon/norms/reading/ocr.py`: legible desde 80, dudosa de 50 a 80, ilegible por debajo de 50 o con menos de 3 palabras con letras o cifras). El informe de la lectura de una oferta (`evaluon/offers/services/offers.py`) lista `low_confidence` (dudosas), `unread` (ilegibles y casi sin texto) y `without_text_unlisted` (páginas sin pasajes que no son blancas ni ilegibles). La evaluación (`assessment/sizing.py::document_pages`) hoy solo trata como "no se pudo leer" las de `unread`.
- **Lecturas nuevas que no pisan las anteriores.** `offers_reading` tiene `sequence` y es de solo inserción; la 008 ya hace una segunda lectura con la imagen preparada (ADR-0028). La evaluación usa la última lectura de cada documento.
- **Cita literal verificable (ADR-0038).** El modelo nunca escribe el texto citado: el sistema ubica lo que el modelo copió en el texto canónico del documento y muestra el recorte del canónico.
- **El original está en la base.** el contenido original del documento está guardado en la base (`offers/models.py`, campo `content`); la imagen de una página se puede volver a dibujar con pypdfium2 (el mismo que usa la lectura).
- **Archivo con visión.** El repositorio oficial `google/gemma-4-12B-it-qat-q4_0-gguf`, revisión `29d097773436b69ff9feafd636ab4cf873786537`, trae `mmproj-gemma-4-12b-it-qat-q4_0.gguf` (175.115.616 bytes, SHA-256 `cb018338a7538a9814d994bfe54644c71eb7ed54e31eae2f721e45fd3c260da7`, consultado en la API de Hugging Face el 2026-10-06). Hoy no se baja (ADR-0002). `llama-server` lo acepta con `--mmproj` y recibe imágenes en `/v1/chat/completions`.

Restricciones: todo local y sin red (P4); la cita literal sigue siendo verificable (REQ-053, ADR-0038); el sistema propone, la persona decide (P3); lo que se lee y con qué queda registrado (P6, P8); sin servicios nuevos (P10); toda medición con umbral escrito antes y dos rondas como máximo (ADR-0025).

## Alternativas

### A. Seguir con el reconocimiento de texto y mejorarlo (resolución, rotación, un tercer intento)
Se gana: nada nuevo en el entorno; es la corrección que ya propone T-155 para el pagaré. Se pierde: el segundo intento resultó peor que el primero; un manuscrito girado y un cuadro fotografiado no mejoran con más resolución; no ve estructura de tabla. Se mantiene igual como primera lectura de toda página.

### B. Un modelo de lectura de documentos aparte (motor de reconocimiento por visión específico)
Se gana: puede leer mejor que un modelo de uso general. Se pierde: otro modelo y otro servicio que dimensionar en la memoria de video y mantener (P10); sin evidencia en este proyecto de que lea mejor español manuscrito; otro archivo para verificar y registrar.

### C. El mismo Gemma 4 con su proyector de imagen: transcribir la página y guardarla como lectura nueva (propuesta)
Para cada página de lectura dudosa, el modelo recibe la imagen y devuelve su transcripción; el sistema la guarda como una lectura nueva del documento (solo inserción), con origen `vision`, y desde ahí la evaluación sigue igual: texto canónico, grupos, citas ubicadas. Se gana: ningún modelo nuevo (178 MB más de archivo), la cita sigue siendo texto ubicado en un canónico guardado y verificable contra la imagen; la lectura anterior queda; se aplica una sola vez por página y no por requisito. Se pierde: un modelo de 12B puede inventar texto donde no se lee; hay un paso más antes de evaluar; la memoria del motor de lotes sube.

### D. Que el modelo mire la imagen dentro de cada pedido de evaluación y cite desde ahí
Se gana: sin lectura intermedia. Se pierde: la cita saldría de la imagen, sin texto canónico donde ubicarla: deja de ser verificable por el sistema y se viola ADR-0038; se pagan las fichas de imagen en cada requisito; no queda un texto que la Comisión pueda leer y comparar.

## Decisión

Se propone C, con estas reglas.

1. **Cuándo.** Antes de evaluar una oferta, el sistema busca en la última lectura de cada documento las páginas de lectura dudosa, por criterio objetivo, sin criterio del modelo:
   - páginas con estado `dudosa` (`low_confidence`), `ilegible` (incluye "casi sin texto") y las de `without_text_unlisted`;
   - toda página de un documento cuyo formato es imagen (foto de una tabla o de un documento), porque ahí falla el reconocimiento.
   Hasta `ASSESSMENT_VISION_MAX_PAGES` páginas por oferta (parámetro, 40 de partida); las que pasan del tope siguen como están y quedan contadas. Una página legible nunca se manda a visión.
   Queda fuera, y se informa como límite: un cuadro leído mal con confianza alta (el reconocimiento no sabe que se equivocó). Es el punto 2 de "Puntos para el responsable" del plan.
2. **Qué modelo y qué archivo.** Gemma 4 12B, el mismo que evalúa, con `mmproj-gemma-4-12b-it-qat-q4_0.gguf` agregado a `generation_batch` (`--mmproj`). `generation` no lo lleva. Temperatura 0 y semilla fija. Cuántos tokens se gastan por imagen y a qué resolución se dibuja la página se fijan en T-160 con el caso-00 y se registran; de partida 280 tokens por imagen (valor del que habla el commit de Google en el repositorio) y 150 puntos por pulgada, a subir si la transcripción pierde texto.
3. **Qué se le pide.** Una página por pedido: transcribir literalmente el texto visible, sin corregir ni completar, con `[ilegible]` donde no se lee y las tablas como filas con las celdas separadas por ` | `, sin comentarios. Instrucciones versionadas en `prompts/vision-v1.md`.
4. **Qué se guarda.** Una lectura nueva del documento (`sequence` siguiente) con las páginas legibles de la lectura anterior tal cual y las de visión reemplazadas por su transcripción, con origen `vision` en cada pasaje; su texto canónico y su huella son propios. No cambia el esquema salvo el valor nuevo `vision` del origen del texto del pasaje (cambio de opciones, de T-160, sin otra tarea que toque el esquema a la vez). La lectura anterior no se toca.
   Una transcripción vacía o con más de 30 % de `[ilegible]` no cuenta como lectura: la página queda "no se pudo leer" como hoy.
5. **Cómo se cita.** La cita de una página leída por visión es literal contra el texto canónico de la lectura por visión: el sistema la ubica igual que cualquier otra (ADR-0038) y muestra el recorte del canónico. Es literal respecto de la transcripción, no del original, así que la pantalla la rotula "leída por visión" y muestra al lado la imagen de la página original y el enlace al archivo. El resultado lleva la marca `vision` cuando alguna cita de la oferta cae en una página de visión. La Comisión compara con el original antes de confirmar (P3).
6. **Auditoría (P6, P8).** Cada lectura por visión guarda en su informe: modelo (alias, SHA-256 del archivo), SHA-256 del proyector, compilación de `llama.cpp`, parámetros (resolución, tokens por imagen, temperatura, semilla), versión de las instrucciones, la lista de páginas, el motivo de cada una (estado y confianza del reconocimiento, formato imagen), la huella de la imagen dibujada de cada página, el pedido, la salida cruda, los tokens y los tiempos. Cada evaluación copia en su registro (`assessment_run.documents`) cuáles lecturas por visión usó. El hecho de auditoría de lectura de la 008 sale con la lectura nueva y la marca de visión. No hay tabla nueva.
7. **Memoria de video.** El proyector de 12B pesa 167 MiB; con el contexto de imagen se estima +0,3 a 0,6 GB sobre los 8.075 MiB de `generation_batch` medidos en T-148, es decir un entorno de uso de unos 11.000 MiB de 24.463. T-159 lo mide.
8. **Medición (umbral escrito antes).** En T-161, sobre el caso-00 con la misma lista esperada:
   - contradicciones: 0 (bloquea);
   - de los 10 pares que la revisión atribuyó a datos que no se leen, al menos 3 pasan a coincidir (el pagaré tiene un techo duro: puede seguir siendo ilegible aunque se lo mire);
   - ningún par que coincidía deja de coincidir por una transcripción inventada (se revisa cada transcripción de los pares que cambian de resultado contra la imagen);
   - toda cita de oferta sobre una página de visión: literal contra su canónico, 100 %;
   - tiempo de la lectura por visión: informado.
   Una ronda de ajuste de la instrucción o de la resolución si no llega; una segunda solo si la primera acerca; después, lo que falte pasa a la lista de revisión con su impacto (ADR-0025).

## Consecuencias

- Más fácil: los 10 pares de datos ilegibles tienen una vía; la cita y la evaluación no cambian de forma; todo queda en una lectura que se puede abrir y comparar con el original.
- Más difícil: un paso más antes de evaluar (unos segundos por página); `generation_batch` y `generation` dejan de tener el mismo comando (el test de T-148 se ajusta: contexto y proyector); la transcripción de un modelo de 12B es una lectura, no un hecho: una página manuscrita puede salir con errores plausibles. Por eso la marca visible, el original al lado y que la persona confirme.
- Qué no resuelve: un cuadro mal leído con confianza alta; el modelo que mira tampoco sabe si se equivoca.
- Para revertir: quitar `--mmproj` y no pedir la lectura por visión (`ASSESSMENT_VISION_MAX_PAGES=0`). Las lecturas por visión ya guardadas quedan como historia y la evaluación puede volver a la lectura anterior ignorándolas.
- Cambiar la resolución, los tokens por imagen o las instrucciones exige volver a medir (P7).

## Fuentes

- Hugging Face, API de `google/gemma-4-12B-it-qat-q4_0-gguf` en la revisión `29d097773436b69ff9feafd636ab4cf873786537` (archivos, tamaños y SHA-256), consultada el 2026-10-06: https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf
- Hugging Face, ficha de `google/gemma-4-26B-A4B-it-qat-q4_0-gguf`, que usa el mismo esquema de archivo y proyector: https://huggingface.co/google/gemma-4-26B-A4B-it-qat-q4_0-gguf
- Documentación de `llama-server` (`--mmproj`, imágenes en chat): https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md (ver ADR-0002 [17]); no se releyó en esta consulta: T-159 comprueba con la compilación fijada `server-cuda-b11347` que acepta el proyector y la imagen.
- ADR-0002, ADR-0004, ADR-0028, ADR-0037, ADR-0038; `specs/004-evaluacion-asistida/verificacion/T-155.md`.

## Sin verificar

- Que la compilación `server-cuda-b11347` acepte `--mmproj` con este proyector y resuelva las imágenes con el contexto de 32.768: T-159.
- Tokens por imagen y resolución útiles para manuscrito y cuadros: T-160.
- Cuántas páginas del caso-00 caen en el criterio: se cuenta en T-160 (el informe de lectura ya las lista).
- Que las dos fuentes de Hugging Face leídas con una herramienta que resume coincidan al byte con el archivo real: lo comprueba la huella al descargar.
