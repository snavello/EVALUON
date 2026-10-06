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
from django.views.decorators.http import require_GET, require_POST

from evaluon.audit.models import Channel
from evaluon.portal.models import PortalItem, PortalLink
from evaluon.portal.services import approval as services

TEMPLATE = "portal/proposal.html"
DATE_PREFIX = "fecha_"
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


@require_GET
def proposal(request, link_id):
    return _page(request, link_id)


def _confirmations(post):
    """`{id del ítem: {"authorization_date": fecha}}` de los campos `fecha_<id>` con fecha."""
    confirmations, invalid = {}, []
    for name, value in post.items():
        if not name.startswith(DATE_PREFIX) or not value.strip():
            continue
        item_id = name[len(DATE_PREFIX):]
        try:
            confirmations[int(item_id)] = {"authorization_date": date.fromisoformat(value.strip())}
        except ValueError:
            invalid.append(value)
    return confirmations, invalid


@require_POST
def decide(request, link_id):
    """Aprobar o rechazar los ítems tildados, o aprobar todo."""
    confirmations, invalid = _confirmations(request.POST)
    if invalid:
        return _page(request, link_id, error="La fecha de autorización no es válida.")
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
