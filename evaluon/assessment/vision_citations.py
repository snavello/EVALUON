"""Qué citas de la oferta salen de una página leída por visión (ADR-0041; P3; plan 015, T-264).

El texto de una cita sobre una página leída por visión es la transcripción que hizo el sistema
mirando la imagen de una página con dificultades de lectura: puede tener errores y conviene que la
Comisión lo vuelva a chequear (decisión del responsable, 2026-10-13). Las pantallas lo rotulan
(`journey/_cita_vision.html`, la 004) y la exportación lo avisa en el fundamento y en el cuadro
(`services/export.py`). Es la misma cuenta que hace `services/evaluate.pair_page` para la 004: la
página de la cita está entre las `vision.vision_pages` de la lectura de la cita.

Para muchas citas de una vez: una consulta con las lecturas que tienen visión, sin importar cuántas
citas (nunca una por fila ni por celda, T-223). Este módulo no depende de `journey`.
"""

from evaluon.assessment.models import Citation, CitationKind
from evaluon.offers import vision


def mark(citations):
    """Marca cada cita de la oferta (con `reading_id` y `page`) con `by_vision`: su página se leyó
    por visión."""
    citations = list(citations)
    seen = vision.pages_read_in(citation.reading_id for citation in citations)
    for citation in citations:
        citation.by_vision = citation.page in seen.get(citation.reading_id, ())


def results_on_vision_pages(result_ids):
    """Los ids, entre `result_ids`, de los resultados que citan de la oferta alguna página leída
    por visión. Una consulta con las citas de todos los resultados y una con las lecturas con
    visión."""
    ids = list(result_ids)
    if not ids:
        return set()
    cited = list(Citation.objects.filter(result_id__in=ids, kind=CitationKind.OFERTA)
                 .values_list("result_id", "reading_id", "page"))
    seen = vision.pages_read_in(reading for _, reading, _ in cited)
    return {result for result, reading, page in cited if page in seen.get(reading, ())}
