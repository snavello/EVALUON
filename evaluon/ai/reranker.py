"""Cliente del servicio `reranker` (`bge-reranker-v2-m3` en `llama-server`, ADR-0003).

Una operación (plan 001, "Reordenamiento"):

- `rerank(query, documents)`: un pedido a `/v1/rerank` con la pregunta y todos los
  textos; devuelve un puntaje por texto, en el orden de `documents`. El servidor devuelve
  un valor sin escala fija (logit); el cliente lo lleva a un número entre 0 y 1 con la
  función sigmoide, la conversión que describen los autores del modelo. Ese número es el
  que se compara con `RERANK_THRESHOLD` y el que se registra.

Errores: `InputTooLongError` si un par pregunta y texto no entra en el contexto (HTTP 500
con `is too large to process`; falla el pedido entero, también los demás textos);
`ServiceTimeoutError` y `ServiceUnavailableError` (ver `evaluon.ai`).
"""

import math

from django.conf import settings

from evaluon.ai import post_json, unexpected

SERVICE = "reranker"


def sigmoid(value):
    """Función sigmoide, 1 / (1 + e^-x), sin desbordes para valores extremos."""
    # Se calcula siempre con la exponencial de un número no positivo, que no desborda.
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    z = math.exp(value)
    return z / (1.0 + z)


def rerank(query, documents):
    """Puntajes entre 0 y 1 de `query` contra cada texto de `documents`, en ese orden. Sin
    textos, lista vacía y sin pedido."""
    documents = list(documents)
    if not documents:
        return []
    body = {
        "model": settings.RERANKER_MODEL,
        "query": query,
        "documents": documents,
        "top_n": len(documents),
    }
    data = post_json(SERVICE, settings.RERANKER_URL, "/v1/rerank", body)
    try:
        by_index = {item["index"]: float(item["relevance_score"]) for item in data["results"]}
        raw = [by_index[i] for i in range(len(documents))]
    except (KeyError, TypeError, ValueError) as error:
        raise unexpected(SERVICE, "falta el puntaje de algún texto", error) from error
    return [sigmoid(value) for value in raw]
