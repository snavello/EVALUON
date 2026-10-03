"""Corrector tolerante de datos clave (T-058; ADR-0011; plan 001, "Evals", "Datos clave y
corrector").

Un dato clave es un texto o una lista de variantes; se cumple si aparece cualquiera de
ellas. El corrector compara con números en letras de cualquier tamaño, sin punto de
miles, y con singular y plural por palabra; no acepta sinónimos, cambio de orden ni
palabras intercaladas. Los ejemplos de la corrida de calibración de T-045 son los que
cita el ADR-0011. Todos los textos son sintéticos o de normativa pública (P4).
"""

import json
from datetime import date
from pathlib import Path

import pytest

from evaluon.queries import evaluation

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "evals" / "t058"

N247 = "Disposición AFIP 247/2022"


def ok(datum, *statements):
    """El dato (texto o lista de variantes) se cumple con las afirmaciones."""
    return evaluation.key_data_missing([datum], list(statements)) == []


# --- Ejemplos del ADR-0011 --------------------------------------------------------------


def test_thirty_in_words_counts_as_30_days():
    """REQ-008 (ADR-0011): "treinta días a partir de la fecha de apertura del acto"
    cumple "30 días"."""
    assert ok("30 días", "Treinta días a partir de la fecha de apertura del acto.")


@pytest.mark.parametrize("datum, answer", [
    ("contratación directa", "Se admiten contrataciones directas en ese caso."),
    ("contrataciones directas", "Procede la contratación directa."),
])
def test_singular_and_plural_are_the_same_datum(datum, answer):
    """REQ-008 (ADR-0011): "contrataciones directas" cumple "contratación directa", y al
    revés."""
    assert ok(datum, answer)


def test_no_with_its_variant_is_met_by_the_variant():
    """REQ-008 (ADR-0011): `["no", "sin posibilidad"]` se cumple con "serán desestimadas
    sin posibilidad de subsanación"; "no" solo, con la misma respuesta, no se cumple: el
    corrector no deduce variantes."""
    answer = "Serán desestimadas sin posibilidad de subsanación."
    assert ok(["no", "sin posibilidad"], answer)
    assert not ok("no", answer)
    assert not ok(["no"], answer)


@pytest.mark.parametrize("datum, answer", [
    ("por igual término", "Se prorroga por un período igual."),
    ("acto de apertura", "Desde la apertura del acto."),
])
def test_synonyms_and_reordering_are_not_accepted(datum, answer):
    """REQ-008 (ADR-0011): "por un período igual" no cumple "por igual término" y
    "apertura del acto" no cumple "acto de apertura": hace falta la variante en el
    caso."""
    assert not ok(datum, answer)


# --- Números en letras de cualquier tamaño y punto de miles -------------------------------


@pytest.mark.parametrize("datum, answer", [
    ("120 días", "Dentro de los ciento veinte días corridos."),
    ("2500", "Hasta dos mil quinientos módulos."),
    ("35 días", "En treinta y cinco días."),
    ("21 días", "En veintiún días."),
    ("100 %", "El cien por ciento del monto."),
    ("1000 pesos", "Mil pesos."),
    ("200000", "Doscientos mil."),
    ("2300000", "Dos millones trescientos mil."),
    ("M 1000", "Hasta M 1.000 de monto."),
    ("M 1.000", "Hasta M 1000 de monto."),
    ("60 días", "Sesenta (60) días."),
    ("2500", "Dos mil quinientos (2.500)."),
])
def test_numbers_in_words_of_any_size_and_thousands_point(datum, answer):
    """REQ-008 (ADR-0011): un número en letras de cualquier tamaño pasa a su cifra
    ("ciento veinte" a 120, "dos mil quinientos" a 2500) y la cifra pierde el punto de
    miles ("M 1.000" cumple "M 1000")."""
    assert ok(datum, answer)


@pytest.mark.parametrize("datum, answer", [
    ("1 %", "Una multa del uno por ciento."),
    ("20 %", "Hasta el veinte por ciento del contrato."),
    ("15 %", "El quince por ciento."),
    ("1 %", "Del 1% del monto."),
])
def test_percent_in_words_without_the_figure(datum, answer):
    """REQ-008 (aviso de T-039, ADR-0011): "uno por ciento" o "veinte por ciento", sin la
    cifra, cumplen "1 %" y "20 %"."""
    assert ok(datum, answer)


def test_per_thousand_is_not_converted():
    """REQ-008 (plan, "Datos clave y corrector"): "por mil" no es un número: "cinco por
    mil" es "5 por mil" y no cumple "5 %"."""
    assert evaluation.normalize_for_search("Cinco por mil") == "5 por mil"
    assert ok("5 por mil", "Una multa del cinco por mil.")
    assert not ok("5 %", "Una multa del cinco por mil.")


@pytest.mark.parametrize("datum, answer", [
    ("3 días", "En 13 días."),
    ("3 días", "En 30 días."),
    ("3 días", "En treinta días."),
    ("5 %", "El 0,5 % del monto."),
    ("5 %", "El cero coma cinco: 0,5 por ciento."),
    ("1000", "Son 21.000 pesos."),
])
def test_number_boundaries_still_hold(datum, answer):
    """REQ-008 (ADR-0011): "13 días" y "30 días" no cumplen "3 días", y "0,5 %" no cumple
    "5 %"."""
    assert not ok(datum, answer)


def test_comma_decimal_is_kept():
    """REQ-008 (plan, "Datos clave y corrector"): la coma decimal se mantiene."""
    assert evaluation.normalize_for_search("0,1 %") == "0,1 %"
    assert ok("0,1 %", "Una multa del 0,1% por día.")


def test_un_and_una_are_one_on_both_sides():
    """REQ-008 (plan): "un", "una" y "uno" pasan a "1" también cuando son artículo, en la
    respuesta y en la variante: "un período" sigue valiendo "un período"."""
    assert ok("un período", "Por un período igual.")
    assert ok("1 vez", "Una vez por año.")


# --- Singular y plural por palabra ------------------------------------------------------


@pytest.mark.parametrize("datum, answer", [
    ("mes", "Dentro de los tres meses."),
    ("meses", "Dentro de un mes."),
    ("vez", "Hasta dos veces."),
    ("veces", "Por una vez."),
    ("día", "Cuenta por días."),
    ("garantía de la oferta", "Las garantías de las ofertas."),
])
def test_plural_by_word(datum, answer):
    """REQ-008 (ADR-0011): "meses" cumple "mes" y "veces" cumple "vez"; cada palabra vale
    con una diferencia final de "s", de "es" o de "z" por "ces"."""
    assert ok(datum, answer)


@pytest.mark.parametrize("datum, answer", [
    ("garantía de la oferta", "La garantía de esta oferta."),
    ("garantía oferta", "La garantía de la oferta."),
    ("días hábiles", "Días no hábiles."),
    ("mes", "Los mesones."),
    ("día", "Diario."),
])
def test_words_must_be_contiguous_whole_and_in_order(datum, answer):
    """REQ-008 (ADR-0011): las palabras del dato van seguidas, en el mismo orden y
    enteras: no hay palabras intercaladas."""
    assert not ok(datum, answer)


# --- "Sí" y "no" ---------------------------------------------------------------------------


@pytest.mark.parametrize("datum, answer, met", [
    ("no", "No obstante, el pliego puede agregar causales.", False),
    (["no", "sin posibilidad"], "No obstante, puede subsanarse.", False),
    ("no", "No, el pliego no puede.", True),
    (["sí", "puede"], "El pliego puede hacerlo.", True),
    (["sí"], "Sí; el pliego puede.", True),
])
def test_yes_or_no_variant_follows_the_first_statement_rule(datum, answer, met):
    """REQ-008 (ADR-0011): una variante "sí" o "no" sigue la regla de la primera
    afirmación ("No obstante, …" no es un "no"); las demás variantes se buscan en todas
    las afirmaciones."""
    assert ok(datum, answer) is met


def test_other_variants_are_searched_in_every_statement():
    """REQ-008 (ADR-0011): una variante que no es "sí" ni "no" se busca en todas las
    afirmaciones, no solo en la primera."""
    assert ok(["no", "sin posibilidad"], "El pliego lo dice.",
              "Se desestiman sin posibilidad de subsanación.")


# --- Lo que se informa como faltante -----------------------------------------------------


def test_missing_datum_is_reported_with_all_its_variants():
    """REQ-008 (plan, "Datos clave y corrector", regla 1): un dato faltante se informa
    con todas sus variantes, como lista; uno de una sola forma, como lista de una."""
    missing = evaluation.key_data_missing(
        ["30 días", ["acto de apertura", "fecha de apertura"], "5 %"],
        ["El plazo es de 10 días desde la publicación."])

    assert missing == [["30 días"], ["acto de apertura", "fecha de apertura"], ["5 %"]]


def test_missing_variants_go_to_results_as_a_list_and_to_the_summary_with_slashes(
    read_user, two_regimes, fake_ai, tmp_path
):
    """REQ-008 (plan, regla 1): un faltante con variantes sale como lista en
    `resultados.jsonl` y con sus variantes separadas por " / " en `resumen.md`."""
    fake_ai.reranker.default = 0.9

    report = evaluation.run(read_user, FIXTURES / "casos-faltante", tmp_path,
                            commit="abc1234")

    rows = [json.loads(row) for row in
            (report.folder / "resultados.jsonl").read_text(encoding="utf-8").splitlines()]
    [row] = [row for row in rows if row["id"] == "EV-861"]
    assert ["acto de apertura", "fecha de apertura"] in row["measures"]["missing_key_data"]
    summary = (report.folder / "resumen.md").read_text(encoding="utf-8")
    failed = summary.split("## Casos fallados")[1]
    assert "acto de apertura / fecha de apertura" in failed


# --- Lectura de los casos ----------------------------------------------------------------


def write_case(folder, datos_clave):
    text = (FIXTURES / "casos-faltante" / "EV-861.yaml").read_text(encoding="utf-8")
    text = text.replace(
        'datos_clave: ["30 días", ["acto de apertura", "fecha de apertura"]]',
        f"datos_clave: {datos_clave}")
    (folder / "EV-861.yaml").write_text(text, encoding="utf-8")


@pytest.mark.parametrize("datos_clave, message", [
    ('["30 días", []]', "lista de variantes vacía"),
    ('["30 días", ""]', "vacío"),
    ('["30 días", ["no", ""]]', "vacía"),
    ('["30 días", [["no"], "sin posibilidad"]]', "lista dentro"),
    ('["30 días", 30]', "texto"),
    ('["30 días", [no, "sin posibilidad"]]', "texto"),
    ('"30 días"', "lista"),
])
def test_malformed_key_data_leaves_the_case_malformed(tmp_path, datos_clave, message):
    """REQ-008 (plan, "Datos clave y corrector"): una lista vacía, un texto vacío, una
    lista dentro de la lista de variantes o un valor que no sea texto dejan el caso mal
    formado, con un mensaje en lenguaje llano, y no se corre."""
    write_case(tmp_path, datos_clave)

    cases, skipped = evaluation.load_cases(tmp_path)

    assert cases == []
    [skip] = skipped
    assert skip.kind == evaluation.MALFORMED
    assert "datos_clave" in skip.reason
    assert message in skip.reason


def test_text_and_variant_lists_are_read_as_variants(tmp_path):
    """REQ-008 (plan): un texto solo equivale a una lista de una variante; una lista es
    el dato con sus variantes."""
    write_case(tmp_path, '["30 días", ["no", "sin posibilidad"]]')

    [case], skipped = evaluation.load_cases(tmp_path)

    assert skipped == []
    assert case.key_data == (("30 días",), ("no", "sin posibilidad"))


def test_block_form_with_variants_is_read(tmp_path):
    """REQ-008 (plan): la forma en bloque del plan también vale."""
    write_case(tmp_path, '\n  - "30 días"\n  - ["acto de apertura", "fecha de apertura"]'
                         '\n  - ["no", "sin posibilidad"]')

    [case], _ = evaluation.load_cases(tmp_path)

    assert case.key_data == (("30 días",), ("acto de apertura", "fecha de apertura"),
                             ("no", "sin posibilidad"))


def test_grade_reports_variants_of_the_missing_datum():
    """REQ-008: `grade` da el caso por incorrecto si falta un dato y lo informa con sus
    variantes."""
    case = evaluation.Case(
        id="EV-999", file="EV-999.yaml", question="¿Pregunta sintética?",
        reference_date=date(2024, 5, 20), regime=N247, has_answer=True,
        units=((N247, "anexo/art-55"),),
        key_data=(("30 días",), ("no", "sin posibilidad")),
        differ=False, pair="", notice=False, approval="Comisión sintética")
    unit = {"unit": 1, "norm": N247, "key": "anexo/art-55", "unit_type": "articulo",
            "category": "regimen_especifico", "literal": True}
    result = {"status": "grounded", "regime": [{"norm": 2, "name": N247}], "notices": [],
              "statements": [{"text": "Treinta días. No obstante, puede.",
                              "citations": [1]}]}

    measures = evaluation.grade(case, result, [unit])

    assert measures["correct"] is False
    assert measures["missing_key_data"] == [["no", "sin posibilidad"]]


def test_no_in_a_later_statement_does_not_count_when_the_first_says_neither():
    """REQ-008 (ADR-0011; plan, "Datos clave y corrector", regla 2): el "no" se mira solo
    en la primera afirmación. Si la primera no dice ni sí ni no, que otra afirmación
    empiece con "No," no cumple el dato."""
    assert not ok("no", "El pliego lo regula.", "No, no puede.")
