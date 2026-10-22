"""El tablero de la sección Normativas y la página general de normativas (REQ-126, REQ-129,
REQ-141; plan 017, «Tablero: mosaicos y detalle»; T-329). Normas sintéticas con contenido inventado
(P4); no se usa ningún modelo."""

import datetime
import re
import time
from pathlib import Path

import pytest
from django.urls import reverse

from evaluon.journey import sections
from evaluon.journey.temas import s5_consulta, s5_normas, s5_rigen
from evaluon.journey.tablero.tiles import Tile
from evaluon.portal.models import PortalProcedureData
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.test_tablero_secciones import Pagina, revisar
from tests.tenders.conftest import evaluator_user, operator_user  # noqa: F401
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import load_and_read, make_procedure

pytestmark = pytest.mark.django_db

ROOT = Path(__file__).resolve().parents[3]
AFTER = datetime.date(2024, 5, 20)
CLAVES = {"rigen", "citas", "regimen", "consulta", "cargadas"}


@pytest.fixture
def after(operator_user):
    return make_procedure(operator_user, AFTER)


class Pedido:
    GET = {}


def tiles_de(tema, user, procedure):
    return {t.key: t for t in tema.tiles(user, procedure, tema.context(user, procedure, Pedido))}


def todos(user, procedure):
    found = {}
    for tema in (s5_rigen, s5_consulta, s5_normas):
        found.update(tiles_de(tema, user, procedure))
    return found


def con_pliego(procedure, user, texto):
    source = load_and_read(user, procedure, tender_pdf([[para("PLIEGO SINTÉTICO"), para("1. Objeto.")]]),
                           title="Pliego", file_name="pliego.pdf")
    PortalProcedureData.objects.create(procedure=procedure, legal_framework=texto, document=source)


def abrir(client, user, procedure, consulta=""):
    assert client.login(username=user.username, password=TEST_PASSWORD)
    response = client.get(reverse("expedientes:normativas", args=[procedure.pk]) + consulta)
    assert response.status_code == 200
    return response.content.decode()


# --- Los mosaicos --------------------------------------------------------------------------------


def test_la_seccion_declara_sus_cinco_mosaicos_con_los_detalles_de_la_014(after, operator_user):
    """REQ-126: Normas que rigen, Citas del pliego, Régimen que rige, Consulta de normativa y
    Normas cargadas; cada uno abre el parcial de su tema (`d-s5-…`)."""
    found = todos(operator_user, after)
    assert set(found) == CLAVES
    assert all(isinstance(t, Tile) for t in found.values())
    assert {k: found[k].detail for k in found} == {
        "rigen": "d-s5-rigen", "citas": "d-s5-rigen", "regimen": "d-s5-rigen",
        "consulta": "d-s5-consulta", "cargadas": "d-s5-normas"}


def test_sin_normas_cargadas_ningun_mosaico_muestra_cifra(after, operator_user):
    """REQ-141: sin normas cargadas todo dice «Falta …» o «Pendiente» y no trae ni cifra ni
    gráfico (la cifra no es nunca un cero inventado)."""
    for key, tile in todos(operator_user, after).items():
        assert not tile.has_data, f"{key} muestra {tile.big!r}"
        assert tile.missing and tile.chart is None, key
    assert todos(operator_user, after)["rigen"].missing.startswith("Falta")
    assert todos(operator_user, after)["cargadas"].missing.startswith("Falta")


def test_normas_que_rigen_cuenta_las_validadas_sobre_las_que_hacen_falta(after, two_regimes, operator_user):
    """REQ-126: «N de M»: la 247/2022 validada, y faltan el marco nacional (dos decretos) sin
    cargar. La 297/03 no aplica y no cuenta."""
    tile = todos(operator_user, after)["rigen"]
    assert tile.big == "1" and tile.unit == "de 3"
    assert "validada" in tile.sub and "2 faltan" in tile.sub


def test_normas_que_rigen_distingue_la_cargada_sin_validar(after, make_norm, make_document,
                                                             make_reading, operator_user):
    """REQ-126: una norma cargada con su lectura sin validar es dato (cuenta 0 validadas), no
    «Falta»."""
    norm = make_norm(norm_type="disposicion", number="247", year=2022, issuer="afip",
                     citation="Disposición AFIP 247/2022", general_regime=True)
    make_reading(make_document(norm), [("art-1", "ARTICULO 1.- Texto sintético.")],
                 status="pending")
    tile = todos(operator_user, after)["rigen"]
    assert tile.has_data and tile.big == "0" and "1 sin validar" in tile.sub


def test_el_regimen_que_rige_sale_de_la_fecha_de_autorizacion(after, two_regimes, operator_user):
    """REQ-126: el régimen es el que devuelve `applicable_regimes` a la fecha; la 297/03 no."""
    tile = todos(operator_user, after)["regimen"]
    assert tile.big == "247/2022" and "Disposición AFIP 247/2022" in tile.sub
    assert "20/05/2024" in tile.sub and "297/03" in tile.sub


def test_sin_regimen_cargado_el_mosaico_dice_que_falta(after, operator_user):
    """REQ-141: sin la norma del régimen en el sistema no se afirma cuál rige."""
    tile = todos(operator_user, after)["regimen"]
    assert not tile.has_data and tile.missing.startswith("Falta")


def test_las_citas_del_pliego_cuentan_normas_citadas_y_cargadas(
        after, operator_user, two_regimes, make_norm, make_document, make_reading):
    """REQ-126, plan 017 D: «N normas citadas · M cargadas», no menciones en el texto."""
    con_pliego(after, operator_user,
               "Disp. 247/22, Resolución N.º 12/2020, Ley 24.156/1992 y otra vez Disp. 247/22")
    norm = make_norm(norm_type="resolucion", number="12", year=2020, issuer="organismo sintetico",
                     citation="Resolución 12/2020")
    make_reading(make_document(norm), [("art-1", "ARTICULO 1.- Monto sintético.")])
    tile = todos(operator_user, after)["citas"]
    assert tile.big == "3" and tile.unit == "citadas"
    assert "2 cargadas" in tile.sub
    assert tile.chart is not None and tile.chart.has_data


def test_sin_encuadre_legal_las_citas_dicen_que_falta(after, operator_user):
    """REQ-141: un pliego sin encuadre legal no tiene citas: «Falta …», sin cifra."""
    tile = todos(operator_user, after)["citas"]
    assert not tile.has_data and tile.missing.startswith("Falta")


def test_encuadre_sin_normas_reconocibles_no_inventa_un_cero(after, operator_user):
    """REQ-141: un encuadre del que no se reconoce ninguna norma no muestra «0 citadas»."""
    con_pliego(after, operator_user, "Según lo que disponga la autoridad competente")
    tile = todos(operator_user, after)["citas"]
    assert not tile.has_data


def test_la_consulta_sin_historial_no_muestra_cifra_y_la_apagada_lo_dice(after, operator_user,
                                                                          monkeypatch):
    """REQ-141, REQ-129: sin consultas hechas dice «Sin consultas»; con la consulta apagada la
    razón queda dicha en el mosaico, como en la 014."""
    monkeypatch.setattr(s5_consulta.services, "consulta_notice", lambda: "")
    assert not todos(operator_user, after)["consulta"].has_data
    monkeypatch.setattr(s5_consulta.services, "consulta_notice",
                        lambda: "La consulta está apagada ahora.")
    tile = todos(operator_user, after)["consulta"]
    assert not tile.has_data and "apagada" in (tile.sub + tile.missing)


def test_la_consulta_con_historial_cuenta_las_consultas(after, operator_user, monkeypatch):
    """REQ-126: con consultas hechas muestra cuántas son y la última."""
    monkeypatch.setattr(s5_consulta.services, "consulta_notice", lambda: "")
    ctx = s5_consulta.context(operator_user, after, None)
    ctx["history"] = [{"id": 2, "when": "01/10/2026 10:00", "question": "¿Qué garantía exige?",
                       "icon": "cumple", "state": "Con fundamento", "by": "x", "url": "#"},
                      {"id": 1, "when": "01/10/2026 09:00", "question": "¿Y el plazo?",
                       "icon": "nodet", "state": "No determinado", "by": "x", "url": "#"}]
    tile = {t.key: t for t in s5_consulta.tiles(operator_user, after, ctx)}["consulta"]
    assert tile.big == "2" and tile.unit == "consultas"
    assert "garantía" in tile.sub


def test_normas_cargadas_cuenta_las_de_toda_la_base(after, two_regimes, operator_user):
    """REQ-126: «Normas cargadas» cuenta las normas del sistema, que son comunes a todos los
    procedimientos; con una sin validar lo dice."""
    tile = todos(operator_user, after)["cargadas"]
    assert tile.big == "2" and tile.unit == "normas"
    assert tile.chart is not None and tile.chart.has_data


def test_normas_cargadas_dice_cuantas_estan_sin_validar(after, make_norm, make_document,
                                                         make_reading, operator_user):
    """REQ-126: la norma sin validar figura en el mosaico y en su gráfico."""
    norm = make_norm(norm_type="decreto", number="1023", year=2001, issuer="poder ejecutivo nacional",
                     citation="Decreto 1023/2001")
    make_reading(make_document(norm), [("art-1", "ARTICULO 1.- Texto sintético.")], status="pending")
    tile = todos(operator_user, after)["cargadas"]
    assert tile.big == "1" and "1 sin validar" in tile.sub


# --- La sección ----------------------------------------------------------------------------------


def test_la_pestana_abre_con_el_tablero_y_las_anclas_de_la_014_viven_en_sus_detalles(
        client, operator_user, after, two_regimes):
    """REQ-126, REQ-127, REQ-129: cinco mosaicos, tres detalles con las anclas de la 014
    (`#s5-subir`, `#s5-lectura`, `#s5-consulta-respuesta`), y la subida sigue a mano."""
    html = abrir(client, operator_user, after)
    pagina = revisar(html)
    assert {t["id"] for t in pagina.tiles} == {f"m-{k}" for k in CLAVES}
    assert set(pagina.details) == {"d-s5-rigen", "d-s5-consulta", "d-s5-normas"}
    assert {"s5-subir", "s5-normas", "s5-lectura"} <= set(pagina.details["d-s5-normas"]["ids"])
    assert "s5-consulta" in pagina.details["d-s5-consulta"]["ids"]
    assert "s5-rigen" in pagina.details["d-s5-rigen"]["ids"]
    assert "Subir archivo" in html


def test_el_parcial_de_las_normas_que_rigen_conserva_su_tabla(client, operator_user, after,
                                                               two_regimes):
    """REQ-129: el detalle sigue con su tabla, sus estados y sus acciones."""
    pagina = Pagina(abrir(client, operator_user, after))
    texto = pagina.text_of("d-s5-rigen")
    assert "Normas que lo rigen y cuáles faltan" in texto and "Subir archivo" in texto


def test_los_parametros_de_la_consulta_abren_su_detalle(client, operator_user, after, two_regimes):
    """REQ-127: `?lectura=` abre las normas cargadas; `?consulta=` abre la consulta."""
    sin = Pagina(abrir(client, operator_user, after))
    assert "data-abre" not in sin.root
    lectura = Pagina(abrir(client, operator_user, after, "?lectura=999"))
    assert lectura.root["data-abre"] == "d-s5-normas"
    consulta = Pagina(abrir(client, operator_user, after, "?consulta=999"))
    assert consulta.root["data-abre"] == "d-s5-consulta"


def test_un_aviso_firmado_abre_el_detalle_del_tema_que_lo_dio(client, operator_user, after):
    """REQ-127: el aviso de una subida abre las normas; el de la consulta, la consulta."""
    aviso_normas = s5_normas.pack("Se subió un archivo.")
    aviso_consulta = s5_consulta.pack("Escriba una pregunta.", ok=False)
    assert Pagina(abrir(client, operator_user, after, f"?aviso={aviso_normas}")).root[
        "data-abre"] == "d-s5-normas"
    assert Pagina(abrir(client, operator_user, after, f"?aviso={aviso_consulta}")).root[
        "data-abre"] == "d-s5-consulta"


def test_el_orden_de_los_mosaicos_es_normas_citas_regimen_consulta_cargadas(procedure,
                                                                            operator_user):
    """REQ-126: el orden de la maqueta aprobada."""
    seccion = sections.sections_for(operator_user, procedure).get("normativas")
    claves = [t.key for t in seccion.tiles(operator_user, procedure, {
        t.KEY: t.context(operator_user, procedure, Pedido) for t in seccion.temas})]
    assert claves == ["rigen", "citas", "regimen", "consulta", "cargadas"]


def test_la_seccion_con_el_caso_chico_carga_en_dos_segundos(client, operator_user, after,
                                                            two_regimes):
    """Umbral de la feature: la sección se ve completa en 2 s o menos con el caso chico."""
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    url = reverse("expedientes:normativas", args=[after.pk])
    client.get(url)  # la primera carga calienta plantillas
    inicio = time.perf_counter()
    assert client.get(url).status_code == 200
    assert time.perf_counter() - inicio <= 2


# --- La página general ---------------------------------------------------------------------------


def test_la_pagina_general_usa_los_tokens_y_no_lleva_estilos_ni_scripts_en_linea(
        client, operator_user, two_regimes):
    """REQ-133: la página general no lleva `style=` ni scripts en línea, ni colores sueltos."""
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    html = client.get(reverse("expedientes:normativas_general")).content.decode()
    assert "style=" not in html and "<script>" not in html
    assert 'id="s5-subir"' in html and 'id="s5-normas"' in html and "Subir archivo" in html


def test_la_pagina_general_abre_con_los_mosaicos_de_la_normativa(client, operator_user, two_regimes):
    """REQ-126: sin procedimiento, la página muestra «Normas cargadas» (y su estado) arriba, con
    el mismo mosaico de la sección, y sigue sin las normas que rigen a un procedimiento."""
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    html = client.get(reverse("expedientes:normativas_general")).content.decode()
    assert 'id="m-cargadas"' in html
    assert 'id="m-rigen"' not in html and 'id="m-regimen"' not in html


def test_la_pagina_general_sin_normas_no_muestra_cifra(client, operator_user):
    """REQ-141: sin normas cargadas el mosaico dice «Falta cargar normas»."""
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    html = client.get(reverse("expedientes:normativas_general")).content.decode()
    mosaico = html.split('id="m-cargadas"')[1].split("</a>")[0]
    assert 'class="big' not in mosaico and 'class="missing"' in mosaico


def test_las_hojas_de_la_seccion_usan_solo_tokens_nuevos():
    """REQ-133: las hojas de Normativas no usan la paleta vieja (azul, beige, rojo) ni colores
    sueltos en hexadecimal."""
    css = ROOT / "evaluon" / "static" / "journey"
    for name in ("s5.css", "s5_consulta.css", "s5_normas.css"):
        text = (css / name).read_text(encoding="utf-8")
        assert not re.search(r"--ev-(azul|beige|rojo)", text), name
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", text), name
    html = (ROOT / "evaluon" / "templates" / "journey" / "normativas.html").read_text(
        encoding="utf-8")
    assert "style=" not in html and "<script" not in html
