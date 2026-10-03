"""Instrucciones completas, marca de regímenes y orden de la respuesta (T-034; plan 001,
"Generación", "Cita" y "Forma de la respuesta").

- El pedido de `consulta-v2` lleva la fecha de autorización del procedimiento; cada
  unidad con su categoría y su papel, en el orden de categorías fijado por el código; una
  unidad modificada, seguida del texto de la que la modifica con la fecha; y los
  considerandos en un bloque aparte rotulado como contexto.
- El orden de la respuesta lo fija el código, no el modelo: las citas de cada afirmación
  por categoría con los considerandos al final, y las afirmaciones por la categoría de su
  primera cita (REQ-018).
- La marca `regimes_differ` se conserva solo con una cita del régimen específico y otra
  del marco nacional; si no, se apaga y queda la anomalía `regimes_flag_dropped` (REQ-019).
- El resultado trae `changes` por unidad, y las unidades que modifican a una citada.

Con el doble del motor de `tests/conftest.py`; los textos son sintéticos (P4).
"""

import json
from datetime import date

import pytest

from evaluon.queries import answering

QUESTION = "¿Qué garantía sintética corresponde a la oferta?"
DATE = date(2024, 5, 20)


def st(text, *aliases, differ=False):
    """Afirmación tal como la devuelve el modelo con el esquema de `consulta-v2`."""
    return {"text": text, "citations": list(aliases), "regimes_differ": differ}


def ask(unit_ids, reference_date=DATE):
    return answering.answer(QUESTION, unit_ids, reference_date=reference_date)


def user_message(fake_generation):
    [(messages, _)] = fake_generation.calls
    return next(m["content"] for m in messages if m["role"] == "user")


def alias_of(answer, unit):
    return next(alias for alias, pk in answer.aliases.items() if pk == unit.pk)


@pytest.fixture
def corpus(make_norm, make_document, make_reading):
    """Una unidad de cada categoría y un considerando del régimen específico."""

    def unit(category, key, text):
        norm = make_norm(category=category)
        return make_reading(make_document(norm), [(key, text)]).units_by_key[key]

    return {
        "regimen": unit("regimen_especifico", "art-5",
                        "ARTICULO 5.- La garantía sintética de oferta es del cinco por ciento."),
        "otra": unit("otra_normativa", "art-2",
                     "ARTICULO 2.- Otra norma sintética sobre garantías."),
        "marco": unit("marco_nacional", "art-10",
                      "ARTICULO 10.- El marco sintético fija la garantía en el tres por ciento."),
        "dictamen": unit("dictamen_legal", "punto-1",
                         "1. El servicio jurídico sintético interpreta la garantía."),
        "auditoria": unit("recomendacion_auditoria", "parrafo-1",
                          "La auditoría sintética recomienda controlar la garantía."),
        "considerando": unit("regimen_especifico", "considerando-1",
                             "Que es necesario fijar garantías sintéticas."),
    }


def pks(corpus, *names):
    return [corpus[name].pk for name in names]


# --- REQ-018: orden de citas y afirmaciones fijado por el código -----------------------


@pytest.mark.django_db
def test_article_goes_before_dictamen_even_if_model_reverses_them(corpus,
                                                                  fake_generation):
    """REQ-018: dada una pregunta que responden un artículo del régimen específico y un
    dictamen legal, cuando el modelo los cita al revés, entonces la respuesta cita
    primero el artículo y después el dictamen, y cada cita lleva su categoría."""
    answer_ids = pks(corpus, "regimen", "dictamen")
    fake_generation.answer([st("La garantía es del cinco por ciento.", "U2", "U1")])

    answer = ask(answer_ids)

    regimen, dictamen = corpus["regimen"], corpus["dictamen"]
    assert answer.aliases == {"U1": regimen.pk, "U2": dictamen.pk}
    assert answer.result["statements"] == [
        {"text": "La garantía es del cinco por ciento.", "regimes_differ": False,
         "citations": [regimen.pk, dictamen.pk]},
    ]
    units = answer.result["units"]
    assert units[str(regimen.pk)]["category"] == "regimen_especifico"
    assert units[str(dictamen.pk)]["category"] == "dictamen_legal"


@pytest.mark.django_db
def test_citations_follow_category_order_with_considerandos_last(corpus,
                                                                 fake_generation):
    """REQ-018: las citas de una afirmación van en el orden régimen específico, otra
    normativa aplicable, marco nacional, dictamen legal, recomendación de auditoría, y
    los considerandos al final, sin importar el orden en que las devuelve el modelo."""
    names = ["considerando", "auditoria", "dictamen", "marco", "otra", "regimen"]
    # Alias en el orden mostrado (por categoría, considerandos al final).
    fake_generation.answer([st("Afirmación.", "U6", "U5", "U4", "U3", "U2", "U1")])

    answer = ask(pks(corpus, *names))

    assert [alias_of(answer, corpus[name]) for name in reversed(names)] == [
        "U1", "U2", "U3", "U4", "U5", "U6"]
    assert answer.result["statements"][0]["citations"] == pks(
        corpus, "regimen", "otra", "marco", "dictamen", "auditoria", "considerando")


@pytest.mark.django_db
def test_statements_follow_the_category_of_their_first_citation(corpus,
                                                                fake_generation):
    """REQ-018: las afirmaciones se ordenan por la categoría de su primera cita (después
    de ordenar sus citas); a igual categoría conservan el orden del modelo, y una que solo
    cita un considerando va al final."""
    selected = pks(corpus, "regimen", "marco", "dictamen", "considerando")
    # Alias en el orden mostrado: U1 régimen, U2 marco, U3 dictamen, U4 considerando.
    fake_generation.answer([
        st("Contexto.", "U4"),
        st("Criterio.", "U3"),
        st("Marco.", "U2"),
        st("Régimen con criterio.", "U3", "U1"),
        st("Régimen solo.", "U1"),
    ])

    answer = ask(selected)

    assert answer.aliases == {"U1": corpus["regimen"].pk, "U2": corpus["marco"].pk,
                              "U3": corpus["dictamen"].pk,
                              "U4": corpus["considerando"].pk}
    assert [s["text"] for s in answer.result["statements"]] == [
        "Régimen con criterio.", "Régimen solo.", "Marco.", "Criterio.", "Contexto.",
    ]
    assert answer.result["statements"][0]["citations"] == pks(corpus, "regimen",
                                                              "dictamen")


# --- Pedido de consulta-v2 ------------------------------------------------------------


@pytest.mark.django_db
def test_request_carries_date_category_role_and_considerandos_block(corpus,
                                                                    fake_generation):
    """REQ-008, REQ-018: el pedido lleva la fecha de autorización del procedimiento;
    cada unidad con su categoría y su papel, ordenadas por categoría aunque lleguen en
    otro orden; y los considerandos en un bloque aparte, después del articulado, rotulado
    como contexto."""
    selected = pks(corpus, "considerando", "dictamen", "marco", "regimen", "auditoria",
                   "otra")

    answer = ask(selected)

    content = user_message(fake_generation)
    assert "Fecha de autorización del procedimiento: 20/05/2024" in content
    assert QUESTION in content
    expected = [("U1", "regimen", "Régimen específico", "es lo que se aplica"),
                ("U2", "otra", "Otra normativa aplicable", "se aplica en lo que trata"),
                ("U3", "marco", "Marco nacional", "marco de referencia"),
                ("U4", "dictamen", "Dictamen legal", "criterio que acompaña"),
                ("U5", "auditoria", "Recomendación de auditoría",
                 "criterio que acompaña")]
    for alias, name, category, role in expected:
        assert answer.aliases[alias] == corpus[name].pk
        block = content.split(f"[{alias}]", 1)[1].split("\n[U", 1)[0]
        assert f"Categoría: {category}" in block
        assert f"Papel: {role}" in block
        assert answering.unit_text(corpus[name]) in block
    assert answer.aliases["U6"] == corpus["considerando"].pk
    articulado, context = content.split(answering.CONSIDERANDOS_HEADING, 1)
    assert "[U6]" not in articulado
    assert "[U5]" not in context
    considerando = context.split("[U6]", 1)[1]
    assert "Papel: contexto" in considerando
    assert answering.unit_text(corpus["considerando"]) in considerando
    positions = [content.index(f"[U{n}]") for n in range(1, 7)]
    assert positions == sorted(positions)


@pytest.mark.django_db
def test_without_considerandos_there_is_no_context_block(corpus, fake_generation):
    """REQ-018: sin considerandos seleccionados el pedido no trae el bloque de
    contexto."""
    ask(pks(corpus, "regimen"))

    assert answering.CONSIDERANDOS_HEADING not in user_message(fake_generation)


def test_v2_instructions_ask_for_everything_in_the_plan():
    """REQ-008, REQ-009, REQ-018, REQ-019: las instrucciones `consulta-v2` piden lo de
    "Qué se le pide" del plan: responder solo con las unidades, afirmaciones cortas con sus
    alias, no copiar el texto, el papel de cada categoría, no usar un considerando como
    obligación, el texto vigente ante una unidad modificada, la marca `regimes_differ`
    con las dos citas, y "undetermined" sin afirmaciones. La v1 sigue sin la marca."""
    v2 = answering.load_instructions("consulta-v2")
    for phrase in ("solo con lo que dicen las unidades", "No copies el texto",
                   "es lo que se aplica", "marco de referencia",
                   "criterio que acompaña", "considerando", "obligación",
                   "texto vigente", "regimes_differ", "undetermined",
                   "fecha de autorización del procedimiento", "6 afirmaciones"):
        assert phrase in v2, phrase
    assert "regimes_differ" not in answering.load_instructions("consulta-v1")


# --- REQ-019: marca de regímenes ------------------------------------------------------


@pytest.mark.django_db
def test_regimes_differ_with_both_citations_is_kept(corpus, fake_generation):
    """REQ-019: dado un punto que el régimen específico y el marco nacional regulan de
    manera distinta, cuando el modelo marca la afirmación y cita los dos, entonces el
    resultado conserva `regimes_differ` con las dos citas, la del régimen específico
    primero, y no queda anomalía."""
    fake_generation.answer([
        st("El régimen fija el cinco por ciento y el marco el tres.", "U2", "U1",
           differ=True),
    ])

    answer = ask(pks(corpus, "regimen", "marco"))

    assert answer.result["status"] == "grounded"
    assert answer.result["statements"] == [
        {"text": "El régimen fija el cinco por ciento y el marco el tres.",
         "regimes_differ": True, "citations": pks(corpus, "regimen", "marco")},
    ]
    assert answer.anomalies == []


@pytest.mark.django_db
@pytest.mark.parametrize("cited", [
    ["regimen"],
    ["marco"],
    ["regimen", "dictamen"],
    ["otra", "marco"],
    ["considerando", "marco"],
], ids=["only-regimen", "only-marco", "regimen-and-dictamen", "otra-and-marco",
        "considerando-and-marco"])
def test_regimes_differ_without_both_citations_is_dropped(corpus, fake_generation,
                                                          cited):
    """REQ-019: `regimes_differ` verdadero sin una cita del régimen específico y otra del
    marco nacional (un considerando no cuenta como texto del régimen) apaga la marca, la
    afirmación queda con sus citas y se anota la anomalía `regimes_flag_dropped`."""
    names = ["regimen", "otra", "marco", "dictamen", "considerando"]
    shown = {name: f"U{n}" for n, name in enumerate(names, start=1)}
    aliases = [shown[name] for name in cited]
    fake_generation.answer([st("Válida.", "U1"), st("Marcada.", *aliases, differ=True)])

    answer = ask(pks(corpus, *names))

    assert all(alias_of(answer, corpus[name]) == alias for name, alias in shown.items())
    assert answer.result["status"] == "grounded"
    marked = next(s for s in answer.result["statements"] if s["text"] == "Marcada.")
    assert marked["regimes_differ"] is False
    assert sorted(marked["citations"]) == sorted(pks(corpus, *cited))
    assert answer.anomalies == [{"type": "regimes_flag_dropped", "statement": 1,
                                 "detail": "regimes_differ sin una cita del régimen "
                                           "específico y otra del marco nacional"}]


# --- Unidades modificadas: pedido y `changes` del resultado ---------------------------


@pytest.fixture
def modified(make_norm, make_document, make_reading, make_relation):
    """`art-1` de una norma del régimen específico, modificado desde el 2020-06-01 por el
    `art-3` de otra norma; `art-2` sin cambios; y un cambio sobre el inciso `b` del
    `art-4` que viene de la norma modificatoria entera (sin unidad de origen)."""
    target = make_norm(category="regimen_especifico")
    target_units = make_reading(make_document(target), [
        ("art-1", "ARTICULO 1.- La garantía sintética es del diez por ciento."),
        ("art-2", "ARTICULO 2.- Otro artículo sintético."),
        ("art-4", "ARTICULO 4.- Requisitos sintéticos:"),
        ("art-4/inc-b", "b) inciso sintético original."),
    ]).units_by_key
    source = make_norm(category="regimen_especifico", citation="Modificatoria sintética 1/2020")
    source_units = make_reading(make_document(source), [
        ("art-3", "ARTICULO 3.- Sustitúyese el artículo 1: la garantía es del cinco por "
                  "ciento."),
    ]).units_by_key
    make_relation(source, target, "modifica", source_unit_key="art-3",
                  target_unit_key="art-1", effective_date=date(2020, 6, 1))
    whole = make_norm(category="regimen_especifico", citation="Modificatoria sintética 2/2021")
    make_relation(whole, target, "deroga", target_unit_key="art-4/inc-b",
                  effective_date=date(2021, 2, 1))
    return {"art-1": target_units["art-1"], "art-2": target_units["art-2"],
            "art-4": target_units["art-4"], "inc-b": target_units["art-4/inc-b"],
            "art-3": source_units["art-3"]}


@pytest.mark.django_db
def test_modified_unit_is_followed_by_the_modifying_text_with_its_date(modified,
                                                                      fake_generation):
    """REQ-008: a la fecha, una unidad modificada se le muestra al modelo seguida del
    texto de la que la modifica, con la fecha del cambio y su propio alias, que el
    modelo puede citar."""
    fake_generation.answer([st("La garantía vigente es del cinco por ciento.", "U1",
                               "U2")])

    answer = ask([modified["art-1"].pk, modified["art-2"].pk])

    assert answer.aliases == {"U1": modified["art-1"].pk, "U2": modified["art-3"].pk,
                              "U3": modified["art-2"].pk}
    content = user_message(fake_generation)
    after_u1 = content.split("[U1]", 1)[1].split("[U3]", 1)[0]
    assert answering.unit_text(modified["art-1"]) in after_u1
    assert "[U2] modifica a [U1] desde el 01/06/2020" in after_u1
    assert answering.unit_text(modified["art-3"]) in after_u1
    assert "Modificatoria sintética 1/2020" in after_u1
    assert answer.result["statements"][0]["citations"] == [modified["art-1"].pk,
                                                           modified["art-3"].pk]


@pytest.mark.django_db
def test_result_carries_changes_and_the_modifying_unit(modified, fake_generation):
    """REQ-008: el resultado trae `changes` por unidad, y la unidad que modifica a una
    citada aparece en `units` aunque el modelo no la cite."""
    fake_generation.answer([st("Afirmación.", "U1")])

    answer = ask([modified["art-1"].pk])

    art_1, art_3 = modified["art-1"], modified["art-3"]
    units = answer.result["units"]
    assert set(units) == {str(art_1.pk), str(art_3.pk)}
    assert units[str(art_1.pk)]["changes"] == [
        {"relation_type": "modifica", "unit": art_3.pk, "target_unit_key": "art-1",
         "effective_date": "2020-06-01"},
    ]
    assert units[str(art_3.pk)]["changes"] == []
    assert units[str(art_3.pk)]["norm"] == "Modificatoria sintética 1/2020"
    assert answer.result["statements"][0]["citations"] == [art_1.pk]


@pytest.mark.django_db
def test_before_the_change_the_unit_goes_alone(modified, fake_generation):
    """REQ-008: antes de la fecha del cambio la unidad se muestra sola y el resultado no
    trae cambios ni la unidad que la modificaría."""
    fake_generation.answer([st("Afirmación.", "U1")])

    answer = ask([modified["art-1"].pk], reference_date=date(2020, 5, 31))

    assert answer.aliases == {"U1": modified["art-1"].pk}
    content = user_message(fake_generation)
    assert "modifica a" not in content
    assert answering.unit_text(modified["art-3"]) not in content
    assert answer.result["units"][str(modified["art-1"].pk)]["changes"] == []
    assert set(answer.result["units"]) == {str(modified["art-1"].pk)}


@pytest.mark.django_db
def test_modifying_unit_also_selected_is_shown_once(modified, fake_generation):
    """REQ-008: si la unidad que modifica también llega entre las seleccionadas (la suma
    la recuperación, T-033), se muestra una sola vez, a continuación de la modificada."""
    answer = ask([modified["art-3"].pk, modified["art-1"].pk])

    content = user_message(fake_generation)
    assert content.count(answering.unit_text(modified["art-3"])) == 1
    assert answer.aliases == {"U1": modified["art-1"].pk, "U2": modified["art-3"].pk}


@pytest.mark.django_db
def test_change_without_source_unit_names_the_norm_and_date(modified, fake_generation):
    """REQ-008: un cambio que viene de una norma entera (sin unidad de origen) se le
    muestra al modelo con la norma, la fecha y la parte alcanzada, y en el resultado
    queda con `unit` vacío."""
    fake_generation.answer([st("Afirmación.", "U1")])

    answer = ask([modified["art-4"].pk])

    content = user_message(fake_generation)
    assert "Modificatoria sintética 2/2021 deroga" in content
    assert "desde el 01/02/2021" in content
    assert modified["inc-b"].path in content
    assert answer.aliases == {"U1": modified["art-4"].pk}
    assert answer.result["units"][str(modified["art-4"].pk)]["changes"] == [
        {"relation_type": "deroga", "unit": None, "target_unit_key": "art-4/inc-b",
         "effective_date": "2021-02-01"},
    ]


@pytest.mark.django_db
def test_stored_result_is_json_serializable(modified, fake_generation):
    """REQ-008: el resultado con cambios se puede guardar como JSON tal cual."""
    fake_generation.answer([st("Afirmación.", "U1", "U2")])

    answer = ask([modified["art-1"].pk])

    assert json.loads(json.dumps(answer.result)) == answer.result


@pytest.mark.django_db
def test_unit_that_modifies_two_selected_units_is_shown_once(make_norm, make_document,
                                                             make_reading, make_relation,
                                                             fake_generation):
    """REQ-008: si una misma unidad modifica a dos unidades seleccionadas, se muestra una
    sola vez, a continuación de la primera; la segunda la nombra por su alias con "Su
    texto está más arriba", y el resultado la trae una sola vez."""
    target = make_norm(category="regimen_especifico")
    target_units = make_reading(make_document(target), [
        ("art-1", "ARTICULO 1.- Plazo sintético de diez días."),
        ("art-2", "ARTICULO 2.- Garantía sintética del diez por ciento."),
    ]).units_by_key
    source = make_norm(category="regimen_especifico",
                       citation="Modificatoria sintética 3/2022")
    art_9 = make_reading(make_document(source), [
        ("art-9", "ARTICULO 9.- Sustitúyense los artículos 1 y 2 por textos sintéticos."),
    ]).units_by_key["art-9"]
    for key in ("art-1", "art-2"):
        make_relation(source, target, "modifica", source_unit_key="art-9",
                      target_unit_key=key, effective_date=date(2022, 3, 1))
    art_1, art_2 = target_units["art-1"], target_units["art-2"]
    fake_generation.answer([st("Afirmación.", "U1", "U3")])

    answer = ask([art_1.pk, art_2.pk])

    assert answer.aliases == {"U1": art_1.pk, "U2": art_9.pk, "U3": art_2.pk}
    content = user_message(fake_generation)
    assert content.count(answering.unit_text(art_9)) == 1
    after_u1 = content.split("[U1]", 1)[1].split("\n\n[U3]", 1)[0]
    assert "[U2] modifica a [U1] desde el 01/03/2022" in after_u1
    assert answering.unit_text(art_9) in after_u1
    after_u3 = content.split("\n\n[U3]", 1)[1]
    assert ("[U2] modifica a [U3] desde el 01/03/2022. Su texto está más arriba."
            in after_u3)
    units = answer.result["units"]
    assert set(units) == {str(art_1.pk), str(art_2.pk), str(art_9.pk)}
    assert [c["unit"] for c in units[str(art_1.pk)]["changes"]] == [art_9.pk]
    assert [c["unit"] for c in units[str(art_2.pk)]["changes"]] == [art_9.pk]


@pytest.mark.django_db
def test_dropped_flag_names_the_position_in_the_model_output(corpus, fake_generation):
    """REQ-019: `statement` de la anomalía `regimes_flag_dropped` es la posición de la
    afirmación en la salida del modelo, no en la respuesta ordenada por el código."""
    # Alias en el orden mostrado: U1 régimen, U2 marco, U3 dictamen.
    fake_generation.answer([
        st("Criterio.", "U3"),
        st("Régimen marcado.", "U1", differ=True),
    ])

    answer = ask(pks(corpus, "regimen", "marco", "dictamen"))

    assert [s["text"] for s in answer.result["statements"]] == ["Régimen marcado.",
                                                               "Criterio."]
    assert answer.result["statements"][0]["regimes_differ"] is False
    assert [a["statement"] for a in answer.anomalies] == [1]
    assert answer.anomalies[0]["type"] == answering.REGIMES_FLAG_DROPPED
