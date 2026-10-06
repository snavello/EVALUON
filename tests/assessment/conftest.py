"""Fixtures de la feature 004 (evaluación asistida de ofertas; T-148).

- Los de la 008: usuarios de la Comisión, el procedimiento del caso chico con su matriz
  validada (`procedure`, `matrix`) y `make_offer` (oferta con documentos ya leídos).
- `rows`: una fila de cada una de las ocho tablas de la evaluación, armada sobre una oferta de
  dos documentos del caso chico. Textos inventados (P4).
"""

from types import SimpleNamespace

import pytest

from evaluon.assessment import models as am
from evaluon.audit import services as audit
from evaluon.audit.models import Channel, EventType, Outcome
from tests.offers.conftest import (  # noqa: F401 - fixtures de la 008 y la 003
    evaluator_user,
    expected,
    matrix,
    no_commission_user,
    offer,
    operator_user,
    procedure,
)


@pytest.fixture
def rows(matrix, offer, evaluator_user):
    """Una fila de cada tabla de la evaluación (`SimpleNamespace`)."""
    version = matrix.version
    requirement = version.requirements.first()
    quote = requirement.quotes.first()
    document = offer.documents.get(file_name="oferta.pdf")
    reading = document.readings.get()
    request = am.Request.objects.create(
        procedure=matrix.procedure, matrix_version=version, offers=[offer.pk],
        requirements=None, cause=am.Cause.MATRIZ, requested_by=evaluator_user)
    run = am.Run.objects.create(
        request=request, offer=offer, matrix_version=version, number=1,
        channel=am.Channel.SCREEN, documents=[], norms={}, models_used={}, parameters={},
        prompt_versions={})
    result = am.Result.objects.create(
        run=run, offer=offer, requirement=requirement, outcome=am.Outcome.CUMPLE,
        exigence=am.Exigence.CONDICION, explanation="Declara estar habilitado.")
    citation = am.Citation.objects.create(
        result=result, order=1, kind=am.CitationKind.OFERTA, document=document,
        reading=reading, page=1, char_start=0, char_end=10,
        text=reading.canonical_text[:10])
    step = am.Step.objects.create(
        run=run, offer=offer, requirement=requirement, purpose=am.Purpose.GRUPO,
        group_index=0)
    event = audit.record(EventType.EVAL_DECISION, outcome=Outcome.OK, channel=Channel.SCREEN,
                         user=evaluator_user)
    decision = am.Decision.objects.create(
        result=result, action=am.Action.CONFIRMAR, user=evaluator_user, event=event)
    question = am.Question.objects.create(
        procedure=matrix.procedure, requirement=requirement, offer=offer, result=result,
        text="¿La póliza fue validada por la SSN?", reason="externo")
    answer = am.Answer.objects.create(
        question=question, text="Sí, validada.", answered_by=evaluator_user, event=event)
    return SimpleNamespace(
        version=version, requirement=requirement, quote=quote, document=document,
        reading=reading, request=request, run=run, result=result, citation=citation,
        step=step, decision=decision, question=question, answer=answer, event=event)
