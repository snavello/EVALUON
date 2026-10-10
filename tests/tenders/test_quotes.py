"""Ubicar un fragmento literal dentro de un tramo (REQ-025; plan 003, "Extracción: qué
recibe y qué devuelve el modelo" y "Cita"; T-073).

Textos inventados (P4). Son pruebas de la función sola, sin base de datos.
"""

from types import SimpleNamespace

import pytest

from evaluon.tenders.proposal import quotes

TEXT = ("1.1. La oferta deberá presentarse en pesos. La oferta deberá presentarse con "
        "firma.\nSegunda línea del tramo.")


def test_locate_returns_the_exact_positions():
    """REQ-025: el fragmento se busca exacto y se devuelve su lugar dentro del tramo."""
    quote = "La oferta deberá presentarse en pesos."
    span = quotes.locate(TEXT, quote)

    assert span == (5, 5 + len(quote))
    assert TEXT[span[0]:span[1]] == quote


def test_locate_ignores_only_the_spaces_at_the_ends():
    """REQ-025: los espacios de los extremos no cuentan; el resto se compara tal cual."""
    span = quotes.locate(TEXT, "  La oferta deberá presentarse en pesos.  \n")

    assert TEXT[span[0]:span[1]] == "La oferta deberá presentarse en pesos."


@pytest.mark.parametrize("quote", [
    "la oferta deberá presentarse en pesos.",      # otra mayúscula
    "Segunda línea del tramo. Y más",              # sobra texto que el tramo no tiene
    "La oferta debera presentarse en pesos.",      # sin tilde
    "La oferta deberá presentarze en pesos.",      # una letra cambiada
])
def test_locate_is_exact(quote):
    """REQ-025: la copia tiene que ser letra por letra; si no, no se ubica."""
    assert quotes.locate(TEXT, quote) is None


@pytest.mark.parametrize("quote", ["", "   ", "\n", None])
def test_empty_quote_is_not_located(quote):
    """REQ-025: una cita vacía no se ubica."""
    assert quotes.locate(TEXT, quote) is None


def test_first_occurrence_not_used_is_taken():
    """REQ-025: si el fragmento aparece más de una vez, se toma la primera aparición
    cuyas posiciones todavía no se usaron."""
    quote = "La oferta deberá presentarse"
    first = quotes.locate(TEXT, quote)
    second = quotes.locate(TEXT, quote, used={first})

    assert first[0] < second[0]
    assert TEXT[second[0]:second[1]] == quote
    assert quotes.locate(TEXT, quote, used={first, second}) is None


def test_absolute_moves_the_span_to_the_canonical_text():
    """REQ-025: las posiciones del tramo se llevan al texto canónico de la lectura."""
    segment = SimpleNamespace(char_start=1000, char_end=1000 + len(TEXT))

    assert quotes.absolute(segment, (6, 10)) == (1006, 1010)
    assert quotes.whole(segment) == (1000, 1000 + len(TEXT))


def test_line_breaks_and_spaces_may_differ():
    """REQ-025: la cita puede traer saltos de línea o espacios distintos de los del tramo;
    se ubica igual y las posiciones son las del texto del tramo."""
    span = quotes.locate(TEXT, "La oferta  deberá\npresentarse en   pesos.")

    assert TEXT[span[0]:span[1]] == "La oferta deberá presentarse en pesos."
    span = quotes.locate(TEXT, "firma. Segunda  línea\ndel tramo.")
    assert TEXT[span[0]:span[1]] == "firma.\nSegunda línea del tramo."


def test_collapsed_search_keeps_the_rule_for_repeated_quotes():
    """REQ-025: con espacios distintos, si aparece dos veces se toma la primera
    aparición no usada, como en la búsqueda exacta."""
    quote = "La oferta\ndeberá presentarse"
    first = quotes.locate(TEXT, quote)
    second = quotes.locate(TEXT, quote, used={first})

    assert first[0] < second[0]
    assert TEXT[second[0]:second[1]].startswith("La oferta deberá presentarse")
    assert quotes.locate(TEXT, quote, used={first, second}) is None


# --- T-234: la cita se amplía a la unidad de sentido (REQ-101) ----------------------------------


def test_locate_unit_returns_the_models_fragment_and_its_sentence():
    """REQ-101, REQ-025: el fragmento se ubica como siempre y se amplía a la oración; la
    ampliación sigue siendo un recorte contiguo del tramo."""
    fragment, expansion = quotes.locate_unit(TEXT, "presentarse con firma")

    assert TEXT[fragment[0]:fragment[1]] == "presentarse con firma"
    assert TEXT[expansion.span[0]:expansion.span[1]] == "La oferta deberá presentarse con firma."
    assert expansion.span == expansion.unit and expansion.too_long is False


def test_locate_unit_does_not_find_what_locate_does_not_find():
    """REQ-025: un fragmento que no está en el tramo no se ubica, ni se amplía."""
    assert quotes.locate_unit(TEXT, "La oferta debera presentarse en pesos.") is None


def test_locate_unit_keeps_the_used_positions_rule():
    """REQ-025: con el mismo fragmento dos veces, la segunda es otra aparición."""
    quote = "La oferta deberá presentarse"
    first, _ = quotes.locate_unit(TEXT, quote)
    second, _ = quotes.locate_unit(TEXT, quote, used={first})

    assert first[0] < second[0]


def test_locate_unit_without_expansion_leaves_the_fragment():
    """REQ-101: el texto de una tabla no tiene oraciones: con `expand=False` la cita queda en
    el fragmento y no hay unidad."""
    fragment, expansion = quotes.locate_unit(TEXT, "presentarse con firma", expand=False)

    assert expansion.span == fragment and expansion.unit is None
