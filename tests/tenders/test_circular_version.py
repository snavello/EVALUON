"""La versión nueva de la matriz que abre una circular modificatoria (REQ-085, REQ-097; plan 014,
T-205; principios P3 y P6).

Pliego y circulares sintéticos (`tests/tenders/pdfs.py`) y el doble del modelo con guion de
`test_circulars.py`; sin modelo real (P4). La matriz de partida está validada.
"""

from datetime import date

import pytest

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.tenders import models as m
from evaluon.tenders.services import circular_version as service
from evaluon.tenders.services import consequences, review
from evaluon.tenders.services import validation as validation_service
from tests.tenders.scripted import (
    PAGO,
    item,
    load_and_read,
    make_procedure,
    propose,
    run_jobs,
)
from tests.tenders.test_circulars import (  # noqa: F401  (fixture: script)
    MONITOR,
    RAM,
    VISITA,
    VISITA_QUOTE,
    add_circular,
    circular as circular_pdf,
    script,
    tender,
)

pytestmark = pytest.mark.django_db

RAM_CHANGE = "1. Reemplázase en el Renglón N° 1 la memoria de 16 GB de RAM por 32 GB de RAM."


@pytest.fixture
def validated(operator_user, evaluator_user, script):  # noqa: F811
    """Un pliego propuesto y validado (versión 1), sin circulares."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, tender())
    script.when(VISITA, item([(VISITA_QUOTE, "formal")]))
    script.when(PAGO, item([(PAGO, "economico")]))
    script.when(RAM, item(technical=["1"]))
    script.when(MONITOR, item(technical=["2"]))
    requested, job = propose(operator_user, procedure)
    assert job.status == "done", job.error
    version = requested.run.version
    for pending in version.pending_items.filter(resolved_at__isnull=True):
        review.resolve_pending(evaluator_user, pending.pk)
    for requirement in version.requirements.exclude(state="quitado"):
        consequences.choose(evaluator_user, requirement.pk,
                            consequence_type="aprobar_igual", note="Motivo de prueba")
    return validation_service.validate(evaluator_user, version.pk)


def modifying(user, procedure, title="Circular N.º 1", day=date(2025, 12, 1)):
    return add_circular(user, procedure, title, day, RAM_CHANGE)


def snapshot(version):
    return [(r.number, r.state, [q.text for q in r.quotes.order_by("order")],
             [(s.effect, s.text) for s in r.sources.order_by("id")])
            for r in version.requirements.order_by("number")]


def test_a_modifying_circular_opens_a_draft_version_with_the_changed_requirement_marked(
        operator_user, validated, script):  # noqa: F811
    """REQ-085: la circular que cambia un requisito produce una versión nueva en borrador con
    ese requisito marcado como cambiado; la anterior no cambia y no se valida sola."""
    before = snapshot(validated)
    circular = modifying(operator_user, validated.procedure)
    script.c_when("por 32 GB", efectos=[("16 GB de RAM", "modifica", "32 GB de RAM")])

    assert [r.state for r in service.states(validated.procedure)] == [service.SIN_VERSION]
    requested = service.open_for_circular(operator_user, validated.procedure, circular)
    run_jobs()

    new = validated.procedure.matrix_versions.get(number=validated.number + 1)
    assert new.status == "draft" and new.validated_at is None and new.validated_by is None
    requested.run.refresh_from_db()
    assert requested.run.version == new
    changed = new.requirements.get(category="tecnico", items=[1])
    source = changed.sources.get()
    assert source.effect == "modifica" and source.text == "32 GB de RAM"
    assert source.segment.reading.document == circular
    assert not new.requirements.get(category="tecnico", items=[2]).sources.exists()
    validated.refresh_from_db()
    assert validated.status == "validated"
    assert snapshot(validated) == before

    (row,) = service.states(validated.procedure)
    assert row.state == service.EN_BORRADOR and row.version == new
    assert row.effect.changed == [changed.number] and not row.effect.added


def test_the_circular_counts_as_pending_until_a_new_matrix_is_validated(
        operator_user, evaluator_user, validated, script):  # noqa: F811
    """REQ-085: sin matriz nueva validada la circular cuenta como pendiente; al validarla,
    deja de serlo."""
    circular = modifying(operator_user, validated.procedure)
    script.c_when("por 32 GB", efectos=[("16 GB de RAM", "modifica", "32 GB de RAM")])
    assert [r.document for r in service.pending(validated.procedure)] == [circular]

    service.open_for_circular(operator_user, validated.procedure, circular)
    run_jobs()
    new = validated.procedure.matrix_versions.get(number=validated.number + 1)
    assert [r.document for r in service.pending(validated.procedure)] == [circular]

    for pending in new.pending_items.filter(resolved_at__isnull=True):
        review.resolve_pending(evaluator_user, pending.pk)
    for requirement in new.requirements.exclude(state="quitado"):
        consequences.choose(evaluator_user, requirement.pk,
                            consequence_type="aprobar_igual", note="Motivo de prueba")
    validation_service.validate(evaluator_user, new.pk)

    assert service.pending(validated.procedure) == []
    assert service.states(validated.procedure)[0].state == service.VALIDADA


def test_a_clarifying_circular_does_not_open_a_version(operator_user, validated):
    """REQ-085: una aclaratoria o una respuesta a una consulta no abre versión."""
    clarifying = add_circular(operator_user, validated.procedure, "Aclaración 1",
                              date(2025, 12, 2), "1. El Renglón N° 1 se entrega en caja.",
                              kind="circular_aclaratoria")
    answer = add_circular(operator_user, validated.procedure, "Respuesta 1",
                          date(2025, 12, 3), "1. La visita es opcional.",
                          kind="respuesta_consulta")

    for document in (clarifying, answer):
        with pytest.raises(service.CircularRefused) as error:
            service.open_for_circular(operator_user, validated.procedure, document)
        assert error.value.reason == "not_modifying"
    assert validated.procedure.matrix_versions.count() == 1
    assert [r.state for r in service.states(validated.procedure)] == [service.NO_APLICA] * 2
    assert service.pending(validated.procedure) == []


def test_a_circular_that_is_not_read_yet_or_with_a_draft_open_is_refused_with_its_reason(
        operator_user, validated, script):  # noqa: F811
    """REQ-085: no se abre sin lectura ni con un borrador abierto; queda el hecho rechazado."""
    from evaluon.tenders.services import documents

    unread = documents.load_document(
        operator_user, validated.procedure, data=circular_pdf(RAM_CHANGE),
        file_name="c.pdf", kind="circular_modificatoria", title="Sin leer",
        issued_on=date(2025, 12, 1)).document
    with pytest.raises(service.CircularRefused) as error:
        service.open_for_circular(operator_user, validated.procedure, unread)
    assert error.value.reason == "not_read"

    run_jobs()
    script.c_when("por 32 GB", efectos=[("16 GB de RAM", "modifica", "32 GB de RAM")])
    validation_service.open_new_version(operator_user, validated.procedure_id)
    with pytest.raises(service.CircularRefused) as error:
        service.open_for_circular(operator_user, validated.procedure, unread)
    assert error.value.reason == "draft_open"
    assert AuditEvent.objects.filter(event_type=EventType.MATRIX_VERSION,
                                     outcome=Outcome.REJECTED,
                                     detail__reason="not_read").exists()


def test_without_a_validated_matrix_the_circular_waits_for_the_proposal(
        operator_user, script):  # noqa: F811
    """REQ-085: sin matriz validada no se abre versión; la primera propuesta la incluirá."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, tender())
    circular = modifying(operator_user, procedure)
    with pytest.raises(service.CircularRefused) as error:
        service.open_for_circular(operator_user, procedure, circular)
    assert error.value.reason == "no_validated_version"
    assert service.pending(procedure) == []


def test_a_circular_already_in_a_version_is_not_opened_twice(
        operator_user, validated, script):  # noqa: F811
    """REQ-085: la circular que ya está en una versión no abre otra."""
    circular = modifying(operator_user, validated.procedure)
    script.c_when("por 32 GB", efectos=[("16 GB de RAM", "modifica", "32 GB de RAM")])
    service.open_for_circular(operator_user, validated.procedure, circular)
    run_jobs()
    with pytest.raises(service.CircularRefused) as error:
        service.open_for_circular(operator_user, validated.procedure, circular)
    assert error.value.reason == "already_applied"


def test_a_user_without_a_commission_role_cannot_open_it(no_commission_user, operator_user,
                                                         validated):
    """P3: sin rol de la Comisión se rechaza y queda el hecho."""
    circular = modifying(operator_user, validated.procedure)
    with pytest.raises(RoleRejected):
        service.open_for_circular(no_commission_user, validated.procedure, circular)
    assert validated.procedure.matrix_versions.count() == 1


def test_the_request_leaves_the_audit_trail_with_the_circular(operator_user, validated,
                                                              script):  # noqa: F811
    """P6: el pedido deja el hecho de pedido de matriz y el de la circular que lo motivó."""
    circular = modifying(operator_user, validated.procedure)
    requested = service.open_for_circular(operator_user, validated.procedure, circular)
    event = AuditEvent.objects.get(event_type=EventType.MATRIX_VERSION, outcome=Outcome.OK,
                                   detail__action="circular")
    assert event.detail["document"] == circular.pk
    assert event.detail["run"] == requested.run.pk and event.detail["based_on"] == validated.pk
    assert AuditEvent.objects.filter(event_type=EventType.MATRIX_REQUEST,
                                     detail__run=requested.run.pk).exists()
    assert m.Document.objects.get(pk=circular.pk).issued_on == date(2025, 12, 1)
