# ADR-0030 · La importación del Portal vive en un módulo propio y propone por ítems antes de cargar

Estado: aceptado · Fecha: 2026-10-05 · Decidió: responsable del proyecto

## Contexto

La feature 012 (ADR-0029) explora la página pública de un proceso del Portal de Compras y propone qué cargar: datos del procedimiento, renglones, documentos, ofertas con su cotización. Nada se carga sin aprobación (REQ-048) y cada dato conserva su origen (REQ-049). La revisión periódica (REQ-050) vuelve a explorar y propone solo lo nuevo o cambiado.

Restricciones:

- Las cargas tienen que entrar por los servicios de la 003 y la 008 (`register_procedure`, `load_document`, `register_offer`), que ya comprueban el rol, rechazan duplicados y dejan el registro P6.
- Hay datos que ni `tenders` ni `offers` tienen donde guardar: renglones con cantidad, expediente, encuadre legal, cronograma, garantías, CUIT, total y garantía de cada oferente, cotización por renglón.
- La 003 y la 008 están verificadas y medidas; su esquema no debería moverse por esta feature.
- La propuesta tiene que sobrevivir entre la exploración (en segundo plano) y la aprobación (otra sesión, otra persona), y la revisión tiene que saber qué se aprobó o rechazó antes.

## Alternativas

### A. Módulo nuevo `evaluon/portal/` con una propuesta persistente de ítems (elegida)

Tablas `portal_*`: enlace, página guardada, archivo bajado, propuesta, ítem (con tipo, clave estable, contenido, huella del contenido, estado, decisión con autor y fecha, y qué objeto se creó) y las tablas de los datos que no tenían lugar (renglón, datos del procedimiento, datos de la oferta, cotización). Una sola dirección de dependencia: `portal` usa `tenders` y `offers`, nunca al revés. Cada tipo de ítem se carga llamando al servicio existente.

- Se gana: la 003 y la 008 no se tocan (salvo `tenders_job`, ver ADR-0031); el origen de lo cargado es el ítem aprobado; "lo ya aprobado no se repite" es comparar huellas de ítems de la misma clave; se puede aprobar todo o ítem por ítem sobre la misma estructura.
- Se pierde: una tabla de ítems genérica con contenido en JSON, sin integridad fina del contenido (la validan el lector de la página y el servicio que carga); el origen de un documento se ve en la pantalla del Portal y no dentro de la pantalla del pliego.

### B. Agregar a `tenders` y `offers` columnas de origen y las tablas que faltan

- Se gana: el origen aparece junto al dato, en las pantallas existentes.
- Se pierde: cambios de esquema y de pantallas en dos features ya verificadas; cualquier error rompe mediciones de la 003 y la 008; la propuesta pendiente igual necesitaría tablas aparte.

### C. Importar directo, con una pantalla de confirmación sin propuesta guardada

- Se gana: menos tablas.
- Se pierde: no hay dónde registrar la decisión por ítem ni qué se rechazó, así que la revisión periódica volvería a proponer lo rechazado y no se cumple REQ-048 ni REQ-050.

## Decisión

Se adopta **A**. Todo el esquema (tablas de `portal`, cambios de `tenders_job` y tipos de hecho de auditoría) lo crea una sola tarea, la primera (T-138); un cambio posterior se hace en una tarea que dependa de la anterior que lo tocó (misma regla que el ADR-0026).

Dos reglas del modelo:

1. Un ítem lleva una clave estable (por ejemplo, `documento:<huella de la URL>`, `oferta:<CUIT>`) y la huella de su contenido. Una exploración nueva propone un ítem solo si su clave no existe o si su huella difiere de la última decidida; un ítem rechazado con la misma huella no se vuelve a proponer.
2. Quien aprueba es el evaluador, salvo los ítems de tipo documento, que también aprueba el operador (REQ-048). Cada decisión deja su hecho de auditoría y la fila del ítem.

## Consecuencias

- Más fácil: sumar tipos de ítem sin tocar los demás (cada uno es un archivo en `evaluon/portal/importers/`); revisar el historial de una importación; borrar todo `portal` sin afectar el pliego.
- Más difícil: el origen de un documento no está en la pantalla del pliego; el contenido del ítem es JSON.
- Para revertir: quitar la aplicación `portal`, su migración y los dos valores de `JobKind`; lo cargado en `tenders` y `offers` queda como una carga manual. Si hay propuestas, se exportan antes.
