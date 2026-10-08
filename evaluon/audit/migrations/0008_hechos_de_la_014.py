# T-193 (REQ-091, REQ-093, REQ-094, REQ-099): tipos de hecho de auditoría de la feature 014.


from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0007_evaluacion'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='auditevent',
            name='audit_event_event_type_valid',
        ),
        migrations.AlterField(
            model_name='auditevent',
            name='event_type',
            field=models.CharField(choices=[('load', 'Carga'), ('reread', 'Relectura'), ('validation', 'Validación'), ('relation', 'Relación'), ('version', 'Versión'), ('pending_amendment', 'Modificatorias sin cargar'), ('query', 'Consulta'), ('search', 'Búsqueda'), ('login', 'Ingreso'), ('login_failed', 'Ingreso fallido'), ('rejected', 'Operación rechazada por rol'), ('user_created', 'Alta de usuario'), ('procedure', 'Alta de procedimiento'), ('tender_load', 'Carga de documento del pliego'), ('tender_read', 'Lectura de documento del pliego'), ('matrix_request', 'Pedido de matriz'), ('matrix_proposal', 'Propuesta de matriz'), ('requirement_change', 'Cambio de requisito'), ('consequence_choice', 'Elección de consecuencia'), ('segment_review', 'Revisión de tramo pendiente'), ('matrix_validation', 'Validación de matriz'), ('matrix_version', 'Versión de matriz'), ('matrix_export', 'Exportación de matriz'), ('user_role_changed', 'Cambio de rol de la Comisión'), ('offer_register', 'Alta de oferta'), ('offer_load', 'Carga de documento de una oferta'), ('offer_read', 'Lectura de documento de una oferta'), ('sheet_request', 'Pedido de ficha'), ('sheet_build', 'Armado de ficha'), ('sheet_change', 'Cambio de la ficha'), ('portal_link', 'Enlace del Portal'), ('portal_explore', 'Exploración del Portal'), ('portal_review', 'Revisión periódica del Portal'), ('portal_decision', 'Decisión sobre un ítem del Portal'), ('eval_request', 'Pedido de evaluación'), ('eval_build', 'Evaluación de una oferta'), ('eval_decision', 'Decisión sobre un resultado de la evaluación'), ('eval_answer', 'Respuesta de la Comisión'), ('document_change', 'Reemplazo, retiro o restitución de un documento'), ('procedure_proposal', 'Propuesta de procedimiento desde el pliego'), ('offer_proposal', 'Propuesta de oferta desde sus archivos'), ('discard_decision', 'Decisión sobre un descarte'), ('norm_upload', 'Norma subida'), ('eval_export', 'Exportación de la evaluación')], max_length=20, verbose_name='hecho'),
        ),
        migrations.AddConstraint(
            model_name='auditevent',
            constraint=models.CheckConstraint(condition=models.Q(('event_type__in', ['load', 'reread', 'validation', 'relation', 'version', 'pending_amendment', 'query', 'search', 'login', 'login_failed', 'rejected', 'user_created', 'procedure', 'tender_load', 'tender_read', 'matrix_request', 'matrix_proposal', 'requirement_change', 'consequence_choice', 'segment_review', 'matrix_validation', 'matrix_version', 'matrix_export', 'user_role_changed', 'offer_register', 'offer_load', 'offer_read', 'sheet_request', 'sheet_build', 'sheet_change', 'portal_link', 'portal_explore', 'portal_review', 'portal_decision', 'eval_request', 'eval_build', 'eval_decision', 'eval_answer', 'document_change', 'procedure_proposal', 'offer_proposal', 'discard_decision', 'norm_upload', 'eval_export'])), name='audit_event_event_type_valid'),
        ),
    ]
