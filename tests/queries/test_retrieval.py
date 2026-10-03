"""Recuperación por significado y reordenamiento con el reranker (T-017; plan 001,
"Recuperación", "Reordenamiento" y "Abstención").

La recuperación recibe la pregunta y la fecha de autorización del procedimiento, busca
por vector entre los pasajes de `consultable_units(fecha)` con `repealed` falso, puntúa
con el reranker encabezado más texto, agrupa por unidad base con su mejor puntaje y deja
pasar las unidades que alcanzan el umbral. Con los dobles de embeddings y reranker de
`tests/conftest.py`; los textos son sintéticos (P4).
"""

import math
from datetime import date

import pytest

from evaluon.queries import retrieval
from tests.conftest import unit_vector

REFERENCE_DATE = date(2024, 5, 20)
QUESTION = "¿Qué garantía hay que presentar con la oferta?"


def mixed_vector(*positions):
    """Vector normalizado con el mismo peso en cada posición."""
    vector = [0.0] * len(unit_vector())
    for position in positions:
        vector[position] = 1.0 / math.sqrt(len(positions))
    return vector


def candidate_units(result):
    return {candidate.unit_id for candidate in result.candidates}


def selected_units(result):
    return [unit.unit_id for unit in result.selected]


@pytest.fixture
def norm_with_units(make_norm, make_document, make_reading, make_passage):
    """Una norma con un artículo por vector, cada uno con un pasaje con ese vector y la
    marca `{mark}-art-N` en su texto. Devuelve la función que la arma."""

    def _make(vectors, mark="marca", **reading_options):
        keys = [f"art-{i}" for i in range(1, len(vectors) + 1)]
        reading = make_reading(
            make_document(make_norm()),
            [(key, f"ARTICULO {i}.- Texto sintético {mark}-{key}.")
             for i, key in enumerate(keys, start=1)],
            passages=False,
            **reading_options,
        )
        units = reading.units_by_key
        for key, vector in zip(keys, vectors):
            make_passage(units[key], embedding=vector)
        return units

    return _make


# --- REQ-005: una norma sin validar no aparece ---------------------------------------


@pytest.mark.django_db
def test_unvalidated_norm_is_not_a_candidate(norm_with_units, fake_embeddings,
                                             fake_reranker):
    """REQ-005: dada una norma incorporada y todavía no validada, cuando se consulta,
    entonces sus unidades no aparecen entre los candidatos ni llegan al reranker, aunque
    su vector sea idéntico al de la pregunta y el reranker le diera el puntaje máximo."""
    fake_embeddings.vectors[QUESTION] = unit_vector(0)
    pending = norm_with_units([unit_vector(0)], mark="pendiente", status="pending")
    validated = norm_with_units([unit_vector(1)])
    fake_reranker.scores = {"pendiente-art-1": 0.99, "marca-art-1": 0.7}

    result = retrieval.retrieve(QUESTION, REFERENCE_DATE)

    assert pending["art-1"].pk not in candidate_units(result)
    assert pending["art-1"].pk not in selected_units(result)
    assert candidate_units(result) == {validated["art-1"].pk}
    reranked = [text for _, texts in fake_reranker.calls for text in texts]
    assert reranked and all("pendiente" not in text for text in reranked)


# --- REQ-009: primera barrera de abstención ------------------------------------------


@pytest.mark.django_db
def test_all_scores_below_threshold_select_nothing(settings, norm_with_units,
                                                   fake_embeddings, fake_reranker):
    """REQ-009: con todos los puntajes bajo el umbral no hay unidades seleccionadas y el
    motivo es `below_threshold`; los candidatos quedan igual registrados con su
    puntaje, y el puntaje más alto es el mayor de ellos."""
    settings.RERANK_THRESHOLD = 0.5
    fake_embeddings.vectors[QUESTION] = unit_vector(0)
    units = norm_with_units([unit_vector(0), unit_vector(1)])
    fake_reranker.scores = {"marca-art-1": 0.49, "marca-art-2": 0.1}

    result = retrieval.retrieve(QUESTION, REFERENCE_DATE)

    assert result.selected == []
    assert result.reason == "below_threshold"
    assert result.max_score == pytest.approx(0.49)
    assert candidate_units(result) == {units["art-1"].pk, units["art-2"].pk}
    assert sorted(c.score for c in result.candidates) == pytest.approx([0.1, 0.49])


@pytest.mark.django_db
def test_nothing_consultable_is_below_threshold(fake_embeddings, fake_reranker):
    """REQ-009: sin pasajes consultables a la fecha, no hay candidatos, no se llama al
    reranker y el motivo es `below_threshold`, sin puntaje más alto."""
    result = retrieval.retrieve(QUESTION, REFERENCE_DATE)

    assert result.candidates == []
    assert result.selected == []
    assert result.reason == "below_threshold"
    assert result.max_score is None
    assert fake_reranker.calls == []


@pytest.mark.django_db
def test_score_equal_to_threshold_is_selected(settings, norm_with_units, fake_embeddings,
                                              fake_reranker):
    """REQ-009, REQ-008: una unidad cuyo puntaje es igual al umbral lo alcanza y queda
    seleccionada; una apenas por debajo, no."""
    settings.RERANK_THRESHOLD = 0.6
    units = norm_with_units([unit_vector(0), unit_vector(1)])
    fake_reranker.scores = {"marca-art-1": 0.6, "marca-art-2": 0.5999}

    result = retrieval.retrieve(QUESTION, REFERENCE_DATE)

    assert selected_units(result) == [units["art-1"].pk]
    assert result.reason is None


# --- REQ-008: la unidad pertinente queda seleccionada --------------------------------


@pytest.mark.django_db
def test_relevant_passage_selects_its_base_unit(settings, norm_with_units,
                                                fake_embeddings, fake_reranker):
    """REQ-008: dado un pasaje pertinente, su unidad base queda seleccionada con el
    puntaje del reranker; las que no alcanzan el umbral quedan solo como candidatas."""
    settings.RERANK_THRESHOLD = 0.5
    fake_embeddings.vectors[QUESTION] = unit_vector(0)
    units = norm_with_units([unit_vector(0), unit_vector(1), unit_vector(2)])
    fake_reranker.scores = {"marca-art-2": 0.93}

    result = retrieval.retrieve(QUESTION, REFERENCE_DATE)

    assert selected_units(result) == [units["art-2"].pk]
    assert result.selected[0].score == pytest.approx(0.93)
    assert result.reason is None
    assert result.max_score == pytest.approx(0.93)
    assert len(result.candidates) == 3


@pytest.mark.django_db
def test_passages_are_grouped_by_base_unit_with_best_score(
        settings, make_norm, make_document, make_reading, make_passage, fake_embeddings,
        fake_reranker):
    """REQ-008: los pasajes de una misma unidad base se agrupan; la unidad entra una sola
    vez, con el mejor puntaje de sus pasajes. Los incisos no generan pasajes: lo que
    queda seleccionado es el artículo que los contiene."""
    settings.RERANK_THRESHOLD = 0.5
    reading = make_reading(make_document(make_norm()), [
        ("art-1", "ARTICULO 1.- Primera parte pasaje-uno. Segunda parte pasaje-dos."),
        ("art-1/inc-a", "pasaje-dos"),
        ("art-2", "ARTICULO 2.- Otro tema pasaje-tres."),
    ], passages=False)
    units = reading.units_by_key
    make_passage(units["art-1"], text="ARTICULO 1.- Primera parte pasaje-uno.",
                 char_end=38, embedding=unit_vector(0))
    make_passage(units["art-1"], text="Segunda parte pasaje-dos.", char_start=39,
                 embedding=unit_vector(1))
    make_passage(units["art-2"], embedding=unit_vector(2))
    fake_reranker.scores = {"pasaje-uno": 0.55, "pasaje-dos": 0.91, "pasaje-tres": 0.7}

    result = retrieval.retrieve(QUESTION, REFERENCE_DATE)

    assert selected_units(result) == [units["art-1"].pk, units["art-2"].pk]
    assert [u.score for u in result.selected] == [pytest.approx(0.91), pytest.approx(0.7)]
    assert len(result.selected[0].passage_ids) == 2
    assert len(result.candidates) == 3
    assert units["art-1/inc-a"].pk not in candidate_units(result)


@pytest.mark.django_db
def test_semantic_path_takes_nearest_passages_by_cosine(settings, norm_with_units,
                                                        fake_embeddings, fake_reranker):
    """REQ-008: el camino por significado toma los pasajes más cercanos a la pregunta por
    distancia coseno, hasta `RETRIEVAL_CANDIDATES_PER_PATH`; el más lejano no llega al
    reranker. Cada candidato registra su camino, su distancia y su puntaje."""
    settings.RETRIEVAL_CANDIDATES_PER_PATH = 2
    fake_embeddings.vectors[QUESTION] = unit_vector(0)
    # art-1 es el más cercano (distancia 0), art-3 el segundo (≈0,29) y art-2 el más
    # lejano (distancia 1). La escala no cuenta en el coseno: art-3 va con largo 5.
    far = unit_vector(1)
    near = [5 * x for x in mixed_vector(0, 1)]
    units = norm_with_units([unit_vector(0), far, near])
    fake_reranker.default = 0.2

    result = retrieval.retrieve(QUESTION, REFERENCE_DATE)

    assert [c.unit_id for c in result.candidates] == [units["art-1"].pk, units["art-3"].pk]
    assert [c.path for c in result.candidates] == [("semantic",), ("semantic",)]
    assert result.candidates[0].distance == pytest.approx(0.0, abs=1e-6)
    assert result.candidates[1].distance == pytest.approx(1 - 1 / math.sqrt(2), abs=1e-6)
    assert all(c.score == pytest.approx(0.2) for c in result.candidates)
    assert fake_embeddings.calls == [[QUESTION]]


@pytest.mark.django_db
def test_reranker_scores_header_and_text_against_question(norm_with_units,
                                                          fake_embeddings, fake_reranker):
    """REQ-008: el reranker recibe la pregunta y, por cada pasaje, su encabezado más su
    texto, en un solo pedido."""
    units = norm_with_units([unit_vector(0)])
    passage = units["art-1"].passages.get()

    retrieval.retrieve(QUESTION, REFERENCE_DATE)

    assert fake_reranker.calls == [(QUESTION, [f"{passage.header}\n{passage.text}"])]


@pytest.mark.django_db
def test_candidate_record_is_serializable(norm_with_units, fake_embeddings, fake_reranker):
    """REQ-008: cada candidato se entrega como registro con pasaje, unidad, camino,
    distancia y puntaje, listo para guardar en el registro de la consulta (P6), junto con
    los parámetros usados."""
    import json

    units = norm_with_units([unit_vector(0)])
    fake_reranker.scores = {"marca-art-1": 0.8}

    result = retrieval.retrieve(QUESTION, REFERENCE_DATE)
    record = result.as_record()

    assert json.loads(json.dumps(record)) == record
    [candidate] = record["candidates"]
    assert candidate["unit"] == units["art-1"].pk
    assert candidate["passage"] == units["art-1"].passages.get().pk
    assert candidate["path"] == ["semantic"]
    assert candidate["score"] == pytest.approx(0.8)
    assert record["reference_date"] == REFERENCE_DATE.isoformat()
    assert record["parameters"]["rerank_threshold"] == pytest.approx(0.5)
    assert record["parameters"]["candidates_per_path"] == 30
    assert record["parameters"]["paths"] == ["semantic", "words", "reference"]
    assert record["parameters"]["reranker"] is True


@pytest.mark.django_db
def test_reranker_document_comes_from_indexing(monkeypatch, norm_with_units,
                                               fake_embeddings, fake_reranker):
    """REQ-008: el texto que puntúa el reranker sale de la única
    `indexing.passage_document`, la misma con que se calculó el vector del pasaje; la
    recuperación no tiene una definición propia."""
    from evaluon.norms import indexing

    norm_with_units([unit_vector(0)])
    monkeypatch.setattr(indexing, "passage_document",
                        lambda header, text: f"DOC[{header}|{text}]")

    retrieval.retrieve(QUESTION, REFERENCE_DATE)

    [(_, documents)] = fake_reranker.calls
    assert documents and all(d.startswith("DOC[") for d in documents)
    assert not hasattr(retrieval, "passage_document")


# --- Fecha de autorización -----------------------------------------------------------


@pytest.mark.django_db
def test_retrieval_reads_what_applies_at_the_reference_date(two_regimes, fake_embeddings,
                                                            fake_reranker):
    """REQ-008 (con la fecha de autorización, REQ-020): la recuperación lee de
    `consultable_units(fecha)` con `repealed` falso. Antes de V son candidatas las
    unidades del régimen anterior y no las del nuevo; desde V, las del régimen anterior
    están derogadas y no sostienen respuestas, y entran las del nuevo."""
    old = {u.pk for k, u in two_regimes.old_units.items() if "inc-" not in k}
    new = {u.pk for u in two_regimes.new_units.values()}

    before = retrieval.retrieve(QUESTION, two_regimes.before_v)
    after = retrieval.retrieve(QUESTION, two_regimes.after_v)
    nothing = retrieval.retrieve(QUESTION, two_regimes.before_all)

    assert candidate_units(before) == old
    assert candidate_units(after) == new
    assert candidate_units(nothing) == set()


@pytest.mark.django_db
def test_retrieval_requires_the_reference_date(fake_embeddings, fake_reranker):
    """REQ-008 (regla de la fecha de autorización): la recuperación no reemplaza una fecha
    vacía por la del día; sin fecha, no busca."""
    with pytest.raises(ValueError):
        retrieval.retrieve(QUESTION, None)
    assert fake_embeddings.calls == []
