"""Extracción de la matriz: disposición de cada tramo, cita literal, reintento único,
lotes cortados y todo o nada (REQ-024, REQ-025, REQ-028; plan 003, "Propuesta de la
matriz" y "Extracción: qué recibe y qué devuelve el modelo"; ADR-0019; T-073).

El modelo es el doble de `tests/conftest.py` con el guion de `tests/tenders/scripted.py`;
los pliegos son sintéticos (P4). La corrida real con el caso-00 es T-075.
"""

import pytest
from django.conf import settings

from evaluon.audit.models import AuditEvent, Channel, EventType, Outcome
from evaluon.tenders import models as m
from evaluon.tenders.proposal import run as proposal
from evaluon.tenders.proposal.extraction import ALL_ITEMS, build_schema, shape_item
from tests.tenders.scripted import (
    ENTREGA,
    GARANTIA,
    MULTA,
    PAGO,
    item,
    load_and_read,
    make_procedure,
    propose,
    script,  # noqa: F401  (fixture)
    three_items_pdf,
)
from tests.tenders.pdfs import para, synthetic_tender_pdf, tender_pdf

pytestmark = pytest.mark.django_db

GARANTIA_QUOTE = "constituir una garantía del 5 % del monto"


def standard(script):
    """El guion de un modelo que acierta en el pliego de tres renglones."""
    script.when(GARANTIA, item([(GARANTIA_QUOTE, "economico")]))
    script.when(PAGO, item([(PAGO, "economico")]))
    script.when(ENTREGA, item(technical=[ALL_ITEMS]))
    script.when(MULTA, item(discard="ejecucion_contrato"))


@pytest.fixture
def case(operator_user, script):
    """Un procedimiento con el pliego de tres renglones leído y el guion estándar."""
    procedure = make_procedure(operator_user)
    document = load_and_read(operator_user, procedure, three_items_pdf())
    standard(script)
    return procedure, document


def dispositions(run):
    return {d.segment.key: d for d in m.Disposition.objects.filter(run=run)
            .select_related("segment")}


def steps(run):
    return list(m.RunStep.objects.filter(run=run).order_by("id"))


def requirement_for(version, key):
    return m.Requirement.objects.get(version=version, quotes__segment__key=key,
                                     category__in=["formal", "economico"])


# --- Cobertura (REQ-024, REQ-028) ----------------------------------------------------------


def test_every_segment_has_exactly_one_disposition(operator_user, case):
    """REQ-024, REQ-028: todo tramo del pliego queda con una disposición (requisitos, fila
    técnica, descarte o pendiente); ninguno desaparece."""
    procedure, document = case

    requested, job = propose(operator_user, procedure)

    assert job.status == m.JobStatus.DONE, job.error
    run = requested.run
    segments = list(document.readings.get().segments.all())
    rows = m.Disposition.objects.filter(run=run)
    assert rows.count() == len(segments) == 19
    assert set(rows.values_list("segment_id", flat=True)) == {s.pk for s in segments}
    assert {d.outcome for d in rows} <= set(m.DispositionOutcome.values)
    counts = run.counts
    assert counts["dispositions"] == {"requisitos": 2, "tecnico": 8, "descartado": 9}
    assert counts["segments_by_source"] == {"regla": 15, "modelo": 4}
    assert counts["segments"] == 19


def test_technical_sections_do_not_reach_the_model(operator_user, case, script):
    """REQ-024: los tramos de una sección técnica no se mandan al modelo y quedan con
    origen "regla"; los títulos también se disponen por regla."""
    procedure, document = case

    requested, _ = propose(operator_user, procedure)

    sent = [block["text"] for blocks in script.calls for block in blocks.values()]
    assert len(sent) == 4
    assert not any("Bolsa" in text or "vencimiento" in text for text in sent)
    by_key = dispositions(requested.run)
    for key in ("sec-ii/1.1", "sec-iii/1", "sec-iii/1.1", "sec-iii/2", "sec-iii/2.1",
                "sec-iii/2.2", "sec-iii/3"):
        assert by_key[key].outcome == "tecnico", key
        assert by_key[key].source == "regla", key
        assert by_key[key].step is None
    for key in ("sec-i", "sec-i/1", "sec-ii", "sec-ii/1", "sec-iii"):
        assert by_key[key].outcome == "descartado", key
        assert by_key[key].discard_reason == "titulo", key
        assert by_key[key].source == "regla", key
    for key in ("sec-i/1.1", "sec-i/2.1", "sec-i/3.1", "sec-i/4.1"):
        assert by_key[key].source == "modelo", key
        assert by_key[key].step is not None


def test_model_discard_keeps_its_reason_and_empty_reason_otherwise(operator_user, case):
    """REQ-024: el motivo de descarte queda solo en lo descartado."""
    procedure, _ = case

    requested, _ = propose(operator_user, procedure)

    by_key = dispositions(requested.run)
    assert by_key["sec-i/4.1"].outcome == "descartado"
    assert by_key["sec-i/4.1"].discard_reason == "ejecucion_contrato"
    assert by_key["sec-i/1.1"].discard_reason == ""
    assert by_key["sec-i/3.1"].discard_reason == ""
    assert by_key["sec-iii/2"].discard_reason == ""


# --- Requisitos y cita literal (REQ-024, REQ-025) -------------------------------------------


def test_requirements_are_literal_fragments_in_the_order_of_the_pliego(operator_user, case):
    """REQ-024, REQ-025: los formales y económicos van primero, en el orden del pliego, y
    cada uno tiene una cita igual al recorte del texto canónico, en su tramo."""
    procedure, document = case

    requested, _ = propose(operator_user, procedure)

    version = requested.run.version
    reading = document.readings.get()
    requirements = list(m.Requirement.objects.filter(version=version).order_by("number"))
    assert [r.number for r in requirements] == [1, 2, 3, 4, 5]
    assert [r.category for r in requirements] == [
        "economico", "economico", "tecnico", "tecnico", "tecnico"]
    first, second = requirements[:2]
    quote = first.quotes.get()
    assert quote.text == GARANTIA_QUOTE
    assert quote.segment.key == "sec-i/1.1"
    assert quote.scope == "" and quote.quote_flag == ""
    assert second.quotes.get().text == PAGO
    for requirement in requirements:
        for cited in requirement.quotes.all():
            assert reading.canonical_text[cited.char_start:cited.char_end] == cited.text
            assert cited.char_start >= cited.segment.char_start
            assert cited.char_end <= cited.segment.char_end
    assert first.origin == "propuesto" and first.state == "propuesto"
    assert first.passes == ["extraccion"]
    assert first.step in steps(requested.run)
    assert first.proposed["category"] == "economico"
    assert first.proposed["quotes"][0]["text"] == GARANTIA_QUOTE


def test_requirement_items_are_those_of_the_segment_not_the_models(operator_user, script):
    """REQ-024: si el tramo cuelga de un renglón, los renglones del requisito son los del
    tramo; si no, vacíos."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("1. RENGLÓN N° 1 - PRODUCTO SINTÉTICO A",
             "1.1. Se cotiza por kilogramo de producto."),
        para("2. GENERALIDADES", "2.1. Se cotiza en pesos."),
    ]], header=None))
    script.when("por kilogramo", item([("Se cotiza por kilogramo de producto.",
                                        "economico")]))
    script.when("en pesos", item([("Se cotiza en pesos.", "economico")]))

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    version = requested.run.version
    assert requirement_for(version, "sec-i/1.1").items == [1]
    assert requirement_for(version, "sec-i/2.1").items == []


def test_section_that_names_a_class_sets_the_class_of_its_requirements(operator_user,
                                                                       script):
    """REQ-024: si el título de la sección nombra una clase, la clase de sus requisitos la
    pone la regla, aunque el modelo diga otra."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, tender_pdf([[
        para("SECCIÓN I - REQUISITOS ECONÓMICOS"),
        para("1. DOCUMENTOS", "1.1. Presentar la constancia sintética."),
    ]], header=None))
    script.when("constancia", item([("Presentar la constancia sintética.", "formal")]))

    requested, _ = propose(operator_user, procedure)

    requirement = requirement_for(requested.run.version, "sec-i/1.1")
    assert requirement.category == "economico"
    block = script.calls[0]["T1"]
    assert block["section_class"] == "económico"


def test_request_goes_to_the_batch_engine_with_one_property_per_segment(operator_user,
                                                                         case,
                                                                         fake_generation):
    """REQ-024: la propuesta usa el motor de los pedidos largos, con el máximo de salida
    de la matriz, y el esquema pide una propiedad por tramo del lote."""
    procedure, _ = case

    requested, _ = propose(operator_user, procedure)

    assert len(fake_generation.calls) == 1
    option = fake_generation.options[0]
    assert option["base_url"] == settings.GENERATION_BATCH_URL
    assert option["max_tokens"] == settings.MATRIX_MAX_OUTPUT_TOKENS == 4096
    assert option["timeout"] == settings.GENERATION_BATCH_TIMEOUT_SECONDS
    messages, schema = fake_generation.calls[0]
    assert messages[0]["content"].startswith("Sos un asistente que ayuda a la Comisión")
    assert list(schema["properties"]) == ["T1", "T2", "T3", "T4"]
    assert schema["required"] == ["T1", "T2", "T3", "T4"]
    one = schema["properties"]["T1"]
    assert one["required"] == ["requisitos", "tecnico", "descarte"]
    assert one["properties"]["tecnico"]["items"]["enum"] == ["todos", "1", "2", "3"]
    assert "" in one["properties"]["descarte"]["enum"]
    assert one["properties"]["requisitos"]["items"]["properties"]["clase"]["enum"] == [
        "formal", "economico"]
    step = steps(requested.run)[0]
    assert step.request["max_tokens"] == 4096
    assert step.request["messages"] == messages
    assert step.raw_output
    assert step.parsed["tramos"]["T1"]["valida"] is True
    assert step.segment_keys == ["sec-i/1.1", "sec-i/2.1", "sec-i/3.1", "sec-i/4.1"]
    assert step.pass_name == "extraccion" and step.retry_of is None


def test_two_equal_quotes_in_a_segment_are_joined(operator_user, case, script):
    """REQ-025: dos requisitos del mismo tramo con la misma cita se unen en uno."""
    procedure, _ = case
    script.when(PAGO, item([(PAGO, "economico"), (PAGO, "economico")]))

    requested, _ = propose(operator_user, procedure)

    version = requested.run.version
    assert m.Requirement.objects.filter(
        version=version, quotes__segment__key="sec-i/2.1").count() == 1
    assert any(a["type"] == "citas_unidas" for a in steps(requested.run)[0].anomalies)
    assert len(script.calls) == 1


def test_two_conditions_in_a_segment_make_two_rows(operator_user, script):
    """REQ-024: un tramo con dos condiciones da dos requisitos, cada uno con su
    fragmento, en el orden del texto."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("1. PRESENTACIÓN",
             "1.1. Se presenta la oferta firmada. Se presenta una garantía."),
    ]], header=None))
    script.when("firmada", item([("Se presenta una garantía.", "economico"),
                                 ("Se presenta la oferta firmada.", "formal")]))

    requested, _ = propose(operator_user, procedure)

    rows = list(m.Requirement.objects.filter(version=requested.run.version)
                .order_by("number"))
    assert [r.quotes.get().text for r in rows] == [
        "Se presenta la oferta firmada.", "Se presenta una garantía."]
    assert [r.category for r in rows] == ["formal", "economico"]


# --- Reintento único (REQ-024, REQ-025, REQ-028) ----------------------------------------------


def test_quote_not_in_the_segment_is_retried_and_stays_wide(operator_user, case, script):
    """REQ-025: una cita que no está en el tramo se vuelve a pedir una vez, solo ese tramo;
    si sigue sin estar, el requisito queda con el tramo entero y la marca de cita amplia."""
    procedure, document = case
    script.when(PAGO, item([("El pago será a los tres días de la entrega.", "economico")]))

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    assert len(script.calls) == 2
    assert list(script.calls[1]) == ["T1"]
    assert "90 días" in script.calls[1]["T1"]["text"]
    first, second = steps(requested.run)
    assert second.retry_of == first
    assert second.segment_keys == ["sec-i/2.1"]
    requirement = requirement_for(requested.run.version, "sec-i/2.1")
    cited = requirement.quotes.get()
    segment = cited.segment
    assert cited.quote_flag == "cita_amplia"
    assert (cited.char_start, cited.char_end) == (segment.char_start, segment.char_end)
    assert cited.text == segment.text
    reading = document.readings.get()
    assert reading.canonical_text[cited.char_start:cited.char_end] == cited.text
    assert requirement.step == second
    counts = requested.run.counts
    assert counts["wide_quotes"] == 1
    assert counts["quotes_retried"] == 1
    assert counts["segments_retried"] == 1
    assert dispositions(requested.run)["sec-i/2.1"].outcome == "requisitos"
    assert any(a["type"] == "cita_no_encontrada" for a in first.anomalies)


def test_retry_that_fixes_the_quote_keeps_it_literal(operator_user, case, script):
    """REQ-025: si el reintento devuelve la cita bien copiada, el requisito queda con el
    fragmento y sin marca."""
    procedure, _ = case

    def wrong_the_first_time(blocks, number, answer):
        if number == 0:
            for alias, block in blocks.items():
                if PAGO in block["text"]:
                    answer[alias] = item([("Pago a los tres días", "economico")])
        return answer

    script.override(wrong_the_first_time)

    requested, _ = propose(operator_user, procedure)

    cited = requirement_for(requested.run.version, "sec-i/2.1").quotes.get()
    assert cited.text == PAGO and cited.quote_flag == ""
    assert len(script.calls) == 2
    counts = requested.run.counts
    assert counts["wide_quotes"] == 0 and counts["quotes_retried"] == 1


def test_wide_quote_is_one_per_class_in_a_segment(operator_user, case, script):
    """REQ-025: dos citas que no se ubican, de la misma clase, dejan una sola cita amplia
    en el tramo (no se puede distinguirlas); de otra clase, otra."""
    procedure, _ = case
    script.when(PAGO, item([("Uno que no está", "economico"), ("Otro que no está",
                                                              "economico"),
                            ("Un tercero que no está", "formal")]))

    requested, _ = propose(operator_user, procedure)

    rows = m.Requirement.objects.filter(version=requested.run.version,
                                        quotes__segment__key="sec-i/2.1")
    assert sorted(r.category for r in rows) == ["economico", "formal"]
    assert all(r.quotes.get().quote_flag == "cita_amplia" for r in rows)


def test_segment_without_disposition_is_retried_and_stays_pending(operator_user, case,
                                                                  script):
    """REQ-028: un tramo sin disposición (nada que devolver) se vuelve a pedir una vez,
    solo; si sigue igual, queda pendiente de revisión."""
    procedure, _ = case
    script.when(PAGO, item())

    requested, _ = propose(operator_user, procedure)

    assert len(script.calls) == 2 and list(script.calls[1]) == ["T1"]
    by_key = dispositions(requested.run)
    assert by_key["sec-i/2.1"].outcome == "pendiente"
    assert by_key["sec-i/2.1"].source == "modelo"
    pending = m.PendingItem.objects.get(version=requested.run.version,
                                        segment__key="sec-i/2.1")
    assert pending.reason == "sin_disposicion"
    assert not m.Requirement.objects.filter(version=requested.run.version,
                                            quotes__segment__key="sec-i/2.1").exists()
    assert any(a["type"] == "sin_disposicion" and a["key"] == "sec-i/2.1"
               for a in requested.run.anomalies)


def test_retry_that_gives_a_disposition_clears_the_pending(operator_user, case, script):
    """REQ-028: si el reintento devuelve una disposición válida, el tramo no queda
    pendiente."""
    procedure, _ = case

    def empty_the_first_time(blocks, number, answer):
        if number == 0:
            for alias, block in blocks.items():
                if PAGO in block["text"]:
                    answer[alias] = item()
        return answer

    script.override(empty_the_first_time)

    requested, _ = propose(operator_user, procedure)

    assert dispositions(requested.run)["sec-i/2.1"].outcome == "requisitos"
    assert set(m.PendingItem.objects.filter(version=requested.run.version)
               .values_list("reason", flat=True)) == {"renglon_sin_especificaciones"}
    assert requested.run.counts["segments_retried"] == 1


def test_discard_together_with_requirements_is_no_disposition(operator_user, case,
                                                              script):
    """REQ-028: un descarte junto con requisitos no es una disposición."""
    procedure, _ = case
    script.when(PAGO, item([(PAGO, "economico")], discard="titulo"))

    requested, _ = propose(operator_user, procedure)

    assert dispositions(requested.run)["sec-i/2.1"].outcome == "pendiente"
    assert m.PendingItem.objects.get(version=requested.run.version,
                                     segment__key="sec-i/2.1").reason == "sin_disposicion"


def test_missing_property_for_a_segment_is_retried(operator_user, case, script):
    """REQ-028: un tramo del lote que el modelo no contestó se vuelve a pedir solo."""
    procedure, _ = case

    def drop_t2_the_first_time(blocks, number, answer):
        if number == 0:
            answer.pop("T2")
        return answer

    script.override(drop_t2_the_first_time)

    requested, _ = propose(operator_user, procedure)

    assert len(script.calls) == 2 and list(script.calls[1]) == ["T1"]
    assert "90 días" in script.calls[1]["T1"]["text"]
    assert dispositions(requested.run)["sec-i/2.1"].outcome == "requisitos"
    assert any(a["type"] == "tramo_sin_propiedad" for a in steps(requested.run)[0].anomalies)


def test_text_that_is_not_json_leaves_every_segment_to_the_retry(operator_user, case,
                                                                 script):
    """REQ-028: una salida que no es JSON deja a todos los tramos del lote sin disposición;
    cada uno se vuelve a pedir solo."""
    procedure, _ = case
    script.override(lambda blocks, number, answer: "esto no es JSON" if number == 0
                    else answer)

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    assert len(script.calls) == 5
    assert all(len(blocks) == 1 for blocks in script.calls[1:])
    assert dispositions(requested.run)["sec-i/1.1"].outcome == "requisitos"


# --- Salida cortada (REQ-024) ------------------------------------------------------------------


def test_cut_output_splits_the_batch_in_two(operator_user, case, script):
    """REQ-024: si la salida se corta por el máximo, el lote se parte en dos y se repite
    cada mitad; el pedido cortado queda registrado."""
    procedure, _ = case
    script.override(lambda blocks, number, answer: ("corte", '{"T1": {"requisitos": [{"ci')
                    if number == 0 else answer)

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    assert [len(blocks) for blocks in script.calls] == [4, 2, 2]
    cut, first, second = steps(requested.run)
    assert cut.parsed is None
    assert [a["type"] for a in cut.anomalies] == ["salida_cortada"]
    assert first.retry_of == cut and second.retry_of == cut
    assert first.segment_keys == ["sec-i/1.1", "sec-i/2.1"]
    assert second.segment_keys == ["sec-i/3.1", "sec-i/4.1"]
    by_key = dispositions(requested.run)
    assert by_key["sec-i/1.1"].step == first
    assert by_key["sec-i/4.1"].step == second
    assert requested.run.counts["split_batches"] == 1
    assert requested.run.counts["dispositions"]["requisitos"] == 2


def test_batches_follow_the_token_limit(operator_user, case, script, settings):
    """REQ-024: los lotes juntan tramos consecutivos hasta el límite de tokens de entrada
    (un token por palabra en el doble); un tramo más largo va solo."""
    procedure, _ = case
    settings.MATRIX_BATCH_INPUT_TOKENS = 30

    requested, _ = propose(operator_user, procedure)

    sizes = [len(blocks) for blocks in script.calls]
    assert sum(sizes) == 4 and len(sizes) > 1
    keys = [key for step in steps(requested.run) for key in step.segment_keys]
    assert keys == ["sec-i/1.1", "sec-i/2.1", "sec-i/3.1", "sec-i/4.1"]
    assert requested.run.counts["dispositions"]["requisitos"] == 2


# --- Marcadores de obligación (REQ-028) ----------------------------------------------------


@pytest.mark.parametrize("text", [
    "El oferente Deberá firmar", "DEBERÁN presentarse", "valor mín. de 5", "Máx. 10 días",
    "BAJO APERCIBIMIENTO de rechazo", "será requisito la firma", "no se aceptarán copias",
    "la desestimación de la oferta", "valor min. de 5",
])
def test_obligation_markers_are_found_without_accents_or_case(text):
    """REQ-028: los marcadores de obligación se reconocen sin tildes ni mayúsculas."""
    assert proposal.has_obligation_markers(text)


@pytest.mark.parametrize("text", [
    "La Agencia pagará en pesos.", "Los bienes se entregan en el depósito.",
    "Administración del contrato",
])
def test_text_without_markers_is_not_marked(text):
    """REQ-028: un texto sin marcadores no se marca."""
    assert not proposal.has_obligation_markers(text)


def test_discarded_segment_with_markers_stays_pending(operator_user, case, script):
    """REQ-028: un tramo que el modelo descartó y tiene marcadores de obligación queda
    pendiente de revisión (en media no hay pasada de completitud); sin marcadores, queda
    descartado con su motivo."""
    procedure, _ = case
    script.when(GARANTIA, item(discard="obligacion_organismo"))

    requested, _ = propose(operator_user, procedure)

    by_key = dispositions(requested.run)
    assert by_key["sec-i/1.1"].outcome == "pendiente"
    assert by_key["sec-i/1.1"].discard_reason == ""
    assert by_key["sec-i/1.1"].source == "modelo"
    pending = m.PendingItem.objects.get(version=requested.run.version,
                                        segment__key="sec-i/1.1")
    assert pending.reason == "marcadores"
    assert by_key["sec-i/4.1"].outcome == "descartado"
    assert requested.run.counts["pending_by_reason"] == {
        "marcadores": 1, "renglon_sin_especificaciones": 1}


# --- Pendientes de la lectura (REQ-028) ----------------------------------------------------


def test_reading_pending_items_are_copied_to_the_matrix(operator_user, script):
    """REQ-028: las tablas y las páginas sin texto legible de la lectura figuran como
    pendientes de revisión de la versión; la página ilegible no pasa por el modelo."""
    procedure = make_procedure(operator_user)
    document = load_and_read(operator_user, procedure, synthetic_tender_pdf())
    reading = document.readings.get()
    marked = {s.key: s.review_reason for s in reading.segments.exclude(review_reason="")}
    assert set(marked.values()) >= {"tabla", "pagina_ilegible"}

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    pending = {p.segment.key: p.reason for p in
               m.PendingItem.objects.filter(version=requested.run.version)
               .select_related("segment")}
    for key, reason in marked.items():
        assert pending[key] == reason, key
    by_key = dispositions(requested.run)
    for key, reason in marked.items():
        if reason == "pagina_ilegible":
            assert by_key[key].outcome == "pendiente" and by_key[key].source == "regla"
        if reason == "tabla":
            assert by_key[key].source == "modelo"
    sent_keys = {key for step in steps(requested.run) for key in step.segment_keys}
    assert not any(key in sent_keys for key, reason in marked.items()
                   if reason == "pagina_ilegible")
    assert any(key in sent_keys for key, reason in marked.items() if reason == "tabla")
    assert len(pending) == len(set(p.segment_id for p in
                                   m.PendingItem.objects.filter(
                                       version=requested.run.version)))
    assert m.Disposition.objects.filter(run=requested.run).count() == \
        reading.segments.count()


# --- Varios documentos --------------------------------------------------------------------------


def test_two_documents_with_the_same_keys_keep_their_own_segments(operator_user, case,
                                                                  script):
    """REQ-025: dos documentos pueden repetir las claves de sus tramos; cada requisito cita
    el tramo de su documento, y los documentos van en el orden de carga."""
    procedure, first = case
    second = load_and_read(operator_user, procedure, tender_pdf([[
        para("SECCIÓN I - ANEXO DE CONDICIONES"),
        para("1. PLAZO", "1.1. La oferta se mantiene por sesenta días corridos."),
    ]], header=None), kind="anexo", title="Anexo de condiciones")
    script.when("sesenta días", item([("se mantiene por sesenta días corridos",
                                       "formal")]))

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    run = requested.run
    assert [d["document"] for d in run.documents] == [first.pk, second.pk]
    requirements = list(m.Requirement.objects.filter(version=run.version)
                        .order_by("number"))
    assert [r.category for r in requirements][:3] == ["economico", "economico", "formal"]
    cited = requirements[2].quotes.get()
    assert cited.segment.key == "sec-i/1.1"
    assert cited.segment.reading.document == second
    assert second.readings.get().canonical_text[cited.char_start:cited.char_end] == \
        "se mantiene por sesenta días corridos"
    assert m.Disposition.objects.filter(run=run).count() == (
        first.readings.get().segments.count() + second.readings.get().segments.count())
    assert "Anexo de condiciones" in script.calls[0]["T5"]["document"]


# --- Todo o nada (ADR-0018) ----------------------------------------------------------------------


def test_service_failure_leaves_the_job_failed_and_the_step_recorded(operator_user, case,
                                                                      script):
    """ADR-0018: si el servicio falla, el pedido queda `failed` con su motivo, no se crea
    ninguna versión, y el pedido al modelo y el hecho fallido quedan registrados."""
    procedure, _ = case
    script.fail("timeout")

    requested, job = propose(operator_user, procedure)

    assert job.status == m.JobStatus.FAILED
    assert job.error.startswith("timeout")
    assert requested.run.version is None
    assert not m.MatrixVersion.objects.exists()
    assert not m.Requirement.objects.exists()
    assert not m.Disposition.objects.exists()
    assert not m.PendingItem.objects.exists()
    step = steps(requested.run)[0]
    assert step.raw_output == "" and step.parsed is None
    assert step.anomalies[0]["type"] == "servicio" and step.anomalies[0]["reason"] == "timeout"
    assert step.request["max_tokens"] == 4096
    event = AuditEvent.objects.get(event_type=EventType.MATRIX_PROPOSAL)
    assert event.outcome == Outcome.FAILED
    assert event.user == operator_user and event.channel == Channel.COMMAND
    assert event.detail["run"] == requested.run.pk
    assert event.detail["model_requests_saved"] == 1
    assert "ServiceTimeoutError" in event.detail["error"]


def test_failure_after_the_model_leaves_no_half_matrix_but_keeps_the_steps(
        operator_user, case, monkeypatch):
    """ADR-0018: una falla al guardar no deja una matriz a medias (ni versión, ni
    requisitos, ni disposiciones), pero los pedidos al modelo ya registrados quedan."""
    procedure, _ = case

    def fail(*args, **kwargs):
        raise RuntimeError("falla simulada al guardar")

    monkeypatch.setattr(proposal, "_check_quote", fail)

    requested, job = propose(operator_user, procedure)

    assert job.status == m.JobStatus.FAILED and "falla simulada" in job.error
    assert not m.MatrixVersion.objects.exists()
    assert not m.Requirement.objects.exists()
    assert not m.RequirementQuote.objects.exists()
    assert not m.Disposition.objects.exists()
    assert not m.PendingItem.objects.exists()
    assert len(steps(requested.run)) == 1
    event = AuditEvent.objects.get(event_type=EventType.MATRIX_PROPOSAL)
    assert event.outcome == Outcome.FAILED
    assert event.detail["model_requests_saved"] == 1
    assert not AuditEvent.objects.filter(event_type=EventType.MATRIX_PROPOSAL,
                                         outcome=Outcome.OK).exists()


# --- Forma de lo que el modelo devuelve (REQ-024) --------------------------------------------------


def test_schema_asks_for_the_known_items_only():
    """REQ-024: el esquema admite `todos` y los renglones del pliego; sin renglones, solo
    `todos`."""
    schema = build_schema(["T1"], [])
    assert schema["properties"]["T1"]["properties"]["tecnico"]["items"]["enum"] == ["todos"]


@pytest.mark.parametrize("raw", [
    [],
    {"requisitos": [], "tecnico": []},
    {"requisitos": [{"cita": "x"}], "tecnico": [], "descarte": ""},
    {"requisitos": [{"cita": "x", "clase": "tecnico"}], "tecnico": [], "descarte": ""},
    {"requisitos": [], "tecnico": ["uno"], "descarte": ""},
    {"requisitos": [], "tecnico": [], "descarte": "otro"},
    {"requisitos": "x", "tecnico": [], "descarte": ""},
])
def test_malformed_items_are_refused(raw):
    """REQ-024: un tramo con la forma rota no es una disposición."""
    from evaluon.tenders.proposal.extraction import InvalidItem

    with pytest.raises(InvalidItem):
        shape_item(raw)


def test_technical_marks_are_numbers_or_all():
    """REQ-024: las marcas técnicas se leen como números; `todos` se impone."""
    assert shape_item({"requisitos": [], "tecnico": ["2", "1", "2"],
                       "descarte": ""}).technical == [2, 1]
    assert shape_item({"requisitos": [], "tecnico": ["2", "todos"],
                       "descarte": ""}).technical == ["todos"]


def test_quote_with_other_line_breaks_is_found_and_saves_the_canonical_slice(
        operator_user, script):
    """REQ-025: una cita con espacios o saltos de línea distintos de los del pliego se
    encuentra, y lo que se guarda es el recorte exacto del texto canónico, sin marca."""
    procedure = make_procedure(operator_user)
    document = load_and_read(operator_user, procedure, tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("1. PRESENTACIÓN", "1.1. Se presenta la oferta firmada",
             "por el representante legal."),
    ]], header=None))
    script.when("firmada", item([("Se presenta  la oferta\nfirmada por\nel representante "
                                  "legal.", "formal")]))

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    cited = requirement_for(requested.run.version, "sec-i/1.1").quotes.get()
    reading = document.readings.get()
    assert cited.quote_flag == ""
    assert reading.canonical_text[cited.char_start:cited.char_end] == cited.text
    assert " ".join(cited.text.split()) == "Se presenta la oferta firmada por el " \
        "representante legal."
    assert len(script.calls) == 1


def test_quote_with_a_changed_letter_is_not_found_and_stays_wide(operator_user, script):
    """REQ-025: una letra cambiada no se tolera: se reintenta y queda cita amplia."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("1. PRESENTACIÓN", "1.1. Se presenta la oferta firmada."),
    ]], header=None))
    script.when("firmada", item([("Se presenta la oferta firmeda.", "formal")]))

    requested, _ = propose(operator_user, procedure)

    cited = requirement_for(requested.run.version, "sec-i/1.1").quotes.get()
    assert cited.quote_flag == "cita_amplia"
    assert len(script.calls) == 2
