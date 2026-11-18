"""El vocabulario en pantalla (REQ-155; plan 018, «Vocabulario»; T-358): la lista de procedimientos
no se llama «Expedientes», la lista de requisitos no se llama «Matriz de cumplimiento» (esa palabra
es del cuadro), y los siete nombres de los pasos son los mismos en el inicio, la portada y el
cuadro. «Expediente» como dato del Portal no se toca. Material inventado (P4)."""

import re
from pathlib import Path

import pytest
from django.urls import reverse

from evaluon.journey.proceso import pasos
from tests.journey.proceso.conftest import caso_recien_cargado, caso_varios_en_curso  # noqa: F401  (fixtures)
from tests.journey.proceso.test_portada import entrar

pytestmark = pytest.mark.django_db

RAIZ = Path(__file__).resolve().parents[2] / "evaluon"
PROHIBIDAS = ("Matriz de cumplimiento", ">Expedientes<", "Cumplimiento por tipo y oferta",
              "Propuesta por oferta y requisito")


def _texto(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def test_req155_ninguna_plantilla_ni_cadena_de_pantalla_usa_las_expresiones_viejas():
    """REQ-155: las expresiones viejas no están en `templates/` ni en `journey/` (código)."""
    hallados = []
    for carpeta, patron in (("templates", "*.html"), ("journey", "*.py")):
        for archivo in (RAIZ / carpeta).rglob(patron):
            texto = archivo.read_text(encoding="utf-8")
            hallados += [f"{archivo.name}: {p}" for p in PROHIBIDAS if p in texto]
    assert hallados == []


def test_req155_las_pantallas_del_caso_chico_no_usan_las_expresiones_viejas(
        client, caso_varios_en_curso):
    """REQ-155: inicio, portada, las cinco secciones y el cuadro, con el caso chico."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    pk = caso.procedure.pk
    urls = ["/", reverse("expedientes:index"), reverse("expedientes:portada", args=[pk]),
            reverse("expedientes:cuadro", args=[pk])]
    urls += [reverse(f"expedientes:{s}", args=[pk])
             for s in ("procedimiento", "pliego", "ofertas", "evaluacion", "normativas")]
    for url in urls:
        respuesta = client.get(url)
        assert respuesta.status_code == 200, url
        html = respuesta.content.decode()
        for prohibida in PROHIBIDAS:
            assert prohibida not in html, (url, prohibida)
        assert "matriz de cumplimiento" not in _texto(html).lower(), url
    assert "Procedimientos" in client.get("/").content.decode()


def test_req155_los_estados_vacios_tampoco_dicen_matriz_de_cumplimiento(
        client, caso_recien_cargado):
    """REQ-155: sin matriz todavía, las secciones dicen «matriz de requisitos» (el nombre viejo
    quedaba en minúscula en los textos de «todavía no hay»)."""
    caso = caso_recien_cargado
    entrar(client, caso.user)
    pk = caso.procedure.pk
    for seccion in ("procedimiento", "pliego", "ofertas", "evaluacion"):
        url = reverse(f"expedientes:{seccion}", args=[pk])
        respuesta = client.get(url)
        assert respuesta.status_code == 200, url
        assert "matriz de cumplimiento" not in _texto(respuesta.content.decode()).lower(), url
    assert "matriz de requisitos" in _texto(
        client.get(reverse("expedientes:pliego", args=[pk])).content.decode()).lower()


def test_req155_los_siete_pasos_se_llaman_igual_en_inicio_portada_y_cuadro(
        client, caso_varios_en_curso):
    """REQ-155: los siete nombres de `pasos.py` aparecen en el inicio y en la portada."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    pk = caso.procedure.pk
    # En el inicio los pasos llegan en la fila que pide `recorrido.js` (T-361).
    for url in (reverse("expedientes:fila", args=[pk]), reverse("expedientes:portada", args=[pk]),
                reverse("expedientes:cuadro", args=[pk])):
        texto = _texto(client.get(url).content.decode())
        faltan = [p.nombre for p in pasos.PASOS if p.nombre not in texto]
        assert faltan == [], (url, faltan)
