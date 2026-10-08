"""Alta del procedimiento desde el pliego subido (REQ-077; ADR-0049; T-196).

El pliego del caso chico es sintético (P4): lleva los cinco datos de la carátula y una tabla de
renglones. El modelo local es el doble de las pruebas: ninguna prueba usa la GPU.
"""

import json
from decimal import Decimal

import pytest

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.norms.models import ProposalState
from evaluon.portal.models import PortalLine, PortalProcedureData
from evaluon.tenders import jobs
from evaluon.tenders import models as m
from evaluon.tenders.services import procedure_proposal as service
from tests.tenders.pdfs import para, table, tender_pdf

pytestmark = pytest.mark.django_db

CASE_NUMBER = "SINT-0100-PRUEBA"
CASE_FILE = "EX-2099-00001234-SINT"


def case_pdf(*, number=CASE_NUMBER, rows=None, cover=None):
    """El pliego del caso chico: carátula con los cinco datos y la tabla de renglones."""
    cover = cover if cover is not None else [
        f"PROCESO Nº: {number}",
        f"EXPEDIENTE Nº: {CASE_FILE}",
        "Tipo de procedimiento: Licitación Pública",
        "NOMBRE DEL PROCESO: ADQUISICIÓN DE INSUMOS SINTÉTICOS DE PRUEBA",
        "Fecha de autorización: 15/03/2025",
    ]
    rows = rows if rows is not None else [
        ("1", "PRODUCTO SINTÉTICO A", "100 UNIDADES"),
        ("2", "PRODUCTO SINTÉTICO B", "1.500,50 KILOGRAMOS"),
        ("3", "PRODUCTO SINTÉTICO C", "7"),
    ]
    blocks = [para("PLIEGO DE BASES Y CONDICIONES PARTICULARES"), para(*cover),
              para("DETALLE DE LOS BIENES"),
              table(("RENGLÓN", "DESCRIPCIÓN", "CANTIDAD"), *rows)]
    return tender_pdf([blocks])


def upload_and_read(user, data, name="pliego.pdf"):
    draft = service.upload_tender(user, data, name)
    jobs.run_next(kinds=[m.JobKind.PROPOSE_PROCEDURE])
    draft.refresh_from_db()
    return draft


def approved(evaluator_user, draft_id, **kwargs):
    return service.approve(evaluator_user, draft_id, **kwargs)


# --- Subir y leer ---------------------------------------------------------------------------


def test_the_small_case_gives_five_of_five_data_and_all_lines(operator_user):
    """REQ-077: el pliego del caso chico: 5 de 5 datos con su cita y renglones completos."""
    draft = upload_and_read(operator_user, case_pdf())
    assert draft.state == ProposalState.PROPUESTO
    fields = draft.proposal["fields"]
    expected = {
        "number": CASE_NUMBER,
        "file_number": CASE_FILE,
        "procedure_type": "Licitación pública",
        "subject": "ADQUISICIÓN DE INSUMOS SINTÉTICOS DE PRUEBA",
        "authorization_date": "2025-03-15",
    }
    for name, value in expected.items():
        assert fields[name]["state"] == "propuesto", name
        assert fields[name]["proposed"] == value, name
        assert fields[name]["citation"]["page"] == 1
        assert fields[name]["citation"]["text"]
    lines = draft.proposal["lines"]
    assert [(x["number"], x["description"], x["quantity"], x["unit"]) for x in lines] == [
        (1, "PRODUCTO SINTÉTICO A", "100", "UNIDADES"),
        (2, "PRODUCTO SINTÉTICO B", "1500.5", "KILOGRAMOS"),
        (3, "PRODUCTO SINTÉTICO C", "7", ""),
    ]
    assert all(x["citation"]["page"] == 1 for x in lines)
    assert draft.job.status == m.JobStatus.DONE


def test_upload_queues_a_propose_procedure_job_without_procedure(operator_user):
    """REQ-077: subir deja el borrador «leyendo» y el pedido en espera, sin procedimiento."""
    draft = service.upload_tender(operator_user, case_pdf(), "pliego.pdf")
    assert draft.state == ProposalState.LEYENDO
    assert draft.job.kind == m.JobKind.PROPOSE_PROCEDURE
    assert draft.job.procedure is None and draft.job.target_id == draft.pk
    assert draft.job.status == m.JobStatus.QUEUED
    assert not m.Procedure.objects.exists()


def test_the_handler_is_registered_in_the_queue():
    """REQ-077: el pedido tiene su manejador en `jobs.HANDLERS`, por su ruta."""
    assert jobs.HANDLERS[m.JobKind.PROPOSE_PROCEDURE] == (
        "evaluon.tenders.services.procedure_proposal.run_propose_procedure")


def test_a_datum_without_citation_stays_undetermined(operator_user, fake_generation):
    """REQ-077: lo que no se encuentra queda «no determinado» y no se propone."""
    cover = ["PROCESO Nº: SINT-0200-PRUEBA", "NOMBRE DEL PROCESO: COMPRA SINTÉTICA"]
    draft = upload_and_read(operator_user, case_pdf(cover=cover))
    fields = draft.proposal["fields"]
    for name in ("file_number", "procedure_type", "authorization_date"):
        assert fields[name]["state"] == "no_determinado"
        assert fields[name]["proposed"] is None and fields[name]["citation"] is None
    assert fields["number"]["proposed"] == "SINT-0200-PRUEBA"


def test_a_pliego_without_recognizable_data_proposes_nothing(operator_user, fake_generation):
    """REQ-077: un pliego sin datos reconocibles queda con todo «no determinado»."""
    data = tender_pdf([[para("Texto libre sin datos del proceso.")]])
    draft = upload_and_read(operator_user, data)
    assert draft.state == ProposalState.PROPUESTO
    assert {f["state"] for f in draft.proposal["fields"].values()} == {"no_determinado"}
    assert draft.proposal["lines"] == []


def test_the_model_fills_only_what_rules_miss_and_its_quote_is_verified(
        operator_user, fake_generation):
    """REQ-077: el modelo entra solo para lo que las reglas no hallan, y su cita se verifica."""
    cover = ["PROCESO Nº: SINT-0300-PRUEBA", "Se convoca a la contratación directa de bienes."]
    fake_generation.respond(json.dumps({
        "procedure_type": {"valor": "", "cita": ""},
        "subject": {"valor": "bienes inventados", "cita": "texto que no está en el pliego"},
    }))
    draft = upload_and_read(operator_user, case_pdf(cover=cover))
    fields = draft.proposal["fields"]
    assert fields["procedure_type"]["method"] == "regla"
    assert fields["subject"]["state"] == "no_determinado"
    assert len(fake_generation.calls) == 1
    event = AuditEvent.objects.filter(event_type=EventType.PROCEDURE_PROPOSAL,
                                      detail__action="propose").get()
    trace = event.detail["model"][0]
    assert trace["asked"] == ["subject"] and trace["prompt_version"]
    assert trace["instructions_sha256"] and trace["output"]


def test_the_model_answer_with_a_literal_quote_is_proposed(operator_user, fake_generation):
    """REQ-077: una cita literal que contiene el valor se propone, marcada como del modelo."""
    cover = ["PROCESO Nº: SINT-0301-PRUEBA", "Contratación para el mantenimiento de equipos."]
    fake_generation.respond(json.dumps({
        "procedure_type": {"valor": "", "cita": ""},
        "subject": {"valor": "mantenimiento de equipos",
                    "cita": "Contratación para el mantenimiento de equipos."},
    }))
    draft = upload_and_read(operator_user, case_pdf(cover=cover))
    subject = draft.proposal["fields"]["subject"]
    assert subject["proposed"] == "mantenimiento de equipos" and subject["method"] == "modelo"
    assert subject["citation"]["page"] == 1
    assert draft.proposal["fields"]["procedure_type"]["state"] == "no_determinado"


def test_a_model_failure_does_not_fail_the_proposal(operator_user, fake_generation):
    """REQ-077: una falla del modelo deja los datos sin determinar, no el pedido fallido."""
    fake_generation.unavailable()
    draft = upload_and_read(operator_user, case_pdf(cover=["PROCESO Nº: SINT-0302-PRUEBA"]))
    assert draft.state == ProposalState.PROPUESTO
    assert draft.proposal["fields"]["subject"]["state"] == "no_determinado"


def test_an_html_pliego_is_read_and_has_no_lines(operator_user, fake_generation):
    """REQ-077: una página web guardada se lee; sin tabla de renglones no hay renglones."""
    html = ("<html><body><p>PROCESO Nº: SINT-0400-PRUEBA</p>"
            "<p>Tipo de procedimiento: Contratación Directa</p></body></html>").encode()
    draft = upload_and_read(operator_user, html, "pliego.html")
    assert draft.state == ProposalState.PROPUESTO
    assert draft.proposal["fields"]["number"]["proposed"] == "SINT-0400-PRUEBA"
    assert draft.proposal["lines"] == []


def test_a_repeated_line_number_keeps_the_first_and_warns(operator_user):
    """REQ-077: un renglón repetido no rompe el alta: se toma el primero y queda el aviso."""
    rows = [("1", "PRODUCTO A", "5"), ("1", "PRODUCTO REPETIDO", "9")]
    draft = upload_and_read(operator_user, case_pdf(rows=rows))
    assert [x["description"] for x in draft.proposal["lines"]] == ["PRODUCTO A"]
    assert draft.proposal["warnings"]


def test_a_damaged_pdf_leaves_the_draft_failed_and_the_job_failed(operator_user):
    """REQ-077: si la lectura falla, el borrador queda «fallido» con su motivo y el hecho."""
    draft = upload_and_read(operator_user, b"%PDF-1.4\nesto no es un pdf de verdad")
    assert draft.state == ProposalState.FALLIDO and draft.failure
    assert draft.job.status == m.JobStatus.FAILED
    assert AuditEvent.objects.filter(event_type=EventType.PROCEDURE_PROPOSAL,
                                     outcome=Outcome.FAILED).exists()


def test_unsupported_and_empty_files_are_rejected_with_their_event(operator_user):
    """REQ-077: un archivo vacío o de otro formato se rechaza y deja el hecho rechazado."""
    for data in (b"", b"no es un pliego"):
        with pytest.raises(service.ProposalRefused):
            service.upload_tender(operator_user, data, "x.txt")
    assert not m.ProcedureDraft.objects.exists()
    assert AuditEvent.objects.filter(event_type=EventType.PROCEDURE_PROPOSAL,
                                     outcome=Outcome.REJECTED).count() == 2


def test_the_same_file_twice_is_rejected(operator_user):
    """REQ-077: el mismo pliego (misma huella) en dos borradores pendientes se rechaza."""
    data = case_pdf()
    service.upload_tender(operator_user, data, "a.pdf")
    with pytest.raises(service.DuplicateTender):
        service.upload_tender(operator_user, data, "b.pdf")
    assert m.ProcedureDraft.objects.count() == 1


# --- Roles ----------------------------------------------------------------------------------


def test_only_the_evaluator_corrects_and_approves(operator_user, no_commission_user):
    """REQ-077: el operador sube y ve; corregir y aprobar solo el evaluador; sin rol, nada."""
    draft = upload_and_read(operator_user, case_pdf())
    assert service.proposal_of(operator_user, draft.pk).pk == draft.pk
    with pytest.raises(RoleRejected):
        service.correct(operator_user, draft.pk, "number", "X-1", "motivo")
    with pytest.raises(RoleRejected):
        service.approve(operator_user, draft.pk)
    with pytest.raises(RoleRejected):
        service.upload_tender(no_commission_user, case_pdf(number="SINT-0500"), "x.pdf")
    with pytest.raises(RoleRejected):
        service.proposal_of(no_commission_user, draft.pk)
    draft.refresh_from_db()
    assert draft.state == ProposalState.PROPUESTO and not draft.proposal["corrections"]
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).count() == 4


# --- Corregir -------------------------------------------------------------------------------


def test_a_correction_needs_a_reason(operator_user, evaluator_user):
    """REQ-077: sin motivo no hay corrección; el hecho rechazado lo registra."""
    draft = upload_and_read(operator_user, case_pdf())
    for reason in ("", "   ", None):
        with pytest.raises(service.ReasonRequired):
            service.correct(evaluator_user, draft.pk, "subject", "Otro objeto", reason)
    draft.refresh_from_db()
    assert draft.proposal["corrections"] == []
    assert AuditEvent.objects.filter(event_type=EventType.PROCEDURE_PROPOSAL,
                                     outcome=Outcome.REJECTED,
                                     detail__reason="missing_reason").count() == 3


def test_a_correction_keeps_the_proposed_value_with_who_and_when(operator_user,
                                                                 evaluator_user):
    """REQ-077: «Escribe el valor y motivo»: queda propuesto, corregido, motivo, quién y cuándo."""
    draft = upload_and_read(operator_user, case_pdf())
    service.correct(evaluator_user, draft.pk, "subject", "Insumos corregidos", "El objeto es otro")
    service.correct(evaluator_user, draft.pk, "line.2.quantity", "1600,5", "Error de lectura")
    service.correct(evaluator_user, draft.pk, "authorization_date", "16/03/2025", "Fecha real")
    draft.refresh_from_db()
    first, second, third = draft.proposal["corrections"]
    assert first["proposed"] == "ADQUISICIÓN DE INSUMOS SINTÉTICOS DE PRUEBA"
    assert first["corrected"] == "Insumos corregidos" and first["reason"] == "El objeto es otro"
    assert first["by"] == evaluator_user.get_username() and first["by_id"] == evaluator_user.pk
    assert first["at"]
    assert second["field"] == "line.2.quantity" and second["proposed"] == "1500.5"
    assert second["corrected"] == "1600.5"
    assert third["corrected"] == "2025-03-16"
    # Lo propuesto no se toca.
    assert draft.proposal["fields"]["subject"]["proposed"].startswith("ADQUISICIÓN")
    assert AuditEvent.objects.filter(event_type=EventType.PROCEDURE_PROPOSAL,
                                     detail__action="correct", outcome=Outcome.OK).count() == 3


def test_a_correction_refuses_unknown_fields_bad_values_and_resolved_drafts(
        operator_user, evaluator_user):
    """REQ-077: no hay alta en blanco: solo se corrige lo que la propuesta tiene."""
    draft = upload_and_read(operator_user, case_pdf())
    cases = [("line.9.description", "x"), ("nope", "x"), ("authorization_date", "no es fecha"),
             ("authorization_date", "01/01/2999"), ("line.1.quantity", "mucho"),
             ("line.1.quantity", "0"), ("subject", "  ")]
    for field, value in cases:
        with pytest.raises(service.ProposalRefused):
            service.correct(evaluator_user, draft.pk, field, value, "motivo")
    approved(evaluator_user, draft.pk)
    with pytest.raises(service.NotPending):
        service.correct(evaluator_user, draft.pk, "subject", "x", "motivo")


# --- Aprobar --------------------------------------------------------------------------------


def test_approve_creates_the_procedure_the_pliego_and_the_lines_together(
        operator_user, evaluator_user):
    """REQ-077: aprobar crea procedimiento, pliego, renglones y expediente con su origen."""
    draft = upload_and_read(operator_user, case_pdf())
    service.correct(evaluator_user, draft.pk, "line.1.description", "PRODUCTO A CORREGIDO",
                    "Descripción incompleta")
    done = approved(evaluator_user, draft.pk)
    assert done.state == ProposalState.APROBADO
    procedure = done.procedure
    assert procedure.number == CASE_NUMBER and procedure.created_by == evaluator_user
    assert procedure.procedure_type == "Licitación pública"
    assert str(procedure.authorization_date) == "2025-03-15"
    document = procedure.documents.get()
    assert document.kind == m.DocumentKind.PLIEGO and document.file_sha256 == draft.file_sha256
    assert bytes(m.DocumentFile.objects.get(document=document).content) == bytes(draft.content)
    assert m.Job.objects.filter(kind=m.JobKind.READ_DOCUMENT, document=document).exists()
    lines = list(PortalLine.objects.filter(procedure=procedure))
    assert [(x.number, x.description, x.quantity, x.unit) for x in lines] == [
        (1, "PRODUCTO A CORREGIDO", Decimal("100"), "UNIDADES"),
        (2, "PRODUCTO SINTÉTICO B", Decimal("1500.5"), "KILOGRAMOS"),
        (3, "PRODUCTO SINTÉTICO C", Decimal("7"), ""),
    ]
    assert all(x.document == document and x.item is None for x in lines)
    data = PortalProcedureData.objects.get(procedure=procedure)
    assert data.file_number == CASE_FILE and data.document == document and data.item is None
    event = AuditEvent.objects.filter(event_type=EventType.PROCEDURE_PROPOSAL,
                                      detail__action="approve").get()
    assert event.user == evaluator_user and event.detail["procedure"] == procedure.pk
    assert event.detail["corrections"][0]["reason"] == "Descripción incompleta"
    assert event.detail["values"]["number"] == CASE_NUMBER


def test_approve_can_discard_lines(operator_user, evaluator_user):
    """REQ-077: el evaluador descarta un renglón propuesto; no queda en el procedimiento."""
    draft = upload_and_read(operator_user, case_pdf())
    with pytest.raises(service.ProposalRefused):
        service.approve(evaluator_user, draft.pk, {"discard_lines": [9]})
    done = approved(evaluator_user, draft.pk, decisions={"discard_lines": [2]})
    assert list(PortalLine.objects.filter(procedure=done.procedure)
                .values_list("number", flat=True)) == [1, 3]


def test_approve_without_a_required_datum_creates_nothing(operator_user, evaluator_user,
                                                          fake_generation):
    """REQ-077: sin los cuatro datos el procedimiento no existe; se corrige con motivo y se
    aprueba."""
    cover = ["PROCESO Nº: SINT-0600-PRUEBA", "Fecha de autorización: 01/02/2025"]
    draft = upload_and_read(operator_user, case_pdf(cover=cover))
    with pytest.raises(service.IncompleteProposal):
        service.approve(evaluator_user, draft.pk)
    assert not m.Procedure.objects.exists()
    draft.refresh_from_db()
    assert draft.state == ProposalState.PROPUESTO and draft.procedure is None
    service.correct(evaluator_user, draft.pk, "procedure_type", "Contratación directa",
                    "Figura en el cuerpo del pliego")
    service.correct(evaluator_user, draft.pk, "subject", "Compra sintética", "Objeto del pliego")
    done = approved(evaluator_user, draft.pk)
    assert done.procedure.subject == "Compra sintética"
    correction = [c for c in done.proposal["corrections"] if c["field"] == "subject"][0]
    assert correction["proposed"] is None and correction["reason"] == "Objeto del pliego"


def test_a_duplicate_number_is_rejected_and_nothing_is_left_half_made(operator_user,
                                                                       evaluator_user):
    """REQ-077: un número ya registrado se rechaza; el borrador queda y no queda nada a medias."""
    first = upload_and_read(operator_user, case_pdf())
    approved(evaluator_user, first.pk)
    other = upload_and_read(operator_user, case_pdf(rows=[("1", "OTRO PRODUCTO", "3")]),
                            "otro.pdf")
    before = (m.Procedure.objects.count(), m.Document.objects.count(), PortalLine.objects.count())
    with pytest.raises(service.ProposalRefused) as caught:
        service.approve(evaluator_user, other.pk)
    assert caught.value.field == "number"
    assert (m.Procedure.objects.count(), m.Document.objects.count(),
            PortalLine.objects.count()) == before
    other.refresh_from_db()
    assert other.state == ProposalState.PROPUESTO and other.procedure is None
    service.correct(evaluator_user, other.pk, "number", "SINT-0101-PRUEBA", "Número del acto")
    assert approved(evaluator_user, other.pk).procedure.number == "SINT-0101-PRUEBA"


def test_the_same_pliego_cannot_be_uploaded_after_it_was_approved(operator_user,
                                                                  evaluator_user):
    """REQ-077: dedupe por huella: un pliego ya cargado en un procedimiento no se sube de nuevo."""
    data = case_pdf()
    draft = upload_and_read(operator_user, data)
    approved(evaluator_user, draft.pk)
    with pytest.raises(service.DuplicateTender):
        service.upload_tender(operator_user, data, "de-nuevo.pdf")


def test_an_approved_draft_cannot_be_approved_twice(operator_user, evaluator_user):
    """REQ-077: aprobar dos veces no crea dos procedimientos."""
    draft = upload_and_read(operator_user, case_pdf())
    approved(evaluator_user, draft.pk)
    with pytest.raises(service.NotPending):
        service.approve(evaluator_user, draft.pk)
    assert m.Procedure.objects.count() == 1


def test_approve_does_not_leave_a_procedure_if_loading_the_pliego_fails(
        operator_user, evaluator_user, monkeypatch):
    """REQ-077: el procedimiento y su borrador aprobado se escriben juntos o ninguno."""
    draft = upload_and_read(operator_user, case_pdf())

    def boom(*args, **kwargs):
        raise RuntimeError("falla simulada al cargar el pliego")

    monkeypatch.setattr(service.documents, "load_document", boom)
    with pytest.raises(RuntimeError):
        service.approve(evaluator_user, draft.pk)
    draft.refresh_from_db()
    assert not m.Procedure.objects.exists()
    assert draft.state == ProposalState.PROPUESTO and draft.procedure is None
