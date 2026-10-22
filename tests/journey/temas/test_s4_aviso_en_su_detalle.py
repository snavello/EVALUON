"""El aviso de una acción de Evaluación vuelve al detalle de esa acción (REQ-127, REQ-089,
REQ-091, REQ-092; T-335). Con el tablero cada tema es un detalle propio: la dirección de regreso
lleva el ancla del aviso dentro del detalle de la acción, no el de la propuesta. Todo el material
es inventado (P4)."""

import re

import pytest

from evaluon.journey.temas import s4_propuesta_acciones as acciones
from tests.assessment.test_matrix import three  # noqa: F401  (fixture)
from tests.assessment.test_ordering import portal  # noqa: F401  (fixture)
from tests.assessment.test_technical_report import (  # noqa: F401  (fixtures y ayudas)
    model,
    offers,
)
from tests.journey.conftest import simulate  # noqa: F401  (fixture)
from tests.journey.temas import test_s4_descartes as descartes
from tests.journey.temas import test_s4_dictamen as dictamen
from tests.journey.temas import test_s4_informe as informe
from tests.journey.temas.test_s4_descartes import proposed  # noqa: F401  (fixture)
from tests.journey.temas.test_s4_dictamen import portal_dictamen
from tests.journey.temas.test_s4_propuesta import log_in

pytestmark = pytest.mark.django_db


def detail_with_notice(client, response):
    """`(detalle que contiene el ancla, texto del aviso)` de la pestaña a la que vuelve la acción."""
    assert response.status_code == 302
    location = response["Location"]
    assert "#" in location, location
    anchor = location.split("#", 1)[1]
    html = client.get(location.split("#", 1)[0]).content.decode()
    found = re.search(rf'<p class="aviso [^"]*" id="{re.escape(anchor)}"[^>]*>(.*?)</p>', html, re.S)
    assert found, f"la pestaña no dibuja el aviso con id {anchor}"
    start = html.index(f'id="{anchor}"')
    openers = [m for m in re.finditer(r'class="inline-detail" id="(d-[^"]+)"', html)
               if m.start() < start]
    assert openers, "el aviso no está dentro de un detalle del tablero"
    return openers[-1].group(1), found.group(1)


def test_the_default_anchor_of_the_proposal_does_not_change():
    """La propuesta sigue volviendo a su propio aviso."""
    assert acciones.ANCHOR == "#s4-aviso"


def test_a_discard_decision_comes_back_to_the_discard_detail(
        client, proposed, procedure, evaluator_user):
    """REQ-091: decidir un descarte vuelve al detalle de los descartes, con su aviso."""
    log_in(client, evaluator_user)
    detail, text = detail_with_notice(client, descartes.post(client, procedure, proposed[1]))
    assert detail == "d-s4-descartes"
    assert "Se confirmó el descarte de la oferta" in text


def test_uploading_the_report_comes_back_to_the_report_detail(
        client, offers, procedure, evaluator_user, model):
    """REQ-089: subir el informe técnico vuelve al detalle del informe, con su aviso."""
    log_in(client, evaluator_user)
    detail, text = detail_with_notice(client, informe.post_upload(client, procedure, offers[0]))
    assert detail == "d-s4-informe"
    assert f"la oferta {offers[0].number}" in text


def test_approving_the_dictamen_comes_back_to_the_dictamen_detail(
        client, procedure, operator_user):
    """REQ-092: aprobar el dictamen del Portal vuelve al detalle del dictamen, con su aviso."""
    portal_dictamen(procedure, operator_user)
    log_in(client, operator_user)
    detail, text = detail_with_notice(client, dictamen.take(client, procedure))
    assert detail == "d-s4-dictamen"
    assert "Se tomó el dictamen del Portal" in text


def test_a_proposal_action_still_comes_back_to_the_proposal_detail(
        client, proposed, procedure, evaluator_user):
    """REQ-089: «Evaluar todas las ofertas» y las decisiones de la tabla siguen volviendo al
    detalle de la propuesta (su aviso es `#s4-aviso`)."""
    from django.urls import reverse
    log_in(client, evaluator_user)
    response = client.post(reverse("expedientes:s4_evaluar", args=[procedure.pk]))
    assert response.status_code == 302 and response["Location"].endswith("#s4-aviso")
    detail, _ = detail_with_notice(client, response)
    assert detail == "d-s4-propuesta"
