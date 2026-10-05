"""Pantalla de la ficha con sus acciones de revisión (REQ-042, REQ-043; plan 008, "Pantalla";
T-132). Caso chico inventado; el modelo es un guion."""

import pytest
from django.urls import reverse
from django.utils import timezone

from evaluon.offers import models as om
from evaluon.offers.services import sheets
from evaluon.tenders import models as m
from tests.offers.conftest import pick
from tests.offers.test_screens import log_in, text_of

pytestmark = pytest.mark.django_db


@pytest.fixture
def sheet(offer, operator_user, script):
    script.choose(pick("Declaro bajo juramento", when="declaración jurada"))
    return sheets.build_sheet(offer, operator_user)


def entry_of(sheet):
    return sheet.entries.filter(outcome="encontrado").first()


def test_the_page_offers_the_actions_and_the_evaluator_confirms(
        client, sheet, operator_user, evaluator_user):
    """REQ-042: el operador ve las acciones pero no puede confirmar; el evaluador confirma y
    la fila queda confirmada."""
    url = reverse("offers:sheet", args=[sheet.pk])
    log_in(client, operator_user)
    page = text_of(client.get(url))
    assert "Quitar" in page and "Corregir, agregar e historial" in page
    assert "Confirmar las filas lo hace el evaluador" in page
    entry = entry_of(sheet)
    response = client.post(reverse("offers:confirm_entries", args=[sheet.pk]),
                           {"entry": [entry.pk]})
    assert response.status_code == 403
    entry.refresh_from_db()
    assert entry.state == "propuesto"
    client.logout()
    log_in(client, evaluator_user)
    assert "Confirmar las filas marcadas" in text_of(client.get(url))
    response = client.post(reverse("offers:confirm_entries", args=[sheet.pk]),
                           {"entry": [entry.pk]})
    assert response.status_code == 302
    entry.refresh_from_db()
    assert entry.state == "confirmado"
    assert "Confirmado" in text_of(client.get(url))


def test_remove_and_restore_from_the_page(client, sheet, operator_user):
    """REQ-042: quitar saca el fragmento de la fila y lo muestra entre los quitados."""
    log_in(client, operator_user)
    entry = entry_of(sheet)
    fragment = entry.fragments.get()
    response = client.post(reverse("offers:fragment_action", args=[fragment.pk, "quitar"]))
    assert response.status_code == 302
    page = text_of(client.get(reverse("offers:sheet", args=[sheet.pk])))
    assert "Quitados:" in page and "Restituir" in page
    assert f"Requisito {entry.requirement.number}:" in page.split("Páginas sin leer")[0]
    client.post(reverse("offers:fragment_action", args=[fragment.pk, "restituir"]))
    assert "Quitados:" not in text_of(client.get(reverse("offers:sheet", args=[sheet.pk])))
    assert client.post(reverse("offers:fragment_action",
                               args=[fragment.pk, "borrar"])).status_code == 404


def test_history_page_corrects_adds_and_shows_the_previous_fragment(
        client, sheet, operator_user):
    """REQ-042: la página de la fila corrige con recorte literal, rechaza uno que no está y
    muestra el fragmento anterior con su autor."""
    entry = entry_of(sheet)
    fragment = entry.fragments.get()
    original = fragment.text
    log_in(client, operator_user)
    url = reverse("offers:entry_history", args=[entry.pk])
    assert "Todavía no hay cambios" in text_of(client.get(url))
    action = reverse("offers:fragment_action", args=[fragment.pk, "corregir"])
    bad = client.post(action, {"passage": fragment.passage_id, "text": "no está",
                               "volver": "fila"})
    assert bad.status_code == 422 and "El recorte no está en el pasaje" in text_of(bad)
    ok = client.post(action, {"passage": fragment.passage_id,
                              "text": "habilitado para contratar", "volver": "fila"})
    assert ok.status_code == 302 and ok.url == url
    page = text_of(client.get(url))
    assert f"Antes: {original}" in page and "Después: habilitado para contratar" in page
    assert operator_user.username in page and "Corregir" in page
    passage = om.Passage.objects.get(text__startswith="Constancia de inscripción")
    client.post(reverse("offers:add_fragment", args=[entry.pk]),
                {"passage": passage.pk, "text": "", "volver": "fila"})
    assert entry.fragments.count() == 2
    assert "(agregado por una persona)" in text_of(
        client.get(reverse("offers:sheet", args=[sheet.pk])))


def test_the_missing_section_follows_the_changes(client, sheet, operator_user):
    """REQ-042: agregar un fragmento a lo que no se encontró lo saca de esa sección."""
    missing = sheet.entries.filter(outcome="no_encontrado").first()
    log_in(client, operator_user)
    url = reverse("offers:sheet", args=[sheet.pk])
    header = text_of(client.get(url)).split("Páginas sin leer")[0]
    assert f"Requisito {missing.requirement.number}:" in header
    passage = om.Passage.objects.get(text__startswith="Constancia de inscripción")
    client.post(reverse("offers:add_fragment", args=[missing.pk]), {"passage": passage.pk})
    header = text_of(client.get(url)).split("Páginas sin leer")[0]
    assert f"Requisito {missing.requirement.number}:" not in header


def test_the_version_notice_and_the_button_to_build_a_new_sheet(
        client, sheet, matrix, operator_user):
    """REQ-043: con la matriz v1 no hay aviso; al validarse la v2, "Armada con la versión 1;
    la versión vigente es la 2" y el botón arma una ficha nueva."""
    log_in(client, operator_user)
    url = reverse("offers:sheet", args=[sheet.pk])
    assert "la versión vigente es la" not in text_of(client.get(url))
    second = m.MatrixVersion.objects.create(procedure=matrix.procedure, number=2,
                                            created_by=operator_user)
    second.status = m.VersionStatus.VALIDATED
    second.validated_at, second.validated_by = timezone.now(), operator_user
    second.save()
    response = client.get(url)
    assert "Armada con la versión 1; la versión vigente es la 2" in text_of(response)
    build = reverse("offers:build_sheet", args=[sheet.offer_id])
    assert f'action="{build}"' in response.content.decode()
    assert "Armar una ficha nueva" in text_of(response)
    assert client.post(build).status_code == 302
    assert m.Job.objects.filter(kind=m.JobKind.BUILD_SHEET).count() == 1


def test_unknown_rows_and_users_without_role(client, sheet, no_commission_user,
                                             operator_user):
    """Sin rol de la Comisión, 403; filas y fragmentos inexistentes, 404."""
    entry = entry_of(sheet)
    log_in(client, no_commission_user)
    assert client.get(reverse("offers:entry_history", args=[entry.pk])).status_code == 403
    assert client.get(reverse("offers:sheet", args=[sheet.pk])).status_code == 403
    client.logout()
    log_in(client, operator_user)
    assert client.get(reverse("offers:entry_history", args=[9999])).status_code == 404
    assert client.post(reverse("offers:add_fragment", args=[9999])).status_code == 404
    assert client.post(reverse("offers:fragment_action",
                               args=[9999, "quitar"])).status_code == 404


def test_an_item_without_a_quote_in_sight_is_labeled_so_and_still_shows_its_fragment(
        client, procedure, operator_user, script):
    """REQ-044 (T-136): en la pantalla, un renglón con la hoja técnica y sin precio dice "sin
    cotización a la vista" y muestra el fragmento."""
    from tests.offers.conftest import make_offer

    offer = make_offer(procedure, operator_user, "Solo hoja", {
        "hoja.docx": ["Resma de papel A4, 75 g/m2, 500 hojas. Marca Ficticia."]},
        kinds={"hoja.docx": "tecnica"})
    script.choose(pick("Resma", quoted="sin_precio", when="RESMA"))
    built = sheets.build_sheet(offer, operator_user)
    log_in(client, operator_user)
    page = text_of(client.get(reverse("offers:sheet", args=[built.pk])))
    assert "sin cotización a la vista" in page
    assert "Resma de papel A4, 75 g/m2" in page
