"""Las cinco secciones de la aplicación (REQ-075, REQ-097, REQ-098, REQ-100; plan 014).
Todo el material es inventado (P4)."""

import pytest
from django.urls import reverse

from evaluon.audit.models import AuditEvent
from evaluon.journey import sections, temas
from evaluon.journey.stages import base, stages_for
from tests.accounts.test_session import TEST_PASSWORD

pytestmark = pytest.mark.django_db

KEYS = ["procedimiento", "pliego", "ofertas", "evaluacion", "normativas"]
LABELS = ["Procedimiento", "Pliego y matriz", "Ofertas", "Evaluación y dictamen",
          "Normativas"]
TEMA_KEYS = [
    "s1_datos", "s1_portal", "s1_pliego", "s2_documentos", "s2_matriz", "s3_ofertas",
    "s3_ficha", "s3_anexos", "s3_circulares", "s4_propuesta", "s4_preguntas", "s4_informe",
    "s4_descartes", "s4_dictamen", "s4_exportar", "s5_normas", "s5_rigen", "s5_consulta"]


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def test_there_are_five_sections_with_state_and_two_counts(procedure, operator_user):
    """REQ-075: cinco secciones, cada una con estado válido y sus dos cuentas."""
    overview = sections.sections_for(operator_user, procedure)
    assert [s.key for s in overview.sections] == KEYS
    assert [s.label for s in overview.sections] == LABELS
    for section in overview.sections:
        assert section.state in base.LABELS
        assert section.pending >= 0 and section.suggestions >= 0
        assert section.url == reverse(f"expedientes:{section.key}", args=[procedure.pk])


def test_the_counts_of_the_sections_add_up_to_the_stages(procedure, matrix, operator_user):
    """REQ-098: lo pendiente y las sugerencias de las secciones salen de las etapas de la 013."""
    journey = stages_for(operator_user, procedure)
    overview = sections.sections_for(operator_user, procedure)
    assert overview.pending == journey.pending == sum(s.pending for s in overview.sections)
    assert overview.suggestions == journey.suggestions


def test_the_18_themes_exist_with_zero_counts(procedure, operator_user):
    """Plan 014, estructura común: 18 temas, cada uno con `status()`; en este corte ninguno
    suma cuentas propias (las de la matriz salen de la etapa de la 013)."""
    assert [t.KEY for t in temas.TEMAS] == TEMA_KEYS
    for tema in temas.TEMAS:
        status = tema.status(operator_user, procedure)
        assert status.pending >= 0 and status.suggestions >= 0
        assert (status.pending, status.suggestions) == (0, 0)
        if tema.KEY not in ("s1_datos", "s3_ofertas", "s4_dictamen", "s5_rigen"):
            # dicen lo que falta con su acción directa: s1_datos (T-194), s3_ofertas (T-202,
            # «Todavía no hay ofertas»), s4_dictamen (T-211) y s5_rigen (T-215)
            assert list(status.missing) == []


@pytest.mark.parametrize("key", KEYS)
def test_any_section_opens_directly_and_shows_the_five_tabs(client, procedure, operator_user,
                                                            key):
    """REQ-075: se entra a cualquiera sin pasar por otra y las cinco se ven con sus cuentas."""
    log_in(client, operator_user)
    response = client.get(reverse(f"expedientes:{key}", args=[procedure.pk]))
    assert response.status_code == 200
    html = response.content.decode()
    for label in LABELS:
        assert label in html
    assert html.count('data-seccion="') == 5
    assert "pend." in html and "sug." in html
    assert 'aria-current="page"' in html


def test_the_user_without_commission_role_gets_403_and_a_recorded_rejection(
        client, procedure, no_commission_user):
    """REQ-075: sin rol de la Comisión, 403 y el rechazo queda registrado."""
    log_in(client, no_commission_user)
    before = AuditEvent.objects.filter(event_type="rejected").count()
    for url in (reverse("expedientes:portada", args=[procedure.pk]),
                reverse("expedientes:pliego", args=[procedure.pk]),
                reverse("expedientes:index")):
        assert client.get(url).status_code == 403
    assert AuditEvent.objects.filter(event_type="rejected").count() == before + 3


def test_the_front_page_has_two_separate_blocks_for_pending_and_suggestions(
        client, procedure, matrix, evaluator_user):
    """REQ-098: pendientes y sugerencias, en dos bloques aparte y visibles."""
    log_in(client, evaluator_user)
    response = client.get(reverse("expedientes:portada", args=[procedure.pk]))
    assert response.status_code == 200
    html = response.content.decode()
    assert 'id="pendientes"' in html and 'id="sugerencias"' in html
    assert html.index('id="pendientes"') < html.index('id="sugerencias"')
    assert "Pendientes de decidir" in html and "Sugerencias del sistema" in html
    assert "Qué hay y qué falta" in html
    for key in KEYS:
        assert reverse(f"expedientes:{key}", args=[procedure.pk]) in html


@pytest.mark.parametrize("key", KEYS)
def test_every_section_uses_the_same_hierarchy(client, procedure, operator_user, key):
    """REQ-100: título, resumen, pendientes y sugerencias, detalle y acciones, en ese orden."""
    log_in(client, operator_user)
    html = client.get(reverse(f"expedientes:{key}", args=[procedure.pk])).content.decode()
    marks = ['id="seccion-titulo"', 'id="seccion-resumen"', 'id="pendientes"',
             'id="sugerencias"', 'id="seccion-detalle"']
    positions = [html.index(m) for m in marks]
    assert positions == sorted(positions)


def test_the_bar_fragment_is_only_the_tabs(client, procedure, operator_user):
    """REQ-075: el sondeo pide solo la barra, sin pasar por `base.html`."""
    log_in(client, operator_user)
    response = client.get(reverse("expedientes:barra", args=[procedure.pk]))
    assert response.status_code == 200
    html = response.content.decode()
    assert "<html" not in html and html.count('data-seccion="') == 5
    assert response["Cache-Control"] == "no-store"


def test_the_header_lists_procedures_and_links_to_the_new_procedure_screen(
        client, procedure, operator_user):
    """El encabezado ofrece cambiar de procedimiento y «+ Nuevo procedimiento», que lleva al alta
    dentro de las cinco pestañas (T-195) y ya no al recorrido de la 013."""
    log_in(client, operator_user)
    html = client.get(reverse("expedientes:portada", args=[procedure.pk])).content.decode()
    assert procedure.number in html
    assert "Nuevo procedimiento" in html
    assert f'href="{reverse("expedientes:nuevo")}"' in html and reverse("journey:index") not in html
    assert "Salir" in html and operator_user.username in html


def test_the_index_lists_procedures_with_their_counts(client, procedure, operator_user):
    """El listado de expedientes lleva a la portada de cada uno."""
    log_in(client, operator_user)
    response = client.get(reverse("expedientes:index"))
    assert response.status_code == 200
    html = response.content.decode()
    assert reverse("expedientes:portada", args=[procedure.pk]) in html
    assert "pend." in html


def test_an_unknown_procedure_is_404(client, operator_user):
    log_in(client, operator_user)
    assert client.get(reverse("expedientes:portada", args=[999999])).status_code == 404


def test_the_header_lists_the_procedures_to_switch(client, procedure, operator_user):
    """El encabezado único trae el desplegable con los procedimientos y el alta, sin menú."""
    log_in(client, operator_user)
    html = client.get(reverse("queries:screen")).content.decode()
    assert reverse("expedientes:procedimiento", args=[procedure.pk]) in html
    assert reverse("expedientes:nuevo") in html and 'class="site-nav"' not in html


def test_no_demo_elements_reach_the_application(client, procedure, operator_user):
    """Nada de la maqueta: ni mapa de pantallas ni «ver como»."""
    log_in(client, operator_user)
    for key in KEYS:
        html = client.get(reverse(f"expedientes:{key}", args=[procedure.pk])).content.decode()
        for forbidden in ("Mapa de pantallas", "Ver como", "(demo)", "de muestra"):
            assert forbidden.lower() not in html.lower()


def test_a_single_ready_document_is_written_in_the_singular(procedure, operator_user):
    """REQ-100: «El documento del pliego está leído», no «Los 1 documentos»."""
    stage = stages_for(operator_user, procedure).stages[1]
    assert stage.key == "pliego" and "Los 1 documentos" not in stage.detail
    assert stage.detail.startswith("El documento del pliego")


def test_the_section_has_one_summary_line_without_repeated_versions(
        client, procedure, matrix, operator_user):
    """REQ-100: una sola línea de resumen; la versión de la matriz no se repite."""
    log_in(client, operator_user)
    html = client.get(reverse("expedientes:pliego", args=[procedure.pk])).content.decode()
    resumen = html[html.index('id="seccion-resumen"'):html.index('id="pendientes"')]
    assert resumen.count("<span class=\"linea") <= 1
    assert resumen.count("ersión 1") <= 1


def test_no_construction_text_in_the_sections(client, procedure, operator_user):
    """REQ-100: sin el bloque «Otras pantallas» ni «mientras se completa»."""
    log_in(client, operator_user)
    for key in KEYS:
        html = client.get(reverse(f"expedientes:{key}", args=[procedure.pk])).content.decode()
        assert "Otras pantallas" not in html and "mientras se completa" not in html
