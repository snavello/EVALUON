"""Informe técnico del área requirente (REQ-074 de la 013; REQ-061 de la 004; ADR-0043; T-190).

Decisiones literales del responsable: «creo que pasa algo similar con el informe tecnico del area
requirente lo mismo para el informe tecnico»; «La parte tecnica ya te dije que venia del area
correspondiente»; «la comision debiera dar el ok de que tiene el informe tecnico aprobado».

La Comisión sube el informe aprobado; el sistema propone por oferta y renglón apto o no apto con
la cita literal del informe y la Comisión confirma o corrige dando el ok. Caso chico inventado
(P4): dos ofertas, seis renglones, uno no apto. El modelo es un guion que lee el texto del informe
que le llega, como lo haría el real.
"""

import json
import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from evaluon.accounts.permissions import RoleRejected
from evaluon.ai import ServiceUnavailableError
from evaluon.ai import generation as generation_client
from evaluon.assessment import documents
from evaluon.assessment import models as am
from evaluon.assessment.services import evaluate, technical
from evaluon.assessment.services import technical_report as report
from evaluon.audit.models import AuditEvent, EventType
from evaluon.audit.models import Outcome as EventOutcome
from evaluon.offers import models as om
from evaluon.offers.services import offers as offers_service
from evaluon.tenders import jobs
from tests.assessment.test_matrix import DECLARATION, add_run, requirement
from tests.offers.conftest import make_offer
from tests.offers.test_screens import log_in, text_of
from tests.tenders.pdfs import para, tender_pdf

pytestmark = [pytest.mark.django_db, pytest.mark.decision_literal]

PENDING = ("no_determinado", "pendiente_informe_tecnico")

APTO = "el área considera apto lo ofertado."
NO_APTO = "el área considera NO APTO lo ofertado: no cumple el gramaje."


def line(bidder, item, text=APTO):
    return f"{bidder} - Renglón {item}: {text}"


def paragraphs(title, *lines):
    """Un párrafo por línea: la lectura une las líneas de un mismo párrafo en una sola."""
    return [para(title), *[para(text) for text in lines]]


def report_pdf(*lines):
    return tender_pdf([paragraphs("INFORME TÉCNICO DEL ÁREA REQUIRENTE", *lines)], header=None)


FULL = [line("Oferente A", 1), line("Oferente A", 2), line("Oferente A", 3),
        line("Oferente B", 1), line("Oferente B", 2, NO_APTO), line("Oferente B", 3)]


class ReportModel:
    """Guion del modelo: lee el informe que llega en el pedido y contesta, por renglón, lo que
    ese texto dice del oferente (apto, no apto o no lo trata). `invent` hace que cite una frase
    que el informe no tiene; `fail` apaga el servicio."""

    def __init__(self, fake):
        self.fake = fake
        self.calls = []
        self.invent = False
        self.fail = False

    def respond(self, messages, schema, **kwargs):
        user = messages[-1]["content"]
        self.calls.append(user)
        if self.fail:
            self.fake.unavailable()
            return self.fake.generate(messages, schema, **kwargs)
        text = re.search(r"\[INFORME\]\n(.*?)\n\[/INFORME\]", user, re.DOTALL).group(1)
        bidder = re.search(r"Oferente: (.*?) \(oferta", user).group(1)
        items = [int(n) for n in re.findall(r"^Renglón (\d+)", user, re.MULTILINE)]
        answers = []
        for item in items:
            found = next((ln for ln in text.splitlines()
                          if ln.startswith(f"{bidder} - Renglón {item}:")), None)
            if found is None:
                answers.append({"renglon": item, "dictamen": "no_trata", "cita": "",
                                "motivo": ""})
                continue
            verdict = "no_apto" if "NO APTO" in found else "apto"
            quote = "El área técnica aprobó todo sin reservas." if self.invent else found
            answers.append({"renglon": item, "dictamen": verdict, "cita": quote,
                            "motivo": "Lo dice el informe."})
        self.fake.respond(json.dumps({"renglones": answers}, ensure_ascii=False))
        return self.fake.generate(messages, schema, **kwargs)


@pytest.fixture
def model(fake_ai, monkeypatch):
    script = ReportModel(fake_ai.generation)
    monkeypatch.setattr(generation_client, "generate", script.respond)
    return script


@pytest.fixture
def offers(procedure, operator_user):
    """Dos ofertas del caso chico, con las filas de los renglones 1, 2 y 3 pendientes del informe
    técnico (seis renglones en total)."""
    made = []
    for name in ("Oferente A", "Oferente B"):
        offer = make_offer(procedure, operator_user, name,
                           {"oferta.pdf": [f"{DECLARATION}. {name}. Texto de la oferta."]})
        rows = {i: requirement(procedure, item=i) for i in (1, 2, 3)}
        add_run(operator_user, procedure, offer,
                {requirement(procedure, "declaración jurada"): "cumple",
                 **{row: PENDING for row in rows.values()}})
        made.append(offer)
    return made


def read_queue():
    ran = []
    while True:
        job = jobs.run_next()
        if job is None:
            return ran
        ran.append(job)


def verdicts(offer):
    return {i: p.verdict for i, p in technical.proposals_of(offer).items()}


def test_one_report_per_offer_gets_a_proposal_with_the_literal_quote(
        offers, evaluator_user, model):
    """REQ-074, REQ-061, P6: el informe de una oferta queda como documento de tipo
    informe_tecnico con su hecho; leído, el sistema propone por renglón apto con la cita literal
    del informe (su página y posiciones) y deja el hecho de la propuesta con modelo y versión."""
    a, _ = offers
    sent = report_pdf(*FULL[:3])
    uploaded = report.upload_report(evaluator_user, offer_id=a.pk, data=sent,
                                    file_name="informe.pdf")
    document = uploaded.documents[0]
    assert document.kind == om.DocumentKind.INFORME_TECNICO and document.offer == a
    event = AuditEvent.objects.get(pk=uploaded.events[0].pk)
    assert event.event_type == EventType.EVAL_DECISION and event.outcome == EventOutcome.OK
    assert event.detail["action"] == "informe_tecnico" and event.detail["scope"] == "oferta"
    assert event.detail["file_sha256"] == document.file_sha256
    assert technical.proposals_of(a) == {}

    read_queue()

    proposals = technical.proposals_of(a)
    assert {i: p.verdict for i, p in proposals.items()} == {1: "apto", 2: "apto", 3: "apto"}
    canonical = document.readings.get().canonical_text
    for item, proposal in proposals.items():
        assert proposal.quote == FULL[item - 1] and proposal.quote in canonical
        assert proposal.page == 1 and proposal.document == document.pk
    built = AuditEvent.objects.get(event_type=EventType.EVAL_BUILD, detail__kind="technical_proposal",
                                   detail__offer=a.pk)
    assert built.outcome == EventOutcome.OK and built.detail["document"] == document.pk
    assert built.detail["models"]["prompt"] == "informe-tecnico-v1"
    assert built.detail["items"]["1"]["char_start"] < built.detail["items"]["1"]["char_end"]
    document.refresh_from_db()
    assert document.kind == om.DocumentKind.INFORME_TECNICO  # la lectura no lo reclasifica


def test_one_report_for_the_procedure_gives_a_proposal_per_offer_and_item(
        offers, procedure, evaluator_user, model):
    """REQ-074: un informe por procedimiento se carga en cada oferta; el sistema propone por
    oferta y renglón (seis, uno no apto), cada una con la cita del oferente que corresponde."""
    a, b = offers
    uploaded = report.upload_report(evaluator_user, procedure_id=procedure.pk,
                                    data=report_pdf(*FULL), file_name="informe.pdf")
    assert {d.offer_id for d in uploaded.documents} == {a.pk, b.pk}
    assert all(e.detail["scope"] == "procedimiento" for e in uploaded.events)

    read_queue()

    assert verdicts(a) == {1: "apto", 2: "apto", 3: "apto"}
    assert verdicts(b) == {1: "apto", 2: "no_apto", 3: "apto"}
    for offer in (a, b):
        for item, proposal in technical.proposals_of(offer).items():
            assert proposal.quote.startswith(f"{offer.bidder} - Renglón {item}:")
    assert technical.proposals_of(b)[2].quote == FULL[4]


def test_what_the_report_does_not_treat_is_said_and_not_proposed(
        offers, procedure, evaluator_user, model):
    """REQ-074, P3: si el informe no trata una oferta o un renglón, el sistema lo dice y no
    propone; no completa lo que el informe no dice."""
    a, b = offers
    sent = report_pdf(line("Oferente A", 1), line("Oferente A", 2, NO_APTO))
    report.upload_report(evaluator_user, procedure_id=procedure.pk, data=sent,
                         file_name="informe.pdf")
    read_queue()
    assert verdicts(a) == {1: "apto", 2: "no_apto", 3: ""}
    proposal = technical.proposals_of(a)[3]
    assert proposal.reason == "no_trata" and proposal.quote == ""
    assert "no trata" in proposal.reason_label
    assert verdicts(b) == {1: "", 2: "", 3: ""}


def test_a_quote_that_is_not_in_the_report_is_not_a_proposal(
        offers, evaluator_user, model):
    """REQ-074, P3: si el modelo cita algo que el informe no dice letra por letra, no hay
    propuesta para ese renglón, con su motivo."""
    a, _ = offers
    model.invent = True
    report.upload_report(evaluator_user, offer_id=a.pk, data=report_pdf(*FULL[:3]),
                         file_name="informe.pdf")
    read_queue()
    assert verdicts(a) == {1: "", 2: "", 3: ""}
    assert {p.reason for p in technical.proposals_of(a).values()} == {"cita_no_ubicada"}
    built = AuditEvent.objects.get(event_type=EventType.EVAL_BUILD, detail__offer=a.pk)
    assert built.detail["anomalies"]


def test_the_proposal_changes_no_result_until_the_commission_gives_the_ok(
        offers, evaluator_user, model):
    """REQ-074, REQ-061, P3: la propuesta no cambia ninguna fila; sigue pendiente del informe
    técnico hasta el ok de la Comisión."""
    a, _ = offers
    before = am.Result.objects.count()
    report.upload_report(evaluator_user, offer_id=a.pk, data=report_pdf(*FULL[:3]),
                         file_name="informe.pdf")
    read_queue()
    assert am.Result.objects.count() == before and not am.TechnicalOk.objects.exists()
    for item in (1, 2, 3):
        row = technical.item_rows(a)[item]
        assert evaluate.current_result(a, row).doubt == "pendiente_informe_tecnico"


def test_the_commission_confirms_or_corrects_and_the_ok_records_which(
        offers, evaluator_user, model):
    """REQ-074, REQ-061, P6: al dar el ok, la Comisión confirma lo propuesto o lo corrige; el
    hecho del ok anota, por renglón, qué se propuso, qué se dio y si se corrigió. Manda lo que da
    la Comisión."""
    _, b = offers
    report.upload_report(evaluator_user, offer_id=b.pk, data=report_pdf(*FULL[3:]),
                         file_name="informe.pdf")
    read_queue()
    assert verdicts(b) == {1: "apto", 2: "no_apto", 3: "apto"}
    # La Comisión confirma el 1 y el 2 y corrige el 3 (el área lo aclaró por otra vía).
    applied = technical.give_ok(evaluator_user, b, verdicts={1: "apto", 2: "no_apto",
                                                             3: "no_apto"})
    record = AuditEvent.objects.get(pk=applied.event.pk).detail["proposal"]
    assert record["1"] == {"proposed": "apto", "given": "apto", "corrected": False,
                           "document": record["1"]["document"], "event": record["1"]["event"]}
    assert record["2"]["corrected"] is False and record["2"]["proposed"] == "no_apto"
    assert record["3"]["proposed"] == "apto" and record["3"]["given"] == "no_apto"
    assert record["3"]["corrected"] is True
    outcomes = {i: evaluate.current_result(b, technical.item_rows(b)[i]).outcome
                for i in (1, 2, 3)}
    assert outcomes == {1: "cumple", 2: "no_cumple", 3: "no_cumple"}


def test_an_ok_without_a_proposal_records_that_there_was_none(offers, evaluator_user):
    """REQ-061, P6: sin informe subido el ok sigue siendo manual y anota que no hubo propuesta."""
    a, _ = offers
    applied = technical.give_ok(evaluator_user, a, items=[1], verdicts={1: "apto"})
    record = AuditEvent.objects.get(pk=applied.event.pk).detail["proposal"]
    assert record["1"]["proposed"] is None and record["1"]["corrected"] is False


def test_a_report_with_several_windows_is_read_in_all_of_them(
        offers, evaluator_user, model, settings):
    """REQ-074: un informe más largo que un pedido se lee por tramos y se toma lo que dice en
    cualquiera; dos tramos que dicen cosas distintas del mismo renglón no proponen."""
    a, _ = offers
    settings.ASSESSMENT_GROUP_TOKENS = 60
    pages = [paragraphs("INFORME TÉCNICO", line("Oferente A", 1), "Se deja constancia."),
             paragraphs("Hoja de continuación", line("Oferente A", 2), "Se deja constancia."),
             paragraphs("Hoja de cierre", line("Oferente A", 3, NO_APTO), "Se deja constancia.")]
    report.upload_report(evaluator_user, offer_id=a.pk, data=tender_pdf(pages, header=None),
                         file_name="informe.pdf")
    read_queue()
    assert len(model.calls) >= 2
    assert verdicts(a) == {1: "apto", 2: "apto", 3: "no_apto"}


def test_the_report_is_not_read_as_a_document_of_the_offer(offers, evaluator_user, model):
    """REQ-074, P3: el informe del área no es un documento de la oferta: no entra en el texto
    con que se evalúa la oferta (ahí podría citarse como si lo hubiera presentado el oferente)."""
    a, _ = offers
    before = documents.build_offer_text(a)
    report.upload_report(evaluator_user, offer_id=a.pk, data=report_pdf(*FULL[:3]),
                         file_name="informe.pdf")
    read_queue()
    after = documents.build_offer_text(a)
    assert [d.document.pk for d in after.documents] == [d.document.pk for d in before.documents]
    assert report.reports_of(a)[0].pk not in [d.document.pk for d in after.documents]


def test_the_file_name_does_not_change_the_kind(offers, evaluator_user, model):
    """REQ-074: un archivo que se llama «especificaciones técnicas» y es el informe sigue siendo
    el informe (la clasificación por reglas no lo pisa), también si se reclasifica."""
    a, _ = offers
    document = report.upload_report(evaluator_user, offer_id=a.pk, data=report_pdf(*FULL[:3]),
                                    file_name="especificaciones-tecnicas.pdf").documents[0]
    read_queue()
    offers_service.reclassify_documents(evaluator_user, a.procedure)
    document.refresh_from_db()
    assert document.kind == om.DocumentKind.INFORME_TECNICO


def test_only_the_evaluator_uploads_the_report_or_asks_for_a_proposal(
        offers, procedure, operator_user, no_commission_user, evaluator_user, model):
    """P3, REQ-074: el operador y quien no es de la Comisión no suben el informe ni piden
    proponer; no queda ningún documento y sí el hecho rechazado."""
    a, _ = offers
    sent = report_pdf(*FULL)
    for user in (operator_user, no_commission_user):
        with pytest.raises(RoleRejected):
            report.upload_report(user, offer_id=a.pk, data=sent, file_name="i.pdf")
        with pytest.raises(RoleRejected):
            report.upload_report(user, procedure_id=procedure.pk, data=sent, file_name="i.pdf")
        with pytest.raises(RoleRejected):
            report.request_proposal(user, a.pk)
    assert report.reports_of(a) == []
    assert AuditEvent.objects.filter(outcome=EventOutcome.REJECTED).count() >= 6


def test_a_failing_model_leaves_the_failure_and_the_proposal_can_be_asked_by_hand(
        offers, evaluator_user, model):
    """REQ-074, P6: si el modelo no responde cuando termina la lectura, el pedido de lectura
    queda terminado, queda el hecho de la falla y la Comisión pide proponer de nuevo."""
    a, _ = offers
    model.fail = True
    document = report.upload_report(evaluator_user, offer_id=a.pk, data=report_pdf(*FULL[:3]),
                                    file_name="informe.pdf").documents[0]
    job = jobs.run_next()
    assert job.status == "done" and job.target_id == document.pk
    assert technical.proposals_of(a) == {}
    failed = AuditEvent.objects.get(event_type=EventType.EVAL_BUILD,
                                    outcome=EventOutcome.FAILED, detail__offer=a.pk)
    assert failed.detail["reason"] == "falla"
    with pytest.raises(report.ReportRefused) as caught:
        report.request_proposal(evaluator_user, a.pk)
    assert caught.value.reason == "model_failed"
    model.fail = False
    report.request_proposal(evaluator_user, a.pk)
    assert verdicts(a) == {1: "apto", 2: "apto", 3: "apto"}


def test_asking_for_a_proposal_needs_a_report_already_read(offers, evaluator_user, model):
    """REQ-074: sin informe no hay nada que proponer; mientras se lee, se rechaza (y queda el
    hecho)."""
    a, _ = offers
    with pytest.raises(report.ReportRefused) as caught:
        report.request_proposal(evaluator_user, a.pk)
    assert caught.value.reason == "report_not_uploaded"
    report.upload_report(evaluator_user, offer_id=a.pk, data=report_pdf(*FULL[:3]),
                         file_name="informe.pdf")
    with pytest.raises(report.ReportRefused) as caught:
        report.request_proposal(evaluator_user, a.pk)
    assert caught.value.reason == "reading_in_progress"
    assert AuditEvent.objects.filter(event_type=EventType.EVAL_BUILD,
                                     outcome=EventOutcome.REJECTED).count() == 2


def test_a_second_report_does_not_erase_what_the_first_one_said(
        offers, evaluator_user, model):
    """REQ-074: con dos informes de la misma oferta, para cada renglón rige el más nuevo que lo
    trata; uno que no trata un renglón no borra lo que el otro decía."""
    a, _ = offers
    report.upload_report(evaluator_user, offer_id=a.pk, data=report_pdf(*FULL[:3]),
                         file_name="informe-1.pdf")
    read_queue()
    report.upload_report(evaluator_user, offer_id=a.pk,
                         data=report_pdf(line("Oferente A", 2, NO_APTO)),
                         file_name="informe-2.pdf")
    read_queue()
    assert verdicts(a) == {1: "apto", 2: "no_apto", 3: "apto"}


# --- Pantalla ----------------------------------------------------------------------------------


def test_the_matrix_shows_the_proposal_next_to_the_ok_and_preloads_it(
        client, offers, procedure, evaluator_user, model):
    """REQ-074: la matriz muestra la propuesta con su cita junto al ok técnico y la precarga en
    el dictamen; lo que el informe no trata figura como tal y queda sin precargar."""
    a, _ = offers
    report.upload_report(evaluator_user, offer_id=a.pk,
                         data=report_pdf(line("Oferente A", 1), line("Oferente A", 2, NO_APTO)),
                         file_name="informe.pdf")
    read_queue()
    log_in(client, evaluator_user)
    response = client.get(reverse("assessment:matrix", args=[procedure.pk]))
    page = text_of(response)
    assert "Propone Apto. El informe dice: «Oferente A - Renglón 1:" in page
    assert "Propone No apto. El informe dice: «Oferente A - Renglón 2:" in page
    assert "No propone: El informe no trata este renglón de esta oferta." in page
    assert "Falta el informe técnico del área de esta oferta" in page  # la oferta B
    html = response.content.decode()
    select_1 = re.search(r'<select name="verdict_1".*?</select>', html, re.DOTALL).group(0)
    select_2 = re.search(r'<select name="verdict_2".*?</select>', html, re.DOTALL).group(0)
    assert 'value="apto" selected' in select_1 and 'value="no_apto" selected' in select_2


def test_the_upload_buttons_are_only_for_the_evaluator(
        client, offers, procedure, evaluator_user, operator_user):
    """REQ-074: «Subir informe técnico» (por oferta y por procedimiento) solo lo ve el
    evaluador."""
    url = reverse("assessment:matrix", args=[procedure.pk])
    log_in(client, evaluator_user)
    page = text_of(client.get(url))
    assert page.count("Subir informe técnico") == 3  # una por oferta y la del procedimiento
    client.logout()
    log_in(client, operator_user)
    page = text_of(client.get(url))
    assert "Subir informe técnico" not in page
    assert "Solo el evaluador de la Comisión sube el informe técnico del área" in page


def test_the_upload_from_the_matrix_loads_the_report_and_shows_it(
        client, offers, procedure, evaluator_user, operator_user, model):
    """REQ-074: el informe se sube desde la matriz (por oferta o por procedimiento); vuelve a la
    matriz con el informe y su huella; un archivo que no se lee vuelve con el motivo (422); el
    operador recibe 403."""
    a, b = offers
    sent = report_pdf(*FULL)
    one = reverse("assessment:report_upload", args=[a.pk])
    every = reverse("assessment:report_upload_procedure", args=[procedure.pk])
    log_in(client, operator_user)
    assert client.post(one, {"file": SimpleUploadedFile("i.pdf", sent)}).status_code == 403
    assert client.post(every, {"file": SimpleUploadedFile("i.pdf", sent)}).status_code == 403
    client.logout()
    log_in(client, evaluator_user)
    assert client.post(one, {"file": SimpleUploadedFile("i.txt", b"nada")}).status_code == 422
    good = client.post(one, {"file": SimpleUploadedFile("informe-a.pdf", sent)})
    assert good.status_code == 302 and good["Location"].endswith(f"#oferta-{a.number}")
    assert client.post(every, {"file": SimpleUploadedFile("informe-a.pdf", sent)}).status_code \
        == 302  # la oferta A ya lo tenía: se carga en la B
    assert len(report.reports_of(a)) == 1 and len(report.reports_of(b)) == 1
    again = client.post(every, {"file": SimpleUploadedFile("informe-a.pdf", sent)})
    assert again.status_code == 422  # ya está en todas
    page = text_of(client.get(reverse("assessment:matrix", args=[procedure.pk])))
    assert report.reports_of(a)[0].file_sha256 in page
    assert "El informe se está leyendo" in page


def test_the_propose_button_asks_again_and_shows_the_reason_when_refused(
        client, offers, procedure, evaluator_user, model):
    """REQ-074: «Proponer de nuevo desde el informe» aparece con el informe leído y propone."""
    a, _ = offers
    model.fail = True
    report.upload_report(evaluator_user, offer_id=a.pk, data=report_pdf(*FULL[:3]),
                         file_name="informe.pdf")
    read_queue()
    model.fail = False
    log_in(client, evaluator_user)
    url = reverse("assessment:matrix", args=[procedure.pk])
    assert "Proponer de nuevo desde el informe" in text_of(client.get(url))
    assert client.post(reverse("assessment:report_propose", args=[a.pk])).status_code == 302
    assert verdicts(a) == {1: "apto", 2: "apto", 3: "apto"}


def test_a_follow_up_hook_that_fails_does_not_stop_the_other(
        offers, evaluator_user, model, monkeypatch):
    """REQ-074: los pasos posteriores de la lectura son independientes: si uno falla, el otro
    corre y el pedido queda terminado."""
    a, _ = offers

    def broken(job):
        raise RuntimeError("falla de prueba")
    monkeypatch.setitem(jobs.AFTER_DONE, jobs.JobKind.READ_OFFER_DOCUMENT,
                        (broken, "evaluon.assessment.services.technical_report.after_read"))
    report.upload_report(evaluator_user, offer_id=a.pk, data=report_pdf(*FULL[:3]),
                         file_name="informe.pdf")
    job = jobs.run_next()
    assert job.status == "done"
    assert verdicts(a) == {1: "apto", 2: "apto", 3: "apto"}
