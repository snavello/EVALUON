"""Consulta de punta a punta con su registro (REQ-008, REQ-009, REQ-012, REQ-013,
REQ-020; plan 001, "Fecha de autorización y régimen aplicado", "Abstención", "Forma de la
respuesta" y "Registro de auditoría"). Versión mínima de T-019.

`ask(usuario, pregunta, fecha, channel=...)` es el único camino para ejecutar una
consulta: la usan la pantalla, los comandos y las evals. Hace, en este orden:

1. Comprueba el rol (los dos roles consultan) y que la pregunta no esté vacía.
2. Valida la fecha de autorización del procedimiento: vacía, la del día en hora de
   Buenos Aires; posterior al día, se rechaza con `FutureDate` sin consultar y sin dejar
   registro de consulta.
3. Llama a `applicable_regimes(fecha)` y guarda lo que devuelve como régimen aplicado,
   con el nombre de cita de cada norma (`norms_norm.citation`). Sin régimen termina en
   "no determinado" con `no_regime_at_date`, sin buscar ni llamar al modelo.
4. Recupera con esa fecha (`retrieval.retrieve`). Si nada alcanza el umbral termina en
   "no determinado" con `below_threshold`, sin llamar al modelo.
5. Genera con las unidades seleccionadas (`answering.answer`).
6. Arma el resultado con la forma de "Forma de la respuesta" (`query_id`,
   `reference_date`, `regime` y `notices` vacío en los tres estados) y guarda, en una sola
   transacción, el hecho `query` de `audit_event` y la fila de `queries_query`, cada uno
   una sola vez y completo.

Fallas técnicas. La recuperación deja pasar los errores propios de los clientes de
embeddings y reranker; la generación los devuelve en `Answer.error`. Los dos estilos
terminan igual: estado `error` con el motivo del error (`timeout`, `service_unavailable`,
`input_too_long`) o `invalid_output`, nunca "no determinado". El servicio, el código
HTTP (`status`), el detalle y el mensaje del error quedan en `anomalies` como
`service_error`, para distinguir un servicio caído de un pedido mal armado (P6).

Inserción única. `audit_event` y `queries_query` solo admiten inserciones, y el
resultado guardado en los dos lleva `query_id`. Por eso el `id` de la consulta se reserva
antes con `nextval` sobre la secuencia de `queries_query.id`, se inserta el hecho con el
resultado completo y después la fila con ese `id`, el usuario y la versión de la
normativa del hecho, y `asked_at` con el momento de la pregunta.

Los avisos de modificatorias sin cargar (`notices`) son de T-052; la recuperación y la
generación completas y el resto del registro, de T-040. Los clientes de IA se usan por su
módulo, dentro de `retrieval` y `answering`.
"""

import time

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from evaluon.accounts.models import Role
from evaluon.accounts.permissions import require_role
from evaluon.ai import AIServiceError
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.queries import answering, retrieval
from evaluon.queries.models import Query, Reason, Status

QUERY_TABLE = Query._meta.db_table

# Tipo de anomalía con que se registra la falla de un servicio de IA.
SERVICE_ERROR = "service_error"

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
    """Copia de los parámetros con que se consulta (P6)."""
    return {
        "candidates_per_path": settings.RETRIEVAL_CANDIDATES_PER_PATH,
        "rerank_threshold": settings.RERANK_THRESHOLD,
        "ai_timeout_seconds": settings.AI_TIMEOUT_SECONDS,
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


def ask(user, question, reference_date=None, *, channel=Channel.SCREEN):
    """Ejecuta una consulta de punta a punta y devuelve la `Query` guardada, con el
    resultado en `query.result`. Ver el módulo.

    - `reference_date`: la fecha de autorización del procedimiento, o `None` para usar
      la del día.
    - `channel`: `screen`, `command` o `eval`.

    Lanza `RoleRejected` sin rol, `QueryRefused` con la pregunta vacía y `FutureDate`
    con una fecha posterior al día; en esos casos no consulta ni deja registro de
    consulta.
    """
    require_role(user, Role.READ)
    if not question or not question.strip():
        raise QueryRefused("Escriba una pregunta.")
    reference_date = validate_reference_date(reference_date)
    asked_at = timezone.now()
    clock = _Clock()

    record = {
        "parameters": parameters(),
        "candidates": [],
        "selected": {"sent": []},
        "max_score": None,
        "prompt_version": "",
        "request": None,
        "raw_output": "",
        "anomalies": [],
    }

    since = time.monotonic()
    regime = applicable_regimes(reference_date)
    clock.stage("regimes", since)
    outcome = _run(question, reference_date, regime, record, clock)

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
                 clock.total())


def _run(question, reference_date, regime, record, clock):
    """Recupera y genera según corresponda. Devuelve la parte del resultado que no
    depende de la fecha ni del régimen, y completa `record`."""
    if not regime:
        return _undetermined(Reason.NO_REGIME_AT_DATE)

    since = time.monotonic()
    try:
        found = retrieval.retrieve(question, reference_date)
    except AIServiceError as error:
        clock.stage("retrieval", since)
        record["anomalies"].append(_service_error(error))
        return _error(error.reason)
    clock.stage("retrieval", since)
    record.update(
        candidates=[c.as_record() for c in found.candidates],
        selected={"sent": [u.as_record() for u in found.selected]},
        max_score=found.max_score,
    )
    record["parameters"].update(found.parameters)
    if not found.selected:
        return _undetermined(Reason.BELOW_THRESHOLD)

    since = time.monotonic()
    generated = answering.answer(question, [u.unit_id for u in found.selected])
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
    return generated.result


def _undetermined(reason):
    return {"status": Status.UNDETERMINED.value, "reason": Reason(reason).value}


def _error(reason):
    return {"status": Status.ERROR.value, "reason": Reason(reason).value}


def _save(user, channel, question, reference_date, asked_at, result, record, timings):
    """Guarda el hecho `query` y la fila de `queries_query`, una sola vez y completos."""
    outcome = Outcome.FAILED if result["status"] == Status.ERROR else Outcome.OK
    with transaction.atomic():
        query_id = _reserve_query_id()
        result["query_id"] = query_id
        event = audit.record(
            EventType.QUERY,
            outcome=outcome,
            channel=channel,
            user=user,
            detail={
                "query_id": query_id,
                "asked_at": asked_at,
                "question": question,
                "reference_date": reference_date.isoformat(),
                "regime": result["regime"],
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
