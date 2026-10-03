"""Una página ilegible dentro de un PDF con texto (T-028; ADR-0004, "Cómo se prueba";
criterio de REQ-004).

El "extracto con ruido" se arma dentro de la prueba, sin subir otro PDF (decisión del
Coordinador): las páginas 1 a 3 del extracto del anexo de la Disposición AFIP 247/2022
(`tests/fixtures/disp-247-2022-anexo-extracto.pdf`, T-012), la página de ruido de T-021
(`tests/fixtures/pagina-ruido.pdf`, una imagen de celdas blancas y negras al azar) y las
páginas 4 a 6 del extracto. Material público o sintético (P4).

La página 4 del archivo armado es la de ruido: la entrada única la clasifica como
escaneada, la reconoce y la da por ilegible; el informe la señala y no señala ninguna
otra.
"""

import io
from pathlib import Path

import pypdfium2 as pdfium
import pytest

from evaluon.norms.models import Unit
from evaluon.norms.reading import (
    ORIGIN_OCR,
    PAGE_ILLEGIBLE,
    PAGE_KIND_SCANNED,
    PAGE_KIND_TEXT,
    PAGE_READ,
    read_document,
)
from evaluon.norms.services import loading
from evaluon.norms.splitting import split_document
from tests.norms.test_three_formats import DATA_247

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures"
EXTRACT = FIXTURES / "disp-247-2022-anexo-extracto.pdf"
NOISE = FIXTURES / "pagina-ruido.pdf"

NOISE_PAGE = 4


def extract_with_noise():
    """El extracto con la página de ruido insertada como página 4."""
    extract = pdfium.PdfDocument(EXTRACT)
    pdf = pdfium.PdfDocument.new()
    pdf.import_pages(extract, pages=[0, 1, 2])
    pdf.import_pages(pdfium.PdfDocument(NOISE), pages=[0])
    pdf.import_pages(extract, pages=[3, 4, 5])
    buffer = io.BytesIO()
    pdf.save(buffer)
    return buffer.getvalue()


@pytest.fixture(scope="module")
def noisy_bytes():
    return extract_with_noise()


@pytest.fixture(scope="module")
def noisy(noisy_bytes):
    return read_document(noisy_bytes)


@pytest.fixture(scope="module")
def noisy_split(noisy):
    return split_document(noisy, part="anexo", category="regimen_especifico")


@pytest.fixture(scope="module")
def extract_split():
    return split_document(read_document(EXTRACT), part="anexo", category="regimen_especifico")


def test_noise_page_is_recognized_and_illegible(noisy):
    """REQ-004, REQ-015: la página de ruido se clasifica como escaneada, se reconoce y
    queda ilegible, sin texto; las otras seis se leen de su capa de texto."""
    assert len(noisy.pages) == 7
    kinds = [page.classification for page in noisy.pages]
    assert kinds == [PAGE_KIND_TEXT] * 3 + [PAGE_KIND_SCANNED] + [PAGE_KIND_TEXT] * 3
    noise = noisy.pages[NOISE_PAGE - 1]
    assert noise.number == NOISE_PAGE
    assert noise.status == PAGE_ILLEGIBLE
    assert noise.origin == ORIGIN_OCR
    assert noise.lines == []
    others = [page for page in noisy.pages if page.number != NOISE_PAGE]
    assert all(page.status == PAGE_READ for page in others)
    assert noisy.pages_not_read == [NOISE_PAGE]


def test_report_points_at_the_illegible_page_and_no_other(noisy_split):
    """REQ-004: el informe de lectura señala la página ilegible y ninguna otra: es la
    única en la lista de ilegibles, ninguna otra figura como casi sin texto, dudosa, sin
    texto o en blanco, y "Requiere atención" la nombra solo a ella."""
    report = noisy_split.report
    assert report["pages"] == {"total": 7, "not_read": [NOISE_PAGE]}
    assert report["page_summary"] == {
        "illegible": [NOISE_PAGE],
        "almost_empty": [],
        "doubtful": [],
        "without_text": [],
        "blank": [],
    }
    page_items = [
        item for item in report["attention"] if item["kind"].endswith("pages")
    ]
    assert [(item["kind"], item["pages"]) for item in page_items] == [
        ("illegible_pages", [NOISE_PAGE])
    ]
    assert "Ilegibles: 4." in noisy_split.report_text
    assert "Páginas ilegibles" in noisy_split.report_text
    for number in (1, 2, 3, 5, 6, 7):
        assert f"página {number} " not in page_items[0]["text"]


def test_noise_page_adds_no_units_and_moves_nothing(noisy_split, extract_split):
    """REQ-004: la página ilegible no aporta texto: las unidades son las del extracto,
    con el mismo texto; solo corren una página las que están después del ruido."""
    def shifted(page):
        return page + 1 if page is not None and page >= NOISE_PAGE else page

    assert [(u.key, u.text) for u in noisy_split.units] == [
        (u.key, u.text) for u in extract_split.units
    ]
    assert [(u.page_start, u.page_end) for u in noisy_split.units] == [
        (shifted(u.page_start), shifted(u.page_end)) for u in extract_split.units
    ]
    assert noisy_split.report["ocr"]["units"] == 0


@pytest.mark.django_db
def test_loaded_report_points_at_the_illegible_page(read_write_user, noisy_bytes):
    """REQ-004: cargado, el documento guarda el informe que señala la página 4 y ninguna
    otra, y el hecho `load` la registra entre las no leídas."""
    result = loading.load_norm(
        read_write_user,
        data=noisy_bytes,
        file_name="disp-247-2022-anexo-extracto-con-ruido.pdf",
        part="anexo",
        general_regime=True,
        **DATA_247,
    )

    report = result.reading.report
    assert report["page_summary"]["illegible"] == [NOISE_PAGE]
    assert sum(len(pages) for pages in report["page_summary"].values()) == 1
    assert result.event.detail["report"]["pages_not_read"] == [NOISE_PAGE]
    assert result.document.file_format == "pdf"
    assert Unit.objects.filter(reading=result.reading, text_origin=ORIGIN_OCR).count() == 0
