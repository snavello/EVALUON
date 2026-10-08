"""Tema «matriz de cumplimiento» de la sección Pliego y matriz (REQ-081, REQ-082; plan 014,
T-192). Solo lectura en este corte. Todo el material es inventado (P4)."""

import datetime
import re

import pytest
from django.urls import reverse
from django.utils import timezone

from evaluon.tenders.models import MatrixVersion, Procedure, Requirement, RequirementState, VersionStatus
from evaluon.tenders.services import validation
from tests.accounts.test_session import TEST_PASSWORD

pytestmark = pytest.mark.django_db

HIDDEN = ("quitado", "sugerido")


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


@pytest.fixture
def two_versions(procedure, matrix, operator_user):
    """El caso chico con la versión 1 validada y la 2 abierta; tres requisitos sin confirmar."""
    opened = validation.open_new_version(operator_user, procedure.pk)
    draft = opened if isinstance(opened, MatrixVersion) else procedure.matrix_versions.get(
        status=VersionStatus.DRAFT)
    unconfirmed = list(draft.requirements.order_by("number")[:3])
    Requirement.objects.filter(pk__in=[r.pk for r in unconfirmed]).update(
        state=RequirementState.PROPUESTO)
    return draft, [r.number for r in unconfirmed]


def page(client, procedure, query=""):
    return client.get(reverse("expedientes:pliego", args=[procedure.pk]) + query)


def rows_of(html):
    """Los números de los requisitos que muestra la tabla, en orden."""
    return re.findall(r'<tr class="fila-req" data-numero="(\d+)"', html)


def test_the_table_is_grouped_by_type_with_the_quote_in_every_row(
        client, procedure, two_versions, operator_user):
    """REQ-081: tabla agrupada por tipo; cada fila se abre con su cita literal."""
    draft, _ = two_versions
    log_in(client, operator_user)
    html = page(client, procedure).content.decode()
    assert 'id="t-matriz"' in html
    groups = re.findall(r'<tr class="grupo" data-tipo="(\w+)"', html)
    assert groups == [g for g in ("formal", "economico", "tecnico")
                      if draft.requirements.filter(category=g).exclude(
                          state__in=HIDDEN).exists()]
    shown = draft.requirements.exclude(state__in=HIDDEN)
    assert len(rows_of(html)) == shown.count()
    for requirement in shown:
        quote = requirement.quotes.order_by("order").first()
        assert quote is not None
        assert f'id="detalle-{requirement.number}"' in html
        assert quote.text.split("\n")[0][:40] in html
    assert html.count('class="detalle"') == shown.count()


def test_the_filter_shows_only_what_is_left_to_decide(client, procedure, two_versions,
                                                      operator_user):
    """REQ-081: «solo lo que falta decidir» deja exactamente las filas sin confirmar."""
    _, unconfirmed = two_versions
    log_in(client, operator_user)
    html = page(client, procedure, "?filtro=falta").content.decode()
    assert sorted(map(int, rows_of(html))) == sorted(unconfirmed)
    assert 'aria-pressed="true"' in html
    assert "Solo lo que falta decidir" in html


def test_the_type_and_state_filters(client, procedure, two_versions, operator_user):
    """REQ-081: filtros por tipo y por estado."""
    draft, unconfirmed = two_versions
    log_in(client, operator_user)
    html = page(client, procedure, "?tipo=formal").content.decode()
    formal = draft.requirements.filter(category="formal").exclude(state__in=HIDDEN).count()
    assert len(rows_of(html)) == formal
    html = page(client, procedure, "?filtro=conf").content.decode()
    assert not set(map(int, rows_of(html))) & set(unconfirmed)
    html = page(client, procedure, "?tipo=inventado").content.decode()
    assert len(rows_of(html)) == draft.requirements.exclude(state__in=HIDDEN).count()


def test_the_list_of_versions_shows_both_with_date_and_who_validated(
        client, procedure, two_versions, operator_user):
    """REQ-082: lista de versiones con estado, fecha y quién validó cada una."""
    log_in(client, operator_user)
    html = page(client, procedure).content.decode()
    block = html[html.index('id="s2-versiones"'):]
    assert block.count('<tr class="version"') == 2
    first = procedure.matrix_versions.get(number=1)
    assert "Validada" in block and "En revisión" in block
    assert timezone.localtime(first.validated_at).strftime("%d/%m/%Y") in block
    assert first.validated_by.username in block


def test_print_and_export_links_point_to_the_existing_screens(client, procedure,
                                                              two_versions, operator_user):
    """REQ-082: imprimir y exportar reutilizan las rutas de `tenders`."""
    draft, _ = two_versions
    log_in(client, operator_user)
    html = page(client, procedure).content.decode()
    assert reverse("tenders:print", args=[draft.pk]) in html
    assert reverse("tenders:pdf", args=[draft.pk]) in html


def test_only_the_evaluator_gets_the_review_actions(client, procedure, two_versions,
                                                    operator_user, evaluator_user):
    """REQ-081: el enlace a decidir en la matriz completa es solo del evaluador."""
    draft, _ = two_versions
    target = reverse("tenders:matrix", args=[draft.pk])
    log_in(client, operator_user)
    assert "Revisar y decidir en la matriz" not in page(client, procedure).content.decode()
    client.logout()
    log_in(client, evaluator_user)
    html = page(client, procedure).content.decode()
    assert "Revisar y decidir en la matriz" in html and target in html


def test_the_unconfirmed_rows_count_once_in_the_section(procedure, two_versions,
                                                        evaluator_user):
    """REQ-098: lo sin confirmar lo cuenta la etapa de la matriz (no se repite en el tema)."""
    from evaluon.journey import sections
    from evaluon.journey.temas import s2_matriz
    _, unconfirmed = two_versions
    assert s2_matriz.status(evaluator_user, procedure).pending == 0
    section = sections.sections_for(evaluator_user, procedure).get("pliego")
    assert section.pending >= len(unconfirmed)
    assert any("Matriz" in item.text for item in section.pending_items)


def test_a_procedure_without_matrix_shows_an_empty_state(client, operator_user):
    """Sin versión de la matriz, el bloque dice qué falta en vez de una tabla vacía."""
    bare = Procedure.objects.create(
        number="VACIO-1", procedure_type="Licitación pública", subject="Inventado",
        authorization_date=datetime.date(2025, 3, 3), created_by=operator_user)
    log_in(client, operator_user)
    html = page(client, bare).content.decode()
    assert "Todavía no hay una matriz" in html and 'id="t-matriz"' not in html


def test_dates_are_shown_in_local_time(client, procedure, two_versions, operator_user):
    """REQ-100: a las 01:20 UTC del 08/10 en Buenos Aires todavía es 07/10."""
    from datetime import datetime, timezone
    moment = datetime(2026, 10, 8, 1, 20, tzinfo=timezone.utc)
    draft, _ = two_versions
    MatrixVersion.objects.filter(pk=draft.pk).update(created_at=moment)
    log_in(client, operator_user)
    html = page(client, procedure).content.decode()
    block = html[html.index('id="s2-versiones"'):]
    assert "abierta el 07/10/2026" in block and "abierta el 08/10/2026" not in block
