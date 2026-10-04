"""Etiquetas de las plantillas de la revisión por grupos y de las filas descartadas
(REQ-033, REQ-034, REQ-032; T-105).

- `discarded_line`: la línea "El sistema descartó N filas y unificó M repetidas" de la
  matriz (con el enlace a la lista) y de la impresión y el PDF (con el reparto por motivo
  y sin enlace).
- `group_headers`: los encabezados por cláusula de primer nivel y por tramo con dos o más
  propuestas, con la cantidad de filas `propuesto` que tocaría cada botón; se cuentan con
  la misma regla que usa el servicio de grupos.
- `lookup`: busca una clave en un diccionario.
"""

from collections import Counter

from django import template

from evaluon.tenders.models import FilterMotive, RequirementQuote, Segment
from evaluon.tenders.services import discarded
from evaluon.tenders.views import review

register = template.Library()


@register.filter
def lookup(mapping, key):
    return mapping.get(key, [])


def _plural(count, one, many):
    return f"{count} {one if count == 1 else many}"


@register.inclusion_tag("tenders/_discarded_line.html")
def discarded_line(page, link=True):
    """Las cantidades de la versión; sin descartadas (y, en la impresión, siempre que no
    las haya) no hay línea."""
    rows = discarded.rows_of(page.version)
    by_reason = Counter(row.reason for row in rows)
    unified = RequirementQuote.objects.filter(
        requirement__version=page.version, scope="repetida").exclude(
        requirement__state="quitado").count()
    show = bool(rows) or (link and unified > 0)
    return {
        "show": show, "link": link, "page": page,
        "discarded": _plural(len(rows), "fila", "filas") if rows else "",
        "unified": _plural(unified, "repetida", "repetidas") if unified else "",
        "reasons": [(FilterMotive(reason).label, count)
                    for reason, count in sorted(by_reason.items())],
    }


@register.simple_tag
def group_headers(page):
    """`{id del requisito: [encabezados]}`: el encabezado va antes de la primera fila de su
    cláusula o tramo en cada documento. Solo en un borrador (donde se revisa)."""
    headers = {}
    if not page.can_edit:
        return headers
    entries = review.proposed_entries(page.version)
    ids = {q.segment_id for d in page.groups for r in d.rows for q in r.quotes}
    key_of = dict(Segment.objects.filter(pk__in=ids).values_list("pk", "key"))

    def count(group):
        return sum(1 for _r, keys in entries if review.in_group(keys, group))

    totals = {}

    def total(group):
        if group not in totals:
            totals[group] = count(group)
        return totals[group]

    for document in page.groups:
        previous_clause = previous_segment = None
        for row in document.rows:
            keys = [key_of[q.segment_id] for q in row.quotes if q.scope in ("", "propia")]
            if not keys:
                previous_clause = previous_segment = None
                continue
            segment = keys[0]
            clause = review.clause_of(segment)
            found = []
            if clause != previous_clause and total(clause):
                found.append({"kind": "clause", "title": f"Cláusula {clause}",
                              "group": clause, "count": total(clause)})
            if segment != previous_segment and segment != clause and total(segment) >= 2:
                found.append({"kind": "segment", "title": f"Tramo {segment}",
                              "group": segment, "count": total(segment),
                              "path": row.quotes[0].place.path})
            previous_clause, previous_segment = clause, segment
            if found:
                headers[row.requirement.pk] = found
    return headers
