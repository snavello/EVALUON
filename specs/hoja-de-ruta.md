# Hoja de ruta de EVALUON

Estado: propuesta · Fecha: 2026-10-02 · Aprobó: —

Las features del proyecto, en el orden en que se construyen. Cada una tiene su carpeta en `specs/` cuando se empieza a trabajar. El tablero (`docs/tablero.md`) lee esta tabla para mostrar el mapa del proyecto.

| N.º | Feature | Qué entrega | Depende de |
|---|---|---|---|
| 001 | Normativa consultable con cita | Las normas de compras cargadas, versionadas y consultables, con cada respuesta respaldada por el artículo que la sostiene | — |
| 002 | Revisión de pliegos | Observaciones a un pliego contra la normativa, antes de publicarlo | 001 |
| 003 | Matriz de requisitos | Los requisitos del pliego ordenados en una matriz que la Comisión valida | 002 |
| 004 | Evaluación de ofertas | Por cada requisito, una propuesta con su cita; la Comisión confirma, corrige o rechaza | 003 |
| 005 | Hojas de compliance | Carga de las validaciones hechas en sistemas no integrados, por oferta | 003 |
| 006 | Salidas de la evaluación | Planilla por oferta, cuadro comparativo y borrador de acta | 004, 005 |

## Alcance del piloto

El piloto de evaluación guiada necesita de la 001 a la 004. La 005 y la 006 lo completan y pueden entrar después de la primera prueba en paralelo con la evaluación habitual.

## Cómo se modifica

Agregar, quitar o reordenar features se hace en esta tabla, con aprobación del responsable. La numeración no se reutiliza.
