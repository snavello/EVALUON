# ADR-0043 · Decisiones literales de la 004: motivos de "no determinado" y reglas antes del modelo

Estado: aceptado · Fecha: 2026-10-06 · Decidió: responsable del proyecto (aplicar las decisiones literales de la spec 004); el diseño, el Coordinador

## Contexto

La medición de la 004 dio 24 de 49 (T-161) porque el sistema no aplicaba decisiones ya tomadas por el responsable: opinaba sobre el ajuste técnico (es del área correspondiente; la Comisión da el ok del informe técnico aprobado), devolvía "duda" en requisitos externos (corresponde "falta la hoja de compliance"), no usaba el Portal y la medición contaba como desacierto el "no se pudo leer" de un documento ilegible. La spec 004 recoge ahora esas decisiones con su texto literal y los REQ-061 a REQ-064.

## Decisión

1. Los cuatro resultados (cumple, no cumple, no se encontró el documento, no determinado) no cambian. Lo nuevo son motivos de "no determinado": `pendiente_informe_tecnico`, `no_se_pudo_leer`, `en_portal`, `falta_coincidencia`; `externo` se muestra como "Falta la hoja de compliance". La pantalla muestra el motivo como resultado.
2. Una regla decide antes del modelo, en este orden: externo (catálogo en código sobre el texto del pliego más la marca del modelo), técnico (por la categoría de la fila: existencia del documento técnico y renglón ofertado), ilegible (documento señalado contrastado con el informe de lectura), Portal (datos locales de la 012). La regla queda registrada con su versión (P6).
3. Ok del informe técnico: la Comisión (evaluador) da el ok de que tiene el informe técnico aprobado, por oferta y renglón, con lo que dice el informe (`apto` / `no_apto`). Con el ok, la fila técnica pasa a cumple o no cumple con ese fundamento y un no cumple entra al descarte por renglón. El sistema no juzga lo técnico; la asistencia al informe es de la 010.
4. El Portal deja de estar fuera de alcance como fuente citada.
5. Antes de cada medición se corren los tests marcados `decision_literal`; si alguno falla, no se mide.

## Alternativas

- **Resultados nuevos en lugar de motivos:** más fiel al texto, pero cambia la lista de resultados que la Comisión elige al corregir, el descarte, la matriz y el esquema de decisiones. Descartada.
- **Marca de "externo" en la matriz de la 003:** más exacta, pero reabre una feature desplegada. Se usa un catálogo en código con test; se revisa con el primer producto.

## Consecuencias

- Una migración en `assessment` (motivos, opinión y hechos del resultado, cita del Portal, tabla del ok técnico).
- La coincidencia se mide con la regla de la spec (enmienda 2026-10-06); el residuo de "duda" se informa aparte.
