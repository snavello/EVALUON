# Guía visual de EVALUON (propuesta)

Estado: propuesta, 2026-10-07, pendiente de aprobación del responsable.
Archivos: `evaluon/static/diseno/tokens.css` (variables) y `docs/diseno/muestra.html` (página de muestra, abrir en el navegador).

## 1. Lo extraído de la referencia

Fuentes: https://www.arca.gob.ar/ (estilos calculados medidos en el navegador, 2026-10-07) y la página principal pública de https://afipcompras.afip.gob.ar/ (estructura). ARCA usa el sistema de diseño "Poncho" del Estado argentino sobre Bootstrap 3. Hojas de fuentes cargadas: roboto-fontface, encode-sans-latin y droid-serif. Iconos: Font Awesome y Material Symbols.

| Aspecto | Valor medido |
|---|---|
| Cuerpo | Roboto 16 px, peso 400, interlineado 22,9 px (1,43), texto `#333333`, fondo `#FAFBFC` |
| Títulos | Roboto peso 500; h1 29 px (interlineado 31,9 px), h2 26 px (28,6 px); algunos h3 en Encode Sans 16 px peso 500 |
| Navegación | Barra de fondo `#242C4F` con sombra `0 2px 2px rgba(0,0,0,.2)`; enlaces del menú 20 px, peso 500, relleno 6px 5px |
| Enlaces | `#0072BB`, peso 500 |
| Botón principal (`.btn`) | Fondo `#139ED9`, texto blanco, peso 700, relleno 8px 10px, radio 4 px, sin sombra |
| Pie | Fondo `#242C4F`, relleno 24px 0 |
| Campos | 14 px, peso 600 |
| Estructura | Columna centrada receptiva; encabezado de ancho completo con menú horizontal y desplegables; tarjetas rectangulares uniformes con ícono; pie en varias columnas |
| Portal de Compras | Base Bootstrap con tema propio; barra de navegación con colapso en pantallas chicas, tarjetas de acción, modales de aviso (colores y fuentes no medidos) |

Contraste de los pares medidos (para decidir qué adoptar): texto `#333333` sobre `#FAFBFC` 12,20:1; enlace `#0072BB` sobre `#FAFBFC` 4,91:1; blanco sobre `#242C4F` 13,56:1; blanco sobre el botón `#139ED9` solo 3,03:1, por debajo de AA para texto normal. Por eso **no adoptamos el color del botón**, solo su forma.

Adoptamos la forma, no la marca: tipografías, escala, pesos, interlineado, relleno de botones, radio de 4 px, barra de navegación oscura con sombra leve, enlaces en peso 500. No se copia logo, escudo ni el color institucional (`#139ED9`, `#0072BB`, `#242C4F`).

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

Para respetar la forma institucional se usan las mismas familias que ARCA:
- **Roboto** para el texto (licencia Apache 2.0), pesos 400, 500 y 700.
- **Encode Sans** para los títulos (SIL Open Font License 1.1), pesos 500 y 600.

Ambas son de libre licencia y se alojan en `evaluon/static/diseno/fuentes/` (woff2); `tokens.css` ya declara los `@font-face`, con `local()` primero. **Pendiente de autorización del responsable:** la descarga de los archivos (Roboto: https://github.com/googlefonts/roboto; Encode Sans: https://github.com/thundernixon/Encode-Sans) junto con el texto de cada licencia. Mientras tanto la pila cae a Segoe UI y fuentes del sistema, sin servicios externos. Mono: pila del sistema.

| Nivel | Tamaño | Peso | Interlineado |
|---|---|---|---|
| h1 (Encode Sans) | 29 px (1,8125 rem) | 500 | 1,1 |
| h2 (Encode Sans) | 26 px (1,625 rem) | 500 | 1,1 |
| h3 (Encode Sans) | 20 px (1,25 rem) | 500 | 1,2 |
| Cuerpo (Roboto) | 16 px | 400 | 1,43 |
| Enlaces | 16 px | 500 | 1,43 |
| Menú | 20 px | 500 | relleno 6px 5px |
| Botón | 16 px | 700 | relleno 8px 10px |
| Etiquetas de campo | 14 px | 600 | 1,43 |
| Tabla densa | 14 px | 400 / 700 en encabezados | 1,3 |
| Notas | 13 px | 400 / 600 | 1,4 |

Líneas de lectura de hasta 44 rem.

### 2.4 Espaciado, radios y sombras

- Base de 4 px: 4, 8, 12, 16, 24, 32, 48 (`--ev-e1` a `--ev-e7`).
- Contenido centrado, máximo 72 rem; margen lateral 16 px (en móvil también 16 px).
- Radios: 2 px (etiquetas de estado), 4 px (botones, campos, tarjetas, como ARCA), 8 px (diálogos). Esquinas poco redondeadas: aspecto institucional.
- Sombras casi planas: botones sin sombra; barra de navegación `0 2px 2px rgba(0,0,0,.2)` (medida en ARCA); `0 1px 2px rgba(11,27,51,.10)` para tarjetas; `0 2px 8px rgba(11,27,51,.14)` solo para menús y diálogos. La jerarquía la dan los bordes de 1 px, no las sombras.
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
| Cuerpo ARCA, referencia (`#333333` / `#FAFBFC`) | no usado | 12,20 | sí |
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

Los colores propuestos no cambiaron con la medición, así que no hubo que recalcular. Todas las combinaciones propuestas superan 4,5:1. El script de cálculo no se versiona (es de una sola vez); los códigos de la tabla son los de `tokens.css`.

## 3. Qué falta decidir

1. Aprobar la gama y el rojo acento (o ajustar tonos tras ver `muestra.html`).
2. Confirmar si "no cumple" usa el rojo propio (`#7A1626`) o se unifica con el acento.
3. Autorizar bajar e incorporar los archivos de Roboto (Apache 2.0) y Encode Sans (OFL) a `evaluon/static/diseno/fuentes/`.
4. Una tarea posterior aplicará los tokens a las plantillas.
