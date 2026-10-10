# Spec 015 · Uso y elección del modelo

Estado: aprobada · Fecha: 2026-10-10 · Aprobó: responsable del proyecto (2026-10-10, «ok apruebo»)

## Problema

Al rehacer el caso real LPU25 como lo haría la Comisión (T-229, `specs/014-aplicacion-por-secciones/verificacion/T-229.md`), el sistema propuso una matriz de 122 filas y la Comisión quitó 95 (78 %). En la evaluación, 87,7 % de las celdas quedaron «no determinado» y el resultado coincidió con el dictamen publicado en 2 de 3 ofertas. Las preguntas a la Comisión fueron genéricas o dirigidas al oferente, y algunas explicaciones contradicen lo que muestra la pantalla.

El diagnóstico del 2026-10-10 (fuera del repositorio, en la carpeta local del Coordinador) atribuye cerca del 85 % de esos errores a cómo se usa el modelo y el 15 % al modelo. En la matriz, 69 de las 95 filas quitadas vienen de las instrucciones: piden dividir enumeraciones y copiar el fragmento más corto, mantener ante la duda, y no distinguen las condiciones opcionales. 16 vienen del modelo y 9 de tramos que llegan sin su encabezado. En la evaluación, 17 celdas quedan sin decidir porque una regla no usa el dato del Portal aunque coincide. Unas 13 se deben a que la instrucción pide el fragmento mínimo y el veredicto antes del razonamiento. 33 dependen de documentos que el caso no tiene (informe técnico, hojas de compliance). Sin corregir el uso, comparar modelos no sirve: el Gemma 4 26B ya rindió peor que el 12B con el mismo uso (ADR-0042).

## Decisiones del responsable (literales)

| Fecha | Tema | Decisión |
|---|---|---|
| 2026-10-10 | Prioridad | «si ya se anticipa que hay que evaluar el modelo y que los numeros de eficiencia son una verguenza empeza a planifiacar la evaluacion del modelo incluso evalua probar otros modelos locales de IA como quen 3.6 30B o el que sugieras a modo de ejemplo. Con los errores o sabrantes en 78 por ciento pasan dos cosas o el modelo elegido no es el mejor o lo estamos utilizando mal. Creo que hay que trabajar ahora para reducir ese gap y los que vengan por la misma causa y luego terminar el resto, porque estamos haciendo cosmetica.» |
| 2026-10-10 | GPU | «si los agentes necesitan usar gpu , no los limites» |
| 2026-10-10 | Instrucciones al modelo | «REvisa tambien como se propmtea los modelos exhaustivamente» |
| 2026-10-10 | Dato del Portal que coincide | «Propone cumple»: el sistema propone «cumple» citando el dato del Portal cuando coincide con lo que exige el pliego, y «no cumple» o diferencia cuando no coincide; la Comisión decide igual. Reemplaza en eso al ADR-0043. |
| 2026-10-10 | Qué entra en la matriz | «no entran ninguno de los 3. una salvedad la moneda de la oferta si es un requisito.»: no son requisitos de la oferta el pago, la moneda de pago y la factura; la forma de presentar por el Portal (por ejemplo, la confirmación por el Administrador Legitimado), ni los compromisos que se cumplen al presentarse (por ejemplo, «la mera presentación implicará el conocimiento y aceptación del pliego»). La moneda en que se cotiza la oferta sí es requisito. |
| 2026-10-10 | Descarga de modelos | «Sí, ya en segundo plano»: se bajan Qwen3.8-27B y Qwen3.6-35B-A3B mientras se corrige el uso. |

## Usuarios y escenarios

**Escenario 1 · Matriz que se puede validar.** Como Comisión, cuando el sistema propone la matriz desde el pliego, necesito que cada fila sea un requisito que la oferta debe cumplir, escrito con su oración completa, para validar confirmando y corrigiendo poco, no quitando la mayoría.

**Escenario 2 · Evaluación que resuelve lo que puede.** Como Comisión, cuando el sistema evalúa las ofertas, necesito que decida con el texto de la oferta, el pliego y el Portal todo lo que tiene respaldo, y que me pregunte con el requisito, la conclusión y el texto delante solo lo que no puede resolver, para concentrarme en lo dudoso.

**Escenario 3 · Elegir el modelo con evidencia.** Como responsable, cuando hay modelos locales nuevos, necesito compararlos con el mismo uso, el mismo caso y la misma lista esperada, para adoptar uno solo si mejora con razones medidas.

## Requisitos funcionales

| ID | Requisito | Origen normativo |
|---|---|---|
| REQ-101 | Cada requisito propuesto en la matriz cita la oración completa del pliego (con el encabezado del punto o del inciso cuando la oración sola no se entiende), nunca un pedazo sin sujeto | — |
| REQ-102 | La matriz propuesta no incluye consecuencias, obligaciones del organismo, condiciones que solo valen si el oferente elige una opción (salvo como condición de esa opción), pago, moneda de pago, factura, forma de presentar por el Portal ni compromisos que se cumplen al presentarse; sí incluye la moneda en que se cotiza la oferta | Decisión del 2026-10-10 |
| REQ-103 | Cuando el dato de la oferta está en el Portal y coincide con lo que exige el pliego, la evaluación propone «cumple» citando el dato del Portal; cuando no coincide, propone «no cumple» o la diferencia | Decisión del 2026-10-10 |
| REQ-104 | En la evaluación, el sistema razona antes de dar el veredicto, cita la oración completa de la oferta y del pliego, y el contraste ve el contexto de la cita | — |
| REQ-105 | Cada pregunta a la Comisión está dirigida a la Comisión (nunca al oferente) y dice qué requisito, qué conclusión y qué texto la motivan; no hay preguntas de texto fijo genérico | — |
| REQ-106 | Todas las instrucciones al modelo (matriz, evaluación, contraste, visión, ficha, consulta) se revisan contra las decisiones vigentes y entre sí: sin reglas que empujen al error, con ejemplos representativos, razonamiento antes del veredicto y la versión registrada en cada pedido (P6) | Decisión del 2026-10-10 |
| REQ-107 | Un modelo nuevo se adopta solo si, con el uso corregido, el mismo caso y la misma lista esperada, mejora las medidas de REQ-101 a REQ-105 sin empeorar contradicciones, citas, tiempo ni memoria, con cada cambio explicado | ADR-0002, ADR-0042 |

## Criterios de aceptación

Medidos con el caso-00 (LPU25) y los casos 01 a 06, públicos. El caso reservado para evaluar a ciegas no se usa. Umbrales escritos antes de medir; dos rondas como máximo (ADR-0024 y ADR-0025).

- **REQ-101 y REQ-102.** Dado el pliego de cada caso, cuando el sistema propone la matriz, entonces la Comisión conserva al menos el 70 % de las filas propuestas (hoy 22 %), 0 filas son pedazos sin sujeto, y están al menos el 95 % de los requisitos de la lista esperada.
- **REQ-103.** Dado un dato del Portal que coincide, entonces la celda se propone «cumple» con la cita del Portal en el 100 % de los casos, y 0 celdas «cumple» con un dato que no coincide.
- **REQ-104.** Dada la evaluación del caso-00, entonces las celdas «no determinado» que no esperan un documento ausente (informe técnico u hoja de compliance) son el 15 % o menos (hoy 47 %); 0 contradicciones con el dictamen; 100 % de citas literales.
- **REQ-105.** El 100 % de las preguntas cumplen REQ-105, revisadas una por una.
- **REQ-106.** El informe de revisión cubre el 100 % de las instrucciones vigentes; cada hallazgo de gravedad alta queda corregido o justificado por escrito.
- **REQ-107.** Cada modelo candidato se mide con el protocolo del ADR-0042 (todo igual salvo el modelo); se adopta solo si cumple REQ-101 a REQ-105 al menos tan bien como el 12B con el uso corregido, mejora en al menos uno con razones por par, entra en 22.000 MiB y tarda como máximo 60 minutos con el caso-00 completo.

## Requisitos no funcionales

- Tiempo con el caso-00 completo (matriz más evaluación de las 3 ofertas): hasta 60 minutos de GPU (hoy 13,5 + 23).
- Memoria de video máxima: 22.000 MiB (ADR-0042).
- Una medición a la vez en la GPU.

## Fuera de alcance

- Cambios de pantalla (la 014).
- El informe técnico del área y las hojas de compliance: el caso no los tiene; esas celdas se cuentan aparte.
- Instrucciones distintas para cada modelo: la comparación usa las mismas.

## Datos involucrados

Pliegos, ofertas, páginas del Portal y dictámenes de los casos 00 a 06, públicos, en `corpus/casos/` (fuera de git). Al repositorio solo van cifras y resultados (P4).

## Preguntas abiertas

Ninguna.
