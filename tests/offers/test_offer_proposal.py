"""Alta de una oferta desde sus archivos: nombre y CUIT propuestos (REQ-083; ADR-0049; T-220).

Las ofertas son sintéticas (P4): imitan la forma de las reales (nota de presentación con razón
social y CUIT, declaración jurada, constancia de inscripción, póliza con el CUIT de la
aseguradora), con nombres y CUIT inventados. El modelo local es el doble de las pruebas:
ninguna usa la GPU.
"""

import itertools
import json
from datetime import date

import pytest

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.norms.models import ProposalState
from evaluon.offers import models as om
from evaluon.offers import proposal_fields as rules
from evaluon.offers import reading as reading_tools
from evaluon.offers.services import offer_proposal as service
from evaluon.offers.services import offers as offers_service
from evaluon.portal.models import PortalOfferData
from evaluon.tenders import jobs
from evaluon.tenders import models as tm
from tests.offers.conftest import evaluator_user, no_commission_user, operator_user  # noqa: F401
from tests.tenders.pdfs import para, tender_pdf

pytestmark = pytest.mark.django_db

_numbers = itertools.count(1)
WEIGHTS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def make_cuit(prefix, body, hyphens=True):
    """Un CUIT inventado con su dígito verificador (cuenta independiente de la del producto)."""
    digits = f"{prefix}{body:08d}"
    total = sum(int(d) * w for d, w in zip(digits, WEIGHTS, strict=True))
    check = (11 - total % 11) % 11
    assert check != 10
    full = f"{digits}{check}"
    return f"{full[:2]}-{full[2:10]}-{full[10]}" if hyphens else full


def break_cuit(cuit):
    return cuit[:-1] + str((int(cuit[-1]) + 1) % 10)


CUIT_A = make_cuit("30", 71234567)
CUIT_B = make_cuit("30", 70555123)
CUIT_INSURER = make_cuit("30", 50004000)
CUIT_ORGANISM = "33-69345023-9"
NAME_A = "Suministros Sintéticos del Sur S.A."
NAME_B = "Comercial Ficticia Norte S.R.L."


@pytest.fixture
def procedure(operator_user):  # noqa: F811
    return tm.Procedure.objects.create(
        number=f"SINT-T220-{next(_numbers)}", procedure_type="Licitación pública",
        subject="Objeto sintético", authorization_date=date(2025, 11, 14),
        created_by=operator_user)


def pdf(*pages):
    """Un PDF sintético: cada argumento es la lista de líneas de una página."""
    return tender_pdf([[para(*lines)] for lines in pages], header=None)


def cover_offer(name=NAME_A, cuit=CUIT_A):
    """Una oferta con la forma de las reales: nota de presentación rotulada, declaración
    jurada y constancia de inscripción."""
    return [
        (f"oferta-{next(_numbers)}.pdf", pdf(
            ["NOTA DE PRESENTACION DE LA OFERTA",
             f"Razón social: {name}",
             f"CUIT: {cuit}",
             "Domicilio: Calle Inventada 123, Ciudad Ficticia"],
            ["Declaración jurada de aptitud para contratar",
             f"{name}, CUIT {cuit}, con domicilio en Calle Inventada 123, declara bajo "
             "juramento que no se encuentra comprendida en las causales de inhabilidad."])),
        (f"constancia-{next(_numbers)}.pdf", pdf(
            ["CONSTANCIA DE INSCRIPCION",
             f"{name}", f"CUIT: {cuit}", "Impuesto al valor agregado: Responsable inscripto"])),
    ]


def upload_and_read(user, procedure, files):
    draft = service.upload_offer_files(user, procedure, files)
    jobs.run_next(kinds=[tm.JobKind.PROPOSE_OFFER])
    draft.refresh_from_db()
    return draft


def fields_of(draft):
    return draft.proposal["fields"]


# --- Reglas ---------------------------------------------------------------------------------


def test_cuit_check_digit_rule():
    """REQ-083: el CUIT se valida por formato y dígito verificador."""
    assert rules.cuit_is_valid(CUIT_A.replace("-", ""))
    assert not rules.cuit_is_valid(break_cuit(CUIT_A).replace("-", ""))
    assert not rules.cuit_is_valid("12345678901")
    assert not rules.cuit_is_valid("3071234567")
    other = make_cuit("27", 12345678)
    assert rules.normalize_cuit(other.replace("-", "")) == other
    assert rules.normalize_cuit(break_cuit(CUIT_A)) is None


# --- Subir y leer ---------------------------------------------------------------------------


def test_the_small_case_gives_two_of_two_data_per_offer_with_citation(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: ofertas del caso chico: 2 de 2 datos por oferta, cada uno con su cita
    (documento, página y texto)."""
    first = upload_and_read(operator_user, procedure, cover_offer(NAME_A, CUIT_A))
    second = upload_and_read(operator_user, procedure, cover_offer(NAME_B, CUIT_B))
    for draft, name, cuit in ((first, NAME_A, CUIT_A), (second, NAME_B, CUIT_B)):
        assert draft.state == ProposalState.PROPUESTO
        fields = fields_of(draft)
        assert fields["bidder"]["proposed"] == name and fields["cuit"]["proposed"] == cuit
        for field in ("bidder", "cuit"):
            assert fields[field]["state"] == "propuesto"
            citation = fields[field]["citation"]
            assert citation["document"].endswith(".pdf") and citation["page"] == 1
            assert len(citation["file_sha256"]) == 64
            assert (name if field == "bidder" else cuit) in citation["text"]
        assert fields["bidder"]["method"] == "regla"
    assert fake_generation.calls == []
    assert first.job.status == tm.JobStatus.DONE


def test_upload_queues_a_propose_offer_job_with_the_procedure(operator_user, procedure):
    """REQ-083: subir deja el borrador «leyendo» y el pedido en espera, sin oferta."""
    draft = service.upload_offer_files(operator_user, procedure, cover_offer())
    assert draft.state == ProposalState.LEYENDO and draft.files.count() == 2
    assert draft.job.kind == tm.JobKind.PROPOSE_OFFER
    assert draft.job.procedure == procedure and draft.job.target_id == draft.pk
    assert not om.Offer.objects.exists()


def test_the_handler_is_registered_in_the_queue():
    """REQ-083: el pedido tiene su manejador en `jobs.HANDLERS`, por su ruta."""
    assert jobs.HANDLERS[tm.JobKind.PROPOSE_OFFER] == (
        "evaluon.offers.services.offer_proposal.run_propose_offer")


def test_a_cuit_without_hyphens_and_a_name_on_the_next_line(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: el CUIT rotulado sin guiones se propone normalizado; el nombre puede estar en
    la línea de abajo del rótulo."""
    plain = make_cuit("30", 71234567, hyphens=False)
    files = [("o.pdf", pdf(["Denominación social:", NAME_A, f"C.U.I.T. N° {plain}"]))]
    draft = upload_and_read(operator_user, procedure, files)
    assert fields_of(draft)["cuit"]["proposed"] == CUIT_A
    assert fields_of(draft)["bidder"]["proposed"] == NAME_A


def test_a_name_before_the_cuit_without_a_label_is_not_proposed(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083 / P3: sin rótulo explícito del oferente, un nombre con tipo societario pegado
    al CUIT no alcanza: queda «no determinado» y el CUIT sí se propone."""
    fake_generation.respond(json.dumps({"bidder": {"valor": "", "cita": ""}}))
    files = [("o.pdf", pdf([f"Constancia de inscripción - {NAME_B} - CUIT {CUIT_B}"]))]
    draft = upload_and_read(operator_user, procedure, files)
    assert fields_of(draft)["bidder"]["state"] == "no_determinado"
    assert fields_of(draft)["bidder"]["citation"] is None
    assert fields_of(draft)["cuit"]["proposed"] == CUIT_B


def test_the_insurer_and_the_organism_are_not_the_bidder(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: el CUIT de la aseguradora (póliza) y el del organismo contratante no se
    proponen aunque aparezcan más de una vez."""
    files = cover_offer(NAME_A, CUIT_A) + [
        ("poliza.pdf", pdf(
            ["POLIZA DE SEGURO DE CAUCION",
             f"Aseguradora: Seguros Ficticios S.A. CUIT {CUIT_INSURER}",
             f"Compañía aseguradora CUIT {CUIT_INSURER}",
             f"Compañía aseguradora CUIT {CUIT_INSURER}",
             f"Tomador: {NAME_A} CUIT {CUIT_A}",
             f"Asegurado: Administración Federal de Ingresos Públicos CUIT {CUIT_ORGANISM}",
             f"Asegurado: AFIP CUIT {CUIT_ORGANISM}"]))]
    draft = upload_and_read(operator_user, procedure, files)
    assert fields_of(draft)["cuit"]["proposed"] == CUIT_A
    assert CUIT_INSURER not in fields_of(draft)["cuit"]["candidates"]
    assert CUIT_ORGANISM not in fields_of(draft)["cuit"]["candidates"]
    assert fields_of(draft)["bidder"]["proposed"] == NAME_A


def test_a_cuit_with_a_wrong_check_digit_is_not_proposed(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083 / P3: un número que parece CUIT pero no cumple el dígito verificador queda
    «no determinado»; sin cita, nada se propone."""
    files = [("o.pdf", pdf([f"Razón social: {NAME_A}", f"CUIT: {break_cuit(CUIT_A)}"]))]
    draft = upload_and_read(operator_user, procedure, files)
    cuit = fields_of(draft)["cuit"]
    assert cuit["state"] == "no_determinado" and cuit["proposed"] is None
    assert cuit["citation"] is None and cuit["candidates"] == []
    # El nombre se ancla al CUIT del oferente: sin CUIT válido, ninguna línea lo justifica.
    assert fields_of(draft)["bidder"]["state"] == "no_determinado"


def test_the_cuit_with_more_support_wins_and_the_others_are_candidates(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: con dos CUIT válidos gana el que más respaldo tiene; el otro queda como
    candidato para que el evaluador decida."""
    files = [("o.pdf", pdf(
        [f"Razón social: {NAME_A}", f"CUIT: {CUIT_A}"],
        [f"Representante legal de {NAME_A} CUIT {CUIT_A}",
         f"Sociedad vinculada CUIT {CUIT_B}"]))]
    draft = upload_and_read(operator_user, procedure, files)
    assert fields_of(draft)["cuit"]["proposed"] == CUIT_A
    assert fields_of(draft)["cuit"]["candidates"] == [CUIT_A, CUIT_B]


def test_a_file_without_data_proposes_nothing(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083 / P3: archivos sin nombre ni CUIT dejan los dos datos «no determinado»."""
    files = [("o.pdf", pdf(["Texto libre sin datos del oferente."]))]
    draft = upload_and_read(operator_user, procedure, files)
    assert draft.state == ProposalState.PROPUESTO
    assert {f["state"] for f in fields_of(draft).values()} == {"no_determinado"}
    assert len(draft.proposal["warnings"]) == 2


# --- El nombre anclado al CUIT (ronda 1) -----------------------------------------------------

PERSON = "María Fernanda Quiroga"
CUIT_PERSON = make_cuit("27", 21345679)
CUIT_MALE = make_cuit("20", 20456789)


def policy_pages():
    """Póliza de una aseguradora con tipo societario: un tercero en la misma oferta."""
    return ("poliza.pdf", pdf(
        ["POLIZA DE SEGURO DE CAUCION", "Seguros Ficticios del Plata S.A.",
         f"Aseguradora CUIT {CUIT_INSURER}", f"Tomador: {PERSON}",
         f"Tomador CUIT {CUIT_PERSON}"]))


def test_a_third_party_with_a_company_suffix_does_not_win_the_name(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083 / P3: una línea con «S.A.» de un tercero (aseguradora, banco) en la misma
    oferta no gana: el nombre se justifica por su cercanía al CUIT del oferente."""
    files = [("o.pdf", pdf(
        ["Banco Ficticio Central S.A.", f"Garante CUIT {CUIT_INSURER}"],
        [f"Oferente: {NAME_A}", f"CUIT: {CUIT_A}"])),
        ("poliza.pdf", pdf(["Compañía de Seguros Inventada S.A.",
                            f"Aseguradora CUIT {CUIT_INSURER}", f"Tomador CUIT {CUIT_A}"]))]
    draft = upload_and_read(operator_user, procedure, files)
    assert fields_of(draft)["cuit"]["proposed"] == CUIT_A
    assert fields_of(draft)["bidder"]["proposed"] == NAME_A
    assert "Seguros" not in " ".join(fields_of(draft)["bidder"]["candidates"])
    assert "Banco" not in " ".join(fields_of(draft)["bidder"]["candidates"])


def test_a_labeled_name_far_from_the_bidder_cuit_is_not_proposed(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083 / P3: un nombre rotulado lejos del CUIT del oferente no se propone."""
    filler = [f"Texto de relleno {n}" for n in range(8)]
    files = [("o.pdf", pdf([f"Razón social: {NAME_B}", *filler, f"CUIT: {CUIT_A}"]))]
    fake_generation.respond(json.dumps({"bidder": {"valor": "", "cita": ""}}))
    draft = upload_and_read(operator_user, procedure, files)
    assert fields_of(draft)["cuit"]["proposed"] == CUIT_A
    assert fields_of(draft)["bidder"]["state"] == "no_determinado"


def test_an_explicit_label_wins_for_a_company_and_for_a_person(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: con rótulo explícito («Razón social», «Denominación», «Oferente», «Apellido y
    nombre», «Nombre y apellido»), en la misma línea o la siguiente, el nombre se propone con
    su cita, también con la póliza de una aseguradora con «S.A.» en la misma oferta."""
    cases = [
        ([f"Razón social: {NAME_A}", f"CUIT: {CUIT_A}"], NAME_A, CUIT_A),
        ([f"Denominación: {NAME_A}", f"CUIT: {CUIT_A}"], NAME_A, CUIT_A),
        ([f"Oferente: {NAME_A}", f"CUIT: {CUIT_A}"], NAME_A, CUIT_A),
        ([f"Apellido y nombre: {PERSON}", f"CUIT: {CUIT_PERSON}"], PERSON, CUIT_PERSON),
        ([f"Nombre y apellido: {PERSON}", f"CUIT: {CUIT_PERSON}"], PERSON, CUIT_PERSON),
        (["Apellido y nombre:", PERSON, f"CUIT: {CUIT_PERSON}"], PERSON, CUIT_PERSON),
    ]
    for lines, name, cuit in cases:
        draft = upload_and_read(operator_user, procedure,
                                [("o.pdf", pdf(lines)), policy_pages()])
        assert fields_of(draft)["cuit"]["proposed"] == cuit, lines
        assert fields_of(draft)["bidder"]["proposed"] == name, lines
        assert fields_of(draft)["bidder"]["method"] == "regla"
        assert name in fields_of(draft)["bidder"]["citation"]["text"]
        om.OfferDraft.objects.filter(pk=draft.pk).update(state=ProposalState.RECHAZADO)


def test_a_signatory_next_to_the_cuit_does_not_win_the_name(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083 / P3: el nombre de un firmante, apoderado o representante junto al CUIT del
    oferente no se propone, ni con rótulo («Nombre y apellido» del bloque de firma)."""
    fake_generation.respond(json.dumps({"bidder": {"valor": "", "cita": ""}}))
    cases = [
        ["Firmante", f"Nombre y apellido: {PERSON}", f"CUIT: {CUIT_PERSON}"],
        [f"Apoderado: {PERSON}", f"Apellido y nombre: {PERSON}", f"CUIT: {CUIT_PERSON}"],
        [f"Representante legal - Apellido y nombre: {PERSON}", f"CUIT: {CUIT_PERSON}"],
        [f"Se presenta {PERSON} en nombre de la empresa", f"CUIT: {CUIT_PERSON}"],
        [PERSON, f"CUIT: {CUIT_PERSON}"],
    ]
    for lines in cases:
        draft = upload_and_read(operator_user, procedure, [("o.pdf", pdf(lines))])
        assert fields_of(draft)["cuit"]["proposed"] == CUIT_PERSON, lines
        assert fields_of(draft)["bidder"]["state"] == "no_determinado", lines
        om.OfferDraft.objects.filter(pk=draft.pk).update(state=ProposalState.RECHAZADO)


def test_a_labeled_third_party_name_is_not_the_bidder(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083 / P3: filtro de terceros en el nombre: «Razón social» de una aseguradora o un
    banco junto al CUIT no se propone."""
    fake_generation.respond(json.dumps({"bidder": {"valor": "", "cita": ""}}))
    for third in ("Seguros Ficticios del Plata S.A.", "Banco Ficticio Central S.A.",
                  "Ficticia del Plata S.A. Compañía Aseguradora"):
        files = [("o.pdf", pdf([f"Razón social: {third}", f"CUIT: {CUIT_A}"]))]
        draft = upload_and_read(operator_user, procedure, files)
        assert fields_of(draft)["bidder"]["state"] == "no_determinado", third
        assert not fields_of(draft)["bidder"]["candidates"]
        om.OfferDraft.objects.filter(pk=draft.pk).update(state=ProposalState.RECHAZADO)


def test_the_cuit_of_an_insurer_with_more_mentions_does_not_win(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083 / P3: filtro de terceros en el CUIT: el de la aseguradora, con más menciones
    que el del oferente, no se propone ni queda como candidato."""
    files = [("o.pdf", pdf([f"Razón social: {NAME_A}", f"CUIT: {CUIT_A}"])),
             ("poliza.pdf", pdf([f"Compañía aseguradora CUIT {CUIT_INSURER}",
                                 f"Compañía aseguradora CUIT {CUIT_INSURER}",
                                 f"Compañía aseguradora CUIT {CUIT_INSURER}"]))]
    draft = upload_and_read(operator_user, procedure, files)
    assert fields_of(draft)["cuit"]["proposed"] == CUIT_A
    assert fields_of(draft)["cuit"]["candidates"] == [CUIT_A]


def test_a_title_line_is_not_taken_as_a_person(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083 / P3: un título de documento junto al CUIT de una persona humana no es su
    nombre."""
    files = [("o.pdf", pdf(["CONSTANCIA DE INSCRIPCION", f"CUIT: {CUIT_MALE}"]))]
    fake_generation.respond(json.dumps({"bidder": {"valor": "", "cita": ""}}))
    draft = upload_and_read(operator_user, procedure, files)
    assert fields_of(draft)["cuit"]["proposed"] == CUIT_MALE
    assert fields_of(draft)["bidder"]["state"] == "no_determinado"


def test_two_different_names_next_to_the_cuit_with_the_same_support_give_no_name(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083 / P3: ante dos nombres distintos con el mismo respaldo junto al CUIT no se
    propone ninguno; ambos quedan como candidatos."""
    files = [("o.pdf", pdf([f"Razón social: {NAME_A}", f"Denominación: {NAME_B}",
                            f"CUIT: {CUIT_A}"]))]
    fake_generation.respond(json.dumps({"bidder": {"valor": "", "cita": ""}}))
    draft = upload_and_read(operator_user, procedure, files)
    name = fields_of(draft)["bidder"]
    assert name["state"] == "no_determinado" and name["proposed"] is None
    assert set(name["candidates"]) == {NAME_A, NAME_B}


FILLER = [f"Texto de relleno {n}" for n in range(8)]


def test_the_model_cannot_name_a_third_party(operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083 / P3: aunque la cita sea literal y traiga rótulo, si habla de una aseguradora el
    modelo no puede proponerla como oferente (filtro sobre la cita, no solo sobre el valor)."""
    line = "Razón social: Ficticia del Plata S.A. aseguradora de la póliza"
    fake_generation.respond(json.dumps(
        {"bidder": {"valor": "Ficticia del Plata S.A.", "cita": line}}))
    draft = upload_and_read(operator_user, procedure,
                            [("o.pdf", pdf([line, *FILLER, f"Número de CUIT: {CUIT_A}"]))])
    assert fields_of(draft)["bidder"]["state"] == "no_determinado"


def test_the_model_cannot_name_a_signatory(operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083 / P3: la cita del modelo con un firmante o representante no vale."""
    line = f"Representante legal - Apellido y nombre: {PERSON}"
    fake_generation.respond(json.dumps({"bidder": {"valor": PERSON, "cita": line}}))
    draft = upload_and_read(operator_user, procedure,
                            [("o.pdf", pdf([line, *FILLER, f"Número de CUIT: {CUIT_A}"]))])
    assert fields_of(draft)["bidder"]["state"] == "no_determinado"


def test_the_model_needs_an_explicit_label_in_its_quote(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083 / P3: una cita literal sin rótulo explícito del oferente no vale."""
    line = f"Presenta esta oferta la firma {NAME_A} para el procedimiento."
    fake_generation.respond(json.dumps({"bidder": {"valor": NAME_A, "cita": line}}))
    draft = upload_and_read(operator_user, procedure,
                            [("o.pdf", pdf([line, *FILLER, f"Número de CUIT: {CUIT_A}"]))])
    assert fields_of(draft)["bidder"]["state"] == "no_determinado"


# --- El modelo -------------------------------------------------------------------------------


def test_the_model_fills_the_name_only_with_a_verified_quote(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: si las reglas no hallan el nombre, el modelo lo propone con cita literal; el
    CUIT sigue siendo por regla; la traza queda en la auditoría."""
    line = f"Razón social: {NAME_A}"
    fake_generation.respond(json.dumps({"bidder": {"valor": NAME_A, "cita": line}}))
    files = [("o.pdf", pdf([line, *FILLER, f"Número de CUIT: {CUIT_A}"]))]
    draft = upload_and_read(operator_user, procedure, files)
    name = fields_of(draft)["bidder"]
    assert name["proposed"] == NAME_A and name["method"] == "modelo"
    assert name["citation"]["text"] == line and name["citation"]["page"] == 1
    assert fields_of(draft)["cuit"]["method"] == "regla"
    event = AuditEvent.objects.get(event_type=EventType.OFFER_PROPOSAL,
                                   detail__action="propose")
    trace = event.detail["model"][0]
    assert trace["asked"] == ["bidder"] and trace["prompt_version"]
    assert trace["instructions_sha256"] and trace["request"] and trace["output"]


@pytest.mark.parametrize("answer", [
    {"valor": NAME_A, "cita": "texto que no está en la oferta"},
    {"valor": NAME_A, "cita": f"una cita inventada que contiene {NAME_A}"},
    {"valor": "Otra Empresa S.A.", "cita": "Presenta esta oferta la firma"},
    {"valor": "", "cita": ""},
])
def test_an_unverifiable_model_quote_leaves_the_name_undetermined(
        operator_user, procedure, fake_generation, answer):  # noqa: F811
    """REQ-083 / P3: una cita que no es literal de la página, un valor fuera de la cita o una
    respuesta vacía dejan el nombre «no determinado»."""
    fake_generation.respond(json.dumps({"bidder": answer}))
    files = [("o.pdf", pdf(["Presenta esta oferta la firma", f"Número de CUIT: {CUIT_A}"]))]
    draft = upload_and_read(operator_user, procedure, files)
    assert fields_of(draft)["bidder"]["state"] == "no_determinado"
    assert fields_of(draft)["bidder"]["citation"] is None
    assert fields_of(draft)["cuit"]["proposed"] == CUIT_A


def test_the_model_never_proposes_the_cuit(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: el CUIT es solo por regla: al modelo se le pregunta únicamente por el nombre."""
    fake_generation.respond(json.dumps({"bidder": {"valor": "", "cita": ""}}))
    draft = upload_and_read(operator_user, procedure, [("o.pdf", pdf(["Texto sin datos."]))])
    assert fields_of(draft)["cuit"]["state"] == "no_determinado"
    _, schema = fake_generation.calls[0]
    assert list(schema["properties"]) == ["bidder"]


def test_a_model_failure_does_not_fail_the_proposal(
        operator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: una falla del servicio del modelo deja el nombre sin determinar y la propuesta
    sigue («propuesto»)."""
    fake_generation.unavailable()
    draft = upload_and_read(operator_user, procedure, [("o.pdf", pdf(["Texto sin datos."]))])
    assert draft.state == ProposalState.PROPUESTO
    assert fields_of(draft)["bidder"]["state"] == "no_determinado"


# --- Fallas de lectura -----------------------------------------------------------------------


def test_an_unreadable_file_does_not_stop_the_others(
        operator_user, procedure, fake_generation, monkeypatch):  # noqa: F811
    """REQ-083: un archivo que no se puede leer queda en los avisos y en el informe; los otros
    se leen."""
    original = reading_tools.read_with_second_attempt
    calls = []

    def flaky(data):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("falla de lectura")
        return original(data)

    monkeypatch.setattr(reading_tools, "read_with_second_attempt", flaky)
    draft = upload_and_read(operator_user, procedure, cover_offer())
    assert draft.state == ProposalState.PROPUESTO
    assert fields_of(draft)["cuit"]["proposed"] == CUIT_A
    assert any("No se pudo leer" in w for w in draft.proposal["warnings"])
    event = AuditEvent.objects.get(event_type=EventType.OFFER_PROPOSAL,
                                   detail__action="propose")
    assert sum("error" in item for item in event.detail["reading"]) == 1


def test_if_no_file_can_be_read_the_draft_fails_with_its_fact(
        operator_user, procedure, fake_generation, monkeypatch):  # noqa: F811
    """REQ-083: si no se lee ningún archivo, el borrador queda «fallido» y el hecho fallido
    en la auditoría."""
    def broken(data):
        raise RuntimeError("falla de lectura")

    monkeypatch.setattr(reading_tools, "read_with_second_attempt", broken)
    draft = service.upload_offer_files(operator_user, procedure, cover_offer())
    with pytest.raises(ValueError):
        service.run_propose_offer(draft.job)
    draft.refresh_from_db()
    assert draft.state == ProposalState.FALLIDO and "ninguno" in draft.failure
    assert AuditEvent.objects.filter(event_type=EventType.OFFER_PROPOSAL,
                                     outcome=Outcome.FAILED).count() == 1


# --- Subir: rechazos -------------------------------------------------------------------------


def test_upload_refuses_empty_unsupported_and_repeated_files(operator_user, procedure):  # noqa: F811
    """REQ-083: sin archivos, un archivo vacío, un formato no soportado y un archivo repetido
    se rechazan con aviso y dejan el hecho `rejected`."""
    good = pdf(["Texto."])
    cases = [[], [("vacio.pdf", b"")], [("nota.txt", b"hola")],
             [("a.pdf", good), ("b.pdf", good)]]
    for files in cases:
        with pytest.raises(service.ProposalRefused):
            service.upload_offer_files(operator_user, procedure, files)
    assert not om.OfferDraft.objects.exists() and not tm.Job.objects.exists()
    assert AuditEvent.objects.filter(event_type=EventType.OFFER_PROPOSAL,
                                     outcome=Outcome.REJECTED).count() == 4


def test_the_same_files_cannot_be_uploaded_twice_until_the_draft_is_rejected(
        operator_user, evaluator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: el mismo archivo en otro borrador pendiente se rechaza; descartado el
    borrador, se puede volver a subir."""
    files = cover_offer()
    draft = upload_and_read(operator_user, procedure, files)
    with pytest.raises(service.DuplicateFiles):
        service.upload_offer_files(operator_user, procedure, files[:1])
    service.reject(evaluator_user, draft.pk, "Se leyó mal")
    again = service.upload_offer_files(operator_user, procedure, files[:1])
    assert again.state == ProposalState.LEYENDO


# --- Corregir --------------------------------------------------------------------------------


def test_a_correction_needs_a_reason(
        operator_user, evaluator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: corregir sin motivo (vacío, espacios, nulo) se rechaza y no cambia nada."""
    draft = upload_and_read(operator_user, procedure, cover_offer())
    for reason in ("", "   ", None):
        with pytest.raises(service.ReasonRequired):
            service.correct(evaluator_user, draft.pk, "bidder", "Otra S.A.", reason)
    draft.refresh_from_db()
    assert draft.proposal["corrections"] == []


def test_a_correction_keeps_the_proposed_value_with_who_and_when(
        operator_user, evaluator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: la corrección guarda propuesto, corregido, motivo, quién y cuándo; el CUIT
    corregido se normaliza y se valida."""
    draft = upload_and_read(operator_user, procedure, cover_offer())
    service.correct(evaluator_user, draft.pk, "bidder", "  Nombre   Corregido S.A. ",
                    "Figura así en el estatuto")
    other = make_cuit("30", 70999888, hyphens=False)
    service.correct(evaluator_user, draft.pk, "cuit", other,
                    "El CUIT correcto está en la póliza")
    draft.refresh_from_db()
    first, second = draft.proposal["corrections"]
    assert first["proposed"] == NAME_A and first["corrected"] == "Nombre Corregido S.A."
    assert first["reason"] == "Figura así en el estatuto"
    assert first["by"] == evaluator_user.get_username() and first["by_id"] == evaluator_user.pk
    assert first["at"]
    assert second["proposed"] == CUIT_A and second["corrected"] == rules.normalize_cuit(other)
    assert fields_of(draft)["bidder"]["proposed"] == NAME_A
    assert fields_of(draft)["cuit"]["proposed"] == CUIT_A
    assert AuditEvent.objects.filter(event_type=EventType.OFFER_PROPOSAL,
                                     detail__action="correct").count() == 2


def test_a_correction_with_an_invalid_cuit_or_field_is_refused(
        operator_user, evaluator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: un CUIT con dígito verificador incorrecto, un valor vacío o un dato que no
    existe se rechazan."""
    draft = upload_and_read(operator_user, procedure, cover_offer())
    for field, value in (("cuit", break_cuit(CUIT_A)), ("cuit", ""), ("bidder", "  "),
                         ("total", "5")):
        with pytest.raises(service.ProposalRefused):
            service.correct(evaluator_user, draft.pk, field, value, "motivo")
    draft.refresh_from_db()
    assert draft.proposal["corrections"] == []


def test_an_undetermined_datum_is_filled_by_writing_value_and_reason(
        operator_user, evaluator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: «Escribe el valor y motivo»: un dato no determinado se completa con su valor
    y su motivo, y queda `proposed: null`."""
    draft = upload_and_read(operator_user, procedure, [("o.pdf", pdf(["Texto sin datos."]))])
    service.correct(evaluator_user, draft.pk, "cuit", CUIT_A, "Figura en el sello")
    draft.refresh_from_db()
    assert draft.proposal["corrections"][0]["proposed"] is None


# --- Roles -----------------------------------------------------------------------------------


def test_the_operator_uploads_but_neither_corrects_nor_approves(
        operator_user, evaluator_user, no_commission_user, procedure,  # noqa: F811
        fake_generation):
    """REQ-083: el operador sube y ve, pero no corrige, no aprueba ni descarta; quien no tiene
    rol de la Comisión no hace nada. Cada rechazo queda auditado."""
    draft = upload_and_read(operator_user, procedure, cover_offer())
    assert service.proposal_of(operator_user, draft.pk).pk == draft.pk
    attempts = [
        lambda: service.correct(operator_user, draft.pk, "bidder", "X S.A.", "motivo"),
        lambda: service.approve(operator_user, draft.pk),
        lambda: service.reject(operator_user, draft.pk, "motivo"),
        lambda: service.upload_offer_files(no_commission_user, procedure, cover_offer()),
        lambda: service.proposal_of(no_commission_user, draft.pk),
    ]
    for attempt in attempts:
        with pytest.raises(RoleRejected):
            attempt()
    draft.refresh_from_db()
    assert draft.state == ProposalState.PROPUESTO and draft.proposal["corrections"] == []
    assert not om.Offer.objects.exists()
    assert AuditEvent.objects.filter(outcome=Outcome.REJECTED).count() == len(attempts)


# --- Aprobar ---------------------------------------------------------------------------------


def test_approve_creates_the_offer_documents_and_cuit_with_its_origin(
        operator_user, evaluator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: aprobar crea la oferta con el nombre, carga los archivos, guarda el CUIT con
    su documento de origen y deja los hechos `offer_proposal` y `offer_register`."""
    draft = upload_and_read(operator_user, procedure, cover_offer())
    cited = fields_of(draft)["cuit"]["citation"]
    service.correct(evaluator_user, draft.pk, "bidder", "Suministros del Sur S.A.",
                    "Nombre corto")
    done = service.approve(evaluator_user, draft.pk)
    assert done.state == ProposalState.APROBADO
    assert done.offer.bidder == "Suministros del Sur S.A."
    offer = done.offer
    assert offer.procedure == procedure and offer.documents.count() == 2
    data = PortalOfferData.objects.get(offer=offer)
    assert data.cuit == CUIT_A and data.item is None
    assert data.document.file_sha256 == cited["file_sha256"]
    assert tm.Job.objects.filter(kind=tm.JobKind.READ_OFFER_DOCUMENT).count() == 2
    event = AuditEvent.objects.get(event_type=EventType.OFFER_PROPOSAL,
                                   detail__action="approve")
    assert event.user == evaluator_user and event.outcome == Outcome.OK
    assert event.detail["values"] == {"bidder": "Suministros del Sur S.A.", "cuit": CUIT_A}
    assert event.detail["proposed"]["bidder"] == NAME_A
    assert event.detail["corrections"][0]["reason"] == "Nombre corto"
    assert event.detail["citations"]["cuit"] == cited
    assert AuditEvent.objects.filter(event_type=EventType.OFFER_REGISTER,
                                     outcome=Outcome.OK).count() == 1


def test_approve_without_a_required_datum_creates_nothing(
        operator_user, evaluator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: con un dato sin determinar no se aprueba; corregido con su motivo, sí."""
    draft = upload_and_read(operator_user, procedure, [("o.pdf", pdf(["Texto sin datos."]))])
    with pytest.raises(service.IncompleteProposal):
        service.approve(evaluator_user, draft.pk)
    service.correct(evaluator_user, draft.pk, "bidder", NAME_A, "Figura en el sello")
    with pytest.raises(service.IncompleteProposal) as error:
        service.approve(evaluator_user, draft.pk)
    assert error.value.field == "cuit"
    assert not om.Offer.objects.exists() and not PortalOfferData.objects.exists()
    service.correct(evaluator_user, draft.pk, "cuit", CUIT_A, "Figura en el sello")
    done = service.approve(evaluator_user, draft.pk)
    assert done.offer.bidder == NAME_A
    assert PortalOfferData.objects.get(offer=done.offer).document.offer == done.offer


def test_a_repeated_bidder_is_refused_and_leaves_nothing_behind(
        operator_user, evaluator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: el mismo oferente (por nombre o por CUIT) en el procedimiento se rechaza con
    aviso y no deja ni oferta, ni documentos, ni datos."""
    first = upload_and_read(operator_user, procedure, cover_offer(NAME_A, CUIT_A))
    service.approve(evaluator_user, first.pk)
    same_name = upload_and_read(operator_user, procedure, cover_offer(NAME_A, CUIT_B))
    with pytest.raises(service.DuplicateBidder):
        service.approve(evaluator_user, same_name.pk)
    same_cuit = upload_and_read(operator_user, procedure, cover_offer(NAME_B, CUIT_A))
    with pytest.raises(service.DuplicateBidder):
        service.approve(evaluator_user, same_cuit.pk)
    assert om.Offer.objects.count() == 1 and om.Document.objects.count() == 2
    assert PortalOfferData.objects.count() == 1
    for draft in (same_name, same_cuit):
        draft.refresh_from_db()
        assert draft.state == ProposalState.PROPUESTO and draft.offer is None
    assert AuditEvent.objects.filter(event_type=EventType.OFFER_PROPOSAL,
                                     outcome=Outcome.REJECTED,
                                     detail__reason="duplicate_bidder").count() == 2


def test_approve_does_not_leave_an_offer_if_loading_a_file_fails(
        operator_user, evaluator_user, procedure, fake_generation, monkeypatch):  # noqa: F811
    """REQ-083: la oferta, sus archivos y el CUIT se crean en una transacción: si falla la
    carga del segundo archivo no queda nada y el borrador sigue «propuesto»."""
    draft = upload_and_read(operator_user, procedure, cover_offer())
    original = offers_service.load_document
    calls = []

    def second_fails(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise offers_service.OfferRefused("No se pudo cargar.", "file")
        return original(*args, **kwargs)

    monkeypatch.setattr(offers_service, "load_document", second_fails)
    with pytest.raises(service.ProposalRefused):
        service.approve(evaluator_user, draft.pk)
    assert not om.Offer.objects.exists() and not om.Document.objects.exists()
    assert not PortalOfferData.objects.exists()
    draft.refresh_from_db()
    assert draft.state == ProposalState.PROPUESTO and draft.offer is None


def test_approve_twice_is_refused(
        operator_user, evaluator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: una propuesta ya aprobada no se vuelve a aprobar ni a corregir."""
    draft = upload_and_read(operator_user, procedure, cover_offer())
    service.approve(evaluator_user, draft.pk)
    with pytest.raises(service.NotPending):
        service.approve(evaluator_user, draft.pk)
    with pytest.raises(service.NotPending):
        service.correct(evaluator_user, draft.pk, "bidder", "X S.A.", "motivo")


# --- Descartar -------------------------------------------------------------------------------


def test_reject_needs_a_reason_and_creates_nothing(
        operator_user, evaluator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: descartar una propuesta mal leída pide motivo, deja quién y cuándo y no crea
    nada; una propuesta ya descartada no se descarta de nuevo."""
    draft = upload_and_read(operator_user, procedure, cover_offer())
    for reason in ("", "  ", None):
        with pytest.raises(service.ReasonRequired):
            service.reject(evaluator_user, draft.pk, reason)
    done = service.reject(evaluator_user, draft.pk, "Los archivos son de otra oferta")
    assert done.state == ProposalState.RECHAZADO and done.offer is None
    assert done.proposal["rejection"]["by"] == evaluator_user.get_username()
    assert done.proposal["rejection"]["at"]
    event = AuditEvent.objects.get(event_type=EventType.OFFER_PROPOSAL,
                                   detail__action="reject", outcome=Outcome.OK)
    assert event.detail["reason"] == "Los archivos son de otra oferta"
    assert not om.Offer.objects.exists()
    with pytest.raises(service.NotPending):
        service.reject(evaluator_user, draft.pk, "otra vez")


def test_a_failed_draft_can_be_closed_with_a_reason(
        operator_user, evaluator_user, procedure, fake_generation):  # noqa: F811
    """REQ-083: un borrador «fallido» se da por cerrado descartándolo con motivo."""
    draft = service.upload_offer_files(operator_user, procedure, cover_offer())
    om.OfferDraft.objects.filter(pk=draft.pk).update(state=ProposalState.FALLIDO)
    done = service.reject(evaluator_user, draft.pk, "Falló la lectura")
    assert done.state == ProposalState.RECHAZADO
