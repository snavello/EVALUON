"""Vistas de la aplicación por secciones (plan 014, «Rutas»): lista de expedientes, portada del
procedimiento, las cinco secciones, y los bloques que pide el sondeo (la barra y la ventana del
proceso). Solo traducen y llaman a `sections_for`: no tienen formularios de decisión (P3)."""

from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit.models import Channel
from evaluon.journey import memo
from evaluon.journey.sections import sections_for
from evaluon.journey.views import inicio
from evaluon.journey.window import window_for
from evaluon.tenders.models import Procedure

OPERATION = "evaluon.journey.views.portada.lista"
ROLE_LABELS = {CommissionRole.OPERATOR: "Operador de la Comisión",
               CommissionRole.EVALUATOR: "Evaluador de la Comisión"}
DROPDOWN_LIMIT = 25


def overview_of(request, procedure_id):
    """Las cinco secciones del procedimiento. 404 si no existe; `RoleRejected` (403) sin rol."""
    try:
        procedure = Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")
    return sections_for(request.user, procedure, channel=Channel.SCREEN)


def shell(request, overview, active=""):
    """Lo que necesita el encabezado y la barra en toda pantalla del procedimiento."""
    procedure = overview.procedure
    return {
        "overview": overview, "procedure": procedure, "active": active,
        "procedures": Procedure.objects.order_by("-created_at", "-pk")[:DROPDOWN_LIMIT],
        "role_label": ROLE_LABELS.get(request.user.commission_role, ""),
        "portal_link": procedure.portal_links.order_by("-pk").first(),
        "bar_url": reverse("expedientes:barra", args=[procedure.pk]),
        "login_url": reverse("accounts:login"),
    }


@require_GET
def lista(request):
    require_commission_role(request.user, CommissionRole.OPERATOR, operation=OPERATION,
                            channel=Channel.SCREEN)
    rows = [sections_for(request.user, p, channel=Channel.SCREEN)
            for p in Procedure.objects.order_by("-created_at", "-pk")]
    return render(request, "journey/expedientes.html", {"rows": rows})


@require_GET
@memo.scoped
def portada(request, procedure_id):
    overview = overview_of(request, procedure_id)
    context = shell(request, overview)
    context.update({
        "window": window_for(overview.procedure),
        "window_url": reverse("expedientes:ventana", args=[procedure_id]),
        "pending_items": [(s, i) for s in overview.sections for i in s.pending_items],
        "suggestion_items": [(s, i) for s in overview.sections for i in s.suggestion_items],
    })
    return inicio.remember(render(request, "journey/portada.html", context), request.user,
                           procedure_id)


@require_GET
@memo.scoped
def seccion(request, procedure_id, key):
    overview = overview_of(request, procedure_id)
    section = overview.get(key)
    blocks = [{"key": tema.KEY, "partial": tema.PARTIAL,
               "t": tema.context(request.user, overview.procedure, request)}
              for tema in section.temas]
    context = shell(request, overview, active=key)
    context.update({
        "section": section, "blocks": blocks,
        "pending_rows": [(section, item) for item in section.pending_items],
        "suggestion_rows": [(section, item) for item in section.suggestion_items],
    })
    return inicio.remember(render(request, "journey/seccion.html", context), request.user,
                           procedure_id)


@require_GET
@memo.scoped
def barra(request, procedure_id):
    """Solo la barra de las cinco secciones, lo que pide el sondeo (ADR-0045). Sin `base.html`:
    así no consume el aviso de fin de pedidos."""
    overview = overview_of(request, procedure_id)
    active = request.GET.get("activa", "")
    response = render(request, "journey/_barra.html", {"overview": overview, "active": active,
                                                       "bar_url": request.path})
    response["Cache-Control"] = "no-store"
    return response


@require_GET
@memo.scoped
def ventana(request, procedure_id):
    """Solo la ventana del proceso, para el sondeo de la portada."""
    overview = overview_of(request, procedure_id)
    response = render(request, "journey/_window.html",
                      {"window": window_for(overview.procedure)})
    response["Cache-Control"] = "no-store"
    return response
