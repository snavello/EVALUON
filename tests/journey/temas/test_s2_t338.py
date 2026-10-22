"""Pliego y matriz más claros (REQ-132, REQ-126, REQ-141, REQ-082; plan 017, T-338): la línea
«Hay / Falta» sin contradicciones, el mosaico de cumplimiento con todas sus categorías y el
detalle de los renglones técnicos sin repetir las cláusulas comunes. Todo el material es
inventado (P4); los resultados de la evaluación se guardan directo, sin el modelo."""

import hashlib
import html as htmllib
import itertools
import re

import pytest
from django.urls import reverse

from evaluon.audit.models import Channel
from evaluon.journey import memo
from evaluon.journey.temas import s2_matriz, s4_propuesta
from evaluon.portal import models as p
from evaluon.tenders import models as m
from tests.accounts.test_session import TEST_PASSWORD
from tests.assessment.test_matrix import (  # noqa: F401  (fixtures)
    evaluated,
    three,
)
from tests.journey.temas.test_s2_matriz import two_versions  # noqa: F401  (fixture)
from tests.journey.temas.test_s2_tiles import tiles_of

pytestmark = pytest.mark.django_db

GENERAL = "Pliego de Bases y Condiciones Generales"
DISPOSITION = "Disposición Aprobatoria del pliego general"
ERROR_SCREEN = ("El Portal respondió su pantalla de error en lugar del documento. Queda la "
                "carga manual.")
_n = itertools.count(1)


def log_in(client, user):
    assert client.login(username=user.username, password=TEST_PASSWORD)


def tab(procedure, query=""):
    return reverse("expedientes:pliego", args=[procedure.pk]) + query


def plain(fragment):
    return " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


# --- 1. «Hay / Falta» -----------------------------------------------------------------------------


@pytest.fixture
def listed(procedure, operator_user):
    """El Portal lista tres documentos del pliego: uno está cargado y leído, dos no se pudieron
    bajar (como en el procedimiento 10 del piloto)."""
    link = p.PortalLink.objects.create(
        url=f"https://portal.ejemplo.test/x.aspx?qs={next(_n)}", procedure=procedure,
        created_by=operator_user)
    p.PortalProposal.objects.create(
        link=link, exploration=1, origin=p.Origin.IMPORTACION, anomalies=[
            {"parte": f"documento «{GENERAL}»", "motivo": ERROR_SCREEN},
            {"parte": f"documento «{DISPOSITION}»", "motivo": ERROR_SCREEN},
            {"parte": "renglones", "motivo": "la tabla de renglones no tiene filas"},
        ])
    return link


def hay_falta(client, procedure):
    html = client.get(tab(procedure)).content.decode()
    hay = re.search(r'id="seccion-resumen">(.*?)</p>', html, re.S)
    falta = re.search(r'<p class="falta">(.*?)</p>', html, re.S)
    return html, plain(hay.group(1)), plain(falta.group(1)) if falta else ""


def test_hay_cuenta_los_documentos_del_pliego_contra_los_que_lista_el_portal(
        client, procedure, matrix, listed, operator_user):
    """REQ-132: «Hay» dice «1 de 3 documentos del pliego (leído)» y la matriz, en la misma línea;
    ya no afirma que «el documento del pliego está leído» como si fuera el único."""
    log_in(client, operator_user)
    _, hay, _ = hay_falta(client, procedure)
    assert hay.startswith("1 de 3 documentos del pliego (leído)")
    assert "matriz versión 1 validada" in hay
    assert "El documento del pliego está leído" not in hay
    assert "La versión 1 está validada" not in hay


def test_falta_junta_los_no_bajados_en_una_sola_linea_con_un_solo_subir_archivo(
        client, procedure, matrix, listed, operator_user):
    """REQ-132: «Falta» nombra los dos documentos en una frase corta, sin la explicación del Portal,
    y con un único «Subir archivo»."""
    log_in(client, operator_user)
    html, _, falta = hay_falta(client, procedure)
    assert falta.startswith(
        "2 documentos que lista el Portal y no se pudieron bajar: "
        f"{GENERAL}; {DISPOSITION}")
    assert "pantalla de error" not in falta
    assert falta.count("Subir archivo") == 1
    block = re.search(r'<p class="falta">(.*?)</p>', html, re.S).group(1)
    assert block.count(">Subir archivo</a>") == 1


def test_el_motivo_del_portal_va_en_el_detalle_del_mosaico_de_documentos(
        client, procedure, matrix, listed, operator_user):
    """REQ-132, P3: la explicación de por qué no bajó cada documento queda en el detalle del
    mosaico «Documentos del pliego», con el nombre de cada uno."""
    log_in(client, operator_user)
    html = client.get(tab(procedure)).content.decode()
    detail = html[html.index('id="s2-documentos"'):html.index('id="s2-matriz"')]
    assert GENERAL in detail and DISPOSITION in detail
    assert detail.count("pantalla de error") == 2


def test_un_solo_no_bajado_se_escribe_en_singular(client, procedure, matrix, operator_user):
    """REQ-132: «1 documento que lista el Portal y no se pudo bajar»."""
    link = p.PortalLink.objects.create(
        url=f"https://portal.ejemplo.test/x.aspx?qs={next(_n)}", procedure=procedure,
        created_by=operator_user)
    p.PortalProposal.objects.create(link=link, exploration=1, origin=p.Origin.IMPORTACION,
                                    anomalies=[{"parte": f"documento «{GENERAL}»",
                                                "motivo": ERROR_SCREEN}])
    log_in(client, operator_user)
    _, hay, falta = hay_falta(client, procedure)
    assert hay.startswith("1 de 2 documentos del pliego (leído)")
    assert falta.startswith(f"1 documento que lista el Portal y no se pudo bajar: {GENERAL}")


def test_sin_documentos_que_el_portal_liste_y_falten_el_hay_no_cambia(
        client, procedure, matrix, operator_user):
    """REQ-132: si lo cargado es todo lo que hay, sigue la frase de siempre (sin «de N»)."""
    log_in(client, operator_user)
    _, hay, falta = hay_falta(client, procedure)
    assert "documento del pliego está leído" in hay
    assert " de " not in hay.split(".")[0]
    assert falta == ""


# --- 2. «Cumplimiento por tipo y oferta» ---------------------------------------------------------


def counts_of(sub):
    """`{categoría: cantidad}` de la línea de apoyo del mosaico."""
    found = {}
    for key, pattern in (("no", r"(\d+) no cumple"), ("nd", r"(\d+) no determinados?"),
                         ("pe", r"(\d+) sin resultado")):
        match = re.search(pattern, sub)
        found[key] = int(match.group(1)) if match else 0
    return found


def test_el_cumplimiento_desglosa_todas_las_categorias_y_la_suma_cuadra(
        evaluated, procedure, matrix, operator_user, rf):
    """REQ-126, P3: la cifra grande son los que cumplen; la línea de apoyo dice cuántos no cumplen,
    cuántos no están determinados y cuántos están sin resultado, con las mismas cuentas que la
    sección Evaluación; la suma da el total."""
    tile = tiles_of(operator_user, procedure, rf)["cumplimiento"]
    with memo.scope():
        fig = s4_propuesta.figures_of(memo.matrix_page(operator_user, procedure.pk,
                                                       channel=Channel.SCREEN))
    ok = sum(o.ok for o in fig.offers)
    no, nd = fig.no, fig.nd
    pe = sum(o.pe for o in fig.offers)
    total = ok + no + nd + pe
    assert tile.big == ok and tile.unit == "cumplen"
    assert counts_of(tile.sub) == {"no": no, "nd": nd, "pe": pe}
    assert f"De {total}" in tile.sub
    assert "Propuesta del sistema; decide la Comisión" in tile.sub
    assert not re.search(r"\bde \d+ cumplen\b", f"{tile.unit} {tile.sub}")


def test_el_cumplimiento_nombra_el_total_como_requisitos_por_ofertas(
        evaluated, procedure, matrix, operator_user, rf):
    """REQ-126: «De 81 (27 requisitos × 3 ofertas)»: de dónde sale el total."""
    tile = tiles_of(operator_user, procedure, rf)["cumplimiento"]
    found = re.search(r"De (\d+) \((\d+) requisitos? × (\d+) ofertas?\)", tile.sub)
    if found is None:  # hay requisitos que no aplican: el total no es el producto
        assert "no aplica" in tile.sub
        return
    total, requirements, offers = map(int, found.groups())
    assert total == requirements * offers


# --- 3. Renglones técnicos -----------------------------------------------------------------------

TABLE = ("RENGLÓN BIENES CANTIDADES UNIDAD DE MEDIDA\n"
         "1 ALIMENTO BALANCEADO PARA GATOS ADULTOS - MARCA GATOFELIZ - LINEA PLUS. 2700 KILOS\n"
         "2 ALIMENTO BALANCEADO PARA GATITOS - MARCA GATOFELIZ - LINEA CRIA. 8760 KILOS\n"
         "3 ARENA SANITARIA AGLOMERANTE - MARCA ARENITA. 250 BOLSAS")
DELIVERY = "8.2. LUGAR DE ENTREGA: Edificio inventado de la localidad de Ejemplo Sur."
TERM = "9.2.1. RENGLONES NROS. 1 A 3: QUINCE (15) días hábiles para la entrega de los bienes."
OBJECT = "1.1. El objeto de la presente contratación es la “Adquisición de alimento para gatos”."


@pytest.fixture
def tecnicos(procedure, two_versions, operator_user):  # noqa: F811
    """El borrador de la versión 2 con sus tres renglones técnicos citando: el objeto y el lugar de
    entrega (comunes), la tabla de renglones y un plazo «de renglón» que es el mismo en todos."""
    draft, _ = two_versions
    document = m.Document.objects.create(
        procedure=procedure, kind="pliego", title="Pliego inventado t338", file_name="t338.pdf",
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
    requirements = list(draft.requirements.filter(category="tecnico").order_by("number"))
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
    return draft, requirements


def technical_html(client, procedure):
    html = client.get(tab(procedure, "?tipo=tecnico")).content.decode()
    return html


def row_block(html, number):
    start = html.index(f'id="req-{number}"')
    end = html.index(f'id="detalle-{number}"')
    detail_end = html.index("</tr>", end)
    return html[start:end], html[end:detail_end]


def test_cada_renglon_se_presenta_con_su_bien_y_no_con_el_objeto(
        client, procedure, tecnicos, operator_user):
    """REQ-082: el texto del renglón sale de su fila en la tabla citada, no de la primera cita."""
    _, requirements = tecnicos
    log_in(client, operator_user)
    html = technical_html(client, procedure)
    first, _ = row_block(html, requirements[0].number)
    assert ("Renglón 1 · Alimento balanceado para gatos adultos — Gatofeliz Linea Plus "
            "· 2700 kilos") in plain(first)
    third, _ = row_block(html, requirements[2].number)
    assert "Renglón 3 · Arena sanitaria aglomerante — Arenita · 250 bolsas" in plain(third)
    assert "El objeto de la presente contratación" not in first


def test_al_abrir_un_renglon_la_cita_del_renglon_muestra_solo_su_fila(
        client, procedure, tecnicos, operator_user):
    """REQ-082, P3: el detalle del renglón 2 trae su fila de la tabla (con el encabezado de las
    columnas) y no las filas de los otros renglones."""
    _, requirements = tecnicos
    log_in(client, operator_user)
    html = technical_html(client, procedure)
    _, detail = row_block(html, requirements[1].number)
    assert "ALIMENTO BALANCEADO PARA GATITOS" in detail
    assert "RENGLÓN BIENES CANTIDADES" in detail
    assert "ALIMENTO BALANCEADO PARA GATOS ADULTOS" not in detail
    assert "ARENA SANITARIA" not in detail


def test_las_clausulas_comunes_aparecen_una_sola_vez_en_la_cabecera_del_grupo(
        client, procedure, tecnicos, operator_user):
    """REQ-082: el objeto, el lugar de entrega y el plazo que repiten todos los renglones están
    una vez, bajo «Cláusulas comunes a todos los renglones (3)»; el texto literal sigue en pantalla
    (P3) y cada renglón tiene un enlace corto."""
    _, requirements = tecnicos
    log_in(client, operator_user)
    html = technical_html(client, procedure)
    for text in (OBJECT, DELIVERY, TERM):
        assert html.count(text) == 1, text
    assert "Cláusulas comunes a todos los renglones (3)" in html
    head = html.index("Cláusulas comunes a todos los renglones")
    assert head < html.index(f'id="req-{requirements[0].number}"')
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
    html = technical_html(client, procedure)
    head = html[html.index('id="comunes-tecnico"'):html.index("</details>",
                                                              html.index('id="comunes-tecnico"'))]
    assert "ARENA SANITARIA AGLOMERANTE" in head and "GATITOS" in head


def test_los_requisitos_formales_no_cambian(client, procedure, tecnicos, operator_user):
    """REQ-082: la cabecera de comunes es solo del grupo técnico; los formales siguen con sus
    citas."""
    draft, _ = tecnicos
    log_in(client, operator_user)
    html = client.get(tab(procedure)).content.decode()
    assert html.count("Cláusulas comunes a todos los renglones") == 1
    formal = draft.requirements.filter(category="formal").exclude(
        state__in=("quitado", "sugerido")).first()
    quote = formal.quotes.order_by("order").first()
    assert quote.text.split("\n")[0][:40] in html


def test_una_cita_con_cambio_de_circular_no_se_vuelve_comun(
        client, procedure, tecnicos, operator_user):
    """P3: si una circular cambió una cita de un renglón, esa cita se queda en su renglón."""
    _, requirements = tecnicos
    quote = requirements[0].quotes.get(segment__key="entrega")
    circular = m.Document.objects.create(
        procedure=procedure, kind="circular_modificatoria", title="Circular inventada", file_name="c.pdf",
        file_format="pdf", file_size=10, file_sha256=f"{next(_n):064x}",
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
    html = technical_html(client, procedure)
    assert "Cláusulas comunes a todos los renglones (3)" in html  # la sigue teniendo el resto
    _, detail = row_block(html, requirements[0].number)
    assert "Nuevo lugar de entrega." in detail
    assert "+ 2 cláusulas comunes" in plain(detail)


# --- El texto del renglón, sin la matriz -----------------------------------------------------------


def test_sin_la_tabla_el_renglon_usa_el_del_procedimiento_y_si_no_el_texto_de_siempre():
    """REQ-082: sin fila en la tabla, la del renglón del procedimiento; sin ninguna, no se
    inventa: queda el texto actual."""
    line = type("L", (), {"number": 4, "description": "ALIMENTO PARA PERROS",
                          "quantity": __import__("decimal").Decimal("360.0000"), "unit": "kg"})
    assert s2_matriz.renglon_text(4, [], {4: line}, "1.1. El objeto") == (
        "Renglón 4 · Alimento para perros · 360 kg")
    assert s2_matriz.renglon_text(5, [], {4: line}, "1.1. El objeto") == (
        "Renglón 5 · 1.1. El objeto")
    assert s2_matriz.renglon_text(5, [TABLE], {}, "x").startswith("Renglón 5 · x")


def test_la_fila_de_una_tabla_con_tabuladores_se_lee_por_celdas():
    """REQ-082: la lectura de una tabla de celdas separa con tabulaciones (`tables.py`)."""
    table = "Renglón\tBienes\tCantidad\tUnidad\n1\tResma de papel A4\t100\tunidades\n2\tToner\t5\tcajas"
    assert s2_matriz.renglon_text(2, [table], {}, "x") == "Renglón 2 · Toner · 5 cajas"
    assert s2_matriz.table_rows(table)[1] == "1\tResma de papel A4\t100\tunidades"


def test_una_cita_que_no_es_una_tabla_no_se_toma_por_tabla():
    """REQ-082: una cláusula numerada «1.1. …» no es una fila."""
    assert s2_matriz.table_rows("1.1. El objeto\n2.1. Otra cosa") == {}
    assert s2_matriz.table_rows("RENGLÓN BIENES\n1 Solo una fila") == {}


def test_las_hojas_y_plantillas_de_la_seccion_no_traen_estilos_ni_scripts_en_linea():
    """Aviso de la 017: ni `style=` ni scripts en línea en las plantillas de la sección 2."""
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[3] / "evaluon" / "templates" / "journey" / "temas"
    for plantilla in sorted(raiz.glob("s2_*.html")):
        text = re.sub(r"\{% comment %\}.*?\{% endcomment %\}", "", plantilla.read_text(
            encoding="utf-8"), flags=re.S)
        assert " style=" not in text, plantilla.name
        assert not re.search(r"<script(?![^>]*\bsrc=)", text), plantilla.name
