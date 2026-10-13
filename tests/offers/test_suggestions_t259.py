"""Clase sugerida al subir un documento a una oferta (REQ-104; T-259; informe del comité, H4 y
acción A5; P3, P9).

- Un informe del organismo con las consultas a bases externas (Registro de Proveedores, REPSAL,
  deuda, penalidades), como el documento 41 de la oferta 3 del caso-00, recibe la sugerencia
  «hoja de compliance»; el tipo no cambia hasta que un evaluador lo confirma.
- Un documento casi igual a otro de la misma oferta recibe la sugerencia «copia»; no se quita ni
  se borra nada.

Textos inventados (P4); los PDF se arman con `tests/tenders/pdfs.py` y la lectura corre con
`jobs.run_next()` como en el `worker`.
"""

import re

import pytest
from django.urls import reverse

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType
from evaluon.offers import models as om
from evaluon.offers import suggestions
from evaluon.offers.services import offers as services
from evaluon.tenders import jobs
from tests.accounts.test_session import TEST_PASSWORD
from tests.tenders.pdfs import para, tender_pdf

pytestmark = pytest.mark.django_db

COMPLIANCE_LINES = (
    "Referencia: CONSULTAS PROVEEDOR SINTÉTICO S.A. EXP. 2099-00000001",
    "REGISTRO DE PROVEEDORES - Estado: Inscripto",
    "REPSAL - Registro público de empleadores con sanciones laborales:",
    "a la fecha de emisión no registra sanciones.",
    "CONSULTA DEUDA PROVEEDORES DEL ESTADO: SIN DEUDA.",
    "PENALIDADES Y MULTAS: no registra.",
)
POLICY_LINES = (
    "PÓLIZA DE SEGURO DE CAUCIÓN SINTÉTICA N.º 0001 para garantizar el mantenimiento",
    "de la oferta presentada por Proveedor Sintético S.A. en la licitación inventada",
    "número 99 del año 2099, por la suma asegurada de pesos cien mil, con vigencia",
    "desde la apertura de las ofertas y hasta la extinción de las obligaciones del",
    "tomador, conforme a las condiciones generales y particulares que se adjuntan.",
)


@pytest.fixture
def new_offer(procedure, operator_user):
    return services.register_offer(operator_user, procedure, bidder="Proveedor Sintético")


def load_and_read(user, offer, name, *paragraphs):
    data = tender_pdf([[para(*lines) for lines in paragraphs]], header=None)
    document = services.load_document(user, offer, data=data, file_name=name).document
    while jobs.run_next() is not None:
        pass
    document.refresh_from_db()
    return document


def latest_report(document):
    return document.readings.order_by("-sequence").first().report


# --- Reglas ------------------------------------------------------------------------------------


def test_a_report_of_external_consultations_suggests_a_compliance_sheet():
    """REQ-104 (T-259, H4): con «consulta» y dos marcas o más, la sugerencia es hoja de
    compliance, con las marcas encontradas en su motivo."""
    found = suggestions.suggest("\n".join(COMPLIANCE_LINES))
    assert found["kind"] == "compliance"
    assert found["marks"] == ["Registro de Proveedores", "REPSAL", "deuda con el Estado",
                              "penalidades"]
    assert "REPSAL" in found["reason"] and found["reason"].startswith("Parece una hoja")


def test_a_declaration_that_only_names_a_registry_is_not_a_compliance_sheet():
    """REQ-104 (T-259; P9): una declaración del oferente que nombra un registro, sin el
    resultado de una consulta, no recibe la sugerencia; tampoco un documento que ya es hoja de
    compliance."""
    declaration = ("Declaro bajo juramento que no me encuentro incluido en el REPSAL ni tengo "
                   "deuda con el Estado.")
    assert suggestions.suggest(declaration) is None
    assert suggestions.suggest("\n".join(COMPLIANCE_LINES), fixed_kind=True) is None


def test_an_almost_identical_text_of_the_same_offer_suggests_a_copy():
    """REQ-104 (T-259, H4): un texto casi igual al de otro documento de la oferta es una copia
    sugerida, con el otro documento y la proporción; uno distinto o muy corto, no."""
    policy = " ".join(POLICY_LINES)
    found = suggestions.suggest(policy + " Copia.", [(7, "Póliza", policy)])
    assert found["kind"] == "duplicate" and found["of_document"] == 7
    assert found["share"] >= suggestions.DUPLICATE_SHARE and "«Póliza»" in found["reason"]
    assert suggestions.suggest(policy, [(7, "Otro", " ".join(COMPLIANCE_LINES))]) is None
    assert suggestions.suggest("Hoja sin texto", [(7, "Otra", "Hoja sin texto")]) is None


# --- Al leer y al confirmar ------------------------------------------------------------------------


def test_reading_suggests_the_compliance_sheet_without_changing_the_kind(
        new_offer, operator_user, fake_ai):
    """REQ-104 (T-259; P9): la lectura deja la sugerencia en su informe y en el hecho
    `offer_read`, pero el tipo del documento no pasa a hoja de compliance por eso."""
    document = load_and_read(operator_user, new_offer, "informe-consultas.pdf",
                             COMPLIANCE_LINES)
    assert latest_report(document)["suggestion"]["kind"] == "compliance"
    assert document.kind != om.DocumentKind.COMPLIANCE
    event = AuditEvent.objects.filter(event_type=EventType.OFFER_READ,
                                      detail__document=document.pk).latest("id")
    assert event.detail["suggestion"]["kind"] == "compliance"


def test_an_evaluator_confirms_it_and_it_becomes_the_compliance_sheet(
        new_offer, operator_user, evaluator_user, fake_ai):
    """REQ-104 (T-259; P9): un evaluador confirma la sugerencia; el documento pasa a hoja de
    compliance, queda el hecho con quién lo confirmó y nada se borra. Un operador no puede."""
    document = load_and_read(operator_user, new_offer, "informe-consultas.pdf",
                             COMPLIANCE_LINES)
    with pytest.raises(RoleRejected):
        services.confirm_compliance(operator_user, document)

    services.confirm_compliance(evaluator_user, document)

    document.refresh_from_db()
    assert document.kind == om.DocumentKind.COMPLIANCE
    event = AuditEvent.objects.get(event_type=EventType.OFFER_READ,
                                   detail__action="confirm_compliance")
    assert event.user == evaluator_user and event.detail["document"] == document.pk
    assert om.Document.objects.filter(pk=document.pk).exists()
    assert services.suggestion_of(document) is None


def test_without_the_suggestion_the_confirmation_is_refused(
        new_offer, operator_user, evaluator_user, fake_ai):
    """REQ-104 (T-259; P9): un documento sin la sugerencia no se convierte en hoja de
    compliance por esta vía."""
    document = load_and_read(operator_user, new_offer, "poliza.pdf", POLICY_LINES)
    with pytest.raises(services.OfferRefused, match="no sugirió"):
        services.confirm_compliance(evaluator_user, document)
    document.refresh_from_db()
    assert document.kind != om.DocumentKind.COMPLIANCE


def test_a_second_copy_gets_the_copy_suggestion_and_nothing_is_removed(
        new_offer, operator_user, fake_ai):
    """REQ-104 (T-259, H4): la segunda póliza casi igual recibe la sugerencia de copia de la
    primera; las dos siguen vigentes y la primera no recibe nada."""
    first = load_and_read(operator_user, new_offer, "poliza.pdf", POLICY_LINES)
    second = load_and_read(operator_user, new_offer, "poliza (1).pdf", POLICY_LINES,
                           ("Copia.",))
    suggestion = latest_report(second)["suggestion"]
    assert suggestion["kind"] == "duplicate" and suggestion["of_document"] == first.pk
    assert "suggestion" not in latest_report(first)
    assert set(new_offer.documents.values_list("pk", flat=True)) == {first.pk, second.pk}


def test_the_offer_tab_shows_the_suggestion_and_the_evaluator_can_confirm(
        client, procedure, new_offer, operator_user, evaluator_user, fake_ai):
    """REQ-104 (T-259): la pestaña Ofertas muestra la sugerencia junto al documento, con
    «Confirmar» para el evaluador; al confirmar vuelve con lo hecho."""
    document = load_and_read(operator_user, new_offer, "informe-consultas.pdf",
                             COMPLIANCE_LINES)
    assert client.login(username=evaluator_user.username, password=TEST_PASSWORD)
    tab = reverse("expedientes:ofertas", args=[procedure.pk]) + f"?oferta={new_offer.pk}"
    html = client.get(tab).content.decode()
    shown = re.search(rf'id="sugerencia-{document.pk}"[^>]*>(.*?)</p>', html, re.S)
    assert shown and "Sugerencia del sistema" in shown.group(1)
    confirm = reverse("expedientes:s3_ofertas_es_compliance", args=[procedure.pk, document.pk])
    assert confirm in html

    response = client.post(confirm)
    assert response.status_code == 302
    document.refresh_from_db()
    assert document.kind == om.DocumentKind.COMPLIANCE
