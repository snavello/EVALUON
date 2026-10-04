"""Tablas, tipos de hecho y parámetros de la 003 (T-067; plan 003, "Modelo de datos",
"Parámetros" y "Registro de auditoría").

Las restricciones van en la base, para que valgan venga de donde venga la escritura: se
prueban con el ORM y, cuando hace falta, con SQL directo. Todos los textos son
sintéticos (P4).
"""

import hashlib
import itertools
from datetime import date
from io import StringIO

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.utils import timezone

from evaluon.audit import services as audit
from evaluon.audit.models import AuditEvent
from evaluon.tenders import models as m

_counter = itertools.count(1)

CANONICAL = (
    "SECCIÓN I - CONDICIONES PARTICULARES\n"
    "11.3. La garantía de mantenimiento de la oferta deberá ser individualizada.\n"
    "1.1. Renglón 1: equipo con 16 GB de RAM.\n"
)


def sha(seed):
    return hashlib.sha256(str(seed).encode()).hexdigest()


@pytest.fixture
def procedure(read_write_user):
    return m.Procedure.objects.create(
        number=f"PROC-SINT-{next(_counter)}",
        procedure_type="Licitación pública",
        subject="Objeto sintético",
        authorization_date=date(2025, 11, 14),
        created_by=read_write_user,
    )


@pytest.fixture
def make_tender_document(read_write_user):
    def make(procedure, **fields):
        values = {
            "kind": m.DocumentKind.PLIEGO,
            "title": "Pliego sintético",
            "file_name": "pliego.pdf",
            "file_format": "pdf",
            "file_size": 10,
            "file_sha256": sha(next(_counter)),
            "loaded_by": read_write_user,
        }
        values.update(fields)
        return m.Document.objects.create(procedure=procedure, **values)

    return make


@pytest.fixture
def segments(procedure, make_tender_document):
    """Una lectura con dos tramos: una cláusula formal y una técnica."""
    document = make_tender_document(procedure)
    reading = m.Reading.objects.create(
        document=document,
        sequence=1,
        pages=[],
        canonical_text=CANONICAL,
        canonical_sha256=sha(CANONICAL),
        tool_versions={},
        report={},
    )
    start_a = CANONICAL.index("11.3.")
    end_a = CANONICAL.index("\n", start_a)
    start_b = CANONICAL.index("1.1.")
    end_b = len(CANONICAL) - 1
    a = m.Segment.objects.create(
        reading=reading, order=1, key="sec-i/11.3", segment_type="clausula",
        char_start=start_a, char_end=end_a, text=CANONICAL[start_a:end_a],
        text_origin="pdf_text",
    )
    b = m.Segment.objects.create(
        reading=reading, order=2, key="sec-iii/1.1", segment_type="clausula",
        section_class="tecnico", items=[1],
        char_start=start_b, char_end=end_b, text=CANONICAL[start_b:end_b],
        text_origin="pdf_text",
    )
    return a, b


@pytest.fixture
def draft(procedure, read_write_user):
    return m.MatrixVersion.objects.create(
        procedure=procedure, number=1, level="alta", created_by=read_write_user
    )


def add_requirement(version, number, category, items=()):
    return m.Requirement.objects.create(
        version=version, number=number, category=category, items=list(items),
        origin="propuesto",
    )


def add_quote(requirement, segment, order=1, scope=""):
    return m.RequirementQuote.objects.create(
        requirement=requirement, order=order, segment=segment,
        char_start=segment.char_start, char_end=segment.char_end, text=segment.text,
        scope=scope,
    )


def validate(version, user):
    m.MatrixVersion.objects.filter(pk=version.pk).update(
        status="validated", validated_at=timezone.now(), validated_by=user
    )


def check_deferred():
    """Los controles diferidos se comprueban al confirmar; las pruebas no confirman."""
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


# --- Tablas ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tables_have_plan_names():
    """REQ-022, REQ-023, REQ-024, REQ-025, REQ-026, REQ-027, REQ-028, REQ-029, REQ-031:
    las tablas de la 003 existen con los nombres del plan."""
    expected = {
        "tenders_procedure", "tenders_document", "tenders_document_file",
        "tenders_reading", "tenders_segment", "tenders_job", "tenders_matrix_run",
        "tenders_run_step", "tenders_disposition", "tenders_matrix_version",
        "tenders_requirement", "tenders_requirement_quote",
        "tenders_requirement_source", "tenders_consequence", "tenders_pending_item",
        "tenders_requirement_change",
    }
    assert expected <= set(connection.introspection.table_names())


@pytest.mark.django_db
def test_no_model_changes_without_migration():
    """REQ-024: los modelos y las migraciones coinciden (`makemigrations --check`)."""
    call_command("makemigrations", "--check", "--dry-run", stdout=StringIO())


# --- Procedimiento y documentos -------------------------------------------------------


@pytest.mark.django_db
def test_procedure_number_is_unique(procedure, read_write_user):
    """REQ-022: el número del procedimiento es único."""
    with pytest.raises(IntegrityError), transaction.atomic():
        m.Procedure.objects.create(
            number=procedure.number, procedure_type="Otro", subject="Otro",
            authorization_date=date(2023, 1, 2), created_by=read_write_user,
        )


@pytest.mark.django_db
def test_same_file_twice_in_procedure_rejected(
    procedure, make_tender_document, read_write_user
):
    """REQ-023: la huella del archivo es única dentro del procedimiento; en otro
    procedimiento, el mismo archivo se acepta."""
    document = make_tender_document(procedure)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_tender_document(procedure, file_sha256=document.file_sha256)

    other = m.Procedure.objects.create(
        number="PROC-SINT-OTRO", procedure_type="Licitación privada", subject="Otro",
        authorization_date=date(2023, 1, 2), created_by=read_write_user,
    )
    make_tender_document(other, file_sha256=document.file_sha256)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "kind", ["circular_modificatoria", "circular_aclaratoria", "respuesta_consulta"]
)
def test_circulars_and_answers_require_date(procedure, make_tender_document, kind):
    """REQ-031: una circular o una respuesta sin fecha se rechaza; con fecha, se acepta."""
    with pytest.raises(IntegrityError), transaction.atomic():
        make_tender_document(procedure, kind=kind)
    make_tender_document(procedure, kind=kind, issued_on=date(2025, 11, 20))


@pytest.mark.django_db
def test_original_file_kept_byte_by_byte(procedure, make_tender_document):
    """REQ-023: el original se guarda tal cual, aparte del documento."""
    content = b"%PDF-1.7\x00\xffsintetico"
    document = make_tender_document(procedure, file_sha256=sha(content))
    m.DocumentFile.objects.create(document=document, content=content)
    assert bytes(m.DocumentFile.objects.get(pk=document.pk).content) == content


# --- Restricciones de valores ---------------------------------------------------------


def _bad_values(procedure, segments, draft, user):
    """Pares (descripción, función que inserta un valor inválido)."""
    a, _ = segments
    job = m.Job.objects.create(
        kind="propose_matrix", procedure=procedure, requested_by=user
    )
    run = m.MatrixRun.objects.create(
        procedure=procedure, level="media", channel="screen",
        authorization_date=procedure.authorization_date,
    )
    requirement = add_requirement(draft, 99, "formal")
    add_quote(requirement, a)
    return {
        "document.kind": lambda: m.Document.objects.create(
            procedure=procedure, kind="borrador", title="x", file_name="x.pdf",
            file_format="pdf", file_size=1, file_sha256=sha("x"), loaded_by=user,
        ),
        "document.sha256": lambda: m.Document.objects.create(
            procedure=procedure, kind="pliego", title="x", file_name="x.pdf",
            file_format="pdf", file_size=1, file_sha256="no-es-huella", loaded_by=user,
        ),
        "segment.type": lambda: m.Segment.objects.create(
            reading=a.reading, order=50, key="x1", segment_type="capitulo",
            char_start=0, char_end=1,
        ),
        "segment.section_class": lambda: m.Segment.objects.create(
            reading=a.reading, order=51, key="x2", segment_type="clausula",
            section_class="juridico", char_start=0, char_end=1,
        ),
        "segment.review_reason": lambda: m.Segment.objects.create(
            reading=a.reading, order=52, key="x3", segment_type="clausula",
            review_reason="otro", char_start=0, char_end=1,
        ),
        "segment.items": lambda: m.Segment.objects.create(
            reading=a.reading, order=53, key="x4", segment_type="clausula",
            items={"renglon": 1}, char_start=0, char_end=1,
        ),
        "segment.char_range": lambda: m.Segment.objects.create(
            reading=a.reading, order=54, key="x5", segment_type="clausula",
            char_start=5, char_end=1,
        ),
        "job.kind": lambda: m.Job.objects.create(
            kind="otro", procedure=procedure, requested_by=user
        ),
        "job.status": lambda: m.Job.objects.create(
            kind="propose_matrix", status="paused", procedure=procedure,
            requested_by=user,
        ),
        "job.read_without_document": lambda: m.Job.objects.create(
            kind="read_document", procedure=procedure, requested_by=user
        ),
        "run.level": lambda: m.MatrixRun.objects.create(
            procedure=procedure, level="baja", channel="screen",
            authorization_date=procedure.authorization_date, job=job,
        ),
        "run.channel": lambda: m.MatrixRun.objects.create(
            procedure=procedure, level="alta", channel="command",
            authorization_date=procedure.authorization_date,
        ),
        "step.pass_name": lambda: m.RunStep.objects.create(
            run=run, pass_name="resumen", batch=1, request={}
        ),
        "disposition.outcome": lambda: m.Disposition.objects.create(
            run=run, segment=a, outcome="ignorado", source="modelo"
        ),
        "disposition.discard_reason": lambda: m.Disposition.objects.create(
            run=run, segment=a, outcome="descartado", discard_reason="aburrido",
            source="modelo",
        ),
        "disposition.discard_without_reason": lambda: m.Disposition.objects.create(
            run=run, segment=a, outcome="descartado", source="modelo"
        ),
        "disposition.source": lambda: m.Disposition.objects.create(
            run=run, segment=a, outcome="pendiente", source="persona"
        ),
        "version.status": lambda: m.MatrixVersion.objects.create(
            procedure=procedure, number=7, status="archived", level="alta",
            created_by=user,
        ),
        "version.level": lambda: m.MatrixVersion.objects.create(
            procedure=procedure, number=8, status="discarded", level="baja",
            created_by=user, discarded_at=timezone.now(), discarded_by=user,
        ),
        "version.validated_without_who": lambda: m.MatrixVersion.objects.create(
            procedure=procedure, number=9, status="validated", level="alta",
            created_by=user,
        ),
        "requirement.category": lambda: add_requirement(draft, 50, "juridico"),
        "requirement.origin": lambda: m.Requirement.objects.create(
            version=draft, number=51, category="formal", origin="modelo"
        ),
        "requirement.state": lambda: m.Requirement.objects.create(
            version=draft, number=52, category="formal", origin="propuesto",
            state="dudoso",
        ),
        "requirement.technical_two_items": lambda: add_requirement(
            draft, 53, "tecnico", items=[1, 2]
        ),
        "quote.scope": lambda: add_quote(
            add_requirement(draft, 54, "tecnico"), a, scope="parcial"
        ),
        "quote.flag": lambda: m.RequirementQuote.objects.create(
            requirement=add_requirement(draft, 55, "tecnico"), order=1, segment=a,
            char_start=0, char_end=1, text="S", quote_flag="dudosa",
        ),
        "source.effect": lambda: m.RequirementSource.objects.create(
            requirement=requirement, effect="reemplaza", segment=a, char_start=0,
            char_end=1, text="S", issued_on=date(2025, 11, 20),
        ),
        "consequence.type": lambda: m.Consequence.objects.create(
            requirement=requirement, consequence_type="multa", origin="sistema"
        ),
        "consequence.system_conditional": lambda: m.Consequence.objects.create(
            requirement=requirement, consequence_type="aprobacion_condicionada",
            origin="sistema",
        ),
        "consequence.system_approve_anyway": lambda: m.Consequence.objects.create(
            requirement=requirement, consequence_type="aprobar_igual",
            origin="sistema",
        ),
        "consequence.undetermined_by_person": lambda: m.Consequence.objects.create(
            requirement=requirement, consequence_type="no_determinada",
            origin="persona",
        ),
        "consequence.undetermined_chosen": lambda: m.Consequence.objects.create(
            requirement=requirement, consequence_type="no_determinada",
            origin="sistema", chosen=True, chosen_by=user, chosen_at=timezone.now(),
        ),
        "consequence.chosen_without_who": lambda: m.Consequence.objects.create(
            requirement=requirement, consequence_type="desestimacion",
            origin="sistema", chosen=True,
        ),
        "pending.reason": lambda: m.PendingItem.objects.create(
            version=draft, segment=a, reason="aburrido"
        ),
        "pending.resolution_without_who": lambda: m.PendingItem.objects.create(
            version=draft, segment=a, reason="tabla", resolution="sin_requisitos"
        ),
        "pending.who_without_resolution": lambda: m.PendingItem.objects.create(
            version=draft, segment=a, reason="tabla", resolved_by=user,
            resolved_at=timezone.now(),
        ),
        "change.action": lambda: m.RequirementChange.objects.create(
            requirement=requirement, action="borrar", user=user,
            event=audit.record(
                "requirement_change", outcome="ok", channel="screen", user=user
            ),
        ),
    }


@pytest.mark.django_db
def test_invalid_values_rejected_by_database(
    procedure, segments, draft, read_write_user
):
    """REQ-024, REQ-025, REQ-026, REQ-027, REQ-028, REQ-029, REQ-030, REQ-031: la base
    rechaza los valores fuera de las listas del plan y las combinaciones que el plan
    prohíbe (un técnico con dos renglones, el sistema sugiriendo una aprobación
    condicionada, un descarte sin motivo, una validación sin evaluador)."""
    cases = _bad_values(procedure, segments, draft, read_write_user)
    accepted = []
    for name, insert in cases.items():
        try:
            with transaction.atomic():
                insert()
        except IntegrityError:
            continue
        accepted.append(name)
    assert accepted == []


@pytest.mark.django_db
def test_valid_values_accepted(procedure, segments, draft, read_write_user):
    """REQ-024, REQ-029: los valores del plan se aceptan, incluidas las consecuencias que
    solo elige un evaluador cuando las pone una persona."""
    a, b = segments
    formal = add_requirement(draft, 1, "formal")
    add_quote(formal, a)
    technical = add_requirement(draft, 2, "tecnico", items=[1])
    add_quote(technical, b, order=1, scope="propia")
    add_quote(technical, a, order=2, scope="general")
    for code in m.ConsequenceType.values:
        origin = "sistema" if code == "no_determinada" else "persona"
        m.Consequence.objects.create(
            requirement=formal, consequence_type=code, origin=origin
        )
    m.Consequence.objects.create(
        requirement=formal, consequence_type="desestimacion", origin="sistema",
        chosen=True, chosen_by=read_write_user, chosen_at=timezone.now(),
        grounds=[{"segment": a.pk, "char_start": a.char_start, "char_end": a.char_end}],
    )
    m.PendingItem.objects.create(
        version=draft, segment=b, reason="renglon_sin_especificaciones",
        resolution="sin_requisitos", resolved_by=read_write_user,
        resolved_at=timezone.now(),
    )
    check_deferred()
    assert len(m.ConsequenceType.values) == 7


@pytest.mark.django_db
def test_only_one_chosen_consequence_per_requirement(
    segments, draft, read_write_user
):
    """REQ-029: un requisito tiene una sola consecuencia elegida."""
    requirement = add_requirement(draft, 1, "economico")
    add_quote(requirement, segments[0])
    for code in ("desestimacion", "intimacion_subsanar"):
        values = dict(
            requirement=requirement, consequence_type=code, origin="sistema",
            chosen=True, chosen_by=read_write_user, chosen_at=timezone.now(),
        )
        if code == "desestimacion":
            m.Consequence.objects.create(**values)
        else:
            with pytest.raises(IntegrityError), transaction.atomic():
                m.Consequence.objects.create(**values)


# --- Versiones ------------------------------------------------------------------------


@pytest.mark.django_db
def test_one_draft_per_procedure(procedure, draft, read_write_user):
    """REQ-027: un procedimiento tiene a lo sumo un borrador; con el anterior validado,
    se puede abrir otro."""
    with pytest.raises(IntegrityError), transaction.atomic():
        m.MatrixVersion.objects.create(
            procedure=procedure, number=2, level="alta", created_by=read_write_user
        )
    validate(draft, read_write_user)
    m.MatrixVersion.objects.create(
        procedure=procedure, number=2, level="alta", based_on=draft,
        created_by=read_write_user,
    )


@pytest.mark.django_db
def test_version_number_unique_in_procedure(procedure, draft, read_write_user):
    """REQ-027: el número de versión es correlativo y único dentro del procedimiento."""
    validate(draft, read_write_user)
    with pytest.raises(IntegrityError), transaction.atomic():
        m.MatrixVersion.objects.create(
            procedure=procedure, number=1, level="alta", created_by=read_write_user
        )


# --- Citas ----------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("category", ["formal", "economico"])
def test_formal_or_economic_with_two_quotes_rejected(segments, draft, category):
    """REQ-025: un formal o un económico tiene una sola cita; la segunda se rechaza."""
    a, b = segments
    requirement = add_requirement(draft, 1, category)
    add_quote(requirement, a)
    with pytest.raises(DatabaseError) as rejected, transaction.atomic():
        add_quote(requirement, b, order=2)
    assert "una sola cita" in str(rejected.value)


@pytest.mark.django_db
def test_formal_without_quote_rejected_at_commit(draft):
    """REQ-025: un formal o un económico sin cita se rechaza al confirmar. (El requisito
    se inserta dentro del bloque para que el rechazo lo deshaga: al terminar cada
    prueba, Django vuelve a comprobar los controles diferidos.)"""
    with pytest.raises(DatabaseError) as rejected, transaction.atomic():
        add_requirement(draft, 1, "formal")
        check_deferred()
    assert "exactamente una cita" in str(rejected.value)


@pytest.mark.django_db
def test_removing_the_only_quote_rejected_at_commit(segments, draft):
    """REQ-025: quitar la única cita de un formal deja el requisito sin cita: se
    rechaza al confirmar."""
    requirement = add_requirement(draft, 1, "formal")
    quote = add_quote(requirement, segments[0])
    check_deferred()
    with pytest.raises(DatabaseError), transaction.atomic():
        m.RequirementQuote.objects.filter(pk=quote.pk).delete()
        check_deferred()


@pytest.mark.django_db
def test_technical_to_formal_with_two_quotes_rejected(segments, draft):
    """REQ-025: un técnico con dos citas no puede pasar a formal."""
    a, b = segments
    requirement = add_requirement(draft, 1, "tecnico", items=[1])
    add_quote(requirement, b, order=1, scope="propia")
    add_quote(requirement, a, order=2, scope="general")
    with pytest.raises(DatabaseError), transaction.atomic():
        m.Requirement.objects.filter(pk=requirement.pk).update(category="formal")


@pytest.mark.django_db
def test_technical_row_has_many_quotes(segments, draft):
    """REQ-024, REQ-025: una fila técnica cita varios tramos (propios y generales)."""
    a, b = segments
    requirement = add_requirement(draft, 1, "tecnico", items=[1])
    add_quote(requirement, b, order=1, scope="propia")
    add_quote(requirement, a, order=2, scope="general")
    check_deferred()
    assert requirement.quotes.count() == 2


# --- Inmutabilidad de una versión validada (REQ-027) ----------------------------------


@pytest.fixture
def validated(procedure, segments, draft, read_write_user):
    """Una versión validada con un requisito, su cita, una fuente, una consecuencia
    elegida y un pendiente resuelto."""
    a, b = segments
    requirement = add_requirement(draft, 1, "formal")
    quote = add_quote(requirement, a)
    source = m.RequirementSource.objects.create(
        requirement=requirement, quote=quote, effect="aclara", segment=b,
        char_start=b.char_start, char_end=b.char_end, text=b.text,
        issued_on=date(2025, 11, 20),
    )
    consequence = m.Consequence.objects.create(
        requirement=requirement, consequence_type="desestimacion", origin="sistema",
        chosen=True, chosen_by=read_write_user, chosen_at=timezone.now(),
    )
    pending = m.PendingItem.objects.create(
        version=draft, segment=b, reason="tabla", resolution="sin_requisitos",
        resolved_by=read_write_user, resolved_at=timezone.now(),
    )
    validate(draft, read_write_user)
    return {
        "tenders_requirement": (requirement, "state", "'quitado'"),
        "tenders_requirement_quote": (quote, "text", "'otro texto'"),
        "tenders_requirement_source": (source, "effect", "'modifica'"),
        "tenders_consequence": (consequence, "chosen_note", "'otro motivo'"),
        "tenders_pending_item": (pending, "reason", "'no_ubicado'"),
    }


TABLES = [
    "tenders_requirement",
    "tenders_requirement_quote",
    "tenders_requirement_source",
    "tenders_consequence",
    "tenders_pending_item",
]


@pytest.mark.django_db
@pytest.mark.parametrize("table", TABLES)
def test_update_on_validated_version_rejected_by_database(validated, table):
    """REQ-027: la base rechaza un UPDATE sobre los requisitos, citas, fuentes,
    consecuencias y pendientes de una versión validada, aunque venga por SQL directo."""
    row, column, value = validated[table]
    with pytest.raises(DatabaseError) as rejected, transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {table} SET {column} = {value} WHERE id = %s", [row.pk]
            )
    assert "versión validada" in str(rejected.value)
    row.refresh_from_db()
    assert getattr(row, column) != value.strip("'")


@pytest.mark.django_db
@pytest.mark.parametrize("table", TABLES)
def test_delete_on_validated_version_rejected_by_database(validated, table):
    """REQ-027: la base rechaza un DELETE sobre las filas de una versión validada."""
    row, _, _ = validated[table]
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {table} WHERE id = %s", [row.pk])
    assert type(row).objects.filter(pk=row.pk).exists()


@pytest.mark.django_db
def test_quote_update_through_orm_rejected(validated):
    """REQ-027: el cambio de una cita de una versión validada se rechaza también por el
    ORM."""
    quote = validated["tenders_requirement_quote"][0]
    quote.text = "otro texto"
    with pytest.raises(DatabaseError), transaction.atomic():
        quote.save()


@pytest.mark.django_db
def test_draft_rows_can_change(segments, draft, read_write_user):
    """REQ-026: en un borrador, los requisitos y sus citas se corrigen."""
    a, _ = segments
    requirement = add_requirement(draft, 1, "formal")
    quote = add_quote(requirement, a)
    m.Requirement.objects.filter(pk=requirement.pk).update(state="confirmado")
    m.RequirementQuote.objects.filter(pk=quote.pk).update(quote_flag="cita_amplia")
    requirement.refresh_from_db()
    assert requirement.state == "confirmado"


@pytest.mark.django_db
def test_row_cannot_move_into_validated_version(
    procedure, segments, draft, read_write_user
):
    """REQ-027: un requisito de un borrador no puede pasar a una versión validada."""
    a, _ = segments
    add_quote(add_requirement(draft, 1, "formal"), a)
    validate(draft, read_write_user)
    new_draft = m.MatrixVersion.objects.create(
        procedure=procedure, number=2, level="alta", based_on=draft,
        created_by=read_write_user,
    )
    moving = add_requirement(new_draft, 5, "formal")
    add_quote(moving, a)
    with pytest.raises(DatabaseError), transaction.atomic():
        m.Requirement.objects.filter(pk=moving.pk).update(version=draft)


def discard(version, user):
    m.MatrixVersion.objects.filter(pk=version.pk).update(
        status="discarded", discarded_at=timezone.now(), discarded_by=user
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "change",
    [
        {"status": "draft"},
        {"status": "discarded"},
        {"level": "media"},
        {"validated_at": None, "validated_by": None, "status": "draft"},
    ],
    ids=["a-borrador", "a-descartada", "nivel", "sin-validacion"],
)
def test_validated_version_row_cannot_change(validated, draft, read_write_user, change):
    """REQ-027: la fila de una versión validada no cambia: no vuelve a borrador, no se
    descarta y no cambia ninguno de sus datos, aunque venga por SQL directo."""
    with pytest.raises(DatabaseError) as rejected, transaction.atomic():
        m.MatrixVersion.objects.filter(pk=draft.pk).update(**change)
    assert "no cambia" in str(rejected.value)
    draft.refresh_from_db()
    assert draft.status == "validated"
    assert draft.level == "alta"
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE tenders_matrix_version SET status = 'draft' WHERE id = %s",
                [draft.pk],
            )


@pytest.mark.django_db
def test_discarded_version_row_cannot_change(draft, read_write_user):
    """REQ-027: una versión descartada tampoco cambia: no vuelve a borrador ni pasa a
    validada."""
    discard(draft, read_write_user)
    for change in (
        {"status": "draft", "discarded_at": None, "discarded_by": None},
        {"status": "validated", "validated_at": timezone.now(),
         "validated_by": read_write_user},
    ):
        with pytest.raises(DatabaseError), transaction.atomic():
            m.MatrixVersion.objects.filter(pk=draft.pk).update(**change)
    draft.refresh_from_db()
    assert draft.status == "discarded"


@pytest.mark.django_db
def test_draft_version_can_be_validated_or_discarded(
    procedure, draft, read_write_user
):
    """REQ-027: un borrador pasa a validada o a descartada, con quién y cuándo."""
    validate(draft, read_write_user)
    draft.refresh_from_db()
    assert draft.status == "validated"
    other = m.MatrixVersion.objects.create(
        procedure=procedure, number=2, level="alta", based_on=draft,
        created_by=read_write_user,
    )
    discard(other, read_write_user)
    other.refresh_from_db()
    assert other.status == "discarded"


def _insert_new_row(table, version, requirement, segment, user):
    """Inserta una fila nueva de `table` en `version` (o en `requirement`)."""
    if table == "tenders_requirement":
        return m.Requirement.objects.create(
            version=version, number=77, category="tecnico", items=[1],
            origin="agregado",
        )
    if table == "tenders_requirement_quote":
        return add_quote(requirement, segment, order=9)
    if table == "tenders_requirement_source":
        return m.RequirementSource.objects.create(
            requirement=requirement, effect="aclara", segment=segment,
            char_start=segment.char_start, char_end=segment.char_end,
            text=segment.text, issued_on=date(2025, 11, 21),
        )
    if table == "tenders_consequence":
        return m.Consequence.objects.create(
            requirement=requirement, consequence_type="intimacion_subsanar",
            origin="persona",
        )
    return m.PendingItem.objects.create(
        version=version, segment=segment, reason="no_ubicado"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("table", TABLES)
def test_insert_into_validated_version_rejected(
    validated, draft, segments, read_write_user, table
):
    """REQ-027: no se agregan requisitos, citas, fuentes, consecuencias ni pendientes a
    una versión validada."""
    requirement = validated["tenders_requirement"][0]
    before = connection.cursor()
    before.execute(f"SELECT count(*) FROM {table}")
    count = before.fetchone()[0]
    with pytest.raises(DatabaseError) as rejected, transaction.atomic():
        _insert_new_row(table, draft, requirement, segments[1], read_write_user)
    assert "borrador" in str(rejected.value)
    before.execute(f"SELECT count(*) FROM {table}")
    assert before.fetchone()[0] == count


@pytest.mark.django_db
@pytest.mark.parametrize("table", TABLES)
def test_insert_into_discarded_version_rejected(
    segments, draft, read_write_user, table
):
    """REQ-027: tampoco se agregan filas a una versión descartada."""
    a, b = segments
    requirement = add_requirement(draft, 1, "tecnico", items=[1])
    add_quote(requirement, b, scope="propia")
    discard(draft, read_write_user)
    with pytest.raises(DatabaseError) as rejected, transaction.atomic():
        _insert_new_row(table, draft, requirement, a, read_write_user)
    assert "borrador" in str(rejected.value)


@pytest.fixture
def discarded(validated, procedure, segments, read_write_user):
    """Una versión descartada (la 2, abierta sobre la validada) con un requisito, su
    cita, una fuente, una consecuencia elegida y un pendiente resuelto."""
    a, b = segments
    old = validated["tenders_requirement"][0].version
    version = m.MatrixVersion.objects.create(
        procedure=procedure, number=2, level="alta", based_on=old,
        created_by=read_write_user,
    )
    requirement = add_requirement(version, 1, "formal")
    quote = add_quote(requirement, a)
    source = m.RequirementSource.objects.create(
        requirement=requirement, quote=quote, effect="aclara", segment=b,
        char_start=b.char_start, char_end=b.char_end, text=b.text,
        issued_on=date(2025, 11, 20),
    )
    consequence = m.Consequence.objects.create(
        requirement=requirement, consequence_type="desestimacion", origin="sistema",
        chosen=True, chosen_by=read_write_user, chosen_at=timezone.now(),
    )
    pending = m.PendingItem.objects.create(
        version=version, segment=b, reason="tabla", resolution="sin_requisitos",
        resolved_by=read_write_user, resolved_at=timezone.now(),
    )
    check_deferred()
    discard(version, read_write_user)
    return {
        "version": version,
        "tenders_requirement": (requirement, "state", "'quitado'"),
        "tenders_requirement_quote": (quote, "text", "'otro texto'"),
        "tenders_requirement_source": (source, "effect", "'modifica'"),
        "tenders_consequence": (consequence, "chosen_note", "'otro motivo'"),
        "tenders_pending_item": (pending, "reason", "'no_ubicado'"),
    }


@pytest.mark.django_db
@pytest.mark.parametrize("table", TABLES)
def test_update_on_discarded_version_rejected_by_database(discarded, table):
    """REQ-027: una versión descartada queda tan fija como una validada: la base
    rechaza un UPDATE sobre su contenido."""
    row, column, value = discarded[table]
    with pytest.raises(DatabaseError) as rejected, transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {table} SET {column} = {value} WHERE id = %s", [row.pk]
            )
    assert "no cambia" in str(rejected.value)
    row.refresh_from_db()
    assert getattr(row, column) != value.strip("'")


@pytest.mark.django_db
@pytest.mark.parametrize("table", TABLES)
def test_delete_on_discarded_version_rejected_by_database(discarded, table):
    """REQ-027: la base rechaza un DELETE sobre el contenido de una versión
    descartada."""
    row, _, _ = discarded[table]
    with pytest.raises(DatabaseError) as rejected, transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(f"DELETE FROM {table} WHERE id = %s", [row.pk])
    assert "no cambia" in str(rejected.value)
    assert type(row).objects.filter(pk=row.pk).exists()


@pytest.mark.django_db
def test_row_cannot_move_into_discarded_version(
    discarded, procedure, segments, read_write_user
):
    """REQ-027: un requisito o un pendiente de un borrador no puede pasar a una versión
    descartada."""
    a, b = segments
    new_draft = m.MatrixVersion.objects.create(
        procedure=procedure, number=3, level="alta", created_by=read_write_user
    )
    # Técnico: la fixture dejó los controles diferidos en inmediato, y un formal sin
    # su cita todavía se rechazaría al insertarlo.
    moving = add_requirement(new_draft, 5, "tecnico", items=[1])
    add_quote(moving, a, scope="propia")
    pending = m.PendingItem.objects.create(
        version=new_draft, segment=b, reason="no_ubicado"
    )
    target = discarded["version"]
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE tenders_requirement SET version_id = %s WHERE id = %s",
                [target.pk, moving.pk],
            )
    with pytest.raises(DatabaseError), transaction.atomic():
        m.PendingItem.objects.filter(pk=pending.pk).update(version=target)
    moving.refresh_from_db()
    pending.refresh_from_db()
    assert moving.version_id == new_draft.pk
    assert pending.version_id == new_draft.pk


# --- Solo inserción -------------------------------------------------------------------


@pytest.fixture
def run_step(procedure):
    run = m.MatrixRun.objects.create(
        procedure=procedure, level="media", channel="screen",
        authorization_date=procedure.authorization_date,
    )
    return m.RunStep.objects.create(
        run=run, pass_name="extraccion", batch=1, segment_keys=["sec-i/11.3"],
        request={"messages": []}, raw_output="{}",
    )


@pytest.mark.django_db
def test_run_step_update_rejected(run_step):
    """REQ-024 (P6): `tenders_run_step` solo admite inserciones: un UPDATE se rechaza."""
    with pytest.raises(DatabaseError) as rejected, transaction.atomic():
        m.RunStep.objects.filter(pk=run_step.pk).update(raw_output="cambiado")
    assert "solo admite agregar" in str(rejected.value)
    run_step.refresh_from_db()
    assert run_step.raw_output == "{}"


@pytest.mark.django_db
def test_run_step_delete_rejected(run_step):
    """REQ-024 (P6): un pedido al modelo registrado no se borra."""
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM tenders_run_step WHERE id = %s", [run_step.pk])
    assert m.RunStep.objects.filter(pk=run_step.pk).exists()


@pytest.mark.django_db
def test_requirement_change_is_append_only(segments, draft, read_write_user):
    """REQ-026: el historial de un requisito solo admite inserciones."""
    requirement = add_requirement(draft, 1, "formal")
    add_quote(requirement, segments[0])
    event = audit.record(
        "requirement_change", outcome="ok", channel="screen", user=read_write_user,
        detail={"action": "corregir"},
    )
    change = m.RequirementChange.objects.create(
        requirement=requirement, action="corregir", before={"category": "formal"},
        after={"category": "economico"}, user=read_write_user, event=event,
    )
    with pytest.raises(DatabaseError), transaction.atomic():
        m.RequirementChange.objects.filter(pk=change.pk).update(after={})
    with pytest.raises(DatabaseError), transaction.atomic():
        m.RequirementChange.objects.filter(pk=change.pk).delete()
    change.refresh_from_db()
    assert change.after == {"category": "economico"}


# --- Tipos de hecho -------------------------------------------------------------------

NEW_EVENT_TYPES = [
    "procedure", "tender_load", "tender_read", "matrix_request", "matrix_proposal",
    "requirement_change", "consequence_choice", "segment_review",
    "matrix_validation", "matrix_version", "matrix_export",
]


@pytest.mark.django_db
@pytest.mark.parametrize("event_type", NEW_EVENT_TYPES)
def test_new_event_types_recorded(event_type, read_write_user):
    """REQ-022, REQ-023, REQ-024, REQ-026, REQ-027, REQ-028, REQ-029, REQ-032 (P6): los
    once hechos de la 003 se registran con `audit.record` y la base los acepta."""
    event = audit.record(
        event_type, outcome="ok", channel="screen", user=read_write_user,
        detail={"sintetico": True},
    )
    assert AuditEvent.objects.get(pk=event.pk).event_type == event_type


@pytest.mark.django_db
def test_unknown_event_type_still_rejected():
    """REQ-012: la restricción de valores de `audit_event` sigue rechazando un tipo
    que no está en la lista."""
    with pytest.raises(IntegrityError), transaction.atomic():
        audit.record("matrix_delete", outcome="ok", channel="screen")


# --- Parámetros -----------------------------------------------------------------------


def test_matrix_parameters_in_settings():
    """REQ-030, REQ-024: los parámetros de la 003 están en la configuración con los
    valores iniciales del plan."""
    assert settings.MATRIX_LEVELS == ["media", "alta", "exigente"]
    assert settings.MATRIX_DEFAULT_LEVEL == "alta"
    assert settings.MATRIX_LEVELS_OFFERED == ("media", "alta")
    assert set(settings.MATRIX_LEVELS) == set(m.Level.values)
    assert settings.MATRIX_BATCH_INPUT_TOKENS == 1500
    assert settings.MATRIX_MAX_OUTPUT_TOKENS == 4096
    assert settings.SEGMENT_MAX_CHARS == 4000
    assert settings.MATRIX_CONSEQUENCES_PER_REQUEST == 25
    assert settings.MATRIX_CIRCULAR_CANDIDATES == 8
    assert settings.MATRIX_PROMPT_VERSIONS["extraccion"] == "matriz-extraccion-v2"
    assert settings.GENERATION_BATCH_TIMEOUT_SECONDS == 180
    assert settings.WORKER_POLL_SECONDS == 5


def test_generation_batch_url_default(monkeypatch):
    """REQ-024 (ADR-0018): sin variable de entorno, el motor del `worker` es
    `generation_batch`."""
    import runpy

    monkeypatch.delenv("GENERATION_BATCH_URL", raising=False)
    values = runpy.run_path(str(settings.BASE_DIR / "evaluon" / "settings.py"))
    assert values["GENERATION_BATCH_URL"] == "http://generation_batch:8080"
