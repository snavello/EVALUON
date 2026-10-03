# ADR-0012 · Cuándo se corre la suite completa de tests

Estado: aceptado · Fecha: 2026-10-03 · Decidió: responsable del proyecto

## Contexto

La suite de tests es la prueba de regresión del proyecto. Cada tarea agrega los tests de lo que construye, y correrlos todos confirma que no se rompió nada anterior. Al 2026-10-03 son unos 1550 tests y la corrida completa tarda unos 3 minutos y medio. Crece con cada tarea.

Hoy cada tarea corre la suite completa al menos tres veces: el desarrollador, el testeador evaluador y el cierre antes de integrar. Además, el testeador hace alteraciones del código y vuelve a correr pruebas. Eso suma unos 10 minutos de suite por tarea, que van a crecer con el proyecto. Dos de esas tres corridas completas prueban el mismo código.

## Alternativas

### A. Seguir corriendo la suite completa en cada paso
Es lo más simple, pero el costo crece con cada tarea, y la mayoría de las corridas repiten una que ya se hizo sobre el mismo código.

### B. Una corrida completa por integración, y la de cada área mientras se trabaja
El desarrollador prueba su área mientras trabaja y corre la suite completa una vez, al final. El testeador corre la completa una vez, ya combinada con main. El cierre la repite solo si entró código a main después de esa verificación.
No se pierde regresión, porque todo lo que se integra queda respaldado por una corrida completa sobre el mismo código, y la cantidad de corridas completas baja a la mitad.

### C. Correr solo los tests "afectados" por cobertura (pytest-testmon)
Es más rápido, pero con la base de datos y Django la elección es poco confiable y puede dejar pasar una rotura.

### D. Correr los tests en paralelo (pytest-xdist)
Bajaría la corrida a la mitad o menos, pero necesita una base de prueba por proceso, que es un cambio de infraestructura. Queda como paso siguiente si B no alcanza.

## Decisión

B, como regla de trabajo para todo el proyecto:

1. **Desarrollador.** Mientras trabaja, corre los tests de su área: la carpeta de `tests/` que toca y las que dependen de ella. Antes de entregar, corre la suite completa una vez y la informa.
2. **Testeador evaluador.** Corre la suite completa una vez, sobre la rama combinada con el main del momento (en una copia aparte), e informa el commit de main con el que la corrió. Para las alteraciones del código corre solo los tests que corresponden a la parte alterada.
3. **Cierre antes de integrar.** Se repite la suite completa solo si, desde el main con el que verificó el testeador, entró a main código, tests o configuración: `evaluon/`, `tests/`, `docker-compose.yml`, `pyproject.toml`, `Dockerfile`, `requirements*`, `scripts/`. Si lo único que entró son documentos de gestión, vale la corrida del testeador.
4. **Antes de la auditoría y del despliegue** de cada feature, la suite completa se corre sobre main.

## Consecuencias

- Por tarea queda una corrida completa del desarrollador y una del testeador, más la del cierre solo cuando hace falta. El tiempo deja de multiplicarse por tres.
- Una tarea puede romper algo fuera de su área sin que el desarrollador lo vea hasta su corrida final. La verificación sigue cubriéndolo antes de integrar.
- Las evals no cambian: según P7, cualquier cambio en recuperación, instrucciones o modelo se mide con el conjunto dorado completo.
- Si la corrida completa pasa de unos 10 minutos, se evalúa la alternativa D en una decisión aparte.
- Para revertirla, se vuelve a la suite completa en cada paso.
