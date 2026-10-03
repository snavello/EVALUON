# Conjunto dorado de la feature 001 · borrador

Borrador para validar. Ningún caso tiene visto bueno: todos llevan `validado_por: pendiente` y `redactado_por: borrador asistido`. La respuesta esperada la valida una persona que conoce la materia (`evals/README.md`).

Fuentes: solo el anexo de la Disposición AFIP 247/2022 (`corpus/normativa/disp-afip-247-2022-anexo.pdf`), su cuerpo (`disp-afip-247-2022-original.htm`) y la Disposición AFIP 297/03 con su Anexo I (`disp-afip-297-2003-original.htm`). Cada `origen` transcribe el texto de la norma y se comprobó por programa que aparece tal cual en el texto extraído (salvo espacios y saltos de línea). En los casos sin respuesta, `origen` explica por qué no hay respuesta.

## Composición

| Grupo | Casos | Cantidad |
|---|---|---|
| Con respuesta en la 247/2022 (fecha desde 2023-01-01) | EV-001 a EV-015 | 15 |
| Con respuesta en la 297/03 (fecha entre 2003-06-14 y 2022-12-31) | EV-016 a EV-024 | 9 |
| Sin respuesta, fecha bajo la 247/2022 | EV-025 a EV-028 | 4 |
| Sin respuesta, fecha bajo la 297/03 | EV-029, EV-030 | 2 |
| Sin respuesta, fecha sin régimen (anterior a 2003-06-14) | EV-031 | 1 |
| **Total** | | **31** |

- Pares (REQ-020): EV-001 y EV-016; EV-003 y EV-017; EV-014 y EV-018.
- `aviso_modificatorias` verdadero: los 9 casos con respuesta en la 297/03. Falso: todos los demás.
- REQ-018 y REQ-019 (categorías y marco nacional): sin casos. No hay documentos de esas categorías en el corpus; quedan pendientes, a cubrir con casos sintéticos cuando se decida. `difieren` es falso en todos.

## Casos

| Id | Pregunta (resumida) | Régimen | Fecha | Esperado (resumido) | Cita | Pareja |
|---|---|---|---|---|---|---|
| EV-001 | Plazo de mantenimiento de oferta si el pliego no lo fija | 247/2022 | 2023-01-01 | 60 días corridos desde la apertura; prórroga automática | Anexo, art. 43 | EV-016 |
| EV-002 | Clases de garantías y porcentajes | 247/2022 | 2024-04-08 | Mantenimiento 5 %, cumplimiento 10 %, contragarantía por el adelanto | Anexo, art. 64 a) b) c) | |
| EV-003 | Plazo para integrar la garantía de cumplimiento | 247/2022 | 2024-03-15 | 10 días desde el perfeccionamiento, prorrogable | Anexo, art. 61 | EV-017 |
| EV-004 | ¿Garantía de oferta si se cotiza poco? | 247/2022 | 2025-07-21 | No, si la oferta no supera M 1.000 | Anexo, art. 66 f) | |
| EV-005 | Plazo para observar el dictamen de evaluación | 247/2022 | 2023-05-02 | 3 días; 1 día en contratación directa | Anexo, art. 57 | |
| EV-006 | Impugnación del acto de aprobación y efecto | 247/2022 | 2024-09-30 | 5 días; revisión en 5 días; no suspensiva | Anexo, art. 59 | |
| EV-007 | Multa por mora si el pliego no la prevé | 247/2022 | 2025-03-12 | 0,1 % por día hábil; tope 100 % | Anexo, art. 88 c) | |
| EV-008 | Sanciones aplicables | 247/2022 | 2023-08-14 | Apercibimiento, suspensión, inhabilitación | Anexo, art. 92 | |
| EV-009 | Modalidades de los procedimientos | 247/2022 | 2026-02-03 | Las ocho del art. 24 | Anexo, art. 24 a) a h) | |
| EV-010 | Garantía en orden de compra abierta | 247/2022 | 2024-06-17 | 5 % sobre máximo de unidades × precio unitario | Anexo, art. 24 b) | |
| EV-011 | Publicidad de la licitación pública | 247/2022 | 2023-10-09 | BO 2 días hábiles, 7 días corridos de antelación, más comunicaciones, invitaciones y difusión | Anexo, art. 33 a) | |
| EV-012 | ¿Se subsana la oferta económica sin firma? | 247/2022 | 2025-11-24 | No; desestimación sin subsanación | Anexo, art. 55 j) | |
| EV-013 | Orden de prelación de los documentos | 247/2022 | 2024-01-22 | Régimen, normas, pliego y circulares, oferta, muestras, adjudicación, orden de compra | Anexo, art. 7 | |
| EV-014 | ¿El pliego puede agregar causales de desestimación? | 247/2022 | 2025-02-10 | No (no subsanables) | Anexo, art. 55, anteúltimo párrafo | EV-018 |
| EV-015 | Aumento o disminución del contrato | 247/2022 | 2026-05-04 | Hasta 20 % sin conformidad; nunca más de 35 % | Anexo, art. 79 | |
| EV-016 | Plazo de mantenimiento de oferta si el pliego no lo fija | 297/03 | 2022-12-31 | 30 días desde la apertura; prórroga automática | Anexo I, art. 39 | EV-001 |
| EV-017 | Plazo para integrar la garantía de cumplimiento | 297/03 | 2019-08-20 | 8 días; si no, rescisión y pérdida de la garantía de oferta | Anexo I, art. 55 inc. 6) | EV-003 |
| EV-018 | ¿El pliego puede agregar causales de desestimación? | 297/03 | 2010-04-05 | Sí, expresa y fundadamente (inadmisibilidad) | Anexo I, art. 43 i) | EV-014 |
| EV-019 | Requisitos y plazo para impugnar la adjudicación | 297/03 | 2003-06-14 | 5 días y depósito del "cinco por mil (0,5 ‰)" de la oferta | Anexo I, art. 53 | |
| EV-020 | Multa por prórroga del plazo de entrega | 297/03 | 2012-09-10 | 1 % cada 7 días corridos o fracción mayor de 3 | Anexo I, art. 58 inc. 10) | |
| EV-021 | ¿Garantía de oferta en contratación directa? | 297/03 | 2016-03-01 | No | Anexo I, art. 55 inc. 3) d) | |
| EV-022 | Integración de la Comisión Evaluadora | 297/03 | 2008-11-17 | Mínimo 3 titulares: presidente y 2 vocales, de planta permanente | Anexo I, art. 48 | |
| EV-023 | Garantía en orden de compra abierta | 297/03 | 2014-05-26 | Garantía de adjudicación del 10 % sobre máximo × precio unitario | Anexo I, art. 25 inc. 3) b) | |
| EV-024 | Plazo para observar el acta de evaluación | 297/03 | 2021-07-05 | 3 días; 2 días en privadas y directas | Anexo I, arts. 50 y 21 f) | |
| EV-025 | Licencia por maternidad de una agente | 247/2022 | 2024-05-02 | No determinado (ajena) | — | |
| EV-026 | Alícuota general del IVA | 247/2022 | 2023-09-01 | No determinado (ajena) | — | |
| EV-027 | Monto máximo de la licitación privada | 247/2022 | 2025-06-30 | No determinado (remite al régimen jurisdiccional, no cargado) | — | |
| EV-028 | Integración de la Comisión Evaluadora | 247/2022 | 2024-11-11 | No determinado (remite a la normativa vigente, no cargada) | — | |
| EV-029 | Monto máximo de la contratación directa por monto | 297/03 | 2015-10-01 | No determinado (remite al régimen jurisdiccional, no cargado) | — | |
| EV-030 | Vencimiento de la DDJJ de ganancias | 297/03 | 2018-04-16 | No determinado (ajena) | — | |
| EV-031 | Plazo de mantenimiento de oferta | sin régimen | 2003-06-13 | No determinado (`no_regime_at_date`) | — | |

## Para mirar con atención

1. **EV-019, el depósito para impugnar.** La 297/03 dice "CINCO POR MIL (0,5 ‰)". Cinco por mil es 5 ‰ (0,5 %), así que la cifra en palabras y la cifra en número no coinciden. El esperado repite el texto. Hay que decidir qué dato exigir en `datos_clave`; quizás alguna de las modificatorias sin cargar lo corrigió.
2. **EV-024, el plazo para observar el acta de evaluación bajo la 297/03.** El art. 50 da 3 días, la pauta f) del art. 21 da 2 días en licitaciones privadas y contrataciones directas, y la pauta g) dice que en las contrataciones directas el acta puede no notificarse y "no será impugnable". El esperado toma el art. 50 y la pauta f). Conviene acotar la pregunta a la licitación pública, o aceptar la respuesta con los dos plazos.
3. **EV-027, EV-028 y EV-029: preguntas cercanas sin respuesta.** La norma no da la cifra ni la integración, pero sí remite a otra normativa (el régimen jurisdiccional o la "normativa vigente"). Un sistema que responda "lo fija el régimen jurisdiccional vigente" citando el artículo no inventa nada. Hay que decidir si eso cuenta como abstención correcta o como respuesta correcta. Se marcaron "no determinado" porque la pregunta pide una cifra o una integración que el corpus no tiene. En EV-028 el art. 50 sí dice quiénes no pueden integrar la Comisión; si se quiere un caso sin ambigüedad, se puede cambiar la pregunta a "¿Cuántos miembros tiene...?".
4. **EV-014 y EV-018, el par con respuestas opuestas.** La 247/2022 prohíbe agregar causales "no subsanables"; no dice nada de causales subsanables. La 297/03 habla de "inadmisibilidad", no de "desestimación". La pregunta usa "desestimar" en los dos casos para que sea la misma; verificar que la equivalencia sea aceptable.
5. **EV-016, el cómputo de los 30 días.** El art. 39 de la 297/03 no dice si los días son corridos o hábiles. Por su art. 8, los plazos se computan en días hábiles administrativos salvo disposición en contrario. El esperado dice "30 días" sin calificarlos; si se exige "hábiles", habría que sumar el art. 8 a `unidades`.
6. **Todos los casos de la 297/03 (EV-016 a EV-024).** Se responden con el texto original de 2003. Infoleg registra 32 modificatorias sin cargar; cualquiera puede haber cambiado un plazo o un porcentaje. Para la medición está bien, porque el sistema solo conoce ese texto; y el aviso de modificatorias existe por eso mismo. Lo que sí hay que revisar es cada caso cuando se cargue una modificatoria.
7. **`aviso_modificatorias` en los casos sin respuesta con fecha bajo la 297/03 (EV-029, EV-030).** Se marcó falso, porque una respuesta "no determinado" no muestra unidades de la 297/03 y la spec pide el aviso solo cuando se muestra una unidad. Confirmar que la pantalla no muestra unidades recuperadas cuando se abstiene.
8. **EV-026, una trampa.** El art. 41 de la 247/2022 menciona el IVA (la AFIP es consumidor final), pero no fija ninguna alícuota. Una respuesta que cite el art. 41 para dar una alícuota es incorrecta.
9. **EV-004, el valor del módulo.** El esperado se queda en "M 1.000". El valor en pesos del módulo lo fija la máxima autoridad (art. 99) y no está cargado.
10. **EV-012.** Solo exige el art. 55. El art. 38 remite al 55 para la oferta económica sin firma; si se quiere exigir también, hay que agregarlo a `unidades`.
11. **EV-031.** Es la misma pregunta que el par EV-001 y EV-016, pero no tiene `pareja`: el plan exige que los dos casos de un par citen normas distintas, y este no cita ninguna. Lo mismo pasa con EV-022 y EV-028.
12. **Las claves de `unidades`.** Están a nivel de artículo (`anexo/art-43`, `anexo-i/art-55`), y el inciso va en `cita.ubicacion`. Según el plan, cuando un caso nombra un inciso vale el artículo que lo contiene. No se usaron claves de inciso porque la forma de los puntos numerados dentro de incisos (por ejemplo, art. 33 a) 1.) no está fijada en el plan.
