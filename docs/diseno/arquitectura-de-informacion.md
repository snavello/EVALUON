# Arquitectura de información de EVALUON (propuesta)

> **Esta versión reemplaza la organización en ocho etapas con orden fijo (ADR-0046) por la de cinco secciones sin orden obligatorio (ADR-0047, spec 014).** Se conserva el diagnóstico inicial (secciones 1 y 2); desde la sección 3 todo es nuevo. La maqueta rehecha está en `docs/diseno/mockup/index.html` y el control de requisitos en `docs/diseno/control-014.md`.

Estado: propuesta para revisión del responsable · Fecha: 2026-10-07 (reescrita el 2026-10-08 para la spec 014) · Mockup navegable: `docs/diseno/mockup/index.html` (abrir en el navegador, datos inventados).

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

1. **Un procedimiento es el eje.** Todo cuelga de él, en cinco secciones a las que se entra en cualquier orden.
2. **Cada pantalla, la misma jerarquía:** título → resumen en una línea → lo pendiente arriba → el detalle después → las acciones de cierre (validar, confirmar) al final del bloque que cierran, nunca antes del contenido.
3. **Existe / falta / subido / pendiente** se ven siempre con las mismas cuatro marcas, en todas las partes.
4. **Origen visible:** cada documento y dato dice si vino del Portal o se subió a mano, con fecha.
5. **Pendientes y sugerencias, separados y ambos visibles** (decisión literal del responsable en la spec 013).
6. **Íconos de color con nombre al pasar el mouse**, sin pastillas (guía visual 2.2).
7. **El sistema propone, la Comisión decide** (P3): toda propuesta se rotula como tal; las acciones de decisión solo las ve el evaluador (REQ-069).

## 3. Organización: el procedimiento y sus cinco secciones

Decisión literal del responsable (ADR-0047): «no lo veas solo como recorrido, porque puede no tener un orden». Navegación de primer nivel (barra superior): **Procedimientos** (y, en la maqueta, el mapa de pantallas). Dentro de un procedimiento, una **barra de secciones** siempre visible (queda fija al desplazarse) con una **Portada** y las cinco secciones. Cada una muestra el ícono de su estado, su nombre y dos cuentas distintas: pendientes de decidir y sugerencias del sistema. No hay «etapa actual», ni pasos numerados obligatorios, ni «paso siguiente» impuesto: el número es solo el nombre de la sección.

| Sección | Qué contiene | Cómo se carga | Qué decide la Comisión |
|---|---|---|---|
| **1 · Procedimiento de compra** | Número, expediente, tipo, objeto, fecha de autorización con su régimen (Disp. 247/2022 o 297/03), renglones con cantidad, apertura, cronograma y garantías; cada dato con su origen. Novedades del Portal. | Explorador y cargador inicial del Portal (se pega el enlace); sin Portal, se sube el pliego y el sistema propone datos y renglones. | Aprobar lo encontrado o propuesto, ítem por ítem o todo; corregir un valor propuesto con motivo; aprobar las novedades. |
| **2 · Pliego y matriz** | Pliego, anexos y especificaciones técnicas; matriz de cumplimiento (tabla por tipo, filtros, filas con cita); versiones. | «Subir archivo» o «Tomar del Portal». | Confirmar, corregir, quitar, agregar y validar la matriz. |
| **3 · Ofertas** | Ofertas, sus documentos, anexos técnicos y hoja de compliance (una por oferta); circulares y aclaraciones; ficha de cada oferta. | Alta de oferta desde el Portal (acta de apertura) o subiendo sus archivos; documentos, anexos y hoja subidos dentro de la oferta; circulares tomadas del Portal o subidas. | Aprobar lo tomado; verificar páginas ilegibles. Una circular modificatoria abre una versión nueva de la matriz de la sección 2. |
| **4 · Evaluación y dictamen** | Resultado por oferta y orden económico, descartes, preguntas y subsanaciones, dictamen, propuesta por oferta y requisito, informe técnico del área, exportaciones. | Informe técnico y dictamen: subidos o, el dictamen, tomado del Portal. | Confirmar, corregir o rechazar la propuesta; decidir descartes; responder preguntas; decidir subsanaciones. El sistema no redacta el dictamen. |
| **5 · Normativas** | Normas que rigen el procedimiento según su fecha de autorización y cuáles faltan; consulta con citas literales. | Solo «Subir archivo»: el sistema lee la norma y muestra el informe de lectura. | Validar la norma desde la pantalla. |

Estado de cada sección, con los íconos de la guía (mismo círculo, distinto símbolo, nombre al pasar el mouse):

| Estado | Ícono | Cuándo |
|---|---|---|
| Lista | tilde verde | Existe y no tiene nada pendiente |
| A decidir | signo de pregunta ámbar | Tiene decisiones pendientes de la Comisión |
| Falta | cruz roja | Debería existir y no está |
| En curso | reloj azul | El sistema la está procesando |

## 4. Pantallas y su jerarquía

Jerarquía común (REQ-100): **título → resumen en una línea → lo pendiente → el detalle → acciones al pie del bloque que cierran.** Las cargas («Subir archivo» y, cuando el Portal lo publica, «Tomar del Portal») van siempre a la vista, junto al título de la sección, y cada alta o carga específica tiene su botón visible en el bloque al que pertenece. Nada va en pestañas, paneles plegados ni formularios para tipear datos o renglones.

### 4.1 Lista de procedimientos
Tabla: procedimiento, régimen, ícono de estado de cada una de las cinco secciones, pendientes y sugerencias. Arriba, «Nuevo procedimiento».

### 4.2 Nuevo procedimiento
Antes de que exista, dos entradas de la sección 1: **Explorar el Portal** (pegar el enlace) o **Subir el pliego**. Sin campos de datos. Al aprobar la propuesta se abre el procedimiento creado con sus cinco secciones.

### 4.3 Portada del procedimiento
Título del procedimiento, barra de secciones, resumen en una línea, **pendientes de decidir y sugerencias en dos bloques separados** (cada ítem con su enlace) y, por sección, qué hay, qué falta y de dónde vino.

### 4.4 Sección 1
Pendientes y sugerencias, novedades del Portal para aprobar, datos con origen, renglones, apertura y garantías. Aparte, el **explorador del Portal** (lo encontrado agrupado, con aprobación ítem por ítem o todo, y destino de cada grupo) y el **alta subiendo el pliego** (datos y renglones propuestos, para aprobar o corregir con motivo).

### 4.5 Sección 2
Documentos con origen y acciones (historial, reemplazar, retirar), matriz agrupada por tipo con filtros y el contador «solo lo que falta decidir», filas que se abren con la cita, acciones al pie (imprimir, exportar, agregar requisito desde el pliego, confirmar, validar) y lista de versiones con fecha y quién validó.

### 4.6 Sección 3
Ofertas con alta a la vista (desde el Portal o subiendo archivos) y, por oferta, botones para documentos, anexo técnico y hoja de compliance; circulares y aclaraciones con su efecto en la matriz. Pantallas de detalle: una oferta y su ficha (lo presentado frente a cada requisito).

### 4.7 Sección 4
La conclusión primero: resultado por oferta y orden económico (total y por renglón), descartes con su decisión registrada, preguntas y subsanaciones, dictamen (del Portal o subido); después el detalle: propuesta por oferta y requisito, informe técnico y exportaciones.

### 4.8 Sección 5
Normas que rigen y cuáles faltan, con «Subir archivo»; consulta con citas literales; informe de lectura de una norma con «Validar la norma».

## 5. Cómo se muestra una matriz grande

1. **Contadores que son filtros** arriba: todos, solo lo que falta decidir, confirmados, cambiados por circular, verificación externa.
2. **Agrupación por tipo** (formales, económicos, técnicos por renglón) y, dentro, por sección del pliego, con cuenta por grupo.
3. **Una fila por requisito**, en tabla densa: número, requisito, ubicación en el pliego, consecuencia, marcas e ícono de revisión.
4. **Fila que se abre** con la cita literal, el texto anterior y el vigente si lo cambió una circular, la consecuencia y las acciones (confirmar, corregir, quitar, historial).
5. **Acciones y condiciones al pie**, con la condición visible para validar.

La propuesta de evaluación (sección 4) usa las mismas reglas: filas = requisitos agrupados por tipo; columnas = ofertas; cada celda un ícono con su motivo al pasar el mouse y su fundamento al abrir la fila.

## 6. Opciones y recomendación

| Tema | Opción A | Opción B | Recomendación |
|---|---|---|---|
| Navegación dentro del procedimiento | **Barra de cinco secciones**, fija, con estado y cuentas | Menú lateral | **A**: se entra a cualquiera, se ve qué falta y no quita ancho a las matrices. |
| Orden de trabajo | **Sin orden obligatorio** (decisión del responsable) | Recorrido fijo (ADR-0046) | **A**: el trabajo real no tiene orden; el recorrido fijo se rechazó. |
| Alta de un procedimiento | **Portal o pliego subido**, con propuesta que se aprueba | Formulario con renglones | **A**: nada se tipea; B se rechazó. |
| Pendientes y sugerencias | **Dos bloques separados, en la portada y en cada sección** | Una sola lista | **A**: se ven los dos (REQ-098). |
| Detalle de cada requisito | **Fila que se abre** | Panel lateral | **A** para empezar; B se puede sumar con pantalla ancha. |
| Ventana del proceso | **Panel lateral**, abrible desde cualquier pantalla | Bloque fijo | **A**. |
| Origen de cada dato | **Marca «Portal» o «Archivo» con fecha** en cada fila | Secciones separadas | **A**. |

## 7. Qué no cambia

- La lógica de cada feature, sus estados y sus reglas (P3: la decisión es de la Comisión).
- La guía visual: colores, tipografía, íconos de estado.
- Del ADR-0046: la jerarquía común, la matriz en tabla agrupada con filtros, los pendientes y sugerencias separados, la ventana del proceso.

## 8. Pasos siguientes (si se aprueba)

1. El responsable aprueba la maqueta.
2. Corte vertical: esqueleto de las cinco secciones, portada y la sección 2 con el caso chico.
3. Después, sección por sección, con el caso-00.

## 9. Altas, cargas y correcciones

Regla general: **cada carga está en la sección a la que pertenece**, con su botón visible, sin desplegar nada. En cada sección, «Subir archivo» y, cuando el Portal lo publica, «Tomar del Portal».

| Qué se da de alta o se carga | Dónde | Cómo |
|---|---|---|
| Procedimiento | Nuevo procedimiento; sección 1 | Explorar el Portal (pegar el enlace) o subir el pliego; se aprueba lo propuesto. |
| Pliego, anexos, especificaciones | Sección 2 | Subir archivo o tomar del Portal. |
| Oferta | Sección 3 | Desde el Portal (acta de apertura) o subiendo los archivos de la oferta. |
| Documentos de una oferta | Sección 3, dentro de la oferta | Varios a la vez; el sistema propone a qué corresponde cada uno. |
| Anexos técnicos de la oferta | Sección 3, dentro de la oferta | «Subir anexo técnico». |
| Hoja de compliance | Sección 3, una por oferta | «Subir hoja de compliance». |
| Circulares y aclaraciones | Sección 3 | Subir o tomar del Portal; una modificatoria abre una versión nueva de la matriz. |
| Informe técnico del área | Sección 4 | «Subir informe técnico», por procedimiento o por oferta. |
| Dictamen | Sección 4 | Tomar del Portal o subir. El sistema no lo redacta. |
| Norma | Sección 5 | Solo el archivo; informe de lectura y validación desde la pantalla. |

**Corregir sin borrar (P6).** Reemplazar un documento conserva la versión anterior; retirarlo lo mueve a «retirados» con el motivo y se puede restituir; el historial muestra todo. Corregir un valor propuesto pide motivo.

## 10. Índice de pantallas

El mismo índice, con los requisitos que cubre cada pantalla, está en la maqueta (`#mapa`) y, con el detalle de qué se ve y dónde, en `docs/diseno/control-014.md`. Roles: el operador prepara y carga; el evaluador además decide; el usuario de lectura solo consulta («ver como» en el encabezado de la maqueta).

| Ancla | Pantalla |
|---|---|
| `#ingreso`, `#ingreso-error` | Ingreso y error de clave |
| `#procedimientos` | Lista de procedimientos |
| `#nuevo` | Nuevo procedimiento (explorar el Portal o subir el pliego) |
| `#portada` | Portada del procedimiento |
| `#s1`, `#s1-portal`, `#s1-pliego`, `#recien-creado` | Sección 1, explorador del Portal, alta subiendo el pliego, procedimiento recién creado |
| `#s2` | Sección 2 · Pliego y matriz |
| `#s3`, `#oferta`, `#ficha`, `#historial` | Sección 3 · Ofertas, una oferta, ficha de la oferta, historial de un documento |
| `#s4`, `#par`, `#proceso` | Sección 4 · Evaluación y dictamen, detalle de un par, ventana del proceso |
| `#s5`, `#lectura-norma` | Sección 5 · Normativas, informe de lectura de una norma |
| `#estados`, `#mapa` | Estados vacíos y errores, mapa de pantallas |
