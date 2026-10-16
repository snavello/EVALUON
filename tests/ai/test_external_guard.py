"""Puerta de filtrado de lo reservado (T-290; REQ-121; ADR-0067; plan 016, "Un solo punto de
filtrado de lo reservado"; umbral 19).

Una hoja de compliance **inventada** (`tests/ai/data/compliance-inventada/hoja.txt`, con la palabra
clave `ZORVANTIQ` en cada párrafo) se carga como documento `compliance` de una oferta del caso
chico. Con el uso externo encendido y el doble del cliente (`fake_external`), ningún pedido que
llegue al cliente o al registro contiene un párrafo de la hoja, ocho palabras seguidas de ella ni
la palabra clave; los requisitos externos (P9) quedan en local; un tipo desconocido, un documento
sin clasificar con un párrafo de la hoja, una respuesta de la Comisión y un informe técnico no
salen. Sin red: la suite bloquea toda llamada real (`no_real_external_calls`).

Todo el texto es público e inventado (P4).
"""

import copy
import dataclasses
import json
import pickle
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.db import connection

from evaluon.ai.external import client, guard, ledger
from evaluon.assessment import externals, grounds
from evaluon.assessment import models as am
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.offers import models as om
from evaluon.tenders import models as tm
from tests.conftest import external_payload
from tests.offers.conftest import (  # noqa: F401 - fixtures de la 008 y la 003
    evaluator_user,
    expected,
    make_offer,
    matrix,
    operator_user,
    procedure,
)

pytestmark = pytest.mark.django_db

DATA = Path(__file__).resolve().parent / "data" / "compliance-inventada"
KEYWORD = "ZORVANTIQ"
MEASUREMENT = "T-290-prueba"

ECONOMIC = ("Propuesta económica del oferente de prueba: renglón 1, resma de papel A4 de 80 "
            "gramos, cien unidades, precio unitario de tres mil pesos con impuestos incluidos.")
TECHNICAL = ("Documentación técnica: la resma ofrecida es de papel blanco, de 500 hojas por "
             "paquete, apta para impresoras láser y de chorro de tinta.")
REPORT = ("Informe técnico del área usuaria: el producto ofrecido en el renglón 1 cumple las "
          "especificaciones del pliego según la muestra revisada.")
NOTE = "Nota del oferente, sin clasificar, que copió por error un párrafo de su hoja: "


def sheet_paragraphs():
    # Con `core.autocrlf` la copia de trabajo puede traer CRLF: los párrafos se separan igual.
    text = (DATA / "hoja.txt").read_text(encoding="utf-8").replace("\r\n", "\n")
    return [part.strip() for part in text.split("\n\n") if part.strip()]


# Los requisitos del caso chico que el modelo local marca `externo` (como el guion de
# `tests/assessment/test_compliance_sheet.py`); el del libre deuda entra además al catálogo.
FLAGGED = ("registro de proveedores", "declaración jurada", "garantía de mantenimiento")
DEBT = "libre deuda"


@pytest.fixture
def debt_in_catalog(monkeypatch):
    """El requisito del libre deuda del caso chico entra al catálogo de los externos (como en
    `tests/assessment/test_externals.py`): el caso chico no trae ninguno que lo reconozca solo."""
    extra = externals.ExternalCheck("libre_deuda", "constancia fiscal de deuda",
                                    re.compile(DEBT))
    monkeypatch.setattr(externals, "CATALOG", (*externals.CATALOG, extra))


@pytest.fixture
def case(matrix, operator_user, fake_ai, debt_in_catalog):
    """El caso chico con una oferta que trae la hoja inventada (tipo `compliance`), una copia sin
    clasificar de uno de sus párrafos, un informe técnico del área y dos documentos públicos."""
    sheet = sheet_paragraphs()
    offer = make_offer(matrix.procedure, operator_user, "Oferente de la hoja inventada", {
        "economica.pdf": [ECONOMIC],
        "tecnica.pdf": [TECHNICAL],
        "hoja-compliance.pdf": sheet,
        "copia-sin-clasificar.pdf": [NOTE + sheet[2]],
        "informe-tecnico.pdf": [REPORT],
    }, kinds={"economica.pdf": "economica", "tecnica.pdf": "tecnica",
              "hoja-compliance.pdf": "compliance", "informe-tecnico.pdf": "informe_tecnico"})
    documents = {d.file_name: d for d in offer.documents.all()}
    return SimpleNamespace(procedure=matrix.procedure, version=matrix.version, offer=offer,
                           documents=documents, sheet=sheet)


def text_of(document):
    return document.readings.get().canonical_text


def ask(case, pieces, *, custom_id="pedido-1", cell=None, offer=True, system=None,
        measurement=MEASUREMENT, stage="verificador", instruction_version="verificador-v1"):
    """Arma un pedido del verificador con la puerta (como lo hará T-299)."""
    return guard.build(
        stage=stage, custom_id=custom_id, procedure=case.procedure,
        offer=case.offer if offer else None, cell=cell,
        system=system or guard.instruction("Instrucción sintética del verificador de citas."),
        messages=[("user", pieces)], max_tokens=600, run_kind="assessment", run_id=1,
        instruction_name="verificador", instruction_version=instruction_version,
        instruction_sha256="0" * 64, measurement=measurement)


def requirement_text(requirement):
    return grounds.requirement_text(requirement).text


def requirement_is_external(requirement):
    return bool(externals.match(grounds.requirement_text(requirement).context))


def catalog_requirement(case):
    return next(r for r in case.version.requirements.order_by("number")
                if requirement_is_external(r))


def flagged_by_the_model(requirement):
    return any(needle in requirement_text(requirement) for needle in FLAGGED)


def public_requirement(case):
    return next(r for r in case.version.requirements.order_by("number")
                if not requirement_is_external(r) and not flagged_by_the_model(r))


def external_requests():
    return list(AuditEvent.objects.filter(event_type=EventType.EXTERNAL_REQUEST).order_by("pk"))


def all_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from all_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from all_strings(item)


def assert_nothing_of_the_sheet(value, sheet):
    """Ningún texto de `value` tiene la palabra clave, un párrafo de la hoja ni ocho palabras
    seguidas de uno (con la normalización de la puerta)."""
    sheet_prints = set().union(*(guard.shingles(p) for p in sheet))
    for text in all_strings(value):
        assert KEYWORD.lower() not in text.lower()
        assert not any(paragraph in text for paragraph in sheet)
        assert not guard.shingles(text) & sheet_prints


# --- La hoja inventada -----------------------------------------------------------------------


def test_the_invented_sheet_marks_every_paragraph():
    """REQ-121: cada párrafo de la hoja inventada lleva la palabra clave y tiene al menos veinte
    palabras (para que la huella lo vea)."""
    sheet = sheet_paragraphs()
    assert len(sheet) >= 5
    for paragraph in sheet:
        assert KEYWORD in paragraph
        assert len(guard.words(paragraph)) >= 20


# --- Lista permitida -------------------------------------------------------------------------


def test_the_allow_lists_are_the_ones_of_the_adr():
    """REQ-121 (ADR-0067, regla 1): la lista permitida es exactamente la del ADR, escrita a mano;
    `compliance` y el informe técnico nunca están, y el dictamen tampoco (no figura en la
    lista)."""
    assert guard.TENDER_KINDS_ALLOWED == {
        "pliego", "anexo", "especificaciones", "circular_modificatoria", "circular_aclaratoria",
        "respuesta_consulta"}
    assert guard.OFFER_KINDS_ALLOWED == {
        "economica", "tecnica", "garantia", "anexo_tecnico", "otro", ""}
    assert "compliance" not in guard.OFFER_KINDS_ALLOWED | guard.TENDER_KINDS_ALLOWED
    assert "informe_tecnico" not in guard.OFFER_KINDS_ALLOWED
    assert "dictamen" not in guard.TENDER_KINDS_ALLOWED
    assert guard.TENDER_KINDS_ALLOWED <= set(tm.DocumentKind.values)
    assert guard.OFFER_KINDS_ALLOWED - {""} <= set(om.DocumentKind.values)
    assert guard.ALLOWED_SOURCES == {"instruccion", "pliego", "oferta", "requisito", "portal"}


def test_public_documents_of_the_offer_and_the_tender_can_go_out(case, fake_external):
    """REQ-121: lo público (documentos económico y técnico de la oferta, el pliego, el requisito
    y un dato del Portal) pasa la puerta y llega al cliente tal como se armó."""
    fake_external.enable()
    tender = case.procedure.documents.filter(kind="pliego").first()
    requirement = public_requirement(case)
    pieces = [guard.instruction("Requisito: "),
              guard.requirement(requirement, requirement_text(requirement)),
              guard.instruction("\nPliego: "), guard.tender_document(tender, "Objeto público."),
              guard.instruction("\nOferta: "),
              guard.offer_document(case.documents["economica.pdf"], ECONOMIC),
              guard.offer_document(case.documents["tecnica.pdf"], TECHNICAL),
              guard.portal("Dato del Portal: oferta presentada el 10/10/2026.")]
    admitted = ask(case, pieces, cell=guard.Cell(
        requirement, group_documents=[case.documents["economica.pdf"]],
        cited_documents=[case.documents["economica.pdf"]]))
    assert isinstance(admitted, guard.Admitted), getattr(admitted, "reasons", None)
    assert admitted.payload.messages[0][1] == "".join(p.text for p in pieces)
    assert admitted.payload.requirement_id == requirement.pk
    assert admitted.filter["motivos"] == []
    sent = ledger.send([admitted], measurement=MEASUREMENT)
    assert sent.answers["pedido-1"].ok
    assert fake_external.batches[0][0] is admitted.payload


# --- El caso de la hoja (umbral 19) ----------------------------------------------------------


def test_nothing_of_the_compliance_sheet_leaves_with_the_external_use_on(case, fake_external):
    """REQ-121 (umbral 19): con la hoja cargada y el uso externo encendido, se pide verificar cada
    requisito con cada documento de la oferta. Ningún pedido que llega al cliente ni ningún hecho
    del registro contiene un párrafo de la hoja, ocho palabras seguidas de ella ni la palabra
    clave; la hoja, la copia sin clasificar y el informe técnico no salen; los requisitos externos
    quedan en local (ningún pedido suyo sale), comprobado en el registro."""
    fake_external.enable()
    requirements = list(case.version.requirements.order_by("number"))
    catalog = {r.pk for r in requirements if requirement_is_external(r)}
    flagged = {r.pk for r in requirements if flagged_by_the_model(r)}
    external = catalog | flagged
    assert catalog and flagged and len(requirements) > len(external)
    admitted, blocked = [], []
    for requirement in requirements:
        for name, document in sorted(case.documents.items()):
            decision = ask(case, [
                guard.requirement(requirement, requirement_text(requirement)),
                guard.instruction("\n\nOración citada de la oferta:\n"),
                guard.offer_document(document, text_of(document))],
                custom_id=f"r{requirement.pk}-d{document.pk}",
                cell=guard.Cell(requirement, external_flagged=requirement.pk in flagged,
                                group_documents=[document], cited_documents=[document]))
            (blocked if decision.blocked else admitted).append((requirement, name, decision))
    sent = ledger.send([d for _, _, d in admitted], measurement=MEASUREMENT)

    # Lo que llegó al cliente.
    reached = [p for batch in fake_external.batches for p in batch]
    assert len(reached) == len(admitted) > 0
    for payload in reached:
        assert_nothing_of_the_sheet(payload.to_params(), case.sheet)
    # Lo que quedó en el registro: un hecho por pedido, ninguno con la hoja.
    events = external_requests()
    assert len(events) == len(admitted) + len(blocked)
    for event in events:
        assert_nothing_of_the_sheet(event.detail, case.sheet)
    # Ningún documento reservado ni el informe técnico salió, con ningún requisito.
    for requirement, name, decision in admitted:
        assert name in ("economica.pdf", "tecnica.pdf"), name
        assert requirement.pk not in external
        assert sent.answers[decision.custom_id].ok
    by_name = {}
    for requirement, name, decision in blocked:
        by_name.setdefault(name, []).append(decision)
    assert all({"documento_compliance", "celda_con_compliance", "huella_compliance"}
               <= set(d.reasons) for d in by_name["hoja-compliance.pdf"])
    assert all("huella_compliance" in d.reasons for d in by_name["copia-sin-clasificar.pdf"])
    assert all("informe_tecnico" in d.reasons for d in by_name["informe-tecnico.pdf"])
    # Los requisitos externos: ningún pedido suyo salió, todos quedaron en local.
    for event in events:
        if event.detail["requisito"] in external:
            assert event.detail["resultado"] == "bloqueado"
            assert event.detail["texto_enviado"] is None
    for requirement, name, decision in blocked:
        if requirement.pk in catalog:
            assert "requisito_externo_catalogo" in decision.reasons
        if requirement.pk in flagged:
            assert "requisito_externo_modelo" in decision.reasons


# --- Los cuatro casos de bloqueo --------------------------------------------------------------


def test_an_unknown_document_kind_does_not_leave(case, fake_external):
    """REQ-121 (ADR-0067, regla 1): un tipo que no está en la lista no sale; también uno nuevo
    que aparezca mañana en el modelo de datos, y el dictamen del pliego."""
    fake_external.enable()
    document = case.documents["economica.pdf"]
    with connection.cursor() as cursor:  # dentro de la transacción de la prueba: se deshace
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cursor.execute("ALTER TABLE offers_document DROP CONSTRAINT offers_document_kind_valid")
    om.Document.objects.filter(pk=document.pk).update(kind="tipo_nuevo")
    decision = ask(case, [guard.offer_document(document, ECONOMIC)])
    assert decision.blocked and decision.reasons == ("tipo_no_permitido",)

    dictamen = tm.Document.objects.create(
        procedure=case.procedure, kind="dictamen", title="Dictamen", file_name="dictamen.pdf",
        file_format="pdf", file_size=1, file_sha256="a" * 64, loaded_by=document.loaded_by)
    decision = ask(case, [guard.tender_document(dictamen, "Dictamen de evaluación.")],
                   custom_id="pedido-2", offer=False)
    assert decision.blocked and decision.reasons == ("tipo_no_permitido",)
    assert fake_external.batches == [] and fake_external.messages == []


def test_an_unclassified_document_with_a_sheet_paragraph_does_not_leave(case, fake_external):
    """REQ-121 (ADR-0067, regla 3): un documento sin clasificar (tipo permitido) que copia un
    párrafo de la hoja se bloquea entero por la huella."""
    fake_external.enable()
    document = case.documents["copia-sin-clasificar.pdf"]
    assert document.kind == ""
    decision = ask(case, [guard.offer_document(document, text_of(document))])
    assert decision.blocked and decision.reasons == ("huella_compliance",)
    assert decision.filter["huellas"]["coincidencias"] > 0
    assert decision.filter["huellas"]["documentos_compliance"] == [
        case.documents["hoja-compliance.pdf"].pk]


def test_eight_words_of_the_sheet_are_enough_to_block(case, fake_external):
    """REQ-121 (ADR-0067, regla 3): ocho palabras seguidas de un párrafo de la hoja, sin la
    palabra clave, con otras tildes y mayúsculas y en medio de texto público, bloquean el pedido;
    siete no (la secuencia es de ocho palabras)."""
    fake_external.enable()
    words = case.sheet[3].split()
    start = words.index("aparece")
    eight = " ".join(words[start:start + 8])
    assert KEYWORD not in eight and len(guard.words(eight)) == 8
    seven = " ".join(words[start:start + 7])
    document = case.documents["economica.pdf"]
    shouted = eight.upper().replace("E", "É")
    decision = ask(case, [guard.offer_document(document, f"{ECONOMIC} {shouted} fin.")])
    assert decision.blocked and decision.reasons == ("huella_compliance",)
    decision = ask(case, [guard.offer_document(document, f"{ECONOMIC} {seven} fin.")],
                   custom_id="pedido-2")
    assert isinstance(decision, guard.Admitted)


def test_a_commission_answer_does_not_leave(case, fake_external):
    """REQ-121 (ADR-0067, regla 2): una respuesta de la Comisión nunca sale, aunque no traiga
    nada de la hoja."""
    fake_external.enable()
    decision = ask(case, [guard.instruction("Respuesta de la Comisión: "),
                          guard.commission_answer("Sí, la póliza fue validada.", ref=7)])
    assert decision.blocked and decision.reasons == ("respuesta_comision",)
    assert "respuesta_comision" in decision.filter["exclusiones"]
    assert fake_external.batches == [] and fake_external.messages == []


def test_the_technical_report_does_not_leave(case, fake_external):
    """REQ-121 (ADR-0067, regla 2): el informe técnico del área no sale, ni declarado como tal ni
    como documento de la oferta de ese tipo."""
    fake_external.enable()
    decision = ask(case, [guard.technical_report(REPORT)])
    assert decision.blocked and decision.reasons == ("informe_tecnico",)
    document = case.documents["informe-tecnico.pdf"]
    decision = ask(case, [guard.offer_document(document, text_of(document))],
                   custom_id="pedido-2")
    assert decision.blocked and decision.reasons == ("informe_tecnico",)
    assert fake_external.batches == [] and fake_external.messages == []


def test_the_compliance_sheet_itself_does_not_leave(case, fake_external):
    """REQ-121 (ADR-0067, regla 1): la hoja no sale por su tipo (y además por su huella)."""
    fake_external.enable()
    document = case.documents["hoja-compliance.pdf"]
    decision = ask(case, [guard.offer_document(document, text_of(document))])
    assert decision.blocked
    assert decision.reason == "documento_compliance"
    assert set(decision.reasons) == {"documento_compliance", "huella_compliance"}


# --- Requisitos externos y celdas -------------------------------------------------------------


def test_an_external_requirement_stays_local_even_with_the_sheet_loaded(case, fake_external):
    """REQ-121 (ADR-0067, regla 2; P9): un requisito que depende de una consulta externa (por el
    catálogo) no sale aunque la hoja esté cargada y el texto sea público."""
    fake_external.enable()
    requirement = catalog_requirement(case)
    document = case.documents["economica.pdf"]
    decision = ask(case, [guard.requirement(requirement, requirement_text(requirement)),
                          guard.offer_document(document, ECONOMIC)],
                   cell=guard.Cell(requirement, group_documents=[document],
                                   cited_documents=[document]))
    assert decision.blocked and decision.reasons == ("requisito_externo_catalogo",)
    assert fake_external.batches == []


def test_a_requirement_marked_external_by_the_model_stays_local(case, fake_external):
    """REQ-121 (P9): la marca `externo` del modelo en la celda, o una ya guardada en un resultado
    del par, deja el requisito en local."""
    fake_external.enable()
    requirement = public_requirement(case)
    document = case.documents["economica.pdf"]
    pieces = [guard.requirement(requirement, requirement_text(requirement)),
              guard.offer_document(document, ECONOMIC)]
    cell = guard.Cell(requirement, group_documents=[document], cited_documents=[document])
    assert isinstance(ask(case, pieces, cell=cell), guard.Admitted)
    flagged = dataclasses.replace(cell, external_flagged=True)
    decision = ask(case, pieces, cell=flagged, custom_id="pedido-2")
    assert decision.blocked and decision.reasons == ("requisito_externo_modelo",)

    request = am.Request.objects.create(
        procedure=case.procedure, matrix_version=case.version, offers=[case.offer.pk],
        requirements=None, cause=am.Cause.MATRIZ, requested_by=document.loaded_by)
    run = am.Run.objects.create(
        request=request, offer=case.offer, matrix_version=case.version, number=1,
        channel=am.Channel.SCREEN, documents=[], norms={}, models_used={}, parameters={},
        prompt_versions={})
    am.Result.objects.create(run=run, offer=case.offer, requirement=requirement,
                             outcome=am.Outcome.NO_DETERMINADO, doubt=am.Doubt.EXTERNO,
                             explanation="Falta la hoja de compliance.")
    decision = ask(case, pieces, cell=cell, custom_id="pedido-3")
    assert decision.blocked and decision.reasons == ("requisito_externo_modelo",)


def test_a_cell_whose_quote_comes_from_the_sheet_does_not_leave(case, fake_external):
    """REQ-121 (ADR-0067, regla 2): una celda cuya cita o cuyo grupo salió de la hoja no sale,
    aunque el texto armado sea solo de documentos públicos."""
    fake_external.enable()
    requirement = public_requirement(case)
    public = case.documents["economica.pdf"]
    sheet = case.documents["hoja-compliance.pdf"]
    pieces = [guard.offer_document(public, ECONOMIC)]
    for cell in (guard.Cell(requirement, group_documents=[public], cited_documents=[sheet]),
                 guard.Cell(requirement, group_documents=[public, sheet],
                            cited_documents=[public])):
        decision = ask(case, pieces, cell=cell)
        assert decision.blocked and decision.reasons == ("celda_con_compliance",)


def test_a_document_of_another_offer_does_not_leave(case, operator_user):
    """REQ-121: un documento tiene que ser de la oferta del pedido; uno de otra oferta no sale,
    ni uno de una oferta en un pedido que no dice de qué oferta es."""
    other = make_offer(case.procedure, operator_user, "Otro oferente",
                       {"otra.pdf": [ECONOMIC]}, kinds={"otra.pdf": "economica"})
    document = other.documents.get()
    decision = ask(case, [guard.offer_document(document, ECONOMIC)])
    assert decision.blocked and decision.reasons == ("documento_de_otra_oferta",)
    decision = ask(case, [guard.offer_document(case.documents["economica.pdf"], ECONOMIC)],
                   offer=False, custom_id="pedido-2")
    assert decision.blocked and decision.reasons == ("documento_de_otra_oferta",)


def test_a_sheet_without_a_reading_blocks_every_request_of_its_procedure(case, operator_user):
    """REQ-121 (ADR-0067, regla 3): una hoja sin lectura no se puede comparar: la puerta falla
    cerrada y no deja salir nada del procedimiento hasta que se lea."""
    sheet = om.Document.objects.create(
        offer=case.offer, title="Hoja nueva", file_name="hoja-nueva.pdf", file_format="pdf",
        file_size=1, file_sha256="b" * 64, loaded_by=operator_user, kind="compliance")
    decision = ask(case, [guard.offer_document(case.documents["economica.pdf"], ECONOMIC)])
    assert decision.blocked and decision.reasons == ("hoja_sin_lectura",)
    assert decision.filter["huellas"]["sin_lectura"] == [sheet.pk]


# --- Qué se registra al bloquear --------------------------------------------------------------


def test_a_blocked_request_is_recorded_without_text_and_returns_the_anomaly(case, fake_external):
    """REQ-121 y REQ-122 (ADR-0067, regla 4): un pedido bloqueado no sale, queda `bloqueado` en el
    registro sin texto (solo el motivo y el filtro) y la etapa recibe `externo_bloqueado`."""
    fake_external.enable()
    document = case.documents["hoja-compliance.pdf"]
    decision = ask(case, [guard.offer_document(document, text_of(document))])
    assert decision.anomaly == "externo_bloqueado"
    event = AuditEvent.objects.get(pk=decision.event_id)
    assert event.event_type == EventType.EXTERNAL_REQUEST
    assert event.outcome == Outcome.REJECTED
    detail = event.detail
    assert detail["resultado"] == "bloqueado"
    assert detail["motivo"] == "documento_compliance"
    assert detail["texto_enviado"] is None and detail["huella_pedido"] is None
    assert detail["respuesta"] is None and detail["costo_usd"] == 0
    assert detail["filtro"]["motivos"] and detail["filtro"]["version"] == guard.VERSION
    assert detail["procedimiento"] == case.procedure.pk and detail["oferta"] == case.offer.pk
    assert_nothing_of_the_sheet(detail, case.sheet)
    assert fake_external.batches == [] and fake_external.messages == []


def test_text_without_its_origin_is_a_programming_error(case):
    """REQ-121: cada texto entra con el documento del que sale; un texto suelto no se acepta."""
    with pytest.raises(TypeError, match="origen"):
        ask(case, ["Texto sin origen."])
    with pytest.raises(TypeError, match="origen"):
        ask(case, [guard.instruction("x")], system="Sistema suelto.")
    assert external_requests() == []


def test_the_ledger_only_sends_what_the_guard_admitted(fake_external):
    """REQ-121: el libro no manda un `ExternalPayload` suelto: solo lo que admitió la puerta."""
    fake_external.enable()
    with pytest.raises(TypeError, match="puerta"):
        ledger.send([external_payload()])
    assert fake_external.batches == []


def test_the_recorded_text_is_the_one_sent_and_has_nothing_of_the_sheet(case, fake_external):
    """REQ-121 y REQ-122: el hecho de un pedido admitido guarda el texto tal como salió y, con la
    hoja cargada, no tiene nada de ella (el filtro guarda solo tipos, ids y cuentas)."""
    fake_external.enable()
    admitted = ask(case, [guard.offer_document(case.documents["economica.pdf"], ECONOMIC)])
    ledger.send([admitted], measurement=MEASUREMENT)
    (event,) = external_requests()
    assert event.detail["texto_enviado"]["mensajes"] == [{"rol": "user", "texto": ECONOMIC}]
    assert KEYWORD not in json.dumps(event.detail, ensure_ascii=False)
    assert event.detail["filtro"]["huellas"]["secuencias_hoja"] > 0
    assert event.detail["filtro"]["documentos"] == [
        {"origen": "oferta", "documento": case.documents["economica.pdf"].pk,
         "tipo": "economica"}]


# --- Un pedido no se rehace fuera de la puerta (O-289-4) ---------------------------------------


def test_a_replaced_payload_is_rejected():
    """REQ-121 (O-289-4): `dataclasses.replace` sobre un pedido no da un pedido que el cliente
    acepte: no pasó por la puerta."""
    payload = external_payload()
    with pytest.raises(TypeError, match="from_guard"):
        dataclasses.replace(payload, system="Texto colado sin pasar por la puerta.")


@pytest.mark.parametrize("duplicate", [copy.copy, copy.deepcopy, lambda p: pickle.loads(
    pickle.dumps(p))])
def test_a_copied_payload_is_rejected(duplicate):
    """REQ-121 (O-289-4): ni `copy`, ni `deepcopy`, ni `pickle` sacan un pedido nuevo sin la
    puerta."""
    with pytest.raises(TypeError):
        duplicate(external_payload())


def test_a_tampered_payload_is_rejected_by_the_client(fake_external):
    """REQ-121 (O-289-4): un pedido cambiado por la fuerza después de armado
    (`object.__setattr__`) no pasa la comprobación del cliente ni llega al doble."""
    fake_external.enable()
    payload = external_payload()
    client._check_payload(payload)
    object.__setattr__(payload, "system", "Texto colado después de la puerta.")
    with pytest.raises(TypeError, match="puerta"):
        client._check_payload(payload)
    with pytest.raises(TypeError, match="puerta"):
        client.send_message(payload)
    assert fake_external.messages == []
