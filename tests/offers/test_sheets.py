"""Pedir y armar la ficha de una oferta (REQ-039, REQ-040, REQ-041, REQ-043, REQ-044; plan 008,
"Flujo de IA: armar la ficha"; ADR-0027; T-130).

La matriz es la del caso chico, inventada (`tests/offers/data/caso-chico/`): cinco requisitos
formales y económicos (números 1 a 5) y tres renglones técnicos (6 a 8). La oferta tiene tres
pasajes (uno por página). El modelo se reemplaza por un guion (`script`): elige pasajes por su
texto o devuelve lo que cada prueba necesita; el sistema arma los fragmentos con el texto del
pasaje, nunca con lo que el modelo escribe."""

import json

import pytest
from django.utils import timezone

from evaluon.accounts.permissions import RoleRejected
from evaluon.ai import ServiceTimeoutError
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.offers import models as om
from evaluon.offers.services import offers as offers_service
from evaluon.offers.services import sheets
from evaluon.tenders import jobs
from evaluon.tenders import models as m
from tests.offers.conftest import DATA, make_offer, pick

pytestmark = pytest.mark.django_db

DECLARATION = "Declaro bajo juramento"
VALIDITY = "validez por sesenta días"
PRICES = "Renglón 1: resma de papel A4"


def events(event_type, outcome=None):
    found = AuditEvent.objects.filter(event_type=event_type)
    return found.filter(outcome=outcome) if outcome else found


def entry_of(sheet, number):
    return sheet.entries.get(requirement__number=number)


def build(offer, user, **kwargs):
    return sheets.build_sheet(offer, user, **kwargs)


# --- Pedido -------------------------------------------------------------------------------


def test_a_request_encloses_the_offer_and_leaves_its_event(offer, matrix, operator_user):
    """REQ-043: el pedido queda con la versión de la matriz y las lecturas incluidas."""
    requested = sheets.request_sheet(operator_user, offer)
    job = requested.job
    assert (job.kind, job.target_id, job.status) == (m.JobKind.BUILD_SHEET, offer.pk,
                                                     m.JobStatus.QUEUED)
    detail = events(EventType.SHEET_REQUEST, Outcome.OK).get().detail
    assert detail["matrix_version"] == matrix.version.pk and detail["job"] == job.pk
    assert len(detail["readings"]) == 2 and detail["matrix_version_number"] == 1


def test_the_sheet_is_only_built_against_a_validated_matrix(operator_user):
    """REQ-043: sin matriz validada no se pide la ficha, y el rechazo queda registrado."""
    procedure = m.Procedure.objects.create(
        number="SIN-MATRIZ", procedure_type="x", subject="x",
        authorization_date="2026-01-01", created_by=operator_user)
    offer = make_offer(procedure, operator_user, "Oferente", {"a.pdf": ["texto"]})
    m.MatrixVersion.objects.create(procedure=procedure, number=1, created_by=operator_user)
    with pytest.raises(sheets.SheetRefused) as error:
        sheets.request_sheet(operator_user, offer)
    assert error.value.reason == "no_matrix"
    assert events(EventType.SHEET_REQUEST, Outcome.REJECTED).get().detail["reason"] == \
        "no_matrix"
    assert not m.Job.objects.filter(kind=m.JobKind.BUILD_SHEET).exists()
    with pytest.raises(sheets.SheetRefused):
        sheets.build_sheet(offer, operator_user)


def test_a_request_without_documents_is_refused(procedure, operator_user):
    """REQ-039: una oferta sin documentos no tiene ficha."""
    offer = offers_service.register_offer(operator_user, procedure, bidder="Vacía")
    with pytest.raises(sheets.SheetRefused) as error:
        sheets.request_sheet(operator_user, offer)
    assert error.value.reason == "no_documents"


def test_a_request_while_a_document_is_being_read_is_refused(procedure, operator_user):
    """REQ-039: no se arma la ficha con documentos sin leer."""
    offer = offers_service.register_offer(operator_user, procedure, bidder="Leyendo")
    offers_service.load_document(operator_user, offer,
                                 data=(DATA / "oferta-propuesta.pdf").read_bytes(),
                                 file_name="oferta-propuesta.pdf")
    with pytest.raises(sheets.SheetRefused) as error:
        sheets.request_sheet(operator_user, offer)
    assert error.value.reason == "reading_in_progress"


def test_a_request_with_a_failed_reading_is_refused(procedure, operator_user, fake_ai):
    """REQ-039: una lectura fallida bloquea la ficha, con su motivo."""
    offer = offers_service.register_offer(operator_user, procedure, bidder="Fallida")
    offers_service.load_document(operator_user, offer,
                                 data=(DATA / "oferta-propuesta.pdf").read_bytes(),
                                 file_name="oferta-propuesta.pdf")
    fake_ai.embeddings.unavailable()
    jobs.run_next()
    with pytest.raises(sheets.SheetRefused) as error:
        sheets.request_sheet(operator_user, offer)
    assert error.value.reason == "reading_failed"


def test_a_second_request_in_progress_is_refused(offer, operator_user):
    """Un solo pedido de ficha por oferta a la vez."""
    sheets.request_sheet(operator_user, offer)
    with pytest.raises(sheets.SheetRefused) as error:
        sheets.request_sheet(operator_user, offer)
    assert error.value.reason == "request_in_progress"


def test_a_user_without_commission_role_cannot_request(offer, no_commission_user):
    """REQ-039: sin rol de la Comisión no se pide la ficha."""
    with pytest.raises(RoleRejected):
        sheets.request_sheet(no_commission_user, offer)
    assert not m.Job.objects.filter(kind=m.JobKind.BUILD_SHEET).exists()


def test_the_worker_builds_the_sheet_of_a_request(offer, matrix, operator_user, script):
    """REQ-039: el `worker` atiende el pedido y deja la ficha y el hecho `sheet_build`."""
    script.choose(pick(DECLARATION))
    requested = sheets.request_sheet(operator_user, offer)
    job = jobs.run_next()
    assert job.pk == requested.job.pk and job.status == m.JobStatus.DONE
    sheet = offer.sheets.get()
    assert (sheet.job_id, sheet.matrix_version_id, sheet.channel) == (job.pk,
                                                                      matrix.version.pk,
                                                                      "screen")
    event = events(EventType.SHEET_BUILD, Outcome.OK).get()
    assert event.detail["sheet"] == sheet.pk and event.detail["job"] == job.pk


# --- Fragmentos: texto literal, de la base ---------------------------------------------------


def test_a_fragment_is_the_passage_text_not_what_the_model_writes(offer, operator_user, script):
    """REQ-039: el fragmento es copia del pasaje, con documento, página y texto literal; la
    síntesis es lo único que escribe el modelo."""
    script.choose(pick(DECLARATION, synthesis="Declara estar habilitado para contratar.",
                       when="declaración jurada"))
    sheet = build(offer, operator_user)
    row = entry_of(sheet, 1)
    assert row.outcome == om.Outcome.ENCONTRADO
    assert row.synthesis == "Declara estar habilitado para contratar."
    fragment = row.fragments.get()
    passage = fragment.passage
    assert fragment.text == passage.text
    assert fragment.text == passage.reading.canonical_text[fragment.char_start:fragment.char_end]
    assert (passage.page, passage.reading.document.file_name) == (1, "oferta.pdf")
    assert (fragment.origin, fragment.state) == ("sistema", "propuesto")
    assert fragment.proposed["text"] == passage.text


def test_the_model_cannot_put_text_in_a_fragment(offer, operator_user, script):
    """REQ-039: aunque el modelo devuelva texto inventado, el fragmento es el del pasaje."""

    script.choose(lambda *args: json.dumps({"pasajes": ["P1"], "sintesis": "x", "texto": "y"}))
    sheet = build(offer, operator_user)
    row = entry_of(sheet, 1)
    # la salida con un campo de más no tiene la forma pedida: no se usa nada de ella
    assert row.outcome == om.Outcome.NO_ENCONTRADO and not row.fragments.exists()
    assert {a["type"] for a in sheet.anomalies} == {"salida_invalida"}


def test_candidates_come_from_all_documents_regardless_of_their_kind(
        procedure, operator_user, fake_ai, script):
    """ADR-0027: la búsqueda recorre todos los documentos; el tipo es solo un dato."""
    offer = make_offer(procedure, operator_user, "Con tipos", {
        "poliza.pdf": ["La póliza de caución respalda la validez por sesenta días."],
        "otro.pdf": ["Nada que ver."]}, kinds={"poliza.pdf": "garantia", "otro.pdf": "otro"})
    script.choose(pick("póliza", when="validez"))
    sheet = build(offer, operator_user)
    assert entry_of(sheet, 5).fragments.get().passage.reading.document.file_name == "poliza.pdf"
    step = sheet.steps.filter(entry__requirement__number=5).get()
    assert len(step.candidates["pool"]) == 2


def test_only_the_best_candidates_by_the_reranker_reach_the_model(
        procedure, operator_user, fake_ai, script):
    """ADR-0027: pasan los mejores del reranker, de mayor a menor puntaje, hasta el tope."""
    pages = [f"Texto número {n}." for n in range(1, 17)]
    offer = make_offer(procedure, operator_user, "Muchos", {"a.pdf": pages})
    fake_ai.reranker.scores = {f"número {n}.": n / 20 for n in range(1, 17)}
    script.choose(pick("número 16."))
    sheet = build(offer, operator_user)
    blocks = script.calls[0]["blocks"]
    assert len(blocks) == 8
    assert list(blocks.values())[0] == "Texto número 16."
    assert list(blocks.values())[-1] == "Texto número 9."
    step = sheet.steps.filter(entry__requirement__number=1).get()
    assert len(step.candidates["pool"]) == 16 and len(step.candidates["sent"]) == 8


def test_the_request_to_the_model_uses_the_batch_engine_and_fixed_parameters(
        offer, operator_user, script):
    """P6: temperatura 0 y semilla fija, motor de los pedidos del `worker`, esquema JSON."""
    build(offer, operator_user)
    call = script.calls[0]
    assert call["kwargs"]["base_url"].startswith("http://generation_batch")
    assert call["kwargs"]["max_tokens"] == 400
    assert call["schema"]["required"] == ["pasajes", "sintesis"]
    assert call["messages"][0]["content"].startswith("Sos un asistente")


# --- Sin respuesta ---------------------------------------------------------------------


def test_a_requirement_without_an_answer_says_it_was_not_found(offer, operator_user, script):
    """REQ-040: el requisito sin respuesta figura "no se encontró en la oferta", sin
    fragmentos ni síntesis, y cuenta en la lista de lo que no se encontró."""
    script.choose(pick(DECLARATION, when="declaración jurada"))
    sheet = build(offer, operator_user)
    row = entry_of(sheet, 3)  # la garantía
    assert row.outcome == om.Outcome.NO_ENCONTRADO
    assert (row.synthesis, row.quoted) == ("", "")
    assert not row.fragments.exists() and not row.unread_pages_warning
    page = sheets.sheet_page(operator_user, sheet.pk)
    missing = {r.requirement.number for r in page.missing}
    assert 3 in missing and 1 not in missing
    assert sheet.counts["not_found"] + sheet.counts["found"] == sheet.counts["entries"] == 9


def test_an_offer_with_no_passages_leaves_every_requirement_not_found(
        procedure, operator_user, fake_ai, script):
    """REQ-040: sin pasajes no hay pedido al modelo y nada queda vacío."""
    offer = make_offer(procedure, operator_user, "Sin texto", {"a.pdf": []})
    sheet = build(offer, operator_user)
    assert script.calls == []
    assert set(sheet.entries.values_list("outcome", flat=True)) == {"no_encontrado"}


def test_a_not_found_row_warns_when_the_offer_has_unread_pages(
        procedure, operator_user, fake_ai, script):
    """REQ-040: si hay páginas sin leer, la fila lo avisa y no supone que la respuesta
    estaba ahí."""
    offer = make_offer(procedure, operator_user, "Con hoja ilegible",
                       {"a.pdf": ["Texto sin relación.", ""]}, unread=[("a.pdf", 2)])
    sheet = build(offer, operator_user)
    assert all(e.unread_pages_warning for e in sheet.entries.all())
    page = sheets.sheet_page(operator_user, sheet.pk)
    assert [(p["page"], p["title"]) for p in page.unread] == [(2, "a.pdf")]


# --- Síntesis sin juicio -------------------------------------------------------------------


@pytest.mark.parametrize("text, found", [
    ("La oferta cumple con lo pedido", ["cumple"]),
    ("No cumple el plazo", ["cumple"]),
    ("Incumple la garantía", ["incumple"]),
    ("La oferta es adecuada y satisface", ["adecuada", "satisface"]),
    ("Está conforme al pliego", ["conforme"]),
    ("Presenta un cumplimiento total", ["cumplimiento"]),
    ("Cotiza 100 unidades a $ 3.000", []),
    ("Declara estar habilitado para contratar", []),
])
def test_judgment_words(text, found):
    """REQ-041: la lista de palabras de juicio, sin tildes ni mayúsculas."""
    assert sheets.judgment_words(text) == found


def test_a_synthesis_with_judgment_is_retried_with_the_warning(offer, operator_user, script):
    """REQ-041: un reintento con el aviso; si la segunda no tiene juicio, se usa."""

    def answer(requirement, blocks, number, messages):
        alias = next((a for a, t in blocks.items() if DECLARATION in t), None)
        if alias is None or "declaración jurada" not in requirement:
            return None
        if "juicio" in messages[-1]["content"]:
            return {"pasajes": [alias], "sintesis": "Declara estar habilitado."}
        return {"pasajes": [alias], "sintesis": "La oferta cumple con la habilitación."}

    script.choose(answer)
    sheet = build(offer, operator_user)
    row = entry_of(sheet, 1)
    assert row.synthesis == "Declara estar habilitado."
    steps = list(sheet.steps.filter(entry=row).order_by("id"))
    assert len(steps) == 2 and steps[1].retry_of_id == steps[0].pk
    assert steps[0].anomalies[0]["type"] == "sintesis_con_juicio"
    assert "cumple" in script.calls[1]["messages"][-1]["content"]
    assert sheet.counts["retries"] == 1 and sheet.anomalies == []


def test_a_synthesis_that_keeps_the_judgment_is_replaced_by_a_neutral_one_with_its_anomaly(
        offer, operator_user, script):
    """REQ-041: si vuelve a fallar, la fila no queda vacía: lleva una síntesis neutra que solo
    dice dónde está la respuesta, conserva sus fragmentos y deja la anomalía en el registro;
    ninguna síntesis guardada tiene palabras de juicio (T-135)."""
    script.choose(pick(DECLARATION, synthesis="La oferta cumple.", when="declaración jurada"))
    sheet = build(offer, operator_user)
    row = entry_of(sheet, 1)
    assert row.synthesis.startswith("El oferente responde en: ") and row.fragments.count() == 1
    assert "oferta.pdf" in row.synthesis and "página 1" in row.synthesis
    assert row.outcome == om.Outcome.ENCONTRADO
    assert {"type": "sintesis_con_juicio", "requirement": 1} in sheet.anomalies
    assert all(not sheets.judgment_words(e.synthesis) for e in sheet.entries.all())


# --- Respuestas del modelo que no sirven ---------------------------------------------------------


def test_an_alias_that_does_not_exist_invalidates_the_choice(offer, operator_user, script):
    """ADR-0027: una alias inexistente invalida la elección; se reintenta una vez y, si
    sigue mal, la fila queda "no se encontró" con la anomalía registrada."""
    script.choose(lambda *args: {"pasajes": ["P99"], "sintesis": "x"})
    sheet = build(offer, operator_user)
    row = entry_of(sheet, 1)
    assert row.outcome == om.Outcome.NO_ENCONTRADO and not row.fragments.exists()
    assert {"type": "alias_inexistente", "requirement": 1} in sheet.anomalies
    assert sheet.steps.filter(entry=row).count() == 2


def test_an_output_that_is_not_json_is_retried_once(offer, operator_user, script):
    """La salida inválida se reintenta una vez con el aviso; la segunda sirve."""

    def answer(requirement, blocks, number, messages):
        if "declaración jurada" not in requirement:
            return None
        if "forma pedida" not in messages[-1]["content"]:
            return "esto no es JSON"
        return {"pasajes": [], "sintesis": ""}

    script.choose(answer)
    sheet = build(offer, operator_user)
    steps = sheet.steps.filter(entry__requirement__number=1).order_by("id")
    assert [bool(s.parsed) for s in steps] == [False, True]
    assert steps[0].raw_output == "esto no es JSON"
    assert sheet.anomalies == []


def test_a_technical_failure_of_the_model_saves_nothing(offer, operator_user, fake_ai, script):
    """P6: una falla del motor deja el hecho `failed` y ninguna ficha a medias."""

    def fail(requirement, blocks, number, messages):
        raise ServiceTimeoutError("generation: demora agotada", service="generation")

    script.choose(fail)
    with pytest.raises(ServiceTimeoutError):
        build(offer, operator_user)
    assert not om.Sheet.objects.exists() and not om.SheetStep.objects.exists()
    assert events(EventType.SHEET_BUILD, Outcome.FAILED).get().detail["error"].startswith(
        "ServiceTimeoutError")


def test_every_model_request_is_recorded(offer, operator_user, script):
    """P6: cada pedido queda con sus candidatos, el pedido, la salida cruda y lo
    interpretado."""
    script.choose(pick(VALIDITY, when="validez"))
    sheet = build(offer, operator_user)
    step = sheet.steps.get(entry__requirement__number=5)
    assert step.request["temperature"] == 0 and step.request["seed"] == 42
    assert json.loads(step.raw_output)["pasajes"] == ["P1"]
    assert step.parsed["pasajes"] == ["P1"]
    pool = step.candidates["pool"]
    assert {"passage", "sources", "distance", "words_rank", "score", "key", "page",
            "document"} <= set(pool[0])
    assert step.timings["generation_seconds"] >= 0
    detail = events(EventType.SHEET_BUILD, Outcome.OK).get().detail
    assert detail["models"]["generation_batch"]["sha256"]
    assert detail["parameters"]["candidates_to_model"] == 8
    assert detail["prompt_versions"] == {"ficha": "ficha-v2", "ficha_renglon": "ficha-renglon-v4",
                                         "reescritura": "reescritura-v1"}
    assert detail["counts"]["model_requests"] == sheet.steps.count()


# --- Renglones y documentación técnica ---------------------------------------------------------


def test_a_quoted_item_shows_its_citation_and_a_missing_one_is_not_quoted(
        offer, operator_user, script):
    """REQ-044: cada renglón figura "cotizado" (con la cita de dónde) o "no cotizado"."""
    script.choose(pick(PRICES, when="RESMA"))
    sheet = build(offer, operator_user)
    first, third = entry_of(sheet, 6), entry_of(sheet, 8)
    assert first.quoted == om.Quoted.COTIZADO and first.fragments.get().text.startswith(
        "Los precios")
    assert third.quoted == om.Quoted.NO_COTIZADO and not third.fragments.exists()
    assert entry_of(sheet, 1).quoted == ""  # solo las filas por renglón llevan cotización
    item_call = next(c for c in script.calls if c["messages"][-1]["content"].startswith("Renglón"))
    assert item_call["schema"]["required"] == ["cotizado", "pasajes", "sintesis"]


def test_an_item_the_model_says_was_not_quoted_is_not_quoted_even_with_a_passage(
        offer, operator_user, script):
    """REQ-044: sin "sí" del modelo, el renglón no figura cotizado."""
    script.choose(pick(PRICES, quoted="no", when="RESMA"))
    sheet = build(offer, operator_user)
    assert entry_of(sheet, 6).quoted == om.Quoted.NO_COTIZADO


def test_an_item_in_an_unreadable_page_is_never_not_quoted(
        procedure, operator_user, fake_ai, script):
    """REQ-044: si la oferta tiene páginas sin leer, un renglón sin cita figura "no se pudo
    leer", nunca "no cotizado"; el que sí se encontró sigue "cotizado"."""
    offer = make_offer(procedure, operator_user, "Con hoja ilegible",
                       {"a.pdf": ["Renglón 1: resma de papel A4, 100 unidades.", ""]},
                       unread=[("a.pdf", 2)])
    script.choose(pick(PRICES, when="RESMA"))
    sheet = build(offer, operator_user)
    assert entry_of(sheet, 6).quoted == om.Quoted.COTIZADO
    assert entry_of(sheet, 8).quoted == om.Quoted.NO_SE_PUDO_LEER
    assert sheet.counts["no_se_pudo_leer"] == 2
    page = sheets.sheet_page(operator_user, sheet.pk)
    assert "no se pudo leer" in " ".join(
        e.get_quoted_display().lower() for e in (r.entry for r in page.rows) if e.quoted)


def test_technical_documentation_is_indicated(procedure, operator_user, fake_ai, script):
    """REQ-044: la ficha indica si la oferta trae documentación técnica solo si hay un
    documento clasificado técnico; una tabla de renglones con fragmentos no alcanza."""
    without = make_offer(procedure, operator_user, "Sin", {"a.pdf": ["Texto sin relación."]})
    assert build(without, operator_user).technical_documents["present"] is False
    typed = make_offer(procedure, operator_user, "Con tipo",
                       {"b.pdf": ["Texto sin relación."]}, kinds={"b.pdf": "tecnica"})
    sheet = build(typed, operator_user)
    assert sheet.technical_documents["present"] is True
    assert sheet.technical_documents["documents"] == [typed.documents.get().pk]
    script.choose(pick("Renglón 2", when="CARTUCHO"))
    cited = make_offer(procedure, operator_user, "Con cita",
                       {"c.pdf": ["Renglón 2: cartucho de tóner."]})
    sheet = build(cited, operator_user)
    assert sheet.technical_documents == {"present": False, "documents": []}
    assert sheet.entries.filter(requirement__category="tecnico", fragments__isnull=False
                                ).exists()


# --- Versión de la matriz --------------------------------------------------------------------


def test_the_sheet_says_which_matrix_version_it_was_built_with(offer, matrix, operator_user,
                                                               script):
    """REQ-043: la ficha armada con la versión 1 avisa, cuando se valida la 2, que se armó
    con la 1."""
    sheet = build(offer, operator_user)
    page = sheets.sheet_page(operator_user, sheet.pk)
    assert sheet.matrix_version_id == matrix.version.pk and page.newer_version is None
    second = m.MatrixVersion.objects.create(procedure=matrix.procedure, number=2,
                                            created_by=operator_user)
    second.status = m.VersionStatus.VALIDATED
    second.validated_at = timezone.now()
    second.validated_by = operator_user
    second.save()
    page = sheets.sheet_page(operator_user, sheet.pk)
    assert page.newer_version.number == 2 and page.sheet.matrix_version.number == 1
    newer = build(offer, operator_user)
    assert (newer.number, newer.matrix_version.number) == (2, 2)
    assert offer.sheets.count() == 2  # la anterior sigue


def test_the_sheet_has_a_row_per_firm_requirement_only(matrix, operator_user, fake_ai,
                                                       script):
    """La ficha tiene una fila por requisito firme (propuesto o confirmado): ni los quitados
    ni las sugerencias de condición son filas."""
    segment = m.Segment.objects.filter(
        reading__document__procedure=matrix.procedure).order_by("order").first()
    other = m.Procedure.objects.create(
        number="ESTADOS", procedure_type="x", subject="x", authorization_date="2026-01-01",
        created_by=operator_user)
    version = m.MatrixVersion.objects.create(procedure=other, number=1,
                                             created_by=operator_user)
    for number, (state, doubt) in enumerate([("propuesto", ""), ("confirmado", ""),
                                              ("quitado", ""), ("sugerido", "duda")], start=1):
        requirement = m.Requirement.objects.create(
            version=version, number=number, category="formal", origin="propuesto",
            state=state, doubt_reason=doubt)
        m.RequirementQuote.objects.create(
            requirement=requirement, order=1, segment=segment, char_start=segment.char_start,
            char_end=segment.char_end, text=segment.text)
    version.status = m.VersionStatus.VALIDATED
    version.validated_at = timezone.now()
    version.validated_by = operator_user
    version.save()
    offer = make_offer(other, operator_user, "Oferente", {"a.pdf": ["Texto."]})
    sheet = build(offer, operator_user)
    assert list(sheet.entries.order_by("requirement__number")
                .values_list("requirement__number", flat=True)) == [1, 2]
    assert set(sheets.FIRM_STATES) == {m.RequirementState.PROPUESTO,
                                       m.RequirementState.CONFIRMADO}


def test_the_prompts_exist_and_say_the_model_does_not_judge():
    """REQ-041: las instrucciones piden una síntesis sin juicio."""
    for name in ("ficha", "ficha_renglon"):
        text = sheets.load_prompt(name)
        assert "no cumple" in text and "No decidís" in text


# --- Ronda 1 de T-135 --------------------------------------------------------------------------


def _table_offer(procedure, operator_user):
    """Una oferta cuya tabla del Portal (solo número y descripción) está partida en tres
    pasajes de la misma página, más una página aparte."""
    offer = make_offer(procedure, operator_user, "Con tabla", {
        "tabla.pdf": ["Renglón Descripción", "Otra página sin relación."]})
    reading = om.Reading.objects.get(document__offer=offer)
    first = reading.passages.get(page=1)
    from tests.conftest import unit_vector

    for order, text in ((3, "2 Cartucho de tóner negro"), (4, "1 Resma de papel A4")):
        om.Passage.objects.create(
            reading=reading, order=order, key=f"p1/b{order}", page=1, char_start=0, char_end=1,
            text=text, text_origin="pdf_text", embedding=unit_vector(100 + order))
    return offer, first


def test_the_query_of_an_item_row_starts_with_the_item_number(offer, operator_user, fake_ai,
                                                              script):
    """REQ-044 (T-135): la consulta del renglón lleva "Renglón N" delante; la de un requisito
    común no cambia."""
    build(offer, operator_user)
    queries = [query for query, _ in fake_ai.reranker.calls]
    assert any(q.startswith("Renglón 1: ") for q in queries)
    assert any(q.startswith("Renglón 3: ") for q in queries)
    assert not any(q.startswith("Renglón") for q in queries
                   if "declaración jurada" in q or "validez" in q)


def test_an_item_row_also_gets_the_neighbors_of_its_best_passages(
        procedure, operator_user, fake_ai, script, settings):
    """REQ-044 (T-135): la zona de tabla: los pasajes vecinos de la misma página del mejor
    candidato llegan al modelo aunque no hayan entrado por el reranker; una fila común no los
    recibe, y una página distinta tampoco."""
    settings.OFFERS_CANDIDATES_TO_MODEL = 1
    settings.OFFERS_ITEM_CANDIDATES_TO_MODEL = 1
    offer, _ = _table_offer(procedure, operator_user)
    fake_ai.reranker.scores = {"Cartucho": 0.9}
    script.choose(lambda requirement, blocks, number, messages: None)
    sheet = build(offer, operator_user)
    item_call = next(c for c in script.calls if c["messages"][-1]["content"].startswith("Renglón"))
    texts = list(item_call["blocks"].values())
    assert texts[0] == "2 Cartucho de tóner negro"
    assert "1 Resma de papel A4" in texts and "Renglón Descripción" not in texts
    assert "Otra página sin relación." not in texts
    common = next(c for c in script.calls
                  if not c["messages"][-1]["content"].startswith("Renglón"))
    assert len(common["blocks"]) == 1
    step = sheet.steps.filter(entry__requirement__number=6).get()
    assert any("neighbor" in c["sources"] for c in step.candidates["pool"])
    assert len(step.candidates["sent"]) == 2


def test_the_item_prompt_v4_asks_for_price_or_quantity_and_not_for_a_technical_sheet():
    """REQ-044: la instrucción del renglón v4 pide el precio o la cantidad ofrecida, en
    cualquier documento, y dice que una hoja técnica sola no alcanza; v1 y v2 siguen como
    estaban."""
    text = sheets.load_prompt("ficha_renglon")
    assert "el precio o la cantidad que el oferente ofrece" in text
    assert "Una hoja técnica" in text and "no alcanzan" in text
    assert "No decidís" in text and "no cumple" in text
    for old in ("ficha-renglon-v1.md", "ficha-renglon-v2.md"):
        assert "no alcanzan" not in sheets.PROMPTS_DIR.joinpath(old).read_text(encoding="utf-8")


def test_the_sheet_prompt_v2_asks_for_the_concrete_datum_and_abstention():
    """REQ-040: la instrucción v2 pide el dato concreto, trae ejemplos de pasaje de tema
    parecido que no responde y dice que sin respuesta la lista va vacía; la v1 no cambió."""
    text = sheets.PROMPTS_DIR.joinpath("ficha-v2.md").read_text(encoding="utf-8")
    assert "dato concreto" in text and "no se encontró" in text and "Ante la duda" in text
    assert text.count('{"pasajes": [], "sintesis": ""}') >= 2
    old = sheets.PROMPTS_DIR.joinpath("ficha-v1.md").read_text(encoding="utf-8")
    assert "dato concreto" not in old and old.count('{"pasajes": [], "sintesis": ""}') == 1
    assert sheets.load_prompt("ficha") == text


def test_a_found_row_never_stays_without_a_synthesis(offer, operator_user, script):
    """REQ-041 (T-135): si el modelo devuelve pasajes con la síntesis vacía, la fila lleva la
    síntesis neutra que dice dónde está la respuesta."""
    script.choose(pick(DECLARATION, synthesis="", when="declaración jurada"))
    row = entry_of(build(offer, operator_user), 1)
    assert row.outcome == om.Outcome.ENCONTRADO
    assert row.synthesis.startswith("El oferente responde en: ")
    assert not sheets.judgment_words(row.synthesis)


# --- Cotización de un renglón y copias idénticas (T-135, decisiones del responsable) -------------


def test_an_item_with_only_a_technical_sheet_is_not_quoted_but_shows_it(
        procedure, operator_user, fake_ai, script):
    """REQ-044 (T-136): una hoja técnica sola no es la cotización: aunque el modelo diga "si",
    el renglón no figura "cotizado" (queda sin cotización a la vista) pero la fila sigue
    mostrando la hoja que describe lo ofrecido."""
    offer = make_offer(procedure, operator_user, "Solo hoja", {
        "hoja.docx": ["Resma de papel A4, 75 g/m2, 500 hojas. Marca Ficticia."]},
        kinds={"hoja.docx": "tecnica"})
    script.choose(pick("Resma", when="RESMA"))
    sheet = build(offer, operator_user)
    row = entry_of(sheet, 6)
    assert row.quoted == "" and row.outcome == om.Outcome.ENCONTRADO
    assert row.fragments.get().text.startswith("Resma de papel A4, 75 g/m2")
    assert sheet.counts["sin_cotizacion_a_la_vista"] >= 1 and sheet.counts["cotizado"] == 0


def test_an_item_with_a_price_in_a_separate_sheet_is_quoted(procedure, operator_user, fake_ai,
                                                            script):
    """REQ-044: el precio en una planilla aparte, junto a una hoja técnica, da "cotizado" y
    la cita es la planilla."""
    offer = make_offer(procedure, operator_user, "Planilla aparte", {
        "hoja.docx": ["Resma de papel A4, 75 g/m2, 500 hojas. Marca Ficticia."],
        "planilla.pdf": ["Renglón 1 · 100 unidades · precio unitario $ 3.100"]},
        kinds={"hoja.docx": "tecnica", "planilla.pdf": "economica"})
    script.choose(pick("precio unitario", when="RESMA"))
    row = entry_of(build(offer, operator_user), 6)
    assert row.quoted == om.Quoted.COTIZADO
    assert row.fragments.get().passage.reading.document.file_name == "planilla.pdf"


def test_identical_passages_are_grouped_before_the_reranker(procedure, operator_user, fake_ai,
                                                            script):
    """REQ-039 (T-135, 2b): una copia idéntica de otro documento no ocupa un candidato: se
    puntúa y se manda una sola vez; la copia queda en el registro con `copy_of`."""
    text = "Declaro bajo juramento que estoy habilitado para contratar."
    offer = make_offer(procedure, operator_user, "Con copias", {
        "a.pdf": [text, "Otro texto distinto."], "b.pdf": [text.upper()]})
    script.choose(pick(DECLARATION, when="declaración jurada"))
    sheet = build(offer, operator_user)
    step = sheet.steps.filter(entry__requirement__number=1).get()
    copies = [c for c in step.candidates["pool"] if c["copy_of"]]
    assert len(copies) == 1 and len(step.candidates["sent"]) == 2
    assert len(script.calls[0]["blocks"]) == 2
    scored = [c for c in step.candidates["pool"] if c["score"] is not None]
    assert len(scored) == 2


# --- Ronda 2 de T-136 ---------------------------------------------------------------------------


def _passage(kind):
    from types import SimpleNamespace

    return SimpleNamespace(reading=SimpleNamespace(document=SimpleNamespace(kind=kind)))


@pytest.mark.parametrize("quoted, kinds, unread, expected", [
    ("si", ["economica"], False, om.Quoted.COTIZADO),
    ("si", ["tecnica", "economica"], False, om.Quoted.COTIZADO),
    ("si", ["tecnica"], False, ""),  # la hoja técnica sola no es la cotización
    ("si", [], False, ""),
    ("sin_precio", ["tecnica"], False, ""),
    ("sin_precio", [], False, ""),
    ("sin_precio", [], True, om.Quoted.NO_SE_PUDO_LEER),
    ("sin_precio", ["tecnica"], True, ""),
    ("no", [], False, om.Quoted.NO_COTIZADO),
    ("no", ["economica"], True, om.Quoted.NO_COTIZADO),  # la negativa expresa está a la vista
    ("no", [], True, om.Quoted.NO_SE_PUDO_LEER),
])
def test_the_state_of_an_item_is_separate_from_the_passages_it_shows(
        quoted, kinds, unread, expected):
    """REQ-044 (T-136): "cotizado" solo con precio o cantidad ofrecida; "no cotizado" solo si la
    oferta dice que no cotiza o su tabla de precios no lo trae; en los demás casos, sin
    cotización a la vista (en blanco), y con páginas sin leer y sin pasajes, "no se pudo
    leer"."""
    assert sheets.item_state(quoted, [_passage(k) for k in kinds], unread) == expected


def test_the_item_answer_accepts_the_three_states_and_nothing_else():
    """REQ-044 (T-136): el esquema y la validación aceptan si, sin_precio y no."""
    schema = sheets.build_schema(["P1"], True)
    assert schema["properties"]["cotizado"]["enum"] == ["si", "sin_precio", "no"]
    for value in ("si", "sin_precio", "no"):
        content = json.dumps({"cotizado": value, "pasajes": ["P1"], "sintesis": "x"})
        assert sheets.parse_answer(content, ["P1"], True)[2] == value
    bad = json.dumps({"cotizado": "quizás", "pasajes": [], "sintesis": ""})
    with pytest.raises(sheets.InvalidAnswer):
        sheets.parse_answer(bad, ["P1"], True)


def test_an_item_described_by_a_signed_spec_without_price_shows_it_without_quote(
        procedure, operator_user, fake_ai, script):
    """REQ-044 (T-136): un renglón con especificaciones firmadas y sin precio ni cantidad
    muestra el pasaje y queda "sin cotización a la vista", no "no cotizado"."""
    offer = make_offer(procedure, operator_user, "Con especificaciones", {
        "especificaciones.pdf": ["Renglón 1: resma de papel A4, marca Ficticia, 75 g/m2."]},
        kinds={"especificaciones.pdf": "tecnica"})
    script.choose(pick("marca Ficticia", quoted="sin_precio", when="RESMA"))
    row = entry_of(build(offer, operator_user), 6)
    assert row.quoted == "" and row.outcome == om.Outcome.ENCONTRADO
    assert row.fragments.get().text.startswith("Renglón 1: resma de papel A4, marca Ficticia")


def test_an_item_the_offer_says_it_does_not_quote_is_not_quoted_and_shows_the_proof(
        procedure, operator_user, fake_ai, script):
    """REQ-044 (T-136): con una tabla de precios en la que el renglón no figura, el modelo
    contesta "no": el renglón figura "no cotizado" y la tabla queda como fragmento."""
    offer = make_offer(procedure, operator_user, "Con tabla de precios", {
        "planilla.pdf": ["Planilla de precios. Renglón 2: cartucho, 30 unidades, $ 4.500."]},
        kinds={"planilla.pdf": "economica"})
    script.choose(pick("Planilla de precios", quoted="no", when="RESMA"))
    row = entry_of(build(offer, operator_user), 6)
    assert row.quoted == om.Quoted.NO_COTIZADO
    assert row.fragments.get().text.startswith("Planilla de precios")


def test_the_item_prompt_v4_has_the_three_answers_and_the_earlier_ones_are_untouched():
    """REQ-044 (T-136): la instrucción v4 distingue si, sin_precio y no, y dice que "no" es solo
    la negativa expresa o la tabla sin el renglón; v3 sigue como estaba."""
    text = sheets.load_prompt("ficha_renglon")
    assert sheets.settings.OFFERS_PROMPT_VERSIONS["ficha_renglon"] == "ficha-renglon-v4"
    for word in ('"si"', '"sin_precio"', '"no"', "expresamente", "No decidís"):
        assert word in text
    v3 = sheets.PROMPTS_DIR.joinpath("ficha-renglon-v3.md").read_text(encoding="utf-8")
    assert "sin_precio" not in v3 and "no alcanzan" in v3


def test_a_common_row_sends_eight_candidates_and_an_item_row_twelve(
        procedure, operator_user, fake_ai, script):
    """REQ-039 (T-136): las filas que no son de renglón vuelven a 8 candidatos; las de renglón
    conservan 12."""
    pages = [f"Texto número {n}." for n in range(1, 17)]
    offer = make_offer(procedure, operator_user, "Muchos", {"a.pdf": pages})
    fake_ai.reranker.scores = {f"número {n}.": 0.5 + n / 40 for n in range(1, 17)}
    script.choose(lambda requirement, blocks, number, messages: None)
    sheet = build(offer, operator_user)
    sizes = {c["messages"][-1]["content"].startswith("Renglón"): len(c["blocks"])
             for c in script.calls}
    assert sizes == {False: 8, True: 12}
    assert sheet.parameters["candidates_to_model"] == 8
    assert sheet.parameters["item_candidates_to_model"] == 12


def test_a_common_row_needs_the_minimum_reranker_score(procedure, operator_user, fake_ai, script,
                                                     settings):
    """REQ-040 (T-136): un pasaje por debajo del puntaje mínimo del reranker no llega al modelo
    en una fila común; si ninguno lo alcanza, la fila queda "no se encontró" sin preguntarle al
    modelo, y el registro conserva lo visto con su puntaje."""
    settings.OFFERS_MIN_RERANK_SCORE = 0.3
    offer = make_offer(procedure, operator_user, "Dos temas", {
        "a.pdf": ["Declaro bajo juramento que estoy habilitado.", "Otro tema de formularios."]})
    fake_ai.reranker.scores = {"Declaro": 0.9, "Otro tema": 0.29}
    script.choose(pick("Otro tema", "Declaro", when="declaración jurada"))
    sheet = build(offer, operator_user)
    first = script.calls[0]
    assert list(first["blocks"].values()) == ["Declaro bajo juramento que estoy habilitado."]
    step = sheet.steps.filter(entry__requirement__number=1).get()
    assert len(step.candidates["pool"]) == 2 and len(step.candidates["sent"]) == 1
    assert sorted(c["score"] for c in step.candidates["pool"]) == [0.29, 0.9]
    # Sin ningún pasaje por encima del mínimo: no se le pregunta al modelo.
    fake_ai.reranker.scores = {"Declaro": 0.1, "Otro tema": 0.29}
    before = len(script.calls)
    sheet = build(offer, operator_user)
    common_calls = [c for c in script.calls[before:]
                    if not c["messages"][-1]["content"].startswith("Renglón")]
    assert common_calls == []
    row = entry_of(sheet, 1)
    assert row.outcome == om.Outcome.NO_ENCONTRADO and not row.fragments.exists()
    assert sheet.parameters["min_rerank_score"] == 0.3


def test_an_item_row_does_not_use_the_minimum_reranker_score(
        procedure, operator_user, fake_ai, script, settings):
    """REQ-044 (T-136): las filas de renglón conservan sus candidatos aunque el puntaje sea
    bajo: la tabla de la oferta no se parece al encabezado del pliego."""
    settings.OFFERS_MIN_RERANK_SCORE = 0.3
    offer = make_offer(procedure, operator_user, "Tabla", {
        "tabla.pdf": ["1 Alimento 2700,00 kg 7.390,00"]})
    fake_ai.reranker.scores = {"Alimento": 0.05}
    script.choose(pick("Alimento", quoted="si", when="RESMA"))
    row = entry_of(build(offer, operator_user), 6)
    assert row.quoted == om.Quoted.COTIZADO and row.fragments.count() == 1


# --- T-146: búsqueda con el requisito reescrito como lo diría una oferta -------------------------

POLICY = ("Póliza de seguro de caución N° 0000-123. Tomador: Insumos Ficticios S.R.L. Asegurado: "
          "el organismo contratante. Suma asegurada: $ 5.045.030,00. Objeto: garantizar el "
          "mantenimiento de la oferta.")
POLICY_QUERY = ("póliza de seguro de caución, garantía de mantenimiento de la oferta, suma "
                "asegurada, vigencia")


def _by_query(monkeypatch, original, rewritten, rewritten_queries):
    """Doble del reranker que puntúa según la consulta: `original` y `rewritten` son
    `{marca del texto: puntaje}` para la consulta del pliego y para las consultas de
    `rewritten_queries`; lo que no figura puntúa 0,0. Devuelve la lista de consultas vistas."""
    from evaluon.ai import reranker as reranker_client

    calls = []

    def rerank(query, documents):
        table = rewritten if query in rewritten_queries else original
        calls.append(query)
        return [max([v for k, v in table.items() if k in d] or [0.0]) for d in documents]

    monkeypatch.setattr(reranker_client, "rerank", rerank)
    return calls


def test_the_rewritten_requirement_finds_the_passage_the_pliego_wording_misses(
        procedure, operator_user, fake_ai, script, settings, monkeypatch):
    """REQ-039 (T-146): la póliza no se parece a la cita del pliego (puntaje 0,09) pero sí al
    requisito dicho como lo diría una oferta (0,99): el pasaje queda con el mejor puntaje, pasa
    al modelo y los dos puntajes y la reescritura quedan en el registro de la ficha (P6)."""
    settings.OFFERS_MIN_RERANK_SCORE = 0.35
    offer = make_offer(procedure, operator_user, "Póliza", {
        "poliza.pdf": [POLICY, "Condiciones generales de la póliza: el asegurador paga."]})
    script.rewrite_with(lambda text: POLICY_QUERY if "garantía de mantenimiento" in text
                        else text)
    calls = _by_query(monkeypatch, {"Póliza de seguro": 0.092}, {"Póliza de seguro": 0.994},
                      [POLICY_QUERY])
    script.choose(pick("Póliza de seguro", when="garantía de mantenimiento"))
    sheet = build(offer, operator_user)
    row = entry_of(sheet, 3)
    assert row.outcome == om.Outcome.ENCONTRADO
    assert row.fragments.get().text == POLICY
    assert POLICY_QUERY in calls
    step = sheet.steps.filter(entry__requirement__number=3).get()
    candidate = next(c for c in step.candidates["pool"] if c["score"] > 0.9)
    assert (candidate["score_original"], candidate["score_rewrite"], candidate["score"]) == (
        0.092, 0.994, 0.994)
    rewrite = step.candidates["rewrite"]
    assert rewrite["query"] == POLICY_QUERY and rewrite["prompt_version"] == "reescritura-v1"
    assert rewrite["raw_output"] and rewrite["request"]["messages"][0]["content"] == (
        sheets.load_prompt("reescritura"))
    assert sheet.prompt_versions["reescritura"] == "reescritura-v1"


def test_the_original_score_still_counts_when_it_is_the_better_one(
        procedure, operator_user, fake_ai, script, settings, monkeypatch):
    """REQ-039 (T-146): el pasaje queda con el mejor de los dos puntajes, también cuando es el
    de la consulta original: la reescritura no empeora lo que ya se encontraba."""
    settings.OFFERS_MIN_RERANK_SCORE = 0.35
    offer = make_offer(procedure, operator_user, "Nota", {
        "nota.pdf": ["Nota: la oferta se mantiene vigente por 60 días desde la apertura."]})
    script.rewrite_with(lambda text: "formulario de la oferta" if "validez" in text else text)
    _by_query(monkeypatch, {"Nota": 0.981}, {"Nota": 0.2}, ["formulario de la oferta"])
    script.choose(pick("Nota", when="validez"))
    sheet = build(offer, operator_user)
    step = sheet.steps.filter(entry__requirement__number=5).get()
    [candidate] = step.candidates["pool"]
    assert (candidate["score_original"], candidate["score_rewrite"], candidate["score"]) == (
        0.981, 0.2, 0.981)
    assert entry_of(sheet, 5).outcome == om.Outcome.ENCONTRADO


def test_a_rewrite_without_the_requested_shape_is_dropped_and_recorded(
        offer, operator_user, fake_ai, script):
    """REQ-040 (T-146): si el modelo no devuelve la consulta pedida, la búsqueda sigue solo con
    la cita del pliego; la ficha se arma igual y la anomalía queda en su registro."""
    script.rewrite_with(lambda text: '{"otra": "cosa"}')
    script.choose(pick(DECLARATION, when="declaración jurada"))
    sheet = build(offer, operator_user)
    assert entry_of(sheet, 1).outcome == om.Outcome.ENCONTRADO
    step = sheet.steps.filter(entry__requirement__number=1).first()
    assert step.candidates["rewrite"]["query"] == ""
    assert step.candidates["rewrite"]["anomaly"]
    assert any(a["type"] == sheets.ANOMALY_REWRITE and a["requirement"] == 1
               for a in sheet.anomalies)
    assert all(c["score_rewrite"] is None for c in step.candidates["pool"])


def test_item_rows_are_not_rewritten(offer, operator_user, fake_ai, script):
    """REQ-044 (T-146): las filas de renglón buscan como antes, sin reescritura; solo se
    reescriben las filas comunes."""
    sheet = build(offer, operator_user)
    common = [e for e in sheet.entries.all() if not sheets.is_item_row(e.requirement)]
    assert common and len(script.rewrites) == len(common)
    assert not any("Renglón" in r["requirement"] for r in script.rewrites)
    step = sheet.steps.filter(entry__requirement__number=6).first()
    assert "rewrite" not in step.candidates


def test_the_rewrite_instructions_are_versioned_and_teach_the_form_of_real_offers():
    """REQ-040 (T-146): las instrucciones de la reescritura tienen versión registrada, piden
    el formato y sus ejemplos (inventados) usan la forma de lo que responde una oferta."""
    from evaluon import settings as defaults

    assert defaults.OFFERS_PROMPT_VERSIONS["reescritura"] == "reescritura-v1"
    text = sheets.load_prompt("reescritura")
    for form in ("póliza de seguro de caución", "nota de la empresa", "declaro bajo juramento",
                 "constancia", "formulario"):
        assert form in text
    assert '{"consulta"' in text


# Puntajes del reranker real (bge-reranker-v2-m3, T-146) sobre textos inventados con la forma de
# lo que responden las ofertas del caso-00 (pólizas de caución, notas de la empresa, formularios
# del Portal, declaraciones juradas, constancias, pagarés): `(original, reescrito)` es el puntaje
# contra la cita del pliego y contra su reescritura con las instrucciones `reescritura-v1`; el
# del pasaje es el mayor de los dos.
CALIBRATION = [
    ("responde", "Póliza de seguro de caución N° 0000-123. Tomador: Insumos Ficticios S.R.L. "
                 "Suma asegurada: $ 5.045.030,00. Objeto: mantenimiento de la oferta.",
     0.092, 0.994),
    ("responde", "Se adjunta póliza de caución en garantía de mantenimiento de oferta, por el 5 % "
                 "del monto cotizado.", 0.897, 0.785),
    ("responde", "Constancia de inscripción en el registro de proveedores, número 000123, "
                 "estado: activo.", 0.551, 0.996),
    ("responde", "Se acompaña constancia de inscripción en AFIP, CUIT 30-00000000-0, con "
                 "impuestos activos.", 0.016, 0.564),
    ("responde", "Declaración jurada de aptitud para contratar. Declaro bajo juramento que no me "
                 "encuentro comprendido en las causales de inhabilidad.", 0.978, 1.000),
    ("responde", "Nota de la empresa: nos comprometemos a entregar los bienes en un plazo de "
                 "diez días corridos desde la orden de compra.", 0.996, 1.000),
    ("responde", "Formulario de oferta. La oferta mantiene su validez por sesenta días corridos "
                 "desde la fecha de apertura.", 0.999, 1.000),
    ("responde", "Detalle de la oferta (Portal). Moneda: peso argentino. Los precios incluyen "
                 "IVA y demás impuestos.", 0.901, 0.979),
    ("responde", "Documento Nacional de Identidad de Pérez, Juan (ficticio). Copia certificada, "
                 "firmada por el titular.", 0.471, 0.356),
    ("responde", "Pagaré a la vista sin protesto por la suma de $ 1.000.000,00, librado a favor "
                 "del organismo.", 0.954, 0.986),
    ("mismo tema", "La garantía de cumplimiento del contrato será del diez por ciento del monto "
                   "adjudicado.", 0.002, 0.022),
    ("mismo tema", "Condiciones generales de la póliza: el asegurador se obliga a pagar al "
                   "asegurado.", 0.000, 0.038),
    ("mismo tema", "Factura N° 0001-00001234. Concepto: premio de la póliza. Importe: $ 52.300,00.",
     0.000, 0.022),
    ("mismo tema", "El registro de proveedores se encuentra abierto durante todo el año.",
     0.010, 0.027),
    ("mismo tema", "Declaración jurada de domicilio: constituyo domicilio especial en la calle "
                   "Ficticia 123.", 0.001, 0.002),
    ("mismo tema", "Los plazos de este formulario se cuentan en días hábiles administrativos.",
     0.114, 0.328),
    ("mismo tema", "La prórroga de la validez de la oferta se considerará aceptada si el "
                   "oferente no manifiesta lo contrario.", 0.273, 0.077),
    ("mismo tema", "La garantía podrá constituirse mediante pagaré, póliza de caución o depósito "
                   "bancario.", 0.173, 0.068),
    ("mismo tema", "El firmante declara conocer las condiciones del pliego y aceptarlas.",
     0.058, 0.010),
    ("ajeno", "Renglón 3: alimento balanceado, 250,00 kg, precio unitario $ 12.000,00.",
     0.000, 0.000),
    ("ajeno", "Total ofertado: $ 100.900.600,00. Cantidad de alternativas presentadas: 6.",
     0.001, 0.000),
]
# Un pasaje que ningún corte separa (nombra las causales del pliego sin que el oferente ofrezca
# nada; puntúa 0,58 con las dos consultas): lo decide el modelo, no el corte.
INSEPARABLE = ("Las causales de inhabilidad para contratar están enumeradas en el reglamento "
               "del régimen de contrataciones.", 0.569, 0.580)


def test_the_minimum_score_separates_answers_from_same_topic_non_answers():
    """REQ-040 (T-146): con el puntaje mínimo de `settings.py` (recalibrado con el mejor de los
    dos puntajes) los pasajes que responden quedan por encima y los del mismo tema que no
    responden, por debajo, con margen; solo el que ningún corte separa pasa al modelo."""
    from evaluon import settings as defaults

    minimum = defaults.OFFERS_MIN_RERANK_SCORE
    best = {kind: [max(a, b) for k, _, a, b in CALIBRATION if k == kind]
            for kind in ("responde", "mismo tema", "ajeno")}
    assert min(best["responde"]) > minimum + 0.1
    assert max(best["mismo tema"] + best["ajeno"]) < minimum
    assert max(INSEPARABLE[1:]) > minimum  # lo que queda es del modelo
    # La reescritura sube lo que la cita sola dejaba por debajo (T-136: 32 de 52 casi nulos).
    lifted = [t for k, t, a, b in CALIBRATION if k == "responde" and a < minimum <= b]
    assert len(lifted) == 2


def test_the_calibrated_minimum_lets_through_what_answers_and_nothing_else(
        procedure, operator_user, fake_ai, script, settings, monkeypatch):
    """REQ-040 (T-146): de punta a punta con el mínimo calibrado: al modelo llegan solo pasajes
    que responden, ninguno de los del mismo tema que no responden ni de los ajenos."""
    from evaluon import settings as defaults

    settings.OFFERS_MIN_RERANK_SCORE = defaults.OFFERS_MIN_RERANK_SCORE
    rewritten_query = "consulta reescrita de prueba"
    offer = make_offer(procedure, operator_user, "Calibración",
                       {"a.pdf": [t for _, t, _, _ in CALIBRATION]})
    _by_query(monkeypatch, {t[:30]: a for _, t, a, _ in CALIBRATION},
              {t[:30]: b for _, t, _, b in CALIBRATION}, [rewritten_query])
    script.rewrite_with(lambda text: rewritten_query)
    script.choose(lambda requirement, blocks, number, messages: None)
    build(offer, operator_user)
    first = next(c for c in script.calls if not c["messages"][-1]["content"]
                 .startswith("Renglón"))
    sent = set(first["blocks"].values())
    answers = {t for k, t, _, _ in CALIBRATION if k == "responde"}
    assert sent and sent <= answers
    assert len(sent) == min(8, len(answers))
