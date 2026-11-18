# ADR-0078 · El estado de los siete pasos se calcula sobre las secciones y etapas existentes, sin guardar nada

Estado: propuesto · Fecha: 2026-11-17 · Propuso: Planificador (plan 018) · Decidió: —

## Contexto

REQ-143 a REQ-145 piden que cada procedimiento muestre siete pasos, cada uno con su estado («Hecho», «En curso», «Todavía no», «Con error»), que varios estén en curso a la vez y que un paso «Hecho» vuelva a «En curso» cuando aparece algo nuevo, **sin guardar una fase ni pedir a nadie que la marque**. El ADR-0045 ya decidió que el estado de las etapas se calcula al mostrar y el ADR-0047, que las secciones no tienen orden obligatorio.

Lo que hay: seis etapas de la 013 con su estado (`journey/stages/*.py`), cinco secciones de la 014 que suman sus cuentas y renglones (`journey/sections/`, con `Item` y `Missing`), y datos sueltos (circulares, documentos de ofertas, dictamen, plazos) que los temas ya leen. Los siete pasos no coinciden uno a uno con las etapas ni con las secciones: el paso 1 mezcla datos del Portal, pliego y circulares; el paso 4 toma de la etapa de evaluación y del informe técnico (que hoy cuenta la etapa «Matriz de evaluación»); el paso 6 toma el resto de esa etapa. Algunos pendientes no son «contados» (validar la matriz con todo confirmado, cargar el dictamen).

## Alternativas

### A. Un módulo nuevo que lee el `Overview` y las funciones existentes y calcula los siete estados al mostrar (propuesta)
`journey/proceso/` toma lo que `sections_for` ya devuelve y reparte los renglones en pasos por su `origen` (campo nuevo, con valor por omisión, que `build_section` completa). Se gana: cero datos nuevos (REQ-145); una sola definición de «pendiente» (el contador de las pestañas y la lista de acciones salen de los mismos renglones); el cálculo se prueba con los mismos fixtures de la 013/014; los estados no pueden desfasarse de las pestañas. Se pierde: el módulo conoce la correspondencia tema → paso (una tabla que hay que mantener al agregar temas; un test lo vigila); algunas reglas del paso (documento no tenido en cuenta por la última evaluación) piden una consulta más.

### B. Guardar la fase o el estado de cada paso
Una tabla o columna con el estado, que se actualiza al cambiar algo. Se gana: lectura barata y un historial. Se pierde: contradice REQ-145 y el ADR-0045; hay que actualizarla desde cada servicio que cambia algo (circular, documento, decisión) y se desfasa si uno se olvida; exige migración.

### C. Calcular los siete estados con consultas propias, sin pasar por las secciones
Un módulo independiente que consulta los modelos directamente. Se gana: independencia de la estructura de secciones y quizá menos trabajo por pedido. Se pierde: una segunda definición de «lista», «pendiente» y «error» que puede discrepar de las pestañas (el criterio numérico 2 de la spec pide coincidencia exacta con los pendientes que ya se calculan); se duplica lógica que la 013 y la 014 probaron.

## Decisión

Se propone **A**. Las reglas comunes son: «Hecho» = condiciones de la spec y ninguna acción abierta del paso; «En curso» = el paso empezó o tiene una acción disponible; «Todavía no» = no empezó y ninguna acción está disponible; «Con error» = su última tarea falló sin un resultado posterior. La tabla paso → reglas → datos → función está en el plan 018. Los casos que los datos no cubrían (documentos «sin revisar», circulares «sin revisar», qué es «A decidir», qué se llama a un paso que se puede empezar) se le preguntaron al responsable y los resolvió el 2026-11-17: «sin revisar» se deduce de la lectura y de `Run.documents`, sin marca nueva; «A decidir» es solo lo no determinado; un paso que se puede empezar está «En curso» y «Todavía no» queda para lo que depende de otro paso. La lista de acciones incluye también las acciones de cierre y los faltantes (decisión «Todo lo que falta»).

## Consecuencias

- Más fácil: ninguna migración; un tema nuevo con pendientes se suma a un paso con una línea en la tabla de origen; el estado siempre coincide con el contador de las pestañas.
- Más difícil: hay que mantener la tabla `origen` → paso (el test falla si un renglón queda sin paso); el cálculo de cada pedido recorre las cinco secciones.
- Para revertir: la lectura se descarta sin dejar rastros (no hay datos). Pasar a B exigiría una migración y actualizar el estado desde cada servicio que cambia algo; no se recomienda.
