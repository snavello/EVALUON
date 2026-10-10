"""Datos del encabezado único (T-219, REQ-100) para las páginas que no arman su propio contexto
de procedimiento: la lista del desplegable y el rótulo del rol. Se calculan solo si la plantilla
los usa. Las vistas de las secciones los pasan ellas mismas y mandan sobre esto."""

from django.utils.functional import SimpleLazyObject

DROPDOWN_LIMIT = 25


def _procedures():
    from evaluon.tenders.models import Procedure
    return list(Procedure.objects.order_by("-created_at", "-pk")[:DROPDOWN_LIMIT])


def shell(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or not user.commission_role:
        return {}
    from evaluon.journey.views.portada import ROLE_LABELS
    return {"procedures": SimpleLazyObject(_procedures),
            "role_label": ROLE_LABELS.get(user.commission_role, "")}
