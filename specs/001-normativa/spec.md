# Spec 001 · Normativa consultable con cita

Estado: borrador · Fecha: 2026-10-02 · Aprobó: —

## Problema

La normativa de compras aplicable está repartida en varios documentos: la Disposición AFIP 297/03, sus complementarias y el marco nacional. Para revisar un pliego o evaluar una oferta hay que saber qué texto está vigente y poder citarlo con precisión.

Todo lo que EVALUON haga después se apoya en esto. La revisión de pliegos y la evaluación de ofertas muestran, en cada conclusión, la norma que la sostiene. Sin una base de normas confiable y citable, esas conclusiones no tienen fundamento que mostrar.

Esta feature construye esa base: las normas cargadas, con sus versiones, partidas en unidades que se pueden citar, y una pantalla de consulta que siempre devuelve la fuente. La pantalla es también la primera oportunidad de que la Comisión use el sistema y opine sobre él.

## Usuarios y escenarios

- **Integrante de la Comisión Evaluadora:** consulta la normativa desde una pantalla.
- **Responsable de normativa:** carga las normas y valida que quedaron bien. [A ACLARAR: quién cumple este rol durante el piloto]

**Escenario 1 · Incorporar una norma.** Como responsable de normativa, cuando se suma una norma al sistema, necesito cargar el documento con sus datos y revisar un informe de lo que el sistema leyó, para confirmar que quedó completa antes de que se use.

**Escenario 2 · Consultar.** Como integrante de la Comisión, cuando tengo una duda sobre qué exige la normativa, necesito escribir mi pregunta en una pantalla y recibir una respuesta con el artículo exacto que la respalda, para poder verificarla yo mismo.

**Escenario 3 · Una norma cambia.** Como responsable de normativa, cuando una norma es modificada o derogada, necesito registrar el cambio sin perder el texto anterior, para que las evaluaciones hechas con la versión vieja sigan siendo explicables.

**Escenario 4 · No hay respuesta.** Como integrante de la Comisión, cuando pregunto algo que la normativa cargada no trata, necesito que el sistema lo diga, para no tomar como cierta una respuesta sin sustento.

## Requisitos funcionales

| ID | Requisito | Origen normativo |
|---|---|---|
| REQ-001 | El sistema debe incorporar una norma a partir de su documento, registrando tipo, número, organismo emisor, título, fecha de publicación, fecha de vigencia y fuente de donde se obtuvo | — |
| REQ-002 | El sistema debe conservar el documento original de cada norma y permitir verlo | — |
| REQ-003 | El sistema debe dividir cada norma en unidades citables (artículo, inciso, anexo), cada una con su ubicación dentro de la norma | — |
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

## Requisitos no funcionales

- **Calidad de las respuestas.** Se mide con un conjunto de preguntas con respuesta conocida (`evals/`). [A ACLARAR: quién valida las respuestas esperadas y qué nivel de acierto se exige para aprobar]
- **Volumen.** [A ACLARAR: qué normas forman el conjunto inicial y cuántas son, aproximadamente]
- **Formato de origen.** [A ACLARAR: las normas están como PDF con texto, como PDF escaneado o solo en páginas web]
- **Tiempo de respuesta.** [A ACLARAR: tiempo aceptable para una consulta; propuesta inicial, hasta 30 segundos]
- **Funcionamiento sin conexión.** La consulta funciona sin acceso a internet, en el equipo donde corre el sistema.
- **Identificación de quien consulta.** El registro de REQ-012 necesita saber quién hizo cada consulta. [A ACLARAR: cómo se identifica una persona en la pantalla durante el piloto: eligiendo su nombre de una lista, o con usuario y clave]
- **Lenguaje de la pantalla.** Textos en lenguaje llano, sin términos técnicos del sistema.

## Fuera de alcance

- Carga y revisión de pliegos (feature 002).
- Evaluación de ofertas (feature 004).
- Descarga automática de normas desde sitios oficiales: las normas se cargan a mano.
- Detección automática de que una norma fue modificada: el cambio lo registra una persona.
- Texto ordenado: armar el texto vigente de una norma con las modificaciones ya aplicadas. Es una decisión diferida (ver `specs/hoja-de-ruta.md`). Esta feature guarda lo que esa consolidación necesitaría: los originales, las relaciones entre normas y las versiones.
- Interpretación jurídica: el sistema muestra lo que la norma dice y dónde lo dice.
- Pantallas para cargar y validar normas: en esta feature esas tareas las hace el responsable de normativa sin pantalla propia. La única pantalla es la de consulta.
- Historial de consultas y conversación de varias preguntas encadenadas: cada consulta es una pregunta y su respuesta.

## Datos involucrados

Normas de compras, todas públicas. Pueden estar en el repositorio (`corpus/normativa/`) y usarse en pruebas y evals (principio P4).

## Preguntas abiertas

Cada punto corresponde a una marca del documento. Las responde el responsable del proyecto.

1. Rol de responsable de normativa: quién carga y valida las normas en el piloto.
2. Calidad: quién valida las respuestas esperadas y qué nivel de acierto se exige.
3. Volumen: qué normas forman el conjunto inicial.
4. Formato de origen de las normas.
5. Tiempo de respuesta aceptable.
6. Identificación de quien consulta en la pantalla.

## Definiciones tomadas

- **2026-10-02 · Significado de consolidar.** En esta feature es reunir las normas con sus modificaciones registradas. Producir el texto ordenado queda para decidir más adelante, sin que esta feature lo impida.
- **2026-10-02 · Forma de uso.** La feature incluye una pantalla simple de consulta, para involucrar a la Comisión desde la primera entrega.
