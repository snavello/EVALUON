"""Guarda de esquema de la 018: la feature no toca la base (REQ-145; T-342)."""

from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

import evaluon

# La última migración de cada app al empezar la 018 y cuántas hay. Una nueva rompe el test.
ULTIMAS = {
    "accounts": ("0003_tema_y_fotos", 3),
    "assessment": ("0005_decisiones_de_descarte", 5),
    "audit": ("0009_externo", 9),
    "norms": ("0008_normas_subidas", 8),
    "offers": ("0007_historial_y_alta_desde_los_archivos", 7),
    "portal": ("0004_origen_en_documento", 4),
    "queries": ("0002_insert_only", 2),
    "tenders": ("0011_motivos_de_descarte_nuevos", 11),
}


@pytest.mark.django_db
def test_los_modelos_coinciden_con_las_migraciones():
    """REQ-145: `makemigrations --check --dry-run` no detecta nada."""
    call_command("makemigrations", "--check", "--dry-run", stdout=StringIO())


def test_no_hay_migraciones_nuevas():
    """REQ-145: ninguna app tiene una migración más que al empezar la 018."""
    base = Path(evaluon.__file__).parent
    found = {}
    for folder in sorted(base.glob("*/migrations")):
        names = sorted(p.stem for p in folder.glob("[0-9][0-9][0-9][0-9]_*.py"))
        found[folder.parent.name] = (names[-1], len(names))
    assert found == ULTIMAS
