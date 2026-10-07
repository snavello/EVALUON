# ADR-0045 · Recorrido del procedimiento: estado calculado, actualización por sondeo local y avance de los pedidos

Estado: aceptado · Fecha: 2026-10-07 · Decidió: responsable del proyecto (2026-10-07, al aprobar el plan 013)

## Contexto

La spec 013 pide una página de recorrido por procedimiento con el estado de cada etapa (REQ-066), el avance en vivo de lo que corre en segundo plano (REQ-067) y los pendientes de decisión con enlace a las pantallas existentes (REQ-068). Restricciones: no agregar datos (la spec dice "la página no agrega datos nuevos"), todo local y sin internet (P4, P5), simplicidad (P10) y no duplicar pantallas.

Hay tres decisiones difíciles de cambiar después sin tocar muchas pantallas: de dónde sale el estado de una etapa, cómo llega a la pantalla sin recargar, y de dónde sale el avance de un pedido.

Lo que la cola ya registra hoy (verificado en el código):

- `tenders_job` guarda tipo, estado, `started_at`, `finished_at` y `error`. No guarda avance.
- Evaluación: una `assessment_run` por oferta, guardada entera al terminar esa oferta (`evaluate.evaluate_offer`). Mientras una oferta se evalúa, que tarda minutos, no queda nada. El pedido (`assessment_request.offers`) dice cuántas ofertas son.
- Matriz: la propuesta (`MatrixRun`) se crea al pedirla y cada pedido al modelo (`RunStep`) se inserta al hacerse; la última pasada se ve en vivo.
- Ficha y lectura de documentos: se guardan al terminar. Durante el pedido solo se sabe que está en curso y desde cuándo.

## Alternativas

### 1. Estado de cada etapa

**A. Calculado al mostrar, a partir de lo registrado.** Una función por etapa mira los pedidos de la cola y las tablas existentes (versión de la matriz, fichas, resultados, decisiones). Se gana: cero tablas nuevas, no puede quedar desactualizado respecto de la verdad, se prueba con filas de prueba. Se pierde: cada vista repite consultas (se acota con las funciones que ya existen, por ejemplo `matrix_page`, y se mide el tiempo contra el umbral de 2 s).

**B. Guardado en una tabla de estado del procedimiento**, actualizada por cada servicio al cambiar algo. Se gana: lectura inmediata. Se pierde: hay que tocar los servicios de las features 003, 004, 008 y 012 (la spec lo deja fuera de alcance), y el estado guardado puede divergir del real sin que nadie lo note.

### 2. Actualización en vivo

**A. Sondeo desde la página** con un script propio de unas 30 líneas (`fetch` cada 5 s al mismo servidor, que devuelve el bloque HTML de las etapas, y se pausa si la pestaña está oculta). Se gana: sin dependencias, funciona en la red local sin internet, se prueba como cualquier vista. Se pierde: una consulta cada 5 s por pestaña abierta (con unos pocos usuarios, despreciable) y una demora de hasta 5 s.

**B. Conexión abierta (eventos del servidor o websocket).** Se gana: aviso inmediato. Se pierde: exige cambiar el servidor a uno asíncrono o sumar una librería de canales y su infraestructura; más piezas por una ganancia de segundos que la spec no pide (pide 10 s).

**C. Recarga automática de la página completa** (meta de refresco). Se gana: nada de script. Se pierde: pierde la posición en la pantalla y lo que la persona esté escribiendo, y vuelve a calcular todo cada vez.

### 3. Avance de un pedido en curso

**A. Solo lo que ya se registra:** tipo, tiempo transcurrido, "oferta k de N" en la evaluación, última pasada y cantidad de pedidos al modelo en la matriz. Se gana: nada que cambiar. Se pierde: la evaluación de una oferta (minutos) se ve como un solo paso, y la lectura y la ficha, solo como "en curso" con el reloj.

**B. Una columna `progress` (JSON) en `tenders_job`**, que el manejador actualiza con una función de la cola (`jobs.report`) en puntos que ya tiene (por requisito evaluado, por requisito de la ficha). Se gana: "requisito 14 de 40" en vivo. Se pierde: una migración en una tabla compartida y una línea en dos manejadores; el dato es descartable (no es registro de auditoría).

## Decisión (propuesta)

1. **Estado calculado al mostrar (1.A).** Cada etapa tiene una función de solo lectura que devuelve su estado (pendiente, en curso, a decidir, lista, con error), sus pendientes y los enlaces. Las reglas están en el plan 013. No se guarda estado.
2. **Sondeo local (2.A).** Un script propio, servido desde `static/`, pide cada 5 s el bloque de etapas. Sin librerías ni CDN.
3. **Avance en dos pasos (3.A y después 3.B).** El corte vertical usa solo lo registrado (3.A). Una tarea aparte y chica agrega la columna `progress` y el aviso desde los dos manejadores largos (3.B). Si el responsable prefiere no tocar la cola, la 013 se cumple con 3.A y la evaluación queda con avance por oferta.

## Consecuencias

- La 013 no cambia la lógica de ninguna etapa (fuera de alcance de la spec); lee lo que las otras features ya guardan.
- Cuando una feature cambie cómo registra sus estados (por ejemplo, un nuevo tipo de pedido), debe actualizar la función de su etapa; el test de los cinco momentos lo detecta.
- 3.B toca el esquema de `tenders_job`: va en una tarea que corre sola.
- Para revertir 2.A a otra técnica basta cambiar el script y la vista del bloque; el cálculo del estado no cambia. Para revertir 3.B se descarta la columna y las dos llamadas; la página vuelve a 3.A.
