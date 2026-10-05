# T-120, diagnóstico 5: resultado de la ronda 1 (commit fb8f1b6) en los casos 01, 05 y 06 (REQ-031)

Solo diagnóstico: no se cambió código, tests, datos, contenedores ni corridas. Sin modelo y sin GPU. Fuentes: las corridas `20261005-040058-fb8f1b6` (caso-01), `20261005-042138-fb8f1b6` (caso-05) y `20261005-043319-fb8f1b6` (caso-06), sus `parametros.json` y `resultados.jsonl`; lecturas de solo lectura de `tenders_run_step`, `tenders_requirement_source`, `tenders_requirement_quote` y `tenders_segment` (corridas de base: caso-01 run 15 contra 18, caso-05 run 16 contra 19, caso-06 run 17 contra 20); el código a fb8f1b6 (`archivo:línea` de ese commit). Sin texto del pliego ni de las circulares: ids y fragmentos de pocas palabras. `R-N` es el número de requisito de la versión; `Qn` es el alias de cita en el pedido de respaldo.

## Resumen

| Pregunta | Resultado | Causa |
|---|---|---|
| 1. caso-06: M-005 `suprimido_por_circular` | El modelo de extracción dijo `aclara` para las tres cláusulas. El código no pudo anclarlas (`clave_ambigua`), las mandó al **respaldo**, y el respaldo (instrucciones v2, sin la clasificación anterior) devolvió `suprime` sobre la cita de M-005. Nada en el código lo frena y `run.py:707` lo pasa a `quitado` | Camino `aclara` a respaldo a `suprime` (defecto de producto, grave) |
| 2. caso-05: ¿actuó la ronda 1? | **Sí.** D4 pasó a ser un apartado (el "I.-" se reconoce) y todos los pedidos usaron v4. Sin cambio en REQ-031 porque ningún obstáculo restante era de los que corrigió la ronda | Siguen B (`clave_ambigua`), y respaldo sin candidatas de renglón |
| 3. caso-01: M-044 | Efecto de `has_circular_obligation` (la palabra "deben" en el último tramo), no variación del modelo ni de `_LABELED`. **M-015 cumple ahora** | La ronda 1 rompió la clasificación como datos del trámite de D15 |
| 4. `parametros.json` | **Defecto de la medición confirmado:** `circulares_cambios` no está en `prompt_versions` de la corrida. Sí queda en cada pedido (`request.instrucciones`) | `run.py:331-334` |
| 5. Correcciones | Ver la sección 5. La primera es un freno al `suprime` que no entra en T-120 | |

## 1. caso-06: de una aclaración a `suprime` sobre M-005

Circular D2 (`IF-2026-02677035`), unidad `apartado` con los tramos `pre/p-9`, `pre/p-10`, `pre/p-11`, `pre/p-12` y `pagina-2`. Cadena de pasos de la corrida (run 20 de la base):

| Paso (`tenders_run_step`) | Pasada | Instrucciones | Qué pasó |
|---|---|---|---|
| 2488 | `circulares` (sin modelo) | no aplica | `motivo: sin_verbo_reconocible`, `resultado: respaldo`. **Ya no es dato del trámite**: la causa A (diag. 4) quedó corregida y el modelo ve la unidad |
| 2489 | `circulares_cambios` | **`matriz-circulares-v4`** (en `request.instrucciones`) | El modelo devolvió tres cambios, los tres `aclara`, objetivo `clausula`, referencias "7.1", "12.10" y "21.3", con `texto_anterior` vacío y el `texto_nuevo` de la respuesta. Esto es lo que la lista espera (`precisa`/`aclara`) |
| 2490 | `circulares` (sin modelo) | no aplica | Los tres cambios quedaron con `motivo: clave_ambigua`; `fuentes: []`; `resultado: aplicada` (el rótulo es engañoso: no se aplicó nada) |
| 2491 a 2495 | `circulares` (modelo, respaldo por tramo) | **`matriz-circulares-v2`** (la de la pasada de respaldo, `settings.py:279`) | Los cinco tramos de la unidad fueron al respaldo. En `pre/p-11` (pedidos 2493 y 2494, el segundo reintento por `circular_texto_no_encontrado`) el modelo devolvió tres efectos |

Los tres efectos del respaldo sobre `pre/p-11`, con las citas que el pedido mostró (Q3 y Q4 son las dos citas de 7.1):

| Cita | Requisito | Efecto devuelto | Resultado |
|---|---|---|---|
| Q3 (7.1, primera cita) | R-14 (M-004) | ninguno | Sin fuente: M-004 falla los puntos 1 a 4 |
| Q4 (7.1, "en caso que… Requiere presentar en Mesa de Entrada… físicamente") | R-15 (M-005) | **`suprime`**, texto "resulta suficiente la carga de la documentación de forma electrónica…" | Fuente `suprime` de 92 caracteres, requisito en estado `quitado` |
| Q7 (12.10) | R-53 (M-025) | `aclara`, fragmento de 63 caracteres ("Ello sin perjuicio de lo establecido…") | Fuente `aclara`; cubre menos de la mitad del ancla vigente (la respuesta entera es de 544 caracteres): punto 3 en falso |
| Q15 (21.3) | R-103 | `aclara`, pero el texto copiado con puntos suspensivos no se encontró (`ubicado: false`) | La fuente de R-103 sí quedó, con el tramo entero de 544 caracteres (`wide`) |

### Por qué terminó en `suprime` (archivo:línea)

1. **El modelo de extracción acertó y el código lo descartó.** `_pool_for` (`circular_changes.py:249-250`): un cambio `aclara` sobre una cláusula con más de una cita y sin texto anterior devuelve `FALLBACK_AMBIGUOUS`. 7.1 tiene dos citas (R-14 y R-15), 12.10 dos (R-53 y la sugerida R-54), 21.3 dos (R-102 y R-103). Es la causa B de los diagnósticos 3 y 4, que la ronda 1 no tocaba.
2. **Todos los tramos van al respaldo.** `_resolve` (`circular_changes.py:~487-499`): sin ningún cambio aplicado (`not applied`), `fallback = [m for m in members if m not in data]`, es decir los cinco tramos.
3. **El respaldo no sabe lo que dijo la extracción.** `Processor._fallback` (`circulars.py:~934`) llama a `_tramo` con el texto del tramo y las ocho mejores citas del reranker; el pedido (2493) no lleva el tipo `aclara` que el modelo había decidido en 2489. Las instrucciones v2 dejan al modelo elegir entre `modifica`, `aclara` y `suprime`; solo dicen "ante la duda entre modifica y aclara, elegí aclara", **no hay una regla equivalente para `suprime`**.
4. **Nada comprueba el efecto.** `Processor._apply` (`circulars.py:1041-1066`) copia el efecto del modelo a una `Source` sin validar que el texto citado diga que algo queda sin efecto. `_note` (`circulars.py:1011-1013`) marca la cita como suprimida para las circulares siguientes.
5. **`suprime` cambia el estado de la fila.** `run.py:707-709`: toda fuente `suprime` sobre un requisito no técnico lo pasa a `quitado`. Ahí se produce el `suprimido_por_circular` de la medición.

Sobre la lectura del modelo: la respuesta dice que alcanza la carga electrónica, y la cita Q4 exige además presentar en papel si el portal lo pide; una lectura literal puede ver ahí una supresión. La lista del responsable la tiene como `precisa`, y la decisión de fondo de qué es cada cosa no es mía. Lo grave no es la lectura sino que **una lectura dudosa llega como hecho**: la fila queda `quitado` sin que ningún control distinga una frase explícita de una interpretación (principio P3). Una corrida con otra semilla podría producir `suprime` sobre otras filas.

### Cómo se compara con la corrida anterior

En la corrida `026259…` la unidad era "datos del trámite" y el modelo no la veía; ahora la ve, pero la ruta de respaldo la rompe. El resumen del caso-06 pasó de "fuente genérica `modifica`" a "`suprime` sobre una condición real". La estimación del diagnóstico 4 se confirma: sin corregir B, la causa A solo cambia el modo de fallar. Resultados por fila del caso-06 con fb8f1b6:

| Fila | Estado | Puntos en falso | Origen |
|---|---|---|---|
| M-004 (R-14) | no cumple | 1, 2, 3 y 4 | Sin fuente (el respaldo no devolvió efecto para Q3) |
| M-005 (R-15) | no cumple | 1 a 4 | Efecto `suprime` (debía ser `aclara`) |
| M-025 (R-53) | no cumple | 3 | `aclara` correcta, fragmento de 63 caracteres menos de la mitad del ancla |

## 2. caso-05: la ronda 1 actuó, pero no tocaba lo que falta

Pasos de `circulares` y `circulares_cambios` de la corrida (run 19) contra la anterior (run 16).

| Circular | Corrida anterior (run 16) | Con fb8f1b6 (run 19) |
|---|---|---|
| D2 (primera) | unidad `apartado` pre/p-9 a pagina-2; v3 devolvió tres cambios `aclara` con objetivo `ninguno`; `sin_objetivo` | Misma unidad; **v4 devolvió cuatro cambios `aclara`** (cláusulas "18", "18.3", "6" y el anexo "VII"): efecto de las reglas "un cambio por cláusula" y "un cambio por objeto". Resultado: `clave_ambigua` y `texto_anterior_sin_coincidencia` y respaldo |
| D4 (tercera) | **Sin apartado**: 18 tramos `suelto` (pre/p-1 a pre/p-18), cada uno por separado, sin su consulta | **Apartado `pre/p-9` a `pre/p-18`** (10 tramos): el encabezado "I.-" **se reconoce** (`circular_units.py:134-135`; `circulars.py:118`). Un pedido a v4 con la unidad entera |

**Se reconoció "I.-" y se usó la v4.** Todos los pedidos `circulares_cambios` de la corrida dicen `matriz-circulares-v4` en `request.instrucciones` (por ejemplo 2319, 2336, 2381). Lo que la ronda hizo está visible en las unidades; lo que no cambia el resultado es lo que sigue.

### Por qué REQ-031 sigue en 2 de 8

| Fila (circular) | Qué pasó con fb8f1b6 | Por qué no cambió |
|---|---|---|
| M-066, M-067, M-068 (D4, `pre/p-13`, renglones 1 a 3) | Paso 2381 (v4): tres cambios `aclara`: "6.4", "26.2" y un tercero con **objetivo `ninguno` y referencia vacía** (el de `pre/p-13`: la respuesta que "ratifica los plazos de entrega" de un bien, sin nombrar renglón ni cláusula). `_pool_for` llega a la rama final (`circular_changes.py:~268-269`): sin objetivo y sin texto anterior, `FALLBACK_NO_TARGET` (`sin_objetivo`). El tramo va al respaldo (paso 2383) | La regla nueva de v4 ("ítem vale como renglón", "un cambio por renglón") solo actúa si la respuesta **nombra** el ítem. Acá no lo hace. El respaldo ve ocho citas del reranker, de las cuales ninguna es de renglón (la lista de renglones del pedido es vacía) y devuelve `sin_efecto: dato_procedimiento`. Misma situación que en la corrida anterior |
| M-046 (D2, `pre/p-16`) | Los cambios "6" y el anexo "VII" quedan sin anclar: "6" tiene varias citas y no hay texto anterior, el anexo sin texto anterior (`circular_changes.py:262-263`: `_from_old_text` con `FALLBACK_NO_OLD_TEXT`, solo `suprime` toma el pool sin texto anterior). Respaldo (2345): `sin_efecto: titulo` | Causa B, sin cambio |
| M-059 (D2) | Sin fila: el tramo `sec-i/18.1/tabla-1` quedó pendiente | Lectura de tablas (diag. 3, 1a), no es de circulares |
| M-060 (D2, `pre/p-15`) | R-133 (18.3) tiene una fuente `aclara` de **73 caracteres** copiada por el respaldo de `pre/p-11` (paso 2340) | Punto 3 sigue en falso: el fragmento no cubre la mitad del ancla (diag. 3, grupo C). v4 pide oraciones completas, pero esa fuente no vino de la extracción por clave: vino del respaldo |
| M-005, M-063 (D4; las dos que ya cumplían) | Ahora las fuentes de R-21 (6.4, 288 caracteres) y R-149 (26.2, 469 caracteres) vienen del **paso 2381** (extracción, v4), antes del respaldo | Cumplen, igual que antes. Es una mejora de origen, no de cantidad |

La ronda sirvió para que D4 se lea completa y para que v4 parta las cláusulas, pero **el cuello de botella sigue después de la extracción**: `clave_ambigua` y el respaldo sin candidatas de renglón.

## 3. caso-01: M-044 y M-015

**M-015 cumple ahora** (`resultados.jsonl`: `estado: cumple`, `fila: 328`, `effect`, `original`, `current` y `document_date` verdaderos). La corrección C de la ronda 1 (`debe/deben`) funcionó.

**M-044 dejó de cumplir** (`fila: 86`, los cuatro puntos en falso) y la causa **no es variación del modelo**:

1. La circular D15 ("II. SE FIJAN NUEVAS FECHAS DE VISITA") es un `apartado` de 64 tramos (`pre/p-15` a `pre/p-78`). En la corrida anterior (run 15, paso 1585) `is_procedure_data` la clasificó como datos del trámite y `_resolve_data` (`circular_units.py:841-872`) fabricó una fuente `modifica` (R-86, `pre/p-16`, "AZOPARDO N° 350…") sobre las fechas de visita. Ese `modifica` es lo que M-044 esperaba.
2. Con fb8f1b6 la unidad ya **no** es dato del trámite (paso 2172: `sin_verbo_reconocible`, `respaldo`) y va al modelo (paso 2173, v4). El modelo devolvió **un cambio `dato_del_tramite`**, objetivo `ninguno`, `texto_nuevo` vacío. `resolve_change` (`circular_changes.py:~291-292`) devuelve `[], [], ""` para `CHANGE_DATA`: no se produce ninguna fuente. Resultado: `dato_del_tramite`, sin efectos (paso 2174), R-86 sin fuente.
3. **Qué cambió la clasificación.** Reproduje con los tramos de la base las dos condiciones de `is_procedure_data` (`circular_units.py:796-812`):

| Condición | Antes de fb8f1b6 | Con fb8f1b6 |
|---|---|---|
| Líneas con marcadores de obligación (lista de `run.py:133-144`) | 0 | 0 |
| Líneas con marcadores nuevos (`_CIRCULAR_OBLIGATION`) | no se buscaba | **1: `pre/p-78`**, "SE RECUERDA QUE DEBEN CONCURRIR CON EL CERTIFICADO…" (la palabra "deben") |
| Líneas rótulo y valor (63 líneas de cuerpo) | 40 | 40 (el valor corto de `_LABELED` no cambia nada acá) |
| Líneas cortas sin rótulo | 22 | 22 |
| Participaciones (mínimos 0,3 y 0,6) | 0,63 y 0,98 | 0,63 y 0,98 |

   Todo es igual salvo el marcador: `is_procedure_data` hace `if any(has_circular_obligation(...)) return False` (`circular_units.py:~806-807`) y una sola línea de recordatorio basta para descalificar una lista de 63. **No es el cambio de `_LABELED` ni "corresponde" (no aparece en la unidad): es "deben" en el último tramo.**
4. Además, el prompt v4 (`matriz-circulares-v4.md:40`) dice que una lista de líneas cortas con rótulo y valor, aunque reemplace un anexo, es `dato_del_tramite`, y `resolve_change` no produce efecto para ese tipo. Entonces, **con el modelo en el camino, un cambio de fechas de visita nunca produce una fuente `modifica`**: la medición anterior cumplía por el atajo del código, no por el modelo.

Efecto colateral del mismo cambio en las otras circulares del caso-01: D16 ahora cumple (M-015), y el resumen de la corrida da 14 de 15 por M-044 solamente.

## 4. `parametros.json` y las instrucciones `circulares_cambios`

- **Confirmado: la v4 no queda registrada en `prompt_versions`.** Los tres `parametros.json` de fb8f1b6 traen `filtro`, `respaldo`, `circulares` (`matriz-circulares-v2`), `extraccion`, `completitud` y `consecuencias`, y ningún `circulares_cambios`. La base lo confirma: `prompt_versions` de los runs 15, 16 y 17 y de los runs 18, 19 y 20 es el mismo diccionario de seis claves.
- **Causa:** `_begin` (`run.py:331-334`) arma `names` con `extraccion`, `completitud`, `filtro`, `circulares` y `consecuencias`; `circulares_cambios` no está en la lista. `Extractor.__init__` (`circular_changes.py:333-334`) sí lee `settings.MATRIX_PROMPT_VERSIONS["circulares_cambios"]` y lo guarda en cada pedido (`circular_changes.py:~358`, `request.instrucciones`), de modo que **la trazabilidad por pedido existe** (P6), pero no la de la corrida.
- **Es un defecto de la medición:** quien lea `parametros.json` o `prompt_versions` ve solo `matriz-circulares-v2` y no puede saber con qué instrucciones de extracción se midió (las corridas de las rondas anteriores usaron v3; esta, v4). Para cada medición de T-120 se confirmó la versión en los pedidos (v3 en los runs 16 y 17, v4 en los runs 19 y 20; el run 15 y el 18 del caso-01 no se contrastaron pedido por pedido), no en el registro de la corrida.
- Además, `circulares` aparece como v2 aunque esa pasada tiene dos instrucciones distintas desde T-115 (respaldo y extracción): conviene un nombre por instrucción.

## 5. Correcciones, por impacto

### Ordenadas

| # | Corrección | Dónde | Filas / efecto | Entra en T-120 |
|---|---|---|---|---|
| 1 | **Freno al `suprime`**: un `suprime` solo es aceptable si el texto citado dice explícitamente que algo queda sin efecto ("sin efecto", "suprim-", "elimin-", "no será exigible", "déjase", "derógase"). Si no, bajarlo a `aclara` (o a sugerencia). Además, **si la extracción por clave dijo `aclara` para esa cláusula y el respaldo dice `suprime`, gana `aclara`** | `circulars.py:1041-1066` (`_apply`) y/o `run.py:707-709`, que pasa a `quitado` | Evita el peor error: decirle a la Comisión que una condición real dejó de regir. M-005 pasaría a `aclara` | **No** (código de producto; el alcance de T-120 son constantes, listas de verbos e instrucciones). Es un hallazgo bloqueante para el piloto: otra tarea, antes de T-108 |
| 2 | **`aclara` sobre una cláusula con varias citas y sin texto anterior**: aplicar la aclaración a **todas** las citas de la cláusula nombrada (efecto `aclara`, inocuo) en vez de `clave_ambigua`; lo mismo para un anexo nombrado sin texto anterior | `circular_changes.py:249-250` y `262-263` | Caso-06: M-004, M-005 y M-025 con hasta 3 de 3 (requiere que 1 no sea necesario para M-005); caso-05: M-046 con el anexo. Quita el camino de la corrección 1 en la mayoría de los casos | **No** (código y criterio de producto). Consultar al responsable: afirma una `aclara` sobre varias citas. Misma tarea que la 1 |
| 3 | **Datos del trámite tolerante a un recordatorio**: `is_procedure_data` debe tolerar una fracción pequeña de líneas con marcador (por ejemplo, hasta el 5 %) en lugar de `any(...)`; o volver a la lista de `has_obligation_markers` en esa función y dejar `has_circular_obligation` solo para `_added_obligations`/`_resolve_addition` (`circular_units.py:584`, `:781`) | `circular_units.py:~806-807` (constante nueva `DATA_MAX_MARKED_SHARE` o cambio de la función) | caso-01: M-044 de nuevo (vuelve el atajo). La consulta-y-respuesta de caso-06 y caso-05 queda cubierta por `_QUESTION_LINE`, no depende de esta condición | **Sí** (constantes y listas, el cambio se limita a una línea). Medir 01 y 06 de nuevo |
| 4 | **`dato_del_tramite` que reemplaza algo del pliego**: que el modelo pueda decir `reemplaza` para "nuevas fechas de visita" y que el código lo anclee; o, en el código, que un cambio `dato_del_tramite` de la unidad entera vuelva a pasar por `_resolve_data` | `matriz-circulares-v4.md:40` (el prompt dice lo contrario) y `circular_changes.py:~291` | Hace que M-044 no dependa de un atajo; también quita la fabricación de `modifica` de caso-06 si se hace con cuidado | Instrucciones: **sí** (v5, una frase); código: no |
| 5 | **Registrar `circulares_cambios` en `prompt_versions`** (y un nombre por instrucción) | `run.py:331-334` (`names`) | Mide lo que se dice medir (P6, P8); no cambia filas | **Sí** si se acepta el cambio de una línea en `run.py`; si no, otra tarea |
| 6 | **Respaldo sin candidatas de renglón para respuestas sin objetivo** (M-066 a M-068): cuando la extracción devolvió `aclara` con objetivo `ninguno`, el respaldo debe recibir como candidatas las citas que mencionan el bien o el plazo, no solo las ocho del reranker | `circulars.py:664-670`; `circular_changes.py:~268` | Caso-05: hasta 3 filas (M-066 a M-068) | **No** (código) |
| 7 | **Fragmento corto de una `aclara` del respaldo** (M-060, M-025): copiar la oración completa o la respuesta entera | Instrucciones v2 del respaldo; o v3 con la misma regla que v4 | Punto 3 de M-060 y M-025 | **Solo si** se autoriza una versión nueva de `matriz-circulares-v2.md` (no figura en la lista de archivos de T-120). Si no, otra tarea |
| 8 | Fila para tramos de tabla pendientes (M-059) y granularidad de la lista (M-039) | Lectura de tablas; instrucciones de extracción | M-059; M-039 | **No** (otra tarea y decisión del responsable, ya dicho en los diagnósticos 3 y 4) |

### Qué entra en T-120 (resumen) y lo que se puede esperar

Dentro del alcance de T-120 (constantes, listas y prompts de circulares) entran 3 y 4 (instrucciones) y 5 (una línea, a decidir). Con 3, el caso-01 vuelve a 15 de 15. Los casos 05 y 06 **no mejoran con nada que entre en T-120**: la causa raíz (B, y el respaldo) es de código. Quedan dos opciones para el Coordinador, que no decido yo: (a) acordar con el responsable una excepción de alcance de T-120 para las correcciones 1 y 2, que son pocas líneas y de alta consecuencia; o (b) cerrar T-120 con las constantes y abrir una tarea nueva con 1, 2 y 6, y medir de nuevo con el segundo ajuste que permite `tasks.md`. Mi recomendación es (a) o (b) con **1 antes de cualquier uso del resultado**.

### Cualquier camino por el cual una `aclara` puede terminar en `suprime`

Revisé todos los puntos donde se escribe o se hereda un efecto:

1. **Respaldo (`circulars.py:1041-1066`)**: es el camino real. Cualquier cambio que la extracción no pueda anclar (`clave_ambigua`, `sin_objetivo`, `texto_anterior_sin_coincidencia`, `no_verificado`, `no_estable`, `ubicado: false`) llega al respaldo con el tramo solo, sin el tipo ya decidido, y el modelo puede elegir `suprime`. No hay una validación del texto citado. **Es el único camino para esta falla.**
2. **Extracción por clave (`circular_changes.py:312-316`)**: el efecto sale del tipo que dio el modelo (`aclara` da `ACLARA`); la extracción solo da `suprime` si el modelo dijo `suprime`. No hay conversión de `aclara` a `suprime`.
3. **Resolución por reglas (`circular_units.py:762`)**: `suprime` solo con el verbo de supresión detectado en el encabezado. Seguro.
4. **`_resolve_data` (`circular_units.py:841-872`)**: fabrica `modifica`, no `suprime` (caso-06 con el diagnóstico 4). Con la corrección A ya no ve unidades de consulta.
5. **`run.py:707-709`**: la consecuencia, no el origen. Cualquier fuente `suprime` sobre un requisito no técnico lo deja `quitado` sin pasar por una persona; es la razón de que la corrección 1 sea bloqueante.

### Medición que corresponde después

Con 3 y 4 (instrucciones) y el registro de versión: caso-01 (objetivo: M-044 y M-015 a la vez, 15 de 15; mirar que D15 siga siendo datos y que el recordatorio de visita no se pierda sin dejar rastro) y caso-06 (verificar que **M-005 deje de ser `suprimido_por_circular`**, o que la corrección 1 se haya hecho antes). No ajustar más de la ronda 2 que prevé `tasks.md`.
