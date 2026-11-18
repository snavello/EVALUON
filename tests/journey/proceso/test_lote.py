"""`lote.abiertos_y_terminados` (REQ-150; plan 018, ADR-0079; T-356): coincide con
`s4_dictamen.dictamen_cargado` procedimiento por procedimiento y usa un número constante de
consultas. Material inventado (P4)."""

from datetime import date

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from evaluon.journey.proceso import lote
from evaluon.journey.temas import s4_dictamen
from evaluon.portal import models as pm
from evaluon.tenders import models as tm
from evaluon.tenders.models import Procedure
from evaluon.tenders.services import document_history
from evaluon.tenders.services import documents as tender_documents

pytestmark = pytest.mark.django_db


def nuevo(user, n):
    return Procedure.objects.create(number=f"LOTE-{n}/2026", subject=f"Objeto inventado {n}",
                                    authorization_date=date(2026, 1, 15), created_by=user)


def portal_dictamen(procedure, user, state, orden=1):
    """Un dictamen del Portal en ese estado; `orden` es la exploración (más alto, más nuevo)."""
    n = pm.PortalLink.objects.count()
    link = pm.PortalLink.objects.create(url=f"https://portal.invalid/proceso-{n}",
                                        procedure=procedure, created_by=user)
    pagina = pm.PortalPage.objects.create(link=link, exploration=orden, kind="proceso",
                                          url=f"https://portal.invalid/p-{n}", sha256="a" * 64,
                                          content=b"x")
    proposal = pm.PortalProposal.objects.create(link=link, exploration=orden,
                                                origin=pm.Origin.REVISION)
    decide = {} if state == pm.ItemState.PROPUESTO else {
        "decided_by": user, "decided_at": proposal.created_at}
    return pm.PortalItem.objects.create(
        proposal=proposal, kind=pm.ItemKind.DOCUMENTO, key=f"dictamen-{n}",
        payload={"nombre": "Dictamen", "clase": "dictamen", "fecha": "2026-10-06"},
        content_sha256="d" * 64, page=pagina, state=state, **decide)


def subir(user, procedure):
    return tender_documents.load_document(
        user, procedure, data=b"%PDF-1.4 dictamen sintetico", file_name="dictamen.pdf",
        kind=tm.DocumentKind.DICTAMEN, title="Dictamen (inventado)").document


def test_req150_coincide_con_dictamen_cargado_en_cada_caso(operator_user):
    """REQ-150: sin dictamen, subido, retirado, restituido y del Portal aprobado, 
    sin aprobar y rechazado: el lote dice lo mismo que `dictamen_cargado` de cada uno."""
    procs = {n: nuevo(operator_user, n) for n in range(7)}
    subir(operator_user, procs[1])
    retirado = subir(operator_user, procs[2])
    document_history.withdraw(operator_user, retirado, "error de carga")
    restituido = subir(operator_user, procs[3])
    document_history.withdraw(operator_user, restituido, "error de carga")
    document_history.restore(operator_user, restituido)
    portal_dictamen(procs[4], operator_user, pm.ItemState.APROBADO)
    portal_dictamen(procs[5], operator_user, pm.ItemState.PROPUESTO)
    portal_dictamen(procs[6], operator_user, pm.ItemState.RECHAZADO)

    abiertos, terminados = lote.abiertos_y_terminados()
    assert set(abiertos) | set(terminados) == {p.pk for p in procs.values()}
    for n, p in procs.items():
        assert (p.pk in terminados) is s4_dictamen.dictamen_cargado(p), n
        assert (p.pk in abiertos) is (not s4_dictamen.dictamen_cargado(p)), n
    assert {n for n, p in procs.items() if p.pk in terminados} == {1, 3, 4}


def test_req150_el_dictamen_mas_nuevo_del_portal_manda(operator_user):
    """REQ-150: igual que `portal_dictamen`, cuenta el ítem más reciente de cada procedimiento."""
    p = nuevo(operator_user, 1)
    portal_dictamen(p, operator_user, pm.ItemState.APROBADO)
    nuevo_item = portal_dictamen(p, operator_user, pm.ItemState.PROPUESTO, orden=2)
    assert s4_dictamen.portal_dictamen(p).pk == nuevo_item.pk
    assert s4_dictamen.dictamen_cargado(p) is False
    assert lote.abiertos_y_terminados()[1] == []


def test_req150_el_orden_es_el_pedido_y_las_consultas_son_constantes(operator_user):
    """REQ-150: con 2 o con 20 procedimientos son las mismas consultas; el orden se conserva."""
    for n in range(2):
        nuevo(operator_user, n)
    with CaptureQueriesContext(connection) as pocas:
        lote.terminados()
    for n in range(2, 20):
        subir(operator_user, nuevo(operator_user, n))
    with CaptureQueriesContext(connection) as muchas:
        terminados = lote.terminados()
    assert len(pocas) == len(muchas) == 2
    assert len(terminados) == 18
    ids = list(Procedure.objects.order_by("-created_at", "-pk").values_list("pk", flat=True))
    abiertos, cerrados = lote.abiertos_y_terminados(ids)
    assert abiertos + cerrados != [] and abiertos == [i for i in ids if i not in terminados]
