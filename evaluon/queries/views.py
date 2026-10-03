"""Pantalla de consulta (REQ-013, REQ-014, REQ-020; plan 001, "Pantalla, acceso y
comandos" y "Forma de la respuesta"; ADR-0005).

Una sola página armada en el servidor, en la raíz del sitio: el formulario de la
pregunta y, para una consulta guardada, uno de tres bloques (con fundamento, no
determinado, falla técnica). La página de una consulta guardada se arma desde
`queries_query.result`; el texto literal de cada cita se lee de `norms_unit` por `id`,
porque no viaja en el resultado. Solo la ve quien hizo la consulta.

Las vistas no guardan nada en la sesión: si lo hicieran, la sesión se volvería a grabar
y el tope de 8 horas desde el ingreso se renovaría con el uso.
"""

from datetime import date

from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_http_methods

from evaluon.norms.models import Unit
from evaluon.queries.forms import QueryForm, today
from evaluon.queries.models import Query, Status

TEMPLATE = "queries/consulta.html"


@require_http_methods(["GET", "POST"])
def screen(request):
    """Página sin consulta: el formulario con la fecha del día. Al enviarlo, el
    formulario se valida; uno rechazado vuelve marcado y no se consulta."""
    if request.method == "POST":
        form = QueryForm(request.POST)
        # El envío de una pregunta válida a la función de consulta lo conecta T-019;
        # hasta entonces, la página vuelve con lo escrito y sin consultar.
        form.is_valid()
    else:
        form = QueryForm(initial={"reference_date": today()})
    return render(request, TEMPLATE, {"form": form})


@require_GET
def query_detail(request, pk):
    """Página de una consulta guardada: el formulario con la fecha de esa consulta y el
    bloque de su resultado."""
    query = get_object_or_404(Query, pk=pk, user=request.user)
    result = query.result
    reference_date = date.fromisoformat(
        result.get("reference_date") or query.reference_date.isoformat()
    )
    status = result.get("status")
    if status not in Status.values:
        status = Status.ERROR

    context = {
        "form": QueryForm(initial={"reference_date": reference_date}),
        "query": query,
        "status": status,
        "reference_date": reference_date,
        "regime": result.get("regime") or [],
        "statements": _statements(result) if status == Status.GROUNDED else [],
    }
    return render(request, TEMPLATE, context)


def _statements(result):
    """Afirmaciones en el orden guardado, cada una con sus citas: norma, ruta y texto
    literal de la unidad."""
    units = result.get("units") or {}
    statements = result.get("statements") or []
    ids = {unit_id for statement in statements for unit_id in statement["citations"]}
    texts = {
        unit.pk: unit.text
        for unit in Unit.objects.filter(pk__in=ids).only("pk", "text")
    }
    return [
        {
            "text": statement["text"],
            "citations": [
                {
                    "id": unit_id,
                    "norm": units.get(str(unit_id), {}).get("norm", ""),
                    "path": units.get(str(unit_id), {}).get("path", ""),
                    "text": texts.get(unit_id),
                }
                for unit_id in statement["citations"]
            ],
        }
        for statement in statements
    ]
