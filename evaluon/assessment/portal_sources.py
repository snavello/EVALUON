"""De qué página del Portal sale cada dato del Portal que se muestra, y cuándo se tomó (P3,
constitución 1.3, ADR-0053; plan 015, T-264).

Las pantallas lo dicen con `portal/_fuente_dato.html`: el enlace a la página del Portal y la fecha en
que se consultó (`PortalPage.url` y `PortalPage.fetched_at` de la página del ítem de origen). La
exportación (`services/export.py`) dice lo mismo con la dirección escrita, porque el archivo se
imprime. Este módulo reúne lo que las dos comparten: las páginas que cita cada resultado y de qué
página salen los precios y totales del orden económico.

Siempre para muchos resultados u ofertas de una vez: nunca una consulta por fila (T-223). Este módulo
no depende de `journey`.
"""

from collections import defaultdict
from datetime import datetime
from typing import NamedTuple

from evaluon.assessment.models import Citation, CitationKind


class Source(NamedTuple):
    """Una página del Portal: su dirección y cuándo se consultó."""

    page_id: int
    url: str
    fetched_at: datetime


def cited_pages(result_ids):
    """`{id del resultado: [Source]}`: las páginas del Portal de las que salen los datos que cita
    cada resultado, sin repetir y en el orden de las citas. El resultado que no cita ningún dato del
    Portal no figura. Una sola consulta para todos los resultados; trae la dirección y la fecha de la
    página, no la página bajada."""
    found = defaultdict(list)
    ids = list(result_ids)
    if not ids:
        return found
    cited = (Citation.objects.filter(result_id__in=ids, kind=CitationKind.PORTAL)
             .order_by("order")
             .values_list("result_id", "portal_item__page_id", "portal_item__page__url",
                          "portal_item__page__fetched_at"))
    for result, page, url, fetched_at in cited:
        source = Source(page, url, fetched_at)
        if source not in found[result]:
            found[result].append(source)
    return found


def offers_phrase(offers):
    """«la oferta 3» o «las ofertas 1, 2 y 3»."""
    numbers = [str(offer.number) for offer in offers]
    if len(numbers) == 1:
        return f"la oferta {numbers[0]}"
    return f"las ofertas {', '.join(numbers[:-1])} y {numbers[-1]}"


def price_sources(offers, data):
    """De qué página del Portal salen los precios y totales y de qué ofertas (P3, constitución 1.3):
    `[{"offers": «las ofertas 1, 2 y 3», "item": ítem de origen}]`, una por página, en el orden de las
    ofertas. `data` es `{id de la oferta: PortalOfferData}` con el ítem de origen y su página cargados
    (`select_related("item__page")`). Una oferta sin datos del Portal, o cuyo dato no sale de un ítem
    del Portal, no figura."""
    groups = {}
    for offer in offers:
        info = data.get(offer.pk)
        if info is None or info.item is None:
            continue
        groups.setdefault(info.item.page_id, {"offers": [], "item": info.item})[
            "offers"].append(offer)
    return [{"offers": offers_phrase(group["offers"]), "item": group["item"]}
            for group in groups.values()]
