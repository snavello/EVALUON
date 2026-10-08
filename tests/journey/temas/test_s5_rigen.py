"""Tema s5_rigen, normas que rigen al procedimiento y cuáles faltan (REQ-095, REQ-097; plan 014,
T-215). El tema queda listo para registrarse en la sección (la línea de `sections/s5.py` es de
T-214). Todo el material es inventado (P4); no se usa ningún modelo."""

import datetime

import pytest
from django.template.loader import render_to_string
from django.utils import timezone

from evaluon.journey.temas import s5_rigen
from evaluon.norms.models import PendingAmendment, Reading
from evaluon.portal.models import PortalProcedureData
from tests.tenders.conftest import evaluator_user, operator_user  # noqa: F401
from tests.tenders.pdfs import para, tender_pdf
from tests.tenders.scripted import load_and_read, make_procedure

pytestmark = pytest.mark.django_db

AFTER = datetime.date(2024, 5, 20)
BEFORE = datetime.date(2021, 3, 15)


def only(rows, text):
    found = [r for r in rows if text in r.name]
    assert len(found) == 1, [r.name for r in rows]
    return found[0]


@pytest.fixture
def after(operator_user):
    return make_procedure(operator_user, AFTER)


@pytest.fixture
def before(operator_user):
    return make_procedure(operator_user, BEFORE)


def test_a_procedure_authorized_after_the_new_regime_shows_it_and_marks_the_old_one_as_not_applying(
        after, two_regimes):
    """REQ-095: el caso autorizado bajo la 247/2022 muestra las normas que lo rigen y marca la
    297/03 como que no aplica."""
    Reading.objects.filter(document__norm=two_regimes.new).update(
        validated_at=timezone.now())
    rows = s5_rigen.rows(after)
    new = only(rows, "247/2022")
    old = only(rows, "297/03")
    assert new.state == s5_rigen.LOADED and "bajo su vigencia" in new.why
    assert new.version == "versión 1" and new.source.startswith("Archivo · validada ")
    assert old.state == s5_rigen.NOT_APPLICABLE and old.why.startswith("No aplica")
    assert not old.upload_url


def test_a_procedure_authorized_before_shows_the_297(before, two_regimes):
    """REQ-095: un procedimiento anterior a la 247/2022 muestra la 297/03 como la que rige."""
    rows = s5_rigen.rows(before)
    assert only(rows, "297/03").state == s5_rigen.LOADED
    assert only(rows, "247/2022").state == s5_rigen.NOT_APPLICABLE


def test_without_any_regime_loaded_the_one_the_date_fixes_is_missing_with_upload(after, before):
    """REQ-095, REQ-097: sin ninguna norma de régimen cargada, falta la que fija la fecha, con
    «Subir archivo» hacia el ancla de subida; la otra no aplica y no se pide."""
    new = only(s5_rigen.rows(after), "247/2022")
    assert new.state == s5_rigen.MISSING and new.upload_url.endswith("/normativas/#s5-subir")
    old = only(s5_rigen.rows(before), "297/03")
    assert old.state == s5_rigen.MISSING and "antes de la entrada en vigencia" in old.why
    assert only(s5_rigen.rows(before), "247/2022").state == s5_rigen.NOT_APPLICABLE


def test_the_national_framework_is_missing_until_loaded(after, two_regimes, make_norm,
                                                         make_document, make_reading):
    """REQ-095: el marco nacional que no está cargado figura como faltante; el cargado, no."""
    rows = s5_rigen.rows(after)
    assert only(rows, "1023/2001").state == s5_rigen.MISSING
    assert only(rows, "1030/2016").state == s5_rigen.MISSING
    norm = make_norm(category="marco_nacional", norm_type="decreto", number="1023", year=2001,
                     issuer="poder ejecutivo nacional", citation="Decreto 1023/2001")
    make_reading(make_document(norm), [("art-1", "ARTICULO 1.- Marco sintético.")])
    rows = s5_rigen.rows(after)
    assert only(rows, "Decreto 1023/2001").state == s5_rigen.LOADED
    assert only(rows, "1030/2016").state == s5_rigen.MISSING


def test_a_loaded_norm_with_a_pending_reading_is_unvalidated(after, make_norm, make_document,
                                                              make_reading):
    """REQ-095: la norma cargada con la lectura sin validar sale «sin validar», no como faltante."""
    norm = make_norm(norm_type="disposicion", number="247", year=2022, issuer="afip",
                     citation="Disposición AFIP 247/2022", general_regime=True)
    make_reading(make_document(norm), [("art-1", "ARTICULO 1.- Texto sintético.")],
                 status="pending")
    row = only(s5_rigen.rows(after), "247/2022")
    assert row.state == s5_rigen.UNVALIDATED and row.source.startswith("Archivo · subido ")
    assert row.validate_url
    assert all("247/2022" not in m.text for m in s5_rigen.status(None, after).missing)


def test_registered_amendments_not_loaded_are_missing(after, two_regimes):
    """REQ-095: una modificatoria registrada y sin cargar de la norma que rige figura como falta."""
    PendingAmendment.objects.create(
        target_norm=two_regimes.new, norm_type="disposicion", number="500", year=2024,
        issuer="afip", source_ref="nota sintética",
        registered_by=two_regimes.new.created_by)
    row = only(s5_rigen.rows(after), "500/2024")
    assert row.state == s5_rigen.MISSING and "247/2022" in row.why and row.upload_url


def test_norms_cited_by_the_pliego_are_listed_loaded_or_missing(
        after, operator_user, two_regimes, make_norm, make_document, make_reading):
    """REQ-095: la norma que cita el pliego en su encuadre legal y no está cargada falta; la
    cargada se muestra con su estado; la ya listada no se repite."""
    source = load_and_read(operator_user, after,
                           tender_pdf([[para("PLIEGO SINTÉTICO"), para("1. Objeto.")]]),
                           title="Pliego", file_name="pliego.pdf")
    PortalProcedureData.objects.create(
        procedure=after, legal_framework="Disp. 247/22, Resolución N.º 12/2020 y Ley 24.156/1992",
        document=source)
    norm = make_norm(norm_type="resolucion", number="12", year=2020, issuer="organismo sintetico",
                     citation="Resolución 12/2020")
    make_reading(make_document(norm), [("art-1", "ARTICULO 1.- Monto sintético.")])
    rows = s5_rigen.rows(after)
    assert only(rows, "Resolución 12/2020").why == "La cita el pliego (encuadre legal)"
    assert only(rows, "Resolución 12/2020").state == s5_rigen.LOADED
    assert only(rows, "Ley 24156/1992").state == s5_rigen.MISSING
    assert len([r for r in rows if "247" in r.name]) == 1


def test_status_lists_each_missing_norm_with_its_upload_action(after, two_regimes):
    """REQ-097: cada faltante figura con su acción «Subir archivo»; no suma pendientes."""
    result = s5_rigen.status(None, after)
    assert {m.action for m in result.missing} == {"Subir archivo"}
    assert {m.url for m in result.missing} == {s5_rigen.upload_url(after)}
    assert sorted(m.text for m in result.missing) == [
        "Falta cargar Decreto 1023/2001", "Falta cargar Decreto 1030/2016"]
    assert result.pending == 0 and result.sources


def test_the_partial_renders_the_blocks_without_old_texts(after, two_regimes):
    """REQ-095: el parcial muestra norma, por qué rige, estado, origen y acciones; la que no
    aplica, marcada; la que falta, con «Subir archivo»."""
    ctx = s5_rigen.context(None, after, None)
    html = render_to_string(s5_rigen.PARTIAL, {"t": ctx})
    assert "Normas que lo rigen y cuáles faltan" in html
    assert "No aplica: rige solo para autorizaciones anteriores a la 247/2022" in html
    assert "No se necesita para este procedimiento" in html
    assert f'href="{s5_rigen.upload_url(after)}">Subir archivo' in html
    assert "20/05/2024" in html
    assert "ejemplo" not in html.lower() and "ficticia" not in html.lower()
    assert ctx["missing"] == 2 and ctx["loaded"] == 1


# --- Correcciones de la verificación ----------------------------------------------------


def with_framework(text, procedure, user):
    source = load_and_read(user, procedure,
                           tender_pdf([[para("PLIEGO SINTÉTICO"), para("1. Objeto.")]]),
                           title="Pliego", file_name="pliego.pdf")
    PortalProcedureData.objects.create(procedure=procedure, legal_framework=text, document=source)


def test_amendments_of_the_regime_that_does_not_apply_are_not_listed(after, two_regimes):
    """REQ-095: una modificatoria de la 297/03 no figura en un procedimiento de 2024."""
    user = two_regimes.old.created_by
    PendingAmendment.objects.create(
        target_norm=two_regimes.old, norm_type="disposicion", number="77", year=2010,
        issuer="afip", source_ref="nota", registered_by=user)
    PendingAmendment.objects.create(
        target_norm=two_regimes.new, norm_type="disposicion", number="500", year=2024,
        issuer="afip", source_ref="nota", registered_by=user)
    names = [r.name for r in s5_rigen.rows(after)]
    assert not any("77/2010" in n for n in names)
    assert any("500/2024" in n for n in names)
    assert any("Disposición 500/2024" in n for n in names)  # con tilde


def test_loaded_amendments_are_not_listed_as_missing(after, two_regimes, make_norm):
    """REQ-095: una modificatoria ya cargada no figura como faltante."""
    loaded = make_norm(norm_type="disposicion", number="500", year=2024, issuer="afip")
    PendingAmendment.objects.create(
        target_norm=two_regimes.new, norm_type="disposicion", number="500", year=2024,
        issuer="afip", source_ref="nota", registered_by=two_regimes.new.created_by,
        loaded_norm=loaded)
    assert not any("500/2024" in r.name for r in s5_rigen.rows(after))


def test_the_boundary_of_the_new_regime_is_january_2nd_2023(operator_user):
    """REQ-095: 1/1/2023 se rige por la 297/03; 2/1/2023, por la 247/2022."""
    day_before = make_procedure(operator_user, datetime.date(2023, 1, 1))
    day_after = make_procedure(operator_user, datetime.date(2023, 1, 2))
    assert only(s5_rigen.rows(day_before), "297/03").state == s5_rigen.MISSING
    assert only(s5_rigen.rows(day_before), "247/2022").state == s5_rigen.NOT_APPLICABLE
    assert only(s5_rigen.rows(day_after), "247/2022").state == s5_rigen.MISSING
    assert only(s5_rigen.rows(day_after), "297/03").state == s5_rigen.NOT_APPLICABLE


def test_a_framework_decree_cited_by_the_pliego_shows_once(after, operator_user, two_regimes):
    """REQ-095: «Decreto 1023/01» del pliego y el marco «Decreto 1023/2001» son una sola fila."""
    with_framework("Decreto 1023/01 y Decreto Delegado N° 1030/2016", after, operator_user)
    rows = s5_rigen.rows(after)
    assert len([r for r in rows if "1023" in r.name]) == 1
    assert len([r for r in rows if "1030" in r.name]) == 1
    assert only(rows, "1023").why == "Marco nacional · citado por el pliego"
    assert only(rows, "1023").upload_url
    assert len(s5_rigen.status(None, after).missing) == 2


def test_the_reading_link_uses_the_format_of_the_upload_tab(after, make_norm, make_document,
                                                              make_reading):
    """REQ-095: el enlace para validar es `?lectura=<id>#s5-lectura` dentro de la pestaña."""
    norm = make_norm(norm_type="disposicion", number="247", year=2022, issuer="afip",
                     citation="Disposición AFIP 247/2022", general_regime=True)
    reading = make_reading(make_document(norm), [("art-1", "Texto sintético.")], status="pending")
    row = only(s5_rigen.rows(after), "247/2022")
    assert row.validate_url == (f"/expedientes/{after.pk}/normativas/"
                                f"?lectura={reading.pk}#s5-lectura")


@pytest.mark.parametrize("text, expected", [
    ("Decreto Delegado N° 1023/2001", "Decreto 1023/2001"),
    ("Decreto Delegado Nº 1023/01", "Decreto 1023/2001"),
    ("Resolución General N° 4000/2017", "Resolución 4000/2017"),
    ("Res. Gral. 4000/17", "Resolución 4000/2017"),
    ("Disp. AFIP N° 99/2022", "Disposición 99/2022"),
    ("Disposición N° 99/2022 (AFIP)", "Disposición 99/2022"),
    ("Ley N° 24.156", "Ley 24.156"),
    ("Ley 24156", "Ley 24156"),
    ("la Ley N° 24.156/1992", "Ley 24156/1992"),
])
def test_each_form_of_citation_is_recognized(after, operator_user, text, expected):
    """REQ-095: las formas de citar del encuadre legal se reconocen y se muestran normalizadas."""
    with_framework(f"Encuadre: {text}.", after, operator_user)
    names = [c.text for c in s5_rigen._cited(after)]
    assert names == [expected]


def test_what_is_not_recognized_is_not_invented(after, operator_user):
    """REQ-095: sin año (salvo la ley), sin número o con texto suelto no se arma ninguna cita."""
    with_framework("Decreto 1023 y la resolución vigente, Disposición N° 247, régimen general",
                   after, operator_user)
    assert s5_rigen._cited(after) == []


def test_a_law_without_year_is_found_when_loaded(after, operator_user, make_norm, make_document,
                                                   make_reading):
    """REQ-095: una ley citada sin año se reconoce como cargada si hay una ley con ese número."""
    with_framework("Ley N° 24.156", after, operator_user)
    assert only(s5_rigen.rows(after), "Ley 24.156").state == s5_rigen.MISSING
    norm = make_norm(norm_type="ley", number="24156", year=1992, issuer="congreso",
                     citation="Ley 24.156")
    make_reading(make_document(norm), [("art-1", "Texto sintético.")])
    assert only(s5_rigen.rows(after), "Ley 24.156").state == s5_rigen.LOADED
