# Guía visual de EVALUON (feature 017)

Estado: versión de trabajo de T-309 (REQ-133). Reemplaza a la guía aprobada el 2026-10-07 (azules, beiges y Barlow Condensed; REQ-100). La versión final la cierra T-331.
Fuente de los valores: la maqueta aprobada `docs/diseno/mockup-017/comun/estilos.css`.
Archivos: `evaluon/static/diseno/tokens.css` (variables de los dos temas y alias), `evaluon/static/diseno/fuentes/` (tipografía alojada), `tests/journey/test_contraste.py` (calcula el contraste de cada par desde `tokens.css`).

## 1. Los dos temas

La estética es el modelo 2 de la ronda 3: negro, grises y blanco; verde lima solo para resaltar; cifras grandes; gráficos en colores levemente desaturados; pestañas en píldora. Hay dos temas con los mismos nombres de token:

- **Gris y blanco** (`:root`, el de inicio, modelo 1).
- **Negro** (`[data-theme="negro"]` en `<html>`, modelo 3). Declara `color-scheme: dark`.

La elección del usuario la guarda su perfil (REQ-134); el atributo lo pone la plantilla base (T-311).

### 1.1 Tokens

Los valores marcados con `*` no son los de la maqueta: se ajustaron para llegar a AA (sección 6).

| Token | Gris y blanco | Negro | Uso |
|---|---|---|---|
| `--bg` | `#FFFFFF` | `#0B0C0E` | Fondo de página |
| `--tile` | `#F4F4F4` | `#17181C` | Mosaico, panel, superficie |
| `--tile-h` | `#ECECEC` | `#1F2126` | Mosaico con el mouse encima o desplegado |
| `--line` | `#E2E2E2` | `#2A2C31` | Separadores y bordes de adorno |
| `--ink` | `#171A20` | `#F2F2F2` | Texto principal y datos grandes |
| `--ink-2` | `#5C5E62` | `#A3A5AA` | Texto secundario |
| `--ink-3` | `#6F6F6F` `*` | `#808288` `*` | Números tenues, separadores, borde de campo. Solo sobre `--bg` y `--tile` |
| `--lime` | `#C6F432` | `#C6F432` | Resaltado (sección 4) |
| `--on-lime` | `#171A20` | `#171A20` | Texto sobre el lima |
| `--btn` / `--on-btn` / `--btn-h` | `#171A20` / `#FFFFFF` / `#000000` | `#C6F432` / `#0B0C0E` / `#D4FF4A` | Acción principal |
| `--focus` | `#6F9108` `*` | `#C6F432` | Anillo de foco |
| `--nav-track` / `--nav-on` / `--nav-on-ink` / `--nav-ink` | `#F4F4F4` / `#171A20` / `#FFFFFF` / `#5C5E62` | `#17181C` / `#C6F432` / `#0B0C0E` / `#A3A5AA` | Pestañas en píldora |
| `--ok` `--no` `--nd` `--pe` `--ext` | `#5C9176` `*` `#BE6A64` `#A57F39` `*` `#7488A4` `*` `#8C7AB0` | `#62A080` `*` `#CC7B75` `#B98C39` `*` `#8094B0` `*` `#9A8AC0` | Estados y gráficos |
| `--s2` / `--s3` | `#868686` `*` / `#5C5E62` `*` | `#8A8C91` `*` / `#6A6D74` `*` | Series neutras de los gráficos |
| `--trk` | `#E2E2E2` | `#2A2C31` | Pista detrás de una barra |
| `--dark-tile` / `--dark-tile-ink` / `--dark-tile-2` | `#171A20` / `#FFFFFF` / `#B9BBBF` | `#C6F432` / `#0B0C0E` / `#2B3310` | Mosaico destacado |
| `--hdr` / `--hdr-ink` / `--hdr-ink-2` / `--hdr-hover` | `#171A20` / `#FFFFFF` / `#B9BBBF` / `#2A2D35` | `#0B0C0E` / `#F2F2F2` / `#A3A5AA` / `#1F2126` | **Transitorio hasta T-311.** Encabezado viejo (`header.top`): `secciones.css` fija en blanco el usuario, «Salir» y el selector, así que su fondo es oscuro también en el tema gris y blanco. T-311 lo retira con el encabezado único |
| `--accent` / `--accent-h` | `#8B1E2D` / `#6F1723` | `#B3263C` / `#8F1D30` | Acento de las páginas viejas (acción destructiva). No es del modelo 2; sale con ellas en T-331 |

Tintas de estado, iguales en los dos temas porque se calculan con `color-mix(in srgb, …)` sobre los tokens: `--X-bg` (el color al 20 %, 22 % para `--nd`, sobre `--bg`) y `--X-ink` (el color al 65 %, 55 % para `--nd`, sobre `--ink`), con `X` en `ok`, `no`, `nd`, `pe`, `ext`. Son el fondo y el texto de las etiquetas y avisos de estado.

Medidas de la maqueta: `--r` 18 px (mosaico), `--r-sm` 10 px, `--maxw` 78 rem, `--gap` 1 rem, curvas `--e-out` y `--e-io`.

### 1.2 Alias de los tokens viejos

Hasta T-331, los `--ev-*` siguen existiendo y apuntan a los tokens nuevos, para que las páginas que todavía no se migraron se lean bien en los dos temas. Equivalencias: `--ev-fondo` es `--bg`; `--ev-superficie`, `--tile`; `--ev-superficie-2`, `--tile-h`; `--ev-texto`, `--ink`; `--ev-texto-suave`, `--ink-2`; `--ev-borde`, `--line`; `--ev-borde-campo`, `--ink-3`; `--ev-enlace`, `--ink` (los enlaces se distinguen por el subrayado); `--ev-azul-*` y `--ev-beige-*` van a `--ink`, `--tile`, `--tile-h`, `--line` según el papel (`--ev-azul-200` y `--ev-azul-800`, que solo usa el encabezado viejo, van a `--hdr-ink-2` y `--hdr-hover`; `--ev-encabezado-fondo` y `-texto`, a `--hdr` y `--hdr-ink`); `--ev-rojo`, `--accent`; los estados (`--ev-cumple`, `--ev-nocumple`, `--ev-nodeterminado`, `--ev-pendiente`, `--ev-externo` y sus `-fondo`), a las tintas `--X-ink` y `--X-bg`; los `--ev-icono-*`, a `--ok`, `--no`, `--nd`, `--pe`. `test_contraste.py` verifica los alias en los dos temas. Las medidas, la escala tipográfica, los radios, las sombras y `--ev-icono-tam` (16 px) no cambian. `test_contraste.py` exige además que todo `var(--…)` de las hojas y plantillas esté definido en `tokens.css` o en su propio archivo.

## 2. Tipografía

- **Hanken Grotesk** variable, pesos 300 a 600, alojada en `evaluon/static/diseno/fuentes/` (subconjuntos `latin` y `latin-ext`; licencia SIL OFL 1.1 en `LICENCIA.txt`). Sin CDN ni servicios externos (P4). Token `--f`; la pila de reserva es la del sistema.
- Cifras con `font-variant-numeric: tabular-nums`.
- Títulos con peso 400 y espaciado negativo (`letter-spacing: -.025em`), interlineado 1,1; texto de 15 px con interlineado 1,5 (maqueta).
- **Barlow Condensed 700** sigue declarada mientras haya páginas viejas que la usen (`--ev-fuente-titulo`); la retira T-331. La familia del cuerpo viejo (`--ev-fuente`) ya es Hanken.

## 3. Estados de cumplimiento

Siguen siendo íconos de color con forma propia y el nombre al pasar el mouse o con el foco (decisión del 2026-10-07): círculo con símbolo blanco (tilde, cruz, signo de pregunta, reloj), un símbolo distinto por estado, nunca solo el color. Los colores salen de `--ok`, `--no`, `--nd`, `--pe` (y `--ext` para la información externa, que es una clase de requisito y no un estado). El símbolo blanco (`--ev-icono-simbolo`) tiene que llegar a 3:1 contra el círculo en los dos temas; por eso en el tema negro los círculos son un poco más oscuros que en la maqueta. El texto que nombra el estado usa `--X-ink` sobre `--X-bg`.

## 4. Regla del verde lima

El lima resalta, no decora ni estructura. Se usa en: pestaña activa (negro), contadores de las pestañas, avance de los procesos, la cifra más baja del orden económico, y la acción principal en el tema negro. Reglas:

1. El texto sobre el lima es siempre `--on-lime` (13,6:1).
2. El lima nunca va solo como único portador de información: va con una cifra o un texto al lado.
3. En el tema gris y blanco el lima casi no se distingue del fondo (1,1 a 1,3:1). Toda marca o relleno lima de un gráfico lleva un **contorno `--ink`** de 1,5 a 2 px (como el punto más bajo de la maqueta). En el tema negro el lima se distingue solo (12 a 15:1).
4. El anillo de foco del tema gris y blanco es el mismo verde oliva más oscuro (`--focus`), no el lima.

## 5. Gráficos

SVG con `fill` y `stroke` en `currentColor`; el color sale de una clase `g-ok`, `g-no`, `g-nd`, `g-pe`, `g-ext`, `g-lime`, `g-ink` o `g-mute`, que solo declara `color: var(--…)` (definición compartida 3 de `tasks.md`). Correspondencias: `g-ok`, `g-no`, `g-nd`, `g-pe`, `g-ext` con los tokens del mismo nombre; `g-lime` con `--lime` (con contorno, regla 3); `g-ink` con `--ink`; `g-mute` con `--s2`; `--s3` es la tercera serie neutra. Cada marca o serie llega a 3:1 contra `--bg`, `--tile` y `--tile-h` (un mosaico desplegado es `--tile-h`). Los textos del gráfico usan `--ink` o `--ink-2`; `--ink-3` no va sobre `--tile-h`. Las cifras del primer panel van en `--ink`.

## 6. Contraste (AA)

Cálculo: luminancia relativa L = 0,2126 R + 0,7152 G + 0,0722 B con canales linealizados; razón = (L claro + 0,05) / (L oscuro + 0,05). Las mezclas `color-mix` se calculan en sRGB como el navegador. `tests/journey/test_contraste.py` declara los pares y los calcula desde `tokens.css`: 133 en el tema gris y blanco y 132 en el negro, todos al 100 %. Mínimos: texto 4,5:1; íconos, marcas y gráficos 3:1; el texto sobre la foto del primer panel lo agrega T-321 (`PARES_FOTO`, en el peor píxel).

Una prueba de alteración demuestra que el test muerde: volver `--ink-3` al `#8E8E8E` de la maqueta, o `--nd` al `#C29A4F`, lo hace fallar.

Exentos y por qué: `--line` y `--trk` (adornos y pistas: la barra o la cifra dan el dato), la opacidad de los controles deshabilitados (WCAG los exime).

### 6.1 Valores ajustados respecto de la maqueta

Criterio: el menor cambio de tono (se mueve solo la luminosidad en HSL, sin tocar matiz ni saturación) hasta pasar con un margen mínimo de 0,05.

| Par | Maqueta | Final | Razón |
|---|---|---|---|
| `--ink-3` sobre `--bg` y `--tile`, claro (texto, 4,5:1) | `#8E8E8E`: 3,28 y 2,98 | `#6F6F6F`: 5,02 y 4,57 | El texto tenue (números de pasos, separadores del camino) debe leerse. Queda cerca de `--ink-2` (`#5C5E62`); la jerarquía se conserva por el peso y el tamaño |
| `--ink-3` sobre `--bg` y `--tile`, negro (texto, 4,5:1) | `#6E7076`: 3,95 y 3,58 | `#808288`: 5,09 y 4,62 | Ídem |
| `--nd` sobre `--tile`, claro (ícono, 3:1) | `#C29A4F`: 2,38 (2,21 sobre `--tile-h`) | `#A57F39`: 3,35 (3,12) | El ámbar claro no llegaba a 3:1; es el cambio más visible y queda más cerca del bronce |
| `--nd` negro (símbolo blanco, 3:1) | `#CFA963`: 2,21 | `#B98C39`: 3,06 | El símbolo blanco sobre el círculo pedía 3:1 |
| `--ok` claro (sobre `--tile-h`, 3:1) | `#5E9479`: 2,97 | `#5C9176`: 3,08 | Un mosaico desplegado es `--tile-h` |
| `--pe` claro (sobre `--tile-h`, 3:1) | `#7A8DA8`: 2,87 | `#7488A4`: 3,06 | Ídem |
| `--ok`, `--pe` negro (símbolo blanco, 3:1) | `#6FA88A`: 2,75; `#8D9FB8`: 2,70 | `#62A080`: 3,06; `#8094B0`: 3,10 | Símbolo blanco sobre el círculo |
| `--focus` claro (anillo, 3:1) | `#8DB80A`: 2,34 (1,98 sobre `--tile-h`) | `#6F9108`: 3,10 sobre `--tile-h` | El anillo de foco debía verse; es el mismo verde oliva, más oscuro |
| `--s2` claro (serie neutra, 3:1) | `#8E8E8E`: 2,77 sobre `--tile-h` | `#868686`: 3,08 | Ídem |
| `--s3` claro (serie neutra, 3:1) | `#C9C9C9`: 1,4 sobre `--tile-h` | `#5C5E62`: 6,50 sobre `--bg`, 5,91 sobre `--tile`, 5,50 sobre `--tile-h` | Un gris claro no puede llegar a 3:1 sobre un mosaico gris: la tercera serie pasa a ser un gris medio-oscuro, distinto de `--ink` (2,7:1 entre ambos) y de `--s2` (1,8:1). Cambia la lectura de ese gráfico: a revisar con el Coordinador |
| `--s3` negro (serie neutra, 3:1) | `#4A4C51`: 1,87 sobre `--tile-h` | `#6A6D74`: 3,11 | Ídem; `--s2` negro sube a `#8A8C91` para mantener la distancia entre las dos series |

Sin cambios, ya pasaban: `--ink`, `--ink-2`, `--no`, `--ext`, `--lime`/`--on-lime`, botón, pestañas, mosaico destacado y todas las tintas de estado (el texto `--X-ink` sobre `--X-bg` queda entre 5,0 y 7,7:1).

## 7. Historia

Las guías anteriores (013, aprobada el 2026-10-07: paleta de azules y beiges, Barlow Condensed, íconos de estado sin pastillas) quedan reemplazadas por esta; del 2026-10-07 se conserva solo la decisión de los íconos de estado (sección 3). El histórico completo está en el repositorio (`git log -- docs/diseno/guia-visual.md`).
