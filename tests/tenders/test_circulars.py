"""Circulares y respuestas a consultas en la propuesta de la matriz (REQ-031; plan 003,
"Circulares y respuestas"; T-083).

Pliegos y circulares sintéticos (`tests/tenders/pdfs.py`) y el doble del modelo con guion
(`tests/tenders/scripted.py`), ampliado acá para responder los pedidos de circulares. Todo el
texto es inventado (P4); sin modelo real.
"""

import json
import re
from datetime import date

import pytest

from evaluon.tenders import models as m
from evaluon.tenders.proposal import circulars
from evaluon.tenders.services import matrix_page
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import (
    PAGO,
    Script,
    item,
    load_and_read,
    make_procedure,
    propose,
)

pytestmark = pytest.mark.django_db

VISITA = "Los oferentes deberán presentar constancia de visita al lugar de entrega."
VISITA_QUOTE = "presentar constancia de visita al lugar de entrega"
RAM = "La computadora tendrá 16 GB de RAM."
MONITOR = "El monitor tendrá 24 pulgadas."

_CITES = re.compile(r"\[(Q\d+)\]\n(.*?)\n\[/\1\]", re.DOTALL)
_TRAMO = re.compile(r"Tramo de la circular:\n\n(.*?)\n\nDevolvé", re.DOTALL)
_CONTEXT = re.compile(r"Contexto de la circular[^\n]*:\n\n(.*?)\n\nTramo de la circular:",
                      re.DOTALL)


def tender():
    """Dos condiciones y dos renglones; el renglón 1 pide 16 GB de RAM."""
    return tender_pdf([
        [
            para("SECCIÓN I - CONDICIONES PARTICULARES"),
            para("1. PRESENTACIÓN", f"1.1. {VISITA}"),
            para("2. PAGO", f"2.1. {PAGO}"),
        ],
        [
            para("SECCIÓN II - ESPECIFICACIONES TÉCNICAS PARTICULARES"),
            para("1. RENGLÓN N° 1 - COMPUTADORA SINTÉTICA", f"1.1. {RAM}"),
            para("2. RENGLÓN N° 2 - MONITOR SINTÉTICO", f"2.1. {MONITOR}"),
        ],
    ])


def circular(*lines):
    """Una circular de una página: un tramo por cláusula numerada."""
    return tender_pdf([[para("CIRCULAR SINTÉTICA", *lines)]], header=None)


class CircularScript(Script):
    """El guion de `scripted.py` más las respuestas de los pedidos de circulares.

    `c_when(texto_del_tramo, efectos=[(texto_de_la_cita, efecto, fragmento)], nuevos=[(fragmento,
    clase)], sin_efecto=…)` responde a todo tramo que contiene `texto_del_tramo`; la cita se
    elige por el texto que contiene su bloque. Sin regla, el tramo es `dato_procedimiento`.
    `requests` guarda, por pedido, el tramo y los bloques de citas que recibió el modelo.
    `raw(texto_del_tramo, [salidas])` responde esas salidas sin tocar, una por pedido."""

    def __init__(self, fake, monkeypatch):
        super().__init__(fake, monkeypatch)
        self.c_rules = []
        self.raw_rules = []
        self.requests = []

    def c_when(self, needle, efectos=(), nuevos=(), sin_efecto=""):
        self.c_rules.insert(0, (needle, efectos, nuevos, sin_efecto))

    def raw(self, needle, outputs):
        self.raw_rules.insert(0, (needle, list(outputs)))

    def _generate(self, messages, schema, **options):
        if "efectos" not in schema.get("properties", {}):
            return super()._generate(messages, schema, **options)
        user = messages[-1]["content"]
        cites = {alias: body for alias, body in _CITES.findall(user)}
        tramo = _TRAMO.search(user).group(1).partition("\nTexto:\n")[2]
        context = _CONTEXT.search(user)
        self.requests.append({"messages": messages, "schema": schema, "cites": cites,
                              "tramo": tramo, "context": context.group(1) if context else ""})
        for needle, outputs in self.raw_rules:
            if needle in tramo and outputs:
                self.fake.respond(outputs.pop(0))
                return self.fake.generate(messages, schema, **options)
        answer = {"efectos": [], "nuevos": [], "sin_efecto": "dato_procedimiento"}
        for needle, efectos, nuevos, sin_efecto in self.c_rules:
            if needle not in tramo:
                continue
            answer = {"efectos": [], "nuevos": [{"cita": t, "clase": k} for t, k in nuevos],
                      "sin_efecto": sin_efecto}
            for cite_text, effect, fragment in efectos:
                alias = next((a for a, body in cites.items() if cite_text in body), "Q99")
                answer["efectos"].append({"cita": alias, "efecto": effect, "texto": fragment})
            break
        self.fake.respond(json.dumps(answer, ensure_ascii=False))
        return self.fake.generate(messages, schema, **options)


@pytest.fixture
def script(fake_generation, monkeypatch):
    return CircularScript(fake_generation, monkeypatch)


@pytest.fixture
def case(operator_user, script):
    """Un pliego leído, con un modelo que acierta lo formal y marca lo técnico."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, tender())
    script.when(VISITA, item([(VISITA_QUOTE, "formal")]))
    script.when(PAGO, item([(PAGO, "economico")]))
    script.when(RAM, item(technical=["1"]))
    script.when(MONITOR, item(technical=["2"]))
    return procedure


def add_circular(user, procedure, title, issued_on, *lines, kind="circular_modificatoria"):
    return load_and_read(user, procedure, circular(*lines), kind=kind, title=title,
                         issued_on=issued_on)


def run_proposal(user, procedure, level="media"):
    requested, job = propose(user, procedure, level=level)
    assert job.status == "done", job.error
    return requested.run.version, requested.run


def requirement_with(version, text):
    for requirement in version.requirements.order_by("number"):
        if any(text in q.text for q in requirement.quotes.all()):
            return requirement
    raise AssertionError(f"ningún requisito cita {text!r}")


def steps_for(text):
    """Los pedidos de circulares cuyo tramo contiene `text`, en orden."""
    return [s for s in m.RunStep.objects.filter(pass_name="circulares").order_by("id")
            if text in s.request["messages"][-1]["content"]]


def step_for(text):
    """El pedido de circulares cuyo tramo contiene `text`."""
    return next(s for s in m.RunStep.objects.filter(pass_name="circulares").order_by("id")
                if text in s.request["messages"][-1]["content"])


def row_of_item(version, number):
    return version.requirements.get(category="tecnico", items=[number])


# --- El criterio de aceptación (REQ-031) --------------------------------------------------------------


def test_modifying_circular_changes_the_item_row_and_keeps_both_texts(operator_user, case,
                                                                      script):
    """REQ-031: el pliego dice "16 GB de RAM" y una circular posterior "32 GB": la fila del
    renglón exige 32 GB en esa cita, conserva el texto original y cita la circular."""
    add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "1. Reemplázase en el Renglón N° 1 la memoria de 16 GB de RAM por 32 GB "
                 "de RAM.")
    script.c_when("por 32 GB", efectos=[("16 GB de RAM", "modifica", "32 GB de RAM")])

    version, _ = run_proposal(operator_user, case)

    row = row_of_item(version, 1)
    source = row.sources.get()
    assert source.effect == "modifica" and source.issued_on == date(2025, 12, 1)
    assert source.text == "32 GB de RAM"
    assert source.segment.reading.document.title == "Circular N.º 1"
    assert source.segment.reading.canonical_text[source.char_start:source.char_end] == \
        source.text
    # La cita alcanzada conserva el texto original del pliego.
    assert RAM in source.quote.text and "16 GB" in source.quote.text
    assert source.quote.requirement == row
    # La otra fila no cambia.
    assert not row_of_item(version, 2).sources.exists()

    page = matrix_page.matrix_page(operator_user, version.pk)
    quote = next(q for r in page.technical if r.requirement == row for q in r.quotes
                 if q.quote_id == source.quote_id)
    assert quote.current.text == "32 GB de RAM" and RAM in quote.text
    assert quote.current.place.document_title == "Circular N.º 1"


def test_the_model_sees_the_candidates_the_tramo_names(operator_user, case, script):
    """REQ-031: las citas candidatas incluyen las que el tramo nombra ("Renglón N° 1") y el
    pedido deja constancia de por qué se mostró cada una."""
    add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "1. Reemplázase en el Renglón N° 1 la memoria de 16 GB de RAM por 32 GB "
                 "de RAM.")

    run_proposal(operator_user, case)

    request = next(r for r in script.requests if "por 32 GB" in r["tramo"])
    assert any(RAM in body for body in request["cites"].values())
    step = step_for("por 32 GB")
    assert step.parsed["candidatas"]["renglones"] == [1]
    assert step.segment_keys and step.request["messages"][0]["role"] == "system"


# --- Aclaración y respuesta a una consulta -----------------------------------------------------------------


def test_answer_to_a_query_that_clarifies_is_shown_next_to_the_requirement(operator_user,
                                                                          case, script):
    """REQ-031: una respuesta a una pregunta de un oferente que precisa un requisito queda
    como `aclara` junto a ese requisito, con su cita."""
    add_circular(operator_user, case, "Respuesta a la consulta 1", date(2025, 12, 3),
                 "1. Pregunta: ¿Alcanza una constancia emitida por el correo? Respuesta: "
                 "la constancia de visita puede emitirla el correo.",
                 kind="respuesta_consulta")
    script.c_when("Respuesta:", efectos=[("constancia de visita", "aclara",
                                          "la constancia de visita puede emitirla el correo")])

    version, _ = run_proposal(operator_user, case)

    requirement = requirement_with(version, VISITA_QUOTE)
    source = requirement.sources.get()
    assert source.effect == "aclara"
    assert source.quote == requirement.quotes.get()
    assert source.segment.reading.document.kind == "respuesta_consulta"
    assert requirement.state == "propuesto"
    page = matrix_page.matrix_page(operator_user, version.pk)
    row = next(r for g in page.groups for r in g.rows if r.requirement == requirement)
    assert [n.effect for n in row.quotes[0].notes] == ["aclara"]
    assert row.quotes[0].current is None
    assert row.quotes[0].notes[0].place.document_title == "Respuesta a la consulta 1"


# --- Supresión -------------------------------------------------------------------------------------------


def test_suppressing_circular_leaves_the_requirement_removed_with_its_citation(
        operator_user, case, script):
    """REQ-031: un requisito suprimido queda quitado, visible y con la cita de la circular."""
    add_circular(operator_user, case, "Circular N.º 2", date(2025, 12, 5),
                 "1. Déjase sin efecto la exigencia de la constancia de visita.")
    script.c_when("sin efecto", efectos=[("constancia de visita", "suprime",
                                          "Déjase sin efecto la exigencia")])

    version, _ = run_proposal(operator_user, case)

    requirement = requirement_with(version, VISITA_QUOTE)
    assert requirement.state == "quitado"
    source = requirement.sources.get()
    assert source.effect == "suprime" and "sin efecto" in source.text
    assert requirement.quotes.get().text == VISITA_QUOTE
    page = matrix_page.matrix_page(operator_user, version.pk)
    removed = [r for r in page.removed if r.requirement == requirement]
    assert removed and [n.effect for n in removed[0].quotes[0].notes] == ["suprime"]
    # El otro requisito sigue vigente.
    assert requirement_with(version, PAGO).state == "propuesto"


def test_suppressing_one_technical_citation_keeps_the_row(operator_user, case, script):
    """REQ-031: en un técnico, la supresión alcanza a esa cita; la fila del renglón sigue."""
    add_circular(operator_user, case, "Circular N.º 2", date(2025, 12, 5),
                 "1. Déjase sin efecto la especificación del monitor del Renglón N° 2.")
    script.c_when("sin efecto", efectos=[("24 pulgadas", "suprime", "Déjase sin efecto")])

    version, _ = run_proposal(operator_user, case)

    row = row_of_item(version, 2)
    assert row.state == "propuesto"
    assert row.sources.get().effect == "suprime"


# --- Dos circulares sobre la misma cita ---------------------------------------------------------------------


def test_two_circulars_on_the_same_citation_apply_by_date_not_by_load_order(
        operator_user, case, script):
    """REQ-031: dos circulares sobre la misma cita se aplican por fecha: la segunda ve el
    texto que dejó la primera y el vigente es el de la última por fecha."""
    # Se carga primero la de diciembre y después la de noviembre.
    add_circular(operator_user, case, "Circular N.º 2", date(2025, 12, 10),
                 "1. Reemplázase en el Renglón N° 1 la memoria de 32 GB de RAM por 64 GB "
                 "de RAM.")
    add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "1. Reemplázase en el Renglón N° 1 la memoria de 16 GB de RAM por 32 GB "
                 "de RAM.")
    script.c_when("por 32 GB", efectos=[("16 GB de RAM", "modifica", "32 GB de RAM")])
    script.c_when("por 64 GB", efectos=[("GB de RAM", "modifica", "64 GB de RAM")])

    version, _ = run_proposal(operator_user, case)

    asked = [r for r in script.requests if "Reemplázase" in r["tramo"]]
    assert "por 32 GB" in asked[0]["tramo"] and "por 64 GB" in asked[1]["tramo"]
    # La segunda circular vio el texto vigente que dejó la primera.
    second = asked[1]["cites"]
    assert any("Texto vigente:\n32 GB de RAM" in body and "Texto original:" in body
               for body in second.values())
    row = row_of_item(version, 1)
    sources = list(row.sources.order_by("issued_on", "id"))
    assert [s.text for s in sources] == ["32 GB de RAM", "64 GB de RAM"]
    assert [s.issued_on for s in sources] == [date(2025, 12, 1), date(2025, 12, 10)]
    page = matrix_page.matrix_page(operator_user, version.pk)
    quote = next(q for r in page.technical if r.requirement == row for q in r.quotes
                 if q.current)
    assert quote.current.text == "64 GB de RAM"


# --- Requisitos nuevos ------------------------------------------------------------------------------------


def test_circular_can_add_a_requirement_that_gets_consequences(operator_user, case, script):
    """REQ-031: un requisito que agrega una circular tiene origen `circular`, cita a la
    circular y recibe su consecuencia ("no determinada" sin fundamento)."""
    add_circular(operator_user, case, "Circular N.º 3", date(2025, 12, 7),
                 "1. Los oferentes deberán presentar una declaración jurada de aptitud "
                 "fiscal.")
    script.c_when("declaración jurada", nuevos=[
        ("presentar una declaración jurada de aptitud fiscal", "formal")])

    version, run = run_proposal(operator_user, case)

    new = version.requirements.get(origin="circular")
    assert new.category == "formal" and new.number == version.requirements.count()
    quote = new.quotes.get()
    assert quote.text == "presentar una declaración jurada de aptitud fiscal"
    assert quote.segment.reading.document.title == "Circular N.º 3"
    assert quote.segment.reading.canonical_text[quote.char_start:quote.char_end] == quote.text
    assert new.proposed["quotes"][0]["text"] == quote.text
    assert list(new.consequences.values_list("consequence_type", flat=True)) == [
        "no_determinada"]
    assert run.counts["requirements_by_class"]["formal"] == 2
    assert run.counts["circulars"]["new_requirements"] == 1


# --- Disposición de cada tramo de circular ------------------------------------------------------------------


def test_every_circular_segment_has_a_disposition(operator_user, case, script):
    """REQ-031 / ADR-0019: todo tramo de una circular queda con disposición: con efectos
    `requisitos`, sin efecto `descartado` con motivo, un título descartado."""
    document = add_circular(
        operator_user, case, "Circular N.º 1", date(2025, 12, 1),
        "1. Reemplázase en el Renglón N° 1 la memoria de 16 GB de RAM por 32 GB de RAM.",
        "2. Prorrógase la fecha de apertura de ofertas al 10 de diciembre.")
    script.c_when("por 32 GB", efectos=[("16 GB de RAM", "modifica", "32 GB de RAM")])

    _, run = run_proposal(operator_user, case)

    reading = document.readings.get()
    segments = list(reading.segments.all())
    assert segments
    dispositions = {d.segment_id: d for d in m.Disposition.objects.filter(
        run=run, segment__reading=reading)}
    assert set(dispositions) == {s.pk for s in segments}
    by_text = {s.pk: s.text for s in segments}
    outcomes = {("por 32 GB" in by_text[pk], "Prorrógase" in by_text[pk]): d
                for pk, d in dispositions.items()}
    assert outcomes[(True, False)].outcome == "requisitos"
    assert outcomes[(True, False)].source == "modelo" and outcomes[(True, False)].step
    assert outcomes[(False, True)].outcome == "descartado"
    assert outcomes[(False, True)].discard_reason == "dato_procedimiento"
    assert all(d.outcome in ("requisitos", "descartado", "pendiente", "tecnico")
               for d in dispositions.values())


def test_invalid_output_is_retried_once_and_then_left_pending(operator_user, case, script):
    """REQ-031 / P3: un tramo cuya salida no tiene la forma se repite una vez; si sigue mal
    queda pendiente (`sin_disposicion`), nunca sin disposición."""
    document = add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                            "1. Reemplázase en el Renglón N° 1 la memoria por 32 GB de RAM.")
    script.raw("por 32 GB", ["basura", '{"efectos": 3}'])

    version, run = run_proposal(operator_user, case)

    steps = steps_for("por 32 GB")
    assert len(steps) == 2 and steps[1].retry_of == steps[0]
    segment = document.readings.get().segments.get(text__contains="por 32 GB")
    assert m.Disposition.objects.get(run=run, segment=segment).outcome == "pendiente"
    pending = m.PendingItem.objects.get(version=version, segment=segment)
    assert pending.reason == "sin_disposicion"
    assert not m.RequirementSource.objects.filter(requirement__version=version).exists()


def test_a_fragment_not_in_the_circular_is_retried_and_then_cites_the_whole_tramo(
        operator_user, case, script):
    """REQ-031 / REQ-025: si el fragmento no está en el tramo se repite el pedido; si sigue
    sin estar, el efecto no se pierde: cita el tramo entero y se anota."""
    add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "1. Reemplázase en el Renglón N° 1 la memoria de 16 GB de RAM por 32 GB "
                 "de RAM.")
    bad = json.dumps({"efectos": [{"cita": "Q1", "efecto": "modifica",
                                   "texto": "treinta y dos gigas"}],
                      "nuevos": [], "sin_efecto": ""})
    script.raw("por 32 GB", [bad, bad])

    version, run = run_proposal(operator_user, case)

    source = m.RequirementSource.objects.get(requirement__version=version)
    assert source.text == source.segment.text and "32 GB" in source.text
    assert len(steps_for("por 32 GB")) == 2
    assert any(a["type"] == "circular_cita_amplia" for a in run.anomalies)


def test_effect_on_a_citation_that_was_not_shown_is_dropped(operator_user, case, script):
    """REQ-031: un alias que el pedido no mostró invalida ese efecto; sin otro efecto, el
    tramo se repite y queda pendiente."""
    add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "1. Reemplázase en el Renglón N° 1 la memoria por 32 GB de RAM.")
    script.c_when("por 32 GB", efectos=[("no está en ninguna cita", "modifica",
                                          "32 GB de RAM")])

    version, run = run_proposal(operator_user, case)

    assert not m.RequirementSource.objects.filter(requirement__version=version).exists()
    assert run.counts["circulars"]["dropped_effects"] == 2
    assert any(a["type"] == "circular_cita_inexistente" for a in run.anomalies)


# --- Candidatas: nombradas y reranker ------------------------------------------------------------------------


def test_named_in_finds_clauses_and_items():
    """REQ-031: el tramo nombra cláusulas y renglones de las formas del pliego."""
    clauses, items = circulars.named_in(
        "Modifícase la cláusula 1.1 y las cláusulas 2.3 y 4.5.1 del Renglón N° 2, y los "
        "renglones 4 a 6. Artículo 12.")
    assert clauses == {"1.1", "2.3", "4.5.1", "12"}
    assert items == {2, 4, 5, 6}
    assert circulars.named_in("Se prorroga el plazo.") == (set(), set())


def test_reranker_picks_the_best_candidates_besides_the_named_ones(
        operator_user, case, script, fake_reranker, settings):
    """REQ-031: las candidatas son las nombradas más las `MATRIX_CIRCULAR_CANDIDATES` mejores
    del reranker; una nombrada entra aunque puntúe bajo."""
    settings.MATRIX_CIRCULAR_CANDIDATES = 1
    add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "1. Reemplázase en la cláusula 2.1 el plazo de pago por 60 días corridos.")
    fake_reranker.scores = {"constancia de visita": 0.9, "24 pulgadas": 0.1}
    fake_reranker.default = 0.0

    run_proposal(operator_user, case)

    request = next(r for r in script.requests if "plazo de pago" in r["tramo"])
    texts = " ".join(request["cites"].values())
    assert PAGO in texts                      # nombrada (cláusula 2.1), con puntaje bajo
    assert "constancia de visita" in texts    # la mejor del reranker
    # "cláusula 2.1" también es la numeración de las especificaciones del renglón 2: ante la
    # duda, de más.
    assert "24 pulgadas" in texts and RAM not in texts
    assert len(request["cites"]) == 3
    step = step_for("plazo de pago")
    assert step.parsed["candidatas"]["clausulas"] == ["2.1"]
    assert step.parsed["candidatas"]["puntajes"]
    assert fake_reranker.calls


# --- Registro (P6) y sin circulares ---------------------------------------------------------------------------


def test_the_proposal_records_the_circulars_and_the_instructions_used(operator_user, case,
                                                                      script):
    """P6: la propuesta deja las circulares usadas, la versión de las instrucciones y el
    pedido completo de cada tramo; el hecho de auditoría las trae."""
    from evaluon.audit.models import AuditEvent, EventType

    document = add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                            "1. Reemplázase en el Renglón N° 1 la memoria por 32 GB de RAM.")
    script.c_when("por 32 GB", efectos=[("16 GB de RAM", "modifica", "32 GB de RAM")])

    version, run = run_proposal(operator_user, case)

    assert run.prompt_versions["circulares"] == "matriz-circulares-v2"
    assert "circulares" in run.parameters["passes"]
    used = run.counts["circulars"]["documents"]
    assert [d["document"] for d in used] == [document.pk]
    assert used[0]["issued_on"] == "2025-12-01" and len(used[0]["sha256"]) == 64
    step = step_for("por 32 GB")
    assert step.request and step.raw_output and step.parsed["valida"] is True
    event = AuditEvent.objects.get(event_type=EventType.MATRIX_PROPOSAL)
    assert event.detail["circulars"] == used
    assert event.detail["counts"]["circulars"]["effects"] == 1
    assert not any(a["type"] == "documentos_no_procesados" for a in run.anomalies)


def test_without_circulars_nothing_changes(operator_user, case, script):
    """Sin circulares la propuesta no hace pedidos de circulares ni los registra."""
    version, run = run_proposal(operator_user, case)

    assert not m.RunStep.objects.filter(pass_name="circulares").exists()
    assert "circulares" not in run.prompt_versions
    assert "circulars" not in run.counts
    assert not m.RequirementSource.objects.exists()
    assert script.requests == []


# --- Consecuencias sobre el texto vigente ----------------------------------------------------------------


def test_consequences_are_asked_on_the_current_text_with_the_original(operator_user, case,
                                                                      script):
    """REQ-031 / REQ-029: la consecuencia de un requisito que una circular cambió se pide
    sobre el texto vigente (el de la circular), mostrando además el original; lo que no
    cambió se pide como siempre."""
    add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "1. Reemplázase en la cláusula 2.1 el plazo de 90 días por 60 días corridos.",
                 "2. Reemplázase en el Renglón N° 1 la memoria de 16 GB de RAM por 32 GB "
                 "de RAM.")
    script.c_when("por 60 días", efectos=[("90 días", "modifica", "60 días corridos")])
    script.c_when("por 32 GB", efectos=[("16 GB de RAM", "modifica", "32 GB de RAM")])

    run_proposal(operator_user, case)

    blocks = {}
    for messages in script.consequence_calls:
        blocks.update({a: b for a, b in re.findall(
            r"\[(R\d+)\]\n(.*?)\n\[/\1\]", messages[-1]["content"], re.DOTALL)})
    pago = next(b for b in blocks.values() if "Clase: económico" in b)
    assert "Texto vigente (según una circular):\n60 días corridos" in pago
    assert "Texto original del pliego:\n" in pago and PAGO in pago
    visita = next(b for b in blocks.values() if VISITA_QUOTE in b)
    assert "Texto:\n" + VISITA_QUOTE in visita and "vigente" not in visita
    ram = next(b for b in blocks.values() if "Renglón 1, especificaciones" in b)
    assert "Texto vigente (según una circular):\n32 GB de RAM" in ram and "16 GB" in ram


# --- Suprimido y vuelto a modificar (O1) ----------------------------------------------------------------


def test_a_later_circular_that_modifies_a_suppressed_requirement_makes_it_current_again(
        operator_user, case, script):
    """REQ-031: si una circular suprime un requisito y otra posterior lo modifica, vuelve a
    estar vigente (`propuesto`) con el texto de la última, y las dos fuentes quedan."""
    add_circular(operator_user, case, "Circular N.º 2", date(2025, 12, 5),
                 "1. Restablécese la exigencia de constancia de visita, que deberá "
                 "presentarse en la sede.")
    add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "1. Déjase sin efecto la exigencia de la constancia de visita.")
    script.c_when("sin efecto", efectos=[("constancia de visita", "suprime",
                                          "Déjase sin efecto la exigencia")])
    script.c_when("Restablécese", efectos=[("constancia de visita", "modifica",
                                            "constancia de visita, que deberá presentarse "
                                            "en la sede")])

    version, _ = run_proposal(operator_user, case)

    requirement = requirement_with(version, VISITA_QUOTE)
    assert requirement.state == "propuesto"
    sources = list(requirement.sources.order_by("issued_on", "id"))
    assert [s.effect for s in sources] == ["suprime", "modifica"]
    page = matrix_page.matrix_page(operator_user, version.pk)
    row = next(r for g in page.groups for r in g.rows if r.requirement == requirement)
    assert "en la sede" in row.quotes[0].current.text
    assert [n.effect for n in row.quotes[0].notes] == ["suprime"]
    assert not [r for r in page.removed if r.requirement == requirement]


# --- Controles que solo detectaban las sondas (M6, M8, M13, M18) ------------------------------------------


def test_page_segments_of_a_circular_are_pending_and_titles_discarded_by_rule():
    """REQ-031 / ADR-0019 (M6): una página de una circular queda pendiente por regla; un
    título, descartado. Un tramo no ubicado ya no se resuelve por regla (T-098): lo ve el
    modelo y sigue pendiente de revisión por la lectura (REQ-028)."""
    from types import SimpleNamespace

    assert circulars.Processor._rule(SimpleNamespace(segment_type="no_ubicado")) is None
    verdict = circulars.Processor._rule(SimpleNamespace(segment_type="pagina"))
    assert verdict.outcome == "pendiente" and verdict.discard_reason == ""
    title = circulars.Processor._rule(SimpleNamespace(segment_type="titulo"))
    assert (title.outcome, title.discard_reason) == ("descartado", "titulo")
    assert circulars.Processor._rule(SimpleNamespace(segment_type="clausula")) is None


def test_a_clarification_does_not_change_the_current_text(operator_user, case, script):
    """REQ-031 (M8): `aclara` deja la fuente junto a la cita pero no cambia el texto vigente,
    que sigue siendo el original (la pantalla no lo muestra como modificado) y las
    consecuencias se piden sobre el original."""
    add_circular(operator_user, case, "Respuesta a la consulta 1", date(2025, 12, 3),
                 "1. Respuesta: la constancia de visita puede emitirla el correo.",
                 kind="respuesta_consulta")
    script.c_when("Respuesta:", efectos=[("constancia de visita", "aclara",
                                          "la constancia de visita puede emitirla el correo")])

    version, _ = run_proposal(operator_user, case)

    requirement = requirement_with(version, VISITA_QUOTE)
    page = matrix_page.matrix_page(operator_user, version.pk)
    row = next(r for g in page.groups for r in g.rows if r.requirement == requirement)
    assert row.quotes[0].current is None and row.quotes[0].text == VISITA_QUOTE
    block = next(body for messages in script.consequence_calls
                 for _, body in re.findall(r"\[(R\d+)\]\n(.*?)\n\[/\1\]",
                                           messages[-1]["content"], re.DOTALL)
                 if VISITA_QUOTE in body)
    assert "vigente" not in block and "Texto:\n" + VISITA_QUOTE in block


def test_disposition_with_effects_and_a_reason_at_once_is_rejected():
    """REQ-031 / ADR-0019 (M13): una salida con efectos (o nuevos) y también un motivo de
    sin efecto no tiene disposición; tampoco la que no trae ninguna cosa."""
    both = circulars.shape({"efectos": [{"cita": "Q1", "efecto": "modifica", "texto": "x"}],
                            "nuevos": [], "sin_efecto": "dato_procedimiento"})
    new_and_reason = circulars.shape({"efectos": [], "sin_efecto": "titulo",
                                      "nuevos": [{"cita": "x", "clase": "formal"}]})
    neither = circulars.shape({"efectos": [], "nuevos": [], "sin_efecto": ""})
    ok = circulars.shape({"efectos": [], "nuevos": [], "sin_efecto": "titulo"})
    assert not both.has_disposition and not new_and_reason.has_disposition
    assert not neither.has_disposition and ok.has_disposition


def test_both_at_once_output_is_retried_and_then_left_pending(operator_user, case, script):
    """REQ-031 (M13): la salida con efectos y motivo a la vez no se acepta: se repite una
    vez y, si sigue igual, el tramo queda pendiente sin crear fuentes."""
    document = add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                            "1. Reemplázase en el Renglón N° 1 la memoria por 32 GB de RAM.")
    both = json.dumps({"efectos": [{"cita": "Q1", "efecto": "modifica",
                                    "texto": "32 GB de RAM"}],
                       "nuevos": [], "sin_efecto": "dato_procedimiento"})
    script.raw("por 32 GB", [both, both])

    version, run = run_proposal(operator_user, case)

    assert len(steps_for("por 32 GB")) == 2
    segment = document.readings.get().segments.get(text__contains="por 32 GB")
    assert m.Disposition.objects.get(run=run, segment=segment).outcome == "pendiente"
    assert not m.RequirementSource.objects.filter(requirement__version=version).exists()


def test_a_general_technical_citation_reaches_every_item_row(operator_user, script):
    """REQ-031 (M18): una cita técnica común a todos los renglones es una sola candidata; si
    una circular la modifica, el efecto alcanza la fila de cada renglón."""
    general = "Los bienes tienen vencimiento mayor a once meses."
    pdf = tender_pdf([
        [
            para("SECCIÓN I - ESPECIFICACIONES TÉCNICAS GENERALES"),
            para("1. CLÁUSULAS GENERALES", f"1.1. {general}"),
        ],
        [
            para("SECCIÓN II - ESPECIFICACIONES TÉCNICAS PARTICULARES"),
            para("1. RENGLÓN N° 1 - PRODUCTO SINTÉTICO A", "1.1. Bolsa de veinte kilos."),
            para("2. RENGLÓN N° 2 - PRODUCTO SINTÉTICO B", "2.1. Bolsa de diez kilos."),
        ],
    ])
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, pdf)
    add_circular(operator_user, procedure, "Circular N.º 1", date(2025, 12, 1),
                 "1. Reemplázase el vencimiento mayor a once meses por doce meses.")
    script.c_when("por doce meses", efectos=[("vencimiento mayor", "modifica",
                                              "doce meses")])

    version, _ = run_proposal(operator_user, procedure)

    rows = [row_of_item(version, 1), row_of_item(version, 2)]
    for row in rows:
        assert row.sources.get().quote == row.quotes.get(scope="general")
    assert rows[0].sources.get().quote != rows[1].sources.get().quote
    assert rows[0].sources.get().char_start == rows[1].sources.get().char_start
    request = next(r for r in script.requests if "por doce meses" in r["tramo"])
    assert sum("vencimiento mayor" in body for body in request["cites"].values()) == 1


# --- Pasada de circulares: causas generales de T-094 (T-098) ------------------------------------------------

ANEXO = "los oferentes deberán completar y adjuntar la planilla del anexo"
ANEXO_CLAUSE = f"1.1. ANEXO VI - PLANILLA SINTÉTICA: {ANEXO}."
FECHAS = ("Los interesados deberán asistir en la fecha indicada en el Anexo “FECHA DE VISITA” "
          "del portal")


def narrative_circular(*paragraphs):
    """Una circular de párrafos sueltos, cada uno un tramo (como una circular sin cláusulas)."""
    return tender_pdf([[para(line) for line in paragraphs]], header=None)


def economy_tender(operator_user, script, clause=ANEXO_CLAUSE, quote=ANEXO):
    pdf = tender_pdf([[para("SECCIÓN I - CONDICIONES PARTICULARES"),
                       para("1. ECONOMÍA", clause),
                       para("2. PAGO", f"2.1. {PAGO}")]])
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, pdf)
    script.when(quote, item([(quote, "formal")]))
    script.when(PAGO, item([(PAGO, "economico")]))
    return procedure


def test_a_tramo_that_names_an_annex_reaches_the_clause_that_defines_it(
        operator_user, script, fake_reranker, settings):
    """REQ-031 (T-094, M-029): un tramo que nombra "Anexo VI" alcanza la cita del requisito
    cuya cláusula lo define aunque el reranker no la ponga entre las mejores y la cita
    (un recorte de la cláusula) no repita el nombre del anexo."""
    settings.MATRIX_CIRCULAR_CANDIDATES = 0
    procedure = economy_tender(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 1", date(2025, 12, 1),
                 "1. La información del Anexo VI no será considerada como un requisito.")
    script.c_when("no será considerada", efectos=[(ANEXO, "suprime", "no será considerada")])

    version, _ = run_proposal(operator_user, procedure)

    request = next(r for r in script.requests if "no será considerada" in r["tramo"])
    assert any(ANEXO in body for body in request["cites"].values())
    assert PAGO not in " ".join(request["cites"].values())
    requirement = requirement_with(version, ANEXO)
    assert requirement.state == "quitado"
    assert requirement.sources.get().effect == "suprime"


def test_a_tramo_that_repeats_the_quoted_title_of_an_annex_reaches_the_citation(
        operator_user, script, fake_reranker, settings):
    """REQ-031 (T-094, M-044): un tramo que repite el título entre comillas de un anexo que
    la cita menciona ("Anexo “FECHA DE VISITA”") alcanza esa cita."""
    settings.MATRIX_CIRCULAR_CANDIDATES = 0
    procedure = economy_tender(operator_user, script, clause=f"1.1. {FECHAS}.", quote=FECHAS)
    load_and_read(operator_user, procedure,
                  narrative_circular("II. SE FIJAN NUEVAS FECHAS",
                                     "FECHA DE VISITA: 21 de julio"),
                  kind="circular_modificatoria", title="Circular N.º 1",
                  issued_on=date(2025, 12, 1))
    script.c_when("21 de julio", efectos=[(FECHAS, "modifica", "21 de julio")])

    version, _ = run_proposal(operator_user, procedure)

    request = next(r for r in script.requests if r["tramo"].startswith("FECHA DE VISITA"))
    assert any(FECHAS in body for body in request["cites"].values())
    assert PAGO not in " ".join(request["cites"].values())
    assert requirement_with(version, FECHAS).sources.get().effect == "modifica"


def test_a_numbered_heading_inside_the_tramo_names_that_clause():
    """REQ-031 (T-094, M-015): un "Debe decir" que reproduce la cláusula con su número
    ("7.5.5 CONFLICTO…") nombra esa cláusula, aunque no diga "cláusula"; el número con que
    empieza la circular misma ("1.1. Reemplázase…") no cuenta."""
    clauses, _ = circulars.named_in("DEBE DECIR:\n7.5.5 CONFLICTO DE INTERESES: texto")
    assert clauses == {"7.5.5"}
    clauses, _ = circulars.named_in("1.1. Reemplázase el plazo por diez días.")
    assert clauses == set()


def test_named_annexes_are_found_by_number_in_any_form():
    """REQ-031: "Anexo VI", "ANEXO N° 2" y "Anexo 3" nombran anexos; la palabra suelta no."""
    assert circulars.named_annexes("el Anexo VI y el ANEXO N° 2, también el anexo 3") == {
        "vi", "2", "3"}
    assert circulars.named_annexes("el anexo al presente pliego") == set()


def test_unlocated_segments_of_a_circular_reach_the_model_and_stay_pending(
        operator_user, case, script):
    """REQ-031 / REQ-028 (T-094, M-015): un tramo `no_ubicado` de una circular (como un
    "Debe decir" bajo el título de una sección) lo analiza el modelo y, además, sigue en
    "Pendiente de revisión" por la lectura."""
    pdf = tender_pdf([[para("CIRCULAR SINTÉTICA"),
                       para("SECCIÓN I - CONDICIONES PARTICULARES"),
                       para("DEBE DECIR:", "2.1. El pago se hará a sesenta días.")]],
                     header=None)
    document = load_and_read(operator_user, case, pdf, kind="circular_modificatoria",
                             title="Circular N.º 1", issued_on=date(2025, 12, 1))
    unlocated = m.Segment.objects.get(reading__document=document,
                                      segment_type="no_ubicado", text__contains="sesenta")
    script.c_when("sesenta días", efectos=[(PAGO, "modifica", "a sesenta días")])

    version, run = run_proposal(operator_user, case)

    assert any("sesenta" in r["tramo"] for r in script.requests)
    assert m.Disposition.objects.get(run=run, segment=unlocated).outcome == "requisitos"
    assert version.pending_items.filter(segment=unlocated, reason="no_ubicado").exists()
    assert requirement_with(version, PAGO).sources.get().effect == "modifica"


def test_a_loose_paragraph_is_shown_with_its_heading_and_the_previous_lines(
        operator_user, case, script):
    """REQ-031 (T-094, M-044): un párrafo suelto de una circular se muestra con el encabezado
    de su apartado ("II. …") y las dos líneas anteriores, aparte del tramo."""
    load_and_read(operator_user, case,
                  narrative_circular("I. OTRO APARTADO", "II. SE FIJAN NUEVAS FECHAS",
                                     "SEDE UNO", "HORA: 10hs", "PUNTO DE ENCUENTRO: puerta"),
                  kind="circular_modificatoria", title="Circular N.º 1",
                  issued_on=date(2025, 12, 1))

    run_proposal(operator_user, case)

    request = next(r for r in script.requests if r["tramo"].startswith("PUNTO DE ENCUENTRO"))
    context = request["context"]
    assert "II. SE FIJAN NUEVAS FECHAS" in context
    assert "SEDE UNO" in context and "HORA: 10hs" in context
    assert "I. OTRO APARTADO" not in context and "PUNTO DE ENCUENTRO" not in context


def test_a_numbered_clause_is_shown_without_context(operator_user, case, script):
    """REQ-031: una cláusula numerada de la circular se entiende sola: no lleva contexto."""
    add_circular(operator_user, case, "Circular N.º 1", date(2025, 12, 1),
                 "1. Reemplázase en la cláusula 2.1 el plazo de pago por 60 días corridos.")

    run_proposal(operator_user, case)

    request = next(r for r in script.requests if "plazo de pago" in r["tramo"])
    assert request["context"] == ""


def test_the_reranker_sees_the_clause_that_holds_the_citation_and_the_heading(
        operator_user, script, fake_reranker, settings):
    """REQ-031 (T-094, M-029): el reranker puntúa la cláusula completa con su ruta (la cita
    puede ser un recorte sin el nombre del anexo) contra el tramo con su encabezado."""
    settings.MATRIX_CIRCULAR_CANDIDATES = 1
    procedure = economy_tender(operator_user, script)
    load_and_read(operator_user, procedure,
                  narrative_circular("II. SE AJUSTA LA PLANILLA", "Se cambia el formato."),
                  kind="circular_modificatoria", title="Circular N.º 1",
                  issued_on=date(2025, 12, 1))

    run_proposal(operator_user, procedure)

    query, documents = fake_reranker.calls[-1][:2]
    assert query.startswith("II. SE AJUSTA LA PLANILLA") and "Se cambia el formato" in query
    assert any("ANEXO VI - PLANILLA SINTÉTICA" in d for d in documents)


def test_the_active_circular_instructions_are_v2_and_v1_is_kept(settings):
    """REQ-031 (T-098): la versión activa es la v2 y la v1 sigue en su archivo; la v2 agrega
    "Donde dice / Debe decir", el bloque de contexto y no elegir una cita ajena, con ejemplos
    inventados (sin texto del caso de medición)."""
    from evaluon.tenders.proposal import extraction

    assert settings.MATRIX_PROMPT_VERSIONS["circulares"] == "matriz-circulares-v2"
    v2 = extraction.load_prompt("circulares")
    assert "Donde dice" in v2 and "Debe decir" in v2
    assert "Contexto de la circular" in v2
    assert "nunca se elige una cita ajena" in v2
    assert v2.count("{") >= 8      # los ejemplos siguen con la forma de la salida
    assert "ARCA" not in v2 and "señalética" not in v2.lower()
    v1 = (extraction.PROMPTS_DIR / "matriz-circulares-v1.md").read_text(encoding="utf-8")
    assert "Debe decir" not in v1
