"""Selección por categoría, cambios por relación, espacio del contexto y orden de entrega
(T-033; plan 001, "Reordenamiento", pasos 4 a 7, y "Conteo de tokens").

`retrieval.select_units(resultado, prompt_tokens)` recibe el resultado de `retrieve` y
cuántos tokens ocupan las instrucciones con la pregunta, y devuelve lo que necesita
`answering.answer`: las unidades en el orden de entrega, los tramos de las unidades
largas, las unidades agregadas por relación y lo que quedó afuera por espacio.

Con los dobles de `tests/conftest.py`: el reranker puntúa por marcas en el texto del
pasaje y el de generación cuenta un token por palabra. Los textos son sintéticos (P4).
"""

import json
from datetime import date

import pytest

from evaluon.queries import answering, retrieval
from tests.conftest import count_words

QUESTION = "¿Qué garantía sintética corresponde?"
DATE = date(2024, 5, 20)
PROMPT_TOKENS = 1000


@pytest.fixture(autouse=True)
def generation_double(fake_generation):
    """La selección cuenta tokens con `generation.count_tokens`: siempre con el doble,
    que cuenta un token por palabra."""
    return fake_generation


@pytest.fixture
def norm_units(make_norm, make_document, make_reading):
    """`norm_units(categoría, [(clave, texto), …], **campos de la lectura)`: una norma
    validada de esa categoría con esas unidades, cada unidad base con un pasaje. Devuelve
    las unidades por clave."""

    def _make(category, units, **fields):
        reading = make_reading(make_document(make_norm(category=category)), units,
                               **fields)
        return reading.units_by_key

    return _make


def scored(fake_reranker, **marks):
    """Puntajes del reranker por marca: `scored(fake_reranker, m1=0.9)` puntúa 0,9 todo
    pasaje que contenga `[m1]`."""
    fake_reranker.scores.update({f"[{mark}]": score for mark, score in marks.items()})


def select(prompt_tokens=PROMPT_TOKENS, reference_date=DATE, **options):
    result = retrieval.retrieve(QUESTION, reference_date, **options)
    return retrieval.select_units(result, prompt_tokens)


def tokens_of(unit, spans=None):
    """Tokens del texto de la unidad que ve el modelo (sin encabezado)."""
    return count_words(answering.prompt_text(unit, spans))


def block_tokens(unit, spans=None):
    """Tokens del bloque de la unidad en el pedido: encabezado más texto. Con el doble,
    que cuenta palabras, el ancho del alias no cambia la cuenta."""
    return count_words(answering.unit_block("[U9]", unit, spans))


def base_tokens(reference_date=DATE):
    """Lo que cuenta quien llama (T-040): instrucciones y comienzo del mensaje."""
    return (count_words(answering.load_instructions())
            + count_words(answering.request_head(QUESTION, reference_date)))


def request_tokens(selection, reference_date=DATE):
    """Tokens del pedido real que arma `answer` con la selección, contados por el doble
    (como `prompt_tokens` del motor doble)."""
    answer = answering.answer(QUESTION, selection.unit_ids, reference_date,
                              passages=selection.passages)
    assert answer.error is None
    return sum(count_words(m["content"]) for m in answer.request["messages"])


def assert_counts_the_request(selection, reference_date=DATE):
    """La cuenta de la selección cubre el pedido real: `prompt_tokens` + `used_tokens`
    no es menor que lo que arma `answer`. Con el doble, que cuenta palabras y es aditivo,
    además es igual: no se cuenta lo que no se muestra."""
    real = request_tokens(selection, reference_date)
    assert selection.prompt_tokens + selection.used_tokens >= real
    assert selection.prompt_tokens + selection.used_tokens == real


# --- Cupos por categoría ---------------------------------------------------------------


@pytest.mark.django_db
def test_national_framework_enters_despite_five_specific_units(norm_units, fake_embeddings,
                                                               fake_reranker):
    """REQ-019: con cinco unidades pertinentes del régimen específico y una del marco
    nacional, puntuada por debajo de las cinco, la del marco nacional entra: el régimen
    específico tiene un cupo de 3 y no la desplaza. Las dos del régimen específico que no
    entran por cupo quedan anotadas."""
    specific = norm_units("regimen_especifico", [
        (f"art-{n}", f"ARTICULO {n}.- Garantía específica [e{n}].") for n in range(1, 6)
    ])
    framework = norm_units("marco_nacional", [
        ("art-30", "ARTICULO 30.- Garantía del marco [n1]."),
    ])
    scored(fake_reranker, e1=0.95, e2=0.94, e3=0.93, e4=0.92, e5=0.91, n1=0.6)

    selection = select()

    assert selection.unit_ids == [specific["art-1"].pk, specific["art-2"].pk,
                                  specific["art-3"].pk, framework["art-30"].pk]
    assert selection.over_quota == [specific["art-4"].pk, specific["art-5"].pk]
    assert selection.left_out == []


@pytest.mark.django_db
def test_considerandos_have_their_own_quota(norm_units, fake_embeddings, fake_reranker):
    """REQ-018: los considerandos no ocupan el cupo de su categoría: tienen uno propio de
    hasta 2. Tres considerandos mejor puntuados no desplazan a tres artículos, y el
    tercero queda afuera por cupo."""
    units = norm_units("regimen_especifico", [
        ("considerando-1", "Que la garantía [c1]."),
        ("considerando-2", "Que la garantía [c2]."),
        ("considerando-3", "Que la garantía [c3]."),
        ("art-1", "ARTICULO 1.- Garantía [a1]."),
        ("art-2", "ARTICULO 2.- Garantía [a2]."),
        ("art-3", "ARTICULO 3.- Garantía [a3]."),
    ])
    scored(fake_reranker, c1=0.99, c2=0.98, c3=0.97, a1=0.7, a2=0.6, a3=0.55)

    selection = select()

    assert selection.unit_ids == [units[k].pk for k in (
        "art-1", "art-2", "art-3", "considerando-1", "considerando-2")]
    assert selection.over_quota == [units["considerando-3"].pk]


@pytest.mark.django_db
def test_below_threshold_units_are_not_selected(norm_units, fake_embeddings,
                                                fake_reranker, settings):
    """REQ-018: la selección parte de las unidades que alcanzaron el umbral; las que no lo
    alcanzan no entran aunque sobre cupo."""
    settings.RERANK_THRESHOLD = 0.368  # el umbral que supone el test, no el calibrado
    units = norm_units("regimen_especifico", [
        ("art-1", "ARTICULO 1.- Garantía [a1]."),
        ("art-2", "ARTICULO 2.- Garantía [a2]."),
    ])
    scored(fake_reranker, a1=0.8, a2=0.3)

    assert select().unit_ids == [units["art-1"].pk]


@pytest.mark.django_db
def test_nothing_pertinent_gives_an_empty_selection(norm_units, fake_embeddings,
                                                    fake_reranker):
    """REQ-018: si nada alcanza el umbral, la selección está vacía y no cuenta tokens (la
    abstención `below_threshold` la resuelve quien llama)."""
    norm_units("regimen_especifico", [("art-1", "ARTICULO 1.- Garantía.")])

    selection = select()

    assert selection.unit_ids == [] and selection.passages == {}
    assert selection.added == [] and selection.left_out == []
    assert selection.tokens == {}


# --- Orden de entrega --------------------------------------------------------------------


@pytest.mark.django_db
def test_article_then_opinion_then_considerando(norm_units, fake_embeddings,
                                                fake_reranker):
    """REQ-018: un artículo del régimen específico y un dictamen legal salen en ese orden
    aunque el dictamen tenga mejor puntaje, y un considerando, el mejor puntuado, va al
    final."""
    specific = norm_units("regimen_especifico", [
        ("considerando-1", "Que la garantía [c1]."),
        ("art-1", "ARTICULO 1.- Garantía [a1]."),
    ])
    opinion = norm_units("dictamen_legal", [("punto-1", "1. La garantía [d1].")])
    scored(fake_reranker, c1=0.99, d1=0.9, a1=0.6)

    selection = select()

    assert selection.unit_ids == [specific["art-1"].pk, opinion["punto-1"].pk,
                                  specific["considerando-1"].pk]


@pytest.mark.django_db
def test_order_of_the_five_categories_and_by_score_within(norm_units, fake_embeddings,
                                                          fake_reranker):
    """REQ-018: el orden lo fija el código: régimen específico, otra normativa aplicable,
    marco nacional, dictamen legal, recomendación de auditoría; dentro de cada categoría,
    de mayor a menor puntaje."""
    audit = norm_units("recomendacion_auditoria", [("punto-1", "1. Garantía [r1].")])
    opinion = norm_units("dictamen_legal", [("punto-1", "1. Garantía [d1].")])
    framework = norm_units("marco_nacional", [("art-1", "ARTICULO 1.- Garantía [n1].")])
    other = norm_units("otra_normativa", [("art-1", "ARTICULO 1.- Garantía [o1].")])
    specific = norm_units("regimen_especifico", [
        ("art-1", "ARTICULO 1.- Garantía [e1]."),
        ("art-2", "ARTICULO 2.- Garantía [e2]."),
    ])
    scored(fake_reranker, r1=0.99, d1=0.98, n1=0.97, o1=0.96, e1=0.6, e2=0.7)

    selection = select()

    assert selection.unit_ids == [
        specific["art-2"].pk, specific["art-1"].pk, other["art-1"].pk,
        framework["art-1"].pk, opinion["punto-1"].pk, audit["punto-1"].pk,
    ]


@pytest.mark.django_db
def test_without_reranker_quotas_use_the_union_order(norm_units, fake_embeddings,
                                                     fake_reranker):
    """REQ-018, REQ-019: sin reranker no hay puntajes: todas las unidades de la unión
    pasan, los cupos se llenan en el orden de la unión (por palabras, en el orden de
    `ts_rank`) y el orden de entrega sigue siendo por categoría."""
    specific = norm_units("regimen_especifico", [
        (f"art-{n}", f"ARTICULO {n}.- " + "garantía " * (6 - n) + "otra.")
        for n in range(1, 6)
    ])
    framework = norm_units("marco_nacional", [("art-9", "ARTICULO 9.- Una garantía.")])

    selection = select(paths=(retrieval.WORDS,), rerank=False)

    assert fake_reranker.calls == []
    assert selection.unit_ids == [specific["art-1"].pk, specific["art-2"].pk,
                                  specific["art-3"].pk, framework["art-9"].pk]
    assert selection.over_quota == [specific["art-4"].pk, specific["art-5"].pk]


# --- Cambios por relación ----------------------------------------------------------------


@pytest.fixture
def modified_article(norm_units, make_relation):
    """Un artículo del régimen específico (`art-3`, pertinente) modificado desde el
    2023-01-01 por el `art-1` de otra norma, que no es pertinente para la pregunta."""
    target = norm_units("regimen_especifico", [
        ("art-3", "ARTICULO 3.- Garantía original [a3]."),
    ])
    source = norm_units("otra_normativa", [
        ("art-1", "ARTICULO 1.- Sustitúyese el texto del artículo 3 por otro."),
    ])
    make_relation(
        source["art-1"].reading.document.norm, target["art-3"].reading.document.norm,
        "modifica", effective_date=date(2023, 1, 1), source_unit_key="art-1",
        target_unit_key="art-3",
    )
    return target["art-3"], source["art-1"]


LONG = ("ARTICULO 7.- Primera parte sobre la garantía [p1]. "
        "Segunda parte sobre plazos sintéticos [p2]. "
        "Tercera parte sobre otra cosa [p3].")


def split_passages(make_passage, unit):
    """Tres pasajes de `unit`, uno por oración, con sus tramos relativos al texto."""
    text = unit.text
    spans = []
    start = 0
    for order, mark in enumerate(("[p1].", "[p2].", "[p3]."), start=1):
        end = text.index(mark) + len(mark)
        make_passage(unit, order=order, char_start=start, char_end=end,
                     text=text[start:end])
        spans.append((start, end))
        start = end + 1
    return spans


@pytest.mark.django_db
def test_modified_article_comes_with_its_modifier_after_the_date(
        modified_article, fake_embeddings, fake_reranker):
    """REQ-007: un artículo modificado a la fecha llega acompañado por la unidad que lo
    modifica, sumada por relación y no por parecido (no alcanzó el umbral); antes de la
    fecha del cambio llega solo. La unidad que modifica y la línea del cambio cuentan en
    el espacio, igual que en el pedido."""
    article, modifier = modified_article
    scored(fake_reranker, a3=0.9)
    after_date, before_date = date(2024, 5, 20), date(2022, 5, 20)

    after = select(prompt_tokens=base_tokens(after_date), reference_date=after_date)
    before = select(prompt_tokens=base_tokens(before_date), reference_date=before_date)

    assert after.unit_ids == [article.pk]
    assert after.added == [{"unit": modifier.pk, "modifies": [article.pk]}]
    assert set(after.tokens) == {article.pk, modifier.pk}
    assert after.tokens[modifier.pk] > block_tokens(modifier)
    assert_counts_the_request(after, after_date)
    assert before.unit_ids == [article.pk]
    assert before.added == []
    assert set(before.tokens) == {article.pk}
    assert_counts_the_request(before, before_date)


@pytest.mark.django_db
def test_selected_modifier_is_not_added_twice(modified_article, fake_embeddings,
                                              fake_reranker):
    """REQ-007: si la unidad que modifica ya está entre las seleccionadas, no se agrega
    otra vez ni se cuenta dos veces: va una vez, anidada como cambio."""
    article, modifier = modified_article
    scored(fake_reranker, a3=0.9)
    fake_reranker.scores["Sustitúyese"] = 0.8

    selection = select(prompt_tokens=base_tokens())

    assert selection.unit_ids == [article.pk, modifier.pk]
    assert selection.added == []
    assert set(selection.tokens) == {article.pk, modifier.pk}
    assert_counts_the_request(selection)


@pytest.mark.django_db
def test_change_from_a_whole_norm_is_counted_and_adds_nothing(
        norm_units, make_relation, fake_embeddings, fake_reranker):
    """REQ-007: un cambio registrado desde una norma entera no trae una unidad
    (`source_unit_id` vacío): no se agrega nada, y la línea "Cambio: …" que el pedido
    muestra igual se cuenta."""
    target = norm_units("regimen_especifico", [("art-3", "ARTICULO 3.- Garantía [a3].")])
    source = norm_units("otra_normativa", [("art-1", "ARTICULO 1.- Cambio entero.")])
    make_relation(source["art-1"].reading.document.norm,
                  target["art-3"].reading.document.norm, "modifica",
                  effective_date=date(2023, 1, 1), target_unit_key="art-3")
    scored(fake_reranker, a3=0.9)

    selection = select(prompt_tokens=base_tokens())

    assert selection.unit_ids == [target["art-3"].pk]
    assert selection.added == [] and selection.passages == {}
    assert set(selection.tokens) == {target["art-3"].pk}
    assert selection.used_tokens > block_tokens(target["art-3"])
    assert_counts_the_request(selection)


@pytest.mark.django_db
def test_self_reference_is_counted_once(norm_units, make_relation, fake_embeddings,
                                        fake_reranker):
    """REQ-007: una relación registrada de una unidad sobre sí misma no la agrega otra
    vez ni la cuenta dos veces; se cuenta la línea "Su texto está más arriba" que muestra
    el pedido."""
    units = norm_units("regimen_especifico", [("art-3", "ARTICULO 3.- Garantía [a3].")])
    norm = units["art-3"].reading.document.norm
    make_relation(norm, norm, "modifica", effective_date=date(2023, 1, 1),
                  source_unit_key="art-3", target_unit_key="art-3")
    scored(fake_reranker, a3=0.9)

    selection = select(prompt_tokens=base_tokens())

    assert selection.unit_ids == [units["art-3"].pk]
    assert selection.added == []
    assert selection.tokens == {units["art-3"].pk: block_tokens(units["art-3"])}
    assert_counts_the_request(selection)


# --- Cadenas: los cambios se siguen a un solo nivel --------------------------------------


@pytest.fixture
def make_chain(norm_units, make_passage, make_relation):
    """`make_chain(categoría de A, categoría de B)`: cadena C → B → A desde el
    2023-01-01: `B` modifica a `A` y `C` (otra normativa, larga, en tres pasajes)
    modifica a `B`. Devuelve `(A, B, C, tramos de C)`."""

    def _make(a_category, b_category):
        a = norm_units(a_category, [("art-1", "ARTICULO 1.- Garantía A [a1].")])
        b = norm_units(b_category, [("art-2", "ARTICULO 2.- Cambia A [b2].")])
        c = norm_units("otra_normativa", [("art-7", LONG)], passages=False)
        spans = split_passages(make_passage, c["art-7"])
        for source, target, source_key, target_key in ((b, a, "art-2", "art-1"),
                                                       (c, b, "art-7", "art-2")):
            make_relation(next(iter(source.values())).reading.document.norm,
                          next(iter(target.values())).reading.document.norm,
                          "modifica", effective_date=date(2023, 1, 1),
                          source_unit_key=source_key, target_unit_key=target_key)
        return a["art-1"], b["art-2"], c["art-7"], spans

    return _make


@pytest.fixture
def chain(make_chain):
    """Cadena C → B → A con A del régimen específico y B del marco nacional."""
    return make_chain("regimen_especifico", "marco_nacional")


@pytest.mark.django_db
def test_chain_nested_modifier_ordered_first_is_not_shown_on_its_own(
        make_chain, fake_embeddings, fake_reranker):
    """REQ-007 (ajuste B2): en la cadena C → B → A, B es del régimen específico y A del
    marco nacional, así que B va antes en el orden. Igual que en `answering`, B se
    muestra anidada bajo A y no por su cuenta, y por eso C no se muestra ni se cuenta."""
    a, b, c, _ = make_chain("marco_nacional", "regimen_especifico")
    scored(fake_reranker, a1=0.8, b2=0.9)

    selection = select(prompt_tokens=base_tokens())

    assert selection.unit_ids == [b.pk, a.pk]
    assert selection.added == []
    assert set(selection.tokens) == {a.pk, b.pk}
    assert_counts_the_request(selection)


@pytest.mark.django_db
def test_chain_follows_changes_one_level(chain, fake_embeddings, fake_reranker):
    """REQ-007 (ajuste B2): con A y B seleccionadas y B mostrada anidada como la que
    modifica a A, la que modifica a B (C) no se muestra: no se cuenta, no se agrega y no
    tiene tramos. El pedido llega a `answer` sin error y la cuenta coincide con él."""
    a, b, c, _ = chain
    scored(fake_reranker, a1=0.9, b2=0.8)

    selection = select(prompt_tokens=base_tokens())

    assert selection.unit_ids == [a.pk, b.pk]
    assert selection.added == []
    assert set(selection.tokens) == {a.pk, b.pk}
    assert c.pk not in selection.passages
    assert_counts_the_request(selection)
    answer = answering.answer(QUESTION, selection.unit_ids, DATE,
                              passages=selection.passages)
    assert set(answer.aliases.values()) == {a.pk, b.pk}


@pytest.mark.django_db
def test_chain_with_long_over_quota_modifier_has_no_spans_for_it(
        settings, chain, norm_units, fake_embeddings, fake_reranker):
    """REQ-007 (ajuste B2): en la cadena C → B → A, C es larga, uno de sus pasajes supera
    el umbral y queda afuera de su cupo. Como B va anidada bajo A, C no se muestra:
    `passages` no la trae (antes `answer` fallaba con "Hay tramos para unidades que no se
    muestran"), y `added` y `tokens` coinciden con lo que se muestra."""
    settings.UNIT_BY_PASSAGES_FROM_TOKENS = 10
    settings.SELECTION_UNITS_PER_CATEGORY = 1
    a, b, c, _ = chain
    other = norm_units("otra_normativa", [("art-9", "ARTICULO 9.- Otra [o9].")])
    scored(fake_reranker, a1=0.9, b2=0.85, o9=0.95, p2=0.8)

    selection = select(prompt_tokens=base_tokens())

    assert selection.over_quota == [c.pk]
    assert selection.unit_ids == [a.pk, other["art-9"].pk, b.pk]
    assert selection.passages == {}
    assert selection.added == []
    assert set(selection.tokens) == {a.pk, b.pk, other["art-9"].pk}
    assert_counts_the_request(selection)


@pytest.mark.django_db
def test_chain_head_not_selected_shows_the_next_level(chain, fake_embeddings,
                                                      fake_reranker):
    """REQ-007: si solo B está seleccionada, B no va anidada y se muestra con la que la
    modifica (C), que entra por relación y se cuenta entera."""
    _, b, c, _ = chain
    scored(fake_reranker, b2=0.8)

    selection = select(prompt_tokens=base_tokens())

    assert selection.unit_ids == [b.pk]
    assert selection.added == [{"unit": c.pk, "modifies": [b.pk]}]
    assert_counts_the_request(selection)


# --- Espacio del contexto ----------------------------------------------------------------


def space_for(settings, words, prompt_tokens=PROMPT_TOKENS):
    """Deja `words` tokens de espacio para unidades con `prompt_tokens` de instrucciones
    y pregunta, sin máximo de salida ni margen."""
    settings.GENERATION_MAX_OUTPUT_TOKENS = 0
    settings.PROMPT_TEMPLATE_MARGIN_TOKENS = 0
    settings.GENERATION_CONTEXT_TOKENS = prompt_tokens + words


TEN_WORDS = "ARTICULO {n}.- uno dos tres cuatro cinco seis siete [{mark}]."


@pytest.mark.django_db
def test_space_is_the_context_minus_prompt_output_and_margin(settings, norm_units,
                                                             fake_embeddings,
                                                             fake_reranker):
    """REQ-018: el espacio para unidades es el contexto menos los tokens de las
    instrucciones con la pregunta (los recibe la selección), menos el máximo de salida,
    menos el margen de la plantilla; los tres salen de `settings.py`. Lo usado es el
    bloque de la unidad, con su encabezado."""
    settings.GENERATION_CONTEXT_TOKENS = 16384
    settings.GENERATION_MAX_OUTPUT_TOKENS = 800
    settings.PROMPT_TEMPLATE_MARGIN_TOKENS = 512
    units = norm_units("regimen_especifico", [("art-1", TEN_WORDS.format(n=1, mark="a1"))])
    scored(fake_reranker, a1=0.9)

    selection = select(prompt_tokens=1234)

    assert selection.available_tokens == 16384 - 1234 - 800 - 512
    assert selection.used_tokens == block_tokens(units["art-1"])
    assert selection.used_tokens > tokens_of(units["art-1"])
    assert selection.anomalies == []


@pytest.mark.django_db
def test_prompt_longer_than_the_context_leaves_no_space(settings, norm_units,
                                                        fake_embeddings, fake_reranker):
    """REQ-018: si las instrucciones con la pregunta ya no entran en el contexto, el
    espacio queda en 0, no negativo, con la anomalía `prompt_exceeds_context` y cuántos
    tokens faltan; ninguna unidad entra."""
    settings.GENERATION_CONTEXT_TOKENS = 1000
    settings.GENERATION_MAX_OUTPUT_TOKENS = 100
    settings.PROMPT_TEMPLATE_MARGIN_TOKENS = 50
    units = norm_units("regimen_especifico", [("art-1", TEN_WORDS.format(n=1, mark="a1"))])
    scored(fake_reranker, a1=0.9)

    selection = select(prompt_tokens=1200)

    assert selection.available_tokens == 0
    assert selection.anomalies == [{"type": "prompt_exceeds_context",
                                    "prompt_tokens": 1200, "missing_tokens": 350}]
    assert selection.unit_ids == []
    assert selection.left_out == [{"unit": units["art-1"].pk,
                                   "tokens": block_tokens(units["art-1"])}]
    assert selection.as_record()["anomalies"] == selection.anomalies


@pytest.mark.django_db
def test_no_unit_fits_gives_empty_unit_ids(settings, norm_units, fake_embeddings,
                                           fake_reranker):
    """REQ-018: si ninguna unidad cabe en el espacio, `unit_ids` queda vacío y todas
    quedan anotadas en `left_out`; no hay tramos ni tokens usados."""
    space_for(settings, 5)
    units = norm_units("regimen_especifico", [
        ("art-1", TEN_WORDS.format(n=1, mark="a1")),
        ("art-2", TEN_WORDS.format(n=2, mark="a2")),
    ])
    scored(fake_reranker, a1=0.9, a2=0.8)

    selection = select()

    assert selection.unit_ids == [] and selection.passages == {}
    assert [entry["unit"] for entry in selection.left_out] == [units["art-1"].pk,
                                                                units["art-2"].pk]
    assert selection.used_tokens == 0 and selection.tokens == {}


@pytest.mark.django_db
def test_without_space_best_of_each_category_first(settings, norm_units, fake_embeddings,
                                                   fake_reranker):
    """REQ-018, REQ-019: si el total no entra, entra primero la mejor unidad de cada
    categoría y después la segunda: con lugar justo para tres bloques, entran la mejor
    del régimen específico, la del marco nacional y la del dictamen, y la segunda del
    régimen específico queda afuera, anotada con sus tokens."""
    specific = norm_units("regimen_especifico", [
        ("art-1", TEN_WORDS.format(n=1, mark="e1")),
        ("art-2", TEN_WORDS.format(n=2, mark="e2")),
    ])
    framework = norm_units("marco_nacional", [("art-1", TEN_WORDS.format(n=1, mark="n1"))])
    opinion = norm_units("dictamen_legal", [("punto-1", TEN_WORDS.format(n=1, mark="d1"))])
    fits = [specific["art-1"], framework["art-1"], opinion["punto-1"]]
    space_for(settings, sum(block_tokens(unit) for unit in fits))
    scored(fake_reranker, e1=0.95, e2=0.94, n1=0.6, d1=0.55)

    selection = select()

    assert selection.unit_ids == [unit.pk for unit in fits]
    assert selection.left_out == [{"unit": specific["art-2"].pk,
                                   "tokens": block_tokens(specific["art-2"])}]
    assert selection.used_tokens == selection.available_tokens


@pytest.mark.django_db
def test_without_space_considerando_does_not_displace_an_article(
        settings, norm_units, fake_embeddings, fake_reranker):
    """REQ-018: sin espacio para todo, un considerando entra después de los artículos
    aunque tenga mejor puntaje: un fundamento no desplaza a un artículo. Su costo incluye
    el rótulo del bloque de considerandos."""
    units = norm_units("regimen_especifico", [
        ("considerando-1", TEN_WORDS.format(n=1, mark="c1")),
        ("art-1", TEN_WORDS.format(n=1, mark="a1")),
        ("art-2", TEN_WORDS.format(n=2, mark="a2")),
    ])
    space_for(settings, block_tokens(units["art-1"]) + block_tokens(units["art-2"]))
    scored(fake_reranker, c1=0.99, a1=0.7, a2=0.6)

    selection = select()

    assert selection.unit_ids == [units["art-1"].pk, units["art-2"].pk]
    heading = count_words(answering.CONSIDERANDOS_HEADING)
    assert selection.left_out == [{"unit": units["considerando-1"].pk,
                                   "tokens": block_tokens(units["considerando-1"])
                                   + heading}]


@pytest.mark.django_db
def test_without_space_a_unit_enters_with_its_modifier(settings, modified_article,
                                                       norm_units, fake_embeddings,
                                                       fake_reranker):
    """REQ-007: una unidad modificada entra al espacio junto con la que la modifica, o no
    entra: con lugar para todo menos un token, queda afuera con el costo de las dos, y
    entra en su lugar otra que sí cabe."""
    article, _ = modified_article
    scored(fake_reranker, a3=0.9)
    package = select().used_tokens
    other = norm_units("marco_nacional", [("art-1", "ARTICULO 1.- Corta [n1].")])
    space_for(settings, package - 1)
    scored(fake_reranker, n1=0.6)

    selection = select()

    assert package > block_tokens(article)
    assert selection.unit_ids == [other["art-1"].pk]
    assert selection.added == []
    assert selection.left_out == [{"unit": article.pk, "tokens": package}]


@pytest.mark.django_db
def test_count_covers_the_request_with_fifteen_units_and_two_changes(
        norm_units, make_relation, fake_embeddings, fake_reranker):
    """REQ-007, REQ-018, REQ-019 (ajuste B1): con 15 unidades seleccionadas (tres por
    categoría) y dos cambios, `prompt_tokens` + `used_tokens` no es menor que los tokens
    del pedido real que arma `answer`, contados con el mismo doble: se cuentan los
    encabezados de cada unidad, los bloques y líneas de los cambios y los separadores."""
    scores = {}
    by_category = {}
    for position, category in enumerate(answering.CATEGORY_ORDER):
        units = norm_units(category, [
            (f"art-{n}", f"ARTICULO {n}.- Texto sintético {category} [k{position}{n}].")
            for n in range(1, 4)
        ])
        by_category[category] = units
        scores.update({f"k{position}{n}": 0.9 - 0.01 * n for n in range(1, 4)})
    amending = norm_units("otra_normativa", [
        ("art-1", "ARTICULO 1.- Sustitúyese un artículo sintético."),
        ("art-2", "ARTICULO 2.- Sustitúyese otro artículo sintético."),
    ])
    for source_key, category in (("art-1", "regimen_especifico"),
                                 ("art-2", "marco_nacional")):
        make_relation(amending["art-1"].reading.document.norm,
                      by_category[category]["art-1"].reading.document.norm, "modifica",
                      effective_date=date(2023, 1, 1), source_unit_key=source_key,
                      target_unit_key="art-1")
    scored(fake_reranker, **scores)

    selection = select(prompt_tokens=base_tokens())

    assert len(selection.unit_ids) == 15
    assert [a["unit"] for a in selection.added] == [amending["art-1"].pk,
                                                    amending["art-2"].pk]
    assert_counts_the_request(selection)


# --- Unidades largas ---------------------------------------------------------------------


@pytest.mark.django_db
def test_long_unit_shows_only_passages_over_threshold(settings, norm_units, make_passage,
                                                      fake_embeddings, fake_reranker,
                                                      fake_generation):
    """REQ-007, REQ-018: de una unidad más larga que `UNIT_BY_PASSAGES_FROM_TOKENS` se
    le muestran al modelo solo los pasajes que superaron el umbral; su bloque se cuenta
    con esos tramos. La unidad corta va entera."""
    settings.UNIT_BY_PASSAGES_FROM_TOKENS = 10
    units = norm_units("regimen_especifico", [
        ("art-7", LONG), ("art-8", "ARTICULO 8.- Corta [a8]."),
    ], passages=False)
    long_unit = units["art-7"]
    spans = split_passages(make_passage, long_unit)
    make_passage(units["art-8"])
    scored(fake_reranker, p1=0.9, p3=0.7, a8=0.8)

    selection = select(prompt_tokens=base_tokens())

    assert selection.passages == {long_unit.pk: [spans[0], spans[2]]}
    assert selection.tokens[long_unit.pk] == block_tokens(long_unit,
                                                          [spans[0], spans[2]])
    assert selection.tokens[long_unit.pk] < block_tokens(long_unit)
    assert selection.tokens[units["art-8"].pk] == block_tokens(units["art-8"])
    assert_counts_the_request(selection)

    user = next(m["content"] for m in fake_generation.calls[-1][0] if m["role"] == "user")
    assert "Primera parte" in user and "Tercera parte" in user
    assert "Segunda parte" not in user
    assert answering.OMITTED_MARK in user


@pytest.mark.django_db
def test_unit_at_the_limit_goes_whole(settings, norm_units, make_passage,
                                      fake_embeddings, fake_reranker):
    """REQ-007: una unidad que no supera `UNIT_BY_PASSAGES_FROM_TOKENS` (contados sobre
    su texto) se muestra entera aunque solo uno de sus pasajes haya superado el umbral."""
    units = norm_units("regimen_especifico", [("art-7", LONG)], passages=False)
    settings.UNIT_BY_PASSAGES_FROM_TOKENS = tokens_of(units["art-7"])
    split_passages(make_passage, units["art-7"])
    scored(fake_reranker, p1=0.9)

    selection = select()

    assert selection.passages == {}
    assert selection.tokens[units["art-7"].pk] == block_tokens(units["art-7"])


@pytest.mark.django_db
def test_long_unit_without_reranker_shows_its_retrieved_passages(
        settings, norm_units, make_passage, fake_embeddings, fake_reranker):
    """REQ-007: sin reranker no hay umbral: de una unidad larga se muestran los pasajes
    con que entró a la unión."""
    settings.UNIT_BY_PASSAGES_FROM_TOKENS = 10
    units = norm_units("regimen_especifico", [("art-7", LONG)], passages=False)
    spans = split_passages(make_passage, units["art-7"])

    result = retrieval.retrieve("plazos", DATE, paths=(retrieval.WORDS,), rerank=False)
    selection = retrieval.select_units(result, PROMPT_TOKENS)

    assert selection.passages == {units["art-7"].pk: [spans[1]]}


@pytest.mark.django_db
def test_without_semantic_path_and_with_reranker(norm_units, fake_embeddings,
                                                 fake_reranker):
    """REQ-018: con el camino por significado apagado y el reranker prendido, la
    selección trabaja con los puntajes del reranker sobre lo que trajeron las palabras y
    la referencia, aunque ningún candidato tenga distancia."""
    units = norm_units("regimen_especifico", [
        ("art-1", "ARTICULO 1.- La garantía sintética [a1]."),
        ("art-2", "ARTICULO 2.- Otra garantía sintética [a2]."),
        ("art-3", "ARTICULO 3.- Sin relación [a3]."),
    ])
    scored(fake_reranker, a1=0.6, a2=0.9, a3=0.95)

    result = retrieval.retrieve(QUESTION, DATE, paths=(retrieval.WORDS,
                                                       retrieval.REFERENCE))
    selection = retrieval.select_units(result, base_tokens())

    assert fake_embeddings.calls == []
    assert all(c.distance is None for c in result.candidates)
    assert selection.unit_ids == [units["art-2"].pk, units["art-1"].pk]
    assert_counts_the_request(selection)


@pytest.fixture
def long_modifier(norm_units, make_passage, make_relation):
    """Un artículo corto del régimen específico (`art-3`) modificado desde el 2023-01-01
    por un artículo largo de otra norma, partido en tres pasajes."""
    target = norm_units("regimen_especifico", [
        ("art-3", "ARTICULO 3.- Garantía original [a3]."),
    ])
    source = norm_units("otra_normativa", [("art-7", LONG)], passages=False)
    spans = split_passages(make_passage, source["art-7"])
    relation = make_relation(
        source["art-7"].reading.document.norm, target["art-3"].reading.document.norm,
        "modifica", effective_date=date(2023, 1, 1), source_unit_key="art-7",
        target_unit_key="art-3",
    )
    assert relation.pk
    return target["art-3"], source["art-7"], spans


@pytest.mark.django_db
def test_long_modifier_shows_its_passages_over_threshold(settings, long_modifier,
                                                         norm_units, fake_embeddings,
                                                         fake_reranker, fake_generation):
    """REQ-007 (aviso de T-034): de una unidad que modifica a otra y es más larga que
    `UNIT_BY_PASSAGES_FROM_TOKENS` se muestran los pasajes que superaron el umbral, y
    `answer` los acepta para esa unidad, que muestra a continuación de la modificada. La
    unidad que modifica entra por relación aunque haya quedado afuera de su cupo."""
    settings.UNIT_BY_PASSAGES_FROM_TOKENS = 10
    settings.SELECTION_UNITS_PER_CATEGORY = 1
    article, modifier, spans = long_modifier
    other = norm_units("otra_normativa", [("art-9", "ARTICULO 9.- Otra [o9].")])
    scored(fake_reranker, a3=0.9, o9=0.95, p2=0.8)

    selection = select(prompt_tokens=base_tokens())

    assert selection.unit_ids == [article.pk, other["art-9"].pk]
    assert selection.over_quota == [modifier.pk]
    assert selection.added == [{"unit": modifier.pk, "modifies": [article.pk]}]
    assert selection.passages == {modifier.pk: [spans[1]]}
    assert_counts_the_request(selection)
    answer = answering.answer(QUESTION, selection.unit_ids, DATE,
                              passages=selection.passages)
    assert set(answer.aliases.values()) == {article.pk, other["art-9"].pk, modifier.pk}
    user = next(m["content"] for m in fake_generation.calls[-1][0] if m["role"] == "user")
    assert "Segunda parte" in user and "Primera parte" not in user


@pytest.mark.django_db
def test_long_modifier_without_passages_over_threshold_goes_whole(
        settings, long_modifier, fake_embeddings, fake_reranker):
    """REQ-007: una unidad larga que entra solo por relación, sin pasajes que superen el
    umbral, se muestra entera (el cambio se ve completo) y se cuenta entera."""
    settings.UNIT_BY_PASSAGES_FROM_TOKENS = 10
    article, modifier, _ = long_modifier
    scored(fake_reranker, a3=0.9)

    selection = select(prompt_tokens=base_tokens())

    assert selection.added == [{"unit": modifier.pk, "modifies": [article.pk]}]
    assert selection.passages == {}
    assert selection.tokens[modifier.pk] > block_tokens(modifier)
    assert_counts_the_request(selection)


# --- Registro ----------------------------------------------------------------------------


@pytest.mark.django_db
def test_record_is_json_with_parameters(settings, norm_units, fake_embeddings,
                                        fake_reranker):
    """REQ-018 (P6): la selección se guarda como JSON en el registro, con lo enviado, lo
    agregado, lo dejado afuera por cupo y por espacio, los tokens, las anomalías y los
    parámetros."""
    units = norm_units("regimen_especifico", [
        ("art-1", TEN_WORDS.format(n=1, mark="e1")),
        ("art-2", TEN_WORDS.format(n=2, mark="e2")),
    ])
    space_for(settings, block_tokens(units["art-1"]))
    scored(fake_reranker, e1=0.9, e2=0.8)

    record = select().as_record()

    assert json.loads(json.dumps(record)) == record
    assert set(record) == {"units", "passages", "added", "over_quota", "left_out",
                           "tokens", "prompt_tokens", "available_tokens", "used_tokens",
                           "anomalies", "parameters"}
    assert len(record["units"]) == 1 and len(record["left_out"]) == 1
    assert record["parameters"] == {
        "units_per_category": 3, "considerandos": 2,
        "context_tokens": PROMPT_TOKENS + block_tokens(units["art-1"]),
        "max_output_tokens": 0, "template_margin_tokens": 0,
        "unit_by_passages_from_tokens": settings.UNIT_BY_PASSAGES_FROM_TOKENS,
    }
