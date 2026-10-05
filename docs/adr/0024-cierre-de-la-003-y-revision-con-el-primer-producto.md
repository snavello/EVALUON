# ADR-0024 · Cierre de la 003 con lo medido y revisión de lo menor con el primer producto

Estado: aceptado · Fecha: 2026-10-05 · Decidió: responsable del proyecto (las cinco decisiones de abajo)

## Contexto

La feature 003 (matriz de cumplimiento) lleva más de 30 tareas de ajuste. Cada ajuste pide una medición real de 30 a 75 minutos de GPU, un diagnóstico, una corrección, una verificación y otra medición. Lo que bloquea hoy la aceptación ya no es lo que la Comisión no puede perderse, sino los requisitos sobrantes: 60 a 70 % de filas firmes sin pareja en los casos 01, 05 y 06, contra un tope del 20 %. Bajarlos es un ajuste largo del filtro (T-106) sin garantía de llegar al tope.

Medido con el código de T-120 ronda 2, T-127, T-128 y T-129 (dos repeticiones con el mismo resultado):

| Caso | Encontrados | REQ-031 | Cita literal | Sobrantes |
|---|---|---|---|---|
| caso-01 | 93 de 93 | 15 de 15 | 100 % | 72 % |
| caso-05 | 68 de 69 | 7 de 8 | 100 % | 70 % |
| caso-06 | 47 de 47 | 3 de 3 | 100 % | 59 % |

Lo que falta en el caso-05 (M-033, línea de formulario; M-059, tabla pendiente) no es de circulares. Una supresión sin frase explícita ya no llega como hecho: queda a revisión obligatoria (P3).

El piloto necesita, además, la 008 (ofertas) y la 004 (evaluación), que no empezaron.

## Alternativas

### a. Cerrar la 003 con lo medido y revisar lo menor con el primer producto (elegida)

- Se gana: llegar antes a ofertas y evaluación; revisar el ruido de la matriz con el uso real de la Comisión y no con listas esperadas.
- Se pierde: la Comisión ve un 60 a 70 % de filas de más y las descarta a mano hasta que se ajuste el filtro.

### b. Ajustar primero el filtro (T-106)

- Se gana: menos filas de más.
- Se pierde: de uno a tres días más, sin garantía de llegar al 20 %.

### c. Seguir como hasta ahora

- Se pierde: semanas en la 003 antes de empezar el centro del piloto.

## Decisión

Se adopta **a**, con estas decisiones del responsable (2026-10-05):

1. La 003 se cierra con los resultados actuales: T-120 se cierra con las repeticiones medidas, sin más rondas de ajuste; después siguen la auditoría y el despliegue.
2. Los requisitos sobrantes se miden y se informan, pero **no bloquean la aceptación** hasta el piloto. Siguen bloqueando: los encontrados (100 %, con "a revisión obligatoria"), la cita literal (100 %) y REQ-031. Esto resuelve T-107.
3. Lo menor pasa a una lista de **revisión con el primer producto** (`specs/003-pliego-matriz/tasks.md`, sección del mismo nombre), que se encara con la 008 y la 004 terminadas: ajuste del filtro y sobrantes (T-106), tablas pendientes que no dan fila, líneas de formulario sin verbo, cambios vigentes de la norma en las consecuencias (T-122), granularidad de la lista esperada y la marca de revisión en una versión nueva sin propuesta propia.
4. La aceptación a ciegas con los casos 02, 03 y 04 (T-108) se mide **una sola vez, sin rondas de ajuste**. Un faltante o un error de circulares que haga perder un requisito se corrige; lo demás va a la lista del punto 3.
5. Se convoca al asesor de metodología para revisar la forma de trabajo de la 008 en adelante (ADR-0013).

## Consecuencias

- La spec de la 003 se enmienda: el tope de sobrantes pasa a informativo hasta el piloto.
- T-107 queda terminada por esta decisión. T-106 y T-122 pasan a la lista de revisión.
- La hoja de ruta registra la revisión con el primer producto entre las decisiones diferidas.
- Antes del piloto se vuelve a decidir el tope, con lo que la Comisión haya visto en uso.
