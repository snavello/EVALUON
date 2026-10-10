"""T-235 (REQ-103, REQ-104, REQ-105; plan 015, "Flujo de IA"; ADR-0053, punto 4 bis): el Portal le
llega al modelo como bloque citable `[P…]`, el contraste recibe la oración y su contexto, el
requisito llega con su punto completo y las preguntas a la Comisión las arma el código. Datos
inventados (P4); el modelo es un guion y no hay red."""

from types import SimpleNamespace

import pytest

from evaluon.assessment import citations, combine, documents, grounds, portal_block, prompting
from tests.assessment.fakes import model, says  # noqa: F401 - `model` es una fixture
from tests.assessment.test_evaluate import (
    DECLARATION,
    number_of,
    offer_cites,
    results_of,
    run_all,
)
from tests.assessment.test_ordering import portal  # noqa: F401 - `portal` es fixture
from tests.assessment.test_portal_facts import portal_data
from tests.offers.conftest import make_offer

pytestmark = pytest.mark.django_db


# --- El bloque del Portal -------------------------------------------------------------------------


def test_the_block_lists_the_portal_data_of_the_offer_with_aliases(offer, portal):
    """REQ-103, ADR-0053 (4 bis): el bloque trae el total y la moneda, las garantías y los precios
    por renglón de esa oferta, cada uno con su alias `P…`."""
    portal_data(portal, offer, amount="21750.00", total="435000.00")
    text, aliased = portal_block.build(offer)
    assert list(aliased) == ["P1", "P2"]
    assert "[P1]\nTotal de la oferta: 435000.00 ARS" in text
    assert "[P2]\nGarantía: tipo Garantía de mantenimiento de oferta" in text
    assert "monto 21750.00" in text and "[/P2]" in text
    assert aliased["P1"].citation()["kind"] == "total"


def test_without_portal_data_there_is_no_block(offer):
    """REQ-103: sin datos del Portal para la oferta, el pedido no lleva bloque."""
    assert portal_block.build(offer) == ("", {})


def test_the_request_carries_the_block_before_the_requirement_and_the_schema_allows_the_alias():
    """REQ-103: el bloque va después de los documentos y antes del requisito; el esquema acepta
    el alias `P…` en las citas y no en `datos`."""
    messages = prompting.build_evaluation_messages(
        "sistema", "DOCS", "", "", "REQUISITO", portal_text="PORTAL")
    user = messages[-1]["content"]
    assert user.index("DOCS") < user.index("PORTAL") < user.index("REQUISITO")
    schema = prompting.evaluation_schema(["D1"], [], ["P1"])
    cited = schema["properties"]["citas"]["items"]["properties"]["documento"]["enum"]
    assert cited == ["D1", "P1"]
    assert schema["properties"]["datos"]["items"]["properties"]["documento"]["enum"] == ["D1"]


def test_the_model_sees_the_block_and_a_portal_citation_is_written_by_the_system(
        offer, operator_user, procedure, model, portal):
    """REQ-103, P3: el modelo cita el dato del Portal por su alias; la cita guardada es de clase
    Portal y su texto sale de las columnas, no de lo que escribió el modelo."""
    portal_data(portal, offer, total="435000.00")
    model.evaluates(lambda call: says("cumple", ("P1", "texto inventado por el modelo"))
                    if "declaración jurada" in call.requirement else None)
    _, runs = run_all(operator_user, procedure)
    sent = next(c for c in model.calls if "declaración jurada" in c.requirement)
    user = sent.messages[-1]["content"]
    assert "[P1]\nTotal de la oferta: 435000.00 ARS" in user
    assert user.index("[P1]") < user.index("Requisito del pliego")
    result = results_of(runs[0])[number_of(procedure, "declaración jurada")]
    assert result.outcome == "cumple"       # una cita del Portal alcanza como fundamento
    cite = result.citations.get(kind="portal")
    assert cite.text == "Total de la oferta: 435000.00 ARS" and cite.portal_kind == "total"
    assert "inventado" not in cite.text
    assert not offer_cites(result)


def test_an_unknown_portal_alias_is_dropped_like_any_other(
        offer, operator_user, procedure, model, portal):
    """REQ-103: un alias `P…` que no existe se descarta con la anomalía; sin otra cita, no hay
    conclusión."""
    portal_data(portal, offer)
    model.evaluates(lambda call: says("cumple", ("P99", "x"))
                    if "declaración jurada" in call.requirement else None)
    _, runs = run_all(operator_user, procedure)
    result = results_of(runs[0])[number_of(procedure, "declaración jurada")]
    assert result.outcome == "no_determinado" and result.doubt == "sin_cita"
    assert any(a["type"] == "alias_inexistente" and a["alias"] == "P99"
               for a in runs[0].anomalies)


# --- Oración completa y contexto ----------------------------------------------------------------


@pytest.fixture
def sentences(procedure, operator_user, fake_ai):
    offer = make_offer(procedure, operator_user, "Oferente con tres oraciones", {
        "oferta.pdf": ["Nota previa del oferente sobre el trámite. "
                       f"{DECLARATION} y acepto el pliego. Nota posterior sobre el domicilio."]})
    return offer, documents.build_offer_text(offer)


def test_the_citation_is_the_whole_sentence_and_keeps_the_models_fragment(sentences):
    """REQ-104: con `expand`, la cita es la oración entera (recorte contiguo del canónico) y el
    fragmento del modelo queda registrado con sus posiciones."""
    _, text = sentences
    doc = text.documents[0]
    found = citations.locate_quote(doc, "me encuentro habilitado para contratar",
                                   citations.PageFinder(), expand=True)
    canonical = doc.reading.canonical_text
    assert found.text == f"{DECLARATION} y acepto el pliego."
    assert found.text == canonical[found.char_start:found.char_end]
    assert canonical[found.fragment_start:found.fragment_end] == (
        "me encuentro habilitado para contratar")
    assert found.char_start <= found.fragment_start < found.fragment_end <= found.char_end


def test_without_expand_the_citation_is_the_fragment(sentences):
    """El valor por omisión no amplía (el informe técnico y los `datos` necesitan el fragmento)."""
    _, text = sentences
    found = citations.locate_quote(text.documents[0], "me encuentro habilitado",
                                   citations.PageFinder())
    assert found.text == "me encuentro habilitado"


def test_two_fragments_of_one_sentence_are_one_citation(sentences):
    """REQ-104: dos fragmentos de la misma oración dan una sola cita."""
    _, text = sentences
    finder, anomalies = citations.PageFinder(), []
    first = citations.locate_quote(text.documents[0], "bajo juramento", finder, anomalies=anomalies,
                                   expand=True)
    again = citations.locate_quote(text.documents[0], "acepto el pliego", finder,
                                   {first.span}, anomalies, expand=True)
    assert again is None and anomalies[-1]["type"] == citations.ANOMALY_REPEATED


def test_a_sentence_over_the_limit_keeps_the_fragment_with_the_anomaly(sentences, settings):
    """REQ-104: si la oración supera el tope de caracteres, queda el fragmento y la anomalía."""
    _, text = sentences
    settings.ASSESSMENT_CITATION_MAX_CHARS = 60
    anomalies = []
    found = citations.locate_quote(text.documents[0], "me encuentro habilitado",
                                   citations.PageFinder(), anomalies=anomalies, expand=True)
    assert found.text == "me encuentro habilitado"
    assert anomalies[0]["type"] == citations.ANOMALY_WIDE_SENTENCE


def test_the_context_is_the_neighbor_sentences_of_the_same_page(sentences):
    """REQ-104: el contexto de la cita son las oraciones vecinas de la misma página, con tope."""
    _, text = sentences
    finder = citations.PageFinder()
    found = citations.locate_quote(text.documents[0], "acepto el pliego", finder, expand=True)
    before, after = citations.context_of(found, finder)
    assert before == "Nota previa del oferente sobre el trámite."
    assert after == "Nota posterior sobre el domicilio."
    before, after = citations.context_of(found, finder, max_chars=20)
    assert len(before) <= 11 and len(after) <= 11


def test_the_contrast_receives_the_sentence_and_its_context(
        procedure, operator_user, model, sentences):
    """REQ-104: el pedido del contraste lleva la oración completa, su contexto y se registra el
    tope del contexto en el pedido guardado."""
    model.evaluates(lambda call: says("cumple", call.quote("me encuentro habilitado para contratar"))
                    if "declaración jurada" in call.requirement else None)
    _, runs = run_all(operator_user, procedure)
    sent = model.contrast_calls[0].user
    assert f"«{DECLARATION} y acepto el pliego.»" in sent
    assert "Nota previa del oferente sobre el trámite." in sent
    assert "Nota posterior sobre el domicilio." in sent
    step = runs[0].steps.filter(purpose="contraste").get()
    assert step.parsed["contexto_max_caracteres"] == citations.CONTEXT_MAX_CHARS
    assert len(step.parsed["contexto"]) == 1
    group = runs[0].steps.filter(purpose="grupo", requirement__number=number_of(
        procedure, "declaración jurada")).get()
    cited = group.parsed["citas_ubicadas"][0]
    assert cited["fragmento_inicio"] >= cited["inicio"] and cited["fragmento_fin"] <= cited["fin"]


def test_the_contrast_message_has_the_portal_citation_when_there_is_one():
    """REQ-104: si hay una cita del Portal, el contraste la ve."""
    messages = prompting.build_contrast_messages(
        "sistema", "REQ", "cumple", [("a.pdf", 1, "La oración.", "antes: «Otra.»")],
        portal_cites=["Total de la oferta: 5 ARS"])
    user = messages[-1]["content"]
    assert "a.pdf, página 1: «La oración.»" in user and "antes: «Otra.»" in user
    assert "Datos del Portal citados" in user and "Total de la oferta: 5 ARS" in user


# --- El requisito con su punto ------------------------------------------------------------------


def _quote(cited, segment_text, start):
    segment = SimpleNamespace(text=segment_text, char_start=100, label="", path="")
    return SimpleNamespace(text=cited, char_start=100 + start, char_end=100 + start + len(cited),
                           segment=segment, scope="", pk=1)


def test_the_requirement_arrives_with_its_whole_point_and_the_cited_sentence_marked():
    """REQ-104: el requisito llega con el punto completo y la oración citada entre `<<< >>>`."""
    point = "Garantías. Constituir la garantía del cinco por ciento. Se aceptan pólizas."
    cited = "Constituir la garantía del cinco por ciento."
    quote = grounds.QuoteText(_quote(cited, point, point.index(cited)), text=cited)
    assert quote.marked_point() == (
        "Garantías. <<<Constituir la garantía del cinco por ciento.>>> Se aceptan pólizas.")
    requirement = SimpleNamespace(category="formal", number=3, items=[])
    rendered = grounds.RequirementText(requirement=requirement, quotes=[quote]).render()
    assert "<<<Constituir la garantía del cinco por ciento.>>>" in rendered
    assert "punto completo del pliego" in rendered


def test_a_point_that_is_only_the_citation_or_a_modified_text_has_no_markers():
    """REQ-104: si el punto es la cita misma, o una circular cambió el texto, no hay marcas."""
    cited = "Presentar la declaración jurada."
    same = grounds.QuoteText(_quote(cited, cited, 0), text=cited)
    assert same.marked_point() is None
    changed = grounds.QuoteText(_quote(cited, "Antes. " + cited, 7), text="Otro texto.",
                                original=cited)
    assert changed.marked_point() is None


def test_a_long_point_is_cut_without_cutting_the_citation(settings):
    """REQ-104: un punto largo se recorta alrededor de la cita, con su tope."""
    cited = "La oración citada."
    point = "a" * 3000 + " " + cited + " " + "b" * 3000
    quote = grounds.QuoteText(_quote(cited, point, point.index(cited)), text=cited)
    marked = quote.marked_point()
    assert f"<<<{cited}>>>" in marked and len(marked) <= grounds.POINT_MAX_CHARS + 40


# --- Las preguntas a la Comisión ----------------------------------------------------------------


def undetermined(**kwargs):
    base = dict(outcome="no_determinado", doubt="sin_dato", ask=True, explanation="Falta el plazo.")
    return combine.Combined(**{**base, **kwargs})


@pytest.mark.parametrize("asked", [
    "¿Podría el oferente aclarar el plazo de entrega?",
    "Solicitamos al oferente que informe el plazo.",
    "El oferente deberá informar el plazo de mantenimiento.",
    "Por favor, indique usted el plazo.",
    "Se solicita al proveedor la constancia.",
])
def test_a_question_addressed_to_the_offeror_is_rejected(asked):
    """REQ-105: una pregunta dirigida al oferente se rechaza (T-229: 3 de las 17)."""
    assert combine.addresses_offeror(asked)
    final = combine.compose_question(5, "Mantener la oferta por sesenta días.",
                                     undetermined(question=asked))
    assert asked not in final and "Comisión" in final.splitlines()[-1]


@pytest.mark.parametrize("asked", [
    "¿Desde cuándo corre el plazo de sesenta días?",
    "¿La Comisión acepta la póliza presentada por el oferente?",
    "¿El oferente presentó la garantía en el Portal?",
])
def test_a_question_to_the_commission_is_kept_with_the_information_in_front(asked):
    """REQ-105: la pregunta del modelo dirigida a la Comisión se acepta y se le antepone el
    requisito, la conclusión y el texto."""
    assert not combine.addresses_offeror(asked)
    final = combine.compose_question(5, "Mantener la oferta por sesenta días.",
                                     undetermined(question=asked))
    lines = final.splitlines()
    assert lines[0].startswith("Requisito 5: «Mantener la oferta por sesenta días.»")
    assert lines[1].startswith("Conclusión del sistema:") and "falta un dato" in lines[1]
    assert lines[2].startswith("Texto de la oferta:") and lines[-1] == asked


def test_every_question_names_the_requirement_the_conclusion_and_the_text():
    """REQ-105: ninguna pregunta es un texto fijo sin datos: cada una dice qué requisito, qué
    conclusión y qué texto la motivan, con documento y página cuando hay cita."""
    cite = SimpleNamespace(text="Declaro bajo juramento algo.", page=3,
                           document=SimpleNamespace(title="oferta.pdf"))
    for combined in (
            undetermined(doubt="sin_corroborar", proposed="cumple", citations=[cite]),
            undetermined(doubt="lectura_incompleta"), undetermined(doubt="sin_dato"),
            undetermined(doubt="duda", ask=False, question="¿Cuál rige?")):
        final = combine.compose_question(9, "Presentar el pagaré.", combined,
                                         documents=["oferta.pdf"],
                                         unread=[{"title": "oferta.pdf", "page": 2}])
        lines = final.splitlines()
        assert len(lines) == 4
        assert "Requisito 9" in lines[0] and "Conclusión del sistema:" in lines[1]
        assert "Texto de la oferta:" in lines[2] and not combine.addresses_offeror(final)
    corroborated = combine.compose_question(
        9, "Presentar el pagaré.",
        undetermined(doubt="sin_corroborar", proposed="cumple", citations=[cite]))
    assert "(oferta.pdf, página 3)" in corroborated and "«cumple»" in corroborated


def test_no_question_without_a_reason_to_ask():
    """REQ-105: lo que no es "no determinado", lo externo y la duda sin pregunta no preguntan."""
    assert combine.compose_question(1, "x", combine.Combined(outcome="cumple", question="¿?")) == ""
    assert combine.compose_question(1, "x", undetermined(doubt="externo")) == ""
    assert combine.compose_question(1, "x", undetermined(doubt="duda", ask=False)) == ""


def test_the_generic_fixed_questions_are_gone():
    """REQ-105: el texto fijo genérico se eliminó."""
    assert not hasattr(combine, "fixed_question")
