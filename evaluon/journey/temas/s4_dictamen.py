"""Tema s4_dictamen: el dictamen del Portal o subido, en la pestaña «Evaluación y dictamen»
(REQ-092, REQ-097; decisión 4.4 de la spec «Sigue diferido»; plan 014, T-211).

El dictamen siempre viene de afuera: lo publica el Portal (se aprueba su carga, y queda como
archivo del Portal) o la Comisión sube el archivo (documento de tipo `dictamen`, que el sistema no
lee: no encola lectura y la matriz no lo toma como documento base). El sistema NO redacta un
borrador del dictamen: no hay ruta ni botón para eso (P3).

Las dos acciones llaman a los servicios de siempre (`approval.decide` y `load_document`: mismo
cambio, mismo rol, mismo hecho de auditoría) y vuelven a la pestaña con el mensaje de lo hecho. El
operador y el evaluador toman y suben; sin rol, «acceso denegado» (403) con el rechazo registrado
por el servicio. Las fechas se muestran en hora local.

Lo que falta se cuenta como faltante con su acción directa, no como pendiente: el ítem del Portal
sin aprobar ya lo cuenta la propuesta del Portal en la sección 1.
"""

from dataclasses import dataclass
from datetime import date

from django.core.exceptions import ValidationError
from django.forms import DateField
from django.http import Http404
from django.urls import path, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from evaluon.accounts.models import CommissionRole
from evaluon.audit.models import Channel
from evaluon.journey.sections.base import Missing, TemaStatus
from evaluon.journey.temas import s4_propuesta_acciones as acciones
from evaluon.journey.temas.s4_propuesta import when
from evaluon.portal.models import ItemKind, ItemState, PortalItem
from evaluon.portal.services import approval
from evaluon.tenders.models import DocumentKind, Procedure
from evaluon.tenders.services import document_history
from evaluon.tenders.services import documents as services

KEY = "s4_dictamen"
SECTION = "evaluacion"
PARTIAL = "journey/temas/s4_dictamen.html"
ANCHOR = "#s4-dictamen"
CHANNEL = Channel.SCREEN

_date_field = DateField(input_formats=["%Y-%m-%d", "%d/%m/%Y"])

STATES = {
    ItemState.PROPUESTO: ("nodet", "Hay uno en el Portal, sin aprobar"),
    ItemState.APROBADO: ("cumple", "Cargado desde el Portal"),
    ItemState.CARGADO: ("cumple", "Cargado desde el Portal"),
    ItemState.RECHAZADO: ("nocumple", "Se rechazó la carga del dictamen del Portal"),
    ItemState.FALLIDO: ("nocumple", "No se pudo tomar del Portal"),
}
TAKEN = (ItemState.APROBADO, ItemState.CARGADO)


@dataclass
class PortalDictamen:
    item: PortalItem
    name: str
    file: str
    published: str
    state: str
    icon: str
    icon_name: str
    decided: str
    failure: str


def can_load(user):
    return getattr(user, "commission_role", "") in (CommissionRole.OPERATOR,
                                                    CommissionRole.EVALUATOR)


def _tab(procedure):
    return reverse("expedientes:evaluacion", args=[procedure.pk])


# --- Lo que hay ----------------------------------------------------------------------------------


def portal_dictamen(procedure):
    """El último dictamen publicado en el Portal para el procedimiento (el ítem más nuevo), o
    `None`. Un ítem aprobado queda como archivo del Portal; el sin aprobar espera."""
    items = (PortalItem.objects
             .filter(kind=ItemKind.DOCUMENTO, proposal__link__procedure=procedure)
             .select_related("proposal", "file", "decided_by")
             .order_by("-proposal__exploration", "-pk"))
    for item in items:
        if item.payload.get("clase") == "dictamen":
            return item
    return None


def uploaded_dictamenes(procedure):
    return list(document_history.current_documents(procedure)
                .filter(kind=DocumentKind.DICTAMEN).select_related("loaded_by"))


def _published(item):
    value = item.payload.get("fecha")
    if value:
        try:
            return f"{date.fromisoformat(value):%d/%m/%Y}"
        except ValueError:
            pass
    return f"{timezone.localtime(item.proposal.created_at):%d/%m/%Y}"


def _portal_view(item):
    icon, name = STATES[item.state]
    file = item.payload.get("archivo") or {}
    decided = ""
    if item.decided_by_id and item.decided_at:
        decided = f"{item.decided_by.get_username()} el {when(item.decided_at)}"
    return PortalDictamen(
        item=item, name=item.payload.get("nombre") or item.key,
        file=" · ".join(p for p in (file.get("nombre", ""), file.get("formato", "")) if p),
        published=_published(item), state=item.state, icon=icon, icon_name=name,
        decided=decided, failure=item.failure)


def status(user, procedure):
    base = _tab(procedure)
    portal = portal_dictamen(procedure)
    uploaded = uploaded_dictamenes(procedure)
    sources = []
    if portal is not None and portal.state in TAKEN:
        text = f"Dictamen: del Portal, publicado el {_published(portal)}"
        if portal.decided_at:
            text += f", aprobado el {when(portal.decided_at)}"
        sources.append(text + ".")
    if uploaded:
        last = max(uploaded, key=lambda d: (d.loaded_at, d.pk))
        sources.append(f"Dictamen: subido por la Comisión, el último el {when(last.loaded_at)}.")
    missing = ()
    if not sources:
        if portal is not None and portal.state == ItemState.PROPUESTO:
            missing = (Missing("Dictamen: el Portal publicó uno que no se aprobó todavía",
                               f"{base}{ANCHOR}", "Tomar del Portal"),)
        else:
            missing = (Missing("Dictamen: no se cargó", f"{base}{ANCHOR}", "Subir el dictamen"),)
    return TemaStatus(sources=tuple(sources), missing=missing)


def context(user, procedure, request):
    portal = portal_dictamen(procedure)
    view = _portal_view(portal) if portal is not None else None
    uploaded = [{"document": d, "loaded": when(d.loaded_at),
                 "by": d.loaded_by.get_username() if d.loaded_by_id else "—",
                 "issued": f"{d.issued_on:%d/%m/%Y}" if d.issued_on else ""}
                for d in uploaded_dictamenes(procedure)]
    loaded = bool(uploaded) or (view is not None and view.state in TAKEN)
    waiting = view is not None and view.state == ItemState.PROPUESTO
    if loaded:
        cta = "cargado"
    elif waiting:
        cta = "hay uno en el Portal, sin aprobar"
    else:
        cta = "no cargado"
    return {
        "pid": procedure.pk, "aviso": acciones.unpack(request.GET.get("aviso")),
        "portal": view, "uploaded": uploaded, "loaded": loaded, "cta": cta,
        "can_load": can_load(user), "waiting": waiting,
    }


# --- Acciones ------------------------------------------------------------------------------------


def _procedure(procedure_id):
    try:
        return Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")


def _title(name):
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return stem.replace("_", " ").strip() or name


@require_POST
def take(request, procedure_id):
    """Aprueba la carga del dictamen que publicó el Portal: queda como archivo del Portal."""
    procedure = _procedure(procedure_id)
    item = portal_dictamen(procedure)
    if item is None:
        return acciones.back(procedure, "El Portal no publicó un dictamen de este procedimiento.",
                             ok=False)
    if item.state != ItemState.PROPUESTO:
        return acciones.back(procedure, "Ese dictamen del Portal ya se decidió.", ok=False)
    (result,) = approval.decide(request.user, [item.pk], approval.APPROVE, channel=CHANNEL)
    if result.result in (approval.KEPT_AS_FILE, approval.LOADED):
        return acciones.back(procedure, "Se tomó el dictamen del Portal. Queda cargado en esta "
                                        "sección, con quién lo aprobó y cuándo.")
    return acciones.back(procedure, f"No se tomó el dictamen del Portal. {result.reason}".strip(),
                         ok=False)


@require_POST
def upload(request, procedure_id):
    """Sube el dictamen como archivo (documento de tipo `dictamen`, que no se lee)."""
    procedure = _procedure(procedure_id)
    file = request.FILES.get("file")
    if file is None:
        return acciones.back(procedure, "Elija el archivo del dictamen.", ok=False)
    content, name = file.read(), file.name
    title = (request.POST.get("title") or "").strip() or _title(name)
    text_date = (request.POST.get("issued_on") or "").strip()
    try:
        issued_on = _date_field.clean(text_date) if text_date else None
    except ValidationError:
        refusal = services.refuse_invalid_date(
            request.user, procedure, data=content, file_name=name, kind=DocumentKind.DICTAMEN,
            title=title, issued_on_text=text_date, channel=CHANNEL)
        return acciones.back(procedure, str(refusal), ok=False)
    try:
        services.load_document(request.user, procedure, data=content, file_name=name,
                               kind=DocumentKind.DICTAMEN, title=title, issued_on=issued_on,
                               channel=CHANNEL)
    except services.DocumentRefused as error:
        return acciones.back(procedure, str(error), ok=False)
    return acciones.back(procedure, f"Se subió el dictamen «{title}». Queda guardado como "
                                    "archivo: el sistema no lo lee ni lo redacta.")


urlpatterns = [
    path("evaluacion/dictamen/tomar/", take, name="s4_dictamen_tomar"),
    path("evaluacion/dictamen/subir/", upload, name="s4_dictamen_subir"),
]
