"""Re-anclaje de la lista esperada a la lectura vigente del pliego (T-262, D-260-2; REQ-101,
REQ-102).

Una relectura del pliego (T-259) puede cambiar la partición (las claves de los tramos) sin
cambiar el texto, o cambiando cómo se escribe una tabla, y la lista congelada deja de encajar.
`medir_matriz --reanclar` reubica cada entrada por su ancla (y cada clave técnica por el texto que
ocupaba en la lectura anterior) y escribe un archivo NUEVO al lado de la lista, con la huella de la
original y de cada lectura y el visto bueno vacío; lo que no se puede reubicar se informa y
conserva su clave. Todo es sintético (P4): el pliego de tres renglones de las pruebas de la
medición y una segunda lectura armada en la prueba.
"""

import hashlib

import pytest
import yaml
from django.core.management import call_command
from django.core.management.base import CommandError

from evaluon.tenders import evaluation as ev
from evaluon.tenders import models as m
from tests.tenders.scripted import script  # noqa: F401  (fixture)
from tests.tenders.test_evaluation import make_case

pytestmark = pytest.mark.django_db

DAY = __import__("datetime").date(2026, 10, 13)

# Una entrada más, con un ancla que está dos veces en el pliego (en los renglones 1 y 2).
REPEATED = """  - id: S-009
    documento: Pliego sintético.pdf
    tramo: sec-iii/2.1
    pagina: 1
    ancla: "Bolsa de"
    clase: formal
    renglones: []
"""


def reread(document, *, renames=None, merges=(), insert=None):
    """La lectura siguiente de `document`, con la partición cambiada como en una relectura:
    `renames` cambia claves, `merges` junta dos tramos seguidos en uno (`(primera, segunda,
    nueva)`) e `insert` (`(clave, texto)`) agrega texto al principio de un tramo, de modo que el
    texto canónico cambia."""
    renames = renames or {}
    old = document.readings.order_by("-sequence").first()
    segments = list(old.segments.order_by("order"))
    canonical = old.canonical_text
    pieces, skip = [], set()
    for index, segment in enumerate(segments):
        if segment.key in skip:
            continue
        start, end, key = segment.char_start, segment.char_end, renames.get(segment.key,
                                                                            segment.key)
        for first, second, new in merges:
            if segment.key == first:
                other = next(s for s in segments if s.key == second)
                end, key = other.char_end, new
                skip.add(second)
        pieces.append((segment, start, end, key))
    text, shift, rows = canonical, 0, []
    if insert is not None:
        at = next(s for s in segments if s.key == insert[0]).char_start
        text = canonical[:at] + insert[1] + canonical[at:]
    for segment, start, end, key in pieces:
        new_start, new_end = start, end
        if insert is not None:
            at = next(s for s in segments if s.key == insert[0]).char_start
            grow = len(insert[1])
            new_start = start + grow if start > at else start
            new_end = end + grow if end > at else end
        rows.append((segment, key, new_start, new_end))
    reading = m.Reading.objects.create(
        document=document, sequence=old.sequence + 1, pages=old.pages, tables=old.tables,
        canonical_text=text, canonical_sha256=hashlib.sha256(text.encode()).hexdigest(),
        items=old.items, tool_versions=old.tool_versions, report=old.report)
    for order, (segment, key, start, end) in enumerate(rows, start=1):
        m.Segment.objects.create(
            reading=reading, order=order, key=key, label=segment.label, path=segment.path,
            segment_type=segment.segment_type, section_class=segment.section_class,
            items=segment.items, page_start=segment.page_start, page_end=segment.page_end,
            char_start=start, char_end=end, text=text[start:end],
            text_origin=segment.text_origin)
    return reading


@pytest.fixture
def case(operator_user, script, tmp_path):  # noqa: F811
    procedure, document, path, text = make_case(operator_user, script, tmp_path)
    text = text + REPEATED
    path.write_text(text, encoding="utf-8")
    return procedure, document, path, text


def test_the_keys_of_the_new_partition_are_found_by_anchor_and_by_text(case):
    """REQ-101 (D-260-2): con la partición nueva, una entrada formal o económica se reubica por su
    ancla, y las claves técnicas, generales o de un renglón, por los tramos vigentes que ocupan su
    texto; la lista re-anclada se comprueba contra la lectura vigente."""
    procedure, document, path, _ = case
    reread(document, renames={"sec-i/1.1": "sec-i/1/p-1", "sec-ii/1.1": "sec-ii/1/p-1"},
           merges=[("sec-iii/1", "sec-iii/1.1", "sec-iii/1/tabla-1")])
    expected = ev.load_expected(path)
    assert not ev.verify_expected(expected, procedure).ok

    result = ev.reanchor_expected(expected, procedure)

    moved = {(r.owner, r.old): r.new for r in result.relocations}
    assert moved[("S-001", "sec-i/1.1")] == ("sec-i/1/p-1",)
    assert moved[("tecnico_general", "sec-ii/1.1")] == ("sec-ii/1/p-1",)
    assert moved[("S-T1", "sec-iii/1")] == moved[("S-T1", "sec-iii/1.1")] == ("sec-iii/1/tabla-1",)
    assert result.entries["S-001"] == "reubicada" and result.entries["S-002"] == "sin_cambio"
    assert not result.unplaced
    target = ev.write_reanchored(result, DAY)
    reanchored = ev.load_expected(target, require_approval=False)
    verification = ev.verify_expected(reanchored, procedure)
    assert verification.problems == ["la lista no tiene visto bueno"]
    assert [r.key for r in next(i for i in reanchored.items if i.id == "S-T1").refs] == [
        "sec-iii/1/tabla-1"]


def test_the_new_file_is_written_beside_the_list_with_its_fingerprints_and_no_approval(case):
    """REQ-101 (D-260-2): el archivo nuevo se llama `matriz-esperada.reanclada-AAAA-MM-DD.yaml`,
    va al lado de la lista, trae la huella de la lista original y la de cada lectura (texto y
    partición) y el visto bueno vacío para el Coordinador; la lista original no cambia."""
    procedure, document, path, _ = case
    before = path.read_bytes()
    reading = reread(document, renames={"sec-i/1.1": "sec-i/1/p-1"})

    target = ev.write_reanchored(ev.reanchor_expected(ev.load_expected(path), procedure), DAY)

    assert target == path.parent / "matriz-esperada.reanclada-2026-10-13.yaml"
    assert path.read_bytes() == before
    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert data["visto_bueno"] == ""
    original = data["reanclaje"]["lista_original"]
    assert original["archivo"] == "matriz-esperada.yaml"
    assert original["sha256"] == hashlib.sha256(before).hexdigest()
    assert original["visto_bueno"].startswith("responsable sintético")
    [entry] = data["reanclaje"]["lecturas"]
    assert entry["archivo"] == document.file_name and entry["lectura"] == reading.sequence
    assert entry["texto_canonico_sha256"] == reading.canonical_sha256
    assert len(entry["particion_sha256"]) == 64
    old = document.readings.get(sequence=reading.sequence - 1)
    assert entry["particion_sha256"] != ev._partition_sha256(old)
    with pytest.raises(ev.ExpectedNotApproved):
        ev.load_expected(target)
    assert {r["id"] for r in data["requisitos"]} == {i.id for i in ev.load_expected(path).items}


def test_an_entry_that_cannot_be_relocated_is_reported_and_keeps_its_key(case):
    """REQ-101 (D-260-2): una entrada cuyo ancla no está en la lectura vigente no se reubica en
    otro lado: se informa con su motivo y conserva su clave en el archivo nuevo."""
    procedure, document, path, text = case
    path.write_text(text.replace("tramo: sec-i/2.1\n    pagina: 1\n    ancla: \"a los 90 días",
                                 "tramo: sec-i/9.9\n    pagina: 1\n    ancla: \"a los 99 días"),
                    encoding="utf-8")
    reread(document, renames={"sec-i/1.1": "sec-i/1/p-1"})

    result = ev.reanchor_expected(ev.load_expected(path), procedure)

    [lost] = result.unplaced
    assert (lost.owner, lost.old, lost.reason) == ("S-002", "sec-i/9.9",
                                                    "el ancla no está en la lectura vigente")
    assert result.entries["S-002"] == "no_reubicada"
    data = yaml.safe_load(ev.write_reanchored(result, DAY).read_text(encoding="utf-8"))
    assert next(r for r in data["requisitos"] if r["id"] == "S-002")["tramo"] == "sec-i/9.9"
    assert data["reanclaje"]["no_reubicadas"] == [
        {"id": "S-002", "campo": "tramo", "tramo": "sec-i/9.9",
         "motivo": "el ancla no está en la lectura vigente"}]
    assert data["reanclaje"]["entradas"]["no_reubicadas"] == 1


def test_a_repeated_anchor_takes_the_place_it_had_in_the_previous_reading(case):
    """REQ-101 (D-260-2): si el ancla está más de una vez en la lectura vigente, la entrada va al
    tramo que ocupa el lugar que el ancla tenía en la lectura anterior, no a la primera aparición."""
    procedure, document, path, _ = case
    reread(document, renames={"sec-iii/1.1": "sec-iii/1/p-1", "sec-iii/2.1": "sec-iii/2/p-1"})

    result = ev.reanchor_expected(ev.load_expected(path), procedure)

    [moved] = result.of("S-009")
    assert moved.new == ("sec-iii/2/p-1",) and moved.occurrence == 1


def test_a_repeated_anchor_without_a_previous_place_is_not_guessed(case):
    """REQ-101 (D-260-2): si el ancla está dos veces y ninguna lectura anterior tiene la clave de la
    lista, no se elige una: se informa."""
    procedure, document, path, text = case
    path.write_text(text.replace("tramo: sec-iii/2.1\n    pagina: 1\n    ancla: \"Bolsa de\"",
                                 "tramo: sec-iii/7.7\n    pagina: 1\n    ancla: \"Bolsa de\""),
                    encoding="utf-8")
    reread(document, renames={"sec-iii/1.1": "sec-iii/1/p-1", "sec-iii/2.1": "sec-iii/2/p-1"})

    [lost] = ev.reanchor_expected(ev.load_expected(path), procedure).of("S-009")

    assert not lost.relocated and "más de una vez" in lost.reason


def test_a_technical_key_follows_its_text_when_the_reading_writes_it_differently(case):
    """REQ-101 (D-260-2): si la relectura cambia el texto canónico (por ejemplo, una tabla escrita
    por celdas), la clave técnica se reubica alineando las palabras de las dos lecturas; si casi
    nada de su texto sigue en la lectura vigente, se informa y no se reubica."""
    procedure, document, path, _ = case
    reread(document, renames={"sec-iii/2.2": "sec-iii/2/p-2", "sec-iii/2.1": "sec-iii/2/p-1"},
           insert=("sec-iii/2.1", "Celda agregada | "))

    result = ev.reanchor_expected(ev.load_expected(path), procedure)

    moved = {r.old: r.new for r in result.of("S-T2")}
    assert moved == {"sec-iii/2.1": ("sec-iii/2/p-1",), "sec-iii/2.2": ("sec-iii/2/p-2",)}
    assert result.of("S-009")[0].new == ("sec-iii/2/p-1",)


def test_a_technical_key_whose_text_is_gone_is_reported(case):
    """REQ-101 (D-260-2): una clave técnica cuyo texto no está en la lectura vigente se informa con
    la parte que se encontró, y no se reubica."""
    procedure, document, path, _ = case
    old = document.readings.order_by("-sequence").first()
    gone = old.segments.get(key="sec-iii/2.2")
    reading = reread(document, renames={"sec-iii/2.2": "sec-iii/2/p-2"})
    replaced = reading.canonical_text.replace(gone.text, "Z" * len(gone.text))
    m.Reading.objects.filter(pk=reading.pk).update(canonical_text=replaced)
    m.Segment.objects.filter(reading=reading, key="sec-iii/2/p-2").update(
        text="Z" * len(gone.text))

    result = ev.reanchor_expected(ev.load_expected(path), procedure)

    [lost] = [r for r in result.of("S-T2") if r.old == "sec-iii/2.2"]
    assert not lost.relocated and lost.reason.startswith("solo el 0,0 %")


def test_exclusions_marked_on_the_original_list_apply_to_the_reanchored_one(case, tmp_path):
    """REQ-102 (T-238, D-260-2): la lista re-anclada tiene las mismas entradas que la original, así
    que valen sus exclusiones (marcadas con la huella de la original); con otra huella, no."""
    procedure, document, path, _ = case
    reread(document, renames={"sec-i/1.1": "sec-i/1/p-1"})
    target = ev.write_reanchored(ev.reanchor_expected(ev.load_expected(path), procedure), DAY)
    reanchored = ev.load_expected(target, require_approval=False)
    exclusions = tmp_path / "exclusiones.yaml"
    original = hashlib.sha256(path.read_bytes()).hexdigest()
    exclusions.write_text(f"lista_sha256: \"{original}\"\nvisto_bueno: \"Coordinador\"\n"
                          "excluidas:\n  - {id: S-002, motivo: pago}\n", encoding="utf-8")

    loaded = ev.load_exclusions(exclusions, reanchored)

    assert reanchored.original_sha256 == original and loaded.motives == {"S-002": "pago"}
    reanchored.exclusions = loaded
    assert "coincide con la de la lista original" in ev.exclusion_lines(reanchored)[0]
    exclusions.write_text(exclusions.read_text(encoding="utf-8").replace(original, "e" * 64),
                          encoding="utf-8")
    with pytest.raises(ev.ExpectedError):
        ev.load_exclusions(exclusions, reanchored)


def test_the_command_reanchors_without_the_model_and_never_overwrites(
        case, operator_user, script, monkeypatch, capsys):  # noqa: F811
    """REQ-101 (D-260-2): `medir_matriz --reanclar` no usa el modelo, escribe el archivo nuevo,
    informa las cuentas sin texto del pliego y no pisa un archivo que ya existe."""
    procedure, document, path, _ = case
    reread(document, renames={"sec-i/1.1": "sec-i/1/p-1"})
    monkeypatch.setattr("evaluon.accounts.permissions.authenticate_command",
                        lambda username: operator_user)
    monkeypatch.setattr("django.utils.timezone.localdate", lambda *args: DAY)
    before, calls = path.read_bytes(), len(script.calls)

    call_command("medir_matriz", usuario="operador", procedimiento=procedure.number,
                 esperada=str(path), reanclar=True)

    out = capsys.readouterr().out
    assert "matriz-esperada.reanclada-2026-10-13.yaml" in out
    assert "Entradas de la lista: 10; sin cambio 9; reubicadas 1; no reubicadas 0" in out
    assert "Anclas encontradas: 6 de 6" in out and "garantía" not in out
    assert path.read_bytes() == before and len(script.calls) == calls
    assert not m.MatrixRun.objects.exists()
    with pytest.raises(CommandError, match="no se pisa"):
        call_command("medir_matriz", usuario="operador", procedimiento=procedure.number,
                     esperada=str(path), reanclar=True)
