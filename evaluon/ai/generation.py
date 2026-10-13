"""Cliente del servicio `generation` (Gemma 4 12B en `llama-server`, ADR-0002).

Operaciones (plan 001, "Generación" y "Conteo de tokens"; plan 003, "Pedido"):

- `generate(messages, schema, max_tokens=None, base_url=None, timeout=None)`: un pedido
  a `/v1/chat/completions` sin transmisión parcial, con temperatura, semilla y
  pensamiento de `settings.py`, y la salida obligada a cumplir `schema`
  (`response_format` de tipo `json_schema`). Devuelve un `GenerationResult` con la salida
  sin tocar: no la interpreta ni la valida. Sin los tres argumentos opcionales es el
  pedido de la 001: máximo de salida `GENERATION_MAX_OUTPUT_TOKENS`, servicio
  `GENERATION_URL` y espera `AI_TIMEOUT_SECONDS`.
- `generate_batch(messages, schema, max_tokens)`: lo mismo, en el motor de los pedidos
  del `worker` (`GENERATION_BATCH_URL`, ADR-0018) con su espera
  (`GENERATION_BATCH_TIMEOUT_SECONDS`) y el máximo de salida indicado. Llama a
  `generate`, así el doble de las pruebas la alcanza.
- `count_tokens(text)`: cantidad de tokens de `text` según `/tokenize` de este servidor.
- `count_tokens_batch(text)`: lo mismo, con el servidor del motor de lotes
  (`GENERATION_BATCH_URL`): los pedidos de lotes cuentan con el tokenizador del modelo que los
  va a responder (T-251; con otro modelo en lotes, el de `generation` daría otra cuenta).

El cuerpo registrado de un pedido dice el alias del modelo del motor al que va (`model_for`): el
de `generation` por omisión, el de `generation_batch` si va a `GENERATION_BATCH_URL` (T-251, P6).

Un solo motor (ADR-0057, T-255): con `GENERATION_URL` igual a `GENERATION_BATCH_URL`
(docker-compose.consulta-27b.yml) la Consulta de normativa pide al mismo motor, y al mismo modelo,
que las evaluaciones y las matrices (`shares_batch_engine`). Ese motor atiende de a un pedido
(`--parallel 1`), así que mientras corre un trabajo de lotes la Consulta espera detrás de él; las
pantallas lo evitan con un aviso (`queries/services.py`, `consulta_notice`). Los pedidos de la
Consulta (`generate`, sin `reasoning`) salen siempre con el pensamiento apagado, aunque el servidor
lo permita por el razonamiento de los pasos de lotes, y esperan `AI_TIMEOUT_SECONDS`, no la espera
extra de un paso que piensa.

Razonamiento propio del modelo (T-253, REQ-107): `generate_batch(..., step=…)` pide pensar si el
paso (`settings.GENERATION_BATCH_REASONING_STEPS`) está encendido en
`settings.GENERATION_BATCH_REASONING`; solo el motor de lotes lo hace. Encendido, el pedido lleva
`chat_template_kwargs.enable_thinking`, el nivel (`reasoning_effort`), el tope de tokens de
razonamiento (`thinking_budget_tokens`), el máximo de salida más ese tope y más espera. El
servidor tiene que permitir pensar (`--reasoning auto --reasoning-budget -1`;
docker-compose.razonamiento.yml): con `--reasoning off` ignora el pedido. El esquema JSON obliga
al contenido, no al razonamiento (que vuelve aparte en `reasoning_content`). El resultado guarda
el texto y los tokens del razonamiento (`GenerationResult.reasoning_record`). Apagado, el pedido
es el de siempre.

Errores: `InputTooLongError` si el pedido no entra en el contexto (HTTP 400
`exceed_context_size_error`); `ServiceTimeoutError` y `ServiceUnavailableError` (ver
`evaluon.ai`).
"""

from dataclasses import dataclass

from django.conf import settings

from evaluon.ai import AIServiceError, count_tokens_with, health_ok, post_json, unexpected

SERVICE = "generation"

# Nombre del esquema en el pedido; el motor lo exige y no cambia la salida.
SCHEMA_NAME = "response"


@dataclass(frozen=True)
class GenerationResult:
    """Resultado de un pedido de generación.

    - `content`: la salida del modelo, sin tocar (texto que debería ser el JSON del
      esquema; puede venir cortada o inválida).
    - `finish_reason`: `stop` si terminó solo; `length` si llegó al máximo de salida.
    - `prompt_tokens`, `completion_tokens`: cuentas que informa el servidor.
    - `request`: el cuerpo del pedido tal como se envió, para el registro.
    - `response`: la respuesta del servidor completa, para el registro.
    - `reasoning`, `reasoning_tokens`, `reasoning_level`: el razonamiento propio del modelo
      (`reasoning_content`), su cantidad de tokens según el servidor y el nivel con que se pidió;
      `reasoning_level` es `None` si el pedido no pidió pensar (T-253).
    """

    content: str
    finish_reason: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    request: dict
    response: dict
    reasoning: str = ""
    reasoning_tokens: int | None = None
    reasoning_level: str | None = None

    def reasoning_record(self):
        """Lo que se guarda del razonamiento en el `parsed` del pedido (P6): `None` si el pedido no
        pidió pensar; si lo pidió, el nivel, el texto (vacío si el modelo no devolvió ninguno) y
        sus tokens (`None` si el servidor no pudo contarlos)."""
        if self.reasoning_level is None:
            return None
        return {"nivel": self.reasoning_level, "texto": self.reasoning,
                "tokens": self.reasoning_tokens}


def _same_url(a, b):
    return (a or "").rstrip("/") == (b or "").rstrip("/")


def shares_batch_engine():
    """¿La Consulta (`GENERATION_URL`) va al mismo motor que los pedidos del `worker`
    (`GENERATION_BATCH_URL`)? Es la configuración de un solo motor (ADR-0057, T-255): el 27B atiende
    evaluaciones, matrices y Consulta, de a un pedido. Con `generation` aparte (la instalación de
    la 001 a la 014 y la vuelta al 12B) es falso y los trabajos de lotes no ocupan a la Consulta."""
    return _same_url(settings.GENERATION_URL, settings.GENERATION_BATCH_URL)


def model_for(base_url=None):
    """El alias del modelo del motor al que va el pedido (T-251, P6): el de
    `GENERATION_BATCH_MODEL` si `base_url` es `GENERATION_BATCH_URL` y es otro motor que
    `generation`; en cualquier otro caso (sin dirección, `GENERATION_URL` o un solo motor), el
    de `GENERATION_MODEL`."""
    if (base_url and _same_url(base_url, settings.GENERATION_BATCH_URL)
            and not _same_url(base_url, settings.GENERATION_URL)):
        return settings.GENERATION_BATCH_MODEL
    return settings.GENERATION_MODEL


def build_request(messages, schema, max_tokens=None, base_url=None, reasoning=None):
    """Cuerpo del pedido a `/v1/chat/completions` con los parámetros fijos de
    `settings.py` y el máximo de salida indicado (sin indicarlo, el de la 001). El `model` es
    el del motor al que va (`base_url`, ver `model_for`). Lo usan el cliente y su doble, así el
    pedido registrado es el mismo.

    `reasoning` es el nivel (`low`, `medium` o `high`) con que se pide al modelo que piense
    (T-253): enciende `enable_thinking`, manda el nivel y el tope de tokens de razonamiento de ese
    nivel, y suma ese tope al máximo de salida. Sin `reasoning`, el pensamiento va apagado."""
    if max_tokens is None:
        max_tokens = settings.GENERATION_MAX_OUTPUT_TOKENS
    body = {
        "model": model_for(base_url),
        "messages": messages,
        "stream": False,
        "temperature": settings.GENERATION_TEMPERATURE,
        "seed": settings.GENERATION_SEED,
        "max_tokens": max_tokens,
        "chat_template_kwargs": dict(settings.GENERATION_CHAT_TEMPLATE_KWARGS),
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": SCHEMA_NAME, "strict": True, "schema": schema},
        },
    }
    if reasoning:
        budget = settings.GENERATION_BATCH_REASONING_BUDGET_TOKENS[reasoning]
        body["chat_template_kwargs"]["enable_thinking"] = True
        body["reasoning_effort"] = reasoning
        body["thinking_budget_tokens"] = budget
        body["max_tokens"] = max_tokens + budget
    return body


def reasoning_level(step):
    """El nivel de razonamiento propio encendido para `step` en el motor de lotes (`low`,
    `medium` o `high`), o `None` si está apagado o no hay paso. Un paso que no es uno de
    `settings.GENERATION_BATCH_REASONING_STEPS` es un error de quien llama."""
    if step is None:
        return None
    if step not in settings.GENERATION_BATCH_REASONING_STEPS:
        raise ValueError(f"paso de razonamiento desconocido: {step!r}")
    level = settings.GENERATION_BATCH_REASONING.get(step, "off")
    return None if level == "off" else level


def generate(messages, schema, *, max_tokens=None, base_url=None, timeout=None, reasoning=None):
    """Pide al motor una respuesta que cumpla `schema` y la devuelve sin tocar.

    `max_tokens`, `base_url` y `timeout` cambian el máximo de salida, el servicio y la
    espera de este pedido; sin indicarlos, los de la 001. `reasoning` pide al modelo que piense
    con ese nivel (ver `build_request`); lo manda `generate_batch`, no la consulta de normativa."""
    body = build_request(messages, schema, max_tokens, base_url, reasoning)
    data = post_json(SERVICE, base_url or settings.GENERATION_URL, "/v1/chat/completions",
                     body, timeout=timeout)
    return _result(data, body, reasoning, base_url)


def build_batch_request(messages, schema, max_tokens=None, step=None):
    """`build_request` de un pedido al motor de lotes: lleva el alias de su modelo y, si el
    razonamiento de `step` está encendido, lo que pide pensar. Lo usan los llamadores de los
    lotes para registrar el pedido que no llegó a salir (T-251, T-253)."""
    return build_request(messages, schema, max_tokens, settings.GENERATION_BATCH_URL,
                         reasoning_level(step))


def build_text_request(messages, max_tokens, repeat_penalty, base_url=None):
    """Cuerpo de un pedido de texto libre (sin `response_format`): los mismos parámetros fijos
    de `settings.py` y la penalización de repetición indicada (T-177)."""
    body = build_request(messages, None, max_tokens, base_url)
    del body["response_format"]
    body["repeat_penalty"] = repeat_penalty
    return body


def generate_text(messages, *, max_tokens, repeat_penalty, base_url=None, timeout=None):
    """Pide al motor una respuesta de texto libre, sin esquema, con `repeat_penalty`, y la
    devuelve sin tocar. La usa la lectura con visión: con la salida JSON obligada, el modelo
    repetía guiones bajos hasta cortarse (T-177)."""
    body = build_text_request(messages, max_tokens, repeat_penalty, base_url)
    data = post_json(SERVICE, base_url or settings.GENERATION_URL, "/v1/chat/completions",
                     body, timeout=timeout)
    return _result(data, body)


def _reasoning_tokens(text, base_url):
    """Tokens del razonamiento según `/tokenize` del servidor que lo generó; `None` si no puede
    contarlos (la respuesta ya generada no se pierde por eso)."""
    if not text:
        return 0
    try:
        return count_tokens_with(SERVICE, base_url or settings.GENERATION_URL, text)
    except AIServiceError:
        return None


def _result(data, body, reasoning=None, base_url=None):
    try:
        choice = data["choices"][0]
        content = choice["message"]["content"]
        if not isinstance(content, str):
            raise TypeError("el contenido no es texto")
    except (KeyError, IndexError, TypeError) as error:
        raise unexpected(SERVICE, "sin choices[0].message.content", error) from error
    usage = data.get("usage") or {}
    thought = ""
    if reasoning:
        thought = choice["message"].get("reasoning_content") or ""
        if not isinstance(thought, str):
            thought = ""
    return GenerationResult(
        content=content,
        finish_reason=choice.get("finish_reason"),
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        request=body,
        response=data,
        reasoning=thought,
        reasoning_tokens=_reasoning_tokens(thought, base_url) if reasoning else None,
        reasoning_level=reasoning or None,
    )


def generate_batch(messages, schema, *, max_tokens, timeout=None, step=None):
    """`generate` en el motor de los pedidos del `worker` (ADR-0018): `generation_batch`,
    o el que indique `GENERATION_BATCH_URL`, con su espera (`timeout`, o la de los pedidos del
    `worker`) y el máximo de salida indicado.

    `step` es uno de `settings.GENERATION_BATCH_REASONING_STEPS`: si su razonamiento propio está
    encendido (`settings.GENERATION_BATCH_REASONING`), el pedido pide pensar y espera
    `GENERATION_BATCH_REASONING_EXTRA_TIMEOUT_SECONDS` más (T-253). Sin `step`, o apagado, el
    pedido es el de siempre."""
    level = reasoning_level(step)
    timeout = timeout or settings.GENERATION_BATCH_TIMEOUT_SECONDS
    options = {}
    if level:
        timeout += settings.GENERATION_BATCH_REASONING_EXTRA_TIMEOUT_SECONDS
        options["reasoning"] = level
    return generate(
        messages,
        schema,
        max_tokens=max_tokens,
        base_url=settings.GENERATION_BATCH_URL,
        timeout=timeout,
        **options,
    )


def count_tokens(text):
    """Cantidad de tokens de `text` para Gemma 4, según `/tokenize` de `generation`. No
    incluye lo que agrega la plantilla de conversación (lo cubre
    `PROMPT_TEMPLATE_MARGIN_TOKENS`)."""
    return count_tokens_with(SERVICE, settings.GENERATION_URL, text)


# Espera del chequeo de salud: la pantalla de la Consulta lo hace al mostrarse, así que no puede
# esperar lo que un pedido.
HEALTH_TIMEOUT_SECONDS = 2


def is_available(timeout=None):
    """¿Responde el motor de la Consulta? Verdadero si `GET /health` de `GENERATION_URL` contesta
    200 dentro de la espera (T-247). Falso si el servicio no existe, está apagado, está cargando el
    modelo (HTTP 503) o no contesta a tiempo. Con el Qwen3.8-27B en el motor de lotes y
    `generation` apagado (ADR-0057) `GENERATION_URL` es la dirección de `generation_batch` (T-255) y
    esto pregunta por él: el 27B tarda de 3 a 10 minutos en cargar y hasta entonces responde 503. La
    pantalla de la Consulta usa esto para decirlo en lugar de fallar. `/health` responde 200 aunque
    el motor esté generando (el chequeo de Docker lo hace cada 10 s durante una evaluación de
    horas), así que no dice si está ocupado con un pedido: eso lo dice la cola de trabajos
    (`queries.services.consulta_notice`). No lanza: cualquier falla es «no disponible», también una
    respuesta que no es HTTP (`BadStatusLine`, `IncompleteRead`, `LineTooLong`: son
    `http.client.HTTPException` y no `OSError`)."""
    return health_ok(settings.GENERATION_URL, timeout or HEALTH_TIMEOUT_SECONDS)


def count_tokens_batch(text):
    """Cantidad de tokens de `text` según `/tokenize` del motor de lotes
    (`GENERATION_BATCH_URL`): la que usan los pedidos de lotes, que los responde ese motor y no
    `generation` (T-251). Con el mismo modelo en los dos, da lo mismo que `count_tokens`. No
    incluye lo que agrega la plantilla de conversación."""
    return count_tokens_with(SERVICE, settings.GENERATION_BATCH_URL, text)
