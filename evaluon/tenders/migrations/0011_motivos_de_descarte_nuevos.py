# T-250 (REQ-102; plan 015, "Modelo de datos"; ADR-0054, regla 5): los motivos de descarte
# nuevos que la Comisión decidió el 2026-10-10 (consecuencia, condición opcional, pago o
# factura, forma de presentar por el Portal y compromiso al presentarse). Solo agrega valores
# permitidos a las restricciones de `tenders_disposition.discard_reason` y de
# `tenders_discarded_row.reason`: las filas ya guardadas no cambian y se puede deshacer.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenders', '0010_consecuencia_sin_indicar_en_el_pliego'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='discardedrow',
            name='tenders_discarded_row_reason_valid',
        ),
        migrations.RemoveConstraint(
            model_name='disposition',
            name='tenders_disposition_discard_reason_valid',
        ),
        migrations.AlterField(
            model_name='discardedrow',
            name='reason',
            field=models.CharField(choices=[('titulo', 'Título'), ('dato_procedimiento', 'Definición o dato del procedimiento'), ('norma_aplicable', 'Norma aplicable'), ('obligacion_organismo', 'Obligación del organismo'), ('ejecucion_contrato', 'Obligación de la ejecución del contrato'), ('formulario', 'Formulario a completar'), ('indice_caratula', 'Índice o carátula'), ('consecuencia_sancion', 'Consecuencia o sanción'), ('derecho_posterior', 'Derecho posterior a la oferta'), ('condicion_opcional', 'Condición opcional del oferente'), ('pago_factura', 'Pago, moneda de pago o factura'), ('forma_presentacion_portal', 'Forma de presentar la oferta por el Portal'), ('compromiso_presentacion', 'Compromiso que se cumple al presentarse')], max_length=30, verbose_name='motivo'),
        ),
        migrations.AlterField(
            model_name='disposition',
            name='discard_reason',
            field=models.CharField(blank=True, choices=[('titulo', 'Título'), ('dato_procedimiento', 'Definición o dato del procedimiento'), ('norma_aplicable', 'Norma aplicable'), ('obligacion_organismo', 'Obligación del organismo que la oferta no puede contradecir ni condicionar'), ('ejecucion_contrato', 'Obligación de la ejecución del contrato'), ('formulario', 'Formulario a completar'), ('indice_caratula', 'Índice o carátula'), ('consecuencia_sancion', 'Consecuencia o sanción'), ('condicion_opcional', 'Condición que solo vale si el oferente elige esa opción'), ('pago_factura', 'Pago, moneda de pago o factura'), ('forma_presentacion_portal', 'Forma de presentar la oferta por el Portal'), ('compromiso_presentacion', 'Compromiso que se cumple al presentarse')], max_length=30, verbose_name='motivo de descarte'),
        ),
        migrations.AddConstraint(
            model_name='discardedrow',
            constraint=models.CheckConstraint(condition=models.Q(('reason__in', ['titulo', 'dato_procedimiento', 'norma_aplicable', 'obligacion_organismo', 'ejecucion_contrato', 'formulario', 'indice_caratula', 'consecuencia_sancion', 'derecho_posterior', 'condicion_opcional', 'pago_factura', 'forma_presentacion_portal', 'compromiso_presentacion'])), name='tenders_discarded_row_reason_valid'),
        ),
        migrations.AddConstraint(
            model_name='disposition',
            constraint=models.CheckConstraint(condition=models.Q(('discard_reason__in', ['titulo', 'dato_procedimiento', 'norma_aplicable', 'obligacion_organismo', 'ejecucion_contrato', 'formulario', 'indice_caratula', 'consecuencia_sancion', 'condicion_opcional', 'pago_factura', 'forma_presentacion_portal', 'compromiso_presentacion']), ('discard_reason', ''), _connector='OR'), name='tenders_disposition_discard_reason_valid'),
        ),
    ]
