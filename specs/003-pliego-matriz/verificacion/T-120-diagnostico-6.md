# T-120, diagnóstico 6: resultado de la ronda 2 (commit 939f9fb) en los casos 01, 05 y 06 (REQ-031)

Solo diagnóstico: no se cambió código, tests, datos, contenedores ni corridas. Sin modelo y sin GPU. Fuentes: las corridas `20261005-062859-939f9fb` (caso-01), `20261005-064845-939f9fb` (caso-05) y `20261005-070000-939f9fb` (caso-06), sus `resultados.jsonl` y `resumen-publico.md`; lecturas de solo lectura de la base real (runs 21, 22 y 23: `MatrixRun.anomalies`, `RunStep`, `RequirementSource`); el código a 939f9fb (`archivo:línea` de ese commit). Sin texto del pliego ni de las circulares: ids y fragmentos de pocas palabras. Las tres corridas registran `circulares_cambios: matriz-circulares-v5` en `prompt_versions` (T-127 c, corregido).

## Resumen

| Caso | REQ-031 | Qué pasó | Causa |
|---|---|---|---|
| 06 | 3 de 3; encontrados 47 de 47 | M-004, M-005 y M-025 cumplen | La extracción (v5) dijo `aclara` y T-128 la aplicó a todas las citas de la cláusula: ya no hay `clave_ambigua` ni respaldo |
| 01 | 13 de 15 | M-025 y M-026 fallan el punto 1 (efecto): la fila queda `aclara`, se esperaba `suprime`. M-044 y M-015 cumplen | La lista de frases de supresión no reconoce el sustantivo "eliminación" |
| 05 | 4 de 8 | M-066, M-067 y M-068 pasaron efecto y original, pero fallan texto vigente y documento y fecha; M-059 sigue pendiente | La extracción v5 sí devolvió los tres cambios de renglón; el código no los aplica (`aclara` de renglón sin texto anterior) y las filas heredan aclaraciones de otra circular |

## 1. caso-06: qué lo resolvió

Run 23. En el paso 3055 (`circulares_cambios`, instrucciones v5) el modelo devolvió cambios `aclara` sobre las cláusulas 7.1, 12.10 y 21.3, sin texto anterior. Antes (diagnóstico 5) `_pool_for` los frenaba con `clave_ambigua` porque cada cláusula tiene dos citas, y todo caía al respaldo, que inventaba `suprime` sobre M-005. Ahora `_pool_for` devuelve todas las citas de la cláusula (`circular_changes.py:249-251`, T-128) y el paso 3056 las aplica por clave: R-14 y R-15 (7.1), R-53 y R-54 (12.10), R-102 y R-103 (21.3), las seis con efecto `aclara`. No hubo respaldo para esa unidad, no hay `suprime` y no hay marca de supresión sin frase. La resolución viene de T-128 con la extracción en v5; el freno de T-127 queda como red de seguridad que no hizo falta.

Costo visible: R-54 (sugerida), R-102 y R-103 reciben `aclara` (2 fuentes ajenas en 2 filas). Es inherente a la decisión del responsable del 2026-10-05.

## 2. caso-01: M-025 y M-026 (D15, punto 1)

| Pregunta | Respuesta |
|---|---|
| Qué esperaba la lista | `suprime` en las dos (sec-i/7.6.5, circular D15 del 2026-07-15), con `texto_vigente: null` |
| Qué dice la circular | "se dispone la eliminación de la subcláusula 7.6.5" |
| Qué hizo el modelo | Un cambio `suprime`, objetivo cláusula, referencia 7.6.5 (extracción v5). Correcto |
| Por qué no lo reconoce `has_suppression_phrase` | `circulars.py:99-101`: `_SUPPRESSION_PHRASE` solo tiene formas verbales (`se suprim-`, `se elimin-`, `se derog-`, `suprimase`, `eliminase`, `derogase`, `queda(n)/dejase sin efecto`, `no sera exigible`, `queda derogad-`). "Se dispone la **eliminación** de" es un sustantivo y ninguna alternativa lo cubre (`se elimin-` exige "se" pegado). La comprobación que actuó es la de `circular_changes.py:319-320` (la del respaldo está en `circulars.py:1100`) |
| Anomalía `circular_supresion_sin_frase` | **Sí apareció**, una vez, en `MatrixRun.anomalies` del run 21: circular D15 (15/07/2026), cambio `suprime`, referencia 7.6.5, resultado `aclara`, `review_required: true`, requisitos 47, 48 y 49 |
| Efecto sobre las filas | R-47 (M-025), R-48 (M-026) y R-49 (otra cita de 7.6.5, ajena a la lista) quedan `propuesto` con fuente `aclara` en lugar de `quitado` |

Sospecha confirmada, con un matiz: el freno de T-127/T-128 funcionó como se diseñó; el defecto es la lista de frases, que deja una supresión real, con redacción clara, como `aclara` con marca de revisión. Por eso M-025 y M-026 salieron de "suprimidas por una circular y encontradas" (quedan 9: M-029 y M-087 a M-094, que sí traen la frase verbal).

**Corrección propuesta:** sumar a `_SUPPRESSION_PHRASE` formas nominales atadas a un objeto de pliego (texto sin tildes ni mayúsculas):

- `(?:eliminacion|supresion|derogacion)\s+de\s+(?:la\s+|el\s+|las\s+|los\s+)?(?:sub-?)?(?:clausulas?|articulos?|puntos?|apartados?|numerales?|incisos?|anexos?|renglon(?:es)?)`
- `(?:resuelve|dispone|establece)\s+(?:suprimir|eliminar|derogar)` (infinitivo)
- opcionalmente `se\s+(?:anula\w*|excluye\w*)`, a decidir con el responsable (menos inequívocas).

El objeto obligatorio evita que "eliminación de errores" o "supresión de la visita" se tomen como supresión de una cláusula. Tests: la frase de M-025 (falla hoy) y el adverso "eliminación" sin objeto de pliego, que sigue como sugerencia.

M-044 (D15, `modifica`) y M-015 (D16, `agrega`) cumplen los cuatro puntos.

## 3. caso-05

### M-066, M-067 y M-068 (D4, `pre/p-13`, renglones 1 a 3): puntos 3 y 4

La extracción **sí** hizo su parte. En el paso 2947 (v5) el modelo devolvió cinco cambios `aclara` de D4: cláusulas 6.4 y 26.2, y **tres de objetivo `renglon` con referencias 1, 2 y 3** (la respuesta que ratifica los plazos de entrega). v5 resolvió lo que v4 dejaba en `ninguno`. Pero esos tres no llegan a fuente:

1. `_pool_for`, rama `renglon` (`circular_changes.py:252-263`): encuentra las citas del renglón (`_item_candidates`, `circular_units.py:513-514`), pero con `change.old_text` vacío solo acepta `suprime` (`:260-262`); para `aclara` devuelve `FALLBACK_NO_OLD_TEXT` (`:263`, que se escribe `texto_anterior_sin_coincidencia`). La rama de cláusula (`:249-251`) y la de anexo (`:270-273`) sí admiten `aclara` sin texto anterior por T-128; la de renglón quedó fuera.
2. Las tres anomalías `circular_cambio_sin_resolver` del run 22 (renglones 1, 2 y 3) lo registran. El respaldo (paso 2949, `pre/p-13`) devuelve `sin_efecto`.
3. Las filas 221 a 223 sí tienen fuente `aclara`, pero **de D2** (2026-07-02): los cambios sobre la cláusula 18 y sobre cantidades a cotizar (paso 2911) que T-128 aplicó a todas las citas, incluidas las citas 18.2.x y 6/tabla que usan las filas de renglón. La medición toma la mejor fuente de la fila: efecto y original cumplen por coincidencia (aclaración que no es la esperada); texto vigente (`evaluation.py:1010`, `covers_text`) y documento y fecha (`:1011`) fallan porque la fuente es de D2.

**Corrección:** que `aclara` de renglón sin texto anterior se aplique a las citas de ese renglón, igual que cláusula y anexo (`circular_changes.py:260-263`, aceptar `CHANGE_CLARIFIES` donde hoy solo acepta `CHANGE_SUPPRESSES`). Riesgo: un renglón tiene muchas citas por fila técnica (secciones I y III); aplicar a todas multiplica el ruido (hoy 0 en esas filas). Conviene confirmarlo con el responsable, como en T-128, o limitarlo a una cita por fila.

### M-059

Sigue sin fila: el tramo `sec-i/18.1/tabla-1` está pendiente por tabla (a revisión obligatoria), el requisito no se creó y no hay dónde colgar la fuente de D2. Es de lectura de tablas, no de circulares; sin cambio desde el diagnóstico 5.

### Fuentes ajenas del caso-05 (19 en 16 filas, antes 0)

Las crea T-128. Las 19 salen de un mismo paso (2911, D2) con cambios `aclara` sin texto anterior sobre la cláusula 18, la 18.3 y las cantidades a cotizar: cada cita de la cláusula recibe la aclaración (R-15 a R-20, R-55, R-97 a R-103, R-134, R-135, R-224 y otras). Antes esos cambios quedaban en `clave_ambigua` y no daban fuentes. Es la decisión del responsable aplicada; con la lista (una fila esperada por circular) cuentan como ruido, no como error de la IA. Con ruido 0 como meta, hace falta una regla más fina (por ejemplo, aplicar la aclaración solo a la cita que el texto de la respuesta menciona), que sale del alcance de T-128.

### Fuentes ajenas del caso-01 (24 en 24 filas)

Solo **1** es de T-127/T-128: R-49, otra cita de 7.6.5 que recibe la `aclara` de la supresión degradada (con la corrección 1 pasaría a `suprime`, efecto coherente con la supresión de la cláusula entera). Las otras 23 vienen de antes de estas tareas: 18 `suprime` de D15 sobre citas de cláusulas suprimidas (efecto preexistente "un `suprime` con frase y sin texto anterior alcanza todas las citas de la cláusula", anotado en `tasks.md`) y 5 `modifica` de D16 sobre la cadena 7.5.5. No las crea T-128.

## 4. Marcas de revisión obligatoria de supresión (`circular_supresion_sin_frase`)

| Caso | Marcas | Detalle |
|---|---|---|
| caso-01 (run 21) | **1** | D15, cláusula 7.6.5; afecta 3 requisitos (R-47, R-48, R-49). Supresión real degradada por la lista de frases (sección 2) |
| caso-05 (run 22) | 0 | |
| caso-06 (run 23) | 0 | |

Contadas en `MatrixRun.anomalies` y en `RunStep.anomalies` de los tres runs (en los pasos no hay ninguna). El resumen de la medición del caso-01 no la cuenta: lista como "a revisión obligatoria" a M-059 y M-055, pero no la supresión de M-025 y M-026 (aviso de T-127).

## 5. Correcciones

| # | Corrección | Dónde | Qué arregla | De quién | Riesgo |
|---|---|---|---|---|---|
| 1 | Formas nominales y de infinitivo en la lista de frases de supresión ("la eliminación de la subcláusula", "se dispone suprimir"), siempre con objeto de pliego | `circulars.py:99-101` (`_SUPPRESSION_PHRASE`) | caso-01: M-025 y M-026 (15 de 15); R-49 pasa a `suprime`; desaparece la marca | Lista de constantes pero en código de T-127: de T-120 solo si se amplía su lista de archivos; si no, tarea aparte | Bajo, con objeto de pliego obligatorio; el adverso "eliminación" sin objeto debe seguir como sugerencia |
| 2 | `aclara` de `renglon` sin texto anterior se aplica a las citas del renglón | `circular_changes.py:260-263` | caso-05: M-066, M-067 y M-068 (puntos 3 y 4); 7 de 8 | Código de otra tarea (T-128) | Medio: más fuentes por fila técnica (hoy 0); confirmar con el responsable o limitar a una cita por fila |
| 3 | Fila para un tramo de tabla pendiente | lectura de tablas | caso-05: M-059 (8 de 8) | Otra tarea | Alto; fuera de alcance |
| 4 | Contar aparte las marcas de supresión sin frase en el resumen de la medición | `evaluation.py` (informe) | Que la medición no esconda una revisión obligatoria; aviso de T-127 | Otra tarea (medición) | Bajo |
| 5 | Ruido de la aclaración a todas las citas de la cláusula (19 en caso-05, 2 en caso-06) | decisión del responsable, no defecto | Solo si se quiere ruido 0 | T-128 | Medio: reglas más finas; choca con la decisión tomada |

Con 1 y 2 se espera: caso-01 15 de 15, caso-05 7 de 8 (queda M-059), caso-06 sin cambio (3 de 3). La 1 es una línea y no toca el modelo; la 2 cambia el comportamiento de los renglones y necesita confirmación.

## 6. Medición que corresponde después

`tasks.md` prevé hasta dos rondas de ajuste y esta fue la segunda: aplicar 1 y 2 requiere una tarea aparte y una medición nueva de caso-01 y caso-05 (caso-06 no debería cambiar).
