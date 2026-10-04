"""Orden de las pasadas de una propuesta de matriz y creación de la versión borrador
(REQ-024, REQ-025, REQ-028, REQ-030; plan 003, "Propuesta de la matriz"; ADR-0019).

`propose(run, user=…, channel=…)` corre las pasadas del nivel de `run` (`MatrixRun`) sobre
los documentos base que la propuesta registró al pedirse (`run.documents`: cada uno con
su lectura) y deja una versión borrador de la matriz. Lo llama el manejador del pedido
`propose_matrix` (`services.matrix.run_propose_matrix`) y, después, la medición.

Pasadas de **media** (las de este módulo):

1. **Disposición por regla.** Sin pasar por el modelo: un tramo `titulo` queda descartado
   ("título"); `pagina` y `no_ubicado` quedan pendientes; todo tramo de una sección técnica
   queda `tecnico` (el encabezado de un renglón también; los demás títulos, descartados).
2. **Extracción** (`extraction.py`) de los tramos restantes: requisitos formales o
   económicos, marca técnica, o motivo de descarte; con reintento único.
3. **Marcadores.** Un tramo que el modelo descartó y tiene marcadores de obligación
   ("deberá", "mín.", "desestim", …) queda pendiente de revisión (en media no hay pasada
   de completitud). Si cuelga de un renglón, entra en la fila de su renglón.
4. **Filas técnicas** (`technical.py`): una por renglón, por regla.

Alta y exigente piden por ahora lo mismo que media y quedan registradas con su nombre (su
pasada de completitud y la segunda extracción llegan con T-078); la propuesta anota esa
anomalía. Las circulares y las consecuencias llegan con T-083 y T-080: los documentos
que no son base no se usan y la propuesta lo anota.

**Disposición de cada tramo.** Todo tramo queda con una disposición (`tenders_disposition`):
`requisitos`, `tecnico`, `descartado` o `pendiente`. Un tramo con requisitos y además citado
por una fila técnica queda `requisitos`. Un tramo que el modelo descartó y cuelga de un
renglón entra igual en la fila de su renglón (ante la duda, de más): queda `tecnico`, con
la anomalía registrada y el motivo del modelo en el pedido (`tenders_run_step.parsed`).

**Pendientes** (`tenders_pending_item`): los de la lectura (`pagina_ilegible`,
`pagina_dudosa`, `tabla`, `no_ubicado`) y los de la propuesta (`sin_disposicion`,
`marcadores`, `renglon_sin_especificaciones`). Uno por tramo: el de la lectura gana, y
después el de la propuesta.

**Qué se guarda y cuándo.** Cada pedido al modelo se guarda apenas vuelve, fuera de la
transacción final, así que queda aunque la propuesta falle. La versión borrador, sus
requisitos, citas, pendientes y disposiciones, el resultado de la propuesta y el hecho
`matrix_proposal` se crean en una sola transacción: nunca queda una matriz a medias
(ADR-0018). Si algo falla, queda el hecho `matrix_proposal` con resultado `failed` y el
motivo, y el error se vuelve a lanzar para que la cola deje el pedido `failed`.

Los requisitos formales y económicos van primero, en el orden del pliego; después los
técnicos, por renglón. Cada requisito formal o económico tiene una cita: el fragmento
literal, o el tramo entero con la marca `cita_amplia`. Cada requisito técnico tiene una
cita por tramo, con su alcance (`propia` o `general`). El texto de toda cita es igual al
recorte del texto canónico de la lectura.
"""

import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction
from django.db.models import Max

from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.tenders.models import (
    Disposition,
    DispositionOutcome,
    DispositionSource,
    MatrixVersion,
    PendingItem,
    PendingReason,
    Reading,
    Requirement,
    RequirementClass,
    RequirementOrigin,
    RequirementQuote,
    RequirementState,
    SegmentType,
    VersionStatus,
)
from evaluon.tenders.proposal import extraction, quotes, technical
from evaluon.tenders.segmenting import RULES_VERSION
from evaluon.tenders.services.procedures import _snapshot, regime_for

# Pasadas de cada nivel. Mientras alta y exigente no tengan las suyas (T-078), piden lo
# mismo que media.
PASSES_MEDIA = ("reglas", "extraccion", "marcadores", "filas_tecnicas")
PASSES = {"media": PASSES_MEDIA, "alta": PASSES_MEDIA, "exigente": PASSES_MEDIA}
LEVELS_WITHOUT_OWN_PASSES = ("alta", "exigente")

# Marcadores de obligación (plan 003, "Pasadas"); se comparan sin tildes ni mayúsculas.
OBLIGATION_MARKERS = (
    "deberá",
    "deberán",
    "será requisito",
    "mín.",
    "máx.",
    "no se aceptarán",
    "bajo apercibimiento",
    "desestim",
)

ANOMALY_DISCARDED_IN_ITEM = "descartado_en_renglon"
ANOMALY_UNPROCESSED_DOCUMENTS = "documentos_no_procesados"
ANOMALY_LEVEL_WITHOUT_PASSES = "nivel_sin_pasadas_propias"
ANOMALY_TECHNICAL_WITHOUT_ITEMS = "secciones_tecnicas_sin_renglones"

# Orden de prioridad de los motivos de un pendiente: gana el de la lectura.
_READING_PENDING = (
    PendingReason.PAGINA_ILEGIBLE.value,
    PendingReason.PAGINA_DUDOSA.value,
    PendingReason.TABLA.value,
    PendingReason.NO_UBICADO.value,
)


def _fold(text):
    """Minúsculas y sin tildes."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


_FOLDED_MARKERS = tuple(_fold(marker) for marker in OBLIGATION_MARKERS)


def has_obligation_markers(text):
    """Si el texto tiene algún marcador de obligación."""
    folded = _fold(text)
    return any(marker in folded for marker in _FOLDED_MARKERS)


@dataclass
class Decision:
    """Qué pasó con un tramo: su disposición y lo que hace falta para armar la matriz."""

    outcome: str
    discard_reason: str = ""
    source: str = DispositionSource.REGLA.value
    step: object = None
    pending_reason: str = ""
    found: list = field(default_factory=list)
    marks: list = field(default_factory=list)


def rule_decision(segment, is_item_header):
    """La disposición de un tramo que no pasa por el modelo, o `None` si debe pasar.
    `is_item_header` dice si el tramo es el encabezado de un renglón."""
    kind = segment.segment_type
    if kind in (SegmentType.PAGINA, SegmentType.NO_UBICADO):
        return Decision(DispositionOutcome.PENDIENTE.value)
    if segment.section_class == RequirementClass.TECNICO:
        if kind == SegmentType.TITULO and not is_item_header:
            return Decision(DispositionOutcome.DESCARTADO.value, "titulo")
        return Decision(DispositionOutcome.TECNICO.value)
    if kind == SegmentType.TITULO:
        return Decision(DispositionOutcome.DESCARTADO.value, "titulo")
    return None


def model_decision(unit, outcome, anomalies):
    """La disposición de un tramo según lo que el modelo devolvió (`extraction.Outcome`)."""
    segment = unit.segment
    base = {"source": DispositionSource.MODELO.value, "step": outcome.step}
    if not outcome.valid:
        return Decision(DispositionOutcome.PENDIENTE.value,
                        pending_reason=PendingReason.SIN_DISPOSICION.value, **base)
    if outcome.found:
        return Decision(DispositionOutcome.REQUISITOS.value, found=outcome.found,
                        marks=list(outcome.technical), **base)
    if outcome.technical:
        return Decision(DispositionOutcome.TECNICO.value, marks=list(outcome.technical),
                        **base)
    if segment.items:
        anomalies.append({"type": ANOMALY_DISCARDED_IN_ITEM, "segment": segment.pk,
                          "key": segment.key, "motivo": outcome.discard})
        return Decision(DispositionOutcome.TECNICO.value, **base)
    if has_obligation_markers(segment.text):
        return Decision(DispositionOutcome.PENDIENTE.value,
                        pending_reason=PendingReason.MARCADORES.value, **base)
    return Decision(DispositionOutcome.DESCARTADO.value,
                    discard_reason=outcome.discard, **base)


# --- Carga de lo que la propuesta usa ------------------------------------------------------


@dataclass
class Loaded:
    """Los documentos base de la propuesta con sus lecturas y tramos."""

    readings: dict
    units: list
    items: list
    reading_of: dict
    header_pks: set


def load(run):
    """Lee de la base las lecturas que la propuesta registró (`run.documents`) y arma las
    unidades en el orden del pliego."""
    readings, units, reading_of = {}, [], {}
    keyed = []
    position = 0
    for entry in run.documents:
        reading = Reading.objects.select_related("document").get(pk=entry["reading"])
        readings[reading.pk] = reading
        by_key = {}
        for segment in reading.segments.order_by("order"):
            segment.reading = reading
            position += 1
            units.append(extraction.Unit(segment, reading.document.title, position))
            reading_of[segment.pk] = reading
            by_key[segment.key] = segment
        keyed.append((reading, by_key))
    items = technical.reading_items(keyed)
    header_pks = {segment.pk for _, segment in items if segment is not None}
    return Loaded(readings=readings, units=units, items=items, reading_of=reading_of,
                  header_pks=header_pks)


# --- Propuesta -----------------------------------------------------------------------------


def _models():
    return {
        "generation_batch": {
            "model": settings.GENERATION_MODEL,
            "file": settings.GENERATION_MODEL_FILE,
            "sha256": settings.GENERATION_MODEL_SHA256,
            "engine_build": settings.GENERATION_ENGINE_BUILD,
            "context_tokens": settings.GENERATION_CONTEXT_TOKENS,
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


def _parameters(run):
    return {
        "passes": list(PASSES[run.level]),
        "temperature": settings.GENERATION_TEMPERATURE,
        "seed": settings.GENERATION_SEED,
        "thinking": settings.GENERATION_THINKING,
        "batch_input_tokens": settings.MATRIX_BATCH_INPUT_TOKENS,
        "max_output_tokens": settings.MATRIX_MAX_OUTPUT_TOKENS,
        "segment_max_chars": settings.SEGMENT_MAX_CHARS,
        "generation_batch_url": settings.GENERATION_BATCH_URL,
        "generation_batch_timeout_seconds": settings.GENERATION_BATCH_TIMEOUT_SECONDS,
        "rules_version": RULES_VERSION,
        "obligation_markers": list(OBLIGATION_MARKERS),
    }


def _begin(run):
    """Fija fecha, régimen, versión de la normativa, modelos, parámetros e instrucciones
    de la propuesta, en una misma instantánea (P6, P8)."""
    run.authorization_date = run.procedure.authorization_date
    with _snapshot():
        run.corpus_version = audit.current_corpus_version()
        run.regime = regime_for(run.authorization_date)
    run.models = _models()
    run.parameters = _parameters(run)
    run.prompt_versions = {"extraccion": settings.MATRIX_PROMPT_VERSIONS["extraccion"]}
    run.save(update_fields=["authorization_date", "corpus_version", "regime", "models",
                            "parameters", "prompt_versions"])


def _pending_reason(segment, decision):
    """El motivo del pendiente de un tramo, o `None` si no tiene: el de la lectura gana
    sobre el de la propuesta."""
    if segment.review_reason in _READING_PENDING:
        return segment.review_reason
    if decision.outcome == DispositionOutcome.PENDIENTE.value:
        return decision.pending_reason or segment.review_reason or None
    return None


def _wide_or_span(segment, found):
    """Posiciones absolutas (inicio, fin) de la cita de un requisito ubicado: el
    fragmento, o el tramo entero si es una cita amplia."""
    if found.flag == quotes.WIDE:
        start, end = quotes.whole(segment)
    else:
        start, end = quotes.absolute(segment, found.span)
    return start, end


def _check_quote(reading, start, end, text):
    if reading.canonical_text[start:end] != text:
        raise RuntimeError(
            "La cita no es igual al recorte del texto canónico de la lectura "
            f"({start}:{end}): no se guardó la matriz."
        )


def _quote_record(segment, start, end, text, scope="", flag=""):
    return {"segment": segment.pk, "key": segment.key, "char_start": start,
            "char_end": end, "text": text, "scope": scope, "flag": flag}


def propose(run, *, user, channel=Channel.COMMAND):
    """Corre las pasadas del nivel de `run` y deja la versión borrador. Devuelve la
    `MatrixVersion`. Ver el módulo."""
    clock = time.monotonic()
    timings = {}
    anomalies = []
    extractor = None
    try:
        _begin(run)
        if run.level in LEVELS_WITHOUT_OWN_PASSES:
            anomalies.append({
                "type": ANOMALY_LEVEL_WITHOUT_PASSES, "level": run.level,
                "detail": "completitud y segunda extracción llegan con T-078: se corren "
                          "las pasadas de media",
            })
        others = run.procedure.documents.exclude(
            pk__in=[entry["document"] for entry in run.documents]
        ).values_list("pk", flat=True)
        if others:
            anomalies.append({"type": ANOMALY_UNPROCESSED_DOCUMENTS,
                              "documents": sorted(others),
                              "detail": "circulares y respuestas llegan con T-083"})

        # 1. Disposición por regla.
        started = time.monotonic()
        loaded = load(run)
        decisions, to_model = {}, []
        for unit in loaded.units:
            decision = rule_decision(unit.segment, unit.segment.pk in loaded.header_pks)
            if decision is None:
                to_model.append(unit)
            else:
                decisions[unit.segment.pk] = decision
        timings["reglas"] = round(time.monotonic() - started, 3)

        # 2. Extracción.
        started = time.monotonic()
        numbers = [number for number, _ in loaded.items]
        extractor = extraction.Extractor(run, numbers)
        result = extractor.extract(to_model)
        timings["extraccion"] = round(time.monotonic() - started, 3)
        anomalies.extend(result.anomalies)

        # 3. Marcadores (dentro de la disposición del tramo descartado).
        started = time.monotonic()
        by_pk = {unit.segment.pk: unit for unit in loaded.units}
        for pk, outcome in result.outcomes.items():
            decisions[pk] = model_decision(by_pk[pk], outcome, anomalies)
        timings["marcadores"] = round(time.monotonic() - started, 3)

        # 4. Filas técnicas.
        started = time.monotonic()
        contributions = []
        for unit in loaded.units:
            decision = decisions[unit.segment.pk]
            segment = unit.segment
            hangs_pending = (
                decision.outcome == DispositionOutcome.PENDIENTE.value
                and bool(segment.items)
                and (
                    decision.pending_reason == PendingReason.SIN_DISPOSICION.value
                    or (segment.segment_type == SegmentType.NO_UBICADO
                        and segment.pk in loaded.header_pks)
                )
            )
            if (
                decision.outcome == DispositionOutcome.TECNICO.value
                or (decision.outcome == DispositionOutcome.REQUISITOS.value
                    and decision.marks)
                or hangs_pending
            ):
                contributions.append(technical.Contribution(unit, tuple(decision.marks)))
        rows = technical.build_rows(loaded.items, contributions, anomalies)
        if not loaded.items and any(
            unit.segment.section_class == RequirementClass.TECNICO for unit in loaded.units
        ):
            anomalies.append({"type": ANOMALY_TECHNICAL_WITHOUT_ITEMS,
                              "detail": "hay secciones técnicas y ningún renglón "
                                        "reconocido: una sola fila técnica sin renglón"})
        timings["filas_tecnicas"] = round(time.monotonic() - started, 3)

        # Guardado: todo o nada.
        started = time.monotonic()
        with transaction.atomic():
            version = _save(run, loaded, decisions, rows, result, anomalies, timings,
                            clock, user, channel, started)
    except Exception as error:
        _record_failure(run, user, channel, error, extractor, timings, clock)
        raise
    return version


def _requirement_sort_key(item):
    unit, found = item
    return (unit.position, found.span[0])


def _save(run, loaded, decisions, rows, result, anomalies, timings, clock, user, channel,
          started):
    """Crea la versión borrador y todo lo que cuelga de ella, y deja el hecho
    `matrix_proposal`. Corre dentro de una transacción."""
    procedure = run.procedure
    number = (procedure.matrix_versions.aggregate(last=Max("number"))["last"] or 0) + 1
    version = MatrixVersion.objects.create(
        procedure=procedure, number=number, status=VersionStatus.DRAFT, level=run.level,
        run=run, created_by=user,
    )
    by_pk = {unit.segment.pk: unit for unit in loaded.units}

    # Disposiciones: una por tramo.
    Disposition.objects.bulk_create(
        Disposition(
            run=run, segment_id=unit.segment.pk, outcome=decisions[unit.segment.pk].outcome,
            discard_reason=decisions[unit.segment.pk].discard_reason,
            source=decisions[unit.segment.pk].source,
            step=decisions[unit.segment.pk].step,
        )
        for unit in loaded.units
    )

    # Requisitos formales y económicos, en el orden del pliego.
    body = []
    for unit in loaded.units:
        for found in decisions[unit.segment.pk].found:
            body.append((unit, found))
    body.sort(key=_requirement_sort_key)
    counter = 0
    by_class = Counter()
    for unit, found in body:
        counter += 1
        segment = unit.segment
        reading = loaded.reading_of[segment.pk]
        start, end = _wide_or_span(segment, found)
        text = (segment.text if found.flag == quotes.WIDE
                else segment.text[found.span[0]:found.span[1]])
        _check_quote(reading, start, end, text)
        record = _quote_record(segment, start, end, text, flag=found.flag)
        requirement = Requirement.objects.create(
            version=version, number=counter, category=found.category,
            items=list(segment.items), origin=RequirementOrigin.PROPUESTO,
            state=RequirementState.PROPUESTO,
            proposed={"category": found.category, "items": list(segment.items),
                      "quotes": [record]},
            step=found.step, passes=["extraccion"],
        )
        RequirementQuote.objects.create(
            requirement=requirement, order=1, segment=segment, char_start=start,
            char_end=end, text=text, scope="", quote_flag=found.flag,
        )
        by_class[found.category] += 1

    # Filas técnicas, una por renglón.
    technical_rows = []
    for row in rows:
        counter += 1
        items = [row.number] if row.number is not None else []
        records = []
        for order, quote in enumerate(row.quotes, start=1):
            segment = quote.segment
            reading = loaded.reading_of[segment.pk]
            _check_quote(reading, segment.char_start, segment.char_end, segment.text)
            records.append((order, segment, quote.scope))
        requirement = Requirement.objects.create(
            version=version, number=counter, category=RequirementClass.TECNICO.value,
            items=items, origin=RequirementOrigin.PROPUESTO,
            state=RequirementState.PROPUESTO,
            proposed={"category": RequirementClass.TECNICO.value, "items": items,
                      "quotes": [_quote_record(segment, segment.char_start,
                                               segment.char_end, segment.text, scope)
                                 for _, segment, scope in records]},
            step=None, passes=[],
        )
        RequirementQuote.objects.bulk_create(
            RequirementQuote(requirement=requirement, order=order, segment=segment,
                             char_start=segment.char_start, char_end=segment.char_end,
                             text=segment.text, scope=scope, quote_flag="")
            for order, segment, scope in records
        )
        by_class[RequirementClass.TECNICO.value] += 1
        technical_rows.append({
            "item": row.number,
            "quotes": len(records),
            "own": sum(1 for _, _, scope in records if scope == "propia"),
            "general": sum(1 for _, _, scope in records if scope == "general"),
        })

    # Pendientes: uno por tramo.
    pending = {}
    for unit in loaded.units:
        reason = _pending_reason(unit.segment, decisions[unit.segment.pk])
        if reason:
            pending[unit.segment.pk] = reason
    for row in rows:
        if row.pending is not None:
            pending.setdefault(row.pending.pk,
                               PendingReason.RENGLON_SIN_ESPECIFICACIONES.value)
    PendingItem.objects.bulk_create(
        PendingItem(version=version, segment_id=pk, reason=reason)
        for pk, reason in sorted(pending.items(), key=lambda kv: by_pk[kv[0]].position)
    )

    # Cuentas, tiempos y resultado de la propuesta.
    outcomes = Counter(d.outcome for d in decisions.values())
    discards = Counter(d.discard_reason for d in decisions.values()
                       if d.outcome == DispositionOutcome.DESCARTADO.value)
    wide = sum(1 for unit, found in body if found.flag == quotes.WIDE)
    counts = {
        "documents": len(loaded.readings),
        "segments": len(loaded.units),
        "segments_by_type": dict(Counter(u.segment.segment_type for u in loaded.units)),
        "segments_by_source": dict(Counter(d.source for d in decisions.values())),
        "dispositions": dict(outcomes),
        "discards_by_reason": dict(discards),
        "pending_by_reason": dict(Counter(pending.values())),
        "items": [number for number, _ in loaded.items],
        "requirements": sum(by_class.values()),
        "requirements_by_class": dict(by_class),
        "technical_rows": technical_rows,
        "model_requests": result.stats["requests"],
        "segments_retried": result.stats["segments_retried"],
        "quotes_retried": result.stats["quotes_retried"],
        "split_batches": result.stats["split_batches"],
        "wide_quotes": wide,
    }
    timings["guardado"] = round(time.monotonic() - started, 3)
    timings["total"] = round(time.monotonic() - clock, 3)
    run.counts = counts
    run.timings = timings
    run.anomalies = anomalies
    run.version = version
    run.save(update_fields=["counts", "timings", "anomalies", "version"])

    audit.record(
        EventType.MATRIX_PROPOSAL, outcome=Outcome.OK, channel=channel, user=user,
        corpus_version=run.corpus_version,
        detail={
            "procedure": procedure.pk,
            "run": run.pk,
            "job": run.job_id,
            "version": version.pk,
            "version_number": version.number,
            "level": run.level,
            "run_channel": run.channel,
            "authorization_date": run.authorization_date.isoformat(),
            "regime": run.regime,
            "corpus_version": run.corpus_version,
            "documents": run.documents,
            "models": run.models,
            "parameters": run.parameters,
            "prompt_versions": run.prompt_versions,
            "counts": counts,
            "timings": timings,
            "anomalies": dict(Counter(a["type"] for a in anomalies)),
        },
    )
    return version


def _record_failure(run, user, channel, error, extractor, timings, clock):
    """Deja el hecho `matrix_proposal` fallido. Lo ya guardado en `tenders_run_step`
    queda."""
    timings = {**timings, "total": round(time.monotonic() - clock, 3)}
    audit.record(
        EventType.MATRIX_PROPOSAL, outcome=Outcome.FAILED, channel=channel, user=user,
        detail={
            "procedure": run.procedure_id,
            "run": run.pk,
            "job": run.job_id,
            "level": run.level,
            "run_channel": run.channel,
            "error": f"{type(error).__name__}: {error}",
            "model_requests_saved": len(extractor.steps) if extractor else 0,
            "timings": timings,
        },
    )
