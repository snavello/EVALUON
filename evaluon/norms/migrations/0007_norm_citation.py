"""Nombre de cita de la norma (T-055; plan 001, `norms_norm`; decisión del responsable
del 2026-10-03).

Agrega `norms_norm.citation`: el nombre con que se cita la norma, tal como lo escribe la
persona al cargarla ("Disposición AFIP 297/03"). Es obligatorio y no vacío: además del
`NOT NULL`, una restricción de la base rechaza el texto vacío o hecho solo de espacios,
igual que la de la categoría.

Las filas existentes necesitan un valor para agregar la columna. El valor por omisión
`''` vale solo dentro de esta migración (`preserve_default=False`): el modelo no tiene
valor por omisión. No se arma un nombre a partir de tipo, número y año, porque esa regla
es justamente la que la decisión descarta. Si la base ya tuviera normas, quedarían con
`''` y la restricción que se agrega a continuación haría fallar la migración: hay que
escribirles el nombre de cita antes de migrar. La base `evaluon` no tiene normas
cargadas a esta fecha.

La reversa quita la restricción y la columna.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("norms", "0006_search_normalize_enye"),
    ]

    operations = [
        migrations.AddField(
            model_name="norm",
            name="citation",
            field=models.TextField(default="", verbose_name="nombre de cita"),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name="norm",
            constraint=models.CheckConstraint(
                condition=models.Q(("citation__regex", "\\S")),
                name="norms_norm_citation_not_blank",
            ),
        ),
    ]
