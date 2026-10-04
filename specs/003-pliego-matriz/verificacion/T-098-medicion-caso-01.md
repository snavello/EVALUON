# T-098: medición de ajuste con el caso-01 (REQ-031, circulares)

Medición de **ajuste**, no de aceptación (spec 003, "Uso de los casos desde el 2026-10-04"). Lectura de solo lectura de la base real (`evaluon-app-1`, `python manage.py shell`): no se modificó nada, no se usó el modelo, no se corrió `medir_matriz`. Sin texto del pliego ni de las circulares: solo `M-NNN`, claves, documentos, sí/no y cuentas.

**Versiones comparadas.** Antes: versión 2 de `caso-01-medicion` (alta, corrida 10, instrucciones `matriz-circulares-v1`, resultado de T-094). Ahora: **versión 3** (alta, corrida 13, creada el 2026-10-04 19:36, corrida `20261004-193633-f08bfc4`, main `f08bfc4` con T-098), descartada, 425 requisitos (la versión 2 tenía 409). Las versiones 1 y 2 de T-094 y esta son las tres que hay en la base.

## Resultado por fila

Criterio: la fila muestra el texto original (cita del pliego) y el modificado (fuente de la circular), cita la circular con documento, ubicación y fecha, y aplica el efecto correcto.

| Fila | Ancla | Antes (v2) | Ahora (v3) |
|---|---|---|---|
| M-012 | `sec-i/7.5.4`, Circular 1 tramo `1` (modifica) | Cumple (R29) | **Cumple** (R29): efecto `modifica`, documento 17, tramo `1`, pág. 4, fecha 2026-07-15, cita original ligada; el texto vigente esperado está en la fuente. La fuente pasó de 218 a 777 caracteres: ahora trae toda la cláusula nueva de 7.5.4, no solo el recorte |
| M-013 | `sec-i/7.5.4`, tramo `1` (modifica) | Cumple (R30, fuente propia) | **No cumple como fila** (R30 sin ninguna fuente). **Regresión.** La fuente de R29 (777 caracteres) contiene también el texto vigente esperado para M-013, pero está ligada solo a la cita de R29 |
| M-025 | `sec-i/7.6.5`, tramo `2` (suprime) | Cumple (R48) | **Cumple** (R48): `suprime`, documento 17, tramo `2`, pág. 4, 2026-07-15, estado `quitado`, original presente |
| M-026 | `sec-i/7.6.5`, tramo `2` (suprime) | Cumple (R49) | **Cumple** (R49): igual. También R50 (otra cita de 7.6.5, no esperada como fila propia) con la misma fuente, igual que antes |
| M-029 | `sec-i/7.7.1`, tramo `3` (suprime) | No cumple (R55 sin fuente) | **No cumple** (R55 sin fuente). Sin cambio |
| M-044 | `sec-i/13.2` (modifica, Circular 1 sin clave numerada, pág. 1) | No cumple (R93 sin fuente) | **Parcial.** R93 ahora tiene 8 fuentes `modifica` de la Circular 1 (tramos `pre/p-17` pág. 1; `p-23`, `p-41` pág. 2; `p-47`, `p-53`, `p-59`, `p-65`, `p-71` pág. 3), fecha 2026-07-15, y todas contienen las nuevas fechas esperadas. Pero la cita original ligada es la cláusula 13.2 del pliego, no el anexo de fecha de visita que la lista espera como original. Y las 8 fuentes son una por línea de visita, no las 2 esperadas. R94 (también 13.2) sin fuente |
| M-015 | agrega la Circular 2 (`origen: circular`, `sec-i/7.5.5~2`) | No cumple (sin fila; tramos `no_ubicado` pendientes) | **Cumple como fila:** R424, origen `circular`, estado propuesto, con cita en el tramo `sec-i/no-ubicado-3` de la Circular 2 (documento 18, pág. 2). El tramo ya no queda pendiente: pasó a `requisitos`. La fila no lleva fuente (es el requisito agregado, no una modificación), por lo que la fecha de la Circular 2 (2026-07-16) no está en la fila sino en el documento |

**Cuenta de las 7 filas.** Antes: 4 cumplen (M-012, M-013, M-025, M-026), 3 no (M-029, M-044, M-015). Ahora: 4 cumplen (M-012, M-025, M-026, M-015), 1 parcial (M-044), 2 no (M-013 por regresión, M-029). Se gana M-015 y media M-044; se pierde M-013. Sin cambio en M-029.

## Ruido

| Medida | Antes (v2, alta) | Ahora (v3, alta) |
|---|---|---|
| Fuentes de circular en total | 142 (en 32 filas) | **100** (en 35 filas) |
| Fuentes por fila técnica (18 filas) | 7 en cada una (126) | **4 en cada una (72)** |
| Fuentes en filas formales y económicas | 16 | 28 |
| Requisitos de origen `circular` | 7 (todos de la Circular 1) | **23**: 20 de la Circular 1 (`pre/p-18` a `pre/p-73`) y 3 de la Circular 2 (R423, R424, R425) |
| Fuentes de la Circular 2 | 0 | 8 (`aclara`, fecha 2026-07-16) |

Detalle ahora:

- Las 72 fuentes de las filas técnicas siguen siendo ajenas (Circular 1, líneas de visita y similares): bajó el ruido en 54 fuentes, pero la causa persiste (4 por fila en vez de 7).
- Las 100 fuentes se reparten así: 72 en filas técnicas, 12 en las filas esperadas con circular (R29: 1; R48 a R50: 3; R93: 8), 8 de la Circular 1 en otras filas (formales 5, económicas 3) y 8 de la Circular 2 en R31 a R34.
- Fuentes pegadas a filas que no corresponden según la lista: las 72 técnicas, las 8 de la Circular 1 en otras filas formales y económicas, y 7 de las 8 de R93 (la lista espera 2). Las 8 de la Circular 2 (`aclara`) están en las 4 filas de la cláusula 7.5.5 (R31 a R34), que es la cláusula que la Circular 2 reemplaza según la nota de M-014; la lista no las trae como fuente, así que se informan aparte y no se cuentan como pegadas por error.
- Los 20 requisitos de origen `circular` de la Circular 1 son más que los 7 de antes y no corresponden a filas de la lista. R423 y R425 (Circular 2) tampoco están en la lista; solo R424 corresponde a M-015.

## Lectura

- T-098 hizo dos cosas visibles: la Circular 2 ya no se pierde (M-015 con fila) y las fuentes de las filas técnicas bajaron de 7 a 4 por fila. Una fila nueva más (M-044) recibe por primera vez las fechas nuevas.
- Costos: **M-013 perdió su fuente** (regresión; el contenido está en la fuente de R29) y los requisitos de origen `circular` pasaron de 7 a 23.
- Sin resolver: M-029 (tramo `3` de la Circular 1 sin fuente) y el original del anexo de visita en M-044.

Medido con lectura directa de la base; no se verificó la pantalla de la matriz.
