# Spec 014 · Aplicación por secciones

Estado: borrador · Fecha: 2026-10-07 · Aprobó: —

> La spec dice qué se necesita y por qué. No menciona tecnología, librerías ni estructura de código: eso va en el plan.

## Problema

EVALUON tiene las funciones de punta a punta: Portal, pliego y matriz, ofertas y ficha, compliance, informe técnico y evaluación asistida. Pero la interfaz no respeta jerarquías. Según el responsable, «no se entiende, está todo mezclado». Además, en una misma pantalla se mezclan datos, documentos, pendientes y formularios, y no se ve qué existe, qué falta ni de dónde vino cada cosa.

La primera respuesta fue una maqueta de 24 pantallas organizada en ocho etapas en orden fijo (ADR-0046). El responsable la rechazó porque imponía un orden que el trabajo real no tiene, inventaba una carga a mano de renglones que nunca se pidió y escondía el alta de ofertas. Esta spec reemplaza esa organización por la que él definió: cinco secciones sin orden obligatorio, y en cada una se pueden subir archivos o tomarlos del Portal.

Sin esta reorganización no se puede mostrar el producto ni operarlo en el piloto.

## Decisiones del responsable (literales)

| Fecha | Tema | Decisión |
|---|---|---|
| 2026-10-07 | Rechazo de la maqueta de 24 pantallas | «porque tengo que dar de alta a mano los renglones ? jamas se hablo de eso, es alta desde el portal o subir el pliego en un file. esto es un error grave. Donde esta el alta de ofertas ? donde esta el resto?» |
| 2026-10-07 | Organización | «no lo veas solo como recorrido, porque puede no tener un orden organizate asi. 1 Procedimiento de compra {datos iniciales], 2 pliego , con su matriz , 3 ofertas con circulares y aclaraciones y matrices y anexos tecnicos y compliance , 4 evaluacion y dictamen 5 normativas . Cada uno con su posibilidad de subir files o tomarlos del portal. en el uno podriamos tener un explorador y cargador inicial del portal para empezar» |
| 2026-10-07 | Circular modificatoria (3.3) | «Versión nueva de la matriz»: la circular abre una versión nueva de la matriz, con lo que cambió marcado, y la Comisión la valida de nuevo. |
| 2026-10-07 | «Matrices» de la oferta (3.4) | «Lo que presentó cada oferta»: por oferta, qué presentó frente a cada requisito de la matriz, con el fragmento de la oferta (la ficha de la oferta). |
| 2026-10-07 | Anexos técnicos (3.5) | «Solo los de la oferta»: fichas y folletos técnicos que presenta cada oferente. El informe técnico del área va en la sección 4 (evaluación). |
| 2026-10-07 | Borrador del dictamen (4.4) | «Sigue diferido»: la sección 4 muestra el resultado por oferta, el orden de mérito y el dictamen del Portal o subido; el borrador queda para después del piloto. |
| 2026-10-07 | Normas (5.1) | «Solo subir el archivo»: se sube el PDF de la norma; el sistema la lee, muestra el informe de lectura y la Comisión la valida. |
| 2026-10-07 | Resto de la hoja «EVALUON en cinco secciones» (1.1 a 1.4, 2.1 a 2.3, 3.1, 3.2, 3.6, 4.1 a 4.3, 4.5, 5.2, 5.3, T.1 a T.6) | «Todo sí». |
| 2026-10-07 | Diseño | «ademas en las pantallas usa el diseño que acordamos» (guía visual, `docs/diseno/guia-visual.md`). |

Decisiones anteriores que siguen vigentes: el Portal es la primera fuente y lo que no publica se sube como complemento (REQ-071, spec 013); los pendientes y las sugerencias se ven separados y los dos visibles (REQ-072, spec 013); la ficha de la oferta es opcional (plan 013); los cuatro íconos de estado tienen el nombre propio de cada pantalla al pasar el mouse (ADR-0046, punto 7).

## Usuarios y escenarios

Usuarios: el **operador** de la Comisión, que prepara y carga; el **evaluador**, que además decide; y el usuario de **lectura**, que solo consulta. Son los roles que ya existen.

**Escenario 1 · Empezar desde el Portal.** Como operador, cuando llega un procedimiento nuevo, necesito pegar el enlace del Portal, ver todo lo que encontró el sistema y aprobar qué se carga, para que el procedimiento quede armado sin tipear nada.

**Escenario 2 · Empezar sin Portal.** Como operador, cuando el procedimiento no está en el Portal, necesito subir el pliego y que el sistema proponga los datos y los renglones, para aprobarlos igual que lo del Portal.

**Escenario 3 · Trabajar sin orden fijo.** Como evaluador, cuando llega una circular, una oferta o una hoja de compliance en cualquier momento, necesito ir directo a la sección que corresponde y ver qué hay, qué falta y qué tengo que decidir.

**Escenario 4 · Cargar lo que el Portal no publica.** Como operador, necesito subir los documentos de cada oferta, sus anexos técnicos y su hoja de compliance desde la sección de ofertas, con el botón a la vista.

**Escenario 5 · Evaluar y cerrar.** Como evaluador, necesito ver la propuesta de evaluación, decidir los descartes y ver el orden económico y el dictamen en una sola sección.

**Escenario 6 · Normativa.** Como evaluador, necesito cargar una norma subiendo su archivo, revisar el informe de lectura y validarla desde la pantalla, y ver en cada procedimiento qué normas lo rigen.

## Requisitos funcionales

La columna «Hoja» remite a la línea de la hoja «EVALUON en cinco secciones» que aprobó el responsable.

| ID | Hoja | Requisito | Origen normativo |
|---|---|---|---|
| REQ-075 | T.1 | Cada procedimiento se organiza en cinco secciones: 1 · Procedimiento de compra, 2 · Pliego y matriz, 3 · Ofertas, 4 · Evaluación y dictamen, 5 · Normativas. Se entra a cualquiera en cualquier momento; no hay orden obligatorio. Desde cualquier pantalla del procedimiento se ven las cinco, cada una con su estado y sus cuentas de pendientes y sugerencias. | — |
| REQ-076 | 1.1 | La sección 1 tiene un explorador y cargador inicial del Portal: se pega el enlace del proceso, el sistema muestra lo que encontró (datos, renglones, cronograma, garantías, documentos y ofertas) y la Comisión aprueba qué se carga, ítem por ítem o todo junto. Lo aprobado queda en la sección que le corresponde (2, 3 o 4). | — |
| REQ-077 | 1.2, T.3 | Sin Portal, el procedimiento se da de alta subiendo el pliego: el sistema lee el archivo y propone los datos del procedimiento (número, expediente, tipo, objeto, fecha de autorización) y sus renglones, y la Comisión los aprueba o corrige como lo del Portal. No hay formulario para tipear datos ni renglones. | — |
| REQ-078 | 1.3 | La sección 1 muestra número, expediente, tipo, objeto, fecha de autorización con el régimen que fija (Disp. 247/2022 o 297/03), renglones con cantidad, apertura y garantías, y cada dato dice de dónde salió (el Portal o tal archivo). | Disp. 247/2022 y 297/03 (régimen por fecha de autorización) |
| REQ-079 | 1.4 | El sistema revisa periódicamente el proceso en el Portal y avisa lo nuevo (una circular, el acta de apertura, el dictamen). Nada entra sin la aprobación de la Comisión. | — |
| REQ-080 | 2.1 | En la sección 2, el pliego, sus anexos y las especificaciones técnicas se toman del Portal o se suben. | — |
| REQ-081 | 2.2 | En la sección 2, la matriz de cumplimiento es una tabla agrupada por tipo (formales, económicos, técnicos), con filtros (por ejemplo, «solo lo que falta decidir»), filas que se abren con la cita del pliego y las acciones de la Comisión: confirmar, corregir, quitar, agregar y validar. | — |
| REQ-082 | 2.3 | La matriz tiene versiones visibles en una lista y se puede imprimir y exportar. | — |
| REQ-083 | 3.1 | En la sección 3, el alta de ofertas está a la vista: desde el Portal (acta de apertura con oferente, CUIT, total, garantía y precio por renglón) o subiendo los archivos de la oferta. | — |
| REQ-084 | 3.2 | Los documentos de cada oferta se suben, varios a la vez, dentro de la oferta. | — |
| REQ-085 | 3.3 | En la sección 3 se ven las circulares y aclaraciones (modificatorias, aclaratorias, respuestas a consultas), tomadas del Portal o subidas. Una circular modificatoria abre una versión nueva de la matriz de la sección 2, con lo que cambió marcado, que la Comisión valida de nuevo. | — |
| REQ-086 | 3.4 | Cada oferta tiene su ficha: qué presentó frente a cada requisito de la matriz, con el fragmento de la oferta que lo respalda. | — |
| REQ-087 | 3.5 | Los anexos técnicos de cada oferta (fichas y folletos técnicos del oferente) se suben dentro de la oferta. | — |
| REQ-088 | 3.6 | La hoja de compliance de cada oferta se sube en la sección 3, una vez por oferta, y rige para todos sus requisitos externos. | — |
| REQ-089 | 4.1 | En la sección 4, el sistema propone por oferta y por requisito cumple, no cumple o no determinado, con su fundamento, y la Comisión confirma, corrige o rechaza. El informe técnico del área requirente se sube en esta sección, por procedimiento o por oferta. | — |
| REQ-090 | 4.2 | En la sección 4 están las preguntas a la Comisión y los pedidos de subsanación, con su respuesta registrada. | — |
| REQ-091 | 4.3 | En la sección 4 se ven los descartes propuestos y el orden económico, total y por renglón. La Comisión confirma o rechaza cada descarte, y la decisión queda registrada con quién y cuándo. | — |
| REQ-092 | 4.4 | El dictamen se toma del Portal si está publicado, o se sube. El sistema no redacta un borrador del dictamen. | — |
| REQ-093 | 4.5 | En la sección 4 se exportan la planilla por oferta y el cuadro comparativo. | — |
| REQ-094 | 5.1 | En la sección 5, una norma se carga subiendo su archivo; el sistema la lee, muestra el informe de lectura y la Comisión la valida, todo desde la pantalla. | — |
| REQ-095 | 5.2 | En cada procedimiento, la sección 5 muestra qué normas lo rigen según su fecha de autorización y cuáles faltan cargar. | Disp. 247/2022 y 297/03 |
| REQ-096 | 5.3 | La consulta de normativa con citas literales está en la sección 5. | — |
| REQ-097 | T.2 | Cada sección muestra qué hay, qué falta y de dónde vino cada cosa, con «Subir archivo» y, cuando el Portal lo publica, «Tomar del Portal», siempre a la vista. | — |
| REQ-098 | T.4 | Lo pendiente de decidir y las sugerencias del sistema se ven separados y los dos visibles, en cada sección y en la portada del procedimiento. | — |
| REQ-099 | T.5 | Reemplazar o retirar un archivo no borra nada: la versión anterior o el retirado quedan en el historial y se pueden ver. | P6 (constitución) |
| REQ-100 | T.6 | Todas las pantallas usan la guía visual acordada (`docs/diseno/guia-visual.md`), con la misma jerarquía: título, resumen, lo pendiente, el detalle y las acciones al pie. | — |

## Criterios de aceptación

Criterio numérico de la feature: con el caso chico de la 013 y con el caso-00, **26 de 26** requisitos (REQ-075 a REQ-100) se comprueban en pantalla; **0** datos o renglones tipeados en el alta, tanto desde el Portal como desde el pliego subido; cada pantalla carga en menos de 2 segundos.

- **REQ-075.** Dado el caso-00 importado, cuando se abre el procedimiento, entonces se ven las cinco secciones con su estado y sus cuentas, y se puede abrir cualquiera sin pasar por las anteriores.
- **REQ-076.** Dado el enlace del caso-00, cuando el operador lo pega, entonces ve la propuesta agrupada y, al aprobarla, los datos quedan en la sección 1, el pliego en la 2 y las ofertas en la 3.
- **REQ-077.** Dado el pliego del caso chico sin Portal, cuando se sube, entonces el sistema propone número, objeto, fecha de autorización y renglones, y no existe ningún campo para tipear renglones.
- **REQ-078.** Dado el caso-00, cuando se abre la sección 1, entonces cada dato dice su origen y la fecha de autorización muestra el régimen correcto.
- **REQ-079.** Dada una novedad del Portal, cuando el sistema la detecta, entonces aparece como pendiente y no se carga hasta que se aprueba.
- **REQ-080.** Dado un procedimiento sin pliego, cuando se abre la sección 2, entonces se ven «Subir archivo» y «Tomar del Portal».
- **REQ-081.** Dada la matriz del caso-00, cuando se aplica el filtro «solo lo que falta decidir», entonces la tabla muestra solo esas filas, agrupadas por tipo, y cada fila se abre con su cita.
- **REQ-082.** Dada una matriz con dos versiones, cuando se abre la sección 2, entonces la lista muestra las dos con su fecha y quién validó cada una.
- **REQ-083.** Dado el caso-00, cuando se abre la sección 3, entonces el botón de alta de oferta está visible sin abrir nada antes.
- **REQ-084.** Dada una oferta, cuando se suben tres archivos juntos, entonces quedan los tres en la oferta.
- **REQ-085.** Dada una circular modificatoria que cambia un requisito, cuando se aprueba su carga, entonces se abre una versión nueva de la matriz con el requisito marcado como cambiado.
- **REQ-086.** Dada una oferta leída, cuando se abre su ficha, entonces cada requisito muestra lo presentado y el fragmento, o «no se encontró en la oferta».
- **REQ-087.** Dada una oferta, cuando se sube una ficha técnica, entonces figura como anexo técnico de esa oferta.
- **REQ-088.** Dada una oferta sin hoja de compliance, cuando se abre la sección 3, entonces figura como faltante, con su botón para subirla.
- **REQ-089.** Dado el caso-00 evaluado, cuando se abre la sección 4, entonces se ve la propuesta por oferta y requisito, y el informe técnico se sube desde ahí.
- **REQ-090.** Dada una pregunta abierta, cuando se abre la sección 4, entonces figura entre los pendientes con su acceso para responderla.
- **REQ-091.** Dado un descarte propuesto, cuando el evaluador lo confirma, entonces queda registrado con quién y cuándo; un operador no ve el botón.
- **REQ-092.** Dado un dictamen publicado en el Portal, cuando se aprueba su carga, entonces aparece en la sección 4; no existe la acción «generar borrador».
- **REQ-093.** Dado el caso-00 evaluado, cuando se exporta, entonces se obtienen la planilla por oferta y el cuadro comparativo.
- **REQ-094.** Dado el archivo de una norma, cuando se sube desde la pantalla, entonces se ve su informe de lectura y el evaluador la valida sin usar comandos.
- **REQ-095.** Dado el caso-00 (autorizado bajo la Disp. 247/2022), cuando se abre la sección 5, entonces se ven las normas que lo rigen y cuáles faltan cargar.
- **REQ-096.** Dada una consulta, cuando se responde, entonces se ven las citas literales con su parte.
- **REQ-097.** Dado un procedimiento recién creado, cuando se abre cualquier sección, entonces se ve qué falta con su acción directa.
- **REQ-098.** Dado el caso-00 con pendientes y sugerencias, cuando se abre la portada, entonces se ven en dos bloques separados con su cuenta.
- **REQ-099.** Dado un documento reemplazado, cuando se abre su historial, entonces se ven la versión anterior y la nueva; un documento retirado aparece en «retirados».
- **REQ-100.** Dada cada pantalla de la feature, cuando la revisa el Coordinador en el navegador, entonces respeta la guía visual y la jerarquía común.

## Requisitos no funcionales

- Cada pantalla carga en menos de 2 segundos con el caso-00.
- Funciona en pantallas desde 1280 px de ancho y es usable en una notebook de 1366 × 768.
- Corte vertical primero: el esqueleto de las cinco secciones y la sección 2 (pliego y matriz) con el caso chico, antes de las demás.

## Fuera de alcance

- El borrador del dictamen (sigue diferido).
- Tipear datos o renglones del procedimiento.
- Traer normas de una fuente oficial (Boletín Oficial, InfoLEG): solo se sube el archivo.
- Bloqueo por intentos fallidos y acceso desde otras computadoras (feature 007).
- Cambiar la lógica de cada feature: la reorganización cambia dónde se ven las cosas y suma las acciones que faltan (REQ-077, REQ-091, REQ-094, REQ-099).

## Datos involucrados

Material público: el caso chico de la 013 y el caso-00. Ningún caso reservado (P4).

## Cómo se construye

1. La maqueta se rehace con estas cinco secciones y el responsable la aprueba antes de programar cualquier pantalla.
2. Corte vertical: el esqueleto (cinco secciones, portada del procedimiento, jerarquía común) y la sección 2 con la matriz de cumplimiento.
3. Después, sección por sección. Las tareas abiertas de la 013 (T-185, T-186, T-188 y T-191) se absorben en esta feature.

## Preguntas abiertas

Ninguna.
