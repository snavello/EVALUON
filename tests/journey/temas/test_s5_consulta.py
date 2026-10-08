"""Tema «consulta de normativa» de la sección Normativas (REQ-096, REQ-097; plan 014, T-216).

La consulta corre con los dobles de los clientes de IA (`fake_ai`): no se usa el modelo real ni la
GPU. Las normas son sintéticas (P4)."""

import re

import pytest
from django.urls import reverse

from evaluon.audit.models import AuditEvent, EventType
from evaluon.queries.models import Query
from tests.conftest import TEST_PASSWORD
from tests.journey.conftest import procedure  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def tab(procedure):
    return reverse("expedientes:normativas", args=[procedure.pk])


def ask_url(procedure):
    return reverse("expedientes:s5_consultar", args=[procedure.pk])


@pytest.fixture
def regimes(two_regimes, procedure):  # noqa: F811
    """El procedimiento autorizado el 20/05/2024: rige el régimen «nuevo» de los de prueba."""
    procedure.authorization_date = two_regimes.after_v
    procedure.save(update_fields=["authorization_date"])
    return two_regimes


def ask(client, procedure, question="¿Cuál es el objeto del régimen?", **extra):
    return client.post(ask_url(procedure), {"question": question, **extra})


def answered(client, response):
    assert response.status_code == 302
    return client.get(response["Location"]).content.decode()


def test_the_tab_has_the_consultation_form_with_the_authorization_date(
        client, operator_user, procedure, regimes):
    """REQ-096: la pestaña trae la consulta con la fecha de autorización ya cargada, sin campo."""
    log_in(client, operator_user)
    html = client.get(tab(procedure)).content.decode()
    assert 'id="s5-consulta-form"' in html
    assert "Consulta de normativa" in html
    assert "20/05/2024" in html
    assert 'name="reference_date"' not in html
    block = html[html.index('id="s5-consulta"'):]
    assert 'action="/"' not in block and "/consultas/" not in block  # sin enlaces a la consulta global


def test_the_answer_shows_numbered_literal_citations_with_their_part(
        client, operator_user, procedure, regimes, fake_ai):
    """REQ-096: la respuesta lleva [1] con el texto literal de la cita y su parte."""
    unit = regimes.new_units["anexo/art-1"]
    literal = unit.reading.canonical_text[unit.char_start:unit.char_end]
    fake_ai.reranker.scores = {"OBJETO. Régimen sintético vigente": 0.9}
    log_in(client, operator_user)

    response = ask(client, procedure)
    html = answered(client, response)

    assert "Con fundamento" in html
    assert 'class="ref"' in html and "[1]" in html
    assert literal in html
    assert f"[1] {regimes.new.citation} · parte: {unit.path}" in html
    assert f"régimen aplicado: {regimes.new.citation}" in html
    query = Query.objects.get()
    assert query.reference_date == regimes.after_v  # la fecha del procedimiento, no la del día


def test_the_query_is_made_with_the_procedure_date_not_a_typed_one(
        client, operator_user, procedure, regimes, fake_ai):
    """REQ-096: aunque se envíe otra fecha, se consulta con la del procedimiento."""
    fake_ai.reranker.default = 0.9
    log_in(client, operator_user)
    ask(client, procedure, reference_date=regimes.before_v.isoformat())
    assert Query.objects.get().reference_date == regimes.after_v


def test_undetermined_is_said_in_plain_words(client, operator_user, procedure, regimes, fake_ai):
    """REQ-096: sin nada pertinente, la pestaña dice «No determinado», sin citas inventadas."""
    fake_ai.reranker.default = 0.0
    log_in(client, operator_user)

    html = answered(client, ask(client, procedure, "¿De qué color es el cielo?"))

    assert "No determinado" in html
    assert "nada pertinente" in html
    assert "<blockquote" not in html


def test_the_model_abstaining_is_not_determined(client, operator_user, procedure, regimes,
                                                fake_ai):
    """REQ-096: si el modelo se abstiene, queda «no determinado»."""
    fake_ai.reranker.default = 0.9
    fake_ai.generation.abstain()
    log_in(client, operator_user)

    html = answered(client, ask(client, procedure))

    assert "No determinado" in html
    assert "<blockquote" not in html


def test_a_technical_failure_is_said_and_can_be_asked_again(
        client, operator_user, procedure, regimes, fake_ai):
    """REQ-096: la falla técnica se dice en llano y la pestaña sigue lista para otra pregunta."""
    fake_ai.reranker.default = 0.9
    fake_ai.generation.unavailable()
    log_in(client, operator_user)

    html = answered(client, ask(client, procedure))

    assert "No se pudo completar la consulta" in html
    assert 'id="s5-consulta-form"' in html


def test_history_lists_this_procedures_queries_only_and_reopens_them(
        client, operator_user, procedure, regimes, fake_ai):
    """REQ-096: el historial muestra las consultas de este procedimiento, con fecha local, y cada
    una se vuelve a abrir sin consultar de nuevo."""
    fake_ai.reranker.default = 0.9
    log_in(client, operator_user)
    ask(client, procedure, "Primera pregunta sintética")
    ask(client, procedure, "Segunda pregunta sintética")
    calls = len(fake_ai.generation.calls)
    # Una consulta de la pantalla global no pertenece a ningún procedimiento.
    client.post("/", {"question": "Pregunta global", "reference_date": regimes.after_v.isoformat()})

    html = client.get(tab(procedure)).content.decode()
    history = html[html.index('id="s5-consulta-historial"'):]
    assert "Segunda pregunta sintética" in history and "Primera pregunta sintética" in history
    assert history.index("Segunda") < history.index("Primera")  # la más nueva primero
    assert "Pregunta global" not in history
    assert re.search(r"\d\d/\d\d/\d{4} \d\d:\d\d · Con fundamento", history)

    first = Query.objects.get(question="Primera pregunta sintética")
    reopened = client.get(f"{tab(procedure)}?consulta={first.pk}").content.decode()
    assert "Primera pregunta sintética" in reopened and 'id="s5-consulta-respuesta"' in reopened
    assert len(fake_ai.generation.calls) == calls + 1  # solo la global volvió a llamar al modelo


def test_each_query_leaves_its_link_to_the_procedure_in_the_audit_log(
        client, operator_user, procedure, regimes, fake_ai):
    """P6: la consulta deja su hecho `query` y el vínculo con el procedimiento."""
    fake_ai.reranker.default = 0.9
    log_in(client, operator_user)
    ask(client, procedure)
    query = Query.objects.get()
    link = AuditEvent.objects.get(event_type=EventType.QUERY,
                                  detail__kind="procedure_query")
    assert link.detail["query_id"] == query.pk and link.detail["procedure_id"] == procedure.pk
    assert link.user == operator_user


def test_nobody_sees_someone_elses_query(client, operator_user, evaluator_user, procedure, regimes,
                                         fake_ai):
    """REQ-096: como en la pantalla global, cada persona ve solo sus consultas."""
    fake_ai.reranker.default = 0.9
    log_in(client, operator_user)
    ask(client, procedure, "Pregunta del operador")
    query = Query.objects.get()
    client.logout()
    log_in(client, evaluator_user)
    html = client.get(f"{tab(procedure)}?consulta={query.pk}").content.decode()
    assert "Pregunta del operador" not in html


def test_an_empty_question_is_refused_with_a_notice(client, operator_user, procedure, regimes,
                                                    fake_ai):
    """REQ-096: sin pregunta no se consulta; la pestaña lo dice."""
    log_in(client, operator_user)
    response = ask(client, procedure, "   ")
    html = answered(client, response)
    assert "Escriba una pregunta." in html
    assert not Query.objects.exists() and not fake_ai.generation.calls


def test_without_a_commission_role_the_query_is_refused(client, no_commission_user, procedure,
                                                        regimes, fake_ai):
    """REQ-097: sin rol de la Comisión la pestaña lo explica y la acción se rechaza."""
    log_in(client, no_commission_user)
    assert ask(client, procedure).status_code == 403
    assert not Query.objects.exists()


def test_the_wait_is_shown_with_its_own_script(client, operator_user, procedure, regimes):
    """REQ-096: la espera de la consulta se muestra (estado y botón) con un script propio."""
    log_in(client, operator_user)
    html = client.get(tab(procedure)).content.decode()
    assert 'id="s5-consulta-espera"' in html and "Buscando en la normativa" in html
    assert "journey/s5_consulta.js" in html
    assert not re.search(r"<script(?![^>]*\bsrc=)", html)

