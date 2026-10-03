"""Relectura de un documento ya cargado y validación que reemplaza la lectura anterior
(T-027; plan 001, "Ingesta", punto 6, "Versiones de una norma", `norms_relation` y
"Registro de auditoría").

`releer_norma` crea una lectura nueva a partir del original guardado, sin pedir el
archivo, en estado `pending`, con su informe y su hecho `reread`. Al validarla, la
anterior pasa a `superseded` sin tocar sus unidades; mientras no se valida, sigue
consultable la anterior. La validación avisa si alguna relación quedó apuntando a una
clave que la lectura nueva no tiene.

También la corrección del aviso de T-026: un documento incorporado con confirmación de
"misma norma" no queda en uso al validarse y no cuenta entre los otros documentos de su
parte; entra en las consultas solo con `registrar_version`.

Documentos de prueba, públicos o sintéticos (P4): el extracto del anexo de la
Disposición AFIP 247/2022 (T-012), sus variantes armadas en memoria (T-026) y el
dictamen sintético (T-024).
"""

from datetime import date
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.db import connection

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent
from evaluon.audit.services import current_corpus_version
from evaluon.norms.management.commands import validar_informe
from evaluon.norms.models import Document, DocumentFile, Reading, Unit
from evaluon.norms.services import amendments, loading, validation, versions
from tests.conftest import TEST_PASSWORD, sha256_hex
from tests.norms.test_duplicates import (
    DATA_247,
    DATA_OPINION,
    EXTRACT_BYTES,
    OPINION,
    pages_five_and_six_pdf,
    resaved_extract,
)

QUERY_DATE = date(2024, 1, 1)
FIXED_NOW = "2026-10-03T10:00:00-03:00"


def consultable_ids(reference_date=QUERY_DATE):
    with connection.cursor() as cursor:
        cursor.execute("SELECT unit_id FROM consultable_units(%s)", [reference_date])
        return {row[0] for row in cursor.fetchall()}


def unit_ids(reading):
    return set(Unit.objects.filter(reading=reading).values_list("pk", flat=True))


def load(user, data=EXTRACT_BYTES, file_name="disp-247-2022-anexo-extracto.pdf", **fields):
    values = {**DATA_247, "part": "anexo", "general_regime": True, **fields}
    return loading.load_norm(user, data=data, file_name=file_name, **values)


def validated(user, data=EXTRACT_BYTES, **fields):
    """Carga y valida: el documento queda en uso con su lectura validada."""
    result = load(user, data=data, **fields)
    validation.validate_reading(user, result.reading.pk)
    result.document.refresh_from_db()
    return result


# --- Relectura -------------------------------------------------------------------------


@pytest.mark.django_db
def test_reread_creates_a_pending_reading_with_its_report(read_write_user, fake_embeddings):
    """REQ-004: la relectura crea una lectura nueva del documento, a partir del original
    guardado, en estado `pending`, con el número siguiente, su informe y sus unidades."""
    first = validated(read_write_user)

    result = loading.reread_document(read_write_user, first.document.pk)

    reading = Reading.objects.get(pk=result.reading.pk)
    assert reading.document_id == first.document.pk
    assert reading.sequence == 2
    assert reading.status == "pending"
    assert reading.validated_at is None
    assert reading.created_by == read_write_user
    assert reading.canonical_text == first.reading.canonical_text
    assert reading.canonical_sha256 == first.reading.canonical_sha256
    assert reading.report["units"]["total"] == result.units > 0
    assert reading.report["document"]["file_name"] == "disp-247-2022-anexo-extracto.pdf"
    assert reading.report["document"]["file_sha256"] == first.document.file_sha256
    assert reading.report["document"]["read_at"]
    assert "Posibles duplicados: ninguno." in reading.report_text
    assert reading.tool_versions["rules_version"] == first.reading.tool_versions["rules_version"]
    assert sorted(Unit.objects.filter(reading=reading).values_list("key", flat=True)) == sorted(
        Unit.objects.filter(reading=first.reading).values_list("key", flat=True)
    )
    assert Document.objects.count() == 1


@pytest.mark.django_db
def test_rereads_number_their_readings_in_sequence(read_write_user, fake_embeddings):
    """REQ-004: cada relectura toma el número siguiente de lectura del documento."""
    first = validated(read_write_user)

    second = loading.reread_document(read_write_user, first.document.pk)
    third = loading.reread_document(read_write_user, first.document.pk)

    assert (second.reading.sequence, third.reading.sequence) == (2, 3)


@pytest.mark.django_db
def test_reread_report_is_built_from_memory_not_from_the_database(
    read_write_user, fake_embeddings, monkeypatch
):
    """REQ-004: con la misma fecha de lectura, el informe en texto de la relectura es
    igual al de la carga: se arma con los datos en memoria y no desde el informe
    guardado, que `jsonb` reordena."""
    monkeypatch.setattr(loading.timezone, "localtime",
                        lambda *args, **kwargs: _fixed_datetime())
    first = validated(read_write_user)

    result = loading.reread_document(read_write_user, first.document.pk)

    assert result.reading.report_text == first.reading.report_text
    stored = Reading.objects.get(pk=result.reading.pk)
    assert stored.report_text == first.reading.report_text


def _fixed_datetime():
    from datetime import datetime

    return datetime.fromisoformat(FIXED_NOW)


@pytest.mark.django_db
def test_reread_keeps_the_load_duplicates_in_the_report(read_write_user):
    """REQ-004, REQ-011: el informe de la relectura de un documento incorporado con
    confirmación de "misma norma" sigue mostrando el posible duplicado de la carga."""
    load(read_write_user)
    second = load(read_write_user, data=pages_five_and_six_pdf(), file_name="otro.pdf",
                  same_norm_confirmation="other_file")

    result = loading.reread_document(read_write_user, second.document.pk)

    assert result.reading.report["duplicates"] == second.reading.report["duplicates"]
    assert "Posibles duplicados: 1." in result.reading.report_text
    assert "duplicates" in [item["kind"] for item in result.reading.report["attention"]]


@pytest.mark.django_db
def test_reread_uses_the_category_of_the_norm(read_write_user):
    """REQ-004, REQ-003: la relectura de un dictamen se parte con la regla de dictámenes,
    la que elige la categoría de su norma."""
    first = loading.load_norm(read_write_user, data=OPINION.read_bytes(),
                              file_name=OPINION.name, **DATA_OPINION)

    result = loading.reread_document(read_write_user, first.document.pk)

    types = set(Unit.objects.filter(reading=result.reading).values_list("unit_type", flat=True))
    assert types and types <= {"punto", "parrafo"}
    assert result.reading.report["rule"] == "dictamenes"


@pytest.mark.django_db
def test_reread_is_recorded_without_a_new_corpus_version(read_write_user, fake_embeddings):
    """REQ-012: la relectura deja el hecho `reread` con el documento, la lectura creada,
    la anterior, el archivo, las versiones de las herramientas y el resumen del informe,
    sin crear una versión de la normativa."""
    first = validated(read_write_user)
    version_before = current_corpus_version()

    result = loading.reread_document(read_write_user, first.document.pk)

    assert current_corpus_version() == version_before
    event = AuditEvent.objects.get(event_type="reread")
    assert (event.outcome, event.user, event.channel) == ("ok", read_write_user, "command")
    detail = event.detail
    assert detail["document"] == first.document.pk
    assert detail["norm"] == first.norm.pk
    assert detail["reading"] == result.reading.pk
    assert detail["sequence"] == 2
    assert detail["previous_reading"] == first.reading.pk
    assert detail["data"]["category"] == "regimen_especifico"
    assert detail["data"]["part"] == "anexo"
    assert detail["file"]["sha256"] == first.document.file_sha256
    assert detail["file"]["format"] == "pdf"
    assert detail["canonical_sha256"] == result.reading.canonical_sha256
    assert detail["tool_versions"]["rules_version"]
    assert detail["units"] == result.units
    assert detail["report"]["units_by_type"]["articulo"] > 0
    assert detail["same_norm_confirmation"] == ""


@pytest.mark.django_db
def test_reread_of_a_missing_document_is_refused_and_recorded(read_write_user):
    """REQ-004, REQ-012: releer un documento que no existe lo dice en lenguaje llano y
    queda registrado como hecho `reread` rechazado."""
    with pytest.raises(loading.RereadRefused, match="no existe el documento 999"):
        loading.reread_document(read_write_user, 999)

    event = AuditEvent.objects.get(event_type="reread")
    assert event.outcome == "rejected"
    assert event.detail["document"] == 999
    assert not Reading.objects.exists()


@pytest.mark.django_db
def test_read_user_cannot_reread(read_write_user, read_user):
    """REQ-016, REQ-004: un usuario de lectura no puede releer un documento."""
    first = load(read_write_user)

    with pytest.raises(RoleRejected):
        loading.reread_document(read_user, first.document.pk)

    assert Reading.objects.count() == 1


# --- Validación de la relectura ------------------------------------------------------


@pytest.mark.django_db
def test_previous_reading_stays_consultable_until_the_new_one_is_validated(
    read_write_user, fake_embeddings
):
    """REQ-005: la lectura nueva no es consultable hasta validarse; mientras tanto sigue
    consultable la anterior. Al validarla, `consultable_units` devuelve las unidades de
    la nueva y ninguna de la anterior."""
    first = validated(read_write_user)
    result = loading.reread_document(read_write_user, first.document.pk)

    consultable = consultable_ids()
    assert unit_ids(first.reading) <= consultable
    assert unit_ids(result.reading).isdisjoint(consultable)

    validation.validate_reading(read_write_user, result.reading.pk)

    consultable = consultable_ids()
    assert unit_ids(result.reading) <= consultable
    assert unit_ids(first.reading).isdisjoint(consultable)


@pytest.mark.django_db
def test_validating_the_new_reading_supersedes_the_previous_and_keeps_its_units(
    read_write_user, fake_embeddings
):
    """REQ-005: al validar la lectura nueva, la anterior pasa a `superseded` con su
    fecha; sus unidades conservan su `id` y su texto, y el documento sigue en uso con su
    versión."""
    first = validated(read_write_user)
    before = {u.pk: (u.key, u.text) for u in Unit.objects.filter(reading=first.reading)}
    result = loading.reread_document(read_write_user, first.document.pk)

    outcome = validation.validate_reading(read_write_user, result.reading.pk)

    old = Reading.objects.get(pk=first.reading.pk)
    assert old.status == "superseded"
    assert old.superseded_at is not None
    after = {u.pk: (u.key, u.text) for u in Unit.objects.filter(reading=first.reading)}
    assert after == before
    document = Document.objects.get(pk=first.document.pk)
    assert (document.in_use, document.version_number) == (True, 1)
    assert outcome.in_use is True and outcome.version_number == 1
    assert outcome.superseded_readings == [first.reading.pk]
    event = AuditEvent.objects.filter(event_type="validation", outcome="ok").latest("pk")
    assert event.detail["superseded_readings"] == [first.reading.pk]


@pytest.mark.django_db
def test_an_older_pending_reading_cannot_be_validated_after_a_reread(read_write_user,
                                                                    fake_embeddings):
    """REQ-005: si el documento tiene una lectura más nueva, la anterior pendiente no se
    valida: así no vuelve a las consultas una lectura que la relectura reemplazó."""
    first = load(read_write_user)
    result = loading.reread_document(read_write_user, first.document.pk)

    with pytest.raises(validation.ReadingNotLatest, match=f"lectura {result.reading.pk}"):
        validation.validate_reading(read_write_user, first.reading.pk)

    assert Reading.objects.get(pk=first.reading.pk).status == "pending"
    refusal = AuditEvent.objects.get(event_type="validation", outcome="rejected")
    assert refusal.detail["reason"] == "not_latest"
    assert refusal.detail["latest_reading"] == result.reading.pk
    validation.validate_reading(read_write_user, result.reading.pk)
    document = Document.objects.get(pk=first.document.pk)
    assert (document.in_use, document.version_number) == (True, 1)


@pytest.mark.django_db
def test_validating_a_reread_still_marks_amendments_loaded(
    read_write_user, fake_embeddings, monkeypatch
):
    """REQ-021, REQ-005: validar una relectura sigue pasando por el paso a cargada de las
    modificatorias anotadas de la norma (T-051)."""
    first = validated(read_write_user)
    result = loading.reread_document(read_write_user, first.document.pk)
    calls = []
    original = amendments.mark_loaded_for_norm

    def spy(norm):
        calls.append(norm)
        return original(norm)

    monkeypatch.setattr(amendments, "mark_loaded_for_norm", spy)

    validation.validate_reading(read_write_user, result.reading.pk)

    assert calls == [first.norm.pk]


@pytest.fixture
def stale_document(read_write_user, make_norm, make_document, make_reading, make_relation):
    """Un documento en uso cuya lectura validada tiene una clave que el archivo no da
    (`anexo/art-999`), como si una regla corregida dejara de reconocer un artículo
    falso. El original guardado es el extracto del anexo. Con dos relaciones hacia la
    norma: una a `anexo/art-999` y otra a `anexo/art-1`, que la relectura conserva."""
    norm = make_norm(citation="Norma sintética con relaciones")
    document = make_document(norm, part="anexo", file_name="extracto.pdf",
                             file_sha256=sha256_hex("extracto guardado"))
    DocumentFile.objects.create(document=document, content=EXTRACT_BYTES)
    reading = make_reading(document, [
        ("anexo", "ANEXO"),
        ("anexo/art-1", "ARTÍCULO 1°.- Texto sintético."),
        ("anexo/art-999", "ARTÍCULO 999.- Artículo falso."),
    ])
    source = make_norm(citation="Norma sintética modificatoria")
    lost = make_relation(source, norm, target_unit_key="anexo/art-999")
    kept = make_relation(source, norm, target_unit_key="anexo/art-1")
    return document, reading, lost, kept


@pytest.mark.django_db
def test_validation_warns_about_relations_left_without_their_unit(
    read_write_user, fake_embeddings, stale_document
):
    """REQ-005, REQ-006: al validar la relectura, se avisa de la relación que apunta a
    una clave que la lectura nueva no tiene, y no de la que sigue teniendo su unidad."""
    document, old, lost, kept = stale_document
    result = loading.reread_document(read_write_user, document.pk)

    summary = validation.reading_summary(read_write_user, result.reading.pk)
    outcome = validation.validate_reading(read_write_user, result.reading.pk)

    for warnings in (summary["relations_without_unit"], outcome.relations_without_unit):
        assert [(w["relation"], w["key"]) for w in warnings] == [(lost.pk, "anexo/art-999")]
        assert "anexo/art-999" in warnings[0]["text"]
    event = AuditEvent.objects.filter(event_type="validation", outcome="ok").latest("pk")
    assert [w["relation"] for w in event.detail["relations_without_unit"]] == [lost.pk]


@pytest.mark.django_db
def test_no_relation_warning_when_every_key_is_kept(read_write_user, fake_embeddings,
                                                   make_relation, make_norm):
    """REQ-005, REQ-006: si la lectura nueva tiene todas las claves a las que apuntan las
    relaciones, no hay aviso."""
    first = validated(read_write_user)
    make_relation(make_norm(), first.norm, target_unit_key="anexo/art-1")
    result = loading.reread_document(read_write_user, first.document.pk)

    outcome = validation.validate_reading(read_write_user, result.reading.pk)

    assert outcome.relations_without_unit == []


# --- Misma norma confirmada (aviso de T-026) -----------------------------------------


@pytest.mark.django_db
def test_same_text_confirmed_with_another_part_is_not_put_in_use(
    read_write_user, fake_embeddings
):
    """REQ-005, REQ-011: el mismo texto cargado con otra parte y confirmado como misma
    norma se valida pero no queda en uso: sus unidades no son consultables."""
    first = validated(read_write_user)
    copy = load(read_write_user, data=resaved_extract(), file_name="copia.pdf",
                part="anexo-i", same_norm_confirmation="other_file")

    outcome = validation.validate_reading(read_write_user, copy.reading.pk)

    document = Document.objects.get(pk=copy.document.pk)
    assert (document.in_use, document.version_number) == (False, None)
    assert outcome.in_use is False
    assert unit_ids(copy.reading).isdisjoint(consultable_ids())
    assert unit_ids(first.reading) <= consultable_ids()


@pytest.mark.django_db
def test_same_text_confirmed_with_another_norm_is_not_put_in_use(
    read_write_user, fake_embeddings
):
    """REQ-005, REQ-011: el mismo texto cargado con los datos de otra norma y confirmado
    como misma norma se valida pero no queda en uso: no duplica unidades en las
    consultas."""
    validated(read_write_user)
    copy = load(read_write_user, data=resaved_extract(), file_name="copia.pdf",
                number="999", citation="Disposición AFIP 999/2022",
                same_norm_confirmation="other_file")

    validation.validate_reading(read_write_user, copy.reading.pk)

    document = Document.objects.get(pk=copy.document.pk)
    assert (document.in_use, document.version_number) == (False, None)
    assert unit_ids(copy.reading).isdisjoint(consultable_ids())


@pytest.mark.django_db
def test_second_file_confirmed_as_new_version_validated_first_does_not_take_version_1(
    read_write_user, fake_embeddings
):
    """REQ-005, REQ-011: un segundo archivo confirmado como versión nueva y validado
    antes que el primero no queda como versión 1 ni en uso, y no le quita al primero su
    lugar: el primero, al validarse, queda como versión 1 y en uso."""
    first = load(read_write_user)
    second = load(read_write_user, data=pages_five_and_six_pdf(), file_name="otro.pdf",
                  same_norm_confirmation="new_version")

    validation.validate_reading(read_write_user, second.reading.pk)
    validation.validate_reading(read_write_user, first.reading.pk)

    second_document = Document.objects.get(pk=second.document.pk)
    first_document = Document.objects.get(pk=first.document.pk)
    assert (second_document.in_use, second_document.version_number) == (False, None)
    assert (first_document.in_use, first_document.version_number) == (True, 1)
    consultable = consultable_ids()
    assert unit_ids(first.reading) <= consultable
    assert unit_ids(second.reading).isdisjoint(consultable)


@pytest.mark.django_db
def test_confirmed_document_enters_the_queries_only_with_registrar_version(
    read_write_user, fake_embeddings
):
    """REQ-005, REQ-007: el documento confirmado como versión nueva, ya validado, entra
    en las consultas al registrarlo con `registrar_version`."""
    first = validated(read_write_user)
    second = load(read_write_user, data=pages_five_and_six_pdf(), file_name="otro.pdf",
                  same_norm_confirmation="new_version", effective_from=date(2023, 6, 1))
    validation.validate_reading(read_write_user, second.reading.pk)

    versions.register_version(read_write_user, second.document.pk)

    document = Document.objects.get(pk=second.document.pk)
    assert (document.in_use, document.version_number) == (True, 2)
    assert unit_ids(second.reading) <= consultable_ids()
    assert first.document.pk != second.document.pk


# --- Comandos ------------------------------------------------------------------------


@pytest.fixture
def typed(monkeypatch):
    """Simula la clave y, en `validar_informe`, la respuesta a la confirmación."""

    def type_(answer="si"):
        monkeypatch.setattr(permissions, "read_password", lambda prompt: TEST_PASSWORD)
        monkeypatch.setattr(validar_informe, "ask_confirmation", lambda prompt: answer)

    return type_


def run(command, *args, user):
    out = StringIO()
    call_command(command, *[str(a) for a in args], stdout=out, stderr=StringIO(),
                 usuario=user.username)
    return out.getvalue()


@pytest.mark.django_db
def test_command_rereads_without_asking_for_the_file(read_write_user, fake_embeddings,
                                                     typed):
    """REQ-004, REQ-005: `releer_norma` recibe el número del documento, crea la lectura
    nueva y dice cómo revisarla y validarla, y que mientras tanto sigue la anterior."""
    typed()
    first = validated(read_write_user)

    out = run("releer_norma", first.document.pk, user=read_write_user)

    reading = Reading.objects.get(document=first.document, sequence=2)
    assert f"Lectura {reading.pk}" in out
    assert "pendiente de validación" in out
    assert f"ver_informe {reading.pk}" in out
    assert f"validar_informe {reading.pk}" in out
    assert f"lectura {first.reading.pk}" in out


@pytest.mark.django_db
def test_command_reread_rejects_read_user(read_write_user, read_user, typed):
    """REQ-016: `releer_norma` rechaza a un usuario de lectura y no crea lectura."""
    typed()
    first = load(read_write_user)

    with pytest.raises(CommandError, match="no tiene permiso"):
        run("releer_norma", first.document.pk, user=read_user)

    assert Reading.objects.count() == 1


@pytest.mark.django_db
def test_command_reread_of_missing_document(read_write_user, typed):
    """REQ-004: `releer_norma` con un documento que no existe lo dice en lenguaje
    llano."""
    typed()

    with pytest.raises(CommandError, match="no existe el documento 999"):
        run("releer_norma", 999, user=read_write_user)


@pytest.mark.django_db
def test_command_says_a_confirmed_document_is_not_used_until_registered(
    read_write_user, fake_embeddings, typed
):
    """REQ-005, REQ-011: al validar un documento confirmado como misma norma,
    `validar_informe` avisa antes que no entra en las consultas y después dice en llano
    que se validó y no se usa hasta registrarlo con `registrar_version`."""
    typed()
    validated(read_write_user)
    copy = load(read_write_user, data=resaved_extract(), file_name="copia.pdf",
                part="anexo-i", same_norm_confirmation="other_file")

    out = run("validar_informe", copy.reading.pk, user=read_write_user)

    assert "la norma queda disponible para consultas" not in out
    assert ("Se validó; no se usa en las consultas hasta registrarlo con "
            "registrar_version.") in out
    assert "Ya hay otro documento validado" not in out


@pytest.mark.django_db
def test_command_validating_a_reread_says_it_replaces_the_previous_reading(
    read_write_user, fake_embeddings, typed, stale_document
):
    """REQ-005, REQ-006: `validar_informe` sobre una relectura dice que reemplaza a la
    lectura anterior y muestra el aviso de relación sin unidad."""
    typed()
    document, old, lost, kept = stale_document
    result = loading.reread_document(read_write_user, document.pk)

    out = run("validar_informe", result.reading.pk, user=read_write_user)

    assert f"reemplaza a la lectura {old.pk}" in out
    assert "Quedó en uso como versión 1 de su parte." in out
    assert f"relación {lost.pk}" in out and "anexo/art-999" in out
    assert f"relación {kept.pk}" not in out
