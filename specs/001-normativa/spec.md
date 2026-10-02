# Spec 001 · Normativa consultable con cita

Estado: borrador · Fecha: 2026-10-02 · Aprobó: —

## Problema

La normativa de compras aplicable está repartida en varios documentos: la Disposición AFIP 297/03, sus complementarias y el marco nacional. Para revisar un pliego o evaluar una oferta hay que saber qué texto está vigente y poder citarlo con precisión.

Todo lo que EVALUON haga después se apoya en esto. La revisión de pliegos y la evaluación de ofertas muestran, en cada conclusión, la norma que la sostiene. Sin una base de normas confiable y citable, esas conclusiones no tienen fundamento que mostrar.

Esta feature construye esa base: las normas cargadas, con sus versiones, partidas en unidades que se pueden citar, y una forma de consultarlas que siempre devuelve la fuente.

## Usuarios y escenarios

- **Integrante de la Comisión Evaluadora:** consulta la normativa.
- **Responsable de normativa:** carga las normas y valida que quedaron bien. [A ACLARAR: quién cumple este rol durante el piloto]

**Escenario 1 · Incorporar una norma.** Como responsable de normativa, cuando se suma una norma al sistema, necesito cargar el documento con sus datos y revisar un informe de lo que el sistema leyó, para confirmar que quedó completa antes de que se use.

**Escenario 2 · Consultar.** Como integrante de la Comisión, cuando tengo una duda sobre qué exige la normativa, necesito preguntar con mis palabras y recibir una respuesta con el artículo exacto que la respalda, para poder verificarla yo mismo.

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
| REQ-007 | El sistema debe mantener las versiones de cada norma y poder indicar qué texto estaba vigente en una fecha dada | — |
| REQ-008 | El sistema debe responder consultas en lenguaje natural sobre la normativa, y cada afirmación de la respuesta debe llevar la cita de la unidad que la sostiene, con su texto literal | — |
| REQ-009 | Cuando la normativa cargada no permite responder, el resultado debe ser "no determinado", sin afirmar nada | — |
| REQ-010 | El sistema debe permitir buscar unidades por norma y número de artículo, y por palabras del texto | — |
| REQ-011 | El sistema debe avisar cuando se intenta cargar una norma que ya está incorporada | — |
| REQ-012 | El sistema debe registrar cada carga, validación y consulta con lo necesario para reconstruirla: quién, cuándo, sobre qué versión de la normativa, qué se recuperó y qué se respondió | — |

El alcance de REQ-007 depende de una definición pendiente. [A ACLARAR: "consolidar la normativa" significa reunir las normas con sus modificaciones registradas, o además producir el texto ordenado vigente de cada norma]

## Criterios de aceptación

- **REQ-001.** Dado el documento de una norma, cuando el responsable lo carga con sus datos, entonces la norma figura en el listado con todos los datos registrados.
- **REQ-002.** Dada una norma incorporada, cuando se pide su original, entonces se obtiene el mismo documento que se cargó.
- **REQ-003.** Dada una norma con artículos numerados, cuando se incorpora, entonces cada artículo existe como unidad separada y su ubicación coincide con la del documento.
- **REQ-004.** Dada una norma con una página ilegible, cuando se incorpora, entonces el informe de lectura señala esa página.
- **REQ-005.** Dada una norma incorporada y todavía no validada, cuando se hace una consulta, entonces esa norma no aparece en las citas.
- **REQ-006.** Dadas dos normas donde una modifica a la otra, cuando se registra la relación, entonces al ver cualquiera de las dos se muestra el vínculo.
- **REQ-007.** Dada una norma con un artículo modificado en una fecha, cuando se consulta el texto vigente antes y después de esa fecha, entonces se obtiene el texto que correspondía a cada momento.
- **REQ-008.** Dada una pregunta cuya respuesta está en un artículo cargado, cuando se consulta, entonces la respuesta cita ese artículo y el texto citado coincide palabra por palabra con el de la norma.
- **REQ-009.** Dada una pregunta sobre un tema que ninguna norma cargada trata, cuando se consulta, entonces el resultado es "no determinado".
- **REQ-010.** Dado un número de norma y de artículo, cuando se busca, entonces se obtiene esa unidad con su texto.
- **REQ-011.** Dada una norma ya incorporada, cuando se intenta cargar el mismo documento, entonces el sistema avisa y no la duplica.
- **REQ-012.** Dada una consulta ya respondida, cuando se revisa su registro, entonces se ve la pregunta, las unidades recuperadas, la respuesta, la versión de la normativa, el usuario y la fecha.

## Requisitos no funcionales

- **Calidad de las respuestas.** Se mide con un conjunto de preguntas con respuesta conocida (`evals/`). [A ACLARAR: quién valida las respuestas esperadas y qué nivel de acierto se exige para aprobar]
- **Volumen.** [A ACLARAR: qué normas forman el conjunto inicial y cuántas son, aproximadamente]
- **Formato de origen.** [A ACLARAR: las normas están como PDF con texto, como PDF escaneado o solo en páginas web]
- **Tiempo de respuesta.** [A ACLARAR: tiempo aceptable para una consulta; propuesta inicial, hasta 30 segundos]
- **Funcionamiento sin conexión.** La consulta funciona sin acceso a internet, en el equipo donde corre el sistema.

## Fuera de alcance

- Carga y revisión de pliegos (feature 002).
- Evaluación de ofertas (feature 004).
- Descarga automática de normas desde sitios oficiales: las normas se cargan a mano.
- Detección automática de que una norma fue modificada: el cambio lo registra una persona.
- Interpretación jurídica: el sistema muestra lo que la norma dice y dónde lo dice.

La forma de uso durante el piloto está pendiente. [A ACLARAR: esta feature incluye una pantalla de consulta para la Comisión, o alcanza con que funcione y se verifique por pruebas hasta que llegue la revisión de pliegos]

## Datos involucrados

Normas de compras, todas públicas. Pueden estar en el repositorio (`corpus/normativa/`) y usarse en pruebas y evals (principio P4).

## Preguntas abiertas

Cada punto corresponde a una marca del documento. Las responde el responsable del proyecto.

1. Rol de responsable de normativa: quién carga y valida las normas en el piloto.
2. Significado de consolidar: reunir las normas con sus modificaciones, o además producir el texto ordenado vigente.
3. Calidad: quién valida las respuestas esperadas y qué nivel de acierto se exige.
4. Volumen: qué normas forman el conjunto inicial.
5. Formato de origen de las normas.
6. Tiempo de respuesta aceptable.
7. Forma de uso en el piloto: con pantalla de consulta o sin ella.
