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

from django.db.models import F

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit.models import Channel
from evaluon.norms.reading import DocumentReading, Line, Page, Word
from evaluon.norms.splitting.canonical import build_canonical_text
from evaluon.tenders import jobs
from evaluon.tenders.models import (
    DATED_DOCUMENT_KINDS,
    ChangeAction,
    Consequence,
    DispositionOutcome,
    JobKind,
    JobStatus,
    MatrixVersion,
    NormSupport,
    PendingItem,
    Procedure,
    Requirement,
    RequirementChange,
    RequirementClass,
    RequirementOrigin,
    RequirementQuote,
    RequirementState,
    Segment,
    SourceEffect,
    VersionStatus,
)
from evaluon.tenders.services.procedures import regime_for

PANEL_OPERATION = "evaluon.tenders.services.matrix_page.panel"
MATRIX_OPERATION = "evaluon.tenders.services.matrix_page.matrix_page"
COVERAGE_OPERATION = "evaluon.tenders.services.matrix_page.coverage_page"


# El estado de cada fila en la cobertura; la sugerencia figura como tal.
ROW_STATE_LABELS = {
    RequirementState.PROPUESTO: "Propuesto",
    RequirementState.CONFIRMADO: "Confirmado",
    RequirementState.QUITADO: "Quitado",
    RequirementState.SUGERIDO: "Sugerencia sin decidir",
}


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


class Pages:
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


def place(pages, segment, start=None, end=None):
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
class OriginalRow:
    """El texto que una circular reemplaza cuando está en un anexo sin requisitos: el recorte
    del tramo del anexo, con su lugar (REQ-031, T-116)."""

    place: Place
    text: str


@dataclass
class SourceRow:
    effect: str
    effect_label: str
    place: Place
    text: str
    issued_on: object
    original: OriginalRow | None = None
    reach: int = 1  # cuántas citas del requisito alcanza el mismo cambio (se muestra una vez)


@dataclass
class QuoteRow:
    place: Place
    text: str
    wide: bool
    scope: str
    scope_label: str
    current: SourceRow | None = None  # la fuente que modifica el texto, si hay
    notes: list = field(default_factory=list)  # aclaraciones y supresiones
    quote_id: int | None = None
    segment_id: int | None = None
    covered: bool = False  # un cambio ya mostrado en una cita anterior también la alcanza


@dataclass
class SupportView:
    """El respaldo normativo de una sugerencia (REQ-036), tal como se guardó: la norma y su
    ruta, la cita literal y dónde está en el original de la norma."""

    unit_label: str
    text: str
    regime: str
    corpus_version: int
    effective_from: object
    effective_to: object
    document_id: int
    page: int | None


# Una frase fija por motivo de la duda (la lista cerrada `DoubtReason`): no es texto del
# modelo (P3).
DOUBT_PHRASES = {
    "no_coinciden": "Las dos preguntas del sistema no coincidieron sobre esta condición.",
    "duda": "El sistema dudó de que sea una condición que se le exige a las ofertas.",
    "descarte_sin_sustento": ("El sistema pensó en descartarla, pero no pudo comprobar el "
                              "motivo en el pliego."),
    "opinion_incompleta": "Solo una de las dos preguntas del sistema pudo responderse.",
}


@dataclass
class OriginNote:
    """"Pasó de sugerencia el DD/MM/AAAA por <persona>" (REQ-035)."""

    at: object
    username: str


@dataclass
class AddedBy:
    """"Agregado por <documento> del <fecha>", del tramo de su cita (REQ-031)."""

    document_title: str
    issued_on: object


@dataclass
class RequirementRow:
    requirement: Requirement
    quotes: list
    sources: list = field(default_factory=list)  # fuentes que no alcanzan a una cita
    supports: list = field(default_factory=list)  # respaldo normativo (sugerencias y su origen)
    doubt_phrase: str = ""  # la frase fija del motivo de la duda, si es o fue sugerencia
    evidence: str = ""  # el indicio literal del tramo, si lo hay
    passed: OriginNote | None = None  # quién la pasó a requisito y cuándo
    added_by: "AddedBy | None" = None  # la circular que lo agregó (origen `circular`)
    review_notes: list = field(default_factory=list)  # circulares que podrían suprimirla (T-127)


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
    removed: list = field(default_factory=list)  # quitados, visibles y con su historia
    can_edit: bool = False  # borrador y rol de la Comisión: corregir, quitar, agregar
    can_confirm: bool = False  # borrador y evaluador: confirmar y resolver pendientes
    segment_options: list = field(default_factory=list)  # (id, descripción) para elegir un tramo
    can_validate: bool = False  # borrador y evaluador: validar y descartar
    can_open_new: bool = False  # validada, la última, sin borrador abierto: versión nueva
    suggestions: list = field(default_factory=list)  # sugerencias de condición sin decidir
    suggestions_open: int = 0


def _require(user, operation, channel):
    require_commission_role(user, CommissionRole.OPERATOR, operation=operation,
                            channel=channel)


def _original_row(pages, source, procedure_id):
    """El original de la fuente, si es válido: la base no garantiza que el tramo sea de un
    documento del pliego de este procedimiento (y no de la circular), ni que el rango sea un
    recorte de su lectura; si no lo es, no se muestra (T-114)."""
    segment = source.original_segment
    if segment is None:
        return None
    reading = segment.reading
    document = reading.document
    start, end = source.original_char_start, source.original_char_end
    if (reading.pk == source.segment.reading_id
            or document.procedure_id != procedure_id
            or document.kind in DATED_DOCUMENT_KINDS
            or start is None or end is None
            or not segment.char_start <= start < end <= len(reading.canonical_text)
            or start >= segment.char_end):
        return None
    return OriginalRow(place=place(pages, segment, start, end),
                       text=reading.canonical_text[start:end])


def quote_rows(requirement, pages):
    """Las citas del requisito con lo que las cambia. Una circular que cambia varias citas
    del mismo requisito deja una fuente por cita; el cambio se muestra una vez, en la primera
    cita que alcanza, y las demás lo indican (`covered`)."""
    procedure_id = requirement.version.procedure_id
    quotes = list(requirement.quotes.select_related(
        "segment__reading__document").order_by("order"))
    order_of = {quote.pk: index for index, quote in enumerate(quotes)}
    sources = sorted(
        requirement.sources.select_related(
            "segment__reading__document", "original_segment__reading__document"),
        key=lambda s: (s.issued_on, order_of.get(s.quote_id, -1), s.pk))
    shown, by_quote, loose, covered = {}, {}, [], set()
    for source in sources:
        key = (source.effect, source.segment_id, source.char_start, source.char_end,
               source.original_segment_id, source.original_char_start)
        if source.quote_id is not None and key in shown:
            shown[key].reach += 1
            covered.add(source.quote_id)
            continue
        row = SourceRow(
            effect=source.effect,
            effect_label=SourceEffect(source.effect).label,
            place=place(pages, source.segment, source.char_start, source.char_end),
            text=source.text,
            issued_on=source.issued_on,
            original=_original_row(pages, source, procedure_id),
        )
        if source.quote_id is None:
            loose.append(row)
        else:
            shown[key] = row
            by_quote.setdefault(source.quote_id, []).append(row)

    rows = []
    for quote in quotes:
        mine = by_quote.get(quote.pk, [])
        modifying = [s for s in mine if s.effect == SourceEffect.MODIFICA]
        rows.append(QuoteRow(
            place=place(pages, quote.segment, quote.char_start, quote.char_end),
            quote_id=quote.pk,
            segment_id=quote.segment_id,
            text=quote.text,
            wide=bool(quote.quote_flag),
            scope=quote.scope,
            scope_label=quote.get_scope_display() if quote.scope else "",
            current=modifying[-1] if modifying else None,
            notes=[s for s in mine if s.effect != SourceEffect.MODIFICA],
            covered=quote.pk in covered and not mine,
        ))
    return rows, loose


def _evidence(doubt):
    """El indicio literal del tramo guardado con la duda, si lo hay."""
    found = doubt.get("evidence") if isinstance(doubt, dict) else None
    if isinstance(found, dict):
        found = found.get("text")
    return found if isinstance(found, str) else ""


def _support_views(requirement):
    views = []
    supports = requirement.norm_supports.select_related(
        "unit__reading__document").order_by("-score", "id")
    for support in supports:
        document = support.unit.reading.document
        views.append(SupportView(
            unit_label=support.unit_label, text=support.text, regime=support.regime,
            corpus_version=support.corpus_version, effective_from=document.effective_from,
            effective_to=document.effective_to, document_id=document.pk,
            page=support.unit.page_start))
    return views


def _passed(requirement):
    """Quién pasó a requisito una fila que fue sugerencia y cuándo; en una versión nueva,
    el dato sale de la fila de la que se copió."""
    seen = 0
    while requirement is not None and seen < 50:
        change = (RequirementChange.objects.filter(
            requirement=requirement, action=ChangeAction.ACEPTAR_SUGERENCIA)
            .select_related("user").order_by("-id").first())
        if change is not None:
            return OriginNote(at=change.at, username=change.user.username if change.user
                              else "")
        requirement, seen = requirement.previous, seen + 1
    return None


def _review_notes(run):
    """Las circulares que podrían dejar sin efecto una condición sin decirlo de forma
    explícita, por número de requisito (T-127, P3): salen de las anomalías de la propuesta."""
    notes = {}
    for anomaly in (run.anomalies if run else None) or []:
        if anomaly.get("type") != "circular_supresion_sin_frase":
            continue
        for number in anomaly.get("requirements", []):
            found = notes.setdefault(number, [])
            if not any(n["circular"] == anomaly["circular"] for n in found):
                found.append({"circular": anomaly["circular"]})
    return notes


def requirement_row(requirement, pages, review=None):
    """Una fila de la matriz: sus citas y, si es o fue una sugerencia, su motivo, el indicio y
    el respaldo normativo (REQ-035, REQ-036)."""
    quotes, loose = quote_rows(requirement, pages)
    row = RequirementRow(requirement=requirement, quotes=quotes, sources=loose)
    row.review_notes = (review or {}).get(requirement.number, [])
    if requirement.origin == RequirementOrigin.CIRCULAR and quotes:
        document = requirement.quotes.select_related("segment__reading__document").order_by(
            "order").first().segment.reading.document
        row.added_by = AddedBy(document_title=document.title, issued_on=document.issued_on)
    if requirement.doubt_reason:
        row.doubt_phrase = DOUBT_PHRASES.get(requirement.doubt_reason, "")
        row.evidence = _evidence(requirement.doubt)
        row.supports = _support_views(requirement)
        if requirement.state != RequirementState.SUGERIDO:
            row.passed = _passed(requirement)
    return row


def _segment_options(version):
    """Los tramos del pliego de la versión, para elegir uno al agregar o corregir."""
    origin = version
    while origin.run_id is None and origin.based_on_id is not None:
        origin = origin.based_on  # una versión abierta sobre otra usa la propuesta de su origen
    reading_ids = [d["reading"] for d in origin.run.documents] if origin.run_id else []
    segments = (Segment.objects.filter(reading_id__in=reading_ids)
                .select_related("reading__document")
                .order_by("reading__document_id", "order"))
    return [(s.pk, f"{s.reading.document.title} · {s.path or s.label or s.key}: "
                   + " ".join(s.text.split())[:70]) for s in segments]


def matrix_page(user, version_id, *, channel=Channel.SCREEN):
    """La página de una versión de la matriz. Lanza `RoleRejected` sin rol de la Comisión
    y `MatrixVersion.DoesNotExist` si no existe."""
    _require(user, MATRIX_OPERATION, channel)
    version = MatrixVersion.objects.select_related(
        "procedure", "run", "validated_by").get(pk=version_id)
    run = version.run
    pages = Pages()
    every = list(version.requirements.order_by("number"))
    review = _review_notes(run)
    suggested = [r for r in every if r.state == RequirementState.SUGERIDO]
    requirements = [r for r in every if r.state not in (RequirementState.QUITADO,
                                                        RequirementState.SUGERIDO)]
    removed = [RequirementRow(requirement=r, quotes=quote_rows(r, pages)[0])
               for r in every if r.state == RequirementState.QUITADO]
    # Primero las que la norma respalda, después el resto, cada grupo en el orden del pliego.
    suggestion_rows = [requirement_row(r, pages) for r in suggested]
    suggestion_rows.sort(key=lambda row: (not row.supports, row.requirement.number))

    groups, technical, by_document = [], [], {}
    counts = {RequirementClass.FORMAL: 0, RequirementClass.ECONOMICO: 0,
              RequirementClass.TECNICO: 0}
    for requirement in requirements:
        counts[requirement.category] += 1
        row = requirement_row(requirement, pages, review)
        quotes = row.quotes
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
                   place=place(pages, item.segment))
        for item in version.pending_items.select_related(
            "segment__reading__document").order_by(
            F("resolved_at").asc(nulls_first=True), "segment__reading__document_id",
            "segment__order")
    ]

    editable = version.status == VersionStatus.DRAFT
    chosen = set(Consequence.objects.filter(
        requirement__in=requirements, chosen=True).values_list("requirement_id", flat=True))
    siblings = version.procedure.matrix_versions
    can_open_new = (
        version.status == VersionStatus.VALIDATED
        and not siblings.filter(number__gt=version.number,
                                status=VersionStatus.VALIDATED).exists()
        and not siblings.filter(status=VersionStatus.DRAFT).exists())
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
                "total": len(requirements),
                "sin_consecuencia": sum(1 for r in requirements if r.pk not in chosen)},
        pending=pending,
        pending_open=sum(1 for p in pending if p.item.resolved_at is None),
        groups=groups,
        technical=technical,
        removed=removed,
        can_edit=editable,
        can_confirm=editable and user.commission_role == CommissionRole.EVALUATOR,
        can_validate=editable and user.commission_role == CommissionRole.EVALUATOR,
        can_open_new=can_open_new,
        segment_options=_segment_options(version) if editable else [],
        suggestions=suggestion_rows,
        suggestions_open=len(suggestion_rows),
    )


# --- Cobertura -----------------------------------------------------------------------------


@dataclass
class CoverageRow:
    place: Place
    outcome: str
    outcome_label: str
    source_label: str
    reason: str
    rows: list = field(default_factory=list)  # (número, estado) de las filas que citan el tramo


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
        pages = Pages()
        pending_reasons = {item.segment_id: item.get_reason_display()
                           for item in version.pending_items.all()}
        dispositions = {d.segment_id: d for d in run.dispositions.all()}
        reading_ids = [document["reading"] for document in run.documents]
        segments = (Segment.objects.filter(reading_id__in=reading_ids)
                    .select_related("reading__document")
                    .order_by("reading__document_id", "order"))
        by_segment = {}
        for quote in RequirementQuote.objects.filter(
                requirement__version=version, scope__in=("", "propia")).select_related(
                "requirement").order_by("requirement__number"):
            by_segment.setdefault(quote.segment_id, []).append(
                (quote.requirement.number, ROW_STATE_LABELS[quote.requirement.state]))
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
            rows.append(CoverageRow(place=place(pages, segment), outcome=outcome,
                                    outcome_label=label, source_label=source,
                                    reason=reason, rows=by_segment.get(segment.pk, [])))
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
    can_open_new: bool = False  # hay una validada y ningún borrador ni pedido en curso


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
                 can_request=active is None and not draft_open, draft_open=draft_open,
                 can_open_new=(active is None and not draft_open and any(
                     v.status == VersionStatus.VALIDATED for v in versions)))


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


# Nombres de antes, para quien todavía los importa (consecuencias, descartadas).
_Pages = Pages
_place = place
_quote_rows = quote_rows
