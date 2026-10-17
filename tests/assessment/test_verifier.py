"""Verificador externo de citas (T-299; REQ-121, REQ-122, REQ-124; plan 016, «Paso 4 · Verificador
externo de citas»; ADR-0065 a ADR-0068).

Con el caso chico, el doble del motor local (`model`) y el doble del cliente externo
(`fake_external`): ninguna llamada real al proveedor. Comprueba qué celdas se mandan y cuáles no
(una por cada exclusión), que `si` deja la celda, que `no` y `parcial` la pasan a «no determinado»
`sin_corroborar` con las mismas citas y la pregunta en forma, que una pregunta al oferente se
reemplaza, que un «no determinado» nunca pasa a «cumple», que una respuesta inválida, un pedido
vencido o con error, un bloqueo y el tope dejan la celda con la anomalía, que con la hoja de
compliance inventada cargada ningún pedido lleva su texto, que con el uso apagado la evaluación es la
de siempre, la pasada sobre una evaluación guardada (`medir_evaluacion --verificador-sobre`) con el
«sin» y el «con», y la clave `externo` con la línea «Etapas fuera del equipo». Textos inventados (P4).
"""

import json
import re
from decimal import Decimal
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from django.core.management import call_command

from evaluon.accounts import permissions
from evaluon.ai.external import guard
from evaluon.assessment import combine, externals, grounds
from evaluon.assessment import evaluation as ev
from evaluon.assessment import models as am
from evaluon.assessment import verifier
from evaluon.assessment.services import evaluate, external_stages
from evaluon.audit.models import AuditEvent, EventType
from evaluon.offers import models as om
from tests.assessment.fakes import CASO_CHICO, model, says  # noqa: F401 - fixture del motor local
from tests.assessment.test_evaluate import requirement_of, results_of, run_all
from tests.assessment.test_evaluation import LIST, load_small_case_portal, oracle_for
from tests.offers.conftest import make_offer

pytestmark = pytest.mark.django_db

SHEET = Path(__file__).resolve().parent.parent / "ai" / "data" / "compliance-inventada" / "hoja.txt"
KEYWORD = "ZORVANTIQ"
TRUTH = CASO_CHICO / "verdad-celdas.yaml"

DECLARATION = "Declaro bajo juramento que me encuentro habilitado para contratar."
PRICES = "Los precios se cotizan en pesos con impuestos incluidos."
REGISTRY = "Constancia de inscripción en el registro de proveedores, número 000123."
LOCAL_REASONING = "Razonamiento sintético del doble local, que no debe salir."
LOCAL_EXPLANATION = "Explicación sintética del doble local, que no debe salir."

SI = json.dumps({"razonamiento": "La cita lo muestra.", "sostiene": "si", "falta": ""})


def sheet_paragraphs():
    text = SHEET.read_text(encoding="utf-8").replace("\r\n", "\n")
    return [part.strip() for part in text.split("\n\n") if part.strip()]


def cumple(call, text):
    """«cumple» con la cita `text` si está en el grupo; si no, «no consta» (la respuesta por
    omisión del doble)."""
    found = call.quote(text)
    if found is None:
        return None
    return says("cumple", found, reasoning=LOCAL_REASONING, explanation=LOCAL_EXPLANATION)


def local_script(call):
    """El motor local: «cumple» con cita en la declaración, el registro y la moneda; «no
    determinado» en la garantía; el resto «no consta»."""
    if "declaración jurada" in call.requirement:
        return cumple(call, DECLARATION)
    if "registro de proveedores" in call.requirement:
        return cumple(call, REGISTRY)
    if "Cotizar en pesos" in call.requirement:
        return cumple(call, PRICES)
    if "garantía de mantenimiento" in call.requirement:
        return says("no_determinado", explanation="El modelo duda.", reasoning=LOCAL_REASONING)
    return None


def answer(sostiene, missing="", reasoning="Lo que dice la cita."):
    return json.dumps({"razonamiento": reasoning, "sostiene": sostiene, "falta": missing})


# Lo que falta, como lo diría el verificador (T-302, D-301-4): una frase corta, sin repetir el
# requisito ni la cita.
MISSING_PRICE = "el precio unitario de cada renglón"
TO_OFFEROR = "que el oferente acompañe la constancia completa del registro"


def external_requests():
    return list(AuditEvent.objects.filter(event_type=EventType.EXTERNAL_REQUEST)
                .exclude(detail__resultado="en_vuelo").order_by("pk"))


def payload_text(payload):
    return payload.system + "\n" + "\n".join(text for _, text in payload.messages)


@pytest.fixture
def numbers(procedure):
    return {name: requirement_of(procedure, needle) for name, needle in (
        ("declaracion", "declaración jurada"), ("registro", "registro de proveedores"),
        ("moneda", "Cotizar en pesos"), ("garantia", "garantía de mantenimiento"))}


# --- Qué celdas se mandan ----------------------------------------------------------------------


def _located(document_id, text="Texto citado."):
    return SimpleNamespace(document=SimpleNamespace(pk=document_id, title="doc.pdf"), page=1,
                           text=text, reading=None, char_start=0, char_end=len(text))


def _cell(outcome=combine.OUT_CUMPLE, *, facts=None, citations=None, portal=(), flagged=False,
          group=(1,), text="Presentar la nota firmada por el oferente."):
    citations = [_located(1)] if citations is None else citations
    combined = combine.Combined(outcome=outcome, doubt="duda" if outcome == "no_determinado"
                                else "", citations=citations, portal=list(portal),
                                facts=facts or {}, explanation="Explicación.")
    requirement = SimpleNamespace(pk=1, number=7)
    quotes = [SimpleNamespace(text=text)]
    return verifier.Cell(requirement=requirement,
                         text=SimpleNamespace(context=text, text=text, quotes=quotes),
                         combined=combined, external_flagged=flagged, group_documents=group)


PORTAL = [{"item": 1, "kind": "total", "text": "Total de la oferta: $ 535.000", "label": "x"}]


@pytest.mark.parametrize("cell, reason", [
    (_cell(), None),
    (_cell(combine.OUT_NO_CUMPLE), None),
    (_cell(facts={"regla": "portal_cumple"}, citations=[], portal=PORTAL), None),
    (_cell(combine.OUT_NO_CUMPLE, facts={"regla": "portal_no_cumple"}, citations=[],
           portal=PORTAL), None),
    (_cell(facts={"regla": "portal_cita_agregada"}, portal=PORTAL), None),
    (_cell(combine.OUT_NO_DETERMINADO), verifier.SKIP_OUTCOME),
    (_cell(combine.OUT_SIN_DOCUMENTO), verifier.SKIP_OUTCOME),
    (_cell(facts={"regla": "cumple_por_ausencia", "criterios": [{"nombre": "x"}]}),
     verifier.SKIP_RULE),
    (_cell(combine.OUT_NO_CUMPLE, facts={"regla": "presentacion_fisica_no_consta"}),
     verifier.SKIP_RULE),
    (_cell(facts={"regla": "forma_garantia_no_elegida", "aplica": False}), verifier.SKIP_RULE),
    (_cell(facts={"regla": "ok_informe_tecnico", "technical_ok": 1}), verifier.SKIP_RULE),
    (_cell(facts={"regla": "portal_cumple", "criterios": [{"nombre": "iva_precio_final_portal"}]},
           citations=[], portal=PORTAL), verifier.SKIP_CRITERION),
    (_cell(citations=[]), verifier.SKIP_NO_CITATION),
    (_cell(flagged=True), verifier.SKIP_EXTERNAL),
    (_cell(text="La Comisión verificará la habilidad para contratar del oferente."),
     verifier.SKIP_EXTERNAL),
    (_cell(group=(1, 9)), verifier.SKIP_COMPLIANCE),
    (_cell(group=(), citations=[_located(9)]), verifier.SKIP_COMPLIANCE),
], ids=["cumple", "no_cumple", "portal_cumple", "portal_no_cumple", "portal_cita_agregada",
        "no_determinado", "sin_documento", "ausencia", "presentacion_fisica", "forma_garantia",
        "informe_tecnico", "iva", "sin_cita", "marca_externo", "catalogo_externo",
        "compliance_en_el_grupo", "compliance_en_la_cita"])
def test_only_conclusions_backed_by_a_citation_are_sent(cell, reason):
    """REQ-124, REQ-121 (P9): van las «cumple» y «no cumple» que se apoyan en una oración citada o
    en un dato del Portal (sin regla, `portal_cumple`, `portal_no_cumple`, la cita del Portal
    agregada); no van las demás reglas (ausencia, presentación física, forma de garantía, informe
    técnico), el criterio del IVA, lo que no concluye, una conclusión sin cita, un requisito
    externo (marca del modelo o catálogo) ni una celda con un documento `compliance` (el 9)."""
    assert verifier.skip_reason(cell, reserved={9}) == reason


# --- Evaluación con el verificador -------------------------------------------------------------


def evaluate_with_verifier(operator_user, procedure, model, fake_external, replies=None,
                           default=SI):
    fake_external.enable(verifier.STAGE)
    fake_external.respond(default)
    for custom_id, text in (replies or {}).items():
        fake_external.respond(text, custom_id)
    model.evaluates(local_script)
    _, runs = run_all(operator_user, procedure)
    return runs[0]


def test_si_keeps_the_cell_and_no_or_parcial_turn_it_undetermined_with_its_question(
        offer, operator_user, procedure, model, fake_external, numbers):
    """REQ-124 (y REQ-105): un pedido por celda con cita, los de la oferta en un lote. `si` deja el
    «cumple»; `no` lo pasa a «no determinado» `sin_corroborar` con las mismas citas y la pregunta
    que arma el código con lo que falta según el verificador (tiene la forma de REQ-105);
    `parcial` con un faltante dirigido al oferente la pasa igual, con lo que razonó el
    verificador. El «no determinado» no se manda y queda."""
    moneda = numbers["moneda"]
    run = evaluate_with_verifier(operator_user, procedure, model, fake_external, {
        verifier.custom_id_of(offer, moneda): answer("no", MISSING_PRICE),
        verifier.custom_id_of(offer, numbers["registro"]): answer("parcial", TO_OFFEROR)})

    # Lo que salió: un lote con las tres conclusiones con cita, ninguna otra celda.
    assert len(fake_external.batches) == 1
    sent = {p.custom_id: p for p in fake_external.batches[0]}
    assert set(sent) == {verifier.custom_id_of(offer, numbers[n])
                         for n in ("declaracion", "registro", "moneda")}
    results = results_of(run)
    declaration = results[numbers["declaracion"].number]
    assert declaration.outcome == "cumple"
    assert declaration.facts["verificador"]["respuesta"] == "si"
    assert declaration.facts["verificador"]["despues"] == {"resultado": "cumple", "motivo": ""}

    changed = results[moneda.number]
    assert (changed.outcome, changed.doubt) == ("no_determinado", "sin_corroborar")
    mark = changed.facts["verificador"]
    assert mark["antes"] == {"resultado": "cumple", "motivo": ""}
    assert mark["despues"] == {"resultado": "no_determinado", "motivo": "sin_corroborar"}
    assert mark["respuesta"] == "no" and mark["falta_usada"] is True
    assert AuditEvent.objects.get(pk=mark["hecho"]).detail["resultado"] == "ok"
    # Las mismas citas: la de la oferta y la del pliego, ninguna nueva.
    cites = list(changed.citations.order_by("order").values_list("kind", "text"))
    assert [t for k, t in cites if k == "oferta"] == [PRICES]
    assert {k for k, _ in cites} == {"oferta", "pliego"}
    question = am.Question.objects.get(result=changed).text
    assert f"Lo que no consta en el texto citado: {MISSING_PRICE}." in question
    # O-299-1: la pregunta dice que quien no lo corroboró fue el verificador, no el contraste.
    assert "pero el verificador externo no lo corroboró" in question
    assert "el contraste no lo corroboró" not in question
    form = ev.question_records(run)
    assert all(q["conforme"] for q in form if q["fila"] in (moneda.number,
                                                             numbers["registro"].number))

    registry = results[numbers["registro"].number]
    assert (registry.outcome, registry.doubt) == ("no_determinado", "sin_corroborar")
    assert registry.facts["verificador"]["falta_usada"] is False
    question = am.Question.objects.get(result=registry).text
    assert TO_OFFEROR not in question and "¿La Comisión confirma, corrige o rechaza" in question
    assert "Lo que observó el verificador: Lo que dice la cita." in question

    guarantee = results[numbers["garantia"].number]
    assert guarantee.outcome == "no_determinado" and "verificador" not in guarantee.facts


def test_a_question_out_of_form_is_replaced_by_one_that_says_what_is_missing(
        offer, operator_user, procedure, model, fake_external, numbers):
    """REQ-105, REQ-124 (T-302, D-301-3; T-301: O3 R62 y O1 R124): si lo que falta según el
    verificador no sirve para la pregunta (le pide algo al oferente o no hay), la que arma el código
    lleva lo que razonó el verificador, completo, y sigue en forma con el requisito, la conclusión
    y el texto."""
    missing = {
        "moneda": ("La cita muestra el total de la oferta en pesos, que es el dato de la cotización, "
                   "pero el requisito pide además el precio unitario de cada renglón y ese dato no "
                   "figura en el texto citado ni en su contexto de la página."),
        "registro": ("La constancia citada muestra el número de inscripción en el registro, pero "
                     "el requisito pide también que esté vigente y el texto citado no trae la fecha "
                     "de vigencia de la inscripción ni de su última renovación.")}
    run = evaluate_with_verifier(operator_user, procedure, model, fake_external, {
        verifier.custom_id_of(offer, numbers["moneda"]):
            answer("parcial", TO_OFFEROR, reasoning=missing["moneda"]),
        verifier.custom_id_of(offer, numbers["registro"]):
            answer("parcial", "", reasoning=missing["registro"])})
    forms = {q["fila"]: q for q in ev.question_records(run)}
    for name, text in missing.items():
        number = numbers[name].number
        result = results_of(run)[number]
        assert result.facts["verificador"]["falta_usada"] is False
        question = am.Question.objects.get(result=result).text
        assert text in question
        assert TO_OFFEROR not in question
        assert forms[number]["conforme"] is True


def test_the_question_has_the_requirement_the_conclusion_and_the_text_once_and_what_is_missing(
        offer, operator_user, procedure, model, fake_external, numbers):
    """REQ-105, REQ-124 (T-302, D-301-4; T-301: las 6 preguntas del verificador repetían lo que el
    código ya pone): el verificador devuelve solo qué falta y el código arma siempre la pregunta;
    la guardada tiene una sola vez el requisito, la conclusión y el texto de la oferta, y cierra con
    lo que falta, en forma y dirigida a la Comisión."""
    moneda = numbers["moneda"]
    run = evaluate_with_verifier(operator_user, procedure, model, fake_external, {
        verifier.custom_id_of(offer, moneda): answer("parcial", MISSING_PRICE)})
    result = results_of(run)[moneda.number]
    question = am.Question.objects.get(result=result).text
    assert question.count("Cotizar en pesos con impuestos incluidos") == 1
    assert question.count("Conclusión del sistema:") == 1
    assert question.count("el sistema propuso «cumple»") == 1
    assert question.count(PRICES) == 1
    assert question.endswith(f"Lo que no consta en el texto citado: {MISSING_PRICE}.")
    assert len(question.splitlines()) == 4
    (form,) = [q for q in ev.question_records(run) if q["fila"] == moneda.number]
    assert form["conforme"] is True and form["nombra_comision"] is True


def test_what_is_sent_is_what_the_contrast_sees_and_nothing_of_the_local_reasoning(
        offer, operator_user, procedure, model, fake_external, numbers):
    """REQ-121, REQ-124 (plan, «Qué se manda»): el pedido lleva el requisito con su punto, la
    conclusión, la oración citada con su documento y su página, con la instrucción
    `verificador-v2`, esfuerzo `low`, pensamiento `between_tools` y el esquema de la salida; no
    lleva el razonamiento ni la explicación del modelo local. Cada pieza entra con su origen."""
    evaluate_with_verifier(operator_user, procedure, model, fake_external)
    payload = next(p for p in fake_external.batches[0]
                   if p.custom_id == verifier.custom_id_of(offer, numbers["moneda"]))
    text = payload_text(payload)
    assert verifier.load_instruction().text == payload.system
    assert "Conclusión propuesta: cumple" in text
    assert f"oferta.pdf, página 2: «{PRICES}»" in text
    assert "Cotizar en pesos con impuestos incluidos" in text
    assert LOCAL_REASONING not in text and LOCAL_EXPLANATION not in text
    params = payload.to_params()
    assert params["output_config"]["effort"] == "low"
    assert params["thinking"] == {"type": "between_tools"}
    assert params["max_tokens"] == verifier.MAX_TOKENS
    assert params["output_config"]["format"]["schema"] == verifier.OUTPUT_SCHEMA
    event = next(e for e in external_requests() if e.detail["custom_id"] == payload.custom_id)
    assert event.detail["instruccion"]["version"] == "verificador-v2"
    assert event.detail["filtro"]["piezas"]["requisito"] == 1
    assert event.detail["filtro"]["piezas"]["oferta"] >= 1
    assert "respuesta_comision" not in event.detail["filtro"]["piezas"]


def test_the_run_records_the_external_key_and_the_screen_line(
        offer, operator_user, procedure, model, fake_external, numbers):
    """REQ-122 (P6; contrato de T-300): la corrida guarda la clave `externo` en `models_used`,
    `parameters`, `prompt_versions` y `counts`, con la entrada propia del verificador; la línea
    «Etapas fuera del equipo» la muestra sin cambios."""
    run = evaluate_with_verifier(operator_user, procedure, model, fake_external, {
        verifier.custom_id_of(offer, numbers["moneda"]): answer("no")})
    externo = run.models_used["externo"]
    assert externo["etapas"] == {"matriz": "local", "verificador": "externo"}
    assert externo["verificador"] == {"proveedor": "anthropic", "modelo": "claude-sonnet-5-5"}
    own = run.parameters["externo"]["verificador"]
    assert own["modo"] == "lotes" and own["effort"] == "low" and own["lote_id"]
    assert run.prompt_versions["externo"]["verificador"] == "verificador-v2"
    counts = run.counts["externo"]["verificador"]
    assert counts["pedidos"] == 3 and counts["enviadas"] == 3
    assert counts["sostiene"] == {"si": 2, "no": 1, "parcial": 0}
    assert counts["a_no_determinado"] == 1 and counts["no_enviadas"]["no_concluye"] >= 1
    assert external_stages.line([run]) == (
        "Etapas fuera del equipo: verificador de citas (anthropic, claude-sonnet-5-5, modo "
        "lotes, 3 pedidos).")


# --- Solo resta ----------------------------------------------------------------------------------


@pytest.mark.parametrize("given", ["si", "no", "parcial", None])
def test_an_undetermined_cell_never_becomes_cumple(given):
    """REQ-124 (P3): `decide` nunca pasa un «no determinado» a «cumple», ni cambia su motivo, con
    ninguna respuesta. Si se permitiera, esta prueba falla."""
    cell = _cell(combine.OUT_NO_DETERMINADO)
    after, _ = verifier.decide(cell, given, missing="el dato del requisito")
    assert after.outcome == combine.OUT_NO_DETERMINADO and after.doubt == "duda"
    assert after.citations == cell.combined.citations


@pytest.mark.parametrize("given", ["no", "parcial"])
def test_a_conclusion_only_goes_to_undetermined_with_the_same_citations(given):
    """REQ-124: `no` y `parcial` pasan un «cumple» o «no cumple» a «no determinado»
    `sin_corroborar`: las mismas citas y datos del Portal (el verificador no agrega nada) y lo que
    se concluyó queda en `proposed`."""
    for outcome in (combine.OUT_CUMPLE, combine.OUT_NO_CUMPLE):
        cell = _cell(outcome, portal=PORTAL)
        after, _ = verifier.decide(cell, given, reasoning="No alcanza.")
        assert (after.outcome, after.doubt) == (combine.OUT_NO_DETERMINADO,
                                                combine.UNCORROBORATED)
        assert after.citations == cell.combined.citations and after.portal == PORTAL
        assert after.proposed == outcome and "No alcanza." in after.explanation


def test_an_undetermined_cell_is_not_sent_and_stays(offer, operator_user, procedure, model,
                                                    fake_external, numbers):
    """REQ-124: aunque el verificador contestara `si` a todo, el «no determinado» de la garantía no
    se manda y queda como estaba (alteración: mandarlo y aplicar `si` haría fallar esto)."""
    run = evaluate_with_verifier(operator_user, procedure, model, fake_external)
    guarantee = results_of(run)[numbers["garantia"].number]
    assert guarantee.outcome == "no_determinado"
    assert all(p.custom_id != verifier.custom_id_of(offer, numbers["garantia"])
               for batch in fake_external.batches for p in batch)


# --- Sin respuesta: la celda queda ---------------------------------------------------------------


@pytest.mark.parametrize("failure", ["invalida", "vencido", "error", "tope"])
def test_no_valid_answer_leaves_the_cell_with_the_anomaly(offer, operator_user, procedure, model,
                                                          fake_external, numbers, settings,
                                                          failure):
    """REQ-124: una respuesta que no es el JSON pedido, un pedido vencido, uno con error o el tope
    agotado dejan cada celda como estaba (el «cumple» queda) con la anomalía
    `verificador_sin_respuesta` en la celda y en la corrida; la etapa vuelve a lo local."""
    if failure == "invalida":
        default = "Esto no es el objeto JSON pedido."
    else:
        default = answer("no")
    fake_external.enable(verifier.STAGE)
    fake_external.respond(default)
    if failure == "vencido":
        fake_external.expire()
    elif failure == "error":
        fake_external.fail()
    elif failure == "tope":
        settings.EXTERNAL_CASE_CAP_USD = Decimal("0.0000001")
    model.evaluates(local_script)
    _, runs = run_all(operator_user, procedure)
    run = runs[0]
    for name in ("declaracion", "registro", "moneda"):
        result = results_of(run)[numbers[name].number]
        assert result.outcome == "cumple", (failure, name)
        mark = result.facts["verificador"]
        assert mark["respuesta"] is None and mark["anomalia"]["type"] == verifier.ANOMALY
        assert mark["despues"] == mark["antes"]
    assert any(a.get("type") == verifier.ANOMALY for a in run.anomalies)
    assert run.models_used["externo"]["etapas"]["verificador"] == "local"
    assert run.counts["externo"]["verificador"]["sin_respuesta"] == 3


def test_a_block_of_the_guard_leaves_the_cell_with_the_anomaly(
        procedure, operator_user, model, fake_external, fake_ai, numbers):
    """REQ-121, REQ-124: una oración citada que copia un párrafo de una hoja de compliance (de otra
    oferta del procedimiento) bloquea su pedido en la puerta: no sale, queda `bloqueado` sin texto
    y la celda queda «cumple» con la anomalía."""
    sheet = sheet_paragraphs()
    make_offer(procedure, operator_user, "Oferente con la hoja", {"hoja.pdf": sheet},
               kinds={"hoja.pdf": "compliance"})
    copied = sheet[1]
    offer = make_offer(procedure, operator_user, "Oferente que copió", {
        "oferta.pdf": [DECLARATION + " " + PRICES], "nota.pdf": [copied]})
    fake_external.enable(verifier.STAGE)
    fake_external.respond(SI)

    def script(call):
        if "registro de proveedores" in call.requirement:
            return cumple(call, copied)
        if "declaración jurada" in call.requirement:
            return cumple(call, DECLARATION)
        return None

    model.evaluates(script)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    results = results_of(runs[0])
    registry = results[numbers["registro"].number]
    assert registry.outcome == "cumple"
    assert registry.facts["verificador"]["anomalia"]["motivo"] == guard.ANOMALY
    event = AuditEvent.objects.get(pk=registry.facts["verificador"]["hecho"])
    assert event.detail["resultado"] == "bloqueado" and event.detail["texto_enviado"] is None
    assert "huella_compliance" in event.detail["motivos"]
    assert results[numbers["declaracion"].number].facts["verificador"]["respuesta"] == "si"
    for payload in [p for batch in fake_external.batches for p in batch]:
        assert KEYWORD not in payload_text(payload)


# --- Lo reservado no sale (REQ-121) --------------------------------------------------------------


@pytest.fixture
def debt_in_catalog(monkeypatch):
    """El libre deuda del caso chico entra al catálogo de los externos (como en
    `tests/ai/test_external_guard.py`)."""
    extra = externals.ExternalCheck("libre_deuda", "constancia fiscal de deuda",
                                    re.compile("libre deuda"))
    monkeypatch.setattr(externals, "CATALOG", (*externals.CATALOG, extra))


def test_with_the_invented_sheet_loaded_nothing_of_it_is_sent(
        procedure, operator_user, model, fake_external, fake_ai, numbers, debt_in_catalog):
    """REQ-121 (umbral 19): con la hoja inventada cargada en una oferta y el uso externo
    encendido, las celdas de esa oferta (su grupo de lectura tiene la hoja) no se mandan, el
    requisito externo del catálogo tampoco, y ningún pedido que llega al cliente ni ningún hecho del
    registro tiene un párrafo de la hoja ni la palabra clave; las celdas de la otra oferta salen."""
    sheet = sheet_paragraphs()
    with_sheet = make_offer(procedure, operator_user, "Oferente con hoja", {
        "oferta.pdf": [DECLARATION, PRICES], "hoja.pdf": sheet,
        "deuda.pdf": ["Certificado fiscal de libre deuda vigente al día de la apertura."]},
        kinds={"hoja.pdf": "compliance"})
    plain = make_offer(procedure, operator_user, "Oferente sin hoja", {
        "oferta.pdf": [DECLARATION, PRICES]})
    fake_external.enable(verifier.STAGE)
    fake_external.respond(SI)

    def script(call):
        if "libre deuda" in call.requirement and call.alias_with("libre deuda vigente"):
            return cumple(call, "Certificado fiscal de libre deuda vigente al día de la apertura.")
        return local_script(call)

    model.evaluates(script)
    _, runs = run_all(operator_user, procedure)
    by_offer = {run.offer_id: run for run in runs}

    reached = [p for batch in fake_external.batches for p in batch]
    assert reached and all(p.offer_id == plain.pk for p in reached)
    for payload in reached:
        text = payload_text(payload)
        assert KEYWORD not in text and not any(paragraph[:60] in text for paragraph in sheet)
    for event in AuditEvent.objects.filter(event_type=EventType.EXTERNAL_REQUEST):
        assert KEYWORD not in json.dumps(event.detail, ensure_ascii=False)
    counts = by_offer[with_sheet.pk].counts["externo"]["verificador"]
    assert counts["pedidos"] == 0 and counts["enviadas"] == 0
    assert counts["no_enviadas"]["documento_compliance"] >= 2
    assert counts["no_enviadas"]["requisito_externo"] == 1
    results = results_of(by_offer[with_sheet.pk])
    debt = next(r for r in results.values() if r.requirement.quotes.filter(
        text__contains="libre deuda").exists())
    assert debt.outcome == "cumple" and "verificador" not in debt.facts


# --- Apagado: la evaluación de siempre (REQ-122) -------------------------------------------------


def _fingerprint(run):
    results = [(r.requirement.number, r.outcome, r.doubt, r.explanation, r.facts,
                list(r.citations.order_by("order").values_list("kind", "text")),
                list(am.Question.objects.filter(result=r).values_list("text", flat=True)))
               for r in run.results.select_related("requirement").order_by("requirement__number")]
    # Lo que cambia de una corrida a otra sin que cambie la evaluación: el reuso de las
    # reescrituras y el tiempo de la visión.
    counts = {k: v for k, v in run.counts.items() if k != "rewrites_reused"}
    counts["vision"] = {k: v for k, v in counts.get("vision", {}).items() if k != "seconds"}
    return (run.models_used, run.parameters, run.prompt_versions, counts, run.anomalies,
            run.documents, results)


@pytest.mark.parametrize("enabled, stage", [(False, "local"), (True, "local"),
                                            (False, "externo")])
def test_with_the_external_use_off_the_evaluation_is_the_same(
        offer, operator_user, procedure, model, fake_external, settings, monkeypatch,
        enabled, stage):
    """REQ-122 (umbral 20): con el uso externo apagado o la etapa en `local`, el verificador no
    corre: ningún pedido, ningún hecho `external_request`, ninguna clave `externo` ni
    `facts["verificador"]`, y la evaluación es igual a la de la configuración por omisión."""
    model.evaluates(local_script)
    _, (baseline,) = run_all(operator_user, procedure)
    settings.EXTERNAL_ENABLED = enabled
    settings.EXTERNAL_STAGES = {**settings.EXTERNAL_STAGES, "verificador": stage}

    def forbidden(*args, **kwargs):
        raise AssertionError("el verificador no debe correr")

    monkeypatch.setattr(verifier, "verify", forbidden)
    _, (again,) = run_all(operator_user, procedure)
    assert not fake_external.batches and not AuditEvent.objects.filter(
        event_type=EventType.EXTERNAL_REQUEST).exists()
    for column in (again.models_used, again.parameters, again.prompt_versions, again.counts):
        assert "externo" not in column
    assert all("verificador" not in r.facts for r in again.results.all())
    first, second = _fingerprint(baseline), _fingerprint(again)
    assert first[:6] == second[:6]
    # Los resultados son los mismos; las preguntas abiertas de la primera no se repiten encima.
    assert [r[:6] for r in first[6]] == [r[:6] for r in second[6]]


# --- Pasada sobre una evaluación guardada (`--verificador-sobre`) --------------------------------


def _measured_small_case(user, model_, tmp_path):
    expected = ev.load_expected(LIST)
    procedure, offers = ev.build_case(user, expected)
    load_small_case_portal(user, procedure, offers)
    raw = yaml.safe_load(LIST.read_text(encoding="utf-8"))
    model_.evaluates(oracle_for(raw))
    truth = ev.load_commission_cells(TRUTH)
    report = ev.measure(user, procedure, expected, offers, tmp_path / "local",
                        commit="abc1234", commission_cells=truth)
    return report, procedure, offers


def test_the_verifier_over_a_saved_run_gives_the_before_and_the_after(
        db, operator_user, fake_ai, model, fake_external, tmp_path, monkeypatch):
    """REQ-124 (plan, «Medición del paso 4»; umbral 17): `medir_evaluacion --verificador-sobre`
    aplica el verificador a la corrida guardada con la misma función, sin la GPU (ningún pedido
    local nuevo), guarda una evaluación derivada por oferta (las de origen no cambian) y escribe el
    «sin» (del `antes`) y el «con»: el «sin» es la exactitud de la corrida de origen; una celda
    exacta que el verificador no corrobora se informa como «no determinado» que venía de una
    exacta. Con `--medicion`, la segunda pasada reusa las respuestas por huella."""
    from tests.tenders.conftest import TEST_PASSWORD

    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    source, procedure, offers = _measured_small_case(operator_user, model, tmp_path)
    local_calls = len(model.calls) + len(model.contrast_calls)
    first = offers["Oferente A Sintético"]
    declaration = next(r for r in first.assessment_results.select_related("requirement")
                       if r.requirement.quotes.filter(text__contains="declaración jurada").exists())
    assert declaration.outcome == "cumple"
    fake_external.enable(verifier.STAGE)
    fake_external.respond(SI)
    fake_external.respond(answer("no", reasoning="La cita no alcanza."),
                          verifier.custom_id_of(first, declaration.requirement))
    before_runs = set(am.Run.objects.values_list("pk", flat=True))

    report = ev.measure_verifier(
        operator_user, procedure, ev.load_expected(LIST), offers, tmp_path / "con",
        source.folder, measurement="T-299-prueba", commit="abc1234",
        commission_cells=ev.load_commission_cells(TRUTH))

    assert len(model.calls) + len(model.contrast_calls) == local_calls
    derived = am.Run.objects.exclude(pk__in=before_runs)
    assert derived.count() == len(offers)
    for run in derived:
        assert run.parameters["derivada_de"]["evaluacion"] in before_runs
        assert run.models_used["externo"]["etapas"]["verificador"] == "externo"
    changed = am.Result.objects.get(run__in=derived, requirement=declaration.requirement,
                                    offer=first)
    assert (changed.outcome, changed.doubt) == ("no_determinado", "sin_corroborar")
    assert changed.previous_id == declaration.pk
    assert am.Result.objects.get(pk=declaration.pk).outcome == "cumple"

    # El «sin» es la corrida de origen; el «con» pierde la exacta que no se corroboró.
    figures = report.total["verificador"]
    assert figures["accuracy_before"]["exact"] == source.total["accuracy"]["exact"]
    assert figures["accuracy_after"]["exact"]["ok"] == source.total["accuracy"]["exact"]["ok"] - 1
    assert figures["from_exact"] == [(first.number, declaration.requirement.number)]
    assert figures["changed"] == figures["from_exact"]
    parameters = json.loads((report.folder / "parametros.json").read_text(encoding="utf-8"))
    assert parameters["verificador_sobre"]["fuente"] == source.folder.name
    assert parameters["verificador_sobre"]["medicion"] == "T-299-prueba"
    summary = (report.folder / "resumen.md").read_text(encoding="utf-8")
    assert "## Verificador externo de citas" in summary
    assert "[sin verificador]" in summary and "[con verificador]" in summary

    # El comando, con la misma medición: no manda nada nuevo (reusa por huella) y dice las cifras.
    batches = len(fake_external.batches)
    out = StringIO()
    call_command("medir_evaluacion", "--usuario", operator_user.username, "--caso-chico",
                 "--corridas", str(tmp_path / "con2"), "--commit", "abc1234",
                 "--celdas-comision", str(TRUTH), "--verificador-sobre", str(source.folder),
                 "--medicion", "T-299-prueba", stdout=out)
    text = out.getvalue()
    assert len(fake_external.batches) == batches
    assert AuditEvent.objects.filter(event_type=EventType.EXTERNAL_REQUEST,
                                     detail__resultado="reutilizado").exists()
    assert "Celdas que pasaron por el verificador externo" in text
    assert "«No determinado» nuevo que venía de una celda exacta (REQ-124): 1 · no cumple" in text


def test_the_verifier_over_a_saved_run_needs_the_stage_on(
        db, operator_user, fake_ai, model, fake_external, tmp_path):
    """REQ-122: sin el uso externo encendido y la etapa en `externo`, la pasada no corre y no
    guarda nada."""
    source, procedure, offers = _measured_small_case(operator_user, model, tmp_path)
    before = am.Run.objects.count()
    with pytest.raises(ev.MeasurementRefused):
        ev.measure_verifier(operator_user, procedure, ev.load_expected(LIST), offers,
                            tmp_path / "con", source.folder)
    assert am.Run.objects.count() == before and not fake_external.batches


def test_the_instruction_is_registered_and_within_its_limit():
    """REQ-119, REQ-122: `verificador-v2` es la instrucción de la etapa (la v1 sigue publicada, sin
    editar), existe y cumple el tope de las instrucciones no decisoras (50 líneas, 5.000
    caracteres)."""
    from django.conf import settings

    instruction = verifier.load_instruction()
    assert settings.EXTERNAL_PROMPT_VERSIONS["verificador"] == instruction.version == "verificador-v2"
    assert len(instruction.text.splitlines()) <= 50 and len(instruction.text) <= 5000
    assert '"sostiene"' in instruction.text and '"falta"' in instruction.text
    assert '"pregunta"' not in instruction.text
    assert (verifier.PROMPTS_DIR / "verificador-v1.md").is_file()


def test_the_instruction_judges_only_what_the_requirement_asks_in_400_characters():
    """REQ-124 (T-302, D-301-2): la instrucción manda juzgar solo la condición que el requisito
    nombra, sin agregar condiciones ni pedir datos que no exige, y deja `no` y `parcial` para cuando
    la cita no dice lo que la conclusión afirma; el razonamiento, de hasta 400 caracteres en
    total."""
    text = " ".join(verifier.load_instruction().text.split())
    for rule in ("Juzgá solo contra lo que el requisito pide, sin agregarle condiciones ni pedir "
                 "datos que no nombra",
                 "Lo que exige otro requisito del pliego, o un dato del proceso que no está en la "
                 "cita, no es una falta de la oferta",
                 '"no" o "parcial" solo cuando el texto no dice lo que la conclusión afirma para '
                 "una condición que el requisito nombra",
                 "de hasta 400 caracteres en total",
                 '"falta": vacía si "sostiene" es "si". Si no, en una frase corta para la Comisión, '
                 "el dato que el requisito pide y el texto citado no trae, sin repetir el "
                 "requisito ni la cita"):
        assert rule in text, rule


def test_a_reasoning_over_400_characters_is_cut_with_a_mark_and_the_answer_stays_valid(
        offer, operator_user, procedure, model, fake_external, numbers):
    """REQ-124 (T-302, D-301-2; T-301: razonamientos de hasta 497 caracteres): el código recorta el
    razonamiento a 400 caracteres con la marca «…» y la respuesta sigue valiendo: la celda pasa a
    «no determinado» igual y el hecho del registro conserva la respuesta completa."""
    long = ("La cita muestra el precio total pero no dice nada del dato que pide el requisito. " * 7
            )[:497]
    assert len(long) == 497
    sostiene, reasoning, _ = verifier.parse(answer("parcial", reasoning=long))
    assert sostiene == "parcial" and len(reasoning) <= 400 and reasoning.endswith("…")
    moneda = numbers["moneda"]
    run = evaluate_with_verifier(operator_user, procedure, model, fake_external, {
        verifier.custom_id_of(offer, moneda): answer("parcial", reasoning=long)})
    changed = results_of(run)[moneda.number]
    assert (changed.outcome, changed.doubt) == ("no_determinado", "sin_corroborar")
    mark = changed.facts["verificador"]
    assert mark["respuesta"] == "parcial" and 300 < len(mark["razonamiento"]) <= 400
    assert mark["razonamiento"].endswith("…") and "anomalia" not in mark
    event = AuditEvent.objects.get(pk=mark["hecho"])
    assert long in json.dumps(event.detail["respuesta"], ensure_ascii=False)


# --- Controles de la verificación de T-299 (H-299-1 y H-299-2) -----------------------------------


def docs_of(offer):
    return {d.title: d for d in om.Document.objects.filter(offer=offer)}


def real_cell(requirement, document, text, *, outcome=combine.OUT_CUMPLE, flagged=False,
              group=(), portal=(), question=""):
    """Una celda con un requisito real de la matriz y una cita de `document` (sin lectura: sin
    contexto)."""
    found = SimpleNamespace(document=document, page=1, text=text, reading=None, char_start=0,
                            char_end=len(text))
    combined = combine.Combined(outcome=outcome, doubt="", citations=[found],
                                portal=list(portal), explanation="Explicación.",
                                question=question)
    return verifier.Cell(requirement=requirement, text=grounds.requirement_text(requirement),
                         combined=combined, external_flagged=flagged,
                         group_documents=tuple(group) or (document.pk,))


def force_send(monkeypatch):
    """Anula el filtro previo para las conclusiones: lo que queda es la puerta sola."""
    original = verifier.skip_reason

    def forced(cell, reserved=frozenset()):
        if cell.combined.outcome in verifier.CONCLUSIONS:
            return None
        return original(cell, reserved)

    monkeypatch.setattr(verifier, "skip_reason", forced)


def test_each_piece_enters_with_its_origin_and_the_request_has_the_plan_parameters(
        procedure, operator_user, fake_external, fake_ai, numbers):
    """REQ-121 (O-290-3), REQ-124: la oración citada entra como texto de su documento de la oferta
    (no como instrucción), el requisito como requisito y el dato del Portal como Portal, una pieza
    de cada una; el dato del Portal está en el pedido; `max_tokens` 1.500 y caché de 1 hora."""
    offer = make_offer(procedure, operator_user, "Oferente", {"oferta.pdf": [DECLARATION, PRICES]})
    document = docs_of(offer)["oferta.pdf"]
    cell = real_cell(numbers["moneda"], document, PRICES, portal=PORTAL)
    fake_external.enable(verifier.STAGE)
    fake_external.respond(SI)
    verifier.verify([cell], offer=offer, run_id="prueba")
    (payload,) = fake_external.batches[0]
    assert "Total de la oferta: $ 535.000" in payload_text(payload)
    event = next(e for e in external_requests() if e.detail["custom_id"] == payload.custom_id)
    pieces = event.detail["filtro"]["piezas"]
    assert (pieces.get("oferta"), pieces.get("portal"), pieces.get("requisito")) == (1, 1, 1)
    params = payload.to_params()
    assert params["max_tokens"] == 1500
    assert params["system"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


def test_the_model_mark_reaches_the_cell_with_the_sheet_loaded(
        procedure, operator_user, model, fake_external, fake_ai, numbers):
    """REQ-121 (P9): con la hoja cargada, la regla de los externos deja «cumple» una celda que el
    modelo marcó externa (la hoja se lee); la marca llega al verificador y la celda no se manda
    como requisito externo."""
    offer = make_offer(procedure, operator_user, "Con hoja", {
        "oferta.pdf": [DECLARATION, PRICES], "hoja.pdf": sheet_paragraphs()},
        kinds={"hoja.pdf": "compliance"})
    fake_external.enable(verifier.STAGE)
    fake_external.respond(SI)

    def script(call):
        if "Cotizar en pesos" in call.requirement:
            return says("cumple", call.quote(PRICES), external=True)
        return local_script(call)

    model.evaluates(script)
    _, runs = run_all(operator_user, procedure, offers=[offer])
    assert results_of(runs[0])[numbers["moneda"].number].outcome == "cumple"
    assert runs[0].counts["externo"]["verificador"]["no_enviadas"]["requisito_externo"] == 1


def test_the_guard_gets_the_group_and_the_cited_documents_of_the_cell(
        procedure, operator_user, fake_external, fake_ai, numbers, monkeypatch):
    """REQ-121 (defensa en profundidad): sin el filtro previo, la puerta bloquea igual la celda con
    la hoja en su grupo de lectura y la que cita la hoja, porque recibe los documentos de los dos
    (`celda_con_compliance`)."""
    offer = make_offer(procedure, operator_user, "Con hoja", {
        "oferta.pdf": [DECLARATION, PRICES], "hoja.pdf": sheet_paragraphs()},
        kinds={"hoja.pdf": "compliance"})
    docs = docs_of(offer)
    plain, sheet = docs["oferta.pdf"], docs["hoja.pdf"]
    force_send(monkeypatch)
    fake_external.enable(verifier.STAGE)
    fake_external.respond(SI)
    in_group = real_cell(numbers["moneda"], plain, PRICES, group=(plain.pk, sheet.pk))
    cited = real_cell(numbers["declaracion"], sheet, "Texto cualquiera sin relación alguna aquí.",
                      group=(plain.pk,))
    done = verifier.verify([in_group, cited], offer=offer, run_id="prueba")
    assert not fake_external.batches
    for item in done.checked:
        assert "celda_con_compliance" in item.anomaly["motivos"]
        assert item.combined.outcome == "cumple"


def test_what_is_missing_goes_into_a_question_to_the_commission_never_to_the_offeror():
    """REQ-105 (T-302, D-301-4): lo que falta, dicho por el verificador, entra en el cierre de la
    pregunta con la conclusión que se discute; si dicho así se dirigiría al oferente, o no hay nada
    que decir, no hay cierre y la pregunta sigue con la que arma el código."""
    closing = verifier.missing_closing("el plazo de vigencia de la garantía.", combine.OUT_CUMPLE)
    assert closing == ("¿La Comisión confirma, corrige o rechaza la conclusión «cumple»? Lo que no "
                       "consta en el texto citado: el plazo de vigencia de la garantía.")
    assert not combine.asks_the_offeror(closing)
    assert verifier.missing_closing("el monto en letras", combine.OUT_NO_CUMPLE).count(
        "«no cumple»") == 1
    assert verifier.missing_closing(TO_OFFEROR, combine.OUT_CUMPLE) == ""
    assert verifier.missing_closing("¿Puede el oferente aclararlo?", combine.OUT_CUMPLE) == ""
    assert verifier.missing_closing("   ", combine.OUT_CUMPLE) == ""
    assert verifier.missing_closing("algo", combine.OUT_NO_DETERMINADO) == ""


def test_the_specific_question_of_the_cell_is_kept_when_the_verifier_one_is_not_used():
    """REQ-105, O-285-7: si lo que falta según el verificador no sirve (o no lo hay), queda la
    pregunta específica que ya traía la celda."""
    cell = _cell()
    specific = "¿La Comisión puede confirmar el dato específico que falta del requisito 7?"
    cell.combined = combine.Combined(**{**cell.combined.__dict__, "question": specific})
    after, used = verifier.decide(cell, "no", missing="¿Puede el oferente aclararlo?")
    assert used is False and after.question == specific
    after, used = verifier.decide(cell, "parcial", missing="")
    assert used is False and after.question == specific and after.outcome == "no_determinado"


@pytest.mark.parametrize("failure", ["configuracion", "sostiene"])
def test_a_bad_configuration_or_a_bad_verdict_leaves_the_cell(
        offer, operator_user, procedure, model, fake_external, numbers, settings, failure):
    """REQ-124: un tope mal configurado (`ImproperlyConfigured`) no hace caer la evaluación y un
    valor de `sostiene` fuera de `si`, `no` y `parcial` no es una respuesta: en los dos casos cada
    celda queda «cumple» con `verificador_sin_respuesta` y su motivo."""
    fake_external.enable(verifier.STAGE)
    if failure == "configuracion":
        fake_external.respond(SI)
        settings.EXTERNAL_CASE_CAP_USD = Decimal("-1")
    else:
        fake_external.respond(json.dumps({"razonamiento": "x", "sostiene": "quizá",
                                          "falta": ""}))
    model.evaluates(local_script)
    _, (run,) = run_all(operator_user, procedure)
    expected = "configuracion" if failure == "configuracion" else "respuesta_invalida"
    for name in ("declaracion", "registro", "moneda"):
        result = results_of(run)[numbers[name].number]
        mark = result.facts["verificador"]
        assert result.outcome == "cumple" and mark["respuesta"] is None
        assert mark["anomalia"]["type"] == verifier.ANOMALY
        assert mark["anomalia"]["motivo"] == expected
    assert run.counts["externo"]["verificador"]["sostiene"] == {"si": 0, "no": 0, "parcial": 0}


def test_the_schema_the_reasoning_and_the_record(offer, operator_user, procedure, model,
                                                 fake_external, numbers, settings):
    """REQ-122 (P6), ADR-0055: el esquema pide primero el razonamiento y lo exige; el razonamiento
    guardado no pasa de 400 caracteres; `facts["verificador"]` lo guarda; `prompt_versions` lleva
    la huella de la instrucción; y una anomalía de la etapa (el tope) llega a la corrida."""
    assert list(verifier.OUTPUT_SCHEMA["properties"]) == ["razonamiento", "sostiene", "falta"]
    assert verifier.OUTPUT_SCHEMA["required"] == ["razonamiento", "sostiene", "falta"]
    _, reasoning, _ = verifier.parse(json.dumps({"razonamiento": "palabra " * 120,
                                                 "sostiene": "si", "falta": ""}))
    assert 300 < len(reasoning) <= 400
    fake_external.enable(verifier.STAGE)
    fake_external.respond(SI)
    fake_external.respond(answer("no", reasoning="El precio unitario no está."),
                          verifier.custom_id_of(offer, numbers["moneda"]))
    model.evaluates(local_script)
    _, (run,) = run_all(operator_user, procedure)
    mark = results_of(run)[numbers["moneda"].number].facts["verificador"]
    assert set(mark) == {"antes", "despues", "respuesta", "razonamiento", "falta", "falta_usada",
                         "hecho", "instruccion"}
    assert mark["razonamiento"] == "El precio unitario no está."
    assert run.prompt_versions["externo"]["huellas"]["verificador"] == \
        verifier.load_instruction().sha256
    settings.EXTERNAL_CASE_CAP_USD = Decimal("0.0000001")
    _, (capped,) = run_all(operator_user, procedure)
    stage = [a for a in capped.anomalies if a.get("type") == "externo_bloqueado"]
    assert stage and stage[0]["motivo"] == "tope" and stage[0]["etapa"] == verifier.STAGE


def test_the_pass_over_a_saved_run_keeps_the_model_mark_and_the_source_questions(
        db, operator_user, fake_ai, model, fake_external, tmp_path):
    """REQ-121, REQ-124: la pasada sobre lo guardado lee la marca externa de los pedidos de lectura
    del origen (la celda no se manda) y la medición cuenta las preguntas del origen que la
    derivada no vuelve a abrir."""
    source, procedure, offers = _measured_small_case(operator_user, model, tmp_path)
    first = offers["Oferente A Sintético"]
    run = am.Run.objects.filter(offer=first).order_by("-number").first()
    declaration = next(r for r in first.assessment_results.select_related("requirement")
                       if r.requirement.quotes.filter(
                           text__contains="declaración jurada").exists())
    am.Step.objects.create(run=run, offer=first, requirement=declaration.requirement,
                           purpose=am.Purpose.GRUPO, group_index=99, parsed={"externo": True})
    fake_external.enable(verifier.STAGE)
    fake_external.respond(SI)
    report = ev.measure_verifier(
        operator_user, procedure, ev.load_expected(LIST), offers, tmp_path / "con",
        source.folder, commit="abc1234", commission_cells=ev.load_commission_cells(TRUTH))
    derived = am.Run.objects.filter(offer=first).order_by("-number").first()
    assert derived.counts["externo"]["verificador"]["no_enviadas"]["requisito_externo"] >= 1
    assert "verificador" not in am.Result.objects.get(
        run=derived, requirement=declaration.requirement).facts
    asked = sum(len(r["measures"]["questions"]) for r in source.offers)
    assert asked > 0
    assert sum(len(r["measures"]["questions"]) for r in report.offers) == asked


def test_a_second_pass_over_the_same_source_measures_the_changed_questions(
        db, operator_user, fake_ai, model, fake_external, tmp_path):
    """REQ-124 (H-299-1): dos pasadas sobre la misma corrida de origen (las dos rondas de ajuste),
    con la misma medición: cada derivada tiene la pregunta de la celda que el verificador cambió,
    aunque siga abierta la de la pasada anterior, y las dos rondas miden las mismas preguntas."""
    source, procedure, offers = _measured_small_case(operator_user, model, tmp_path)
    first = offers["Oferente A Sintético"]
    declaration = next(r for r in first.assessment_results.select_related("requirement")
                       if r.requirement.quotes.filter(
                           text__contains="declaración jurada").exists())
    number = declaration.requirement.number
    fake_external.enable(verifier.STAGE)
    fake_external.respond(SI)
    fake_external.respond(answer("no", MISSING_PRICE),
                          verifier.custom_id_of(first, declaration.requirement))
    seen = []
    for round_ in (1, 2):
        report = ev.measure_verifier(
            operator_user, procedure, ev.load_expected(LIST), offers, tmp_path / f"r{round_}",
            source.folder, measurement="T-299-rondas", commit="abc1234",
            commission_cells=ev.load_commission_cells(TRUTH))
        rows = sorted((r["number"], q["fila"]) for r in report.offers
                      for q in r["measures"]["questions"])
        derived = am.Run.objects.filter(offer=first).order_by("-number").first()
        changed = am.Result.objects.get(run=derived, requirement=declaration.requirement)
        assert am.Question.objects.filter(result=changed).count() == 1
        assert (first.number, number) in rows
        seen.append(rows)
    assert seen[0] == seen[1]
    assert report.total["questions_form"]["total"] == len(seen[1])
