"""El panel de la celda en el cuadro de cumplimiento (REQ-154; T-352): pliego y oferta lado a lado
con su ubicación y el motivo, los mismos formularios que la página del par con `desde=cuadro`, la
misma decisión registrada y el regreso al cuadro. Material inventado (P4)."""

import re

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from evaluon.accounts.models import CommissionRole, Role
from evaluon.assessment import models as am
from evaluon.journey.temas import s4_propuesta_acciones as acciones
from tests.accounts.test_session import TEST_PASSWORD
from tests.journey.proceso.test_cuadro import entrar, sintetico, texto_de, url_de
from tests.assessment.test_matrix import requirement

pytestmark = pytest.mark.django_db


def celda(caso, oferta, needle):
    """`(oferta, requisito)` del caso en curso: la oferta por posición y el requisito por su cita."""
    return caso.offers[oferta], requirement(caso.procedure, needle)


def abrir(client, caso, oferta, needle, extra=""):
    offer, req = celda(caso, oferta, needle)
    response = client.get(url_de(caso.procedure, f"?celda={offer.pk}-{req.pk}{extra}"))
    return response, response.content.decode(), offer, req


def decision_url(procedure, offer, req):
    result = am.Result.objects.filter(offer=offer, requirement=req).get()
    return reverse("expedientes:s4_decidir", args=[procedure.pk, result.pk])


def test_la_celda_abierta_trae_pliego_oferta_ubicaciones_y_motivo(client, caso_varios_en_curso):
    """REQ-154: el panel dibuja a la derecha el texto del pliego con su ubicación, el de la oferta
    con documento y página, y el motivo de lo que propone el sistema; la celda queda marcada."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    response, html, offer, req = abrir(client, caso, 0, "garantía de mantenimiento")
    assert response.status_code == 200
    panel = html[html.index('id="cu-panel"'):]
    assert "Lo que exige el pliego" in panel and "Punto del pliego" in panel
    assert "garantía de mantenimiento de la oferta" in panel
    assert re.search(r'class="punto-donde">[^<]+', panel)  # la ubicación en el pliego
    assert "Lo que presentó la oferta" in panel and "oferta.pdf · página 1" in panel
    assert "Explicación del sistema" in panel and "Lo dice el texto." in panel
    assert re.search(rf'id="c-{offer.pk}-{req.pk}"[^>]*aria-current="true"', html)
    assert len(re.findall(r'<a class="cu-cel [^"]* sel"', html)) == 1  # solo una celda marcada
    # La duda de otra celda: el motivo se dice en la primera línea del panel.
    _, duda, offer, req = abrir(client, caso, 0, "declaración jurada")
    assert "(duda)" in duda[duda.index('id="cu-panel"'):]


def test_el_panel_lleva_desde_cuadro_y_el_filtro_en_los_tres_formularios(client, caso_varios_en_curso):
    """REQ-154: confirmar, corregir y rechazar envían `desde=cuadro` y el filtro vigente; un filtro
    desconocido se ignora."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    _, html, _, _ = abrir(client, caso, 1, "declaración jurada", "&filtro=a-decidir")
    assert html.count('name="desde" value="cuadro"') == 3
    assert html.count('name="filtro" value="a-decidir"') == 3
    assert html.count("← Volver a Evaluación") == 1  # el del cuadro; el panel no trae el suyo
    assert 'celda=' in html and "&amp;filtro=a-decidir#c-" in html  # las celdas conservan el filtro
    _, otro, _, _ = abrir(client, caso, 1, "declaración jurada", "&filtro=inventado")
    assert 'name="filtro"' not in otro


def test_decidir_desde_el_cuadro_deja_el_hecho_de_siempre_y_la_celda_cambia(
        client, caso_varios_en_curso):
    """REQ-154: confirmar desde el cuadro deja el mismo hecho que desde la página del par, vuelve
    al cuadro con la celda y el aviso, y la celda pasa de «sin confirmar» a confirmada."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    a, req_a = celda(caso, 0, "garantía de mantenimiento")
    b, req_b = celda(caso, 1, "sesenta días")
    antes = client.get(url_de(caso.procedure)).content.decode()
    assert texto_de(antes, a.pk, req_a.pk) == "Cumple sin confirmar"
    cuadro = client.post(decision_url(caso.procedure, a, req_a),
                         {"action": "confirmar", "desde": "cuadro", "filtro": "a-decidir"})
    par = client.post(decision_url(caso.procedure, b, req_b),
                      {"action": "confirmar", "desde": "par"})
    base = acciones.cuadro_url(caso.procedure, a.pk, req_a.pk, "a-decidir")
    assert cuadro["Location"].startswith(base + "&aviso=") and cuadro["Location"].endswith("#s4-aviso")
    assert par["Location"].startswith(acciones.pair_url(caso.procedure, b.pk, req_b.pk))
    hechos = []
    for offer, req in ((a, req_a), (b, req_b)):
        decision = am.Decision.objects.get(result__offer=offer, result__requirement=req)
        event = decision.event
        detail = {k: v for k, v in event.detail.items() if k not in ("result", "offer", "requirement")}
        hechos.append((decision.action, decision.user_id, decision.note, decision.outcome_after,
                       event.event_type, event.outcome, event.channel, detail))
    assert hechos[0] == hechos[1]
    assert am.Decision.objects.get(result__offer=a, result__requirement=req_a).user_id == caso.user.pk
    vuelta = client.get(cuadro["Location"])
    html = vuelta.content.decode()
    assert vuelta.status_code == 200 and 'id="s4-aviso"' in html and 'role="status"' in html
    assert 'id="cu-panel"' in html
    assert texto_de(html, a.pk, req_a.pk) == "Cumple"


def test_decidir_sin_rol_de_evaluador_se_rechaza_igual(client, caso_varios_en_curso, operator_user):
    """REQ-154, P6: el operador que envía la decisión recibe el mismo rechazo y no cambia nada."""
    caso = caso_varios_en_curso
    a, req_a = celda(caso, 0, "garantía de mantenimiento")
    entrar(client, operator_user)
    response = client.post(decision_url(caso.procedure, a, req_a),
                           {"action": "confirmar", "desde": "cuadro"})
    assert response.status_code == 403
    assert not am.Decision.objects.filter(result__offer=a, result__requirement=req_a).exists()


@pytest.fixture
def lector(db):
    """Usuario de lectura: sin rol de la Comisión (solo consulta)."""
    return get_user_model().objects.create_user(
        username="lector-cuadro", password=TEST_PASSWORD, role=Role.READ,
        commission_role=CommissionRole.NONE)


@pytest.mark.parametrize("quien", ["operator_user", "lector"])
def test_operador_y_lectura_ven_el_panel_sin_botones(client, caso_varios_en_curso, request, quien):
    """REQ-154: el panel se dibuja completo para quien no decide, sin ningún formulario de acción."""
    caso = caso_varios_en_curso
    entrar(client, request.getfixturevalue(quien))
    response, html, _, _ = abrir(client, caso, 1, "declaración jurada")
    assert response.status_code == 200
    panel = html[html.index('id="cu-panel"'):]
    assert "Lo que exige el pliego" in panel and "Historial del par" in panel
    assert "/decidir/" not in panel and 'name="desde"' not in panel
    if quien == "operator_user":
        assert "lo decide un evaluador" in panel


def test_una_fila_tecnica_dice_que_se_decide_con_el_informe(client, caso_varios_en_curso):
    """REQ-154: una celda técnica «Espera informe» abre su panel sin botones y lo dice."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    tecnico = caso.procedure.matrix_versions.get(number=1).requirements.get(
        category="tecnico", items=[1])
    html = client.get(url_de(caso.procedure, f"?celda={caso.offers[0].pk}-{tecnico.pk}")
                      ).content.decode()
    assert "Esta fila se decide con el ok del informe técnico del área." in html
    assert "/decidir/" not in html


@pytest.mark.parametrize("celda_mala", ["abc", "1-2-3", "-5", "1-", "1_2", "1-2 ", " 1-2", "０-1"])
def test_una_celda_mal_escrita_da_404(client, caso_varios_en_curso, celda_mala):
    """Una `celda` que no son dos números separados por un guion da 404."""
    entrar(client, caso_varios_en_curso.user)
    response = client.get(url_de(caso_varios_en_curso.procedure, f"?celda={celda_mala}"))
    assert response.status_code == 404


@pytest.mark.parametrize("sufijo", ["%0A", "x", "%20", "-1", "%0D%0A"])
def test_una_celda_valida_con_un_sufijo_da_404(client, caso_varios_en_curso, sufijo):
    """Una celda de verdad (oferta y requisito del procedimiento) seguida de un salto de línea u
    otro sufijo no es una celda: 404 (no se acepta con `$`)."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    offer, req = celda(caso, 0, "garantía de mantenimiento")
    ok = client.get(url_de(caso.procedure, f"?celda={offer.pk}-{req.pk}"))
    assert ok.status_code == 200 and 'id="cu-panel"' in ok.content.decode()
    mala = client.get(url_de(caso.procedure, f"?celda={offer.pk}-{req.pk}{sufijo}"))
    assert mala.status_code == 404


def test_los_enlaces_de_las_celdas_no_arrastran_un_filtro_desconocido(client, caso_varios_en_curso):
    """REQ-154: un `?filtro=` inventado no llega a ningún enlace de celda ni al panel; uno conocido
    sí, en todos."""
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    offer, req = celda(caso, 0, "garantía de mantenimiento")
    base = f"?celda={offer.pk}-{req.pk}"
    mala = client.get(url_de(caso.procedure, base + "&filtro=inventado")).content.decode()
    enlaces = re.findall(r'<a class="cu-cel [^"]*"[^>]*href="([^"]+)"', mala)
    assert len(enlaces) == 18 and not any("filtro" in e for e in enlaces)
    buena = client.get(url_de(caso.procedure, base + "&filtro=no-cumple")).content.decode()
    enlaces = re.findall(r'<a class="cu-cel [^"]*"[^>]*href="([^"]+)"', buena)
    assert len(enlaces) == 18 and all("&amp;filtro=no-cumple#c-" in e for e in enlaces)


def test_el_lector_no_recibe_el_enlace_al_archivo_original(client, caso_varios_en_curso, lector,
                                                            evaluator_user):
    """Quien no tiene rol de la Comisión no puede abrir el original (403): el panel dice el
    documento y la página sin enlace; el evaluador sí lo tiene."""
    caso = caso_varios_en_curso
    offer, req = celda(caso, 0, "garantía de mantenimiento")
    query = f"?celda={offer.pk}-{req.pk}"
    entrar(client, evaluator_user)
    con = client.get(url_de(caso.procedure, query)).content.decode()
    assert "offers/" in con or "original" in con
    assert re.search(r'<a href="[^"]*original[^"]*">oferta\.pdf · página 1</a>', con)
    client.logout()
    entrar(client, lector)
    sin = client.get(url_de(caso.procedure, query)).content.decode()
    assert "oferta.pdf · página 1" in sin
    assert "original" not in sin[sin.index('id="cu-panel"'):]


def test_oferta_o_requisito_de_otro_procedimiento_dan_404(client, caso_varios_en_curso):
    caso = caso_varios_en_curso
    entrar(client, caso.user)
    req = requirement(caso.procedure, "garantía de mantenimiento")
    assert client.get(url_de(caso.procedure, f"?celda=999999-{req.pk}")).status_code == 404
    assert client.get(url_de(caso.procedure, f"?celda={caso.offers[0].pk}-999999")).status_code == 404


def test_una_celda_que_ya_no_existe_muestra_el_cuadro_sin_panel(
        client, procedure, evaluator_user, fake_ai):
    """Tras una evaluación nueva (otra versión de la matriz) o con un par sin resultado, el cuadro
    se muestra igual y sin panel; no es un error."""
    version, filas, ofertas = sintetico(procedure, evaluator_user, 12, 2)
    entrar(client, evaluator_user)
    vieja = procedure.matrix_versions.get(number=1).requirements.first()
    response = client.get(url_de(procedure, f"?celda={ofertas[0].pk}-{vieja.pk}"))
    assert response.status_code == 200 and 'id="cu-panel"' not in response.content.decode()
    sin = next(f for i, f in enumerate(filas) if i % 6 == 5)  # sin resultado para la oferta 1
    response = client.get(url_de(procedure, f"?celda={ofertas[0].pk}-{sin.pk}"))
    assert response.status_code == 200
    html = response.content.decode()
    assert 'id="cu-panel"' not in html and texto_de(html, ofertas[0].pk, sin.pk) == "Sin resultado"
    con = next(f for i, f in enumerate(filas) if i % 6 == 0)
    assert 'id="cu-panel"' in client.get(
        url_de(procedure, f"?celda={ofertas[0].pk}-{con.pk}")).content.decode()
