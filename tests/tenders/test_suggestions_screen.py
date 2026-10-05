"""Pantalla e impresión de las sugerencias de condición con su respaldo normativo
(REQ-035, REQ-036, REQ-034, REQ-032; plan 003, "Pantalla e impresión" de las sugerencias;
ADR-0022; T-112).

Pliego, normas y datos sintéticos (P4). Las pantallas se prueban con el cliente de pruebas.
"""

from django.utils import timezone
import html
import io
import re

import pdfplumber
import pytest
from django.urls import reverse

from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.tenders import export, models as m
from evaluon.tenders.services import review, suggestions, validation
from tests.conftest import TEST_PASSWORD
from tests.tenders.test_suggestions import (  # noqa: F401  (fixtures y ayudas)
    add_support,
    case,
    finish,
    make_suggestion,
    norm_unit,
    script,
)

pytestmark = pytest.mark.django_db

LEGEND = "BORRADOR INCOMPLETO"
SECTION = "Sugerencias de condición"
PRINT_SECTION = "Sugerencias de condición sin decidir"
NO_SUPPORT = "Sin respaldo normativo encontrado: no es motivo para quitarla"
EXIGE = "La norma aplicable la exige"


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def text_of(response):
    return html.unescape(response.content.decode())


def squash(text):
    return " ".join(text.split())


def matrix_url(version):
    return reverse("tenders:matrix", args=[version.pk])


def group_url(version):
    return reverse("tenders:suggestion_group", args=[version.pk])


def accept_url(requirement):
    return reverse("tenders:suggestion_accept", args=[requirement.pk])


def state(requirement):
    return m.Requirement.objects.get(pk=requirement.pk).state


@pytest.fixture
def suggested(case):
    """Una versión sin otras filas, con tres sugerencias en el tramo 3.1 y una en el 4.1;
    la segunda tiene respaldo normativo."""
    case.requirements.update(state="quitado")
    rows = [make_suggestion(case, "sec-i/3.1", start=i * 6) for i in range(3)]
    other = make_suggestion(case, "sec-i/4.1", reason="duda")
    return case, rows, other


def section_of(page_text, start, end):
    """El texto entre dos encabezados de la página."""
    first = page_text.index(start)
    return page_text[first:page_text.index(end, first)]


# --- La sección ----------------------------------------------------------------------------------


def test_the_section_shows_each_suggestion_with_its_literal_text_reason_and_place(
        client, operator_user, suggested):
    """REQ-035: la sección está después de "Pendiente de revisión" y antes de los
    requisitos firmes; cada sugerencia con su cita igual al recorte, documento, cláusula,
    enlace al original, motivo (frase fija) e indicio literal, y la leyenda de que no se
    valida con sugerencias sin decidir."""
    version, rows, _other = suggested
    log_in(client, operator_user)

    page = text_of(client.get(matrix_url(version)))

    assert page.index("Pendiente de revisión") < page.index(SECTION) < page.index(
        "Requisitos formales y económicos")
    assert "no se puede validar con sugerencias sin decidir" in squash(page)
    section = squash(section_of(page, "<h2 id=\"suggestions-title\"", "Requisitos formales"))
    for row in rows:
        quote = row.quotes.get()
        recorte = quote.segment.reading.canonical_text[quote.char_start:quote.char_end]
        assert quote.text == recorte
        assert f'<blockquote class="literal">{recorte}</blockquote>' in section
    assert "Las dos preguntas del sistema no coincidieron" in section
    assert "El sistema dudó" in section
    assert "indicio" in section  # el indicio literal del tramo
    assert reverse("tenders:document_original",
                   args=[rows[0].quotes.get().segment.reading.document_id]) in page
    assert "Pasar a requisito" in section and "Quitar" in section


def test_the_text_shown_is_literal_and_escaped_not_interpreted(
        client, operator_user, suggested):
    """REQ-035 (P3): el texto de la cita, del indicio y de la norma se muestra tal cual,
    sin interpretar marcas."""
    version, rows, _other = suggested
    row = rows[0]
    row.doubt = {"answers": ["si", "no"], "evidence": "<b>negrita</b> & más"}
    row.save(update_fields=["doubt"])
    log_in(client, operator_user)

    raw = client.get(matrix_url(version)).content.decode()

    assert "&lt;b&gt;negrita&lt;/b&gt; &amp; más" in raw
    assert "<b>negrita</b>" not in raw


def test_suggestions_with_support_go_first_marked_and_show_the_cited_norm(
        client, operator_user, suggested, norm_unit):
    """REQ-036: primero las que tienen respaldo, marcadas "la norma aplicable la exige", con
    norma y ruta, vigencia, cita literal y enlace a la unidad; la que no tiene dice "Sin
    respaldo normativo encontrado: no es motivo para quitarla"."""
    version, rows, other = suggested
    add_support(rows[2], norm_unit, version.run)
    log_in(client, operator_user)

    page = text_of(client.get(matrix_url(version)))

    section = squash(section_of(page, "<h2 id=\"suggestions-title\"", "Requisitos formales"))
    assert section.index(f"Requisito {rows[2].number}") < section.index(
        f"Requisito {rows[0].number}")
    assert section.count(EXIGE) == 1
    assert section.count(NO_SUPPORT) == 3
    assert "Norma sintética, art. 1" in section
    assert "Artículo 1." in section  # la cita literal de la norma
    assert "vigente desde" in section
    document = norm_unit.reading.document
    assert reverse("norms:original", args=[document.pk]) in page
    # la norma no cambia el estado: sigue siendo una sugerencia
    assert state(rows[2]) == "sugerido"


def test_suggestions_never_show_in_the_firm_requirements_or_the_counts(
        client, operator_user, suggested):
    """REQ-035: una sugerencia no figura entre los requisitos firmes ni en las cuentas por
    clase; el resumen suma "sugerencias sin decidir"."""
    version, _rows, _other = suggested
    log_in(client, operator_user)

    response = client.get(matrix_url(version))
    page = text_of(response)

    firm = page[page.index('id="requirements-title"'):page.index('id="technical-title"')]
    assert "Requisito " not in firm
    assert response.context["page"].counts["formal"] == 0
    assert "Sugerencias sin decidir: 4" in squash(page)


def test_the_screen_shows_the_same_groups_as_validation(client, operator_user,
                                                        evaluator_user, suggested):
    """REQ-035 (aviso de T-110): los grupos de la pantalla son los de `validation._groups`:
    los mismos tramos que nombra el rechazo de la validación, con la misma cuenta."""
    version, rows, other = suggested
    log_in(client, operator_user)
    page = squash(text_of(client.get(matrix_url(version))))
    finish(evaluator_user, version)

    with pytest.raises(validation.ValidationRefused) as error:
        validation.validate(evaluator_user, version.pk)

    assert validation._groups(rows + [other]) == "sec-i/3.1, sec-i/4.1"
    for key in ("sec-i/3.1", "sec-i/4.1"):
        assert key in str(error.value)
        assert f"Tramo {key}" in page or f"Cláusula {key.split('.')[0]}" in page
    assert "Pasar a requisito las 3" in page and "Quitar las 3" in page
    assert "las 1" not in page
    assert "4" in str(error.value)


# --- Decidir una por una -------------------------------------------------------------------------


def test_pass_to_requirement_changes_the_state_and_the_row_moves_to_the_firm_ones(
        client, operator_user, suggested, norm_unit):
    """REQ-035: "Pasar a requisito" deja la fila `propuesto`, con su historial; aparece
    entre los requisitos con "Pasó de sugerencia el DD/MM/AAAA por <persona>" y su
    respaldo."""
    version, rows, _other = suggested
    add_support(rows[0], norm_unit, version.run)
    log_in(client, operator_user)

    response = client.post(accept_url(rows[0]))

    assert response.status_code == 302
    assert state(rows[0]) == "propuesto"
    page = text_of(client.get(matrix_url(version)))
    firm = page[page.index('id="requirements-title"'):page.index('id="technical-title"')]
    assert f"Requisito {rows[0].number}" in firm
    change = rows[0].changes.get(action="aceptar_sugerencia")
    date = timezone.localtime(change.at).strftime("%d/%m/%Y")
    assert f"Pasó de sugerencia el {date} por operador" in squash(firm)
    assert "Norma sintética, art. 1" in firm
    assert f"Requisito {rows[0].number}" not in section_of(
        page, "<h2 id=\"suggestions-title\"", "Requisitos formales")


def test_remove_a_suggestion_sends_it_to_the_removed_ones(client, operator_user, suggested):
    """REQ-035: "Quitar" deja la fila `quitado`, visible entre los quitados."""
    version, rows, _other = suggested
    log_in(client, operator_user)

    client.post(reverse("tenders:review_remove", args=[rows[1].pk]))

    assert state(rows[1]) == "quitado"
    page = text_of(client.get(matrix_url(version)))
    assert f"Requisito {rows[1].number} " in page[page.index('id="removed-title"'):]


def test_a_user_without_commission_role_is_denied_and_the_attempt_is_recorded(
        client, no_commission_user, suggested):
    """REQ-026/P6: sin rol de la Comisión, 403 en el botón, la página de grupo y la matriz,
    y el rechazo queda registrado; la fila no cambia."""
    version, rows, _other = suggested
    log_in(client, no_commission_user)
    query = {"group": "sec-i/3.1", "action": "pasar"}

    assert client.post(accept_url(rows[0])).status_code == 403
    assert client.get(group_url(version), query).status_code == 403
    assert client.post(group_url(version), query).status_code == 403
    assert client.get(matrix_url(version)).status_code == 403

    assert state(rows[0]) == "sugerido"
    assert AuditEvent.objects.filter(outcome=Outcome.REJECTED).count() >= 3


def test_a_validated_version_refuses_to_decide_a_suggestion(
        client, operator_user, evaluator_user, suggested):
    """REQ-035: solo en un borrador; en una versión ya validada la acción se rechaza con
    el motivo y no cambia nada."""
    version, rows, other = suggested
    for row in rows:
        suggestions.accept_suggestion(operator_user, row.pk)
    review.remove(operator_user, other.pk)
    finish(evaluator_user, version)
    validation.validate(evaluator_user, version.pk)
    log_in(client, operator_user)

    response = client.post(accept_url(rows[0]))

    assert response.status_code == 400
    assert state(rows[0]) == "confirmado"


# --- Decidir por grupo ---------------------------------------------------------------------------


def test_the_group_button_first_shows_the_rows_and_only_accept_applies(
        client, operator_user, suggested):
    """REQ-034: "Pasar a requisito las 3" lleva a la página con las 3 filas y su texto
    literal; nada cambia hasta "Aceptar", que pasa cada fila con su historial y
    `via_grupo`; la fila de otro grupo no se toca."""
    version, rows, other = suggested
    log_in(client, operator_user)

    page = text_of(client.get(group_url(version), {"group": "sec-i/3.1", "action": "pasar"}))

    assert "Pasar a requisito las 3" in squash(page) and "Aceptar" in page
    for row in rows:
        quote = row.quotes.get()
        assert quote.text in page
        assert f"Requisito {row.number}" in page
    assert f"Requisito {other.number}" not in page
    assert {state(r) for r in rows} == {"sugerido"}

    response = client.post(group_url(version), {"group": "sec-i/3.1", "action": "pasar"})

    assert response.status_code == 302
    assert {state(r) for r in rows} == {"propuesto"}
    assert state(other) == "sugerido"
    for row in rows:
        change = row.changes.get(action="aceptar_sugerencia")
        assert change.event.detail["via_grupo"] == "sec-i/3.1"


def test_the_group_remove_button_removes_only_that_group(client, operator_user, suggested):
    """REQ-034: "Quitar las 3" muestra primero las filas y después las quita."""
    version, rows, other = suggested
    log_in(client, operator_user)
    query = {"group": "sec-i/3.1", "action": "quitar"}

    page = text_of(client.get(group_url(version), query))
    assert "Quitar las 3" in squash(page) and {state(r) for r in rows} == {"sugerido"}
    client.post(group_url(version), query)

    assert {state(r) for r in rows} == {"quitado"} and state(other) == "sugerido"


def test_an_unknown_group_action_or_empty_group_is_refused_without_changes(
        client, operator_user, suggested):
    """REQ-034: una acción inventada o un grupo sin sugerencias se rechaza y no cambia
    nada."""
    version, rows, _other = suggested
    log_in(client, operator_user)

    bad = client.post(group_url(version), {"group": "sec-i/3.1", "action": "confirmar"})
    empty = client.post(group_url(version), {"group": "sec-i/9", "action": "pasar"})

    assert bad.status_code == 400 and empty.status_code == 400
    assert {state(r) for r in rows} == {"sugerido"}


# --- Validar y cobertura -------------------------------------------------------------------------


def test_the_validate_button_tells_how_many_suggestions_are_left(
        client, evaluator_user, suggested):
    """REQ-035: "Validar" con sugerencias sin decidir informa cuántas faltan y dónde, y la
    versión sigue en borrador."""
    version, _rows, _other = suggested
    finish(evaluator_user, version)
    log_in(client, evaluator_user)

    response = client.post(reverse("tenders:validate", args=[version.pk]))

    page = squash(text_of(response))
    assert response.status_code == 400
    assert "4 sugerencias" in page and "sec-i/3.1" in page and "sec-i/4.1" in page
    version.refresh_from_db()
    assert version.status == "draft"


def test_the_coverage_shows_the_state_of_each_row(client, operator_user, suggested):
    """REQ-035: la cobertura nombra cada fila de un tramo con su estado; la sugerencia
    figura como tal."""
    version, rows, other = suggested
    suggestions.accept_suggestion(operator_user, rows[0].pk)
    log_in(client, operator_user)

    page = squash(text_of(client.get(reverse("tenders:coverage", args=[version.pk]))))

    assert f"Requisito {rows[0].number}: Propuesto" in page
    assert f"Requisito {rows[1].number}: Sugerencia sin decidir" in page
    assert f"Requisito {other.number}: Sugerencia sin decidir" in page


# --- Impresión y PDF -----------------------------------------------------------------------------


def test_print_view_has_the_section_before_the_requirements_with_support_and_legend(
        client, operator_user, suggested, norm_unit):
    """REQ-032/035: la impresión de un borrador trae "Sugerencias de condición sin
    decidir" justo antes de los requisitos, con cita, ubicación, motivo y respaldo, y la
    leyenda; sin botones de edición."""
    version, rows, _other = suggested
    add_support(rows[1], norm_unit, version.run)
    log_in(client, operator_user)

    page = text_of(client.get(reverse("tenders:print", args=[version.pk])))

    assert page.index(PRINT_SECTION) < page.index("Requisitos formales y económicos")
    assert page.index("Pendiente de revisión") < page.index(PRINT_SECTION)
    assert LEGEND in page and "Pasar a requisito" not in page
    section = squash(section_of(page, PRINT_SECTION, "Requisitos formales"))
    assert rows[0].quotes.get().text in section
    assert "Cláusula" in section and "Las dos preguntas del sistema no coincidieron" in section
    assert "Norma sintética, art. 1" in section and "Artículo 1." in section
    assert section.count(NO_SUPPORT) == 3


def pdf_pages(data):
    with pdfplumber.open(io.BytesIO(data)) as document:
        return [" ".join((page.extract_text() or "").split()) for page in document.pages]


def test_every_page_of_the_pdf_with_suggestions_has_the_legend_and_the_section(
        operator_user, suggested, norm_unit):
    """REQ-032: el PDF de un borrador con sugerencias lleva la sección y "BORRADOR
    INCOMPLETO" en cada página (se suman sugerencias hasta pasar de una página)."""
    version, rows, _other = suggested
    add_support(rows[0], norm_unit, version.run)
    for index in range(30):
        make_suggestion(version, "sec-i/4.1", start=index % 3, reason="duda")

    data, _name = export.export_pdf(operator_user, version.pk)

    pages = pdf_pages(data)
    assert len(pages) >= 2
    assert all(LEGEND in text for text in pages)
    assert any(PRINT_SECTION in text for text in pages)


def test_a_validated_version_has_no_section_and_the_row_from_a_suggestion_shows_its_origin(
        client, operator_user, evaluator_user, suggested, norm_unit):
    """REQ-035: una versión validada no tiene la sección, ni en pantalla ni en la
    impresión; el requisito que vino de una sugerencia muestra su origen y su respaldo."""
    version, rows, other = suggested
    add_support(rows[0], norm_unit, version.run)
    for row in rows:
        suggestions.accept_suggestion(operator_user, row.pk)
    review.remove(operator_user, other.pk)
    finish(evaluator_user, version)
    validation.validate(evaluator_user, version.pk)
    log_in(client, evaluator_user)

    screen = text_of(client.get(matrix_url(version)))
    printed = text_of(client.get(reverse("tenders:print", args=[version.pk])))

    assert SECTION not in screen and PRINT_SECTION not in printed
    assert LEGEND not in printed
    assert "Pasó de sugerencia el" in squash(screen)
    assert "Pasó de sugerencia el" in squash(printed)
    assert "Norma sintética, art. 1" in squash(printed)


def test_no_page_references_external_addresses(client, operator_user, suggested, norm_unit):
    """P4: ni la matriz, ni la impresión, ni la página de grupo, ni la cobertura apuntan a
    direcciones externas."""
    version, rows, _other = suggested
    add_support(rows[0], norm_unit, version.run)
    log_in(client, operator_user)
    urls = [matrix_url(version), reverse("tenders:print", args=[version.pk]),
            reverse("tenders:coverage", args=[version.pk])]

    bodies = [client.get(url).content.decode() for url in urls]
    bodies.append(client.get(group_url(version),
                             {"group": "sec-i/3.1", "action": "pasar"}).content.decode())

    for body in bodies:
        assert not re.search(r"(?:href|src|action)=\"(?:https?:)?//", body)
        assert "http://" not in body and "https://" not in body
