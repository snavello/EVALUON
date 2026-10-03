"""Esquema de normas, documentos, lecturas, unidades, pasajes, relaciones, modificatorias
sin cargar y versiones de la normativa (T-008; plan 001, "Modelo de datos").

Comprueba las restricciones que pone la base: lo que no se puede guardar no se guarda,
venga de donde venga. Los datos son sintéticos.
"""

import hashlib
from datetime import date

import pytest
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext

from evaluon.audit import services
from evaluon.audit.models import AuditEvent
from evaluon.norms.models import (
    CorpusVersion,
    Document,
    DocumentFile,
    Norm,
    Passage,
    PendingAmendment,
    Reading,
    Relation,
    Unit,
)

# --- Armado de datos sintéticos ----------------------------------------------------


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def make_norm(user, **overrides):
    values = {
        "category": "regimen_especifico",
        "norm_type": "disposicion",
        "number": "999",
        "year": 2099,
        "issuer": "organismo de prueba",
        "title": "Norma sintética de prueba",
        "created_by": user,
    }
    values.update(overrides)
    return Norm.objects.create(**values)


def make_document(norm, user, **overrides):
    values = {
        "norm": norm,
        "publication_date": date(2099, 1, 2),
        "effective_from": date(2099, 1, 3),
        "source": "https://example.org/norma-sintetica",
        "file_name": "norma.pdf",
        "file_format": "pdf",
        "file_size": 10,
        "file_sha256": sha(f"archivo {Document.objects.count()}"),
        "loaded_by": user,
    }
    values.update(overrides)
    return Document.objects.create(**values)


def make_reading(document, user, sequence=1):
    return Reading.objects.create(
        document=document,
        sequence=sequence,
        pages=[],
        canonical_text="ARTICULO 1.- Texto. ARTICULO 2.- Texto.",
        canonical_sha256=sha("canónico"),
        tool_versions={},
        report={},
        report_text="",
        created_by=user,
    )


def make_unit(reading, **overrides):
    values = {
        "reading": reading,
        "unit_type": "articulo",
        "number": "1",
        "label": "ARTICULO 1.-",
        "key": "art-1",
        "path": "Artículo 1",
        "order": 1,
        "char_start": 0,
        "char_end": 19,
        "text": "ARTICULO 1.- Texto.",
        "text_origin": "pdf_text",
    }
    values.update(overrides)
    return Unit.objects.create(**values)


# --- Tablas -------------------------------------------------------------------------


@pytest.mark.django_db
def test_tables_have_plan_names_and_passage_columns():
    """REQ-001, REQ-003: las tablas se llaman como en el plan; `norms_passage` tiene
    sus columnas, incluida `tsv`, que agrega T-009."""
    expected = {
        Norm: "norms_norm",
        Document: "norms_document",
        DocumentFile: "norms_document_file",
        Reading: "norms_reading",
        Unit: "norms_unit",
        Passage: "norms_passage",
        Relation: "norms_relation",
        PendingAmendment: "norms_pending_amendment",
        CorpusVersion: "norms_corpus_version",
    }
    tables = set(connection.introspection.table_names())
    for model, table in expected.items():
        assert model._meta.db_table == table
        assert table in tables

    with connection.cursor() as cursor:
        columns = {
            c.name
            for c in connection.introspection.get_table_description(
                cursor, "norms_passage"
            )
        }
    assert {"unit_id", "order", "char_start", "char_end", "header", "text", "tsv",
            "embedding", "embedding_model", "embedding_revision"} <= columns


@pytest.mark.django_db
def test_vector_and_unaccent_extensions_are_installed():
    """REQ-008, REQ-010: la primera migración de `norms` instala las extensiones
    `vector` (vectores de los pasajes) y `unaccent` (búsqueda sin acentos, T-009)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT extname FROM pg_extension WHERE extname IN ('vector', 'unaccent')"
        )
        installed = {row[0] for row in cursor.fetchall()}
    assert installed == {"vector", "unaccent"}


# --- Normas -------------------------------------------------------------------------


@pytest.mark.django_db
def test_norm_and_document_keep_the_req_001_data(read_write_user):
    """REQ-001: la norma y su documento guardan tipo, número, organismo, título, fecha
    de publicación, fecha de vigencia y fuente, y se leen igual."""
    norm = make_norm(read_write_user)
    document = make_document(norm, read_write_user)

    stored_norm = Norm.objects.get(pk=norm.pk)
    stored_document = Document.objects.get(pk=document.pk)
    assert (stored_norm.norm_type, stored_norm.number, stored_norm.year,
            stored_norm.issuer, stored_norm.title) == (
        "disposicion", "999", 2099, "organismo de prueba", "Norma sintética de prueba")
    assert stored_document.publication_date == date(2099, 1, 2)
    assert stored_document.effective_from == date(2099, 1, 3)
    assert stored_document.effective_to is None
    assert stored_document.source == "https://example.org/norma-sintetica"
    assert stored_document.norm_id == norm.pk


@pytest.mark.django_db
@pytest.mark.parametrize("category", ["", "otra_cosa"])
def test_norm_without_valid_category_is_not_saved(read_write_user, category):
    """REQ-017: una norma sin categoría, o con una que no es de las cinco, no se
    guarda."""
    with pytest.raises(IntegrityError), transaction.atomic():
        make_norm(read_write_user, category=category)
    assert not Norm.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "category",
    ["regimen_especifico", "otra_normativa", "marco_nacional", "dictamen_legal",
     "recomendacion_auditoria"],
)
def test_the_five_categories_are_accepted(read_write_user, category):
    """REQ-017: las cinco categorías de la spec se guardan."""
    norm = make_norm(read_write_user, category=category)
    assert Norm.objects.get(pk=norm.pk).category == category


@pytest.mark.django_db
def test_same_type_number_year_and_issuer_is_not_saved_twice(read_write_user):
    """REQ-011: tipo, número, año y organismo identifican la norma: la misma norma no
    se guarda dos veces; con otro organismo sí."""
    make_norm(read_write_user)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_norm(read_write_user, title="Otro título")
    make_norm(read_write_user, issuer="otro organismo")
    assert Norm.objects.count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    "category",
    ["otra_normativa", "marco_nacional", "dictamen_legal", "recomendacion_auditoria"],
)
def test_only_a_specific_regime_can_be_a_general_regime(read_write_user, category):
    """REQ-020: una norma de otra categoría no se puede marcar como régimen general."""
    with pytest.raises(IntegrityError), transaction.atomic():
        make_norm(read_write_user, category=category, general_regime=True)
    assert not Norm.objects.exists()


@pytest.mark.django_db
def test_specific_regime_can_be_a_general_regime_and_defaults_to_false(read_write_user):
    """REQ-020: una norma de categoría `regimen_especifico` se puede marcar como régimen
    general; sin indicarlo, la marca es falsa."""
    general = make_norm(read_write_user, general_regime=True)
    other = make_norm(read_write_user, number="1000")
    assert Norm.objects.get(pk=general.pk).general_regime is True
    assert Norm.objects.get(pk=other.pk).general_regime is False


# --- Documentos ---------------------------------------------------------------------


@pytest.mark.django_db
def test_two_documents_with_the_same_hash_are_not_saved(read_write_user):
    """REQ-011: dos documentos con la misma huella de archivo no se guardan, aunque
    sean de normas distintas."""
    first = make_norm(read_write_user)
    second = make_norm(read_write_user, number="1000")
    make_document(first, read_write_user, file_sha256=sha("mismo archivo"))
    with pytest.raises(IntegrityError), transaction.atomic():
        make_document(second, read_write_user, file_sha256=sha("mismo archivo"))
    assert Document.objects.count() == 1


@pytest.mark.django_db
def test_part_defaults_to_body_and_accepts_annex_keys(read_write_user):
    """REQ-020, REQ-011: la parte es `cuerpo` por omisión y admite la clave de un
    anexo (`anexo`, `anexo-i`, `anexo-ii`)."""
    norm = make_norm(read_write_user)
    body = make_document(norm, read_write_user)
    assert Document.objects.get(pk=body.pk).part == "cuerpo"
    for part in ("anexo", "anexo-i", "anexo-ii"):
        document = make_document(norm, read_write_user, part=part)
        assert Document.objects.get(pk=document.pk).part == part


@pytest.mark.django_db
@pytest.mark.parametrize("part", ["", "Anexo", "apendice", "anexo i", "cuerpo-2"])
def test_part_other_than_body_or_annex_key_is_not_saved(read_write_user, part):
    """REQ-020, REQ-011: una parte que no es `cuerpo` ni la clave de un anexo no se
    guarda."""
    norm = make_norm(read_write_user)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_document(norm, read_write_user, part=part)


@pytest.mark.django_db
def test_body_and_annex_in_use_at_once_but_not_two_of_the_same_part(read_write_user):
    """REQ-011: el cuerpo y el anexo de una misma norma pueden estar en uso a la vez
    con la misma versión; dos documentos de la misma parte y versión en uso, no. Otra
    versión de la misma parte sí puede estar en uso."""
    norm = make_norm(read_write_user, general_regime=True)
    make_document(norm, read_write_user, part="cuerpo", version_number=1, in_use=True)
    make_document(norm, read_write_user, part="anexo", version_number=1, in_use=True)

    with pytest.raises(IntegrityError), transaction.atomic():
        make_document(
            norm, read_write_user, part="anexo", version_number=1, in_use=True
        )

    # Un segundo documento de la misma parte, validado pero sin usar, sí se guarda.
    make_document(norm, read_write_user, part="anexo", version_number=1, in_use=False)
    # La versión siguiente de la misma parte también puede estar en uso.
    make_document(norm, read_write_user, part="anexo", version_number=2, in_use=True)

    assert Document.objects.filter(norm=norm, in_use=True).count() == 3


@pytest.mark.django_db
def test_document_in_use_needs_a_version_number(read_write_user):
    """REQ-011: un documento en uso es el de una versión: sin número de versión no
    puede estar en uso (así no hay dos en uso de la misma parte sin versión)."""
    norm = make_norm(read_write_user)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_document(norm, read_write_user, in_use=True, version_number=None)


@pytest.mark.django_db
def test_original_file_is_kept_byte_by_byte(read_write_user):
    """REQ-002: el archivo original se guarda aparte, byte por byte."""
    content = bytes(range(256)) * 4
    document = make_document(
        make_norm(read_write_user),
        read_write_user,
        file_size=len(content),
        file_sha256=hashlib.sha256(content).hexdigest(),
    )
    DocumentFile.objects.create(document=document, content=content)

    stored = bytes(DocumentFile.objects.get(document=document).content)
    assert stored == content
    assert hashlib.sha256(stored).hexdigest() == document.file_sha256


# --- Lecturas y unidades ------------------------------------------------------------


@pytest.mark.django_db
def test_two_units_with_the_same_key_in_a_reading_are_not_saved(read_write_user):
    """REQ-003: dos unidades con la misma clave en una lectura no se guardan; la misma
    clave en otra lectura sí."""
    document = make_document(make_norm(read_write_user), read_write_user)
    reading = make_reading(document, read_write_user)
    make_unit(reading)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_unit(reading, order=2, label="ARTICULO 1.- (repetido)")

    other_reading = make_reading(document, read_write_user, sequence=2)
    make_unit(other_reading)
    assert Unit.objects.filter(key="art-1").count() == 2


@pytest.mark.django_db
def test_unit_types_are_the_seven_of_the_plan(read_write_user):
    """REQ-003: `unit_type` admite los siete tipos del plan, incluido `clausula`, que se
    guarda sin número; un tipo que no está en la lista no se guarda."""
    reading = make_reading(
        make_document(make_norm(read_write_user), read_write_user), read_write_user
    )
    root = make_unit(
        reading, unit_type="anexo", number="", key="anexo", path="Anexo", order=1
    )
    types = ["articulo", "inciso", "considerando", "punto", "parrafo"]
    for order, unit_type in enumerate(types, start=2):
        make_unit(
            reading,
            parent=root,
            unit_type=unit_type,
            key=f"anexo/{unit_type}-1",
            order=order,
        )
    clause = make_unit(
        reading,
        parent=root,
        unit_type="clausula",
        number="",
        label="CLÁUSULA TRANSITORIA REGISTRO DE PROVEEDORES",
        key="anexo/clausula-transitoria",
        path="Anexo › Cláusula transitoria",
        order=10,
    )

    stored = Unit.objects.get(pk=clause.pk)
    assert stored.unit_type == "clausula"
    assert stored.number == ""
    assert stored.parent_id == root.pk
    assert set(Unit.objects.values_list("unit_type", flat=True)) == {
        "anexo", "articulo", "inciso", "considerando", "punto", "parrafo", "clausula"
    }

    with pytest.raises(IntegrityError), transaction.atomic():
        make_unit(reading, unit_type="titulo", key="titulo-1", order=11)


@pytest.mark.django_db
def test_reading_status_and_text_origin_only_take_plan_values(read_write_user):
    """REQ-003: el estado de una lectura empieza en `pending` y solo admite los valores
    del plan; el origen del texto de una unidad, también."""
    document = make_document(make_norm(read_write_user), read_write_user)
    reading = make_reading(document, read_write_user)
    assert Reading.objects.get(pk=reading.pk).status == "pending"

    with pytest.raises(IntegrityError), transaction.atomic():
        Reading.objects.filter(pk=reading.pk).update(status="aprobada")
    with pytest.raises(IntegrityError), transaction.atomic():
        make_unit(reading, text_origin="manual")
    with pytest.raises(IntegrityError), transaction.atomic():
        make_reading(document, read_write_user, sequence=1)


@pytest.mark.django_db
def test_passage_keeps_a_1024_dimension_vector(read_write_user):
    """REQ-003: un pasaje pertenece a una unidad y guarda su vector de 1024
    dimensiones con el modelo que lo calculó."""
    reading = make_reading(
        make_document(make_norm(read_write_user), read_write_user), read_write_user
    )
    unit = make_unit(reading)
    vector = [0.0] * 1024
    vector[0] = 1.0
    passage = Passage.objects.create(
        unit=unit,
        order=1,
        char_start=0,
        char_end=19,
        header="Disposición 999/2099, artículo 1",
        text="ARTICULO 1.- Texto.",
        embedding=vector,
        embedding_model="bge-m3",
        embedding_revision=sha("modelo"),
    )
    stored = Passage.objects.get(pk=passage.pk)
    assert len(stored.embedding) == 1024
    assert stored.embedding[0] == 1.0
    assert stored.unit_id == unit.pk


# --- Relaciones y modificatorias sin cargar -----------------------------------------


@pytest.mark.django_db
def test_relation_types_are_the_four_of_the_plan(read_write_user):
    """REQ-020: una relación `deroga` entre normas enteras se guarda con su fecha (así
    se registra la abrogación de un régimen); un tipo fuera de la lista no se guarda."""
    old = make_norm(read_write_user, general_regime=True)
    new = make_norm(read_write_user, number="1000", general_regime=True)
    for relation_type in ("modifica", "complementa", "reglamenta", "deroga"):
        Relation.objects.create(
            relation_type=relation_type,
            source_norm=new,
            target_norm=old,
            source_unit_key="art-2",
            effective_date=date(2099, 6, 1),
            registered_by=read_write_user,
        )
    repeal = Relation.objects.get(relation_type="deroga")
    assert repeal.target_unit_key == ""
    assert repeal.effective_date == date(2099, 6, 1)

    with pytest.raises(IntegrityError), transaction.atomic():
        Relation.objects.create(
            relation_type="abroga",
            source_norm=new,
            target_norm=old,
            effective_date=date(2099, 6, 1),
            registered_by=read_write_user,
        )


@pytest.mark.django_db
def test_same_pending_amendment_is_not_recorded_twice_for_a_norm(read_write_user):
    """REQ-021: la misma modificatoria (tipo, número, año y organismo) no se anota dos
    veces para una norma; para otra norma, o de otro organismo, sí."""
    target = make_norm(read_write_user)
    other_target = make_norm(read_write_user, number="1000")
    values = {
        "norm_type": "disposicion",
        "number": "5",
        "year": 2100,
        "issuer": "organismo de prueba",
        "source_ref": "https://example.org/modificatoria-5",
        "registered_by": read_write_user,
    }
    PendingAmendment.objects.create(target_norm=target, **values)
    with pytest.raises(IntegrityError), transaction.atomic():
        PendingAmendment.objects.create(target_norm=target, **values)

    PendingAmendment.objects.create(target_norm=other_target, **values)
    PendingAmendment.objects.create(
        target_norm=target, **{**values, "issuer": "otro organismo"}
    )
    pending = PendingAmendment.objects.get(target_norm=other_target)
    assert pending.loaded_norm is None
    assert PendingAmendment.objects.count() == 3


# --- Versión de la normativa en el registro de auditoría ----------------------------


@pytest.mark.django_db
def test_event_before_any_corpus_version_has_no_version(read_user):
    """REQ-012: sin ninguna versión de la normativa creada, el hecho queda sin
    versión."""
    event = services.record("login", outcome="ok", channel="screen", user=read_user)
    assert AuditEvent.objects.get(pk=event.pk).corpus_version is None
    assert services.current_corpus_version() is None


@pytest.mark.django_db
def test_event_after_a_corpus_version_carries_its_number_without_updates(
    read_write_user, read_user
):
    """REQ-012: un hecho registrado después de crear una versión de la normativa lleva
    su número. El hecho que crea la versión ya nace con el número nuevo, la versión
    apunta a ese hecho, y en todo el proceso no hay ningún UPDATE sobre
    `audit_event`."""
    with CaptureQueriesContext(connection) as queries:
        with transaction.atomic():
            origin = services.record(
                "validation",
                outcome="ok",
                channel="command",
                user=read_write_user,
                detail={"reading": 1},
                creates_corpus_version=True,
            )
        later = services.record(
            "query", outcome="ok", channel="screen", user=read_user
        )

    version = CorpusVersion.objects.get()
    stored_origin = AuditEvent.objects.get(pk=origin.pk)
    assert version.event_id == origin.pk
    assert stored_origin.corpus_version == version.pk
    assert stored_origin.detail == {"reading": 1, "new_corpus_version": version.pk}
    assert AuditEvent.objects.get(pk=later.pk).corpus_version == version.pk
    assert services.current_corpus_version() == version.pk

    statements = [q["sql"].upper() for q in queries.captured_queries]
    assert not [s for s in statements if s.startswith("UPDATE") and "AUDIT_EVENT" in s]


@pytest.mark.django_db
def test_each_new_corpus_version_is_greater_and_later_events_follow_it(
    read_write_user,
):
    """REQ-012: cada versión nueva tiene un número mayor que la anterior, y los hechos
    siguientes llevan el de la última."""
    numbers = []
    for event_type in ("validation", "relation", "pending_amendment"):
        with transaction.atomic():
            event = services.record(
                event_type,
                outcome="ok",
                channel="command",
                user=read_write_user,
                creates_corpus_version=True,
            )
        numbers.append(event.corpus_version)
        after = services.record(
            "search", outcome="ok", channel="screen", user=read_write_user
        )
        assert after.corpus_version == event.corpus_version

    assert numbers == sorted(numbers)
    assert len(set(numbers)) == 3
    assert CorpusVersion.objects.count() == 3


@pytest.mark.django_db
def test_a_rejected_or_failed_event_does_not_create_a_corpus_version(read_write_user):
    """REQ-012: solo un hecho con resultado `ok` crea una versión de la normativa; si
    se pide con otro resultado, no se registra nada."""
    for outcome in ("rejected", "failed"):
        with pytest.raises(ValueError), transaction.atomic():
            services.record(
                "validation",
                outcome=outcome,
                channel="command",
                user=read_write_user,
                creates_corpus_version=True,
            )
    assert not CorpusVersion.objects.exists()
    assert not AuditEvent.objects.exists()


@pytest.mark.django_db
def test_a_corpus_version_cannot_point_to_an_event_already_used(read_write_user):
    """REQ-012: cada versión apunta a un hecho distinto: dos versiones no comparten el
    hecho que las originó."""
    with transaction.atomic():
        origin = services.record(
            "relation",
            outcome="ok",
            channel="command",
            user=read_write_user,
            creates_corpus_version=True,
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        CorpusVersion.objects.create(event=origin)
