"""«No aplica (forma de garantía no elegida)»: cómo se ve y se cuenta un requisito que no aplica a la
oferta (REQ-103; decisión del Coordinador sobre T-240, H-2; spec 015, «Requisito de la forma
elegida»).

El esquema no tiene un resultado «no aplica»: la regla de `guarantee_form.py` guarda el par como
«cumple» con `facts.aplica = false`. Eso nunca se muestra ni se cuenta como «cumple»: **esta es la única
definición**, y la usan la celda y el detalle del par, el resumen por oferta, la planilla y el cuadro
(Excel y PDF), el recorrido, las cuentas de la corrida y las medidas de `medir_evaluacion`. Una
corrección de la Comisión rige sobre la propuesta: solo el resultado **propuesto y no corregido**
se muestra como «no aplica».
"""

LABEL = "No aplica (forma de garantía no elegida)"
# Clave con que se cuentan, aparte de los cuatro resultados.
KEY = "no_aplica"


def is_not_applicable(result):
    """Si el resultado (`Result`, `Combined` o cualquier cosa con `facts`) es un requisito que no
    aplica a la oferta (`facts.aplica` falso)."""
    facts = getattr(result, "facts", None) or {}
    return facts.get("aplica") is False


def shows_not_applicable(result, outcome=None):
    """Si hay que mostrarlo como «no aplica»: lo es y el resultado vigente (`outcome`) sigue siendo
    el propuesto (sin corrección de la persona). Sin `outcome`, el propuesto."""
    if result is None or not is_not_applicable(result):
        return False
    return outcome is None or outcome == result.outcome


def result_label(result, outcome=None, labels=None):
    """El texto del resultado de `result` (o del `outcome` vigente si se pasa): «No aplica (forma de
    garantía no elegida)» o la etiqueta de siempre (`labels`, por omisión `Outcome`)."""
    if shows_not_applicable(result, outcome):
        return LABEL
    if labels is None:
        from evaluon.assessment.models import Outcome as labels
    value = result.outcome if outcome is None else outcome
    return labels(value).label if value else ""


def outcome_key(result, outcome=None):
    """La clave con que se cuenta: `KEY` si se muestra como «no aplica»; si no, el resultado."""
    if shows_not_applicable(result, outcome):
        return KEY
    return result.outcome if outcome is None else outcome
