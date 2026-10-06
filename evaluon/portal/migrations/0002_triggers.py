"""Reglas del Portal que la base hace valer con triggers (plan 012, "Inmutabilidad"; T-138).

- `portal_page` y `portal_file` son de **solo inserción** (P6): rechazan UPDATE y DELETE,
  venga el cambio del modelo, de `QuerySet.update()` o de SQL directo. Lo bajado del Portal
  es la evidencia del origen de cada dato (REQ-049).
- `portal_item` rechaza el UPDATE que cambie su **contenido** (propuesta, tipo, clave,
  datos, huella, campos dañados, página y archivo de origen). Cambian solo el estado y los
  campos de decisión y de carga.

Para limpiar datos de prueba hay que recrear la base.
"""

from django.db import migrations

APPEND_ONLY = ("portal_page", "portal_file")

FORWARD = r"""
CREATE FUNCTION portal_reject_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'La tabla % solo admite agregar filas: una fila registrada no se puede modificar ni borrar.', TG_TABLE_NAME;
END;
$$;

CREATE FUNCTION portal_item_reject_content_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.proposal_id, NEW.kind, NEW.key, NEW.payload, NEW.content_sha256,
        NEW.damaged_fields, NEW.page_id, NEW.file_id)
       IS DISTINCT FROM
       (OLD.proposal_id, OLD.kind, OLD.key, OLD.payload, OLD.content_sha256,
        OLD.damaged_fields, OLD.page_id, OLD.file_id) THEN
        RAISE EXCEPTION 'El contenido de un ítem de la propuesta no se puede modificar: solo su estado y su decisión.';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER portal_item_content_immutable
    BEFORE UPDATE ON portal_item
    FOR EACH ROW EXECUTE FUNCTION portal_item_reject_content_change();
""" + "".join(
    f"""
CREATE TRIGGER {table}_append_only
    BEFORE UPDATE OR DELETE ON {table}
    FOR EACH ROW EXECUTE FUNCTION portal_reject_change();
"""
    for table in APPEND_ONLY
)

REVERSE = (
    "".join(f"DROP TRIGGER {table}_append_only ON {table};\n" for table in APPEND_ONLY)
    + "DROP TRIGGER portal_item_content_immutable ON portal_item;\n"
    + "DROP FUNCTION portal_item_reject_content_change();\n"
    + "DROP FUNCTION portal_reject_change();\n"
)


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=FORWARD, reverse_sql=REVERSE),
    ]
