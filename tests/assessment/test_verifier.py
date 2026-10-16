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
from evaluon.assessment import combine, externals
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

SI = json.dumps({"razonamiento": "La cita lo muestra.", "sostiene": "si", "pregunta": ""})


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


def answer(sostiene, question="", reasoning="Lo que dice la cita."):
    return json.dumps({"razonamiento": reasoning, "sostiene": sostiene, "pregunta": question})


def good_question(number):
    return (f"¿La Comisión confirma la conclusión «cumple» del requisito {number}? La oración del "
            "pliego «Cotizar en pesos con impuestos incluidos, indicando el precio unitario de cada "
            f"renglón.» pide el precio unitario, y el texto citado de la oferta «{PRICES}» "
            "(oferta.pdf, página 2) no lo muestra.")


TO_OFFEROR = "¿Puede el oferente acompañar la constancia completa del registro?"


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
    del verificador (tiene la forma de REQ-105); `parcial` con una pregunta al oferente la pasa
    igual, con la pregunta que arma el código. El «no determinado» no se manda y queda."""
    moneda = numbers["moneda"]
    run = evaluate_with_verifier(operator_user, procedure, model, fake_external, {
        verifier.custom_id_of(offer, moneda): answer("no", good_question(moneda.number)),
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
    assert mark["respuesta"] == "no" and mark["pregunta_usada"] is True
    assert AuditEvent.objects.get(pk=mark["hecho"]).detail["resultado"] == "ok"
    # Las mismas citas: la de la oferta y la del pliego, ninguna nueva.
    cites = list(changed.citations.order_by("order").values_list("kind", "text"))
    assert [t for k, t in cites if k == "oferta"] == [PRICES]
    assert {k for k, _ in cites} == {"oferta", "pliego"}
    question = am.Question.objects.get(result=changed).text
    assert good_question(moneda.number) in question
    form = ev.question_records(run)
    assert all(q["conforme"] for q in form if q["fila"] in (moneda.number,
                                                             numbers["registro"].number))

    registry = results[numbers["registro"].number]
    assert (registry.outcome, registry.doubt) == ("no_determinado", "sin_corroborar")
    assert registry.facts["verificador"]["pregunta_usada"] is False
    question = am.Question.objects.get(result=registry).text
    assert TO_OFFEROR not in question and "¿La Comisión confirma, corrige o rechaza" in question

    guarantee = results[numbers["garantia"].number]
    assert guarantee.outcome == "no_determinado" and "verificador" not in guarantee.facts


def test_what_is_sent_is_what_the_contrast_sees_and_nothing_of_the_local_reasoning(
        offer, operator_user, procedure, model, fake_external, numbers):
    """REQ-121, REQ-124 (plan, «Qué se manda»): el pedido lleva el requisito con su punto, la
    conclusión, la oración citada con su documento y su página, con la instrucción
    `verificador-v1`, esfuerzo `low`, pensamiento `between_tools` y el esquema de la salida; no
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
    assert event.detail["instruccion"]["version"] == "verificador-v1"
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
    assert run.prompt_versions["externo"]["verificador"] == "verificador-v1"
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
    after, _ = verifier.decide(cell, given, question="¿La Comisión confirma?")
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
    """REQ-119, REQ-122: `verificador-v1` es la instrucción de la etapa, existe y cumple el tope de
    las instrucciones no decisoras (50 líneas, 5.000 caracteres)."""
    from django.conf import settings

    instruction = verifier.load_instruction()
    assert settings.EXTERNAL_PROMPT_VERSIONS["verificador"] == instruction.version == "verificador-v1"
    assert len(instruction.text.splitlines()) <= 50 and len(instruction.text) <= 5000
    assert '"sostiene"' in instruction.text and '"pregunta"' in instruction.text
