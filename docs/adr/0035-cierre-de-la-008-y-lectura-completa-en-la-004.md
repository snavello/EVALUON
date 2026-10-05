# ADR-0035 · Cierre de la 008 con la ficha actual y lectura completa de los documentos en la 004

Estado: aceptado · Fecha: 2026-10-05 · Decidió: responsable del proyecto (opción A)

## Contexto

La ficha por oferta (REQ-039) se midió con las tres ofertas reales del caso-00 en cuatro versiones (T-134, T-135, T-136 y T-146). La última encuentra 25 de 55 fragmentos esperados; descontando los defectos de la lista (copias de cuadros y cuadros del Portal no contemplados) ronda el 55 %, contra una meta del 90 %. En cambio cumplen: texto literal 100 %, síntesis sin juicio 100 %, "no se encontró" 90 de 100, renglones 6 de 6 y documentación técnica 3 de 3. El diagnóstico de T-146 (`specs/008-ofertas-ficha/verificacion/T-146.md`) muestra que el método de búsqueda de pasajes parecidos es el límite: en 16 a 19 de los 30 fragmentos que faltan, el pasaje correcto llega con puntaje casi nulo, aun con el requisito reescrito; bajar el umbral solo agrega hallazgos falsos.

## Decisión

1. La 008 se cierra con la ficha actual. La ficha nunca inventa: cuando no encuentra respaldo dice "no se encontró" y la Comisión revisa.
2. El criterio de aceptación de REQ-039 se enmienda: bloquean el texto literal (100 %) y que ningún hallazgo se presente sin respaldo; el 90 % de fragmentos encontrados se mide y se informa, y pasa a ser meta de la 004.
3. La 004 (evaluación asistida) se diseña desde el inicio con **lectura completa de los documentos de la oferta por requisito** (las ofertas tienen pocas páginas), no solo con los pasajes que trae la búsqueda; la ficha queda como apoyo.
4. Van a la revisión con el primer producto: la medición que no reconoce las copias deduplicadas (`copy_of`), y la lista esperada del caso-00, que debe sumar los cuadros del Portal.

## Alternativas

- B. Tarea nueva en la 008 para que la ficha lea las páginas completas: mejora la ficha ya, pero suma uno o dos días antes de la 012 y la 004.

## Consecuencias

- Spec 008: enmienda de REQ-039.
- La spec y el plan de la 004 parten de la lectura completa por requisito y miden contra el 90 %.
