"""El tablero de las secciones (REQ-126, REQ-127; plan 017, «Tablero: mosaicos y detalle»;
ADR-0076; definiciones compartidas 1 a 3 y 9). Datos inventados (P4).

Recorre todos los temas que declaran `tiles()`: cada bloque nuevo queda cubierto sin editar este
archivo. Como los temas todavía no declaran mosaicos, el resto de las pruebas instala unos de
prueba en `s3_ofertas`. El despliegue en el navegador se revisa en T-316."""

from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

import pytest
from django.urls import reverse

from evaluon.journey import sections, temas
from evaluon.journey.tablero import charts, economico
from evaluon.journey.tablero.tiles import Detail, Tile
from tests.accounts.test_session import TEST_PASSWORD

pytestmark = pytest.mark.django_db

DETALLES = "d-s3-ofertas"


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def tema_con_mosaicos():
    return [t for t in temas.TEMAS if hasattr(t, "tiles")]


# --- Lectura del HTML ----------------------------------------------------------------------------


class Pagina(HTMLParser):
    """Lo que hace falta del HTML: mosaicos, detalles (con su texto) y enlaces a anclas."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.tiles, self.details, self.ids, self.anchors = [], {}, [], []
        self.root, self.zone_depth = {}, None
        self._stack, self._detail = [], None
        self.outside_text = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if a.get("id"):
            self.ids.append(a["id"])
        if "tablero" in classes:
            self.root = a
        if tag == "a" and "tile" in classes:
            self.tiles.append(a)
        if "inline-detail" in classes:
            self._detail = {"id": a.get("id"), "depth": len(self._stack), "text": [], "ids": []}
            self.details[a.get("id")] = self._detail
        elif self._detail is not None:
            if a.get("id"):
                self._detail["ids"].append(a["id"])
            if tag == "a" and (a.get("href") or "").startswith("#"):
                self.anchors.append(a["href"][1:])
        if tag not in ("br", "img", "input", "meta", "link", "hr", "path", "circle", "rect",
                       "line", "polyline", "polygon", "ellipse"):
            self._stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self._stack:
            while self._stack and self._stack.pop() != tag:
                pass
        if self._detail is not None and len(self._stack) <= self._detail["depth"]:
            self._detail = None

    def handle_data(self, data):
        if self._detail is not None:
            self._detail["text"].append(data)
        else:
            self.outside_text.append(data)

    def text_of(self, ident):
        return " ".join("".join(self.details[ident]["text"]).split())


def revisar(html):
    """Las condiciones de REQ-126 y REQ-127 sobre una página de sección con tablero."""
    pagina = Pagina(html)
    assert pagina.root, "la sección no abre con su tablero"
    assert pagina.tiles, "el tablero no tiene mosaicos"
    llaves = [t.get("id") for t in pagina.tiles]
    assert len(llaves) == len(set(llaves)), "mosaicos con id repetido"
    assert len(pagina.details) == len(set(pagina.details)), "detalles con id repetido"
    for tile in pagina.tiles:
        destino = tile.get("data-detail")
        if destino is None:  # enlace a otra pantalla
            assert not (tile.get("href") or "").startswith("#")
            continue
        assert destino in pagina.details, f"el mosaico {tile.get('id')} abre {destino}, que no existe"
        assert tile["href"] == f"#{destino}"
        assert tile.get("aria-controls") == destino
    for detalle in pagina.details.values():
        assert detalle["id"].startswith("d-")
    for ancla in pagina.anchors:
        assert ancla in pagina.ids, f"el enlace a #{ancla} no tiene destino"
    return pagina


# --- Mosaicos de prueba --------------------------------------------------------------------------


@pytest.fixture
def con_mosaicos(monkeypatch, procedure):
    """Instala `tiles`, `details` y `opens` de prueba en el tema de Ofertas."""
    tema = temas.by_key("s3_ofertas")

    def tiles(user, proc, ctx):
        return [
            Tile(key="acta", title="Ofertas del acta", detail=DETALLES, width=2, big="3",
                 unit="ofertas", sub="Con su total",
                 chart=charts.Columns(uid="t-acta", title="Totales", items=[
                     charts.ColumnItem("Of. 1", Decimal("100"), "100"),
                     charts.ColumnItem("Of. 2", Decimal("90"), "90", highlight=True)])),
            Tile(key="baja", title="La más baja", detail=DETALLES, big="90", unit="miles"),
            Tile(key="alta", title="La más alta", detail=DETALLES, tone="dark", big=None,
                 missing="Falta el total"),
            Tile(key="orden", title="Orden económico", detail="d-s3-orden", big=None),
        ]

    def details(user, proc, ctx):
        return [Detail("d-s3-orden", "Orden económico", "journey/_economico.html",
                       {"orden": economico.economic_view(proc, uid="prueba")})]

    def opens(request):
        return DETALLES if request.GET.get("oferta") else None

    monkeypatch.setattr(tema, "tiles", tiles, raising=False)
    monkeypatch.setattr(tema, "details", details, raising=False)
    monkeypatch.setattr(tema, "opens", opens, raising=False)


def pedir(client, procedure, user, clave="ofertas", consulta=""):
    log_in(client, user)
    respuesta = client.get(reverse(f"expedientes:{clave}", args=[procedure.pk]) + consulta)
    assert respuesta.status_code == 200
    return respuesta.content.decode()


# --- Pruebas -------------------------------------------------------------------------------------


def test_cada_seccion_que_declara_mosaicos_abre_con_su_tablero(client, procedure, matrix, offer,
                                                              operator_user):
    """REQ-126: la sección abre con su tablero; cada mosaico tiene un detalle existente con id
    único, `aria-controls` coincide y cada ancla usada existe (recorre los temas reales)."""
    por_seccion = {}
    for tema in tema_con_mosaicos():
        por_seccion.setdefault(tema.SECTION, []).append(tema)
    for seccion in por_seccion:
        revisar(pedir(client, procedure, operator_user, seccion))


def test_la_seccion_abre_con_su_tablero_y_cada_mosaico_tiene_su_detalle(
        client, procedure, matrix, operator_user, con_mosaicos):
    """REQ-126: tablero con mosaicos antes de los detalles; cada mosaico abre uno que existe."""
    html = pedir(client, procedure, operator_user)
    pagina = revisar(html)
    assert [t["data-detail"] for t in pagina.tiles] == [DETALLES, DETALLES, DETALLES, "d-s3-orden"]
    assert html.index('class="board"') < html.index('class="detalles"')
    assert "Ofertas del acta" in html and "La más baja" in html


def test_varios_mosaicos_abren_el_mismo_detalle(client, procedure, matrix, operator_user,
                                                con_mosaicos):
    """REQ-127: «La más baja» y «Ofertas del acta» abren el mismo detalle, que está una sola vez."""
    pagina = revisar(pedir(client, procedure, operator_user))
    assert sum(t["data-detail"] == DETALLES for t in pagina.tiles) == 3
    assert list(pagina.details).count(DETALLES) == 1


def test_el_detalle_trae_el_parcial_del_tema_ya_renderizado(client, procedure, matrix,
                                                            operator_user, con_mosaicos):
    """REQ-127: el parcial del tema (con sus formularios) está dentro de su detalle."""
    pagina = revisar(pedir(client, procedure, operator_user))
    assert {"s3-ofertas", "s3-alta-portal"} <= set(pagina.details[DETALLES]["ids"])
    assert "Ofertas del acta" in pagina.text_of(DETALLES)


def test_el_detalle_propio_de_un_tema_se_dibuja_con_su_plantilla(client, procedure, matrix,
                                                                 operator_user, con_mosaicos):
    """REQ-130: un detalle extra (el orden económico) usa `_economico.html`."""
    pagina = revisar(pedir(client, procedure, operator_user))
    assert "Orden económico" in pagina.text_of("d-s3-orden")
    assert "prueba" in pagina.details["d-s3-orden"]["ids"]


def test_los_temas_sin_mosaico_siguen_accesibles(client, procedure, matrix, operator_user,
                                                 con_mosaicos):
    """T-315: el parcial de un tema que no tiene mosaico sigue a la vista, fuera de los detalles
    y dentro de `#seccion-detalle` como hoy."""
    html = pedir(client, procedure, operator_user)
    pagina = Pagina(html)
    assert 's3-circulares' in html
    assert "s3-circulares" not in " ".join(i for d in pagina.details.values() for i in d["ids"])
    assert html.index('id="seccion-detalle"') < html.index('id="s3-circulares"')


def test_un_parametro_de_modo_abre_su_detalle(client, procedure, matrix, operator_user,
                                              con_mosaicos):
    """REQ-127: `opens(request)` dice qué detalle abre `?oferta=`."""
    sin = Pagina(pedir(client, procedure, operator_user))
    con = Pagina(pedir(client, procedure, operator_user, consulta="?oferta=1"))
    assert "data-abre" not in sin.root
    assert con.root["data-abre"] == DETALLES


def test_sin_mosaicos_la_seccion_se_muestra_como_hoy(client, procedure, matrix, operator_user):
    """REQ-126: mientras un tema no declara `tiles()`, la sección sigue con sus parciales."""
    assert not any(t.SECTION == "ofertas" for t in tema_con_mosaicos())
    html = pedir(client, procedure, operator_user)
    assert 'class="tablero"' not in html
    for marca in ('id="seccion-titulo"', 'id="seccion-resumen"', 'id="pendientes"',
                  'id="seccion-detalle"'):
        assert marca in html


def test_la_pagina_con_tablero_enlaza_el_script_y_no_lleva_scripts_en_linea(
        client, procedure, matrix, operator_user, con_mosaicos):
    """ADR-0076: `tablero.js` se enlaza como archivo; la política de contenido no admite
    scripts ni estilos en línea."""
    html = pedir(client, procedure, operator_user)
    assert "journey/tablero.js" in html and "journey/tablero.css" in html
    assert "<script>" not in html


def test_el_tablero_deja_los_huecos_de_otras_tareas():
    """T-312 (Hay/Falta) llena su bloque de `seccion.html` al integrar y acá tiene que seguir
    definido y vacío. El de pendientes lo llenó T-318 (`test_pendientes.py` lo comprueba) y tiene
    que seguir entre Hay/Falta y el tablero."""
    texto = (Path(__file__).resolve().parents[2] / "evaluon" / "templates" / "journey"
             / "seccion.html").read_text(encoding="utf-8")
    assert "{% block hay_falta %}{% endblock %}" in texto
    assert "{% block pendientes %}" in texto
    assert texto.index("block hay_falta") < texto.index("block pendientes") < texto.index(
        "journey/_tablero.html")


def test_la_seccion_junta_los_mosaicos_de_sus_temas_en_orden(procedure, matrix, operator_user,
                                                             con_mosaicos):
    """Definición compartida 2: `Section.tiles` junta los de sus temas, con el contexto de cada
    uno; `Section.opens` da el primer detalle que algún tema abre."""
    from types import SimpleNamespace
    section = sections.sections_for(operator_user, procedure).get("ofertas")
    assert [t.key for t in section.tiles(operator_user, procedure, {})] == [
        "acta", "baja", "alta", "orden"]
    pedido = SimpleNamespace(GET={"oferta": "1"})
    assert section.opens(pedido) == DETALLES
    assert section.opens(SimpleNamespace(GET={})) is None
    assert section.ingreso_template is None and section.ingreso_context(operator_user,
                                                                        procedure) == {}


def test_las_demas_secciones_no_cambian_con_los_mosaicos_de_ofertas(
        client, procedure, matrix, operator_user, con_mosaicos):
    """REQ-126: los mosaicos de una sección no aparecen en otra."""
    html = pedir(client, procedure, operator_user, "pliego")
    assert 'class="tablero"' not in html and "Ofertas del acta" not in html
