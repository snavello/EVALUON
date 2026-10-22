"""La línea «Hay · Falta» siempre lleva la etiqueta «Falta:» y no repite la palabra
(REQ-132; plan 017, T-336). Todo el material es inventado (P4)."""

import re
from types import SimpleNamespace as NS

import pytest
from django.template.loader import render_to_string
from django.urls import reverse

from tests.accounts.test_session import TEST_PASSWORD

pytestmark = pytest.mark.django_db


def render(missing):
    section = NS(summary=[("x", "Hay algo.")], tema_missing=missing)
    return render_to_string("journey/_hay_falta.html", {"section": section})


def falta_row(html):
    return html.split('class="hf-fila hf-falta"')[1]


def test_the_falta_label_is_always_there_and_the_word_is_not_repeated():
    """REQ-132: «Falta el informe…» queda «Falta: El informe…»; «Faltan…» queda «Falta: Los…»."""
    html = render([NS(text="Falta el informe técnico del área (oferta 2)", url="/a/", action="Subir"),
                   NS(text="Faltan los renglones con su cantidad", url="", action=""),
                   NS(text="Sin la palabra", url="", action="")])
    row = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", falta_row(html)))
    assert "Falta:" in row and "Falta: Falta" not in row
    assert "El informe técnico del área (oferta 2)" in row and "Los renglones con su cantidad" in row
    assert "Falta el" not in row and "Faltan los" not in row
    assert "Sin la palabra" in row and 'href="/a/"' in html and "Subir" in html


def test_without_missing_items_there_is_no_falta_text():
    """REQ-132: sin faltantes, «Ningún faltante registrado.»"""
    assert "Ningún faltante registrado." in render([])


def test_a_real_page_has_the_label_before_the_missing_text(client, operator_user, procedure):
    """REQ-132: en la página del procedimiento cargado a mano la fila trae «Falta:»."""
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    for key in ("procedimiento", "evaluacion", "normativas"):
        html = client.get(reverse(f"expedientes:{key}", args=[procedure.pk])).content.decode()
        fila = falta_row(html).split("</div>")[0]
        if "<p class=\"falta\">" in fila:
            assert "Falta:" in fila, key
        assert "Falta: Falta" not in re.sub(r"<[^>]+>|\s+", " ", fila), key
