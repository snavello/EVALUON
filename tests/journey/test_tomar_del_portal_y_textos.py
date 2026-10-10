"""«Tomar del Portal» en Pliego y en Ofertas, y textos repetidos o sin nombre (REQ-084, REQ-097; plan
014, T-232, puntos P-8, O-3, H-1 y O-1 de la revisión C). Todo el material es inventado (P4)."""

import datetime
import html as htmllib
import itertools
import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from evaluon.journey import window
from evaluon.offers.services import offers as offers_service
from evaluon.portal import models as p
from evaluon.tenders.models import JobStatus, Procedure
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.temas.test_s3_ofertas import notice, url as s3_url
from tests.journey.conftest import progress_steps, simulate, two_offers  # noqa: F401  (fixtures)
from tests.tenders.conftest import evaluator_user, operator_user  # noqa: F401
from tests.tenders.pdfs import para, tender_pdf

pytestmark = pytest.mark.django_db

_n = itertools.count(1)


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


@pytest.fixture
def followed(operator_user):
    """Un procedimiento que sigue un proceso del Portal que lista un documento y una circular sin
    tomar."""
    procedure = Procedure.objects.create(
        number=f"PORTAL-{next(_n)}", procedure_type="Licitación pública", subject="Inventado",
        authorization_date=datetime.date(2026, 3, 3), created_by=operator_user)
    link = p.PortalLink.objects.create(url="https://portal.ejemplo.test/x?qs=9",
                                       procedure=procedure, created_by=operator_user)
    proposal = p.PortalProposal.objects.create(link=link, exploration=1,
                                               origin=p.Origin.IMPORTACION)
    page_row = p.PortalPage.objects.create(link=link, exploration=1, kind=p.PageKind.PROCESO,
                                           url=link.url, sha256="a" * 64, content=b"x")
    for key, name, clase in (("a1", "Anexo inventado", "anexo"),
                             ("c1", "Circular inventada", "circular")):
        p.PortalItem.objects.create(proposal=proposal, kind=p.ItemKind.DOCUMENTO, key=key,
                                    payload={"nombre": name, "clase": clase},
                                    content_sha256="b" * 64, page=page_row)
    return procedure


def portal_hrefs(html):
    """Los destinos de los enlaces y botones «Tomar del Portal»."""
    return re.findall(r'<a [^>]*href="([^"]+)"[^>]*>\s*Tomar del Portal\s*</a>', html)


# --- P-8 y O-3: «Tomar del Portal» lleva al bloque del Portal de su pestaña ----------------------


@pytest.mark.parametrize("tab_name", ["pliego", "ofertas"])
def test_take_from_the_portal_goes_to_the_portal_block_of_the_procedure(
        client, followed, operator_user, tab_name):
    """REQ-097: en Pliego y en Ofertas, «Tomar del Portal» lleva al bloque del Portal del
    procedimiento, no al alta ni a la ruta vieja de importación."""
    log_in(client, operator_user)
    html = client.get(reverse(f"expedientes:{tab_name}", args=[followed.pk])).content.decode()
    target = reverse("expedientes:procedimiento", args=[followed.pk]) + "#s1-portal"
    hrefs = portal_hrefs(html)
    assert hrefs and set(hrefs) == {target}, hrefs
    assert not any("/expedientes/nuevo/" in h or "/importar/" in h for h in hrefs)


def test_the_target_of_take_from_the_portal_is_a_page_with_that_block(client, followed,
                                                                      operator_user):
    """REQ-097: el destino no redirige: es la pestaña Procedimiento y tiene el bloque anclado."""
    log_in(client, operator_user)
    target = reverse("expedientes:procedimiento", args=[followed.pk])
    response = client.get(target)
    assert response.status_code == 200 and 'id="s1-portal"' in response.content.decode()


def test_the_missing_line_of_the_pliego_and_of_the_circulars_use_the_same_target(
        followed, operator_user):
    """REQ-097: la fila «Falta» (de la sección) lleva el mismo destino."""
    from evaluon.journey.temas import s2_documentos, s3_circulares
    target = reverse("expedientes:procedimiento", args=[followed.pk]) + "#s1-portal"
    assert s2_documentos.portal_url(followed) == target
    assert s3_circulares.portal_url(followed) == target
    assert {m.url for m in s2_documentos.status(operator_user, followed).missing} == {target}


# --- H-1: «Oferta Oferta 0 de 3» -----------------------------------------------------------------


def test_the_process_window_does_not_repeat_the_word_offer(
        client, procedure, two_offers, simulate, progress_steps, operator_user):
    """REQ-070: «Hecho Oferta 1 de 2», no «Hecho Oferta Oferta 1 de 2»."""
    log_in(client, operator_user)
    made = simulate(two_offers, JobStatus.RUNNING, done=1)
    progress_steps(made.job, ["Evaluando el requisito 1 de 3"], done=1, total=3,
                   scope="Oferta 2 de 2")
    html = client.get(reverse("journey:stages", args=[procedure.pk])).content.decode()
    text = " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", html)).split())
    assert "En esta oferta" in text  # hay cuenta fina: el caso del error
    assert "Oferta Oferta" not in text
    assert "Hecho Oferta 1 de 2" in text


def test_the_window_counts_read_well_with_and_without_detail():
    """REQ-070: el texto de la cuenta gruesa lleva «Oferta» una sola vez."""
    main = window._count("Oferta", "Ofertas por evaluar", 0, 3)
    assert main["text"] == "Oferta 0 de 3"


# --- O-1: aviso de archivo duplicado con el nombre del archivo ------------------------------------


def pdf_file(name, text):
    return SimpleUploadedFile(name, tender_pdf([[para(text)]], header=None))


def test_a_duplicate_notice_names_the_refused_file(client, offer, procedure, operator_user,
                                                   fake_ai):
    """REQ-084: el aviso del archivo repetido empieza con el nombre del archivo rechazado, no con
    «: »."""
    log_in(client, operator_user)
    content = tender_pdf([[para("Texto sintético uno")]], header=None)
    client.post(s3_url("s3_ofertas_documentos", procedure, offer.pk),
                {"files": [SimpleUploadedFile("oferta tecnica.pdf", content)]})
    results = notice(client, client.post(
        s3_url("s3_ofertas_documentos", procedure, offer.pk),
        {"files": [SimpleUploadedFile("oferta tecnica (1).pdf", content)]}))
    assert [ok for ok, _ in results] == [False]
    text = results[0][1]
    assert not text.startswith(":") and not text.startswith(" ")
    assert text.startswith("«oferta tecnica (1).pdf» ya está cargado en esta oferta")
    assert "oferta tecnica.pdf" in text and "No se cargó de nuevo" in text


def test_the_service_message_names_the_file(offer, operator_user):
    """REQ-084: el mensaje del servicio nombra el archivo que se rechaza y el que ya estaba."""
    content = tender_pdf([[para("Texto sintético dos")]], header=None)
    offers_service.load_document(operator_user, offer, data=content, file_name="a.pdf")
    with pytest.raises(offers_service.DuplicateFile) as error:
        offers_service.load_document(operator_user, offer, data=content, file_name="a (1).pdf")
    assert str(error.value).startswith("«a (1).pdf» ya está cargado en esta oferta")
    assert "(a.pdf)" in str(error.value)
