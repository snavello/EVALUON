# ADR-0066 · Cliente de la API externa (Anthropic) y salida a internet de la instancia que lo usa

Estado: aceptado · Fecha: 2026-10-15 · Propuso: planificador (plan 016) · Decidió: responsable del proyecto (2026-10-15, «Apruebo el plan 016 y los ADR 0066 a 0070»)

## Contexto

El ADR-0065 permite usar una API externa con lo público cuando una medición con umbral previo muestra que mejora la calidad, y la spec 016 (REQ-121 a REQ-124) pide hacerlo en dos etapas, la matriz y el verificador de citas, con un modelo de referencia: Claude Sonnet 5.5 (`claude-sonnet-5-5`), y Claude Opus 5.5 (`claude-opus-5-5`) solo como segunda comparación. Hace falta decidir cómo se habla con el proveedor y cómo sale la instancia a internet, sabiendo que esto es lo más difícil de revertir de la feature: una dependencia central y un cambio en la red.

Restricciones de la instalación:

- El `worker`, que corre las propuestas de matriz y las evaluaciones, está en la red `internal` (sin salida a internet). Solo `portal_worker` está en la red `egress` (ADR-0031), y `tests/portal/test_network.py` comprueba que ningún otro servicio la use. `app` tiene la red `web` (con salida, para publicar el puerto) y su garantía de no salir es de código (`tests/portal/test_no_outbound.py`).
- Todo cliente de red del proyecto usa `urllib` de la biblioteca estándar (`evaluon/ai/__init__.py`, `evaluon/portal/client.py`); la suite reemplaza los clientes de IA por dobles (T-011).
- Cada pedido debe quedar registrado (ADR-0065, punto 4) y el gasto, limitado (spec: 2 USD por caso y 10 USD por mes).

Datos del proveedor, consultados el 2026-10-15 (fuentes abajo): Sonnet 5.5, 2 USD por millón de tokens de entrada y 10 de salida, contexto de 1 millón de tokens, salida máxima de 128.000, retiro no anterior al 2027-09-28; Opus 5.5, 4 y 20; la API de lotes cuesta la mitad, procesa hasta 100.000 pedidos o 256 MB por lote, la mayoría termina en menos de una hora y vence a las 24 horas, y sus resultados se pueden bajar durante 29 días; la caché leída cuesta 0,05 veces el precio de entrada en Sonnet 5.5 y Opus 5.5, la escritura de 5 minutos 1,25 veces y la de una hora 2 veces, con un mínimo de 512 tokens, y el proveedor recomienda la de una hora para lotes con contexto común; la salida estructurada se pide con `output_config.format` de tipo `json_schema` (sin `minLength`, `maxLength` ni límites numéricos); el nivel de esfuerzo es `output_config.effort` (`high` por omisión en Sonnet 5.5, `medium` en Opus 5.5) y el pensamiento adaptativo se cobra como salida; `thinking: {"type": "between_tools"}` es el nivel más bajo de pensamiento previo en Sonnet 5.5.

## Alternativas

### A. Cliente propio con `urllib`, mensajes directos y lotes, anfitrión fijo, salida por un archivo de compose (propuesta)

Un módulo `evaluon/ai/external/client.py` con tres llamadas del proveedor (crear un mensaje, crear y consultar un lote, bajar sus resultados), el anfitrión `api.anthropic.com` escrito en el código, y un archivo `docker-compose.externo.yml` que le suma la red `egress` al `worker` y a `app` del clon y le pasa la clave. Sin ese archivo, no hay ruta a internet. Se gana: cero dependencias nuevas, el mismo estilo y las mismas pruebas que los demás clientes, un doble sencillo, y el apagado completo es no usar el archivo. Se pierde: hay que escribir y probar reintentos, errores y el manejo de lotes que un SDK ya trae; el `worker` queda con salida a internet mientras se use ese archivo (solo en el clon durante la feature).

### B. SDK oficial `anthropic` para Python

Se gana: tipos, reintentos, lotes y salida estructurada hechos y al día con la API. Se pierde: una dependencia central nueva (hay que reconstruir la imagen y fijarla), código de red de un tercero dentro del proceso del `worker` fuera del control de `test_no_outbound.py`, y la API del proveedor cambia con frecuencia (la página de modelos ya lista varias generaciones y parámetros que cambian de un modelo al siguiente, como el pensamiento y el esfuerzo). El doble pasaría a ser de un objeto grande en lugar de tres funciones.

### C. Servicio puente `external_gateway`, el único con salida

Un contenedor en `internal` y `egress` que recibe pedidos del `worker` por la red interna, aplica la puerta de filtrado, el registro y el tope, y los reenvía; el `worker` no sale nunca. Se gana: el mismo aislamiento que `portal_worker` (ADR-0031), la clave solo en un contenedor, y la puerta fuera del proceso que lee los documentos. Se pierde: un servicio más, una API interna, los lotes de hasta una hora obligan a consultas intermedias (cola o sondeo entre dos procesos), y todo eso para una medición. Queda como endurecimiento si una etapa externa se adopta para el piloto.

### D. Otra vía al mismo modelo (Amazon Bedrock, Google Cloud o Microsoft Foundry)

Se gana: facturación y contratos de una nube que ya se use. Se pierde: no hay cuenta ni contrato en ninguna de ellas, las condiciones de lotes, caché y salida estructurada cambian por plataforma y habría que medir de nuevo. No se justifica sin una razón de contrato que hoy no existe.

## Decisión

Se propone **A**, con estas reglas:

1. **Proveedor y modelos.** Anthropic. Referencia `claude-sonnet-5-5`; `claude-opus-5-5` solo como segunda comparación cuando Sonnet no pasa el umbral de la etapa. El identificador es una instantánea fija.
2. **Cliente.** `evaluon/ai/external/client.py`, con `urllib`. Anfitrión fijo y HTTPS en el código. `tests/portal/test_no_outbound.py` pasa a permitir exactamente ese archivo, además de `evaluon/ai/__init__.py` y `evaluon/portal/`; ningún otro módulo importa un cliente de red.
3. **Modo.** Las mediciones y todo lo que corre en segundo plano usan la API de lotes (mitad de precio). El modo directo existe para la prueba de humo con el caso chico y como camino de emergencia.
4. **Parámetros.** Esfuerzo y pensamiento fijados por etapa y registrados en cada pedido; `max_tokens` explícito; salida estructurada con `output_config.format`, validando los largos en el cliente; caché de una hora en el prefijo común.
5. **Apagado.** `EXTERNAL_ENABLED=false` por omisión; cada etapa (`EXTERNAL_STAGES`) elige `local` o `externo`, también `local` por omisión. Sin clave o sin habilitar, toda llamada falla con `ExternalDisabled` antes de abrir un socket, y la etapa sigue por el camino local.
6. **Salida a internet.** Solo con `docker-compose.externo.yml`, que suma la red `egress` y la clave a los contenedores del clon que corren etapas externas. El compose base no cambia. `tests/portal/test_network.py` sigue comprobando que el compose base solo le da `egress` a `portal_worker`.
7. **Clave.** En el `.env` del clon, fuera del repositorio; el espacio de trabajo de la consola del proveedor tiene un límite mensual de 10 USD.
8. **Pruebas.** El cliente tiene su doble (`FakeExternal` en `tests/conftest.py`) y un fixture automático impide toda llamada real dentro de la suite.

## Consecuencias

- Más fácil: comparar un modelo externo por etapa con el protocolo del ADR-0042; apagar lo externo sin tocar la arquitectura (constitución 1.6); medir con costo bajo gracias a los lotes.
- Más difícil: mantener tres llamadas del proveedor (si cambia su API, cambia el módulo); el `worker` del clon tiene salida a internet mientras dura la medición, protegido por el anfitrión fijo, por la puerta de filtrado (ADR-0067) y por la ausencia de clave en cualquier otro lugar; el externo no es determinista, así que cada pedido y su respuesta se guardan (ADR-0068) y las cifras se recalculan sin repetirlo.
- Para revertir: `EXTERNAL_STAGES` en `local` y no usar `docker-compose.externo.yml`; revocar la clave. Quitar el código es revertir el pull request; la migración de auditoría solo agrega un valor permitido.

## Fuentes

Consultadas el 2026-10-15 con una herramienta que resume las páginas:

- Modelos y precios: https://platform.claude.com/docs/en/about-claude/models/overview y https://platform.claude.com/docs/en/about-claude/pricing
- Lotes: https://platform.claude.com/docs/en/build-with-claude/batch-processing
- Caché de prompts: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Salida estructurada: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- Esfuerzo y pensamiento: https://platform.claude.com/docs/en/build-with-claude/effort
- Límites de gasto en la consola: https://docs.anthropic.com/en/api/rate-limits (los menús exactos varían; se confirman al crear la clave).

## Sin verificar

- La política de retención y de uso de los datos enviados por la API (el ADR-0065 ya clasifica lo público, pero no se leyó aquí la política del proveedor): debe confirmarla el responsable antes del primer pedido real.
- ~~Si estos modelos aceptan temperatura y semilla~~ Verificado por el Coordinador (2026-10-15, referencia de la API): Sonnet 5.5 y Opus 5.5 rechazan valores distintos del predeterminado en temperatura, `top_p` y `top_k`, y no hay semilla; `thinking: between_tools` solo se acepta con esfuerzo `high` o menor. El externo no es determinista: se guardan pedido y respuesta, como dice el plan.
- Si la caché se aprovecha dentro de un lote: el proveedor sugiere la de una hora para mejorar los aciertos en lotes, lo que indica que no están garantizados; el estimado de costo supone que no hay ninguno.
- El nivel de uso y los límites de velocidad de la organización con la que se cree la clave.
