"""T-240 (ronda de ajuste única de la 015, ADR-0025): los hallazgos de código de la medición T-239
que tocan la evaluación. Un bloque por hallazgo. Textos y datos inventados (P4); sin red ni modelo.

- H-1: el número de una cláusula («11.10.») no es un monto exigido (REQ-103).
- H-2: el requisito de una forma de garantía no aplica a la oferta que eligió otra (REQ-103,
  decisión del 2026-10-10 «Requisito de la forma elegida»).
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from evaluon.assessment import combine, portal_facts, rules
from evaluon.portal import models as pm  # noqa: F401
from tests.assessment.test_ordering import portal  # noqa: F401 - `portal` es fixture
from tests.assessment.test_portal_facts import pair_of, portal_data

pytestmark = pytest.mark.django_db


# --- H-1: el número de cláusula no es un monto --------------------------------------------------


@pytest.mark.parametrize("text", [
    "11.10. Cláusula de ejemplo",
    "17.12. Constituir la garantía. 11.10. Otro punto del pliego.",
    "Conforme al punto 11.10 del pliego, el original se presentará en la oficina.",
    "Según los puntos 11.9, 11.10 y 11.11 del pliego.",
    "Ver el artículo 18.10 de la disposición.",
    "Cláusula N° 13.20 y anexo 4.50 del pliego.",
])
def test_a_clause_number_is_not_an_amount(text):
    """REQ-103, T-240 (H-1): «11.10.» al comienzo de una cláusula, o un número de punto o artículo,
    no se lee como monto."""
    assert portal_facts.amounts(text) == []


@pytest.mark.parametrize("text, expected", [
    ("11.10. La garantía será de $ 21.750,00.", [Decimal("21750.00")]),
    ("Constituir una garantía por $ 11.10.", [Decimal("11.10")]),
    ("El Portal informa 5045030.00 de garantía.", [Decimal("5045030.00")]),
    ("17.12. Hasta la suma de $ 3000 en el punto 17.12.", [Decimal("3000")]),
])
def test_an_amount_next_to_a_clause_number_is_still_read(text, expected):
    """REQ-103, T-240 (H-1): lo que sí es un monto se sigue leyendo (con `$`, con separador de miles
    o con dos decimales fuera de un número de cláusula)."""
    assert portal_facts.amounts(text) == expected


def test_the_clause_number_is_not_the_amount_the_pliego_requires(offer, portal):
    """REQ-103, T-240 (H-1): un requisito que empieza con su número («11.10.») y no fija monto ni
    porcentaje no se compara con «11.10»: el Portal no contradice nada (antes: «no cumple»,
    «el pliego exige el monto de 11.10», en ofertas que el dictamen admite)."""
    portal_data(portal, offer, amount="5045030.00")
    text = "11.10. Constituir la garantía de mantenimiento de la oferta en la forma elegida."
    pair = pair_of(text, combine.Combined(outcome="sin_documento"))
    rules.apply(pair, SimpleNamespace(offer=offer))
    assert pair.combined.outcome != "no_cumple"
    assert pair.combined.facts["comparacion"]["exigido"] != "11.10"
    assert "11.10" not in pair.combined.explanation


# --- H-2: el requisito de una forma de garantía solo se evalúa en la oferta que la eligió -----------

PAGARE_LIMIT = ("Si se opta por el pagaré, el oferente tendrá presente que su importe no excederá las CIEN "
                "(100) UNIDADES TASADAS y que no podrá combinarse con otra forma de garantía.")
PAGARE_COPY = ("Será requisito insubsanable acompañar con la oferta la copia del pagaré, sin perjuicio "
               "de su posterior entrega.")
POLICY_UPLOAD = ("Además, el oferente deberá cargar el documento electrónico de la póliza de seguro de "
                 "caución en el Portal de Contrataciones: «Etapa 5 Datos mínimos de la garantía». De no "
                 "contarse con la constancia de constitución de la garantía de mantenimiento de la "
                 "oferta, el organismo la requerirá.")
NOT_ELECTRONIC = ("Cuando se opte por garantías no electrónicas, el original de la garantía deberá "
                  "entregarse en la ventanilla de recepción de la sede central.")


def chosen_form(portal, offer, form, amount="21750.00"):
    """El Portal informa una garantía de mantenimiento de la oferta en la forma `form`."""
    data = pm.PortalOfferData.objects.create(
        offer=offer, cuit="30-00000000-0", currency="ARS", total=Decimal("435000.00"), item=portal)
    pm.PortalGuarantee.objects.create(
        offer_data=data, guarantee_type="Mantenimiento oferta", guarantee_form=form,
        amount=Decimal(amount), item=portal)
    return data


def apply(offer, text, outcome="no_determinado", doubt="falta_coincidencia", **fields):
    pair = pair_of(text, combine.Combined(outcome=outcome, doubt=doubt, **fields))
    return rules.apply(pair, SimpleNamespace(offer=offer)), pair.combined


@pytest.mark.decision_literal
@pytest.mark.parametrize("text, form", [
    (PAGARE_LIMIT, "Seguros"),        # el límite del pagaré en una oferta con póliza
    (PAGARE_COPY, "Seguros"),         # la copia del pagaré en una oferta con póliza
    (POLICY_UPLOAD, "Pagare"),        # la póliza que se carga en el Portal en una oferta con pagaré
    (NOT_ELECTRONIC, "Seguros"),      # el original de las garantías no electrónicas, con póliza
])
def test_the_requirement_of_a_form_not_chosen_does_not_apply(offer, portal, text, form):
    """REQ-103, decisión del 2026-10-10 «Requisito de la forma elegida»: el requisito de una forma
    de garantía que la oferta no eligió no aplica: «cumple» con la explicación «No aplica», la
    cita del Portal que muestra la forma elegida y sin pregunta (antes: «no cumple» o «falta de
    coincidencia» en condiciones de la póliza evaluadas en el pagaré y al revés)."""
    chosen_form(portal, offer, form)
    name, combined = apply(offer, text)
    assert name == "forma_garantia_no_elegida"
    assert (combined.outcome, combined.doubt) == ("cumple", "")
    assert combined.explanation.startswith("No aplica:") and form in combined.explanation
    assert combined.facts["aplica"] is False and combined.facts["regla"] == name
    assert combined.facts["version_reglas"] == "reglas-v12"
    assert combined.question == "" and not combined.ask
    assert combined.citations == [] and len(combined.portal) == 1
    assert combined.portal[0]["kind"] == "garantia" and form in combined.portal[0]["text"]


@pytest.mark.decision_literal
@pytest.mark.parametrize("text, form", [
    (PAGARE_LIMIT, "Pagare"),
    (PAGARE_COPY, "Pagare"),
    (POLICY_UPLOAD, "Seguros"),
    (NOT_ELECTRONIC, "Pagare"),
])
def test_the_requirement_of_the_form_chosen_is_evaluated_as_always(offer, portal, text, form):
    """REQ-103, «Requisito de la forma elegida»: en la oferta que eligió esa forma el requisito se
    evalúa: la regla de la forma no decide y queda lo que concluyó el modelo."""
    chosen_form(portal, offer, form)
    name, combined = apply(offer, text, outcome="cumple", doubt="")
    assert name != "forma_garantia_no_elegida"
    assert combined.outcome == "cumple" and not combined.explanation.startswith("No aplica")
    assert "aplica" not in combined.facts


@pytest.mark.parametrize("text", [
    # nombra dos formas: vale para todas las ofertas
    "La garantía se constituirá con pagaré o con póliza de seguro de caución.",
    # nombra una forma sin condicionarla ni pedir su documento
    "La garantía de mantenimiento se constituirá mediante póliza de seguro de caución.",
    # no es una forma de garantía
    "Se acompañará una póliza de seguro de responsabilidad civil.",
    # ninguna forma
    "Constituir una garantía de mantenimiento de la oferta del cinco por ciento (5 %).",
])
def test_a_requirement_that_is_not_of_one_form_applies_to_every_offer(offer, portal, text):
    """REQ-103: solo es «de una forma» el requisito que nombra una sola y la condiciona o pide su
    documento; los demás valen para todas las ofertas."""
    chosen_form(portal, offer, "Seguros" if "pagaré" in text.lower() else "Pagare")
    name, _ = apply(offer, text)
    assert name != "forma_garantia_no_elegida"


def test_without_the_portal_form_the_rule_says_nothing(offer, portal):
    """REQ-103: sin garantía del Portal, o con una forma que no se reconoce, la regla no decide:
    queda lo que concluyó el modelo (que la instrucción guía)."""
    name, combined = apply(offer, PAGARE_LIMIT, outcome="cumple", doubt="")
    assert name != "forma_garantia_no_elegida" and combined.outcome == "cumple"
    chosen_form(portal, offer, "Efectivo")
    name, _ = apply(offer, PAGARE_LIMIT)
    assert name != "forma_garantia_no_elegida"


def test_the_guarantee_of_another_obligation_is_not_the_form_chosen(offer, portal):
    """REQ-103: la garantía de cumplimiento que informe el Portal no cuenta como la forma elegida
    para la oferta."""
    data = chosen_form(portal, offer, "Seguros")
    pm.PortalGuarantee.objects.filter(offer_data=data).update(guarantee_type="Cumplimiento de contrato")
    name, _ = apply(offer, PAGARE_LIMIT)
    assert name != "forma_garantia_no_elegida"


# --- La regla del Portal no compara lo que el requisito no pide (T-239: 8 «no determinado» de código) --

QUOTE_PER_LINE = ("Si se habilita la cotización parcial para las cooperativas, el resto de los oferentes "
                  "podrá cotizar en el apartado «oferta alternativa del SESENTA POR CIENTO (60 %)» del "
                  "Portal distintos precios según los porcentajes de adjudicación posibles hasta los "
                  "cuales el organismo podrá adjudicar, sin perjuicio de que deberá presentar la "
                  "cotización por la cantidad total de cada renglón.")


def quoted_lines(offer, procedure, portal, numbers=(1, 2, 3)):
    portal_data(portal, offer)
    for number in numbers:
        line = pm.PortalLine.objects.create(
            procedure=procedure, number=number, description="x", item=portal)
        pm.PortalQuote.objects.create(
            offer=offer, line=line, price=Decimal("100.0000"), quantity=Decimal("10.0000"))


@pytest.mark.decision_literal
def test_an_alternative_percentage_and_a_hasta_that_are_not_about_the_price_do_not_block_the_quote(
        offer, procedure, portal):
    """REQ-103, T-240: «hasta los cuales…» y «oferta alternativa del 60 %» describen la oferta
    alternativa y la adjudicación, no un tope ni un porcentaje del precio: el Portal tiene el precio
    de todos los renglones y el requisito pide la cotización de cada renglón, entonces «cumple»
    con la cita del Portal (antes: «tope que el sistema no compara»)."""
    quoted_lines(offer, procedure, portal)
    pair = pair_of(QUOTE_PER_LINE, combine.Combined(outcome="no_determinado", doubt="duda"))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_cumple"
    assert pair.combined.outcome == "cumple" and pair.combined.portal


@pytest.mark.decision_literal
@pytest.mark.parametrize("text", [
    "El oferente deberá cotizar cada renglón con un descuento del 10 % sobre el precio de lista.",
    "El precio unitario de cada renglón será de hasta $ 500,00.",
    "El oferente deberá cotizar el precio unitario de cada renglón, con un recargo de hasta "
    "5 % sobre el total.",
])
def test_a_percentage_or_a_hasta_that_is_about_the_price_still_blocks_the_quote(
        offer, procedure, portal, text):
    """REQ-103, D-233-1: un descuento, un recargo o un «hasta» con un valor sobre el precio siguen
    sin compararse: nunca «cumple»."""
    quoted_lines(offer, procedure, portal)
    pair = pair_of(text, combine.Combined(outcome="sin_documento"))
    rules.apply(pair, SimpleNamespace(offer=offer))
    assert pair.combined.outcome != "cumple"
    assert pair.combined.facts["regla"] != "portal_cumple"


@pytest.mark.decision_literal
def test_loading_the_policy_in_the_portal_is_met_by_the_guarantee_the_portal_informs(offer, portal):
    """REQ-103, T-240: «cargar el documento de la póliza en el Portal» con una póliza como forma
    elegida: el Portal informa esa garantía, «cumple» con la cita del Portal aunque el modelo no
    la haya visto (antes: «tope que el sistema no compara», por «Requisitos mínimos»)."""
    chosen_form(portal, offer, "Seguros")
    pair = pair_of(POLICY_UPLOAD, combine.Combined(outcome="sin_documento"))
    assert rules.apply(pair, SimpleNamespace(offer=offer)) == "portal_cumple"
    assert pair.combined.outcome == "cumple" and pair.combined.portal[0]["kind"] == "garantia"
    assert pair.combined.explanation.startswith("Fuente: Portal")


@pytest.mark.parametrize("text, form", [
    (PAGARE_COPY, "Pagare"),         # la copia del pagaré se mira en los documentos
    (NOT_ELECTRONIC, "Pagare"),      # el original en la Mesa de Entrada no lo resuelve el Portal
    ("El original de la garantía se presentará en la Mesa de Entrada.", "Seguros"),
])
def test_a_requirement_about_a_guarantee_document_is_not_decided_by_the_portal_amount(
        offer, portal, text, form):
    """REQ-103, T-240: un requisito sobre el documento de la garantía (copia, original, Mesa de
    Entrada) no pide un monto: el Portal no decide y no hay «falta de coincidencia» por un monto que
    nadie pidió. T-257 (decisión del 2026-10-12): la presentación física que no consta la decide la
    regla de la presentación física, no la del Portal."""
    chosen_form(portal, offer, form)
    pair = pair_of(text, combine.Combined(outcome="sin_documento"))
    name = rules.apply(pair, SimpleNamespace(offer=offer))
    assert name is None or not name.startswith("portal_")
    assert pair.combined.doubt != "falta_coincidencia"
    if name is None:
        assert pair.combined.outcome == "sin_documento"
    else:
        assert name == "presentacion_fisica_no_consta"


# --- Instrucciones de la evaluación: evaluacion-v9 (REQ-104, REQ-105, REQ-106) ---------------------

import json  # noqa: E402

from django.conf import settings  # noqa: E402

from evaluon.assessment import prompting  # noqa: E402


def test_the_evaluation_instruction_v10_covers_the_cases_and_asks_for_the_citation_that_says_it():
    """REQ-104, REQ-106, T-240 (O-240-2): `evaluacion-v10` dice qué hacer con el requisito de
    referencia, el negativo, el mantenimiento de la oferta y la forma u opción que la oferta no eligió;
    «cumple» solo con la oración de la oferta que dice lo afirmado (P3) y, si no la hay, «no
    determinado»; y la explicación y la pregunta dicen lo mismo que las condiciones y el Portal."""
    # T-257: la vigente es `evaluacion-v11` (criterios del 2026-10-12); esta prueba queda sobre la v10
    # publicada, y la v11 tiene la suya en `test_comite_t257.py`.
    body = (prompting.PROMPTS_DIR / "evaluacion-v10.md").read_text(encoding="utf-8")
    for phrase in ("Requisito de referencia", "no pide un documento propio",
                   "Requisito negativo", "Mantenimiento de la oferta",
                   "Forma u opción que la oferta no eligió", "no la des por cumplida",
                   "Coherencia", "No afirmes en la explicación que una condición se cumple",
                   "No digas que el Portal no informa algo que el bloque",
                   "si todas cumplen, la pregunta va vacía"):
        assert phrase in body, phrase
    # P3: «cumple» solo con la oración que lo dice; sin ella, «no determinado»
    assert body.count("solo si una oración de la oferta") >= 3
    assert body.count('es "no_determinado"') >= 3
    assert "lo da por cumplido" not in body and 'es "cumple", el dato dice "no aplica' not in body
    # lo que ya decían las versiones anteriores sigue
    assert "solo con su propio dato (no vacío) y su propia cita" in body


def test_the_evaluation_instruction_v10_does_not_repeat_the_currency_and_tax_scenario():
    """REQ-106, T-240 (D-240-3): el escenario «pesos e IVA» es el del requisito 10 del caso-00 que se
    mide: `evaluacion-v10` no lo trae (ni «IVA» ni «pesos»), como `evaluacion-v7` y `-v8`; su ejemplo de
    dos condiciones es de otro rubro (vigilancia: dólares y turnos). La v11 tiene la suya en
    `test_comite_t257.py` (T-257)."""
    body = (prompting.PROMPTS_DIR / "evaluacion-v10.md").read_text(encoding="utf-8")
    assert "IVA" not in body and "pesos" not in body and "impuesto" not in body.lower()
    assert "turnos de ocho horas" in body and "USD" in body
    for old in ("evaluacion-v7", "evaluacion-v8"):
        older = (prompting.PROMPTS_DIR / f"{old}.md").read_text(encoding="utf-8")
        assert "IVA" not in older and "pesos" not in older


def test_the_new_evaluation_examples_cite_the_sentence_that_says_what_they_affirm():
    """REQ-104, REQ-106, T-240: hay un ejemplo de requisito de referencia que cumple, uno negativo que
    cumple y uno que no cumple, y uno de mantenimiento de la oferta que cumple; todos se leen con el
    código, su resultado es el que se deriva de sus condiciones y la cita de cada «cumple» dice lo
    afirmado (formularios acompañados, sin reservas, el plazo)."""
    body = prompting.load_prompt("evaluacion")
    section = body[body.index("EJEMPLOS"):]
    examples = [json.loads(line) for line in section.splitlines() if line.startswith("{")]

    def of(keyword):
        return [e for e in examples if keyword in e["condiciones"][0]["condicion"].lower()]

    reference, maintenance = of("formularios"), of("mantener la oferta")
    negative = of("reservas") + of("anticipo")
    assert [e["resultado"] for e in reference] == ["cumple"]
    assert sorted(e["resultado"] for e in negative) == ["cumple", "no_cumple"]
    assert [e["resultado"] for e in maintenance] == ["cumple"]
    says = {"formularios": "formularios 1 a 3", "reservas": "sin reservas",
            "mantener la oferta": "cuarenta días corridos"}
    for keyword, found in (("formularios", reference), ("reservas", negative),
                           ("mantener la oferta", maintenance)):
        for example in found:
            parsed = prompting.parse_evaluation(json.dumps(example), ["D1", "D2", "D3", "P1"], [])
            assert prompting.derive_result(parsed.conditions) == example["resultado"]
            if example["resultado"] == "cumple":
                assert says[keyword] in example["citas"][0]["texto"]


def test_a_cumple_condition_whose_datum_says_no_aplica_goes_down_to_no_determinado():
    """REQ-103, T-240 (observación de la verificación): si el modelo da por «cumple» una condición con
    el dato «no aplica…», la celda no dice «Cumple»: baja a «no determinado» y queda la anomalía; solo
    la regla de la forma de garantía (`guarantee_form`) decide que un requisito no aplica."""
    from evaluon.assessment.services import evaluate as evaluate_service

    cited = SimpleNamespace(text="Texto de la oferta.", document=SimpleNamespace(title="D"), page=1)
    evidence = {1: ("oferta", cited)}
    conditions = [
        prompting.Condition("Entregar la copia del pagaré", "No aplica: la oferta eligió póliza", 1,
                            "cumple"),
        prompting.Condition("Entregar la nota firmada", "nota firmada", 1, "cumple"),
        prompting.Condition("Entregar el formulario", "no aplica: otra forma", 1, "no_cumple"),
    ]
    anomalies = []
    effective, records = evaluate_service._check_conditions(conditions, evidence, 1, anomalies)
    assert [c.result for c in effective] == ["no_determinado", "cumple", "no_cumple"]
    assert [a["type"] for a in anomalies] == ["condicion_no_aplica"]
    assert prompting.derive_result(effective) == "no_cumple"
    assert prompting.derive_result(effective[:2]) == "no_determinado"


def test_the_measurement_match_does_not_count_not_applicable_as_cumple():
    """REQ-103, T-240 (O-240-4): `_match` no cuenta «No aplica» (guardado como «cumple») como «cumple»
    frente a un dictamen que espera «cumple»: no coincide, y se informa aparte."""
    from evaluon.assessment import evaluation

    pair = SimpleNamespace(kind="oferta", result="cumple", doubt="")
    plain = SimpleNamespace(outcome="cumple", doubt="", facts={})
    inapplicable = SimpleNamespace(outcome="cumple", doubt="", facts={"aplica": False})
    assert evaluation._match(pair, plain) is True
    assert evaluation._match(pair, inapplicable) is False


# --- «No aplica (forma de garantía no elegida)»: nunca «cumple» donde se muestra ni se cuenta -----------

from evaluon.assessment import guarantee_form, not_applicable  # noqa: E402
from evaluon.assessment.models import Outcome  # noqa: E402
from evaluon.assessment.services import export as export_service  # noqa: E402
from evaluon.assessment.services import matrix as matrix_service  # noqa: E402
from tests.assessment.fakes import model, says  # noqa: E402,F401 - `model` es una fixture
from tests.assessment.test_evaluate import number_of, results_of, run_all  # noqa: E402

NA_LABEL = "No aplica (forma de garantía no elegida)"


def facts_of(applies=None):
    return SimpleNamespace(outcome="cumple", facts={} if applies is None else {"aplica": applies})


def test_a_single_function_decides_how_a_not_applicable_result_is_shown_and_counted():
    """REQ-103, T-240 (decisión del Coordinador): `not_applicable` es la única definición: un
    resultado con `facts.aplica` falso se muestra «No aplica (forma de garantía no elegida)» y se
    cuenta aparte; una corrección de la persona rige sobre la propuesta."""
    result = facts_of(False)
    assert not_applicable.is_not_applicable(result)
    assert not_applicable.result_label(result) == NA_LABEL
    assert not_applicable.result_label(result, "cumple") == NA_LABEL
    assert not_applicable.outcome_key(result) == not_applicable.KEY == "no_aplica"
    # corregido por la Comisión: rige su resultado
    assert not_applicable.result_label(result, "no_cumple") == "No cumple"
    assert not_applicable.outcome_key(result, "no_cumple") == "no_cumple"
    # un «cumple» común sigue siendo «Cumple»
    assert not_applicable.result_label(facts_of()) == "Cumple"
    assert not_applicable.outcome_key(facts_of()) == "cumple"


@pytest.fixture
def not_applicable_guarantee(monkeypatch):
    """El requisito de la garantía de la matriz se toma como el de una sola forma (pagaré) y el
    Portal informa una póliza de caución: no aplica."""
    monkeypatch.setattr(guarantee_form, "required_forms", lambda text: (
        {"pagare"} if "garantía de mantenimiento" in text else set()))


def evaluated_with_not_applicable(offer, operator_user, procedure, portal):
    portal_data(portal, offer)
    _, runs = run_all(operator_user, procedure)
    return runs[0], results_of(runs[0])[number_of(procedure, "garantía de mantenimiento")]


def test_the_cell_the_pair_and_the_run_counts_never_say_cumple_for_a_not_applicable_requirement(
        offer, operator_user, procedure, model, portal, not_applicable_guarantee):
    """REQ-103, T-240: la regla deja el par «cumple» con `aplica` falso; el detalle del par (texto del
    resultado), la celda de la matriz y las cuentas de la corrida dicen «No aplica (forma de
    garantía no elegida)», no «Cumple»; la cuenta va aparte de «cumple»."""
    run, result = evaluated_with_not_applicable(offer, operator_user, procedure, portal)
    assert result.facts["regla"] == "forma_garantia_no_elegida" and result.facts["aplica"] is False
    assert result.outcome == "cumple"                       # el valor guardado (sin migración)
    assert result.get_outcome_display() == NA_LABEL         # detalle del par
    assert result.citations.filter(kind="portal").exists() and not result.questions.exists()
    assert run.counts["by_outcome"].get("no_aplica") == 1
    others = sum(v for k, v in run.counts["by_outcome"].items() if k != "no_aplica")
    assert others == run.counts["pairs"] - 1               # no está contada como «cumple»
    page = matrix_service.matrix_page(operator_user, procedure.pk)
    cell = page.cells[(offer.pk, result.requirement_id)]
    assert cell.effective_label == NA_LABEL and cell.effective_key == "no_aplica"


def test_the_summary_by_offer_the_economic_page_and_the_exports_count_it_apart(
        offer, operator_user, procedure, model, portal, not_applicable_guarantee):
    """REQ-103, T-240: el resumen por oferta (cuentas y fila aparte), el resumen del recorrido
    («Resultado propuesto por oferta»), la planilla y el cuadro (datos de Excel y PDF) muestran «No
    aplica (forma de garantía no elegida)»; no suma a «cumple» ni a «no determinado»."""
    _, result = evaluated_with_not_applicable(offer, operator_user, procedure, portal)
    page = matrix_service.matrix_page(operator_user, procedure.pk)
    status = next(s for s in page.statuses if s.offer.pk == offer.pk)
    assert status.by_outcome.get("no_aplica") == 1
    counted_cumple = sum(1 for c in page.cells.values()
                         if c.result is not None and c.offer.pk == offer.pk
                         and c.effective_key == "cumple")
    assert status.by_outcome.get("cumple", 0) == counted_cumple
    assert (NA_LABEL, 1) in status.by_outcome_rows
    assert dict(status.by_outcome_rows)["Cumple"] == counted_cumple
    # resumen del recorrido
    from evaluon.journey.temas import s4_descartes

    row = next(r for r in s4_descartes._results(page) if r.get("evaluated"))
    assert row["not_applicable"] == 1 and row["meets"] == counted_cumple
    # planilla y cuadro: los datos que arman el Excel y el PDF
    data = export_service.collect(operator_user, procedure.pk)
    sheet = next(s for s in data.sheets if s.offer.pk == offer.pk)
    requirement_row = next(r for r in sheet.rows if r.number == result.requirement.number)
    assert requirement_row.proposed == NA_LABEL and requirement_row.effective == NA_LABEL
    grid_row = next(cells for r, _, cells in data.grid if r.number == result.requirement.number)
    assert grid_row[0].startswith(NA_LABEL) and "Cumple" not in grid_row[0]
    html = export_service.build_html(data, "planilla")
    assert NA_LABEL in html


def test_the_proposal_screen_shows_it_with_its_own_icon_and_never_as_cumple(
        offer, operator_user, procedure, model, portal, not_applicable_guarantee):
    """REQ-103, T-240: la grilla del recorrido muestra el ícono y el nombre de «No aplica (forma de
    garantía no elegida)» en la celda."""
    from evaluon.journey.temas import s4_propuesta

    _, result = evaluated_with_not_applicable(offer, operator_user, procedure, portal)
    page = matrix_service.matrix_page(operator_user, procedure.pk)
    view = s4_propuesta._cell_views(page, operator_user)[(offer.pk, result.requirement_id)]
    assert view.name == NA_LABEL and view.icon == "na"


def test_the_measurement_counts_these_cells_apart(offer, operator_user, procedure, model, portal,
                                                  not_applicable_guarantee):
    """REQ-103, REQ-104, T-240: `medir_evaluacion` no cuenta estas celdas como «cumple» ni como «no
    determinado»: las informa aparte (cuentas de celdas, celdas del Portal y resultado por par)."""
    from evaluon.assessment import evaluation

    run, result = evaluated_with_not_applicable(offer, operator_user, procedure, portal)
    counts = evaluation.cell_counts(run)
    assert counts["not_applicable"] == 1 and counts["total"] == run.results.count() - 1
    record = evaluation.portal_cell_record(result, "garantia", "21750.00", True)
    assert record["no_aplica"] is True and record["obtenido"] == "no_aplica"
    assert record["cumple_con_cita_portal"] is False and record["cumple_con_dato_distinto"] is False
    assert Outcome.CUMPLE == "cumple"


# --- D-240-1: el número de cláusula sin punto final, con paréntesis, guion o dos puntos -------------------


@pytest.mark.parametrize("text", [
    "3.15 Texto del punto sin importe alguno.",
    "3.15) Texto del punto sin importe alguno.",
    "3.15- Texto del punto sin importe alguno.",
    "11.10: Texto del punto sin importe alguno.",
    "(11.10) Texto del punto sin importe alguno.",
    "Lo dispuesto en 11.10 se aplicará a todos los oferentes.",
    "Los apartados 7.5.1 y 7.5.2 y el 11.10 rigen de igual modo.",
    "Primera oración. 4.20 Texto de otro punto.",
])
def test_a_clause_number_in_any_numbering_form_is_not_an_amount(text):
    """REQ-103, T-240 (D-240-1): el número «N.NN» sin `$` ni señal de dinero no es un monto aunque no
    lleve punto final: «3.15 Texto», «3.15) Texto», «3.15- Texto», «11.10: Texto», «(11.10) Texto» o
    «lo dispuesto en 11.10»."""
    assert portal_facts.amounts(text) == []


@pytest.mark.parametrize("text, expected", [
    ("3.15 El monto de la caución será de $2500,50 por unidad.", [Decimal("2500.50")]),
    ("(11.10) La garantía será de $ 21.750,00.", [Decimal("21750.00")]),
    ("El monto de 11.10 se pagará en cuotas.", [Decimal("11.10")]),
    ("La garantía será de 11.10 pesos.", [Decimal("11.10")]),
    ("Precio total 15.50.", [Decimal("15.50")]),
    ("11.10: el importe asciende a 5045030.00", [Decimal("5045030.00")]),
])
def test_an_amount_with_a_sign_of_money_is_still_read_next_to_a_clause_number(text, expected):
    """REQ-103, T-240 (D-240-1): un «N.NN» con `$`, con una palabra de monto antes o con la moneda
    después sigue siendo un monto; el número de cláusula que lo acompaña no."""
    assert portal_facts.amounts(text) == expected


# --- D-240-2: las relajaciones de la regla del Portal no dan «cumple» sin respaldo --------------------


def apply_portal(offer, text, *, items=()):
    pair = pair_of(text, combine.Combined(outcome="sin_documento"), items=items)
    name = rules.apply(pair, SimpleNamespace(offer=offer))
    return name, pair.combined


@pytest.mark.decision_literal
def test_a_ceiling_written_in_words_is_not_a_cumple(offer, portal):
    """REQ-103, T-240 (D-240-2): «hasta pesos un millón» es un tope escrito en letras: con un total de
    5.000.000 en el Portal nunca «cumple» (queda «no determinado» con la diferencia)."""
    portal_data(portal, offer, total="5000000.00")
    for text in ("El total de la oferta será de hasta pesos un millón.",
                 "El total de la oferta no excederá de pesos un millón.",
                 "El importe total ofertado llegará hasta cien mil pesos."):
        name, combined = apply_portal(offer, text)
        assert name != "portal_cumple" and combined.outcome != "cumple", text
        assert combined.doubt == "falta_coincidencia", text


@pytest.mark.decision_literal
def test_a_tax_rate_is_not_a_fact_the_portal_confirms(offer, procedure, portal):
    """REQ-103, T-240 (D-240-2): «el IVA se calculará al 21 %» fija una alícuota que el Portal no
    informa: aunque el precio esté cargado, nunca «cumple»."""
    quoted_lines(offer, procedure, portal, numbers=(1,))
    for text in ("En la cotización el IVA se calculará al 21 %.",
                 "La cotización del renglón incluirá el impuesto al valor agregado, con alícuota general."):
        name, combined = apply_portal(offer, text, items=[1])
        assert name != "portal_cumple" and combined.outcome != "cumple", text


GUARANTEE_BASE = "Constituir una garantía de mantenimiento de la oferta"
PROBES = [
    # (texto, resultado esperado de la regla: cumple / no_cumple / sin_cumple)
    (f"{GUARANTEE_BASE} del 5 % del total cotizado.", "cumple"),
    (f"{GUARANTEE_BASE} del 5 % del monto total ofertado.", "cumple"),
    (f"{GUARANTEE_BASE} del 5 % del valor total de la oferta.", "cumple"),
    (f"{GUARANTEE_BASE} del 5 % del importe total de la oferta.", "cumple"),
    (f"{GUARANTEE_BASE} del 5 % del total cotizado. Se presentará en la plataforma de compras.",
     "cumple"),
    ("Indicar el precio total de la oferta.", "cumple"),
    (f"{GUARANTEE_BASE} por $ 21.750,00.", "no_cumple"),   # el Portal informa 21.749
    ("El CUIT del oferente deberá ser 20-22222222-2.", "no_cumple"),
    (f"{GUARANTEE_BASE} del 5 % del presupuesto oficial.", "sin_cumple"),
    (f"{GUARANTEE_BASE} del 5 % del presupuesto oficial del renglón.", "sin_cumple"),
    (f"{GUARANTEE_BASE} del 5 % de la oferta de mayor monto.", "sin_cumple"),
    (f"{GUARANTEE_BASE} de como mínimo el 5 % del total cotizado.", "sin_cumple"),
    (f"{GUARANTEE_BASE} de al menos el 5 % del total cotizado.", "sin_cumple"),
    (f"{GUARANTEE_BASE} que no podrá superar el 5 % del total cotizado.", "sin_cumple"),
    (f"{GUARANTEE_BASE} hasta $ 25.000,00.", "sin_cumple"),
    (f"{GUARANTEE_BASE} del 5 % del monto adjudicado.", "sin_cumple"),
    (f"{GUARANTEE_BASE} en un importe superior a pesos veinte mil.", "sin_cumple"),
]


@pytest.mark.decision_literal
@pytest.mark.parametrize("text, want", PROBES)
def test_the_17_probes_of_d_233_1_still_give_no_cumple_without_support(offer, portal, text, want):
    """REQ-103, D-233-1, T-240 (D-240-2): las 17 sondas de la verificación de T-233 (tope, mínimo,
    base distinta del total cotizado, monto adjudicado, CUIT distinto, monto distinto) siguen sin dar
    «cumple» donde el pliego fija algo que el Portal no confirma, y dan «cumple» solo cuando coincide."""
    portal_data(portal, offer, amount="21749.00" if "21.750,00" in text else "21750.00",
                total="435000.00", cuit="30-11111111-1")
    name, combined = apply_portal(offer, text)
    if want == "cumple":
        assert name == "portal_cumple" and combined.outcome == "cumple"
    elif want == "no_cumple":
        assert name == "portal_no_cumple" and combined.outcome == "no_cumple"
    else:
        assert name != "portal_cumple" and combined.outcome != "cumple", (name, combined.outcome)
