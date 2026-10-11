"""Esquema de la 015 en `tenders`: los motivos de descarte nuevos (T-250; REQ-102; plan 015,
"Modelo de datos"; ADR-0054, regla 5, que enmienda la lista cerrada del ADR-0019).

La Comisión decidió el 2026-10-10 que no son requisitos de la oferta el pago, la moneda de
pago y la factura, la forma de presentar por el Portal ni los compromisos que se cumplen al
presentarse; y que una condición que solo vale si el oferente elige una opción entra solo como
condición de esa opción. La migración solo agrega valores permitidos: lo ya guardado no
cambia. Las restricciones las hace valer la base. Textos inventados (P4).
"""

import pytest
from django.conf import settings
from django.db import IntegrityError, connection, transaction

from evaluon.tenders import models as m
from tests.tenders.test_discarded import add_row, case  # noqa: F401  (fixture y ayuda)
from tests.tenders.test_discarded_screen import list_url, log_in, text_of
from tests.tenders.test_filter import (  # noqa: F401  (fixtures y ayudas)
    FRAG_1,
    SENT_1,
    discard,
    filt,
    one_row,
    pliego,
    run_with,
    script,
)
from tests.tenders.test_models import (  # noqa: F401  (fixtures y ayudas)
    add_discarded,
    draft,
    make_tender_document,
    new_run,
    new_step,
    procedure,
    segments,
)

pytestmark = pytest.mark.django_db

# Los nueve motivos que había antes de la 015, en su orden.
BEFORE = ["titulo", "dato_procedimiento", "norma_aplicable", "obligacion_organismo",
          "ejecucion_contrato", "formulario", "indice_caratula", "consecuencia_sancion",
          "derecho_posterior"]
# Los de las filas que el filtro descarta y el nuevo motivo de los tramos.
NEW_FOR_ROWS = ["condicion_opcional", "pago_factura", "forma_presentacion_portal",
                "compromiso_presentacion"]
NEW_FOR_SEGMENTS = ["consecuencia_sancion", *NEW_FOR_ROWS]


# --- La lista de motivos del filtro y la del modelo son la misma ----------------------------------


def test_the_filter_motives_are_the_models_in_the_same_order():
    """REQ-102: `FILTER_MOTIVES` (la lista que ve el modelo en el esquema) y los valores de
    `FilterMotive` (los que acepta la base) coinciden, sin repetidos y en el mismo orden."""
    assert list(settings.FILTER_MOTIVES) == list(m.FilterMotive.values)
    assert len(set(settings.FILTER_MOTIVES)) == len(settings.FILTER_MOTIVES)


def test_the_new_motives_are_in_the_closed_lists_and_the_old_ones_stay():
    """REQ-102: consecuencia, condición opcional, pago o factura, forma de presentar por el
    Portal y compromiso al presentarse están en las dos listas; los motivos anteriores siguen,
    en su lugar."""
    assert list(m.FilterMotive.values) == [*BEFORE, *NEW_FOR_ROWS]
    assert list(m.DiscardReason.values)[:7] == BEFORE[:7]
    assert set(NEW_FOR_SEGMENTS) <= set(m.DiscardReason.values)
    assert set(BEFORE[:7]) <= set(m.DiscardReason.values)


@pytest.mark.parametrize("enum", [m.DiscardReason, m.FilterMotive])
def test_every_motive_has_a_distinct_readable_label(enum):
    """REQ-102: las etiquetas salen del modelo y la Comisión las lee: ninguna igual a su
    valor, ninguna repetida."""
    labels = [label for _, label in enum.choices]
    assert len(set(labels)) == len(labels)
    assert all(label != value for value, label in enum.choices)


# --- La base acepta los valores nuevos y rechaza los que no existen ----------------------------------


@pytest.mark.parametrize("reason", NEW_FOR_SEGMENTS)
def test_a_discarded_segment_accepts_each_new_motive(new_run, segments, reason):
    """REQ-102: la disposición de un tramo descartado admite cada motivo nuevo."""
    saved = m.Disposition.objects.create(
        run=new_run, segment=segments[0], outcome="descartado", discard_reason=reason,
        source="modelo")

    assert m.Disposition.objects.get(pk=saved.pk).discard_reason == reason


def test_a_discarded_segment_rejects_a_motive_that_does_not_exist(new_run, segments):
    """REQ-102: un motivo fuera de la lista cerrada lo rechaza la base."""
    with pytest.raises(IntegrityError), transaction.atomic():
        m.Disposition.objects.create(
            run=new_run, segment=segments[0], outcome="descartado",
            discard_reason="pago_o_algo", source="modelo")


@pytest.mark.parametrize("reason", NEW_FOR_ROWS)
def test_a_discarded_row_accepts_each_new_motive(new_run, new_step, segments, draft, reason):
    """REQ-102: la fila descartada por el filtro admite cada motivo nuevo."""
    saved = add_discarded(new_run, draft, segments[0], new_step, reason=reason)

    assert m.DiscardedRow.objects.get(pk=saved.pk).reason == reason


def test_a_discarded_row_rejects_a_motive_that_does_not_exist(
        new_run, new_step, segments, draft):
    """REQ-102: un motivo fuera de la lista cerrada lo rechaza la base."""
    with pytest.raises(IntegrityError), transaction.atomic():
        add_discarded(new_run, draft, segments[0], new_step, reason="pago_o_algo")


# --- El filtro descarta con un motivo nuevo y todo se guarda --------------------------------------------


@pytest.mark.parametrize("reason", NEW_FOR_ROWS)
def test_a_row_the_filter_discards_with_a_new_motive_is_saved_with_its_segment(
        operator_user, script, filt, reason):  # noqa: F811
    """REQ-102: una fila que el filtro descarta con un motivo nuevo (y con la que se descarta
    el tramo entero) se guarda con ese motivo en la fila descartada y en la disposición del
    tramo, sin que la base rechace la propuesta."""
    one_row(script)
    filt.when(FRAG_1, discard(reason, SENT_1), "no")

    run = run_with(operator_user, pliego(SENT_1))

    row = m.DiscardedRow.objects.get(run=run)
    assert row.reason == reason
    assert m.Disposition.objects.get(run=run, segment=row.segment).discard_reason == reason


# --- La pantalla de descartadas muestra la etiqueta de cada motivo nuevo ----------------------------


@pytest.mark.parametrize("reason", NEW_FOR_ROWS)
def test_the_discarded_screen_shows_the_label_of_each_new_motive(
        client, operator_user, case, reason):  # noqa: F811
    """REQ-102, REQ-033: la lista de descartadas muestra el motivo nuevo con su etiqueta."""
    add_row(case, "sec-i/3.1", order=1, reason=reason)
    log_in(client, operator_user)

    page = text_of(client.get(list_url(case)))

    assert m.FilterMotive(reason).label in page


# --- La migración solo agrega valores y se puede deshacer --------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_the_motives_migration_keeps_the_saved_rows_and_is_reversible(
        new_run, new_step, segments, draft):  # noqa: F811
    """REQ-102: con un tramo descartado y una fila descartada ya guardados con motivos
    anteriores, la migración se revierte y se vuelve a aplicar sin cambiarlos; antes de ella,
    la base no admite los motivos nuevos."""
    from django.db.migrations.executor import MigrationExecutor

    kept = m.Disposition.objects.create(
        run=new_run, segment=segments[0], outcome="descartado", discard_reason="formulario",
        source="modelo")
    row = add_discarded(new_run, draft, segments[0], new_step, reason="norma_aplicable")

    def migrate(targets):
        MigrationExecutor(connection).migrate(targets)

    latest = [("tenders", MigrationExecutor(connection).loader.graph.leaf_nodes("tenders")[0][1])]
    try:
        migrate([("tenders", "0010_consecuencia_sin_indicar_en_el_pliego")])
        with pytest.raises(IntegrityError), transaction.atomic():
            m.Disposition.objects.create(
                run=new_run, segment=segments[1], outcome="descartado",
                discard_reason="pago_factura", source="modelo")
        migrate(latest)
        assert m.Disposition.objects.get(pk=kept.pk).discard_reason == "formulario"
        assert m.DiscardedRow.objects.get(pk=row.pk).reason == "norma_aplicable"
        added = m.Disposition.objects.create(
            run=new_run, segment=segments[1], outcome="descartado",
            discard_reason="pago_factura", source="modelo")
        assert m.Disposition.objects.get(pk=added.pk).discard_reason == "pago_factura"
    finally:
        migrate(latest)
