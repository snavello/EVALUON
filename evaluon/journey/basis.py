"""El fundamento de cada resultado, para las pantallas del expediente (P3, constitución 1.3; plan 015,
T-264).

Toda conclusión del sistema muestra su fundamento. Dos clases de fundamento necesitan algo más que
el texto en las pantallas:

- **La cita de la oferta sobre una página leída por visión** (ADR-0041): el texto es la
  transcripción que hizo el modelo mirando la imagen, no el del original. La pantalla la rotula
  «leída por visión», avisa que proviene de una página con dificultades de lectura y que conviene
  que la Comisión la vuelva a chequear, y enlaza a la imagen de la página
  (`journey/_cita_vision.html`; decisión del responsable, 2026-10-13).
- **El dato del Portal**: lleva el enlace a su página y la fecha en que se tomó
  (`portal/_fuente_dato.html`).

Este módulo trae las dos cosas **para todas las filas de una pantalla de una vez**: una consulta con
las citas de la oferta y del Portal de todos los resultados y una con las lecturas que tienen visión.
Nunca una consulta por fila ni por celda (T-223). Las citas de la oferta salen marcadas con
`by_vision` (la cuenta común está en `assessment/vision_citations.py`, que usa también la
exportación).
"""

from collections import defaultdict

from evaluon.assessment import vision_citations
from evaluon.assessment.models import Citation, CitationKind


def of_results(result_ids):
    """`(de la oferta, del Portal)`: `{id del resultado: [citas]}` de los resultados dados, en el
    orden de la evaluación.

    - Las citas de la oferta traen su documento y salen marcadas con `by_vision`.
    - Las del Portal traen la página y la propuesta del ítem de origen (el enlace y la fecha que
      muestra `portal/_fuente_dato.html`) y no la página bajada ni los datos del ítem: se
      repetirían en cada cita (como las lecturas, T-231).

    Una consulta para las dos clases de cita y una para la visión, sin importar cuántos
    resultados."""
    offer, portal = defaultdict(list), defaultdict(list)
    ids = list(result_ids)
    if not ids:
        return offer, portal
    for citation in (Citation.objects
                     .filter(result_id__in=ids, kind__in=(CitationKind.OFERTA, CitationKind.PORTAL))
                     .select_related("document", "portal_item__page", "portal_item__proposal")
                     .defer("portal_item__page__content", "portal_item__payload",
                            "portal_item__proposal__anomalies")
                     .order_by("order")):
        found = offer if citation.kind == CitationKind.OFERTA else portal
        found[citation.result_id].append(citation)
    vision_citations.mark(citation for group in offer.values() for citation in group)
    return offer, portal
