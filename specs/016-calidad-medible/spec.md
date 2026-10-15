# Spec 016 · Calidad medible: verdad ampliada, instrucciones simples y modelos externos por clase de dato

Estado: aprobada · Fecha: 2026-10-15 · Aprobó: responsable del proyecto (2026-10-15, «Apruebo la spec 016»)

> La spec dice qué se necesita y por qué. No menciona tecnología, librerías ni estructura de código: eso va en el plan.
> Cada duda se marca `[A ACLARAR: pregunta concreta]`. Una spec con marcas pendientes no pasa la compuerta.

## Problema

Con el modelo local adoptado (ADR-0057) la matriz propuesta ya se puede validar: en los casos de validación la Comisión conserva entre el 93 % y el 97 % de las filas firmes y en los de prueba entre el 77 % y el 89 % (T-266). La evaluación, en cambio, quedó estancada por debajo de la spec 015: en el caso-00 el 25,4 % de las celdas que cuentan quedan «no determinado» (el 42,9 % de las decidibles), el dato del Portal se usa en 7 de 14 celdas donde coincide y 14 de 17 preguntas son conformes (T-263). La Comisión decide a mano entre 1 de cada 4 y 1 de cada 3 celdas.

Hay tres causas que se refuerzan. Primera, la evidencia: la evaluación se mide celda por celda con un solo caso, el caso-00, con 48 celdas decididas por una Comisión de prueba, y es el mismo caso con que se ajustó el sistema. Con ese tamaño ninguna mejora se distingue del ruido (T-263 contra la versión anterior, p = 0,180; el 12B contra el 27B, p = 0,227), y la regla de «en empate queda lo que está» (ADR-0059) deja todo como está. Segunda, las instrucciones al modelo crecieron por acumulación: cada ronda agregó una regla para un fallo del caso-00 (la de evaluación va por la versión 12, la de extracción de la matriz por la 12, el filtro por la 9) y parte de las mejoras viene de formas que enseñan los ejemplos, que no son evidencia independiente. Tercera, una parte de los «no determinado» no la produce el modelo sino las reglas y el código que convierten su respuesta: pares que terminan en «no se encontró el documento» sin la pregunta que el modelo había escrito, o condiciones que la regla del Portal deja abiertas.

Por encima de todo eso, la constitución (P4, versión 1.5) prohibía procesar pliegos y ofertas con un modelo externo aunque sean públicos. El ADR-0065 lo cambió: lo publicado por transparencia puede usar una API externa cuando una medición muestra que mejora, prefiriendo siempre lo local a calidad igual; la hoja de compliance y las consultas de cumplimiento nunca salen del equipo. Esta feature usa esa puerta por etapas, mide cada paso contra un umbral escrito antes y no toca el piloto hasta que cada paso pasa.

## Decisiones del responsable (literales)

| Fecha | Tema | Decisión |
|---|---|---|
| 2026-10-14 | Clasificación de datos | «La conformidad del area legal o seguridad no se requiere sobre documentos como el pliego, las ofertas, las circulares y las evaluaciones terminadas porque es informacion publica mostrada sin authenticacion por normativa de trasnparencia del estado nacional. Eso incluye cualquier tipo de informacion polizas, firmas, pagares etc. Lo que si tiene una sensibiliodad mayor son algunas partes de lo que llamammos hoja de compliance donde por ejemplo se mira cumplimiento tributario.» (ADR-0065) |
| 2026-10-14 | Ofertas del proceso en curso | «las ofertas no son reservadas.»: tampoco antes del dictamen (resuelve el punto pendiente del ADR-0065). |
| 2026-10-14 | Preferencia | «Siempre prefiriendo el uso local cuanto sea posible sin resignar calidad.» |
| 2026-10-14 | Orden de trabajo | «Entiendo que las propuestas A D B y C podrian ser pasos incrementales de mejoras y quizas la C se torna innecesaria.» y «arrancá la spec de la feature 016 en un clon aparte, con la secuencia D, simplificación, A y B»: primero la verdad ampliada (D), después la simplificación de instrucciones y reglas, después la matriz con modelo externo (A) y por último el verificador externo de citas (B). La lectura completa de la oferta con modelo externo (C) queda fuera de esta feature. |
| 2026-10-15 | Quién valida la verdad | «La verdad celda por celda la arma un agente que rehace el caso como Comisión y la reviso yo.»: un agente rehace cada caso como lo haría la Comisión (como en T-229) y el responsable revisa y firma cada celda. |
| 2026-10-15 | Tope de gasto externo | «Tope de gasto externo: fijalo vos con una estimación razonable y me lo mostrás.»: el Coordinador fija el tope con la estimación de «Requisitos no funcionales»; el responsable lo aprueba con la spec. El 2026-10-15 objetó la primera estimación («es muchisimo. (…) Uso en otro proyecto centenas de pdfs contra la api con sonnet por 1 o 2 dolares.»); se rehízo con el modelo de gama media y los tamaños medidos, y el responsable fijó el tope: «2 dolares por caso 10 dolares mes». |
| 2026-10-15 | Tope de gasto externo (cifra) | «2 dolares por caso 10 dolares mes»: 2 USD por caso completo y 10 USD por mes. |
| 2026-10-15 | Falta de coincidencia con el Portal (REQ-120 y ADR-0053) | «Si, de acuerdo. Preguntar mostrando las dos posturas con contradicciones a la comision»: cuando el valor de la oferta y el dato del Portal no coinciden, la celda queda «no determinado» con las dos citas y además pregunta a la Comisión mostrando las dos posturas y la contradicción, y cuál rige. Enmienda el ADR-0053 (decisión 4). |
| 2026-10-15 | Con qué caso se arranca | «Arranquemos la medición con el caso 1 que está completo y es el más representativo, luego iremos agregando los documentos del resto» y, ante la pregunta, «Perdón no me refería al 1 me refería al 00»: las mediciones arrancan con el caso-00 (LPU25), el único completo; las ofertas y el dictamen de los demás casos los agrega el responsable después. Mientras tanto el paso 1 (verdad de casos nuevos, T-272 a T-276) queda bloqueado y el paso 2 se mide con el caso-00 y las matrices de los siete pliegos. |
| 2026-10-15 | Garantía de cumplimiento de contrato (REQ-102) | «Si . Solo queda garantía de mantenimiento de oferta la otra es extemporanea»: la garantía de cumplimiento de contrato que constituye el adjudicatario no es requisito de la oferta y no entra en la matriz; la garantía de mantenimiento de oferta sigue siendo requisito. Confirma la definición derivada D-32 del informe de revisión de instrucciones (T-279 y T-280). |
| 2026-10-14 | Dónde se trabaja | «Por una cuestion de metodologia y de proteccion de lo hecho apuntaria a trabajar sobre una clonacion o similar»: todo el trabajo corre en una instancia clonada; el piloto y lo integrado no cambian hasta que cada paso pasa su umbral. |

## Usuarios y escenarios

**Escenario 1 · Medir con evidencia.** Como responsable, cuando quiero saber si un cambio mejora la evaluación, necesito verdad celda por celda en varios casos públicos que no se usaron para ajustar, para que una mejora o un empeoramiento se vean y no dependan de un solo caso.

**Escenario 2 · Instrucciones que se entienden.** Como responsable, cuando reviso por qué el sistema decidió algo, necesito que la instrucción al modelo sea corta y diga solo las definiciones y decisiones vigentes, para poder controlarla contra la tabla de decisiones sin leer reglas acumuladas de rondas anteriores.

**Escenario 3 · Menos celdas a mano.** Como Comisión, cuando el sistema evalúa las ofertas, necesito que cada celda sin decidir traiga la pregunta o diga qué documento falta, y que lo decidible se decida, para concentrarme en lo dudoso.

**Escenario 4 · La matriz con lo que corresponde.** Como Comisión, cuando valido la matriz propuesta, necesito que no falte ningún requisito del pliego y que las filas de más sean pocas, aunque para eso el sistema use un modelo externo con el pliego, que es público.

**Escenario 5 · Lo reservado se queda.** Como Comisión, cuando cargo una hoja de compliance con el resultado de consultas tributarias, necesito la garantía de que nada de ese documento sale del equipo, aunque el resto de la evaluación use un modelo externo.

## Requisitos funcionales

| ID | Requisito | Origen normativo |
|---|---|---|
| REQ-118 | Existe verdad celda por celda (cumple, no cumple, no aplica o no determinado, con su fundamento) para al menos tres casos públicos además del caso-00, validada por una persona, dividida en un lote de ajuste y un lote de aceptación que nunca se usa para ajustar | P7, ADR-0059 |
| REQ-119 | Cada instrucción al modelo local (matriz, evaluación, contraste, visión, ficha, consulta) contiene solo las definiciones y decisiones vigentes de las specs, sin ejemplos copiados de los casos, con un largo máximo escrito en el plan, y queda registrada con su versión en cada pedido (P6) | Decisión del 2026-10-14 |
| REQ-120 | Toda celda de la evaluación termina en una de tres salidas: «cumple» con fundamento, «no cumple» con cita, o «no determinado» con la pregunta a la Comisión o el documento que falta nombrado; ninguna conversión del código deja una celda sin decidir sin decir por qué | P3 |
| REQ-121 | El sistema puede usar un modelo externo solo con documentos públicos; ningún pedido externo contiene un documento de tipo hoja de compliance ni un fragmento que provenga de uno, y los requisitos que dependen de esas consultas se evalúan siempre con el modelo local | ADR-0065, P4, P9 |
| REQ-122 | Cada pedido a un modelo externo queda en el registro de auditoría con proveedor, modelo, versión de la instrucción, texto enviado y respuesta; el registro de cada evaluación y de cada matriz dice qué etapas corrieron fuera del equipo; con el uso externo apagado el sistema funciona completo | P6, ADR-0065 |
| REQ-123 | La matriz de cumplimiento se puede proponer con un modelo externo que lee el pliego completo, con las mismas medidas y la misma lista esperada que la local; se adopta por etapa solo si mejora según el ADR-0065 y, en empate, queda la local | ADR-0065, ADR-0042 |
| REQ-124 | Una verificación con modelo externo puede revisar cada «cumple» o «no cumple» propuesto por el modelo local: confirma que la cita sostiene la conclusión y propone la redacción de la pregunta; si no la sostiene, la celda pasa a «no determinado» con pregunta; la verificación nunca convierte un «no determinado» en «cumple» | P3, ADR-0065 |
| REQ-125 | Cada paso de la feature (verdad ampliada, simplificación, matriz externa, verificador externo) se mide contra un umbral escrito antes, en la instancia clonada, y se integra solo si lo pasa; la elección local o externa de cada etapa queda en un ADR con su medición | ADR-0024, ADR-0025, ADR-0059 |

## Criterios de aceptación

Medidos con los casos públicos 00 a 06 en la instancia clonada. Umbrales escritos antes de medir; dos rondas como máximo por medición (ADR-0024 y ADR-0025). Los casos 03, 04 y 05 son el lote de aceptación y no se corren para ajustar.

- **REQ-118.** Dado el corpus público, cuando termina el paso de verdad ampliada, entonces hay al menos 3 casos más con verdad celda por celda, al menos 40 celdas decididas por caso y al menos 150 en total, cada una con quién la validó y cuándo: la arma un agente que rehace el caso como Comisión y la revisa y firma el responsable; al menos 2 de esos casos son del lote de aceptación y no se corrió el sistema sobre ellos antes de la medición final.
- **REQ-119.** Dadas las instrucciones nuevas, cuando se mide el modelo local con ellas en los casos de validación (00, 01, 02 y 06), entonces ninguna instrucción supera el largo máximo del plan, 0 ejemplos copian texto de un caso (la prueba automática mira también el cuerpo de los pliegos y las ofertas), y las medidas graves no empeoran: 0 «cumple» sin fundamento, 0 contradicciones con el dictamen, 100 % de citas literales, lista presente de la matriz igual o mejor en cada caso. Si las demás medidas empatan, queda la instrucción corta.
- **REQ-120.** Dada la evaluación de los casos con verdad, cuando se cuentan las celdas, entonces 0 celdas quedan en «no se encontró el documento» sin pregunta y el 100 % de los «no determinado» nombran la pregunta o el documento que falta. Lectura (Coordinador, 2026-10-15, con el plan): «no se encontró el documento» y «no aplica» se conservan como formas de «no determinado» con el documento o la razón nombrados (ADR-0038 y ADR-0043); no se cambia el esquema.
- **REQ-121.** Dada una oferta con una hoja de compliance cargada, cuando se evalúa con el uso externo encendido, entonces 0 pedidos externos contienen texto de ese documento y los requisitos que dependen de consultas externas (P9) corren en el modelo local, comprobado en el registro de auditoría.
- **REQ-122.** Dado el uso externo encendido, cuando se evalúa o se propone una matriz, entonces el 100 % de los pedidos externos están en el registro con proveedor, modelo, versión de la instrucción, texto enviado y respuesta, y la pantalla y la exportación de la evaluación dicen qué etapas corrieron fuera del equipo. Dado el uso externo apagado, cuando se corre la suite completa y el caso-00 completo, entonces pasan igual que hoy.
- **REQ-123.** Dado el lote de aceptación (03, 04 y 05), cuando se propone la matriz con el modelo externo y con el local, entonces el externo se adopta solo si la lista presente sube al menos 5 puntos en al menos 2 de los 3 casos sin bajar en ninguno, las filas firmes con pareja no bajan y los pedazos quedan en 0; si no, queda el local. Meta de la spec 015 para la matriz: lista presente al 95 % o más y filas conservadas al 70 % o más en los 3.
- **REQ-124.** Dado el lote de aceptación con verdad, cuando se evalúa con y sin el verificador externo, entonces con el verificador hay 0 «cumple» sin fundamento, el 100 % de las preguntas son conformes (dirigidas a la Comisión, con requisito, conclusión y texto), las celdas exactas no bajan y el «no determinado» no sube; si empata, queda sin verificador. Lectura (Coordinador, 2026-10-15, con el plan): como el verificador solo puede pasar un «cumple» o «no cumple» a «no determinado», «no sube» se mide así: ninguna celda exacta pasa a «no determinado» y todo «no determinado» nuevo viene de una celda que era errada; las erradas no suben. Meta de la spec 015 para la evaluación: Portal «cumple» con su cita 100 %, «no determinado» que cuenta 15 % o menos, preguntas conformes 100 %.
- **REQ-125.** Dado cada paso, cuando se integra, entonces su medición está registrada con el umbral escrito antes, el resultado y la decisión; existe un ADR por etapa que diga si queda local o externo y por qué.

## Requisitos no funcionales

- **Instancia clonada.** Todo el trabajo corre en una instancia aparte con su propia base restaurada del último respaldo; la instancia del piloto y lo integrado no cambian hasta que cada paso pasa su umbral. Una sola instancia usa la GPU a la vez.
- **Tiempo local.** El caso-00 completo con el modelo local no supera los 180 minutos (spec 015); la simplificación no lo empeora más de un 10 %.
- **Memoria de video.** 22.000 MiB como máximo (ADR-0042).
- **Costo externo.** Tope de **2 USD por caso completo** (matriz y verificación de las 3 ofertas, todas las rondas) y **10 USD por mes** mientras dura la feature (decisión del responsable del 2026-10-15: «2 dolares por caso 10 dolares mes»). Con 7 casos y 2 rondas, el tope mensual obliga a repartir la medición en más de un mes o a usar el modo de lotes del proveedor (mitad de precio); el plan lo prevé. Cada medición registra el gasto real por etapa, y una etapa que supere el doble de su estimación se frena y se informa antes de seguir. Estimación que sostiene el tope, con el modelo de gama media que usa el responsable en otros proyectos (precio de lista de octubre de 2026: 2 USD por millón de tokens de entrada, 10 por millón de salida, un décimo por lo reusado) y los tamaños medidos en T-148, T-263 y T-266 (una oferta ronda los 20.000 tokens; un pliego con sus anexos, entre 30.000 y 70.000):

  | Etapa | Tamaño por caso | Estimado |
  |---|---|---|
  | Matriz desde el pliego completo (A) | 30.000 a 70.000 tokens leídos una vez y reusados en 3 a 5 pedidos; unos 10.000 de salida | 0,20 a 0,30 USD |
  | Verificador de citas (B), unas 50 celdas con veredicto | 3.000 tokens de entrada y 300 de salida por celda | 0,30 a 0,50 USD |
  | Caso completo, una ronda | — | 0,50 a 0,80 USD |
  | Feature entera: 7 casos, 2 rondas, más pruebas de desarrollo | — | 10 a 20 USD |

  El modelo de gama alta, de usarse como segunda comparación, cuesta el doble y entra igual en el tope. La verdad ampliada (D) no gasta en la API: la arma un agente de construcción.

- **Sin salida a internet en las pruebas.** La suite automática corre sin acceso a la API externa, con dobles, y la clave queda fuera del repositorio.
- **Trazabilidad.** Igual que hoy: al repositorio van solo cifras, claves y estados; el texto de los casos queda fuera (P4, ADR-0060).

## Fuera de alcance

- La lectura completa de la oferta con un modelo externo (la variante C): se reabre, con spec propia, solo si al terminar esta feature el «no determinado» por lectura sigue por encima del umbral.
- La hoja de compliance como fundamento (feature 005) y su circuito de carga.
- Cambios de pantalla que no sean indicar qué etapas corrieron fuera del equipo.
- Comparar más modelos locales: la referencia local es el modelo adoptado por el ADR-0057.
- El proceso reservado para la prueba a ciegas: no se usa para esta feature.

## Datos involucrados

- Pliegos, circulares, ofertas, páginas del Portal y dictámenes de los casos 00 a 06: públicos (ADR-0065), en `corpus/casos/`, fuera de git. Pueden enviarse a un modelo externo en las etapas que esta spec permite.
- Hojas de compliance: reservadas. No hay ninguna real en el corpus; para probar REQ-121 se usan documentos inventados marcados como hoja de compliance.
- Verdad celda por celda y listas esperadas: se guardan junto al corpus, fuera de git; al repositorio van solo cifras.

## Preguntas abiertas

Ninguna. Las dos marcas del borrador se cerraron con las decisiones del 2026-10-15.
