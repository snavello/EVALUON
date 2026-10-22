"""Tema s3_anexos: «Anexos técnicos y hoja de compliance» de cada oferta, dentro de la pestaña
«Ofertas» (REQ-087, REQ-088, REQ-097; decisiones 3.5 y 3.6 de la spec; plan 014, T-204).

- Anexos técnicos: las fichas y folletos del oferente se suben dentro de la oferta. Quedan como
  documento de tipo `anexo_tecnico`, fijado por la acción (`offers.services.offers.load_document`
  con `kind`), igual que la hoja de compliance: la clasificación por reglas no lo pisa. Es la
  misma carga de la 008 (huella, original, lectura en la cola, hecho `offer_load`).
- Hoja de compliance: una por oferta (decisión 3.6), rige para todos sus requisitos externos.
  Se sube con `assessment.services.compliance.upload_sheet` (mismo cambio, mismo hecho de
  auditoría `eval_decision` y mismo rol que la pantalla vieja: lo sube el evaluador). Una oferta
  sin hoja figura como faltante con su botón y suma a las cuentas de la sección y de la portada.

Cada acción es un POST que vuelve a la pestaña con el mensaje de lo hecho (firmado en la
dirección, `?aviso_anexos=`, sin guardar nada en la sesión). El bloque de cada oferta
(`offer_block` y el parcial `_s3_anexos_oferta.html`) lo incluye la tabla de ofertas del tema
s3_ofertas (T-202), en sus columnas «Anexos técnicos» y «Hoja de compliance», y el detalle de la
oferta; el mensaje de lo hecho lo muestra ese mismo tema, arriba de la tabla. Los anexos que
figuran son los vigentes (lo retirado o reemplazado va al historial de la oferta, T-206).
"""

from dataclasses import dataclass, field

from django.core import signing
from django.http import Http404
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from evaluon.accounts.models import CommissionRole
from evaluon.assessment.services import compliance
from evaluon.audit.models import Channel
from evaluon.journey import external, memo
from evaluon.journey.sections.base import Missing, TemaStatus
from evaluon.journey.tablero.tiles import Tile
from evaluon.offers.models import DocumentKind, Offer
from evaluon.offers.services import document_history
from evaluon.offers.services import offers as offers_service
from evaluon.tenders.models import Procedure

KEY = "s3_anexos"
SECTION = "ofertas"
PARTIAL = "journey/temas/s3_anexos.html"
CHANNEL = Channel.SCREEN

SALT = "journey.s3.anexos.aviso"
AVISO_MAX_AGE = 300
PARAM = "aviso_anexos"
ANCHOR = "#s3-aviso-anexos"

READING_TEXT = {
    offers_service.STATE_QUEUED: "En espera de lectura",
    offers_service.STATE_RUNNING: "Leyendo",
    offers_service.STATE_READ: "Leído",
    offers_service.STATE_FAILED: "No se pudo leer",
}


# --- Mensajes y regreso a la pestaña -------------------------------------------------------------


def pack(text, ok=True):
    return signing.dumps({"ok": ok, "m": text}, salt=SALT, compress=True)


def unpack(value):
    """El mensaje firmado de la dirección, o `None` si falta, está alterado o venció."""
    if not value:
        return None
    try:
        data = signing.loads(value, salt=SALT, max_age=AVISO_MAX_AGE)
    except signing.BadSignature:
        return None
    return {"ok": bool(data.get("ok")), "text": str(data.get("m", ""))}


def tab_url(procedure_id):
    return reverse("expedientes:ofertas", args=[procedure_id])


def back(procedure, text, ok=True):
    return redirect(f"{tab_url(procedure.pk)}?{PARAM}={pack(text, ok)}{ANCHOR}")


def _when(moment):
    """Fecha y hora en hora local (America/Argentina/Buenos_Aires), no la de la base en UTC."""
    return f"{timezone.localtime(moment):%d/%m/%Y %H:%M}"


def _day(moment):
    return f"{timezone.localtime(moment):%d/%m/%Y}"


# --- Qué cuenta en la sección --------------------------------------------------------------------


def _annexes(offer):
    """Los anexos técnicos vigentes de la oferta, en orden de carga."""
    return list(document_history.current_documents(offer)
                .filter(kind=DocumentKind.ANEXO_TECNICO).select_related("loaded_by"))


def status(user, procedure):
    """Una oferta sin hoja de compliance es un faltante, con su botón (REQ-088); suma a las
    cuentas de la sección y de la portada. Los anexos no son obligatorios: no cuentan."""
    base = tab_url(procedure.pk)
    missing, sources = [], []
    offers = list(procedure.offers.order_by("number"))
    sheets_of = compliance.sheets_by_offer(offers)
    annexes_of = document_history.current_documents_by_offer(offers, DocumentKind.ANEXO_TECNICO)
    for offer in offers:
        sheets = sheets_of[offer.pk]
        if not sheets:
            missing.append(Missing(
                f"Oferta {offer.number} ({offer.bidder}): falta la hoja de compliance",
                f"{base}#s3-anexos-oferta-{offer.number}", "Subir hoja de compliance"))
        else:
            sources.append(f"Hoja de compliance de la oferta {offer.number}: cargada el "
                           f"{_day(sheets[-1].loaded_at)}.")
        annexes = annexes_of.get(offer.pk, [])
        if annexes:
            sources.append(f"Anexos técnicos de la oferta {offer.number}: {len(annexes)} "
                           f"{'subido' if len(annexes) == 1 else 'subidos'} por la Comisión.")
    return TemaStatus(missing=tuple(missing), sources=tuple(sources))


# --- Lo que se ve --------------------------------------------------------------------------------


@dataclass
class DocView:
    document: object
    title: str
    loaded: str
    state: str
    by: str
    pages: object = None  # páginas leídas, o `None` mientras no hay lectura
    origin: str = "Archivo"  # de dónde vino: los anexos y la hoja los sube la Comisión
    day: str = ""


@dataclass
class OfferBlock:
    """Lo de una oferta: sus anexos técnicos y su hoja de compliance."""

    offer: object
    annexes: list = field(default_factory=list)
    sheets: list = field(default_factory=list)
    can_upload_annex: bool = False
    can_upload_sheet: bool = False
    # Números de los requisitos externos que esperan la hoja de la oferta (T-228).
    externals: tuple = ()

    @property
    def has_sheet(self):
        return bool(self.sheets)

    @property
    def sheet(self):
        return self.sheets[-1] if self.sheets else None


def _view(document):
    row = offers_service.document_row(document)
    report = row.reading.report if row.reading is not None else None
    return DocView(document=document, title=document.title, loaded=_when(document.loaded_at),
                   state=READING_TEXT.get(row.state, row.state),
                   by=document.loaded_by.get_username() if document.loaded_by_id else "—",
                   pages=report.get("pages") if isinstance(report, dict) else None,
                   day=_day(document.loaded_at))


def offer_block(user, offer, externals=()):
    """El bloque de una oferta, para la tabla de ofertas (T-202) y para esta pestaña. `externals`
    son los números de los requisitos externos que esperan su hoja de compliance."""
    role = getattr(user, "commission_role", "")
    return OfferBlock(
        offer=offer, externals=tuple(externals), annexes=[_view(d) for d in _annexes(offer)],
        sheets=[_view(d) for d in compliance.sheets_of(offer)],
        can_upload_annex=role in (CommissionRole.OPERATOR, CommissionRole.EVALUATOR),
        can_upload_sheet=role == CommissionRole.EVALUATOR)


def context(user, procedure, request):
    """El bloque de cada oferta y el mensaje de lo hecho los muestra la tabla de ofertas
    (s3_ofertas, T-202). El parcial propio, el detalle de «Hojas de compliance», solo resume qué
    oferta tiene su hoja y cuál no (T-326)."""
    return {"pid": procedure.pk, "rows": sheet_rows(procedure)}


# --- Tablero (REQ-126, REQ-141; plan 017, T-326) ---------------------------------------------------

DETAIL = "d-s3-anexos"


@dataclass
class SheetRow:
    """Una oferta con su hoja de compliance (o sin ella) y sus anexos técnicos."""

    offer: object
    sheet: object  # el documento de la última hoja, o `None`
    day: str = ""
    annexes: int = 0
    url: str = ""


def sheet_rows(procedure):
    """Una fila por oferta, calculada una sola vez por pedido (la usan el mosaico y el detalle)."""
    def compute():
        offers = list(procedure.offers.order_by("number"))
        sheets_of = compliance.sheets_by_offer(offers)
        annexes_of = document_history.current_documents_by_offer(offers,
                                                                  DocumentKind.ANEXO_TECNICO)
        rows = []
        for offer in offers:
            sheets = sheets_of[offer.pk]
            rows.append(SheetRow(
                offer=offer, sheet=sheets[-1] if sheets else None,
                day=_day(sheets[-1].loaded_at) if sheets else "",
                annexes=len(annexes_of.get(offer.pk, [])),
                url=f"{tab_url(procedure.pk)}?oferta={offer.pk}#s3-anexos-oferta-{offer.number}"))
        return rows
    return memo.once(("s3_anexos", "filas", procedure.pk), compute)


def numbers_text(numbers):
    """«la oferta 2», «las ofertas 2 y 3» o «las ofertas 1, 2 y 4»."""
    if len(numbers) == 1:
        return f"la oferta {numbers[0]}"
    head = ", ".join(str(n) for n in numbers[:-1])
    return f"las ofertas {head} y {numbers[-1]}"


def _waiting(user, procedure):
    """Cuántos requisitos externos esperan la hoja (los que la matriz marca como externos)."""
    page = memo.matrix_page(user, procedure.pk, channel=Channel.SCREEN)
    return len(external.requirements_of_page(page))


def tiles(user, procedure, ctx):
    """«Hojas de compliance»: cuántas ofertas tienen su hoja, de las que el sistema conoce. Sin
    ofertas, dice que faltan (REQ-141)."""
    rows = sheet_rows(procedure)
    if not rows:
        return [Tile(key="compliance", title="Hojas de compliance", detail=DETAIL,
                     missing="Falta cargar las ofertas")]
    lacking = [r.offer.number for r in rows if r.sheet is None]
    have = len(rows) - len(lacking)
    if not lacking:
        sub = "Todas las ofertas tienen su hoja"
    else:
        sub = f"Falta la hoja de {numbers_text(lacking)}"
        waiting = _waiting(user, procedure)
        if waiting:
            sub += (f". {waiting} {'requisito externo espera' if waiting == 1 else 'requisitos externos esperan'}"
                    " la hoja")
    return [Tile(key="compliance", title="Hojas de compliance", detail=DETAIL, big=have,
                 unit=f"de {len(rows)}", sub=sub)]


def opens(request):
    """El mensaje de una acción de anexos o de hojas se muestra arriba de la tabla de ofertas."""
    return "d-s3-ofertas" if request.GET.get(PARAM) else None


# --- Acciones ------------------------------------------------------------------------------------


def _procedure(procedure_id):
    try:
        return Procedure.objects.get(pk=procedure_id)
    except Procedure.DoesNotExist:
        raise Http404("No hay un procedimiento con ese número.")


def _offer(procedure, offer_id):
    try:
        return Offer.objects.get(pk=offer_id, procedure=procedure)
    except Offer.DoesNotExist:
        raise Http404("No hay una oferta con ese número en este procedimiento.")


def _file(request):
    file = request.FILES.get("file")
    return (file.read(), file.name) if file is not None else (b"", "")


@require_POST
def upload_annex(request, procedure_id, offer_id):
    """Sube un anexo técnico del oferente: documento de la oferta con el tipo fijado."""
    procedure = _procedure(procedure_id)
    offer = _offer(procedure, offer_id)
    data, name = _file(request)
    try:
        loaded = offers_service.load_document(
            request.user, offer, data=data, file_name=name,
            title=request.POST.get("title", ""), kind=DocumentKind.ANEXO_TECNICO,
            channel=CHANNEL)
    except offers_service.OfferRefused as error:
        return back(procedure, str(error), ok=False)
    return back(procedure, f"Se cargó «{loaded.document.title}» como anexo técnico de la oferta "
                           f"{offer.number}; queda en espera de lectura.")


@require_POST
def upload_sheet(request, procedure_id, offer_id):
    """Sube la hoja de compliance de la oferta (una por oferta; la sube el evaluador)."""
    procedure = _procedure(procedure_id)
    offer = _offer(procedure, offer_id)
    data, name = _file(request)
    try:
        done = compliance.upload_sheet(
            request.user, offer.pk, data=data, file_name=name,
            note=request.POST.get("note", ""), channel=CHANNEL)
    except (compliance.ComplianceRefused, offers_service.OfferRefused) as error:
        return back(procedure, str(error), ok=False)
    text = (f"Se cargó la hoja de compliance de la oferta {offer.number}; queda en espera de "
            "lectura.")
    if done.external_pending:
        text += (f" Cuando termine, el sistema evalúa de nuevo sus {done.external_pending} "
                 "requisitos externos leyendo la hoja.")
    return back(procedure, text)


urlpatterns = [
    path("ofertas/<int:offer_id>/anexo/subir/", upload_annex, name="s3_anexos_anexo"),
    path("ofertas/<int:offer_id>/compliance/subir/", upload_sheet, name="s3_anexos_hoja"),
]
