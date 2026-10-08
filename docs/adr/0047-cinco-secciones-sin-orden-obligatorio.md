# ADR-0047 · Cinco secciones sin orden obligatorio

Estado: aceptado · Fecha: 2026-10-07 · Decidió: responsable del proyecto (aprobó la spec 014, 20:20)

## Contexto

La maqueta de 24 pantallas del ADR-0046 organizaba el procedimiento en ocho etapas con un orden fijo. Además inventaba un alta a mano con renglones tipeados y dejaba el alta de ofertas escondida. El responsable la rechazó: «es alta desde el portal o subir el pliego en un file. esto es un error grave. Donde esta el alta de ofertas ?».

## Decisión

Literal: «no lo veas solo como recorrido, porque puede no tener un orden organizate asi. 1 Procedimiento de compra {datos iniciales], 2 pliego , con su matriz , 3 ofertas con circulares y aclaraciones y matrices y anexos tecnicos y compliance , 4 evaluacion y dictamen 5 normativas . Cada uno con su posibilidad de subir files o tomarlos del portal. en el uno podriamos tener un explorador y cargador inicial del portal para empezar».

1. Cada procedimiento se organiza en cinco secciones, a las que se entra en cualquier orden.
2. En cada sección se pueden subir archivos o tomarlos del Portal. Nada que venga del Portal o de un archivo se tipea.
3. La sección 1 empieza con el explorador y cargador inicial del Portal. Sin Portal, el alta se hace subiendo el pliego.
4. Las circulares y aclaraciones van en la sección 3. Una circular modificatoria abre una versión nueva de la matriz de la sección 2.
5. El informe técnico del área va en la sección 4. Los anexos técnicos de la oferta van en la 3.

Del ADR-0046 siguen vigentes: la jerarquía común de cada pantalla, la matriz en tabla agrupada con filtros, los pendientes y las sugerencias separados, la ventana del proceso, la guía visual y los íconos de estado.

## Consecuencias

- Se abre la feature 014 (`specs/014-aplicacion-por-secciones/spec.md`), que absorbe las tareas abiertas de la 013.
- La maqueta se rehace con las cinco secciones y se aprueba antes de programar.
- Se agrega una función nueva: el alta de un procedimiento a partir del pliego subido, con los datos y los renglones propuestos por el sistema.
