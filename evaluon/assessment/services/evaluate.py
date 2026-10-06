"""Pedir y armar la evaluación de las ofertas de un procedimiento (REQ-052 a REQ-055, REQ-059,
REQ-060; plan 004, "Flujo de IA", "Roles" y "Registro de auditoría"; ADR-0037 a ADR-0039;
T-150).

- `request_evaluation`: pide la evaluación de una o varias ofertas (todas por omisión) y de uno
  o varios requisitos (todos por omisión). Lo hacen el operador y el evaluador. Encola un solo
  pedido `evaluate_offers` y deja el hecho `eval_request`. Se rechaza, sin encolar nada y con el
  hecho en resultado `rejected` y su motivo, si no hay matriz validada (`no_matrix`), si el
  procedimiento no tiene ofertas (`no_offers`), si una oferta pedida no tiene documentos
  (`no_documents`) o algún documento está en lectura (`reading_in_progress`) o falló
  (`reading_failed`), si un requisito o una oferta no son del procedimiento (`invalid_request`)
  o si ya hay un pedido de evaluación en espera o en curso (`request_in_progress`).
- `run_evaluate_offers`: el manejador del pedido (lo registra `tenders.jobs`). Evalúa las ofertas
  de a una; cada una se guarda entera, en una transacción, al terminar: un pedido cortado
  conserva las ofertas ya evaluadas y no deja ninguna a medias.
- `evaluate_offer`: la evaluación de una oferta. Lee completos sus documentos por grupos
  (`documents.py`, ADR-0037); por cada requisito y grupo, un pedido al modelo; el sistema ubica
  cada cita en el texto canónico (`citations.py`), une los grupos con reglas fijas y contrasta
  antes de concluir "cumple" o "no cumple" (`combine.py`, ADR-0038). Sin cita ubicada no hay
  conclusión (P3). Cada pedido al modelo queda en `assessment_step` y el armado deja el hecho
  `eval_build` (P6).
- `current_result`: **la función única** del resultado vigente de un par: el de la evaluación
  más reciente de esa oferta (ADR-0039).
- `pair_page`: la página de un par, en solo lectura.

El rol se comprueba fuera de toda transacción. Todo corre en el equipo, sin servicios externos
(P4).
"""

import time
from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.ai import generation
from evaluon.assessment import citations as citing
from evaluon.assessment import combine, documents, grounds, prompting
from evaluon.assessment.models import (
    Answer,
    Cause,
    Citation,
    CitationKind,
    Decision,
    Question,
    Request,
    Result,
    Run,
    Step,
)
from evaluon.assessment.models import Channel as RunChannel
from evaluon.assessment.models import Purpose
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.offers.models import Offer
from evaluon.offers.services import offers as offers_service
from evaluon.offers.services import sheets
from evaluon.tenders import jobs
from evaluon.tenders.models import (
    Job,
    JobKind,
    JobStatus,
    MatrixVersion,
    Requirement,
    RequirementClass,
)
from evaluon.tenders.services.validation import latest_validated

REQUEST_OPERATION = "evaluon.assessment.services.evaluate.request_evaluation"
PAGE_OPERATION = "evaluon.assessment.services.evaluate.pair_page"

# Anomalías del registro.
ANOMALY_NO_QUOTE = "requisito_sin_cita"
ANOMALY_NO_CLAUSE = "no_cumple_sin_clausula"
ANOMALY_REWRITE = "reescritura_descartada"
ANOMALY_UNKNOWN_ALIAS = "alias_inexistente"
ANOMALY_CONTRAST_INVALID = "contraste_invalido"
ANOMALY_UNREAD_GROUPS = "grupos_sin_leer"


class EvaluationRefused(ValueError):
    """No se pidió la evaluación. `reason` es el motivo que queda en el registro."""

    def __init__(self, message, reason):
        super().__init__(message)
        self.reason = reason


class EvaluationFailed(RuntimeError):
    """El pedido terminó, pero alguna oferta no se pudo evaluar. Las que sí, quedaron."""


@dataclass(frozen=True)
class Requested:
    """Lo que devuelve `request_evaluation`: el pedido, el pedido de la cola y el hecho."""

    request: Request
    job: Job
    event: object


# --- Resultado vigente -------------------------------------------------------------------------


def current_result(offer, requirement):
    """El resultado vigente del par: el de la evaluación más reciente de la oferta que incluyó
    ese requisito, o `None` si nunca se evaluó. Es la única definición de "vigente" (ADR-0039):
    la pantalla, la matriz y la medición la usan."""
    return (Result.objects.filter(offer=offer, requirement=requirement)
            .select_related("run").order_by("-run__number", "-pk").first())


# --- Pedido ------------------------------------------------------------------------------------


def _requested_offers(procedure, offers):
    if offers is None:
        return list(procedure.offers.order_by("number"))
    ids = [o.pk if isinstance(o, Offer) else int(o) for o in offers]
    found = {o.pk: o for o in procedure.offers.filter(pk__in=ids)}
    unknown = [i for i in ids if i not in found]
    if unknown:
        raise EvaluationRefused("Hay ofertas pedidas que no son de este procedimiento.",
                                "invalid_request")
    return [found[i] for i in dict.fromkeys(ids)]


def _requested_requirements(version, requirements):
    firm = {r.pk for r in sheets.firm_requirements(version)}
    if requirements is None:
        return None
    ids = [r.pk if isinstance(r, Requirement) else int(r) for r in requirements]
    if not ids or any(i not in firm for i in ids):
        raise EvaluationRefused("Hay requisitos pedidos que no son de la matriz validada.",
                                "invalid_request")
    return list(dict.fromkeys(ids))


def _check_request(procedure, offers, requirements):
    """Lanza `EvaluationRefused` si no se puede pedir; si no, devuelve `(versión, ofertas,
    ids de requisitos o None)`."""
    version = latest_validated(procedure)
    if version is None:
        raise EvaluationRefused(
            "El procedimiento no tiene una matriz validada: la evaluación se arma solo contra "
            "una matriz validada.", "no_matrix")
    chosen = _requested_offers(procedure, offers)
    if not chosen:
        raise EvaluationRefused("El procedimiento no tiene ofertas cargadas.", "no_offers")
    requirement_ids = _requested_requirements(version, requirements)
    for offer in chosen:
        rows = [offers_service.document_row(d)
                for d in offer.documents.order_by("loaded_at", "id")]
        if not rows:
            raise EvaluationRefused(
                f"La oferta {offer.number} no tiene documentos cargados.", "no_documents")
        waiting = [r.document.title for r in rows
                   if r.state in (offers_service.STATE_QUEUED, offers_service.STATE_RUNNING)]
        if waiting:
            raise EvaluationRefused(
                f"En la oferta {offer.number} hay documentos que todavía se están leyendo: "
                + ", ".join(f"«{t}»" for t in waiting) + ". Espere a que terminen.",
                "reading_in_progress")
        failed = [r.document.title for r in rows
                  if r.state == offers_service.STATE_FAILED or r.reading is None]
        if failed:
            raise EvaluationRefused(
                f"En la oferta {offer.number} no se pudo leer: "
                + ", ".join(f"«{t}»" for t in failed) + ".", "reading_failed")
    if Job.objects.filter(kind=JobKind.EVALUATE_OFFERS, procedure=procedure,
                          status__in=[JobStatus.QUEUED, JobStatus.RUNNING]).exists():
        raise EvaluationRefused(
            "Ya hay un pedido de evaluación de este procedimiento en espera o en curso.",
            "request_in_progress")
    return version, chosen, requirement_ids


def request_evaluation(user, procedure, offers=None, requirements=None, cause=Cause.MATRIZ,
                       *, decision=None, answer=None, channel=Channel.SCREEN):
    """Pide la evaluación de `offers` (todas por omisión) y `requirements` (todos por
    omisión) de `procedure`. Ver el módulo. Lanza `RoleRejected` sin rol de la Comisión y
    `EvaluationRefused` si no se puede pedir."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=REQUEST_OPERATION,
                            channel=channel)
    detail = {"procedure": procedure.pk, "cause": str(cause)}
    try:
        version, chosen, requirement_ids = _check_request(procedure, offers, requirements)
    except EvaluationRefused as error:
        audit.record(EventType.EVAL_REQUEST, outcome=Outcome.REJECTED, channel=channel,
                     user=user, detail={**detail, "reason": error.reason,
                                        "message": str(error)})
        raise
    with transaction.atomic():
        job = jobs.enqueue(JobKind.EVALUATE_OFFERS, procedure=procedure, requested_by=user)
        request = Request.objects.create(
            procedure=procedure, matrix_version=version, offers=[o.pk for o in chosen],
            requirements=requirement_ids, cause=cause, decision=decision, answer=answer,
            requested_by=user, job=job)
        # Las tablas de la evaluación son de solo inserción: el pedido nace con su `job` y el
        # `job` (que sí admite el cambio) anota el pedido después.
        Job.objects.filter(pk=job.pk).update(target_id=request.pk)
        job.target_id = request.pk
        event = audit.record(
            EventType.EVAL_REQUEST, outcome=Outcome.OK, channel=channel, user=user,
            detail={**detail, "request": request.pk, "job": job.pk,
                    "matrix_version": version.pk, "matrix_version_number": version.number,
                    "offers": request.offers, "requirements": request.requirements,
                    "decision": decision.pk if decision else None,
                    "answer": answer.pk if answer else None})
    return Requested(request=request, job=job, event=event)


# --- Armado ------------------------------------------------------------------------------------


def _models():
    return {
        "generation_batch": {
            "model": settings.GENERATION_MODEL, "file": settings.GENERATION_MODEL_FILE,
            "sha256": settings.GENERATION_MODEL_SHA256,
            "engine_build": settings.GENERATION_ENGINE_BUILD,
            "context_tokens": settings.GENERATION_BATCH_CONTEXT_TOKENS},
        "embeddings": {
            "model": settings.EMBEDDINGS_MODEL, "file": settings.EMBEDDINGS_MODEL_FILE,
            "sha256": settings.EMBEDDINGS_MODEL_SHA256},
        "reranker": {
            "model": settings.RERANKER_MODEL, "file": settings.RERANKER_MODEL_FILE,
            "sha256": settings.RERANKER_MODEL_SHA256},
    }


def _parameters():
    return {
        "group_tokens": settings.ASSESSMENT_GROUP_TOKENS,
        "max_groups": settings.ASSESSMENT_MAX_GROUPS,
        "max_output_tokens": settings.ASSESSMENT_MAX_OUTPUT_TOKENS,
        "max_citations": settings.ASSESSMENT_MAX_CITATIONS,
        "citation_max_chars": settings.ASSESSMENT_CITATION_MAX_CHARS,
        "request_timeout_seconds": settings.ASSESSMENT_REQUEST_TIMEOUT_SECONDS,
        "norm_units_max": settings.ASSESSMENT_NORM_UNITS_MAX,
        "answers_max": settings.ASSESSMENT_ANSWERS_MAX,
        "temperature": settings.GENERATION_TEMPERATURE,
        "seed": settings.GENERATION_SEED,
        "thinking": settings.GENERATION_THINKING,
        "generation_batch_url": settings.GENERATION_BATCH_URL,
        "passage_max_chars": settings.OFFERS_PASSAGE_MAX_CHARS,
        "passage_min_chars": settings.OFFERS_PASSAGE_MIN_CHARS,
    }


@dataclass
class StepData:
    """Un pedido al modelo, todavía sin guardar."""

    purpose: str
    requirement: object | None
    group_index: int | None = None
    documents: list = field(default_factory=list)
    request: dict | None = None
    raw_output: str = ""
    parsed: dict | None = None
    anomalies: list = field(default_factory=list)
    retry_of: int | None = None  # posición del pedido anterior en la lista de la evaluación
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    timings: dict = field(default_factory=dict)


@dataclass
class PairData:
    """Un par (oferta y requisito) en armado."""

    requirement: Requirement
    text: object
    answers: list = field(default_factory=list)
    norms: list = field(default_factory=list)
    groups: list = field(default_factory=list)
    combined: object = None
    anomalies: list = field(default_factory=list)
    seconds: float = 0.0
    contrast: tuple | None = None
    # El resultado vigente del par antes de esta evaluación (para el recorrido).
    previous: object = None


class Context:
    """Lo que comparten los pares de una oferta mientras se arma su evaluación."""

    def __init__(self, offer, offer_text, rewrites, clock):
        self.offer = offer
        self.offer_text = offer_text
        self.rewrites = rewrites
        self.clock = clock
        self.finder = citing.PageFinder()
        self.steps = []
        self.single_plan = None
        self.rewrites_reused = 0

    def add(self, step):
        self.steps.append(step)
        return len(self.steps) - 1


def _generate(messages, schema, step, ctx):
    """El pedido al motor de lotes; anota en `step` lo que se envió y lo que volvió."""
    started = ctx.clock()
    result = generation.generate(
        messages, schema, max_tokens=settings.ASSESSMENT_MAX_OUTPUT_TOKENS,
        base_url=settings.GENERATION_BATCH_URL,
        timeout=settings.ASSESSMENT_REQUEST_TIMEOUT_SECONDS)
    step.timings["generation_seconds"] = round(ctx.clock() - started, 3)
    step.request = result.request
    step.raw_output = result.content
    step.prompt_tokens = result.prompt_tokens
    step.completion_tokens = result.completion_tokens
    return result


def _plan_for(ctx, pair):
    """Los grupos con que se lee la oferta para este requisito."""
    offer_text = ctx.offer_text
    if offer_text.fits:
        if ctx.single_plan is None:
            ctx.single_plan = documents.plan_groups(offer_text)
        return ctx.single_plan, None
    requirement = pair.requirement
    item_row = sheets.is_item_row(requirement)
    text = pair.text.text
    rewrite = None
    if text and not item_row:
        rewrite = ctx.rewrites.get(requirement.pk)
        if rewrite is None:
            rewrite = sheets.rewrite_requirement(text, ctx.clock)
            ctx.rewrites[requirement.pk] = rewrite
            step = StepData(Purpose.REESCRITURA, None, request=rewrite["request"],
                            raw_output=rewrite["raw_output"],
                            parsed={"requirement": requirement.pk, "query": rewrite["query"],
                                    "prompt_version": rewrite["prompt_version"]},
                            timings={"generation_seconds": rewrite["seconds"]})
            if rewrite.get("anomaly"):
                step.anomalies.append({"type": ANOMALY_REWRITE, "reason": rewrite["anomaly"]})
                pair.anomalies.append({"type": ANOMALY_REWRITE, "reason": rewrite["anomaly"]})
            ctx.add(step)
        else:
            ctx.rewrites_reused += 1
    query = sheets.retrieval_query(requirement, text)
    scores, found = documents.relevance(
        offer_text, query, rewrite["query"] if rewrite else "")
    plan = documents.plan_groups(offer_text, scores)
    return plan, {"relevance": {str(k): round(v, 6) for k, v in scores.items()},
                  "query": found.query, "rewrite": found.rewrite}


def _group_result(ctx, pair, group_index, pieces, relevance_note):
    """Pide un grupo (con un reintento si hace falta) y devuelve su `GroupResult`."""
    docs_text, doc_map = prompting.render_documents(pieces)
    answers_text, answer_map = prompting.render_answers(pair.answers)
    norms_text, norm_map = prompting.render_norms(pair.norms)
    support_map = {**answer_map, **norm_map}
    schema = prompting.evaluation_schema(list(doc_map), list(support_map))
    system = prompting.load_prompt("evaluacion")
    requirement_block = pair.text.render()
    pieces_record = [p.record() for p in pieces]
    if relevance_note:
        pieces_record.append(relevance_note)

    correction, previous = "", None
    for attempt in range(2):
        step = StepData(Purpose.GRUPO, pair.requirement, group_index=group_index,
                        documents=pieces_record, retry_of=previous)
        position = ctx.add(step)
        messages = prompting.build_evaluation_messages(
            system, docs_text, answers_text, norms_text, requirement_block, correction)
        result = _generate(messages, schema, step, ctx)
        problem, evaluation, located = None, None, []
        try:
            evaluation = prompting.parse_evaluation(
                result.content, list(doc_map), list(support_map))
        except prompting.InvalidOutput as error:
            step.anomalies.append({"type": error.kind, "message": str(error)})
            problem = prompting.ANOMALY_INVALID_OUTPUT
        else:
            used = {c.span for c in located}
            for alias, quote in evaluation.citations:
                piece = doc_map.get(alias)
                if piece is None:
                    step.anomalies.append({"type": ANOMALY_UNKNOWN_ALIAS, "alias": alias})
                    continue
                found = citing.locate_quote(piece.doc, quote, ctx.finder, used,
                                            step.anomalies)
                if found is not None:
                    located.append(found)
                    used.add(found.span)
            step.parsed = {**evaluation.as_json(),
                           "citas_ubicadas": [{"documento": c.document.pk, "pagina": c.page,
                                               "inicio": c.char_start, "fin": c.char_end}
                                              for c in located]}
            if evaluation.result in (prompting.CUMPLE, prompting.NO_CUMPLE) and not located:
                step.anomalies.append({"type": prompting.ANOMALY_NO_CITATION})
                problem = prompting.ANOMALY_NO_CITATION
        pair.anomalies.extend({**a, "requirement": pair.requirement.number, "step": position}
                              for a in step.anomalies)
        if problem is None:
            break
        if attempt == 0:
            correction = prompting.correction_for(problem)
            previous = position

    if problem == prompting.ANOMALY_INVALID_OUTPUT:
        return combine.GroupResult(group_index, prompting.NO_DETERMINADO, doubt=combine.DOUBT,
                                   explanation="El modelo no devolvió una salida válida.")
    supports = [support_map[a] for a in evaluation.supports]
    if problem == prompting.ANOMALY_NO_CITATION:
        return combine.GroupResult(
            group_index, prompting.NO_DETERMINADO, doubt=combine.NO_CITATION,
            exigence=evaluation.exigence, supports=supports,
            explanation=evaluation.explanation, question=evaluation.question,
            external=evaluation.external)
    if (evaluation.result == prompting.NO_CUMPLE
            and pair.requirement.category == RequirementClass.TECNICO
            and not combine.clause_supported(evaluation.clause, pair.text.text)):
        pair.anomalies.append({"type": ANOMALY_NO_CLAUSE, "requirement": pair.requirement.number,
                               "group": group_index})
        return combine.GroupResult(
            group_index, prompting.NO_DETERMINADO, doubt=combine.NO_DATA,
            exigence=evaluation.exigence, citations=located, supports=supports,
            explanation=f"{evaluation.explanation} {combine.NO_CLAUSE_NOTE}".strip(),
            question=evaluation.question, external=evaluation.external)
    keep = [] if evaluation.result == prompting.NO_CONSTA else located
    return combine.GroupResult(
        group_index, evaluation.result,
        doubt=combine.DOUBT if evaluation.result == prompting.NO_DETERMINADO else "",
        exigence=evaluation.exigence, citations=keep, supports=supports,
        explanation=evaluation.explanation, question=evaluation.question,
        external=evaluation.external)


def _read_pair(ctx, pair):
    """Lee los grupos que le tocan al requisito y deja `pair.combined` sin el contraste."""
    started = ctx.clock()
    offer_text = ctx.offer_text
    if not pair.text.quotes:
        pair.anomalies.append({"type": ANOMALY_NO_QUOTE, "requirement": pair.requirement.number})
        pair.combined = combine.Combined(
            outcome=combine.OUT_NO_DETERMINADO, doubt=combine.DOUBT,
            explanation="El requisito no tiene texto citado del pliego: no se puede evaluar.",
            unread_warning=offer_text.has_unread)
        return
    plan, note = _plan_for(ctx, pair)
    if plan.unread_groups:
        pair.anomalies.append({"type": ANOMALY_UNREAD_GROUPS,
                               "requirement": pair.requirement.number,
                               "groups": plan.unread_groups})
    for index, pieces in enumerate(plan.groups):
        pair.groups.append(_group_result(ctx, pair, index, pieces, note if index == 0 else None))
    pair.combined = combine.combine(
        pair.groups, unread=offer_text.unread, without_reading=offer_text.without_reading,
        unread_groups=plan.unread_groups)
    pair.seconds = ctx.clock() - started


def _supports_text(combined):
    """Los fundamentos que el contraste recibe: normas y respuestas que se usaron."""
    lines = []
    for support in combined.supports:
        if isinstance(support, Answer):
            lines.append(f"- Respuesta de la Comisión: {support.text}")
        else:
            lines.append(f"- {support.label}: {support.text}")
    return "Fundamentos:\n" + "\n".join(lines) if lines else ""


def _contrast_pair(ctx, pair):
    """El pedido corto del contraste de un "cumple" o un "no cumple"."""
    combined = pair.combined
    if combined is None or not combined.needs_contrast:
        return
    started = ctx.clock()
    system = prompting.load_prompt("contraste")
    cited = [(c.document.title, c.page, c.text) for c in combined.citations]
    conclusion = "cumple" if combined.outcome == combine.OUT_CUMPLE else "no cumple"
    answer, reason, previous, correction = None, "", None, ""
    for attempt in range(2):
        step = StepData(Purpose.CONTRASTE, pair.requirement, retry_of=previous)
        position = ctx.add(step)
        messages = prompting.build_contrast_messages(
            system, pair.text.render(), conclusion, cited, _supports_text(combined),
            correction)
        result = _generate(messages, prompting.CONTRAST_SCHEMA, step, ctx)
        try:
            answer, reason = prompting.parse_contrast(result.content)
        except prompting.InvalidOutput as error:
            step.anomalies.append({"type": error.kind, "message": str(error)})
            pair.anomalies.append({"type": ANOMALY_CONTRAST_INVALID,
                                   "requirement": pair.requirement.number, "step": position})
            previous = position
            correction = prompting.correction_for(prompting.ANOMALY_INVALID_OUTPUT)
            continue
        step.parsed = {"respuesta": answer, "motivo": reason}
        break
    if answer is None:
        answer, reason = "parcial", "el contraste no devolvió una salida válida"
    pair.contrast = (answer, reason)
    pair.combined = combine.apply_contrast(combined, answer, reason)
    pair.seconds += ctx.clock() - started


def _requirements(request, version):
    firm = sheets.firm_requirements(version)
    if request.requirements is None:
        return firm
    wanted = set(request.requirements)
    return [r for r in firm if r.pk in wanted]


def _counts(pairs, steps):
    by_outcome, by_doubt = {}, {}
    for pair in pairs:
        by_outcome[pair.combined.outcome] = by_outcome.get(pair.combined.outcome, 0) + 1
        if pair.combined.doubt:
            by_doubt[pair.combined.doubt] = by_doubt.get(pair.combined.doubt, 0) + 1
    return {"pairs": len(pairs), "by_outcome": by_outcome, "by_doubt": by_doubt,
            "model_requests": len(steps),
            "retries": sum(1 for s in steps if s.retry_of is not None),
            "contrasts": sum(1 for s in steps if s.purpose == Purpose.CONTRASTE),
            "questions": sum(1 for p in pairs if p.combined.question)}


def _open_question(offer, requirement):
    """La pregunta abierta (sin respuesta) del par, si hay."""
    return (Question.objects.filter(offer=offer, requirement=requirement, answers__isnull=True)
            .order_by("-pk").first())


def _save_pair(run, offer, pair, procedure):
    combined = pair.combined
    result = Result.objects.create(
        run=run, offer=offer, requirement=pair.requirement, outcome=combined.outcome,
        doubt=combined.doubt, exigence=combined.exigence, explanation=combined.explanation,
        unread_pages_warning=combined.unread_warning, previous=pair.previous)
    order = 0

    def cite(**fields):
        nonlocal order
        order += 1
        return Citation.objects.create(result=result, order=order, **fields)

    for found in combined.citations:
        cite(kind=CitationKind.OFERTA, document=found.document, reading=found.reading,
             page=found.page, char_start=found.char_start, char_end=found.char_end,
             text=found.text)
    for quote in pair.text.quotes:
        cite(kind=CitationKind.PLIEGO, requirement_quote=quote.quote, text=quote.text,
             original_text=quote.original)
    for support in combined.supports:
        if isinstance(support, Answer):
            cite(kind=CitationKind.RESPUESTA, answer=support)
        else:
            cite(kind=CitationKind.NORMA, norm_unit=support.unit, label=support.label[:300],
                 text=support.text)
    question = None
    if combined.question and _open_question(offer, pair.requirement) is None:
        question = Question.objects.create(
            procedure=procedure, requirement=pair.requirement, offer=offer, result=result,
            text=combined.question, reason=combined.doubt)
    return result, question


def evaluate_offer(request, offer, user, *, channel=RunChannel.SCREEN,
                   audit_channel=Channel.COMMAND, job=None, rewrites=None,
                   clock=time.monotonic):
    """Evalúa la oferta `offer` contra la matriz del pedido y guarda la evaluación entera en una
    transacción. Cualquier falla deja el hecho `eval_build` fallido y se vuelve a lanzar."""
    rewrites = rewrites if rewrites is not None else {}
    detail = {"procedure": offer.procedure_id, "offer": offer.pk, "request": request.pk,
              "job": job.pk if job else None,
              "matrix_version": request.matrix_version_id}
    try:
        version = request.matrix_version
        requirements = _requirements(request, version)
        started = clock()
        offer_text = documents.build_offer_text(offer)
        if not offer_text.pieces:
            raise EvaluationRefused("La oferta no tiene ningún documento leído.",
                                    "no_documents")
        ctx = Context(offer, offer_text, rewrites, clock)
        pairs = []
        for requirement in requirements:
            pair = PairData(requirement=requirement, text=grounds.requirement_text(requirement),
                            answers=grounds.applicable_answers(requirement, offer),
                            norms=grounds.norm_grounds(requirement))
            pair.previous = current_result(offer, requirement)
            pairs.append(pair)
        # Por cada requisito se piden seguidos todos los grupos; los contrastes, al final y
        # juntos, para no desalojar el prefijo de los documentos (plan, "Orden de los pedidos").
        for pair in pairs:
            _read_pair(ctx, pair)
        for pair in pairs:
            _contrast_pair(ctx, pair)
        anomalies = [a for pair in pairs for a in pair.anomalies]
        counts = {**_counts(pairs, ctx.steps), "rewrites_reused": ctx.rewrites_reused,
                  "documents": len(offer_text.documents),
                  "copies": sum(1 for d in offer_text.documents if d.copy_of is not None),
                  "pieces": len(offer_text.pieces), "tokens": offer_text.tokens,
                  "unread_pages": len(offer_text.unread),
                  "without_reading": len(offer_text.without_reading)}
        timings = {"total_seconds": round(clock() - started, 3), "pairs": len(pairs),
                   "model_requests": len(ctx.steps),
                   "pair_seconds": {str(p.requirement.number): round(p.seconds, 3)
                                    for p in pairs}}

        with transaction.atomic():
            Offer.objects.select_for_update().get(pk=offer.pk)
            last = Run.objects.filter(offer=offer).aggregate(last=Max("number"))["last"] or 0
            run = Run.objects.create(
                request=request, offer=offer, matrix_version=version, number=last + 1,
                channel=channel, documents=offer_text.record(),
                norms=grounds.norms_record(version), models_used=_models(),
                parameters=_parameters(),
                prompt_versions=dict(settings.ASSESSMENT_PROMPT_VERSIONS), counts=counts,
                timings=timings, anomalies=anomalies, built_at=timezone.now())
            saved = []
            for step in ctx.steps:
                saved.append(Step.objects.create(
                    run=run, offer=offer, requirement=step.requirement, purpose=step.purpose,
                    group_index=step.group_index, documents=step.documents,
                    request=step.request, raw_output=step.raw_output, parsed=step.parsed,
                    anomalies=step.anomalies,
                    retry_of=None if step.retry_of is None else saved[step.retry_of],
                    prompt_tokens=step.prompt_tokens,
                    completion_tokens=step.completion_tokens, timings=step.timings))
            questions = 0
            for pair in pairs:
                _, question = _save_pair(run, offer, pair, offer.procedure)
                questions += question is not None
            audit.record(
                EventType.EVAL_BUILD, outcome=Outcome.OK, channel=audit_channel, user=user,
                detail={**detail, "run": run.pk, "number": run.number, "documents": run.documents,
                        "norms": run.norms, "models": run.models_used,
                        "parameters": run.parameters, "prompt_versions": run.prompt_versions,
                        "counts": counts, "questions_created": questions,
                        "anomalies": anomalies, "timings": timings})
    except Exception as error:
        audit.record(EventType.EVAL_BUILD, outcome=Outcome.FAILED, channel=audit_channel,
                     user=user, detail={**detail, "error": f"{type(error).__name__}: {error}"})
        raise
    return run


def execute(request, user, *, channel=RunChannel.SCREEN, audit_channel=Channel.COMMAND,
            job=None, clock=time.monotonic):
    """Evalúa las ofertas del pedido, de a una. Cada una queda guardada al terminar; si alguna
    falla, las demás siguen y al final se lanza `EvaluationFailed` con lo que falló."""
    rewrites, runs, failures = {}, [], []
    for offer_id in request.offers:
        offer = Offer.objects.select_related("procedure").get(pk=offer_id)
        try:
            runs.append(evaluate_offer(request, offer, user, channel=channel,
                                       audit_channel=audit_channel, job=job,
                                       rewrites=rewrites, clock=clock))
        except Exception as error:  # noqa: BLE001 - ya quedó el hecho fallido de la oferta
            failures.append(f"oferta {offer.number}: {type(error).__name__}: {error}")
    if failures:
        raise EvaluationFailed("; ".join(failures))
    return runs


def run_evaluate_offers(job):
    """Manejador del pedido `evaluate_offers`: evalúa las ofertas del pedido que nombra
    `job.target_id`. No marca el estado del pedido: eso es de `jobs.run`."""
    request = Request.objects.select_related("procedure", "matrix_version").get(
        pk=job.target_id)
    if request.procedure_id != job.procedure_id:
        raise ValueError("El pedido de evaluación no es del procedimiento del pedido.")
    return execute(request, job.requested_by, channel=RunChannel.SCREEN,
                   audit_channel=Channel.SCREEN, job=job)


# --- Página de un par --------------------------------------------------------------------------


@dataclass
class PairPage:
    """La página de un par: el resultado vigente con sus fundamentos, en solo lectura."""

    offer: Offer
    requirement: Requirement
    result: Result
    run: Run
    offer_citations: list
    requirement_citations: list
    norm_citations: list
    answer_citations: list
    question: Question | None
    newer_version: MatrixVersion | None
    decisions: list


def pair_page(user, offer_id, requirement_id, *, channel=Channel.SCREEN):
    """El resultado vigente de un par para la pantalla. Lanza `RoleRejected` sin rol de la
    Comisión y `Result.DoesNotExist` si el par no se evaluó."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=PAGE_OPERATION,
                            channel=channel)
    result = (Result.objects.filter(offer_id=offer_id, requirement_id=requirement_id)
              .select_related("offer__procedure", "requirement", "run__matrix_version")
              .order_by("-run__number", "-pk").first())
    if result is None:
        raise Result.DoesNotExist("El par no se evaluó.")
    rows = list(result.citations.select_related(
        "document", "reading", "requirement_quote", "norm_unit", "answer__question",
        "answer__answered_by").order_by("order"))
    latest = latest_validated(result.offer.procedure)
    newer = latest if latest is not None and latest.number > result.run.matrix_version.number \
        else None
    return PairPage(
        offer=result.offer, requirement=result.requirement, result=result, run=result.run,
        offer_citations=[c for c in rows if c.kind == CitationKind.OFERTA],
        requirement_citations=[c for c in rows if c.kind == CitationKind.PLIEGO],
        norm_citations=[c for c in rows if c.kind == CitationKind.NORMA],
        answer_citations=[c for c in rows if c.kind == CitationKind.RESPUESTA],
        question=_open_question(result.offer, result.requirement), newer_version=newer,
        decisions=list(Decision.objects.filter(result=result).order_by("at", "pk")))
