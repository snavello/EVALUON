"""El primer panel: orden económico, plazos y vencimiento del mantenimiento (REQ-128, REQ-130,
REQ-131, REQ-141; plan 017, «Datos que faltan hoy»; ADR-0077, vencimiento A; T-322).

Caso chico y público: tres ofertas inventadas con su total del Portal, el cronograma con la apertura
el 22/09/2026 y la página del proceso del caso público `portal-chico` (60 días corridos). «Hoy» se
fija en el 21/10/2026 para que las cuentas sean las de la spec.
"""

import hashlib
import re
import time
from datetime import date, datetime, timezone as tz
from decimal import Decimal
from pathlib import Path

import pytest
from django.urls import reverse

from evaluon.journey.tablero import economico, ingreso
from evaluon.portal import models as pm
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.test_economico import make, opening  # noqa: F401  (fixtures)
from tests.journey.test_primer_panel import portal, tres  # noqa: F401  (fixtures)
from tests.journey.test_tablero_secciones import revisar

pytestmark = pytest.mark.django_db

PROCESO = Path(__file__).resolve().parents[1] / "portal" / "data" / "portal-chico" / "proceso.html"
HOY = date(2026, 10, 21)
TOMADA = datetime(2026, 10, 20, 15, 30, tzinfo=tz.utc)


@pytest.fixture(autouse=True)
def hoy(monkeypatch):
    """Hoy es el 21/10/2026 (el ejemplo de REQ-131)."""
    monkeypatch.setattr(ingreso, "today", lambda: HOY)


@pytest.fixture
def pagina(portal):  # noqa: F811
    """`pagina(plazo=None)`: la página del proceso guardada, con el plazo de mantenimiento pedido
    (por omisión, el del caso: «60 Días corridos Acto de apertura»)."""
    def guardar(plazo=None, tomada=TOMADA):
        contenido = PROCESO.read_bytes()
        if plazo is not None:
            nuevo = contenido.replace(b"60 D\xc3\xadas corridos Acto de apertura", plazo.encode())
            assert nuevo != contenido, "el plazo del caso no está en el HTML"
            contenido = nuevo
        return pm.PortalPage.objects.create(
            link=portal.proposal.link, exploration=2, kind="proceso", url="https://portal.invalid/p",
            sha256=hashlib.sha256(contenido).hexdigest(), content=contenido, fetched_at=tomada)
    return guardar


def abrir(client, procedure, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)
    respuesta = client.get(reverse("expedientes:procedimiento", args=[procedure.pk]))
    assert respuesta.status_code == 200
    return respuesta.content.decode()


def texto(html):
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def numero(html, clave):
    trozo = html.split(f'id="n-{clave}"')[1].split(">", 1)[1].split("</div>")[0]
    return texto(trozo)


def mosaico(html, clave):
    return html.split(f'id="m-{clave}"')[1].split("</a>")[0]


# --- El plazo de mantenimiento, tal como lo escribe el Portal -------------------------------------


@pytest.mark.parametrize("escrito,dias,tipo,desde_apertura", [
    ("60 Días corridos Acto de apertura", 60, "corridos", True),
    ("30 Días hábiles Acto de apertura", 30, "hábiles", True),
    ("1 Día corrido Acto de apertura", 1, "corridos", True),
    ("45 Días corridos Notificación de la adjudicación", 45, "corridos", False),
])
def test_el_plazo_se_lee_con_sus_dias_su_tipo_y_su_origen(escrito, dias, tipo, desde_apertura):
    """REQ-131: «N Días corridos|hábiles <desde cuándo>» se separa en sus partes."""
    plazo = ingreso.parse_term(escrito)
    assert (plazo.days, plazo.kind, plazo.from_opening) == (dias, tipo, desde_apertura)


@pytest.mark.parametrize("escrito", ["", "A convenir", "Sesenta días", "Días corridos"])
def test_un_plazo_que_no_se_entiende_no_se_inventa(escrito):
    """REQ-141: lo que no tiene días ni tipo no da un plazo."""
    assert ingreso.parse_term(escrito) is None


# --- Vencimiento (REQ-131) ------------------------------------------------------------------------


def test_apertura_22_09_y_60_dias_corridos_vence_el_21_11_y_faltan_31(
        client, procedure, matrix, tres, opening, pagina, operator_user):  # noqa: F811
    """REQ-131: apertura del 22/09/2026, 60 días corridos, hoy 21/10/2026."""
    pagina()
    vence = ingreso.maintenance(procedure)
    assert vence.due == date(2026, 11, 21) and vence.days_left == 31
    html = abrir(client, procedure, operator_user)
    assert "21/11 · vence el mantenimiento de las ofertas" in texto(html)
    assert "faltan 31 días" in texto(html)
    assert numero(html, "vence") == "31 días vence el mantenimiento (21/11)"


def test_el_vencimiento_dice_de_donde_sale(client, procedure, matrix, tres, opening, pagina,
                                           operator_user):  # noqa: F811
    """ADR-0077: «Fuente: Portal, tomado el …» con el día en que se bajó la página."""
    pagina()
    assert "Fuente: Portal, tomado el 20/10/2026" in texto(abrir(client, procedure, operator_user))


def test_en_dias_habiles_no_se_calcula_y_dice_que_falta_el_calendario(
        client, procedure, matrix, tres, opening, pagina, operator_user):  # noqa: F811
    """REQ-131 (ADR-0077): sin calendario de feriados, «30 días hábiles desde la apertura»."""
    pagina("30 Días hábiles Acto de apertura")
    vence = ingreso.maintenance(procedure)
    assert vence.due is None and vence.days_left is None
    panel = texto(abrir(client, procedure, operator_user))
    assert "30 días hábiles desde la apertura" in panel and "Falta el calendario" in panel
    assert "faltan" not in panel


def test_si_cuenta_desde_otro_hecho_tampoco_se_calcula(client, procedure, matrix, tres, opening,
                                                       pagina, operator_user):  # noqa: F811
    """ADR-0077: con otro hecho de origen se muestra el plazo y «Falta el calendario»."""
    pagina("45 Días corridos Notificación de la adjudicación")
    vence = ingreso.maintenance(procedure)
    assert vence.due is None
    panel = texto(abrir(client, procedure, operator_user))
    assert "45 días corridos" in panel and "Falta el calendario" in panel


def test_sin_pagina_guardada_el_vencimiento_dice_falta(client, procedure, matrix, tres, opening,
                                                       operator_user):
    """REQ-141: sin la página del Portal no hay plazo: «Falta», sin fecha ni cifra."""
    vence = ingreso.maintenance(procedure)
    assert vence.due is None and vence.state == "missing"
    html = abrir(client, procedure, operator_user)
    assert numero(html, "vence").startswith("Falta")
    assert "faltan" not in texto(html) and "Fuente: Portal" not in texto(html)


def test_sin_cronograma_no_hay_vencimiento_y_dice_falta(client, procedure, matrix, tres, pagina,
                                                        operator_user):  # noqa: F811
    """REQ-131, REQ-141: con el plazo pero sin la apertura en el cronograma, «Falta»."""
    pagina()
    vence = ingreso.maintenance(procedure)
    assert vence.due is None
    html = abrir(client, procedure, operator_user)
    assert numero(html, "vence").startswith("Falta")
    assert "faltan" not in texto(html)


def test_un_vencimiento_pasado_dice_que_vencio(client, procedure, matrix, tres, opening, pagina,
                                               operator_user, monkeypatch):  # noqa: F811
    """El 25/11/2026 el mantenimiento (21/11) ya venció hace 4 días: no dice «faltan»."""
    pagina()
    monkeypatch.setattr(ingreso, "today", lambda: date(2026, 11, 25))
    vence = ingreso.maintenance(procedure)
    assert vence.days_left == -4
    panel = texto(abrir(client, procedure, operator_user))
    assert "venció hace 4 días" in panel and "faltan" not in panel


# --- Los plazos importantes (REQ-131) -------------------------------------------------------------


def test_los_plazos_van_en_orden_con_lo_que_paso_lo_de_hoy_y_lo_que_viene(
        procedure, tres, opening, pagina):  # noqa: F811
    """REQ-131: apertura (ya pasó), hoy, vencimiento (viene) y dictamen (pendiente)."""
    pagina()
    plazos = ingreso.plazos(procedure)
    assert [(p.key, p.state) for p in plazos.events] == [
        ("apertura", "past"), ("hoy", "now"), ("vence", "future"), ("dictamen", "pending")]
    assert [p.date_text for p in plazos.events] == ["22/09", "21/10", "21/11", "Pendiente"]
    assert [e.state for e in plazos.chart.events] == ["past", "now", "future", "pending"]


def test_sin_dictamen_el_plazo_del_dictamen_dice_pendiente(client, procedure, matrix, tres,
                                                           opening, pagina, operator_user):  # noqa: F811
    """REQ-141: sin dictamen, «Pendiente» y ninguna fecha inventada."""
    pagina()
    pagina_html = abrir(client, procedure, operator_user)
    detalle = texto(pagina_html.split('id="d-s1-plazos"')[1].split("</article>")[0])
    assert re.search(r"Pendiente\s*·\s*dictamen de la Comisión", detalle)


def test_con_un_dictamen_del_portal_se_muestra_su_fecha(client, procedure, matrix, tres, opening,
                                                        pagina, portal, operator_user):  # noqa: F811
    """REQ-131: la fecha del dictamen publicado por el Portal (15/10/2026) ya pasó."""
    pagina()
    pm.PortalItem.objects.create(
        proposal=portal.proposal, kind="documento", key="dictamen",
        payload={"clase": "dictamen", "fecha": "2026-10-15"}, content_sha256="c" * 64,
        page=portal.page)
    dictamen = next(p for p in ingreso.plazos(procedure).events if p.key == "dictamen")
    assert (dictamen.date_text, dictamen.state) == ("15/10", "past")


def test_sin_cronograma_la_apertura_dice_falta(procedure, tres):
    """REQ-141: sin apertura en el cronograma, el hito dice «Falta» y no tiene fecha."""
    apertura = next(p for p in ingreso.plazos(procedure).events if p.key == "apertura")
    assert apertura.date_text == "Falta" and apertura.state == "pending"


def test_el_mosaico_de_plazos_cuenta_los_dias_hasta_el_vencimiento(
        client, procedure, matrix, tres, opening, pagina, operator_user):  # noqa: F811
    """REQ-131: la cifra grande es la de los días que faltan, con su gráfico."""
    pagina()
    html = abrir(client, procedure, operator_user)
    plazos = mosaico(html, "plazos")
    assert 'class="big' in plazos and "31" in texto(plazos) and 'class="ch"' in plazos
    revisar(html)  # el detalle que abre el mosaico existe
    assert "d-s1-plazos" in html


def test_el_mosaico_de_plazos_con_el_mantenimiento_vencido_dice_vencio(
        client, procedure, matrix, tres, opening, pagina, operator_user,  # noqa: F811
        monkeypatch):
    """REQ-131 (T-336): el 25/11/2026 el vencimiento (21/11) pasó hace 4 días: la cifra grande es
    «Venció», sin «días» ni «faltan», y el apoyo dice hace cuánto y cuándo fue."""
    pagina()
    monkeypatch.setattr(ingreso, "today", lambda: date(2026, 11, 25))
    plazos = texto(mosaico(abrir(client, procedure, operator_user), "plazos"))
    assert "Venció" in plazos and "hace 4 días · el 21/11" in plazos
    assert "faltan" not in plazos and "4 días vence" not in plazos


def test_el_mosaico_de_plazos_sin_vencer_sigue_con_los_dias_que_faltan(
        client, procedure, matrix, tres, opening, pagina, operator_user):  # noqa: F811
    """REQ-131 (T-336): antes del vencimiento, «31 días» y la fecha con «vence …»."""
    pagina()
    plazos = texto(mosaico(abrir(client, procedure, operator_user), "plazos"))
    assert "31" in plazos and "días" in plazos and "21/11 · vence el mantenimiento" in plazos
    assert "Venció" not in plazos


def test_sin_cronograma_el_mosaico_de_plazos_dice_falta(client, procedure, matrix, tres,
                                                        operator_user):
    """REQ-141: sin apertura ni vencimiento no hay cifra: «Falta»."""
    plazos = mosaico(abrir(client, procedure, operator_user), "plazos")
    assert 'class="missing"' in plazos and "Falta" in plazos and 'class="big' not in plazos


# --- Orden económico (REQ-130) --------------------------------------------------------------------


@pytest.fixture
def con_totales(make):  # noqa: F811
    """Tres ofertas con total: la 2 es la más baja y la 3 la más alta."""
    return [make(1, Decimal("1100.00")), make(2, Decimal("1000.00")), make(3, Decimal("1250.00"))]


def test_con_tres_ofertas_se_ve_la_mas_baja_la_mas_alta_y_el_orden(
        client, procedure, matrix, con_totales, opening, operator_user):
    """REQ-130: de menor a mayor, con la más baja y la más alta como indicadores y la diferencia."""
    html = abrir(client, procedure, operator_user)
    assert numero(html, "baja") == "$ 1.000,00 la más baja: Oferta 2"
    assert numero(html, "alta") == "$ 1.250,00 la más alta: Oferta 3"
    orden = mosaico(html, "orden")
    assert 'class="big' in orden and 'class="ch"' in orden and "25,0 %" in texto(orden)
    detalle = texto(html.split('id="d-s1-orden"')[1].split("</article>")[0])
    assert detalle.index("Oferta 2") < detalle.index("Oferta 1") < detalle.index("Oferta 3")
    assert "+10,0 %" in detalle and "+25,0 %" in detalle


def test_sin_ofertas_el_orden_muestra_el_dia_de_la_apertura_y_pendiente(
        client, procedure, matrix, opening, operator_user):
    """REQ-130, REQ-141: sin ofertas, el día de la apertura y «Pendiente», sin cifras."""
    html = abrir(client, procedure, operator_user)
    orden = mosaico(html, "orden")
    assert 'class="missing"' in orden and "Pendiente" in orden
    assert "22/09/2026" in texto(orden)
    assert 'class="big' not in orden and 'class="ch"' not in orden
    assert "n-baja" not in html and "n-alta" not in html
    assert "22/09" in numero(html, "apertura") and "Pendiente" in numero(html, "apertura")


def test_sin_ofertas_ni_cronograma_el_orden_dice_pendiente_y_falta_la_apertura(
        client, procedure, matrix, operator_user):
    """REQ-141: sin ofertas y sin apertura no hay ninguna fecha."""
    html = abrir(client, procedure, operator_user)
    assert 'class="missing"' in mosaico(html, "orden")
    assert numero(html, "apertura").startswith("Falta")


def test_con_una_sola_oferta_la_mas_alta_dice_que_falta(client, procedure, matrix, make,  # noqa: F811
                                                         opening, operator_user):
    """REQ-130, REQ-141: con un solo total no hay oferta más alta: lo dice, no la inventa."""
    make(1, Decimal("1000.00"))
    html = abrir(client, procedure, operator_user)
    assert numero(html, "baja").startswith("$ 1.000,00")
    assert "Falta otra oferta" in numero(html, "alta")


def test_ofertas_sin_total_no_dan_cifras(client, procedure, matrix, tres, opening, operator_user):
    """REQ-141: tres ofertas sin total del Portal: la cantidad y «Falta el total», sin importes."""
    html = abrir(client, procedure, operator_user)
    assert numero(html, "ofertas").startswith("3 ofertas")
    assert "Falta el total" in numero(html, "baja") and "Falta el total" in numero(html, "alta")
    assert 'class="big' not in mosaico(html, "orden")


def test_el_orden_se_calcula_una_sola_vez_por_pedido(client, procedure, matrix, con_totales,
                                                    opening, operator_user, monkeypatch):
    """Aviso de T-314: los indicadores y el mosaico comparten una sola `economic_view`."""
    llamadas = []
    original = economico.economic_view
    monkeypatch.setattr(economico, "economic_view",
                        lambda *a, **k: llamadas.append(1) or original(*a, **k))
    abrir(client, procedure, operator_user)
    assert len(llamadas) == 1


# --- Tiempos --------------------------------------------------------------------------------------


def test_leer_el_plazo_de_la_pagina_guardada_es_rapido(procedure, opening, pagina, capsys):  # noqa: F811
    """ADR-0077: si la lectura pasa de unos 150 ms se decide guardar el dato (alternativa B). Acá
    se mide y se informa; falla solo si pasa de un segundo."""
    pagina()
    t0 = time.perf_counter()
    vence = ingreso.maintenance(procedure)
    milisegundos = (time.perf_counter() - t0) * 1000
    with capsys.disabled():
        print(f"\n[T-322] lectura de mantenimiento_oferta: {milisegundos:.0f} ms")
    assert vence.due == date(2026, 11, 21)
    assert milisegundos < 1000


def test_el_primer_panel_completo_se_arma_en_dos_segundos(
        client, procedure, matrix, con_totales, opening, pagina, operator_user):  # noqa: F811
    """El tablero del primer panel en 2 s o menos con el caso chico, incluida la lectura del plazo."""
    pagina()
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    url = reverse("expedientes:procedimiento", args=[procedure.pk])
    client.get(url)
    t0 = time.perf_counter()
    assert client.get(url).status_code == 200
    assert time.perf_counter() - t0 <= 2.0
