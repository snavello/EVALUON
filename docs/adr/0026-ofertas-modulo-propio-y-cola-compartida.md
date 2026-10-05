# ADR-0026 · Las ofertas viven en un módulo propio, con la cola de pedidos compartida

Estado: aceptado · Fecha: 2026-10-05 · Decidió: responsable del proyecto (al aprobar el plan 008)

## Contexto

La feature 008 guarda ofertas, sus documentos, su lectura, los pasajes de texto en que se busca y la ficha con sus fragmentos. Es esquema nuevo y difícil de revertir una vez que haya datos. La 003 ya tiene, en `evaluon/tenders/`, un modelo de documento del pliego (`Document`, `Reading`, `Segment`) y una cola de pedidos en segundo plano (`tenders_job`, ADR-0018) que atiende el `worker`.

Restricciones: las ofertas se procesan solo con IA local (P4); el esquema lo toca un solo agente por vez; la lectura de PDF, el OCR y el texto canónico ya existen en `evaluon/norms/` y no se rehacen. Las ofertas no tienen la estructura de un pliego (cláusulas numeradas, renglones, secciones): son declaraciones, constancias, pólizas, planillas y escaneos.

## Alternativas

### A. Reutilizar `Document`, `Reading` y `Segment` del pliego, con un tipo "oferta"

- Se gana: ninguna tabla de lectura nueva; la pantalla de documentos ya existe.
- Se pierde: `Segment` está atado a las reglas de tramos del pliego (claves de cláusula, `section_class`, renglones) y a sus restricciones de la base; `Document` cuelga de un procedimiento y no de una oferta ni de un oferente. Habría que aflojar restricciones de la 003 ya verificada, y cualquier cambio de la 008 podría romper la medición de la 003.

### B. Módulo nuevo `evaluon/offers/` con tablas propias y la cola de `tenders_job` compartida (elegida)

- Tablas `offers_*` para oferta, documento, original, lectura, pasaje, ficha, entrada, fragmento, pedidos al modelo e historial. Una dirección de dependencia: `offers` usa `tenders` (procedimiento, versión de la matriz, requisito), nunca al revés.
- La cola: dos tipos de pedido nuevos en `tenders_job` (`read_offer_document`, `build_sheet`) y un campo `target_id` (entero, sin clave foránea) con el id del documento de oferta o de la oferta. Sin clave foránea porque una de `tenders` a `offers` crearía una dependencia circular entre migraciones.
- Se gana: la 003 no se toca salvo una migración chica de `tenders_job`; el `worker` atiende todo con un solo proceso y un solo motor de generación (la GPU no se comparte entre dos colas); el aviso de fin de la 003 sirve tal cual.
- Se pierde: `target_id` no tiene integridad referencial en la base (la comprueba la función de negocio); hay una migración en dos aplicaciones.

### C. Cola propia para las ofertas (`offers_job`) y un segundo servicio de lectura

- Se gana: separación total.
- Se pierde: dos procesos que compiten por la misma GPU sin coordinación, un segundo aviso de fin y duplicar la lógica de la cola (ADR-0018 ya la resolvió). Contra P10.

## Decisión

Se adopta B. Todo el esquema de la feature (tablas de `offers`, tipos de hecho de auditoría y la migración de `tenders_job`) lo crea una sola tarea, la primera (T-130), con todas las tablas que el plan nombra, aunque las pantallas lleguen después. Un cambio posterior de esquema se hace en una tarea que dependa de la anterior que lo tocó y que no corra en paralelo con otra que lo toque.

## Consecuencias

- Más fácil: la medición y la pantalla de la 003 no se mueven; las ofertas se pueden borrar o reescribir sin tocar el pliego.
- Más difícil: `target_id` pide un control en la función de negocio y una prueba.
- Para revertir: quitar la aplicación `offers` y sus migraciones y los dos valores de `JobKind`; el pliego no se afecta. Si ya hay ofertas cargadas, se exportan antes.
