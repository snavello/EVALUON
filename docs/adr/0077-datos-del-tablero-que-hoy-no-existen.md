# ADR-0077 · Datos que la maqueta usa y el sistema no tiene: monto estimado, vencimiento del mantenimiento y avance

Estado: aceptado · Fecha: 2026-10-21 · Propuso: Planificador (plan 017) · Decidió: responsable del proyecto (2026-10-21 21:57, «Apruebo el plan 017 con sus decisiones. Seguí con las tareas.»)

## Contexto

REQ-141 y P3: los tableros muestran solo datos que el sistema tiene; lo que no existe se muestra como «Falta» o «Pendiente», nunca con un valor inventado, y toda propuesta lleva su fundamento. La maqueta de la 017 usa tres datos que hoy no existen, y REQ-128, REQ-130 y REQ-131 los nombran:

1. **Monto estimado.** El Portal de Compras no lo publica en la página del proceso que lee el parser (`portal/parsing/pagina.py`), `PortalLine` no tiene precio y `Procedure` no tiene el campo. REQ-130 pide para cada oferta «cuánto se aparta del estimado».
2. **Vencimiento del mantenimiento de las ofertas.** El parser lee el plazo (`mantenimiento_oferta`, por ejemplo «60 Días corridos Acto de apertura») pero el importador no lo guarda en el procedimiento (`_FIELDS` de `portal/importers/procedure.py` no lo incluye); la página completa sí queda guardada (`PortalPage.content`, con su enlace y fecha de lectura). La apertura sí está en el cronograma (`PortalProcedureData.schedule`). REQ-131 pide «21/11 · vence el mantenimiento» y «faltan 31 días».
3. **Avance.** REQ-128 lo lista como dato principal; la maqueta muestra 76 % y barras por sección. Hoy hay estado por sección (pendiente, en curso, a decidir, lista, con error) y cuentas, pero no un porcentaje.

## Alternativas

### Monto estimado

**A. Solo «Falta».** Nada se carga; el mosaico dice «Falta el monto estimado» y REQ-130 muestra solo la diferencia con la más baja. Se gana: cero cambios de esquema. Se pierde: el estimado y la diferencia con él (parte de REQ-128 y REQ-130) nunca se muestran.

**B. Lo carga el evaluador desde el pliego, con respaldo (propuesta).** Un formulario chico en el detalle de «Datos del procedimiento» (importe, moneda, documento del pliego y cita literal de dónde sale), que guarda una fila en una tabla de solo inserción `tenders_procedure_estimate` con usuario y momento; se muestra como «Cargado por X el …, según el pliego» (la respuesta de una persona registrada es fundamento, P3). Se gana: el dato existe con fundamento y se puede corregir con una fila nueva sin perder la anterior. Se pierde: una tabla, un servicio y un formulario que la spec no describe (hay que aprobarlos); el dato lo tipea una persona (con su cita).

**D. No se usa: la oferta más alta y la más baja como indicadores (decidida por el responsable).** El orden económico y el primer panel muestran la oferta más alta y la más baja; cada oferta se compara con la más baja. Sin ofertas cargadas, el cuadro muestra el día de la apertura (cronograma) y «Pendiente». Se gana: cero cambios de esquema, nada se tipea y todo sale del acta del Portal. Se pierde: la comparación con el presupuesto oficial.

**C. Lo propone el sistema leyendo el pliego.** Extender la lectura del alta desde el pliego (ADR-0049) con un sexto dato y su cita verificada, y que el evaluador lo apruebe o corrija. Se gana: coherente con el alta, menos tipeo. Se pierde: ensancha una función de la 014 (que la 017 no puede cambiar) y exige medición con umbral previo; si se quiere, es una feature aparte.

### Vencimiento del mantenimiento

**A. Leerlo al vuelo de la última página guardada del proceso (propuesta).** Se lee `mantenimiento_oferta` con `parse_page` y se suma a la apertura del cronograma si el plazo es en días corridos contados desde el acto de apertura. Se muestra «Fuente: Portal, tomado el …». Si el plazo es en días hábiles (no hay calendario de feriados) o cuenta desde otro hecho, se muestra el plazo y «Falta el calendario»; sin página guardada o sin apertura, «Falta». Se gana: sin cambios de esquema ni de la 012; el fundamento (Portal, enlace y fecha) ya existe. Se pierde: analiza una página en cada carga del primer panel (se memoiza por pedido; si pasa de unos 150 ms, se pasa a B).

**B. Guardarlo en `portal_procedure_data` al explorar.** Se gana: lectura inmediata. Se pierde: cambia el importador de la 012 y el esquema, y los procedimientos ya cargados no lo tienen hasta la próxima revisión.

**C. Leerlo del requisito de la matriz («Mantenimiento de oferta por 60 días»).** Se gana: no depende del Portal. Se pierde: la matriz es una propuesta del modelo local, no un dato oficial; no es fundamento de P3.

### Avance

**A. Secciones en estado «lista» de las cinco (propuesta).** «2 de 5 secciones listas»; el mosaico «Avance por sección» muestra el estado de cada una con su ícono, pendientes y faltantes. Se gana: sale de datos que ya se calculan; no inventa pesos. Se pierde: es un avance grueso (cinco escalones), sin las barras porcentuales de la maqueta.

**B. Porcentaje ponderado por pendientes y faltantes.** Se gana: avance fino. Se pierde: hay que inventar qué pesa cada pendiente y cuál es el total; contradice REQ-141.

## Decisión

Monto estimado: **D**, decidida por el responsable el 2026-10-21: «tomamos la oferta maxima y la minima como indicadores, si aun no se cargaron las ofertas queda el cuadro con el dia y un indicador de pendiente». La spec se enmendó (REQ-128, REQ-130). B se descartó además porque haría tipear un dato, contra la decisión del 2026-10-07 de que nada se escribe desde cero. Se propone **vencimiento A** y **avance A**. Además, el denominador de documentos por oferta («23 de 27») y las menciones del pliego a normas («14 de 15») no existen y no se crean: se muestran la cantidad y los faltantes que el sistema sí conoce (hoja de compliance, anexos) y las normas distintas citadas en el encuadre legal. Las fechas de plazos que no existen (dictamen de la Comisión) se muestran «Pendiente».

## Consecuencias

- Más fácil: ningún tablero muestra un número sin respaldo; cada «Falta» dice qué dato falta y, cuando existe, cómo cargarlo.
- Más difícil: no hay comparación con el presupuesto oficial; si se quiere más adelante, va por C como feature aparte, con su medición.
- Para revertir: D no toca el esquema; el vencimiento tampoco; el avance es un cálculo.
