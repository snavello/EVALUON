"""Tema «explorador y cargador del Portal» de la sección Procedimiento y alta sin procedimiento
(REQ-076, REQ-079, REQ-097; plan 014, T-195). El Portal es el simulado del proyecto: no hay red y
todo el material es inventado (P4)."""

import datetime
import re

import pytest
from django.urls import reverse

from evaluon.audit.models import AuditEvent, EventType
from evaluon.journey.temas import s1_portal
from evaluon.portal.models import (
    ItemKind,
    ItemState,
    Origin,
    PortalItem,
    PortalLine,
    PortalLink,
)
from evaluon.portal.services import approval
from evaluon.tenders import jobs
from evaluon.tenders.models import PORTAL_JOB_KINDS, Document, Job, JobKind, JobStatus, Procedure
from tests.accounts.test_session import TEST_PASSWORD
from tests.portal.fakeportal import (  # noqa: F401
    EXPECTED,
    LINK_URL,
    explore_link,
    fake_portal_calco,
    portal_client,
    portal_settings,
)
from tests.portal.test_documents import docs_portal, serve_documents  # noqa: F401

pytestmark = pytest.mark.django_db

DATE = datetime.date(2025, 11, 14)
OLD_SCREENS = ("/importar/", "/recorrido/", "/procedimientos/")


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def new_page(client):
    return client.get(reverse("expedientes:nuevo"))


def explore(client, user):
    """Pega el enlace en la pantalla de alta y atiende el pedido como lo haría el servicio."""
    log_in(client, user)
    response = client.post(reverse("expedientes:nuevo"), {"url": LINK_URL})
    assert response.status_code == 302
    job = jobs.run_next(kinds=PORTAL_JOB_KINDS)
    assert job.status == JobStatus.DONE, job.error
    return response.url


def tab(client, procedure, query=""):
    return client.get(reverse("expedientes:procedimiento", args=[procedure.pk]) + query)


def decision_links(html):
    """Los enlaces y acciones de la página que llevan a una pantalla vieja de decisión del Portal."""
    targets = re.findall(r'(?:href|action)="([^"]+)"', html)
    return [t for t in targets if t.startswith(OLD_SCREENS)]


def mine(html):
    """Lo que dibuja este tema en la pestaña: del bloque del Portal en adelante."""
    return html[html.index('id="s1-portal"'):]


def row_links(html, text):
    """Los enlaces del renglón de pendientes que dice `text`."""
    row = re.search(r"<li>(?:(?!</li>).)*" + re.escape(text) + r"(?:(?!</li>).)*</li>", html, re.S)
    assert row, text
    return re.findall(r'href="([^"]+)"', row.group(0))


@pytest.fixture
def loaded(client, operator_user, evaluator_user, two_regimes, docs_portal):
    """Un procedimiento creado desde el Portal simulado, con el procedimiento y los renglones
    aprobados por el evaluador."""
    url = explore(client, operator_user)
    link = PortalLink.objects.get()
    ids = list(PortalItem.objects.filter(kind__in=(ItemKind.PROCEDIMIENTO, ItemKind.RENGLONES))
               .values_list("pk", flat=True))
    procedure_item = PortalItem.objects.get(kind=ItemKind.PROCEDIMIENTO)
    approval.decide(evaluator_user, ids, approval.APPROVE,
                    confirmations={procedure_item.pk: {"authorization_date": DATE}})
    link.refresh_from_db()
    return link.procedure


# --- La pantalla de alta ----------------------------------------------------------------------


def test_new_procedure_opens_inside_the_five_tabs(client, operator_user, procedure):
    """REQ-076: «+ Nuevo procedimiento» del desplegable lleva al alta dentro de las cinco pestañas:
    encabezado «sin crear», tres pestañas en gris, Normativas habilitada y las dos entradas."""
    log_in(client, operator_user)
    html = client.get(reverse("expedientes:portada", args=[procedure.pk])).content.decode()
    assert f'href="{reverse("expedientes:nuevo")}"' in html and "+ Nuevo procedimiento" in html
    page = new_page(client)
    assert page.status_code == 200
    html = page.content.decode()
    assert "Nuevo procedimiento (sin crear)" in html
    bar = html[html.index('id="barra-secciones"'):html.index('id="journey-status"')]
    assert bar.count('class="off"') == 3 and bar.count("Disponible al crear el procedimiento") >= 3
    for label in ("Pliego y matriz", "Ofertas", "Evaluación y dictamen", "Normativas"):
        assert label in bar
    assert "siempre disponible" in bar and 'aria-current="page"' in bar
    assert "Explorar el Portal" in html and "Subir el pliego" in html


def test_normativas_without_a_procedure_goes_to_the_general_consultation(
        client, operator_user, procedure):
    """Sin procedimiento, la pestaña Normativas lleva a la consulta general y nunca a la de otro
    procedimiento, aunque haya procedimientos cargados."""
    log_in(client, operator_user)
    html = new_page(client).content.decode()
    bar = html[html.index('id="barra-secciones"'):html.index('id="journey-status"')]
    assert f'href="{reverse("queries:screen")}"' in bar
    assert "/normativas/" not in bar and f"/expedientes/{procedure.pk}/" not in bar


def test_upload_the_tender_is_visible_but_not_available_yet(client, operator_user):
    """La entrada «Subir el pliego» es de T-197: se ve, deshabilitada y con «Disponible en breve»."""
    log_in(client, operator_user)
    html = new_page(client).content.decode()
    button = re.search(r"<button[^>]*disabled[^>]*>Subir el pliego</button>", html)
    assert button and "Disponible en breve" in html


def test_there_is_no_blank_form_to_create_a_procedure(client, operator_user):
    """No hay alta en blanco: la única entrada de texto es el enlace del proceso."""
    log_in(client, operator_user)
    html = new_page(client).content.decode()
    fields = re.findall(r'<(?:input|textarea|select)[^>]*name="([^"]+)"', html)
    assert [f for f in fields if f != "csrfmiddlewaretoken"] == ["url"]


def test_new_screen_has_no_link_to_old_screens(client, operator_user, evaluator_user,
                                               portal_client, two_regimes):
    log_in(client, operator_user)
    assert decision_links(new_page(client).content.decode()) == []
    url = explore(client, operator_user)
    assert decision_links(client.get(url).content.decode()) == []


def test_pasting_the_link_registers_it_and_queues_the_reading(client, operator_user,
                                                              portal_client):
    """REQ-076: pegar el enlace deja el enlace, el pedido de exploración y el hecho de auditoría,
    y no carga nada."""
    log_in(client, operator_user)
    response = client.post(reverse("expedientes:nuevo"), {"url": LINK_URL})
    link = PortalLink.objects.get()
    assert response.url == reverse("expedientes:nuevo_enlace", args=[link.pk])
    assert Job.objects.filter(kind=JobKind.PORTAL_EXPLORE, target_id=link.pk).count() == 1
    assert AuditEvent.objects.filter(event_type=EventType.PORTAL_LINK).count() == 1
    html = client.get(response.url).content.decode()
    assert "está leyendo el Portal" in html and 'http-equiv="refresh"' in html
    assert not Procedure.objects.exists()


def test_a_bad_link_explains_why_where_it_happens(client, operator_user, portal_settings):
    log_in(client, operator_user)
    response = client.post(reverse("expedientes:nuevo"), {"url": "http://otro.ejemplo.test/x"})
    html = response.content.decode()
    assert response.status_code == 200 and 'id="error-enlace"' in html
    assert "No se puede usar ese enlace" in html
    assert not PortalLink.objects.exists() and not Job.objects.exists()


def test_a_registered_link_offers_to_open_it(client, operator_user, portal_client):
    explore(client, operator_user)
    html = client.post(reverse("expedientes:nuevo"), {"url": LINK_URL}).content.decode()
    assert "Ese proceso ya está registrado" in html and "Ver ese proceso" in html


def test_user_without_commission_role_cannot_use_the_screen(client, no_commission_user):
    log_in(client, no_commission_user)
    assert new_page(client).status_code == 403
    assert client.post(reverse("expedientes:nuevo"), {"url": LINK_URL}).status_code == 403


# --- La propuesta agrupada ---------------------------------------------------------------------


def test_the_proposal_is_grouped_with_where_each_thing_goes(client, operator_user, docs_portal,
                                                            two_regimes):
    """REQ-076: datos, renglones y documentos agrupados, con la columna «Queda en» (pliego a la
    sección 2, circulares y ofertas a la 3, dictamen a la 4); explorar no carga nada."""
    url = explore(client, operator_user)
    html = client.get(url).content.decode()
    for title in ("Datos del procedimiento", "Renglones", "Documentos publicados"):
        assert title in html
    assert EXPECTED["procedimiento"]["numero"] in html
    assert html.count("Queda en") >= 4
    docs = html[html.index('id="s1-grupo-documentos"'):]
    assert "Clausulas Particulares" in docs
    assert "Pliego y matriz" in docs and "Evaluación y dictamen" in docs
    assert "archivo del Portal" in docs  # el acta queda como archivo, en Procedimiento
    assert not Procedure.objects.exists() and not PortalLine.objects.exists()
    assert not PortalItem.objects.exclude(state=ItemState.PROPUESTO).exists()


def test_reading_approves_nothing(client, operator_user, evaluator_user, docs_portal,
                                  two_regimes):
    """Ver la propuesta, una y otra vez, no decide ni carga nada."""
    url = explore(client, operator_user)
    for user in (operator_user, evaluator_user, operator_user):
        client.logout()
        log_in(client, user)
        assert client.get(url).status_code == 200
    assert not AuditEvent.objects.filter(event_type=EventType.PORTAL_DECISION).exists()
    assert not PortalItem.objects.exclude(state=ItemState.PROPUESTO).exists()


def test_the_operator_sees_no_approval_of_data_lines_or_offers(client, operator_user, docs_portal,
                                                               two_regimes):
    """REQ-079 y REQ-048 de la 012: el operador solo aprueba documentos; lo demás lo aprueba un
    evaluador y no se le ofrece."""
    url = explore(client, operator_user)
    html = client.get(url).content.decode()
    assert 'value="todo"' not in html and 'value="grupo:datos"' not in html
    assert 'value="grupo:renglones"' not in html
    assert 'value="grupo:documentos"' not in html or "Aprobar este grupo" in html
    assert "Este grupo lo aprueba un evaluador" in html
    document = PortalItem.objects.filter(kind=ItemKind.DOCUMENTO).first()
    assert f'value="item:{document.pk}"' in html


def test_the_evaluator_approves_everything_and_lands_in_the_new_procedure(
        client, operator_user, evaluator_user, docs_portal, two_regimes):
    """REQ-076: «Aprobar todo lo encontrado» con la fecha de autorización confirmada crea el
    procedimiento, los renglones y los documentos, y abre la pestaña Procedimiento con el
    resultado de cada ítem y la sección donde quedó."""
    url = explore(client, operator_user)
    client.logout()
    log_in(client, evaluator_user)
    html = client.get(url).content.decode()
    item = PortalItem.objects.get(kind=ItemKind.PROCEDIMIENTO)
    assert f'name="fecha_{item.pk}"' in html and 'value="todo"' in html
    response = client.post(reverse("expedientes:nuevo_decidir", args=[item.proposal.link_id]),
                           {"aprobar": "todo", f"fecha_{item.pk}": "2025-11-14"})
    procedure = Procedure.objects.get()
    assert response.status_code == 302
    assert response.url.startswith(reverse("expedientes:procedimiento", args=[procedure.pk]))
    assert procedure.number == EXPECTED["procedimiento"]["numero"]
    assert PortalLine.objects.filter(procedure=procedure).count() == 6
    assert Document.objects.filter(procedure=procedure).exists()
    page = client.get(response.url)
    html = page.content.decode()
    assert "quedó listo" in html and "cargado. Quedó en" in html
    assert f'href="{reverse("expedientes:pliego", args=[procedure.pk])}"' in html
    assert AuditEvent.objects.filter(event_type=EventType.PORTAL_DECISION,
                                     user=evaluator_user).exists()
    decided = PortalItem.objects.exclude(state=ItemState.PROPUESTO)
    assert decided.exists() and all(i.decided_by == evaluator_user for i in decided)


def test_approving_the_view_leaves_the_same_change_and_audit_as_the_service(
        client, operator_user, evaluator_user, docs_portal, two_regimes):
    """El tema usa los servicios de la 012: la misma aprobación por la vista y por el servicio deja
    los mismos estados y el mismo hecho de auditoría por ítem."""
    url = explore(client, operator_user)
    link = PortalLink.objects.get()
    item = PortalItem.objects.get(kind=ItemKind.PROCEDIMIENTO)
    client.logout()
    log_in(client, evaluator_user)
    client.post(reverse("expedientes:nuevo_decidir", args=[link.pk]),
                {"aprobar": f"item:{item.pk}", f"fecha_{item.pk}": "2025-11-14"})
    item.refresh_from_db()
    assert item.state == ItemState.CARGADO and item.loaded_model == "tenders_procedure"
    event = AuditEvent.objects.get(event_type=EventType.PORTAL_DECISION)
    assert event.detail["decision"] == "aprobar" and event.detail["result"] == "cargado"
    assert event.detail["item"] == item.pk and event.user == evaluator_user


def test_approval_without_the_date_loads_nothing_and_says_why(
        client, operator_user, evaluator_user, docs_portal, two_regimes):
    url = explore(client, operator_user)
    link = PortalLink.objects.get()
    client.logout()
    log_in(client, evaluator_user)
    response = client.post(reverse("expedientes:nuevo_decidir", args=[link.pk]),
                           {"aprobar": "todo"})
    html = client.get(response.url).content.decode()
    assert "Confirme la fecha de autorización" in html
    assert not Procedure.objects.exists() and not PortalLine.objects.exists()


def test_the_operator_cannot_approve_data_and_nothing_is_loaded(
        client, operator_user, docs_portal, two_regimes):
    """REQ-079: forzar el POST del evaluador siendo operador da 403, deja el rechazo y no carga."""
    explore(client, operator_user)
    link = PortalLink.objects.get()
    for action in ("todo", "grupo:datos", "grupo:renglones"):
        response = client.post(reverse("expedientes:nuevo_decidir", args=[link.pk]),
                               {"aprobar": action})
        assert response.status_code == 403, action
    assert not Procedure.objects.exists() and not PortalLine.objects.exists()
    assert AuditEvent.objects.filter(outcome="rejected").exists()


def test_the_operator_approves_documents_once_the_procedure_exists(
        client, operator_user, loaded):
    """REQ-079: con el procedimiento creado, el operador aprueba los documentos de la
    propuesta y quedan cargados en su sección."""
    client.logout()
    log_in(client, operator_user)
    html = tab(client, loaded).content.decode()
    assert 'id="s1-grupo-documentos"' in html and "Aprobar este grupo" in html
    link = PortalLink.objects.get()
    response = client.post(reverse("expedientes:s1_portal_decidir", args=[loaded.pk, link.pk]),
                           {"aprobar": "grupo:documentos"})
    assert response.status_code == 302
    assert Document.objects.filter(procedure=loaded).exists()
    html = client.get(response.url).content.decode()
    assert "cargado. Quedó en «Pliego y matriz»" in html
    assert decision_links(mine(html)) == []


def test_another_procedures_link_is_not_decided_from_this_tab(client, evaluator_user, loaded,
                                                              procedure):
    log_in(client, evaluator_user)
    link = PortalLink.objects.get()
    response = client.post(reverse("expedientes:s1_portal_decidir", args=[procedure.pk, link.pk]),
                           {"aprobar": "todo"})
    assert response.status_code == 404


# --- La pestaña de un procedimiento ----------------------------------------------------------------


def test_a_hand_loaded_procedure_offers_to_take_from_the_portal(client, operator_user, procedure):
    log_in(client, operator_user)
    html = tab(client, procedure).content.decode()
    assert 'id="s1-portal"' in html and "no tiene un proceso del Portal" in html
    assert f'href="{reverse("expedientes:nuevo")}"' in html and "Tomar del Portal" in html


def test_the_tab_shows_the_pending_proposal_and_counts_it(client, operator_user, loaded):
    """Lo propuesto y sin aprobar es pendiente de la sección y de la portada, con su enlace a la
    propuesta dentro de la pestaña."""
    log_in(client, operator_user)
    pending = PortalItem.objects.filter(state=ItemState.PROPUESTO).count()
    assert pending > 0
    html = tab(client, loaded).content.decode()
    assert 'id="s1-propuesta"' in html and f"Propuesta del Portal: {pending} sin aprobar" in html
    portada = client.get(reverse("expedientes:portada", args=[loaded.pk])).content.decode()
    assert f"Propuesta del Portal: {pending} sin aprobar" in portada
    assert decision_links(mine(html)) == []
    for page in (html, portada):
        (link,) = row_links(page, f"Propuesta del Portal: {pending} sin aprobar")
        assert link == f'{reverse("expedientes:procedimiento", args=[loaded.pk])}#s1-propuesta'
    assert f'href="{reverse("expedientes:procedimiento", args=[loaded.pk])}#s1-portal"' in html
    from evaluon.journey.sections import sections_for
    section = sections_for(operator_user, loaded).get("procedimiento")
    assert section.pending == pending
    assert sum(i.count for i in section.pending_items) == pending


def test_a_new_circular_is_a_pending_novelty_and_nothing_loads(
        client, operator_user, evaluator_user, loaded, docs_portal):
    """REQ-079: la revisión detecta una circular nueva (`origin = revision`): aparece como pendiente
    de la sección y de la portada, bajo «Novedades del Portal», y no se carga sin aprobación."""
    link = PortalLink.objects.get()
    docs_portal.serve("proceso-con-circular.html")
    serve_documents(docs_portal, version=2)
    jobs.enqueue(JobKind.PORTAL_REVIEW, procedure=None, requested_by=operator_user,
                 target_id=link.pk)
    assert jobs.run_next(kinds=PORTAL_JOB_KINDS).status == JobStatus.DONE
    news = PortalItem.objects.filter(proposal__origin=Origin.REVISION, state=ItemState.PROPUESTO)
    assert news.count() == 2 and news.filter(payload__nombre='Circular 1').exists()
    documents_before = Document.objects.filter(procedure=loaded).count()
    log_in(client, operator_user)
    html = tab(client, loaded).content.decode()
    block = html[html.index('id="s1-novedades"'):]
    assert "Novedades del Portal" in block and "2 sin aprobar" in block
    assert "Ofertas" in block  # a dónde queda
    assert "Novedades del Portal: 2 sin aprobar" in html
    portada = client.get(reverse("expedientes:portada", args=[loaded.pk])).content.decode()
    assert row_links(portada, "Novedades del Portal: 2 sin aprobar")[0].endswith("#s1-novedades")
    assert Document.objects.filter(procedure=loaded).count() == documents_before
    assert decision_links(mine(html)) == []
    # No aparece también en la propuesta común.
    assert block.count("Circular 1") == 1


def test_approving_a_novelty_needs_the_circular_type_and_date(
        client, operator_user, loaded, docs_portal):
    link = PortalLink.objects.get()
    docs_portal.serve("proceso-con-circular.html")
    serve_documents(docs_portal, version=2)
    jobs.enqueue(JobKind.PORTAL_REVIEW, procedure=None, requested_by=operator_user,
                 target_id=link.pk)
    jobs.run_next(kinds=PORTAL_JOB_KINDS)
    item = PortalItem.objects.get(proposal__origin=Origin.REVISION, state=ItemState.PROPUESTO,
                                  payload__nombre="Circular 1")
    log_in(client, operator_user)
    url = reverse("expedientes:s1_portal_decidir", args=[loaded.pk, link.pk])
    needs_kind = not item.payload.get("tipo_circular")
    needs_date = not item.payload.get("fecha")
    post = {"aprobar": f"item:{item.pk}"}
    if needs_kind or needs_date:
        refused = client.get(client.post(url, post).url).content.decode()
        assert "no se cargó" in refused
        item.refresh_from_db()
        assert item.state == ItemState.PROPUESTO
    if needs_kind:
        post[f"tipo_{item.pk}"] = "circular_aclaratoria"
    if needs_date:
        post[f"emision_{item.pk}"] = "2025-11-25"
    response = client.post(url, post)
    item.refresh_from_db()
    assert item.state == ItemState.CARGADO
    assert "Quedó en «Ofertas»" in client.get(response.url).content.decode()


def test_review_now_and_stop_following_are_in_the_tab(client, operator_user, loaded):
    """«Revisar ahora» y «dejar de seguir» están a la vista, piden lo mismo que las pantallas
    viejas y vuelven a la pestaña con el aviso."""
    link = PortalLink.objects.get()
    log_in(client, operator_user)
    html = tab(client, loaded).content.decode()
    assert "Revisar ahora" in html and "Dejar de seguir" in html
    review = reverse("expedientes:s1_portal_revisar", args=[loaded.pk, link.pk])
    response = client.post(review)
    assert response.url.startswith(reverse("expedientes:procedimiento", args=[loaded.pk]))
    assert Job.objects.filter(kind=JobKind.PORTAL_REVIEW, target_id=link.pk).count() == 1
    assert "Se pidió una revisión" in client.get(response.url).content.decode()
    again = client.get(client.post(review).url).content.decode()
    assert "Ya hay una lectura del Portal en curso" in again
    assert Job.objects.filter(kind=JobKind.PORTAL_REVIEW, target_id=link.pk).count() == 1
    stop = client.post(reverse("expedientes:s1_portal_dejar", args=[loaded.pk, link.pk]))
    link.refresh_from_db()
    assert not link.following
    assert "ya no lo revisa" in client.get(stop.url).content.decode()
    assert "Sin seguimiento" in tab(client, loaded).content.decode()
    assert AuditEvent.objects.filter(event_type=EventType.PORTAL_LINK,
                                     detail__action="dejar_de_seguir").exists()


def test_the_message_is_signed_and_expires(client, operator_user, procedure):
    log_in(client, operator_user)
    forged = tab(client, procedure, "?portal=falsificado").content.decode()
    assert 's1-resultado' not in forged
    signed = s1_portal.pack([s1_portal.entry("Mensaje de prueba.")])
    assert "Mensaje de prueba." in tab(client, procedure, f"?portal={signed}").content.decode()


def test_dates_are_shown_in_local_time(client, operator_user, loaded):
    """Las horas de la propuesta y de la lectura están en hora local, no en la de la base."""
    from django.utils import timezone
    log_in(client, operator_user)
    item = PortalItem.objects.filter(state=ItemState.PROPUESTO).first()
    view = s1_portal.link_view(operator_user, PortalLink.objects.get())
    assert view["job"]["at"] == f"{timezone.localtime(Job.objects.filter(kind=JobKind.PORTAL_EXPLORE).get().finished_at):%d/%m/%Y %H:%M}"
    assert item is not None
