"""Comando `releer_pliego` (REQ-016, REQ-104; T-259; P6): vuelve a leer el pliego de un
procedimiento con el código vigente desde el original guardado y deja una lectura nueva de cada
documento, sin borrar la anterior. Exige `--usuario` y un rol de la Comisión. PDF inventado
(P4)."""

from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from evaluon.accounts import permissions
from evaluon.audit.models import AuditEvent, EventType
from evaluon.tenders import jobs
from evaluon.tenders.models import DocumentKind, Procedure, Reading
from evaluon.tenders.services import documents
from evaluon.tenders.tables import CELLS_VERSION
from tests.conftest import TEST_PASSWORD
from tests.tenders.pdfs import para, table, tender_pdf

pytestmark = pytest.mark.django_db


@pytest.fixture
def read_procedure(operator_user):
    procedure = Procedure.objects.create(
        number="SINT-RELEER", procedure_type="Licitación pública",
        subject="Adquisición sintética de insumos de prueba",
        authorization_date=date(2025, 11, 14), created_by=operator_user)
    data = tender_pdf([[para("17.1. Tipo de Cotización:"),
                        table(("Total", ""), ("Por Renglón", "X")),
                        para("17.2. La oferta se presenta por el Portal.")]], header=None)
    loaded = documents.load_document(operator_user, procedure, data=data,
                                     file_name="pliego.pdf", kind=DocumentKind.PLIEGO,
                                     title="Pliego sintético")
    while jobs.run_next() is not None:
        pass
    return procedure, loaded.document


def test_the_command_rereads_and_keeps_the_previous_reading(
        read_procedure, operator_user, monkeypatch):
    """REQ-104 (T-259; P6): el comando deja la lectura número 2 con la versión vigente, la 1
    sigue guardada, y queda el hecho `tender_read` a nombre de quien lo pidió."""
    procedure, document = read_procedure
    first = Reading.objects.get(document=document)
    # La lectura anterior, como si viniera de antes de T-259.
    Reading.objects.filter(pk=first.pk).update(tool_versions={"rules_version": "viejo"})
    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    out = StringIO()

    call_command("releer_pliego", procedure.number, "--usuario", operator_user.username,
                 stdout=out)

    readings = list(Reading.objects.filter(document=document).order_by("sequence"))
    assert [r.sequence for r in readings] == [1, 2]
    assert readings[0].pk == first.pk and readings[0].tool_versions == {"rules_version": "viejo"}
    assert readings[1].tool_versions["table_cells"] == CELLS_VERSION
    assert "Se releyeron 1 de 1 documentos" in out.getvalue()
    event = AuditEvent.objects.filter(event_type=EventType.TENDER_READ).latest("id")
    assert event.user == operator_user and event.detail["reading"] == readings[1].pk


def test_the_command_requires_the_user_and_a_commission_role(
        read_procedure, no_commission_user, monkeypatch):
    """REQ-016 (T-259): sin `--usuario` no corre; sin rol de la Comisión se rechaza y no deja
    lectura nueva."""
    procedure, document = read_procedure
    with pytest.raises(CommandError):
        call_command("releer_pliego", procedure.number, stdout=StringIO())
    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    with pytest.raises(CommandError):
        call_command("releer_pliego", procedure.number, "--usuario",
                     no_commission_user.username, stdout=StringIO())
    assert Reading.objects.filter(document=document).count() == 1
