"""Por qué el Pliego Único no baja, dicho en la anomalía (REQ-104; T-259; informe del comité
H7). Con el calco `portal-chico` y el portal de mentira (sin red, P4): el Pliego general da la
pantalla de error, como en los casos 00 y 05; la anomalía dice que en el Portal lo abre una
función de la página que el sistema no reproduce, y sigue quedando la carga manual."""

import pytest

from evaluon.portal.models import PortalItem
from tests.portal.fakeportal import (  # noqa: F401
    explore_link,
    fake_portal_calco,
    portal_client,
    portal_settings,
)
from tests.portal.test_documents import PLIEGO_GENERAL, docs_portal, serve_documents  # noqa: F401
from tests.tenders.conftest import operator_user  # noqa: F401

pytestmark = pytest.mark.django_db


def test_the_anomaly_of_the_general_tender_says_why_it_fails(
        operator_user, explore_link, docs_portal):  # noqa: F811
    """REQ-104 (T-259, H7): la anomalía del Pliego general dice la pantalla de error, la causa
    (una función de la página del Portal) y la carga manual."""
    link, job = explore_link(operator_user)
    assert job.status == "done", job.error
    anomalies = PortalItem.objects.first().proposal.anomalies
    [general] = [a for a in anomalies if PLIEGO_GENERAL in a["parte"]]
    assert "pantalla de error" in general["motivo"]
    assert "función de su página" in general["motivo"]
    assert "carga manual" in general["motivo"]
