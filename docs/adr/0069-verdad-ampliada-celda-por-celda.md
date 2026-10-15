# ADR-0069 · Verdad ampliada celda por celda: armada a ciegas del sistema, revisada y firmada por el responsable

Estado: propuesto · Fecha: 2026-10-15 · Propuso: planificador (plan 016) · Decidió: —

## Contexto

La evaluación se mide hoy celda por celda con un solo caso, el caso-00: 48 celdas decididas por una Comisión de prueba (T-229), que además es el caso con el que se ajustó el sistema. Con ese tamaño ninguna mejora se distingue del ruido (T-263 contra V1, p = 0,180; el 12B contra el 27B, p = 0,227; ADR-0059, reglas 3 y 6). La spec 016 (REQ-118) pide verdad celda por celda en al menos tres casos más, con al menos 40 celdas decididas por caso y 150 en total, cada una con quién la validó y cuándo, divididos en lote de ajuste y lote de aceptación; el responsable decidió el 2026-10-15: «La verdad celda por celda la arma un agente que rehace el caso como Comisión y la reviso yo».

Lo que hay: `celdas-comision-*.yaml` (un archivo por caso con `procedimiento`, `huella`, `visto_bueno` y `celdas` con `oferta`, `fila`, `resultado`, `nota`), que carga `load_commission_cells` y mide `cell_accuracy`; resultados admitidos: `cumple`, `no_cumple`, `no_aplica` y `no_se_encontro_documento`. Los casos 00 a 06 y sus listas esperadas viven en `corpus/casos/`, fuera de git (P4, ADR-0060).

## Alternativas

### A. Un archivo por caso, armado por un agente que no ve nada del sistema, con fundamento y revisión por celda (propuesta)

El agente recibe lo que recibiría una Comisión: pliego, circulares, la lista de requisitos del caso, la lectura de las ofertas, los datos del Portal y el dictamen publicado; no ve ninguna evaluación ni propuesta del sistema. Cada celda lleva su resultado, su fundamento y, después, quién la revisó y cuándo. Se gana: no hay anclaje en lo que el sistema dijo; los casos de aceptación cumplen que «el sistema no corrió»; la comprobación por máquina de las citas ataja lo inventado. Se pierde: más trabajo del agente que corregir propuestas, y una revisión larga del responsable.

### B. Como T-229: el agente corrige en la pantalla las propuestas del sistema

Se gana: es más rápido y ya está probado. Se pierde: las decisiones se anclan en lo que el sistema ya propuso (en T-229, 44 correcciones y 7 confirmaciones sobre 51), y para los casos de aceptación obliga a correr el sistema antes de tener la verdad, lo que REQ-118 prohíbe.

### C. La verdad en la base de datos

Se gana: consulta directa. Se pierde: no se versiona con el caso, se pisa al restaurar un respaldo, y la verdad es del corpus (fuera de git), no del esquema.

### D. Pedir al responsable que decida desde cero cada celda

Se gana: independencia total. Se pierde: es el trabajo que se quiere ahorrar y el responsable ya eligió otra cosa.

## Decisión

Se propone **A**.

1. **Casos.** Los elige una tarea de inventario: pliego releído, al menos 2 ofertas legibles, datos del Portal, dictamen publicado y 40 celdas decidibles como mínimo. Al menos 3, de los cuales al menos 2 de aceptación (de 03, 04 y 05) y uno de ajuste (de 01, 02 y 06). Hasta 3 ofertas por caso y entre 40 y 120 celdas decididas por caso, para que el responsable revise entre 150 y 360 celdas.
2. **A ciegas.** El agente no ve ninguna corrida, propuesta ni evaluación del sistema sobre ese caso. Para los casos de aceptación, la base del clon no tiene corridas de evaluación guardadas de sus procedimientos hasta la medición final; se comprueba y se registra.
3. **Clave.** Oferta y requisito de la lista esperada (`M-NNN`); la medida lo traduce a la fila de la matriz que arma `build_case` desde la lista, no desde una propuesta.
4. **Resultados.** `cumple`, `no_cumple`, `no_aplica`, `no_se_encontro_documento` y `no_determinado` (nuevo en `COMMISSION_RESULTS`; un «no determinado» del sistema contra un «no determinado» de la verdad es exacto). Cuentan como «decididas» las cuatro primeras.
5. **Fundamento por celda.** `tipo` (`cita_oferta`, `dato_portal`, `ausencia`, `pregunta` o `documento_faltante`), documento, página, texto y nota; en un «no determinado», la pregunta. Un «cumple» o «no cumple» sin cita literal ubicada en la lectura de la oferta o sin ítem del Portal no se acepta (`quotes.locate`).
6. **Revisión.** El Coordinador arma por caso un documento de revisión (fuera de git, con la tabla de ejemplos reales y una pregunta de sí o no por fila, de lo más dudoso a lo más seguro). El responsable confirma o corrige cada celda; en cada una queda `revision` (`por`, `fecha`, `estado`, y el resultado anterior si la corrigió). El archivo lleva `visto_bueno` y una `huella` de oferta, requisito y resultado. Una celda sin revisión no se cuenta.
7. **Congelado.** Antes de la primera corrida sobre un caso de aceptación se escribe `congelado-016.txt` junto al archivo, con la huella de la verdad y de la lista, el commit y la fecha. `medir_evaluacion --verificar-verdad` lo comprueba, comprueba que no haya corridas de evaluación del procedimiento y cuenta casos, celdas decididas, revisadas y con quién y cuándo.
8. **Dónde vive.** `corpus/casos/caso-0N/esperado/verdad-celdas.yaml`, fuera de git; al repositorio van solo conteos y claves. El caso chico, que es público e inventado, tiene su verdad dentro de `tests/assessment/data/caso-chico/`, para probar el cargador y el conteo.

## Consecuencias

- Más fácil: que una mejora o un empeoramiento se vean con 150 o más celdas de tres o cuatro casos, y que las mejoras de ajuste se comprueben en casos que no se usaron para ajustar.
- Más difícil: la revisión de entre 150 y 360 celdas la hace el responsable; el agente puede repetir sus propios sesgos (se atenúa con la comprobación de citas y la revisión); la verdad de aceptación se pierde como aceptación si alguien corre el sistema sobre esos casos antes de tiempo (el congelado lo hace visible).
- Para revertir: la verdad es aditiva; no usar los archivos deja la medida como estaba. El cargador extendido sigue aceptando `celdas-comision-*.yaml` sin cambios.
