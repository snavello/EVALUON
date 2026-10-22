"""El resto del tablero de Ofertas: hojas de compliance, documentación, circulares y fichas
(REQ-126, REQ-129, REQ-141; plan 017, D-11; T-326). Material inventado (P4)."""

import re
from types import SimpleNamespace

import pytest
from django.urls import reverse

from evaluon.journey.temas import s3_anexos, s3_circulares, s3_ficha, s3_ofertas
from tests.journey.temas.test_s3_anexos import sheet_pdf
from tests.journey.temas.test_s3_anexos import url as annex_url
from tests.journey.temas.test_s3_circulares import pdf_file
from tests.journey.temas.test_s3_circulares import upload_url as circular_url
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.conftest import two_offers  # noqa: F401  (fixture)
from tests.journey.test_tablero_secciones import Pagina, revisar

pytestmark = pytest.mark.django_db

ORDEN_ESPERADO = ["m-acta", "m-baja", "m-alta", "m-docs", "m-orden", "m-fichas", "m-compliance",
                  "m-circulares"]
DETALLES = {"m-compliance": "d-s3-anexos", "m-docs": "d-s3-ofertas", "m-circulares": "d-s3-circulares",
            "m-fichas": "d-s3-ficha"}


def pedir(client, procedure, user, consulta=""):
    assert client.login(username=user.username, password=TEST_PASSWORD)
    respuesta = client.get(reverse("expedientes:ofertas", args=[procedure.pk]) + consulta)
    assert respuesta.status_code == 200
    return respuesta.content.decode()


def mosaico(html, clave):
    return html.split(f'id="m-{clave}"')[1].split("</a>")[0]


def texto(html):
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


# --- Composición del tablero --------------------------------------------------------------------------


def test_el_tablero_suma_los_cuatro_mosaicos_y_cada_uno_abre_su_detalle(
        client, procedure, matrix, two_offers, operator_user):
    """REQ-126: hojas de compliance, documentación, circulares y fichas se suman a los cuatro de
    T-315; cada uno abre un detalle que existe."""
    pagina = revisar(pedir(client, procedure, operator_user))
    assert [t["id"] for t in pagina.tiles] == ORDEN_ESPERADO
    abre = {t["id"]: t["data-detail"] for t in pagina.tiles}
    for clave, detalle in DETALLES.items():
        assert abre[clave] == detalle
        assert detalle in pagina.details


# --- Hojas de compliance ----------------------------------------------------------------------------


def test_hojas_de_compliance_cuenta_las_ofertas_con_hoja_y_dice_cuales_faltan(
        client, procedure, matrix, two_offers, evaluator_user, fake_ai):
    """REQ-126: «N de M» con la hoja presente por oferta; la línea de apoyo nombra las que faltan."""
    a, b = two_offers
    assert client.login(username=evaluator_user.username, password=TEST_PASSWORD)
    client.post(annex_url("s3_anexos_hoja", procedure, a), {"file": sheet_pdf()})
    tile = mosaico(pedir(client, procedure, evaluator_user), "compliance")
    plano = texto(tile)
    assert 'class="big' in tile and "Hojas de compliance" in plano
    assert re.search(r"1\s*de 2", plano)
    assert f"Falta la hoja de la oferta {b.number}" in plano and f"oferta {a.number}" not in plano


def test_hojas_de_compliance_con_todas_dice_que_estan_todas(
        client, procedure, matrix, two_offers, evaluator_user, fake_ai):
    """REQ-126: con todas las hojas, no se nombra ninguna oferta como faltante."""
    assert client.login(username=evaluator_user.username, password=TEST_PASSWORD)
    for oferta in two_offers:
        client.post(annex_url("s3_anexos_hoja", procedure, oferta), {"file": sheet_pdf()})
    plano = texto(mosaico(pedir(client, procedure, evaluator_user), "compliance"))
    assert re.search(r"2\s*de 2", plano) and "Falta" not in plano


def test_el_detalle_de_la_hoja_lista_cada_oferta(client, procedure, matrix, two_offers,
                                                 operator_user):
    """REQ-126: el parcial `d-s3-anexos` ya no está vacío: una fila por oferta, con su hoja."""
    pagina = revisar(pedir(client, procedure, operator_user))
    detalle = pagina.text_of("d-s3-anexos")
    for oferta in two_offers:
        assert oferta.bidder in detalle
    assert "Sin cargar" in detalle


# --- Documentación de las ofertas --------------------------------------------------------------------


def test_documentacion_cuenta_los_documentos_sin_denominador_inventado(
        client, procedure, matrix, two_offers, operator_user):
    """REQ-141, D-11: la cantidad de documentos de las ofertas, sin «de N»: el sistema no sabe
    cuántos debe presentar cada una."""
    tile = mosaico(pedir(client, procedure, operator_user), "docs")
    plano = texto(tile)
    esperado = sum(len(s3_ofertas.own_current(o)) for o in two_offers)
    assert esperado > 0
    assert 'class="big' in tile and re.search(rf"\b{esperado}\b", plano)
    assert not re.search(r"\bde \d+", plano), plano
    for oferta in two_offers:
        assert f"Oferta {oferta.number}" in plano


def test_documentacion_dice_que_cuenta_solo_los_documentos_propios(
        client, procedure, matrix, two_offers, evaluator_user, fake_ai):
    """REQ-141 (T-336): el mosaico dice «documentos propios» y «sin anexos técnicos ni hojas», para
    que no se lea como el total de la línea «Hay» (que cuenta también anexos y hojas)."""
    assert client.login(username=evaluator_user.username, password=TEST_PASSWORD)
    client.post(annex_url("s3_anexos_hoja", procedure, two_offers[0]), {"file": sheet_pdf()})
    propios = sum(len(s3_ofertas.own_current(o)) for o in two_offers)
    plano = texto(mosaico(pedir(client, procedure, evaluator_user), "docs"))
    assert re.search(rf"\b{propios}\s+documentos propios", plano), plano
    assert "Sin anexos técnicos ni hojas" in plano


# --- Fichas -----------------------------------------------------------------------------------------


def test_fichas_sin_ninguna_armada_es_un_cero_con_su_denominador_conocido(
        client, procedure, matrix, two_offers, operator_user):
    """REQ-141: 0 de 2 es un dato (el sistema conoce las 2 ofertas); no se muestra «Pendiente»."""
    tile = mosaico(pedir(client, procedure, operator_user), "fichas")
    plano = texto(tile)
    assert 'class="big' in tile and re.search(r"0\s*de 2", plano)
    assert 'class="missing"' not in tile


def test_la_ficha_abierta_despliega_el_detalle_de_la_ficha(client, procedure, matrix, two_offers,
                                                           operator_user):
    """REQ-127: `?ficha=` abre `d-s3-ficha`, donde está la ficha, y no el de las ofertas."""
    html = pedir(client, procedure, operator_user, f"?ficha={two_offers[0].pk}")
    assert Pagina(html).root["data-abre"] == "d-s3-ficha"
    assert s3_ficha.opens(SimpleNamespace(GET={"ficha": "3"})) == "d-s3-ficha"
    assert s3_ficha.opens(SimpleNamespace(GET={})) is None


# --- Circulares -------------------------------------------------------------------------------------


def test_circulares_sin_ninguna_dice_que_no_hay_y_no_muestra_cifra(client, procedure, matrix,
                                                                  operator_user):
    """REQ-141: sin circulares cargadas ni detectadas, el mosaico lo dice y no dibuja una cifra."""
    tile = mosaico(pedir(client, procedure, operator_user), "circulares")
    assert 'class="big' not in tile and 'class="missing"' in tile


def test_circulares_cuenta_las_cargadas(client, procedure, matrix, operator_user):
    """REQ-126: dos circulares cargadas, dos."""
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    client.post(circular_url(procedure), {
        "files": [pdf_file("c1.pdf"), pdf_file("c2.pdf")], "kind": "circular_aclaratoria",
        "issued_on": "2026-09-20"})
    tile = mosaico(pedir(client, procedure, operator_user), "circulares")
    assert 'class="big' in tile and re.search(r">\s*2\s*<", tile)
    assert not re.search(r"\bde \d+", texto(tile))


def test_los_modos_de_circulares_y_anexos_abren_su_detalle():
    """REQ-127: el aviso de las circulares abre `d-s3-circulares`; el de los anexos, el de las
    ofertas (donde están sus botones)."""
    assert s3_circulares.opens(SimpleNamespace(GET={s3_circulares.PARAM: "x"})) == "d-s3-circulares"
    assert s3_circulares.opens(SimpleNamespace(GET={})) is None
    assert s3_anexos.opens(SimpleNamespace(GET={s3_anexos.PARAM: "x"})) == "d-s3-ofertas"
    assert s3_anexos.opens(SimpleNamespace(GET={})) is None


# --- Sin ofertas ------------------------------------------------------------------------------------


def test_sin_ofertas_los_cuatro_mosaicos_nuevos_dicen_que_falta(client, procedure, matrix,
                                                                operator_user):
    """REQ-141: sin ofertas, ni cifra ni gráfico en los mosaicos nuevos."""
    html = pedir(client, procedure, operator_user)
    for clave in ("compliance", "docs", "fichas", "circulares"):
        tile = mosaico(html, clave)
        assert 'class="big' not in tile and 'class="ch"' not in tile, clave
        assert 'class="missing"' in tile, clave


def test_ningun_mosaico_oscuro_lleva_graficos_de_estado(client, procedure, matrix, two_offers,
                                                        operator_user):
    """Los mosaicos nuevos son claros; si alguno fuera oscuro no lleva gráfico de estado."""
    html = pedir(client, procedure, operator_user)
    for clave in ("compliance", "docs", "fichas", "circulares"):
        antes = html.split(f'id="m-{clave}"')[0].rsplit("<a ", 1)[1]
        if "dark" in antes:
            for estado in ("g-ok", "g-no", "g-nd", "g-pe"):
                assert estado not in mosaico(html, clave)
