"""Recuperación por tres caminos y unión de los candidatos (T-032; plan 001,
"Recuperación"; ADR-0003, ADR-0007).

Los tres caminos (por significado, por palabras y por referencia exacta) leen de
`consultable_units(fecha)` con `repealed` falso, con la fecha de autorización que recibe
la recuperación. Se unen sin repetir pasajes y sin fórmula de fusión: el orden lo pone el
reranker. Cada candidato registra por qué caminos entró. Cada camino y el reranker se
pueden apagar por parámetro, para la comparación quitando piezas de las evals.

Con los dobles de embeddings y reranker de `tests/conftest.py`; los textos son
sintéticos (P4).
"""

import json
from datetime import date

import pytest

from evaluon.queries import retrieval
from tests.conftest import unit_vector

REFERENCE_DATE = date(2024, 5, 20)

ONLY_SEMANTIC = (retrieval.SEMANTIC,)
ONLY_WORDS = (retrieval.WORDS,)
ONLY_REFERENCE = (retrieval.REFERENCE,)


def candidate_units(result):
    return {candidate.unit_id for candidate in result.candidates}


def by_unit(result):
    return {candidate.unit_id: candidate for candidate in result.candidates}


def base_units(units):
    return {u.pk for k, u in units.items() if "inc-" not in k}


def pks(units, *keys):
    return {units[key].pk for key in keys}


# --- Detección de referencias exactas --------------------------------------------------


@pytest.mark.parametrize("question, articles", [
    ("¿Qué dice el artículo 23?", {"23"}),
    ("¿Qué dice el articulo 23?", {"23"}),
    ("ARTÍCULO 23", {"23"}),
    ("según el art. 5 inc. b", {"5"}),
    ("según el art 5, inciso b)", {"5"}),
    ("el inciso b del artículo 5", {"5"}),
    ("artículo 7°", {"7"}),
    ("artículo 7º", {"7"}),
    ("art. Nº 8", {"8"}),
    ("¿Qué establece el 14 bis?", {"14 bis"}),
    ("artículo 14 bis de la 297/03", {"14 bis"}),
    ("artículo 14 ter", {"14 ter"}),
    ("artículos de la ley", set()),
    ("el arte de contratar 5 veces", set()),
    ("¿Qué garantía hay que presentar?", set()),
])
def test_article_references_are_detected(question, articles):
    """REQ-008: el patrón de referencia exacta detecta el número de artículo escrito como
    "artículo 23", "art. 5 inc. b" o "14 bis", con o sin tilde y en mayúsculas o
    minúsculas; si nombra un inciso, cuenta el artículo que lo contiene. Una pregunta sin
    número de artículo no da referencia."""
    assert retrieval.find_references(question).articles == frozenset(articles)


@pytest.mark.parametrize("question, norms", [
    ("Disposición 297/03", {("297", 3, 2)}),
    ("297/2003", {("297", 2003, 4)}),
    ("la Disposición 247/2022", {("247", 2022, 4)}),
    ("Disp. 247/22 y Disposición 297/2003", {("247", 22, 2), ("297", 2003, 4)}),
    ("Ley 13.064/47", {("13064", 47, 2)}),
    ("procedimiento autorizado el 15/03/2021", set()),
    ("artículo 1", set()),
])
def test_norm_references_are_detected(question, norms):
    """REQ-020, REQ-008: el patrón detecta la norma por número y año, como
    "Disposición 297/03", "297/2003" o "Disposición 247/2022", con año de dos o de cuatro
    cifras. Una fecha escrita con barras no es una norma."""
    found = {(ref.number, ref.year, ref.year_digits)
             for ref in retrieval.find_references(question).norms}
    assert found == norms


# --- Camino por palabras -----------------------------------------------------------------


@pytest.fixture
def word_norm(make_norm, make_document, make_reading, make_passage):
    """Una norma validada con tres artículos de texto distinto. Los vectores de los
    pasajes quedan lejos del de la pregunta."""
    reading = make_reading(make_document(make_norm()), [
        ("art-1", "ARTICULO 1.- Las licitaciones públicas se anuncian marca-uno."),
        ("art-2", "ARTICULO 2.- La garantía de oferta es del cinco por ciento marca-dos."),
        ("art-3", "ARTICULO 3.- Los plazos se cuentan en días hábiles marca-tres."),
    ], passages=False)
    units = reading.units_by_key
    for position, key in enumerate(["art-1", "art-2", "art-3"], start=10):
        make_passage(units[key], embedding=unit_vector(position))
    return units


@pytest.mark.django_db
def test_words_find_plural_without_accents(word_norm, fake_embeddings, fake_reranker):
    """REQ-008: una pregunta sin tildes encuentra el pasaje por palabras aunque el pasaje
    use el plural: "licitacion" encuentra "licitaciones" (ADR-0007)."""
    result = retrieval.retrieve("¿como se publica una licitacion?", REFERENCE_DATE,
                                paths=ONLY_WORDS)

    assert candidate_units(result) == pks(word_norm, "art-1")
    [candidate] = result.candidates
    assert candidate.path == (retrieval.WORDS,)
    assert candidate.distance is None


@pytest.mark.django_db
def test_words_are_joined_by_or(word_norm, fake_embeddings, fake_reranker):
    """REQ-008: las palabras de la pregunta se unen por "o": basta que un pasaje tenga una
    de ellas. Con "y", ningún pasaje tendría las dos."""
    result = retrieval.retrieve("licitación garantía", REFERENCE_DATE, paths=ONLY_WORDS)

    assert candidate_units(result) == pks(word_norm, "art-1", "art-2")


@pytest.mark.django_db
def test_words_ignore_search_syntax_in_the_question(word_norm, fake_embeddings,
                                                    fake_reranker):
    """REQ-008: comillas, signos y guiones de la pregunta no cambian el camino por
    palabras: no se leen como frase exacta ni como exclusión."""
    result = retrieval.retrieve('¿"garantía -licitaciones" o plazos?', REFERENCE_DATE,
                                paths=ONLY_WORDS)

    assert candidate_units(result) == pks(word_norm, "art-1", "art-2", "art-3")


@pytest.mark.django_db
def test_words_path_takes_up_to_the_limit(settings, word_norm, fake_embeddings,
                                          fake_reranker):
    """REQ-008: el camino por palabras trae hasta `RETRIEVAL_CANDIDATES_PER_PATH`
    pasajes."""
    settings.RETRIEVAL_CANDIDATES_PER_PATH = 2

    result = retrieval.retrieve("licitaciones garantía plazos", REFERENCE_DATE,
                                paths=ONLY_WORDS)

    assert len(result.candidates) == 2


@pytest.mark.django_db
def test_words_over_the_limit_keep_the_best_ts_rank(settings, make_norm, make_document,
                                                    make_reading, fake_embeddings,
                                                    fake_reranker):
    """REQ-008: con más coincidencias por palabras que `RETRIEVAL_CANDIDATES_PER_PATH`,
    se quedan las de mejor `ts_rank`, no las primeras que se cargaron: la que más repite
    la palabra entra aunque sea la última."""
    settings.RETRIEVAL_CANDIDATES_PER_PATH = 2
    reading = make_reading(make_document(make_norm()), [
        ("art-1", "ARTICULO 1.- La garantía se presenta."),
        ("art-2", "ARTICULO 2.- Una garantía y otra garantía distinta."),
        ("art-3", "ARTICULO 3.- Garantía, garantía y garantía: tres garantías."),
    ])
    units = reading.units_by_key

    result = retrieval.retrieve("garantía", REFERENCE_DATE, paths=ONLY_WORDS)

    assert [c.unit_id for c in result.candidates] == [units["art-3"].pk,
                                                       units["art-2"].pk]


@pytest.mark.django_db
def test_words_do_not_search_the_header(make_norm, make_document, make_reading,
                                        fake_embeddings, fake_reranker):
    """REQ-008 (aviso de T-009): la búsqueda por palabras mira el texto del pasaje y no su
    encabezado; el nombre de la norma no la hace coincidir."""
    norm = make_norm(citation="Norma Zapallar 1/2099")
    make_reading(make_document(norm), [("art-1", "ARTICULO 1.- Texto sin la palabra.")])

    result = retrieval.retrieve("zapallar", REFERENCE_DATE, paths=ONLY_WORDS)

    assert result.candidates == []


@pytest.mark.django_db
def test_question_without_words_does_not_search_by_words(word_norm, fake_embeddings,
                                                         fake_reranker):
    """REQ-008: una pregunta sin palabras buscables (solo signos o palabras vacías) no
    trae nada por palabras."""
    assert retrieval.retrieve("¿?", REFERENCE_DATE, paths=ONLY_WORDS).candidates == []
    assert retrieval.retrieve("¿de la que?", REFERENCE_DATE,
                              paths=ONLY_WORDS).candidates == []


# --- Camino por referencia exacta --------------------------------------------------------


@pytest.fixture
def reference_norm(make_norm, make_document, make_reading, make_passage):
    """Una norma validada con artículos 5 (con incisos), 14 y 14 bis, y un artículo 7
    largo partido en dos pasajes."""
    norm = make_norm(number="555", year=2010)
    reading = make_reading(make_document(norm), [
        ("art-5", "ARTICULO 5.- Requisitos: a) primero; b) segundo marca-cinco."),
        ("art-5/inc-a", "a) primero;"),
        ("art-5/inc-b", "b) segundo marca-cinco."),
        ("art-7", "ARTICULO 7.- Primera parte larga. Segunda parte larga."),
        ("art-14", "ARTICULO 14.- Catorce marca-catorce."),
        ("art-14-bis", "ARTICULO 14 BIS.- Catorce bis marca-bis."),
    ], passages=False)
    units = reading.units_by_key
    for key in ("art-5", "art-14", "art-14-bis"):
        make_passage(units[key])
    make_passage(units["art-7"], text="ARTICULO 7.- Primera parte larga.", char_end=33)
    make_passage(units["art-7"], text="Segunda parte larga.", char_start=34)
    return units


@pytest.mark.django_db
def test_reference_with_inciso_brings_the_article(reference_norm, fake_embeddings,
                                                  fake_reranker):
    """REQ-008: "art. 5 inc. b" trae el artículo 5, que contiene el inciso, y no el inciso:
    los incisos no se recuperan por separado."""
    result = retrieval.retrieve("¿Qué pide el art. 5 inc. b?", REFERENCE_DATE,
                                paths=ONLY_REFERENCE)

    assert candidate_units(result) == pks(reference_norm, "art-5")
    assert result.candidates[0].path == (retrieval.REFERENCE,)
    assert fake_embeddings.calls == []


@pytest.mark.django_db
def test_reference_with_numeric_inciso_brings_only_the_article(
        make_norm, make_document, make_reading, fake_embeddings, fake_reranker):
    """REQ-008: "art. 14 inc. 1" trae el artículo 14, que contiene el inciso 1; el número
    del inciso no se toma por un artículo, así que el artículo 1 no entra."""
    reading = make_reading(make_document(make_norm()), [
        ("art-1", "ARTICULO 1.- Uno."),
        ("art-14", "ARTICULO 14.- Catorce: 1) primero; 2) segundo."),
        ("art-14/inc-1", "1) primero;"),
        ("art-14/inc-2", "2) segundo."),
    ])
    units = reading.units_by_key
    question = "¿Qué dice el art. 14 inc. 1?"

    result = retrieval.retrieve(question, REFERENCE_DATE, paths=ONLY_REFERENCE)

    assert retrieval.find_references(question).articles == frozenset({"14"})
    assert candidate_units(result) == pks(units, "art-14")


@pytest.mark.django_db
def test_reference_brings_only_articles(make_norm, make_document, make_reading,
                                        fake_embeddings, fake_reranker):
    """REQ-008: "artículo 3" trae el artículo 3 y no un considerando ni un anexo que lleven
    el mismo número: la referencia exacta es a artículos."""
    reading = make_reading(make_document(make_norm()), [
        ("considerando-3", "Que el tercer considerando sintético."),
        ("art-3", "ARTICULO 3.- Tercero."),
        ("anexo-3", "ANEXO 3 sintético."),
    ])
    units = reading.units_by_key
    assert {units[k].number for k in units} == {"3"}

    result = retrieval.retrieve("¿Qué dice el artículo 3?", REFERENCE_DATE,
                                paths=ONLY_REFERENCE)

    assert candidate_units(result) == pks(units, "art-3")


@pytest.mark.django_db
def test_reference_distinguishes_bis(reference_norm, fake_embeddings, fake_reranker):
    """REQ-008: "14 bis" trae el artículo 14 bis y no el 14; "artículo 14" trae el 14 y no
    el 14 bis."""
    bis = retrieval.retrieve("¿Qué dice el 14 bis?", REFERENCE_DATE, paths=ONLY_REFERENCE)
    plain = retrieval.retrieve("¿Qué dice el artículo 14?", REFERENCE_DATE,
                               paths=ONLY_REFERENCE)

    assert candidate_units(bis) == pks(reference_norm, "art-14-bis")
    assert candidate_units(plain) == pks(reference_norm, "art-14")


@pytest.mark.django_db
def test_reference_brings_every_passage_of_the_unit(reference_norm, fake_embeddings,
                                                    fake_reranker):
    """REQ-008: la referencia trae la unidad entera: todos sus pasajes llegan al
    reranker."""
    result = retrieval.retrieve("artículo 7", REFERENCE_DATE, paths=ONLY_REFERENCE)

    assert len(result.candidates) == 2
    assert candidate_units(result) == pks(reference_norm, "art-7")
    [unit] = result.units
    assert len(unit.passage_ids) == 2


@pytest.mark.django_db
def test_reference_to_unknown_norm_brings_nothing(reference_norm, fake_embeddings,
                                                  fake_reranker):
    """REQ-008: si la pregunta nombra una norma que no está consultable, la referencia no
    se amplía a las demás normas."""
    result = retrieval.retrieve("artículo 5 de la Disposición 999/2001", REFERENCE_DATE,
                                paths=ONLY_REFERENCE)

    assert result.candidates == []


@pytest.mark.django_db
def test_reference_ignores_dates_written_with_slashes(reference_norm, fake_embeddings,
                                                      fake_reranker):
    """REQ-008: una fecha con barras en la pregunta no se toma por una norma ni restringe
    la referencia."""
    result = retrieval.retrieve("artículo 5, procedimiento del 15/03/2021",
                                REFERENCE_DATE, paths=ONLY_REFERENCE)

    assert candidate_units(result) == pks(reference_norm, "art-5")


# --- REQ-020: referencia exacta y dos regímenes --------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("question", [
    "Artículo 1 de la Disposición 297/03",
    "¿qué dice el articulo 1 de la 297/2003?",
])
def test_named_old_regime_article_before_and_after_v(question, two_regimes,
                                                     fake_embeddings, fake_reranker):
    """REQ-020: con una fecha anterior a V, "Artículo 1 de la Disposición 297/03" trae
    `art-1` y `anexo-i/art-1` (de todas las partes de la norma); con una fecha posterior
    no trae ninguna de las dos, porque la norma está derogada a esa fecha, ni se pasa a
    otra norma."""
    old = two_regimes.old_units

    before = retrieval.retrieve(question, two_regimes.before_v, paths=ONLY_REFERENCE)
    after = retrieval.retrieve(question, two_regimes.after_v, paths=ONLY_REFERENCE)

    assert candidate_units(before) == pks(old, "art-1", "anexo-i/art-1")
    assert candidate_units(after) == set()


@pytest.mark.django_db
def test_named_new_regime_article_after_v(two_regimes, fake_embeddings, fake_reranker):
    """REQ-020: "Disposición 247/2022, artículo 2" trae el artículo 2 del cuerpo y el del
    anexo desde V, y nada antes de V, cuando la norma todavía no regía."""
    new = two_regimes.new_units
    question = "Disposición 247/2022, artículo 2"

    after = retrieval.retrieve(question, two_regimes.after_v, paths=ONLY_REFERENCE)
    before = retrieval.retrieve(question, two_regimes.before_v, paths=ONLY_REFERENCE)

    assert candidate_units(after) == pks(new, "art-2", "anexo/art-2")
    assert candidate_units(before) == set()


@pytest.mark.django_db
def test_article_without_norm_brings_the_regime_in_force(two_regimes, fake_embeddings,
                                                         fake_reranker):
    """REQ-020: "artículo 1" sin nombrar la norma trae los artículos 1 del régimen que rige
    a la fecha, en todas sus partes."""
    old, new = two_regimes.old_units, two_regimes.new_units

    before = retrieval.retrieve("artículo 1", two_regimes.before_v, paths=ONLY_REFERENCE)
    after = retrieval.retrieve("artículo 1", two_regimes.after_v, paths=ONLY_REFERENCE)

    assert candidate_units(before) == pks(old, "art-1", "anexo-i/art-1")
    assert candidate_units(after) == pks(new, "art-1", "anexo/art-1")


# --- REQ-005 y REQ-020 por los tres caminos --------------------------------------------

PATH_CASES = [
    pytest.param(ONLY_SEMANTIC, id="semantic"),
    pytest.param(ONLY_WORDS, id="words"),
    pytest.param(ONLY_REFERENCE, id="reference"),
]
PATH_QUESTION = "artículo 1 sobre licitaciones de la Disposición 9999/2099"


@pytest.fixture
def pending_and_validated(make_norm, make_document, make_reading, fake_embeddings):
    """Dos normas iguales, número 9999/2099 de distinto organismo: una con su lectura sin
    validar y otra validada. Su artículo 1 coincide con la pregunta por los tres caminos:
    vector idéntico al de la pregunta, la palabra "licitaciones" y la referencia exacta."""
    fake_embeddings.vectors[PATH_QUESTION] = unit_vector(7)
    made = {}
    for status, issuer in (("pending", "pendiente"), ("validated", "validado")):
        norm = make_norm(number="9999", year=2099, issuer=issuer)
        reading = make_reading(make_document(norm), [
            ("art-1", f"ARTICULO 1.- Régimen de licitaciones {issuer}."),
        ], status=status, passages=False)
        unit = reading.units_by_key["art-1"]
        unit.passages.create(
            order=1, char_start=0, char_end=len(unit.text), header=f"Norma {issuer}",
            text=unit.text, embedding=unit_vector(7), embedding_model="doble",
            embedding_revision="0" * 64,
        )
        made[status] = unit
    return made


@pytest.mark.django_db
@pytest.mark.parametrize("paths", PATH_CASES)
def test_unvalidated_norm_absent_from_every_path(paths, pending_and_validated,
                                                 fake_reranker):
    """REQ-005: dada una norma cargada y sin validar, no aparece por ninguno de los tres
    caminos, aunque coincida por vector, por palabras y por referencia; la misma norma
    validada sí aparece por ese camino."""
    result = retrieval.retrieve(PATH_QUESTION, REFERENCE_DATE, paths=paths)

    assert candidate_units(result) == {pending_and_validated["validated"].pk}
    reranked = [text for _, texts in fake_reranker.calls for text in texts]
    assert all("pendiente" not in text for text in reranked)


@pytest.mark.django_db
@pytest.mark.parametrize("paths", PATH_CASES)
def test_repealed_unit_absent_from_every_path(paths, two_regimes, fake_embeddings,
                                              fake_reranker):
    """REQ-020, REQ-008: una unidad derogada a la fecha no entra por ningún camino; antes
    de la derogación, sí. La pregunta coincide con `art-1` del régimen anterior por
    vector, por palabras ("licitaciones") y por referencia ("Artículo 1 de la Disposición
    297/03")."""
    question = "Artículo 1 de la Disposición 297/03 sobre licitaciones"
    target = two_regimes.old_units["art-1"]
    fake_embeddings.vectors[question] = list(target.passages.get().embedding)

    before = retrieval.retrieve(question, two_regimes.before_v, paths=paths)
    after = retrieval.retrieve(question, two_regimes.after_v, paths=paths)

    assert target.pk in candidate_units(before)
    assert candidate_units(after).isdisjoint(base_units(two_regimes.old_units))


@pytest.mark.django_db
@pytest.mark.parametrize("paths", [
    pytest.param(ONLY_SEMANTIC, id="semantic"),
    pytest.param(ONLY_WORDS, id="words"),
])
def test_new_regime_absent_before_v(paths, two_regimes, fake_embeddings, fake_reranker):
    """REQ-020: con una fecha anterior a V, la Disposición 247/2022 no aparece por
    significado ni por palabras, aunque la pregunta coincida con su artículo por vector y
    por palabras ("garantías"); desde V, sí aparece."""
    question = "garantías sintéticas"
    target = two_regimes.new_units["anexo/art-2"]
    fake_embeddings.vectors[question] = list(target.passages.get().embedding)

    before = retrieval.retrieve(question, two_regimes.before_v, paths=paths)
    after = retrieval.retrieve(question, two_regimes.after_v, paths=paths)

    assert candidate_units(before).isdisjoint(base_units(two_regimes.new_units))
    assert target.pk in candidate_units(after)


# --- Unión de los caminos ----------------------------------------------------------------


@pytest.fixture
def union_norm(make_norm, make_document, make_reading, make_passage, fake_embeddings):
    """Norma con tres artículos: `art-1` es el más cercano por vector y coincide por
    palabras, `art-2` coincide solo por palabras y `art-3` solo por referencia ("art.
    3"). Los textos no traen el encabezado "ARTICULO N", para que el número no coincida
    por palabras. Con un candidato por camino, `art-2` no entra."""
    question = "garantía art. 3"
    fake_embeddings.vectors[question] = unit_vector(0)
    reading = make_reading(make_document(make_norm()), [
        ("art-1", "La garantía se constituye marca-uno."),
        ("art-2", "Otra garantía distinta marca-dos."),
        ("art-3", "Sin relación marca-tres."),
    ], passages=False)
    units = reading.units_by_key
    make_passage(units["art-1"], embedding=unit_vector(0))
    make_passage(units["art-2"], embedding=unit_vector(500))
    make_passage(units["art-3"], embedding=unit_vector(600))
    return question, units


@pytest.mark.django_db
def test_union_without_repeats_records_every_path(settings, union_norm, fake_reranker):
    """REQ-008: los tres caminos se unen sin repetir pasajes; un pasaje que entra por dos
    caminos aparece una vez, con los dos caminos anotados, y llega una sola vez al
    reranker. La distancia queda solo en los que entraron por significado."""
    settings.RETRIEVAL_CANDIDATES_PER_PATH = 1
    question, units = union_norm
    fake_reranker.scores = {"marca-uno": 0.9, "marca-dos": 0.8, "marca-tres": 0.7}

    result = retrieval.retrieve(question, REFERENCE_DATE)
    found = by_unit(result)

    assert len(result.candidates) == len({c.passage_id for c in result.candidates})
    assert found[units["art-1"].pk].path == (retrieval.SEMANTIC, retrieval.WORDS)
    assert found[units["art-1"].pk].distance == pytest.approx(0.0, abs=1e-6)
    assert found[units["art-3"].pk].path == (retrieval.REFERENCE,)
    assert found[units["art-3"].pk].distance is None
    assert set(found) == pks(units, "art-1", "art-3")
    assert [found[units[k].pk].score for k in ("art-1", "art-3")] == [
        pytest.approx(0.9), pytest.approx(0.7)]
    [(_, documents)] = fake_reranker.calls
    assert len(documents) == len(result.candidates) == 2


@pytest.mark.django_db
def test_order_comes_from_the_reranker(union_norm, fake_reranker):
    """REQ-008: no hay fórmula de fusión: el orden de las unidades lo pone el puntaje del
    reranker, aunque la unidad haya entrado por un solo camino."""
    question, units = union_norm
    fake_reranker.scores = {"marca-uno": 0.2, "marca-dos": 0.6, "marca-tres": 0.95}

    result = retrieval.retrieve(question, REFERENCE_DATE)

    assert [u.unit_id for u in result.units] == [
        units["art-3"].pk, units["art-2"].pk, units["art-1"].pk]
    assert [u.unit_id for u in result.selected] == [units["art-3"].pk, units["art-2"].pk]


@pytest.mark.django_db
def test_record_has_paths_and_optional_distance(settings, union_norm, fake_reranker):
    """REQ-008 (P6): el registro de cada candidato trae pasaje, unidad, la lista de
    caminos, la distancia (vacía si no entró por significado) y el puntaje; el resultado
    trae cuántos pasajes y unidades aportó cada camino, y se guarda como JSON."""
    settings.RETRIEVAL_CANDIDATES_PER_PATH = 1
    question, units = union_norm
    fake_reranker.default = 0.4

    record = retrieval.retrieve(question, REFERENCE_DATE).as_record()

    assert json.loads(json.dumps(record)) == record
    entries = {c["unit"]: c for c in record["candidates"]}
    assert set(entries[units["art-1"].pk]) == {"passage", "unit", "path", "distance",
                                               "score"}
    assert entries[units["art-3"].pk]["path"] == ["reference"]
    assert entries[units["art-3"].pk]["distance"] is None
    assert record["path_counts"]["reference"] == {"passages": 1, "units": 1}
    assert record["path_counts"]["words"] == {"passages": 1, "units": 1}
    assert set(record["path_counts"]) == {"semantic", "words", "reference"}


@pytest.mark.django_db
def test_path_counts_show_long_units_filling_the_semantic_path(
        settings, make_norm, make_document, make_reading, make_passage, fake_embeddings,
        fake_reranker):
    """REQ-008 (aviso de T-031): si los candidatos por significado se llenan con varios
    pasajes de una misma unidad larga, el registro lo muestra: más pasajes que unidades."""
    settings.RETRIEVAL_CANDIDATES_PER_PATH = 3
    reading = make_reading(make_document(make_norm()), [
        ("art-1", "ARTICULO 1.- Uno. Dos. Tres."),
        ("art-2", "ARTICULO 2.- Otro."),
    ], passages=False)
    units = reading.units_by_key
    for order in range(1, 4):
        make_passage(units["art-1"], order=order, embedding=unit_vector(0))
    make_passage(units["art-2"], embedding=unit_vector(1))
    fake_embeddings.vectors["pregunta"] = unit_vector(0)

    result = retrieval.retrieve("pregunta", REFERENCE_DATE, paths=ONLY_SEMANTIC)

    assert result.path_counts == {"semantic": {"passages": 3, "units": 1}}


# --- Apagar caminos y reranker -------------------------------------------------------


@pytest.mark.django_db
def test_semantic_off_does_not_embed(union_norm, fake_embeddings, fake_reranker):
    """REQ-008: con el camino por significado apagado no se calcula el vector de la
    pregunta, y los parámetros registran los caminos usados."""
    question, units = union_norm

    result = retrieval.retrieve(question, REFERENCE_DATE,
                                paths=(retrieval.WORDS, retrieval.REFERENCE))

    assert fake_embeddings.calls == []
    assert candidate_units(result) == pks(units, "art-1", "art-2", "art-3")
    assert result.parameters["paths"] == ["words", "reference"]


@pytest.mark.django_db
def test_each_path_alone(settings, union_norm, fake_embeddings, fake_reranker):
    """REQ-008: cada camino se puede correr solo, para la comparación quitando piezas."""
    settings.RETRIEVAL_CANDIDATES_PER_PATH = 1
    question, units = union_norm

    semantic = retrieval.retrieve(question, REFERENCE_DATE, paths=ONLY_SEMANTIC)
    reference = retrieval.retrieve(question, REFERENCE_DATE, paths=ONLY_REFERENCE)

    assert candidate_units(semantic) == pks(units, "art-1")
    assert candidate_units(reference) == pks(units, "art-3")
    assert {c.path for c in semantic.candidates} == {(retrieval.SEMANTIC,)}


@pytest.mark.django_db
def test_no_paths_no_candidates(union_norm, fake_embeddings, fake_reranker):
    """REQ-008: con los tres caminos apagados no hay candidatos ni pedidos a los
    servicios."""
    question, _ = union_norm

    result = retrieval.retrieve(question, REFERENCE_DATE, paths=())

    assert result.candidates == []
    assert result.reason == "below_threshold"
    assert fake_embeddings.calls == [] and fake_reranker.calls == []


@pytest.mark.django_db
def test_unknown_path_is_rejected(fake_embeddings, fake_reranker):
    """REQ-008: un nombre de camino desconocido es un error de quien llama, no se ignora
    en silencio."""
    with pytest.raises(ValueError):
        retrieval.retrieve("pregunta", REFERENCE_DATE, paths=("bm25",))


@pytest.mark.django_db
def test_reranker_off(union_norm, fake_reranker):
    """REQ-008: con el reranker apagado no se lo llama; los candidatos quedan sin puntaje,
    las unidades en el orden de la unión (significado, palabras, referencia) y todas
    pasan, sin barrera de umbral. Los parámetros lo registran."""
    question, units = union_norm

    result = retrieval.retrieve(question, REFERENCE_DATE, rerank=False)

    assert fake_reranker.calls == []
    assert all(c.score is None for c in result.candidates)
    assert [u.unit_id for u in result.units][0] == units["art-1"].pk
    assert [u.unit_id for u in result.units][-1] == units["art-3"].pk
    assert result.selected == result.units
    assert result.max_score is None
    assert result.reason is None
    assert result.parameters["reranker"] is False
    assert json.loads(json.dumps(result.as_record())) == result.as_record()


@pytest.mark.django_db
def test_paths_require_the_reference_date(fake_embeddings, fake_reranker):
    """REQ-020: con cualquier combinación de caminos, la recuperación no reemplaza una
    fecha vacía por la del día."""
    with pytest.raises(ValueError):
        retrieval.retrieve("artículo 1", None, paths=ONLY_REFERENCE)
