"""Tema s3_ficha: «Lo que presentó cada oferta», la ficha de cada oferta dentro de la pestaña
«Ofertas» (REQ-086; plan 014, T-203).

La ficha dice, por oferta y por requisito de la matriz validada, qué presentó el oferente con el
fragmento literal que lo respalda y dónde está (documento y página), o «No se encontró en la
oferta». No juzga si cumple: eso es la sección 4 (P3). La ficha es opcional: una oferta sin ficha
no cuenta como faltante, es una sugerencia; las filas propuestas de una ficha cuentan como
pendientes de decidir.

Se abre dentro de la pestaña con `?ficha=<oferta>` y vuelve con «Volver a Ofertas». El enlace a
la ficha de cada oferta está en la tabla de ofertas (s3_ofertas, T-202). Cada acción
(armar la ficha, confirmar filas, corregir, quitar, restituir o agregar un fragmento) es un POST
que llama al mismo servicio de `evaluon.offers.services` que la pantalla vieja (el mismo cambio,
el mismo rol y el mismo hecho de auditoría) y vuelve a la pestaña con el mensaje de lo hecho. El
servicio no guarda el motivo de una corrección ni de un quitar: queda en un hecho propio de
auditoría, con quién y cuándo, y se ve en la fila. Un operador no ve el botón de confirmar: lo
decide un evaluador.

El mensaje viaja firmado en la dirección (`?aviso_ficha=`), sin guardar nada en la sesión.
"""

from collections import defaultdict

from django.core import signing
from django.http import Http404
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from evaluon.accounts.models import CommissionRole
from evaluon.audit import services as audit
from evaluon.audit.models import AuditEvent, Channel, EventType, Outcome
from evaluon.journey.sections.base import Item, TemaStatus
from evaluon.journey.stages.ofertas import _pending_sheets
from evaluon.offers.models import (
    Change,
    Document,
    Fragment,
    Offer,
    Passage,
    Sheet as SheetModel,
    SheetChannel,
    SheetEntry,
)
from evaluon.offers.models import Outcome as EntryOutcome
from evaluon.offers.services import review
from evaluon.offers.services import sheets as sheets_service
from evaluon.offers.services.offers import offer_ids_with_documents
from evaluon.tenders.models import Procedure
from evaluon.tenders.services.validation import latest_validated

KEY = "s3_ficha"
SECTION = "ofertas"
PARTIAL = "journey/temas/s3_ficha.html"

SALT = "journey.s3.ficha.aviso"
AVISO_MAX_AGE = 300
PARAM = "aviso_ficha"
ANCHOR = "#s3-aviso-ficha"
CHANNEL = Channel.SCREEN
EXCERPT = 200
PASSAGE_LABEL = 80
ACTIONS = {"corregir": "Corregido", "quitar": "Quitado"}


# --- Mensajes y regreso a la pestaña -------------------------------------------------------------


def pack(text, ok=True):
    return signing.dumps({"ok": ok, "m": text}, salt=SALT, compress=True)


def unpack(value):
    """El mensaje firmado de la dirección, o `None` si falta, está alterado o venció."""
    if not value:
        return None
    try:
        data = signing.loads(value, salt=SALT, max_age=AVISO_MAX_AGE)
    except signing.BadSignature:
        return None
    return {"ok": bool(data.get("ok")), "text": str(data.get("m", ""))}


def tab_url(procedure_id, offer_id=None, entry_id=None):
    """La pestaña «Ofertas»; con `offer_id`, abierta en la ficha de esa oferta (y con
    `entry_id`, en esa fila)."""
    url = reverse("expedientes:ofertas", args=[procedure_id])
    query = []
    if offer_id:
        query.append(f"ficha={offer_id}")
    if entry_id:
        query.append(f"fila={entry_id}")
    return url + (("?" + "&".join(query)) if query else "")


def back(procedure, offer, text, ok=True, entry=None):
    url = tab_url(procedure.pk, offer.pk, entry)
    return redirect(f"{url}&{PARAM}={pack(text, ok)}{ANCHOR}")


def _when(moment):
    """Fecha y hora en hora local (America/Argentina/Buenos_Aires), no la de la base en UTC."""
    return f"{timezone.localtime(moment):%d/%m/%Y %H:%M}"


# --- Qué cuenta en la sección --------------------------------------------------------------------


def _latest_sheet(offer):
    return offer.sheets.filter(channel=SheetChannel.SCREEN).order_by("-number").first()


def _latest_sheets(offers):
    """`{id de la oferta: su última ficha de pantalla}` con una sola consulta (T-223)."""
    found = {}
    for sheet in (SheetModel.objects.filter(offer__in=list(offers), channel=SheetChannel.SCREEN)
                  .select_related("matrix_version").order_by("number", "pk")):
        found[sheet.offer_id] = sheet
    return found


def _all_read(offers):
    documents = Document.objects.filter(offer__in=offers).exclude(kind="informe_tecnico")
    return documents.exists() and not documents.filter(readings__isnull=True).exists()


def status(user, procedure):
    """Las filas propuestas son pendientes y la oferta sin ficha es una sugerencia; ninguna es
    faltante (la ficha es opcional). Las cuentas las suma la etapa de ofertas de la 013; acá se
    reemplazan sus renglones genéricos por uno por oferta, con su enlace dentro de la pestaña."""
    offers = list(procedure.offers.order_by("number"))
    having = offer_ids_with_documents(offers)
    with_documents = [o for o in offers if o.pk in having]
    latest = _latest_sheets(offers)
    pending = [Item(f"Oferta {offer.number} ({offer.bidder}): {count} "
                    f"{'fila' if count == 1 else 'filas'} de la ficha por confirmar",
                    tab_url(procedure.pk, offer.pk) + "#s3-ficha", count, "Resolver",
                    kind="ficha", noun="ofertas con filas de la ficha por confirmar",
                    group_url=tab_url(procedure.pk) + "#s3-ficha")
               for offer, _, count in _pending_sheets(with_documents)]
    suggestions = []
    if _all_read(with_documents) and latest_validated(procedure) is not None:
        suggestions = [Item(f"Oferta {o.number} ({o.bidder}): se puede armar la ficha "
                            "(opcional)", tab_url(procedure.pk, o.pk) + "#s3-ficha", 1,
                            "Ver", kind="ficha_arma",
                            noun="ofertas donde se puede armar la ficha (opcional)",
                            group_url=tab_url(procedure.pk) + "#s3-ficha")
                       for o in with_documents if o.pk not in latest]
    sources = []
    for offer in offers:
        sheet = latest.get(offer.pk)
        if sheet is not None:
            sources.append(f"Ficha de la oferta {offer.number}: armada el "
                           f"{timezone.localtime(sheet.built_at):%d/%m/%Y} sobre la versión "
                           f"{sheet.matrix_version.number} de la matriz.")
    return TemaStatus(sources=tuple(sources), pending_items=tuple(pending),
                      suggestion_items=tuple(suggestions), detailed_stages=("ofertas",))


# --- Lo que se ve --------------------------------------------------------------------------------


def _excerpt(text):
    text = " ".join((text or "").split())
    return text if len(text) <= EXCERPT else text[:EXCERPT].rstrip() + "…"


def _entry_state(entry):
    """Ícono y nombre del estado de una fila. No juzga cumplimiento: dice si hay respaldo y si
    la Comisión ya lo confirmó."""
    if entry.outcome == EntryOutcome.NO_ENCONTRADO:
        return "nocumple", "No se encontró en la oferta"
    if entry.unread_pages_warning:
        return "nodet", "Hay páginas de la oferta sin leer"
    if entry.state == "confirmado":
        return "cumple", "Confirmada por la Comisión"
    return "pend", "Propuesta, sin confirmar"


QUOTED = {"cotizado": "Renglón cotizado", "no_cotizado": "Renglón no cotizado",
          "no_se_pudo_leer": "Renglón: no se pudo leer"}


def _presented(entry, item):
    if entry.outcome == EntryOutcome.NO_ENCONTRADO:
        return ""
    parts = []
    if entry.synthesis:
        parts.append(entry.synthesis)
    if item is not None and entry.quoted in QUOTED:
        parts.append(QUOTED[entry.quoted])
    return " · ".join(parts)


def _motives(entry_ids):
    """El motivo de cada corrección o quitar, con quién y cuándo, desde el hecho de auditoría."""
    found = defaultdict(list)
    events = AuditEvent.objects.filter(
        event_type=EventType.SHEET_CHANGE, detail__action="motivo",
        detail__entry__in=list(entry_ids)).select_related("user").order_by("pk")
    for event in events:
        who = event.user.username if event.user else event.username
        verb = ACTIONS.get(event.detail.get("of"), "Cambiado")
        found[event.detail["entry"]].append(
            f"{verb} por {who} el {_when(event.occurred_at)} · motivo: "
            f"{event.detail.get('reason', '')}")
    return found


def _changes(entry_ids):
    found = defaultdict(list)
    for change in (Change.objects.filter(entry_id__in=list(entry_ids))
                   .select_related("user").order_by("at", "pk")):
        who = change.user.username if change.user else "—"
        found[change.entry_id].append(
            f"{change.get_action_display()} · {who} · {_when(change.at)}")
    return found


def _passages(sheet):
    ids = [r["reading"] for r in sheet.readings]
    rows = (Passage.objects.filter(reading_id__in=ids)
            .select_related("reading__document").order_by("reading__document_id", "order"))
    return [(p.pk, f"{p.reading.document.title} · pág. {p.page}: "
                   + " ".join(p.text.split())[:PASSAGE_LABEL]) for p in rows]


def _sheet_detail(user, offer, request):
    sheet = _latest_sheet(offer)
    base = {"offer": offer, "sheet": None, "back_url": tab_url(offer.procedure_id)}
    if sheet is None:
        return base
    reviewed = review.review_page(user, sheet.pk, channel=CHANNEL)
    page = reviewed.page
    open_id = request.GET.get("fila", "")
    open_id = int(open_id) if open_id.isdigit() else None
    ids = [r.entry.pk for r in page.rows]
    motives, changes = _motives(ids), _changes(ids)
    rows = []
    for row in page.rows:
        entry = row.entry
        icon, name = _entry_state(entry)
        rows.append({
            "entry": entry, "number": row.requirement.number,
            "category": row.requirement.get_category_display(), "item": row.item,
            "text": _excerpt(row.text), "presented": _presented(entry, row.item),
            "found": entry.outcome == EntryOutcome.ENCONTRADO,
            "fragments": row.fragments, "removed": row.removed, "icon": icon,
            "state_name": name, "proposed": entry.state == "propuesto",
            "motives": motives.get(entry.pk, []), "changes": changes.get(entry.pk, []),
            "active": entry.pk == open_id,
            "edit_url": tab_url(offer.procedure_id, offer.pk, entry.pk) + f"#fila-{entry.pk}"})
    active = any(r["active"] for r in rows)
    return {
        **base, "sheet": sheet, "rows": rows,
        "proposed": [r for r in rows if r["proposed"]],
        "missing": [r for r in rows if not r["found"]],
        "unread": page.unread, "newer": page.newer_version,
        "built_at": _when(sheet.built_at), "version": sheet.matrix_version.number,
        "can_confirm": reviewed.can_confirm,
        "passages": _passages(sheet) if active else [],
    }


def context(user, procedure, request):
    wanted = request.GET.get("ficha", "")
    offer = procedure.offers.filter(pk=wanted).first() if wanted.isdigit() else None
    return {"pid": procedure.pk, "aviso": unpack(request.GET.get(PARAM)),
            "detail": _sheet_detail(user, offer, request) if offer else None,
            "is_evaluator": user.commission_role == CommissionRole.EVALUATOR}


# --- Acciones ------------------------------------------------------------------------------------


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


def _entry(procedure, entry_id):
    try:
        return SheetEntry.objects.select_related("sheet__offer").get(
            pk=entry_id, sheet__offer__procedure=procedure)
    except SheetEntry.DoesNotExist:
        raise Http404("No hay una fila de la ficha con ese número en este procedimiento.")


def _fragment(procedure, fragment_id):
    try:
        return Fragment.objects.select_related("entry__sheet__offer").get(
            pk=fragment_id, entry__sheet__offer__procedure=procedure)
    except Fragment.DoesNotExist:
        raise Http404("No hay un fragmento con ese número en este procedimiento.")


def _motive(user, entry, fragment, action, motive):
    """El motivo de una corrección o de un quitar: el servicio de la pantalla vieja no lo
    guarda, así que queda en un hecho propio, con quién y cuándo."""
    audit.record(
        EventType.SHEET_CHANGE, outcome=Outcome.OK, channel=CHANNEL, user=user,
        detail={"action": "motivo", "of": action, "sheet": entry.sheet_id,
                "entry": entry.pk, "fragment": fragment.pk,
                "requirement": entry.requirement_id, "reason": motive})


@require_POST
def build(request, procedure_id, offer_id):
    procedure = _procedure(procedure_id)
    offer = _offer(procedure, offer_id)
    try:
        requested = sheets_service.request_sheet(request.user, offer, channel=CHANNEL)
    except sheets_service.SheetRefused as error:
        return back(procedure, offer, str(error), ok=False)
    return back(procedure, offer,
                f"Se pidió la ficha de la oferta {offer.number} sobre la versión "
                f"{requested.matrix_version.number} de la matriz. El sistema la arma ahora; "
                "cuando termine aparece acá.")


@require_POST
def confirm(request, procedure_id, offer_id):
    procedure = _procedure(procedure_id)
    offer = _offer(procedure, offer_id)
    ids = [i for i in request.POST.getlist("entry") if i.isdigit()]
    for entry_id in ids:
        if _entry(procedure, entry_id).sheet.offer_id != offer.pk:
            raise Http404("Esa fila no es de la ficha de esta oferta.")
    try:
        done = review.confirm(request.user, ids, channel=CHANNEL)
    except review.ReviewRefused as error:
        return back(procedure, offer, str(error), ok=False)
    count = len(done.entries)
    text = ("No había nada para confirmar." if not count else
            "Se confirmó 1 fila de la ficha." if count == 1 else
            f"Se confirmaron {count} filas de la ficha.")
    return back(procedure, offer, text)


@require_POST
def fragment_action(request, procedure_id, fragment_id, action):
    if action not in ("corregir", "quitar", "restituir"):
        raise Http404("Acción desconocida.")
    procedure = _procedure(procedure_id)
    fragment = _fragment(procedure, fragment_id)
    entry, offer = fragment.entry, fragment.entry.sheet.offer
    post = request.POST
    motive = " ".join(post.get("motive", "").split())
    if action in ACTIONS and not motive:
        return back(procedure, offer, "Escriba el motivo: es obligatorio y queda registrado.",
                    ok=False, entry=entry.pk)
    try:
        if action == "corregir":
            review.correct(request.user, fragment.pk, passage_id=post.get("passage") or None,
                           text=post.get("text", ""), channel=CHANNEL)
        elif action == "quitar":
            review.remove(request.user, fragment.pk, channel=CHANNEL)
        else:
            review.restore(request.user, fragment.pk, channel=CHANNEL)
    except review.ReviewRefused as error:
        return back(procedure, offer, str(error), ok=False, entry=entry.pk)
    if action in ACTIONS:
        _motive(request.user, entry, fragment, action, motive)
    text = {"corregir": "Se corrigió el fragmento. Quedó registrado el motivo, quién y cuándo; "
                        "la fila vuelve a quedar sin confirmar.",
            "quitar": "Se quitó el fragmento. No se borra: queda en la fila, con su motivo.",
            "restituir": "Se restituyó el fragmento; la fila vuelve a quedar sin confirmar."}
    return back(procedure, offer, text[action], entry=entry.pk)


@require_POST
def add(request, procedure_id, entry_id):
    procedure = _procedure(procedure_id)
    entry = _entry(procedure, entry_id)
    offer = entry.sheet.offer
    try:
        review.add(request.user, entry.pk, passage_id=request.POST.get("passage"),
                   text=request.POST.get("text", ""), channel=CHANNEL)
    except review.ReviewRefused as error:
        return back(procedure, offer, str(error), ok=False, entry=entry.pk)
    return back(procedure, offer, "Se agregó el fragmento a la fila; queda sin confirmar.",
                entry=entry.pk)


urlpatterns = [
    path("ofertas/<int:offer_id>/ficha/armar/", build, name="s3_ficha_armar"),
    path("ofertas/<int:offer_id>/ficha/confirmar/", confirm, name="s3_ficha_confirmar"),
    path("ofertas/ficha/fila/<int:entry_id>/agregar/", add, name="s3_ficha_agregar"),
    path("ofertas/ficha/fragmento/<int:fragment_id>/<str:action>/", fragment_action,
         name="s3_ficha_fragmento"),
]
