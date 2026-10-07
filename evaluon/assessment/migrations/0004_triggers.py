"""Solo inserción para `assessment_technical_ok` (REQ-061; ADR-0043; T-165).

Usa la función `assessment_reject_change` de la migración `0002_triggers`. Las columnas nuevas
de `assessment_result` y `assessment_citation` (migración `0003`) no necesitan trigger: agregar
una columna no dispara UPDATE y esas tablas ya tienen el suyo.
"""

from django.db import migrations

FORWARD = """
CREATE TRIGGER assessment_technical_ok_append_only
    BEFORE UPDATE OR DELETE ON assessment_technical_ok
    FOR EACH ROW EXECUTE FUNCTION assessment_reject_change();
"""

REVERSE = "DROP TRIGGER assessment_technical_ok_append_only ON assessment_technical_ok;\n"


class Migration(migrations.Migration):

    dependencies = [
        ("assessment", "0003_resultados_decisiones_literales"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD, reverse_sql=REVERSE),
    ]
