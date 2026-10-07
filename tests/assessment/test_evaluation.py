"""Medición de la evaluación asistida contra la lista esperada (REQ-052, REQ-053, REQ-054,
REQ-055, REQ-059, REQ-060; plan 004, "Cómo se cuenta" y "Umbrales"; T-151). Caso chico
inventado (P4) y modelo simulado: las pruebas comprueban el contador, no al modelo real."""

import dataclasses
import json
import re
from io import StringIO

import pytest
import yaml
from django.core.management import call_command
from django.core.management.base import CommandError

from evaluon.accounts import permissions
from evaluon.assessment import evaluation as ev
from evaluon.assessment import models as am
from tests.assessment.fakes import (  # noqa: F401 - `model` es fixture
    CASO_CHICO, ILEGIBLE_NEEDLE, model, model_view, says)

pytestmark = pytest.mark.django_db

LIST = CASO_CHICO / "evaluacion-esperada.yaml"
# Pares del caso chico cuya regla todavía no existe (T-169 los llevó a 0).
WITHOUT_RULES = 0


def oracle_for(raw, *, change=None):
    """Un modelo que contesta lo que dice la lista esperada; `change(bidder, id, entry)` puede
    devolver otra respuesta (un diccionario del modelo) para provocar una diferencia."""
    ids = [r["id"] for r in raw["matriz"]["requisitos"]]
    by_bidder = {o["oferente"]: {ids.index(e["requisito"]) + 1: e for e in o["requisitos"]}
                 for o in raw["ofertas"]}

    def quote_of(call, anchor):
        words = anchor.split()
        for size in range(len(words), 2, -1):
            found = call.quote(" ".join(words[:size]))
            if found is not None:
                return found
        return None

    def oracle(call):
        bidder = next(b for b in by_bidder if b in "".join(call.documents.values()))
        number = int(re.search(r"requisito (\d+)", call.requirement).group(1))
        entry = model_view(bidder, by_bidder[bidder][number])
        if change is not None:
            other = change(bidder, entry["requisito"], entry, call)
            if other is not None:
                return other
        result = entry["resultado"]
        if result in ("cumple", "no_cumple"):
            quotes = [quote_of(call, c["ancla"]) for c in entry["citas"]]
            answer = says(result, *[q for q in quotes if q is not None])
            if result == "no_cumple" and call.requirement.startswith("Renglón"):
                # Un "no cumple" de un renglón cita la cláusula del pliego que contradice
                # (T-156): la última cláusula del requisito, sin las comillas.
                answer["clausula"] = re.findall(r"«(.*?)»", call.requirement)[-1]
            return answer
        if entry.get("ilegible"):
            return says("no_determinado", ilegible=call.alias_with(ILEGIBLE_NEEDLE))
        if entry.get("motivo") == "falta_hoja_compliance":
            return says("no_determinado", external=True)
        return says("no_consta", exigence="documento")

    return oracle


def load_small_case_portal(user, procedure, offers):
    """Las tablas del Portal del caso chico (datos inventados): la garantía del M-006 de A."""
    from decimal import Decimal

    from evaluon.portal import models as pm
    link = pm.PortalLink.objects.create(url="https://portal.invalid/proceso",
                                        procedure=procedure, created_by=user)
    page = pm.PortalPage.objects.create(link=link, exploration=1, kind="cuadro",
                                        url="https://portal.invalid/cuadro",
                                        sha256="a" * 64, content=b"x")
    proposal = pm.PortalProposal.objects.create(link=link, exploration=1, origin="importacion")
    item = pm.PortalItem.objects.create(proposal=proposal, kind="oferta", key="o", payload={},
                                        content_sha256="b" * 64, page=page)
    data = pm.PortalOfferData.objects.create(offer=offers["Oferente A Sintético"],
                                             cuit="30-00000000-0", total=Decimal("535000.00"),
                                             item=item)
    pm.PortalGuarantee.objects.create(offer_data=data, guarantee_type="Garantía de mantenimiento",
                                      amount=Decimal("26750.00"), item=item)


def measured(user, model_, tmp_path, *, change=None, fichas=None):
    expected = ev.load_expected(LIST)
    procedure, offers = ev.build_case(user, expected)
    load_small_case_portal(user, procedure, offers)
    raw = yaml.safe_load(LIST.read_text(encoding="utf-8"))
    model_.evaluates(oracle_for(raw, change=change))
    report = ev.measure(user, procedure, expected, offers, tmp_path, fichas=fichas,
                        commit="abc1234")
    return report, procedure, offers


# --- La lista ------------------------------------------------------------------------------------


def test_the_small_case_list_is_read_with_its_correction():
    """REQ-052: la lista del caso chico se lee con su visto bueno, 30 pares, y trae la
    corrección del ADR-0038 (M-003 de la oferta B, lectura incompleta con pregunta) y el par de
    documento ausente con lectura completa (M-003 de la oferta C)."""
    expected = ev.load_expected(LIST)
    assert expected.kind == "evaluacion" and expected.approval
    assert sum(len(o.pairs) for o in expected.offers) == 30
    kinds = [p.kind for o in expected.offers for p in o.pairs]
    assert {k: kinds.count(k) for k in ev.PAIR_TYPES} == {
        "oferta": 16, "externo": 3, "tecnico": 9, "ilegible": 1, "portal": 1}
    assert ev.check_fields(expected) == []
    pair = {o.bidder[:10]: {p.requirement: p for p in o.pairs} for o in expected.offers}
    assert pair["Oferente B"]["M-003"].result == am.Outcome.NO_DETERMINADO
    assert pair["Oferente B"]["M-003"].doubt == am.Doubt.LECTURA_INCOMPLETA
    assert pair["Oferente B"]["M-003"].question
    assert pair["Oferente C"]["M-003"].result == am.Outcome.SIN_DOCUMENTO
    raw = yaml.safe_load(LIST.read_text(encoding="utf-8"))
    counts = {}
    for offer in raw["ofertas"]:
        for entry in offer["requisitos"]:
            counts[entry["resultado"]] = counts.get(entry["resultado"], 0) + 1
    assert counts == raw["resumen"]["por_resultado"]
    assert sum(e["pregunta"] == "si" for o in raw["ofertas"] for e in o["requisitos"]
               if "pregunta" in e) == raw["resumen"]["preguntas_esperadas"]


def test_a_list_without_approval_is_not_used(tmp_path):
    """Una lista sin visto bueno, o con "pendiente", no se mide (como en la 008)."""
    raw = yaml.safe_load(LIST.read_text(encoding="utf-8"))
    for value in ("pendiente", ""):
        raw["visto_bueno"] = value
        path = tmp_path / "lista.yaml"
        path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
        with pytest.raises(ev.ExpectedNotApproved):
            ev.load_expected(path)
        assert ev.load_expected(path, require_approval=False).approval == ""


def test_the_dictamen_list_is_read(tmp_path):
    """La lista del caso-00 (por requisito `dictamen`, sin matriz ni documentos) se lee y su
    resultado es el del dictamen; las fichas dan el mapeo y las copias equivalentes."""
    path = tmp_path / "dictamen-esperado.yaml"
    path.write_text(yaml.safe_dump({
        "caso": "caso-00", "visto_bueno": "Coordinador, 2026-10-06",
        "matriz": {"procedimiento": "P-1", "archivo": "matriz-esperada.yaml"},
        "ofertas": [{"oferente": "Uno", "descartada": "parcial", "requisitos": [
            {"requisito": "M-008", "dictamen": "cumple", "base": "externa", "via": "expreso"},
            {"requisito": "M-051", "dictamen": "no_cumple", "base": "tecnica"}]}],
        "orden_economico": {"por_renglon": {1: ["Uno"]}}}, allow_unicode=True),
        encoding="utf-8")
    expected = ev.load_expected(path)
    assert expected.kind == "dictamen" and expected.requirements == []
    assert [(p.requirement, p.result, p.base) for p in expected.offers[0].pairs] == [
        ("M-008", "cumple", "externa"), ("M-051", "no_cumple", "tecnica")]
    assert expected.offers[0].discarded == "parcial"
    fichas = tmp_path / "fichas-esperadas.yaml"
    fichas.write_text(yaml.safe_dump({"ofertas": [{
        "oferente": "Uno", "fragmentos": [
            {"id": "F-1", "requisito": "M-008", "documento": "a.pdf", "pagina": 2, "ancla": "x"}],
        "equivalentes": [{"archivo": "b.pdf", "equivale_a": "a.pdf", "sha256": "0"}]}],
        "matriz": {"requisitos": [{"id": "M-008", "clase": "formal", "cita": "x"}]}}),
        encoding="utf-8")
    loaded = ev.load_fichas(fichas)
    assert loaded.equivalents == {"Uno": {"b.pdf": "a.pdf"}}
    assert loaded.fragments["Uno"][0]["pagina"] == 2


def test_a_dictamen_cumple_on_an_external_pair_matches_the_abstention():
    """Decisión 1 del responsable: en lo externo, "no determinado" por requisito externo
    coincide con el "cumple" del dictamen; "no cumple" por "cumple" es una contradicción."""
    pair = ev.ExpectedPair(requirement="M-008", result="cumple", base="externa")
    undetermined = am.Result(outcome="no_determinado", doubt="externo")
    assert ev._match(pair, undetermined)
    assert not ev._match(pair, am.Result(outcome="no_determinado", doubt="duda"))
    assert not ev._match(dataclasses.replace(pair, base="oferta"), undetermined)
    assert ev._contradiction(pair, am.Result(outcome="no_cumple"))
    assert not ev._contradiction(pair, undetermined)


# --- El armado del caso -------------------------------------------------------------------------


def test_a_technical_row_of_the_case_carries_the_clauses_of_its_renglon(db, operator_user,
                                                                       fake_ai):
    """REQ-052: la fila técnica del caso lleva el encabezado del renglón y sus cláusulas (la de
    la 008 solo traía el encabezado)."""
    expected = ev.load_expected(LIST)
    only_a = dataclasses.replace(expected, offers=expected.offers[:1])
    only_a.offers[0].documents = []
    procedure, _ = ev.build_case(operator_user, only_a)
    version = procedure.matrix_versions.get(number=1)
    row = version.requirements.get(category="tecnico", items=[1])
    texts = [q.text for q in row.quotes.order_by("order")]
    assert len(texts) == 2 and "RENGLÓN" in texts[0] and "75 gramos" in texts[1]
    assert version.requirements.count() == 10


# --- La medición -------------------------------------------------------------------------------


def test_the_list_is_checked_against_the_readings(db, operator_user, fake_ai):
    """`--verificar-esperada`: huellas, anclas de las citas y páginas ilegibles contra las
    lecturas, sin el modelo; una ancla que no está en su página falla."""
    expected = ev.load_expected(LIST)
    _, offers = ev.build_case(operator_user, expected)
    verification = ev.verify_expected(expected, offers)
    assert verification.ok, verification.lines
    assert verification.counts["anchors"] == 15 and verification.counts["unreadable_pages"] == 1
    expected.offers[0].pairs[0].citations[0]["ancla"] = "Un texto que no figura en la página"
    assert not ev.verify_expected(expected, offers).ok


def test_a_model_that_follows_the_list_reaches_the_threshold(db, operator_user, fake_ai, model,
                                                            tmp_path):
    """REQ-052 a REQ-055, REQ-059, REQ-060: con un modelo que contesta lo esperado, todas las
    medidas del caso chico llegan al umbral y la corrida guarda sus cuatro archivos."""
    report, _, _ = measured(operator_user, model, tmp_path)
    total = report.total
    # Con todas las reglas (T-169), ninguna medida queda corta.
    assert report.blocking == []
    assert total["pairs"] == 30 and total["match"]["ok"] == 30 - WITHOUT_RULES
    assert total["match_by_type"]["oferta"] == {"ok": 16, "total": 16, "rate": 1.0}
    assert total["match_by_type"]["externo"] == {"ok": 3, "total": 3, "rate": 1.0}
    assert total["contradictions"] == [] and total["no_citation"] == []
    assert total["literal"]["ok"] == total["literal"]["total"] > 0
    assert total["missing_document"] == {"ok": 1, "total": 1, "rate": 1.0}
    raw = yaml.safe_load(LIST.read_text(encoding="utf-8"))
    asked = sum(e.get("pregunta") == "si" for o in raw["ofertas"] for e in o["requisitos"])
    assert total["questions"] == {"ok": asked, "total": asked, "rate": 1.0}
    assert total["matrix"]["ok"] == 30
    assert total["discards"]["ok"] == 3
    assert sorted(p.name for p in report.folder.iterdir()) == sorted(ev.RUN_FILE_NAMES)
    assert report.folder.name.endswith("-abc1234")
    parameters = json.loads((report.folder / "parametros.json").read_text(encoding="utf-8"))
    assert parameters["caso"] == "caso-chico-evaluacion" and parameters["lista"]["pares"] == 30
    lines = (report.folder / "resultados.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 30


def test_the_public_summary_has_no_bidder_names(db, operator_user, fake_ai, model, tmp_path):
    """P4: el resumen público no nombra a los oferentes; el completo sí."""
    report, _, _ = measured(operator_user, model, tmp_path)
    public = (report.folder / "resumen-publico.md").read_text(encoding="utf-8")
    full = (report.folder / "resumen.md").read_text(encoding="utf-8")
    assert "Sintético" not in public and "Sintético" in full
    assert "Coincidencia por tipo de par: oferta 100,0 % (16 de 16" in public
    assert "Residuo de «no determinado»" in public


def test_a_cumple_where_the_list_says_no_cumple_is_a_contradiction(db, operator_user, fake_ai,
                                                                  model, tmp_path):
    """REQ-052: un "cumple" donde se espera "no cumple" cuenta como contradicción, baja la
    coincidencia y bloquea la aceptación."""
    def wrong(bidder, requirement, entry, call):
        if requirement == "M-001" and bidder.startswith("Oferente C"):
            return says("cumple", call.quote(
                "se encuentra comprendido en una causal de inhabilidad para contratar"))
        return None

    report, _, _ = measured(operator_user, model, tmp_path, change=wrong)
    total = report.total
    assert total["contradictions"] == [("M-001", "no_cumple", "cumple")]
    assert total["match"]["ok"] == 30 - WITHOUT_RULES - 1
    assert any("Contradicciones" in line for line in report.blocking)
    assert any("Coincidencia" in line for line in report.blocking)


def test_a_pair_without_the_expected_question_or_missing_document_fails(
        db, operator_user, fake_ai, model, tmp_path):
    """REQ-055 y REQ-060: un "no determinado" sin pregunta donde se espera una y un "no se
    encontró el documento" que se vuelve "no determinado" quedan contados como faltas."""
    def vague(bidder, requirement, entry, call):
        if requirement == "M-003" and bidder.startswith("Oferente C"):
            return says("no_determinado", question="")
        return None

    report, _, _ = measured(operator_user, model, tmp_path, change=vague)
    total = report.total
    assert total["missing_document"] == {"ok": 0, "total": 1, "rate": 0.0}
    assert total["match"]["ok"] == 30 - WITHOUT_RULES - 1
    assert any("REQ-060" in line for line in report.blocking)


def test_fragments_count_the_same_document_and_page_and_the_equivalent_copies(
        db, operator_user, fake_ai, model, tmp_path):
    """REQ-054: la propuesta cita el documento y la página del fragmento esperado, y una copia
    equivalente (campo `equivalentes`) cuenta como el mismo documento."""
    fichas = ev.Fichas(
        requirements=[], equivalents={"Oferente A Sintético": {
            "ofertas/oferente-a/poliza-caucion-copia.pdf": "ofertas/oferente-a/poliza-caucion.pdf"}},
        fragments={"Oferente A Sintético": [
            {"requisito": "M-006", "documento": "ofertas/oferente-a/poliza-caucion-copia.pdf",
             "pagina": 1},
            {"requisito": "M-001", "documento": "ofertas/oferente-a/oferta-propuesta.pdf",
             "pagina": 2}],
        "Oferente B Sintético": [], "Oferente C Sintético": []})
    report, _, _ = measured(operator_user, model, tmp_path, fichas=fichas)
    # M-006 cita la póliza original y el fragmento está en su copia: equivalente.
    # M-001 cita la página 1 y el fragmento esperado dice página 2: no coincide.
    assert report.total["fragments"] == {"ok": 1, "total": 2, "rate": 0.5}
    assert ev._canonical_document("b", {"b": "a", "a": "z"}) == "z"


def test_the_small_case_derives_its_fragments_from_the_list_citations(
        db, operator_user, fake_ai, model, tmp_path):
    """REQ-054: sin lista de fichas, los fragmentos son las citas de la lista; un modelo que
    las sigue las encuentra todas."""
    report, _, _ = measured(operator_user, model, tmp_path)
    fragments = report.total["fragments"]
    assert fragments["total"] == 15 and fragments["ok"] == fragments["total"]


# --- El comando ---------------------------------------------------------------------------------


def test_the_command_measures_the_small_case(db, operator_user, fake_ai, model, tmp_path,
                                             monkeypatch):
    """REQ-052: `medir_evaluacion --caso-chico` arma el caso, mide y escribe la corrida; con
    `--verificar-esperada` no usa el modelo."""
    from tests.tenders.conftest import TEST_PASSWORD
    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    out = StringIO()
    call_command("medir_evaluacion", "--usuario", operator_user.username, "--caso-chico",
                 "--verificar-esperada", stdout=out)
    assert "sin fallas" in out.getvalue() and not model.calls
    raw = yaml.safe_load(LIST.read_text(encoding="utf-8"))
    model.evaluates(oracle_for(raw))
    out = StringIO()
    call_command("medir_evaluacion", "--usuario", operator_user.username, "--caso-chico",
                 "--corridas", str(tmp_path), "--commit", "abc1234", stdout=out)
    text = out.getvalue()
    assert "Bloquea la aceptación: Coincidencia" in text and "Corrida guardada en" in text
    with pytest.raises(CommandError):
        call_command("medir_evaluacion", "--usuario", operator_user.username,
                     stdout=StringIO())


def test_bidder_names_of_the_dictamen_are_paired_with_the_loaded_offers():
    """REQ-052 (caso-00): el dictamen nombra a «Munoz» y la oferta cargada es «Muñoz Insumos
    Veterinarios SRL»; el nombre se parea sin tildes ni mayúsculas, y un nombre ambiguo no."""
    names = ["Lombardozzi", "Muñoz Insumos Veterinarios SRL", "Ricardo José Zelarayan"]
    assert ev.match_name("Munoz", names) == "Muñoz Insumos Veterinarios SRL"
    assert ev.match_name("Zelarayan", names) == "Ricardo José Zelarayan"
    assert ev.match_name("Lombardozzi", names) == "Lombardozzi"
    assert ev.match_name("Perez", names) is None
    assert ev.match_name("Muñoz", ["Muñoz Uno SA", "Muñoz Dos SA"]) is None


# --- Alteraciones de las métricas que bloquean ------------------------------------------------------


def _pair_on(rows, outcome, number=2, doubt=""):
    """Un resultado nuevo (otra evaluación) del requisito de `rows`, sin citas."""
    run = am.Run.objects.create(
        request=rows.request, offer=rows.run.offer, matrix_version=rows.version, number=number,
        channel=am.Channel.SCREEN, documents=[], norms={}, models_used={}, parameters={},
        prompt_versions={})
    return am.Result.objects.create(run=run, offer=run.offer, requirement=rows.requirement,
                                    outcome=outcome, doubt=doubt,
                                    exigence=am.Exigence.CONDICION)


def test_a_citation_that_is_not_the_canonical_cut_is_not_counted_as_literal(rows):
    """REQ-053: una cita cuyo texto no es el recorte del texto canónico no cuenta como
    literal, ni una cuya página no es la del recorte."""
    result = _pair_on(rows, am.Outcome.CUMPLE)
    reading = rows.reading
    common = dict(result=result, kind=am.CitationKind.OFERTA, document=rows.document,
                  reading=reading, page=1, char_start=0, char_end=10)
    am.Citation.objects.create(order=1, text=reading.canonical_text[:10], **common)
    am.Citation.objects.create(order=2, text="otro texto", **common)
    pair = ev.ExpectedPair(requirement="M-001", result=am.Outcome.CUMPLE, base="oferta")
    record = ev.measure_pair(pair, result, rows.requirement, result.offer, ev.PageFinder(),
                             [], {})
    assert (record["citas_oferta"], record["citas_literales"]) == (2, 1)
    total = ev.aggregate([{"records": [record], "timings": {}, "steps": {
        "pedidos": 0, "tokens_pedido": 0, "tokens_salida": 0}, "unread_pages": 0,
        "discard_ok": None}])
    assert total["literal"] == {"ok": 1, "total": 2, "rate": 0.5}
    assert any("Citas de la oferta" in line for line in ev.blocking(total))


def test_a_cumple_without_a_citation_is_counted_and_blocks(rows):
    """REQ-053: un "cumple" sin cita de la oferta queda en `no_citation` y bloquea."""
    result = _pair_on(rows, am.Outcome.CUMPLE)
    pair = ev.ExpectedPair(requirement="M-001", result=am.Outcome.CUMPLE, base="oferta")
    record = ev.measure_pair(pair, result, rows.requirement, result.offer, ev.PageFinder(),
                             [], {})
    assert record["sin_cita"] is True
    total = ev.aggregate([{"records": [record], "timings": {}, "steps": {
        "pedidos": 0, "tokens_pedido": 0, "tokens_salida": 0}, "unread_pages": 0,
        "discard_ok": None}])
    assert total["no_citation"] == ["M-001"]
    assert any("sin cita" in line for line in ev.blocking(total))


def test_a_question_of_an_earlier_evaluation_is_not_counted(rows):
    """REQ-055: "pregunta formulada" cuenta solo la pregunta de la evaluación medida, no la
    abierta de una corrida anterior."""
    result = _pair_on(rows, am.Outcome.NO_DETERMINADO, doubt=am.Doubt.EXTERNO)
    pair = ev.ExpectedPair(requirement="M-001", result=am.Outcome.NO_DETERMINADO,
                           base="oferta", question=True)
    other = am.Question.objects.create(
        procedure=rows.request.procedure, requirement=rows.requirement,
        offer=result.offer, result=rows.result, text="¿Otra pregunta?", reason="externo")
    record = ev.measure_pair(pair, result, rows.requirement, result.offer, ev.PageFinder(),
                             [], {})
    assert other.answers.count() == 0 and record["pregunta_formulada"] is False


# --- La regla nueva por tipo de par (enmienda 2026-10-06, T-170) -------------------------------------


def _result(outcome, doubt="", **fields):
    return am.Result(outcome=outcome, doubt=doubt, **fields)


def _technical(**fields):
    base = dict(requirement="M-008", result=am.Outcome.NO_DETERMINADO, base="tecnica",
                technical_document="hay", offered="si", dictamen="cumple")
    return ev.ExpectedPair(**{**base, **fields})


PENDING = am.Doubt.PENDIENTE_INFORME_TECNICO


@pytest.mark.decision_literal
def test_a_technical_row_matches_pending_with_the_two_facts_equal():
    """REQ-052, REQ-061 (decisión 1 y 2): una fila técnica coincide con «pendiente del informe
    técnico» si el documento técnico y el renglón ofertado son los esperados; con otro hecho,
    con un «cumple» o sin hechos, no."""
    pair = _technical()
    facts = {"documento_tecnico": "hay", "renglon_ofertado": "si"}
    assert ev._match(pair, _result(am.Outcome.NO_DETERMINADO, PENDING, facts=facts))
    assert not ev._match(pair, _result(am.Outcome.NO_DETERMINADO, PENDING, facts={}))
    assert not ev._match(pair, _result(am.Outcome.NO_DETERMINADO, PENDING, facts={
        "documento_tecnico": "hay", "renglon_ofertado": "no"}))
    assert not ev._match(pair, _result(am.Outcome.NO_DETERMINADO, am.Doubt.DUDA, facts=facts))
    assert not ev._match(pair, _result(am.Outcome.CUMPLE, facts=facts))
    # Sin renglones (`no_aplica`): el hecho no está en `facts`.
    whole = _technical(offered="no_aplica")
    assert ev._match(whole, _result(am.Outcome.NO_DETERMINADO, PENDING,
                                    facts={"documento_tecnico": "hay"}))
    # Si lo esperado es que el documento falta, coincide «no se encontró el documento».
    missing = _technical(technical_document="no_se_encontro", offered="no")
    assert ev._match(missing, _result(am.Outcome.SIN_DOCUMENTO, facts={
        "documento_tecnico": "no_se_encontro", "renglon_ofertado": "no"}))
    assert not ev._match(missing, _result(am.Outcome.NO_DETERMINADO, PENDING, facts={
        "documento_tecnico": "no_se_encontro", "renglon_ofertado": "no"}))


@pytest.mark.decision_literal
def test_a_technical_fact_opposed_to_the_list_is_a_contradiction_reported_apart():
    """REQ-052, REQ-061: «renglón ofertado: sí» donde la lista dice que no se ofertó es una
    contradicción (de hecho); un hecho «no determinado» solo no coincide."""
    pair = _technical(offered="no")
    opposed = _result(am.Outcome.NO_DETERMINADO, PENDING, facts={
        "documento_tecnico": "hay", "renglon_ofertado": "si"})
    assert ev._fact_contradictions(pair, opposed) == [
        "renglon_ofertado: esperado no, obtenido si"]
    undetermined = _result(am.Outcome.NO_DETERMINADO, PENDING, facts={
        "documento_tecnico": "hay", "renglon_ofertado": "no_determinado"})
    assert ev._fact_contradictions(pair, undetermined) == []
    assert not ev._match(pair, undetermined)
    doc = _result(am.Outcome.SIN_DOCUMENTO, facts={
        "documento_tecnico": "no_se_encontro", "renglon_ofertado": "no"})
    assert ev._fact_contradictions(pair, doc) == [
        "documento_tecnico: esperado hay, obtenido no_se_encontro"]


@pytest.mark.decision_literal
def test_the_technical_opinion_is_not_the_result_but_a_cumple_against_the_dictamen_counts():
    """REQ-061: la opinión no es el resultado ni una contradicción; un «cumple» o «no cumple»
    en el resultado de una fila técnica sí se cuenta contra el dictamen y se informa."""
    pair = _technical(dictamen="no_cumple")
    facts = {"documento_tecnico": "hay", "renglon_ofertado": "si"}
    with_opinion = _result(am.Outcome.NO_DETERMINADO, PENDING, facts=facts,
                           opinion=am.Opinion.CUMPLE)
    assert ev._match(pair, with_opinion) and not ev._contradiction(pair, with_opinion)
    assert ev._contradiction(pair, _result(am.Outcome.CUMPLE, facts=facts))
    assert not ev._contradiction(pair, _result(am.Outcome.NO_CUMPLE, facts=facts))


def _unreadable(**fields):
    base = dict(requirement="M-004", result=am.Outcome.NO_DETERMINADO, base="oferta",
                doubt=am.Doubt.NO_SE_PUDO_LEER,
                unreadable={"documento": "ofertas/b/mixto.pdf", "pagina": 2})
    return ev.ExpectedPair(**{**base, **fields})


@pytest.mark.decision_literal
def test_an_unreadable_document_matches_only_with_its_document_and_page():
    """REQ-052, REQ-064 (decisión 5): «no se pudo leer» coincide con el documento y la página
    de la lista; con otra página, otro documento o `lectura_incompleta`, no."""
    pair = _unreadable()
    good = {"ilegible": {"documento": "Título del documento", "documento_id": 7,
                         "archivo": "mixto.pdf", "pagina": 2, "paginas": [2]}}
    assert ev._match(pair, _result(am.Outcome.NO_DETERMINADO, am.Doubt.NO_SE_PUDO_LEER,
                                   facts=good))
    for facts in ({"ilegible": {"archivo": "mixto.pdf", "pagina": 3, "paginas": [3]}},
                  {"ilegible": {"archivo": "otro.pdf", "documento": "mixto.pdf",
                                "pagina": 2}}, {}):
        assert not ev._match(pair, _result(
            am.Outcome.NO_DETERMINADO, am.Doubt.NO_SE_PUDO_LEER, facts=facts))
    assert not ev._match(pair, _result(am.Outcome.NO_DETERMINADO, am.Doubt.LECTURA_INCOMPLETA,
                                       facts=good))


@pytest.mark.decision_literal
def test_an_external_pair_matches_the_missing_sheet_whatever_the_dictamen_says():
    """REQ-052, REQ-063 (decisión 3): «falta la hoja de compliance» coincide aunque el dictamen
    diga cumple o no cumple; con la hoja cargada vale el mismo resultado del dictamen; una
    «duda» o «no se encontró el documento» no cuentan."""
    for dictamen in (am.Outcome.CUMPLE, am.Outcome.NO_CUMPLE):
        pair = ev.ExpectedPair(requirement="M-008", result=dictamen, base="externa")
        assert ev._match(pair, _result(am.Outcome.NO_DETERMINADO, am.Doubt.EXTERNO))
        assert ev._match(pair, _result(dictamen))
        assert not ev._match(pair, _result(am.Outcome.NO_DETERMINADO, am.Doubt.DUDA))
        assert not ev._match(pair, _result(am.Outcome.SIN_DOCUMENTO))


def test_the_residue_and_the_types_are_reported_apart_from_the_threshold():
    """REQ-052: el residuo de `duda`, `sin_dato` y `sin_corroborar` y la coincidencia por tipo
    de par se informan; no bloquean."""
    records = []
    for kind, outcome, doubt, hit in (
            ("oferta", am.Outcome.CUMPLE, "", True),
            ("externo", am.Outcome.NO_DETERMINADO, am.Doubt.EXTERNO, True),
            ("tecnico", am.Outcome.NO_DETERMINADO, am.Doubt.DUDA, False),
            ("tecnico", am.Outcome.NO_DETERMINADO, am.Doubt.SIN_DATO, False),
            ("oferta", am.Outcome.NO_DETERMINADO, am.Doubt.SIN_CORROBORAR, False)):
        records.append({
            "requisito": "M-001", "tipo": kind, "obtenido": outcome, "motivo": doubt,
            "esperado": am.Outcome.CUMPLE, "coincide": hit, "contradiccion": False,
            "sin_cita": False, "citas_oferta": 0, "citas_literales": 0,
            "pregunta_esperada": False, "pregunta_formulada": False, "cita_pliego": False,
            "fragmento": None, "sin_documento_donde_cumple": False, "base": "oferta",
            "contradicciones_hecho": [], "dictamen": "cumple", "opinion": "no_cumple",
            "tecnico_concluido": False, "citas_portal": 0, "citas_portal_literales": 0})
    total = ev.aggregate([{"records": records, "timings": {}, "steps": {
        "pedidos": 0, "tokens_pedido": 0, "tokens_salida": 0}, "unread_pages": 0,
        "discard_ok": None, "technical_discard": {
            "dictamen_no_cumple": 0, "opinion_no_cumple": 2, "ambos": 0}}])
    assert total["residue"] == {"duda": 1, "sin_dato": 1, "sin_corroborar": 1}
    assert total["match_by_type"]["tecnico"] == {"ok": 0, "total": 2, "rate": 0.0}
    assert total["match_by_type"]["externo"]["ok"] == 1
    assert total["technical_opinion"] == {"ok": 0, "total": 2, "rate": 0.0}
    assert total["technical_discard"]["opinion_no_cumple"] == 2
    assert total["technical_concluded"] == []


# --- El Portal ----------------------------------------------------------------------------------


@pytest.fixture
def portal_rows(rows, procedure, operator_user):
    """Una oferta con una fila de garantía del Portal (monto inventado) y su ítem de origen."""
    from evaluon.portal import models as pm

    link = pm.PortalLink.objects.create(url="https://portal.invalid/proceso",
                                        procedure=procedure, created_by=operator_user)
    page = pm.PortalPage.objects.create(link=link, exploration=1, kind="cuadro",
                                        url="https://portal.invalid/cuadro",
                                        sha256="a" * 64, content=b"x")
    proposal = pm.PortalProposal.objects.create(link=link, exploration=1, origin="importacion")
    item = pm.PortalItem.objects.create(proposal=proposal, kind="oferta", key="o", payload={},
                                        content_sha256="b" * 64, page=page)
    data = pm.PortalOfferData.objects.create(offer=rows.result.offer, cuit="30-00000000-0",
                                             total="535000.00", item=item)
    pm.PortalGuarantee.objects.create(offer_data=data, guarantee_type="Póliza",
                                      amount="26750.00", item=item)
    return item


def _portal_cite(rows, item, text, kind=am.PortalKind.GARANTIA, order=5):
    return am.Citation.objects.create(
        result=rows.result, order=order, kind=am.CitationKind.PORTAL, portal_item=item,
        portal_kind=kind, text=text, label="Portal: acta de apertura")


def _portal_pair(tipo="garantia", valor="26750"):
    return ev.ExpectedPair(requirement="M-006", result=am.Outcome.CUMPLE, base="oferta",
                           portal={"tipo": tipo, "valor": valor})


@pytest.mark.decision_literal
def test_a_portal_pair_matches_the_cited_value_and_opposed_values_are_contradictions(
        rows, portal_rows):
    """REQ-052, REQ-062 (decisión 4): el par con `portal` coincide si el resultado cita un dato
    del Portal del mismo tipo y valor (escrito a la argentina o sin separadores); un valor
    distinto no coincide y se cuenta como contradicción de dato; sin cita, no coincide."""
    pair = _portal_pair()
    assert not ev._match(pair, rows.result)
    assert ev._fact_contradictions(pair, rows.result) == []
    _portal_cite(rows, portal_rows, "Garantía: Póliza, $ 26.750,00")
    assert ev._match(pair, rows.result)
    assert ev._fact_contradictions(pair, rows.result) == []
    assert not ev._match(_portal_pair(tipo="total"), rows.result)
    other = _portal_pair(valor="30000")
    assert not ev._match(other, rows.result)
    assert ev._fact_contradictions(other, rows.result) == [
        "portal garantia: valor distinto del esperado"]


@pytest.mark.decision_literal
def test_a_portal_citation_is_literal_only_if_it_equals_its_row(rows, portal_rows):
    """REQ-053, REQ-062: la cita del Portal cuenta como literal si el monto de su fila está en
    el texto; con otro monto, no; las citas del Portal tienen su propio umbral del 100 %."""
    offer = rows.result.offer
    good = _portal_cite(rows, portal_rows, "Garantía: Póliza, $ 26.750,00")
    bad = _portal_cite(rows, portal_rows, "Garantía: Póliza, $ 25.000,00", order=6)
    assert ev._portal_cite_is_literal(good, offer)
    assert not ev._portal_cite_is_literal(bad, offer)
    total = _portal_cite(rows, portal_rows, "Total ofertado: $ 535.000", am.PortalKind.TOTAL, 7)
    cuit = _portal_cite(rows, portal_rows, "CUIT 30-00000000-0", am.PortalKind.CUIT, 8)
    assert ev._portal_cite_is_literal(total, offer) and ev._portal_cite_is_literal(cuit, offer)
    pair = _portal_pair()
    record = ev.measure_pair(pair, rows.result, rows.requirement, offer, ev.PageFinder(), [], {})
    assert (record["citas_portal"], record["citas_portal_literales"]) == (4, 3)
    totals = ev.aggregate([{"records": [record], "timings": {}, "steps": {
        "pedidos": 0, "tokens_pedido": 0, "tokens_salida": 0}, "unread_pages": 0,
        "discard_ok": None}])
    assert totals["portal_literal"] == {"ok": 3, "total": 4, "rate": 0.75}
    assert any("Portal" in line for line in ev.blocking(totals))
    assert ev.portal_value_in("garantia", "$ 26.750,00", "26750")
    assert not ev.portal_value_in("garantia", "$ 26.750,00", "2675")


# --- Umbral y campos ---------------------------------------------------------------------------


@pytest.mark.decision_literal
def test_the_case_00_threshold_is_more_than_80_percent_with_zero_contradictions():
    """REQ-052: el umbral del caso-00 es más del 80 % (no «80 % o más»), 0 contradicciones y
    100 % de citas literales; 40 de 49 llega y 39 de 49 no; el caso chico sigue en 100 %."""
    assert ev.thresholds_for("caso-00")["match"] == (0.80, True)
    assert ev.thresholds_for("caso-00")["contradictions"] == (0, True)
    assert ev.thresholds_for("caso-00")["literal"] == (1.0, True)
    assert ev.thresholds_for("caso-chico-evaluacion")["match"] == (1.0, True)

    def totals(ok, total=49):
        zero = {"ok": 0, "total": 0, "rate": None}
        return {"match": ev.ratio(ok, total), "contradictions": [], "no_citation": [],
                "literal": {"ok": 5, "total": 5, "rate": 1.0}, "missing_document": zero,
                "questions": zero, "fragments": zero, "portal_literal": zero,
                "matrix": {"ok": 49, "total": 49, "rate": 1.0}}
    assert ev.blocking(totals(40), "caso-00") == []
    assert len(ev.blocking(totals(39), "caso-00")) == 1
    assert "más de" in ev.blocking(totals(39), "caso-00")[0]
    assert ev.blocking(totals(8, 10), "caso-00") != []   # 80,0 %: no es «más de 80 %»


def _list_with(tmp_path, mutate):
    raw = yaml.safe_load(LIST.read_text(encoding="utf-8"))
    mutate(raw)
    path = tmp_path / "lista.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


@pytest.mark.decision_literal
def test_a_list_pair_without_the_fields_of_its_type_refuses_the_measurement(
        db, operator_user, fake_ai, tmp_path):
    """REQ-052, REQ-061, REQ-064: una fila técnica sin `documento_tecnico` o `renglon_ofertado`
    y un «no se pudo leer» sin `ilegible` rechazan la medición con el motivo (sin nombrar a los
    oferentes); un valor inválido rechaza la lectura de la lista."""
    def strip(raw):
        entries = raw["ofertas"][0]["requisitos"]
        entries[7].pop("documento_tecnico")
        entries[8].pop("renglon_ofertado")
        raw["ofertas"][1]["requisitos"][3].pop("ilegible")

    expected = ev.load_expected(_list_with(tmp_path, strip))
    problems = ev.check_fields(expected)
    assert problems == [
        "oferta 1, M-008: fila técnica sin `documento_tecnico`",
        "oferta 1, M-009: fila técnica sin `renglon_ofertado`",
        "oferta 2, M-004: «no se pudo leer» sin `ilegible` (documento y página)"]
    assert all("Sintético" not in p for p in problems)
    procedure, offers = ev.build_case(operator_user, expected, folder=CASO_CHICO)
    with pytest.raises(ev.MeasurementRefused, match="campos de la regla nueva"):
        ev.measure(operator_user, procedure, expected, offers, tmp_path)
    for field, value in (("documento_tecnico", "quizas"), ("renglon_ofertado", "tal vez")):
        def invalid(raw, field=field, value=value):
            raw["ofertas"][0]["requisitos"][7][field] = value
        with pytest.raises(ev.ExpectedError, match=field):
            ev.load_expected(_list_with(tmp_path, invalid))

    def bad_portal(raw):
        raw["ofertas"][0]["requisitos"][5]["portal"] = {"tipo": "otro", "valor": "1"}
    with pytest.raises(ev.ExpectedError, match="portal"):
        ev.load_expected(_list_with(tmp_path, bad_portal))

    def bad_unreadable(raw):
        raw["ofertas"][1]["requisitos"][3]["ilegible"] = {"documento": "x.pdf"}
    with pytest.raises(ev.ExpectedError, match="ilegible"):
        ev.load_expected(_list_with(tmp_path, bad_unreadable))


@pytest.mark.decision_literal
def test_a_dictamen_list_with_the_new_fields_is_read(tmp_path):
    """REQ-052, REQ-061, REQ-062, REQ-064: una lista del dictamen INVENTADA con los campos
    nuevos se lee (fila técnica, ilegible y Portal); una lista vieja, sin ellos, se lee pero
    `check_fields` dice qué le falta."""
    entries = [
        {"requisito": "M-047", "dictamen": "cumple", "base": "tecnica",
         "documento_tecnico": "hay", "renglon_ofertado": "si"},
        {"requisito": "M-051", "dictamen": "no_cumple", "base": "tecnica",
         "documento_tecnico": "hay", "renglon_ofertado": "no"},
        {"requisito": "M-019", "dictamen": "cumple", "base": "oferta",
         "ilegible": {"documento": "pagare.pdf", "pagina": 1}},
        {"requisito": "M-024", "dictamen": "cumple", "base": "oferta",
         "portal": {"tipo": "cotizacion", "valor": "1500"}},
        {"requisito": "M-008", "dictamen": "cumple", "base": "externa"}]
    raw = {"caso": "caso-00", "visto_bueno": "Coordinador, fecha inventada",
           "matriz": {"procedimiento": "P-1"},
           "ofertas": [{"oferente": "Uno", "descartada": "parcial", "requisitos": entries}]}
    path = tmp_path / "dictamen-esperado.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    expected = ev.load_expected(path)
    pairs = {p.requirement: p for p in expected.offers[0].pairs}
    assert [pairs[r].kind for r in ("M-047", "M-051", "M-019", "M-024", "M-008")] == [
        "tecnico", "tecnico", "ilegible", "portal", "externo"]
    assert (pairs["M-051"].technical_document, pairs["M-051"].offered,
            pairs["M-051"].dictamen) == ("hay", "no", "no_cumple")
    assert pairs["M-019"].unreadable == {"documento": "pagare.pdf", "pagina": 1}
    assert pairs["M-024"].portal == {"tipo": "cotizacion", "valor": "1500"}
    assert ev.check_fields(expected) == []
    del entries[0]["documento_tecnico"]
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    assert ev.check_fields(ev.load_expected(path)) == [
        "oferta 1, M-047: fila técnica sin `documento_tecnico`"]


# --- --verificar-decisiones ------------------------------------------------------------------------


class _Done:
    def __init__(self, code, out=""):
        self.returncode, self.stdout, self.stderr = code, out, ""


def test_the_decision_tests_run_by_their_marker_and_a_failure_is_not_absence():
    """REQ-052: se corren los tests con la marca `decision_literal`; 0 es ok, 5 (ninguno) es
    ausente y no bloquea, cualquier otro código es fallo."""
    seen = []
    codes = [0, 5, 1, 2]

    def runner(command, **kwargs):
        seen.append(command)
        return _Done(codes.pop(0), "salida")

    assert [ev.run_decision_tests(runner)[0] for _ in range(4)] == [
        "ok", "ausente", "fallo", "fallo"]
    assert all("-m" in c and ev.DECISION_MARK in c for c in seen)

    def broken(command, **kwargs):
        raise OSError("sin pytest")
    assert ev.run_decision_tests(broken)[0] == "fallo"


def _command(operator_user, monkeypatch, *args):
    from tests.tenders.conftest import TEST_PASSWORD
    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    out = StringIO()
    call_command("medir_evaluacion", "--usuario", operator_user.username,
                 "--verificar-decisiones", *args, stdout=out)
    return out.getvalue()


def test_verify_decisions_passes_with_green_tests_and_a_complete_list(
        db, operator_user, monkeypatch):
    """REQ-052: `--verificar-decisiones` con los tests en verde y la lista completa informa y no
    falla; no usa el modelo."""
    monkeypatch.setattr(ev, "run_decision_tests", lambda *a, **k: ("ok", "12 passed"))
    text = _command(operator_user, monkeypatch, "--caso-chico")
    assert "decision_literal: ok" in text and "trae los campos nuevos" in text


def test_verify_decisions_with_no_marked_test_informs_and_does_not_block(
        db, operator_user, monkeypatch):
    """REQ-052: si todavía ningún test lleva la marca, lo informa y no bloquea."""
    monkeypatch.setattr(ev, "run_decision_tests", lambda *a, **k: ("ausente", ""))
    text = _command(operator_user, monkeypatch, "--caso-chico")
    assert "ausente" in text and "no bloquea" in text


def test_verify_decisions_rejects_a_failing_test_or_a_list_without_the_fields(
        db, operator_user, monkeypatch, tmp_path):
    """REQ-052: un test de decisión que falla, o una lista sin los campos nuevos, rechazan la
    medición (error)."""
    monkeypatch.setattr(ev, "run_decision_tests", lambda *a, **k: ("fallo", "1 failed"))
    with pytest.raises(CommandError, match="falla"):
        _command(operator_user, monkeypatch, "--caso-chico")
    monkeypatch.setattr(ev, "run_decision_tests", lambda *a, **k: ("ok", ""))

    def strip(raw):
        raw["ofertas"][0]["requisitos"][7].pop("renglon_ofertado")
    path = _list_with(tmp_path, strip)
    with pytest.raises(CommandError, match="regla nueva"):
        _command(operator_user, monkeypatch, "--esperada", str(path))
