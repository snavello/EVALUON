# Cambio de opciones (T-190; REQ-074): el tipo de un documento de la oferta suma `informe_tecnico`,
# el informe técnico aprobado del área requirente que la Comisión sube.

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('offers', '0005_hoja_de_compliance'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='document',
            name='offers_document_kind_valid',
        ),
        migrations.AlterField(
            model_name='document',
            name='kind',
            field=models.CharField(blank=True, choices=[('economica', 'Propuesta económica'), ('tecnica', 'Documentación técnica'), ('garantia', 'Garantía'), ('compliance', 'Hoja de compliance'), ('informe_tecnico', 'Informe técnico del área'), ('otro', 'Otro')], max_length=20, verbose_name='tipo'),
        ),
        migrations.AddConstraint(
            model_name='document',
            constraint=models.CheckConstraint(condition=models.Q(('kind__in', ['economica', 'tecnica', 'garantia', 'compliance', 'informe_tecnico', 'otro']), ('kind', ''), _connector='OR'), name='offers_document_kind_valid'),
        ),
    ]
