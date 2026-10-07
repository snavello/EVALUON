"""El Portal como fuente (REQ-062; plan 004, "El Portal como fuente"; ADR-0043; T-169).

Decisión literal del responsable: «Debiste informar que el doc esta en el portal o que falta
coincidencia». Cuando el dato o el documento que pide un requisito está en el Portal, el sistema
lo informa y lo cita como fuente; si el Portal y la oferta no coinciden, lo informa como falta de
coincidencia. Todo sale de las tablas locales de la 012 (sin red, P4).

Qué requisito pide un dato del Portal lo dice un catálogo corto sobre el texto vigente del
pliego (como el de `externals.py`, con la misma versión `ASSESSMENT_RULES_VERSION`):

- `garantia`: garantía de oferta o de mantenimiento (`portal_guarantee`: tipo, forma, monto);
- `cuit`: el CUIT del oferente (`portal_offer_data.cuit`);
- `cotizacion`: la cotización de un renglón (`portal_quote`: precio y cantidad);
- `total`: el total de la oferta (`portal_offer_data.total`).

La regla (cuarta del orden, después de externo, técnico e ilegible):

- el dato está en el Portal y **no** en la oferta (sin cita de la oferta ni `datos`):
  "no determinado", `en_portal`, con la cita `portal`;
- está en los dos: la cita del Portal se agrega y el resultado no cambia;
- el modelo devolvió `datos` (texto **literal** de la oferta con el monto o el CUIT, ubicado como
  cualquier cita) y su valor, leído por regla y sin el modelo, difiere del Portal: "no
  determinado", `falta_coincidencia`, con la cita de la oferta y la del Portal;
- un `datos` que no se ubicó, o del que no se lee un valor, no se compara: no se afirma nada.

El texto de la cita lo escribe el sistema desde las columnas del Portal, tal cual están en la
fila (nunca el modelo). Una cita del Portal no habilita "cumple" ni "no cumple" (P3).
"""

import re
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation

from django.conf import settings

from evaluon.assessment import combine
from evaluon.assessment.externals import fold
from evaluon.portal.models import PortalOfferData, PortalQuote

EN_PORTAL = "en_portal"
FALTA_COINCIDENCIA = "falta_coincidencia"

RULE_ONLY_PORTAL = "portal_en_portal"
RULE_BOTH = "portal_cita_agregada"
RULE_MISMATCH = "portal_falta_coincidencia"

GARANTIA = "garantia"
COTIZACION = "cotizacion"
TOTAL = "total"
CUIT = "cuit"

ACTA = "Portal: acta de apertura"
CUADRO = "Portal: cuadro comparativo"

# Qué requisito pide un dato del Portal: expresión sobre el texto sin acentos ni mayúsculas. El
# orden es el de precedencia (una garantía «del monto cotizado» es una garantía, no un total).
CATALOG = (
    (GARANTIA, re.compile(
        r"garantia de (?:mantenimiento|oferta)|mantenimiento de (?:la )?oferta"
        r"|garantia de (?:la )?oferta|poliza de caucion|pagare"
        # T-175: la garantía individualizada en el Portal («Paso 4 Ingreso de Garantía»).
        r"|ingreso de (?:la )?garantia|garantias? (?:\w+ ){0,3}individualizad"
        r"|individualiz\w* (?:\w+ ){0,3}garantia")),
    (CUIT, re.compile(r"\bcuit\b|clave unica de identificacion tributaria")),
    (COTIZACION, re.compile(
        r"cotizacion|cotizar|precio unitario|planilla de precios|oferta economica")),
    (TOTAL, re.compile(
        r"(?:precio|monto|importe|valor) total|total de la oferta|oferta economica"
        r"|propuesta economica")),
)


# T-175: un requisito que pide cotizar por renglón (todos o algunos, el valor unitario de cada
# uno, «por renglón») sin ser la fila de un renglón concreto: pide la cotización de todos los
# renglones de la oferta que el Portal tiene.
PER_LINE = re.compile(
    r"cotiz\w*\W+(?:\w+\W+){0,12}?renglon|renglon\w*\W+(?:\w+\W+){0,12}?cotiz"
    r"|(?:precio|valor) unitario\W+(?:\w+\W+){0,8}?renglon|por renglon|cada (?:uno de los )?renglon")


# T-175 (H-1): la cotización sin renglón nombrado aplica solo si el requisito pide un precio, un
# valor unitario o un importe; «porcentaje de la cotización» o «cantidad por renglón» no lo piden.
PRICE_WORD = re.compile(r"\bprecios?\b|\bimportes?\b|\bvalor(?:es)?\b")


def kind_of(text, requirement=None):
    """La clase de dato del Portal que pide el requisito, o `None`. La cotización por renglón
    rige si la fila es de un renglón o si el texto pide cotizar por renglón (todos, algunos o
    cada uno); si no, una oferta económica es el total."""
    folded = fold(text)
    items = getattr(requirement, "items", None) or []
    for kind, pattern in CATALOG:
        if kind == COTIZACION and not items:
            if PER_LINE.search(folded) and PRICE_WORD.search(folded):
                return kind
            continue
        if not pattern.search(folded):
            continue
        return kind
    return None


@dataclass(frozen=True)
class Datum:
    """Un dato del Portal para citar: clase, valor para comparar (`Decimal` o texto), el valor
    tal cual figura en la fila, el ítem de origen y el texto de la cita."""

    kind: str
    value: object
    shown: str
    item: int
    label: str
    text: str

    def citation(self):
        return {"item": self.item, "kind": self.kind, "label": self.label, "text": self.text}


def _amount(value):
    """El monto tal cual está en la fila (sin normalizar)."""
    return "sin dato" if value is None else str(value)


def _wants_type(text):
    """Qué tipo de garantía nombra el requisito: `mantenim`, `oferta` o ambos."""
    words = []
    if "mantenimiento" in text:
        words.append("mantenim")
    if re.search(r"garantia de (?:la )?oferta", text):
        words.append("oferta")
    return words


def _guarantees(data, text):
    wanted = _wants_type(fold(text))
    found = []
    for guarantee in data.guarantees.select_related("item").all():
        kind = fold(guarantee.guarantee_type)
        if wanted and kind and not any(word in kind for word in wanted):
            continue
        if guarantee.amount is None:
            continue
        found.append(Datum(
            GARANTIA, guarantee.amount, _amount(guarantee.amount), guarantee.item_id, ACTA,
            f"Garantía: tipo {guarantee.guarantee_type or 'sin dato'}, forma "
            f"{guarantee.guarantee_form or 'sin dato'}, monto {_amount(guarantee.amount)}"))
    return found


def read(offer, kind, text, items):
    """Los datos del Portal que corresponden al requisito para la oferta (lista, quizá vacía),
    leídos de las tablas locales de la 012."""
    data = PortalOfferData.objects.filter(offer=offer).select_related("item").first()
    if data is None:
        return []
    if kind == GARANTIA:
        return _guarantees(data, text)
    if kind == CUIT:
        return [Datum(CUIT, digits(data.cuit), data.cuit, data.item_id, ACTA,
                      f"CUIT del oferente: {data.cuit}")] if digits(data.cuit) else []
    if kind == TOTAL:
        if data.total is None:
            return []
        return [Datum(TOTAL, data.total, _amount(data.total), data.item_id, ACTA,
                      f"Total de la oferta: {_amount(data.total)}"
                      + (f" {data.currency}" if data.currency else ""))]
    if kind == COTIZACION:
        # Con renglones nombrados, los de la fila; sin ellos (cotizar por renglón), todos los
        # que cotizó la oferta (T-175).
        quotes = PortalQuote.objects.filter(
            offer=offer, line__procedure_id=offer.procedure_id,
            price__isnull=False).select_related("line").order_by("line__number")
        if items:
            quotes = quotes.filter(line__number__in=items)
        return [Datum(
            COTIZACION, quote.price, _amount(quote.price), data.item_id, CUADRO,
            f"Renglón {quote.line.number}: precio {_amount(quote.price)}, cantidad "
            f"{_amount(quote.quantity)}") for quote in quotes]
    return []


# --- Lectura de un valor en el texto de la oferta (por regla, sin el modelo) --------------------

_MONEY = re.compile(
    r"(?<![\w.,])(\$\s*)?(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)(?![\d])"
    r"(?!\s*%)(?![.,]\d)")
_CUIT = re.compile(r"(?<!\d)(\d{2})[-\s]?(\d{8})[-\s]?(\d)(?!\d)")


def digits(text):
    return re.sub(r"\D", "", text or "")


def _parse_amount(token):
    if "," in token:
        token = token.replace(".", "").replace(",", ".")
    elif "." in token:
        groups = token.split(".")
        if all(len(group) == 3 for group in groups[1:]):
            token = token.replace(".", "")
    try:
        return Decimal(token)
    except InvalidOperation:
        return None


def amounts(text):
    """Los montos que se leen en `text`: los que llevan `$`, separador de miles o dos decimales
    (un número suelto, como un día o un porcentaje, no es un monto). Argentina: punto de miles
    y coma decimal."""
    found = []
    for match in _MONEY.finditer(text or ""):
        sign, token = match.groups()
        money = bool(sign) or re.search(r"\.\d{3}|[.,]\d{2}$", token)
        value = _parse_amount(token) if money else None
        if value is not None:
            found.append(value)
    return found


def cuits(text):
    """Los CUIT (once dígitos, con o sin guiones) que se leen en `text`, solo dígitos."""
    return ["".join(m.groups()) for m in _CUIT.finditer(text or "")]


def offered_values(kind, texts):
    """Los valores de la oferta del mismo tipo que el dato del Portal, leídos del texto literal."""
    values = []
    for text in texts:
        values.extend(cuits(text) if kind == CUIT else amounts(text))
    return values


def _equal(kind, offered, portal):
    if kind == CUIT:
        return offered == portal
    return Decimal(offered).quantize(Decimal("0.01")) == Decimal(portal).quantize(Decimal("0.01"))


def _located_texts(pair):
    return [found.text for found in getattr(pair, "datos", []) or []]


def _merge_offer(combined, located):
    seen = {found.span for found in combined.citations}
    merged = list(combined.citations)
    for found in located:
        if found.span not in seen:
            seen.add(found.span)
            merged.append(found)
    return merged[:settings.ASSESSMENT_MAX_CITATIONS]


def rule(pair, ctx):
    """La regla 4 de `rules.py`: devuelve el resultado nuevo del par o `None` si el requisito no
    pide un dato del Portal o el Portal no lo tiene para la oferta."""
    requirement = pair.requirement
    # T-175: además del texto de la cita se mira lo que la antecede en su tramo (la cita puede
    # recortar solo «el número identificatorio…» y la condición dice «Ingreso de Garantía»).
    text = getattr(pair.text, "opening", None) or pair.text.text
    kind = kind_of(text, requirement)
    if kind is None:
        return None
    portal = read(ctx.offer, kind, text, item_numbers(requirement))
    if not portal:
        return None
    combined = pair.combined
    located = list(getattr(pair, "datos", []) or [])
    values = offered_values(kind, _located_texts(pair))
    matching = [d for d in portal if any(_equal(kind, v, d.value) for v in values)]
    facts = {**combined.facts, "portal": {
        "tipo": kind, "valor": (matching or portal)[0].shown,
        "valores": [d.shown for d in portal],
        "items": sorted({d.item for d in portal})}}
    cites = [*combined.portal, *[d.citation() for d in portal]]
    if values and not matching:
        offered = ", ".join(sorted({str(v) for v in values}))
        shown = ", ".join(d.shown for d in portal)
        return replace(
            combined, outcome=combine.OUT_NO_DETERMINADO, doubt=FALTA_COINCIDENCIA,
            exigence=combined.exigence, citations=_merge_offer(combined, located),
            portal=cites, question="",
            explanation=("Falta coincidencia: el Portal informa " + shown + " y la oferta "
                         + offered + ". La Comisión verifica cuál rige."),
            facts={**facts, "regla": RULE_MISMATCH, "oferta_valor": offered})
    in_offer = bool(combined.citations) or bool(located)
    if in_offer:
        return replace(combined, portal=cites, facts={**facts, "regla": RULE_BOTH})
    return replace(
        combined, outcome=combine.OUT_NO_DETERMINADO, doubt=EN_PORTAL,
        question="", portal=cites,
        explanation=("El documento o el dato está en el Portal (fuente: Portal), no en los "
                     "documentos de la oferta. " + "; ".join(d.text for d in portal) + "."),
        facts={**facts, "regla": RULE_ONLY_PORTAL})


def item_numbers(requirement):
    """Los renglones que nombra la fila, como números."""
    numbers = []
    for item in getattr(requirement, "items", None) or []:
        try:
            numbers.append(int(item))
        except (TypeError, ValueError):
            continue
    return numbers
