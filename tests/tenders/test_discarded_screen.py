"""Pantalla, impresión y cobertura de las filas descartadas por el sistema (REQ-033,
REQ-032, REQ-034, REQ-026; plan 003, "Pantalla" y "Impresión y PDF"; ADR-0021; T-105).

Pliego y datos sintéticos (P4). Las pantallas se prueban con el cliente de pruebas.
"""

import html

import pytest
from django.urls import reverse

from evaluon.audit.models import AuditEvent, Outcome
from evaluon.tenders import export
from evaluon.tenders import models as m
from evaluon.tenders.services import validation
from tests.conftest import TEST_PASSWORD
from tests.tenders.scripted import script  # noqa: F401  (fixture)
from tests.tenders.test_discarded import add_row, case, segment  # noqa: F401
from tests.tenders.test_export import pdf_pages
from tests.tenders.test_validation import finish_review

pytestmark = pytest.mark.django_db

LEGEND = "BORRADOR INCOMPLETO"


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def text_of(response):
    return html.unescape(response.content.decode())


def squash(text):
    return " ".join(text.split())


def list_url(version):
    return reverse("tenders:discarded", args=[version.pk])


def restore_url(version):
    return reverse("tenders:discarded_restore", args=[version.pk])


# --- La lista ------------------------------------------------------------------------------------


def test_the_list_shows_each_row_with_literal_text_reason_evidence_and_link(
        client, operator_user, case):
    """REQ-033: cada descartada con su cita literal (igual al recorte), documento, página,
    cláusula, enlace al original, clase, motivo, indicio y estado."""
    row = add_row(case, "sec-i/3.1", order=1, category="economico")
    log_in(client, operator_user)

    response = client.get(list_url(case))

    assert response.status_code == 200
    page = squash(text_of(response))
    reading = row.segment.reading
    assert row.text == reading.canonical_text[row.char_start:row.char_end]
    assert squash(row.text) in page
    assert squash(row.evidence_text) in page
    assert m.FilterMotive(row.reason).label in page
    assert "Económico" in page and "Descartada" in page
    assert reading.document.title in page
    assert "Cláusula: " + row.segment.path in page
    assert reverse("tenders:document_original", args=[reading.document.pk]) in page
    assert "Descartadas por el sistema" in page
    assert f'value="{row.pk}"' in page and "Devolver a la matriz" in page


def test_the_list_without_rows_says_so(client, operator_user, case):
    """REQ-033: sin descartadas, la página lo dice y no hay botón."""
    log_in(client, operator_user)

    page = text_of(client.get(list_url(case)))

    assert "no descartó ninguna fila" in page
    assert "Devolver a la matriz" not in page


def test_returning_nothing_or_twice_shows_the_reason_and_changes_nothing(
        client, evaluator_user, case):
    """REQ-033: sin filas marcadas, o una fila ya devuelta, vuelve a la página con el
    motivo."""
    row = add_row(case, "sec-i/3.1", order=1)
    log_in(client, evaluator_user)

    none = client.post(restore_url(case), {})
    assert none.status_code == 400
    assert "al menos una fila" in text_of(none)

    assert client.post(restore_url(case), {"row": [row.pk]}).status_code == 302
    again = client.post(restore_url(case), {"row": [row.pk]})
    assert again.status_code == 400 and "ya se devolvió" in text_of(again)
    assert m.Requirement.objects.filter(version=case, restored_from=row).count() == 1


def test_operator_and_evaluator_return_rows_and_a_user_without_role_cannot(
        client, evaluator_user, no_commission_user, case):
    """REQ-026/P6: operador y evaluador devuelven; sin rol de la Comisión, 403 en la lista
    y al devolver, con el rechazo registrado, y no se crea nada."""
    row = add_row(case, "sec-i/3.1", order=1)
    log_in(client, no_commission_user)

    assert client.get(list_url(case)).status_code == 403
    assert client.post(restore_url(case), {"row": [row.pk]}).status_code == 403
    assert not m.Requirement.objects.filter(restored_from=row).exists()
    assert AuditEvent.objects.filter(outcome=Outcome.REJECTED).exists()

    client.logout()
    log_in(client, evaluator_user)
    assert client.post(restore_url(case), {"row": [row.pk]}).status_code == 302


def test_a_validated_version_shows_the_list_without_the_return_form(
        client, evaluator_user, case):
    """REQ-033: en una versión validada la lista se ve, pero sin casillas ni botón; y
    devolver se rechaza."""
    row = add_row(case, "sec-i/3.1", order=1)
    finish_review(evaluator_user, case)
    validation.validate(evaluator_user, case.pk)
    log_in(client, evaluator_user)

    page = text_of(client.get(list_url(case)))

    assert squash(row.text) in squash(page)
    assert "Devolver a la matriz" not in page and 'type="checkbox"' not in page
    assert client.post(restore_url(case), {"row": [row.pk]}).status_code == 400


def test_a_missing_version_answers_404(client, operator_user):
    """REQ-033: una versión que no existe da 404."""
    log_in(client, operator_user)
    assert client.get(reverse("tenders:discarded", args=[999999])).status_code == 404
    assert client.post(reverse("tenders:discarded_restore", args=[999999]),
                       {"row": [1]}).status_code == 404


def test_the_repeated_quotes_of_a_discarded_row_are_listed(client, operator_user, case):
    """REQ-033: las citas adicionales de la descartada se muestran todas."""
    row = add_row(case, "sec-i/3.1", extra_key="sec-i/4.1", order=1)
    other = segment(case, "sec-i/4.1")
    log_in(client, operator_user)

    page = squash(text_of(client.get(list_url(case))))

    assert "también en" in page.lower()
    assert squash(other.text) in page and squash(row.text) in page


# --- La matriz: línea de descartadas y citas repetidas -----------------------------------------


def repeat_quote(requirement, other, length, order):
    return m.RequirementQuote.objects.create(
        requirement=requirement, order=order, segment=other, char_start=other.char_start,
        char_end=other.char_start + length,
        text=other.reading.canonical_text[other.char_start:other.char_start + length],
        scope="repetida", quote_flag="")


def test_the_coverage_shows_the_filter_origin(client, operator_user, case):
    """REQ-033: la cobertura muestra el origen `filtro` de un tramo cuyas filas se
    descartaron todas."""
    seg = segment(case, "sec-i/3.1")
    m.Disposition.objects.filter(run=case.run, segment=seg).delete()
    m.Disposition.objects.create(run=case.run, segment=seg, outcome="descartado",
                                 discard_reason="ejecucion_contrato", source="filtro")
    log_in(client, operator_user)

    page = text_of(client.get(reverse("tenders:coverage", args=[case.pk])))

    assert "<td>Filtro</td>" in page


# --- Impresión y PDF -----------------------------------------------------------------------------


def test_print_view_has_the_discarded_line_by_reason_and_keeps_the_legend(
        client, operator_user, case):
    """REQ-032/033: la impresión de un borrador con descartadas lleva la línea con la
    cantidad y el reparto por motivo, y la leyenda sigue igual; sin direcciones externas."""
    add_row(case, "sec-i/3.1", order=1, reason="consecuencia_sancion")
    add_row(case, "sec-i/4.1", order=2, reason="consecuencia_sancion")
    add_row(case, "sec-i/3.1", order=3, reason="formulario")
    log_in(client, operator_user)

    page = squash(text_of(client.get(reverse("tenders:print", args=[case.pk]))))

    assert "El sistema descartó 3 filas" in page
    assert "Consecuencia o sanción: 2" in page and "Formulario a completar: 1" in page
    assert 'class="page-mark draft" role="note">BORRADOR INCOMPLETO' in page
    assert "http://" not in page and "https://" not in page


def test_print_view_without_discarded_rows_has_no_line(client, operator_user, case):
    """REQ-032: sin descartadas la impresión queda como estaba."""
    log_in(client, operator_user)

    page = text_of(client.get(reverse("tenders:print", args=[case.pk])))

    assert "El sistema descartó" not in page and LEGEND in page


def test_the_pdf_of_a_draft_with_discarded_rows_has_the_line_and_the_legend_on_every_page(
        operator_user, case):
    """REQ-032/033: el PDF lleva la línea de descartadas y "BORRADOR INCOMPLETO" en cada
    página."""
    add_row(case, "sec-i/3.1", order=1, reason="formulario")

    data, _name = export.export_pdf(operator_user, case.pk)

    pages = pdf_pages(data)
    assert any("El sistema descartó 1 fila" in text for text in pages)
    assert all(LEGEND in text for text in pages)
