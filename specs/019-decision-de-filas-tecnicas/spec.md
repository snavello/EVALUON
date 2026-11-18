# Spec 019 · Las filas técnicas se deciden solo con el ok del informe técnico

Estado: borrador · Fecha: 2026-11-18 · Aprobó: — · Carril: completo (ADR-0081; decisión del responsable del 2026-11-18, «Sí, carril completo»)

> La spec dice qué se necesita y por qué. No menciona tecnología, librerías ni estructura de código: eso va en el plan.
> Cada duda se marca `[A ACLARAR: pregunta concreta]`. Una spec con marcas pendientes no pasa la compuerta.

## Problema

En la matriz de cumplimiento hay filas técnicas por renglón. Esas filas no las decide la Comisión cruce por cruce: las resuelve el área requirente con su informe técnico, y la Comisión da el ok de que tiene ese informe aprobado (decisión del responsable del 2026-10-06, spec 004).

La pantalla respeta esa regla: en una fila técnica nunca ofrece confirmar, corregir ni rechazar. Pero el sistema, por detrás, sí acepta ese pedido si alguien lo arma a mano, sin pasar por la pantalla. La medición final de la feature 018 lo encontró el 2026-11-18.

Lo que cuesta: un cruce técnico puede quedar como «corregido: cumple» sin informe del área, y ese resultado llega a la comparación de ofertas y al dictamen. Es un dictamen con una conclusión que nadie respaldó. Hoy no pasó (ver «Datos involucrados»), pero nada lo impide.

## Decisiones del responsable (literales)

| Fecha | Tema | Decisión |
|---|---|---|
| 2026-10-06 | Técnico (spec 004) | «La parte tecnica ya te dije que venia del area correspondiente»; «la comision debiera dar el ok de que tiene el informe tecnico aprobado. Para eso lo vamos a asistir por separado» |
| 2026-11-18 | Hacerlo y por qué carril | Ante la pregunta «¿Corrijo aparte que el servidor acepte decidir una fila técnica sin el informe técnico?», con las opciones «Corregirlo aparte, por carril completo (recomendada)» y «Dejarlo así», respondió: «Sí, carril completo». |
| 2026-11-18 | La regla | Ante la pregunta «¿Qué regla hago cumplir en el servidor?», con las opciones «Nunca por esa vía» (se rechaza siempre, con o sin ok del informe) y «Solo mientras falte el ok» (se acepta una vez dado el ok), eligió: «Nunca por esa vía (Recomendada)». |

## Usuarios y escenarios

**Escenario 1 · pedido que no sale de la pantalla.** Como responsable del sistema, cuando alguien con rol de evaluador envía un pedido de confirmar, corregir o rechazar un cruce de una fila técnica sin usar la pantalla, necesito que el sistema lo rechace y lo deje anotado, para que ningún resultado técnico exista sin el informe del área.

**Escenario 2 · el trabajo de siempre.** Como evaluador de la Comisión, cuando decido un cruce de una fila que no es técnica, o doy o retiro el ok del informe técnico de una oferta, necesito que todo funcione igual que hoy.

**Escenario 3 · saber si ya pasó.** Como responsable del sistema, antes de poner la corrección en uso, necesito saber si ya hay decisiones guardadas sobre filas técnicas, para decidir qué hacer con ellas.

## Requisitos funcionales

| ID | Requisito | Origen normativo |
|---|---|---|
| REQ-159 | El sistema debe rechazar todo pedido de confirmar, corregir o rechazar un cruce requisito–oferta de una fila técnica por renglón. Lo rechaza siempre: llegue por donde llegue el pedido, lo haga quien lo haga, y tenga o no la oferta el ok del informe técnico (dado, retirado o nunca dado). | — (principio P3; decisión del 2026-10-06) |
| REQ-160 | Un pedido rechazado por REQ-159 no debe cambiar nada del cruce: ni su resultado, ni su estado, ni su historial de decisiones. Debe quedar registrado quién lo intentó, cuándo, sobre qué cruce, qué acción pidió y por qué se rechazó. La persona recibe un mensaje en lenguaje llano que dice que esa fila se decide con el ok del informe técnico. | — (principio P6) |
| REQ-161 | Lo demás no cambia: la decisión de la Comisión sobre los cruces de filas no técnicas, y dar o retirar el ok del informe técnico, deben funcionar igual que antes de esta feature. La pantalla no cambia. | — |
| REQ-162 | El sistema debe poder listar las decisiones ya guardadas sobre cruces de filas técnicas por renglón (procedimiento, oferta, requisito, acción, quién y cuándo). El listado no modifica ni borra nada. | — (principio P6) |

## Criterios de aceptación

Criterio numérico de la feature (ADR-0025): **12 de 12 pedidos rechazados y 0 decisiones guardadas** sobre filas técnicas, en las combinaciones de 2 vías de entrada × 3 acciones (confirmar, corregir, rechazar) × 2 situaciones (oferta con ok del informe y sin él); y **0 cambios** en el comportamiento de las filas no técnicas.

- **REQ-159.** Dado un procedimiento con una oferta evaluada y una fila técnica por renglón, sin ok del informe técnico, cuando un evaluador pide confirmar, corregir o rechazar ese cruce por cada una de las vías que reciben decisiones, entonces cada pedido se rechaza y no se guarda ninguna decisión.
- **REQ-159.** Dado el mismo caso con el ok del informe técnico dado, y después retirado, cuando se repiten los mismos pedidos, entonces también se rechazan todos.
- **REQ-160.** Dado un pedido rechazado por REQ-159, cuando se consulta el cruce, entonces su resultado, su estado y su historial son los mismos que antes del pedido; y en el registro de hechos hay una entrada con el usuario, la fecha, el cruce, la acción pedida y el motivo del rechazo.
- **REQ-160.** Dado un pedido rechazado por REQ-159, cuando la persona ve la respuesta, entonces lee un mensaje sin términos técnicos que nombra el ok del informe técnico.
- **REQ-161.** Dado un cruce de una fila no técnica con propuesta del sistema, cuando el evaluador lo confirma, lo corrige con motivo o lo rechaza con motivo, entonces la decisión se guarda como hoy. Las pruebas que ya existen sobre decidir, dar el ok y retirar el ok pasan sin cambios.
- **REQ-161.** Dada una fila técnica, cuando el evaluador da el ok del informe técnico, entonces el cruce queda decidido por ese ok, como hoy.
- **REQ-162.** Dado un procedimiento con una decisión guardada sobre una fila técnica (puesta a propósito en la prueba) y otras sobre filas no técnicas, cuando se pide el listado, entonces aparece la primera con sus datos y ninguna de las otras; y después del listado los datos son los mismos que antes.

Corte vertical (ADR-0025): el primer paso se prueba con el caso chico y público que ya usan las pruebas, antes de mirar los procedimientos reales.

## Requisitos no funcionales

- El control de REQ-159 no debe sumar más de 0,1 segundo a guardar una decisión sobre una fila no técnica.
- El listado de REQ-162 sobre los procedimientos cargados hoy (10) debe terminar en menos de 30 segundos.

## Fuera de alcance

- Cambios en la pantalla: ya no ofrece estas acciones.
- Permitir que la Comisión corrija una fila técnica después del ok (opción descartada por el responsable el 2026-11-18).
- Qué hacer con decisiones ya guardadas sobre filas técnicas, si el listado de REQ-162 encuentra alguna: no se borran ni se corrigen solas; se informan al responsable y él decide.
- Los enlaces que dan «acceso denegado» al rol sin Comisión y los demás puntos de la lista de revisión.

## Datos involucrados

- Pruebas: solo el caso chico y público y datos inventados (P4).
- El listado de REQ-162 se corre sobre los procedimientos reales del equipo propio; su resultado es material reservado y no se sube al repositorio. Al repositorio va solo la cuenta (cuántas hay), sin nombres ni contenidos.
- Control previo del Coordinador, 2026-11-18, sobre la copia de la base del piloto de ese día: 52 decisiones guardadas, ninguna sobre un requisito de clase técnica. Es un control aproximado (por clase del requisito, no por fila técnica por renglón); el definitivo es el de REQ-162.

## Preguntas abiertas

No quedan dudas abiertas.
