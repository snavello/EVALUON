"""T-114 (plan 003, rediseño de circulares del 2026-10-04, ADR-0023, REQ-031): el original
de una circular en un anexo y la pasada de extracción de cambios.

- `tenders_requirement_source` suma `original_segment`, `original_char_start` y
  `original_char_end`, opcionales: los tres juntos o ninguno. Las filas existentes quedan
  con los tres nulos (válidas).
- `pass_name` de `tenders_run_step` (y `source_pass` de las descartadas, que comparte la
  lista de pasadas) suma `circulares_cambios`.

El trigger de inmutabilidad de una versión validada (0002) es por fila y no por columna:
cubre los campos nuevos sin cambios.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenders', '0003_sugerencias_descartadas_proceso_unico'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='discardedrow',
            name='tenders_discarded_row_source_pass_valid',
        ),
        migrations.RemoveConstraint(
            model_name='runstep',
            name='tenders_run_step_pass_name_valid',
        ),
        migrations.AddField(
            model_name='requirementsource',
            name='original_char_end',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='fin del original en el texto canónico'),
        ),
        migrations.AddField(
            model_name='requirementsource',
            name='original_char_start',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='inicio del original en el texto canónico'),
        ),
        migrations.AddField(
            model_name='requirementsource',
            name='original_segment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='requirement_source_originals', to='tenders.segment', verbose_name='tramo del original'),
        ),
        migrations.AlterField(
            model_name='runstep',
            name='pass_name',
            field=models.CharField(choices=[('extraccion', 'Extracción'), ('extraccion_2', 'Segunda extracción'), ('completitud', 'Completitud'), ('consecuencias', 'Consecuencias'), ('circulares', 'Circulares'), ('unificacion', 'Unificación de repetidas'), ('filtro', 'Filtro de sobrantes'), ('filtro_2', 'Filtro de sobrantes, segunda opinión'), ('respaldo_normativo', 'Respaldo normativo'), ('circulares_cambios', 'Extracción de cambios de circulares')], max_length=20, verbose_name='pasada'),
        ),
        migrations.AddConstraint(
            model_name='discardedrow',
            constraint=models.CheckConstraint(condition=models.Q(('source_pass__in', ['extraccion', 'extraccion_2', 'completitud', 'consecuencias', 'circulares', 'unificacion', 'filtro', 'filtro_2', 'respaldo_normativo', 'circulares_cambios'])), name='tenders_discarded_row_source_pass_valid'),
        ),
        migrations.AddConstraint(
            model_name='requirementsource',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('original_char_end__isnull', True), ('original_char_start__isnull', True), ('original_segment__isnull', True)), models.Q(('original_char_end__gte', models.F('original_char_start')), ('original_char_end__isnull', False), ('original_char_start__isnull', False), ('original_segment__isnull', False)), _connector='OR'), name='tenders_requirement_source_original_valid'),
        ),
        migrations.AddConstraint(
            model_name='runstep',
            constraint=models.CheckConstraint(condition=models.Q(('pass_name__in', ['extraccion', 'extraccion_2', 'completitud', 'consecuencias', 'circulares', 'unificacion', 'filtro', 'filtro_2', 'respaldo_normativo', 'circulares_cambios'])), name='tenders_run_step_pass_name_valid'),
        ),
    ]
