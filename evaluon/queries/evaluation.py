"""Corrida del conjunto de preguntas y medida de las exigencias de la spec (P7; REQ-008,
REQ-009, REQ-020, REQ-021; plan 001, "Evals"). Versión de T-039.

`run(usuario, carpeta_de_casos, carpeta_de_corridas)`:

1. Comprueba el rol (lectura; el de lectura y escritura lo incluye).
2. Lee los casos: un archivo `EV-NNN.yaml` por pregunta (`load_cases`). Un caso mal
   formado, o sin `fecha_autorizacion`, se informa y no se corre; un caso sin
   `visto_bueno` tampoco se corre. Los demás archivos de la carpeta se ignoran.
3. Corre cada caso con la misma función que la pantalla, `services.ask`, con el canal
   `eval` y la `fecha_autorizacion` del caso, una pregunta por vez. Nunca pasa una
   fecha vacía: la función de consulta usaría la del día. Cada consulta queda en el
   registro de auditoría como cualquier otra (P6).
4. Mide cada caso (`grade`) y la corrida entera (`measure`):
   - cita literal: sobre todas las citas de todas las respuestas, el texto que se
     muestra (`answering.citation_texts`) es igual a `canonical_text[char_start:char_end]`
     de la lectura de la unidad, leído acá por separado. Umbral 100 %;
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

Los datos clave se buscan en el texto de las afirmaciones sin distinguir mayúsculas,
tildes ni espacios repetidos; fuera de eso, tienen que aparecer tal cual. En la corrida
que se presenta para aprobar, el responsable revisa además las respuestas contra la
esperada (plan, "Evals").

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
        if not case.approval:
            skipped.append(Skipped(path.name, case.id, NOT_APPROVED,
                                   "sin visto bueno de la Comisión"))
            continue
        cases.append(case)
    return cases, skipped


# --- Medida de un caso -----------------------------------------------------------------


def normalize(text):
    """Texto para buscar los datos clave: sin tildes, sin distinguir mayúsculas y con
    los espacios repetidos reducidos a uno."""
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", plain.casefold()).strip()


def _statement_citations(result):
    return [unit_id for s in result.get("statements") or [] for unit_id in s["citations"]]


def cited_units(result):
    """Cada unidad citada en el resultado, una vez y en orden de aparición, con su norma
    (nombre de cita), su clave, su tipo, su categoría y si el texto que se muestra es
    igual a `canonical_text[char_start:char_end]` de su lectura."""
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
                          "category": None, "literal": False})
            continue
        norm = unit.reading.document.norm
        expected = unit.reading.canonical_text[unit.char_start:unit.char_end]
        cited.append({
            "unit": unit_id,
            "norm": norm.citation,
            "key": unit.key,
            "unit_type": unit.unit_type,
            "category": norm.category,
            "literal": unit_id in shown and shown[unit_id] == expected,
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

    text = normalize("\n".join(s["text"] for s in result.get("statements") or []))
    missing_units = [u for u in case.units
                     if not any(_unit_matches(u, unit) for unit in cited)]
    missing_data = [d for d in case.key_data if normalize(d) not in text]
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
    """Las cuatro medidas exigidas sobre los renglones de los casos corridos."""
    answered = [line for line in lines if line["has_answer"]]
    unanswerable = [line for line in lines if not line["has_answer"]]
    times = [line["time_seconds"] for line in lines]
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
    - `results`: un renglón por caso corrido, como en `resultados.jsonl`.
    - `skipped`: los casos que no se corrieron, con su motivo.
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
        """Casos corridos que fallaron alguna medida o comprobación, en orden."""
        return [line["id"] for line in self.results if _failures(line)]


def _failures(line):
    measures = line["measures"]
    reasons = []
    if line["has_answer"] and not measures["correct"]:
        failed = [name for name, ok in measures["checks"].items() if not ok]
        reasons.append("respuesta incorrecta (" + ", ".join(_CHECK_TEXT[n] for n in failed) + ")")
    if not line["has_answer"] and not measures["abstained"]:
        reasons.append("no se abstuvo" if line["status"] != Status.ERROR
                       else "falla técnica en lugar de abstención")
    if measures["literal_citations"] != measures["citations"]:
        reasons.append("cita que no es literal")
    if not measures["notice_ok"]:
        reasons.append("aviso de modificatorias distinto del esperado")
    if line["time_seconds"] > MAX_SECONDS:
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
        "prompt_version": answering.PROMPT_VERSION,
        "search": services.parameters(),
    }


def _case_line(case, query, elapsed):
    result = query.result
    cited = cited_units(result)
    line = {
        "id": case.id,
        "file": case.file,
        "ran": True,
        "question": case.question,
        "reference_date": case.reference_date.isoformat(),
        "expected_regime": case.regime,
        "has_answer": case.has_answer,
        "pair": case.pair,
        "expected_notice": case.notice,
        "query_id": query.pk,
        "corpus_version": query.corpus_version,
        "status": result["status"],
        "reason": result["reason"],
        "regime": [r["name"] for r in result.get("regime") or []],
        "notices": result.get("notices") or [],
        "statements": result.get("statements") or [],
        "cited_units": cited,
        "measures": grade(case, result, cited),
        "time_seconds": round(elapsed, 3),
        "timings": query.timings,
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
            skipped.append(Skipped(case.file, case.id, REFUSED,
                                   f"la consulta se rechazó: {error}"))
            continue
        elapsed = clock() - since
        lines.append(_case_line(case, query, elapsed))

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
    """Cantidades de casos leídos, corridos y no corridos por motivo."""
    by_kind = {kind: sum(1 for s in report.skipped if s.kind == kind)
               for kind in (NOT_APPROVED, MALFORMED, REFUSED)}
    ran = len(report.results)
    return {"read": ran + len(report.skipped), "ran": ran, **by_kind}


def counts_line(report):
    """Una línea en lenguaje llano con las cantidades de casos."""
    c = counts(report)
    line = (f"Casos leídos: {c['read']} · corridos: {c['ran']} · "
            f"{c[NOT_APPROVED]} sin visto bueno · {c[MALFORMED]} mal formados")
    if c[REFUSED]:
        line += f" · {c[REFUSED]} rechazados por la consulta"
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
    out = [
        f"# Corrida {report.folder.name}",
        "",
        f"- Comienzo: {p['started_at']} · fin: {p['finished_at']}",
        f"- Commit: {p['commit']}",
        f"- Modelo de generación: {search['generation']['model']} "
        f"(compilación {search['generation']['engine_build']})",
        f"- Versión de las instrucciones: {p['prompt_version']}",
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
