"""Registrar un procedimiento y mostrar su régimen (REQ-022; plan 003, "Procedimiento y
documentos", "Roles", "Pantalla" y "Registro de auditoría"; T-069).

Los regímenes son los de prueba de la 001 (`two_regimes`): "Disposición AFIP 297/03"
hasta el 2023-01-01 y "Disposición AFIP 247/2022" desde el 2023-01-02. Los números,
tipos y objetos de los procedimientos son sintéticos (P4).
"""

import html
from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from evaluon.accounts.permissions import RoleRejected
from evaluon.audit import services as audit_services
from evaluon.audit.models import AuditEvent, Channel, EventType, Outcome
from evaluon.tenders.models import MatrixVersion, Procedure, VersionStatus
from evaluon.tenders.services import procedures
from tests.conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db

OLD_LINE = "Procedimiento autorizado el 15/12/2022 · Régimen aplicado: Disposición AFIP 297/03"
NEW_LINE = "Procedimiento autorizado el 02/01/2023 · Régimen aplicado: Disposición AFIP 247/2022"
NO_REGIME_TEXT = "Para esa fecha no hay un régimen específico cargado en el sistema"
NAV_LINK = 'href="/procedimientos/"'


def register(user, number="SINT-0001-LPU22", authorization_date=date(2022, 12, 15),
             **fields):
    return procedures.register_procedure(
        user,
        number=number,
        procedure_type=fields.get("procedure_type", "Licitación pública"),
        subject=fields.get("subject", "Adquisición sintética de equipos de prueba"),
        authorization_date=authorization_date,
    )


def procedure_events():
    return AuditEvent.objects.filter(event_type=EventType.PROCEDURE)


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def page_text(response):
    return html.unescape(response.content.decode())


def post_form(client, number="SINT-0001-LPU22", authorization_date="2022-12-15"):
    return client.post(reverse("tenders:procedures"), {
        "number": number,
        "procedure_type": "Licitación pública",
        "subject": "Adquisición sintética de equipos de prueba",
        "authorization_date": authorization_date,
    })


# --- Función de negocio -----------------------------------------------------------------


def test_procedure_authorized_2022_12_15_gets_disposicion_297_03(operator_user,
                                                                 two_regimes):
    """REQ-022: autorizado el 2022-12-15, el régimen es la Disposición 297/03."""
    outcome = register(operator_user, authorization_date=date(2022, 12, 15))

    assert outcome.regime == [{"norm": two_regimes.old.pk,
                               "name": "Disposición AFIP 297/03"}]
    procedure = Procedure.objects.get()
    assert procedure == outcome.procedure
    assert procedure.number == "SINT-0001-LPU22"
    assert procedure.procedure_type == "Licitación pública"
    assert procedure.subject == "Adquisición sintética de equipos de prueba"
    assert procedure.authorization_date == date(2022, 12, 15)
    assert procedure.created_by == operator_user


def test_procedure_authorized_2023_01_02_gets_disposicion_247_2022(operator_user,
                                                                   two_regimes):
    """REQ-022: autorizado el 2023-01-02, el régimen es la Disposición 247/2022."""
    outcome = register(operator_user, authorization_date=date(2023, 1, 2))

    assert outcome.regime == [{"norm": two_regimes.new.pk,
                               "name": "Disposición AFIP 247/2022"}]


def test_regime_is_the_one_of_applicable_regimes(operator_user, two_regimes):
    """REQ-022: el régimen sale de `applicable_regimes` de la 001, sin otra regla."""
    from evaluon.queries.services import applicable_regimes

    for day in (date(2022, 12, 15), date(2023, 1, 2), two_regimes.after_v):
        assert procedures.regime_for(day) == applicable_regimes(day)


def test_future_date_is_refused_without_saving(operator_user, two_regimes):
    """REQ-022: una fecha de autorización posterior al día se rechaza: no queda el
    procedimiento ni el hecho `procedure`."""
    tomorrow = timezone.localdate() + timedelta(days=1)

    with pytest.raises(procedures.FutureDate):
        register(operator_user, authorization_date=tomorrow)

    assert not Procedure.objects.exists()
    assert not procedure_events().exists()


def test_today_is_accepted(operator_user, two_regimes):
    """REQ-022: la fecha del día no es futura."""
    outcome = register(operator_user, authorization_date=timezone.localdate())

    assert outcome.procedure.authorization_date == timezone.localdate()


def test_repeated_number_is_refused(operator_user, evaluator_user, two_regimes):
    """REQ-022: el número del procedimiento es único; uno repetido se rechaza y no
    deja un segundo procedimiento ni un segundo hecho."""
    register(operator_user, number="SINT-0002-LPU23", authorization_date=date(2023, 1, 2))

    with pytest.raises(procedures.DuplicateNumber):
        register(evaluator_user, number=" SINT-0002-LPU23 ",
                 authorization_date=date(2022, 12, 15))

    assert Procedure.objects.count() == 1
    assert procedure_events().count() == 1


@pytest.mark.parametrize("field", ["number", "procedure_type", "subject"])
def test_empty_field_is_refused(operator_user, two_regimes, field):
    """REQ-022: número, tipo y objeto son obligatorios."""
    data = {"number": "SINT-0003-LPU23", "procedure_type": "Licitación pública",
            "subject": "Objeto sintético", field: "   "}

    with pytest.raises(procedures.ProcedureRefused):
        procedures.register_procedure(operator_user, authorization_date=date(2023, 1, 2),
                                      **data)

    assert not Procedure.objects.exists()


def test_event_keeps_regime_and_corpus_version(operator_user, read_write_user,
                                               two_regimes):
    """REQ-022 (P6, P8): el hecho `procedure` guarda número, tipo, objeto, fecha, el
    régimen mostrado y la versión de la normativa vigente al registrar."""
    version_event = audit_services.record(
        EventType.VALIDATION, outcome=Outcome.OK, channel=Channel.COMMAND,
        user=read_write_user, creates_corpus_version=True,
    )

    outcome = register(operator_user, authorization_date=date(2022, 12, 15))

    event = procedure_events().get()
    assert event == outcome.event
    assert event.outcome == Outcome.OK
    assert event.channel == Channel.SCREEN
    assert event.user == operator_user
    assert event.corpus_version == version_event.corpus_version
    assert outcome.corpus_version == version_event.corpus_version
    assert event.detail == {
        "procedure": outcome.procedure.pk,
        "number": "SINT-0001-LPU22",
        "procedure_type": "Licitación pública",
        "subject": "Adquisición sintética de equipos de prueba",
        "authorization_date": "2022-12-15",
        "regime": [{"norm": two_regimes.old.pk, "name": "Disposición AFIP 297/03"}],
        "corpus_version": version_event.corpus_version,
    }


def test_event_without_regime_at_the_date(operator_user, two_regimes):
    """REQ-022: sin régimen cargado a la fecha, se registra igual, con régimen vacío."""
    outcome = register(operator_user, authorization_date=two_regimes.before_all)

    assert outcome.regime == []
    assert procedure_events().get().detail["regime"] == []


def test_evaluator_can_register(evaluator_user, two_regimes):
    """REQ-022 (plan 003, "Roles"): el evaluador también registra."""
    register(evaluator_user)

    assert Procedure.objects.get().created_by == evaluator_user


def test_user_without_commission_role_cannot_register_or_list(no_commission_user,
                                                              two_regimes):
    """REQ-022 (plan 003, "Roles"): sin rol de la Comisión no se registra ni se lista,
    aunque el usuario escriba en la normativa; cada rechazo deja el hecho `rejected`
    con una operación legible."""
    with pytest.raises(RoleRejected):
        register(no_commission_user)
    with pytest.raises(RoleRejected):
        procedures.list_procedures(no_commission_user)

    assert not Procedure.objects.exists()
    rejected = AuditEvent.objects.filter(event_type=EventType.REJECTED).order_by("id")
    assert [event.detail["operation"] for event in rejected] == [
        procedures.REGISTER_OPERATION, procedures.LIST_OPERATION,
    ]
    assert all(event.user == no_commission_user for event in rejected)


def test_list_shows_regime_and_matrix_status(operator_user, evaluator_user,
                                             two_regimes):
    """REQ-022: la lista trae cada procedimiento con su régimen calculado a su fecha y
    el estado de su matriz, el más reciente primero."""
    old = register(operator_user, number="SINT-0004-LPU22",
                   authorization_date=date(2022, 12, 15)).procedure
    new = register(operator_user, number="SINT-0005-LPU23",
                   authorization_date=date(2023, 1, 2)).procedure
    MatrixVersion.objects.create(procedure=new, number=1, level="alta",
                                 created_by=evaluator_user)

    rows = procedures.list_procedures(operator_user)

    assert [row.procedure for row in rows] == [new, old]
    assert rows[0].regime == [{"norm": two_regimes.new.pk,
                               "name": "Disposición AFIP 247/2022"}]
    assert rows[1].regime == [{"norm": two_regimes.old.pk,
                               "name": "Disposición AFIP 297/03"}]
    assert rows[0].matrix.number == 1
    assert rows[0].matrix.status == VersionStatus.DRAFT
    assert rows[1].matrix is None


# --- Pantalla ---------------------------------------------------------------------------


def test_screen_refuses_future_date(client, operator_user, two_regimes):
    """REQ-022: una fecha futura vuelve marcada en el formulario y no registra."""
    log_in(client, operator_user)
    tomorrow = timezone.localdate() + timedelta(days=1)

    response = post_form(client, authorization_date=tomorrow.isoformat())

    assert response.status_code == 200
    assert "La fecha de autorización no puede ser posterior a hoy" in page_text(response)
    assert not Procedure.objects.exists()
    assert not procedure_events().exists()


def test_screen_refuses_repeated_number(client, operator_user, two_regimes):
    """REQ-022: un número repetido vuelve marcado en el formulario y no registra."""
    register(operator_user, number="SINT-0008-LPU23", authorization_date=date(2023, 1, 2))
    log_in(client, operator_user)

    response = post_form(client, number="SINT-0008-LPU23")

    assert response.status_code == 200
    assert procedures.DUPLICATE_NUMBER_MESSAGE in page_text(response)
    assert Procedure.objects.count() == 1
