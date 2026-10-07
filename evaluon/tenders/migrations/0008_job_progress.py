# T-184 (REQ-067, ADR-0045 3.B): avance fino de los pedidos en la cola.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenders', '0007_evaluacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='progress',
            field=models.JSONField(blank=True, default=dict, verbose_name='avance'),
        ),
    ]
