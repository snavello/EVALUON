# ADR-0046 · Organización de la aplicación por expediente (maqueta aprobada)

Estado: reemplazado en parte por el ADR-0047 (2026-10-07: puntos 1 a 3 y la maqueta de 24 pantallas) · Fecha: 2026-10-07 · Decidió: responsable del proyecto ("ok adelante", al ver la maqueta)

## Contexto

El responsable vio la matriz de cumplimiento y el recorrido desplegados y los encontró desordenados: "no se entiende, está todo mezclado, no respetan jerarquías". Pidió orden ("Normativa, pliego, ofertas, las matrices asociadas, las hojas de compliance, la evaluación de manera ordenada; que se sepa qué existe y qué no, qué se subió y qué falta"), un diseñador con sentido práctico y una maqueta antes de programar, con el diseño acordado en todas las pantallas.

## Decisión

Se adopta la organización de `docs/diseno/arquitectura-de-informacion.md` y la maqueta `docs/diseno/mockup/index.html`, con las recomendaciones de su tabla de opciones:
1. El procedimiento es el eje, con ocho partes en orden: Normativa, Pliego y circulares, Matriz de cumplimiento, Ofertas, Hojas de compliance, Informe técnico, Evaluación, Dictamen y cierre.
2. Portada del procedimiento: el estado del expediente (lista de control de qué hay, qué falta, origen Portal o a mano, pendientes, sugerencias y paso que sigue), que reemplaza al recorrido y a la página del procedimiento por separado.
3. Barra de etapas fija con estado y dos cuentas (pendientes y sugerencias); bandeja "Para decidir".
4. Misma jerarquía en cada pantalla: título, resumen, lo pendiente, el detalle y las acciones al pie.
5. Matriz de cumplimiento en tabla densa agrupada por tipo y sección, con filtros y filas que se abren con la cita.
6. Ofertas como cuadro de documentos exigidos por oferente; compliance e informe técnico en una pantalla; evaluación que abre con la conclusión; ventana del proceso como panel lateral.
7. Guía visual aprobada en todas las pantallas. Los cuatro íconos de estado se usan en todas, con el nombre propio de cada pantalla al pasar el mouse (aprobado).

## Consecuencias

- Se enmienda la spec 013 (o se abre una nueva) y se planifica la reorganización; se empieza por la matriz de cumplimiento.
- Toda pantalla nueva pasa por la maqueta antes de programarse, y el Coordinador la revisa en el navegador antes de mostrarla.
