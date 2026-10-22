"""Los tableros no inventan datos (REQ-141; plan 017, «Tablero: mosaicos y detalle»; ADR-0076).

Con un procedimiento vacío ningún mosaico muestra una cifra: todos dicen «falta» o «pendiente».
Recorre los temas que declaran `tiles()`. Datos inventados (P4)."""

from datetime import date

import pytest
from django.urls import reverse

from evaluon.journey import temas
from evaluon.journey.tablero.tiles import Tile
from evaluon.tenders.models import Procedure
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.test_tablero_secciones import Pagina, tema_con_mosaicos

pytestmark = pytest.mark.django_db

# Mosaicos cuyo dato es de la instalación y no del procedimiento (por ejemplo, las normas
# cargadas en toda la base). Cada uno entra con su razón escrita; por omisión no hay ninguno.
RAZON_NORMAS = ("Normas cargadas cuenta las normas de toda la base, comunes a todos los "
                "procedimientos; sin ninguna dice «Falta cargar normas» (T-329, "
                "tests/journey/temas/test_s5_tiles.py)")
# Se declara con la clave del mosaico y con su id en la página (`m-…`): el primer test mira el id y
# el segundo, la clave.
DATO_DE_LA_INSTALACION: dict[str, str] = {"cargadas": RAZON_NORMAS, "m-cargadas": RAZON_NORMAS}


@pytest.fixture
def vacio(operator_user):
    return Procedure.objects.create(number="VACIO-SINTETICO", procedure_type="Prueba",
                                    subject="Procedimiento inventado sin nada cargado",
                                    authorization_date=date(2026, 1, 5), created_by=operator_user)


def mosaicos_html(html):
    """El HTML de cada mosaico del tablero, tal como lo ve la persona."""
    partes = html.split('<a class="tile')[1:]
    return [parte.split("</a>")[0] for parte in partes]


def test_con_un_procedimiento_vacio_ningun_mosaico_muestra_cifra(client, vacio, operator_user):
    """REQ-141: los mosaicos de los temas reales, sobre un procedimiento vacío, dicen «falta» o
    «pendiente» y no dibujan ni cifra ni gráfico."""
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    secciones = {tema.SECTION for tema in tema_con_mosaicos()}
    for seccion in secciones:
        html = client.get(reverse(f"expedientes:{seccion}", args=[vacio.pk])).content.decode()
        pagina = Pagina(html)
        assert pagina.tiles, seccion
        for tile in mosaicos_html(html):
            ident = tile.split('id="')[1].split('"')[0] if 'id="' in tile else tile[:60]
            if ident in DATO_DE_LA_INSTALACION:
                continue
            assert 'class="big' not in tile, f"{ident} muestra una cifra sin procedimiento"
            assert "<small>" not in tile
            assert 'class="missing"' in tile, f"{ident} no dice qué falta"
            assert 'class="ch"' not in tile, f"{ident} dibuja un gráfico sin datos"


def test_ningun_tema_inventa_cifra_con_el_procedimiento_vacio(vacio, operator_user, rf):
    """REQ-141: lo mismo a nivel de `tiles()`: ningún `Tile` del procedimiento vacío tiene `big`."""
    request = rf.get("/")
    request.user = operator_user
    for tema in tema_con_mosaicos():
        ctx = tema.context(operator_user, vacio, request)
        for tile in tema.tiles(operator_user, vacio, ctx):
            if tile.key in DATO_DE_LA_INSTALACION:
                continue
            assert isinstance(tile, Tile)
            assert not tile.has_data, f"{tema.KEY}/{tile.key} muestra {tile.big!r}"
            assert tile.missing, f"{tema.KEY}/{tile.key} no dice qué falta"


def test_un_mosaico_sin_cifra_dice_su_falta_aunque_traiga_unidad_y_grafico():
    """REQ-141: la regla vale en la plantilla, no en cada tema: aunque el tema pase unidad y
    gráfico, con `big` en `None` solo se ve `missing`."""
    from decimal import Decimal

    from django.template.loader import render_to_string

    from evaluon.journey.tablero import charts

    tile = Tile(key="a", title="Orden económico", detail="d-s3-orden", unit="miles",
                missing="Pendiente",
                chart=charts.Columns(uid="x", title="T", items=[
                    charts.ColumnItem("Of. 1", Decimal("5"), "5")]))
    html = render_to_string("journey/_mosaico.html", {"tile": tile})
    assert "Pendiente" in html
    assert 'class="big' not in html and "<small>" not in html and 'class="ch"' not in html


def test_ningun_tema_declara_mosaicos_sin_el_contrato_completo():
    """Definición compartida 2: quien declara `tiles()` declara con la firma del contrato, y
    `opens` (si existe) recibe el pedido."""
    import inspect
    for tema in tema_con_mosaicos():
        assert list(inspect.signature(tema.tiles).parameters) == ["user", "procedure", "ctx"], \
            tema.KEY
        if hasattr(tema, "opens"):
            assert list(inspect.signature(tema.opens).parameters) == ["request"], tema.KEY
    assert temas.TEMAS


def instalar_mosaicos_que_cuentan(monkeypatch):
    """Un tema de prueba cuyos mosaicos calculan su cifra desde la base y la dejan en `None` si
    no hay dato, como tienen que hacer los temas reales."""
    tema = temas.by_key("s3_ofertas")

    def tiles(user, procedure, ctx):
        cantidad = procedure.offers.count() or None
        return [Tile(key="acta", title="Ofertas del acta", detail="d-s3-ofertas", width=2,
                     big=cantidad, unit="ofertas", missing="Falta cargar las ofertas"),
                Tile(key="orden", title="Orden económico", detail="d-s3-ofertas", big=None)]

    monkeypatch.setattr(tema, "tiles", tiles, raising=False)
    # Desde T-326 los otros temas de Ofertas declaran sus mosaicos; acá se apagan para probar el
    # tema de prueba solo (los reales los cubre `test_con_un_procedimiento_vacio_...`).
    for clave in ("s3_ficha", "s3_anexos", "s3_circulares"):
        monkeypatch.setattr(temas.by_key(clave), "tiles", lambda user, proc, ctx: [], raising=False)


def test_la_pagina_de_un_procedimiento_vacio_no_muestra_cifras(client, vacio, operator_user,
                                                                monkeypatch):
    """REQ-141: de punta a punta, un procedimiento sin ofertas dice «Falta …» y «Pendiente»."""
    instalar_mosaicos_que_cuentan(monkeypatch)
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    html = client.get(reverse("expedientes:ofertas", args=[vacio.pk])).content.decode()
    tarjetas = mosaicos_html(html)
    assert len(tarjetas) == 2
    assert all('class="big' not in t and 'class="missing"' in t for t in tarjetas)
    assert "Falta cargar las ofertas" in tarjetas[0] and "Pendiente" in tarjetas[1]


def test_con_ofertas_el_mosaico_muestra_la_cifra(client, procedure, offer, operator_user,
                                                  monkeypatch):
    """REQ-126: el mismo tema, con un dato que existe, dibuja la cifra (no es siempre «falta»)."""
    instalar_mosaicos_que_cuentan(monkeypatch)
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    html = client.get(reverse("expedientes:ofertas", args=[procedure.pk])).content.decode()
    assert 'class="big">1<small>ofertas</small>' in mosaicos_html(html)[0]
