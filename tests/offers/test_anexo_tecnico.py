"""Anexo técnico del oferente como tipo fijado por la acción (REQ-087; plan 014, T-204).

La ficha o el folleto técnico que sube la Comisión dentro de la oferta queda como documento de
tipo `anexo_tecnico`; la clasificación por reglas al leer no lo pisa, ni al reclasificar.
Textos inventados (P4)."""

import pytest

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.offers import models as om
from evaluon.offers.services import offers as services
from evaluon.tenders import jobs
from tests.tenders.pdfs import para, tender_pdf

pytestmark = pytest.mark.django_db


def folleto(text="FICHA TECNICA del producto ofrecido"):
    return tender_pdf([[para(text, "Rendimiento declarado por el fabricante.")]], header=None)


@pytest.fixture
def new_offer(procedure, operator_user):
    return services.register_offer(operator_user, procedure, bidder="Oferente de anexos")


def test_a_technical_sheet_loaded_with_the_kind_is_a_technical_annex_of_the_offer(
        new_offer, operator_user, fake_ai):
    """REQ-087: la ficha técnica subida con el tipo figura como anexo técnico de esa oferta y
    el hecho de carga lo dice."""
    loaded = services.load_document(operator_user, new_offer, data=folleto(),
                                    file_name="ficha.pdf", kind=om.DocumentKind.ANEXO_TECNICO)
    assert loaded.document.kind == "anexo_tecnico" and loaded.document.offer == new_offer
    assert loaded.event.detail["kind"] == "anexo_tecnico"
    assert loaded.event.outcome == Outcome.OK


def test_the_rules_classification_does_not_overwrite_the_fixed_kind(
        new_offer, operator_user, fake_ai):
    """REQ-087: aunque el nombre y el texto digan «ficha técnica» (que las reglas clasifican
    como documentación técnica), al leer el documento sigue siendo anexo técnico."""
    loaded = services.load_document(operator_user, new_offer, data=folleto(),
                                    file_name="ficha-tecnica.pdf",
                                    kind=om.DocumentKind.ANEXO_TECNICO)
    while jobs.run_next() is not None:
        pass
    loaded.document.refresh_from_db()
    assert loaded.document.readings.exists()
    assert loaded.document.kind == om.DocumentKind.ANEXO_TECNICO
    # Sin tipo fijado, las mismas reglas lo clasifican como documentación técnica.
    other = services.load_document(operator_user, new_offer,
                                   data=folleto("FICHA TECNICA de otro producto"),
                                   file_name="ficha-tecnica-otro.pdf")
    while jobs.run_next() is not None:
        pass
    other.document.refresh_from_db()
    assert other.document.kind == om.DocumentKind.TECNICA


def test_reclassifying_does_not_touch_a_technical_annex(new_offer, operator_user, fake_ai):
    """REQ-087: volver a clasificar los documentos del procedimiento no pisa el anexo."""
    loaded = services.load_document(operator_user, new_offer, data=folleto(),
                                    file_name="ficha-tecnica.pdf",
                                    kind=om.DocumentKind.ANEXO_TECNICO)
    while jobs.run_next() is not None:
        pass
    services.reclassify_documents(operator_user, new_offer.procedure)
    loaded.document.refresh_from_db()
    assert loaded.document.kind == om.DocumentKind.ANEXO_TECNICO


def test_a_technical_annex_is_one_of_the_documents_of_the_offer(new_offer, operator_user,
                                                                fake_ai):
    """REQ-087: el anexo es documento propio de la oferta (a diferencia del informe del área)."""
    loaded = services.load_document(operator_user, new_offer, data=folleto(),
                                    file_name="ficha.pdf", kind=om.DocumentKind.ANEXO_TECNICO)
    assert loaded.document in services.own_documents(new_offer)


def test_a_user_without_commission_role_cannot_load_an_annex(new_offer, no_commission_user):
    """REQ-087: sin rol de la Comisión no se sube; queda el rechazo y ningún documento."""
    with pytest.raises(RoleRejected):
        services.load_document(no_commission_user, new_offer, data=folleto(),
                               file_name="ficha.pdf", kind=om.DocumentKind.ANEXO_TECNICO)
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).exists()
    assert not new_offer.documents.exists()
