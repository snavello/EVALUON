"""La página de Normativas general, sin procedimiento (REQ-094, REQ-096; T-225): la normativa no
está atada a ningún procedimiento. Tiene lo común de la pestaña (subir, informe de lectura,
validar, lista de normas y consulta) y subir o validar desde ella da lo mismo que desde la pestaña
de un procedimiento. Normas sintéticas, con contenido inventado (P4)."""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from evaluon.accounts.models import CommissionRole, Role
from evaluon.audit.models import AuditEvent, EventType, Outcome
from evaluon.norms.models import NormUpload, Reading, ReadingStatus
from evaluon.norms.services import loading
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.conftest import procedure  # noqa: F401  (fixture)
from tests.journey.temas.test_s5_normas import (  # noqa: F401  (fixtures y ayudas)
    NORM_FILE,
    embeddings,
    evaluator,
    log_in,
    operator,
)

pytestmark = pytest.mark.django_db

GENERAL = "/expedientes/normativas/"


def general(name, *args):
    return reverse(f"expedientes:{name}_general", args=args)


def page(client, query=""):
    response = client.get(reverse("expedientes:normativas_general") + query)
    assert response.status_code == 200
    return response.content.decode()


def load_from(client, prefix_name, args, name="rg-9999-2024.htm"):
    """Sube, completa y carga la norma con las rutas `prefix_name` (general o de un
    procedimiento). Devuelve la subida y la respuesta de la carga."""
    def route(action, *more):
        if prefix_name == "general":
            return general(action, *more)
        return reverse(f"expedientes:{action}", args=[*args, *more])

    client.post(route("s5_subir"), {"file": SimpleUploadedFile(name, NORM_FILE)})
    staged = NormUpload.objects.get(file_name=name)
    for field, entry in staged.proposal["fields"].items():
        if field in loading.REQUIRED and entry["propuesto"] is None:
            client.post(route("s5_corregir", staged.pk),
                        {"field": field, "value": "dato escrito", "reason": "Escrito"})
    response = client.post(route("s5_cargar", staged.pk), {"kind": "texto"})
    staged.refresh_from_db()
    return staged, response


def test_the_general_page_exists_without_a_procedure_with_the_mockup_header(client, operator):
    """REQ-094: sin procedimiento, la página de Normativas abre (no da 404), con el encabezado de
    la maqueta (título, «Subir archivo», resumen) y los bloques comunes, y sus formularios van a
    las rutas generales."""
    log_in(client, operator)
    html = page(client)
    assert reverse("expedientes:normativas_general") == GENERAL
    assert '<h2 id="seccion-titulo">Normativas</h2>' in html
    assert 'href="#s5-subir"' in html and "Subir archivo" in html
    assert "no están atadas a ningún procedimiento" in html
    assert "Subir una norma" in html and 'id="s5-normas"' in html
    assert f'action="{general("s5_subir")}"' in html
    assert "Consulta de normativa" in html and reverse("queries:screen") in html
    assert "Pendientes de decidir" in html


def test_the_general_page_needs_a_commission_role(client, read_write_user):
    """P3, P6: sin rol de la Comisión, acceso denegado y el rechazo queda registrado."""
    log_in(client, read_write_user)
    before = AuditEvent.objects.filter(event_type=EventType.REJECTED).count()
    assert client.get(GENERAL).status_code == 403
    assert AuditEvent.objects.filter(event_type=EventType.REJECTED).count() == before + 1


def test_uploading_and_validating_from_the_general_page_is_the_same_as_from_a_procedure(
        client, procedure, evaluator):
    """REQ-094: subir, cargar y validar desde la página general vuelve a ella con el aviso y deja
    lo mismo (subida, norma, lectura validada, hechos) que hacerlo desde la pestaña de un
    procedimiento, y la norma se ve en las dos."""
    log_in(client, evaluator)
    staged, response = load_from(client, "general", ())
    assert response.status_code == 302 and response["Location"].startswith(GENERAL)
    assert staged.state == "aprobado"
    reading = Reading.objects.get(document=staged.document)
    html = page(client, f"?lectura={reading.pk}")
    assert f'action="{general("s5_validar", reading.pk)}"' in html
    validated = client.post(general("s5_validar", reading.pk))
    assert validated.status_code == 302 and validated["Location"].startswith(GENERAL)
    reading.refresh_from_db()
    assert reading.status == ReadingStatus.VALIDATED
    tab = client.get(reverse("expedientes:normativas", args=[procedure.pk])).content.decode()
    general_html = page(client)
    for html in (tab, general_html):
        assert "Resolución General 9999/2024" in html or "9999/2024" in html
    events = AuditEvent.objects.filter(event_type=EventType.NORM_UPLOAD, outcome=Outcome.OK)
    assert sorted(e.detail["action"] for e in events) == ["confirm", "stage"]
    assert all(e.channel == "screen" for e in events)


def test_the_procedure_tab_keeps_its_own_routes(client, procedure, operator):
    """REQ-094: la pestaña de un procedimiento sigue subiendo con sus rutas y vuelve a ella."""
    log_in(client, operator)
    html = client.get(reverse("expedientes:normativas", args=[procedure.pk])).content.decode()
    assert f'action="{reverse("expedientes:s5_subir", args=[procedure.pk])}"' in html
    response = client.post(reverse("expedientes:s5_subir", args=[procedure.pk]),
                           {"file": SimpleUploadedFile("rg.htm", NORM_FILE)})
    assert response["Location"].startswith(f"/expedientes/{procedure.pk}/normativas/")


def test_the_general_page_is_reachable_from_the_new_procedure_screen_and_the_dropdown(
        client, procedure, operator):
    """REQ-094: se llega desde la pantalla de alta (pestaña Normativas) y desde el desplegable
    de procedimientos."""
    log_in(client, operator)
    new = client.get(reverse("expedientes:nuevo")).content.decode()
    bar = new[new.index('id="barra-secciones"'):new.index('id="journey-status"')]
    assert f'href="{GENERAL}"' in bar
    portada = client.get(reverse("expedientes:portada", args=[procedure.pk])).content.decode()
    menu = portada[portada.index('class="sel-proc"'):portada.index("</details>")]
    assert f'href="{GENERAL}"' in menu
    html = page(client)
    menu = html[html.index('class="sel-proc"'):html.index("</details>")]
    assert f'href="{GENERAL}"' in menu and "Normativas" in menu
    assert reverse("expedientes:portada", args=[procedure.pk]) in menu


def make_user(name, commission):
    return get_user_model().objects.create_user(
        username=name, password=TEST_PASSWORD, role=Role.READ_WRITE, commission_role=commission)


def test_an_operator_discards_its_upload_from_the_general_page(client):
    """REQ-094: «Descartar esta subida» también funciona desde la página general."""
    user = make_user("operador-general", CommissionRole.OPERATOR)
    log_in(client, user)
    client.post(general("s5_subir"), {"file": SimpleUploadedFile("rg.htm", NORM_FILE)})
    staged = NormUpload.objects.get()
    assert general("s5_descartar", staged.pk) in page(client)
    response = client.post(general("s5_descartar", staged.pk), {"reason": "Equivocada."})
    assert response["Location"].startswith(GENERAL)
    staged.refresh_from_db()
    assert staged.state == "rechazado"
