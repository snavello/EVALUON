# T-193 (REQ-077, REQ-083): renglones, expediente y CUIT con documento de origen: `item` admite nulo y
# exactamente uno entre `item` y `document` (ADR-0049).


import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('offers', '0007_historial_y_alta_desde_los_archivos'),
        ('portal', '0003_garantias'),
        ('tenders', '0009_historial_y_alta_desde_el_pliego'),
    ]

    operations = [
        migrations.AddField(
            model_name='portalline',
            name='document',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='portal_lines', to='tenders.document', verbose_name='documento de origen'),
        ),
        migrations.AddField(
            model_name='portalofferdata',
            name='document',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='portal_offer_data', to='offers.document', verbose_name='documento de origen'),
        ),
        migrations.AddField(
            model_name='portalproceduredata',
            name='document',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='portal_procedure_data', to='tenders.document', verbose_name='documento de origen'),
        ),
        migrations.AlterField(
            model_name='portalline',
            name='item',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='lines', to='portal.portalitem', verbose_name='ítem de origen'),
        ),
        migrations.AlterField(
            model_name='portalofferdata',
            name='item',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='offer_data', to='portal.portalitem', verbose_name='ítem de origen'),
        ),
        migrations.AlterField(
            model_name='portalproceduredata',
            name='item',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='procedure_data', to='portal.portalitem', verbose_name='ítem de origen'),
        ),
        migrations.AddConstraint(
            model_name='portalline',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('item__isnull', False), ('document__isnull', True)), models.Q(('item__isnull', True), ('document__isnull', False)), _connector='OR'), name='portal_line_exactly_one_origin'),
        ),
        migrations.AddConstraint(
            model_name='portalofferdata',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('item__isnull', False), ('document__isnull', True)), models.Q(('item__isnull', True), ('document__isnull', False)), _connector='OR'), name='portal_offer_data_exactly_one_origin'),
        ),
        migrations.AddConstraint(
            model_name='portalproceduredata',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('item__isnull', False), ('document__isnull', True)), models.Q(('item__isnull', True), ('document__isnull', False)), _connector='OR'), name='portal_procedure_data_exactly_one_origin'),
        ),
    ]
