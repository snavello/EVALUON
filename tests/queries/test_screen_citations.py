"""Citas de la pantalla de consulta con categoría, papel y cambios (T-037; plan 001,
"Pantalla, acceso y comandos", "Forma de la respuesta", "Cita" y "Texto normativo sin
número de artículo").

Las consultas se guardan a mano con la forma del resultado de `answering` (T-034):
afirmaciones en orden con sus citas y `regimes_differ`, y `units` con la categoría, el
tipo, la ruta, el origen del texto, el documento, la página y, con fecha, los `changes`.
El texto literal no viaja en el resultado: la pantalla lo lee de la base. Todos los
textos son sintéticos (P4).
"""

import html
import re
from datetime import date

import pytest
from django.urls import reverse

from evaluon.audit import services as audit_services
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.norms.models import Unit
from evaluon.queries.models import Query
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db

REGIMES_DIFFER_NOTICE = ("El régimen específico y el marco nacional tratan este punto "
                         "de manera distinta. Se aplica el régimen específico.")
APPLICABLE_LABEL = "Texto aplicable"
ORIGINAL_LINK_TEXT = "Abrir el documento original"
OCR_NOTICE = "reconocimiento sobre la imagen"
TEXT_SHOWN_ABOVE = "El texto de esta cita se muestra"
CHANGE_TEXT_MISSING = "El texto que trae el cambio no está disponible."

ROLE_LABELS = {
    "regimen_especifico": "Régimen específico · es lo que se aplica",
    "otra_normativa": "Otra normativa aplicable · se aplica en lo que trata",
    "marco_nacional": "Marco nacional · marco de referencia",
    "dictamen_legal": "Dictamen legal · criterio que acompaña",
    "recomendacion_auditoria": "Recomendación de auditoría · criterio que acompaña",
}
CONSIDERANDO_LABEL = "Régimen específico · Considerando · contexto"

REFERENCE_DATE = date(2024, 5, 20)


# --- Normativa sintética ----------------------------------------------------------------


@pytest.fixture
def corpus(make_norm, make_document, make_reading):
    """Una norma por categoría, una modificatoria y sus unidades.

    - `re`: régimen específico en PDF, con un considerando, dos artículos (páginas 3 y
      4), un inciso del segundo, el anexo y su cláusula transitoria (página 9).
    - `other`: otra normativa aplicable en PDF, un artículo.
    - `mn`: marco nacional como página web, un artículo, sin páginas.
    - `dl`: dictamen legal en PDF escaneado, un punto leído por reconocimiento (página 2).
    - `ra`: recomendación de auditoría en PDF, un punto.
    - `mod`: modificatoria del régimen específico, en PDF, un artículo en la página 1.
    """

    def norm_with(category, citation, file_format, units):
        norm = make_norm(category=category, citation=citation)
        document = make_document(norm, file_format=file_format)
        reading = make_reading(document, units)
        return norm, document, reading.units_by_key

    re_norm, re_doc, re_units = norm_with(
        "regimen_especifico", "Disposición sintética 101/2020", "pdf", [
            {"key": "considerando-1", "text": "Que es necesario ordenar el régimen.",
             "page_start": 1, "page_end": 1},
            {"key": "art-1", "text": "ARTICULO 1.- Las garantías son del cinco por ciento.",
             "page_start": 3, "page_end": 3},
            {"key": "art-2", "text": "ARTICULO 2.- Los plazos son de diez días.",
             "page_start": 4, "page_end": 4},
            {"key": "art-2/inc-b", "text": "b) plazo de impugnación.",
             "page_start": 4, "page_end": 4},
            {"key": "anexo", "text": "ANEXO", "page_start": 9, "page_end": 9},
            {"key": "anexo/clausula-transitoria",
             "text": "CLÁUSULA TRANSITORIA REGISTRO SINTÉTICO El registro sigue vigente.",
             "label": "CLÁUSULA TRANSITORIA REGISTRO SINTÉTICO",
             "path": "Anexo › Cláusula transitoria",
             "page_start": 9, "page_end": 9},
        ])
    other_norm, other_doc, other_units = norm_with(
        "otra_normativa", "Resolución sintética 55/2019", "pdf",
        [{"key": "art-5", "text": "ARTICULO 5.- Otra regla sintética.", "page_start": 2}])
    mn_norm, mn_doc, mn_units = norm_with(
        "marco_nacional", "Decreto sintético 1030/2016", "html",
        [{"key": "art-10", "text": "ARTICULO 10.- Las garantías son del diez por ciento.",
          "text_origin": "web"}])
    dl_norm, dl_doc, dl_units = norm_with(
        "dictamen_legal", "Dictamen sintético 7/2021", "pdf",
        [{"key": "punto-1", "text": "1. La garantía se interpreta en sentido estricto.",
          "text_origin": "ocr", "page_start": 2, "page_end": 2,
          "ocr_confidence_min": 80.0, "ocr_confidence_avg": 91.0}])
    ra_norm, ra_doc, ra_units = norm_with(
        "recomendacion_auditoria", "Informe sintético de auditoría 3/2022", "pdf",
        [{"key": "punto-1", "text": "1. Se recomienda controlar las garantías.",
          "page_start": 5}])
    mod_norm, mod_doc, mod_units = norm_with(
        "regimen_especifico", "Disposición sintética 202/2021", "pdf",
        [{"key": "art-1", "text": "ARTICULO 1.- Sustitúyese el plazo por quince días.",
          "page_start": 1, "page_end": 1}])

    def get(units, key):
        return Unit.objects.select_related("reading__document__norm").get(
            pk=units[key].pk)

    return {
        "considerando": get(re_units, "considerando-1"),
        "re_art_1": get(re_units, "art-1"),
        "re_art_2": get(re_units, "art-2"),
        "re_inc_b": get(re_units, "art-2/inc-b"),
        "clausula": get(re_units, "anexo/clausula-transitoria"),
        "other": get(other_units, "art-5"),
        "mn": get(mn_units, "art-10"),
        "dl": get(dl_units, "punto-1"),
        "ra": get(ra_units, "punto-1"),
        "mod": get(mod_units, "art-1"),
    }


def canonical(unit):
    return unit.reading.canonical_text[unit.char_start:unit.char_end]


def entry(unit, changes=()):
    """Una unidad en `units`, como la guarda `answering` con fecha."""
    norm = unit.reading.document.norm
    return {
        "norm": norm.citation,
        "category": norm.category,
        "unit_type": unit.unit_type,
        "path": unit.path,
        "text_origin": unit.text_origin,
        "document": unit.reading.document_id,
        "page_start": unit.page_start,
        "changes": list(changes),
    }


def change(source, target_key, relation_type="modifica", effective_date="2010-05-01"):
    return {"relation_type": relation_type,
            "unit": source.pk if source is not None else None,
            "target_unit_key": target_key, "effective_date": effective_date}


def statement(text, *units, differ=False):
    return {"text": text, "regimes_differ": differ,
            "citations": [unit.pk for unit in units]}


def grounded(statements, units, extra_units=()):
    """Resultado con fundamento. `units` se arma con cada unidad citada, en el orden en
    que aparece, y con `extra_units` (pares `(unidad, entrada)`)."""
    by_id = {}
    for unit in units:
        by_id.setdefault(str(unit.pk), entry(unit))
    for unit, unit_entry in extra_units:
        by_id[str(unit.pk)] = unit_entry
    return {
        "query_id": None,
        "status": "grounded",
        "reason": None,
        "reference_date": REFERENCE_DATE.isoformat(),
        "regime": [{"norm": 1, "name": "Disposición sintética 101/2020"}],
        "notices": [],
        "statements": statements,
        "units": by_id,
    }


def save_query(user, result, question="¿Qué garantía se exige?"):
    event = audit_services.record(
        EventType.QUERY, outcome=Outcome.OK, channel=Channel.SCREEN, user=user,
        detail={"question": question, "result": result},
    )
    return Query.objects.create(
        event=event, user=user, question=question,
        reference_date=date.fromisoformat(result["reference_date"]),
        corpus_version=event.corpus_version, status=result["status"],
        reason=result["reason"] or "", result=result,
    )


def page(client, user, result):
    assert client.login(username=user.username, password=TEST_PASSWORD)
    query = save_query(user, result)
    response = client.get(reverse("queries:query", args=[query.pk]))
    assert response.status_code == 200
    return response.content.decode()


def citations(body):
    """Cada cita de la página, en orden: `(id de unidad, contenido)`."""
    return [(int(m.group(1)), m.group(2)) for m in re.finditer(
        r'<details class="citation" data-unit="(\d+)"[^>]*>(.*?)</details>', body, re.S)]


def citation_of(body, unit):
    found = [content for unit_id, content in citations(body) if unit_id == unit.pk]
    assert found, f"falta la cita de la unidad {unit.pk}"
    return found[0]


def literals(fragment):
    return re.findall(r'<blockquote class="literal">(.*?)</blockquote>', fragment, re.S)


def statement_blocks(body):
    """Cada afirmación de la página, en orden, con su contenido."""
    block = re.search(r'<ol class="statements">(.*)</ol>', body, re.S).group(1)
    return re.split(r'<li class="statement">', block)[1:]


def summary(fragment):
    return re.search(r"<summary>(.*?)</summary>", fragment, re.S).group(1)


# --- REQ-013: texto literal y documento original -----------------------------------------


def test_citation_shows_literal_text_and_link_to_original_pdf_page(
    client, read_user, corpus
):
    """REQ-013: al desplegar una cita se ve el texto literal de la unidad, igual carácter
    por carácter a `canonical_text[char_start:char_end]`, y el enlace "Abrir el documento
    original", que abre el PDF en otra pestaña en la página de la unidad."""
    art = corpus["re_art_1"]
    body = page(client, read_user, grounded(
        [statement("La garantía es del cinco por ciento.", art)], [art]))

    content = citation_of(body, art)
    assert literals(content) == [html.escape(canonical(art))]
    url = reverse("norms:original", args=[art.reading.document_id])
    assert url == f"/normas/documentos/{art.reading.document_id}/original/"
    link = re.search(rf'<a href="{re.escape(url)}#page=3"([^>]*)>{ORIGINAL_LINK_TEXT}</a>',
                     content)
    assert link, "falta el enlace al original en la página 3"
    assert 'target="_blank"' in link.group(1)
    assert 'rel="noopener"' in link.group(1)


def test_link_to_original_web_page_has_no_page(client, read_user, corpus):
    """REQ-013: el enlace al original de una página web guardada no lleva número de
    página y también abre en otra pestaña."""
    mn = corpus["mn"]
    body = page(client, read_user, grounded([statement("Marco.", mn)], [mn]))

    content = citation_of(body, mn)
    url = reverse("norms:original", args=[mn.reading.document_id])
    link = re.search(r'<a href="([^"]*)"([^>]*)>' + ORIGINAL_LINK_TEXT + "</a>", content)
    assert link.group(1) == url
    assert 'target="_blank"' in link.group(2) and 'rel="noopener"' in link.group(2)


def test_literal_text_is_the_canonical_slice_not_the_text_column(
    client, read_user, corpus
):
    """REQ-013 (REQ-008): el texto que muestra la cita es el tramo
    `canonical_text[char_start:char_end]` de su lectura, aunque la columna `text` de la
    unidad diga otra cosa."""
    art = corpus["re_art_1"]
    Unit.objects.filter(pk=art.pk).update(text="texto distinto de la columna")
    art = Unit.objects.select_related("reading__document__norm").get(pk=art.pk)
    assert art.text != canonical(art)

    body = page(client, read_user, grounded([statement("Garantía.", art)], [art]))

    assert literals(citation_of(body, art)) == [html.escape(canonical(art))]
    assert "texto distinto de la columna" not in body


def test_unit_cited_by_several_statements_shows_its_text_once(client, read_user, corpus):
    """REQ-013: si varias afirmaciones citan la misma unidad, su texto literal se
    muestra una sola vez y cada afirmación la cita y lleva a ese texto."""
    art = corpus["re_art_1"]
    body = page(client, read_user, grounded([
        statement("Primera afirmación.", art),
        statement("Segunda afirmación.", art),
        statement("Tercera afirmación.", art),
    ], [art]))

    assert body.count(html.escape(canonical(art))) == 1
    found = [content for unit_id, content in citations(body) if unit_id == art.pk]
    assert len(found) == 3
    assert len(literals(found[0])) == 1
    anchor = re.search(r'id="(texto-\d+)"', body).group(1)
    for content in found[1:]:
        assert not literals(content)
        assert TEXT_SHOWN_ABOVE in content
        assert f'href="#{anchor}"' in content
        assert art.reading.document.norm.citation in summary(content)
        assert html.escape(art.path) in summary(content)
    blocks = statement_blocks(body)
    assert len(blocks) == 3
    for block in blocks:
        assert f'data-unit="{art.pk}"' in block


def test_script_opens_the_text_when_following_a_reference(client, read_user):
    """REQ-013: el script propio de la pantalla despliega la cita a la que lleva una
    referencia "más arriba" (un `details` cerrado no muestra su texto)."""
    from django.conf import settings
    from pathlib import Path

    script = (Path(settings.BASE_DIR) / "evaluon" / "static" / "js" /
              "consulta.js").read_text(encoding="utf-8")
    assert "hashchange" in script
    assert ".open = true" in script


# --- REQ-018: categoría, papel y orden ---------------------------------------------------


def test_article_first_then_legal_opinion_each_with_its_category(
    client, read_user, corpus
):
    """REQ-018: con un artículo del régimen específico y un dictamen legal, la página
    muestra primero el artículo y después el dictamen, y cada cita su categoría con su
    papel."""
    art, dl = corpus["re_art_1"], corpus["dl"]
    body = page(client, read_user, grounded(
        [statement("La garantía es del cinco por ciento.", art, dl)], [art, dl]))

    found = citations(body)
    assert [unit_id for unit_id, _ in found] == [art.pk, dl.pk]
    assert ROLE_LABELS["regimen_especifico"] in summary(found[0][1])
    assert ROLE_LABELS["dictamen_legal"] in summary(found[1][1])


def test_every_category_shows_its_role_in_words(client, read_user, corpus):
    """REQ-018: cada categoría se muestra con su papel en palabras: régimen específico,
    lo que se aplica; otra normativa, en lo que trata; marco nacional, marco de
    referencia; dictamen y recomendación, criterio que acompaña."""
    units = [corpus[k] for k in ("re_art_1", "other", "mn", "dl", "ra")]
    body = page(client, read_user, grounded([statement("Varias.", *units)], units))

    for unit in units:
        category = unit.reading.document.norm.category
        assert ROLE_LABELS[category] in summary(citation_of(body, unit))


def test_considerando_goes_last_labelled_as_context(client, read_user, corpus):
    """REQ-018: un considerando muestra la categoría de su documento y se presenta
    como contexto ("Régimen específico · Considerando · contexto"), después del
    articulado, en el orden guardado."""
    art, considerando = corpus["re_art_1"], corpus["considerando"]
    body = page(client, read_user, grounded([
        statement("Garantía.", art, considerando),
    ], [art, considerando]))

    found = citations(body)
    assert [unit_id for unit_id, _ in found] == [art.pk, considerando.pk]
    assert CONSIDERANDO_LABEL in summary(found[1][1])
    assert ROLE_LABELS["regimen_especifico"] not in summary(found[1][1])
    assert "contexto" not in summary(found[0][1])


def test_statements_and_citations_keep_the_saved_order(client, read_user, corpus):
    """REQ-018: la pantalla no reordena: las afirmaciones y sus citas se muestran en el
    orden guardado, que fijó el código al responder."""
    art, mn, dl, ra = corpus["re_art_1"], corpus["mn"], corpus["dl"], corpus["ra"]
    body = page(client, read_user, grounded([
        statement("Primera.", art, mn),
        statement("Segunda.", dl),
        statement("Tercera.", ra),
    ], [art, mn, dl, ra]))

    blocks = statement_blocks(body)
    assert ["Primera." in blocks[0], "Segunda." in blocks[1], "Tercera." in blocks[2]] \
        == [True, True, True]
    assert [unit_id for unit_id, _ in citations(body)] == [art.pk, mn.pk, dl.pk, ra.pk]


def test_clausula_shows_its_path_and_category_role_without_context_label(
    client, read_user, corpus
):
    """REQ-018 (REQ-003): una cita de una unidad `clausula` muestra su norma y su ruta
    ("Anexo › Cláusula transitoria") con el papel de su categoría, igual que un
    artículo, sin rótulo de contexto; al desplegarla se ve su texto, que empieza con el
    encabezado."""
    clausula = corpus["clausula"]
    body = page(client, read_user, grounded([statement("Registro.", clausula)],
                                            [clausula]))

    content = citation_of(body, clausula)
    assert "Disposición sintética 101/2020" in summary(content)
    assert html.escape("Anexo › Cláusula transitoria") in summary(content)
    assert ROLE_LABELS["regimen_especifico"] in summary(content)
    assert "contexto" not in content
    assert literals(content) == [html.escape(canonical(clausula))]
    assert literals(content)[0].startswith("CLÁUSULA TRANSITORIA")
    assert "#page=9" in content


# --- REQ-019: el régimen específico y el marco nacional difieren -------------------------


def test_regimes_differ_shows_notice_both_texts_and_applicable_label(
    client, read_user, corpus
):
    """REQ-019: con la marca, la afirmación lleva el aviso de texto fijo, muestra los
    dos textos (desplegados) y señala el del régimen específico como el aplicable."""
    art, mn = corpus["re_art_1"], corpus["mn"]
    body = page(client, read_user, grounded(
        [statement("Las garantías difieren.", art, mn, differ=True)], [art, mn]))

    block = statement_blocks(body)[0]
    assert REGIMES_DIFFER_NOTICE in block
    for unit in (art, mn):
        details = re.search(rf'<details class="citation" data-unit="{unit.pk}"([^>]*)>',
                            block)
        assert details and " open" in details.group(1)
        assert literals(citation_of(block, unit)) == [html.escape(canonical(unit))]
    assert APPLICABLE_LABEL in summary(citation_of(block, art))
    assert APPLICABLE_LABEL not in summary(citation_of(block, mn))
    assert body.count(APPLICABLE_LABEL) == 1


def test_without_the_mark_there_is_no_notice_nor_applicable_label(
    client, read_user, corpus
):
    """REQ-019: sin la marca, ni aviso ni rótulo de aplicable, y las citas quedan
    plegadas."""
    art, mn = corpus["re_art_1"], corpus["mn"]
    body = page(client, read_user, grounded(
        [statement("Garantías.", art, mn)], [art, mn]))

    assert REGIMES_DIFFER_NOTICE not in body
    assert APPLICABLE_LABEL not in body
    assert not re.search(r'<details class="citation"[^>]* open', body)


# --- REQ-007: unidad modificada ---------------------------------------------------------


def test_modified_unit_shows_the_text_that_modifies_it_with_its_date(
    client, read_user, corpus
):
    """REQ-007: una unidad modificada a la fecha se muestra junto con el texto literal
    de la que la modifica, señalando el cambio, la norma que lo trae y desde cuándo."""
    art, mod = corpus["re_art_2"], corpus["mod"]
    art_entry = entry(art, [change(mod, art.key)])
    body = page(client, read_user, grounded(
        [statement("El plazo es de diez días.", art)], [],
        extra_units=[(art, art_entry), (mod, entry(mod))]))

    content = citation_of(body, art)
    texts = literals(content)
    assert texts == [html.escape(canonical(art)), html.escape(canonical(mod))]
    note = re.search(r'<p class="change-note">(.*?)</p>', content, re.S).group(1)
    assert "Modificación desde el 01/05/2010" in note
    assert "Disposición sintética 202/2021" in note
    assert html.escape(mod.path) in note
    assert "Tiene cambios" in summary(content)
    # El texto de la modificatoria tiene su propio enlace al original, en su página.
    mod_url = reverse("norms:original", args=[mod.reading.document_id])
    assert f'href="{mod_url}#page=1"' in content


def test_before_the_change_only_the_original_text_is_shown(client, read_user, corpus):
    """REQ-007: antes de la fecha del cambio la respuesta guardada no trae cambios y la
    cita muestra solo el texto original, sin aviso de cambio."""
    art = corpus["re_art_2"]
    body = page(client, read_user, grounded([statement("Plazo.", art)], [art]))

    content = citation_of(body, art)
    assert literals(content) == [html.escape(canonical(art))]
    assert "change-note" not in content
    assert "Tiene cambios" not in content


def test_change_to_a_contained_part_names_that_part(client, read_user, corpus):
    """REQ-007: si el cambio alcanza a una parte de la unidad (un inciso), el aviso dice
    qué parte cambió."""
    art, mod, inc = corpus["re_art_2"], corpus["mod"], corpus["re_inc_b"]
    art_entry = entry(art, [change(mod, inc.key, effective_date="2021-07-15")])
    body = page(client, read_user, grounded(
        [statement("Plazo.", art)], [], extra_units=[(art, art_entry), (mod, entry(mod))]))

    note = re.search(r'<p class="change-note">(.*?)</p>',
                     citation_of(body, art), re.S).group(1)
    assert html.escape(f"«{inc.path}»") in note
    assert "desde el 15/07/2021" in note


def test_repeal_of_a_part_is_shown_as_such(client, read_user, corpus):
    """REQ-007: una derogación de una parte se señala como derogación, con su fecha."""
    art, mod, inc = corpus["re_art_2"], corpus["mod"], corpus["re_inc_b"]
    art_entry = entry(art, [change(mod, inc.key, relation_type="deroga")])
    body = page(client, read_user, grounded(
        [statement("Plazo.", art)], [], extra_units=[(art, art_entry), (mod, entry(mod))]))

    note = re.search(r'<p class="change-note">(.*?)</p>',
                     citation_of(body, art), re.S).group(1)
    assert "Derogación de" in note and "desde el 01/05/2010" in note


def test_change_without_source_unit_is_shown_with_what_there_is(
    client, read_user, corpus
):
    """REQ-007: un cambio sin la unidad que lo trae (`unit` vacío) se muestra sin error,
    con su fecha, y dice que el texto que trae el cambio no está disponible."""
    art = corpus["re_art_2"]
    art_entry = entry(art, [change(None, art.key)])
    body = page(client, read_user, grounded(
        [statement("Plazo.", art)], [], extra_units=[(art, art_entry)]))

    content = citation_of(body, art)
    assert "Modificación desde el 01/05/2010" in content
    assert CHANGE_TEXT_MISSING in content
    assert literals(content) == [html.escape(canonical(art))]


def test_change_whose_unit_is_not_in_units_is_read_from_the_database(
    client, read_user, corpus
):
    """REQ-007: si la unidad que trae el cambio no está en `units` (los cambios se
    siguen a un solo nivel), su norma, su ruta y su texto se leen de la base."""
    art, mod = corpus["re_art_2"], corpus["mod"]
    art_entry = entry(art, [change(mod, art.key)])
    body = page(client, read_user, grounded(
        [statement("Plazo.", art)], [], extra_units=[(art, art_entry)]))

    content = citation_of(body, art)
    assert literals(content) == [html.escape(canonical(art)), html.escape(canonical(mod))]
    assert "Disposición sintética 202/2021" in content


def test_change_whose_unit_does_not_exist_is_tolerated(client, read_user, corpus):
    """REQ-007: si la unidad que trae el cambio no existe, la página se muestra igual,
    con el cambio y su fecha, sin el texto."""
    art = corpus["re_art_2"]
    missing = {"relation_type": "modifica", "unit": 999999, "target_unit_key": art.key,
               "effective_date": "2010-05-01"}
    body = page(client, read_user, grounded(
        [statement("Plazo.", art)], [], extra_units=[(art, entry(art, [missing]))]))

    content = citation_of(body, art)
    assert "Modificación desde el 01/05/2010" in content
    assert CHANGE_TEXT_MISSING in content


def test_modifier_also_cited_shows_its_text_once(client, read_user, corpus):
    """REQ-007, REQ-013: si la unidad que modifica también se cita en otra afirmación,
    su texto se muestra una sola vez y la otra cita lleva a él."""
    art, mod = corpus["re_art_2"], corpus["mod"]
    art_entry = entry(art, [change(mod, art.key)])
    body = page(client, read_user, grounded(
        [statement("Plazo.", art), statement("Quince días.", mod)], [],
        extra_units=[(art, art_entry), (mod, entry(mod))]))

    assert body.count(html.escape(canonical(mod))) == 1
    content = citation_of(body, mod)
    assert not literals(content)
    assert TEXT_SHOWN_ABOVE in content


def test_result_without_changes_key_is_shown(client, read_user, corpus):
    """REQ-013: en el camino sin fecha `units` no trae `changes`; la cita se muestra
    igual, sin aviso de cambio."""
    art = corpus["re_art_1"]
    result = grounded([statement("Garantía.", art)], [art])
    del result["units"][str(art.pk)]["changes"]

    body = page(client, read_user, result)

    assert literals(citation_of(body, art)) == [html.escape(canonical(art))]
    assert "change-note" not in body


# --- REQ-015: reconocimiento sobre imagen ------------------------------------------------


def test_ocr_unit_shows_recognition_notice(client, read_user, corpus):
    """REQ-015: si el texto de la unidad vino de reconocimiento sobre una imagen, al
    desplegar la cita se ve la leyenda que lo dice; una unidad de PDF con texto no la
    lleva."""
    art, dl = corpus["re_art_1"], corpus["dl"]
    body = page(client, read_user, grounded([statement("Garantía.", art, dl)], [art, dl]))

    assert OCR_NOTICE in citation_of(body, dl)
    assert OCR_NOTICE not in citation_of(body, art)
    assert "#page=2" in citation_of(body, dl)


# --- Lenguaje llano ---------------------------------------------------------------------


def test_page_shows_no_internal_names(client, read_user, corpus):
    """REQ-013, REQ-018: la página no muestra nombres internos del sistema ni los
    valores guardados de categoría, tipo, origen o marca."""
    art, mn, dl, considerando, mod = (corpus[k] for k in
                                      ("re_art_1", "mn", "dl", "considerando", "mod"))
    art_2 = corpus["re_art_2"]
    art_2_entry = entry(art_2, [change(mod, corpus["re_inc_b"].key)])
    body = page(client, read_user, grounded(
        [statement("Garantías.", art, mn, differ=True),
         statement("Plazo.", art_2, dl, considerando)],
        [art, mn, dl, considerando], extra_units=[(art_2, art_2_entry)]))

    for name in ("grounded", "undetermined", "below_threshold", "reranker",
                 "regimen_especifico", "marco_nacional", "dictamen_legal",
                 "regimes_differ", "target_unit_key", "relation_type", "text_origin",
                 "pdf_text", "unit_type", "articulo", "None"):
        assert name not in body, name


# --- Ajustes de verificación ------------------------------------------------------------


def anchors(body):
    return re.findall(r'id="(texto-\d+)"', body)


@pytest.mark.parametrize("earlier", ["re_art_1", "mn"])
def test_regimes_differ_shows_both_texts_even_if_already_shown(
    client, read_user, corpus, earlier
):
    """REQ-019: en la afirmación con la marca, el texto del régimen específico y el del
    marco nacional se muestran completos y desplegados aunque uno de ellos ya haya
    aparecido antes en la página; "Texto aplicable" va sobre la cita del régimen
    específico que muestra el texto, y el ancla de cada unidad no se repite."""
    art, mn = corpus["re_art_1"], corpus["mn"]
    body = page(client, read_user, grounded([
        statement("Antes, sin marca.", corpus[earlier]),
        statement("Difieren.", art, mn, differ=True),
    ], [art, mn]))

    block = statement_blocks(body)[1]
    assert REGIMES_DIFFER_NOTICE in block
    for unit in (art, mn):
        details = re.search(rf'<details class="citation" data-unit="{unit.pk}"([^>]*)>',
                            block)
        assert " open" in details.group(1)
        content = citation_of(block, unit)
        assert literals(content) == [html.escape(canonical(unit))]
        assert TEXT_SHOWN_ABOVE not in content
    assert APPLICABLE_LABEL in summary(citation_of(block, art))
    assert body.count(APPLICABLE_LABEL) == 1
    assert sorted(anchors(body)) == sorted({f"texto-{art.pk}", f"texto-{mn.pk}"})
    # La primera afirmación conserva el ancla de la unidad que citó.
    assert f'id="texto-{corpus[earlier].pk}"' in statement_blocks(body)[0]


def test_applicable_label_is_never_on_a_considerando(client, read_user, corpus):
    """REQ-019 (REQ-018): con la marca, un considerando del régimen específico no lleva
    "Texto aplicable"; solo el artículo."""
    art, mn, considerando = corpus["re_art_1"], corpus["mn"], corpus["considerando"]
    body = page(client, read_user, grounded(
        [statement("Difieren.", art, mn, considerando, differ=True)],
        [art, mn, considerando]))

    assert APPLICABLE_LABEL not in summary(citation_of(body, considerando))
    assert APPLICABLE_LABEL in summary(citation_of(body, art))
    assert body.count(APPLICABLE_LABEL) == 1


def test_change_mark_on_every_appearance_of_the_modified_unit(client, read_user, corpus):
    """REQ-007: la unidad modificada lleva "Tiene cambios" en el resumen cada vez que se
    cita, también cuando su texto se muestra más arriba."""
    art, mod = corpus["re_art_2"], corpus["mod"]
    body = page(client, read_user, grounded(
        [statement("Uno.", art), statement("Dos.", art)], [],
        extra_units=[(art, entry(art, [change(mod, art.key)])), (mod, entry(mod))]))

    blocks = statement_blocks(body)
    for block in blocks:
        assert "Tiene cambios" in summary(citation_of(block, art))
    assert TEXT_SHOWN_ABOVE in citation_of(blocks[1], art)


def test_web_page_link_has_no_page_even_if_the_unit_has_one(client, read_user, corpus):
    """REQ-013: el enlace al original de una página web guardada no lleva `#page`
    aunque la unidad traiga un número de página; solo un PDF lo lleva."""
    mn = corpus["mn"]
    result = grounded([statement("Marco.", mn)], [mn])
    result["units"][str(mn.pk)]["page_start"] = 4

    body = page(client, read_user, result)

    content = citation_of(body, mn)
    assert ORIGINAL_LINK_TEXT in content
    assert "#page=" not in content


RAW_VALUES = ("ocr", "web", "pdf_text", "clausula", "articulo", "considerando")


def test_raw_stored_values_do_not_appear_in_the_page(client, read_user, corpus):
    """REQ-013, REQ-015, REQ-018: los valores guardados de origen del texto y de tipo de
    unidad (`ocr`, `web`, `pdf_text`, `clausula`, `articulo`, `considerando`) no
    aparecen en la página: ni como valor de un atributo ni como palabra suelta del texto
    visible, en minúscula. "Considerando · contexto" va con mayúscula y no cuenta."""
    units = [corpus[k] for k in ("re_art_1", "mn", "dl", "considerando", "clausula")]
    body = page(client, read_user, grounded([statement("Varias.", *units)], units))

    values = "|".join(RAW_VALUES)
    assert not re.search(rf'=\s*"[^"]*\b({values})\b[^"]*"', body)
    visible = re.sub(r"<[^>]+>", " ", body)
    found = re.findall(rf"\b({values})\b", visible)
    assert found == []
    assert "Considerando · contexto" in visible


def test_citation_unknown_everywhere_says_it_is_not_available(client, read_user, corpus):
    """REQ-013: una cita cuyo id no está ni en `units` ni en la base se muestra con un
    texto llano, "Esta cita no está disponible", y no con un resumen vacío."""
    art = corpus["re_art_1"]
    result = grounded([statement("Garantía.", art)], [art])
    result["statements"][0]["citations"].append(987654)

    body = page(client, read_user, result)

    block = statement_blocks(body)[0]
    assert "Esta cita no está disponible." in block
    assert 'data-unit="987654"' not in block
    assert "<summary> · </summary>" not in block
    assert literals(citation_of(block, art)) == [html.escape(canonical(art))]
