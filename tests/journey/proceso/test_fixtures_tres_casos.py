"""Los tres procedimientos de la tabla de 21 estados se arman con el caso chico y cumplen las
condiciones de datos del anexo del plan 018 (REQ-144, REQ-145; T-340). Se comprueban con las etapas
y temas que ya existen (`stages_for`, `s4_dictamen.uploaded_dictamenes`, `memo.matrix_page`); no
hay cálculo nuevo. Datos inventados (P4)."""

import pytest

from evaluon.assessment import models as am
from evaluon.assessment.services import matrix as matrix_service
from evaluon.journey import memo, stages
from evaluon.journey.stages import base
from evaluon.journey.temas import s4_dictamen
from evaluon.portal.models import PortalOfferData

pytestmark = pytest.mark.django_db


def estados(caso):
    journey = stages.stages_for(caso.user, caso.procedure)
    return journey, {s.key: s.state for s in journey.stages}


def pagina(caso):
    return memo.matrix_page(caso.user, caso.procedure.pk)


def efectivos(page):
    cuentas = {}
    for cell in page.cells.values():
        if cell.result is not None and cell.effective_outcome:
            cuentas[cell.effective_key] = cuentas.get(cell.effective_key, 0) + 1
    return cuentas


def test_recien_cargado(caso_recien_cargado):
    """REQ-144: pliego leído, sin circulares, sin matriz, sin ofertas, sin dictamen."""
    caso = caso_recien_cargado
    _, st = estados(caso)
    assert st["pliego"] == base.LISTA
    assert st["matriz"] == base.PENDIENTE
    assert st["ofertas"] == base.PENDIENTE
    assert st["evaluacion"] == base.PENDIENTE
    assert st["matriz_evaluacion"] == base.PENDIENTE
    assert [d.kind for d in caso.procedure.documents.all()] == ["pliego"]
    assert not caso.procedure.matrix_versions.exists()
    assert not caso.procedure.offers.exists()
    assert s4_dictamen.uploaded_dictamenes(caso.procedure) == []


def test_varios_en_curso(caso_varios_en_curso):
    """REQ-144, REQ-145: pliego y matriz hechos; un documento sin leer; 12 no determinados, un
    «no cumple», 4 preguntas, propuestas «cumple» sin confirmar, sin informe técnico, todas las
    ofertas con total, sin dictamen."""
    caso = caso_varios_en_curso
    _, st = estados(caso)
    assert st["pliego"] == base.LISTA
    assert st["matriz"] == base.LISTA
    assert st["ofertas"] == base.PENDIENTE            # el documento nuevo no tiene lectura
    assert not caso.sin_leer.readings.exists()
    assert st["matriz_evaluacion"] == base.A_DECIDIR

    page = pagina(caso)
    cuentas = efectivos(page)
    assert cuentas["no_determinado"] == 12
    assert cuentas["no_cumple"] == 1
    assert sum(len(s.open_questions) for s in page.statuses) == 4
    propuestos = [c for c in page.cells.values()
                  if c.state == matrix_service.PENDING and c.effective_key == "cumple"]
    assert len(propuestos) == cuentas["cumple"] == 5   # propuestas «cumple» sin confirmar
    for status in page.statuses:                       # filas técnicas evaluadas, sin ok ni informe
        assert len(status.technical) == 3 and status.reports == []
        assert not any(row.approved for row in status.technical)
    assert PortalOfferData.objects.filter(
        offer__in=caso.offers, total__isnull=False).count() == len(caso.offers) == 2
    # El «no cumple» de la oferta A propone su descarte (cualquier requisito formal lo hace) y
    # la saca del orden económico; el orden de las demás existe con su total.
    assert [d.offer.pk for d in page.discards] == [caso.offers[0].pk]
    assert page.order is not None
    assert [r.offer.pk for r in page.order.totals] == [caso.offers[1].pk]
    assert s4_dictamen.uploaded_dictamenes(caso.procedure) == []


def test_todo_hecho(caso_todo_hecho):
    """REQ-144, REQ-145: nada pendiente, informe técnico y ok dados, totales del acta de todas las
    ofertas y dictamen cargado."""
    caso = caso_todo_hecho
    journey, st = estados(caso)
    # El Portal es opcional: no hay vínculo en el caso chico y queda pendiente sin frenar el resto.
    assert {k: v for k, v in st.items() if k != "portal"} == dict.fromkeys(
        [k for k in st if k != "portal"], base.LISTA)
    assert journey.current is None and journey.pending == 0

    page = pagina(caso)
    assert efectivos(page) == {"cumple": 18}
    # Las filas técnicas se deciden con el ok del informe, no confirmando el par.
    tecnicas = {(estado.offer.pk, row.requirement.pk)
                for estado in page.statuses for row in estado.technical}
    assert not any(c.state == matrix_service.PENDING
                   for key, c in page.cells.items() if key not in tecnicas)
    for status in page.statuses:
        assert status.open_questions == [] and len(status.reports) == 1
        assert all(row.approved for row in status.technical) and len(status.technical) == 3
    assert not am.Question.objects.filter(offer__in=caso.offers).exists()
    assert PortalOfferData.objects.filter(
        offer__in=caso.offers, total__isnull=False).count() == 2
    assert [d.pk for d in s4_dictamen.uploaded_dictamenes(caso.procedure)] == [caso.dictamen.pk]
