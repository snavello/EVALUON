# ADR-0037 · Lectura completa por requisito: grupos de documentos completos y contexto de 32.768 tokens en el motor de lotes

Estado: propuesto · Fecha: 2026-10-06 · Decidió: —

## Contexto

La spec 004 pide (REQ-054, ADR-0035) que el modelo lea completos los documentos de la oferta que pueden responder cada requisito, y no solo los pasajes de una búsqueda: con ofertas reales la búsqueda de pasajes dejó fuera el pasaje correcto en 16 a 19 de los 30 fragmentos que faltaban (T-146).

Restricciones:

- El motor de lotes (`generation_batch`) arranca hoy con un contexto de 16.384 tokens, igual al de `generation` (ADR-0002, `docker-compose.yml`). Con la lectura completa, una oferta chica entra; una grande, no.
- Las ofertas del caso-00 tienen 9, 16 y 45 páginas, repartidas en 10 a 16 archivos (pólizas, declaraciones, hojas técnicas, escaneos). Estimación, a confirmar con la medición de T-148: de 350 a 900 tokens por página según sea formulario, escaneo o texto legal denso, es decir de 4.000 a 8.000 tokens la más chica, de 6.000 a 14.000 la mediana y de 18.000 a 40.000 la de 45 páginas (menos si se descartan copias de texto idéntico).
- Reparto de memoria de video (ADR-0002): hasta unos 16 GB para generación, y ya hay dos instancias del modelo. Con Gemma 4 12B en 4 bits, la medición citada en ADR-0002 [25] da 8,6 GB (8.758 MiB) con contexto de 32.000 tokens, sobre una RTX 5090 de escritorio; en esta notebook no está medido.
- El servidor reutiliza la parte común del inicio de pedidos seguidos: `cache_prompt` vale `true` por omisión y `--cache-ram` limita la memoria de ese caché (README de `llama-server`, https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md, consultado el 2026-10-06; el compose ya fija `--cache-ram` en 2048 MiB).
- Todo corre en el equipo (P4); la calidad manda sobre el tiempo (decisión del responsable para la matriz, extendida aquí).

## Alternativas

### A. Pasajes ampliados con el contexto actual (16.384)

Más candidatos por requisito, páginas vecinas, reranker más generoso. Se gana: sin cambios de entorno. Se pierde: es lo que el ADR-0035 descartó; el pasaje correcto llega con puntaje casi nulo y subir candidatos agrega falsos hallazgos.

### B. Toda la oferta en un solo pedido, con contexto de 65.536 tokens o más

Se gana: nada se selecciona, nada se agrupa. Se pierde: más memoria de video (el caché de contexto crece con el largo) con dos instancias del modelo ya cargadas; cada pedido lee decenas de miles de tokens aunque el requisito se responda en una página; un modelo de 12.000 millones de parámetros pierde precisión de recuperación en contexto muy largo (riesgo que hay que medir, no un dato); y no garantiza que la oferta de 45 páginas entre.

### C. Grupos de documentos completos con contexto de 32.768 tokens (elegida)

Los documentos de la oferta se empaquetan enteros, ordenados por relevancia para el requisito, en grupos de hasta 20.000 tokens de texto de oferta; un documento mayor que eso se parte por páginas en ventanas. Se pregunta por cada grupo y se unen las respuestas (ver el plan, "Flujo de IA"). Se gana: cada pedido lee texto completo y acotado; una oferta chica es un solo grupo; ninguna parte de la oferta queda sin leer por la selección; el orden de los pedidos (documentos primero, requisito al final) deja trabajar al caché de prefijo. Se pierde: una oferta grande se lee en dos o tres pedidos por requisito; hay que unir respuestas de grupos (regla en ADR-0038); sube el contexto del motor de lotes (memoria de video).

### D. Selección previa por el modelo (leer un índice de documentos y elegir cuáles abrir)

Se gana: menos tokens por requisito. Se pierde: una decisión más del modelo que puede dejar fuera justo el documento que responde, sin que nadie lo vea; contradice "no omitir" y cuesta otro pedido por requisito.

## Decisión

Se propone C:

1. `generation_batch` pasa a contexto de **32.768 tokens**, con una variable propia (`GENERATION_BATCH_CTX_SIZE`); `generation` (consultas de normativa) queda en 16.384.
2. El presupuesto de texto de oferta por pedido es de **20.000 tokens** (`ASSESSMENT_GROUP_TOKENS`), de modo que instrucciones, requisito, fundamentos, salida y margen de plantilla (unos 6.000) quepan con holgura.
3. La primera tarea (T-148) mide el tamaño real de las ofertas con el tokenizador del modelo y la memoria de video con los tres modelos cargados. Si el contexto de 32.768 no entra en el reparto, se baja a 24.576 con presupuesto de 14.000 tokens, o se apaga `generation` mientras corre una evaluación; se registra en este ADR.

Lo que no se decide: que la oferta entera entre en un pedido; esa es la alternativa B, que se reabre si la medición muestra que los grupos pierden respuestas.

## Consecuencias

- Más fácil: la lectura completa es por construcción; el requisito de la spec se cumple sin depender de una búsqueda.
- Más difícil: cambia `docker-compose.yml` (contexto del lote), el test que exige que los dos motores tengan el mismo comando (`tests/tenders/test_generation_batch.py`) y el registro del contexto en las propuestas de la 003 y las fichas de la 008, que hoy toma el valor del motor interactivo; T-148 lo corrige. Más memoria de video: a medir.
- Para revertir: volver `GENERATION_BATCH_CTX_SIZE` a 16.384 y bajar `ASSESSMENT_GROUP_TOKENS` a 8.000; las ofertas grandes pasarían a más grupos o a ventanas por página.
- Cambiar el presupuesto, el contexto o el orden de los pedidos exige volver a medir (P7).
