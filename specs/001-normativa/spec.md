# Spec 001 · Normativa consultable con cita

Estado: borrador · Fecha: 2026-10-02 · Aprobó: —

## Problema

El marco regulatorio de compras está repartido en documentos de distinto tipo y peso: la Disposición AFIP 297/03 y sus modificatorias, otra normativa aplicable, la normativa nacional que funciona como marco, dictámenes legales y recomendaciones de auditoría. Para revisar un pliego o evaluar una oferta hay que saber qué texto está vigente, cuál prevalece y poder citarlo con precisión.

Rige el régimen específico. La normativa nacional es marco: se aplica lo específico.

Todo lo que EVALUON haga después se apoya en esto. La revisión de pliegos y la evaluación de ofertas muestran, en cada conclusión, la norma que la sostiene. Sin una base de normas confiable y citable, esas conclusiones no tienen fundamento que mostrar.

Esta feature construye esa base: las normas cargadas, con sus versiones, partidas en unidades que se pueden citar, y una pantalla de consulta que siempre devuelve la fuente. La pantalla es también la primera oportunidad de que la Comisión use el sistema y opine sobre él.

## Documentos del marco regulatorio

En esta spec, "norma" abarca todos los documentos del marco regulatorio. Cada uno pertenece a una categoría:

| Categoría | Qué incluye | Cómo se usa |
|---|---|---|
| Régimen específico | Disposición AFIP 297/03 y sus modificatorias | Es lo que se aplica. Va primero |
| Otra normativa aplicable | Normas puntuales que alcanzan a las compras | Se aplica en lo que trata. Va después del régimen específico |
| Marco nacional | Normativa nacional de contrataciones | Marco de referencia. No desplaza al régimen específico |
| Dictamen legal | Opiniones del servicio jurídico | Criterio de interpretación. Acompaña a la norma, no la reemplaza |
| Recomendación de auditoría | Observaciones y recomendaciones de auditoría | Criterio de control. Acompaña a la norma, no la reemplaza |

## Usuarios y escenarios

- **Integrante de la Comisión Evaluadora:** consulta la normativa desde una pantalla. Usuario con rol de lectura.
- **Responsable de normativa:** carga las normas y valida que quedaron bien. Usuario con rol de lectura y escritura.

**Escenario 1 · Incorporar una norma.** Como responsable de normativa, cuando se suma una norma al sistema, necesito cargar el documento con sus datos y revisar un informe de lo que el sistema leyó, para confirmar que quedó completa antes de que se use.

**Escenario 2 · Consultar.** Como integrante de la Comisión, cuando tengo una duda sobre qué exige la normativa, necesito escribir mi pregunta en una pantalla y recibir una respuesta con el artículo exacto que la respalda, para poder verificarla yo mismo.

**Escenario 3 · Una norma cambia.** Como responsable de normativa, cuando una norma es modificada o derogada, necesito registrar el cambio sin perder el texto anterior, para que las evaluaciones hechas con la versión vieja sigan siendo explicables.

**Escenario 4 · No hay respuesta.** Como integrante de la Comisión, cuando pregunto algo que la normativa cargada no trata, necesito que el sistema lo diga, para no tomar como cierta una respuesta sin sustento.

## Requisitos funcionales

| ID | Requisito | Origen normativo |
|---|---|---|
| REQ-001 | El sistema debe incorporar una norma a partir de su documento, registrando tipo, número, organismo emisor, título, fecha de publicación, fecha de vigencia y fuente de donde se obtuvo | — |
| REQ-002 | El sistema debe conservar el documento original de cada norma y permitir verlo | — |
| REQ-003 | El sistema debe dividir cada documento en unidades citables, cada una con su ubicación: artículo, inciso o anexo en las normas; punto o párrafo en dictámenes y recomendaciones | — |
| REQ-004 | El sistema debe entregar, por cada norma incorporada, un informe de lectura: cuántas unidades reconoció, cuáles páginas no pudo leer y qué no pudo ubicar | — |
| REQ-005 | Una norma debe quedar disponible para consultas solo después de que una persona valide su informe de lectura | — |
| REQ-006 | El sistema debe registrar las relaciones entre normas: cuál modifica, complementa, reglamenta o deroga a cuál | — |
| REQ-007 | El sistema debe mantener las versiones de cada norma y, para una fecha dada, indicar qué unidades estaban vigentes y qué normas las habían modificado o derogado, mostrando el texto literal de cada una | — |
| REQ-008 | El sistema debe responder consultas en lenguaje natural sobre la normativa, y cada afirmación de la respuesta debe llevar la cita de la unidad que la sostiene, con su texto literal | — |
| REQ-009 | Cuando la normativa cargada no permite responder, el resultado debe ser "no determinado", sin afirmar nada | — |
| REQ-010 | El sistema debe permitir buscar unidades por norma y número de artículo, y por palabras del texto | — |
| REQ-011 | El sistema debe avisar cuando se intenta cargar una norma que ya está incorporada | — |
| REQ-012 | El sistema debe registrar cada carga, validación y consulta con lo necesario para reconstruirla: quién, cuándo, sobre qué versión de la normativa, qué se recuperó y qué se respondió | — |
| REQ-013 | El sistema debe ofrecer una pantalla de consulta donde una persona escribe su pregunta y ve la respuesta con sus citas; desde cada cita se ve el texto literal de la unidad y se puede abrir la norma original | — |
| REQ-014 | La pantalla de consulta debe distinguir a simple vista una respuesta con fundamento de un resultado "no determinado" | — |
| REQ-015 | El sistema debe incorporar normas en tres formatos: PDF con texto, PDF escaneado y página web guardada. Cuando el texto de una unidad se obtuvo por reconocimiento sobre una imagen, debe quedar indicado en la unidad y en el informe de lectura | — |
| REQ-016 | El sistema debe exigir usuario y clave para ingresar. Cada usuario tiene un rol: lectura, que permite consultar y buscar; o lectura y escritura, que además permite cargar y validar normas y registrar relaciones y versiones | — |
| REQ-017 | El sistema debe registrar la categoría de cada documento: régimen específico, otra normativa aplicable, marco nacional, dictamen legal o recomendación de auditoría | — |
| REQ-018 | Cada cita debe mostrar la categoría de su documento. En una respuesta, las citas del régimen específico van primero; las del marco nacional se presentan como marco; los dictámenes y las recomendaciones se presentan como criterio que acompaña | — |
| REQ-019 | Cuando el régimen específico y el marco nacional tratan el mismo punto de manera distinta, la respuesta debe mostrar ambos textos y señalar el del régimen específico como el aplicable | — |

En esta feature, consolidar significa reunir: cada norma se guarda tal como fue publicada, y los cambios entre normas los registra una persona (REQ-006 y REQ-007). El sistema no redacta textos nuevos; toda cita es texto literal de un documento publicado.

## Criterios de aceptación

- **REQ-001.** Dado el documento de una norma, cuando el responsable lo carga con sus datos, entonces la norma figura en el listado con todos los datos registrados.
- **REQ-002.** Dada una norma incorporada, cuando se pide su original, entonces se obtiene el mismo documento que se cargó.
- **REQ-003.** Dada una norma con artículos numerados, cuando se incorpora, entonces cada artículo existe como unidad separada y su ubicación coincide con la del documento.
- **REQ-004.** Dada una norma con una página ilegible, cuando se incorpora, entonces el informe de lectura señala esa página.
- **REQ-005.** Dada una norma incorporada y todavía no validada, cuando se hace una consulta, entonces esa norma no aparece en las citas.
- **REQ-006.** Dadas dos normas donde una modifica a la otra, cuando se registra la relación, entonces al ver cualquiera de las dos se muestra el vínculo.
- **REQ-007.** Dada una norma con un artículo modificado por otra norma en una fecha, cuando se consulta ese artículo antes y después de esa fecha, entonces antes se muestra solo el texto original, y después el original junto con el texto literal de la norma que lo modifica, señalando el cambio.
- **REQ-008.** Dada una pregunta cuya respuesta está en un artículo cargado, cuando se consulta, entonces la respuesta cita ese artículo y el texto citado coincide palabra por palabra con el de la norma.
- **REQ-009.** Dada una pregunta sobre un tema que ninguna norma cargada trata, cuando se consulta, entonces el resultado es "no determinado".
- **REQ-010.** Dado un número de norma y de artículo, cuando se busca, entonces se obtiene esa unidad con su texto.
- **REQ-011.** Dada una norma ya incorporada, cuando se intenta cargar el mismo documento, entonces el sistema avisa y no la duplica.
- **REQ-012.** Dada una consulta ya respondida, cuando se revisa su registro, entonces se ve la pregunta, las unidades recuperadas, la respuesta, la versión de la normativa, el usuario y la fecha.
- **REQ-013.** Dada la pantalla de consulta, cuando una persona escribe una pregunta que la normativa responde, entonces ve la respuesta con sus citas, y al elegir una cita ve el texto literal del artículo y puede abrir el documento original.
- **REQ-014.** Dada la pantalla de consulta, cuando el resultado es "no determinado", entonces se muestra con un aviso propio, distinto del de una respuesta, y sin citas.
- **REQ-015.** Dada una misma norma disponible como PDF con texto, como PDF escaneado y como página web guardada, cuando se incorpora cada versión, entonces en los tres casos sus artículos quedan como unidades citables, y en el caso escaneado el informe de lectura y cada unidad indican que el texto proviene de reconocimiento.
- **REQ-016.** Dada una persona sin sesión iniciada, cuando intenta consultar, entonces el sistema le pide usuario y clave. Dado un usuario con rol de lectura, cuando intenta cargar o validar una norma, entonces el sistema lo rechaza y deja registro del intento.
- **REQ-017.** Dado un documento que se carga, cuando no se indica su categoría, entonces el sistema no lo incorpora y pide el dato.
- **REQ-018.** Dada una pregunta que responden un artículo del régimen específico y un dictamen legal, cuando se consulta, entonces la respuesta cita primero el artículo, después el dictamen, y cada cita muestra su categoría.
- **REQ-019.** Dado un punto que el régimen específico y el marco nacional regulan de manera distinta, cuando se consulta por ese punto, entonces la respuesta muestra los dos textos y señala el del régimen específico como el aplicable.

## Requisitos no funcionales

- **Calidad de las respuestas.** Se mide con un conjunto de unas 30 preguntas con respuesta conocida (`evals/`), que incluye preguntas que el marco regulatorio cargado no responde. Exigencias para aprobar:
    - El texto citado coincide palabra por palabra con el documento: siempre, sin tolerancia.
    - La respuesta es correcta y cita la unidad correcta: al menos 85 % de las preguntas con respuesta.
    - El sistema se abstiene cuando no hay respuesta: al menos 90 % de las preguntas sin respuesta.
- **Validación del conjunto de preguntas.** El Coordinador propone las preguntas y sus respuestas a partir de los documentos, el responsable del proyecto las corrige y un integrante de la Comisión Evaluadora les da el visto bueno. Sin ese visto bueno, una pregunta no entra al conjunto.
- **Volumen.** Menos de 10 documentos por ahora, repartidos entre las cinco categorías del marco regulatorio.
- **Formato de origen.** La mayoría de las normas está en PDF con texto; algunas están escaneadas o solo en páginas web (REQ-015).
- **Tiempo de respuesta.** Hasta 30 segundos por consulta, en el equipo donde corre el sistema.
- **Funcionamiento sin conexión.** La consulta funciona sin acceso a internet, en el equipo donde corre el sistema.
- **Identificación de quien consulta.** El registro de REQ-012 guarda el usuario que ingresó con su clave (REQ-016).
- **Claves.** Las claves no se guardan en forma legible.
- **Lenguaje de la pantalla.** Textos en lenguaje llano, sin términos técnicos del sistema.

## Fuera de alcance

- Carga y revisión de pliegos (feature 002).
- Evaluación de ofertas (feature 004).
- Descarga automática de normas desde sitios oficiales: las normas se cargan a mano.
- Detección automática de que una norma fue modificada: el cambio lo registra una persona.
- Texto ordenado: armar el texto vigente de una norma con las modificaciones ya aplicadas. Es una decisión diferida (ver `specs/hoja-de-ruta.md`). Esta feature guarda lo que esa consolidación necesitaría: los originales, las relaciones entre normas y las versiones.
- Interpretación jurídica: el sistema muestra lo que la norma dice y dónde lo dice.
- Pantallas para cargar y validar normas: en esta feature esas tareas las hace el responsable de normativa sin pantalla propia. La única pantalla es la de consulta.
- Historial de consultas visible para el usuario y conversación de varias preguntas encadenadas: cada consulta es una pregunta y su respuesta. El registro de auditoría sí guarda todas las consultas.
- Pantalla de administración de usuarios: en esta feature los usuarios y sus roles se dan de alta sin pantalla propia.
- Roles adicionales a lectura y lectura y escritura.

## Datos involucrados

Todos los documentos del marco regulatorio, incluidos los dictámenes legales y las recomendaciones de auditoría, tienen carácter público. En esta etapa pueden estar en el repositorio (`corpus/normativa/`) y usarse en pruebas y evals (principio P4).

En operación quedan en la base interna del sistema y solo los ven los usuarios con acceso (REQ-016). Eso es una decisión sobre quién usa el sistema; los documentos siguen siendo públicos.

## Preguntas abiertas

No quedan preguntas abiertas.

## Definiciones tomadas

- **2026-10-02 · Significado de consolidar.** En esta feature es reunir las normas con sus modificaciones registradas. Producir el texto ordenado queda para decidir más adelante, sin que esta feature lo impida.
- **2026-10-02 · Forma de uso.** La feature incluye una pantalla simple de consulta, para involucrar a la Comisión desde la primera entrega.
- **2026-10-02 · Formato de origen.** Mezcla de formatos: mayormente PDF con texto, más PDF escaneado y páginas web.
- **2026-10-02 · Acceso.** Ingreso con usuario y clave. Dos roles en principio: lectura, y lectura y escritura. El registro de consultas guarda el usuario que ingresó.
- **2026-10-02 · Responsable de normativa.** No es una persona fija: es quien tenga el rol de lectura y escritura.
- **2026-10-02 · Composición del marco regulatorio.** Disposición 297/03 y modificatorias, otra normativa aplicable, normativa nacional como marco, dictámenes legales y recomendaciones de auditoría. Se aplica el régimen específico; la normativa nacional es marco.
- **2026-10-02 · Volumen.** Menos de 10 documentos por ahora.
- **2026-10-02 · Carácter de los documentos.** Todos son públicos, también dictámenes y recomendaciones. En operación van a la base interna y los ven solo los usuarios, sin perder su carácter público.
- **2026-10-02 · Tiempo de respuesta.** Hasta 30 segundos por consulta.
- **2026-10-02 · Calidad.** Unas 30 preguntas de prueba; cita literal siempre, respuesta correcta en al menos 85 %, abstención en al menos 90 %. Son valores de partida para el piloto y se revisan con mediciones reales.
- **2026-10-02 · Validación de las preguntas.** Las propone el Coordinador, las corrige el responsable y las aprueba un integrante de la Comisión.
