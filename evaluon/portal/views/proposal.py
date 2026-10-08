"""Página "Propuesta": los ítems de un enlace con su origen, su marca de texto dañado y los
botones para aprobar o rechazar, por ítem o todo (REQ-048; plan 012, "Pantalla"; T-141).

Cada tipo de ítem tiene su parcial en `templates/portal/items/<tipo>.html`; si todavía no hay
uno (documentos y ofertas llegan en T-142 y T-143), se usa el genérico. La fecha de
autorización del procedimiento la confirma quien aprueba en el mismo formulario.
"""

from datetime import date

from django.http import Http404
from django.shortcuts import render
from django.template.loader import select_template
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from evaluon.audit.models import Channel
from evaluon.journey.legacy import section_url, to_section
from evaluon.portal.models import PortalItem, PortalLink
from evaluon.portal.services import approval as services

TEMPLATE = "portal/proposal.html"
CIRCULAR_KINDS = ("circular_modificatoria", "circular_aclaratoria")
ALL = "aprobar_todo"


def _page(request, link_id, results=None, error=""):
    try:
        page = services.proposal_page(request.user, link_id, channel=Channel.SCREEN)
    except PortalLink.DoesNotExist:
        raise Http404("No hay un enlace con ese número.")
    for group in page.rows.values():
        for row in group:
            row.template = select_template(
                [f"portal/items/{row.item.kind}.html", "portal/items/_generico.html"]
            ).template.name
    groups = [(kind, services.ItemKind(kind).label, group) for kind, group in page.rows.items()]
    return render(request, TEMPLATE, {"page": page, "groups": groups,
                                      "results": results or [], "error": error})


def _link_section(request, link_id):
    """Con procedimiento creado, su pestaña Procedimiento; si no, el alta con ese proceso."""
    link = PortalLink.objects.filter(pk=link_id).first()
    if link is None:
        raise Http404("No hay un proceso del Portal con ese número.")
    if link.procedure_id:
        return section_url("procedimiento", link.procedure_id)
    return reverse("expedientes:nuevo_enlace", args=[link.pk])


@to_section(_link_section)
@require_GET
def proposal(request, link_id):
    return _page(request, link_id)


def _confirmations(post):
    """Lo que confirma quien aprueba, por ítem: `fecha_<id>` (fecha de autorización del
    procedimiento), `emision_<id>` (fecha de una circular) y `tipo_<id>` (tipo de una
    circular). Devuelve `({id: {...}}, [lo que no es válido])`."""
    confirmations, invalid = {}, []
    for name, value in post.items():
        prefix, _, item_id = name.partition("_")
        if prefix not in ("fecha", "emision", "tipo") or not item_id.isdigit() or not value.strip():
            continue
        entry = confirmations.setdefault(int(item_id), {})
        value = value.strip()
        if prefix == "tipo":
            if value not in CIRCULAR_KINDS:
                invalid.append(value)
            entry["circular_kind"] = value
            continue
        try:
            entry["authorization_date" if prefix == "fecha" else "issued_on"] = (
                date.fromisoformat(value))
        except ValueError:
            invalid.append(value)
    return confirmations, invalid


@require_POST
def decide(request, link_id):
    """Aprobar o rechazar los ítems tildados, o aprobar todo."""
    confirmations, invalid = _confirmations(request.POST)
    if invalid:
        return _page(request, link_id, error="Una fecha o un tipo elegido no es válido.")
    action = request.POST.get("decision", "")
    try:
        if action == ALL:
            results = services.approve_all(request.user, link_id,
                                           confirmations=confirmations, channel=Channel.SCREEN)
        elif action in (services.APPROVE, services.REJECT):
            ids = [int(i) for i in request.POST.getlist("item") if i.isdigit()]
            if not ids:
                return _page(request, link_id, error="Elija al menos un ítem.")
            results = services.decide(request.user, ids, action,
                                      confirmations=confirmations, channel=Channel.SCREEN)
        else:
            return _page(request, link_id, error="Elija qué hacer con los ítems.")
    except PortalItem.DoesNotExist:
        raise Http404("No hay un ítem con ese número.")
    return _page(request, link_id, results=results)
