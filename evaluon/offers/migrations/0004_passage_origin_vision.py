# Cambio de opciones (T-160; ADR-0041): el origen del texto de un pasaje de una oferta suma
# `vision`, el texto que el modelo transcribió mirando la imagen de la página.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('offers', '0003_docx_format'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='passage',
            name='offers_passage_text_origin_valid',
        ),
        migrations.AlterField(
            model_name='passage',
            name='text_origin',
            field=models.CharField(choices=[('pdf_text', 'PDF con texto'), ('ocr', 'Reconocimiento de texto'), ('web', 'Página web'), ('vision', 'Leída por visión')], max_length=10, verbose_name='origen del texto'),
        ),
        migrations.AddConstraint(
            model_name='passage',
            constraint=models.CheckConstraint(condition=models.Q(('text_origin__in', ['pdf_text', 'ocr', 'web', 'vision'])), name='offers_passage_text_origin_valid'),
        ),
    ]
