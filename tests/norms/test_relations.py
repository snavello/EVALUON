"""Relaciones entre normas y sus vínculos (T-029; plan 001, `norms_relation`, "Unidades
consultables a una fecha", "Pantalla, acceso y comandos" y "Registro de auditoría").

Registrar una relación comprueba el rol, los datos y que las claves de unidad existan en
los documentos en uso de cada norma, en cualquiera de sus partes; guarda la relación con
la fecha que escribe la persona, deja el hecho `relation` y crea una versión nueva de la
normativa. El listado muestra los vínculos de cada norma en los dos sentidos.

Los datos son sintéticos y se arman con las fábricas de `tests/conftest.py` (P4).
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
from evaluon.norms.models import CorpusVersion, Relation
from evaluon.norms.services import listing, relations
from tests.conftest import TEST_PASSWORD

V = date(2023, 1, 1)


def unit_changes(reference_date):
    """Filas de `unit_changes(fecha)`: `(unit_id, relation_id, source_unit_id)`."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT unit_id, relation_id, source_unit_id FROM unit_changes(%s)",
            [reference_date],
        )
        return cursor.fetchall()


def repealed_by_unit(reference_date):
    """`repealed` de cada unidad consultable a la fecha, por `unit_id`."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT unit_id, repealed FROM consultable_units(%s)", [reference_date]
        )
        return dict(cursor.fetchall())


def links_of(user, norm):
    (item,) = [n for n in listing.list_norms(user) if n.id == norm.pk]
    return item.links


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
def two_norms(make_norm, make_document, make_reading):
    """Una norma alcanzada con `art-1` (e inciso `a`) y `art-2`, y una norma de origen
    en dos partes: el cuerpo (`art-1`, `art-2`) y el anexo (`anexo`, `anexo/art-1`).
    Las dos, con sus documentos validados y en uso."""
    target = make_norm(citation="Norma alcanzada sintética 1/2099")
    target_reading = make_reading(make_document(target), [
        ("art-1", "ARTICULO 1.- Texto original sintético."),
        ("art-1/inc-a", "a) inciso original sintético."),
        ("art-2", "ARTICULO 2.- Otro texto sintético."),
    ])
    source = make_norm(citation="Norma de origen sintética 2/2099")
    body_reading = make_reading(make_document(source, part="cuerpo"), [
        ("art-1", "ARTICULO 1.- Sustitúyese el artículo 1 de la norma alcanzada."),
        ("art-2", "ARTICULO 2.- Derógase la norma alcanzada."),
    ])
    annex_reading = make_reading(make_document(source, part="anexo"), [
        ("anexo", "ANEXO"),
        ("anexo/art-1", "ARTÍCULO 1°.- Texto sintético del anexo."),
    ])
    return {
        "target": target,
        "source": source,
        "target_units": target_reading.units_by_key,
        "source_units": {**body_reading.units_by_key, **annex_reading.units_by_key},
    }


def register(user, source, target, relation_type="modifica", **fields):
    values = {"effective_date": V, "source_unit_key": "", "target_unit_key": ""}
    values.update(fields)
    return relations.register_relation(
        user,
        relation_type=relation_type,
        source_norm=source.pk,
        target_norm=target.pk,
        **values,
    )


# --- Registro de la relación (REQ-006) -----------------------------------------------


@pytest.mark.django_db
def test_registered_relation_appears_as_link_in_both_norms(
    two_norms, read_write_user, read_user
):
    """REQ-006: dadas dos normas donde una modifica a la otra, registrada la relación,
    al listar cualquiera de las dos aparece el vínculo, en su sentido."""
    source, target = two_norms["source"], two_norms["target"]

    result = register(read_write_user, source, target, "modifica")

    (outgoing,) = links_of(read_user, source)
    assert outgoing.direction == "outgoing"
    assert outgoing.relation_id == result.relation.pk
    assert outgoing.relation_type == "modifica"
    assert (outgoing.other_norm_id, outgoing.other_citation) == (
        target.pk, "Norma alcanzada sintética 1/2099"
    )
    assert outgoing.effective_date == V
    (incoming,) = links_of(read_user, target)
    assert incoming.direction == "incoming"
    assert incoming.relation_id == result.relation.pk
    assert (incoming.other_norm_id, incoming.other_citation) == (
        source.pk, "Norma de origen sintética 2/2099"
    )


@pytest.mark.django_db
def test_relation_between_units_keeps_their_keys(two_norms, read_write_user, read_user):
    """REQ-006: una relación entre unidades guarda las claves de la unidad de origen y
    de la alcanzada, y el vínculo las muestra."""
    source, target = two_norms["source"], two_norms["target"]

    result = register(read_write_user, source, target, "modifica",
                      source_unit_key="art-1", target_unit_key="art-1/inc-a")

    relation = Relation.objects.get(pk=result.relation.pk)
    assert (relation.source_unit_key, relation.target_unit_key) == ("art-1", "art-1/inc-a")
    assert (relation.source_norm_id, relation.target_norm_id) == (source.pk, target.pk)
    assert relation.registered_by == read_write_user
    (link,) = links_of(read_user, target)
    assert (link.source_unit_key, link.target_unit_key) == ("art-1", "art-1/inc-a")


@pytest.mark.django_db
def test_key_of_any_part_of_the_norm_is_accepted(two_norms, read_write_user):
    """REQ-006: la clave se busca en todas las partes en uso de la norma: una clave del
    anexo de la norma de origen se acepta."""
    source, target = two_norms["source"], two_norms["target"]

    result = register(read_write_user, source, target, "complementa",
                      source_unit_key="anexo/art-1", target_unit_key="art-2")

    assert result.relation.source_unit_key == "anexo/art-1"


@pytest.mark.django_db
@pytest.mark.parametrize("keys", [
    {"source_unit_key": "art-99"},
    {"target_unit_key": "art-99"},
    {"source_unit_key": "anexo/art-1", "target_unit_key": "anexo/art-1"},
], ids=["origen", "alcanzada", "clave-de-la-otra-norma"])
def test_missing_unit_key_is_refused_and_nothing_is_saved(
    two_norms, read_write_user, keys
):
    """REQ-006: una clave que no existe en la norma se rechaza: no se guarda la
    relación ni se crea versión de la normativa; el rechazo queda registrado."""
    source, target = two_norms["source"], two_norms["target"]
    versions_before = CorpusVersion.objects.count()

    with pytest.raises(relations.UnitKeyNotFound, match="art-"):
        register(read_write_user, source, target, "modifica", **keys)

    assert not Relation.objects.exists()
    assert CorpusVersion.objects.count() == versions_before
    event = AuditEvent.objects.get(event_type="relation")
    assert event.outcome == "rejected"
    assert event.detail["reason"] == "unit_key_not_found"


@pytest.mark.django_db
def test_key_only_in_a_document_not_in_use_or_not_validated_is_refused(
    make_norm, make_document, make_reading, read_write_user
):
    """REQ-006: solo cuentan los documentos en uso con su lectura validada: una clave
    que solo está en un documento fuera de uso o en una lectura pendiente se rechaza."""
    target = make_norm()
    make_reading(make_document(target), [("art-1", "ARTICULO 1.- Texto sintético.")])
    make_reading(make_document(target, part="anexo", in_use=False, version_number=None),
                 [("anexo/art-5", "ARTICULO 5.- Fuera de uso.")])
    make_reading(make_document(target, part="anexo-ii"),
                 [("anexo-ii/art-6", "ARTICULO 6.- Lectura pendiente.")],
                 status="pending")
    source = make_norm()

    for key in ("anexo/art-5", "anexo-ii/art-6"):
        with pytest.raises(relations.UnitKeyNotFound):
            register(read_write_user, source, target, target_unit_key=key)

    assert not Relation.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("change, error", [
    ({"relation_type": "sustituye"}, relations.InvalidRelation),
    ({"relation_type": ""}, relations.InvalidRelation),
    ({"effective_date": None}, relations.InvalidRelation),
    ({"source_norm": 0}, relations.NormNotFound),
    ({"target_norm": 0}, relations.NormNotFound),
    ({"same_norm": True}, relations.InvalidRelation),
], ids=["tipo-invalido", "sin-tipo", "sin-fecha", "sin-origen", "sin-alcanzada",
        "misma-norma"])
def test_invalid_data_is_refused(two_norms, read_write_user, change, error):
    """REQ-006, REQ-007: el tipo tiene que ser uno de los cuatro; la fecha es
    obligatoria y la escribe la persona (no se completa sola); las dos normas tienen
    que existir y ser distintas. Nada se guarda y el rechazo queda registrado."""
    values = {
        "relation_type": "modifica",
        "source_norm": two_norms["source"].pk,
        "target_norm": two_norms["target"].pk,
        "effective_date": V,
    }
    change = dict(change)
    if change.pop("same_norm", False):
        values["target_norm"] = values["source_norm"]
    values.update(change)

    with pytest.raises(error):
        relations.register_relation(read_write_user, **values)

    assert not Relation.objects.exists()
    assert AuditEvent.objects.get(event_type="relation").outcome == "rejected"


@pytest.mark.django_db
def test_read_user_cannot_register(two_norms, read_user):
    """REQ-016, REQ-006: un usuario de lectura no registra relaciones."""
    with pytest.raises(RoleRejected):
        register(read_user, two_norms["source"], two_norms["target"])

    assert not Relation.objects.exists()


# --- Registro de auditoría y versión de la normativa (REQ-012, P6, P8) ---------------


@pytest.mark.django_db
def test_relation_event_has_its_data_and_creates_a_corpus_version(
    two_norms, read_write_user
):
    """REQ-006, REQ-012: el hecho `relation` guarda tipo, normas, claves de unidad,
    fecha y usuario, y crea una versión nueva de la normativa que apunta a él."""
    source, target = two_norms["source"], two_norms["target"]
    versions_before = CorpusVersion.objects.count()

    result = register(read_write_user, source, target, "modifica",
                      source_unit_key="art-1", target_unit_key="art-1",
                      effective_date=date(2020, 6, 1))

    event = AuditEvent.objects.get(event_type="relation")
    assert event == result.event
    assert (event.outcome, event.channel, event.user) == ("ok", "command", read_write_user)
    detail = event.detail
    assert detail["relation"] == result.relation.pk
    assert detail["relation_type"] == "modifica"
    assert detail["source_norm"] == source.pk
    assert detail["target_norm"] == target.pk
    assert detail["source_unit_key"] == "art-1"
    assert detail["target_unit_key"] == "art-1"
    assert detail["effective_date"] == "2020-06-01"
    assert CorpusVersion.objects.count() == versions_before + 1
    assert detail["new_corpus_version"] == event.corpus_version == current_corpus_version()
    assert result.corpus_version == event.corpus_version
    assert CorpusVersion.objects.get(pk=event.corpus_version).event == event


class SimulatedFailure(Exception):
    """Falla provocada por la prueba al registrar el hecho."""


@pytest.mark.django_db
def test_a_failure_when_recording_leaves_no_relation(two_norms, read_write_user,
                                                     monkeypatch):
    """REQ-006, REQ-012: la relación, el hecho y la versión de la normativa se guardan
    juntos: si falla el registro del hecho, la relación no queda."""
    original = audit_services.record

    def failing(*args, **kwargs):
        if kwargs.get("creates_corpus_version"):
            raise SimulatedFailure("falla simulada")
        return original(*args, **kwargs)

    monkeypatch.setattr(audit_services, "record", failing)

    with pytest.raises(SimulatedFailure):
        register(read_write_user, two_norms["source"], two_norms["target"])

    assert not Relation.objects.exists()
    assert not CorpusVersion.objects.exists()


# --- Efecto en las fechas (REQ-007, REQ-020) -----------------------------------------


@pytest.mark.django_db
def test_modified_article_before_and_after_the_date(two_norms, read_write_user):
    """REQ-007: un artículo modificado en una fecha: antes, `unit_changes` no devuelve
    nada; desde esa fecha, devuelve la unidad que lo modifica, con su texto literal."""
    source_units, target_units = two_norms["source_units"], two_norms["target_units"]
    register(read_write_user, two_norms["source"], two_norms["target"], "modifica",
             source_unit_key="art-1", target_unit_key="art-1",
             effective_date=date(2020, 6, 1))
    article = target_units["art-1"]

    before = [row for row in unit_changes(date(2020, 5, 31)) if row[0] == article.pk]
    after = [row for row in unit_changes(date(2020, 6, 1)) if row[0] == article.pk]

    assert before == []
    (row,) = after
    modifying = source_units["art-1"]
    assert row[2] == modifying.pk
    reading = modifying.reading
    assert modifying.text == reading.canonical_text[modifying.char_start:modifying.char_end]
    assert modifying.text == "ARTICULO 1.- Sustitúyese el artículo 1 de la norma alcanzada."


@pytest.mark.django_db
def test_repeal_of_a_whole_norm_from_a_two_part_norm(two_norms, read_write_user):
    """REQ-006, REQ-007, REQ-020: una relación `deroga` de una norma en dos partes sobre
    otra norma entera, con origen en `art-2` del cuerpo, se registra y deja a la norma
    alcanzada con `repealed` verdadero desde su fecha y no antes. No es un cambio de
    cada unidad: `unit_changes` no la devuelve."""
    target_units = two_norms["target_units"]

    result = register(read_write_user, two_norms["source"], two_norms["target"], "deroga",
                      source_unit_key="art-2", effective_date=V)

    assert (result.relation.source_unit_key, result.relation.target_unit_key) == (
        "art-2", ""
    )
    before = repealed_by_unit(date(2022, 12, 31))
    after = repealed_by_unit(V)
    for unit in target_units.values():
        assert before[unit.pk] is False
        assert after[unit.pk] is True
    target_ids = {u.pk for u in target_units.values()}
    assert not [row for row in unit_changes(V) if row[0] in target_ids]


# --- Comandos ------------------------------------------------------------------------


@pytest.mark.django_db
def test_registrar_relacion_registers_and_listar_normas_shows_the_link(
    two_norms, read_write_user, read_user, typed_password
):
    """REQ-006: `registrar_relacion` registra la derogación con su fecha y su unidad de
    origen e informa la versión nueva de la normativa; después `listar_normas` muestra
    el vínculo en las dos normas."""
    source, target = two_norms["source"], two_norms["target"]
    typed_password()

    out = run("registrar_relacion", tipo="deroga", origen=source.pk,
              unidad_origen="art-2", alcanzada=target.pk, fecha="2023-01-01",
              usuario=read_write_user.username)

    relation = Relation.objects.get()
    assert relation.relation_type == "deroga"
    assert relation.effective_date == V
    assert f"Se registró la relación {relation.pk}" in out
    assert f"versión {current_corpus_version()} de la normativa" in out

    listed = run("listar_normas", usuario=read_user.username)
    source_block, target_block = (
        block for citation in ("Norma de origen sintética 2/2099",
                               "Norma alcanzada sintética 1/2099")
        for block in listed.split("\n\n") if block.startswith(citation)
    )
    assert "Vínculos:" in source_block
    assert (f"Deroga a Norma alcanzada sintética 1/2099 (norma {target.pk}) · "
            "origen: art-2 · alcanza: la norma entera · desde el 01/01/2023") in source_block
    assert (f"Derogada por Norma de origen sintética 2/2099 (norma {source.pk}) · "
            "origen: art-2 · alcanza: la norma entera · desde el 01/01/2023") in target_block


@pytest.mark.django_db
def test_listar_normas_without_links(two_norms, read_user, typed_password):
    """REQ-006: una norma sin relaciones lo dice en el listado."""
    typed_password()

    listed = run("listar_normas", usuario=read_user.username)

    assert "Vínculos: ninguno" in listed


@pytest.mark.django_db
def test_registrar_relacion_reports_refusals(two_norms, read_write_user, read_user,
                                            typed_password):
    """REQ-006, REQ-016: el comando informa en lenguaje llano una clave inexistente, una
    fecha mal escrita y un usuario de lectura, y no registra nada."""
    source, target = two_norms["source"], two_norms["target"]
    typed_password()
    base = {"tipo": "modifica", "origen": source.pk, "alcanzada": target.pk,
            "fecha": "2023-01-01"}

    with pytest.raises(CommandError, match="art-99"):
        run("registrar_relacion", **base, unidad_alcanzada="art-99",
            usuario=read_write_user.username)
    with pytest.raises(CommandError, match="AAAA-MM-DD"):
        run("registrar_relacion", **{**base, "fecha": "1/1/2023"},
            usuario=read_write_user.username)
    with pytest.raises(CommandError, match="permiso"):
        run("registrar_relacion", **base, usuario=read_user.username)

    assert not Relation.objects.exists()
