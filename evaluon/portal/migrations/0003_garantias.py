"""Una oferta puede tener más de una garantía (T-144; aviso de T-143).

Paso 1 (aditivo): tabla `portal_guarantee`. Paso 2: copia la garantía única que ya estaba en
`portal_offer_data` (solo las filas que tenían alguna). Paso 3: quita las tres columnas de la
garantía única de `portal_offer_data`; la marcha atrás las vuelve a crear y copia la primera
garantía de cada oferta.
"""

import django.db.models.deletion
from django.db import migrations, models


def move_guarantees(apps, schema_editor):
    OfferData = apps.get_model("portal", "PortalOfferData")
    Guarantee = apps.get_model("portal", "PortalGuarantee")
    for data in OfferData.objects.all():
        if data.guarantee_type or data.guarantee_form or data.guarantee_amount is not None:
            Guarantee.objects.create(
                offer_data=data, guarantee_type=data.guarantee_type,
                guarantee_form=data.guarantee_form, amount=data.guarantee_amount,
                item=data.item,
            )


def restore_first_guarantee(apps, schema_editor):
    OfferData = apps.get_model("portal", "PortalOfferData")
    for data in OfferData.objects.all():
        first = data.guarantees.order_by("id").first()
        if first is not None:
            data.guarantee_type = first.guarantee_type
            data.guarantee_form = first.guarantee_form
            data.guarantee_amount = first.amount
            data.save(update_fields=["guarantee_type", "guarantee_form", "guarantee_amount"])


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0002_triggers"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalGuarantee",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("guarantee_type", models.CharField(blank=True, max_length=100, verbose_name="tipo de garantía")),
                ("guarantee_form", models.CharField(blank=True, max_length=100, verbose_name="forma de garantía")),
                ("amount", models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True, verbose_name="monto de la garantía")),
                ("item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="guarantees", to="portal.portalitem", verbose_name="ítem de origen")),
                ("offer_data", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="guarantees", to="portal.portalofferdata", verbose_name="datos de la oferta")),
            ],
            options={
                "verbose_name": "garantía de la oferta del Portal",
                "verbose_name_plural": "garantías de la oferta del Portal",
                "db_table": "portal_guarantee",
                "ordering": ["offer_data_id", "id"],
            },
        ),
        migrations.RunPython(move_guarantees, restore_first_guarantee),
        migrations.RemoveField(model_name="portalofferdata", name="guarantee_type"),
        migrations.RemoveField(model_name="portalofferdata", name="guarantee_form"),
        migrations.RemoveField(model_name="portalofferdata", name="guarantee_amount"),
    ]
