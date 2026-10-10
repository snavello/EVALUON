# Guía visual de EVALUON (propuesta)

Estado: aprobada por el responsable el 2026-10-07 (ver sección 3).
Archivos: `evaluon/static/diseno/tokens.css` (variables), `evaluon/static/diseno/fuentes/` (tipografía alojada) y `docs/diseno/muestra.html` (página de muestra, abrir en el navegador).

## 1. Referencias extraídas

### 1.1 Referencia principal: proyecto Colm3na (repositorio propio del responsable)

Fuente: `snavello/MITRABAJOC` (`static/marca.css`, `static/encabezado.css`, `static/interior.css`, `docs/generador/estilos.css`, `.claude/skills/frontend-design/SKILL.md`). De ahí se toman tipografía, escala, espaciados, radios, sombras, bordes y estructura del encabezado. **No se toman sus colores**: la paleta es la de EVALUON (sección 2.1).

| Aspecto | Valor en Colm3na |
|---|---|
| Cuerpo | `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`; interlineado 1,5; 15 px en documentos |
| Cifras | `ui-monospace, Consolas, "SF Mono", monospace` con `font-variant-numeric: tabular-nums` |
| Títulos y encabezados de sección | Barlow Condensed 700 (SIL OFL 1.1, alojada). h1 de portada `clamp(30px, 4.5vw, 50px)` con interlineado 1; h2 30 px (24 px en bloques) interlineado 1,05; h3 20 px con espaciado .4 px; h4 18 px |
| Etiquetas | Condensada en mayúsculas: encabezados de tabla 12,5 px con espaciado 1,2 px; pestañas 15 px con 1,4 px; insignias 11 px con 1,2 px |
| Encabezado | Barra oscura, relleno 11px 18px, separación 14 px, borde inferior de 1 px; nombre en condensada 36 px (26 px en móvil), mayúsculas, espaciado .6 px, con filo de 2 px a la derecha; fecha o usuario a la derecha en 11,5 px / 12,5 px |
| Pestañas | Barra pegajosa, fondo de superficie, borde inferior 1 px; pestaña con relleno 13px 14px 11px y subrayado de 3 px en la activa |
| Radios | Tarjeta 12 px, botón 9 px, chip 20 px, panel 14 px, bloque 16 px, insignia 999 px |
| Sombras y bordes | Borde de 1 px en todo; sombra de paneles `0 1px 2px rgba(10,20,33,.05)`; flotantes `0 2px 10px rgba(0,0,0,.25)` |
| Densidad | Controles 13–14,5 px; secundarios 10,5–12,5 px; tablas 13,5 px con celdas 7px 10px; tablas de columnas 12,5 px con celdas 4px 8px |
| Botón | Relleno 13 px (a ancho completo en móvil), 14,5 px, peso 650, radio 9 px; secundario transparente con borde de 1 px |
| Notas | Filete lateral de 3 px, fondo suave, radio `0 10px 10px 0`, 14,5 px |
| Reglas de la skill de diseño | Tipografía con personalidad (display con medida, cuerpo neutro); la estructura debe codificar información, no decorar; una sola firma memorable y el resto sobrio; visible el foco de teclado; respeto de movimiento reducido |

Nota: Colm3na usa además la condensada en peso 600 en algunos lugares, pero solo está alojado el peso 700. EVALUON usa solo 700 para no generar negritas falsas; el peso 600 queda anotado como pendiente si se lo quiere (no se descargó).

### 1.2 Referencia institucional: ARCA (solo contexto)

Fuente: https://www.arca.gob.ar/, estilos calculados medidos en el navegador (2026-10-07); sistema de diseño "Poncho" del Estado argentino sobre Bootstrap 3. El Portal de Compras (https://afipcompras.afip.gob.ar/) usa Bootstrap con tema propio.

| Aspecto | Valor medido en ARCA |
|---|---|
| Cuerpo | Roboto 16 px, peso 400, interlineado 1,43, texto `#333333`, fondo `#FAFBFC` |
| Títulos | Roboto 500; h1 29 px, h2 26 px; algunos h3 en Encode Sans 16 px |
| Navegación | Barra `#242C4F` con sombra `0 2px 2px rgba(0,0,0,.2)`; enlaces de menú 20 px, peso 500 |
| Enlaces y botón | Enlaces `#0072BB` peso 500; botón `#139ED9`, texto blanco, peso 700, relleno 8px 10px, radio 4 px |
| Pie y campos | Pie `#242C4F` con relleno 24px 0; campos 14 px peso 600 |

De ARCA se conserva la idea de barra de navegación oscura con sombra leve y columna centrada. Contraste de sus pares: texto `#333333` sobre `#FAFBFC` 12,20:1; enlace `#0072BB` sobre `#FAFBFC` 4,91:1; blanco sobre `#139ED9` solo 3,03:1 (no cumple AA para texto normal). No se copia logo, escudo ni el color institucional.

## 2. Propuesta para EVALUON

Principio: sobrio, legible en jornadas largas, denso donde hace falta (matrices). Los azules estructuran; el beige suaviza los fondos; el rojo oscuro es el único acento. La firma tipográfica es la condensada de Colm3na en títulos, etiquetas y pestañas; el resto, texto del sistema.

### 2.1 Paleta

Azules, de azul noche a casi blanco:

| Token | Código | Uso |
|---|---|---|
| azul-900 | `#0B1B33` | Texto principal, encabezado |
| azul-800 | `#12284A` | Hover sobre encabezado, fondos oscuros secundarios |
| azul-700 | `#1B3A66` | Botón primario, pestaña activa, borde de cabecera de tabla, etapa hecha |
| azul-600 | `#22467C` | Hover del botón primario |
| azul-500 | `#1B4F8F` | Enlaces y anillo de foco |
| azul-300 | `#9DB4D3` | Bordes suaves |
| azul-200 | `#C9D6E6` | Texto secundario sobre encabezado |
| azul-100 | `#E3E9F0` | Fondo "pendiente"; numeración de etapa |
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

Texto suave: `#3E4C63` (descripciones, ayudas, etiquetas, pestañas inactivas).

Acento: rojo oscuro `#8B1E2D` (hover `#6F1723`). Uso acotado: filete inferior del encabezado, filo del nombre en la barra, acción destructiva o irreversible, aviso importante. No decora ni titula.

### 2.2 Estados de cumplimiento: ícono de color, sin pastillas

Decisión del responsable (sección 3): cada estado se muestra como un **ícono de color** del mismo tamaño y forma base, y **el nombre aparece al pasar el mouse**.

- Forma: círculo de 16 px (`--ev-icono-tam`) con un símbolo blanco distinto adentro: tilde, cruz, signo de pregunta, reloj. SVG en línea (sprite `<symbol>` + `<use>`), sin dependencias externas.
- Nombre: al pasar el mouse **y también al enfocar con el teclado** (`tabindex="0"`). Cada ícono lleva `role="img"`, `aria-label` y `title` con el nombre, y un tooltip propio en CSS (`data-nombre`, fondo azul-900, texto blanco, a la derecha del ícono) porque el `title` nativo tarda y no se ve con el foco. En la muestra hay además una leyenda fija de los cuatro estados.
- La información no depende solo del color: la forma del símbolo distingue cada estado.

| Estado | Color del círculo | Símbolo | vs superficie `#FCFAF5` | vs cebra `#F3EFE4` | vs fila resaltada `#EFF3F8` | Símbolo blanco vs círculo |
|---|---|---|---|---|---|---|
| Cumple | `#1E7F55` | tilde | 4,77 | 4,33 | 4,46 | 4,97 |
| No cumple | `#B3263C` | cruz | 6,18 | 5,61 | 5,78 | 6,44 |
| No determinado | `#A8680B` | signo de pregunta | 4,33 | 3,93 | 4,05 | 4,52 |
| Pendiente | `#4A6590` | reloj | 5,66 | 5,14 | 5,30 | 5,91 |

Componente gráfico (WCAG 1.4.11): el círculo debe superar 3:1 contra el fondo de la celda; el mínimo es 3,69:1 (no determinado sobre `#E3E9F0`, el fondo "pendiente" en avisos), y el símbolo blanco supera 4,5:1 contra el círculo. Los colores de texto y fondo de estado (`--ev-cumple`, `--ev-nocumple`, etc.) quedan para avisos y textos que nombren el estado.

Justificación de la gama: "pendiente" queda dentro de la gama azul. "Cumple" lleva un verde apagado y "no determinado" un ámbar apagado, porque con solo azules y rojo no se distinguen cuatro estados en una matriz. "No cumple" usa su rojo propio, más claro y frío que el acento `#8B1E2D`, para no mezclar un resultado de evaluación con una acción destructiva.

#### Requisitos con información externa (T-228)

Los requisitos que se cumplen con información externa (la hoja de compliance de cada oferta, no el texto de la oferta) se muestran **aparte desde el principio**, con una marca propia que no es un estado de cumplimiento sino una clase de requisito. Por eso lleva su gama, un violeta apagado que no se parece a ningún estado: `--ev-externo` (texto, `#4B2E83`), `--ev-externo-fondo` (`#ECE7F5`) y `--ev-externo-marca` (`#6B4BA3`: filete lateral, borde de la insignia y encabezado del grupo). Se usa con texto («Externo», «Requisitos que se cumplen con información externa»), nunca solo el color.

| Par | Colores | Razón | Cumple |
|---|---|---|---|
| Texto / fondo del grupo | `#4B2E83` / `#ECE7F5` | 8,58 | AA |
| Texto / superficie | `#4B2E83` / `#FCFAF5` | 9,98 | AA |
| Texto / cebra | `#4B2E83` / `#F3EFE4` | 9,06 | AA |
| Marca / superficie (componente, mínimo 3:1) | `#6B4BA3` / `#FCFAF5` | 6,37 | sí |
| Marca / cebra | `#6B4BA3` / `#F3EFE4` | 5,78 | sí |

Calculado con el mismo método de la sección 2.6.

### 2.3 Tipografía

- **Texto:** pila del sistema `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`. No requiere archivos, es rápida y se ve nativa en el equipo de la Comisión.
- **Cifras** (folios, importes, plazos): `ui-monospace, Consolas, "SF Mono", monospace` con `tabular-nums`.
- **Títulos, etiquetas y pestañas:** **Barlow Condensed 700**, licencia SIL Open Font License 1.1, copiada del repositorio propio del responsable a `evaluon/static/diseno/fuentes/barlow-condensed-bold.woff2` (con `LICENCIA.txt`). Alojada localmente, sin CDN (P4). Solo existe el peso 700; no se simulan otros.

| Nivel | Tamaño | Fuente y peso | Interlineado | Otros |
|---|---|---|---|---|
| h1 | 31 px (portada: `clamp(30px, 4.5vw, 50px)`) | Condensada 700 | 1 – 1,05 | |
| h2 | 30 px (bloques: 24 px) | Condensada 700 | 1,05 | |
| h3 | 20 px | Condensada 700 | 1,05 | espaciado .4 px |
| h4 / título de ítem | 18 px | Condensada 700 | 1,05 | espaciado .3 px |
| Nombre en la barra | 36 px (móvil 26 px) | Condensada 700, mayúsculas | 1 | espaciado .6 px |
| Pestañas | 16 px | Condensada 700, mayúsculas | | espaciado 1,4 px |
| Encabezado de tabla | 12,5 px | Condensada 700, mayúsculas | | espaciado 1,2 px |
| Cuerpo | 15 px | Sistema 400 | 1,5 | |
| Controles | 14,5 px | Sistema 600 | 1,2 | |
| Tablas | 13,5 px | Sistema 400 | 1,4 | cifras tabulares |
| Notas y ayudas | 12,5 px | Sistema 400 | 1,4 | |
| Insignias | 11 px | Condensada 700, mayúsculas | | espaciado 1,2 px |

Líneas de lectura de hasta 80 caracteres.

### 2.4 Espaciado, radios, bordes y sombras

- Base de 4 px (4, 8, 12, 16, 24, 32, 48) y pasos chicos de Colm3na: 7, 10, 11, 14 px.
- Contenido centrado, máximo 72 rem, margen lateral `clamp(14px, 3vw, 36px)`.
- Encabezado: barra oscura, relleno 11px 18px, separación 14 px; nombre en condensada con filo rojo de 2 px; usuario a la derecha (nombre en 13,5 px, rol en 12,5 px); filete rojo inferior de 3 px. Debajo, pestañas en mayúsculas condensadas.
- Radios: 4 px (casillas), 9 px (botones y campos), 12 px (tarjetas), 14 px (paneles y tablas), 16 px (bloques), 20 px (chips).
- Bordes de 1 px en `#D9D2C1` en todas las superficies; la jerarquía la dan bordes y tipografía, no la sombra.
- Sombras: paneles `0 1px 2px rgba(10,20,33,.05)`; flotantes (menús, botones flotantes) `0 2px 10px rgba(0,0,0,.25)`.
- Texturas: ninguna imagen ni degradado; superficies planas beige con bordes finos.

### 2.5 Tablas densas (matrices grandes)

- Estados como íconos de 16 px centrados en su celda (sección 2.2).
- Texto de 13,5 px, interlineado 1,4; relleno de celda 4px 8px en matrices (7px 10px en tablas de lectura).
- Cabecera fija (`position: sticky`) con fondo `#E2E7EE`, texto condensado en mayúsculas de 12,5 px con espaciado 1,2 px y filete inferior de 2 px en azul-700.
- Cebra con beige-200, separadores de 1 px, resalte al pasar en azul-50.
- Primera columna como `th scope="row"`; cifras en monoespaciada, alineadas a la derecha y tabulares; contenedor con scroll horizontal y radio de 14 px; `caption` descriptivo.

### 2.6 Contraste (WCAG AA, mínimo 4,5:1)

Cálculo: luminancia relativa L = 0,2126 R + 0,7152 G + 0,0722 B con canales linealizados; razón = (L claro + 0,05) / (L oscuro + 0,05). Calculado con un script de Python sobre cada par. Los colores no cambiaron al cambiar de referencia; se agregó el par nuevo de la cabecera de tabla (texto suave sobre `#E2E7EE`).

| Texto sobre fondo | Colores | Razón | AA |
|---|---|---|---|
| Texto / fondo de página | `#0B1B33` / `#F7F4EC` | 15,68 | sí |
| Texto / superficie | `#0B1B33` / `#FCFAF5` | 16,52 | sí |
| Texto / superficie secundaria | `#0B1B33` / `#EEE9DC` | 14,21 | sí |
| Texto / cebra | `#0B1B33` / `#F3EFE4` | 15,00 | sí |
| Texto / cabecera de tabla | `#0B1B33` / `#E2E7EE` | 13,86 | sí |
| Texto suave / cabecera de tabla | `#3E4C63` / `#E2E7EE` | 6,99 | sí |
| Texto suave / fondo | `#3E4C63` / `#F7F4EC` | 7,90 | sí |
| Texto suave / superficie | `#3E4C63` / `#FCFAF5` | 8,32 | sí |
| Texto suave / superficie secundaria | `#3E4C63` / `#EEE9DC` | 7,16 | sí |
| Texto suave / cebra | `#3E4C63` / `#F3EFE4` | 7,56 | sí |
| Enlace / fondo | `#1B4F8F` / `#F7F4EC` | 7,46 | sí |
| Enlace / superficie | `#1B4F8F` / `#FCFAF5` | 7,86 | sí |
| Blanco / encabezado | `#FFFFFF` / `#0B1B33` | 17,23 | sí |
| Azul-200 / encabezado | `#C9D6E6` / `#0B1B33` | 11,69 | sí |
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

Todas las combinaciones propuestas superan 4,5:1. Los textos de 11–12,5 px de la escala usan los pares ya calculados (texto, texto suave, estados), que superan el mínimo con margen.

## 3. Decisiones del responsable (texto literal)

Aprobación de la guía: 2026-10-07. Respuestas a las tres preguntas de la propuesta:

1. Aplicar la guía en la feature 013: **sí**.
2. "No cumple" con su rojo propio, distinto del acento: **sí**.
3. Verde y ámbar apagados para "cumple" y "no determinado": **sí**.

Decisión adicional, textual:

> "los estados no me gustan las pastillas preferiria un icono de color y que al pasar el mouse muestre el nombre asi son todos iguales"

Aplicada en la sección 2.2, en `tokens.css` (`--ev-icono-*`, `--ev-icono-tam`, `--ev-tooltip-*`) y en la matriz de `muestra.html`.

## 4. Pendiente

- El peso 600 de Barlow Condensed no está en el repositorio del responsable; solo se usa el 700. Si se lo quiere, habría que descargarlo.
- La aplicación de los tokens a las plantillas la hace una tarea de la feature 013.
