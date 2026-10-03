"""Modificatorias sin cargar de una norma (T-051; plan 001, `norms_pending_amendment`,
"Modificatorias sin cargar", "Registro de auditoría" y "Pantalla, acceso y comandos").

`registrar_modificatorias` anota, en lote desde un CSV o de a una, las modificatorias
de una norma que todavía no están cargadas; una ya anotada no se anota otra vez y un
renglón incompleto rechaza el archivo entero. Una modificatoria anotada pasa a cargada
cuando su norma está cargada, con lectura validada y en uso, y tiene una relación
registrada hacia la norma alcanzada, en cualquier orden. `listar_normas` muestra
cuántas quedan sin cargar y cuáles son.

Los datos son sintéticos (P4): el CSV de `tests/fixtures/modificatorias-sinteticas.csv`
y las normas que arman las fábricas de `tests/conftest.py`.
"""

import hashlib
from datetime import date
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import CommandError, call_command

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent
from evaluon.audit.services import current_corpus_version
from evaluon.norms.models import PendingAmendment
from evaluon.norms.services import amendments, listing, relations
from tests.conftest import TEST_PASSWORD

CSV_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "modificatorias-sinteticas.csv"
V = date(2023, 1, 1)


@pytest.fixture
def typed_password(monkeypatch):
    def type_(password=TEST_PASSWORD):
        monkeypatch.setattr(permissions, "read_password", lambda prompt: password)

    return type_


def run(command, *args, **options):
    out = StringIO()
    call_command(command, *args, stdout=out, stderr=StringIO(), **options)
    return out.getvalue()


@pytest.fixture
def target(make_norm, make_document, make_reading):
    """La norma alcanzada, como la 297/03: validada y en uso."""
    norm = make_norm(citation="Disposición sintética 297/03", number="297", year=2003,
                     issuer="afip")
    make_reading(make_document(norm), [("art-1", "ARTICULO 1.- Texto sintético.")])
    return norm


@pytest.fixture
def loaded_norm(make_norm, make_document, make_reading):
    """Fábrica de normas cargadas: `loaded_norm(tipo, número, año, organismo,
    validated=True)`. Con `validated=False`, la lectura queda pendiente y el documento
    fuera de uso, como después de `cargar_norma` y antes de `validar_informe`."""

    def _make(norm_type, number, year, issuer="afip", *, validated=True, **fields):
        norm = make_norm(norm_type=norm_type, number=number, year=year, issuer=issuer,
                         **fields)
        if validated:
            document = make_document(norm)
            make_reading(document, [("art-1", "ARTICULO 1.- Modificación sintética.")])
        else:
            document = make_document(norm, in_use=False, version_number=None)
            make_reading(document, [("art-1", "ARTICULO 1.- Modificación sintética.")],
                         status="pending", passages=False)
        return norm

    return _make


def register_file(user, target_norm, path=CSV_PATH):
    data = Path(path).read_bytes()
    return amendments.register_amendments_file(
        user, target_norm=target_norm.pk, data=data, file_name=Path(path).name
    )


def relate(user, source, target_norm, relation_type="modifica", effective_date=V):
    return relations.register_relation(
        user, relation_type=relation_type, source_norm=source.pk,
        target_norm=target_norm.pk, effective_date=effective_date,
    )


def listed_block(user, citation):
    listed = run("listar_normas", usuario=user.username)
    (block,) = [b for b in listed.split("\n\n") if b.startswith(citation)]
    return block


# --- Anotar modificatorias (REQ-021) ------------------------------------------------


@pytest.mark.django_db
def test_batch_of_three_rows_leaves_three_pending_and_listing_shows_them(
    target, read_write_user, read_user
):
    """REQ-021: la carga en lote de un CSV de tres renglones deja tres modificatorias
    sin cargar, guardadas con los datos normalizados igual que en `norms_norm`, y el
    listado de la norma alcanzada las muestra con su cuenta."""
    result = register_file(read_write_user, target)

    assert len(result.added) == 3
    assert result.already == []
    assert result.pending == 3
    assert amendments.pending_count(target) == 3
    rows = list(
        PendingAmendment.objects.filter(target_norm=target)
        .order_by("number")
        .values_list("norm_type", "number", "year", "issuer", "source_ref",
                     "loaded_norm", "registered_by")
    )
    assert rows == [
        ("disposicion", "9101", 2005, "afip",
         "https://example.org/modificatoria-sintetica-9101", None, read_write_user.pk),
        ("disposicion", "9102", 2007, "afip - subdireccion general sintetica",
         "https://example.org/modificatoria-sintetica-9102", None, read_write_user.pk),
        ("resolucion general", "9103", 2010, "afip",
         "https://example.org/modificatoria-sintetica-9103", None, read_write_user.pk),
    ]

    (item,) = [n for n in listing.list_norms(read_user) if n.id == target.pk]
    assert [(p.norm_type, p.number, p.year, p.issuer, p.source_ref)
            for p in item.pending_amendments] == [r[:5] for r in rows]


@pytest.mark.django_db
def test_repeating_the_batch_does_not_duplicate(target, read_write_user):
    """REQ-021: repetir la carga del mismo archivo no duplica: informa que las tres ya
    estaban y siguen quedando tres sin cargar."""
    register_file(read_write_user, target)

    again = register_file(read_write_user, target)

    assert again.added == []
    assert len(again.already) == 3
    assert again.pending == 3
    assert PendingAmendment.objects.filter(target_norm=target).count() == 3


@pytest.mark.django_db
def test_already_noted_is_reported_and_the_rest_is_noted(target, read_write_user):
    """REQ-021: una modificatoria ya anotada, escrita con otras mayúsculas y tildes, no
    se anota otra vez; las demás del lote sí."""
    amendments.register_amendments(read_write_user, target_norm=target.pk, amendments=[
        {"norm_type": "DISPOSICION", "number": "9101", "year": 2005, "issuer": "Afip",
         "source_ref": "https://example.org/otra-referencia"},
    ])

    result = register_file(read_write_user, target)

    assert [(a["norm_type"], a["number"]) for a in result.already] == [
        ("disposicion", "9101")
    ]
    assert len(result.added) == 2
    assert amendments.pending_count(target) == 3


@pytest.mark.django_db
def test_row_without_number_rejects_the_whole_file(target, read_write_user, tmp_path):
    """REQ-021, REQ-012: un renglón sin número rechaza el archivo entero sin anotar
    ninguna, y el rechazo queda registrado con el renglón y la huella del archivo."""
    text = CSV_PATH.read_text(encoding="utf-8")
    bad = text + "Disposición,,2011,AFIP,https://example.org/modificatoria-sin-numero\n"
    path = tmp_path / "modificatorias-con-error.csv"
    path.write_text(bad, encoding="utf-8")

    with pytest.raises(amendments.InvalidAmendments, match="renglón 5") as error:
        register_file(read_write_user, target, path)

    assert "numero" in str(error.value)
    assert PendingAmendment.objects.count() == 0
    event = AuditEvent.objects.get(event_type="pending_amendment")
    assert (event.outcome, event.user) == ("rejected", read_write_user)
    assert event.detail["reason"] == "invalid_data"
    assert event.detail["file"] == {
        "name": "modificatorias-con-error.csv",
        "sha256": hashlib.sha256(bad.encode("utf-8")).hexdigest(),
    }


@pytest.mark.django_db
@pytest.mark.parametrize("content, expected", [
    ("tipo,numero,anio,organismo\nDisposición,1,2005,AFIP\n", "referencia"),
    ("tipo,numero,anio,organismo,referencia\nDisposición,1,dos mil,AFIP,x\n", "anio"),
    ("tipo,numero,anio,organismo,referencia\n", "no trae ninguna"),
])
def test_file_with_missing_column_bad_year_or_no_rows_is_refused(
    target, read_write_user, content, expected
):
    """REQ-021: un archivo sin la columna `referencia`, con un año que no es un número o
    sin renglones se rechaza sin anotar nada."""
    with pytest.raises(amendments.InvalidAmendments, match=expected):
        amendments.register_amendments_file(
            read_write_user, target_norm=target.pk, data=content.encode("utf-8"),
            file_name="x.csv",
        )
    assert PendingAmendment.objects.count() == 0


@pytest.mark.django_db
def test_missing_target_norm_is_refused(read_write_user):
    """REQ-021: si la norma alcanzada no existe, no se anota nada."""
    with pytest.raises(amendments.NormNotFound, match="999"):
        register_file(read_write_user, type("N", (), {"pk": 999})())
    assert PendingAmendment.objects.count() == 0


@pytest.mark.django_db
def test_read_user_cannot_register(target, read_user):
    """REQ-016, REQ-021: un usuario de lectura no puede anotar modificatorias."""
    with pytest.raises(RoleRejected):
        register_file(read_user, target)
    assert PendingAmendment.objects.count() == 0


# --- Registro de auditoría (REQ-012) ------------------------------------------------


@pytest.mark.django_db
def test_noting_is_recorded_with_its_user_and_a_new_corpus_version(
    target, read_write_user
):
    """REQ-012: la anotación queda en el hecho `pending_amendment` con su usuario, la
    norma alcanzada, cada modificatoria anotada, las que ya estaban, las cargadas en el
    acto, el nombre y la huella del archivo y cuántas quedan; crea una versión nueva de
    la normativa."""
    before = current_corpus_version() or 0  # None si todavía no hay ninguna

    result = register_file(read_write_user, target)

    event = AuditEvent.objects.get(event_type="pending_amendment")
    assert (event.outcome, event.channel, event.user) == ("ok", "command", read_write_user)
    assert result.corpus_version == event.corpus_version == current_corpus_version()
    assert event.corpus_version > before
    detail = event.detail
    assert detail["target_norm"] == target.pk
    assert detail["target_citation"] == "Disposición sintética 297/03"
    assert [a["number"] for a in detail["added"]] == ["9101", "9102", "9103"]
    assert detail["added"][1] == {
        "id": PendingAmendment.objects.get(number="9102").pk,
        "norm_type": "disposicion", "number": "9102", "year": 2007,
        "issuer": "afip - subdireccion general sintetica",
        "source_ref": "https://example.org/modificatoria-sintetica-9102",
    }
    assert detail["already"] == []
    assert detail["loaded"] == []
    assert detail["file"] == {
        "name": "modificatorias-sinteticas.csv",
        "sha256": hashlib.sha256(CSV_PATH.read_bytes()).hexdigest(),
    }
    assert detail["pending"] == 3


@pytest.mark.django_db
def test_closing_is_recorded_in_the_relation_event_with_its_user(
    target, read_write_user, loaded_norm
):
    """REQ-012, REQ-021: el cierre de una modificatoria queda en el hecho `relation`
    con su usuario: cuál quedó cargada, con qué norma, y cuántas quedan."""
    register_file(read_write_user, target)
    source = loaded_norm("disposicion", "9101", 2005)

    result = relate(read_write_user, source, target)

    entry = PendingAmendment.objects.get(number="9101")
    event = AuditEvent.objects.filter(event_type="relation").latest("pk")
    assert (event.outcome, event.user) == ("ok", read_write_user)
    assert event.detail["amendments_loaded"] == [{
        "id": entry.pk, "norm_type": "disposicion", "number": "9101", "year": 2005,
        "issuer": "afip", "loaded_norm": source.pk,
    }]
    assert event.detail["source_in_pending_amendments"] is True
    assert event.detail["pending_amendments"] == 2
    assert [e.pk for e in result.loaded_amendments] == [entry.pk]
    assert result.pending_amendments == 2


# --- Paso a cargada (REQ-021) -------------------------------------------------------


@pytest.mark.django_db
def test_loaded_and_validated_still_counts_until_its_relation(
    target, read_write_user, loaded_norm
):
    """REQ-021: cargada y validada la norma de una modificatoria, sigue contando (aunque
    se vuelva a anotar el lote); registrada su relación hacia la norma alcanzada, deja
    de contar y `loaded_norm` apunta a ella."""
    register_file(read_write_user, target)
    source = loaded_norm("disposicion", "9101", 2005)

    again = register_file(read_write_user, target)
    assert again.loaded == []
    assert amendments.pending_count(target) == 3

    relate(read_write_user, source, target)

    assert amendments.pending_count(target) == 2
    assert PendingAmendment.objects.get(number="9101").loaded_norm == source


@pytest.mark.django_db
def test_relation_first_then_noting_gives_the_same_result(
    target, read_write_user, loaded_norm
):
    """REQ-021: hecho en el otro orden, relación primero y anotación después, la
    modificatoria queda cargada en el acto y la cuenta es la misma."""
    source = loaded_norm("disposicion", "9101", 2005)
    relate(read_write_user, source, target)

    result = register_file(read_write_user, target)

    assert [e.number for e in result.loaded] == ["9101"]
    assert result.pending == 2
    assert amendments.pending_count(target) == 2
    assert PendingAmendment.objects.get(number="9101").loaded_norm == source
    event = AuditEvent.objects.get(event_type="pending_amendment")
    assert [(a["number"], a["loaded_norm"]) for a in event.detail["loaded"]] == [
        ("9101", source.pk)
    ]
    assert event.detail["pending"] == 2


@pytest.mark.django_db
def test_relation_from_a_norm_not_noted_does_not_change_the_count(
    target, read_write_user, loaded_norm
):
    """REQ-021: una relación desde una norma que no está anotada no cambia la cuenta, y
    el hecho `relation` dice que no figura entre las anotadas."""
    register_file(read_write_user, target)
    other = loaded_norm("disposicion", "9999", 2005)

    result = relate(read_write_user, other, target)

    assert result.loaded_amendments == []
    assert result.source_in_pending_amendments is False
    assert amendments.pending_count(target) == 3
    assert PendingAmendment.objects.filter(loaded_norm__isnull=False).count() == 0
    event = AuditEvent.objects.filter(event_type="relation").latest("pk")
    assert event.detail["source_in_pending_amendments"] is False
    assert event.detail["amendments_loaded"] == []
    assert event.detail["pending_amendments"] == 3


@pytest.mark.django_db
def test_relation_from_a_norm_without_validated_reading_does_not_load(
    target, read_write_user, loaded_norm
):
    """REQ-021: una relación desde la norma de una modificatoria cuya lectura todavía
    no está validada ni en uso no la deja cargada."""
    register_file(read_write_user, target)
    source = loaded_norm("disposicion", "9101", 2005, validated=False)

    result = relate(read_write_user, source, target)

    assert result.loaded_amendments == []
    assert result.source_in_pending_amendments is True
    assert amendments.pending_count(target) == 3


@pytest.mark.django_db
def test_relation_toward_another_norm_does_not_load(
    target, read_write_user, loaded_norm, make_norm
):
    """REQ-021: la relación tiene que ser hacia la norma alcanzada: una relación de la
    misma norma hacia otra no deja cargada la modificatoria."""
    register_file(read_write_user, target)
    source = loaded_norm("disposicion", "9101", 2005)
    elsewhere = make_norm(citation="Otra norma sintética")

    relate(read_write_user, source, elsewhere)

    assert amendments.pending_count(target) == 3


@pytest.mark.django_db
def test_issuer_breaks_the_tie_and_is_not_needed_otherwise(
    target, read_write_user, loaded_norm
):
    """REQ-021: la coincidencia es por tipo, número y año; el organismo solo desempata.
    Con dos anotadas de mismo tipo, número y año y distinto organismo, la relación deja
    cargada solo la del organismo de la norma; con una sola anotada, el organismo
    escrito distinto no impide la coincidencia."""
    amendments.register_amendments(read_write_user, target_norm=target.pk, amendments=[
        {"norm_type": "Disposición", "number": "50", "year": 2008,
         "issuer": "AFIP - Dirección Sintética A", "source_ref": "https://example.org/a"},
        {"norm_type": "Disposición", "number": "50", "year": 2008,
         "issuer": "AFIP - Dirección Sintética B", "source_ref": "https://example.org/b"},
        {"norm_type": "Disposición", "number": "60", "year": 2009,
         "issuer": "Administración Federal sintética", "source_ref": "https://example.org/c"},
    ])
    tie = loaded_norm("disposicion", "50", 2008, "afip - direccion sintetica b")
    single = loaded_norm("disposicion", "60", 2009, "afip")

    relate(read_write_user, tie, target)
    relate(read_write_user, single, target)

    loaded = dict(
        PendingAmendment.objects.values_list("source_ref", "loaded_norm")
    )
    assert loaded == {
        "https://example.org/a": None,
        "https://example.org/b": tie.pk,
        "https://example.org/c": single.pk,
    }
    assert amendments.pending_count(target) == 1


@pytest.mark.django_db
def test_pending_count_accepts_a_norm_or_its_id_and_ignores_other_norms(
    target, read_write_user, make_norm, make_pending_amendment
):
    """REQ-021: la cuenta para el aviso es la de filas sin `loaded_norm` de esa norma,
    con la norma o su número."""
    other = make_norm()
    make_pending_amendment(other)
    make_pending_amendment(target)
    make_pending_amendment(target, loaded_norm=other)

    assert amendments.pending_count(target) == 1
    assert amendments.pending_count(target.pk) == 1
    assert amendments.pending_count(other) == 1


# --- Comandos ------------------------------------------------------------------------


@pytest.mark.django_db
def test_registrar_modificatorias_batch_and_listar_normas(
    target, read_write_user, read_user, typed_password
):
    """REQ-021: `registrar_modificatorias --archivo` informa cuántas anotó, cuántas ya
    estaban y cuántas quedan; `listar_normas` muestra la cuenta y cuáles son."""
    typed_password()

    out = run("registrar_modificatorias", alcanzada=target.pk, archivo=str(CSV_PATH),
              usuario=read_write_user.username)

    assert "Se anotaron 3 modificatorias sin cargar" in out
    assert "Ya estaban anotadas: 0." in out
    assert "Quedan 3 modificatorias sin cargar de la Disposición sintética 297/03." in out
    assert f"versión {current_corpus_version()} de la normativa" in out

    again = run("registrar_modificatorias", alcanzada=target.pk, archivo=str(CSV_PATH),
                usuario=read_write_user.username)
    assert "Se anotaron 0 modificatorias sin cargar" in again
    assert "Ya estaban anotadas: 3." in again
    assert "ya estaba anotada" in again

    block = listed_block(read_user, "Disposición sintética 297/03")
    assert "Modificatorias sin cargar: 3" in block
    assert ("disposicion 9102/2007 · organismo: afip - subdireccion general sintetica · "
            "referencia: https://example.org/modificatoria-sintetica-9102") in block


@pytest.mark.django_db
def test_registrar_modificatorias_one_at_a_time(target, read_write_user, typed_password):
    """REQ-021: `registrar_modificatorias` anota una sola modificatoria con `--tipo`,
    `--numero`, `--anio`, `--organismo` y `--referencia`."""
    typed_password()

    out = run("registrar_modificatorias", alcanzada=target.pk, tipo="Disposición",
              numero="12", anio="2004", organismo="AFIP",
              referencia="https://example.org/una", usuario=read_write_user.username)

    assert "Se anotaron 1 modificatorias sin cargar" in out
    entry = PendingAmendment.objects.get()
    assert (entry.norm_type, entry.number, entry.year, entry.issuer) == (
        "disposicion", "12", 2004, "afip"
    )
    event = AuditEvent.objects.get(event_type="pending_amendment")
    assert event.detail["file"] is None


@pytest.mark.django_db
def test_registrar_modificatorias_reports_refusals(
    target, read_write_user, read_user, typed_password, tmp_path
):
    """REQ-016, REQ-021: el comando informa en lenguaje llano un renglón incompleto, la
    falta de datos, la mezcla de archivo y datos sueltos y un usuario de lectura, y no
    anota nada."""
    typed_password()
    bad = tmp_path / "malo.csv"
    bad.write_text("tipo,numero,anio,organismo,referencia\nDisposición,,2005,AFIP,x\n",
                   encoding="utf-8")

    with pytest.raises(CommandError, match="renglón 2"):
        run("registrar_modificatorias", alcanzada=target.pk, archivo=str(bad),
            usuario=read_write_user.username)
    with pytest.raises(CommandError, match="--archivo"):
        run("registrar_modificatorias", alcanzada=target.pk,
            usuario=read_write_user.username)
    with pytest.raises(CommandError, match="--archivo"):
        run("registrar_modificatorias", alcanzada=target.pk, archivo=str(CSV_PATH),
            tipo="Disposición", usuario=read_write_user.username)
    with pytest.raises(CommandError, match="falta"):
        run("registrar_modificatorias", alcanzada=target.pk, tipo="Disposición",
            numero="12", anio="2004", organismo="AFIP",
            usuario=read_write_user.username)
    with pytest.raises(CommandError, match="permiso"):
        run("registrar_modificatorias", alcanzada=target.pk, archivo=str(CSV_PATH),
            usuario=read_user.username)
    assert PendingAmendment.objects.count() == 0


@pytest.mark.django_db
def test_registrar_relacion_reports_the_loaded_amendment_and_how_many_remain(
    target, read_write_user, loaded_norm, typed_password
):
    """REQ-021: `registrar_relacion` informa que la relación dejó cargada una
    modificatoria y cuántas quedan; con una norma que no está anotada, lo dice."""
    typed_password()
    register_file(read_write_user, target)
    source = loaded_norm("disposicion", "9101", 2005, citation="Disposición sintética 9101/05")
    other = loaded_norm("disposicion", "9999", 2005, citation="Disposición sintética 9999/05")

    out = run("registrar_relacion", tipo="modifica", origen=source.pk,
              alcanzada=target.pk, fecha="2023-01-01", usuario=read_write_user.username)
    assert ("La Disposición sintética 9101/05 quedó cargada como modificatoria de la "
            "Disposición sintética 297/03.") in out
    assert "Quedan 2 modificatorias sin cargar de la Disposición sintética 297/03." in out

    out = run("registrar_relacion", tipo="complementa", origen=other.pk,
              alcanzada=target.pk, fecha="2023-01-01", usuario=read_write_user.username)
    assert ("La Disposición sintética 9999/05 no figura entre las modificatorias sin "
            "cargar anotadas de la Disposición sintética 297/03.") in out
    assert "Quedan 2 modificatorias sin cargar" in out


@pytest.mark.django_db
def test_listar_normas_without_pending_amendments(target, read_user, typed_password):
    """REQ-021: una norma sin modificatorias sin cargar lo dice en el listado."""
    typed_password()

    block = listed_block(read_user, "Disposición sintética 297/03")

    assert "Modificatorias sin cargar: ninguna" in block


# --- Fecha de fin en el listado ------------------------------------------------------


@pytest.mark.django_db
def test_listar_normas_shows_the_last_day_of_a_closed_version(
    make_norm, make_document, read_user, typed_password
):
    """REQ-007: `effective_to` es exclusiva (T-009): una versión cerrada con
    `effective_to` 01/03/2024 rige hasta el 29/02/2024, y así lo muestra
    `listar_normas`, igual que `registrar_version`."""
    typed_password()
    norm = make_norm(citation="Norma sintética con dos versiones")
    make_document(norm, effective_from=date(2020, 1, 1), effective_to=date(2024, 3, 1),
                  in_use=True, version_number=1, file_name="version-1.pdf")
    make_document(norm, effective_from=date(2024, 3, 1), in_use=True,
                  version_number=2, file_name="version-2.pdf")

    block = listed_block(read_user, "Norma sintética con dos versiones")

    assert "Vigente desde 01/01/2020 hasta 29/02/2024" in block
    assert "hasta 01/03/2024" not in block
    assert "Vigente desde 01/03/2024\n" in block + "\n"
