"""Etiqueta de las plantillas para las consecuencias de un requisito (T-081): las opciones
con el texto literal de cada fundamento y, para el evaluador, el formulario de elección."""

from django import template

from evaluon.tenders.models import ConsequenceType
from evaluon.tenders.services import consequences

register = template.Library()


@register.inclusion_tag("tenders/_consequences.html", takes_context=True)
def consequence_panel(context, requirement):
    page = context["page"]
    return {
        "requirement": requirement,
        "options": consequences.options(requirement),
        "can_choose": page.can_confirm,
        "page": page,
        "other_types": [(v, l) for v, l in ConsequenceType.choices
                        if v != ConsequenceType.NO_DETERMINADA.value],
        "csrf_token": context.get("csrf_token", ""),
        "error": (context.get("review_error")
                  if context.get("review_error_requirement") == requirement.pk else ""),
    }


@register.inclusion_tag("tenders/_consequences_print.html")
def consequence_print(requirement):
    """Las consecuencias para la impresión y el PDF, de solo lectura (REQ-032, T-086): la
    elegida sola, con su motivo, quién y cuándo; si no hay elegida, las sugeridas con su
    fundamento resumido por su ubicación."""
    options = consequences.options(requirement)
    chosen = [o for o in options if o.chosen]
    return {"chosen": chosen[0] if chosen else None,
            "suggested": [] if chosen else options}
