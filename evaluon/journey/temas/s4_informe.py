"""Tema s4_informe: el informe técnico del área requirente en la pestaña «Evaluación y dictamen»
(REQ-089, REQ-097; decisión 3.5 de la spec; plan 014, T-209).

El juicio técnico es del área (P3): el sistema no lo emite. Acá se sube el informe aprobado del
área, por procedimiento (se carga en cada oferta) o por oferta; el sistema lo lee y propone apto
o no apto por renglón con la cita literal del informe, o dice que no lo trata; y el evaluador da
o retira el ok de la Comisión. Las vistas llaman a los MISMOS servicios que la matriz vieja
(`technical_report.upload_report`, `technical_report.request_proposal`, `technical.give_ok` y
`technical.withdraw_ok`: mismo cambio, mismo hecho de auditoría, mismo rol) y vuelven a la
pestaña con el mensaje de lo hecho. Sin el rol, «acceso denegado» (403) con el rechazo registrado
por el servicio. Un operador ve el estado y no los botones.

Las ofertas con filas técnicas por renglón y sin informe figuran como faltante, con su botón. Los
oks pendientes son pendientes de la sección (la cuenta es la de la etapa `matriz_evaluacion`).
"""

from dataclasses import dataclass, field

from django.http import Http404
from django.urls import path, reverse
from django.views.decorators.http import require_POST

from evaluon.accounts.models import CommissionRole
from evaluon.assessment.models import TechnicalVerdict
from evaluon.assessment.services import technical, technical_report
from evaluon.audit.models import Channel
from evaluon.journey import memo
from evaluon.journey.sections.base import Item, Missing, TemaStatus
from evaluon.journey.temas import s4_propuesta_acciones as acciones
from evaluon.journey.temas.s4_propuesta import when
from evaluon.offers.models import Offer
from evaluon.offers.services import offers as offers_service
from evaluon.tenders.models import Procedure

KEY = "s4_informe"
SECTION = "evaluacion"
PARTIAL = "journey/temas/s4_informe.html"
ANCHOR = "#s4-informe"
CHANNEL = Channel.SCREEN

READING_TEXT = {
    offers_service.STATE_QUEUED: "En espera de lectura",
    offers_service.STATE_RUNNING: "Leyendo",
    offers_service.STATE_READ: "Leído",
    offers_service.STATE_FAILED: "No se pudo leer",
}
VERDICT_ICONS = {technical_report.APTO: ("cumple", "Apto"),
                 technical_report.NO_APTO: ("nocumple", "No apto")}


@dataclass
class ReportDoc:
    title: str
    loaded: str
    state: str
    sha: str


@dataclass
class Cell:
    """Un renglón de una oferta: lo que propone el informe y el ok de la Comisión."""

    icon: str = ""
    name: str = ""
    note: str = ""  # «Ok de X el 07/10/2026 16:40» o el motivo por el que no se propone
    quote: str = ""
    page: int | None = None
    row: object = None


@dataclass
class OfferBlock:
    offer: object
    docs: list = field(default_factory=list)
    reading: bool = False
    rows: list = field(default_factory=list)  # TechnicalRow
    to_decide: list = field(default_factory=list)  # (renglón, veredicto propuesto) sin ok
    approved: int = 0
    can_propose: bool = False

    @property
    def has_report(self):
        return bool(self.docs)


def _is_evaluator(user):
    return getattr(user, "commission_role", "") == CommissionRole.EVALUATOR


def _tab(procedure):
    return reverse("expedientes:evaluacion", args=[procedure.pk])


def _with_rows(page):
    """Los estados de las ofertas con filas técnicas por renglón en la matriz evaluada."""
    return [status for status in page.statuses if status.technical]


def _pending_ok_offers(page):
    """Las ofertas con alguna fila técnica ya evaluada y sin ok vigente (como la etapa)."""
    return [status.offer for status in page.statuses
            if any(not row.approved
                   and page.cells[(status.offer.pk, row.requirement.pk)].result is not None
                   for row in status.technical
                   if (status.offer.pk, row.requirement.pk) in page.cells)]


# --- Estado y pendientes -------------------------------------------------------------------------


def status(user, procedure):
    page = memo.matrix_page(user, procedure.pk, channel=Channel.SCREEN)
    base = _tab(procedure)
    with_rows = _with_rows(page)
    pending = []
    for offer in _pending_ok_offers(page):
        if technical_report.reports_of(offer):
            pending.append(Item(f"Oferta {offer.number}: falta el ok del informe técnico",
                                f"{base}{ANCHOR}", 1, "Resolver"))
        else:  # sin informe, lo primero es subirlo: va al formulario de esa oferta
            pending.append(Item(f"Oferta {offer.number}: falta subir el informe técnico",
                                f"{base}#informe-oferta-{offer.number}", 1, "Resolver"))
    missing = tuple(
        Missing(f"Oferta {s.offer.number}: falta el informe técnico del área",
                f"{base}{ANCHOR}", "Subir informe técnico")
        for s in with_rows if not s.reports)
    sources = []
    uploaded = [d for s in with_rows for d in s.reports]
    if uploaded:
        last = max(d.loaded_at for d in uploaded)
        sources.append("Informe técnico del área: subido por la Comisión, el último el "
                       f"{when(last)}.")
    return TemaStatus(sources=tuple(sources), pending_items=tuple(pending), missing=missing,
                      detailed_stages=("matriz_evaluacion",))


# --- Lo que muestra la pestaña ------------------------------------------------------------------


def _cell(row, block):
    """El renglón de la oferta: el ok si ya se dio; si no, la propuesta del informe."""
    proposal = row.proposal
    if row.approved:
        icon, name = VERDICT_ICONS.get(row.verdict, ("pend", row.verdict_label))
        who = row.ok.user.get_username() if row.ok.user_id else "—"
        return Cell(icon=icon, name=f"{name}: ok de la Comisión",
                    note=f"Ok de {who} el {when(row.ok.at)}", row=row,
                    quote=proposal.quote if proposal else "",
                    page=proposal.page if proposal else None)
    if proposal is not None and proposal.verdict:
        icon, name = VERDICT_ICONS[proposal.verdict]
        return Cell(icon=icon, name=f"{name}, propuesto", row=row, quote=proposal.quote,
                    page=proposal.page)
    if not block.has_report:
        return Cell(icon="pend", name="Falta el informe técnico del área", row=row)
    if block.reading:
        return Cell(icon="pend", name="Falta leer el informe", row=row)
    if proposal is not None and proposal.reason:
        return Cell(icon="nodet", name="Sin propuesta", note=proposal.reason_label, row=row)
    return Cell(icon="pend", name="Sin propuesta todavía", row=row)


def _blocks(page):
    blocks = []
    for status_ in _with_rows(page):
        block = OfferBlock(offer=status_.offer, reading=status_.report_reading,
                           rows=status_.technical)
        for document in status_.reports:
            doc_row = offers_service.document_row(document)
            block.docs.append(ReportDoc(
                title=document.title, loaded=when(document.loaded_at),
                state=READING_TEXT[doc_row.state], sha=document.file_sha256))
        block.approved = sum(1 for r in status_.technical if r.approved)
        block.to_decide = [(r.item, r.proposal.verdict if r.proposal else "")
                           for r in status_.technical if not r.approved]
        block.can_propose = block.has_report and not block.reading
        blocks.append(block)
    return blocks


def context(user, procedure, request):
    page = memo.matrix_page(user, procedure.pk, channel=Channel.SCREEN)
    blocks = _blocks(page)
    items = sorted({row.item for block in blocks for row in block.rows})
    cells = {}
    for block in blocks:
        for row in block.rows:
            cells[(block.offer.pk, row.item)] = _cell(row, block)
    table = [{"item": item, "cells": [cells.get((b.offer.pk, item)) for b in blocks],
              "quotes": [(b.offer, cells[(b.offer.pk, item)]) for b in blocks
                         if (b.offer.pk, item) in cells and cells[(b.offer.pk, item)].quote]}
             for item in items]
    proposed = sum(1 for c in cells.values()
                   if c.row.proposal is not None and c.row.proposal.verdict)
    return {
        "pid": procedure.pk, "blocks": blocks, "table": table,
        "is_evaluator": _is_evaluator(user), "total": len(cells), "proposed": proposed,
        "choices": list(TechnicalVerdict.choices),
        "all_reports": sum(len(b.docs) for b in blocks),
    }


# --- Acciones ------------------------------------------------------------------------------------


def _procedure(procedure_id):
    try:
        return Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")


def _offer(procedure, offer_id):
    offer = Offer.objects.filter(pk=offer_id, procedure=procedure).first()
    if offer is None:
        raise Http404("No hay una oferta con ese número en este procedimiento.")
    return offer


def _plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


@require_POST
def upload(request, procedure_id):
    """Sube el informe del área para todo el procedimiento (sin `offer`) o para una oferta."""
    procedure = _procedure(procedure_id)
    file = request.FILES.get("file")
    data, name = (file.read(), file.name) if file is not None else (b"", "")
    chosen = request.POST.get("offer", "")
    try:
        if chosen:
            offer = _offer(procedure, chosen)
            done = technical_report.upload_report(
                request.user, offer_id=offer.pk, data=data, file_name=name,
                note=request.POST.get("note", ""), channel=CHANNEL)
            scope = f"la oferta {offer.number}"
        else:
            done = technical_report.upload_report(
                request.user, procedure_id=procedure.pk, data=data, file_name=name,
                note=request.POST.get("note", ""), channel=CHANNEL)
            scope = "todo el procedimiento"
    except (technical_report.ReportRefused, offers_service.OfferRefused) as error:
        return acciones.back(procedure, str(error), ok=False)
    text = (f"Se cargó el informe técnico del área para {scope} "
            f"({_plural(len(done.documents), 'oferta', 'ofertas')}); queda en espera de "
            "lectura. Cuando termine, el sistema propone apto o no apto por renglón.")
    if done.already:
        text += " Ya lo tenían: " + ", ".join(f"oferta {o.number}" for o in done.already) + "."
    return acciones.back(procedure, text)


@require_POST
def propose(request, procedure_id, offer_id):
    """Pide proponer de nuevo desde los informes ya leídos de la oferta."""
    procedure = _procedure(procedure_id)
    offer = _offer(procedure, offer_id)
    try:
        technical_report.request_proposal(request.user, offer.pk, channel=CHANNEL)
    except technical_report.ReportRefused as error:
        return acciones.back(procedure, str(error), ok=False)
    return acciones.back(procedure, f"El sistema volvió a leer el informe de la oferta "
                                    f"{offer.number} y dejó su propuesta por renglón.")


@require_POST
def give(request, procedure_id, offer_id):
    """Da el ok de la Comisión al informe: lo que el evaluador marca por renglón (apto o no
    apto) es lo que queda; la propuesta del sistema solo precarga la elección."""
    procedure = _procedure(procedure_id)
    offer = _offer(procedure, offer_id)
    rows = technical.status_of(offer)
    pending = [str(r.item) for r in rows if not r.approved]
    items = None if len(pending) == len(rows) else pending
    verdicts = {i: request.POST.get(f"verdict_{i}", "") for i in pending}
    try:
        technical.give_ok(request.user, offer, items=items, verdicts=verdicts,
                          note=request.POST.get("note", ""), channel=CHANNEL)
    except technical.TechnicalRefused as error:
        return acciones.back(procedure, str(error), ok=False)
    return acciones.back(procedure, f"Se dio el ok al informe técnico de la oferta "
                                    f"{offer.number}. Quedó registrado quién y cuándo.")


@require_POST
def withdraw(request, procedure_id, offer_id):
    """Retira el ok: las filas vuelven a «pendiente del informe técnico». Pide el motivo."""
    procedure = _procedure(procedure_id)
    offer = _offer(procedure, offer_id)
    try:
        technical.withdraw_ok(request.user, offer, items=None,
                              note=request.POST.get("note", ""), channel=CHANNEL)
    except technical.TechnicalRefused as error:
        return acciones.back(procedure, str(error), ok=False)
    return acciones.back(procedure, f"Se retiró el ok del informe técnico de la oferta "
                                    f"{offer.number}. Quedó registrado quién y cuándo.")


urlpatterns = [
    path("evaluacion/informe/subir/", upload, name="s4_informe_subir"),
    path("evaluacion/informe/<int:offer_id>/proponer/", propose, name="s4_informe_proponer"),
    path("evaluacion/informe/<int:offer_id>/ok/", give, name="s4_informe_ok"),
    path("evaluacion/informe/<int:offer_id>/retirar/", withdraw, name="s4_informe_retirar"),
]
