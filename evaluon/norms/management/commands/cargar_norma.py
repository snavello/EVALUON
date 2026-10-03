"""Comando `cargar_norma`: incorpora el documento de una norma con sus datos, su
categoría y su parte (REQ-001, REQ-002, REQ-004, REQ-012, REQ-017, REQ-020; plan 001,
"Pantalla, acceso y comandos").

Rol: lectura y escritura. Recibe la ruta del archivo, los datos de la norma, `--parte`
(por omisión, `cuerpo`), `--regimen-general` y `--usuario`; la clave se pide por
teclado. Solo traduce y llama a `evaluon.norms.services.loading`.

Ejemplo, el anexo de la Disposición AFIP 247/2022:

    python manage.py cargar_norma corpus/normativa/disp-afip-247-2022-anexo.pdf \\
        --categoria regimen_especifico --tipo Disposición --numero 247 --anio 2022 \\
        --organismo AFIP --titulo "Régimen General para Contrataciones ..." \\
        --nombre "Disposición AFIP 247/2022" --fecha-publicacion 2022-11-30 \\
        --fecha-vigencia 2023-01-01 --fuente https://... --parte anexo \\
        --regimen-general --usuario responsable
"""

from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import Channel
from evaluon.norms.models import Category
from evaluon.norms.services import loading


def _date(value, option):
    if value is None:
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        raise CommandError(
            f"La fecha de {option} ({value}) no es válida: escríbala como AAAA-MM-DD, por "
            "ejemplo 2023-01-01."
        ) from None


def _year(value):
    if value is None:
        return None
    try:
        return int(value.strip())
    except ValueError:
        raise CommandError(
            f"El año de --anio ({value}) no es válido: escríbalo con cuatro cifras, por "
            "ejemplo 2022."
        ) from None


class Command(BaseCommand):
    help = (
        "Incorpora el documento de una norma con sus datos, su categoría y su parte. "
        "Deja una lectura pendiente de validación: revise su informe con ver_informe y "
        "valídela con validar_informe."
    )

    def add_arguments(self, parser):
        parser.add_argument("archivo", help="Ruta del archivo de la norma (PDF).")
        parser.add_argument(
            "--categoria",
            help=f"Categoría del documento: {', '.join(Category.values)}. Obligatoria.",
        )
        parser.add_argument("--tipo", help='Tipo de norma, por ejemplo "Disposición".')
        parser.add_argument("--numero", help="Número de la norma, por ejemplo 247.")
        parser.add_argument("--anio", help="Año de la norma, con cuatro cifras.")
        parser.add_argument("--organismo", help='Organismo emisor, por ejemplo "AFIP".')
        parser.add_argument("--titulo", help="Título de la norma.")
        parser.add_argument(
            "--nombre",
            help='Nombre con que se cita la norma, por ejemplo "Disposición AFIP '
            '247/2022". Obligatorio al cargar una norma nueva.',
        )
        parser.add_argument(
            "--fecha-publicacion", dest="fecha_publicacion",
            help="Fecha de publicación, como AAAA-MM-DD.",
        )
        parser.add_argument(
            "--fecha-vigencia", dest="fecha_vigencia",
            help="Fecha desde la que rige el texto, como AAAA-MM-DD. El sistema no la "
            "calcula.",
        )
        parser.add_argument("--fuente", help="De dónde se obtuvo el documento.")
        parser.add_argument(
            "--parte", default="cuerpo",
            help="Qué parte de la norma es el archivo: cuerpo (por omisión) o la clave "
            "de un anexo, como anexo o anexo-i.",
        )
        parser.add_argument(
            "--regimen-general", dest="regimen_general", action="store_true",
            help="La norma aprueba un régimen general de contrataciones. Solo con la "
            "categoría regimen_especifico.",
        )
        permissions.add_user_argument(parser)

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        path = Path(options["archivo"])
        try:
            data = path.read_bytes()
        except OSError:
            raise CommandError(f"No se encontró el archivo {path} o no se puede abrir.") from None

        fields = {
            "category": options["categoria"],
            "norm_type": options["tipo"],
            "number": options["numero"],
            "year": _year(options["anio"]),
            "issuer": options["organismo"],
            "title": options["titulo"],
            "citation": options["nombre"],
            "publication_date": _date(options["fecha_publicacion"], "--fecha-publicacion"),
            "effective_from": _date(options["fecha_vigencia"], "--fecha-vigencia"),
            "source": options["fuente"],
        }
        try:
            result = loading.load_norm(
                user,
                data=data,
                file_name=path.name,
                part=options["parte"],
                general_regime=options["regimen_general"],
                channel=Channel.COMMAND,
                **fields,
            )
        except (RoleRejected, loading.LoadRefused) as error:
            raise CommandError(str(error)) from None

        reading = result.reading
        report = reading.report
        not_read = ", ".join(str(n) for n in report["pages"]["not_read"]) or "ninguna"
        new = "norma nueva" if result.created_norm else "norma ya cargada"
        self.stdout.write(
            f"Se cargó el documento {result.document.pk}: parte {result.document.part} de "
            f"la {result.norm.citation} ({new}).\n"
            f"Lectura {reading.pk}, pendiente de validación: {result.units} unidades, "
            f"{report['pages']['total']} páginas, páginas no leídas: {not_read}, "
            f"{len(report['unlocated'])} tramos no ubicados.\n"
            f"Revise el informe con: ver_informe {reading.pk} --usuario "
            f"{user.get_username()}\n"
            f"Para que la norma se pueda consultar, valídelo con: validar_informe "
            f"{reading.pk} --usuario {user.get_username()}"
        )
