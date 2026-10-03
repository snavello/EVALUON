"""Tabla `queries_query`: registro detallado de cada consulta (T-010; plan 001, "Modelo de
datos", sección `queries`, y "Forma de la respuesta").

La fila se inserta una vez, al terminar la consulta, y apunta a su hecho `query` de
`audit_event`, que nace completo. Estas pruebas arman la consulta a mano, sin la función
de consulta (T-019), y comprueban lo que la base guarda y lo que no deja guardar. Los
datos son sintéticos (P4).
"""

from datetime import date

import pytest
from django.db import DatabaseError, IntegrityError, transaction

from evaluon.audit import services
from evaluon.audit.models import Channel, EventType, Outcome
from evaluon.queries.models import Query, Reason, Status


@pytest.fixture
def corpus_version(read_write_user):
    """Una versión de la normativa, creada como la crea una validación."""
    event = services.record(
        EventType.VALIDATION,
        outcome=Outcome.OK,
        channel=Channel.COMMAND,
        user=read_write_user,
        detail={"reading": 1},
        creates_corpus_version=True,
    )
    return event.corpus_version


@pytest.fixture
def cited_unit(make_norm, make_document, make_reading):
    """Un artículo sintético de un régimen general, para citar."""
    norm = make_norm(
        norm_type="disposicion", number="297", year=2003, issuer="afip",
        general_regime=True,
    )
    document = make_document(norm, file_format="html")
    reading = make_reading(document, [
        ("art-14", "ARTICULO 14.- Garantías sintéticas de la oferta."),
    ])
    unit = reading.units_by_key["art-14"]
    return unit


def grounded_result(unit, reference_date):
    """Resultado con la forma de "Forma de la respuesta" del plan."""
    norm = unit.reading.document.norm
    return {
        "query_id": None,
        "status": "grounded",
        "reason": None,
        "reference_date": reference_date.isoformat(),
        "regime": [{"norm": norm.pk, "name": "Disposición AFIP 297/03"}],
        "notices": [
            {"type": "pending_amendments", "norm": norm.pk,
             "name": "Disposición AFIP 297/03", "pending": 32}
        ],
        "statements": [
            {"text": "La oferta lleva garantía.", "regimes_differ": False,
             "citations": [unit.pk]}
        ],
        "units": {
            str(unit.pk): {
                "norm": "Disposición AFIP 297/03",
                "category": "regimen_especifico",
                "unit_type": "articulo",
                "path": unit.path,
                "text_origin": "pdf_text",
                "document": unit.reading.document.pk,
                "page_start": None,
                "changes": [],
            }
        },
    }


def record_query_event(user, question, reference_date, result):
    return services.record(
        EventType.QUERY,
        outcome=Outcome.OK,
        channel=Channel.SCREEN,
        user=user,
        detail={
            "question": question,
            "reference_date": reference_date.isoformat(),
            "result": result,
        },
    )


def query_values(event, user, **overrides):
    """Valores mínimos de una consulta `undetermined` por falta de régimen."""
    values = {
        "event": event,
        "user": user,
        "question": "¿Qué garantía se exige?",
        "reference_date": date(2021, 3, 15),
        "corpus_version": event.corpus_version,
        "status": Status.UNDETERMINED,
        "reason": Reason.NO_REGIME_AT_DATE,
        "result": {"status": "undetermined", "reason": "no_regime_at_date"},
    }
    values.update(overrides)
    return values


@pytest.mark.django_db
def test_saved_query_reads_back_with_user_date_and_corpus_version(
    read_user, corpus_version, cited_unit
):
    """REQ-012: una consulta guardada con la forma de "Forma de la respuesta" se lee igual
    y conserva pregunta, fecha de autorización, unidades recuperadas, respuesta, versión de
    la normativa, usuario y fecha, y apunta a su hecho `query`."""
    question = "¿Qué garantía se exige al presentar la oferta?"
    reference_date = date(2021, 3, 15)
    result = grounded_result(cited_unit, reference_date)
    candidates = [
        {"unit": cited_unit.pk, "passage": 1, "path": "vector", "score": 0.91,
         "text_origin": "pdf_text"},
        {"unit": cited_unit.pk, "passage": 1, "path": "text", "score": 0.91,
         "text_origin": "pdf_text"},
    ]
    selected = {"sent": [cited_unit.pk], "added_by_relation": [], "left_out": []}
    parameters = {"candidates_per_path": 30, "threshold": 0.5, "per_category": 3}
    request = {"messages": [{"role": "user", "content": "U1 ..."}], "temperature": 0}
    raw_output = '{"status": "grounded", "statements": [{"text": "La oferta lleva garantía.", "citations": ["U1"], "regimes_differ": false}]}'
    timings = {"retrieval": 0.8, "generation": 12.4, "total": 13.3}

    event = record_query_event(read_user, question, reference_date, result)
    created = Query.objects.create(
        event=event,
        user=read_user,
        question=question,
        reference_date=reference_date,
        corpus_version=event.corpus_version,
        status=Status.GROUNDED,
        reason="",
        parameters=parameters,
        candidates=candidates,
        selected=selected,
        max_score=0.91,
        prompt_version="v1",
        request=request,
        raw_output=raw_output,
        result=result,
        anomalies=[],
        timings=timings,
    )

    saved = Query.objects.get(pk=created.pk)
    assert saved.question == question
    assert saved.reference_date == reference_date
    assert saved.user == read_user
    assert saved.asked_at is not None
    assert saved.corpus_version == corpus_version
    assert saved.status == "grounded"
    assert saved.reason == ""
    assert saved.result == result
    assert saved.result["statements"][0]["citations"] == [cited_unit.pk]
    assert saved.candidates == candidates
    assert saved.selected == selected
    assert saved.parameters == parameters
    assert saved.max_score == pytest.approx(0.91)
    assert saved.prompt_version == "v1"
    assert saved.request == request
    assert saved.raw_output == raw_output
    assert saved.anomalies == []
    assert saved.timings == timings

    # La consulta apunta a su hecho, que lleva el mismo usuario y la misma versión.
    assert saved.event == event
    assert saved.event.event_type == EventType.QUERY
    assert saved.event.user == read_user
    assert saved.event.corpus_version == saved.corpus_version
    assert event.query == saved


@pytest.mark.django_db
def test_query_without_corpus_version_and_without_model_call(read_user):
    """REQ-012: una consulta hecha antes de que exista una versión de la normativa, que
    terminó sin buscar ni llamar al modelo, se guarda con la versión vacía y sin pedido,
    salida ni puntaje."""
    event = record_query_event(read_user, "¿Qué rige?", date(2001, 1, 10), {})
    assert event.corpus_version is None

    query = Query.objects.create(**query_values(event, read_user))

    saved = Query.objects.get(pk=query.pk)
    assert saved.corpus_version is None
    assert saved.max_score is None
    assert saved.request is None
    assert saved.raw_output == ""
    assert saved.prompt_version == ""
    assert saved.candidates == []
    assert saved.anomalies == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("status", "reason"),
    [
        ("grounded", ""),
        ("undetermined", "no_regime_at_date"),
        ("undetermined", "below_threshold"),
        ("undetermined", "model_abstained"),
        ("undetermined", "invalid_citation"),
        ("error", "timeout"),
        ("error", "service_unavailable"),
        ("error", "invalid_output"),
        ("error", "input_too_long"),
    ],
)
def test_allowed_status_and_reason(read_user, status, reason):
    """REQ-012: los estados y motivos del plan ("Forma de la respuesta") se guardan."""
    event = record_query_event(read_user, "¿Pregunta?", date(2021, 3, 15), {})
    Query.objects.create(**query_values(event, read_user, status=status, reason=reason))
    assert Query.objects.get(event=event).reason == reason


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("status", "reason"),
    [
        ("grounded", "below_threshold"),       # una respuesta con fundamento no lleva motivo
        ("undetermined", ""),                  # un "no determinado" siempre dice por qué
        ("undetermined", "timeout"),           # una falla técnica no es "no determinado"
        ("error", ""),                         # una falla técnica siempre dice cuál
        ("error", "model_abstained"),          # una abstención no es una falla técnica
        ("answered", ""),                      # estado que no existe
        ("undetermined", "otro_motivo"),       # motivo que no existe
    ],
)
def test_rejected_status_and_reason(read_user, status, reason):
    """REQ-012: la base no guarda un estado o un motivo fuera del plan, ni un motivo que
    no corresponde a su estado."""
    event = record_query_event(read_user, "¿Pregunta?", date(2021, 3, 15), {})
    with pytest.raises(IntegrityError), transaction.atomic():
        Query.objects.create(
            **query_values(event, read_user, status=status, reason=reason)
        )


@pytest.mark.django_db
@pytest.mark.parametrize("score", [-0.01, 1.01])
def test_max_score_outside_zero_one_rejected(read_user, score):
    """REQ-012: el puntaje más alto es el del reranker llevado a un número entre 0 y 1
    (plan, "Reordenamiento"); fuera de ese rango no se guarda."""
    event = record_query_event(read_user, "¿Pregunta?", date(2021, 3, 15), {})
    with pytest.raises(IntegrityError), transaction.atomic():
        Query.objects.create(**query_values(
            event, read_user, status="undetermined", reason="below_threshold",
            max_score=score,
        ))


@pytest.mark.django_db
def test_one_query_per_event(read_user):
    """REQ-012: cada consulta tiene su propio hecho `query`; dos consultas no comparten
    hecho."""
    event = record_query_event(read_user, "¿Pregunta?", date(2021, 3, 15), {})
    Query.objects.create(**query_values(event, read_user))
    with pytest.raises(IntegrityError), transaction.atomic():
        Query.objects.create(**query_values(event, read_user))


@pytest.mark.django_db
def test_query_is_inserted_once(read_user):
    """REQ-012: la consulta se inserta una vez, al terminar: la base rechaza modificarla
    o borrarla, venga del modelo o de una actualización en lote."""
    event = record_query_event(read_user, "¿Pregunta?", date(2021, 3, 15), {})
    query = Query.objects.create(**query_values(event, read_user))
    original = query.question

    query.question = "otra pregunta"
    with pytest.raises(ValueError):
        query.save()
    with pytest.raises(ValueError):
        query.delete()
    with pytest.raises(DatabaseError) as rejected, transaction.atomic():
        Query.objects.filter(pk=query.pk).update(question="otra pregunta")
    assert "registro de consultas" in str(rejected.value)
    with pytest.raises(DatabaseError) as rejected, transaction.atomic():
        Query.objects.filter(pk=query.pk).delete()
    assert "registro de consultas" in str(rejected.value)

    assert Query.objects.get(pk=query.pk).question == original
