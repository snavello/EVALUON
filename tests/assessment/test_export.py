"""Exportación de la planilla por oferta y del cuadro comparativo (REQ-093; plan 014, T-212;
ADR-0050). Caso chico con resultados guardados directo y cotizaciones inventadas (P4). El `.xlsx`
se reabre leyendo el zip y su XML (la prueba no suma dependencias)."""

import hashlib
import io
import re
import zipfile
from decimal import Decimal
from unittest import mock
from xml.etree import ElementTree

import pytest

from evaluon.accounts.permissions import RoleRejected
from evaluon.assessment import models as am
from evaluon.assessment.models import Result
from evaluon.assessment.services import discards, review
from evaluon.assessment.services import export as service
from evaluon.assessment.services import external_stages
from evaluon.audit.models import AuditEvent, EventType
from evaluon.audit.models import Outcome as AuditOutcome
from evaluon.tenders import export as tenders_export
from tests.assessment.test_matrix import (  # noqa: F401  (fixtures y ayudas)
    add_run,
    open_matrix,
    page_of,
    requirement,
    three,
)
from tests.assessment.test_ordering import portal, quote_data  # noqa: F401  (fixtures y ayudas)

pytestmark = pytest.mark.django_db

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def read_xlsx(data):
    """`{nombre de la hoja: [[texto de cada celda por fila]]}` leyendo el zip."""
    archive = zipfile.ZipFile(io.BytesIO(data))
    shared = []
    if "xl/sharedStrings.xml" in archive.namelist():
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        shared = ["".join(t.text or "" for t in si.iter("{%s}t" % NS["m"]))
                  for si in root.findall("m:si", NS)]
    book = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    names = [s.get("name") for s in book.find("m:sheets", NS)]
    sheets = {}
    for index, name in enumerate(names, start=1):
        root = ElementTree.fromstring(archive.read(f"xl/worksheets/sheet{index}.xml"))
        rows = []
        for row in root.find("m:sheetData", NS):
            values = {}
            for cell in row:
                column = re.match(r"[A-Z]+", cell.get("r")).group()
                index_ = 0
                for letter in column:
                    index_ = index_ * 26 + ord(letter) - 64
                value = cell.find("m:v", NS)
                if value is None:
                    text = ""
                elif cell.get("t") == "s":
                    text = shared[int(value.text)]
                else:
                    text = value.text
                values[index_ - 1] = text
            width = max(values) + 1 if values else 0
            rows.append([values.get(i, "") for i in range(width)])
        sheets[name] = rows
    return sheets


def flat(rows):
    return [text for row in rows for text in row]


@pytest.fixture
def proposed(three, portal, procedure, operator_user):  # noqa: F811
    """B con un motivo que la descarta entera; C con uno que descarta solo el renglón 2; A sin
    motivos. Con cotizaciones del Portal."""
    a, b, c = three
    open_matrix()
    declaration = requirement(procedure, "declaración jurada")
    add_run(operator_user, procedure, a, {declaration: "cumple"})
    add_run(operator_user, procedure, b, {declaration: "no_cumple"})
    add_run(operator_user, procedure, c, {requirement(procedure, item=2): "no_cumple",
                                          requirement(procedure, item=1): "cumple"})
    quote_data(portal, procedure, a, total=Decimal("900"), prices={1: (Decimal("10"), 1),
                                                                 2: (Decimal("10"), 1)})
    quote_data(portal, procedure, b, total=Decimal("100"), prices={1: (Decimal("5"), 1),
                                                                 2: (Decimal("5"), 1)})
    quote_data(portal, procedure, c, total=Decimal("500"), prices={1: (Decimal("7"), 1),
                                                                 2: (Decimal("7"), 1)})
    return three


def last_event():
    return AuditEvent.objects.filter(event_type=EventType.EVAL_EXPORT).order_by("-pk").first()


def test_the_planilla_has_one_sheet_per_offer_with_every_requirement(
        proposed, procedure, operator_user):
    """REQ-093: el libro reabierto trae el 100 % de las ofertas (una hoja cada una) y el 100 % de
    los requisitos de la matriz en cada hoja, con resultado, fundamento y el rótulo de propuesta."""
    data, name, kind = service.export(operator_user, procedure.pk, "planilla", "xlsx")
    assert name.startswith("planilla-") and name.endswith(".xlsx") and "spreadsheetml" in kind
    sheets = read_xlsx(data)
    page = page_of(operator_user, procedure)
    assert list(sheets) == [f"Oferta {o.number}" for o in page.offers]
    assert len(page.requirements) >= 2
    for offer in page.offers:
        rows = sheets[f"Oferta {offer.number}"]
        texts = flat(rows)
        assert any(offer.bidder in t for t in texts)
        assert any(t.startswith("Propuesta de evaluación del sistema") for t in texts)
        start = next(i for i, row in enumerate(rows) if row and row[0] == "Requisito") + 1
        numbers = [row[0] for row in rows[start:start + len(page.requirements)]]
        assert numbers == [str(r.number) for r in page.requirements]
    b_sheet = flat(sheets[f"Oferta {proposed[1].number}"])
    assert "No cumple" in b_sheet and "Lo dice el texto." in b_sheet
    assert "Oferta completa" in b_sheet and "Propuesto, sin decidir" in b_sheet


def test_the_planilla_shows_the_decision_with_who_and_when_and_the_discard_decision(
        proposed, procedure, operator_user, evaluator_user):
    """REQ-093: la decisión de la Comisión sobre un resultado y sobre un descarte figura con quién
    y cuándo, en hora local."""
    b = proposed[1]
    result = Result.objects.filter(offer=b, outcome="no_cumple").get()
    review.confirm(evaluator_user, result.pk, note="De acuerdo.")
    discards.decide(evaluator_user, procedure.pk, b.pk, None, "confirmar", note="Falta la DJ.")
    data, _, _ = service.export(operator_user, procedure.pk, "planilla", "xlsx")
    texts = flat(read_xlsx(data)[f"Oferta {b.number}"])
    who = evaluator_user.username
    assert any(re.fullmatch(
        rf"Confirmado por {who} el \d\d/\d\d/\d{{4}} \d\d:\d\d · motivo: De acuerdo\.", t)
        for t in texts)
    assert any(re.fullmatch(
        rf"Confirmado por {who} el \d\d/\d\d/\d{{4}} \d\d:\d\d · nota: Falta la DJ\.", t)
        for t in texts)


def test_the_cuadro_has_every_offer_and_requirement_and_the_economic_order_of_the_screen(
        proposed, procedure, operator_user, evaluator_user):
    """REQ-093 y REQ-091: el cuadro trae el 100 % de ofertas y requisitos y el orden económico
    total y por renglón con los mismos números que la pantalla; la oferta con descarte confirmado
    figura como descartada y no se ordena; el renglón confirmado figura descartado."""
    a, b, c = proposed
    discards.decide(evaluator_user, procedure.pk, b.pk, None, "confirmar")
    discards.decide(evaluator_user, procedure.pk, c.pk, 2, "confirmar")
    data, name, _ = service.export(operator_user, procedure.pk, "cuadro", "xlsx")
    assert name.startswith("cuadro-")
    sheet = read_xlsx(data)["Cuadro comparativo"]
    page = page_of(operator_user, procedure)
    header = next(row for row in sheet if row and row[0] == "Requisito")
    assert header[3:] == [f"Oferta {o.number} · {o.bidder}" for o in page.offers]
    start = sheet.index(header) + 1
    body = sheet[start:start + len(page.requirements)]
    assert [row[0] for row in body] == [str(r.number) for r in page.requirements]
    assert all(len(row) == 3 + len(page.offers) for row in body)
    order_start = next(i for i, row in enumerate(sheet) if row[:2] == ["Orden", "Oferta"])
    totals = {row[1]: row for row in sheet[order_start + 1:order_start + 4]}
    mine = totals[f"{c.number} · {c.bidder}"]
    assert mine[0] == "1" and mine[3] == "$ 500" and "Renglón 2 descartado" in mine[4]
    assert totals[f"{a.number} · {a.bidder}"][0] == "2"
    assert totals[f"{b.number} · {b.bidder}"][0] == "—"
    assert totals[f"{b.number} · {b.bidder}"][4].startswith("Descartada.")
    assert any("(descartada)" in text for text in flat(sheet))


def test_an_undecided_discard_is_marked_and_keeps_ordering(proposed, procedure, operator_user):
    """REQ-091 y REQ-093: el descarte propuesto sin decidir se marca como tal y la oferta sigue
    ordenándose."""
    b = proposed[1]
    data, _, _ = service.export(operator_user, procedure.pk, "cuadro", "xlsx")
    sheet = read_xlsx(data)["Cuadro comparativo"]
    row = next(r for r in sheet if len(r) > 1 and r[1] == f"{b.number} · {b.bidder}")
    assert row[0] == "1" and row[3] == "$ 100"
    assert "Descarte propuesto, sin decidir" in row[4]


@pytest.mark.parametrize("document", ["planilla", "cuadro"])
def test_the_pdf_is_generated_with_the_offers_and_the_notice(
        proposed, procedure, operator_user, document):
    """REQ-093: el PDF de la planilla y del cuadro se genera dentro del equipo, con el rótulo de
    propuesta y todas las ofertas."""
    data, name, kind = service.export(operator_user, procedure.pk, document, "pdf")
    assert data.startswith(b"%PDF") and name.endswith(".pdf") and kind == "application/pdf"
    page = page_of(operator_user, procedure)
    html = service.build_html(service.collect(operator_user, procedure.pk), document)
    assert "Propuesta de evaluación del sistema" in html
    for offer in page.offers:
        assert offer.bidder in html
    for requirement_ in page.requirements:
        assert f"<td>{requirement_.number}</td>" in html


def test_every_export_leaves_the_audit_fact_with_what_and_from_which_evaluation(
        proposed, procedure, operator_user):
    """REQ-093 y P6: el hecho `eval_export` dice qué se exportó, de qué pedido de evaluación sale
    cada oferta y la huella del archivo entregado."""
    data, name, _ = service.export(operator_user, procedure.pk, "planilla", "xlsx")
    event = last_event()
    assert event.outcome == AuditOutcome.OK and event.user == operator_user
    detail = event.detail
    assert detail["document"] == "planilla" and detail["format"] == "xlsx"
    assert detail["file_name"] == name and detail["size"] == len(data)
    assert detail["sha256"] == hashlib.sha256(data).hexdigest()
    assert detail["offer_count"] == 3 and [o["offer"] for o in detail["offers"]] == [1, 2, 3]
    assert all(o["request"] for o in detail["offers"])
    assert detail["requirement_count"] == len(page_of(operator_user, procedure).requirements)
    service.export(operator_user, procedure.pk, "cuadro", "pdf")
    assert last_event().detail["document"] == "cuadro" and last_event().detail["pages"] >= 1


def test_a_failed_pdf_leaves_the_fact_as_failed(
        proposed, procedure, operator_user, monkeypatch):
    """P6: una exportación que falla deja el hecho en resultado `failed` y avisa."""
    def broken(html):
        raise tenders_export.ExportFailed("sin motor", "render_failed")
    monkeypatch.setattr(service, "html_to_pdf", broken)
    with pytest.raises(tenders_export.ExportFailed):
        service.export(operator_user, procedure.pk, "cuadro", "pdf")
    assert last_event().outcome == AuditOutcome.FAILED


def test_without_a_commission_role_it_is_refused(proposed, procedure, no_commission_user):
    """REQ-093: sin el rol de la Comisión no se exporta."""
    with pytest.raises(RoleRejected):
        service.export(no_commission_user, procedure.pk, "planilla", "xlsx")
    assert last_event() is None


def test_unknown_document_or_format_is_refused(proposed, procedure, operator_user):
    """REQ-093: un documento o formato desconocido se rechaza."""
    with pytest.raises(service.ExportRefused):
        service.export(operator_user, procedure.pk, "otro", "xlsx")
    with pytest.raises(service.ExportRefused):
        service.export(operator_user, procedure.pk, "cuadro", "csv")


def test_a_procedure_without_offers_exports_empty_files(procedure, operator_user):
    """REQ-093: sin ofertas el libro y el PDF igual se generan, diciéndolo."""
    data, _, _ = service.export(operator_user, procedure.pk, "planilla", "xlsx")
    assert "El procedimiento no tiene ofertas cargadas." in flat(read_xlsx(data)["Planilla"])
    pdf, _, _ = service.export(operator_user, procedure.pk, "planilla", "pdf")
    assert pdf.startswith(b"%PDF")


# --- Etapas fuera del equipo (REQ-122; plan 016, "Modelo de datos"; T-300) ------------------------

NONE_LINE = "Etapas fuera del equipo: Ninguna: todo corrió en el equipo."
VERIFIER_LINE = ("Etapas fuera del equipo: verificador de citas "
                 "(anthropic, claude-sonnet-5-5, modo lotes, 12 pedidos).")


def external_key(stages, *, requests=12, mode="lotes"):
    """Lo que la corrida guarda en `models_used`, `parameters` y `counts` cuando una etapa corre
    fuera del equipo (la escriben T-291 y T-299; acá se simula)."""
    return {
        "models_used": {"externo": {"habilitado": True, "etapas": stages,
                                    "proveedor": "anthropic", "modelo": "claude-sonnet-5-5"}},
        "parameters": {"externo": {"modo": mode}},
        "counts": {"externo": {"pedidos": requests, "gasto_usd": 0.41}},
    }


def add_external_run(user, procedure, offer, outcomes, key):
    """Como `add_run`, pero con la clave `externo` en la corrida guardada."""
    create = am.Run.objects.create
    with mock.patch.object(am.Run.objects, "create",
                           side_effect=lambda **fields: create(**{**fields, **key})):
        return add_run(user, procedure, offer, outcomes)


def planilla_texts(user, procedure):
    data, _, _ = service.export(user, procedure.pk, "planilla", "xlsx")
    return flat([row for rows in read_xlsx(data).values() for row in rows])


def test_the_export_says_which_stages_ran_outside_the_equipment(
        three, procedure, operator_user):
    """REQ-122: con una corrida que usó el verificador externo, la planilla, el cuadro y el HTML
    del PDF traen una sola línea con proveedor, modelo, modo y cantidad de pedidos."""
    a, b, _ = three
    open_matrix()
    declaration = requirement(procedure, "declaración jurada")
    add_external_run(operator_user, procedure, a, {declaration: "cumple"},
                     external_key({"matriz": "local", "verificador": "externo"}))
    add_run(operator_user, procedure, b, {declaration: "cumple"})
    assert planilla_texts(operator_user, procedure).count(VERIFIER_LINE) == 3
    data, _, _ = service.export(operator_user, procedure.pk, "cuadro", "xlsx")
    assert flat(read_xlsx(data)["Cuadro comparativo"]).count(VERIFIER_LINE) == 1
    collected = service.collect(operator_user, procedure.pk)
    for document in ("planilla", "cuadro"):
        assert service.build_html(collected, document).count(VERIFIER_LINE) == 1


def test_the_export_says_none_when_the_key_is_missing_or_every_stage_is_local(
        three, procedure, operator_user):
    """REQ-122: las corridas de hoy no traen la clave `externo`, y una que la trae con todo en
    `local` tampoco cuenta: «Ninguna: todo corrió en el equipo»."""
    a, b, _ = three
    open_matrix()
    declaration = requirement(procedure, "declaración jurada")
    add_run(operator_user, procedure, a, {declaration: "cumple"})
    texts = planilla_texts(operator_user, procedure)
    assert texts.count(NONE_LINE) == 3
    add_external_run(operator_user, procedure, b, {declaration: "cumple"},
                     external_key({"matriz": "local", "verificador": "local"}))
    assert planilla_texts(operator_user, procedure).count(NONE_LINE) == 3
    html = service.build_html(service.collect(operator_user, procedure.pk), "cuadro")
    assert html.count(NONE_LINE) == 1


def test_the_line_adds_up_the_requests_of_each_stage_across_the_offers(
        three, procedure, operator_user):
    """REQ-122: dos ofertas con el verificador externo suman sus pedidos; la matriz externa figura
    aparte, con lo que dice su propia entrada."""
    a, b, _ = three
    open_matrix()
    declaration = requirement(procedure, "declaración jurada")
    both = external_key({"matriz": "externo", "verificador": "externo"})
    both["models_used"]["externo"]["matriz"] = {"modelo": "claude-opus-5-5"}
    both["parameters"]["externo"]["matriz"] = {"modo": "directo"}
    both["counts"]["externo"] = {"matriz": {"pedidos": 3}, "verificador": {"pedidos": 12}}
    add_external_run(operator_user, procedure, a, {declaration: "cumple"}, both)
    add_external_run(operator_user, procedure, b, {declaration: "cumple"},
                     external_key({"matriz": "local", "verificador": "externo"}, requests=5))
    line = service.collect(operator_user, procedure.pk).external_line
    assert line == (
        "Etapas fuera del equipo: matriz de requisitos (anthropic, claude-opus-5-5, modo "
        "directo, 3 pedidos); verificador de citas (anthropic, claude-sonnet-5-5, modo lotes, "
        "17 pedidos).")


@pytest.mark.parametrize("block", [None, "texto", [], {"etapas": None}, {"etapas": "externo"}])
def test_a_malformed_key_reads_as_none(block):
    """REQ-122: una clave `externo` que no tiene la forma esperada no rompe la pantalla ni la
    exportación; se lee como «Ninguna»."""
    run = am.Run(models_used={"externo": block}, parameters={}, counts={})
    assert external_stages.line([run]) == NONE_LINE
