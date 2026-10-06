"""Esquema de la importación desde el Portal (T-138; plan 012, "Modelo de datos" e
"Inmutabilidad"; ADR-0030).

Las restricciones y los triggers los hace valer la base: se prueban con SQL directo y con
el modelo. Todos los datos son inventados (P4).
"""

import hashlib
from datetime import date
from decimal import Decimal

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.utils import timezone

from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.offers.models import Offer
from evaluon.portal import models as p

pytestmark = pytest.mark.django_db

PORTAL_TABLES = {
    "portal_link", "portal_page", "portal_file", "portal_proposal", "portal_item",
    "portal_procedure_data", "portal_line", "portal_offer_data", "portal_quote",
}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.fixture
def link(read_write_user):
    return p.PortalLink.objects.create(
        url="https://portal.ejemplo.test/PLIEGO/x.aspx?qs=1", created_by=read_write_user)


@pytest.fixture
def page(link):
    return p.PortalPage.objects.create(
        link=link, exploration=1, kind=p.PageKind.PROCESO, url=link.url,
        sha256=sha("pagina"), content=b"<html>inventado</html>")


@pytest.fixture
def proposal(link):
    return p.PortalProposal.objects.create(
        link=link, exploration=1, origin=p.Origin.IMPORTACION)


@pytest.fixture
def item(proposal, page):
    return p.PortalItem.objects.create(
        proposal=proposal, kind=p.ItemKind.PROCEDIMIENTO, key="procedimiento",
        payload={"numero": "X-1"}, content_sha256=sha("x"), page=page)


def test_all_portal_tables_exist():
    """REQ-045, REQ-049: están las nueve tablas del plan."""
    with connection.cursor() as cursor:
        names = set(connection.introspection.table_names(cursor))
    assert PORTAL_TABLES <= names


# --- Solo inserción -------------------------------------------------------------------


def test_pages_are_append_only(page):
    """REQ-049: una página bajada no se modifica ni se borra, ni con el modelo ni con SQL
    directo."""
    with pytest.raises(DatabaseError), transaction.atomic():
        p.PortalPage.objects.filter(pk=page.pk).update(content=b"cambiado")
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("UPDATE portal_page SET url = 'otra' WHERE id = %s", [page.pk])
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM portal_page WHERE id = %s", [page.pk])
    page.refresh_from_db()
    assert bytes(page.content) == b"<html>inventado</html>"


def test_files_are_append_only(link, page):
    """REQ-049: un archivo bajado no se modifica ni se borra."""
    file = p.PortalFile.objects.create(
        link=link, exploration=1, url=link.url + "&f=1", file_name="pliego.pdf",
        file_format="pdf", sha256=sha("archivo"), content=b"%PDF inventado", page=page)
    with pytest.raises(DatabaseError), transaction.atomic():
        p.PortalFile.objects.filter(pk=file.pk).update(file_name="otro.pdf")
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM portal_file WHERE id = %s", [file.pk])
    assert p.PortalFile.objects.filter(pk=file.pk, file_name="pliego.pdf").exists()


def test_item_content_cannot_change_but_state_can(item, read_write_user):
    """REQ-048, REQ-049: el contenido de un ítem no se modifica; el estado y la decisión
    sí cambian."""
    for change in (
        {"payload": {"numero": "otro"}},
        {"content_sha256": sha("otro")},
        {"key": "otra-clave"},
        {"kind": p.ItemKind.DOCUMENTO},
        {"damaged_fields": ["objeto"]},
    ):
        with pytest.raises(DatabaseError), transaction.atomic():
            p.PortalItem.objects.filter(pk=item.pk).update(**change)
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE portal_item SET payload = '{}'::jsonb WHERE id = %s", [item.pk])

    p.PortalItem.objects.filter(pk=item.pk).update(
        state=p.ItemState.APROBADO, decided_by=read_write_user, decided_at=timezone.now())
    item.refresh_from_db()
    assert item.state == p.ItemState.APROBADO
    assert item.payload == {"numero": "X-1"}


# --- Restricciones --------------------------------------------------------------------


def test_link_url_is_unique(link, read_write_user):
    """REQ-045: un enlace ya registrado no se registra de nuevo."""
    with pytest.raises(IntegrityError), transaction.atomic():
        p.PortalLink.objects.create(url=link.url, created_by=read_write_user)


def test_invalid_values_are_rejected(link, page, proposal, item):
    """Los valores de dominio y las huellas se comprueban en la base."""
    with pytest.raises(IntegrityError), transaction.atomic():
        p.PortalPage.objects.create(
            link=link, exploration=1, kind="otro", url="u", sha256=sha("a"), content=b"x")
    with pytest.raises(IntegrityError), transaction.atomic():
        p.PortalPage.objects.create(
            link=link, exploration=1, kind=p.PageKind.ACTA, url="u", sha256="corta",
            content=b"x")
    with pytest.raises(IntegrityError), transaction.atomic():
        p.PortalItem.objects.create(
            proposal=proposal, kind="otro", key="k", payload={}, content_sha256=sha("k"),
            page=page)
    with pytest.raises(IntegrityError), transaction.atomic():
        p.PortalItem.objects.create(
            proposal=proposal, kind=p.ItemKind.RENGLONES, key="k", payload={},
            content_sha256=sha("k"), page=page, state="otro")
    with pytest.raises(IntegrityError), transaction.atomic():  # misma clave en la propuesta
        p.PortalItem.objects.create(
            proposal=proposal, kind=item.kind, key=item.key, payload={},
            content_sha256=sha("z"), page=page)


def test_decided_item_needs_author_and_loaded_item_needs_object(proposal, page):
    """REQ-048: un ítem decidido dice quién y cuándo; uno cargado, qué objeto creó."""
    with pytest.raises(IntegrityError), transaction.atomic():
        p.PortalItem.objects.create(
            proposal=proposal, kind=p.ItemKind.RENGLONES, key="a", payload={},
            content_sha256=sha("a"), page=page, state=p.ItemState.RECHAZADO)
    with pytest.raises(IntegrityError), transaction.atomic():
        p.PortalItem.objects.create(
            proposal=proposal, kind=p.ItemKind.RENGLONES, key="b", payload={},
            content_sha256=sha("b"), page=page, state=p.ItemState.CARGADO)


def test_data_without_a_place_points_to_its_item(item, procedure, read_write_user):
    """REQ-049: renglones, datos del procedimiento, de la oferta y cotizaciones guardan el
    ítem que los originó; el renglón es único por procedimiento y número, y la cotización
    por oferta y renglón."""
    data = p.PortalProcedureData.objects.create(
        procedure=procedure, file_number="EX-0001", legal_framework="Régimen inventado",
        schedule=[{"hito": "apertura", "fecha": "2025-12-01"}], guarantees=[], item=item)
    assert data.item == item
    line = p.PortalLine.objects.create(
        procedure=procedure, number=1, description="Resma de papel", quantity=Decimal("10"),
        unit="unidad", item=item)
    with pytest.raises(IntegrityError), transaction.atomic():
        p.PortalLine.objects.create(
            procedure=procedure, number=1, description="Otra", item=item)
    offer = Offer.objects.create(
        procedure=procedure, number=1, bidder="Oferente Inventado SA", created_by=read_write_user)
    extra = p.PortalOfferData.objects.create(
        offer=offer, cuit="30-00000000-0", confirmed_on=date(2025, 12, 1), currency="ARS",
        total=Decimal("1000.50"), guarantee_type="Oferta", guarantee_form="Póliza",
        guarantee_amount=Decimal("10.00"), item=item)
    assert extra.item == item
    p.PortalQuote.objects.create(
        offer=offer, line=line, price=Decimal("100.0000"), quantity=Decimal("10"))
    with pytest.raises(IntegrityError), transaction.atomic():
        p.PortalQuote.objects.create(offer=offer, line=line, price=Decimal("1"))


# --- Auditoría ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event_type",
    [EventType.PORTAL_LINK, EventType.PORTAL_EXPLORE, EventType.PORTAL_REVIEW,
     EventType.PORTAL_DECISION],
)
def test_audit_accepts_the_portal_events(event_type, read_write_user):
    """P6: los cuatro hechos del Portal se pueden registrar; los tipos caben en el campo."""
    assert len(event_type.value) <= 20
    event = audit.record(
        event_type, outcome=Outcome.OK, channel=Channel.SCREEN, user=read_write_user,
        detail={"link": 1})
    event.refresh_from_db()
    assert event.event_type == event_type.value


def test_audit_rejects_unknown_events_in_the_database(read_write_user):
    """P6: la restricción de la base sigue rechazando un tipo que no existe."""
    with pytest.raises(IntegrityError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO audit_event (occurred_at, event_type, outcome, channel, "
                "username, detail) VALUES (now(), 'portal_otro', 'ok', 'screen', '', '{}')")
