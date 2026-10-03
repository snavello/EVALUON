"""Consulta de punta a punta con su registro (REQ-008, REQ-009, REQ-012, REQ-013,
REQ-018, REQ-019, REQ-020; plan 001, "Fecha de autorización y régimen aplicado",
"Recuperación", "Reordenamiento", "Conteo de tokens", "Generación", "Cita",
"Abstención", "Forma de la respuesta" y "Registro de auditoría"). T-019 dejó la versión
mínima; T-040 une la recuperación de T-032 y T-033 y la generación de T-034 y completa el
registro.

`ask(usuario, pregunta, fecha, channel=...)` es el único camino para ejecutar una
consulta: la usan la pantalla, los comandos y las evals. Hace, en este orden:

1. Comprueba el rol (los dos roles consultan) con el canal de la consulta, fuera de toda
   transacción: así el hecho `rejected` no se pierde si algo después se deshace (T-038).
   Comprueba que la pregunta no esté vacía.
2. Valida la fecha de autorización del procedimiento: vacía, la del día en hora de
   Buenos Aires; posterior al día, se rechaza con `FutureDate` sin consultar y sin dejar
   registro de consulta.
3. Instantánea (transacción `REPEATABLE READ` de solo lectura, ver `_snapshot`): toma la
   versión de la normativa vigente, llama a `applicable_regimes(fecha)`, recupera y
   selecciona. Todo lo que se lee ahí ve la base en un mismo momento, y la versión
   registrada es la de ese momento aunque se cree otra mientras la consulta sigue
   (decisión del responsable del 2026-10-03, P6 y P8).
   - Sin régimen a la fecha: "no determinado" con `no_regime_at_date`, sin buscar.
   - Recuperación por los tres caminos (`retrieval.retrieve`). Si no trae ningún
     candidato, "no determinado"; si ningún candidato alcanza el umbral, también. Los
     dos con el motivo `below_threshold` en el resultado, porque es lo que el plan y la
     tabla admiten, y con el motivo propio (`no_candidates` o `below_threshold`) en la
     decisión de abstención del registro (decisión 4 del Coordinador para T-040).
   - Selección (`retrieval.select_units`) con los tokens de las instrucciones
     `consulta-v2` y del comienzo del mensaje (`answering.request_head`), contados con
     `generation.count_tokens`.
   - Control del pedido completo (`_check_request`): se arma el pedido con
     `answering.build_request`, el mismo camino que usa `answer`, y se cuentan sus
     mensajes; si no entra en el contexto (menos el máximo de salida y el margen de la
     plantilla), se sacan unidades desde el final de `retrieval.priority_order` y se
     registran como fuera por espacio (decisión 3).
   - Si no queda ninguna unidad para mostrar, sea porque las instrucciones con la
     pregunta ya no dejan espacio (`prompt_exceeds_context`), porque ninguna entra o
     porque el control las sacó a todas: falla técnica `input_too_long`, sin llamar al
     modelo. No es un "no determinado" (decisión 2).
4. Fuera de la instantánea, genera (`answering.answer`) con la fecha, las unidades y sus
   tramos. Con fecha, `answer` usa las instrucciones `consulta-v2` (decisión 1).
5. Arma el resultado con la forma de "Forma de la respuesta" (`query_id`,
   `reference_date`, `regime` y `notices` vacío en los tres estados) y guarda, en una
   sola transacción, el hecho `query` de `audit_event` y la fila de `queries_query`,
   cada uno una sola vez y completo, con la versión de la normativa de la instantánea.

Registro (fila "Consulta" de "Registro de auditoría"). Las columnas de
`queries_query` y el detalle del hecho llevan lo mismo:

- `parameters`: en el primer nivel, los de búsqueda (caminos, reranker encendido,
  candidatos por camino, umbral, cupos y espacio del contexto); `generation` (modelo,
  archivo, huella, compilación del motor,
  contexto, temperatura, semilla, pensamiento, máximo de salida y de afirmaciones),
  `embeddings` y `reranker` (modelo, archivo y huella) y la espera de los clientes.
- `candidates`: cada pasaje candidato con su unidad, sus caminos, su distancia, su
  puntaje y el origen del texto de su unidad (`text_origin`).
- `selected`:
  - `sent`: las unidades enviadas al modelo, en el orden de entrega, con su puntaje y
    sus pasajes;
  - `added`: las agregadas por relación (`{"unit", "modifies"}`);
  - `left_out`: las dejadas afuera por espacio, con `check` igual a `selection` (las
    dejó afuera la selección) o `request` (las sacó el control del pedido completo);
  - `over_quota`: las que alcanzaron el umbral y no entraron por el cupo;
  - `retrieval`: `path_counts`, cada unidad candidata con su mejor puntaje y el motivo
    de la recuperación;
  - `selection`: la selección tal como la devolvió `select_units` (`as_record()`);
  - `request_check`: tokens del pedido completo, límite y unidades sacadas;
  - `abstention`: la decisión de abstención, `{"abstained", "reason"}`.
- `max_score`, `prompt_version` (la versión de las instrucciones, cuando se usaron),
  `request`, `raw_output`, `anomalies` (de la selección, de la generación, como
  `regimes_flag_dropped`, y las fallas de los servicios como `service_error`) y
  `timings` (régimen, recuperación, selección, generación y total).
- En el hecho, además: pregunta, `asked_at`, fecha, régimen aplicado, avisos mostrados
  (`notices`), estado, motivo y el resultado completo.

Fallas técnicas. La recuperación y la cuenta de tokens dejan pasar los errores propios
de los clientes; la generación los devuelve en `Answer.error`. Todos terminan igual:
estado `error` con el motivo del error (`timeout`, `service_unavailable`,
`input_too_long`) o `invalid_output`, nunca "no determinado". El servicio, el código
HTTP (`status`), el detalle y el mensaje del error quedan en `anomalies` como
`service_error`, para distinguir un servicio caído de un pedido mal armado (P6).

Inserción única. `audit_event` y `queries_query` solo admiten inserciones, y el
resultado guardado en los dos lleva `query_id`. Por eso el `id` de la consulta se reserva
antes con `nextval` sobre la secuencia de `queries_query.id`, se inserta el hecho con el
resultado completo y después la fila con ese `id`, el usuario y la versión de la
normativa del hecho, y `asked_at` con el momento de la pregunta.

Los avisos de modificatorias sin cargar (`notices`) son de T-052. Los clientes de IA se
usan por su módulo (`generation.count_tokens`, y dentro de `retrieval` y `answering`).
"""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from evaluon.accounts.models import Role
from evaluon.accounts.permissions import require_role
from evaluon.ai import AIServiceError, generation
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.norms.models import Unit
from evaluon.queries import answering, retrieval
from evaluon.queries.models import Query, Reason, Status

QUERY_TABLE = Query._meta.db_table

# Tipo de anomalía con que se registra la falla de un servicio de IA.
SERVICE_ERROR = "service_error"

# Motivo propio de la decisión de abstención cuando la recuperación no trajo ningún
# candidato. En el resultado y en la columna `reason` queda `below_threshold`.
NO_CANDIDATES = "no_candidates"

# De dónde sale una unidad dejada afuera por espacio (`selected["left_out"][…]["check"]`).
CHECK_SELECTION = "selection"
CHECK_REQUEST = "request"

_REGIMES_SQL = """
SELECT ar.norm_id, n.citation
FROM applicable_regimes(%s) ar
JOIN norms_norm n ON n.id = ar.norm_id
ORDER BY ar.norm_id
"""


class QueryRefused(ValueError):
    """La consulta no se ejecutó. El mensaje dice por qué, en lenguaje llano. No deja
    registro de consulta."""


class FutureDate(QueryRefused):
    """La fecha de autorización es posterior al día."""


def today():
    """Fecha del día en hora de Buenos Aires (`TIME_ZONE`)."""
    return timezone.localdate()


def validate_reference_date(reference_date):
    """Fecha de autorización con que se consulta: la recibida o, si llega vacía, la del
    día. Lanza `FutureDate` si es posterior al día."""
    current = today()
    if reference_date is None:
        return current
    if reference_date > current:
        raise FutureDate("La fecha de autorización no puede ser posterior a hoy")
    return reference_date


def applicable_regimes(reference_date):
    """Régimen aplicado a la fecha, como se guarda en `result["regime"]`: una entrada
    `{"norm", "name"}` por norma que devuelve `applicable_regimes(fecha)`, con el nombre
    de cita de la norma."""
    with connection.cursor() as cursor:
        cursor.execute(_REGIMES_SQL, [reference_date])
        return [{"norm": norm_id, "name": citation}
                for norm_id, citation in cursor.fetchall()]


def parameters():
    """Copia de todos los parámetros con que se consulta, tomados de `settings.py` (P6).
    Los de búsqueda van en el primer nivel (la corrida de evals lee `rerank_threshold`
    ahí, T-039): caminos, reranker encendido (`rerank`), candidatos por camino, umbral,
    cupos y espacio del contexto. La consulta los actualiza con los que informan la
    recuperación y la selección, que son los mismos. `generation`, `embeddings` y
    `reranker` describen los modelos."""
    return {
        "ai_timeout_seconds": settings.AI_TIMEOUT_SECONDS,
        "paths": list(retrieval.ALL_PATHS),
        "rerank": True,
        "candidates_per_path": settings.RETRIEVAL_CANDIDATES_PER_PATH,
        "rerank_threshold": settings.RERANK_THRESHOLD,
        "units_per_category": settings.SELECTION_UNITS_PER_CATEGORY,
        "considerandos": settings.SELECTION_CONSIDERANDOS,
        "context_tokens": settings.GENERATION_CONTEXT_TOKENS,
        "max_output_tokens": settings.GENERATION_MAX_OUTPUT_TOKENS,
        "template_margin_tokens": settings.PROMPT_TEMPLATE_MARGIN_TOKENS,
        "unit_by_passages_from_tokens": settings.UNIT_BY_PASSAGES_FROM_TOKENS,
        "generation": {
            "model": settings.GENERATION_MODEL,
            "file": settings.GENERATION_MODEL_FILE,
            "sha256": settings.GENERATION_MODEL_SHA256,
            "engine_build": settings.GENERATION_ENGINE_BUILD,
            "context_tokens": settings.GENERATION_CONTEXT_TOKENS,
            "temperature": settings.GENERATION_TEMPERATURE,
            "seed": settings.GENERATION_SEED,
            "thinking": settings.GENERATION_THINKING,
            "max_output_tokens": settings.GENERATION_MAX_OUTPUT_TOKENS,
            "max_statements": settings.GENERATION_MAX_STATEMENTS,
        },
        "embeddings": {
            "model": settings.EMBEDDINGS_MODEL,
            "file": settings.EMBEDDINGS_MODEL_FILE,
            "sha256": settings.EMBEDDINGS_MODEL_SHA256,
        },
        "reranker": {
            "model": settings.RERANKER_MODEL,
            "file": settings.RERANKER_MODEL_FILE,
            "sha256": settings.RERANKER_MODEL_SHA256,
        },
    }


def _service_error(error):
    """La falla de un cliente de IA tal como se registra."""
    return {
        "type": SERVICE_ERROR,
        "reason": error.reason,
        "service": error.service,
        "status": error.status,
        "detail": error.detail,
        "message": str(error),
    }


class _Clock:
    """Tiempos de cada etapa y total, en segundos."""

    def __init__(self):
        self.start = time.monotonic()
        self.timings = {}

    def stage(self, name, since):
        self.timings[name] = round(time.monotonic() - since, 3)

    def total(self):
        self.timings["total"] = round(time.monotonic() - self.start, 3)
        return self.timings


def _reserve_query_id():
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval(pg_get_serial_sequence(%s, 'id'))", [QUERY_TABLE])
        return cursor.fetchone()[0]


@contextmanager
def _snapshot():
    """Transacción `REPEATABLE READ` de solo lectura: todo lo que se lee adentro ve la
    base en el momento de la primera lectura. Si ya hay una transacción abierta (por
    ejemplo, la de una prueba), no se puede cambiar su aislamiento: se usa un punto de
    guardado dentro de ella."""
    if connection.in_atomic_block:
        with transaction.atomic():
            yield
        return
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        yield


def _empty_record():
    """Registro de una consulta antes de empezar: lo que no se llega a hacer queda
    vacío."""
    return {
        "parameters": parameters(),
        "candidates": [],
        "selected": {
            "sent": [],
            "added": [],
            "left_out": [],
            "over_quota": [],
            "abstention": {"abstained": False, "reason": None},
        },
        "max_score": None,
        "prompt_version": "",
        "request": None,
        "raw_output": "",
        "anomalies": [],
    }


@dataclass
class _Ready:
    """Lo que se le muestra al modelo después de la selección y del control del
    pedido."""

    unit_ids: list
    passages: dict = field(default_factory=dict)


def ask(user, question, reference_date=None, *, channel=Channel.SCREEN):
    """Ejecuta una consulta de punta a punta y devuelve la `Query` guardada, con el
    resultado en `query.result`. Ver el módulo.

    - `reference_date`: la fecha de autorización del procedimiento, o `None` para usar
      la del día.
    - `channel`: `screen`, `command` o `eval`.

    Lanza `RoleRejected` sin rol, `QueryRefused` con la pregunta vacía y `FutureDate`
    con una fecha posterior al día; en esos casos no consulta ni deja registro de
    consulta (el rechazo por rol deja su hecho `rejected`, con el canal recibido).
    """
    require_role(user, Role.READ, channel=channel)
    if not question or not question.strip():
        raise QueryRefused("Escriba una pregunta.")
    reference_date = validate_reference_date(reference_date)
    asked_at = timezone.now()
    clock = _Clock()
    record = _empty_record()

    with _snapshot():
        corpus_version = audit.current_corpus_version()
        since = time.monotonic()
        regime = applicable_regimes(reference_date)
        clock.stage("regimes", since)
        prepared = _prepare(question, reference_date, regime, record, clock)

    if isinstance(prepared, _Ready):
        outcome = _generate(question, reference_date, prepared, record, clock)
    else:
        outcome = prepared

    result = {
        "query_id": None,
        "status": outcome["status"],
        "reason": outcome["reason"],
        "reference_date": reference_date.isoformat(),
        "regime": regime,
        "notices": [],
        "statements": outcome.get("statements", []),
        "units": outcome.get("units", {}),
    }
    return _save(user, channel, question, reference_date, asked_at, result, record,
                 clock.total(), corpus_version)


def _abstain(record, reason, result_reason=None):
    """"No determinado": anota la decisión con su motivo y devuelve la parte del
    resultado. `result_reason` es el motivo del resultado si difiere del de la
    decisión."""
    record["selected"]["abstention"] = {"abstained": True, "reason": reason}
    return _undetermined(result_reason or reason)


def _prepare(question, reference_date, regime, record, clock):
    """Recupera y selecciona, dentro de la instantánea. Devuelve `_Ready` si hay que
    llamar al modelo, o la parte del resultado si la consulta termina acá. Completa
    `record`."""
    if not regime:
        return _abstain(record, Reason.NO_REGIME_AT_DATE.value)

    since = time.monotonic()
    try:
        found = retrieval.retrieve(question, reference_date)
    except AIServiceError as error:
        clock.stage("retrieval", since)
        record["anomalies"].append(_service_error(error))
        return _error(error.reason)
    clock.stage("retrieval", since)

    search = record["parameters"]
    search.update(paths=list(found.parameters["paths"]),
                  rerank=found.parameters["reranker"],
                  candidates_per_path=found.parameters["candidates_per_path"],
                  rerank_threshold=found.parameters["rerank_threshold"])
    record["candidates"] = _candidate_records(found.candidates)
    record["max_score"] = found.max_score
    retrieved = found.as_record()
    record["selected"]["retrieval"] = {key: retrieved[key]
                                       for key in ("path_counts", "units", "reason")}
    if not found.candidates:
        return _abstain(record, NO_CANDIDATES, Reason.BELOW_THRESHOLD.value)
    if not found.selected:
        return _abstain(record, Reason.BELOW_THRESHOLD.value)

    since = time.monotonic()
    try:
        prompt_tokens = (generation.count_tokens(answering.load_instructions())
                         + generation.count_tokens(
                             answering.request_head(question, reference_date)))
        record["prompt_version"] = answering.PROMPT_VERSION_WITH_DATE
        selection = retrieval.select_units(found, prompt_tokens)
        search.update(selection.parameters)
        record["anomalies"].extend(selection.anomalies)
        unit_ids, passages, check = _check_request(question, reference_date, found,
                                                   selection)
    except AIServiceError as error:
        clock.stage("selection", since)
        record["anomalies"].append(_service_error(error))
        return _error(error.reason)
    clock.stage("selection", since)

    scores = {unit.unit_id: unit for unit in found.units}
    removed = check["removed"] if check else []
    selected = record["selected"]
    selected.update(
        sent=[scores[unit_id].as_record() for unit_id in unit_ids],
        added=[{"unit": a["unit"],
                "modifies": [pk for pk in a["modifies"] if pk in unit_ids]}
               for a in selection.added
               if any(pk in unit_ids for pk in a["modifies"])],
        left_out=([{**entry, "check": CHECK_SELECTION} for entry in selection.left_out]
                  + [{"unit": pk, "tokens": selection.tokens.get(pk),
                      "check": CHECK_REQUEST} for pk in removed]),
        over_quota=list(selection.over_quota),
        selection=selection.as_record(),
    )
    if check is not None:
        selected["request_check"] = check
    if not unit_ids:
        return _error(Reason.INPUT_TOO_LONG.value)
    return _Ready(unit_ids=unit_ids, passages=passages)


def _candidate_records(candidates):
    """Cada candidato como se registra, con el origen del texto de su unidad."""
    origins = dict(Unit.objects.filter(pk__in={c.unit_id for c in candidates})
                   .values_list("pk", "text_origin"))
    return [{**c.as_record(), "text_origin": origins.get(c.unit_id)}
            for c in candidates]


def _build_request(question, reference_date, unit_ids, passages):
    """`answering.build_request` con los tramos de la selección que corresponden a
    unidades mostradas. Después de sacar una unidad, sus tramos (o los de la que la
    modificaba) sobran y `build_request` los rechaza. Las unidades mostradas no dependen
    de los tramos: si alguna que entra por relación tiene tramos, se arma otra vez con
    ellos."""
    own = {pk: spans for pk, spans in passages.items() if pk in unit_ids}
    built = answering.build_request(question, unit_ids, reference_date, own)
    extra = {pk: spans for pk, spans in passages.items()
             if pk in built.shown and pk not in own}
    if extra:
        built = answering.build_request(question, unit_ids, reference_date,
                                        {**own, **extra})
    return built


def _check_request(question, reference_date, found, selection):
    """Control final del pedido completo (decisión 3 del Coordinador para T-040).

    Cuenta con `generation.count_tokens` cada mensaje del pedido que arma
    `answering.build_request`, el mismo que usa `answer`. Si el total supera el contexto
    menos el máximo de salida y el margen de la plantilla de conversación, saca la última
    unidad en la prioridad de la selección (`retrieval.priority_order`: la mejor de cada
    categoría, después la segunda, y así; los considerandos al final) y vuelve a contar,
    hasta que entre o no quede ninguna.

    Devuelve `(unit_ids, passages, check)`: las unidades y los tramos que se muestran, y
    `{"tokens", "limit", "removed"}`; `check` es `None` si no había unidades."""
    unit_ids = list(selection.unit_ids)
    if not unit_ids:
        return [], {}, None
    limit = (settings.GENERATION_CONTEXT_TOKENS - settings.GENERATION_MAX_OUTPUT_TOKENS
             - settings.PROMPT_TEMPLATE_MARGIN_TOKENS)
    units = Unit.objects.select_related("reading__document__norm").in_bulk(unit_ids)
    by_score = [units[u.unit_id] for u in found.selected if u.unit_id in units]
    priority = [unit.pk for unit in retrieval.priority_order(by_score)]

    counted = {}

    def count(text):
        if text not in counted:
            counted[text] = generation.count_tokens(text)
        return counted[text]

    removed = []
    shown = set()
    tokens = None
    while unit_ids:
        built = _build_request(question, reference_date, unit_ids, selection.passages)
        shown = built.shown
        tokens = sum(count(message["content"]) for message in built.messages)
        if tokens <= limit:
            break
        drop = next(pk for pk in reversed(priority) if pk in unit_ids)
        unit_ids.remove(drop)
        removed.append(drop)
        shown = set()
    passages = {pk: spans for pk, spans in selection.passages.items() if pk in shown}
    return unit_ids, passages, {"tokens": tokens, "limit": limit, "removed": removed}


def _generate(question, reference_date, ready, record, clock):
    """Genera fuera de la instantánea y devuelve la parte del resultado que arma
    `answering`. Completa `record`."""
    since = time.monotonic()
    generated = answering.answer(question, ready.unit_ids, reference_date,
                                 passages=ready.passages)
    clock.stage("generation", since)
    record.update(
        prompt_version=generated.prompt_version,
        request=generated.request,
        raw_output=generated.raw_output,
    )
    record["anomalies"].extend(generated.anomalies)
    if generated.error is not None:
        record["anomalies"].append({"type": SERVICE_ERROR,
                                    "reason": generated.result["reason"],
                                    **generated.error})
    if generated.result["status"] == Status.UNDETERMINED:
        record["selected"]["abstention"] = {"abstained": True,
                                            "reason": generated.result["reason"]}
    return generated.result


def _undetermined(reason):
    return {"status": Status.UNDETERMINED.value, "reason": Reason(reason).value}


def _error(reason):
    return {"status": Status.ERROR.value, "reason": Reason(reason).value}


def _save(user, channel, question, reference_date, asked_at, result, record, timings,
          corpus_version):
    """Guarda el hecho `query` y la fila de `queries_query`, una sola vez y completos,
    con la versión de la normativa con que se hizo la búsqueda."""
    outcome = Outcome.FAILED if result["status"] == Status.ERROR else Outcome.OK
    with transaction.atomic():
        query_id = _reserve_query_id()
        result["query_id"] = query_id
        event = audit.record(
            EventType.QUERY,
            outcome=outcome,
            channel=channel,
            user=user,
            corpus_version=corpus_version,
            detail={
                "query_id": query_id,
                "asked_at": asked_at,
                "question": question,
                "reference_date": reference_date.isoformat(),
                "regime": result["regime"],
                "notices": result["notices"],
                "status": result["status"],
                "reason": result["reason"],
                **record,
                "result": result,
                "timings": timings,
            },
        )
        return Query.objects.create(
            id=query_id,
            event=event,
            user=user,
            asked_at=asked_at,
            question=question,
            reference_date=reference_date,
            corpus_version=event.corpus_version,
            status=result["status"],
            reason=result["reason"] or "",
            result=result,
            timings=timings,
            **record,
        )
