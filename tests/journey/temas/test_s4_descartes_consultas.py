"""«Descartes propuestos» no consulta por cada fundamento (REQ-091, REQ-100; plan 015, T-264;
T-223). El motivo de un descarte muestra el título del documento de la cita de la oferta: traerlo
con una consulta por motivo hacía que la pestaña de Evaluación hiciera más consultas cuantos más
requisitos «no cumple» había. Todo el material es inventado (P4)."""

import re
from decimal import Decimal

import pytest
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from evaluon.assessment import models as am
from evaluon.journey import memo
from evaluon.journey.temas import s4_descartes
from evaluon.offers import models as om
from tests.assessment.test_matrix import add_run, requirement
from tests.assessment.test_ordering import quote_data
from tests.assessment.test_result_fundamento import portal  # noqa: F401 - fixture
from tests.journey.temas.test_s4_propuesta import log_in
from tests.journey.test_queries import SCALE_LIMIT, grow_case, make_case
from tests.offers.conftest import make_offer

pytestmark = pytest.mark.django_db


def cite_the_failures():
    """Cada resultado «no cumple» o «falta el documento» que todavía no cita nada pasa a citar una
    página de la oferta (la primera lectura de su primer documento). Citas directas, sin el
    modelo."""
    readings = {}
    failed = (am.Outcome.NO_CUMPLE, am.Outcome.SIN_DOCUMENTO)
    for result in am.Result.objects.filter(citations__isnull=True, outcome__in=failed
                                           ).select_related("offer"):
        if result.offer_id not in readings:
            document = om.Document.objects.filter(offer_id=result.offer_id).first()
            readings[result.offer_id] = document.readings.order_by("sequence").first()
        reading = readings[result.offer_id]
        am.Citation.objects.create(
            result=result, order=1, kind=am.CitationKind.OFERTA, document=reading.document,
            reading=reading, page=1, char_start=0, char_end=10, text=reading.canonical_text[:10])


def measured(client, procedure):
    """`(consultas, las que piden documentos de la oferta, ofertas del HTML con motivo)`."""
    url = reverse("expedientes:evaluacion", args=[procedure.pk])
    client.get(url)  # calienta cachés
    with CaptureQueriesContext(connection) as queries:
        response = client.get(url)
    assert response.status_code == 200
    documents = sum(1 for q in queries if 'FROM "offers_document"' in q["sql"])
    grounds = len(re.findall(r'<div class="motivo">', response.content.decode()))
    return len(queries), documents, grounds


def test_the_discard_grounds_do_not_query_per_ground(client, procedure, operator_user, simulate):
    """REQ-091, REQ-100, T-223: con 3 ofertas y citas de la oferta en los resultados «no cumple» y
    «falta el documento», la pestaña hace la misma cantidad de consultas con 50 que con 100
    requisitos, y las que traen documentos de la oferta tampoco crecen: no hay una consulta por
    motivo de descarte."""
    log_in(client, operator_user)
    offers, runs = make_case(procedure, operator_user, simulate)
    grow_case(procedure, operator_user, offers, runs, 50)
    cite_the_failures()
    small, small_documents, small_grounds = measured(client, procedure)
    assert small_grounds > 10, "el caso tiene que tener motivos de descarte"
    assert small < SCALE_LIMIT, f"{small} consultas con 50 requisitos"
    grow_case(procedure, operator_user, offers, runs, 100)
    cite_the_failures()
    big, big_documents, big_grounds = measured(client, procedure)
    assert big_grounds > small_grounds
    assert (big_documents, big) == (small_documents, small), (
        f"con 50 requisitos: {small} consultas ({small_documents} de documentos); con 100: {big} "
        f"({big_documents} de documentos)")


def economic_order(user, procedure):
    """Lo que arma el tema de Descartes y las consultas que leen el ítem o la página del Portal
    por su cuenta (no como parte de otra consulta)."""
    request = RequestFactory().get("/")
    with memo.scope():
        with CaptureQueriesContext(connection) as queries:
            context = s4_descartes.context(user, procedure, request)
    alone = [q for q in queries
             if 'FROM "portal_item"' in q["sql"] or 'FROM "portal_page"' in q["sql"]]
    return context, len(alone)


def test_the_economic_order_source_does_not_query_the_portal_item_per_offer(
        procedure, operator_user, portal):  # noqa: F811
    """REQ-091, REQ-100, T-223: la fuente de los precios sale del ítem de los datos de cada oferta,
    que viene en la misma consulta que los datos: con 2 y con 6 ofertas ninguna consulta lee el
    ítem ni la página del Portal de a una."""
    declaration = requirement(procedure, "declaración jurada")
    offers = []

    def add(count):
        for _ in range(count):
            offer = make_offer(procedure, operator_user, f"Oferente {len(offers) + 1}",
                               {"oferta.pdf": ["Texto de la oferta."]})
            add_run(operator_user, procedure, offer, {declaration: "cumple"})
            quote_data(portal, procedure, offer, total=Decimal("100"),
                       prices={1: (Decimal("5"), 1)})
            offers.append(offer)

    add(2)
    context, few = economic_order(operator_user, procedure)
    assert [s["offers"] for s in context["price_sources"]] == ["las ofertas 1 y 2"]
    add(4)
    context, many = economic_order(operator_user, procedure)
    assert [s["offers"] for s in context["price_sources"]] == ["las ofertas 1, 2, 3, 4, 5 y 6"]
    assert few == many == 0, f"{few} consultas del ítem con 2 ofertas y {many} con 6"
