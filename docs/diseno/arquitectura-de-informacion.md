# Arquitectura de información de EVALUON (propuesta)

Estado: propuesta para revisión del responsable · Fecha: 2026-10-07 · Mockup navegable: `docs/diseno/mockup/index.html` (abrir en el navegador, datos inventados).

Origen: pedido del responsable del 2026-10-07, después de ver la matriz de cumplimiento: ordenar la aplicación para que se vea qué existe y qué no, qué se subió y qué falta, con jerarquía clara (normativa, pliego, ofertas, matrices, hojas de compliance, evaluación). Se apoya en la guía visual aprobada (`docs/diseno/guia-visual.md`) y no cambia la lógica de ninguna feature: reorganiza cómo se presenta lo que el sistema ya registra (specs 001, 003, 008, 012, 004 y 013).

## 1. El problema de la versión actual

Revisado sobre las plantillas de `evaluon/templates/` (la aplicación no estaba corriendo al hacer este análisis).

### 1.1 No hay un eje: el procedimiento está repartido en pantallas sueltas

- La barra superior (`base.html`) ofrece **Consulta · Recorrido · Procedimientos · Importar del Portal**. "Recorrido" y "Procedimientos" llevan a dos páginas distintas del **mismo** procedimiento (`journey/procedure.html` y `tenders/procedure.html`), cada una con una parte de la información. El usuario tiene que saber cuál abrir.
- "Importar del Portal" es una sección global, separada del procedimiento, aunque la decisión del responsable es que el Portal sea **la primera fuente del procedimiento** (spec 013, REQ-071).
- La página del procedimiento (`tenders/procedure.html`) mezcla en una sola columna: datos del procedimiento, tabla de documentos del pliego, tramos pendientes de revisión de cada documento, el panel de la matriz y el formulario para cargar un documento. Las ofertas aparecen como un enlace suelto arriba; la evaluación no aparece.
- El recorrido (`journey/_stages.html`) tiene seis etapas: Datos del Portal, Pliego y circulares, Matriz, Ofertas, Evaluación, Matriz de evaluación. **Faltan como partes visibles** la normativa aplicable, las hojas de compliance, el informe técnico y el cierre (dictamen). Las hojas y el informe solo aparecen como cuentas dentro de "Evaluación".
- El estado de cada etapa se muestra con una pastilla de texto (`badge`), contra la decisión de la guía visual (íconos de color, sin pastillas).

### 1.2 La matriz de cumplimiento no respeta jerarquías

En `tenders/matrix.html` el orden de lectura es: botones Validar y Descartar → impresión → encabezado → resumen en viñetas → tramos pendientes → sugerencias → un botón "Confirmar los requisitos marcados" suelto → requisitos formales **y** económicos juntos → técnicos → quitados → formularios para agregar.

- **Las acciones van antes que el contenido.** "Validar" y "Descartar el borrador" están arriba, antes de ver un solo requisito; el botón de confirmar queda lejos de las casillas que confirma.
- **Cada requisito es una tarjeta completa**: cita literal abierta, cambios de circulares, respaldo normativo, panel de consecuencias, historial y formularios de corrección. Con 60 a 120 requisitos la página es un rollo de varios metros sin forma de ver el conjunto.
- **Formales y económicos van mezclados** en una misma sección; los grupos por tramo del pliego aparecen como encabezados intercalados entre tarjetas, con sus botones de grupo, y no se distinguen de un requisito.
- **No hay tabla, ni filtros, ni contadores por grupo.** El resumen es una lista de viñetas al principio; no se puede filtrar "solo lo que falta decidir" ni "solo económicos".
- **Marcas de distinto significado se ven iguales**: "Confirmado", "Agregado por una persona", "Devuelto de las descartadas" y "Agregado por la circular" usan la misma marca de texto.

### 1.3 La matriz de evaluación pone la conclusión al final

En `assessment/matrix.html`:

- Arriba se apilan hasta cinco avisos (propuesta del sistema, pedido hecho, ofertas sin documentos, evaluación en curso, versión de matriz) y el botón "Evaluar todas las ofertas", antes del resultado.
- La grilla muestra en cada celda texto largo ("No determinado: falta la hoja de compliance · ok de la Comisión al informe técnico (propuesto: …)") en lugar de un ícono; la fila del requisito dice solo "12 · Formal · renglón 3", sin el texto del requisito, y las filas no están agrupadas por tipo.
- La carga del informe técnico del área aparece en el medio de la evaluación, como un formulario más.
- El estado por oferta son párrafos de "etiqueta cuenta · etiqueta cuenta".
- **Descartes y orden económico, que son la conclusión, van al final de la página.**

### 1.4 Lo que falta en todas las pantallas

- No se distingue **lo que vino del Portal** de **lo que se subió a mano** (REQ-071).
- No hay una vista que diga, para todo el expediente, **qué existe, qué falta y qué espera decisión**.
- Las **sugerencias** del sistema y las **decisiones pendientes** se cuentan, pero no se ven juntas en un lugar con acceso directo (REQ-072).

## 2. Principios de la propuesta

1. **Un procedimiento es el eje.** Todo cuelga de él, en el orden en que la Comisión trabaja.
2. **Cada pantalla, la misma jerarquía:** título → resumen en una línea → lo pendiente arriba → el detalle después → las acciones de cierre (validar, confirmar) al final del bloque que cierran, nunca antes del contenido.
3. **Existe / falta / subido / pendiente** se ven siempre con las mismas cuatro marcas, en todas las partes.
4. **Origen visible:** cada documento y dato dice si vino del Portal o se subió a mano, con fecha.
5. **Pendientes y sugerencias, separados y ambos visibles** (decisión literal del responsable en la spec 013).
6. **Íconos de color con nombre al pasar el mouse**, sin pastillas (guía visual 2.2).
7. **El sistema propone, la Comisión decide** (P3): toda propuesta se rotula como tal; las acciones de decisión solo las ve el evaluador (REQ-069).

## 3. Organización: el procedimiento y sus ocho partes

Navegación de primer nivel (barra superior): **Procedimientos · Normativa · Consulta**. "Importar del Portal" deja de ser una sección: es el primer paso de "Nuevo procedimiento". "Recorrido" y "Procedimiento" se unen en una sola página: el **estado del expediente**.

Dentro de un procedimiento, una **barra de etapas** fija, debajo del encabezado del procedimiento, con las ocho partes en orden. Cada etapa muestra su ícono de estado, su nombre y, si los hay, dos contadores distintos: decisiones pendientes (rojo oscuro) y sugerencias (azul). La primera entrada de la barra es el **Expediente** (la lista de control).

| N.º | Parte | Qué existe | Qué puede faltar | Qué se subió (origen) | Qué espera decisión | Qué sugiere el sistema |
|---|---|---|---|---|---|---|
| 1 | **Normativa aplicable** | Régimen según la fecha de autorización (247/2022 o 297/03), marco nacional, complementarias, cada una validada o no | Normas sin cargar o sin validar; modificatorias pendientes (REQ-021) | Carga de normativa (feature 001), común a todos los procedimientos | Validar el informe de lectura de una norma nueva | Normas citadas por el pliego que no están cargadas |
| 2 | **Pliego y circulares** | Pliego particular, anexos, especificaciones, circulares y respuestas a consultas, con fecha y estado de lectura | Documentos que el Portal lista y no se bajaron; circulares nuevas detectadas | Portal (con fecha de consulta) o a mano | Aprobar lo importado; tramos ilegibles a revisar | Novedades del Portal para aprobar (REQ-050) |
| 3 | **Matriz de cumplimiento** | Requisitos formales, económicos y técnicos por renglón, con su cita; versión y quién la validó | Matriz sin pedir, sin validar o desactualizada por una circular | — (la propone el sistema) | Confirmar, corregir o quitar; tramos pendientes; consecuencias sin elegir; validar | Sugerencias de condición (REQ-035) y respaldo normativo |
| 4 | **Ofertas** | Cada oferta con su oferente, total, garantía y renglones cotizados; sus documentos con estado de lectura | Documentos exigidos por el pliego que no están; páginas ilegibles | Datos del Portal (acta de apertura, cotización) y documentos a mano | Aprobar lo importado; páginas ilegibles para revisar | Documento que parece faltar según la matriz |
| 5 | **Hojas de compliance** | Una hoja por oferta (REQ-073), con fecha y quién la subió | Hojas no subidas; requisitos externos a la espera | A mano (la sube la Comisión) | Subir la hoja | Lista de verificaciones externas que la hoja debe cubrir |
| 6 | **Informe técnico** | Informe del área requirente, por procedimiento o por oferta (REQ-074) | Informe no subido | A mano | Dar el ok a la propuesta apto / no apto por renglón | Apto o no apto por oferta y renglón, con cita del informe |
| 7 | **Evaluación** | Matriz de evaluación ofertas × requisitos, con descartes y orden económico | Ofertas sin evaluar; evaluación hecha con una versión vieja de la matriz | — (la propone el sistema) | Confirmar, corregir o rechazar; responder preguntas; decidir subsanaciones | Resultado por requisito, descartes y orden (REQ-059) |
| 8 | **Dictamen y cierre** | Resumen de lo decidido, listo para el acta | Decisiones abiertas que impiden cerrar | Dictamen publicado en el Portal (si existe) | Cerrar la evaluación | — (el borrador de acta está diferido, hoja de ruta) |

Estado de cada parte, con los íconos de la guía (mismo círculo, distinto símbolo, nombre al pasar el mouse):

| Estado de la parte | Ícono | Cuándo |
|---|---|---|
| Lista | tilde verde | Existe y no tiene nada pendiente |
| A decidir | signo de pregunta ámbar | Existe y tiene decisiones pendientes de la Comisión |
| Falta | cruz roja | Debería existir y no está (documento, hoja, informe) |
| Pendiente / en curso | reloj azul | Todavía no corresponde o el sistema la está procesando |

## 4. Pantallas y su jerarquía

### 4.1 Lista de procedimientos
Tabla: número, objeto, régimen, etapa actual (ícono y nombre), decisiones pendientes, sugerencias, última novedad del Portal. Arriba, "Nuevo procedimiento" con el campo del enlace del Portal y la alternativa "cargar a mano" (REQ-065, REQ-071).

### 4.2 Estado del expediente (portada del procedimiento)
1. Encabezado del procedimiento: número, objeto, fecha de autorización y régimen, origen (Portal, fecha de la última revisión).
2. **Para decidir ahora**: dos columnas separadas, *Decisiones pendientes* y *Sugerencias del sistema*, cada ítem con su enlace directo.
3. **Lista de control**: las ocho partes en orden; por cada una, estado, qué hay (con origen), qué falta y la acción que sigue.
4. La ventana del proceso, si hay algo corriendo.

### 4.3 Cada parte
Misma estructura: título y resumen en una línea (contadores) → bloque "Pendiente" (solo si hay) → contenido → acciones de cierre al pie del bloque que cierran. Las cargas a mano van en un panel plegable al final ("Agregar a mano"), no en el medio.

## 5. Cómo se muestra una matriz grande

1. **Barra de contadores** arriba: total, por tipo, y por estado de revisión (propuesto, confirmado, sugerencia, quitado). Cada contador es también un filtro.
2. **Agrupación en dos niveles**: primero por **tipo** (Formales · Económicos · Técnicos por renglón), y dentro de cada tipo por **sección del pliego** (artículo o cláusula). Cada grupo es plegable, con su cuenta y sus acciones de grupo ("confirmar las 6") en el encabezado del grupo.
3. **Una fila por requisito**, en tabla densa (13,5 px, celdas 4px 8px): número, requisito en una línea, ubicación en el pliego, consecuencia elegida, estado (ícono). Marcas aparte, en una columna "Origen", para "agregado por circular", "agregado por una persona" o "devuelto".
4. **Fila expandible**: al abrirla se ve la cita literal, los cambios de circulares (antes / después), el respaldo normativo, las consecuencias posibles y las acciones (confirmar, corregir, quitar, historial).
5. **Filtros** persistentes: tipo, estado, renglón, solo con cambios de circular, texto libre.
6. **Sugerencias y tramos pendientes** en un bloque propio arriba de la tabla, con su cuenta, porque bloquean la validación.
7. **Validar** al pie, con la condición visible ("quedan 3 sugerencias sin decidir").
8. La leyenda "BORRADOR INCOMPLETO" se mantiene como franja mientras no está validada (REQ-032).

La matriz de evaluación usa las mismas reglas: filas = requisitos agrupados por tipo y sección; columnas = ofertas; cada celda es un ícono (cumple, no cumple, no determinado, pendiente) con su motivo al pasar el mouse y el fundamento al hacer clic. Arriba de la grilla va la **conclusión**: ofertas descartadas con su motivo y orden económico propuesto. Debajo, el estado por oferta en una tabla de cuentas.

## 6. Opciones y recomendación

| Tema | Opción A | Opción B | Opción C | Recomendación |
|---|---|---|---|---|
| Navegación dentro del procedimiento | **Barra de etapas horizontal** bajo el encabezado | Menú lateral fijo con las partes | Pestañas sin estado | **A**: muestra el orden y el estado de todo a la vez; en pantallas angostas se vuelve desplazable. B ocupa ancho que necesitan las matrices. C no muestra qué falta. |
| Portada del procedimiento | **Estado del expediente** (lista de control) | Mantener "Recorrido" y "Procedimiento" separados | Tablero con tarjetas por etapa | **A**: una sola entrada responde "qué hay, qué falta, qué decido"; C se ve bien pero se lee peor que una lista. |
| Agrupación de la matriz de cumplimiento | **Tipo → sección del pliego** | Sección del pliego → tipo (orden del documento) | Lista plana con filtros | **A** por defecto, con un selector "agrupar por sección del pliego" para quien revisa leyendo el pliego. C no da jerarquía. |
| Detalle de cada requisito | **Fila expandible** en tabla | Tabla + panel de detalle a la derecha | Tarjetas (como hoy) | **A** para empezar (simple, funciona en cualquier ancho). B es mejor para revisar muchas filas seguidas con pantalla ancha; se puede sumar después. C descartada: es el problema actual. |
| Pendientes y sugerencias | **Bandeja "Para decidir" en el expediente + contadores en la barra** | Solo dentro de cada parte | Página aparte de bandeja | **A**: cumple "que quede claro que están ambas" sin duplicar las pantallas de decisión (REQ-068). |
| Ventana del proceso | **Panel lateral plegable**, visible en cualquier pantalla del procedimiento | Bloque dentro del expediente (como hoy) | Página aparte | **A**: se sigue el proceso sin dejar lo que se está mirando; un indicador en la barra de etapas lo abre. |
| Origen del documento | **Marca "Portal" o "A mano" en cada fila, con fecha** + filtro | Dos secciones separadas (Portal / a mano) | Solo en el detalle | **A**: muestra el Portal como primera fuente sin partir la lista; B duplica encabezados. |
| Hojas de compliance e informe técnico | **Una pantalla con las dos, por oferta** | Dentro de cada oferta | Dentro de la evaluación (como hoy) | **A**: son los dos insumos que sube la Comisión y bloquean filas de la evaluación; juntos se ve de un vistazo qué falta subir. |

## 7. Qué no cambia

- La lógica de cada feature, sus estados y sus reglas (P3: la decisión es de la Comisión).
- Las pantallas de decisión existentes (confirmar una propuesta, responder una pregunta, aprobar lo importado); la reorganización cambia por dónde se llega y cómo se presentan.
- La guía visual: colores, tipografía, íconos de estado.

## 8. Pasos siguientes (si se aprueba)

1. Registrar la decisión de organización como ADR.
2. Pasar a la spec 013 (o a una nueva) los cambios de navegación: expediente como portada, ocho partes, barra de etapas, bandeja de decisiones.
3. Rehacer primero la matriz de cumplimiento (el caso más grave) y después la matriz de evaluación, con el caso-00.

## 9. Altas, cargas y correcciones

Agregado el 2026-10-08 a pedido del responsable ("no veo en el mockup algo sencillo como dónde subir un documento… dónde están las altas").

Regla general: **cada carga está en la parte del expediente a la que pertenece**, con un botón visible a la derecha del título de la parte, y además como acción directa en la fila de la lista de control donde algo falta ("Falta el pliego → Subir documento"). No hay una sección aparte de cargas.

| Qué se da de alta o se carga | Dónde | Cómo |
|---|---|---|
| Procedimiento | Procedimientos → Nuevo procedimiento | Primero "Explorar el Portal": pegar el enlace, ver la propuesta agrupada (datos, renglones, cronograma y garantías, documentos, ofertas) y aprobar ítem por ítem o todo. Alternativa: alta a mano con número, expediente, tipo, objeto, fecha de autorización (muestra el régimen) y renglones. |
| Documentos del pliego | 2 · Pliego y circulares → "Subir documento" | Arrastrar y soltar varios archivos; cada uno con tipo (pliego, circular modificatoria, circular aclaratoria, respuesta a consulta, anexo), título y fecha propuestos por el sistema y corregibles; estado de lectura en vivo. Una circular modificatoria avisa que puede abrir una versión nueva de la matriz. |
| Oferta | 4 · Ofertas → "Agregar oferta" | Desde el Portal (acta de apertura: oferente, CUIT, total, garantía) o a mano. |
| Documentos de una oferta | Dentro de cada oferta → "Subir documentos", y "Subir" en cada celda que falta del cuadro de exigidos | Varios a la vez; el sistema propone a qué documento exigido corresponde cada archivo y el cuadro se completa al terminar la lectura. |
| Hoja de compliance | 5 · Hojas de compliance, botón en cada fila que falta (y en la lista de control) | Archivo, fecha de la verificación y resultado que informa (puede ser "no cumple"). |
| Informe técnico | 6 · Informe técnico | Por procedimiento o por oferta. |
| Norma | Normativa → "Cargar norma" | Archivo, tipo, número, organismo, parte de la normativa, título, fechas de publicación y vigencia, fuente y a qué norma modifica. Después, el informe de lectura y "Validar la lectura". |

**Corregir sin borrar (P6).** Toda corrección pide motivo y queda registrada con quién y cuándo:
- *Editar datos* del procedimiento o de una oferta: muestra el origen de cada dato y la lista de cambios (antes, después, motivo).
- *Reemplazar* un documento: la versión anterior se conserva y lo que dependía de ella se vuelve a leer y evaluar.
- *Retirar* un documento: sale del expediente pero no se borra; aparece en "Mostrar los retirados" y se puede restituir. Usa el botón de acento (acción con efecto fuerte).
- *Historial* de un documento: línea de tiempo (subido, leído, evaluado, reemplazado, retirado) y tabla de versiones con su huella.

## 10. Índice de pantallas

Agregado el 2026-10-08 ("armá el mockup de todo, desde el ingreso a la evaluación final"). En la maqueta, el mismo índice está en la pantalla "Mapa de pantallas" (`#mapa`). Roles: el operador prepara y carga; el evaluador además decide; el usuario de lectura solo consulta. En la maqueta se cambia de rol con "ver como" en el encabezado: con operador desaparecen los botones de decisión y se avisa "lo decide un evaluador".

| N.º | Pantalla (ancla) | Qué muestra | Quién la usa | Acciones |
|---|---|---|---|---|
| 1 | Ingreso (`#ingreso`) | Usuario y clave; error de clave con intentos restantes; qué puede cada rol | Todos | Ingresar; salir (vuelve acá con aviso) |
| 2 | Procedimientos (`#procedimientos`) | Lista con régimen, etapa actual, pendientes, sugerencias, última novedad del Portal | Todos | Explorar el Portal; alta a mano; abrir un expediente |
| 3 | Nuevo procedimiento (`#nuevo`, `#nuevo-mano`) | Pasos pegar enlace → revisar → aprobar; propuesta agrupada con origen en el Portal; o formulario a mano con renglones | Operador prepara; evaluador aprueba datos y ofertas | Explorar; marcar o desmarcar ítems; aprobar los marcados; rechazar el resto; crear a mano; agregar renglón |
| 4 | Estado del expediente (`#expediente`) | Para decidir (pendientes y sugerencias separados); lista de control de las 8 partes; ejemplo de procedimiento recién creado | Todos | Ir a cada decisión; acción directa en cada falta (subir, agregar oferta, subir hoja, subir informe) |
| 5 | Editar datos del procedimiento (`#editar-proc`) | Datos con su origen; cambios registrados | Operador y evaluador | Guardar con motivo |
| 6 | 1 · Normativa aplicable (`#normativa-proc`) | Normas que rigen a la fecha de autorización; la que no aplica; la que falta cargar | Todos | Ir a cargarla |
| 7 | Normativa, biblioteca (`#normativa`) | Normas con parte, estado, unidades y origen; lecturas para validar | Operador carga; evaluador valida | Cargar norma; ver informe; validar; reemplazar; retirar; registrar modificatoria |
| 8 | Informe de lectura (`#lectura-norma`) | Unidades reconocidas, páginas no leídas, tramos sin ubicar | Evaluador | Validar la lectura; rechazar y volver a cargar |
| 9 | Consulta de normativa (`#consulta`) | Pregunta con fecha de autorización; respuesta con citas literales y su parte; "no determinado" | Todos | Consultar; abrir la norma citada |
| 10 | 2 · Pliego y circulares (`#pliego`, `#pliego-subir`) | Documentos con tipo, fecha, origen, lectura y efecto en la matriz; retirados | Operador | Subir varios (arrastrar y soltar); reemplazar; retirar; historial; restituir |
| 11 | 3 · Matriz, antes de proponer (`#matriz-vacia`) | Estado vacío con lo que hay del pliego | Operador o evaluador | Proponer la matriz (abre la ventana del proceso) |
| 12 | 3 · Matriz de cumplimiento (`#matriz`) | Tabla agrupada por tipo y sección, contadores que filtran, filtros, filas que se abren con cita y consecuencias; en borrador: franja, sugerencias y tramos | Evaluador decide; operador prepara | Confirmar (uno o por grupo), corregir, quitar, agregar, pasar o quitar sugerencias, elegir consecuencia, validar, descartar el borrador, versiones, imprimir, exportar, abrir versión nueva |
| 13 | 4 · Ofertas (`#ofertas`, `#ofertas-alta`) | Pendientes de la parte; cuadro de documentos exigidos por oferente; detalle por oferta | Operador | Agregar oferta (Portal o a mano); subir documentos; subir en la celda que falta; editar datos; reemplazar; retirar; aprobar novedades del Portal |
| 14 | Ficha de la oferta (`#ficha`) | Síntesis y fragmento literal por requisito; "no se encontró en la oferta" | Todos (opcional) | Corregir o agregar fragmentos |
| 15 | Historial de un documento (`#historial`) | Línea de tiempo y versiones con huella; ejemplo de retiro | Todos | Ver versiones; restituir |
| 16 | 5 · Hojas de compliance (`#compliance`) | Hoja por oferta, requisitos que cubre, cuáles faltan | Evaluador | Subir hoja; ver; reemplazar; retirar |
| 17 | 6 · Informe técnico (`#informe`) | Informe subido y propuesta apto o no apto por oferta y renglón con cita | Evaluador | Subir informe (procedimiento u oferta); ver el proceso; dar el ok |
| 18 | 7 · Evaluación (`#evaluacion`) | Descartes propuestos, orden económico (total y por renglón), estado por oferta, matriz requisitos × ofertas | Evaluador decide | Volver a evaluar; confirmar o rechazar descartes; abrir el detalle; confirmar, corregir, rechazar |
| 19 | Ventana del proceso (`#proceso`) | Tarea, paso actual, hecho y lo que falta, últimos pasos, aviso al terminar | Todos | Abrir y cerrar desde cualquier pantalla del procedimiento |
| 20 | Detalle de un par (`#par`) | Cita del pliego, de la oferta y del Portal, cálculo, norma, historial | Evaluador | Confirmar; corregir con fundamento; rechazar la propuesta |
| 21 | Preguntas a la Comisión (`#preguntas`) | Abiertas con su contexto citado; respondidas y dónde se usan | Evaluador | Registrar respuesta; dejar sin responder |
| 22 | Subsanación (`#subsanacion`) | Pasos no se encontró → decidir → pedir → subir → reevaluar | Evaluador decide; operador sube | Pedir que se subsane con plazo; no pedir; subir el documento |
| 23 | 8 · Evaluación final y dictamen (`#cierre`) | Qué falta para cerrar; al terminar: resultado por oferta, orden de mérito por renglón, borrador del dictamen | Evaluador | Generar borrador; exportar planilla o PDF; cerrar el expediente |
| 24 | Estados vacíos y errores (`#estados`) | Sin procedimientos, Portal caído, documento ilegible, proceso que falló, matriz cambiada, falta lo previo, sin permiso, sesión vencida, documento repetido | Todos | La acción que corresponde a cada caso |

Pendiente de decisión del responsable: el **borrador del dictamen** (pantalla 23) está diferido en la hoja de ruta desde el 2026-10-03; la maqueta lo muestra para que se decida si se habilita.
