# ADR-0072 · Matriz de requisitos: queda en el modelo local; la etapa externa no pasa a aceptación

Estado: aceptado · Fecha: 2026-10-17 · Propuso: Coordinador (T-298, plan 016) · Decidió: responsable del proyecto (2026-10-17, «Apruebo el ADR-0072: la matriz queda en el modelo local y la plataforma externa sigue para el verificador. Integrá el PR 418.»)

## Contexto

El paso 3 de la feature 016 (REQ-121 a REQ-123; ADR-0066, 0067 y 0068) construyó una etapa externa que reemplaza la extracción, la completitud y el filtro de la matriz por pedidos a `claude-sonnet-5-5` sobre el pliego completo, detrás de una sola puerta de filtrado, con registro de cada pedido y tope de gasto en código (T-288 a T-292). La puerta de ajuste del plan (umbral 16) exigía, en los casos 00, 01, 02 y 06, que la propuesta externa **no fuera peor** que la local simplificada de T-286 en lista presente ni en filas firmes con pareja, y 0 pedazos sin sujeto; solo entonces se gastaba la corrida de aceptación en 03, 04 y 05 (umbrales 13 a 15). Se midió en dos rondas, las que admite ADR-0025.

**Ronda 1 (T-293, `matriz-externa-v1`, 00, 02 y 06; el 01 no cupo en el freno de etapa):** lista presente mejor en 00 (41/42 contra 39/42) y 06 (35/35 contra 34/35) y peor en 02 (93/97 contra 94/97); firmes con pareja por debajo de la local en los tres (90,6 / 95,3 / 86,7 % contra 93,3 / 96,2 / 95,8 %); 3 pedazos sin sujeto. Gasto 1,0025 USD. Hallazgos D-293-1 a D-293-6.

**Ajuste único (T-294):** `matriz-externa-v2` (opción que solo se permite no es fila; la cita trae la oración con su antecedente; la consulta externa del organismo es fila), guarda de código que baja a revisión toda fila cuya cita no tiene sujeto, un solo esquema de salida para que la completitud lea la caché, estimador del libro calibrado (ADR-0068 enmendado) y `medir_matriz --solo-externo`. Verificación plena: pasa.

**Ronda 2 y última (T-295, v2, los cuatro casos; el 01 con estimado propio por decisión del responsable):**

| Caso | Lista presente (externo contra local T-286) | Firmes con pareja | Pedazos | Puerta |
|---|---|---|---|---|
| 00 | 41/42 contra 39/42 | 90,6 % contra 93,3 % | 0 | no |
| 01 | **66/80 contra 78/80** | 86,2 % contra 91,1 % | 0 | no |
| 02 | **89/97 contra 94/97** | 90,7 % contra 96,2 % | 0 | no |
| 06 | 34/35 contra 34/35 | 82,8 % contra 95,8 % | 0 | no |

La puerta no se cumple en ninguno de los cuatro. Lo que la v2 arregló se ve (0 pedazos; la completitud lee la caché: 50 mil a 287 mil tokens leídos y 0 escritos; estimado del libro 1,2 a 1,4 veces el real sobre las cifras de T-293), pero apareció una regresión: en tramos de varias oraciones el modelo cita solo la primera y omite las demás, y 16 entradas de las listas pasan a faltantes (02 ×5, 06 ×1, 01 ×10; D-295-1). Además la regla del descuento y de la forma por el Portal se obedece de modo inconsistente (sobrantes 3, 8, 8 y 5 contra 2, 5, 3 y 1 de la local; D-295-2), la guarda baja el pedazo pero no lo une (D-295-3) y en el 01 seis filas de circular quedan sin el cambio ni la marca de revisión (REQ-031 9/15 contra 15/15 de la local; D-295-4). Gasto 1,6020 USD; total del paso 3 en el libro del clon 2,6045 USD de 10.

Lo que el externo hizo bien y conviene retener: citas literales ubicadas al 100 % (11.904 de 11.904 en la ronda 2); la presentación física sale como fila firme (la local la deja como sugerencia, D-286-1); lista presente igual o mejor en los pliegos chicos (00 y 06); tiempo de la propuesta 28 a 66 % menor; la plataforma (puerta, libro, lotes, caché, registro, línea «Etapas fuera del equipo») funcionó en 23 pedidos reales sin una fuga ni un pedido sin registrar.

## Alternativas

### A. La matriz queda en el modelo local; la etapa externa queda en el código, apagada por omisión (propuesta)

Es lo que el plan fija para este resultado («si no lo pasa tras las dos rondas, el externo no pasa a aceptación y queda local»). Se gana: la Comisión del piloto sigue con la matriz local medida (T-286, ADR-0071), sin gasto externo ni dependencia del proveedor para la matriz; la plataforma externa queda probada para el verificador del paso 4 y para una ronda futura. Se pierde: la presentación física firme y el menor tiempo del externo; los pliegos chicos, donde el externo recupera 1 entrada más, siguen con la local.

### B. Tercera ronda de ajuste

ADR-0025 la admite solo si se pierde un requisito o se viola un principio. El camino por omisión es la local, que no pierde nada: los requisitos (REQ-121 a REQ-123) están cumplidos por la plataforma y la decisión de usar o no la etapa es de medición. La regresión de D-295-1 es del externo, no del producto. Costaría otra ventana de GPU (1 h), otros 1,5 a 2,5 USD y un tercer ajuste de instrucción sobre los mismos cuatro casos, con 18 caracteres de margen en la v2 (ADR-0070).

### C. Externo solo para pliegos chicos (00 y 06)

Lista presente igual o mejor ahí, pero las firmes con pareja bajan también en 00 y 06 (90,6 y 82,8 %) y la puerta pedía los cuatro casos; sería decidir con 2 casos lo que el plan pidió decidir con 4.

### D. Externo con `claude-opus-5-5` (T-297)

El plan lo preveía solo si Sonnet pasaba la puerta 16 y fallaba el umbral 13 o 14 en aceptación. No pasó la puerta: T-297 se cierra sin correr. Nada indica que el modelo sea la causa de D-295-1 (la instrucción pide citar con el antecedente y el modelo cita menos oraciones).

## Decisión

Se elige **A** (decisión del responsable, 2026-10-17).

1. **La matriz de requisitos la propone el modelo local** con las instrucciones cortas y `reglas-v15` (ADR-0071). `EXTERNAL_STAGE_MATRIZ` queda en `local` por omisión; la etapa externa (`tenders/proposal/external.py`, `matriz-externa-v2`) queda en el código, cubierta por sus tests con el doble, para una ronda futura.
2. **La plataforma externa sigue vigente** (ADR-0066 a 0068, enmendado) para el verificador de citas del paso 4 y para cualquier etapa futura que una medición justifique (P4 1.6, ADR-0065).
3. **T-296 y T-297 se cierran sin correr.** Los casos 03, 04 y 05 quedan sin tocar para una aceptación futura.
4. **D-293-1 a D-293-6 y D-295-1 a D-295-6 pasan a la lista de revisión** como «ronda futura de la matriz externa», sin tarea asignada: si el responsable la pide, arranca con D-295-1 (citar todas las oraciones del tramo), D-295-2 (guarda de código para la opción que solo se permite) y D-295-3 (unir en código la oración que continúa), con los mismos cuatro casos y la misma puerta.
5. **Gasto:** el paso 3 costó 2,6045 USD (T-293 1,0025 y T-295 1,6020) más 0,0597 de la prueba de humo; se registra en `tasks.md` y queda en los libros de `evaluon_clon` y `evaluon_clon_humo`.

## Consecuencias

- Más fácil: cerrar el paso 3 sin cambiar nada del piloto; el paso 4 arranca sobre la evaluación local de referencia (T-286) con la plataforma ya probada.
- Más difícil: la presentación física sigue como sugerencia (D-286-1) hasta la lista de revisión; el tiempo de la matriz sigue siendo el local (unos 15 a 60 min por pliego).
- Para revertir: poner `EXTERNAL_STAGE_MATRIZ=externo` con la clave y el compose externo; no hay migración ni cambio de esquema.
