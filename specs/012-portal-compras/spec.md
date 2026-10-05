# Spec 012 · Importación asistida desde el Portal de Compras

Estado: aprobada · Fecha: 2026-10-05 · Aprobó: responsable del proyecto (2026-10-05, con las respuestas de "Preguntas abiertas")

> La spec dice qué se necesita y por qué. No menciona tecnología, librerías ni estructura de código: eso va en el plan.
> Cada duda se marca `[A ACLARAR: pregunta concreta]`. Una spec con marcas pendientes no pasa la compuerta.

## Problema

Hoy el operador carga a mano el procedimiento, el pliego, cada circular y los documentos de cada oferta, y tipea los datos del procedimiento. Es lento, es fácil olvidar una circular o un documento, y algunos datos clave llegan de la peor forma: la cotización por renglón de cada oferente, por ejemplo, terminó leyéndose de fotos de pantalla, con errores.

El Portal de Compras de AFIP/ARCA publica de forma pública y ordenada casi toda esa información: los datos del proceso (número, expediente, objeto, encuadre legal, renglones con cantidades, cronograma, garantías), los documentos (pliego, circulares, actos administrativos, acta de apertura, dictamen) y, ya abiertas las ofertas, cada oferente con su total, su garantía y el detalle de precios por renglón. Es la fuente oficial (decisión de la Comisión, 2026-10-05): conviene que sea la primera fuente de EVALUON, y que la carga a mano quede para lo que no está publicado, como los documentos de cada oferta.

La información aparece por etapas (las ofertas, recién después de la apertura; el dictamen, después de la evaluación), así que además de la importación inicial hace falta revisar periódicamente los procesos en curso para no perder novedades.

## Usuarios y escenarios

Roles de la 003: el operador propone; la Comisión (evaluador) aprueba (P3).

**Escenario 1 · Importar un proceso.** Como operador, cuando la Comisión empieza a trabajar un proceso, necesito pegar en EVALUON el enlace público del proceso en el Portal, para que el sistema explore todo lo publicado y me proponga qué cargar.

**Escenario 2 · Aprobar la propuesta.** Como integrante de la Comisión, cuando el sistema terminó de explorar, necesito ver en una sola pantalla todo lo que propone cargar (datos del proceso, renglones, documentos, ofertas, cotizaciones, garantías), con su origen en el Portal, y aprobarlo en el momento, todo junto o ítem por ítem, para que se cargue sin tipear nada.

**Escenario 3 · Novedades.** Como integrante de la Comisión, mientras un proceso está en curso, necesito que el sistema revise el Portal periódicamente y me avise cuando aparezca algo nuevo (una circular, el acta de apertura, las ofertas, el dictamen), con la misma propuesta para aprobar.

**Escenario 4 · Lo que no está publicado.** Como operador, necesito seguir cargando a mano lo que el Portal no publica (los documentos de cada oferta) o un documento que el Portal no deja bajar.

## Requisitos funcionales

| ID | Requisito | Origen normativo |
|---|---|---|
| REQ-045 | El sistema debe permitir registrar un proceso a partir del enlace público de su página en el Portal de Compras. | — |
| REQ-046 | Con ese enlace, el sistema debe explorar lo publicado y proponer, sin cargar nada todavía: los datos del procedimiento (número, expediente, objeto, tipo, encuadre legal y fecha de autorización), los renglones con su cantidad, el cronograma, las garantías, y la lista de documentos disponibles (pliego, circulares, actos administrativos, acta de apertura, dictamen). | Encuadre legal: régimen aplicable (Disp. 247/2022 o 297/03 según la fecha de autorización) |
| REQ-047 | Si las ofertas ya están abiertas, la propuesta debe incluir cada oferta con su oferente, su CUIT, su total, su garantía (tipo, forma y monto) y el precio y la cantidad ofrecidos por renglón. | — |
| REQ-048 | Nada se carga sin la aprobación de un evaluador; el operador puede aprobar solo la carga de documentos. La aprobación puede ser de toda la propuesta o ítem por ítem, y cada ítem aprobado o rechazado queda registrado con quién y cuándo (P6). | — |
| REQ-049 | Cada documento y cada dato cargado desde el Portal debe conservar su origen (la página o el documento del Portal y la fecha de la consulta) y, para los documentos, el original sin cambios con su huella. | — |
| REQ-050 | El sistema debe revisar periódicamente los procesos en curso y proponer las novedades (documentos o datos nuevos o cambiados) con el mismo circuito de aprobación. Lo ya aprobado no se vuelve a proponer. | — |
| REQ-051 | La carga a mano sigue disponible para todo lo que el Portal no publique o no deje bajar, y convive con lo importado. | — |

## Criterios de aceptación

- **REQ-045.** Dado el enlace público de un proceso, cuando el operador lo registra, entonces el sistema lo acepta y lo asocia al proceso, o explica por qué no puede usarlo.
- **REQ-046.** Dado el proceso del caso-00, cuando el sistema explora, entonces propone el 100 % de los datos del procedimiento, los 6 renglones con su cantidad y todos los documentos que muestra la página, cada uno con su origen.
- **REQ-047.** Dado el caso-00, entonces la propuesta trae las 3 ofertas con su total y su garantía, y los 18 pares oferta y renglón con su precio y cantidad, iguales a los del Portal.
- **REQ-048.** Dada una propuesta, cuando un integrante aprueba una parte y rechaza otra, entonces solo se carga lo aprobado y ambas decisiones quedan registradas con autor y fecha; sin aprobación no se carga nada.
- **REQ-049.** Dado un documento importado, entonces se puede ver de qué página del Portal salió y cuándo, y su huella coincide con el archivo bajado.
- **REQ-050.** Dado un proceso en curso al que el Portal le agrega una circular, cuando corre la revisión periódica, entonces la circular aparece propuesta como novedad, y lo ya aprobado no se repite.
- **REQ-051.** Dado un proceso importado, cuando el operador carga a mano un documento de una oferta, entonces queda junto a lo importado, con origen "carga manual".

## Requisitos no funcionales

- **Conexión:** es la única parte de EVALUON que sale a internet, y solo hacia el Portal de Compras, para leer información pública. Los pliegos y las ofertas se siguen procesando en el equipo (P4). Excepción aprobada por el responsable el 2026-10-05 (ADR-0029).
- **Búsqueda:** la búsqueda del Portal exige un código de verificación (CAPTCHA); el sistema no lo resuelve ni lo evita. El enlace de cada proceso lo consigue una persona una vez.
- **Frecuencia de la revisión periódica:** una vez por día hábil por proceso en curso, y a demanda con un botón (decisión del responsable, 2026-10-05).
- **Cambios del Portal:** si la página cambia y el sistema no puede leerla, lo informa y se sigue con la carga a mano.
- **Medición:** con el caso-00 (proceso A0PC000000-0004-LPU25, con ofertas y dictamen publicados) y un proceso con circulares. Umbral: 100 % de los datos y documentos propuestos coinciden con el Portal.

## Fuera de alcance

- Buscar procesos en el Portal sin el enlace (la búsqueda exige CAPTCHA).
- Los documentos de cada oferta (pólizas, declaraciones, hojas técnicas): el Portal no los publica; siguen con carga a mano (008).
- Publicar o modificar algo en el Portal: el sistema solo lee.

## Datos involucrados

Información pública del Portal de Compras de AFIP/ARCA. El sistema es para la propia AFIP/ARCA (decisión del responsable, 2026-10-05), por lo que el uso de su Portal no plantea restricciones de uso. Los datos de los oferentes (razón social, CUIT, montos) son públicos en el Portal, pero los casos se siguen guardando fuera del repositorio (P4).

## Preguntas abiertas

Ninguna. Respuestas del responsable (2026-10-05):

1. Excepción a la operación sin conexión: sí, solo para leer el Portal (ADR-0029).
2. Revisión periódica: una vez por día hábil por proceso en curso, y a demanda.
3. Aprobación: un evaluador; el operador puede aprobar solo la carga de documentos.
4. Los términos y condiciones del Portal no son impedimento: el sistema es para la propia AFIP/ARCA.
