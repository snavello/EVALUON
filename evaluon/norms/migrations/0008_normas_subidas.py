# T-193 (REQ-094): normas subidas que esperan la confirmación de la Comisión (ADR-0051).


import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('norms', '0007_norm_citation'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='NormUpload',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_name', models.CharField(max_length=255, verbose_name='nombre del archivo')),
                ('file_format', models.CharField(choices=[('pdf', 'PDF'), ('html', 'Página web')], max_length=10, verbose_name='formato')),
                ('file_size', models.PositiveBigIntegerField(verbose_name='tamaño')),
                ('file_sha256', models.CharField(max_length=64, verbose_name='huella del archivo')),
                ('content', models.BinaryField(verbose_name='contenido')),
                ('proposal', models.JSONField(default=dict, verbose_name='datos propuestos')),
                ('state', models.CharField(choices=[('leyendo', 'Leyendo'), ('propuesto', 'Propuesto'), ('aprobado', 'Aprobado'), ('rechazado', 'Rechazado'), ('fallido', 'Fallido')], default='leyendo', max_length=10, verbose_name='estado')),
                ('failure', models.TextField(blank=True, verbose_name='motivo de la falla')),
                ('uploaded_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='subida')),
                ('document', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='upload', to='norms.document', verbose_name='documento resultante')),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='norm_uploads', to=settings.AUTH_USER_MODEL, verbose_name='subida por')),
            ],
            options={
                'verbose_name': 'norma subida',
                'verbose_name_plural': 'normas subidas',
                'db_table': 'norms_upload',
                'constraints': [models.CheckConstraint(condition=models.Q(('state__in', ['leyendo', 'propuesto', 'aprobado', 'rechazado', 'fallido'])), name='norms_upload_state_valid'), models.CheckConstraint(condition=models.Q(('file_format__in', ['pdf', 'html'])), name='norms_upload_file_format_valid'), models.CheckConstraint(condition=models.Q(('file_sha256__regex', '^[0-9a-f]{64}$')), name='norms_upload_file_sha256_valid'), models.CheckConstraint(condition=models.Q(models.Q(('state', 'aprobado'), ('document__isnull', False)), models.Q(models.Q(('state', 'aprobado'), _negated=True), ('document__isnull', True)), _connector='OR'), name='norms_upload_document_only_if_approved')],
            },
        ),
    ]
