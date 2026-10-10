# ADR-0053 · El dato del Portal que coincide con el pliego propone «cumple»

Estado: aceptado · Fecha: 2026-10-10 · Decidió: — (la decisión de fondo es del responsable, 2026-10-10, «Propone cumple», registrada en la spec 015; este ADR fija cómo se aplica y reemplaza en parte al ADR-0043)

**Enmienda de la constitución (2026-10-10).** El responsable decidió enmendar P3: «enmendar. considera al portal como oficial, porque es oficial». La constitución pasa a la versión 1.3 y P3 suma como fundamento el dato publicado en el Portal de Compras para ese procedimiento u oferta, con su enlace y la fecha en que se tomó.

## Contexto

El ADR-0043 (2026-10-06) aplicó la decisión literal «Debiste informar que el doc esta en el portal o que falta coincidencia»: cuando el dato que pide un requisito está en el Portal y no en el texto de la oferta, el sistema lo cita y **no decide** («no determinado», motivo `en_portal`); si los valores difieren, «no determinado» con motivo `falta_coincidencia`. La regla es `evaluon/assessment/portal_facts.py` (`RULE_ONLY_PORTAL`, `RULE_MISMATCH`) y su docstring dice que una cita del Portal no habilita «cumple» ni «no cumple» (P3).

Al rehacer el caso LPU25 (T-229, `specs/014-aplicacion-por-secciones/verificacion/T-229.md`) quedaron 17 celdas en «el dato está en el Portal» y 4 en «falta de coincidencia», de 81. En las 17 el dato estaba cargado y coincidía con lo que exige el pliego (por ejemplo, el monto de la garantía de oferta es exactamente el 5 % del total cotizado); la Comisión las confirmó una por una. El diagnóstico del 2026-10-10 las cuenta entre las celdas que se resuelven con un cambio de regla.

El 2026-10-10 el responsable decidió: **«Propone cumple»**. El sistema propone «cumple» citando el dato del Portal cuando coincide con lo que exige el pliego, y «no cumple» o la diferencia cuando no coincide; la Comisión decide igual. La spec 015 (REQ-103) lo recoge y dice que reemplaza en eso al ADR-0043.

Restricciones: todo sale de las tablas locales de la 012, sin red (P4); el texto de la cita del Portal lo escribe el sistema desde las columnas, nunca el modelo; la decisión final es de la Comisión (P3, P11); la regla queda registrada con su versión (P6).

## Alternativas

### A. Mantener el ADR-0043: citar el Portal y no decidir
Se gana: la lectura más estricta de P3; no cambia nada. Se pierde: las 17 celdas (hasta 20 de 81, 21 % de las celdas) siguen sin decidir aunque el dato coincide, y la Comisión repite a mano una comprobación que el sistema ya hizo. Es la causa que el responsable pidió corregir.

### B. Comparar el dato del Portal con lo que exige el pliego y proponer «cumple» o «no cumple» con la cita del Portal (propuesta)
Se gana: resuelve lo que tiene respaldo; la celda llega con su fundamento (la cita del Portal) y la Comisión confirma o corrige. Se pierde: el Portal pasa a ser fundamento de una conclusión, no solo de un aviso; hay que mantener las reglas de comparación por clase de dato (garantía, cotización por renglón, total, CUIT); un dato mal cargado en el Portal produciría un «cumple» equivocado, aunque visible y corregible por la Comisión.

### C. Proponer «cumple» solo si además el texto de la oferta lo confirma
Se gana: dos fuentes para concluir, la lectura más conservadora que admite una conclusión. Se pierde: no resuelve el caso que motivó la decisión, porque en las 17 celdas el dato estaba solo en el Portal.

## Decisión

Se propone **B**, con estas reglas (el detalle de cada comparación lo fija T-233 con sus tests; los umbrales, el plan 015):

1. Qué dato pide el requisito sigue siendo el catálogo de `portal_facts.py` (garantía, CUIT, cotización, total). La regla sigue en el cuarto lugar del orden (después de externo, técnico e ilegible).
2. **Qué exige el pliego, por clase de dato.** Garantía: el porcentaje que fija el requisito sobre el total cotizado del Portal; coincide si la diferencia es de un centavo o menos. Cotización por renglón: todos los renglones del procedimiento tienen precio en el Portal. Total: el total está cargado y, si el requisito fija moneda, coincide. CUIT: igualdad de los once dígitos.
3. **Coincide:** «cumple», con la cita del Portal escrita por el sistema (`citation kind portal`) y la explicación «Fuente: Portal», sin pasar por el contraste del modelo. **No coincide, y los dos valores son comparables:** «no cumple», con la diferencia en la explicación y las dos citas. **No coincide pero no son comparables** (no hay un valor exigido que se pueda leer, o el requisito pide otro dato): «no determinado» con motivo `falta_coincidencia` y la diferencia a la vista.
4. Si el Portal no tiene el dato, o el requisito no pide un dato del Portal, no rige esta regla y sigue el flujo de la 004. Si el texto de la oferta trae un valor distinto del Portal, sigue siendo «no determinado» `falta_coincidencia` (la Comisión verifica cuál rige): eso se mantiene del ADR-0043.
4 bis. **El Portal también le llega al modelo.** Hoy el modelo recibe solo los PDF (la revisión de las instrucciones lo mostró en la oferta 1: «la oferta no incluye una cotización de precios», con el precio en el Portal). La evaluación le agrega un bloque `[P…]` con los datos del Portal de esa oferta (moneda, total, garantías, precios por renglón), citable: el sistema escribe el texto de la cita desde las columnas, nunca el modelo. Lo que se puede comparar por regla (montos, centavos, CUIT) lo decide el código; al modelo se le pide evidencia. Un requisito de dos condiciones no es «cumple» si a una le falta el dato.
5. Sigue valiendo P3: la Comisión confirma, corrige o rechaza cada celda; la decisión queda registrada como suya. La regla deja en `facts` la `regla` (`portal_cumple`, `portal_no_cumple` o `portal_falta_coincidencia`), los valores comparados y `version_reglas` (`reglas-v8`).

**Lectura de P3 que este ADR necesita que el responsable confirme.** P3 pide como fundamento «el fragmento del pliego o de la oferta y la cita normativa», o la respuesta de la Comisión. El Portal es el lugar donde el oferente presenta su oferta (ADR-0029): sus datos son datos de la oferta cargados por el oferente. Este ADR los trata así, como cita de la oferta con otra fuente. Si el responsable prefiere la lectura estricta (solo texto de documentos), hace falta una enmienda de la constitución por ADR (como el ADR-0009) antes de integrar T-233.

## Consecuencias

Más fácil: hasta unas 20 celdas del caso LPU25 pasan de «no determinado» a una propuesta fundamentada; las preguntas ya no piden confirmar lo que coincide.

Más difícil: hay que mantener las comparaciones por clase de dato y sus tests (marca `decision_literal`: los tests del ADR-0043 que afirmaban «no determinado» se reescriben con la decisión nueva); el sistema puede proponer «cumple» sobre un dato de Portal equivocado, por eso la celda siempre muestra la cita del Portal con el ítem de origen.

Para revertir: volver a la versión de reglas `reglas-v7` (la regla `portal_en_portal` del ADR-0043). Los resultados guardados con `reglas-v8` conservan su regla y su versión; no se reescriben.

## Sin verificar

- Que el catálogo de `portal_facts.py` cubra todos los requisitos del Portal de los casos 01 a 06 (se mide en T-239).
- La tolerancia de un centavo es la de la decisión del diagnóstico del 2026-10-10 (garantía = 5 % del total); no hay otra tolerancia decidida para cotizaciones por renglón.
