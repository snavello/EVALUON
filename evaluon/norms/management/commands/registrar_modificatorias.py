"""Comando `registrar_modificatorias`: anota las modificatorias de una norma que todavía
no están cargadas en el sistema (REQ-012, REQ-021; plan 001, "Modificatorias sin
cargar" y "Pantalla, acceso y comandos").

Rol: lectura y escritura. La norma alcanzada se indica por su número de norma, el que
muestra `listar_normas`. Las modificatorias se dan en lote, con `--archivo` (un CSV con
las columnas tipo, numero, anio, organismo y referencia, un renglón por modificatoria),
o de a una, con `--tipo`, `--numero`, `--anio`, `--organismo` y `--referencia`. Recibe
`--usuario`; la clave se pide por teclado. Solo traduce y llama a
`evaluon.norms.services.amendments`.

Ejemplo, las modificatorias de la Disposición AFIP 297/03 (si `listar_normas` la muestra
como norma 1):

    python manage.py registrar_modificatorias --alcanzada 1 \\
        --archivo corpus/normativa/referencias/disp-afip-297-2003-modificatorias.csv \\
        --usuario responsable
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import Channel
from evaluon.norms.services import amendments

# Opciones de la modificatoria suelta y el campo que llenan.
SINGLE_OPTIONS = {
    "tipo": "norm_type",
    "numero": "number",
    "anio": "year",
    "organismo": "issuer",
    "referencia": "source_ref",
}


def _name(entry):
    """`disposicion 12/2004 · organismo: afip`, de una fila o de un diccionario."""
    get = entry.get if isinstance(entry, dict) else lambda name: getattr(entry, name)
    return (
        f"{get('norm_type')} {get('number')}/{get('year')} · organismo: {get('issuer')}"
    )


class Command(BaseCommand):
    help = (
        "Anota las modificatorias de una norma que todavía no están cargadas, en lote "
        "desde un archivo CSV o de a una."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--alcanzada", type=int, required=True,
            help="Número de la norma que tiene las modificatorias, como lo muestra "
            "listar_normas.",
        )
        parser.add_argument(
            "--archivo",
            help="CSV en UTF-8 con las columnas tipo, numero, anio, organismo y "
            "referencia, un renglón por modificatoria.",
        )
        parser.add_argument("--tipo", help='Tipo de la modificatoria, por ejemplo "Disposición".')
        parser.add_argument("--numero", help="Número de la modificatoria.")
        parser.add_argument("--anio", help="Año de la modificatoria, con cuatro cifras.")
        parser.add_argument("--organismo", help="Organismo emisor de la modificatoria.")
        parser.add_argument(
            "--referencia",
            help="Referencia en la fuente: la dirección de la ficha en Infoleg.",
        )
        permissions.add_user_argument(parser)

    def handle(self, *args, **options):
        single = {field: options[option] for option, field in SINGLE_OPTIONS.items()}
        given = any(value is not None for value in single.values())
        if options["archivo"] and given:
            raise CommandError(
                "Indique las modificatorias con --archivo o con --tipo, --numero, "
                "--anio, --organismo y --referencia, no de las dos maneras a la vez."
            )
        if not options["archivo"] and not given:
            raise CommandError(
                "Indique las modificatorias con --archivo (un CSV) o una sola con "
                "--tipo, --numero, --anio, --organismo y --referencia."
            )
        data = None
        if options["archivo"]:
            path = Path(options["archivo"])
            try:
                data = path.read_bytes()
            except OSError:
                raise CommandError(
                    f"No se encontró el archivo {path} o no se puede abrir."
                ) from None

        user = permissions.authenticate_command(options["usuario"])
        try:
            if data is not None:
                result = amendments.register_amendments_file(
                    user, target_norm=options["alcanzada"], data=data,
                    file_name=path.name, channel=Channel.COMMAND,
                )
            else:
                result = amendments.register_amendments(
                    user, target_norm=options["alcanzada"], amendments=[single],
                    channel=Channel.COMMAND,
                )
        except (RoleRejected, amendments.AmendmentsRefused) as error:
            raise CommandError(str(error)) from None

        citation = result.target_norm.citation
        lines = [f"Se anotaron {len(result.added)} modificatorias sin cargar de la "
                 f"{citation}."]
        lines += [f"  - {_name(entry)}" for entry in result.added]
        lines.append(f"Ya estaban anotadas: {len(result.already)}.")
        lines += [f"  - {_name(entry)}: ya estaba anotada" for entry in result.already]
        lines.append(f"Quedaron cargadas en el acto: {len(result.loaded)}.")
        lines += [f"  - {_name(entry)}: norma {entry.loaded_norm_id}"
                  for entry in result.loaded]
        lines.append(f"Quedan {result.pending} modificatorias sin cargar de la {citation}.")
        if result.added or result.loaded:
            lines.append(f"Se creó la versión {result.corpus_version} de la normativa.")
        else:
            lines.append(
                "No cambió nada: la normativa sigue en la versión "
                f"{result.corpus_version}."
            )
        self.stdout.write("\n".join(lines))
