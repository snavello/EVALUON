# Constitución de EVALUON

Versión 1.6 · 2026-10-14 · Estado: aprobada por el responsable del proyecto. La versión 1.1 ajustó el propósito según el ADR-0006; la 1.2 enmienda P3 según el ADR-0009; la 1.3 enmienda P3 según el ADR-0053 (el dato del Portal de Compras como fundamento); la 1.4 enmienda P3 según el ADR-0058 (la ausencia verificada en la lectura completa de la oferta como fundamento); la 1.5 enmienda P4 según el ADR-0060 (el material reservado del piloto durante su estabilización); la 1.6 enmienda P4 según el ADR-0065 (clasificación por transparencia y modelos externos por clase de dato).

Este documento fija los principios que ninguna spec, plan o tarea puede contradecir. Todos los agentes lo leen antes de actuar. Se modifica solo mediante un ADR aprobado por el responsable.

## Propósito del sistema

EVALUON consolida la normativa de compras (el régimen de contrataciones de la AFIP: Disposición 247/2022 y, para los procedimientos autorizados antes de su entrada en vigencia, Disposición 297/03; sus modificatorias y complementarias; y el marco nacional), revisa pliegos de bases y condiciones contra esa normativa y asiste a la Comisión Evaluadora para determinar si las ofertas cumplen los requisitos del pliego.

## Principios

### P1. La especificación es la fuente de verdad
El código se deriva de la spec. Si el código y la spec difieren, se corrige uno de los dos de forma explícita: nunca se deja la diferencia. Nada se construye sin un requisito que lo pida.

### P2. Trazabilidad de punta a punta
Cada requisito tiene un identificador (`REQ-NNN`) que aparece en la tarea (`T-NNN`), en el test y en el commit. Los requisitos de origen normativo citan norma y artículo. Un requisito sin test, o un commit sin requisito, es un hallazgo de auditoría.

### P3. El sistema recomienda, la Comisión decide
Toda conclusión del sistema muestra su fundamento: el fragmento del pliego o de la oferta y la cita normativa que la sostiene, el dato publicado en el Portal de Compras para ese procedimiento u oferta (fuente oficial), con su enlace y la fecha en que se tomó, la ausencia verificada en la lectura completa de la oferta (para un requisito que se cumple si la oferta no dice algo en contra: se nombran los documentos leídos y que ninguno lo contradice), o la respuesta de la Comisión a una pregunta del sistema, registrada con quién respondió y cuándo, y mostrada como tal. Si no hay fundamento recuperable, el resultado es "no determinado", nunca una afirmación. Una pregunta sin responder no es fundamento. La decisión final es siempre de una persona y queda registrada como tal.

### P4. Clasificación de datos
- **Fase de construcción (actual):** se trabaja únicamente con normas, pliegos, ofertas y evaluaciones públicos. Ese material puede estar en GitHub y pasar por servicios de IA en la nube. No se incorpora material reservado al repositorio, a las pruebas ni a las conversaciones con agentes.
- **Fase de operación (ADR-0065):** lo publicado por el Estado nacional sin autenticación (normativa, pliegos, circulares, ofertas con todos sus documentos, dictámenes y datos del Portal) puede usar una API externa cuando una medición con umbral previo muestra que mejora la calidad, prefiriendo siempre la IA local a calidad igual. La hoja de compliance y toda consulta de cumplimiento tributario, previsional o de sanciones sobre un oferente se procesan solo con IA local y nunca salen del equipo.
- **Excepción (ADR-0060):** durante la estabilización del piloto, los agentes de construcción pueden leer el material del proceso en curso en la instancia del piloto. Nunca va al repositorio ni a las pruebas. La excepción termina cuando el responsable da por terminada la estabilización.
- **Consecuencia de diseño:** el camino local de pliegos y ofertas existe completo desde la primera versión; apagar la API externa no requiere cambios de arquitectura. Pasar de construcción a operación tampoco.

### P5. Local primero y reproducible
El sistema corre en un equipo propio: IA local, embeddings, reranker y Postgres en Docker. Todo el entorno se levanta con un único comando y es portable a otro equipo sin pasos manuales no documentados.

### P6. Registro de auditoría completo
Cada evaluación registra: documentos analizados, versión de la normativa, modelo y parámetros, instrucciones usadas, fragmentos recuperados, resultado, usuario y fecha. Con ese registro se puede reconstruir por qué el sistema dijo lo que dijo.

### P7. Evals además de tests
Los tests verifican que el software hace lo que la spec pide. Las evals miden si la IA responde bien. Ningún cambio en recuperación, instrucciones o modelo se acepta sin correr el conjunto dorado; una baja en las métricas acordadas requiere aprobación explícita del responsable.

### P8. Normativa versionada
Cada norma se guarda con su fuente, fecha de vigencia y versión. Las evaluaciones referencian la versión usada, de modo que un cambio normativo posterior no altera evaluaciones ya hechas.

### P9. Validaciones externas como hojas de compliance
Las verificaciones contra bases y sistemas no integrados se cargan como hojas de compliance de la oferta, por una persona identificada. El sistema no las infiere ni las completa.

### P10. Simplicidad
Se construye lo mínimo que cumple la spec. No se agregan funciones, capas ni abstracciones que ningún requisito pide.

### P11. Compuertas humanas
La spec, el plan y cada despliegue requieren aprobación del responsable. Los agentes preparan y proponen; no se autoaprueban.

## Enmiendas

Un cambio a esta constitución se propone como ADR en `docs/adr/`, con el motivo y el impacto sobre specs existentes. Entra en vigor cuando el responsable lo aprueba y se actualiza la versión de este documento.
