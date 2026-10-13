"""«No aplica (opción no usada)»: la condición de una opción que la oferta no usa (REQ-103,
REQ-105; spec 015, decisión del 2026-10-10 sobre lo que entra en la matriz, REQ-102: las condiciones
que solo valen si el oferente elige una opción entran «como condición de esa opción»; definiciones
de la matriz: «se evalúa solo en la oferta que usa la opción»; T-257).

La matriz nombra la opción de la que depende una fila en `Requirement.proposed["opcion"]` (un nombre
corto: `mipyme`, `oferta_alternativa`, `descuento`, `subcontratacion`, `cotizacion_parcial`…; lo
guarda T-258). La regla (segunda del orden de `rules.py`, después de la forma de garantía y antes que
la de externos) dice que la fila **no aplica** a la oferta cuando ni sus documentos ni el Portal
muestran que la oferta use la opción:

- el modelo leyó la oferta completa y no ubicó ningún texto ni dato del Portal sobre la fila (ningún
  grupo trae una cita ubicada: lo que el modelo concluya sin cita no muestra nada);
- para la cotización parcial, además, el Portal informa la cotización de todos los renglones del
  procedimiento por la cantidad pedida (si cotizó menos, la usa).

Se guarda como la forma de garantía no elegida (`not_applicable.py`): «cumple» con `facts.aplica`
falso, nunca mostrado ni contado como «cumple», sin pregunta, con la explicación de qué opción es y
qué documentos se leyeron. Solo con la cita del requisito ubicada en el pliego y sin ninguna
evidencia de uso (verificación de T-257, D-257-6): si el modelo dice algo de la opción sin una cita
ubicada (una cita que no se ubicó, un dato, una conclusión), si el contraste no corroboró, o si en la
cotización parcial el Portal no tiene los renglones, el resultado es «no determinado» con la pregunta
de si la opción aplica (`opcion_sin_determinar`). Con partes de la oferta sin leer la regla no dice nada (no se puede
afirmar que no la usa). Si la oferta muestra que usa la opción, se evalúa como cualquier otra fila.
Una matriz sin `opcion` (ya validada antes de T-258) no pasa por esta regla: la instrucción de la
evaluación (`evaluacion-v11`) tiene la regla de respaldo.
"""

from dataclasses import replace

from evaluon.assessment import combine, criteria
from evaluon.assessment.not_applicable import OPTION_RULE
from evaluon.portal.models import PortalLine, PortalQuote

RULE = OPTION_RULE
# T-257, verificación (D-257-6): cuando no se puede afirmar si la oferta usa la opción, «no
# determinado» con la pregunta de si la opción aplica, nunca «no aplica».
RULE_UNSURE = "opcion_sin_determinar"

NAMES = {"mipyme": "MiPyME", "oferta_alternativa": "oferta alternativa",
         "descuento": "descuento", "subcontratacion": "subcontratación",
         "cotizacion_parcial": "cotización parcial"}


def option_of(requirement):
    """El nombre corto de la opción de la que depende la fila, o `""`."""
    proposed = getattr(requirement, "proposed", None)
    name = proposed.get("opcion") if isinstance(proposed, dict) else None
    return name.strip() if isinstance(name, str) else ""


def label(name):
    if name in ("otra", "otro", "opcion"):
        # O-257-5: la opción «otra» de la matriz no tiene un nombre que decir.
        return "que nombra el requisito"
    return NAMES.get(name, name.replace("_", " "))


def _named(name):
    shown = label(name)
    return f"la opción {shown}" if shown.startswith("que ") else f"la opción «{shown}»"


def _quotes_part(offer):
    """Si el Portal muestra que la oferta cotizó parte de lo pedido: un renglón sin precio o con una
    cantidad menor que la del procedimiento. `None` si el Portal no tiene los renglones del
    procedimiento (no se puede saber)."""
    lines = {line.number: line.quantity
             for line in PortalLine.objects.filter(procedure_id=offer.procedure_id)}
    if not lines:
        return None
    quotes = {q.line.number: q for q in PortalQuote.objects.filter(
        offer=offer, line__procedure_id=offer.procedure_id).select_related("line")}
    for number, wanted in lines.items():
        quote = quotes.get(number)
        if quote is None or quote.price is None:
            return True
        if wanted is not None and quote.quantity is not None and quote.quantity < wanted:
            return True
    return False


def _shows_use(pair, ctx, name):
    """Si los documentos o el Portal muestran que la oferta usa la opción."""
    combined = pair.combined
    groups = getattr(pair, "groups", None) or []
    if combined.citations or any(getattr(g, "citations", None) for g in groups):
        return True
    if "parcial" in name:
        # Lo que muestra el Portal de una cotización parcial son sus renglones y cantidades: el
        # modelo puede citar la cotización completa sin que eso muestre la opción.
        return bool(_quotes_part(ctx.offer))
    return bool(combined.portal or any(getattr(g, "portal", None) for g in groups))


def _unsure(pair, ctx, name):
    """Por qué no se puede afirmar que la oferta no usa la opción (D-257-6), o `""`: el modelo dice
    algo de la opción sin una cita ubicada (una cita que no se ubicó, un dato, una conclusión), el
    contraste no corroboró, o, en la cotización parcial, el Portal no tiene los renglones."""
    combined = pair.combined
    if combined.doubt in ("sin_cita", "sin_corroborar", "contradiccion") or combined.proposed:
        return "el modelo dice algo sobre la opción y el sistema no ubicó su texto"
    if any(getattr(g, "result", "") in ("cumple", "no_cumple")
           for g in getattr(pair, "groups", None) or []):
        return "el modelo concluyó sobre la opción sin un texto ubicado"
    for item in criteria.conditions_of(pair):
        if (item.get("dato") or "").strip() or (
                item.get("resultado_modelo") or item.get("resultado")) in ("cumple", "no_cumple"):
            return "el modelo dice algo sobre la opción sin un texto ubicado"
    if "parcial" in name and _quotes_part(ctx.offer) is None:
        return "el Portal no tiene los renglones del procedimiento"
    return ""


def rule(pair, ctx):
    """La regla de `rules.py`: devuelve el resultado nuevo del par o `None`. «No aplica» solo con la
    cita del requisito ubicada, la lectura completa y sin ninguna evidencia de que la oferta use la
    opción (D-257-6); con evidencia sin cita, «no determinado» con la pregunta."""
    name = option_of(pair.requirement)
    combined = pair.combined
    if not name or combined is None or not criteria.complete(combined):
        return None
    if not getattr(pair.text, "quotes", None):
        # Sin la cita del requisito ubicada en el pliego no se sabe a qué alcanza la opción.
        return None
    if _shows_use(pair, ctx, name):
        return None
    why = _unsure(pair, ctx, name)
    if why:
        return replace(
            combined, outcome=combine.OUT_NO_DETERMINADO, doubt=combine.NO_DATA, ask=True,
            proposed="",
            question=(f"¿La oferta usa {_named(name)}? {why[0].upper()}{why[1:]}; si no la usa, "
                      "la condición no aplica a esta oferta."),
            explanation=(f"No se puede afirmar si la oferta usa {_named(name)}: {why}."),
            facts={**combined.facts, "regla": RULE_UNSURE, "opcion": name})
    titles = criteria.documents_read(ctx)
    read = ", ".join(f"«{t}»" for t in titles) if titles else "todos los documentos de la oferta"
    return replace(
        combined, outcome=combine.OUT_CUMPLE, doubt="", citations=[], supports=[], portal=[],
        question="", ask=False, proposed="", unread_warning=False,
        explanation=(f"No aplica: la condición vale solo para quien usa {_named(name)} y "
                     f"ni los documentos de la oferta ({read}) ni el Portal muestran que la use."),
        facts={**combined.facts, "regla": RULE, "aplica": False, "opcion": name,
               "documentos_leidos": titles})
