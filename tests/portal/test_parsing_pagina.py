"""Lectura de la página pública del proceso con el calco (T-140; REQ-046).

Función pura sobre bytes: sin red ni base. La lista esperada es `portal-esperado.yaml`
(todos los datos inventados; P4).
"""

import os
from datetime import date
from pathlib import Path

import pytest
import yaml
from django.conf import settings

from evaluon.portal.parsing import pagina, texto

DATA = Path(settings.BASE_DIR) / "tests" / "portal" / "data" / "portal-chico"
ESPERADO = yaml.safe_load((DATA / "portal-esperado.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def page():
    return pagina.parse_page((DATA / "proceso.html").read_bytes())


def squash(value):
    """El esperado conserva los espacios del expediente; el lector los normaliza."""
    if isinstance(value, str):
        return texto.normalize(value)
    if isinstance(value, list):
        return [squash(v) for v in value]
    if isinstance(value, dict):
        return {k: squash(v) for k, v in value.items()}
    return value


def test_basic_data_match_the_expected_list(page):
    """REQ-046: el 100 % de los datos básicos, cronograma y garantías del calco."""
    esperado = squash(ESPERADO["procedimiento"])
    for key, value in esperado.items():
        if key == "fecha_autorizacion":
            continue
        assert page.data[key] == value, key


def test_six_lines_with_quantity(page):
    """REQ-046: los 6 renglones con su cantidad, código y descripción."""
    assert len(page.lines) == len(ESPERADO["renglones"]) == 6
    for got, want in zip(page.lines, ESPERADO["renglones"]):
        assert got["numero"] == want["numero"]
        assert got["codigo_item"] == want["codigo_item"]
        assert got["descripcion"] == want["descripcion"]
        assert got["cantidad"] == want["cantidad"]
        assert got["unidad"] == want["unidad"]


def test_documents_list_matches_the_expected_list(page):
    """REQ-046: todos los documentos, con nombre, número GDE, y envío o URL directa."""
    by_name = {d["nombre"]: d for d in page.documents}
    esperados = ESPERADO["documentos"]
    assert len(page.documents) == len(esperados)
    for want in esperados:
        got = by_name[texto.normalize(want["nombre"])]
        assert got["numero_gde"] == want.get("numero_gde")
        if want["como"] == "URL directa":
            assert got["como"] == "url"
            assert got["url"] == want["url"]
        else:
            assert got["como"] == "formulario"
            assert got["target"] == want["target"]
        if "fecha_vinculacion" in want:
            d, m, y = want["fecha_vinculacion"].split("/")
            assert got["fecha_vinculacion"] == date(int(y), int(m), int(d))
        if "numero_especial" in want:
            assert got["numero_especial"] == want["numero_especial"]


def test_acta_and_dictamen_urls(page):
    """REQ-046: la URL directa del acta y del dictamen, y el envío del cuadro."""
    urls = {d["nombre"]: d["url"] for d in ESPERADO["documentos"] if d["como"] == "URL directa"}
    assert page.acta["url"] == urls["Acta de Apertura"]
    assert page.dictamen["url"] == urls["Dictamen de Evaluación"]
    assert page.cuadro["target"].endswith("lnkVerCuadroComparativo")


def test_authorization_date_is_pending_with_candidate(page):
    """REQ-046: la página no trae la fecha de autorización: queda pendiente con candidata."""
    fecha = page.data["fecha_autorizacion"]
    assert fecha["valor"] is None
    assert fecha["candidata"] == date(2025, 11, 14)
    assert "Autorización llamado" in fecha["origen_candidata"]


def test_damaged_text_is_marked_and_kept(page):
    """REQ-046, P3: los campos con `¿¿` se marcan y el texto queda como lo entrega el Portal."""
    for campo in ESPERADO["marcas_de_texto_danado"]["campos"]:
        assert campo in page.damaged
    assert "¿¿" in page.data["unidad_operativa"]
    assert "nombre" not in page.damaged


def test_nothing_missing_in_a_complete_page(page):
    """REQ-046: la página completa no informa faltantes ni secciones ausentes."""
    assert page.missing == []
    assert page.issues == []


def test_version_with_circular_lists_annex_circular_and_act():
    """REQ-046: la segunda versión suma anexo, circular (id del onclick) y acto."""
    p = pagina.parse_page((DATA / "proceso-con-circular.html").read_bytes())
    base = pagina.parse_page((DATA / "proceso.html").read_bytes())
    v2 = ESPERADO["version_2"]["novedades_respecto_de_la_version_1"]
    assert len(p.circulars) == 1
    circ = p.circulars[0]
    want = v2["circulares_nuevas"][0]
    assert circ["numero"] == 1
    assert circ["fecha_publicacion"] == date(2026, 7, 2)
    assert circ["tipo"] == want["tipo"]
    assert circ["url"] == want["url"]
    names = [d["nombre"] for d in p.documents]
    assert v2["anexos_nuevos"][0]["nombre"] in names
    assert "Autorización circular" in names
    anexo = next(d for d in p.documents if d["nombre"] == v2["anexos_nuevos"][0]["nombre"])
    assert anexo["como"] == "formulario"
    assert anexo["target"] == v2["anexos_nuevos"][0]["target"]
    assert len(p.documents) == len(base.documents) + 2


def test_missing_section_does_not_break_the_rest():
    """REQ-046: sin la tabla de renglones y sin el cronograma, informa y lee lo demás."""
    html = (DATA / "proceso.html").read_text(encoding="utf-8")
    html = html.replace("UC_DetalleProductos_gvLineaPliego", "X_ausente")
    html = html.replace("UC_Cronograma_", "X_cronograma_")
    p = pagina.parse_page(html.encode("utf-8"))
    assert p.lines == []
    assert p.data["cronograma"] == {}
    assert {"renglones", "cronograma"} <= {i["seccion"] for i in p.issues}
    assert p.data["numero"] == ESPERADO["procedimiento"]["numero"]
    assert len(p.documents) == len(ESPERADO["documentos"])


def test_missing_required_field_is_reported_not_invented():
    """REQ-046: si falta el número del proceso, se informa y no se inventa."""
    html = (DATA / "proceso.html").read_text(encoding="utf-8")
    html = html.replace("lblNumeroProceso", "x1").replace("lblNumPliego", "x2")
    p = pagina.parse_page(html.encode("utf-8"))
    assert "numero" in p.missing
    assert p.data["numero"] is None


def test_page_that_is_not_a_process_page_reports_everything_missing():
    """REQ-046: una pantalla de error no revienta: todo faltante, nada inventado."""
    p = pagina.parse_page((DATA / "error-pantalla.html").read_bytes())
    assert {"numero", "tipo"} <= set(p.missing)
    assert p.lines == [] and p.documents == []


@pytest.mark.skipif(
    not os.environ.get("EVALUON_CASOS_DIR"), reason="páginas reales: solo local (P4)"
)
def test_real_page_reads_with_the_same_counts():
    """REQ-046: corrida local con la página real, sin subir nada (EVALUON_CASOS_DIR)."""
    base = Path(os.environ["EVALUON_CASOS_DIR"]) / "caso-00"
    p = pagina.parse_page((base / "portal" / "proceso.html").read_bytes())
    esperado = yaml.safe_load((base / "esperado" / "portal-esperado.yaml").read_text("utf-8"))
    assert len(p.lines) == len(esperado["renglones"])
    assert p.missing == []
