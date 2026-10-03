# Recalificación de la corrida del 03/10/2026 13:20

Recalificación de la carpeta `2026-10-03T132016_8ad46e6_gemma-4-12b-it-qat-q4_0`, hecha el 03/10/2026 14:59 con el commit `30dc41e` y los casos de `evals/casos`. Recalificación: no se hicieron consultas ni se llamó a ningún servicio de IA. Las respuestas son las de la corrida de origen, medidas otra vez con los casos y el corrector vigentes. Se compara con esa corrida al final. Salvo la carpeta y las cantidades de casos, los datos que siguen son los de la corrida de origen.

- Carpeta: `2026-10-03T145904_30dc41e_gemma-4-12b-it-qat-q4_0_recalificada`
- Comienzo: 03/10/2026 13:20 · fin: 03/10/2026 13:22
- Commit: `8ad46e6`
- Modelo de generación: `gemma-4-12b-it-qat-q4_0` (compilación `b11347`)
- Versión de las instrucciones: consulta-v2
- Versión de la normativa: 5
- Umbral del modelo que reordena los resultados (reranker): 0,500
- Casos leídos: 31 · corridos: 31 · 0 sin visto bueno · 0 mal formados

## Medidas exigidas

| Exigencia | Resultado | Umbral | Cumple |
|---|---|---|---|
| Cita literal | 100,0 % (72 de 72 citas) | 100 % | sí |
| Respuesta correcta que cita la unidad correcta | 79,2 % (19 de 24 preguntas con respuesta) | al menos 85 % | no |
| Abstención | 85,7 % (6 de 7 preguntas sin respuesta) | al menos 90 % | no |
| Tiempo de respuesta | mediana 4,54 s · máximo 9,62 s | máximo de 30 s | sí |

Una falla técnica no cuenta como abstención. El responsable revisa además las respuestas contra la esperada.

## Medidas por régimen (diagnóstico)

Separadas según el régimen esperado de cada caso. Son de diagnóstico: las exigencias de la spec se miden sobre el conjunto entero, y con pocos casos por régimen sirven solo para orientar.

| Régimen | Respuesta correcta | Abstención |
|---|---|---|
| Disposición AFIP 247/2022 | 86,7 % (13 de 15) | 75,0 % (3 de 4) |
| Disposición AFIP 297/03 | 66,7 % (6 de 9) | 100,0 % (2 de 2) |
| Sin régimen cargado a la fecha | — (0 de 0) | 100,0 % (1 de 1) |

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

Leído del registro de cada consulta. La unidad correcta cuenta si están todas las unidades esperadas del caso (un inciso vale con su artículo); se mide sobre las preguntas con respuesta (ADR-0003).

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

Umbral propuesto (provisorio): 0,368 · umbral actual: 0,500. La calibración no cambia el umbral configurado del sistema: el valor lo fija T-045 con los servicios reales y el conjunto con visto bueno.

- Preguntas con respuesta que llegaron a puntuarse: 24. Se eligió el puntaje número 1 de 24, contados de menor a mayor: es el más alto que, dejando cada vez una pregunta afuera, frena por error a lo sumo el 5,0 %.
- Dejando cada vez una afuera: frena 1 de 24 (4,2 %); el umbral calculado va de 0,368 a 0,507; cumple el 5,0 %: sí. Frenadas: EV-020.
- Con el umbral propuesto, frena por error en el conjunto completo: ninguna.
- Para comparar, la regla anterior (frenar a lo sumo el 5,0 % del conjunto completo, sin dejar ninguna afuera) daría 0,507, que frena EV-020; dejando cada vez una afuera frenaría el 8,3 %.
- Con el umbral actual, frena por error: EV-020.
- Preguntas sin respuesta que el umbral propuesto frena: 3 de 6.
- Preguntas con respuesta sin puntaje (ningún umbral las cambia): ninguna.

| Caso | Con respuesta | Régimen | Puntaje más alto |
|---|---|---|---|
| EV-001 | sí | Disposición AFIP 247/2022 | 0,998 |
| EV-002 | sí | Disposición AFIP 247/2022 | 1,000 |
| EV-003 | sí | Disposición AFIP 247/2022 | 1,000 |
| EV-004 | sí | Disposición AFIP 247/2022 | 0,508 |
| EV-005 | sí | Disposición AFIP 247/2022 | 0,998 |
| EV-006 | sí | Disposición AFIP 247/2022 | 0,996 |
| EV-007 | sí | Disposición AFIP 247/2022 | 0,748 |
| EV-008 | sí | Disposición AFIP 247/2022 | 1,000 |
| EV-009 | sí | Disposición AFIP 247/2022 | 0,992 |
| EV-010 | sí | Disposición AFIP 247/2022 | 0,998 |
| EV-011 | sí | Disposición AFIP 247/2022 | 0,986 |
| EV-012 | sí | Disposición AFIP 247/2022 | 0,994 |
| EV-013 | sí | Disposición AFIP 247/2022 | 0,998 |
| EV-014 | sí | Disposición AFIP 247/2022 | 0,995 |
| EV-015 | sí | Disposición AFIP 247/2022 | 0,999 |
| EV-016 | sí | Disposición AFIP 297/03 | 1,000 |
| EV-017 | sí | Disposición AFIP 297/03 | 0,999 |
| EV-018 | sí | Disposición AFIP 297/03 | 0,984 |
| EV-019 | sí | Disposición AFIP 297/03 | 0,999 |
| EV-020 | sí | Disposición AFIP 297/03 | 0,368 |
| EV-021 | sí | Disposición AFIP 297/03 | 0,997 |
| EV-022 | sí | Disposición AFIP 297/03 | 0,999 |
| EV-023 | sí | Disposición AFIP 297/03 | 0,984 |
| EV-024 | sí | Disposición AFIP 297/03 | 0,995 |
| EV-025 | no | Disposición AFIP 247/2022 | 0,120 |
| EV-026 | no | Disposición AFIP 247/2022 | 0,022 |
| EV-027 | no | Disposición AFIP 247/2022 | 0,775 |
| EV-028 | no | Disposición AFIP 247/2022 | 0,988 |
| EV-029 | no | Disposición AFIP 297/03 | 0,743 |
| EV-030 | no | Disposición AFIP 297/03 | 0,003 |

## Comparación quitando piezas

No se corrió en esta corrida. Se corre una vez, con `correr_evals --quitando-piezas` (ADR-0003).

## Comparación con la corrida anterior

Corrida anterior: la del 03/10/2026 13:20 (carpeta `2026-10-03T132016_8ad46e6_gemma-4-12b-it-qat-q4_0`).

Esta carpeta es una recalificación de esa corrida: las respuestas son las mismas y solo cambian los casos o el corrector. Una recalificación no es una corrida nueva a los efectos de P7.

| Medida | Anterior | Actual | Cambio |
|---|---|---|---|
| Cita literal | 100,0 % | 100,0 % | igual |
| Respuesta correcta que cita la unidad correcta | 45,8 % | 79,2 % | mejora |
| Abstención | 85,7 % | 85,7 % | igual |
| Tiempo de respuesta (mediana) | 4,54 s | 4,54 s | igual |
| Tiempo de respuesta (máximo) | 9,62 s | 9,62 s | igual |

- Pasaban y ahora fallan: ninguno.
- Fallaban y ahora pasan: EV-003, EV-005, EV-011, EV-012, EV-014, EV-016, EV-018, EV-021.
- Cambiaron de resultado o de citas sin cambiar si pasan: ninguno.
- Solo en la anterior: ninguno. Solo en esta: ninguno.

Con unas 30 preguntas, cada una pesa entre 3 y 5 puntos: una diferencia de una pregunta no demuestra nada.

## Casos fallados

- EV-006: respuesta incorrecta (faltan datos clave: "revisión", "máxima autoridad").
- EV-009: respuesta incorrecta (faltan datos clave: "acuerdo marco interadministrativo", "acuerdo interadministrativo por imperio normativo").
- EV-017: respuesta incorrecta (faltan datos clave: "pérdida de la garantía de la oferta").
- EV-020: respuesta incorrecta (no hubo respuesta con fundamento, no cita la unidad esperada, faltan datos clave: "1 %", "7 días corridos", "fracción", "3 días"); aviso de modificatorias distinto del esperado.
- EV-024: respuesta incorrecta (no cita la unidad esperada, faltan datos clave: "2 días", "licitaciones privadas", "contrataciones directas").
- EV-028: no se abstuvo.

## Casos no corridos

Ninguno.
