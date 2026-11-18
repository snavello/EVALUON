"""Un paso «Hecho» vuelve solo a «En curso» cuando aparece algo nuevo que le corresponde
(REQ-145; plan 018, T-345), sin que nadie lo marque y sin guardar ninguna fase."""

from datetime import date

import pytest

from evaluon.journey.proceso import calculo, pasos
from evaluon.offers.models import Document as OfferDocument
from evaluon.offers.models import DocumentFile as OfferDocumentFile
from evaluon.tenders import models as m
from evaluon.tenders.services import documents as tender_documents

pytestmark = pytest.mark.django_db

HECHO, EN_CURSO = pasos.Estado.HECHO, pasos.Estado.EN_CURSO


def _estados(caso, numeros=(1, 2, 3)):
    proceso = calculo.proceso_de(caso.user, caso.procedure)
    return {p.numero: p.estado for p in proceso.pasos if p.numero in numeros}, proceso


def test_req145_circular_modificatoria_reabre_el_paso_2(caso_todo_hecho):
    """REQ-145: con la matriz validada (paso 2 «Hecho»), una circular modificatoria nueva lo pasa
    a «En curso» y dice que hay una circular posterior a la matriz; el paso 1 también (la circular
    todavía no se leyó). El paso 3 no cambia."""
    caso = caso_todo_hecho
    antes, _ = _estados(caso)
    assert antes == {1: HECHO, 2: HECHO, 3: HECHO}
    tender_documents.load_document(
        caso.user, caso.procedure, data=b"%PDF-1.4 circular sintetica", file_name="circular.pdf",
        kind=m.DocumentKind.CIRCULAR_MODIFICATORIA, title="Circular 1 (inventada)",
        issued_on=date(2026, 10, 1))
    despues, proceso = _estados(caso)
    assert despues == {1: EN_CURSO, 2: EN_CURSO, 3: HECHO}
    assert "circular modificatoria posterior a la matriz" in proceso.pasos[1].resumen
    assert proceso.pasos[0].dato == "Pliego, 0 anexos, 1 circular"


def test_req145_documento_nuevo_en_una_oferta_reabre_el_paso_3(caso_todo_hecho):
    """REQ-145: un documento agregado a una oferta y todavía sin lectura vuelve el paso 3 a
    «En curso»; los pasos 1 y 2 siguen «Hecho»."""
    caso = caso_todo_hecho
    nuevo = OfferDocument.objects.create(
        offer=caso.offers[0], title="subsanacion.pdf", file_name="subsanacion.pdf",
        file_format="pdf", file_size=1, file_sha256="e" * 64, loaded_by=caso.user)
    OfferDocumentFile.objects.create(document=nuevo, content=b"%PDF-sintetico")
    estados, proceso = _estados(caso)
    assert estados == {1: HECHO, 2: HECHO, 3: EN_CURSO}
    assert "Faltan leer" in proceso.pasos[2].resumen


def test_req145_el_estado_vuelve_solo_al_quitar_lo_nuevo(caso_todo_hecho):
    """REQ-145: no se guarda una fase: si lo nuevo desaparece, el paso vuelve a «Hecho»."""
    caso = caso_todo_hecho
    nuevo = OfferDocument.objects.create(
        offer=caso.offers[0], title="x.pdf", file_name="x.pdf", file_format="pdf", file_size=1,
        file_sha256="d" * 64, loaded_by=caso.user)
    assert _estados(caso)[0][3] is EN_CURSO
    nuevo.delete()
    assert _estados(caso)[0][3] is HECHO
