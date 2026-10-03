"""Recalificar una corrida guardada (T-058; ADR-0011; plan 001, "Evals", "Recalificar una
corrida guardada").

`evaluation.rescore` vuelve a medir los renglones de `resultados.jsonl` de una corrida con
los casos vigentes y el corrector vigente, sin consultar ni llamar a ningún servicio de IA,
y guarda una carpeta nueva terminada en `_recalificada`. La corrida guardada y los casos
son sintéticos (P4) y están en `tests/fixtures/evals/t058/`; la corrida se copia a una
carpeta temporal para comprobar que no se modifica.
"""

import json
import shutil
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import CommandError, call_command

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, Channel, EventType
from evaluon.queries import evaluation
from evaluon.queries.models import Query

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "evals" / "t058"
CASES = FIXTURES / "casos-recalificar"
SOURCE_NAME = "2026-10-03T120000_abc1234_modelo-sintetico"
RUN_FILES = ("parametros.json", "resultados.jsonl", "resumen.md")

TEST_PASSWORD = "clave-sintetica-de-prueba"  # la de tests/conftest.py


@pytest.fixture
def saved_run(tmp_path):
    """Copia de la corrida sintética guardada, dentro de una carpeta de corridas."""
    runs = tmp_path / "corridas"
    shutil.copytree(FIXTURES / "corridas" / SOURCE_NAME, runs / SOURCE_NAME)
    return runs / SOURCE_NAME


def snapshot(folder):
    return {name: (folder / name).read_bytes() for name in RUN_FILES}


def rescore(user, source, **kwargs):
    kwargs.setdefault("commit", "def5678")
    return evaluation.rescore(user, source, CASES, source.parent, **kwargs)


def results_of(folder):
    return [json.loads(row) for row in
            (folder / "resultados.jsonl").read_text(encoding="utf-8").splitlines()]


def test_case_with_the_new_variant_goes_from_failed_to_correct(read_user, saved_run):
    """REQ-008 (plan, "Recalificar"): un caso cuyo dato clave pasó a tener la variante
    que dice la respuesta pasa de fallado a correcto, con las mismas respuestas."""
    report = rescore(read_user, saved_run)

    lines = {line["id"]: line for line in report.results}
    assert lines["EV-871"]["measures"]["correct"] is True
    assert lines["EV-871"]["passed"] is True
    assert lines["EV-871"]["statements"][0]["text"] == "Se prorroga por un período igual."
    assert lines["EV-873"]["measures"]["abstained"] is True
    assert "EV-871" in report.comparison["improvements"]
    assert report.comparison["previous"] == SOURCE_NAME


def test_case_with_another_question_or_date_is_not_rescorable(read_user, saved_run):
    """REQ-008 (plan, "Recalificar"): un caso cuya pregunta o fecha no coincide con el
    renglón guardado se informa como no recalificable y queda fuera de la medida."""
    report = rescore(read_user, saved_run)

    not_rescorable = {s.case_id: s for s in report.skipped
                      if s.kind == evaluation.NOT_RESCORABLE}
    assert set(not_rescorable) == {"EV-872", "EV-874"}
    assert "pregunta" in not_rescorable["EV-872"].reason
    assert "fecha" in not_rescorable["EV-874"].reason
    assert {line["id"] for line in report.results} == {"EV-871", "EV-873"}
    assert (report.adjustment_measures["correct_answer"]["ok"],
            report.adjustment_measures["correct_answer"]["total"]) == (1, 1)
    rows = {row["id"]: row for row in results_of(report.folder)}
    assert rows["EV-872"]["skipped"] == evaluation.NOT_RESCORABLE
    summary = (report.folder / "resumen.md").read_text(encoding="utf-8")
    assert "no recalificable" in summary


def test_case_whose_answer_presence_changed_is_not_rescorable(read_user, saved_run,
                                                               tmp_path):
    """REQ-008 (plan, "Recalificar"): si el caso pasó a ser sin respuesta (o al revés),
    no se recalifica."""
    cases = tmp_path / "casos"
    shutil.copytree(CASES, cases)
    text = (cases / "EV-871.yaml").read_text(encoding="utf-8")
    text = (text.replace('esperado: "Por igual término."', 'esperado: "no determinado"')
            .replace('regimen: "Disposición AFIP 247/2022"', 'regimen: ""')
            .replace("unidades: [{norma: \"Disposición AFIP 247/2022\", key: anexo/art-43}]",
                     "unidades: []")
            .replace('datos_clave: [["por igual término", "por un período igual"]]',
                     "datos_clave: []"))
    (cases / "EV-871.yaml").write_text(text, encoding="utf-8")

    report = evaluation.rescore(read_user, saved_run, cases, saved_run.parent, commit="x")

    [skip] = [s for s in report.skipped if s.case_id == "EV-871"]
    assert skip.kind == evaluation.NOT_RESCORABLE
    assert "respuesta" in skip.reason


def test_new_folder_has_the_three_files_and_the_source(read_user, saved_run):
    """REQ-008 (plan, "Recalificar"): la carpeta nueva termina en `_recalificada`, lleva
    el modelo de la corrida original y los tres archivos; `parametros.json` copia los de
    la original y suma el origen y el aviso de que no se hicieron consultas; `resumen.md`
    empieza diciendo que es una recalificación y se compara con la original."""
    report = rescore(read_user, saved_run)

    folder = report.folder
    assert folder.parent == saved_run.parent
    assert folder.name.endswith("_def5678_modelo-sintetico_recalificada")
    assert sorted(p.name for p in folder.iterdir()) == sorted(RUN_FILES)
    parameters = json.loads((folder / "parametros.json").read_text(encoding="utf-8"))
    original = json.loads((saved_run / "parametros.json").read_text(encoding="utf-8"))
    assert parameters["search"] == original["search"]
    assert parameters["corpus_version"] == original["corpus_version"]
    assert parameters["rescore"]["source"] == SOURCE_NAME
    assert parameters["rescore"]["commit"] == "def5678"
    assert "no se hicieron consultas" in parameters["rescore"]["note"]
    summary = (folder / "resumen.md").read_text(encoding="utf-8")
    head = summary.split("## ", 1)[0]
    assert "Recalificación" in head
    assert SOURCE_NAME in head
    comparison = summary.split("## Comparación con la corrida anterior")[1]
    assert SOURCE_NAME in comparison
    assert "recalificación" in comparison


def test_original_folder_is_not_modified(read_user, saved_run):
    """REQ-008 (plan, "Recalificar"): la carpeta original no se modifica."""
    before = snapshot(saved_run)
    names_before = sorted(p.name for p in saved_run.iterdir())

    rescore(read_user, saved_run)

    assert snapshot(saved_run) == before
    assert sorted(p.name for p in saved_run.iterdir()) == names_before


def test_rescore_makes_no_query_and_no_audit_event(read_user, saved_run, monkeypatch):
    """REQ-008 (plan, "Recalificar"; P6): recalificar no consulta, no llama a los
    servicios de IA y no crea consultas ni hechos del registro de auditoría."""
    from evaluon.queries import services

    def forbidden(*args, **kwargs):
        raise AssertionError("la recalificación no consulta")

    monkeypatch.setattr(services, "ask", forbidden)
    events = AuditEvent.objects.count()

    rescore(read_user, saved_run)

    assert Query.objects.count() == 0
    assert AuditEvent.objects.count() == events


def test_user_without_role_is_rejected(read_user, saved_run):
    """REQ-008 (REQ-016): un usuario sin rol de lectura es rechazado antes de leer nada;
    queda el hecho `rejected` con el canal `eval` y no se crea ninguna carpeta."""
    read_user.is_active = False
    read_user.save()

    with pytest.raises(RoleRejected):
        rescore(read_user, saved_run)

    [event] = AuditEvent.objects.filter(event_type=EventType.REJECTED)
    assert event.channel == Channel.EVAL
    assert event.detail["operation"] == "evaluon.queries.evaluation.rescore"
    assert [p.name for p in saved_run.parent.iterdir()] == [SOURCE_NAME]


def test_folder_without_results_is_an_error(read_user, tmp_path):
    """REQ-008: una carpeta sin `resultados.jsonl` no es una corrida guardada."""
    with pytest.raises(FileNotFoundError, match="resultados.jsonl"):
        evaluation.rescore(read_user, tmp_path, CASES, tmp_path, commit="x")


# --- Comando ---------------------------------------------------------------------------


def call(*args, monkeypatch):
    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    out = StringIO()
    call_command("correr_evals", *args, stdout=out, stderr=StringIO())
    return out.getvalue()


def test_command_rescores_a_saved_run(read_user, saved_run, monkeypatch):
    """REQ-008: `correr_evals --recalificar <carpeta>` recalifica con los casos de
    `--casos`, guarda la carpeta nueva en `--corridas` y lo dice."""
    output = call("--usuario", read_user.username, "--recalificar", str(saved_run),
                  "--casos", str(CASES), "--corridas", str(saved_run.parent),
                  "--commit", "def5678", monkeypatch=monkeypatch)

    [folder] = [p for p in saved_run.parent.iterdir() if p.name != SOURCE_NAME]
    assert folder.name.endswith("_recalificada")
    assert "Recalificación" in output
    assert str(folder) in output
    assert "no recalificable" in output
    assert Query.objects.count() == 0


def test_command_does_not_mix_rescore_and_ablation(read_user, saved_run, monkeypatch):
    """REQ-008: recalificar no recupera: `--recalificar` con `--quitando-piezas` se
    rechaza sin guardar nada."""
    with pytest.raises(CommandError, match="quitando-piezas"):
        call("--usuario", read_user.username, "--recalificar", str(saved_run),
             "--casos", str(CASES), "--corridas", str(saved_run.parent),
             "--quitando-piezas", monkeypatch=monkeypatch)

    assert [p.name for p in saved_run.parent.iterdir()] == [SOURCE_NAME]


def test_command_with_a_missing_folder_says_so(read_user, tmp_path, monkeypatch):
    """REQ-008: si la carpeta a recalificar no es una corrida guardada, el comando lo
    dice y no guarda nada."""
    with pytest.raises(CommandError, match="resultados.jsonl"):
        call("--usuario", read_user.username, "--recalificar", str(tmp_path / "no-existe"),
             "--casos", str(CASES), "--corridas", str(tmp_path), monkeypatch=monkeypatch)

    assert list(tmp_path.iterdir()) == []
