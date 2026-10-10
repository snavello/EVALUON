"""Tema s1_pliego: alta del procedimiento subiendo el pliego (REQ-077, REQ-076, REQ-097; plan 014,
T-197).

Sin Portal, el procedimiento se da de alta subiendo el pliego: el sistema lo lee y propone número,
expediente, tipo, objeto, fecha de autorización y renglones, cada uno con dónde lo leyó, y la
Comisión los aprueba o corrige. No hay alta en blanco: sin propuesta no hay nada que escribir; lo
único que se escribe es el valor y el motivo de una corrección, y el motivo de un rechazo.

La pantalla vive en `expedientes/nuevo/pliego/` (una página por pliego subido, con el avance en
vivo mientras se lee) y la entrada «Subir el pliego» de `expedientes/nuevo/` la enchufa este tema
con `context(user, None, request)["upload"]`. En la sección 1 de un procedimiento, el tema muestra
de dónde vino (el pliego, quién lo subió y lo aprobó, lo corregido con su motivo) y los pliegos
leídos que esperan.

Este tema no cambia las reglas de la 014: cada acción llama a `procedure_proposal` (T-196:
`upload_tender`, `proposal_of`, `correct`, `approve`, `reject`), que comprueba el rol y deja el
hecho `procedure_proposal`. Solo un evaluador aprueba, corrige o rechaza; el operador sube y ve
(un POST suyo da 403 y queda el rechazo). Leer no aprueba nada (P3). Las acciones vuelven a la
pantalla con un aviso firmado en la dirección (`?pliego=`), sin guardar nada en la sesión. Las
fechas se muestran en hora local.
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal, InvalidOperation

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit.models import AuditEvent, Channel, EventType, Outcome
from evaluon.journey.sections.base import TemaStatus
from evaluon.journey.temas import s1_portal
from evaluon.journey.window import plain_reason
from evaluon.norms.models import ProposalState
from evaluon.tenders.models import DocumentKind, JobStatus, Procedure, ProcedureDraft
from evaluon.tenders.proposal.procedure_fields import (
    DEDUCED_FROM_NUMBER,
    FIELDS,
    REQUIRED_FIELDS,
)
from evaluon.tenders.services import documents
from evaluon.tenders.services import procedure_proposal as service
from evaluon.tenders.services import procedures

KEY = "s1_pliego"
SECTION = "procedimiento"
PARTIAL = "journey/temas/s1_pliego.html"
ANCHOR = "#s1-pliego"
ADD_OPERATION = "evaluon.journey.temas.s1_pliego.add_to_procedure"
REFRESH_SECONDS = 5
OPEN_STATES = (ProposalState.LEYENDO, ProposalState.PROPUESTO, ProposalState.FALLIDO)
WAITING_LIMIT = 10
QUOTE_LIMIT = 160

LABELS = {
    "number": "Número",
    "file_number": "Expediente",
    "procedure_type": "Tipo",
    "subject": "Objeto",
    "authorization_date": "Fecha de autorización",
}
LINE_LABELS = {"description": "Descripción", "quantity": "Cantidad", "unit": "Unidad"}
STATE_TEXT = {
    ProposalState.LEYENDO: "Leyendo",
    ProposalState.PROPUESTO: "Esperando aprobación",
    ProposalState.FALLIDO: "No se pudo leer",
}
JOB_TEXT = {JobStatus.QUEUED: "En espera de lectura", JobStatus.RUNNING: "Leyendo el pliego"}


def can_load(user):
    return user.commission_role in (CommissionRole.OPERATOR, CommissionRole.EVALUATOR)


def can_decide(user):
    """Solo un evaluador aprueba, corrige o rechaza (REQ-077)."""
    return user.commission_role == CommissionRole.EVALUATOR


# --- Formatos -----------------------------------------------------------------------------------


def _moment(value):
    """Fecha y hora en hora local; acepta un `datetime` o su texto ISO."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if timezone.is_naive(value):
        value = timezone.make_aware(value, dt_timezone.utc)
    return f"{timezone.localtime(value):%d/%m/%Y %H:%M}"


def _day(value):
    try:
        return f"{date.fromisoformat(str(value)):%d/%m/%Y}"
    except ValueError:
        return str(value)


def _number(value):
    try:
        text = format(Decimal(str(value)).normalize(), "f")
    except (InvalidOperation, ValueError):
        return str(value)
    whole, _, rest = text.partition(".")
    whole = f"{int(whole):,}".replace(",", ".")
    return f"{whole},{rest}" if rest else whole


def _display(name, value):
    if not value:
        return ""
    return _day(value) if name == "authorization_date" else str(value)


def _quote(citation):
    text = " ".join(str(citation.get("text", "")).split())
    return text if len(text) <= QUOTE_LIMIT else text[:QUOTE_LIMIT].rstrip() + "…"


def _where(citation):
    return f"Pliego, pág. {citation['page']}" if citation else ""


def _field_label(field):
    if field in LABELS:
        return LABELS[field]
    _, number, attr = field.split(".")
    return f"Renglón {number}: {LINE_LABELS[attr].lower()}"


# --- Lo que muestra la propuesta ------------------------------------------------------------------


def _effective(proposal):
    """Valores vigentes: `({dato: valor}, {número: {atributo: valor}}, {campo: [correcciones]})`,
    con la última corrección de cada uno por encima de lo propuesto."""
    history = {}
    for item in proposal.get("corrections", []):
        history.setdefault(item["field"], []).append(item)
    latest = {field: items[-1]["corrected"] for field, items in history.items()}
    values = {name: latest.get(name, proposal["fields"][name]["proposed"]) for name in FIELDS}
    lines = {}
    for line in proposal["lines"]:
        number = line["number"]
        lines[number] = {attr: latest.get(f"line.{number}.{attr}", line[attr])
                         for attr in LINE_LABELS}
    return values, lines, history


def _changes(entries):
    return [{"label": _field_label(item["field"]),
             "previous": _display(item["field"], item.get("previous")),
             "corrected": _display(item["field"], item["corrected"]),
             "reason": item["reason"], "by": item["by"], "at": _moment(item["at"])}
            for item in entries]


def _regimes(value):
    try:
        return [r["name"] for r in procedures.regime_for(date.fromisoformat(value))]
    except (ValueError, TypeError):
        return []


def _datum_row(name, datum, values, history, deciding):
    value = values[name]
    entries = history.get(name, [])
    citation = datum.get("citation")
    state = "corregido" if entries else ("propuesto" if value else "no_determinado")
    icon, icon_name = {
        "corregido": ("cumple", "Corregido por la Comisión"),
        "propuesto": ("pend", "Propuesto: se aprueba con todo lo propuesto"),
        "no_determinado": ("nodet", "No determinado en el pliego: complételo con Corregir"),
    }[state]
    return {
        "name": name, "label": LABELS[name], "required": name in REQUIRED_FIELDS,
        "value": _display(name, value), "raw": value or "", "state": state,
        "icon": icon, "icon_name": icon_name,
        "where": _where(citation), "quote": _quote(citation) if citation else "",
        "deduced": datum.get("deduced") == DEDUCED_FROM_NUMBER,
        "others": [_display(name, c) for c in datum.get("candidates", [])
                   if c and c != datum.get("proposed")][:3],
        "regimes": _regimes(value) if name == "authorization_date" and value else [],
        "changes": _changes(entries),
        "is_date": name == "authorization_date", "can_correct": deciding,
    }


def _line_row(line, current, history, deciding):
    number = line["number"]
    entries = [item for field, items in history.items() if field.startswith(f"line.{number}.")
               for item in items]
    entries.sort(key=lambda item: item["at"])
    quantity = current["quantity"]
    return {
        "number": number, "description": current["description"],
        "quantity": " ".join(p for p in (_number(quantity) if quantity else "", current["unit"])
                             if p),
        "no_quantity": not quantity, "where": _where(line.get("citation")),
        "quote": _quote(line["citation"]) if line.get("citation") else "",
        "changes": _changes(entries), "corrected": bool(entries), "can_correct": deciding,
    }


def draft_view(user, draft):
    """Lo que dibuja la pantalla de un borrador, según su estado."""
    job = draft.job
    view = {
        "draft": draft, "state": draft.state, "file_name": draft.file_name,
        "uploaded_by": draft.created_by.get_username() if draft.created_by_id else "",
        "uploaded_at": _moment(draft.created_at), "can_decide": can_decide(user),
        "reading": draft.state == ProposalState.LEYENDO,
        "failed": draft.state == ProposalState.FALLIDO,
        "rejected": draft.state == ProposalState.RECHAZADO,
        "proposed": draft.state == ProposalState.PROPUESTO,
        "job_text": "", "job_step": "", "job_at": "",
        "failure": plain_reason(job.error if job is not None and job.error else draft.failure),
    }
    if job is not None:
        view["job_text"] = JOB_TEXT.get(job.status, "")
        step = job.progress.get("step") if isinstance(job.progress, dict) else ""
        view["job_step"] = step or ""
        when = job.started_at or job.requested_at
        view["job_at"] = _moment(when) if when else ""
    entry = (draft.proposal or {}).get("rejection")
    if entry:
        view["rejection"] = {"reason": entry["reason"], "by": entry["by"],
                             "at": _moment(entry["at"])}
    if view["proposed"]:
        proposal = draft.proposal
        values, lines, history = _effective(proposal)
        deciding = view["can_decide"]
        view["data"] = [_datum_row(name, proposal["fields"][name], values, history, deciding)
                        for name in FIELDS]
        view["lines"] = [_line_row(line, lines[line["number"]], history, deciding)
                         for line in proposal["lines"]]
        view["data_found"] = sum(1 for row in view["data"] if row["raw"])
        view["missing"] = [LABELS[name] for name in REQUIRED_FIELDS if not values[name]]
        view["warnings"] = proposal.get("warnings", [])
    return view


def waiting_drafts(limit=WAITING_LIMIT):
    """Los pliegos subidos que todavía no se resolvieron, del más nuevo al más viejo."""
    drafts = (ProcedureDraft.objects.filter(state__in=OPEN_STATES)
              .select_related("created_by").defer("content").order_by("-created_at", "-pk"))
    return [{"pk": d.pk, "file_name": d.file_name, "state": STATE_TEXT[d.state],
             "by": d.created_by.get_username() if d.created_by_id else "",
             "at": _moment(d.created_at),
             "url": reverse("expedientes:s1_pliego_borrador", args=[d.pk])}
            for d in drafts[:limit]]


def origin_of(procedure):
    """De dónde vino un procedimiento dado de alta con un pliego: el archivo, quién lo subió y lo
    aprobó, y lo corregido con su motivo. `None` si no nació de un pliego subido."""
    draft = (ProcedureDraft.objects.filter(procedure=procedure, state=ProposalState.APROBADO)
             .select_related("created_by").defer("content").first())
    if draft is None:
        return None
    event = (AuditEvent.objects.filter(event_type=EventType.PROCEDURE_PROPOSAL,
                                       outcome=Outcome.OK, detail__action="approve",
                                       detail__draft=draft.pk)
             .select_related("user").order_by("-pk").first())
    detail = event.detail if event else {}
    return {
        "file_name": draft.file_name, "size": draft.file_size,
        "by": draft.created_by.get_username() if draft.created_by_id else "",
        "at": _moment(draft.created_at),
        "approved_by": event.user.get_username() if event and event.user_id else "",
        "approved_at": _moment(event.occurred_at) if event else "",
        "changes": _changes(detail.get("corrections", draft.proposal.get("corrections", []))),
        "discarded": detail.get("discarded_lines", []),
        "lines": detail.get("lines"),
    }


# --- Estado y contexto del tema -------------------------------------------------------------------


def status(user, procedure):
    """El tema no cuenta pendientes del procedimiento: un pliego que espera todavía no pertenece a
    ninguno."""
    return TemaStatus()


def context(user, procedure, request):
    """Lo que necesita el parcial: la entrada «Subir el pliego» (en el alta, `procedure=None`) o el
    origen del procedimiento y los pliegos que esperan (en la sección 1)."""
    loads = can_load(user)
    messages = s1_portal.unpack(request.GET.get("pliego")) if request is not None else None
    return {
        "upload": loads, "procedure": procedure is not None,
        "upload_url": reverse("expedientes:s1_pliego_subir"),
        "pid": procedure.pk if procedure is not None else None,
        "new_url": reverse("expedientes:nuevo") + "#entrada-pliego",
        "messages": messages, "waiting": waiting_drafts() if loads else [],
        "origin": origin_of(procedure) if procedure is not None else None,
    }


# --- Las acciones (vuelven a la pantalla con un aviso) -----------------------------------------------


def _pack(text, ok=True):
    return s1_portal.pack([s1_portal.entry(text, ok=ok)])


def _to_draft(draft_id, text, ok=True):
    url = reverse("expedientes:s1_pliego_borrador", args=[draft_id])
    return redirect(f"{url}?pliego={_pack(text, ok)}")


def _to_entry(text, ok=True):
    url = reverse("expedientes:nuevo")
    return redirect(f"{url}?pliego={_pack(text, ok)}#entrada-pliego")


def _draft_or_404(draft_id):
    try:
        return ProcedureDraft.objects.defer("content").select_related("job", "created_by").get(
            pk=draft_id)
    except ProcedureDraft.DoesNotExist:
        raise Http404("No hay un pliego subido con ese número.")


@require_POST
def upload(request):
    """Sube el pliego y pasa a su pantalla, donde se ve cómo avanza la lectura. Sin el rol de la
    Comisión el servicio lo rechaza (403) y deja el hecho."""
    sent = request.FILES.get("file")
    data = sent.read() if sent is not None else b""
    try:
        draft = service.upload_tender(request.user, data, sent.name if sent is not None else "")
    except service.ProposalRefused as refused:
        return _to_entry(str(refused), ok=False)
    return _to_draft(draft.pk, "Se subió el pliego: el sistema lo está leyendo.")


@require_POST
def add_to_procedure(request, procedure_id):
    """«Subir archivo» de la sección 1 de un procedimiento ya creado: agrega el pliego al
    procedimiento abierto con el mismo servicio de carga de la sección 2 (`load_document`); no
    da de alta otro procedimiento (T-227, D-2). El archivo queda en espera de lectura y, leído,
    la Comisión lo ve en la sección 2. Sin el rol de la Comisión, 403 con el rechazo registrado."""
    try:
        procedure = Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")
    sent = request.FILES.get("file")
    url = reverse("expedientes:procedimiento", args=[procedure.pk])
    try:
        if sent is None:
            require_commission_role(request.user, CommissionRole.OPERATOR,
                                    operation=ADD_OPERATION, channel=Channel.SCREEN)
            raise documents.DocumentRefused("Elija el archivo del pliego.", "missing_data")
        documents.load_document(request.user, procedure, data=sent.read(), file_name=sent.name,
                                kind=DocumentKind.PLIEGO, title=sent.name.rsplit(".", 1)[0],
                                channel=Channel.SCREEN)
    except documents.DocumentRefused as refused:
        return redirect(f"{url}?pliego={_pack(str(refused), ok=False)}#s1-pliego-subir")
    return redirect(f"{url}?pliego={_pack('Se subió el pliego a este procedimiento: queda en '
                                          'espera de lectura.')}#s1-pliego")


@require_GET
def draft_page(request, draft_id):
    """La pantalla del pliego subido: el avance de la lectura y, al terminar, la propuesta."""
    from evaluon.journey.views.nuevo import _shell

    try:
        service.proposal_of(request.user, draft_id)  # el rol, antes de mostrar nada
    except ProcedureDraft.DoesNotExist:
        raise Http404("No hay un pliego subido con ese número.")
    draft = _draft_or_404(draft_id)
    if draft.state == ProposalState.APROBADO and draft.procedure_id:
        return redirect(reverse("expedientes:procedimiento", args=[draft.procedure_id]))
    view = draft_view(request.user, draft)
    context = _shell(request)
    context.update({
        "v": view, "messages": s1_portal.unpack(request.GET.get("pliego")),
        "refresh": REFRESH_SECONDS if view["reading"] else 0,
        "new_url": reverse("expedientes:nuevo") + "#entrada-pliego",
        "back_url": reverse("expedientes:nuevo"),
        "urls": {name: reverse(f"expedientes:s1_pliego_{name}", args=[draft.pk])
                 for name in ("corregir", "aprobar", "rechazar")},
    })
    return render(request, "journey/s1_pliego_borrador.html", context)


@require_POST
def correct(request, draft_id):
    _draft_or_404(draft_id)
    try:
        service.correct(request.user, draft_id, request.POST.get("field", ""),
                        request.POST.get("value", ""), request.POST.get("reason", ""))
    except service.ProposalRefused as refused:
        return _to_draft(draft_id, str(refused), ok=False)
    return _to_draft(draft_id, "Se guardó la corrección con su motivo. Lo propuesto queda a la "
                     "vista.")


@require_POST
def approve(request, draft_id):
    _draft_or_404(draft_id)
    discard = [int(n) for n in request.POST.getlist("descartar") if n.isdigit()]
    try:
        draft = service.approve(request.user, draft_id, {"discard_lines": discard})
    except service.ProposalRefused as refused:
        return _to_draft(draft_id, str(refused), ok=False)
    text = (f"El procedimiento {draft.procedure.number} quedó creado desde el pliego "
            f"«{draft.file_name}»: ya están disponibles todas sus pestañas.")
    url = reverse("expedientes:procedimiento", args=[draft.procedure_id])
    return redirect(f"{url}?portal={_pack(text)}{ANCHOR}")


@require_POST
def reject(request, draft_id):
    draft = _draft_or_404(draft_id)
    try:
        service.reject(request.user, draft_id, request.POST.get("reason", ""))
    except service.ProposalRefused as refused:
        return _to_draft(draft_id, str(refused), ok=False)
    return _to_entry(f"Se descartó la lectura de «{draft.file_name}». Puede volver a subir el "
                     "pliego.")


# Rutas del alta, sin procedimiento: las monta `journey/urls.py` bajo `nuevo/pliego/`.
draft_urlpatterns = [
    path("subir/", upload, name="s1_pliego_subir"),
    path("<int:draft_id>/", draft_page, name="s1_pliego_borrador"),
    path("<int:draft_id>/corregir/", correct, name="s1_pliego_corregir"),
    path("<int:draft_id>/aprobar/", approve, name="s1_pliego_aprobar"),
    path("<int:draft_id>/rechazar/", reject, name="s1_pliego_rechazar"),
]
# Las del procedimiento: el tema no tiene ninguna (el alta no cuelga de un procedimiento).
urlpatterns = [
    path("procedimiento/pliego/subir/", add_to_procedure, name="s1_pliego_agregar"),
]
