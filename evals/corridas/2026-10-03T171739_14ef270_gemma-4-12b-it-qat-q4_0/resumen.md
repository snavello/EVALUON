# Corrida del 03/10/2026 17:17

- Carpeta: `2026-10-03T171739_14ef270_gemma-4-12b-it-qat-q4_0`
- Comienzo: 03/10/2026 17:17 · fin: 03/10/2026 17:21
- Commit: `14ef270`
- Modelo de generación: `gemma-4-12b-it-qat-q4_0` (compilación `b11347`)
- Versión de las instrucciones: consulta-v3
- Versión de la normativa: 5
- Umbral del modelo que reordena los resultados (reranker): 0,219
- Casos leídos: 56 · corridos: 56 · 0 sin visto bueno · 0 mal formados

## Medidas exigidas

La cita literal y el tiempo se miden sobre toda la corrida; la respuesta correcta y la abstención, sobre el lote de aceptación (ADR-0014; plan, "Lote de aceptación").

| Exigencia | Resultado | Umbral | Cumple |
|---|---|---|---|
| Cita literal (toda la corrida) | 100,0 % (113 de 113; IC 95 %: 96,7 % a 100 %) | 100 % | sí |
| Respuesta correcta que cita la unidad correcta (lote de aceptación) | 94,1 % (16 de 17; IC 95 %: 73,0 % a 99,0 %) | al menos 85 % | sí |
| Abstención (lote de aceptación) | 100,0 % (6 de 6; IC 95 %: 61,0 % a 100 %) | al menos 90 % | sí |
| Tiempo de respuesta (toda la corrida) | mediana 4,03 s · máximo 8,22 s | máximo de 30 s | sí |

IC 95 %: intervalo de confianza al 95 % por el método de Wilson (plan, "Margen de error"). La exigencia se compara con el valor medido; el intervalo dice cuánto se le puede creer. Una falla técnica no cuenta como abstención. El responsable revisa además las respuestas contra la esperada.

## Lote de ajuste (diagnóstico)

Casos sin `lote` o con `lote: ajuste` (ADR-0014): son los que se usan para ajustar el corrector, los datos clave, el umbral y las instrucciones. Se informan como diagnóstico; no sirven para dar por cumplidas las exigencias.

| Medida | Resultado |
|---|---|
| Cita literal | 100,0 % (74 de 74; IC 95 %: 95,1 % a 100 %) |
| Respuesta correcta que cita la unidad correcta | 85,2 % (23 de 27; IC 95 %: 67,5 % a 94,1 %) |
| Abstención | 100,0 % (6 de 6; IC 95 %: 61,0 % a 100 %) |

## Medidas por régimen (diagnóstico)

Casos del lote de ajuste, separados según el régimen esperado de cada caso. Son de diagnóstico: las exigencias de la spec se miden con el lote de aceptación, y con pocos casos por régimen sirven solo para orientar.

| Régimen | Respuesta correcta | Abstención |
|---|---|---|
| Disposición AFIP 247/2022 | 88,2 % (15 de 17; IC 95 %: 65,7 % a 96,7 %) | 100,0 % (3 de 3; IC 95 %: 43,8 % a 100 %) |
| Disposición AFIP 297/03 | 80,0 % (8 de 10; IC 95 %: 49,0 % a 94,3 %) | 100,0 % (2 de 2; IC 95 %: 34,2 % a 100 %) |
| Sin régimen cargado a la fecha | — | 100,0 % (1 de 1; IC 95 %: 20,7 % a 100 %) |

## Pares de REQ-020

| Par | Resultado | Detalle |
|---|---|---|
| EV-001 y EV-016 | pasa | — |
| EV-003 y EV-017 | falla | EV-017 no pasa por su cuenta |
| EV-014 y EV-018 | pasa | — |
| EV-022 y EV-028 | pasa | — |
| EV-034 y EV-035 | pasa | — |
| EV-036 y EV-037 | pasa | — |
| EV-038 y EV-039 | pasa | — |
| EV-049 y EV-050 | pasa | — |

## Aviso de REQ-021

56 de 56 casos traen o no traen el aviso de modificatorias sin cargar según lo esperado.

## Recuperación (diagnóstico)

Casos del lote de ajuste, leído del registro de cada consulta. La unidad correcta cuenta si están todas las unidades esperadas del caso (un inciso vale con su artículo); se mide sobre las preguntas con respuesta (ADR-0003).

| Medida | Resultado |
|---|---|
| Unidad correcta entre los candidatos por significado | 100,0 % (27 de 27) |
| Unidad correcta entre los candidatos por palabras | 100,0 % (27 de 27) |
| Unidad correcta entre los candidatos por referencia exacta | 0,0 % (0 de 27) |
| Unidad correcta entre los candidatos en la unión | 100,0 % (27 de 27) |
| Unidad correcta entre las enviadas al modelo | 96,3 % (26 de 27) |
| Posición de la unidad correcta en el orden del reranker | mediana 1 · peor 4 |
| Preguntas con respuesta frenadas por el umbral | 0,0 % (0 de 27) |
| Preguntas sin respuesta frenadas por el umbral | 83,3 % (5 de 6) |
| Tiempo de la recuperación | mediana 0,56 s · máximo 0,75 s |

Preguntas con respuesta frenadas por el umbral: ninguna.
Preguntas con respuesta cuya unidad correcta no llegó al modelo: EV-024.

## Salidas con falla de formato o de cita

Se cuentan por el tipo de anomalía; una falla de un servicio no cuenta. Se espera ninguna.

- Falla de formato (la salida no cumple el esquema): 0 (ninguno).
- Falla de cita (cita una unidad que no se mostró o una afirmación sin cita): 0 (ninguno).

## Casos de REQ-018 y REQ-019

- REQ-018 (etiqueta "dos categorías"): ningún caso corrido.
- REQ-019 (casos con la marca de regímenes distintos: el régimen específico y el marco nacional difieren): ningún caso corrido.

## Calibración del umbral (provisoria)

Umbral propuesto (provisorio): 0,219 · A (ajena a la normativa más alta): EV-025, 0,1195 · B (con respuesta más baja): EV-020, 0,3680 · margen 0,728 (mínimo 0,5) · cumple el margen mínimo: sí · umbral actual: 0,219.

Regla del hueco (ADR-0014, punto 2; plan, "Abstención"): con las preguntas del lote de ajuste, el umbral va en el punto medio, en la escala anterior a la sigmoide, entre la pregunta ajena a la normativa con el puntaje más alto (A) y la pregunta con respuesta con el puntaje más bajo (B), redondeado hacia abajo a tres decimales; el margen es la mitad del hueco y el mínimo, 0,5. Las preguntas de tema cercano no entran: las tiene que frenar el modelo. La calibración no cambia el umbral configurado del sistema: el valor es provisorio y fijarlo es una decisión aparte.

| Dato | Caso | Puntaje | Escala anterior a la sigmoide |
|---|---|---|---|
| A: ajena a la normativa más alta | EV-025 | 0,1195 | −1,9967 |
| B: con respuesta más baja | EV-020 | 0,3680 | −0,5407 |
| Punto medio | — | 0,2195 | −1,2687 |

- Margen: 0,728 (mínimo 0,5); cumple el margen mínimo: sí.

- Preguntas sin respuesta que frena el umbral propuesto: EV-025, EV-026, EV-030, EV-032, EV-033 (de 5 con puntaje); las que frena el actual: EV-025, EV-026, EV-030, EV-032, EV-033.
- Preguntas con respuesta que frena el umbral propuesto: ninguna (de 27 con puntaje); las que frena el actual: ninguna.
- Preguntas de tema cercano que quedan por encima del umbral propuesto (las tiene que frenar el modelo): ninguna.
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
| EV-027 | con respuesta | Disposición AFIP 247/2022 | 0,7751 | 1,2372 |
| EV-028 | con respuesta | Disposición AFIP 247/2022 | 0,9881 | 4,4183 |
| EV-029 | con respuesta | Disposición AFIP 297/03 | 0,7430 | 1,0617 |
| EV-030 | ajena a la normativa | Disposición AFIP 297/03 | 0,0032 | −5,7331 |
| EV-032 | tema cercano | Disposición AFIP 297/03 | 0,0011 | −6,7698 |
| EV-033 | tema cercano | Disposición AFIP 247/2022 | 0,0234 | −3,7310 |

## Comparación quitando piezas

No se corrió en esta corrida. Se corre una vez, con `correr_evals --quitando-piezas` (ADR-0003).

## Comparación con la corrida anterior

Corrida anterior: la del 03/10/2026 16:51 (carpeta `2026-10-03T165105_d5b96d4_gemma-4-12b-it-qat-q4_0`).

Cambió: commit. No es una repetición: las diferencias pueden venir de ese cambio.

Cada lote se compara con el mismo lote de la anterior; en una corrida sin el campo `lote`, todos los casos son del lote de ajuste. El tiempo es de toda la corrida.

### Lote de aceptación

| Medida | Anterior | Actual | Cambio |
|---|---|---|---|
| Cita literal | — | 100,0 % | — |
| Respuesta correcta que cita la unidad correcta | — | 94,1 % | — |
| Abstención | — | 100,0 % | — |

### Lote de ajuste

| Medida | Anterior | Actual | Cambio |
|---|---|---|---|
| Cita literal | 100,0 % | 100,0 % | igual |
| Respuesta correcta que cita la unidad correcta | 81,5 % | 85,2 % | mejora |
| Abstención | 100,0 % | 100,0 % | igual |

### Tiempo de toda la corrida

| Medida | Anterior | Actual | Cambio |
|---|---|---|---|
| Tiempo de respuesta (mediana) | 4,79 s | 4,03 s | más rápido |
| Tiempo de respuesta (máximo) | 29,52 s | 8,22 s | más rápido |

- Pasaban y ahora fallan: ninguno.
- Fallaban y ahora pasan: EV-003.
- Cambiaron de resultado o de citas sin cambiar si pasan: ninguno.
- Solo en la anterior: ninguno. Solo en esta: EV-034, EV-035, EV-036, EV-037, EV-038, EV-039, EV-040, EV-041, EV-042, EV-043, EV-044, EV-045, EV-046, EV-047, EV-048, EV-049, EV-050, EV-051, EV-052, EV-053, EV-054, EV-055, EV-056.

Igualdad al repetir: 33 de 33 casos corridos en las dos dan el mismo resultado (estado, motivo, citas y texto de las afirmaciones); 33 de 33 con el mismo estado, el mismo motivo y las mismas citas. Con temperatura 0 y semilla fija, la primera consulta después de levantar el motor puede redactar distinto sin cambiar estado, motivo ni citas (T-018).

Con unas 30 preguntas, cada una pesa entre 3 y 5 puntos: una diferencia de una pregunta no demuestra nada.

## Casos fallados

Casos del lote de ajuste.

- EV-006: respuesta incorrecta (faltan datos clave: "revisión", "máxima autoridad").
- EV-009: respuesta incorrecta (faltan datos clave: "acuerdo marco interadministrativo", "acuerdo interadministrativo por imperio normativo").
- EV-017: respuesta incorrecta (faltan datos clave: "pérdida de la garantía de la oferta").
- EV-024: respuesta incorrecta (no cita la unidad esperada, faltan datos clave: "2 días", "licitaciones privadas", "contrataciones directas").

## Casos fallados del lote de aceptación

Estos casos no se usan para ajustar (plan, "Lote de aceptación"): cambiar instrucciones, umbral, parámetros de búsqueda, reglas de partición, o datos clave o variantes a partir de ellos le quita al lote su condición.

- EV-044: respuesta incorrecta (no hubo respuesta con fundamento, no cita la unidad esperada, faltan datos clave: "60 días corridos", "renuncia tácita").

## Casos no corridos

Ninguno.
