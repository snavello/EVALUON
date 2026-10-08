"""Tema s5_rigen: normas que rigen al procedimiento y cuáles faltan cargar (REQ-095, REQ-097; plan
014, T-215), en la sección «normativas».

Según la fecha de autorización, `applicable_regimes` (de la 001, sin tocarla) dice qué régimen
rige. Junto a él se listan el marco nacional, las modificatorias registradas sin cargar y las
normas que cita el pliego en su encuadre legal. Cada norma lleva por qué rige, su estado, de dónde
vino y su acción; la que falta cargar lleva «Subir archivo» (el ancla de subida es la de T-214).
Si el sistema no tiene cargada ninguna norma del régimen aplicable a la fecha, la norma que la
fecha fija sale de la regla del ADR-0006 (Disp. 247/2022 desde el 2 de enero de 2023; antes, la
297/03). Solo lee; no decide nada (P3). Las fechas se muestran en hora local.
"""

import re
from dataclasses import dataclass
from datetime import date

from django.urls import reverse
from django.utils import timezone

from evaluon.journey.sections.base import Missing, TemaStatus
from evaluon.norms.models import BODY_PART, Category, Norm, PendingAmendment, ReadingStatus
from evaluon.portal.models import PortalProcedureData
from evaluon.queries.services import applicable_regimes

KEY = "s5_rigen"
SECTION = "normativas"
PARTIAL = "journey/temas/s5_rigen.html"
urlpatterns = []

# Primer día bajo la Disp. 247/2022 (ADR-0006, corrección del 2026-10-03).
NEW_REGIME_FROM = date(2023, 1, 2)
# (número, año, nombre) de las normas que el sistema espera tener cargadas.
NEW_REGIME = ("247", 2022, "Disp. AFIP 247/2022")
OLD_REGIME = ("297", 2003, "Disp. AFIP 297/03")
NATIONAL_FRAMEWORK = (("1023", 2001, "Decreto 1023/2001"), ("1030", 2016, "Decreto 1030/2016"))

LOADED, UNVALIDATED, MISSING, NOT_APPLICABLE = "validada", "sin_validar", "falta", "no_aplica"
STATES = {
    LOADED: ("cumple", "Validada"),
    UNVALIDATED: ("nodet", "Cargada, sin validar"),
    MISSING: ("nocumple", "Falta cargar"),
}

# «Decreto 1023/2001», «Decreto Delegado N° 1023/01», «Disp. AFIP N° 247/22», «Disposición N° 247/2022
# (AFIP)», «Resolución General N° 4000/2017», «Ley N° 24.156» (la ley puede ir sin año).
_CITED = re.compile(
    r"\b(Ley|Decreto(?:\s+Delegado|\s+de\s+Necesidad\s+y\s+Urgencia)?|Disposici[oó]n|Disp\.|"
    r"Resoluci[oó]n(?:\s+General|\s+Conjunta)?|Res\.(?:\s+Gral\.)?)"
    r"(?:\s+(?:AFIP|ARCA))?(?:\s+(?:N\.?\s?[º°o]\.?|n[º°]|Nro\.?))?"
    r"\s*(\d[\d.]*\d|\d)(?:\s*/\s*(\d{2,4}))?(?!\d)", re.I)
KINDS = (("ley", "Ley", "ley"), ("decreto", "Decreto", "decreto"),
         ("disp", "Disposición", "disposicion"), ("resol", "Resolución", "resolucion"),
         ("res.", "Resolución", "resolucion"))
TYPE_NAMES = {"ley": "Ley", "decreto": "Decreto", "disposicion": "Disposición",
              "resolucion": "Resolución", "decision": "Decisión"}


@dataclass(frozen=True)
class Row:
    name: str
    why: str
    state: str
    source: str = ""
    version: str = ""
    original_url: str = ""
    validate_url: str = ""
    upload_url: str = ""


def upload_url(procedure):
    """El ancla de subida de normas (T-214), dentro de la pestaña."""
    return reverse("expedientes:normativas", args=[procedure.pk]) + "#s5-subir"


def _day(value):
    return f"{timezone.localtime(value):%d/%m/%Y}"


def _plain_number(value):
    return value.replace(".", "").lstrip("0")


def _full_year(value):
    year = int(value)
    if year < 100:
        year += 2000 if year <= 30 else 1900
    return year


def _find(number, year, norm_type=None):
    """La norma cargada con ese número y año, si hay (el organismo no se exige). Sin año (solo
    las leyes), se busca por tipo y número."""
    norms = Norm.objects.filter(number=number)
    if year is not None:
        norms = norms.filter(year=year)
    elif norm_type:
        norms = norms.filter(norm_type=norm_type)
    return norms.order_by("pk").first()


def _type_name(norm_type):
    return TYPE_NAMES.get(norm_type.lower(), norm_type.capitalize())


def _norm_info(norm):
    """Estado, origen y versión de una norma cargada, desde sus documentos en uso y su última
    lectura. Sin documento en uso o con alguna lectura sin validar, queda sin validar."""
    documents = list(norm.documents.filter(in_use=True).order_by("part", "pk"))
    state, validated_at, loaded_at, url, pending_reading = LOADED, None, None, "", None
    for document in documents:
        reading = (document.readings.exclude(status=ReadingStatus.SUPERSEDED)
                   .order_by("-sequence").first())
        if reading is None or reading.status != ReadingStatus.VALIDATED:
            state = UNVALIDATED
            pending_reading = pending_reading or reading
        elif reading.validated_at and (validated_at is None or reading.validated_at > validated_at):
            validated_at = reading.validated_at
        if document.part == BODY_PART or not url:
            url = reverse("norms:original", args=[document.pk])
        if loaded_at is None or document.loaded_at > loaded_at:
            loaded_at = document.loaded_at
    if not documents:
        state = UNVALIDATED
    if state == LOADED and validated_at:
        source = f"Archivo · validada {_day(validated_at)}"
    elif loaded_at:
        source = f"Archivo · subido {_day(loaded_at)}"
    else:
        source = "Archivo"
    versions = sorted({d.version_number for d in documents if d.version_number})
    version = f"versión {versions[-1]}" if versions else ""
    validate = f"?lectura={pending_reading.pk}#s5-lectura" if pending_reading else ""
    return state, source, version, url, validate


def _row(norm, name, why, procedure=None):
    state, source, version, url, validate = _norm_info(norm)
    if validate and procedure is not None:
        validate = reverse("expedientes:normativas", args=[procedure.pk]) + validate
    return Row(name=name or norm.citation, why=why, state=state, source=source,
               version=version, original_url=url, validate_url=validate)


def _missing_row(name, why, procedure):
    return Row(name=name, why=why, state=MISSING, upload_url=upload_url(procedure))


def _expected_regime(authorization_date):
    return NEW_REGIME if authorization_date >= NEW_REGIME_FROM else OLD_REGIME


def _regime_rows(procedure, shown, governs):
    """Las normas del régimen: el que rige a la fecha y, marcado, el que no aplica."""
    day = procedure.authorization_date
    when = f"{day:%d/%m/%Y}"
    applicable = {r["norm"]: r["name"] for r in applicable_regimes(day)}
    norms = {n.pk: n for n in Norm.objects.filter(pk__in=applicable)}
    rows = []
    if applicable:
        for pk in applicable:
            shown.add(pk)
            governs.add(pk)
            rows.append(_row(norms[pk], None, f"Autorizado el {when}, bajo su vigencia",
                             procedure))
        applies = {(n.number, n.year) for n in norms.values()}
    else:
        number, year, name = _expected_regime(day)
        why = (f"Autorizado el {when}, bajo su vigencia" if number == NEW_REGIME[0]
               else f"Autorizado el {when}, antes de la entrada en vigencia de la 247/2022")
        norm = _find(number, year)
        if norm is None:
            rows.append(_missing_row(name, why, procedure))
        else:
            shown.add(norm.pk)
            governs.add(norm.pk)
            rows.append(_row(norm, name, why, procedure))
        applies = {(number, year)}
    other = next((r for r in (NEW_REGIME, OLD_REGIME) if (r[0], r[1]) not in applies), None)
    if other is not None:
        norm = _find(other[0], other[1])
        if norm:
            shown.add(norm.pk)
        reason = ("No aplica: rige solo para autorizaciones anteriores a la 247/2022"
                  if other is OLD_REGIME else
                  "No aplica: rige solo para autorizaciones desde la 247/2022")
        rows.append(Row(name=norm.citation if norm else other[2], why=reason,
                        state=NOT_APPLICABLE))
    return rows


def _framework_rows(procedure, shown, governs, cited):
    """El marco nacional; si además lo cita el pliego, una sola fila que lo dice."""
    cited_ids = {(c.number, c.year) for c in cited}
    rows = []

    def why(number, year):
        if (number, year) in cited_ids:
            return "Marco nacional · citado por el pliego"
        return "Marco nacional de contrataciones"

    for number, year, name in NATIONAL_FRAMEWORK:
        norm = _find(number, year)
        if norm is None:
            rows.append(_missing_row(name, why(number, year), procedure))
        else:
            shown.add(norm.pk)
            governs.add(norm.pk)
            rows.append(_row(norm, name, why(number, year), procedure))
    for norm in Norm.objects.filter(category=Category.MARCO_NACIONAL).exclude(pk__in=shown):
        shown.add(norm.pk)
        governs.add(norm.pk)
        rows.append(_row(norm, None, why(norm.number, norm.year), procedure))
    return rows


def _amendment_rows(procedure, governs):
    """Las modificatorias registradas y sin cargar, solo de las normas que rigen."""
    entries = (PendingAmendment.objects.filter(loaded_norm__isnull=True, target_norm__in=governs)
               .select_related("target_norm").order_by("pk"))
    return [Row(name=f"{_type_name(e.norm_type)} {e.number}/{e.year} ({e.issuer.upper()})",
                why=f"Modifica a {e.target_norm.citation}", state=MISSING,
                source=f"Registrada {_day(e.registered_at)}", upload_url=upload_url(procedure))
            for e in entries]


@dataclass(frozen=True)
class Cited:
    kind: str       # «Decreto», «Ley»…
    norm_type: str  # el de `norms_norm`: «decreto», «ley»…
    number: str     # sin puntos ni ceros a la izquierda
    year: int | None
    text: str       # cómo se muestra: «Decreto 1023/2001»


def _cited(procedure):
    """Las normas que cita el encuadre legal del pliego. Solo lo que se reconoce: número y año
    (dos o cuatro cifras); sin año, solo las leyes."""
    data = PortalProcedureData.objects.filter(procedure=procedure).first()
    text = data.legal_framework if data else ""
    found, seen = [], set()
    for match in _CITED.finditer(text):
        raw = match.group(1).lower()
        kind, norm_type = next((k, t) for prefix, k, t in KINDS if raw.startswith(prefix))
        number = _plain_number(match.group(2))
        year = _full_year(match.group(3)) if match.group(3) else None
        if (year is None and norm_type != "ley") or not number:
            continue
        if (norm_type, number, year) in seen:
            continue
        seen.add((norm_type, number, year))
        shown_number = match.group(2) if year is None else number
        name = f"{kind} {shown_number}" + (f"/{year}" if year else "")
        found.append(Cited(kind, norm_type, number, year, name))
    return found


def _cited_rows(procedure, shown, cited):
    rows = []
    why = "La cita el pliego (encuadre legal)"
    for c in cited:
        norm = _find(c.number, c.year, c.norm_type)
        if norm is not None and norm.pk in shown:
            continue
        if norm is None:
            if any(n == c.number and y == c.year for n, y, _ in _EXPECTED):
                continue  # ya figura como faltante del régimen o del marco
            rows.append(_missing_row(c.text, why, procedure))
        else:
            shown.add(norm.pk)
            rows.append(_row(norm, None, why, procedure))
    return rows


_EXPECTED = (NEW_REGIME, OLD_REGIME) + NATIONAL_FRAMEWORK


def rows(procedure):
    shown, governs = set(), set()
    cited = _cited(procedure)
    result = _regime_rows(procedure, shown, governs)
    result += _framework_rows(procedure, shown, governs, cited)
    result += _amendment_rows(procedure, governs)
    result += _cited_rows(procedure, shown, cited)
    return result


def status(user, procedure):
    """Lo que falta cargar, con «Subir archivo». No suma pendientes: validar una lectura es de
    la carga de normas (T-214)."""
    url = upload_url(procedure)
    missing = tuple(Missing(f"Falta cargar {r.name}", url, "Subir archivo")
                    for r in rows(procedure) if r.state == MISSING)
    source = (f"Normas que rigen: calculadas desde la fecha de autorización, "
              f"{procedure.authorization_date:%d/%m/%Y}.")
    return TemaStatus(missing=missing, sources=(source,))


def context(user, procedure, request):
    listed = rows(procedure)
    return {
        "pid": procedure.pk,
        "date": f"{procedure.authorization_date:%d/%m/%Y}",
        "rows": [{"row": r, "icon": STATES.get(r.state, ("", ""))[0],
                  "state_name": STATES.get(r.state, ("", ""))[1]} for r in listed],
        "loaded": sum(1 for r in listed if r.state in (LOADED, UNVALIDATED)),
        "unvalidated": sum(1 for r in listed if r.state == UNVALIDATED),
        "missing": sum(1 for r in listed if r.state == MISSING),
        "upload_url": upload_url(procedure),
    }
