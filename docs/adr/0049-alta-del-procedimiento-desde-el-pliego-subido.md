# ADR-0049 · Alta del procedimiento desde el pliego subido

Estado: aceptado · Fecha: 2026-10-07 · Decidió: responsable del proyecto (2026-10-07 21:20, «ok avanza», junto con la maqueta)

## Contexto

El responsable decidió que el alta de un procedimiento es «desde el portal o subir el pliego en un file» y que no se tipean datos ni renglones (ADR-0047; REQ-077). Desde el Portal esto ya existe (`PortalProposal`, `PortalItem`, `PortalProcedureData`, `PortalLine`). Sin Portal, hoy `register_procedure` pide número, tipo, objeto y fecha tipeados, y los renglones no existen fuera del Portal. Restricciones: un procedimiento no puede existir sin sus cuatro datos obligatorios; un documento del pliego exige procedimiento; el pliego es material de ofertas y pliegos, por lo que se procesa solo con IA local (P4); toda conclusión del sistema lleva su fundamento y la decide una persona (P3).

## Alternativas

### A. Borrador previo, propuesta por reglas y modelo local con cita verificada, renglones en las tablas del Portal
Una tabla `tenders_procedure_draft` guarda el archivo y la propuesta hasta que la Comisión la aprueba. Un pedido `propose_procedure` lee el pliego con la lectura local, busca número, expediente y fecha por reglas, y tipo y objeto por reglas y, si no alcanzan, con el modelo local exigiendo una cita literal que se verifica contra el texto; los renglones salen de la tabla de renglones. Al aprobar se crea el procedimiento con las funciones existentes y se escriben renglones y expediente en `portal_line` y `portal_procedure_data`, que pasan a admitir un documento de origen en lugar de un ítem del Portal. Se gana: un solo lugar de lectura de renglones para todo el sistema, mismo patrón de cita verificada que la matriz, el procedimiento solo existe si la Comisión aprobó. Se pierde: dos tablas del Portal cambian de significado (nombres engañosos), una lectura doble del pliego (una para proponer y otra al cargarlo) y un pedido nuevo en la cola.

### B. Solo reglas, sin modelo
Igual que A pero sin modelo local. Se gana: sin instrucciones nuevas al modelo ni evals de IA; rápido. Se pierde: tipo y objeto dependen del formato de cada pliego; seguramente más datos «no determinados» y más corrección manual.

### C. Crear el procedimiento vacío y completarlo después
Registrar el procedimiento con datos provisorios y subir el pliego normalmente. Se gana: no hay borrador ni lectura doble. Se pierde: viola la regla de que el procedimiento no existe sin sus datos, deja procedimientos «fantasma» si se abandona y obliga a tipear algo, que es lo que el responsable rechazó.

### D. Tablas nuevas de renglones propias de la 014
Se gana: nombres limpios. Se pierde: dos lugares donde buscar renglones (`assessment` y las pantallas leen `portal_line`) y más cambios de código.

## Decisión

A, propuesta, con B como primera ronda de medición: se mide primero con reglas y el modelo local entra solo para los datos que no alcancen, sujeto a los umbrales del plan (caso chico 5 de 5; caso-00 al menos 4 de 5 datos y 90 % de renglones) y a dos rondas máximo. Si las reglas alcanzan, el modelo no se usa. El nombre de las tablas del Portal no se cambia en esta feature.

Corrección y roles (decisión del responsable, 2026-10-07: «Escribe el valor y motivo»): para corregir un dato o un renglón propuesto, el evaluador escribe el valor correcto y un motivo obligatorio; queda guardado el valor propuesto, el corregido, el motivo, quién y cuándo. No existe un alta en blanco: sin propuesta no hay nada que corregir. Subir el pliego lo puede hacer el operador; aprobar o corregir lo propuesto (datos y renglones) solo el evaluador, igual que lo importado del Portal (REQ-048 de la 012).

## Consecuencias

- Más fácil: el alta sin Portal es igual al alta con Portal (propuesta, cita, aprobación); las demás pantallas leen los renglones de siempre.
- Más difícil: dos orígenes por cada renglón (Portal o documento) con una restricción de «exactamente uno»; leer el pliego dos veces la primera vez.
- Revertir: quitar el borrador y el pedido; los renglones desde documento quedan en `portal_line` con su documento de origen y se pueden conservar.
- Si el modelo local entra, sus instrucciones, parámetros y fragmentos se registran (P6) y se miden con el conjunto de pruebas del alta antes de aceptarlo (P7).
