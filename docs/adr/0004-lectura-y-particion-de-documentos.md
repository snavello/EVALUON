# ADR-0004 · Lectura y partición de documentos

Estado: aceptado · Fecha: 2026-10-02 · Decidió: responsable del proyecto

## Contexto

Antes de poder citar una norma, el sistema tiene que leerla y separarla en partes con nombre propio: "artículo 14", "inciso b", "Anexo I". Si lee mal una página o corta mal un artículo, todo lo que venga después (la búsqueda, la respuesta, la cita) hereda ese error sin que nadie lo note. Este ADR decide con qué herramientas se lee cada formato, cómo se corta el texto y qué se le muestra a la persona que valida la carga para que pueda detectar los problemas.

Requisitos que esta decisión atiende, de `specs/001-normativa/spec.md`:

- **REQ-015.** Tres formatos de origen: PDF con texto (la mayoría), PDF escaneado y página web guardada. El texto que salió de reconocimiento sobre imagen queda marcado en la unidad y en el informe.
- **REQ-003.** Unidades citables con su ubicación: artículo, inciso y anexo en las normas; punto o párrafo en dictámenes y recomendaciones.
- **REQ-004.** Informe de lectura: unidades reconocidas, páginas que no se pudieron leer, texto que no se pudo ubicar.
- **REQ-011.** Aviso cuando la norma ya está incorporada.
- **REQ-008 y requisito de calidad.** El texto citado coincide palabra por palabra con el documento, sin tolerancia.

Restricciones:

- **P4.** Nada sale del equipo. Los mismos componentes de lectura se van a reusar en las features 002 a 004 con pliegos y ofertas, así que no puede haber ningún servicio externo, ni siquiera opcional, en este camino.
- **P5.** Todo se levanta con Docker y se muda a otro equipo sin pasos manuales. Las herramientas y sus modelos quedan dentro de la imagen, con versión fija.
- **P10.** Menos de 10 documentos. No se diseña para volúmenes que nadie pidió.
- **REQ-005.** Una persona valida el informe de lectura antes de que la norma se pueda consultar. El diseño se apoya en esa revisión: no necesita acertar siempre, necesita mostrar con claridad dónde dudó.
- **Memoria de video.** Está reservada para el modelo de generación (hasta unos 16 GB) y para embeddings y reranker (hasta unos 4 GB). La lectura debe correr en CPU.
- **Equipo (dato a confirmar).** Notebook MSI, Intel Core Ultra 9 de 24 núcleos, 32 GB de RAM, GPU NVIDIA RTX 5090 de notebook con 24 GB de memoria de video, Windows con WSL2, Docker Desktop 29, Python 3.12.

Un dato del corpus que condiciona el diseño. La página de Infoleg de la Disposición AFIP 297/03 muestra, en un mismo documento: cinco artículos de la disposición con la forma `ARTICULO 1° —` (sin tilde); un `ANEXO I - DISPOSICION Nº 297/03 (AFIP)` que empieza con un índice que repite los encabezados de los artículos; y dentro del anexo 64 artículos que **vuelven a numerarse desde 1**, con la forma `ARTICULO 1.- OBJETO`, agrupados en títulos y capítulos, con incisos escritos `Inciso 1)` y letras `a)`, `b)`. Es decir: "artículo 1" no identifica una unidad si no se dice dentro de qué está, y una regla ingenua tomaría el índice por artículos. (Lectura hecha con un lector automático; ver "Sin verificar".)

## Alternativas

### Parte 1 · Lectura de PDF con texto

#### A. PyMuPDF
Biblioteca sobre MuPDF, de Artifex. Versión 1.28.2 (agosto de 2026). Es la más rápida (un comparativo de julio de 2026 mide unas 180 páginas por segundo contra 18 de pdfplumber), da texto con posición, dibuja páginas como imagen y puede invocar Tesseract.

- Se gana: velocidad y una sola biblioteca para leer y dibujar.
- Se pierde: su licencia es AGPL-3.0 o licencia comercial de Artifex. La AGPL extiende la obligación de ofrecer el código fuente completo, bajo la misma licencia, a las obras mayores que usan la biblioteca, y trata el uso por red como distribución. EVALUON es una aplicación web que usan los integrantes de la Comisión. El propio Artifex sostiene que el uso interno no distribuido en general no dispara esas obligaciones, pero si un sistema web de uso interno en un organismo público queda alcanzado es una pregunta jurídica, y la respuesta condicionaría la licencia de todo EVALUON. Esto no es una opinión legal: es el motivo por el que adoptarla requeriría un dictamen del servicio jurídico o comprar la licencia comercial.
- La velocidad no pesa: con menos de 10 documentos, la diferencia es de segundos, una sola vez por documento.

#### B. pdfplumber, con pypdfium2 para dibujar páginas
pdfplumber 0.11.10 (junio de 2026, licencia MIT), construido sobre pdfminer.six (MIT). Entrega cada carácter con su posición, tamaño y fuente, y arma palabras y líneas con su recuadro. Ya trae como dependencia a pypdfium2 5.x (BSD-3-Clause y Apache-2.0), que dibuja la página como imagen: es lo que hace falta para pasarle una página escaneada al reconocimiento de texto.

- Se gana: licencias permisivas, sin obligaciones sobre el código de EVALUON; posición y tipografía de cada carácter, que sirven para ubicar encabezados y pies por su zona en la página; sin modelos ni descargas; resultado determinista (la misma entrada da siempre la misma salida).
- Se pierde: es unas diez veces más lento que PyMuPDF (irrelevante a este volumen) y no entiende diseños complejos: en documentos a dos columnas o con tablas grandes el orden de lectura puede salir mal. Las normas del corpus son texto corrido a una columna; las páginas del Boletín Oficial a varias columnas son el caso a vigilar.

#### C. Docling
Paquete de IBM (licencia MIT, versión 2.132.0 del 1 de octubre de 2026). Convierte PDF, HTML, MHTML e imágenes a un formato único, con modelos que reconocen el diseño de la página, el orden de lectura y las tablas, y admite varios motores de reconocimiento de texto. Declara ejecución local para entornos aislados, con los modelos descargados de antemano.

- Se gana: una sola herramienta para los tres formatos, y mejor manejo de páginas a varias columnas y de tablas.
- Se pierde: es mucho más pesado (modelos de diseño de página, dependencias de aprendizaje automático, imagen de Docker más grande), los modelos tienen licencias propias que hay que revisar una por una, publica versiones casi a diario, y agrega entre el PDF y el texto una capa de modelos cuyo resultado puede cambiar entre versiones. Para normas de texto corrido aporta poco; para español igual habría que configurarle Tesseract u otro motor.
- Es el candidato a evaluar en la feature 002, cuando aparezcan pliegos con tablas y planillas.

### Parte 2 · Reconocimiento de texto en PDF escaneado

#### D. Tesseract 5
Motor clásico de reconocimiento (Apache-2.0), versión 5.5.3 de julio de 2026. Corre en CPU, sin conexión, con un modelo para español (`spa`) publicado bajo Apache-2.0 en tres calidades; la más precisa es `tessdata_best`. Devuelve cada palabra con su posición y un valor de confianza.

- Se gana: no usa memoria de video; licencia permisiva; se instala dentro de la imagen de Docker; la confianza por palabra es justo lo que el informe de lectura necesita para señalar páginas dudosas; es un motor que transcribe lo que ve, no un modelo que redacta.
- Se pierde: es el más flojo con escaneos malos (torcidos, con manchas, de baja resolución) y con diseños complejos. Su documentación pide imágenes de al menos 300 puntos por pulgada y páginas derechas. En una prueba publicada sobre una factura limpia cometió 3 errores de carácter donde PaddleOCR no cometió ninguno.

#### E. PaddleOCR (o RapidOCR, que usa los mismos modelos)
PaddleOCR 3.7.0 (junio de 2026, Apache-2.0). Modelos más modernos, con un modelo para alfabeto latino que incluye el español. RapidOCR 3.9.2 (Apache-2.0) ejecuta esos modelos con un motor más liviano. Ambos corren en CPU.

- Se gana: mejor resultado en imágenes difíciles.
- Se pierde: dependencias más pesadas; los modelos se descargan en el primer uso, así que hay que incorporarlos a la imagen de Docker para trabajar sin conexión; el modelo latino es compartido entre unos 40 idiomas, no específico del español; no encontré una medición independiente sobre documentos en español que justifique el costo adicional.

#### F. Motores basados en modelos de visión y lenguaje (Surya 2, olmOCR, GraniteDocling y similares)
Son los de mejor puntaje en las comparativas de 2026. Se descartan por tres motivos:

- Necesitan GPU para ser prácticos, y la memoria de video ya está asignada.
- Son modelos que generan texto. Un estudio de 2026 que los compara con motores clásicos documenta errores que los clásicos no tienen (repeticiones, texto fuera del documento) y muestra que, ante un texto alterado, se alejan de lo que la imagen dice más que los clásicos: tienden a escribir lo esperable en lugar de lo que está impreso. Para un sistema cuya regla es la cita palabra por palabra, es el peor tipo de error: un texto fluido, verosímil y distinto del original.
- En el caso de Surya, los pesos del modelo tienen una licencia que solo permite uso gratuito para investigación, uso personal y empresas de menos de 5 millones de dólares de facturación o financiamiento; no contempla el caso de un organismo público.

#### G. OCRmyPDF
Herramienta (MPL-2.0, versión 17.13.0) que envuelve a Tesseract: endereza la página, la limpia y devuelve un PDF con capa de texto.

- Se gana: enderezado y limpieza resueltos.
- Se pierde: agrega una dependencia y un PDF intermedio, y deja menos a mano la confianza por palabra. Queda como recurso si los escaneos reales llegan torcidos.

### Parte 3 · Lectura de página web guardada

#### H. BeautifulSoup con lxml, y reglas por sitio de origen
BeautifulSoup 4.15.0 (MIT) y lxml 6.1.3 (BSD-3-Clause). Se recorre el documento en orden, se descartan los elementos que no son texto de la norma (menús, scripts, estilos, pie del sitio) con reglas explícitas, y se detecta la codificación de caracteres.

- Se gana: control total sobre qué se descarta; tolera el HTML antiguo de Infoleg; determinista.
- Se pierde: hay que escribir una regla por sitio (Infoleg, argentina.gob.ar, Boletín Oficial) y mantenerla si el sitio cambia de diseño.

#### I. trafilatura
Biblioteca (Apache-2.0 desde la versión 1.8.0; versión actual 2.2.0) que extrae sola el "contenido principal" de una página.

- Se gana: no hay que escribir reglas por sitio.
- Se pierde: decide con heurísticas qué es contenido y qué es ruido. Si descarta un anexo o una tabla, el texto se pierde sin aviso. En este sistema, perder texto sin avisar es más grave que conservar ruido.

### Parte 4 · Partición en unidades citables

#### J. Reglas y expresiones regulares
Un conjunto de reglas reconoce los encabezados habituales al comienzo de una línea y corta ahí.

- Se gana: es determinista y se puede probar con una tabla de casos; cada unidad es un recorte exacto del texto leído, así que la cita literal queda garantizada por construcción; se puede explicar por qué cortó donde cortó (P6); no usa GPU ni depende del motor de IA.
- Se pierde: no entiende formatos que nadie previó. Un dictamen sin numeración, o un "ARTICULO" mal leído por el reconocimiento de texto, quedan sin ubicar. Cada forma nueva exige agregar una regla, y eso es una tarea de desarrollo.

#### K. Partición con el modelo de lenguaje local
Se le entrega el documento al modelo y se le pide que identifique las unidades.

- Se gana: flexibilidad ante formatos imprevistos, en especial dictámenes y recomendaciones, que no siguen una forma fija.
- Se pierde: no es determinista (dos cargas del mismo documento pueden dar cortes distintos); una norma de 64 artículos no entra cómoda en una sola pasada; si el modelo devuelve el texto de las unidades puede alterarlo, lo que rompe la cita literal; obliga a registrar instrucciones, modelo y parámetros de cada carga (P6) y a sumar una evaluación propia (P7); y ata la carga de documentos al motor que decide el ADR-0002.

#### L. Combinación: reglas primero, modelo solo para lo que quedó sin ubicar
Las reglas cortan todo lo que reconocen. El modelo interviene solo sobre los tramos sin ubicar y propone cortes, que la persona ve marcados en el informe.

- Se gana: la flexibilidad de K acotada a donde hace falta.
- Se pierde: dos mecanismos para mantener y probar. Con menos de 10 documentos conocidos de antemano, no hay hoy evidencia de que haga falta.
- Qué se le pediría al modelo, si se adoptara: recibe las líneas numeradas del tramo sin ubicar y devuelve solo una lista de cortes (número de línea donde empieza cada unidad, tipo y etiqueta), en formato estructurado y con temperatura cero. **Nunca devuelve texto**: el texto de la unidad se recorta siempre del documento leído. Un corte que no cae en un comienzo de línea se descarta. Las unidades así creadas llevan la marca "corte propuesto por el modelo" hasta que la persona valida.

## Decisión

Se propone: **B + D + H + J**. Todo corre en CPU, sin GPU y sin conexión.

1. **PDF con texto:** pdfplumber, con pypdfium2 para dibujar páginas.
2. **PDF escaneado:** Tesseract 5 con el modelo de español `tessdata_best`, sobre páginas dibujadas a 300 puntos por pulgada.
3. **Página web guardada:** BeautifulSoup con lxml y reglas por sitio de origen.
4. **Partición:** reglas, con el informe de lectura y la validación humana (REQ-005) como red de seguridad. La alternativa L queda documentada como paso siguiente, con una condición concreta para activarla (ver "Consecuencias").

Motivo principal: en este sistema, el error más caro no es leer un poco peor sino entregar texto que parece literal y no lo es. Las cuatro piezas elegidas transcriben y recortan; ninguna redacta. Son deterministas, de licencia permisiva (MIT, BSD, Apache-2.0), caben en una imagen de Docker sin descargas en ejecución y no compiten por la memoria de video.

Este ADR decide la partición de los documentos del marco regulatorio. La lectura (puntos 1 a 3) es la parte que se reutiliza en las features 002 a 004; cómo se parten pliegos y ofertas se decide en esas features.

### Cómo se lee

1. **Formato.** Se determina por el contenido del archivo, no por su extensión.
2. **Cada página de un PDF** se clasifica antes de leerla:
   - *Con texto:* tiene capa de texto utilizable. Se lee con pdfplumber. Origen: texto del PDF.
   - *Escaneada:* no tiene capa de texto, o una imagen cubre casi toda la página. Se reconoce con Tesseract. Origen: reconocimiento sobre imagen. Esto incluye los escaneos que ya traen una capa de texto oculta puesta por el escáner: ese texto también salió de un reconocimiento, de calidad desconocida, así que se vuelve a reconocer y se marca como tal.
   - *Con texto inservible:* la capa de texto existe pero trae caracteres de reemplazo o códigos sin letra por encima de un umbral. Se trata como escaneada.
   - *En blanco:* sin texto y sin tinta. Se informa, no cuenta como ilegible.
3. **Estado de lectura de cada página reconocida**, según la confianza promedio de sus palabras: legible, dudosa o ilegible. Valores de partida, a calibrar con los escaneos reales del corpus: legible desde 80, dudosa entre 50 y 80, ilegible por debajo de 50 o con casi ninguna palabra reconocida. Una página ilegible no aporta texto a las unidades y figura en el informe (REQ-004).
4. **Página web:** se detecta la codificación, se descartan scripts, estilos y la navegación del sitio, y se recorren los bloques de texto en el orden del documento. Una página web no tiene páginas: la ubicación es el orden del bloque.
5. **Resultado común a los tres formatos:** la *lectura* del documento, una lista de páginas, cada una con sus líneas; cada línea con su texto, su posición en la página, su origen y, si vino de reconocimiento, su confianza. La lectura se guarda, junto con las versiones de las herramientas y del modelo de español: permite volver a partir sin volver a leer y reconstruir cómo se obtuvo cada texto (P6).

### Encabezados y pies que se descartan

- En PDF: líneas en la franja superior o inferior de la página que se repiten en la mayoría de las páginas (ignorando los números, para atrapar "Página 3 de 40"), más formas conocidas: encabezado del Boletín Oficial, dirección web y fecha que agrega el navegador al imprimir, leyendas de Infoleg.
- En web: lo que queda fuera del cuerpo de la norma según la regla del sitio.
- Lo descartado no se borra de la lectura: se excluye de las unidades y se lista en el informe, para que la persona vea que no se fue nada normativo.

### Texto literal

El texto de una unidad es un recorte del *texto canónico* del documento, que se obtiene de la lectura con cinco operaciones fijas y ninguna más:

1. Normalización Unicode NFC. No se usa NFKC, porque convertiría `º` en `o`.
2. Las ligaduras tipográficas (`ﬁ`, `ﬂ`) se separan en sus letras; los espacios duros pasan a espacio común; los guiones opcionales invisibles se quitan.
3. Los saltos de línea dentro de un párrafo se reemplazan por un espacio.
4. Una palabra cortada por guion al final de la línea se une (`contra-` + `tación` → `contratación`) solo si la línea siguiente empieza en minúscula. Cada unión se cuenta y se lista en el informe, porque puede equivocarse con palabras compuestas.
5. Los espacios repetidos se reducen a uno.

No se corrige ortografía, no se agregan ni quitan tildes, no se cambian mayúsculas. "Palabra por palabra" significa: la misma secuencia de palabras, con los mismos signos, después de estas cinco operaciones. La verificación de cita literal de tests y evals debe usar esta misma definición.

### Cómo se parte

Las reglas trabajan sobre las líneas del texto canónico. Un encabezado solo se reconoce al comienzo de una línea.

| Elemento | Formas que se reconocen | Qué produce |
|---|---|---|
| Artículo | `ARTÍCULO 1°.-`, `ARTICULO 1° —`, `ARTICULO 1.- OBJETO`, `Art. 2º`, `Artículo 14 bis`; con o sin tilde, con `°`, `º` u `o`, con o sin epígrafe | Unidad `articulo` |
| Inciso | `a)`, `1)`, `1.`, `Inciso 1)`, `inc. a)` y un segundo nivel dentro del inciso | Unidad `inciso`, hija del artículo |
| Anexo | `ANEXO`, `ANEXO I`, `ANEXO A`, con o sin título a continuación | Unidad `anexo`; contiene sus propios artículos |
| Título, capítulo, sección | `TÍTULO I`, `CAPÍTULO II`, `SECCIÓN 1ª` | No son unidades: pasan a la ruta de las unidades que contienen |
| Visto y considerandos | `VISTO`, `CONSIDERANDO:`, párrafos que empiezan con `Que` | Unidad `considerando`, una por párrafo |
| Índice | Encabezados seguidos sin texto entre ellos | Se excluye de las unidades y se informa |
| Cierre y firma | Fórmula de forma después del último artículo, firmas | Queda dentro del último artículo o se informa como no ubicado |
| Dictamen o recomendación | Puntos numerados (`I.`, `1.`, `1.1.`, `2.3`); si no hay numeración, párrafos | Unidad `punto` o `parrafo`, numerada por orden si no trae número |

Tres controles evitan los cortes falsos más comunes:

- **Secuencia.** Dentro de un mismo contenedor (la norma o un anexo), un encabezado de artículo se acepta si continúa la numeración. Así no se confunde una línea que empieza con "Artículo 5° de la Ley..." en medio de un párrafo, ni el artículo que una norma modificatoria transcribe entre comillas (`Sustitúyese el artículo 14 por el siguiente: "ARTICULO 14.- ..."`), que queda dentro de la unidad que lo transcribe.
- **Saltos y repeticiones.** Si falta un número o aparece dos veces, se informa.
- **Cobertura.** Todo carácter del texto canónico termina en una unidad, en la lista de descartados o en la lista de no ubicados. La suma tiene que dar el total; nada se pierde en silencio.

El artículo es la unidad base y su texto incluye completos sus incisos. Cada inciso existe además como unidad hija, cuyo texto es un recorte del texto del artículo. Son unidades base todas las que no son `inciso`. Un anexo que contiene artículos tiene como texto propio solo su encabezado y lo que haya antes del primer artículo; un anexo sin artículos tiene todo su texto. El control de cobertura cuenta cada carácter una vez, en su unidad base.

### Qué lleva cada unidad

| Campo | Contenido | Por qué |
|---|---|---|
| `reading` | Lectura a la que pertenece; la lectura pertenece a un documento (el archivo cargado) | Definición compartida. Una relectura crea una lectura nueva sin tocar las unidades de la anterior |
| `unit_type` | `articulo`, `inciso`, `anexo`, `considerando`, `punto`, `parrafo` | Definición compartida. `considerando` se agrega para no mezclar fundamentos con texto dispositivo |
| `label` | Etiqueta como figura en el documento: "ARTICULO 14.- GARANTIAS" | Definición compartida |
| `number` | Número normalizado: `14`, `14 bis`, `b`, `I` | REQ-010, búsqueda por número de artículo |
| `parent` | Unidad que la contiene | Agregado. Sin esto "artículo 1" es ambiguo: la Disp. 297/03 tiene uno en la disposición y otro en el Anexo I |
| `key` | Clave estable, única dentro de la lectura, armada con la cadena de unidades que la contienen: `art-1`, `anexo-i/art-14/inc-1`, `considerando-3`. Títulos y capítulos no entran | Agregado en la integración. Es lo que usan las relaciones, los comandos y el conjunto de preguntas |
| `path` | Ruta legible: "Anexo I › Título II › Capítulo I › Artículo 14 › Inciso 1" | Agregado. Es lo que se muestra en la cita |
| `page_start`, `page_end` | Páginas donde empieza y termina; vacío en páginas web | Definición compartida (ubicación). Un artículo puede ocupar más de una página |
| `order` | Posición en el documento, creciente | Definición compartida (ubicación) |
| `char_start`, `char_end` | Posición del recorte dentro del texto canónico | Agregado. Permite comprobar con una operación que el texto es literal |
| `text` | Texto literal | Definición compartida |
| `text_origin` | `pdf_text`, `ocr` o `web` | Definición compartida, REQ-015. Si alguna línea de la unidad vino de reconocimiento, la unidad es `ocr` |
| `ocr_confidence_min`, `ocr_confidence_avg` | Confianza mínima y promedio de sus palabras; vacíos si no es `ocr` | Agregado. REQ-004 y REQ-015: permite ordenar el informe por lo más dudoso |

### Qué contiene el informe de lectura (REQ-004)

Se guarda como datos estructurados y se entrega además como texto legible, porque esta feature no tiene pantalla de carga. Empieza por lo que requiere atención.

1. **Requiere atención.** Lista corta, en lenguaje llano, de todo lo que sigue que no esté en orden.
2. **Documento.** Nombre del archivo, huella digital, formato detectado, cantidad de páginas, fecha, versiones de las herramientas y del modelo de español, versión de las reglas de partición.
3. **Páginas.** Por cada una: origen del texto, estado (legible, dudosa, ilegible, en blanco), cantidad de caracteres y, si hubo reconocimiento, confianza promedio. Aparte, la lista de páginas ilegibles y la de dudosas.
4. **Unidades reconocidas.** Cantidad por tipo y por contenedor (por ejemplo, "Disposición: 5 artículos; Anexo I: 64 artículos"), primer y último número, saltos y repeticiones en la numeración.
5. **No ubicado.** Cada tramo de texto que no entró en ninguna unidad, con su página y sus primeras palabras.
6. **Descartado.** Encabezados, pies e índices excluidos: cuántas líneas y un ejemplo de cada forma.
7. **Uniones de palabras cortadas.** Cuántas y cuáles.
8. **Reconocimiento sobre imagen.** Cuántas unidades tienen ese origen, y las palabras de menor confianza con su página, para compararlas con el original.
9. **Control de cobertura.** Caracteres en unidades, descartados y no ubicados, y que la suma coincide con el total leído.
10. **Posibles duplicados** (ver abajo).

### Cómo se detecta un duplicado (REQ-011)

Tres comprobaciones, de la más segura a la más amplia:

1. **Mismo archivo.** Huella SHA-256 del archivo original. Si coincide con uno ya incorporado, se avisa y no se incorpora.
2. **Mismo texto, distinto archivo.** Huella SHA-256 del texto canónico. Atrapa el mismo PDF descargado dos veces con diferencias internas. Se avisa y no se incorpora sin una confirmación expresa, igual que en la comprobación siguiente.
3. **Misma norma.** Coinciden tipo, número, año y organismo emisor (datos de REQ-001) con una norma ya incorporada. Se avisa y no se incorpora sin una confirmación expresa de la persona, que indica si es otro formato o una versión de la misma norma.

No se propone comparación por parecido de textos: ningún requisito la pide (P10).

### Cómo se prueba

- **REQ-015, la misma norma en tres formatos.** Se toma una norma del corpus disponible como PDF con texto y como página web, y se le suma un escaneo. Si no hay un escaneo real, se fabrica uno dibujando el PDF como imágenes; es más limpio que un escaneo de verdad, así que mide el caso fácil, y hay que sumar un escaneo real apenas el corpus tenga uno. Se exige: en los tres casos, la misma lista de unidades (tipo, número y contenedor); entre PDF con texto y web, la misma secuencia de palabras en cada artículo; en el escaneado, todas las unidades con origen `ocr` y el informe diciéndolo. Además se mide y se informa qué proporción de palabras del escaneado coincide con el PDF con texto. Para que la comparación valga, los tres archivos tienen que ser el mismo texto: el original publicado, no un texto actualizado.
- **REQ-003.** Para la Disp. 297/03 se escribe a mano la tabla esperada (contenedor, número, página de inicio) y se compara con lo que el sistema produce, incluido que el artículo 1 de la disposición y el artículo 1 del Anexo I son dos unidades distintas y que el índice no produce unidades.
- **REQ-004.** Un PDF al que se le inserta una página ilegible (una imagen de ruido): el informe debe señalar esa página y ninguna otra.
- **REQ-011.** Cargar dos veces el mismo archivo: un aviso, un solo documento. Cargar la misma norma en otro formato: aviso de "misma norma".
- **Reglas.** Una tabla de encabezados reales, con sus variantes, y el resultado esperado de cada uno; más los casos trampa (cita a un artículo en medio de un párrafo, artículo transcripto entre comillas, índice).
- **Propiedades que se cumplen siempre.** El texto de cada unidad es igual al recorte del texto canónico entre sus posiciones; la cobertura suma el total; el orden es creciente.
- **Sin conexión.** La lectura de los tres formatos se ejecuta en un contenedor sin red.

## Consecuencias

Más fácil:

- La cita literal se puede comprobar de forma mecánica, sin depender de la IA.
- No hay pregunta de licencias: todas las piezas son MIT, BSD o Apache-2.0.
- La carga de normas no depende del motor de IA ni usa memoria de video.
- Pasar a operación no cambia nada en la lectura (P4).

Más difícil:

- Un formato que las reglas no reconocen exige una tarea de desarrollo. Mientras tanto, la norma queda sin validar y no se puede consultar. Con un corpus de menos de 10 documentos conocidos, las reglas se ajustan contra esos documentos durante la construcción.
- **Condición para pasar a la alternativa L:** si, con el corpus real cargado, queda algún documento con tramos sin ubicar que no se resuelven agregando una regla razonable (lo esperable es que ocurra con dictámenes o recomendaciones), se propone L en un ADR que reemplace a este en la parte 4. Requeriría que el motor del ADR-0002 pueda devolver salida estructurada.
- Tesseract puede no alcanzar con escaneos malos. La lectura queda detrás de una sola función por formato, de modo que cambiar a PaddleOCR o RapidOCR (alternativa E) no toca la partición ni lo que viene después.
- Las reglas por sitio web se rompen si el sitio cambia su diseño. Afecta solo a cargas nuevas; se detecta en el informe porque cae la cantidad de unidades o aparece texto de navegación como no ubicado.
- Páginas del Boletín Oficial a varias columnas pueden leerse en mal orden. Se detecta por saltos de numeración en el informe. Si aparece, es el caso para evaluar Docling.

Cuestiones que este ADR deja a la vista y no resuelve:

- **Texto mal reconocido.** Si Tesseract lee mal una palabra, la unidad no coincide con el documento impreso. Ningún requisito pide corregir a mano el texto de una unidad, y la spec dice que el sistema no redacta textos. Por eso el diseño no incluye corrección manual: la persona ve las palabras dudosas en el informe y decide si valida la norma, con su marca de reconocimiento, o no la valida y consigue una fuente mejor.
- **Considerandos.** La spec no los nombra entre las unidades citables. Se propone guardarlos con tipo propio para no perder texto y para que una respuesta nunca presente un fundamento como si fuera una disposición. Si se citan o no, es una definición del responsable. *Resuelta por el responsable: son unidades citables; se citan como contexto, identificados como considerando y después del articulado.*
- **REQ-011 frente a la prueba de REQ-015.** La prueba de REQ-015 carga la misma norma en tres formatos; REQ-011 pide avisar y no duplicar. La tercera comprobación de duplicados (aviso con confirmación) es la forma propuesta de conciliarlos.
- **Qué es una "página web guardada".** Un navegador puede guardar una página como un archivo `.html` solo, como un `.html` con una carpeta de imágenes, o como un archivo único `.mhtml`. Para conservar el original y devolverlo igual (REQ-002) tiene que ser un solo archivo. Se propone aceptar el `.html` solo, que alcanza para el texto, y sumar `.mhtml` únicamente si es como el responsable de normativa guarda las páginas. *Resuelta en la spec: se acepta un archivo `.html`.*
- **Mostrar el original de una página web.** Una página guardada puede traer scripts. Al mostrar el original (REQ-002, REQ-013), la aplicación web no debe ejecutarlos. Es una definición del ADR de la aplicación web.

Para revertir: reemplazar una herramienta de lectura o las reglas de partición obliga a volver a leer los documentos, y las unidades pueden cambiar. Como las consultas registradas referencian unidades (P6, P8), una relectura debe crear una lectura nueva del documento y pasar otra vez por la validación (REQ-005), sin pisar la anterior.

## Fuentes

Consultadas el 2026-10-02.

Lectura de PDF:
- PyMuPDF en PyPI (versión, licencia): https://pypi.org/project/PyMuPDF/
- Artifex, "Open Source All The Way Down: PyMuPDF4LLM Goes Fully AGPL": https://pymupdf.io/blog/open-source-all-the-way-down-pymupdf4llm-goes-fully-agpl
- Resumen de la licencia AGPL-3.0: https://choosealicense.com/licenses/agpl-3.0/
- pdfplumber en PyPI: https://pypi.org/project/pdfplumber/
- pdfplumber, repositorio y dependencias: https://github.com/jsvine/pdfplumber y https://raw.githubusercontent.com/jsvine/pdfplumber/stable/requirements.txt
- pdfminer.six en PyPI: https://pypi.org/project/pdfminer.six/
- pypdfium2 en PyPI: https://pypi.org/project/pypdfium2/
- Comparativo PyMuPDF y pdfplumber (publicado por un proveedor de una herramienta competidora; tomarlo con esa reserva): https://pdfmux.com/blog/pymupdf-vs-pdfplumber/
- Docling en PyPI: https://pypi.org/project/docling/
- Docling, repositorio: https://github.com/docling-project/docling
- Docling, uso sin conexión: https://docling-project.github.io/docling/usage/advanced_options/
- Docling, formatos admitidos: https://docling-project.github.io/docling/usage/supported_formats/

Reconocimiento de texto:
- Tesseract, repositorio (licencia, formatos de salida): https://github.com/tesseract-ocr/tesseract
- Tesseract, notas de versión (fechas): https://tesseract-ocr.github.io/tessdoc/ReleaseNotes.html
- Tesseract, modelos de idioma: https://tesseract-ocr.github.io/tessdoc/Data-Files.html
- Tesseract, modelos `tessdata_best` (licencia, español): https://github.com/tesseract-ocr/tessdata_best
- Tesseract, cómo mejorar la calidad (300 puntos por pulgada, enderezado): https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html
- pytesseract en PyPI: https://pypi.org/project/pytesseract/
- PaddleOCR en PyPI: https://pypi.org/project/paddleocr/
- PaddleOCR, modelo latino de PP-OCRv5: https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html
- RapidOCR en PyPI: https://pypi.org/project/rapidocr/
- Surya, repositorio (licencia de los pesos): https://github.com/datalab-to/surya
- OCRmyPDF en PyPI: https://pypi.org/project/ocrmypdf/
- Prueba de Tesseract y PaddleOCR sobre una factura limpia (un solo documento, en inglés): https://www.codesota.com/ocr/paddleocr-vs-tesseract
- Comparativa de ocho motores en cinco idiomas, sin español y sin Tesseract: https://voiceping.net/en/blog/research-multilingual-ocr-gpu-benchmark-2026/
- "Reading or Guessing? Visual Grounding Failures of Vision-Language Models for OCR in Ancient Greek and Arabic Editions": https://arxiv.org/html/2605.27750v2
- Análisis de motores de reconocimiento clásicos (debilidades de Tesseract): https://intuitionlabs.ai/articles/non-llm-ocr-technologies

Página web:
- BeautifulSoup en PyPI: https://pypi.org/project/beautifulsoup4/
- lxml en PyPI: https://pypi.org/project/lxml/
- trafilatura en PyPI: https://pypi.org/project/trafilatura/

Forma de las normas:
- Disposición AFIP 297/2003 en Infoleg: https://servicios.infoleg.gob.ar/infolegInternet/anexos/85000-89999/86154/norma.htm
- Disposición AFIP 297/2003 en argentina.gob.ar: https://www.argentina.gob.ar/normativa/nacional/norma-86154/texto

## Sin verificar

- **Calidad de Tesseract en español sobre escaneos de normas.** No encontré una medición independiente y reciente en español. Las comparativas halladas son en otros idiomas o sobre un único documento. La recomendación se apoya en sus propiedades (CPU, licencia, confianza por palabra, no genera texto) y no en un puntaje. La primera medición real sale de la prueba de REQ-015.
- **Tiempos.** No medí cuánto tarda la lectura ni el reconocimiento en el equipo. Las cifras de velocidad citadas son de un tercero con interés comercial.
- **Estructura de la Disp. 297/03.** La leí a través de un lector automático que resume la página, y la página llegó cortada. Dos lecturas no coincidieron en un detalle (si los artículos de la disposición llevan epígrafe). Lo firme: hay índice, el anexo vuelve a numerar desde 1, y conviven las formas `ARTICULO 1° —` y `ARTICULO 1.-`. Todo debe confirmarse contra el archivo que entre a `corpus/normativa/`, que hoy está vacío.
- **Encabezados y pies del Boletín Oficial y de Infoleg en PDF, y estructura interna de sus páginas web.** No tuve documentos reales a la vista. Las reglas se escriben contra los archivos del corpus.
- **Codificación de caracteres de las páginas de Infoleg.** No la pude comprobar; por eso el diseño la detecta en lugar de suponerla.
- **Alcance de la AGPL para una aplicación web de uso interno en un organismo público.** No pude consultar el texto completo de la licencia en gnu.org; usé un resumen y la explicación del propio Artifex. No es una opinión legal.
- **Versión de Tesseract que instala la imagen base de Docker y qué modelo de español trae.** La documentación de Tesseract dice que las distribuciones de Linux incluyen `tessdata_fast`; no pude ver el paquete de Debian. Por eso se propone incorporar `spa.traineddata` de `tessdata_best` a la imagen, fijado por versión y con su suma de comprobación.
- **Licencias de los modelos de Docling y cuál es su motor de reconocimiento por defecto.** El repositorio remite a la licencia de cada modelo; no las revisé una por una.
- **Umbrales de confianza (80 y 50) y de página "con texto inservible".** Son valores de partida propuestos por mí, sin medición detrás.
- **El equipo.** Las características de la notebook son un dato a confirmar.

## Ajustes de integración

Hechos el 2026-10-02 al integrar el plan (`specs/001-normativa/plan.md`). Las herramientas elegidas, las reglas de partición y la definición de texto literal no cambian.

- **A qué pertenece una unidad.** En "Qué lleva cada unidad", el campo `document` pasó a ser `reading`. El plan guarda cuatro niveles: norma, documento (cada archivo cargado), lectura (cada vez que se leyó y partió) y unidad. Es lo que este ADR ya pedía en "Para revertir": una relectura crea una lectura nueva y pasa otra vez por la validación, sin pisar la anterior. La relectura se hace con el comando `releer_norma`.
- **Identificación de la unidad.** Se agregó el campo `key`. `parent` y `path` resuelven la ambigüedad de "artículo 1" para mostrar; `key` la resuelve para las relaciones entre unidades (REQ-006), que tienen que seguir valiendo si el documento se vuelve a leer.
- **Confianza del reconocimiento.** `ocr_confidence` se separó en `ocr_confidence_min` y `ocr_confidence_avg`, que es lo que su descripción ya decía.
- **Unidades anidadas.** Se precisó qué es una unidad base y cuál es el texto propio de un anexo que contiene artículos. El plan indexa y cita solo unidades base; los incisos sirven para relaciones y para la búsqueda directa. Así el mismo texto no aparece dos veces en una respuesta y el control de cobertura suma una sola vez cada carácter.
- **Duplicados.** La segunda comprobación (mismo texto en otro archivo) decía "se avisa y no se incorpora". La spec ahora dice que la misma norma en otro archivo se incorpora con confirmación expresa (REQ-011), así que pasó a pedir confirmación, como la tercera.
- **Informe de lectura.** El texto del informe lista además las unidades con su `key`, porque es el dato que la persona necesita para registrar una relación entre unidades. Al validar una lectura nueva de un documento ya validado, el informe avisa si alguna relación registrada quedó sin unidad.
- **Dudas resueltas.** Considerandos y formato de la página web guardada: resueltas en la spec; se anotó en cada una. Mostrar el original de una página web sin ejecutar scripts: lo define el ADR-0005. La cuestión de REQ-011 frente a la prueba de REQ-015 queda resuelta con la confirmación expresa y con la regla del plan de un solo documento en uso por versión de la norma.
- **Cita literal.** El plan adopta la definición de "palabra por palabra" de este ADR como la única del proyecto, y la comprueba comparando el texto de cada cita con el recorte del texto canónico entre `char_start` y `char_end`.
