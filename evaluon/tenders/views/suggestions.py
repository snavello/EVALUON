"""Decidir las sugerencias de condición desde la pantalla (REQ-035, REQ-034, REQ-026; plan 003,
"Pantalla e impresión" de las sugerencias; ADR-0022; T-112).

- `accept`: "Pasar a requisito" de una sugerencia (POST). Quitar una sola es la acción de
  quitar de la revisión, que admite una sugerencia.
- `group`: "Pasar a requisito las N" y "Quitar las N" de una cláusula o un tramo. GET muestra
  la página previa con las N filas y su texto literal; POST ("Aceptar") lo aplica. Reutiliza
  `group_confirm.html`.

Cada acción llama al servicio, que comprueba el rol y deja el registro. Un cambio rechazado
vuelve a mostrar la matriz con el motivo, sin cambiar nada. Sin el rol, "acceso denegado"
(403) y el rechazo queda registrado. La vista no guarda nada en la sesión.
"""

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit.models import Channel
from evaluon.tenders.models import MatrixVersion, Requirement, VersionStatus
from evaluon.tenders.services import groups, suggestions
from evaluon.tenders.services import matrix_page as pages
from evaluon.tenders.services import review as service

MATRIX_TEMPLATE = "tenders/matrix.html"
GROUP_TEMPLATE = "tenders/group_confirm.html"
GROUP_OPERATION = "evaluon.tenders.views.suggestions.group"

# Qué servicio aplica cada acción de grupo y cómo se llama su botón; las dos son del
# operador o el evaluador.
GROUP_ACTIONS = {
    "pasar": (suggestions.accept_suggestions_group, "Pasar a requisito"),
    "quitar": (suggestions.remove_suggestions_group, "Quitar"),
}


def _refused(request, version_id, error):
    page = pages.matrix_page(request.user, version_id, channel=Channel.SCREEN)
    return render(request, MATRIX_TEMPLATE, {"page": page, "review_error": str(error),
                                             "review_error_field": error.field},
                  status=400)


@require_POST
def accept(request, requirement_id):
    """Pasa a requisito una sugerencia y vuelve a la matriz, en esa fila."""
    try:
        version_id = Requirement.objects.values_list("version_id", flat=True).get(
            pk=requirement_id)
    except Requirement.DoesNotExist:
        raise Http404("No hay un requisito con ese número.")
    try:
        done = suggestions.accept_suggestion(request.user, requirement_id,
                                             channel=Channel.SCREEN)
    except service.ReviewRefused as error:
        return _refused(request, version_id, error)
    url = reverse("tenders:matrix", args=[version_id])
    return redirect(f"{url}#requisito-{done.requirements[0].number}")


def _group_rows(version, group):
    rows = [r for r, keys in groups.suggested_entries(version)
            if groups.in_group(keys, group)]
    if not rows:
        raise service.ReviewRefused(
            f"El grupo «{group}» no tiene sugerencias: no hay nada que cambiar.",
            "empty_group", "group")
    return rows


def _group_page(request, version, action, group):
    """La página de confirmación previa: las N sugerencias con su texto literal y su motivo."""
    _apply, verb = GROUP_ACTIONS[action]
    require_commission_role(request.user, CommissionRole.EVALUATOR,
                            operation=GROUP_OPERATION, channel=Channel.SCREEN)
    if version.status != VersionStatus.DRAFT:
        raise service.ReviewRefused(
            "La versión de la matriz ya está validada o descartada y no se puede "
            "cambiar: abra una versión nueva.", "version_not_draft")
    group = (group or "").strip()
    if not group:
        raise service.ReviewRefused("Indique la cláusula o el tramo del grupo.",
                                    "invalid_group", "group")
    cache = pages.Pages()
    items = []
    for requirement in _group_rows(version, group):
        row = pages.requirement_row(requirement, cache)
        items.append({"requirement": requirement, "corrected": False, "quotes": row.quotes,
                      "phrase": row.doubt_phrase, "supported": bool(row.supports)})
    return render(request, GROUP_TEMPLATE, {
        "version": version, "procedure": version.procedure, "group": group,
        "action": action, "verb": verb, "noun": "sugerencias", "items": items,
        "count": len(items), "corrected_count": 0,
        "post_url": reverse("tenders:suggestion_group", args=[version.pk])})


@require_http_methods(["GET", "POST"])
def group(request, version_id):
    """GET: la página previa con las sugerencias que se van a tocar. POST ("Aceptar"): lo
    aplica."""
    try:
        version = MatrixVersion.objects.select_related("procedure").get(pk=version_id)
    except MatrixVersion.DoesNotExist:
        raise Http404("No hay una versión de la matriz con ese número.")
    data = request.POST if request.method == "POST" else request.GET
    action = data.get("action", "")
    name = data.get("group", "")
    try:
        if action not in GROUP_ACTIONS:
            raise service.ReviewRefused("Elija si pasar a requisito o quitar el grupo.",
                                        "invalid_group_action", "action")
        if request.method == "GET":
            return _group_page(request, version, action, name)
        GROUP_ACTIONS[action][0](request.user, version_id, name, channel=Channel.SCREEN)
    except service.ReviewRefused as error:
        return _refused(request, version_id, error)
    return redirect(reverse("tenders:matrix", args=[version_id]))
