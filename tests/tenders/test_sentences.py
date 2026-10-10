"""Oraciones y unidad de sentido de un tramo (REQ-101; plan 015, T-234; ADR-0054, reglas 1
a 3).

Los textos son inventados con la forma de los pedazos del diagnóstico del 2026-10-10 (P4):
un fragmento que empieza con «e incluir…», «deberán incluir…» o «y la Compañía en el
campo…», incisos que llegan sin el encabezado de su punto, y el ejemplo del perro del
responsable («que tenga cuatro patas, dos ojos y de color marrón»), que va en una sola fila.
No usan base ni modelo.
"""

from types import SimpleNamespace

import pytest

from evaluon.tenders.proposal import filter as row_filter
from evaluon.tenders.proposal import sentences
from evaluon.tenders.proposal.sentences import (
    expand_to_sentence,
    heading_of,
    is_continuation,
    parent_key,
    sentence_spans,
)


def cut(text, span):
    return text[span[0]:span[1]]


# --- Las funciones de oración se mudaron sin cambiar de comportamiento -----------------------


def test_the_filter_keeps_the_public_names_of_the_sentence_functions():
    """REQ-101: `filter.py` importa las funciones de oración de `sentences.py` con los
    mismos nombres, así que quien las llamaba no cambia."""
    for name in ("ABBREVIATIONS", "SENTENCE_END", "_sentence_ends", "sentence_range",
                 "sentence_bounds"):
        assert getattr(row_filter, name) is getattr(sentences, name), name


@pytest.mark.parametrize("abbr", ["art.", "inc.", "Dec.", "S.A.", "Res.", "Disp.", "nro.",
                                  "J.", "cfr.", "pág."])
def test_a_dot_after_an_abbreviation_does_not_end_the_sentence(abbr):
    """REQ-101: la oración no se corta tras una abreviatura conocida ni tras una inicial; el
    fragmento "5 del reglamento" se amplía a la oración entera."""
    text = f"El pago se hará conforme al {abbr} 5 del reglamento vigente. Otra frase distinta."
    start = text.index("5 del")

    result = expand_to_sentence(text, (start, start + len("5 del reglamento")))

    assert cut(text, result.span) == (
        f"El pago se hará conforme al {abbr} 5 del reglamento vigente.")


def test_a_dot_after_a_common_word_ends_the_sentence():
    """REQ-101: un punto tras una palabra común sí termina la oración."""
    text = "La oferta se presenta firmada. La garantía es del 5 % del monto."
    start = text.index("5 %")

    result = expand_to_sentence(text, (start, start + 3))

    assert cut(text, result.span) == "La garantía es del 5 % del monto."


def test_closing_marks_end_a_sentence():
    """REQ-101: `?` y `!` también cierran la oración."""
    text = "¿Hay prórroga? Se presenta la oferta firmada."
    assert [cut(text, s) for s in sentence_spans(text)] == [
        "¿Hay prórroga?", "Se presenta la oferta firmada."]


# --- El número de la cláusula, la viñeta y la letra del inciso no son la oración -----------


@pytest.mark.parametrize("label", ["1.1.", "10.2.1.", "•", "−", "a)"])
def test_the_label_of_the_segment_is_not_part_of_the_sentence(label):
    """REQ-101: la oración empieza en su primera palabra, no en el rótulo del tramo."""
    sentence = "Los oferentes deberán constituir una garantía del 5 % del monto."
    text = f"{label} {sentence}"

    result = expand_to_sentence(text, (text.index("constituir"), text.index("constituir") + 10))

    assert cut(text, result.span) == sentence


def test_a_number_inside_the_sentence_is_not_a_label():
    """REQ-101: "5 %" o "3.972 kcal" dentro de la oración no la parten."""
    text = "El aporte es de 3.972 kcal por unidad y no debe superar el 5 % del peso."
    assert [cut(text, s) for s in sentence_spans(text)] == [text]


# --- Las enumeraciones de una oración son una sola fila -------------------------------------


DOG = "Quiero comprar un perro que tenga cuatro patas, dos ojos y de color marrón."


@pytest.mark.parametrize("fragment", ["cuatro patas", "dos ojos", "de color marrón",
                                      "que tenga cuatro patas, dos ojos"])
def test_every_piece_of_an_enumeration_expands_to_the_same_whole_sentence(fragment):
    """REQ-101 (ejemplo del perro del responsable): «cuatro patas», «dos ojos» y «de color
    marrón» son partes de una misma oración: los tres fragmentos se amplían a la misma
    unidad, que es una sola fila."""
    start = DOG.index(fragment)

    result = expand_to_sentence(DOG, (start, start + len(fragment)))

    assert cut(DOG, result.span) == DOG
    assert result.too_long is False


def test_fragments_of_the_diagnosis_without_subject_expand_to_their_sentence():
    """REQ-101: los pedazos «e incluir IVA», «deberán incluir impuestos» y «y la Compañía en el
    campo “Entidad Legal”» (texto inventado de la misma forma) quedan con la oración que los
    contiene."""
    cases = [
        ("Las ofertas se cotizarán en pesos argentinos por renglón e incluir IVA.",
         "e incluir IVA"),
        ("Los precios cotizados serán firmes y deberán incluir impuestos y tasas.",
         "deberán incluir impuestos"),
        ("El formulario se completa con la razón social en el campo “Razón Social” y la "
         "Compañía en el campo “Entidad Legal”.",
         "y la Compañía en el campo “Entidad Legal”"),
    ]
    for sentence, fragment in cases:
        start = sentence.index(fragment)
        result = expand_to_sentence(sentence, (start, start + len(fragment)))
        assert cut(sentence, result.span) == sentence, fragment


# --- Las oraciones cortas contiguas del mismo asunto van juntas -------------------------------


def test_a_short_sentence_that_starts_with_deberan_joins_the_previous_one():
    """REQ-101: «Deberán incluir impuestos.» no tiene sujeto propio y sigue a la anterior: si
    el modelo señala la primera, la unidad incluye la segunda."""
    first = "Los precios se expresarán en pesos argentinos por renglón."
    second = "Deberán incluir impuestos y tasas."
    text = f"{first} {second}"

    result = expand_to_sentence(text, (0, 20))

    assert cut(text, result.span) == text


def test_the_pointed_sentence_may_be_the_one_that_continues():
    """REQ-101: si el modelo señala la oración que continúa, la unidad incluye la anterior."""
    first = "Los precios se expresarán en pesos argentinos por renglón."
    second = "Deberán incluir impuestos y tasas."
    text = f"{first} {second}"
    start = text.index("impuestos")

    result = expand_to_sentence(text, (start, start + 9))

    assert cut(text, result.span) == text


def test_la_misma_and_esto_and_lowercase_continue_the_previous_sentence():
    """REQ-101: «La misma…», «Esto…» y lo que empieza en minúscula siguen el asunto, y se
    encadenan: la unidad es el conjunto de oraciones cortas contiguas."""
    head = "La garantía de oferta será del cinco por ciento del monto total ofertado."
    text = (f"{head} La misma deberá constituirse en pesos. Esto no admite excepciones. "
            "y se devolverá al finalizar.")

    result = expand_to_sentence(text, (0, 10))

    assert cut(text, result.span) == text


def test_a_sentence_with_its_own_subject_does_not_join():
    """REQ-101: una oración con sujeto propio abre otro asunto y no se une."""
    first = "Los oferentes deberán cotizar en pesos."
    second = "La entrega se hará dentro de los quince días hábiles."
    text = f"{first} {second}"

    result = expand_to_sentence(text, (0, 10))

    assert cut(text, result.span) == first


def test_a_long_continuation_does_not_join():
    """REQ-101: solo se unen oraciones cortas: una continuadora larga abre su propia unidad."""
    first = "La garantía se constituye en pesos."
    second = "Deberá " + "ser presentada y mantenida en las condiciones que fije el organismo " * 6
    text = f"{first} {second.strip()}."

    result = expand_to_sentence(text, (0, 10))

    assert cut(text, result.span) == first


def test_a_fragment_that_crosses_sentences_covers_those_it_touches():
    """REQ-101: si el fragmento cruza varias oraciones, la unidad abarca las que toca."""
    text = ("Primero se presenta la oferta. Después se firma el acta. "
            "Luego se abre el sobre.")
    start = text.index("se presenta")
    stop = text.index("el acta") + len("el acta")

    result = expand_to_sentence(text, (start, stop))

    assert cut(text, result.span) == "Primero se presenta la oferta. Después se firma el acta."


def test_the_unit_always_contains_the_fragment():
    """REQ-101: la ampliación nunca recorta lo que el modelo señaló, ni siquiera si el
    fragmento incluye el número de la cláusula."""
    text = "1.1. Los oferentes deberán constituir una garantía."

    result = expand_to_sentence(text, (0, text.index("constituir")))

    assert result.span[0] == 0
    assert cut(text, result.span) == text


# --- Una unidad demasiado larga no se usa --------------------------------------------------------


def test_a_unit_longer_than_a_citation_keeps_the_models_fragment_for_review():
    """REQ-101: si la unidad pasa del largo máximo de una cita, queda el fragmento del modelo
    y se avisa, para que la Comisión lo revise; la unidad calculada queda registrada."""
    sentence = "Los oferentes deberán presentar " + ", ".join(f"documento {n}" for n in range(60)) + "."
    start = sentence.index("documento 5")

    result = expand_to_sentence(sentence, (start, start + 11), max_chars=200)

    assert result.too_long is True
    assert result.span == (start, start + 11)
    assert result.unit == (0, len(sentence))


def test_when_only_the_continuation_makes_it_too_long_the_sentence_is_kept():
    """REQ-101: si la oración sola cabe y con las continuadoras no, la cita es la oración."""
    first = "Los precios se expresarán en pesos."
    second = "Deberán incluir impuestos, tasas y contribuciones de toda clase."
    text = f"{first} {second}"

    result = expand_to_sentence(text, (0, 10), max_chars=len(first) + 5)

    assert cut(text, result.span) == first
    assert result.too_long is False
    assert cut(text, result.unit) == text


def test_the_limit_is_the_one_of_the_citations(settings):
    """REQ-101: sin otro valor, el largo máximo es `ASSESSMENT_CITATION_MAX_CHARS`."""
    settings.ASSESSMENT_CITATION_MAX_CHARS = 30
    text = "Los oferentes deberán constituir una garantía del cinco por ciento."

    result = expand_to_sentence(text, (4, 12))

    assert result.too_long is True and result.span == (4, 12)


def test_a_fragment_outside_any_sentence_stays_as_it_is():
    """REQ-101: sin oración que tocar (texto vacío), el fragmento queda igual."""
    assert expand_to_sentence("", (0, 0)).span == (0, 0)
    assert expand_to_sentence("   ", (1, 2)).span == (1, 2)


@pytest.mark.parametrize("sentence, expected", [
    ("y la Compañía en el campo", True),
    ("e incluir IVA", True),
    ("Ni siquiera con prórroga", True),
    ("Deberán incluir impuestos", True),
    ("Deberá ser en pesos", True),
    ("La misma deberá ser en pesos", True),
    ("Las mismas se presentan firmadas", True),
    ("Esto no admite excepciones", True),
    ("de color marrón", True),
    ("Los oferentes deberán cotizar", False),
    ("La entrega se hará en quince días", False),
    ("Estos plazos son corridos", False),
    ("Debidamente firmada", False),
    ("Entregarán la muestra", False),
])
def test_which_sentences_start_without_their_own_subject(sentence, expected):
    """REQ-101: se reconocen las que empiezan en minúscula, con una conjunción, con «Deberá»
    o «Deberán», con «La misma» o con «Esto»; las demás tienen sujeto propio."""
    assert is_continuation(sentence) is expected


# --- Encabezado del punto ------------------------------------------------------------------------


def segment(key, text, kind="vineta"):
    return SimpleNamespace(key=key, text=text, segment_type=kind)


def lookup_of(*segments):
    by_key = {s.key: s for s in segments}
    return by_key.get


def test_parent_keys():
    """REQ-101: el padre de una viñeta o un inciso es su cláusula; el de una parte de un
    tramo largo, la primera parte; una clave sin barra no tiene padre."""
    assert parent_key("sec-ii/5.2/inc-b") == "sec-ii/5.2"
    assert parent_key("sec-ii/5.2/v-1") == "sec-ii/5.2"
    assert parent_key("sec-ii/5.2") == "sec-ii"
    assert parent_key("sec-iii/1.1#2") == "sec-iii/1.1"
    assert parent_key("sec-ii/5.2~2/v-1") == "sec-ii/5.2~2"
    assert parent_key("sec-ii") == ""
    assert parent_key("7.5.2") == ""


def test_an_item_of_a_list_gets_the_heading_of_its_point():
    """REQ-101: un inciso de una lista cuyo encabezado termina en «:» lleva el encabezado de
    su punto, sin el número de la cláusula, aunque su oración parezca entenderse."""
    parent = segment("sec-ii/5.2", "5.2. La oferta deberá incluir:", "clausula")
    item = segment("sec-ii/5.2/inc-b", "b) Copia certificada del estatuto social.")

    assert heading_of(item, lookup_of(parent, item)) == "La oferta deberá incluir:"


def test_an_item_that_starts_in_lowercase_gets_the_heading_of_its_point():
    """REQ-101: un inciso sin sujeto («copia certificada…») se entiende con el encabezado."""
    parent = segment("sec-ii/5.2", "5.2. La oferta deberá incluir:", "clausula")
    item = segment("sec-ii/5.2/inc-b", "b) copia certificada del estatuto social;")

    assert heading_of(item, lookup_of(parent, item)) == "La oferta deberá incluir:"


@pytest.mark.parametrize("text", [
    "Esto no admite excepciones.",
    "La misma deberá constituirse en pesos.",
    "y la Compañía en el campo “Entidad Legal”.",
    "Deberán incluir impuestos y tasas.",
])
def test_a_paragraph_that_does_not_stand_alone_gets_the_heading(text):
    """REQ-101: una oración que abre con «Esto», «La misma», «Deberán…», una conjunción o
    una minúscula lleva el encabezado de su punto."""
    parent = segment("sec-i/3", "3. FORMA DE COTIZAR Las ofertas se cotizan en pesos.",
                     "clausula")
    paragraph = segment("sec-i/3/p-1", text, "parrafo")

    assert heading_of(paragraph, lookup_of(parent, paragraph)).startswith("FORMA DE COTIZAR")


def test_a_segment_that_stands_alone_gets_no_heading():
    """REQ-101: una oración con sujeto propio, que no es un inciso de lista, no lleva
    encabezado: sería ruido."""
    parent = segment("sec-i/3", "3. Cotización.", "clausula")
    paragraph = segment("sec-i/3/p-1", "Los precios incluyen impuestos.", "parrafo")
    item = segment("sec-i/3/v-1", "• Los precios incluyen impuestos.")

    assert heading_of(paragraph, lookup_of(parent, paragraph)) == ""
    assert heading_of(item, lookup_of(parent, item)) == ""


def test_no_heading_without_a_parent_in_the_reading():
    """REQ-101: si el tramo padre no está, no hay encabezado (ni error)."""
    item = segment("sec-ii/5.2/inc-b", "b) copia certificada del estatuto social;")

    assert heading_of(item, lookup_of(item)) == ""
    assert heading_of(segment("pagina-3", "texto", "pagina"), lookup_of()) == ""


def test_a_long_heading_keeps_its_last_sentences_in_one_line():
    """REQ-101: el encabezado va en una línea y, si es largo, queda con las últimas oraciones,
    que son las que desembocan en la lista."""
    intro = " ".join(f"Oración de contexto número {n} del punto." for n in range(40))
    parent = segment("sec-ii/5.2", f"5.2. {intro}\nLa oferta deberá incluir:", "clausula")
    item = segment("sec-ii/5.2/inc-a", "a) copia del acta.")

    heading = heading_of(item, lookup_of(parent, item))

    assert "\n" not in heading
    assert len(heading) <= sentences.HEADING_MAX_CHARS
    assert heading.endswith("La oferta deberá incluir:")
