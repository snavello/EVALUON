"""Tema «exportar» de la sección Evaluación y dictamen (REQ-093; plan 014, T-212): el bloque al
pie de la pestaña y las descargas. Material inventado (P4)."""

import re

import pytest
from django.urls import reverse

from evaluon.audit.models import AuditEvent, EventType
from tests.assessment.test_export import proposed, read_xlsx  # noqa: F401  (fixture y ayuda)
from tests.assessment.test_matrix import three  # noqa: F401  (fixture)
from tests.assessment.test_ordering import portal  # noqa: F401  (fixture)
from tests.journey.temas.test_s4_propuesta import log_in, page

pytestmark = pytest.mark.django_db


def link(procedure, document, fmt):
    return reverse("expedientes:s4_exportar_archivo", args=[procedure.pk, document, fmt])


def test_the_block_is_at_the_foot_of_the_tab_with_the_four_downloads(
        client, proposed, procedure, operator_user):
    """REQ-093: planilla por oferta y cuadro comparativo, cada uno con Excel y PDF, después del
    dictamen."""
    log_in(client, operator_user)
    html = page(client, procedure)
    assert html.index('id="s4-dictamen"') < html.index('id="s4-exportar"')
    block = html.split('id="s4-exportar"', 1)[1]
    assert "Planilla por oferta" in block and "Cuadro comparativo" in block
    for document in ("planilla", "cuadro"):
        for fmt in ("xlsx", "pdf"):
            assert f'href="{link(procedure, document, fmt)}"' in block
    assert re.findall(r">(Excel|PDF)</a>", block) == ["Excel", "PDF"] * 2


def test_downloading_gives_the_file_and_leaves_the_fact(
        client, proposed, procedure, evaluator_user):
    """REQ-093: la descarga entrega el archivo con su nombre y queda el hecho de auditoría."""
    log_in(client, evaluator_user)
    response = client.get(link(procedure, "planilla", "xlsx"))
    assert response.status_code == 200
    disposition = response["Content-Disposition"]
    assert "attachment" in disposition and ".xlsx" in disposition
    assert len(read_xlsx(b"".join(response.streaming_content))) == 3
    response = client.get(link(procedure, "cuadro", "pdf"))
    assert response.status_code == 200 and response["Content-Type"] == "application/pdf"
    assert b"".join(response.streaming_content).startswith(b"%PDF")
    assert AuditEvent.objects.filter(event_type=EventType.EVAL_EXPORT).count() == 2


def test_unknown_document_is_not_found_and_no_session_is_sent_to_login(
        client, proposed, procedure, operator_user):
    """REQ-093: un documento que no existe da 404; sin sesión se pide ingresar."""
    anonymous = client.get(link(procedure, "planilla", "xlsx"))
    assert anonymous.status_code == 302 and "/ingresar/" in anonymous["Location"]
    log_in(client, operator_user)
    assert client.get(link(procedure, "otro", "xlsx")).status_code == 404
    assert client.get(link(procedure, "cuadro", "csv")).status_code == 404
