"""Cliente del servicio `embeddings` (`bge-m3` en `llama-server`, ADR-0003).

Dos operaciones (plan 001, "Recuperación" y "Conteo de tokens"):

- `embed(texts)`: un pedido a `/v1/embeddings` con todos los textos; devuelve un vector
  por texto, en el mismo orden. El servidor los entrega normalizados (entorno.md, T-003).
- `count_tokens(text)`: cantidad de tokens de `text` según `/tokenize` de este servidor.
  Es la cuenta de los pasajes de hasta `PASSAGE_MAX_TOKENS`.

Errores: `InputTooLongError` si un texto no entra en el contexto (HTTP 500 con
`is too large to process`; falla el pedido entero); `ServiceTimeoutError` y
`ServiceUnavailableError` (ver `evaluon.ai`).
"""

from django.conf import settings

from evaluon.ai import count_tokens_with, post_json, unexpected

SERVICE = "embeddings"


def embed(texts):
    """Vectores de `texts`, uno por texto y en el mismo orden. Sin textos, lista vacía y
    sin pedido."""
    texts = list(texts)
    if not texts:
        return []
    body = {"model": settings.EMBEDDINGS_MODEL, "input": texts, "encoding_format": "float"}
    data = post_json(SERVICE, settings.EMBEDDINGS_URL, "/v1/embeddings", body)
    try:
        by_index = {item["index"]: item["embedding"] for item in data["data"]}
        vectors = [by_index[i] for i in range(len(texts))]
    except (KeyError, TypeError) as error:
        raise unexpected(SERVICE, "falta el vector de algún texto", error) from error
    return vectors


def count_tokens(text):
    """Cantidad de tokens de `text` para `bge-m3`, según `/tokenize` de `embeddings`, sin
    los 2 tokens especiales que el modelo agrega a cada texto."""
    return count_tokens_with(SERVICE, settings.EMBEDDINGS_URL, text)
