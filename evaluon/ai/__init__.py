"""Clientes HTTP de los tres servicios de IA (plan 001, "Servicios" y "Flujo de IA").

- `generation`: generar con esquema (`/v1/chat/completions`) y contar tokens
  (`/tokenize`) con el servidor de Gemma 4.
- `embeddings`: convertir textos en vectores (`/v1/embeddings`) y contar tokens
  (`/tokenize`) con el servidor de `bge-m3`.
- `reranker`: puntuar una pregunta contra una lista de textos (`/v1/rerank`), con el valor
  llevado a un número entre 0 y 1 por la función sigmoide.

Los tres hablan con `llama-server` (ADR-0002, ADR-0003) con `urllib` de la biblioteca
estándar. Direcciones, modelos y parámetros se leen de `settings.py` en cada llamada.

Errores propios, uno por cada falla técnica del plan ("Abstención" y "Forma de la
respuesta"); cada uno lleva en `reason` el motivo que se registra:

- `InputTooLongError` (`input_too_long`): el servidor rechazó la entrada por no entrar en
  el contexto. Nunca se recorta ni se reintenta.
- `ServiceTimeoutError` (`timeout`): no hubo respuesta dentro de `AI_TIMEOUT_SECONDS`.
- `ServiceUnavailableError` (`service_unavailable`): el servicio no responde, responde con
  otro error o con una respuesta que no tiene la forma esperada.

Ninguno es un "no determinado". La salida inválida del modelo (`invalid_output`) no la
decide el cliente: la generación devuelve la salida sin tocar y la valida quien la usa.

Las pruebas reemplazan los clientes por los dobles de `tests/conftest.py`. Por eso quien
los usa importa el módulo y llama a su función (`from evaluon.ai import generation`;
`generation.generate(...)`), nunca la función suelta (`from evaluon.ai.generation import
generate`), que el doble no alcanzaría.
"""

import json
import socket
import urllib.error
import urllib.request

from django.conf import settings

# Marcas del rechazo por entrada demasiado larga, medidas en la etapa 0 (entorno.md, T-002
# sección 9 y T-003 sección 5): `generation` responde HTTP 400 con ese `type`;
# `embeddings` y `reranker` responden HTTP 500 `server_error` con ese mensaje.
TOO_LONG_TYPES = ("exceed_context_size_error",)
TOO_LONG_MESSAGES = ("is too large to process", "exceeds the available context size")


class AIServiceError(Exception):
    """Falla técnica de un servicio de IA. `reason` es el motivo que se registra."""

    reason = "service_unavailable"

    def __init__(self, message, *, service, status=None, detail=None):
        super().__init__(message)
        self.service = service
        self.status = status
        self.detail = detail


class InputTooLongError(AIServiceError):
    """El servidor rechazó la entrada porque no entra en el contexto del modelo."""

    reason = "input_too_long"


class ServiceTimeoutError(AIServiceError):
    """El servidor no respondió dentro de la espera máxima."""

    reason = "timeout"


class ServiceUnavailableError(AIServiceError):
    """El servidor no responde, responde con error o con una respuesta inesperada."""

    reason = "service_unavailable"


def _is_timeout(error):
    return isinstance(error, (TimeoutError, socket.timeout))


def _rejection(service, status, raw):
    """Arma el error propio de una respuesta HTTP con código de error."""
    try:
        detail = json.loads(raw)
    except ValueError:
        detail = raw.decode("utf-8", errors="replace")[:2000]
    error = detail.get("error", {}) if isinstance(detail, dict) else {}
    if not isinstance(error, dict):
        error = {"message": str(error)}
    error_type = str(error.get("type", ""))
    message = str(error.get("message", ""))
    if error_type in TOO_LONG_TYPES or any(m in message for m in TOO_LONG_MESSAGES):
        return InputTooLongError(
            f"{service}: la entrada no entra en el contexto del modelo ({message})",
            service=service, status=status, detail=detail,
        )
    return ServiceUnavailableError(
        f"{service}: el servidor respondió HTTP {status} ({message or detail})",
        service=service, status=status, detail=detail,
    )


def post_json(service, base_url, path, body):
    """Envía `body` como JSON a `base_url + path` y devuelve la respuesta decodificada.

    Traduce toda falla a un error propio: entrada demasiado larga, espera agotada o
    servicio no disponible. No reintenta.
    """
    url = base_url.rstrip("/") + path
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    timeout = settings.AI_TIMEOUT_SECONDS
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        try:
            raw = error.read()
        except Exception:  # noqa: BLE001 - el cuerpo del error es solo informativo
            raw = b""
        raise _rejection(service, error.code, raw) from error
    except urllib.error.URLError as error:
        if _is_timeout(error.reason):
            raise ServiceTimeoutError(
                f"{service}: sin respuesta en {timeout} s ({url})", service=service
            ) from error
        raise ServiceUnavailableError(
            f"{service}: no responde ({url}: {error.reason})", service=service
        ) from error
    except (TimeoutError, socket.timeout) as error:
        raise ServiceTimeoutError(
            f"{service}: sin respuesta en {timeout} s ({url})", service=service
        ) from error
    except OSError as error:
        # Conexión cortada o rechazada a mitad del pedido (http.client y socket).
        raise ServiceUnavailableError(
            f"{service}: no responde ({url}: {error})", service=service
        ) from error

    try:
        return json.loads(raw)
    except ValueError as error:
        raise ServiceUnavailableError(
            f"{service}: la respuesta no es JSON ({url})", service=service
        ) from error


def unexpected(service, what, error=None):
    """Error propio para una respuesta con forma inesperada."""
    return ServiceUnavailableError(f"{service}: respuesta inesperada ({what})", service=service,
                                   detail=repr(error) if error else None)


def count_tokens_with(service, base_url, text):
    """Cuenta los tokens de `text` con `POST /tokenize` del servidor del modelo: la cantidad
    es el largo de la lista que devuelve, sin los tokens especiales del modelo (plan 001,
    "Conteo de tokens")."""
    data = post_json(service, base_url, "/tokenize", {"content": text, "add_special": False})
    try:
        tokens = data["tokens"]
        if not isinstance(tokens, list):
            raise TypeError("tokens no es una lista")
    except (KeyError, TypeError) as error:
        raise unexpected(service, "/tokenize sin lista de tokens", error) from error
    return len(tokens)


# Los módulos de cada cliente se importan al final: usan lo definido arriba.
from evaluon.ai import embeddings, generation, reranker  # noqa: E402

__all__ = [
    "AIServiceError",
    "InputTooLongError",
    "ServiceTimeoutError",
    "ServiceUnavailableError",
    "embeddings",
    "generation",
    "reranker",
]
