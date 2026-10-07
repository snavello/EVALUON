# Spec 013 · Recorrido del procedimiento (aplicación mínima)

Estado: aprobada · Fecha: 2026-10-07 · Aprobó: responsable del proyecto (2026-10-07; enmienda del mismo día con REQ-070 a REQ-072)

> La spec dice qué se necesita y por qué. No menciona tecnología, librerías ni estructura de código: eso va en el plan.

## Problema

EVALUON ya tiene las funciones de punta a punta (Portal, pliego y matriz, ofertas y ficha, evaluación asistida), pero están en pantallas sueltas: para seguir un procedimiento hay que saber a qué pantalla ir, en qué orden y cuándo terminó un proceso que corre en segundo plano. El responsable y la Comisión no pueden ver, en un solo lugar y mientras ocurre, en qué etapa está un procedimiento, qué hizo el sistema y qué falta decidir.

Sin esa vista no se puede mostrar el producto ni operarlo en el piloto: la evaluación tarda minutos por oferta y hoy no se ve su avance.

## Usuarios y escenarios

**Escenario 1 · Seguir un procedimiento de principio a fin.** Como integrante de la Comisión (o el responsable), cuando abro un procedimiento, necesito ver sus etapas en orden —datos del Portal, pliego y circulares, matriz, ofertas, evaluación, matriz de evaluación— con el estado de cada una (pendiente, en curso, a decidir, lista), para saber dónde estoy y qué sigue.

**Escenario 2 · Ver en vivo lo que hace el sistema.** Como usuario, cuando el sistema está leyendo documentos, proponiendo la matriz o evaluando ofertas, necesito ver el avance sin recargar la página (qué está haciendo, cuánto lleva, cuánto falta aproximadamente) y enterarme cuando termina o falla.

**Escenario 3 · Ir a decidir.** Como evaluador, cuando una etapa tiene algo para decidir (aprobar lo importado, validar la matriz, confirmar propuestas, responder preguntas, dar el ok del informe técnico), necesito ver cuántas decisiones esperan y llegar con un clic a la pantalla donde se toman.

**Escenario 4 · Empezar un procedimiento nuevo.** Como operador, necesito empezar desde una sola entrada: pegar el enlace del Portal (o cargar a mano) y que el recorrido me lleve por las etapas.

## Requisitos funcionales

| ID | Requisito | Origen normativo |
|---|---|---|
| REQ-065 | Una página de entrada lista los procedimientos con su etapa actual y lo pendiente de decidir, y permite empezar uno nuevo desde el enlace del Portal o a mano. | — |
| REQ-066 | Cada procedimiento tiene una página de recorrido con sus etapas en orden y el estado de cada una (pendiente, en curso, a decidir, lista, con error), calculado a partir de lo que ya registra el sistema. | — |
| REQ-067 | Mientras el sistema trabaja en segundo plano, la página muestra el avance en vivo (tarea, paso, porcentaje o cuenta, tiempo transcurrido) sin recargar, y avisa cuando termina o falla, con el motivo. | — |
| REQ-068 | Cada etapa muestra cuántas decisiones esperan a la Comisión y enlaza a la pantalla existente donde se toman; el recorrido no duplica esas pantallas. | P3 |
| REQ-069 | El recorrido respeta los roles: el operador ve todo y prepara; solo el evaluador ve las acciones de decisión. | P3 |

## Criterios de aceptación

- **REQ-065.** Dado el sistema con procedimientos cargados, cuando se abre la entrada, entonces se ve cada procedimiento con su etapa actual y sus pendientes; desde ahí se empieza uno nuevo con un enlace del Portal.
- **REQ-066.** Dado el caso-00 cargado desde cero, cuando se abre su recorrido, entonces cada etapa muestra el estado correcto en cada momento del proceso (comprobado en al menos cinco momentos: antes de importar, importado, matriz propuesta, matriz validada, evaluación terminada).
- **REQ-067.** Dada una evaluación en curso, cuando se mira el recorrido, entonces el avance se actualiza solo al menos cada 10 segundos y, al terminar, la etapa pasa a "a decidir" o "lista" sin recargar.
- **REQ-068.** Dada una etapa con decisiones pendientes, cuando se hace clic en ella, entonces se llega a la pantalla existente donde se toman.
- **REQ-069.** Dado un operador, cuando abre el recorrido, entonces no ve acciones de decisión; un evaluador sí.

## Requisitos no funcionales

- La página de recorrido carga en menos de 2 segundos con el caso-00.
- Funciona en el navegador del equipo, en la red local, sin conexión a internet (P4).

## Fuera de alcance

- Cambiar la lógica de las etapas (Portal, matriz, fichas, evaluación).
- Reemplazar las pantallas existentes; el recorrido las conecta.
- Notificaciones fuera de la aplicación (correo, celular).

## Datos involucrados

Los mismos de las features 003, 004, 008 y 012; la página no agrega datos nuevos. Casos públicos (P4).

## Decisiones del responsable (texto literal)

| Fecha | Tema | Decisión (literal) |
|---|---|---|
| 2026-10-07 | Ver el proceso | "me gustaria ver en una ventana el proceso" |
| 2026-10-07 | Ficha | La ficha de la oferta no es obligatoria para evaluar ("si") |
| 2026-10-07 | Sugerencias | Se cuentan aparte de las decisiones pendientes, "pero que quede claro que estan ambas" |
| 2026-10-07 | Portal | "el portal es opcional pero debiera poder ser explorado como primer fuente y no al reves. Asi funciona hoy la comision. Es decir explora porta , muestra que tiene mas lo que se sube a mano como complemento" |

### Enmienda 2026-10-07

- **REQ-070 · Ventana del proceso.** Mientras el sistema trabaja, una ventana (panel) muestra el proceso paso a paso, en vivo y en lenguaje llano: qué documento lee, qué requisito evalúa, qué decidió una regla, cuánto lleva; con la lista de lo hecho y lo que falta.
- **REQ-071 · El Portal primero.** El alta de un procedimiento empieza explorando el Portal (enlace del proceso); el recorrido muestra lo que trajo el Portal y, aparte, lo que se sube a mano como complemento. La carga a mano sin Portal sigue siendo posible.
- **REQ-072 · Sugerencias y pendientes.** En cada etapa se ven por separado las decisiones pendientes y las sugerencias, las dos visibles.

## Preguntas abiertas

Ninguna. La forma de la demostración del caso-00 (instancia aparte o la real) es una decisión de operación, no de la spec.
