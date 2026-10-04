"""Acciones de revisión de la matriz y el historial de un requisito (REQ-026, REQ-028;
plan 003, "Revisión, validación y versiones" y "Pantalla"; ADR-0005; T-079).

Cada acción es un formulario de la página de la matriz que se envía por POST a su ruta,
llama a `services.review` y vuelve a la matriz, en el requisito tocado. Un cambio rechazado
(fragmento que no está en el tramo, segunda fila técnica, versión validada) vuelve a
mostrar la matriz con el motivo, sin cambiar nada. Sin el rol que la acción pide, "acceso
denegado" (403) y el rechazo queda registrado. La vista no guarda nada en la sesión.
"""

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from evaluon.audit.models import Channel
from evaluon.tenders.models import MatrixVersion, PendingItem, Requirement
from evaluon.tenders.services import matrix_page as pages
from evaluon.tenders.services import review as service

MATRIX_TEMPLATE = "tenders/matrix.html"
HISTORY_TEMPLATE = "tenders/history.html"


def _back(version_id, requirement=None):
    url = reverse("tenders:matrix", args=[version_id])
    return redirect(f"{url}#requisito-{requirement.number}" if requirement else url)


def _refused(request, version_id, error):
    page = pages.matrix_page(request.user, version_id, channel=Channel.SCREEN)
    return render(request, MATRIX_TEMPLATE, {"page": page, "review_error": str(error),
                                             "review_error_field": error.field},
                  status=400)


def _version_of_requirement(requirement_id):
    try:
        return Requirement.objects.values_list("version_id", flat=True).get(
            pk=requirement_id)
    except Requirement.DoesNotExist:
        raise Http404("No hay un requisito con ese número.")


def _act(request, version_id, action):
    try:
        done = action()
    except service.ReviewRefused as error:
        return _refused(request, version_id, error)
    return _back(version_id, done.requirements[0] if len(done.requirements) == 1 else None)


@require_POST
def confirm(request, version_id):
    if not MatrixVersion.objects.filter(pk=version_id).exists():
        raise Http404("No hay una versión de la matriz con ese número.")
    ids = [i for i in request.POST.getlist("requirement") if i.isdigit()]
    return _act(request, version_id, lambda: service.confirm(
        request.user, ids, channel=Channel.SCREEN))


@require_POST
def correct(request, requirement_id):
    version_id = _version_of_requirement(requirement_id)
    post = request.POST
    return _act(request, version_id, lambda: service.correct(
        request.user, requirement_id,
        category=post.get("category") or None,
        items=post.get("items") if "items" in post else None,
        segment=post.get("segment") or None,
        quote=post.get("quote") or None,
        add_segments=post.getlist("add_segment"),
        remove_quotes=post.getlist("remove_quote"),
        channel=Channel.SCREEN))


@require_POST
def remove(request, requirement_id):
    version_id = _version_of_requirement(requirement_id)
    return _act(request, version_id, lambda: service.remove(
        request.user, requirement_id, channel=Channel.SCREEN))


@require_POST
def restore(request, requirement_id):
    version_id = _version_of_requirement(requirement_id)
    return _act(request, version_id, lambda: service.restore(
        request.user, requirement_id, channel=Channel.SCREEN))


@require_POST
def add(request, version_id):
    if not MatrixVersion.objects.filter(pk=version_id).exists():
        raise Http404("No hay una versión de la matriz con ese número.")
    post = request.POST
    return _act(request, version_id, lambda: service.add_requirement(
        request.user, version_id, segment=post.get("segment"), quote=post.get("quote", ""),
        category=post.get("category", ""),
        items=post.get("items") if post.get("items", "").strip() else None,
        pending=post.get("pending") or None, channel=Channel.SCREEN))


@require_POST
def add_technical(request, version_id):
    if not MatrixVersion.objects.filter(pk=version_id).exists():
        raise Http404("No hay una versión de la matriz con ese número.")
    post = request.POST
    return _act(request, version_id, lambda: service.add_technical_row(
        request.user, version_id, item=post.get("item", ""),
        segments=post.getlist("segment"), channel=Channel.SCREEN))


@require_POST
def resolve(request, pending_id):
    try:
        version_id = PendingItem.objects.values_list("version_id", flat=True).get(
            pk=pending_id)
    except PendingItem.DoesNotExist:
        raise Http404("No hay un pendiente con ese número.")
    return _act(request, version_id, lambda: service.resolve_pending(
        request.user, pending_id, channel=Channel.SCREEN))


@require_GET
def history(request, requirement_id):
    try:
        page = service.history(request.user, requirement_id, channel=Channel.SCREEN)
    except Requirement.DoesNotExist:
        raise Http404("No hay un requisito con ese número.")
    return render(request, HISTORY_TEMPLATE, {"page": page})


@require_POST
def join_segment(request, version_id):
    """Suma un tramo a una fila técnica elegida en la página de la matriz."""
    if not MatrixVersion.objects.filter(pk=version_id).exists():
        raise Http404("No hay una versión de la matriz con ese número.")
    row = request.POST.get("row", "")
    if not row.isdigit():
        return _refused(request, version_id,
                        service.ReviewRefused("Elija la fila técnica.", "nothing_selected",
                                              "row"))
    if _version_of_requirement(int(row)) != version_id:
        raise Http404("Esa fila no es de esta matriz.")
    return _act(request, version_id, lambda: service.correct(
        request.user, int(row), add_segments=[request.POST.get("segment")],
        channel=Channel.SCREEN))
