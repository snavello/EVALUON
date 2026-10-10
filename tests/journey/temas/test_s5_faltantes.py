"""Pestaña Normativas: lo que falta y lo que no hace falta para el procedimiento, y los nombres de
las modificatorias (REQ-094, REQ-097; plan 014, T-232, puntos N-1 y N-2 de la revisión C). Todo el
material es inventado (P4); no se usa ningún modelo."""

import datetime

import pytest
from django.urls import reverse

from evaluon.audit.models import Channel
from evaluon.journey.sections import s5, sections_for
from evaluon.journey.temas import s5_normas, s5_rigen
from evaluon.norms.models import PendingAmendment
from tests.accounts.test_session import TEST_PASSWORD
from tests.tenders.conftest import evaluator_user, operator_user  # noqa: F401
from tests.tenders.scripted import make_procedure

pytestmark = pytest.mark.django_db

AFTER = datetime.date(2024, 5, 20)
BEFORE = datetime.date(2021, 3, 15)


@pytest.fixture
def after(operator_user):
    return make_procedure(operator_user, AFTER)


@pytest.fixture
def before(operator_user):
    return make_procedure(operator_user, BEFORE)


def register(target, number, year=2010, issuer="administracion federal de ingresos publicos",
             norm_type="disposicion"):
    return PendingAmendment.objects.create(
        target_norm=target, norm_type=norm_type, number=str(number), year=year, issuer=issuer,
        source_ref="nota sintética", registered_by=target.created_by)


@pytest.fixture
def amendments(two_regimes):
    """Una modificatoria sin cargar de la 247/2022 y tres de la 297/03."""
    register(two_regimes.new, 500, 2024)
    for number in (393, 394, 395):
        register(two_regimes.old, number, 2005)
    return two_regimes


def section(user, procedure):
    return sections_for(user, procedure, channel=Channel.SCREEN).get("normativas")


# --- N-1: «Falta» separado de «No hace falta para este procedimiento» -----------------------------


def test_amendments_of_the_regime_that_does_not_apply_are_not_missing(
        after, amendments, evaluator_user):
    """REQ-097: en un procedimiento autorizado bajo la 247/2022, las modificatorias de la 297/03
    no son faltantes: solo cuenta la de la 247/2022."""
    texts = [m.text for m in s5_normas.status(evaluator_user, after).missing]
    assert len(texts) == 1 and "500/2024" in texts[0]
    found = section(evaluator_user, after)
    assert [m.text for m in found.tema_missing if "odificatoria" in m.text] == texts
    summary = " ".join(detail for _, detail in found.summary)
    assert "1 modificatoria sin cargar" in summary
    assert "4 modificatorias" not in summary and "3 modificatorias sin cargar" not in summary


def test_the_summary_says_apart_how_many_are_not_needed(after, amendments, evaluator_user):
    """REQ-097: la línea de la sección dice aparte cuántas modificatorias no hacen falta, y de qué
    norma."""
    summary = " ".join(detail for _, detail in section(evaluator_user, after).summary)
    assert "3 modificatorias de la Disposición AFIP 297/03 no hacen falta para este " \
           "procedimiento" in summary


def test_the_rigen_table_lists_the_ones_not_needed_apart_from_the_missing(
        after, amendments, evaluator_user):
    """REQ-095, REQ-097: la tabla de normas que rigen muestra, aparte de las que faltan, las
    modificatorias que no hacen falta para este procedimiento."""
    context = s5_rigen.context(evaluator_user, after, None)
    assert context["not_needed"] == [
        {"norm": "Disposición AFIP 297/03", "count": 3}]


def test_for_an_older_procedure_the_new_regime_amendments_are_the_ones_not_needed(
        before, amendments, evaluator_user):
    """REQ-097: la regla es simétrica: autorizado bajo la 297/03, las de la 247/2022 no hacen
    falta."""
    texts = [m.text for m in s5_normas.status(evaluator_user, before).missing]
    assert len(texts) == 3 and not any("500/2024" in t for t in texts)
    summary = " ".join(detail for _, detail in section(evaluator_user, before).summary)
    assert "1 modificatoria de la Disposición AFIP 247/2022 no hace falta para este " \
           "procedimiento" in summary


def test_an_amendment_of_any_other_norm_is_still_missing(after, two_regimes, evaluator_user,
                                                         make_norm):
    """REQ-097: lo que no es del otro régimen sigue faltando; no se oculta nada que no se sabe
    que sobra."""
    other = make_norm(norm_type="decreto", number="9", year=2001, issuer="poder ejecutivo",
                      citation="Decreto 9/2001")
    register(other, 77, 2020, issuer="poder ejecutivo nacional", norm_type="decreto")
    texts = [m.text for m in s5_normas.status(evaluator_user, after).missing]
    assert len(texts) == 1 and "77/2020" in texts[0]


def test_the_general_page_still_counts_every_loaded_library_amendment(
        amendments, evaluator_user):
    """REQ-094: sin procedimiento no hay régimen que descartar: la biblioteca común muestra todas
    las modificatorias sin cargar."""
    assert len(s5_normas.status(evaluator_user, None).missing) == 4
    summary = " ".join(d for _, d in s5.summary(evaluator_user, None, ()))
    assert "4 modificatorias sin cargar" in summary
    assert "no hacen falta" not in summary


def test_the_tab_shows_missing_and_not_needed_separately(client, after, amendments,
                                                         evaluator_user):
    """REQ-097: en la pestaña, «Falta» solo lleva las que hacen falta."""
    assert client.login(username=evaluator_user.username, password=TEST_PASSWORD)
    html = client.get(reverse("expedientes:normativas", args=[after.pk])).content.decode()
    falta = html[html.index('<p class="falta">'):]
    falta = falta[:falta.index("</p>")]
    assert "500/2024" in falta and "393/2005" not in falta and "297" not in falta
    assert "no hacen falta para este procedimiento" in html


# --- N-2: nombres de las modificatorias y rótulo del régimen -------------------------------------


def test_amendments_are_named_with_accents_and_capitals(after, amendments, evaluator_user):
    """REQ-097: «Disposición 393/2005 (Administración Federal de Ingresos Públicos)», no
    «disposicion 393/2005 (administracion federal de ingresos publicos)»."""
    rows, _ = s5_normas._norm_rows(evaluator_user)
    names = [name for row in rows for name in row["amendments"]]
    assert "Disposición 393/2005 (Administración Federal de Ingresos Públicos)" in names
    assert not any(name[0].islower() for name in names)
    missing = [m.text for m in s5_normas.status(evaluator_user, None).missing]
    assert any("Disposición 393/2005 (Administración Federal de Ingresos Públicos)" in t
               for t in missing)
    assert not any("disposicion" in t for t in missing)


def test_a_general_regime_is_not_labelled_specific_and_general(amendments, evaluator_user):
    """REQ-097: una norma de régimen general se rotula «Régimen general de contrataciones», no
    «Régimen específico · régimen general»."""
    rows, _ = s5_normas._norm_rows(evaluator_user)
    general = [r for r in rows if r["general"]]
    assert general and all(r["category"] == "Régimen general de contrataciones" for r in general)
    assert not any("Régimen específico" in r["category"] for r in general)


def test_the_tab_does_not_repeat_the_regime_label(client, after, amendments, evaluator_user):
    """REQ-097: en el HTML no aparece «Régimen específico · régimen general»."""
    assert client.login(username=evaluator_user.username, password=TEST_PASSWORD)
    html = client.get(reverse("expedientes:normativas", args=[after.pk])).content.decode()
    assert "Régimen específico · régimen general" not in html
    assert "Régimen general de contrataciones" in html
