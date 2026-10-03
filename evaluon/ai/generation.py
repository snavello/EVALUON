"""Cliente del servicio `generation` (Gemma 4 12B en `llama-server`, ADR-0002).

Dos operaciones (plan 001, "Generación" y "Conteo de tokens"):

- `generate(messages, schema)`: un pedido a `/v1/chat/completions` sin transmisión
  parcial, con temperatura, semilla, pensamiento y máximo de salida de `settings.py`, y la
  salida obligada a cumplir `schema` (`response_format` de tipo `json_schema`). Devuelve
  un `GenerationResult` con la salida sin tocar: no la interpreta ni la valida.
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


def build_request(messages, schema):
    """Cuerpo del pedido a `/v1/chat/completions` con los parámetros fijos de
    `settings.py`. Lo usan el cliente y su doble, así el pedido registrado es el mismo."""
    return {
        "model": settings.GENERATION_MODEL,
        "messages": messages,
        "stream": False,
        "temperature": settings.GENERATION_TEMPERATURE,
        "seed": settings.GENERATION_SEED,
        "max_tokens": settings.GENERATION_MAX_OUTPUT_TOKENS,
        "chat_template_kwargs": dict(settings.GENERATION_CHAT_TEMPLATE_KWARGS),
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": SCHEMA_NAME, "strict": True, "schema": schema},
        },
    }


def generate(messages, schema):
    """Pide al motor una respuesta que cumpla `schema` y la devuelve sin tocar."""
    body = build_request(messages, schema)
    data = post_json(SERVICE, settings.GENERATION_URL, "/v1/chat/completions", body)
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


def count_tokens(text):
    """Cantidad de tokens de `text` para Gemma 4, según `/tokenize` de `generation`. No
    incluye lo que agrega la plantilla de conversación (lo cubre
    `PROMPT_TEMPLATE_MARGIN_TOKENS`)."""
    return count_tokens_with(SERVICE, settings.GENERATION_URL, text)
