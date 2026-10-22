"""Datos del encabezado único (T-219, REQ-100) para las páginas que no arman su propio contexto
de procedimiento: la lista del desplegable y el rótulo del rol. Se calculan solo si la plantilla
los usa. Las vistas de las secciones los pasan ellas mismas y mandan sobre esto."""

import functools

from django.utils.functional import SimpleLazyObject

DROPDOWN_LIMIT = 25


def _procedures():
    from evaluon.tenders.models import Procedure
    return list(Procedure.objects.order_by("-created_at", "-pk")[:DROPDOWN_LIMIT])


def _avance(procedure_id):
    """El indicador de avance del encabezado (REQ-140; T-312), o `None` sin pedido en curso."""
    from evaluon.journey.views.avance import avance_of
    from evaluon.tenders.models import Procedure
    procedure = Procedure.objects.filter(pk=procedure_id).first()
    return avance_of(procedure) if procedure else None


def shell(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    out = {}
    match = getattr(request, "resolver_match", None)
    procedure_id = match.kwargs.get("procedure_id") if match else None
    if procedure_id is not None and match.namespace == "expedientes":
        # Un invocable memoizado: la plantilla lo llama al resolver `avance_pedido` y recibe el
        # dict o `None`. No se llama `avance` porque la sección 1 pasa su propio `avance` (el de
        # las secciones del primer panel) y tapaba este: el anillo giraba sin pedido (T-336).
        out["avance_pedido"] = functools.cache(lambda: _avance(procedure_id))
    if not user.commission_role:
        return out
    from evaluon.journey.views.portada import ROLE_LABELS
    out.update({"procedures": SimpleLazyObject(_procedures),
                "role_label": ROLE_LABELS.get(user.commission_role, "")})
    return out
