"""`s4_dictamen.dictamen_cargado` y su uso en `context` (REQ-145; T-342). Inventado (P4)."""

import pytest
from django.urls import reverse

from evaluon.journey.temas import s4_dictamen
from evaluon.portal import models as pm
from evaluon.tenders import models as tm
from tests.journey.temas.test_s4_dictamen import portal_dictamen, post_upload
from tests.journey.temas.test_s4_propuesta import log_in, notice

pytestmark = pytest.mark.django_db


def test_sin_dictamen_no_esta_cargado(procedure, operator_user):
    """REQ-145: ni subido ni del Portal."""
    assert s4_dictamen.dictamen_cargado(procedure) is False
    assert s4_dictamen.context(operator_user, procedure, None)["loaded"] is False


def test_del_portal_sin_aprobar_no_cuenta(procedure, operator_user):
    """REQ-145: el publicado y sin aprobar espera; no está cargado."""
    portal_dictamen(procedure, operator_user, pm.ItemState.PROPUESTO)
    assert s4_dictamen.dictamen_cargado(procedure) is False
    assert s4_dictamen.context(operator_user, procedure, None)["loaded"] is False


def test_del_portal_aprobado_cuenta(procedure, operator_user):
    """REQ-145: aprobado desde el Portal es dictamen cargado."""
    portal_dictamen(procedure, operator_user, pm.ItemState.APROBADO)
    assert s4_dictamen.dictamen_cargado(procedure) is True
    assert s4_dictamen.context(operator_user, procedure, None)["loaded"] is True


def test_rechazado_no_cuenta(procedure, operator_user):
    """REQ-145: un dictamen del Portal rechazado no está cargado."""
    portal_dictamen(procedure, operator_user, pm.ItemState.RECHAZADO)
    assert s4_dictamen.dictamen_cargado(procedure) is False


def test_subido_cuenta_y_retirado_no(client, procedure, operator_user):
    """REQ-145: el subido vigente cuenta; al retirarlo deja de contar."""
    log_in(client, operator_user)
    notice(client, post_upload(client, procedure, title="Dictamen CD 1"))
    document = tm.Document.objects.get(procedure=procedure, kind=tm.DocumentKind.DICTAMEN)
    assert s4_dictamen.dictamen_cargado(procedure) is True
    ok, _ = notice(client, client.post(
        reverse("expedientes:s4_dictamen_retirar", args=[procedure.pk, document.pk]),
        {"note": "error de carga"}))
    assert ok
    assert s4_dictamen.dictamen_cargado(procedure) is False
