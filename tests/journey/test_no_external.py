"""Sin direcciones externas en el recorrido (P4, P5; plan 013, "No funcional")."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "evaluon"
FILES = [*(ROOT / "templates" / "journey").glob("*.html"),
         *(ROOT / "static" / "journey").glob("*")]


def test_templates_and_static_files_have_no_external_addresses():
    """No funcional: ningún http:// ni https:// en las plantillas, el script ni los estilos."""
    assert len(FILES) >= 4
    for path in FILES:
        text = path.read_text(encoding="utf-8")
        assert "http://" not in text and "https://" not in text, path.name
