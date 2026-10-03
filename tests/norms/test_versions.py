"""Versiones de una norma (T-030; plan 001, "Versiones de una norma", "Unidades
consultables a una fecha" y "Registro de auditoría").

`registrar_version` deja un documento validado como versión siguiente de su parte de la
norma, o como el archivo en uso de una versión existente de esa parte. Los documentos se
arman como los deja la validación: el primero de cada parte, versión 1 y en uso; los
siguientes de la misma parte, validados, sin versión y fuera de uso. Los datos son
sintéticos (P4).
"""

from datetime import date
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.db import connection

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit import services as audit_services
from evaluon.audit.models import AuditEvent
from evaluon.audit.services import current_corpus_version
from evaluon.norms.models import CorpusVersion, Document
from evaluon.norms.services import versions
from tests.conftest import TEST_PASSWORD

V1_FROM = date(2010, 3, 1)
V2_FROM = date(2015, 7, 1)
V3_FROM = date(2020, 1, 1)


def consultable_ids(reference_date):
    with connection.cursor() as cursor:
        cursor.execute("SELECT unit_id FROM consultable_units(%s)", [reference_date])
        return {row[0] for row in cursor.fetchall()}


def unit_ids(reading):
    return {u.pk for u in reading.units_by_key.values()}


@pytest.fixture
def first_version(make_document, make_reading):
    """El primer documento validado de una parte: versión 1 y en uso, vigente desde
    `effective_from`. `first_version(norma, unidades, part="cuerpo",
    effective_from=V1_FROM)` devuelve la lectura."""

    def _make(norm, units, part="cuerpo", effective_from=V1_FROM):
        document = make_document(norm, part=part, effective_from=effective_from,
                                 version_number=1, in_use=True)
        return make_reading(document, units)

    return _make


@pytest.fixture
def validated_unregistered(make_document, make_reading):
    """Otro documento de la misma parte, validado y todavía sin registrar como versión:
    fuera de uso y sin número de versión. `validated_unregistered(norma, unidades,
    part="cuerpo", effective_from=V2_FROM, status="validated")` devuelve la lectura."""

    def _make(norm, units, part="cuerpo", effective_from=V2_FROM, status="validated"):
        document = make_document(norm, part=part, effective_from=effective_from,
                                 version_number=None, in_use=False)
        return make_reading(document, units, status=status)

    return _make


V1_UNITS = [("art-1", "ARTICULO 1.- Texto sintético original del artículo uno.")]
V2_UNITS = [("art-1", "ARTICULO 1.- Texto sintético rectificado del artículo uno.")]
V3_UNITS = [("art-1", "ARTICULO 1.- Texto sintético de la tercera versión.")]
ANNEX_V1 = [("anexo", "ANEXO"), ("anexo/art-1", "ARTÍCULO 1°.- Anexo sintético original.")]
ANNEX_V2 = [("anexo", "ANEXO"), ("anexo/art-1", "ARTÍCULO 1°.- Anexo sintético rectificado.")]


def refreshed(reading):
    document = Document.objects.get(pk=reading.document_id)
    return document


# --- Versión nueva --------------------------------------------------------------------


@pytest.mark.django_db
def test_two_versions_each_date_returns_its_own(
    make_norm, first_version, validated_unregistered, read_write_user
):
    """REQ-007: con dos versiones de una norma, `consultable_units` devuelve para cada
    fecha las unidades de la suya: antes de la vigencia de la segunda, las de la
    primera; desde ese día, las de la segunda."""
    norm = make_norm()
    v1 = first_version(norm, V1_UNITS)
    v2 = validated_unregistered(norm, V2_UNITS)

    versions.register_version(read_write_user, v2.document_id)

    before = consultable_ids(date(2015, 6, 30))
    assert unit_ids(v1) <= before
    assert unit_ids(v2).isdisjoint(before)
    on_the_day = consultable_ids(V2_FROM)
    assert unit_ids(v2) <= on_the_day
    assert unit_ids(v1).isdisjoint(on_the_day)
    later = consultable_ids(date(2024, 1, 1))
    assert unit_ids(v2) <= later
    assert unit_ids(v1).isdisjoint(later)


@pytest.mark.django_db
def test_new_version_gets_next_number_in_use_and_closes_the_previous(
    make_norm, first_version, validated_unregistered, read_write_user
):
    """REQ-007: la versión nueva recibe el número siguiente de su parte y queda en uso;
    la anterior sigue en uso para sus fechas, con `effective_to` igual al
    `effective_from` de la nueva (fin exclusivo)."""
    norm = make_norm()
    v1 = first_version(norm, V1_UNITS)
    v2 = validated_unregistered(norm, V2_UNITS)

    result = versions.register_version(read_write_user, v2.document_id)

    old, new = refreshed(v1), refreshed(v2)
    assert (new.version_number, new.in_use, new.effective_from, new.effective_to) == (
        2, True, V2_FROM, None)
    assert (old.version_number, old.in_use, old.effective_to) == (1, True, V2_FROM)
    assert result.document == new
    assert result.version_number == 2
    assert result.previous_document == old
    assert result.replaced_document is None


@pytest.mark.django_db
def test_third_version_closes_only_the_second(
    make_norm, first_version, validated_unregistered, read_write_user
):
    """REQ-007: con tres versiones, cada una rige hasta el día en que empieza la
    siguiente, y cada fecha devuelve las unidades de la suya."""
    norm = make_norm()
    v1 = first_version(norm, V1_UNITS)
    v2 = validated_unregistered(norm, V2_UNITS)
    v3 = validated_unregistered(norm, V3_UNITS, effective_from=V3_FROM)

    versions.register_version(read_write_user, v2.document_id)
    versions.register_version(read_write_user, v3.document_id)

    assert refreshed(v1).effective_to == V2_FROM
    assert refreshed(v2).effective_to == V3_FROM
    assert (refreshed(v3).version_number, refreshed(v3).effective_to) == (3, None)
    for day, own in ((date(2012, 1, 1), v1), (date(2018, 1, 1), v2),
                     (date(2024, 1, 1), v3)):
        found = consultable_ids(day)
        for reading in (v1, v2, v3):
            if reading is own:
                assert unit_ids(reading) <= found
            else:
                assert unit_ids(reading).isdisjoint(found)


@pytest.mark.django_db
def test_new_version_of_the_annex_does_not_touch_the_body(
    make_norm, first_version, validated_unregistered, read_write_user
):
    """REQ-007: registrar una versión nueva del anexo de una norma no cambia el
    documento en uso de su cuerpo: sigue en uso, versión 1, sin fin de vigencia, y sus
    unidades siguen consultables después de la vigencia del anexo nuevo."""
    norm = make_norm()
    body = first_version(norm, V1_UNITS, part="cuerpo")
    annex_v1 = first_version(norm, ANNEX_V1, part="anexo")
    annex_v2 = validated_unregistered(norm, ANNEX_V2, part="anexo")

    versions.register_version(read_write_user, annex_v2.document_id)

    body_doc = refreshed(body)
    assert (body_doc.version_number, body_doc.in_use, body_doc.effective_to) == (
        1, True, None)
    assert refreshed(annex_v1).effective_to == V2_FROM
    assert (refreshed(annex_v2).version_number, refreshed(annex_v2).in_use) == (2, True)
    later = consultable_ids(date(2024, 1, 1))
    assert unit_ids(body) <= later
    assert unit_ids(annex_v2) <= later
    assert unit_ids(annex_v1).isdisjoint(later)


@pytest.mark.django_db
def test_new_version_must_start_after_the_previous(
    make_norm, first_version, validated_unregistered, read_write_user
):
    """REQ-007, REQ-012: una versión nueva que no empieza después de la vigencia de la
    anterior se rechaza, sin cambiar nada y con el intento registrado."""
    norm = make_norm()
    v1 = first_version(norm, V1_UNITS)
    v2 = validated_unregistered(norm, V2_UNITS, effective_from=V1_FROM)
    versions_before = CorpusVersion.objects.count()

    with pytest.raises(versions.VersionRefused) as error:
        versions.register_version(read_write_user, v2.document_id)

    assert "01/03/2010" in str(error.value)
    assert (refreshed(v1).effective_to, refreshed(v2).in_use) == (None, False)
    assert refreshed(v2).version_number is None
    assert CorpusVersion.objects.count() == versions_before
    event = AuditEvent.objects.get(event_type="version")
    assert event.outcome == "rejected"
    assert event.detail["document"] == v2.document_id
    assert event.detail["reason"] == "invalid_dates"


# --- Archivo en uso de una versión existente -------------------------------------------


@pytest.mark.django_db
def test_same_part_validated_in_three_files_appears_once(
    make_norm, first_version, validated_unregistered, read_write_user
):
    """REQ-007: la misma parte de una norma validada en tres archivos aparece una sola
    vez: solo el documento en uso es consultable, antes y después de reemplazar el
    archivo en uso de la versión 1 por otro de los tres."""
    norm = make_norm()
    pdf = first_version(norm, V1_UNITS)
    scanned = validated_unregistered(norm, V1_UNITS, effective_from=V1_FROM)
    web = validated_unregistered(norm, V1_UNITS, effective_from=V1_FROM)
    day = date(2024, 1, 1)

    found = consultable_ids(day)
    assert unit_ids(pdf) <= found
    assert unit_ids(scanned).isdisjoint(found) and unit_ids(web).isdisjoint(found)

    result = versions.register_version(read_write_user, web.document_id,
                                       replaces_version=1)

    found = consultable_ids(day)
    assert unit_ids(web) <= found
    assert unit_ids(pdf).isdisjoint(found) and unit_ids(scanned).isdisjoint(found)
    old, new = refreshed(pdf), refreshed(web)
    assert (old.in_use, old.version_number) == (False, 1)
    assert (new.in_use, new.version_number) == (True, 1)
    assert result.replaced_document == old
    assert result.previous_document is None


@pytest.mark.django_db
def test_replacement_keeps_the_closed_vigencia_of_the_version(
    make_norm, first_version, validated_unregistered, read_write_user
):
    """REQ-007: reemplazar el archivo de una versión ya cerrada por una posterior
    conserva su fin de vigencia, de modo que cada fecha sigue devolviendo su versión."""
    norm = make_norm()
    v1 = first_version(norm, V1_UNITS)
    v2 = validated_unregistered(norm, V2_UNITS)
    versions.register_version(read_write_user, v2.document_id)
    v1_other_file = validated_unregistered(norm, V1_UNITS, effective_from=V1_FROM)

    versions.register_version(read_write_user, v1_other_file.document_id,
                              replaces_version=1)

    new = refreshed(v1_other_file)
    assert (new.version_number, new.in_use, new.effective_to) == (1, True, V2_FROM)
    assert unit_ids(v1_other_file) <= consultable_ids(date(2012, 1, 1))
    assert unit_ids(v1_other_file).isdisjoint(consultable_ids(date(2024, 1, 1)))
    assert unit_ids(v1).isdisjoint(consultable_ids(date(2012, 1, 1)))


@pytest.mark.django_db
def test_replacement_must_have_the_same_effective_from(
    make_norm, first_version, validated_unregistered, read_write_user
):
    """REQ-007, REQ-012: el archivo que reemplaza al de una versión tiene que regir desde
    la misma fecha; si no, se rechaza sin cambiar nada y con el intento registrado."""
    norm = make_norm()
    v1 = first_version(norm, V1_UNITS)
    other = validated_unregistered(norm, V1_UNITS, effective_from=V2_FROM)

    with pytest.raises(versions.VersionRefused):
        versions.register_version(read_write_user, other.document_id, replaces_version=1)

    assert (refreshed(v1).in_use, refreshed(other).in_use) == (True, False)
    event = AuditEvent.objects.get(event_type="version")
    assert (event.outcome, event.detail["reason"]) == ("rejected", "invalid_dates")


@pytest.mark.django_db
def test_replacing_a_version_that_does_not_exist_is_refused(
    make_norm, first_version, validated_unregistered, read_write_user
):
    """REQ-007: no se puede reemplazar el archivo de una versión que la parte no tiene."""
    norm = make_norm()
    first_version(norm, V1_UNITS)
    other = validated_unregistered(norm, V1_UNITS, effective_from=V1_FROM)

    with pytest.raises(versions.VersionRefused) as error:
        versions.register_version(read_write_user, other.document_id, replaces_version=5)

    assert "versión 5" in str(error.value)
    assert refreshed(other).in_use is False


# --- Condiciones del documento ----------------------------------------------------------


@pytest.mark.django_db
def test_document_without_validated_reading_is_refused(
    make_norm, first_version, validated_unregistered, read_write_user
):
    """REQ-007, REQ-005: un documento cuya lectura no está validada no se registra como
    versión."""
    norm = make_norm()
    first_version(norm, V1_UNITS)
    pending = validated_unregistered(norm, V2_UNITS, status="pending")

    with pytest.raises(versions.VersionRefused) as error:
        versions.register_version(read_write_user, pending.document_id)

    assert "validada" in str(error.value)
    assert refreshed(pending).in_use is False


@pytest.mark.django_db
def test_document_already_in_use_is_refused(make_norm, first_version, read_write_user):
    """REQ-007: un documento que ya está en uso no se registra otra vez."""
    v1 = first_version(make_norm(), V1_UNITS)

    with pytest.raises(versions.VersionRefused) as error:
        versions.register_version(read_write_user, v1.document_id)

    assert "ya está en uso" in str(error.value)


@pytest.mark.django_db
def test_unknown_document_is_refused(db, read_write_user):
    """REQ-007: un documento inexistente se rechaza con un mensaje llano."""
    with pytest.raises(versions.VersionRefused) as error:
        versions.register_version(read_write_user, 999999)

    assert "no existe el documento 999999" in str(error.value)


@pytest.mark.django_db
def test_key_already_in_another_part_in_use_is_refused(
    make_norm, first_version, validated_unregistered, read_write_user
):
    """REQ-007: si una clave del documento ya existe en otra parte en uso de la misma
    norma, no se registra, como en la validación."""
    norm = make_norm()
    first_version(norm, V1_UNITS, part="cuerpo")
    first_version(norm, ANNEX_V1, part="anexo")
    clash = validated_unregistered(
        norm, [("anexo", "ANEXO"), ("anexo/art-1", "Otro texto."), ("art-1", "Choca.")],
        part="anexo")

    with pytest.raises(versions.VersionRefused) as error:
        versions.register_version(read_write_user, clash.document_id)

    assert "art-1" in str(error.value)
    assert refreshed(clash).in_use is False


@pytest.mark.django_db
def test_read_only_user_cannot_register_a_version(
    make_norm, first_version, validated_unregistered, read_user
):
    """REQ-007, REQ-016: un usuario de lectura no registra versiones."""
    norm = make_norm()
    first_version(norm, V1_UNITS)
    v2 = validated_unregistered(norm, V2_UNITS)

    with pytest.raises(RoleRejected):
        versions.register_version(read_user, v2.document_id)

    assert refreshed(v2).in_use is False


# --- Registro y atomicidad ------------------------------------------------------------


@pytest.mark.django_db
def test_version_event_and_new_corpus_version(
    make_norm, first_version, validated_unregistered, read_write_user
):
    """REQ-007, REQ-012: registrar una versión crea una versión nueva de la normativa y
    deja el hecho `version` con documento, parte, número de versión, vigencia, documento
    anterior y documento que deja de estar en uso."""
    norm = make_norm()
    v1 = first_version(norm, V1_UNITS)
    v2 = validated_unregistered(norm, V2_UNITS)
    before = current_corpus_version()

    result = versions.register_version(read_write_user, v2.document_id)

    event = AuditEvent.objects.get(event_type="version")
    assert event.outcome == "ok"
    assert event.user == read_write_user
    assert event.channel == "command"
    assert event.corpus_version == result.corpus_version == current_corpus_version()
    assert before is None or result.corpus_version > before
    assert CorpusVersion.objects.get(pk=result.corpus_version).event == event
    assert event.detail == {
        "mode": "new_version",
        "document": v2.document_id,
        "norm": norm.pk,
        "part": "cuerpo",
        "version_number": 2,
        "effective_from": "2015-07-01",
        "effective_to": None,
        "previous_document": v1.document_id,
        "previous_version_number": 1,
        "previous_effective_to": "2015-07-01",
        "replaced_document": None,
        "new_corpus_version": result.corpus_version,
    }


@pytest.mark.django_db
def test_replacement_event_names_the_document_out_of_use(
    make_norm, first_version, validated_unregistered, read_write_user
):
    """REQ-012: el hecho del reemplazo nombra el documento que deja de estar en uso."""
    norm = make_norm()
    v1 = first_version(norm, V1_UNITS)
    other = validated_unregistered(norm, V1_UNITS, effective_from=V1_FROM)

    versions.register_version(read_write_user, other.document_id, replaces_version=1)

    detail = AuditEvent.objects.get(event_type="version").detail
    assert detail["mode"] == "replace_file"
    assert detail["replaced_document"] == v1.document_id
    assert detail["version_number"] == 1
    assert detail["previous_document"] is None


@pytest.mark.parametrize("replaces_version", [None, 1])
@pytest.mark.django_db
def test_a_failure_while_recording_leaves_nothing(
    make_norm, first_version, validated_unregistered, read_write_user, monkeypatch,
    replaces_version,
):
    """REQ-007, REQ-012: si el registro falla al final, no queda nada a medias: el
    documento nuevo sigue fuera de uso y sin versión, el anterior sigue en uso y sin fin
    de vigencia, y no hay versión nueva de la normativa ni hecho `version`."""
    norm = make_norm()
    v1 = first_version(norm, V1_UNITS)
    effective_from = V2_FROM if replaces_version is None else V1_FROM
    v2 = validated_unregistered(norm, V2_UNITS, effective_from=effective_from)
    versions_before = CorpusVersion.objects.count()
    original = audit_services.record

    def failing(*args, **kwargs):
        if kwargs.get("creates_corpus_version"):
            raise RuntimeError("falla simulada al registrar")
        return original(*args, **kwargs)

    monkeypatch.setattr(audit_services, "record", failing)

    with pytest.raises(RuntimeError):
        versions.register_version(read_write_user, v2.document_id,
                                  replaces_version=replaces_version)

    old, new = refreshed(v1), refreshed(v2)
    assert (old.in_use, old.version_number, old.effective_to) == (True, 1, None)
    assert (new.in_use, new.version_number, new.effective_to) == (False, None, None)
    assert CorpusVersion.objects.count() == versions_before
    assert not AuditEvent.objects.filter(event_type="version", outcome="ok").exists()


# --- Comando registrar_version ---------------------------------------------------------


@pytest.fixture
def typed_password(monkeypatch):
    def _type(password=TEST_PASSWORD):
        monkeypatch.setattr(permissions, "read_password", lambda prompt: password)

    return _type


def run_registrar_version(*args, **options):
    out = StringIO()
    call_command("registrar_version", *args, stdout=out, stderr=StringIO(), **options)
    return out.getvalue()


@pytest.mark.django_db
def test_command_registers_a_new_version(
    make_norm, first_version, validated_unregistered, read_write_user, typed_password
):
    """REQ-007: `registrar_version <documento> --nueva` deja el documento como versión
    siguiente de su parte y lo informa, con la vigencia cerrada de la anterior y la
    versión nueva de la normativa."""
    norm = make_norm()
    v1 = first_version(norm, V1_UNITS)
    v2 = validated_unregistered(norm, V2_UNITS)
    typed_password()

    out = run_registrar_version(str(v2.document_id), "--nueva",
                                usuario=read_write_user.username)

    assert refreshed(v2).version_number == 2
    assert f"documento {v2.document_id}" in out
    assert "versión 2" in out
    assert f"documento {v1.document_id}" in out and "30/06/2015" in out
    assert f"versión {current_corpus_version()} de la normativa" in out


@pytest.mark.django_db
def test_command_replaces_the_file_in_use(
    make_norm, first_version, validated_unregistered, read_write_user, typed_password
):
    """REQ-007: `registrar_version <documento> --reemplaza 1` deja el documento como
    archivo en uso de la versión 1 y dice cuál deja de estarlo."""
    norm = make_norm()
    v1 = first_version(norm, V1_UNITS)
    other = validated_unregistered(norm, V1_UNITS, effective_from=V1_FROM)
    typed_password()

    out = run_registrar_version(str(other.document_id), "--reemplaza", "1",
                                usuario=read_write_user.username)

    assert refreshed(other).in_use is True
    assert f"documento {v1.document_id} deja de estar en uso" in out


@pytest.mark.django_db
def test_command_requires_choosing_new_or_replace(
    make_norm, first_version, validated_unregistered, read_write_user, typed_password
):
    """REQ-007: el comando exige elegir entre versión nueva y reemplazo, y no acepta los
    dos a la vez."""
    norm = make_norm()
    first_version(norm, V1_UNITS)
    v2 = validated_unregistered(norm, V2_UNITS)
    typed_password()

    with pytest.raises(CommandError):
        run_registrar_version(str(v2.document_id), usuario=read_write_user.username)
    with pytest.raises(CommandError):
        run_registrar_version(str(v2.document_id), "--nueva", "--reemplaza", "1",
                              usuario=read_write_user.username)
    assert refreshed(v2).in_use is False


@pytest.mark.django_db
def test_command_reports_a_refusal_in_plain_words(
    make_norm, first_version, read_write_user, typed_password
):
    """REQ-007: un rechazo sale como error del comando, con el mensaje llano."""
    v1 = first_version(make_norm(), V1_UNITS)
    typed_password()

    with pytest.raises(CommandError, match="ya está en uso"):
        run_registrar_version(str(v1.document_id), "--nueva",
                              usuario=read_write_user.username)


@pytest.mark.django_db
def test_command_rejects_read_only_user(
    make_norm, first_version, validated_unregistered, read_user, typed_password
):
    """REQ-007, REQ-016: el comando rechaza a un usuario de lectura."""
    norm = make_norm()
    first_version(norm, V1_UNITS)
    v2 = validated_unregistered(norm, V2_UNITS)
    typed_password()

    with pytest.raises(CommandError, match="permiso"):
        run_registrar_version(str(v2.document_id), "--nueva", usuario=read_user.username)
    assert refreshed(v2).in_use is False


@pytest.mark.django_db
def test_command_wrong_password_is_rejected(
    make_norm, first_version, validated_unregistered, read_write_user, typed_password
):
    """REQ-007, REQ-016: con la clave equivocada no se registra nada."""
    norm = make_norm()
    first_version(norm, V1_UNITS)
    v2 = validated_unregistered(norm, V2_UNITS)
    typed_password("clave-equivocada-sintetica")

    with pytest.raises(CommandError, match="Usuario o clave incorrectos"):
        run_registrar_version(str(v2.document_id), "--nueva",
                              usuario=read_write_user.username)
    assert refreshed(v2).in_use is False
