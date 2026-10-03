"""Extensiones de Postgres que usa la normativa (plan 001, "Migraciones con SQL propio").

- `vector`: vectores de los pasajes (`norms_passage.embedding`).
- `unaccent`: la usa la normalización de la búsqueda por palabras de T-009 (ADR-0007).

La imagen fijada en T-004 trae las dos. Crearlas exige un rol con permiso en la base;
hoy es el usuario de la base del contenedor (los roles de despliegue son de T-049).
"""

from django.db import migrations

FORWARD = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS unaccent;
"""

REVERSE = """
DROP EXTENSION IF EXISTS unaccent;
DROP EXTENSION IF EXISTS vector;
"""


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(sql=FORWARD, reverse_sql=REVERSE),
    ]
