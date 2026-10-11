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

- el dato coincide con lo que exige el pliego, sobre la base que el pliego dice (T-233b: el
  porcentaje de la garantía es sobre el total cotizado solo si el pliego lo dice; un tope, un
  mínimo, un monto o un CUIT fijados por el pliego se comparan o dejan el par sin comparar):
  "cumple" con la cita del Portal y la explicación
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

T-240 (ronda de ajuste): el número de una cláusula no es un monto (`amounts`); «hasta» es un tope
solo si lo sigue un valor, y un porcentaje fija el total o la cotización solo si modifica el precio
(descuento, recargo); un requisito sobre el documento de la garantía (copia, original, Mesa de
Entrada) no pide un monto y el Portal no lo decide (`NO_PIDE`); «cargar el documento de la póliza
en el Portal» coincide si el Portal informa una garantía en esa forma.

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
        r"|garantia de (?:la )?oferta|poliza de (?:seguro de )?caucion|seguro de caucion|pagare"
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


# T-233b (D-233-1): lo que el pliego fija y la regla no compara. Un tope o un mínimo («no podrá
# superar», «como mínimo», «hasta»), un monto o un porcentaje fijado para el total, la cotización o
# el CUIT, y una base del porcentaje que no es el total cotizado de la oferta dejan el par sin
# comparar: nunca «cumple».
_LIMIT = re.compile(
    r"\bsuper(?:ar|a|e|en|ara|aran|ando)\b|\bexced\w+|\bmayor(?:es)?\b|\bmenor(?:es)?\b|\bmaxim\w+|\bminim\w+"
    r"|\binferior\w*|\bsuperior\w*|\bal menos\b|\bpor lo menos\b|\btope\b|\blimite\w*"
    # T-240: «hasta» es un tope si lo sigue un valor («hasta $ 500», «hasta 260 módulos», «hasta pesos
    # un millón»: cifra, `$`, moneda o número escrito en letras), no si es un «hasta los cuales» que
    # habla de otra cosa.
    r"|\bhasta\b(?:\W+\w+){0,6}?\W*(?:[\d$]|(?:pesos|dolares|usd|ars|mil|millon\w*|cien\w*|dos|tres"
    r"|cuatro|cinco|seis|siete|ocho|nueve|diez|veinte\w*|treinta|cuarenta|cincuenta|sesenta|setenta"
    r"|ochenta|noventa|doscientos|trescientos|cuatrocientos|quinientos)\b)"
    r"|\bno (?:podra|puede|debera|debe|menos|mas)\b")
# La base del porcentaje de una garantía: lo que se busca después del porcentaje.
_OFFER_BASE = re.compile(
    r"\b(?:cotizad\w*|ofertad\w*)\b"
    r"|\b(?:monto|total|importe|valor|precio|suma)\s+(?:total\s+)?(?:de|del)\s+(?:la\s+|su\s+)?"
    r"(?:oferta|cotizacion)\b|\boferta\s+economica\b")
_OTHER_BASE = re.compile(
    r"presupuesto|adjudic|contrat|renglon|estimad|referencia|oficial|orden de compra|licitad"
    r"|\bbase\b|\bcanon\b|\bpedido\b")
BASE_WINDOW = 90


def _mentions_percent(text):
    folded = fold(text)
    return bool(_PERCENT.search(folded)) or any(
        m.group(1) in _NUMBER_WORDS for m in _WORD_PERCENT.finditer(folded))


# T-240: un porcentaje fija el valor del total o de la cotización solo si modifica el precio
# («descuento del 10 %», «recargo de hasta 5 % sobre el total»); «oferta alternativa del 60 %» o un
# porcentaje de adjudicación hablan de otra cosa.
_PRICE_MODIFIER = re.compile(
    r"descuento|recargo|bonificaci|rebaja|incremento|aumento|reduccion|margen|variacion"
    r"|\biva\b|alicuota|impuesto|\bcotizacion\b"
    r"|\b(?:sobre|del|al) (?:el |la |los |las )?(?:precio|total|monto|importe|valor)")
PERCENT_WINDOW = 50
# T-240 (D-240-2): el impuesto (IVA, alícuota) no es un dato que el Portal confirme.
_TAX = re.compile(r"\biva\b|alicuotas?|impuestos?")


def _percent_on_price(text):
    folded = fold(text)
    spans = [m.span() for m in _PERCENT.finditer(folded)] + [
        m.span() for m in _WORD_PERCENT.finditer(folded) if m.group(1) in _NUMBER_WORDS]
    return any(_PRICE_MODIFIER.search(folded[max(a - PERCENT_WINDOW, 0):b + PERCENT_WINDOW])
               for a, b in spans)


def _percent_base(text):
    """`True` si el pliego dice que el porcentaje es sobre el total cotizado de la oferta; `False`
    si nombra otra base o no se puede leer (T-233b)."""
    folded = fold(text)
    ends = [m.end() for m in _PERCENT.finditer(folded)] + [
        m.end() for m in _WORD_PERCENT.finditer(folded) if m.group(1) in _NUMBER_WORDS]
    if not ends:
        return False
    after = folded[max(ends):max(ends) + BASE_WINDOW]
    after = re.split(r"[.;]\s", after)[0]
    return bool(_OFFER_BASE.search(after)) and not _OTHER_BASE.search(after)


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


# T-240 (H-1, D-240-1): el número de una cláusula («11.10.», «3.15 Texto», «(11.10)», «11.10:») se parece a
# un monto con dos decimales. Un «N.NN» sin `$` es un número de cláusula salvo que haya una señal de
# dinero: una palabra de monto antes («el monto de 11.10») o la moneda después («11.10 pesos»). Es
# también número de cláusula, con señal o sin ella, el que sigue a una palabra de referencia («punto
# 11.10», «puntos 3.10, 3.11 y 3.12», «artículo 18.10»).
_CLAUSE_TOKEN = re.compile(r"\d{1,2}\.\d{1,2}")
_CLAUSE_REFERENCE = re.compile(
    r"\b(?:punto|puntos|clausula|clausulas|articulo|articulos|art|arts|inciso|incisos|apartado"
    r"|apartados|numeral|numerales|item|items|capitulo|seccion|titulo|anexo|anexos|pto)\b\.?\s*"
    r"(?:n[°ºo]\.?\s*|nro\.?\s*)?(?:[\d.]+\s*(?:,|;|\by\b|\be\b|\bo\b|\bal\b|-)\s*)*$")
_MONEY_WORD_BEFORE = re.compile(
    r"\b(?:monto|montos|importe|importes|suma|total|valor|precio|pesos|ars|usd|dolares)\b")
_MONEY_WORD_AFTER = re.compile(r"^\W{0,3}(?:pesos|ars|usd|dolares|u\$s)\b")
MONEY_WINDOW = 25


def _is_clause_number(text, match):
    """`True` si el número que leyó `_MONEY` en `match` es el de una cláusula y no un monto."""
    sign, token = match.groups()
    if sign or not _CLAUSE_TOKEN.fullmatch(token):
        return False
    before = fold(text[max(match.start() - 60, 0):match.start()])
    if _CLAUSE_REFERENCE.search(before):
        return True
    # La señal de dinero se busca en la misma oración, cerca del número.
    sentence = re.split(r"[.;:]\s", before[-MONEY_WINDOW:])[-1]
    if _MONEY_WORD_BEFORE.search(sentence):
        return False
    return not _MONEY_WORD_AFTER.match(fold(text[match.end():match.end() + 12]))


def amounts(text):
    """Los montos que se leen en `text`: los que llevan `$`, separador de miles o dos decimales
    (un número suelto, como un día o un porcentaje, no es un monto, ni lo es el número de una
    cláusula como «11.10.»; T-240, H-1). Argentina: punto de miles y coma decimal."""
    found = []
    text = text or ""
    for match in _MONEY.finditer(text):
        sign, token = match.groups()
        money = bool(sign) or re.search(r"\.\d{3}|[.,]\d{2}$", token)
        if money and _is_clause_number(text, match):
            continue
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
# T-240: el requisito no pide un dato que el Portal pueda comparar (pide un documento de la
# garantía, no un monto): el Portal no decide y queda lo que concluyó el modelo.
NO_PIDE = "no_pide"

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
    if percent is not None and (amounts(text) or not _percent_base(text)):
        return Comparison(
            NO_COMPARABLE, "El pliego fija el porcentaje de la garantía sobre una base que no es "
            "el total cotizado de la oferta, o la base no se puede leer, o suma un monto: el "
            "sistema no lo compara con el Portal.")
    if percent is not None:
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


def _cuit_comparison(portal, text=""):
    """El CUIT del Portal: si el pliego nombra un CUIT, que sea ese; si no, once dígitos (la
    igualdad con el de la oferta la mira la regla)."""
    shown = portal[0].shown
    required = set(cuits(text))
    if required:
        wanted = ", ".join(sorted(required))
        if digits(shown) in required:
            return Comparison(COINCIDE, f"El Portal informa el CUIT {shown}, el que fija el "
                              "pliego.", wanted, shown)
        return Comparison(DIFIERE, f"El pliego fija el CUIT {wanted} y el Portal informa {shown}.",
                          wanted, shown, "distinto")
    size = len(digits(shown))
    if size == 11:
        return Comparison(COINCIDE, f"El Portal informa el CUIT del oferente {shown}, de once "
                          "dígitos.", "11 dígitos", shown)
    return Comparison(DIFIERE, f"El CUIT que informa el Portal ({shown}) tiene {size} dígitos y "
                      "el CUIT tiene once.", "11 dígitos", shown, f"{size} dígitos")


# T-240: lo que pide un requisito sobre el documento de una garantía (no sobre su monto).
_PORTAL_LOAD = re.compile(
    r"\b(?:cargar|cargue|cargado|ingresar|ingrese|consignar|consigne|subir)\b")
_GUARANTEE_DOCUMENT = re.compile(
    r"\bcopias?\b|\boriginal(?:es)?\b|\bmesa de entradas?\b|\bcargar\b|\badjunt\w+")


def _guarantee_document(data, portal, text):
    """El requisito de una garantía que no fija porcentaje ni monto y trata de su documento: si pide
    cargar el documento de una forma de garantía en el Portal y el Portal informa una garantía en
    esa forma, coincide; si pide la copia, el original o la Mesa de Entrada, el Portal no lo
    resuelve (`NO_PIDE`). `None` si no es ese caso (T-240)."""
    from evaluon.assessment import guarantee_form

    folded = fold(text)
    forms = guarantee_form.required_forms(text)
    if (forms and _PORTAL_LOAD.search(folded) and re.search(r"\bportal\b", folded)
            and not re.search(r"\boriginal(?:es)?\b|\bmesa de entradas?\b", folded)
            and guarantee_form.chosen_forms(list(data.guarantees.all())) & forms):
        observed = ", ".join(d.shown for d in portal)
        return Comparison(
            COINCIDE, f"El Portal informa una garantía en la forma que el pliego pide cargar "
            f"(monto {observed}).", "garantía cargada en el Portal", observed)
    if _GUARANTEE_DOCUMENT.search(folded):
        return Comparison(NO_PIDE, "El requisito trata del documento de la garantía y no fija un "
                          "monto ni un porcentaje que el Portal pueda comparar.")
    return None


def compare(kind, offer, data, portal, text, items):
    """Lo que informa el Portal frente a lo que exige el pliego (`Comparison`). «Cumple» solo si el
    valor del Portal coincide con lo que el pliego fija, sobre la base que el pliego dice; si el
    pliego fija algo que no se compara, `NO_COMPARABLE` (T-233b, D-233-1)."""
    folded = fold(text)
    if kind == GARANTIA and required_percent(text) is None and not amounts(text):
        document = _guarantee_document(data, portal, text)
        if document is not None:
            return document
    if _LIMIT.search(folded):
        return Comparison(NO_COMPARABLE, "El pliego fija un tope o un mínimo que el sistema no "
                          "compara con el dato del Portal.")
    if kind == GARANTIA:
        return _guarantee_comparison(data, portal, text)
    if kind == CUIT:
        return _cuit_comparison(portal, text)
    if kind in (TOTAL, COTIZACION) and _TAX.search(folded):
        return Comparison(NO_COMPARABLE, "El pliego nombra un impuesto (IVA o alícuota) y el Portal no "
                          "lo informa: el sistema no lo compara.")
    if kind in (TOTAL, COTIZACION) and (amounts(text) or _percent_on_price(text)):
        return Comparison(NO_COMPARABLE, "El pliego fija un monto o un porcentaje para este dato "
                          "y el sistema no lo compara con el Portal.")
    if kind == TOTAL:
        return _total_comparison(data, portal, text)
    if kind == COTIZACION:
        return _quote_comparison(offer, items)
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
    if comparison.state == NO_PIDE:
        return None
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
