"""Explorar el proceso y armar la propuesta (REQ-046, REQ-049; T-141; plan 012, "Flujo, paso 2")."""

import hashlib
from datetime import date

import pytest

from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.portal.importers import discover
from evaluon.portal.models import (
    ItemKind,
    ItemState,
    Origin,
    PortalItem,
    PortalLine,
    PortalPage,
    PortalProposal,
)
from evaluon.portal.parsing import texto
from evaluon.portal.services import approval, explore
from evaluon.tenders import jobs
from evaluon.tenders.models import Job, JobStatus, Procedure
from tests.portal.fakeportal import (  # noqa: F401
    DATA,
    EXPECTED,
    LINK_URL,
    explore_link,
    fake_portal_calco,
    portal_client,
    portal_settings,
)
from tests.tenders.conftest import (  # noqa: F401
    evaluator_user,
    no_commission_user,
    operator_user,
)

pytestmark = pytest.mark.django_db


def item_of(kind):
    return PortalItem.objects.get(kind=kind)


def test_importers_are_discovered_by_file_name():
    """Plan 012: los tipos de ítem se descubren por los archivos de importers/."""
    registry = discover()
    assert {ItemKind.PROCEDIMIENTO, ItemKind.RENGLONES} <= set(registry)
    for module in registry.values():
        assert callable(module.explore) and callable(module.load)


def test_exploration_saves_the_page_and_proposes_the_items(operator_user, explore_link):
    """REQ-046, REQ-049: página guardada tal cual con huella y fecha; propuesta con los ítems."""
    link, job = explore_link(operator_user)
    assert job.status == JobStatus.DONE, job.error
    page = PortalPage.objects.get()
    raw = (DATA / "proceso.html").read_bytes()
    assert bytes(page.content) == raw
    assert page.sha256 == hashlib.sha256(raw).hexdigest()
    assert page.url == LINK_URL and page.fetched_at is not None
    proposal = PortalProposal.objects.get()
    assert proposal.origin == Origin.IMPORTACION and proposal.job == job
    assert {i.kind for i in proposal.items.all()} == {ItemKind.PROCEDIMIENTO, ItemKind.RENGLONES}
    assert all(i.state == ItemState.PROPUESTO and i.page == page for i in proposal.items.all())
    assert link.process_number == EXPECTED["procedimiento"]["numero"]


def test_nothing_is_loaded_without_approval(operator_user, explore_link):
    """REQ-048: explorar no crea procedimiento ni renglones."""
    link, _ = explore_link(operator_user)
    assert not Procedure.objects.exists()
    assert not PortalLine.objects.exists()
    assert link.procedure is None


def test_procedure_item_has_all_the_data_of_the_page(operator_user, explore_link):
    """REQ-046: el 100 % de los datos del procedimiento, iguales a los del calco."""
    explore_link(operator_user)
    data = item_of(ItemKind.PROCEDIMIENTO).payload
    want = EXPECTED["procedimiento"]
    for key in ("numero", "expediente", "nombre", "objeto", "unidad_operativa", "tipo",
                "encuadre_legal", "moneda"):
        assert data[key] == texto.normalize(want[key]), key
    assert data["cronograma"] == {texto.normalize(k): v for k, v in want["cronograma"].items()}
    assert data["garantias"] == [texto.normalize(g) for g in want["garantias"]]
    assert "accion" not in data  # crear o asociar se decide al mostrar y al cargar


def test_authorization_date_is_a_candidate_not_a_value(operator_user, explore_link):
    """REQ-046, P3: la fecha de autorización se propone como candidata, sin confirmarla."""
    explore_link(operator_user)
    authorization = item_of(ItemKind.PROCEDIMIENTO).payload["fecha_autorizacion"]
    assert authorization["candidata"] == "2025-11-14"
    assert "Autorización llamado" in authorization["origen"]
    assert "valor" not in authorization


def test_six_lines_with_their_quantity(operator_user, explore_link):
    """REQ-046: 6 de 6 renglones con su cantidad."""
    explore_link(operator_user)
    lines = item_of(ItemKind.RENGLONES).payload["renglones"]
    assert len(lines) == len(EXPECTED["renglones"]) == 6
    for got, want in zip(lines, EXPECTED["renglones"]):
        assert (got["numero"], got["cantidad"], got["unidad"]) == (
            want["numero"], want["cantidad"], want["unidad"])


def test_damaged_text_is_kept_and_marked(operator_user, explore_link):
    """REQ-046, P3: el texto roto se guarda tal cual y el ítem lo marca; no se adivina."""
    explore_link(operator_user)
    item = item_of(ItemKind.PROCEDIMIENTO)
    assert "encuadre_legal" in item.damaged_fields
    assert "¿" in item.payload["encuadre_legal"]
    assert "Disposici¿¿n" in item.payload["encuadre_legal"]


def test_existing_procedure_is_associated_not_duplicated(operator_user, explore_link):
    """Plan 012: si el número ya está registrado, la propuesta es asociar al existente."""
    existing = Procedure.objects.create(
        number=EXPECTED["procedimiento"]["numero"], procedure_type="Licitación pública",
        subject="Cargado a mano", authorization_date=date(2025, 11, 14),
        created_by=operator_user)
    link, _ = explore_link(operator_user)
    page = approval.proposal_page(operator_user, link.pk)
    (row,) = page.rows[ItemKind.PROCEDIMIENTO]
    assert row.action == "asociar"
    assert Procedure.objects.get() == existing


def test_exploration_leaves_its_fact(operator_user, explore_link):
    """P6: hecho portal_explore con la página, su huella y su fecha, los ítems y el tiempo."""
    link, job = explore_link(operator_user)
    event = AuditEvent.objects.get(event_type=EventType.PORTAL_EXPLORE)
    assert event.outcome == Outcome.OK and event.user == operator_user
    detail = event.detail
    assert detail["link"] == link.pk and detail["origin"] == Origin.IMPORTACION
    page = PortalPage.objects.get()
    assert detail["pages"] == [{"kind": "proceso", "url": LINK_URL, "sha256": page.sha256,
                                "fetched_at": page.fetched_at.isoformat()}]
    assert detail["items"] == {"procedimiento": 1, "renglones": 1}
    assert detail["reader_version"] and "elapsed_seconds" in detail


def test_page_that_is_not_a_process_fails_with_the_reason(operator_user, explore_link,
                                                          fake_portal_calco):
    """Plan 012: si no se puede leer ni la página del proceso, el pedido falla con el motivo."""
    fake_portal_calco.serve("error-pantalla.html")
    link, job = explore_link(operator_user)
    assert job.status == JobStatus.FAILED
    assert "no es la de un proceso" in job.error
    assert not PortalProposal.objects.exists()
    assert PortalPage.objects.count() == 1  # lo bajado queda
    event = AuditEvent.objects.get(event_type=EventType.PORTAL_EXPLORE)
    assert event.outcome == Outcome.FAILED and "reason" in event.detail


def test_http_error_fails_the_job_with_a_fact(operator_user, explore_link, fake_portal_calco):
    """REQ-051: una falla de conexión deja el pedido fallido con motivo y el hecho."""
    fake_portal_calco.serve("proceso.html", status=500)
    _, job = explore_link(operator_user)
    assert job.status == JobStatus.FAILED and job.error
    assert AuditEvent.objects.get(event_type=EventType.PORTAL_EXPLORE).outcome == Outcome.FAILED


def test_decided_items_are_not_proposed_again(operator_user, evaluator_user, explore_link,
                                              fake_portal_calco):
    """REQ-050 (inicio): lo aprobado y lo rechazado con la misma huella no se repite."""
    link, _ = explore_link(operator_user)
    procedure_item, lines_item = item_of(ItemKind.PROCEDIMIENTO), item_of(ItemKind.RENGLONES)
    approval.decide(evaluator_user, [procedure_item.pk], approval.APPROVE,
                    confirmations={procedure_item.pk: {"authorization_date": date(2025, 11, 14)}})
    approval.decide(evaluator_user, [lines_item.pk], approval.REJECT)
    review = jobs.enqueue("portal_review", procedure=None, requested_by=operator_user,
                          target_id=link.pk)
    jobs.run(review)
    assert Job.objects.get(pk=review.pk).status == JobStatus.DONE
    assert PortalItem.objects.count() == 2
    assert not PortalProposal.objects.filter(origin=Origin.REVISION).exists()
    event = AuditEvent.objects.get(event_type=EventType.PORTAL_REVIEW)
    assert event.detail["omitted"] == 2 and event.detail["items"] == {}


def test_changed_content_is_proposed_again(operator_user, evaluator_user, explore_link,
                                           fake_portal_calco):
    """Plan 012: con otra huella el ítem se propone de nuevo (la circular agregada cambia la página)."""
    link, _ = explore_link(operator_user)
    lines_item = item_of(ItemKind.RENGLONES)
    approval.decide(evaluator_user, [lines_item.pk], approval.REJECT)
    page = (DATA / "proceso.html").read_bytes().replace(b"2700 kg", b"2800 kg")
    from tests.portal.conftest import reply
    fake_portal_calco.routes[("GET", LINK_URL)] = reply(LINK_URL, page)
    review = jobs.enqueue("portal_review", procedure=None, requested_by=operator_user,
                          target_id=link.pk)
    jobs.run(review)
    new = PortalItem.objects.filter(proposal__origin=Origin.REVISION)
    assert [i.kind for i in new] == [ItemKind.RENGLONES]
    assert new[0].payload["renglones"][0]["cantidad"] == 2800
    assert explore.READER_VERSION
