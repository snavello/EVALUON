"""Validación de una lectura (T-015; plan 001, "Ingesta", "Una norma en más de un
archivo", "Versiones de una norma" y "Registro de auditoría").

Al validar se calculan pasajes y vectores, la lectura pasa a `validated`, el primer
documento validado de cada parte de una norma queda como versión 1 y en uso, se crea una
versión nueva de la normativa y queda el hecho `validation`. Los documentos se arman
como los deja la carga (T-014): sin versión, fuera de uso y con la lectura `pending`.
Los datos son sintéticos (P4); el vector lo da el doble de embeddings.
"""

import hashlib
from datetime import date
from io import StringIO

import pytest
from django.conf import settings
from django.core.management import CommandError, call_command
from django.db import connection

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit import services as audit_services
from evaluon.audit.models import AuditEvent
from evaluon.audit.services import current_corpus_version
from evaluon.norms import indexing
from evaluon.norms.management.commands import validar_informe
from evaluon.norms.models import CorpusVersion, Passage
from evaluon.norms.services import validation
from tests.conftest import TEST_PASSWORD

QUERY_DATE = date(2024, 1, 1)


def consultable_ids(reference_date=QUERY_DATE):
    with connection.cursor() as cursor:
        cursor.execute("SELECT unit_id FROM consultable_units(%s)", [reference_date])
        return {row[0] for row in cursor.fetchall()}


@pytest.fixture
def load(make_document, make_reading):
    """Deja un documento como lo deja la carga: sin versión, fuera de uso y con una
    lectura `pending` sin pasajes. `load(norma, unidades, part="cuerpo")`."""

    def _load(norm, units, part="cuerpo"):
        document = make_document(norm, part=part, in_use=False, version_number=None)
        return make_reading(document, units, status="pending", passages=False)

    return _load


BODY_UNITS = [
    ("art-1", "ARTICULO 1.- Apruébase el régimen sintético: a) primero."),
    ("art-1/inc-a", "a) primero."),
    ("art-2", "ARTICULO 2.- Comuníquese."),
]
ANNEX_UNITS = [
    ("anexo", "ANEXO"),
    ("anexo/art-1", "ARTÍCULO 1°.- OBJETO. Régimen sintético."),
]


def unit_ids(reading):
    return {u.pk for u in reading.units_by_key.values()}


# --- Función de validación -----------------------------------------------------------


@pytest.mark.django_db
def test_units_become_consultable_only_after_validation(
    make_norm, load, read_write_user, fake_embeddings
):
    """REQ-005: antes de validar, `consultable_units` no devuelve unidades de la norma;
    después de validar, sí."""
    reading = load(make_norm(), BODY_UNITS)
    assert unit_ids(reading).isdisjoint(consultable_ids())

    validation.validate_reading(read_write_user, reading.pk)

    assert unit_ids(reading) <= consultable_ids()


@pytest.mark.django_db
def test_validation_stores_passages_and_marks_reading_and_document(
    make_norm, load, read_write_user, fake_embeddings
):
    """REQ-005: al validar, cada unidad base recibe su pasaje con vector, la lectura
    queda `validated` con quién y cuándo, y el primer documento validado de la parte
    queda como versión 1 y en uso."""
    reading = load(make_norm(), BODY_UNITS)

    result = validation.validate_reading(read_write_user, reading.pk)

    reading.refresh_from_db()
    document = reading.document
    document.refresh_from_db()
    assert reading.status == "validated"
    assert reading.validated_by == read_write_user
    assert reading.validated_at is not None
    assert document.in_use is True
    assert document.version_number == 1
    passages = Passage.objects.filter(unit__reading=reading)
    assert sorted(p.unit.key for p in passages) == ["art-1", "art-2"]
    assert result.passages == 2
    assert len(fake_embeddings.calls) == 1


@pytest.mark.django_db
def test_embeddings_down_does_not_validate_nor_leave_anything(
    make_norm, load, read_write_user, fake_embeddings
):
    """REQ-005, REQ-012: con el servicio de embeddings caído no se valida, la lectura
    sigue `pending`, no hay pasajes, el documento no queda en uso, no se crea versión de
    la normativa, el motivo se dice en el error y el intento fallido queda registrado."""
    reading = load(make_norm(), BODY_UNITS)
    versions_before = CorpusVersion.objects.count()
    fake_embeddings.unavailable()

    with pytest.raises(validation.EmbeddingsFailed) as error:
        validation.validate_reading(read_write_user, reading.pk)

    assert "embeddings" in str(error.value)
    assert "No se validó" in str(error.value)
    reading.refresh_from_db()
    reading.document.refresh_from_db()
    assert reading.status == "pending"
    assert reading.validated_at is None
    assert not Passage.objects.filter(unit__reading=reading).exists()
    assert reading.document.in_use is False
    assert reading.document.version_number is None
    assert CorpusVersion.objects.count() == versions_before
    event = AuditEvent.objects.get(event_type="validation")
    assert event.outcome == "failed"
    assert event.user == read_write_user
    assert event.detail["reading"] == reading.pk
    assert event.detail["reason"] == "service_unavailable"


@pytest.mark.django_db
def test_embeddings_down_while_counting_tokens_is_recorded(
    make_norm, load, read_write_user, fake_embeddings
):
    """REQ-005, REQ-012: la partición en pasajes cuenta tokens con el servicio de
    embeddings (T-031). Si el servicio está caído, la falla ocurre al contar, antes de
    pedir ningún vector, y termina igual que una falla al calcular vectores: no se
    valida, la lectura sigue `pending`, sin pasajes, y queda el hecho `failed`."""
    reading = load(make_norm(), BODY_UNITS)
    fake_embeddings.unavailable()

    with pytest.raises(validation.EmbeddingsFailed) as error:
        validation.validate_reading(read_write_user, reading.pk)

    assert fake_embeddings.calls == [], "la falla tenía que ocurrir al contar tokens"
    assert "No se validó" in str(error.value)
    reading.refresh_from_db()
    assert reading.status == "pending"
    assert not Passage.objects.filter(unit__reading=reading).exists()
    event = AuditEvent.objects.get(event_type="validation")
    assert event.outcome == "failed"
    assert event.user == read_write_user
    assert event.detail["reading"] == reading.pk
    assert event.detail["reason"] == "service_unavailable"
    assert event.detail["service"] == "embeddings"


class SimulatedFailure(Exception):
    """Falla provocada por la prueba en medio de la validación confirmada."""


def _fail_record(monkeypatch):
    """`record` falla solo cuando registra la validación que crea la versión de la
    normativa; los demás hechos se registran normalmente."""
    original = audit_services.record

    def failing(*args, **kwargs):
        if kwargs.get("creates_corpus_version"):
            raise SimulatedFailure("falla simulada al registrar la validación")
        return original(*args, **kwargs)

    monkeypatch.setattr(audit_services, "record", failing)


def _fail_after_saving_passages(monkeypatch):
    """Los pasajes se guardan y enseguida algo falla."""
    original = indexing.save_passages

    def failing(drafts, vectors):
        original(drafts, vectors)
        raise SimulatedFailure("falla simulada después de guardar los pasajes")

    monkeypatch.setattr(indexing, "save_passages", failing)


@pytest.mark.django_db
@pytest.mark.parametrize("fail", [_fail_record, _fail_after_saving_passages],
                         ids=["record", "save_passages"])
def test_a_failure_inside_the_confirmation_leaves_nothing(
    make_norm, load, read_write_user, fake_embeddings, monkeypatch, fail
):
    """REQ-005, REQ-012: si algo falla durante la validación confirmada (al guardar los
    pasajes o al registrar el hecho), todo se deshace junto: la lectura sigue `pending`,
    sin pasajes, el documento sin versión ni en uso, y no hay hecho `validation` correcto
    ni versión nueva de la normativa (P6, P8)."""
    reading = load(make_norm(), BODY_UNITS)
    versions_before = CorpusVersion.objects.count()
    fail(monkeypatch)

    with pytest.raises(SimulatedFailure):
        validation.validate_reading(read_write_user, reading.pk)

    reading.refresh_from_db()
    reading.document.refresh_from_db()
    assert reading.status == "pending"
    assert reading.validated_at is None
    assert reading.validated_by is None
    assert not Passage.objects.filter(unit__reading=reading).exists()
    assert reading.document.in_use is False
    assert reading.document.version_number is None
    assert CorpusVersion.objects.count() == versions_before
    assert not AuditEvent.objects.filter(event_type="validation", outcome="ok").exists()
    assert unit_ids(reading).isdisjoint(consultable_ids())


@pytest.mark.django_db
def test_input_too_long_does_not_validate_and_says_why(
    make_norm, load, read_write_user, fake_embeddings
):
    """REQ-005, REQ-012: si el servicio de embeddings rechaza un texto por demasiado
    largo, no se valida, el mensaje lo dice con sus palabras, no queda nada guardado y
    el intento queda registrado como `failed` con el motivo `input_too_long`."""
    reading = load(make_norm(), BODY_UNITS)
    versions_before = CorpusVersion.objects.count()
    fake_embeddings.input_too_long()

    with pytest.raises(validation.EmbeddingsFailed) as error:
        validation.validate_reading(read_write_user, reading.pk)

    message = str(error.value)
    assert "No se validó" in message
    assert "demasiado largo" in message
    assert "no respondió" not in message
    reading.refresh_from_db()
    reading.document.refresh_from_db()
    assert reading.status == "pending"
    assert not Passage.objects.filter(unit__reading=reading).exists()
    assert reading.document.in_use is False
    assert reading.document.version_number is None
    assert CorpusVersion.objects.count() == versions_before
    event = AuditEvent.objects.get(event_type="validation")
    assert event.outcome == "failed"
    assert event.detail["reason"] == "input_too_long"
    assert event.detail["reading"] == reading.pk


@pytest.mark.django_db
def test_body_and_annex_of_a_norm_are_both_in_use(
    make_norm, load, read_write_user, fake_embeddings
):
    """REQ-005: validados el cuerpo y el anexo de una misma norma, los dos quedan en uso
    como versión 1 de su parte y `consultable_units` devuelve las unidades de los dos."""
    norm = make_norm()
    body = load(norm, BODY_UNITS, part="cuerpo")
    annex = load(norm, ANNEX_UNITS, part="anexo")

    validation.validate_reading(read_write_user, body.pk)
    validation.validate_reading(read_write_user, annex.pk)

    for reading in (body, annex):
        reading.document.refresh_from_db()
        assert reading.document.in_use is True
        assert reading.document.version_number == 1
    assert unit_ids(body) | unit_ids(annex) <= consultable_ids()


@pytest.mark.django_db
def test_second_document_of_same_part_is_validated_but_not_in_use(
    make_norm, load, read_write_user, fake_embeddings
):
    """REQ-005: un segundo documento de la misma norma y la misma parte queda validado
    pero no en uso, y sus unidades no son consultables hasta registrarlo como versión."""
    norm = make_norm()
    first = load(norm, BODY_UNITS)
    second = load(norm, BODY_UNITS)

    validation.validate_reading(read_write_user, first.pk)
    validation.validate_reading(read_write_user, second.pk)

    second.refresh_from_db()
    second.document.refresh_from_db()
    assert second.status == "validated"
    assert second.document.in_use is False
    assert second.document.version_number is None
    consultable = consultable_ids()
    assert unit_ids(first) <= consultable
    assert unit_ids(second).isdisjoint(consultable)


@pytest.mark.django_db
def test_key_already_in_another_part_in_use_is_not_validated(
    make_norm, load, read_write_user, fake_embeddings
):
    """REQ-005, REQ-012: si una clave de la lectura ya existe en otra parte en uso de la
    misma norma, no se valida, el mensaje dice qué clave y en qué parte, no se calculan
    vectores y el rechazo queda registrado."""
    norm = make_norm()
    annex = load(norm, ANNEX_UNITS, part="anexo")
    validation.validate_reading(read_write_user, annex.pk)
    calls_before = len(fake_embeddings.calls)
    body = load(norm, [
        ("art-1", "ARTICULO 1.- Apruébase el régimen sintético."),
        ("anexo", "ANEXO"),
        ("anexo/art-1", "ARTICULO 1.- Objeto repetido en el cuerpo."),
    ], part="cuerpo")

    with pytest.raises(validation.KeyConflict) as error:
        validation.validate_reading(read_write_user, body.pk)

    message = str(error.value)
    assert "anexo/art-1" in message
    assert "parte anexo" in message
    body.refresh_from_db()
    body.document.refresh_from_db()
    assert body.status == "pending"
    assert body.document.in_use is False
    assert not Passage.objects.filter(unit__reading=body).exists()
    assert len(fake_embeddings.calls) == calls_before
    event = AuditEvent.objects.filter(event_type="validation").latest("id")
    assert event.outcome == "rejected"
    assert event.detail["reading"] == body.pk
    assert set(event.detail["conflicting_keys"]) == {"anexo", "anexo/art-1"}


@pytest.mark.django_db
def test_same_keys_in_the_same_part_do_not_conflict(
    make_norm, load, read_write_user, fake_embeddings
):
    """REQ-005: la comprobación de claves mira solo las otras partes: un segundo
    documento de la misma parte, con las mismas claves, se valida."""
    norm = make_norm()
    validation.validate_reading(read_write_user, load(norm, BODY_UNITS).pk)
    second = load(norm, BODY_UNITS)

    validation.validate_reading(read_write_user, second.pk)

    second.refresh_from_db()
    assert second.status == "validated"


@pytest.mark.django_db
def test_validation_event_has_reading_passages_model_and_new_corpus_version(
    make_norm, load, read_write_user, fake_embeddings
):
    """REQ-012: el registro de la validación trae quién, cuándo, la lectura, la huella
    del informe que la persona vio, la cantidad de pasajes, el modelo de embeddings con
    su huella y la versión nueva de la normativa, que apunta a ese hecho."""
    norm = make_norm()
    reading = load(norm, BODY_UNITS)
    versions_before = CorpusVersion.objects.count()

    result = validation.validate_reading(read_write_user, reading.pk)

    event = AuditEvent.objects.get(event_type="validation")
    assert result.event == event
    assert event.outcome == "ok"
    assert event.channel == "command"
    assert event.user == read_write_user
    assert event.occurred_at is not None
    detail = event.detail
    assert detail["reading"] == reading.pk
    assert detail["document"] == reading.document.pk
    assert detail["norm"] == norm.pk
    assert detail["part"] == "cuerpo"
    assert detail["report_sha256"] == hashlib.sha256(
        reading.report_text.encode("utf-8")
    ).hexdigest()
    assert detail["passages"] == 2
    assert detail["embedding_model"] == settings.EMBEDDINGS_MODEL
    assert detail["embedding_revision"] == settings.EMBEDDINGS_MODEL_SHA256
    assert detail["in_use"] is True
    assert detail["version_number"] == 1
    assert CorpusVersion.objects.count() == versions_before + 1
    assert detail["new_corpus_version"] == event.corpus_version == current_corpus_version()
    assert CorpusVersion.objects.get(pk=event.corpus_version).event == event
    assert result.corpus_version == event.corpus_version


@pytest.mark.django_db
def test_read_only_user_cannot_validate(make_norm, load, read_user, fake_embeddings):
    """REQ-016, REQ-005: un usuario de lectura no puede validar; la lectura sigue
    `pending` y no se calculan vectores."""
    reading = load(make_norm(), BODY_UNITS)

    with pytest.raises(RoleRejected):
        validation.validate_reading(read_user, reading.pk)

    reading.refresh_from_db()
    assert reading.status == "pending"
    assert fake_embeddings.calls == []


@pytest.mark.django_db
def test_only_a_pending_reading_can_be_validated(
    make_norm, make_document, make_reading, read_write_user, fake_embeddings
):
    """REQ-005: una lectura ya validada o inexistente no se vuelve a validar y no se
    crea versión de la normativa."""
    reading = make_reading(make_document(make_norm()), BODY_UNITS)
    versions_before = CorpusVersion.objects.count()

    with pytest.raises(validation.ReadingNotPending):
        validation.validate_reading(read_write_user, reading.pk)
    with pytest.raises(validation.ReadingNotFound):
        validation.validate_reading(read_write_user, 999999)

    assert CorpusVersion.objects.count() == versions_before
    assert fake_embeddings.calls == []


# --- Comando validar_informe ---------------------------------------------------------


@pytest.fixture
def command_input(monkeypatch):
    """Simula lo que la persona escribe: la clave y la respuesta a la confirmación.
    Guarda los textos con que se le preguntó."""
    prompts = []

    def type_(answer, password=TEST_PASSWORD):
        def fake_password(prompt):
            prompts.append(prompt)
            return password

        def fake_confirm(prompt):
            prompts.append(prompt)
            return answer

        monkeypatch.setattr(permissions, "read_password", fake_password)
        monkeypatch.setattr(validar_informe, "ask_confirmation", fake_confirm)
        return prompts

    return type_


def run_validar_informe(*args, **options):
    out = StringIO()
    call_command("validar_informe", *args, stdout=out, stderr=StringIO(), **options)
    return out.getvalue()


@pytest.mark.django_db
def test_command_validates_after_confirmation(
    make_norm, load, read_write_user, fake_embeddings, command_input
):
    """REQ-005, REQ-012: `validar_informe` muestra qué se va a validar, pide
    confirmación y, confirmada, valida y dice la versión nueva de la normativa."""
    reading = load(make_norm(), BODY_UNITS)
    prompts = command_input("si")

    out = run_validar_informe(str(reading.pk), usuario=read_write_user.username)

    reading.refresh_from_db()
    assert reading.status == "validated"
    assert len(prompts) == 2
    assert "Lectura" in out and str(reading.pk) in out
    assert f"versión {current_corpus_version()} de la normativa" in out
    event = AuditEvent.objects.get(event_type="validation", outcome="ok")
    assert event.channel == "command"


@pytest.mark.django_db
def test_command_without_confirmation_does_not_validate(
    make_norm, load, read_write_user, fake_embeddings, command_input
):
    """REQ-005: si la persona no confirma, la lectura sigue `pending` y no se calcula
    nada."""
    reading = load(make_norm(), BODY_UNITS)
    command_input("no")

    out = run_validar_informe(str(reading.pk), usuario=read_write_user.username)

    reading.refresh_from_db()
    assert reading.status == "pending"
    assert fake_embeddings.calls == []
    assert "No se validó" in out


@pytest.mark.django_db
def test_command_rejects_read_only_user_before_asking(
    make_norm, load, read_user, fake_embeddings, command_input
):
    """REQ-016, REQ-005: un usuario de lectura que corre `validar_informe` es rechazado
    antes de que se le pida confirmación, y no se valida nada."""
    reading = load(make_norm(), BODY_UNITS)
    prompts = command_input("si")

    with pytest.raises(CommandError, match="no tiene permiso"):
        run_validar_informe(str(reading.pk), usuario=read_user.username)

    assert prompts == ["Clave de EVALUON: "]
    reading.refresh_from_db()
    assert reading.status == "pending"


@pytest.mark.django_db
def test_command_reports_embeddings_down(
    make_norm, load, read_write_user, fake_embeddings, command_input
):
    """REQ-005: con el servicio de embeddings caído, el comando dice que no validó y
    por qué, y la lectura sigue `pending`."""
    reading = load(make_norm(), BODY_UNITS)
    command_input("si")
    fake_embeddings.unavailable()

    with pytest.raises(CommandError, match="No se validó"):
        run_validar_informe(str(reading.pk), usuario=read_write_user.username)

    reading.refresh_from_db()
    assert reading.status == "pending"


@pytest.mark.django_db
def test_command_wrong_password_is_rejected(
    make_norm, load, read_write_user, fake_embeddings, command_input
):
    """REQ-016: con una clave incorrecta el comando da el mensaje único y no valida."""
    reading = load(make_norm(), BODY_UNITS)
    command_input("si", password="clave-equivocada-sintetica")

    with pytest.raises(CommandError, match=permissions.LOGIN_FAILED_MESSAGE):
        run_validar_informe(str(reading.pk), usuario=read_write_user.username)

    reading.refresh_from_db()
    assert reading.status == "pending"
