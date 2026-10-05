"""Reglas de la 008 que la base hace valer con triggers (plan 008, "Modelo de datos";
"Inmutabilidad"; T-130).

**Solo inserción** (P6): las lecturas, los pasajes, los pedidos al modelo y el historial de
la ficha rechazan todo UPDATE y DELETE, venga el cambio del modelo, de `QuerySet.update()`
o de SQL directo, como `tenders_run_step` en la 003.

Para limpiar datos de prueba hay que recrear la base.
"""

from django.db import migrations

TABLES = ("offers_reading", "offers_passage", "offers_sheet_step", "offers_change")

FORWARD = r"""
CREATE FUNCTION offers_reject_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'La tabla % solo admite agregar filas: una fila registrada no se puede modificar ni borrar.', TG_TABLE_NAME;
END;
$$;
""" + "".join(
    f"""
CREATE TRIGGER {table}_append_only
    BEFORE UPDATE OR DELETE ON {table}
    FOR EACH ROW EXECUTE FUNCTION offers_reject_change();
"""
    for table in TABLES
)

REVERSE = "".join(f"DROP TRIGGER {table}_append_only ON {table};\n" for table in TABLES) + (
    "DROP FUNCTION offers_reject_change();\n"
)


class Migration(migrations.Migration):

    dependencies = [
        ("offers", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD, reverse_sql=REVERSE),
    ]
