"""Qué citas de la oferta salen de una página leída por visión (ADR-0041; P3; plan 015, T-264).

El texto de una cita sobre una página leída por visión es la transcripción que hizo el sistema
mirando la imagen de una página con dificultades de lectura: puede tener errores y conviene que la
Comisión lo vuelva a chequear (decisión del responsable, 2026-10-13). Las pantallas lo rotulan
(`journey/_cita_vision.html`, la 004) y la exportación lo avisa en el fundamento de la planilla, con
el documento y la página, y en el cuadro (`services/export.py`). Es la misma cuenta que hace
`services/evaluate.pair_page` para la 004: la página de la cita está entre las
`vision.vision_pages` de la lectura de la cita.

Para muchas citas de una vez: una consulta con las lecturas que tienen visión, sin importar cuántas
citas (nunca una por fila ni por celda, T-223). Este módulo no depende de `journey`.
"""

from evaluon.assessment.models import Citation, CitationKind
from evaluon.offers import vision


def mark(citations):
    """Marca cada cita de la oferta (con `reading_id` y `page`) con `by_vision`: su página se leyó
    por visión."""
    citations = list(citations)
    flagged = vision.on_vision((citation.reading_id, citation.page) for citation in citations)
    for citation in citations:
        citation.by_vision = (citation.reading_id, citation.page) in flagged


def results_on_vision_pages(result_ids):
    """`{id del resultado: [(título del documento, página)]}` de los resultados, entre `result_ids`,
    que citan de la oferta alguna página leída por visión: cuáles son esas páginas, sin repetir y en
    el orden de las citas. El resultado que no cita ninguna no figura. Una consulta con las citas
    (y el documento) de todos los resultados y una con las lecturas con visión."""
    ids = list(result_ids)
    if not ids:
        return {}
    cited = list(Citation.objects.filter(result_id__in=ids, kind=CitationKind.OFERTA)
                 .order_by("order")
                 .values_list("result_id", "reading_id", "page", "document__title"))
    seen = vision.pages_read_in(reading for _, reading, _, _ in cited)
    found = {}
    for result, reading, page, title in cited:
        if page in seen.get(reading, ()):
            place = ((title or "").strip(), page)
            if place not in found.setdefault(result, []):
                found[result].append(place)
    return found
