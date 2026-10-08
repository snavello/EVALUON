"""Pendientes y sugerencias agrupados por tipo cuando son muchos (REQ-098; T-222).
Material inventado (P4)."""

import functools

import pytest

from evaluon.journey.sections import base, sections_for
from evaluon.journey.sections.base import Item, group_items
from tests.journey.temas.test_s4_preguntas import asked, tab  # noqa: F401  (fixtures y ayudas)
from tests.journey.temas.test_s4_preguntas import (  # noqa: F401
    evaluated,
    log_in,
    requirement,
    simulate,
    three,
)

pytestmark = pytest.mark.django_db


def pairs(n):
    return [Item(f"Oferta {i} · requisito 1: cumple propuesto, sin decidir", f"/x#ev-{i}", 1,
                 "Resolver", kind="par", noun="pares por decidir", group_url="/x?ver=abiertas")
            for i in range(n)]


def test_up_to_the_limit_items_stay_one_by_one():
    """REQ-098: con 8 o menos del mismo tipo, se muestran uno por uno."""
    items = pairs(8)
    assert group_items(items) == items


def test_many_items_become_one_line_with_count_and_filtered_access():
    """REQ-098: más de 8 del mismo tipo: una línea con la cuenta, la acción y el bloque filtrado;
    la suma de `count` no cambia (sigue coincidiendo con la barra)."""
    other = Item("Otra cosa", "/y", 1)
    items = pairs(138) + [other]
    grouped = group_items(items)
    assert len(grouped) == 2 and other in grouped
    line = grouped[0]
    assert line.text == "138 pares por decidir" and line.url == "/x?ver=abiertas"
    assert line.action == "Revisar"
    assert sum(i.count for i in grouped) == sum(i.count for i in items)


def test_kinds_are_grouped_independently():
    items = pairs(9) + [Item(f"q{i}", "/q", 1, kind="pregunta", noun="preguntas abiertas",
                             group_url="/q?preg=abiertas", group_action="Responder")
                        for i in range(3)]
    grouped = group_items(items)
    assert len(grouped) == 1 + 3


def test_section_groups_and_count_matches_the_bar(monkeypatch, procedure, evaluated, asked,
                                                  evaluator_user):
    """REQ-098: en la sección, agrupar no cambia la cuenta; el acceso lleva al filtro."""
    monkeypatch.setattr(base, "group_items", functools.partial(group_items, limit=10_000))
    before = sections_for(evaluator_user, procedure).get("evaluacion")
    monkeypatch.setattr(base, "group_items", functools.partial(group_items, limit=0))
    after = sections_for(evaluator_user, procedure).get("evaluacion")
    assert after.pending == before.pending
    assert sum(i.count for i in after.pending_items) == sum(i.count for i in before.pending_items)
    assert len(after.pending_items) < len(before.pending_items)
    urls = {i.url for i in after.pending_items}
    assert any("preg=abiertas" in u for u in urls)


def test_questions_block_filters_to_what_is_open(client, procedure, asked, evaluator_user):
    """REQ-098: `?preg=abiertas` deja en el bloque solo lo abierto."""
    log_in(client, evaluator_user)
    html = client.get(tab(procedure) + "?preg=abiertas").content.decode()
    assert "¿La garantía está vigente?" in html
    assert "¿La firma es del apoderado?" not in html
    assert 'id="preg-filtro"' in html
    full = client.get(tab(procedure)).content.decode()
    assert "¿La firma es del apoderado?" in full
