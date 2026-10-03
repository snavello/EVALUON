"""Pantalla de consulta (REQ-007, REQ-013, REQ-014, REQ-015, REQ-018, REQ-019, REQ-020;
plan 001, "Pantalla, acceso y comandos", "Forma de la respuesta" y "Cita"; ADR-0005).

Una sola página armada en el servidor, en la raíz del sitio: el formulario de la
pregunta y, para una consulta guardada, uno de tres bloques (con fundamento, no
determinado, falla técnica). La página de una consulta guardada se arma desde
`queries_query.result`; el texto literal de cada cita se lee de la base por `id`
(`answering.unit_text`: `canonical_text[char_start:char_end]`), porque no viaja en el
resultado. Solo la ve quien hizo la consulta.

Cada cita muestra la categoría de su documento con su papel en palabras (T-037), la norma
y la ruta; al desplegarla, el texto literal, el enlace al documento original (en un PDF,
a la página de la unidad) y, si el texto vino de reconocimiento sobre imagen, la leyenda
que lo dice. Una unidad modificada a la fecha lleva el aviso del cambio y el texto de la
unidad que la modifica. El texto de cada unidad se muestra una sola vez en la página: las
demás citas de esa unidad llevan a él.

Las vistas no guardan nada en la sesión: si lo hicieran, la sesión se volvería a grabar
y el tope de 8 horas desde el ingreso se renovaría con el uso.
"""

from datetime import date

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from evaluon.audit.models import Channel
from evaluon.norms.indexing import norm_name
from evaluon.norms.models import Category, Document, FileFormat, TextOrigin, Unit, UnitType
from evaluon.queries import answering, services
from evaluon.queries.forms import QueryForm, today
from evaluon.queries.models import Query, Status

TEMPLATE = "queries/consulta.html"

# Papel de un considerando en la pantalla (REQ-018).
CONSIDERANDO_ROLE = "Considerando · contexto"

# Cómo se nombra cada tipo de cambio en el aviso (REQ-007).
CHANGE_NAMES = {"modifica": "Modificación", "deroga": "Derogación"}
CHANGE_NAME_DEFAULT = "Cambio"


@require_http_methods(["GET", "POST"])
def screen(request):
    """Página sin consulta: el formulario con la fecha del día. Al enviarlo, el
    formulario se valida; uno rechazado vuelve marcado y no se consulta. Una pregunta
    válida va a la función de consulta con la fecha del formulario (vacía, la del día) y
    la página redirige al resultado guardado, de modo que recargar no vuelve a consultar
    (T-019)."""
    if request.method == "POST":
        form = QueryForm(request.POST)
        if form.is_valid():
            try:
                query = services.ask(
                    request.user,
                    form.cleaned_data["question"],
                    form.cleaned_data["reference_date"],
                    channel=Channel.SCREEN,
                )
            except services.FutureDate as error:
                # El día cambió entre el formulario y la consulta.
                form.add_error("reference_date", str(error))
            except services.QueryRefused as error:
                form.add_error("question", str(error))
            else:
                return redirect("queries:query", pk=query.pk)
    else:
        form = QueryForm(initial={"reference_date": today()})
    return render(request, TEMPLATE, {"form": form})


@require_GET
def query_detail(request, pk):
    """Página de una consulta guardada: el formulario con la fecha de esa consulta y el
    bloque de su resultado."""
    query = get_object_or_404(Query, pk=pk, user=request.user)
    result = query.result
    reference_date = date.fromisoformat(
        result.get("reference_date") or query.reference_date.isoformat()
    )
    status = result.get("status")
    if status not in Status.values:
        status = Status.ERROR

    context = {
        "form": QueryForm(initial={"reference_date": reference_date}),
        "query": query,
        "status": status,
        "reference_date": reference_date,
        "regime": result.get("regime") or [],
        "statements": _statements(result) if status == Status.GROUNDED else [],
    }
    return render(request, TEMPLATE, context)


# --- Afirmaciones y citas ---------------------------------------------------------------


def _statements(result):
    """Afirmaciones en el orden guardado, cada una con sus citas en el orden guardado.

    Cada cita trae su papel, norma y ruta. La primera vez que aparece una unidad en la
    página (como cita o como unidad que modifica a otra) trae además su texto: literal,
    enlace al original, leyenda de reconocimiento y cambios. Las siguientes llevan a esa
    primera aparición (`anchor`)."""
    records = result.get("units") or {}
    statements = result.get("statements") or []
    page = _Page(records, statements)
    return [
        {
            "text": statement.get("text", ""),
            "regimes_differ": bool(statement.get("regimes_differ")),
            "citations": [
                page.citation(unit_id, bool(statement.get("regimes_differ")))
                for unit_id in statement.get("citations") or []
            ],
        }
        for statement in statements
    ]


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _iso_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def anchor(unit_id):
    """Ancla del texto de una unidad en la página."""
    return f"texto-{unit_id}"


def role(category, unit_type):
    """Categoría con su papel en palabras, derivado de `category` y `unit_type`
    (REQ-018). Un considerando es contexto; cualquier otra unidad, también una
    `clausula`, lleva el papel de su categoría. Una categoría desconocida no se muestra."""
    if unit_type == UnitType.CONSIDERANDO:
        return CONSIDERANDO_ROLE
    if category in Category.values:
        return f"{Category(category).label} · {answering.ROLES[category]}"
    return ""


class _Page:
    """Lo que hace falta leer de la base para las citas de una respuesta, y el registro
    de qué unidades ya mostraron su texto en la página."""

    def __init__(self, records, statements):
        self.records = records
        self.shown = set()
        cited = {_int(unit_id) for s in statements for unit_id in s.get("citations") or []}
        sources = {_int(change.get("unit"))
                   for record in records.values()
                   for change in record.get("changes") or ()}
        wanted = {unit_id for unit_id in cited | sources if unit_id is not None}
        self.units = Unit.objects.select_related("reading__document__norm").in_bulk(wanted)
        document_ids = {_int(record.get("document")) for record in records.values()}
        document_ids |= {unit.reading.document_id for unit in self.units.values()}
        self.formats = dict(Document.objects.filter(
            pk__in=[pk for pk in document_ids if pk is not None]
        ).values_list("pk", "file_format"))
        self.target_paths = self._target_paths()

    def _target_paths(self):
        """Ruta de la parte alcanzada por cada cambio, buscada en la lectura de la unidad
        que cambia: `{(id de lectura, clave): ruta}`."""
        wanted = set()
        for unit_id, record in self.records.items():
            unit = self.units.get(_int(unit_id))
            for change in record.get("changes") or ():
                key = change.get("target_unit_key")
                if unit is not None and key and key != unit.key:
                    wanted.add((unit.reading_id, key))
        if not wanted:
            return {}
        rows = Unit.objects.filter(
            reading_id__in={reading for reading, _ in wanted},
            key__in={key for _, key in wanted},
        ).values_list("reading_id", "key", "path")
        return {(reading, key): path for reading, key, path in rows
                if (reading, key) in wanted}

    def _describe(self, unit_id):
        """Norma, ruta, categoría, tipo, origen, documento y página de una unidad: lo
        guardado en `units` y, lo que falte, de la base."""
        record = self.records.get(str(unit_id)) or {}
        unit = self.units.get(unit_id)
        norm = unit.reading.document.norm if unit is not None else None

        def value(name, from_unit):
            if record.get(name) not in (None, ""):
                return record[name]
            return from_unit() if unit is not None else None

        return {
            "norm": value("norm", lambda: norm_name(norm)) or "",
            "path": value("path", lambda: unit.path) or "",
            "category": value("category", lambda: norm.category),
            "unit_type": value("unit_type", lambda: unit.unit_type),
            "text_origin": value("text_origin", lambda: unit.text_origin),
            "document": _int(value("document", lambda: unit.reading.document_id)),
            "page": _int(value("page_start", lambda: unit.page_start)),
        }

    def _original_url(self, described):
        document_id = described["document"]
        if document_id is None:
            return None
        url = reverse("norms:original", args=[document_id])
        if self.formats.get(document_id) == FileFormat.PDF and described["page"]:
            url += f"#page={described['page']}"
        return url

    def _text(self, unit_id, described):
        """Texto de una unidad con lo que lo acompaña, y queda marcada como mostrada.
        `literal` es `None` si la unidad no está en la base."""
        self.shown.add(unit_id)
        unit = self.units.get(unit_id)
        return {
            "anchor": anchor(unit_id),
            "literal": answering.unit_text(unit) if unit is not None else None,
            "original_url": self._original_url(described),
            "ocr": described["text_origin"] == TextOrigin.OCR,
        }

    def citation(self, unit_id, regimes_differ):
        unit_id = _int(unit_id)
        described = self._describe(unit_id)
        citation = {
            "id": unit_id,
            "norm": described["norm"],
            "path": described["path"],
            "role": role(described["category"], described["unit_type"]),
            "applicable": (regimes_differ
                           and described["category"] == Category.REGIMEN_ESPECIFICO
                           and described["unit_type"] != UnitType.CONSIDERANDO),
            "open": regimes_differ,
            "anchor": anchor(unit_id),
            "text": None,
            "changes": [],
        }
        if unit_id in self.shown:
            return citation
        citation["text"] = self._text(unit_id, described)
        record = self.records.get(str(unit_id)) or {}
        citation["changes"] = [self._change(unit_id, change)
                               for change in record.get("changes") or ()]
        return citation

    def _change(self, unit_id, change):
        """Un cambio de la unidad: qué es, desde cuándo, a qué parte alcanza y la unidad
        que lo trae, con su texto si es la primera vez que aparece en la página."""
        unit = self.units.get(unit_id)
        key = change.get("target_unit_key") or ""
        if unit is None or not key or key == unit.key:
            part = ""
        else:
            part = self.target_paths.get((unit.reading_id, key), "")
        source_id = _int(change.get("unit"))
        source = None
        if source_id is not None and (str(source_id) in self.records
                                      or source_id in self.units):
            described = self._describe(source_id)
            source = {"norm": described["norm"], "path": described["path"],
                      "anchor": anchor(source_id), "text": None}
            if source_id not in self.shown and source_id in self.units:
                source["text"] = self._text(source_id, described)
        return {
            "name": CHANGE_NAMES.get(change.get("relation_type"), CHANGE_NAME_DEFAULT),
            "part": part,
            "date": _iso_date(change.get("effective_date")),
            "source": source,
            "source_shown_above": (source is not None and source["text"] is None
                                   and source_id in self.shown),
        }
