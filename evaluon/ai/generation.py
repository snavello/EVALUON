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

Errores: `InputTooLongError` si el pedido no entra en el contexto (HTTP 400
`exceed_context_size_error`); `ServiceTimeoutError` y `ServiceUnavailableError` (ver
`evaluon.ai`).
"""

from dataclasses import dataclass

from django.conf import settings

from evaluon.ai import count_tokens_with, post_json, unexpected

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
    """

    content: str
    finish_reason: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    request: dict
    response: dict


def build_request(messages, schema, max_tokens=None):
    """Cuerpo del pedido a `/v1/chat/completions` con los parámetros fijos de
    `settings.py` y el máximo de salida indicado (sin indicarlo, el de la 001). Lo usan
    el cliente y su doble, así el pedido registrado es el mismo."""
    if max_tokens is None:
        max_tokens = settings.GENERATION_MAX_OUTPUT_TOKENS
    return {
        "model": settings.GENERATION_MODEL,
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


def generate(messages, schema, *, max_tokens=None, base_url=None, timeout=None):
    """Pide al motor una respuesta que cumpla `schema` y la devuelve sin tocar.

    `max_tokens`, `base_url` y `timeout` cambian el máximo de salida, el servicio y la
    espera de este pedido; sin indicarlos, los de la 001."""
    body = build_request(messages, schema, max_tokens)
    data = post_json(SERVICE, base_url or settings.GENERATION_URL, "/v1/chat/completions",
                     body, timeout=timeout)
    return _result(data, body)


def build_text_request(messages, max_tokens, repeat_penalty):
    """Cuerpo de un pedido de texto libre (sin `response_format`): los mismos parámetros fijos
    de `settings.py` y la penalización de repetición indicada (T-177)."""
    body = build_request(messages, None, max_tokens)
    del body["response_format"]
    body["repeat_penalty"] = repeat_penalty
    return body


def generate_text(messages, *, max_tokens, repeat_penalty, base_url=None, timeout=None):
    """Pide al motor una respuesta de texto libre, sin esquema, con `repeat_penalty`, y la
    devuelve sin tocar. La usa la lectura con visión: con la salida JSON obligada, el modelo
    repetía guiones bajos hasta cortarse (T-177)."""
    body = build_text_request(messages, max_tokens, repeat_penalty)
    data = post_json(SERVICE, base_url or settings.GENERATION_URL, "/v1/chat/completions",
                     body, timeout=timeout)
    return _result(data, body)


def _result(data, body):
    try:
        choice = data["choices"][0]
        content = choice["message"]["content"]
        if not isinstance(content, str):
            raise TypeError("el contenido no es texto")
    except (KeyError, IndexError, TypeError) as error:
        raise unexpected(SERVICE, "sin choices[0].message.content", error) from error
    usage = data.get("usage") or {}
    return GenerationResult(
        content=content,
        finish_reason=choice.get("finish_reason"),
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        request=body,
        response=data,
    )


def generate_batch(messages, schema, *, max_tokens):
    """`generate` en el motor de los pedidos del `worker` (ADR-0018): `generation_batch`,
    o el que indique `GENERATION_BATCH_URL`, con su espera y el máximo de salida
    indicado."""
    return generate(
        messages,
        schema,
        max_tokens=max_tokens,
        base_url=settings.GENERATION_BATCH_URL,
        timeout=settings.GENERATION_BATCH_TIMEOUT_SECONDS,
    )


def count_tokens(text):
    """Cantidad de tokens de `text` para Gemma 4, según `/tokenize` de `generation`. No
    incluye lo que agrega la plantilla de conversación (lo cubre
    `PROMPT_TEMPLATE_MARGIN_TOKENS`)."""
    return count_tokens_with(SERVICE, settings.GENERATION_URL, text)
