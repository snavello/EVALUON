# ADR-0080 · Mapa del proceso: tarjetas de HTML y conectores SVG con geometría constante

Estado: propuesto · Fecha: 2026-11-17 · Propuso: Planificador (plan 018) · Decidió: —

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
