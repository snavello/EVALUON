# ADR-0071 · Cierre del paso 2: las instrucciones cortas y las reglas a tres salidas quedan en el modelo local

Estado: aceptado · Fecha: 2026-10-16 · Propuso: Coordinador (T-287, plan 016) · Decidió: responsable del proyecto (2026-10-16, «Cerrá el paso 2 con las instrucciones cortas (ADR-0071, T-287) y pasá D-286-1 a D-286-8 a la lista de revisión con el primer producto.»)

## Contexto

El paso 2 de la feature 016 (REQ-119 y REQ-120; ADR-0070) reemplazó las instrucciones acumuladas de la 015 por instrucciones cortas (solo definiciones y decisiones vigentes, sin ejemplos de casos, con su tabla de decisiones en `specs/016-calidad-medible/revision-instrucciones.md`) y llevó las reglas de decisión a tres salidas por celda (`reglas-v15`). Se construyó en T-278 a T-282, se midió en T-283 (ronda 1: no pasa, 4 de 6 umbrales), se ajustó una sola vez en T-285 (16 commits, un hallazgo por commit) y se volvió a medir en T-286, que por ADR-0025 es la última ronda. La regla de la spec («si las medidas graves no empeoran y las demás empatan, queda la instrucción corta», REQ-119) no se da en sentido estricto, así que el cierre es una decisión del responsable (P7).

**Resultado de T-286 (código 573449ea, Qwen3.8-27B, ventana de GPU de 10:56 a 14:36 del 2026-10-16) contra los umbrales 7 a 12 del plan:**

| # | Qué | Umbral (escrito antes) | T-283 (ronda 1) | T-286 (ronda 2) | Cumple |
|---|---|---|---|---|---|
| 7 | Medidas graves | 0 «cumple» sin fundamento, 0 contradicciones, 100 % citas literales | 1 contradicción, 4 erradas de 48 | 0 contradicciones, **0 erradas de 48** (T-263: 1), citas 100 % en la evaluación y en las 4 matrices; 1 «cumple» con fundamento débil (O1 R62) | sí, con un reparo |
| 8 | Lista presente de la matriz | 00 41/42, 01 79/80, 02 95/97, 06 35/35 (T-266) | 37, 76, 93, 32 | **39/42, 78/80, 94/97, 34/35**: falta la presentación física en firme en los cuatro casos (queda como sugerencia, en el 01 descartada) y M-007 del 00 | no (0 de 4) |
| 9 | Tres salidas | 0 «no se encontró el documento» sin pregunta; 100 % «no determinado» con pregunta o documento | sí | 0 de 1; 52 de 52; preguntas conformes 21 de 24 (T-263 14 de 17) | sí |
| 10 | Las demás no empeoran | firmes con pareja ≥ 70 % sin bajar 10 puntos; filas que la Comisión conserva; exactitud por celda (ADR-0059) | no (filas que conserva 90,0 %) | firmes con pareja 93,3 / 91,1 / 96,2 / 95,8 %; la Comisión conserva 96,7 %; 4 filas en contra y 2 a favor | sí |
| 11 | Tiempo y memoria | caso-00 ≤ 112,6 min y ≤ 22.000 MiB | sí | **88,9 min** (T-266 102,4) y 21.138 MiB | sí |
| 12 | Auxiliares | evals 16/17, 6/6, 100 % cita, ≤ 30 s; fichas y visión sin bajar de T-249 | no | evals **15/17** por el corrector (16/17 por lectura; `consulta-v6` se abstiene en EV-010 y EV-012; aviso REQ-021 56/56), 6/6, 104/104, 21,0 s; visión DNI 15/18 y pagaré 10/18 (−1 cada uno); fichas 21/55 (T-249 16/55) | no |

Evaluación del caso-00 (48 celdas de la Comisión, versión 3b): exactas 26, abstenciones 22, erradas 0 (T-263 con las instrucciones largas: 30, 17 y 1; T-283: 21, 23 y 4). Coincidencia con el dictamen 35/42. «No determinado» que cuenta: 33,3 % (T-263 25,4 %; meta de la 015 15 %).

**Tamaño de las instrucciones** (líneas y caracteres, con el bloque de definiciones incluido en las decisoras):

| Instrucción | 015 (vigente antes) | 016 (vigente ahora) |
|---|---|---|
| Evaluación | `evaluacion-v12`: 161 líneas, 36.609 | `evaluacion-v14`: 43 líneas, 7.738 |
| Extracción de la matriz | `matriz-extraccion-v12`: 207, 26.784 | `matriz-extraccion-v14`: 37, 3.176 (+ definiciones v10: 32, 3.821) |
| Filtro de la matriz | `matriz-filtro-v9`: 194, 26.312 | `matriz-filtro-v11`: 44, 3.651 |
| Ficha | `ficha-v3`: 107, 5.118 | `ficha-v4`: 16, 1.474 |
| Ficha por renglón | `ficha-renglon-v5`: 130, 6.408 | `ficha-renglon-v6`: 18, 1.808 |

Todas las instrucciones vigentes cumplen el tope del ADR-0070 (test de largo), no tienen ejemplos de casos (test de no calco contra el corpus: 0 secuencias de 6 palabras) y tienen su tabla de decisiones (test de revisión); los tests `decision_literal` (246) siguen verdes.

**El paso 1 (verdad ampliada, ADR-0069) sigue abierto:** en el corpus solo el caso-00 tiene ofertas y dictamen; T-272 a T-276 esperan las ofertas y el dictamen de tres procesos más, que aporta el responsable. La evaluación del paso 2 se midió sobre las 48 celdas del caso-00 y las matrices sobre los casos 00, 01, 02 y 06.

## Alternativas

### A. Cerrar el paso 2 con las instrucciones cortas y `reglas-v15` (elegida)

Se gana: 0 celdas erradas y 0 contradicciones con el dictamen (lo grave, P3); tres salidas al 100 % con pregunta o documento nombrado (REQ-120); instrucciones que el responsable controla oración por oración contra su tabla (escenario 2 de la spec); un cuarto del contexto para la instrucción y el resto para los documentos; 13 % menos de tiempo en el caso-00; una referencia local estable para medir los pasos 3 y 4. Se pierde: la presentación física queda como sugerencia (la Comisión la acepta en 00, 02 y 06 y la carga a mano en 01); 4 exactas menos y 7 preguntas más que T-263 en el caso-00 (24 contra 17); la Consulta se abstiene en dos evals donde antes contestaba; la visión lee un dato menos en el DNI y en el pagaré. Todo eso va a la lista de revisión con el primer producto (D-286-1 a D-286-8).

### B. Una ronda más de ajuste

ADR-0025 la admite solo si se pierde un requisito o se viola un principio. No se pierde ninguno: la presentación física sigue propuesta (como sugerencia), ningún caso pierde 3 o más entradas de la lista (ADR-0059, regla 2) y no hay erradas. Se perdería una ventana más de GPU (4 h) y se volvería a ajustar sobre el caso-00, que es el círculo que la 016 vino a cortar (un solo caso de evaluación: ninguna mejora se distingue del ruido).

### C. Volver a las instrucciones de la 015

Se gana: +1 en la lista presente de cada caso y 16/17 en las evals. Se pierde: la celda errada y la contradicción que T-263 tenía, las tres salidas garantizadas, la tabla de decisiones (las instrucciones largas no son controlables oración por oración) y 29.000 caracteres de contexto por pedido en la evaluación.

### D. Mezcla: cortas en la matriz, largas en la evaluación o `consulta-v4`

Se pierde la regla del ADR-0070 (toda instrucción vigente es corta y tiene tabla) y la comparación de los pasos 3 y 4 contra una sola referencia. `consulta-v4` era la vuelta prevista si T-286 no recuperaba la Consulta: la recuperó (REQ-021 56/56, 6/6 abstenciones, 104/104 citas); lo que queda (EV-010 y EV-012) es un ajuste de la lista de revisión.

## Decisión

Se elige **A**.

1. **Quedan como vigentes del modelo local** `matriz-definiciones-v10`, `matriz-extraccion-v14`, `matriz-filtro-v11`, `matriz-completitud-v7`, `matriz-union-v2`, `matriz-consecuencias-v3`, `matriz-respaldo-v3`, `matriz-circulares-v8`, `matriz-circulares-cambios-v7`, `evaluacion-v14`, `contraste-v5`, `clausulas-v6`, `reescritura-v3`, `vision-v6`, `ficha-v4`, `ficha-renglon-v6`, `informe-tecnico-v3`, `oferente-nombre-v3`, `procedimiento-datos-v3`, `consulta-v6` y `reglas-v15`, con el código de T-277 y T-285 (`combine.py`, `options.py`, `absence.py`, `portal_facts.py`, `services/evaluate.py`, `tenders/proposal/filter.py`). «No aplica» sale solo de la `opcion` de la fila de la matriz, nunca de una marca del modelo (H-285-1).
2. **La corrida de T-286 es la referencia local de los pasos 3 y 4** (T-293, T-301 y T-307): caso-00 con la versión 3b (fila 80 con `opcion` = `mipyme`), 26 exactas, 22 abstenciones, 0 erradas, 88,9 min, 21.138 MiB; matrices 39/42, 78/80, 94/97 y 34/35; evals de la 001 15/17 por el corrector. Las corridas quedan en la carpeta local del Coordinador (`coord\t286-out`) y la base `evaluon_clon_e2` del clon.
3. **D-286-1 a D-286-8 pasan a la lista de revisión con el primer producto**, con su impacto para la Comisión del piloto: la presentación física llega como sugerencia (hay que aceptarla; en el caso 01, cargarla a mano); en el caso-00, 24 preguntas contra 17 y 0 errores contra su decisión; «no determinado» 33,3 %. Se corrigen en una sola tarea por lote, con una medición por lote (ADR-0025).
4. **El paso 1 no cierra con este ADR.** Cierra con T-276 cuando haya verdad celda por celda de tres casos más. Esa verdad mide, no reabre: el paso 2 se reabre solo si con ella se pierde un requisito o se viola un principio (ADR-0025).
5. **Integración.** `016-integracion` (T-270, T-271, T-277 a T-283, T-285, T-286, T-288 a T-292, T-299 y T-300) se integra a `main` con la suite completa en verde sobre la combinación (ADR-0012, lote 4 en `tasks.md`). Con el uso externo apagado (valor por omisión), nada de lo del paso 3 corre.
6. **El piloto de 8000 no cambia por esta integración.** La raíz del repositorio (lo que monta 8000) se actualiza y se migra (`audit.0009_externo`) solo cuando el responsable apruebe el despliegue de la feature (etapa 7, `implementador`), o antes si lo pide: hasta entonces 8000 sigue con las instrucciones de la 015 y la Comisión no ve el cambio.

## Consecuencias

- Más fácil: medir los pasos 3 y 4 contra una sola referencia local; controlar cada instrucción contra su tabla; que un hallazgo nuevo se escriba como definición y no como ejemplo (el test de no calco lo impide).
- Más difícil: la Comisión del piloto recibe la presentación física como sugerencia y más preguntas en el caso-00 hasta que la lista de revisión se corrija; la meta de «no determinado» ≤ 15 % de la 015 queda lejos (33,3 %) y se persigue con la verdad ampliada y el verificador del paso 4, no con otra ronda de instrucciones.
- Para revertir: las de ADR-0070 (volver las versiones de `MATRIX_PROMPT_VERSIONS`, `ASSESSMENT_PROMPT_VERSIONS`, `OFFERS_PROMPT_VERSIONS`, `ASSESSMENT_VISION_PROMPT_VERSION`, `consulta` y `ASSESSMENT_RULES_VERSION` a las de la 015 y revertir `combine.py` y las reglas del Portal); las huellas de las versiones anteriores siguen congeladas en `tests/fixtures/instrucciones.sha256`.
