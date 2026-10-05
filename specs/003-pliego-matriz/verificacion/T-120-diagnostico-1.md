# T-120, diagnóstico 1: lo que falló en la corrida 14 del caso-01 (REQ-024, REQ-031)

Solo diagnóstico: no se cambió código, tests ni datos. Lectura de la base real (`evaluon-app-1`, `python manage.py shell`, solo consultas). Para ubicar anclas se usó la lista `matriz-esperada.yaml` del caso-01; para reproducir qué fila empareja cada esperado se llamó a las funciones de medición sin guardar nada (`load_expected`, `verify_expected`, `measure_version`); no se corrió `medir_matriz` ni se usó el modelo. Sin texto del pliego ni de las circulares: solo `M-NNN`, `R-NNN`, claves de tramo y cuentas.

Corrida 14, versión 13 (`caso-01-medicion`, 293 requisitos: 228 propuestos, 53 sugeridos, 12 quitados), código `4906d80`. Las pasadas de la entrega 1 (por clave, sin modelo) y de la entrega 2 (`circulares_cambios`, 18 pedidos) corrieron; los 26 pedidos `circulares` son unidades sin modelo y respaldo.

## Resumen

| Punto | Qué pasó | Defecto de |
|---|---|---|
| 1. Anexo VI (M-087 a M-094) | El producto las propuso y la circular las dejó `quitado` con una fuente `suprime` correcta. La medición solo mira filas firmes y las cuenta como faltantes. | Medición |
| 2. Texto original (M-025, M-026, M-029) | No es un fallo del texto original: la medición las empareja con una fila técnica equivocada por un error de comparación entre lecturas | Medición (error de código) |
| 2. Texto original (M-044) | La fuente no guarda el original: el anexo de la visita no se encontró porque el título del documento tiene guiones bajos y extensión | Producto |
| 3. M-015 | La unidad "Donde dice / Debe decir" se aplicó como `modifica` sobre 7.5.5 y nadie crea el requisito que agrega la circular | Producto |
| 4. M-058, M-063 | Se cumplieron las cuatro condiciones; el criterio del filtro falló en dos formas distintas | Producto (instrucciones y una guarda) |

Dato que cambia la lectura de los resultados: **83 de 93 está inflado**. M-025, M-026, M-029 y M-059 figuran como "encontrados con clase equivocada" por el error del punto 2 y no están en ninguna fila firme.

## 1. Filas del Anexo VI

**Qué hizo el producto (bien).** La unidad "cláusula 3" de la Circular 1 (paso 1302, sin modelo) resolvió el objetivo `anexo` "vi" con diez citas: la cláusula 7.7.1 que manda presentar el anexo (R46) y las ocho filas formales/económicas del anexo (R199 a R206), más las citas de las 18 filas técnicas. Todas recibieron una fuente `suprime` del documento 17 (Circular 1), tramo `3`, fecha 2026-07-15. R46 y R199 a R206 quedaron `quitado`, visibles y con su cita; no hay filas descartadas por el filtro en `sec-iv/anexo-vi` (0 en `DiscardedRow`). Las ocho filas existen: no es un problema de propuesta.

**Por qué la medición las da por faltantes.** `_proposed` y `measure_circulars` usan `FIRM_STATES` (propuesto y confirmado); una fila quitada no es pareja de nadie. El esperado cae en `_cause` y, como el tramo tiene otras filas (las técnicas), la causa es `tramo_con_requisitos_sin_este`. Los cuatro puntos fallan porque no hay fila. Lo mismo pasa con R39 a R41 (M-025, M-026) y R46 (M-029), quitadas por las cláusulas 2 y 3.

**Qué debería pasar.** El plan (rediseño de circulares, "Aplicación por clave") y T-119 (decisión 5 del 2026-10-04) dicen que una fila suprimida por una circular queda `quitado`, visible, con los dos textos y su cita, y que las del Anexo VI cuentan como afectadas y esperadas. Por lo tanto cuenta como encontrada: la Comisión ve la fila, ve que la circular la quitó y decide. Lo que sigue excluido es el tope de sobrantes (no son filas firmes), que no cambia.

**Arreglo general (medición, `evaluation.py`).**
1. Un esperado con bloque `circulares` de efecto `suprime` se empareja también con filas `quitado` que tengan una fuente `suprime`. Cuenta como encontrado (detalle "suprimido por circular") y es la fila que mide REQ-031.
2. Un esperado sin bloque `suprime` que solo tiene pareja quitada no se da por encontrado: causa nueva `suprimido_por_circular` en lugar de `tramo_con_requisitos_sin_este`, porque el motivo del faltante no es que el sistema no lo propuso.
3. Los sobrantes siguen midiéndose solo sobre filas firmes.

## 2. Texto original (punto 2 de REQ-031)

### M-025, M-026, M-029: error de la medición, no del texto original

Las tres filas reales (R39, R40, R41, R46) tienen la cita en el tramo correcto y su fuente conserva el original en la cita (`original_segment` nulo: es lo previsto cuando la cita alcanzada ya es el original). El punto 2 falla porque la medición empareja M-025, M-026 y M-029 con la fila técnica R276 y compara el original de **esa** fila.

Causa: `_technical_citing` (evaluation.py) pregunta si alguna cita de una fila técnica contiene las posiciones del ancla, pero compara `char_start`/`char_end` **sin comprobar que la cita sea de la misma lectura**. La cita de R276 en `anexo-iv/p-361` (lectura 16, un manual de señalética, posiciones 31656 a 32317) contiene numéricamente las posiciones del ancla en el pliego (lectura 3). Es un falso positivo por coincidencia de números entre documentos distintos. Comprobado por lectura: de los esperados que `_technical_citing` empareja, M-025, M-026, M-029 y M-059 son falsos; M-016, M-017, M-021, M-022, M-023, M-024, M-027, M-028 y M-043 son verdaderos (misma lectura).

Consecuencias: los "encontrados" suben 4 de más, la clase equivocada (6) incluye 4 falsos, y REQ-031 mide estas filas contra una fila técnica que no tiene nada que ver. Con el arreglo, M-025, M-026 y M-029 se miden contra R39, R40 y R46 (arreglo del punto 1); su punto 2 pasa porque la cita alcanzada es el original. M-059 queda en "tramo pendiente" (a revisión), no como faltante.

**Arreglo (medición):** en `_technical_citing`, exigir `quote.segment.reading_id == entry.reading.pk` en cada cita (hoy lo exige a la primera cita de la fila). Test: dos lecturas con posiciones solapadas, una fila técnica con una cita en la otra lectura, y el esperado no se empareja. Re-medir con `--regenerar-resumen` cambia las corridas anteriores del caso-01 y del caso-02: avisar al Coordinador.

### M-044: defecto del producto

La fila R76 (13.2) recibió una fuente `modifica` con el bloque entero de la lista de visitas como vigente (2708 caracteres: correcto, no es la última línea) pero `original_segment` nulo, así que el original mostrado es la cita de 13.2 y no el anexo de la visita. Pasos 1293 (unidad de 64 tramos): `cambio: dato_del_tramite`, objetivo `anexo` con referencia "fecha de visita", fuente con `original: null`.

Causa: `_find_original` (circular_units.py) busca el título del anexo dentro de `fold(título del documento)`. El título del documento 4 es el nombre de archivo (`ANEXO_FECHA_DE_VISITA.pdf`), que con `fold` queda con guiones bajos y extensión y no contiene "fecha de visita". La segunda vía (un contenedor `anexo-*` cuyo encabezado nombra el título) no aplica porque el anexo es un documento aparte cuyos tramos son `pre/p-N`. El título está en el primer párrafo del documento (`pre/p-1`), que no se mira.

**Arreglo general (producto):** normalizar el título del documento antes de comparar (guiones bajos y medios a espacio, sin extensión, sin mayúsculas ni tildes) y, si no coincide, comparar con el primer párrafo no vacío del documento. Tolerar plural/singular ("visita" y "visitas") por raíz o por inclusión de las palabras. Sigue exigiendo una sola coincidencia (si hay varias, queda sin original, como hoy). Test sintético: anexo cuyo archivo se llama con guiones bajos y cuyo título está solo en la primera línea.

## 3. M-015: lo que hizo la pasada con la Circular 2

La Circular 2 se partió en una unidad `apartado` (encabezado romano en `pre/p-9`, 10 tramos hasta `sec-i/no-ubicado-4`, paso 1319). `find_pair` detectó el par "Donde dice / Debe decir" y `_resolve_pair` lo aplicó: objetivo cláusula 7.5.5, `reemplaza`, una fuente `modifica` por cada una de las cinco citas (R23 a R27), con el lado "debe decir" entero como vigente. Resultado `aplicada`: no pasó por el modelo (`circulares_cambios` solo corrió con cabeceras y con la cláusula 2 de la Circular 1) ni por el respaldo.

El lado "debe decir" repite la cláusula y agrega un párrafo: verificado por oraciones, 10 oraciones en el lado nuevo y 4 que no están en el lado "dice" (una de ellas, la larga, es el párrafo que la lista espera como M-015). No hay ningún requisito `origin = circular` en la versión (los 293 son `propuesto`).

Causa: `_resolve_pair` solo crea efectos `modifica` sobre citas existentes. El camino `Addition` existe solo para una unidad con verbo `agrega` y cláusula inexistente (`_resolve_addition`). Nadie compara el texto nuevo del par con el viejo para detectar lo que se suma.

**Arreglo general (producto):** en `_resolve_pair` (y en `reemplaza` de cláusula completa, comparando con las citas de la cláusula), buscar en el lado nuevo las oraciones que no están en el lado viejo (comparación sin mayúsculas ni espacios) y que llevan marcadores de obligación (los de T-093, ya usados por `is_procedure_data`); cada una es un `Addition` formal con cita literal en el tramo de la circular, origen `circular`. Esto cubre "el mismo texto más un párrafo" sin nombrar el caso. Sin lado viejo (reemplazo por "la siguiente"), comparar con las citas alcanzadas. Test sintético: cláusula con tres oraciones y su "debe decir" con una cuarta obligatoria nueva.

Observación menor (no se toca): los tramos de cabecera de cada circular (`pre/p-1` a `pre/p-8`) hacen 16 pedidos de respaldo y 16 de `circulares_cambios` sin resultado (anomalías vacías); es tiempo sin beneficio y se puede evitar mandando al modelo solo tramos con disposición `requisitos`.

## 4. M-058 y M-063: descartados por el filtro

Las dos filas fueron descartadas por la pasada de completitud/extracción (R20 y R21 en `sec-i/18.6`, motivo `obligacion_organismo`; R26 en `sec-i/27.1`, motivo `norma_aplicable`) con respuestas A y B guardadas en `tenders_discarded_row`, y pedidos 1252/1253 y 1258/1259.

| Fila | A (clasificación) | B (¿puede condicionarla la oferta?) | Indicio |
|---|---|---|---|
| M-058 (R21) | descartar, `obligacion_organismo` | no | Es la propia frase de la fila, literal en el tramo |
| M-063 (R26) | descartar, `norma_aplicable` | no | Es la propia frase de la fila, literal en el tramo |

**Las cuatro condiciones (plan, "Cuándo se descarta") se cumplieron en las dos filas:** (1) A dice descartar, (2) el motivo está en la lista cerrada, (3) el indicio es literal en el tramo, (4) B dice no. El mecanismo hizo lo que está escrito; lo que falló es el criterio, y B no protegió porque contesta con el mismo sesgo que A (las dos respuestas se dan sobre el mismo texto y las mismas instrucciones: no son independientes).

**Falla de criterio en M-058.** La fila dice que la existencia de deuda tributaria o previsional se verificará en la evaluación. El filtro la leyó por el sujeto gramatical ("el organismo verifica") y no por el objeto: lo que se verifica es una condición del oferente (no tener deuda). Es la comprobación de un requisito de la oferta, y la Comisión la hace en la evaluación. La definición de `obligacion_organismo` en las instrucciones ("una obligación del organismo que la oferta no puede contradecir ni condicionar") no distingue "el organismo hace algo propio" de "el organismo comprueba algo del oferente".

**Falla de criterio en M-063.** La fila es la segunda mitad de la misma oración que R146 (los pagos se efectúan en moneda nacional "y en un todo de acuerdo a" la norma). R146 se mantuvo; el resto de la oración, evaluado solo, parece la cita de una norma y se descartó como `norma_aplicable`. Las instrucciones ya dicen que la forma, el plazo y la moneda de pago son requisitos aunque los cumpla el organismo; no dicen que un fragmento que sigue a una condición dentro de la misma oración forma parte de ella.

**Arreglos generales (producto, a coordinar con T-106, que es dueña del filtro).**
1. Instrucciones v2 del filtro, una frase por regla y sin nombrar cláusulas: (a) "Si el organismo verifica, controla o exige algo sobre el oferente o su oferta (que no tenga deudas, que esté inscripto, que cumpla un requisito), la fila describe una condición de la oferta: se mantiene aunque el sujeto de la oración sea el organismo." (b) "Un fragmento que continúa la misma oración que otra fila mantenida (una referencia a la norma que sigue a una condición de pago, de plazo o de presentación) forma parte de esa condición: se mantiene." Con un ejemplo inventado de otro objeto en cada pregunta y un caso `duda` en B.
2. Guarda en código, independiente del modelo: una fila cuyo fragmento comparte oración con otra fila firme del mismo tramo no se descarta; pasa a sugerencia (destino ya existente, REQ-035) o se mantiene. Es la forma más barata de proteger el "ante la duda, de más".
3. Medir con la lista: los esperados descartados por el sistema deben ser 0 (T-106).

## Efecto esperado de los arreglos sobre la corrida 14 (sin volver a correrla)

| Medida | Hoy | Con los arreglos de medición |
|---|---|---|
| Encontrados | 83 de 93 (inflado: 4 falsos) | 90 de 93 (79 verdaderos + M-025, M-026, M-029 y M-087 a M-094 suprimidos por circular); quedan M-058 y M-063 (filtro) y M-059 (pendiente, a revisión) |
| REQ-031, cumplen los 4 puntos | 2 de 15 | 13 de 15 (estimado): fallarían solo M-015 y M-044, que dependen de los arreglos de producto de los puntos 2 y 3; con ellos, 15 de 15 |
| Ruido de circulares | 22 fuentes en 22 filas | 17 son fuentes `suprime` del Anexo VI sobre las citas de las filas técnicas (efecto correcto de la circular 1, cláusula 3; la lista no las espera) y 5 son los `modifica` correctos de la cláusula 7.5.5 (R23 a R27) que la lista tampoco espera; ver la nota de lista |

La cuenta de REQ-031 es estimada: se calculó pareja por pareja con la lógica de `measure_circulars`, no se re-midió.

## Nota sobre la lista (no se tocó)

- Las filas de 7.5.5 (R23 a R26) reciben un `modifica` correcto de la Circular 2 y la lista no lleva bloque `circulares` en ellas (solo en M-015); la medición las cuenta como ruido. Si se quiere que no sean ruido, el Coordinador agrega el bloque `modifica` en esas filas (texto original y vigente iguales salvo el párrafo nuevo). Es decisión de lista, no de producto.
- Las fuentes `suprime` sobre las filas técnicas que citan el Anexo VI (17) son coherentes con la cláusula 3 de la Circular 1; la lista no las tiene como esperadas. Decisión del Coordinador: agregarlas como esperadas o aceptar que son ruido informado.

## Orden sugerido

1. Medición: `_technical_citing` por lectura y emparejamiento de filas quitadas por circular (puntos 1 y 2). Es el cambio con más efecto y el único que corrige números ya informados (T-103, T-098).
2. Producto, entrega 1: `_find_original` y el `agrega` en el par (puntos 2 y 3).
3. Filtro: instrucciones v2 y guarda (punto 4), dentro de T-106 y con la regla de generalidad.
