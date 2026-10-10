"""Los cinco momentos del caso chico en las cinco secciones (T-217; REQ-075, REQ-097, REQ-098).

Servicios reales con el modelo simulado (sin GPU). La tabla esperada está en
`data/momentos-esperados.yaml`, escrita desde la spec y no desde el código. Todo el material es
inventado (P4)."""

import re
from pathlib import Path

import pytest
import yaml
from django.urls import reverse
from django.utils import timezone

from evaluon.assessment import models as am
from evaluon.journey import sections
from evaluon.tenders.models import Job, JobKind, JobStatus
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.moments import MOMENTS, Case
from tests.journey.temas.test_s5_normas import complete_and_load, evaluator  # noqa: F401

pytestmark = pytest.mark.django_db

STATIC = Path(__file__).resolve().parents[2] / "evaluon" / "static" / "journey"
TABLE = yaml.safe_load(
    (Path(__file__).parent / "data" / "momentos-esperados.yaml").read_text(encoding="utf-8"))
KEYS = ("procedimiento", "pliego", "ofertas", "evaluacion", "normativas")


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


@pytest.fixture
def case(operator_user, evaluator_user, expected, fake_ai):
    return Case(operator_user, evaluator_user, expected)


def test_the_table_has_25_cells():
    """REQ-075: cinco momentos por cinco secciones, todas escritas en la tabla."""
    assert list(TABLE["momentos"]) == list(MOMENTS)
    assert all(list(row) == list(KEYS) for row in TABLE["momentos"].values())


def test_the_25_cells_have_the_state_the_counts_and_the_access(client, case, operator_user):
    """REQ-075, REQ-097, REQ-098: en cada momento, cada sección dice su estado, sus dos
    cuentas, qué falta y de dónde vino lo que hay, y tiene «Subir archivo» a la vista; la barra
    y la pantalla coinciden con el cálculo. Se recorren las 25 celdas y se informan todas las
    diferencias juntas."""
    log_in(client, operator_user)
    wrong, checked = [], 0
    for moment in MOMENTS:
        case.go_to(moment)
        procedure = case.procedure
        overview = sections.sections_for(operator_user, procedure)
        bar = client.get(reverse("expedientes:barra", args=[procedure.pk])).content.decode()
        for key in KEYS:
            want = TABLE["momentos"][moment][key]
            got = overview.get(key)
            page = client.get(reverse(f"expedientes:{key}", args=[procedure.pk])).content.decode()
            checked += 1
            faltas = " | ".join(x.text for x in got.missing) + " | " + " | ".join(
                x.text for x in got.tema_missing)
            origen = " | ".join(got.sources)
            problems = []
            if got.state != want["estado"]:
                problems.append(f"estado {got.state} != {want['estado']}")
            if got.pending != want["pendientes"]:
                problems.append(f"pendientes {got.pending} != {want['pendientes']}")
            if got.suggestions != want["sugerencias"]:
                problems.append(f"sugerencias {got.suggestions} != {want['sugerencias']}")
            problems += [f"no dice que falta «{t}»" for t in want["falta"] if t not in faltas]
            problems += [f"no dice el origen «{t}»" for t in want["origen"] if t not in origen]
            if not want["falta"] and got.missing:
                problems.append("dice que falta algo y la tabla no espera nada")
            tab = re.search(rf'data-seccion="{key}" data-state="(\w+)".*?<b>(\d+)</b> pend\. · '
                            rf'<b>(\d+)</b> sug\.', bar, re.S)
            if not tab or (tab[1], int(tab[2]), int(tab[3])) != (
                    want["estado"], want["pendientes"], want["sugerencias"]):
                problems.append(f"la barra dice {tab.groups() if tab else None}")
            if "Subir archivo" not in page:
                problems.append("falta «Subir archivo» en la pantalla")
            wrong += [f"{moment}/{key}: {p}" for p in problems]
    assert checked == 25
    assert not wrong, "\n".join(wrong)


def test_the_total_of_each_moment_is_the_sum_of_the_sections(client, case, operator_user):
    """REQ-098: la cuenta de la portada es la suma de las cinco secciones, en dos bloques
    separados y visibles en todos los momentos."""
    log_in(client, operator_user)
    for moment in MOMENTS:
        case.go_to(moment)
        overview = sections.sections_for(operator_user, case.procedure)
        want = TABLE["momentos"][moment]
        assert overview.pending == sum(c["pendientes"] for c in want.values()), moment
        assert overview.suggestions == sum(c["sugerencias"] for c in want.values()), moment
        html = client.get(reverse("expedientes:portada", args=[case.procedure.pk])
                          ).content.decode()
        assert html.index('id="pendientes"') < html.index('id="sugerencias"'), moment
        assert "Pendientes de decidir" in html and "Sugerencias del sistema" in html, moment


def test_any_section_opens_at_any_moment_without_passing_through_the_others(
        client, case, operator_user):
    """REQ-075: en cualquier momento se abre cualquier sección y las cinco pestañas se ven."""
    log_in(client, operator_user)
    for moment in MOMENTS:
        case.go_to(moment)
        for key in KEYS:
            response = client.get(reverse(f"expedientes:{key}", args=[case.procedure.pk]))
            assert response.status_code == 200, (moment, key)
            assert response.content.decode().count('data-seccion="') == 5, (moment, key)


def test_a_new_procedure_says_what_is_missing_with_a_direct_action_in_every_section(
        client, case, operator_user):
    """REQ-097: recién creado el procedimiento, cada sección dice qué falta y lleva a la
    acción directa (un enlace dentro de la misma aplicación)."""
    log_in(client, operator_user)
    case.antes_de_importar()
    overview = sections.sections_for(operator_user, case.procedure)
    for section in overview.sections:
        assert section.missing, section.key
        assert section.upload_url and section.upload_url.startswith(
            f"/expedientes/{case.procedure.pk}/"), section.key
        page = client.get(section.url).content.decode()
        assert re.search(r"Falta|Faltan|Todavía no hay", page), section.key
        assert section.upload_url.split("#")[0] in page, section.key


def test_a_section_without_stage_gets_its_state_from_its_own_pending(
        client, case, operator_user, evaluator):
    """REQ-097, REQ-098: Normativas no tiene etapa de la 013: una norma cargada que espera
    validación la deja «a decidir» con 1 pendiente, y las demás secciones no cambian."""
    case.go_to("antes_de_importar")
    before = sections.sections_for(operator_user, case.procedure)
    assert (before.get("normativas").state, before.get("normativas").pending) == (
        "pendiente", 0)
    complete_and_load(client, case.procedure, evaluator)
    after = sections.sections_for(operator_user, case.procedure)
    norms = after.get("normativas")
    assert (norms.state, norms.pending) == ("a_decidir", 1)
    assert after.pending == before.pending + 1
    assert [s.state for s in after.sections if s.key != "normativas"] == [
        s.state for s in before.sections if s.key != "normativas"]


# --- Avisos de la 013 (T-185) ---------------------------------------------------------------


def test_the_polling_pauses_when_the_tab_is_hidden_and_resumes_when_it_is_shown():
    """013, aviso 1: el sondeo no pide nada con la pestaña oculta y vuelve a pedir al mostrarse
    (REQ-075: la barra se sondea igual que el bloque de etapas)."""
    js = (STATIC / "recorrido.js").read_text(encoding="utf-8")
    assert re.search(r"if \(document\.hidden\) \{ return; \}", js)
    assert re.search(r'addEventListener\("visibilitychange",\s*function \(\) \{\s*'
                     r'if \(!document\.hidden\) \{ poll\(\); \}', js)


def test_suggestions_count_in_the_stages_and_reach_the_sections(case, operator_user):
    """013, aviso 2: `Stage.suggestions` llega a la sección; en el último momento las dos
    ofertas sin ficha dan 2 sugerencias, aparte de lo pendiente (REQ-098)."""
    case.go_to("evaluacion_terminada")
    overview = sections.sections_for(operator_user, case.procedure)
    assert sum(s.suggestions for s in overview.journey.stages) == overview.suggestions == 2
    assert overview.get("ofertas").suggestions == 2 and overview.get("ofertas").pending == 0


def test_a_failure_shows_its_reason_in_plain_words_and_never_the_raw_error(
        client, case, operator_user):
    """013, aviso 3: la sección 4 con la evaluación fallida muestra el motivo en lenguaje llano
    (`plain_reason`), con estado «con error», y no el texto técnico."""
    case.go_to("evaluacion_terminada")
    job = Job.objects.create(kind=JobKind.EVALUATE_OFFERS, procedure=case.procedure,
                             requested_by=operator_user)
    am.Request.objects.create(
        procedure=case.procedure, matrix_version=case.version,
        offers=[o.pk for o in case.offers], requirements=None, cause=am.Cause.MATRIZ,
        requested_by=operator_user, job=job)
    Job.objects.filter(pk=job.pk).update(
        status=JobStatus.FAILED, started_at=timezone.now(), finished_at=timezone.now(),
        error="ConnectionError: http://generation_batch:8080 timeout")
    log_in(client, operator_user)
    overview = sections.sections_for(operator_user, case.procedure)
    assert overview.get("evaluacion").state == "con_error"
    page = client.get(reverse("expedientes:evaluacion", args=[case.procedure.pk])
                      ).content.decode()
    for technical in ("generation_batch", "8080", "ConnectionError", "Traceback"):
        assert technical not in page
    assert "el motor de IA no respondió a tiempo" in page


def test_the_icon_keeps_the_keyboard_focus_after_each_poll():
    """013, aviso 4: el sondeo devuelve el foco al elemento que lo tenía y los íconos se
    enfocan con el teclado y muestran su nombre con el foco."""
    js = (STATIC / "recorrido.js").read_text(encoding="utf-8")
    assert "function focusIndex" in js and ".focus()" in js
    css = (STATIC / "recorrido.css").read_text(encoding="utf-8")
    assert ".pw-icon:focus::after" in css and "attr(data-nombre)" in css


def test_section_1_is_never_ready_while_something_is_missing(case):
    """REQ-097 (T-217, brecha 2): la sección 1 con faltantes a la vista (el expediente, el
    cronograma, las garantías, los renglones con su cantidad) no queda «Lista»: queda pendiente."""
    for moment in MOMENTS:
        case.go_to(moment)
        section = sections.sections_for(case.operator, case.procedure).get("procedimiento")
        assert section.tema_missing, moment
        assert section.state == "pendiente", moment
