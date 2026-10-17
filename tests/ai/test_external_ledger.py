"""Libro de los pedidos externos: registro, tope de gasto, freno de la etapa, reuso por huella y
el comando `gasto_externo` (T-290; REQ-121 y REQ-122; ADR-0068; plan 016, "Modelo de datos" y
"Costo y tope"; umbral 21).

Sin red: el doble del cliente (`fake_external`) responde y la suite bloquea toda llamada real.
Los importes son `Decimal` exactos. Todo el texto es público e inventado (P4).
"""

import ast
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from evaluon.accounts import permissions
from evaluon.ai.external import guard, ledger
from evaluon.audit import services as audit
from evaluon.audit.models import AuditEvent, Channel, EventType, Outcome
from tests.ai.test_external_guard import (  # noqa: F401 - fixtures y ayudas de la puerta
    ECONOMIC,
    KEYWORD,
    MEASUREMENT,
    TECHNICAL,
    ask,
    assert_nothing_of_the_sheet,
    case,
    debt_in_catalog,
    evaluator_user,
    expected,
    external_requests,
    matrix,
    operator_user,
    procedure,
)
from tests.conftest import TEST_PASSWORD
from tests.tenders.conftest import no_commission_user  # noqa: F401 - fixture de la 003

pytestmark = pytest.mark.django_db

COMMAND = Path(__file__).resolve().parents[2] / "evaluon" / "assessment" / "management" / \
    "commands" / "gasto_externo.py"

# Campos del hecho `external_request` (plan 016, "Modelo de datos").
PLAN_FIELDS = {
    "proveedor", "modelo", "modelo_respuesta", "etapa", "instruccion", "definiciones", "modo",
    "lote_id", "custom_id", "parametros", "procedimiento", "oferta", "requisito", "corrida",
    "texto_enviado", "huella_pedido", "respuesta", "uso", "costo_usd", "tabla_de_precios",
    "duracion_s", "resultado", "error", "filtro"}


def economic(case, custom_id="pedido-1", **kwargs):
    return ask(case, [guard.offer_document(case.documents["economica.pdf"], ECONOMIC)],
               custom_id=custom_id, **kwargs)


def technical(case, custom_id="pedido-2", **kwargs):
    return ask(case, [guard.offer_document(case.documents["tecnica.pdf"], TECHNICAL)],
               custom_id=custom_id, **kwargs)


def past_spend(amount, *, procedure_id, stage="verificador", measurement=None, when=None,
               run=("assessment", 1)):
    """Un pedido ya pagado en el registro (como lo deja el libro), con su costo."""
    detail = {"proveedor": "anthropic", "modelo": "claude-sonnet-5-5", "etapa": stage,
              "etapa_grupo": stage.split("_", 1)[0], "procedimiento": procedure_id,
              "medicion": measurement, "corrida": {"tipo": run[0], "numero": run[1]},
              "resultado": "ok", "costo_usd": float(amount)}
    if when is None:
        return audit.record(EventType.EXTERNAL_REQUEST, outcome=Outcome.OK,
                            channel=Channel.COMMAND, detail=detail)
    return AuditEvent.objects.create(event_type=EventType.EXTERNAL_REQUEST, outcome=Outcome.OK,
                                     channel=Channel.COMMAND, occurred_at=when, detail=detail)


def cost(event):
    return Decimal(str(event.detail["costo_usd"]))


# --- Registro ---------------------------------------------------------------------------------


def test_each_request_is_recorded_with_the_fields_of_the_plan(case, fake_external):
    """REQ-122 (ADR-0068, punto 1): cada pedido que sale deja un hecho `external_request` con los
    campos del plan: proveedor, modelos, etapa, instrucción, modo, lote, parámetros, ids, texto
    enviado, huella, respuesta completa, uso, costo, tabla de precios, duración, resultado y
    filtro."""
    fake_external.enable()
    fake_external.respond('{"sostiene": "si"}', model="claude-sonnet-5-5-20261001")
    admitted = [economic(case), technical(case)]
    sent = ledger.send(admitted, measurement=MEASUREMENT)
    events = external_requests()
    assert len(events) == 2
    for event, item in zip(events, admitted, strict=True):
        payload = item.payload
        detail = event.detail
        assert PLAN_FIELDS <= set(detail)
        assert event.event_type == EventType.EXTERNAL_REQUEST and event.outcome == Outcome.OK
        assert detail["proveedor"] == "anthropic"
        assert detail["modelo"] == "claude-sonnet-5-5"
        assert detail["modelo_respuesta"] == "claude-sonnet-5-5-20261001"
        assert detail["etapa"] == "verificador" and detail["modo"] == "lotes"
        assert detail["instruccion"] == {"nombre": "verificador", "version": "verificador-v1",
                                         "sha256": "0" * 64}
        assert detail["lote_id"] == "msgbatch_fake_1" == sent.batch_id
        assert detail["custom_id"] == payload.custom_id
        assert detail["parametros"] == {"effort": "low", "thinking": "between_tools",
                                        "max_tokens": 600, "formato_salida": None,
                                        "cache_system_ttl": "1h"}
        assert detail["procedimiento"] == case.procedure.pk
        assert detail["oferta"] == case.offer.pk
        assert detail["corrida"] == {"tipo": "assessment", "numero": 1}
        assert detail["medicion"] == MEASUREMENT
        assert detail["texto_enviado"] == {
            "sistema": payload.system,
            "mensajes": [{"rol": r, "texto": t} for r, t in payload.messages]}
        assert detail["huella_pedido"] == payload.request_sha256
        assert detail["respuesta"]["content"][0]["text"] == '{"sostiene": "si"}'
        assert set(detail["uso"]) == {"entrada", "salida", "escritura_cache", "lectura_cache"}
        assert cost(event) > 0
        assert detail["tabla_de_precios"] == {
            "version": "2026-10-15", "fecha": "2026-10-15",
            "fuente": "https://platform.claude.com/docs/en/about-claude/pricing"}
        assert detail["duracion_s"] is not None
        assert detail["resultado"] == "ok" and detail["error"] is None
        assert detail["filtro"] == item.filter
    assert sent.answers["pedido-1"].text == '{"sostiene": "si"}'
    assert sent.answers["pedido-1"].event_id == events[0].pk
    assert sent.summary()["pedidos"] == 2 and sent.summary()["modo"] == "lotes"


def test_the_append_only_trigger_protects_the_recorded_requests(case, fake_external):
    """REQ-122 (P6): un pedido registrado por el libro no se puede editar ni borrar, ni desde la
    aplicación ni directo en la base."""
    fake_external.enable()
    ledger.send([economic(case)], measurement=MEASUREMENT)
    (event,) = external_requests()
    for sql in ("UPDATE audit_event SET detail = '{}' WHERE id = %s",
                "UPDATE audit_event SET outcome = 'failed' WHERE id = %s",
                "DELETE FROM audit_event WHERE id = %s"):
        with pytest.raises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(sql, [event.pk])
    with pytest.raises(ValueError):
        event.save()
    with pytest.raises(ValueError):
        event.delete()
    assert AuditEvent.objects.get(pk=event.pk).detail["resultado"] == "ok"


def test_a_direct_message_is_recorded_too(case, fake_external):
    """REQ-122: en el modo directo (prueba de humo) también queda un hecho por pedido, sin lote,
    con su duración y el costo a precio entero."""
    fake_external.enable()
    fake_external.respond("ok", usage={"input_tokens": 1000, "output_tokens": 100})
    sent = ledger.send([economic(case)], mode="directo")
    (event,) = external_requests()
    assert event.detail["modo"] == "directo" and event.detail["lote_id"] is None
    assert event.detail["duracion_s"] == 0.0
    assert cost(event) == Decimal("0.003")  # (1000 × 2 + 100 × 10) / 1e6
    assert len(fake_external.messages) == 1 and sent.answers["pedido-1"].ok


# --- Costo ------------------------------------------------------------------------------------


def test_the_real_cost_uses_the_usage_reported_and_halves_in_batches(case, fake_external):
    """REQ-122 (ADR-0068, punto 3): el costo sale del uso informado (entrada, salida, escritura y
    lectura de caché) y la tabla versionada, con `Decimal` exacto; en lotes, a la mitad."""
    fake_external.enable()
    fake_external.respond("ok", usage={"input_tokens": 1000, "output_tokens": 200,
                                       "cache_creation_input_tokens": 100,
                                       "cache_read_input_tokens": 400})
    sent = ledger.send([economic(case)], measurement=MEASUREMENT)
    (event,) = external_requests()
    # (1000 × 2 + 100 × 2 × 2 + 400 × 2 × 0,05 + 200 × 10) / 1e6 × 0,5
    assert cost(event) == Decimal("0.00222")
    assert sent.cost_usd == Decimal("0.00222")
    assert event.detail["uso"] == {"entrada": 1000, "salida": 200, "escritura_cache": 100,
                                   "lectura_cache": 400}


def test_the_estimate_is_the_conservative_one_of_the_plan(case):
    """REQ-122 (ADR-0068, punto 4, calibrado con T-293; D-293-5): caracteres entre 1,9 por el precio
    de entrada (el sistema con caché a precio de escritura, el doble), más la salida esperada por el
    de salida; en lotes, a la mitad. Las cifras de T-293 están en `test_external_estimate.py`."""
    payload = economic(case).payload
    tokens_system = Decimal(len(payload.system)) / Decimal("1.9")
    tokens_messages = Decimal(sum(len(text) for _, text in payload.messages)) / Decimal("1.9")
    expected_out = min(payload.max_tokens, ledger.OUTPUT_TOKENS_ESTIMATE)
    direct = ((tokens_system * 2 + tokens_messages) * 2 + expected_out * 10) / Decimal(1_000_000)
    assert ledger.estimate(payload, "directo") == direct.quantize(Decimal("0.00000001"),
                                                                  rounding="ROUND_CEILING")
    assert ledger.estimate(payload, "lotes") == (direct / 2).quantize(
        Decimal("0.00000001"), rounding="ROUND_CEILING")


def test_the_sums_are_exact_decimals_per_case_and_per_month(case):
    """REQ-122: el libro suma `costo_usd` del procedimiento y del mes con `Decimal` exacto; lo
    del mes anterior no cuenta en el mes."""
    pk = case.procedure.pk
    for _ in range(10):
        past_spend("0.1", procedure_id=pk)
    past_spend("0.3", procedure_id=pk + 1000)
    past_spend("5", procedure_id=pk, when=timezone.now() - timedelta(days=40))
    assert ledger.spent_case(pk) == Decimal("6.0")
    assert ledger.spent_month() == Decimal("1.3")


# --- Tope (umbral 21) -------------------------------------------------------------------------


def test_a_batch_that_would_pass_the_case_cap_does_not_go_out(case, fake_external):
    """REQ-122 (umbral 21): si el estimado del lote pasa lo que queda de los 2 USD del caso, el
    lote no sale: cada pedido queda `bloqueado` con motivo `tope`, sin texto, y la etapa recibe
    `externo_bloqueado` para seguir en local."""
    fake_external.enable()
    past_spend("1.999", procedure_id=case.procedure.pk)
    sent = ledger.send([economic(case), technical(case)], measurement=MEASUREMENT)
    assert fake_external.batches == [] and fake_external.messages == []
    assert {a.outcome for a in sent.answers.values()} == {"bloqueado"}
    assert {a.reason for a in sent.answers.values()} == {"tope"}
    assert sent.anomalies[0]["anomalia"] == "externo_bloqueado"
    assert sent.anomalies[0]["tope"] == "caso"
    blocked = [e for e in external_requests() if e.detail["resultado"] == "bloqueado"]
    assert len(blocked) == 2
    for event in blocked:
        assert event.outcome == Outcome.REJECTED and event.detail["motivo"] == "tope"
        assert event.detail["texto_enviado"] is None and event.detail["costo_usd"] == 0
        assert event.detail["tope"]["gasto_caso_usd"] == 1.999


def test_a_batch_that_would_pass_the_month_cap_does_not_go_out(case, fake_external):
    """REQ-122 (umbral 21): el mes suma lo de todos los procedimientos; si el lote pasa lo que
    queda de los 10 USD del mes, no sale, aunque el caso tenga margen."""
    fake_external.enable()
    for other in range(5):
        past_spend("1.9999", procedure_id=case.procedure.pk + 1000 + other)
    sent = ledger.send([economic(case)], measurement=MEASUREMENT)
    assert fake_external.batches == []
    answer = sent.answers["pedido-1"]
    assert (answer.outcome, answer.reason) == ("bloqueado", "tope")
    assert sent.anomalies[0]["tope"] == "mes"


def test_last_month_does_not_count_against_this_month(case, fake_external):
    """REQ-122: lo gastado el mes anterior no frena el mes en curso."""
    fake_external.enable()
    past_spend("50", procedure_id=case.procedure.pk + 1000,
               when=ledger.month_bounds()[0] - timedelta(minutes=1))
    sent = ledger.send([economic(case)], measurement=MEASUREMENT)
    assert sent.answers["pedido-1"].ok and len(fake_external.batches) == 1


def test_a_batch_within_the_caps_goes_out(case, fake_external):
    """REQ-122: con margen en el caso y en el mes, el lote sale."""
    fake_external.enable()
    past_spend("1.5", procedure_id=case.procedure.pk)
    past_spend("8", procedure_id=case.procedure.pk + 1000)
    sent = ledger.send([economic(case)], measurement=MEASUREMENT)
    assert sent.answers["pedido-1"].ok and len(fake_external.batches) == 1


@pytest.mark.parametrize("name", ["EXTERNAL_CASE_CAP_USD", "EXTERNAL_MONTH_CAP_USD",
                                  "EXTERNAL_STAGE_STOP_FACTOR"])
@pytest.mark.parametrize("value", ["0", "-5", "NaN", "Infinity", "-Infinity", "sNaN"])
def test_a_cap_that_is_not_a_positive_number_is_a_configuration_error(
        case, fake_external, settings, name, value):
    """REQ-122 (O-288-2): un tope o un factor no positivo, `NaN` o infinito no se usa como tope:
    es un error de configuración, nada sale y nada se registra como enviado."""
    fake_external.enable()
    admitted = economic(case)
    setattr(settings, name, Decimal(value))
    with pytest.raises(ImproperlyConfigured, match=name):
        ledger.send([admitted], measurement=MEASUREMENT)
    assert fake_external.batches == [] and external_requests() == []


def test_a_stage_estimate_that_is_not_positive_is_a_configuration_error(
        case, fake_external, settings):
    """REQ-122 (O-288-2): un estimado de etapa en cero tampoco se usa."""
    fake_external.enable()
    admitted = economic(case)
    settings.EXTERNAL_STAGE_ESTIMATE_USD = {**settings.EXTERNAL_STAGE_ESTIMATE_USD,
                                            "verificador": Decimal("0")}
    with pytest.raises(ImproperlyConfigured, match="verificador"):
        ledger.send([admitted], measurement=MEASUREMENT)
    assert fake_external.batches == []


def test_a_model_without_a_price_does_not_go_out(case, fake_external):
    """REQ-122: un modelo que no está en la tabla de precios no sale (no se puede estimar)."""
    fake_external.enable()
    unpriced = guard.build(
        stage="verificador", custom_id="pedido-x", procedure=case.procedure, offer=case.offer,
        system=guard.instruction("Instrucción."), max_tokens=10, model="modelo-sin-precio",
        messages=[("user", [guard.offer_document(case.documents["economica.pdf"], ECONOMIC)])])
    assert isinstance(unpriced, guard.Admitted)
    sent = ledger.send([unpriced])
    assert sent.answers["pedido-x"].reason == "sin_precio"
    assert fake_external.batches == []


# --- Freno de la etapa ------------------------------------------------------------------------


def test_a_stage_that_reached_twice_its_estimate_stops(case, fake_external, settings):
    """REQ-122 (umbral 21; ADR-0068, punto 4): si la etapa ya gastó el doble de su estimado en la
    medición, el lote no sale (`bloqueado`, motivo `etapa`) y se informa (`stage_stopped`); en
    otra medición sigue."""
    fake_external.enable()
    assert settings.EXTERNAL_STAGE_ESTIMATE_USD["verificador"] == Decimal("0.30")
    past_spend("0.60", procedure_id=case.procedure.pk, measurement=MEASUREMENT)
    sent = ledger.send([economic(case)], measurement=MEASUREMENT)
    assert sent.stage_stopped
    assert (sent.answers["pedido-1"].outcome, sent.answers["pedido-1"].reason) == (
        "bloqueado", "etapa")
    assert fake_external.batches == []
    other = ledger.send([economic(case)], measurement="otra-medicion")
    assert other.answers["pedido-1"].ok and not other.stage_stopped


def test_a_stage_that_passes_twice_its_estimate_with_a_batch_is_reported(
        case, fake_external, settings):
    """REQ-122 (umbral 21): el lote que hace pasar a la etapa el doble de su estimado la deja
    frenada e informada; el siguiente lote de la etapa ya no sale."""
    fake_external.enable()
    settings.EXTERNAL_STAGE_ESTIMATE_USD = {**settings.EXTERNAL_STAGE_ESTIMATE_USD,
                                            "verificador": Decimal("0.0001")}
    fake_external.respond("ok", usage={"input_tokens": 1000, "output_tokens": 1000})
    first = ledger.send([economic(case)], measurement=MEASUREMENT)
    assert first.answers["pedido-1"].ok
    assert first.stage_stopped and first.spent_stage_usd == Decimal("0.006")
    assert first.anomalies[-1]["anomalia"] == "externo_etapa_frenada"
    second = ledger.send([technical(case)], measurement=MEASUREMENT)
    assert second.answers["pedido-2"].reason == "etapa"
    assert len(fake_external.batches) == 1


def test_without_a_measurement_the_stage_counts_by_run(case, fake_external):
    """REQ-122: sin medición, el freno de la etapa cuenta lo de la misma corrida."""
    fake_external.enable()
    past_spend("0.60", procedure_id=case.procedure.pk, run=("assessment", 1))
    sent = ledger.send([economic(case, measurement=None)])
    assert sent.answers["pedido-1"].reason == "etapa"
    past = ledger.spent_stage("verificador", case.procedure.pk, run_kind="assessment",
                              run_id=2)
    assert past == 0


# --- Reuso por huella -------------------------------------------------------------------------


def test_the_same_request_in_the_same_measurement_is_reused_and_does_not_pay(case,
                                                                              fake_external):
    """REQ-122 (ADR-0068, punto 5): el mismo pedido (huella, modelo, parámetros y versión de la
    instrucción) ya respondido en la medición no sale: queda `reutilizado`, con costo 0 y la
    respuesta guardada."""
    fake_external.enable()
    fake_external.respond('{"sostiene": "no"}')
    first = ledger.send([economic(case)], measurement=MEASUREMENT)
    again = ledger.send([economic(case, custom_id="pedido-9")], measurement=MEASUREMENT)
    assert len(fake_external.batches) == 1
    answer = again.answers["pedido-9"]
    assert answer.outcome == "reutilizado" and answer.ok
    assert answer.text == '{"sostiene": "no"}'
    assert again.cost_usd == 0
    original, reused = external_requests()
    assert reused.detail["resultado"] == "reutilizado" and cost(reused) == 0
    assert reused.detail["reutiliza"] == original.pk == first.answers["pedido-1"].event_id
    assert reused.detail["huella_pedido"] == original.detail["huella_pedido"]
    assert ledger.spent_case(case.procedure.pk) == cost(original)


def test_reuse_needs_the_same_measurement_and_instruction_version(case, fake_external):
    """REQ-122: en otra medición, sin medición o con otra versión de la instrucción, el pedido
    sale de nuevo (y paga)."""
    fake_external.enable()
    ledger.send([economic(case)], measurement=MEASUREMENT)
    ledger.send([economic(case)], measurement="otra-medicion")
    ledger.send([economic(case, measurement=None)])
    ledger.send([economic(case, instruction_version="verificador-v2")],
                measurement=MEASUREMENT)
    assert len(fake_external.batches) == 4
    assert {e.detail["resultado"] for e in external_requests()} == {"ok"}


# --- Fallas del proveedor ---------------------------------------------------------------------


def test_failed_expired_and_unavailable_requests_are_recorded(case, fake_external):
    """REQ-122: un pedido con error o vencido en el lote, o un lote que no responde, quedan en el
    registro (`error` o `vencido`) con el motivo, y la etapa recibe `externo_no_disponible`."""
    fake_external.enable()
    fake_external.fail("pedido-1")
    fake_external.expire("pedido-2")
    sent = ledger.send([economic(case), technical(case)], measurement=MEASUREMENT)
    assert sent.answers["pedido-1"].outcome == "error"
    assert sent.answers["pedido-2"].outcome == "vencido"
    errored, expired = external_requests()
    assert errored.outcome == Outcome.FAILED and errored.detail["error"]["motivo"]
    assert expired.detail["resultado"] == "vencido"
    assert {a["anomalia"] for a in sent.anomalies} == {"externo_no_disponible"}

    fake_external.timeout()
    later = ledger.send([economic(case, custom_id="pedido-3")], measurement=MEASUREMENT)
    assert later.answers["pedido-3"].outcome == "error"
    assert later.answers["pedido-3"].reason == "timeout"
    event = external_requests()[-1]
    assert event.detail["error"]["motivo"] == "timeout"
    assert event.detail["texto_enviado"] is not None


def test_with_the_external_use_off_nothing_goes_out_and_it_is_recorded(case, fake_external):
    """REQ-122: con el uso externo apagado, el cliente no se conecta y el pedido queda como
    `error` (`external_disabled`); la etapa sigue en local."""
    sent = ledger.send([economic(case)], measurement=MEASUREMENT)
    assert sent.answers["pedido-1"].reason == "external_disabled"
    assert fake_external.batches == []
    (event,) = external_requests()
    assert event.detail["resultado"] == "error"


# --- Comando gasto_externo --------------------------------------------------------------------


@pytest.fixture
def logged_in(monkeypatch, operator_user):
    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    return operator_user


def run_command(user, *args):
    out = StringIO()
    call_command("gasto_externo", "--usuario", user.username, *args, stdout=out)
    return out.getvalue()


def test_the_command_prints_the_real_spend_by_month_case_and_stage(case, fake_external,
                                                                   logged_in):
    """REQ-122 (ADR-0068, punto 6): `gasto_externo` imprime el gasto real y la cantidad de pedidos
    por resultado, por mes, por procedimiento y por etapa."""
    fake_external.enable()
    fake_external.respond("ok", usage={"input_tokens": 1000, "output_tokens": 100})
    ledger.send([economic(case), technical(case)], measurement=MEASUREMENT)
    past_spend("0.25", procedure_id=case.procedure.pk, stage="matriz_extraccion")
    past_spend("1", procedure_id=case.procedure.pk + 1000)
    past_spend("3", procedure_id=case.procedure.pk, when=timezone.now() - timedelta(days=40))
    month = timezone.localtime().strftime("%Y-%m")

    out = run_command(logged_in, "--mes", month)
    assert "Pedidos registrados: 4 (ok 4" in out
    assert "Gasto real: 1.253000 USD" in out  # 2 × 0,0015 + 0,25 + 1

    out = run_command(logged_in, "--procedimiento", case.procedure.number, "--por-etapa")
    assert "Pedidos registrados: 4" in out and "Gasto real: 3.253000 USD" in out
    assert "verificador: 3 pedidos (ok 3), 3.003000 USD" in out
    assert "matriz_extraccion: 1 pedidos (ok 1), 0.250000 USD" in out


def test_verifying_the_filter_counts_zero_on_a_clean_registry(case, fake_external, logged_in):
    """REQ-121 (umbral 19): con la hoja cargada y los pedidos armados por la puerta,
    `--verificar-filtro` cuenta 0 pedidos con texto de una hoja."""
    fake_external.enable()
    ledger.send([economic(case), technical(case)], measurement=MEASUREMENT)
    ask(case, [guard.offer_document(case.documents["hoja-compliance.pdf"], case.sheet[0])],
        custom_id="pedido-3")
    out = run_command(logged_in, "--verificar-filtro")
    assert "Pedidos con texto de una hoja de compliance: 0 (criterio de REQ-121: 0)" in out
    assert "3 pedidos revisados contra 1 hojas de compliance" in out


@pytest.mark.parametrize("leak", ["paragraph", "eight_words"])
def test_verifying_the_filter_detects_a_request_with_text_of_a_sheet(case, logged_in, leak):
    """REQ-121 (ADR-0067, punto 5): un pedido armado a mano en el registro que contiene un
    párrafo de la hoja (u ocho palabras seguidas de ella, sin la palabra clave) se detecta, y el
    comando termina con error."""
    words = case.sheet[1].split()
    text = case.sheet[1] if leak == "paragraph" else " ".join(words[3:11])
    assert leak == "paragraph" or KEYWORD not in text
    leaked = audit.record(EventType.EXTERNAL_REQUEST, outcome=Outcome.OK, channel=Channel.COMMAND,
                          detail={"procedimiento": case.procedure.pk, "etapa": "verificador",
                                  "resultado": "ok", "costo_usd": 0.001,
                                  "texto_enviado": {"sistema": "Instrucción.", "mensajes": [
                                      {"rol": "user", "texto": f"Oferta. {text} Fin."}]}})
    audit.record(EventType.EXTERNAL_REQUEST, outcome=Outcome.OK, channel=Channel.COMMAND,
                 detail={"procedimiento": case.procedure.pk, "etapa": "verificador",
                         "resultado": "ok", "costo_usd": 0.001,
                         "texto_enviado": {"sistema": "Instrucción.", "mensajes": [
                             {"rol": "user", "texto": ECONOMIC}]}})
    out = StringIO()
    with pytest.raises(CommandError, match="REQ-121"):
        call_command("gasto_externo", "--usuario", logged_in.username, "--verificar-filtro",
                     stdout=out)
    assert "Pedidos con texto de una hoja de compliance: 1" in out.getvalue()
    assert f"hecho {leaked.pk}:" in out.getvalue()


def test_the_filter_scan_is_independent_of_the_guard():
    """REQ-121 (ADR-0067, punto 5): el escaneo del comando tiene su propia implementación: no
    importa la puerta ni el paquete externo."""
    tree = ast.parse(COMMAND.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported |= {f"{node.module}.{alias.name}" for alias in node.names}
    assert not [name for name in imported if "ai.external" in name or "guard" in name]


def test_the_command_needs_a_commission_user(case, monkeypatch, no_commission_user):
    """REQ-122: el comando pide usuario y clave, y un rol de la Comisión."""
    monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
    with pytest.raises(CommandError):
        run_command(no_commission_user)


def test_no_text_of_the_sheet_reaches_the_registry_through_the_ledger(case, fake_external):
    """REQ-121: lo que el libro registra de un lote con la hoja cargada no tiene nada de ella."""
    fake_external.enable()
    ledger.send([economic(case), technical(case)], measurement=MEASUREMENT)
    for event in external_requests():
        assert_nothing_of_the_sheet(event.detail, case.sheet)


def test_verifying_the_filter_sees_a_paragraph_split_across_messages(case, logged_in):
    """REQ-121 (H-290-1): el escaneo del comando arma el pedido entero (sistema y mensajes en
    orden) y ve un párrafo de la hoja repartido en trozos de 7 palabras."""
    words = case.sheet[3].split()
    audit.record(EventType.EXTERNAL_REQUEST, outcome=Outcome.OK, channel=Channel.COMMAND,
                 detail={"procedimiento": case.procedure.pk, "etapa": "verificador",
                         "resultado": "ok", "costo_usd": 0.001, "texto_enviado": {
                             "sistema": " ".join(words[:7]), "mensajes": [
                                 {"rol": "user", "texto": " ".join(words[7:14])},
                                 {"rol": "assistant", "texto": " ".join(words[14:21])}]}})
    out = StringIO()
    with pytest.raises(CommandError, match="REQ-121"):
        call_command("gasto_externo", "--usuario", logged_in.username, "--verificar-filtro",
                     stdout=out)
    assert "Pedidos con texto de una hoja de compliance: 1" in out.getvalue()


@pytest.mark.parametrize("mark", ["\u200b", "\u00ad"])
def test_verifying_the_filter_ignores_invisible_characters(case, logged_in, mark):
    """REQ-121 (H-290-2): el escaneo del comando también descarta los caracteres invisibles y
    normaliza con NFKC (letras de ancho completo) antes de cortar las palabras."""
    words = case.sheet[3].split()
    hidden = " ".join(mark.join([w[:len(w) // 2], w[len(w) // 2:]]) for w in words[:10])
    wide = "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c
                   for c in " ".join(words[10:20]))
    for text in (hidden, wide):
        audit.record(EventType.EXTERNAL_REQUEST, outcome=Outcome.OK, channel=Channel.COMMAND,
                     detail={"procedimiento": case.procedure.pk, "etapa": "verificador",
                             "resultado": "ok", "costo_usd": 0.001, "texto_enviado": {
                                 "sistema": "Instrucción.",
                                 "mensajes": [{"rol": "user", "texto": f"Oferta. {text} Fin."}]}})
    out = StringIO()
    with pytest.raises(CommandError, match="REQ-121"):
        call_command("gasto_externo", "--usuario", logged_in.username, "--verificar-filtro",
                     stdout=out)
    assert "Pedidos con texto de una hoja de compliance: 2" in out.getvalue()


def test_verifying_the_filter_sees_text_of_a_suggested_document(case, logged_in, operator_user):
    """REQ-121 (H-290-3): el escaneo del comando compara también con los documentos que tienen la
    sugerencia `compliance` en su lectura."""
    from tests.ai.test_external_guard import CONSULTATION, suggested_document

    suggested_document(case.offer, operator_user)
    audit.record(EventType.EXTERNAL_REQUEST, outcome=Outcome.OK, channel=Channel.COMMAND,
                 detail={"procedimiento": case.procedure.pk, "etapa": "verificador",
                         "resultado": "ok", "costo_usd": 0.001, "texto_enviado": {
                             "sistema": "Instrucción.",
                             "mensajes": [{"rol": "user", "texto": CONSULTATION}]}})
    out = StringIO()
    with pytest.raises(CommandError, match="REQ-121"):
        call_command("gasto_externo", "--usuario", logged_in.username, "--verificar-filtro",
                     stdout=out)
    assert "contra 2 hojas de compliance" in out.getvalue()


# --- Pruebas que faltaban (H-290-4) ------------------------------------------------------------


def test_the_cost_is_rounded_up(settings):
    """REQ-122 (H-290-4, alteración M12): el costo se guarda con 8 decimales redondeando siempre
    hacia arriba (nunca se subestima lo gastado)."""
    from evaluon.ai.external.client import ExternalUsage

    settings.EXTERNAL_PRICES = {**settings.EXTERNAL_PRICES, "modelos": {
        "claude-sonnet-5-5": {"entrada": Decimal("0.003"), "salida": Decimal("0.003")}}}
    usage = ExternalUsage(input_tokens=1)
    assert ledger.cost_of("claude-sonnet-5-5", usage, "directo") == Decimal("0.00000001")


def test_the_stage_brake_counts_only_its_procedure(case, fake_external):
    """REQ-122 (H-290-4, alteración M24): lo que gastó la etapa en otro procedimiento, en la misma
    medición, no frena la etapa de este."""
    fake_external.enable()
    past_spend("0.60", procedure_id=case.procedure.pk + 1000, measurement=MEASUREMENT)
    sent = ledger.send([economic(case)], measurement=MEASUREMENT)
    assert sent.answers["pedido-1"].ok and not sent.stage_stopped


def test_the_cap_adds_the_estimate_of_every_request_of_the_batch(case, fake_external):
    """REQ-122 (H-290-4, alteración M25): el tope suma el estimado de todos los pedidos del lote:
    si el primero solo entra pero los dos juntos no, el lote no sale."""
    fake_external.enable()
    first, second = economic(case), technical(case)
    one, two = ledger.estimate_batch([first.payload, second.payload], "lotes")
    past = Decimal("2") - one - (two / 2).quantize(Decimal("0.00000001"))
    past_spend(past, procedure_id=case.procedure.pk)
    sent = ledger.send([first, second], measurement=MEASUREMENT)
    assert {a.reason for a in sent.answers.values()} == {"tope"}
    assert fake_external.batches == []
    alone = ledger.send([economic(case, custom_id="solo")], measurement=MEASUREMENT)
    assert alone.answers["solo"].ok


@pytest.mark.parametrize("factor", ["cache_lectura", "cache_escritura_1h", "lotes"])
@pytest.mark.parametrize("value", ["0", "-1", "NaN", "Infinity"])
def test_an_invalid_price_factor_stops_before_sending(case, fake_external, settings, factor,
                                                     value):
    """REQ-122 (H-290-5; O-288-2): un factor de caché o de lotes de `EXTERNAL_PRICES` que no es un
    número finito y positivo se rechaza antes de mandar: nada sale y nada queda sin registro."""
    fake_external.enable()
    admitted = economic(case)
    settings.EXTERNAL_PRICES = {**settings.EXTERNAL_PRICES, factor: Decimal(value)}
    with pytest.raises(ImproperlyConfigured, match=factor):
        ledger.send([admitted], measurement=MEASUREMENT)
    assert fake_external.batches == [] and fake_external.messages == []
    assert external_requests() == []


# --- Lote en vuelo (O-290-6) -------------------------------------------------------------------


class WorkerDied(BaseException):
    """El proceso que esperaba el lote se cae (como un reinicio del `worker`)."""


def worker_dies(batch, started):
    raise WorkerDied


def in_flight_events():
    return list(AuditEvent.objects.filter(event_type=EventType.EXTERNAL_REQUEST,
                                          detail__resultado="en_vuelo").order_by("pk"))


def test_a_batch_leaves_an_in_flight_fact_as_soon_as_it_exists(case, fake_external,
                                                               monkeypatch):
    """REQ-122 (O-290-6): apenas el proveedor crea el lote queda un hecho `en_vuelo` con su
    identificador, los pedidos y el estimado, sin texto; si el proceso muere esperando, el tope lo
    cuenta con su estimado."""
    fake_external.enable()
    first, second = economic(case), technical(case)
    estimate = sum(ledger.estimate_batch([first.payload, second.payload], "lotes"), Decimal(0))

    from evaluon.ai.external import client
    monkeypatch.setattr(client, "_wait_for", worker_dies)
    with pytest.raises(WorkerDied):
        ledger.send([first, second], measurement=MEASUREMENT)
    (flight,) = in_flight_events()
    assert flight.detail["lote_id"] == "msgbatch_fake_1"
    assert flight.detail["custom_ids"] == ["pedido-1", "pedido-2"]
    assert cost(flight) == estimate
    assert flight.detail["texto_enviado"] is None
    assert ledger.spent_case(case.procedure.pk) == estimate
    assert ledger.spent_month() == estimate
    assert ledger.spent_stage("verificador", case.procedure.pk,
                              measurement=MEASUREMENT) == estimate


def test_an_in_flight_fact_stops_counting_when_its_batch_is_recorded(case, fake_external):
    """REQ-122 (O-290-6): cuando el lote vuelve y se registran sus pedidos, el estimado del hecho
    `en_vuelo` deja de contar: las sumas son solo del costo real."""
    fake_external.enable()
    fake_external.respond("ok", usage={"input_tokens": 1000, "output_tokens": 100})
    sent = ledger.send([economic(case), technical(case)], measurement=MEASUREMENT)
    (flight,) = in_flight_events()
    assert flight.detail["lote_id"] == sent.batch_id
    assert ledger.spent_case(case.procedure.pk) == Decimal("0.003") == sent.cost_usd
    assert len(external_requests()) == 2  # un hecho por pedido, aparte del lote


def test_a_failed_batch_closes_its_in_flight_fact(case, fake_external):
    """REQ-122 (O-290-6): si la espera del lote falla, los pedidos quedan como error con el
    identificador del lote y el hecho `en_vuelo` deja de contar."""
    fake_external.enable()
    fake_external.never_ends()
    ledger.send([economic(case)], measurement=MEASUREMENT)
    assert len(in_flight_events()) == 1
    (event,) = external_requests()
    assert event.detail["resultado"] == "error" and event.detail["lote_id"] == "msgbatch_fake_1"
    assert ledger.spent_case(case.procedure.pk) == 0


def test_begin_creates_the_batch_without_waiting_and_finish_waits_for_it(case, fake_external):
    """REQ-122 (T-302, D-301-5): `begin` hace todo lo de `send` hasta crear el lote (reuso, freno,
    tope, hecho en vuelo) sin esperarlo ni registrar los pedidos; `finish` espera, registra y
    devuelve el mismo `Sent`."""
    fake_external.enable()
    fake_external.respond("ok", usage={"input_tokens": 1000, "output_tokens": 100})
    started = ledger.begin([economic(case), technical(case)], measurement=MEASUREMENT)
    assert len(fake_external.batches) == 1 and fake_external.sleeps == []
    assert not external_requests() and len(in_flight_events()) == 1
    sent = ledger.finish(started)
    assert fake_external.sleeps and len(external_requests()) == 2
    assert sent.batch_id == "msgbatch_fake_1" and list(sent.answers) == ["pedido-1", "pedido-2"]
    assert all(answer.ok for answer in sent.answers.values())
    assert sent.cost_usd == Decimal("0.003") == ledger.spent_case(case.procedure.pk)


def test_a_batch_created_by_begin_counts_for_the_cap_of_the_next_begin(
        case, fake_external, settings):
    """REQ-122 (T-302, D-301-5): dos `begin` seguidos antes de esperar: el estimado del lote en
    vuelo del primero cuenta para el tope del caso del segundo, que no sale; el primero se
    espera igual."""
    fake_external.enable()
    first, second = economic(case), technical(case, custom_id="pedido-3")
    estimate = sum(ledger.estimate_batch([first.payload], "lotes"), Decimal(0))
    settings.EXTERNAL_CASE_CAP_USD = estimate * Decimal("1.5")
    one = ledger.begin([first], measurement=MEASUREMENT)
    two = ledger.begin([second], measurement=MEASUREMENT)
    assert len(fake_external.batches) == 1
    assert two.sent.answers["pedido-3"].outcome == "bloqueado"
    assert two.sent.answers["pedido-3"].reason == "tope"
    done = ledger.finish(one)
    assert done.answers["pedido-1"].ok
    assert ledger.finish(two).answers["pedido-3"].outcome == "bloqueado"


def test_begin_in_direct_mode_sends_when_finished(case, fake_external):
    """REQ-122 (T-302): en el modo directo `begin` no manda nada y `finish` manda los pedidos de a
    uno, como `send`."""
    fake_external.enable()
    started = ledger.begin([economic(case), technical(case)], mode="directo")
    assert not fake_external.messages and not external_requests()
    sent = ledger.finish(started)
    assert len(fake_external.messages) == 2 and len(external_requests()) == 2
    assert all(answer.ok for answer in sent.answers.values())


def test_the_command_reports_open_batches_apart(case, fake_external, logged_in, monkeypatch):
    """REQ-122 (O-290-6): `gasto_externo` no cuenta un hecho `en_vuelo` como pedido ni como gasto
    real, e informa aparte los lotes sin cerrar con su estimado."""
    fake_external.enable()
    from evaluon.ai.external import client

    monkeypatch.setattr(client, "_wait_for", worker_dies)
    with pytest.raises(WorkerDied):
        ledger.send([economic(case)], measurement=MEASUREMENT)
    out = run_command(logged_in)
    assert "Pedidos registrados: 0" in out and "Gasto real: 0.000000 USD" in out
    assert "Lotes en vuelo sin cerrar: 1" in out


# --- Reverificación (H-290-6 y O6i) ------------------------------------------------------------


@pytest.mark.parametrize("separator", ["_", chr(0x200B), chr(0x2060), chr(0x00AD)],
                         ids=["V6-guion-bajo", "V7-U+200B", "V8-U+2060", "V9-U+00AD"])
def test_verifying_the_filter_sees_words_joined_by_an_invisible(case, logged_in, separator):
    """REQ-121 (H-290-6): el escaneo del comando ve un párrafo de la hoja con las palabras
    separadas solo por un guion bajo o un invisible."""
    text = separator.join(case.sheet[3].split())
    audit.record(EventType.EXTERNAL_REQUEST, outcome=Outcome.OK, channel=Channel.COMMAND,
                 detail={"procedimiento": case.procedure.pk, "etapa": "verificador",
                         "resultado": "ok", "costo_usd": 0.001, "texto_enviado": {
                             "sistema": "Instrucción.",
                             "mensajes": [{"rol": "user", "texto": text}]}})
    out = StringIO()
    with pytest.raises(CommandError, match="REQ-121"):
        call_command("gasto_externo", "--usuario", logged_in.username, "--verificar-filtro",
                     stdout=out)
    assert "Pedidos con texto de una hoja de compliance: 1" in out.getvalue()


def test_the_command_does_not_list_a_closed_batch(case, fake_external, logged_in):
    """REQ-122 (O-290-6, alteración O6i): un lote que volvió y tiene sus pedidos registrados no
    figura entre los lotes en vuelo sin cerrar."""
    fake_external.enable()
    ledger.send([economic(case)], measurement=MEASUREMENT)
    assert len(in_flight_events()) == 1
    out = run_command(logged_in)
    assert "Lotes en vuelo sin cerrar: 0 (estimado 0.000000 USD)" in out
    assert "Pedidos registrados: 1 (ok 1" in out
