# Spec 008 · Ofertas y ficha por oferta

Estado: aprobada · Fecha: 2026-10-05 · Aprobó: responsable del proyecto (2026-10-05, con las tres respuestas de "Preguntas abiertas"); enmienda del 2026-10-05: criterio de REQ-039 (ADR-0035), decisión del responsable

> La spec dice qué se necesita y por qué. No menciona tecnología, librerías ni estructura de código: eso va en el plan.
> Cada duda se marca `[A ACLARAR: pregunta concreta]`. Una spec con marcas pendientes no pasa la compuerta.

## Problema

Con la matriz validada (feature 003), la Comisión sabe qué exige el pliego. El paso siguiente es buscar en cada oferta dónde el oferente responde a cada requisito. Una oferta llega en muchos documentos: la propuesta económica, las declaraciones juradas, las pólizas de garantía, las constancias, la documentación técnica. Algunos tienen texto y otros son fotos o escaneos. Hoy la Comisión los recorre a mano, requisito por requisito y oferta por oferta.

Esa búsqueda es el trabajo más largo de la evaluación, y donde más fácil se pasa por alto un documento o una página. La evaluación asistida (feature 004) necesita además, para cada requisito, el fragmento de la oferta en que apoyarse.

Esta feature carga las ofertas de un procedimiento y arma una **ficha por oferta**: para cada requisito de la matriz validada, qué ofreció el oferente y en qué documento y página lo dice, con la cita textual. La ficha no dice si cumple o no cumple, porque eso es la 004. Dice qué hay y dónde, o que no se encontró.

## Usuarios y escenarios

Los roles son los de la 003: el operador carga y corrige; el evaluador valida (P3).

**Escenario 1 · Cargar una oferta.** Como operador, cuando se abren las ofertas de un procedimiento, necesito registrar cada oferta con su oferente y cargar todos sus documentos, tengan texto o sean escaneos, para que el sistema los lea.

**Escenario 2 · Ver la ficha.** Como integrante de la Comisión, cuando el sistema terminó de leer una oferta, necesito ver, para cada requisito de la matriz validada, lo que la oferta dice sobre él, con el documento, la página y el texto exacto, para no tener que recorrer todos los documentos.

**Escenario 3 · Lo que no aparece.** Como integrante de la Comisión, necesito saber qué requisitos no tienen ningún fragmento en la oferta, y qué páginas el sistema no pudo leer, para revisarlos yo antes de evaluar.

**Escenario 4 · Corregir la ficha.** Como integrante de la Comisión, cuando el sistema citó un fragmento equivocado o se le pasó uno, necesito corregirlo o agregarlo, para que la evaluación se apoye en la ficha correcta.

## Requisitos funcionales

| ID | Requisito | Origen normativo |
|---|---|---|
| REQ-037 | El sistema debe permitir registrar las ofertas de un procedimiento, cada una con su oferente, y cargar en cada una varios documentos. | — |
| REQ-038 | El sistema debe leer los documentos con texto y los escaneados o fotografiados, e informar qué páginas no pudo leer o leyó con baja confianza. | — |
| REQ-039 | Para cada oferta y cada requisito de la matriz validada, el sistema debe proponer los fragmentos de la oferta que responden al requisito, cada uno con el documento, la página y el texto literal. | — |
| REQ-040 | Cuando no encuentra ningún fragmento para un requisito, el sistema debe decirlo expresamente en la ficha ("no se encontró en la oferta"), sin dejar el requisito vacío ni suponer. | — |
| REQ-041 | La ficha debe mostrar una síntesis breve de lo ofrecido para cada requisito, sin juicio de cumplimiento. | — |
| REQ-042 | La Comisión debe poder confirmar, corregir, quitar o agregar fragmentos de la ficha. Cada cambio queda registrado con quién y cuándo (P6). | — |
| REQ-043 | La ficha se arma solo contra una matriz validada. Si la matriz cambia de versión, la ficha indica con qué versión se armó. | — |
| REQ-044 | Para la parte técnica, la ficha indica si la oferta trae documentación técnica y, cuando el pliego tiene renglones, si el oferente cotizó o no cada renglón. No compara el contenido técnico con las especificaciones (eso es la feature 010). | — |

## Criterios de aceptación

- **REQ-037.** Dado un procedimiento con la matriz validada, cuando el operador registra una oferta y carga sus documentos, entonces la oferta queda con su oferente y todos sus documentos, cada uno con su huella.
- **REQ-038.** Dada una oferta con documentos escaneados, cuando el sistema la lee, entonces cada página tiene texto o figura en la lista de páginas no leídas.
- **REQ-039.** Dada una oferta de un caso medido, cuando el sistema arma la ficha, entonces encuentra al menos el **90 %** de los fragmentos esperados de la lista del caso, y el texto que muestra es copia literal del documento (100 %). Un fragmento cuenta como encontrado si señala el mismo lugar de la oferta (documento, página y pasaje) que el esperado, aunque no coincida palabra por palabra (decisión del responsable, 2026-10-05).
  - **Enmienda del 2026-10-05 (ADR-0035):** bloquean el texto literal (100 %) y que ningún hallazgo se presente sin respaldo ("no se encontró" cuando no lo hay). El 90 % de fragmentos encontrados se mide y se informa sin bloquear, y pasa a ser meta de la 004, que lee completos los documentos de la oferta por requisito.
- **REQ-040.** Dado un requisito sin respuesta en la oferta, cuando se arma la ficha, entonces figura "no se encontró en la oferta" y cuenta en la lista del escenario 3.
- **REQ-041.** Dada una ficha armada, la síntesis no contiene "cumple" ni "no cumple" ni equivalentes.
- **REQ-042.** Dada una ficha, cuando un integrante corrige un fragmento, entonces el cambio queda con su autor y su fecha, y el fragmento anterior sigue visible en el historial.
- **REQ-043.** Dada una ficha armada con la versión 1 de la matriz, cuando se valida una versión 2, entonces la ficha avisa que se armó con la versión 1.
- **REQ-044.** Dada una oferta de un pliego con renglones, cuando se arma la ficha, entonces cada renglón figura como "cotizado" (con la cita de dónde) o "no cotizado", y se indica si la oferta trae documentación técnica.

## Requisitos no funcionales

- **Medición:** primero con un caso chico y público (una oferta y pocos requisitos) y después con las tres ofertas del caso-00, que tiene la evaluación terminada (ADR-0025). La lista de fragmentos esperados la arma el Coordinador leyendo las ofertas, sin correr el sistema. Como máximo dos rondas de ajuste. Por ahora no hay ofertas de otro caso: la medición a ciegas con otro caso queda para la revisión con el primer producto (ADR-0024; decisión del responsable, 2026-10-05).
- **Tiempo:** se mide y se informa por oferta y por página; no tiene máximo (como en la 003).
- **Funcionamiento sin conexión:** todo corre en el equipo propio, también la lectura de escaneos (P4, P5).

## Fuera de alcance

- Decir si una oferta cumple o no cumple: es la feature 004.
- Las hojas de compliance (feature 005) y las preguntas a la Comisión (feature 009).
- Comparar ofertas entre sí (feature 006).
- Comparar el contenido técnico de la oferta con las especificaciones renglón por renglón (feature 010). La 008 solo verifica que exista documentación técnica y qué renglones se cotizaron (REQ-044).

## Datos involucrados

- Ofertas públicas de procedimientos ya adjudicados. Hoy solo el caso-00 tiene ofertas cargadas: tres oferentes, 29 documentos, algunos escaneados con celular. Por ahora no hay ofertas de otro caso.
- Las ofertas incluyen datos personales de los oferentes (nombres, documentos de identidad). Se quedan fuera del repositorio, como los casos de la 003 (P4); al repositorio solo van identificadores y medidas.

## Preguntas abiertas

Ninguna. Respuestas del responsable (2026-10-05):

1. Meta de fragmentos encontrados: 90 %. La coincidencia con el esperado no tiene que ser literal; el texto mostrado sí es copia literal del documento.
2. Parte técnica: se verifica que exista documentación técnica y, si hay renglones, si cada uno tiene o no oferta (REQ-044).
3. No hay ofertas de otro caso por ahora: se mide con el caso-00 y la medición a ciegas queda diferida.
