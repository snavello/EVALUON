"""Corrida del conjunto de preguntas y medida de las exigencias de la spec (P7; REQ-008,
REQ-009, REQ-020, REQ-021; plan 001, "Evals"). Versión de T-039.

`run(usuario, carpeta_de_casos, carpeta_de_corridas)`:

1. Comprueba el rol (lectura; el de lectura y escritura lo incluye).
2. Lee los casos: un archivo `EV-NNN.yaml` por pregunta (`load_cases`). Un caso mal
   formado, o sin `fecha_autorizacion`, se informa y no se corre; un caso sin
   `visto_bueno` (vacío, "pendiente" o "no") tampoco se corre. Los demás archivos de la
   carpeta se ignoran.
3. Corre cada caso con la misma función que la pantalla, `services.ask`, con el canal
   `eval` y la `fecha_autorizacion` del caso, una pregunta por vez. Nunca pasa una
   fecha vacía: la función de consulta usaría la del día. Cada consulta queda en el
   registro de auditoría como cualquier otra (P6). Un caso que la consulta rechaza (por
   ejemplo, una fecha posterior al día) no sale de la medida: cuenta como incorrecto o
   como no abstenido, y el resumen lo marca.
4. Mide cada caso (`grade`) y la corrida entera (`measure`):
   - cita literal: sobre todas las citas de todas las respuestas, `Unit.text` guardado y
     el texto que entrega `answering.citation_texts` para mostrar son iguales a
     `canonical_text[char_start:char_end]` de la lectura de la unidad, leído acá por
     separado. Umbral 100 %;
   - respuesta correcta que cita la unidad correcta, sobre las preguntas con respuesta:
     `grounded`, régimen aplicado igual a `regimen`, cita todas las `unidades` (si el
     caso nombra un inciso, vale el artículo que lo contiene), contiene los
     `datos_clave` y, con `difieren`, trae la marca `regimes_differ` en una afirmación
     que cita al régimen específico y al marco nacional. Al menos 85 %;
   - abstención, sobre las preguntas sin respuesta (`esperado: no determinado`): cuenta
     si el resultado es `undetermined`; una falla técnica no cuenta. Al menos 90 %;
   - tiempo de cada consulta: mediana y máximo. Máximo de 30 segundos.
   Aparte, y se espera cero fallas: los pares de REQ-020 (`check_pairs`) y el aviso de
   REQ-021 (`notice_ok`).
5. Guarda la corrida en `carpeta_de_corridas/<fecha>T<hora>_<commit>_<modelo>/`:
   `parametros.json`, `resultados.jsonl` (un renglón por caso, también los que no se
   corrieron) y `resumen.md`.

Los datos clave (`key_data_missing`, reglas del Coordinador en la verificación de T-039)
se buscan en el texto de las afirmaciones, normalizado igual que el dato: sin distinguir
mayúsculas, tildes ni espacios repetidos; un número en letras seguido de su cifra entre
paréntesis vale como la cifra; del uno al veinte en letras equivalen a su cifra; "5%" y
"5 %" son lo mismo. El dato tiene que aparecer sin una letra, un dígito o un separador
de número pegados. Un dato "sí" o "no" se cumple solo si la primera afirmación empieza
con esa palabra. En la corrida que se presenta para aprobar, el responsable revisa
además las respuestas contra la esperada (plan, "Evals").

Las medidas de recuperación, por régimen, la comparación con la corrida anterior, la
comparación quitando piezas y la calibración del umbral son de T-042.
"""

import json
import re
import statistics
import subprocess
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from evaluon.accounts.models import Role
from evaluon.accounts.permissions import require_role
from evaluon.audit.models import Channel
from evaluon.audit.services import current_corpus_version
from evaluon.norms.models import Category, Unit, UnitType
from evaluon.queries import answering, services
from evaluon.queries.models import Status

# Umbrales de las exigencias de la spec (plan 001, "Cómo se mide cada exigencia").
LITERAL_THRESHOLD = 1.0
CORRECT_THRESHOLD = 0.85
ABSTENTION_THRESHOLD = 0.90
MAX_SECONDS = 30.0

NO_ANSWER = "no determinado"
PENDING_AMENDMENTS = "pending_amendments"

# Por qué un caso no se corrió.
MALFORMED = "malformed"
NOT_APPROVED = "not_approved"
REFUSED = "refused"

# Valores de `visto_bueno` que no son visto bueno, ya normalizados.
NOT_AN_APPROVAL = {"", "pendiente", "no"}

CASE_GLOB = "EV-*.yaml"
NO_COMMIT = "sin-commit"

# Estados de un par de REQ-020.
PAIR_PASSES = "pasa"
PAIR_FAILS = "falla"
PAIR_INCOMPLETE = "incompleto"

REQUIRED_FIELDS = (
    "id", "pregunta", "esperado", "fecha_autorizacion", "regimen", "unidades",
    "datos_clave", "difieren", "pareja", "aviso_modificatorias", "etiquetas",
    "visto_bueno",
)


class CaseError(ValueError):
    """El caso está mal formado. El mensaje dice por qué, en lenguaje llano."""


@dataclass(frozen=True)
class Case:
    """Un caso del conjunto de preguntas, ya validado."""

    id: str
    file: str
    question: str
    reference_date: date
    regime: str
    has_answer: bool
    units: tuple  # pares (norma, key)
    key_data: tuple
    differ: bool
    pair: str
    notice: bool
    approval: str


@dataclass(frozen=True)
class Skipped:
    """Un caso que no se corrió: `kind` es `malformed`, `not_approved` o `refused`."""

    file: str
    case_id: str
    kind: str
    reason: str


# --- Lectura de los casos --------------------------------------------------------------


def _text(data, name, *, empty=True):
    value = data.get(name)
    if value is None and empty:
        return ""
    if not isinstance(value, str):
        raise CaseError(f"`{name}` tiene que ser un texto")
    if not empty and not value.strip():
        raise CaseError(f"`{name}` no puede estar vacío")
    return value.strip()


def _flag(data, name):
    value = data.get(name)
    if not isinstance(value, bool):
        raise CaseError(f"`{name}` tiene que ser verdadero o falso")
    return value


def _texts(data, name):
    value = data.get(name)
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise CaseError(f"`{name}` tiene que ser una lista de textos")
    return tuple(v.strip() for v in value)


def _reference_date(data):
    value = data.get("fecha_autorizacion")
    if value is None or value == "":
        raise CaseError("falta `fecha_autorizacion`, que no tiene valor por omisión")
    if isinstance(value, datetime):
        raise CaseError("`fecha_autorizacion` tiene que ser una fecha AAAA-MM-DD, sin hora")
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise CaseError("`fecha_autorizacion` tiene que ser una fecha AAAA-MM-DD") from None


def _units(data):
    value = data.get("unidades")
    if not isinstance(value, list):
        raise CaseError("`unidades` tiene que ser una lista")
    units = []
    for item in value:
        if (not isinstance(item, dict)
                or not isinstance(item.get("norma"), str) or not item["norma"].strip()
                or not isinstance(item.get("key"), str) or not item["key"].strip()):
            raise CaseError("cada unidad de `unidades` necesita `norma` y `key`")
        units.append((item["norma"].strip(), item["key"].strip()))
    return tuple(units)


def _approval(data):
    value = data.get("visto_bueno")
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, cls=DjangoJSONEncoder) if value else ""
    raise CaseError("`visto_bueno` tiene que ser un texto")


def parse_case(path):
    """Lee y valida un caso. Devuelve un `Case` o lanza `CaseError`."""
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as error:
        raise CaseError(f"no se puede leer como YAML ({error.__class__.__name__})") from None
    if not isinstance(data, dict):
        raise CaseError("no tiene la forma de un caso")
    missing = [name for name in REQUIRED_FIELDS
               if name not in data and name != "fecha_autorizacion"]
    if missing:
        raise CaseError("faltan los datos " + ", ".join(f"`{n}`" for n in missing))

    case_id = _text(data, "id", empty=False)
    if case_id != Path(path).stem:
        raise CaseError(f"`id` ({case_id}) no coincide con el nombre del archivo")
    reference_date = _reference_date(data)
    expected = _text(data, "esperado", empty=False)
    has_answer = expected.casefold() != NO_ANSWER
    regime = _text(data, "regimen")
    units = _units(data)
    differ = _flag(data, "difieren")
    pair = _text(data, "pareja")
    _texts(data, "etiquetas")

    if has_answer and not units:
        raise CaseError("una pregunta con respuesta necesita `unidades`")
    if has_answer and not regime:
        raise CaseError("una pregunta con respuesta necesita `regimen`")
    if not has_answer and units:
        raise CaseError("una pregunta sin respuesta no lleva `unidades`")
    if differ and not has_answer:
        raise CaseError("`difieren` solo va en una pregunta con respuesta")
    if pair == case_id:
        raise CaseError("`pareja` no puede ser el mismo caso")

    return Case(
        id=case_id,
        file=Path(path).name,
        question=_text(data, "pregunta", empty=False),
        reference_date=reference_date,
        regime=regime,
        has_answer=has_answer,
        units=units,
        key_data=_texts(data, "datos_clave"),
        differ=differ,
        pair=pair,
        notice=_flag(data, "aviso_modificatorias"),
        approval=_approval(data),
    )


def is_approved(approval):
    """Un visto bueno vacío, "pendiente" o "no" (sin distinguir mayúsculas ni tildes) no
    es visto bueno."""
    return normalize(approval or "") not in NOT_AN_APPROVAL


def load_cases(directory):
    """Lee los `EV-*.yaml` de `directory`, en orden de nombre. Devuelve `(casos, no
    corridos)`: los casos bien formados y con visto bueno, y un `Skipped` por cada uno de
    los demás."""
    cases, skipped = [], []
    for path in sorted(Path(directory).glob(CASE_GLOB)):
        try:
            case = parse_case(path)
        except CaseError as error:
            skipped.append(Skipped(path.name, path.stem, MALFORMED, f"mal formado: {error}"))
            continue
        if not is_approved(case.approval):
            skipped.append(Skipped(path.name, case.id, NOT_APPROVED,
                                   "sin visto bueno de la Comisión"))
            continue
        cases.append(case)
    return cases, skipped


# --- Medida de un caso -----------------------------------------------------------------


def normalize(text):
    """Texto sin tildes, sin distinguir mayúsculas y con los espacios repetidos
    reducidos a uno."""
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", plain.casefold()).strip()


# Palabras de un número escrito en letras, ya sin tildes ni mayúsculas.
_NUMBER_WORD = (
    r"(?:un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|"
    r"catorce|quince|dieci[a-z]+|veinte|veinti[a-z]+|treinta|cuarenta|cincuenta|"
    r"sesenta|setenta|ochenta|noventa|cien|ciento|[a-z]+cientos|quinientos|mil|"
    r"millon|millones)"
)
# "sesenta (60)", "treinta y cinco (35)", "cinco por ciento (5%)": queda la cifra.
_WORDS_WITH_FIGURE = re.compile(
    rf"\b{_NUMBER_WORD}(?:\s+(?:y\s+)?{_NUMBER_WORD})*(?:\s+por\s+ciento)?\s*"
    r"\(\s*(\d[\d.,]*(?:\s*%)?)\s*\)"
)
# Del uno al veinte, en letras, equivalen a su cifra.
_SMALL_NUMBERS = {
    "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
    "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17,
    "dieciocho": 18, "diecinueve": 19, "veinte": 20,
}
_SMALL_NUMBER_WORDS = re.compile(r"\b(" + "|".join(_SMALL_NUMBERS) + r")\b")

# Datos clave que se responden con la primera palabra de la respuesta.
_YES_NO = {"si", "no"}


def normalize_for_search(text):
    """Texto de la respuesta o del dato clave tal como se comparan (decisión del
    Coordinador, verificación de T-039): además de `normalize`, un número en letras
    seguido de su cifra entre paréntesis queda solo con la cifra ("sesenta (60) días"
    pasa a "60 días"), del uno al veinte en letras pasan a su cifra ("dos vocales" a "2
    vocales") y el signo de porcentaje va siempre separado por un espacio ("5%" a
    "5 %")."""
    text = normalize(text)
    text = _WORDS_WITH_FIGURE.sub(lambda m: m.group(1), text)
    text = _SMALL_NUMBER_WORDS.sub(lambda m: str(_SMALL_NUMBERS[m.group(1)]), text)
    text = re.sub(r"(\d)\s*%", r"\1 %", text)
    return re.sub(r"\s+", " ", text).strip()


def _contains(text, fragment):
    """`fragment` aparece en `text` sin una letra, un dígito o un separador de número
    pegados antes o después. Una coma o un punto cuentan como pegados solo si están
    junto a un dígito ("0,1 %", "21.000"); el que cierra una frase no."""
    if not fragment:
        return True
    pattern = (r"(?<!\w)(?<!\d[.,])" + re.escape(fragment) + r"(?!\w)(?![.,]\d)")
    return re.search(pattern, text) is not None


def _starts_with(text, word):
    """La afirmación empieza con `word`, salteando signos de puntuación y espacios
    iniciales."""
    index = 0
    while index < len(text) and (text[index].isspace()
                                 or unicodedata.category(text[index]).startswith("P")):
        index += 1
    return re.match(re.escape(word) + r"(?!\w)", text[index:]) is not None


def key_data_missing(key_data, statements):
    """Los datos clave que no están en las afirmaciones `statements` (textos, en orden).

    Un dato "sí" o "no" (regla del Coordinador) se cumple solo si la primera afirmación
    empieza con esa palabra. Los demás se buscan en todas las afirmaciones con
    `normalize_for_search` y límites de palabra y de número (`_contains`)."""
    first = normalize(statements[0]) if statements else ""
    text = normalize_for_search("\n".join(statements))
    missing = []
    for datum in key_data:
        plain = normalize(datum)
        if plain in _YES_NO:
            found = _starts_with(first, plain)
        else:
            found = _contains(text, normalize_for_search(datum))
        if not found:
            missing.append(datum)
    return missing


def _statement_citations(result):
    return [unit_id for s in result.get("statements") or [] for unit_id in s["citations"]]


def cited_units(result):
    """Cada unidad citada en el resultado, una vez y en orden de aparición, con su norma
    (nombre de cita), su clave, su tipo, su categoría y la comprobación de cita literal
    contra `canonical_text[char_start:char_end]` de su lectura, en dos partes:

    - `stored_text_ok`: `Unit.text` guardado es igual al recorte (datos que se apartan
      del original);
    - `shown_text_ok`: el texto que entrega `answering.citation_texts` para mostrar
      también lo es.

    `literal` es verdadero solo si se cumplen las dos."""
    ids = list(dict.fromkeys(_statement_citations(result)))
    units = Unit.objects.select_related("reading__document__norm").in_bulk(ids)
    try:
        shown = answering.citation_texts(result)
    except (KeyError, ValueError):
        shown = {}
    cited = []
    for unit_id in ids:
        unit = units.get(unit_id)
        if unit is None:
            cited.append({"unit": unit_id, "norm": None, "key": None, "unit_type": None,
                          "category": None, "stored_text_ok": False,
                          "shown_text_ok": False, "literal": False})
            continue
        norm = unit.reading.document.norm
        expected = unit.reading.canonical_text[unit.char_start:unit.char_end]
        stored_ok = unit.text == expected
        shown_ok = unit_id in shown and shown[unit_id] == expected
        cited.append({
            "unit": unit_id,
            "norm": norm.citation,
            "key": unit.key,
            "unit_type": unit.unit_type,
            "category": norm.category,
            "stored_text_ok": stored_ok,
            "shown_text_ok": shown_ok,
            "literal": stored_ok and shown_ok,
        })
    return cited


def _unit_matches(expected, unit):
    norm, key = expected
    if unit["norm"] != norm:
        return False
    if unit["key"] == key:
        return True
    # Si el caso nombra un inciso, vale el artículo que lo contiene.
    return unit["unit_type"] == UnitType.ARTICULO and key.startswith(unit["key"] + "/")


def _differ_ok(result, by_id):
    for statement in result.get("statements") or []:
        if statement.get("regimes_differ") is not True:
            continue
        categories = {by_id[u]["category"] for u in statement["citations"] if u in by_id}
        if {Category.REGIMEN_ESPECIFICO.value, Category.MARCO_NACIONAL.value} <= categories:
            return True
    return False


def notice_ok(expected, result):
    """Comprobación de REQ-021: el resultado trae algún aviso de modificatorias sin
    cargar exactamente cuando el caso lo pide."""
    has_notice = any(n.get("type") == PENDING_AMENDMENTS
                     for n in result.get("notices") or [])
    return has_notice == bool(expected)


def grade(case, result, cited):
    """Medidas de un caso a partir de su resultado guardado y de `cited_units(result)`."""
    by_id = {unit["unit"]: unit for unit in cited}
    citations = _statement_citations(result)
    literal = sum(1 for u in citations if by_id.get(u, {}).get("literal"))
    regime = [r["name"] for r in result.get("regime") or []]
    status = result.get("status")

    measures = {
        "citations": len(citations),
        "literal_citations": literal,
        "correct": None,
        "abstained": None,
        "notice_ok": notice_ok(case.notice, result),
        "checks": {},
        "missing_units": [],
        "missing_key_data": [],
    }
    if not case.has_answer:
        measures["abstained"] = status == Status.UNDETERMINED
        return measures

    missing_units = [u for u in case.units
                     if not any(_unit_matches(u, unit) for unit in cited)]
    missing_data = key_data_missing(
        case.key_data, [s["text"] for s in result.get("statements") or []])
    checks = {
        "status": status == Status.GROUNDED,
        "regime": regime == ([case.regime] if case.regime else []),
        "units": not missing_units,
        "key_data": not missing_data,
    }
    if case.differ:
        checks["regimes_differ"] = _differ_ok(result, by_id)
    measures.update(
        correct=all(checks.values()),
        checks=checks,
        missing_units=[{"norma": n, "key": k} for n, k in missing_units],
        missing_key_data=missing_data,
    )
    return measures


def _passed(line):
    measures = line["measures"]
    answered = measures["correct"] if line["has_answer"] else measures["abstained"]
    return bool(answered)


# --- Pares de REQ-020 ------------------------------------------------------------------


def check_pairs(lines):
    """Un par pasa si sus dos casos tienen la misma pregunta, cada uno pasa por su
    cuenta y las normas citadas son distintas. Si uno de los dos no se corrió, el par
    queda incompleto. `lines` son los renglones de los casos corridos."""
    by_id = {line["id"]: line for line in lines}
    pairs = []
    seen = set()
    for line in lines:
        if not line["pair"]:
            continue
        ids = tuple(sorted((line["id"], line["pair"])))
        if ids in seen:
            continue
        seen.add(ids)
        missing = [case_id for case_id in ids if case_id not in by_id]
        if missing:
            pairs.append({"cases": list(ids), "status": PAIR_INCOMPLETE,
                          "problems": [f"{case_id} no se corrió" for case_id in missing]})
            continue
        first, second = by_id[ids[0]], by_id[ids[1]]
        problems = []
        if first["pair"] != second["id"] or second["pair"] != first["id"]:
            problems.append("los dos casos no se nombran entre sí como pareja")
        if first["question"].strip() != second["question"].strip():
            problems.append("las preguntas no son iguales")
        problems.extend(f"{one['id']} no pasa por su cuenta"
                        for one in (first, second) if not one["passed"])
        norms = [{u["norm"] for u in one["cited_units"]} for one in (first, second)]
        if norms[0] == norms[1]:
            problems.append("los dos casos citan las mismas normas")
        pairs.append({"cases": list(ids),
                      "status": PAIR_FAILS if problems else PAIR_PASSES,
                      "problems": problems})
    return pairs


# --- Medidas de la corrida -------------------------------------------------------------


def _ratio(ok, total, threshold):
    rate = ok / total if total else None
    return {"ok": ok, "total": total, "rate": rate, "threshold": threshold,
            "meets": None if rate is None else rate >= threshold}


def measure(lines):
    """Las cuatro medidas exigidas sobre los renglones de los casos medidos: los
    corridos y los que la consulta rechazó, que cuentan como incorrectos o no abstenidos.
    El tiempo se mide solo sobre las consultas hechas."""
    answered = [line for line in lines if line["has_answer"]]
    unanswerable = [line for line in lines if not line["has_answer"]]
    times = [line["time_seconds"] for line in lines if line["time_seconds"] is not None]
    longest = max(times) if times else None
    return {
        "literal_citation": _ratio(
            sum(line["measures"]["literal_citations"] for line in lines),
            sum(line["measures"]["citations"] for line in lines),
            LITERAL_THRESHOLD),
        "correct_answer": _ratio(
            sum(1 for line in answered if line["measures"]["correct"]),
            len(answered), CORRECT_THRESHOLD),
        "abstention": _ratio(
            sum(1 for line in unanswerable if line["measures"]["abstained"]),
            len(unanswerable), ABSTENTION_THRESHOLD),
        "response_time": {
            "median": statistics.median(times) if times else None,
            "max": longest,
            "threshold": MAX_SECONDS,
            "meets": None if longest is None else longest <= MAX_SECONDS,
        },
    }


@dataclass
class RunReport:
    """Lo que dejó una corrida.

    - `folder`: la carpeta de la corrida.
    - `results`: un renglón por caso medido, como en `resultados.jsonl`: los corridos
      y los que la consulta rechazó (`status` `refused`, `ran` falso).
    - `skipped`: los casos que no se corrieron ni se miden (mal formados o sin visto
      bueno), con su motivo.
    - `measures`: las cuatro medidas exigidas (`measure`).
    - `pairs`: los pares de REQ-020 (`check_pairs`).
    - `notices`: la comprobación de REQ-021: `ok`, `total` y los casos `failed`.
    - `parameters`: lo que se guardó en `parametros.json`.
    """

    folder: Path
    results: list
    skipped: list
    measures: dict
    pairs: list
    notices: dict
    parameters: dict

    def failed_ids(self):
        """Casos medidos que fallaron alguna medida o comprobación, en orden."""
        return [line["id"] for line in self.results if _failures(line)]

    def ran(self):
        """Renglones de los casos que se corrieron de verdad."""
        return [line for line in self.results if line["ran"]]


def _failures(line):
    measures = line["measures"]
    reasons = []
    if line["status"] == REFUSED:
        reasons.append(f"consulta rechazada ({line['reason']}), cuenta como "
                       + ("incorrecta" if line["has_answer"] else "no abstenida"))
    elif line["has_answer"] and not measures["correct"]:
        failed = [name for name, ok in measures["checks"].items() if not ok]
        reasons.append("respuesta incorrecta (" + ", ".join(_CHECK_TEXT[n] for n in failed) + ")")
    elif not line["has_answer"] and not measures["abstained"]:
        reasons.append("no se abstuvo" if line["status"] != Status.ERROR
                       else "falla técnica en lugar de abstención")
    if measures["literal_citations"] != measures["citations"]:
        reasons.append("cita que no es literal")
    if not measures["notice_ok"]:
        reasons.append("aviso de modificatorias distinto del esperado")
    if line["time_seconds"] is not None and line["time_seconds"] > MAX_SECONDS:
        reasons.append("superó los 30 segundos")
    return reasons


_CHECK_TEXT = {
    "status": "no hubo respuesta con fundamento",
    "regime": "régimen aplicado distinto",
    "units": "no cita la unidad esperada",
    "key_data": "faltan datos clave",
    "regimes_differ": "sin la marca de regímenes que difieren con sus dos citas",
}


# --- Corrida ---------------------------------------------------------------------------


def detect_commit():
    """Commit del código, abreviado, si hay un repositorio de git a mano; si no,
    `sin-commit`. Dentro del contenedor no hay `.git`: conviene pasar `--commit`."""
    try:
        done = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=settings.BASE_DIR, capture_output=True, text=True,
                              timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return NO_COMMIT
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else NO_COMMIT


def _slug(text):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(text)).strip("-") or "x"


def run_folder_name(started_at, commit, model):
    """`AAAA-MM-DDTHHMMSS_<commit>_<modelo>`, con la hora de Buenos Aires."""
    local = timezone.localtime(started_at)
    return f"{local:%Y-%m-%dT%H%M%S}_{_slug(commit)}_{_slug(model)}"


def run_parameters(started_at, commit, cases_dir):
    """Lo que se guarda en `parametros.json` al empezar la corrida (plan, "Dónde se
    guarda")."""
    return {
        "started_at": timezone.localtime(started_at).isoformat(),
        "commit": commit,
        "cases_dir": str(cases_dir),
        "corpus_version": current_corpus_version(),
        "prompt_version": None,  # se completa con las de las consultas
        "search": services.parameters(),
    }


def prompt_versions(lines):
    """Versiones de las instrucciones que usaron las consultas, en orden de aparición:
    la única si fue una sola, la lista si hubo varias, o `None` si ninguna consulta
    llamó al modelo."""
    versions = list(dict.fromkeys(line["prompt_version"] for line in lines
                                  if line.get("prompt_version")))
    if not versions:
        return None
    return versions[0] if len(versions) == 1 else versions


def _refused_result(error):
    return {"status": REFUSED, "reason": str(error), "regime": [], "notices": [],
            "statements": [], "units": {}}


def _case_line(case, result, query=None, elapsed=None):
    """Renglón de un caso medido. Sin `query`, la consulta se rechazó."""
    cited = cited_units(result)
    line = {
        "id": case.id,
        "file": case.file,
        "ran": query is not None,
        "question": case.question,
        "reference_date": case.reference_date.isoformat(),
        "expected_regime": case.regime,
        "has_answer": case.has_answer,
        "pair": case.pair,
        "expected_notice": case.notice,
        "query_id": query.pk if query else None,
        "corpus_version": query.corpus_version if query else None,
        "prompt_version": query.prompt_version if query else "",
        "status": result["status"],
        "reason": result["reason"],
        "regime": [r["name"] for r in result.get("regime") or []],
        "notices": result.get("notices") or [],
        "statements": result.get("statements") or [],
        "cited_units": cited,
        "measures": grade(case, result, cited),
        "time_seconds": round(elapsed, 3) if query else None,
        "timings": query.timings if query else {},
    }
    line["passed"] = _passed(line)
    return line


def _skipped_line(skipped):
    return {"id": skipped.case_id, "file": skipped.file, "ran": False,
            "skipped": skipped.kind, "reason": skipped.reason}


def run(user, cases_dir, runs_dir, *, commit=None, clock=time.monotonic):
    """Corre los casos de `cases_dir` y guarda la corrida en una carpeta nueva dentro de
    `runs_dir`. Ver el módulo. Lanza `RoleRejected` sin rol, antes de leer nada; el
    rechazo queda registrado con el canal `eval` y esta función como operación (T-038).

    - `commit`: el commit del código; si no se indica, `detect_commit()`.
    - `clock`: reloj en segundos para medir cada consulta (las pruebas lo reemplazan).
    """
    require_role(user, Role.READ, channel=Channel.EVAL)
    cases_dir = Path(cases_dir)
    if not cases_dir.is_dir():
        raise FileNotFoundError(f"No existe la carpeta de casos {cases_dir}.")
    cases, skipped = load_cases(cases_dir)
    started_at = timezone.now()
    commit = commit or detect_commit()
    parameters = run_parameters(started_at, commit, cases_dir)

    lines = []
    for case in cases:
        since = clock()
        try:
            query = services.ask(user, case.question, case.reference_date,
                                 channel=Channel.EVAL)
        except services.QueryRefused as error:
            clock()
            lines.append(_case_line(case, _refused_result(error)))
            continue
        elapsed = clock() - since
        lines.append(_case_line(case, query.result, query, elapsed))

    parameters["prompt_version"] = prompt_versions(lines)
    parameters["finished_at"] = timezone.localtime(timezone.now()).isoformat()
    notice_lines = [line for line in lines if not line["measures"]["notice_ok"]]
    report = RunReport(
        folder=Path(runs_dir) / run_folder_name(started_at, commit, settings.GENERATION_MODEL),
        results=lines,
        skipped=skipped,
        measures=measure(lines),
        pairs=check_pairs(lines),
        notices={"ok": len(lines) - len(notice_lines), "total": len(lines),
                 "failed": [line["id"] for line in notice_lines]},
        parameters=parameters,
    )
    _write(report)
    return report


# --- Archivos de la corrida ------------------------------------------------------------


def _dumps(value, **kwargs):
    return json.dumps(value, ensure_ascii=False, cls=DjangoJSONEncoder, **kwargs)


def _write(report):
    report.folder.mkdir(parents=True, exist_ok=False)
    (report.folder / "parametros.json").write_text(
        _dumps(report.parameters, indent=2) + "\n", encoding="utf-8")
    rows = report.results + [_skipped_line(s) for s in report.skipped]
    rows.sort(key=lambda row: row["file"])
    (report.folder / "resultados.jsonl").write_text(
        "".join(_dumps(row) + "\n" for row in rows), encoding="utf-8")
    (report.folder / "resumen.md").write_text(summary_markdown(report), encoding="utf-8")


def _percent(value):
    return "—" if value is None else f"{value * 100:.1f} %".replace(".", ",")


def _seconds(value):
    return "—" if value is None else f"{value:.2f} s".replace(".", ",")


def _meets(value):
    return {True: "sí", False: "no", None: "sin casos"}[value]


def counts(report):
    """Cantidades de casos leídos, corridos, rechazados por la consulta (se miden igual)
    y no corridos por motivo."""
    by_kind = {kind: sum(1 for s in report.skipped if s.kind == kind)
               for kind in (NOT_APPROVED, MALFORMED)}
    ran = len(report.ran())
    refused = len(report.results) - ran
    return {"read": len(report.results) + len(report.skipped), "ran": ran,
            REFUSED: refused, **by_kind}


def counts_line(report):
    """Una línea en lenguaje llano con las cantidades de casos."""
    c = counts(report)
    line = (f"Casos leídos: {c['read']} · corridos: {c['ran']} · "
            f"{c[NOT_APPROVED]} sin visto bueno · {c[MALFORMED]} mal formados")
    if c[REFUSED]:
        line += (f" · {c[REFUSED]} rechazados por la consulta (cuentan como "
                 "incorrectos o no abstenidos)")
    return line


NOTHING_RAN = ("No se corrió ningún caso: ninguno está bien formado y con visto bueno "
               "de la Comisión. Las medidas quedan sin valor.")


def measure_rows(measures):
    """Renglones de la tabla de medidas exigidas: exigencia, resultado, umbral, cumple."""
    literal = measures["literal_citation"]
    correct = measures["correct_answer"]
    abstention = measures["abstention"]
    timing = measures["response_time"]
    return [
        ("Cita literal", f"{_percent(literal['rate'])} ({literal['ok']} de {literal['total']} citas)",
         "100 %", _meets(literal["meets"])),
        ("Respuesta correcta que cita la unidad correcta",
         f"{_percent(correct['rate'])} ({correct['ok']} de {correct['total']} preguntas con respuesta)",
         "al menos 85 %", _meets(correct["meets"])),
        ("Abstención",
         f"{_percent(abstention['rate'])} ({abstention['ok']} de {abstention['total']} preguntas sin respuesta)",
         "al menos 90 %", _meets(abstention["meets"])),
        ("Tiempo de respuesta",
         f"mediana {_seconds(timing['median'])} · máximo {_seconds(timing['max'])}",
         "máximo de 30 s", _meets(timing["meets"])),
    ]


def summary_markdown(report):
    """Contenido de `resumen.md`."""
    p = report.parameters
    search = p["search"]
    versions = p["prompt_version"]
    if versions is None:
        versions = "ninguna (ninguna consulta llamó al modelo)"
    elif isinstance(versions, list):
        versions = "varias: " + ", ".join(versions)
    out = [
        f"# Corrida {report.folder.name}",
        "",
        f"- Comienzo: {p['started_at']} · fin: {p['finished_at']}",
        f"- Commit: {p['commit']}",
        f"- Modelo de generación: {search['generation']['model']} "
        f"(compilación {search['generation']['engine_build']})",
        f"- Versión de las instrucciones: {versions}",
        f"- Versión de la normativa: {p['corpus_version'] if p['corpus_version'] is not None else 'ninguna'}",
        f"- Umbral del reranker: {search['rerank_threshold']}",
        f"- {counts_line(report)}",
        "",
    ]
    if not report.results:
        out += [f"**{NOTHING_RAN}**", ""]

    out += ["## Medidas exigidas", "",
            "| Exigencia | Resultado | Umbral | Cumple |", "|---|---|---|---|"]
    out += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in measure_rows(report.measures)]
    out += ["", "Una falla técnica no cuenta como abstención. El responsable revisa además "
            "las respuestas contra la esperada.", ""]

    out += ["## Pares de REQ-020", ""]
    if report.pairs:
        out += ["| Par | Resultado | Detalle |", "|---|---|---|"]
        out += [f"| {' y '.join(pair['cases'])} | {pair['status']} | "
                f"{'; '.join(pair['problems']) or '—'} |" for pair in report.pairs]
    else:
        out.append("Ningún par entre los casos corridos.")
    out.append("")

    notices = report.notices
    out += ["## Aviso de REQ-021", "",
            f"{notices['ok']} de {notices['total']} casos traen o no traen el aviso de "
            "modificatorias sin cargar según lo esperado.", ""]
    if notices["failed"]:
        out += ["Fallan: " + ", ".join(notices["failed"]) + ".", ""]

    out += ["## Casos fallados", ""]
    failed = [(line["id"], _failures(line)) for line in report.results if _failures(line)]
    if failed:
        out += [f"- {case_id}: {'; '.join(reasons)}." for case_id, reasons in failed]
    else:
        out.append("Ninguno.")
    out.append("")

    out += ["## Casos no corridos", ""]
    if report.skipped:
        out += [f"- {s.file}: {s.reason}." for s in report.skipped]
    else:
        out.append("Ninguno.")
    out.append("")
    return "\n".join(out)
