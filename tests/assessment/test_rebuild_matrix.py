"""Rehacer la matriz validada con las cláusulas de cada renglón (REQ-052; T-156). Caso chico
inventado (P4): la versión de partida solo trae el encabezado del renglón, como la de la 008."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from evaluon.accounts import permissions
from evaluon.assessment import evaluation as ev
from evaluon.audit.models import AuditEvent, EventType
from evaluon.tenders import models as m
from evaluon.tenders.services import validation
from tests.assessment.fakes import CASO_CHICO

pytestmark = pytest.mark.django_db

LIST = CASO_CHICO / "evaluacion-esperada.yaml"


@pytest.fixture
def header_only(operator_user, fake_ai):
    """El procedimiento del caso chico con una última versión validada cuya fila técnica del
    renglón 1 trae solo el encabezado."""
    import dataclasses
    expected = ev.load_expected(LIST)
    only = dataclasses.replace(expected, offers=expected.offers[:1])
    only.offers[0].documents = []
    procedure, _ = ev.build_case(operator_user, only)
    draft = validation.open_new_version(operator_user, procedure.pk)
    row = draft.requirements.get(category="tecnico", items=[1])
    row.quotes.filter(order__gt=1).delete()
    draft.status = m.VersionStatus.VALIDATED
    draft.validated_at, draft.validated_by = timezone.now(), operator_user
    draft.save(update_fields=["status", "validated_at", "validated_by"])
    return procedure, draft


def test_the_rebuilt_matrix_is_a_new_version_with_all_the_clauses(operator_user, header_only):
    """REQ-052: la fila técnica vuelve a tener encabezado y cláusulas; la versión anterior no
    se toca y el cambio queda registrado."""
    procedure, old = header_only
    assert old.requirements.get(category="tecnico", items=[1]).quotes.count() == 1
    version, rows = ev.rebuild_matrix(operator_user, procedure)
    assert rows == 1 and version.number == old.number + 1
    assert version.status == m.VersionStatus.VALIDATED and version.based_on == old
    row = version.requirements.get(category="tecnico", items=[1])
    texts = [q.text for q in row.quotes.order_by("order")]
    assert len(texts) == 2 and "75 gramos" in texts[1]
    assert old.requirements.get(category="tecnico", items=[1]).quotes.count() == 1
    assert version.requirements.count() == old.requirements.count()
    event = AuditEvent.objects.filter(event_type=EventType.MATRIX_VERSION).latest("pk")
    assert event.detail["action"] == "rebuilt" and event.detail["version"] == version.pk


def test_a_matrix_that_already_has_the_clauses_is_not_rebuilt(operator_user, header_only):
    """REQ-052: sin filas que cambiar no se crea una versión de más."""
    procedure, _ = header_only
    ev.rebuild_matrix(operator_user, procedure)
    with pytest.raises(ev.MeasurementRefused):
        ev.rebuild_matrix(operator_user, procedure)
    assert procedure.matrix_versions.count() == 3


def test_the_command_rebuilds_the_matrix(operator_user, header_only, monkeypatch):
    """REQ-052: `rehacer_matriz --procedimiento` crea la versión y lo informa."""
    from tests.tenders.conftest import TEST_PASSWORD
    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    procedure, _ = header_only
    out = StringIO()
    call_command("rehacer_matriz", "--usuario", operator_user.username,
                 "--procedimiento", procedure.number, stdout=out)
    assert "1 filas técnicas" in out.getvalue()
    with pytest.raises(CommandError):
        call_command("rehacer_matriz", "--usuario", operator_user.username,
                     "--procedimiento", procedure.number, stdout=StringIO())
