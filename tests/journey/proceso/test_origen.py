"""Cada renglón de pendientes y faltantes lleva su origen (REQ-147; T-342): `etapa:<clave>` para
el genérico de una etapa y la clave del tema para los de un tema. Material inventado (P4)."""

import pytest

from evaluon.journey.sections import sections_for
from evaluon.journey.sections.base import Item, Missing, group_items, group_missing

pytestmark = pytest.mark.django_db


def test_origen_por_omision_vacio():
    """REQ-147: sin origen declarado, el renglón lo trae vacío."""
    assert Item("x").origen == "" and Missing("x").origen == ""


def test_group_items_copia_el_origen():
    """REQ-147: el renglón agrupado conserva el origen del grupo."""
    items = [Item(f"p{i}", "/x", 1, kind="par", noun="pares", origen="s4_preguntas")
             for i in range(9)]
    assert [i.origen for i in group_items(items)] == ["s4_preguntas"]


def test_group_missing_copia_el_origen():
    """REQ-147: el faltante agrupado conserva el origen del grupo."""
    items = [Missing(f"m{i}", "/x", "Ir", kind="of", noun="ofertas", origen="s3_ofertas")
             for i in range(4)]
    assert [m.origen for m in group_missing(items)] == ["s3_ofertas"]


def test_todo_renglon_de_las_secciones_tiene_origen(procedure, operator_user):
    """REQ-147: tras `build_section` ningún renglón queda sin origen: es `etapa:<clave>` o la
    clave de un tema."""
    overview = sections_for(operator_user, procedure)
    temas = {t.KEY for s in overview.sections for t in s.temas}
    visto = 0
    for section in overview.sections:
        for one in (*section.pending_items, *section.suggestion_items, *section.missing,
                    *section.tema_missing):
            visto += 1
            assert one.origen.startswith("etapa:") or one.origen in temas, one
    assert visto > 0
