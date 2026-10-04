"""Cargar los documentos del pliego y leerlos en segundo plano (REQ-023, REQ-028,
REQ-031; plan 003, "Carga y lectura", "Procedimiento y documentos", "Roles" y "Registro
de auditoría"; T-072).

Los pliegos son sintéticos (`tests/tenders/pdfs.py`); la página de ruido es la de la 001
(`tests/fixtures/pagina-ruido.pdf`, celdas blancas y negras al azar). No hay datos de
personas (P4). La lectura se ejecuta con `jobs.run_next()` sobre la base de pruebas,
como la haría el `worker`.
"""

import hashlib
import html
import io
import itertools
from datetime import date
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.norms.reading import read_document
from evaluon.tenders import jobs
from evaluon.tenders import models as m
from evaluon.tenders.segmenting import RULES_VERSION, split_tender
from evaluon.tenders.services import documents
from evaluon.tenders.tables import table_zones
from tests.conftest import TEST_PASSWORD
from tests.tenders.pdfs import para, synthetic_tender_pdf, tender_pdf

pytestmark = pytest.mark.django_db

REPO = Path(__file__).resolve().parents[2]
NOISE = REPO / "tests" / "fixtures" / "pagina-ruido.pdf"

_counter = itertools.count(1)


# --- Pliegos sintéticos ------------------------------------------------------------------


def annex_pdf():
    return tender_pdf([
        [
            para("ANEXO I - PLANILLA SINTÉTICA DE COTIZACIÓN"),
            para("El oferente completa la planilla sintética con sus precios."),
        ],
        [para("Fecha: ________/_________/_________")],
    ])


def circular_pdf():
    return tender_pdf([
        [
            para("CIRCULAR MODIFICATORIA N° 1"),
            para("1. Se modifica la cláusula 1.1 del pliego sintético."),
        ],
    ], header=None)


TEXT_PAGES = [
    [
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("1. OBJETO", "1.1. El objeto es la adquisición de insumos sintéticos."),
    ],
    [
        para("2. GARANTÍA", "2.1. La oferta deberá acompañar una garantía sintética."),
    ],
    [
        para("3. ENTREGA", "3.1. Los bienes se entregan en el depósito sintético."),
    ],
]
NOISE_PAGE = 2


def noisy_pdf():
    """Tres páginas con texto y la de ruido insertada como página 2."""
    text = pdfium.PdfDocument(tender_pdf(TEXT_PAGES))
    pdf = pdfium.PdfDocument.new()
    pdf.import_pages(text, pages=[0])
    pdf.import_pages(pdfium.PdfDocument(NOISE), pages=[0])
    pdf.import_pages(text, pages=[1, 2])
    buffer = io.BytesIO()
    pdf.save(buffer)
    return buffer.getvalue()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


# --- Ayudas --------------------------------------------------------------------------------


@pytest.fixture
def procedure(operator_user):
    return m.Procedure.objects.create(
        number=f"SINT-DOC-{next(_counter)}",
        procedure_type="Licitación pública",
        subject="Adquisición sintética de insumos de prueba",
        authorization_date=date(2025, 11, 14),
        created_by=operator_user,
    )


def load(user, procedure, data, *, kind=m.DocumentKind.PLIEGO, title="Pliego sintético",
         issued_on=None, file_name="pliego-sintetico.pdf"):
    return documents.load_document(
        user, procedure, data=data, file_name=file_name, kind=kind, title=title,
        issued_on=issued_on,
    )


def load_events(outcome=None):
    events = AuditEvent.objects.filter(event_type=EventType.TENDER_LOAD)
    if outcome is not None:
        events = events.filter(outcome=outcome)
    return events.order_by("id")


def read_all():
    """Ejecuta los pedidos en espera, de a uno, como el `worker`."""
    done = []
    while (job := jobs.run_next()) is not None:
        job.refresh_from_db()
        done.append(job)
    return done


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def page_text(response):
    return html.unescape(response.content.decode())


def upload(client, procedure, data, *, kind="pliego", title="Pliego sintético",
           issued_on="", file_name="pliego-sintetico.pdf"):
    return client.post(
        reverse("tenders:procedure", args=[procedure.pk]),
        {
            "file": SimpleUploadedFile(file_name, data, content_type="application/pdf"),
            "kind": kind,
            "title": title,
            "issued_on": issued_on,
        },
    )


# --- Carga (REQ-023, REQ-031) --------------------------------------------------------------


def test_load_keeps_the_original_and_queues_its_reading(operator_user, procedure):
    """REQ-023: cargar un documento guarda el original byte por byte, con su huella,
    formato y tamaño, y deja su lectura en espera; el hecho `tender_load` registra
    procedimiento, tipo, título, fecha, nombre, formato, tamaño y huella."""
    data = synthetic_tender_pdf()
    loaded = load(operator_user, procedure, data)

    document = loaded.document
    assert bytes(document.file.content) == data
    assert document.file_sha256 == sha256(data)
    assert document.file_size == len(data)
    assert document.file_format == "pdf"
    assert document.loaded_by == operator_user
    assert loaded.job.kind == m.JobKind.READ_DOCUMENT
    assert loaded.job.status == m.JobStatus.QUEUED
    assert loaded.job.document == document
    assert loaded.job.requested_by == operator_user

    event = load_events(Outcome.OK).get()
    assert event.user == operator_user
    assert event.detail["procedure"] == procedure.pk
    assert event.detail["document"] == document.pk
    assert event.detail["job"] == loaded.job.pk
    assert event.detail["kind"] == "pliego"
    assert event.detail["title"] == "Pliego sintético"
    assert event.detail["issued_on"] is None
    assert event.detail["file"] == {
        "name": "pliego-sintetico.pdf", "format": "pdf", "size": len(data),
        "sha256": sha256(data),
    }


def test_three_documents_and_each_original_comes_back_unchanged(client, operator_user,
                                                                procedure):
    """REQ-023: un pliego en tres documentos cargados por pantalla; la huella de lo que
    entrega la vista del original es igual a la de cada archivo cargado."""
    files = [
        ("pliego", "Pliego de bases y condiciones particulares", "", "pliego.pdf",
         synthetic_tender_pdf()),
        ("anexo", "Anexo I", "", "anexo.pdf", annex_pdf()),
        ("circular_modificatoria", "Circular N.º 1", "2025-11-20", "circular.pdf",
         circular_pdf()),
    ]
    log_in(client, operator_user)
    for kind, title, issued_on, file_name, data in files:
        response = upload(client, procedure, data, kind=kind, title=title,
                          issued_on=issued_on, file_name=file_name)
        assert response.status_code == 302

    loaded = list(procedure.documents.order_by("id"))
    assert [d.file_name for d in loaded] == ["pliego.pdf", "anexo.pdf", "circular.pdf"]
    assert loaded[2].issued_on == date(2025, 11, 20)
    for document, (*_, data) in zip(loaded, files):
        response = client.get(reverse("tenders:document_original", args=[document.pk]))
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert sha256(response.content) == sha256(data) == document.file_sha256


def test_same_file_twice_is_refused_and_recorded(operator_user, evaluator_user, procedure):
    """REQ-023: el mismo archivo dos veces en un procedimiento se rechaza con aviso, no
    guarda nada y queda registrado como carga rechazada, con la huella."""
    data = annex_pdf()
    first = load(operator_user, procedure, data, kind=m.DocumentKind.ANEXO, title="Anexo")

    with pytest.raises(documents.DuplicateFile) as refused:
        load(evaluator_user, procedure, data, kind=m.DocumentKind.ANEXO,
             title="Anexo repetido", file_name="otro-nombre.pdf")
    assert "ya está cargado" in str(refused.value)
    assert procedure.documents.count() == 1
    assert m.Job.objects.count() == 1

    rejected = load_events(Outcome.REJECTED).get()
    assert rejected.user == evaluator_user
    assert rejected.detail["reason"] == "duplicate_file"
    assert rejected.detail["procedure"] == procedure.pk
    assert rejected.detail["file"]["sha256"] == sha256(data)
    assert rejected.detail["loaded_document"] == first.document.pk


def test_same_file_in_another_procedure_is_accepted(operator_user, procedure):
    """REQ-023: la huella es única dentro del procedimiento; otro procedimiento puede
    cargar el mismo archivo."""
    data = annex_pdf()
    other = m.Procedure.objects.create(
        number=f"SINT-DOC-{next(_counter)}", procedure_type="Contratación directa",
        subject="Otro objeto sintético", authorization_date=date(2025, 11, 14),
        created_by=operator_user,
    )
    load(operator_user, procedure, data)
    load(operator_user, other, data)
    assert m.Document.objects.filter(file_sha256=sha256(data)).count() == 2


@pytest.mark.parametrize("kind", [
    m.DocumentKind.CIRCULAR_MODIFICATORIA,
    m.DocumentKind.CIRCULAR_ACLARATORIA,
    m.DocumentKind.RESPUESTA_CONSULTA,
])
def test_circular_or_answer_without_date_is_refused(operator_user, procedure, kind):
    """REQ-031: una circular o una respuesta a consulta sin fecha se rechaza, no guarda
    nada y queda registrada."""
    with pytest.raises(documents.DocumentRefused) as refused:
        load(operator_user, procedure, circular_pdf(), kind=kind, title="Circular")
    assert refused.value.field == "issued_on"
    assert procedure.documents.count() == 0
    assert m.Job.objects.count() == 0
    rejected = load_events(Outcome.REJECTED).get()
    assert rejected.detail["reason"] == "missing_date"
    assert rejected.detail["kind"] == kind


def test_circular_with_date_keeps_it(operator_user, procedure):
    """REQ-031: una circular con fecha se carga con su fecha."""
    loaded = load(operator_user, procedure, circular_pdf(),
                  kind=m.DocumentKind.CIRCULAR_ACLARATORIA, title="Circular N.º 2",
                  issued_on=date(2025, 11, 21))
    assert loaded.document.issued_on == date(2025, 11, 21)
    assert load_events(Outcome.OK).get().detail["issued_on"] == "2025-11-21"


def test_pliego_may_have_a_date(operator_user, procedure):
    """REQ-031: la fecha es optativa en los documentos que no son circulares ni
    respuestas."""
    loaded = load(operator_user, procedure, annex_pdf(), kind=m.DocumentKind.ANEXO,
                  title="Anexo", issued_on=date(2025, 11, 1))
    assert loaded.document.issued_on == date(2025, 11, 1)


@pytest.mark.parametrize("field, values", [
    ("title", {"title": "  "}),
    ("kind", {"kind": "otro"}),
    ("file", {"data": b""}),
    ("file", {"file_name": ""}),
])
def test_missing_or_invalid_data_is_refused(operator_user, procedure, field, values):
    """REQ-023: sin título, con un tipo que no existe o sin archivo, no se carga nada y
    el rechazo queda registrado."""
    arguments = {"data": annex_pdf(), "kind": m.DocumentKind.ANEXO, "title": "Anexo",
                 "file_name": "anexo.pdf", **values}
    with pytest.raises(documents.DocumentRefused) as refused:
        documents.load_document(operator_user, procedure, **arguments)
    assert refused.value.field == field
    assert procedure.documents.count() == 0
    assert load_events(Outcome.REJECTED).count() == 1


def test_file_that_is_not_pdf_or_web_page_is_refused(operator_user, procedure):
    """REQ-023: un archivo que no es PDF ni página web guardada se rechaza al cargarlo."""
    with pytest.raises(documents.DocumentRefused) as refused:
        load(operator_user, procedure, b"texto plano sintetico", file_name="nota.txt")
    assert refused.value.field == "file"
    assert procedure.documents.count() == 0
    assert load_events(Outcome.REJECTED).get().detail["reason"] == "unsupported_format"


def test_user_without_commission_role_cannot_load_or_open(no_commission_user,
                                                          operator_user, procedure):
    """REQ-023: sin rol de la Comisión no se carga ni se abre un original; el rechazo
    queda registrado como `rejected`."""
    with pytest.raises(RoleRejected):
        load(no_commission_user, procedure, annex_pdf())
    loaded = load(operator_user, procedure, annex_pdf())
    with pytest.raises(RoleRejected):
        documents.original_file(no_commission_user, loaded.document.pk)
    rejected = AuditEvent.objects.filter(event_type=EventType.REJECTED)
    assert [e.detail["operation"] for e in rejected.order_by("id")] == [
        documents.LOAD_OPERATION, documents.ORIGINAL_OPERATION,
    ]
    assert procedure.documents.count() == 1


def test_evaluator_can_load(evaluator_user, procedure):
    """REQ-023: el evaluador también carga documentos."""
    assert load(evaluator_user, procedure, annex_pdf()).document.loaded_by == evaluator_user


# --- Lectura en segundo plano (REQ-023, REQ-028) ------------------------------------------


def test_reading_saves_reading_segments_and_report(operator_user, procedure):
    """REQ-028: el pedido de lectura lee con la lectura de la 001, busca las zonas de
    tabla y parte en tramos; guarda la lectura (con las versiones de las herramientas y
    de las reglas de tramos), los tramos con su texto literal y el informe, y deja el
    hecho `tender_read`. El pedido queda `done`."""
    data = synthetic_tender_pdf()
    loaded = load(operator_user, procedure, data)
    [job] = read_all()
    assert job.status == m.JobStatus.DONE, job.error

    expected = split_tender(read_document(data), table_zones(data))
    reading = loaded.document.readings.get()
    assert reading.sequence == 1
    assert reading.job == job
    assert reading.canonical_text == expected.canonical.text
    assert reading.canonical_sha256 == sha256(expected.canonical.text.encode("utf-8"))
    assert reading.tables == table_zones(data)
    assert reading.tool_versions["rules_version"] == RULES_VERSION
    assert reading.pages["file_format"] == "pdf"
    assert reading.items == expected.items

    segments = list(reading.segments.order_by("order"))
    assert [s.key for s in segments] == [s.key for s in expected.segments]
    for segment in segments:
        assert segment.text == reading.canonical_text[segment.char_start:segment.char_end]

    event = AuditEvent.objects.get(event_type=EventType.TENDER_READ)
    assert event.outcome == Outcome.OK
    assert event.user == operator_user
    assert event.detail["document"] == loaded.document.pk
    assert event.detail["reading"] == reading.pk
    assert event.detail["job"] == job.pk
    assert event.detail["tool_versions"] == reading.tool_versions
    assert event.detail["segments_by_type"] == reading.report["segments_by_type"]
    assert event.detail["items"] == reading.items
    assert event.detail["coverage"]["matches"] is True


def test_report_counts_segments_by_type_and_lists_the_items(operator_user, procedure):
    """REQ-028: el informe de la lectura cuenta los tramos por tipo y lista los
    renglones reconocidos, cada uno con la clave del tramo de su encabezado."""
    loaded = load(operator_user, procedure, synthetic_tender_pdf())
    read_all()
    reading = loaded.document.readings.get()
    report = reading.report

    counted = {}
    for segment in reading.segments.all():
        counted[segment.segment_type] = counted.get(segment.segment_type, 0) + 1
    by_type = {kind: n for kind, n in report["segments_by_type"].items() if n}
    assert by_type == counted
    assert report["segments"] == reading.segments.count()
    assert [item["number"] for item in report["items"]] == [1, 2, 3, 4]
    assert report["items"] == reading.items
    for item in report["items"]:
        assert reading.segments.filter(key=item["key"]).exists()


def test_noise_page_is_the_only_page_pending_review(operator_user, procedure):
    """REQ-028: un PDF con una página de ruido deja esa página como tramo `pagina`
    pendiente de revisión (`pagina_ilegible`), y ninguna otra."""
    loaded = load(operator_user, procedure, noisy_pdf())
    [job] = read_all()
    assert job.status == m.JobStatus.DONE, job.error
    reading = loaded.document.readings.get()

    pending = reading.segments.exclude(review_reason="")
    assert [(s.key, s.segment_type, s.review_reason, s.page_start) for s in pending] == [
        (f"pagina-{NOISE_PAGE}", "pagina", "pagina_ilegible", NOISE_PAGE)
    ]
    assert reading.report["pending"] == [
        {"key": f"pagina-{NOISE_PAGE}", "reason": "pagina_ilegible", "detail": ""}
    ]
    assert reading.report["pages_by_status"] == {"legible": 3, "ilegible": 1}


def test_damaged_pdf_fails_the_job_and_saves_no_reading(operator_user, procedure):
    """REQ-028: un PDF dañado deja el pedido `failed` con el motivo, ninguna lectura a
    medias, y el hecho `tender_read` con resultado fallido."""
    damaged = synthetic_tender_pdf()[:400]
    loaded = load(operator_user, procedure, damaged)
    [job] = read_all()
    assert job.status == m.JobStatus.FAILED
    assert "dañado" in job.error
    assert not loaded.document.readings.exists()
    assert not m.Segment.objects.exists()
    event = AuditEvent.objects.get(event_type=EventType.TENDER_READ)
    assert event.outcome == Outcome.FAILED
    assert event.detail["document"] == loaded.document.pk
    assert event.detail["job"] == job.pk
    assert "dañado" in event.detail["error"]


def test_changed_original_is_not_read(operator_user, procedure):
    """REQ-023: si el original guardado ya no tiene su huella, no se lee y el pedido
    falla con el motivo."""
    loaded = load(operator_user, procedure, annex_pdf())
    m.DocumentFile.objects.filter(document=loaded.document).update(content=b"%PDF-otro")
    [job] = read_all()
    assert job.status == m.JobStatus.FAILED
    assert "huella" in job.error
    assert not loaded.document.readings.exists()


def test_read_document_handler_is_registered():
    """REQ-023: el tipo de pedido `read_document` tiene su manejador en la cola."""
    assert jobs.HANDLERS[m.JobKind.READ_DOCUMENT] == (
        "evaluon.tenders.services.documents.run_read_document"
    )


# --- Pantalla ----------------------------------------------------------------------------


def test_page_shows_each_document_with_its_reading_state(client, operator_user, procedure):
    """REQ-023, REQ-028: la página del procedimiento muestra cada documento con su tipo,
    su fecha, el estado de la lectura y el enlace al original; leído, sus pendientes de
    revisión (página ilegible)."""
    log_in(client, operator_user)
    upload(client, procedure, noisy_pdf(), title="Pliego con ruido")
    upload(client, procedure, circular_pdf(), kind="circular_aclaratoria",
           title="Circular N.º 1", issued_on="2025-11-20", file_name="circular.pdf")
    url = reverse("tenders:procedure", args=[procedure.pk])

    page = page_text(client.get(url))
    assert procedure.number in page
    assert "Pliego con ruido" in page and "Circular N.º 1" in page
    assert "Circular aclaratoria" in page and "20/11/2025" in page
    assert page.count("En espera de lectura") == 2
    for document in procedure.documents.all():
        assert reverse("tenders:document_original", args=[document.pk]) in page

    read_all()
    page = page_text(client.get(url))
    assert "En espera de lectura" not in page
    assert page.count("Leído") == 2
    assert "Pendiente de revisión" in page
    assert f"Página {NOISE_PAGE}" in page
    assert "Página ilegible" in page


def test_procedure_list_links_each_procedure_to_its_page(client, operator_user,
                                                         procedure):
    """REQ-023: la lista de procedimientos enlaza cada uno a su página, donde se cargan
    sus documentos."""
    log_in(client, operator_user)
    page = page_text(client.get(reverse("tenders:procedures")))
    link = reverse("tenders:procedure", args=[procedure.pk])
    assert f'<a href="{link}">{procedure.number}</a>' in page


def test_page_shows_a_failed_reading(client, operator_user, procedure):
    """REQ-028: una lectura fallida figura en la página con su motivo."""
    log_in(client, operator_user)
    upload(client, procedure, synthetic_tender_pdf()[:400], title="Pliego dañado")
    read_all()
    page = page_text(client.get(reverse("tenders:procedure", args=[procedure.pk])))
    assert "No se pudo leer" in page
    assert "dañado" in page


def test_screen_refuses_a_circular_without_date(client, operator_user, procedure):
    """REQ-031: por pantalla, una circular sin fecha vuelve al formulario marcado y no
    carga nada."""
    log_in(client, operator_user)
    response = upload(client, procedure, circular_pdf(), kind="circular_modificatoria",
                      title="Circular N.º 1")
    assert response.status_code == 200
    assert "fecha" in page_text(response)
    assert procedure.documents.count() == 0


def test_screen_refuses_the_same_file_twice(client, operator_user, procedure):
    """REQ-023: por pantalla, el mismo archivo dos veces vuelve con el aviso."""
    log_in(client, operator_user)
    data = annex_pdf()
    upload(client, procedure, data)
    response = upload(client, procedure, data, title="Otra vez")
    assert response.status_code == 200
    assert "ya está cargado" in page_text(response)
    assert procedure.documents.count() == 1


def test_screen_hidden_for_user_without_commission_role(client, no_commission_user,
                                                        operator_user, procedure):
    """REQ-023: sin rol de la Comisión, la página del procedimiento y el original dan
    "acceso denegado"."""
    loaded = load(operator_user, procedure, annex_pdf())
    log_in(client, no_commission_user)
    assert client.get(reverse("tenders:procedure", args=[procedure.pk])).status_code == 403
    original = reverse("tenders:document_original", args=[loaded.document.pk])
    assert client.get(original).status_code == 403


def test_original_requires_a_session(client, operator_user, procedure):
    """REQ-023: sin sesión, el original no se entrega: se redirige al ingreso."""
    loaded = load(operator_user, procedure, annex_pdf())
    response = client.get(reverse("tenders:document_original", args=[loaded.document.pk]))
    assert response.status_code == 302
    assert "ingresar" in response["Location"] or "login" in response["Location"]


def test_unknown_procedure_or_document_is_not_found(client, operator_user):
    """REQ-023: un procedimiento o un documento que no existe da "no encontrado"."""
    log_in(client, operator_user)
    assert client.get(reverse("tenders:procedure", args=[999999])).status_code == 404
    assert client.get(
        reverse("tenders:document_original", args=[999999])
    ).status_code == 404
