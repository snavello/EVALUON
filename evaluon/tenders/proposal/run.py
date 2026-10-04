"""Orden de las pasadas de una propuesta de matriz y creación de la versión borrador
(REQ-024, REQ-025, REQ-028, REQ-030; plan 003, "Propuesta de la matriz"; ADR-0019).

`propose(run, user=…, channel=…)` corre el proceso único (`PASSES`) sobre
los documentos base que la propuesta registró al pedirse (`run.documents`: cada uno con
su lectura) y deja una versión borrador de la matriz. Lo llama el manejador del pedido
`propose_matrix` (`services.matrix.run_propose_matrix`) y, después, la medición. Desde el
2026-10-04 (REQ-030 enmendado) hay un solo proceso, el más completo; no hay niveles ni
segunda extracción, y la propuesta registra el proceso y la versión de cada instrucción.

Pasadas, en orden:

1. **Disposición por regla.** Sin pasar por el modelo: un tramo `titulo` queda descartado
   ("título"); `pagina` y `no_ubicado` quedan pendientes; todo tramo de una sección técnica
   queda `tecnico` (el encabezado de un renglón también; los demás títulos, descartados).
2. **Extracción** (`extraction.py`) de los tramos restantes: requisitos formales o
   económicos, marca técnica, o motivo de descarte; con reintento único.
3. **Completitud** (`completeness.py`; solo formales y económicos): revisa cada tramo con
   requisitos y cada tramo que el modelo descartó teniendo marcadores de obligación
   ("deberá", "mín.", "desestim", …): suma los que faltan y divide los que juntan dos
   condiciones. Un descartado con marcadores queda pendiente solo si la completitud no dio
   resultado.
4. **Filas técnicas** (`technical.py`): una por renglón, por regla, después de la
   completitud. Los tramos de secciones técnicas no pasan por el modelo y no llegan a la
   completitud.

Cada requisito formal o económico guarda en `passes` las pasadas que lo encontraron.

**Consecuencias** (`consequences.py`; T-080), la última pasada: para cada
requisito, ya numerado como lo va a quedar en la versión, sugiere hasta tres consecuencias
con su fundamento del pliego o de la norma, o la deja "no determinada". Las crea `_save`
junto con los requisitos, en la misma transacción.

**Circulares y respuestas** (`circulars.py`; T-083), después de las filas técnicas y antes de
las consecuencias, si el procedimiento tiene alguna: por fecha, cada tramo cambia, aclara o
suprime una cita de un requisito, o agrega un requisito (origen `circular`). Los documentos
usados quedan en `run.counts["circulars"]` y en el hecho de auditoría; los efectos, en
`tenders_requirement_source`. Un requisito formal o económico suprimido queda `quitado`, visible
y con la cita de la circular. Los requisitos nuevos se numeran después de las filas técnicas y
también reciben consecuencias.

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
    Consequence,
    ConsequenceOrigin,
    Disposition,
    DispositionOutcome,
    DispositionSource,
    MatrixVersion,
    PassName,
    PendingItem,
    PendingReason,
    Reading,
    Requirement,
    RequirementClass,
    RequirementOrigin,
    RequirementQuote,
    RequirementSource,
    RequirementState,
    SegmentType,
    SourceEffect,
    VersionStatus,
)
from evaluon.tenders.proposal import (
    circulars,
    completeness,
    consequences,
    extraction,
    quotes,
    technical,
)
from evaluon.tenders.segmenting import RULES_VERSION
from evaluon.tenders.services.procedures import _snapshot, regime_for

# Pasadas del proceso único, en orden (plan 003, "Pasadas"; REQ-030 enmendado).
PASSES = ("reglas", "extraccion", "completitud", "filas_tecnicas", "consecuencias")

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
    # Condiciones dichas como efecto (T-093); sin tildes también valen los plurales.
    "se considerará",
    "se entenderá",
    "quedará",
)

ANOMALY_DISCARDED_IN_ITEM = "descartado_en_renglon"
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
    """La disposición de un tramo según lo que el modelo devolvió (`extraction.Outcome`).
    Un descartado con marcadores de obligación queda descartado: la completitud lo revisa."""
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


def _parameters(run, with_circulars=False):
    passes = list(PASSES)
    if with_circulars:
        passes.insert(passes.index("consecuencias"), "circulares")
    return {
        "process": settings.MATRIX_PROCESS,
        "passes": passes,
        "circular_candidates": settings.MATRIX_CIRCULAR_CANDIDATES,
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


def _begin(run, with_circulars=False):
    """Fija fecha, régimen, versión de la normativa, modelos, parámetros e instrucciones
    de la propuesta, en una misma instantánea (P6, P8)."""
    run.authorization_date = run.procedure.authorization_date
    with _snapshot():
        run.corpus_version = audit.current_corpus_version()
        run.regime = regime_for(run.authorization_date)
    run.models = _models()
    run.parameters = _parameters(run, with_circulars)
    run.process = settings.MATRIX_PROCESS
    names = (["extraccion", "completitud"]
             + (["circulares"] if with_circulars else []) + ["consecuencias"])
    run.prompt_versions = {name: settings.MATRIX_PROMPT_VERSIONS[name] for name in names}
    run.save(update_fields=["process", "authorization_date", "corpus_version", "regime",
                            "models",
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
    """Corre las pasadas del proceso único y deja la versión borrador. Devuelve la
    `MatrixVersion`. Ver el módulo."""
    clock = time.monotonic()
    timings = {}
    anomalies = []
    workers = []
    try:
        # 1. Disposición por regla.
        started = time.monotonic()
        loaded = load(run)
        dated = circulars.load(run, len(loaded.units))
        _begin(run, with_circulars=bool(dated.documents))
        for document in dated.missing:
            anomalies.append({"type": circulars.ANOMALY_NO_READING,
                              "document": document.pk, "title": document.title})
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
        workers.append(extractor)
        result = extractor.extract(to_model)
        timings["extraccion"] = round(time.monotonic() - started, 3)
        anomalies.extend(result.anomalies)
        outcomes = result.outcomes
        requests = {PassName.EXTRACCION.value: result.stats["requests"]}
        stats = [result.stats]

        # 3. Disposición según el modelo.
        by_pk = {unit.segment.pk: unit for unit in loaded.units}
        for pk, outcome in outcomes.items():
            decisions[pk] = model_decision(by_pk[pk], outcome, anomalies)

        # 3 bis. Completitud.
        started = time.monotonic()
        completer = completeness.Completer(run)
        workers.append(completer)
        candidates = completeness_candidates(loaded, decisions)
        if candidates:
            completion = completer.complete(candidates)
            apply_completeness(decisions, completion)
            anomalies.extend(completion.anomalies)
        completion_stats = {key: completer.stats[key] for key in
                            ("segments", "added", "split", "invalid")}
        requests[PassName.COMPLETITUD.value] = completer.stats["requests"]
        timings["completitud"] = round(time.monotonic() - started, 3)

        keep_tables_pending(loaded, decisions)

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

        # 4 bis. Circulares y respuestas a consultas, por fecha.
        body = [(unit, found, _found_text(unit.segment, found))
                for unit, found in _body(loaded, decisions)]
        circular_result = None
        if dated.documents:
            started = time.monotonic()
            processor = circulars.Processor(run)
            workers.append(processor)
            candidates = circulars.build_candidates(loaded, body, rows)
            circular_result = processor.process(dated, candidates)
            anomalies.extend(circular_result.anomalies)
            requests[PassName.CIRCULARES.value] = circular_result.stats["requests"]
            timings["circulares"] = round(time.monotonic() - started, 3)

        # 5. Consecuencias de cada requisito, numerados como van a quedar en la versión.
        started = time.monotonic()
        subjects = consequences.build_subjects(loaded, body, rows)
        if circular_result is not None:
            circulars.apply_to_subjects(subjects, candidates)
            subjects += circular_result.subjects(
                len(subjects) + 1, {u.segment.pk: u for d in dated.documents
                                    for u in d.units})
        suggester = consequences.Suggester(run, loaded)
        workers.append(suggester)
        suggestions = suggester.suggest(subjects)
        anomalies.extend(suggestions.anomalies)
        requests[PassName.CONSECUENCIAS.value] = suggestions.stats["requests"]
        timings["consecuencias"] = round(time.monotonic() - started, 3)

        # Guardado: todo o nada.
        started = time.monotonic()
        with transaction.atomic():
            version = _save(run, loaded, decisions, rows, stats, requests, completion_stats,
                            anomalies, timings, clock, user, channel, started, suggestions,
                            dated, circular_result)
    except Exception as error:
        _record_failure(run, user, channel, error, workers, timings, clock)
        raise
    return version


def completeness_candidates(loaded, decisions):
    """Los tramos para la completitud, en el orden del pliego: los que el modelo dejó con
    requisitos, y los que descartó teniendo marcadores de obligación. Solo pasan por acá
    tramos que ya pasaron por el modelo, así que nunca los de una sección técnica."""
    candidates = []
    for unit in loaded.units:
        decision = decisions[unit.segment.pk]
        if decision.source != DispositionSource.MODELO.value:
            continue
        if decision.outcome == DispositionOutcome.REQUISITOS.value and decision.found:
            candidates.append(completeness.Candidate(unit, list(decision.found)))
        elif (decision.outcome == DispositionOutcome.DESCARTADO.value
              and has_obligation_markers(unit.segment.text)):
            candidates.append(completeness.Candidate(unit, []))
    return candidates


def keep_tables_pending(loaded, decisions):
    """Un tramo `tabla` nunca queda descartado (T-093): si el modelo no propuso filas ni
    marca técnica, queda pendiente de revisión con el motivo `tabla`. Se aplica después
    de la completitud, que todavía puede encontrarle filas."""
    for unit in loaded.units:
        decision = decisions[unit.segment.pk]
        if (unit.segment.segment_type == SegmentType.TABLA
                and decision.outcome == DispositionOutcome.DESCARTADO.value):
            decisions[unit.segment.pk] = Decision(
                DispositionOutcome.PENDIENTE.value,
                pending_reason=PendingReason.TABLA.value,
                source=decision.source, step=decision.step)


def apply_completeness(decisions, completion):
    """Pasa a las disposiciones lo que dijo la completitud. Un descartado con marcadores
    en que no se encontró nada queda descartado; si la completitud no dio resultado, queda
    pendiente por los marcadores."""
    for pk, result in completion.results.items():
        decision = decisions[pk]
        discarded = decision.outcome == DispositionOutcome.DESCARTADO.value
        if not result.valid:
            if discarded:
                decisions[pk] = Decision(
                    DispositionOutcome.PENDIENTE.value,
                    pending_reason=PendingReason.MARCADORES.value,
                    source=DispositionSource.MODELO.value, step=decision.step)
            continue
        if result.found:
            decisions[pk] = Decision(
                DispositionOutcome.REQUISITOS.value, found=result.found,
                marks=list(decision.marks), source=DispositionSource.MODELO.value,
                step=result.step if discarded else decision.step)


def _requirement_sort_key(item):
    unit, found = item
    return (unit.position, found.span[0])


def _body(loaded, decisions):
    """Los requisitos formales y económicos como `[(unidad, Found)]`, en el orden del
    pliego."""
    body = []
    for unit in loaded.units:
        for found in decisions[unit.segment.pk].found:
            body.append((unit, found))
    body.sort(key=_requirement_sort_key)
    return body


def _found_text(segment, found):
    """El texto literal de la cita de un requisito: el fragmento, o el tramo entero."""
    if found.flag == quotes.WIDE:
        return segment.text
    return segment.text[found.span[0]:found.span[1]]


def _original_fields(source, circular_readings):
    """Dónde está el texto que la fuente reemplaza cuando no es la cita (anexo sin
    requisitos; T-113). La base no garantiza que el tramo sea de la lectura de las posiciones
    ni que sea del pliego: se comprueba acá, como toda cita."""
    original = getattr(source, "original", None)
    if original is None:
        return {}
    segment = original.segment
    reading = segment.reading
    if (reading.pk in circular_readings
            or not segment.char_start <= original.start < original.end <= len(reading.canonical_text)
            or original.start >= segment.char_end):
        raise RuntimeError(
            "El original de una fuente de circular no es un recorte de la lectura de un "
            f"documento del pliego ({segment.key} {original.start}:{original.end}): no se "
            "guardó la matriz.")
    return {"original_segment": segment, "original_char_start": original.start,
            "original_char_end": original.end}


def _save_circulars(version, dated, result, created, quote_of, by_class):
    """Crea las fuentes de las circulares (`tenders_requirement_source`), una por requisito
    alcanzado, y los requisitos que agregan. Un formal o económico que una circular suprime
    queda `quitado`, visible y con su cita."""
    circular_readings = {d.reading.pk for d in dated.documents}
    for source in result.sources:
        reading = dated.reading_of[source.segment.pk]
        _check_quote(reading, source.start, source.end, source.text)
        for target in source.candidate.targets:
            requirement = created[target.number]
            RequirementSource.objects.create(
                requirement=requirement, quote=quote_of[(target.number, target.order)],
                effect=source.effect, segment=source.segment, char_start=source.start,
                char_end=source.end, text=source.text, issued_on=source.issued_on,
                step=source.step, **_original_fields(source, circular_readings),
            )
            if (source.effect == SourceEffect.SUPRIME.value
                    and target.category != RequirementClass.TECNICO.value):
                requirement.state = RequirementState.QUITADO
                requirement.save(update_fields=["state"])
            elif (source.effect == SourceEffect.MODIFICA.value
                    and target.category != RequirementClass.TECNICO.value
                    and requirement.state == RequirementState.QUITADO):
                # Una circular posterior que lo modifica lo vuelve a poner vigente.
                requirement.state = RequirementState.PROPUESTO
                requirement.save(update_fields=["state"])
    for new in result.new_requirements:
        reading = dated.reading_of[new.segment.pk]
        _check_quote(reading, new.start, new.end, new.text)
        flag = quotes.WIDE if new.wide else ""
        record = _quote_record(new.segment, new.start, new.end, new.text, flag=flag)
        requirement = created[new.number] = Requirement.objects.create(
            version=version, number=new.number,
            category=new.category, items=list(new.segment.items),
            origin=RequirementOrigin.CIRCULAR, state=RequirementState.PROPUESTO,
            proposed={"category": new.category, "items": list(new.segment.items),
                      "quotes": [record]},
            step=new.step, passes=[],
        )
        RequirementQuote.objects.create(
            requirement=requirement, order=1, segment=new.segment, char_start=new.start,
            char_end=new.end, text=new.text, scope="", quote_flag=flag,
        )
        by_class[new.category] += 1


def _save(run, loaded, decisions, rows, stats, requests, completion_stats, anomalies,
          timings, clock, user, channel, started, suggestions, dated=None,
          circular_result=None):
    """Crea la versión borrador y todo lo que cuelga de ella, y deja el hecho
    `matrix_proposal`. Corre dentro de una transacción."""
    procedure = run.procedure
    number = (procedure.matrix_versions.aggregate(last=Max("number"))["last"] or 0) + 1
    version = MatrixVersion.objects.create(
        procedure=procedure, number=number, status=VersionStatus.DRAFT, process=run.process,
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
    if circular_result is not None:
        Disposition.objects.bulk_create(
            Disposition(run=run, segment_id=pk, outcome=verdict.outcome,
                        discard_reason=verdict.discard_reason, source=verdict.source,
                        step=verdict.step)
            for pk, verdict in circular_result.verdicts.items()
        )

    # Requisitos formales y económicos, en el orden del pliego.
    body = _body(loaded, decisions)
    created, quote_of = {}, {}
    counter = 0
    by_class = Counter()
    for unit, found in body:
        counter += 1
        segment = unit.segment
        reading = loaded.reading_of[segment.pk]
        start, end = _wide_or_span(segment, found)
        text = _found_text(segment, found)
        _check_quote(reading, start, end, text)
        record = _quote_record(segment, start, end, text, flag=found.flag)
        requirement = created[counter] = Requirement.objects.create(
            version=version, number=counter, category=found.category,
            items=list(segment.items), origin=RequirementOrigin.PROPUESTO,
            state=RequirementState.PROPUESTO,
            proposed={"category": found.category, "items": list(segment.items),
                      "quotes": [record]},
            step=found.step, passes=completeness.passes_of(found),
        )
        quote_of[(counter, 1)] = RequirementQuote.objects.create(
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
        requirement = created[counter] = Requirement.objects.create(
            version=version, number=counter, category=RequirementClass.TECNICO.value,
            items=items, origin=RequirementOrigin.PROPUESTO,
            state=RequirementState.PROPUESTO,
            proposed={"category": RequirementClass.TECNICO.value, "items": items,
                      "quotes": [_quote_record(segment, segment.char_start,
                                               segment.char_end, segment.text, scope)
                                 for _, segment, scope in records]},
            step=None, passes=[],
        )
        for made in RequirementQuote.objects.bulk_create(
            RequirementQuote(requirement=requirement, order=order, segment=segment,
                             char_start=segment.char_start, char_end=segment.char_end,
                             text=segment.text, scope=scope, quote_flag="")
            for order, segment, scope in records
        ):
            quote_of[(counter, made.order)] = made
        by_class[RequirementClass.TECNICO.value] += 1
        technical_rows.append({
            "item": row.number,
            "quotes": len(records),
            "own": sum(1 for _, _, scope in records if scope == "propia"),
            "general": sum(1 for _, _, scope in records if scope == "general"),
        })

    # Circulares y respuestas: lo que cambian, aclaran o suprimen, y lo que agregan.
    if circular_result is not None:
        _save_circulars(version, dated, circular_result, created, quote_of, by_class)

    # Consecuencias sugeridas: las de cada requisito, o "no determinada".
    Consequence.objects.bulk_create(
        Consequence(requirement=created[number], consequence_type=option.consequence_type,
                    grounds=option.grounds, origin=ConsequenceOrigin.SISTEMA.value,
                    step=option.step)
        for number, options in sorted(suggestions.options.items())
        for option in options
    )

    # Pendientes: uno por tramo.
    pending = {}
    for unit in loaded.units:
        reason = _pending_reason(unit.segment, decisions[unit.segment.pk])
        if reason:
            pending[unit.segment.pk] = reason
    if circular_result is not None:
        circular_units = {u.segment.pk: u for d in dated.documents for u in d.units}
        for pk, verdict in circular_result.verdicts.items():
            reason = _pending_reason(circular_units[pk].segment, verdict)
            if reason:
                pending[pk] = reason
        by_pk = {**by_pk, **circular_units}
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
        "model_requests": sum(requests.values()),
        "model_requests_by_pass": requests,
        "segments_retried": sum(s["segments_retried"] for s in stats),
        "quotes_retried": sum(s["quotes_retried"] for s in stats),
        "split_batches": sum(s["split_batches"] for s in stats),
        "wide_quotes": wide,
    }
    counts["consequences"] = {key: suggestions.stats[key] for key in (
        "requirements", "options", "undetermined", "invalid", "dropped_options",
        "retried", "split_batches", "norm_units", "requests")}
    if completion_stats is not None:
        counts["completeness"] = completion_stats
    if circular_result is not None:
        counts["circulars"] = {
            "documents": circulars.circular_record(dated),
            "not_read": circulars.missing_record(dated),
            "dispositions": dict(Counter(v.outcome
                                         for v in circular_result.verdicts.values())),
            **{key: circular_result.stats[key] for key in (
                "segments", "requests", "retried", "effects", "new_requirements",
                "no_effect", "pending", "wide_quotes", "dropped_effects")},
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
            "process": run.process,
            "run_channel": run.channel,
            "authorization_date": run.authorization_date.isoformat(),
            "regime": run.regime,
            "corpus_version": run.corpus_version,
            "documents": run.documents,
            "circulars": counts.get("circulars", {}).get("documents", []),
            "models": run.models,
            "parameters": run.parameters,
            "prompt_versions": run.prompt_versions,
            "counts": counts,
            "timings": timings,
            "anomalies": dict(Counter(a["type"] for a in anomalies)),
        },
    )
    return version


def _record_failure(run, user, channel, error, workers, timings, clock):
    """Deja el hecho `matrix_proposal` fallido. Lo ya guardado en `tenders_run_step`
    queda."""
    timings = {**timings, "total": round(time.monotonic() - clock, 3)}
    audit.record(
        EventType.MATRIX_PROPOSAL, outcome=Outcome.FAILED, channel=channel, user=user,
        detail={
            "procedure": run.procedure_id,
            "run": run.pk,
            "job": run.job_id,
            "process": run.process,
            "run_channel": run.channel,
            "error": f"{type(error).__name__}: {error}",
            "model_requests_saved": sum(len(worker.steps) for worker in workers),
            "timings": timings,
        },
    )
