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
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit.models import Channel
from evaluon.tenders.models import (
    ChangeAction,
    MatrixVersion,
    PendingItem,
    Requirement,
    RequirementChange,
    VersionStatus,
)
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


# --- Revisión por grupos (REQ-034, T-105) --------------------------------------------------------

GROUP_TEMPLATE = "tenders/group_confirm.html"
GROUP_OPERATION = "evaluon.tenders.views.review.group"

# Qué rol pide cada acción de grupo y qué servicio la aplica: confirmar es del evaluador;
# quitar, del operador o el evaluador (igual que en la matriz).
GROUP_ACTIONS = {
    "confirmar": (CommissionRole.EVALUATOR, service.confirm_group, "Confirmar"),
    "quitar": (CommissionRole.OPERATOR, service.remove_group, "Quitar"),
}


def clause_of(key):
    """La cláusula de primer nivel de la clave de un tramo: `sec-i/3.1.2` es de `sec-i/3`;
    las claves no tienen más niveles que la sección y la cláusula."""
    head = "/".join(key.split("/")[:2])
    for separator in (".", "#"):
        head = head.split(separator)[0]
    return head


def proposed_entries(version):
    """`[(requisito, [claves de sus citas propias])]` de las filas `propuesto` de la
    versión: lo mismo que mira el servicio para decidir si una fila es de un grupo."""
    entries = []
    for requirement in version.requirements.filter(state="propuesto").order_by("number"):
        keys = [q.segment.key for q in requirement.quotes.select_related("segment")
                if q.scope in ("", "propia")]
        entries.append((requirement, keys))
    return entries


def in_group(keys, group):
    """Si una fila con esas claves es del grupo (la regla de `services.review`)."""
    return bool(keys) and all(service.in_group(key, group) for key in keys)


def _group_rows(version, group):
    rows = [r for r, keys in proposed_entries(version) if in_group(keys, group)]
    if not rows:
        raise service.ReviewRefused(
            f"El grupo «{group}» no tiene filas propuestas: no hay nada que cambiar.",
            "empty_group", "group")
    return rows


def _group_page(request, version, action, group):
    """La página de confirmación previa: las N filas con su texto literal y, marcadas, las
    que una persona corrigió (vuelven a `propuesto` y entran en el grupo)."""
    role, _apply, verb = GROUP_ACTIONS[action]
    require_commission_role(request.user, role, operation=GROUP_OPERATION,
                            channel=Channel.SCREEN)
    if version.status != VersionStatus.DRAFT:
        raise service.ReviewRefused(
            "La versión de la matriz ya está validada o descartada y no se puede "
            "cambiar: abra una versión nueva.", "version_not_draft")
    group = (group or "").strip()
    if not group:
        raise service.ReviewRefused("Indique la cláusula o el tramo del grupo.",
                                    "invalid_group", "group")
    rows = _group_rows(version, group)
    corrected = set(RequirementChange.objects.filter(
        requirement__in=rows, action=ChangeAction.CORREGIR).values_list(
        "requirement_id", flat=True))
    cache = pages._Pages()
    items = [{"requirement": r, "corrected": r.pk in corrected,
              "quotes": pages._quote_rows(r, cache)[0]} for r in rows]
    return render(request, GROUP_TEMPLATE, {
        "version": version, "procedure": version.procedure, "group": group,
        "action": action, "verb": verb, "items": items, "count": len(items),
        "corrected_count": len(corrected)})


@require_http_methods(["GET", "POST"])
def group(request, version_id):
    """GET: la página previa con las filas que se van a tocar. POST ("Aceptar"): lo aplica."""
    try:
        version = MatrixVersion.objects.select_related("procedure").get(pk=version_id)
    except MatrixVersion.DoesNotExist:
        raise Http404("No hay una versión de la matriz con ese número.")
    data = request.POST if request.method == "POST" else request.GET
    action = data.get("action", "")
    name = data.get("group", "")
    try:
        if action not in GROUP_ACTIONS:
            raise service.ReviewRefused("Elija si confirmar o quitar el grupo.",
                                        "invalid_group_action", "action")
        if request.method == "GET":
            return _group_page(request, version, action, name)
        GROUP_ACTIONS[action][1](request.user, version_id, name, channel=Channel.SCREEN)
    except service.ReviewRefused as error:
        return _refused(request, version_id, error)
    return _back(version_id)
