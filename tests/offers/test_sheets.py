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
    pages = [f"Texto número {n}." for n in range(1, 13)]
    offer = make_offer(procedure, operator_user, "Muchos", {"a.pdf": pages})
    fake_ai.reranker.scores = {f"número {n}.": n / 20 for n in range(1, 13)}
    script.choose(pick("número 12."))
    sheet = build(offer, operator_user)
    blocks = script.calls[0]["blocks"]
    assert len(blocks) == 8
    assert list(blocks.values())[0] == "Texto número 12."
    assert list(blocks.values())[-1] == "Texto número 5."
    step = sheet.steps.filter(entry__requirement__number=1).get()
    assert len(step.candidates["pool"]) == 12 and len(step.candidates["sent"]) == 8


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
    assert sheet.counts["not_found"] + sheet.counts["found"] == sheet.counts["entries"] == 8


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


def test_a_synthesis_that_keeps_the_judgment_is_left_empty_with_its_anomaly(
        offer, operator_user, script):
    """REQ-041: si vuelve a fallar, la fila queda sin síntesis (conserva sus fragmentos) y la
    anomalía en el registro; ninguna síntesis guardada tiene palabras de juicio."""
    script.choose(pick(DECLARATION, synthesis="La oferta cumple.", when="declaración jurada"))
    sheet = build(offer, operator_user)
    row = entry_of(sheet, 1)
    assert row.synthesis == "" and row.fragments.count() == 1
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
    assert detail["prompt_versions"] == {"ficha": "ficha-v1", "ficha_renglon": "ficha-renglon-v1"}
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
    assert script.calls[-1]["schema"]["required"] == ["cotizado", "pasajes", "sintesis"]


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
    """REQ-044: la ficha indica si la oferta trae documentación técnica: por un documento
    clasificado técnico o por fragmentos en una fila técnica."""
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
    assert sheet.technical_documents == {"present": True, "documents": [],
                                         "from_fragments": True}


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
