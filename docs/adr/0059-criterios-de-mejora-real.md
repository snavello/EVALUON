# ADR-0059 · Criterios de mejora real

Estado: aceptado · Fecha: 2026-10-14 · Decidió: responsable del proyecto (2026-10-14, «2 ok todo», literal en la spec 015) · Reemplaza la versión propuesta del 2026-10-12 (commits 3a3b0ad4 y 814a5b9b, de T-256 y la mesa de comité)

## Contexto

La mesa de comité del 2026-10-12 encontró defectos en la medida que cambiaban las cifras (D1 a D9) y T-256 los corrigió. Con la medida corregida quedaron cuatro hechos que siguen valiendo:

- La coincidencia con el dictamen casi no puede ver un «cumple» falso: la mayoría de los pares se ganan absteniéndose.
- La única verdad por celda son las decisiones de la Comisión de prueba de T-229, en un solo caso (el caso-00, que además es de desarrollo). Las celdas de una misma fila se mueven juntas: la muestra efectiva es la cantidad de filas.
- Con la misma configuración la salida sale idéntica: repetir una corrida no mide el ruido.
- Toda la evaluación sale del caso con que se diagnosticó y se ajustó.

La versión propuesta del 2026-10-12 se usó en T-260, T-263 y T-266 sin estar aprobada. El 2026-10-14 el responsable la encontró «un tanto antojadiza» y pidió revisarla. La revisión (dos análisis independientes y una verificación contra los registros) encontró:

- **Lo sólido:** medir aciertos contra la Comisión y no la coincidencia con el dictamen; cero «cumple» sin fundamento (P3); separar los casos para ajustar de los casos para comprobar; reconocer que la evaluación sale de un solo caso.
- **Lo elegido a ojo:** el «doble del ruido», los «2 de 3 casos», el «no más de 1 unidad» en validación, el 5 % de la corrida alterada y el desempate «por tiempo y simplicidad», que además contradice la prioridad del responsable (calidad antes que tiempo, 2026-10-11 y 2026-10-14).
- **Lo que no rindió:** ningún criterio cambió una decisión. La corrida alterada costó de 85 a 94 minutos de GPU por medición y midió 0 las dos veces (0 de 52 celdas en T-260, 0 de 78 en T-263), porque no movía los bordes de los grupos (O-263-1). El archivo de unidades y el caso público nunca se hicieron, y el criterio de filas conservadas quedó siempre «pendiente».
- **Lo que faltaba:** la adopción del modelo (ADR-0057) comparó el 12B y el 27B con códigos distintos, aunque el ADR-0056 pedía «mismo commit del código».

## Decisión

Las metas de la spec 015 y de su plan siguen como están: dicen si una configuración llega a lo pedido. Estas reglas dicen si un cambio (de instrucciones, de código o de modelo) mejora frente a la configuración vigente. Cambiar una meta sigue pidiendo enmendar la spec con la aprobación del responsable (P11).

1. **Lo grave nunca empeora (P3, bloqueante).** No se adopta un cambio que deje un «cumple» sin fundamento (fundamento es lo que define la constitución en 1.3 y 1.4), una contradicción con la Comisión («cumple» donde dijo «no cumple»), más conclusiones erradas que la configuración vigente, o que haga faltar un requisito que la Comisión usó. Si pasa, decide el responsable (P7). Cada errada nueva se explica y va a la lista de revisión.

2. **Probar fuera del caso de ajuste.** Todo cambio de instrucciones se mide también en los casos de comprobación (regla 7). Perder 3 o más requisitos de la lista en un caso, o la traza de una circular (REQ-031), bloquea el cambio; perder 1 o 2 se explica fila por fila. Lo que falla en un caso de comprobación no se corrige mirando ese caso: va a la lista de revisión.
   - Por qué 3: cambios que no deberían influir ya movieron 2 entradas (T-260, caso-01, por el texto de alrededor) o 1 (O-265-3, por el lote). Con 3, la pérdida real de T-263 (6 en el caso-01, D-263-1) se detecta igual.

3. **Mejora solo si se nota.**
   - **Matriz:** la Comisión tiene que borrar al menos 10 puntos menos de las filas propuestas, o aparecen al menos 3 requisitos más de la lista, en al menos 2 casos. Se cuenta igual en las dos configuraciones (las dos con la cuenta mecánica de `medir_matriz`, o las dos revisadas por alguien que no sabe cuál es cuál) y no cuentan los requisitos que enseñan los ejemplos de las instrucciones.
   - **Evaluación:** se compara fila por fila contra las decisiones de la Comisión. Una fila mejora si mejora en alguna oferta y no empeora en ninguna. Hay mejora con 6 filas a favor y ninguna en contra, o con 8 a favor y 1 en contra (McNemar exacto, p < 0,05); si no, se informa «no se distingue con un solo caso».
   - Por qué esos tamaños: 10 puntos es una diferencia que la Comisión nota en su trabajo y supera los 6,1 puntos que separan la cuenta mecánica de la revisión (D6); 3 requisitos superan las 2 entradas que se movieron solas (regla 2); se cuentan filas y no celdas porque las celdas de una fila se mueven juntas.

4. **En un empate queda lo que ya está.** Un ajuste optativo que no mejora no se agrega. Un cambio que cumple una decisión literal del responsable solo tiene que pasar la regla 1. El tiempo desempata solo si el responsable lo pide.

5. **Comparar modelos en igualdad.** Dos modelos se comparan con el mismo código, las mismas instrucciones y los mismos casos, y se miden los dos con el mismo commit. Si no, la diferencia no se atribuye al modelo.

6. **De dónde sale cada cifra.** Cada cifra dice de cuántos casos sale, con qué código y con qué modelo. Hoy la evaluación tiene verdad por celda solo en el caso-00, que es de desarrollo: una mejora de evaluación se informa «en desarrollo», no como general. El segundo caso con decisiones reales de una Comisión lo va a dar el piloto, medido en el equipo local y sin subirlo (P4).

7. **Conjuntos de casos.**

   | Conjunto | Casos | Uso |
   |---|---|---|
   | Desarrollo | Caso-00 y caso chico | Diagnosticar y ajustar, con el umbral escrito antes |
   | Comprobación | 01, 02, 05 y 06 | Comprobar que un cambio no empeora fuera del caso-00 (regla 2). No se calcan ejemplos de sus textos. El 05 pasa de prueba a comprobación porque T-265 ya lo usó para ajustar |
   | Prueba | 03 y 04 | Congelados desde el 2026-10-14 con las listas re-ancladas de T-262 (huella y fecha). Una sola corrida por configuración final; no se miran para ajustar. Lo que no llega va a la lista de revisión (ADR-0024) |
   | A ciegas | El caso reservado | Una sola vez, al final, con el producto cerrado |

### Qué se quitó de la versión propuesta

- **El «doble del ruido»** como tamaño mínimo: una sola corrida alterada es una sola observación, y midió 0.
- **La corrida alterada obligatoria.** Queda optativa al cambiar de modelo o de configuración del motor, comprobando antes sin GPU que la alteración cambia los grupos; su resultado es informativo, no condición del veredicto.
- **El archivo de unidades como condición.** La matriz se mide con la lista presente sin lo que está a revisión obligatoria y con las filas que la Comisión borra (regla 3).
- **El desempate por tiempo y simplicidad** (reemplazado por la regla 4).
- **McNemar por celdas** (reemplazado por filas, regla 3).
- **«No perder más de 1 unidad» en validación** (reemplazado por 3, regla 2).

## Alternativas

- **Aprobar la versión propuesta tal cual.** Se mantienen números sin fundamento y una corrida alterada que cuesta hora y media de GPU por medición sin dar información.
- **No tener criterios escritos.** Se vuelve a adoptar por diferencias de una o dos decisiones, que están dentro de lo que se mueve solo.
- **Más rigor estadístico (varias corridas, más casos con verdad por celda).** Hoy no hay con qué: la salida a temperatura 0 es idéntica y hay un solo caso con decisiones de la Comisión. Se revisa cuando el piloto dé el segundo caso.

## Consecuencias

- Aplicadas a las mediciones ya hechas, estas reglas dan los mismos veredictos (revisión del 2026-10-14): en T-260 y T-263 la evaluación contra V1 da 7 filas a favor y 2 en contra, empate; T-263 pierde 6 requisitos en el caso-01, bloquea (T-265 lo corrigió); T-266 contra T-263 da −1, −1 y 0 en los casos de prueba, empate. No se reabre nada.
- La regla 5 no se cumplió en la adopción del 27B (ADR-0057). T-268 mide una vez el 12B con el código actual (decisión del responsable del 2026-10-14) para separar lo que aporta el modelo de lo que aporta el código.
- Los casos 03 y 04 quedan congelados desde hoy; el 05 pasa a comprobación.
- El caso público con ofertas y dictamen deja de ser trabajo pendiente del Coordinador: el segundo caso lo da el piloto.
