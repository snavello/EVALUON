# ADR-0059 · Criterios de mejora real

Estado: propuesto · Fecha: 2026-10-12 · Propone: Desarrollador (T-256), con la medición de la mesa de comité del 2026-10-12 · Decide: responsable del proyecto

## Contexto

La mesa de comité del 2026-10-12 revisó si lo que se mide dice cuánto sirve EVALUON a la Comisión. Encontró defectos en la medida que cambiaban las cifras (D1 a D9). T-256 los corrige y recalcula sin GPU las 8 corridas del caso-00 y las matrices de los casos 01, 02 y 06 (`specs/015-uso-y-eleccion-del-modelo/verificacion/T-256.md`).

Con la medida corregida quedan cuatro hechos:

- La coincidencia con el dictamen y «0 contradicciones» casi no pueden ver un «cumple» falso. De 49 pares, 32 se ganan absteniéndose y ninguno decidible es «no cumple».
- La verdad por celda que existe hoy son las 51 decisiones de la Comisión de prueba de T-229. Las 8 corridas aciertan entre 24 y 28. Entre configuraciones vecinas cambian de 1 a 4 celdas. Las celdas van de a 3 por fila, así que la muestra efectiva es de unas 17 filas.
- Con la misma configuración la salida sale idéntica: repetir una corrida no mide el ruido.
- Toda la evaluación sale de un solo caso, el mismo con que se diagnosticó y se ajustó.

Hacen falta criterios escritos antes de la próxima medición (T-260) para decir si un cambio mejora o empata. Sin ellos se adopta por cifras que están dentro del ruido.

## Decisión propuesta

### 1. Medidas principales

1. **Matriz.**
   - La principal es la de unidades completas: unidades de la lista sin excluidas que quedan completas en una sola fila, en cada caso de prueba. Al lado se informan las unidades partidas, las filas que juntan unidades distintas y las filas conservadas en una revisión a ciegas: filas mezcladas, sin decir qué variante las hizo.
   - Hasta que exista el archivo de unidades (con huella y visto bueno, como el de exclusiones), rigen dos cifras. La lista presente sin lo que está a revisión obligatoria (T-256, D5), con las suprimidas por una circular que están en otra fila como encontradas (D7). Y las filas conservadas.
   - Las dos se informan también sin las filas técnicas que arma una regla (D9).
2. **Evaluación.**
   - La principal es la exactitud por celda contra la Comisión: exactas con fundamento, abstenciones y erradas. Que la cita sostenga lo afirmado se lee celda por celda en `muestra-exactas.md`.
   - Al lado va la coincidencia con el dictamen corregida (D1 y D2).
   - El «no determinado» se informa sobre todas las celdas y sobre las decidibles. Lo que el modelo marca «externo» no se descuenta (D3).
   - Las filas agregadas solo para la medida no se evalúan: van en un archivo de exclusión de celdas, con su motivo.
3. **P3, bloqueante, en cero.** Se cuentan tres fallas y ninguna puede aparecer:
   - un «cumple» sin respaldo, que se ve leyendo la celda;
   - un «no se encontró el documento» donde la Comisión dijo «cumple» o «no aplica»;
   - una contradicción.

   El «cumple» citado al Portal tiene respaldo (D8, constitución 1.3).

### 2. Tamaño mínimo del efecto

| Medida | Mejora real si… | Por qué ese tamaño |
|---|---|---|
| Unidades completas (o, mientras no haya archivo de unidades, lista presente sin revisión) | +2 unidades netas en al menos 2 de los 3 casos de prueba, sin perder ninguna unidad del dictamen | Una unidad es una decisión de la Comisión; con unas 25 por caso, 1 sola puede ser ruido de agrupamiento (D7) |
| Filas conservadas (revisión a ciegas) | +10 puntos en al menos 2 casos | La diferencia entre la medida mecánica y la revisión ya es de 6 puntos en el caso-00 (D6) |
| Exactitud por celda | +6 celdas netas en al menos 2 filas distintas, sin ninguna errada nueva | Con 51 celdas, McNemar exacto pide unas 6 discordancias en un solo sentido para p < 0,05; hoy las variantes difieren en 1 a 4 |
| Cualquier cambio de instrucciones | Explicado par por par (REQ-107), y sin empeorar en el conjunto de validación más de 1 unidad por caso | Evita aceptar un ajuste que solo sirve al caso-00 |

- Por debajo de esos tamaños, el resultado es **empate**. En un empate se elige por tiempo y simplicidad, no por la cifra.
- El tamaño mínimo de cada medida es el mayor de dos valores: el de la tabla, o el doble de lo que cambie esa medida con la corrida alterada (punto 4).

### 3. Cantidad de casos

- **Matriz.** Una mejora vale si se ve en al menos 2 de los 3 casos de prueba y no empeora en el conjunto de validación.
- **Evaluación.** Hoy hay un solo caso con verdad por celda, el caso-00, que además es de desarrollo. Una mejora de evaluación medida solo ahí se informa como «en desarrollo», no como general. Para decir que generaliza hace falta un caso público con ofertas y dictamen, revisado como Comisión antes de mirar la salida del sistema. Lo consigue el Coordinador.

### 4. Estabilidad

- No se repite una corrida igual: sale idéntica.
- Se hace **una corrida alterada** de la configuración adoptada, sin cambiar el modelo ni las instrucciones. Por ejemplo: el orden de las ofertas invertido, la semilla 43 en lugar de 42 y `group_tokens` movido un 5 % para correr los bordes de los lotes.
- Se cuentan las filas y las celdas que cambian. Se hace una sola vez, antes de cerrar la medición.

### 5. Conjuntos

| Conjunto | Casos | Uso | Regla |
|---|---|---|---|
| Desarrollo | Caso-00 y caso chico | Diagnosticar y ajustar | Libre, con el umbral escrito antes |
| Validación | 01, 02 y 06 | Comprobar que un ajuste no empeora fuera del caso-00 | Se miran las cifras y los pares; no se calcan ejemplos de sus textos |
| Prueba | 03, 04 y 05, congelados | Una sola corrida por configuración final | Listas y exclusiones congeladas con huella y fecha. No se miran sus faltantes para ajustar. Lo que no llega va a la lista de revisión con el primer producto (ADR-0024) |
| A ciegas | El caso reservado | Al final, con el producto cerrado | Una sola vez |

## Alternativas

- **Seguir con las medidas de la spec 015 tal como estaban.** Se pierde la posibilidad de ver un «cumple» falso o un «no se encontró» errado, y se adopta por diferencias de 1 a 4 celdas que están dentro de lo que cambia una variante vecina.
- **Repetir cada corrida para medir el ruido.** No sirve: con la misma configuración la salida es idéntica. La corrida alterada mide lo que sí varía.
- **Usar todos los casos para ajustar.** Más datos para el ajuste, pero ninguna cifra que diga si generaliza.

## Consecuencias

- T-260 mide con estos criterios y lo dice en su registro. Cada cifra trae su tamaño mínimo y su veredicto: mejora, empate o empeora.
- Los casos 03, 04 y 05 quedan congelados desde que se aprueba este ADR. Sus listas y exclusiones no se tocan mirando sus resultados.
- El archivo de unidades de la matriz y el caso público con ofertas y dictamen quedan como trabajo pendiente. Mientras no existan, la matriz se mide con la lista presente sin revisión y la evaluación generaliza solo dentro del caso-00.
