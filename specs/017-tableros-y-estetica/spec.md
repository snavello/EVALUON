# Spec 017 · Tableros de primer nivel y estética nueva

Estado: aprobada · Fecha: 2026-10-21 · Aprobó: responsable del proyecto (2026-10-21 21:32, «Apruebo la spec 017. Seguí con el plan.»)

> La spec dice qué se necesita y por qué. No menciona tecnología, librerías ni estructura de código: eso va en el plan.
> Las dudas se marcan como «a aclarar» hasta que el responsable las responde. Una spec con dudas pendientes no pasa la compuerta.

## Problema

La aplicación por secciones (feature 014) ordenó el trabajo en cinco secciones, pero cada sección abre directo en el detalle: tablas largas, documentos y formularios. Quien entra no ve de un vistazo qué es lo importante, qué falta, cuánto cotizó cada oferta ni qué plazo vence. La estética actual (azul, beige y títulos condensados) tampoco es la que el responsable quiere mostrar.

El 2026-10-21 el responsable recorrió tres rondas de maquetas (20 propuestas, 8 con la skill impeccable y 5 con tableros) y eligió un formato: cada sección abre con un tablero de información agregada, y el detalle se despliega debajo del mosaico que se toca. Pidió además un selector de tema claro u oscuro, una foto con datos en el ingreso, fotos propias en el perfil y un indicador de avance para los procesos largos, todo implementable en 8000 sin mayores complejidades.

Sin esto, la Comisión tiene que recorrer cada sección para saber qué hacer, y el producto no se muestra como el responsable lo quiere mostrar.

## Decisiones del responsable (literales)

| Fecha | Tema | Decisión |
|---|---|---|
| 2026-10-21 | Pedido inicial | «Vamos a empezar a trabajar un poco la ui y la estetica. Vas agregar algunas animaciones cuando pasamos de opcion con efecto pasar pagina, que podes armar com las animaciones de emil kovalski. TEmbien vamos a trabajar una imagen de marca y colores nuevos con con la skill de impeccable que ya tengo instalada.» |
| 2026-10-21 | Ronda 2 | «instala impeccable y hace versiones nuevas» |
| 2026-10-21 | Ronda 3 | «hace una como el formato jacaranda pero en contrastes de negros grises y blanco, como la pagina de tesla mas un color verde limon para resaltadps. Los graficos pueden contener colores aunque ligeramente desaturado. Con estas especificaciones varia que datos van al dashboard oficial y podes hacer combinaciones y en alguna una foto blanco y negro o color papel . HAce 5 en total y pasamos a migrar la pagina real si me gusta. Lo que me muestre debera ser capaz de implementarse sin mayores complejidades en 8000. La idea general es tener un primer nivel de cada menu con informacion agregada y luego on click se abre o usa otra ventana» |
| 2026-10-21 | Elección y alcance | «El detalle Se despliega debajo del mosaico, Vamos a elegir default grafico del modelo la que tiene foto es decir el numero , pero la foto quisera que este mas chica 40 por ciento menos y que tenga algun dato arriba para que no quede solo decorativo. Quiero un pendiente de hacer general y despues uno en cada etapa. Un orden economico de las ofertas y plazos importantes. El primer panel sera como un ingreso a lo importante de todos. En el resto se pueden repetir o mostrar datos de la etapa. Elegido ya el formato de las pantallas, tendremos un pequeño selector en pantalla para pasar a Negro como el modelo 3 y a gris blanco como el modelo 1 . En todos los casos procura siempre que se sepa el camino, que hay y que falta hacer o completar. Cuando haya foto ingresaran con una sutil animacion y tendremos un pequeño crud para subir fotos que tomara al azar y solo cambian al cambiar de pantalla. todas las que subamos las transformaras para que tengan la misma tonalidad, saturacion, temperatura, brillo contraste etc para que no quede desfasada la imagen. podemos ponerlo como una opcion del perfil para tener un gesto amable con los usuarios que por ejemplo puedan usar el sistema con una foto de un ser querido. limite 10 cada uno . Cuando haya procesos ejecutando tareas largas tenes que dejar algo que marque avance acorde con la estetica . Vamos al desarrollo ! Alguna duda ?» |
| 2026-10-21 | Marca | «Marca: mantenemos el logotipo aprobado el 13/10 (EVALU ON vidrio), recoloreado a negro, gris y lima.» |
| 2026-10-21 | Tono de las fotos | «acepto recomendacion», sobre la recomendación del Coordinador: blanco y negro para todas las fotos. |
| 2026-10-21 | Foto y primer panel | «si solo en la primer panel . la foto tiene que ser un fondo muy suave casi etereo pero que se note. si hay lugar principales datos de procedimiento. No de normativa esa actua como soporte estatico». Lectura del Coordinador, a confirmar al aprobar: el primer panel es el ingreso de un procedimiento (no una portada de todos), con sus datos principales sobre la foto y sin datos de normativa. |

Referencias: maquetas de la exploración en `docs/diseno/exploracion-ui/` (ronda 3: modelos 1, 2 y 3) y maqueta de esta feature en `docs/diseno/mockup-017/index.html`, que reúne lo elegido.

## Usuarios y escenarios

**Escenario 1 · Entrar a un procedimiento.** Como evaluador, cuando abro un procedimiento, necesito ver en una sola pantalla lo pendiente de todas las secciones, el orden económico de las ofertas y los plazos que vencen, para saber qué hacer primero sin recorrer las cinco secciones.

**Escenario 2 · Trabajar en una sección.** Como evaluador, cuando entro a Ofertas, necesito ver qué hay, qué falta y lo pendiente de esa sección, y abrir el detalle de un dato (por ejemplo, la comparación de las tres ofertas) debajo de su mosaico, sin perder el resto del tablero.

**Escenario 3 · Elegir el tema.** Como evaluador que trabaja muchas horas, quiero pasar la pantalla a negro o volver a gris y blanco con un selector chico, y que la aplicación recuerde mi elección.

**Escenario 4 · Mis fotos.** Como usuario, quiero subir hasta 10 fotos propias (por ejemplo, de un ser querido) para que aparezcan en el ingreso, con el mismo tono que el resto de la pantalla, y quitarlas cuando quiera.

**Escenario 5 · Esperar un proceso largo.** Como evaluador, cuando el sistema evalúa las ofertas o lee un documento largo, quiero ver cuánto avanzó, en qué paso está y los últimos pasos, desde cualquier sección.

## Requisitos funcionales

| ID | Requisito | Origen normativo |
|---|---|---|
| REQ-126 | Cada una de las cinco secciones abre con un tablero de primer nivel: mosaicos con información agregada (cifras grandes y gráficos), cada uno con un detalle. | — |
| REQ-127 | Al tocar un mosaico, su detalle se despliega debajo de la fila del mosaico, en la misma pantalla; al tocarlo de nuevo se pliega. Solo un detalle abierto a la vez. | — |
| REQ-128 | El primer panel (sección Procedimiento) es el ingreso a lo importante del procedimiento: sus datos principales (objeto, número, expediente, fecha de autorización, monto estimado, cantidad de ofertas, la más baja, avance, días hasta el vencimiento del mantenimiento y cantidad de pendientes), el pendiente general, el orden económico de las ofertas y los plazos importantes. La normativa no aparece en el primer panel: actúa como soporte estático y se consulta en su sección. Es el ingreso de un procedimiento, no una portada de todos los procedimientos. | — |
| REQ-129 | Hay un pendiente general en el primer panel, con todo lo que falta hacer en las cinco secciones, y un pendiente propio en cada sección. Cada pendiente dice qué falta, por qué importa, en qué sección está y tiene su acción a mano (aprobar, tomar del Portal, subir, responder, decidir). | — |
| REQ-130 | El orden económico muestra las ofertas de menor a mayor total, el monto estimado y cuánto se aparta cada una de la más baja y del estimado. | Pliego del procedimiento |
| REQ-131 | Los plazos importantes muestran al menos la apertura, el día de hoy, el vencimiento del mantenimiento de las ofertas y el dictamen de la Comisión, con lo que ya pasó, lo de hoy y lo que viene. | Pliego del procedimiento (plazo de mantenimiento) |
| REQ-132 | Siempre se sabe el camino: un recorrido arriba (Procedimientos › procedimiento › sección) y, en cada sección, una línea con qué hay y qué falta completar. Las pestañas muestran cuántos pendientes tiene cada sección. | — |
| REQ-133 | La estética sigue el modelo 2 de la ronda 3: negro, grises y blanco, verde lima solo para resaltar, cifras grandes, gráficos en colores levemente desaturados y pestañas en píldora. Los estados de cumplimiento siguen siendo íconos de color con forma propia y el nombre al pasar el mouse (guía visual, decisión del 2026-10-07). | — |
| REQ-134 | Un selector chico en el encabezado pasa la pantalla a negro (modelo 3) o a gris y blanco (modelo 1). La elección queda guardada en el perfil del usuario y vale en cualquier equipo. El tema de inicio es gris y blanco. | — |
| REQ-135 | La foto aparece solo en el primer panel, como fondo muy suave, casi etéreo, pero que se note, detrás de los datos principales del procedimiento. Ocupa a lo sumo el 60 % del ancho que ocupaba en el modelo 2 (un 40 % menos) y se funde con el fondo del panel. | — |
| REQ-136 | Cada usuario tiene en su perfil «Mis fotos»: sube, ve y quita hasta 10 fotos. Si no tiene fotos propias, se muestra la foto de la casa. Las fotos quedan en el equipo, las ve solo su dueño y nunca van al repositorio ni a un servicio externo. | P4, P5 (constitución) |
| REQ-137 | Al subir una foto, el sistema la ajusta para que todas tengan el mismo tono, saturación, temperatura, brillo y contraste: todas quedan en blanco y negro, con el mismo brillo medio y el mismo contraste que la foto de la casa. | — |
| REQ-138 | La foto se elige al azar entre las del usuario y cambia solo al cambiar de pantalla, nunca mientras se está en ella. Entra con una animación sutil. | — |
| REQ-139 | Al cambiar de sección, la pantalla pasa con efecto de hoja que gira. Con «reducir movimiento» activado en el equipo, el paso es un fundido corto. | — |
| REQ-140 | Mientras corre un proceso largo (evaluar ofertas, proponer la matriz, leer un documento, explorar el Portal), se ve su avance con la estética nueva: porcentaje, dónde va (por ejemplo, oferta 2 de 3, requisito 14 de 23) y los últimos pasos en lenguaje llano, en el primer panel y como indicador chico en el encabezado de todas las secciones. | REQ-067 (feature 013) |
| REQ-141 | Los tableros muestran solo datos que el sistema tiene; lo que todavía no existe se muestra como «falta» o «pendiente», nunca con un valor inventado. Toda propuesta del sistema sigue mostrando su fundamento (P3). | P3 (constitución) |
| REQ-142 | La marca sigue siendo el logotipo «EVALU ON» y el isotipo «E + on» aprobados el 2026-10-13, con la misma forma, el efecto vidrio y el halo, recoloreados a la estética nueva: en el tema gris y blanco, la placa EVALU en negro y la de ON en verde lima; en el tema negro, la placa EVALU en gris y la de ON en verde lima. El encabezado muestra la versión del tema elegido y la pestaña del navegador lleva el isotipo. Archivos: `docs/diseno/marca/017/`. | — |

Se mantienen sin cambios las funciones de la feature 014 (REQ-075 a REQ-099). REQ-133 reemplaza a REQ-100 (guía visual) y REQ-142 enmienda a REQ-108 (marca).

## Criterios de aceptación

Criterio numérico de la feature (ADR-0025): en los dos temas, el 100 % de los pares de texto y fondo cumple contraste WCAG AA (4,5:1 en texto, 3:1 en íconos y gráficos), y las cinco secciones abren con su tablero en 2 segundos o menos con un procedimiento real de la base del piloto.

- **REQ-126.** Dado un procedimiento con sus cinco secciones cargadas, cuando entro a cualquier sección, entonces lo primero que veo es su tablero de mosaicos, y cada mosaico abre un detalle.
- **REQ-127.** Dado el tablero de Ofertas, cuando toco «Ofertas del acta», entonces la comparación de las tres ofertas se despliega debajo de esa fila en 0,4 segundos o menos; cuando toco otro mosaico, el primero se pliega.
- **REQ-128.** Dado el caso de muestra, cuando abro el procedimiento, entonces veo en el primer panel los datos principales sobre la foto, el pendiente general, el orden económico y los plazos, sin desplazarme más de dos pantallas en un monitor de 1440 × 900, y ningún dato de normativa.
- **REQ-129.** Dado un pendiente «Aprobar el dictamen publicado en el Portal», cuando lo apruebo desde el pendiente general, entonces desaparece del pendiente general y del de Evaluación, el contador de la pestaña baja en uno y queda registrado quién lo aprobó y cuándo.
- **REQ-130.** Dadas tres ofertas, cuando miro el orden económico, entonces están de menor a mayor, la más baja resaltada, y cada una muestra su diferencia porcentual con el estimado y con la más baja.
- **REQ-131.** Dada una apertura del 22/09/2026 y un mantenimiento de 60 días, cuando miro los plazos el 21/10/2026, entonces veo «21/11 · vence el mantenimiento de las ofertas» y «faltan 31 días».
- **REQ-132.** Dada cualquier pantalla, cuando la miro, entonces veo el recorrido (Procedimientos › procedimiento › sección) y la línea «Hay: … · Falta: …» de esa sección.
- **REQ-133.** Dada la guía visual nueva, cuando reviso las cinco secciones en los dos temas, entonces el verde lima solo aparece en resaltados (pestaña activa, contadores, avance, lo más bajo, acción principal en negro) y los íconos de estado conservan su forma y su nombre al pasar el mouse.
- **REQ-134.** Dado que elegí negro en un equipo, cuando entro desde otro equipo con mi usuario, entonces la pantalla abre en negro.
- **REQ-135.** Dado el primer panel, cuando lo miro, entonces la foto se ve detrás de los datos principales, ocupa como máximo el 60 % del ancho del panel, y todos los datos encima de ella se leen con contraste de 4,5:1 o más en los dos temas; en las otras secciones no hay foto.
- **REQ-136.** Dado un usuario con 10 fotos, cuando intenta subir otra, entonces el sistema le pide quitar una antes; y ningún otro usuario ve sus fotos.
- **REQ-137.** Dadas dos fotos muy distintas (una oscura y saturada, otra clara y fría), cuando las subo, entonces las dos quedan en blanco y negro y su brillo medio y contraste difieren en 10 % o menos.
- **REQ-138.** Dado un usuario con 3 fotos, cuando paso de una sección a otra y vuelvo al primer panel, entonces la foto puede cambiar; si me quedo en la misma pantalla, no cambia.
- **REQ-139.** Dado el pase entre secciones, cuando cambio de sección, entonces la hoja gira en 0,5 segundos o menos; con «reducir movimiento», el cambio es un fundido de 0,15 segundos o menos.
- **REQ-140.** Dada una evaluación de ofertas en curso, cuando estoy en cualquier sección, entonces el indicador del encabezado muestra el porcentaje, y en el primer panel veo dónde va y los últimos 3 pasos, actualizados con la frecuencia del avance actual (10 segundos, REQ-067).
- **REQ-141.** Dado un procedimiento sin dictamen, cuando miro el tablero de Evaluación, entonces el mosaico dice «Pendiente» y no muestra un valor.
- **REQ-142.** Dado el encabezado, cuando cambio de tema, entonces el logotipo pasa de la versión negro y lima a la versión gris y lima, con la misma forma que el aprobado el 2026-10-13, y las letras se leen con contraste de 4,5:1 o más sobre su placa.

## Requisitos no funcionales

- Implementable en 8000 sobre las plantillas actuales, sin agregar un marco de interfaz nuevo (pedido del responsable: «sin mayores complejidades»).
- Tablero de una sección: 2 segundos o menos hasta verse completo, con un procedimiento real del piloto.
- Fotos: hasta 10 por usuario; cada una se guarda ajustada y con un tamaño máximo de 2 MB.
- Tipografías y fotos de la casa alojadas en el equipo (P4, P5).
- Uso completo con teclado; selector de tema y mosaicos accesibles con foco visible.

## Fuera de alcance

- Cambiar funciones de la feature 014 (cargas, Portal, matriz, evaluación, dictamen): solo cambia cómo se presentan.
- Compartir fotos entre usuarios o fotos institucionales cargadas por los usuarios.
- Un tercer tema o temas por procedimiento.
- Redactar el dictamen (sigue diferido, decisión del 2026-10-03).

## Datos involucrados

- Datos del procedimiento, pliego, ofertas, evaluación y normativa que ya existen en el sistema (públicos en la fase de construcción).
- Fotos personales de los usuarios: material privado. Quedan solo en el equipo, por usuario, nunca en el repositorio, en las pruebas ni en servicios externos (P4).
- Foto de la casa: biblioratos de Beatriz Pérez Moya en Unsplash, licencia Unsplash (uso libre), procesada en blanco y negro y en tono papel (`docs/diseno/mockup-017/img/CREDITOS.txt`).

## Preguntas abiertas

Ninguna. Las cuatro dudas se respondieron el 2026-10-21 (ver «Decisiones del responsable»).