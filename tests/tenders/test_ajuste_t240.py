"""T-240 (ronda de ajuste única de la 015, ADR-0025): los hallazgos de código de la medición T-239
que tocan la propuesta de la matriz. Un bloque por hallazgo. Pliegos sintéticos (P4), modelo con
guion (`tests/tenders/scripted.py`), sin GPU.

- H-7: los tramos de un documento técnico anexo van a las filas técnicas por renglón, como manda
  la regla técnica, y no quedan como requisitos formales sueltos (REQ-101, REQ-102).
"""

import pytest

from evaluon.tenders import models as m
from evaluon.tenders.proposal import run as proposal_run
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import (
    ENTREGA,
    item,
    load_and_read,
    make_procedure,
    propose,
    script,  # noqa: F401  (fixture)
    three_items_pdf,
)

pytestmark = pytest.mark.django_db

HEIGHT = "La altura mínima de la letra del cartel deberá ser de cuarenta milímetros."
VISIT = "El oferente deberá concurrir a la visita en la fecha indicada."


def annex_pdf(sentence):
    return tender_pdf([[para("1. CARTELES", f"1.1. {sentence}")]], header=None)


def formal_texts(run):
    return [q.text for r in m.Requirement.objects.filter(version=run.version)
            .exclude(category="tecnico") for q in r.quotes.all()]


def technical_quotes(run):
    return [(q.text, q.scope) for r in m.Requirement.objects.filter(
        version=run.version, category="tecnico") for q in r.quotes.all()]


@pytest.mark.parametrize("kind, title, file_name", [
    (m.DocumentKind.ANEXO, "Manual de señalética", "MANUAL_de_SENALETICA.pdf"),
    (m.DocumentKind.ANEXO, "Plano de carteles", "plano-03.pdf"),
    (m.DocumentKind.ESPECIFICACIONES, "Documento adicional", "adicional.pdf"),
])
def test_a_technical_annex_goes_to_the_technical_rows_and_not_to_formal_rows(
        operator_user, script, kind, title, file_name):
    """REQ-101, REQ-102, T-240 (H-7): un anexo técnico (especificaciones, manual o plano) con un
    tramo que el modelo toma como requisito no agrega una fila formal: el tramo entra en las filas
    técnicas por renglón, como cita general (antes: 60 filas formales del manual en el caso-01)."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, three_items_pdf())
    load_and_read(operator_user, procedure, annex_pdf(HEIGHT), kind=kind, title=title,
                  file_name=file_name)
    script.when(HEIGHT, item(requirements=[(HEIGHT, "formal")]))

    requested, job = propose(operator_user, procedure)

    assert job.status == "done", job.error
    assert not any("altura mínima" in text for text in formal_texts(requested.run))
    quotes = technical_quotes(requested.run)
    assert any("altura mínima" in text and scope == "general" for text, scope in quotes)


def test_an_annex_that_is_not_technical_still_gives_its_formal_rows(operator_user, script):
    """REQ-101: un anexo que no es técnico (la fecha de visita) sigue dando sus requisitos
    formales: solo cambia el destino de los anexos técnicos."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, three_items_pdf())
    load_and_read(operator_user, procedure, annex_pdf(VISIT), kind=m.DocumentKind.ANEXO,
                  title="Anexo fecha de visita", file_name="ANEXO_FECHA_DE_VISITA.pdf")
    script.when(VISIT, item(requirements=[(VISIT, "formal")]))

    requested, _ = propose(operator_user, procedure)

    assert any("concurrir a la visita" in text for text in formal_texts(requested.run))
    assert not any("concurrir" in text for text, _ in technical_quotes(requested.run))


@pytest.mark.parametrize("kind, title, file_name, technical", [
    (m.DocumentKind.ESPECIFICACIONES, "Cualquiera", "x.pdf", True),
    (m.DocumentKind.ANEXO, "Manual de señalética", "m.pdf", True),
    (m.DocumentKind.ANEXO, "Anexo", "PLANO_CR-03.pdf", True),
    (m.DocumentKind.ANEXO, "Croquis de la obra", "c.pdf", True),
    (m.DocumentKind.ANEXO, "Anexo fecha de visita", "ANEXO_FECHA_DE_VISITA.pdf", False),
    (m.DocumentKind.ANEXO, "Declaración jurada de intereses", "dj.pdf", False),
    (m.DocumentKind.PLIEGO, "Pliego con manual técnico", "pliego.pdf", False),
])
def test_which_documents_are_technical_annexes(kind, title, file_name, technical):
    """REQ-101, T-240 (H-7): es anexo técnico el documento de tipo especificaciones, o un anexo
    cuyo título o archivo es un manual, un plano o un croquis; el pliego nunca."""
    document = m.Document(kind=kind, title=title, file_name=file_name)
    assert proposal_run.is_technical_annex(document) is technical
