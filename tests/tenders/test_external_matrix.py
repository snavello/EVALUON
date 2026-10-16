"""La matriz con el modelo externo (T-291; REQ-122, REQ-123; plan 016, «Paso 3 · Matriz con
modelo externo»; ADR-0065 a ADR-0068).

Con el caso chico (`tests/assessment/data/caso-chico/`, inventado y público) y el doble del cliente
externo (`fake_external`, sin red: la suite bloquea toda llamada real), comprueba que:

- la propuesta externa manda el pliego completo como prefijo común, en pedidos de extracción y uno
  de completitud y filtro, y deja filas cuyas citas son recortes literales del texto canónico;
- un fragmento que el modelo inventa se descarta con `fragmento_externo_no_ubicado`;
- con el uso externo apagado (o la matriz en `local`) la propuesta es idéntica a la local;
- un pedido que falla, un bloqueo de la puerta y el tope vuelven a la cadena local con la anomalía;
- una hoja de compliance inventada no sale en ningún pedido;
- la propuesta guarda la clave `externo` y la línea «Etapas fuera del equipo» aparece en la pantalla
  de la matriz y en su impresión;
- `medir_matriz --externo matriz` corre dos propuestas sobre la misma lectura y suma el gasto real.

Todo el texto es inventado (P4).
"""

import json
import re
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.urls import reverse

from evaluon.ai.external import ledger
from evaluon.assessment import models as am
from evaluon.assessment.services import external_stages
from evaluon.audit.models import AuditEvent, EventType
from evaluon.tenders import evaluation as ev
from evaluon.tenders import models as m
from evaluon.tenders.proposal import external, extraction
from tests.accounts.test_session import TEST_PASSWORD
from tests.assessment.fakes import CASO_CHICO
from tests.offers.conftest import make_offer
from tests.tenders.pdfs import synthetic_tender_pdf
from tests.tenders.scripted import (  # noqa: F401  (fixture)
    ENTREGA,
    GARANTIA,
    MULTA,
    item,
    load_and_read,
    make_procedure,
    parse_blocks,
    propose,
    script,
    three_items_pdf,
)
from tests.tenders.test_evaluation import make_case

pytestmark = pytest.mark.django_db

KEYWORD = "ZORVANTIQ"
OBJECT = "El objeto es la adquisición de insumos de oficina sintéticos"
IDENTITY = "documento de identidad"
QUOTATION = "Cotizar en pesos con impuestos incluidos"
REGISTRY = "constancia de inscripción"
STATUTE = "certificado de vigencia"
DECLARATION = ("Presentar la declaración jurada de habilidad para contratar firmada por el "
               "oferente.")
INVENTED = "Una oración que el modelo inventó y que no figura en ningún tramo del pliego."
LINE = ("Etapas fuera del equipo: matriz de requisitos (anthropic, claude-sonnet-5-5, modo lotes, "
        "{n} pedidos).")
NONE_LINE = "Etapas fuera del equipo: Ninguna: todo corrió en el equipo."

_ASKED = re.compile(r"Tramos que decidís en este pedido: (.*?)\.\n")
_OPEN = re.compile(r"Tramos decididos: (.*?)\.\n")
_ROW = re.compile(r"\[(F\d+)\] Tramo: (T\d+)[^\n]*\nCita: (.*?)\n\[/\1\]", re.DOTALL)


def _first_line(text):
    return next(line.strip() for line in text.splitlines() if line.strip())


class ExternalScript:
    """Guion del doble externo: lee el pedido (el pliego del sistema y los tramos o las filas del
    mensaje) y contesta con la forma del esquema. Por omisión propone la primera línea de cada
    tramo como requisito formal y deja firme toda fila. `discard_segment` (texto → motivo) descarta
    el tramo que lo contiene; `invent` (texto) cita un fragmento inventado en ese tramo;
    `rows` (texto → respuesta) contesta esa respuesta a la fila cuya cita lo contiene;
    `missing` (texto del tramo → faltante); `fail_stage` hace fallar los pedidos de esa etapa."""

    def __init__(self, fake, monkeypatch):
        self.fake = fake
        self.payloads = []
        self.discard_segment = {}
        self.invent = set()
        self.rows = {}
        self.missing = {}
        self.fail_stage = None
        monkeypatch.setattr(fake, "_reply", self.reply)

    def reply(self, payload):
        self.payloads.append(payload)
        reply = {"kind": "respond", "model": None, "stop_reason": "end_turn", "usage": None}
        if self.fail_stage in (payload.stage, "todas"):
            return {**reply, "kind": "errored", "text": ""}
        user = payload.messages[0][1]
        blocks = parse_blocks(payload.system)
        if payload.stage == external.STAGE_EXTRACTION:
            answer = {"tramos": [self._segment(alias, blocks[alias]["text"])
                                 for alias in _ASKED.search(user).group(1).split(", ")]}
        else:
            answer = {"faltantes": self._missing(_OPEN.search(user).group(1).split(", "),
                                                 blocks),
                      "filas": [self._row(alias, quote) for alias, _, quote in _ROW.findall(user)]}
        return {**reply, "text": json.dumps(answer, ensure_ascii=False)}

    def _segment(self, alias, text):
        for needle, reason in self.discard_segment.items():
            if needle in text:
                return {"tramo": alias, "requisitos": [], "tecnico": [], "descarte": reason}
        quote = INVENTED if any(needle in text for needle in self.invent) else _first_line(text)
        return {"tramo": alias, "requisitos": [{"cita": quote, "clase": "formal", "opcion": ""}],
                "tecnico": [], "descarte": ""}

    def _missing(self, aliases, blocks):
        found = []
        for alias in aliases:
            for needle, entry in self.missing.items():
                if alias in blocks and needle in blocks[alias]["text"]:
                    found.append({"tramo": alias, **entry})
        return found

    def _row(self, alias, quote):
        for needle, answer in self.rows.items():
            if needle in quote:
                return {"fila": alias, **answer}
        return {"fila": alias, "destino": "firme", "motivo": "", "indicio": "",
                "razonamiento": ""}


@pytest.fixture
def ext(fake_external, monkeypatch):
    return ExternalScript(fake_external, monkeypatch)


@pytest.fixture
def small_case(operator_user, script):  # noqa: F811
    """El procedimiento del caso chico con su pliego leído. El guion local propone la primera
    línea de cada tramo (como `test_matriz_caso_chico_t279`)."""
    script.override(lambda blocks, number, answer: {
        alias: item([(_first_line(block["text"]), "formal")]) for alias, block in blocks.items()})
    return new_case(operator_user)


def new_case(user):
    procedure = make_procedure(user)
    document = load_and_read(user, procedure, (CASO_CHICO / "pliego.pdf").read_bytes(),
                             title="Pliego del caso chico")
    return SimpleNamespace(procedure=procedure, document=document,
                           canonical=document.readings.get().canonical_text)


def requests_of(run=None):
    """Los hechos de cada pedido externo (sin los de lote en vuelo, uno por lote: O-290-6)."""
    events = AuditEvent.objects.filter(event_type=EventType.EXTERNAL_REQUEST).exclude(
        detail__resultado="en_vuelo").order_by("pk")
    if run is not None:
        events = events.filter(detail__corrida={"tipo": "matriz", "numero": run.pk})
    return list(events)


def anomaly_types(run):
    return [anomaly["type"] for anomaly in run.anomalies]


def rows_of(run, **filters):
    return list(m.Requirement.objects.filter(version=run.version, **filters).order_by("number"))


def assert_literal(case, run):
    for row in rows_of(run):
        for quote in row.quotes.all():
            assert quote.text == case.canonical[quote.char_start:quote.char_end]


# --- La propuesta externa ------------------------------------------------------------------------


def test_the_external_proposal_makes_rows_with_literal_located_quotes(
        small_case, operator_user, ext, fake_external, script):  # noqa: F811
    """REQ-123: con la matriz en `externo`, la extracción, la completitud y el filtro los hace el
    modelo externo (ningún pedido local de esas pasadas); las filas salen con citas literales
    ubicadas en el texto canónico; una fila dudosa va a sugerencia, una descartada con su indicio
    queda en las descartadas y un faltante se suma a su tramo."""
    fake_external.enable("matriz")
    ext.discard_segment[OBJECT] = "dato_procedimiento"
    ext.missing[OBJECT] = {"cita": OBJECT, "clase": "formal", "opcion": "",
                           "destino": "firme"}
    ext.rows[IDENTITY] = {"destino": "sugerencia", "motivo": "", "indicio": "",
                          "razonamiento": "No se sabe si lo pide a toda oferta."}
    ext.rows[QUOTATION] = {"destino": "descartada", "motivo": "pago_factura",
                           "indicio": QUOTATION, "razonamiento": "Habla de la moneda."}
    # Un descarte cuyo indicio no está en el tramo no se sostiene: va a sugerencia.
    ext.rows[STATUTE] = {"destino": "descartada", "motivo": "formulario",
                         "indicio": "una frase que no figura en el tramo del pliego",
                         "razonamiento": "Parece un formulario."}

    requested, job = propose(operator_user, small_case.procedure)

    assert job.status == "done", job.error
    run = requested.run
    assert script.calls == [] and script.completeness_default_calls == []
    assert not m.RunStep.objects.filter(run=run, pass_name__in=["filtro", "filtro_2"]).exists()
    assert run.models["externo"]["etapas"] == {"matriz": "externo", "verificador": "local"}
    assert_literal(small_case, run)
    firm = rows_of(run, state="propuesto", category__in=["formal", "economico"])
    assert firm and any(OBJECT in row.quotes.get(order=1).text for row in firm)
    added = next(row for row in firm if OBJECT in row.quotes.get(order=1).text)
    assert added.passes == ["completitud"]
    suggested = {row.doubt_reason: row.quotes.get(order=1).text
                 for row in rows_of(run, state="sugerido")}
    assert len(suggested) == 2
    assert IDENTITY in suggested["duda"] and STATUTE in suggested["descarte_sin_sustento"]
    discarded = m.DiscardedRow.objects.get(run=run)
    assert discarded.reason == "pago_factura" and discarded.evidence_text == QUOTATION
    assert discarded.step_a.request["externo"]["etapa"] == external.STAGE_COMPLETION
    assert not any(QUOTATION in row.quotes.get(order=1).text for row in rows_of(run))
    # Los pedidos: uno de extracción (el caso chico tiene pocos tramos) y uno de completitud y
    # filtro, en lotes, cada uno con el pliego completo como sistema.
    events = requests_of(run)
    assert [e.detail["etapa"] for e in events] == [external.STAGE_EXTRACTION,
                                                   external.STAGE_COMPLETION]
    instruction = external.load_instruction()
    for event in events:
        detail = event.detail
        assert detail["resultado"] == "ok" and detail["modo"] == "lotes"
        assert detail["texto_enviado"]["sistema"].startswith(instruction.text.rstrip())
        assert "PLIEGO COMPLETO" in detail["texto_enviado"]["sistema"]
        assert detail["instruccion"]["version"] == "matriz-externa-v1"
        assert detail["definiciones"]["version"] == "matriz-definiciones-v10"
        assert detail["parametros"]["max_tokens"] == 32000
        assert detail["parametros"]["effort"] == "medium"
        assert detail["parametros"]["cache_system_ttl"] == "1h"
    assert events[0].detail["texto_enviado"]["sistema"] == events[1].detail["texto_enviado"][
        "sistema"]
    assert DECLARATION in events[0].detail["texto_enviado"]["sistema"]
    # Cada tramo entra con su documento (O-290-3): la puerta lo comprobó como pliego.
    segments = m.Segment.objects.filter(reading__document=small_case.document).count()
    for event in events:
        checked = event.detail["filtro"]
        assert checked["piezas"]["pliego"] >= segments
        assert checked["documentos"] == [{"origen": "pliego", "documento": small_case.document.pk,
                                          "tipo": "pliego"}]
    steps = m.RunStep.objects.filter(run=run, request__has_key="externo")
    assert {step.pass_name for step in steps} == {"extraccion", "completitud"}
    for step in steps:
        assert step.parsed["instruccion"] == instruction.record
        assert step.parsed["hecho"] in {e.pk for e in events}


def test_the_proposal_keeps_the_external_key_in_its_record(
        small_case, operator_user, ext, fake_external):
    """REQ-122: la propuesta guarda la clave `externo` en `models`, `parameters`,
    `prompt_versions` y `counts`, con la forma que lee la línea (contrato de T-300)."""
    fake_external.enable("matriz")

    requested, job = propose(operator_user, small_case.procedure)

    assert job.status == "done", job.error
    run = requested.run
    key = run.models["externo"]
    assert key["habilitado"] is True and key["proveedor"] == "anthropic"
    assert key["modelo"] == "claude-sonnet-5-5"
    assert run.parameters["externo"]["modo"] == "lotes"
    assert run.parameters["externo"]["matriz"]["reemplaza"] == list(external.REPLACED_PASSES)
    assert run.prompt_versions["externo"]["matriz"] == "matriz-externa-v1"
    assert run.prompt_versions["externo"]["huellas"]["matriz"] == (
        external.load_instruction().sha256)
    counts = run.counts["externo"]["matriz"]
    assert counts["pedidos"] == 2 and counts["volvio_a_local"] is False
    assert counts["gasto_usd"] == pytest.approx(sum(
        e.detail["costo_usd"] for e in requests_of(run)))
    assert external_stages.line([run]) == LINE.format(n=2)
    event = AuditEvent.objects.filter(event_type=EventType.MATRIX_PROPOSAL).latest("pk")
    assert event.detail["models"]["externo"]["etapas"]["matriz"] == "externo"


def test_an_invented_fragment_is_dropped_with_its_anomaly(
        small_case, operator_user, ext, fake_external):
    """REQ-123 (plan 016, «Cómo se cita»): un fragmento que el modelo inventa no se ubica: se
    descarta con la anomalía `fragmento_externo_no_ubicado` y el tramo queda pendiente de revisión
    (no descartado en silencio)."""
    fake_external.enable("matriz")
    ext.invent.add(REGISTRY)

    requested, job = propose(operator_user, small_case.procedure)

    assert job.status == "done", job.error
    run = requested.run
    lost = [a for a in run.anomalies if a["type"] == external.ANOMALY_NOT_LOCATED]
    assert len(lost) == 1
    segment = m.Segment.objects.get(pk=lost[0]["segment"])
    assert REGISTRY in segment.text
    assert not any(INVENTED in q.text for r in rows_of(run) for q in r.quotes.all())
    assert m.Disposition.objects.get(run=run, segment=segment).outcome == "pendiente"
    assert m.PendingItem.objects.filter(version=run.version, segment=segment).exists()
    assert_literal(small_case, run)


# --- Con el uso externo apagado, lo local de siempre ----------------------------------------------


def _requests_and_rows(run):
    steps = m.RunStep.objects.filter(run=run).order_by("pk")
    requests = [(step.pass_name, step.request.get("messages")) for step in steps]
    rows = [(r.category, r.state, [q.text for q in r.quotes.order_by("order")])
            for r in rows_of(run)]
    return requests, rows


def test_with_the_external_use_off_the_proposal_is_the_local_one(
        operator_user, script, ext, fake_external, settings):  # noqa: F811
    """REQ-122: con el uso externo apagado, o encendido con la matriz en `local`, la propuesta hace
    los mismos pedidos locales y da las mismas filas; no sale ningún pedido externo y la corrida no
    guarda la clave `externo` (la línea dice «Ninguna»)."""
    script.override(lambda blocks, number, answer: {
        alias: item([(_first_line(block["text"]), "formal")]) for alias, block in blocks.items()})
    first = new_case(operator_user)
    requested, job = propose(operator_user, first.procedure)
    assert job.status == "done", job.error
    off = requested.run

    fake_external.enable("verificador")  # encendido, pero la matriz sigue en `local`
    assert settings.EXTERNAL_ENABLED and settings.EXTERNAL_STAGES["matriz"] == "local"
    second = new_case(operator_user)
    requested, job = propose(operator_user, second.procedure)
    assert job.status == "done", job.error
    local = requested.run

    assert _requests_and_rows(off) == _requests_and_rows(local)
    assert _requests_and_rows(off)[1]
    for run in (off, local):
        for column in (run.models, run.parameters, run.prompt_versions, run.counts):
            assert "externo" not in column
        assert external_stages.line([run]) == NONE_LINE
    assert ext.payloads == [] and fake_external.batches == [] and fake_external.messages == []
    assert requests_of() == []


# --- Vuelta a lo local ---------------------------------------------------------------------------


def _assert_local_after_external(run, script, reason_type, reason):  # noqa: F811
    assert script.calls, "la cadena local no corrió"
    types = anomaly_types(run)
    assert reason_type in types and external.ANOMALY_UNAVAILABLE in types
    fallback = [a for a in run.anomalies
                if a["type"] == external.ANOMALY_UNAVAILABLE and "camino" in a]
    assert len(fallback) == 1
    assert fallback[0]["camino"] == "local" and fallback[0]["etapa"] == "matriz"
    assert fallback[0]["motivo"] == reason
    assert run.models["externo"]["etapas"]["matriz"] == "local"
    assert run.counts["externo"]["matriz"]["volvio_a_local"] is True
    assert run.parameters["externo"]["matriz"]["reemplaza"] == []
    assert external_stages.line([run]) == NONE_LINE
    assert m.RunStep.objects.filter(run=run, pass_name="extraccion").exclude(
        request__has_key="externo").exists()
    assert rows_of(run)


@pytest.mark.parametrize("stage", [external.STAGE_EXTRACTION, external.STAGE_COMPLETION])
def test_a_failed_request_goes_back_to_the_local_chain(
        small_case, operator_user, ext, fake_external, script, stage):  # noqa: F811
    """REQ-122 (plan 016, «Si el pedido externo falla»): un pedido de extracción o de completitud y
    filtro que falla deja la propuesta en la cadena local, con `externo_no_disponible`; nada de lo
    externo se aplica a medias."""
    fake_external.enable("matriz")
    ext.fail_stage = stage

    requested, job = propose(operator_user, small_case.procedure)

    assert job.status == "done", job.error
    run = requested.run
    _assert_local_after_external(run, script, ledger.ANOMALY_UNAVAILABLE, "service_unavailable")
    assert {e.detail["resultado"] for e in requests_of(run)
            if e.detail["etapa"] == stage} == {"error"}
    assert_literal(small_case, run)


def test_the_cap_goes_back_to_the_local_chain_without_sending(
        small_case, operator_user, ext, fake_external, script, settings):  # noqa: F811
    """REQ-122 (ADR-0068): con el tope del caso agotado el lote no sale, queda `bloqueado` con el
    motivo «tope» y la propuesta sigue por la cadena local."""
    fake_external.enable("matriz")
    settings.EXTERNAL_CASE_CAP_USD = Decimal("0.00000001")

    requested, job = propose(operator_user, small_case.procedure)

    assert job.status == "done", job.error
    run = requested.run
    assert fake_external.batches == [] and ext.payloads == []
    blocked = requests_of(run)
    assert blocked and {e.detail["resultado"] for e in blocked} == {"bloqueado"}
    assert {e.detail["motivo"] for e in blocked} == {"tope"}
    _assert_local_after_external(run, script, ledger.ANOMALY_BLOCKED, "tope")


def _sheet(procedure, user, paragraphs):
    return make_offer(procedure, user, "Oferente de la hoja inventada",
                      {"hoja-compliance.pdf": paragraphs, "economica.pdf": [
                          "Propuesta económica inventada del oferente de prueba."]},
                      kinds={"hoja-compliance.pdf": "compliance", "economica.pdf": "economica"})


def _nothing_of_the_sheet_left(paragraphs):
    for event in AuditEvent.objects.filter(event_type=EventType.EXTERNAL_REQUEST):
        sent = json.dumps(event.detail, ensure_ascii=False)
        assert KEYWORD not in sent
        for paragraph in paragraphs:
            assert paragraph not in sent


def test_a_gate_block_by_a_compliance_sheet_goes_back_to_the_local_chain(
        small_case, operator_user, ext, fake_external, script, fake_ai):  # noqa: F811
    """REQ-121, REQ-122: con una hoja de compliance inventada que copia una oración del pliego, la
    puerta bloquea el pedido entero (huella), nada sale al proveedor, ningún registro tiene texto de
    la hoja y la matriz se propone con la cadena local."""
    paragraphs = [f"Consulta {KEYWORD} inventada: el oferente copió la cláusula «{DECLARATION}»",
                  f"Situación previsional {KEYWORD} simulada, sin deuda exigible inventada."]
    _sheet(small_case.procedure, operator_user, paragraphs)
    fake_external.enable("matriz")

    requested, job = propose(operator_user, small_case.procedure)

    assert job.status == "done", job.error
    run = requested.run
    assert fake_external.batches == [] and ext.payloads == []
    blocked = requests_of(run)
    assert blocked and all(e.detail["resultado"] == "bloqueado" for e in blocked)
    assert all(e.detail["texto_enviado"] is None for e in blocked)
    assert "huella_compliance" in blocked[0].detail["motivos"]
    assert any(a["type"] == external.ANOMALY_BLOCKED and a["motivo"] == "huella_compliance"
               for a in run.anomalies)
    _assert_local_after_external(run, script, external.ANOMALY_BLOCKED, "bloqueado")
    _nothing_of_the_sheet_left(paragraphs)


def test_an_unrelated_compliance_sheet_never_reaches_a_request(
        small_case, operator_user, ext, fake_external, fake_ai):
    """REQ-121: con una hoja de compliance inventada que no repite el pliego, la propuesta externa
    corre y ningún pedido registrado (sistema, mensajes ni respuesta) contiene texto de la hoja ni
    su palabra clave."""
    paragraphs = [f"Consulta {KEYWORD} al registro inventado: el oferente figura inscripto con un "
                  "legajo de fantasía que vence un día que no existe.",
                  f"Sancionados {KEYWORD}: el oferente imaginario no aparece en el registro "
                  "inventado de empleadores sancionados."]
    _sheet(small_case.procedure, operator_user, paragraphs)
    fake_external.enable("matriz")

    requested, job = propose(operator_user, small_case.procedure)

    assert job.status == "done", job.error
    run = requested.run
    assert run.models["externo"]["etapas"]["matriz"] == "externo"
    assert len(ext.payloads) == 2
    for payload in ext.payloads:
        text = "\n".join([payload.system, *(content for _, content in payload.messages)])
        assert KEYWORD not in text
    _nothing_of_the_sheet_left(paragraphs)


# --- La línea en la pantalla y en la impresión de la matriz -----------------------------------------


def _log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def test_the_matrix_screen_and_its_print_say_which_stages_ran_outside(
        small_case, operator_user, ext, fake_external, client):
    """REQ-122: la pestaña «Pliego y matriz» y la impresión (y el PDF, misma plantilla) de una
    matriz propuesta con el modelo externo dicen «Etapas fuera del equipo» con proveedor, modelo,
    modo y pedidos, una sola vez."""
    fake_external.enable("matriz")
    requested, job = propose(operator_user, small_case.procedure)
    assert job.status == "done", job.error
    line = LINE.format(n=2)
    _log_in(client, operator_user)

    tab = client.get(reverse("expedientes:pliego", args=[small_case.procedure.pk]))
    printed = client.get(reverse("tenders:print", args=[requested.run.version_id]))

    for response in (tab, printed):
        assert response.status_code == 200
        assert response.content.decode().count(line) == 1


def test_a_local_matrix_says_none_on_the_screen(small_case, operator_user, client):
    """REQ-122: una matriz propuesta en el equipo dice «Ninguna: todo corrió en el equipo»."""
    requested, job = propose(operator_user, small_case.procedure)
    assert job.status == "done", job.error
    _log_in(client, operator_user)

    tab = client.get(reverse("expedientes:pliego", args=[small_case.procedure.pk]))
    printed = client.get(reverse("tenders:print", args=[requested.run.version_id]))

    for response in (tab, printed):
        assert response.content.decode().count(NONE_LINE) == 1


# --- La línea con la corrida de la matriz y O-300-1 -----------------------------------------------


def test_the_line_reads_a_matrix_run_and_never_breaks_with_a_list():
    """REQ-122 (O-300-1 de la verificación de T-300): la línea lee la clave de una corrida de
    matriz (`models` en lugar de `models_used`); un proveedor, un modelo o un modo que no es texto
    (una lista) se lee «sin dato» y no rompe la pantalla."""
    matrix_run = m.MatrixRun(
        models={"externo": {"etapas": {"matriz": "externo"}, "proveedor": "anthropic",
                            "modelo": "claude-sonnet-5-5"}},
        parameters={"externo": {"modo": "lotes"}}, counts={"externo": {"matriz": {"pedidos": 3}}})
    assert external_stages.line([matrix_run]) == LINE.format(n=3)

    for field_name in ("proveedor", "modelo"):
        run = am.Run(models_used={"externo": {"etapas": {"verificador": "externo"},
                                              field_name: ["a"]}},
                     parameters={"externo": {"modo": ["lotes"]}}, counts={})
        assert external_stages.line([run]) == (
            "Etapas fuera del equipo: verificador de citas (sin dato, sin dato, modo sin dato, "
            "sin dato).")


# --- Reparto de los tramos y esquemas -------------------------------------------------------------


@pytest.mark.parametrize("count, sizes", [
    (0, []), (40, [40]), (150, [150]), (151, [76, 75]), (300, [150, 150]),
    (450, [150, 150, 150]), (600, [150] * 4), (700, [175] * 4)])
def test_the_segments_are_split_in_up_to_four_requests(count, sizes):
    """REQ-123 (plan 016, «Qué se le pide»): unos 150 tramos por pedido de extracción, de 1 a 4
    pedidos, en el orden del pliego."""
    chunks = external.split(range(count))
    assert [len(chunk) for chunk in chunks] == sizes
    assert [n for chunk in chunks for n in chunk] == list(range(count))


def test_the_schemas_carry_no_length_limits():
    """REQ-123 (plan 016): los esquemas de salida no traen límites de largo (los largos se validan
    en el cliente) y piden la lista cerrada de motivos."""
    text = json.dumps([external.extraction_schema([1, 2]), external.completion_schema()])
    for limit in ("minLength", "maxLength", "maxItems", "minItems"):
        assert limit not in text
    descarte = external.extraction_schema([1])["properties"]["tramos"]["items"]["properties"][
        "descarte"]
    assert set(descarte["enum"]) == {"", *m.DiscardReason.values}


def test_the_instruction_includes_the_block_of_the_local_matrix(settings):
    """REQ-119, REQ-123: la instrucción externa incluye el bloque de definiciones que usa la matriz
    local (la fuente de las decisiones es una) y registra versión y huellas."""
    instruction = external.load_instruction()
    assert instruction.version == settings.EXTERNAL_PROMPT_VERSIONS["matriz"]
    assert extraction.DEFINITIONS_MARK not in instruction.text
    assert instruction.definitions[0] == settings.MATRIX_PROMPT_VERSIONS["definiciones"]
    assert instruction.definitions[1] == extraction.load_instruction("extraccion").definitions[1]


# --- medir_matriz --externo matriz ------------------------------------------------------------------


def test_the_measurement_runs_a_local_and_an_external_proposal_on_the_same_reading(
        operator_user, script, ext, fake_external, tmp_path, monkeypatch, capsys):  # noqa: F811
    """REQ-123: `medir_matriz --externo matriz` corre dos propuestas sobre la misma lectura (cada
    una con su registro, medidas con la misma lista) y pone el gasto real de la externa en el
    resumen y en la salida del comando."""
    procedure, document, path, _ = make_case(operator_user, script, tmp_path)
    fake_external.enable("matriz")
    monkeypatch.setattr("evaluon.accounts.permissions.authenticate_command",
                        lambda username: operator_user)

    call_command("medir_matriz", usuario="operador", procedimiento=procedure.number,
                 esperada=str(path), externo="matriz")

    out = capsys.readouterr().out
    runs = list(m.MatrixRun.objects.filter(procedure=procedure).order_by("pk"))
    assert len(runs) == 2
    local, remote = runs
    assert local.documents == remote.documents
    assert "externo" not in local.models
    assert remote.models["externo"]["etapas"]["matriz"] == "externo"
    assert {run.version.status for run in runs} == {"discarded"}
    folder = next((path.parent.parent / "corridas").iterdir())
    parameters = json.loads((folder / "parametros.json").read_text(encoding="utf-8"))
    labels = [entry["process"] for entry in parameters["propuestas"]]
    assert labels == ["completo · local", "completo · externo"]
    spending = parameters["propuestas"][1]["gasto_externo"]
    assert spending["pedidos"] == 2 and spending["etapa"] == "externo"
    assert spending["gasto_usd"] == pytest.approx(sum(
        e.detail["costo_usd"] for e in requests_of(remote)))
    assert "gasto_externo" not in parameters["propuestas"][0]
    assert [entry["etiqueta"] for entry in parameters["propuestas"]] == labels
    summary = (folder / "resumen-publico.md").read_text(encoding="utf-8")
    assert summary.count("Gasto externo real") == 1
    assert "completo · externo: Gasto externo real" in out
    # Los resúmenes se rehacen sin el modelo con los mismos nombres y el mismo gasto.
    (folder / "resumen-publico.md").unlink()
    again = ev.regenerate_summaries(procedure, ev.load_expected(path), folder)
    assert [r["process"] for r in again.results] == labels
    assert (folder / "resumen-publico.md").read_text(encoding="utf-8") == summary


def test_the_external_measurement_needs_the_external_use_on(operator_user, script, tmp_path):  # noqa: F811
    """REQ-123: sin el uso externo encendido y la matriz en `externo`, la medición externa no
    corre (no hay dos propuestas a medias)."""
    procedure, _, path, _ = make_case(operator_user, script, tmp_path)
    expected = ev.load_expected(path)

    with pytest.raises(ev.MeasurementRefused):
        ev.measure(operator_user, procedure, expected, tmp_path / "corridas", external=True)
    assert not m.MatrixRun.objects.exists()


# --- Controles de H-291-1 (verificación de T-291): origen exacto, tablas, interruptor, alias
# repetido y versión abierta sobre otra. Pliego de tres renglones (`three_items_pdf`). --------------


class Rules(ExternalScript):
    """Como el guion local de `make_case`: la garantía formal, la multa económica, la entrega
    técnica para todos los renglones y el resto descartado."""

    def _segment(self, alias, text):
        if GARANTIA in text:
            return {"tramo": alias, "requisitos": [
                {"cita": "garantía del 5 % del monto", "clase": "formal", "opcion": ""}],
                "tecnico": [], "descarte": ""}
        if MULTA in text:
            return {"tramo": alias, "requisitos": [
                {"cita": "En caso de atraso se aplicará una multa del 1 % diario",
                 "clase": "economico", "opcion": ""}], "tecnico": [], "descarte": ""}
        if ENTREGA in text:
            return {"tramo": alias, "requisitos": [], "tecnico": [extraction.ALL_ITEMS],
                    "descarte": ""}
        return {"tramo": alias, "requisitos": [], "tecnico": [],
                "descarte": "dato_procedimiento"}


@pytest.fixture
def rules(fake_external, monkeypatch):
    return Rules(fake_external, monkeypatch)


def _three_items(user, script, pdf=None):  # noqa: F811
    script.when(GARANTIA, item(requirements=[("garantía del 5 % del monto", "formal")]))
    script.when(MULTA, item(requirements=[
        ("En caso de atraso se aplicará una multa del 1 % diario", "economico")]))
    script.when(ENTREGA, item(technical=[extraction.ALL_ITEMS]))
    procedure = make_procedure(user)
    document = load_and_read(user, procedure, pdf or three_items_pdf(), title="Pliego sintético")
    return procedure, document


def _external_run(user, procedure, fake_external):
    fake_external.enable("matriz")
    requested, job = propose(user, procedure)
    assert job.status == "done", job.error
    return requested.run


def test_every_piece_of_the_tender_enters_with_its_document(
        operator_user, script, rules, fake_external):  # noqa: F811
    """REQ-121, REQ-123 (O-290-3; A2 de H-291-1): cada tramo del prefijo y la cita de cada fila del
    pedido de completitud entran como texto del pliego, nunca como instrucción: la puerta cuenta
    exactamente una pieza `pliego` por tramo y, en la completitud, una más por fila."""
    procedure, document = _three_items(operator_user, script)
    run = _external_run(operator_user, procedure, fake_external)
    segments = m.Segment.objects.filter(reading__document=document).count()
    rows = len(m.RunStep.objects.get(run=run, pass_name="completitud").parsed["filas"])
    assert rows > 0
    by_stage = {e.detail["etapa"]: e.detail["filtro"]["piezas"] for e in requests_of(run)}
    assert by_stage[external.STAGE_EXTRACTION]["pliego"] == segments
    assert by_stage[external.STAGE_COMPLETION]["pliego"] == segments + rows


def test_a_table_the_external_model_discards_stays_pending(
        operator_user, script, rules, fake_external):  # noqa: F811
    """REQ-123, P3 (B1 de H-291-1): una tabla que el modelo externo descarta no queda descartada en
    silencio: `keep_tables_pending` la deja pendiente de revisión con el motivo `tabla`."""
    procedure, document = _three_items(operator_user, script, synthetic_tender_pdf())
    tables = list(m.Segment.objects.filter(reading__document=document, segment_type="tabla"))
    assert tables
    run = _external_run(operator_user, procedure, fake_external)
    assert run.models["externo"]["etapas"]["matriz"] == "externo"
    for segment in tables:
        assert m.Disposition.objects.get(run=run, segment=segment).outcome == "pendiente"
        assert m.PendingItem.objects.filter(version=run.version, segment=segment,
                                            reason="tabla").exists()


def test_the_stage_alone_does_not_turn_the_external_use_on(
        operator_user, script, rules, fake_external, settings):  # noqa: F811
    """REQ-122 (B8 de H-291-1): con la matriz en `externo` pero el uso externo apagado
    (`EXTERNAL_ENABLED`), la propuesta es local: no arma ningún pedido ni guarda la clave."""
    settings.EXTERNAL_ENABLED = False
    settings.EXTERNAL_STAGES = {**settings.EXTERNAL_STAGES, "matriz": "externo"}
    procedure, _ = _three_items(operator_user, script)
    requested, job = propose(operator_user, procedure)
    assert job.status == "done", job.error
    run = requested.run
    assert not external.enabled()
    assert "externo" not in run.models and "externo" not in run.prompt_versions
    assert script.calls and requests_of() == [] and rules.payloads == []


def test_a_repeated_alias_in_the_answer_is_not_used(
        operator_user, script, rules, fake_external):  # noqa: F811
    """REQ-123 (B9 de H-291-1): si la respuesta trae dos veces el mismo tramo no vale ninguna de las
    dos: queda `externo_respuesta_repetida` y el tramo, pendiente sin disposición."""
    procedure, _ = _three_items(operator_user, script)
    plain = rules.reply

    def repeated(payload):
        base = plain(payload)
        data = json.loads(base["text"])
        if payload.stage == external.STAGE_EXTRACTION:
            first = data["tramos"][0]
            data["tramos"] = [first, {**first, "requisitos": [], "tecnico": [],
                                      "descarte": "titulo"}, *data["tramos"][1:]]
        return {**base, "text": json.dumps(data, ensure_ascii=False)}

    rules.fake._reply = repeated
    run = _external_run(operator_user, procedure, fake_external)
    assert "externo_respuesta_repetida" in anomaly_types(run)
    repeated_segment = next(a["segment"] for a in run.anomalies
                            if a["type"] == "externo_respuesta_repetida")
    assert m.PendingItem.objects.get(version=run.version,
                                     segment_id=repeated_segment).reason == "sin_disposicion"


def test_the_line_of_a_version_opened_on_another_follows_its_origin(
        operator_user, script, rules, fake_external):  # noqa: F811
    """REQ-122 (E5 de H-291-1): una versión abierta sobre otra no tiene propuesta propia: su línea
    «Etapas fuera del equipo» es la de la propuesta de origen."""
    from django.utils import timezone

    from evaluon.tenders.services import matrix_page

    procedure, _ = _three_items(operator_user, script)
    run = _external_run(operator_user, procedure, fake_external)
    first = run.version
    m.MatrixVersion.objects.filter(pk=first.pk).update(
        status="validated", validated_at=timezone.now(), validated_by=operator_user)
    second = m.MatrixVersion.objects.create(procedure=procedure, number=2, process="completo",
                                            based_on=first, status="draft",
                                            created_by=operator_user)
    assert matrix_page.external_line(second) == LINE.format(n=2)
