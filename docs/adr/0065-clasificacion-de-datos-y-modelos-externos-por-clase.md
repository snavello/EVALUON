# ADR-0065 · Clasificación de datos por transparencia y uso de modelos externos por clase de dato (enmienda de P4)

Estado: propuesto · Fecha: 2026-10-14 · Propuso: Coordinador, a partir de la consulta del responsable del 2026-10-14 · Decidió: — (se formaliza cuando el responsable integra este pull request)

## Contexto

P4 de la constitución (versión 1.5) dice que en la fase de operación «los pliegos y las ofertas se procesan solo con IA local» y que la normativa, por ser pública, puede usar una API externa. Esa regla supuso que las ofertas eran material reservado. El ADR-0060 lo repitió al decir que las ofertas del proceso en curso «son reservadas hasta el dictamen».

El 2026-10-14 el responsable aclaró, con estas palabras:

> «La conformidad del area legal o seguridad no se requiere sobre documentos como el pliego, las ofertas, las circulares y las evaluaciones terminadas porque es informacion publica mostrada sin authenticacion por normativa de trasnparencia del estado nacional. Eso incluye cualquier tipo de informacion polizas, firmas, pagares etc. Lo que si tiene una sensibiliodad mayor son algunas partes de lo que llamammos hoja de compliance donde por ejemplo se mira cumplimiento tributario.»

Y fijó la preferencia: «Siempre prefiriendo el uso local cuanto sea posible sin resignar calidad.»

Lo que motiva la decisión es la calidad. Con el modelo local adoptado (Qwen3.8-27B, ADR-0057) la matriz llegó a entre 93 % y 97 % de filas firmes con pareja en los casos de validación y a entre 77 % y 89 % en los de prueba (T-266), pero la evaluación quedó estancada: «no determinado» en el 25,4 % de las celdas del caso-00, el dato del Portal usado en 7 de 14 celdas y 14 de 17 preguntas conformes (T-263), por debajo de la spec 015. Entre el 12B y el 27B la evaluación no se distingue con un solo caso (T-268). Las instrucciones acumularon reglas por ronda (evaluación en versión 12, extracción de matriz en versión 12, filtro en versión 9) y la spec 015 exige las mismas instrucciones para todos los modelos.

Un modelo grande por API externa (contexto de un millón de tokens, mejor lectura de escaneos y mejor razonamiento sobre condiciones múltiples) podría resolver parte de eso. P4, tal como está, lo prohíbe para pliegos y ofertas aunque sean públicos.

## Alternativas

### A. Mantener P4: todo lo de pliegos y ofertas solo con IA local
Se gana: ninguna dependencia externa en el camino de los documentos; nada cambia. Se pierde: la mejora de calidad queda limitada a lo que da un modelo de 27B en 32.768 tokens, y la medición actual no puede demostrar mejoras chicas (ADR-0059, regla 4: en empate queda lo que está).

### B. Clasificar por transparencia y permitir API externa para lo público, con el local como primera opción (elegida)
Lo publicado por el Estado nacional sin autenticación (pliego final, circulares, ofertas con todos sus documentos, dictámenes y evaluaciones terminadas, datos del Portal) puede procesarse con una API externa cuando mejora la calidad medida. Lo reservado (la hoja de compliance y toda consulta de cumplimiento tributario, previsional o de sanciones sobre un oferente) se procesa solo con IA local y nunca sale del equipo. Se gana: acceso a modelos mejores donde se demuestre que ayudan, sin exponer lo sensible. Se pierde: dependencia de internet y de un proveedor en esas etapas; otro origen que registrar en la auditoría (P6).

### C. Seudonimizar todo y mandar cualquier cosa a la API externa
Se gana: cubriría también la hoja de compliance. Se pierde: los importes, fechas y datos técnicos no se pueden enmascarar sin destruir la evaluación; un texto seudonimizado sigue siendo identificable por contenido; las imágenes no se seudonimizan. No hace falta para lo público y no alcanza para lo reservado. Se descarta.

## Decisión

1. **Clasificación de datos.** Son **públicos**: el pliego final y sus anexos, las circulares, los documentos de las ofertas (incluidas pólizas, pagarés, firmas y declaraciones), los datos del Portal de Compras, los dictámenes y las evaluaciones terminadas. Son **reservados**: la hoja de compliance (documento de tipo `compliance` en el sistema) y cualquier resultado de consultas de cumplimiento tributario, previsional, de sanciones o de deuda sobre un oferente, vengan en una hoja de compliance, en un informe de consultas o en una respuesta de la Comisión que los transcriba.
2. **Regla de uso de modelos externos.** Lo público puede procesarse con una API externa solo cuando una medición con umbral escrito antes (ADR-0024, ADR-0025, ADR-0059) muestra que mejora la calidad respecto del modelo local. **Lo reservado se procesa solo con IA local y nunca sale del equipo.** El sistema no manda a una API externa ningún documento de tipo `compliance` ni ningún fragmento que provenga de uno, y la evaluación de los requisitos que dependen de esas consultas (P9) corre siempre en el modelo local.
3. **Local primero.** Entre una variante local y una externa de calidad equivalente se elige la local (modifica, para este caso, el desempate del ADR-0059: en empate queda lo local, esté o no en uso). La externa se adopta solo donde la mejora se nota y por etapa (matriz, lectura, contraste, preguntas), no en bloque.
4. **Registro (P6).** Cada pedido a una API externa queda en el registro de auditoría con proveedor, modelo, versión de la instrucción, fragmentos enviados y respuesta, igual que un pedido local. El registro de evaluación dice qué etapas corrieron fuera del equipo.
5. **Constitución 1.6.** P4 pasa a decir, en la fase de operación: «Lo publicado por el Estado nacional sin autenticación (pliegos, circulares, ofertas, dictámenes y datos del Portal) puede usar una API externa cuando una medición muestra que mejora la calidad, prefiriendo siempre la IA local a calidad igual. La hoja de compliance y toda consulta de cumplimiento tributario, previsional o de sanciones sobre un oferente se procesan solo con IA local y nunca salen del equipo.» La consecuencia de diseño se mantiene: el camino local de pliegos y ofertas sigue existiendo completo, y apagar la API externa no debe requerir cambios de arquitectura.
6. **Qué no cambia.** El repositorio es público y los casos de compra no se suben a él (ADR-0060, punto 2). Las mediciones y verificaciones llevan solo cifras y claves. La spec 015 queda enmendada en «Fuera de alcance»: la exigencia de instrucciones idénticas para todos los modelos deja de regir cuando se compara un modelo local con uno externo; cada uno lleva la instrucción más corta que cumple la spec, registrada con su versión.

## Consecuencias

- Más fácil: comparar un modelo externo por etapa con el mismo protocolo del ADR-0042 (todo igual salvo el modelo y su instrucción); simplificar las instrucciones del modelo local sin la obligación de que sirvan también al externo.
- Más difícil: la aplicación necesita salida a internet en las etapas que usen la API externa y una clave guardada fuera del repositorio; el entorno de pruebas tiene que poder correr sin esa salida (dobles de la API, como los clientes de IA de T-011).
- Pendiente de confirmar con el responsable: el ADR-0060 trató las ofertas del proceso en curso como reservadas «hasta el dictamen». Si antes de la apertura o del dictamen hay un período en que los documentos de las ofertas no están publicados, en ese período se las trata como reservadas y corren solo en el modelo local. Hasta que lo confirme, el sistema aplica la regla externa solo a procedimientos cuyas ofertas ya están publicadas en el Portal.
- Para revertir: volver P4 a la versión 1.5 y apagar la API externa por configuración; el camino local sigue completo.
