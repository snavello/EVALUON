"""Tema s3_ofertas: las ofertas presentadas y sus documentos, en la pestaña «Ofertas» (REQ-083,
REQ-084, REQ-097; plan 014, T-202).

- **Tabla de ofertas.** Una fila por oferta, con su origen (el acta de apertura del Portal, los
  archivos de la oferta o la carga anterior a la 014), su total, sus documentos con «Subir
  documentos» (varios a la vez), el bloque de anexos técnicos y hoja de compliance de T-204
  (`s3_anexos.offer_block`) y el enlace a su ficha (T-203, `?ficha=`).
- **Alta a la vista** (REQ-083, «Donde esta el alta de ofertas?»): «Agregar oferta desde el
  Portal» lista las ofertas del acta de apertura que todavía no se cargaron (oferente, CUIT,
  total, garantía y renglones cotizados) y las carga con `portal.services.approval.decide` (la
  aprueba un evaluador, como en la 012). «Subir los archivos de una oferta» llama a
  `offers.services.offer_proposal` (T-220): el sistema lee los archivos y propone nombre y CUIT
  con su cita; el evaluador aprueba, corrige escribiendo el valor y el motivo («Escribe el valor y
  motivo») o descarta con motivo. El operador sube y ve la propuesta sin esos botones; si manda
  el formulario, el servicio lo rechaza (403) y deja el hecho. Nada se tipea desde cero.
- **Detalle de la oferta** dentro de la pestaña (`?oferta=`): sus datos, sus documentos con su
  lectura y su origen, la subida múltiple y los anexos y la hoja (T-204).
- **Propuesta de una oferta subida** dentro de la pestaña (`?borrador=`): el avance de la
  lectura y, al terminar, nombre y CUIT con dónde los leyó.

Cada acción es un POST que vuelve a la pestaña con el resultado firmado en la dirección
(`?aviso_ofertas=`), sin guardar nada en la sesión. Las fechas se muestran en hora local.
"""

from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation

from django.core import signing
from django.http import Http404
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from evaluon.accounts.models import CommissionRole
from evaluon.audit.models import Channel
from evaluon.journey.sections.base import Item, Missing, TemaStatus
from evaluon.journey.temas import s3_anexos
from evaluon.journey.window import plain_reason
from evaluon.norms.models import ProposalState
from evaluon.offers.models import Document, DocumentKind, Offer, OfferDraft
from evaluon.offers.proposal_fields import FIELDS
from evaluon.offers.services import document_history as history_service
from evaluon.offers.services import offer_proposal as proposal_service
from evaluon.offers.services import offers as offers_service
from evaluon.portal.models import ItemKind, ItemState, PortalItem, PortalOfferData, PortalQuote
from evaluon.portal.services import approval
from evaluon.tenders.models import JobStatus, Procedure

KEY = "s3_ofertas"
SECTION = "ofertas"
PARTIAL = "journey/temas/s3_ofertas.html"
CHANNEL = Channel.SCREEN

SALT = "journey.s3.ofertas.aviso"
MAX_AGE = 300
PARAM = "aviso_ofertas"
MAX_FILES = 30
QUOTE_LIMIT = 160
REFRESH_SECONDS = 5

# Tipos que no son «documentos» de la fila: los anexos y la hoja van en su columna (T-204) y el
# informe técnico del área no es de la oferta (va en la sección 4).
APART = (DocumentKind.ANEXO_TECNICO, DocumentKind.COMPLIANCE, DocumentKind.INFORME_TECNICO)
OPEN_DRAFTS = (ProposalState.LEYENDO, ProposalState.PROPUESTO, ProposalState.FALLIDO)
LABELS = {"bidder": "Oferente", "cuit": "CUIT"}

READING = {
    offers_service.STATE_QUEUED: ("pend", "En espera de lectura"),
    offers_service.STATE_RUNNING: ("pend", "Leyendo"),
    offers_service.STATE_READ: ("cumple", "Leído"),
    offers_service.STATE_FAILED: ("nocumple", "No se pudo leer"),
}


def can_load(user):
    return getattr(user, "commission_role", "") in (CommissionRole.OPERATOR,
                                                    CommissionRole.EVALUATOR)


def can_decide(user):
    """Solo un evaluador aprueba, corrige o descarta la propuesta (REQ-083, plan, «Roles»)."""
    return getattr(user, "commission_role", "") == CommissionRole.EVALUATOR


# --- Formatos -------------------------------------------------------------------------------------


def _moment(value):
    """Fecha y hora locales (la base guarda UTC); acepta un `datetime` o su texto ISO."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if timezone.is_naive(value):
        value = timezone.make_aware(value, dt_timezone.utc)
    return f"{timezone.localtime(value):%d/%m/%Y %H:%M}"


def _day(value):
    return f"{timezone.localtime(value):%d/%m/%Y}"


def _money(value):
    if value in (None, ""):
        return ""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    whole = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {whole}"


def _who(user):
    return user.get_username() if user is not None else "sistema"


def _quote(text):
    text = " ".join(str(text or "").split())
    return text if len(text) <= QUOTE_LIMIT else text[:QUOTE_LIMIT].rstrip() + "…"


# --- Direcciones y mensajes -----------------------------------------------------------------------


def tab_url(procedure_id, query=""):
    return reverse("expedientes:ofertas", args=[procedure_id]) + (f"?{query}" if query else "")


def offer_url(procedure_id, offer_id, extra=""):
    return tab_url(procedure_id, f"oferta={offer_id}{extra}") + "#s3-oferta"


def draft_url(procedure_id, draft_id):
    return tab_url(procedure_id, f"borrador={draft_id}") + "#s3-borrador"


def pack(results):
    return signing.dumps(results, salt=SALT, compress=True)


def unpack(value):
    """Los resultados firmados de la dirección, o `None` si faltan, están alterados o vencieron."""
    if not value:
        return None
    try:
        data = signing.loads(value, salt=SALT, max_age=MAX_AGE)
    except signing.BadSignature:
        return None
    return [{"name": str(r.get("n", "")), "ok": bool(r.get("ok")), "text": str(r.get("t", ""))}
            for r in data if isinstance(r, dict)]


def _result(name, ok, text):
    return {"n": name, "ok": ok, "t": text}


def back(procedure, results, query="", anchor="#s3-ofertas"):
    base = reverse("expedientes:ofertas", args=[procedure.pk])
    joined = f"{query}&" if query else ""
    return redirect(f"{base}?{joined}{PARAM}={pack(results)}{anchor}")


# --- Lo que hay -----------------------------------------------------------------------------------


def _portal_data(offer):
    try:
        return offer.portal_data
    except PortalOfferData.DoesNotExist:
        return None


def own_current(offer):
    """Los documentos vigentes de la oferta que presentó el oferente, sin anexos, hoja ni
    informe técnico (que tienen su lugar propio)."""
    return list(history_service.current_documents(offer).exclude(kind__in=APART)
                .select_related("loaded_by"))


def _origin(offer):
    """`(de dónde vino, detalle)` de la oferta."""
    data = _portal_data(offer)
    if data is not None and data.item_id:
        return "Portal", "acta de apertura"
    if data is not None and data.document_id:
        return "Archivos de la oferta", (f"nombre y CUIT propuestos por el sistema, aprobados el "
                                         f"{_day(offer.created_at)}")
    return "Carga anterior", f"alta del {_day(offer.created_at)}"


@dataclass
class DocRow:
    document: Document
    kind_label: str
    icon: str
    icon_name: str
    reading_text: str
    pages: object
    origin: str
    origin_date: str
    origin_by: str
    note: str = ""


def _kind_label(document):
    return DocumentKind(document.kind).label if document.kind else "Sin clasificar"


def _doc_row(document):
    row = offers_service.document_row(document)
    icon, name = READING[row.state]
    text = name
    if row.state == offers_service.STATE_READ and (row.unread or row.low_confidence):
        icon, name = "nodet", "Leído, con páginas a revisar"
        parts = []
        if row.unread:
            parts.append("pág. " + ", ".join(str(p["page"]) for p in row.unread) + " sin leer")
        if row.low_confidence:
            parts.append(f"{len(row.low_confidence)} de baja confianza")
        text = "Leído; " + " · ".join(parts)
    report = row.reading.report if row.reading is not None else None
    return DocRow(document=document, kind_label=_kind_label(document), icon=icon,
                  icon_name=name, reading_text=text,
                  pages=report.get("pages") if isinstance(report, dict) else None,
                  origin="Archivo", origin_date=_day(document.loaded_at),
                  origin_by=_who(document.loaded_by) if document.loaded_by_id else "")


@dataclass
class OfferRow:
    offer: Offer
    origin: str
    origin_detail: str
    total: str
    documents: int
    unread: int
    block: object
    detail_url: str
    card_url: str
    stale: bool = False


def _row(user, procedure, offer):
    origin, detail = _origin(offer)
    data = _portal_data(offer)
    documents = own_current(offer)
    unread = sum(1 for d in documents if not d.readings.exists())
    return OfferRow(
        offer=offer, origin=origin, origin_detail=detail,
        total=_money(data.total) if data is not None and data.total is not None else "",
        documents=len(documents), unread=unread, block=s3_anexos.offer_block(user, offer),
        detail_url=offer_url(procedure.pk, offer.pk),
        card_url=tab_url(procedure.pk, f"ficha={offer.pk}") + "#s3-ficha")


def offers_of(procedure):
    return list(procedure.offers.select_related("portal_data").order_by("number"))


# --- Ofertas del acta de apertura del Portal ------------------------------------------------------


def portal_offers(procedure):
    """Los ítems de oferta del Portal sin cargar (el más nuevo de cada oferente)."""
    items = (PortalItem.objects.filter(proposal__link__procedure=procedure, kind=ItemKind.OFERTA,
                                       state=ItemState.PROPUESTO)
             .select_related("proposal").order_by("-pk"))
    seen, found = set(), []
    for item in items:
        if item.key not in seen:
            seen.add(item.key)
            found.append(item)
    return list(reversed(found))


def _portal_view(item):
    data = item.payload
    guarantees = [" · ".join(p for p in (g.get("tipo") or "", g.get("forma") or "",
                                         _money(g.get("monto"))) if p)
                  for g in data.get("garantias", [])]
    return {"item": item, "bidder": data.get("oferente", ""), "cuit": data.get("cuit", ""),
            "total": _money(data.get("total")) or "No consta", "guarantees": guarantees,
            "lines": ", ".join(str(q.get("renglon")) for q in data.get("cotizaciones", [])),
            "notes": data.get("anomalias", []), "published": _day(item.proposal.created_at)}


# --- Ofertas subidas por sus archivos (T-220) ------------------------------------------------------


def open_drafts(procedure):
    return list(OfferDraft.objects.filter(procedure=procedure, state__in=OPEN_DRAFTS)
                .select_related("job", "created_by").order_by("created_at", "pk"))


def _effective(proposal):
    """`({dato: valor vigente}, {dato: [correcciones]})`: la última corrección por encima de lo
    propuesto."""
    history = {}
    for entry in proposal.get("corrections", []):
        history.setdefault(entry["field"], []).append(entry)
    values = {name: (history[name][-1]["corrected"] if name in history
                     else proposal["fields"][name]["proposed"]) for name in FIELDS}
    return values, history


def _datum(name, proposal, values, history):
    datum = proposal["fields"][name]
    citation = datum.get("citation")
    entries = history.get(name, [])
    value = values[name]
    state = "corregido" if entries else ("propuesto" if value else "no_determinado")
    icon, icon_name = {
        "corregido": ("cumple", "Corregido por la Comisión"),
        "propuesto": ("pend", "Propuesto: se aprueba con todo lo propuesto"),
        "no_determinado": ("nodet", "No determinado en los archivos: complételo con Corregir"),
    }[state]
    return {
        "name": name, "label": LABELS[name], "value": value or "", "state": state,
        "icon": icon, "icon_name": icon_name,
        "where": f"{citation['document']}, pág. {citation['page']}" if citation else "",
        "quote": _quote(citation.get("text")) if citation else "",
        "others": [c for c in datum.get("candidates", [])
                   if isinstance(c, str) and c and c != datum.get("proposed")][:3],
        "changes": [{"previous": e.get("previous") or "", "corrected": e["corrected"],
                     "reason": e["reason"], "by": e["by"], "at": _moment(e["at"])}
                    for e in entries],
    }


def draft_view(user, draft):
    """Lo que dibuja la propuesta de una oferta subida, según su estado."""
    job = draft.job
    view = {
        "draft": draft,
        "files": list(draft.files.order_by("id").values_list("file_name", flat=True)),
        "by": _who(draft.created_by) if draft.created_by_id else "",
        "at": _moment(draft.created_at), "can_decide": can_decide(user),
        "reading": draft.state == ProposalState.LEYENDO,
        "failed": draft.state == ProposalState.FALLIDO,
        "rejected": draft.state == ProposalState.RECHAZADO,
        "proposed": draft.state == ProposalState.PROPUESTO,
        "approved": draft.state == ProposalState.APROBADO,
        "failure": plain_reason(job.error if job is not None and job.error else draft.failure),
        "job_text": "", "job_step": "",
        "urls": {name: reverse(f"expedientes:s3_ofertas_{name}",
                               args=[draft.procedure_id, draft.pk])
                 for name in ("corregir", "aprobar", "rechazar")},
    }
    if job is not None:
        view["job_text"] = {JobStatus.QUEUED: "En espera de lectura",
                            JobStatus.RUNNING: "Leyendo los archivos"}.get(job.status, "")
        step = job.progress.get("step") if isinstance(job.progress, dict) else ""
        view["job_step"] = step or ""
    rejection = (draft.proposal or {}).get("rejection")
    if rejection:
        view["rejection"] = {"reason": rejection["reason"], "by": rejection["by"],
                             "at": _moment(rejection["at"])}
    if view["proposed"]:
        proposal = draft.proposal
        values, history = _effective(proposal)
        view["data"] = [_datum(name, proposal, values, history) for name in FIELDS]
        view["missing"] = [LABELS[name] for name in FIELDS if not values[name]]
        view["warnings"] = proposal.get("warnings", [])
        view["found"] = sum(1 for d in view["data"] if d["value"])
    return view


def _draft_summary(procedure, draft):
    state = {ProposalState.LEYENDO: "Leyendo", ProposalState.PROPUESTO: "Esperando aprobación",
             ProposalState.FALLIDO: "No se pudo leer"}[draft.state]
    values = _effective(draft.proposal)[0] if draft.state == ProposalState.PROPUESTO else {}
    return {"draft": draft, "state": state, "bidder": values.get("bidder") or "",
            "cuit": values.get("cuit") or "", "files": draft.files.count(),
            "by": _who(draft.created_by) if draft.created_by_id else "",
            "at": _moment(draft.created_at), "url": draft_url(procedure.pk, draft.pk)}


# --- Estado del tema ----------------------------------------------------------------------------


def status(user, procedure):
    """Lo que aporta a la sección: las propuestas de ofertas subidas que esperan una decisión
    (pendientes), lo que falta (ofertas del acta sin agregar, ninguna oferta) y de dónde vino cada
    oferta. Las ofertas del acta sin aprobar ya las cuenta la sección 1 como pendientes del
    Portal: acá son un faltante, sin sumar a la cuenta."""
    base = tab_url(procedure.pk)
    offers = offers_of(procedure)
    drafts = open_drafts(procedure)
    pending, missing, sources = [], [], []
    for draft in drafts:
        if draft.state == ProposalState.PROPUESTO:
            name = _effective(draft.proposal)[0].get("bidder") or "oferente no determinado"
            pending.append(Item(f"Oferta subida por archivos ({name}): nombre y CUIT propuestos "
                                "para aprobar", draft_url(procedure.pk, draft.pk), 1, "Revisar",
                                kind="oferta_borrador",
                                noun="ofertas subidas con nombre y CUIT para aprobar",
                                group_url=f"{base}#s3-borradores"))
        elif draft.state == ProposalState.FALLIDO:
            pending.append(Item("Oferta subida por archivos: no se pudo leer; descártela o "
                                "súbala de nuevo", draft_url(procedure.pk, draft.pk), 1,
                                "Revisar", kind="oferta_borrador_fallida",
                                noun="ofertas subidas que no se pudieron leer",
                                group_url=f"{base}#s3-borradores"))
    from_portal = portal_offers(procedure)
    if from_portal:
        count = len(from_portal)
        missing.append(Missing(
            f"El acta de apertura del Portal tiene {count} "
            f"{'oferta' if count == 1 else 'ofertas'} sin agregar",
            f"{tab_url(procedure.pk, 'alta=portal')}#s3-alta-portal",
            "Agregar oferta desde el Portal"))
    if not offers and not drafts and not from_portal:
        missing.append(Missing("Todavía no hay ofertas",
                               f"{tab_url(procedure.pk, 'alta=archivos')}#s3-alta-archivos",
                               "Subir los archivos de una oferta"))
    if offers:
        kinds = {}
        for offer in offers:
            label = _origin(offer)[0]
            kinds[label] = kinds.get(label, 0) + 1
        names = {"Portal": "del acta de apertura del Portal",
                 "Archivos de la oferta": "desde los archivos de la oferta",
                 "Carga anterior": "de la carga anterior"}
        sources.append("Ofertas: " + ", ".join(f"{n} {names[label]}"
                                               for label, n in kinds.items()) + ".")
    return TemaStatus(pending=len(pending), pending_items=tuple(pending),
                      missing=tuple(missing), sources=tuple(sources))


# --- Contexto del parcial -------------------------------------------------------------------------


def _offer_detail(user, procedure, offer, request):
    rows = [_doc_row(d) for d in own_current(offer)]
    data = _portal_data(offer)
    origin, origin_detail = _origin(offer)
    guarantees, lines = [], []
    if data is not None:
        guarantees = [" · ".join(p for p in (g.guarantee_type, g.guarantee_form,
                                             _money(g.amount)) if p)
                      for g in data.guarantees.all()]
        lines = list(PortalQuote.objects.filter(offer=offer).order_by("line__number")
                     .values_list("line__number", flat=True))
    return {
        "offer": offer, "rows": rows, "origin": origin, "origin_detail": origin_detail,
        "total": _money(data.total) if data is not None and data.total is not None else "",
        "cuit": data.cuit if data is not None else "", "guarantees": guarantees,
        "lines": ", ".join(str(n) for n in lines),
        "pending": [r for r in rows if r.icon in ("nodet", "nocumple")],
        "block": s3_anexos.offer_block(user, offer),
        "url": offer_url(procedure.pk, offer.pk),
        "card_url": tab_url(procedure.pk, f"ficha={offer.pk}") + "#s3-ficha",
    }


def context(user, procedure, request):
    common = {"pid": procedure.pk, "results": unpack(request.GET.get(PARAM)),
              "annex_notice": s3_anexos.unpack(request.GET.get(s3_anexos.PARAM)),
              "can_load": can_load(user), "can_decide": can_decide(user),
              "tab_url": tab_url(procedure.pk), "mode": "tabla"}
    if request.GET.get("ficha"):
        # La ficha de una oferta (T-203) ocupa la pestaña: la tabla no se muestra.
        return {**common, "mode": "ficha"}
    wanted = request.GET.get("oferta", "")
    offer = (procedure.offers.select_related("portal_data").filter(pk=int(wanted)).first()
             if wanted.isdigit() else None)
    if offer is not None:
        return {**common, "mode": "oferta", "d": _offer_detail(user, procedure, offer, request)}
    wanted = request.GET.get("borrador", "")
    if wanted.isdigit() and can_load(user):
        draft = (OfferDraft.objects.filter(procedure=procedure, pk=int(wanted))
                 .select_related("job", "created_by").first())
        if draft is not None:
            view = draft_view(user, draft)
            return {**common, "mode": "borrador", "v": view,
                    "refresh": REFRESH_SECONDS if view["reading"] else 0}
    rows = [_row(user, procedure, o) for o in offers_of(procedure)]
    link = procedure.portal_links.order_by("-pk").first()
    alta = request.GET.get("alta", "")
    return {
        **common, "rows": rows, "empty": not rows,
        "portal": [_portal_view(i) for i in portal_offers(procedure)], "portal_link": link,
        "portal_url": reverse("expedientes:procedimiento", args=[procedure.pk]) + "#s1-portal",
        "drafts": [_draft_summary(procedure, d) for d in open_drafts(procedure)],
        "open_portal": alta == "portal", "open_files": alta == "archivos",
        "documents_total": sum(r.documents for r in rows),
        "with_sheet": sum(1 for r in rows if r.block.has_sheet),
        "stale_count": sum(1 for r in rows if r.stale),
    }


# --- Acciones -------------------------------------------------------------------------------------


def _procedure(procedure_id):
    try:
        return Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")


def _offer(procedure, offer_id):
    try:
        return Offer.objects.get(pk=offer_id, procedure=procedure)
    except Offer.DoesNotExist:
        raise Http404("No hay una oferta con ese número en este procedimiento.")


def _draft(procedure, draft_id):
    try:
        return OfferDraft.objects.get(pk=draft_id, procedure=procedure)
    except OfferDraft.DoesNotExist:
        raise Http404("No hay una oferta subida con ese número en este procedimiento.")


@require_POST
def take_portal(request, procedure_id, item_id):
    """Agrega la oferta del acta de apertura: la carga el importador de la 012 (la aprueba un
    evaluador; sin ese rol, `decide` lo rechaza con 403 y deja el hecho)."""
    procedure = _procedure(procedure_id)
    try:
        item = PortalItem.objects.get(pk=item_id, kind=ItemKind.OFERTA,
                                      proposal__link__procedure=procedure)
    except PortalItem.DoesNotExist:
        raise Http404("No hay una oferta del Portal con ese número en este procedimiento.")
    name = item.payload.get("oferente", "")
    if item.state != ItemState.PROPUESTO:
        return back(procedure, [_result(name, False, "Esa oferta del Portal ya se decidió.")])
    (result,) = approval.decide(request.user, [item.pk], approval.APPROVE, channel=CHANNEL)
    if result.result == approval.LOADED:
        text = "Se agregó la oferta desde el acta de apertura del Portal."
        if result.reason:
            text += f" {result.reason}"
        return back(procedure, [_result(name, True, text)])
    return back(procedure, [_result(name, False, f"No se agregó. {result.reason}".strip())],
                query="alta=portal", anchor="#s3-alta-portal")


@require_POST
def upload_offer(request, procedure_id):
    """Sube los archivos de una oferta nueva: el sistema los lee y propone nombre y CUIT."""
    procedure = _procedure(procedure_id)
    files = [(f.name, f.read()) for f in request.FILES.getlist("files")[:MAX_FILES]]
    try:
        draft = proposal_service.upload_offer_files(request.user, procedure, files,
                                                    channel=CHANNEL)
    except proposal_service.ProposalRefused as error:
        return back(procedure, [_result("", False, str(error))], query="alta=archivos",
                    anchor="#s3-alta-archivos")
    count = len(files)
    return back(procedure, [_result("", True, f"Se {'subió' if count == 1 else 'subieron'} "
                                    f"{count} archivo{'' if count == 1 else 's'}: el sistema "
                                    "los está leyendo para proponer el nombre y el CUIT del "
                                    "oferente.")],
                query=f"borrador={draft.pk}", anchor="#s3-borrador")


def _to_draft(procedure, draft, ok, text, name=""):
    return back(procedure, [_result(name, ok, text)], query=f"borrador={draft.pk}",
                anchor="#s3-borrador")


@require_POST
def correct(request, procedure_id, draft_id):
    procedure = _procedure(procedure_id)
    draft = _draft(procedure, draft_id)
    field_name = request.POST.get("field", "")
    label = LABELS.get(field_name, "")
    try:
        proposal_service.correct(request.user, draft.pk, field_name,
                                 request.POST.get("value", ""), request.POST.get("reason", ""),
                                 channel=CHANNEL)
    except proposal_service.ProposalRefused as error:
        return _to_draft(procedure, draft, False, str(error), label)
    return _to_draft(procedure, draft, True, "Se guardó la corrección con su motivo. Lo "
                                             "propuesto queda a la vista.", label)


@require_POST
def approve(request, procedure_id, draft_id):
    procedure = _procedure(procedure_id)
    draft = _draft(procedure, draft_id)
    try:
        done = proposal_service.approve(request.user, draft.pk, channel=CHANNEL)
    except proposal_service.ProposalRefused as error:
        return _to_draft(procedure, draft, False, str(error))
    offer = done.offer
    return back(procedure, [_result(offer.bidder, True,
                                    f"Quedó como oferta {offer.number}, con sus "
                                    f"{offer.documents.count()} archivos en espera de lectura.")])


@require_POST
def reject(request, procedure_id, draft_id):
    procedure = _procedure(procedure_id)
    draft = _draft(procedure, draft_id)
    try:
        proposal_service.reject(request.user, draft.pk, request.POST.get("reason", ""),
                                channel=CHANNEL)
    except proposal_service.ProposalRefused as error:
        return _to_draft(procedure, draft, False, str(error))
    return back(procedure, [_result("", True, "Se descartó la propuesta. Los mismos archivos se "
                                    "pueden volver a subir.")])


@require_POST
def upload_documents(request, procedure_id, offer_id):
    """Sube varios documentos a la oferta: cada uno pasa por `load_document` por separado (su
    hecho `offer_load`, su resultado); un rechazado no frena a los demás. Sin rol, 403."""
    procedure = _procedure(procedure_id)
    offer = _offer(procedure, offer_id)
    uploads = request.FILES.getlist("files")[:MAX_FILES]
    query = f"oferta={offer.pk}" if request.POST.get("volver") == "oferta" else ""
    anchor = "#s3-oferta" if query else "#s3-ofertas"
    if not uploads:
        return back(procedure, [_result("", False, "Elija al menos un archivo para subir.")],
                    query=query, anchor=anchor)
    results = []
    for upload_file in uploads:
        try:
            offers_service.load_document(request.user, offer, data=upload_file.read(),
                                         file_name=upload_file.name, channel=CHANNEL)
        except offers_service.OfferRefused as error:
            results.append(_result(upload_file.name, False, str(error)))
        else:
            results.append(_result(upload_file.name, True,
                                   f"Cargado en la oferta {offer.number}; queda en espera de "
                                   "lectura."))
    return back(procedure, results, query=query, anchor=anchor)


urlpatterns = [
    path("ofertas/alta/portal/<int:item_id>/", take_portal, name="s3_ofertas_portal"),
    path("ofertas/alta/archivos/", upload_offer, name="s3_ofertas_alta"),
    path("ofertas/alta/<int:draft_id>/corregir/", correct, name="s3_ofertas_corregir"),
    path("ofertas/alta/<int:draft_id>/aprobar/", approve, name="s3_ofertas_aprobar"),
    path("ofertas/alta/<int:draft_id>/rechazar/", reject, name="s3_ofertas_rechazar"),
    path("ofertas/<int:offer_id>/documentos/subir/", upload_documents,
         name="s3_ofertas_documentos"),
]
