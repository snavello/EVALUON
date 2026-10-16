"""Ajuste único de la matriz externa (T-294; REQ-123; plan 016, «Paso 3»; ADR-0025, ADR-0066 a
ADR-0068, ADR-0070): los hallazgos D-293-1 a D-293-5 y O-293-2 de la medición T-293 (ronda 1 del
paso 3, que no pasó la puerta 16), uno por grupo de pruebas.

Con el caso chico (`tests/assessment/data/caso-chico/`, inventado y público) y el doble del cliente
externo (`fake_external`, sin red: la suite bloquea toda llamada real). Todo el texto es inventado
(P4).
"""

import pytest
from django.conf import settings

import json

from evaluon.tenders import evaluation as ev
from evaluon.tenders import models as m
from evaluon.tenders.proposal import external
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import (  # noqa: F401  (fixture)
    load_and_read,
    make_procedure,
    propose,
    script,
)
from tests.tenders.test_external_matrix import (  # noqa: F401  (fixtures y ayudas)
    QUOTATION,
    ExternalScript,
    ext,
    rows_of,
    small_case,
)

pytestmark = pytest.mark.django_db

VERSION = "matriz-externa-v2"
PORTAL_RULE = "Una oración que solo permite una opción o solo dice cómo se carga en el Portal"
FILTER_RULE = "si solo la permite o dice cómo se carga en el Portal, se descarta"


class OptionScript(ExternalScript):
    """Como `ExternalScript`, pero el requisito del tramo que contiene `needle` sale con la opción
    `option` (el modelo que arma una fila de una opción que solo se permite)."""

    def __init__(self, fake, monkeypatch, needle, option):
        super().__init__(fake, monkeypatch)
        self.needle, self.option = needle, option

    def _segment(self, alias, text):
        answer = super()._segment(alias, text)
        if self.needle in text:
            for requirement in answer["requisitos"]:
                requirement["opcion"] = self.option
        return answer


# --- La instrucción en uso ---------------------------------------------------------------------


def test_the_external_instruction_in_use_is_v2():
    """REQ-123 (T-294): `EXTERNAL_PROMPT_VERSIONS` apunta a `matriz-externa-v2` y la etapa carga esa
    versión, con el bloque de definiciones puesto donde tiene la marca; la v1 sigue publicada."""
    instruction = external.load_instruction()

    assert settings.EXTERNAL_PROMPT_VERSIONS["matriz"] == VERSION
    assert instruction.version == VERSION
    assert "{{DEFINICIONES}}" not in instruction.text
    assert instruction.text.startswith("Ayudás a la Comisión Evaluadora")


# --- D-293-1: una opción que solo se permite no es una fila -------------------------------------


def test_d_293_1_the_instruction_says_that_an_option_that_only_permits_is_not_a_row():
    """REQ-123, D-293-1 (D-13, D-12, D-21): la extracción y el control de filas de la v2 dicen que
    la oración que solo permite una opción, o solo dice cómo se carga en el Portal, no es
    requisito (y que la fila con opción que solo eso dice se descarta)."""
    text = external.load_instruction().text

    assert PORTAL_RULE in text
    assert FILTER_RULE in text


def test_d_293_1_the_request_carries_the_rule_and_the_row_of_a_permitted_option_is_not_firm(
        small_case, operator_user, fake_external, monkeypatch):  # noqa: F811
    """REQ-123, D-293-1: el pedido que sale lleva la regla de la v2 en su sistema; si el modelo arma
    una fila con `opcion` = `descuento` en un tramo que solo permite la opción y el control la baja
    por `forma_presentacion_portal`, la fila no queda firme: queda descartada con su indicio."""
    fake_external.enable("matriz")
    script = OptionScript(fake_external, monkeypatch, QUOTATION, "descuento")
    script.rows[QUOTATION] = {"destino": "descartada", "motivo": "forma_presentacion_portal",
                              "indicio": QUOTATION, "razonamiento": "Solo dice cómo se carga."}

    requested, job = propose(operator_user, small_case.procedure)

    assert job.status == "done", job.error
    run = requested.run
    assert all(PORTAL_RULE in payload.system and FILTER_RULE in payload.system
               for payload in script.payloads)
    assert run.prompt_versions["externo"]["matriz"] == VERSION
    assert not any(QUOTATION in row.quotes.get(order=1).text for row in rows_of(run))
    discarded = m.DiscardedRow.objects.get(run=run)
    assert discarded.reason == "forma_presentacion_portal" and discarded.evidence_text == QUOTATION


def test_d_293_1_a_row_of_an_option_dropped_as_optional_goes_to_review_not_to_firm(
        small_case, operator_user, fake_external, monkeypatch):  # noqa: F811
    """REQ-123, D-293-1: si el control baja la fila con `opcion` por `condicion_opcional` (la
    oración solo permite la opción), la guarda de código la manda a revisión como sugerencia
    (`no_coinciden`, anomalía `filtro_opcion_descartada`) y no queda firme."""
    fake_external.enable("matriz")
    script = OptionScript(fake_external, monkeypatch, QUOTATION, "descuento")
    script.rows[QUOTATION] = {"destino": "descartada", "motivo": "condicion_opcional",
                              "indicio": QUOTATION, "razonamiento": "Solo permite el descuento."}

    requested, job = propose(operator_user, small_case.procedure)

    assert job.status == "done", job.error
    run = requested.run
    firm = [row for row in rows_of(run, state="propuesto")
            if QUOTATION in row.quotes.get(order=1).text]
    suggested = [row for row in rows_of(run, state="sugerido")
                 if QUOTATION in row.quotes.get(order=1).text]
    assert firm == [] and len(suggested) == 1
    assert suggested[0].doubt_reason == "no_coinciden"


# --- D-293-2: una oración que continúa a otra no sale como fila sin su sujeto ------------------------

FIRST = "El oferente presentará la constancia de inscripción vigente."
SECOND = "Deberá estar firmada por el representante legal."
PRONOUN = "Esto vale también para las ofertas presentadas en conjunto."
ANTECEDENT_RULE = ("la oración que empieza con un verbo, un pronombre o una minúscula se cita "
                   "junto con la anterior, que le da su sujeto")


class Quoting(ExternalScript):
    """El modelo cita lo que `quote` dice del tramo que contiene `needle` (la clase es formal)."""

    def __init__(self, fake, monkeypatch, needle, quote):
        super().__init__(fake, monkeypatch)
        self.needle, self.quote = needle, quote

    def _segment(self, alias, text):
        if self.needle not in text:
            return {"tramo": alias, "requisitos": [], "tecnico": [],
                    "descarte": "dato_procedimiento"}
        return {"tramo": alias, "requisitos": [
            {"cita": self.quote, "clase": "formal", "opcion": ""}], "tecnico": [], "descarte": ""}


def two_sentences_case(user):
    """Un pliego de un tramo con dos oraciones: la segunda empieza con un verbo y sola no se
    entiende."""
    procedure = make_procedure(user)
    pdf = tender_pdf([[para("SECCIÓN I - CONDICIONES PARTICULARES"),
                       para("1. CONSTANCIA", f"1.1. {FIRST} {SECOND}"),
                       para("2. ALCANCE", f"2.1. {FIRST} {PRONOUN}")]])
    load_and_read(user, procedure, pdf, title="Pliego sintético")
    return procedure


def anomalies_of(run, kind):
    return [a for a in run.anomalies if a["type"] == kind]


def test_d_293_2_the_instruction_asks_for_the_quote_with_its_antecedent():
    """REQ-123, D-293-2 (D-14, D-15): la v2 pide que la oración sin sujeto propio se cite junto con
    la anterior (la fila es la obligación completa)."""
    assert ANTECEDENT_RULE in external.load_instruction().text


def test_d_293_2_a_row_whose_quote_has_no_subject_goes_to_review_and_counts_as_a_piece(
        operator_user, script, fake_external, monkeypatch):  # noqa: F811
    """REQ-123, D-293-2: la respuesta falsa cita una oración que empieza con un verbo sin la que le
    da el sujeto: la fila no queda firme, va a revisión (sugerencia `duda`) y la propuesta cuenta
    el pedazo con la anomalía `externo_fila_sin_sujeto`; la medición de pedazos sin sujeto de las
    filas firmes da 0."""
    fake_external.enable("matriz")
    Quoting(fake_external, monkeypatch, SECOND, SECOND)
    procedure = two_sentences_case(operator_user)

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    run = requested.run
    pieces = anomalies_of(run, external.ANOMALY_NO_SUBJECT)
    assert len(pieces) == 1 and SECOND in m.Segment.objects.get(pk=pieces[0]["segment"]).text
    assert not [row for row in rows_of(run, state="propuesto") if SECOND in row.quotes.get(
        order=1).text]
    suggested = [row for row in rows_of(run, state="sugerido")
                 if SECOND in row.quotes.get(order=1).text]
    assert len(suggested) == 1 and suggested[0].doubt_reason == "duda"
    found, checked, _ = ev.pieces_of(ev._proposed(run.version))
    assert found == []


def test_d_293_2_a_quote_with_its_antecedent_stays_firm_without_the_anomaly(
        operator_user, script, fake_external, monkeypatch):  # noqa: F811
    """REQ-123, D-293-2: la misma obligación citada con la oración que le da el sujeto queda firme y
    no deja la anomalía (es lo que pide la instrucción)."""
    fake_external.enable("matriz")
    Quoting(fake_external, monkeypatch, SECOND, f"{FIRST} {SECOND}")
    procedure = two_sentences_case(operator_user)

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    run = requested.run
    assert anomalies_of(run, external.ANOMALY_NO_SUBJECT) == []
    firm = [row for row in rows_of(run, state="propuesto")
            if SECOND in row.quotes.get(order=1).text]
    assert len(firm) == 1 and FIRST in firm[0].quotes.get(order=1).text
    found, checked, _ = ev.pieces_of(ev._proposed(run.version))
    assert found == [] and checked >= 1


def test_d_293_2_a_pronoun_opening_without_its_antecedent_is_counted_too(
        operator_user, script, fake_external, monkeypatch):  # noqa: F811
    """REQ-123, D-293-2: una cita que empieza con un pronombre demostrativo sin su antecedente
    tampoco queda firme: la unidad que calcula el sistema la completa con la oración anterior, así
    que la fila firme es la obligación entera (y no hay pedazo)."""
    fake_external.enable("matriz")
    Quoting(fake_external, monkeypatch, PRONOUN, PRONOUN)
    procedure = two_sentences_case(operator_user)

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    run = requested.run
    found, _, _ = ev.pieces_of(ev._proposed(run.version))
    assert found == []
    firm = [row for row in rows_of(run, state="propuesto")
            if PRONOUN in row.quotes.get(order=1).text]
    assert len(firm) == 1 and FIRST in firm[0].quotes.get(order=1).text


# --- D-293-3: lo que el organismo comprueba del oferente es una fila, no una duda -------------------

CHECK = ("El organismo verificará en el registro de deudores que el oferente no registre deudas "
         "exigibles.")
EXTERNAL_RULE = ("también el que el organismo comprueba del oferente con una consulta externa "
                 "(registros, deudas, sanciones), que no es una duda")


def external_check_case(user):
    procedure = make_procedure(user)
    pdf = tender_pdf([[para("SECCIÓN I - CONDICIONES PARTICULARES"),
                       para("1. HABILIDAD", f"1.1. {CHECK}")]])
    load_and_read(user, procedure, pdf, title="Pliego sintético")
    return procedure


def test_d_293_3_the_instruction_says_that_an_external_check_is_a_requirement():
    """REQ-123, D-293-3 (D-33, D-01): la v2 dice, en el destino de las filas, que lo que el
    organismo comprueba del oferente con una consulta fuera de la oferta es requisito firme y que
    ser una consulta externa no es una duda; el bloque de definiciones ya lo dice como requisito
    externo de la oferta."""
    text = external.load_instruction().text

    assert EXTERNAL_RULE in text
    assert "es un requisito externo" in text


def test_d_293_3_the_request_carries_the_rule_and_an_external_check_is_a_firm_row(
        operator_user, script, fake_external, monkeypatch):  # noqa: F811
    """REQ-123, D-293-3: el pedido de completitud y filtro lleva la regla; la fila de una
    comprobación externa del organismo, con la respuesta firme del modelo, queda firme (no baja a
    revisión por «posible requisito externo») con la clase del pliego."""
    fake_external.enable("matriz")
    script = Quoting(fake_external, monkeypatch, CHECK, CHECK)
    procedure = external_check_case(operator_user)

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    run = requested.run
    completion = [p for p in script.payloads if p.stage == external.STAGE_COMPLETION]
    assert len(completion) == 1 and EXTERNAL_RULE in completion[0].system
    firm = [row for row in rows_of(run, state="propuesto") if CHECK in row.quotes.get(order=1).text]
    assert len(firm) == 1 and firm[0].category == "formal"
    assert rows_of(run, state="sugerido") == []


# --- D-293-4: los pedidos de un caso comparten el prefijo de la caché ---------------------------------


def _params(script, stage):
    return [payload.to_params() for payload in script.payloads if payload.stage == stage]


def test_d_293_4_extraction_and_completion_requests_share_the_cached_prefix(
        small_case, operator_user, ext, fake_external, monkeypatch):  # noqa: F811
    """REQ-123, D-293-4: el proveedor arma la caché con el prefijo (herramientas, sistema y formato
    de salida); en T-293 la completitud reescribía el pliego entero porque su `output_config.format`
    era otro. Con dos pedidos de extracción y uno de completitud del mismo caso, `to_params()`
    coincide en `system`, `output_config`, `thinking` y `tools` (si los hubiera); solo cambia el
    mensaje."""
    fake_external.enable("matriz")
    monkeypatch.setattr(external, "SEGMENTS_PER_REQUEST", 3)

    requested, job = propose(operator_user, small_case.procedure)

    assert job.status == "done", job.error
    extraction = _params(ext, external.STAGE_EXTRACTION)
    completion = _params(ext, external.STAGE_COMPLETION)
    assert len(extraction) >= 2 and len(completion) == 1
    for other in extraction[1:] + completion:
        for key in ("system", "output_config", "thinking", "tools"):
            assert other.get(key) == extraction[0].get(key), key
    assert extraction[0]["output_config"]["format"]["type"] == "json_schema"
    assert extraction[0]["messages"] != completion[0]["messages"]
    assert extraction[0]["system"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


def test_d_293_4_the_one_schema_has_the_three_lists_of_both_stages():
    """REQ-123, D-293-4: el esquema único trae las tres listas, todas requeridas, sin límites de
    largo, y no depende del tipo de pedido (solo de los renglones del pliego)."""
    schema = external.output_schema([1, 2])

    assert list(schema["properties"]) == ["tramos", "faltantes", "filas"]
    assert schema["required"] == ["tramos", "faltantes", "filas"]
    assert external.output_schema([1, 2]) == schema
    assert external.output_schema([1, 2, 3]) != schema
    text = json.dumps(schema)
    for limit in ("minLength", "maxLength", "maxItems", "minItems"):
        assert limit not in text


class DropsLists(ExternalScript):
    """Como `ExternalScript`, pero la respuesta de extracción no trae las listas que no pidió."""

    def reply(self, payload):
        reply = super().reply(payload)
        if payload.stage == external.STAGE_EXTRACTION and reply.get("text"):
            answer = json.loads(reply["text"])
            reply["text"] = json.dumps({"tramos": answer["tramos"]})
        return reply


def test_d_293_4_a_response_without_the_three_lists_is_not_the_requested_json(
        small_case, operator_user, fake_external, monkeypatch):  # noqa: F811
    """REQ-123, D-293-4: la salida tiene que traer las tres listas del esquema; una que trae solo
    una no es el JSON pedido: nada de lo externo se aplica y la propuesta sigue por lo local."""
    fake_external.enable("matriz")
    DropsLists(fake_external, monkeypatch)

    requested, job = propose(operator_user, small_case.procedure)

    assert job.status == "done", job.error
    run = requested.run
    kinds = [a["type"] for a in run.anomalies]
    assert external.ANOMALY_INVALID in kinds and external.ANOMALY_UNAVAILABLE in kinds
    assert run.models["externo"]["etapas"]["matriz"] == "local"
