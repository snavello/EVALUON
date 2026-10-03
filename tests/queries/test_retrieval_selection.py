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
    return count_words(answering.prompt_text(unit, spans))


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
                                                fake_reranker):
    """REQ-018: la selección parte de las unidades que alcanzaron el umbral; las que no lo
    alcanzan no entran aunque sobre cupo."""
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


@pytest.mark.django_db
def test_modified_article_comes_with_its_modifier_after_the_date(
        modified_article, fake_embeddings, fake_reranker):
    """REQ-007: un artículo modificado a la fecha llega acompañado por la unidad que lo
    modifica, sumada por relación y no por parecido (no alcanzó el umbral); antes de la
    fecha del cambio llega solo. La unidad que modifica cuenta en el espacio."""
    article, modifier = modified_article
    scored(fake_reranker, a3=0.9)

    after = select(reference_date=date(2024, 5, 20))
    before = select(reference_date=date(2022, 5, 20))

    assert after.unit_ids == [article.pk]
    assert after.added == [{"unit": modifier.pk, "modifies": [article.pk]}]
    assert set(after.tokens) == {article.pk, modifier.pk}
    assert after.used_tokens == tokens_of(article) + tokens_of(modifier)
    assert before.unit_ids == [article.pk]
    assert before.added == []
    assert set(before.tokens) == {article.pk}


@pytest.mark.django_db
def test_selected_modifier_is_not_added_twice(modified_article, fake_embeddings,
                                              fake_reranker):
    """REQ-007: si la unidad que modifica ya está entre las seleccionadas, no se agrega
    otra vez ni se cuenta dos veces."""
    article, modifier = modified_article
    scored(fake_reranker, a3=0.9)
    fake_reranker.scores["Sustitúyese"] = 0.8

    selection = select()

    assert selection.unit_ids == [article.pk, modifier.pk]
    assert selection.added == []
    assert selection.used_tokens == tokens_of(article) + tokens_of(modifier)


# --- Espacio del contexto ----------------------------------------------------------------


def space_for(settings, words):
    """Deja `words` tokens de espacio para unidades con `PROMPT_TOKENS` de instrucciones y
    pregunta, sin máximo de salida ni margen."""
    settings.GENERATION_MAX_OUTPUT_TOKENS = 0
    settings.PROMPT_TEMPLATE_MARGIN_TOKENS = 0
    settings.GENERATION_CONTEXT_TOKENS = PROMPT_TOKENS + words


TEN_WORDS = "ARTICULO {n}.- uno dos tres cuatro cinco seis siete [{mark}]."


@pytest.mark.django_db
def test_space_is_the_context_minus_prompt_output_and_margin(settings, norm_units,
                                                             fake_embeddings,
                                                             fake_reranker):
    """REQ-018: el espacio para unidades es el contexto menos los tokens de las
    instrucciones con la pregunta (los recibe la selección), menos el máximo de salida,
    menos el margen de la plantilla; los tres salen de `settings.py`."""
    settings.GENERATION_CONTEXT_TOKENS = 16384
    settings.GENERATION_MAX_OUTPUT_TOKENS = 800
    settings.PROMPT_TEMPLATE_MARGIN_TOKENS = 512
    norm_units("regimen_especifico", [("art-1", TEN_WORDS.format(n=1, mark="a1"))])
    scored(fake_reranker, a1=0.9)

    selection = select(prompt_tokens=1234)

    assert selection.available_tokens == 16384 - 1234 - 800 - 512
    assert selection.used_tokens == 10


@pytest.mark.django_db
def test_without_space_best_of_each_category_first(settings, norm_units, fake_embeddings,
                                                   fake_reranker):
    """REQ-018, REQ-019: si el total no entra, entra primero la mejor unidad de cada
    categoría y después la segunda: con lugar para tres unidades de diez tokens, entran
    la mejor del régimen específico, la del marco nacional y la del dictamen, y la
    segunda del régimen específico queda afuera, anotada con sus tokens."""
    space_for(settings, 30)
    specific = norm_units("regimen_especifico", [
        ("art-1", TEN_WORDS.format(n=1, mark="e1")),
        ("art-2", TEN_WORDS.format(n=2, mark="e2")),
    ])
    framework = norm_units("marco_nacional", [("art-1", TEN_WORDS.format(n=1, mark="n1"))])
    opinion = norm_units("dictamen_legal", [("punto-1", TEN_WORDS.format(n=1, mark="d1"))])
    scored(fake_reranker, e1=0.95, e2=0.94, n1=0.6, d1=0.55)

    selection = select()

    assert selection.unit_ids == [specific["art-1"].pk, framework["art-1"].pk,
                                  opinion["punto-1"].pk]
    assert selection.left_out == [{"unit": specific["art-2"].pk, "tokens": 10}]
    assert selection.used_tokens == 30


@pytest.mark.django_db
def test_without_space_considerando_does_not_displace_an_article(
        settings, norm_units, fake_embeddings, fake_reranker):
    """REQ-018: sin espacio para todo, un considerando entra después de los artículos
    aunque tenga mejor puntaje: un fundamento no desplaza a un artículo."""
    space_for(settings, 20)
    units = norm_units("regimen_especifico", [
        ("considerando-1", TEN_WORDS.format(n=1, mark="c1")),
        ("art-1", TEN_WORDS.format(n=1, mark="a1")),
        ("art-2", TEN_WORDS.format(n=2, mark="a2")),
    ])
    scored(fake_reranker, c1=0.99, a1=0.7, a2=0.6)

    selection = select()

    assert selection.unit_ids == [units["art-1"].pk, units["art-2"].pk]
    assert selection.left_out == [{"unit": units["considerando-1"].pk, "tokens": 10}]


@pytest.mark.django_db
def test_without_space_a_unit_enters_with_its_modifier(settings, modified_article,
                                                       norm_units, fake_embeddings,
                                                       fake_reranker):
    """REQ-007: una unidad modificada entra al espacio junto con la que la modifica, o no
    entra: con lugar solo para la unidad, queda afuera con el costo de las dos, y entra
    en su lugar otra que sí cabe."""
    article, modifier = modified_article
    package = tokens_of(article) + tokens_of(modifier)
    other = norm_units("marco_nacional", [("art-1", "ARTICULO 1.- Corta [n1].")])
    space_for(settings, package - 1)
    scored(fake_reranker, a3=0.9, n1=0.6)

    selection = select()

    assert selection.unit_ids == [other["art-1"].pk]
    assert selection.added == []
    assert selection.left_out == [{"unit": article.pk, "tokens": package}]


# --- Unidades largas ---------------------------------------------------------------------

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
def test_long_unit_shows_only_passages_over_threshold(settings, norm_units, make_passage,
                                                      fake_embeddings, fake_reranker,
                                                      fake_generation):
    """REQ-007, REQ-018: de una unidad más larga que `UNIT_BY_PASSAGES_FROM_TOKENS` se
    le muestran al modelo solo los pasajes que superaron el umbral; sus tokens se cuentan
    sobre `prompt_text` con esos tramos. La unidad corta va entera."""
    settings.UNIT_BY_PASSAGES_FROM_TOKENS = 10
    units = norm_units("regimen_especifico", [
        ("art-7", LONG), ("art-8", "ARTICULO 8.- Corta [a8]."),
    ], passages=False)
    long_unit = units["art-7"]
    spans = split_passages(make_passage, long_unit)
    make_passage(units["art-8"])
    scored(fake_reranker, p1=0.9, p3=0.7, a8=0.8)

    selection = select()

    assert selection.passages == {long_unit.pk: [spans[0], spans[2]]}
    assert selection.tokens[long_unit.pk] == tokens_of(long_unit, [spans[0], spans[2]])
    assert selection.tokens[long_unit.pk] < tokens_of(long_unit)
    assert selection.tokens[units["art-8"].pk] == tokens_of(units["art-8"])

    answering.answer(QUESTION, selection.unit_ids, DATE, passages=selection.passages)
    user = next(m["content"] for m in fake_generation.calls[-1][0] if m["role"] == "user")
    assert "Primera parte" in user and "Tercera parte" in user
    assert "Segunda parte" not in user
    assert answering.OMITTED_MARK in user


@pytest.mark.django_db
def test_unit_at_the_limit_goes_whole(settings, norm_units, make_passage,
                                      fake_embeddings, fake_reranker):
    """REQ-007: una unidad que no supera `UNIT_BY_PASSAGES_FROM_TOKENS` se muestra entera
    aunque solo uno de sus pasajes haya superado el umbral."""
    units = norm_units("regimen_especifico", [("art-7", LONG)], passages=False)
    settings.UNIT_BY_PASSAGES_FROM_TOKENS = tokens_of(units["art-7"])
    split_passages(make_passage, units["art-7"])
    scored(fake_reranker, p1=0.9)

    selection = select()

    assert selection.passages == {}
    assert selection.tokens[units["art-7"].pk] == tokens_of(units["art-7"])


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

    selection = select()

    assert selection.unit_ids == [article.pk, other["art-9"].pk]
    assert selection.over_quota == [modifier.pk]
    assert selection.added == [{"unit": modifier.pk, "modifies": [article.pk]}]
    assert selection.passages == {modifier.pk: [spans[1]]}
    assert selection.tokens[modifier.pk] == tokens_of(modifier, [spans[1]])
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

    selection = select()

    assert selection.added == [{"unit": modifier.pk, "modifies": [article.pk]}]
    assert selection.passages == {}
    assert selection.tokens[modifier.pk] == tokens_of(modifier)


# --- Registro ----------------------------------------------------------------------------


@pytest.mark.django_db
def test_record_is_json_with_parameters(settings, norm_units, fake_embeddings,
                                        fake_reranker):
    """REQ-018 (P6): la selección se guarda como JSON en el registro, con lo enviado, lo
    agregado, lo dejado afuera por cupo y por espacio, los tokens y los parámetros."""
    space_for(settings, 10)
    norm_units("regimen_especifico", [
        ("art-1", TEN_WORDS.format(n=1, mark="e1")),
        ("art-2", TEN_WORDS.format(n=2, mark="e2")),
    ])
    scored(fake_reranker, e1=0.9, e2=0.8)

    record = select().as_record()

    assert json.loads(json.dumps(record)) == record
    assert set(record) == {"units", "passages", "added", "over_quota", "left_out",
                           "tokens", "prompt_tokens", "available_tokens", "used_tokens",
                           "parameters"}
    assert len(record["units"]) == 1 and len(record["left_out"]) == 1
    assert record["parameters"] == {
        "units_per_category": 3, "considerandos": 2, "context_tokens": PROMPT_TOKENS + 10,
        "max_output_tokens": 0, "template_margin_tokens": 0,
        "unit_by_passages_from_tokens": settings.UNIT_BY_PASSAGES_FROM_TOKENS,
    }
