"""Comando `registrar_relacion`: registra que una norma modifica, complementa, reglamenta
o deroga a otra, con la fecha desde la que rige el cambio y, si corresponde, las
unidades (REQ-006, REQ-007, REQ-020; plan 001, "Pantalla, acceso y comandos").

Rol: lectura y escritura. Las normas se indican por su número de norma, el que muestra
`listar_normas` ("norma 2"); las unidades, por su clave, la que muestra `ver_informe`
(`art-2`, `anexo/art-50`). Sin clave de unidad, la relación es desde o hacia la norma
entera. La fecha la escribe la persona: el sistema no la calcula. Recibe `--usuario`;
la clave se pide por teclado. Solo traduce y llama a
`evaluon.norms.services.relations`.

Ejemplo, la derogación de la Disposición AFIP 297/03 por el artículo 2 de la
Disposición AFIP 247/2022, desde su entrada en vigencia (si `listar_normas` muestra la
247/2022 como norma 2 y la 297/03 como norma 1):

    python manage.py registrar_relacion --tipo deroga --origen 2 --unidad-origen art-2 \\
        --alcanzada 1 --fecha 2023-01-01 --usuario responsable
"""

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import Channel
from evaluon.norms.models import RelationType
from evaluon.norms.services import relations


def _date(value):
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        raise CommandError(
            f"La fecha de --fecha ({value}) no es válida: escríbala como AAAA-MM-DD, por "
            "ejemplo 2023-01-01."
        ) from None


class Command(BaseCommand):
    help = (
        "Registra que una norma modifica, complementa, reglamenta o deroga a otra, con "
        "la fecha desde la que rige el cambio y, si corresponde, las unidades."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tipo", required=True,
            help=f"Tipo de relación: {', '.join(RelationType.values)}.",
        )
        parser.add_argument(
            "--origen", type=int, required=True,
            help="Número de la norma que modifica, complementa, reglamenta o deroga, "
            "como lo muestra listar_normas.",
        )
        parser.add_argument(
            "--unidad-origen", dest="unidad_origen", default="",
            help="Clave de la unidad de la norma de origen que trae el cambio, por "
            "ejemplo art-2. Sin ella, la relación es desde la norma entera.",
        )
        parser.add_argument(
            "--alcanzada", type=int, required=True,
            help="Número de la norma alcanzada, como lo muestra listar_normas.",
        )
        parser.add_argument(
            "--unidad-alcanzada", dest="unidad_alcanzada", default="",
            help="Clave de la unidad alcanzada, por ejemplo anexo/art-14/inc-b. Sin "
            "ella, la relación alcanza a la norma entera.",
        )
        parser.add_argument(
            "--fecha", required=True,
            help="Fecha desde la que rige el cambio, como AAAA-MM-DD. El sistema no la "
            "calcula.",
        )
        permissions.add_user_argument(parser)

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        effective_date = _date(options["fecha"])
        try:
            result = relations.register_relation(
                user,
                relation_type=options["tipo"],
                source_norm=options["origen"],
                target_norm=options["alcanzada"],
                source_unit_key=options["unidad_origen"],
                target_unit_key=options["unidad_alcanzada"],
                effective_date=effective_date,
                channel=Channel.COMMAND,
            )
        except (RoleRejected, relations.RelationRefused) as error:
            raise CommandError(str(error)) from None

        relation = result.relation
        source = relation.source_unit_key or "la norma entera"
        target = relation.target_unit_key or "la norma entera"
        self.stdout.write(
            f"Se registró la relación {relation.pk}: la {relation.source_norm.citation} "
            f"({source}) {RelationType(relation.relation_type).label.lower()} a la "
            f"{relation.target_norm.citation} ({target}), desde el "
            f"{relation.effective_date.strftime('%d/%m/%Y')}.\n"
            f"Se creó la versión {result.corpus_version} de la normativa."
        )
