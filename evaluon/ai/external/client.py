"""Cliente de la API externa de modelos (Anthropic) (ADR-0066; plan 016, "Plataforma externa").

Es el único módulo de EVALUON, fuera de `evaluon/portal/` y del cliente de los servicios de IA
(`evaluon/ai/__init__.py`), que abre una conexión a internet (`tests/portal/test_no_outbound.py`
permite exactamente este archivo). Con `urllib` de la biblioteca estándar, como los demás
clientes, y limitado así:

- el anfitrión es `api.anthropic.com`, escrito acá, y solo HTTPS: no es un ajuste ni sale de
  ningún dato; las redirecciones no se siguen (la clave no viaja a otro destino);
- la única entrada es un `ExternalPayload` (`payload.py`), que solo arma `guard.py` (T-290);
- antes de abrir un socket se comprueba que el uso esté habilitado: `EXTERNAL_ENABLED`, la
  etapa del pedido en `externo` (`EXTERNAL_STAGES`) y `ANTHROPIC_API_KEY` en el entorno. Si
  falta algo, `ExternalDisabled`. La clave se lee del entorno en cada llamada: no está en
  `settings`, no se guarda y no aparece en ningún error ni registro (P4);
- ninguna llamada reintenta un pedido que pudo haber trabajado: se reintenta solo lo que el
  proveedor rechazó antes de procesar (429 y 529) y, en las consultas que no cambian nada
  (estado y resultados de un lote), las fallas del servidor y de la conexión.

Operaciones (cada una recibe lo ya filtrado y devuelve lo que el registro necesita, ADR-0068):

- `send_message(payload)`: un mensaje directo (la prueba de humo y el camino de emergencia).
- `create_batch(payloads)`, `retrieve_batch(batch)`, `fetch_results(batch)`: las tres llamadas
  de la API de lotes.
- `cancel_batch(batch)`: pide al proveedor cancelar un lote (`POST .../{id}/cancel`).
- `run_batch(payloads)`: crea el lote, lo consulta cada `EXTERNAL_BATCH_POLL_SECONDS` hasta
  `EXTERNAL_BATCH_MAX_WAIT_SECONDS` y baja los resultados. Si la espera se agota, cancela el
  lote antes de lanzar `ExternalTimeoutError`, para que no siga gastando.

Errores propios, cada uno con el motivo que se registra en `reason`:

- `ExternalDisabled` (`external_disabled`): no está habilitado o falta la clave; no se conectó.
- `ExternalTimeoutError` (`timeout`): una llamada o la espera de un lote pasó su tiempo.
- `ExternalUnavailableError` (`service_unavailable`): el proveedor no responde o responde un
  error (incluidos 401, 429, 5xx).
- `ExternalInputTooLongError` (`input_too_long`): el pedido no entra en el contexto.
- `ExternalExpired` (`expired`): el proveedor venció el pedido (24 horas) sin procesarlo.
- `ExternalInvalidResponse` (`invalid_response`): la respuesta no tiene la forma esperada.

Un mensaje directo con falla lanza el error. En un lote, la falla de un pedido no pierde los
demás: queda en su `ExternalResult` con `outcome` distinto de `ok` y `raise_for_outcome()` lo
convierte en el error que corresponde.

Quien lo usa importa el módulo y llama a su función (`from evaluon.ai.external import client`;
`client.run_batch(...)`), nunca la función suelta: el doble de las pruebas (`FakeExternal`)
reemplaza las funciones del módulo.
"""

import json
import math
import os
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, replace

from django.conf import settings

from evaluon.ai.external.payload import ExternalPayload, stage_group

PROVIDER = "anthropic"
HOST = "api.anthropic.com"
BASE_URL = "https://" + HOST
API_VERSION = "2023-06-01"
KEY_ENV = "ANTHROPIC_API_KEY"
USER_AGENT = "EVALUON/1.0"

MESSAGE_TIMEOUT_SECONDS = 600     # un mensaje directo (con pensamiento puede tardar)
CALL_TIMEOUT_SECONDS = 60         # crear o consultar un lote
RESULTS_TIMEOUT_SECONDS = 300     # bajar los resultados de un lote
MAX_RETRIES = 2
RETRY_SECONDS = 5
MAX_RETRY_AFTER_SECONDS = 60     # tope de lo que el proveedor pida esperar
MIN_KEY_LENGTH_TO_SCRUB = 8

BATCH_STATUSES = ("in_progress", "canceling", "ended")
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_TOO_LONG_MARKERS = ("prompt is too long", "request_too_large", "exceeds the maximum",
                     "too many tokens")


# --- Errores ----------------------------------------------------------------------------------


def _scrub(value):
    """Reemplaza la clave del proveedor por `***` en un texto, o en los textos de un diccionario
    o una lista, antes de devolverlo (P4): si el proveedor la repitiera en un error, no
    llegaría al registro de auditoría, que es de solo inserción."""
    key = os.environ.get(KEY_ENV, "").strip()
    if len(key) < MIN_KEY_LENGTH_TO_SCRUB:
        return value
    if isinstance(value, str):
        return value.replace(key, "***")
    if isinstance(value, dict):
        return {_scrub(k): _scrub(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_scrub(v) for v in value)
    return value


class ExternalError(Exception):
    """Falla al usar la API externa. `reason` es el motivo que se registra.

    `canceled` es `None` mientras no se intentó cancelar el lote al que se refiere el error,
    y `True` o `False` según haya salido la cancelación. Los textos pasan por `_scrub`: la
    clave nunca queda en `str(error)` ni en `detail`."""

    reason = "service_unavailable"
    canceled = None

    def __init__(self, message, *, status=None, detail=None, batch_id=None):
        super().__init__(_scrub(message))
        self.status = status
        self.detail = _scrub(detail)
        self.batch_id = batch_id


class ExternalDisabled(ExternalError):
    """El uso externo no está habilitado para esta etapa o falta la clave; no se conectó."""

    reason = "external_disabled"


class ExternalTimeoutError(ExternalError):
    """No hubo respuesta a tiempo (una llamada o la espera de un lote)."""

    reason = "timeout"


class ExternalUnavailableError(ExternalError):
    """El proveedor no responde o responde con un error."""

    reason = "service_unavailable"


class ExternalInputTooLongError(ExternalError):
    """El proveedor rechazó el pedido porque no entra en el contexto del modelo."""

    reason = "input_too_long"


class ExternalExpired(ExternalError):
    """El proveedor venció el pedido sin procesarlo."""

    reason = "expired"


class ExternalInvalidResponse(ExternalError):
    """La respuesta del proveedor no tiene la forma esperada."""

    reason = "invalid_response"


# --- Resultados ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class ExternalUsage:
    """Tokens que informa el proveedor (el costo se calcula con ellos, ADR-0068)."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @classmethod
    def from_body(cls, usage):
        if not isinstance(usage, dict):
            raise ExternalInvalidResponse("La respuesta no trae el uso de tokens.")
        values = {}
        for name in ("input_tokens", "output_tokens", "cache_creation_input_tokens",
                     "cache_read_input_tokens"):
            value = usage.get(name) or 0
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ExternalInvalidResponse(f"El uso de tokens trae {name} inválido.")
            values[name] = value
        return cls(**values)


@dataclass(frozen=True)
class ExternalResult:
    """Lo que devuelve el proveedor para un pedido, con lo que el registro necesita.

    `outcome`: `ok`, `error`, `canceled` o `expired` (en un mensaje directo solo `ok`: el resto
    lanza). `text`, `model` (el que devuelve el proveedor), `stop_reason`, `usage`,
    `message_id`. `batch_id` (o `None` en el modo directo), `custom_id`, `mode` (`directo` o
    `lotes`). `request_body`: el cuerpo del pedido tal como salió (sin cabeceras ni clave).
    `response_body`: el mensaje completo del proveedor (`ok`) o su resultado de error.
    `error`: el detalle del error del proveedor. `duration_s`: lo que tardó el mensaje directo
    (en un lote, `None`: la duración es la del lote, en `BatchRun`). `request_sha256`: huella
    del pedido.
    """

    payload: ExternalPayload
    outcome: str
    text: str
    model: str
    stop_reason: str | None
    usage: ExternalUsage
    message_id: str | None
    batch_id: str | None
    custom_id: str
    mode: str
    request_body: dict
    response_body: dict
    error: dict | None = None
    duration_s: float | None = None
    request_sha256: str = ""

    @property
    def ok(self):
        return self.outcome == "ok"

    @property
    def reason(self):
        """Motivo para el registro: `ok`, `expired`, `input_too_long` o `service_unavailable`."""
        if self.outcome == "ok":
            return "ok"
        if self.outcome == "expired":
            return ExternalExpired.reason
        if self.outcome == "error" and _too_long(self.error):
            return ExternalInputTooLongError.reason
        return ExternalUnavailableError.reason

    def raise_for_outcome(self):
        """Devuelve el resultado si salió bien; si no, lanza el error que corresponde."""
        if self.ok:
            return self
        message = f"El pedido {self.custom_id} terminó en {self.outcome}: {self.error or ''}"
        error_class = {ExternalExpired.reason: ExternalExpired,
                       ExternalInputTooLongError.reason: ExternalInputTooLongError,
                       }.get(self.reason, ExternalUnavailableError)
        raise error_class(message, detail=self.error, batch_id=self.batch_id)


@dataclass(frozen=True)
class ExternalBatch:
    """Un lote en el proveedor. `status`: `in_progress`, `canceling` o `ended`.
    `request_body` es lo que se mandó al crearlo y `response_body`, la última respuesta del
    proveedor sobre él."""

    id: str
    stage: str
    status: str
    request_counts: dict
    payloads: tuple = field(repr=False)
    request_body: dict = field(repr=False)
    response_body: dict = field(repr=False)


@dataclass(frozen=True)
class BatchRun:
    """El lote terminado: `batch` (el último estado), `results` (`custom_id` → resultado, en
    el orden de los pedidos), cantidad de consultas y duración total en segundos."""

    batch: ExternalBatch
    results: dict
    polls: int
    duration_s: float


# --- Habilitación -------------------------------------------------------------------------------


def require_enabled(stage):
    """Devuelve la clave si la etapa `stage` puede salir; si no, lanza `ExternalDisabled`.

    Las tres condiciones juntas (O-288-3): el interruptor general, la etapa en `externo` y la
    clave en el entorno. No abre ningún socket.
    """
    group = stage_group(stage)
    if group not in settings.EXTERNAL_STAGE_NAMES:
        raise ExternalDisabled(f"La etapa {stage!r} no es una etapa que pueda usar lo externo.")
    if not settings.EXTERNAL_ENABLED:
        raise ExternalDisabled("El uso externo está apagado (EXTERNAL_ENABLED).")
    if settings.EXTERNAL_STAGES.get(group) != "externo":
        raise ExternalDisabled(f"La etapa {group!r} está en local (EXTERNAL_STAGES).")
    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        raise ExternalDisabled(f"Falta {KEY_ENV} en el entorno.")
    return key


# --- Transporte -------------------------------------------------------------------------------


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # la clave no viaja a otro destino: la redirección queda como error


_OPENER = urllib.request.build_opener(_NoRedirect)


def _urlopen(request, timeout):
    """Abre la conexión. Es el único punto que toca la red: la suite lo reemplaza
    (`tests/conftest.py`) y hace fallar toda llamada real."""
    return _OPENER.open(request, timeout=timeout)


def _now():
    return time.monotonic()


def _sleep(seconds):
    time.sleep(seconds)


def _is_timeout(error):
    return isinstance(error, (TimeoutError, socket.timeout))


def _too_long(error):
    if not isinstance(error, dict):
        return False
    text = f"{error.get('type', '')} {error.get('message', '')}".lower()
    return any(marker in text for marker in _TOO_LONG_MARKERS)


def _retry_after(error):
    """Segundos que pide esperar el proveedor (`retry-after`), acotados a
    `MAX_RETRY_AFTER_SECONDS`; lo que no sea un número finito y positivo cuenta como ausente."""
    try:
        seconds = float(error.headers.get("retry-after"))
    except (AttributeError, TypeError, ValueError):
        return None
    if not math.isfinite(seconds) or seconds <= 0:
        return None
    return min(seconds, MAX_RETRY_AFTER_SECONDS)


def _rejection(status, raw, retry_after=None):
    """Arma el error propio de una respuesta HTTP con código de error."""
    try:
        detail = json.loads(raw)
    except ValueError:
        detail = raw.decode("utf-8", errors="replace")[:2000]
    error = detail.get("error", {}) if isinstance(detail, dict) else {}
    if not isinstance(error, dict):
        error = {"message": str(error)}
    message = str(error.get("message", ""))
    if status == 413 or _too_long(error):
        return ExternalInputTooLongError(
            f"El pedido no entra en el contexto del modelo (HTTP {status}: {message})",
            status=status, detail=detail)
    unavailable = ExternalUnavailableError(
        f"El proveedor respondió HTTP {status} ({error.get('type', '')}: {message})",
        status=status, detail=detail)
    unavailable.retry_after = retry_after
    return unavailable


def _call_once(key, method, path, body, timeout):
    url = BASE_URL + path
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, method=method,
        headers={"x-api-key": key, "anthropic-version": API_VERSION,
                 "content-type": "application/json", "user-agent": USER_AGENT})
    try:
        with _urlopen(request, timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        try:
            raw = error.read()
        except Exception:  # noqa: BLE001 - el cuerpo del error es solo informativo
            raw = b""
        retry_after = _retry_after(error)
        raise _rejection(error.code, raw, retry_after) from error
    except urllib.error.URLError as error:
        if _is_timeout(error.reason):
            raise ExternalTimeoutError(f"Sin respuesta en {timeout} s ({method} {path})") from error
        raise ExternalUnavailableError(
            f"El proveedor no responde ({method} {path}: {error.reason})") from error
    except (TimeoutError, socket.timeout) as error:
        raise ExternalTimeoutError(f"Sin respuesta en {timeout} s ({method} {path})") from error
    except OSError as error:
        raise ExternalUnavailableError(
            f"El proveedor no responde ({method} {path}: {error})") from error


def _call(key, method, path, body=None, *, timeout, idempotent=False):
    """Una llamada a la API con sus reintentos; devuelve el cuerpo de la respuesta en bytes.

    Reintenta (hasta `MAX_RETRIES`) lo que el proveedor rechazó antes de procesar (429 y 529) y,
    si `idempotent`, también las fallas del servidor y de la conexión. Nunca reintenta una
    espera agotada ni un pedido demasiado largo.
    """
    attempt = 0
    while True:
        try:
            return _call_once(key, method, path, body, timeout)
        except ExternalUnavailableError as error:
            retry = error.status in (429, 529) or (
                idempotent and (error.status is None or error.status >= 500))
            if not retry or attempt >= MAX_RETRIES:
                raise
            attempt += 1
            _sleep(getattr(error, "retry_after", None) or RETRY_SECONDS * attempt)


def _json_object(raw, what):
    try:
        data = json.loads(raw)
    except ValueError as error:
        raise ExternalInvalidResponse(f"{what}: la respuesta no es JSON.") from error
    if not isinstance(data, dict):
        raise ExternalInvalidResponse(f"{what}: la respuesta no es un objeto JSON.")
    return data


# --- Lectura de las respuestas ------------------------------------------------------------------


def parse_message(payload, body, *, mode, batch_id=None, duration_s=None, outcome="ok"):
    """Convierte el mensaje que devuelve el proveedor en un `ExternalResult`.

    Exige `content` (lista de bloques; el texto es el de los bloques `text`) y `usage`; sin
    ellos, `ExternalInvalidResponse`."""
    if not isinstance(body, dict) or not isinstance(body.get("content"), list):
        raise ExternalInvalidResponse("El mensaje no trae la lista `content`.",
                                      batch_id=batch_id)
    text = "".join(block.get("text", "") for block in body["content"]
                   if isinstance(block, dict) and block.get("type") == "text"
                   and isinstance(block.get("text"), str))
    stop_reason = body.get("stop_reason")
    return ExternalResult(
        payload=payload, outcome=outcome, text=text,
        model=str(body.get("model") or ""),
        stop_reason=stop_reason if isinstance(stop_reason, str) else None,
        usage=ExternalUsage.from_body(body.get("usage")),
        message_id=body.get("id") if isinstance(body.get("id"), str) else None,
        batch_id=batch_id, custom_id=payload.custom_id, mode=mode,
        request_body=payload.to_params(), response_body=body, duration_s=duration_s,
        request_sha256=payload.request_sha256)


def _unsuccessful(payload, outcome, result, *, batch_id):
    error = result.get("error") if isinstance(result.get("error"), dict) else None
    if isinstance(error, dict) and isinstance(error.get("error"), dict):
        error = error["error"]  # el proveedor anida `{"type": "error", "error": {...}}`
    return ExternalResult(
        payload=payload, outcome=outcome, text="", model="", stop_reason=None,
        usage=ExternalUsage(), message_id=None, batch_id=batch_id,
        custom_id=payload.custom_id, mode="lotes", request_body=payload.to_params(),
        response_body=_scrub(result), error=_scrub(error),
        request_sha256=payload.request_sha256)


def parse_batch_results(batch, raw):
    """Convierte el texto de resultados de un lote (un JSON por línea) en un diccionario
    `custom_id` → `ExternalResult`, en el orden de los pedidos. Un `custom_id` repetido, que
    no se pidió o que falta es `ExternalInvalidResponse`."""
    by_id = {payload.custom_id: payload for payload in batch.payloads}
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    found = {}
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        entry = _json_object(line, f"Resultados del lote, línea {number}")
        custom_id = entry.get("custom_id")
        result = entry.get("result")
        if custom_id not in by_id or custom_id in found or not isinstance(result, dict):
            raise ExternalInvalidResponse(
                f"Resultados del lote {batch.id}: línea {number} con un pedido que no "
                f"corresponde ({custom_id!r}).", batch_id=batch.id)
        kind = result.get("type")
        payload = by_id[custom_id]
        if kind == "succeeded":
            found[custom_id] = parse_message(payload, result.get("message"), mode="lotes",
                                             batch_id=batch.id)
        elif kind in ("errored", "canceled", "expired"):
            outcome = "error" if kind == "errored" else kind
            found[custom_id] = _unsuccessful(payload, outcome, result, batch_id=batch.id)
        else:
            raise ExternalInvalidResponse(
                f"Resultados del lote {batch.id}: tipo de resultado {kind!r} desconocido.",
                batch_id=batch.id)
    missing = [custom_id for custom_id in by_id if custom_id not in found]
    if missing:
        raise ExternalInvalidResponse(
            f"Resultados del lote {batch.id}: faltan {len(missing)} pedidos "
            f"({missing[:3]}).", batch_id=batch.id)
    return {custom_id: found[custom_id] for custom_id in by_id}


def _batch_state(body, what):
    batch_id = body.get("id")
    status = body.get("processing_status")
    counts = body.get("request_counts")
    if not isinstance(batch_id, str) or not _ID_PATTERN.match(batch_id):
        raise ExternalInvalidResponse(f"{what}: la respuesta no trae un identificador de lote.")
    if status not in BATCH_STATUSES:
        raise ExternalInvalidResponse(f"{what}: estado de lote {status!r} desconocido.",
                                      batch_id=batch_id)
    return batch_id, status, counts if isinstance(counts, dict) else {}


# --- Operaciones --------------------------------------------------------------------------------


def _check_payload(payload):
    if not isinstance(payload, ExternalPayload):
        raise TypeError("El cliente externo solo acepta un ExternalPayload (lo arma guard.py).")
    if not payload.sealed:  # O-289-4 (T-290): cambiado después de la puerta
        raise TypeError("El pedido cambió después de pasar por la puerta (guard.py): no sale.")


def check_batch(payloads):
    """Valida los pedidos de un lote (misma etapa, `custom_id` distintos) y los devuelve como
    tupla. No abre red."""
    payloads = tuple(payloads)
    if not payloads:
        raise ValueError("Un lote necesita al menos un pedido.")
    for payload in payloads:
        _check_payload(payload)
    if len({payload.stage for payload in payloads}) != 1:
        raise ValueError("Todos los pedidos de un lote tienen que ser de la misma etapa.")
    if len({payload.custom_id for payload in payloads}) != len(payloads):
        raise ValueError("Los custom_id de un lote tienen que ser distintos.")
    return payloads


def send_message(payload, *, timeout=None):
    """Manda un mensaje directo (`POST /v1/messages`) y devuelve su `ExternalResult`.

    Lanza `ExternalDisabled` antes de abrir un socket si no está habilitado. Un error del
    proveedor lanza el error propio que corresponde.
    """
    _check_payload(payload)
    key = require_enabled(payload.stage)
    started = _now()
    raw = _call(key, "POST", "/v1/messages", payload.to_params(),
                timeout=timeout or MESSAGE_TIMEOUT_SECONDS)
    body = _json_object(raw, "Mensaje")
    if body.get("type") == "error":
        raise _rejection(200, raw)
    return parse_message(payload, body, mode="directo", duration_s=_now() - started)


def create_batch(payloads):
    """Crea un lote (`POST /v1/messages/batches`) con los pedidos de una etapa."""
    payloads = check_batch(payloads)
    key = require_enabled(payloads[0].stage)
    request_body = {"requests": [{"custom_id": payload.custom_id, "params": payload.to_params()}
                                 for payload in payloads]}
    raw = _call(key, "POST", "/v1/messages/batches", request_body, timeout=CALL_TIMEOUT_SECONDS)
    body = _json_object(raw, "Creación del lote")
    batch_id, status, counts = _batch_state(body, "Creación del lote")
    return ExternalBatch(id=batch_id, stage=payloads[0].stage, status=status,
                         request_counts=counts, payloads=payloads, request_body=request_body,
                         response_body=body)


def retrieve_batch(batch):
    """Consulta el estado de un lote (`GET /v1/messages/batches/{id}`)."""
    key = require_enabled(batch.stage)
    raw = _call(key, "GET", f"/v1/messages/batches/{batch.id}", timeout=CALL_TIMEOUT_SECONDS,
                idempotent=True)
    body = _json_object(raw, "Consulta del lote")
    batch_id, status, counts = _batch_state(body, "Consulta del lote")
    if batch_id != batch.id:
        raise ExternalInvalidResponse("La consulta respondió por otro lote.", batch_id=batch.id)
    return replace(batch, status=status, request_counts=counts, response_body=body)


def cancel_batch(batch):
    """Pide cancelar un lote (`POST /v1/messages/batches/{id}/cancel`); el proveedor lo pasa a
    `canceling` y termina los pedidos que ya procesó. Devuelve el lote con su nuevo estado."""
    key = require_enabled(batch.stage)
    raw = _call(key, "POST", f"/v1/messages/batches/{batch.id}/cancel",
                timeout=CALL_TIMEOUT_SECONDS, idempotent=True)
    body = _json_object(raw, "Cancelación del lote")
    batch_id, status, counts = _batch_state(body, "Cancelación del lote")
    if batch_id != batch.id:
        raise ExternalInvalidResponse("La cancelación respondió por otro lote.",
                                      batch_id=batch.id)
    return replace(batch, status=status, request_counts=counts, response_body=body)


def fetch_results(batch):
    """Baja los resultados de un lote terminado (`GET /v1/messages/batches/{id}/results`) y
    devuelve un diccionario `custom_id` → `ExternalResult`, en el orden de los pedidos."""
    if batch.status != "ended":
        raise ValueError(f"El lote {batch.id} no terminó (estado {batch.status}).")
    key = require_enabled(batch.stage)
    raw = _call(key, "GET", f"/v1/messages/batches/{batch.id}/results",
                timeout=RESULTS_TIMEOUT_SECONDS, idempotent=True)
    return parse_batch_results(batch, raw)


def run_batch(payloads, *, on_created=None):
    """Crea el lote, lo consulta hasta que termine y baja sus resultados.

    Consulta cada `EXTERNAL_BATCH_POLL_SECONDS` y, pasados `EXTERNAL_BATCH_MAX_WAIT_SECONDS`
    sin que termine, pide cancelar el lote (si la cancelación falla, igual sigue) y lanza
    `ExternalTimeoutError` con el `batch_id` y `canceled` según haya salido la cancelación.
    Si una consulta de estado o de resultados falla después de que el lote existe, también
    pide cancelarlo (lo mejor que pueda) y relanza el error con su `batch_id` y `canceled`:
    un lote que nadie espera no queda gastando. `on_created(batch)`, si se pasa, se llama
    apenas el lote existe, antes de esperar: sirve para registrar su identificador. Devuelve
    un `BatchRun`.
    """
    started = _now()
    batch = create_batch(payloads)
    if on_created is not None:
        on_created(batch)
    try:
        return _wait_for(batch, started)
    except ExternalError as error:
        if error.batch_id is None:
            error.batch_id = batch.id
        if error.canceled is None:
            error.canceled = _try_cancel(batch)
        raise


def _try_cancel(batch):
    """Pide cancelar `batch`; dice si se pudo. Nunca lanza."""
    try:
        cancel_batch(batch)
        return True
    except ExternalError:
        return False


def _wait_for(batch, started):
    poll = max(int(settings.EXTERNAL_BATCH_POLL_SECONDS), 1)
    max_wait = int(settings.EXTERNAL_BATCH_MAX_WAIT_SECONDS)
    polls = 0
    while batch.status != "ended":
        waited = _now() - started
        if waited >= max_wait:
            canceled = _try_cancel(batch)
            timeout_error = ExternalTimeoutError(
                f"El lote {batch.id} no terminó en {max_wait} s (estado {batch.status}). "
                + ("Se pidió su cancelación." if canceled else "No se pudo cancelarlo."),
                batch_id=batch.id)
            timeout_error.canceled = canceled
            raise timeout_error
        _sleep(min(poll, max_wait - waited))
        batch = retrieve_batch(batch)
        polls += 1
    results = fetch_results(batch)
    return BatchRun(batch=batch, results=results, polls=polls, duration_s=_now() - started)
