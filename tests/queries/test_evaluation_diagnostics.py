"""Medidas de diagnóstico, comparación de corridas y comparación quitando piezas (T-042;
plan 001, "Evals"; ADR-0003, "Cómo se mide").

`evaluation.run` suma a lo de T-039: medidas de recuperación por caso y de la corrida,
salidas con falla de formato o de cita, los casos de REQ-018 y REQ-019 aparte, respuesta
correcta y abstención por régimen, la comparación con la corrida anterior (con la
igualdad al repetir) y, a pedido, la comparación quitando piezas.

Los casos son sintéticos (P4), en `tests/fixtures/evals/t042-diagnostico` y
`t039-medidas`, y se responden con los dos regímenes de `two_regimes` (T-009) y los
dobles de los clientes de IA. Las corridas se guardan en una carpeta temporal.
"""

import itertools
import json
import re
import shutil
from pathlib import Path

import pytest
from django.conf import settings

from evaluon.ai import ServiceUnavailableError
from evaluon.ai import generation as generation_client
from evaluon.ai import reranker as reranker_client
from evaluon.audit.models import Channel
from evaluon.queries import evaluation, retrieval, services
from evaluon.queries.models import Query

from tests.queries.test_evaluation import FIXTURES, key_data_ok

pytestmark = pytest.mark.django_db

N247 = "Disposición AFIP 247/2022"
N297 = "Disposición AFIP 297/03"

# Preguntas de los casos sintéticos de `t042-diagnostico`.
Q_OLD = "¿Cuál es el objeto del régimen sintético anterior?"
Q_NEW = "¿Cuál es el objeto del régimen sintético?"
Q_NONE_NEW = "¿Cuántos días de licencia sintética corresponden?"
Q_NONE_OLD = "¿Cuántos días de licencia sintética había?"
Q_GUARANTEE = "¿Qué garantías sintéticas se piden?"

# Preguntas de `t039-medidas`.
Q1 = "¿Cuál es el objeto del régimen sintético?"
Q2 = "¿Qué garantías sintéticas se piden?"
Q4 = "¿Cuál es la alícuota sintética del impuesto?"

# Marcas del texto de las unidades de `two_regimes`, para el reranker.
OLD_OBJECT = "Objeto del régimen sintético anterior"
NEW_OBJECT = "OBJETO. Régimen sintético vigente"
GUARANTEES = "Garantías sintéticas"


@pytest.fixture
def scripted(monkeypatch, fake_ai):
    """Dobles ajustados por pregunta.

    - `marks[pregunta]`: puntaje del reranker para cada marca de texto; lo que no tiene
      marca puntúa 0.
    - `failing`: preguntas para las que la generación falla con el servicio caído.
    - `outputs[pregunta]`: salida sin tocar que devuelve la generación para esa
      pregunta (por ejemplo, una cortada o una que cita un alias que no se mostró).
    Lo demás lo responde el doble de `tests/conftest.py`, que cita el primer alias.
    """
    marks = {}
    failing = set()
    outputs = {}

    def rerank(query, documents):
        scores = marks.get(query, {})
        return [max([s for mark, s in scores.items() if mark in document], default=0.0)
                for document in documents]

    double = fake_ai.generation

    def generate(messages, schema):
        content = "\n".join(str(m.get("content", "")) for m in messages)
        if any(question in content for question in failing):
            raise ServiceUnavailableError("generation: falla simulada", service="generation")
        for question, output in outputs.items():
            if question in content:
                double.respond(output)
                try:
                    return double.generate(messages, schema)
                finally:
                    double._mode = ("default", None)
        return double.generate(messages, schema)

    monkeypatch.setattr(reranker_client, "rerank", rerank)
    monkeypatch.setattr(generation_client, "generate", generate)
    return type("Scripted", (), {"marks": marks, "failing": failing, "outputs": outputs})


def diagnostic_marks(scripted):
    """Puntajes del conjunto `t042-diagnostico`: dos aciertos (0,9 y 0,8), una pregunta
    con respuesta que queda bajo el umbral (0,3) y dos sin respuesta (0,2 y 0)."""
    scripted.marks[Q_OLD] = {OLD_OBJECT: 0.9}
    scripted.marks[Q_NEW] = {NEW_OBJECT: 0.8}
    scripted.marks[Q_GUARANTEE] = {GUARANTEES: 0.3}
    scripted.marks[Q_NONE_NEW] = {NEW_OBJECT: 0.2}


def run(user, folder, runs_dir, **kwargs):
    kwargs.setdefault("commit", "abc1234")
    return evaluation.run(user, FIXTURES / folder, runs_dir, **kwargs)


def by_id(report):
    return {line["id"]: line for line in report.results}


def summary_of(report):
    return (report.folder / "resumen.md").read_text(encoding="utf-8")


def section(summary, heading):
    """Texto de la sección `## heading` de `resumen.md`, hasta la siguiente."""
    rest = summary.split(f"## {heading}\n", 1)[1]
    return rest.split("\n## ", 1)[0]


# --- Avisos de T-039 sobre los datos clave ---------------------------------------------


@pytest.mark.parametrize("key, answer, ok", [
    ("no", "No obstante, el pliego puede agregar causales.", False),
    ("no", "No hace falta otra cosa.", False),
    ("sí", "Sin perjuicio de lo anterior, puede hacerlo.", False),
    ("sí", "Si el pliego lo prevé, puede hacerlo.", False),
    ("no", "No", True),
    ("no", "No, el pliego no puede.", True),
    ("no", "No: el pliego no puede.", True),
    ("sí", "Sí; el pliego puede.", True),
    ("sí", "—¡Sí! Puede hacerlo.", True),
    ("no", "«No», según el artículo.", True),
])
def test_yes_or_no_needs_punctuation_or_the_end_after_the_word(key, answer, ok):
    """REQ-008 (aviso de T-039): un dato clave "sí" o "no" se cumple solo si la primera
    afirmación empieza con esa palabra seguida de un signo de puntuación o del final:
    "No obstante, …" no cuenta como "no"."""
    assert key_data_ok(key, answer) is ok


@pytest.mark.parametrize("key, answer, ok", [
    ("1 %", "La multa es del uno por ciento del monto.", True),
    ("20 %", "Hasta el veinte por ciento del contrato.", True),
    ("5 %", "El cinco por ciento del monto ofertado.", True),
    ("10 %", "El 10 por ciento del monto.", True),
    ("1 %", "La multa es del 0,1 por ciento por día.", False),
    ("20 %", "Hasta el veinte del mes.", False),
])
def test_percent_in_words_without_the_figure_is_recognized(key, answer, ok):
    """REQ-008 (aviso de T-039): "uno por ciento" o "veinte por ciento", sin la cifra
    entre paréntesis, valen como "1 %" y "20 %"."""
    assert key_data_ok(key, answer) is ok


# --- Medidas de recuperación ------------------------------------------------------------


def test_each_case_carries_its_retrieval_diagnostics(read_user, two_regimes, scripted,
                                                      tmp_path, settings):
    """REQ-008, REQ-009 (ADR-0003): cada caso trae si la unidad correcta estuvo entre los
    candidatos (por camino y en la unión) y entre las seleccionadas, su posición, el
    puntaje más alto, si el umbral lo frenó y el tiempo de la recuperación."""
    settings.RERANK_THRESHOLD = 0.368  # el umbral que supone el test, no el calibrado
    diagnostic_marks(scripted)

    report = run(read_user, "t042-diagnostico", tmp_path)

    lines = by_id(report)
    hit = lines["EV-801"]["diagnostics"]
    assert hit["found"]["union"] is True
    assert hit["found"]["semantic"] is True
    assert hit["found"]["reference"] is False  # la pregunta no nombra un artículo
    assert set(hit["found"]) == {"semantic", "words", "reference", "union"}
    assert hit["selected"] is True
    assert hit["position"] == 1
    assert hit["max_score"] == pytest.approx(0.9)
    assert hit["stopped_by_threshold"] is False
    assert isinstance(hit["retrieval_seconds"], float)

    stopped = lines["EV-805"]["diagnostics"]
    assert lines["EV-805"]["status"] == "undetermined"
    assert stopped["found"]["union"] is True
    assert stopped["selected"] is False
    assert stopped["position"] == 1
    assert stopped["stopped_by_threshold"] is True
    assert stopped["max_score"] == pytest.approx(0.3)

    unanswerable = lines["EV-803"]["diagnostics"]
    assert unanswerable["found"] is None
    assert unanswerable["stopped_by_threshold"] is True


def test_run_retrieval_measures_are_aggregated(read_user, two_regimes, scripted, tmp_path,
                                               settings):
    """REQ-008, REQ-009 (ADR-0003): la corrida informa la unidad correcta entre los
    candidatos por camino y en la unión, entre las seleccionadas, su posición, las
    preguntas con respuesta y sin respuesta frenadas por el umbral y el tiempo de la
    recuperación."""
    settings.RERANK_THRESHOLD = 0.368  # el umbral que supone el test, no el calibrado
    diagnostic_marks(scripted)

    report = run(read_user, "t042-diagnostico", tmp_path)

    measures = report.retrieval
    assert (measures["found"]["union"]["ok"], measures["found"]["union"]["total"]) == (3, 3)
    assert measures["found"]["reference"]["ok"] == 0
    assert (measures["selected"]["ok"], measures["selected"]["total"]) == (2, 3)
    assert measures["position"]["max"] == 1
    assert (measures["answered_stopped"]["ok"], measures["answered_stopped"]["total"]) == (1, 3)
    assert (measures["unanswered_stopped"]["ok"],
            measures["unanswered_stopped"]["total"]) == (2, 2)
    assert measures["retrieval_time"]["max"] is not None

    text = section(summary_of(report), "Recuperación (diagnóstico)")
    assert "en la unión" in text
    assert "por referencia exacta" in text
    assert "frenadas por el umbral" in text
    assert "EV-805" in text


def test_measures_are_separated_by_regime(read_user, two_regimes, scripted, tmp_path):
    """REQ-020, REQ-009: respuesta correcta y abstención se informan separadas por el
    régimen del caso (`regimen`), como diagnóstico."""
    diagnostic_marks(scripted)

    report = run(read_user, "t042-diagnostico", tmp_path)

    old = report.by_regime[N297]
    new = report.by_regime[N247]
    assert (old["correct_answer"]["ok"], old["correct_answer"]["total"]) == (1, 1)
    assert (old["abstention"]["ok"], old["abstention"]["total"]) == (1, 1)
    assert (new["correct_answer"]["ok"], new["correct_answer"]["total"]) == (1, 2)
    assert (new["abstention"]["ok"], new["abstention"]["total"]) == (1, 1)

    text = section(summary_of(report), "Medidas por régimen (diagnóstico)")
    assert N297 in text and N247 in text
    assert "1 de 2" in text


def test_summary_has_every_section(read_user, two_regimes, scripted, tmp_path):
    """REQ-008, REQ-009, REQ-020, REQ-021: `resumen.md` trae las medidas exigidas, la
    tabla del lote de ajuste (T-060), las medidas por régimen, la recuperación, las
    fallas de formato o de cita, los casos de REQ-018 y REQ-019, los pares de REQ-020 y
    el aviso de REQ-021 en su propio apartado, la calibración, la comparación quitando
    piezas, la comparación con la corrida anterior, los casos fallados del lote de ajuste
    y, aparte, los del lote de aceptación, y los no corridos."""
    diagnostic_marks(scripted)

    summary = summary_of(run(read_user, "t042-diagnostico", tmp_path))

    headings = [line[3:] for line in summary.splitlines() if line.startswith("## ")]
    assert headings == [
        "Medidas exigidas",
        "Lote de ajuste (diagnóstico)",
        "Medidas por régimen (diagnóstico)",
        "Pares de REQ-020",
        "Aviso de REQ-021",
        "Recuperación (diagnóstico)",
        "Salidas con falla de formato o de cita",
        "Casos de REQ-018 y REQ-019",
        "Calibración del umbral (provisoria)",
        "Comparación quitando piezas",
        "Comparación con la corrida anterior",
        "Casos fallados",
        "Casos fallados del lote de aceptación",
        "Casos no corridos",
    ]


def test_req_018_and_req_019_cases_are_reported_apart(read_user, two_regimes, scripted,
                                                      tmp_path):
    """REQ-008 (REQ-018, REQ-019): los casos con la etiqueta "dos categorías" y los que
    tienen `difieren` se informan aparte, con si pasan."""
    diagnostic_marks(scripted)

    report = run(read_user, "t042-diagnostico", tmp_path)

    assert report.special == {
        "REQ-018": [{"id": "EV-802", "passed": True}],
        "REQ-019": [{"id": "EV-805", "passed": False}],
    }
    text = section(summary_of(report), "Casos de REQ-018 y REQ-019")
    assert "EV-802" in text and "EV-805" in text


def test_format_and_citation_failures_are_counted_by_type(read_user, two_regimes,
                                                          scripted, tmp_path):
    """REQ-008 (ADR-0002, aviso de T-019): se cuentan las salidas con falla de formato
    (`invalid_output`) y de cita (`invalid_citation`) filtrando las anomalías por tipo;
    una falla de servicio (`service_error`) no cuenta."""
    scripted.marks[Q1] = {NEW_OBJECT: 0.9}
    scripted.marks[Q2] = {NEW_OBJECT: 0.9}
    scripted.marks[Q4] = {NEW_OBJECT: 0.9}
    scripted.outputs[Q1] = '{"status": "grounded", "statements": [{"text": "La'
    scripted.outputs[Q2] = json.dumps({"status": "grounded", "statements": [
        {"text": "Afirmación sintética.", "citations": ["U9"], "regimes_differ": False}]})
    scripted.failing.add(Q4)

    report = run(read_user, "t039-medidas", tmp_path)

    lines = by_id(report)
    assert lines["EV-901"]["reason"] == "invalid_output"
    assert lines["EV-902"]["reason"] == "invalid_citation"
    assert lines["EV-904"]["reason"] == "service_unavailable"
    assert report.output_failures == {"format": ["EV-901"], "citation": ["EV-902"]}
    text = section(summary_of(report), "Salidas con falla de formato o de cita")
    assert "EV-901" in text and "EV-902" in text and "EV-904" not in text


# --- Comparación con la corrida anterior -------------------------------------------------


def all_marks(scripted):
    scripted.marks[Q1] = {NEW_OBJECT: 0.9}
    scripted.marks[Q2] = {NEW_OBJECT: 0.9}
    scripted.marks[Q4] = {NEW_OBJECT: 0.9}


def earlier(report, name="2000-01-01T000000_prev_modelo"):
    """Deja la corrida como si fuera anterior, con un nombre de fecha más vieja."""
    target = report.folder.with_name(name)
    report.folder.rename(target)
    return target


def test_first_run_says_there_is_no_previous_run(read_user, two_regimes, scripted,
                                                 tmp_path):
    """REQ-008: sin una corrida anterior en la carpeta, el resumen lo dice."""
    all_marks(scripted)

    report = run(read_user, "t039-medidas", tmp_path)

    assert report.comparison is None
    text = section(summary_of(report), "Comparación con la corrida anterior")
    assert "No hay una corrida anterior" in text


def test_summary_compares_with_the_previous_run_and_lists_differences(
    read_user, two_regimes, scripted, tmp_path
):
    """REQ-008, REQ-009 (P7): el resumen compara las medidas con la corrida anterior de
    la carpeta y lista los casos que pasaban y ahora fallan, los que fallaban y ahora
    pasan, y los que cambiaron de resultado."""
    all_marks(scripted)
    previous = earlier(run(read_user, "t039-medidas", tmp_path))
    del scripted.marks[Q1]  # EV-901 deja de pasar: queda bajo el umbral
    scripted.marks[Q2] = {GUARANTEES: 0.9}  # EV-902 pasa a citar el artículo 2

    report = run(read_user, "t039-medidas", tmp_path)

    comparison = report.comparison
    assert comparison["previous"] == previous.name
    assert comparison["regressions"] == ["EV-901"]
    assert comparison["improvements"] == ["EV-902"]
    measures = {row["name"]: row for row in comparison["measures"]}
    assert measures["correct_answer"]["previous"] == 0.5
    assert measures["correct_answer"]["current"] == 0.5
    assert measures["abstention"]["previous"] == 0.5

    text = section(summary_of(report), "Comparación con la corrida anterior")
    assert previous.name in text
    assert "Pasaban y ahora fallan: EV-901" in text
    assert "Fallaban y ahora pasan: EV-902" in text


def test_repeating_the_run_reports_equality(read_user, two_regimes, scripted, tmp_path):
    """REQ-008 (ADR-0002, P6): al repetir la corrida en las mismas condiciones, el
    resumen informa cuántos casos dan el mismo resultado (estado, citas y texto)."""
    all_marks(scripted)
    earlier(run(read_user, "t039-medidas", tmp_path))

    report = run(read_user, "t039-medidas", tmp_path)

    equality = report.comparison["equality"]
    assert (equality["same"], equality["same_status_reason_and_citations"],
            equality["total"]) == (4, 4, 4)
    assert report.comparison["conditions_changed"] == []
    text = section(summary_of(report), "Comparación con la corrida anterior")
    assert "4 de 4" in text
    assert "mismas condiciones" in text


def test_unreadable_previous_run_does_not_lose_the_current_one(
    read_user, two_regimes, scripted, tmp_path
):
    """REQ-008 (P7): si la corrida anterior no se puede leer, la actual se guarda igual
    y el resumen dice que no se comparó."""
    all_marks(scripted)
    broken = tmp_path / "2000-01-01T000000_rota_modelo"
    broken.mkdir()
    (broken / "resultados.jsonl").write_text("{esto no es JSON\n", encoding="utf-8")

    report = run(read_user, "t039-medidas", tmp_path)

    assert report.comparison["previous"] == broken.name
    assert "no se pudo leer" in report.comparison["error"]
    text = section(summary_of(report), "Comparación con la corrida anterior")
    assert "No se comparó" in text


def test_changed_conditions_are_named(read_user, two_regimes, scripted, tmp_path):
    """REQ-008 (P7): si cambió el commit, el umbral, los modelos, las instrucciones o la
    normativa, la comparación lo dice: no es una repetición."""
    all_marks(scripted)
    earlier(run(read_user, "t039-medidas", tmp_path, commit="aaa1111"))

    report = run(read_user, "t039-medidas", tmp_path, commit="bbb2222")

    assert report.comparison["conditions_changed"] == ["commit"]


# --- Comparación quitando piezas --------------------------------------------------------


def test_ablation_produces_the_four_configurations(read_user, two_regimes, scripted,
                                                   tmp_path, monkeypatch, settings):
    """REQ-008, REQ-009 (ADR-0003): la comparación quitando piezas corre cada caso con
    las cuatro configuraciones (solo vectores, solo palabras, combinada sin reranker,
    completa) con los parámetros públicos de la recuperación, sin pasar por la función
    de consulta, y la informa en `resumen.md`."""
    settings.RERANK_THRESHOLD = 0.368  # el umbral que supone el test, no el calibrado
    diagnostic_marks(scripted)
    calls = []
    original = retrieval.retrieve

    def spy(question, reference_date, *, paths=retrieval.ALL_PATHS, rerank=True):
        calls.append((question, reference_date, tuple(paths), rerank))
        return original(question, reference_date, paths=paths, rerank=rerank)

    monkeypatch.setattr(retrieval, "retrieve", spy)

    report = run(read_user, "t042-diagnostico", tmp_path, ablation=True)

    # Una consulta por caso, como siempre; la comparación no crea consultas.
    assert Query.objects.count() == 5
    configurations = {(paths, rerank) for q, d, paths, rerank in calls
                      if q == Q_OLD and d == two_regimes.before_v}
    assert configurations == {
        (("semantic",), True),
        (("words",), True),
        (("semantic", "words", "reference"), False),
        (("semantic", "words", "reference"), True),
    }
    names = [config["name"] for config in report.ablation]
    assert names == ["solo vectores", "solo palabras", "combinada sin reranker",
                     "completa"]
    by_name = {config["name"]: config for config in report.ablation}
    combined = by_name["combinada sin reranker"]
    full = by_name["completa"]
    # Sin reranker no hay umbral: "entre las seleccionadas" es toda la unión y coincide
    # con "entre los candidatos" (aclaración de T-032).
    assert combined["answered_stopped"] is None
    assert combined["threshold"] is None
    assert (combined["found"]["union"]["ok"], combined["found"]["union"]["total"]) == (3, 3)
    assert (combined["selected"]["ok"], combined["selected"]["total"]) == (3, 3)
    # Con los dobles, sin reranker la unidad esperada queda en el puesto 4 o 5 del orden
    # de la unión, y el cupo de 3 unidades por categoría la deja afuera de lo que se
    # envía al modelo en los tres casos con respuesta.
    assert (combined["position"]["median"], combined["position"]["max"]) == (4, 5)
    assert (combined["delivered"]["ok"], combined["delivered"]["total"]) == (0, 3)
    # Con reranker, EV-805 queda bajo el umbral (0,3): ni seleccionada ni enviada.
    assert (full["selected"]["ok"], full["delivered"]["ok"]) == (2, 2)
    assert full["answered_stopped"]["ok"] == 1
    assert full["threshold"] == settings.RERANK_THRESHOLD
    assert set(by_name["solo vectores"]["found"]) == {"semantic", "union"}

    line = by_id(report)["EV-805"]
    assert [entry["name"] for entry in line["ablation"]] == names
    combined_805 = line["ablation"][2]
    assert (combined_805["selected"], combined_805["delivered"]) == (True, False)

    text = section(summary_of(report), "Comparación quitando piezas")
    for name in names:
        assert name in text
    assert "Entre las enviadas al modelo" in text
    assert "coincide con \"entre los candidatos\"" in text
    row = next(r for r in text.splitlines() if r.startswith("| combinada sin reranker"))
    assert "| sin umbral | 100,0 % (3 de 3) | 100,0 % (3 de 3) | 0,0 % (0 de 3) |" in row


def test_ablation_is_not_run_unless_asked(read_user, two_regimes, scripted, tmp_path):
    """REQ-008 (ADR-0003): la comparación quitando piezas se corre una vez, a pedido; sin
    pedirla, el resumen dice cómo correrla."""
    diagnostic_marks(scripted)

    report = run(read_user, "t042-diagnostico", tmp_path)

    assert report.ablation is None
    assert "--quitando-piezas" in section(summary_of(report), "Comparación quitando piezas")


def test_command_runs_the_ablation_on_request(read_user, two_regimes, scripted, tmp_path,
                                             monkeypatch):
    """REQ-008: `correr_evals --quitando-piezas` corre la comparación y el comando muestra
    el umbral propuesto y con qué corrida se comparó."""
    from tests.queries.test_evaluation import call

    diagnostic_marks(scripted)
    before = settings.RERANK_THRESHOLD

    output = call("--usuario", read_user.username,
                  "--casos", str(FIXTURES / "t042-diagnostico"),
                  "--corridas", str(tmp_path), "--commit", "abc1234",
                  "--quitando-piezas", monkeypatch=monkeypatch)

    [folder] = list(tmp_path.iterdir())
    summary = (folder / "resumen.md").read_text(encoding="utf-8")
    assert "combinada sin reranker" in section(summary, "Comparación quitando piezas")
    assert "Umbral propuesto (provisorio): 0,246" in output
    assert "Corrida anterior: ninguna" in output
    assert Query.objects.filter(event__channel=Channel.EVAL).count() == 5
    assert settings.RERANK_THRESHOLD == before


def test_ablation_skips_dates_without_regime(read_user, two_regimes, scripted, tmp_path,
                                             monkeypatch):
    """REQ-020: como la consulta, la comparación quitando piezas no busca para una fecha
    sin régimen cargado."""
    cases = tmp_path / "casos"
    cases.mkdir()
    text = (FIXTURES / "t042-diagnostico" / "EV-803.yaml").read_text(encoding="utf-8")
    (cases / "EV-803.yaml").write_text(
        text.replace("2024-05-20", "2001-01-10").replace(
            'regimen: "Disposición AFIP 247/2022"', 'regimen: ""'), encoding="utf-8")
    calls = []
    monkeypatch.setattr(retrieval, "retrieve", lambda *a, **k: calls.append(a))

    report = evaluation.run(read_user, cases, tmp_path / "corridas", commit="x",
                            ablation=True)

    assert calls == []
    assert [entry["skipped"] for entry in by_id(report)["EV-803"]["ablation"]] == [
        "no_regime_at_date"] * 4
    assert services.applicable_regimes(two_regimes.before_all) == []


# --- Ajustes de la verificación de T-042 --------------------------------------------------


def _without_code(text):
    """El texto del resumen sin lo que va entre comillas invertidas (nombres de carpeta,
    commit, modelo), que son identificadores y no números para leer."""
    return re.sub(r"`[^`]*`", "", text)


def test_summary_uses_decimal_commas_and_plain_times(read_user, two_regimes, scripted,
                                                      tmp_path):
    """REQ-008, REQ-009 (B2): en todo `resumen.md` los números llevan coma decimal (el
    umbral del encabezado, los de cada configuración, las medianas) y las horas van como
    "03/10/2026 08:21": ningún número con punto decimal ni fecha u hora en formato ISO."""
    diagnostic_marks(scripted)
    earlier(run(read_user, "t042-diagnostico", tmp_path))

    summary = summary_of(run(read_user, "t042-diagnostico", tmp_path, ablation=True))

    plain = _without_code(summary)
    assert re.findall(r"\d\.\d", plain) == []
    assert re.findall(r"\d{4}-\d{2}-\d{2}", plain) == []
    assert re.findall(r"\d{2}:\d{2}:\d{2}", plain) == []
    assert re.search(r"^# Corrida del \d{2}/\d{2}/\d{4} \d{2}:\d{2}$", summary, re.M)
    assert re.search(r"Comienzo: \d{2}/\d{2}/\d{4} \d{2}:\d{2} · fin: "
                     r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", summary)
    threshold = f"{settings.RERANK_THRESHOLD:.3f}".replace(".", ",")
    assert (f"Umbral del modelo que reordena los resultados (reranker): {threshold}"
            in summary)
    assert "la del 01/01/2000 00:00" in summary
    assert f"| completa | {threshold} |" in summary


def test_a_median_position_between_two_is_written_with_a_comma():
    """REQ-008 (B2): una mediana de posición que no es entera se escribe con coma."""
    found = {"semantic": True, "words": True, "reference": False, "union": True}

    def diagnostics(position):
        return {"found": found, "selected": True, "position": position,
                "stopped_by_threshold": False, "retrieval_seconds": 0.1}

    measures = evaluation.retrieval_measures([("EV-1", True, diagnostics(1)),
                                              ("EV-2", True, diagnostics(2))])
    [row] = [r for r in evaluation._retrieval_section(measures) if "Posición" in r]

    assert "mediana 1,5 · peor 2" in row


def test_previous_run_is_the_latest_one_before_the_current(read_user, two_regimes,
                                                           scripted, tmp_path):
    """REQ-008 (P7, B3): con varias corridas en la carpeta, la anterior es la más
    reciente de las que tienen nombre anterior al de la actual y tienen resultados: no
    la más vieja, no una de nombre posterior y no una carpeta sin resultados."""
    all_marks(scripted)
    first = run(read_user, "t039-medidas", tmp_path)
    for name in ("2000-01-01T000000_vieja_modelo", "2001-01-01T000000_media_modelo",
                 "2999-01-01T000000_futura_modelo"):
        shutil.copytree(first.folder, tmp_path / name)
    (tmp_path / "2002-01-01T000000_vacia_modelo").mkdir()
    shutil.rmtree(first.folder)

    report = run(read_user, "t039-medidas", tmp_path)

    assert report.comparison["previous"] == "2001-01-01T000000_media_modelo"
    text = section(summary_of(report), "Comparación con la corrida anterior")
    assert "la del 01/01/2001 00:00" in text


def synthetic_line(case_id, *, status="grounded", reason=None, keys=("anexo/art-1",),
                   text="Afirmación sintética.", passed=True):
    cited = [{"unit": index, "norm": N247, "key": key}
             for index, key in enumerate(keys, start=1)]
    return {
        "id": case_id, "ran": True, "has_answer": True, "passed": passed,
        "status": status, "reason": reason, "cited_units": cited,
        "statements": [{"text": text, "regimes_differ": False,
                        "citations": [u["unit"] for u in cited]}],
        "measures": {"literal_citations": len(cited), "citations": len(cited),
                     "correct": passed, "abstained": None},
        "time_seconds": 1.0,
    }


def previous_run(lines, commit="x"):
    return {"folder": Path("2000-01-01T000000_x_modelo"), "parameters": {"commit": commit},
            "lines": lines}


def test_equality_tells_text_status_reason_and_citations_apart():
    """REQ-008 (ADR-0002, B4): al repetir, un caso que cambia solo el texto no cuenta
    como mismo resultado pero sí como mismo estado, motivo y citas; uno que cambia solo
    el estado, solo el motivo o solo las citas no cuenta en ninguna de las dos."""
    ids = ["EV-TEXTO", "EV-ESTADO", "EV-MOTIVO", "EV-CITAS", "EV-IGUAL"]
    old = [synthetic_line(case_id) for case_id in ids]
    new = [
        synthetic_line("EV-TEXTO", text="Otra redacción de la afirmación."),
        synthetic_line("EV-ESTADO", status="undetermined"),
        synthetic_line("EV-MOTIVO", reason="model_abstained"),
        synthetic_line("EV-CITAS", keys=("anexo/art-2",)),
        synthetic_line("EV-IGUAL"),
    ]

    comparison = evaluation.compare_runs(previous_run(old), new, {"commit": "x"})

    assert comparison["equality"] == {"same": 1, "same_status_reason_and_citations": 2,
                                      "total": 5}
    assert comparison["changed"] == ["EV-ESTADO", "EV-MOTIVO", "EV-CITAS"]
    text = "\n".join(evaluation._comparison_section(comparison))
    assert "1 de 5 casos corridos" in text
    assert "2 de 5 con el mismo estado, el mismo motivo y las mismas citas" in text


def test_each_drop_is_marked_and_asks_for_approval():
    """REQ-008, REQ-009 (P7): en la comparación con la corrida anterior, cada medida que
    baja se marca como "baja" y el resumen recuerda que requiere aprobación."""
    old = [synthetic_line("EV-001"), synthetic_line("EV-002")]
    new = [synthetic_line("EV-001", passed=False), synthetic_line("EV-002")]

    comparison = evaluation.compare_runs(previous_run(old), new, {"commit": "x"})

    assert comparison["drops"] == [{"name": "correct_answer", "lot": "ajuste"}]
    text = "\n".join(evaluation._comparison_section(comparison))
    assert ("| Respuesta correcta que cita la unidad correcta | 100,0 % | 50,0 % | baja |"
            in text)
    assert "| Cita literal | 100,0 % | 100,0 % | igual |" in text
    assert "| Tiempo de respuesta (mediana) | 1,00 s | 1,00 s | igual |" in text
    assert "requiere la aprobación explícita del responsable" in text


def timed_lines(*seconds):
    lines = [synthetic_line(f"EV-{i:03d}") for i in range(1, len(seconds) + 1)]
    for line, value in zip(lines, seconds):
        line["time_seconds"] = value
    return lines


def time_comparison(old_seconds, new_seconds):
    comparison = evaluation.compare_runs(previous_run(timed_lines(*old_seconds)),
                                         timed_lines(*new_seconds), {"commit": "x"})
    return comparison, "\n".join(evaluation._comparison_section(comparison))


def test_small_time_changes_are_shown_without_a_drop():
    """REQ-008 (P7, decisión del Coordinador): si el máximo no supera 30 s y la mediana no
    sube más de un 25 %, el cambio de tiempo se muestra sin marcarlo como baja; una suba
    de exactamente el 25 % tampoco es baja."""
    comparison, text = time_comparison((10.0, 10.0), (11.0, 12.0))

    assert comparison["drops"] == []
    assert "| Tiempo de respuesta (mediana) | 10,00 s | 11,50 s | más lento |" in text
    assert "| Tiempo de respuesta (máximo) | 10,00 s | 12,00 s | más lento |" in text
    assert "Hay bajas" not in text
    assert time_comparison((8.0,), (10.0,))[0]["drops"] == []
    assert time_comparison((40.0,), (29.0,))[0]["drops"] == []


def test_time_over_the_limit_is_a_drop():
    """REQ-008 (P7): si el máximo de esta corrida supera los 30 s, el tiempo es baja,
    aunque la mediana no cambie."""
    comparison, text = time_comparison((10.0, 10.0, 10.0), (10.0, 10.0, 31.0))

    assert comparison["drops"] == [{"name": "response_time", "lot": None}]
    assert ("| Tiempo de respuesta (máximo) | 10,00 s | 31,00 s | "
            "baja (supera el límite de 30 s) |") in text
    assert "| Tiempo de respuesta (mediana) | 10,00 s | 10,00 s | igual |" in text
    assert "requiere la aprobación explícita del responsable" in text


def test_a_median_rise_over_25_percent_is_a_drop():
    """REQ-008 (P7): si la mediana sube más de un 25 % respecto de la corrida anterior,
    el tiempo es baja, aunque el máximo siga debajo de 30 s."""
    comparison, text = time_comparison((8.0, 8.0), (11.0, 11.0))

    assert comparison["drops"] == [{"name": "response_time_median", "lot": None}]
    assert ("| Tiempo de respuesta (mediana) | 8,00 s | 11,00 s | "
            "baja (sube más del 25 %) |") in text
    assert "| Tiempo de respuesta (máximo) | 8,00 s | 11,00 s | más lento |" in text


def test_command_names_the_previous_run_by_date_and_warns_of_drops(
    read_user, two_regimes, scripted, tmp_path, monkeypatch
):
    """REQ-008 (P7): la salida de `correr_evals` nombra la corrida anterior por su fecha,
    no por la carpeta, y avisa en una línea si hay bajas que requieren aprobación."""
    from tests.queries.test_evaluation import call

    all_marks(scripted)
    steady_clock(monkeypatch)
    earlier(run(read_user, "t039-medidas", tmp_path))
    del scripted.marks[Q1]  # EV-901 deja de pasar: baja la respuesta correcta

    output = call("--usuario", read_user.username,
                  "--casos", str(FIXTURES / "t039-medidas"),
                  "--corridas", str(tmp_path), "--commit", "abc1234",
                  monkeypatch=monkeypatch)

    lines = output.splitlines()
    assert "Corrida anterior: la del 01/01/2000 00:00" in lines
    assert "2000-01-01T000000" not in output
    assert ("Hay bajas respecto de la corrida anterior que requieren la aprobación del "
            "responsable: respuesta correcta que cita la unidad correcta del lote de "
            "ajuste.") in lines


def test_command_says_when_there_are_no_drops(read_user, two_regimes, scripted, tmp_path,
                                             monkeypatch):
    """REQ-008 (P7): sin bajas, la salida del comando lo dice."""
    from tests.queries.test_evaluation import call

    all_marks(scripted)
    steady_clock(monkeypatch)
    earlier(run(read_user, "t039-medidas", tmp_path))

    output = call("--usuario", read_user.username,
                  "--casos", str(FIXTURES / "t039-medidas"),
                  "--corridas", str(tmp_path), "--commit", "abc1234",
                  monkeypatch=monkeypatch)

    assert "Sin bajas respecto de la corrida anterior." in output.splitlines()


def test_retrieval_row_says_sent_to_the_model():
    """REQ-008: en "Recuperación (diagnóstico)" el renglón de lo que llegó al modelo se
    llama "entre las enviadas al modelo", sin "seleccionadas", para no confundirlo con la
    medida de la comparación quitando piezas."""
    found = {"semantic": True, "words": True, "reference": False, "union": True}
    diagnostics = {"found": found, "selected": True, "position": 1,
                   "stopped_by_threshold": False, "retrieval_seconds": 0.1}

    rows = evaluation._retrieval_section(
        evaluation.retrieval_measures([("EV-1", True, diagnostics)]))

    assert any(r.startswith("| Unidad correcta entre las enviadas al modelo |")
               for r in rows)
    assert not any("seleccionadas" in r for r in rows)


def test_a_case_with_several_units_needs_all_of_them(two_regimes):
    """REQ-008 (A11): con varias unidades esperadas, la unidad correcta cuenta entre los
    candidatos, entre las seleccionadas y entre las enviadas solo si están todas, y la
    posición es la de la peor ubicada."""
    first = two_regimes.new_units["anexo/art-1"].pk
    second = two_regimes.new_units["anexo/art-2"].pk
    other = two_regimes.new_units["art-1"].pk
    expected = ((N247, "anexo/art-1"), (N247, "anexo/art-2"))

    only_one = evaluation.unit_hits(expected, [{"unit": first, "path": ["semantic"]}],
                                    [first], [first], retrieval.ALL_PATHS,
                                    delivered=[first])
    both = evaluation.unit_hits(
        expected,
        [{"unit": first, "path": ["semantic"]}, {"unit": second, "path": ["words"]},
         {"unit": other, "path": ["semantic", "words"]}],
        [first, second], [second, other, first], retrieval.ALL_PATHS,
        delivered=[second, first])

    assert only_one["found"]["union"] is False
    assert (only_one["selected"], only_one["delivered"], only_one["position"]) == (
        False, False, None)
    assert both["found"]["union"] is True
    assert both["found"]["semantic"] is False  # por significado entró solo una
    assert both["found"]["words"] is False
    assert (both["selected"], both["delivered"], both["position"]) == (True, True, 3)


def steady_clock(monkeypatch):
    """Que cada consulta de la corrida mida 1 s, también las que corre el comando: con el
    reloj real, tiempos de milisegundos podrían variar más de un 25 % entre corridas y
    marcar una baja de tiempo al azar."""
    original = evaluation.run

    def run_with_steady_clock(*args, **kwargs):
        ticks = itertools.count()
        kwargs.setdefault("clock", lambda: next(ticks))
        return original(*args, **kwargs)

    monkeypatch.setattr(evaluation, "run", run_with_steady_clock)
