"""Fixtures de la feature 018 (T-340): los tres procedimientos de la tabla de 21 estados.

Se arman con el caso chico público e inventado de la 008 (`tests/offers/data/caso-chico/`) y los
fixtures que ya existen (`matrix`, `make_offer`, `add_run`, `decide`); no se abre `corpus/casos/`
(P4). Cada fixture devuelve un `SimpleNamespace` con `procedure`, `user` (el evaluador que actúa),
`offers` y lo que cada caso sumó. Los tres crean el mismo procedimiento del caso chico: un test usa
uno solo (no pide `procedure` ni `matrix` junto con `caso_recien_cargado`).

- `caso_recien_cargado`: alta desde el pliego, pliego leído, sin circulares, sin matriz, sin
  ofertas, sin dictamen.
- `caso_varios_en_curso`: la situación de la maqueta A. Pliego y matriz hechos; dos ofertas
  (una con un documento nuevo sin leer); 18 pares evaluados con 12 puntos no determinados, un
  «no cumple», 5 propuestas «cumple» sin confirmar y 4 preguntas abiertas; las filas técnicas
  sin informe técnico; las dos ofertas con total del acta; sin dictamen.
- `caso_todo_hecho`: lo anterior resuelto: todos los pares «cumple» y confirmados, las filas
  técnicas con el informe técnico cargado y su ok, sin preguntas abiertas, totales del acta de las
  dos ofertas y dictamen cargado.

Los resultados se guardan directo, sin el modelo (como en `tests/assessment/test_matrix.py`).
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from evaluon.assessment import models as am
from evaluon.assessment.services import technical
from evaluon.audit.models import Channel
from evaluon.offers import evaluation
from evaluon.offers.models import Document as OfferDocument
from evaluon.offers.models import DocumentKind as OfferDocumentKind
from evaluon.offers.models import DocumentFile as OfferDocumentFile
from evaluon.portal import models as pm
from evaluon.tenders import models as m
from evaluon.tenders.services import documents as tender_documents
from evaluon.tenders.services import procedures as tender_procedures
from tests.assessment.test_matrix import add_run, decide, open_matrix
from tests.offers.conftest import DATA, make_offer

ND = am.Outcome.NO_DETERMINADO
PENDIENTE_INFORME = (ND, am.Doubt.PENDIENTE_INFORME_TECNICO)
DUDA = (ND, am.Doubt.DUDA)
INFORME = "informe-tecnico.pdf"


def _requirements(procedure):
    """La matriz validada del caso chico: `(formales y económicos, filas técnicas)` en orden."""
    rows = list(procedure.matrix_versions.get(number=1).requirements.order_by("number"))
    technical_rows = [r for r in rows if r.category == "tecnico"]
    return [r for r in rows if r.category != "tecnico"], technical_rows


def _oferta_con_documentos(procedure, user, nombre, *, con_informe=False):
    documents = {"oferta.pdf": [
        "Declaro bajo juramento que me encuentro habilitado para contratar. "
        f"{nombre}. La oferta mantiene su validez por sesenta días corridos.",
        "Los precios se cotizan en pesos con impuestos incluidos. Renglón 1: resma de papel A4."]}
    kinds = {}
    if con_informe:
        documents[INFORME] = ["Informe técnico del área (texto inventado): renglones 1 a 3 aptos."]
        kinds[INFORME] = OfferDocumentKind.INFORME_TECNICO
    return make_offer(procedure, user, nombre, documents, kinds=kinds)


def _total_del_acta(offer, total):
    """El total que publica el acta de apertura (`PortalOfferData`); el origen es un documento
    de la oferta (la tabla pide exactamente un origen)."""
    pm.PortalOfferData.objects.create(
        offer=offer, cuit="30-00000000-0", currency="ARS", total=Decimal(total),
        document=offer.documents.order_by("pk").first())


def _pregunta(procedure, offer, requirement, result):
    return am.Question.objects.create(
        procedure=procedure, requirement=requirement, offer=offer, result=result,
        text="¿El documento presentado está vigente?", reason="externo")


@pytest.fixture
def caso_recien_cargado(evaluator_user, expected, fake_ai):
    """Alta desde el pliego y pliego leído: sin circulares, sin matriz, sin ofertas, sin dictamen."""
    matrix = expected.matrix
    registration = tender_procedures.register_procedure(
        evaluator_user, number=matrix["procedimiento"], procedure_type=matrix["tipo"],
        subject=matrix["objeto"], authorization_date=matrix["fecha_autorizacion"],
        channel=Channel.COMMAND)
    procedure = registration.procedure
    evaluation._read_pliego(evaluator_user, procedure, DATA, matrix["pliego"])
    return SimpleNamespace(procedure=procedure, user=evaluator_user, offers=[])


@pytest.fixture
def caso_varios_en_curso(matrix, evaluator_user, fake_ai):
    """La situación de la maqueta A (ver el módulo)."""
    procedure = matrix.procedure
    formal, tecnicas = _requirements(procedure)
    a = _oferta_con_documentos(procedure, evaluator_user, "Oferente A Sintético")
    b = _oferta_con_documentos(procedure, evaluator_user, "Oferente B Sintético")
    open_matrix()
    # Oferta A: 3 técnicas sin informe + 2 dudas + 1 «no cumple» + 3 «cumple» = 5 no determinados.
    resultados_a = add_run(evaluator_user, procedure, a, {
        **{r: PENDIENTE_INFORME for r in tecnicas},
        formal[0]: DUDA, formal[1]: DUDA, formal[-1]: am.Outcome.NO_CUMPLE,
        formal[2]: am.Outcome.CUMPLE, formal[3]: am.Outcome.CUMPLE,
        formal[4]: am.Outcome.CUMPLE})
    # Oferta B: 3 técnicas sin informe + 4 dudas + 2 «cumple» = 7 no determinados (12 en total).
    resultados_b = add_run(evaluator_user, procedure, b, {
        **{r: PENDIENTE_INFORME for r in tecnicas},
        formal[0]: DUDA, formal[1]: DUDA, formal[2]: DUDA, formal[3]: DUDA,
        formal[4]: am.Outcome.CUMPLE, formal[5]: am.Outcome.CUMPLE})
    preguntas = [_pregunta(procedure, a, formal[0], resultados_a[formal[0].pk]),
                 _pregunta(procedure, a, formal[1], resultados_a[formal[1].pk]),
                 _pregunta(procedure, b, formal[0], resultados_b[formal[0].pk]),
                 _pregunta(procedure, b, formal[1], resultados_b[formal[1].pk])]
    # Un documento nuevo de la oferta B, cargado y todavía sin lectura.
    nuevo = OfferDocument.objects.create(
        offer=b, title="anexo-nuevo.pdf", file_name="anexo-nuevo.pdf", file_format="pdf",
        file_size=1, file_sha256="f" * 64, loaded_by=evaluator_user)
    OfferDocumentFile.objects.create(document=nuevo, content=b"%PDF-sintetico")
    _total_del_acta(a, "21750.00")
    _total_del_acta(b, "23100.00")
    return SimpleNamespace(procedure=procedure, user=evaluator_user, offers=[a, b],
                           sin_leer=nuevo, preguntas=preguntas,
                           resultados={a.pk: resultados_a, b.pk: resultados_b})


@pytest.fixture
def caso_todo_hecho(matrix, evaluator_user, fake_ai):
    """Todo resuelto y dictamen cargado (ver el módulo)."""
    procedure = matrix.procedure
    formal, tecnicas = _requirements(procedure)
    ofertas = [_oferta_con_documentos(procedure, evaluator_user, nombre, con_informe=True)
               for nombre in ("Oferente A Sintético", "Oferente B Sintético")]
    open_matrix()
    for offer in ofertas:
        resultados = add_run(evaluator_user, procedure, offer, {
            **{r: PENDIENTE_INFORME for r in tecnicas},
            **{r: am.Outcome.CUMPLE for r in formal}})
        for r in formal:
            decide(evaluator_user, resultados[r.pk], am.Action.CONFIRMAR)
        technical.give_ok(evaluator_user, offer,
                          verdicts={i: "apto" for i in range(1, len(tecnicas) + 1)})
    _total_del_acta(ofertas[0], "21750.00")
    _total_del_acta(ofertas[1], "23100.00")
    dictamen = tender_documents.load_document(
        evaluator_user, procedure, data=b"%PDF-1.4 dictamen sintetico", file_name="dictamen.pdf",
        kind=m.DocumentKind.DICTAMEN, title="Dictamen de evaluación (inventado)").document
    return SimpleNamespace(procedure=procedure, user=evaluator_user, offers=ofertas,
                           dictamen=dictamen)
