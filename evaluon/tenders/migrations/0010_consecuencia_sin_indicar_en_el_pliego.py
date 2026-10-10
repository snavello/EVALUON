# T-232 (REQ-081; REQ-029 de la 003): la Comisión puede elegir «El pliego no indica consecuencia»
# cuando el pliego no dice ninguna. Es un tipo más de la lista de consecuencias: se agrega a la
# restricción de valores válidos, sin tocar filas ni las demás restricciones.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenders', '0009_historial_y_alta_desde_el_pliego'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='consequence',
            name='tenders_consequence_type_valid',
        ),
        migrations.AlterField(
            model_name='consequence',
            name='consequence_type',
            field=models.CharField(choices=[('desestimacion', 'Desestimación sin posibilidad de subsanar'), ('intimacion_subsanar', 'Intimación a subsanar; si no se subsana, desestimación'), ('consultar_oferente', 'Consultar al oferente'), ('aprobacion_condicionada', 'Aprobación condicionada'), ('aprobar_igual', 'Aprobar de todas maneras'), ('otra_pliego', 'Otra consecuencia prevista en el pliego'), ('sin_consecuencia', 'El pliego no indica consecuencia'), ('no_determinada', 'No determinada')], max_length=30, verbose_name='tipo'),
        ),
        migrations.AddConstraint(
            model_name='consequence',
            constraint=models.CheckConstraint(condition=models.Q(('consequence_type__in', ['desestimacion', 'intimacion_subsanar', 'consultar_oferente', 'aprobacion_condicionada', 'aprobar_igual', 'otra_pliego', 'sin_consecuencia', 'no_determinada'])), name='tenders_consequence_type_valid'),
        ),
    ]
