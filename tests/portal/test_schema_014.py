"""Esquema de la 014 en `portal` (T-193; plan 014, "Modelo de datos"; ADR-0049): renglones,
expediente y CUIT con documento de origen, exactamente uno entre el ítem del Portal y el
documento. Textos inventados (P4)."""

import hashlib
from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from evaluon.offers import models as om
from evaluon.portal import models as p
from evaluon.tenders import models as tm

pytestmark = pytest.mark.django_db


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.fixture
def procedure(read_write_user):
    return tm.Procedure.objects.create(
        number="PROC-014-P-1", procedure_type="Licitación pública",
        subject="Objeto sintético", authorization_date=date(2025, 11, 14),
        created_by=read_write_user)


@pytest.fixture
def tender_document(procedure, read_write_user):
    return tm.Document.objects.create(
        procedure=procedure, kind=tm.DocumentKind.PLIEGO, title="Pliego",
        file_name="p.pdf", file_format="pdf", file_size=1, file_sha256=sha("pliego"),
        loaded_by=read_write_user)


@pytest.fixture
def offer(procedure, read_write_user):
    return om.Offer.objects.create(procedure=procedure, number=1, bidder="Oferente SA",
                                   created_by=read_write_user)


@pytest.fixture
def offer_document(offer, read_write_user):
    return om.Document.objects.create(
        offer=offer, title="Oferta", file_name="o.pdf", file_format="pdf", file_size=1,
        file_sha256=sha("oferta"), loaded_by=read_write_user)


@pytest.fixture
def item(read_write_user):
    link = p.PortalLink.objects.create(url="https://portal.ejemplo.test/x?qs=1",
                                       created_by=read_write_user)
    page = p.PortalPage.objects.create(link=link, exploration=1, kind=p.PageKind.PROCESO,
                                       url=link.url, sha256=sha("pagina"), content=b"<html/>")
    proposal = p.PortalProposal.objects.create(link=link, exploration=1,
                                               origin=p.Origin.IMPORTACION)
    return p.PortalItem.objects.create(proposal=proposal, kind=p.ItemKind.RENGLONES,
                                       key="renglones", payload={},
                                       content_sha256=sha("item"), page=page)


# --- Renglones ----------------------------------------------------------------------------


def test_a_line_comes_from_the_portal_item_or_from_the_tender_document(
        procedure, item, tender_document):
    """REQ-077, REQ-078: el renglón propuesto desde el pliego se guarda en la misma tabla,
    con su documento de origen; el del Portal, con su ítem."""
    from_portal = p.PortalLine.objects.create(procedure=procedure, number=1,
                                              description="Resma", item=item)
    from_tender = p.PortalLine.objects.create(procedure=procedure, number=2,
                                              description="Tóner", quantity=Decimal("5"),
                                              document=tender_document)
    assert (from_portal.document, from_tender.item) == (None, None)
    assert tender_document.portal_lines.get() == from_tender


def test_a_line_needs_exactly_one_origin(procedure, item, tender_document):
    """REQ-077: sin origen, o con los dos, se rechaza."""
    for fields in ({}, {"item": item, "document": tender_document}):
        with pytest.raises(IntegrityError), transaction.atomic():
            p.PortalLine.objects.create(procedure=procedure, number=9,
                                        description="x", **fields)


def test_the_line_number_stays_unique_per_procedure(procedure, item, tender_document):
    p.PortalLine.objects.create(procedure=procedure, number=1, description="a", item=item)
    with pytest.raises(IntegrityError), transaction.atomic():
        p.PortalLine.objects.create(procedure=procedure, number=1, description="b",
                                    document=tender_document)


# --- Datos del procedimiento --------------------------------------------------------------


def test_the_procedure_data_comes_from_one_origin(procedure, item, tender_document):
    """REQ-077, REQ-078: el expediente propuesto desde el pliego lleva el documento."""
    data = p.PortalProcedureData.objects.create(procedure=procedure, file_number="EX-1",
                                                document=tender_document)
    assert data.item is None and data.document == tender_document


def test_the_procedure_data_needs_exactly_one_origin(procedure, item, tender_document):
    for fields in ({}, {"item": item, "document": tender_document}):
        with pytest.raises(IntegrityError), transaction.atomic():
            p.PortalProcedureData.objects.create(procedure=procedure, file_number="EX-1",
                                                 **fields)


# --- CUIT de la oferta --------------------------------------------------------------------


def test_the_cuit_comes_from_the_act_or_from_an_offer_document(
        offer, offer_document, item):
    """REQ-083: el CUIT propuesto desde los archivos de la oferta lleva su documento."""
    data = p.PortalOfferData.objects.create(offer=offer, cuit="30-00000000-0",
                                            document=offer_document)
    assert data.item is None and data.document == offer_document


def test_the_offer_data_needs_exactly_one_origin(offer, offer_document, item):
    for fields in ({}, {"item": item, "document": offer_document}):
        with pytest.raises(IntegrityError), transaction.atomic():
            p.PortalOfferData.objects.create(offer=offer, cuit="30-00000000-0", **fields)


def test_the_offer_data_from_the_portal_still_works(offer, item):
    """Lo existente no cambia: el acta del Portal sigue cargando con su ítem."""
    data = p.PortalOfferData.objects.create(offer=offer, cuit="30-00000000-0", item=item)
    assert data.document is None
    guarantee = p.PortalGuarantee.objects.create(offer_data=data, item=item)
    assert guarantee.offer_data == data


def test_a_document_with_portal_data_cannot_be_deleted(procedure, tender_document):
    """P6: el documento de origen no se borra mientras haya datos que lo citan."""
    p.PortalLine.objects.create(procedure=procedure, number=1, description="x",
                                document=tender_document)
    with pytest.raises(Exception), transaction.atomic():
        tender_document.delete()
