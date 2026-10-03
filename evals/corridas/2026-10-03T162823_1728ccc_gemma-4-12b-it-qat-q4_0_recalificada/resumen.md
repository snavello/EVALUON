# Recalificación de la corrida del 03/10/2026 13:20

Recalificación de la carpeta `2026-10-03T132016_8ad46e6_gemma-4-12b-it-qat-q4_0`, hecha el 03/10/2026 16:28 con el commit `1728ccc` y los casos de `evals/casos`. Recalificación: no se hicieron consultas ni se llamó a ningún servicio de IA. Las respuestas son las de la corrida de origen, medidas otra vez con los casos y el corrector vigentes. Se compara con esa corrida al final. Salvo la carpeta y las cantidades de casos, los datos que siguen son los de la corrida de origen.

- Carpeta: `2026-10-03T162823_1728ccc_gemma-4-12b-it-qat-q4_0_recalificada`
- Comienzo: 03/10/2026 13:20 · fin: 03/10/2026 13:22
- Commit: `8ad46e6`
- Modelo de generación: `gemma-4-12b-it-qat-q4_0` (compilación `b11347`)
- Versión de las instrucciones: consulta-v2
- Versión de la normativa: 5
- Umbral del modelo que reordena los resultados (reranker): 0,500
- Casos leídos: 31 · corridos: 31 · 0 sin visto bueno · 0 mal formados

## Medidas exigidas

La cita literal y el tiempo se miden sobre toda la corrida; la respuesta correcta y la abstención, sobre el lote de aceptación (ADR-0014; plan, "Lote de aceptación").

| Exigencia | Resultado | Umbral | Cumple |
|---|---|---|---|
| Cita literal (toda la corrida) | 100,0 % (72 de 72; IC 95 %: 94,9 % a 100 %) | 100 % | sí |
| Respuesta correcta que cita la unidad correcta (lote de aceptación) | — | al menos 85 % | sin casos |
| Abstención (lote de aceptación) | — | al menos 90 % | sin casos |
| Tiempo de respuesta (toda la corrida) | mediana 4,54 s · máximo 9,62 s | máximo de 30 s | sí |

**La corrida no tiene casos del lote de aceptación: las exigencias de respuesta correcta y abstención no se pueden dar por cumplidas con ella.**

IC 95 %: intervalo de confianza al 95 % por el método de Wilson (plan, "Margen de error"). La exigencia se compara con el valor medido; el intervalo dice cuánto se le puede creer. Una falla técnica no cuenta como abstención. El responsable revisa además las respuestas contra la esperada.

## Lote de ajuste (diagnóstico)

Casos sin `lote` o con `lote: ajuste` (ADR-0014): son los que se usan para ajustar el corrector, los datos clave, el umbral y las instrucciones. Se informan como diagnóstico; no sirven para dar por cumplidas las exigencias.

| Medida | Resultado |
|---|---|
| Cita literal | 100,0 % (72 de 72; IC 95 %: 94,9 % a 100 %) |
| Respuesta correcta que cita la unidad correcta | 79,2 % (19 de 24; IC 95 %: 59,5 % a 90,8 %) |
| Abstención | 85,7 % (6 de 7; IC 95 %: 48,7 % a 97,4 %) |

## Medidas por régimen (diagnóstico)

Casos del lote de ajuste, separados según el régimen esperado de cada caso. Son de diagnóstico: las exigencias de la spec se miden con el lote de aceptación, y con pocos casos por régimen sirven solo para orientar.

| Régimen | Respuesta correcta | Abstención |
|---|---|---|
| Disposición AFIP 247/2022 | 86,7 % (13 de 15; IC 95 %: 62,1 % a 96,3 %) | 75,0 % (3 de 4; IC 95 %: 30,1 % a 95,4 %) |
| Disposición AFIP 297/03 | 66,7 % (6 de 9; IC 95 %: 35,4 % a 87,9 %) | 100,0 % (2 de 2; IC 95 %: 34,2 % a 100 %) |
| Sin régimen cargado a la fecha | — | 100,0 % (1 de 1; IC 95 %: 20,7 % a 100 %) |

## Pares de REQ-020

| Par | Resultado | Detalle |
|---|---|---|
| EV-001 y EV-016 | pasa | — |
| EV-003 y EV-017 | falla | EV-017 no pasa por su cuenta |
| EV-014 y EV-018 | pasa | — |

## Aviso de REQ-021

30 de 31 casos traen o no traen el aviso de modificatorias sin cargar según lo esperado.

Fallan: EV-020.

## Recuperación (diagnóstico)

Casos del lote de ajuste, leído del registro de cada consulta. La unidad correcta cuenta si están todas las unidades esperadas del caso (un inciso vale con su artículo); se mide sobre las preguntas con respuesta (ADR-0003).

| Medida | Resultado |
|---|---|
| Unidad correcta entre los candidatos por significado | 100,0 % (24 de 24) |
| Unidad correcta entre los candidatos por palabras | 100,0 % (24 de 24) |
| Unidad correcta entre los candidatos por referencia exacta | 0,0 % (0 de 24) |
| Unidad correcta entre los candidatos en la unión | 100,0 % (24 de 24) |
| Unidad correcta entre las enviadas al modelo | 91,7 % (22 de 24) |
| Posición de la unidad correcta en el orden del reranker | mediana 1 · peor 4 |
| Preguntas con respuesta frenadas por el umbral | 4,2 % (1 de 24) |
| Preguntas sin respuesta frenadas por el umbral | 42,9 % (3 de 7) |
| Tiempo de la recuperación | mediana 0,62 s · máximo 1,40 s |

Preguntas con respuesta frenadas por el umbral: EV-020.
Preguntas con respuesta cuya unidad correcta no llegó al modelo: EV-020, EV-024.

## Salidas con falla de formato o de cita

Se cuentan por el tipo de anomalía; una falla de un servicio no cuenta. Se espera ninguna.

- Falla de formato (la salida no cumple el esquema): 0 (ninguno).
- Falla de cita (cita una unidad que no se mostró o una afirmación sin cita): 0 (ninguno).

## Casos de REQ-018 y REQ-019

- REQ-018 (etiqueta "dos categorías"): ningún caso corrido.
- REQ-019 (casos con la marca de regímenes distintos: el régimen específico y el marco nacional difieren): ningún caso corrido.

## Calibración del umbral (provisoria)

Umbral propuesto (provisorio): 0,219 · A (ajena a la normativa más alta): EV-025, 0,1195 · B (con respuesta más baja): EV-020, 0,3680 · margen 0,728 (mínimo 0,5) · cumple el margen mínimo: sí · umbral actual: 0,500.

Regla del hueco (ADR-0014, punto 2; plan, "Abstención"): con las preguntas del lote de ajuste, el umbral va en el punto medio, en la escala anterior a la sigmoide, entre la pregunta ajena a la normativa con el puntaje más alto (A) y la pregunta con respuesta con el puntaje más bajo (B), redondeado hacia abajo a tres decimales; el margen es la mitad del hueco y el mínimo, 0,5. Las preguntas de tema cercano no entran: las tiene que frenar el modelo. La calibración no cambia el umbral configurado del sistema: el valor es provisorio y fijarlo es una decisión aparte.

| Dato | Caso | Puntaje | Escala anterior a la sigmoide |
|---|---|---|---|
| A: ajena a la normativa más alta | EV-025 | 0,1195 | −1,9967 |
| B: con respuesta más baja | EV-020 | 0,3680 | −0,5407 |
| Punto medio | — | 0,2195 | −1,2687 |

- Margen: 0,728 (mínimo 0,5); cumple el margen mínimo: sí.

- Preguntas sin respuesta que frena el umbral propuesto: EV-025, EV-026, EV-030 (de 6 con puntaje); las que frena el actual: EV-025, EV-026, EV-030.
- Preguntas con respuesta que frena el umbral propuesto: ninguna (de 24 con puntaje); las que frena el actual: EV-020.
- Preguntas de tema cercano que quedan por encima del umbral propuesto (las tiene que frenar el modelo): EV-027, EV-028, EV-029.
- Preguntas con respuesta sin puntaje (ningún umbral las cambia): ninguna.

Puntajes del lote de ajuste:

| Caso | Grupo | Régimen | Puntaje más alto | Escala anterior a la sigmoide |
|---|---|---|---|---|
| EV-001 | con respuesta | Disposición AFIP 247/2022 | 0,9982 | 6,3129 |
| EV-002 | con respuesta | Disposición AFIP 247/2022 | 0,9996 | 7,8373 |
| EV-003 | con respuesta | Disposición AFIP 247/2022 | 0,9995 | 7,6875 |
| EV-004 | con respuesta | Disposición AFIP 247/2022 | 0,5077 | 0,0310 |
| EV-005 | con respuesta | Disposición AFIP 247/2022 | 0,9984 | 6,4297 |
| EV-006 | con respuesta | Disposición AFIP 247/2022 | 0,9962 | 5,5741 |
| EV-007 | con respuesta | Disposición AFIP 247/2022 | 0,7482 | 1,0891 |
| EV-008 | con respuesta | Disposición AFIP 247/2022 | 0,9997 | 7,9723 |
| EV-009 | con respuesta | Disposición AFIP 247/2022 | 0,9922 | 4,8469 |
| EV-010 | con respuesta | Disposición AFIP 247/2022 | 0,9975 | 6,0077 |
| EV-011 | con respuesta | Disposición AFIP 247/2022 | 0,9864 | 4,2836 |
| EV-012 | con respuesta | Disposición AFIP 247/2022 | 0,9940 | 5,1064 |
| EV-013 | con respuesta | Disposición AFIP 247/2022 | 0,9983 | 6,3811 |
| EV-014 | con respuesta | Disposición AFIP 247/2022 | 0,9954 | 5,3702 |
| EV-015 | con respuesta | Disposición AFIP 247/2022 | 0,9993 | 7,2396 |
| EV-016 | con respuesta | Disposición AFIP 297/03 | 0,9995 | 7,6950 |
| EV-017 | con respuesta | Disposición AFIP 297/03 | 0,9994 | 7,4452 |
| EV-018 | con respuesta | Disposición AFIP 297/03 | 0,9839 | 4,1112 |
| EV-019 | con respuesta | Disposición AFIP 297/03 | 0,9985 | 6,5090 |
| EV-020 | con respuesta | Disposición AFIP 297/03 | 0,3680 | −0,5407 |
| EV-021 | con respuesta | Disposición AFIP 297/03 | 0,9971 | 5,8461 |
| EV-022 | con respuesta | Disposición AFIP 297/03 | 0,9989 | 6,8002 |
| EV-023 | con respuesta | Disposición AFIP 297/03 | 0,9845 | 4,1481 |
| EV-024 | con respuesta | Disposición AFIP 297/03 | 0,9952 | 5,3338 |
| EV-025 | ajena a la normativa | Disposición AFIP 247/2022 | 0,1195 | −1,9967 |
| EV-026 | ajena a la normativa | Disposición AFIP 247/2022 | 0,0218 | −3,8017 |
| EV-027 | tema cercano | Disposición AFIP 247/2022 | 0,7751 | 1,2372 |
| EV-028 | tema cercano | Disposición AFIP 247/2022 | 0,9881 | 4,4183 |
| EV-029 | tema cercano | Disposición AFIP 297/03 | 0,7430 | 1,0617 |
| EV-030 | ajena a la normativa | Disposición AFIP 297/03 | 0,0032 | −5,7331 |

## Comparación quitando piezas

No se corrió en esta corrida. Se corre una vez, con `correr_evals --quitando-piezas` (ADR-0003).

## Comparación con la corrida anterior

Corrida anterior: la del 03/10/2026 13:20 (carpeta `2026-10-03T132016_8ad46e6_gemma-4-12b-it-qat-q4_0`).

Esta carpeta es una recalificación de esa corrida: las respuestas son las mismas y solo cambian los casos o el corrector. Una recalificación no es una corrida nueva a los efectos de P7.

Cada lote se compara con el mismo lote de la anterior; en una corrida sin el campo `lote`, todos los casos son del lote de ajuste. El tiempo es de toda la corrida.

### Lote de aceptación

Ninguna de las dos corridas tiene casos de este lote.

### Lote de ajuste

| Medida | Anterior | Actual | Cambio |
|---|---|---|---|
| Cita literal | 100,0 % | 100,0 % | igual |
| Respuesta correcta que cita la unidad correcta | 45,8 % | 79,2 % | mejora |
| Abstención | 85,7 % | 85,7 % | igual |

### Tiempo de toda la corrida

| Medida | Anterior | Actual | Cambio |
|---|---|---|---|
| Tiempo de respuesta (mediana) | 4,54 s | 4,54 s | igual |
| Tiempo de respuesta (máximo) | 9,62 s | 9,62 s | igual |

- Pasaban y ahora fallan: ninguno.
- Fallaban y ahora pasan: EV-003, EV-005, EV-011, EV-012, EV-014, EV-016, EV-018, EV-021.
- Cambiaron de resultado o de citas sin cambiar si pasan: ninguno.
- Solo en la anterior: ninguno. Solo en esta: ninguno.

Con unas 30 preguntas, cada una pesa entre 3 y 5 puntos: una diferencia de una pregunta no demuestra nada.

## Casos fallados

Casos del lote de ajuste.

- EV-006: respuesta incorrecta (faltan datos clave: "revisión", "máxima autoridad").
- EV-009: respuesta incorrecta (faltan datos clave: "acuerdo marco interadministrativo", "acuerdo interadministrativo por imperio normativo").
- EV-017: respuesta incorrecta (faltan datos clave: "pérdida de la garantía de la oferta").
- EV-020: respuesta incorrecta (no hubo respuesta con fundamento, no cita la unidad esperada, faltan datos clave: "1 %", "7 días corridos", "fracción", "3 días"); aviso de modificatorias distinto del esperado.
- EV-024: respuesta incorrecta (no cita la unidad esperada, faltan datos clave: "2 días", "licitaciones privadas", "contrataciones directas").
- EV-028: no se abstuvo.

## Casos fallados del lote de aceptación

La corrida no tiene casos del lote de aceptación.

## Casos no corridos

Ninguno.
