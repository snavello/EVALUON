"""AFIP y ARCA son el mismo organismo (T-057; ADR-0010).

Donde el sistema compara por organismo, "AFIP" y "ARCA", con sigla o con nombre largo,
valen lo mismo: la identidad de una norma al cargarla y la de una modificatoria anotada,
también en el desempate por organismo. Ninguna norma cambia su nombre de cita.

Los datos son sintéticos (P4), salvo el extracto público del anexo de la Disposición
AFIP 247/2022 que ya usa `test_loading.py`.
"""

from datetime import date

import pytest

from evaluon.norms.models import Norm, PendingAmendment
from evaluon.norms.services import amendments, loading, relations, validation
from tests.norms.test_loading import DATA_247, load, pages_five_and_six_pdf

V = date(2023, 1, 1)


@pytest.mark.parametrize("issuer", [
    "AFIP",
    "afip",
    "ARCA",
    " Arca ",
    "Administración Federal de Ingresos Públicos",
    "ADMINISTRACION FEDERAL DE INGRESOS PUBLICOS",
    "Agencia de Recaudación y Control Aduanero",
    "AGENCIA  DE RECAUDACION Y CONTROL ADUANERO",
])
def test_afip_and_arca_normalize_to_the_same_issuer(issuer):
    """REQ-001: al normalizar el organismo emisor, la sigla y el nombre largo de AFIP y
    de ARCA dan la misma forma, la de AFIP, que es la que ya tienen las normas
    cargadas."""
    assert loading.normalize_identity(issuer) == "afip"


@pytest.mark.parametrize("value, expected", [
    ("Disposición", "disposicion"),
    ("AFIP - Dirección Sintética A", "afip - direccion sintetica a"),
    ("Dirección Regional Centro (AFIP-DGI)", "direccion regional centro (afip-dgi)"),
    ("Ministerio de Economía", "ministerio de economia"),
    ("Arcadia", "arcadia"),
])
def test_other_values_are_normalized_as_before(value, expected):
    """REQ-001: la equivalencia vale solo para el organismo entero: una dependencia de la
    AFIP, otro organismo y los demás datos se normalizan como antes."""
    assert loading.normalize_identity(value) == expected


@pytest.mark.django_db
def test_part_loaded_as_arca_joins_the_norm_loaded_as_afip(read_write_user):
    """REQ-001: una parte cargada con organismo "ARCA" se suma a la norma ya cargada
    como AFIP con el mismo tipo, número y año, sin dar de alta otra norma, y la norma
    conserva su nombre de cita."""
    first = load(read_write_user)
    second = load(read_write_user, data=pages_five_and_six_pdf(),
                  file_name="disp-247-2022-anexo-ii.pdf", part="anexo-ii",
                  issuer="Agencia de Recaudación y Control Aduanero", citation="")

    assert second.document.norm_id == first.document.norm_id
    assert Norm.objects.count() == 1
    norm = Norm.objects.get()
    assert norm.citation == DATA_247["citation"] == "Disposición AFIP 247/2022"
    assert norm.issuer == "afip"


@pytest.mark.django_db
def test_new_norm_dictated_as_arca_keeps_its_citation(read_write_user):
    """REQ-001: una norma nueva dictada como ARCA se carga con su nombre de cita
    oficial, con "ARCA": la equivalencia no renombra nada."""
    result = load(read_write_user, number="9057", year=2025,
                  citation="Disposición ARCA 9057/2025", issuer="ARCA")

    assert result.document.norm.citation == "Disposición ARCA 9057/2025"


# --- Modificatorias sin cargar (REQ-021) -----------------------------------------------


@pytest.fixture
def target(make_norm, make_document, make_reading):
    """La norma alcanzada, como la 297/03: validada y en uso, organismo AFIP."""
    norm = make_norm(citation="Disposición sintética 297/03", number="297", year=2003,
                     issuer="afip")
    make_reading(make_document(norm), [("art-1", "ARTICULO 1.- Texto sintético.")])
    return norm


def note(user, target_norm, *rows):
    return amendments.register_amendments(user, target_norm=target_norm.pk, amendments=[
        {"norm_type": norm_type, "number": number, "year": year, "issuer": issuer,
         "source_ref": ref}
        for norm_type, number, year, issuer, ref in rows
    ])


def relate(user, source, target_norm):
    return relations.register_relation(
        user, relation_type="modifica", source_norm=source.pk,
        target_norm=target_norm.pk, effective_date=V,
    )


@pytest.mark.django_db
def test_amendment_noted_as_arca_is_loaded_when_the_afip_norm_is_validated(
    target, read_write_user, make_norm, make_document, make_reading, fake_embeddings
):
    """REQ-021: una modificatoria anotada con organismo ARCA pasa a cargada al validar
    una norma cargada como AFIP con el mismo tipo, número y año, aun cuando el organismo
    tiene que desempatar entre dos anotadas."""
    note(read_write_user, target,
         ("Disposición", "70", 2024, "ARCA", "https://example.org/arca"),
         ("Disposición", "70", 2024, "AFIP - Dirección Sintética",
          "https://example.org/dependencia"))
    source = make_norm(norm_type="disposicion", number="70", year=2024, issuer="afip")
    document = make_document(source, in_use=False, version_number=None)
    reading = make_reading(document, [("art-1", "ARTICULO 1.- Modificación sintética.")],
                           status="pending", passages=False)
    relate(read_write_user, source, target)
    assert amendments.pending_count(target) == 2

    validation.validate_reading(read_write_user, reading.pk)

    loaded = dict(PendingAmendment.objects.values_list("source_ref", "loaded_norm"))
    assert loaded == {"https://example.org/arca": source.pk,
                      "https://example.org/dependencia": None}
    assert Norm.objects.get(pk=source.pk).citation == source.citation


@pytest.mark.django_db
def test_issuer_tie_is_broken_with_afip_and_arca_as_the_same(
    target, read_write_user, make_norm, make_document, make_reading
):
    """REQ-021: con dos normas de mismo tipo, número y año, la modificatoria anotada con
    el nombre largo de la AFIP queda cargada con la norma registrada como "arca" (así
    puede estar guardada una norma anterior a esta tarea), y no con la otra, cuando las
    dos ya tienen su relación hacia la norma alcanzada."""
    arca = make_norm(norm_type="disposicion", number="80", year=2024, issuer="arca")
    other = make_norm(norm_type="disposicion", number="80", year=2024,
                      issuer="ministerio sintetico")
    for norm in (arca, other):
        make_reading(make_document(norm), [("art-1", "ARTICULO 1.- Sintético.")])
        relate(read_write_user, norm, target)

    note(read_write_user, target,
         ("Disposición", "80", 2024, "Administración Federal de Ingresos Públicos",
          "https://example.org/afip"))

    entry = PendingAmendment.objects.get()
    assert entry.loaded_norm == arca
    assert amendments.matching_entry(target, arca) == entry


@pytest.mark.django_db
def test_amendment_noted_as_afip_and_as_arca_is_noted_once(target, read_write_user):
    """REQ-021: una modificatoria ya anotada como AFIP no se anota otra vez como ARCA:
    se informa como ya anotada."""
    note(read_write_user, target,
         ("Disposición", "90", 2024, "AFIP", "https://example.org/afip"))
    result = note(read_write_user, target,
                  ("Disposición", "90", 2024, "ARCA", "https://example.org/arca"))

    assert result.added == []
    assert len(result.already) == 1
    assert amendments.pending_count(target) == 1


@pytest.mark.django_db
def test_noting_again_rows_stored_with_the_long_name_reports_them_as_already_noted(
    target, read_write_user
):
    """REQ-021: si una modificatoria quedó guardada con el nombre largo de la AFIP tal
    cual (anotada antes de la equivalencia), volver a anotarla, con ese nombre o con
    "ARCA", la informa como ya anotada y no la duplica."""
    note(read_write_user, target,
         ("Disposición", "95", 2024, "AFIP", "https://example.org/larga"))
    PendingAmendment.objects.update(
        issuer="administracion federal de ingresos publicos")

    for issuer in ("ADMINISTRACION FEDERAL DE INGRESOS PUBLICOS", "ARCA"):
        result = note(read_write_user, target,
                      ("Disposición", "95", 2024, issuer, "https://example.org/larga"))
        assert result.added == []
        assert len(result.already) == 1
    assert PendingAmendment.objects.count() == 1
    assert amendments.pending_count(target) == 1


@pytest.mark.django_db
@pytest.mark.parametrize("stored", ["arca", "administracion federal de ingresos publicos"])
def test_norm_stored_with_arca_or_the_long_name_is_recognized_when_loading(
    read_write_user, stored
):
    """REQ-001: una norma guardada con organismo "arca" o con el nombre largo (antes de
    la equivalencia) se reconoce al cargarle otra parte como AFIP: no se da de alta otra
    norma y conserva su nombre de cita."""
    first = load(read_write_user)
    Norm.objects.update(issuer=stored)

    second = load(read_write_user, data=pages_five_and_six_pdf(),
                  file_name="disp-247-2022-anexo-ii.pdf", part="anexo-ii", citation="")

    assert second.document.norm_id == first.document.norm_id
    assert Norm.objects.count() == 1
    assert Norm.objects.get().citation == "Disposición AFIP 247/2022"
