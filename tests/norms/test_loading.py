"""Carga de una norma (T-014; plan 001, "Ingesta", "Una norma en más de un archivo",
"Dónde se guarda el archivo original" y "Registro de auditoría").

Documento de prueba: `tests/fixtures/disp-247-2022-anexo-extracto.pdf` (T-012), las
páginas 1 a 6 del anexo de la Disposición AFIP 247/2022, documento público (P4). El
segundo documento de una misma norma se arma en memoria con las páginas 5 y 6 del
extracto, sin cambiar su contenido: es otro archivo, con otro texto canónico. Los PDF
truncados y los archivos que no son PDF también se arman en memoria.
"""

import hashlib
import io
from datetime import date
from io import StringIO
from pathlib import Path

import pypdfium2
import pytest
from django.core.management import CommandError, call_command

from evaluon.accounts import permissions
from evaluon.accounts.permissions import RoleRejected
from evaluon.audit.models import AuditEvent
from evaluon.norms.models import (
    CorpusVersion,
    Document,
    DocumentFile,
    Norm,
    Reading,
    Unit,
)
from evaluon.norms.reading import read_document
from evaluon.norms.services import loading
from evaluon.norms.splitting import RULES_VERSION, split_document
from tests.conftest import TEST_PASSWORD

REPO = Path(__file__).resolve().parents[2]
EXTRACT = REPO / "tests" / "fixtures" / "disp-247-2022-anexo-extracto.pdf"
EXTRACT_BYTES = EXTRACT.read_bytes()

# Datos de la Disposición AFIP 247/2022 según el manifiesto del corpus y el ADR-0006.
DATA_247 = {
    "category": "regimen_especifico",
    "norm_type": "Disposición",
    "number": "247",
    "year": 2022,
    "issuer": "AFIP",
    "title": "Régimen General para Contrataciones de Bienes, Servicios y Obras Públicas",
    "citation": "Disposición AFIP 247/2022",
    "publication_date": date(2022, 11, 30),
    "effective_from": date(2023, 1, 1),
    "source": "https://servicios.infoleg.gob.ar/infolegInternet/anexos/375000-379999/"
    "375829/disp247.pdf",
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def pages_five_and_six_pdf():
    """Las páginas 5 y 6 del extracto, solas, como otro archivo PDF: traen los artículos
    1 a 7 sin la carátula ni el comienzo del índice."""
    source = pypdfium2.PdfDocument(EXTRACT_BYTES)
    target = pypdfium2.PdfDocument.new()
    target.import_pages(source, [4, 5])
    buffer = io.BytesIO()
    target.save(buffer)
    return buffer.getvalue()


def load(user, data=EXTRACT_BYTES, file_name="disp-247-2022-anexo-extracto.pdf", **fields):
    values = {**DATA_247, "part": "anexo", "general_regime": True, **fields}
    return loading.load_norm(user, data=data, file_name=file_name, **values)


def nothing_stored():
    return not (
        Norm.objects.exists()
        or Document.objects.exists()
        or DocumentFile.objects.exists()
        or Reading.objects.exists()
        or Unit.objects.exists()
    )


# --- Función de carga ----------------------------------------------------------------


@pytest.mark.django_db
def test_load_stores_norm_with_its_data_normalized(read_write_user):
    """REQ-001, REQ-017, REQ-020: la carga guarda la norma con su categoría, sus datos
    (tipo, número, año y organismo normalizados), su título, su nombre de cita y su
    marca de régimen general."""
    result = load(read_write_user)

    norm = Norm.objects.get()
    assert result.norm == norm and result.created_norm
    assert (norm.norm_type, norm.number, norm.year, norm.issuer) == (
        "disposicion", "247", 2022, "afip"
    )
    assert norm.category == "regimen_especifico"
    assert norm.title == DATA_247["title"]
    assert norm.citation == "Disposición AFIP 247/2022"
    assert norm.general_regime is True
    assert norm.created_by == read_write_user


@pytest.mark.django_db
def test_load_stores_document_with_part_dates_and_source(read_write_user):
    """REQ-001, REQ-020: el documento queda con su parte, su fecha de publicación, la
    fecha de vigencia tal como la escribió la persona, su fuente y los datos del
    archivo; sin versión y fuera de uso hasta que se valide."""
    result = load(read_write_user)

    document = Document.objects.get()
    assert result.document == document
    assert document.part == "anexo"
    assert document.publication_date == date(2022, 11, 30)
    assert document.effective_from == date(2023, 1, 1)
    assert document.effective_to is None
    assert document.source == DATA_247["source"]
    assert document.file_name == "disp-247-2022-anexo-extracto.pdf"
    assert document.file_format == "pdf"
    assert document.file_size == len(EXTRACT_BYTES)
    assert document.file_sha256 == sha256(EXTRACT_BYTES)
    assert document.in_use is False and document.version_number is None
    assert document.loaded_by == read_write_user


@pytest.mark.django_db
def test_load_keeps_the_original_byte_by_byte(read_write_user):
    """REQ-002: el original se guarda byte por byte; su huella es igual a la del
    archivo cargado."""
    load(read_write_user)

    stored = bytes(DocumentFile.objects.get().content)
    assert stored == EXTRACT_BYTES
    assert sha256(stored) == sha256(EXTRACT_BYTES) == Document.objects.get().file_sha256


@pytest.mark.django_db
def test_load_stores_pending_reading_with_canonical_text_and_report(read_write_user):
    """REQ-004: la lectura queda `pending`, con el texto canónico y su huella, las
    versiones de las herramientas y de las reglas, y el informe en datos y en texto,
    iguales a los de la partición."""
    expected = split_document(read_document(EXTRACT_BYTES), part="anexo")

    result = load(read_write_user)

    reading = Reading.objects.get()
    assert result.reading == reading
    assert reading.sequence == 1
    assert reading.status == "pending"
    assert reading.validated_at is None
    assert reading.canonical_text == expected.canonical_text
    assert reading.canonical_sha256 == expected.canonical_sha256
    assert reading.canonical_sha256 == sha256(reading.canonical_text.encode("utf-8"))
    assert reading.tool_versions["rules_version"] == RULES_VERSION
    assert "pdfplumber" in reading.tool_versions
    assert reading.report == expected.report
    assert reading.report_text == expected.report_text
    assert reading.pages["pages"][0]["number"] == 1 and len(reading.pages["pages"]) == 6
    assert reading.created_by == read_write_user


@pytest.mark.django_db
def test_load_as_annex_stores_units_under_the_annex_root(read_write_user):
    """REQ-020, REQ-004: cargado el extracto como parte `anexo`, las unidades cuelgan de
    la unidad raíz `anexo` y sus claves son `anexo/art-N`; cada una guarda el texto
    literal de su tramo del texto canónico."""
    expected = split_document(read_document(EXTRACT_BYTES), part="anexo")

    load(read_write_user)

    reading = Reading.objects.get()
    units = list(reading.units.order_by("order"))
    assert [u.key for u in units] == [u.key for u in expected.units]
    root = units[0]
    assert (root.key, root.unit_type, root.parent) == ("anexo", "anexo", None)
    articles = units[1:]
    assert articles and all(u.key.startswith("anexo/art-") for u in articles)
    assert all(u.parent == root for u in articles)
    assert "anexo/art-1" in {u.key for u in articles}
    for unit, draft in zip(units, expected.units, strict=True):
        assert unit.text == reading.canonical_text[unit.char_start:unit.char_end]
        assert (unit.unit_type, unit.number, unit.label, unit.path, unit.order,
                unit.page_start, unit.page_end, unit.text_origin) == (
            draft.unit_type, draft.number, draft.label, draft.path, draft.order,
            draft.page_start, draft.page_end, draft.text_origin)


@pytest.mark.django_db
def test_load_without_part_is_the_body(read_write_user):
    """REQ-020: sin parte, el documento es el cuerpo y las claves no llevan prefijo."""
    load(read_write_user, part=None, general_regime=False,
         category="otra_normativa")

    assert Document.objects.get().part == "cuerpo"
    keys = set(Unit.objects.values_list("key", flat=True))
    assert "art-1" in keys and not any(key.startswith("anexo") for key in keys)


@pytest.mark.django_db
def test_load_without_category_is_not_incorporated_and_asks_for_it(read_write_user):
    """REQ-017: una carga sin categoría no incorpora nada y pide el dato."""
    with pytest.raises(loading.MissingData) as raised:
        load(read_write_user, category=None)

    assert "categoría" in str(raised.value)
    assert "regimen_especifico" in str(raised.value)
    assert nothing_stored()


@pytest.mark.django_db
def test_invalid_category_is_rejected(read_write_user):
    """REQ-017: una categoría que no es una de las cinco se rechaza, con las válidas."""
    with pytest.raises(loading.InvalidData) as raised:
        load(read_write_user, category="ley")

    assert "recomendacion_auditoria" in str(raised.value)
    assert nothing_stored()


@pytest.mark.django_db
def test_missing_norm_data_is_rejected_and_named(read_write_user):
    """REQ-001: sin los datos de la norma no se incorpora; el mensaje dice cuáles
    faltan."""
    with pytest.raises(loading.MissingData) as raised:
        load(read_write_user, number="", source=None, effective_from=None)

    message = str(raised.value)
    assert "número" in message and "fuente" in message and "fecha de vigencia" in message
    assert nothing_stored()


@pytest.mark.django_db
def test_new_norm_without_citation_name_is_rejected(read_write_user):
    """REQ-001: al dar de alta una norma nueva el nombre de cita es obligatorio."""
    with pytest.raises(loading.MissingData, match="nombre de cita"):
        load(read_write_user, citation="  ")

    assert nothing_stored()


@pytest.mark.django_db
def test_general_regime_with_other_category_is_rejected(read_write_user):
    """REQ-020, REQ-017: la marca de régimen general solo se acepta con categoría
    `regimen_especifico`."""
    with pytest.raises(loading.InvalidData, match="régimen general"):
        load(read_write_user, category="marco_nacional", general_regime=True)

    assert nothing_stored()


@pytest.mark.django_db
def test_invalid_part_is_rejected(read_write_user):
    """REQ-020: la parte es `cuerpo` o la clave de un anexo."""
    with pytest.raises(loading.InvalidData, match="parte"):
        load(read_write_user, part="apendice")

    assert nothing_stored()


@pytest.mark.django_db
def test_a_second_part_is_added_to_the_same_norm(read_write_user):
    """REQ-001, REQ-020: un segundo documento con otra parte queda bajo la misma norma,
    aunque no traiga el nombre de cita."""
    first = load(read_write_user)
    second = load(read_write_user, data=pages_five_and_six_pdf(),
                  file_name="paginas-5-y-6.pdf",
                  part="cuerpo", citation=None)

    assert Norm.objects.count() == 1
    assert second.norm == first.norm and not second.created_norm
    assert sorted(Document.objects.values_list("part", flat=True)) == ["anexo", "cuerpo"]
    body_keys = set(second.reading.units.values_list("key", flat=True))
    assert body_keys and all(key.startswith("art-") for key in body_keys)


@pytest.mark.django_db
def test_a_second_part_with_different_norm_data_is_rejected(read_write_user):
    """REQ-001, REQ-020: si los datos de la norma indicados difieren de los registrados,
    no se incorpora y se muestran los registrados."""
    load(read_write_user)

    with pytest.raises(loading.NormDataMismatch) as raised:
        load(read_write_user, data=pages_five_and_six_pdf(), part="cuerpo",
             general_regime=False,
             title="Otro título")

    message = str(raised.value)
    assert DATA_247["title"] in message and "Régimen general: sí" in message
    assert "Otro título" in message
    assert Document.objects.count() == 1


@pytest.mark.django_db
def test_same_part_already_loaded_is_rejected(read_write_user):
    """REQ-001: otro archivo de una parte que la norma ya tiene no se incorpora en
    esta versión (la confirmación expresa de "misma norma" es de REQ-011)."""
    load(read_write_user)

    with pytest.raises(loading.LoadRefused, match="parte anexo"):
        load(read_write_user, data=pages_five_and_six_pdf())

    assert Document.objects.count() == 1


@pytest.mark.django_db
def test_same_file_twice_is_rejected(read_write_user):
    """REQ-001: el mismo archivo no se incorpora dos veces."""
    load(read_write_user)

    with pytest.raises(loading.LoadRefused, match="ya está cargado"):
        load(read_write_user, part="cuerpo", general_regime=True)

    assert Document.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "data",
    [
        EXTRACT_BYTES[: len(EXTRACT_BYTES) // 2],
        b"<html><body>%PDF- dentro del primer kilobyte</body></html>",
        b"Esto no es un PDF.",
    ],
    ids=["pdf-truncado", "html-con-marca-pdf", "texto"],
)
def test_unreadable_file_is_reported_and_not_incorporated(read_write_user, data):
    """REQ-004: un archivo que no se puede leer (un PDF truncado, un HTML con la marca
    de PDF, un archivo de otro formato) no se incorpora y se informa en lenguaje
    llano."""
    with pytest.raises(loading.UnreadableFile, match="No se pudo leer el archivo"):
        load(read_write_user, data=data)

    assert nothing_stored()


@pytest.mark.django_db
def test_read_only_user_cannot_load(read_user):
    """REQ-016, REQ-001: un usuario de lectura no puede cargar normas; no se guarda
    nada."""
    with pytest.raises(RoleRejected):
        load(read_user)

    assert nothing_stored()
    assert not AuditEvent.objects.filter(event_type="load").exists()


# --- Registro ------------------------------------------------------------------------


@pytest.mark.django_db
def test_load_event_says_who_when_and_what(read_write_user):
    """REQ-012: la carga deja el hecho `load` con quién, cuándo y qué: norma,
    documento, lectura, datos ingresados con su parte y su marca, archivo, huellas,
    versiones de las herramientas y resumen del informe. No crea versión de la
    normativa."""
    result = load(read_write_user)

    event = AuditEvent.objects.get(event_type="load")
    assert result.event == event
    assert (event.outcome, event.channel, event.user, event.username) == (
        "ok", "command", read_write_user, read_write_user.username
    )
    assert event.occurred_at is not None
    detail = event.detail
    assert detail["norm"] == result.norm.pk
    assert detail["document"] == result.document.pk
    assert detail["reading"] == result.reading.pk
    assert detail["norm_created"] is True
    assert detail["data"]["category"] == "regimen_especifico"
    assert detail["data"]["part"] == "anexo"
    assert detail["data"]["general_regime"] is True
    assert detail["data"]["citation"] == "Disposición AFIP 247/2022"
    assert detail["data"]["effective_from"] == "2023-01-01"
    assert detail["file"] == {
        "name": "disp-247-2022-anexo-extracto.pdf",
        "format": "pdf",
        "size": len(EXTRACT_BYTES),
        "sha256": sha256(EXTRACT_BYTES),
    }
    assert detail["canonical_sha256"] == result.reading.canonical_sha256
    assert detail["tool_versions"]["rules_version"] == RULES_VERSION
    report = result.reading.report
    assert detail["report"] == {
        "units_by_type": report["units"]["by_type"],
        "pages_not_read": report["pages"]["not_read"],
        "unlocated": len(report["unlocated"]),
    }
    assert not CorpusVersion.objects.exists()
    assert event.corpus_version is None


@pytest.mark.django_db
def test_refused_load_is_recorded(read_write_user):
    """REQ-012, REQ-017: una carga rechazada también queda registrada, con el motivo y
    sin nada incorporado."""
    with pytest.raises(loading.MissingData):
        load(read_write_user, category=None)

    event = AuditEvent.objects.get(event_type="load")
    assert (event.outcome, event.user) == ("rejected", read_write_user)
    assert event.detail["reason"] == "missing_data"
    assert event.detail["missing"] == ["category"]
    assert event.detail["file"]["sha256"] == sha256(EXTRACT_BYTES)


@pytest.mark.django_db
def test_unreadable_file_is_recorded(read_write_user):
    """REQ-012, REQ-004: el intento con un archivo que no se puede leer queda
    registrado."""
    with pytest.raises(loading.UnreadableFile):
        load(read_write_user, data=b"Esto no es un PDF.")

    event = AuditEvent.objects.get(event_type="load")
    assert event.outcome == "rejected"
    assert event.detail["reason"] == "unreadable_file"


# --- Comando cargar_norma ------------------------------------------------------------


@pytest.fixture
def typed_password(monkeypatch):
    """Simula la clave escrita por teclado. Guarda los textos con que se la pidió."""
    prompts = []

    def type_(password=TEST_PASSWORD):
        def fake_password(prompt):
            prompts.append(prompt)
            return password

        monkeypatch.setattr(permissions, "read_password", fake_password)
        return prompts

    return type_


COMMAND_ARGS = [
    "--categoria", "regimen_especifico",
    "--tipo", "Disposición",
    "--numero", "247",
    "--anio", "2022",
    "--organismo", "AFIP",
    "--titulo", DATA_247["title"],
    "--nombre", "Disposición AFIP 247/2022",
    "--fecha-publicacion", "2022-11-30",
    "--fecha-vigencia", "2023-01-01",
    "--fuente", DATA_247["source"],
]


def run_cargar_norma(*args, **options):
    out = StringIO()
    call_command("cargar_norma", *args, stdout=out, stderr=StringIO(), **options)
    return out.getvalue()


def without(args, option):
    index = args.index(option)
    return args[:index] + args[index + 2:]


@pytest.mark.django_db
def test_command_loads_the_extract_as_annex_and_general_regime(
    read_write_user, typed_password
):
    """REQ-001, REQ-020, REQ-012: `cargar_norma` con `--parte anexo` y
    `--regimen-general` carga el extracto, dice qué lectura quedó pendiente y deja el
    hecho por comando."""
    typed_password()

    out = run_cargar_norma(str(EXTRACT), *COMMAND_ARGS, "--parte", "anexo",
                           "--regimen-general", usuario=read_write_user.username)

    norm = Norm.objects.get()
    reading = Reading.objects.get()
    assert norm.general_regime and norm.citation == "Disposición AFIP 247/2022"
    assert Document.objects.get().part == "anexo"
    assert f"Lectura {reading.pk}" in out
    assert "pendiente de validación" in out
    assert f"ver_informe {reading.pk}" in out
    assert AuditEvent.objects.get(event_type="load").channel == "command"


@pytest.mark.django_db
def test_command_without_category_asks_for_it(read_write_user, typed_password):
    """REQ-017: `cargar_norma` sin `--categoria` no incorpora y pide el dato."""
    typed_password()

    with pytest.raises(CommandError, match="--categoria"):
        run_cargar_norma(str(EXTRACT), *without(COMMAND_ARGS, "--categoria"),
                         usuario=read_write_user.username)

    assert nothing_stored()


@pytest.mark.django_db
def test_command_rejects_general_regime_with_other_category(
    read_write_user, typed_password
):
    """REQ-020: `--regimen-general` con otra categoría se rechaza."""
    typed_password()
    args = without(COMMAND_ARGS, "--categoria") + ["--categoria", "dictamen_legal"]

    with pytest.raises(CommandError, match="régimen general"):
        run_cargar_norma(str(EXTRACT), *args, "--regimen-general",
                         usuario=read_write_user.username)

    assert nothing_stored()


@pytest.mark.django_db
def test_command_rejects_read_only_user(read_user, typed_password):
    """REQ-016: un usuario de lectura que corre `cargar_norma` es rechazado y no se
    incorpora nada."""
    typed_password()

    with pytest.raises(CommandError, match="no tiene permiso"):
        run_cargar_norma(str(EXTRACT), *COMMAND_ARGS, usuario=read_user.username)

    assert nothing_stored()


@pytest.mark.django_db
def test_command_wrong_password_is_rejected(read_write_user, typed_password):
    """REQ-016: con una clave incorrecta el comando da el mensaje único y no carga."""
    typed_password("clave-equivocada-sintetica")

    with pytest.raises(CommandError, match=permissions.LOGIN_FAILED_MESSAGE):
        run_cargar_norma(str(EXTRACT), *COMMAND_ARGS, usuario=read_write_user.username)

    assert nothing_stored()


@pytest.mark.django_db
def test_command_reports_missing_file(read_write_user, typed_password):
    """REQ-001: un archivo que no existe se informa en lenguaje llano."""
    typed_password()

    with pytest.raises(CommandError, match="No se encontró el archivo"):
        run_cargar_norma(str(REPO / "no-existe.pdf"), *COMMAND_ARGS,
                         usuario=read_write_user.username)


@pytest.mark.django_db
def test_command_rejects_badly_written_date(read_write_user, typed_password):
    """REQ-001: una fecha mal escrita se rechaza y no se incorpora nada."""
    typed_password()
    args = without(COMMAND_ARGS, "--fecha-vigencia") + ["--fecha-vigencia", "1/1/2023"]

    with pytest.raises(CommandError, match="AAAA-MM-DD"):
        run_cargar_norma(str(EXTRACT), *args, usuario=read_write_user.username)

    assert nothing_stored()
