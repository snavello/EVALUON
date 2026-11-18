# ADR-0080 · Mapa del proceso: tarjetas de HTML y conectores SVG con geometría constante

Estado: aceptado · Fecha: 2026-11-17 · Propuso: Planificador (plan 018) · Decidió: responsable del proyecto (2026-11-17, al aprobar el plan 018)

## Contexto

REQ-158 pide, en la portada de cada procedimiento, un grafo de los siete pasos: una tarjeta por paso (número, nombre, dato clave, estado escrito y tareas, hasta 3 y «+N más»), ocho líneas de dependencia (1→2, 2→4, 3→4, 3→5, 4→5, 4→6, 4→7, 6→7) llenas o punteadas según el estado del paso de origen, y una línea de plazos. Cada tarjeta y tarea son enlaces. Debe tener equivalente en texto, funcionar con teclado y verse bien en los dos temas. La maqueta (`a-grafo.html`) usa tarjetas posicionadas y un SVG con codos.

Restricciones: HTML del servidor y poco JavaScript, sin marco nuevo (ADR-0076); política de contenido `default-src 'self'` (sin `style=` ni scripts en línea); sin dependencias nuevas (P5); simplicidad (P10). El grafo es fijo (siempre los mismos siete nodos y ocho aristas): lo que cambia es el estado y las tareas, no la forma.

## Alternativas

### A. Tarjetas de HTML posicionadas con clases y un SVG de conectores cuya geometría es una constante del módulo (propuesta)
Las posiciones, el alto fijo de tarjeta y los ocho trazos están en `proceso/mapa.py`; la plantilla recorre esas constantes. Las tarjetas son elementos HTML (enlaces, texto real, foco, lector de pantalla) y el SVG es decorativo (`aria-hidden`). Se gana: ningún script; texto accesible y seleccionable; la geometría se prueba en Python (ninguna tarjeta tapa un conector); se parece a la maqueta. Se pierde: un grafo fijo (agregar un paso exige tocar las constantes); alto fijo de tarjeta, con texto recortado y el completo en la lista; la lectura de los codos no cambia con el tamaño de letra si el usuario la agranda (el lienzo hace scroll horizontal).

### B. Biblioteca de grafos en JavaScript (d3, dagre, mermaid o similar)
Se gana: distribución automática y manejo de tarjetas de alto variable. Se pierde: una dependencia nueva que fijar y alojar (P5), un marco de dibujo en el navegador (contradice ADR-0076), accesibilidad por reconstruir y nada de lo que el grafo fijo necesita.

### C. Todo dentro de un SVG (tarjetas incluidas)
Se gana: un solo lienzo y conectores siempre alineados. Se pierde: texto en SVG sin ajuste de línea (hay que medir y cortar a mano), enlaces y foco más frágiles, peor lectura con lector de pantalla.

### D. Cuadrícula de CSS con conectores hechos con bordes o pseudoelementos
Se gana: sin SVG. Se pierde: los codos entre filas distintas y las líneas que cruzan columnas (3→5, 4→7) no se resuelven bien con bordes; el resultado es más frágil que un trazo.

## Decisión

Se propone **A**. Alto fijo de tarjeta (240 px) con presupuesto de alto por componente; trazo calculado una vez al importar el módulo (salida por el borde derecho a `y + 28`, codo en el hueco entre columnas, entrada por el borde izquierdo); línea llena si el paso de origen está «Hecho», punteada si no. Posiciones por clases `pos-N` en la hoja de estilo (la política de contenido no admite `style=`), iguales a las constantes. Bajo 900 px de ancho el mapa se oculta y queda la lista de pasos, que siempre está en la página.

## Consecuencias

- Más fácil: probar la geometría sin navegador; cambiar un estilo o una posición es tocar una constante y su clase; el mapa y la lista leen el mismo cálculo.
- Más difícil: si algún día los pasos cambian de cantidad o de dependencias hay que redibujar las posiciones a mano; el texto de las tareas se recorta en la tarjeta (se ve completo en la lista y en el `title`).
- Para revertir: quitar `_mapa.html` y su hoja deja la portada con la lista de pasos y las acciones, que no dependen del mapa; pasar a B es reemplazar `_mapa.html` sin tocar el cálculo.

## Enmienda (2026-11-18, T-363): tarjetas a medida, cuatro columnas y geometría en función del contenido

El responsable, al ver el mapa real, eligió «tarjetas más anchas y a medida» y pidió que se lea de izquierda a derecha y de arriba abajo. Se cambia, sin cambiar la alternativa elegida (A: tarjetas de HTML y conectores SVG):

- **Alto de tarjeta variable.** Las tarjetas miden 252 px de ancho y lo que ocupe su contenido; las tareas, el dato y el nombre se leen enteros (sin recorte). Los conectores siguen entrando y saliendo a 24 px del borde superior, por lo que el alto variable no los mueve.
- **Cuatro columnas y dos filas** en lugar de cinco columnas: arriba 1, 2, 4 y 6; abajo 3, 5 y 7 (Dictamen termina abajo a la derecha). Con cinco columnas de ~200 px, una tarea de 74 caracteres ocupaba tres líneas. 3→5 pasa por debajo de la tarjeta 2; 3→4 y 4→7 son codos por el hueco que precede a su destino; 4→5 y 6→7 son lazos de la misma columna por el hueco de la derecha (4→5 y 4→7 comparten el tronco y se bifurcan).
- **La geometría deja de ser una constante única.** Es una función determinista del contenido: `mapa.alto_estimado` calcula, en el servidor, con anchos de letra medidos en Chrome y aumentados 3 %, un alto que es siempre mayor o igual que el real; la fila de arriba y la de abajo se redondean al próximo de una lista corta de escalones (`ESCALONES`, de 24 en 24). Cada par de escalones es un par de clases del lienzo (`fila-b-N`, `alto-b-N`) que fija dónde empieza la fila de abajo y cuánto mide el lienzo, y `mapa.geometria(k, m)` calcula el `d` de cada conector para ese par (es un atributo, no un estilo). Los tests prueban cada par: ninguna tarjeta se superpone y ningún conector cruza una tarjeta ni su texto; y una medición en Chrome compara el alto real con el estimado en todos los casos.
- **Consecuencia:** quitar el recorte cuesta un lienzo de alto variable (de ~320 a ~700 px según el contenido, antes 740 fijos) y una estimación que mantener junto a `mapa.css` (un test recalcula el alto máximo desde la hoja). Si el texto estimado supera el último escalón, la tarjeta puede pisar la fila de abajo: hoy no ocurre porque una tarjeta muestra hasta tres tareas.

### Segunda parte de la enmienda (T-363, tras la verificación): fallar seguro

La verificación mostró que «el alto real nunca supera al estimado» no se sostiene con otra tipografía, letra agrandada, emojis o textos larguísimos. Se agrega, sin cambiar la disposición aprobada:

- **Estimación más honesta.** Los anchos de letra se midieron en Chrome con la fuente de la aplicación ya cargada (la primera tabla se midió con la de respaldo y quedó corta), con 8 % de margen por carácter, un ancho de sobra para lo desconocido (emojis incluidos) y una línea de tarea (14 px) de holgura por tarjeta. Un test fija el estimado contra altos reales medidos una vez en Chrome para 43 textos difíciles.
- **Red de seguridad en la hoja, que no depende de la estimación.** Cada tarjeta tiene como alto máximo el escalón de su fila (`--alto-a` arriba, `--alto-b` abajo, fijados por las clases del lienzo) y es una columna con corte propio: las tareas que no entran pasan a una segunda columna oculta, de modo que se corta entre tarea y tarea y nunca a media línea; «+ N más» y las advertencias no se cortan. Lo peor que puede pasar con otra tipografía o un texto enorme es que una tarjeta muestre menos y mande a la lista: nunca se pisan, ni salen del lienzo ni tapan un conector. Si el alto estimado pasa del último escalón, la tarjeta lo dice con «Ver todo en la lista» (enlace a `#paso-N`).
- **Tope de largo en la tarjeta.** Una tarea o el dato muy largos (errores de etapa, por ejemplo) se acortan con «…» (110 y 90 caracteres); el texto completo queda en el `title` y en la lista de pasos.
- **4→5 y 4→7 con troncos separados** 8 px (antes compartían el tronco y se leían como una flecha doble entre 5 y 7); sus codos son de radio 4.

