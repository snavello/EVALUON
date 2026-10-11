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


# --- H-6: «dicha», «tal» y «tales» continúan la oración anterior --------------------------------

from types import SimpleNamespace  # noqa: E402

from evaluon.tenders.evaluation import piece_problem  # noqa: E402
from evaluon.tenders.proposal.sentences import (  # noqa: E402
    expand_to_sentence,
    heading_of,
    is_continuation,
    lacks_subject,
)


@pytest.mark.parametrize("sentence", [
    "Tal manifestación deberá ser suscripta por el representante legal.",
    "Tales documentos se acompañarán en copia simple.",
    "Dichas copias serán certificadas.",
    "El porcentaje de dicha cotización no podrá ser inferior al veinte por ciento.",
    "El plazo de dichos trabajos se fijará en el contrato.",
])
def test_tal_tales_and_dicha_make_the_sentence_a_continuation(sentence):
    """REQ-101, T-240 (H-6): una oración que abre con «Tal» o «Tales», o que remite con «dicho»,
    «dicha», «dichos» o «dichas» en sus primeras palabras, sigue a la anterior."""
    assert is_continuation(sentence) and lacks_subject(sentence)


@pytest.mark.parametrize("sentence", [
    "Tal como se indica en el punto anterior, el oferente presentará la nota.",
    "Tal vez el organismo prorrogue el plazo.",
    "El oferente presentará la nota firmada por el representante legal, en dicha forma.",
    "La garantía se constituirá en pesos.",
])
def test_a_tal_como_or_a_late_dicha_does_not_make_a_continuation(sentence):
    """REQ-101: «Tal como…» y «Tal vez…» abren una oración propia, y un «dicha» lejos del comienzo
    no la ata a la anterior."""
    assert not is_continuation(sentence)


def test_a_unit_joins_the_short_sentence_that_says_dicha_or_tal():
    """REQ-101, T-240 (H-6): la unidad de sentido incluye la oración corta que sigue con «Tal» o
    «dicha»: el porcentaje de dicha cotización va con la oración de la cotización parcial."""
    first = "Las empresas medianas podrán presentar cotización parcial."
    second = "El porcentaje de dicha cotización no podrá ser inferior al veinte por ciento."
    text = f"{first} {second} El oferente fijará el plazo."
    start = text.index("El porcentaje")
    unit = expand_to_sentence(text, (start, start + len("El porcentaje de dicha"))).span
    assert text[unit[0]:unit[1]] == f"{first} {second}"
    third = "Tal manifestación deberá ser suscripta por el representante legal."
    text = f"Podrá manifestar la voluntad de no renovar la oferta. {third}"
    start = text.index("Tal")
    unit = expand_to_sentence(text, (start, start + len(third))).span
    assert text[unit[0]:unit[1]] == text


def test_the_mechanical_check_marks_a_quote_that_starts_with_tal_or_dicha():
    """REQ-101, T-240 (H-6): la comprobación de pedazos marca la cita que arranca con «Tal…» o
    con «…dicha…» sin la oración anterior (antes: 1 pedazo mecánico contra 12 por lectura)."""
    text = ("Podrá manifestar la voluntad de no renovar la oferta. Tal manifestación deberá ser "
            "suscripta por el representante legal.")
    start = text.index("Tal")
    assert piece_problem(text, start, len(text)) == "sin_sujeto"
    text = ("Las empresas medianas podrán presentar cotización parcial. El porcentaje de dicha "
            "cotización no podrá ser inferior al veinte por ciento.")
    assert piece_problem(text, text.index("El porcentaje"), len(text)) == "sin_sujeto"


# --- Incisos sin encabezado: la oración que los introduce es un párrafo hermano -------------------


def paragraph(key, text, kind="parrafo"):
    return SimpleNamespace(key=key, text=text, segment_type=kind)


def lookup(*segments):
    by_key = {s.key: s for s in segments}
    return by_key.get


def test_an_inciso_paragraph_gets_the_intro_that_is_its_previous_sibling():
    """REQ-101, T-240: los incisos «b)», «c)»… de una lista que introduce el párrafo anterior (un
    hermano, no el padre) llevan ese encabezado (antes: llegaban sin él y la oración sola no se
    entendía: 9 filas en el caso-00)."""
    title = paragraph("sec-iv/anexo-ii", "ANEXO II - DECLARACIÓN JURADA", "titulo")
    intro = paragraph("sec-iv/anexo-ii/p-2", "ARTÍCULO 18.- No podrán contratar con el "
                      "Organismo: a) Los infractores de la presente norma;")
    first = paragraph("sec-iv/anexo-ii/p-3", "b) Los funcionarios del Organismo.")
    second = paragraph("sec-iv/anexo-ii/p-4", "c) Los condenados por delitos dolosos.")
    other = paragraph("sec-iv/anexo-ii/p-5", "Proceso de compra N°: __________")
    find = lookup(title, intro, first, second, other)
    assert "No podrán contratar con el Organismo:" in heading_of(first, find)
    assert "No podrán contratar con el Organismo:" in heading_of(second, find)
    assert heading_of(other, find) == ""
    assert heading_of(intro, find) == ""


def test_an_inciso_whose_intro_is_not_found_has_no_heading():
    """REQ-101: sin párrafo hermano que lo introduzca, el inciso no inventa un encabezado."""
    item = paragraph("sec-iv/anexo-ii/p-3", "b) Los funcionarios del Organismo.")
    assert heading_of(item, lookup(item)) == ""
