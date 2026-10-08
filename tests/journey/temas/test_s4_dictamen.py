"""Tema «dictamen» de la sección Evaluación y dictamen (REQ-092, REQ-097; plan 014, T-211). El
dictamen se toma del Portal o se sube; el sistema no lo redacta. Todo el material es inventado
(P4)."""

import re
from datetime import datetime
from datetime import timezone as dt_timezone

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import NoReverseMatch, get_resolver, reverse

from evaluon.audit.models import AuditEvent, EventType
from evaluon.audit.models import Outcome as AuditOutcome
from evaluon.journey.sections import sections_for
from evaluon.journey.temas import s4_dictamen
from evaluon.portal import models as pm
from evaluon.tenders import models as tm
from tests.journey.conftest import simulate  # noqa: F401  (fixture)
from tests.journey.temas.test_s4_propuesta import log_in, notice, page
from tests.tenders.pdfs import synthetic_tender_pdf as _new_pdf

pytestmark = pytest.mark.django_db

_PDF = []


def synthetic_tender_pdf():
    """El mismo PDF cada vez (el generado cambia de un armado al otro)."""
    if not _PDF:
        _PDF.append(_new_pdf())
    return _PDF[0]


def portal_dictamen(procedure, user, state=pm.ItemState.PROPUESTO, published="2026-10-06"):
    """Un dictamen publicado en el Portal, como lo deja la exploración: archivo e ítem."""
    link = pm.PortalLink.objects.create(url="https://portal.invalid/proceso",
                                        procedure=procedure, created_by=user)
    page_ = pm.PortalPage.objects.create(link=link, exploration=1, kind="proceso",
                                         url="https://portal.invalid/p", sha256="a" * 64,
                                         content=b"x")
    file = pm.PortalFile.objects.create(
        link=link, exploration=1, url="https://portal.invalid/dictamen.pdf",
        file_name="dictamen.pdf", file_format="pdf", sha256="c" * 64,
        content=synthetic_tender_pdf(), page=page_)
    proposal = pm.PortalProposal.objects.create(link=link, exploration=1,
                                                origin=pm.Origin.REVISION)
    fields = {}
    if state != pm.ItemState.PROPUESTO:
        fields = {"decided_by": user, "decided_at": proposal.created_at}
    return pm.PortalItem.objects.create(
        proposal=proposal, kind=pm.ItemKind.DOCUMENTO, key="dictamen-1",
        payload={"nombre": "Dictamen de la Comisión Evaluadora", "clase": "dictamen",
                 "fecha": published, "se_carga_como": "archivo",
                 "archivo": {"nombre": "dictamen.pdf", "formato": "pdf"}},
        content_sha256="d" * 64, page=page_, file=file, state=state, **fields)


def dictamen_block(html):
    return html.split('id="s4-dictamen"', 1)[1].split('id="s4-exportar"', 1)[0]


def post_upload(client, procedure, name="dictamen.pdf", data=None, **fields):
    data = synthetic_tender_pdf() if data is None else data
    return client.post(reverse("expedientes:s4_dictamen_subir", args=[procedure.pk]),
                       {"file": SimpleUploadedFile(name, data), **fields})


def take(client, procedure):
    return client.post(reverse("expedientes:s4_dictamen_tomar", args=[procedure.pk]))


def test_without_a_dictamen_the_tab_says_so_and_offers_to_upload_it(
        client, procedure, evaluator_user):
    """REQ-097: sin dictamen se ve qué falta, con «Subir el dictamen» a la vista."""
    log_in(client, evaluator_user)
    block = dictamen_block(page(client, procedure))
    assert "no cargado" in block and "Subir el dictamen" in block
    assert "el sistema no lo redacta" in block
    assert "Tomar del Portal" not in block  # el Portal no publicó nada
    section = sections_for(evaluator_user, procedure).get("evaluacion")
    assert any("Dictamen: no se cargó" in m.text and m.action == "Subir el dictamen"
               for m in section.tema_missing)


def test_a_dictamen_published_in_the_portal_appears_once_its_load_is_approved(
        client, procedure, operator_user):
    """REQ-092: el dictamen del Portal espera su aprobación; al aprobarla (el operador decide los
    documentos) aparece cargado en la sección, con quién y cuándo."""
    item = portal_dictamen(procedure, operator_user)
    log_in(client, operator_user)
    before = dictamen_block(page(client, procedure))
    assert "hay uno en el Portal, sin aprobar" in before and "Tomar del Portal" in before
    assert "06/10/2026" in before
    section = sections_for(operator_user, procedure).get("evaluacion")
    assert any(m.action == "Tomar del Portal" for m in section.tema_missing)

    ok, text = notice(client, take(client, procedure))
    assert ok and "Se tomó el dictamen del Portal" in text
    item.refresh_from_db()
    assert item.state == pm.ItemState.APROBADO and item.decided_by == operator_user
    after = dictamen_block(page(client, procedure))
    assert "Cargado desde el Portal" in after and operator_user.username in after
    assert "Tomar del Portal" not in after and '<span class="cta">cargado' in after
    section = sections_for(operator_user, procedure).get("evaluacion")
    assert not any("Dictamen" in m.text for m in section.tema_missing)
    assert any("Dictamen: del Portal" in s for s in section.sources)
    # el hecho de la 012 queda, igual que en la pestaña del Portal
    assert AuditEvent.objects.filter(event_type=EventType.PORTAL_DECISION,
                                     outcome=AuditOutcome.OK).exists()


def test_taking_without_a_dictamen_or_twice_says_why(client, procedure, operator_user):
    """El intento sin dictamen del Portal y el de uno ya decidido avisan, sin cambiar nada."""
    log_in(client, operator_user)
    ok, text = notice(client, take(client, procedure))
    assert not ok and "no publicó un dictamen" in text
    portal_dictamen(procedure, operator_user, state=pm.ItemState.RECHAZADO)
    ok, text = notice(client, take(client, procedure))
    assert not ok and "ya se decidió" in text


def test_a_rejected_dictamen_of_the_portal_still_lets_the_commission_upload_the_file(
        client, procedure, operator_user):
    """El Portal rechazado no deja la sección sin salida: se sube el archivo."""
    portal_dictamen(procedure, operator_user, state=pm.ItemState.RECHAZADO)
    log_in(client, operator_user)
    block = dictamen_block(page(client, procedure))
    assert "Se rechazó la carga del dictamen del Portal" in block
    assert "Tomar del Portal" not in block and 'id="dictamen-subir"' in block


def test_an_uploaded_dictamen_is_kept_as_a_file_and_is_not_read(
        client, procedure, evaluator_user):
    """REQ-092: el dictamen subido queda como documento de tipo dictamen, sin lectura, y la
    pestaña vuelve con el aviso, el nombre, quién y cuándo."""
    log_in(client, evaluator_user)
    jobs_before = tm.Job.objects.count()
    response = post_upload(client, procedure, title="Dictamen CD 99", issued_on="2026-10-06")
    ok, text = notice(client, response)
    assert ok and "Dictamen CD 99" in text and "no lo lee" in text
    document = tm.Document.objects.get(procedure=procedure, kind=tm.DocumentKind.DICTAMEN)
    assert document.issued_on.isoformat() == "2026-10-06"
    assert document.loaded_by == evaluator_user
    assert tm.Job.objects.count() == jobs_before
    block = dictamen_block(page(client, procedure))
    assert "Dictamen subido" in block and "Dictamen CD 99" in block
    assert evaluator_user.username in block
    assert "06/10/2026" in block and '<span class="cta">cargado' in block
    assert reverse("tenders:document_original", args=[document.pk]) in block
    section = sections_for(evaluator_user, procedure).get("evaluacion")
    assert any("Dictamen: subido por la Comisión" in s for s in section.sources)
    assert not any("Dictamen" in m.text for m in section.tema_missing)


def test_the_uploaded_dictamen_uses_the_file_name_when_there_is_no_title(
        client, procedure, operator_user):
    log_in(client, operator_user)
    notice(client, post_upload(client, procedure, name="dictamen_cd_99.pdf"))
    assert tm.Document.objects.get(kind=tm.DocumentKind.DICTAMEN).title == "dictamen cd 99"


def test_a_bad_file_or_date_is_refused_with_its_reason(client, procedure, operator_user):
    """Un archivo que no es PDF ni página web, una fecha inválida, un archivo repetido y la falta
    de archivo se rechazan con el motivo y sin cargar de más."""
    log_in(client, operator_user)
    ok, text = notice(client, post_upload(client, procedure, data=b"no es un pdf"))
    assert not ok and "no es un PDF" in text
    ok, text = notice(client, post_upload(client, procedure, issued_on="31/02/2026"))
    assert not ok and "fecha" in text
    assert not tm.Document.objects.filter(kind=tm.DocumentKind.DICTAMEN).exists()
    assert notice(client, post_upload(client, procedure))[0]
    ok, text = notice(client, post_upload(client, procedure, name="otra.pdf"))
    assert not ok and "ya está cargado" in text
    ok, text = notice(client, client.post(
        reverse("expedientes:s4_dictamen_subir", args=[procedure.pk]), {}))
    assert not ok and "Elija el archivo" in text
    assert tm.Document.objects.filter(kind=tm.DocumentKind.DICTAMEN).count() == 1


def test_without_a_commission_role_nothing_is_uploaded_or_taken(
        client, procedure, operator_user, no_commission_user):
    """Sin rol de la Comisión, «acceso denegado» (403) en las dos acciones y en la pestaña, y no
    cambia nada."""
    item = portal_dictamen(procedure, operator_user)
    log_in(client, no_commission_user)
    assert post_upload(client, procedure).status_code == 403
    assert take(client, procedure).status_code == 403
    item.refresh_from_db()
    assert item.state == pm.ItemState.PROPUESTO
    assert not tm.Document.objects.filter(kind=tm.DocumentKind.DICTAMEN).exists()
    assert client.get(reverse("expedientes:evaluacion", args=[procedure.pk])).status_code == 403


def test_there_is_no_route_or_button_to_draft_the_dictamen(client, procedure, evaluator_user):
    """REQ-092: la acción «generar borrador» no existe: ni ruta ni botón (decisión 4.4)."""
    names = {name for name in get_resolver().reverse_dict if isinstance(name, str)}
    assert not [n for n in names if "borrador" in n.lower() or "draft" in n.lower()]
    assert not [p for p in s4_dictamen.urlpatterns if "borrador" in str(p.pattern)]
    for name in ("s4_dictamen_borrador", "s4_dictamen_generar"):
        with pytest.raises(NoReverseMatch):
            reverse(f"expedientes:{name}", args=[procedure.pk])
    log_in(client, evaluator_user)
    assert not re.search(r"borrador|generar (el )?dictamen",
                         dictamen_block(page(client, procedure)), re.I)


def test_the_dictamen_block_has_no_old_links_nor_mockup_text(client, procedure, evaluator_user):
    """REQ-097: el bloque no enlaza pantallas viejas ni deja textos de la maqueta."""
    log_in(client, evaluator_user)
    block = dictamen_block(page(client, procedure))
    assert "/assessment/" not in block and "/portal/" not in block and "/tenders/" not in block
    assert "CD-99" not in block and "06/10/2026" not in block
    assert "data-tomar" not in block and "data-subir" not in block


def test_dates_are_shown_in_local_time(client, procedure, operator_user):
    """Las fechas se muestran en hora local (America/Argentina/Buenos_Aires), no en UTC."""
    log_in(client, operator_user)
    notice(client, post_upload(client, procedure))
    document = tm.Document.objects.get(kind=tm.DocumentKind.DICTAMEN)
    tm.Document.objects.filter(pk=document.pk).update(
        loaded_at=datetime(2026, 10, 8, 1, 30, tzinfo=dt_timezone.utc))
    assert "07/10/2026 22:30" in dictamen_block(page(client, procedure))
