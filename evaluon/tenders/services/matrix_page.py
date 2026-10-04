"""Lo que muestran las páginas de la matriz y su cobertura (REQ-025, REQ-028, REQ-030,
REQ-032; plan 003, "Pantalla" y "Roles"; ADR-0005; T-074).

- `panel`: las versiones de la matriz de un procedimiento y el pedido de propuesta en curso,
  para la página del procedimiento.
- `matrix_page`: una versión con su encabezado, su resumen por clase, sus pendientes primero,
  sus requisitos formales y económicos agrupados por documento y sus filas técnicas por
  renglón. Cada cita lleva el texto literal que se guardó (igual al recorte del texto
  canónico), el documento, la página, la cláusula y los datos para el enlace al original.
- `coverage_page`: la disposición de cada tramo de la propuesta de esa versión.
- `finished_notice`: los pedidos de la persona que terminaron sin que viera el aviso; al
  entregarlos los marca como vistos, así que cada aviso se muestra una sola vez.

Las tres páginas comprueban el rol de la Comisión (el rechazo queda registrado). No
escriben nada, salvo la marca de aviso visto.
"""

from dataclasses import dataclass, field

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit.models import Channel
from evaluon.norms.reading import DocumentReading, Line, Page, Word
from evaluon.norms.splitting.canonical import build_canonical_text
from evaluon.tenders import jobs
from evaluon.tenders.models import (
    DispositionOutcome,
    JobKind,
    JobStatus,
    MatrixVersion,
    PendingItem,
    Procedure,
    Requirement,
    RequirementClass,
    RequirementState,
    Segment,
    SourceEffect,
    VersionStatus,
)
from evaluon.tenders.services.procedures import regime_for

PANEL_OPERATION = "evaluon.tenders.services.matrix_page.panel"
MATRIX_OPERATION = "evaluon.tenders.services.matrix_page.matrix_page"
COVERAGE_OPERATION = "evaluon.tenders.services.matrix_page.coverage_page"


# --- Páginas de las citas --------------------------------------------------------------------


def _rebuild_reading(reading):
    """La lectura guardada como objetos, para volver a armar el texto canónico."""
    data = reading.pages
    pages = [
        Page(**{**page, "lines": [
            Line(**{**line, "words": [Word(**word) for word in line["words"]]})
            for line in page["lines"]
        ]})
        for page in data["pages"]
    ]
    return DocumentReading(file_format=data["file_format"], pages=pages,
                           tool_versions=data["tool_versions"],
                           encoding=data.get("encoding"))


class _Pages:
    """Página de una cita. Un tramo de una sola página da su página; si abarca varias, se
    ubica la cita en las líneas del texto canónico (`pages_at`), que se arma de nuevo una
    vez por lectura. Si no coincide con el texto guardado, se muestra el rango del tramo."""

    def __init__(self):
        self._canonical = {}

    def _canonical_of(self, reading):
        if reading.pk not in self._canonical:
            try:
                canonical = build_canonical_text(_rebuild_reading(reading))
            except Exception:  # noqa: BLE001 - sin líneas, se cae al rango del tramo
                canonical = None
            if canonical is not None and canonical.text != reading.canonical_text:
                canonical = None
            self._canonical[reading.pk] = canonical
        return self._canonical[reading.pk]

    def of(self, segment, start=None, end=None):
        """`(primera, última)` página, o `(None, None)` en una página web."""
        first, last = segment.page_start, segment.page_end
        if first is None or last is None or first == last or start is None:
            return (first, last)
        canonical = self._canonical_of(segment.reading)
        if canonical is None:
            return (first, last)
        found = canonical.pages_at(start, end)
        return found if found[0] is not None else (first, last)


@dataclass
class Place:
    """Dónde está un texto en el pliego: documento, páginas, cláusula."""

    document_id: int
    document_title: str
    page: int | None
    page_end: int | None
    path: str
    label: str


def _place(pages, segment, start=None, end=None):
    first, last = pages.of(segment, start, end)
    document = segment.reading.document
    return Place(
        document_id=document.pk,
        document_title=document.title,
        page=first,
        page_end=last if last != first else None,
        path=segment.path,
        label=segment.label,
    )


# --- Filas -------------------------------------------------------------------------------------


@dataclass
class SourceRow:
    effect: str
    effect_label: str
    place: Place
    text: str
    issued_on: object


@dataclass
class QuoteRow:
    place: Place
    text: str
    wide: bool
    scope: str
    scope_label: str
    current: SourceRow | None = None  # la fuente que modifica el texto, si hay
    notes: list = field(default_factory=list)  # aclaraciones y supresiones


@dataclass
class RequirementRow:
    requirement: Requirement
    quotes: list
    sources: list = field(default_factory=list)  # fuentes que no alcanzan a una cita


@dataclass
class DocumentGroup:
    title: str
    rows: list


@dataclass
class PendingRow:
    item: PendingItem
    reason: str
    place: Place


@dataclass
class MatrixPage:
    version: MatrixVersion
    procedure: Procedure
    run: object
    regime: list
    authorization_date: object
    draft: bool
    counts: dict
    pending: list
    pending_open: int
    groups: list
    technical: list


def _require(user, operation, channel):
    require_commission_role(user, CommissionRole.OPERATOR, operation=operation,
                            channel=channel)


def _quote_rows(requirement, pages):
    by_quote, loose = {}, []
    for source in requirement.sources.select_related(
            "segment__reading__document").order_by("issued_on", "id"):
        row = SourceRow(
            effect=source.effect,
            effect_label=SourceEffect(source.effect).label,
            place=_place(pages, source.segment, source.char_start, source.char_end),
            text=source.text,
            issued_on=source.issued_on,
        )
        if source.quote_id is None:
            loose.append(row)
        else:
            by_quote.setdefault(source.quote_id, []).append(row)

    rows = []
    for quote in requirement.quotes.select_related(
            "segment__reading__document").order_by("order"):
        mine = by_quote.get(quote.pk, [])
        modifying = [s for s in mine if s.effect == SourceEffect.MODIFICA]
        rows.append(QuoteRow(
            place=_place(pages, quote.segment, quote.char_start, quote.char_end),
            text=quote.text,
            wide=bool(quote.quote_flag),
            scope=quote.scope,
            scope_label=quote.get_scope_display() if quote.scope else "",
            current=modifying[-1] if modifying else None,
            notes=[s for s in mine if s.effect != SourceEffect.MODIFICA],
        ))
    return rows, loose


def matrix_page(user, version_id, *, channel=Channel.SCREEN):
    """La página de una versión de la matriz. Lanza `RoleRejected` sin rol de la Comisión
    y `MatrixVersion.DoesNotExist` si no existe."""
    _require(user, MATRIX_OPERATION, channel)
    version = MatrixVersion.objects.select_related(
        "procedure", "run", "validated_by").get(pk=version_id)
    run = version.run
    pages = _Pages()
    requirements = list(
        version.requirements.exclude(state=RequirementState.QUITADO).order_by("number")
    )

    groups, technical, by_document = [], [], {}
    counts = {RequirementClass.FORMAL: 0, RequirementClass.ECONOMICO: 0,
              RequirementClass.TECNICO: 0}
    for requirement in requirements:
        counts[requirement.category] += 1
        quotes, loose = _quote_rows(requirement, pages)
        row = RequirementRow(requirement=requirement, quotes=quotes, sources=loose)
        if requirement.category == RequirementClass.TECNICO:
            technical.append(row)
            continue
        title = quotes[0].place.document_title if quotes else "Sin cita"
        if title not in by_document:
            by_document[title] = DocumentGroup(title=title, rows=[])
            groups.append(by_document[title])
        by_document[title].rows.append(row)

    pending = [
        PendingRow(item=item, reason=item.get_reason_display(),
                   place=_place(pages, item.segment))
        for item in version.pending_items.select_related(
            "segment__reading__document").order_by(
            "resolved_at", "segment__reading__document_id", "segment__order")
    ]

    authorization_date = (run.authorization_date if run
                          else version.procedure.authorization_date)
    return MatrixPage(
        version=version,
        procedure=version.procedure,
        run=run,
        regime=run.regime if run else regime_for(authorization_date),
        authorization_date=authorization_date,
        draft=version.status != VersionStatus.VALIDATED,
        counts={"formal": counts[RequirementClass.FORMAL],
                "economico": counts[RequirementClass.ECONOMICO],
                "tecnico": counts[RequirementClass.TECNICO],
                "total": len(requirements)},
        pending=pending,
        pending_open=sum(1 for p in pending if p.item.resolved_at is None),
        groups=groups,
        technical=technical,
    )


# --- Cobertura -----------------------------------------------------------------------------


@dataclass
class CoverageRow:
    place: Place
    outcome: str
    outcome_label: str
    source_label: str
    reason: str


@dataclass
class CoveragePage:
    version: MatrixVersion
    procedure: Procedure
    run: object
    rows: list
    counts: list  # (etiqueta, cantidad) por disposición
    anomalies: list


def coverage_page(user, version_id, *, channel=Channel.SCREEN):
    """La cobertura de la propuesta de una versión: la disposición de cada tramo, su origen
    y su motivo. Lanza `RoleRejected` sin rol de la Comisión y
    `MatrixVersion.DoesNotExist` si no existe."""
    _require(user, COVERAGE_OPERATION, channel)
    version = MatrixVersion.objects.select_related("procedure", "run").get(pk=version_id)
    run = version.run
    rows, counts = [], {}
    if run is not None:
        pages = _Pages()
        pending_reasons = {item.segment_id: item.get_reason_display()
                           for item in version.pending_items.all()}
        dispositions = {d.segment_id: d for d in run.dispositions.all()}
        reading_ids = [document["reading"] for document in run.documents]
        segments = (Segment.objects.filter(reading_id__in=reading_ids)
                    .select_related("reading__document")
                    .order_by("reading__document_id", "order"))
        for segment in segments:
            disposition = dispositions.get(segment.pk)
            if disposition is None:
                outcome, label, source, reason = "", "Sin disposición", "", ""
            else:
                outcome = disposition.outcome
                label = disposition.get_outcome_display()
                source = disposition.get_source_display()
                reasons = []
                if outcome == DispositionOutcome.DESCARTADO:
                    reasons.append(disposition.get_discard_reason_display())
                if segment.pk in pending_reasons:
                    reasons.append("Pendiente: " + pending_reasons[segment.pk])
                reason = " · ".join(reasons)
            counts[label] = counts.get(label, 0) + 1
            rows.append(CoverageRow(place=_place(pages, segment), outcome=outcome,
                                    outcome_label=label, source_label=source,
                                    reason=reason))
    return CoveragePage(version=version, procedure=version.procedure, run=run, rows=rows,
                        counts=list(counts.items()),
                        anomalies=list(run.anomalies) if run else [])


# --- Página del procedimiento ------------------------------------------------------------------


@dataclass
class Panel:
    versions: list
    active_job: object
    can_request: bool
    draft_open: bool


def panel(user, procedure, *, channel=Channel.SCREEN):
    """Las versiones de la matriz del procedimiento (la más reciente primero), el pedido de
    propuesta en espera o en curso y si se puede pedir otra."""
    _require(user, PANEL_OPERATION, channel)
    versions = list(procedure.matrix_versions.order_by("-number"))
    active = procedure.jobs.filter(
        kind=JobKind.PROPOSE_MATRIX, status__in=(JobStatus.QUEUED, JobStatus.RUNNING)
    ).order_by("-id").first()
    draft_open = any(v.status == VersionStatus.DRAFT for v in versions)
    return Panel(versions=versions, active_job=active,
                 can_request=active is None and not draft_open, draft_open=draft_open)


# --- Aviso de fin ------------------------------------------------------------------------------


@dataclass
class Notice:
    job: object
    failed: bool
    version_id: int | None


def finished_notice(user):
    """Los avisos de los pedidos de `user` que terminaron y todavía no vio, del más
    reciente al más antiguo; los marca como vistos. Sin sesión, no hay avisos."""
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    unseen = list(jobs.unseen_finished(user).select_related("procedure", "document"))
    if not unseen:
        return []
    notices = []
    for job in unseen:
        version_id = None
        if job.kind == JobKind.PROPOSE_MATRIX and job.status == JobStatus.DONE:
            run = job.matrix_runs.order_by("-id").first()
            version_id = run.version_id if run else None
        notices.append(Notice(job=job, failed=job.status == JobStatus.FAILED,
                              version_id=version_id))
    jobs.mark_seen(user, [job.pk for job in unseen])
    return notices
