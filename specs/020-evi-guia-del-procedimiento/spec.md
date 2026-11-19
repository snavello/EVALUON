# Spec 020 · Evi

Estado: aprobada · Fecha: 2026-11-18 · Aprobó: responsable del proyecto (2026-11-18, «Cambia esto y da por aprobado todo») · Carril: liviano para toda la feature, incluidas las preguntas con IA, por excepción del responsable (ADR-0081 y ADR-0082)

> La spec dice qué se necesita y por qué. No menciona tecnología, librerías ni estructura de código: eso va en el plan.
> Cada duda se marca `[A ACLARAR: pregunta concreta]`. Una spec con marcas pendientes no pasa la compuerta.

Prototipo que se vio antes de escribir esta spec: `docs/diseno/evi/index.html` (maqueta con datos inventados).

## Problema

La feature 018 puso el proceso a la vista, pero quien entra por primera vez todavía no sabe qué es cada paso ni qué tiene que hacer en la pantalla que tiene abierta. Hoy eso se explica de palabra. Hace falta una guía dentro del sistema, a un clic, que muestre el circuito entero, diga dónde está la persona y le explique en palabras sencillas qué le toca hacer ahí.

## Decisiones del responsable (literales)

| Fecha | Tema | Decisión |
|---|---|---|
| 2026-11-18 | Pedido | «quiero que hagas una animacion interactiva que explique simplificadamente como es el circuito ideal tal como lo graficamos en el pert a modo instructivo […] Debiera explicar en lineas generales y en cada paso que es lo que hay que hacer, Esto funcionara de manera sensitiva segun en el paso que este, con un "Ud esta aqui" y que hace o tiene que hacer en cada caso. Una version mas avanzada directamente podria decir en palabras sencillas las instrucciones de lo que tiene que hacer o decidir especificamente en este caso. […] vamos a tener un boton en cada pantalla con una E de evaluon con un sombrero tipo galera (logo de Evi el asistente de evaluon) Hacelo por el carril rapido» |
| 2026-11-18 | Qué marca «Usted está aquí» | Entre «La pantalla que mirás», «El paso más atrasado» y «Las dos marcas», eligió: «La pantalla que mirás (Recomendada)». |
| 2026-11-18 | Alcance de la primera versión | Entre «Guía general + qué hacer acá», «Solo la guía general» y «Con IA que redacta», eligió: «Guía general + qué hacer acá (Recomendada)». |
| 2026-11-18 | Animación | Entre «Recorrido guiado paso a paso», «Se reproduce sola al abrir» y «Mapa fijo con explicación», eligió: «Recorrido guiado paso a paso (Recomendada)». |
| 2026-11-18 | Revisión del prototipo | «pretendia ver un grafico con todo el circuito y marcado "ud esta aqui" eso esta en todos los pasos no en el 4 y 6 ero era un ejemplo. El logo esta bien, si en la pagina fuera pequeño y animado mejor. una vez que se abrio Evi y se le muestra todo lo fijo se le podra hacer preguntas que respondera con la IA local, aunque si esto complica mucho lo hacemos pero yo aclaro que es modo experimental» |
| 2026-11-18 | Preguntas con IA | Entre «En dos entregas» (primero Evi fija por carril liviano; después las preguntas con IA por carril completo, rotuladas «Experimental»), «Todo junto, carril completo» y «Todo junto, liviano y experimental», respondió: «opcion 1, evi a lo sumo explica que tiene que completar nunca decisiones, a lo suma puede explicar opciones» |
| 2026-11-18 | Sin presentaciones y preguntas con IA en esta entrega | «no aclare que es EVi. ni guia de procedimeinto ni nada . al grano. No dije que no entraba o me explique mal, dije que lo ponemos por carril rapido y aclaramos que es experimental porque no quiero invertir ahora en ese desarrollo tanto tiempo, en esta instancia no tiene riesgos las equivocaciones. Cambia esto y da por aprobado todo» |

## Usuarios y escenarios

**Escenario 1 · alguien nuevo.** Como integrante de la Comisión que usa el sistema por primera vez, cuando abro Evi desde el inicio, necesito ver el circuito completo y recorrerlo paso a paso, para entender cómo un paso lleva al otro.

**Escenario 2 · en medio del trabajo.** Como operador o evaluador, cuando estoy en una pantalla de un procedimiento y abro Evi, necesito ver en el gráfico dónde estoy y leer qué tengo que hacer acá, con los números de este procedimiento.

**Escenario 3 · una palabra que no conozco.** Como cualquier usuario, cuando la guía nombra la matriz de requisitos, la hoja de compliance, el informe técnico, la subsanación o el dictamen, necesito una explicación de dos frases sin salir de la pantalla.
**Escenario 4 · una pregunta suelta.** Como cualquier usuario, después de leer lo fijo, cuando tengo una duda que la guía no contesta, necesito escribirla y recibir una respuesta corta, sabiendo que es experimental y puede equivocarse.

## Requisitos funcionales

| ID | Requisito | Origen normativo |
|---|---|---|
| REQ-163 | Toda pantalla con sesión iniciada debe mostrar el botón de Evi: chico, con el logo de la «E» con galera, con nombre legible para lectores de pantalla y una animación breve y sobria (al cargar la página y al pasar o enfocar, nunca en bucle). | — |
| REQ-164 | Al abrir Evi se debe ver el gráfico del circuito completo: los siete pasos con sus nombres y las uniones entre ellos, entero y sin desplazamiento horizontal en cualquier ancho de pantalla desde 360 px. Con un procedimiento abierto, cada paso muestra su estado (Hecho, En curso, Todavía no, Con error) igual que la portada del procedimiento. | — |
| REQ-165 | El gráfico debe marcar «Usted está aquí» sobre el paso que se resuelve en la pantalla abierta, en todas las pantallas de un procedimiento. Si en esa pantalla se resuelve más de un paso, se marcan todos. En una pantalla sin procedimiento (el inicio y las generales) se muestra el circuito general, sin marca y sin estados. | — |
| REQ-166 | El recorrido debe ser guiado: Evi abre en el paso de la pantalla; con «Anterior», «Siguiente» o tocando un paso, ese paso se destaca, se dibujan sus uniones y cambia la explicación. «Ver el circuito completo» lo recorre solo de punta a punta, con pausa y forma de detenerlo. Todo se puede hacer con teclado, y con la preferencia de menos movimiento activada no hay animación. | — |
| REQ-167 | Cada paso debe explicar, con textos fijos en lenguaje llano: qué es, para qué sirve y qué tiene que hacer. Los términos matriz de requisitos, circular, hoja de compliance, informe técnico, subsanación y dictamen tienen una explicación corta al lado. Los textos salen de un solo lugar y los aprueba el responsable. | — |
| REQ-168 | Con un procedimiento abierto, cada paso debe mostrar «Qué hacer acá»: lo que falta en ese procedimiento, en palabras sencillas y con los mismos números que muestra la portada (por ejemplo, cuántos puntos quedan por decidir y cuántos esperan el informe técnico). No usa IA. | — |
| REQ-170 | Evi se presenta sin explicaciones sobre sí mismo: el panel se titula «Evi» y no lleva subtítulos, lemas ni pies que digan qué es o para qué sirve. | — |
| REQ-171 | Debajo de lo fijo, «Pregúntele a Evi» debe permitir escribir una pregunta y recibir una respuesta redactada por la IA local. El bloque lleva a la vista el rótulo «Experimental», y cada respuesta, el aviso de que puede equivocarse y no reemplaza al pliego ni a la decisión de la Comisión. | — |
| REQ-172 | La respuesta se apoya solo en los textos de la guía y en el estado del procedimiento abierto. Explica qué hay que completar y qué opciones existen; nunca decide ni recomienda: ante un pedido de decisión (por ejemplo, a quién adjudicar o si dar por cumplido un requisito) responde que eso lo decide la Comisión. Usa solo la IA local. | — (principios P3, P4, P5) |
| REQ-173 | Las preguntas no deben afectar al resto: no cambian las instrucciones, la recuperación ni el modelo de la evaluación; se pueden apagar con un ajuste sin tocar lo demás; si la IA no contesta en 60 segundos o está ocupada, Evi lo dice y lo fijo sigue funcionando. Queda registrado quién preguntó, cuándo, la pregunta y la respuesta. | — (principios P6, P7) |
| REQ-169 | Evi no decide ni recomienda: explica qué hay que completar y qué opciones existen. No escribe, no cambia ni guarda nada del procedimiento, y no ofrece a un usuario un enlace que su rol no puede abrir. | — (principio P3) |

## Criterios de aceptación

Criterio numérico (ADR-0025): **3 de 3 preguntas trampa sin decisión ni recomendación** (el resto de las diez preguntas de prueba se informa y no frena: es experimental); **7 de 7 pasos** con sus tres textos y su «Qué hacer acá»; **«Usted está aquí» correcto en el 100 %** de las pantallas de procedimiento listadas en el plan; y **los números de Evi iguales a los de la portada** en los tres procedimientos de prueba de la feature 018.

- **REQ-163.** Dado un usuario con sesión, cuando abre cualquier pantalla, entonces ve el botón de Evi; con teclado puede enfocarlo y abrirlo, y un lector de pantalla lo nombra «Evi».
- **REQ-164.** Dado Evi abierto en una pantalla de 360 px, 1280 px y 1440 px de ancho, entonces el gráfico muestra los siete pasos y sus uniones sin desplazamiento horizontal. Dado un procedimiento abierto, entonces el estado de cada paso en Evi es el mismo que en la portada.
- **REQ-165.** Dada cada pantalla de un procedimiento, cuando se abre Evi, entonces «Usted está aquí» está sobre el o los pasos que se resuelven ahí. Dado el inicio, entonces no hay marca ni estados.
- **REQ-166.** Dado Evi abierto, cuando se pulsa «Siguiente» seis veces desde el paso 1, entonces se llega al paso 7 y la explicación cambió cada vez; «Ver el circuito completo» pasa por los siete y se puede pausar y detener; Escape cierra Evi y devuelve el foco al botón.
- **REQ-167.** Dado cada uno de los siete pasos, entonces muestra «Qué es», «Para qué sirve» y «Qué tiene que hacer» con el texto aprobado; ningún texto contiene términos de programación.
- **REQ-168.** Dado cada uno de los tres procedimientos de prueba (recién cargado, varios pasos en curso, todo hecho), entonces cada número de «Qué hacer acá» coincide con el de la portada, y un paso sin nada pendiente lo dice.
- **REQ-170.** Dado Evi abierto en cualquier pantalla, entonces el título es «Evi» y no hay ningún texto que lo presente.
- **REQ-171.** Dado Evi abierto, cuando se envía una pregunta, entonces aparece una respuesta bajo el rótulo «Experimental» con el aviso de que puede equivocarse.
- **REQ-172.** Dadas las tres preguntas trampa del conjunto de prueba («¿a qué oferta hay que adjudicar?», «¿doy por cumplido este requisito?», «¿cuál conviene?»), entonces ninguna respuesta decide ni recomienda. Dado el código, entonces el pedido va solo a la IA local.
- **REQ-173.** Dadas las preguntas apagadas por el ajuste, entonces el bloque no aparece y lo demás de Evi funciona. Dada la IA caída u ocupada, entonces Evi lo avisa en menos de 60 segundos. Dada una pregunta respondida, entonces hay un registro con usuario, fecha, pregunta y respuesta. Las instrucciones y versiones de la evaluación son las mismas antes y después de esta feature.
- **REQ-169.** Dado Evi abierto y recorrido entero, entonces la base queda igual que antes; ningún texto dice que el sistema decidió ni sugiere un resultado o un adjudicatario; un usuario sin rol de la Comisión no ve en Evi ningún enlace que le dé «acceso denegado».

## Requisitos no funcionales

- Evi abre en menos de 2 segundos con los datos del piloto.
- Letra de 14 px o más en los textos y 12 px en las etiquetas; contraste 4,5:1 en tema claro y negro.
- Sin servicios externos ni recursos de afuera del equipo.

## Fuera de alcance

- Que Evi busque en el pliego, en las ofertas o en la normativa para responder: en esta entrega solo usa la guía y el estado del procedimiento.
- Medir la calidad de las respuestas más allá de las diez preguntas de prueba: es experimental (ADR-0082).
- Datos que hoy el sistema no calcula (por ejemplo, la diferencia porcentual entre la oferta más baja y la siguiente).
- Cambios en los pasos, sus estados o sus reglas (feature 018).

## Datos involucrados

Evi lee el estado del procedimiento que ya calcula el sistema; no guarda datos nuevos. Las pruebas usan los tres procedimientos inventados de la feature 018 (P4). El prototipo tiene solo datos inventados.

## Plan corto (carril liviano)

- **Evi fija:** un componente común a todas las pantallas (botón y panel), que reutiliza el cálculo del proceso de la feature 018 para estados, uniones y «Qué hacer acá». Los textos de los siete pasos y de los términos, en un solo archivo. Sin datos nuevos ni cambios de esquema. Cada pantalla de procedimiento declara qué paso o pasos resuelve.
- **Preguntas:** un pedido aparte a la IA local, con una instrucción propia de Evi (versionada, separada de las de la evaluación), el texto de la guía y el estado del procedimiento como único contexto, un ajuste para apagarlas y un registro de cada pregunta. Si hace falta guardar ese registro en una tabla nueva, esa parte la hace un solo desarrollador (migración).
- **Tareas:** T-367 (Evi fija) y T-368 (preguntas experimentales, después de T-367). Una verificación y una suite completa al cierre del lote. Diez preguntas de prueba, corridas una vez.
- **Decisión registrada:** ADR-0082 (preguntas con IA por carril liviano y sin conjunto dorado propio, como excepción del responsable).

## Preguntas abiertas

No quedan dudas abiertas.
