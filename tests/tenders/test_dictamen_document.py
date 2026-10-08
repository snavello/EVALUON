"""El dictamen subido como documento del procedimiento (REQ-092; plan 014, T-211): se guarda
como archivo, no se lee, no encola pedido y la matriz no lo toma como documento base. Material
inventado (P4)."""

import pytest

from evaluon.audit.models import Outcome
from evaluon.tenders import models as m
from evaluon.tenders.services import documents
from evaluon.tenders.services import matrix as matrix_service
from tests.tenders.pdfs import synthetic_tender_pdf as _new_pdf
from tests.tenders.test_documents import annex_pdf
from tests.tenders.test_documents import load, load_events, procedure  # noqa: F401

pytestmark = pytest.mark.django_db

_PDF = []


def synthetic_tender_pdf():
    """El mismo PDF cada vez (el generado cambia de un armado al otro)."""
    if not _PDF:
        _PDF.append(_new_pdf())
    return _PDF[0]


def load_dictamen(user, procedure, **extra):
    return load(user, procedure, synthetic_tender_pdf(), kind=m.DocumentKind.DICTAMEN,
                title="Dictamen sintético", file_name="dictamen-sintetico.pdf", **extra)


def test_a_dictamen_is_kept_but_its_reading_is_not_queued(operator_user, procedure):
    """REQ-092: el dictamen subido no se lee: se guarda el original con su huella y el hecho
    `tender_load`, pero no hay pedido de lectura."""
    loaded = load_dictamen(operator_user, procedure)

    assert loaded.job is None
    assert loaded.document.kind == m.DocumentKind.DICTAMEN
    assert bytes(loaded.document.file.content) == synthetic_tender_pdf()
    assert not m.Job.objects.filter(kind=m.JobKind.READ_DOCUMENT).exists()
    event = load_events(Outcome.OK).get()
    assert event.detail["kind"] == "dictamen" and event.detail["job"] is None
    assert event.detail["document"] == loaded.document.pk


def test_a_dictamen_does_not_need_a_date(operator_user, procedure):
    """REQ-092: el dictamen lleva fecha optativa (no es una circular)."""
    assert load_dictamen(operator_user, procedure).document.issued_on is None


def test_the_matrix_does_not_take_the_dictamen_as_a_base_document(operator_user, procedure):
    """REQ-092: la matriz parte solo del pliego, los anexos y las especificaciones."""
    load_dictamen(operator_user, procedure)
    assert list(matrix_service.base_documents(procedure)) == []
    pliego = load(operator_user, procedure, annex_pdf(), title="Pliego sintético",
                  file_name="pliego-sintetico.pdf").document
    assert list(matrix_service.base_documents(procedure)) == [pliego]


def test_a_pliego_still_queues_its_reading(operator_user, procedure):
    """El ajuste no cambia el resto: un pliego sigue encolando su lectura."""
    loaded = load(operator_user, procedure, synthetic_tender_pdf())
    assert loaded.job.kind == m.JobKind.READ_DOCUMENT


def test_a_repeated_dictamen_is_refused_like_any_document(operator_user, procedure):
    """El mismo archivo dos veces se rechaza también para el dictamen."""
    load_dictamen(operator_user, procedure)
    with pytest.raises(documents.DuplicateFile):
        load_dictamen(operator_user, procedure)
