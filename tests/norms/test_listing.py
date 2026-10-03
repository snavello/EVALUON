"""Listado de normas e informe de lectura (T-014; plan 001, "Pantalla, acceso y
comandos": `listar_normas` y `ver_informe`).

Las normas se cargan con la función de carga a partir del extracto del anexo de la
Disposición AFIP 247/2022 (`tests/fixtures/disp-247-2022-anexo-extracto.pdf`, T-012),
documento público (P4). El segundo documento son las páginas 5 y 6 del extracto,
armadas en memoria.
"""

import hashlib
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.norms.services import listing, validation
from tests.conftest import TEST_PASSWORD
from tests.norms.test_loading import DATA_247, load, pages_five_and_six_pdf


@pytest.fixture
def typed_password(monkeypatch):
    def type_(password=TEST_PASSWORD):
        monkeypatch.setattr(permissions, "read_password", lambda prompt: password)

    return type_


def run(command, *args, **options):
    out = StringIO()
    call_command(command, *args, stdout=out, stderr=StringIO(), **options)
    return out.getvalue()


# --- Función de listado --------------------------------------------------------------


@pytest.mark.django_db
def test_listing_shows_the_norm_with_all_its_data(read_write_user, read_user):
    """REQ-001, REQ-017, REQ-020: cargada una norma con sus datos, el listado la muestra
    con todos ellos: categoría, tipo, número, año, organismo, título, nombre de cita,
    marca de régimen general, y su documento con la parte, las fechas de publicación y
    de vigencia, la fuente y el estado de validación."""
    result = load(read_write_user)

    norms = listing.list_norms(read_user)

    assert len(norms) == 1
    norm = norms[0]
    assert norm.id == result.norm.pk
    assert (norm.category, norm.norm_type, norm.number, norm.year, norm.issuer) == (
        "regimen_especifico", "disposicion", "247", 2022, "afip"
    )
    assert norm.title == DATA_247["title"]
    assert norm.citation == "Disposición AFIP 247/2022"
    assert norm.general_regime is True
    (document,) = norm.documents
    assert document.id == result.document.pk
    assert document.part == "anexo"
    assert document.publication_date == DATA_247["publication_date"]
    assert document.effective_from == DATA_247["effective_from"]
    assert document.effective_to is None
    assert document.source == DATA_247["source"]
    assert document.file_name == "disp-247-2022-anexo-extracto.pdf"
    assert (document.in_use, document.version_number) == (False, None)
    assert document.reading_id == result.reading.pk
    assert document.reading_status == "pending"


@pytest.mark.django_db
def test_listing_shows_both_parts_under_one_norm(read_write_user, read_user):
    """REQ-020: el cuerpo y el anexo de una norma figuran bajo la misma norma, cada uno
    con su parte."""
    load(read_write_user)
    load(read_write_user, data=pages_five_and_six_pdf(), file_name="paginas-5-y-6.pdf",
         part="cuerpo",
         citation=None)

    (norm,) = listing.list_norms(read_user)

    assert [d.part for d in norm.documents] == ["cuerpo", "anexo"]


@pytest.mark.django_db
def test_listing_shows_validation_state(read_write_user, read_user, fake_embeddings):
    """REQ-001: el listado muestra el estado de validación de cada documento: validado,
    en uso y con su versión."""
    result = load(read_write_user)
    validation.validate_reading(read_write_user, result.reading.pk)

    (norm,) = listing.list_norms(read_user)

    (document,) = norm.documents
    assert document.reading_status == "validated"
    assert (document.in_use, document.version_number) == (True, 1)


@pytest.mark.django_db
def test_listing_requires_a_user_with_a_role(db):
    """REQ-016: sin usuario no se lista."""
    with pytest.raises(RoleRejected):
        listing.list_norms(None)


@pytest.mark.django_db
def test_report_is_the_text_that_validation_fingerprints(read_write_user, read_user):
    """REQ-004: el informe que se muestra es exactamente el texto guardado, el mismo
    cuya huella guarda la validación."""
    result = load(read_write_user)

    report = listing.reading_report(read_user, result.reading.pk)

    assert report.report_text == result.reading.report_text
    summary = validation.reading_summary(read_write_user, result.reading.pk)
    assert report.report_sha256 == summary["report_sha256"]
    assert report.citation == "Disposición AFIP 247/2022"
    assert report.part == "anexo"


@pytest.mark.django_db
def test_report_of_missing_reading_is_refused(read_user):
    """REQ-004: pedir el informe de una lectura que no existe lo dice en lenguaje
    llano."""
    with pytest.raises(listing.ReadingNotFound, match="No existe la lectura 999"):
        listing.reading_report(read_user, 999)


# --- Comandos ------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["read_user", "read_write_user"])
def test_listar_normas_shows_all_data_for_both_roles(
    request, role, read_write_user, typed_password
):
    """REQ-001, REQ-020: `listar_normas`, para los dos roles, muestra la norma con
    todos sus datos, la marca de régimen general con su fecha de vigencia y el
    documento con su parte y su estado de validación."""
    result = load(read_write_user)
    user = request.getfixturevalue(role)
    typed_password()

    out = run("listar_normas", usuario=user.username)

    for expected in (
        "Disposición AFIP 247/2022",
        DATA_247["title"],
        "Régimen específico",
        "Régimen general: sí",
        "disposicion",
        "247",
        "2022",
        "afip",
        "Parte anexo",
        "Publicada el 30/11/2022",
        "Vigente desde 01/01/2023",
        DATA_247["source"],
        f"Lectura {result.reading.pk}",
        "pendiente de validación",
    ):
        assert expected in out


@pytest.mark.django_db
def test_listar_normas_without_norms(read_user, typed_password):
    """REQ-001: sin normas cargadas, el listado lo dice."""
    typed_password()

    assert "No hay normas cargadas." in run("listar_normas", usuario=read_user.username)


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["read_user", "read_write_user"])
def test_ver_informe_shows_the_exact_report_with_unit_keys(
    request, role, read_write_user, typed_password
):
    """REQ-004, REQ-020: `ver_informe`, para los dos roles, muestra el informe tal como
    está guardado, con la lista de unidades y sus claves `anexo/art-N`, y la huella que
    después muestra `validar_informe`."""
    result = load(read_write_user)
    user = request.getfixturevalue(role)
    typed_password()

    out = run("ver_informe", str(result.reading.pk), usuario=user.username)

    report_text = result.reading.report_text
    assert out.endswith(report_text)
    assert "Disposición AFIP 247/2022" in out
    assert "anexo/art-1" in out
    sha = hashlib.sha256(report_text.encode("utf-8")).hexdigest()
    assert f"Huella del informe: {sha}" in out


@pytest.mark.django_db
def test_ver_informe_of_missing_reading(read_user, typed_password):
    """REQ-004: `ver_informe` con una lectura inexistente lo dice y termina con
    error."""
    typed_password()

    with pytest.raises(CommandError, match="No existe la lectura 999"):
        run("ver_informe", "999", usuario=read_user.username)


@pytest.mark.django_db
def test_commands_reject_wrong_password(read_user, typed_password):
    """REQ-016: con una clave incorrecta, `listar_normas` y `ver_informe` dan el
    mensaje único."""
    typed_password("clave-equivocada-sintetica")

    with pytest.raises(CommandError, match=permissions.LOGIN_FAILED_MESSAGE):
        run("listar_normas", usuario=read_user.username)
    with pytest.raises(CommandError, match=permissions.LOGIN_FAILED_MESSAGE):
        run("ver_informe", "1", usuario=read_user.username)
