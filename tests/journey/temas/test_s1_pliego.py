"""Tema «alta subiendo el pliego» de la sección Procedimiento y del alta (REQ-077, REQ-076,
REQ-097; plan 014, T-197). Todo el material es inventado (P4) y no se usa el modelo real: la
generación es el doble de las pruebas (`fake_generation`)."""

import re

import pytest
from django.urls import get_resolver, reverse
from django.utils import timezone

from evaluon.audit.models import AuditEvent, EventType
from evaluon.journey.temas import s1_portal
from evaluon.norms.models import ProposalState
from evaluon.portal.models import PortalLine
from evaluon.tenders import jobs
from evaluon.tenders import models as m
from evaluon.tenders.services import procedure_proposal as service
from tests.accounts.test_session import TEST_PASSWORD
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.test_procedure_proposal import case_pdf, portal_style_pdf

pytestmark = pytest.mark.django_db

OLD_SCREENS = ("/importar/", "/recorrido/", "/procedimientos/")
MOCKUP_TEXTS = ("pliego-cd-99-2026", "99/2026", "EX-2026-00000099-DEMO", "Alimento balanceado")


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def upload(client, data, name="pliego.pdf"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return client.post(reverse("expedientes:s1_pliego_subir"),
                       {"file": SimpleUploadedFile(name, data, content_type="application/pdf")})


def read_it():
    job = jobs.run_next(kinds=[m.JobKind.PROPOSE_PROCEDURE])
    assert job is not None and job.status == m.JobStatus.DONE, job and job.error


def uploaded(client, user, data=None, name="pliego.pdf"):
    """Sube el pliego como `user` y devuelve el borrador, todavía sin leer."""
    log_in(client, user)
    response = upload(client, case_pdf() if data is None else data, name)
    assert response.status_code == 302, response.content
    return m.ProcedureDraft.objects.latest("pk")


def proposed(client, user, data=None, name="pliego.pdf"):
    draft = uploaded(client, user, data, name)
    read_it()
    draft.refresh_from_db()
    return draft


def page(client, draft):
    return client.get(reverse("expedientes:s1_pliego_borrador", args=[draft.pk]))


def post(client, name, draft, data=None):
    return client.post(reverse(f"expedientes:s1_pliego_{name}", args=[draft.pk]), data or {})


def input_names(html):
    return set(re.findall(r'<(?:input|textarea|select)[^>]*\bname="([^"]+)"', html))


# --- La entrada «Subir el pliego» de la pantalla de alta ----------------------------------------


def test_the_new_procedure_screen_offers_the_upload(client, operator_user):
    """REQ-077: la entrada «Subir el pliego» del alta está habilitada y es un archivo: lo único
    que se elige; el resto de la pantalla solo tiene el enlace del Portal."""
    log_in(client, operator_user)
    html = client.get(reverse("expedientes:nuevo")).content.decode()
    assert "Disponible en breve" not in html
    assert reverse("expedientes:s1_pliego_subir") in html
    assert 'type="file"' in html and "Subir y leer el pliego" in html
    assert input_names(html) - {"csrfmiddlewaretoken"} == {"url", "file"}


def test_there_is_no_blank_entry_route_or_form(client, operator_user, evaluator_user):
    """REQ-077: no existe ruta ni formulario de alta en blanco; sin archivo no se crea nada ni se
    puede escribir un procedimiento a mano."""
    def walk(patterns, prefix=""):
        for item in patterns:
            if hasattr(item, "url_patterns"):
                yield from walk(item.url_patterns, prefix + str(item.pattern))
            else:
                yield item.name or "", prefix + str(item.pattern)

    names = {name for name, _ in walk(get_resolver().url_patterns)}
    assert not {n for n in names if re.search(r"crear|blanco|manual|alta_a_mano", n)}
    log_in(client, evaluator_user)
    created_before = m.Procedure.objects.count()
    for url in (reverse("expedientes:s1_pliego_subir"), reverse("expedientes:nuevo")):
        response = client.post(url, {"number": "X-1", "subject": "Algo", "procedure_type": "LP",
                                     "authorization_date": "2025-01-01"})
        assert response.status_code in (200, 302)
    assert m.Procedure.objects.count() == created_before
    assert not m.ProcedureDraft.objects.exists()


def test_uploading_leaves_a_reading_draft_and_the_page_follows_it(client, operator_user):
    """REQ-077: subir deja el borrador «leyendo» sin procedimiento y la pantalla muestra el
    avance en vivo (se actualiza sola) hasta que la lectura termina."""
    draft = uploaded(client, operator_user)
    assert draft.state == ProposalState.LEYENDO and not m.Procedure.objects.exists()
    html = page(client, draft).content.decode()
    assert "Leyendo el pliego" in html or "En espera de lectura" in html
    assert 'http-equiv="refresh"' in html
    assert "Datos propuestos" not in html
    read_it()
    html = page(client, draft).content.decode()
    assert 'http-equiv="refresh"' not in html and "Datos propuestos" in html


def test_a_refused_file_comes_back_to_the_entry_with_the_reason(client, operator_user):
    """REQ-077: un archivo que no es PDF ni .html, o uno repetido, vuelve a la pantalla de alta
    con el motivo en lenguaje llano y no deja nada."""
    log_in(client, operator_user)
    response = upload(client, b"esto no es un pliego", "notas.txt")
    html = client.get(response.url).content.decode()
    assert response.url.startswith(reverse("expedientes:nuevo"))
    assert "no es un PDF" in html
    assert not m.ProcedureDraft.objects.exists()
    data = case_pdf()
    uploaded(client, operator_user, data)
    again = upload(client, data, "otra-vez.pdf")
    assert "ya se subió" in client.get(again.url).content.decode()
    assert m.ProcedureDraft.objects.count() == 1


def test_pending_drafts_are_listed_in_the_entry(client, operator_user):
    """REQ-077: un pliego leído que espera aprobación se puede retomar desde la pantalla de
    alta."""
    draft = proposed(client, operator_user)
    html = client.get(reverse("expedientes:nuevo")).content.decode()
    assert reverse("expedientes:s1_pliego_borrador", args=[draft.pk]) in html
    assert "pliego.pdf" in html


# --- La propuesta -------------------------------------------------------------------------------


def test_the_proposal_shows_each_datum_and_line_with_where_it_was_read(client, evaluator_user):
    """REQ-077: datos y renglones propuestos, cada uno con dónde lo leyó (página y cita), sin
    ningún campo para tipear datos o renglones; la fecha en hora local."""
    draft = proposed(client, evaluator_user)
    html = page(client, draft).content.decode()
    assert "Lo que el sistema leyó del pliego" in html
    assert "Datos propuestos" in html and "Renglones propuestos" in html
    for text in ("SINT-0100-PRUEBA", "EX-2099-00001234-SINT", "Licitación pública",
                 "ADQUISICIÓN DE INSUMOS SINTÉTICOS DE PRUEBA", "15/03/2025",
                 "PRODUCTO SINTÉTICO A", "PRODUCTO SINTÉTICO B", "PRODUCTO SINTÉTICO C"):
        assert text in html, text
    assert html.count("pág. 1") >= 8
    assert f"{timezone.localtime(draft.created_at):%d/%m/%Y %H:%M}" in html
    assert "pliego.pdf" in html
    # Lo único que se escribe es el valor y el motivo de una corrección, el motivo de un
    # rechazo y qué renglón se descarta.
    allowed = {"csrfmiddlewaretoken", "field", "value", "reason", "descartar", "aprobar"}
    assert input_names(html) <= allowed
    assert not [t for t in OLD_SCREENS if t in html]
    assert not [t for t in MOCKUP_TEXTS if t in html]


def test_the_type_read_from_the_process_number_is_marked(client, evaluator_user, fake_generation):
    """REQ-077: el tipo que sale del código del número de proceso dice «deducido del número de
    proceso»."""
    draft = proposed(client, evaluator_user, portal_style_pdf(), "portal.pdf")
    html = page(client, draft).content.decode()
    assert "deducido del número de proceso" in html


def test_an_undetermined_datum_is_shown_as_such_with_correct(client, evaluator_user,
                                                             fake_generation):
    """REQ-077: lo que no se pudo leer figura «No determinado» con su «Corregir» (valor y
    motivo), nunca un formulario en blanco, y no se puede aprobar hasta completarlo."""
    draft = proposed(client, evaluator_user, portal_style_pdf(with_date=False), "sin-fecha.pdf")
    assert draft.proposal["fields"]["authorization_date"]["state"] == "no_determinado"
    html = page(client, draft).content.decode()
    assert "No determinado" in html
    row = html[html.index("Fecha de autorización"):]
    row = row[:row.index("</tr>")]
    assert "Corregir" in row and 'name="value"' in row and 'name="reason"' in row
    assert "Falta" in html and "fecha de autorización" in html
    assert re.search(r'<button[^>]*disabled[^>]*>\s*Aprobar todo lo propuesto', html)
    response = post(client, "aprobar", draft)
    assert response.status_code == 302
    assert "Falta la fecha de autorización" in client.get(response.url).content.decode()
    assert not m.Procedure.objects.exists()


def test_correcting_needs_a_reason_and_records_who_and_when(client, evaluator_user,
                                                           fake_generation):
    """REQ-077: corregir exige el motivo; deja lo propuesto, lo corregido, el motivo, quién y
    cuándo (en hora local), y a la vista; sin motivo no cambia nada."""
    draft = proposed(client, evaluator_user, portal_style_pdf(with_date=False), "sin-fecha.pdf")
    refused = post(client, "corregir", draft, {"field": "authorization_date",
                                              "value": "2025-11-14", "reason": "  "})
    assert "Escriba el motivo" in client.get(refused.url).content.decode()
    draft.refresh_from_db()
    assert draft.proposal["corrections"] == []
    ok = post(client, "corregir", draft, {"field": "authorization_date", "value": "2025-11-14",
                                         "reason": "Figura en la resolución de apertura"})
    assert ok.status_code == 302
    draft.refresh_from_db()
    entry = draft.proposal["corrections"][0]
    assert entry["by"] == evaluator_user.username and entry["reason"] and entry["at"]
    assert entry["proposed"] is None and entry["corrected"] == "2025-11-14"
    html = page(client, draft).content.decode()
    assert "14/11/2025" in html and "Figura en la resolución de apertura" in html
    assert evaluator_user.username in html
    assert "Corregido" in html
    event = AuditEvent.objects.filter(event_type=EventType.PROCEDURE_PROPOSAL,
                                      detail__action="correct", outcome="ok").latest("pk")
    assert event.detail["reason"] == "Figura en la resolución de apertura"
    assert event.user_id == evaluator_user.pk


def test_a_line_quantity_can_be_corrected(client, evaluator_user, fake_generation):
    """REQ-077: la cantidad, la unidad y la descripción de un renglón se corrigen con valor y
    motivo (el pliego del caso-00 trae renglones sin cantidad); no hay forma de agregar."""
    data = tender_pdf([[para("1. RENGLÓN N° 1 - SILLA SINTÉTICA")]])
    draft = proposed(client, evaluator_user, data, "renglon.pdf")
    html = page(client, draft).content.decode()
    assert "SILLA SINTÉTICA" in html and "No consta" in html
    assert 'value="line.1.quantity"' in html and 'value="line.1.unit"' in html
    assert 'value="line.1.description"' in html
    post(client, "corregir", draft, {"field": "line.1.quantity", "value": "30",
                                    "reason": "Figura en el anexo"})
    html = page(client, draft).content.decode()
    assert re.search(r"\b30\b", html) and "Figura en el anexo" in html
    bad = post(client, "corregir", draft, {"field": "line.9.quantity", "value": "3",
                                          "reason": "agregar"})
    assert "no está en la propuesta" in client.get(bad.url).content.decode()


# --- Aprobar, descartar y rechazar ---------------------------------------------------------------


def test_approving_creates_the_procedure_and_opens_it_with_its_origin(client, evaluator_user,
                                                                      two_regimes):
    """REQ-077: aprobar crea el procedimiento y abre la sección 1, que muestra el origen: el
    pliego, quién lo subió, quién lo aprobó y cuándo."""
    draft = proposed(client, evaluator_user)
    response = post(client, "aprobar", draft)
    procedure = m.Procedure.objects.get()
    assert response.status_code == 302
    assert response.url.startswith(reverse("expedientes:procedimiento", args=[procedure.pk]))
    html = client.get(response.url).content.decode()
    assert procedure.number == "SINT-0100-PRUEBA"
    assert "Se creó desde el pliego subido" in html or "Alta desde el pliego" in html
    block = html[html.index('id="s1-pliego"'):]
    assert "pliego.pdf" in block
    assert f"subido por {evaluator_user.username}" in block
    assert f"aprobado por {evaluator_user.username}" in block
    assert PortalLine.objects.filter(procedure=procedure).count() == 3
    assert page(client, draft).status_code == 302  # la propuesta ya no está: va al procedimiento


def test_approving_after_a_correction_keeps_the_correction_in_the_origin(
        client, evaluator_user, two_regimes, fake_generation):
    """REQ-077: lo corregido (valor, motivo, quién, cuándo) queda visible en el origen del
    procedimiento recién creado."""
    draft = proposed(client, evaluator_user, portal_style_pdf(with_date=False), "sin-fecha.pdf")
    post(client, "corregir", draft, {"field": "authorization_date", "value": "2025-11-14",
                                    "reason": "Figura en la resolución de apertura"})
    response = post(client, "aprobar", draft)
    html = client.get(response.url).content.decode()
    block = html[html.index('id="s1-pliego"'):]
    assert "Figura en la resolución de apertura" in block and "14/11/2025" in block
    assert m.Procedure.objects.get().authorization_date.isoformat() == "2025-11-14"


def test_a_line_can_be_discarded_before_approving(client, evaluator_user, two_regimes):
    """REQ-077: el evaluador descarta un renglón de la propuesta y no se carga."""
    draft = proposed(client, evaluator_user)
    post(client, "aprobar", draft, {"descartar": ["2"]})
    numbers = sorted(PortalLine.objects.values_list("number", flat=True))
    assert numbers == [1, 3]


def test_a_pliego_without_recognizable_data_shows_undetermined_and_creates_nothing(
        client, evaluator_user, fake_generation):
    """REQ-077: un pliego sin datos reconocibles muestra todo «No determinado», no se puede
    aprobar y no crea nada."""
    draft = proposed(client, evaluator_user, tender_pdf([[para("Texto libre sin datos.")]]),
                     "libre.pdf")
    html = page(client, draft).content.decode()
    assert html.count("No determinado") >= 4
    assert re.search(r'<button[^>]*disabled[^>]*>\s*Aprobar todo lo propuesto', html)
    post(client, "aprobar", draft)
    assert not m.Procedure.objects.exists()


def test_rejecting_the_reading_needs_a_reason_and_lets_the_file_be_uploaded_again(
        client, evaluator_user, fake_generation):
    """REQ-077: «Rechazar la lectura» pide el motivo, vuelve a la pantalla de alta con aviso y
    el mismo archivo se puede volver a subir."""
    draft = proposed(client, evaluator_user)
    no_reason = post(client, "rechazar", draft, {"reason": ""})
    assert "Escriba el motivo" in client.get(no_reason.url).content.decode()
    draft.refresh_from_db()
    assert draft.state == ProposalState.PROPUESTO
    done = post(client, "rechazar", draft, {"reason": "Se leyó mal el pliego"})
    assert done.url.startswith(reverse("expedientes:nuevo"))
    assert "Se descartó la lectura" in client.get(done.url).content.decode()
    draft.refresh_from_db()
    assert draft.state == ProposalState.RECHAZADO
    assert upload(client, case_pdf()).status_code == 302
    assert m.ProcedureDraft.objects.count() == 2


def test_a_failed_reading_is_explained_and_can_be_discarded(client, evaluator_user):
    """REQ-077: una lectura que falló dice por qué en lenguaje llano y se puede descartar."""
    draft = uploaded(client, evaluator_user)
    m.ProcedureDraft.objects.filter(pk=draft.pk).update(
        state=ProposalState.FALLIDO, failure="ValueError: algo técnico")
    m.Job.objects.filter(pk=draft.job_id).update(status=m.JobStatus.FAILED,
                                                 error="ValueError: algo técnico")
    html = page(client, draft).content.decode()
    assert "No se pudo leer" in html and "ValueError" not in html
    assert "Rechazar la lectura" in html
    post(client, "rechazar", draft, {"reason": "Falló la lectura"})
    draft.refresh_from_db()
    assert draft.state == ProposalState.RECHAZADO


# --- Roles ----------------------------------------------------------------------------------------


def test_the_operator_uploads_and_sees_without_approve_or_correct(client, operator_user):
    """REQ-077: el operador sube y ve la propuesta con citas, sin botones de aprobar, corregir
    ni rechazar."""
    draft = proposed(client, operator_user)
    html = page(client, draft).content.decode()
    assert "Datos propuestos" in html and "SINT-0100-PRUEBA" in html
    for text in ("Aprobar todo lo propuesto", "Rechazar la lectura", 'name="reason"',
                 'name="value"'):
        assert text not in html, text
    assert "Lo aprueba un evaluador" in html


def test_the_operator_post_is_refused_with_403_and_audited(client, operator_user):
    """REQ-077: forzar los POST del evaluador siendo operador da 403, deja el rechazo y no
    cambia nada."""
    draft = proposed(client, operator_user)
    before = AuditEvent.objects.filter(outcome="rejected").count()
    for name, data in (("corregir", {"field": "subject", "value": "Otro", "reason": "x"}),
                       ("aprobar", {}), ("rechazar", {"reason": "x"})):
        assert post(client, name, draft, data).status_code == 403, name
    assert AuditEvent.objects.filter(outcome="rejected").count() == before + 3
    draft.refresh_from_db()
    assert draft.state == ProposalState.PROPUESTO and draft.proposal["corrections"] == []
    assert not m.Procedure.objects.exists()


def test_a_reader_cannot_see_or_upload(client, evaluator_user, no_commission_user):
    """REQ-077: sin rol de la Comisión no se sube ni se ve la propuesta (403)."""
    draft = proposed(client, evaluator_user)
    client.logout()
    log_in(client, no_commission_user)
    assert page(client, draft).status_code == 403
    assert upload(client, case_pdf(), "otro.pdf").status_code == 403
    assert m.ProcedureDraft.objects.count() == 1


# --- En la sección 1 ---------------------------------------------------------------------------------


def test_section_one_of_a_procedure_without_a_pliego_origin_offers_the_upload(
        client, operator_user, procedure):
    """REQ-097: en la sección 1 de un procedimiento que no nació del pliego está «Subir el
    pliego», que lleva al alta; no hay origen que mostrar."""
    log_in(client, operator_user)
    html = client.get(reverse("expedientes:procedimiento", args=[procedure.pk])).content.decode()
    block = html[html.index('id="s1-pliego"'):]
    assert "Subir el pliego" in block
    assert reverse("expedientes:nuevo") in block
    assert "subido por" not in block


def test_section_one_lists_the_drafts_waiting(client, operator_user, procedure):
    """REQ-097: los pliegos leídos que esperan aprobación se ven y se retoman desde la sección
    1."""
    draft = proposed(client, operator_user)
    html = client.get(reverse("expedientes:procedimiento", args=[procedure.pk])).content.decode()
    assert reverse("expedientes:s1_pliego_borrador", args=[draft.pk]) in html


def test_the_tema_status_is_empty_and_context_is_pure_reading(operator_user, procedure, rf):
    """REQ-097: el tema no inventa cuentas para un procedimiento y su contexto sin
    procedimiento ofrece la subida."""
    from evaluon.journey.temas import s1_pliego

    assert s1_pliego.status(operator_user, procedure).pending == 0
    request = rf.get("/")
    assert s1_pliego.context(operator_user, None, request)["upload"] is True
    assert s1_portal.pack([]) is not None


def test_the_finished_notice_of_a_reading_does_not_break_the_next_page(client, operator_user):
    """REQ-077: cuando termina la lectura del pliego, el aviso de pedidos terminados (que va en
    todas las páginas) lo nombra y enlaza a la propuesta, sin romper la página siguiente."""
    draft = uploaded(client, operator_user)
    read_it()
    html = client.get(reverse("expedientes:index")).content.decode()
    assert "Terminó la lectura del pliego subido" in html
    assert reverse("expedientes:s1_pliego_borrador", args=[draft.pk]) in html
