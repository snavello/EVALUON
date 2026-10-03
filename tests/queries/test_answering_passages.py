"""Unidades largas mostradas por tramos (T-034; plan 001, "Recuperación", paso 6, y
"Cita").

De una unidad de más de 1.500 tokens se le muestran al modelo solo los pasajes que
superaron el umbral; la cita muestra siempre la unidad entera. La recuperación (T-033)
decide qué tramos van y se los pasa a `answer` en `passages`: `{id de unidad: [(inicio,
fin), …]}`, posiciones de caracteres relativas al texto de la unidad. `prompt_text` da el
texto de una unidad tal como se le muestra al modelo, para que T-033 cuente sus tokens
sobre el mismo texto que va en el pedido.

Con el doble del motor de `tests/conftest.py`; los textos son sintéticos (P4).
"""

from datetime import date

import pytest

from evaluon.queries import answering

QUESTION = "¿Qué garantía sintética corresponde a la oferta?"
DATE = date(2024, 5, 20)

LONG = ("ARTICULO 7.- Primera parte sintética. Segunda parte sintética. Tercera parte "
        "sintética. Cuarta parte sintética.")
SHORT = "ARTICULO 8.- Artículo sintético corto."

MARK = answering.OMITTED_MARK


def piece(start, end):
    """Tramo del texto de la unidad larga, con posiciones relativas a ese texto."""
    return LONG[start:end]


@pytest.fixture
def units(make_norm, make_document, make_reading):
    reading = make_reading(make_document(make_norm(category="regimen_especifico")),
                           [("art-7", LONG), ("art-8", SHORT)])
    return reading.units_by_key


def st(text, *aliases):
    return {"text": text, "citations": list(aliases), "regimes_differ": False}


def user_message(fake_generation):
    messages = fake_generation.calls[-1][0]
    return next(m["content"] for m in messages if m["role"] == "user")


def first_part():
    return (0, LONG.index(" Segunda"))


def third_part():
    start = LONG.index("Tercera")
    return (start, LONG.index(" Cuarta"))


# --- prompt_text ----------------------------------------------------------------------


@pytest.mark.django_db
def test_without_spans_prompt_text_is_the_whole_unit(units):
    """REQ-007: sin tramos (o con una lista vacía), el texto que se le muestra al modelo
    es la unidad entera, `canonical_text[char_start:char_end]`."""
    unit = units["art-7"]

    assert answering.prompt_text(unit) == answering.unit_text(unit) == LONG
    assert answering.prompt_text(unit, []) == LONG
    assert answering.prompt_text(unit, None) == LONG


@pytest.mark.django_db
def test_overlapping_spans_are_joined(units):
    """REQ-007: dos tramos que se solapan (o que se tocan) se muestran como uno solo, sin
    marca de omisión entre ellos; entre tramos separados va la marca visible, y también
    al principio o al final si se omitió texto ahí."""
    unit = units["art-7"]
    start, end = third_part()

    shown = answering.prompt_text(unit, [(0, 20), (10, first_part()[1]), (start, end)])

    assert shown == "\n".join([piece(0, first_part()[1]), MARK, piece(start, end), MARK])
    assert shown.count(MARK) == 2
    # Tramos que se tocan: no hay texto omitido entre ellos, no va marca.
    touching = answering.prompt_text(unit, [(0, 10), (10, 25)])
    assert touching == "\n".join([piece(0, 25), MARK])


@pytest.mark.django_db
def test_spans_out_of_order_are_shown_in_text_order(units):
    """REQ-007: los tramos se muestran en el orden del texto de la unidad, aunque lleguen
    en otro orden."""
    unit = units["art-7"]
    third = third_part()
    first = first_part()

    shown = answering.prompt_text(unit, [third, first])

    assert shown == answering.prompt_text(unit, [first, third])
    assert shown.index(piece(*first)) < shown.index(piece(*third))


@pytest.mark.django_db
def test_span_reaching_the_end_has_no_trailing_mark(units):
    """REQ-007: si el último tramo llega al final de la unidad, no va marca al final; si
    el primero no empieza al principio, va una al principio."""
    unit = units["art-7"]
    start = LONG.index("Cuarta")

    assert answering.prompt_text(unit, [(start, len(LONG))]) == \
        "\n".join([MARK, piece(start, len(LONG))])


@pytest.mark.django_db
@pytest.mark.parametrize("spans", [[(-1, 5)], [(5, 5)], [(10, 3)], [(0, len(LONG) + 1)]],
                         ids=["negative", "empty", "reversed", "past-the-end"])
def test_invalid_span_is_rejected(units, spans):
    """REQ-007: un tramo vacío, invertido o fuera del texto de la unidad es un error de
    quien llama, no un texto recortado en silencio."""
    with pytest.raises(ValueError):
        answering.prompt_text(units["art-7"], spans)


# --- answer con passages --------------------------------------------------------------


@pytest.mark.django_db
def test_request_shows_only_the_spans_and_matches_prompt_text(units, fake_generation):
    """REQ-007, REQ-008: con tramos para una unidad, el pedido muestra solo esos tramos
    con la marca de omisión, y el texto es exactamente `prompt_text(unidad, tramos)`;
    la unidad sin tramos va entera."""
    long_unit, short_unit = units["art-7"], units["art-8"]
    spans = [third_part(), first_part()]

    answering.answer(QUESTION, [long_unit.pk, short_unit.pk], reference_date=DATE,
                     passages={long_unit.pk: spans})

    content = user_message(fake_generation)
    assert answering.prompt_text(long_unit, spans) in content
    assert "Segunda parte sintética" not in content
    assert "Cuarta parte sintética" not in content
    assert LONG not in content
    assert answering.prompt_text(short_unit) == SHORT
    assert SHORT in content


@pytest.mark.django_db
def test_citation_keeps_the_whole_unit(units, fake_generation):
    """REQ-007, REQ-008: aunque al modelo se le muestren solo tramos, la cita se refiere a
    la unidad entera: el resultado la cita por su `id`, `units` trae su registro de
    siempre y el texto que se inserta es la unidad entera."""
    long_unit = units["art-7"]
    fake_generation.answer([st("La primera parte lo dice.", "U1")])

    answer = answering.answer(QUESTION, [long_unit.pk], reference_date=DATE,
                              passages={long_unit.pk: [first_part()]})

    without = answering.answer(QUESTION, [long_unit.pk], reference_date=DATE)
    assert answer.aliases == {"U1": long_unit.pk}
    assert answer.result["statements"][0]["citations"] == [long_unit.pk]
    assert answer.result == without.result
    assert answering.citation_texts(answer.result) == {long_unit.pk: LONG}


@pytest.mark.django_db
def test_without_passages_the_request_does_not_change(units, fake_generation):
    """REQ-008: sin `passages`, o con un mapa vacío, el pedido es el mismo que antes:
    todas las unidades enteras."""
    selected = [units["art-7"].pk, units["art-8"].pk]

    answering.answer(QUESTION, selected, reference_date=DATE)
    answering.answer(QUESTION, selected, reference_date=DATE, passages={})
    answering.answer(QUESTION, selected, reference_date=DATE,
                     passages={units["art-7"].pk: []})

    first, second, third = (call[0] for call in fake_generation.calls)
    assert first == second == third
    assert LONG in user_message(fake_generation)
    assert MARK not in user_message(fake_generation)


@pytest.mark.django_db
def test_passages_also_apply_without_date(units, fake_generation):
    """REQ-007: el camino sin fecha (`consulta-v1`) también muestra solo los tramos."""
    long_unit = units["art-7"]
    spans = [first_part()]

    answering.answer(QUESTION, [long_unit.pk], passages={long_unit.pk: spans})

    content = user_message(fake_generation)
    assert answering.prompt_text(long_unit, spans) in content
    assert "Cuarta parte sintética" not in content


@pytest.mark.django_db
def test_passages_for_a_unit_not_shown_is_an_error(units, fake_generation):
    """REQ-007: tramos para una unidad que no se le muestra al modelo son un error de
    quien llama, y no se llama al modelo."""
    with pytest.raises(ValueError):
        answering.answer(QUESTION, [units["art-8"].pk], reference_date=DATE,
                         passages={units["art-7"].pk: [first_part()]})
    assert fake_generation.calls == []
