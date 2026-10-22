"""El primer panel de la sección Procedimiento (REQ-128, REQ-129, REQ-132, REQ-135, REQ-138;
plan 017, «Primer panel» y «De dónde sale cada dato»; ADR-0077; T-321).

Caso chico y público: un procedimiento con tres ofertas inventadas. La revisión visual a 1440 x 900
la hace el Coordinador en el navegador; acá se prueba lo que el HTML y las hojas de estilo dicen.
"""

import re
import time

import pytest
from django.urls import reverse
from django.utils import timezone

from evaluon.journey import sections
from evaluon.journey.stages import base as stage_base
from tests.accounts.test_fotos import make_photo
from tests.accounts.test_session import TEST_PASSWORD
from evaluon.portal import models as pm
from tests.journey.test_economico import make, opening  # noqa: F401  (fixtures)
from tests.journey.test_tablero_secciones import revisar

pytestmark = pytest.mark.django_db

STATIC = __import__("pathlib").Path(__file__).resolve().parents[2] / "evaluon" / "static"
INGRESO_CSS = STATIC / "journey" / "ingreso.css"


def abrir(client, procedure, user, seccion="procedimiento", consulta=""):
    assert client.login(username=user.username, password=TEST_PASSWORD)
    respuesta = client.get(reverse(f"expedientes:{seccion}", args=[procedure.pk]) + consulta)
    assert respuesta.status_code == 200
    return respuesta.content.decode()


def heroe(html):
    """Solo el encabezado con la foto y los datos principales."""
    return html.split('id="ingreso"')[1].split("</section>")[0]


def ingreso(html):
    """Todo el primer panel: encabezado, ventana del proceso y pendiente general."""
    return html.split('id="ingreso"')[1].split('class="tablero"')[0]


def numero(html, clave):
    """El texto del dato principal `n-<clave>`, sin etiquetas."""
    trozo = html.split(f'id="n-{clave}"')[1].split(">", 1)[1].split("</div>")[0]
    return " ".join(re.sub(r"<[^>]+>", " ", trozo).split())


@pytest.fixture
def portal(procedure, operator_user):
    """El ítem del Portal del que cuelgan los datos y el cronograma, ya aprobado: así la sección 1
    no lo ofrece como propuesta pendiente (su vista de la propuesta pide el CUIT de una oferta)."""
    link = pm.PortalLink.objects.create(url="https://portal.invalid/proceso",
                                        procedure=procedure, created_by=operator_user)
    page = pm.PortalPage.objects.create(link=link, exploration=1, kind="cuadro",
                                        url="https://portal.invalid/cuadro",
                                        sha256="a" * 64, content=b"x")
    proposal = pm.PortalProposal.objects.create(link=link, exploration=1, origin="importacion")
    return pm.PortalItem.objects.create(proposal=proposal, kind="oferta", key="o", payload={},
                                        content_sha256="b" * 64, page=page,
                                        state=pm.ItemState.APROBADO, decided_by=operator_user,
                                        decided_at=timezone.now())


@pytest.fixture
def tres(make):  # noqa: F811
    return [make(n, None) for n in (1, 2, 3)]


# --- Datos principales (REQ-128) -----------------------------------------------------------------


def test_el_primer_panel_muestra_los_datos_principales_del_procedimiento(
        client, procedure, matrix, tres, opening, operator_user):  # noqa: F811
    """REQ-128: objeto, tipo y número, expediente y fecha de autorización, sobre la foto."""
    html = abrir(client, procedure, operator_user)
    texto = " ".join(re.sub(r"<[^>]+>", " ", heroe(html)).split())
    assert procedure.subject in texto
    assert procedure.procedure_type in texto and procedure.number in texto
    assert "EX-SINT-1" in texto
    assert f"{procedure.authorization_date:%d/%m/%Y}" in texto
    assert 'class="photo-bg"' in heroe(html)


def test_sin_expediente_cargado_dice_falta(client, procedure, matrix, operator_user):
    """REQ-128, REQ-141: si el expediente no se cargó, el dato dice «Falta», sin inventarlo."""
    texto = " ".join(re.sub(r"<[^>]+>", " ", heroe(abrir(client, procedure, operator_user))).split())
    assert re.search(r"Expediente\s*Falta", texto)


def test_cantidad_de_ofertas_pendientes_y_avance(client, procedure, matrix, tres, operator_user):
    """REQ-128: cantidad de ofertas, cantidad de pendientes y «N de 5 secciones listas» (ADR-0077)."""
    html = abrir(client, procedure, operator_user)
    resumen = sections.sections_for(operator_user, procedure)
    listas = sum(1 for s in resumen.sections if s.state == stage_base.LISTA)
    assert numero(html, "ofertas").startswith("3 ofertas")
    assert numero(html, "avance") == f"{listas} de 5 secciones listas"
    assert numero(html, "pendientes") == f"{resumen.pending} pendientes"
    assert re.search(r'class="hl"[^>]*>\s*%d\s*<' % resumen.pending, heroe(html))


def test_el_avance_no_usa_porcentajes(client, procedure, matrix, tres, operator_user):
    """ADR-0077 (avance A): sin porcentajes inventados, ni en el dato ni en el mosaico."""
    html = abrir(client, procedure, operator_user)
    assert "%" not in numero(html, "avance")
    mosaico = html.split('id="m-avance"')[1].split("</a>")[0]
    assert "%" not in mosaico
    assert "de 5" in mosaico


def test_el_mosaico_de_avance_abre_el_estado_de_las_cinco_secciones(
        client, procedure, matrix, tres, operator_user):
    """REQ-128: el detalle «Avance por sección» nombra las cinco secciones con su estado."""
    pagina = revisar(abrir(client, procedure, operator_user))
    assert "m-avance" in [t["id"] for t in pagina.tiles]
    texto = pagina.text_of("d-s1-avance")
    for nombre in ("Procedimiento", "Pliego y matriz", "Ofertas", "Evaluación", "Normativas"):
        assert nombre in texto


# --- Pendiente general (REQ-129) -----------------------------------------------------------------


def test_el_pendiente_general_junta_las_cinco_secciones(client, procedure, matrix, tres,
                                                        operator_user):
    """REQ-129: el pendiente general lleva el nombre de la sección de cada renglón y sus
    contadores coinciden con los del procedimiento."""
    html = abrir(client, procedure, operator_user)
    resumen = sections.sections_for(operator_user, procedure)
    panel = ingreso(html)
    assert 'id="pendientes"' in panel and 'id="sugerencias"' in panel
    assert re.search(r'Pendientes de decidir <span class="cta">%d<' % resumen.pending, panel)
    assert re.search(r'Sugerencias del sistema <span class="cta">%d<' % resumen.suggestions, panel)
    con_renglones = {s.label for s in resumen.sections
                     if s.pending_items or s.suggestion_items}
    for etiqueta in con_renglones:
        assert f'<span class="donde">{etiqueta}</span>' in panel


# --- Sin normativa y sin cifras inventadas (REQ-128, REQ-141) ------------------------------------


def test_el_encabezado_no_trae_datos_de_normativa(client, procedure, matrix, tres, opening,
                                                  operator_user):
    """REQ-128: el régimen, las normas y las citas se consultan en su sección, no acá."""
    texto = " ".join(re.sub(r"<[^>]+>", " ", heroe(abrir(client, procedure, operator_user))).split())
    for palabra in ("régimen", "Régimen", "Disposición", "Decreto", "norma", "Norma", "cita"):
        assert palabra not in texto, palabra


def test_el_tablero_del_primer_panel_no_tiene_mosaicos_de_normativa(
        client, procedure, matrix, tres, operator_user):
    """REQ-128 (D-3 del plan): ningún mosaico del primer panel es de la sección Normativas."""
    pagina = revisar(abrir(client, procedure, operator_user))
    for mosaico in pagina.tiles:
        assert "s5" not in (mosaico.get("data-detail") or "")
        assert "normativas" not in (mosaico.get("href") or "").lower().replace("#", "")


def test_los_mosaicos_de_la_evaluacion_enlazan_sin_repetir_el_detalle(
        client, procedure, matrix, tres, operator_user):
    """REQ-128 (D-4 del plan): resultado, descartes y preguntas llevan a `evaluacion/#d-s4-…`."""
    pagina = revisar(abrir(client, procedure, operator_user))
    destino = reverse("expedientes:evaluacion", args=[procedure.pk])
    enlaces = {t["id"]: t["href"] for t in pagina.tiles if t["id"] in
               ("m-resultado", "m-descartes", "m-preguntas")}
    assert set(enlaces) == {"m-resultado", "m-descartes", "m-preguntas"}
    for href in enlaces.values():
        assert href.startswith(destino + "#d-s4-")


def test_sin_evaluacion_los_mosaicos_de_la_evaluacion_dicen_pendiente(
        client, procedure, matrix, tres, operator_user):
    """REQ-141: sin evaluación no hay cifras: cada mosaico dice «Pendiente»."""
    html = abrir(client, procedure, operator_user)
    for clave in ("resultado", "descartes", "preguntas"):
        mosaico = html.split(f'id="m-{clave}"')[1].split("</a>")[0]
        assert 'class="missing"' in mosaico and "Pendiente" in mosaico
        assert 'class="big' not in mosaico and 'class="ch"' not in mosaico


# --- Foto (REQ-135, REQ-138) ---------------------------------------------------------------------


def test_sin_fotos_propias_se_ve_la_foto_de_la_casa(client, procedure, matrix, tres, operator_user):
    """REQ-135: la foto de la casa, dibujada como imagen decorativa, con su texto."""
    encabezado = heroe(abrir(client, procedure, operator_user))
    assert re.search(r'<div class="photo-bg"[^>]*>\s*<img [^>]*src="[^"]*biblioratos-bn[^"]*"',
                     encabezado)
    assert 'alt=""' in encabezado
    assert "Foto de la casa" in encabezado


def test_con_fotos_propias_se_ve_una_de_ellas_con_su_texto(client, procedure, matrix, tres,
                                                           operator_user):
    """REQ-138: la foto de su perfil sale de la ruta que sirve las fotos propias."""
    propias = [make_photo(operator_user, slot=n, content=b"x%d" % n) for n in range(3)]
    encabezado = heroe(abrir(client, procedure, operator_user))
    assert "Foto de su perfil" in encabezado
    assert any(f"/perfil/fotos/{p.pk}/" in encabezado for p in propias)


def test_pedidos_sucesivos_eligen_otra_foto_y_la_pagina_no_trae_script_que_la_cambie(
        client, procedure, matrix, tres, operator_user):
    """REQ-138: con 3 fotos la foto cambia al volver al primer panel; nunca la cambia un script."""
    propias = [make_photo(operator_user, slot=n, content=b"x%d" % n) for n in range(3)]
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    url = reverse("expedientes:procedimiento", args=[procedure.pk])
    elegidas = []
    for _ in range(6):
        html = client.get(url).content.decode()
        hallada = re.search(r"/perfil/fotos/(\d+)/", heroe(html))
        assert hallada
        elegidas.append(int(hallada.group(1)))
        assert not re.search(r"<script(?![^>]*\bsrc=)", html), "script en línea en la página"
    assert set(elegidas) <= {p.pk for p in propias}
    assert all(a != b for a, b in zip(elegidas, elegidas[1:])), elegidas
    assert len(set(elegidas)) >= 2


def test_la_foto_solo_esta_en_el_primer_panel(client, procedure, matrix, tres, operator_user):
    """REQ-135: en las otras cuatro secciones no hay foto."""
    for seccion in ("pliego", "ofertas", "evaluacion", "normativas"):
        html = abrir(client, procedure, operator_user, seccion)
        assert "photo-bg" not in html and "biblioratos" not in html, seccion


def test_el_primer_panel_no_trae_estilos_ni_scripts_en_linea(client, procedure, matrix, tres,
                                                             operator_user):
    """La política de contenido es `default-src 'self'`: nada de `style=` ni de scripts."""
    panel = ingreso(abrir(client, procedure, operator_user))
    assert "style=" not in panel and "<script" not in panel


def test_la_foto_ocupa_a_lo_sumo_el_60_por_ciento_del_ancho():
    """REQ-135: ningún ancho de la capa de la foto pasa del 60 %."""
    css = INGRESO_CSS.read_text(encoding="utf-8")
    capas = re.findall(r"\.photo-bg\s*\{[^}]*\}", css)
    assert capas
    anchos = [float(a) for capa in capas for a in re.findall(r"(?<![-\w])width:\s*([\d.]+)%", capa)]
    assert anchos and max(anchos) <= 60


def test_la_animacion_respeta_reducir_movimiento():
    """REQ-135: entrada de 0,9 s con fundido y leve escala; con «reducir movimiento», 0,3 s."""
    css = INGRESO_CSS.read_text(encoding="utf-8")
    assert re.search(r"animation:\s*[\w-]+\s+\.9s", css)
    reducido = css.split("prefers-reduced-motion")[1]
    assert re.search(r"\.3s", reducido)


def test_la_hoja_del_primer_panel_usa_solo_tokens():
    """REQ-133: sin colores en hexadecimal ni funciones de color fijas."""
    css = re.sub(r"/\*.*?\*/", "", INGRESO_CSS.read_text(encoding="utf-8"), flags=re.S)
    assert re.findall(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(", css) == []


def test_el_texto_sobre_la_foto_no_usa_opacidad():
    """REQ-135: el contraste se mide con colores planos: la opacidad solo está en la imagen."""
    css = re.sub(r"/\*.*?\*/", "", INGRESO_CSS.read_text(encoding="utf-8"), flags=re.S)
    for selector, cuerpo in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if "opacity" in cuerpo and selector.strip() not in ("from", "to"):
            assert "photo-bg" in selector, f"opacidad fuera de la foto: {selector.strip()}"


# --- Hay/Falta y tiempos -------------------------------------------------------------------------


def test_el_encabezado_deja_el_lugar_de_hay_falta():
    """REQ-132: el primer panel incluye la línea «Hay · Falta» (T-312)."""
    plantilla = (STATIC.parent / "templates" / "journey" / "_ingreso.html").read_text("utf-8")
    assert '{% include "journey/_hay_falta.html" %}' in plantilla


def test_el_primer_panel_se_arma_en_dos_segundos_con_el_caso_chico(
        client, procedure, matrix, tres, opening, operator_user):
    """El tablero del primer panel, en 2 s o menos con el caso chico."""
    assert client.login(username=operator_user.username, password=TEST_PASSWORD)
    url = reverse("expedientes:procedimiento", args=[procedure.pk])
    client.get(url)  # la primera carga abre conexiones y plantillas
    t0 = time.perf_counter()
    assert client.get(url).status_code == 200
    assert time.perf_counter() - t0 <= 2.0


def test_el_usuario_de_lectura_ve_el_primer_panel_sin_acciones(client, procedure, matrix, tres,
                                                               no_commission_user):
    """REQ-075: el panel se ve sin botones de decisión ni de subir."""
    html = abrir(client, procedure, no_commission_user)
    assert "photo-bg" in html
    assert "<form" not in ingreso(html).replace('class="preferencia"', "")


def test_el_primer_panel_trae_la_ventana_del_proceso(client, procedure, matrix, tres, offer,
                                                      simulate, operator_user):
    """REQ-140 (aviso de T-330): con un pedido en curso, el primer panel muestra la ventana del
    proceso (`id="process-window"`), debajo de los datos principales, y el sondeo la reemplaza."""
    from evaluon.tenders.models import JobStatus
    simulate([offer], JobStatus.RUNNING)
    html = abrir(client, procedure, operator_user)
    assert 'id="process-window"' in html
    assert 'data-poll-url="' + reverse("expedientes:ventana", args=[procedure.pk]) + '"' in html
    assert html.index('id="ingreso"') < html.index('id="process-window"') < html.index('id="pendientes"')
