"""El tablero de la sección Ofertas (REQ-126, REQ-127, REQ-130, REQ-141; plan 017, «Tablero:
mosaicos y detalle» y «Orden económico»; T-315). Caso chico y público: tres ofertas inventadas con
su total del Portal. El despliegue en el navegador se revisa a mano (T-316)."""

import time
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.urls import reverse

from evaluon.journey import temas
from evaluon.journey.tablero import economico
from evaluon.journey.temas import s3_ofertas
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.test_economico import make, opening, portal  # noqa: F401  (fixtures)
from tests.journey.test_tablero_secciones import Pagina, revisar

pytestmark = pytest.mark.django_db

ACTA = "d-s3-ofertas"
ORDEN = "d-s3-orden"


@pytest.fixture
def tres(make):  # noqa: F811
    """Tres ofertas con total: la 2 es la más baja y la 3 la más alta."""
    return [make(1, Decimal("1100.00")), make(2, Decimal("1000.00")), make(3, Decimal("1250.00"))]


def pedir(client, procedure, user, consulta=""):
    assert client.login(username=user.username, password=TEST_PASSWORD)
    respuesta = client.get(reverse("expedientes:ofertas", args=[procedure.pk]) + consulta)
    assert respuesta.status_code == 200
    return respuesta.content.decode()


def mosaico(html, clave):
    """El HTML del mosaico `m-<clave>`."""
    return html.split(f'id="m-{clave}"')[1].split("</a>")[0]


def clases(html, clave):
    """Las clases del mosaico `m-<clave>`."""
    return html.split(f'id="m-{clave}"')[0].rsplit("<a ", 1)[1]


# --- El tablero abre con sus mosaicos ---------------------------------------------------------------


def test_el_tablero_de_ofertas_abre_con_sus_cuatro_mosaicos(client, procedure, matrix, tres,
                                                           operator_user):
    """REQ-126: la sección Ofertas abre con su tablero; cada mosaico abre un detalle que existe."""
    pagina = revisar(pedir(client, procedure, operator_user))
    assert [t["id"] for t in pagina.tiles] == ["m-acta", "m-baja", "m-alta", "m-orden"]
    assert [t["data-detail"] for t in pagina.tiles] == [ACTA, ORDEN, ORDEN, ORDEN]
    assert ACTA in pagina.details and ORDEN in pagina.details


def test_los_mosaicos_con_tres_ofertas_dicen_lo_que_el_sistema_tiene(client, procedure, matrix,
                                                                    tres, operator_user):
    """REQ-126, REQ-130: la cantidad, la más baja, la más alta y el orden salen de los totales."""
    html = pedir(client, procedure, operator_user)
    acta, baja, alta, orden = (mosaico(html, k) for k in ("acta", "baja", "alta", "orden"))
    assert 'class="big' in acta and ">3<" in acta.replace(" ", "") and "ofertas" in acta
    assert "1.000,00" in baja and "Oferta 2" in baja
    assert "1.250,00" in alta and "Oferta 3" in alta
    assert "dark" in clases(html, "baja") and "dark" not in clases(html, "alta")
    assert 'class="ch"' in acta and 'class="ch"' in orden
    assert "25,0" in orden  # lo que se aparta la más alta de la más baja


def test_el_mosaico_oscuro_no_lleva_graficos_de_estado(client, procedure, matrix, tres,
                                                       operator_user):
    """El tono oscuro no tiene medidos los colores de estado: «La más baja» no dibuja gráfico."""
    baja = mosaico(pedir(client, procedure, operator_user), "baja")
    assert 'class="ch"' not in baja
    for estado in ("g-ok", "g-no", "g-nd", "g-pe"):
        assert estado not in baja


def test_ofertas_del_acta_despliega_la_comparacion_de_las_ofertas(client, procedure, matrix,
                                                                 tres, operator_user):
    """REQ-127: el detalle de «Ofertas del acta» trae a las tres ofertas con su total."""
    pagina = revisar(pedir(client, procedure, operator_user))
    texto = pagina.text_of(ACTA)
    for oferente in ("Oferente Sintético 1", "Oferente Sintético 2", "Oferente Sintético 3"):
        assert oferente in texto
    for total in ("1.100,00", "1.000,00", "1.250,00"):
        assert total in texto


# --- Orden económico -------------------------------------------------------------------------------


def test_el_orden_economico_con_tres_ofertas_va_de_menor_a_mayor(client, procedure, matrix, tres,
                                                                 operator_user):
    """REQ-130: de menor a mayor, con la más baja, la más alta y la diferencia."""
    texto = revisar(pedir(client, procedure, operator_user)).text_of(ORDEN)
    assert texto.index("Oferta 2") < texto.index("Oferta 1") < texto.index("Oferta 3")
    assert "La más baja" in texto and "La más alta" in texto
    assert "+10,0 %" in texto and "+25,0 %" in texto


def test_sin_ofertas_el_orden_muestra_el_dia_de_la_apertura_y_pendiente(
        client, procedure, matrix, opening, operator_user):
    """REQ-130, REQ-141: sin ofertas, el día de la apertura y «Pendiente», sin cifras en los
    mosaicos."""
    html = pedir(client, procedure, operator_user)
    pagina = revisar(html)
    texto = pagina.text_of(ORDEN)
    assert "22/09/2026" in texto and "Pendiente" in texto
    for clave in ("acta", "baja", "alta", "orden"):
        tile = mosaico(html, clave)
        assert 'class="big' not in tile and 'class="ch"' not in tile
        assert 'class="missing"' in tile


def test_con_un_solo_total_la_mas_alta_dice_que_falta(client, procedure, matrix, make,  # noqa: F811
                                                      operator_user):
    """REQ-141: con una sola oferta no hay «más alta»: el mosaico dice qué falta."""
    make(1, Decimal("1000.00"))
    html = pedir(client, procedure, operator_user)
    assert 'class="big' in mosaico(html, "baja")
    alta = mosaico(html, "alta")
    assert 'class="big' not in alta and 'class="missing"' in alta


def test_ofertas_sin_total_muestran_solo_la_cantidad(client, procedure, matrix, make,  # noqa: F811
                                                     operator_user):
    """REQ-141: sin totales, «Ofertas del acta» da la cantidad y no dibuja columnas; el orden y
    la más baja dicen que falta el total."""
    make(1, None)
    make(2, False)
    html = pedir(client, procedure, operator_user)
    acta = mosaico(html, "acta")
    assert ">2<" in acta.replace(" ", "") and 'class="ch"' not in acta
    for clave in ("baja", "alta", "orden"):
        tile = mosaico(html, clave)
        assert 'class="big' not in tile and "Falta el total" in tile


def test_el_orden_economico_se_calcula_una_sola_vez_por_pedido(client, procedure, matrix, tres,
                                                               operator_user, monkeypatch):
    """Aviso de T-314: los tres mosaicos y el detalle comparten un solo cálculo."""
    llamadas = []
    original = economico.economic_view
    monkeypatch.setattr(economico, "economic_view",
                        lambda *a, **k: llamadas.append(1) or original(*a, **k))
    pedir(client, procedure, operator_user)
    assert len(llamadas) == 1


def test_los_ids_de_los_cuadros_no_se_repiten(client, procedure, matrix, tres, operator_user):
    """Cada cuadro y gráfico lleva su propio id: sin repetidos en la página."""
    pagina = Pagina(pedir(client, procedure, operator_user))
    assert len(pagina.ids) == len(set(pagina.ids))


# --- Modos y temas sin mosaico ----------------------------------------------------------------------


@pytest.mark.parametrize("consulta", ["?oferta={o}", "?ficha={o}", "?oferta={o}&historial=1"])
def test_los_parametros_de_modo_abren_el_detalle_de_las_ofertas(client, procedure, matrix, tres,
                                                               operator_user, consulta):
    """REQ-127: `?oferta=`, `?ficha=` y `?historial=` abren el detalle «Ofertas del acta»."""
    html = pedir(client, procedure, operator_user, consulta.format(o=tres[0].pk))
    assert Pagina(html).root["data-abre"] == ACTA


def test_sin_parametros_no_se_abre_ningun_detalle(client, procedure, matrix, tres, operator_user):
    """REQ-127: sin parámetro de modo, el tablero abre plegado."""
    assert "data-abre" not in Pagina(pedir(client, procedure, operator_user)).root


def test_opens_reconoce_el_historial_aunque_venga_solo():
    """REQ-127: `opens` devuelve el detalle de las ofertas o nada."""
    assert s3_ofertas.opens(SimpleNamespace(GET={"historial": "3"})) == ACTA
    assert s3_ofertas.opens(SimpleNamespace(GET={})) is None


def test_los_parciales_de_los_temas_sin_mosaico_siguen_accesibles(client, procedure, matrix, tres,
                                                                  operator_user):
    """T-315: circulares, anexos y ficha (aún sin mosaico) se ven como hoy, debajo del tablero."""
    html = pedir(client, procedure, operator_user)
    assert 'id="seccion-detalle"' in html and 'id="s3-circulares"' in html
    assert html.index('id="seccion-detalle"') > html.index('class="detalles"')
    assert {t.KEY for t in temas.TEMAS if t.SECTION == "ofertas"} >= {"s3_circulares"}


# --- Tiempo -----------------------------------------------------------------------------------------


def test_el_tablero_se_arma_en_dos_segundos_con_el_caso_chico(client, procedure, matrix, tres,
                                                              operator_user):
    """Umbral del plan: 2 s o menos hasta tener la página completa con el caso chico."""
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    url = reverse("expedientes:ofertas", args=[procedure.pk])
    client.get(url)  # la primera carga calienta plantillas y conexiones
    inicio = time.perf_counter()
    assert client.get(url).status_code == 200
    assert time.perf_counter() - inicio <= 2.0
