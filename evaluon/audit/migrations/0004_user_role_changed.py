"""Tipo de hecho `user_role_changed` en `audit_event` (T-088). Cambia la lista de
valores válidos."""

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0003_tender_event_types'),
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
            field=models.CharField(choices=[('load', 'Carga'), ('reread', 'Relectura'), ('validation', 'Validación'), ('relation', 'Relación'), ('version', 'Versión'), ('pending_amendment', 'Modificatorias sin cargar'), ('query', 'Consulta'), ('search', 'Búsqueda'), ('login', 'Ingreso'), ('login_failed', 'Ingreso fallido'), ('rejected', 'Operación rechazada por rol'), ('user_created', 'Alta de usuario'), ('procedure', 'Alta de procedimiento'), ('tender_load', 'Carga de documento del pliego'), ('tender_read', 'Lectura de documento del pliego'), ('matrix_request', 'Pedido de matriz'), ('matrix_proposal', 'Propuesta de matriz'), ('requirement_change', 'Cambio de requisito'), ('consequence_choice', 'Elección de consecuencia'), ('segment_review', 'Revisión de tramo pendiente'), ('matrix_validation', 'Validación de matriz'), ('matrix_version', 'Versión de matriz'), ('matrix_export', 'Exportación de matriz'), ('user_role_changed', 'Cambio de rol de la Comisión')], max_length=20, verbose_name='hecho'),
        ),
        migrations.AddConstraint(
            model_name='auditevent',
            constraint=models.CheckConstraint(condition=models.Q(('event_type__in', ['load', 'reread', 'validation', 'relation', 'version', 'pending_amendment', 'query', 'search', 'login', 'login_failed', 'rejected', 'user_created', 'procedure', 'tender_load', 'tender_read', 'matrix_request', 'matrix_proposal', 'requirement_change', 'consequence_choice', 'segment_review', 'matrix_validation', 'matrix_version', 'matrix_export', 'user_role_changed'])), name='audit_event_event_type_valid'),
        ),
    ]
