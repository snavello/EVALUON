"""Ítem `oferta` (T-143; REQ-047, REQ-048, REQ-049, REQ-051).

Si las ofertas ya están abiertas, se baja el acta de apertura (URL directa) y el cuadro
comparativo (envío de formulario de ASP.NET), se guardan tal cual (`portal_page`) y se
propone un ítem por oferente (agrupado por CUIT), con su total, su garantía y el precio y la
cantidad que ofreció en cada renglón. Una parte que no se puede bajar o leer queda como
anomalía y no frena el resto (carga a mano, REQ-051).

Al cargar el ítem aprobado: `register_offer` de la 008 da de alta la oferta (si un operador ya
la había registrado a mano con el mismo nombre, se asocia a esa); lo que la 008 no tiene dónde
guardar va a `portal_offer_data` y `portal_quote`, con el ítem de origen. Los documentos de la
oferta no son públicos: se cargan a mano con `offers.load_document`, que no se toca.

Una oferta puede tener varias garantías (`portal_guarantee`). Si el ítem es un cambio de una
oferta ya cargada desde el Portal, `load` actualiza lo cargado y deja el antes y el después en el
registro (REQ-050). Anomalías: el precio por la cantidad no da el total del renglón, o el mismo
CUIT figura con nombres distintos.
"""

import hashlib
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from urllib.parse import urljoin

from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.offers.models import Offer
from evaluon.offers.services.offers import register_offer
from evaluon.portal.client import PortalError
from evaluon.portal.importers import Draft, jsonable
from evaluon.portal.models import (
    ItemKind,
    LoadedModel,
    PageKind,
    PortalGuarantee,
    PortalLine,
    PortalOfferData,
    PortalPage,
    PortalQuote,
)
from evaluon.portal.parsing.acta import parse_acta
from evaluon.portal.parsing.cuadro import parse_cuadro

KIND = ItemKind.OFERTA


def _fetch(context, document):
    """Baja un documento de la página (URL directa o envío de formulario). Devuelve la
    respuesta; los errores de red o de estado llegan como `PortalError`."""
    if document.get("como") == "url" and document.get("url"):
        return context.client.get(urljoin(context.link.url, document["url"]))
    return context.client.submit_form(
        context.link.url, bytes(context.page.content),
        {"__EVENTTARGET": document["target"], "__EVENTARGUMENT": document.get("argumento") or ""},
    )


def _download(context, document, kind, label):
    """Baja y guarda una página; devuelve `(PortalPage, bytes)` o `None` con la anomalía."""
    if not document:
        return None
    try:
        response = _fetch(context, document)
    except PortalError as error:
        context.anomalies.append({
            "parte": label, "motivo": f"no se pudo bajar: {error}. Cargue las ofertas a mano.",
        })
        return None
    page = PortalPage.objects.create(
        link=context.link, exploration=context.exploration, kind=kind, url=response.url,
        sha256=hashlib.sha256(response.body).hexdigest(), content=response.body,
    )
    return page, response.body


def explore(context):
    parsed = context.parsed
    if parsed.acta is None and parsed.cuadro is None:
        return []
    acta_page = _download(context, parsed.acta, PageKind.ACTA, "acta de apertura")
    cuadro_page = _download(context, parsed.cuadro, PageKind.CUADRO, "cuadro comparativo")
    acta = parse_acta(acta_page[1]) if acta_page else None
    cuadro = parse_cuadro(cuadro_page[1]) if cuadro_page else None
    for source, label in ((acta, "acta de apertura"), (cuadro, "cuadro comparativo")):
        for issue in (source.issues if source else []):
            context.anomalies.append({"parte": label, "motivo": issue})

    bidders = {}  # CUIT -> datos, en el orden del acta y después los que solo están en el cuadro
    for offer in (acta.offers if acta else []):
        bidders[offer.cuit] = {"acta": offer, "cuadro": None}
    for bidder in (cuadro.bidders if cuadro else []):
        bidders.setdefault(bidder.cuit, {"acta": None, "cuadro": None})["cuadro"] = bidder
    origin = acta_page or cuadro_page
    drafts = []
    for cuit, found in bidders.items():
        drafts.append(_draft(context, cuit, found, cuadro, acta_page, cuadro_page, origin[0]))
    declared = parsed.data.get("ofertas_confirmadas")
    if declared is not None and acta is not None and declared != len(acta.offers):
        context.anomalies.append({
            "parte": "acta de apertura",
            "motivo": (f"la página del proceso dice {declared} ofertas confirmadas y el acta "
                       f"trae {len(acta.offers)}"),
        })
    return drafts


def _draft(context, cuit, found, cuadro, acta_page, cuadro_page, page):
    offer, bidder = found["acta"], found["cuadro"]
    notes = []
    if offer is None and acta_page:
        notes.append("el oferente figura en el cuadro comparativo y no en el acta")
    if bidder is None and cuadro_page:
        notes.append("el oferente figura en el acta y no en el cuadro comparativo")
    name = offer.bidder if offer else bidder.bidder
    total = offer.total if offer and offer.total is not None else (bidder.total if bidder else None)
    if offer and bidder and offer.total is not None and bidder.total is not None \
            and offer.total != bidder.total:
        notes.append(f"el total del acta ({offer.total}) y el del cuadro comparativo "
                     f"({bidder.total}) difieren")
    guarantees = offer.guarantees if offer else []
    if offer and bidder and not _same_name(offer.bidder, bidder.bidder):
        notes.append(f"el CUIT figura con nombres distintos: «{offer.bidder}» en el acta y "
                     f"«{bidder.bidder}» en el cuadro comparativo")
    quotes, taken = [], set()
    for quote in (cuadro.quotes if cuadro else []):
        if quote["cuit"] != cuit:
            continue
        if quote["renglon"] in taken:
            notes.append(f"el renglón {quote['renglon']} trae más de una alternativa: "
                         "se toma la primera")
            continue
        taken.add(quote["renglon"])
        line_total = quote["total"]
        if line_total is not None and abs(quote["precio"] * quote["cantidad"] - line_total) \
                > Decimal("0.01"):
            notes.append(f"renglón {quote['renglon']}: el precio ({quote['precio']}) por la "
                         f"cantidad ({quote['cantidad']}) no da el total del renglón "
                         f"({line_total})")
        quotes.append({"renglon": quote["renglon"], "alternativa": quote["alternativa"],
                       "precio": quote["precio"], "cantidad": quote["cantidad"],
                       "total_renglon": quote["total"]})
    if cuadro_page and not quotes:
        notes.append("el cuadro comparativo no trae cotizaciones de este oferente")
    for note in notes:
        context.anomalies.append({"parte": f"oferta {cuit}", "motivo": note})
    damaged = (offer.damaged if offer else False) or (bidder.damaged if bidder else False)
    payload = {
        "oferente": name, "cuit": cuit,
        "confirmada": offer.confirmed_on if offer else None,
        "moneda": offer.currency if offer else "",
        "total": total, "total_cuadro": bidder.total if bidder else None,
        "garantias": guarantees, "cotizaciones": quotes,
        "fuentes": [label for label, got in (("acta", acta_page), ("cuadro", cuadro_page))
                    if got],
        "anomalias": notes,
    }
    return Draft(ItemKind.OFERTA, f"oferta:{cuit}", jsonable(payload),
                 ["oferente"] if damaged else [], page=page)


def _same_name(a, b):
    return " ".join(a.split()).casefold() == " ".join(b.split()).casefold()


def _words(name):
    """Palabras de un nombre sin acentos ni signos y en minúsculas (para emparejar)."""
    text = unicodedata.normalize("NFD", name or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    text = text.replace(".", "").replace("'", "")  # S.R.L. = SRL; D'Alessio = DAlessio
    return "".join(c if c.isalnum() else " " for c in text).split()


@dataclass
class Match:
    """Propuesta de emparejar una oferta del Portal con una ya cargada (T-174)."""
    offer: object = None
    how: str = ""  # "cuit", "nombre" o "" si no se empareja
    note: str = ""  # por qué no se empareja o qué difiere (falta de coincidencia)


def match_offer(procedure, cuit, name):
    """Busca la oferta ya cargada del procedimiento que corresponde a la del Portal.

    1) Por CUIT, si la oferta cargada lo tiene (lo trae su carga desde el Portal).
    2) Si no, por nombre normalizado igual o, si todas las palabras del nombre cargado están
    en el del Portal, siempre que haya un solo candidato. Con dos candidatos posibles no se
    empareja. Una oferta cargada con otro CUIT no es candidata: se informa como falta de
    coincidencia. Solo propone; no escribe nada."""
    offers = list(Offer.objects.filter(procedure=procedure).order_by("number"))
    cuits = dict(PortalOfferData.objects.filter(offer__in=offers).values_list("offer_id", "cuit"))
    for offer in offers:
        if cuits.get(offer.pk) == cuit:
            return Match(offer, "cuit")
    portal = _words(name)
    exact, partial, other_cuit = [], [], []
    for offer in offers:
        words = _words(offer.bidder)
        if not words:
            continue
        if words == portal:
            kind = exact
        elif set(words) <= set(portal):
            kind = partial
        else:
            continue
        (other_cuit if offer.pk in cuits else kind).append(offer)
    for candidates in (exact, partial):
        if len(candidates) == 1:
            return Match(candidates[0], "nombre")
        if len(candidates) > 1:
            names = "; ".join(o.bidder for o in candidates)
            return Match(note=f"hay más de una oferta cargada que podría ser esta ({names}): "
                              "no se empareja, asócielas a mano")
    if other_cuit:
        names = "; ".join(f"{o.bidder} (CUIT {cuits[o.pk]})" for o in other_cuit)
        return Match(note=f"falta de coincidencia: el nombre se parece al de {names}, pero el "
                          f"CUIT del Portal ({cuit}) es otro; no se empareja")
    return Match()


def proposal_match(item):
    """Para la pantalla de aprobación: a qué oferta cargada se asociaría el ítem."""
    return match_offer(item.proposal.link.procedure, item.payload["cuit"],
                       item.payload["oferente"]) if item.proposal.link.procedure_id else Match()


def _snapshot(offer_data):
    """Lo cargado de una oferta, para el registro de un cambio (P6)."""
    return jsonable({
        "total": offer_data.total, "moneda": offer_data.currency,
        "confirmada": offer_data.confirmed_on,
        "garantias": [{"tipo": g.guarantee_type, "forma": g.guarantee_form, "monto": g.amount}
                      for g in offer_data.guarantees.all()],
        "cotizaciones": [{"renglon": q.line.number, "precio": q.price, "cantidad": q.quantity}
                         for q in PortalQuote.objects.filter(offer=offer_data.offer)
                         .select_related("line").order_by("line__number")],
        "item": offer_data.item_id,
    })


def _write_guarantees(offer_data, guarantees, item):
    PortalGuarantee.objects.bulk_create(
        PortalGuarantee(offer_data=offer_data, guarantee_type=g.get("tipo") or "",
                        guarantee_form=g.get("forma") or "", amount=_decimal(g.get("monto")),
                        item=item)
        for g in guarantees
    )


def _update(user, item, channel, offer_data, data, lines):
    """El ítem trae un cambio de una oferta ya cargada: actualiza lo cargado y deja el
    registro con el antes y el después (P6)."""
    before = _snapshot(offer_data)
    offer_data.confirmed_on = _date(data["confirmada"])
    offer_data.currency = _currency_code(data["moneda"])
    offer_data.total = _decimal(data["total"])
    offer_data.item = item
    offer_data.save()
    offer_data.guarantees.all().delete()
    _write_guarantees(offer_data, data["garantias"], item)
    PortalQuote.objects.filter(offer=offer_data.offer).delete()
    _write_quotes(offer_data.offer, data, lines)
    audit.record(EventType.PORTAL_DECISION, outcome=Outcome.OK, channel=channel, user=user,
                 detail={"action": "actualizar_cargado", "link": item.proposal.link_id,
                         "item": item.pk, "kind": item.kind, "key": item.key,
                         "offer": offer_data.offer_id, "before": before,
                         "after": _snapshot(offer_data)})
    return LoadedModel.OFFER, offer_data.offer_id


def _write_quotes(offer, data, lines):
    PortalQuote.objects.bulk_create(
        PortalQuote(offer=offer, line=lines[q["renglon"]], price=_decimal(q["precio"]),
                    quantity=_decimal(q["cantidad"]))
        for q in data["cotizaciones"]
    )


def load(user, item, confirmation=None, channel=Channel.SCREEN):
    """Carga la oferta aprobada. Devuelve `(modelo, id)`; levanta una excepción con el motivo.
    Si la oferta ya estaba cargada desde el Portal, el ítem es un cambio y actualiza lo
    cargado (REQ-050)."""
    data = item.payload
    procedure = item.proposal.link.procedure
    lines = {line.number: line for line in PortalLine.objects.filter(procedure=procedure)}
    missing = sorted({q["renglon"] for q in data["cotizaciones"]} - set(lines))
    if missing:
        raise ValueError("El cuadro cotiza renglones que no están cargados: "
                         + ", ".join(str(n) for n in missing) + ".")
    loaded = list(PortalOfferData.objects.select_for_update()
                  .filter(offer__procedure=procedure, cuit=data["cuit"]))
    if len(loaded) > 1:
        raise ValueError("Hay más de una oferta cargada con ese CUIT en el procedimiento.")
    if loaded:
        return _update(user, item, channel, loaded[0], data, lines)
    found = match_offer(procedure, data["cuit"], data["oferente"])
    existing = found.offer
    offer = existing or register_offer(user, procedure, bidder=data["oferente"], channel=channel)
    if existing is not None and PortalOfferData.objects.filter(offer=existing).exists():
        raise ValueError("Esta oferta ya está cargada desde el Portal con otro CUIT.")
    # Lo que se decidió sobre el emparejamiento queda en el registro del ítem (P6).
    item.audit_extra = {"match": found.how, "match_offer": existing.pk if existing else None,
                        "match_note": found.note}
    offer_data = PortalOfferData.objects.create(
        offer=offer, cuit=data["cuit"], confirmed_on=_date(data["confirmada"]),
        currency=_currency_code(data["moneda"]), total=_decimal(data["total"]), item=item,
    )
    _write_guarantees(offer_data, data["garantias"], item)
    _write_quotes(offer, data, lines)
    return LoadedModel.OFFER, offer.pk


# `portal_offer_data.currency` guarda hasta 10 caracteres: el nombre del Portal (que queda entero
# en el ítem) se guarda como código cuando se lo conoce; si no, vacío (no se corta ni se inventa).
_CURRENCY_CODES = {"peso argentino": "ARS", "dolar estadounidense": "USD", "euro": "EUR"}


def _currency_code(name):
    text = unicodedata.normalize("NFD", (name or "").casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return _CURRENCY_CODES.get(" ".join(text.split()), (name or "")[:10] if len(name or "") <= 10 else "")


def _decimal(value):
    return None if value in (None, "") else Decimal(str(value))


def _date(value):
    return date.fromisoformat(value) if value else None
