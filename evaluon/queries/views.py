"""Pantalla de consulta (REQ-007, REQ-013, REQ-014, REQ-015, REQ-018, REQ-019, REQ-020,
REQ-021; plan 001, "Pantalla, acceso y comandos", "Forma de la respuesta", "Cita" y
"Aviso de modificatorias sin cargar (REQ-021)"; ADR-0005).

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

Búsqueda directa (REQ-006, REQ-010, REQ-012, REQ-020; T-041). La página tiene también el
formulario de búsqueda, con su propio campo de fecha. Se envía a `buscar/`, que llama a
la función de búsqueda (`services.search`, que comprueba el rol y deja el hecho
`search`) y muestra la pantalla con los resultados, sin redirigir: la búsqueda no guarda
un resultado que se pueda volver a mostrar, y cada envío es una búsqueda registrada.
Arriba de los resultados va la línea de fecha y régimen aplicado. Cada resultado muestra
su categoría, norma y ruta, la marca de derogado con la norma que lo derogó y desde
cuándo, el texto literal con el enlace al original, los cambios vigentes a la fecha con el
texto que los trae y los vínculos de su norma con otras. Un texto se muestra una sola vez
en la página, con el ancla `texto-N`: un cambio cuyo texto es otro resultado, o ya se
mostró, lleva a él.

Solo lo vigente (enmienda de REQ-010; T-056). El formulario tiene la casilla "Incluir
textos derogados", apagada de entrada, que se pasa a la función de búsqueda y conserva su
estado en la página de resultados. Si una búsqueda por artículo no muestra nada porque lo
que encontró está derogado a la fecha, la página lo dice en llano y explica cómo verlo.

Avisos de modificatorias sin cargar (REQ-021; T-052). Una respuesta con fundamento y
los resultados de una búsqueda llevan, debajo de la línea de régimen y arriba de las
afirmaciones o de los resultados, un recuadro por cada aviso guardado (`notices`), con
texto fijo de la plantilla (`_pending_notices.html`): solo el nombre de la norma y la
cantidad salen del aviso. Una consulta guardada muestra los avisos con que se respondió.

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
from evaluon.queries.forms import QueryForm, SearchForm, today
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
    return render(request, TEMPLATE, {
        "form": form,
        "search_form": SearchForm(initial={"reference_date": today()}),
    })


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
        "search_form": SearchForm(initial={"reference_date": reference_date}),
        "query": query,
        "status": status,
        "reference_date": reference_date,
        "regime": result.get("regime") or [],
        "statements": _statements(result) if status == Status.GROUNDED else [],
        "notices": _notices(result) if status == Status.GROUNDED else [],
    }
    return render(request, TEMPLATE, context)


@require_http_methods(["GET", "POST"])
def search(request):
    """Búsqueda directa enviada desde la pantalla. Un formulario rechazado vuelve
    marcado y no se busca. Uno válido va a la función de búsqueda con la fecha del
    formulario (vacía, la del día) y la página muestra los resultados, con esa fecha en
    los dos formularios. Sin envío, lleva a la pantalla."""
    if request.method == "GET":
        return redirect("queries:screen")
    search_form = SearchForm(request.POST)
    query_date = today()
    context = {}
    if search_form.is_valid():
        data = search_form.cleaned_data
        norm = data["norm"]
        try:
            outcome = services.search(
                request.user,
                data["reference_date"],
                norm_id=norm.pk if norm is not None else None,
                article=data["article"],
                words=data["words"],
                include_repealed=data["include_repealed"],
                channel=Channel.SCREEN,
            )
        except services.FutureDate as error:
            # El día cambió entre el formulario y la búsqueda.
            search_form.add_error("reference_date", str(error))
        except services.QueryRefused as error:
            search_form.add_error(None, str(error))
        else:
            query_date = outcome.reference_date
            search_form = SearchForm(initial={
                "norm": norm, "article": data["article"], "words": data["words"],
                "reference_date": outcome.reference_date,
                "include_repealed": outcome.include_repealed,
            })
            context["search"] = {
                "kind": outcome.kind,
                "terms": outcome.terms,
                "reference_date": outcome.reference_date,
                "regime": outcome.regime,
                "notices": _notices({"notices": outcome.notices}),
                "items": _search_items(outcome.results),
                "repealed_hidden": outcome.repealed_hidden,
            }
    context.update(
        form=QueryForm(initial={"reference_date": query_date}),
        search_form=search_form,
    )
    return render(request, TEMPLATE, context)


# --- Avisos de modificatorias sin cargar -------------------------------------------------


def _notices(result):
    """Los avisos de modificatorias sin cargar guardados en `result["notices"]`, como los
    muestra `_pending_notices.html`: nombre de la norma y cantidad. Se descartan los de
    otro tipo y los que no traen nombre o una cantidad mayor que cero."""
    notices = []
    for notice in result.get("notices") or []:
        if (not isinstance(notice, dict)
                or notice.get("type") != services.PENDING_AMENDMENTS):
            continue
        count = _int(notice.get("pending"))
        name = notice.get("name") or ""
        if count and count > 0 and name:
            notices.append({"name": name, "count": count})
    return notices


# --- Resultados de la búsqueda ------------------------------------------------------------

# Cómo se nombra un vínculo de la norma del resultado con otra (REQ-006): con la norma del
# resultado como origen ("Deroga …") o como alcanzada ("Es derogada por …").
LINK_OUTGOING = {"modifica": "Modifica", "complementa": "Complementa",
                 "reglamenta": "Reglamenta", "deroga": "Deroga"}
LINK_INCOMING = {"modifica": "Es modificada por", "complementa": "Es complementada por",
                 "reglamenta": "Es reglamentada por", "deroga": "Es derogada por"}
LINK_DEFAULT = "Tiene un vínculo con"


def original_url(document_id, file_format, page):
    """Enlace al documento original; en un PDF, a la página indicada."""
    if document_id is None:
        return None
    url = reverse("norms:original", args=[document_id])
    if file_format == FileFormat.PDF and page:
        url += f"#page={page}"
    return url


def _category_label(category):
    return Category(category).label if category in Category.values else ""


def _search_items(results):
    """Los resultados de `queries/search.py` como los muestra la página, en el orden
    recibido. El texto de cada resultado se muestra en el resultado; el de una unidad
    que trae un cambio, la primera vez que aparece, salvo que sea otro resultado."""
    result_ids = {result.unit_id for result in results}
    source_ids = {change.source_unit_id for result in results
                  for change in result.changes if change.source_unit_id is not None}
    units = Unit.objects.select_related("reading__document").in_bulk(
        result_ids | source_ids)
    target_paths = _search_target_paths(results, units)
    shown = set(result_ids)
    items = []
    for result in results:
        unit = units.get(result.unit_id)
        items.append({
            "id": result.unit_id,
            "anchor": anchor(result.unit_id),
            "norm": result.norm_name,
            "path": result.path,
            "category": _category_label(result.category),
            "repealed": result.repealed,
            "repeal": result.repealed_by,
            "text": _search_text(unit, result.document_id, result.text_origin,
                                 fallback=result.text),
            "changes": [_search_change(result, change, units, target_paths, shown,
                                       result_ids)
                        for change in result.changes],
            "links": [
                {"label": (LINK_OUTGOING if link.direction == "outgoing"
                           else LINK_INCOMING).get(link.relation_type, LINK_DEFAULT),
                 "norm": link.other_norm_name,
                 "date": link.effective_date}
                for link in result.links
            ],
        })
    return items


def _search_text(unit, document_id, text_origin, fallback=None):
    """Texto literal de una unidad con su enlace al original y la leyenda de
    reconocimiento, como lo recibe `_unit_text.html`."""
    if unit is not None:
        document = unit.reading.document
        literal = answering.unit_text(unit)
        url = original_url(document.pk, document.file_format, unit.page_start)
    else:
        literal = fallback
        url = original_url(document_id, None, None)
    return {"literal": literal, "original_url": url,
            "ocr": text_origin == TextOrigin.OCR}


def _search_target_paths(results, units):
    """Ruta de la parte alcanzada por cada cambio, buscada en la lectura del resultado:
    `{(id de lectura, clave): ruta}`."""
    wanted = set()
    for result in results:
        unit = units.get(result.unit_id)
        for change in result.changes:
            if unit is not None and change.target_unit_key \
                    and change.target_unit_key != unit.key:
                wanted.add((unit.reading_id, change.target_unit_key))
    if not wanted:
        return {}
    rows = Unit.objects.filter(
        reading_id__in={reading for reading, _ in wanted},
        key__in={key for _, key in wanted},
    ).values_list("reading_id", "key", "path")
    return {(reading, key): path for reading, key, path in rows
            if (reading, key) in wanted}


def _search_change(result, change, units, target_paths, shown, result_ids):
    """Un cambio de un resultado: qué es, a qué parte alcanza, desde cuándo y la unidad
    que lo trae, con su texto si es la primera vez que aparece en la página."""
    unit = units.get(result.unit_id)
    key = change.target_unit_key or ""
    part = ""
    if unit is not None and key and key != unit.key:
        part = target_paths.get((unit.reading_id, key), "")
    source = None
    source_id = change.source_unit_id
    if source_id is not None:
        source_unit = units.get(source_id)
        source = {"norm": change.source_norm_name, "path": change.source_unit_path or "",
                  "anchor": anchor(source_id), "text": None}
        if source_id not in shown and source_unit is not None:
            shown.add(source_id)
            source["text"] = _search_text(source_unit, None, source_unit.text_origin)
    return {
        "name": CHANGE_NAMES.get(change.relation_type, CHANGE_NAME_DEFAULT),
        "part": part,
        "date": change.effective_date,
        "source_norm": change.source_norm_name,
        "source": source,
        "source_in_results": source_id in result_ids,
        "source_shown_above": (source is not None and source["text"] is None
                               and source_id in shown
                               and source_id not in result_ids),
    }


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
    (REQ-018). Un considerando lleva la categoría de su documento y se presenta como
    contexto ("Régimen específico · Considerando · contexto"); cualquier otra unidad,
    también una `clausula`, lleva el papel de su categoría. Una categoría desconocida no
    se muestra."""
    label = Category(category).label if category in Category.values else ""
    if unit_type == UnitType.CONSIDERANDO:
        return f"{label} · {CONSIDERANDO_ROLE}" if label else CONSIDERANDO_ROLE
    if label:
        return f"{label} · {answering.ROLES[category]}"
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
        return original_url(document_id, self.formats.get(document_id),
                            described["page"])

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
        """Una cita. La primera aparición de la unidad lleva el ancla y el texto; las
        siguientes llevan a ella. Excepción (REQ-019): en una afirmación con
        `regimes_differ`, el texto del régimen específico y el del marco nacional se
        muestran siempre, desplegados, aunque ya hayan aparecido; el ancla sigue en la
        primera aparición. Una cita que no está ni en `units` ni en la base se muestra
        como no disponible."""
        raw_id = unit_id
        unit_id = _int(unit_id)
        record = self.records.get(str(unit_id)) or self.records.get(str(raw_id)) or {}
        if not record and unit_id not in self.units:
            return {"id": raw_id, "unavailable": True}
        described = self._describe(unit_id)
        compared = (regimes_differ
                    and described["unit_type"] != UnitType.CONSIDERANDO
                    and described["category"] in (Category.REGIMEN_ESPECIFICO,
                                                  Category.MARCO_NACIONAL))
        first = unit_id not in self.shown
        citation = {
            "id": unit_id,
            "unavailable": False,
            "norm": described["norm"],
            "path": described["path"],
            "role": role(described["category"], described["unit_type"]),
            "open": compared,
            "first": first,
            "anchor": anchor(unit_id),
            "changed": bool(record.get("changes")),
            "text": None,
            "changes": [],
        }
        if first or compared:
            citation["text"] = self._text(unit_id, described)
            citation["changes"] = [self._change(unit_id, change)
                                   for change in record.get("changes") or ()]
        # "Texto aplicable" solo sobre una cita que muestra su texto.
        citation["applicable"] = (compared and citation["text"] is not None
                                  and described["category"]
                                  == Category.REGIMEN_ESPECIFICO)
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
