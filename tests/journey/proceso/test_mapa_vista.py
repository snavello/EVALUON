"""El selector «Mapa / Lista» y la hoja del mapa (REQ-158; plan 018, «Selector» y «Pantallas
angostas»; T-350): `?vista=` sin estado guardado, la lista bajo 900 px, las posiciones de la hoja
iguales a las constantes de `mapa.py`. Material inventado (P4)."""

import re
from pathlib import Path

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from evaluon.journey.proceso import mapa
from tests.journey.proceso.test_portada import entrar, html_de, url_de

pytestmark = pytest.mark.django_db
CSS = Path(__file__).resolve().parents[3] / "evaluon" / "static" / "journey" / "mapa.css"


def css():
    return re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.S)


def test_req158_vista_lista_no_trae_mapa_ni_cookies_ni_escrituras(client, caso_varios_en_curso):
    """REQ-158: `?vista=lista` no dibuja ni el `<svg>` ni las tarjetas, sí el selector y los plazos;
    no pone cookies y no escribe en la base."""
    entrar(client, caso_varios_en_curso.user)
    with CaptureQueriesContext(connection) as q:
        r = client.get(url_de(caso_varios_en_curso) + "?vista=lista")
    html = r.content.decode()
    assert r.status_code == 200
    assert '<svg class="mp-hilos"' not in html and "mp-nodo" not in html and "data-tarjeta" not in html
    assert 'aria-current="page">Lista</a>' in html and 'class="mp-plazos"' in html
    assert html.count('data-pieza="paso"') == 7
    assert set(r.cookies) <= {"csrftoken"}  # solo el de los formularios de siempre; la vista no se guarda
    # La única escritura es la del aviso «terminó la lectura» del marco de todas las pantallas
    # (`tenders_job.seen_at`); la vista del mapa no guarda nada.
    assert not [c["sql"] for c in q.captured_queries
                if re.match(r"\s*(INSERT|UPDATE|DELETE)", c["sql"], re.I) and "tenders_job" not in c["sql"]]


def test_req158_vista_mapa_por_omision_y_valor_raro_es_mapa(client, caso_varios_en_curso):
    """REQ-158: sin parámetro, o con un valor desconocido, se dibuja el mapa; no se recuerda la elección."""
    base = html_de(client, caso_varios_en_curso)
    assert 'aria-current="page">Mapa</a>' in base
    r = client.get(url_de(caso_varios_en_curso) + "?vista=x")
    assert 'aria-current="page">Mapa</a>' in r.content.decode()
    client.get(url_de(caso_varios_en_curso) + "?vista=lista")
    otra = client.get(url_de(caso_varios_en_curso))
    assert 'aria-current="page">Mapa</a>' in otra.content.decode() and set(otra.cookies) <= {"csrftoken"}


def test_req158_los_enlaces_del_selector(client, caso_varios_en_curso):
    """REQ-158: «Lista» conserva la dirección con `#pasos`; el destino existe."""
    html = html_de(client, caso_varios_en_curso)
    url = url_de(caso_varios_en_curso)
    assert f'href="{url}?vista=lista#pasos"' in html and f'href="{url}?vista=mapa"' in html
    assert 'id="pasos"' in html


def test_req158_mapa_css_tiene_la_regla_de_900_px_que_oculta_mapa_y_selector():
    """REQ-158: bajo 900 px se oculta el encabezado con el selector y la leyenda (y no se dibuja el
    lienzo: lo oculta su contenedor); la lista queda."""
    texto = css()
    media = re.search(r"@media \(max-width: 899px\)\s*\{(.*)\}\s*$", texto, re.S)
    assert media, "falta @media (max-width: 899px)"
    assert re.search(r"\.mp-cab\s*\{\s*display:\s*none", media.group(1))
    assert re.search(r"\.mp-lienzo-w\s*\{\s*display:\s*none", media.group(1))


def test_req158_mapa_css_declara_las_mismas_posiciones_que_mapa_py():
    """REQ-158: `pos-N`, `col-N`, lienzo y tarjeta de la hoja = las constantes de `mapa.py`."""
    texto = css()
    pos = {int(n): (int(x), int(y)) for n, x, y in re.findall(
        r"\.pos-(\d)\s*\{\s*left:\s*(\d+)px;\s*top:\s*(\d+)px;?\s*\}", texto)}
    assert pos == mapa.POSICIONES
    col = [int(x) for x in re.findall(r"\.col-\d\s*\{\s*left:\s*(\d+)px", texto)]
    assert col == [x for _, x in mapa.COLUMNAS]
    lienzo = re.search(r"\.mp-lienzo\s*\{[^}]*width:\s*(\d+)px;\s*height:\s*(\d+)px", texto)
    assert (int(lienzo.group(1)), int(lienzo.group(2))) == mapa.LIENZO
    nodo = re.search(r"\.mp-nodo\s*\{[^}]*width:\s*(\d+)px;\s*height:\s*(\d+)px", texto)
    assert (int(nodo.group(1)), int(nodo.group(2))) == (mapa.ANCHO, mapa.ALTO)


def test_req158_mapa_css_recorta_las_tareas_y_declara_las_clases_de_los_hitos():
    """REQ-158: tareas de una línea con puntos suspensivos; `x-0` … `x-100` para los hitos; sin colores
    fijos; ningún texto bajo 12 px."""
    texto = css()
    assert re.search(r"\.mp-txt\s*\{[^}]*overflow:\s*hidden;\s*text-overflow:\s*ellipsis;"
                     r"\s*white-space:\s*nowrap", texto)
    assert [int(n) for n in re.findall(r"\.mp-hito\.x-(\d+)\s*\{", texto)] == list(range(101))
    assert re.findall(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(", texto) == []
    assert not re.search(r"font-size:\s*(?:[0-9]|1[01])(?:\.\d+)?px", texto)


def test_req156_el_foco_se_ve_en_tarjetas_y_tareas():
    """REQ-156: foco de 3 px `--focus` en los enlaces del mapa y en la tarjeta que lo contiene."""
    texto = css()
    assert ".mp a:focus-visible" in texto and ".mp-nodo:focus-within" in texto
    assert "outline: 3px solid var(--focus)" in texto


def test_req156_el_orden_de_tabulacion_es_el_de_lectura(client, caso_varios_en_curso):
    """REQ-156: las tarjetas vienen en el orden 1 a 7 (nombre y luego tareas) y nada tiene `tabindex`."""
    html = html_de(client, caso_varios_en_curso)
    mp = html[html.index('<ol class="mp-nodos"'):]
    mp = mp[:mp.index("</ol>")]
    assert [int(n) for n in re.findall(r'data-tarjeta="(\d)"', mp)] == [1, 2, 3, 4, 5, 6, 7]
    assert "tabindex" not in mp


def test_req158_el_mapa_cuenta_como_una_pieza(client, caso_varios_en_curso):
    """REQ-158: el mapa es UNA pieza: ni tarjetas ni tareas ni hitos llevan `data-pieza`."""
    html = html_de(client, caso_varios_en_curso)
    mp = html[html.index('class="mp mp-mapa"'):html.index('data-pieza="acciones"')]
    assert re.findall(r'data-pieza="([^"]+)"', mp) == ["mapa"]
