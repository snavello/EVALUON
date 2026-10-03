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
5. Diagnóstico (T-042; plan, "Evals", y ADR-0003, "Cómo se mide"), que no son
   exigencias de la spec:
   - recuperación de cada caso (`case_diagnostics`), leída del registro de su consulta:
     unidad correcta entre los candidatos, por camino y en la unión; entre las
     enviadas al modelo; su posición en el orden del reranker; puntaje más alto; si el
     umbral la frenó; tiempo de la recuperación. Y de la corrida
     (`retrieval_measures`), con las preguntas con y sin respuesta frenadas por el
     umbral;
   - salidas con falla de formato (`invalid_output`) o de cita (`invalid_citation`),
     contadas por el `type` de las anomalías: una falla de servicio no cuenta;
   - los casos de REQ-018 (etiqueta "dos categorías") y de REQ-019 (`difieren`), aparte;
   - respuesta correcta y abstención por régimen (`regimen` del caso);
   - calibración del umbral (`calibrate`), con el puntaje más alto de cada pregunta;
   - comparación con la corrida anterior de la misma carpeta, con la igualdad al
     repetir (`compare_runs`);
   - a pedido (`ablation=True`), la comparación quitando piezas (`run_ablation`).
6. Guarda la corrida en `carpeta_de_corridas/<fecha>T<hora>_<commit>_<modelo>/`:
   `parametros.json`, `resultados.jsonl` (un renglón por caso, también los que no se
   corrieron) y `resumen.md`.

Los datos clave (`key_data_missing`, reglas del Coordinador en la verificación de T-039)
se buscan en el texto de las afirmaciones, normalizado igual que el dato: sin distinguir
mayúsculas, tildes ni espacios repetidos; un número en letras seguido de su cifra entre
paréntesis vale como la cifra; del uno al veinte en letras equivalen a su cifra; "5%",
"5 %" y "5 por ciento" son lo mismo. El dato tiene que aparecer sin una letra, un dígito
o un separador de número pegados. Un dato "sí" o "no" se cumple solo si la primera
afirmación empieza con esa palabra seguida de un signo de puntuación o del final ("No
obstante, …" no es un "no"). En la corrida que se presenta para aprobar, el responsable
revisa además las respuestas contra la esperada (plan, "Evals").

Calibración (plan, "Abstención", pasos 1 y 2). Con las preguntas con respuesta que
llegaron a puntuarse, `n`, se admite frenar por error `k = piso(5 % de n)`; el umbral
propuesto es el puntaje más alto que deja pasar a todas salvo a lo sumo `k`: el
`k+1`-ésimo puntaje más bajo, redondeado hacia abajo a tres decimales (la selección pasa
con puntaje igual o mayor). Dejando cada vez una pregunta afuera, se calcula el umbral
con las demás y se mira si frena a la que quedó afuera: la proporción de frenadas es la
estimación de lo que frenaría con preguntas nuevas. El valor es uno solo para los dos
regímenes, se informa como provisorio y no cambia `settings.py`: lo fija T-045.

Comparación quitando piezas (ADR-0003). Cada caso se corre con cuatro configuraciones
de `retrieval.retrieve(..., paths=, rerank=)` seguido de `retrieval.select_units`, sin
pasar por la consulta ni por el modelo de generación: solo vectores (camino por
significado, con reranker), solo palabras (camino por palabras, con reranker), combinada
sin reranker (los tres caminos, sin umbral) y completa. Para una fecha sin régimen
cargado no se busca, igual que en la consulta. Estas recuperaciones no crean consultas
ni hechos del registro de auditoría: lo que recuperó cada configuración queda en
`resultados.jsonl` de la corrida.
"""

import json
import math
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
from evaluon.ai import AIServiceError, generation
from evaluon.audit.models import Channel
from evaluon.audit.services import current_corpus_version
from evaluon.norms.models import Category, Unit, UnitType
from evaluon.queries import answering, retrieval, services
from evaluon.queries.models import Reason, Status

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

# Calibración: proporción de preguntas con respuesta que el umbral puede frenar por
# error (plan, "Abstención", paso 2) y decimales del umbral propuesto.
CALIBRATION_MAX_BLOCKED = 0.05
CALIBRATION_DECIMALS = 3

# Etiqueta de los casos de REQ-018 (plan, "Evals", `etiquetas`), ya normalizada.
TWO_CATEGORIES = "dos categorias"

# Lo que se mide de la recuperación: los caminos y la unión.
UNION = "union"

# Tipos de anomalía que son salidas con falla de formato o de cita (aviso de T-019).
FORMAT_FAILURE = Reason.INVALID_OUTPUT.value
CITATION_FAILURE = Reason.INVALID_CITATION.value

# Comparación quitando piezas (ADR-0003): nombre, caminos y reranker.
ABLATION_CONFIGS = (
    ("solo vectores", (retrieval.SEMANTIC,), True),
    ("solo palabras", (retrieval.WORDS,), True),
    ("combinada sin reranker", retrieval.ALL_PATHS, False),
    ("completa", retrieval.ALL_PATHS, True),
)

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
    labels: tuple = ()


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
    labels = _texts(data, "etiquetas")

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
        labels=labels,
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
    vocales"), "por ciento" después de una cifra es el signo de porcentaje ("uno por
    ciento" y "1 por ciento" pasan a "1 %", aviso de T-039) y el signo va siempre
    separado por un espacio ("5%" a "5 %")."""
    text = normalize(text)
    text = _WORDS_WITH_FIGURE.sub(lambda m: m.group(1), text)
    text = _SMALL_NUMBER_WORDS.sub(lambda m: str(_SMALL_NUMBERS[m.group(1)]), text)
    text = re.sub(r"(\d)\s+por\s+ciento\b", r"\1 %", text)
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


def _is_punctuation(char):
    return unicodedata.category(char).startswith("P")


def _starts_with(text, word):
    """La afirmación empieza con `word`, salteando signos de puntuación y espacios
    iniciales, y a la palabra le sigue un signo de puntuación o el final (aviso de
    T-039): "No, …", "¡Sí!" y "«No»" cuentan; "No obstante, …" y "No hace falta" no."""
    index = 0
    while index < len(text) and (text[index].isspace() or _is_punctuation(text[index])):
        index += 1
    rest = text[index:]
    if not rest.startswith(word):
        return False
    after = rest[len(word):]
    return not after or _is_punctuation(after[0])


def key_data_missing(key_data, statements):
    """Los datos clave que no están en las afirmaciones `statements` (textos, en orden).

    Un dato "sí" o "no" (regla del Coordinador) se cumple solo si la primera afirmación
    empieza con esa palabra seguida de un signo de puntuación o del final. Los demás se buscan en todas las afirmaciones con
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


# --- Diagnóstico de la recuperación (T-042; ADR-0003, "Cómo se mide") --------------------


def _unit_info(ids):
    """`{id: {"norm", "key", "unit_type"}}` de las unidades `ids`, para compararlas con
    las `unidades` de un caso como en la respuesta correcta (`_unit_matches`)."""
    units = Unit.objects.select_related("reading__document__norm").in_bulk(set(ids))
    return {pk: {"norm": unit.reading.document.norm.citation, "key": unit.key,
                 "unit_type": unit.unit_type} for pk, unit in units.items()}


def _all_found(expected, ids, info):
    return all(any(_unit_matches(unit, info[pk]) for pk in ids if pk in info)
               for unit in expected)


def _worst_position(expected, ranked, info):
    positions = []
    for unit in expected:
        position = next((i for i, pk in enumerate(ranked, start=1)
                         if pk in info and _unit_matches(unit, info[pk])), None)
        if position is None:
            return None
        positions.append(position)
    return max(positions) if positions else None


def unit_hits(expected, candidates, sent, ranked, paths):
    """Dónde quedaron las unidades esperadas `expected` (pares norma y clave) de un caso:

    - `found`: por cada camino de `paths` y en la unión (`union`), si todas estaban entre
      los candidatos que entraron por ahí. Los candidatos son pasajes de unidades base:
      un inciso esperado vale con el artículo que lo contiene, como en la respuesta
      correcta.
    - `selected`: si todas estaban entre las unidades enviadas al modelo (`sent`).
    - `position`: la posición, desde 1, de la peor ubicada en `ranked` (el orden del
      reranker; sin reranker, el de la unión), o `None` si alguna no estaba.

    `candidates` son `{"unit", "path"}`, como los registra la consulta."""
    info = _unit_info([c["unit"] for c in candidates] + list(sent) + list(ranked))
    found = {path: _all_found(expected, [c["unit"] for c in candidates if path in c["path"]],
                              info)
             for path in paths}
    found[UNION] = _all_found(expected, [c["unit"] for c in candidates], info)
    return {"found": found, "selected": _all_found(expected, sent, info),
            "position": _worst_position(expected, ranked, info)}


def _anomalies_of(anomalies, kind):
    """Cuántas anomalías son del tipo `kind`. `anomalies` mezcla fallas de formato o de
    cita con las de los servicios (`service_error`): se filtra por `type` (aviso de
    T-019)."""
    return sum(1 for a in anomalies or [] if isinstance(a, dict) and a.get("type") == kind)


def case_diagnostics(case, query):
    """Diagnóstico de un caso corrido, leído del registro de su consulta (P6): puntaje
    más alto, motivo de la abstención, si la frenó el umbral, tiempo de la recuperación,
    fallas de formato y de cita y, si el caso tiene respuesta, `unit_hits`."""
    selected = query.selected or {}
    reason = (selected.get("abstention") or {}).get("reason")
    diagnostics = {
        "max_score": query.max_score,
        "abstention_reason": reason,
        "stopped_by_threshold": reason == Reason.BELOW_THRESHOLD.value,
        "retrieval_seconds": (query.timings or {}).get("retrieval"),
        "format_failures": _anomalies_of(query.anomalies, FORMAT_FAILURE),
        "citation_failures": _anomalies_of(query.anomalies, CITATION_FAILURE),
        "found": None,
        "selected": None,
        "position": None,
    }
    if case.has_answer:
        paths = (query.parameters or {}).get("paths") or list(retrieval.ALL_PATHS)
        ranked = [u["unit"] for u in (selected.get("retrieval") or {}).get("units") or []]
        sent = [u["unit"] for u in selected.get("sent") or []]
        diagnostics.update(unit_hits(case.units, query.candidates or [], sent, ranked,
                                     paths))
    return diagnostics


def _count(values):
    values = [v for v in values if v is not None]
    ok = sum(1 for v in values if v)
    return {"ok": ok, "total": len(values), "rate": ok / len(values) if values else None}


def _spread(values):
    values = [v for v in values if v is not None]
    return {"median": statistics.median(values) if values else None,
            "max": max(values) if values else None}


def retrieval_measures(items, paths=retrieval.ALL_PATHS, thresholded=True):
    """Medidas de recuperación de la corrida (ADR-0003). `items` son `(id, con
    respuesta, diagnóstico)`; un diagnóstico vacío (caso no corrido o no buscado) no
    cuenta. Con `thresholded` falso (sin reranker) no hay frenadas por el umbral."""
    items = [(case_id, has_answer, d) for case_id, has_answer, d in items if d]
    answered = [(case_id, d) for case_id, has_answer, d in items if has_answer]
    unanswered = [d for _, has_answer, d in items if not has_answer]
    return {
        "found": {key: _count(d["found"].get(key) for _, d in answered)
                  for key in [*paths, UNION]},
        "selected": _count(d["selected"] for _, d in answered),
        "not_selected": [case_id for case_id, d in answered if not d["selected"]],
        "position": _spread(d["position"] for _, d in answered),
        "answered_stopped": (_count(d["stopped_by_threshold"] for _, d in answered)
                             if thresholded else None),
        "answered_stopped_ids": ([case_id for case_id, d in answered
                                  if d["stopped_by_threshold"]] if thresholded else []),
        "unanswered_stopped": (_count(d["stopped_by_threshold"] for d in unanswered)
                               if thresholded else None),
        "retrieval_time": _spread(d["retrieval_seconds"] for _, _, d in items),
    }


def measures_by_regime(lines):
    """Respuesta correcta y abstención separadas por el régimen del caso (`regimen`),
    como diagnóstico (plan, "Evals"). La clave vacía es la de los casos sin régimen."""
    groups = {}
    for line in lines:
        groups.setdefault(line["expected_regime"], []).append(line)
    measures = {}
    for regime in sorted(groups, key=lambda name: (name == "", name)):
        group = groups[regime]
        answered = [line for line in group if line["has_answer"]]
        unanswerable = [line for line in group if not line["has_answer"]]
        measures[regime] = {
            "correct_answer": _ratio(sum(1 for line in answered
                                         if line["measures"]["correct"]),
                                     len(answered), CORRECT_THRESHOLD),
            "abstention": _ratio(sum(1 for line in unanswerable
                                     if line["measures"]["abstained"]),
                                 len(unanswerable), ABSTENTION_THRESHOLD),
        }
    return measures


def output_failures(lines):
    """Casos cuya salida tuvo una falla de formato o de cita (ADR-0002). Se espera
    ninguno."""
    with_diagnostics = [line for line in lines if line.get("diagnostics")]
    return {
        "format": [line["id"] for line in with_diagnostics
                   if line["diagnostics"]["format_failures"]],
        "citation": [line["id"] for line in with_diagnostics
                     if line["diagnostics"]["citation_failures"]],
    }


def special_cases(lines):
    """Los casos de REQ-018 (etiqueta "dos categorías") y de REQ-019 (`difieren`), con
    si pasan, para informarlos aparte."""
    return {
        "REQ-018": [{"id": line["id"], "passed": line["passed"]} for line in lines
                    if TWO_CATEGORIES in {normalize(label) for label in line["labels"]}],
        "REQ-019": [{"id": line["id"], "passed": line["passed"]} for line in lines
                    if line["differ"]],
    }


# --- Calibración del umbral (plan, "Abstención") ----------------------------------------


def _floor(value):
    factor = 10 ** CALIBRATION_DECIMALS
    return math.floor(round(value * factor, 6)) / factor


def highest_threshold(scores, max_rate=CALIBRATION_MAX_BLOCKED):
    """El umbral más alto que frena (puntaje menor que el umbral) a lo sumo
    `piso(max_rate × n)` de los `n` puntajes: el `k+1`-ésimo más bajo, sin redondear.
    `None` sin puntajes."""
    if not scores:
        return None
    ordered = sorted(scores)
    return ordered[math.floor(max_rate * len(ordered) + 1e-9)]


def calibrate(entries, current, max_rate=CALIBRATION_MAX_BLOCKED):
    """Calibración del umbral con el puntaje más alto de cada pregunta. Ver el módulo.

    `entries` son `{"id", "has_answer", "max_score"}`; `current` es el umbral con que se
    corrió. Devuelve:

    - `proposed`: el umbral propuesto, redondeado hacia abajo a tres decimales, o `None`
      sin preguntas con respuesta y puntaje; `provisional`: siempre verdadero.
    - `answered`: preguntas con respuesta y puntaje; `allowed_blocked`: cuántas se
      admite frenar por error; `blocked`: las que frena el propuesto.
    - `unanswered` y `unanswered_stopped`: preguntas sin respuesta con puntaje y las que
      el propuesto frena (cuánto de la abstención resolvería el umbral solo).
    - `without_score`: preguntas con respuesta que no llegaron a puntuarse (sin régimen,
      sin candidatos o consulta rechazada); ningún umbral las cambia y no entran en la
      cuenta.
    - `current`: el umbral actual y las preguntas con respuesta que frena.
    - `leave_one_out`: por cada pregunta con respuesta, el umbral calculado con las demás
      (`thresholds`) y si la frena (`blocked`); `rate` es la proporción de frenadas y
      `meets` si no pasa de `max_rate`.
    - `scores`: el puntaje más alto de cada pregunta que lo tiene.
    """
    answered = [(e["id"], e["max_score"]) for e in entries
                if e["has_answer"] and e["max_score"] is not None]
    unanswered = [(e["id"], e["max_score"]) for e in entries
                  if not e["has_answer"] and e["max_score"] is not None]
    raw = highest_threshold([score for _, score in answered], max_rate)
    proposed = None if raw is None else _floor(raw)

    def below(rows, threshold):
        if threshold is None:
            return []
        return [case_id for case_id, score in rows if score < threshold]

    thresholds = {}
    for index, (case_id, _) in enumerate(answered):
        others = [score for i, (_, score) in enumerate(answered) if i != index]
        threshold = highest_threshold(others, max_rate)
        if threshold is not None:
            thresholds[case_id] = _floor(threshold)
    loo_blocked = [case_id for case_id, score in answered
                   if case_id in thresholds and score < thresholds[case_id]]
    loo_rate = len(loo_blocked) / len(thresholds) if thresholds else None

    return {
        "proposed": proposed,
        "provisional": True,
        "max_rate": max_rate,
        "answered": len(answered),
        "allowed_blocked": math.floor(max_rate * len(answered) + 1e-9),
        "blocked": below(answered, proposed),
        "unanswered": len(unanswered),
        "unanswered_stopped": below(unanswered, proposed),
        "without_score": [e["id"] for e in entries
                          if e["has_answer"] and e["max_score"] is None],
        "current": {"threshold": current, "blocked": below(answered, current)},
        "leave_one_out": {
            "blocked": loo_blocked,
            "total": len(thresholds),
            "rate": loo_rate,
            "meets": None if loo_rate is None else loo_rate <= max_rate + 1e-9,
            "thresholds": thresholds,
            "min": min(thresholds.values()) if thresholds else None,
            "max": max(thresholds.values()) if thresholds else None,
        },
        "scores": {e["id"]: e["max_score"] for e in entries if e["max_score"] is not None},
    }


def calibration_entries(lines):
    return [{"id": line["id"], "has_answer": line["has_answer"],
             "max_score": (line["diagnostics"] or {}).get("max_score")
             if line.get("diagnostics") else None}
            for line in lines]


# --- Comparación quitando piezas (ADR-0003) ---------------------------------------------


def _ablation_entry(case, name, paths, rerank, prompt_tokens, clock):
    """Una configuración de la comparación para un caso: recupera con `paths` y
    `rerank`, selecciona con `select_units` y mide. Devuelve la entrada y los tokens de
    instrucciones y pregunta, contados la primera vez como en la consulta."""
    entry = {"name": name, "paths": list(paths), "rerank": rerank, "skipped": None,
             "error": None}
    since = clock()
    try:
        found = retrieval.retrieve(case.question, case.reference_date, paths=paths,
                                   rerank=rerank)
        seconds = clock() - since
        if prompt_tokens is None:
            prompt_tokens = (generation.count_tokens(answering.load_instructions())
                             + generation.count_tokens(
                                 answering.request_head(case.question,
                                                        case.reference_date)))
        selection = retrieval.select_units(found, prompt_tokens)
    except AIServiceError as error:
        entry["error"] = error.reason
        return entry, prompt_tokens
    candidates = [c.as_record() for c in found.candidates]
    entry.update(
        max_score=found.max_score,
        stopped_by_threshold=(bool(found.candidates) and not found.selected) if rerank
        else None,
        retrieval_seconds=round(seconds, 3),
        candidates=candidates,
        units=[u.as_record() for u in found.units],
        sent=list(selection.unit_ids),
        found=None, selected=None, position=None,
    )
    if case.has_answer:
        entry.update(unit_hits(case.units, candidates, selection.unit_ids,
                               [u.unit_id for u in found.units], paths))
    return entry, prompt_tokens


def run_ablation(cases, clock=time.monotonic):
    """La comparación quitando piezas: `{id del caso: [entrada por configuración]}`, en
    el orden de `ABLATION_CONFIGS`. Ver el módulo."""
    ablated = {}
    for case in cases:
        if not services.applicable_regimes(case.reference_date):
            ablated[case.id] = [
                {"name": name, "paths": list(paths), "rerank": rerank,
                 "skipped": Reason.NO_REGIME_AT_DATE.value, "error": None}
                for name, paths, rerank in ABLATION_CONFIGS]
            continue
        entries, prompt_tokens = [], None
        for name, paths, rerank in ABLATION_CONFIGS:
            entry, prompt_tokens = _ablation_entry(case, name, paths, rerank,
                                                   prompt_tokens, clock)
            entries.append(entry)
        ablated[case.id] = entries
    return ablated


def ablation_measures(cases, ablated):
    """Medidas de recuperación de cada configuración, sobre los casos que se buscaron."""
    measures = []
    for index, (name, paths, rerank) in enumerate(ABLATION_CONFIGS):
        items = []
        errors = []
        for case in cases:
            entry = ablated[case.id][index]
            if entry["error"]:
                errors.append(case.id)
            usable = not entry["skipped"] and not entry["error"]
            items.append((case.id, case.has_answer, entry if usable else None))
        measures.append({"name": name, "paths": list(paths), "rerank": rerank,
                         "errors": errors,
                         **retrieval_measures(items, paths, thresholded=rerank)})
    return measures


# --- Comparación con la corrida anterior -------------------------------------------------


def find_previous_run(runs_dir, current_name):
    """La carpeta de la corrida anterior a `current_name` en `runs_dir`: la de nombre
    más alto entre las anteriores (el nombre empieza con la fecha y la hora) que tiene
    `resultados.jsonl`. `None` si no hay."""
    runs_dir = Path(runs_dir)
    if not runs_dir.is_dir():
        return None
    names = sorted(p.name for p in runs_dir.iterdir()
                   if p.is_dir() and p.name < current_name
                   and (p / "resultados.jsonl").is_file())
    return runs_dir / names[-1] if names else None


def load_run(folder):
    """Parámetros y renglones de los casos medidos de una corrida guardada."""
    folder = Path(folder)
    rows = [json.loads(row) for row in
            (folder / "resultados.jsonl").read_text(encoding="utf-8").splitlines()
            if row.strip()]
    parameters_file = folder / "parametros.json"
    parameters = (json.loads(parameters_file.read_text(encoding="utf-8"))
                  if parameters_file.is_file() else {})
    return {"folder": folder, "parameters": parameters,
            "lines": [row for row in rows if "measures" in row]}


_MODEL_KEYS = ("generation", "embeddings", "reranker")


def _conditions(parameters):
    search = dict(parameters.get("search") or {})
    models = {key: search.pop(key, None) for key in _MODEL_KEYS}
    return {
        "commit": parameters.get("commit"),
        "models": models,
        "prompt_version": parameters.get("prompt_version"),
        "corpus_version": parameters.get("corpus_version"),
        "search": search,
    }


def _cited_keys(line):
    return [(u["norm"], u["key"]) for u in line.get("cited_units") or []]


def _result_signature(line, with_text):
    keys = {u["unit"]: (u["norm"], u["key"]) for u in line.get("cited_units") or []}
    signature = [line["status"], line["reason"], _cited_keys(line)]
    if with_text:
        signature.append([(s.get("text"), bool(s.get("regimes_differ")),
                           [keys.get(u) for u in s.get("citations") or []])
                          for s in line.get("statements") or []])
    return json.dumps(signature, ensure_ascii=False, cls=DjangoJSONEncoder)


def compare_runs(previous, lines, parameters):
    """Comparación con la corrida anterior (plan, "Evals", y ADR-0002):

    - `measures`: cada medida exigida, en la anterior y en esta (`rate`; el tiempo, el
      máximo);
    - `regressions` y `improvements`: casos que pasaban y ahora fallan, y al revés;
    - `changed`: casos que cambiaron de estado, de motivo o de citas sin cambiar si
      pasan; `only_previous` y `only_current`: casos medidos en una sola;
    - `equality`: entre los casos corridos en las dos, cuántos dan el mismo resultado
      (`same`: estado, motivo, citas y texto de las afirmaciones) y cuántos el mismo
      estado y las mismas citas (`same_status_and_citations`);
    - `conditions_changed`: qué cambió entre las dos (commit, modelos, instrucciones,
      normativa o parámetros de búsqueda). Vacío: es una repetición."""
    old_lines = previous["lines"]
    old = {line["id"]: line for line in old_lines}
    new = {line["id"]: line for line in lines}
    both = [case_id for case_id in new if case_id in old]

    old_measures, new_measures = measure(old_lines), measure(lines)
    rows = [{"name": name, "previous": old_measures[name]["rate"],
             "current": new_measures[name]["rate"]}
            for name in ("literal_citation", "correct_answer", "abstention")]
    rows.append({"name": "response_time", "previous": old_measures["response_time"]["max"],
                 "current": new_measures["response_time"]["max"]})

    regressions = [c for c in both if old[c]["passed"] and not new[c]["passed"]]
    improvements = [c for c in both if not old[c]["passed"] and new[c]["passed"]]
    changed = [c for c in both if c not in regressions and c not in improvements
               and _result_signature(old[c], False) != _result_signature(new[c], False)]

    ran = [c for c in both if old[c].get("ran") and new[c].get("ran")]
    current = json.loads(_dumps(parameters))
    old_conditions = _conditions(previous["parameters"])
    new_conditions = _conditions(current)
    return {
        "previous": previous["folder"].name,
        "measures": rows,
        "regressions": regressions,
        "improvements": improvements,
        "changed": changed,
        "only_previous": [c for c in old if c not in new],
        "only_current": [c for c in new if c not in old],
        "equality": {
            "same": sum(1 for c in ran if _result_signature(old[c], True)
                        == _result_signature(new[c], True)),
            "same_status_and_citations": sum(1 for c in ran
                                             if _result_signature(old[c], False)
                                             == _result_signature(new[c], False)),
            "total": len(ran),
        },
        "conditions_changed": [key for key in new_conditions
                               if old_conditions.get(key) != new_conditions[key]],
    }


def _comparison(previous, lines, parameters):
    """`compare_runs` con la corrida anterior, si hay. Si no se puede leer, se informa y
    la corrida actual se guarda igual."""
    if previous is None:
        return None
    try:
        loaded = load_run(previous)
        return compare_runs(loaded, lines, parameters)
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {"previous": previous.name,
                "error": f"no se pudo leer ({error.__class__.__name__}: {error})"}


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

    Diagnóstico (T-042):

    - `by_regime`: respuesta correcta y abstención por régimen (`measures_by_regime`).
    - `retrieval`: medidas de recuperación de la corrida (`retrieval_measures`).
    - `output_failures`: casos con falla de formato o de cita (`output_failures`).
    - `special`: los casos de REQ-018 y REQ-019 (`special_cases`).
    - `calibration`: la calibración del umbral (`calibrate`).
    - `ablation`: medidas de cada configuración de la comparación quitando piezas
      (`ablation_measures`), o `None` si no se pidió.
    - `comparison`: la comparación con la corrida anterior (`compare_runs`), o `None` si
      no hay una.
    """

    folder: Path
    results: list
    skipped: list
    measures: dict
    pairs: list
    notices: dict
    parameters: dict
    by_regime: dict = None
    retrieval: dict = None
    output_failures: dict = None
    special: dict = None
    calibration: dict = None
    ablation: list = None
    comparison: dict = None

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
        "labels": list(case.labels),
        "differ": case.differ,
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
        "diagnostics": case_diagnostics(case, query) if query else None,
    }
    line["passed"] = _passed(line)
    return line


def _skipped_line(skipped):
    return {"id": skipped.case_id, "file": skipped.file, "ran": False,
            "skipped": skipped.kind, "reason": skipped.reason}


def run(user, cases_dir, runs_dir, *, commit=None, clock=time.monotonic, ablation=False):
    """Corre los casos de `cases_dir` y guarda la corrida en una carpeta nueva dentro de
    `runs_dir`. Ver el módulo. Lanza `RoleRejected` sin rol, antes de leer nada; el
    rechazo queda registrado con el canal `eval` y esta función como operación (T-038).

    - `commit`: el commit del código; si no se indica, `detect_commit()`.
    - `clock`: reloj en segundos para medir cada consulta y cada recuperación de la
      comparación quitando piezas (las pruebas lo reemplazan).
    - `ablation`: si es verdadero, corre además la comparación quitando piezas.
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

    ablated = run_ablation(cases, clock) if ablation else None
    for line in lines:
        line["ablation"] = ablated.get(line["id"]) if ablated else None

    parameters["prompt_version"] = prompt_versions(lines)
    parameters["finished_at"] = timezone.localtime(timezone.now()).isoformat()
    notice_lines = [line for line in lines if not line["measures"]["notice_ok"]]
    folder = Path(runs_dir) / run_folder_name(started_at, commit, settings.GENERATION_MODEL)
    previous = find_previous_run(runs_dir, folder.name)
    report = RunReport(
        folder=folder,
        results=lines,
        skipped=skipped,
        measures=measure(lines),
        pairs=check_pairs(lines),
        notices={"ok": len(lines) - len(notice_lines), "total": len(lines),
                 "failed": [line["id"] for line in notice_lines]},
        parameters=parameters,
        by_regime=measures_by_regime(lines),
        retrieval=retrieval_measures(
            [(line["id"], line["has_answer"], line["diagnostics"]) for line in lines]),
        output_failures=output_failures(lines),
        special=special_cases(lines),
        calibration=calibrate(calibration_entries(lines),
                              parameters["search"]["rerank_threshold"]),
        ablation=ablation_measures(cases, ablated) if ablated is not None else None,
        comparison=_comparison(previous, lines, parameters),
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


def _score(value):
    return "—" if value is None else f"{value:.3f}".replace(".", ",")


def _ratio_text(ratio, unit=""):
    if ratio is None:
        return "no aplica"
    return f"{_percent(ratio['rate'])} ({ratio['ok']} de {ratio['total']}{unit})"


def _ids(ids, none="ninguno"):
    return ", ".join(ids) if ids else none


def threshold_line(calibration):
    """La línea del umbral propuesto, igual en `resumen.md` y en el comando."""
    if calibration["proposed"] is None:
        return ("Umbral propuesto (provisorio): sin valor (no hay preguntas con respuesta "
                "que hayan llegado a puntuarse)")
    return f"Umbral propuesto (provisorio): {_score(calibration['proposed'])}"


_PATH_TEXT = {
    retrieval.SEMANTIC: "por significado",
    retrieval.WORDS: "por palabras",
    retrieval.REFERENCE: "por referencia exacta",
    UNION: "en la unión",
}

_CONDITION_TEXT = {
    "commit": "commit",
    "models": "modelos",
    "prompt_version": "instrucciones",
    "corpus_version": "normativa",
    "search": "parámetros de búsqueda",
}

_MEASURE_TEXT = {
    "literal_citation": "Cita literal",
    "correct_answer": "Respuesta correcta que cita la unidad correcta",
    "abstention": "Abstención",
    "response_time": "Tiempo de respuesta (máximo)",
}

SMALL_SET_NOTE = ("Con unas 30 preguntas, cada una pesa entre 3 y 5 puntos: una diferencia "
                  "de una pregunta no demuestra nada.")


def _by_regime_section(by_regime):
    out = ["## Medidas por régimen (diagnóstico)", "",
           "Separadas según el `regimen` de cada caso. Son de diagnóstico: las exigencias "
           "de la spec se miden sobre el conjunto entero, y con pocos casos por régimen "
           "sirven solo para orientar.", ""]
    if not by_regime:
        return out + ["Ningún caso medido.", ""]
    out += ["| Régimen | Respuesta correcta | Abstención |", "|---|---|---|"]
    for regime, measures in by_regime.items():
        out.append(f"| {regime or 'Sin régimen cargado a la fecha'} | "
                   f"{_ratio_text(measures['correct_answer'])} | "
                   f"{_ratio_text(measures['abstention'])} |")
    return out + [""]


def _retrieval_section(measures):
    out = ["## Recuperación (diagnóstico)", "",
           "Leído del registro de cada consulta. La unidad correcta cuenta si están "
           "todas las `unidades` del caso (un inciso vale con su artículo); se mide "
           "sobre las preguntas con respuesta (ADR-0003).", "",
           "| Medida | Resultado |", "|---|---|"]
    for key, ratio in measures["found"].items():
        out.append(f"| Unidad correcta entre los candidatos {_PATH_TEXT[key]} | "
                   f"{_ratio_text(ratio)} |")
    position = measures["position"]
    timing = measures["retrieval_time"]
    out += [
        f"| Unidad correcta entre las seleccionadas (enviadas al modelo) | "
        f"{_ratio_text(measures['selected'])} |",
        f"| Posición de la unidad correcta en el orden del reranker | mediana "
        f"{position['median'] if position['median'] is not None else '—'} · peor "
        f"{position['max'] if position['max'] is not None else '—'} |",
        f"| Preguntas con respuesta frenadas por el umbral | "
        f"{_ratio_text(measures['answered_stopped'])} |",
        f"| Preguntas sin respuesta frenadas por el umbral | "
        f"{_ratio_text(measures['unanswered_stopped'])} |",
        f"| Tiempo de la recuperación | mediana {_seconds(timing['median'])} · máximo "
        f"{_seconds(timing['max'])} |",
        "",
        f"Preguntas con respuesta frenadas por el umbral: "
        f"{_ids(measures['answered_stopped_ids'], 'ninguna')}.",
        f"Preguntas con respuesta cuya unidad correcta no llegó al modelo: "
        f"{_ids(measures['not_selected'], 'ninguna')}.",
        "",
    ]
    return out


def _output_failures_section(failures):
    return ["## Salidas con falla de formato o de cita", "",
            "Se cuentan por el tipo de anomalía; una falla de un servicio no cuenta. Se "
            "espera ninguna.", "",
            f"- Falla de formato (la salida no cumple el esquema): {len(failures['format'])}"
            f" ({_ids(failures['format'])}).",
            f"- Falla de cita (cita una unidad que no se mostró o una afirmación sin cita): "
            f"{len(failures['citation'])} ({_ids(failures['citation'])}).",
            ""]


def _special_section(special):
    def describe(entries):
        if not entries:
            return "ningún caso corrido"
        return ", ".join(f"{e['id']} {'pasa' if e['passed'] else 'falla'}" for e in entries)

    return ["## Casos de REQ-018 y REQ-019", "",
            f"- REQ-018 (etiqueta \"dos categorías\"): {describe(special['REQ-018'])}.",
            f"- REQ-019 (`difieren`): {describe(special['REQ-019'])}.",
            ""]


def _calibration_section(calibration, lines):
    loo = calibration["leave_one_out"]
    current = calibration["current"]
    out = ["## Calibración del umbral (provisoria)", "",
           f"{threshold_line(calibration)} · umbral actual: {_score(current['threshold'])}. "
           "La calibración no cambia `settings.py`: el valor lo fija T-045 con los "
           "servicios reales y el conjunto con visto bueno.", "",
           f"- Preguntas con respuesta que llegaron a puntuarse: {calibration['answered']}; "
           f"se admite frenar por error {calibration['allowed_blocked']} "
           f"({_percent(calibration['max_rate'])}).",
           "- Con el umbral propuesto, frena por error: "
           f"{_ids(calibration['blocked'], 'ninguna')}.",
           "- Con el umbral actual, frena por error: "
           f"{_ids(current['blocked'], 'ninguna')}.",
           f"- Dejando cada vez una afuera: frena {len(loo['blocked'])} de {loo['total']} "
           f"({_percent(loo['rate'])}); el umbral calculado va de {_score(loo['min'])} a "
           f"{_score(loo['max'])}; cumple el {_percent(calibration['max_rate'])}: "
           f"{_meets(loo['meets'])}. Frenadas: {_ids(loo['blocked'], 'ninguna')}.",
           f"- Preguntas sin respuesta que el umbral propuesto frena: "
           f"{len(calibration['unanswered_stopped'])} de {calibration['unanswered']}.",
           f"- Preguntas con respuesta sin puntaje (ningún umbral las cambia): "
           f"{_ids(calibration['without_score'], 'ninguna')}.",
           ""]
    scores = calibration["scores"]
    if scores:
        out += ["| Caso | Con respuesta | Régimen | Puntaje más alto |", "|---|---|---|---|"]
        for line in lines:
            if line["id"] in scores:
                out.append(f"| {line['id']} | {'sí' if line['has_answer'] else 'no'} | "
                           f"{line['expected_regime'] or '—'} | "
                           f"{_score(scores[line['id']])} |")
        out.append("")
    return out


def _ablation_section(ablation):
    out = ["## Comparación quitando piezas", ""]
    if ablation is None:
        return out + ["No se corrió en esta corrida. Se corre una vez, con "
                      "`correr_evals --quitando-piezas` (ADR-0003).", ""]
    out += ["Cada caso se recupera y se selecciona con cada configuración, sin el modelo "
            "de generación. Sin reranker no hay umbral: pasan todas las unidades de la "
            "unión, hasta los cupos.", "",
            "| Configuración | Entre los candidatos | Entre las seleccionadas | "
            "Posición (mediana · peor) | Con respuesta frenadas por el umbral | "
            "Sin respuesta frenadas por el umbral | Tiempo de la recuperación |",
            "|---|---|---|---|---|---|---|"]
    for config in ablation:
        position = config["position"]
        timing = config["retrieval_time"]
        out.append(
            f"| {config['name']} | {_ratio_text(config['found'][UNION])} | "
            f"{_ratio_text(config['selected'])} | "
            f"{position['median'] if position['median'] is not None else '—'} · "
            f"{position['max'] if position['max'] is not None else '—'} | "
            f"{_ratio_text(config['answered_stopped'])} | "
            f"{_ratio_text(config['unanswered_stopped'])} | "
            f"mediana {_seconds(timing['median'])} · máximo {_seconds(timing['max'])} |")
    errors = [f"{config['name']}: {', '.join(config['errors'])}"
              for config in ablation if config["errors"]]
    out += ["", "Fallas técnicas: " + ("; ".join(errors) if errors else "ninguna") + ".",
            SMALL_SET_NOTE, ""]
    return out


def _comparison_value(name, value):
    if name == "response_time":
        return _seconds(value)
    return _percent(value)


def _comparison_section(comparison):
    out = ["## Comparación con la corrida anterior", ""]
    if comparison is None:
        return out + ["No hay una corrida anterior en la carpeta de corridas.", ""]
    if comparison.get("error"):
        return out + [f"Corrida anterior: {comparison['previous']}: "
                      f"{comparison['error']}. No se comparó.", ""]
    changed = comparison["conditions_changed"]
    if changed:
        conditions = ("Cambió: " + ", ".join(_CONDITION_TEXT[c] for c in changed)
                      + ". No es una repetición: las diferencias pueden venir de ese cambio.")
    else:
        conditions = ("Las dos corridas tienen las mismas condiciones (commit, modelos, "
                      "instrucciones, normativa y parámetros de búsqueda): cuenta como "
                      "repetición.")
    out += [f"Corrida anterior: {comparison['previous']}.", "", conditions, "",
            "| Medida | Anterior | Actual |", "|---|---|---|"]
    out += [f"| {_MEASURE_TEXT[row['name']]} | "
            f"{_comparison_value(row['name'], row['previous'])} | "
            f"{_comparison_value(row['name'], row['current'])} |"
            for row in comparison["measures"]]
    equality = comparison["equality"]
    out += ["",
            f"- Pasaban y ahora fallan: {_ids(comparison['regressions'])}.",
            f"- Fallaban y ahora pasan: {_ids(comparison['improvements'])}.",
            f"- Cambiaron de resultado o de citas sin cambiar si pasan: "
            f"{_ids(comparison['changed'])}.",
            f"- Solo en la anterior: {_ids(comparison['only_previous'])}. Solo en esta: "
            f"{_ids(comparison['only_current'])}.",
            "",
            f"Igualdad al repetir: {equality['same']} de {equality['total']} casos corridos "
            "en las dos dan el mismo resultado (estado, motivo, citas y texto de las "
            f"afirmaciones); {equality['same_status_and_citations']} de "
            f"{equality['total']} con el mismo estado y las mismas citas. Con temperatura 0 "
            "y semilla fija, la primera consulta después de levantar el motor puede "
            "redactar distinto sin cambiar estado ni citas (T-018).",
            "", SMALL_SET_NOTE, ""]
    return out


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

    out += _by_regime_section(report.by_regime)

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

    out += _retrieval_section(report.retrieval)
    out += _output_failures_section(report.output_failures)
    out += _special_section(report.special)
    out += _calibration_section(report.calibration, report.results)
    out += _ablation_section(report.ablation)
    out += _comparison_section(report.comparison)

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
