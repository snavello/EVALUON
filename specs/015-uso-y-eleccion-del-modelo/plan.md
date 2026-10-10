# Plan 015 · Uso y elección del modelo

Estado: aprobado · Fecha: 2026-10-10 · Aprobó: responsable del proyecto (2026-10-10, «ok a todo»), con la ejecución en cuatro tandas propuesta por el Coordinador

Spec: `specs/015-uso-y-eleccion-del-modelo/spec.md` (aprobada el 2026-10-10)

ADR de este plan, **propuestos**: `docs/adr/0053-dato-del-portal-que-coincide-propone-cumple.md` (reemplaza en parte al ADR-0043), `docs/adr/0054-matriz-oracion-completa-y-definiciones-del-responsable.md` (enmienda al ADR-0019, decisiones 2 y 3, y al ADR-0021: motivos de descarte nuevos y regla «ante la duda»), `docs/adr/0055-razonamiento-en-el-json-antes-del-veredicto.md` y `docs/adr/0056-candidatos-qwen-y-protocolo-de-comparacion.md`. El resultado de la comparación irá en un ADR nuevo, reservado como **ADR-0057** (lo redacta T-247). Se apoya en los ADR 0002, 0019, 0024, 0025, 0027, 0041, 0042 y 0043.

Entradas fuera del repositorio (carpeta local del Coordinador, con texto de casos): `diagnostico-modelo.md`, `candidatos-modelo.md` y `revision-instrucciones.md` (las 10 correcciones ordenadas, con seis pruebas a la GPU). Al repositorio van solo cifras y conclusiones (P4).

## Resumen del enfoque

El orden lo fijó el responsable: **primero cerrar el gap, después lo demás**. El diagnóstico del 2026-10-10 atribuye cerca del 85 % de los errores de T-229 al uso del modelo y el 15 % al modelo; la revisión de las instrucciones lo confirma con la GPU: con solo las definiciones nuevas del responsable, 13 de 15 filas del primer lote del filtro pasaron de «mantener» a «descartar» (las 2 que quedaron eran las correctas). Por eso el plan corrige el uso con el mismo Gemma 4 12B, mide una vez, y recién con el uso corregido compara modelos nuevos.

1. **Correcciones de uso por código** (T-233 a T-235 y T-250), sin cambiar el modelo ni el texto de las instrucciones: el dato del Portal que coincide propone «cumple»; la cita de la matriz y de la evaluación se amplía por código hasta la oración completa; el encabezado del inciso viaja con la cita; el Portal le llega al modelo como bloque citable; el contraste ve el contexto; las preguntas a la Comisión se arman con requisito, conclusión y texto; y la lista cerrada de motivos de descarte se amplía (una migración, a cargo de un solo agente, T-250).
2. **Reescritura de las instrucciones** (T-236, T-252 y T-237), con un bloque común de definiciones copiado literal de las decisiones del responsable, sin las reglas que empujan al error («dividí», «fragmento más corto», «mantené ante la duda»), con ejemplos balanceados, razonamiento antes del veredicto, lotes más grandes y la versión y la huella de cada instrucción registradas.
3. **Preparar la comparación** (T-251): el cuerpo del pedido y el conteo de tokens de los lotes usan el motor de lotes y no `generation`. Va antes de la primera medición para que el 12B y los candidatos se midan con el mismo código.
4. **Una medición con el 12B** y el uso corregido (T-238 prepara las medidas; T-239 mide) y, como máximo, una ronda de ajuste (T-240 y T-241).
5. **Servicio de los candidatos** Qwen3.8-27B y Qwen3.6-35B-A3B (T-242, T-243, T-245): archivo de compose adicional por candidato, huellas, prueba de humo con texto e imagen, memoria, caché de prefijo y razonamiento apagado.
6. **Comparación de a uno** con el protocolo del ADR-0042 (T-244 y T-246) y un ADR de adopción o descarte (T-247).
7. **Lo demás** (T-248 y T-249): el resto de las instrucciones (consecuencias, respaldo, ficha, visión, informe técnico, consulta, propuestas de datos) con los hallazgos del informe de revisión (REQ-106), después de la comparación para que todas las corridas usen el mismo código.

Esquema: **una sola migración**, de `tenders` (motivos de descarte nuevos, T-250). Lo demás va en columnas JSON que ya existen (`parsed`, `facts`, `request`). Sin pantallas nuevas (una línea de encabezado en la fila de la matriz). Lo único infraestructural es un archivo de compose por candidato, a la manera del ADR-0042.

## Criterio de aceptación numérico y umbrales (escritos antes de medir)

Casos: caso-00 (LPU25) y casos 01 a 06, públicos. El caso reservado para evaluar a ciegas no se usa. Antes de los casos reales corre el **caso chico** y público (`tests/assessment/data/caso-chico/`) como corte vertical (ADR-0025, punto 5): si falla en forma, no se mide lo demás. Rondas: la medición del 12B (T-239) es la ronda 1; un solo ajuste con su re-medición (T-240 y T-241) es la ronda 2. Lo que no llegue pasa con su impacto a la lista de revisión con el primer producto (ADR-0024). Una ronda más solo si se pierde un requisito o se viola un principio.

| Qué | Umbral | Con qué se mide | Tarea |
|---|---|---|---|
| Filas de la matriz que la Comisión conserva (REQ-101, REQ-102) | al menos 70 % de las filas propuestas, en cada caso y en total (hoy 22 %: 27 de 122) | Caso-00: la matriz propuesta se revisa como en T-229 (mismos criterios y motivo por fila) por el testeador. Casos 01 a 06: filas firmes con pareja en la lista esperada (la medida de sobrantes de `medir_matriz`, que mide lo mismo con la lista) | T-239 |
| Pedazos sin sujeto (REQ-101) | 0 filas | Comprobación mecánica sobre todas las filas (la cita empieza donde empieza una oración o un inciso con su encabezado y termina donde termina una oración) más lectura de una muestra de 30 filas por caso | T-238, T-239 |
| Requisitos de la lista esperada que están (REQ-101, REQ-102) | al menos 95 %, sin contar las entradas excluidas por la decisión del 2026-10-10 | `medir_matriz` con la lista esperada ajustada (huella y visto bueno del Coordinador) | T-238, T-239 |
| Dato del Portal que coincide (REQ-103) | 100 % de esas celdas propuestas «cumple» con la cita del Portal; 0 celdas «cumple» con un dato que no coincide | `medir_evaluacion` con la lista de celdas del Portal del caso-00 (21 celdas de T-229 más las del caso chico) | T-238, T-239 |
| «No determinado» que no espera un documento ausente (REQ-104) | 12 de 81 celdas o menos (15 %; hoy 38 de 81 = 47 %). No cuentan las que esperan el informe técnico o una hoja de compliance (hoy 33) | `medir_evaluacion` con el caso-00 | T-239 |
| Contradicciones con el dictamen; citas literales (REQ-104) | 0; 100 % | `medir_evaluacion` | T-239 |
| Preguntas a la Comisión (REQ-105) | 100 % cumplen: dirigidas a la Comisión, con el requisito, la conclusión y el texto que las motivan | Comprobación mecánica de la forma y lectura una por una de todas las preguntas del caso-00 por el testeador | T-238, T-239 |
| Instrucciones revisadas (REQ-106) | el informe cubre el 100 % de las instrucciones vigentes; cada hallazgo de gravedad alta, corregido o justificado por escrito; cada pedido registra la versión y la huella de su instrucción | Test que lista las instrucciones vigentes y comprueba que el informe las nombra a todas y que las versiones publicadas están congeladas; revisión del Coordinador | T-236, T-252, T-237, T-248 |
| Tiempo y memoria (no funcionales) | caso-00 completo (matriz y evaluación de las 3 ofertas) en 60 minutos de GPU o menos (hoy 13,5 + 23); memoria de video máxima 22.000 MiB | Tiempos de los pedidos guardados; `nvidia-smi` durante la corrida | T-239, T-243 a T-246 |
| Adopción de un candidato (REQ-107) | cumple REQ-101 a REQ-105 al menos tan bien como el 12B de T-239 (o de T-241 si hubo ajuste), mejora al menos una medida con razones por par, no empeora contradicciones, citas, tiempo ni memoria, entra en 22.000 MiB y tarda 60 minutos o menos | Protocolo del ADR-0056 | T-244, T-246 |

El razonamiento suma entre 40 y 50 % de tokens de salida donde se usa y los modelos densos son más lentos: si con el 12B el caso-00 completo tarda más de 60 minutos, el hallazgo vuelve al ADR-0055 antes de medir candidatos, porque sin ese margen un candidato más lento no tiene dónde entrar.

## Componentes

No hay componentes nuevos. Cada tarea toca solo estas partes.

| Parte | Cambia | Qué cambia | Tarea |
|---|---|---|---|
| `evaluon/assessment/portal_facts.py`, `rules.py` | Sí | La regla del Portal compara con lo que exige el pliego y propone «cumple» o «no cumple» con la cita del Portal; versión de reglas `reglas-v8` | T-233 |
| `evaluon/tenders/proposal/sentences.py` (nuevo), `quotes.py`, `extraction.py`, `completeness.py`, `run.py`, `filter.py` | Sí | La ampliación a la oración se hace en un módulo que comparten la matriz y la evaluación (las funciones de oración salen de `filter.py`); el encabezado del inciso entra en el pedido de extracción y se ve en la fila | T-234 |
| `evaluon/tenders/models.py`, `evaluon/tenders/migrations/`, `FILTER_MOTIVES` | Sí | Motivos de descarte nuevos en `DiscardReason` y `FilterMotive` (una migración, un solo agente) | T-250 |
| `evaluon/assessment/citations.py`, `grounds.py`, `portal_block.py` (nuevo), `combine.py`, `prompting.py`, `services/evaluate.py`, `services/questions.py` | Sí | Las citas de la oferta se amplían a la oración; el requisito llega con su punto; el Portal llega al modelo como bloque citable; el contraste recibe el contexto; las preguntas se arman con requisito, conclusión y texto | T-235 |
| `evaluon/tenders/prompts/` (bloque común, extracción, completitud, circulares), loaders y `OBLIGATION_MARKERS` de `run.py`, `evaluon/settings.py` | Sí | Instrucciones nuevas con un bloque común de definiciones, sin divisiones; huella de cada instrucción | T-236 |
| `evaluon/tenders/prompts/matriz-filtro-v3.md`, `evaluon/tenders/proposal/filter.py`, `evaluon/settings.py` | Sí | Filtro A y B con las definiciones, sin «ante la duda», `razonamiento` primero, `decide()` revisada, lotes de 5 a 8 filas | T-252 |
| `evaluon/assessment/prompts/`, `prompting.py`, `services/evaluate.py`, `evaluon/settings.py` | Sí | Instrucciones nuevas de evaluación, contraste y cláusulas; `razonamiento` primero en los esquemas; reintento con memoria | T-237 |
| `evaluon/ai/generation.py` y los llamadores de `count_tokens` de los lotes | Sí | Alias real del motor de lotes en el cuerpo del pedido; tokens de los lotes contados con ese motor | T-251 |
| `evaluon/tenders/evaluation.py`, `evaluon/assessment/evaluation.py` y sus comandos de medición | Sí | Medidas nuevas de este plan y lista de celdas del Portal | T-238 |
| `docker-compose.qwen38-27b.yml`, `docker-compose.qwen36-35b.yml` (nuevos), `scripts/fetch_models.sh`, `scripts/models.sha256` | Sí | Servicio de cada candidato, a la manera del ADR-0042; el compose base no cambia | T-242 |
| Servicios de IA (`generation`, `embeddings`, `reranker`, `generation_batch`), base, `app`, `worker` | No | Sin cambios de arquitectura; `generation_batch` se reemplaza **temporalmente** durante una comparación | — |

Cómo se comunican: igual que hoy. El `worker` atiende los pedidos largos con `generation_batch`; la aplicación guarda cada pedido en `tenders_run_step` o `assessment_step` apenas vuelve. El camino de pliegos y ofertas no depende de ningún servicio externo (P4): los modelos nuevos corren con `--offline`, y bajarlos es el único paso con internet, una vez por equipo, como los demás.

## Modelo de datos

**Una migración, la de T-250** (`tenders`): los valores nuevos de `DiscardReason` (usado por `tenders_disposition.discard_reason` y sus restricciones) y de `FilterMotive` (usado por `tenders_discarded_row.reason`), que cumplen la enmienda del ADR-0019 (ADR-0054, regla 5). Solo agrega valores permitidos: las filas ya guardadas no cambian. Corre sola entre las tareas que tocan el esquema; ninguna otra tarea de este plan genera migraciones. `FILTER_MOTIVES` (en `settings.py`) y `FilterMotive.values` tienen que seguir coincidiendo (hoy lo comprueba `tests/tenders/test_models.py`).

Lo demás va en columnas JSON existentes:

- `tenders_run_step.parsed` y `assessment_step.parsed`: `razonamiento`, la versión y la huella de la instrucción, y en la extracción el fragmento que señaló el modelo junto con la oración a la que se amplió.
- `assessment_result.facts`: `regla` (`portal_cumple`, `portal_no_cumple`, `portal_falta_coincidencia`), `version_reglas` (`reglas-v8`), los valores comparados.
- `assessment_question.text`: el texto de la pregunta, que ahora lleva requisito, conclusión y texto.
- `prompt_versions` de cada corrida: nombre y huella SHA-256 de cada instrucción.

Si otra tarea descubre que necesita una columna o una restricción, la deja como hallazgo y el Coordinador decide.

## Flujo de IA

### Matriz de cumplimiento

- **Ingesta:** igual (tramos de `segmenting.py`, reglas `tramos-2`). Nuevo: un tramo que es un inciso conoce su encabezado por la clave de su tramo padre.
- **Recuperación:** no hay búsqueda; el pliego se recorre por tramos con disposición obligatoria (ADR-0019). Los lotes de extracción pasan de 1.500 a 3.000–4.000 tokens de entrada y llevan la línea `Encabezado:`; el filtro, de 15 a 5–8 filas por pedido con el punto completo de cada una.
- **Generación:** la extracción devuelve, por tramo, requisitos (un fragmento y su clase), marca técnica o motivo de descarte (con los motivos nuevos); la completitud suma oraciones completas que faltan, sin dividir; el filtro hace dos preguntas por fila (clasificación y «¿la oferta puede condicionarlo?») con `razonamiento` antes del veredicto. Todas las instrucciones incluyen el bloque común de definiciones del responsable (ADR-0054).
- **Cita:** el modelo señala un fragmento; el sistema lo ubica (`quotes.locate`) y lo **amplía por código hasta la oración completa** o el inciso; lo que se guarda es el recorte contiguo del texto canónico, así que sigue siendo literal (REQ-025). El inciso muestra su encabezado.
- **Abstención:** una duda del filtro no mantiene la fila: va a **sugerencia**. Un tramo sin disposición queda pendiente de revisión. Nada se descarta en silencio.

### Evaluación de las ofertas

- **Qué se lee:** igual (lectura completa por grupos de documentos, ADR-0037). Las páginas de lectura dudosa siguen leyéndose con visión antes de evaluar (ADR-0041), y esas lecturas ya hechas no se rehacen durante este plan. Nuevo: el modelo recibe un bloque `[P…]` con los datos del Portal de la oferta, y cada requisito llega con su punto completo y la oración citada marcada.
- **Orden de decisión:** el modelo razona, cita y recién después da el veredicto (orden del esquema: razonamiento, citas, externo e ilegible, datos, resultado, explicación, pregunta); el sistema ubica las citas y las amplía a la oración completa (REQ-104); se une el resultado de los grupos; el contraste recibe la oración y su contexto y razona antes de responder; después aplican las reglas sin modelo en su orden (externo, técnico, ilegible y **Portal**). La regla del Portal propone «cumple» o «no cumple» con la cita del Portal cuando el dato coincide o difiere de lo que exige el pliego (ADR-0053).
- **Preguntas:** las arma el código con el requisito (cita del pliego), la conclusión del sistema y el texto de la oferta (documento y página), y las dirige a la Comisión; la pregunta que escribe el modelo se acepta solo si cumple esa forma. Se elimina el texto fijo genérico (`combine.fixed_question`).
- **Abstención:** «no determinado» con su motivo, como hoy. La duda ya no se resuelve con «ante la duda, no determinado»: se declara con su razón (qué dato falta o qué texto contradice).

### Comparación de modelos

El ADR-0056 fija el protocolo: todo igual salvo el modelo, un compose por candidato, prueba de humo y control de memoria, caché de prefijo y razonamiento apagado antes de medir, compuerta de salida temprana con el caso-00 completo, y un ADR de adopción o descarte.

## Registro de auditoría

Cada pedido, propuesta y evaluación sigue registrando (P6): documentos analizados, versión de la normativa, modelo (alias, huella del archivo y del proyector, compilación del motor), contexto, temperatura, semilla, pensamiento apagado, instrucciones usadas, fragmentos recuperados, resultado, usuario y fecha. Lo que suma esta feature:

- La **versión y la huella SHA-256 de la instrucción en cada pedido** (`parsed`) y en la corrida (`prompt_versions`), y un test que congela las versiones publicadas (REQ-106).
- El **alias del modelo que atiende cada pedido de lotes** en el cuerpo del pedido, no el de `generation` (T-251).
- El **razonamiento** de cada respuesta, tal como lo escribió el modelo.
- En la matriz, el **fragmento que señaló el modelo y la oración a la que se amplió**, ambos con sus posiciones.
- En la evaluación, la **regla del Portal** (`regla`, `version_reglas`, valores comparados y los ítems del Portal citados) y el bloque `[P…]` que vio el modelo.
- Para los candidatos: el tipo de caché de claves y valores y las banderas de la caché de prefijo, en el compose y en la corrida.
- Cada medición guarda la corrida (parámetros, resultados por fila o par, resumen público con solo cifras) en la carpeta de corridas del caso, fuera del repositorio.

## Cola de GPU

Una sola tarea usa la GPU a la vez. Orden de las tareas que la usan: T-239, T-241 (si hubo ajuste), T-243, T-244, T-245, T-246, T-249; la columna «Depende de» las encadena. El Coordinador lanza una cuando la anterior terminó y su verificación quedó registrada. Mientras corre una medición no se integra nada a la carpeta que el compose monta (`./evaluon`): las corridas T-239 a T-246 se hacen sobre el mismo commit de `main`, que el informe de cada una nombra.

## Cobertura de requisitos

| Requisito | Cómo se resuelve | Cómo se verifica |
|---|---|---|
| REQ-101 | Ampliación por código a la oración y encabezado del inciso (T-234); completitud que no divide, instrucción de extracción sin «dividí» ni «fragmento más corto» (T-236) | Tests de T-234 con los casos de pedazos sin sujeto del diagnóstico; medición T-239 (0 pedazos, 70 %, 95 %) |
| REQ-102 | Bloque común de definiciones y motivos nuevos (T-250, T-236); filtro sin «ante la duda» (T-252, ADR-0054); listas esperadas ajustadas (T-238) | Tests de forma de las instrucciones y del filtro; medición T-239 |
| REQ-103 | Regla del Portal que compara y propone «cumple» o «no cumple» con la cita del Portal (T-233, ADR-0053); el Portal llega al modelo (T-235) | Tests `decision_literal` reescritos (T-233); medición T-239 (100 %, 0) |
| REQ-104 | Cita de la oferta ampliada a la oración, contexto en el contraste (T-235); `razonamiento` primero y sin «fragmento mínimo» (T-237, ADR-0055) | Tests de T-235 y T-237; medición T-239 (12 de 81, 0 contradicciones, 100 % literal) |
| REQ-105 | Preguntas armadas por el código y validación de la pregunta del modelo (T-235); instrucción de la pregunta (T-237) | Tests de T-235; lectura una por una en T-239 |
| REQ-106 | Informe de revisión en el repositorio, reescritura de matriz (T-236, T-252) y evaluación (T-237), resto de las instrucciones (T-248), versión y huella registradas en cada pedido | Test de cobertura del informe y de versiones congeladas (T-236); medición T-249 de lo que cambió T-248 |
| REQ-107 | Código listo para otro modelo (T-251); servicio y control de los candidatos (T-242, T-243, T-245); comparación de a uno (T-244, T-246); ADR de adopción o descarte (T-247) | Informes de T-243 a T-246; umbral del ADR-0056 |

## Verificación contra la constitución

| Principio | Cumple | Nota |
|---|---|---|
| P1 Spec fuente de verdad | sí | Cada decisión literal de la spec tiene su tarea y su test; ADR-0053 pide confirmar la lectura de P3 antes de integrar T-233 |
| P2 Trazabilidad | sí | Cada tarea nombra sus `REQ-NNN`; commits `T-NNN (REQ-NNN): …` |
| P3 El sistema recomienda, la Comisión decide | sí, con una lectura a confirmar | La cita del Portal como fundamento del «cumple» interpreta el Portal como la oferta presentada por el oferente (ADR-0029). Si el responsable prefiere la lectura estricta, hace falta enmienda por ADR |
| P4 Datos | sí | Solo material público; el camino de pliegos y ofertas no sale de la red interna; las corridas y los informes con texto de casos quedan fuera del repositorio, al repositorio van cifras |
| P5 Local y reproducible | sí | Cada candidato se levanta con un archivo de compose y sus huellas en `scripts/models.sha256`; el runbook documenta la descarga; la migración es solo de valores |
| P6 Auditoría | sí | Ver «Registro de auditoría»: mejora lo que hoy falta (huella de la instrucción, alias real del motor de lotes) |
| P7 Evals además de tests | sí | Ningún cambio de instrucciones o de modelo se acepta sin la medición de T-239 o T-244/T-246; los cambios de T-248 se miden en T-249 |
| P8 Normativa versionada | sí | Sin cambios |
| P9 Hojas de compliance | sí | El sistema sigue sin inferirlas; las celdas externas se cuentan aparte |
| P10 Simplicidad | sí | Una migración de valores, sin pantalla nueva; `sentences.py` reúne código que ya existía; el razonamiento va solo donde decide; no se deja el pensamiento nativo decidible por pedido porque ningún requisito lo pide |
| P11 Compuertas humanas | sí | Plan y despliegue los aprueba el responsable; adoptar un modelo es una decisión suya |

## Decisiones

ADR propuestos por este plan: 0053, 0054, 0055 y 0056 (ver arriba). Reservado: 0057 (resultado de la comparación, T-247).

## Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Las condiciones de la forma de garantía que elige el oferente (pagaré o póliza; resuelto: «Requisito de la forma elegida») | La regla de la «opción» descarta de más tres condiciones de esa forma (prueba 5 de la revisión): baja el recall | T-236 y T-252 escriben la regla con la distinción «opción que puede no usar» y «forma que tiene que elegir», mantienen esas condiciones como condición de su opción, y no se mide sin la respuesta, que se copia literal a la spec y al ADR-0054 |
| Los 70 % de filas conservadas no se alcanzan | REQ-101 y REQ-102 quedan sin cumplir | Una sola ronda de ajuste (T-240); lo que falte pasa a la lista de revisión con su impacto. Los cambios son acumulativos (cita, definiciones, motivos, filtro) y el diagnóstico los cuantifica sobre las 95 quitas |
| Las pruebas de la revisión son de un lote y se parecen a LPU25 | Los ejemplos pueden ajustarse a este caso | Se mide con los casos 01 a 06, que no se usaron para escribir los ejemplos |
| La medición de «conserva» en los casos 01 a 06 usa la lista esperada, no una Comisión | La cifra puede subestimar o sobrestimar | Se informa la forma de medirla; el caso-00 se mide además con la revisión como en T-229 |
| El razonamiento en el JSON y los lotes suben el tiempo (entre 40 y 50 % de tokens de salida donde se usa) | El caso-00 pasa los 60 minutos con el 12B | Tope del razonamiento y de tokens de salida; se mide en T-239 y se informa antes de gastar horas en candidatos |
| La cadena de tareas que tocan `settings.py` (T-233, T-250, T-236, T-252, T-237) alarga el camino hasta la primera medición | Más días antes de T-239 | Cada una toca un bloque distinto del archivo: si el Coordinador acepta fusionar a mano ese archivo, T-237 corre en paralelo con T-236 y T-252 |
| La caché de prefijo no se reutiliza con los modelos Qwen de atención híbrida | La evaluación tarda mucho más y el candidato queda fuera | T-243 y T-245 miden el reuso con las banderas de puntos de control; se descarta en la prueba de humo, no en la comparación |
| El 27B denso es más lento que el 12B | No entra en 60 minutos | Compuerta de salida temprana con el caso-00; la cifra de tiempo queda en el ADR de resultado |
| La memoria de los candidatos roza los 22.000 MiB | No entra | Un solo ajuste permitido (caché `q8_0`), igual en la prueba y la comparación y registrado; si no alcanza, se descarta |
| T-231 y T-232 de la 014 también tocan `portal_facts.py`, `evaluate.py`, `questions.py` y la fila de la matriz | Conflicto de archivos y de criterio | T-233, T-234 y T-235 dependen de ellas; el Coordinador puede mover esos puntos a estas tareas |
| La migración de T-250 choca con otra del `tenders` en vuelo (014) | Dos migraciones con el mismo número | T-250 corre sola entre las tareas que tocan el esquema y depende de T-232 (014); la numeración la fija el desarrollador al arrancar |
| El compose monta `./evaluon`: integrar durante una medición cambia el código medido | Medición inválida | No se integra mientras corre una medición; cada informe nombra el commit |
| Cambiar las listas esperadas para no contar las filas excluidas se parece a bajar la vara | Una cifra de recall engañosa | Solo se marcan las entradas que la decisión del 2026-10-10 excluye, con huella y visto bueno del Coordinador, y se informa cuántas son |
| Los archivos Qwen son de un tercero (Unsloth) | Origen menos directo que el de Google | Revisión fijada y huella verificada contra `scripts/models.sha256`; licencia Apache 2.0 |

## Puntos para el responsable

Resueltos el 2026-10-10 (literales en la spec):
1. **Forma de garantía que elige el oferente:** «Requisito de la forma elegida»; sus condiciones entran y se evalúan solo en la oferta que eligió esa forma (ADR-0054). T-239 ya se puede medir.
2. **P3 y el Portal:** «enmendar. considera al portal como oficial, porque es oficial»; constitución 1.3 (ADR-0053).
3. **Una fila por oración:** «Una fila por oración» (ADR-0054).

Defaults del Coordinador (sin objeción del responsable):
4. «La Comisión conserva el 70 %» en los casos 01 a 06 se mide contra la lista esperada; el caso-00, además, con la revisión como en T-229.
5. El 35B-A3B se mide aunque el 27B se adopte.
6. Si el 27B denso no entra en 60 minutos, se descarta según el umbral de la spec.
