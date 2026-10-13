# ADR-0059 · Criterios de mejora real

Estado: propuesto · Fecha: 2026-10-12 · Propone: Desarrollador (T-256), con la medición de la mesa de comité del 2026-10-12 · Decide: responsable del proyecto

## Contexto

La mesa de comité del 2026-10-12 revisó si lo que se mide dice cuánto sirve EVALUON a la Comisión. Encontró defectos en la medida que cambiaban las cifras (D1 a D9). T-256 los corrige y recalcula sin GPU las 8 corridas del caso-00 y las matrices de los casos 01, 02 y 06 (`specs/015-uso-y-eleccion-del-modelo/verificacion/T-256.md`).

Con la medida corregida quedan cuatro hechos:

- La coincidencia con el dictamen y «0 contradicciones» casi no pueden ver un «cumple» falso. La mayoría de los pares de la lista se ganan absteniéndose y ninguno decidible es «no cumple».
- La única verdad por celda que existe hoy son las decisiones de la Comisión de prueba de T-229, en un solo caso. Entre configuraciones vecinas cambian pocas celdas, menos que lo que hace falta para distinguir una mejora del ruido. Las celdas de una misma fila se mueven juntas (una por oferta), así que la muestra efectiva es la cantidad de filas, no la de celdas.
- Con la misma configuración la salida sale idéntica: repetir una corrida no mide el ruido.
- Toda la evaluación sale de un solo caso, el mismo con que se diagnosticó y se ajustó.

Hacen falta criterios escritos antes de la próxima medición (T-260) para decir si un cambio mejora o empata. Sin ellos se adopta por cifras que están dentro del ruido.

## Decisión propuesta

### 0. Relación con los umbrales de la spec 015

- Este ADR **complementa** los umbrales de la spec 015 y de su plan; no los reemplaza ni los cambia:
  - filas conservadas ≥ 70 %, 0 pedazos sin sujeto y lista presente ≥ 95 %;
  - Portal: 100 % «cumple» con su cita y 0 «cumple» con un dato que no coincide;
  - «no determinado» que cuenta ≤ 15 %, 0 contradicciones y 100 % de citas literales;
  - 100 % de preguntas conformes.
- Las dos cosas responden preguntas distintas. Los umbrales dicen si una configuración llega a la meta de la spec. Este ADR dice si un cambio mejora frente a la configuración de referencia.
- Los umbrales se miden con la medida corregida de T-256. Lo que cambia es la forma de contar, no el número de la meta. Por ejemplo, la lista presente ya no suma lo que está a revisión obligatoria.
- El 15 % de «no determinado» se compara con la cifra sobre todas las celdas, como lo escribió el plan. La cifra sobre las celdas decidibles se informa al lado.
- Cambiar un umbral sigue pidiendo enmendar la spec, con la aprobación del responsable (P11).

### 1. Medidas principales

1. **Matriz.**
   - La principal es la de unidades completas: unidades de la lista sin excluidas que quedan completas en una sola fila, en cada caso de prueba. Al lado se informan las unidades partidas, las filas que juntan unidades distintas y las filas conservadas en una revisión a ciegas: filas mezcladas, sin decir qué variante las hizo.
   - Hasta que exista el archivo de unidades (con huella y visto bueno, como el de exclusiones), rigen dos cifras. La lista presente sin lo que está a revisión obligatoria (T-256, D5), con las suprimidas por una circular que están en otra fila como encontradas (D7). Y las filas conservadas.
   - Las dos se informan también sin las filas técnicas que arma una regla (D9).
2. **Evaluación.**
   - La principal es la exactitud por celda contra la Comisión: exactas con fundamento, abstenciones y erradas. Que el fundamento sostenga lo afirmado se lee celda por celda en `muestra-exactas.md`.
   - Al lado va la coincidencia con el dictamen corregida (D1 y D2).
   - El «no determinado» se informa sobre todas las celdas y sobre las decidibles. Lo que el modelo marca «externo» no se descuenta (D3).
   - Las filas que el archivo de exclusión de celdas saca de la medida no se evalúan; cada una lleva su motivo.
3. **Fundamento (P3, constitución 1.4).** Una conclusión tiene fundamento si muestra alguna de estas cosas:
   - el fragmento de la oferta o del pliego, con su cita normativa;
   - el dato del Portal, con su enlace y su fecha (D8);
   - la ausencia verificada en la lectura completa de la oferta, para un requisito negativo o supletorio: nombra los documentos leídos y dice que ninguno lo contradice;
   - la respuesta de la Comisión a una pregunta del sistema, registrada con quién respondió y cuándo.

   La medida cuenta el «cumple» por ausencia verificada como una conclusión con fundamento, no como «sin cita». T-257 registra en el resultado la regla de la ausencia, y la medida la reconoce igual que reconoce la cita del Portal. Un «cumple» por ausencia que no nombra los documentos leídos no tiene fundamento.
4. **P3, bloqueante.** Hay dos criterios, según la falla:
   - **En cero:** un «cumple» sin fundamento (se ve leyendo la celda) o una contradicción, es decir, «cumple» por «no cumple».
   - **Que no suba respecto de la referencia:** un «no se encontró el documento» donde la Comisión dijo «cumple» o «no aplica». Cuenta como conclusión errada y se informa siempre. Bloquea la adopción de un cambio solo si sube respecto de la configuración de referencia: la referencia actual, V1, ya tiene 3.

### 2. Tamaño mínimo del efecto

| Medida | Mejora real si… | Por qué ese tamaño |
|---|---|---|
| Unidades completas (o, mientras no haya archivo de unidades, lista presente sin revisión) | +2 unidades netas en al menos 2 de los 3 casos de prueba, sin perder ninguna unidad del dictamen | Una unidad es una decisión de la Comisión. Con decenas de unidades por caso, una sola puede ser ruido de agrupamiento (D7) |
| Filas conservadas (revisión a ciegas) | +10 puntos en al menos 2 casos | La diferencia entre la medida mecánica y la revisión ya llega a varios puntos (D6) |
| Exactitud por celda | Las celdas discordantes entre el cambio y la referencia dan p < 0,05 con McNemar exacto a favor del cambio, en al menos 2 filas distintas, y sin ninguna errada nueva | Con todas las discordancias a favor hacen falta al menos 6 (p ≈ 0,031). Con alguna en contra hacen falta más: 7 a favor y 1 en contra da p ≈ 0,07 |
| Cualquier cambio de instrucciones | Explicado par por par (REQ-107), y sin empeorar en el conjunto de validación más de 1 unidad por caso | Evita aceptar un ajuste que solo sirve al caso-00 |

- Por debajo de esos tamaños, el resultado es **empate**. En un empate se elige por tiempo y simplicidad, no por la cifra.
- El tamaño mínimo de cada medida es el mayor de dos valores: el de la tabla, o el doble de lo que cambie esa medida con la corrida alterada (punto 4).

### 3. Cantidad de casos

- **Matriz.** Una mejora vale si se ve en al menos 2 de los 3 casos de prueba y no empeora en el conjunto de validación.
- **Evaluación.** Hoy hay un solo caso con verdad por celda, el caso-00, que además es de desarrollo. Una mejora de evaluación medida solo ahí se informa como «en desarrollo», no como general. Para decir que generaliza hace falta un caso público con ofertas y dictamen, revisado como Comisión antes de mirar la salida del sistema. Lo consigue el Coordinador.

### 4. Estabilidad: la corrida alterada es obligatoria

- No se repite una corrida igual: sale idéntica.
- Toda medición que decide una adopción incluye **una corrida alterada** de la configuración candidata, fijada desde ahora y no elegida después de medir:
  - mismo modelo, mismas instrucciones y **misma semilla**;
  - **el orden de las ofertas invertido**;
  - **los lotes desplazados**: el tope de tokens por grupo (`ASSESSMENT_GROUP_TOKENS`) un 5 % menor, lo que corre los bordes de cada lote.
- Se cuentan las filas y las celdas que cambian respecto de la corrida sin alterar. Esa cifra fija el ruido del punto 2.
- Sin la corrida alterada no hay veredicto de mejora: el resultado queda pendiente.

### 5. Conjuntos

| Conjunto | Casos | Uso | Regla |
|---|---|---|---|
| Desarrollo | Caso-00 y caso chico | Diagnosticar y ajustar | Libre, con el umbral escrito antes |
| Validación | 01, 02 y 06 | Comprobar que un ajuste no empeora fuera del caso-00 | Se miran las cifras y los pares; no se calcan ejemplos de sus textos |
| Prueba | 03, 04 y 05, congelados | Una sola corrida por configuración final | Listas y exclusiones congeladas con huella y fecha. No se miran sus faltantes para ajustar. Lo que no llega va a la lista de revisión con el primer producto (ADR-0024) |
| A ciegas | El caso reservado | Al final, con el producto cerrado | Una sola vez |

## Alternativas

- **Seguir con las medidas de la spec 015 tal como estaban.** Se pierde la posibilidad de ver un «cumple» falso o un «no se encontró» errado, y se adopta por diferencias de pocas celdas que están dentro de lo que cambia una variante vecina.
- **Repetir cada corrida para medir el ruido.** No sirve: con la misma configuración la salida es idéntica. La corrida alterada mide lo que sí varía.
- **Usar todos los casos para ajustar.** Más datos para el ajuste, pero ninguna cifra que diga si generaliza.

## Consecuencias

- T-260 mide con estos criterios y lo dice en su registro. Cada cifra trae su tamaño mínimo y su veredicto: mejora, empate o empeora. Al lado van los umbrales de la spec 015, que siguen vigentes.
- La medida reconoce como fundamento la ausencia verificada en cuanto T-257 la registre en el resultado; hasta entonces, ningún resultado la usa.
- Los casos 03, 04 y 05 quedan congelados desde que se aprueba este ADR. Sus listas y exclusiones no se tocan mirando sus resultados.
- El archivo de unidades de la matriz y el caso público con ofertas y dictamen quedan como trabajo pendiente. Mientras no existan, la matriz se mide con la lista presente sin revisión y la evaluación generaliza solo dentro del caso-00.
