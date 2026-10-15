# ADR-0067 · Un solo punto de filtrado de lo reservado antes de cualquier pedido externo

Estado: propuesto · Fecha: 2026-10-15 · Propuso: planificador (plan 016) · Decidió: —

## Contexto

El ADR-0065 y la constitución 1.6 (P4) dicen que lo público puede ir a una API externa cuando una medición lo justifica y que lo reservado nunca sale del equipo. Es reservada la hoja de compliance (documento de tipo `compliance`) y todo resultado de consultas de cumplimiento tributario, previsional, de sanciones o de deuda sobre un oferente, «vengan en una hoja de compliance, en un informe de consultas o en una respuesta de la Comisión que los transcriba». P9 agrega que esas verificaciones se cargan como hojas y que el sistema no las infiere. La spec 016 (REQ-121) exige que ningún pedido externo contenga un documento de ese tipo ni un fragmento que provenga de uno, y que los requisitos que dependen de esas consultas se evalúen siempre en el modelo local.

Cómo está hoy el código (leído para este ADR):

- Una hoja de compliance cargada es un documento más de la oferta: `assessment/externals.py` deja de aplicar la regla de «falta la hoja» y el requisito se evalúa por lectura con su cita, con lo cual el texto de la hoja entra a los grupos de documentos, a las citas y al contraste.
- El tipo de un documento de la oferta (`offers.DocumentKind`) lo pone el sistema por reglas, salvo la hoja y el informe técnico, que fija una acción de la Comisión; el tipo puede estar vacío si no se pudo clasificar. Hay un comando de reclasificación.
- Los requisitos que dependen de consultas externas se reconocen por un catálogo de expresiones (`externals.CATALOG`) y por la marca `externo` que escribe el modelo.
- Las respuestas de la Comisión a las preguntas entran como fundamentos `[R]` de los pedidos locales.

El riesgo es que un camino nuevo (la matriz externa, el verificador, o uno futuro) arme un pedido por su cuenta y se salte una regla.

## Alternativas

### A. Una sola puerta, `guard.py`, con lista permitida, exclusiones por contenido y comprobación por huellas (propuesta)

Todo texto que va a un pedido externo entra con el documento del que sale, y solo `guard.py` puede construir el objeto que el cliente acepta. Se gana: un único lugar para razonar, probar y auditar; un tipo de documento nuevo queda bloqueado hasta que alguien lo permita; la comprobación por huellas atrapa un documento mal clasificado. Se pierde: un poco de código y de falsos positivos (un pedido bloqueado por coincidir con un párrafo de la hoja cae al camino local).

### B. Lista prohibida: no mandar los documentos de tipo `compliance`

Se gana: es lo más simple. Se pierde: depende de que el tipo esté bien puesto (puede estar vacío o ser equivocado), no cubre un tipo nuevo ni los resultados de consultas que vengan en una respuesta de la Comisión ni los requisitos externos cuyo grupo cita otro documento, y cada etapa repetiría la regla.

### C. Filtrar en cada etapa donde se arma un pedido

Se gana: cada etapa conoce sus datos. Se pierde: la regla queda repartida en el flujo, y cada etapa nueva puede olvidarla; es el modo de falla que REQ-121 quiere evitar.

### D. Seudonimizar y mandar todo

Descartada por el ADR-0065 (alternativa C): no alcanza para lo reservado y destruye importes y fechas.

### E. No usar el externo con ofertas, solo con el pliego

Se gana: ninguna oferta sale y el riesgo desaparece. Se pierde: el verificador (paso 4) queda sin existir, y el responsable ya dijo que las ofertas no son reservadas.

## Decisión

Se propone **A**: `evaluon/ai/external/guard.py` es el único lugar que arma un pedido externo, y el cliente (ADR-0066) rechaza todo lo que no sea un `ExternalPayload` salido de ahí. Reglas:

1. **Lista permitida por tipo.** Se permiten los documentos del pliego, de sus anexos y de sus circulares y respuestas a consultas (`tenders.DocumentKind`) y los documentos de la oferta de tipo económico, técnico, garantía, anexo técnico, otro o sin clasificar. Todo tipo que no figure en la lista queda bloqueado, también uno nuevo. `compliance` nunca.
2. **Exclusiones por contenido.** Nunca van: las respuestas de la Comisión; el informe técnico del área (el ADR-0065 no lo clasifica: queda en local hasta que el responsable lo decida); los requisitos que dependen de consultas externas, por catálogo o por la marca del modelo, aunque la hoja esté cargada; y cualquier celda cuyo grupo de lectura o cuya cita haya salido de un documento `compliance`.
3. **Huellas.** Antes de mandar, la puerta compara el texto armado con los párrafos de los documentos `compliance` del procedimiento (secuencias de 8 palabras normalizadas, sin tildes ni mayúsculas); una coincidencia bloquea el pedido entero.
4. **Qué pasa al bloquear.** El pedido no sale, se registra como `bloqueado` sin texto (ADR-0068) y la etapa sigue por el camino local con la anomalía `externo_bloqueado`. Un bloqueo nunca baja la calidad de la celda: la deja como la dejó el modelo local.
5. **Cómo se prueba.**
   - `tests/ai/test_external_guard.py`, sin red: una hoja de compliance inventada, marcada con una palabra clave improbable en cada párrafo, cargada en una oferta de prueba; se evalúa con el uso externo encendido y el doble; ningún pedido registrado contiene un párrafo de la hoja ni la palabra clave, y los requisitos externos quedan en local. Además: un tipo desconocido, un documento sin clasificar con un párrafo de la hoja, una respuesta de la Comisión y un informe técnico.
   - Una prueba de humo con el proveedor real sobre el caso chico, con la misma hoja inventada.
   - `manage.py gasto_externo --verificar-filtro` escanea el registro de pedidos del clon con una implementación propia (independiente de `guard.py`) y cuenta los pedidos con texto de una hoja: el criterio de aceptación de REQ-121 es 0.
6. **Dónde se filtra en el flujo.** En la matriz, al armar el pedido de extracción y de completitud (el pliego no tiene hoja, pero pasa por la misma puerta). En la evaluación, al armar el pedido de cada celda del verificador, después de saber qué documentos sostienen la cita. Nada más sale de ninguna otra manera.

## Consecuencias

- Más fácil: demostrar P4 con una prueba y con un conteo sobre el registro; sumar una etapa externa sin repetir la regla; cambiar la lista de tipos permitidos en un solo archivo.
- Más difícil: toda etapa externa nueva tiene que construir su pedido con la puerta, aunque sea más lento de escribir; una clasificación mal puesta puede bloquear un pedido legítimo, lo que se ve en el registro como `bloqueado`.
- Queda abierto para el responsable: si el informe técnico del área puede ir a un modelo externo; si las respuestas de la Comisión que no transcriben consultas pueden ir (hoy no se distingue y no van).
- Para revertir: no hay nada que revertir en la práctica, porque con el uso externo apagado la puerta no se usa; quitarla exige quitar todas las etapas externas.
