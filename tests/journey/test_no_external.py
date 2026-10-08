"""Sin direcciones externas en el recorrido y en las secciones (P4, P5; plan 013, "No
funcional"; plan 014, umbral «Sin internet»)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "evaluon"
FILES = [*(ROOT / "templates" / "journey").rglob("*.html"),
         *(ROOT / "static" / "journey").glob("*")]


def test_templates_and_static_files_have_no_external_addresses():
    """No funcional: ningún http:// ni https:// en las plantillas, el script ni los estilos."""
    assert len(FILES) >= 4
    for path in FILES:
        text = path.read_text(encoding="utf-8")
        assert "http://" not in text and "https://" not in text, path.name


def test_the_section_screens_have_no_inline_styles_or_scripts():
    """Plan 014: la política de contenido solo permite recursos propios, así que ni estilos
    ni scripts en línea; los archivos nuevos existen."""
    names = {p.name for p in FILES}
    assert {"seccion_base.html", "portada.html", "secciones.css", "secciones.js"} <= names
    for path in FILES:
        if path.suffix != ".html":
            continue
        text = path.read_text(encoding="utf-8")
        assert " style=" not in text and "<style" not in text, path.name
        assert "onclick=" not in text, path.name
        assert not re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", text), path.name
