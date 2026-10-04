"""Etiquetas de las plantillas de la 003 (T-074).

- `matrix_panel`: la sección de la matriz de la página de un procedimiento (versiones,
  pedido en curso y formulario "Proponer matriz"). Las páginas del procedimiento están en
  `views/documents.py`; la etiqueta evita tocarlas. Toma el error de un pedido rechazado
  (`matrix_error`) y el nivel elegido (`matrix_level`) del contexto.
- `finished_notice`: el aviso de pedidos terminados que va en `base.html`, en todas las
  páginas. Entrega cada aviso una sola vez: al armarlo, lo marca como visto.
"""

from django import template
from django.conf import settings

from evaluon.tenders.models import Level
from evaluon.tenders.services import matrix_page

register = template.Library()


def _levels():
    return [(value, label) for value, label in Level.choices
            if value in settings.MATRIX_LEVELS_OFFERED]


@register.inclusion_tag("tenders/_matrix_panel.html", takes_context=True)
def matrix_panel(context, procedure):
    request = context["request"]
    return {
        "panel": matrix_page.panel(request.user, procedure),
        "procedure": procedure,
        "levels": _levels(),
        "selected_level": context.get("matrix_level") or settings.MATRIX_DEFAULT_LEVEL,
        "matrix_error": context.get("matrix_error", ""),
        "csrf_token": context.get("csrf_token", ""),
    }


@register.inclusion_tag("tenders/_finished_notice.html", takes_context=True)
def finished_notice(context):
    request = context.get("request")
    user = getattr(request, "user", None)
    return {"notices": matrix_page.finished_notice(user)}
