# ADR-0048 · Historial de documentos sin borrar

Estado: aceptado · Fecha: 2026-10-07 · Decidió: responsable del proyecto (2026-10-07 21:20, «ok avanza», junto con la maqueta)

## Contexto

La spec 014 (REQ-099, principio P6) pide que reemplazar o retirar un archivo no borre nada: la versión anterior y el retirado quedan en el historial y se pueden ver, y lo retirado se puede restituir. Hoy ni el pliego (`tenders_document`) ni las ofertas (`offers_document`) permiten reemplazar, retirar ni restituir; un archivo repetido se rechaza por su huella y las versiones de la matriz y de la ficha ya tienen su propio historial. Los documentos, sus archivos originales y sus lecturas están protegidos (`on_delete=PROTECT`) y las evaluaciones guardan qué documentos usaron.

## Alternativas

### A. Tabla de cambios de solo inserción y estado calculado
Una tabla `document_change` por app (documento, acción `reemplazar`/`retirar`/`restituir`, documento nuevo, nota, usuario, momento, hecho de auditoría), con disparador que impide `UPDATE` y `DELETE`. «Vigente», «reemplazado» y «retirado» se calculan del último cambio. Es el patrón de `RequirementChange` y `SheetEntry` del proyecto. Se gana: el documento y su archivo no se tocan nunca, el historial es auditable, restituir es otro hecho y no deshace nada. Se pierde: hay que calcular el estado con una consulta (un índice por documento alcanza) y son dos tablas, una por app.

### B. Columnas en el documento (`replaced_by`, `withdrawn_at`, `withdrawn_by`)
Se agrega al propio documento quién lo reemplazó y cuándo se retiró. Se gana: una consulta más simple. Se pierde: el documento deja de ser inmutable (hay que quitar la protección de actualización), restituir borra el dato del retiro (se pierde el historial de retiro y restitución) y el historial de más de un ciclo no cabe.

### C. Borrado lógico más copia de seguridad
Marcar `deleted` y guardar el original en otra tabla. Se gana: nada. Se pierde: es B con más piezas y no deja historial legible.

## Decisión

A, propuesta. Reemplazar crea el documento nuevo con la carga existente y un cambio que los une; retirar y restituir solo agregan cambios. El estado vigente es el del último cambio. Lo retirado o reemplazado deja de entrar a la propuesta de la matriz y a la evaluación, pero las versiones de la matriz ya validadas y las evaluaciones hechas no cambian: se les marca que usaron un documento que después se retiró.

## Consecuencias

- Más fácil: auditar quién retiró qué y cuándo; ver todas las versiones de un documento.
- Más difícil: toda consulta de «documentos vigentes» debe pasar por el servicio de historial (`document_history.py`), no por `documents.all()`.
- Revertir: quitar las dos tablas y el filtro; los documentos no se modifican, así que no hay datos que recomponer.
- Agrega dos tablas por una función que la spec pide explícitamente (P10).
