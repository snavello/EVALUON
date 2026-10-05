"""Registrar ofertas, cargar sus documentos y leerlos (REQ-037, REQ-038; plan 008, "Carga y
lectura", "Roles" y "Registro de auditoría"; T-130).

Los documentos son los del caso chico, inventados (`tests/offers/data/caso-chico/`): un PDF
con texto y una constancia escaneada, sin capa de texto, que la lectura reconoce con
Tesseract. La lectura se ejecuta con `jobs.run_next()` sobre la base de pruebas, como la
haría el `worker`."""

import hashlib

import pytest

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.offers import models as om
from evaluon.offers.services import offers as services
from evaluon.tenders import jobs
from evaluon.tenders import models as m
from tests.offers.conftest import DATA
from tests.tenders.pdfs import fields_only_page, para, tender_pdf

pytestmark = pytest.mark.django_db


def events(event_type, outcome=None):
    found = AuditEvent.objects.filter(event_type=event_type)
    return found.filter(outcome=outcome) if outcome else found


@pytest.fixture
def new_offer(procedure, operator_user):
    return services.register_offer(operator_user, procedure, bidder="Oferente nuevo")


def load(user, offer, name="oferta-propuesta.pdf", data=None):
    data = data if data is not None else (DATA / name).read_bytes()
    return services.load_document(user, offer, data=data, file_name=name)


# --- Alta de la oferta -----------------------------------------------------------------


def test_registering_an_offer_numbers_it_and_leaves_its_event(procedure, operator_user):
    """REQ-037: la oferta queda con su oferente y su número, y el hecho no lleva el nombre."""
    first = services.register_offer(operator_user, procedure, bidder="  Uno   S.A. ")
    second = services.register_offer(operator_user, procedure, bidder="Dos")
    assert (first.number, first.bidder, second.number) == (1, "Uno S.A.", 2)
    event = events(EventType.OFFER_REGISTER, Outcome.OK).get(detail__offer=first.pk)
    assert event.user == operator_user and "Uno" not in str(event.detail)


def test_the_same_bidder_twice_is_refused_and_registered(procedure, new_offer, operator_user):
    """REQ-037: un oferente repetido se rechaza con aviso y deja su hecho."""
    with pytest.raises(services.DuplicateBidder):
        services.register_offer(operator_user, procedure, bidder="Oferente nuevo")
    refused = events(EventType.OFFER_REGISTER, Outcome.REJECTED).get()
    assert refused.detail["reason"] == "duplicate_bidder"
    assert procedure.offers.count() == 1


def test_a_blank_bidder_is_refused(procedure, operator_user):
    """REQ-037: sin oferente no hay oferta."""
    with pytest.raises(services.OfferRefused) as error:
        services.register_offer(operator_user, procedure, bidder="  ")
    assert error.value.field == "bidder"
    assert events(EventType.OFFER_REGISTER, Outcome.REJECTED).count() == 1


def test_a_user_without_commission_role_cannot_register(procedure, no_commission_user):
    """REQ-037: sin rol de la Comisión se rechaza y queda el hecho `rejected`."""
    with pytest.raises(RoleRejected):
        services.register_offer(no_commission_user, procedure, bidder="X")
    assert events(EventType.REJECTED).count() == 1
    assert not procedure.offers.exists()


# --- Carga -------------------------------------------------------------------------------


def test_loading_a_document_keeps_the_original_and_its_fingerprint(new_offer, operator_user):
    """REQ-037: la oferta queda con su oferente y sus documentos, cada uno con su huella;
    el original se guarda byte por byte y la lectura queda encolada."""
    data = (DATA / "oferta-propuesta.pdf").read_bytes()
    loaded = load(operator_user, new_offer)
    document = loaded.document
    assert document.file_sha256 == hashlib.sha256(data).hexdigest()
    assert bytes(document.file.content) == data
    assert document.kind == ""  # la persona no elige el tipo
    assert document.title == "oferta-propuesta"
    job = loaded.job
    assert (job.kind, job.target_id, job.status) == (m.JobKind.READ_OFFER_DOCUMENT,
                                                     document.pk, m.JobStatus.QUEUED)
    event = events(EventType.OFFER_LOAD, Outcome.OK).get()
    assert event.detail["file"]["sha256"] == document.file_sha256
    assert event.detail["document"] == document.pk and event.detail["job"] == job.pk


def test_the_same_file_twice_is_refused_and_registered(new_offer, operator_user):
    """REQ-037: el mismo archivo dos veces en la oferta se rechaza con aviso."""
    first = load(operator_user, new_offer)
    with pytest.raises(services.DuplicateFile) as error:
        load(operator_user, new_offer, name="copia.pdf",
             data=(DATA / "oferta-propuesta.pdf").read_bytes())
    assert error.value.loaded_document == first.document.pk
    assert new_offer.documents.count() == 1
    assert m.Job.objects.filter(kind=m.JobKind.READ_OFFER_DOCUMENT).count() == 1
    refused = events(EventType.OFFER_LOAD, Outcome.REJECTED).get()
    assert refused.detail["reason"] == "duplicate_file"
    assert refused.detail["loaded_document"] == first.document.pk


@pytest.mark.parametrize("data, name, reason", [
    (b"", "vacio.pdf", "missing_data"),
    (b"no es un pdf", "texto.pdf", "unsupported_format"),
])
def test_a_missing_or_unsupported_file_is_refused(new_offer, operator_user, data, name, reason):
    """REQ-037: un archivo vacío o que no es PDF se rechaza y deja su hecho."""
    with pytest.raises(services.OfferRefused):
        services.load_document(operator_user, new_offer, data=data, file_name=name)
    assert events(EventType.OFFER_LOAD, Outcome.REJECTED).get().detail["reason"] == reason
    assert not new_offer.documents.exists()


def test_a_user_without_commission_role_cannot_load(new_offer, no_commission_user):
    """REQ-037: sin rol de la Comisión no se carga nada."""
    with pytest.raises(RoleRejected):
        load(no_commission_user, new_offer)
    assert not new_offer.documents.exists()


# --- Lectura ------------------------------------------------------------------------------


def test_reading_a_text_document_saves_passages_with_vectors(new_offer, operator_user, fake_ai):
    """REQ-038: cada página tiene texto; los pasajes llevan página, vector y texto literal."""
    document = load(operator_user, new_offer).document
    assert jobs.run_next().status == m.JobStatus.DONE
    reading = document.readings.get()
    passages = list(reading.passages.order_by("order"))
    assert [p.page for p in passages] == [1, 1, 2, 2, 3]
    assert all(reading.canonical_text[p.char_start:p.char_end] == p.text for p in passages)
    assert all(len(p.embedding) == 1024 for p in passages)
    assert sum(len(call) for call in fake_ai.embeddings.calls) == len(passages)
    report = reading.report
    assert report["pages"] == 3 and report["unread"] == [] == report["without_text_unlisted"]
    event = events(EventType.OFFER_READ, Outcome.OK).get()
    assert event.detail["reading"] == reading.pk and event.detail["passages"] == 5
    assert event.detail["tool_versions"]["embeddings"]["model"]


def test_the_system_classifies_the_document_kind_by_rules(new_offer, operator_user, fake_ai):
    """REQ-037: el tipo lo pone el sistema al leer, por reglas sobre el nombre y el texto."""
    document = load(operator_user, new_offer).document
    jobs.run_next()
    document.refresh_from_db()
    assert document.kind == om.DocumentKind.ECONOMICA


def test_a_document_the_rules_cannot_classify_keeps_an_empty_kind(new_offer, operator_user,
                                                                  fake_ai):
    """REQ-037: si ninguna regla alcanza, el tipo queda vacío."""
    data = tender_pdf([[para("Un texto cualquiera sin palabras clave.")]], header=None)
    document = load(operator_user, new_offer, name="varios.pdf", data=data).document
    jobs.run_next()
    document.refresh_from_db()
    assert document.kind == ""


@pytest.mark.parametrize("name, kind", [
    ("poliza-de-caucion.pdf", "garantia"),
    ("planilla-de-cotizacion.pdf", "economica"),
    ("ficha-tecnica.pdf", "tecnica"),
    ("constancia.pdf", ""),
])
def test_kind_rules_use_the_file_name(name, kind):
    """REQ-037: las reglas del tipo de documento."""
    assert services.classify_kind(name, "") == kind


def test_a_scanned_document_is_read_with_text_recognition(new_offer, operator_user, fake_ai):
    """REQ-038: una constancia escaneada, sin capa de texto, se lee y cada página tiene texto
    o figura en la lista de no leídas."""
    document = load(operator_user, new_offer, name="constancia-escaneada.pdf").document
    jobs.run_next()
    reading = document.readings.get()
    assert reading.pages["pages"][0]["classification"] == "escaneada"
    passages = list(reading.passages.all())
    assert passages and all(p.text_origin == "ocr" for p in passages)
    assert all(p.ocr_confidence_avg and p.ocr_confidence_min for p in passages)
    assert "registro de proveedores" in " ".join(p.text for p in passages)
    assert reading.report["without_text_unlisted"] == []
    assert reading.tool_versions["embeddings"]["model"]


def test_a_page_that_cannot_be_read_goes_to_the_unread_list(new_offer, operator_user, fake_ai):
    """REQ-038: la página sin texto legible figura en la lista de no leídas, con su documento
    y su número; la oferta la muestra."""
    data = tender_pdf([[para("Una página con texto legible, para comparar.")],
                       fields_only_page()], header=None)
    document = load(operator_user, new_offer, name="con-hoja-ilegible.pdf", data=data).document
    jobs.run_next()
    report = document.readings.get().report
    assert [(e["page"], e["document"]) for e in report["unread"]] == [(2, document.pk)]
    assert report["without_text_unlisted"] == []
    page = services.offer_page(operator_user, new_offer.pk)
    assert [e["page"] for e in page.unread] == [2]
    assert page.documents[0].state == services.STATE_READ


def test_a_reading_that_fails_leaves_the_event_and_no_reading(new_offer, operator_user,
                                                              fake_ai):
    """REQ-038 (P6): una falla del servicio de vectores deja el pedido fallido, el hecho
    `failed` y nada a medias."""
    document = load(operator_user, new_offer).document
    fake_ai.embeddings.unavailable()
    job = jobs.run_next()
    assert job.status == m.JobStatus.FAILED and "service_unavailable" in job.error
    assert not document.readings.exists()
    assert events(EventType.OFFER_READ, Outcome.FAILED).count() == 1
    assert services.offer_page(operator_user, new_offer.pk).documents[0].state == \
        services.STATE_FAILED


def test_a_job_whose_document_is_from_another_procedure_fails(new_offer, operator_user,
                                                              fake_ai):
    """ADR-0026: `target_id` no tiene clave foránea: lo controla la función de negocio."""
    load(operator_user, new_offer)
    job = m.Job.objects.get(kind=m.JobKind.READ_OFFER_DOCUMENT)
    other = m.Procedure.objects.create(
        number="OTRO", procedure_type="x", subject="x", authorization_date="2026-01-01",
        created_by=operator_user)
    job.procedure = other
    job.save()
    assert jobs.run_next().status == m.JobStatus.FAILED
    assert not om.Reading.objects.exists()


def test_a_job_with_a_missing_document_fails(procedure, operator_user, fake_ai):
    """ADR-0026: un pedido que apunta a un documento que no existe falla con su motivo."""
    job = jobs.enqueue(m.JobKind.READ_OFFER_DOCUMENT, procedure=procedure,
                       requested_by=operator_user, target_id=987654)
    jobs.run(job)
    job.refresh_from_db()
    assert job.status == m.JobStatus.FAILED and "DoesNotExist" in job.error


def test_a_second_reading_numbers_after_the_first(new_offer, operator_user, fake_ai):
    """REQ-038: una lectura nueva del mismo documento toma el número siguiente."""
    document = load(operator_user, new_offer).document
    jobs.run_next()
    jobs.enqueue(m.JobKind.READ_OFFER_DOCUMENT, procedure=new_offer.procedure,
                 requested_by=operator_user, target_id=document.pk)
    jobs.run_next()
    assert sorted(document.readings.values_list("sequence", flat=True)) == [1, 2]


def test_the_original_is_delivered_byte_by_byte(new_offer, operator_user):
    """REQ-037: el original se entrega tal como se cargó, solo con rol de la Comisión."""
    document = load(operator_user, new_offer).document
    stored = services.original_file(operator_user, document.pk)
    assert bytes(stored.content) == (DATA / "oferta-propuesta.pdf").read_bytes()
    with pytest.raises(RoleRejected):
        services.original_file(None, document.pk)


def test_the_offers_list_shows_reading_and_sheet_state(procedure, new_offer, operator_user,
                                                       fake_ai):
    """REQ-037: la lista de ofertas muestra cuántos documentos se leyeron."""
    load(operator_user, new_offer)
    _, rows = services.offers_page(operator_user, procedure.pk)
    assert (rows[0].documents, rows[0].read, rows[0].sheet) == (1, 0, None)
    jobs.run_next()
    _, rows = services.offers_page(operator_user, procedure.pk)
    assert rows[0].read == 1


# --- Fotos, segundo intento y enlaces (T-131) ------------------------------------------------


def _photo(kind="jpg", *, angle=0, shadow=0, noise=0, blur=0):
    from tests.offers.test_reading import jpeg, png, synthetic_photo

    image = synthetic_photo(angle, shadow, noise, blur)
    return jpeg(image) if kind == "jpg" else png(image)


@pytest.mark.parametrize("kind", ["jpg", "png"])
def test_a_photo_is_loaded_keeps_its_original_and_is_read(new_offer, operator_user, fake_ai,
                                                         kind):
    """REQ-037, REQ-038: una foto se guarda tal cual, se convierte en el equipo y se lee."""
    data = _photo(kind)
    document = load(operator_user, new_offer, name=f"foto.{kind}", data=data).document
    assert document.file_format == kind
    assert bytes(document.file.content) == data
    assert jobs.run_next().status == m.JobStatus.DONE
    reading = document.readings.get()
    assert reading.report["second_attempt"] == []
    assert "registro de proveedores" in " ".join(p.text for p in reading.passages.all())


def test_a_damaged_photo_and_a_damaged_word_file_are_refused_with_their_event(
        new_offer, operator_user):
    """REQ-037: una foto dañada y un Word dañado se rechazan y dejan su hecho."""
    for name, data, reason in [("rota.jpg", _photo()[:300], "unreadable_file"),
                               ("hoja.docx", b"PKroto", "unsupported_format")]:
        with pytest.raises(services.OfferRefused):
            load(operator_user, new_offer, name=name, data=data)
        assert events(EventType.OFFER_LOAD, Outcome.REJECTED).filter(
            detail__reason=reason).exists()
    assert not new_offer.documents.exists()


def test_the_same_photo_twice_is_refused(new_offer, operator_user):
    """REQ-037: la misma foto dos veces en la oferta se rechaza."""
    data = _photo()
    load(operator_user, new_offer, name="a.jpg", data=data)
    with pytest.raises(services.DuplicateFile):
        load(operator_user, new_offer, name="b.jpg", data=data)


def test_a_crooked_photo_is_read_again_and_the_report_says_which_reading_was_kept(
        new_offer, operator_user, fake_ai):
    """REQ-038: la foto torcida con sombra y ruido queda leída tras el segundo intento; el
    informe de la lectura lo dice, y el hecho `offer_read` lo lleva."""
    document = load(operator_user, new_offer, name="torcida.jpg",
                    data=_photo(angle=7, shadow=200, noise=5, blur=3)).document
    jobs.run_next()
    reading = document.readings.get()
    [attempt] = reading.report["second_attempt"]
    assert attempt["page"] == 1 and attempt["kept"] == "segunda"
    assert reading.report["unread"] == []
    assert "registro de proveedores" in " ".join(p.text for p in reading.passages.all())
    assert events(EventType.OFFER_READ, Outcome.OK).get().detail["second_attempt"] == [attempt]


def test_a_photo_that_cannot_be_read_goes_to_the_unread_list_with_its_page(
        new_offer, operator_user, fake_ai):
    """REQ-038: la foto que sigue ilegible figura en la lista de no leídas, con documento y
    página; no se inventa texto."""
    document = load(operator_user, new_offer, name="mala.jpg",
                    data=_photo(angle=6, shadow=120, noise=8, blur=4.5)).document
    jobs.run_next()
    reading = document.readings.get()
    assert [(e["document"], e["page"]) for e in reading.report["unread"]] == [(document.pk, 1)]
    assert reading.report["second_attempt"][0]["kept"] == "primera"
    assert not reading.passages.exists()
    assert services.offer_page(operator_user, new_offer.pk).unread[0]["page"] == 1


def test_good_pages_do_not_change_their_text_after_the_second_attempt_exists(
        new_offer, operator_user, fake_ai):
    """REQ-038: una oferta con un PDF de texto y un escaneo bueno no relee nada."""
    for name in ("oferta-propuesta.pdf", "constancia-escaneada.pdf"):
        load(operator_user, new_offer, name=name)
        jobs.run_next()
    for reading in om.Reading.objects.all():
        assert reading.report["second_attempt"] == []


@pytest.mark.parametrize("name, text, kind", [
    ("hoja-tecnica-resma.docx", "", "tecnica"),
    ("folleto-cartucho.pdf", "", "tecnica"),
    ("especificaciones-tecnicas-firmadas.pdf", "", "tecnica"),
    ("renglones.pdf", "Renglón 1 · Cantidad 100 · Precio unitario 3.000", "economica"),
    ("anexo.pdf", "HOJA TÉCNICA del producto ofrecido", "tecnica"),
])
def test_a_technical_document_is_classified_but_a_price_table_is_not(name, text, kind):
    """REQ-044: la documentación técnica es un documento técnico (hoja, folleto,
    especificaciones), no una tabla de renglones con precios."""
    assert services.classify_kind(name, text) == kind


def test_the_offer_page_links_the_pages_to_review_and_the_download(client, operator_user,
                                                                   procedure, fake_ai):
    """REQ-038: cada página no leída enlaza al original en esa página; el original se baja."""
    from django.urls import reverse

    from tests.conftest import TEST_PASSWORD

    offer = services.register_offer(operator_user, procedure, bidder="Con foto mala")
    document = load(operator_user, offer, name="mala.jpg",
                    data=_photo(angle=6, shadow=120, noise=8, blur=4.5)).document
    jobs.run_next()
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    body = client.get(reverse("offers:offer", args=[offer.pk])).content.decode()
    original = reverse("offers:document_original", args=[document.pk])
    assert f"{original}#page=1" in body and f"{original}?descargar=1" in body
    assert "Foto JPG" in body
    download = client.get(original + "?descargar=1")
    assert download["Content-Disposition"].startswith("attachment")
    assert download["Content-Type"] == "image/jpeg"


def test_the_procedure_page_links_to_its_offers(client, operator_user, procedure):
    """REQ-037: desde el procedimiento se llega a sus ofertas."""
    from django.urls import reverse

    from tests.conftest import TEST_PASSWORD

    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    body = client.get(reverse("tenders:procedure", args=[procedure.pk])).content.decode()
    assert reverse("offers:procedure_offers", args=[procedure.pk]) in body


def _data_sheet_docx():
    """Un .docx inventado con la forma de una hoja técnica: encabezado, tabla de
    características y bloque de firma."""
    from tests.offers.test_reading import make_docx

    return make_docx(
        ["HOJA TÉCNICA · Resma de papel A4 de 75 gramos", "Marca sintética · Modelo S-75",
         "CARACTERÍSTICAS", "Firmado: Responsable técnico sintético"],
        rows=[("Característica", "Valor"), ("Gramaje", "75 g/m²"),
              ("Hojas por resma", "500"), ("Blancura", "92 %")])


def test_a_word_data_sheet_is_loaded_converted_read_and_classified_technical(
        new_offer, operator_user, fake_ai):
    """REQ-037, REQ-038, REQ-044: la hoja técnica en Word se guarda tal cual, se convierte
    en el equipo, se lee con su tabla y el sistema la clasifica como técnica."""
    data = _data_sheet_docx()
    document = load(operator_user, new_offer, name="hoja-tecnica-resma.docx", data=data).document
    assert document.file_format == "docx" and bytes(document.file.content) == data
    assert jobs.run_next().status == m.JobStatus.DONE
    document.refresh_from_db()
    assert document.kind == om.DocumentKind.TECNICA
    text = " ".join(p.text for p in document.readings.get().passages.all())
    assert "Gramaje" in text and "75 g/m²" in text and "Hojas por resma" in text


def test_a_word_original_is_served_with_its_type(client, operator_user, new_offer, fake_ai):
    """REQ-037: el original Word se entrega como Word."""
    from django.urls import reverse

    from tests.conftest import TEST_PASSWORD

    document = load(operator_user, new_offer, name="hoja.docx", data=_data_sheet_docx()).document
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    response = client.get(reverse("offers:document_original", args=[document.pk]))
    assert response["Content-Type"].endswith("wordprocessingml.document")


@pytest.mark.parametrize("name, text, kind", [
    # título mal leído por el OCR: una letra cambiada en "especificaciones"
    ("firmadas.pdf", "ESPECIFICAC10NES del equipo ofrecido, firmadas por el oferente", "tecnica"),
    ("firmadas.pdf", "Espec1ficaciones del equipo ofrecido", "tecnica"),
    # hoja con un encabezado que no es una frase de la lista
    ("hoja-1.docx", "Datos técnicos del modelo XT-5\nPotencia: 500 W", "tecnica"),
    ("hoja-2.docx", "ESPECIFICACIÓN DEL PRODUCTO\nMarca: Marca Ficticia", "tecnica"),
    ("hoja-3.docx", "Caracteristicas tecn1cas\nPeso: 2 kg", "tecnica"),
    # no se confunde: nada que parezca la raíz, o la tabla de precios del Portal
    ("tabla.pdf", "Renglón Descripción\n1 Resma de papel A4\n2 Cartucho de tóner", ""),
    ("carta.pdf", "Nota de presentación de la oferta a la Comisión", ""),
    ("renglones.pdf", "Renglón 1 · Cantidad 100 · Precio unitario 3.000 · técnico", "economica"),
])
def test_the_technical_root_in_the_header_tolerates_text_recognition_errors(name, text, kind):
    """REQ-044: una hoja con otro encabezado o un título mal leído se clasifica técnica por
    la raíz "tecnic" o "especif" (T-135)."""
    assert services.classify_kind(name, text) == kind


# --- Reclasificar y rearmar lo ya cargado (T-136) -----------------------------------------------


def _long_item_pdf():
    """Un PDF de una página con un solo párrafo largo que trae dos encabezados de renglón."""
    lines = []
    for item in (1, 2):
        lines.append(f"RENGLÓN {item}: alimento balanceado para perros adultos de raza grande.")
        lines += [f"Descripción {item}.{n}: bolsa de veinte kilos, presentación cerrada y "
                  "etiquetada." for n in range(1, 8)]
    return tender_pdf([[para(*lines)]], header=None)


@pytest.fixture
def read_document_of(new_offer, operator_user, fake_ai):
    """Una oferta con un documento ya leído (PDF con texto, dos renglones en un párrafo)."""
    document = load(operator_user, new_offer, name="especificaciones.pdf",
                    data=_long_item_pdf()).document
    jobs.run_next()
    return document


def test_rebuilding_passages_adds_a_new_reading_without_reading_the_file_again(
        read_document_of, operator_user, fake_ai, settings, monkeypatch):
    """REQ-039 (T-136): con el particionado de hoy se arma una lectura nueva desde las páginas
    guardadas, sin OCR ni leer el archivo; la anterior queda como estaba y el texto de cada
    pasaje es el recorte del texto canónico."""
    document = read_document_of
    old = document.readings.get()
    old_passages = list(old.passages.values_list("text", flat=True))
    settings.OFFERS_PASSAGE_MAX_CHARS = 400

    def forbidden(*args, **kwargs):
        raise AssertionError("no se vuelve a leer el archivo")

    monkeypatch.setattr("evaluon.offers.reading.read_with_second_attempt", forbidden)
    monkeypatch.setattr("evaluon.offers.reading.read_document", forbidden)
    new = services.rebuild_passages(operator_user, document)
    assert new.sequence == 2 and new.job is None
    assert new.pages == old.pages and new.canonical_sha256 == old.canonical_sha256
    assert new.passages.count() > len(old_passages)
    for passage in new.passages.all():
        assert passage.text == new.canonical_text[passage.char_start:passage.char_end]
        assert passage.embedding is not None
    assert list(old.passages.values_list("text", flat=True)) == old_passages
    assert document.readings.count() == 2
    event = events(EventType.OFFER_READ, Outcome.OK).filter(
        detail__action="rebuild_passages").get()
    assert event.detail["from_reading"] == old.pk and event.detail["reading"] == new.pk
    assert event.detail["passages"] == new.passages.count()
    assert event.detail["passages_before"] == len(old_passages)


def test_a_rebuild_that_changes_nothing_adds_no_reading(read_document_of, operator_user):
    """REQ-039 (T-136): si el particionado de hoy da los mismos pasajes, no hay lectura nueva."""
    assert services.rebuild_passages(operator_user, read_document_of) is None
    assert read_document_of.readings.count() == 1


def test_a_rebuild_needs_a_commission_role_and_a_reading(new_offer, operator_user,
                                                         read_document_of):
    """REQ-039 (T-136): sin rol no se rearma; un documento sin lectura deja el hecho fallido."""
    with pytest.raises(RoleRejected):
        services.rebuild_passages(None, read_document_of)
    unread = load(operator_user, new_offer, name="otra.pdf", data=_long_item_pdf() + b"\n").document
    with pytest.raises(ValueError):
        services.rebuild_passages(operator_user, unread)
    assert events(EventType.OFFER_READ, Outcome.FAILED).filter(
        detail__action="rebuild_passages").exists()


def test_reclassifying_applies_the_current_rules_and_records_each_change(
        procedure, operator_user):
    """REQ-044 (T-136): se vuelve a aplicar `classify_kind` al nombre y al texto de la última
    lectura de cada documento, sin leer ni OCR; el cambio queda en el registro con el tipo
    anterior. Los que no cambian y los que ninguna regla alcanza no se tocan."""
    from tests.offers.conftest import make_offer

    offer = make_offer(procedure, operator_user, "Reclasificar", {
        "sin-tipo.pdf": ["ESPEC1FICACIONES firmadas por el oferente para el renglón 1."],
        "con-tipo.pdf": ["Planilla de precios del oferente."],
        "nada.pdf": ["Un texto cualquiera sin palabras clave."]},
        kinds={"con-tipo.pdf": "economica", "nada.pdf": "otro"})
    changed = services.reclassify_documents(operator_user, procedure)
    assert [(d.file_name, before, after) for d, before, after in changed] == [
        ("sin-tipo.pdf", "", "tecnica")]
    kinds = dict(offer.documents.values_list("file_name", "kind"))
    assert kinds == {"sin-tipo.pdf": "tecnica", "con-tipo.pdf": "economica", "nada.pdf": "otro"}
    event = events(EventType.OFFER_READ, Outcome.OK).get(detail__action="reclassify")
    assert event.detail["kind_before"] == "" and event.detail["kind"] == "tecnica"
    assert services.reclassify_documents(operator_user, procedure) == []
    with pytest.raises(RoleRejected):
        services.reclassify_documents(None, procedure)


def test_the_maintenance_commands_reclassify_and_rebuild(
        read_document_of, procedure, operator_user, settings, monkeypatch, capsys):
    """REQ-039, REQ-044 (T-136): los dos comandos corren los servicios sobre el procedimiento."""
    from django.core.management import call_command

    monkeypatch.setattr("evaluon.accounts.permissions.authenticate_command",
                        lambda username: operator_user)
    call_command("reclasificar_documentos", usuario="operador",
                 procedimiento=procedure.number)
    assert "documentos cambiaron de tipo" in capsys.readouterr().out
    settings.OFFERS_PASSAGE_MAX_CHARS = 400
    call_command("rearmar_pasajes", usuario="operador", procedimiento=procedure.number)
    assert "1 documentos con lectura nueva" in capsys.readouterr().out
    assert read_document_of.readings.count() == 2
    call_command("rearmar_pasajes", usuario="operador", procedimiento=procedure.number)
    assert "sin cambios" in capsys.readouterr().out
