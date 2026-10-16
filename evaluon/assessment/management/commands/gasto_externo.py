"""Comando `gasto_externo`: el gasto real de los pedidos a la API externa y el escaneo del filtro
de lo reservado (T-290; REQ-121 y REQ-122; ADR-0067, punto 5, y ADR-0068, punto 6; plan 016,
"Costo y tope").

Rol: operador de la Comisión (el evaluador lo incluye). Recibe `--usuario`; la clave se pide por
teclado (REQ-016). Lee el registro de auditoría (hechos `external_request`); no cambia nada y no
llama a ningún modelo.

Opciones:

- `--mes AAAA-MM`: solo los pedidos de ese mes calendario (hora de `TIME_ZONE`). Sin `--mes` ni
  `--procedimiento`, el mes en curso.
- `--procedimiento N`: solo los pedidos de ese procedimiento (su número), todas las rondas.
- `--por-etapa`: suma además por etapa (`matriz_extraccion`, `verificador`...).
- `--verificar-filtro`: cuenta los pedidos registrados que contienen texto de una hoja de
  compliance: cualquier secuencia de 8 palabras seguidas (sin tildes ni mayúsculas) de un
  documento `compliance` cargado en la base (o con la sugerencia `compliance` en su lectura,
  H-290-3), en el pedido armado entero (sistema y mensajes en orden) o en cualquier otro texto
  del hecho. El criterio de REQ-121 es 0; si encuentra alguno, termina con error. Usa una
  implementación **propia**, que no importa ni llama a la puerta (`evaluon/ai/external/guard.py`):
  es el control independiente.

Los hechos `en_vuelo` (uno por lote, O-290-6) no son pedidos ni gasto real: se informan aparte
los lotes sin cerrar, con su estimado.

Imprime el gasto real (la suma de `costo_usd`, el que se calculó con el uso informado por el
proveedor) y la cantidad de pedidos por resultado; cada registro de medición pega esta salida.
"""

import re
import unicodedata
from datetime import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.accounts.models import CommissionRole
from evaluon.audit.models import AuditEvent, EventType
from evaluon.offers.models import Document, DocumentKind, Passage, Reading
from evaluon.tenders.models import Procedure

WINDOW = 8
RESULTS = ("ok", "reutilizado", "bloqueado", "error", "vencido")
IN_FLIGHT = "en_vuelo"
_SEPARATOR = re.compile(r"[^0-9a-z]+")


def _tokens(text):
    """Palabras en minúsculas y sin tildes (implementación propia, distinta de la de la puerta:
    descompone, descarta lo que no es ASCII y corta en todo lo que no sea letra o número). Antes
    descarta los caracteres invisibles de formato (`Cf`) y el guion blando, y normaliza con NFKC
    (H-290-2): las letras de ancho completo pasan a ser letras comunes y no se pierden."""
    visible = "".join(char for char in text
                      if char != "\u00ad" and unicodedata.category(char) != "Cf")
    composed = unicodedata.normalize("NFKC", visible)
    ascii_text = unicodedata.normalize("NFD", composed).encode("ascii", "ignore").decode("ascii")
    return [token for token in _SEPARATOR.split(ascii_text.lower()) if token]


def _windows(text):
    tokens = _tokens(text)
    return {" ".join(tokens[i:i + WINDOW]) for i in range(len(tokens) - WINDOW + 1)}


def _strings(value):
    """Todos los textos de un valor JSON, en cualquier nivel (claves incluidas)."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


def _sheet_windows():
    """Las secuencias de todas las hojas de compliance de la base (todas sus lecturas y
    pasajes), y cuántas hojas hay y cuántas sin lectura."""
    # Las hojas y los documentos con la sugerencia `compliance` en alguna lectura (H-290-3).
    sheets = list(Document.objects.filter(
        Q(kind=DocumentKind.COMPLIANCE) | Q(readings__report__suggestion__kind="compliance"))
        .distinct().values_list("pk", flat=True))
    found = set()
    for text in Reading.objects.filter(document_id__in=sheets).values_list(
            "canonical_text", flat=True):
        found |= _windows(text)
    for text in Passage.objects.filter(reading__document_id__in=sheets).values_list(
            "text", flat=True):
        found |= _windows(text)
    read = set(Reading.objects.filter(document_id__in=sheets).values_list(
        "document_id", flat=True))
    return found, len(sheets), len([pk for pk in sheets if pk not in read])


def _whole_request(detail):
    """El pedido tal como salió, en un solo texto: el sistema y los mensajes en orden, separados
    por un salto de línea (H-290-1: un párrafo repartido entre mensajes se ve igual)."""
    sent = detail.get("texto_enviado") if isinstance(detail, dict) else None
    if not isinstance(sent, dict):
        return ""
    parts = [sent.get("sistema") or ""]
    for message in sent.get("mensajes") or []:
        if isinstance(message, dict):
            parts.append(message.get("texto") or "")
    return "\n".join(str(part) for part in parts)


def _leaks(detail, sheet_windows):
    """Las secuencias de una hoja que aparecen en el pedido armado o en algún texto del hecho."""
    hits = _windows(_whole_request(detail)) & sheet_windows
    for text in _strings(detail):
        hits |= _windows(text) & sheet_windows
    return hits


def _closed_batches():
    """Los lotes que ya tienen algún hecho de pedido registrado."""
    return set(AuditEvent.objects.filter(event_type=EventType.EXTERNAL_REQUEST)
               .exclude(detail__resultado=IN_FLIGHT).exclude(detail__lote_id=None)
               .values_list("detail__lote_id", flat=True))


def _usd(value):
    return f"{Decimal(value).quantize(Decimal('0.000001'))} USD"


class Command(BaseCommand):
    help = "Gasto real de la API externa por mes, caso y etapa, y escaneo del filtro."

    def add_arguments(self, parser):
        permissions.add_user_argument(parser)
        parser.add_argument("--mes", default=None, help="Mes calendario, AAAA-MM.")
        parser.add_argument("--procedimiento", default=None,
                            help="Número del procedimiento.")
        parser.add_argument("--por-etapa", action="store_true", dest="por_etapa",
                            help="Suma también por etapa.")
        parser.add_argument("--verificar-filtro", action="store_true", dest="verificar_filtro",
                            help="Cuenta los pedidos con texto de una hoja de compliance "
                                 "(criterio: 0).")

    def handle(self, *args, **options):
        user = permissions.authenticate_command(options["usuario"])
        try:
            permissions.require_commission_role(user, CommissionRole.OPERATOR,
                                                operation="gasto_externo")
        except RoleRejected as error:
            raise CommandError(str(error)) from None
        events, scope = self._events(options)
        self._spend(events, scope, by_stage=options["por_etapa"])
        if options["verificar_filtro"]:
            self._verify(events)

    def _events(self, options):
        events = AuditEvent.objects.filter(event_type=EventType.EXTERNAL_REQUEST)
        scope = []
        month = options["mes"]
        if month is None and options["procedimiento"] is None:
            month = timezone.localtime().strftime("%Y-%m")
        if month is not None:
            try:
                start = datetime.strptime(month, "%Y-%m")
            except ValueError:
                raise CommandError("--mes tiene que ser AAAA-MM.") from None
            end = (datetime(start.year + 1, 1, 1) if start.month == 12
                   else datetime(start.year, start.month + 1, 1))
            zone = timezone.get_current_timezone()
            events = events.filter(occurred_at__gte=timezone.make_aware(start, zone),
                                   occurred_at__lt=timezone.make_aware(end, zone))
            scope.append(f"mes {month}")
        if options["procedimiento"] is not None:
            try:
                procedure = Procedure.objects.get(number=options["procedimiento"])
            except Procedure.DoesNotExist:
                raise CommandError("No hay un procedimiento con ese número.") from None
            events = events.filter(detail__procedimiento=procedure.pk)
            scope.append(f"procedimiento {procedure.number}")
        return list(events.order_by("pk")), scope

    def _spend(self, events, scope, *, by_stage):
        total, counts, stages = Decimal(0), {}, {}
        flights = [e for e in events if e.detail.get("resultado") == IN_FLIGHT]
        events = [e for e in events if e.detail.get("resultado") != IN_FLIGHT]
        for event in events:
            detail = event.detail
            cost = Decimal(str(detail.get("costo_usd") or 0))
            result = detail.get("resultado") or "sin_resultado"
            total += cost
            counts[result] = counts.get(result, 0) + 1
            stage = stages.setdefault(detail.get("etapa") or "sin_etapa",
                                      {"pedidos": 0, "gasto": Decimal(0), "resultados": {}})
            stage["pedidos"] += 1
            stage["gasto"] += cost
            stage["resultados"][result] = stage["resultados"].get(result, 0) + 1
        self.stdout.write(f"Gasto externo ({', '.join(scope)})")
        self.stdout.write(f"Pedidos registrados: {len(events)} ("
                          + ", ".join(f"{name} {counts.get(name, 0)}" for name in RESULTS)
                          + ")")
        self.stdout.write(f"Gasto real: {_usd(total)}")
        # Un lote en vuelo es un hecho por lote, no un pedido (O-290-6): sin cerrar, su proceso no
        # registró todavía los pedidos (o murió esperando) y se informa con su estimado.
        closed = _closed_batches()
        open_ = [e for e in flights if e.detail.get("lote_id") not in closed]
        estimated = sum((Decimal(str(e.detail.get("costo_usd") or 0)) for e in open_), Decimal(0))
        self.stdout.write(f"Lotes en vuelo sin cerrar: {len(open_)} (estimado {_usd(estimated)})")
        if by_stage:
            self.stdout.write("Por etapa:")
            for name in sorted(stages):
                stage = stages[name]
                detail = ", ".join(f"{k} {v}" for k, v in sorted(stage["resultados"].items()))
                self.stdout.write(f"  {name}: {stage['pedidos']} pedidos ({detail}), "
                                  f"{_usd(stage['gasto'])}")

    def _verify(self, events):
        sheet_windows, sheets, unread = _sheet_windows()
        events = [e for e in events if e.detail.get("resultado") != IN_FLIGHT]  # sin texto
        leaking = []
        for event in events:
            hits = _leaks(event.detail, sheet_windows)
            if hits:
                leaking.append((event.pk, len(hits)))
        self.stdout.write(f"Verificación del filtro: {len(events)} pedidos revisados contra "
                          f"{sheets} hojas de compliance ({unread} sin lectura), secuencias de "
                          f"{WINDOW} palabras.")
        if unread:
            self.stdout.write(f"Aviso: {unread} hojas de compliance sin lectura no se pudieron "
                              "comparar.")
        self.stdout.write(f"Pedidos con texto de una hoja de compliance: {len(leaking)} "
                          "(criterio de REQ-121: 0)")
        for pk, count in leaking:
            self.stdout.write(f"  hecho {pk}: {count} secuencias de una hoja")
        if leaking:
            raise CommandError(f"{len(leaking)} pedidos externos contienen texto de una hoja de "
                               "compliance (REQ-121 exige 0).")
