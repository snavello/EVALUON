# ADR-0027 · Cómo se encuentran los fragmentos de una oferta: recuperación en pasajes y elección del modelo entre candidatos

Estado: aceptado · Fecha: 2026-10-05 · Decidió: responsable del proyecto (al aprobar el plan 008). La recuperación recorre siempre todos los documentos de la oferta, sin filtrar por tipo.

## Contexto

REQ-039 pide, para cada requisito de la matriz validada, los fragmentos de la oferta que lo responden, con documento, página y texto literal, y encontrar al menos el 90 % de los esperados. REQ-040 pide decir "no se encontró" cuando no hay. REQ-041, una síntesis sin juicio de cumplimiento. P3: nada sin fundamento recuperable; P4: solo IA local.

Datos: una oferta tiene de 5 a 15 documentos, de pocas a decenas de páginas, algunos escaneados. El modelo de generación tiene un contexto de 16.384 tokens (`generation_batch`), lo que no alcanza para una oferta entera. La 001 y la 003 ya tienen embeddings (bge-m3), reranker (bge-reranker-v2-m3), búsqueda por palabras en Postgres con normalización de tildes (ADR-0007) y verificación de cita literal.

## Alternativas

### A. El modelo lee la oferta por tramos y extrae citas, como en la matriz

- Se gana: un solo mecanismo ya conocido (ADR-0019).
- Se pierde: la oferta tiene 20 a 60 veces más texto relevante que un pliego por requisito buscado; habría que recorrerla entera por cada requisito o pedir todos los requisitos en cada tramo. Decenas de pedidos largos por oferta y muchos "no encontrado" falsos si un tramo cae fuera de la ventana.

### B. Solo recuperación: el mejor fragmento por embeddings y reranker, sin modelo de generación

- Se gana: rápido, determinista, el texto es el pasaje y nada lo inventa.
- Se pierde: no hay síntesis (REQ-041); el reranker no distingue "no se encontró" de "lo más parecido"; en renglones (REQ-044) no puede decir si un renglón se cotizó.

### C. Recuperación en pasajes y el modelo elige entre los candidatos (elegida)

1. Al leer, cada página se parte en **pasajes** (bloques de texto de hasta 1.200 caracteres, sin cruzar la página), cada uno con su vector y su texto normalizado para palabras.
2. Por cada entrada de la ficha: candidatos por embeddings (los 20 más cercanos de la oferta) y por palabras (20), unidos; el reranker los ordena y pasan los 8 mejores.
3. Un pedido al modelo por entrada: recibe el requisito (su cita literal del pliego) y los candidatos con alias `P1…P8`; devuelve en JSON las aliases que responden al requisito (ninguna es una respuesta válida), una síntesis de una o dos oraciones de lo que la oferta ofrece, y para un renglón si lo cotizó.
4. **El sistema construye el fragmento**: el texto es el del pasaje elegido, copiado de la base. El modelo no escribe texto citado. Una alias inexistente invalida la elección.
5. Si no elige ninguna, la entrada queda "no se encontró en la oferta". Si hay páginas sin leer en la oferta, la entrada lo avisa, sin suponer.
6. La síntesis se controla con una lista de palabras de juicio ("cumple", "no cumple", "incumple", "satisface", "adecuado", "conforme"…). Si falla, se reintenta una vez con el aviso; si vuelve a fallar, la entrada queda sin síntesis y con la anomalía registrada.

- Se gana: cada fragmento es literal por construcción; el contexto del modelo es siempre chico (unos 3.000 tokens); la búsqueda no depende de que el modelo vea toda la oferta; sirve igual para los renglones.
- Se pierde: un requisito cuya respuesta no está entre los 8 candidatos no se encuentra (el techo del recall lo pone la recuperación); un pasaje de 1.200 caracteres puede traer más de lo pedido; un pedido al modelo por entrada (unas 35 a 45 por oferta, de 3 a 6 segundos cada uno, estimación a medir).

### D. Modelo de visión local que lea cada página como imagen

- Se gana: salta el OCR.
- Se pierde: no hay en el repositorio un modelo de visión verificado; ocupa GPU que hoy está casi llena (ver plan 003, "Tiempos y GPU"); el texto que produce no es copia literal de nada recuperable, contra P3 y REQ-039. Se descarta; no se probó (no hay datos del equipo que lo sostengan).

## Decisión

Se adopta C. El criterio de aceptación es el de la spec: 90 % de fragmentos esperados encontrados, donde "encontrado" es señalar el mismo documento, página y pasaje, y 100 % de texto literal. Si la medición muestra que el techo de recall de los 8 candidatos es el problema, el ajuste es subir a 12 candidatos o sumar la búsqueda por renglón antes de pensar en A.

## Consecuencias

- Más fácil: la medición de fragmentos es una comparación de lugares, sin redacciones; el registro de auditoría guarda candidatos, orden y elección de cada pedido.
- Más difícil: se agrega una tabla de pasajes con un vector por fila y una columna de palabras; reindexar si cambia el modelo de embeddings.
- Revertir: cambiar el paso 3 por A no cambia el esquema (los fragmentos siguen apuntando a un pasaje o a un rango del texto canónico).
