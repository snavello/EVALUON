"""Las filas descartadas por el sistema: la página "Descartadas por el sistema" de una
versión y el botón "Devolver a la matriz" (REQ-033, REQ-026; plan 003, "La lista de
descartadas y cómo se devuelve"; ADR-0021; T-105).

La lista se ve en cualquier versión; devolver solo en un borrador. Sin el rol de la
Comisión, "acceso denegado" (403) con el rechazo registrado. Un pedido rechazado (nada
marcado, fila ya devuelta, versión validada) vuelve a mostrar la lista con el motivo y sin
cambiar nada. La vista no guarda nada en la sesión.
"""

from dataclasses import dataclass, field

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from evaluon.accounts.models import CommissionRole
from evaluon.accounts.permissions import require_commission_role
from evaluon.audit.models import Channel
from evaluon.tenders.models import FilterMotive, MatrixVersion, Segment, VersionStatus
from evaluon.tenders.services import discarded as service
from evaluon.tenders.services import matrix_page as pages
from evaluon.tenders.services.review import ReviewRefused

TEMPLATE = "tenders/discarded.html"
LIST_OPERATION = "evaluon.tenders.views.discarded.listing"


@dataclass
class Extra:
    """Una cita adicional de la descartada (la misma condición repetida en otro tramo)."""

    place: object
    text: str


@dataclass
class Item:
    view: service.DiscardedView
    place: object
    evidence_place: object
    extras: list = field(default_factory=list)
    reason_label: str = ""
    category_label: str = ""

    @property
    def can_pick(self):
        return self.view.state == service.DISCARDED


def _version(version_id):
    try:
        return MatrixVersion.objects.select_related("procedure").get(pk=version_id)
    except MatrixVersion.DoesNotExist:
        raise Http404("No hay una versión de la matriz con ese número.")


def _items(version):
    cache = pages._Pages()
    items = []
    for view in service.list_discarded(version):
        row = view.row
        extras = []
        for extra in row.extra_quotes:
            segment = Segment.objects.select_related(
                "reading__document").get(pk=extra["segment"])
            extras.append(Extra(place=pages._place(cache, segment, extra["char_start"],
                                                   extra["char_end"]), text=extra["text"]))
        items.append(Item(
            view=view,
            place=pages._place(cache, row.segment, row.char_start, row.char_end),
            evidence_place=pages._place(cache, row.evidence_segment, row.evidence_start,
                                        row.evidence_end),
            extras=extras,
            reason_label=FilterMotive(row.reason).label,
            category_label=row.get_category_display()))
    return items


def _render(request, version, *, error="", status=200):
    items = _items(version)
    context = {
        "version": version,
        "procedure": version.procedure,
        "items": items,
        "draft": version.status == VersionStatus.DRAFT,
        "can_restore": version.status == VersionStatus.DRAFT and any(
            i.can_pick for i in items),
        "review_error": error,
    }
    return render(request, TEMPLATE, context, status=status)


@require_GET
def listing(request, version_id):
    """La lista de las descartadas de la versión, con su estado."""
    version = _version(version_id)
    require_commission_role(request.user, CommissionRole.OPERATOR,
                            operation=LIST_OPERATION, channel=Channel.SCREEN)
    return _render(request, version)


@require_POST
def restore(request, version_id):
    """Devuelve a la matriz las filas marcadas."""
    version = _version(version_id)
    try:
        service.restore(request.user, version_id, request.POST.getlist("row"),
                        channel=Channel.SCREEN)
    except ReviewRefused as error:
        return _render(request, version, error=str(error), status=400)
    return redirect(reverse("tenders:discarded", args=[version_id]))
