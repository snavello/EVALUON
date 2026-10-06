"""Revisión del Portal: novedades, cambios y anomalías repetidas (REQ-050, REQ-048; T-144).
Sin red: el transporte es `FakePortal` con la versión con circular del calco."""

from datetime import date

import pytest
from django.urls import reverse

from evaluon.audit.models import AuditEvent, EventType
from evaluon.portal.models import (
    ItemKind,
    ItemState,
    Origin,
    PortalItem,
    PortalLine,
    PortalProcedureData,
    PortalProposal,
)
from evaluon.portal.services import approval
from evaluon.tenders import jobs
from evaluon.tenders.models import PORTAL_JOB_KINDS, JobStatus
from tests.conftest import TEST_PASSWORD
from tests.portal.conftest import reply
from tests.portal.fakeportal import (  # noqa: F401
    DATA,
    LINK_URL,
    explore_link,
    fake_portal_calco,
    portal_client,
    portal_settings,
)
from tests.portal.test_documents import (  # noqa: F401
    circular_item,
    docs_portal,
    serve_documents,
)
from tests.tenders.conftest import (  # noqa: F401
    evaluator_user,
    no_commission_user,
    operator_user,
)

pytestmark = pytest.mark.django_db

DATE = date(2025, 11, 14)


def review(user, link):
    jobs.enqueue("portal_review", procedure=None, requested_by=user, target_id=link.pk)
    job = jobs.run_next(kinds=PORTAL_JOB_KINDS)
    assert job.status == JobStatus.DONE, job.error
    return job


def approve_basics(evaluator_user):
    procedure = PortalItem.objects.get(kind=ItemKind.PROCEDIMIENTO)
    lines = PortalItem.objects.get(kind=ItemKind.RENGLONES)
    results = approval.decide(evaluator_user, [procedure.pk, lines.pk], approval.APPROVE,
                              confirmations={procedure.pk: {"authorization_date": DATE}})
    assert [r.result for r in results] == [approval.LOADED, approval.LOADED]


def change_page(portal, *pairs):
    page = (DATA / "proceso.html").read_bytes()
    for old, new in pairs:
        assert old in page
        page = page.replace(old, new)
    portal.routes[("GET", LINK_URL)] = reply(LINK_URL, page)


def test_a_changed_item_updates_what_is_loaded(operator_user, evaluator_user, explore_link,
                                               fake_portal_calco):
    """REQ-050: un ítem cambiado y aprobado actualiza lo cargado (no se crea de nuevo, sin
    IntegrityError) y deja el antes y el después en el registro (P6)."""
    link, _ = explore_link(operator_user)
    approve_basics(evaluator_user)
    first_line_id = PortalLine.objects.get(number=1).pk
    change_page(fake_portal_calco, (b"2700 kg", b"2800 kg"),
                (b"SGXXXXX#SDGXXX", b"SGYYYYY#SDGXXX"))
    review(operator_user, link)
    changed = list(PortalItem.objects.filter(proposal__origin=Origin.REVISION))
    assert {i.kind for i in changed} == {ItemKind.PROCEDIMIENTO, ItemKind.RENGLONES}
    results = approval.decide(evaluator_user, [i.pk for i in changed], approval.APPROVE)
    assert [r.result for r in results] == [approval.LOADED, approval.LOADED], \
        [r.reason for r in results]
    assert PortalLine.objects.count() == 6
    line = PortalLine.objects.get(number=1)
    assert line.pk == first_line_id and line.item.proposal.origin == Origin.REVISION
    data = PortalProcedureData.objects.get()
    assert "SGYYYYY" in data.file_number and data.item.proposal.origin == Origin.REVISION
    events = AuditEvent.objects.filter(event_type=EventType.PORTAL_DECISION,
                                       detail__action="actualizar_cargado")
    assert events.count() == 2
    lines_event = events.get(detail__kind=ItemKind.RENGLONES)
    assert lines_event.user == evaluator_user
    assert lines_event.detail["before"]["1"]["cantidad"] != lines_event.detail["after"]["1"]["cantidad"]
    procedure_event = events.get(detail__kind=ItemKind.PROCEDIMIENTO)
    assert "SGXXXXX" in procedure_event.detail["before"]["file_number"]
    assert "SGYYYYY" in procedure_event.detail["after"]["file_number"]


def test_a_changed_item_is_shown_as_changed(client, operator_user, evaluator_user, explore_link,
                                            fake_portal_calco):
    """REQ-050: el ítem cambiado se muestra «Cambiado respecto de lo aprobado»."""
    link, _ = explore_link(operator_user)
    approve_basics(evaluator_user)
    change_page(fake_portal_calco, (b"2700 kg", b"2800 kg"))
    review(operator_user, link)
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    html = client.get(reverse("portal:proposal", args=[link.pk])).content.decode()
    assert html.count("Cambiado respecto de lo aprobado") == 1


def test_a_removed_line_is_not_deleted_silently(operator_user, evaluator_user, explore_link):
    """Un renglón cargado que el Portal ya no trae no se borra: la carga falla con el motivo."""
    link, _ = explore_link(operator_user)
    approve_basics(evaluator_user)
    item = PortalItem.objects.get(kind=ItemKind.RENGLONES)
    payload = {"renglones": item.payload["renglones"][:-1]}
    clone = PortalItem.objects.create(
        proposal=PortalProposal.objects.create(link=link, exploration=99, origin=Origin.REVISION),
        kind=ItemKind.RENGLONES, key=item.key, payload=payload, content_sha256="1" * 64,
        page=item.page)
    (result,) = approval.decide(evaluator_user, [clone.pk], approval.APPROVE)
    assert result.result == approval.FAILED and "ya no trae los renglones 6" in result.reason
    assert PortalLine.objects.count() == 6


def test_three_identical_reviews_leave_no_new_proposal(operator_user, explore_link,
                                                       fake_portal_calco):
    """REQ-050: tres revisiones iguales no crean ninguna propuesta nueva, aunque se repita una
    anomalía ya informada (como la del pliego general)."""
    link, _ = explore_link(operator_user)
    assert PortalProposal.objects.get().anomalies  # el pliego general ya figura como anomalía
    for _ in range(3):
        review(operator_user, link)
    assert PortalProposal.objects.count() == 1
    assert PortalProposal.objects.get().origin == Origin.IMPORTACION


def test_the_new_circular_appears_once_and_decided_items_do_not_repeat(
        operator_user, evaluator_user, explore_link, docs_portal):
    """REQ-050: la circular agregada aparece como novedad una sola vez; lo ya rechazado con la
    misma huella no se repite, y la anomalía repetida tampoco crea propuesta."""
    link, _ = explore_link(operator_user)
    approve_basics(evaluator_user)
    docs_portal.serve("proceso-con-circular.html")
    serve_documents(docs_portal, version=2)
    review(operator_user, link)
    item = circular_item()
    assert item.proposal.origin == Origin.REVISION and item.state == ItemState.PROPUESTO
    approval.decide(operator_user, [item.pk], approval.REJECT)
    review(operator_user, link)
    review(operator_user, link)
    assert PortalItem.objects.filter(kind=ItemKind.DOCUMENTO, key=item.key).count() == 1
    assert PortalProposal.objects.filter(origin=Origin.REVISION).count() == 1


def test_deciding_the_dictamen_ends_the_following(operator_user, evaluator_user, explore_link,
                                                  docs_portal):
    """REQ-050: al decidirse el ítem del dictamen termina el seguimiento, con su registro."""
    link, _ = explore_link(operator_user)
    approve_basics(evaluator_user)
    dictamen = [i for i in PortalItem.objects.filter(kind=ItemKind.DOCUMENTO)
                if i.payload["clase"] == "dictamen"]
    assert len(dictamen) == 1
    link.refresh_from_db()
    assert link.following is True
    approval.decide(operator_user, [dictamen[0].pk], approval.APPROVE)
    link.refresh_from_db()
    assert link.following is False
    assert AuditEvent.objects.filter(event_type=EventType.PORTAL_LINK,
                                     detail__action="fin_de_seguimiento").count() == 1


def test_rejecting_the_dictamen_also_ends_the_following(operator_user, evaluator_user,
                                                        explore_link, docs_portal):
    """REQ-050: decidir el dictamen, también rechazarlo, termina el seguimiento (aviso de
    T-144: el rechazo no tenía test)."""
    link, _ = explore_link(operator_user)
    approve_basics(evaluator_user)
    dictamen = [i for i in PortalItem.objects.filter(kind=ItemKind.DOCUMENTO)
                if i.payload["clase"] == "dictamen"]
    link.refresh_from_db()
    assert link.following is True
    results = approval.decide(operator_user, [dictamen[0].pk], approval.REJECT)
    assert [r.result for r in results] == [approval.REJECTED]
    link.refresh_from_db()
    assert link.following is False
    event = AuditEvent.objects.get(event_type=EventType.PORTAL_LINK,
                                   detail__action="fin_de_seguimiento")
    assert event.user == operator_user and event.detail["item"] == dictamen[0].pk


def test_a_new_name_or_object_is_shown_and_recorded_not_applied(
        operator_user, evaluator_user, explore_link, fake_portal_calco):
    """REQ-050, P6: si el Portal cambia el nombre o el objeto, el procedimiento conserva el
    anterior, y el cambio queda a la vista en el resultado y en el registro."""
    from evaluon.tenders.models import Procedure

    link, _ = explore_link(operator_user)
    approve_basics(evaluator_user)
    before = Procedure.objects.get().subject
    change_page(fake_portal_calco,
                (b"ADQUISICI\xc3\x93N DE YERBA MATE PARA OFICINAS",
                 b"ADQUISICI\xc3\x93N DE T\xc3\x89 PARA OFICINAS"))
    review(operator_user, link)
    changed = PortalItem.objects.get(proposal__origin=Origin.REVISION,
                                     kind=ItemKind.PROCEDIMIENTO)
    (result,) = approval.decide(evaluator_user, [changed.pk], approval.APPROVE)
    assert result.result == approval.LOADED
    assert "el Portal cambió el nombre u objeto; el procedimiento conserva el anterior" \
        in result.reason
    assert Procedure.objects.get().subject == before
    event = AuditEvent.objects.get(event_type=EventType.PORTAL_DECISION,
                                   detail__action="nombre_u_objeto_cambiado")
    assert event.user == evaluator_user
    assert event.detail["conserva"] == before and "T\u00c9" in event.detail["portal"]


def test_the_notice_reaches_the_screen(client, operator_user, evaluator_user, explore_link,
                                       fake_portal_calco):
    """REQ-050: el aviso del cambio de nombre u objeto se ve en la pantalla de la propuesta."""
    link, _ = explore_link(operator_user)
    approve_basics(evaluator_user)
    change_page(fake_portal_calco, (b"ADQUISICI\xc3\x93N DE YERBA MATE PARA OFICINAS",
                                    b"ADQUISICI\xc3\x93N DE T\xc3\x89 PARA OFICINAS"))
    review(operator_user, link)
    changed = PortalItem.objects.get(proposal__origin=Origin.REVISION,
                                     kind=ItemKind.PROCEDIMIENTO)
    assert client.login(username=evaluator_user.username, password=TEST_PASSWORD)
    response = client.post(reverse("portal:decide", args=[link.pk]),
                           {"decision": "aprobar", "item": [changed.pk]})
    html = response.content.decode()
    assert "el Portal cambió el nombre u objeto; el procedimiento conserva el anterior" in html
