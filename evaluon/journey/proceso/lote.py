"""Qué procedimientos están abiertos y cuáles terminados, de todos juntos y con dos consultas
(REQ-150; plan 018, «Inicio de la aplicación», ADR-0079; T-356).

Un procedimiento está terminado cuando tiene el dictamen cargado: lo mismo que
`s4_dictamen.dictamen_cargado`, pero para muchos a la vez, sin recorrer `sections_for` ni armar
el `Proceso` de cada uno. Las dos consultas son (1) los documentos de tipo dictamen vigentes
(la definición de `tenders.services.document_history.current_documents`: sin cambios o con la
última acción «restituir») agrupados por procedimiento y (2) los dictámenes del Portal, de los que
cuenta el más nuevo de cada procedimiento (el mismo orden de `s4_dictamen.portal_dictamen`) si
está aprobado o cargado. Solo lee."""

from django.db.models import OuterRef, Q, Subquery

from evaluon.journey.temas import s4_dictamen
from evaluon.portal.models import ItemKind, PortalItem
from evaluon.tenders.models import (
    Document,
    DocumentChange,
    DocumentChangeAction,
    DocumentKind,
    Procedure,
)


def _con_dictamen_subido():
    """Ids de los procedimientos con un documento `dictamen` vigente (una consulta)."""
    ultima = (DocumentChange.objects.filter(document=OuterRef("pk")).order_by("-id")
              .values("action")[:1])
    return set(Document.objects.filter(kind=DocumentKind.DICTAMEN)
               .annotate(ultima_accion=Subquery(ultima))
               .filter(Q(ultima_accion__isnull=True)
                       | Q(ultima_accion=DocumentChangeAction.RESTITUIR))
               .values_list("procedure_id", flat=True))


def _con_dictamen_del_portal():
    """Ids de los procedimientos cuyo dictamen más nuevo del Portal está aprobado o cargado."""
    visto, tomados = set(), set()
    filas = (PortalItem.objects.filter(kind=ItemKind.DOCUMENTO, payload__clase="dictamen")
             .order_by("-proposal__exploration", "-pk")
             .values_list("proposal__link__procedure_id", "state"))
    for procedimiento, estado in filas:
        if procedimiento in visto:
            continue
        visto.add(procedimiento)
        if estado in s4_dictamen.TAKEN:
            tomados.add(procedimiento)
    return tomados


def terminados():
    """El conjunto de ids de procedimientos con el dictamen cargado (dos consultas)."""
    return _con_dictamen_subido() | _con_dictamen_del_portal()


def abiertos_y_terminados(procedimientos=None):
    """`(abiertos, terminados)`: dos listas de ids, del más reciente al más viejo. Sin
    `procedimientos` (ids o `Procedure`, ya en el orden pedido) los lee de la base."""
    if procedimientos is None:
        procedimientos = Procedure.objects.order_by("-created_at", "-pk")
    ids = [getattr(p, "pk", p) for p in procedimientos]
    cerrados = terminados()
    return [i for i in ids if i not in cerrados], [i for i in ids if i in cerrados]
