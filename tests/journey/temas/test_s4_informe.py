"""Tema «informe técnico del área» de la sección Evaluación y dictamen (REQ-089, REQ-097; plan 014,
T-209). El modelo es el simulado de la 013 (la GPU no se comparte); todo el material es
inventado (P4). Cada acción de la pestaña se compara con la ruta vieja de `assessment`: mismo
cambio y mismo hecho de auditoría."""

import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from evaluon.assessment import models as am
from evaluon.assessment.services import evaluate, technical
from evaluon.assessment.services import technical_report as report
from evaluon.audit.models import AuditEvent, EventType
from evaluon.audit.models import Outcome as AuditOutcome
from evaluon.journey.sections import sections_for
from evaluon.journey.stages import matriz_evaluacion
from evaluon.journey.temas import s4_informe
from evaluon.offers import models as om
from tests.assessment.test_matrix import add_run, requirement  # noqa: F401
from tests.assessment.test_technical_report import (  # noqa: F401  (fixtures y ayudas)
    FULL,
    PENDING,
    model,
    offers,
    read_queue,
    report_pdf,
)
from tests.journey.conftest import simulate  # noqa: F401  (fixture)
from tests.journey.temas.test_s4_propuesta import log_in, notice, page, tab

pytestmark = pytest.mark.django_db


_FULL_PDF = []


def pdf(name="informe.pdf", data=None):
    """El mismo informe cada vez (el PDF generado cambia de un armado al otro)."""
    if data is None:
        if not _FULL_PDF:
            _FULL_PDF.append(report_pdf(*FULL))
        data = _FULL_PDF[0]
    return SimpleUploadedFile(name, data)


def post_upload(client, procedure, offer=None, **extra):
    data = {"file": pdf(**extra)}
    if offer is not None:
        data["offer"] = offer.pk
    return client.post(reverse("expedientes:s4_informe_subir", args=[procedure.pk]), data)


def informe_block(html):
    """Solo el bloque del informe técnico de la pestaña."""
    return html.split('id="s4-informe"', 1)[1]


def tab_view(client, procedure, user):
    client.logout()
    log_in(client, user)
    return page(client, procedure)


def url(name, procedure, offer):
    return reverse(f"expedientes:{name}", args=[procedure.pk, offer.pk])


# --- Subir el informe ----------------------------------------------------------------------------


def test_the_header_upload_button_leads_to_the_report_upload_of_this_tab(
        client, offers, procedure, evaluator_user):
    """REQ-097: «Subir archivo» del encabezado de la sección lleva a la subida del informe en
    esta misma pestaña, y el ancla existe."""
    section = sections_for(evaluator_user, procedure).get("evaluacion")
    assert section.upload_url == tab(procedure) + "#s4-informe"
    log_in(client, evaluator_user)
    html = page(client, procedure)
    assert f'href="{section.upload_url}"' in html and 'id="s4-informe"' in html
    assert 'id="s4-informe-subir"' in html and "Subir informe técnico" in html


def test_the_report_is_uploaded_from_the_tab_for_the_procedure_or_for_one_offer(
        client, offers, procedure, evaluator_user, model):
    """REQ-089: el informe se sube desde la sección, por procedimiento (se carga en cada
    oferta) o por oferta; la pestaña vuelve con el aviso y la oferta lo muestra."""
    a, b = offers
    log_in(client, evaluator_user)
    ok, text = notice(client, post_upload(client, procedure, a))
    assert ok and f"la oferta {a.number}" in text
    assert len(report.reports_of(a)) == 1 and not report.reports_of(b)
    ok, text = notice(client, post_upload(client, procedure))
    assert ok and "Ya lo tenían" in text and "todo el procedimiento" in text
    assert len(report.reports_of(a)) == 1 and len(report.reports_of(b)) == 1
    ok, text = notice(client, post_upload(client, procedure))
    assert not ok and "Todas las ofertas ya tienen este informe." in text
    html = informe_block(page(client, procedure))
    assert html.count("Informe técnico · informe") == 2  # el título del informe, en cada oferta
    assert report.reports_of(a)[0].kind == om.DocumentKind.INFORME_TECNICO


def test_uploading_from_the_tab_leaves_the_same_change_and_fact_as_the_old_route(
        client, offers, procedure, evaluator_user, model):
    """REQ-089, P6: subir desde la pestaña deja el mismo documento y el mismo hecho de
    auditoría que la ruta vieja de la matriz."""
    a, b = offers
    log_in(client, evaluator_user)
    sent = pdf().read()
    old = client.post(reverse("assessment:report_upload", args=[a.pk]),
                      {"file": SimpleUploadedFile("informe.pdf", sent), "note": "nota"})
    assert old.status_code == 302
    new = client.post(reverse("expedientes:s4_informe_subir", args=[procedure.pk]),
                      {"file": SimpleUploadedFile("informe.pdf", sent), "offer": b.pk,
                       "note": "nota"})
    assert new.status_code == 302
    (da,), (db,) = report.reports_of(a), report.reports_of(b)
    assert (da.kind, da.title, da.file_sha256, da.loaded_by) == \
        (db.kind, db.title, db.file_sha256, db.loaded_by)
    ea = AuditEvent.objects.get(event_type=EventType.EVAL_DECISION, detail__offer=a.pk,
                                detail__action="informe_tecnico")
    eb = AuditEvent.objects.get(event_type=EventType.EVAL_DECISION, detail__offer=b.pk,
                                detail__action="informe_tecnico")
    assert (ea.outcome, ea.channel, ea.user) == (eb.outcome, eb.channel, eb.user)
    drop = ("offer", "document", "load_event")
    assert {k: v for k, v in ea.detail.items() if k not in drop} == \
        {k: v for k, v in eb.detail.items() if k not in drop}


def test_a_file_that_cannot_be_read_or_a_missing_one_comes_back_with_the_reason(
        client, offers, procedure, evaluator_user):
    """REQ-089: un archivo que no se acepta o la falta de archivo no cargan nada y la pestaña
    dice por qué."""
    log_in(client, evaluator_user)
    ok, text = notice(client, post_upload(client, procedure, name="i.txt", data=b"nada"))
    assert not ok and text
    response = client.post(reverse("expedientes:s4_informe_subir", args=[procedure.pk]), {})
    ok, text = notice(client, response)
    assert not ok and text
    assert not om.Document.objects.filter(kind=om.DocumentKind.INFORME_TECNICO).exists()


# --- Faltante, propuesta y cita -----------------------------------------------------------------


def test_an_offer_with_technical_rows_and_no_report_is_missing_with_its_button(
        client, offers, procedure, evaluator_user, operator_user, model):
    """REQ-097: la oferta con filas técnicas y sin informe figura como faltante de la sección,
    con su botón; al subirlo deja de faltar."""
    a, b = offers
    section = sections_for(operator_user, procedure).get("evaluacion")
    texts = [m.text for m in section.tema_missing if "informe técnico" in m.text]
    # T-231 (E-12): una sola vez por procedimiento, con las ofertas a las que falta.
    assert texts == [f"Falta el informe técnico del área (ofertas {a.number} y {b.number})"]
    missing = next(m for m in section.tema_missing if "informe técnico" in m.text)
    assert missing.url == tab(procedure) + "#s4-informe" and "informe técnico" in missing.action
    log_in(client, evaluator_user)
    html = informe_block(page(client, procedure))
    assert html.count("Falta el informe técnico del área") >= 2
    assert html.count('name="offer" value="') == 2  # el botón de cada oferta que falta
    notice(client, post_upload(client, procedure, a))
    section = sections_for(operator_user, procedure).get("evaluacion")
    texts = [m.text for m in section.tema_missing if "informe técnico" in m.text]
    assert texts == [f"Falta el informe técnico del área (oferta {b.number})"]


def test_the_tab_shows_the_proposal_per_item_with_the_quote_of_the_report(
        client, offers, procedure, evaluator_user, operator_user, model):
    """REQ-089, P3: leído el informe, la pestaña muestra apto o no apto por renglón y oferta
    con la frase del informe y su página, y dice cuando el informe no trata un renglón."""
    a, b = offers
    log_in(client, evaluator_user)
    sent = report_pdf(*FULL[:5])  # el informe no trata el renglón 3 de la oferta B
    notice(client, post_upload(client, procedure, data=sent))
    read_queue()
    html = informe_block(page(client, procedure))
    assert "Apto, propuesto" in html and "No apto, propuesto" in html
    assert FULL[4] in html and "página 1" in html  # la frase y su página
    assert "El informe no trata este renglón de esta oferta." in html
    # El operador ve lo mismo, sin botones.
    html = informe_block(tab_view(client, procedure, operator_user))
    assert "No apto, propuesto" in html and FULL[4] in html


def test_ask_again_proposes_from_the_read_report(
        client, offers, procedure, evaluator_user, model):
    """REQ-089: «Proponer de nuevo desde el informe» vuelve a la pestaña con el aviso y deja la
    propuesta; sin informe la pestaña dice por qué."""
    a, _ = offers
    log_in(client, evaluator_user)
    ok, text = notice(client, client.post(url("s4_informe_proponer", procedure, a)))
    assert not ok and "todavía no tiene informe técnico" in text
    model.fail = True
    notice(client, post_upload(client, procedure, a, data=report_pdf(*FULL[:3])))
    read_queue()
    model.fail = False
    assert technical.proposals_of(a) == {}
    assert "Proponer de nuevo desde el informe" in page(client, procedure)
    ok, _ = notice(client, client.post(url("s4_informe_proponer", procedure, a)))
    assert ok
    assert {i: p.verdict for i, p in technical.proposals_of(a).items()} == \
        {1: "apto", 2: "apto", 3: "apto"}


# --- El ok ---------------------------------------------------------------------------------------


def give_data(verdicts):
    return {f"verdict_{i}": v for i, v in verdicts.items()}


def test_giving_the_ok_from_the_tab_leaves_the_same_change_and_fact_as_the_old_route(
        client, offers, procedure, evaluator_user, model):
    """REQ-089, P6: dar el ok desde la pestaña deja el mismo ok, los mismos resultados y el
    mismo hecho de auditoría que la ruta vieja de la matriz."""
    a, b = offers
    log_in(client, evaluator_user)
    notice(client, post_upload(client, procedure, data=report_pdf(*FULL)))
    read_queue()
    chosen = {1: "apto", 2: "no_apto", 3: "apto"}
    old = client.post(reverse("assessment:technical_give", args=[a.pk]),
                      {"all": "1", "note": "ok", **give_data(chosen)})
    assert old.status_code == 302
    ok, text = notice(client, client.post(url("s4_informe_ok", procedure, b),
                                          {"note": "ok", **give_data(chosen)}))
    assert ok and "Quedó registrado quién y cuándo" in text
    oa, ob = (am.TechnicalOk.objects.get(offer=o) for o in (a, b))
    assert (oa.items, oa.verdicts, oa.action, oa.note, oa.user) == \
        (ob.items, ob.verdicts, ob.action, ob.note, ob.user)
    ea, eb = oa.event, ob.event
    assert (ea.event_type, ea.outcome, ea.channel) == (eb.event_type, eb.outcome, eb.channel)
    for key in ("kind", "action", "items", "verdicts", "note", "user", "changed", "skipped"):
        assert ea.detail[key] == eb.detail[key], key
    for item in (1, 2, 3):
        rows_a, rows_b = technical.item_rows(a)[item], technical.item_rows(b)[item]
        assert evaluate.current_result(a, rows_a).outcome == \
            evaluate.current_result(b, rows_b).outcome == \
            {"apto": "cumple", "no_apto": "no_cumple"}[chosen[item]]


def test_the_ok_needs_a_verdict_per_item_and_nothing_changes_without_it(
        client, offers, procedure, evaluator_user, model):
    """REQ-089: sin apto o no apto en todos los renglones, el ok no se da; la pestaña vuelve con
    el motivo y no queda ningún ok."""
    a, _ = offers
    log_in(client, evaluator_user)
    ok, text = notice(client, client.post(url("s4_informe_ok", procedure, a),
                                          give_data({1: "apto", 2: "", 3: "apto"})))
    assert not ok and "renglón 2" in text
    assert not am.TechnicalOk.objects.exists()


def test_the_ok_is_shown_with_who_and_when_in_local_time_and_can_be_withdrawn(
        client, offers, procedure, evaluator_user, model):
    """REQ-089: el ok dado figura con quién y cuándo en hora local; retirarlo exige el motivo,
    queda registrado y las filas vuelven a pendientes."""
    a, _ = offers
    log_in(client, evaluator_user)
    notice(client, post_upload(client, procedure, a, data=report_pdf(*FULL[:3])))
    read_queue()
    ok, _ = notice(client, client.post(url("s4_informe_ok", procedure, a),
                                       give_data({1: "apto", 2: "apto", 3: "apto"})))
    assert ok
    given = am.TechnicalOk.objects.get(offer=a)
    html = informe_block(page(client, procedure))
    local = s4_informe.when(given.at)
    assert f"Ok de {evaluator_user.username} el {local}" in html
    utc = f"{given.at:%d/%m/%Y %H:%M}"
    assert utc == local or f"el {utc}" not in html
    assert "Apto: ok de la Comisión" in html
    assert "Retirar el ok" in html and "Dar el ok a la propuesta del informe" not in html
    withdraw = url("s4_informe_retirar", procedure, a)
    ok, text = notice(client, client.post(withdraw, {"note": "  "}))
    assert not ok and "motivo" in text.lower()
    assert am.TechnicalOk.objects.filter(offer=a).count() == 1
    ok, _ = notice(client, client.post(withdraw, {"note": "El área corrigió el informe."}))
    assert ok
    last = am.TechnicalOk.objects.filter(offer=a).order_by("-pk").first()
    assert last.action == "retirar_ok" and last.note == "El área corrigió el informe."
    fact = AuditEvent.objects.get(pk=last.event_id)
    assert fact.event_type == EventType.EVAL_DECISION and fact.outcome == AuditOutcome.OK
    row = technical.item_rows(a)[1]
    assert evaluate.current_result(a, row).doubt == "pendiente_informe_tecnico"


# --- Rol -----------------------------------------------------------------------------------------


def test_the_operator_sees_no_buttons_and_every_post_is_denied_and_audited(
        client, offers, procedure, evaluator_user, operator_user, model):
    """REQ-089, P3: el operador ve el estado y no los botones; cada POST suyo es 403, con el
    rechazo registrado, y no cambia nada."""
    a, _ = offers
    log_in(client, evaluator_user)
    notice(client, post_upload(client, procedure, a, data=report_pdf(*FULL[:3])))
    read_queue()
    before_docs = om.Document.objects.count()
    html = informe_block(tab_view(client, procedure, operator_user))
    for text in ("Dar el ok a la propuesta del informe", "Subir informe técnico",
                 "Proponer de nuevo desde el informe", 'id="s4-informe-subir"'):
        assert text not in html, text
    assert "Solo el evaluador de la Comisión sube el informe técnico" in html
    rejected_before = AuditEvent.objects.filter(outcome=AuditOutcome.REJECTED).count()
    posts = [
        client.post(reverse("expedientes:s4_informe_subir", args=[procedure.pk]),
                    {"file": pdf(), "offer": a.pk}),
        client.post(url("s4_informe_proponer", procedure, a)),
        client.post(url("s4_informe_ok", procedure, a),
                    give_data({1: "apto", 2: "apto", 3: "apto"})),
        client.post(url("s4_informe_retirar", procedure, a), {"note": "x"}),
    ]
    assert [r.status_code for r in posts] == [403, 403, 403, 403]
    assert AuditEvent.objects.filter(outcome=AuditOutcome.REJECTED).count() == \
        rejected_before + 4
    assert om.Document.objects.count() == before_docs and not am.TechnicalOk.objects.exists()


# --- Pendientes y cuentas ------------------------------------------------------------------------


def test_the_technical_ok_pending_is_listed_once_by_this_theme_and_sums_like_the_stage(
        client, offers, procedure, operator_user, evaluator_user):
    """REQ-097: el ok técnico pendiente figura una sola vez por oferta (en este tema, no en
    la propuesta) con enlace al ancla de la oferta, y la suma es la de la etapa."""
    a, b = offers
    stage = matriz_evaluacion.compute(operator_user, procedure)
    section = sections_for(operator_user, procedure).get("evaluacion")
    assert section.pending == len(section.pending_items) == stage.pending
    ok_items = [i for i in section.pending_items if "informe técnico" in i.text]
    assert len(ok_items) == 2
    assert {i.url for i in ok_items} == {tab(procedure) + f"#informe-oferta-{o.number}"
                                         for o in offers}
    assert all(i.text.startswith(("Oferta 1:", "Oferta 2:")) for i in ok_items)
    from evaluon.journey.temas import s4_propuesta
    assert not [i for i in s4_propuesta.status(operator_user, procedure).pending_items
                if "informe técnico" in i.text]
    assert len(s4_informe.status(operator_user, procedure).pending_items) == 2
    # Con el ok dado en una oferta, queda uno.
    technical.give_ok(evaluator_user, a, verdicts={1: "apto", 2: "apto", 3: "apto"})
    section = sections_for(operator_user, procedure).get("evaluacion")
    assert section.pending == len(section.pending_items) == \
        matriz_evaluacion.compute(operator_user, procedure).pending
    assert len([i for i in section.pending_items if "informe técnico" in i.text]) == 1


def test_the_block_has_the_mockup_titles_and_no_link_to_the_old_screens(
        client, offers, procedure, evaluator_user):
    """REQ-089/REQ-100: los títulos de la maqueta aprobada, ningún texto de ejemplo y ningún
    enlace ni formulario a las pantallas viejas."""
    log_in(client, evaluator_user)
    html = page(client, procedure)
    block = informe_block(html).split('id="s4-dictamen"', 1)[0]
    assert "Informe técnico del área requirente" in block
    assert "Propuesta apto o no apto por renglón" in block
    assert "IT-07/2026" not in block and "[texto de ejemplo]" not in block
    for old in (reverse("assessment:matrix", args=[procedure.pk]),
                reverse("assessment:technical_give", args=[offers[0].pk]),
                reverse("assessment:report_upload", args=[offers[0].pk])):
        assert f'"{old}' not in block and old not in block


def test_an_offer_of_another_procedure_is_not_found(client, offers, procedure, evaluator_user):
    """REQ-089: una oferta que no es del procedimiento da 404 y no cambia nada."""
    log_in(client, evaluator_user)
    response = client.post(reverse("expedientes:s4_informe_proponer", args=[procedure.pk, 99999]))
    assert response.status_code == 404
    response = client.post(reverse("expedientes:s4_informe_subir", args=[procedure.pk]),
                           {"file": pdf(), "offer": 99999})
    assert response.status_code == 404


def test_the_module_keys_are_the_registered_ones():
    """Plan 014: el tema es el de la sección «evaluacion»."""
    assert s4_informe.KEY == "s4_informe" and s4_informe.SECTION == "evaluacion"
    assert s4_informe.PARTIAL == "journey/temas/s4_informe.html"
    assert re.fullmatch(r"#s4-informe", s4_informe.ANCHOR)
    assert PENDING  # el estado de las filas del caso chico


def test_an_offer_without_report_says_to_upload_it_and_the_summary_counts_them_apart(
        client, offers, procedure, operator_user, evaluator_user, model):
    """REQ-097: sin informe el pendiente dice «falta subir el informe técnico» y lleva al
    formulario de esa oferta; con informe, «falta el ok». El resumen cuenta por separado y la
    suma no cambia."""
    a, b = offers
    log_in(client, evaluator_user)
    notice(client, post_upload(client, procedure, a))
    section = sections_for(operator_user, procedure).get("evaluacion")
    items = {i.text: i.url for i in section.pending_items if "informe técnico" in i.text}
    assert items == {
        f"Oferta {a.number}: falta el ok del informe técnico": tab(procedure) + "#s4-informe",
        f"Oferta {b.number}: falta subir el informe técnico":
            tab(procedure) + f"#informe-oferta-{b.number}"}
    html = page(client, procedure)
    assert f'id="informe-oferta-{b.number}"' in html
    stage = matriz_evaluacion.compute(operator_user, procedure)
    assert "1 oferta sin informe técnico" in stage.detail
    assert "1 oferta con el ok del informe técnico pendiente" in stage.detail
    assert section.pending == len(section.pending_items) == stage.pending
