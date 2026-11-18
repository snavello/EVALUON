# ADR-0079 · Inicio de la aplicación: lista de abiertos calculada en el servidor y presupuesto de 2 segundos

Estado: aceptado · Fecha: 2026-11-17 · Propuso: Planificador (plan 018) · Decidió: responsable del proyecto (2026-11-17, al aprobar el plan 018)

## Contexto

REQ-150 y REQ-151: al entrar, la persona ve todos los procedimientos abiertos, cada uno con el estado de sus siete pasos, sus acciones y su vencimiento más próximo. El requisito no funcional pide 2 segundos o menos con 20 procedimientos abiertos. Hoy `/` redirige al último procedimiento visto (`views/inicio.py`) y la lista «Expedientes» (`views/portada.py` `lista`) calcula `sections_for` de **todos** los procedimientos, abiertos o no, y solo muestra pendientes y sugerencias.

El cálculo de un procedimiento (`sections_for` más la lectura de los siete pasos) son decenas de consultas y, para el vencimiento, la lectura de una página del Portal guardada (`tablero/ingreso.py` `_read_term`). Con 20 procedimientos se multiplica. No hay medición real todavía. Un procedimiento «terminado» (dictamen cargado) no necesita el cálculo de pasos, solo saberse terminado.

## Alternativas

### A. Servidor dibuja todo, un cálculo por procedimiento abierto, con medición y salida prevista (propuesta)
Dos consultas para todos los procedimientos separan abiertos y terminados (documentos de tipo dictamen vigentes y dictámenes del Portal aprobados). Para cada abierto se calcula `proceso_de` una vez, con su `memo.scope`. La lista llega completa en una respuesta. Se gana: es lo más simple (HTML del servidor, sin script, ADR-0076), funciona sin JavaScript y se prueba con tests de Django. Se pierde: el tiempo crece con los abiertos y no hay certeza de los 2 s sin medir.

### B. Dibujar la lista al instante y traer cada procedimiento por separado
La respuesta trae las filas con nombre y número y, por cada una, un bloque con `data-poll-url` que el sondeo ya existente (`recorrido.js`) completa con los pasos y las acciones. Se gana: la primera pantalla aparece en milisegundos y los procedimientos se completan en paralelo; ya hay mecanismo y política de contenido compatible. Se pierde: sin JavaScript la lista queda a medias; hay una ruta de fragmento más; el orden por vencimiento exige calcularlo antes (al menos el vencimiento) o reordenar en el cliente.

### C. Caché en memoria del resultado por procedimiento
Guardar `proceso_de` unos segundos. Se gana: lectura barata cuando se recarga. Se pierde: puede mostrar un estado viejo tras una decisión (la persona decide y vuelve al inicio y no ve el cambio), obliga a invalidar en cada servicio que cambia algo y agrega una capa que ningún requisito pide (P10).

## Decisión

Se propone **A**, con la medición como compuerta: en el corte vertical se mide el inicio con 20 copias del caso chico y, una vez, con el procedimiento real del piloto (mediana de 5 cargas; al repositorio solo cifras). Si la mediana pasa de 2 s, se pasa a **B** sin cambiar el cálculo (solo se parte la plantilla en fila y fragmento). **C** se descarta. Los terminados no se calculan: solo se listan.

## Consecuencias

- Más fácil: un solo cálculo por procedimiento, el mismo de la portada; lo que se ve en el inicio coincide siempre con la portada.
- Más difícil: el tiempo del inicio crece con la cantidad de abiertos; las costosas lecturas del Portal guardado se hacen por procedimiento y se memoizan por pedido.
- Para revertir o cambiar: pasar de A a B es partir `inicio.html` en fila y fragmento y sumar una ruta (`expedientes/<id>/fila/`); ninguna migración.
