"""Pasajes de búsqueda y sus vectores (T-015, T-031; plan 001, "Unidades base, incisos
y pasajes", "Conteo de tokens" y `norms_passage`).

Cada unidad base da uno o más pasajes, con su encabezado de contexto (norma y ruta), su
texto, su vector y el nombre y la huella del modelo que lo calculó. Una unidad larga se
parte en pasajes de hasta `PASSAGE_MAX_TOKENS`, con un solape de hasta
`PASSAGE_OVERLAP_TOKENS`, cortando en los límites de inciso, de párrafo o de oración
(T-031). Los datos son sintéticos (P4), salvo el art. 24 del anexo de la Disposición
AFIP 247/2022, que es público. El vector y la cuenta de tokens los da el doble de
embeddings, que cuenta una palabra por token.
"""

from pathlib import Path

import pytest
from django.conf import settings

from evaluon.ai import embeddings
from evaluon.norms import indexing
from evaluon.norms.models import Passage
from evaluon.norms.reading import read_document
from evaluon.norms.splitting import split_document
from tests.conftest import count_words

REPO = Path(__file__).resolve().parents[2]
ANNEX_247 = REPO / "corpus" / "normativa" / "disp-afip-247-2022-anexo.pdf"


def annex_norm(make_norm):
    return make_norm(norm_type="disposicion", number="247", year=2022, issuer="afip",
                     citation="Disposición AFIP 247/2022")


def test_passage_document_is_header_newline_text():
    """REQ-005: el texto que se convierte en vector es el encabezado y el texto del
    pasaje unidos por un salto de línea, la misma forma con que la recuperación puntúa
    cada pasaje. Se fija la forma exacta."""
    assert (
        indexing.passage_document("Disposición AFIP 247/2022, Anexo, Artículo 1", "Texto.")
        == "Disposición AFIP 247/2022, Anexo, Artículo 1\nTexto."
    )


@pytest.mark.django_db
def test_header_is_norm_name_and_path(make_norm, make_document, make_reading):
    """REQ-005: el encabezado de contexto de un pasaje es el nombre de cita de la norma
    y la ruta de la unidad, con sus tramos separados por comas."""
    norm = annex_norm(make_norm)
    reading = make_reading(make_document(norm, part="anexo"), [
        ("anexo", "ANEXO"),
        {"key": "anexo/art-50", "text": "ARTÍCULO 50.- Garantías sintéticas.",
         "path": "Anexo › Título II › Capítulo V › Artículo 50"},
        {"key": "anexo/clausula-transitoria", "text": "CLÁUSULA TRANSITORIA Texto.",
         "path": "Anexo › Cláusula transitoria"},
    ], status="pending", passages=False)
    units = reading.units_by_key

    assert indexing.norm_name(norm) == "Disposición AFIP 247/2022"
    assert indexing.passage_header(norm, units["anexo/art-50"]) == (
        "Disposición AFIP 247/2022, Anexo, Título II, Capítulo V, Artículo 50"
    )
    assert indexing.passage_header(norm, units["anexo/clausula-transitoria"]) == (
        "Disposición AFIP 247/2022, Anexo, Cláusula transitoria"
    )


@pytest.mark.django_db
def test_norm_name_is_the_citation_as_written(make_norm, make_document, make_reading):
    """REQ-001, REQ-013, REQ-020: el nombre de la norma es el nombre de cita que
    escribió la persona, sin reglas propias de tipo, organismo ni año: la Disposición
    AFIP 297/03 se nombra con el año en dos cifras, aunque su año sea 2003. El
    encabezado de un pasaje empieza con ese nombre."""
    norm = make_norm(norm_type="disposicion", number="297", year=2003, issuer="afip",
                     citation="Disposición AFIP 297/03")
    reading = make_reading(make_document(norm), [
        ("anexo-i", "ANEXO I"),
        {"key": "anexo-i/art-1", "text": "ARTICULO 1.- Objeto sintético.",
         "path": "Anexo I › Artículo 1"},
    ], status="pending", passages=False)

    assert indexing.norm_name(norm) == "Disposición AFIP 297/03"
    assert indexing.passage_header(norm, reading.units_by_key["anexo-i/art-1"]) == (
        "Disposición AFIP 297/03, Anexo I, Artículo 1"
    )


@pytest.mark.django_db
def test_norm_name_has_no_rules_of_its_own(make_norm):
    """REQ-001: `norm_name` devuelve el nombre de cita tal cual, aunque no coincida con
    el tipo, el organismo ni el número de la norma."""
    norm = make_norm(norm_type="resolucion general", number="5", year=2099,
                     issuer="organismo sintetico", citation="Nombre de cita sintético")

    assert indexing.norm_name(norm) == "Nombre de cita sintético"


@pytest.mark.django_db
def test_test_passages_have_the_same_header_as_real_ones(two_regimes):
    """REQ-005, REQ-020: los pasajes de los datos de prueba llevan el encabezado que
    arma la validación, que empieza con el nombre de cita de cada régimen."""
    old_unit = two_regimes.old_units["anexo-i/art-1"]
    new_unit = two_regimes.new_units["anexo/art-1"]

    old_header = old_unit.passages.get().header
    new_header = new_unit.passages.get().header

    assert old_header == indexing.passage_header(two_regimes.old, old_unit)
    assert old_header.startswith("Disposición AFIP 297/03, ")
    assert new_header == indexing.passage_header(two_regimes.new, new_unit)
    assert new_header.startswith("Disposición AFIP 247/2022, ")


@pytest.mark.django_db
def test_one_passage_per_base_unit_and_none_for_incisos(
    make_norm, make_document, make_reading, fake_embeddings
):
    """REQ-005: cada unidad base da un pasaje con todo su texto; los incisos no generan
    pasajes."""
    norm = annex_norm(make_norm)
    reading = make_reading(make_document(norm), [
        ("art-1", "ARTICULO 1.- Objeto sintético: a) primero."),
        ("art-1/inc-a", "a) primero."),
        ("art-2", "ARTICULO 2.- Comuníquese."),
    ], status="pending", passages=False)
    units = reading.units_by_key

    drafts = indexing.build_passages(reading)

    assert [d.unit.key for d in drafts] == ["art-1", "art-2"]
    for draft in drafts:
        assert draft.order == 1
        assert draft.char_start == 0
        assert draft.char_end == len(draft.unit.text)
        assert draft.text == draft.unit.text
        assert draft.header == indexing.passage_header(norm, draft.unit)
    assert drafts[0].unit.pk == units["art-1"].pk


@pytest.mark.django_db
def test_annex_with_articles_contributes_only_its_own_text(
    make_norm, make_document, make_reading, fake_embeddings
):
    """REQ-005: un anexo que contiene artículos aporta como pasaje solo su texto propio
    (lo que va antes del primer artículo), para que ningún texto quede en pasajes de dos
    unidades base."""
    norm = annex_norm(make_norm)
    annex_text = "ANEXO\nDisposiciones sintéticas.\nARTÍCULO 1°.- Objeto sintético."
    article_text = "ARTÍCULO 1°.- Objeto sintético."
    start = annex_text.index(article_text)
    reading = make_reading(make_document(norm, part="anexo"), [
        {"key": "anexo", "text": annex_text, "char_start": 0, "char_end": len(annex_text)},
        {"key": "anexo/art-1", "text": article_text, "char_start": start,
         "char_end": start + len(article_text)},
    ], status="pending", passages=False)

    drafts = {d.unit.key: d for d in indexing.build_passages(reading)}

    assert drafts["anexo"].text == "ANEXO\nDisposiciones sintéticas."
    assert drafts["anexo"].char_start == 0
    assert drafts["anexo"].char_end == len("ANEXO\nDisposiciones sintéticas.")
    assert drafts["anexo/art-1"].text == article_text


@pytest.mark.django_db
def test_vectors_are_computed_on_header_and_text(
    make_norm, make_document, make_reading, fake_embeddings
):
    """REQ-005, REQ-012: el vector de cada pasaje se calcula sobre
    `passage_document(header, text)`, con el cliente de embeddings, y el pasaje guarda
    el vector, el nombre del modelo y la huella del archivo del modelo."""
    norm = annex_norm(make_norm)
    reading = make_reading(make_document(norm), [
        ("art-1", "ARTICULO 1.- Objeto sintético."),
        ("art-2", "ARTICULO 2.- Comuníquese."),
    ], status="pending", passages=False)
    drafts = indexing.build_passages(reading)
    expected_documents = [indexing.passage_document(d.header, d.text) for d in drafts]
    fake_embeddings.vectors[expected_documents[0]] = [0.5] * 1024

    vectors = indexing.embed_passages(drafts)
    indexing.save_passages(drafts, vectors)

    assert fake_embeddings.calls == [expected_documents]
    stored = list(Passage.objects.filter(unit__reading=reading).order_by("unit__order"))
    assert [p.unit.key for p in stored] == ["art-1", "art-2"]
    assert list(stored[0].embedding) == [0.5] * 1024
    assert list(stored[1].embedding) == fake_embeddings.vector_for(expected_documents[1])
    for passage, draft in zip(stored, drafts):
        assert passage.header == draft.header
        assert passage.text == draft.text
        assert passage.embedding_model == settings.EMBEDDINGS_MODEL
        assert passage.embedding_revision == settings.EMBEDDINGS_MODEL_SHA256


# --- Partición de unidades largas (T-031) --------------------------------------------


def document_tokens(draft):
    """Tokens de un pasaje según el doble: encabezado más texto, una palabra por token."""
    return count_words(indexing.passage_document(draft.header, draft.text))


def assert_well_formed(unit, drafts, max_tokens):
    """Comprobaciones comunes a toda partición: orden 1..n, texto igual al tramo de la
    unidad, sin superar el límite, sin cortar palabras y en orden de avance."""
    assert [d.order for d in drafts] == list(range(1, len(drafts) + 1))
    for draft in drafts:
        assert draft.unit.pk == unit.pk
        assert draft.text == unit.text[draft.char_start:draft.char_end]
        assert draft.text == draft.text.strip()
        assert document_tokens(draft) <= max_tokens
        assert draft.char_start == 0 or unit.text[draft.char_start - 1].isspace()
        assert draft.char_end == len(unit.text) or unit.text[draft.char_end].isspace()
    for previous, following in zip(drafts, drafts[1:]):
        assert following.char_start > previous.char_start
        assert following.char_end > previous.char_end


def assert_covers(text, drafts, end=None):
    """Todo carácter que no es espacio, hasta `end`, está en algún pasaje: ningún texto
    se recorta en silencio."""
    end = len(text) if end is None else end
    covered = set()
    for draft in drafts:
        covered.update(range(draft.char_start, draft.char_end))
    missing = [i for i in range(end) if not text[i].isspace() and i not in covered]
    assert missing == []


def sentence(prefix, n):
    """Oración sintética de `n` palabras que termina en punto."""
    words = ["Texto", *(f"{prefix}{i}" for i in range(1, n))]
    return " ".join(words) + "."


@pytest.mark.django_db
def test_short_unit_gives_a_single_passage(
    make_norm, make_document, make_reading, fake_embeddings, settings
):
    """REQ-003, REQ-008: una unidad base que entra en el límite (encabezado más texto)
    da un único pasaje con todo su texto, aunque tenga varios párrafos."""
    settings.PASSAGE_MAX_TOKENS = 40
    settings.PASSAGE_OVERLAP_TOKENS = 5
    norm = annex_norm(make_norm)
    text = "ARTICULO 3.- Primer párrafo sintético.\nSegundo párrafo sintético."
    reading = make_reading(make_document(norm), [("art-3", text)],
                           status="pending", passages=False)

    drafts = indexing.build_passages(reading)

    assert len(drafts) == 1
    assert drafts[0].order == 1
    assert (drafts[0].char_start, drafts[0].char_end) == (0, len(text))
    assert drafts[0].text == text


@pytest.mark.django_db
def test_annex_without_articles_gives_several_overlapping_passages(
    make_norm, make_document, make_reading, fake_embeddings, settings
):
    """REQ-003, REQ-008: un anexo sin artículos de varias páginas da varios pasajes que
    cubren todo su texto, sin superar el límite (encabezado más texto) y con solape:
    cada pasaje repite, del anterior, tramos completos que suman hasta el solape."""
    settings.PASSAGE_MAX_TOKENS = 40
    settings.PASSAGE_OVERLAP_TOKENS = 10
    norm = annex_norm(make_norm)
    paragraphs = ["ANEXO II", "MODELO SINTÉTICO DE FORMULARIO"]
    for k in range(1, 9):
        paragraphs.append(" ".join([
            sentence(f"p{k}a", 6), sentence(f"p{k}b", 8), sentence(f"p{k}c", 5),
        ]))
    text = "\n".join(paragraphs)
    reading = make_reading(make_document(norm, part="anexo-ii"), [("anexo-ii", text)],
                           status="pending", passages=False)
    unit = reading.units_by_key["anexo-ii"]

    drafts = indexing.build_passages(reading)

    assert len(drafts) > 3
    assert_well_formed(unit, drafts, 40)
    assert_covers(unit.text, drafts)
    for previous, following in zip(drafts, drafts[1:]):
        assert following.char_start < previous.char_end, "sin solape"
        overlap = unit.text[following.char_start:previous.char_end]
        assert 0 < count_words(overlap) <= 10
        assert overlap.endswith(".")


@pytest.mark.django_db
def test_article_with_many_incisos_is_cut_at_inciso_limits(
    make_norm, make_document, make_reading, fake_embeddings, settings
):
    """REQ-003, REQ-008: un artículo con muchos incisos se corta en los límites de sus
    incisos, aunque cortar en un párrafo dejara el pasaje más lleno. Cada pasaje termina
    donde termina un inciso, y el siguiente repite el último párrafo del anterior."""
    norm = annex_norm(make_norm)
    preamble = "ARTICULO 5.- MODALIDADES sintéticas siguientes:"  # 5 palabras
    incisos = [
        f"{letter}) Modalidad {letter}.\n"  # 3 palabras con la etiqueta
        f"Texto sintético de la modalidad {letter} con nueve palabras."  # 9 palabras
        for letter in "abcde"
    ]
    text = "\n".join([preamble, *incisos])
    specs = [{"key": "art-5", "text": text}]
    for letter, inciso in zip("abcde", incisos):
        start = text.index(inciso)
        specs.append({"key": f"art-5/inc-{letter}", "text": inciso,
                      "char_start": start, "char_end": start + len(inciso)})
    reading = make_reading(make_document(norm), specs, status="pending", passages=False)
    unit = reading.units_by_key["art-5"]
    header_tokens = count_words(indexing.passage_header(norm, unit))
    # Entran el encabezado, el preámbulo y dos incisos (5 + 12 + 12 = 29), y el primer
    # párrafo de un tercero (3 más): un corte por párrafo terminaría dentro del inciso c.
    settings.PASSAGE_MAX_TOKENS = header_tokens + 33
    settings.PASSAGE_OVERLAP_TOKENS = 9

    drafts = indexing.build_passages(reading)

    inciso_ends = {text.index(inciso) + len(inciso) for inciso in incisos}
    assert [d.char_end for d in drafts] == [
        text.index(incisos[1]) + len(incisos[1]),
        text.index(incisos[3]) + len(incisos[3]),
        len(text),
    ]
    assert all(d.char_end in inciso_ends for d in drafts)
    assert_well_formed(unit, drafts, settings.PASSAGE_MAX_TOKENS)
    assert_covers(unit.text, drafts)
    # Solape: el último párrafo del inciso anterior (9 palabras, una oración).
    assert drafts[1].text.startswith("Texto sintético de la modalidad b")
    assert drafts[2].text.startswith("Texto sintético de la modalidad d")
    assert not any(d.unit.unit_type == "inciso" for d in drafts)


@pytest.mark.django_db
def test_long_paragraph_is_cut_at_sentence_limits(
    make_norm, make_document, make_reading, fake_embeddings, settings
):
    """REQ-003, REQ-008: un párrafo que solo no entra en el límite se corta al final de
    una oración, nunca en medio de ella si la oración entra."""
    settings.PASSAGE_MAX_TOKENS = 30
    settings.PASSAGE_OVERLAP_TOKENS = 6
    norm = annex_norm(make_norm)
    text = "ARTICULO 7.- " + " ".join(sentence(f"o{k}", 7) for k in range(1, 9))
    reading = make_reading(make_document(norm), [("art-7", text)],
                           status="pending", passages=False)
    unit = reading.units_by_key["art-7"]

    drafts = indexing.build_passages(reading)

    assert len(drafts) > 2
    assert_well_formed(unit, drafts, 30)
    assert_covers(unit.text, drafts)
    assert all(d.text.endswith(".") for d in drafts)


@pytest.mark.django_db
def test_long_sentence_is_cut_between_words(
    make_norm, make_document, make_reading, fake_embeddings, settings
):
    """REQ-003, REQ-008: un tramo que solo supera el límite (una oración sin puntos ni
    saltos) se parte entre palabras: ningún pasaje supera el límite, ninguno corta una
    palabra y entre todos cubren el texto."""
    settings.PASSAGE_MAX_TOKENS = 25
    settings.PASSAGE_OVERLAP_TOKENS = 4
    norm = annex_norm(make_norm)
    text = "ARTICULO 8.- " + " ".join(f"palabra{i}" for i in range(1, 80))
    reading = make_reading(make_document(norm), [("art-8", text)],
                           status="pending", passages=False)
    unit = reading.units_by_key["art-8"]

    drafts = indexing.build_passages(reading)

    assert len(drafts) > 3
    assert_well_formed(unit, drafts, 25)
    assert_covers(unit.text, drafts)


@pytest.mark.django_db
def test_no_text_in_passages_of_two_base_units(
    make_norm, make_document, make_reading, fake_embeddings, settings
):
    """REQ-003, REQ-008: un anexo con artículos aporta solo su texto propio, también
    cuando ese texto es largo y se parte; ningún texto del documento aparece en pasajes
    de dos unidades base distintas (el solape queda dentro de cada unidad)."""
    settings.PASSAGE_MAX_TOKENS = 30
    settings.PASSAGE_OVERLAP_TOKENS = 8
    norm = annex_norm(make_norm)
    own = "ANEXO\n" + "\n".join(sentence(f"c{k}", 9) for k in range(1, 7))
    art_1 = "ARTÍCULO 1°.- " + " ".join(sentence(f"x{k}", 8) for k in range(1, 7))
    art_2 = "ARTÍCULO 2°.- " + " ".join(sentence(f"y{k}", 8) for k in range(1, 7))
    annex_text = "\n".join([own, art_1, art_2])
    start_1 = annex_text.index(art_1)
    start_2 = annex_text.index(art_2)
    reading = make_reading(make_document(norm, part="anexo"), [
        {"key": "anexo", "text": annex_text, "char_start": 0, "char_end": len(annex_text)},
        {"key": "anexo/art-1", "text": art_1, "char_start": start_1,
         "char_end": start_1 + len(art_1)},
        {"key": "anexo/art-2", "text": art_2, "char_start": start_2,
         "char_end": start_2 + len(art_2)},
    ], status="pending", passages=False)
    units = reading.units_by_key

    drafts = indexing.build_passages(reading)

    by_unit = {}
    for draft in drafts:
        by_unit.setdefault(draft.unit.key, []).append(draft)
    assert set(by_unit) == {"anexo", "anexo/art-1", "anexo/art-2"}
    assert all(len(found) > 1 for found in by_unit.values())
    assert max(d.char_end for d in by_unit["anexo"]) <= len(own)
    assert_covers(units["anexo"].text, by_unit["anexo"], end=len(own))
    covered = {}
    for key, found in by_unit.items():
        offset = units[key].char_start
        covered[key] = set()
        for d in found:
            covered[key].update(range(offset + d.char_start, offset + d.char_end))
    keys = list(covered)
    for i, first in enumerate(keys):
        for second in keys[i + 1:]:
            assert covered[first].isdisjoint(covered[second])


@pytest.mark.django_db
def test_annex_root_without_own_text_gives_no_passage(
    make_norm, make_document, make_reading, fake_embeddings
):
    """REQ-003: la raíz de un anexo se indexa si tiene texto propio (la carátula); si su
    texto propio queda vacío, no genera pasaje."""
    norm = annex_norm(make_norm)
    article = "ARTÍCULO 1°.- Objeto sintético."
    reading = make_reading(make_document(norm, part="anexo"), [
        {"key": "anexo", "text": article, "char_start": 0, "char_end": len(article)},
        {"key": "anexo/art-1", "text": article, "char_start": 0, "char_end": len(article)},
    ], status="pending", passages=False)

    drafts = indexing.build_passages(reading)

    assert [d.unit.key for d in drafts] == ["anexo/art-1"]


@pytest.fixture(scope="module")
def annex_247_article_24():
    """Texto del art. 24 del anexo de la Disposición AFIP 247/2022 (público), partido
    con las reglas de lectura y partición vigentes."""
    result = split_document(read_document(ANNEX_247), part="anexo")
    return next(u.text for u in result.units if u.key == "anexo/art-24")


@pytest.mark.django_db
def test_real_article_24_of_annex_247_is_split_in_passages(
    make_norm, make_document, make_reading, fake_embeddings, annex_247_article_24
):
    """REQ-003, REQ-008: caso real de T-020. El art. 24 del anexo de la Disposición AFIP
    247/2022 (unos 2.300 tokens) era un solo pasaje; con el límite de `settings.py` se
    parte en varios, ninguno lo supera, todos terminan en un fin de párrafo (cada inciso
    empieza en un párrafo propio) y entre todos cubren el artículo entero."""
    norm = annex_norm(make_norm)
    text = annex_247_article_24
    assert text.startswith("ARTÍCULO 24.- MODALIDADES.")
    reading = make_reading(make_document(norm, part="anexo"), [
        ("anexo", "ANEXO"),
        {"key": "anexo/art-24", "text": text, "path": "Anexo › Artículo 24"},
    ], status="pending", passages=False)
    unit = reading.units_by_key["anexo/art-24"]

    drafts = [d for d in indexing.build_passages(reading) if d.unit.pk == unit.pk]

    assert count_words(text) > settings.PASSAGE_MAX_TOKENS
    assert len(drafts) >= 3
    assert_well_formed(unit, drafts, settings.PASSAGE_MAX_TOKENS)
    assert_covers(unit.text, drafts)
    for draft in drafts:
        assert draft.char_end == len(text) or text[draft.char_end] == "\n"


@pytest.mark.django_db
def test_tokens_are_counted_on_the_assembled_passage(
    make_norm, make_document, make_reading, fake_embeddings, settings, monkeypatch
):
    """REQ-003, REQ-008: los tokens se cuentan sobre el pasaje tal como se manda
    (encabezado, salto de línea y texto), no sumando cuentas sueltas. Con un contador
    que no es aditivo (una palabra o un salto de línea, un token), ningún pasaje supera
    el límite según ese mismo contador."""
    def count(text):
        return count_words(text) + text.count("\n")

    monkeypatch.setattr(embeddings, "count_tokens", count)
    settings.PASSAGE_OVERLAP_TOKENS = 0
    norm = annex_norm(make_norm)
    text = "\n".join(sentence(f"q{k}", 5) for k in range(1, 5))
    reading = make_reading(make_document(norm), [("art-6", text)],
                           status="pending", passages=False)
    unit = reading.units_by_key["art-6"]
    header_tokens = count(indexing.passage_header(norm, unit))
    # Dos párrafos juntos cuestan encabezado + 1 (salto tras el encabezado) + 10 + 1
    # (salto entre párrafos): uno más que el límite. Sumando cuentas sueltas se pierde el
    # salto tras el encabezado y entrarían.
    settings.PASSAGE_MAX_TOKENS = header_tokens + 11

    drafts = indexing.build_passages(reading)

    assert len(drafts) == 4
    for draft in drafts:
        assert count(indexing.passage_document(draft.header, draft.text)) <= (
            settings.PASSAGE_MAX_TOKENS
        )
    assert_covers(unit.text, drafts)


@pytest.mark.django_db
def test_overlap_that_does_not_fit_is_dropped(
    make_norm, make_document, make_reading, fake_embeddings, settings
):
    """REQ-003, REQ-008: si el solape no entra junto con el tramo siguiente, se repite
    menos; si ni el tramo más chico entra, el pasaje va sin solape. Ningún pasaje supera
    el límite."""
    norm = annex_norm(make_norm)
    first = " ".join(sentence(f"r{k}", 7) for k in range(1, 4))  # 21 palabras
    second = " ".join(sentence(f"s{k}", 7) for k in range(1, 4))  # 21 palabras
    text = f"{first}\n{second}"
    reading = make_reading(make_document(norm, part="anexo-iii"), [("anexo-iii", text)],
                           status="pending", passages=False)
    unit = reading.units_by_key["anexo-iii"]
    header_tokens = count_words(indexing.passage_header(norm, unit))
    # El solape posible es la última oración del primer párrafo (7 palabras, hasta 10);
    # con el segundo párrafo suma 28 y el límite deja 27 para el texto.
    settings.PASSAGE_MAX_TOKENS = header_tokens + 27
    settings.PASSAGE_OVERLAP_TOKENS = 10

    drafts = indexing.build_passages(reading)

    assert [(d.char_start, d.char_end) for d in drafts] == [
        (0, len(first)), (len(first) + 1, len(text)),
    ]
    assert_well_formed(unit, drafts, settings.PASSAGE_MAX_TOKENS)


@pytest.mark.django_db
def test_abbreviations_do_not_end_a_sentence(
    make_norm, make_document, make_reading, fake_embeddings, settings
):
    """REQ-003, REQ-008: al partir un párrafo largo por oraciones, "art. 4", "inc. b" y
    "N° 5" no son fin de oración: ningún pasaje termina en la abreviatura ni empieza con
    el número o la letra que la sigue."""
    norm = annex_norm(make_norm)
    sentences = [
        "ARTICULO 9.- Primera oración sintética de seis palabras.",  # 8
        "Según el art. 4 corresponde aplicar el régimen sintético.",  # 9
        "Tercera oración sintética de seis palabras.",  # 6
        "Por el inc. b corresponde aplicar el régimen sintético.",  # 9
        "Quinta oración sintética de seis palabras.",  # 6
        "Según el N° 5 corresponde aplicar el régimen sintético.",  # 9
    ]
    text = " ".join(sentences)
    reading = make_reading(make_document(norm), [("art-9", text)],
                           status="pending", passages=False)
    unit = reading.units_by_key["art-9"]
    # Cada oración entra sola y dos no: cada pasaje es una oración. Si la abreviatura
    # cortara, la primera oración se llevaría "Según el art." y el pasaje terminaría ahí.
    settings.PASSAGE_MAX_TOKENS = count_words(indexing.passage_header(norm, unit)) + 12
    settings.PASSAGE_OVERLAP_TOKENS = 0

    drafts = indexing.build_passages(reading)

    assert [d.text for d in drafts] == sentences
    assert_well_formed(unit, drafts, settings.PASSAGE_MAX_TOKENS)
