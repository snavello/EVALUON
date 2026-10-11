"""La forma de garantía que elige el oferente (REQ-103; spec 015, decisión del 2026-10-10
«Requisito de la forma elegida»; ADR-0054; T-240, H-2).

Decisión literal del responsable: las condiciones de cada forma de garantía (por ejemplo, el límite
del pagaré o la póliza según la norma de la Superintendencia) entran en la matriz y se evalúan
solo en la oferta que eligió esa forma; para las demás no aplican.

La regla (primera del orden de `rules.py`): si el requisito es de **una** forma de garantía y la
forma que el Portal informa para la oferta es otra, el requisito **no aplica** a esa oferta. Se
guarda el par con la explicación «No aplica: …», la cita del Portal que muestra la forma elegida
y sin pregunta; `facts.aplica` queda en falso. El esquema no tiene un resultado «no aplica» (sumarlo
es una migración y la decide el responsable): el valor guardado es «cumple», pero **nunca se muestra ni
se cuenta como «cumple»**: `not_applicable.py` es la única definición del texto «No aplica (forma de
garantía no elegida)» y de la cuenta aparte (decisión del Coordinador sobre T-240).

Cuándo un requisito es de una forma (texto sin acentos): nombra una sola forma de garantía
(pagaré, póliza o seguro de caución, fianza, aval; `unreadable.FORMS`) **y** la condiciona («si se
trata de pagaré», «en el caso de optar por…») o trata de su documento («copia del pagaré», «cargar
el documento de la póliza», «el original…»). «Garantías no electrónicas» son todas las formas menos
la póliza, que se constituye en forma electrónica. Un requisito que nombra dos formas, o que
nombra una sin condicionar ni pedir su documento, vale para todas las ofertas.

Sin datos de garantía del Portal para la oferta, o con una forma que no se reconoce, la regla no
dice nada: queda lo que concluyó el modelo, a quien la instrucción le pide la misma distinción.
"""

import re
from dataclasses import replace

from evaluon.assessment import combine, portal_facts, unreadable
from evaluon.assessment.externals import fold
from evaluon.portal.models import PortalOfferData

RULE = "forma_garantia_no_elegida"

# Una garantía: sin esta palabra, «póliza» puede ser un seguro de otra cosa.
_GUARANTEE = re.compile(r"garantia|pagare|caucion|fianza|aval\b")
_NOT_ELECTRONIC = re.compile(r"garantias? no electronicas?")
# La condición que ata el requisito a una forma, o el documento de esa forma.
_CONDITIONAL = re.compile(
    r"\bsi\b|\ben (?:el )?caso\b|\bcuando\b|\boptar\b|\boptan\b|\boptare\w*|\belegi\w+"
    r"|\bse trata de\b|\bsegun (?:la )?forma\b")
_DOCUMENT = re.compile(
    r"\bcopias?\b|\boriginal(?:es)?\b|\bcargar\b|\badjunt\w+|\bdocumento\b|\bmesa de entradas?\b"
    r"|\bsuscri\w+|\bfirm\w+|\bendos\w+")
# La forma que el Portal informa: además de las palabras del pliego, «Seguros» (así lo rotula).
_PORTAL_POLICY = re.compile(r"\bseguros?\b")

LABELS = {"pagare": "pagaré", "poliza": "póliza de seguro de caución", "fianza": "fianza",
          "aval": "aval bancario"}


def required_forms(text):
    """Las formas de garantía a las que está atado el requisito (conjunto, quizá vacío): una sola
    forma nombrada y condicionada o con su documento; «no electrónicas», todas menos la póliza."""
    folded = fold(text)
    if not _GUARANTEE.search(folded):
        return set()
    if _NOT_ELECTRONIC.search(folded):
        return set(unreadable.FORMS) - {"poliza"}
    named = unreadable.forms_of(text)
    if len(named) != 1:
        return set()
    if _CONDITIONAL.search(folded) or _DOCUMENT.search(folded):
        return named
    return set()


def chosen_forms(rows):
    """Las formas de garantía que informa el Portal, de las filas de `portal_guarantee` de una
    oferta (solo las de la oferta: tipo vacío o «mantenimiento»/«oferta»)."""
    chosen = set()
    for row in rows:
        kind = fold(row.guarantee_type)
        if kind and "mantenim" not in kind and "oferta" not in kind:
            continue
        folded = fold(row.guarantee_form)
        chosen |= unreadable.forms_of(row.guarantee_form)
        if _PORTAL_POLICY.search(folded):
            chosen.add("poliza")
    return chosen


def _names(forms):
    return " o ".join(LABELS[name] for name in sorted(forms))


def rule(pair, ctx):
    """La regla 0 de `rules.py`: devuelve el resultado nuevo del par o `None`."""
    text = getattr(pair.text, "opening", None) or pair.text.text
    required = required_forms(text)
    if not required:
        return None
    data = PortalOfferData.objects.filter(offer=ctx.offer).first()
    if data is None:
        return None
    rows = list(data.guarantees.select_related("item").all())
    chosen = chosen_forms(rows)
    if not chosen or chosen & required:
        return None
    # La cita del Portal la escribe el sistema desde la fila, como en `portal_facts` (P3): sin ella
    # no hay «cumple».
    cites = [datum.citation() for datum in portal_facts.read(
        ctx.offer, portal_facts.GARANTIA, "", [])]
    if not cites:
        return None
    shown = ", ".join(sorted({row.guarantee_form for row in rows if row.guarantee_form}))
    combined = pair.combined
    return replace(
        combined, outcome=combine.OUT_CUMPLE, doubt="", citations=[], supports=[],
        portal=cites, question="", ask=False, proposed="", unread_warning=False,
        explanation=(f"No aplica: el requisito es de la garantía en {_names(required)} y la oferta "
                     f"eligió otra forma (el Portal informa «{shown}»). Fuente: Portal."),
        facts={**combined.facts, "regla": RULE, "aplica": False,
               "forma_requisito": sorted(required), "forma_oferta": sorted(chosen)})
