"""Evaluación legible (plan 014, T-228; REQ-089, REQ-090, REQ-098): el punto completo del pliego en
cada celda, pendiente y pregunta; las preguntas con su contexto; los requisitos externos aparte
con lo que falta; y qué se leyó cuando no hay cita de la oferta. Los resultados se guardan
directo, sin el modelo (la GPU no se comparte); todo el material es inventado (P4)."""

import html as htmllib
import re
from types import SimpleNamespace

import pytest
from django.urls import reverse

from django.db import connection

from evaluon.assessment import externals, grounds
from evaluon.assessment import models as am
from evaluon.journey import points
from evaluon.journey import reading_note as reading
from evaluon.journey.sections import sections_for
from tests.accounts.test_session import TEST_PASSWORD
from tests.assessment.test_matrix import (  # noqa: F401  (fixtures y ayudas)
    add_run,
    decide,
    evaluated,
    requirement,
    three,
)
from tests.journey.conftest import simulate  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def tab(procedure):
    return reverse("expedientes:evaluacion", args=[procedure.pk])


def page(client, procedure, query=""):
    response = client.get(tab(procedure) + query)
    assert response.status_code == 200
    return response.content.decode()


def plain(html):
    """El texto visible: sin etiquetas, sin escapes y con los espacios colapsados."""
    return " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", html)).split())


def squash(text):
    return " ".join(text.split())


def detail_of(html, number):
    start = html.index(f'id="ev-det-{number}"')
    return html[start:html.index("</tr>", start)]


def firm(procedure):
    version = procedure.matrix_versions.get(number=1)
    return list(version.requirements.exclude(state__in=("quitado", "sugerido"))
                .order_by("number"))


def first_quote(row):
    return row.quotes.order_by("order").first()


# --- Punto 1: el punto completo del pliego ------------------------------------------------------


def fake_segment(text, *, label="7.1.", start=0):
    reading_ = SimpleNamespace(document=SimpleNamespace(title="Pliego de prueba"))
    return SimpleNamespace(pk=1, text=text, label=label, path="Cláusula 7", char_start=start,
                           reading=reading_)


def fake_quote(segment, fragment, *, current=None, source=None):
    """La cita `fragment` del tramo, como el texto vigente que arma `grounds.requirement_text`
    (`current` es el texto que dejó una circular)."""
    at = segment.text.index(fragment)
    quote = SimpleNamespace(text=fragment, char_start=segment.char_start + at,
                            char_end=segment.char_start + at + len(fragment), scope="")
    if current is None:
        return grounds.QuoteText(quote, text=fragment)
    return grounds.QuoteText(quote, text=current, original=fragment, source=source)


def test_a_point_is_the_whole_segment_with_the_requirement_fragment_marked():
    """REQ-089: el punto es el texto completo del tramo, con su encabezado, y el fragmento del
    requisito va marcado (no solo el pedazo)."""
    text = ('La documentación que se solicite en el presente punto se deberá adjuntar '
            'electrónicamente en el sistema "Portal de Compras", en caso que corresponda.')
    segment = fake_segment(text, start=500)
    point = points.build(segment, [fake_quote(segment, "se deberá adjuntar electrónicamente")])
    assert point.label == "7.1." and point.text == text and not point.long
    assert [t for t, marked in point.parts if marked] == ["se deberá adjuntar electrónicamente"]
    assert point.head == point.parts


def test_a_long_point_shows_its_first_lines_and_keeps_the_whole_text_apart():
    """REQ-089: un punto largo muestra las primeras líneas y el texto completo para «ver todo»."""
    text = "\n".join(f"Línea {n} del punto con bastante texto inventado." for n in range(1, 21))
    segment = fake_segment(text)
    point = points.build(segment, [fake_quote(segment, "Línea 2 ")])
    assert point.long and point.text == text and point.chars == len(text)
    shown = "".join(t for t, _ in point.head)
    assert "Línea 1 " in shown and "Línea 20" not in shown


def test_a_fragment_beyond_the_first_lines_is_still_visible_in_the_short_view():
    """REQ-089: si el fragmento queda lejos del comienzo, la vista corta lo incluye marcado."""
    text = "\n".join(f"Línea {n} del punto con bastante texto inventado." for n in range(1, 31))
    segment = fake_segment(text)
    point = points.build(segment, [fake_quote(segment, "Línea 25 del punto")])
    assert point.long
    assert [t for t, marked in point.head if marked] == ["Línea 25 del punto"]


def test_every_cell_detail_shows_the_whole_point_with_the_fragment_marked(
        client, evaluated, procedure, operator_user):
    """REQ-089: en el detalle de cada requisito de la evaluación (100 %) figura el punto completo
    del pliego, con su encabezado, y el fragmento citado resaltado con <mark>."""
    log_in(client, operator_user)
    html = page(client, procedure)
    rows = firm(procedure)
    assert rows
    for row in rows:
        quote = first_quote(row)
        segment = quote.segment
        detail = detail_of(html, row.number)
        assert 'class="punto-pliego"' in detail, f"requisito {row.number}"
        assert squash(segment.text) in plain(detail), f"requisito {row.number}"
        marked = [squash(htmllib.unescape(m)) for m in re.findall(r"<mark>(.*?)</mark>", detail,
                                                                  re.S)]
        assert squash(quote.text) in marked, f"requisito {row.number}"
        if segment.label:
            assert htmllib.escape(segment.label.strip()) in detail


def test_the_pair_page_shows_the_whole_point_too(client, evaluated, procedure, operator_user):
    """REQ-089: el detalle del par (oferta × requisito) también muestra el punto completo."""
    declaration = requirement(procedure, "declaración jurada")
    log_in(client, operator_user)
    url = reverse("expedientes:s4_par", args=[procedure.pk, evaluated[0].pk, declaration.pk])
    response = client.get(url)
    assert response.status_code == 200
    html = response.content.decode()
    assert 'class="punto-pliego"' in html
    assert squash(first_quote(declaration).segment.text) in plain(html)


# --- Punto 1 y 2: pendientes -------------------------------------------------------------------


def test_every_pending_pair_and_open_question_carries_its_point(
        evaluated, procedure, evaluator_user):
    """REQ-098: cada pendiente individual (par por decidir, pregunta abierta) trae el punto
    completo de su requisito."""
    declaration = requirement(procedure, "declaración jurada")
    guarantee = requirement(procedure, "garantía de mantenimiento")
    a, b, c = evaluated
    result = am.Result.objects.get(offer=c, requirement=guarantee)
    am.Question.objects.create(procedure=procedure, requirement=guarantee, offer=c,
                               result=result, text="¿Está vigente?")
    # Se deciden algunos pares para que los que quedan no se agrupen en una sola línea.
    for result_ in am.Result.objects.exclude(requirement=declaration).exclude(
            offer=c, requirement=guarantee)[:6]:
        decide(evaluator_user, result_, "confirmar")
    items = sections_for(evaluator_user, procedure).get("evaluacion").pending_items
    individual = [i for i in items if i.kind in ("par", "pregunta")]
    assert len(individual) >= 3 and any(i.kind == "pregunta" for i in individual)
    for item in individual:
        assert item.points, item.text
        assert item.points[0].text, item.text
    mine = next(i for i in individual if i.kind == "pregunta")
    assert mine.points[0].text == first_quote(guarantee).segment.text


def test_the_pending_panel_shows_the_point_of_each_item(
        client, evaluated, procedure, evaluator_user):
    """REQ-098: el panel de pendientes de la pestaña dibuja el punto completo de cada pendiente."""
    declaration = requirement(procedure, "declaración jurada")
    for result_ in am.Result.objects.exclude(requirement=declaration):
        decide(evaluator_user, result_, "confirmar")
    log_in(client, evaluator_user)
    html = page(client, procedure)
    start = html.index('id="pendientes"')
    panel = html[start:html.index("</section>", start)]
    items = re.findall(r"<li>(.*?)</li>", panel, re.S)
    of_requirements = [i for i in items if re.search(r"requisito \d+", plain(i))]
    assert of_requirements
    for item in of_requirements:
        assert 'class="punto-pliego"' in item, plain(item)
    assert squash(first_quote(declaration).segment.text) in plain(panel)


# --- Punto 2: preguntas con su contexto --------------------------------------------------------


def block(client, procedure, user):
    log_in(client, user)
    html = page(client, procedure)
    start = html.index('id="s4-preguntas"')
    end = html.find('id="s4-informe"', start)
    return html[start:] if end < 0 else html[start:end]


def test_a_question_brings_its_requirement_offer_cited_fragment_and_original_link(
        client, evaluated, procedure, evaluator_user):
    """REQ-090: cada pregunta trae en el mismo lugar el requisito (número y punto completo), la
    oferta, el fragmento citado con documento y página, y el enlace al original."""
    guarantee = requirement(procedure, "garantía de mantenimiento")
    c = evaluated[2]
    result = am.Result.objects.get(offer=c, requirement=guarantee)
    document = c.documents.first()
    reading_ = document.readings.get()
    am.Citation.objects.create(
        result=result, order=9, kind=am.CitationKind.OFERTA, document=document,
        reading=reading_, page=1, char_start=0, char_end=12, text=reading_.canonical_text[:12])
    question = am.Question.objects.create(
        procedure=procedure, requirement=guarantee, offer=c, result=result,
        text="¿Este requisito está cumplido?", reason="No se pudo determinar")
    html = block(client, procedure, evaluator_user)
    start = html.index(f'id="preg-{question.pk}"')
    mine = html[start:html.index("</tbody>", start)]
    text = plain(mine)
    assert f"Requisito {guarantee.number}" in text
    assert squash(first_quote(guarantee).segment.text) in text
    assert 'class="punto-pliego"' in mine and "<mark>" in mine
    assert f"Oferta {c.number}" in text and c.bidder in text
    assert htmllib.escape(reading_.canonical_text[:12]) in mine
    assert f"{document.title} · página 1" in text
    assert f'href="{reverse("offers:document_original", args=[document.pk])}#page=1"' in mine


def test_every_question_and_remedy_line_has_its_context(
        client, evaluated, procedure, evaluator_user):
    """REQ-090: todas las filas del bloque (preguntas y subsanaciones, 100 %) traen el punto
    completo de su requisito."""
    guarantee = requirement(procedure, "garantía de mantenimiento")
    c = evaluated[2]
    am.Question.objects.create(
        procedure=procedure, requirement=guarantee, offer=c,
        result=am.Result.objects.get(offer=c, requirement=guarantee), text="¿Vigente?")
    html = block(client, procedure, evaluator_user)
    rows = re.findall(r'<tbody class="linea" id="(?:preg|sub)-\d+">(.*?)</tbody>', html, re.S)
    assert len(rows) >= 2  # la pregunta y la subsanación de la constancia (sin documento)
    for row in rows:
        assert 'class="punto-pliego"' in row


def test_without_offer_text_the_explanation_says_what_was_read_and_where(
        client, evaluated, procedure, operator_user):
    """REQ-089: cuando el resultado no tiene cita de la oferta, la explicación dice qué documentos
    y páginas se leyeron (según los pedidos al modelo de la corrida)."""
    guarantee = requirement(procedure, "garantía de mantenimiento")
    c = evaluated[2]
    document = c.documents.first()
    # Una evaluación nueva de la oferta C (las filas guardadas no se modifican) que guarda lo leído.
    version = procedure.matrix_versions.get(number=1)
    request = am.Request.objects.create(
        procedure=procedure, matrix_version=version, offers=[c.pk], requirements=None,
        cause=am.Cause.MATRIZ, requested_by=operator_user)
    run = am.Run.objects.create(
        request=request, offer=c, matrix_version=version, number=c.assessment_runs.count() + 1,
        channel=am.Channel.SCREEN, norms={}, models_used={}, parameters={}, prompt_versions={},
        documents=[{"document": document.pk, "title": document.title, "pages": 3,
                    "unread_pages": []}])
    am.Result.objects.create(run=run, offer=c, requirement=guarantee, outcome="no_determinado",
                             doubt="duda", exigence=am.Exigence.CONDICION, explanation="Dudó.")
    am.Step.objects.create(run=run, offer=c, requirement=guarantee, purpose=am.Purpose.GRUPO,
                           group_index=1, documents=[
                               {"document": document.pk, "tokens": 10, "pages": [1, 2]},
                               {"relevance": {}, "query": "x", "rewrite": ""}])
    log_in(client, operator_user)
    html = page(client, procedure)
    detail = plain(detail_of(html, guarantee.number))
    assert "Sin texto de la oferta que respalde una conclusión" in detail
    assert f"Se leyó: «{document.title}» (páginas 1 a 2)" in detail
    # El detalle del par dice lo mismo.
    response = client.get(reverse("expedientes:s4_par",
                                  args=[procedure.pk, c.pk, guarantee.pk]))
    assert f"Se leyó: «{document.title}» (páginas 1 a 2)" in plain(response.content.decode())


def test_without_a_record_of_the_reading_it_says_so():
    """REQ-089: sin pedidos ni documentos en la corrida, «no quedó registrado qué se leyó»."""
    run = SimpleNamespace(documents=[])
    assert reading.note_for(run, []) == "No quedó registrado qué se leyó."


def test_the_reading_note_joins_the_page_ranges_and_names_unread_pages():
    """REQ-089: las páginas leídas se unen en rangos y las ilegibles se nombran."""
    run = SimpleNamespace(documents=[
        {"document": 7, "title": "oferta.pdf", "pages": 6, "unread_pages": [4]},
        {"document": 8, "title": "hoja.pdf", "pages": 1, "unread_pages": []}])
    steps = [[{"document": 7, "tokens": 5, "pages": [1, 2]}],
             [{"document": 7, "tokens": 5, "pages": [2, 3]}, {"document": 8, "tokens": 1}]]
    note = reading.note_for(run, steps)
    assert "«oferta.pdf» (páginas 1 a 3)" in note and "«hoja.pdf» (página 1)" in note
    assert "página 4 de «oferta.pdf»" in note


# --- Punto 3: requisitos externos aparte -------------------------------------------------------


@pytest.fixture
def external_catalog(monkeypatch):
    """El catálogo de la evaluación reconoce la constancia de inscripción como externa."""
    check = externals._check("prueba", "Registro de Proveedores", r"constancia de inscripcion")
    monkeypatch.setattr(externals, "CATALOG", externals.CATALOG + (check,))
    return check


def test_external_requirements_show_from_the_start_with_what_each_offer_lacks(
        client, procedure, three, evaluator_user, external_catalog):
    """REQ-089: antes de evaluar, los requisitos externos figuran en un grupo aparte y, por oferta,
    dice qué falta con el botón para subir la hoja (solo el evaluador)."""
    registry = requirement(procedure, "constancia de inscripción")
    log_in(client, evaluator_user)
    html = page(client, procedure)
    start = html.index('id="s4-externos"')
    block_ = html[start:html.index("</section>", start)]
    assert "Requisitos que se cumplen con información externa" in block_
    assert f"Requisito {registry.number}" in plain(block_)
    assert 'class="punto-pliego"' in block_
    for offer in three:
        assert f"Falta la hoja de compliance de la oferta {offer.number}" in plain(block_)
        assert reverse("expedientes:s3_anexos_hoja", args=[procedure.pk, offer.pk]) in block_
    assert "Registro de Proveedores" in block_


def test_an_operator_sees_what_is_missing_but_not_the_upload_buttons(
        client, procedure, three, operator_user, external_catalog):
    """REQ-089: el operador ve qué hoja falta pero no los botones (la sube un evaluador)."""
    log_in(client, operator_user)
    html = page(client, procedure)
    start = html.index('id="s4-externos"')
    block_ = html[start:html.index("</section>", start)]
    assert f"Falta la hoja de compliance de la oferta {three[0].number}" in plain(block_)
    assert "<form" not in block_ and "la sube un evaluador" in plain(block_).lower()


def test_in_the_table_the_external_requirements_are_a_separate_marked_group(
        client, evaluated, procedure, operator_user, external_catalog):
    """REQ-089: en la tabla de la evaluación, los externos (100 %) forman un grupo propio con su
    marca y no figuran entre los formales."""
    registry = requirement(procedure, "constancia de inscripción")
    log_in(client, operator_user)
    html = page(client, procedure)
    group = re.search(r'<tr class="grupo grupo-externo" data-tipo="externo">', html)
    assert group, "no hay grupo de externos"
    after = html[group.end():]
    following = re.search(r'<tr class="grupo', after)
    region = after[:following.start()] if following else after
    rows = re.findall(r'<tr class="fila-req fila-externa" data-numero="(\d+)"', region)
    assert rows == [str(registry.number)]
    assert "marca-externa" in region
    # Fuera de su grupo no figura (no se repite entre los formales).
    outside = html[:group.start()] + (after[following.start():] if following else "")
    assert f'data-numero="{registry.number}"' not in outside


def test_a_requirement_flagged_by_the_model_is_grouped_too(
        client, evaluated, procedure, operator_user):
    """REQ-089: el requisito que el modelo marcó «falta la hoja de compliance» en alguna oferta
    también va al grupo de externos."""
    registry = requirement(procedure, "constancia de inscripción")
    add_run(operator_user, procedure, evaluated[2], {registry: ("no_determinado", "externo")})
    log_in(client, operator_user)
    html = page(client, procedure)
    assert 'data-tipo="externo"' in html
    assert f"Requisito {registry.number}" in plain(html[html.index('id="s4-externos"'):])


def test_the_offers_summary_says_which_sheet_is_missing_and_how_many_requirements_wait_for_it(
        client, procedure, three, evaluator_user, external_catalog):
    """REQ-089: el resumen de Ofertas dice «falta la hoja de compliance de la oferta N» y cuántos
    requisitos externos esperan esa hoja, con el botón para subirla."""
    registry = requirement(procedure, "constancia de inscripción")
    log_in(client, evaluator_user)
    response = client.get(reverse("expedientes:ofertas", args=[procedure.pk]))
    assert response.status_code == 200
    text = plain(response.content.decode())
    for offer in three:
        assert f"Falta la hoja de compliance de la oferta {offer.number}" in text
    assert f"requisito {registry.number}" in text.lower()
    assert reverse("expedientes:s3_anexos_hoja", args=[procedure.pk, three[0].pk]) in \
        response.content.decode()


# --- Correcciones de la verificación: circulares y filas de «falta la hoja» ----------------------


def add_circular(requirement_, text, *, effect="modifica", day="2026-02-01"):
    """Una circular que cambia la cita del requisito (las filas de una matriz validada solo
    admiten inserciones en un borrador: se apaga el disparador mientras dura la prueba)."""
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE tenders_requirement_source DISABLE TRIGGER USER")
    quote = requirement_.quotes.get()
    return requirement_.sources.create(
        quote=quote, effect=effect, segment=quote.segment, char_start=quote.char_start,
        char_end=quote.char_end, text=text, issued_on=day)


def test_a_circular_that_makes_a_requirement_external_groups_it(
        client, procedure, three, evaluator_user):
    """REQ-089 (D-1): el grupo de externos usa el texto vigente después de las circulares, como la
    evaluación: una circular que vuelve externo un requisito lo agrupa antes de evaluar."""
    validity = requirement(procedure, "sesenta días")
    add_circular(validity, "La Comisión verificará la inscripción del oferente en el Registro "
                           "de Proveedores.")
    assert externals.match(grounds.requirement_text(validity).context)  # la evaluación lo ve
    log_in(client, evaluator_user)
    html = page(client, procedure)
    assert 'id="s4-externos"' in html
    block_ = html[html.index('id="s4-externos"'):]
    assert f"Requisito {validity.number}" in plain(block_[:block_.index("</section>")])


def test_a_circular_that_stops_a_requirement_being_external_ungroups_it(
        client, procedure, three, evaluator_user, external_catalog):
    """REQ-089 (D-1): una circular que deja de hacer externo a un requisito lo saca del grupo,
    como la evaluación, que ya no lo trata como externo."""
    registry = requirement(procedure, "constancia de inscripción")
    add_circular(registry, "El oferente acompañará una nota firmada.")
    assert not externals.match(grounds.requirement_text(registry).context)
    log_in(client, evaluator_user)
    html = page(client, procedure)
    assert 'id="s4-externos"' not in html and "grupo-externo" not in html


def test_the_point_shows_the_current_text_and_folds_the_original_after_a_circular(
        client, evaluated, procedure, operator_user):
    """REQ-089 (O-3): si una circular cambió el requisito, el punto muestra el texto vigente con el
    cambio marcado, dice por qué circular y deja el original plegado."""
    validity = requirement(procedure, "sesenta días")
    original = validity.quotes.get().text
    add_circular(validity, "Mantener la validez de la oferta por noventa días corridos.")
    log_in(client, operator_user)
    html = page(client, procedure)
    detail = detail_of(html, validity.number)
    marked = [squash(htmllib.unescape(m)) for m in re.findall(r"<mark>(.*?)</mark>", detail, re.S)]
    assert "Mantener la validez de la oferta por noventa días corridos." in marked
    text = plain(detail)
    assert "Modificado por la circular" in text and "01/02/2026" in text
    folded = re.search(r'<details class="punto-ver punto-original">(.*?)</details>', detail, re.S)
    assert folded and squash(original) in plain(folded.group(1))
    assert "Ver el texto original" in plain(folded.group(1))
    assert squash(original) not in plain(detail.replace(folded.group(0), ""))


def test_a_point_marks_the_current_text_inside_the_whole_segment():
    """REQ-089 (O-3): el punto es el tramo entero con el texto vigente en el lugar del fragmento."""
    text = "Antes. Mantener la validez por sesenta días. Después."
    segment = fake_segment(text)
    source = SimpleNamespace(effect="modifica", issued_on=None, segment=SimpleNamespace(
        reading=SimpleNamespace(document=SimpleNamespace(title="Circular 3"))))
    point = points.build(segment, [fake_quote(segment, "Mantener la validez por sesenta días.",
                                              current="Mantener la validez por noventa días.",
                                              source=source)])
    assert point.text == "Antes. Mantener la validez por noventa días. Después."
    assert [t for t, marked in point.parts if marked] == ["Mantener la validez por noventa días."]
    assert [c.original for c in point.changes] == ["Mantener la validez por sesenta días."]
    assert "circular 3" in point.changes[0].note.lower()


def _result_with_reading(procedure, offer, requirement_, doubt, user):
    """Una evaluación nueva de `offer` con lo leído registrado y el requisito en `doubt`."""
    document = offer.documents.first()
    version = procedure.matrix_versions.get(number=1)
    request = am.Request.objects.create(
        procedure=procedure, matrix_version=version, offers=[offer.pk], requirements=None,
        cause=am.Cause.MATRIZ, requested_by=user)
    run = am.Run.objects.create(
        request=request, offer=offer, matrix_version=version,
        number=offer.assessment_runs.count() + 1, channel=am.Channel.SCREEN, norms={},
        models_used={}, parameters={}, prompt_versions={},
        documents=[{"document": document.pk, "title": document.title, "pages": 3,
                    "unread_pages": []}])
    result = am.Result.objects.create(
        run=run, offer=offer, requirement=requirement_, outcome="no_determinado", doubt=doubt,
        exigence=am.Exigence.CONDICION, explanation="Falta la hoja.")
    am.Step.objects.create(run=run, offer=offer, requirement=requirement_,
                           purpose=am.Purpose.GRUPO, group_index=1,
                           documents=[{"document": document.pk, "tokens": 5, "pages": [1, 2]}])
    return result


def test_a_missing_sheet_row_does_not_say_what_was_read(
        client, evaluated, procedure, evaluator_user):
    """REQ-089 (O-2): en las filas de «falta la hoja de compliance» (celda, detalle del par y
    subsanación) no figura el «Se leyó…»; en las demás, sí."""
    registry = requirement(procedure, "constancia de inscripción")
    guarantee = requirement(procedure, "garantía de mantenimiento")
    c = evaluated[2]
    _result_with_reading(procedure, c, registry, "externo", evaluator_user)
    _result_with_reading(procedure, c, guarantee, "duda", evaluator_user)
    log_in(client, evaluator_user)
    html = page(client, procedure)
    assert "Se leyó" not in plain(detail_of(html, registry.number))
    assert "Sin texto de la oferta que respalde una conclusión" in plain(
        detail_of(html, registry.number))
    assert "Se leyó" in plain(detail_of(html, guarantee.number))
    response = client.get(reverse("expedientes:s4_par", args=[procedure.pk, c.pk, registry.pk]))
    assert "Se leyó" not in plain(response.content.decode())
    start = html.index('id="s4-preguntas"')
    lines = re.findall(r'<tbody class="linea" id="sub-\d+">(.*?)</tbody>', html[start:], re.S)
    external_line = [line for line in lines if "falta la hoja de compliance" in plain(line).lower()]
    assert external_line and all("Se leyó" not in plain(line) for line in external_line)
