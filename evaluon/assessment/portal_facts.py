"""El Portal como fuente (REQ-062, REQ-103; plan 004, "El Portal como fuente"; ADR-0043,
ADR-0053; T-169, T-233).

Decisión literal del responsable (2026-10-10, «Propone cumple»): cuando el dato que pide un
requisito está en el Portal, el sistema lo compara con lo que exige el pliego; si coincide propone
"cumple" citando el dato del Portal, y si no coincide propone "no cumple" o la diferencia. La
Comisión decide igual (P3, constitución 1.3: el Portal es fundamento). Reemplaza en eso al
ADR-0043 (que citaba el Portal y no decidía). Todo sale de las tablas locales de la 012 (sin red,
P4).

Qué requisito pide un dato del Portal lo dice un catálogo corto sobre el texto vigente del
pliego (como el de `externals.py`, con la misma versión `ASSESSMENT_RULES_VERSION`):

- `garantia`: garantía de oferta o de mantenimiento (`portal_guarantee`: tipo, forma, monto);
- `cuit`: el CUIT del oferente (`portal_offer_data.cuit`);
- `cotizacion`: la cotización de un renglón (`portal_quote`: precio y cantidad);
- `total`: el total de la oferta (`portal_offer_data.total`).

Qué exige el pliego, por clase de dato (`compare`): la garantía, el porcentaje (o el monto) que
fija el requisito sobre el total cotizado del Portal, con la tolerancia de un centavo; la
cotización por renglón, que todos los renglones del procedimiento (o los de la fila) tengan precio;
el total, que esté cargado y, si el requisito fija la moneda, que coincida; el CUIT, los once
dígitos. La regla (cuarta del orden, después de externo, técnico e ilegible):

- el dato coincide con lo que exige el pliego: "cumple" con la cita del Portal y la explicación
  «Fuente: Portal», sin pasar por el contraste del modelo (`portal_cumple`);
- no coincide: "no cumple" con la diferencia y la cita del Portal (`portal_no_cumple`);
- el pliego no fija un valor que se pueda leer (no es comparable): "no determinado",
  `falta_coincidencia`, con la diferencia a la vista (`portal_falta_coincidencia`); si la oferta ya
  concluyó con su propio texto, la conclusión queda y se agrega la cita (`portal_cita_agregada`);
- el modelo devolvió `datos` (texto **literal** de la oferta con el monto o el CUIT, ubicado como
  cualquier cita) y su valor, leído por regla y sin el modelo, difiere del Portal: "no
  determinado", `falta_coincidencia`, con la cita de la oferta y la del Portal;
- el texto de la oferta y el Portal se contradicen (el Portal coincide y la oferta dice "no
  cumple", o el Portal difiere y la oferta dice "cumple"): "no determinado",
  `falta_coincidencia`: la Comisión verifica cuál rige;
- un `datos` que no se ubicó, o del que no se lee un valor, no se compara: no se afirma nada.

El texto de la cita lo escribe el sistema desde las columnas del Portal, tal cual están en la
fila (nunca el modelo). Un "cumple" por esta regla nunca sale sin la cita del Portal (P3).
"""

import re
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation

from django.conf import settings

from evaluon.assessment import combine
from evaluon.assessment.externals import fold
from evaluon.portal.models import PortalLine, PortalOfferData, PortalQuote

FALTA_COINCIDENCIA = "falta_coincidencia"

# T-233 (ADR-0053): `portal_en_portal` (ADR-0043) ya no se emite; el dato del Portal se compara.
RULE_CUMPLE = "portal_cumple"
RULE_NO_CUMPLE = "portal_no_cumple"
RULE_MISMATCH = "portal_falta_coincidencia"
RULE_BOTH = "portal_cita_agregada"

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


# T-231 (E-7): una diferencia de redondeo de un centavo no es falta de coincidencia (el Portal y la
# oferta redondean el porcentaje de una garantía a veces distinto).
TOLERANCE = Decimal("0.01")


def _equal(kind, offered, portal):
    if kind == CUIT:
        return offered == portal
    return abs(Decimal(offered) - Decimal(portal)) <= TOLERANCE


# Qué otros datos del Portal se confunden con el pedido: una garantía no se compara con el total
# ni con el precio de un renglón, ni el total con la garantía (T-231, E-5).
OTHER_KINDS = {GARANTIA: (TOTAL, COTIZACION), TOTAL: (GARANTIA, COTIZACION),
               COTIZACION: (TOTAL, GARANTIA)}


def _other_values(offer, kind):
    """Los valores del Portal de otra clase de dato para la misma oferta."""
    values = []
    for other in OTHER_KINDS.get(kind, ()):
        values.extend(datum.value for datum in read(offer, other, "", []))
    return values


def _same_data(kind, located, portal, others):
    """Los fragmentos `datos` que hablan del mismo dato que el requisito. Un fragmento cuyos
    montos son todos de otra clase de dato del Portal (el total, cuando el requisito pide la
    garantía) no se compara: se compara garantía con garantía y total con total."""
    kept = []
    for found in located:
        values = amounts(found.text) if kind != CUIT else []
        other = bool(values) and all(
            any(_equal(kind, v, o) for o in others)
            and not any(_equal(kind, v, d.value) for d in portal) for v in values)
        if not other:
            kept.append(found)
    return kept


def _flagged(ctx):
    """Las diferencias ya señaladas en la oferta que se evalúa: la misma no se marca de nuevo."""
    flagged = getattr(ctx, "portal_flagged", None)
    if flagged is None:
        flagged = {}
        try:
            ctx.portal_flagged = flagged
        except AttributeError:
            pass
    return flagged


def _merge_offer(combined, located):
    seen = {found.span for found in combined.citations}
    merged = list(combined.citations)
    for found in located:
        if found.span not in seen:
            seen.add(found.span)
            merged.append(found)
    return merged[:settings.ASSESSMENT_MAX_CITATIONS]


# --- Lo que exige el pliego, por clase de dato (ADR-0053; T-233) -------------------------------

COINCIDE = "coincide"
DIFIERE = "difiere"
NO_COMPARABLE = "no_comparable"

# Porcentaje que fija el requisito: «5 %», «5%», «cinco por ciento», «cinco (5) por ciento».
_PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:\(\s*\d+\s*\)\s*)?(?:%|por\s*ciento)")
_WORD_PERCENT = re.compile(r"\b([a-z]+)\s*(?:\(\s*\d+\s*\)\s*)?por\s*ciento")
_NUMBER_WORDS = {
    "uno": 1, "un": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
    "ocho": 8, "nueve": 9, "diez": 10, "quince": 15, "veinte": 20, "treinta": 30,
    "cincuenta": 50, "cien": 100,
}


# T-175: la garantía individualizada en el Portal («Paso 4 Ingreso de Garantía»).
_INDIVIDUALIZED = re.compile(
    r"ingreso de (?:la )?garantia|garantias? (?:\w+ ){0,3}individualizad"
    r"|individualiz\w* (?:\w+ ){0,3}garantia")


@dataclass(frozen=True)
class Comparison:
    """Qué exige el pliego, qué informa el Portal y cómo quedan frente a frente."""

    state: str
    detail: str
    expected: str = ""
    observed: str = ""
    difference: str = ""

    def facts(self):
        return {"estado": self.state, "exigido": self.expected, "portal": self.observed,
                "diferencia": self.difference}


def required_percent(text):
    """El porcentaje que fija el texto del requisito, o `None` si no hay uno o hay varios
    distintos."""
    folded = fold(text)
    found = set()
    for match in _PERCENT.finditer(folded):
        found.add(Decimal(match.group(1).replace(",", ".")))
    for match in _WORD_PERCENT.finditer(folded):
        value = _NUMBER_WORDS.get(match.group(1))
        if value is not None:
            found.add(Decimal(value))
    return found.pop() if len(found) == 1 else None


def _plain(value):
    """Un número para leer: sin ceros de más ni notación científica."""
    text = f"{Decimal(value):f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _money(value):
    return f"{Decimal(value):.2f}"


def _guarantee_comparison(data, portal, text):
    """La garantía del Portal contra el porcentaje (sobre el total del Portal) o el monto que
    fija el requisito; coincide si la diferencia es de un centavo o menos."""
    folded = fold(text)
    percent = required_percent(text)
    if percent is not None and "renglon" not in folded:
        if data.total is None:
            return Comparison(NO_COMPARABLE, "El pliego fija la garantía como un porcentaje del "
                              "total cotizado y el Portal no informa el total de la oferta.")
        expected = data.total * percent / 100
        basis = f"el {_plain(percent)} % del total cotizado de {_money(data.total)}"
    else:
        absolute = set(amounts(text))
        if len(absolute) != 1:
            if _INDIVIDUALIZED.search(folded):
                # «Paso 4 Ingreso de Garantía» (T-175): lo que el pliego pide es que la garantía
                # esté individualizada en el Portal, y la fila de `portal_guarantee` lo muestra.
                observed = ", ".join(_money(d.value) for d in portal)
                return Comparison(
                    COINCIDE, f"La garantía está individualizada en el Portal ({observed}), "
                    "como pide el pliego.", "garantía individualizada", observed)
            return Comparison(NO_COMPARABLE, "El pliego no fija para la garantía un porcentaje "
                              "ni un monto que el sistema pueda leer.")
        expected = absolute.pop()
        basis = f"el monto de {_money(expected)}"
    values = [d.value for d in portal]
    observed = ", ".join(_money(v) for v in values)
    best = min([*values, sum(values)], key=lambda v: abs(Decimal(v) - expected))
    difference = abs(Decimal(best) - expected)
    if difference <= TOLERANCE:
        return Comparison(
            COINCIDE, f"El Portal informa una garantía de {observed}; el pliego exige {basis}, "
            f"es decir {_money(expected)}.", _money(expected), observed, _money(difference))
    return Comparison(
        DIFIERE, f"El Portal informa una garantía de {observed} y el pliego exige {basis}, es "
        f"decir {_money(expected)} (diferencia de {_money(difference)}).",
        _money(expected), observed, _money(difference))


def _currency_wanted(text):
    """La moneda que fija el requisito (`ARS` o `USD`), o `None` si no fija una sola."""
    folded = fold(text)
    pesos = bool(re.search(r"\bpesos?\b", folded))
    dollars = bool(re.search(r"\bdolar(?:es)?\b|\busd\b|u\$s", folded))
    if pesos == dollars:
        return None
    return "ARS" if pesos else "USD"


def _currency_of(value):
    folded = fold(value)
    if folded in {"ars", "peso", "pesos", "pesos argentinos", "$"}:
        return "ARS"
    if folded in {"usd", "u$s", "dolar", "dolares", "dolar estadounidense", "us$"}:
        return "USD"
    return None


def _total_comparison(data, portal, text):
    """El total del Portal: tiene que estar cargado y, si el requisito fija la moneda, coincidir."""
    shown = portal[0].shown
    wanted = _currency_wanted(text)
    if wanted is None:
        return Comparison(COINCIDE, f"El Portal informa un total de la oferta de {shown}"
                          + (f" {data.currency}" if data.currency else "")
                          + "; el pliego no fija otra condición para el total.", "", shown)
    have = _currency_of(data.currency)
    if have is None:
        return Comparison(
            NO_COMPARABLE, f"El pliego pide el total en {wanted} y el Portal no informa una "
            f"moneda que el sistema pueda leer ({data.currency or 'sin dato'}).", wanted, shown)
    if have == wanted:
        return Comparison(COINCIDE, f"El Portal informa un total de {shown} en {data.currency}, "
                          f"la moneda que fija el pliego ({wanted}).", wanted, shown)
    return Comparison(DIFIERE, f"El pliego pide el total en {wanted} y el Portal lo informa en "
                      f"{data.currency}.", wanted, f"{shown} {data.currency}")


def _quote_comparison(offer, items):
    """Todos los renglones del procedimiento (o los de la fila) con precio en el Portal."""
    lines = set(PortalLine.objects.filter(procedure_id=offer.procedure_id)
                .values_list("number", flat=True))
    wanted = set(items) if items else lines
    if not wanted:
        return Comparison(NO_COMPARABLE, "El Portal no informa los renglones del procedimiento.")
    quoted = set(PortalQuote.objects.filter(
        offer=offer, line__procedure_id=offer.procedure_id, price__isnull=False)
        .values_list("line__number", flat=True))
    missing = sorted(wanted - quoted)
    names = ", ".join(str(n) for n in sorted(wanted))
    if not missing:
        return Comparison(COINCIDE, f"El Portal informa el precio de todos los renglones que "
                          f"exige el pliego ({names}).", names, names, "")
    return Comparison(
        DIFIERE, f"El pliego exige el precio de los renglones {names} y el Portal no informa el "
        f"de los renglones {', '.join(str(n) for n in missing)}.", names,
        ", ".join(str(n) for n in sorted(wanted & quoted)) or "ninguno",
        ", ".join(str(n) for n in missing))


def _cuit_comparison(portal):
    """El CUIT del Portal: once dígitos (la igualdad con el de la oferta la mira la regla)."""
    shown = portal[0].shown
    size = len(digits(shown))
    if size == 11:
        return Comparison(COINCIDE, f"El Portal informa el CUIT del oferente {shown}, de once "
                          "dígitos.", "11 dígitos", shown)
    return Comparison(DIFIERE, f"El CUIT que informa el Portal ({shown}) tiene {size} dígitos y "
                      "el CUIT tiene once.", "11 dígitos", shown, f"{size} dígitos")


def compare(kind, offer, data, portal, text, items):
    """Lo que informa el Portal frente a lo que exige el pliego (`Comparison`)."""
    if kind == GARANTIA:
        return _guarantee_comparison(data, portal, text)
    if kind == TOTAL:
        return _total_comparison(data, portal, text)
    if kind == COTIZACION:
        return _quote_comparison(offer, items)
    if kind == CUIT:
        return _cuit_comparison(portal)
    return Comparison(NO_COMPARABLE, "El requisito pide otro dato.")


def _facts_of(combined, kind, portal, matching):
    return {**combined.facts, "portal": {
        "tipo": kind, "valor": (matching or portal)[0].shown,
        "valores": [d.shown for d in portal],
        "items": sorted({d.item for d in portal})}}


def _merge_portal(combined, extra):
    """Las citas del Portal que ya traía el par (las que el modelo citó con su alias) y las del
    dato leído, sin repetir."""
    cites, seen = [], set()
    for cite in [*combined.portal, *extra]:
        key = (cite["item"], cite["kind"], cite["text"])
        if key not in seen:
            seen.add(key)
            cites.append(cite)
    return cites


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
    items = item_numbers(requirement)
    portal = read(ctx.offer, kind, text, items)
    if not portal:
        return None
    combined = pair.combined
    located = _same_data(kind, list(getattr(pair, "datos", []) or []), portal,
                         _other_values(ctx.offer, kind) if kind in OTHER_KINDS else [])
    values = offered_values(kind, [found.text for found in located])
    matching = [d for d in portal if any(_equal(kind, v, d.value) for v in values)]
    facts = _facts_of(combined, kind, portal, matching)
    cites = _merge_portal(combined, [d.citation() for d in portal])
    if values and not matching:
        offered = ", ".join(sorted({str(v) for v in values}))
        shown = ", ".join(d.shown for d in portal)
        flagged = _flagged(ctx)
        key = (kind, offered, shown)
        first = flagged.setdefault(key, getattr(requirement, "number", None))
        explanation = ("Falta coincidencia: el Portal informa " + shown + " y la oferta "
                       + offered + ". La Comisión verifica cuál rige.")
        extra = {}
        if first != getattr(requirement, "number", None):
            # La misma diferencia ya se señaló en otro requisito de esta oferta (T-231, D-1): la
            # celda sigue en «falta coincidencia» y lo dice, sin repetir lo que ya se explicó.
            explanation = (f"Falta coincidencia con el Portal: misma diferencia que en el "
                           f"requisito {first} (el Portal informa {shown} y la oferta "
                           f"{offered}).")
            extra = {"diferencia_ya_senalada": first}
        return replace(
            combined, outcome=combine.OUT_NO_DETERMINADO, doubt=FALTA_COINCIDENCIA,
            exigence=combined.exigence, citations=_merge_offer(combined, located),
            portal=cites, question="", explanation=explanation,
            facts={**facts, "regla": RULE_MISMATCH, "oferta_valor": offered, **extra})

    data = PortalOfferData.objects.filter(offer=ctx.offer).first()
    comparison = compare(kind, ctx.offer, data, portal, text, items)
    facts = {**facts, "comparacion": comparison.facts()}
    from_offer = combined.outcome in (combine.OUT_CUMPLE, combine.OUT_NO_CUMPLE)

    def undetermined(why):
        return replace(
            combined, outcome=combine.OUT_NO_DETERMINADO, doubt=FALTA_COINCIDENCIA,
            citations=_merge_offer(combined, located), portal=cites, question="",
            explanation=f"Falta coincidencia: {why} La Comisión verifica cuál rige.",
            facts={**facts, "regla": RULE_MISMATCH})

    if comparison.state == NO_COMPARABLE:
        if from_offer:
            # La oferta ya concluyó con su propio texto: queda y se agrega la cita del Portal.
            return replace(combined, portal=cites, facts={**facts, "regla": RULE_BOTH})
        informed = ", ".join(d.shown for d in portal)
        return undetermined(f"el Portal informa {informed}. {comparison.detail} No se puede "
                            "comparar con el pliego.")
    if comparison.state == COINCIDE:
        if combined.outcome == combine.OUT_NO_CUMPLE:
            return undetermined(
                comparison.detail + " El texto de la oferta concluyó que no cumple.")
        note = (f"{combined.explanation} " if combined.outcome == combine.OUT_CUMPLE
                and combined.explanation else "")
        return replace(
            combined, outcome=combine.OUT_CUMPLE, doubt="", portal=cites, question="",
            explanation=f"{note}Fuente: Portal. {comparison.detail}",
            facts={**facts, "regla": RULE_CUMPLE})
    # El Portal difiere de lo que exige el pliego.
    if combined.outcome == combine.OUT_CUMPLE and not matching:
        return undetermined(comparison.detail + " El texto de la oferta concluyó que cumple.")
    kept = combined.citations if combined.outcome == combine.OUT_NO_CUMPLE else []
    return replace(
        combined, outcome=combine.OUT_NO_CUMPLE, doubt="", citations=kept, portal=cites,
        question="",
        explanation=f"No cumple según el Portal (fuente: Portal). {comparison.detail}",
        facts={**facts, "regla": RULE_NO_CUMPLE})


def item_numbers(requirement):
    """Los renglones que nombra la fila, como números."""
    numbers = []
    for item in getattr(requirement, "items", None) or []:
        try:
            numbers.append(int(item))
        except (TypeError, ValueError):
            continue
    return numbers
