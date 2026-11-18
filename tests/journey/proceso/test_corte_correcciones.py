"""Correcciones del corte vertical de la 018 (T-362; REQ-149, REQ-152, REQ-154, REQ-156): el panel
del cuadro con cada rol (H-A1), los enlaces de Indicadores que un rol no puede abrir (H-A2), el
cuadro ancho que no desplaza la página (H-A3) y la letra del encabezado del cuadro (H-A5).
Material inventado (P4)."""

import re
from pathlib import Path

import pytest
from django.urls import reverse

from tests.journey.proceso.test_cuadro import entrar
from tests.journey.proceso.test_cuadro_panel import abrir

pytestmark = pytest.mark.django_db

RAIZ = Path(__file__).resolve().parents[3] / "evaluon"
CSS = RAIZ / "static" / "journey" / "cuadro.css"
ROLES = ("evaluator_user", "operator_user", "no_commission_user")


def panel_de(client, request, caso, rol, needle="garantía de mantenimiento"):
    """El HTML del panel de la celda para ese rol."""
    client.logout()
    entrar(client, request.getfixturevalue(rol))
    response, html, _, _ = abrir(client, caso, 0, needle)
    assert response.status_code == 200
    return html[html.index('id="cu-panel"'):]


def texto(html):
    """Solo el texto visible: sin etiquetas, con los espacios normalizados."""
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def enlace_original(html):
    return re.search(r'<a href="[^"]*/original/[^"]*">oferta\.pdf · página 1</a>', html)


# --- H-A1 ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("rol", ROLES)
def test_el_panel_nunca_muestra_marcado_escrito(client, caso_varios_en_curso, request, rol):
    """REQ-154: con cualquier rol el panel se dibuja y no queda ni una etiqueta escapada en pantalla
    (antes, sin rol de la Comisión el cuerpo entero salía como texto: `&lt;div …`)."""
    panel = panel_de(client, request, caso_varios_en_curso, rol)
    assert "&lt;" not in panel and "&gt;" not in panel
    assert "<h2>Oferta 1 × requisito" in panel
    assert "Lo que exige el pliego" in panel and "Historial del par" in panel
    assert "oferta.pdf · página 1" in panel


def test_operador_y_solo_lectura_ven_el_mismo_panel_salvo_el_enlace(
        client, caso_varios_en_curso, request):
    """REQ-154: el texto del panel es el mismo; solo cambia que el documento original, que
    solo abre quien tiene rol de la Comisión, sea un enlace o solo el nombre."""
    caso = caso_varios_en_curso
    operador = panel_de(client, request, caso, "operator_user")
    lectura = panel_de(client, request, caso, "no_commission_user")
    assert texto(operador) == texto(lectura)
    assert enlace_original(operador) and not enlace_original(lectura)


@pytest.mark.parametrize("rol,con_enlace", [("evaluator_user", True), ("operator_user", True),
                                            ("no_commission_user", False)])
def test_el_enlace_al_original_solo_lo_ofrece_a_quien_puede_abrirlo(
        client, caso_varios_en_curso, request, rol, con_enlace):
    """El original da 403 sin rol de la Comisión: a ese rol no se le ofrece el enlace, y lo que se
    ofrece se puede abrir."""
    panel = panel_de(client, request, caso_varios_en_curso, rol)
    assert bool(enlace_original(panel)) is con_enlace
    assert ("/original/" in panel) is con_enlace
    for destino in re.findall(r'<a href="([^"]*/original/[^"]*)"', panel):
        assert client.get(destino.split("#")[0]).status_code == 200


def test_sin_enlace_el_nombre_del_documento_sigue_escapado(client, caso_varios_en_curso, request):
    """P3 y seguridad: lo que se muestra sin enlace sale de la plantilla (con su escape): el título
    del documento con marcado se ve como texto, nunca como etiqueta."""
    caso = caso_varios_en_curso
    from evaluon.offers.models import Document

    Document.objects.filter(offer=caso.offers[0]).update(title="<i>x</i>.pdf")
    panel = panel_de(client, request, caso, "no_commission_user")
    assert "<i>x</i>" not in panel
    assert "&lt;i&gt;x&lt;/i&gt;.pdf · página 1" in panel


def test_la_vista_no_arma_html_a_mano():
    """El panel no pasa por un reemplazo de texto sobre el HTML ya dibujado y la vista no marca
    nada como seguro: lo que se muestra sale de la plantilla (H-A1)."""
    fuente = (RAIZ / "journey" / "views" / "cuadro.py").read_text(encoding="utf-8")
    assert "re.sub" not in fuente and "mark_safe" not in fuente


# --- H-A2 ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("rol,con_enlace", [("evaluator_user", True), ("operator_user", True),
                                            ("no_commission_user", False)])
def test_indicadores_no_ofrece_tomar_del_portal_a_quien_recibe_403(
        client, caso_varios_en_curso, request, rol, con_enlace):
    """Alta de un procedimiento (`/expedientes/nuevo/`): solo operador y evaluador. A solo lectura
    no se le ofrece «Tomar del Portal»; el faltante se sigue diciendo."""
    caso = caso_varios_en_curso
    entrar(client, request.getfixturevalue(rol))
    html = client.get(reverse("expedientes:procedimiento", args=[caso.procedure.pk])
                      ).content.decode()
    destinos = re.findall(r'<a [^>]*href="(/expedientes/nuevo/[^"]*)"', html)
    assert bool(destinos) is con_enlace
    faltan = re.search(r'<p class="falta">(.*?)</p>', html, re.S)
    assert faltan and "Falta" in html
    if not con_enlace:
        assert "Tomar del Portal" not in faltan.group(1)
    for destino in destinos:  # lo que se ofrece, se puede abrir
        assert client.get(destino).status_code == 200


# --- H-A3 y H-A5 ---------------------------------------------------------------------------------


def reglas(selector):
    """Las declaraciones de la regla cuyo selector es exactamente `selector` (sin comentarios)."""
    css = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)
    found = {}
    for sel, cuerpo in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if sel.strip() == selector:
            for decl in cuerpo.split(";"):
                if ":" in decl:
                    clave, valor = decl.split(":", 1)
                    found[clave.strip()] = valor.strip()
    return found


def px(valor):
    numero = float(re.match(r"[\d.]+", valor).group())
    return numero * 16 if valor.endswith("rem") else numero


def test_la_grilla_del_cuadro_tiene_una_columna_que_se_encoge():
    """REQ-152: sin panel, la grilla `.cu-dos` también declara su columna con `minmax(0, 1fr)`. Con
    la columna `auto` por omisión, una tabla de 10 ofertas (1.584 px) la ensanchaba y la página
    se desplazaba de costado (medido en Chrome: documento de 1.709 px a 1440 px)."""
    assert reglas(".cu-dos").get("grid-template-columns") == "minmax(0, 1fr)"
    assert reglas(".cu-tabla").get("min-width") == "0"
    # La tabla se desplaza dentro de su caja, y la caja es el bloque contenedor de los textos para
    # lector de pantalla (`.cu-sr`, de posición absoluta): si no, su lugar queda fuera de la caja,
    # `overflow` no los recorta y ensanchan la página (medido: 1.546 px a 1280 px, con la grilla ya
    # arreglada).
    assert reglas(".cu-scroll").get("overflow-x") == "auto"
    assert reglas(".cu-scroll").get("position") == "relative"


def test_la_caja_de_la_tabla_se_enfoca_con_el_teclado(client, caso_varios_en_curso):
    """REQ-152: la caja que se desplaza es una región con nombre y entra en el orden del teclado."""
    entrar(client, caso_varios_en_curso.user)
    html = client.get(reverse("expedientes:cuadro", args=[caso_varios_en_curso.procedure.pk])
                      ).content.decode()
    assert re.search(r'<div class="cu-scroll" role="region" aria-label="[^"]+" tabindex="0">', html)


@pytest.mark.parametrize("selector", [".cu-cuadro th.cu-of small", ".cu-nota"])
def test_la_letra_del_encabezado_y_de_sin_confirmar_es_de_12_px_o_mas(selector):
    """REQ-156: el nombre y el total de cada oferta y la leyenda «sin confirmar» miden 12 px o más
    (antes 11,67 y 11 px)."""
    tamano = reglas(selector).get("font-size")
    assert tamano and px(tamano) >= 12
