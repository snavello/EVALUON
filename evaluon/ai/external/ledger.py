"""Libro de los pedidos externos: registro, tope de gasto y reuso por huella (T-290; REQ-122;
ADR-0068; plan 016, "Modelo de datos", "Registro de auditoría" y "Costo y tope").

Cada pedido a la API externa deja **un hecho `external_request`** en `audit_event` (de solo
inserción, P6), con los campos del plan: proveedor, modelo pedido y devuelto, etapa, instrucción y
definiciones (nombre, versión y huella), modo, lote y pedido, parámetros, procedimiento, oferta,
requisito, corrida, el texto enviado tal como salió, la huella del pedido, la respuesta completa,
el uso de tokens, el costo en USD con la tabla de precios versionada, la duración, el resultado
(`ok`, `error`, `vencido`, `bloqueado` o `reutilizado`), el error y lo que comprobó la puerta
(`filtro`). Un pedido bloqueado (por la puerta o por el tope) queda sin texto.

La única forma de mandar es `send(admitidos)`, con lo que devolvió `guard.build` (nunca un
`ExternalPayload` suelto). Antes de cada lote, en este orden:

1. **Reuso por huella.** Un pedido con la misma huella, modelo, parámetros y versión de la
   instrucción que uno ya respondido (`ok`) en la misma medición (`measurement`) no sale: se
   contesta con la respuesta guardada y queda `reutilizado`, con costo 0. Sin medición no hay
   reuso.
2. **Freno de la etapa.** Si lo gastado por la etapa (`matriz` o `verificador`) en el
   procedimiento y la medición (o, sin medición, en la corrida) ya llegó a
   `EXTERNAL_STAGE_STOP_FACTOR` veces su estimado (`EXTERNAL_STAGE_ESTIMATE_USD`), el lote no
   sale: `bloqueado` con motivo `etapa` y `stage_stopped`, para que la etapa lo informe y no
   siga sin decisión.
3. **Tope.** Se suma `costo_usd` del procedimiento (todas las rondas) y del mes calendario
   (hora de `TIME_ZONE`), y se estima el lote con lo conservador del plan: caracteres entre 2,5
   por el precio de entrada, más `max_tokens` por el de salida (a la mitad en lotes). Si el
   estimado pasa lo que queda del caso (`EXTERNAL_CASE_CAP_USD`) o del mes
   (`EXTERNAL_MONTH_CAP_USD`), el lote no sale: `bloqueado` con motivo `tope`.

Un tope, un estimado o un factor que no sea un número finito y positivo es un error de
configuración (`ImproperlyConfigured`, O-288-2): no se usa como tope. Lo mismo los factores de
lotes y de caché de `EXTERNAL_PRICES`, que se comprueban antes de mandar (H-290-5). Un modelo
sin precio en `EXTERNAL_PRICES` tampoco sale (motivo `sin_precio`).

El costo real se calcula con el uso que informa el proveedor (entrada, salida, escritura y lectura
de caché) y la tabla `EXTERNAL_PRICES`; en lotes, a la mitad. La escritura de caché se cobra con el
factor de una hora (`cache_escritura_1h`), el único de la tabla y el más caro. Los importes son
`Decimal` y se guardan en el JSON como número (`jsonb` los guarda como `numeric`, exactos); la
suma se hace en SQL con `numeric`.

Este módulo no importa ningún módulo de red: llama al cliente como
`client.run_batch(...)`/`client.send_message(...)` para que el doble de las pruebas lo alcance.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_CEILING, Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import DecimalField, Sum
from django.db.models.fields.json import KT
from django.db.models.functions import Cast
from django.utils import timezone

from evaluon.ai.external import client
from evaluon.audit import services as audit
from evaluon.audit.models import AuditEvent, Channel, EventType, Outcome

# Resultados de un pedido en el registro.
OK = "ok"
ERROR = "error"
EXPIRED = "vencido"
BLOCKED = "bloqueado"
REUSED = "reutilizado"
RESULTS = (OK, ERROR, EXPIRED, BLOCKED, REUSED)

# Motivos de un bloqueo del libro (los de la puerta los pone `guard.py`).
CAP = "tope"
STAGE_STOP = "etapa"
NO_PRICE = "sin_precio"

# Anomalías que la etapa recibe para seguir por el camino local.
ANOMALY_BLOCKED = "externo_bloqueado"
ANOMALY_UNAVAILABLE = "externo_no_disponible"

CHARS_PER_TOKEN = Decimal("2.5")
MILLION = Decimal(1_000_000)
COST_QUANTUM = Decimal("0.00000001")  # 8 decimales, siempre hacia arriba

_EVENT_OUTCOME = {OK: Outcome.OK, REUSED: Outcome.OK, BLOCKED: Outcome.REJECTED,
                  ERROR: Outcome.FAILED, EXPIRED: Outcome.FAILED}


# --- Configuración ----------------------------------------------------------------------------


def _positive(name, value):
    """`value` como `Decimal` finito y positivo; si no, `ImproperlyConfigured` (O-288-2)."""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ImproperlyConfigured(f"{name} tiene que ser un número positivo.") from None
    if not number.is_finite() or number <= 0:
        raise ImproperlyConfigured(
            f"{name} tiene que ser un número finito y positivo (es {value!r}): no se usa como "
            "tope.")
    return number


def case_cap():
    return _positive("EXTERNAL_CASE_CAP_USD", settings.EXTERNAL_CASE_CAP_USD)


def month_cap():
    return _positive("EXTERNAL_MONTH_CAP_USD", settings.EXTERNAL_MONTH_CAP_USD)


def stage_limit(group):
    """Lo que puede gastar la etapa `group` antes de frenarse: el estimado por el factor."""
    estimates = settings.EXTERNAL_STAGE_ESTIMATE_USD
    if group not in estimates:
        raise ImproperlyConfigured(f"No hay estimado de gasto para la etapa {group!r}.")
    estimate = _positive(f"EXTERNAL_STAGE_ESTIMATE_USD[{group}]", estimates[group])
    factor = _positive("EXTERNAL_STAGE_STOP_FACTOR", settings.EXTERNAL_STAGE_STOP_FACTOR)
    return estimate * factor


PRICE_FACTORS = ("lotes", "cache_lectura", "cache_escritura_1h")


def price_factors():
    """Los factores de `EXTERNAL_PRICES` (lotes y caché), cada uno finito y positivo; si no,
    `ImproperlyConfigured`. Se comprueban antes de mandar (H-290-5): un factor inválido que se
    descubriera al calcular el costo real dejaría un lote pagado y sin registro."""
    table = settings.EXTERNAL_PRICES
    return {name: _positive(f"EXTERNAL_PRICES.{name}", table.get(name))
            for name in PRICE_FACTORS}


def price_table():
    """Versión, fecha y fuente de la tabla de precios (lo que registra cada pedido)."""
    prices = settings.EXTERNAL_PRICES
    return {"version": prices["version"], "fecha": prices["fecha"], "fuente": prices["fuente"]}


def _model_prices(model):
    prices = settings.EXTERNAL_PRICES["modelos"].get(model)
    if prices is None:
        return None
    return (_positive(f"EXTERNAL_PRICES[{model}].entrada", prices["entrada"]),
            _positive(f"EXTERNAL_PRICES[{model}].salida", prices["salida"]))


def _mode_factor(mode):
    if mode == "lotes":
        return _positive("EXTERNAL_PRICES.lotes", settings.EXTERNAL_PRICES["lotes"])
    return Decimal(1)


def _round(cost):
    return cost.quantize(COST_QUANTUM, rounding=ROUND_CEILING)


def _number(cost):
    """El importe para el JSON: número (no texto). Con 8 decimales y menos de 15 cifras, el
    número que se escribe es exactamente el `Decimal`."""
    return float(_round(cost))


# --- Costo ------------------------------------------------------------------------------------


def estimate(payload, mode):
    """Estimación conservadora de un pedido (ADR-0068, punto 4): los caracteres del sistema y de
    los mensajes entre 2,5 por el precio de entrada, más `max_tokens` por el de salida; en lotes, a
    la mitad. `None` si el modelo no tiene precio."""
    prices = _model_prices(payload.model)
    if prices is None:
        return None
    entrada, salida = prices
    chars = len(payload.system) + sum(len(text) for _, text in payload.messages)
    tokens_in = Decimal(chars) / CHARS_PER_TOKEN
    cost = (tokens_in * entrada + Decimal(payload.max_tokens) * salida) / MILLION
    return _round(cost * _mode_factor(mode))


def cost_of(model, usage, mode):
    """Costo real con el uso que informa el proveedor (`ExternalUsage`)."""
    prices = _model_prices(model)
    if prices is None:
        raise ImproperlyConfigured(f"El modelo {model!r} no tiene precio en EXTERNAL_PRICES.")
    entrada, salida = prices
    table = settings.EXTERNAL_PRICES
    write = _positive("EXTERNAL_PRICES.cache_escritura_1h", table["cache_escritura_1h"])
    read = _positive("EXTERNAL_PRICES.cache_lectura", table["cache_lectura"])
    cost = (Decimal(usage.input_tokens) * entrada
            + Decimal(usage.cache_creation_input_tokens) * entrada * write
            + Decimal(usage.cache_read_input_tokens) * entrada * read
            + Decimal(usage.output_tokens) * salida) / MILLION
    return _round(cost * _mode_factor(mode))


# --- Sumas sobre el registro ------------------------------------------------------------------


def _requests():
    return AuditEvent.objects.filter(event_type=EventType.EXTERNAL_REQUEST)


def _total(queryset):
    value = queryset.aggregate(total=Sum(Cast(
        KT("detail__costo_usd"), DecimalField(max_digits=24, decimal_places=10))))["total"]
    return Decimal(value or 0)


def month_bounds(moment=None):
    """Inicio y fin del mes calendario de `moment` (por omisión, ahora), en `TIME_ZONE`."""
    local = timezone.localtime(moment or timezone.now())
    start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    following = (datetime(start.year + 1, 1, 1) if start.month == 12
                 else datetime(start.year, start.month + 1, 1))
    return start, timezone.make_aware(following, timezone.get_current_timezone())


def spent_month(moment=None):
    """Gasto real del mes calendario (todos los procedimientos)."""
    start, end = month_bounds(moment)
    return _total(_requests().filter(occurred_at__gte=start, occurred_at__lt=end))


def spent_case(procedure_id):
    """Gasto real del procedimiento, todas las rondas (el tope de 2 USD por caso)."""
    return _total(_requests().filter(detail__procedimiento=procedure_id))


def _stage_scope(group, procedure_id, measurement, run_kind, run_id):
    queryset = _requests().filter(detail__etapa_grupo=group, detail__procedimiento=procedure_id)
    if measurement:
        return queryset.filter(detail__medicion=measurement)
    return queryset.filter(detail__medicion=None, detail__corrida={"tipo": run_kind,
                                                                    "numero": run_id})


def spent_stage(group, procedure_id, *, measurement=None, run_kind=None, run_id=None):
    """Gasto real de la etapa en el procedimiento y la medición (o la corrida, sin medición)."""
    return _total(_stage_scope(group, procedure_id, measurement, run_kind, run_id))


# --- Registro ---------------------------------------------------------------------------------


def _parameters(payload):
    return {"effort": payload.effort, "thinking": payload.thinking,
            "max_tokens": payload.max_tokens, "formato_salida": payload.output_schema,
            "cache_system_ttl": payload.cache_system_ttl}


def _instruction(payload):
    return {"nombre": payload.instruction_name, "version": payload.instruction_version,
            "sha256": payload.instruction_sha256}


def _definitions(payload):
    if not (payload.definitions_version or payload.definitions_sha256):
        return None
    return {"version": payload.definitions_version, "sha256": payload.definitions_sha256}


def _text_sent(payload):
    return {"sistema": payload.system,
            "mensajes": [{"rol": role, "texto": text} for role, text in payload.messages]}


def _usage(usage):
    if usage is None:
        return None
    return {"entrada": usage.input_tokens, "salida": usage.output_tokens,
            "escritura_cache": usage.cache_creation_input_tokens,
            "lectura_cache": usage.cache_read_input_tokens}


def _base(*, stage, custom_id, procedure_id, offer_id, requirement_id, run_kind, run_id,
          model, parameters, instruction, definitions, measurement, filter):
    return {
        "proveedor": client.PROVIDER, "modelo": model, "modelo_respuesta": None,
        "etapa": stage, "etapa_grupo": str(stage).split("_", 1)[0],
        "instruccion": instruction, "definiciones": definitions,
        "modo": None, "lote_id": None, "custom_id": custom_id, "parametros": parameters,
        "procedimiento": procedure_id, "oferta": offer_id, "requisito": requirement_id,
        "corrida": {"tipo": run_kind, "numero": run_id}, "medicion": measurement,
        "texto_enviado": None, "huella_pedido": None, "respuesta": None, "uso": None,
        "costo_usd": 0.0, "tabla_de_precios": price_table(), "duracion_s": None,
        "resultado": None, "error": None, "motivo": None, "filtro": filter,
    }


def _payload_base(payload, *, measurement, filter):
    return _base(stage=payload.stage, custom_id=payload.custom_id,
                 procedure_id=payload.procedure_id, offer_id=payload.offer_id,
                 requirement_id=payload.requirement_id, run_kind=payload.run_kind,
                 run_id=payload.run_id, model=payload.model, parameters=_parameters(payload),
                 instruction=_instruction(payload), definitions=_definitions(payload),
                 measurement=measurement, filter=filter)


def _write(detail, *, channel, user):
    if detail["resultado"] not in RESULTS:
        raise ValueError(f"Resultado de un pedido externo desconocido: {detail['resultado']!r}.")
    return audit.record(EventType.EXTERNAL_REQUEST, outcome=_EVENT_OUTCOME[detail["resultado"]],
                        channel=channel or Channel.COMMAND, user=user, detail=detail)


def record_blocked(*, stage, custom_id, reason, filter, procedure_id, offer_id=None,
                   requirement_id=None, run_kind=None, run_id=None, model="", parameters=None,
                   instruction=None, definitions=None, measurement=None, channel=None,
                   user=None, reasons=None):
    """Registra un pedido que no salió: `bloqueado`, **sin texto ni huella del texto**, con el
    motivo y lo que comprobó la puerta (`filter`, sin texto). Lo usan la puerta y el tope."""
    detail = _base(stage=stage, custom_id=custom_id, procedure_id=procedure_id,
                   offer_id=offer_id, requirement_id=requirement_id, run_kind=run_kind,
                   run_id=run_id, model=model, parameters=parameters, instruction=instruction,
                   definitions=definitions, measurement=measurement, filter=filter)
    detail.update(resultado=BLOCKED, motivo=reason, motivos=list(reasons or [reason]))
    return _write(detail, channel=channel, user=user)


def _record_payload_blocked(admitted, reason, *, measurement, channel, user, extra=None):
    payload = admitted.payload
    detail = _payload_base(payload, measurement=measurement, filter=admitted.filter)
    detail.update(resultado=BLOCKED, motivo=reason, motivos=[reason])
    if extra:
        detail["tope"] = extra
    return _write(detail, channel=channel, user=user)


def _record_result(admitted, result, *, measurement, channel, user, duration_s=None):
    """Registra lo que devolvió el proveedor para un pedido (`ExternalResult`)."""
    payload = admitted.payload
    detail = _payload_base(payload, measurement=measurement, filter=admitted.filter)
    outcome = {"ok": OK, "expired": EXPIRED}.get(result.outcome, ERROR)
    cost = cost_of(payload.model, result.usage, result.mode)
    detail.update(
        modelo_respuesta=result.model or None, modo=result.mode, lote_id=result.batch_id,
        texto_enviado=_text_sent(payload), huella_pedido=result.request_sha256,
        respuesta=result.response_body, uso=_usage(result.usage), costo_usd=_number(cost),
        duracion_s=result.duration_s if result.duration_s is not None else duration_s,
        resultado=outcome, mensaje_id=result.message_id, stop_reason=result.stop_reason,
        error=None if outcome == OK else {"motivo": result.reason, "detalle": result.error})
    return _write(detail, channel=channel, user=user), cost


def _record_failure(admitted, error, *, mode, measurement, channel, user, batch_id=None):
    """Registra un pedido cuya llamada falló entera (`ExternalError`): no hubo respuesta."""
    payload = admitted.payload
    detail = _payload_base(payload, measurement=measurement, filter=admitted.filter)
    outcome = EXPIRED if isinstance(error, client.ExternalExpired) else ERROR
    detail.update(
        modo=mode, lote_id=getattr(error, "batch_id", None) or batch_id,
        texto_enviado=_text_sent(payload), huella_pedido=payload.request_sha256,
        resultado=outcome,
        error={"motivo": error.reason, "mensaje": str(error), "estado_http": error.status,
               "detalle": error.detail, "cancelado": error.canceled})
    return _write(detail, channel=channel, user=user)


def _record_reused(admitted, original, *, measurement, channel, user):
    payload = admitted.payload
    detail = _payload_base(payload, measurement=measurement, filter=admitted.filter)
    before = original.detail
    detail.update(
        modelo_respuesta=before.get("modelo_respuesta"), modo=before.get("modo"),
        lote_id=before.get("lote_id"), texto_enviado=_text_sent(payload),
        huella_pedido=payload.request_sha256, respuesta=before.get("respuesta"),
        uso=before.get("uso"), costo_usd=0.0, resultado=REUSED, reutiliza=original.pk)
    return _write(detail, channel=channel, user=user)


# --- Envío ------------------------------------------------------------------------------------


@dataclass
class Answer:
    """Lo que la etapa recibe por cada pedido. `outcome`: `ok`, `reutilizado`, `error`,
    `vencido` o `bloqueado`; `text` es la respuesta (vacía si no la hubo); `event_id`, el hecho
    del registro (lo que la etapa guarda como referencia)."""

    custom_id: str
    outcome: str
    text: str = ""
    event_id: int | None = None
    reason: str | None = None
    result: object = None

    @property
    def ok(self):
        return self.outcome in (OK, REUSED)


@dataclass
class Sent:
    """El resultado de `send`. `answers`: `custom_id` → `Answer`, en el orden de los pedidos.
    `stage_stopped`: la etapa llegó al doble de su estimado y no sigue sin decisión (se informa).
    `anomalies`: lo que la etapa registra al seguir por lo local. `cost_usd`: lo gastado en este
    envío (`Decimal`). `spent_stage_usd`: lo gastado por la etapa en su medición, con este envío."""

    stage: str
    mode: str
    model: str
    answers: dict = field(default_factory=dict)
    stage_stopped: bool = False
    anomalies: list = field(default_factory=list)
    cost_usd: Decimal = Decimal(0)
    spent_stage_usd: Decimal = Decimal(0)
    batch_id: str | None = None

    def summary(self):
        """Lo que la corrida guarda en su clave `externo` para esta etapa (plan 016, "Modelo de
        datos"): proveedor, modelo, modo, pedidos (los que salieron o se reutilizaron) y gasto."""
        return {"proveedor": client.PROVIDER, "modelo": self.model, "modo": self.mode,
                "pedidos": sum(1 for a in self.answers.values() if a.outcome != BLOCKED),
                "gasto_usd": _number(self.cost_usd), "tabla_de_precios": price_table()["version"],
                "frenada": self.stage_stopped}


def _admitted(items):
    from evaluon.ai.external import guard

    items = list(items)
    if not items:
        raise ValueError("No hay pedidos para mandar.")
    for item in items:
        if not isinstance(item, guard.Admitted):
            raise TypeError("El libro solo manda lo que admitió la puerta (guard.build).")
    if len({item.payload.stage for item in items}) != 1:
        raise ValueError("Todos los pedidos de un envío tienen que ser de la misma etapa.")
    if len({item.payload.custom_id for item in items}) != len(items):
        raise ValueError("Los custom_id de un envío tienen que ser distintos.")
    if len({item.payload.procedure_id for item in items}) != 1:
        raise ValueError("Todos los pedidos de un envío tienen que ser del mismo procedimiento.")
    return items


def _reusable(payload, measurement):
    if not measurement:
        return None
    return (_requests().filter(
        detail__medicion=measurement, detail__resultado=OK,
        detail__huella_pedido=payload.request_sha256, detail__modelo=payload.model,
        detail__parametros=_parameters(payload),
        detail__instruccion__version=payload.instruction_version)
        .order_by("pk").first())


def send(admitted, *, measurement=None, mode=None, channel=None, user=None):
    """Manda los pedidos admitidos por la puerta (una etapa, un procedimiento) y registra cada
    uno. Devuelve `Sent`; nunca lanza por una falla del proveedor (queda en cada `Answer` y en el
    registro). Lanza `ImproperlyConfigured` si un tope, estimado o factor no es válido.

    `measurement`: la medición (por ejemplo `T-293-caso-00-r1`); delimita el reuso por huella y
    el freno de la etapa. `mode`: `lotes` o `directo` (por omisión, `EXTERNAL_MODE`)."""
    items = _admitted(admitted)
    mode = mode or settings.EXTERNAL_MODE
    if mode not in ("lotes", "directo"):
        raise ValueError(f"Modo desconocido: {mode!r}.")
    first = items[0].payload
    group = first.stage_group
    procedure_id = first.procedure_id
    limits = (case_cap(), month_cap(), stage_limit(group))  # O-288-2: antes de todo
    price_factors()  # H-290-5: también antes de mandar
    sent = Sent(stage=first.stage, mode=mode, model=first.model)
    record = {"measurement": measurement, "channel": channel, "user": user}

    def scope_spent():
        return spent_stage(group, procedure_id, measurement=measurement,
                           run_kind=first.run_kind, run_id=first.run_id)

    pending = []
    for item in items:
        original = _reusable(item.payload, measurement)
        if original is None:
            pending.append(item)
            continue
        event = _record_reused(item, original, **record)
        sent.answers[item.payload.custom_id] = Answer(
            item.payload.custom_id, REUSED, text=_response_text(original.detail),
            event_id=event.pk)

    if pending:
        reason, extra = _hold_back(pending, mode, procedure_id, limits, scope_spent())
        if reason is not None:
            for item in pending:
                event = _record_payload_blocked(item, reason, extra=extra, **record)
                sent.answers[item.payload.custom_id] = Answer(
                    item.payload.custom_id, BLOCKED, event_id=event.pk, reason=reason)
            sent.anomalies.append({"anomalia": ANOMALY_BLOCKED, "motivo": reason,
                                   "etapa": first.stage, "pedidos": len(pending), **extra})
            sent.stage_stopped = reason == STAGE_STOP
        elif mode == "lotes":
            _send_batch(pending, sent, record)
        else:
            _send_direct(pending, sent, record)

    sent.answers = {item.payload.custom_id: sent.answers[item.payload.custom_id]
                    for item in items}
    sent.spent_stage_usd = scope_spent()
    if sent.spent_stage_usd >= limits[2] and not sent.stage_stopped:
        sent.stage_stopped = True
        sent.anomalies.append({"anomalia": "externo_etapa_frenada", "etapa": first.stage,
                               "gasto_usd": _number(sent.spent_stage_usd),
                               "limite_usd": _number(limits[2])})
    return sent


def _hold_back(pending, mode, procedure_id, limits, stage_spent):
    """El motivo por el que el lote no sale (`None` si puede salir) y sus cifras."""
    cap_case, cap_month, cap_stage = limits
    if stage_spent >= cap_stage:
        return STAGE_STOP, {"gasto_etapa_usd": _number(stage_spent),
                            "limite_etapa_usd": _number(cap_stage)}
    estimates = [estimate(item.payload, mode) for item in pending]
    if any(value is None for value in estimates):
        return NO_PRICE, {}
    batch = sum(estimates, Decimal(0))
    case, month = spent_case(procedure_id), spent_month()
    figures = {"estimado_usd": _number(batch), "gasto_caso_usd": _number(case),
               "tope_caso_usd": _number(cap_case), "gasto_mes_usd": _number(month),
               "tope_mes_usd": _number(cap_month)}
    if case + batch > cap_case:
        return CAP, {**figures, "tope": "caso"}
    if month + batch > cap_month:
        return CAP, {**figures, "tope": "mes"}
    return None, {}


def _response_text(detail):
    body = detail.get("respuesta") or {}
    content = body.get("content") if isinstance(body, dict) else None
    if not isinstance(content, list):
        return ""
    return "".join(block.get("text", "") for block in content
                   if isinstance(block, dict) and block.get("type") == "text"
                   and isinstance(block.get("text"), str))


def _take(sent, item, result, record, *, duration_s=None):
    event, cost = _record_result(item, result, duration_s=duration_s, **record)
    sent.cost_usd += cost
    answer = Answer(item.payload.custom_id, event.detail["resultado"],
                    text=result.text if result.ok else "", event_id=event.pk,
                    reason=None if result.ok else result.reason, result=result)
    sent.answers[item.payload.custom_id] = answer
    if not answer.ok:
        sent.anomalies.append({"anomalia": ANOMALY_UNAVAILABLE, "motivo": result.reason,
                               "custom_id": item.payload.custom_id})


def _fail(sent, items, error, record, *, mode, batch_id=None):
    for item in items:
        event = _record_failure(item, error, mode=mode, batch_id=batch_id, **record)
        sent.answers[item.payload.custom_id] = Answer(
            item.payload.custom_id, event.detail["resultado"], event_id=event.pk,
            reason=error.reason)
    sent.anomalies.append({"anomalia": ANOMALY_UNAVAILABLE, "motivo": error.reason,
                           "pedidos": len(items), "lote_id": error.batch_id or batch_id})


def _send_batch(items, sent, record):
    created = {}

    def on_created(batch):
        created["id"] = batch.id
        sent.batch_id = batch.id

    try:
        run = client.run_batch([item.payload for item in items], on_created=on_created)
    except client.ExternalError as error:
        _fail(sent, items, error, record, mode="lotes", batch_id=created.get("id"))
        return
    for item in items:
        _take(sent, item, run.results[item.payload.custom_id], record,
              duration_s=run.duration_s)


def _send_direct(items, sent, record):
    for item in items:
        try:
            result = client.send_message(item.payload)
        except client.ExternalError as error:
            _fail(sent, [item], error, record, mode="directo")
            continue
        _take(sent, item, result, record)

