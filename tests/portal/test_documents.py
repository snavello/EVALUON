"""Documentos del Portal con su huella (REQ-046, REQ-048, REQ-049, REQ-051; T-142).

Con el calco `portal-chico` y un portal de mentira (sin red, P4): los documentos se bajan por
URL directa o por envío de formulario, se guardan con su huella, se proponen con su origen y,
aprobados, se cargan con `load_document` de la 003 o quedan como archivo del Portal.
"""

import hashlib
from datetime import date
from urllib.parse import parse_qs

import pytest
import yaml
from django.urls import reverse

from evaluon.audit.models import AuditEvent, EventType
from evaluon.portal.models import ItemKind, ItemState, LoadedModel, PortalFile, PortalItem
from evaluon.portal.services import approval
from evaluon.tenders import jobs
from evaluon.tenders.models import (
    PORTAL_JOB_KINDS,
    Document,
    DocumentKind,
    Job,
    JobKind,
)
from evaluon.tenders.services.documents import load_document
from tests.conftest import TEST_PASSWORD
from tests.portal.conftest import ALLOWED, reply
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

RESPUESTAS = yaml.safe_load((DATA / "respuestas.yaml").read_text(encoding="utf-8"))
PLIEGO_GENERAL = "Pliego de Bases y Condiciones Generales"
CLAUSULAS = "Clausulas Particulares"


def sha(name):
    return hashlib.sha256((DATA / name).read_bytes()).hexdigest()


def serve_documents(portal, version=1):
    """Agrega al portal de mentira lo que responde a los documentos del calco: los envíos de
    formulario (POST a la página del proceso) y los GET directos. El Pliego general
    responde con una redirección a la pantalla de error, como el Portal real."""
    forms = dict(RESPUESTAS["envios_de_formulario"])
    extra = forms.pop("solo_version_2")
    if version == 2:
        forms.update(extra)

    def post(request):
        target = parse_qs(request.body.decode())["__EVENTTARGET"][0]
        answer = forms.get(target)
        if answer is None:
            return reply(request.url, b"no existe", status=404)
        if "redireccion_final" in answer:
            return reply(request.url, b"", status=302, location="/CORE/PantallaError.aspx?qs=x")
        headers = {}
        if "content_disposition" in answer:
            headers["content-disposition"] = answer["content_disposition"]
        return reply(request.url, (DATA / answer["archivo"]).read_bytes(), **headers)

    portal.routes[("POST", LINK_URL)] = post
    portal.routes[("GET", f"https://{ALLOWED}/CORE/PantallaError.aspx?qs=x")] = reply(
        "", (DATA / "error-pantalla.html").read_bytes())
    for path, answer in RESPUESTAS["get_directos"].items():
        portal.routes[("GET", f"https://{ALLOWED}{path}")] = reply(
            "", (DATA / answer["archivo"]).read_bytes())


@pytest.fixture
def docs_portal(portal_client):
    serve_documents(portal_client)
    return portal_client


def document_items():
    return {i.payload["nombre"]: i for i in PortalItem.objects.filter(kind=ItemKind.DOCUMENTO)}


def load_procedure(evaluator, link):
    """Aprueba el procedimiento (con la fecha candidata) para poder cargar documentos."""
    item = PortalItem.objects.get(proposal__link=link, kind=ItemKind.PROCEDIMIENTO)
    approval.decide(evaluator, [item.pk], approval.APPROVE,
                    confirmations={item.pk: {"authorization_date": date(2025, 11, 14)}})
    link.refresh_from_db()
    assert link.procedure is not None


def test_documents_are_proposed_with_their_fingerprint(operator_user, explore_link, docs_portal):
    """REQ-046, REQ-049: cada documento que se puede bajar se propone con la huella del
    archivo bajado, que es la del calco, y con la página de origen."""
    link, job = explore_link(operator_user)
    assert job.status == "done", job.error
    items = document_items()
    expected = {d["nombre"]: d for d in EXPECTED["documentos"]
                if d.get("sha256") and d["nombre"] != "Cuadro comparativo de ofertas"}
    assert expected and set(expected) <= set(items)
    for name, want in expected.items():
        item = items[name]
        assert item.payload["archivo"]["sha256"] == want["sha256"]
        assert item.file.sha256 == want["sha256"]
        assert bytes(item.file.content) == (DATA / want["archivo"]).read_bytes()
        assert item.page.fetched_at is not None and item.state == ItemState.PROPUESTO
    # Acta y dictamen, de URL directa, también.
    assert items["Acta de Apertura"].file.sha256 == sha("acta-apertura.html")
    assert items["Dictamen de Evaluación"].file.sha256 == sha("dictamen.html")


def test_general_tender_error_screen_is_reported_not_broken(
        operator_user, explore_link, docs_portal):
    """REQ-051: el Pliego general da pantalla de error: se informa como anomalía, queda la
    carga manual y el resto se propone igual."""
    link, job = explore_link(operator_user)
    assert job.status == "done", job.error
    proposal = PortalItem.objects.first().proposal
    text = " ".join(f"{a['parte']} {a['motivo']}" for a in proposal.anomalies)
    assert PLIEGO_GENERAL in text and "pantalla de error" in text and "carga manual" in text
    assert PLIEGO_GENERAL not in document_items()
    assert CLAUSULAS in document_items()


def test_documents_the_portal_cannot_serve_are_anomalies(operator_user, explore_link, docs_portal):
    """REQ-051: un documento que no se baja (404) o que no es PDF ni web guardada es
    anomalía; los demás siguen."""
    docs_portal.routes[("GET", next(
        u for (m, u) in list(docs_portal.routes) if "GenerarActaApertura" in u))] = reply(
            "", b"", status=404)
    docs_portal.routes[("GET", next(
        u for (m, u) in list(docs_portal.routes) if "PreAdjudicar" in u))] = reply(
            "", b"\x00\x01\x02 datos que no son un documento")
    link, job = explore_link(operator_user)
    assert job.status == "done", job.error
    items = document_items()
    assert "Acta de Apertura" not in items and "Dictamen de Evaluación" not in items
    assert CLAUSULAS in items
    anomalies = PortalItem.objects.first().proposal.anomalies
    assert any("Acta de Apertura" in a["parte"] for a in anomalies)
    assert any("no es un PDF" in a["motivo"] for a in anomalies)


def test_exploration_event_records_each_file_with_its_fingerprint(
        operator_user, explore_link, docs_portal):
    """P6, REQ-049: el hecho de la exploración lista cada archivo con huella y fecha."""
    explore_link(operator_user)
    event = AuditEvent.objects.filter(event_type=EventType.PORTAL_EXPLORE).get()
    shas = {f["sha256"] for f in event.detail["files"]}
    assert sha("clausulas-particulares.pdf") in shas and sha("acta-apertura.html") in shas
    assert all(f["fetched_at"] for f in event.detail["files"])


def test_operator_approves_a_tender_document_and_loads_it_with_load_document(
        operator_user, evaluator_user, explore_link, docs_portal):
    """REQ-048, REQ-049: el operador aprueba un documento; se carga por `load_document`
    con la misma huella que el archivo bajado y su lectura queda encolada."""
    link, _ = explore_link(operator_user)
    load_procedure(evaluator_user, link)
    item = document_items()[CLAUSULAS]
    [result] = approval.decide(operator_user, [item.pk], approval.APPROVE)
    assert result.result == approval.LOADED, result.reason
    item.refresh_from_db()
    document = Document.objects.get(pk=item.loaded_id)
    assert item.loaded_model == LoadedModel.DOCUMENT and item.state == ItemState.CARGADO
    assert document.kind == DocumentKind.PLIEGO and document.procedure == link.procedure
    assert document.file_sha256 == item.file.sha256 == sha("clausulas-particulares.pdf")
    assert Job.objects.filter(kind=JobKind.READ_DOCUMENT, document=document).exists()
    assert item.decided_by == operator_user


def test_operator_cannot_approve_the_procedure_but_the_documents_wait_for_it(
        operator_user, explore_link, docs_portal):
    """REQ-048: sin procedimiento cargado un documento no se carga; queda propuesto."""
    explore_link(operator_user)
    item = document_items()[CLAUSULAS]
    [result] = approval.decide(operator_user, [item.pk], approval.APPROVE)
    assert result.result == approval.PENDING and "procedimiento" in result.reason
    assert not Document.objects.exists()


def test_act_stays_as_a_portal_file_and_is_downloadable(
        client, operator_user, evaluator_user, explore_link, docs_portal):
    """Decisión del plan: acto, acta y dictamen no pasan por la 003; quedan como archivo
    del Portal con su origen y se descargan desde lo importado."""
    link, _ = explore_link(operator_user)
    load_procedure(evaluator_user, link)
    item = document_items()["Adjudicación y OC"]
    [result] = approval.decide(operator_user, [item.pk], approval.APPROVE)
    assert result.result == approval.KEPT_AS_FILE
    item.refresh_from_db()
    assert item.state == ItemState.APROBADO and not Document.objects.exists()
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    page = client.get(reverse("portal:imported", args=[link.pk])).content.decode()
    assert "Adjudicación y OC" in page and item.file.sha256 in page
    assert "Archivo del Portal" in page
    response = client.get(reverse("portal:download", args=[link.pk, item.file_id]))
    assert response.status_code == 200
    assert response.content == (DATA / "adjudicacion-oc.pdf").read_bytes()
    assert response["Content-Type"] == "application/pdf"


def test_download_only_serves_files_of_the_link(client, operator_user, explore_link, docs_portal):
    link, _ = explore_link(operator_user)
    stored = PortalFile.objects.first()
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    assert client.get(reverse("portal:download", args=[link.pk + 99, stored.pk])).status_code == 404
    client.logout()
    assert client.get(reverse("portal:download", args=[link.pk, stored.pk])).status_code in (302, 403)


def test_duplicate_document_is_refused_with_a_notice(
        operator_user, evaluator_user, explore_link, docs_portal):
    """El mismo archivo ya cargado a mano se rechaza con aviso; no se carga dos veces."""
    link, _ = explore_link(operator_user)
    load_procedure(evaluator_user, link)
    load_document(operator_user, link.procedure,
                  data=(DATA / "clausulas-particulares.pdf").read_bytes(),
                  file_name="a-mano.pdf", kind=DocumentKind.PLIEGO, title="Cargado a mano")
    item = document_items()[CLAUSULAS]
    [result] = approval.decide(operator_user, [item.pk], approval.APPROVE)
    assert result.result == approval.FAILED and "ya está cargado" in result.reason
    assert Document.objects.count() == 1
    item.refresh_from_db()
    assert item.state == ItemState.FALLIDO


def test_manual_document_is_shown_as_manual_load(
        client, operator_user, evaluator_user, explore_link, docs_portal):
    """REQ-051: lo cargado a mano en el mismo procedimiento figura como "carga manual" y
    convive con lo importado, que muestra su página y su fecha."""
    link, _ = explore_link(operator_user)
    load_procedure(evaluator_user, link)
    load_document(operator_user, link.procedure, data=(DATA / "adjudicacion-oc.pdf").read_bytes(),
                  file_name="manual.pdf", kind=DocumentKind.ANEXO, title="Anexo cargado a mano")
    item = document_items()[CLAUSULAS]
    approval.decide(operator_user, [item.pk], approval.APPROVE)
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    html = client.get(reverse("portal:imported", args=[link.pk])).content.decode()
    assert "Anexo cargado a mano" in html and "Carga manual" in html
    assert CLAUSULAS in html and "Portal · página consultada el" in html
    assert html.count("Carga manual") == 1  # lo importado no figura como manual


def test_review_does_not_propose_decided_documents_again(
        operator_user, evaluator_user, explore_link, docs_portal):
    """REQ-050 (base): lo aprobado con la misma huella no se vuelve a proponer, y el
    archivo igual no se guarda dos veces."""
    link, _ = explore_link(operator_user)
    load_procedure(evaluator_user, link)
    item = document_items()[CLAUSULAS]
    approval.decide(operator_user, [item.pk], approval.APPROVE)
    files_before = PortalFile.objects.count()
    jobs.enqueue("portal_review", procedure=None, requested_by=operator_user, target_id=link.pk)
    jobs.run_next(kinds=PORTAL_JOB_KINDS)
    assert PortalItem.objects.filter(kind=ItemKind.DOCUMENTO, key=item.key).count() == 1
    assert PortalFile.objects.count() == files_before


# --- Circulares ----------------------------------------------------------------------------


@pytest.fixture
def circular_portal(docs_portal):
    serve_documents(docs_portal, version=2)
    docs_portal.serve("proceso-con-circular.html")
    return docs_portal


def circular_item():
    return next(i for i in PortalItem.objects.filter(kind=ItemKind.DOCUMENTO)
                if i.payload["clase"] == "circular")


def test_circular_is_opened_with_a_get_and_asks_for_its_type(
        operator_user, explore_link, circular_portal):
    """REQ-046: la circular se abre con GET de `VistaPreviaCircularCiudadano.aspx?qs=`; el
    Portal dice «Con consulta» y no el tipo: el ítem lo pide."""
    explore_link(operator_user)
    item = circular_item()
    gets = [r.url for r in circular_portal.requests if r.method == "GET"]
    assert any("VistaPreviaCircularCiudadano.aspx?qs=" in u for u in gets)
    assert item.payload["tipo_circular"] is None and item.payload["tipo_portal"] == "Con consulta"
    assert item.payload["fecha"] == "2026-07-02"
    assert item.file.sha256 == sha("circular-1.html")


def test_circular_cannot_be_approved_without_a_type(
        operator_user, evaluator_user, explore_link, circular_portal):
    link, _ = explore_link(operator_user)
    load_procedure(evaluator_user, link)
    item = circular_item()
    [result] = approval.decide(operator_user, [item.pk], approval.APPROVE)
    assert result.result == approval.PENDING and "modificatoria o aclaratoria" in result.reason
    assert not Document.objects.exists()
    item.refresh_from_db()
    assert item.state == ItemState.PROPUESTO and item.decided_by is None


def test_circular_loaded_with_the_chosen_type(
        operator_user, evaluator_user, explore_link, circular_portal):
    """REQ-048: quien aprueba elige el tipo; la circular se carga con su fecha del Portal."""
    link, _ = explore_link(operator_user)
    load_procedure(evaluator_user, link)
    item = circular_item()
    [result] = approval.decide(
        operator_user, [item.pk], approval.APPROVE,
        confirmations={item.pk: {"circular_kind": DocumentKind.CIRCULAR_ACLARATORIA}})
    assert result.result == approval.LOADED, result.reason
    document = Document.objects.get()
    assert document.kind == DocumentKind.CIRCULAR_ACLARATORIA
    assert document.issued_on == date(2026, 7, 2)
    assert document.file_sha256 == sha("circular-1.html")


def test_circular_type_is_chosen_on_the_screen(
        client, operator_user, evaluator_user, explore_link, circular_portal):
    link, _ = explore_link(operator_user)
    load_procedure(evaluator_user, link)
    item = circular_item()
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    html = client.get(reverse("portal:proposal", args=[link.pk])).content.decode()
    assert f'name="tipo_{item.pk}"' in html
    response = client.post(reverse("portal:decide", args=[link.pk]),
                           {"decision": "aprobar", "item": [item.pk],
                            f"tipo_{item.pk}": "circular_modificatoria"})
    assert response.status_code == 200
    assert Document.objects.get().kind == DocumentKind.CIRCULAR_MODIFICATORIA


def test_circular_with_an_invalid_type_is_not_loaded(
        client, operator_user, evaluator_user, explore_link, circular_portal):
    link, _ = explore_link(operator_user)
    load_procedure(evaluator_user, link)
    item = circular_item()
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    client.post(reverse("portal:decide", args=[link.pk]),
                {"decision": "aprobar", "item": [item.pk], f"tipo_{item.pk}": "pliego"})
    assert not Document.objects.exists()


def test_circular_without_a_date_asks_for_it(operator_user, evaluator_user):
    """La fecha es obligatoria: sin ella en el Portal y sin confirmar, no se aprueba."""
    from evaluon.portal.importers import documents

    class Fake:
        payload = {"clase": "circular", "fecha": None, "tipo_circular": "circular_aclaratoria"}

    assert "fecha" in documents.blocker(Fake, {})
    assert documents.blocker(Fake, {"issued_on": date(2026, 7, 2)}) == ""
