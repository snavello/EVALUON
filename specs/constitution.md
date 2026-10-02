# Constitución de EVALUON

Versión 1.1 · 2026-10-02 · Estado: aprobada por el responsable del proyecto. La versión 1.1 ajusta el propósito según el ADR-0006.

Este documento fija los principios que ninguna spec, plan o tarea puede contradecir. Todos los agentes lo leen antes de actuar. Se modifica solo mediante un ADR aprobado por el responsable.

## Propósito del sistema

EVALUON consolida la normativa de compras (el régimen de contrataciones de la AFIP: Disposición 247/2022 y, para los procedimientos autorizados antes de su entrada en vigencia, Disposición 297/03; sus modificatorias y complementarias; y el marco nacional), revisa pliegos de bases y condiciones contra esa normativa y asiste a la Comisión Evaluadora para determinar si las ofertas cumplen los requisitos del pliego.

## Principios

### P1. La especificación es la fuente de verdad
El código se deriva de la spec. Si el código y la spec difieren, se corrige uno de los dos de forma explícita: nunca se deja la diferencia. Nada se construye sin un requisito que lo pida.

### P2. Trazabilidad de punta a punta
Cada requisito tiene un identificador (`REQ-NNN`) que aparece en la tarea (`T-NNN`), en el test y en el commit. Los requisitos de origen normativo citan norma y artículo. Un requisito sin test, o un commit sin requisito, es un hallazgo de auditoría.

### P3. El sistema recomienda, la Comisión decide
Toda conclusión del sistema muestra su fundamento: el fragmento del pliego o de la oferta y la cita normativa que la sostiene. Si no hay fundamento recuperable, el resultado es "no determinado", nunca una afirmación. La decisión final es siempre de una persona y queda registrada como tal.

### P4. Clasificación de datos
- **Fase de construcción (actual):** se trabaja únicamente con normas, pliegos, ofertas y evaluaciones públicos. Ese material puede estar en GitHub y pasar por servicios de IA en la nube. No se incorpora material reservado al repositorio, a las pruebas ni a las conversaciones con agentes.
- **Fase de operación:** los pliegos y las ofertas se procesan solo con IA local. La normativa, por ser pública, puede usar una API externa.
- **Consecuencia de diseño:** el camino que recorren pliegos y ofertas no depende de ningún servicio externo, desde la primera versión. Pasar de construcción a operación no debe requerir cambios de arquitectura.

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
