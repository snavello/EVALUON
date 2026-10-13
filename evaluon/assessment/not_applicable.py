"""«No aplica»: cómo se ve y se cuenta un requisito que no aplica a la oferta (REQ-103; decisión del
Coordinador sobre T-240, H-2; spec 015, «Requisito de la forma elegida»; T-257).

Dos reglas dejan un requisito que no aplica a la oferta, cada una con su texto:

- `guarantee_form.py`: el requisito de una forma de garantía que la oferta no eligió, «No aplica
  (forma de garantía no elegida)»;
- `options.py` (T-257): la condición de una opción que la oferta no usa (MiPyME, oferta
  alternativa, descuento, subcontratación, cotización parcial; la matriz la nombra en
  `Requirement.proposed["opcion"]`), «No aplica (opción no usada)».

El esquema no tiene un resultado «no aplica»: la regla guarda el par como «cumple» con
`facts.aplica = false`. Eso nunca se muestra ni se cuenta como «cumple»: **esta es la única
definición**, y la usan la celda y el detalle del par, el resumen por oferta, la planilla y el cuadro
(Excel y PDF), el recorrido, las cuentas de la corrida y las medidas de `medir_evaluacion`. Una
corrección de la Comisión rige sobre la propuesta: solo el resultado **propuesto y no corregido**
se muestra como «no aplica». Las dos reglas se cuentan juntas, con la clave `KEY`.
"""

LABEL = "No aplica (forma de garantía no elegida)"
OPTION_LABEL = "No aplica (opción no usada)"
# La regla que dejó el requisito sin aplicar (`facts.regla`) y su texto.
GUARANTEE_RULE = "forma_garantia_no_elegida"
OPTION_RULE = "opcion_no_usada"
LABELS = {GUARANTEE_RULE: LABEL, OPTION_RULE: OPTION_LABEL}
# Clave con que se cuentan, aparte de los cuatro resultados.
KEY = "no_aplica"


def is_not_applicable(result):
    """Si el resultado (`Result`, `Combined` o cualquier cosa con `facts`) es un requisito que no
    aplica a la oferta (`facts.aplica` falso)."""
    facts = getattr(result, "facts", None) or {}
    return facts.get("aplica") is False


def label_of(result):
    """El texto «No aplica (…)» de un resultado que no aplica, según la regla que lo decidió (la
    forma de garantía si no se sabe)."""
    facts = getattr(result, "facts", None) or {}
    return LABELS.get(facts.get("regla"), LABEL)


def shows_not_applicable(result, outcome=None):
    """Si hay que mostrarlo como «no aplica»: lo es y el resultado vigente (`outcome`) sigue siendo
    el propuesto (sin corrección de la persona). Sin `outcome`, el propuesto."""
    if result is None or not is_not_applicable(result):
        return False
    return outcome is None or outcome == result.outcome


def result_label(result, outcome=None, labels=None):
    """El texto del resultado de `result` (o del `outcome` vigente si se pasa): «No aplica (forma de
    garantía no elegida)», «No aplica (opción no usada)» o la etiqueta de siempre (`labels`, por
    omisión `Outcome`)."""
    if shows_not_applicable(result, outcome):
        return label_of(result)
    if labels is None:
        from evaluon.assessment.models import Outcome as labels
    value = result.outcome if outcome is None else outcome
    return labels(value).label if value else ""


def outcome_key(result, outcome=None):
    """La clave con que se cuenta: `KEY` si se muestra como «no aplica»; si no, el resultado."""
    if shows_not_applicable(result, outcome):
        return KEY
    return result.outcome if outcome is None else outcome
