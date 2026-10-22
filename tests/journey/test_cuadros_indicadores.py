"""Los cuadros de indicadores arriba y el detalle debajo, en todas las secciones (T-337; REQ-126,
REQ-129, REQ-132, REQ-141; plan 017). «Qué hay y qué falta», «Pendientes de decidir» y
«Sugerencias del sistema» son los tres primeros mosaicos del tablero de cada sección y del primer
panel; al hacer clic se despliega debajo el detalle. Todo el material es inventado (P4)."""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.urls import reverse

from evaluon.journey.sections.base import Item, Missing
from evaluon.journey.tablero import resumen
from tests.accounts.test_session import TEST_PASSWORD

pytestmark = pytest.mark.django_db

KEYS = ["procedimiento", "pliego", "ofertas", "evaluacion", "normativas"]
RAIZ = Path(__file__).resolve().parents[2]
TEMPLATES = RAIZ / "evaluon" / "templates" / "journey"


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def pedir(client, procedure, user, key="ofertas"):
    log_in(client, user)
    response = client.get(reverse(f"expedientes:{key}", args=[procedure.pk]))
    assert response.status_code == 200
    return response.content.decode()


def filas(*items):
    return [(SimpleNamespace(label="Ofertas", url="/x/"), item) for item in items]


AGRUPADO = (Item("12 pares por decidir", "/p/", 12, "Revisar"), Item("Uno", "/a/", 1),
            Item("Dos", "/b/", 1), Item("Tres", "/c/", 1))


# --- Los textos cortos ----------------------------------------------------------------------------


def test_el_cuadro_de_pendientes_dice_la_cifra_total_y_cuantos_grupos_son():
    """REQ-129: 15 pendientes en 4 filas: la cifra es 15 y la línea de apoyo explica la agrupación."""
    tile = resumen.pending_tile(15, filas(*AGRUPADO))
    assert tile.title == "Pendientes de decidir" and tile.big == 15
    assert tile.sub == "en 4 grupos"
    assert tile.detail == "d-pendientes"


def test_sin_agrupar_la_linea_de_apoyo_no_inventa_grupos():
    """REQ-129: si cada fila es un pendiente no hay grupos que explicar."""
    tile = resumen.pending_tile(2, filas(Item("A", "/a/", 1), Item("B", "/b/", 1)))
    assert tile.big == 2 and "grupo" not in tile.sub


def test_cero_pendientes_es_un_dato():
    """REQ-141: «Pendientes de decidir: 0» es un dato y el cuadro lo dice."""
    tile = resumen.pending_tile(0, [])
    assert tile.has_data and tile.big == 0 and tile.sub


def test_el_cuadro_de_sugerencias_lleva_su_cifra():
    tile = resumen.suggestion_tile(3, filas(Item("S", "/s/", 3)))
    assert tile.title == "Sugerencias del sistema" and tile.big == 3
    assert tile.detail == "d-sugerencias"


def test_hay_y_falta_en_corto_sin_explicaciones():
    """REQ-132: el cuadro dice «Hay: …» y «Falta: …» cortos; los textos largos van al detalle."""
    resumen_largo = (("Ofertas", "Los 24 documentos de las ofertas están leídos. Se puede armar "
                      "la ficha de 3 ofertas."), ("Pliego", "El documento del pliego está leído."))
    faltas = (Missing("Falta la hoja de compliance de 3 ofertas", "/h/", "Subir archivo"),
              Missing("Falta el informe técnico del área (Oferta 1)", "/i/", "Subir archivo"),
              Missing("Falta el expediente", None), Missing("Falta la apertura", None))
    tile = resumen.hay_falta_tile(resumen_largo, faltas)
    textos = dict(tile.lines)
    assert textos["Hay"] == "Los 24 documentos de las ofertas están leídos · El documento del " \
                            "pliego está leído"
    assert textos["Falta"].startswith("La hoja de compliance de 3 ofertas · El informe técnico")
    assert textos["Falta"].endswith("y 2 más")
    assert "Se puede armar" not in textos["Hay"]


def test_sin_faltantes_el_cuadro_dice_falta_nada():
    """REQ-132: sin faltantes, «Falta: nada»."""
    tile = resumen.hay_falta_tile((("Ofertas", "Hay tres ofertas leídas."),), ())
    assert dict(tile.lines)["Falta"] == "nada"


def test_sin_datos_que_resumir_el_cuadro_lo_dice():
    """REQ-141: sin resumen no se inventa nada."""
    tile = resumen.hay_falta_tile((), ())
    assert dict(tile.lines)["Hay"] == "nada todavía"


# --- La página ------------------------------------------------------------------------------------


@pytest.mark.parametrize("key", KEYS)
def test_cada_seccion_abre_con_los_tres_cuadros_antes_que_el_resto(client, procedure, matrix,
                                                                  operator_user, key):
    """REQ-126, REQ-132: debajo del título, los tres cuadros son los primeros mosaicos; el
    detalle de cada uno existe y lleva los ids de la 014."""
    html = pedir(client, procedure, operator_user, key)
    tablero = html[html.index('class="board"'):html.index('class="detalles"')]
    mosaicos = re.findall(r'<a class="tile[^"]*" id="m-([\w-]+)"', tablero)
    assert mosaicos[:3] == ["hay-falta", "pendientes", "sugerencias"]
    assert html.index('id="seccion-titulo"') < html.index('id="m-hay-falta"')
    for detalle in ("d-hay-falta", "d-pendientes", "d-sugerencias"):
        assert f'id="{detalle}"' in html
    for marca in ('id="seccion-resumen"', 'id="pendientes"', 'id="sugerencias"'):
        assert marca in html
    # los ids de la 014 quedan dentro de los detalles, no sueltos en la página
    zona = html[html.index('class="detalles"'):]
    assert zona.index('id="d-hay-falta"') < zona.index('id="seccion-resumen"')
    assert zona.index('id="d-pendientes"') < zona.index('id="pendientes"')
    assert zona.index('id="d-sugerencias"') < zona.index('id="sugerencias"')


def test_la_cifra_del_cuadro_es_la_de_la_barra(client, procedure, matrix, operator_user):
    """REQ-129: la cifra del cuadro de pendientes es la cuenta de la sección."""
    from evaluon.journey import sections
    section = sections.sections_for(operator_user, procedure).get("pliego")
    html = pedir(client, procedure, operator_user, "pliego")
    cuadro = re.search(r'<a class="tile[^"]*" id="m-pendientes".*?</a>', html, re.S).group(0)
    assert f'<span class="big">{section.pending}' in cuadro


def test_el_primer_panel_tiene_los_cuadros_con_el_pendiente_general(client, procedure, matrix,
                                                                    operator_user):
    """REQ-129: el primer panel suma los pendientes de las cinco secciones, debajo del
    encabezado con la foto y antes de los mosaicos de siempre."""
    from evaluon.journey import sections
    overview = sections.sections_for(operator_user, procedure)
    html = pedir(client, procedure, operator_user, "procedimiento")
    assert html.index('id="ingreso"') < html.index('id="m-hay-falta"') \
        < html.index('id="m-pendientes"') < html.index('id="m-orden"')
    cuadro = re.search(r'<a class="tile[^"]*" id="m-pendientes".*?</a>', html, re.S).group(0)
    assert f'<span class="big">{overview.pending}' in cuadro


def test_el_usuario_de_lectura_no_ve_botones_de_decision(client, procedure, matrix):
    """REQ-129: el detalle no le da formularios de acción al usuario de lectura."""
    from django.contrib.auth import get_user_model

    from evaluon.accounts.models import CommissionRole, Role
    viewer = get_user_model().objects.create_user(
        username="lector-337", password=TEST_PASSWORD, role=Role.READ,
        commission_role=CommissionRole.NONE)
    html = pedir(client, procedure, viewer, "evaluacion")
    assert 'id="m-pendientes"' in html
    assert 'class="accion-form"' not in html


def test_la_hoja_y_las_plantillas_no_traen_estilos_ni_scripts_en_linea():
    """ADR-0076: política de contenido default-src 'self', solo tokens, sin hexadecimales."""
    for nombre in ("_mosaico.html", "_pendientes.html", "_detalle_pendientes.html",
                   "_detalle_sugerencias.html", "seccion.html", "_ingreso.html"):
        texto = (TEMPLATES / nombre).read_text(encoding="utf-8")
        assert " style=" not in texto and "<script" not in texto, nombre
    css = re.sub(r"/\*.*?\*/", "", (RAIZ / "evaluon/static/journey/tablero.css").read_text(
        encoding="utf-8"), flags=re.S)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)


def test_la_fila_agrupada_muestra_cuantos_pendientes_suma():
    """REQ-129: la suma de las filas cuadra con la cifra del cuadro."""
    from django.template.loader import render_to_string
    html = render_to_string("journey/_pendientes.html", {
        "solo": "pendientes", "pending_total": 15, "pending_rows": filas(*AGRUPADO),
        "show_section": False, "next_url": "/x/"})
    cuentas = re.findall(r'<span class="cuenta"[^>]*>(\d+)</span>', html)
    assert cuentas == ["12", "1", "1", "1"] and sum(map(int, cuentas)) == 15
    assert 'id="pendientes"' in html and 'id="sugerencias"' not in html
