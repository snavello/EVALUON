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

Límite del esquema: `portal_offer_data` guarda una sola garantía. Si el acta trae más de una
para el mismo oferente, el ítem las muestra y las conserva todas y la tabla guarda la primera.
"""

import hashlib
import unicodedata
from datetime import date
from decimal import Decimal
from urllib.parse import urljoin

from evaluon.audit.models import Channel
from evaluon.offers.models import Offer
from evaluon.offers.services.offers import register_offer
from evaluon.portal.client import PortalError
from evaluon.portal.importers import Draft, jsonable
from evaluon.portal.models import (
    ItemKind,
    LoadedModel,
    PageKind,
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
    if len(guarantees) > 1:
        notes.append(f"el acta trae {len(guarantees)} garantías: se muestran todas y se "
                     "registra la primera")
    quotes, taken = [], set()
    for quote in (cuadro.quotes if cuadro else []):
        if quote["cuit"] != cuit:
            continue
        if quote["renglon"] in taken:
            notes.append(f"el renglón {quote['renglon']} trae más de una alternativa: "
                         "se toma la primera")
            continue
        taken.add(quote["renglon"])
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


def load(user, item, confirmation=None, channel=Channel.SCREEN):
    """Carga la oferta aprobada. Devuelve `(modelo, id)`; levanta una excepción con el motivo."""
    data = item.payload
    procedure = item.proposal.link.procedure
    if PortalOfferData.objects.filter(offer__procedure=procedure, cuit=data["cuit"]).exists():
        raise ValueError("Esta oferta ya está cargada desde el Portal para el procedimiento.")
    lines = {line.number: line for line in PortalLine.objects.filter(procedure=procedure)}
    missing = sorted({q["renglon"] for q in data["cotizaciones"]} - set(lines))
    if missing:
        raise ValueError("El cuadro cotiza renglones que no están cargados: "
                         + ", ".join(str(n) for n in missing) + ".")
    existing = next((o for o in Offer.objects.filter(procedure=procedure)
                     if _same_name(o.bidder, data["oferente"])), None)
    offer = existing or register_offer(user, procedure, bidder=data["oferente"], channel=channel)
    if existing is not None and PortalOfferData.objects.filter(offer=existing).exists():
        raise ValueError("Esta oferta ya está cargada desde el Portal para el procedimiento.")
    guarantee = (data["garantias"] or [{}])[0]
    PortalOfferData.objects.create(
        offer=offer, cuit=data["cuit"], confirmed_on=_date(data["confirmada"]),
        currency=_currency_code(data["moneda"]), total=_decimal(data["total"]),
        guarantee_type=guarantee.get("tipo") or "", guarantee_form=guarantee.get("forma") or "",
        guarantee_amount=_decimal(guarantee.get("monto")), item=item,
    )
    PortalQuote.objects.bulk_create(
        PortalQuote(offer=offer, line=lines[q["renglon"]], price=_decimal(q["precio"]),
                    quantity=_decimal(q["cantidad"]))
        for q in data["cotizaciones"]
    )
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
