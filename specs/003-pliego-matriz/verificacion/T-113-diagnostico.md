# T-113: pasada de circulares, diagnóstico y propuesta (REQ-031)

Etapa solo de diagnóstico: no se cambió código, tests ni datos. Lectura de la base real (`evaluon-app-1`, `python manage.py shell`), sin usar el modelo. Fuente: la corrida 13 (`caso-01-medicion`, versión 3 de la matriz, instrucciones `matriz-circulares-v2`), con sus 99 pedidos de la pasada guardados en `tenders_run_step` (pedido completo, salida, candidatas mostradas, puntajes). Sin texto del pliego ni de las circulares: solo `R-NNN`, claves de tramo, alias y cuentas. Las claves de tramo son las del sistema (`sec-i/7.5.4`, `pre/p-17`).

El caso-01 es caso de ajuste para circulares; no se miró ningún caso de aceptación (03, 04).

## 1. Cómo es la entrada (lo que explica casi todo)

- **Circular 1 (documento 17, 82 tramos).** Tiene dos formas distintas de cambiar el pliego:
  - Tres cláusulas numeradas (`1`, `2`, `3`): "se modifica la sub-cláusula X por la siguiente", "se suprime la cláusula Y", "el Anexo VI no es requisito".
  - Un apartado "II" que fija nuevas fechas de visita: **79 párrafos sueltos** (`pre/p-1` a `pre/p-79`), uno por línea de una lista que se repite por edificio (fecha, hora, punto de encuentro, referente, dirección).
- **Anexo de fecha de visita (documento 4).** Es la lista original que el apartado II de la circular reemplaza. No tiene requisitos propios: la única cita del pliego que lo menciona es la cláusula 13.2 (R93, R94).
- **Circular 2 (documento 18, 18 tramos).** Una cláusula reescrita con "DONDE DICE / DEBE DECIR". La lectura no ubica los tramos (`no-ubicado-1` a `-4`, más tablas): "DONDE DICE:" y "DEBE DECIR:" son tramos distintos, y el texto viejo y el nuevo de la cláusula 7.5.5 caen en tramos aparte.
- La pasada hizo **99 pedidos, 432 s y unos 836.000 tokens de entrada** (unos 8.400 por pedido), sin reintentos. 79 de los 99 pedidos son líneas sueltas de la lista de visitas.

## 2. Causa de cada fallo

### M-013 (R30 sin fuente): una reescritura de cláusula se aplica a una sola cita

- Tramo `1` de la Circular 1 (pedido 80): "se modifica la sub-cláusula 7.5.4 por la siguiente: …". La cláusula 7.5.4 tiene **dos citas del pliego** (R29 y R30, dos oraciones de la misma cláusula). Las dos se mostraron al modelo (Q1 y Q2, ambas `sec-i/7.5.4`, nombradas por cláusula).
- El modelo devolvió **un solo efecto**: `modifica` sobre Q1 (R29), con el texto entero de la cláusula nueva (777 caracteres). R30 quedó sin fuente.
- Causa: el diseño le pide al modelo elegir "la cita alcanzada". Cuando una circular reemplaza **toda** la cláusula, todas las citas de la cláusula están alcanzadas, pero el esquema y las instrucciones (v2: "elegí la cita cuyo texto trata de lo mismo") empujan a elegir la mejor. El modelo decide lo que el sistema podía decidir por la clave.
- Nada en el código mira "la circular dice reemplazar la cláusula X": `named_in` solo sirve para ordenar las candidatas.

### M-029 (R55 sin fuente): el efecto va al contenido del anexo, no a la cláusula que lo exige

- Tramo `3` (pedido 82): "la información del Anexo VI no será considerada como un requisito". Candidatas mostradas: 30. R55 (cláusula 7.7.1, "completar y adjuntar este Anexo", sin número de anexo en la cita) está como Q6, aludida por el nombre del anexo; **no se puntuó** (las aludidas no pasan por el reranker).
- El modelo devolvió 8 `suprime` sobre Q11 a Q18, las citas del propio Anexo VI (R243 a R250), y ninguno sobre Q6.
- Causa: ante una circular que dice "el Anexo X no es requisito" hay dos niveles de cita (el contenido del anexo y la cláusula que manda presentarlo) y el modelo agota el efecto en el primer nivel. Elegir ambos niveles es una regla estructural ("el anexo nombrado y las cláusulas que lo exigen"), no un juicio de lectura.
- Para la lista de aceptación: las 8 fuentes sobre R243 a R250 **no son ruido, son correctas** según el texto de la circular: si el anexo no es requisito, sus filas quedan quitadas. La lista del caso solo trae R55 (decisión 3).

### M-044 (parcial): la lista de visitas se trata línea por línea

- Las líneas "FECHA DE VISITA: …" (`pre/p-17`, `p-23`, `p-41`, `p-47`, `p-53`, `p-59`, `p-65`, `p-71`) se piden **una por una**, cada una con la cláusula 13.2 como candidata. El modelo respondió `modifica` sobre 13.2 en 8 de ellas: **8 fuentes en vez de 1**. Otras líneas de fecha idénticas (`p-29`, `p-35`) recibieron `sin_efecto: titulo` con el mismo texto y las mismas candidatas: **la salida no es estable para entradas idénticas**.
- El texto "vigente" de la cita queda como el de la **última línea** procesada, no como la lista completa, porque `Candidate.current` se pisa con cada `modifica`.
- La cita original ligada es 13.2, que solo dice "en la fecha y lugar indicados en el Anexo «FECHA DE VISITA»". El texto que la circular reemplaza está en el anexo (documento 4), que **no es candidata** porque ningún requisito tiene citas allí. El sistema no tiene cómo ligar "este bloque de la circular reemplaza este otro documento".
- R94 (segunda cita de 13.2) sin fuente: misma causa que M-013 (una sola cita por efecto).

### M-015 (R424 sin fuente propia)

- R424 es el requisito agregado por la Circular 2 (`origen: circular`, tramo `sec-i/no-ubicado-3`). El modelo lo creó como `nuevos` junto con R423 (`no-ubicado-2`) y R425 (`no-ubicado-3`).
- No tiene fuente porque el diseño solo crea fuentes para efectos sobre una cita existente (`modifica`, `aclara`, `suprime`); un requisito nuevo no tiene vía para mostrar documento y fecha de la circular, aunque su cita sí está en el tramo.
- R423 y R425 son duplicados de lo mismo. R31 a R34 (las 4 citas de 7.5.5) reciben cada una **2 `aclara`**, una del tramo "DONDE DICE" (texto viejo) y otra del "DEBE DECIR". La instrucción v2 ("el Donde dice no produce efecto") no se cumple porque el rótulo está en un tramo aparte (`no-ubicado-1`) y el texto viejo en otro (`no-ubicado-2`), sin que el sistema los empareje. Además el reemplazo se marcó `aclara` y no `modifica`.

## 3. Causa de cada tipo de ruido

| Ruido | Cuenta | Causa, con evidencia |
|---|---|---|
| 72 fuentes ajenas en las 18 filas técnicas | 4 por fila | Cuatro efectos del apartado de visitas caen sobre **citas comunes a todos los renglones**: `aclara` sobre `sec-i/9.3` (lugar de entrega) en `pre/p-22` y `p-28`, `modifica` sobre 9.3 en `p-58`, `modifica` sobre `sec-iv/anexo-vii/p-4` en `p-70`. Cada una pega un efecto en R385 a R402. El modelo las eligió por parecido semántico: la lista de direcciones de visita se parece a la lista de edificios de entrega de 9.3. La regla "una cita común a todos los renglones alcanza la fila de cada uno" **multiplica por 18** cualquier error de elección. |
| 20 requisitos `circular` de la Circular 1 | R403 a R422 | Líneas de la lista (hora de visita, punto de encuentro: `pre/p-18`, `p-19`, `p-24`, `p-25`, …) que el modelo marcó como `nuevos` formales. Son datos del trámite, no requisitos de la oferta. Cada línea se ve aislada: con "las dos anteriores" de contexto no se ve que es una lista de datos. |
| 8 fuentes de la Circular 1 en filas formales y económicas ajenas | R243 a R250 | No es ruido: es el efecto correcto del tramo `3` sobre el Anexo VI (ver M-029). |
| 8 fuentes `aclara` de la Circular 2 en R31 a R34 | 2 por fila | Duplicación por no emparejar "Donde dice" con "Debe decir" (ver M-015). Las filas son las correctas (7.5.5); el efecto correcto es uno solo y `modifica`. |
| 540 citas "aludidas" en el tramo 1 | 104 mostradas | El tramo `1` cita "el Anexo IV de la Disposición N° …" (norma externa) y `named_annexes` lo toma como el Anexo IV del pliego: se agregan 540 citas de ese anexo, se muestran 104 hasta llenar el contexto. Pedido 80: 104 candidatas para una cláusula ya nombrada. No cambió el resultado esta vez, pero consume contexto y puede desplazar a la candidata buena. |
| Tiempo | 432 s, 836.000 tokens | 79 pedidos (80 %) son líneas de una lista; cada uno arrastra de 3 a 104 citas del pliego. |

## 4. ¿Puede el diseño actual cumplir REQ-031 con ajustes?

El diseño actual: cada tramo de circular → candidatas (nombradas, aludidas, las 8 del reranker) → el modelo elige efecto sobre una cita.

**Se conserva:** la ordenación por fecha, la verificación de citas literales, la disposición de cada tramo, los textos original y vigente, el registro de cada pedido (P6) y la regla de que ningún tramo desaparece.

**Lo que está mal en el diseño, no en los parámetros:**

1. **La unidad de trabajo es el párrafo que dejó la lectura, no el cambio que la circular declara.** Una lista de 79 líneas son 79 pedidos; "DONDE DICE" y "DEBE DECIR" son pedidos distintos. El modelo no ve el cambio entero.
2. **Lo que la circular dice con precisión (cláusula 7.5.4, Anexo VI, Renglón N) se deja a la elección del modelo entre candidatas.** La clave nombrada es un dato verificable; hoy solo sirve para ordenar.
3. **Un efecto por cita elegida** no representa "reemplazo de cláusula" (todas las citas de la cláusula) ni "el anexo ya no es requisito" (el anexo y quien lo exige).
4. **Las citas comunes a los 18 renglones amplifican por 18** cada elección dudosa, sin umbral de confianza.
5. **La salida no es estable** (mismo texto y mismas candidatas: `modifica` o `titulo`), y sin reintentos no se detecta la discrepancia.

El diseño **puede** cumplir el ejemplo sintético de la spec (16 GB a 32 GB en un renglón). No hay evidencia de que cumpla de manera repetible con circulares reales: cada falla de T-094 y T-098 se corrigió con una regla propia del caso (anexo nombrado, título entre comillas, número al comienzo de línea, contexto por encabezado) y cada corrección abrió otra (regresión de M-013, 20 requisitos de más, 540 aludidas). Los casos 03 y 04 traerán otras formas de circular; la lista de reglas seguirá creciendo.

## 5. Opciones

### Opción (a): lista estructurada de cambios, luego aplicar por clave

**Idea.** Cada circular se parte en **unidades de cambio** (no en tramos de lectura) y se trabaja en tres etapas.

1. **Extracción (modelo, sin ver el pliego).** Por cada unidad, el modelo devuelve una lista de cambios: `{objetivo: cláusula | anexo | renglón | ninguno, número o título, tipo: reemplaza | suprime | agrega | aclara | dato_del_trámite, texto_anterior (si la circular lo da), texto_nuevo (literal)}`. Las unidades son: cada cláusula numerada de la circular; el apartado completo bajo un encabezado romano (la lista de visitas es **una** unidad); y el par "DONDE DICE / DEBE DECIR" juntos. El pedido lleva solo la circular, sin 8 a 104 citas del pliego.
2. **Aplicación (código, sin modelo).** El objetivo se resuelve contra el pliego por la clave:
   - cláusula `7.5.4` → **todas** las citas de esa cláusula (R29 y R30) y sus subcláusulas;
   - anexo `VI` → las citas del anexo y las cláusulas que lo piden con el número o el título entre comillas (R243 a R250 y R55);
   - renglón `N` → las filas técnicas de ese renglón;
   - bloque que reemplaza un anexo (la lista de visitas) → una sola fuente `modifica` sobre las citas que **mencionan** ese anexo (R93, R94), con el bloque entero como texto vigente;
   - tipo `dato_del_trámite` → ningún requisito, descarte con motivo.
3. **Respaldo.** Solo para cambios sin clave ("la memoria RAM del equipo", respuestas a consultas sin número) se usa el flujo actual (candidatas por reranker, el modelo elige), restringido a esos cambios.

**Qué resuelve.**

| Fila o ruido | Cómo |
|---|---|
| M-013 | La cláusula 7.5.4 reemplazada afecta a R29 y R30. |
| M-029 | El anexo VI y la cláusula que lo pide (R55) reciben `suprime`. |
| M-044 | Una sola unidad (apartado II), una fuente por cita de 13.2 (R93 y R94). |
| 72 fuentes técnicas | Desaparecen: el apartado de visitas no nombra la 9.3 ni los renglones. |
| 20 requisitos `circular` | Desaparecen: el bloque es `dato_del_trámite`. |
| R423, R425 y los dobles `aclara` | El par emparejado produce un `reemplaza` de 7.5.5; el texto viejo no crea efecto. |
| 540 aludidas | No se muestran citas en la extracción. |
| M-015 | El `agrega` produce el requisito con documento y fecha (decisión 4). |
| Estabilidad y tiempo | Unos 8 a 12 pedidos cortos en vez de 99 (estimación); se pueden repetir 2 o 3 veces y comparar. |

**Riesgos.**
- La resolución por clave depende de que la circular diga el número y de que el pliego tenga esa clave. Una numeración distinta ("7.5.5" contra la del pliego) se resuelve por número normalizado; si no existe, va al respaldo y no se pierde.
- "El anexo y las cláusulas que lo nombran" puede quitar de más una cláusula que cita el anexo de pasada. Mitigación: se aplica solo a cláusulas cuyo texto *pide* el anexo ("completar", "adjuntar", "presentar") y queda como propuesta con su cita; la Comisión decide.
- La partición en unidades usa encabezados y rótulos; una circular sin ellos cae en "una unidad por tramo" (el comportamiento de hoy).
- El modelo sigue extrayendo: puede equivocar el tipo (`reemplaza` contra `aclara`). Pero el error queda en una lista corta, revisable y repetible, no escondido en 99 pedidos.
- Hay que decidir cómo se muestra el texto original cuando está en un anexo sin requisitos (decisión 2).

**Costo y cuánto código cambia.**
- Módulo nuevo `circular_changes.py` (partición en unidades, esquema, extracción, validación de literales): unas 300 a 400 líneas, y una instrucción nueva `matriz-circulares-v3.md`.
- `circulars.py`: candidatas, `named_in`, `is_referred` y el procesador por tramo quedan como respaldo; `_apply` y `Source` se reutilizan. Cambia entre 30 y 40 % del módulo. No cambian `Result` ni `run._save`, ni las tablas ni la pantalla, salvo que se apruebe la decisión 2 (campo nuevo, migración).
- Tests nuevos con fixtures sintéticas, sin modelo en las reglas de aplicación. Tamaño: lo de T-083 más lo de T-098.

### Opción (b): ajustes incrementales al diseño actual

1. **Agrupar el apartado** bajo un encabezado romano en un solo tramo (hasta 4.000 caracteres): un pedido por apartado, no por línea.
2. **Reescritura de cláusula completa:** si el tramo dice "se modifica / reemplaza / sustituye la cláusula X", aplicar el `modifica` elegido a **todas** las citas de la cláusula X (postproceso en código).
3. **No tomar como anexo del pliego** "Anexo N de la Disposición/Resolución/Decreto …", y topar las aludidas.
4. **Para un efecto sobre una cita común a los 18 renglones**, exigir que el tramo nombre la cláusula o el renglón; si no, `sin_efecto`.
5. **Emparejar "DONDE DICE" con el "DEBE DECIR"** siguiente y no pedir el primero.

**Resuelve:** M-013 (2), M-044 en parte (1: de 8 a 1 fuente, pero el original sigue siendo 13.2 y no el anexo), el ruido técnico (4), los 20 requisitos (1) y la duplicación de la Circular 2 (5). **M-029 queda igual** salvo que se agregue una sexta regla ("anexo nombrado extiende a las cláusulas que lo piden").

**Riesgos.** Cada ajuste sale de lo visto en el caso-01, el mismo patrón que se repitió en T-094 y T-098; no hay garantía para las formas de los casos 03 y 04. El modelo sigue decidiendo por tramo lo que el código podría decidir, y la salida sigue sin ser estable. Tiempo y tokens no bajan.

**Costo.** Chico: de 100 a 200 líneas más tests, una tarea.

### Comparación

| | (a) Lista de cambios y aplicación por clave | (b) Ajustes incrementales |
|---|---|---|
| Fallos del caso-01 | M-013, M-029, M-044 completo (según decisión 2), M-015 con fuente, ruido | M-013, M-044 en parte, ruido; M-029 solo con una regla más |
| Generalización | Mayor: "aplicar lo que la circular dice por su clave" | Menor: un parche por forma |
| Estabilidad | Mejor: pocos pedidos cortos, repetibles y comparables | Igual que hoy |
| Tiempo y tokens | Bajan mucho (estimado 5 a 10 veces menos tokens) | Sin cambio o más |
| Código | 300 a 400 líneas nuevas y 30 a 40 % de `circulars.py` | 100 a 200 líneas |
| Riesgo | Mayor al empezar (módulo nuevo); un error de partición se arrastra | Menor al empezar, más deuda después |
| Tablas y pantalla | Sin cambios, salvo decisión 2 | Sin cambios |

## 6. Recomendación

**Opción (a), en dos entregas** para acotar el riesgo:

1. **Parte determinista**, que sirve también a (b): partir en unidades de cambio (cláusula numerada, apartado completo, par DONDE DICE / DEBE DECIR), resolver por clave a **todas** las citas de la cláusula, extender el efecto del anexo a las cláusulas que lo piden y tratar las listas como `dato_del_trámite`. Resuelve M-013, M-029, el ruido técnico y los 20 requisitos de más.
2. **Extracción con el modelo y respaldo** para lo que no tiene clave, más estabilidad (repetir la extracción y comparar).

Razón: los fallos no son del modelo sino de lo que se le hace decidir. Lo que la circular nombra por número, el código lo resuelve exacto y siempre igual; el modelo queda para lo que requiere lectura. Es la única opción que no pide un parche más por cada forma de circular nueva, que es lo que pasará con los casos 03 y 04. Si se prefiere el menor costo inmediato, (b) con los ajustes 1, 2 y 4 resuelve M-013, el ruido y gran parte de M-044, pero **no** M-029 ni da garantía para la aceptación.

## 7. Cómo se probaría sin mirar los casos 03 y 04

- **Reglas de aplicación (código):** tests unitarios con pliegos y circulares sintéticos que reproducen las *formas* (no el texto) del caso-01: cláusula con dos citas reemplazada; anexo declarado no requisito con una cláusula que lo pide; lista de datos bajo un encabezado romano; "DONDE DICE / DEBE DECIR" en tramos separados; mención de un anexo de una norma externa; cita común a varios renglones con y sin el renglón nombrado. Sin modelo; fallan sin el arreglo y pasan con él.
- **Extracción con el modelo (ajuste):** medir con el caso-01 (caso de ajuste), con las 7 filas esperadas y las cuentas de ruido de `T-098-medicion-caso-01.md`, y repetir la extracción 3 veces para medir estabilidad. La corrida con el modelo es aparte y de una por vez (GPU).
- **Más circulares reales públicas** distintas del caso-01, 03 y 04: conviene sumar 2 o 3 pliegos públicos de otros organismos con circulares (material público, P4) como casos de ajuste, para no calibrar solo sobre uno (decisión 5).
- **Aceptación:** los casos 03 y 04 se miden a ciegas una sola vez, después de la entrega 2, sin ajustar sobre ellos.

## 8. Decisiones de diseño que hacen falta

1. **Elegir (a) con dos entregas, o (b).** Es la decisión principal.
2. **Cómo se muestra el texto original cuando está en un anexo sin requisitos** (la lista de visitas, documento 4, citada desde 13.2). (i) La fila de 13.2 muestra la cita de la cláusula y un enlace al anexo: sin migración, M-044 queda parcial según la lista actual. (ii) La fuente guarda una referencia al tramo del anexo como original: campo nuevo en `tenders_requirement_source`, **migración** que el desarrollador no hace sin aprobación. Recomendado (ii): la spec pide mostrar "los dos textos" y el anexo es el original.
3. **Qué cuenta como esperado cuando una circular quita un anexo:** si R243 a R250 (filas del anexo) son esperadas junto con R55. El efecto es correcto según la circular; conviene incluirlas en la lista y no contarlas como ruido. La lista la decide quien la preparó.
4. **Qué muestra un requisito que agrega una circular** (M-015): una fuente con efecto nuevo (`agrega`; cambia el conjunto de efectos de la tabla, **migración**) o que la pantalla tome documento y fecha del tramo de su cita. Recomendado lo segundo, sin migración.
5. **Más casos públicos de ajuste** de circulares, además del caso-01.

## 9. Fuera de alcance, para anotar

- `named_annexes` toma "Anexo IV de la Disposición" como anexo del pliego: se corrige en la parte determinista de (a) o en el ajuste 3 de (b).
- `Candidate.current` se pisa con cada `modifica`: con varias líneas del mismo cambio el texto vigente queda en la última. Desaparece si el cambio se aplica por unidad.
- El historial "modificada por Circular-1 …" se repite tantas veces como líneas; con unidades, una vez.
