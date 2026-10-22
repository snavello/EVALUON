"""Vistas de la aplicación por secciones (plan 014, «Rutas»): lista de expedientes, portada del
procedimiento, las cinco secciones, y los bloques que pide el sondeo (la barra y la ventana del
proceso). Solo traducen y llaman a `sections_for`: no tienen formularios de decisión (P3)."""

import re
from functools import wraps

from django.http import Http404
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_GET

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role, viewing
from evaluon.audit.models import Channel
from evaluon.journey import memo
from evaluon.journey.sections import sections_for
from evaluon.journey.stages import is_viewer
from evaluon.journey.tablero.tiles import build_board
from evaluon.journey.views import inicio
from evaluon.journey.window import window_for
from evaluon.tenders.models import Procedure

OPERATION = "evaluon.journey.views.portada.lista"
ROLE_LABELS = {CommissionRole.NONE: "Solo lectura",
               CommissionRole.OPERATOR: "Operador de la Comisión",
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


# Un formulario de acción (POST), salvo el de salir. Las acciones del usuario de lectura no se
# dibujan: el servicio igual lo rechazaría (403), pero un botón que no funciona confunde.
_ACTION_FORM = re.compile(
    r'<form(?=[\s>])(?=[^>]*method="post")(?![^>]*logout-form)[^>]*>.*?</form>', re.S | re.I)


# Los enlaces «Subir …» llevan a un formulario que el usuario de lectura no tiene (D-3 de T-227).
_UPLOAD_LINK = re.compile(r"<a\s[^>]*>\s*Subir[^<]*</a>", re.S | re.I)


def without_actions(response):
    """La respuesta HTML sin los formularios de acción ni los enlaces para subir."""
    if response.status_code == 200 and "text/html" in response.get("Content-Type", ""):
        html = _ACTION_FORM.sub("", response.content.decode())
        response.content = _UPLOAD_LINK.sub("", html)
    return response


def reading(view):
    """La vista solo lee: el usuario de lectura la ve entera y sin acciones."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        with viewing(request.user):
            response = view(request, *args, **kwargs)
        if not request.user.commission_role:
            response = without_actions(response)
        return response
    return wrapper


@require_GET
def lista(request):
    if not is_viewer(request.user):
        require_commission_role(request.user, CommissionRole.OPERATOR, operation=OPERATION,
                                channel=Channel.SCREEN)
    rows = [sections_for(request.user, p, channel=Channel.SCREEN)
            for p in Procedure.objects.order_by("-created_at", "-pk")]
    return render(request, "journey/expedientes.html", {"rows": rows})


@require_GET
@memo.scoped
@reading
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
@reading
def seccion(request, procedure_id, key):
    overview = overview_of(request, procedure_id)
    section = overview.get(key)
    contexts = {tema.KEY: tema.context(request.user, overview.procedure, request)
                for tema in section.temas}
    context = shell(request, overview, active=key)
    context.update({
        "section": section,
        "pending_rows": [(section, item) for item in section.pending_items],
        "suggestion_rows": [(section, item) for item in section.suggestion_items],
    })
    board = build_board(section, request.user, overview.procedure, contexts, request)
    if board is None:
        # Ningún tema declara mosaicos: la sección se muestra como antes, con sus parciales.
        context["blocks"] = [{"key": tema.KEY, "partial": tema.PARTIAL, "t": contexts[tema.KEY]}
                             for tema in section.temas]
    else:
        # Cada detalle se dibuja acá, con el contexto completo de la página (los parciales usan
        # `procedure`, `section` y el pedido), y llega a la plantilla como HTML.
        context.update({
            "board": board.tiles, "abre": board.abre,
            "details": [{"id": d.id, "title": d.title, "html": render_to_string(
                d.template, {**context, **d.context}, request=request)} for d in board.details],
            "blocks": [{"key": tema.KEY, "partial": tema.PARTIAL, "t": contexts[tema.KEY]}
                       for tema in board.leftover],
        })
    return inicio.remember(render(request, "journey/seccion.html", context), request.user,
                           procedure_id)


@require_GET
@memo.scoped
@reading
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
@reading
def ventana(request, procedure_id):
    """Solo la ventana del proceso, para el sondeo de la portada."""
    overview = overview_of(request, procedure_id)
    response = render(request, "journey/_window.html",
                      {"window": window_for(overview.procedure)})
    response["Cache-Control"] = "no-store"
    return response
