"""Corrida del conjunto de preguntas y medidas de las exigencias (T-039; plan 001, "Evals").

`evaluation.run` lee los casos `EV-NNN.yaml` de una carpeta, corre con la función de
consulta de la pantalla (`services.ask`, canal `eval`) los que están bien formados y
tienen visto bueno, mide las cuatro exigencias de la spec y las comprobaciones de pares
(REQ-020) y de aviso (REQ-021), y guarda la corrida en una carpeta propia.

Los casos son sintéticos (P4) y están en `tests/fixtures/evals/t039-*`. Se responden
con los dos regímenes de prueba de `two_regimes` (T-009) y con los dobles de los tres
clientes de IA; los dobles de reranker y generación se ajustan acá para que cada
pregunta tenga su propio comportamiento. Las corridas se guardan en una carpeta
temporal.
"""

import json
import re
from datetime import date
from io import StringIO
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import CommandError, call_command

from evaluon.accounts import permissions
from evaluon.ai import ServiceUnavailableError
from evaluon.ai import generation as generation_client
from evaluon.ai import reranker as reranker_client
from evaluon.audit.models import AuditEvent, Channel, EventType
from evaluon.queries import evaluation, services
from evaluon.queries.models import Query

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "evals"
REAL_CASES = Path(settings.BASE_DIR) / "evals" / "casos"

TEST_PASSWORD = "clave-sintetica-de-prueba"  # la de tests/conftest.py

N247 = "Disposición AFIP 247/2022"
N297 = "Disposición AFIP 297/03"

# Preguntas de los casos sintéticos.
Q1 = "¿Cuál es el objeto del régimen sintético?"
Q2 = "¿Qué garantías sintéticas se piden?"
Q3 = "¿Cuántos días de licencia sintética corresponden?"
Q4 = "¿Cuál es la alícuota sintética del impuesto?"
QP = "¿Qué objeto tiene el régimen sintético de contrataciones?"

# Marcas del texto de las unidades de `two_regimes`, para el reranker.
OLD_OBJECT = "Objeto del régimen sintético anterior"
NEW_OBJECT = "OBJETO. Régimen sintético vigente"


@pytest.fixture
def scripted(monkeypatch, fake_ai):
    """Dobles ajustados por pregunta.

    - `marks[pregunta]`: puntaje del reranker para cada marca de texto; lo que no tiene
      marca puntúa 0. Una pregunta sin entrada no alcanza el umbral.
    - `failing`: preguntas para las que la generación falla con el servicio caído.
    Lo demás lo responde el doble de generación de `tests/conftest.py`, que cita el
    primer alias que se le muestra.
    """
    marks = {}
    failing = set()

    def rerank(query, documents):
        scores = marks.get(query, {})
        return [max([s for mark, s in scores.items() if mark in document], default=0.0)
                for document in documents]

    delegate = fake_ai.generation.generate

    def generate(messages, schema):
        content = "\n".join(str(m.get("content", "")) for m in messages)
        if any(question in content for question in failing):
            raise ServiceUnavailableError("generation: falla simulada", service="generation")
        return delegate(messages, schema)

    monkeypatch.setattr(reranker_client, "rerank", rerank)
    monkeypatch.setattr(generation_client, "generate", generate)
    return type("Scripted", (), {"marks": marks, "failing": failing})


def fake_clock(*values):
    """Reloj que devuelve `values` en orden: dos lecturas por caso corrido."""
    iterator = iter(values)
    return lambda: next(iterator)


def run(user, folder, runs_dir, **kwargs):
    kwargs.setdefault("commit", "abc1234")
    return evaluation.run(user, FIXTURES / folder, runs_dir, **kwargs)


def by_id(report):
    return {line["id"]: line for line in report.results}


# --- Las cuatro medidas exigidas -----------------------------------------------------


def test_four_synthetic_cases_give_the_expected_measures(
    read_user, two_regimes, scripted, tmp_path
):
    """REQ-008, REQ-009: con un acierto, una cita equivocada, una abstención correcta y
    una falla técnica, la cita literal da 2 de 2, la respuesta correcta 1 de 2, la
    abstención 1 de 2 (la falla técnica no cuenta como abstención) y el tiempo, la
    mediana y el máximo de los cuatro."""
    scripted.marks[Q1] = {NEW_OBJECT: 0.9}
    scripted.marks[Q2] = {NEW_OBJECT: 0.9}  # recupera el artículo 1, no el 2
    scripted.marks[Q4] = {NEW_OBJECT: 0.9}
    scripted.failing.add(Q4)

    report = run(read_user, "t039-medidas", tmp_path,
                 clock=fake_clock(0, 2, 10, 13, 20, 21, 30, 38))

    lines = by_id(report)
    assert lines["EV-901"]["status"] == "grounded"
    assert lines["EV-901"]["measures"]["correct"] is True
    assert lines["EV-902"]["status"] == "grounded"
    assert lines["EV-902"]["measures"]["correct"] is False
    assert lines["EV-902"]["measures"]["missing_units"] == [
        {"norma": N247, "key": "anexo/art-2"}
    ]
    assert lines["EV-903"]["status"] == "undetermined"
    assert lines["EV-903"]["measures"]["abstained"] is True
    assert lines["EV-904"]["status"] == "error"
    assert lines["EV-904"]["measures"]["abstained"] is False

    measures = report.measures
    assert measures["literal_citation"]["ok"] == 2
    assert measures["literal_citation"]["total"] == 2
    assert measures["literal_citation"]["meets"] is True
    assert (measures["correct_answer"]["ok"], measures["correct_answer"]["total"]) == (1, 2)
    assert measures["correct_answer"]["rate"] == 0.5
    assert measures["correct_answer"]["meets"] is False
    assert (measures["abstention"]["ok"], measures["abstention"]["total"]) == (1, 2)
    assert measures["abstention"]["meets"] is False
    assert measures["response_time"]["median"] == 2.5
    assert measures["response_time"]["max"] == 8
    assert measures["response_time"]["meets"] is True


def test_right_unit_with_the_wrong_regime_is_incorrect(
    read_user, two_regimes, scripted, tmp_path
):
    """REQ-020: una respuesta que cita la unidad esperada pero con un régimen aplicado
    distinto del de `regimen` cuenta como incorrecta."""
    scripted.marks[Q1] = {NEW_OBJECT: 0.9}

    report = run(read_user, "t039-regimen", tmp_path)

    line = by_id(report)["EV-921"]
    assert line["status"] == "grounded"
    assert line["regime"] == [N247]
    assert line["measures"]["checks"]["units"] is True
    assert line["measures"]["checks"]["regime"] is False
    assert line["measures"]["correct"] is False
    assert report.measures["correct_answer"]["ok"] == 0


# --- Pares de REQ-020 ------------------------------------------------------------------


def test_pair_passes_when_each_case_cites_its_regime(
    read_user, two_regimes, scripted, tmp_path
):
    """REQ-020: un par con la misma pregunta y dos fechas pasa cuando cada caso pasa por
    su cuenta y cita su régimen: la 297/03 antes del cambio y la 247/2022 después."""
    scripted.marks[QP] = {OLD_OBJECT: 0.9, NEW_OBJECT: 0.9}

    report = run(read_user, "t039-par-bien", tmp_path)

    lines = by_id(report)
    assert [u["norm"] for u in lines["EV-931"]["cited_units"]] == [N297]
    assert [u["norm"] for u in lines["EV-932"]["cited_units"]] == [N247]
    assert report.pairs == [
        {"cases": ["EV-931", "EV-932"], "status": "pasa", "problems": []}
    ]


def test_pair_fails_when_both_cases_cite_the_same_norm(
    read_user, two_regimes, scripted, tmp_path
):
    """REQ-020: un par cuyos dos casos citan la misma norma falla, aunque cada caso pase
    por su cuenta."""
    scripted.marks[QP] = {OLD_OBJECT: 0.9, NEW_OBJECT: 0.9}

    report = run(read_user, "t039-par-mal", tmp_path)

    lines = by_id(report)
    assert lines["EV-941"]["measures"]["correct"] is True
    assert lines["EV-942"]["measures"]["correct"] is True
    [pair] = report.pairs
    assert pair["cases"] == ["EV-941", "EV-942"]
    assert pair["status"] == "falla"
    assert pair["problems"] == ["los dos casos citan las mismas normas"]


def test_pair_with_a_partner_that_did_not_run_is_incomplete():
    """REQ-020: un par del que se corrió un solo caso se informa como incompleto, no
    como aprobado."""
    line = {"id": "EV-001", "question": "¿Pregunta?", "pair": "EV-016",
            "passed": True, "cited_units": [{"norm": N247}]}

    assert evaluation.check_pairs([line]) == [
        {"cases": ["EV-001", "EV-016"], "status": "incompleto",
         "problems": ["EV-016 no se corrió"]}
    ]


# --- Aviso de REQ-021 ------------------------------------------------------------------


def test_case_expecting_the_notice_fails_without_it(
    read_user, two_regimes, scripted, tmp_path
):
    """REQ-021: un caso con `aviso_modificatorias` verdadero falla la comprobación de
    aviso si el resultado no trae el aviso en `notices`."""
    scripted.marks[Q1] = {NEW_OBJECT: 0.9}

    report = run(read_user, "t039-aviso", tmp_path)

    line = by_id(report)["EV-951"]
    assert line["notices"] == []
    assert line["measures"]["notice_ok"] is False
    assert report.notices == {"ok": 0, "total": 1, "failed": ["EV-951"]}
    assert "EV-951" in report.failed_ids()


@pytest.mark.parametrize("expected, notices, ok", [
    (True, [{"type": "pending_amendments", "norm": 1, "name": N297, "pending": 32}], True),
    (True, [], False),
    (False, [], True),
    (False, [{"type": "pending_amendments", "norm": 1, "name": N297, "pending": 2}], False),
])
def test_notice_check_follows_the_case(expected, notices, ok):
    """REQ-021: la comprobación de aviso pasa si el resultado trae el aviso de
    modificatorias sin cargar exactamente cuando el caso lo pide."""
    assert evaluation.notice_ok(expected, {"notices": notices}) is ok


# --- Fecha, canal y filtro de casos ----------------------------------------------------


def test_query_function_receives_the_case_date_and_the_eval_channel(
    read_user, two_regimes, scripted, tmp_path, monkeypatch
):
    """REQ-020: la corrida llama a la función de consulta de la pantalla con la
    `fecha_autorizacion` de cada caso y el canal `eval`, una pregunta por vez."""
    scripted.marks[QP] = {OLD_OBJECT: 0.9, NEW_OBJECT: 0.9}
    received = []
    original = services.ask

    def spy(user, question, reference_date=None, *, channel=Channel.SCREEN):
        received.append((question, reference_date, channel))
        return original(user, question, reference_date, channel=channel)

    monkeypatch.setattr(services, "ask", spy)

    run(read_user, "t039-par-bien", tmp_path)

    assert received == [
        (QP, date(2021, 3, 15), Channel.EVAL),
        (QP, date(2024, 5, 20), Channel.EVAL),
    ]


def test_cases_without_date_or_approval_and_malformed_cases_are_not_run(
    read_user, two_regimes, scripted, tmp_path, monkeypatch
):
    """REQ-020, REQ-008: el caso sin `fecha_autorizacion`, el caso sin visto bueno y los
    casos mal formados no se corren y se informan con su motivo; el caso bien formado y
    con visto bueno se corre. Los archivos que no son `EV-*.yaml` se ignoran."""
    scripted.marks[Q1] = {NEW_OBJECT: 0.9}
    asked = []
    original = services.ask

    def spy(user, question, reference_date=None, *, channel=Channel.SCREEN):
        asked.append(question)
        return original(user, question, reference_date, channel=channel)

    monkeypatch.setattr(services, "ask", spy)

    report = run(read_user, "t039-filtro", tmp_path)

    assert asked == [Q1]
    assert [line["id"] for line in report.results] == ["EV-964"]
    skipped = {s.file: s for s in report.skipped}
    assert set(skipped) == {"EV-961.yaml", "EV-962.yaml", "EV-963.yaml", "EV-965.yaml"}
    assert skipped["EV-961.yaml"].kind == evaluation.MALFORMED
    assert "fecha_autorizacion" in skipped["EV-961.yaml"].reason
    assert skipped["EV-962.yaml"].kind == evaluation.NOT_APPROVED
    assert skipped["EV-963.yaml"].kind == evaluation.MALFORMED
    assert "difieren" in skipped["EV-963.yaml"].reason
    assert skipped["EV-965.yaml"].kind == evaluation.MALFORMED


def test_case_without_date_is_never_asked_with_today(tmp_path):
    """REQ-020: `fecha_autorizacion` no tiene valor por omisión: vacía o ausente, el
    caso se informa como mal formado."""
    text = (FIXTURES / "t039-filtro" / "EV-964.yaml").read_text(encoding="utf-8")
    path = tmp_path / "EV-964.yaml"
    path.write_text(text.replace("fecha_autorizacion: 2024-05-20",
                                 'fecha_autorizacion: ""'), encoding="utf-8")

    cases, skipped = evaluation.load_cases(tmp_path)

    assert cases == []
    assert skipped[0].kind == evaluation.MALFORMED
    assert "fecha_autorizacion" in skipped[0].reason


def test_real_cases_are_well_formed():
    """REQ-020, REQ-021: los casos de `evals/casos/` se leen con este formato sin
    ninguno mal formado (la falta de visto bueno no es un defecto de formato)."""
    cases, skipped = evaluation.load_cases(REAL_CASES)

    assert [s for s in skipped if s.kind == evaluation.MALFORMED] == []
    assert len(cases) + len(skipped) >= 31


# --- Registro y carpeta de la corrida --------------------------------------------------


def test_user_without_read_role_is_rejected_with_the_eval_channel(
    read_user, two_regimes, scripted, tmp_path
):
    """REQ-008 (REQ-016, REQ-012): un usuario sin rol de lectura (desactivado) que corre
    la corrida es rechazado; queda el hecho `rejected` con el canal `eval` y la
    operación de la corrida, y no se corre ningún caso ni se guarda la carpeta."""
    from evaluon.accounts.permissions import RoleRejected

    scripted.marks[Q1] = {NEW_OBJECT: 0.9}
    read_user.is_active = False
    read_user.save()

    with pytest.raises(RoleRejected):
        run(read_user, "t039-aviso", tmp_path)

    [event] = AuditEvent.objects.filter(event_type=EventType.REJECTED)
    assert event.channel == Channel.EVAL
    assert event.user_id == read_user.pk
    assert event.detail["operation"] == "evaluon.queries.evaluation.run"
    assert Query.objects.count() == 0
    assert not AuditEvent.objects.filter(event_type=EventType.QUERY).exists()
    assert list(tmp_path.iterdir()) == []


def test_each_query_of_the_run_is_logged_with_the_eval_channel(
    read_user, two_regimes, scripted, tmp_path
):
    """REQ-008 (P6): cada consulta de la corrida queda en el registro de auditoría con el
    canal `eval`, y su línea de resultados apunta a esa consulta."""
    scripted.marks[Q1] = {NEW_OBJECT: 0.9}
    scripted.marks[Q2] = {NEW_OBJECT: 0.9}
    scripted.marks[Q4] = {NEW_OBJECT: 0.9}
    scripted.failing.add(Q4)

    report = run(read_user, "t039-medidas", tmp_path)

    events = AuditEvent.objects.filter(event_type=EventType.QUERY)
    assert events.count() == 4
    assert set(events.values_list("channel", flat=True)) == {Channel.EVAL}
    query_ids = sorted(line["query_id"] for line in report.results)
    assert query_ids == sorted(Query.objects.values_list("id", flat=True))


def test_run_folder_has_the_three_files(read_user, two_regimes, scripted, tmp_path):
    """REQ-008, REQ-009, REQ-020, REQ-021: la corrida queda en una carpeta con la fecha,
    el commit y el modelo en el nombre, con `parametros.json`, `resultados.jsonl` (un
    renglón por caso) y `resumen.md` (medidas, pares, aviso y casos fallados)."""
    scripted.marks[Q1] = {NEW_OBJECT: 0.9}
    scripted.marks[Q2] = {NEW_OBJECT: 0.9}
    scripted.marks[Q4] = {NEW_OBJECT: 0.9}
    scripted.failing.add(Q4)

    report = run(read_user, "t039-medidas", tmp_path, commit="abc1234")

    folder = report.folder
    assert folder.parent == tmp_path
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{6}_abc1234_"
                        + re.escape(settings.GENERATION_MODEL), folder.name)
    assert sorted(p.name for p in folder.iterdir()) == [
        "parametros.json", "resultados.jsonl", "resumen.md"
    ]

    parameters = json.loads((folder / "parametros.json").read_text(encoding="utf-8"))
    assert parameters["commit"] == "abc1234"
    assert parameters["prompt_version"]
    assert "corpus_version" in parameters
    assert parameters["search"]["generation"]["sha256"] == settings.GENERATION_MODEL_SHA256
    assert parameters["search"]["rerank_threshold"] == settings.RERANK_THRESHOLD

    lines = [json.loads(line) for line in
             (folder / "resultados.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [line["id"] for line in lines] == ["EV-901", "EV-902", "EV-903", "EV-904"]
    for line in lines:
        assert {"status", "cited_units", "measures", "time_seconds"} <= set(line)

    summary = (folder / "resumen.md").read_text(encoding="utf-8")
    for heading in ("## Medidas exigidas", "## Pares de REQ-020",
                    "## Aviso de REQ-021", "## Casos fallados"):
        assert heading in summary
    assert "EV-902" in summary.split("## Casos fallados")[1]
    assert "EV-904" in summary.split("## Casos fallados")[1]


# --- Respuesta correcta: inciso, datos clave y regímenes que difieren ------------------


def make_case(**fields):
    values = {
        "id": "EV-999", "file": "EV-999.yaml", "question": "¿Pregunta sintética?",
        "reference_date": date(2024, 5, 20), "regime": N247, "has_answer": True,
        "units": ((N247, "anexo/art-24/inc-b"),), "key_data": (), "differ": False,
        "pair": "", "notice": False, "approval": "Comisión sintética",
    }
    values.update(fields)
    return evaluation.Case(**values)


def grounded(statements, units):
    return {"status": "grounded", "regime": [{"norm": 2, "name": N247}],
            "notices": [], "statements": statements,
            "units": {str(u["unit"]): {"category": u["category"]} for u in units}}


def cited(unit, key, unit_type="articulo", category="regimen_especifico", norm=N247):
    return {"unit": unit, "norm": norm, "key": key, "unit_type": unit_type,
            "category": category, "literal": True}


def test_citing_the_article_counts_for_an_inciso():
    """REQ-008: si el caso nombra un inciso, vale el artículo que lo contiene; otro
    artículo no vale."""
    case = make_case()
    statement = [{"text": "Respuesta sintética.", "citations": [1]}]

    right = evaluation.grade(case, grounded(statement, [cited(1, "anexo/art-24")]),
                             [cited(1, "anexo/art-24")])
    wrong = evaluation.grade(case, grounded(statement, [cited(1, "anexo/art-2")]),
                             [cited(1, "anexo/art-2")])

    assert right["correct"] is True
    assert wrong["correct"] is False


def test_answer_must_contain_the_key_data():
    """REQ-008: la respuesta correcta contiene los `datos_clave`, sin distinguir
    mayúsculas, tildes ni espacios repetidos."""
    case = make_case(units=((N247, "anexo/art-43"),),
                     key_data=("60 días corridos", "5 días hábiles"))
    unit = cited(1, "anexo/art-43")

    def grade(text):
        return evaluation.grade(
            case, grounded([{"text": text, "citations": [1]}], [unit]), [unit])

    complete = grade("Son 60 Días  corridos y 5 DIAS hábiles.")
    missing = grade("60 días corridos.")

    assert complete["correct"] is True
    assert missing["correct"] is False
    assert missing["missing_key_data"] == [["5 días hábiles"]]


def test_differ_requires_the_flag_and_both_citations():
    """REQ-008 (REQ-019): con `difieren`, la respuesta correcta trae la marca
    `regimes_differ` en una afirmación que cita al régimen específico y al marco
    nacional."""
    case = make_case(units=((N247, "anexo/art-1"),), differ=True)
    specific = cited(1, "anexo/art-1")
    national = cited(2, "art-5", category="marco_nacional", norm="Ley sintética 1/2000")
    units = [specific, national]

    def grade(statement):
        return evaluation.grade(case, grounded([statement], units), units)

    with_both = grade({"text": "Difieren.", "regimes_differ": True, "citations": [1, 2]})
    without_flag = grade({"text": "Difieren.", "regimes_differ": False,
                          "citations": [1, 2]})
    one_citation = grade({"text": "Difieren.", "regimes_differ": True, "citations": [1]})

    assert with_both["correct"] is True
    assert without_flag["correct"] is False
    assert one_citation["correct"] is False


# --- Comando ---------------------------------------------------------------------------


def call(*args, password=TEST_PASSWORD, monkeypatch=None):
    monkeypatch.setattr(permissions, "read_password", lambda prompt: password)
    out = StringIO()
    call_command("correr_evals", *args, stdout=out, stderr=StringIO())
    return out.getvalue()


def test_command_without_approved_cases_runs_nothing_and_says_so(
    read_user, fake_ai, tmp_path, monkeypatch
):
    """REQ-008: si ningún caso tiene visto bueno, `correr_evals` no corre ninguno, lo
    informa con claridad y termina sin error, dejando la corrida registrada con un
    renglón por caso no corrido."""
    output = call("--usuario", read_user.username,
                  "--casos", str(FIXTURES / "t039-sin-visto-bueno"),
                  "--corridas", str(tmp_path), "--commit", "abc1234",
                  monkeypatch=monkeypatch)

    assert "No se corrió ningún caso" in output
    assert "2 sin visto bueno" in output
    assert Query.objects.count() == 0
    [folder] = list(tmp_path.iterdir())
    summary = (folder / "resumen.md").read_text(encoding="utf-8")
    assert "No se corrió ningún caso" in summary
    lines = [json.loads(line) for line in
             (folder / "resultados.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(line["id"], line["ran"], line["skipped"]) for line in lines] == [
        ("EV-971", False, evaluation.NOT_APPROVED),
        ("EV-972", False, evaluation.NOT_APPROVED),
    ]


def test_command_runs_the_cases_with_the_read_role(
    read_user, two_regimes, scripted, tmp_path, monkeypatch
):
    """REQ-008: `correr_evals` con rol de lectura, `--usuario` y clave por teclado corre
    los casos y muestra las medidas y la carpeta de la corrida."""
    scripted.marks[Q1] = {NEW_OBJECT: 0.9}

    output = call("--usuario", read_user.username,
                  "--casos", str(FIXTURES / "t039-aviso"),
                  "--corridas", str(tmp_path), "--commit", "abc1234",
                  monkeypatch=monkeypatch)

    [folder] = list(tmp_path.iterdir())
    assert str(folder) in output
    assert "Respuesta correcta" in output
    assert Query.objects.get().event.channel == Channel.EVAL


def test_command_with_a_wrong_password_runs_nothing(read_user, fake_ai, tmp_path,
                                                     monkeypatch):
    """REQ-008: con una clave incorrecta el comando se rechaza con el mensaje único y no
    corre ni guarda nada."""
    with pytest.raises(CommandError, match="Usuario o clave incorrectos"):
        call("--usuario", read_user.username,
             "--casos", str(FIXTURES / "t039-aviso"),
             "--corridas", str(tmp_path), password="otra-clave-incorrecta-123",
             monkeypatch=monkeypatch)

    assert list(tmp_path.iterdir()) == []
    assert Query.objects.count() == 0


# --- Ajustes de la verificación ---------------------------------------------------------


def test_literal_citation_fails_when_the_stored_unit_text_differs(
    read_user, two_regimes, scripted, tmp_path
):
    """REQ-008: si `Unit.text` de la unidad citada no es igual a
    `canonical_text[char_start:char_end]` (datos guardados que se apartan del original),
    la cita no cuenta como literal y la medida no cumple."""
    from evaluon.norms.models import Unit

    scripted.marks[Q1] = {NEW_OBJECT: 0.9}
    unit = two_regimes.new_units["anexo/art-1"]
    Unit.objects.filter(pk=unit.pk).update(text="TEXTO ALTERADO QUE NO ESTA EN LA NORMA")

    report = run(read_user, "t039-aviso", tmp_path)

    line = by_id(report)["EV-951"]
    [cited_unit] = line["cited_units"]
    assert cited_unit["stored_text_ok"] is False
    assert cited_unit["shown_text_ok"] is True
    assert cited_unit["literal"] is False
    assert (line["measures"]["literal_citations"], line["measures"]["citations"]) == (0, 1)
    assert report.measures["literal_citation"]["meets"] is False
    summary = (report.folder / "resumen.md").read_text(encoding="utf-8")
    assert "cita que no es literal" in summary.split("## Casos fallados")[1]


def test_literal_citation_fails_when_the_shown_text_differs(
    read_user, two_regimes, scripted, tmp_path, monkeypatch
):
    """REQ-008: si el texto que entrega `answering.citation_texts` para mostrar no es el
    recorte canónico, la cita no cuenta como literal."""
    from evaluon.queries import answering

    scripted.marks[Q1] = {NEW_OBJECT: 0.9}
    monkeypatch.setattr(answering, "citation_texts",
                        lambda result: {int(u): "otro texto" for u in result["units"]})

    report = run(read_user, "t039-aviso", tmp_path)

    [cited_unit] = by_id(report)["EV-951"]["cited_units"]
    assert cited_unit["stored_text_ok"] is True
    assert cited_unit["shown_text_ok"] is False
    assert report.measures["literal_citation"]["ok"] == 0


def key_data_ok(key, answer):
    case = make_case(units=((N247, "anexo/art-55"),), key_data=(key,))
    unit = cited(1, "anexo/art-55")
    measures = evaluation.grade(
        case, grounded([{"text": answer, "citations": [1]}], [unit]), [unit])
    return measures["checks"]["key_data"]


@pytest.mark.parametrize("key, answer", [
    ("no", "Sí, el pliego puede agregar causales propias, según la norma."),
    ("sí", "No. El pliego no puede agregar causales de inadmisibilidad."),
    ("1 %", "La multa es del 0,1 % por día."),
    ("10 días", "El plazo es de 110 días."),
    ("1.000", "El monto es de 21.000 pesos."),
])
def test_key_data_needs_word_and_number_boundaries(key, answer):
    """REQ-008: un dato clave no se cumple si aparece pegado a una letra, un dígito o un
    separador de número ("no" dentro de "norma", "si" dentro de "inadmisibilidad",
    "1 %" dentro de "0,1 %")."""
    assert key_data_ok(key, answer) is False


def test_key_data_at_the_end_of_a_sentence_is_found():
    """REQ-008: el punto o la coma que cierran una frase no cuentan como pegados al
    dato: solo un separador seguido o precedido de dígito."""
    assert key_data_ok("60 días corridos", "Son 60 días corridos.") is True
    assert key_data_ok("5 %", "Es el 5 %, sobre el total.") is True


@pytest.mark.parametrize("key, answer, ok", [
    ("sí", "Sí, el pliego puede hacerlo.", True),
    ("sí", "—¡Sí! Puede hacerlo.", True),
    ("sí", "El pliego sí puede hacerlo.", False),
    ("no", "No. El pliego no puede hacerlo.", True),
    ("no", "«No», según el artículo.", True),
    ("no", "El pliego no puede hacerlo.", False),
    ("no", "Nunca puede hacerlo.", False),
])
def test_yes_or_no_key_data_is_how_the_first_statement_starts(key, answer, ok):
    """REQ-008: un dato clave "sí" o "no" se cumple solo si la primera afirmación empieza
    con esa palabra, salteando signos de puntuación iniciales."""
    assert key_data_ok(key, answer) is ok


def test_yes_or_no_looks_only_at_the_first_statement():
    """REQ-008: "sí" o "no" se mira en la primera afirmación, no en las siguientes."""
    case = make_case(units=((N247, "anexo/art-55"),), key_data=("no",))
    unit = cited(1, "anexo/art-55")
    statements = [{"text": "Sí, puede.", "citations": [1]},
                  {"text": "No hace falta otra cosa.", "citations": [1]}]

    measures = evaluation.grade(case, grounded(statements, [unit]), [unit])

    assert measures["checks"]["key_data"] is False


@pytest.mark.parametrize("key, answer", [
    ("60 días corridos", "Sesenta (60) días corridos desde la apertura."),
    ("60 días corridos", "SESENTA ( 60 ) DÍAS CORRIDOS."),
    ("SESENTA (60) días", "Son 60 días."),
    ("5 %", "El cinco por ciento (5%) del monto ofertado."),
])
def test_number_in_words_with_its_figure_counts_as_the_figure(key, answer):
    """REQ-008: un número escrito en letras seguido de la cifra entre paréntesis vale
    como la cifra, en la respuesta y en el dato clave."""
    assert key_data_ok(key, answer) is True


@pytest.mark.parametrize("key, answer", [
    ("5 %", "El 5% del monto."),
    ("5%", "El 5 % del monto."),
])
def test_percent_with_or_without_space_is_the_same(key, answer):
    """REQ-008: "5%" y "5 %" son el mismo dato."""
    assert key_data_ok(key, answer) is True


@pytest.mark.parametrize("key, answer", [
    ("presidente y 2 vocales", "Un presidente y dos vocales."),
    ("3 días", "Dentro de los tres días."),
    ("20 días", "En veinte días hábiles."),
    ("dos vocales", "Con 2 vocales."),
])
def test_numbers_one_to_twenty_in_words_equal_their_figure(key, answer):
    """REQ-008: los números del uno al veinte escritos en letras equivalen a su cifra."""
    assert key_data_ok(key, answer) is True


def test_case_accents_and_repeated_spaces_are_ignored():
    """REQ-008: mayúsculas, tildes y espacios repetidos no cuentan."""
    assert key_data_ok("60 días corridos", "Son 60 DIAS    Corridos.") is True
    assert key_data_ok("prórroga automática", "Hay PRORROGA automatica.") is True


def test_refused_case_stays_in_the_measures(read_user, two_regimes, scripted, tmp_path):
    """REQ-009, REQ-008: un caso que la consulta rechaza (fecha posterior al día) no sale
    de la medida: sin respuesta cuenta como no abstenido y con respuesta como incorrecto,
    y el resumen lo marca."""
    cases = tmp_path / "casos"
    cases.mkdir()
    for name in ("EV-901", "EV-903"):
        text = (FIXTURES / "t039-medidas" / f"{name}.yaml").read_text(encoding="utf-8")
        (cases / f"{name}.yaml").write_text(text.replace("2024-05-20", "2099-01-01"),
                                            encoding="utf-8")

    report = evaluation.run(read_user, cases, tmp_path / "corridas", commit="x")

    lines = by_id(report)
    assert lines["EV-901"]["status"] == evaluation.REFUSED
    assert lines["EV-901"]["measures"]["correct"] is False
    assert lines["EV-903"]["measures"]["abstained"] is False
    assert (report.measures["correct_answer"]["ok"],
            report.measures["correct_answer"]["total"]) == (0, 1)
    assert (report.measures["abstention"]["ok"],
            report.measures["abstention"]["total"]) == (0, 1)
    assert report.skipped == []
    summary = (report.folder / "resumen.md").read_text(encoding="utf-8")
    failed = summary.split("## Casos fallados")[1]
    assert "EV-901: consulta rechazada" in failed
    assert "EV-903: consulta rechazada" in failed


@pytest.mark.parametrize("value, approved", [
    ('""', False),
    ('"pendiente"', False),
    ('"Pendiente "', False),
    ('"NO"', False),
    ('"no"', False),
    ("", False),
    ('"Comisión sintética, 2026-10-03"', True),
])
def test_empty_pending_or_no_is_not_an_approval(tmp_path, value, approved):
    """REQ-008: vacío, "pendiente" o "no" (sin distinguir mayúsculas) no son visto
    bueno: el caso no se corre."""
    text = (FIXTURES / "t039-filtro" / "EV-964.yaml").read_text(encoding="utf-8")
    text = re.sub(r"(?m)^visto_bueno: .*$", f"visto_bueno: {value}", text)
    (tmp_path / "EV-964.yaml").write_text(text, encoding="utf-8")

    cases, skipped = evaluation.load_cases(tmp_path)

    assert (len(cases) == 1) is approved
    if not approved:
        assert skipped[0].kind == evaluation.NOT_APPROVED


def test_pair_with_different_questions_fails():
    """REQ-020: un par cuyos casos tienen preguntas distintas falla, aunque cada uno pase
    y citen normas distintas."""
    lines = [
        {"id": "EV-001", "question": "¿Pregunta uno?", "pair": "EV-016", "passed": True,
         "cited_units": [{"norm": N247}]},
        {"id": "EV-016", "question": "¿Pregunta dos?", "pair": "EV-001", "passed": True,
         "cited_units": [{"norm": N297}]},
    ]

    assert evaluation.check_pairs(lines) == [
        {"cases": ["EV-001", "EV-016"], "status": "falla",
         "problems": ["las preguntas no son iguales"]}
    ]


def test_citing_an_inciso_does_not_count_for_the_article():
    """REQ-008: si el caso espera el artículo y la respuesta cita solo uno de sus
    incisos, no vale."""
    case = make_case(units=((N247, "anexo/art-24"),))
    inciso = cited(1, "anexo/art-24/inc-b", unit_type="inciso")
    statement = [{"text": "Respuesta sintética.", "citations": [1]}]

    measures = evaluation.grade(case, grounded(statement, [inciso]), [inciso])

    assert measures["checks"]["units"] is False
    assert measures["correct"] is False


def test_case_over_thirty_seconds_does_not_meet_the_time(
    read_user, two_regimes, scripted, tmp_path
):
    """REQ-008: una consulta de más de 30 segundos hace que la medida de tiempo no
    cumpla y el caso figure entre los fallados."""
    scripted.marks[QP] = {OLD_OBJECT: 0.9, NEW_OBJECT: 0.9}

    report = run(read_user, "t039-par-bien", tmp_path, clock=fake_clock(0, 31, 40, 41))

    assert report.measures["response_time"]["max"] == 31
    assert report.measures["response_time"]["meets"] is False
    assert report.failed_ids() == ["EV-931"]
    summary = (report.folder / "resumen.md").read_text(encoding="utf-8")
    assert "EV-931: superó los 30 segundos" in summary


def test_malformed_and_unapproved_cases_are_in_the_results_file(
    read_user, two_regimes, scripted, tmp_path
):
    """REQ-008, REQ-020: `resultados.jsonl` trae un renglón por cada archivo de caso,
    también los mal formados y los que no tienen visto bueno, con su motivo."""
    scripted.marks[Q1] = {NEW_OBJECT: 0.9}

    report = run(read_user, "t039-filtro", tmp_path)

    rows = [json.loads(line) for line in
            (report.folder / "resultados.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(r["id"], r["ran"], r.get("skipped")) for r in rows] == [
        ("EV-961", False, evaluation.MALFORMED),
        ("EV-962", False, evaluation.NOT_APPROVED),
        ("EV-963", False, evaluation.MALFORMED),
        ("EV-964", True, None),
        ("EV-965", False, evaluation.MALFORMED),
    ]
    assert all(r["reason"] for r in rows if not r["ran"])


def test_prompt_version_comes_from_the_queries_of_the_run(
    read_user, two_regimes, scripted, tmp_path
):
    """REQ-008 (P6): `parametros.json` lleva la versión de las instrucciones que usaron
    las consultas de la corrida, tal como quedó registrada en cada consulta, sea cual
    sea la versión vigente (aviso de T-039: el test no depende de la constante)."""
    scripted.marks[Q1] = {NEW_OBJECT: 0.9}

    report = run(read_user, "t039-aviso", tmp_path)

    registered = Query.objects.get().prompt_version
    assert registered
    parameters = json.loads((report.folder / "parametros.json").read_text(encoding="utf-8"))
    assert parameters["prompt_version"] == registered
    assert by_id(report)["EV-951"]["prompt_version"] == registered


def test_prompt_versions_are_all_listed_when_they_differ():
    """REQ-008 (P6): si las consultas usaron versiones distintas, se listan todas; las
    que no llamaron al modelo no aportan versión."""
    lines = [{"prompt_version": "consulta-v1"}, {"prompt_version": ""},
             {"prompt_version": "consulta-v2"}, {"prompt_version": "consulta-v1"}]

    assert evaluation.prompt_versions(lines) == ["consulta-v1", "consulta-v2"]
    assert evaluation.prompt_versions(lines[:2]) == "consulta-v1"
    assert evaluation.prompt_versions([{"prompt_version": ""}]) is None
