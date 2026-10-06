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
from tests.assessment.fakes import CASO_CHICO, model, says  # noqa: F401 - `model` es fixture

pytestmark = pytest.mark.django_db

LIST = CASO_CHICO / "evaluacion-esperada.yaml"


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
        entry = by_bidder[bidder][number]
        if change is not None:
            other = change(bidder, entry["requisito"], entry, call)
            if other is not None:
                return other
        result = entry["resultado"]
        if result in ("cumple", "no_cumple"):
            quotes = [quote_of(call, c["ancla"]) for c in entry["citas"]]
            return says(result, *[q for q in quotes if q is not None])
        if entry.get("motivo") == "falta_hoja_compliance":
            return says("no_determinado", external=True)
        return says("no_consta", exigence="documento")

    return oracle


def measured(user, model_, tmp_path, *, change=None, fichas=None):
    expected = ev.load_expected(LIST)
    procedure, offers = ev.build_case(user, expected)
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
    assert verification.counts["anchors"] == 24 and verification.counts["unreadable_pages"] == 1
    expected.offers[0].pairs[0].citations[0]["ancla"] = "Un texto que no figura en la página"
    assert not ev.verify_expected(expected, offers).ok


def test_a_model_that_follows_the_list_reaches_the_threshold(db, operator_user, fake_ai, model,
                                                            tmp_path):
    """REQ-052 a REQ-055, REQ-059, REQ-060: con un modelo que contesta lo esperado, todas las
    medidas del caso chico llegan al umbral y la corrida guarda sus cuatro archivos."""
    report, _, _ = measured(operator_user, model, tmp_path)
    total = report.total
    assert report.blocking == [], report.blocking
    assert total["pairs"] == 30 and total["match"]["ok"] == 30
    assert total["contradictions"] == [] and total["no_citation"] == []
    assert total["literal"]["ok"] == total["literal"]["total"] > 0
    assert total["missing_document"] == {"ok": 1, "total": 1, "rate": 1.0}
    assert total["questions"] == {"ok": 5, "total": 5, "rate": 1.0}
    assert total["matrix"]["ok"] == 30
    assert total["by_outcome"] == {"cumple": 22, "no_cumple": 2, "no_determinado": 5,
                                   "sin_documento": 1}
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
    assert "Cumple el umbral." in public


def test_a_cumple_where_the_list_says_no_cumple_is_a_contradiction(db, operator_user, fake_ai,
                                                                  model, tmp_path):
    """REQ-052: un "cumple" donde se espera "no cumple" cuenta como contradicción, baja la
    coincidencia y bloquea la aceptación."""
    def wrong(bidder, requirement, entry, call):
        if requirement == "M-008" and bidder.startswith("Oferente C"):
            return says("cumple", call.quote("Gramaje 70 g/m²"))
        return None

    report, _, _ = measured(operator_user, model, tmp_path, change=wrong)
    total = report.total
    assert total["contradictions"] == [("M-008", "no_cumple", "cumple")]
    assert total["match"]["ok"] == 29
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
    assert total["match"]["ok"] == 29
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
    assert fragments["total"] == 22 + 2 and fragments["ok"] == fragments["total"]


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
    assert "Bloquea la aceptación: nada" in text and "Corrida guardada en" in text
    with pytest.raises(CommandError):
        call_command("medir_evaluacion", "--usuario", operator_user.username,
                     stdout=StringIO())
