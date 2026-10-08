"""Tema s1_portal: explorador y cargador del Portal (REQ-076, REQ-079, REQ-097; plan 014, T-195).

Se pega el enlace del proceso y el sistema lee el Portal; lo que encontró se ve agrupado (datos,
renglones, cronograma y garantías, documentos y ofertas), cada grupo con la sección donde queda,
y una persona de la Comisión lo aprueba ítem por ítem, grupo por grupo o todo junto. Las
novedades de la revisión periódica (`origin = revision`) quedan como pendientes de la sección y
de la portada, y no se cargan sin aprobación. «Revisar ahora» y «Dejar de seguir» están a la vista.

Este tema no cambia las reglas de la 012: cada acción llama a los servicios de
`evaluon.portal.services` (`links.register_link`, `approval.decide`, `approval.approve_all`,
`schedule.review_now`, `links.stop_following`), así que dejan el mismo cambio, el mismo rol y el
mismo hecho de auditoría que las pantallas viejas. Solo un evaluador aprueba datos, renglones y
ofertas; el operador, los documentos. Leer no aprueba nada (P3).

Las acciones vuelven a la pestaña Procedimiento con el resultado de cada ítem y la sección donde
quedó, con un enlace a ella. El mensaje viaja firmado en la dirección (`?portal=`), sin guardar
nada en la sesión, y vale cinco minutos. Las fechas se muestran en hora local. El alta sin
procedimiento (`expedientes/nuevo/`) usa estas mismas funciones (ver `journey/views/nuevo.py`).
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from django.core import signing
from django.http import Http404
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from evaluon.accounts.models import CommissionRole
from evaluon.audit.models import Channel
from evaluon.journey.sections import SECTIONS
from evaluon.journey.sections.base import Item, TemaStatus
from evaluon.journey.temas import s1_datos
from evaluon.journey.window import plain_reason
from evaluon.portal.importers import discover
from evaluon.portal.models import ItemKind, ItemState, Origin, PortalItem, PortalLink
from evaluon.portal.services import approval, links, schedule
from evaluon.tenders.models import PORTAL_JOB_KINDS, Job, JobStatus, Procedure
from evaluon.tenders.services import procedures

KEY = "s1_portal"
SECTION = "procedimiento"
PARTIAL = "journey/temas/s1_portal.html"

SALT = "journey.s1.portal"
MAX_AGE = 300
ANCHOR = "#s1-portal"
CHANNEL = Channel.SCREEN

LABELS = {module.KEY: module.LABEL for module in SECTIONS}
GROUPS = (  # (clave del grupo, título, tipo de ítem)
    ("datos", "Datos del procedimiento", ItemKind.PROCEDIMIENTO),
    ("renglones", "Renglones", ItemKind.RENGLONES),
    ("documentos", "Documentos publicados", ItemKind.DOCUMENTO),
    ("ofertas", "Ofertas del acta de apertura", ItemKind.OFERTA),
)
KIND_OF_GROUP = {key: kind for key, _, kind in GROUPS}
STATE_ICONS = {
    ItemState.CARGADO: ("cumple", "Cargado"),
    ItemState.APROBADO: ("cumple", "Aprobado: queda como archivo del Portal"),
    ItemState.RECHAZADO: ("nocumple", "Rechazado"),
    ItemState.FALLIDO: ("nocumple", "No se pudo cargar"),
    ItemState.PROPUESTO: ("nodet", "Sin aprobar: no se cargó"),
}
JOB_TEXT = {
    JobStatus.QUEUED: "En espera de lectura",
    JobStatus.RUNNING: "Leyendo el Portal",
    JobStatus.DONE: "Terminada",
}
OPEN_JOBS = (JobStatus.QUEUED, JobStatus.RUNNING)
CIRCULAR_CHOICES = (("circular_modificatoria", "Modificatoria"),
                    ("circular_aclaratoria", "Aclaratoria"))


def can_load(user):
    return user.commission_role in (CommissionRole.OPERATOR, CommissionRole.EVALUATOR)


def can_decide(user, kind):
    """El operador decide los documentos; el evaluador, todo."""
    return (user.commission_role == CommissionRole.EVALUATOR
            or (user.commission_role == CommissionRole.OPERATOR
                and approval.required_role(kind) == CommissionRole.OPERATOR))


# --- A qué sección va cada cosa -------------------------------------------------------------------


def destination(item):
    """La sección donde queda un ítem aprobado: pliego y anexos a la 2, circulares y ofertas a la 3,
    el dictamen a la 4; el resto (datos, renglones, actas y actos) queda en la 1."""
    if item.kind == ItemKind.OFERTA:
        return "ofertas"
    if item.kind == ItemKind.DOCUMENTO:
        return {"pliego": "pliego", "anexo": "pliego", "circular": "ofertas",
                "dictamen": "evaluacion"}.get(item.payload.get("clase"), "procedimiento")
    return "procedimiento"


def destination_label(item):
    label = LABELS[destination(item)]
    if item.kind == ItemKind.DOCUMENTO and item.payload.get("clase") in ("acta", "acto"):
        return f"{label} (archivo del Portal)"
    return label


def title_of(item):
    """Cómo se nombra un ítem en los mensajes."""
    data = item.payload
    if item.kind == ItemKind.PROCEDIMIENTO:
        return f"Datos del procedimiento {data.get('numero', '')}".strip()
    if item.kind == ItemKind.RENGLONES:
        return "Renglones"
    if item.kind == ItemKind.DOCUMENTO:
        return data.get("nombre") or item.key
    return f"Oferta de {data.get('oferente', item.key)}"


def _moment(value):
    """Fecha y hora en hora local, no la de la base en UTC."""
    return f"{timezone.localtime(value):%d/%m/%Y %H:%M}"


# --- El mensaje de lo hecho -----------------------------------------------------------------------


def pack(entries):
    return signing.dumps(entries, salt=SALT, compress=True)


def unpack(value):
    """Los mensajes firmados de la dirección, o `None` si faltan, están alterados o vencieron."""
    if not value:
        return None
    try:
        data = signing.loads(value, salt=SALT, max_age=MAX_AGE)
    except signing.BadSignature:
        return None
    return [{"ok": bool(e.get("ok")), "text": str(e.get("t", "")), "go": str(e.get("g", ""))}
            for e in data if isinstance(e, dict)]


def entry(text, ok=True, go=""):
    return {"ok": ok, "t": text, "g": go}


def entries_of(results):
    """Un mensaje por ítem decidido, con la sección donde quedó."""
    out = []
    for r in results:
        name = title_of(r.item)
        if r.result == approval.LOADED:
            out.append(entry(f"{name}: cargado. Quedó en «{destination_label(r.item)}».",
                             go=destination(r.item)))
            if r.reason:
                out.append(entry(r.reason))
        elif r.result == approval.KEPT_AS_FILE:
            out.append(entry(f"{name}: aprobado. Queda como archivo del Portal, sin leerse.",
                             go=destination(r.item)))
        elif r.result in (approval.PENDING, approval.FAILED):
            out.append(entry(f"{name}: no se cargó. {r.reason}", ok=False))
        else:
            out.append(entry(f"{name}: ya estaba decidido.", ok=False))
    return out


def back(procedure, entries):
    """Vuelve a la pestaña del procedimiento con el resultado."""
    url = reverse("expedientes:procedimiento", args=[procedure.pk])
    return redirect(f"{url}?portal={pack(entries)}{ANCHOR}")


# --- Las acciones, con los servicios de la 012 -----------------------------------------------------


def confirmations_of(post):
    """`({id del ítem: {...}}, [valores inválidos])` de los campos `fecha_<id>` (fecha de
    autorización del procedimiento), `emision_<id>` (fecha de una circular) y `tipo_<id>` (tipo de
    una circular). Los campos vacíos se ignoran."""
    confirmations, invalid = {}, []
    for name, value in post.items():
        prefix, _, item_id = name.partition("_")
        value = value.strip()
        if prefix not in ("fecha", "emision", "tipo") or not item_id.isdigit() or not value:
            continue
        found = confirmations.setdefault(int(item_id), {})
        if prefix == "tipo":
            if value not in dict(CIRCULAR_CHOICES):
                invalid.append(value)
            found["circular_kind"] = value
            continue
        try:
            found["authorization_date" if prefix == "fecha" else "issued_on"] = (
                date.fromisoformat(value))
        except ValueError:
            invalid.append(value)
    return confirmations, invalid


def decide_from_post(user, link, post):
    """Aprueba lo que pidió el botón apretado (`aprobar` = `item:<id>`, `grupo:<clave>` o
    `todo`) con los servicios de la 012. Devuelve la lista de mensajes. Sin el rol que pide algún
    ítem, el servicio levanta `RoleRejected` (403) con el rechazo registrado y no decide ninguno."""
    confirmations, invalid = confirmations_of(post)
    if invalid:
        return [entry("Una fecha o un tipo elegido no es válido: no se aprobó nada.", ok=False)]
    action = post.get("aprobar", "")
    if action == "todo":
        results = approval.approve_all(user, link.pk, confirmations=confirmations,
                                       channel=CHANNEL)
    else:
        pending = PortalItem.objects.filter(proposal__link=link, state=ItemState.PROPUESTO)
        what, _, value = action.partition(":")
        if what == "item" and value.isdigit():
            ids = list(pending.filter(pk=int(value)).values_list("pk", flat=True))
        elif what == "grupo" and value in KIND_OF_GROUP:
            ids = list(pending.filter(kind=KIND_OF_GROUP[value]).values_list("pk", flat=True))
        else:
            return [entry("Elija qué aprobar.", ok=False)]
        if not ids:
            return [entry("No hay nada pendiente ahí: ya se decidió.", ok=False)]
        results = approval.decide(user, ids, approval.APPROVE, confirmations=confirmations,
                                  channel=CHANNEL)
    if not results:
        return [entry("No había nada pendiente de aprobar.", ok=False)]
    return entries_of(results)


def review_entries(user, link):
    _, created = schedule.review_now(user, link.pk, channel=CHANNEL)
    if created:
        return [entry("Se pidió una revisión del Portal: el sistema la hace en un momento. "
                      "Lo que encuentre queda como pendiente hasta que se apruebe.")]
    return [entry("Ya hay una lectura del Portal en curso: espere a que termine.", ok=False)]


def stop_entries(user, link):
    links.stop_following(user, link.pk, channel=CHANNEL)
    return [entry("Se dejó de seguir el proceso: el sistema ya no lo revisa. Lo ya cargado "
                  "queda como está.")]


# --- Lo que cuenta la sección ----------------------------------------------------------------------


def procedure_links(procedure):
    return list(procedure.portal_links.order_by("created_at", "pk"))


def _counts(procedure):
    """`(propuesta, novedades, ya contadas por la etapa)`: los ítems sin decidir de los enlaces del
    procedimiento, separados por el origen de su propuesta."""
    items = list(PortalItem.objects.filter(
        proposal__link__procedure=procedure, state=ItemState.PROPUESTO)
        .values_list("proposal__origin", "proposal_id", "proposal__link_id"))
    news = sum(1 for origin, _, _ in items if origin == Origin.REVISION)
    latest = {}
    for link in procedure_links(procedure):
        proposal = link.proposals.order_by("-exploration", "-pk").first()
        if proposal is not None:
            latest[link.pk] = proposal.pk
    counted = sum(1 for _, proposal_id, link_id in items if latest.get(link_id) == proposal_id)
    return len(items) - news, news, counted


def status(user, procedure):
    """Lo sin aprobar del Portal, en dos renglones (la propuesta y las novedades) que reemplazan al
    genérico de la etapa. La etapa del Portal ya cuenta los ítems de la última propuesta de cada
    enlace; acá se suman solo los que ella no cuenta, para que el total de la sección sea exacto."""
    proposal, news, counted = _counts(procedure)
    base = reverse("expedientes:procedimiento", args=[procedure.pk])
    pending_items = []
    if proposal:
        pending_items.append(Item(f"Propuesta del Portal: {proposal} sin aprobar",
                                  f"{base}#s1-propuesta", proposal, "Aprobar"))
    if news:
        pending_items.append(Item(f"Novedades del Portal: {news} sin aprobar",
                                  f"{base}#s1-novedades", news, "Aprobar"))
    return TemaStatus(pending=proposal + news - counted, pending_items=tuple(pending_items),
                      detailed_stages=("portal",))


# --- Lo que muestra el tema -------------------------------------------------------------------------


def _damaged(item, name):
    return name in (item.damaged_fields or [])


def _number(value):
    try:
        return s1_datos._number(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return str(value)


def _money(value):
    try:
        return s1_datos._money(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return "No consta"


def _authorization(item, row, user):
    """La fecha de autorización: el Portal no la muestra, la confirma quien aprueba."""
    data = item.payload.get("fecha_autorizacion") or {}
    candidate = data.get("candidata") or ""
    regimes = []
    if candidate:
        try:
            regimes = [r["name"] for r in procedures.regime_for(date.fromisoformat(candidate))]
        except ValueError:
            candidate = ""
    ask = (row.action == "crear" and item.state == ItemState.PROPUESTO
           and can_decide(user, item.kind)
           and discover()[item.kind].needs_authorization_date(item))
    return {"candidate": candidate, "origin": data.get("origen", ""), "regimes": regimes,
            "ask": bool(ask)}


def _item_view(user, row):
    item = row.item
    data = item.payload
    icon, name = STATE_ICONS[item.state]
    view = {
        "pk": item.pk, "kind": item.kind, "state": item.state, "icon": icon, "icon_name": name,
        "pending": item.state == ItemState.PROPUESTO, "can_decide": can_decide(user, item.kind),
        "changed": row.changed, "failure": item.failure,
        "destination": destination_label(item), "title": title_of(item),
        "decided": (f"{item.decided_by.username} · {_moment(item.decided_at)}"
                    if item.decided_by_id and item.decided_at else ""),
        "origin_at": _moment(item.proposal.created_at), "damaged": bool(item.damaged_fields),
        "published": f"{timezone.localtime(item.proposal.created_at):%d/%m/%Y}",
    }
    if item.kind == ItemKind.PROCEDIMIENTO:
        view["rows"] = [
            ("Número", data.get("numero", ""), _damaged(item, "numero")),
            ("Expediente", data.get("expediente", ""), _damaged(item, "expediente")),
            ("Tipo", data.get("tipo", ""), _damaged(item, "tipo")),
            ("Objeto", data.get("objeto", ""), _damaged(item, "objeto")),
            ("Unidad operativa", data.get("unidad_operativa", ""),
             _damaged(item, "unidad_operativa")),
            ("Encuadre legal", data.get("encuadre_legal", ""), _damaged(item, "encuadre_legal")),
        ]
        view["action"] = row.action
        view["authorization"] = _authorization(item, row, user)
        view["schedule"] = s1_datos._schedule(SimpleNamespace(schedule=data.get("cronograma")))
        view["guarantees"] = s1_datos._guarantees(
            SimpleNamespace(guarantees=data.get("garantias")))
        view["damaged_schedule"] = _damaged(item, "cronograma")
        view["damaged_guarantees"] = _damaged(item, "garantias")
    elif item.kind == ItemKind.RENGLONES:
        view["lines"] = [{"number": line.get("numero"), "description": line.get("descripcion", ""),
                          "quantity": " ".join(p for p in (
                              _number(line["cantidad"]) if line.get("cantidad") is not None
                              else "No consta", line.get("unidad", "")) if p),
                          "damaged": bool(line.get("danado"))}
                         for line in data.get("renglones", [])]
    elif item.kind == ItemKind.DOCUMENTO:
        file = data.get("archivo") or {}
        circular = data.get("clase") == "circular" and item.state == ItemState.PROPUESTO
        view.update(
            date="", class_label=data.get("clase", ""),
            file=" · ".join(p for p in (file.get("nombre", ""), file.get("formato", "")) if p),
            ask_kind=circular and not data.get("tipo_circular"),
            ask_date=circular and not data.get("fecha"),
            portal_kind=data.get("tipo_portal") or "",
            loads=data.get("se_carga_como") == "documento")
        if data.get("fecha"):
            try:
                view["date"] = f"{date.fromisoformat(data['fecha']):%d/%m/%Y}"
                view["published"] = view["date"]
            except ValueError:
                view["date"] = str(data["fecha"])
    else:
        match = row.match
        view.update(
            bidder=data.get("oferente", ""), cuit=data.get("cuit", ""),
            total=_money(data["total"]) if data.get("total") is not None else "No consta",
            guarantees=[" · ".join(p for p in (
                g.get("tipo") or "", g.get("forma") or "",
                _money(g["monto"]) if g.get("monto") is not None else "") if p)
                for g in data.get("garantias", [])],
            notes=data.get("anomalias", []),
            match=match.offer.bidder if match and getattr(match, "offer", None) else "",
            match_note=getattr(match, "note", "") if match else "")
    return view


def proposal_view(user, link):
    """La propuesta de un enlace agrupada, con sus novedades aparte (`origin = revision`)."""
    page = approval.proposal_page(user, link.pk, channel=CHANNEL)
    groups = []
    for key, title, kind in GROUPS:
        views = [_item_view(user, row) for row in page.rows.get(kind, [])
                 if row.item.proposal.origin != Origin.REVISION]
        if views:
            groups.append({"key": key, "title": title, "items": views,
                           "pending": sum(1 for v in views if v["pending"]),
                           "can_decide": can_decide(user, kind),
                           "single": len(views) == 1})
    news = [_item_view(user, row) for group in page.rows.values() for row in group
            if row.item.proposal.origin == Origin.REVISION
            and row.item.state == ItemState.PROPUESTO]
    pending = sum(g["pending"] for g in groups)
    return {"groups": groups, "news": news, "anomalies": page.anomalies, "pending": pending,
            "total": sum(len(g["items"]) for g in groups),
            "done": sum(len(g["items"]) for g in groups) - pending,
            "can_approve_all": page.can_approve_all}


def job_view(link):
    """El último pedido del Portal del enlace, en lenguaje llano."""
    job = (Job.objects.filter(kind__in=PORTAL_JOB_KINDS, target_id=link.pk)
           .order_by("-id").first())
    if job is None:
        return {"text": "Sin lectura todavía", "open": False, "failed": False, "at": ""}
    failed = job.status == JobStatus.FAILED
    when = job.finished_at or job.started_at or job.requested_at
    return {"text": (f"No se pudo leer: {plain_reason(job.error)}" if failed
                     else JOB_TEXT.get(job.status, "En espera de lectura")),
            "open": job.status in OPEN_JOBS, "failed": failed,
            "at": _moment(when) if when else ""}


def action_urls(link):
    """Las direcciones de las acciones: las del procedimiento si el enlace ya lo tiene; si no, las
    del alta (`expedientes/nuevo/<enlace>/`)."""
    if link.procedure_id:
        args = [link.procedure_id, link.pk]
        return {"decide": reverse("expedientes:s1_portal_decidir", args=args),
                "review": reverse("expedientes:s1_portal_revisar", args=args),
                "stop": reverse("expedientes:s1_portal_dejar", args=args)}
    return {"decide": reverse("expedientes:nuevo_decidir", args=[link.pk]),
            "review": reverse("expedientes:nuevo_revisar", args=[link.pk]),
            "stop": reverse("expedientes:nuevo_dejar", args=[link.pk])}


def link_view(user, link):
    return {"link": link, "job": job_view(link), "proposal": proposal_view(user, link),
            "last_review": f"{link.last_review_on:%d/%m/%Y}" if link.last_review_on else "",
            "urls": action_urls(link), "can_load": can_load(user),
            "can_approve_all": user.commission_role == CommissionRole.EVALUATOR}


# --- Rutas de acción (vuelven a la pestaña) -----------------------------------------------------------


def _link(procedure_id, link_id):
    try:
        procedure = Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")
    try:
        return procedure, PortalLink.objects.get(pk=link_id, procedure=procedure)
    except PortalLink.DoesNotExist:
        raise Http404("No hay un proceso del Portal con ese número en este procedimiento.")


@require_POST
def decide(request, procedure_id, link_id):
    procedure, link = _link(procedure_id, link_id)
    return back(procedure, decide_from_post(request.user, link, request.POST))


@require_POST
def review(request, procedure_id, link_id):
    procedure, link = _link(procedure_id, link_id)
    return back(procedure, review_entries(request.user, link))


@require_POST
def stop(request, procedure_id, link_id):
    procedure, link = _link(procedure_id, link_id)
    return back(procedure, stop_entries(request.user, link))


urlpatterns = [
    path("procedimiento/portal/<int:link_id>/decidir/", decide, name="s1_portal_decidir"),
    path("procedimiento/portal/<int:link_id>/revisar/", review, name="s1_portal_revisar"),
    path("procedimiento/portal/<int:link_id>/dejar-de-seguir/", stop, name="s1_portal_dejar"),
]


def messages_for(value, procedure):
    """Los mensajes firmados de la dirección, cada uno con el enlace a la sección donde quedó lo
    cargado; `None` si no hay."""
    found = unpack(value)
    if found is None:
        return None
    for message in found:
        key = message.pop("go")
        message["url"] = (reverse(f"expedientes:{key}", args=[procedure.pk])
                          if key in LABELS and procedure is not None else "")
        message["label"] = LABELS.get(key, "")
    return found


def context(user, procedure, request):
    views = [link_view(user, link) for link in procedure_links(procedure)]
    news = [(v, item) for v in views for item in v["proposal"]["news"]]
    return {
        "pid": procedure.pk, "links": views, "news": news, "news_count": len(news),
        "can_load": can_load(user), "messages": messages_for(request.GET.get("portal"), procedure),
        "new_url": reverse("expedientes:nuevo"), "confirm_kinds": CIRCULAR_CHOICES,
    }
