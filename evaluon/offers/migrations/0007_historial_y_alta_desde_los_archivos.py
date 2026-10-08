# T-193 (REQ-083, REQ-087, REQ-099): historial de documentos de la oferta (solo inserción, ADR-0048), borrador de
# oferta con sus archivos (ADR-0049) y tipo `anexo_tecnico`.


import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0008_hechos_de_la_014'),
        ('offers', '0006_informe_tecnico_del_area'),
        ('tenders', '0009_historial_y_alta_desde_el_pliego'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentChange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('reemplazar', 'Reemplazar'), ('retirar', 'Retirar'), ('restituir', 'Restituir')], max_length=12, verbose_name='acción')),
                ('note', models.TextField(blank=True, verbose_name='nota')),
                ('at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='momento')),
            ],
            options={
                'verbose_name': 'cambio de un documento de la oferta',
                'verbose_name_plural': 'cambios de los documentos de las ofertas',
                'db_table': 'offers_document_change',
            },
        ),
        migrations.CreateModel(
            name='OfferDraft',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('proposal', models.JSONField(default=dict, verbose_name='propuesta')),
                ('state', models.CharField(choices=[('leyendo', 'Leyendo'), ('propuesto', 'Propuesto'), ('aprobado', 'Aprobado'), ('rechazado', 'Rechazado'), ('fallido', 'Fallido')], default='leyendo', max_length=10, verbose_name='estado')),
                ('failure', models.TextField(blank=True, verbose_name='motivo de la falla')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='subido')),
            ],
            options={
                'verbose_name': 'borrador de oferta',
                'verbose_name_plural': 'borradores de oferta',
                'db_table': 'offers_offer_draft',
            },
        ),
        migrations.CreateModel(
            name='OfferDraftFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_name', models.CharField(max_length=255, verbose_name='nombre del archivo')),
                ('file_format', models.CharField(choices=[('pdf', 'PDF'), ('jpg', 'Foto JPG'), ('png', 'Foto PNG'), ('docx', 'Word')], max_length=10, verbose_name='formato')),
                ('file_size', models.PositiveBigIntegerField(verbose_name='tamaño')),
                ('file_sha256', models.CharField(max_length=64, verbose_name='huella del archivo')),
                ('content', models.BinaryField(verbose_name='contenido')),
            ],
            options={
                'verbose_name': 'archivo de un borrador de oferta',
                'verbose_name_plural': 'archivos de los borradores de oferta',
                'db_table': 'offers_offer_draft_file',
            },
        ),
        migrations.RemoveConstraint(
            model_name='document',
            name='offers_document_kind_valid',
        ),
        migrations.AlterField(
            model_name='document',
            name='kind',
            field=models.CharField(blank=True, choices=[('economica', 'Propuesta económica'), ('tecnica', 'Documentación técnica'), ('garantia', 'Garantía'), ('compliance', 'Hoja de compliance'), ('informe_tecnico', 'Informe técnico del área'), ('anexo_tecnico', 'Anexo técnico de la oferta'), ('otro', 'Otro')], max_length=20, verbose_name='tipo'),
        ),
        migrations.AddConstraint(
            model_name='document',
            constraint=models.CheckConstraint(condition=models.Q(('kind__in', ['economica', 'tecnica', 'garantia', 'compliance', 'informe_tecnico', 'anexo_tecnico', 'otro']), ('kind', ''), _connector='OR'), name='offers_document_kind_valid'),
        ),
        migrations.AddField(
            model_name='documentchange',
            name='document',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='changes', to='offers.document', verbose_name='documento'),
        ),
        migrations.AddField(
            model_name='documentchange',
            name='event',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='offer_document_changes', to='audit.auditevent', verbose_name='hecho registrado'),
        ),
        migrations.AddField(
            model_name='documentchange',
            name='new_document',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='replaces', to='offers.document', verbose_name='documento nuevo'),
        ),
        migrations.AddField(
            model_name='documentchange',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='offer_document_changes', to=settings.AUTH_USER_MODEL, verbose_name='usuario'),
        ),
        migrations.AddField(
            model_name='offerdraft',
            name='created_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='offer_drafts_created', to=settings.AUTH_USER_MODEL, verbose_name='subido por'),
        ),
        migrations.AddField(
            model_name='offerdraft',
            name='job',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='offer_drafts', to='tenders.job', verbose_name='pedido'),
        ),
        migrations.AddField(
            model_name='offerdraft',
            name='offer',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='draft', to='offers.offer', verbose_name='oferta resultante'),
        ),
        migrations.AddField(
            model_name='offerdraft',
            name='procedure',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='offer_drafts', to='tenders.procedure', verbose_name='procedimiento'),
        ),
        migrations.AddField(
            model_name='offerdraftfile',
            name='draft',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='files', to='offers.offerdraft', verbose_name='borrador'),
        ),
        migrations.AddIndex(
            model_name='documentchange',
            index=models.Index(fields=['document', 'id'], name='offers_docchange_document'),
        ),
        migrations.AddConstraint(
            model_name='documentchange',
            constraint=models.CheckConstraint(condition=models.Q(('action__in', ['reemplazar', 'retirar', 'restituir'])), name='offers_document_change_action_valid'),
        ),
        migrations.AddConstraint(
            model_name='documentchange',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('action', 'reemplazar'), ('new_document__isnull', False), models.Q(('new_document', models.F('document')), _negated=True)), models.Q(models.Q(('action', 'reemplazar'), _negated=True), ('new_document__isnull', True)), _connector='OR'), name='offers_document_change_new_document_only_if_replaced'),
        ),
        migrations.AddConstraint(
            model_name='offerdraft',
            constraint=models.CheckConstraint(condition=models.Q(('state__in', ['leyendo', 'propuesto', 'aprobado', 'rechazado', 'fallido'])), name='offers_offer_draft_state_valid'),
        ),
        migrations.AddConstraint(
            model_name='offerdraft',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('state', 'aprobado'), ('offer__isnull', False)), models.Q(models.Q(('state', 'aprobado'), _negated=True), ('offer__isnull', True)), _connector='OR'), name='offers_offer_draft_offer_only_if_approved'),
        ),
        migrations.AddConstraint(
            model_name='offerdraftfile',
            constraint=models.CheckConstraint(condition=models.Q(('file_format__in', ['pdf', 'jpg', 'png', 'docx'])), name='offers_offer_draft_file_format_valid'),
        ),
        migrations.AddConstraint(
            model_name='offerdraftfile',
            constraint=models.CheckConstraint(condition=models.Q(('file_sha256__regex', '^[0-9a-f]{64}$')), name='offers_offer_draft_file_sha256_valid'),
        ),
        migrations.AddConstraint(
            model_name='offerdraftfile',
            constraint=models.UniqueConstraint(fields=('draft', 'file_sha256'), name='offers_offer_draft_file_sha256_unique'),
        ),
        migrations.RunSQL(
            sql='CREATE TRIGGER offers_document_change_append_only\n    BEFORE UPDATE OR DELETE ON offers_document_change\n    FOR EACH ROW EXECUTE FUNCTION offers_reject_change();\n',
            reverse_sql='DROP TRIGGER offers_document_change_append_only ON offers_document_change;\n',
        ),
    ]
