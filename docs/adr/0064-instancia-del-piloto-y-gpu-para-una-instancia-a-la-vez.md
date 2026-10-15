# ADR-0064 · Instancia del piloto en la misma notebook, con el motor de generación para una instancia a la vez

Estado: rechazado (2026-10-14, versión mínima: una sola instancia) · Fecha: 2026-10-14 · Propuso: planificador (plan 007) · Decidió: responsable del proyecto (2026-10-14, «si» a la versión mínima)

## Por qué se rechazó

El responsable decidió el 2026-10-14: «el sistema aun no ha sido probado y estamos poniendo mil trabas de seguridad. Ahora es una perdida de tiempo.», y dijo «si» a una versión mínima. Mientras dure la estabilización, el piloto usa la instancia de siempre (8000), abierta a la red, sin segunda instancia ni préstamo del motor. La spec 007 quedó enmendada: la separación del proceso reservado (REQ-117) se hace al terminar la estabilización.

## Qué se había propuesto

Queda como antecedente para ese momento:

- una segunda instancia (`evaluon-piloto`) en el mismo equipo, con proyecto, carpeta, base, imagen, puerto, secretos y respaldos propios;
- un script que fija el nombre del proyecto, porque sin `COMPOSE_PROJECT_NAME` el `name: evaluon` del compose haría que las órdenes actuaran sobre 8000;
- el 27B en una sola instancia a la vez, porque no entran dos en la GPU, movido con un script que se niega con pedidos en curso y deja dicho quién tiene el motor;
- un procedimiento para cerrar el acceso de los agentes al terminar la estabilización.

Alternativas que se habían evaluado:

- un solo motor compartido, que rompe la separación;
- otro equipo, que no existe.

Los datos de T-049 (convivencia de dos instancias, memoria de la GPU, tiempos del 27B) están en `specs/001-normativa/entorno.md`.
