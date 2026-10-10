"""Tema «lo que presentó cada oferta» (la ficha) de la sección Ofertas (REQ-086; plan 014, T-203).
La ficha se abre dentro de la pestaña y cada acción vuelve a la pestaña, con el mismo cambio y el
mismo hecho de auditoría que la pantalla vieja. Todo el material es inventado (P4)."""

import html as htmllib
import re

import pytest
from django.urls import reverse
from django.utils import timezone

from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.journey.sections import sections_for
from evaluon.journey.temas import s3_ficha
from evaluon.offers import models as om
from evaluon.offers.services import review, sheets
from evaluon.tenders.models import Job, JobKind
from tests.accounts.test_session import TEST_PASSWORD
from tests.offers.conftest import (  # noqa: F401  (fixtures)
    _no_minimum_rerank_score,
    make_offer,
    pick,
    script,
)

pytestmark = pytest.mark.django_db

JURADA = "Declaro bajo juramento"


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def url(name, procedure, *args):
    return reverse(f"expedientes:{name}", args=[procedure.pk, *args])


def tab(procedure, offer, query=""):
    return url("ofertas", procedure) + f"?ficha={offer.pk}{query}"


@pytest.fixture
def sheet(offer, operator_user, script):  # noqa: F811
    script.choose(pick(JURADA, when="declaración jurada"))
    return sheets.build_sheet(offer, operator_user)


def found_entry(sheet):
    return sheet.entries.filter(outcome="encontrado").first()


def missing_entry(sheet):
    return sheet.entries.filter(outcome="no_encontrado").first()


def block(html):
    """El bloque de la ficha dentro de la pestaña."""
    return html[html.index('class="ficha"'):]


def follow(client, response, offer):
    """La pestaña a la que vuelve la acción y el mensaje que muestra."""
    assert response.status_code == 302
    assert response["Location"].startswith(
        reverse("expedientes:ofertas", args=[offer.procedure_id]) + f"?ficha={offer.pk}")
    page = client.get(response["Location"])
    assert page.status_code == 200
    found = re.search(r'<p class="aviso (aviso-ok|aviso-error)"[^>]*>(.*?)</p>',
                      page.content.decode(), re.S)
    assert found, "la pestaña no muestra el mensaje de lo hecho"
    return found.group(1) == "aviso-ok", htmllib.unescape(found.group(2))


def fact(entry, action):
    """El hecho de auditoría y la fila de historial de una acción, sin lo propio de la fila."""
    change = entry.changes.filter(action=action).order_by("-pk").first()
    assert change is not None, f"falta el cambio {action}"
    event = change.event
    detail = {k: v for k, v in event.detail.items()
              if k not in ("entry", "requirement", "fragment", "before", "after")}
    return (event.event_type, event.outcome, event.channel, detail, change.action)


# --- Lo que se ve ----------------------------------------------------------------------------------


def test_every_requirement_shows_what_was_presented_and_the_fragment_or_not_found(
        client, procedure, offer, sheet, operator_user):
    """REQ-086: con una oferta leída, cada requisito muestra lo presentado y el fragmento
    (entre comillas, con documento y página), o «No se encontró en la oferta»; todo dentro de
    la pestaña, con «Volver a Ofertas»."""
    log_in(client, operator_user)
    page = client.get(tab(procedure, offer))
    assert page.status_code == 200
    html = block(page.content.decode())
    assert "← Volver a Ofertas" in html
    assert f'href="{url("ofertas", procedure)}"' in html
    rows = re.findall(r'<tr class="fila-req" id="fila-(\d+)"', html)
    assert len(rows) == sheet.entries.count() > 1
    fragment = found_entry(sheet).fragments.get()
    assert "Lo que ofrece el oferente." in html
    assert f"«{fragment.text[:60]}" in html
    assert f"{fragment.passage.reading.document.title}, pág. {fragment.passage.page}" in html
    assert html.count("No se encontró en la oferta") >= sheet.entries.filter(
        outcome="no_encontrado").count()
    assert "Esta oferta todavía no tiene ficha" not in html


def test_an_offer_without_a_sheet_shows_the_button_to_build_it(
        client, procedure, offer, operator_user):
    """REQ-086: la ficha es opcional; sin ficha la pestaña lo dice y ofrece armarla."""
    log_in(client, operator_user)
    html = block(client.get(tab(procedure, offer)).content.decode())
    assert "Esta oferta todavía no tiene ficha" in html
    assert url("s3_ficha_armar", procedure, offer.pk) in html


def test_the_tab_lists_the_offers_with_their_sheet_link(client, procedure, offer, sheet,
                                                         operator_user):
    """REQ-086: sin abrir una ficha, la tabla de ofertas (T-202) enlaza la ficha de cada una con
    «Ficha (opcional)»; la lista provisoria de T-203 ya no está."""
    log_in(client, operator_user)
    html = client.get(url("ofertas", procedure)).content.decode()
    table = html[html.index('id="s3-ofertas"'):]
    assert f'href="{tab(procedure, offer)}#s3-ficha"' in table
    assert "Ficha (opcional)" in table
    assert 'id="s3-fichas"' not in html


def test_no_link_of_the_tab_goes_to_an_old_decision_screen(client, procedure, offer, sheet,
                                                            evaluator_user):
    """REQ-086: ningún enlace ni formulario de la ficha sale de la pestaña hacia las pantallas
    viejas de decisión; solo el original del documento (un archivo)."""
    log_in(client, evaluator_user)
    html = block(client.get(tab(procedure, offer, f"&fila={found_entry(sheet).pk}"))
                 .content.decode())
    targets = re.findall(r'(?:href|action)="([^"]+)"', html)
    assert targets
    for target in (t for t in targets if not t.startswith("#")):
        assert (target.startswith(f"/expedientes/{procedure.pk}/") or "/original/" in target
                or target.startswith("/static/")), target
        assert "/fichas/" not in target and "/recorrido/" not in target, target


def test_dates_are_shown_in_local_time(client, procedure, offer, sheet, operator_user):
    """REQ-100: la fecha de armado sale en hora local."""
    log_in(client, operator_user)
    html = block(client.get(tab(procedure, offer)).content.decode())
    assert f"{timezone.localtime(sheet.built_at):%d/%m/%Y %H:%M}" in html


# --- Cuentas: pendientes y sugerencias, nunca faltantes ---------------------------------------------


def test_proposed_rows_are_pending_and_a_missing_sheet_is_not_a_missing_item(
        procedure, offer, sheet, operator_user):
    """REQ-086: las filas propuestas suman a los pendientes, con su enlace a la ficha dentro
    de la pestaña; la ficha no cuenta como faltante."""
    status = s3_ficha.status(operator_user, procedure)
    assert status.missing == ()
    assert sum(i.count for i in status.pending_items) == sheet.entries.count()
    assert all(i.url.startswith(f"/expedientes/{procedure.pk}/ofertas/")
               for i in status.pending_items)
    section = next(s for s in sections_for(operator_user, procedure).sections
                   if s.key == "ofertas")
    assert section.pending == sheet.entries.count()
    assert not [m for m in section.missing if "ficha" in m.text.lower()]


def test_confirmed_rows_stop_counting_and_an_offer_without_sheet_is_a_suggestion(
        procedure, offer, sheet, operator_user, evaluator_user):
    """REQ-086: confirmar baja los pendientes; la oferta sin ficha es una sugerencia (no
    obligatoria) con su enlace dentro de la pestaña."""
    review.confirm(evaluator_user, list(sheet.entries.values_list("pk", flat=True)))
    status = s3_ficha.status(operator_user, procedure)
    assert status.pending_items == () and status.suggestion_items == ()
    other = make_offer(procedure, operator_user, "Otro oferente", {"o.pdf": ["Texto."]})
    status = s3_ficha.status(operator_user, procedure)
    assert [i.count for i in status.suggestion_items] == [1]
    assert status.suggestion_items[0].url.startswith(
        f"/expedientes/{procedure.pk}/ofertas/?ficha={other.pk}")
    assert status.missing == ()


# --- Acciones: vuelven a la pestaña con el mismo cambio y el mismo hecho ----------------------------


def test_confirming_rows_does_the_same_as_the_old_screen(client, procedure, offer, sheet,
                                                          evaluator_user):
    """REQ-086: confirmar desde la ficha deja el mismo cambio y el mismo hecho que la pantalla
    vieja, y vuelve a la pestaña con el mensaje."""
    first, second = found_entry(sheet), missing_entry(sheet)
    log_in(client, evaluator_user)
    response = client.post(url("s3_ficha_confirmar", procedure, offer.pk),
                           {"entry": [first.pk]})
    ok, text = follow(client, response, offer)
    assert ok and "Se confirmó 1 fila" in text
    client.post(reverse("offers:confirm_entries", args=[sheet.pk]), {"entry": [second.pk]})
    first.refresh_from_db()
    assert first.state == "confirmado" and first.fragments.get().state == "confirmado"
    assert fact(first, "confirmar") == fact(second, "confirmar")


def test_the_operator_has_no_confirm_button_and_cannot_confirm(client, procedure, offer, sheet,
                                                                operator_user):
    """REQ-086: el operador no ve el botón de decisión; si lo manda igual, 403 con el rechazo
    registrado y sin cambio."""
    entry = found_entry(sheet)
    log_in(client, operator_user)
    html = block(client.get(tab(procedure, offer, f"&fila={entry.pk}")).content.decode())
    assert "Las confirma un evaluador" in html
    assert url("s3_ficha_confirmar", procedure, offer.pk) not in html
    response = client.post(url("s3_ficha_confirmar", procedure, offer.pk),
                           {"entry": [entry.pk]})
    assert response.status_code == 403
    entry.refresh_from_db()
    assert entry.state == "propuesto"
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).exists()


def test_removing_needs_a_motive_and_keeps_who_and_when_in_the_row(
        client, procedure, offer, sheet, operator_user):
    """REQ-086: quitar un fragmento exige motivo; sin él no cambia nada. Con motivo, queda el
    cambio, el hecho del servicio y un hecho propio con quién y cuándo, visible en la fila."""
    entry = found_entry(sheet)
    fragment = entry.fragments.get()
    log_in(client, operator_user)
    action = url("s3_ficha_fragmento", procedure, fragment.pk, "quitar")
    ok, text = follow(client, client.post(action, {"motive": "  "}), offer)
    assert not ok and "motivo" in text.lower()
    fragment.refresh_from_db()
    assert fragment.state == "propuesto"
    ok, text = follow(client, client.post(action, {"motive": "No es de este requisito"}),
                      offer)
    assert ok and "Se quitó el fragmento" in text
    fragment.refresh_from_db()
    assert fragment.state == "quitado"
    event = AuditEvent.objects.get(event_type=EventType.SHEET_CHANGE,
                                   detail__action="motivo", detail__entry=entry.pk)
    assert event.user == operator_user and event.detail["reason"] == "No es de este requisito"
    html = block(client.get(tab(procedure, offer)).content.decode())
    assert (f"Quitado por {operator_user.username} el "
            f"{timezone.localtime(event.occurred_at):%d/%m/%Y %H:%M} · motivo: "
            "No es de este requisito") in html
    assert "Restituir" in html


def test_removing_leaves_the_same_fact_as_the_old_screen(client, procedure, offer, sheet,
                                                          operator_user):
    """REQ-086: el quitar de la pestaña y el de la pantalla vieja dejan el mismo hecho."""
    entry = found_entry(sheet)
    fragment = entry.fragments.get()
    other_entry = missing_entry(sheet)
    other = om.Fragment.objects.create(
        entry=other_entry, order=1, passage=fragment.passage, char_start=fragment.char_start,
        char_end=fragment.char_end, text=fragment.text, origin="sistema", state="propuesto")
    log_in(client, operator_user)
    client.post(url("s3_ficha_fragmento", procedure, fragment.pk, "quitar"), {"motive": "x"})
    client.post(reverse("offers:fragment_action", args=[other.pk, "quitar"]))
    assert fact(entry, "quitar") == fact(other_entry, "quitar")


def test_restoring_a_removed_fragment(client, procedure, offer, sheet, operator_user):
    """REQ-086: un fragmento quitado se restituye desde la fila; la fila vuelve a propuesta."""
    fragment = found_entry(sheet).fragments.get()
    log_in(client, operator_user)
    client.post(url("s3_ficha_fragmento", procedure, fragment.pk, "quitar"), {"motive": "x"})
    ok, text = follow(client, client.post(
        url("s3_ficha_fragmento", procedure, fragment.pk, "restituir")), offer)
    assert ok and "Se restituyó" in text
    fragment.refresh_from_db()
    assert fragment.state == "propuesto"


def test_correcting_needs_a_motive_and_the_cut_must_be_literal(
        client, procedure, offer, sheet, operator_user):
    """REQ-086, P3: corregir exige motivo; el recorte debe estar en el pasaje (si no, el
    servicio lo rechaza y no cambia nada); con recorte válido, queda el motivo."""
    entry = found_entry(sheet)
    fragment = entry.fragments.get()
    log_in(client, operator_user)
    action = url("s3_ficha_fragmento", procedure, fragment.pk, "corregir")
    ok, text = follow(client, client.post(action, {"text": "habilitado para contratar"}), offer)
    assert not ok and "motivo" in text.lower()
    ok, text = follow(client, client.post(
        action, {"text": "habilitado para licitar", "motive": "Ajuste"}), offer)
    assert not ok and "recorte" in text.lower()
    assert not AuditEvent.objects.filter(detail__action="motivo").exists()
    ok, text = follow(client, client.post(
        action, {"text": "habilitado para contratar", "motive": "Ajuste"}), offer)
    assert ok and "Se corrigió el fragmento" in text
    fragment.refresh_from_db()
    assert fragment.text == "habilitado para contratar"
    assert AuditEvent.objects.filter(detail__action="motivo", detail__of="corregir",
                                     detail__entry=entry.pk).count() == 1


def test_adding_a_fragment_to_a_row_that_was_not_found(client, procedure, offer, sheet,
                                                        operator_user):
    """REQ-086: a una fila «no se encontró» se le agrega un fragmento de un pasaje de la
    oferta; pasa a encontrada y queda el cambio con quién y cuándo."""
    entry = missing_entry(sheet)
    passage = om.Passage.objects.filter(reading__document__offer=offer).first()
    log_in(client, operator_user)
    html = block(client.get(tab(procedure, offer, f"&fila={entry.pk}")).content.decode())
    assert url("s3_ficha_agregar", procedure, entry.pk) in html
    ok, text = follow(client, client.post(
        url("s3_ficha_agregar", procedure, entry.pk), {"passage": passage.pk}), offer)
    assert ok and "Se agregó el fragmento" in text
    entry.refresh_from_db()
    assert entry.outcome == "encontrado"
    assert entry.changes.get(action="agregar").user == operator_user


def test_a_refused_add_comes_back_to_the_tab_with_the_reason(client, procedure, offer, sheet,
                                                              operator_user):
    """REQ-086: un pasaje que no es de la oferta se rechaza y el motivo se ve en la pestaña."""
    entry = missing_entry(sheet)
    log_in(client, operator_user)
    ok, text = follow(client, client.post(
        url("s3_ficha_agregar", procedure, entry.pk), {"passage": "999999"}), offer)
    assert not ok and "pasaje" in text.lower()
    assert om.Change.objects.filter(entry=entry).count() == 0


def test_building_the_sheet_from_the_tab_queues_the_same_request(
        client, procedure, offer, operator_user):
    """REQ-086: «Armar la ficha» pide lo mismo que la pantalla vieja (un pedido y su hecho) y
    vuelve a la pestaña con el aviso."""
    log_in(client, operator_user)
    ok, text = follow(client, client.post(url("s3_ficha_armar", procedure, offer.pk)), offer)
    assert ok and "Se pidió la ficha" in text
    assert Job.objects.filter(kind=JobKind.BUILD_SHEET, target_id=offer.pk).count() == 1
    event = AuditEvent.objects.get(event_type=EventType.SHEET_REQUEST, outcome=Outcome.OK)
    assert event.detail["offer"] == offer.pk
    ok, text = follow(client, client.post(url("s3_ficha_armar", procedure, offer.pk)), offer)
    assert not ok and "en espera o en curso" in text


def test_an_action_on_something_that_is_not_of_the_procedure_is_not_found(
        client, procedure, offer, sheet, operator_user):
    """REQ-086: una fila de otro procedimiento (dirección de otro número) da 404."""
    entry = found_entry(sheet)
    log_in(client, operator_user)
    wrong = reverse("expedientes:s3_ficha_agregar", args=[procedure.pk + 1000, entry.pk])
    assert client.post(wrong, {"passage": 1}).status_code == 404


def test_the_summary_line_of_the_tab_starts_with_a_capital(client, procedure, offer, sheet,
                                                            operator_user):
    """REQ-100: la línea de resumen de la pestaña empieza con mayúscula."""
    log_in(client, operator_user)
    html = client.get(url("ofertas", procedure)).content.decode()
    text = re.search(r'id="seccion-resumen">\s*(.*?)</p>', html, re.S).group(1).strip()
    assert "de la ficha por confirmar" in text
    assert text[0].isupper()
    assert "Oferta 1 (" in text
