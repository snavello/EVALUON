"""Renglones técnicos sin repetir en la sección Evaluación (REQ-126, REQ-082; plan 017, T-339):
cada renglón con su bien en el título, su fila de la tabla al abrirlo y los puntos del pliego
comunes una sola vez en la cabecera del grupo. Todo el material es inventado (P4); los resultados
de la evaluación se guardan directo, sin el modelo."""

import decimal
import hashlib
import html as htmllib
import itertools
import re

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from evaluon.journey import renglones
from evaluon.portal import models as p
from evaluon.tenders import models as m
from tests.accounts.test_session import TEST_PASSWORD
from tests.assessment.test_matrix import (  # noqa: F401  (fixtures)
    evaluated,
    three,
)
from tests.journey.temas.test_s2_t338 import DELIVERY, OBJECT, TABLE, TERM

pytestmark = pytest.mark.django_db

_n = itertools.count(1)


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def plain(fragment):
    return " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


@pytest.fixture
def tecnicos(procedure, evaluated, operator_user):  # noqa: F811
    """La matriz vigente con sus tres renglones técnicos citando: el objeto y el lugar de entrega
    (comunes), la tabla de renglones y un plazo que es el mismo en todos."""
    with connection.cursor() as cursor:  # las filas de una matriz validada solo admiten un borrador
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        for table in ("tenders_requirement_quote", "tenders_requirement_source"):
            cursor.execute(f"ALTER TABLE {table} DISABLE TRIGGER USER")
    version = procedure.matrix_versions.get(number=1)
    document = m.Document.objects.create(
        procedure=procedure, kind="pliego", title="Pliego inventado t339", file_name="t339.pdf",
        file_format="pdf", file_size=10, file_sha256=f"{next(_n):064x}", loaded_by=operator_user)
    pieces = [("objeto", OBJECT), ("tabla", TABLE), ("entrega", DELIVERY), ("plazo", TERM)]
    canonical, spans = "", {}
    for key, text in pieces:
        start = len(canonical) + (1 if canonical else 0)
        canonical = (canonical + "\n" if canonical else "") + text
        spans[key] = (start, start + len(text), text)
    reading = m.Reading.objects.create(
        document=document, sequence=1, pages={"pages": []}, tables=[], canonical_text=canonical,
        canonical_sha256=hashlib.sha256(canonical.encode()).hexdigest(), items=[],
        tool_versions={}, report={})
    segments = {}
    for order, (key, (start, end, text)) in enumerate(spans.items(), start=1):
        segments[key] = m.Segment.objects.create(
            reading=reading, order=order, key=key, label="", path=key,
            segment_type="tabla" if key == "tabla" else "clausula", items=[], page_start=1,
            page_end=1, char_start=start, char_end=end, text=text, text_origin="pdf_text")
    requirements = list(version.requirements.filter(category="tecnico").order_by("number"))
    assert [r.items for r in requirements] == [[1], [2], [3]]
    for requirement in requirements:
        base = requirement.quotes.count()
        for order, (key, scope) in enumerate(
                (("objeto", "general"), ("tabla", "propia"), ("entrega", "general"),
                 ("plazo", "propia")), start=base + 1):
            start, end, text = spans[key]
            m.RequirementQuote.objects.create(
                requirement=requirement, order=order, segment=segments[key], char_start=start,
                char_end=end, text=text, scope=scope, quote_flag="")
    return version, requirements


def evaluation(client, procedure, query="?tipo=tecnico"):
    response = client.get(reverse("expedientes:evaluacion", args=[procedure.pk]) + query)
    assert response.status_code == 200
    return response.content.decode()


def row_block(html, number):
    """`(la fila, su detalle)` del requisito `number` en la tabla de la propuesta."""
    start = html.index(f'id="ev-{number}"')
    end = html.index(f'id="ev-det-{number}"')
    return html[start:end], html[end:html.index("</tr>", end)]


def test_cada_renglon_se_presenta_con_su_bien_y_no_con_el_objeto(
        client, procedure, tecnicos, operator_user):
    """REQ-082: el título del renglón sale de su fila en la tabla citada, no de la primera cita."""
    _, requirements = tecnicos
    log_in(client, operator_user)
    html = evaluation(client, procedure)
    first, _ = row_block(html, requirements[0].number)
    assert ("Renglón 1 · Alimento balanceado para gatos adultos — Gatofeliz Linea Plus "
            "· 2700 kilos") in plain(first)
    third, _ = row_block(html, requirements[2].number)
    assert "Renglón 3 · Arena sanitaria aglomerante — Arenita · 250 bolsas" in plain(third)
    assert "El objeto de la presente contratación" not in first


def test_al_abrir_un_renglon_el_punto_de_la_tabla_muestra_solo_su_fila(
        client, procedure, tecnicos, operator_user):
    """REQ-082, P3: el detalle del renglón 2 trae el encabezado de las columnas y su fila, no las
    filas de los otros renglones."""
    _, requirements = tecnicos
    log_in(client, operator_user)
    html = evaluation(client, procedure)
    _, detail = row_block(html, requirements[1].number)
    assert "ALIMENTO BALANCEADO PARA GATITOS" in detail
    assert "RENGLÓN BIENES CANTIDADES" in detail
    assert "ALIMENTO BALANCEADO PARA GATOS ADULTOS" not in detail
    assert "ARENA SANITARIA" not in detail


def test_los_puntos_comunes_aparecen_una_sola_vez_en_la_cabecera_del_grupo(
        client, procedure, tecnicos, operator_user):
    """REQ-082: el objeto, el lugar de entrega y el plazo que repiten todos los renglones están
    una vez, bajo «Cláusulas comunes a todos los renglones (3)»; el literal sigue en pantalla (P3)
    y cada renglón tiene su enlace corto."""
    _, requirements = tecnicos
    log_in(client, operator_user)
    html = evaluation(client, procedure)
    for text in (OBJECT, DELIVERY, TERM):
        assert html.count(text) == 1, text
    assert "Cláusulas comunes a todos los renglones (3)" in html
    assert html.index("Cláusulas comunes a todos los renglones") < html.index(
        f'id="ev-{requirements[0].number}"')
    assert 'id="comunes-tecnico"' in html
    for requirement in requirements:
        _, detail = row_block(html, requirement.number)
        assert 'href="#comunes-tecnico"' in detail
        assert "+ 3 cláusulas comunes" in plain(detail)
        assert OBJECT not in detail and DELIVERY not in detail and TERM not in detail


def test_la_tabla_completa_queda_a_la_vista_una_vez_en_la_cabecera(
        client, procedure, tecnicos, operator_user):
    """P3: recortar la tabla en cada renglón no hace perder el literal: la tabla entera está una
    vez en las cláusulas comunes."""
    log_in(client, operator_user)
    html = evaluation(client, procedure)
    start = html.index('id="comunes-tecnico"')
    head = html[start:html.index("</details>", start)]
    assert "ARENA SANITARIA AGLOMERANTE" in head and "GATITOS" in head
    assert "GATOS ADULTOS" in head


def test_las_acciones_de_la_comision_sobre_cada_par_siguen_igual(
        client, procedure, tecnicos, operator_user, evaluated):  # noqa: F811
    """P6: el detalle de cada renglón sigue trayendo sus pares por oferta, con el enlace al
    detalle del par; solo cambia cómo se muestra el pliego."""
    _, requirements = tecnicos
    log_in(client, operator_user)
    html = evaluation(client, procedure)
    for requirement in requirements:
        _, detail = row_block(html, requirement.number)
        for offer in evaluated:
            assert f'id="par-{offer.number}-{requirement.number}"' in detail
        assert detail.count('id="par-') == len(evaluated)


def test_sin_filtro_los_requisitos_formales_no_cambian(client, procedure, tecnicos, operator_user):
    """REQ-082: la cabecera de comunes es solo del grupo técnico; los formales siguen con su
    punto del pliego."""
    log_in(client, operator_user)
    html = evaluation(client, procedure, "")
    assert html.count("Cláusulas comunes a todos los renglones") == 1
    assert "Presentar la declaración jurada" in html


def test_un_punto_que_una_circular_cambio_no_se_vuelve_comun(
        client, procedure, tecnicos, operator_user):
    """P3: si una circular cambió el punto de un renglón, ese punto se queda en su renglón."""
    _, requirements = tecnicos
    quote = requirements[0].quotes.get(segment__key="entrega")
    circular = m.Document.objects.create(
        procedure=procedure, kind="circular_modificatoria", title="Circular inventada",
        file_name="c.pdf", file_format="pdf", file_size=10, file_sha256=f"{next(_n):064x}",
        issued_on="2026-03-01", loaded_by=operator_user)
    reading = m.Reading.objects.create(
        document=circular, sequence=1, pages={"pages": []}, tables=[],
        canonical_text="Nuevo lugar de entrega.", canonical_sha256="b" * 64, items=[],
        tool_versions={}, report={})
    segment = m.Segment.objects.create(
        reading=reading, order=1, key="n", label="", path="n", segment_type="clausula",
        items=[], page_start=1, page_end=1, char_start=0, char_end=23,
        text="Nuevo lugar de entrega.", text_origin="pdf_text")
    m.RequirementSource.objects.create(
        requirement=requirements[0], quote=quote, segment=segment, char_start=0, char_end=23,
        text="Nuevo lugar de entrega.", effect="modifica", issued_on="2026-03-01")
    log_in(client, operator_user)
    html = evaluation(client, procedure)
    assert "Cláusulas comunes a todos los renglones (3)" in html
    _, detail = row_block(html, requirements[0].number)
    assert "Nuevo lugar de entrega." in detail
    assert "+ 2 cláusulas comunes" in plain(detail)


def test_los_renglones_del_procedimiento_se_piden_una_vez_por_pedido(
        client, procedure, tecnicos, operator_user):
    """REQ-100: si el título sale del renglón del procedimiento, se lo consulta una sola vez para
    todos, no una por renglón."""
    _, requirements = tecnicos
    for requirement in requirements:  # sin tabla: el bien sale del Portal
        requirement.quotes.filter(segment__key="tabla").delete()
    source = m.Document.objects.create(
        procedure=procedure, kind="pliego", title="Renglones inventados", file_name="r.pdf",
        file_format="pdf", file_size=10, file_sha256=f"{next(_n):064x}", loaded_by=operator_user)
    for number in (1, 2, 3):
        p.PortalLine.objects.create(
            procedure=procedure, number=number, description=f"BIEN INVENTADO {number}",
            quantity=decimal.Decimal("10"), unit="unidades", document=source)
    log_in(client, operator_user)
    evaluation(client, procedure)  # calienta cachés
    with CaptureQueriesContext(connection) as queries:
        html = evaluation(client, procedure)
    assert "Renglón 2 · Bien inventado 2 · 10 unidades" in plain(html)
    assert sum('"portal_portalline"' in q["sql"] for q in queries) <= 1


# --- El texto del renglón, sin la pantalla ---------------------------------------------------------


def test_una_descripcion_igual_a_renglon_n_no_se_repite():
    """REQ-082: un renglón del procedimiento cuya descripción es «Renglón 1» no sale «Renglón 1 ·
    Renglón 1»; queda el texto de siempre."""
    line = type("L", (), {"number": 1, "description": "Renglón 1",
                          "quantity": decimal.Decimal("5"), "unit": "u"})
    assert renglones.renglon_text(1, [], {1: line}, "1.1. El objeto") == (
        "Renglón 1 · 1.1. El objeto")
    assert renglones.renglon_text(1, [], {1: line}, None) is None
    line.description = "RENGLON  1"
    assert renglones.renglon_text(1, [], {1: line}, "x") == "Renglón 1 · x"
