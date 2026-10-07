# Guía visual de EVALUON (propuesta)

Estado: propuesta, 2026-10-07, pendiente de aprobación del responsable.
Archivos: `evaluon/static/diseno/tokens.css` (variables) y `docs/diseno/muestra.html` (página de muestra, abrir en el navegador).

## 1. Lo extraído de la referencia

Fuentes consultadas (solo páginas principales públicas): https://www.arca.gob.ar/ y https://afipcompras.afip.gob.ar/ (2026-10-07).

**Limitación de la extracción.** La herramienta de lectura entrega el contenido convertido a texto: no expone las hojas de estilo, ni los códigos de color, ni las familias tipográficas declaradas, y el acceso directo desde la terminal estaba bloqueado. Lo que sigue es lo observable en la estructura; lo que no se pudo verificar está marcado. Recomiendo una revisión visual rápida del responsable contra el sitio real antes de aprobar.

| Aspecto | Observado | Fuente |
|---|---|---|
| Tipografía | Sans-serif sin remates en todo el sitio; jerarquía por niveles de título (h1 a h3) y texto de cuerpo. Familia y tamaños exactos: no verificados. | ARCA |
| Estructura | Una sola columna centrada y receptiva; encabezado de ancho completo con logo y menú horizontal con desplegables; carrusel destacado; tarjetas rectangulares uniformes con ícono ("Más consultados"); pie en varias columnas. | ARCA |
| Superficies | Fondo blanco con secciones en gris suave; texto gris oscuro a negro; azul claro en elementos interactivos; azul marino/negro en zonas de contraste. | ARCA |
| Componentes | Menú principal con desplegables, bloque de acceso, tarjetas de servicios, botones de llamada a la acción como texto azul enlazado, pie con enlaces agrupados. | ARCA |
| Portal de Compras | Base Bootstrap (tema propio); barra de navegación con colapso en pantallas chicas, carrusel, tarjetas de acción ("Soy Proveedor", "Procesos de compra"), modales de aviso, búsquedas frecuentes. Colores y fuentes: no verificados. | Portal de Compras |

Rasgos que adoptamos (la forma, no la marca): encabezado oscuro de ancho completo; navegación horizontal simple; contenido en columna centrada con tarjetas rectangulares de bordes finos; fondos claros con contraste fuerte de texto; jerarquía clara de títulos. No se copia logo, escudo, marca ni el color institucional.

## 2. Propuesta para EVALUON

Principio: sobrio, legible en jornadas largas, con densidad alta en las matrices. Los azules estructuran; el beige suaviza los fondos; el rojo oscuro es el único acento.

### 2.1 Paleta

Azules, de azul noche a casi blanco:

| Token | Código | Uso |
|---|---|---|
| azul-900 | `#0B1B33` | Texto principal, encabezado |
| azul-800 | `#12284A` | Barra de navegación |
| azul-700 | `#1B3A66` | Botón primario, borde de cabecera de tabla, etapa hecha |
| azul-600 | `#22467C` | Hover del botón primario |
| azul-500 | `#1B4F8F` | Enlaces y anillo de foco |
| azul-300 | `#9DB4D3` | Borde de avisos informativos |
| azul-200 | `#C9D6E6` | Texto secundario sobre encabezado |
| azul-100 | `#E3E9F0` | Texto sobre navegación; fondo "pendiente" |
| azul-50 | `#EFF3F8` | Fila resaltada, aviso informativo, etapa actual |

Beiges, fondos casi blancos:

| Token | Código | Uso |
|---|---|---|
| beige-100 | `#F7F4EC` | Fondo de página |
| beige-50 | `#FCFAF5` | Superficie (tarjetas, tablas, campos) |
| beige-200 | `#F3EFE4` | Cebra de tablas |
| beige-300 | `#EEE9DC` | Superficie secundaria (paneles laterales) |
| beige-400 | `#D9D2C1` | Bordes y separadores |
| beige-600 | `#7A7260` | Borde de campos de formulario |

Texto suave: `#3E4C63` (descripciones, ayudas, etiquetas secundarias).

Acento: rojo oscuro `#8B1E2D` (hover `#6F1723`). Uso acotado: filete inferior del encabezado, acción destructiva o irreversible (descartar, anular), aviso importante. No se usa para decorar ni para títulos.

### 2.2 Estados de cumplimiento

Siempre con texto y símbolo además del color (no depender solo del color).

| Estado | Texto | Fondo | Símbolo |
|---|---|---|---|
| Cumple | `#14573D` | `#E1EFE7` | ✓ |
| No cumple | `#7A1626` | `#F6E1E3` | ✗ |
| No determinado | `#6B4700` | `#F6EACB` | ? |
| Pendiente | `#34476A` | `#E3E9F0` | … |

Justificación: "pendiente" queda dentro de la gama azul. "Cumple" necesita un verde y "no determinado" un ámbar porque entre azules y rojo no hay forma de distinguir cuatro estados de un vistazo en una matriz; ambos son tonos apagados que conviven con el beige. "No cumple" usa un rojo propio, más frío que el acento, para no mezclar "error de datos" con "acción destructiva"; si el responsable prefiere, puede unificarse con el acento.

### 2.3 Tipografía

Familia: **Source Sans 3** (Adobe), licencia **SIL Open Font License 1.1** (libre uso, redistribución y alojamiento propio). Elegida por su legibilidad en tamaños chicos, números tabulares (`font-variant-numeric: tabular-nums`) y buena cobertura del español. Se aloja en `evaluon/static/diseno/fuentes/` (woff2, pesos 400, 600 y 700); `tokens.css` ya declara los `@font-face`. **Pendiente:** los archivos de fuente no se incluyeron porque no hubo acceso a internet desde esta tarea; hay que bajarlos una vez de https://github.com/adobe-fonts/source-sans y guardarlos junto con el texto de la licencia. Mientras tanto la pila cae a Segoe UI y fuentes del sistema, sin servicios externos. Mono (identificadores, citas literales): pila del sistema.

| Nivel | Tamaño | Peso | Interlineado |
|---|---|---|---|
| h1 | 34 px (2,125 rem) | 700 | 1,2 |
| h2 | 26 px (1,625 rem) | 600 | 1,25 |
| h3 | 20 px (1,25 rem) | 600 | 1,3 |
| Cuerpo | 16 px | 400 | 1,5 |
| Destacado | 18 px | 400 | 1,5 |
| Tabla densa | 14 px | 400 / 600 en encabezados | 1,3 |
| Notas y etiquetas | 13 px | 400 / 600 | 1,4 |

Líneas de lectura de hasta 44 rem (unos 75 caracteres).

### 2.4 Espaciado, radios y sombras

- Base de 4 px: 4, 8, 12, 16, 24, 32, 48 (`--ev-e1` a `--ev-e7`).
- Contenido centrado, máximo 72 rem; margen lateral 16 px (en móvil también 16 px).
- Radios: 2 px (etiquetas de estado), 4 px (botones, campos, tarjetas), 8 px (diálogos). Esquinas poco redondeadas: aspecto institucional.
- Sombras casi planas: `0 1px 2px rgba(11,27,51,.10)` para tarjetas; `0 2px 8px rgba(11,27,51,.14)` solo para menús y diálogos. La jerarquía la dan los bordes de 1 px, no las sombras.
- Texturas: ninguna imagen ni degradado; superficies planas beige con bordes finos.

### 2.5 Tablas densas (matrices grandes)

- Texto de 14 px, interlineado 1,3, relleno de celda 6 px por 12 px.
- Cabecera fija (`position: sticky`) con fondo `#E2E7EE` y filete inferior de 2 px en azul-700.
- Cebra con beige-200, separadores de 1 px en beige-400, resalte al pasar en azul-50.
- Primera columna como `th scope="row"`; números alineados a la derecha y tabulares; contenedor con scroll horizontal; `caption` descriptivo.
- Celdas de estado como etiquetas compactas de 13 px con borde del mismo color del texto.

### 2.6 Contraste (WCAG AA, mínimo 4,5:1)

Cálculo: luminancia relativa L = 0,2126 R + 0,7152 G + 0,0722 B con canales linealizados; razón = (L claro + 0,05) / (L oscuro + 0,05). Calculado con un script de Python sobre cada par.

| Texto sobre fondo | Colores | Razón | AA |
|---|---|---|---|
| Texto / fondo de página | `#0B1B33` / `#F7F4EC` | 15,68 | sí |
| Texto / superficie | `#0B1B33` / `#FCFAF5` | 16,52 | sí |
| Texto / superficie secundaria | `#0B1B33` / `#EEE9DC` | 14,21 | sí |
| Texto / cebra | `#0B1B33` / `#F3EFE4` | 15,00 | sí |
| Texto / cabecera de tabla | `#0B1B33` / `#E2E7EE` | 13,86 | sí |
| Texto suave / fondo | `#3E4C63` / `#F7F4EC` | 7,90 | sí |
| Texto suave / superficie | `#3E4C63` / `#FCFAF5` | 8,32 | sí |
| Texto suave / superficie secundaria | `#3E4C63` / `#EEE9DC` | 7,16 | sí |
| Texto suave / cebra | `#3E4C63` / `#F3EFE4` | 7,56 | sí |
| Enlace / fondo | `#1B4F8F` / `#F7F4EC` | 7,46 | sí |
| Enlace / superficie | `#1B4F8F` / `#FCFAF5` | 7,86 | sí |
| Blanco / encabezado | `#FFFFFF` / `#0B1B33` | 17,23 | sí |
| Azul-200 / encabezado | `#C9D6E6` / `#0B1B33` | 11,69 | sí |
| Azul-100 / navegación | `#E3E9F0` / `#12284A` | 12,03 | sí |
| Blanco / botón primario | `#FFFFFF` / `#1B3A66` | 11,39 | sí |
| Blanco / botón hover | `#FFFFFF` / `#22467C` | 9,40 | sí |
| Blanco / botón de acento | `#FFFFFF` / `#8B1E2D` | 9,05 | sí |
| Acento / fondo | `#8B1E2D` / `#F7F4EC` | 8,23 | sí |
| Acento / superficie | `#8B1E2D` / `#FCFAF5` | 8,67 | sí |
| Cumple | `#14573D` / `#E1EFE7` | 7,19 | sí |
| No cumple | `#7A1626` / `#F6E1E3` | 8,53 | sí |
| No determinado | `#6B4700` / `#F6EACB` | 6,95 | sí |
| Pendiente | `#34476A` / `#E3E9F0` | 7,62 | sí |
| Borde de campo / superficie (componente, mínimo 3:1) | `#7A7260` / `#FCFAF5` | 4,57 | sí |
| Anillo de foco / fondo (mínimo 3:1) | `#1B4F8F` / `#F7F4EC` | 7,46 | sí |

Todas las combinaciones propuestas superan 4,5:1. El script de cálculo no se versiona (es de una sola vez); los códigos de la tabla son los de `tokens.css`.

## 3. Qué falta decidir

1. Aprobar la gama y el rojo acento (o ajustar tonos tras ver `muestra.html`).
2. Confirmar si "no cumple" usa el rojo propio (`#7A1626`) o se unifica con el acento.
3. Autorizar bajar e incorporar los archivos de Source Sans 3 (OFL) a `evaluon/static/diseno/fuentes/`.
4. Verificar visualmente contra el sitio de ARCA lo que la extracción no pudo confirmar (familias y tamaños exactos).
5. Una tarea posterior aplicará los tokens a las plantillas.
