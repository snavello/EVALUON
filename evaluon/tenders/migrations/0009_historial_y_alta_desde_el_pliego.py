# T-193 (REQ-077, REQ-092, REQ-099): historial de documentos del pliego (solo inserción, ADR-0048), borrador de
# procedimiento (ADR-0049), tipo `dictamen` y pedidos `propose_procedure` y `propose_offer`.


import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0008_hechos_de_la_014'),
        ('tenders', '0008_job_progress'),
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
                'verbose_name': 'cambio de un documento del pliego',
                'verbose_name_plural': 'cambios de los documentos del pliego',
                'db_table': 'tenders_document_change',
            },
        ),
        migrations.CreateModel(
            name='ProcedureDraft',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_name', models.CharField(max_length=255, verbose_name='nombre del archivo')),
                ('file_format', models.CharField(choices=[('pdf', 'PDF'), ('html', 'Página web')], max_length=10, verbose_name='formato')),
                ('file_size', models.PositiveBigIntegerField(verbose_name='tamaño')),
                ('file_sha256', models.CharField(max_length=64, verbose_name='huella del archivo')),
                ('content', models.BinaryField(verbose_name='contenido')),
                ('proposal', models.JSONField(default=dict, verbose_name='propuesta')),
                ('state', models.CharField(choices=[('leyendo', 'Leyendo'), ('propuesto', 'Propuesto'), ('aprobado', 'Aprobado'), ('rechazado', 'Rechazado'), ('fallido', 'Fallido')], default='leyendo', max_length=10, verbose_name='estado')),
                ('failure', models.TextField(blank=True, verbose_name='motivo de la falla')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='subido')),
            ],
            options={
                'verbose_name': 'borrador de procedimiento',
                'verbose_name_plural': 'borradores de procedimiento',
                'db_table': 'tenders_procedure_draft',
            },
        ),
        migrations.RemoveConstraint(
            model_name='document',
            name='tenders_document_kind_valid',
        ),
        migrations.RemoveConstraint(
            model_name='job',
            name='tenders_job_procedure_required',
        ),
        migrations.RemoveConstraint(
            model_name='job',
            name='tenders_job_kind_valid',
        ),
        migrations.AlterField(
            model_name='document',
            name='kind',
            field=models.CharField(choices=[('pliego', 'Pliego'), ('anexo', 'Anexo'), ('especificaciones', 'Especificaciones técnicas'), ('circular_modificatoria', 'Circular modificatoria'), ('circular_aclaratoria', 'Circular aclaratoria'), ('respuesta_consulta', 'Respuesta a consulta'), ('dictamen', 'Dictamen')], max_length=30, verbose_name='tipo'),
        ),
        migrations.AlterField(
            model_name='job',
            name='kind',
            field=models.CharField(choices=[('read_document', 'Leer un documento'), ('propose_matrix', 'Proponer la matriz'), ('read_offer_document', 'Leer un documento de una oferta'), ('build_sheet', 'Armar la ficha de una oferta'), ('portal_explore', 'Explorar un proceso del Portal'), ('portal_review', 'Revisar un proceso del Portal'), ('evaluate_offers', 'Evaluar las ofertas'), ('propose_procedure', 'Proponer el procedimiento desde el pliego'), ('propose_offer', 'Proponer la oferta desde sus archivos')], max_length=20, verbose_name='tipo'),
        ),
        migrations.AddConstraint(
            model_name='document',
            constraint=models.CheckConstraint(condition=models.Q(('kind__in', ['pliego', 'anexo', 'especificaciones', 'circular_modificatoria', 'circular_aclaratoria', 'respuesta_consulta', 'dictamen'])), name='tenders_document_kind_valid'),
        ),
        migrations.AddConstraint(
            model_name='job',
            constraint=models.CheckConstraint(condition=models.Q(('kind__in', ['read_document', 'propose_matrix', 'read_offer_document', 'build_sheet', 'portal_explore', 'portal_review', 'evaluate_offers', 'propose_procedure', 'propose_offer'])), name='tenders_job_kind_valid'),
        ),
        migrations.AddConstraint(
            model_name='job',
            constraint=models.CheckConstraint(condition=models.Q(('procedure__isnull', False), ('kind__in', ['portal_explore', 'portal_review', 'propose_procedure']), _connector='OR'), name='tenders_job_procedure_required'),
        ),
        migrations.AddConstraint(
            model_name='job',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('kind__in', ('propose_procedure', 'propose_offer')), _negated=True), ('target_id__isnull', False), _connector='OR'), name='tenders_job_proposal_kinds_have_target'),
        ),
        migrations.AddField(
            model_name='documentchange',
            name='document',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='changes', to='tenders.document', verbose_name='documento'),
        ),
        migrations.AddField(
            model_name='documentchange',
            name='event',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='tender_document_changes', to='audit.auditevent', verbose_name='hecho registrado'),
        ),
        migrations.AddField(
            model_name='documentchange',
            name='new_document',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='replaces', to='tenders.document', verbose_name='documento nuevo'),
        ),
        migrations.AddField(
            model_name='documentchange',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='tender_document_changes', to=settings.AUTH_USER_MODEL, verbose_name='usuario'),
        ),
        migrations.AddField(
            model_name='proceduredraft',
            name='created_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='procedure_drafts_created', to=settings.AUTH_USER_MODEL, verbose_name='subido por'),
        ),
        migrations.AddField(
            model_name='proceduredraft',
            name='job',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='procedure_drafts', to='tenders.job', verbose_name='pedido'),
        ),
        migrations.AddField(
            model_name='proceduredraft',
            name='procedure',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='draft', to='tenders.procedure', verbose_name='procedimiento resultante'),
        ),
        migrations.AddIndex(
            model_name='documentchange',
            index=models.Index(fields=['document', 'id'], name='tenders_docchange_document'),
        ),
        migrations.AddConstraint(
            model_name='documentchange',
            constraint=models.CheckConstraint(condition=models.Q(('action__in', ['reemplazar', 'retirar', 'restituir'])), name='tenders_document_change_action_valid'),
        ),
        migrations.AddConstraint(
            model_name='documentchange',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('action', 'reemplazar'), ('new_document__isnull', False), models.Q(('new_document', models.F('document')), _negated=True)), models.Q(models.Q(('action', 'reemplazar'), _negated=True), ('new_document__isnull', True)), _connector='OR'), name='tenders_document_change_new_document_only_if_replaced'),
        ),
        migrations.AddConstraint(
            model_name='proceduredraft',
            constraint=models.CheckConstraint(condition=models.Q(('state__in', ['leyendo', 'propuesto', 'aprobado', 'rechazado', 'fallido'])), name='tenders_procedure_draft_state_valid'),
        ),
        migrations.AddConstraint(
            model_name='proceduredraft',
            constraint=models.CheckConstraint(condition=models.Q(('file_format__in', ['pdf', 'html'])), name='tenders_procedure_draft_file_format_valid'),
        ),
        migrations.AddConstraint(
            model_name='proceduredraft',
            constraint=models.CheckConstraint(condition=models.Q(('file_sha256__regex', '^[0-9a-f]{64}$')), name='tenders_procedure_draft_file_sha256_valid'),
        ),
        migrations.AddConstraint(
            model_name='proceduredraft',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('state', 'aprobado'), ('procedure__isnull', False)), models.Q(models.Q(('state', 'aprobado'), _negated=True), ('procedure__isnull', True)), _connector='OR'), name='tenders_procedure_draft_procedure_only_if_approved'),
        ),
        migrations.RunSQL(
            sql='CREATE TRIGGER tenders_document_change_append_only\n    BEFORE UPDATE OR DELETE ON tenders_document_change\n    FOR EACH ROW EXECUTE FUNCTION tenders_reject_change();\n',
            reverse_sql='DROP TRIGGER tenders_document_change_append_only ON tenders_document_change;\n',
        ),
    ]
