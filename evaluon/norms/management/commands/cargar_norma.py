"""Comando `cargar_norma`: incorpora el documento de una norma con sus datos, su
categoría y su parte (REQ-001, REQ-002, REQ-004, REQ-011, REQ-012, REQ-017, REQ-020;
plan 001, "Pantalla, acceso y comandos" e "Ingesta").

Rol: lectura y escritura. Recibe la ruta del archivo, los datos de la norma, `--parte`
(por omisión, `cuerpo`), `--regimen-general` y `--usuario`; la clave se pide por
teclado. Solo traduce y llama a `evaluon.norms.services.loading`.

Si el documento es la misma norma que uno ya cargado (REQ-011), muestra el aviso y
pregunta por teclado si es otro archivo de lo mismo o una versión nueva; cualquier otra
respuesta, o la falta de teclado, deja el documento sin incorporar.
`--confirmar-misma-norma {otro-archivo,version-nueva}` da esa respuesta de antemano,
sin preguntar: sirve para los tests y para la carga del corpus. Al sumar una parte a una
norma ya cargada lo informa sin preguntar, y avisa si la fecha de vigencia difiere de la
de otra parte en uso.

Ejemplo, el anexo de la Disposición AFIP 247/2022:

    python manage.py cargar_norma corpus/normativa/disp-afip-247-2022-anexo.pdf \\
        --categoria regimen_especifico --tipo Disposición --numero 247 --anio 2022 \\
        --organismo AFIP --titulo "Régimen General para Contrataciones ..." \\
        --nombre "Disposición AFIP 247/2022" --fecha-publicacion 2022-11-30 \\
        --fecha-vigencia 2023-01-01 --fuente https://... --parte anexo \\
        --regimen-general --usuario responsable
"""

import unicodedata
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import Channel
from evaluon.norms.models import Category, SameNormConfirmation
from evaluon.norms.services import loading
from evaluon.norms.splitting.report import PAGE_LISTS, WEB_PAGE

# Valores de `--confirmar-misma-norma` y respuestas por teclado, sin tildes.
CONFIRMATIONS = {
    "otro-archivo": SameNormConfirmation.OTHER_FILE,
    "version-nueva": SameNormConfirmation.NEW_VERSION,
}

CONFIRMATION_PROMPT = (
    "¿Qué es este archivo? Escriba otro-archivo si es otro archivo de lo mismo, "
    "version-nueva si es una versión nueva, o cualquier otra cosa para no incorporarlo: "
)


def ask_confirmation(prompt):
    """Pregunta por teclado y devuelve lo que la persona escribió."""
    return input(prompt)


def _confirmation(answer):
    """La confirmación que corresponde a lo escrito, o `None`. Acepta "versión nueva" u
    "otro archivo", con o sin tilde y con espacio o guion."""
    text = unicodedata.normalize("NFKD", answer.strip().lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return CONFIRMATIONS.get("-".join(text.split()))


def _page_lists(report):
    """Las listas de páginas con la misma redacción del informe: "Ilegibles: ninguna.
    Casi sin texto: ninguna. ... Sin texto: 45. En blanco: ninguna." """
    summary = report["page_summary"]
    lists = []
    for name, _, title in PAGE_LISTS:
        numbers = [WEB_PAGE if n is None else str(n) for n in summary[name]]
        lists.append(f"{title}: {', '.join(numbers) or 'ninguna'}.")
    return " ".join(lists)


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
        parser.add_argument(
            "--confirmar-misma-norma", dest="confirmar_misma_norma",
            choices=sorted(CONFIRMATIONS),
            help="Si el sistema avisa que es la misma norma que un documento ya cargado, "
            "confirma sin preguntar que es otro archivo de lo mismo (otro-archivo) o una "
            "versión nueva (version-nueva). Sin esta opción, se pregunta por teclado.",
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
        given = options["confirmar_misma_norma"]
        shown = []

        def confirm(warning):
            self.stdout.write(warning.message)
            shown.append(warning)
            try:
                answer = ask_confirmation(CONFIRMATION_PROMPT)
            except EOFError:
                return None
            return _confirmation(answer)

        try:
            result = loading.load_norm(
                user,
                data=data,
                file_name=path.name,
                part=options["parte"],
                general_regime=options["regimen_general"],
                same_norm_confirmation=CONFIRMATIONS[given] if given else None,
                confirm_same_norm=confirm,
                channel=Channel.COMMAND,
                **fields,
            )
        except (RoleRejected, loading.LoadRefused) as error:
            raise CommandError(str(error)) from None

        if result.same_norm_warning is not None:
            if not shown:
                self.stdout.write(result.same_norm_warning.message)
            name = loading.CONFIRMATION_NAMES[result.document.same_norm_confirmation]
            self.stdout.write(
                f"Se incorporó como {name}. No se usa en las consultas hasta registrarlo "
                "con registrar_version, después de validarlo."
            )
        for notice in result.notices:
            self.stdout.write(notice)

        reading = result.reading
        report = reading.report
        new = "norma nueva" if result.created_norm else "norma ya cargada"
        self.stdout.write(
            f"Se cargó el documento {result.document.pk}: parte {result.document.part} de "
            f"la {result.norm.citation} ({new}).\n"
            f"Lectura {reading.pk}, pendiente de validación: {result.units} unidades, "
            f"{report['pages']['total']} páginas, {len(report['unlocated'])} tramos no "
            f"ubicados.\n"
            f"Páginas: {_page_lists(report)}\n"
            f"Revise el informe con: ver_informe {reading.pk} --usuario "
            f"{user.get_username()}\n"
            f"Para que la norma se pueda consultar, valídelo con: validar_informe "
            f"{reading.pk} --usuario {user.get_username()}"
        )
