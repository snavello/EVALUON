"""La presentación física en la Mesa de Entrada (REQ-104, REQ-105; spec 015, decisión del
2026-10-12 «si requiere presentacion fisica y no la hace (no consta entre los documentos ni en la
matriz de compliance) la oferta no cumple se informa con texto por si la comision o alguien olvido
agregarla»; ADR-0058, punto 4; T-257).

Presentar en la Mesa de Entrada lo que el Portal marca como «Requiere presentar» es requisito. La
regla (después de la forma de garantía y de la opción, antes que la de externos) reconoce el
requisito que pide presentar algo físicamente (un original, en la Mesa de Entrada) y:

- si el pliego lo ata a una forma de garantía («en el caso de optar por garantías no
  electrónicas»), rige solo si el Portal informa que la oferta eligió esa forma; la forma no
  elegida ya la resolvió `guarantee_form.py` («No aplica») y sin el dato de la forma no se decide;
- si lo ata a una marca del Portal («en caso que el sistema indique "Requiere presentar…"»), el
  sistema no tiene esa marca entre los datos del Portal que importa: «no determinado» con la
  pregunta a la Comisión de si el Portal lo marca, y el aviso de que, si lo marca y no consta, la
  oferta no cumple. **Pendiente** (desvío aceptado por el Coordinador sobre T-257, por prudencia):
  cuando el importador del Portal traiga la marca «Requiere presentar» de cada documento, esta
  rama pasa a «no cumple» con el aviso de que puede faltar cargarlo, como la decisión del
  2026-10-12;
- si rige y ni los documentos de la oferta ni su hoja de compliance la muestran (el modelo no ubicó
  ninguna cita, y la lectura fue completa): «no cumple», con el texto que avisa que puede faltar
  cargarlo (la constancia de la presentación o la hoja de compliance).

Si el modelo ubicó un texto que muestra la presentación (la constancia de la Mesa de Entrada, la
hoja de compliance), sigue el flujo de siempre. `facts` registra la regla y la versión (P6).
"""

import re
from dataclasses import replace

from evaluon.assessment import combine, criteria, guarantee_form
from evaluon.assessment.externals import fold, has_sheet
from evaluon.portal.models import PortalOfferData

RULE_MISSING = "presentacion_fisica_no_consta"
RULE_MARK = "presentacion_fisica_sin_marca"

PHYSICAL = re.compile(
    r"\bfisicamente\b|\bmesa de entradas?\b|\bpresentacion fisica\b|\brequiere presentar\b")
_PRESENT = re.compile(r"\bpresent\w*|\bentreg\w*|\bacompan\w*|\boriginal(?:es)?\b|\bfisicamente\b")
# La presentación atada a la marca del Portal.
PORTAL_MARK = re.compile(r"\b(?:se )?indiqu\w*\W+(?:\w+\W+){0,3}?requiere presentar"
                         r"|\brequiere presentar\b")

MISSING = ("No consta la presentación física que pide el pliego: ninguno de los documentos "
           "leídos ({read}) ni la hoja de compliance la muestra. Puede faltar cargarlo: si la "
           "oferta lo presentó, la Comisión puede subir la constancia de la Mesa de Entrada o la "
           "hoja de compliance.")
MARK = ("El pliego pide presentar físicamente lo que el Portal marque como «Requiere presentar», "
        "y el sistema no tiene esa marca entre los datos del Portal. Si el Portal lo marca y no "
        "consta la presentación entre los documentos ni en la hoja de compliance, la oferta no "
        "cumple: puede faltar cargarlo.")
MARK_QUESTION = ("¿El Portal marca algún documento de esta oferta como «Requiere presentar en Mesa "
                 "de Entrada»? Si lo marca y no consta la presentación, la oferta no cumple, aunque "
                 "quizá falte cargar la constancia o la hoja de compliance.")


def is_physical(text):
    """Si el requisito pide presentar algo físicamente (en la Mesa de Entrada)."""
    folded = fold(text)
    return bool(PHYSICAL.search(folded) and _PRESENT.search(folded))


def _form_applies(text, offer):
    """`True` si rige por la forma de garantía (o no está atado a una), `False` si no rige y `None`
    si está atado a una forma y el Portal no informa cuál eligió la oferta."""
    required = guarantee_form.required_forms(text)
    if not required:
        return True
    data = PortalOfferData.objects.filter(offer=offer).first()
    chosen = guarantee_form.chosen_forms(list(data.guarantees.all())) if data else set()
    if not chosen:
        return None
    return bool(chosen & required)


def rule(pair, ctx):
    """La regla de `rules.py`: devuelve el resultado nuevo del par o `None`."""
    combined = pair.combined
    text = getattr(pair.text, "opening", None) or pair.text.text
    if combined is None or not is_physical(text):
        return None
    groups = getattr(pair, "groups", None) or []
    if combined.citations or any(getattr(g, "citations", None) for g in groups):
        return None
    if not criteria.complete(combined):
        return None
    titles = criteria.documents_read(ctx)
    read = ", ".join(f"«{t}»" for t in titles) if titles else "todos los documentos de la oferta"
    if PORTAL_MARK.search(fold(text)):
        return replace(
            combined, outcome=combine.OUT_NO_DETERMINADO, doubt=combine.NO_DATA, citations=[],
            portal=[], question=MARK_QUESTION, ask=True, proposed="", explanation=MARK,
            facts={**combined.facts, "regla": RULE_MARK, "documentos_leidos": titles,
                   "hoja_compliance": has_sheet(ctx.offer)})
    if _form_applies(text, ctx.offer) is not True:
        return None
    return replace(
        combined, outcome=combine.OUT_NO_CUMPLE, doubt="", citations=[], portal=[], question="",
        ask=False, proposed="", explanation=MISSING.format(read=read),
        facts={**combined.facts, "regla": RULE_MISSING, "documentos_leidos": titles,
               "hoja_compliance": has_sheet(ctx.offer),
               "decision": "2026-10-12, presentación física que no consta"})
