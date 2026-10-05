# ADR-0033 · Revisión periódica: la hace el servicio del Portal, una vez por día hábil y a demanda

Estado: propuesto · Fecha: 2026-10-05 · Decidió: —

## Contexto

La spec 012 (REQ-050) pide revisar los procesos en curso una vez por día hábil y a demanda con un botón (decisión del responsable, 2026-10-05). La revisión explora de nuevo la página del proceso y propone solo lo nuevo o cambiado. Hace falta decidir quién la dispara. Ya hay una cola de pedidos (ADR-0018) y, por el ADR-0031, un servicio `portal_worker` que atiende los pedidos del Portal.

## Alternativas

### A. El bucle de `portal_worker` encola las revisiones que corresponden (elegida)

En cada vuelta, antes de tomar un pedido, `portal_worker` mira los enlaces en curso: si es día hábil (lunes a viernes, hora de Buenos Aires), ya pasó la hora de revisión (`PORTAL_REVIEW_HOUR`, por omisión 7) y el enlace no tiene revisión hecha ni pedida ese día, encola un pedido `portal_review`. El botón "Revisar ahora" encola el mismo pedido. La fecha de la última revisión se guarda en el enlace.

- Se gana: ninguna pieza nueva; si el servicio estuvo apagado, recupera el día al arrancar; la misma cola y el mismo aviso de fin; se prueba con un reloj inyectado.
- Se pierde: si el servicio está apagado todo el día, ese día no hay revisión (se hace al volver). No hay calendario de feriados: en un feriado también se revisa, sin daño (solo lee).

### B. Un programador aparte (cron en el equipo, o una biblioteca como APScheduler o Celery beat)

- Se gana: horarios exactos y calendarios.
- Se pierde: otro servicio o dependencia, otra configuración y otro punto de falla para una tarea de una vez por día (contra P10).

### C. El `worker` existente

- Se pierde: el `worker` no tiene salida a internet (ADR-0031) y es el que ocupa la GPU.

## Decisión

Se adopta **A**. Reglas:

1. "Día hábil" es de lunes a viernes; no se mantiene un calendario de feriados.
2. "En curso" es un enlace al que no se le puso fin: se le pone fin cuando se decide el ítem del dictamen (aprobado o rechazado) o a mano con un botón. Un enlace sin fin se revisa.
3. A lo sumo un pedido de revisión en espera o en curso por enlace; el botón no apila pedidos.
4. Si la revisión no puede leer la página, el pedido queda fallido con el motivo, se avisa a quien registró el enlace y no se descarta nada ya propuesto.

## Consecuencias

- Más fácil: un solo servicio con salida y un solo lugar que decide cuándo se consulta el Portal.
- Más difícil: la hora y el día hábil se prueban con reloj falso; un cambio de zona horaria del servidor rompería el horario (se usa `TIME_ZONE` de la aplicación).
- Para revertir: pasar el disparo a un programador externo; la revisión es un pedido de la cola y no cambia.
