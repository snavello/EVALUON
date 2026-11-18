"""El aviso de «leída por visión» (REQ-158; T-359): con `sin_original` (el panel del cuadro para
quien no puede abrir el original) no ofrece el enlace a la imagen; sin esa marca, sí. Datos
inventados (P4)."""

from django.template.loader import render_to_string

PLANTILLA = "journey/_cita_vision.html"


def test_req158_la_cita_leida_por_vision_ofrece_el_original():
    """REQ-158: por omisión el aviso trae la marca y el enlace a la página citada."""
    html = render_to_string(PLANTILLA, {"document_id": 7, "page": 3})
    assert "leída por visión" in html
    assert "Ver la imagen de la página" in html and "#page=3" in html


def test_req158_con_sin_original_la_marca_queda_y_el_enlace_no():
    """REQ-158: `sin_original` conserva la marca y el aviso, y no ofrece el enlace al original."""
    html = render_to_string(PLANTILLA, {"document_id": 7, "page": 3, "sin_original": True})
    assert "leída por visión" in html and "Conviene que la Comisión" in html
    assert "Ver la imagen de la página" not in html and "<a " not in html
