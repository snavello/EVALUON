# T-193 (REQ-091): decisión de la Comisión sobre cada descarte propuesto (solo inserción).


import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assessment', '0004_triggers'),
        ('audit', '0008_hechos_de_la_014'),
        ('offers', '0007_historial_y_alta_desde_los_archivos'),
        ('tenders', '0009_historial_y_alta_desde_el_pliego'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DiscardDecision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('line', models.PositiveIntegerField(blank=True, null=True, verbose_name='renglón')),
                ('action', models.CharField(choices=[('confirmar', 'Confirmar el descarte'), ('rechazar', 'Rechazar el descarte')], max_length=10, verbose_name='acción')),
                ('note', models.TextField(blank=True, verbose_name='nota')),
                ('at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='momento')),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assessment_discard_decisions', to='audit.auditevent', verbose_name='hecho registrado')),
                ('offer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assessment_discard_decisions', to='offers.offer', verbose_name='oferta')),
                ('procedure', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assessment_discard_decisions', to='tenders.procedure', verbose_name='procedimiento')),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='discard_decisions', to='assessment.request', verbose_name='pedido de evaluación')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assessment_discard_decisions', to=settings.AUTH_USER_MODEL, verbose_name='usuario')),
            ],
            options={
                'verbose_name': 'decisión sobre un descarte',
                'verbose_name_plural': 'decisiones sobre los descartes',
                'db_table': 'assessment_discard_decision',
                'indexes': [models.Index(fields=['request', 'offer', 'line'], name='assessment_discard_pair')],
                'constraints': [models.CheckConstraint(condition=models.Q(('action__in', ['confirmar', 'rechazar'])), name='assessment_discard_decision_action_valid')],
            },
        ),
        migrations.RunSQL(
            sql='CREATE TRIGGER assessment_discard_decision_append_only\n    BEFORE UPDATE OR DELETE ON assessment_discard_decision\n    FOR EACH ROW EXECUTE FUNCTION assessment_reject_change();\n',
            reverse_sql='DROP TRIGGER assessment_discard_decision_append_only ON assessment_discard_decision;\n',
        ),
    ]
