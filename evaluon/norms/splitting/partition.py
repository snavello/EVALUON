"""Partición de una norma en unidades (ADR-0004, "Cómo se parte"; plan 001,
"Identificación de unidades", "Una norma en más de un archivo", "Texto normativo sin
número de artículo" y "Unidades base, incisos y pasajes"; T-013 y T-023).

Las reglas trabajan sobre los párrafos del texto canónico, clasificados por su comienzo
con la tabla de `headings.py`. Cada párrafo termina en uno de tres lugares, y la suma da
el total (control de cobertura):

- **Una unidad base.** Artículo, cláusula (texto normativo sin número), anexo (su texto
  propio), visto y considerandos. Cada una va desde su encabezado hasta el párrafo
  anterior al siguiente encabezado que la cierra.
- **Descartado.** La carátula (membrete y datos GDE), el índice, los encabezados de
  título, capítulo y sección, que no son unidades y pasan a la ruta, y los datos de
  publicación del Boletín Oficial de una página web.
- **No ubicado.** Todo lo demás: lo que sigue a un encabezado reconocido hasta la próxima
  unidad, la fórmula "Por ello", lo que sigue al artículo de forma y la firma.

Los incisos son unidades hijas del artículo, cuyo texto es un recorte del artículo; no
cuentan en la cobertura.

Reglas:

- **Qué cierra una unidad.** Un artículo aceptado, un título, capítulo o sección, una
  cláusula, un anexo, el índice y la firma. Decisión del responsable del 2026-10-03: un
  párrafo propio que coincide con un encabezado reconocido cierra el artículo, y lo que
  sigue hasta la próxima unidad queda sin ubicar; un párrafo en mayúsculas que no es un
  encabezado reconocido no corta: queda dentro y el informe lo señala.
- **Secuencia.** Dentro de cada contenedor (el cuerpo, la unidad raíz de un anexo o un
  anexo dentro del cuerpo) un encabezado de artículo se acepta si continúa la numeración
  o salta hacia adelante hasta `SEQUENCE_MARGIN` números; el salto se informa. `14 bis`
  se acepta después del 14. Un encabezado que no se acepta queda dentro de la unidad
  abierta y se informa. En párrafos de reconocimiento sobre imagen, un encabezado con el
  número mal leído se acepta como el siguiente esperado N, y se informa como dudoso, si
  puede ser N (`$` por 8; N seguido de un 7 o un 9, que es el signo `°` leído como cifra:
  `47` por `4°`) y el encabezado que le sigue no es N, o si está donde corresponde por la
  secuencia (los encabezados que le siguen continúan la numeración). En PDF con texto y
  en web la regla queda estricta.
- **Índice.** Una serie de encabezados de artículo sin texto, con títulos intercalados,
  es un índice si al menos `INDEX_MIN_HEADINGS` de sus números vuelven a aparecer
  después como encabezados de artículo en el mismo contenedor: en un cuerpo, antes del
  siguiente encabezado "ANEXO", que vuelve a numerar; con una parte que es un anexo, en
  todo el documento, porque sus encabezados "ANEXO" no abren otro contenedor. Así dos
  artículos "DEROGADO" seguidos no se toman por un índice, aunque un anexo posterior
  repita sus números. La serie empieza con "ÍNDICE", un título o un encabezado de
  artículo, y admite también incisos y párrafos en mayúsculas (el índice de la 297/03
  lista los incisos y parte en dos líneas los epígrafes largos); termina en su último
  encabezado de artículo y los incisos que lo siguen.
- **Títulos.** Un título cierra el capítulo y la sección abiertos; un capítulo, la
  sección. Pasan a la ruta de las unidades que siguen. Una cláusula y un anexo los
  cierran todos. Un título solo (`TITULO II`) seguido de un párrafo en mayúsculas lleva
  ahí su nombre, que se descarta con él (297/03).
- **Artículo de forma.** El artículo cuyo texto empieza con "Comuníquese", "Regístrese"
  o "Publíquese" termina en su párrafo: lo que le sigue hasta el próximo encabezado (la
  firma, el nombre de un anexo) queda no ubicado. Los datos de publicación del Boletín
  Oficial (la nota sobre los anexos y la línea de edición) cierran la unidad abierta y se
  descartan.
- **Anexos.** Con una parte que es un anexo, todas las unidades cuelgan de la unidad raíz
  y los encabezados "ANEXO" de su carátula no abren otro contenedor. En un cuerpo, un
  encabezado "ANEXO" después del primer artículo abre una unidad `anexo` que vuelve a
  numerar; un párrafo en prosa que empieza con "ANEXO I" no es un encabezado
  (`headings.py`). El texto propio de un anexo es su encabezado y lo que hay antes de su primer
  artículo, título o cláusula; un anexo sin artículos tiene todo su texto.
- **Visto y considerandos.** Solo en el cuerpo, antes del primer artículo: el visto es la
  unidad `visto`; cada párrafo que empieza con "Que" es un considerando, y los párrafos
  que siguen sin "Que" son de ese considerando. El encabezado "CONSIDERANDO:" va con el
  primero.
- **Incisos.** Dos niveles. Un inciso se acepta si continúa la secuencia de su forma
  (`a)`, `b)`...; `1.`, `2.`...) o si abre una forma nueva por su primer valor. Va hasta
  el siguiente inciso de su nivel o de uno superior; el último de su lista no se lleva
  los párrafos que siguen, que son de la unidad que lo contiene. Como el PDF no
  distingue sangrías, esos párrafos pueden ser del inciso: el informe los señala con la
  clave del inciso y cuántos párrafos quedaron en la unidad que lo contiene. Formas de
  la 297/03 (T-050):
  - `Inciso N)`, con la palabra, es siempre del primer nivel: cierra las listas abiertas
    y no se anida en un inciso de letra. Es una sección con epígrafe: el último de la
    lista lleva sus párrafos hasta el final del artículo, como los demás hasta el
    siguiente, y no se señala.
  - Con los dos niveles ocupados, un párrafo que no es inciso y termina en dos puntos
    ("... las siguientes pautas:") abre una lista nueva en el primer nivel; ese párrafo
    es del artículo y el inciso anterior termina antes.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from evaluon.norms.splitting.headings import (
    ANNEX,
    ARTICLE,
    CLAUSE,
    CONSIDERANDO_HEADING,
    FORMULA,
    INCISO,
    INDEX,
    PUBLICATION,
    QUE,
    SIGNATURE,
    TITLE,
    UPPER,
    VISTO,
    Heading,
    classify_heading,
    is_closing_article,
)

# Cuántos números puede saltar hacia adelante un encabezado de artículo y aceptarse.
SEQUENCE_MARGIN = 3
# Cuántos encabezados sin texto, seguidos, hacen un índice, y cuántos de sus números
# tienen que repetirse después.
INDEX_MIN_HEADINGS = 2
# Cuántos niveles de incisos se reconocen.
INCISO_LEVELS = 2

# Carátula de un documento GDE: membrete con la leyenda del año, "Número:" y
# "Referencia:".
LETTERHEAD = re.compile(r".+\b\d{4} - [\"“].+[\"”]$")
GDE_NUMBER = re.compile(r"Número:")
GDE_REFERENCE = re.compile(r"Referencia:")

PATH_SEPARATOR = " › "
BODY_NAME = "Cuerpo"

# Destinos de un tramo que no es unidad.
DISCARDED = "discarded"
UNLOCATED = "unlocated"


@dataclass
class Paragraph:
    index: int
    start: int
    end: int
    text: str
    page: int | None
    ocr: bool
    heading: Heading


@dataclass
class Container:
    """El cuerpo, la unidad raíz de un anexo o un anexo dentro del cuerpo."""

    name: str
    key: str  # vacía en el cuerpo
    path: str  # vacía en el cuerpo
    expected: int = 1
    last_number: int | None = None
    suffixes: set = field(default_factory=set)
    gaps: list = field(default_factory=list)
    not_accepted: list = field(default_factory=list)
    clause_names: dict = field(default_factory=dict)

    def child_key(self, key):
        return f"{self.key}/{key}" if self.key else key

    def child_path(self, *parts):
        return PATH_SEPARATOR.join(([self.path] if self.path else []) + list(parts))


@dataclass
class Block:
    """Una unidad base en armado: va del párrafo `first` al `last` (vacía si
    `first > last`)."""

    unit_type: str
    number: str
    label: str
    key: str
    path: str
    parent_key: str | None
    first: int
    last: int


@dataclass
class Span:
    """Un tramo que no es unidad: descartado o no ubicado."""

    kind: str
    first: int
    last: int
    reason: str = ""
    group: int | None = None


@dataclass
class Partition:
    """Resultado de la partición, en párrafos. `items` trae los bloques y los tramos en
    el orden del documento; `incisos` los incisos de cada artículo, por su clave."""

    items: list = field(default_factory=list)
    incisos: dict = field(default_factory=dict)
    containers: list = field(default_factory=list)
    uppercase_in_units: list = field(default_factory=list)
    doubtful_headings: list = field(default_factory=list)


def classify(paragraph_spans, text, canonical, ocr_flags):
    """Los párrafos del texto canónico con su clase."""
    paragraphs = []
    for index, (start, end) in enumerate(paragraph_spans):
        content = text[start:end]
        paragraphs.append(
            Paragraph(
                index=index,
                start=start,
                end=end,
                text=content,
                page=canonical.pages_at(start, end)[0],
                ocr=ocr_flags[index],
                heading=classify_heading(content, ocr=ocr_flags[index]),
            )
        )
    return paragraphs


def partition(paragraphs, root=None):
    """Asigna cada párrafo a una unidad o a un tramo. `root` es la unidad raíz de un
    anexo (`{"key", "number", "path"}`) o vacío para el cuerpo."""
    return _Walk(paragraphs, root).run()


class _Walk:
    def __init__(self, paragraphs, root):
        self.paragraphs = paragraphs
        self.root = root
        self.result = Partition()
        self.open = None  # bloque abierto
        self.held = None  # párrafo "CONSIDERANDO:" a la espera de su primer considerando
        self.titles = [None, None, None]
        self.body_started = False
        self.considerandos = 0
        self.annex_keys = {}
        self.doubtful = False
        self.closing_key = None  # clave del artículo de forma
        self.bare_title = None  # párrafo de un título solo, a la espera de su nombre
        if root:
            self.container = Container(name=root["path"], key=root["key"], path=root["path"])
        else:
            self.container = Container(name=BODY_NAME, key="", path="")
        self.result.containers.append(self.container)

    # --- Recorrido ---------------------------------------------------------------------

    def run(self):
        paragraphs = self.paragraphs
        in_index = _index_blocks(paragraphs, same_container=self.root is None)
        start = _cover_end(paragraphs) + 1
        if start > 0:
            self.result.items.append(Span(DISCARDED, 0, start - 1, reason="caratula"))
        if self.root:
            label = self.root["path"]
            self.open = Block("anexo", self.root["number"], label, self.root["key"],
                              self.root["path"], None, start, start - 1)
            self.root_open = True
        else:
            self.root_open = False

        for paragraph in paragraphs[start:]:
            self.step(paragraph, in_index)
        self.flush_held()
        self.close()
        return self.result

    def step(self, p, in_index):
        k, h = p.index, p.heading
        eligible_considerando = self.container.key == "" and not self.body_started
        if self.held is not None and not (h.kind == QUE and eligible_considerando):
            self.flush_held()

        bare_title, self.bare_title = self.bare_title, None
        if k in in_index:
            self.close()
            self.span(DISCARDED, k, reason="indice", group=in_index[k])
            return
        if bare_title is not None and h.kind == UPPER and self.open is None:
            # El nombre de un título que vino solo en el párrafo anterior.
            self.span(DISCARDED, k, reason="titulo", group=bare_title)
            return
        body_annex = h.kind == ANNEX and not self.root
        if self.root_open and h.kind not in (ARTICLE, TITLE, CLAUSE, SIGNATURE, PUBLICATION) and not body_annex:
            self.extend(p, record_upper=False)
            if self.root and h.kind == ANNEX and self.open.label == self.root["path"]:
                self.open.label = p.text
            return
        if h.kind == ARTICLE:
            number = self.accept_article(p)
            if number is not None:
                self.close()
                self.open_article(p, number)
                return
            self.container.not_accepted.append(
                {"number": h.number, "page": p.page, "inside": self.open.key if self.open else ""}
            )
        elif h.kind == TITLE:
            self.close()
            level = h.level
            self.titles[level] = h.name
            for lower in range(level + 1, len(self.titles)):
                self.titles[lower] = None
            self.span(DISCARDED, k, reason="titulo", group=k)
            if h.heading_only:
                self.bare_title = k
            return
        elif h.kind == CLAUSE:
            self.close()
            self.open_clause(p)
            return
        elif h.kind == ANNEX:
            self.close()
            if not self.root and self.body_started:
                self.open_annex(p)
            else:
                self.span(UNLOCATED, k)
            return
        elif h.kind == SIGNATURE:
            self.close()
            self.span(UNLOCATED, k)
            return
        elif h.kind == PUBLICATION:
            self.close()
            self.span(DISCARDED, k, reason="publicacion")
            return
        elif h.kind == VISTO and eligible_considerando:
            self.close()
            self.open = Block("considerando", "", "VISTO", "visto", "Visto", None, k, k)
            return
        elif h.kind == CONSIDERANDO_HEADING and eligible_considerando:
            self.close()
            self.held = k
            return
        elif h.kind == QUE and eligible_considerando:
            self.close()
            self.considerandos += 1
            n = self.considerandos
            first = self.held if self.held is not None else k
            self.held = None
            self.open = Block("considerando", str(n), f"Considerando {n}", f"considerando-{n}",
                              f"Considerando {n}", None, first, k)
            return
        elif h.kind == FORMULA and self.open is not None and self.open.unit_type == "considerando":
            self.close()
            self.span(UNLOCATED, k)
            return

        if self.open is not None and self.open.key == self.closing_key:
            # Lo que sigue al artículo de forma (la firma, el nombre de un anexo) no se
            # le suma.
            self.close()
        if self.open is not None:
            self.extend(p, record_upper=h.kind == UPPER)
        else:
            self.span(UNLOCATED, k)

    # --- Unidades ----------------------------------------------------------------------

    def extend(self, p, record_upper):
        self.open.last = p.index
        if record_upper and self.open.unit_type in ("articulo", "clausula", "considerando"):
            self.result.uppercase_in_units.append(
                {"key": self.open.key, "page": p.page, "first_words": " ".join(p.text.split()[:8])}
            )

    def close(self):
        if self.open is not None:
            self.result.items.append(self.open)
            self.open = None
        self.root_open = False

    def flush_held(self):
        if self.held is not None:
            self.span(UNLOCATED, self.held)
            self.held = None

    def span(self, kind, k, reason="", group=None):
        """Suma el párrafo `k` al último tramo si es del mismo destino, del mismo grupo y
        le sigue; si no, abre un tramo nuevo."""
        items = self.result.items
        last = items[-1] if items else None
        if (
            isinstance(last, Span)
            and last.kind == kind
            and last.reason == reason
            and last.group == group
            and last.last == k - 1
        ):
            last.last = k
            return
        items.append(Span(kind, k, k, reason=reason, group=group))

    def accept_article(self, p):
        """El número con que se acepta un encabezado de artículo, o vacío."""
        h, c = p.heading, self.container
        if h.suffix:
            if (
                h.article_number is not None
                and h.article_number == c.last_number
                and h.suffix not in c.suffixes
            ):
                c.suffixes.add(h.suffix)
                return h.number
            return None
        n = h.article_number
        if n is not None and c.expected <= n <= c.expected + SEQUENCE_MARGIN:
            c.gaps.extend(str(missing) for missing in range(c.expected, n))
            self.advance(n)
            return str(n)
        if p.ocr and (_could_be(h.raw, c.expected) or self.fits_sequence(p.index)):
            # Leído por reconocimiento: el número está mal leído (`$6` por 86, `47` por
            # 4° con el signo leído como cifra) o es imposible para la secuencia y el
            # encabezado está donde corresponde. Se acepta como el siguiente, dudoso.
            if _could_be(h.raw, c.expected) and self.next_could_be(p.index, c.expected):
                return None  # el siguiente encabezado es el que corresponde
            n = c.expected
            self.advance(n)
            self.doubtful = True
            return str(n)
        return None

    def next_could_be(self, k, number):
        following = self.following_headings(k)[:1]
        return bool(following) and _could_be(following[0].raw, number)

    def following_headings(self, k):
        return [
            p.heading
            for p in self.paragraphs[k + 1 :]
            if p.heading.kind == ARTICLE and not p.heading.suffix
        ]

    def advance(self, n):
        c = self.container
        c.expected = n + 1
        c.last_number = n
        c.suffixes = set()

    def fits_sequence(self, k):
        """Si un encabezado leído por reconocimiento está donde corresponde por la
        secuencia: alguno de los dos encabezados de artículo que le siguen continúa la
        numeración (o no se pudo leer), o no le sigue ninguno."""
        expected = self.container.expected
        following = self.following_headings(k)[:2]
        if not following:
            return True
        for distance, heading in enumerate(following, start=1):
            if heading.article_number is None or _could_be(heading.raw, expected + distance):
                return True
        return False

    def open_article(self, p, number):
        c = self.container
        if c.key == "":
            self.body_started = True
        key = c.child_key("art-" + number.replace(" ", "-"))
        titles = [title for title in self.titles if title]
        path = c.child_path(*titles, f"Artículo {number}")
        self.open = Block("articulo", number, p.heading.label, key, path, c.key or None,
                          p.index, p.index)
        if is_closing_article(p.text, ocr=p.ocr):
            self.closing_key = key
        if self.doubtful:
            self.result.doubtful_headings.append(
                {"key": key, "label": p.heading.label, "page": p.page}
            )
            self.doubtful = False

    def open_clause(self, p):
        c = self.container
        name = p.heading.name
        slug = _slug(name)
        count = c.clause_names.get(slug, 0) + 1
        c.clause_names[slug] = count
        key = c.child_key(slug if count == 1 else f"{slug}-{count}")
        self.titles = [None, None, None]
        self.open = Block("clausula", "", p.text, key, c.child_path(name), c.key or None,
                          p.index, p.index)

    def open_annex(self, p):
        designator = p.heading.number
        key = "anexo" + (f"-{designator.lower()}" if designator else "")
        count = self.annex_keys.get(key, 0) + 1
        self.annex_keys[key] = count
        if count > 1:
            key = f"{key}-{count}"
        self.titles = [None, None, None]
        self.container = Container(name=p.heading.name, key=key, path=p.heading.name)
        self.result.containers.append(self.container)
        self.open = Block("anexo", designator, p.text, key, p.heading.name, None, p.index, p.index)
        self.root_open = True


def _could_be(raw, number):
    """Si un número leído por reconocimiento puede ser `number`: igual, con `$` o `§`
    en lugar de un 8, o seguido de una cifra que es el signo `°` leído como 7 o 9
    (`47` por `4°`)."""
    if not raw:
        return False
    read = raw.replace("$", "8").replace("§", "8")
    target = str(number)
    return read == target or (len(read) == len(target) + 1 and read.startswith(target) and read[-1] in "79")


def _slug(name):
    """Minúsculas, sin tildes y con guiones en lugar de espacios."""
    decomposed = unicodedata.normalize("NFD", name.lower())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", "-", plain.strip())


def _cover_end(paragraphs):
    """Último párrafo de la carátula que se descarta, o -1. Carátula GDE: desde el
    comienzo hasta el párrafo "Referencia:", si antes hay uno "Número:" y ningún
    encabezado de artículo, título o índice. Si no hay carátula GDE, el membrete solo,
    si es el primer párrafo."""
    number_seen = False
    for p in paragraphs:
        if p.heading.kind in (ARTICLE, TITLE, INDEX):
            break
        if GDE_NUMBER.match(p.text):
            number_seen = True
        elif GDE_REFERENCE.match(p.text) and number_seen:
            return p.index
    if paragraphs and LETTERHEAD.match(paragraphs[0].text):
        return 0
    return -1


def _index_blocks(paragraphs, same_container=True):
    """Índices: `{párrafo: primer párrafo del índice}`. Una serie de párrafos que son
    la palabra "ÍNDICE", títulos o encabezados de artículo sin texto, con al menos
    `INDEX_MIN_HEADINGS` encabezados, que termina en su último encabezado de artículo,
    y de cuyos números al menos `INDEX_MIN_HEADINGS` vuelven a aparecer después. Con
    `same_container` (un cuerpo), la repetición se busca solo hasta el siguiente
    encabezado "ANEXO", que abre otro contenedor y vuelve a numerar."""
    in_index = {}
    i = 0
    while i < len(paragraphs):
        if not _index_start(paragraphs[i]):
            i += 1
            continue
        j = i
        while j < len(paragraphs) and _index_member(paragraphs[j]):
            j += 1
        headings = [p for p in paragraphs[i:j] if p.heading.kind == ARTICLE]
        if len(headings) >= INDEX_MIN_HEADINGS:
            last = headings[-1].index
            later = set()
            for p in paragraphs[last + 1 :]:
                if same_container and p.heading.kind == ANNEX:
                    break
                if p.heading.kind == ARTICLE:
                    later.add(p.heading.article_number)
            repeated = sum(1 for p in headings if p.heading.article_number in later)
            if repeated >= INDEX_MIN_HEADINGS:
                # Los incisos que lista el índice después de su último artículo.
                while last + 1 < j and paragraphs[last + 1].heading.kind == INCISO:
                    last += 1
                for k in range(i, last + 1):
                    in_index[k] = i
                i = last + 1
                continue
        i = max(j, i + 1)
    return in_index


def _index_start(paragraph):
    """Un índice empieza con "ÍNDICE", un título o un encabezado de artículo sin texto;
    no con un inciso ni con un párrafo en mayúsculas (como el nombre del régimen que va
    antes del índice)."""
    kind = paragraph.heading.kind
    return kind in (INDEX, TITLE) or (kind == ARTICLE and paragraph.heading.heading_only)


def _index_member(paragraph):
    """Lo que puede ir en un índice: además de lo que lo empieza, los incisos y los
    párrafos en mayúsculas, como la segunda línea de un epígrafe largo (297/03)."""
    return _index_start(paragraph) or paragraph.heading.kind in (INCISO, UPPER)


# --- Incisos ----------------------------------------------------------------------------


@dataclass
class IncisoNode:
    heading: Heading
    index: int
    children: list = field(default_factory=list)
    end: int = 0


def find_incisos(paragraphs, block):
    """Los incisos de un artículo, como árbol de dos niveles con el último párrafo de
    cada uno."""
    roots, stack, introduced = [], [], []
    for p in paragraphs[block.first + 1 : block.last + 1]:
        h = p.heading
        if h.kind != INCISO:
            continue
        if h.word:
            # `Inciso N)`: siempre del primer nivel; cierra las listas abiertas.
            if stack and _same_form(stack[0].heading, h):
                if not _is_next(stack[0].heading.number, h.number):
                    continue
            elif not _is_first(h.number):
                continue
            node = IncisoNode(h, p.index)
            roots.append(node)
            stack = [node]
            continue
        level = next((i for i, node in enumerate(stack) if _same_form(node.heading, h)), None)
        if level is not None:
            if not _is_next(stack[level].heading.number, h.number):
                continue
            node = IncisoNode(h, p.index)
            siblings = stack[level - 1].children if level else roots
            siblings.append(node)
            stack = stack[:level] + [node]
        elif _is_first(h.number) and len(stack) < INCISO_LEVELS:
            node = IncisoNode(h, p.index)
            (stack[-1].children if stack else roots).append(node)
            stack.append(node)
        elif _is_first(h.number) and _introduces_list(paragraphs, p.index, block.first):
            # Los dos niveles ocupados y un párrafo que presenta una lista nueva: la lista
            # va en el primer nivel.
            node = IncisoNode(h, p.index)
            roots.append(node)
            stack = [node]
            introduced.append(node)
    _assign_ends(roots)
    for position, node in enumerate(roots):
        if node in introduced and position:
            # El párrafo que presenta la lista nueva es del artículo: el inciso anterior
            # termina antes.
            roots[position - 1].end = node.index - 2
    if roots and roots[-1].heading.word:
        # El último `Inciso N)` lleva sus párrafos hasta el final del artículo.
        roots[-1].end = block.last
    return roots


def _same_form(a, b):
    """Si dos encabezados de inciso son de la misma forma: el mismo estilo y los dos con
    la palabra "Inciso" o los dos sin ella."""
    return a.style == b.style and a.word == b.word


def _introduces_list(paragraphs, k, first):
    """Si el párrafo anterior al `k`, dentro del artículo, presenta una lista: no es un
    inciso y termina en dos puntos."""
    previous = paragraphs[k - 1]
    return k - 1 > first and previous.heading.kind != INCISO and previous.text.rstrip().endswith(":")


def after_last_inciso(nodes, end):
    """Listas de incisos cuyo último inciso tiene párrafos después, dentro de la unidad
    que contiene la lista (que termina en el párrafo `end`): pares (camino de nodos
    hasta ese inciso, cantidad de párrafos que quedaron en la unidad que lo contiene),
    en el orden del documento."""
    found = []
    for node in nodes:
        for path, count in after_last_inciso(node.children, node.end):
            found.append(([node] + path, count))
    if nodes and nodes[-1].end < end:
        found.append(([nodes[-1]], end - nodes[-1].end))
    return found


def _assign_ends(nodes):
    for position, node in enumerate(nodes):
        _assign_ends(node.children)
        if position + 1 < len(nodes):
            node.end = nodes[position + 1].index - 1
        else:
            node.end = max([node.index] + [child.end for child in node.children])


_LETTERS = "abcdefghijklmnñopqrstuvwxyz"


def _is_first(value):
    return value in ("a", "1")


def _is_next(previous, value):
    if previous.isdigit() and value.isdigit():
        return int(value) == int(previous) + 1
    if previous in _LETTERS and value in _LETTERS:
        step = _LETTERS.index(value) - _LETTERS.index(previous)
        # La eñe puede no usarse: después de la n vale la ñ o la o.
        return step == 1 or (previous == "n" and value == "o")
    return False
