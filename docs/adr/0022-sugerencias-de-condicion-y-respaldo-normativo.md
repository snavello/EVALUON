# ADR-0022 · Sugerencias de condición y respaldo normativo: un tercer destino del filtro, y la norma solo confirma

Estado: propuesto · Fecha: 2026-10-04 · Decidió: —

## Contexto

La spec 003, enmendada otra vez el 2026-10-04, pide dos cosas sobre el filtro de precisión del ADR-0021:

- **REQ-035.** La matriz propuesta separa los requisitos firmes de las *sugerencias de condición*: condiciones plausibles sobre las que el sistema duda. Van en una sección aparte, con su cita y el motivo de la duda; la Comisión decide cada una (o por grupo, REQ-034) y la matriz no se valida con sugerencias sin decidir. Las sugerencias no entran en el tope de sobrantes.
- **REQ-036.** Para cada sugerencia y cada fila dudosa, el sistema busca en la normativa aplicable (según la fecha de autorización, REQ-022) si el régimen exige esa condición a las ofertas; si la encuentra, muestra la cita de la norma como respaldo y puede proponerla como requisito. La norma solo confirma: que una condición no figure en ella nunca es motivo de descarte, porque el pliego puede agregar exigencias propias. El responsable la marcó como importante.

El ADR-0021 (aceptado) tiene dos destinos para una fila: firme o descartada, y "ante la duda, se mantiene". Lo medido en el caso-00 (T-093) hace probable que el tope del 20 % no se alcance con ese filtro solo: quedarían unos 30 sobrantes sobre unas 80 filas, sobre todo condiciones plausibles que la lista no tiene. Esas filas no se pueden descartar sin arriesgar el 100 % de encontrados; la sección de sugerencias les da otro lugar sin cargarlas al tope.

Restricciones: lo que el modelo escribe no se muestra como texto propio (P3); la cita es literal y la comprueba el sistema (ADR-0004); la normativa se busca con la recuperación de la 001, a la fecha de autorización (ADR-0006, P8), con AFIP y ARCA como el mismo organismo (ADR-0010); todo corre en el equipo (P4); el tiempo es secundario.

## Alternativas

Hay dos decisiones: cómo se guarda y se decide una sugerencia, y qué puede hacer la norma con ella.

### 1. Dónde vive una sugerencia

#### 1A. Un estado más del requisito (`sugerido`)
La sugerencia es una fila de `tenders_requirement` con `state` `sugerido`, un motivo de duda de lista cerrada y un JSON con las dos respuestas y el indicio.
- Se gana: conserva todo lo que ya existe para un requisito (citas principal y repetidas, renglones, historial, grupos de REQ-034, copia entre versiones, consecuencias); la migración de T-099 suma pocos campos; pasar a requisito es cambiar de estado, sin copiar nada.
- Se pierde: el estado `sugerido` tiene que excluirse en cada consulta que cuenta requisitos (tope, validación, resumen, impresión, la 004 y la 008 al leer la matriz vigente); un descuido muestra una sugerencia como requisito. Se mitiga con la regla de validación (ninguna versión validada tiene sugerencias) y con tests de cada lectura.

#### 1B. Una tabla aparte de sugerencias (como `tenders_discarded_row`)
- Se gana: ningún lector de requisitos puede confundirla; ya hay un precedente (las descartadas).
- Se pierde: pasar a requisito exige crear el requisito copiando citas y renglones (como "devolver"), hay que duplicar los grupos, el historial y las copias entre versiones, y una tabla más con su trigger; para el estado de una sugerencia (pendiente, aceptada, quitada) hay que derivarlo, como en las descartadas. Más esquema y más código para lo mismo.

#### 1C. Dejarlas firmes con una marca
- Se gana: ninguna sección nueva.
- Se pierde: entran en el tope y en la validación como cualquier fila; no cumple REQ-035 (no hay sección aparte, ni bloqueo, ni exclusión del tope).

### 2. Qué puede hacer el respaldo normativo

#### 2A. Solo confirmar: propone, la Comisión decide
El respaldo (norma, artículo, vigencia, cita literal) se muestra junto a la sugerencia, que pasa primero en su sección y marcada "la norma aplicable la exige"; la Comisión la pasa a requisito con un clic o por grupo. Nunca cambia un estado.
- Se gana: la decisión sigue en la Comisión (P3); un respaldo equivocado no mete una fila en la matriz; el tope no depende de la calidad de la consulta normativa.
- Se pierde: un clic por sugerencia con respaldo (atenuado por los grupos de REQ-034).

#### 2B. Promover sola la sugerencia con respaldo completo
Con puntaje del reranker sobre el umbral, el modelo diciendo que la unidad exige esa condición y la cita literal verificada, la sugerencia pasa a requisito propuesto sin intervención.
- Se gana: menos trabajo de la Comisión y menos sugerencias sin decidir.
- Se pierde: la decisión sale de la Comisión para una parte de las filas; un falso positivo del modelo (una unidad que habla de algo parecido) agrega una fila firme que cuenta como sobrante; el tope pasa a depender de la consulta normativa. Con los datos de un solo caso no hay cómo medir su precisión. Podría adoptarse más adelante, con una enmienda, si la medición de los tres casos muestra que todas las sugerencias con respaldo eran requisitos esperados.

#### 2C. Usar la norma también para descartar lo que no figura
Quitar o dar de baja una sugerencia porque la norma no la exige.
- Se pierde todo: el pliego puede agregar exigencias propias, y REQ-036 lo prohíbe. Se descarta.

## Decisión

Se propone **1A con 2A**, con estas reglas:

1. **Tres destinos, sin pedidos nuevos.** Se aplica una tabla fija a las dos respuestas validadas del filtro (primera: mantener o descartar con motivo e indicio; segunda: sí, no o duda): firme solo con (mantener, sí) o con una única opinión válida que mantiene o con ninguna válida; descartada solo con las cuatro condiciones del ADR-0021; todo lo demás, sugerencia. Complementa la regla 3 del ADR-0021 ("todo lo demás mantiene la fila"): lo que mantenía la fila ahora la deja como sugerencia cuando hay una señal de duda. Una falla técnica sin ninguna opinión válida no fabrica una duda: la fila queda firme.
2. **La sugerencia nace solo del filtro.** Ninguna otra pasada la produce; así el motivo de la duda es siempre una de las cuatro razones de lista cerrada (no coinciden, duda, descarte sin sustento, opinión incompleta), no texto del modelo.
3. **Estado `sugerido` en el requisito.** Con motivo y JSON de las respuestas y el indicio; una restricción impide un técnico en ese estado. La matriz validada no puede tener ninguna.
4. **Decidir:** pasar a requisito (queda `propuesto`; después lo confirma un evaluador) o quitar, una por una o por grupo (REQ-034), con quién y cuándo. La validación se rechaza con sugerencias sin decidir.
5. **Respaldo normativo:** una consulta por sugerencia con la recuperación y la selección de la 001, a la fecha de autorización; un pedido que pregunta por cada unidad si exige esa misma condición y cita un fragmento literal de ella. Es respaldo solo con las tres condiciones: puntaje sobre el umbral, "exige" y cita hallada en la unidad. Solo se muestra; no cambia ningún estado, y su ausencia no es un motivo ni una marca.
6. **Medición:** las sugerencias no entran en el tope; un esperado en una sugerencia cuenta como "a revisión obligatoria"; se informa cuántas hay, qué proporción eran esperados, cuántas con respaldo y cuántas de esas eran esperados.
7. **Contra el depósito.** La sugerencia no se genera por fallas; el informe pone la proporción de esperados entre las sugerencias a la vista y el tope informativo "con las sugerencias como firmes"; los grupos permiten decidir por cláusula. Ningún límite duro: la spec no lo pide y la medición dirá si hace falta (decisión del responsable en T-107).

Motivo principal: es la forma que da a la sugerencia todo lo que ya tiene un requisito con el menor cambio de esquema, y que mantiene la decisión en la Comisión mientras la norma sirve de evidencia visible, no de árbitro.

## Consecuencias

**Más fácil**
- El tope se mide sobre las filas firmes, con las dudosas en un lugar propio: el filtro no tiene que descartar condiciones plausibles para ajustarse a la lista, que era el riesgo que dejó ADR-0021.
- La Comisión ve junto a cada sugerencia por qué se dudó y, si existe, qué artículo la exige; decidir por grupo cuesta un clic.
- Lo que el filtro no se animó a descartar queda a la vista: nada se pierde ni se esconde.

**Más difícil**
- Todo código que cuenta o muestra requisitos tiene que tratar `sugerido`: tope, resumen, impresión, validación y lo que lea la matriz vigente. Se cubre con tests de cada lectura.
- Una pasada más por sugerencia (una recuperación y un pedido corto): del orden de segundos por sugerencia, a medir en la corrida del caso-00.
- Una sección más que puede llenarse: la medición decide si es útil (proporción de esperados entre las sugerencias, esperados con respaldo).
- Las consecuencias se piden también para las sugerencias, para que pasen a requisito con ayuda: más tiempo, no más trabajo humano.

**Para revertir**
- `SUGGESTIONS_ENABLED` en falso devuelve el filtro a dos destinos (lo que mantiene la fila queda firme); `NORM_SUPPORT_ENABLED` en falso saltea la consulta normativa. Las sugerencias y los respaldos ya guardados siguen siendo válidos. Pasar a 2B es un cambio de regla (y una enmienda a la spec) sin cambiar el esquema; pasar a 1B, una migración que mueva los estados `sugerido` a la tabla nueva.

## Sin verificar

- Cuántas filas pasan a sugerencia en el caso-00, qué proporción eran esperados y si el tope se alcanza sobre las firmes. Se mide en T-106; los casos 01 y 02, en T-108, sin ajustar.
- Cuánto recupera la búsqueda de la 001 cuando la "pregunta" es un fragmento de pliego, y si el umbral del reranker de la 001 (0,219) es adecuado para esta consulta. Se mide en T-106; no se baja para que aparezcan respaldos.
- Si el modelo distingue bien "exige esa misma condición" de "habla del mismo tema". Se verifica con la muestra revisada, no con dobles.
- Cuántas sugerencias con respaldo son requisitos esperados: de eso depende una eventual promoción automática (2B).
