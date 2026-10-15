# Revisión de las instrucciones al modelo de la 016 · decisiones y oraciones

Spec 016, REQ-119 · ADR-0070 · Tareas T-278 (tabla de decisiones), T-279 a T-282 y T-291 (instrucciones nuevas).

Este archivo es el resumen para el repositorio: **no lleva texto ni cifras de los casos** (P4). Tiene dos partes:

1. **Tabla de decisiones.** Cada decisión literal del responsable que una instrucción tiene que aplicar, con su fuente. Sale de las tablas «Decisiones del responsable» de las specs 003, 004, 014 y 015 y de los ADR 0043, 0053, 0054 y 0058. Los ejemplos de las decisiones que vienen de un caso se omiten (se indica en la fila); las instrucciones se escriben en términos generales, sin ejemplos de licitaciones.
2. **Oración → decisión, por instrucción nueva.** Por cada instrucción de la 016, una tabla con cada oración de la instrucción y la decisión de la que sale (`D-NN`). La completa la tarea que escribe la instrucción. El responsable controla la instrucción contra esta tabla (escenario 2 de la spec).

Lo prueba `tests/test_instrucciones_revisadas.py`: toda versión de la tabla `SIMPLIFIED` (`tests/test_instrucciones_largo.py`) tiene su sección `### <versión>` con al menos una fila de oración, y cada fila nombra una decisión de la tabla de decisiones. Una versión que se suma a `SIMPLIFIED` con su sección sin completar hace fallar esa prueba. El largo y el no calco los prueban `test_instrucciones_largo.py` y `test_instrucciones_sin_casos.py`.

## Tabla de decisiones

La columna «Aplica a» es la propuesta de T-278; T-279 a T-282 la confirman al completar sus tablas.

| Id | Decisión (literal, entre comillas angulares) | Fuente | Aplica a |
|---|---|---|---|
| D-01 | «Es requisito de la oferta lo que la oferta tiene que presentar, ofrecer o comprometer, y toda condición del pliego que la oferta pueda contradecir o condicionar, aunque la cumpla el organismo». «No son requisitos de la oferta la ejecución y el control del contrato, como las multas por atraso.» (El ejemplo del pago de la decisión original lo reemplaza D-12.) | Spec 003, «Qué es un requisito», 2026-10-03 | definiciones, extracción |
| D-02 | Los requisitos técnicos van «en una fila por renglón del pliego, con la cita a sus especificaciones técnicas». «La Comisión no evalúa el detalle técnico: se apoya en el informe técnico del área requirente.» | Spec 003, «Qué es un requisito», 2026-10-03 | definiciones, extracción, completitud, filtro, evaluación |
| D-03 | «La clase sigue la sección del pliego cuando el pliego ordena sus requisitos por secciones. Si no, se clasifica por naturaleza: la garantía, el precio, la moneda y el pago son económicos; los documentos y compromisos de la presentación, formales; el bien y su entrega, técnicos.» (Pago, moneda de pago y compromisos de la presentación ya no son requisitos: D-12.) | Spec 003, «Qué es un requisito», 2026-10-03 | definiciones, extracción, completitud |
| D-04 | «El sistema no decide si un requisito es subsanable: detecta qué consecuencias tiene su falta, sugiere las posibles con su fundamento, y un integrante de la Comisión confirma una.» Tipos: desestimación sin posibilidad de subsanar; intimación a subsanar y, si no se subsana, desestimación; consultar al oferente; aprobación condicionada; aprobar de todas maneras; otra consecuencia prevista en el pliego; no determinada (el sistema no encontró fundamento). | Spec 003, «Consecuencia del incumplimiento», 2026-10-03; REQ-029 | definiciones, extracción, consecuencias |
| D-05 | REQ-031: las circulares y las respuestas a consultas cambian o precisan un requisito; la matriz aplica el cambio, muestra los dos textos y cita el documento que lo produjo. «Versión nueva de la matriz»: la circular abre una versión nueva, con lo que cambió marcado, y la Comisión la valida de nuevo. «Lo no tocado confirmado»: solo se decide lo que cambió la circular. | Spec 003, REQ-031; spec 014, 2026-10-07 y 2026-10-10 | circulares |
| D-06 | REQ-033 y REQ-035: antes de mostrar la matriz se descartan las filas que no son requisitos de la oferta, cada una con su cita y su motivo; las condiciones plausibles sobre las que el sistema duda van como sugerencia de condición, con su cita y el motivo de la duda. Lo descartado y lo dudado no desaparece. | Spec 003, REQ-033 y REQ-035 | definiciones, extracción, filtro |
| D-07 | REQ-036: para cada sugerencia y cada fila dudosa se busca en la normativa aplicable si el régimen exige esa condición. «La normativa solo sirve para confirmar: que una condición no figure en la norma nunca es motivo para descartarla, porque el pliego puede agregar exigencias propias.» | Spec 003, REQ-036 | respaldo |
| D-08 | «el porcentaje esta bien, aunque no necesariamente sea literal la coincidencia. Lo tecnico verificamos que exista y que en caso de tener renglones si tiene o no tiene oferta» | Spec 004, 2026-10-06, «Coincidencia y técnico» | evaluación |
| D-09 | «La parte tecnica ya te dije que venia del area correspondiente»; «la comision debiera dar el ok de que tiene el informe tecnico aprobado». REQ-061: el sistema verifica que exista el documento técnico y qué renglones tienen oferta; el cumple o no cumple técnico lo da el informe técnico del área. La opinión técnica con citas, si la hay, es información, no resultado. | Spec 004, 2026-10-06, «Técnico» y REQ-061; ADR-0043, decisión 3 | evaluación, informe técnico |
| D-10 | «eso lo integrará un documento que llamamos hoja de compliance. Si detectas que falta uno pueden subir otra. O una que informe que No cumple». REQ-063: un requisito que se verifica con consultas externas tiene resultado «falta la hoja de compliance»; «nunca duda». | Spec 004, 2026-10-06, «Externos» y REQ-063; ADR-0043, decisión 1 | evaluación, definiciones |
| D-11 | «Debiste informar que el doc esta en el portal o que falta coincidencia». REQ-062: cuando el dato o el documento está en el Portal, el sistema lo informa y lo cita como fuente (Portal, con su página o cuadro); si el Portal y la oferta no coinciden, lo informa como falta de coincidencia. | Spec 004, 2026-10-06, «Portal» y REQ-062; ADR-0043, decisión 2 | evaluación |
| D-12 | «no entran ninguno de los 3. una salvedad la moneda de la oferta si es un requisito.»: no son requisitos de la oferta el pago, la moneda de pago y la factura; la forma de presentar por el Portal; ni los compromisos que se cumplen al presentarse. La moneda en que se cotiza la oferta sí es requisito. (Los ejemplos de la decisión se omiten acá: ver la fuente.) | Spec 015, 2026-10-10, «Qué entra en la matriz»; ADR-0054, decisión 4 | definiciones, extracción, completitud, filtro, circulares |
| D-13 | «Requisito de la forma elegida»: las condiciones de cada forma de garantía entran en la matriz y se evalúan solo en la oferta que eligió esa forma; para las demás no aplican. Una condición que solo vale si el oferente puede no usar una opción (alternativa, descuento, MiPyME, subcontratación) entra solo como condición de esa opción; la oración que le exige algo a quien usa la opción se mantiene. | Spec 015, 2026-10-10, «Forma de garantía que elige el oferente»; ADR-0054, decisión 4 | definiciones, extracción, filtro, evaluación |
| D-14 | «Una fila por oración»: una fila con la oración completa; la evaluación revisa cada condición con su dato y lo muestra por separado dentro de la celda. Aclaración: «cuando dije una condicion por fila lo estaba diciendo para un parrafo o una oracion que tenia 2 o mas condiciones y pretendo que se evaluen todas. Lo mas razonable es tomar las oraciones cortas dentro del mismo contexto semantico no separado. Te doy un ejemplo, quiero comprar un perro que tenga cuatro patas, dos ojos y de color marron. la oracion es clara si la tomas toda, luego si la separas las condiciones y me pones cuatro patas en una fila, dos ojos en otra, y marron en otra pierde sentido y es muy dificil de evaluar.» | Spec 015, 2026-10-10, «Filas de la matriz» y «Unidad de la fila»; ADR-0054, decisión 3 | definiciones, extracción, completitud, unión, evaluación |
| D-15 | REQ-101: la cita es la oración completa, con el encabezado del punto o del inciso cuando la oración sola no se entiende, nunca un pedazo sin sujeto. El modelo señala un fragmento; el sistema lo ubica y lo amplía a la oración. Una duda real no se pierde: va a sugerencia, no a un descarte silencioso. La extracción conserva «proponé de más», limitado a oraciones que le exigen algo a todas las ofertas; la completitud y el filtro no. | ADR-0054, decisiones 1, 2, 6 y 7 | definiciones, extracción, completitud, unión, filtro |
| D-16 | «Propone cumple»: el sistema propone «cumple» citando el dato del Portal cuando coincide con lo que exige el pliego, y «no cumple» o diferencia cuando no coincide; la Comisión decide igual. El Portal le llega al modelo como un bloque citable que escribe el sistema desde las columnas; lo que se compara por regla (montos, CUIT) lo decide el código. Un requisito de dos condiciones no es «cumple» si a una le falta el dato. | Spec 015, 2026-10-10, «Dato del Portal que coincide»; ADR-0053, reglas 1 a 5 y 4 bis | evaluación |
| D-17 | «enmendar. considera al portal como oficial, porque es oficial»: el dato publicado en el Portal de Compras vale como fundamento (constitución 1.3). | Spec 015, 2026-10-10, «El Portal como fundamento (P3)»; ADR-0053 | evaluación, contraste |
| D-18 | «Cumple por ausencia, con fundamento»: un requisito negativo o supletorio se propone «cumple» diciendo qué documentos se leyeron y que ninguno lo contradice; si alguno lo contradice, «no cumple» con la cita. Rige solo para prohibiciones sobre lo que dice la oferta y reglas supletorias, con nada en contra en las condiciones ni en el grupo, el contraste sin rechazar y la lectura completa. Una exigencia de documento dicha en negativo pide el documento. Ante la duda, «no determinado» con pregunta. | Spec 015, 2026-10-12; ADR-0058, decisión 2 y aplicación (constitución 1.4) | evaluación, contraste |
| D-19 | «Precio del Portal = final con IVA»: salvo que la oferta diga lo contrario, el precio cotizado en el Portal es precio final con IVA incluido; se propone «cumple» citando el Portal y este criterio. No rige si la oferta dice algo sobre impuestos o ajustes de precio. | Spec 015, 2026-10-12; ADR-0058, decisión 1 y aplicación | evaluación |
| D-20 | «En la misma fila del plazo»: una sola fila con el plazo de mantenimiento y su prórroga automática (mismo asunto); se evalúa por ausencia salvo que la oferta limite el plazo o rechace la prórroga. El aviso de no renovar, su firma, su fecha y lo que pasa si no se avisa no son esa fila ni otra (aclaración del Coordinador, T-258). | Spec 015, 2026-10-12, «Prórroga automática del mantenimiento»; ADR-0058, decisión 3 | definiciones, extracción, completitud, unión, evaluación |
| D-21 | «si requiere presentacion fisica y no la hace (no consta entre los documentos ni en la matriz de compliance) la oferta no cumple se informa con texto por si la comision o alguien olvido agregarla»: presentar en la mesa de entradas lo que el Portal marca como «Requiere presentar» es requisito; la cláusula de completar la oferta económica por el formulario del Portal no es fila propia (es forma de presentar por el Portal). Mientras el Portal no traiga la marca, cuando la obligación depende de ella el resultado es «no determinado» con pregunta a la Comisión. | Spec 015, 2026-10-12; ADR-0058, decisión 4 y aplicación | definiciones, extracción, filtro, evaluación |
| D-22 | «lo del pagare es ilegible se informa asi y ese si lo chequea la comision»; «con la aclaracion de que no pudo leer alguno». REQ-064: si el documento que responde un requisito no se puede leer, el resultado es «no se pudo leer», con el documento y la página. | Spec 004, 2026-10-06, «Ilegible» y REQ-064 | evaluación, visión |
| D-23 | «Informa 'no se encontró documento' la comisión decide». «el que lo haga la comision no es opcion, asi el sistema no aporta nada. La comision conformar y elegir en casos que no haya alternativa.» | Spec 004, 2026-10-06, «Documento faltante» y «Rol del sistema» | evaluación |
| D-24 | Los cuatro resultados (cumple, no cumple, no se encontró el documento, no determinado) no cambian; los motivos de «no determinado» son `pendiente_informe_tecnico`, `no_se_pudo_leer`, `en_portal`, `falta_coincidencia` y `externo` (se muestra como «Falta la hoja de compliance»). Una regla decide antes del modelo, en este orden: externo, técnico, ilegible, Portal. | ADR-0043, decisiones 1 y 2 | evaluación |
| D-25 | «Mantengo la visión, siempre es preferible a no leída. Obviamente aclarando que proviene de un documento con dificultades de lectura y que conviene re chequear por la comisión, ofreciendo ver la imagen»: toda cita de una página leída por visión lo dice. | Spec 015, 2026-10-13, «Lectura por visión con el 27B» | visión |
| D-26 | «Lo que presentó cada oferta»: por oferta, qué presentó frente a cada requisito de la matriz, con el fragmento de la oferta (la ficha de la oferta). Anexos técnicos, «Solo los de la oferta»: fichas y folletos técnicos que presenta cada oferente; el informe técnico del área va en la sección de evaluación. | Spec 014, 2026-10-07, puntos 3.4 y 3.5 | ficha, ficha por renglón, informe técnico |
| D-27 | «El sistema lo propone»: lee los archivos de la oferta y propone nombre y CUIT del oferente con su cita; la Comisión aprueba o corrige. «Escribe el valor y motivo»: lo propuesto se corrige con motivo obligatorio; nada se escribe desde cero. | Spec 014, 2026-10-07, «Alta de oferta sin Portal» y «Corregir un dato propuesto» | oferente, procedimiento |
| D-28 | Evaluación legible (A): el punto completo del pliego, las preguntas con su contexto, los requisitos externos aparte y qué se leyó y dónde (resumen de la spec; la decisión literal habla de cómo rehacer un caso y no de la instrucción). | Spec 014, 2026-10-10, «Evaluación legible y revisión» | evaluación, contraste, cláusulas |
| D-29 | «La Comisión ve todo»: cada consulta de normativa queda con quién la hizo. La consulta responde con la cita de la norma y se abstiene cuando no la encuentra (evals de la 001, ADR-0002). | Spec 014, 2026-10-10, «Historial de la Consulta»; spec 015, 2026-10-14, «Calidad antes que tiempo» | consulta |
| D-30 | «REvisa tambien como se propmtea los modelos exhaustivamente»; «Siempre prefiriendo el uso local cuanto sea posible sin resignar calidad». Las instrucciones nuevas llevan solo las definiciones y decisiones vigentes de esta tabla, en términos generales y sin ejemplos de licitaciones. | Spec 015, 2026-10-10, «Instrucciones al modelo»; spec 016, REQ-119 y 2026-10-14, «Preferencia» | todas |
| D-31 | Las «formas» que la medición de la 015 mostró y que quedan como definiciones del responsable, sin ejemplo: la presentación física (D-21), el mantenimiento con su cómputo y su prórroga (D-20), la nota de la tabla de una declaración jurada, que si le exige algo al oferente es requisito y no se descarta como planilla en blanco (D-14), la cotización parcial (D-13: quien cotiza una parte y la condición para que se considere) y la forma de garantía con su límite y la copia en filas separadas (D-13 y D-14: dos obligaciones distintas sobre el mismo objeto son filas distintas). | Plan 016, «Paso 2»; ADR-0059; 015, T-258, T-262 y T-265 (resúmenes en `specs/015-uso-y-eleccion-del-modelo/revision-instrucciones.md`) | definiciones, extracción, unión |

## Oración → decisión, por instrucción nueva

Formato de cada fila: la oración de la instrucción (o su primera frase, si es larga) y las decisiones de las que sale (`D-NN`, separadas por comas). Una oración que no sale de ninguna decisión no va en la instrucción. Lo que el código ya garantiza (ubicar las citas, el esquema JSON, derivar el resultado de las condiciones) tampoco. Los nombres de `matriz-circulares-v8` y `matriz-circulares-cambios-v7` los confirma T-280.

## Instrucciones de T-279

Los títulos en mayúsculas («QUÉ DEVOLVER POR TRAMO», «SALIDA») y la marca `{{DEFINICIONES}}` no son oraciones: ordenan el texto. El bloque `matriz-definiciones-v9` lo incluyen, donde tienen la marca, la extracción v13, la completitud v7 y la unión v2 (y, hasta que T-280 las reemplace, el filtro v9 y las circulares v7). Una oración larga se nombra por su primera frase. El esqueleto de la salida se nombra sin copiarlo (lleva una barra vertical que rompería la tabla).

### matriz-definiciones-v9

| Oración | Decisión |
|---|---|
| QUÉ ES UN REQUISITO DE LA OFERTA (título del bloque) | D-01 |
| Estas definiciones son decisiones del responsable y valen para toda la matriz. | D-30 |
| Es requisito de la oferta lo que la oferta tiene que presentar, ofrecer o comprometer, y toda condición del pliego que la oferta pueda contradecir o condicionar, aunque la cumpla el organismo. | D-01 |
| También lo es lo que el organismo comprueba del oferente con una consulta fuera de la oferta (registros, deudas, sanciones): es un requisito externo. | D-01, D-10 |
| Una condición puede estar dicha como efecto sobre la oferta («se considerará», «se entenderá», «quedará»): si nombra algo que la oferta tiene que presentar o cumplir, es requisito; si solo dice qué pasa cuando no se cumple otra condición, es una consecuencia. | D-01, D-04 |
| Una fila es una unidad de sentido: la oración completa del pliego, con todas sus condiciones. | D-14, D-15 |
| Si la oración junta varias condiciones, sigue siendo una fila: la evaluación revisa cada una dentro de la celda. | D-14 |
| Las oraciones cortas seguidas que continúan el mismo asunto, sin sujeto propio o remitiendo a la anterior, van en la misma fila. | D-14 |
| Dos obligaciones distintas sobre un mismo objeto son dos filas, aunque estén seguidas. | D-14, D-31 |
| El mantenimiento de la oferta, con su plazo, su cómputo y su prórroga automática, es una sola fila. | D-20, D-31 |
| El aviso del oferente para no renovarla, y lo que pasa si no avisa, no es fila. | D-20 |
| No son requisitos de la oferta, aunque el pliego diga «deberá»: | D-01, D-12 |
| las consecuencias de no cumplir (desestimar, intimar a subsanar, sancionar, ejecutar una garantía); la condición que las origina sí es requisito; | D-01, D-04 |
| las obligaciones del organismo que la oferta no puede contradecir ni condicionar; | D-01 |
| la ejecución y el control del contrato: lo que el adjudicatario hace, entrega o garantiza durante la prestación, incluida la garantía que constituye para asegurar que cumplirá; lo que se acredita al ofertar sí es requisito; | D-01 |
| el pago, la moneda de pago y la factura; | D-12 |
| la forma de presentar la oferta por el Portal (cargar, subir o completar datos en él); la cláusula que pide completar la oferta económica en el formulario del Portal no es fila propia; | D-12, D-21 |
| los compromisos que se cumplen con solo presentarse; | D-12 |
| las definiciones, los datos del procedimiento, la cita de normas, los títulos, los índices y las planillas o modelos en blanco. | D-01, D-31 |
| Sí son requisitos de la oferta: | D-12, D-13, D-21 |
| la moneda en que se cotiza la oferta; | D-12 |
| entregar en papel lo que el Portal marca como «Requiere presentar», aunque la oración empiece por la carga en el Portal; | D-21, D-31 |
| las condiciones de la forma de garantía que el oferente elige, que se evalúan solo en la oferta que eligió esa forma; | D-13 |
| la nota de una planilla o de una declaración que le exige algo al oferente sobre lo que informa. | D-14, D-31 |
| Opciones: una condición que solo vale si el oferente usa una opción que puede no usar (oferta alternativa, descuento, cotización parcial, beneficio MiPyME, subcontratación) entra solo como condición de esa opción. | D-13, D-31 |
| La oración que solo permite o describe la opción, sin exigirle nada a quien la usa, no es requisito. | D-13 |
| Clases: si el pliego ordena sus requisitos por secciones, la clase es la de la sección. | D-03 |
| Si no, por naturaleza: la garantía, el precio y la moneda de cotización son económicos; los documentos, las declaraciones y los compromisos de la oferta, formales; el bien y su entrega, técnicos, en una fila por renglón con la cita a sus especificaciones. | D-02, D-03, D-12 |
| Duda: una duda real no se pierde; va como sugerencia con su motivo, nunca a un descarte silencioso. | D-06, D-15 |

### matriz-extraccion-v13

| Oración | Decisión |
|---|---|
| Leés tramos del pliego de una contratación y decís, por cada tramo, qué requisitos de la oferta contiene o por qué no contiene ninguno. | D-01, D-06 |
| Cada tramo va entre [Tn] y [/Tn], con su documento, su ruta, a veces sus renglones, y su texto. | D-30 |
| La línea «Encabezado:» es el comienzo del punto al que pertenece el tramo: sirve para entender una oración que sola no se entiende y nunca se cita. | D-15 |
| (Bloque `matriz-definiciones-v9`, por la marca) | D-30 |
| "requisitos": cada requisito de la oferta que trae el tramo, con su cita, su clase y su opción. | D-01 |
| "cita": la oración que lo exige, entera y copiada letra por letra del texto del tramo, junto con las oraciones seguidas del mismo asunto. | D-14, D-15 |
| "clase": "formal" o "economico", según las definiciones. | D-03 |
| "opcion": "" si el requisito vale para toda oferta. | D-13 |
| Si es la condición de una opción que el oferente puede no usar, el nombre de esa opción: "mipyme", "oferta_alternativa", "descuento", "subcontratacion", "cotizacion_parcial" u "otra". | D-13 |
| La forma de garantía que el oferente elige no es una opción. | D-13 |
| "tecnico": si el tramo trata del bien o de su entrega, los renglones a los que se aplica, o "todos" si son todos o no se sabe cuáles; si no, vacío. | D-02 |
| "descarte": si el tramo no trae requisitos ni nada técnico, el motivo; si no, vacío. | D-06 |
| Motivos de descarte, según las definiciones: | D-06 |
| titulo: un título. | D-01 |
| indice_caratula: un índice o una carátula. | D-01 |
| dato_procedimiento: una definición o un dato del procedimiento. | D-01 |
| norma_aplicable: la cita o la transcripción de una norma. | D-01 |
| formulario: una planilla o un modelo en blanco. | D-01, D-31 |
| obligacion_organismo: una obligación del organismo que la oferta no puede contradecir ni condicionar. | D-01 |
| ejecucion_contrato: la ejecución o el control del contrato después de adjudicar, incluida la garantía que constituye el adjudicatario. | D-01 |
| consecuencia_sancion: una consecuencia de no cumplir. | D-04 |
| condicion_opcional: una oración que solo permite o describe una opción y no le exige nada a quien la usa. | D-13 |
| pago_factura: el pago, la moneda de pago o la factura. | D-12 |
| forma_presentacion_portal: la forma de presentar la oferta por el Portal. | D-12, D-21 |
| compromiso_presentacion: un compromiso que se cumple con solo presentarse. | D-12 |
| Todo tramo trae requisitos, una marca técnica o un motivo de descarte. | D-06 |
| Un tramo puede traer requisitos y marca técnica a la vez; un motivo de descarte nunca va con ninguno de los dos. | D-02, D-06 |
| En esta lectura buscás que no falte nada: ante la duda de si una oración le exige algo a todas las ofertas, proponela. | D-15 |
| Si un tramo trae un requisito y también frases de un motivo de descarte, devolvé el requisito. | D-06, D-15 |
| Un objeto JSON con una propiedad por alias, y el esqueleto de la salida con marcadores (cita, clase, opción, técnico y descarte de un tramo). | D-30 |

### matriz-completitud-v7

| Oración | Decisión |
|---|---|
| Una primera lectura de un pliego ya propuso los requisitos de cada tramo. | D-15 |
| Tu tarea es decir qué requisito formal o económico de la oferta quedó afuera. | D-03, D-15 |
| Cada tramo va entre [Tn] y [/Tn], con sus «Requisitos ya encontrados» («ninguno» si la primera lectura lo descartó) y su texto. | D-30 |
| La línea «Encabezado:» es contexto y nunca se cita. | D-15 |
| (Bloque `matriz-definiciones-v9`, por la marca) | D-30 |
| Por cada tramo, "faltantes" lista las oraciones del texto que son requisitos según estas definiciones y no están entre los ya encontrados, cada una con su "cita", copiada letra por letra del texto, y su "clase" ("formal" o "economico"). | D-03, D-12, D-14, D-15 |
| Un requisito ya encontrado está completo aunque junte varias condiciones: no lo repitas ni lo partas. | D-14 |
| Si una oración seguida del mismo asunto quedó fuera de un requisito ya encontrado, como la prórroga automática de un plazo, devolvela como faltante. | D-14, D-20 |
| Lo técnico no lo buscás. | D-02 |
| Si no falta nada, la lista va vacía. | D-15 |
| Salida, un objeto JSON con una propiedad por alias, y el esqueleto de la salida con marcadores (faltantes con cita y clase). | D-30 |

### matriz-union-v2

| Oración | Decisión |
|---|---|
| Una lectura de un pliego ya propuso las filas de la matriz, cada una con la oración que la exige. | D-14 |
| Por cada par de filas, decís si son un mismo requisito (una fila) o dos requisitos (dos filas). | D-14 |
| Cada par va entre [Pn] y [/Pn], con su documento, su ruta, a veces un «Encabezado:» que es solo contexto, la «Fila A» y la «Fila B». | D-15, D-30 |
| Hay dos clases de pares: dos filas seguidas del mismo punto, con lo que el pliego dice entre ellas si dice algo; o una fila del punto y una nota de una tabla que cuelga de ese punto, con el texto de la tabla que está antes de la nota. | D-14, D-31 |
| (Bloque `matriz-definiciones-v9`, por la marca) | D-30 |
| Es «una» cuando la fila B continúa o precisa lo que pide la fila A (el mismo documento, la misma declaración, la misma verificación o el mismo plazo) y sola no se entiende o no se evalúa por separado. | D-14, D-20 |
| También es «una» la nota de una tabla que agrega algo que se cumple con la misma declaración de la fila A. | D-14, D-31 |
| Es «dos» cuando cada fila pide algo que se puede cumplir sin la otra. | D-14, D-31 |
| Que las dos traten del mismo tema general no alcanza para unirlas. | D-14 |
| "razonamiento": una o dos oraciones, primero: qué pide cada fila y si es lo mismo. | D-30 |
| "filas": "una" o "dos". | D-14 |
| Salida, un objeto JSON con una propiedad por alias, y el esqueleto de la salida con marcadores (razonamiento y filas de un par). | D-30 |

## Instrucciones de T-280

### matriz-filtro-v10

| Oración | Decisión |
|---|---|
| (pendiente: T-280) | (pendiente) |

### matriz-consecuencias-v3

| Oración | Decisión |
|---|---|
| (pendiente: T-280) | (pendiente) |

### matriz-circulares-v8

| Oración | Decisión |
|---|---|
| (pendiente: T-280) | (pendiente) |

### matriz-circulares-cambios-v7

| Oración | Decisión |
|---|---|
| (pendiente: T-280) | (pendiente) |

### matriz-respaldo-v3

| Oración | Decisión |
|---|---|
| (pendiente: T-280) | (pendiente) |

## Instrucciones de T-281

### evaluacion-v13

| Oración | Decisión |
|---|---|
| (pendiente: T-281) | (pendiente) |

### contraste-v5

| Oración | Decisión |
|---|---|
| (pendiente: T-281) | (pendiente) |

### clausulas-v6

| Oración | Decisión |
|---|---|
| (pendiente: T-281) | (pendiente) |

### reescritura-v3

| Oración | Decisión |
|---|---|
| (pendiente: T-281) | (pendiente) |

## Instrucciones de T-282

### vision-v5

| Oración | Decisión |
|---|---|
| (pendiente: T-282) | (pendiente) |

### ficha-v4

| Oración | Decisión |
|---|---|
| (pendiente: T-282) | (pendiente) |

### ficha-renglon-v6

| Oración | Decisión |
|---|---|
| (pendiente: T-282) | (pendiente) |

### informe-tecnico-v3

| Oración | Decisión |
|---|---|
| (pendiente: T-282) | (pendiente) |

### oferente-nombre-v3

| Oración | Decisión |
|---|---|
| (pendiente: T-282) | (pendiente) |

### procedimiento-datos-v3

| Oración | Decisión |
|---|---|
| (pendiente: T-282) | (pendiente) |

### consulta-v5

| Oración | Decisión |
|---|---|
| (pendiente: T-282) | (pendiente) |

## Instrucciones de T-291

### matriz-externa-v1

| Oración | Decisión |
|---|---|
| (pendiente: T-291) | (pendiente) |
