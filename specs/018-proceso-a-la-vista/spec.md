# Spec 018 · El proceso a la vista

Estado: aprobada · Fecha: 2026-11-17 · Aprobó: responsable del proyecto (2026-11-17, «Si ok.  Los que vencen hoy marcamos el paso o  tarea  en lila 🟪 color  de alerta») · Enmienda: 2026-11-17, respuestas del responsable a las preguntas del plan (REQ-147, REQ-152, REQ-157 y reglas de estado)

> La spec dice qué se necesita y por qué. No menciona tecnología, librerías ni estructura de código: eso va en el plan.
> Cada duda se marca `[A ACLARAR: pregunta concreta]`. Una spec con marcas pendientes no pasa la compuerta.

## Problema

El responsable mostró el sistema a la Comisión Evaluadora. La demostración sirvió, pero a la Comisión le costó entenderlo. Lo que más costó fue no ver el proceso entero: cómo el pliego lleva a los requisitos, los requisitos a la revisión de cada oferta, y eso a la decisión y al dictamen.

El relevamiento del 2026-11-17 encontró por qué:

- La portada de un procedimiento cuenta cosas, no cuenta el proceso. Tiene 12 mosaicos del mismo peso y entre 35 y 40 piezas en la primera pantalla. Dice cuánto hay de cada cosa, pero no cómo está cada paso ni qué se puede hacer.
- Las cinco secciones ordenan por tipo de documento. La Comisión piensa en pasos. El avance se mide en «secciones listas» y una de ellas es Normativas.
- El cumplimiento por oferta aparece con cuatro nombres en tres secciones («Fichas de las ofertas», «Hojas de compliance», «Cumplimiento por tipo y oferta», «Propuesta por oferta y requisito»). «Matriz de cumplimiento» nombra en realidad la lista de requisitos del pliego.
- Lo mismo aparece varias veces: el orden económico en tres lugares; resultado, descartes y preguntas en dos.
- No hay una pantalla de inicio: al entrar se abre el último procedimiento visto. La lista de procedimientos se llama «Expedientes».
- Para ver lo que pide el pliego al lado de lo que trajo una oferta hay que llegar a una página que está a tres clics.

Sin esto, quien entra no sabe cómo está el procedimiento ni qué le toca, y el sistema se percibe como un tablero de cifras y no como una ayuda para evaluar.

## Decisiones del responsable (literales)

| Fecha | Tema | Decisión |
|---|---|---|
| 2026-11-17 | Pedido | «Necesito que evalues muy bien el sistema desde el punto de vista de lo operativo,  aun resulta poco claro el proceso por la abundancia de informacion y la falta de una vision ingrada del proceso de publicacion del pliego, matriz de requerimientos, matrices de cumplimiento , recepcion de ofertas analisis, comparacion y evaluacion entre pliego, e informe final . Evalua solo la exposicion sin variar aun componentes centrales . Creo que el tablero de inicio no es suficientemente representativo del procediemiento y solo seria una aplicacion mas , no necesariamente la portada o al menos no asi.» |
| 2026-11-17 | La demostración | «Ya hice una demostracion y si bien resulto util claramente les resulto dificil de entender.» |
| 2026-11-17 | Qué costó más | Ante la pregunta del Coordinador, eligió: «No ver el proceso entero». |
| 2026-11-17 | El estado no es un solo paso | «me parece bien tu propuesta, pero una aclaracion un procedimeiento , si bien hay precedencias, puede que haya operaciones que se realicen en simultaneo por lo que el estado no es en un solo paso sino una foto de como esta cada paso.» |
| 2026-11-17 | Elección | «Si, seguí con esa propuesta e a cuadro de c». Lectura del Coordinador: la opción E como inicio de la aplicación, la opción A como portada de cada procedimiento y el cuadro de la opción C dentro de los pasos de cumplimiento y evaluación. |
| 2026-11-17 | Circulares | Ante la pregunta «¿las circulares se muestran en el paso 1, "Pliego publicado"?», respondió: «Si 1». |
| 2026-11-17 | Informe técnico del área | Ante la pregunta «¿va en el paso 4, "Cumplimiento de cada oferta", o en el paso 6, "Evaluación de la Comisión"?», respondió: «Paso 4». |
| 2026-11-17 | Comparación de ofertas | Ante la pregunta «¿cuándo se da por hecha la "Comparación de ofertas"?», respondió: «Con el cumplimiento hecho». |
| 2026-11-17 | Acciones en el inicio | Ante la pregunta «¿cuántas acciones muestra "Para hoy" y en qué orden?», respondió: «Todas, que sea posible colapsar  y expandir un procedimiento». Lectura del Coordinador, a confirmar al aprobar: no hay un bloque «Para hoy» aparte; la lista de procedimientos es una sola y cada procedimiento se expande para mostrar sus acciones. Los procedimientos se ordenan por el vencimiento más próximo y abren expandidos. |
| 2026-11-17 | Procedimientos terminados | Ante las opciones «1. cuando se carga el dictamen» y «2. lo archiva una persona a mano», respondió: «Opción 1». |
| 2026-11-17 | Aprobación y vence hoy | Ante el pedido de aprobación con la lectura del Coordinador sobre el inicio, respondió: «Si ok.  Los que vencen hoy marcamos el paso o  tarea  en lila 🟪 color  de alerta». Lectura del Coordinador: el lila marca solo lo que vence hoy; lo que vence en los próximos días y lo ya vencido se muestran con su fecha y su texto, sin lila. Los vencimientos que el sistema conoce hoy son la apertura, el mantenimiento de las ofertas y el dictamen (REQ-131). El lila ya se usa en el cuadro de cumplimiento para el estado «externo»: el plan resuelve que no se confundan. |
| 2026-11-17 | Qué es «A decidir» (pregunta del plan) | Entre «1. Solo los no determinados» y «2. Todo lo sin confirmar», eligió: «1». Las acciones del paso 6 se parten en «Decidir N puntos», «Revisar N "no cumple"» y «Confirmar N propuestas "cumple"». |
| 2026-11-17 | Qué entra en «Qué se puede hacer ahora» (pregunta del plan) | Entre «1. Sí, siete acciones de cierre», «2. Solo los pendientes de hoy» y «3. Todo lo que falta», eligió: «3». |
| 2026-11-17 | Documentos y circulares sin revisar (pregunta del plan) | Entre «1. Lo deduce solo» (sin lectura, o no tenido en cuenta por la última evaluación; sin datos nuevos) y «2. Marca "revisado por"», eligió: «1». |
| 2026-11-17 | Paso que no empezó pero se puede empezar (pregunta del plan) | Entre «1. "En curso"» y «2. "Todavía no"», eligió: «1». «Todavía no» queda para lo que depende de otro paso; el dictamen espera a los pasos 4 y 6, salvo que el mantenimiento venza hoy o ya haya vencido. |
| 2026-11-17 | Requisito que no aplica a una oferta (pregunta del plan) | Entre «1. Mostrar "No aplica"» y «2. Dejar la celda vacía», eligió: «1». |
| 2026-11-17 | Lo ya vencido | Ante la pregunta «¿y lo que ya venció y sigue sin resolverse?», respondió: «Rojo brillante vencido». Reemplaza la lectura del Coordinador de que lo vencido iba sin color. |

Referencias: maquetas en `docs/diseno/exposicion-proceso/` (`index.html` con el diagnóstico y la comparación; `e.html`, `a.html` y `c.html` son las elegidas; `b.html` y `d.html` quedan como alternativas no elegidas).

## Usuarios y escenarios

**Escenario 1 · Entrar al sistema.** Como integrante de la Comisión, cuando entro, necesito ver todos los procedimientos abiertos con el estado de cada uno y lo que hay para hacer hoy, para elegir por dónde empezar.

**Escenario 2 · Abrir un procedimiento.** Como evaluador, cuando abro un procedimiento, necesito ver de un vistazo cómo está cada paso del proceso y qué se puede hacer ahora, aunque haya varios pasos en curso a la vez, para no tener que recorrer las cinco secciones.

**Escenario 3 · Un paso que se reabre.** Como evaluador, cuando llega una circular nueva o un documento por subsanación, necesito que el paso que ya estaba hecho vuelva a mostrarse en curso con lo que hay que revisar.

**Escenario 4 · Decidir con el pliego y la oferta a la vista.** Como evaluador, cuando el sistema no pudo concluir un punto, necesito ver en una misma pantalla qué pide el pliego, qué trajo la oferta y por qué el sistema dudó, para decidir y pasar al siguiente.

**Escenario 5 · Comparar las ofertas requisito por requisito.** Como evaluador, necesito un cuadro con los requisitos en filas y las ofertas en columnas, para ver qué cumple cada una y dónde falta decidir.

## Requisitos funcionales

| ID | Requisito | Origen normativo |
|---|---|---|
| REQ-143 | El proceso de un procedimiento se muestra en siete pasos, siempre con estos nombres y en este orden de lectura: 1 Pliego publicado, 2 Matriz de requisitos, 3 Ofertas recibidas, 4 Cumplimiento de cada oferta, 5 Comparación de ofertas, 6 Evaluación de la Comisión, 7 Dictamen. El número da el orden de lectura, no un orden obligatorio de trabajo. | — |
| REQ-144 | Cada paso tiene su propio estado, independiente del de los demás: «Hecho», «En curso», «Todavía no» o «Con error». Varios pasos pueden estar en curso a la vez. No existe un «paso actual» del procedimiento. | — |
| REQ-145 | El estado de cada paso se calcula con los datos que el sistema ya tiene; no se guarda una fase del procedimiento ni se pide a nadie que la marque. Un paso «Hecho» vuelve a «En curso» cuando aparece algo nuevo que le corresponde (por ejemplo, una circular modificatoria o un documento agregado a una oferta). | — |
| REQ-146 | La portada de un procedimiento muestra, en este orden: la foto de los siete pasos con su estado; la lista «Qué se puede hacer ahora»; y los siete pasos, cada uno con un resumen de una línea de lo que ya hay y, si está en curso, lo que le falta con su acción a mano. | — |
| REQ-147 | «Qué se puede hacer ahora» lista todo lo que falta y se puede hacer en cualquier paso: los pendientes que el sistema ya cuenta, las acciones de cierre (proponer y validar la matriz, tomar del Portal lo que falta, agregar las ofertas del acta, evaluar las ofertas, resolver un error, cargar el dictamen) y cada faltante que hoy muestra la línea «Hay / Falta» de las secciones. No hay orden obligatorio entre ellas; cada una dice a qué paso pertenece. Una acción que depende de otra todavía no hecha no aparece en la lista: el paso dice de qué depende. | — |
| REQ-148 | Los plazos importantes (REQ-131) se ven en la portada del procedimiento. El tablero de mosaicos del primer panel (REQ-128) deja de ser la portada y queda a un clic con el nombre «Indicadores», sin perder ningún dato. | — |
| REQ-149 | Las cinco secciones y sus tableros (features 014 y 017) se mantienen. Cada paso y cada acción de la portada llevan al lugar de la sección donde se resuelven. | — |
| REQ-150 | El inicio de la aplicación es la lista de procedimientos abiertos. Por cada uno muestra: nombre y número, el estado de los siete pasos, qué se puede hacer ahora y el vencimiento más próximo. Enmienda a REQ-128 solo en esto: entrar al sistema ya no abre el último procedimiento visto. Un procedimiento pasa solo a «Terminados» cuando su dictamen está cargado, y vuelve solo a la lista de abiertos si el dictamen se quita; no se guarda un estado final ni lo archiva una persona. | — |
| REQ-151 | El inicio muestra todas las acciones disponibles de todos los procedimientos abiertos, agrupadas por procedimiento. Cada procedimiento se puede colapsar y expandir: colapsado muestra su línea (REQ-150) y cuántas acciones tiene; expandido lista sus acciones, cada una con un botón que lleva a resolverla. | — |
| REQ-152 | Hay un cuadro de cumplimiento: los requisitos de la matriz vigente en filas, agrupados por tipo, y las ofertas en columnas con su total. Cada celda muestra con texto uno de estos estados: «Cumple», «No cumple», «A decidir», «Espera informe», «Sin resultado» o «No aplica» (no cuenta en los totales). «A decidir» es solo lo que el sistema no pudo concluir (no determinado); un «Cumple» o «No cumple» propuesto que ninguna persona confirmó conserva su texto con la leyenda «sin confirmar». Al pie, cuántos requisitos cumple cada oferta hasta ahora. Se llega desde los pasos 4 y 6. | — |
| REQ-153 | El cuadro se puede filtrar por: todos, con algo pendiente, a decidir, no cumple y los que esperan informe técnico. Un grupo donde todas las ofertas cumplen todo se muestra resumido en una línea. | — |
| REQ-154 | Al tocar una celda se ve, sin salir del cuadro: qué pide el pliego (texto y dónde está), qué trajo esa oferta (texto y dónde está), por qué el sistema propone lo que propone, y las mismas acciones de decisión que existen hoy. Desde ahí se pasa al siguiente punto a decidir. | P3 (constitución) |
| REQ-155 | Vocabulario único en pantalla: «Procedimientos» (no «Expedientes») para la lista; «Matriz de requisitos» para la lista de lo que pide el pliego; «Cuadro de cumplimiento» para requisitos por ofertas. Los nombres de los siete pasos no cambian de una pantalla a otra. | — |
| REQ-156 | Todo estado se muestra con texto además del color, en los dos temas (claro y negro). | — |
| REQ-157 | Lo que vence hoy se marca en lila, el color de alerta, con el texto «Vence hoy»: el paso o la acción a la que pertenece el vencimiento, en el inicio y en la portada del procedimiento. En esas pantallas el lila no se usa para ninguna otra cosa. Lo que ya venció y sigue sin resolverse se marca en rojo brillante con el texto «Vencido», hasta que se resuelva. | — |

Se mantienen sin cambios las funciones de las features 004, 008, 012, 014 y 016 y los requisitos de la 017 no enmendados arriba. Qué entra en cada paso:

| Paso | Qué reúne | Está «Hecho» cuando |
|---|---|---|
| 1 Pliego publicado | Datos del procedimiento, pliego, anexos y circulares (se muestran en este paso aunque hoy se carguen en la sección Ofertas) | El pliego está cargado y leído y no hay circulares sin revisar |
| 2 Matriz de requisitos | Requisitos, sugerencias del sistema, versiones | La versión vigente está validada y no hay una circular modificatoria posterior a ella |
| 3 Ofertas recibidas | Ofertas del acta, sus documentos, fichas y hojas de compliance | Todas las ofertas del acta tienen sus documentos cargados y no hay documentos nuevos sin revisar |
| 4 Cumplimiento de cada oferta | La revisión del sistema de cada oferta contra cada requisito, y el informe técnico del área (es un insumo que destraba resultados, no una decisión de la Comisión) | Todas las ofertas están revisadas con la matriz vigente y ningún resultado espera el informe técnico |
| 5 Comparación de ofertas | Orden económico, la más baja y la más alta, cumplimiento por tipo | Todas las ofertas tienen su total y el paso 4 está «Hecho» con la matriz vigente. Con los totales cargados y el paso 4 incompleto queda «En curso» y dice que el orden económico está listo y falta completar el cumplimiento |
| 6 Evaluación de la Comisión | Puntos a decidir, «no cumple» a revisar, preguntas, subsanaciones, descartes | No quedan puntos a decidir, preguntas sin contestar ni descartes sin resolver |
| 7 Dictamen | Dictamen tomado del Portal o subido; exportar planilla y cuadro comparativo | El dictamen está cargado |

## Criterios de aceptación

Criterio numérico de la feature (ADR-0025), escrito antes de construir:

- Para tres procedimientos de prueba en situaciones distintas (recién cargado, con varios pasos en curso, con todo hecho), el estado de cada uno de los siete pasos coincide en el 100 % de los casos (21 de 21) con una tabla escrita a mano antes de programar.
- La lista «Qué se puede hacer ahora» coincide en el 100 % con lo que el sistema ya calcula para ese procedimiento: la suma de las líneas que vienen de pendientes es igual al contador de pendientes de hoy, y cada acción de cierre y cada faltante aparece si y solo si su condición se cumple. Ninguno de más y ninguno de menos.
- La primera pantalla de la portada de un procedimiento tiene 15 piezas o menos en un monitor de 1440 × 900 (hoy tiene entre 35 y 40). Si «Qué se puede hacer ahora» tiene más de 6 líneas, muestra las primeras 6 y un «ver las N restantes».
- De la portada a ver pliego y oferta lado a lado de un punto a decidir: 2 clics o menos (hoy 3 o más).

Por requisito:

- **REQ-143.** Dado cualquier procedimiento, cuando miro su portada, el inicio de la aplicación o el cuadro, entonces los pasos tienen los mismos siete nombres y el mismo orden.
- **REQ-144.** Dado un procedimiento con una oferta que recibió un documento nuevo, sin informe técnico y con 12 puntos a decidir, cuando abro su portada, entonces los pasos 3, 4 y 6 dicen «En curso» a la vez y ninguna pantalla dice «va por el paso N».
- **REQ-145.** Dado un procedimiento con la matriz validada (paso 2 «Hecho»), cuando se carga una circular modificatoria, entonces el paso 2 pasa a «En curso» y dice que hay una circular posterior a la matriz, sin que nadie lo marque. Y en la base no existe ningún dato nuevo que guarde la fase.
- **REQ-146.** Dado el procedimiento de la maqueta A, cuando abro su portada, entonces veo primero la foto de los siete pasos, después «Qué se puede hacer ahora» y después los siete pasos con su resumen; los pasos en curso muestran lo que falta con su enlace.
- **REQ-147.** Dado un procedimiento sin matriz validada y con ofertas cargadas, cuando miro «Qué se puede hacer ahora», entonces aparece «Validar la matriz» y no aparece ninguna acción de evaluación; el paso 4 dice «Todavía no: depende de la matriz de requisitos».
- **REQ-148.** Dada la portada, cuando toco «Abrir indicadores», entonces veo los mismos mosaicos y cifras que hoy muestra el primer panel.
- **REQ-149.** Dada la acción «Cargar el informe técnico del área» en la portada, cuando la toco, entonces llego al lugar de la sección Evaluación y dictamen donde se sube, sin pasos intermedios.
- **REQ-150.** Dado un usuario que la vez anterior dejó abierto un procedimiento, cuando entra al sistema, entonces ve la lista de procedimientos abiertos con el estado de los siete pasos de cada uno, y no ese procedimiento. Dado un procedimiento abierto, cuando se carga su dictamen, entonces deja la lista de abiertos y aparece en «Terminados».
- **REQ-151.** Dados cuatro procedimientos abiertos con 9 acciones disponibles entre todos, cuando entro, entonces veo las 9 agrupadas bajo su procedimiento; cuando colapso uno, quedan su línea y «N acciones», y cuando lo expando vuelven a verse; el botón de cada acción lleva a resolverla.
- **REQ-152.** Dado un procedimiento con 27 requisitos y 3 ofertas evaluadas, cuando abro el cuadro, entonces veo 27 filas en 3 grupos y 3 columnas, cada celda con su estado en texto, y al pie cuántos cumple cada oferta; los totales coinciden con los del mosaico «Resultado por oferta».
- **REQ-153.** Dado el cuadro anterior con 12 puntos a decidir, cuando elijo «A decidir», entonces solo quedan las filas que tienen al menos una celda «A decidir».
- **REQ-154.** Dada una celda «A decidir», cuando la toco, entonces veo en la misma pantalla el texto del pliego con su ubicación, el texto de la oferta con su ubicación y el motivo de la duda; cuando decido, queda registrado quién y cuándo como hoy, la celda cambia y puedo pasar al siguiente.
- **REQ-155.** Dadas todas las pantallas, cuando busco «Expedientes» o «Matriz de cumplimiento» como nombre de la lista de requisitos, entonces no aparecen.
- **REQ-156.** Dada cualquier marca de estado, cuando la miro en los dos temas, entonces tiene su nombre escrito y contraste de 4,5:1 o más.
- **REQ-157.** Dado un procedimiento cuyo mantenimiento de oferta vence hoy y al que le falta el dictamen, cuando miro el inicio y su portada, entonces el paso 7 y la acción «Cargar el dictamen» están en lila y dicen «Vence hoy»; al día siguiente, si sigue faltando, están en rojo brillante y dicen «Vencido». Dado un procedimiento sin vencimientos hoy, cuando lo miro, entonces no hay nada en lila.

## Requisitos no funcionales

- Inicio de la aplicación: 2 segundos o menos con 20 procedimientos abiertos.
- Portada de un procedimiento y cuadro de cumplimiento: 2 segundos o menos con un procedimiento real del piloto (hasta 60 requisitos y 10 ofertas).
- Sin datos nuevos guardados para el estado de los pasos (REQ-145).
- Implementable en 8000 sobre las plantillas actuales, sin un marco de interfaz nuevo, como la 017.
- Uso completo con teclado y foco visible.
- Corte vertical (ADR-0025): primero un procedimiento chico y público de punta a punta (portada con los siete pasos y cuadro), antes de los casos del piloto.

## Fuera de alcance

- Reemplazar las cinco pestañas por un riel de siete pasos (maqueta B). Se revisa si después de esta feature la Comisión sigue perdiéndose dentro de las secciones.
- Un informe o dictamen redactado por el sistema (maqueta D). Sigue diferido (decisión del 2026-10-03); se le muestra a la Comisión como pregunta.
- Acciones del inicio distintas para cada persona: requiere registrar quiénes integran la Comisión de cada procedimiento, que hoy no existe.
- Fecha límite de cada subsanación, orden de mérito como decisión registrada y estados finales del procedimiento (adjudicado, desierto).
- Cambios en cómo se arma la matriz, cómo se evalúa o qué se registra: solo cambia cómo se muestra.

## Datos involucrados

- Datos del procedimiento, pliego, ofertas y evaluación que ya existen en el sistema. Sin datos nuevos.
- Las maquetas usan un caso inventado (sin datos de procedimientos reales ni de personas). Las pruebas usan casos públicos o inventados (P4).

## Preguntas abiertas

Para el responsable, de a una:

1. REQ-151 · Acciones en el inicio: resuelta el 2026-11-17 (todas, por procedimiento, colapsable).
2. Paso 1 · Circulares: resuelta el 2026-11-17 (van en el paso 1).
3. Paso 4 · Informe técnico del área: resuelta el 2026-11-17 (va en el paso 4).
4. Paso 5 · Comparación de ofertas: resuelta el 2026-11-17 (hecha cuando el cumplimiento está hecho).
5. Procedimientos terminados: resuelta el 2026-11-17 (cuando se carga el dictamen).

No quedan dudas abiertas. El responsable confirmó al aprobar la lectura del Coordinador sobre las acciones en el inicio (ver «Decisiones del responsable»).
