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

T-257 (mesa de comité, A-2 y H6; decisión del 2026-10-12 «Precio del Portal = final con IVA»):

- la regla conserva las condiciones que revisó el modelo y su pregunta, y resuelve solo la condición
  que su dato cubre (`cover`): si queda una sin dato, la celda es «no determinado» con esa condición
  a la vista y la pregunta (`portal_cubre_parte`), no «cumple» ni «falta de coincidencia»;
- el impuesto que el pliego pide incluido en el precio se da por incluido en el precio del Portal
  (criterio de la Comisión, registrado en `facts.criterios` con su versión); una alícuota sigue sin
  compararse; una condición de precio fijo se cubre por ausencia si la lectura fue completa y nada la
  contradice (`criteria.py`);
- con un requisito que habla de la cantidad, se compara la cantidad ofertada con la pedida
  (`cantidad_parcial`: «no determinado» con la diferencia);
- la moneda en que se cotiza la oferta es el total del Portal con su moneda;
- un requisito que pide datos de la garantía que el Portal no guarda (número, compañía) no se da
  por cumplido con la fila de la garantía.

El texto de la cita lo escribe el sistema desde las columnas del Portal, tal cual están en la
fila (nunca el modelo). Un "cumple" por esta regla nunca sale sin la cita del Portal (P3).
"""

import re
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from django.conf import settings

from evaluon.assessment import combine, criteria
from evaluon.assessment.externals import fold
from evaluon.portal.models import PortalLine, PortalOfferData, PortalQuote

FALTA_COINCIDENCIA = "falta_coincidencia"

# T-233 (ADR-0053): `portal_en_portal` (ADR-0043) ya no se emite; el dato del Portal se compara.
RULE_CUMPLE = "portal_cumple"
RULE_NO_CUMPLE = "portal_no_cumple"
RULE_MISMATCH = "portal_falta_coincidencia"
RULE_BOTH = "portal_cita_agregada"
# T-257: el dato del Portal cubre una parte de las condiciones (o no responde a lo que pide el
# pliego) y lo que falta queda a la vista, con la pregunta.
RULE_PARTIAL = "portal_cubre_parte"

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
        r"|propuesta economica"
        # T-257: la moneda en que se cotiza (REQ-102: es requisito) se compara con la del total.
        r"|\bcotizacion\w*\b(?:\W+\w+){0,6}?\W+(?:pesos|dolares|moneda)\b"
        r"|\bmoneda\b(?:\W+\w+){0,3}?\W+cotiz\w*")),
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
# T-240 (D-240-2): la alícuota del impuesto no es un dato que el Portal confirme. T-257 (decisión del
# 2026-10-12): el impuesto incluido en el precio sí, por el criterio del IVA (`criteria.py`).
_TAX = criteria.TAX
_TAX_RATE = re.compile(r"alicuotas?")


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


def amounts(text, *, without_other_concepts=False):
    """Los montos que se leen en `text`: los que llevan `$`, separador de miles o dos decimales
    (un número suelto, como un día o un porcentaje, no es un monto, ni lo es el número de una
    cláusula como «11.10.»; T-240, H-1). Argentina: punto de miles y coma decimal. Con
    `without_other_concepts`, sin los montos rotulados como otro concepto (`_other_concept`)."""
    found = []
    text = text or ""
    for match in _MONEY.finditer(text):
        sign, token = match.groups()
        money = bool(sign) or re.search(r"\.\d{3}|[.,]\d{2}$", token)
        if money and _is_clause_number(text, match):
            continue
        if money and without_other_concepts and _other_concept(text, match):
            continue
        value = _parse_amount(token) if money else None
        if value is not None:
            found.append(value)
    return found


# T-285 (D-283-7, «no comparar magnitudes distintas»; D-42, decisión del 2026-10-15: se comparan el
# valor de la oferta y el dato del Portal de un mismo dato): un monto rotulado como un impuesto, una
# prima, una tasa o un recargo no es el total, el precio ni la garantía que informa el Portal, salvo
# que el mismo rótulo nombre también el total, el precio o la garantía («total con IVA»). El rótulo es
# lo que el texto dice antes del monto, en la misma frase.
_OTHER_CONCEPT = re.compile(
    r"\b(?:iva|i\W?v\W?a|impuestos?|alicuotas?|percepcion\w*|retencion\w*|primas?|premios?"
    r"|sellados?|tasas?|recargos?|comision\w*|intereses)\b")
_SAME_CONCEPT = re.compile(
    r"\b(?:total\w*|precio\w*|importe total|monto total|suma asegurada|monto asegurado"
    r"|monto de la garantia|valor de la garantia|cotizacion\w*)\b")
CONCEPT_WINDOW = 60


def _other_concept(text, match):
    """Si el monto de `match` está rotulado como otro concepto (`_OTHER_CONCEPT`) y su rótulo no
    nombra el total, el precio o la garantía (`_SAME_CONCEPT`)."""
    before = fold(text[max(match.start() - CONCEPT_WINDOW, 0):match.start()])
    label = re.split(r"[;\n]|\.\s", before)[-1]
    return bool(_OTHER_CONCEPT.search(label)) and not _SAME_CONCEPT.search(label)


def cuits(text):
    """Los CUIT (once dígitos, con o sin guiones) que se leen en `text`, solo dígitos."""
    return ["".join(m.groups()) for m in _CUIT.finditer(text or "")]


def offered_values(kind, texts):
    """Los valores de la oferta del mismo tipo que el dato del Portal, leídos del texto literal."""
    values = []
    for text in texts:
        values.extend(cuits(text) if kind == CUIT
                      else amounts(text, without_other_concepts=True))
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
# T-257: la oferta cotiza en el Portal una cantidad menor que la pedida en algún renglón.
PARCIAL = "cantidad_parcial"

# Porcentaje que fija el requisito: «5 %», «5%», «cinco por ciento», «cinco (5) por ciento».
_PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:\(\s*\d+\s*\)\s*)?(?:%|por\s*ciento)")
_WORD_PERCENT = re.compile(r"\b([a-z]+)\s*(?:\(\s*\d+\s*\)\s*)?por\s*ciento")
_NUMBER_WORDS = {
    "uno": 1, "un": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
    "ocho": 8, "nueve": 9, "diez": 10, "quince": 15, "veinte": 20, "treinta": 30,
    "cincuenta": 50, "cien": 100,
}


# T-257 (D-257-5): el Portal trae una lista cerrada de datos (el total y su moneda, el precio y la
# cantidad de cada renglón, la garantía con su tipo, su forma y su monto, y el CUIT). Lo que el
# pliego pida además, aunque se parezca (que la garantía cubra el plazo, su identificador o la
# razón social de quien la emite, la marca de lo ofrecido), el Portal no lo resuelve.
_OTHER_DATA = re.compile(
    r"\bnumeros?\b|\bnro\b|\bcompania\b|\bentidad\b|\bcampos?\b|\baseguradora\b"
    r"|\bemisor\w*|\bemit\w*|\bemite\b|\bidentificador\w*|\bidentificatori\w*|\brazon social\b"
    r"|\bvigencia\b|\bvencimiento\b|\bcubr\w*|\bplazos?\b|\bfirm\w*|\bmarcas?\b|\bmodelos?\b"
    r"|\bdomicilio\b|\bcaracteristicas?\b|\bespecificacion\w*|\bfolletos?\b|\bcatalogos?\b"
    r"|\bmuestras?\b|\borigen\b|\bprocedencia\b")
_PORTAL_LACKS = _OTHER_DATA

# Reverificación de T-257 (decisión del Coordinador, estricta): el Portal resuelve solo lo que pide
# EXACTAMENTE un dato de su lista. Una condición (o, sin condiciones, el requisito) se da por
# respondida por el Portal solo si **todas** sus palabras son de este vocabulario cerrado: las
# palabras de los datos que el Portal trae y las de enlace. Cualquier otra palabra (color, talle,
# referencia, denominación, íntegramente, kilos…) deja la condición sin resolver.
_WORD = re.compile(r"[a-z]+|\d+(?:[.,]\d+)*|%")
_LINKS = set(
    "a al ante con cada como de del desde e el en entre la las lo los o para por que se su sus tanto "
    "u un una uno unos unas y todo todos toda todas dicha dicho dichos misma mismo este esta estos "
    "estas sera seran ser es son debe deben debera deberan deberá realizar realizara realizaran "
    "realizarse efectuar efectuada efectuado efectuarse constituir constituira constituiran "
    "constituida constituido constituirse integrar integrara junto informar informara informaran "
    "indicar indicara indicaran indicando expresar expresarse expresara expresaran expresados "
    "expresadas incluir incluira incluiran incluido incluidos incluida incluidas presentar presentara "
    "presentaran cotizar cotizara cotizaran cotizarse cotizacion cotizaciones cotizado cotizada "
    "cotizados cotizadas ofertar ofertado ofertada ofertados ofertadas oferta ofertas ofrecido "
    "ofrecida ofrecidos ofrecidas oferente oferentes proponente proponentes pertinente portal "
    "plataforma compras equivalente equivalentes economica economicas sobre".split())
_PORTAL_VOCABULARY = set(
    "total totales monto montos importe importes precio precios unitario unitarios unitaria "
    "unitarias valor valores renglon renglones cantidad cantidades totalidad pedida pedidas pedido "
    "pedidos solicitada solicitadas solicitado solicitados requerida requeridas requerido requeridos "
    "indicada indicadas indicado indicados iva impuesto impuestos garantia garantias poliza "
    "caucion pagare fianza aval bancario forma formas tipo porcentaje ciento cuit clave "
    "identificacion tributaria".split())
# Cuarta pasada (P5f): la moneda es un dato del total y de la cotización, no de la garantía.
_CURRENCY_WORDS = set(
    "moneda pesos peso argentinos argentina nacional dolares dolar estadounidenses usd ars".split())
# Cuarta pasada (P5b, P5c): «seguro» solo como «seguro de caución» y «mantenimiento» solo como
# «(garantía de) mantenimiento de (la) oferta»; sueltos son otra cosa (el seguro del bien, su
# mantenimiento) y el Portal no los muestra.
_PHRASES = ((re.compile(r"\bseguros? de caucion\b"), "caucion"),
            (re.compile(r"\bmantenimiento de (?:la |las |su |sus )?ofertas?\b"), "oferta"))
_NUMBER_WORDS_ALL = set(
    "uno un una dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince "
    "dieciseis diecisiete dieciocho diecinueve veinte veinticinco treinta cuarenta cincuenta sesenta "
    "setenta ochenta noventa cien ciento doscientos trescientos cuatrocientos quinientos mil millon "
    "millones".split())


# Los verbos de enlace, por su raíz (cualquier tiempo): cotizar, ofertar, ofrecer, realizar, efectuar,
# constituir, integrar, informar, indicar, expresar, incluir, presentar, consignar, deber.
_LINK_STEMS = ("cotiz", "ofert", "ofrec", "realiz", "efectu", "constitu", "expres", "inclu", "consign",
               "deb")
# Las formas de los verbos cuya raíz se confunde con otras palabras («integramente», «informe»,
# «indicador», «presente»): una por una.
_LINK_FORMS = set(
    "integrar integrara integraran integrada integrado integradas integrados integre integren "
    "informar informara informaran informada informado informadas informados informe informen "
    "indicar indicara indicaran indicando indicada indicado indicadas indicados indique indiquen "
    "presentar presentara presentaran presentarse presentada presentado presentadas presentados "
    "presente presenten".split())
_BE = set("es son sea sean sera seran ser esta estan estara estaran estar".split())


# Lo que antecede a la exigencia sin pedir nada: la remisión a una norma («conforme lo previsto en
# los artículos…, sus complementarias y/o modificatorias,») y el umbral de monto que hace exigible la
# garantía («Si la oferta superase el monto indicado en la sub-cláusula anterior,»).
_LEGAL_REFERENCE = re.compile(
    r"(?:conforme(?: a| con)?|de acuerdo con|segun) (?:lo (?:previsto|establecido|dispuesto) en )?"
    r"[^.]*?(?:complementarias|modificatorias|vigentes?)\s*,\s*")
_AMOUNT_THRESHOLD = re.compile(
    r"^\W*(?:\d+(?:\.\d+)*\.?\s*)?si (?:la oferta|el monto de la oferta|el total de la oferta)"
    r" (?:super|exced)\w+ [^,]*,\s*")


def requirement_core(text):
    """El texto del requisito sin la remisión a la norma ni el umbral de monto que lo hacen exigible:
    lo que se mira contra la lista cerrada del Portal."""
    folded = fold(text)
    folded = _AMOUNT_THRESHOLD.sub("", folded)
    return _LEGAL_REFERENCE.sub("", folded)


def asks_only_portal_data(text, kind=None):
    """Si el texto pide solo datos de la lista cerrada del Portal (todas sus palabras son del
    vocabulario cerrado), sin ninguna otra exigencia. La moneda vale solo para el total y la
    cotización (`kind`); «seguro» y «mantenimiento», solo dentro de sus frases cerradas."""
    folded = fold(text)
    for pattern, token in _PHRASES:
        folded = pattern.sub(token, folded)
    currency = kind in (TOTAL, COTIZACION, None) and kind != GARANTIA
    words = _WORD.findall(folded)
    return bool(words) and all(
        word in _LINKS or word in _PORTAL_VOCABULARY or word in _NUMBER_WORDS_ALL or word in _BE
        or word in _LINK_FORMS or (currency and word in _CURRENCY_WORDS)
        or word.startswith(_LINK_STEMS) or word == "%" or word[0].isdigit() for word in words)

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
    # Los criterios de la Comisión que se aplicaron para llegar al estado (T-257, P6).
    criteria: tuple = ()

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
            if _INDIVIDUALIZED.search(folded) and _OTHER_DATA.search(folded):
                # T-257 (H-C2-6): el pliego pide datos de la garantía que `portal_guarantee` no
                # guarda (el número del documento, la compañía): el Portal no los muestra.
                return Comparison(
                    NO_COMPARABLE, "El pliego pide datos de la garantía que el Portal no informa "
                    "(el Portal trae su tipo, su forma y su monto).")
            if _INDIVIDUALIZED.search(folded):
                # «Paso 4 Ingreso de Garantía» (T-175): lo que el pliego pide es que la garantía
                # esté individualizada en el Portal, y la fila de `portal_guarantee` lo muestra.
                observed = ", ".join(_money(d.value) for d in portal)
                return Comparison(
                    COINCIDE, f"La garantía está individualizada en el Portal ({observed}), "
                    "como pide el pliego.", "garantía individualizada", observed)
            # T-285 (D-283-7): el motivo dice lo que pasa sin dar a entender que el requisito fija un
            # porcentaje que el sistema no leyó.
            return Comparison(NO_COMPARABLE, "El requisito no fija para la garantía un porcentaje "
                              "ni un monto que se compare con el que informa el Portal.")
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


# T-257 (H6 de las omisiones, R87; D-257-5): el requisito que pide la cantidad de cada renglón, dicho
# de cualquiera de estas formas.
_QUANTITY = re.compile(
    r"\bcantidad(?:es)?\b|\btotalidad\b|\btotal de lo (?:solicitado|pedido|requerido)\b"
    r"|\bunidades\b|\bsin fraccionar\b|\bcomplet[oa]s?\b|\bparcial\w*")


def _quote_comparison(offer, items, text=""):
    """Todos los renglones del procedimiento (o los de la fila) con precio en el Portal; si el
    requisito habla de la cantidad, además la cantidad ofertada contra la pedida (T-257)."""
    lines = {line.number: line.quantity
             for line in PortalLine.objects.filter(procedure_id=offer.procedure_id)}
    wanted = set(items) if items else set(lines)
    if not wanted:
        return Comparison(NO_COMPARABLE, "El Portal no informa los renglones del procedimiento.")
    quotes = {q.line.number: q for q in PortalQuote.objects.filter(
        offer=offer, line__procedure_id=offer.procedure_id, price__isnull=False)
        .select_related("line")}
    quoted = set(quotes)
    missing = sorted(wanted - quoted)
    names = ", ".join(str(n) for n in sorted(wanted))
    if not missing and _QUANTITY.search(fold(text)):
        pairs = [(n, quotes[n].quantity, lines.get(n)) for n in sorted(wanted)]
        short = [(n, got, need) for n, got, need in pairs
                 if got is not None and need is not None and got < need]
        shown = "; ".join(f"renglón {n}: {_plain(got)} de {_plain(need)}"
                          for n, got, need in pairs if got is not None and need is not None)
        if short:
            return Comparison(
                PARCIAL, "El Portal informa una cantidad menor que la pedida en "
                + "; ".join(f"el renglón {n} ({_plain(got)} de {_plain(need)})"
                            for n, got, need in short) + ".", names, shown,
                ", ".join(str(n) for n, _, _ in short))
        if shown:
            return Comparison(COINCIDE, f"El Portal informa el precio y la cantidad pedida de "
                              f"todos los renglones que exige el pliego ({shown}).", names, shown,
                              "")
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
    pliego fija algo que no se compara, `NO_COMPARABLE` (T-233b, D-233-1).

    T-285 (D-283-6, c): el umbral de monto que hace exigible el requisito, dicho al comienzo de la
    oración («si la oferta supera el monto de…, …», `_AMOUNT_THRESHOLD`), dice cuándo se exige y no es
    un tope ni un monto del dato: no se mira para comparar (como en `requirement_core`)."""
    if _AMOUNT_THRESHOLD.search(fold(text)):
        text = _AMOUNT_THRESHOLD.sub("", fold(text))
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
    tax = kind in (TOTAL, COTIZACION) and bool(_TAX.search(folded))
    if tax and (_TAX_RATE.search(folded) or _mentions_percent(text)):
        # T-240 (D-240-2): una alícuota o un porcentaje del impuesto no es un dato del Portal.
        return Comparison(NO_COMPARABLE, "El pliego fija la alícuota del impuesto y el Portal no "
                          "la informa: el sistema no la compara.")
    if kind in (TOTAL, COTIZACION) and (amounts(text) or _percent_on_price(text)):
        return Comparison(NO_COMPARABLE, "El pliego fija un monto o un porcentaje para este dato "
                          "y el sistema no lo compara con el Portal.")
    if kind == TOTAL:
        found = _total_comparison(data, portal, text)
    elif kind == COTIZACION:
        found = _quote_comparison(offer, items, text)
    else:
        return Comparison(NO_COMPARABLE, "El requisito pide otro dato.")
    if tax and found.state == COINCIDE:
        # T-257, decisión del 2026-10-12 «Precio del Portal = final con IVA»: el impuesto que el
        # pliego pide incluido en el precio se da por incluido en el precio del Portal.
        return replace(found, detail=f"{found.detail} {criteria.NOTES[criteria.IVA]}",
                       criteria=(criteria.IVA,))
    return found


def _facts_of(combined, kind, portal, matching):
    return {**combined.facts, "portal": {
        "tipo": kind, "valor": (matching or portal)[0].shown,
        "valores": [d.shown for d in portal],
        "items": sorted({d.item for d in portal})}}


# --- Las condiciones del modelo que cubre el dato del Portal (T-257; A-2 del comité) ------------

# Qué condición responde el dato del Portal, por clase de dato (texto de la condición sin acentos):
# la lista cerrada de lo que el Portal trae (D-257-5). Una condición que nombra además otro dato
# (`_OTHER_DATA`) no se cubre.
_COVERS = {
    GARANTIA: re.compile(r"\bgarantia\b|\bpoliza\b|\bpagare\b|\bcaucion\b|\bfianza\b|\baval\b"
                         r"|\bmonto\b|\bimporte\b|\bpor ciento\b|%|\bforma\b|\btipo\b"),
    TOTAL: re.compile(r"\btotal\b|\bmoneda\b|\bpesos?\b|\bdolar\w*|\busd\b|\bars\b"),
    COTIZACION: re.compile(r"\bcotiz\w*|\bprecios?\b|\bvalor unitario\b|\brenglon\w*"
                           r"|\bcantidad\w*|\btotalidad\b"),
    CUIT: re.compile(r"\bcuit\b"),
}


def _cited(item):
    cite = item.get("cita")
    return isinstance(cite, dict) and cite.get("tipo") == "oferta"


def criteria_doubt(pair, records):
    """Por qué no rigen la ausencia ni el IVA en esta celda (D-257-2, D-257-3), o `""`: la lectura
    incompleta, una duda (sin corroborar, sin cita, contradicción), algo que la contradice, o un
    texto de la oferta que el modelo citó y que no sostiene una condición que cumple (en el grupo y
    no en la condición)."""
    combined = pair.combined
    if not criteria.complete(combined):
        return "la lectura de la oferta está incompleta"
    if combined.doubt in criteria.DOUBTFUL or combined.proposed:
        return "hay un texto dudoso o el contraste no corroboró una conclusión"
    if criteria.contradicted(pair):
        return "un texto de la oferta lo contradice"
    backing = {r["cita"].get("texto", "") for r in records
               if r.get("resultado") == "cumple" and _cited(r)}
    stray = [t for t in criteria.offer_citations(pair) if t not in backing]
    if stray:
        return "el modelo citó un texto de la oferta que no sostiene una condición"
    return ""


def threshold_condition(condition, requirement_text):
    """Si la condición es el umbral de monto que hace exigible el requisito («que la oferta supere el
    monto…»), dicho al comienzo de la oración del pliego (`_AMOUNT_THRESHOLD`, el mismo que
    `requirement_core` quita antes de mirar la lista cerrada del Portal): T-285, D-283-6 (c)."""
    if not _AMOUNT_THRESHOLD.search(fold(requirement_text or "")):
        return False
    return bool(_THRESHOLD_CONDITION.search(fold(condition or "")))


# La condición que repite ese umbral: «(que / si) la oferta (o su monto, su total) supere / exceda…».
_THRESHOLD_CONDITION = re.compile(
    r"^\W*(?:que |si |cuando |en caso de que )?(?:la oferta|el monto de la oferta|el total de la "
    r"oferta|el importe de la oferta|su oferta|el monto ofertado|el monto cotizado) "
    r"(?:\w+ ){0,2}?(?:super|exced)\w*\b")


def cover(records, kind, comparison, combined, pair=None, ctx=None, requirement_text=""):
    """Las condiciones del modelo (`records`) con las que cubre el dato del Portal, el criterio del
    IVA o la ausencia marcadas «cumple» (`cubierta_por`), y los criterios usados.

    - El Portal cubre solo una condición que pide EXACTAMENTE un dato de su lista cerrada: de su
      clase (`_COVERS`), con todas sus palabras del vocabulario cerrado (`asks_only_portal_data`) y
      sin otro dato (`_OTHER_DATA`), también si es la única (reverificación de T-257).
    - T-285 (D-283-6, c; REQ-103): con una garantía del Portal que coincide con lo que exige el
      pliego, la condición que repite el umbral de monto que hace exigible la garantía
      (`threshold_condition`) queda cubierta: el umbral dice cuándo se exige la garantía, no algo
      que la oferta tenga que mostrar, y la garantía que se exige está en el Portal
      (`cubierta_por` «umbral»).
    - El IVA rige solo sin duda (`criteria_doubt`), para una condición sin cita propia, y si ni los
      documentos ni lo que el modelo citó o anotó dicen nada del impuesto o del precio
      (`criteria.price_talk`). La ausencia ya no cubre condiciones sueltas: rige solo la de la
      oración entera (`absence.py`).
    - Una condición que el modelo dio por «no cumple» no se cubre."""
    pair = pair if pair is not None else SimpleNamespace(combined=combined, groups=[],
                                                         conditions={})
    doubt = criteria_doubt(pair, records)
    talk = criteria.price_talk(pair, ctx)
    iva_ok = criteria.IVA in comparison.criteria and not doubt and not talk
    if not records:
        return [], [criteria.IVA] if iva_ok else []
    shown, used = [], []
    for item in records:
        how = None
        text = fold(item.get("condicion", ""))
        if item.get("resultado") not in ("cumple", "no_cumple"):
            if criteria.names_tax(text):
                how = criteria.IVA if iva_ok and not _cited(item) and not (
                    item.get("dato") or "").strip() else None
            elif (_COVERS[kind].search(text) and asks_only_portal_data(text, kind)
                  and not _OTHER_DATA.search(text)):
                how = "portal"
            elif (kind == GARANTIA and comparison.state == COINCIDE
                  and threshold_condition(item.get("condicion", ""), requirement_text)):
                how = "umbral"
        if how:
            item = {**item, "resultado": "cumple", "cubierta_por": how}
            if how not in ("portal", "umbral"):
                used.append(how)
        shown.append(item)
    if iva_ok:
        # El pliego pide el impuesto incluido aunque el modelo no lo haya separado como condición: el
        # criterio rige igual sobre el precio del Portal.
        used.append(criteria.IVA)
    return shown, [name for name in (criteria.IVA, criteria.ABSENCE) if name in used]


def _missing(records):
    """Qué condición quedó sin dato, para la explicación (REQ-104)."""
    names = [r.get("condicion", "").strip(" .") for r in records
             if r.get("resultado") != "cumple"]
    if not names:
        return ""
    word = "la condición" if len(names) == 1 else "las condiciones"
    return f"Falta el dato de {word}: " + "; ".join(f"«{n}»" for n in names) + "."


def _missing_question(records, informed=""):
    """La pregunta a la Comisión por lo que falta (REQ-105), escrita por el código. Con `informed`
    nombra también el dato del Portal que sí hay (REQ-120)."""
    names = [r.get("condicion", "").strip(" .") for r in records
             if r.get("resultado") != "cumple"]
    if not names:
        return ""
    joined = " y ".join(f"«{n}»" for n in names)
    word = "la condición" if len(names) == 1 else "las condiciones"
    known = f"El Portal informa {informed} y no lo responde" if informed else (
        "El dato del Portal no lo responde")
    return (f"¿Cómo resuelve la Comisión {word} {joined}? {known}, y la oferta no lo trae.")


def _condition_name(records, text):
    """La condición que queda abierta, para la pregunta (REQ-120): las del modelo que no se
    cumplieron o, si no hay, el requisito del pliego."""
    names = [r.get("condicion", "").strip(" .") for r in records
             if r.get("resultado") != "cumple" and r.get("condicion", "").strip(" .")]
    if names:
        return " y ".join(f"«{n}»" for n in names)
    return f"«{combine.clip(text, 160)}»"


def _asked_or(combined, fallback):
    """La pregunta del modelo si se dirige a la Comisión y, si no, `fallback` (REQ-105)."""
    asked = " ".join((combined.question or "").split())
    return asked if asked and not combine.asks_the_offeror(asked) else fallback


def _open_question(combined, name, why):
    """La pregunta de una celda que el Portal deja «no determinado» (REQ-120, T-277): la del modelo
    si se dirige a la Comisión y, si no, una que nombra la condición abierta y el dato del Portal
    que sí hay (`why` lo dice)."""
    return _asked_or(combined, f"¿Cómo resuelve la Comisión {name}? {why}".strip())


def _offer_position(found):
    """Una cita de la oferta para la pregunta: el texto con su documento y página (si se conocen)."""
    document = getattr(getattr(found, "document", None), "title", "")
    page = getattr(found, "page", None)
    where = ", ".join(part for part in (document, f"página {page}" if page else "") if part)
    return f"«{combine.clip(found.text, 200)}»" + (f" ({where})" if where else "")


def _portal_position(data):
    """El dato del Portal para la pregunta: el valor con el enlace de la página de origen y la fecha
    en que se consultó (`PortalItem.page`)."""
    from evaluon.portal.models import PortalItem

    parts = []
    for datum in data:
        item = PortalItem.objects.filter(pk=datum.item).select_related("page").first()
        source = ""
        if item is not None:
            fetched = item.page.fetched_at
            source = (f" (enlace {item.page.url}, consultado el {fetched:%d/%m/%Y})")
        parts.append(f"{datum.shown}{source}")
    return "; ".join(parts)


def _two_positions_question(text, offered, offer_cites, data):
    """La pregunta de la falta de coincidencia (ADR-0053, decisión 4, enmienda del 2026-10-15;
    REQ-120): muestra las dos posturas, el valor de la oferta con su cita y el dato del Portal con su
    enlace y fecha, señala la contradicción y pregunta cuál rige. Va a la Comisión."""
    cited = "; ".join(_offer_position(found) for found in offer_cites)
    return (f"¿Cuál rige para {_condition_name([], text)}? Las dos fuentes se contradicen. La oferta "
            f"dice {offered}" + (f" en {cited}" if cited else "") + ". El Portal informa "
            f"{_portal_position(data)}.")


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
        offer_cites = _merge_offer(combined, located)
        return replace(
            combined, outcome=combine.OUT_NO_DETERMINADO, doubt=FALTA_COINCIDENCIA,
            exigence=combined.exigence, citations=offer_cites, portal=cites, ask=True,
            question=_two_positions_question(text, offered, offer_cites, portal),
            explanation=explanation,
            facts={**facts, "regla": RULE_MISMATCH, "oferta_valor": offered, **extra})

    data = PortalOfferData.objects.filter(offer=ctx.offer).first()
    comparison = compare(kind, ctx.offer, data, portal, text, items)
    if comparison.state == NO_PIDE:
        return None
    facts = {**facts, "comparacion": comparison.facts()}
    informed = ", ".join(d.shown for d in portal)
    from_offer = combined.outcome in (combine.OUT_CUMPLE, combine.OUT_NO_CUMPLE)
    # T-257 (A-2 del comité): las condiciones que revisó el modelo quedan, con la que cubre el dato
    # del Portal (o un criterio de la Comisión) marcada; la pregunta del modelo queda.
    records = criteria.conditions_of(pair)

    def undetermined(why):
        kept = {"condiciones": records} if records else {}
        return replace(
            combined, outcome=combine.OUT_NO_DETERMINADO, doubt=FALTA_COINCIDENCIA,
            citations=_merge_offer(combined, located), portal=cites, ask=True,
            question=_open_question(combined, _condition_name(records, text), why),
            explanation=f"Falta coincidencia: {why} La Comisión verifica cuál rige.",
            facts={**facts, **kept, "regla": RULE_MISMATCH})

    if comparison.state == NO_COMPARABLE:
        if from_offer:
            # La oferta ya concluyó con su propio texto: queda y se agrega la cita del Portal.
            return replace(combined, portal=cites, facts={**facts, "regla": RULE_BOTH})
        pending = [r for r in records if r.get("resultado") != "cumple"]
        if combined.outcome == combine.OUT_NO_DETERMINADO and (
                combined.doubt not in ("", combine.NO_DATA) or (records and not pending)):
            # T-285 (D-283-6, c; REQ-103): el dato del Portal no responde a este requisito, así que no
            # cambia lo que dejó la lectura: el motivo (un contraste que no corroboró, una
            # contradicción, una cita que no se ubicó) y su pregunta quedan; se agrega la cita.
            return replace(combined, portal=cites, facts={**facts, "regla": RULE_BOTH})
        if records:
            # El dato del Portal no responde a lo que pide el pliego: quedan las condiciones del
            # modelo, con lo que falta y su pregunta (no es una diferencia con el Portal).
            note = _missing(records)
            return replace(
                combined, outcome=combine.OUT_NO_DETERMINADO, doubt=combine.NO_DATA,
                citations=_merge_offer(combined, located), portal=cites, ask=True,
                question=_asked_or(combined, _missing_question(records, informed)),
                explanation=" ".join(part for part in (
                    f"El Portal informa {informed}. {comparison.detail}", note) if part),
                facts={**facts, "condiciones": records, "regla": RULE_PARTIAL})
        return undetermined(f"el Portal informa {informed}. {comparison.detail} No se puede "
                            "comparar con el pliego.")
    if comparison.state == PARCIAL:
        return undetermined(comparison.detail)
    if comparison.state == COINCIDE:
        if combined.outcome == combine.OUT_NO_CUMPLE:
            return undetermined(
                comparison.detail + " El texto de la oferta concluyó que no cumple.")
        shown, used = cover(records, kind, comparison, combined, pair, ctx, requirement_text=text)
        if criteria.IVA in comparison.criteria and criteria.IVA not in used and not records:
            # El pliego pide el impuesto incluido y el criterio del IVA no rige (la oferta dice algo
            # del impuesto o de un ajuste, o hay una duda): el Portal no lo resuelve (D-257-3).
            return replace(
                combined, outcome=combine.OUT_NO_DETERMINADO, doubt=combine.NO_DATA,
                portal=cites, ask=True,
                question=_asked_or(combined, (
                    "¿El precio de la oferta incluye el impuesto que pide el pliego? El Portal "
                    f"informa {informed}; la oferta dice algo sobre el impuesto o el ajuste del "
                    "precio, o hay una duda.")),
                explanation=f"Fuente: Portal, para lo que su dato cubre. {comparison.detail} El "
                            "criterio del IVA no rige: la oferta dice algo sobre el impuesto o el "
                            "ajuste del precio, o hay una duda.",
                facts={**facts, "regla": RULE_PARTIAL})
        # El pliego pide además un dato que el Portal no trae; sin las condiciones del modelo,
        # decide la lista de lo que el Portal SÍ trae (reverificación de T-257): el Portal no da
        # «cumple». Si la oferta ya concluyó «cumple» con su texto (y el contraste lo corroboró),
        # queda su conclusión con la cita del Portal agregada.
        # Tercera pasada (bloqueante): el Portal decide mirando la ORACIÓN DEL PLIEGO, no las
        # condiciones del modelo: si el requisito pide cualquier cosa fuera de la lista cerrada de lo
        # que el Portal trae, no hay «cumple», digan lo que digan las condiciones.
        asks_more = bool(_OTHER_DATA.search(fold(text))) or not asks_only_portal_data(
            requirement_core(text), kind)
        if asks_more and combined.outcome == combine.OUT_CUMPLE:
            return replace(combined, portal=cites, facts={**facts, "regla": RULE_BOTH})
        extra = {"condiciones": shown} if shown else {}
        if used:
            extra["criterios"] = [criteria.record(name, **(
                {"documentos_leidos": criteria.documents_read(ctx)}
                if name == criteria.ABSENCE else {})) for name in used]
        pending = [r for r in shown if r.get("resultado") != "cumple"]
        if pending or asks_more:
            # El dato del Portal cubre una parte: lo que falta queda a la vista, con su pregunta.
            asked = (_asked_or(combined, "") if not any(r.get("cubierta_por") for r in shown)
                     else "")
            more = "" if pending else " El pliego pide además un dato que el Portal no trae."
            return replace(
                combined, outcome=combine.OUT_NO_DETERMINADO, doubt=combine.NO_DATA,
                portal=cites, ask=True,
                question=asked or _missing_question(shown, informed) or (
                    f"¿Cómo resuelve la Comisión lo que pide {_condition_name(shown, text)} además "
                    f"del dato del Portal? El Portal informa {informed}."),
                explanation=f"Fuente: Portal, para lo que su dato cubre. {comparison.detail} "
                            f"{_missing(shown)}{more}".strip(),
                facts={**facts, **extra, "regla": RULE_PARTIAL})
        note = (f"{combined.explanation} " if combined.outcome == combine.OUT_CUMPLE
                and combined.explanation else "")
        absent = (" " + criteria.absence_note(criteria.documents_read(ctx), "de "
                  + "; ".join(f"«{r['condicion']}»" for r in shown
                              if r.get("cubierta_por") == criteria.ABSENCE))
                  if criteria.ABSENCE in used else "")
        return replace(
            combined, outcome=combine.OUT_CUMPLE, doubt="", portal=cites, question="",
            explanation=f"{note}Fuente: Portal. {comparison.detail}{absent}",
            facts={**facts, **extra, "regla": RULE_CUMPLE})
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
