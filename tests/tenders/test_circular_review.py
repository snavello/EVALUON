"""Pasada de circulares: revisión obligatoria visible ante un cambio sin resolver y las causas de
la aceptación a ciegas (REQ-031; plan 003; T-137, P3).

Los textos son inventados (P4): toman como guía solo la forma de las circulares reales
(renglones numerados, carátula, cronograma de visita, respuestas a consultas). Sin modelo real.
"""

from datetime import date

import pytest

from evaluon.tenders import models as m
from evaluon.tenders.proposal import circular_units as units
from evaluon.tenders.proposal import circulars
from evaluon.tenders.services import matrix_page
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import item, load_and_read, make_procedure
from tests.tenders.test_circular_changes import (  # noqa: F401  (script es una fixture)
    change,
    script,
)
from tests.tenders.test_circulars import (
    add_circular,
    narrative_circular,
    requirement_with,
    row_of_item,
    run_proposal,
)

pytestmark = pytest.mark.django_db

EQUIPO = "El equipo llevará una polea de acero y un cable de seis milímetros."
VISITA_CLAUSE = ("La visita al lugar de entrega es obligatoria y quien no asista queda "
                 "desestimado.")
VISITA_QUOTE = "La visita al lugar de entrega es obligatoria"


def items_case(user, script):
    """Dos renglones con la misma especificación (como el 6 y el 14 de una tabla de precios)."""
    procedure = make_procedure(user)
    load_and_read(user, procedure, tender_pdf([[
        para("SECCIÓN II - ESPECIFICACIONES TÉCNICAS PARTICULARES"),
        para("6. RENGLÓN N° 6 - EQUIPO SINTÉTICO A", f"6.1. {EQUIPO}"),
        para("14. RENGLÓN N° 14 - EQUIPO SINTÉTICO B", f"14.1. {EQUIPO}"),
    ]]))
    script.override(lambda blocks, number, answer: {
        alias: item(technical=[block["items"]]) for alias, block in blocks.items()})
    return procedure


def anomalies_of(run, kind):
    return [a for a in run.anomalies if a["type"] == kind]


def flagged_numbers(user, version):
    page = matrix_page.matrix_page(user, version.pk)
    rows = [r for g in page.groups for r in g.rows] + page.technical
    return {r.requirement.number: r.review_notes for r in rows if r.review_notes}


# --- (1) Un cambio sin resolver deja la marca en las filas que la circular nombra -------------------------


def test_an_unresolved_change_marks_the_named_row_and_not_the_other(operator_user, script):
    """REQ-031, P3: la circular reemplaza algo del renglón 6 que ninguna cita muestra; ni el
    código ni el respaldo lo aplican: la fila del renglón 6 queda "a revisión obligatoria" con
    la circular y su fecha; la del renglón 14 no."""
    procedure = items_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 7", date(2025, 12, 9),
                 "1. En el Renglón N° 6 se reemplaza la balanza de plataforma por una "
                 "balanza de precisión.")
    script.x_when("balanza", [change("reemplaza", "renglon", "6", "la balanza de plataforma",
                                     "una balanza de precisión")])

    version, run = run_proposal(operator_user, procedure)

    (anomaly,) = anomalies_of(run, circulars.ANOMALY_REVIEW_REQUIRED)
    assert anomaly["reason"] == "cambio_sin_resolver" and anomaly["review_required"] is True
    assert anomaly["requirements"] == [row_of_item(version, 6).number]
    assert "Circular N.º 7" in anomaly["circular"] and "09/12/2025" in anomaly["circular"]
    assert not m.RequirementSource.objects.filter(requirement__version=version).exists()
    flagged = flagged_numbers(operator_user, version)
    assert list(flagged) == [row_of_item(version, 6).number]
    assert flagged[row_of_item(version, 6).number][0]["lost"] is True


def test_the_mark_text_says_the_change_could_not_be_applied(operator_user, script):
    """REQ-031, P3: la pantalla y la impresión dicen "A revisión obligatoria" con la circular,
    y el texto es el del cambio no aplicado, no el de una supresión."""
    from evaluon.tenders import export as matrix_export

    procedure = items_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 7", date(2025, 12, 9),
                 "1. En el Renglón N° 6 se reemplaza la balanza de plataforma por una "
                 "balanza de precisión.")
    script.x_when("balanza", [change("reemplaza", "renglon", "6", "la balanza de plataforma",
                                     "una balanza de precisión")])

    version, _ = run_proposal(operator_user, procedure)

    html, _ = matrix_export.render_html(operator_user, version.pk, pdf=False)
    assert html.count("A revisión obligatoria") == 1
    assert "no pudo aplicar su cambio con certeza" in html and "Circular N.º 7" in html
    assert "podría dejar sin efecto" not in html


def test_a_change_the_fallback_applies_leaves_no_mark(operator_user, script):
    """REQ-031: si el respaldo lo aplica a la cita del renglón, no hay nada que revisar."""
    procedure = items_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 7", date(2025, 12, 9),
                 "1. En el Renglón N° 6 se reemplaza la balanza de plataforma por una "
                 "balanza de precisión.")
    script.x_when("balanza", [change("reemplaza", "renglon", "6", "la balanza de plataforma",
                                     "una balanza de precisión")])
    script.c_when("balanza", efectos=[("6.1. El equipo", "modifica", "una balanza de precisión")])

    version, run = run_proposal(operator_user, procedure)

    assert row_of_item(version, 6).sources.get().effect == "modifica"
    assert not anomalies_of(run, circulars.ANOMALY_REVIEW_REQUIRED)[0]["requirements"]
    assert not flagged_numbers(operator_user, version)


def test_an_invalid_extraction_marks_the_rows_the_unit_names(operator_user, script):
    """REQ-031, P3: el modelo devuelve una salida inválida dos veces; la unidad va al respaldo,
    que no encuentra efecto. Las filas de los renglones que nombra quedan a revisión."""
    procedure = items_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 8", date(2025, 12, 10),
                 "1. En los Renglones N° 6 y 14 la precisión de la balanza pasa a ser de "
                 "diez gramos.")
    script.x_when("balanza", "esto no es json", "tampoco")

    version, run = run_proposal(operator_user, procedure)

    (anomaly,) = anomalies_of(run, circulars.ANOMALY_REVIEW_REQUIRED)
    assert anomaly["reason"] == "salida_invalida"
    assert anomaly["requirements"] == sorted([row_of_item(version, 6).number,
                                              row_of_item(version, 14).number])
    assert set(flagged_numbers(operator_user, version)) == set(anomaly["requirements"])


def test_a_retry_that_loses_a_change_marks_the_row_it_did_not_reach(operator_user, script):
    """REQ-031, P3 (caso del reintento que pierde el cambio de un renglón): la primera salida
    es inválida; el reintento trae el cambio del renglón 6 y no el del 14. La fila del 6
    recibe su fuente; la del 14, que la circular nombra, queda a revisión obligatoria."""
    procedure = items_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 8", date(2025, 12, 10),
                 "1. En el Renglón N° 6 el cable pasa a ser de ocho milímetros y en el "
                 "Renglón N° 14 el cable pasa a ser de nueve milímetros.")
    script.x_when("cable pasa", "salida cortada", [
        change("aclara", "renglon", "6", "", "el cable pasa a ser de ocho milímetros")])

    version, run = run_proposal(operator_user, procedure)

    assert {s.text for s in row_of_item(version, 6).sources.all()} == {
        "el cable pasa a ser de ocho milímetros"}
    assert not row_of_item(version, 14).sources.exists()
    (anomaly,) = anomalies_of(run, circulars.ANOMALY_REVIEW_REQUIRED)
    assert anomaly["reason"] == "reintento_pierde_cambios"
    # No se sabe qué cambio se perdió: las dos filas que la unidad nombra quedan a revisión.
    assert anomaly["requirements"] == sorted([row_of_item(version, 6).number,
                                              row_of_item(version, 14).number])


def test_a_retry_that_applies_one_change_to_a_row_and_loses_another_still_marks_it(
        operator_user, script):
    """REQ-031, P3 (D1): el reintento aplica el cambio A a la fila 6 y pierde el B, que nombra
    la misma fila: la fila tiene fuente y queda marcada igual."""
    procedure = items_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 8", date(2025, 12, 10),
                 "1. En el Renglón N° 6 el cable pasa a ser de ocho milímetros. En el "
                 "Renglón N° 6 la balanza pasa a ser digital.")
    script.x_when("cable pasa", "salida cortada", [
        change("aclara", "renglon", "6", "", "el cable pasa a ser de ocho milímetros")])

    version, _ = run_proposal(operator_user, procedure)

    row = row_of_item(version, 6)
    assert row.sources.exists()
    assert list(flagged_numbers(operator_user, version)) == [row.number]


def test_a_tramo_the_model_cannot_dispose_of_marks_the_rows_it_names(operator_user, script,
                                                                     settings):
    """REQ-031, P3: con la extracción apagada, el respaldo devuelve una salida sin forma dos
    veces: el tramo queda pendiente y además las filas que nombra quedan a revisión."""
    settings.CIRCULAR_EXTRACTION_ENABLED = False
    procedure = items_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 9", date(2025, 12, 11),
                 "1. En el Renglón N° 14 la balanza pasa a ser digital.")
    script.raw("balanza pasa", ["no es json", "sigue sin serlo"])

    version, run = run_proposal(operator_user, procedure)

    (anomaly,) = anomalies_of(run, circulars.ANOMALY_REVIEW_REQUIRED)
    assert anomaly["reason"] == "salida_invalida"
    assert anomaly["requirements"] == [row_of_item(version, 14).number]


# --- (2) El encabezado del renglón va al contexto ----------------------------------------------------------


def test_a_change_under_a_renglon_heading_is_not_offered_to_another_renglon(operator_user,
                                                                            script):
    """REQ-031 (caso-03, D7, renglones 6 y 14): el tramo "El cable pasa a ser…" no nombra el
    renglón; el anterior ("En el renglón nro 6…") sí. El respaldo ve el encabezado como
    contexto y solo la cita del renglón 6: la fila del renglón 14, con texto idéntico, no
    recibe fuente."""
    procedure = items_case(operator_user, script)
    load_and_read(operator_user, procedure, narrative_circular(
        "En el renglón nro 6 el equipo se cotiza por servicio.",
        "El cable pasa a ser de ocho milímetros."),
        kind="circular_modificatoria", title="Circular N.º 3", issued_on=date(2025, 12, 2))
    script.c_when("cable pasa", efectos=[("6.1. El equipo", "modifica",
                                          "El cable pasa a ser de ocho milímetros")])

    version, run = run_proposal(operator_user, procedure)

    (request,) = [r for r in script.requests if "cable pasa" in r["tramo"]]
    assert request["cites"] and all(
        body.startswith("Renglón 6, especificaciones técnicas")
        for body in request["cites"].values())
    assert "Renglón del encabezado: En el renglón nro 6" in request["context"]
    assert row_of_item(version, 6).sources.get().effect == "modifica"
    assert not row_of_item(version, 14).sources.exists()


def test_the_extraction_applies_a_bare_change_only_to_the_renglon_of_the_heading(
        operator_user, script):
    """REQ-031: el modelo extrae el cambio sin renglón ("ninguno") con el texto anterior que
    comparten los dos renglones; el código lo aplica solo al renglón del encabezado, sin
    respaldo."""
    procedure = items_case(operator_user, script)
    load_and_read(operator_user, procedure, narrative_circular(
        "En el renglón nro 6 el equipo se cotiza por servicio.",
        "El cable de seis milímetros pasa a ser de ocho milímetros."),
        kind="circular_modificatoria", title="Circular N.º 3", issued_on=date(2025, 12, 2))
    script.x_when("cable de seis", [change("reemplaza", "ninguno", "",
                                           "cable de seis milímetros", "ocho milímetros")])

    version, _ = run_proposal(operator_user, procedure)

    source = row_of_item(version, 6).sources.get()
    assert source.effect == "modifica" and source.step.pass_name == "circulares_cambios"
    assert not row_of_item(version, 14).sources.exists()
    assert not [r for r in script.requests if "cable de seis" in r["tramo"]]


def test_a_tramo_that_names_its_own_renglon_ignores_the_heading(operator_user, script):
    """REQ-031, caso adverso: un tramo que nombra el renglón 14 no hereda el encabezado del 6."""
    procedure = items_case(operator_user, script)
    load_and_read(operator_user, procedure, narrative_circular(
        "En el renglón nro 6 el equipo se cotiza por servicio.",
        "En el renglón 14 el cable pasa a ser de ocho milímetros."),
        kind="circular_modificatoria", title="Circular N.º 3", issued_on=date(2025, 12, 2))
    script.c_when("cable pasa", efectos=[("14.1. El equipo", "modifica", "ocho milímetros")])

    version, _ = run_proposal(operator_user, procedure)

    (request,) = [r for r in script.requests if "cable pasa" in r["tramo"]]
    assert any(body.startswith("Renglón 14,") for body in request["cites"].values())
    assert row_of_item(version, 14).sources.get().effect == "modifica"
    assert not row_of_item(version, 6).sources.exists()


# --- (3) La visita no es dato del trámite y un título de carátula no es una aclaración ------------------


def visit_case(user, script, *, second_clause=False):
    pages = [[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("1. VISITA", f"1.1. {VISITA_CLAUSE}"),
    ]]
    if second_clause:
        pages.append([
            para("SECCIÓN II - OTRAS CONDICIONES"),
            para("3. REPETICIÓN", "3.1. La visita se repite para los oferentes del interior.")])
    procedure = make_procedure(user)
    load_and_read(user, procedure, tender_pdf(pages))
    script.when(VISITA_CLAUSE, item([(VISITA_QUOTE, "formal")]))
    script.when("La visita se repite", item([("La visita se repite para los oferentes",
                                              "formal")]))
    return procedure


CRONOGRAMA = ["II. FECHA DE VISITA", "FECHA: 3 de marzo", "HORA: 9 hs",
              "LUGAR: portería del edificio"]
CARATULA = "LICITACIÓN PÚBLICA N° 99/2099 - ADQUISICIÓN SINTÉTICA DE INSUMOS"


def test_a_visit_schedule_is_not_procedure_data_when_the_tender_has_the_clause(
        operator_user, script):
    """REQ-031 (caso-04, D2): fecha, hora y lugar de la visita precisan la cláusula del pliego
    que la exige: una fuente `modifica` con la lista, en la fila de la visita y en ninguna
    otra. Sin la cláusula, siguen siendo dato del trámite."""
    procedure = visit_case(operator_user, script)
    load_and_read(operator_user, procedure, narrative_circular(*CRONOGRAMA),
                  kind="circular_modificatoria", title="Circular N.º 2",
                  issued_on=date(2025, 12, 1))

    version, run = run_proposal(operator_user, procedure)

    source = requirement_with(version, VISITA_QUOTE).sources.get()
    assert source.effect == "modifica" and "FECHA: 3 de marzo" in source.text
    assert "LUGAR: portería del edificio" in source.text and "II. FECHA" not in source.text
    assert not version.requirements.filter(origin="circular").exists()


def test_a_visit_schedule_without_a_clause_in_the_tender_stays_procedure_data(
        operator_user, script):
    """REQ-031: sin cláusula de visita en el pliego, la lista es dato del trámite (sin
    fuentes ni requisitos), como antes; la fecha de apertura tampoco se toma por visita."""
    procedure = make_procedure(operator_user)
    load_and_read(operator_user, procedure, tender_pdf([[
        para("SECCIÓN I - CONDICIONES PARTICULARES"),
        para("1. PAGO", "1.1. El pago se efectuará a los 90 días corridos de la factura."),
    ]]))
    script.when("El pago se efectuará", item([("El pago se efectuará a los 90 días", "economico")]))
    load_and_read(operator_user, procedure, narrative_circular(*CRONOGRAMA),
                  kind="circular_modificatoria", title="Circular N.º 2",
                  issued_on=date(2025, 12, 1))

    version, _ = run_proposal(operator_user, procedure)

    assert not m.RequirementSource.objects.filter(requirement__version=version).exists()


def test_a_visit_schedule_that_two_clauses_could_fix_goes_to_the_fallback(operator_user,
                                                                          script):
    """REQ-031, caso adverso: si dos cláusulas hablan de la visita no se elige una por el
    código; la lista va al respaldo y, si este no la aplica, las filas que nombra se revisan."""
    procedure = visit_case(operator_user, script, second_clause=True)
    load_and_read(operator_user, procedure, narrative_circular(*CRONOGRAMA),
                  kind="circular_modificatoria", title="Circular N.º 2",
                  issued_on=date(2025, 12, 1))

    version, _ = run_proposal(operator_user, procedure)

    assert not m.RequirementSource.objects.filter(requirement__version=version).exists()
    unit = m.RunStep.objects.filter(pass_name="circulares", request__has_key="unidad",
                                    parsed__resultado="respaldo").get()
    assert unit.parsed["motivo"] == "clave_ambigua"


def test_the_visit_rule_also_applies_to_a_data_change_the_model_extracts(operator_user,
                                                                         script):
    """REQ-031: una unidad que la regla no resuelve (un párrafo suelto con la visita) y que el
    modelo lee como `dato_del_tramite` precisa igual la cláusula de la visita."""
    procedure = visit_case(operator_user, script)
    load_and_read(operator_user, procedure, narrative_circular(
        "Visita: se realizará el 3 de marzo a las 9 hs en la portería del edificio."),
        kind="circular_modificatoria", title="Circular N.º 2", issued_on=date(2025, 12, 1))
    script.x_when("Visita: se realizará", [change("dato_del_tramite")])

    version, _ = run_proposal(operator_user, procedure)

    source = requirement_with(version, VISITA_QUOTE).sources.get()
    assert source.effect == "modifica" and "3 de marzo" in source.text


def test_a_cover_title_is_not_a_clarification_of_the_conditions(operator_user, script):
    """REQ-031 (caso-04, D2: la carátula tomada como aclaración en #193 y #194): el título del
    procedimiento no deja una fuente `aclara`, ni por el respaldo ni por la extracción, y
    queda la anomalía."""
    procedure = visit_case(operator_user, script)
    load_and_read(operator_user, procedure, narrative_circular(CARATULA, *CRONOGRAMA),
                  kind="circular_modificatoria", title="Circular N.º 2",
                  issued_on=date(2025, 12, 1))
    script.c_when("LICITACIÓN PÚBLICA", efectos=[("visita", "aclara", CARATULA)])

    version, run = run_proposal(operator_user, procedure)

    sources = list(m.RequirementSource.objects.filter(requirement__version=version))
    assert [s.effect for s in sources] == ["modifica"]
    assert anomalies_of(run, circulars.ANOMALY_TITLE_NOT_CLARIFICATION)


def test_a_cover_title_extracted_as_a_clarification_is_dropped(operator_user, script):
    """REQ-031: lo mismo si el modelo de extracción lo devuelve como `aclara` de una cláusula."""
    procedure = visit_case(operator_user, script)
    load_and_read(operator_user, procedure, narrative_circular(CARATULA),
                  kind="circular_modificatoria", title="Circular N.º 2",
                  issued_on=date(2025, 12, 1))
    script.x_when("LICITACIÓN PÚBLICA", [change("aclara", "clausula", "1.1", "", CARATULA)])

    version, run = run_proposal(operator_user, procedure)

    assert not m.RequirementSource.objects.filter(requirement__version=version).exists()
    assert anomalies_of(run, circulars.ANOMALY_TITLE_NOT_CLARIFICATION)


@pytest.mark.parametrize("text, expected", [
    (CARATULA, True),
    ("Licitación Pública N° 99/2099 - Adquisición sintética de insumos", True),
    ("La constancia de visita puede emitirla el correo.", False),      # una respuesta
    ("II. SE ACLARA EL PLAZO DE ENTREGA", False),                      # encabezado de apartado
    ("FECHA: 3 de marzo\nHORA: 9 hs", False),                          # varias líneas
    ("Los participantes tendrán que acompañar el comprobante de visita", False),   # minúsculas con verbo
])
def test_what_counts_as_a_cover_title(text, expected):
    """REQ-031: una carátula es una línea sin punto final en mayúsculas o con el nombre del
    procedimiento y su número; una oración de respuesta no lo es."""
    assert units.is_title_text(text) is expected


# --- Verificación de T-137: la marca va por cambio; una exigencia no es un título ----------------------------


def test_a_lost_change_marks_the_row_even_if_another_change_of_the_unit_reached_it(
        operator_user, script):
    """REQ-031, P3 (D1): en una misma unidad un cambio se aplica al renglón 6 y otro, sobre
    el mismo renglón, no se resuelve; la fila del 6 tiene una fuente y queda marcada igual."""
    procedure = items_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 7", date(2025, 12, 9),
                 "1. En el Renglón N° 6 el cable pasa a ser de ocho milímetros. En el "
                 "Renglón N° 6 se reemplaza la balanza de plataforma por una balanza de "
                 "precisión.")
    script.x_when("cable pasa", [
        change("aclara", "renglon", "6", "", "el cable pasa a ser de ocho milímetros"),
        change("reemplaza", "renglon", "6", "la balanza de plataforma",
               "una balanza de precisión")])

    version, run = run_proposal(operator_user, procedure)

    row = row_of_item(version, 6)
    assert row.sources.exists()
    assert list(flagged_numbers(operator_user, version)) == [row.number]


@pytest.mark.parametrize("text", [
    "SE DEBERÁ PRESENTAR MUESTRA DE CADA RENGLÓN",
    "LA GARANTÍA DE OFERTA SERÁ DEL 5% DEL MONTO",
    "Compulsa abreviada N° 3: se exige muestra",
])
def test_an_exigence_is_never_a_cover_title(text):
    """REQ-031, P3 (D2): un texto con marcador de obligación o verbo de exigencia no es título."""
    assert units.is_title_text(text) is False


def test_a_dropped_title_that_names_a_condition_of_the_row_leaves_it_for_review(
        operator_user, script):
    """REQ-031, P3 (D2): si el título descartado habla de la condición de la fila (comparte una
    palabra con ella), la fila queda a revisión obligatoria."""
    procedure = visit_case(operator_user, script)
    title = "LICITACIÓN PÚBLICA N° 99/2099 - VISITA AL LUGAR DE ENTREGA"
    load_and_read(operator_user, procedure, narrative_circular(title),
                  kind="circular_modificatoria", title="Circular N.º 2",
                  issued_on=date(2025, 12, 1))
    script.x_when("LICITACIÓN PÚBLICA", [change("aclara", "clausula", "1.1", "", title)])

    version, _ = run_proposal(operator_user, procedure)

    assert list(flagged_numbers(operator_user, version)) == [
        requirement_with(version, VISITA_QUOTE).number]


def test_a_dropped_title_that_names_no_condition_of_the_row_does_not_mark_it(
        operator_user, script):
    """REQ-031 (ronda 2): un título que no habla de nada de la fila no la marca."""
    procedure = visit_case(operator_user, script)
    load_and_read(operator_user, procedure, narrative_circular(CARATULA),
                  kind="circular_modificatoria", title="Circular N.º 2",
                  issued_on=date(2025, 12, 1))
    script.x_when("LICITACIÓN PÚBLICA", [change("aclara", "clausula", "1.1", "", CARATULA)])

    version, run = run_proposal(operator_user, procedure)

    assert anomalies_of(run, circulars.ANOMALY_TITLE_NOT_CLARIFICATION)
    assert not flagged_numbers(operator_user, version)


# --- Ronda 2: la marca cae donde el cambio perdido apunta ------------------------------------------------------

COTIZAR = ("Cada participante cotizará la totalidad de los renglones y consignará el precio "
           "unitario en pesos.")
COTIZAR_UNA_RAIZ = "El precio de cada renglón incluye los impuestos vigentes."
COTIZAR_SIN_RENGLON = "Cada participante cotizará el precio unitario en pesos."


def pricing_case(user, script):
    """Una cláusula de cotización sin renglón y los renglones 6 y 14."""
    procedure = make_procedure(user)
    load_and_read(user, procedure, tender_pdf([
        [para("SECCIÓN I - CONDICIONES PARTICULARES"), para("1. COTIZACIÓN", f"1.1. {COTIZAR}", f"1.2. {COTIZAR_UNA_RAIZ}",
                                       f"1.3. {COTIZAR_SIN_RENGLON}")],
        [para("SECCIÓN II - ESPECIFICACIONES TÉCNICAS PARTICULARES"),
         para("6. RENGLÓN N° 6 - EQUIPO SINTÉTICO A", f"6.1. {EQUIPO}"),
         para("14. RENGLÓN N° 14 - EQUIPO SINTÉTICO B", f"14.1. {EQUIPO}")],
    ]))
    script.when(COTIZAR, item([(COTIZAR.rstrip("."), "economico")]))
    script.when(COTIZAR_UNA_RAIZ, item([(COTIZAR_UNA_RAIZ.rstrip("."), "economico")]))
    script.when(COTIZAR_SIN_RENGLON, item([(COTIZAR_SIN_RENGLON.rstrip("."), "economico")]))
    script.when("EQUIPO SINTÉTICO", item(technical=["6"]))
    script.override(lambda blocks, number, answer: {
        alias: (item(technical=[block["items"]]) if block["items"] else answer[alias])
        for alias, block in blocks.items()})
    return procedure


def test_a_lost_pricing_change_marks_the_pricing_row_and_only_the_renglon_it_names(
        operator_user, script):
    """REQ-031, P3 (caso-03, D7, M-028): la circular rectifica lo del renglón 6 y pide cotizar
    por servicio; el cambio no se resuelve. Quedan marcadas la fila del renglón 6 y la de la
    cláusula de cotización (nombra los renglones y comparte dos raíces con el cambio), no el
    renglón 14, ni la cita que comparte una sola raíz, ni la que no habla de renglones, aunque
    un renglón anterior del encabezado nombre otros."""
    procedure = pricing_case(operator_user, script)
    load_and_read(operator_user, procedure, narrative_circular(
        "SE MODIFICAN LOS RENGLONES 1 A 20 DE LA TABLA DE PRECIOS:",
        "Se rectifica la circular anterior en lo que respecta al renglón 6, debiendo las "
        "empresas participantes cotizar en este renglón los siguientes servicios y sus "
        "repuestos con precio unitario por servicio, según el siguiente detalle:"),
        kind="circular_modificatoria", title="Circular N.º 5", issued_on=date(2025, 12, 2))
    script.x_when("rectifica la circular", [change(
        "reemplaza", "renglon", "6", "",
        "debiendo las empresas participantes cotizar en este renglón los siguientes "
        "servicios y sus repuestos con precio unitario por servicio")])

    version, _ = run_proposal(operator_user, procedure)

    flagged = set(flagged_numbers(operator_user, version))
    assert flagged == {row_of_item(version, 6).number,
                       requirement_with(version, "cotizará la totalidad").number}


def test_a_bare_change_under_a_long_renglon_heading_goes_only_to_that_renglon(
        operator_user, script):
    """REQ-031 (caso-03, D7, polea y cable): el encabezado nombra el renglón al final de una
    línea larga ("MODIFICAR EL PLIEGO … EN EL RENGLÓN NRO 6:"); el tramo siguiente no nombra
    ninguno y el texto es el mismo en el 6 y en el 14: solo el 6 recibe la fuente."""
    procedure = items_case(operator_user, script)
    load_and_read(operator_user, procedure, narrative_circular(
        "MODIFICAR EL PLIEGO DE BASES Y CONDICIONES PARTICULARES EN EL RENGLÓN NRO 6:",
        "Dentro del título Cable: el cable de seis milímetros modificar por el cable de ocho "
        "milímetros."),
        kind="circular_modificatoria", title="Circular N.º 3", issued_on=date(2025, 12, 2))
    script.x_when("Dentro del título", [change("reemplaza", "ninguno", "",
                                                "el cable de seis milímetros",
                                                "el cable de ocho milímetros")])
    script.c_when("Dentro del título", efectos=[("6.1. El equipo", "modifica",
                                                 "el cable de ocho milímetros")])

    version, _ = run_proposal(operator_user, procedure)

    assert row_of_item(version, 6).sources.exists()
    assert not row_of_item(version, 14).sources.exists()
    # Lo aplica el código por clave, sin que el respaldo vea otros renglones.
    assert not [r for r in script.requests if "Dentro del título" in r["tramo"]]


def test_a_change_that_names_a_renglon_no_candidate_has_marks_nothing_else(operator_user, script):
    """REQ-031, P3 (ronda 2): el cambio perdido nombra el renglón 99, que no existe; otro
    cambio de la misma unidad nombra el 6. Como el cambio perdido sí nombra algo, no se
    recurre a todo lo que nombra la unidad: ninguna fila queda marcada por él."""
    procedure = items_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 7", date(2025, 12, 9),
                 "1. En el Renglón N° 6 el cable pasa a ser de ocho milímetros y en el "
                 "Renglón N° 99 se reemplaza la balanza por otra.")
    script.x_when("cable pasa", [
        change("aclara", "renglon", "6", "", "el cable pasa a ser de ocho milímetros"),
        change("reemplaza", "renglon", "99", "la balanza", "otra")])

    version, run = run_proposal(operator_user, procedure)

    assert anomalies_of(run, circulars.ANOMALY_REVIEW_REQUIRED)
    assert not flagged_numbers(operator_user, version)


def test_a_lost_change_that_names_nothing_marks_what_the_unit_names(operator_user, script):
    """REQ-031, P3 (ronda 2): el cambio perdido no nombra renglón ni cláusula; entonces se
    marcan las filas que nombra la unidad (el renglón 6) y no las de otro renglón."""
    procedure = items_case(operator_user, script)
    add_circular(operator_user, procedure, "Circular N.º 7", date(2025, 12, 9),
                 "1. En el Renglón N° 6 se reemplaza la balanza de plataforma por una "
                 "balanza de precisión.")
    script.x_when("balanza", [change("reemplaza", "ninguno", "", "la balanza de plataforma",
                                     "una balanza de precisión")])

    version, _ = run_proposal(operator_user, procedure)

    assert list(flagged_numbers(operator_user, version)) == [row_of_item(version, 6).number]


def test_a_title_dropped_by_the_fallback_marks_the_row_only_if_it_names_its_condition(
        operator_user, script):
    """REQ-031, P3 (ronda 2): el modelo de respaldo devuelve un título como `aclara`; se
    descarta y la fila se marca solo si el título comparte dos raíces con su condición."""
    procedure = visit_case(operator_user, script)
    sharing = "LICITACIÓN PÚBLICA N° 99/2099 - VISITA AL LUGAR DE ENTREGA"
    load_and_read(operator_user, procedure, narrative_circular(sharing),
                  kind="circular_modificatoria", title="Circular N.º 2",
                  issued_on=date(2025, 12, 1))
    script.c_when("LICITACIÓN PÚBLICA", efectos=[("visita", "aclara", sharing)])

    version, run = run_proposal(operator_user, procedure)

    assert anomalies_of(run, circulars.ANOMALY_TITLE_NOT_CLARIFICATION)
    assert not m.RequirementSource.objects.filter(requirement__version=version).exists()
    assert list(flagged_numbers(operator_user, version)) == [
        requirement_with(version, VISITA_QUOTE).number]


def test_a_title_dropped_by_the_fallback_that_shares_one_root_does_not_mark_the_row(
        operator_user, script):
    """REQ-031 (ronda 2): comparte solo una raíz ("visita") con la condición: no se marca."""
    procedure = visit_case(operator_user, script)
    one_root = "LICITACIÓN PÚBLICA N° 99/2099 - VISITA TÉCNICA DE INSUMOS"
    load_and_read(operator_user, procedure, narrative_circular(one_root),
                  kind="circular_modificatoria", title="Circular N.º 2",
                  issued_on=date(2025, 12, 1))
    script.c_when("LICITACIÓN PÚBLICA", efectos=[("visita", "aclara", one_root)])

    version, run = run_proposal(operator_user, procedure)

    assert anomalies_of(run, circulars.ANOMALY_TITLE_NOT_CLARIFICATION)
    assert not flagged_numbers(operator_user, version)
