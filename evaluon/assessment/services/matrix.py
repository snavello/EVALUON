"""La matriz de evaluación de un procedimiento: todas las ofertas a la vez (REQ-057, REQ-058,
REQ-059; plan 004, "Pantalla" y "Decisiones del responsable"; T-152).

- `matrix_page`: la grilla de requisitos por ofertas con el resultado vigente de cada par
  (`evaluate.current_result`, la definición única de "vigente") y el estado del par; el estado
  de cada oferta (requisitos por estado y por resultado, preguntas abiertas); el descarte
  propuesto y el orden económico (`ordering.py`); el aviso de versión posterior de la matriz y
  las ofertas sin documentos. Todo es una propuesta: decide la Comisión (P3).
- `request_all`: "Evaluar todas las ofertas": pide la evaluación de todas las ofertas con
  documentos con un solo pedido (`evaluate.request_evaluation`; el aviso de fin es el de la 003)
  y devuelve cuáles quedaron afuera por no tener documentos, para avisarlo antes.

**Estado de un par.** `sin_evaluar` (no hay resultado), `propuesto` (hay propuesta y ninguna
decisión), `confirmado`, `corregido` o `rechazado`: el de la última decisión entre confirmar,
corregir y rechazar sobre el resultado vigente; pedir la subsanación y subsanar son el recorrido
y no lo cambian. El **resultado efectivo** es el de la propuesta, o el que la persona eligió al
corregir; un resultado rechazado no tiene resultado efectivo (no cuenta para el descarte).
"""

from dataclasses import dataclass, field

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.assessment import ordering
from evaluon.assessment.models import Doubt, Outcome, Question, Result
from evaluon.assessment.services import (
    compliance,
    evaluate,
    review,
    technical,
    technical_report,
)
from evaluon.audit.models import Channel
from evaluon.offers.services import offers as offers_service
from evaluon.offers.services import sheets
from evaluon.tenders.models import Job, JobKind, JobStatus, MatrixVersion, Procedure
from evaluon.tenders.services.validation import latest_validated

PAGE_OPERATION = "evaluon.assessment.services.matrix.matrix_page"
REQUEST_OPERATION = "evaluon.assessment.services.matrix.request_all"

# Estados de un par.
UNEVALUATED = "sin_evaluar"
PENDING = review.PROPOSED
CONFIRMED = "confirmado"
CORRECTED = "corregido"
REJECTED = "rechazado"
STATES = (UNEVALUATED, PENDING, CONFIRMED, CORRECTED, REJECTED)
STATE_LABELS = {
    UNEVALUATED: "Sin evaluar", PENDING: "Propuesto", CONFIRMED: "Confirmado",
    CORRECTED: "Corregido", REJECTED: "Rechazado",
}


@dataclass
class Cell:
    """Un par de la matriz."""

    offer: object
    requirement: object
    result: Result | None
    state: str = UNEVALUATED
    effective_outcome: str | None = None

    @property
    def state_label(self):
        return STATE_LABELS[self.state]

    @property
    def effective_label(self):
        return Outcome(self.effective_outcome).label if self.effective_outcome else ""

    @property
    def reason(self):
        """El motivo del «no determinado» propuesto (por qué no se pudo concluir), o vacío. Solo
        se muestra mientras rige la propuesta: una corrección de la persona ya no lo tiene."""
        if (self.result is not None and self.effective_outcome == Outcome.NO_DETERMINADO
                and self.result.outcome == Outcome.NO_DETERMINADO and self.result.doubt):
            return self.result.doubt
        return ""

    @property
    def reason_label(self):
        return Doubt(self.reason).label if self.reason else ""

    @property
    def from_technical_ok(self):
        """La fila salió del ok de la Comisión al informe técnico (REQ-061)."""
        return self.result is not None and bool(self.result.facts.get("technical_ok"))

    @property
    def changed(self):
        """La persona corrigió el resultado propuesto."""
        return self.state == CORRECTED


def _cell(offer, requirement, result, decision=None):
    """El estado y el resultado efectivo salen de `review` (T-153): una sola definición. La
    última decisión de estado del resultado la trae quien arma la grilla (T-223)."""
    if result is None:
        return Cell(offer=offer, requirement=requirement, result=None)
    return Cell(offer, requirement, result, review.state_from(decision),
                review.outcome_from(result, decision))


@dataclass
class OfferStatus:
    """El estado de la evaluación de una oferta (REQ-058)."""

    offer: object
    evaluated: bool
    run: object = None
    by_state: dict = field(default_factory=dict)
    by_outcome: dict = field(default_factory=dict)
    by_reason: dict = field(default_factory=dict)
    technical: list = field(default_factory=list)
    open_questions: list = field(default_factory=list)
    newer_version: MatrixVersion | None = None
    has_documents: bool = True
    # Hoja de compliance de la oferta (T-189; REQ-073): sus hojas, cuántos requisitos siguen
    # «falta la hoja de compliance» y si ya se puede pedir evaluarlos de nuevo.
    sheets: list = field(default_factory=list)
    externals_pending: int = 0
    sheet_reading: bool = False
    # Informes técnicos del área de la oferta (T-190; REQ-074): los cargados y si alguno se lee.
    reports: list = field(default_factory=list)
    report_reading: bool = False

    @property
    def by_state_rows(self):
        return [(STATE_LABELS[s], self.by_state.get(s, 0)) for s in STATES]

    @property
    def by_outcome_rows(self):
        return [(o.label, self.by_outcome.get(o.value, 0)) for o in Outcome]

    @property
    def by_reason_rows(self):
        """«No determinado» agrupado por motivo: lo que la Comisión tiene que resolver o traer,
        con lo que falta en cada caso."""
        return [(d.label, self.by_reason[d.value]) for d in Doubt if self.by_reason.get(d.value)]


@dataclass
class MatrixPage:
    procedure: Procedure
    version: MatrixVersion | None
    newer_version: MatrixVersion | None
    requirements: list
    offers: list
    cells: dict
    statuses: list
    discards: list
    order: ordering.EconomicOrder | None
    without_documents: list
    pending_job: Job | None
    can_request: bool
    can_decide_technical: bool = False

    @property
    def can_upload_sheet(self):
        """Solo el evaluador sube la hoja de compliance (T-189; REQ-073)."""
        return self.can_decide_technical

    @property
    def can_upload_report(self):
        """Solo el evaluador sube el informe técnico del área (T-190; REQ-074)."""
        return self.can_decide_technical

    @property
    def rows(self):
        """`(requisito, celdas en el orden de las ofertas)` en el orden de la matriz."""
        return [(r, [self.cells[(o.pk, r.pk)] for o in self.offers])
                for r in self.requirements]


def offers_without_documents(procedure, offers=None):
    """Las ofertas del procedimiento que no tienen ningún documento cargado. `offers` son las
    del procedimiento, por número, si quien llama ya las tiene."""
    if offers is None:
        offers = list(procedure.offers.order_by("number"))
    with_documents = offers_service.offer_ids_with_documents(offers)
    return [o for o in offers if o.pk not in with_documents]


def _grid_version(procedure, offers):
    """La versión de la matriz que muestra la grilla: la de la evaluación más reciente; si
    nunca se evaluó, la validada vigente."""
    latest = (Result.objects.filter(offer__in=offers).select_related("run__matrix_version")
              .order_by("-run__matrix_version__number", "-run__number", "-pk").first())
    return latest.run.matrix_version if latest else latest_validated(procedure)


def matrix_page(user, procedure_id, *, channel=Channel.SCREEN):
    """La matriz de evaluación del procedimiento. Lanza `RoleRejected` sin rol de la Comisión y
    `Procedure.DoesNotExist` si no existe."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=PAGE_OPERATION,
                            channel=channel)
    procedure = Procedure.objects.get(pk=procedure_id)
    offers = list(procedure.offers.order_by("number"))
    validated = latest_validated(procedure)
    version = _grid_version(procedure, offers)
    requirements = sheets.firm_requirements(version) if version else []

    # Una consulta para los resultados vigentes y otra para sus decisiones (T-223): antes era
    # una por par y dos por resultado.
    results = evaluate.current_results(offers, requirements)
    decisions = review.current_decisions(results.values())
    cells = {}
    for o in offers:
        for r in requirements:
            result = results.get((o.pk, r.pk))
            cells[(o.pk, r.pk)] = _cell(o, r, result,
                                        decisions.get(result.pk) if result else None)

    newer = validated if (validated is not None and version is not None
                          and validated.number > version.number) else None
    without = offers_without_documents(procedure, offers)
    # Lo que cada oferta pide a la base, de una vez para todas (T-223).
    loaded = _Loaded(
        sheets=compliance.sheets_by_offer(offers),
        reports=technical_report.reports_by_offer(offers),
        externals=compliance.external_results_by_offer(offers),
        questions=_open_questions(offers, requirements),
        without={o.pk for o in without})
    statuses = [_status(o, requirements, cells, validated, version, loaded) for o in offers]
    discards = ordering.propose_discards(offers, requirements, cells)
    pending = (Job.objects.filter(kind=JobKind.EVALUATE_OFFERS, procedure=procedure,
                                  status__in=[JobStatus.QUEUED, JobStatus.RUNNING])
               .order_by("-requested_at").first())
    return MatrixPage(
        procedure=procedure, version=version, newer_version=newer, requirements=requirements,
        offers=offers, cells=cells, statuses=statuses,
        discards=[discards[o.pk] for o in offers if o.pk in discards],
        order=ordering.economic_order(procedure, offers, discards) if offers else None,
        without_documents=without, pending_job=pending,
        can_request=validated is not None and len(without) < len(offers) and pending is None,
        can_decide_technical=(
            getattr(user, "commission_role", "") == CommissionRole.EVALUATOR))


@dataclass
class _Loaded:
    """Lo que el estado de cada oferta necesita y se carga una vez para todas las ofertas."""

    sheets: dict
    reports: dict
    externals: dict
    questions: dict
    without: set


def _open_questions(offers, requirements):
    """`{id de la oferta: preguntas abiertas de esos requisitos}` con una sola consulta."""
    found = {offer.pk: [] for offer in offers}
    for question in (Question.objects.filter(offer__in=offers, requirement__in=requirements,
                                             answers__isnull=True)
                     .select_related("requirement").order_by("requirement__number", "pk")):
        found[question.offer_id].append(question)
    return found


def _status(offer, requirements, cells, validated, version, loaded):
    own = [cells[(offer.pk, r.pk)] for r in requirements]
    evaluated = [c for c in own if c.result is not None]
    status = OfferStatus(offer=offer, evaluated=bool(evaluated),
                         has_documents=offer.pk not in loaded.without)
    for state in STATES:
        status.by_state[state] = sum(1 for c in own if c.state == state)
    for cell in evaluated:
        if cell.effective_outcome:
            status.by_outcome[cell.effective_outcome] = \
                status.by_outcome.get(cell.effective_outcome, 0) + 1
        if cell.reason:
            status.by_reason[cell.reason] = status.by_reason.get(cell.reason, 0) + 1
    if evaluated:
        status.run = max((c.result.run for c in evaluated), key=lambda r: (r.number, r.pk))
        if validated is not None and validated.number > status.run.matrix_version.number:
            status.newer_version = validated
    status.technical = technical.status_of(offer, version, requirements)
    status.sheets = loaded.sheets[offer.pk]
    status.externals_pending = len(loaded.externals[offer.pk])
    status.sheet_reading = any(
        offers_service.document_row(d).state != offers_service.STATE_READ
        for d in status.sheets)
    status.reports = loaded.reports[offer.pk]
    status.report_reading = bool(technical_report.reading_reports(offer, status.reports))
    status.open_questions = loaded.questions[offer.pk]
    return status


def request_all(user, procedure, *, channel=Channel.SCREEN):
    """"Evaluar todas las ofertas": un pedido con todas las ofertas que tienen documentos.
    Devuelve `(pedido, ofertas sin documentos que quedaron afuera)`. Lanza `RoleRejected` y
    `EvaluationRefused` (ver `evaluate.request_evaluation`; si ninguna oferta tiene
    documentos, el motivo es `no_documents`)."""
    require_commission_role(user, CommissionRole.OPERATOR, operation=REQUEST_OPERATION,
                            channel=channel)
    without = offers_without_documents(procedure)
    offers = list(procedure.offers.order_by("number"))
    ready = [o for o in offers if o not in without]
    # Sin ofertas con documentos se pide igual con todas: el pedido se rechaza con su motivo
    # y queda registrado (`no_offers` o `no_documents`).
    requested = evaluate.request_evaluation(
        user, procedure, offers=ready if ready else None, channel=channel)
    return requested, without
