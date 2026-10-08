"""Acciones de la Comisión sobre la matriz, desde la pestaña «Pliego y matriz» (REQ-081, REQ-082;
plan 014, T-201). Cada acción desde la fila deja el mismo cambio y el mismo hecho de auditoría que
la pantalla vieja. Todo el material es inventado (P4)."""

import html as htmllib
import re

import pytest
from django.urls import reverse
from django.utils import timezone

from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.journey.temas import s2_matriz_acciones as acciones
from evaluon.tenders import models as m
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.temas.test_s2_matriz import two_versions  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def tab(procedure):
    return reverse("expedientes:pliego", args=[procedure.pk])


def url(name, procedure, *args):
    return reverse(f"expedientes:{name}", args=[procedure.pk, *args])


def segments_of(version):
    return list(m.Segment.objects.filter(
        reading__document__procedure_id=version.procedure_id).order_by("pk"))


def make_suggestion(version, segment):
    number = version.requirements.order_by("-number").first().number + 1
    requirement = m.Requirement.objects.create(
        version=version, number=number, category="formal", items=[], origin="propuesto",
        state="sugerido", proposed={}, passes=[], doubt_reason="duda",
        doubt={"answers": ["a", "b"], "evidence": "indicio"})
    m.RequirementQuote.objects.create(
        requirement=requirement, order=1, segment=segment, char_start=segment.char_start,
        char_end=segment.char_start + 6,
        text=segment.reading.canonical_text[segment.char_start:segment.char_start + 6],
        scope="", quote_flag="")
    return requirement


@pytest.fixture
def board(procedure, two_versions):  # noqa: F811
    """El borrador (versión 2) con tres sin confirmar, una sugerencia y un tramo por revisar."""
    draft, numbers = two_versions
    segments = segments_of(draft)
    suggestion = make_suggestion(draft, segments[0])
    pending = m.PendingItem.objects.create(version=draft, segment=segments[1],
                                           reason="sin_disposicion")
    rows = [draft.requirements.get(number=n) for n in numbers]
    return type("Board", (), {"draft": draft, "rows": rows, "suggestion": suggestion,
                              "pending": pending, "segments": segments})


def follow(client, response):
    """La pestaña a la que vuelve la acción y el mensaje que muestra."""
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("expedientes:pliego", args=[
        int(re.search(r"/(\d+)/pliego/", response["Location"]).group(1))]))
    page = client.get(response["Location"])
    assert page.status_code == 200
    found = re.search(r'<p class="aviso (aviso-ok|aviso-error)"[^>]*>(.*?)</p>',
                      page.content.decode(), re.S)
    assert found, "la pestaña no muestra el mensaje de lo hecho"
    return found.group(1) == "aviso-ok", htmllib.unescape(found.group(2))


def fact(requirement, action):
    """El hecho de auditoría y la fila de historial de una acción, sin lo propio de la fila."""
    change = requirement.changes.filter(action=action).order_by("-pk").first()
    assert change is not None, f"falta el cambio {action}"
    event = change.event
    detail = {k: v for k, v in event.detail.items()
              if k not in ("requirement", "number", "version")}
    return (event.event_type, event.outcome, event.channel, detail, change.before,
            change.after)


def last_motive(requirement):
    return AuditEvent.objects.filter(event_type=EventType.REQUIREMENT_CHANGE,
                                     detail__action="motivo",
                                     detail__requirement=requirement.pk).last()


# --- Confirmar ------------------------------------------------------------------------------------


def test_confirming_from_the_row_does_the_same_as_the_old_screen(
        client, procedure, board, evaluator_user):
    """REQ-081: confirmar desde la fila deja el mismo cambio y el mismo hecho que la pantalla
    vieja, y vuelve a la pestaña con el mensaje."""
    first, second = board.rows[:2]
    log_in(client, evaluator_user)
    response = client.post(url("s2_confirmar", procedure), {"requirement": [first.pk]})
    ok, text = follow(client, response)
    assert ok and f"confirmó el requisito {first.number}" in text
    client.post(reverse("tenders:review_confirm", args=[board.draft.pk]),
                {"requirement": [second.pk]})
    first.refresh_from_db()
    assert first.state == "confirmado"
    assert fact(first, "confirmar") == fact(second, "confirmar")


def test_confirming_a_group_and_all_the_unconfirmed(client, procedure, board, evaluator_user):
    """REQ-081: «confirmar los N» confirma todos los marcados, uno por uno, con su hecho."""
    log_in(client, evaluator_user)
    response = client.post(url("s2_confirmar", procedure),
                           {"requirement": [r.pk for r in board.rows]})
    ok, text = follow(client, response)
    assert ok and "Se confirmaron 3 requisitos" in text
    assert all(m.Requirement.objects.get(pk=r.pk).state == "confirmado" for r in board.rows)
    assert AuditEvent.objects.filter(event_type=EventType.REQUIREMENT_CHANGE,
                                     detail__action="confirmar",
                                     detail__requirement__in=[r.pk for r in board.rows]
                                     ).count() == 3


# --- Corregir y quitar con motivo -----------------------------------------------------------------


def edit_form(row):
    quote = row.quotes.order_by("order").first()
    return {"category": "economico" if row.category == "formal" else "formal",
            "items": "", "segment": quote.segment_id, "quote": quote.text}


def test_correcting_needs_a_motive_and_records_who_and_when(
        client, procedure, board, evaluator_user):
    """REQ-081: corregir pide un motivo; sin motivo no cambia nada; con motivo queda el mismo
    cambio que en la pantalla vieja más el motivo, con quién y cuándo."""
    row, other = [r for r in board.rows if r.category in ("formal", "economico")][:2]
    log_in(client, evaluator_user)
    before = m.Requirement.objects.get(pk=row.pk).category
    refused = client.post(url("s2_corregir", procedure, row.pk), edit_form(row))
    ok, text = follow(client, refused)
    assert not ok and "motivo" in text
    assert m.Requirement.objects.get(pk=row.pk).category == before
    assert not row.changes.filter(action="corregir").exists()

    response = client.post(url("s2_corregir", procedure, row.pk),
                           {**edit_form(row), "motive": "El pliego lo trata como económico."})
    ok, text = follow(client, response)
    assert ok and f"corrigió el requisito {row.number}" in text
    assert m.Requirement.objects.get(pk=row.pk).category != before
    client.post(reverse("tenders:review_correct", args=[other.pk]), edit_form(other))
    assert fact(row, "corregir")[:3] == fact(other, "corregir")[:3]
    motive = last_motive(row)
    assert motive.user == evaluator_user and motive.occurred_at <= timezone.now()
    assert motive.detail["reason"] == "El pliego lo trata como económico."


def test_removing_and_restoring(client, procedure, board, evaluator_user):
    """REQ-081: quitar pide motivo, no borra; restituir lo devuelve; mismo cambio que la vieja."""
    row, other = board.rows[:2]
    log_in(client, evaluator_user)
    ok, text = follow(client, client.post(url("s2_quitar", procedure, row.pk), {}))
    assert not ok and m.Requirement.objects.get(pk=row.pk).state == "propuesto"
    ok, text = follow(client, client.post(url("s2_quitar", procedure, row.pk),
                                          {"motive": "Duplica el requisito 3."}))
    assert ok and m.Requirement.objects.get(pk=row.pk).state == "quitado"
    client.post(reverse("tenders:review_remove", args=[other.pk]))
    assert fact(row, "quitar") == fact(other, "quitar")
    assert last_motive(row).detail["reason"] == "Duplica el requisito 3."
    html = client.get(tab(procedure)).content.decode()
    assert 'id="s2-quitados"' in html and "Restituir" in html

    ok, text = follow(client, client.post(url("s2_restituir", procedure, row.pk)))
    assert ok and m.Requirement.objects.get(pk=row.pk).state == "propuesto"
    client.post(reverse("tenders:review_restore", args=[other.pk]))
    assert fact(row, "restituir") == fact(other, "restituir")


# --- Agregar --------------------------------------------------------------------------------------


def test_adding_a_requirement_from_a_clause_without_typing_the_quote(
        client, procedure, board, evaluator_user):
    """REQ-081: agregar toma la cita literal del tramo elegido; mismo hecho que la vieja."""
    segment = next(s for s in board.segments if len(s.text) > 30)
    log_in(client, evaluator_user)
    form = {"segment": segment.pk, "category": "formal", "items": ""}
    ok, text = follow(client, client.post(url("s2_agregar", procedure), form))
    assert ok and "Se agregó el requisito" in text
    new = board.draft.requirements.order_by("-number").first()
    assert new.origin == "agregado" and new.state == "propuesto"
    assert new.quotes.get().text.strip() == segment.text.strip()
    client.post(reverse("tenders:review_add", args=[board.draft.pk]),
                {**form, "quote": segment.text})
    old = board.draft.requirements.order_by("-number").first()
    assert old.pk != new.pk
    assert fact(new, "agregar") == fact(old, "agregar")


def test_adding_a_technical_row(client, procedure, board, evaluator_user):
    """REQ-081: la fila técnica de un renglón se agrega desde un tramo."""
    log_in(client, evaluator_user)
    row = board.draft.requirements.filter(category="tecnico").exclude(state="quitado").first()
    assert row is not None, "el caso chico trae filas técnicas"
    item = row.items[0]
    refused = follow(client, client.post(url("s2_agregar_tecnico", procedure), {
        "item": item, "segment": board.segments[0].pk}))
    assert not refused[0]  # ese renglón ya tiene su fila
    # Un renglón sin fila: la fila de antes queda sin renglón (arreglo del caso de prueba).
    m.Requirement.objects.filter(pk=row.pk).update(items=[])
    ok, text = follow(client, client.post(url("s2_agregar_tecnico", procedure), {
        "item": item, "segment": board.segments[0].pk}))
    assert ok, text
    new = board.draft.requirements.filter(category="tecnico", items=[item]).exclude(
        state="quitado").get()
    assert new.pk != row.pk and new.state == "propuesto"


# --- Sugerencias y tramos -------------------------------------------------------------------------


def test_suggestions_and_segments_are_decided_in_the_block(
        client, procedure, board, evaluator_user):
    """REQ-081: pasar a requisito, quitar y marcar revisado, con el mismo hecho que la vieja."""
    html = client.get(tab(procedure)).content.decode() if client.login(
        username=evaluator_user.username, password=TEST_PASSWORD) else ""
    assert 'id="s2-decidir"' in html and 'id="decidir-cta">2<' in html
    assert "Pasar a requisito" in html and "Marcar revisado" in html
    suggestion = board.suggestion
    ok, text = follow(client, client.post(url("s2_sugerencia_pasar", procedure,
                                              suggestion.pk)))
    assert ok and m.Requirement.objects.get(pk=suggestion.pk).state == "propuesto"
    other = make_suggestion(board.draft, board.segments[2])
    client.post(reverse("tenders:suggestion_accept", args=[other.pk]))
    assert fact(suggestion, "aceptar_sugerencia") == fact(other, "aceptar_sugerencia")

    third = make_suggestion(board.draft, board.segments[3])
    ok, _ = follow(client, client.post(url("s2_sugerencia_quitar", procedure, third.pk)))
    assert ok and m.Requirement.objects.get(pk=third.pk).state == "quitado"

    ok, _ = follow(client, client.post(url("s2_tramo_revisado", procedure,
                                           board.pending.pk)))
    board.pending.refresh_from_db()
    assert ok and board.pending.resolution == "sin_requisitos"
    assert board.pending.resolved_by == evaluator_user
    assert AuditEvent.objects.filter(event_type=EventType.SEGMENT_REVIEW).exists()


def test_a_requirement_added_from_a_segment_resolves_it(
        client, procedure, board, evaluator_user):
    """REQ-081: agregar un requisito desde un tramo pendiente lo resuelve."""
    log_in(client, evaluator_user)
    segment = board.pending.segment
    ok, _ = follow(client, client.post(url("s2_agregar", procedure), {
        "segment": segment.pk, "pending": board.pending.pk, "category": "formal"}))
    board.pending.refresh_from_db()
    assert ok and board.pending.resolution == "requisito_agregado"


# --- Consecuencia ---------------------------------------------------------------------------------


def test_choosing_the_consequence(client, procedure, board, evaluator_user):
    """REQ-081: elegir la consecuencia con motivo deja la elección, quién y cuándo."""
    row = board.rows[0]
    log_in(client, evaluator_user)
    ok, text = follow(client, client.post(url("s2_consecuencia", procedure, row.pk), {
        "consequence_type": "desestimacion", "note": "Lo dice el pliego."}))
    assert ok, text
    chosen = row.consequences.get(chosen=True)
    assert chosen.consequence_type == "desestimacion" and chosen.chosen_by == evaluator_user
    refused = client.post(url("s2_consecuencia", procedure, row.pk), {
        "consequence_type": "intimacion_subsanar"})
    ok, text = follow(client, refused)
    assert not ok and row.consequences.get(chosen=True) == chosen


# --- Validar y versión nueva ----------------------------------------------------------------------


def decide_everything(client, procedure, board):
    for row in board.draft.requirements.exclude(state__in=("quitado", "sugerido")):
        client.post(url("s2_consecuencia", procedure, row.pk), {
            "consequence_type": "desestimacion", "note": "Lo dice el pliego."})
    client.post(url("s2_confirmar", procedure), {"requirement": [r.pk for r in board.rows]})
    client.post(url("s2_sugerencia_quitar", procedure, board.suggestion.pk))
    client.post(url("s2_tramo_revisado", procedure, board.pending.pk))


def test_validation_waits_for_everything_to_be_decided(client, procedure, board,
                                                       evaluator_user):
    """REQ-081: no se valida mientras quede algo sin decidir; el botón queda apagado y al lado
    dice qué falta; con todo decidido se valida con quién y cuándo."""
    log_in(client, evaluator_user)
    html = client.get(tab(procedure)).content.decode()
    assert re.search(r'<button class="btn primario" id="validar"[^>]*\bdisabled\b', html)
    condition = re.search(r'id="cond-validar">(.*?)</p>', html, re.S).group(1)
    assert condition.startswith("Quedan 14 sin decidir: 3 requisitos sin confirmar, "
                                "1 sugerencia, 1 tramo, 9 consecuencias sin elegir."), condition
    assert f"Validar la versión {board.draft.number}" in html

    ok, text = follow(client, client.post(url("s2_validar", procedure, board.draft.pk)))
    board.draft.refresh_from_db()
    assert not ok and "Quedan 14 sin decidir" in text
    assert board.draft.status == "draft"
    assert not AuditEvent.objects.filter(event_type=EventType.MATRIX_VALIDATION,
                                         detail__version=board.draft.pk).exists()

    decide_everything(client, procedure, board)
    html = client.get(tab(procedure)).content.decode()
    assert not re.search(r'id="validar"[^>]*\bdisabled\b', html)
    assert "No queda nada sin decidir" in html
    ok, text = follow(client, client.post(url("s2_validar", procedure, board.draft.pk)))
    board.draft.refresh_from_db()
    assert ok and board.draft.status == "validated"
    assert board.draft.validated_by == evaluator_user and board.draft.validated_at
    event = AuditEvent.objects.get(event_type=EventType.MATRIX_VALIDATION,
                                   detail__version=board.draft.pk)
    assert event.outcome == Outcome.OK and event.user == evaluator_user


def test_after_validating_a_new_version_can_be_opened(client, procedure, board,
                                                      evaluator_user, operator_user):
    """REQ-082: la versión validada queda fija y se abre otra sin perder la anterior."""
    log_in(client, evaluator_user)
    decide_everything(client, procedure, board)
    client.post(url("s2_validar", procedure, board.draft.pk))
    html = client.get(tab(procedure)).content.decode()
    assert "Abrir una versión nueva" in html and 'id="validar"' not in html
    ok, text = follow(client, client.post(url("s2_nueva_version", procedure)))
    assert ok and "Se abrió la versión 3" in text
    assert procedure.matrix_versions.filter(number=3, status="draft").exists()
    assert procedure.matrix_versions.get(number=2).status == "validated"
    again = follow(client, client.post(url("s2_nueva_version", procedure)))
    assert not again[0]  # ya hay un borrador abierto


# --- El operador ----------------------------------------------------------------------------------


def test_the_operator_sees_no_decision_buttons(client, procedure, board, operator_user):
    """REQ-081: el operador ve que lo decide un evaluador, sin botones de decisión."""
    log_in(client, operator_user)
    html = client.get(tab(procedure)).content.decode()
    block = html[html.index('id="s2-decidir"'):html.index('id="s2-versiones"')]
    for label in ("Pasar a requisito", "Marcar revisado", "Confirmar", "Corregir", "Quitar",
                  "Validar la versión", "Agregar requisito", "Elegir la consecuencia",
                  "Abrir una versión nueva"):
        assert label not in block, label
    assert "Lo decide un evaluador" in block
    assert "<form" not in re.sub(r'<form[^>]*id="f-matriz".*?</form>', "", block, flags=re.S)


def test_the_operator_cannot_validate_or_confirm(client, procedure, board, operator_user):
    """REQ-081: aunque arme el pedido a mano, validar y confirmar le dan «acceso denegado» y
    queda el rechazo registrado; la versión no cambia."""
    log_in(client, operator_user)
    decide = [url("s2_validar", procedure, board.draft.pk),
              url("s2_confirmar", procedure)]
    for target in decide:
        response = client.post(target, {"requirement": [board.rows[0].pk]})
        assert response.status_code == 403
    board.draft.refresh_from_db()
    assert board.draft.status == "draft"
    assert m.Requirement.objects.get(pk=board.rows[0].pk).state == "propuesto"
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).count() >= 1


# --- Imprimir, exportar, límites ------------------------------------------------------------------


def test_print_and_pdf_answer_from_the_tab(client, procedure, board, evaluator_user):
    """REQ-082: la vista de impresión y el PDF responden 200 desde los enlaces de la pestaña."""
    log_in(client, evaluator_user)
    html = client.get(tab(procedure)).content.decode()
    print_url = reverse("tenders:print", args=[board.draft.pk])
    pdf_url = reverse("tenders:pdf", args=[board.draft.pk])
    assert f'href="{print_url}"' in html and f'href="{pdf_url}"' in html
    assert "Exportar a Excel" not in html
    assert client.get(print_url).status_code == 200
    response = client.get(pdf_url)
    assert response.status_code == 200 and response["Content-Type"] == "application/pdf"


def test_discarded_rows_and_coverage_are_linked(client, procedure, board, evaluator_user):
    """REQ-082: las filas descartadas por el sistema y la cobertura se alcanzan desde el pie."""
    log_in(client, evaluator_user)
    html = client.get(tab(procedure)).content.decode()
    assert reverse("tenders:discarded", args=[board.draft.pk]) in html
    assert client.get(reverse("tenders:discarded", args=[board.draft.pk])).status_code == 200


def test_a_requirement_of_another_procedure_is_not_found(client, procedure, board,
                                                         evaluator_user):
    """REQ-081: una acción sobre un requisito de otro procedimiento da 404 y no cambia nada."""
    log_in(client, evaluator_user)
    missing = reverse("expedientes:s2_confirmar", args=[999999])
    assert client.post(missing, {"requirement": [board.rows[0].pk]}).status_code == 404
    assert m.Requirement.objects.get(pk=board.rows[0].pk).state == "propuesto"


def test_the_message_is_signed_and_expires(client, procedure, board, evaluator_user):
    """REQ-081: un mensaje armado a mano en la dirección no se muestra."""
    log_in(client, evaluator_user)
    html = client.get(tab(procedure) + "?aviso=texto-falso").content.decode()
    assert 'class="aviso' not in html
    good = acciones.pack("Todo bien.")
    assert acciones.unpack(good) == {"ok": True, "text": "Todo bien."}
    assert acciones.unpack(good + "x") is None


def test_the_read_only_pages_still_work_for_a_validated_version(
        client, procedure, matrix, evaluator_user):
    """REQ-081: con la versión validada y sin borrador no hay botones de decisión, solo abrir
    una versión nueva para el evaluador."""
    log_in(client, evaluator_user)
    html = client.get(tab(procedure)).content.decode()
    assert "Abrir una versión nueva" in html
    for label in ("Validar la versión", "Confirmar los", "Quitar"):
        assert label not in html.split('id="s2-versiones"')[0].split('id="s2-matriz"')[1], label


def test_the_evaluator_sees_the_buttons_of_the_mockup(client, procedure, board, evaluator_user):
    """REQ-081: acciones en la fila que se abre, confirmar los N, agregar y validar al pie."""
    log_in(client, evaluator_user)
    html = client.get(tab(procedure)).content.decode()
    for label in ("Confirmar los 3 sin confirmar", "Agregar requisito desde el pliego",
                  "Agregar la fila técnica de un renglón", "Validar la versión 2",
                  "Corregir", "Quitar el requisito", "Elegir la consecuencia",
                  "Guardar la corrección"):
        assert label in html, label
    assert html.count("del grupo</button>") >= 1
    assert "Motivo (obligatorio)" in html and "required" in html


# --- Paneles de la pestaña, cuentas y texto llano --------------------------------------------------


def quedan(html):
    return int(re.search(r"Quedan (\d+) sin decidir", html).group(1))


def panel_counts(procedure, user):
    from evaluon.journey.sections import sections_for
    section = sections_for(user, procedure).get("pliego")
    return section.pending, section.suggestions


def test_the_panels_list_each_thing_with_a_link_to_this_tab(client, procedure, board,
                                                            evaluator_user):
    """REQ-098: cada cosa por decidir figura con su «Resolver» al ancla de esta pestaña, nunca a
    la pantalla vieja."""
    log_in(client, evaluator_user)
    html = client.get(tab(procedure)).content.decode()
    panels = html[html.index('id="pendientes"'):html.index('id="seccion-detalle"')]
    base = tab(procedure)
    for number in [r.number for r in board.rows]:
        assert f"Requisito {number} sin confirmar" in panels
        assert f'href="{base}#req-{number}"' in panels
    assert f"Tramo por revisar:" in panels and f'#tramo-{board.pending.pk}' in panels
    # Con más de 8 del mismo tipo se agrupan en una línea con su cuenta (T-222).
    assert ("Consecuencia sin elegir: requisito" in panels
            or "consecuencias sin elegir" in panels)
    assert f'href="{base}#sug-{board.suggestion.number}"' in panels
    assert "Resolver</a>" in panels
    assert "/procedimientos/matrices/" not in panels
    assert "Matriz de cumplimiento:" not in panels


def test_pending_plus_suggestions_always_match_what_is_left(client, procedure, board,
                                                            evaluator_user):
    """REQ-098: pendientes + sugerencias de la barra y del panel coinciden con «Quedan N»."""
    log_in(client, evaluator_user)

    def check():
        html = client.get(tab(procedure)).content.decode()
        pending, suggestions = panel_counts(procedure, evaluator_user)
        left = quedan(html) if "Quedan" in html else 0
        assert pending + suggestions == left
        panel = html[html.index('id="pendientes"'):html.index('id="sugerencias"')]
        assert f'<span class="cta">{pending}</span>' in panel
        return left

    assert check() == 14
    client.post(url("s2_confirmar", procedure), {"requirement": [board.rows[0].pk]})
    assert check() == 13
    client.post(url("s2_consecuencia", procedure, board.rows[0].pk), {
        "consequence_type": "desestimacion", "note": "Lo dice el pliego."})
    assert check() == 12
    client.post(url("s2_sugerencia_quitar", procedure, board.suggestion.pk))
    client.post(url("s2_tramo_revisado", procedure, board.pending.pk))
    assert check() == 10


def test_the_segment_reason_is_in_plain_words(client, procedure, board, evaluator_user):
    """REQ-100: sin jerga del modelo en el tramo por revisar."""
    log_in(client, evaluator_user)
    html = client.get(tab(procedure)).content.decode()
    assert "Sin disposición del modelo" not in html
    assert "El sistema no pudo decidir si este tramo contiene requisitos" in html


def test_the_suggestion_shows_the_whole_sentence(client, procedure, board, evaluator_user):
    """REQ-081: la sugerencia no se corta a mitad de palabra."""
    segment = max(board.segments, key=lambda s: len(s.text))
    long = make_suggestion(board.draft, segment)
    quote = long.quotes.get()
    text = segment.text.strip()
    m.RequirementQuote.objects.filter(pk=quote.pk).update(
        char_end=segment.char_start + len(segment.text), text=segment.text)
    log_in(client, evaluator_user)
    html = htmllib.unescape(client.get(tab(procedure)).content.decode())
    assert text in " ".join(html.split()) or " ".join(text.split()) in " ".join(html.split())


def test_the_motive_shows_in_the_open_row(client, procedure, board, evaluator_user):
    """REQ-081: el motivo de corregir o quitar se ve junto al cambio, con quién y cuándo."""
    row, other = board.rows[:2]
    log_in(client, evaluator_user)
    client.post(url("s2_quitar", procedure, other.pk), {"motive": "Duplica otro."})
    client.post(url("s2_restituir", procedure, other.pk))
    client.post(url("s2_corregir", procedure, row.pk),
                {**edit_form(row), "motive": "Es económico."})
    html = client.get(tab(procedure)).content.decode()
    assert re.search(r"Corregido por evaluador el \d\d/\d\d \d\d:\d\d · motivo: Es económico\.",
                     html)
    assert "Quitado por evaluador" in html and "motivo: Duplica otro." in html
