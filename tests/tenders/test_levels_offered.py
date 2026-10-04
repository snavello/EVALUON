"""Solo se ofrecen los niveles que decidió el responsable: media y alta (REQ-030; T-085)."""

import pytest
from django.conf import settings
from django.urls import reverse

from evaluon.tenders.services import matrix
from tests.conftest import TEST_PASSWORD
from tests.tenders.scripted import (
    load_and_read,
    make_procedure,
    script,  # noqa: F401  (fixture)
    three_items_pdf,
)

pytestmark = pytest.mark.django_db


def test_offered_levels_are_media_and_alta_and_default_is_offered():
    """REQ-030: se ofrecen media y alta; exigente existe pero no se ofrece; el nivel por
    omisión es uno de los ofrecidos."""
    assert tuple(settings.MATRIX_LEVELS_OFFERED) == ("media", "alta")
    assert "exigente" in settings.MATRIX_LEVELS
    assert settings.MATRIX_DEFAULT_LEVEL == "alta"
    assert settings.MATRIX_DEFAULT_LEVEL in settings.MATRIX_LEVELS_OFFERED


def test_exigente_is_not_in_the_form_and_its_request_is_refused(client, operator_user, script):
    """REQ-030: exigente no aparece en el formulario y su pedido se rechaza sin encolar."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, three_items_pdf())
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)

    page = client.get(reverse("tenders:procedure", args=[procedure.pk])).content.decode()
    assert 'value="exigente"' not in page and 'value="alta" selected' in page

    with pytest.raises(matrix.MatrixRefused) as error:
        matrix.request_matrix(operator_user, procedure, level="exigente")
    assert error.value.reason == "level_not_offered"
    assert not procedure.matrix_runs.exists()
